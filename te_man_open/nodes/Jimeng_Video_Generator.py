# -*- coding: utf-8 -*-
"""te_man_open · Jimeng_Video_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

te_man_open 纯 Python 复刻（spec/Jimeng_Video_Generator.md 含动态回填节）：
- 即梦/Seedance 2.0 四渠道视频节点（渠道2 LongXia-G-Seedance-2.0 /
  渠道3 seedance2.0-full-9img / 渠道4 sora-v3-pro / 渠道5 sora-v3-fast）
- 三种素材提交方式并存（逐渠道映射 spec 标注未确认，此处按重建策略落地）：
  b64_json（reference_images/reference_audios）、data URI（image_urls）、
  参考图超 15MB 走图床 http://teh.tetae.top:40061/api/index.php（内置 token 换 URL）
- POST {base}/v1/videos 提交 → sleep 轮询 GET /v1/videos/{task_id} → 流式下载到 output
本节点自建 requests.Session 直连（不复用 api_client，spec §2 负证据），
含 trust_env 代理开关；requests/torch/numpy/comfy 系全部惰性导入。
"""

import base64
import io
import json
import os
import re
import time
import wave

try:  # 包内相对导入；以文件方式直载时回退绝对导入
    from ..shared.config_manager import CONFIG_MANAGER
    from ..shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_file_part
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared.config_manager import CONFIG_MANAGER
    from te_man_open.shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_file_part
    from te_man_open.shared.logger import logger


# ==================== 模块常量（spec §7.4 动态回填实锤值） ====================

def _probe_comfy_video():
    """探测 comfy_api 的 VideoFromFile 是否可用（_HAS_COMFY_VIDEO 守卫）。"""
    try:
        from comfy_api.input_impl import VideoFromFile  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        try:
            from comfy_api.latest.input_impl import VideoFromFile  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False


#: ComfyUI 视频支持可用性（真机 introspection 实锤值：True）
_HAS_COMFY_VIDEO = _probe_comfy_video()

#: 请求 UA 与输出文件名前缀（配 .mp4）
_USER_AGENT = "ComfyUI-TE_API/1.0"
_OUTPUT_FILE_PREFIX = "jimeng_video_"

#: 渠道标签（spec §7.4 原文实锤）
_CHANNEL2_LABEL = "渠道2(2.0)"
_CHANNEL3_LABEL = "渠道3(2.0)"
_CHANNEL4_LABEL = "渠道4(2.0)"
_CHANNEL5_LABEL = "渠道5(2.0fast)"
_LEGACY_CHANNEL4_LABEL = "渠道4(2.0fast)"
_CHANNEL_OPTIONS = [_CHANNEL2_LABEL, _CHANNEL3_LABEL, _CHANNEL4_LABEL, _CHANNEL5_LABEL]
_ALL_CHANNEL_OPTIONS = [
    "渠道1", "渠道2", _CHANNEL2_LABEL, "渠道3", _CHANNEL3_LABEL,
    "渠道4", _CHANNEL4_LABEL, _LEGACY_CHANNEL4_LABEL, "渠道5", _CHANNEL5_LABEL,
]

#: 渠道 → 模型字符串（spec §7.4 常量实锤）
_JIMENG_SEEDANCE_MODEL_G = "LongXia-G-Seedance-2.0"
_JIMENG_SEEDANCE_MODEL_V = "LongXia-V-Seedance-2.0"  # 遗留，不在 _CHANNEL_OPTIONS
_JIMENG_SEEDANCE_MODEL_FULL_9IMG = "seedance2.0-full-9img"
_JIMENG_SEEDANCE_MODEL_SORA_V3_PRO = "sora-v3-pro"
_JIMENG_SEEDANCE_MODEL_SORA_V3_FAST = "sora-v3-fast"
_JIMENG_SEEDANCE_MODEL_FAST_20 = "video-v1-15s"  # 旧 Fast 2.0 渠道模型，不再暴露

#: 渠道 → 模型（_ALL 渠道标签亦映射，含遗留渠道，便于归一化）
_CHANNEL_TO_MODEL = {
    _CHANNEL2_LABEL: _JIMENG_SEEDANCE_MODEL_G,
    _CHANNEL3_LABEL: _JIMENG_SEEDANCE_MODEL_FULL_9IMG,
    _CHANNEL4_LABEL: _JIMENG_SEEDANCE_MODEL_SORA_V3_PRO,
    _CHANNEL5_LABEL: _JIMENG_SEEDANCE_MODEL_SORA_V3_FAST,
    "渠道2": _JIMENG_SEEDANCE_MODEL_G,
    "渠道3": _JIMENG_SEEDANCE_MODEL_FULL_9IMG,
    "渠道4": _JIMENG_SEEDANCE_MODEL_SORA_V3_PRO,
    "渠道5": _JIMENG_SEEDANCE_MODEL_SORA_V3_FAST,
    _LEGACY_CHANNEL4_LABEL: _JIMENG_SEEDANCE_MODEL_FAST_20,
}

#: prompt 限长（spec §7.4 实锤：G=3500 / V=3999 / FAST_20=4096 / SORA_V3_FAST=4096）
_PROMPT_MAX_CHARS_G = 3500
_PROMPT_MAX_CHARS_V = 3999
_PROMPT_MAX_CHARS_FAST_20 = 4096
_PROMPT_MAX_CHARS_SORA_V3_FAST = 4096

#: 渠道 → prompt 限长（渠道2/3 归 LongXia 家族取 G 限；渠道4 取 FAST_20 限；渠道5 取 SORA_V3_FAST 限）
_CHANNEL_PROMPT_LIMITS = {
    _CHANNEL2_LABEL: _PROMPT_MAX_CHARS_G,
    _CHANNEL3_LABEL: _PROMPT_MAX_CHARS_G,
    _CHANNEL4_LABEL: _PROMPT_MAX_CHARS_FAST_20,
    _CHANNEL5_LABEL: _PROMPT_MAX_CHARS_SORA_V3_FAST,
    _LEGACY_CHANNEL4_LABEL: _PROMPT_MAX_CHARS_FAST_20,
}

#: 渠道2/3 尺寸映射 与 渠道4/5 尺寸映射（spec §7.4 配对实锤）
_SIZE_BY_RATIO = {"16:9": "1280x720", "9:16": "720x1280", "1:1": "720x720"}
_FAST_20_SIZE_BY_RATIO = {"16:9": "1920x1080", "9:16": "1080x1920", "1:1": "1080x1080"}
_SORA_V3_ASPECT_RATIOS = ["21:9", "1:1", "4:3", "3:4", "16:9", "9:16"]
_SORA_V3_FIXED_RESOLUTION = "720p"
_NARROW_RATIOS = ("16:9", "9:16", "1:1")

#: 参考素材上限（spec §7.4 实锤）
_MAX_REFERENCE_IMAGES = 9
_MAX_REFERENCE_IMAGES_CHANNEL5 = 4
_MAX_REFERENCE_IMAGE_BYTES = 31457280  # 30 MB
_MAX_REFERENCE_AUDIOS = 3
_MAX_REFERENCE_AUDIO_BYTES = 15728640  # 15 MB
_MAX_REFERENCE_AUDIO_SECONDS = 15.0
_MIN_REFERENCE_AUDIO_SECONDS = 2.0

#: 参考图内联阈值：单张超 15MB 转图床 URL 提交（复刻重建，≤30MB 硬上限内）
_INLINE_TO_UPLOAD_IMAGE_BYTES = 15728640  # 15 MB

#: 图床上传 API 与内置 token（spec §7.4 实锤）
_TE_IMAGE_HOST_UPLOAD_URL = "http://teh.tetae.top:40061/api/index.php"
_TE_IMAGE_HOST_TOKEN = "1c17b11693cb5ec63859b091c5b9c1b2"

#: 轮询兜底上限（原版无 UI 超时输入，函数体不可见，复刻重建保守值）
_POLL_MAX_WAIT_S = 3600

#: 任务状态机（spec §3.4.5 字面量实锤）
_TERMINAL_SUCCESS_STATUS = frozenset({"succeeded", "completed", "success"})
_TERMINAL_FAILED_STATUS = frozenset({"failed", "failure"})
_CANCELLED_STATUS = frozenset({"cancelled", "canceled", "expired"})
_IN_PROGRESS_STATUS = frozenset({"progress", "ready", "finished"})

_MSG_EMPTY_PROMPT = "请输入 prompt"
_MSG_NO_KEY = "请在 config.ini 中配置 API Key 或在节点中填写"
_MSG_NO_URL = "请在 config.ini 中配置 API URL 或在节点中填写"
_MSG_INVALID_URL = "未配置有效的 API URL"
_MSG_INVALID_TASK_ID = "未提供有效的任务 ID"

_BASE64ISH_RE = re.compile(r"[A-Za-z0-9+/=]{512,}")
_URL_CANDIDATE_RE = re.compile(r"https?://[^\s\"'<>\\]+")


# ==================== 会话 / 中断 / 鉴权 ====================

def _ensure_not_interrupted():
    """配合 comfy.model_management 响应 ComfyUI 中断（spec §2）。"""
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001  非 ComfyUI 环境
        return
    throw = (
        getattr(model_management, "throw_exception_if_processing_interrupted", None)
        or getattr(model_management, "throw_exception_if_interrupted", None)
    )
    if callable(throw):
        throw()
        return
    ensure = getattr(model_management, "ensure_not_interrupted", None)
    if callable(ensure):
        ensure()


def _build_session(bypass_proxy):
    """自建 requests.Session 直连（本模块不复用 api_client）；绕代理时 trust_env=False。"""
    import requests  # 惰性导入

    session = requests.Session()
    if bypass_proxy:
        session.trust_env = False
        session.proxies = {}
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _masked_key(api_key):
    """日志打码：保留首尾 4 位。"""
    key = str(api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 8 + key[-4:]


# ==================== URL 解析器（spec §2 符号名） ====================

def _strip_base_url(api_base_url):
    """归一 base URL；空报「请在 config.ini 中配置 API URL…」，无 scheme 报「未配置有效的 API URL」。"""
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError(_MSG_NO_URL)
    if not base.startswith(("http://", "https://")):
        raise ValueError(_MSG_INVALID_URL)
    return base


def _resolve_jimeng_submit_url(api_base_url):
    """渠道2/3 提交端点：`{base}/v1/videos`（模块 docstring 实锤）。"""
    base = _strip_base_url(api_base_url)
    if base.endswith("/v1/videos"):
        return base
    if base.endswith("/v1"):
        return base + "/videos"
    return base + "/v1/videos"


def _resolve_jimeng_fetch_url(task_id, api_base_url):
    """渠道2/3 轮询端点：`GET /v1/videos/{task_id}`（docstring 实锤）。"""
    if not str(task_id or "").strip():
        raise ValueError(_MSG_INVALID_TASK_ID)
    return _resolve_jimeng_submit_url(api_base_url) + "/" + str(task_id).strip()


def _resolve_fast_20_submit_url(api_base_url):
    """渠道4/5（sora-v3）提交端点（spec §7.5：精确路径未确认，按 docstring /v1/videos 复刻）。"""
    return _resolve_jimeng_submit_url(api_base_url)


def _resolve_fast_20_fetch_url(task_id, api_base_url):
    """渠道4/5（sora-v3）轮询端点（同上按 docstring 复刻）。"""
    return _resolve_jimeng_fetch_url(task_id, api_base_url)


# ==================== 归一化（spec §2 符号名） ====================

def _clamp_int(value, minimum, maximum, default):
    """整型限幅，解析失败取 default。"""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, result))


def _normalize_duration_value(duration):
    """时长归一（UI 仅暴露 "15" 单枚举）。"""
    try:
        return int(str(duration).strip())
    except (TypeError, ValueError):
        return 15


def _normalize_ratio(aspect_ratio):
    """窄集比例归一（渠道2/3 仅使用 16:9 / 9:16 / 1:1，其余回退 16:9）。"""
    ratio = str(aspect_ratio or "").strip()
    if ratio in _NARROW_RATIOS:
        return ratio
    logger.warning("当前渠道仅支持 16:9 / 9:16 / 1:1 比例，%s 已回退为 16:9" % (ratio or "空值"))
    return "16:9"


def _normalize_sora_v3_ratio(aspect_ratio):
    """渠道4/5 全比例归一（_SORA_V3_ASPECT_RATIOS），未知值回退 16:9。"""
    ratio = str(aspect_ratio or "").strip()
    if ratio in _SORA_V3_ASPECT_RATIOS:
        return ratio
    logger.warning("不支持的比例 %s，已回退为 16:9" % (ratio or "空值"))
    return "16:9"


def _resolve_longxia_size(ratio):
    """渠道2/3：比例 → 尺寸（_SIZE_BY_RATIO）。"""
    return _SIZE_BY_RATIO.get(str(ratio or "").strip()) or "1280x720"


def _resolve_fast_20_size(ratio):
    """渠道4/5：比例 → 尺寸（_FAST_20_SIZE_BY_RATIO）。"""
    return _FAST_20_SIZE_BY_RATIO.get(str(ratio or "").strip()) or "1920x1080"


# ==================== 协议解析（spec §2 符号名） ====================

def _summarize_payload_for_log(payload, max_chars=800):
    """payload 摘要：base64/data URI 以 <base64 len=…>/<data_uri len=…> 截断占位。"""
    def _summarize_node(node):
        if isinstance(node, dict):
            return {str(key): _summarize_node(value) for key, value in node.items()}
        if isinstance(node, (list, tuple)):
            return [_summarize_node(item) for item in node]
        if isinstance(node, str):
            if node.startswith("data:") and ";base64," in node:
                return "<data_uri len=%d>" % len(node)
            if len(node) >= 512 and _BASE64ISH_RE.fullmatch(node):
                return "<base64 len=%d>" % len(node)
            return node
        return node

    try:
        text = json.dumps(_summarize_node(payload), ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = str(payload)
    if len(text) > max_chars:
        text = text[:max_chars] + "... <truncated>"
    return text


def _read_json_response_or_raise(resp, label):
    """HTTP 检查 + JSON 解析；失败按 `label: HTTP …/返回的不是 JSON` 报错。"""
    status_code = getattr(resp, "status_code", 0)
    if status_code >= 400:
        body_text = str(getattr(resp, "text", "") or "")[:300]
        raise RuntimeError(
            "%s: HTTP %s, Body: %s" % (label, status_code, body_text or "<empty body>")
        )
    content_type = ""
    headers = getattr(resp, "headers", None)
    if headers:
        content_type = str(headers.get("Content-Type", "") or "")
    try:
        return resp.json()
    except Exception as exc:  # noqa: BLE001  JSONDecodeError / RequestsJSONDecodeError
        body_text = str(getattr(resp, "text", "") or "")[:300]
        raise RuntimeError(
            "%s: 返回的不是 JSON（HTTP %s, Content-Type: %s, Body: %s）"
            % (label, status_code, content_type, body_text or "<empty body>")
        ) from exc


def _iter_task_nodes(payload):
    """任务 JSON 的候选节点：顶层 + data 内嵌层。"""
    if isinstance(payload, dict):
        yield payload
        data = payload.get("data")
        if isinstance(data, dict):
            yield data


def _extract_task_id(payload):
    """从任务 JSON 抽 taskId / task_id / id（spec §3.4.5 字段别名）。"""
    for node in _iter_task_nodes(payload):
        for key in ("taskId", "task_id", "id"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _extract_task_status(payload):
    """从任务 JSON 抽 status（含 taskStatus 别名）。"""
    for node in _iter_task_nodes(payload):
        for key in ("status", "taskStatus"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _extract_failure_reason(payload):
    """从任务 JSON 抽失败原因（fail_reason / error / message）。"""
    for node in _iter_task_nodes(payload):
        for key in ("fail_reason", "failReason", "fail_msg", "error", "message"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _pick_video_url_node(node):
    """递归在响应结构中抽取视频 URL（命名键优先）。"""
    if isinstance(node, dict):
        for key in (
            "videoUrl", "video_url", "download_url", "direct_url", "result_url", "url",
        ):
            value = node.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://", "data:")):
                if key != "url" or re.search(r"\.(mp4|webm|mov|mkv)(\?|#|$)", value, re.IGNORECASE):
                    return value
        for value in node.values():
            found = _pick_video_url_node(value)
            if found:
                return found
    elif isinstance(node, str):
        if node.startswith(("http://", "https://")) and re.search(
            r"\.(mp4|webm|mov|mkv)(\?|#|$)", node, re.IGNORECASE
        ):
            return node
    elif isinstance(node, (list, tuple)):
        for item in node:
            found = _pick_video_url_node(item)
            if found:
                return found
    return ""


def _extract_jimeng_video_url(payload):
    """从任务 JSON 抽视频 URL（videoUrl/video_url/download_url/direct_url/result_url/videos）。"""
    return _pick_video_url_node(payload)


def _extract_uploaded_file_url(payload):
    """从图床响应抽文件 URL：结构化键优先，文本正则兜底（/content、uploads、files 片段）。"""
    if isinstance(payload, dict):
        for key in ("url", "src", "link", "path", "u"):
            value = payload.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
        data = payload.get("data")
        if isinstance(data, dict):
            found = _extract_uploaded_file_url(data)
            if found:
                return found
        for value in payload.values():
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                return value
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, default=str)
    urls = _URL_CANDIDATE_RE.findall(text)
    for url in urls:
        if any(fragment in url for fragment in ("/content", "uploads", "files")):
            return url
    return urls[0] if urls else ""


# ==================== 图床上传（spec §3.4 第 3 条） ====================

def _upload_file_to_te_image_host(session, file_tuple):
    """上传文件到 TE 图床，返回可访问 URL（内置 token 换 URL）。"""
    filename, mime_type, data = file_tuple
    logger.info("图床上传 API: %s" % _TE_IMAGE_HOST_UPLOAD_URL)
    try:
        resp = session.post(
            _TE_IMAGE_HOST_UPLOAD_URL,
            data={"token": _TE_IMAGE_HOST_TOKEN},
            files={
                "file": (
                    filename or "file.bin",
                    data,
                    mime_type or "application/octet-stream",
                )
            },
            timeout=(15, 120),
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("图床上传失败: %s" % exc) from exc
    try:
        payload = resp.json()
    except Exception:  # noqa: BLE001
        payload = str(getattr(resp, "text", "") or "")
    url = _extract_uploaded_file_url(payload)
    if not url:
        raise RuntimeError("图床上传成功，但未解析到 url")
    logger.info("图床上传成功 (%.1f MB) -> 图床 URL" % (len(data) / 1048576.0))
    return url


# ==================== 素材编码（spec §2 媒体符号名） ====================

def _image_tensor_to_file_tuples(image_tensor, start_index):
    """IMAGE 端口 tensor → [(filename, mime_type, bytes), ...]（每帧一个部件）。"""
    if image_tensor is None:
        return []
    ndim = getattr(image_tensor, "ndim", None)
    if ndim not in (3, 4):
        raise ValueError("不支持的 IMAGE 维度: %s" % ndim)
    try:
        frames = IMAGE_CODEC.extract_numpy_images(image_tensor)
    except ImportError as exc:  # noqa: BLE001  缺 numpy/torch
        raise RuntimeError("缺少图像依赖（numpy/torch）: %s" % exc) from exc
    parts = []
    for offset, frame in enumerate(frames):
        _field, filename, mime_type, data = encode_numpy_image_to_api_file_part(
            frame,
            field_name="image",
            filename_prefix="reference_%d" % (start_index + offset),
        )
        parts.append((filename, mime_type, data))
    return parts


def _audio_input_to_wav_bytes(audio_input):
    """AUDIO 输入（{waveform, sample_rate}）→ (WAV bytes, 时长秒)。"""
    if not isinstance(audio_input, dict):
        raise ValueError("未提供有效的 AUDIO 输入")
    waveform = audio_input.get("waveform")
    sample_rate = audio_input.get("sample_rate")
    if waveform is None:
        raise ValueError("未提供有效的 AUDIO 输入")
    if sample_rate is None:
        raise ValueError("AUDIO 输入缺少有效的 sample_rate")
    try:
        import numpy as np  # 惰性导入
        import torch  # 惰性导入
    except ImportError as exc:  # noqa: BLE001  缺 numpy/torch
        raise RuntimeError("缺少音频依赖（numpy/torch）: %s" % exc) from exc
    try:
        if isinstance(waveform, torch.Tensor):
            tensor = waveform.detach()
        else:
            tensor = torch.as_tensor(waveform)
        if tensor.ndim == 2:
            tensor = tensor.unsqueeze(0)
        if tensor.ndim != 3:
            raise ValueError("不支持的 AUDIO 维度: %s" % tensor.ndim)
        tensor = tensor[0]  # 取第一批
        if tensor.ndim == 1:
            tensor = tensor.unsqueeze(0)
        channels = int(tensor.shape[0])
        audio_np = tensor.to(torch.float32).cpu().numpy()
    except ImportError as exc:  # noqa: BLE001  缺 numpy/torch
        raise RuntimeError("缺少音频依赖（numpy/torch）: %s" % exc) from exc
    # [C, N] → [N, C]（transpose），float 波形 → int16 PCM（tobytes）
    samples = np.ascontiguousarray(audio_np.T)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0
    scale = 32767.0 / peak if peak > 1.0 + 1e-6 else 32767.0
    pcm = np.clip(samples * scale, -32768.0, 32767.0).astype(np.int16)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)
        wav_file.setframerate(int(sample_rate))
        wav_file.writeframes(pcm.tobytes())
    frame_count = int(samples.shape[0])
    duration = frame_count / float(sample_rate) if sample_rate else 0.0
    return buffer.getvalue(), duration


def _get_wav_duration_seconds(file_bytes):
    """WAV 字节 → 时长秒（wave.getnframes / getframerate）。"""
    with wave.open(io.BytesIO(file_bytes), "rb") as wav_file:
        framerate = wav_file.getframerate() or 1
        return wav_file.getnframes() / float(framerate)


def _file_tuple_to_b64_material(file_tuple, fallback_filename="file"):
    """(filename, mime, bytes) → base64 字符串（b64_json 素材）。"""
    filename, _mime_type, data = file_tuple
    if not data:
        raise ValueError("%s 为空，无法编码为 b64_json" % (filename or fallback_filename))
    return base64.b64encode(data).decode("ascii")


def _file_tuple_to_data_uri(file_tuple, fallback_mime="image/png"):
    """(filename, mime, bytes) → `data:;base64,…`（原版使用空 MIME 前缀，spec §3.4）。"""
    filename, _mime_type, data = file_tuple
    if not data:
        raise ValueError("%s 为空，无法编码为 data URI" % (filename or "image"))
    return "data:;base64,%s" % base64.b64encode(data).decode("ascii")


# ==================== 输出 / VIDEO 包装 ====================

def _get_output_dir():
    """ComfyUI output 目录（folder_paths），纯 Python 环境回退 ./output。"""
    try:
        import folder_paths  # 仅 ComfyUI 环境存在

        return folder_paths.get_output_directory()
    except Exception:  # noqa: BLE001
        return os.path.join(os.getcwd(), "output")


def _make_video_from_file(path):
    """VideoFromFile 包装（comfy_api.latest 惰性导入，_HAS_COMFY_VIDEO 为 False 时报环境不支持）。"""
    if not _HAS_COMFY_VIDEO:
        raise RuntimeError("当前 ComfyUI 环境缺少 comfy_api 视频支持，无法返回 VIDEO 输出")
    last_error = None
    for module_path in ("comfy_api.input_impl", "comfy_api.latest.input_impl"):
        try:
            module = __import__(module_path, fromlist=["VideoFromFile"])
            return module.VideoFromFile(path)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError("Invalid video file: %s (%s)" % (os.path.basename(path), last_error))


def _download_video(session, video_url, api_key, timeout_s=600):
    """流式分块下载到 ComfyUI/output，jimeng_video_ 前缀命名。"""
    _ensure_not_interrupted()
    headers = {"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"}
    if api_key:
        headers["Authorization"] = "Bearer %s" % api_key
    logger.info("开始下载视频到 ComfyUI/output ...")
    output_dir = _get_output_dir()
    os.makedirs(output_dir, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, "%s%s.mp4" % (_OUTPUT_FILE_PREFIX, stamp))
    counter = 1
    while os.path.exists(path):
        path = os.path.join(output_dir, "%s%s_%d.mp4" % (_OUTPUT_FILE_PREFIX, stamp, counter))
        counter += 1
    total = 0
    progress_bar = None
    chunk_size = 256 * 1024
    try:
        with session.get(video_url, headers=headers, stream=True, timeout=(15, timeout_s)) as resp:
            status_code = getattr(resp, "status_code", 0)
            if status_code >= 400:
                raise RuntimeError("下载视频失败: HTTP %s" % status_code)
            total_bytes = int((getattr(resp, "headers", {}) or {}).get("Content-Length") or 0)
            if total_bytes > 0:
                try:
                    from comfy.utils import ProgressBar  # 惰性导入

                    progress_bar = ProgressBar(max(1, int(total_bytes / chunk_size)))
                except Exception:  # noqa: BLE001  非 ComfyUI 环境
                    progress_bar = None
            with open(path, "wb") as handle:
                for chunk in resp.iter_content(chunk_size=chunk_size):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    total += len(chunk)
                    if progress_bar is not None:
                        progress_bar.update(1)
                    _ensure_not_interrupted()
    except RuntimeError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("下载视频失败: %s" % exc) from exc
    if total <= 0:
        raise RuntimeError("下载视频失败: 返回内容为空")
    logger.info("视频已保存: %s（大小: %d KB）" % (path, total // 1024))
    return path


class BananaJimengVideoNode:
    """TE MAN JM Video 2

    注册名: TE_image_pro_jimeng_video_2
    规格:   spec/Jimeng_Video_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Jimeng'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'task_id', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '@image1 是主体，镜头缓慢推进，保持主体一致，电影感光影，自然运动。', 'tooltip': '用于生成视频的提示词；渠道2用 @image1/@audio1，渠道3用 @图1/@audio1，渠道4支持最多 3 路参考音频，渠道5不支持音频。'}), 'duration': (('15',), {'default': '15', 'tooltip': '视频时长固定 15 秒'}), 'aspect_ratio': (('21:9', '1:1', '4:3', '3:4', '16:9', '9:16'), {'default': '16:9', 'tooltip': '视频比例；渠道4/渠道5支持全部比例，其他渠道仅使用 16:9 / 9:16 / 1:1。'})}, 'optional': {'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': 'https://tem.588186.xyz', 'multiline': False, 'tooltip': '服务地址（不要带 /v1/videos）'}), 'image': ('IMAGE', {'tooltip': '第一张参考图，提交为 reference_images[0]，提示词中用 [img1] 引用'}), 'image_2': ('IMAGE', {'tooltip': '第二张参考图（可选）'}), 'image_3': ('IMAGE', {'tooltip': '第三张参考图（可选）'}), 'image_4': ('IMAGE', {'tooltip': '第四张参考图（可选）'}), 'image_5': ('IMAGE', {'tooltip': '第五张参考图（可选）'}), 'image_6': ('IMAGE', {'tooltip': '第六张参考图（可选）'}), 'image_7': ('IMAGE', {'tooltip': '第七张参考图（可选）'}), 'image_8': ('IMAGE', {'tooltip': '第八张参考图（可选）'}), 'image_9': ('IMAGE', {'tooltip': '第九张参考图（可选）'}), 'audio': ('AUDIO', {'tooltip': '参考音频（可选），提交为 reference_audios[0]，提示词中用 [audio1] 引用'}), 'audio_2': ('AUDIO', {'tooltip': '第二个参考音频（可选），提交为 reference_audios[1]，提示词中用 [audio2] 引用'}), 'audio_3': ('AUDIO', {'tooltip': '第三个参考音频（可选），提交为 reference_audios[2]，提示词中用 [audio3] 引用'}), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 2147483647, 'tooltip': '保留参数；新接口不写入请求体'}), 'poll_interval_s': ('INT', {'default': 5, 'min': 2, 'max': 60, 'tooltip': '轮询间隔（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '渠道选择': (('渠道2(2.0)', '渠道3(2.0)', '渠道4(2.0)', '渠道5(2.0fast)'), {'default': '渠道2(2.0)', 'tooltip': '渠道2(2.0)：LongXia-G-Seedance-2.0；渠道3(2.0)：seedance2.0-full-9img；渠道4(2.0)：sora-v3-pro；渠道5(2.0fast)：sora-v3-fast。'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 配置解析（spec §3.4 步骤 1） ====================

    def _resolve_key_and_url(self, api_key, api_base_url):
        """key/URL 缺省 → config.ini（[gemini] api_key / get_effective_api_base_url）。"""
        key = str(api_key or "").strip() or (CONFIG_MANAGER.load_api_key() or "")
        if not key:
            raise ValueError(_MSG_NO_KEY)
        url = str(api_base_url or "").strip() or CONFIG_MANAGER.get_effective_api_base_url("")
        if not url:
            raise ValueError(_MSG_NO_URL)
        logger.info("API Key: %s" % _masked_key(key))
        logger.info("API URL: [已脱敏]")
        return key, url

    # ==================== 轮询（spec §3.4 步骤 5） ====================

    def _poll_task_video(self, session, api_key, base_url, task_id, poll_interval_s,
                         is_sora_v3_channel):
        """sleep 轮询 GET /v1/videos/{task_id}，状态机按 spec §3.4.5。"""
        if not str(task_id or "").strip():
            raise ValueError(_MSG_INVALID_TASK_ID)
        if is_sora_v3_channel:
            fetch_url = _resolve_fast_20_fetch_url(task_id, base_url)
        else:
            fetch_url = _resolve_jimeng_fetch_url(task_id, base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        started = time.monotonic()
        attempt = 0
        last_status_data = {}
        while True:
            _ensure_not_interrupted()
            time.sleep(poll_interval_s)
            attempt += 1
            try:
                resp = session.get(fetch_url, headers=headers, timeout=(15, 60))
            except Exception as exc:  # noqa: BLE001  网络抖动继续轮询
                logger.warning("查询任务暂时失败: %s" % exc)
                continue
            if getattr(resp, "status_code", 0) >= 400:
                logger.warning("查询任务暂时失败: HTTP %s" % getattr(resp, "status_code", 0))
                if time.monotonic() - started > _POLL_MAX_WAIT_S:
                    raise RuntimeError(
                        "视频生成轮询超时（%d 秒），任务 ID: %s"
                        % (int(time.monotonic() - started), task_id)
                    )
                continue
            body = _read_json_response_or_raise(resp, "查询任务失败")
            if not isinstance(body, dict):
                raise RuntimeError("返回 JSON 结构异常：%s" % _summarize_payload_for_log(body))
            last_status_data = body
            status_raw = _extract_task_status(body)
            status = str(status_raw or "").strip().lower()
            if attempt % 10 == 1:
                logger.info("任务状态: %s（第 %d 次轮询）" % (status or "unknown", attempt))
            if status in _TERMINAL_SUCCESS_STATUS:
                video_url = _extract_jimeng_video_url(body)
                if not video_url:
                    raise RuntimeError("任务完成，但未解析到视频 URL")
                logger.info("视频生成完成，已获取下载地址")
                return video_url, body
            fail_reason = _extract_failure_reason(body)
            if status in _TERMINAL_FAILED_STATUS or status in _CANCELLED_STATUS:
                raise RuntimeError("视频生成失败: %s" % (fail_reason or status or "未知原因"))
            if fail_reason and not status:
                raise RuntimeError("视频生成失败: %s" % fail_reason)
            if time.monotonic() - started > _POLL_MAX_WAIT_S:
                raise RuntimeError(
                    "视频生成轮询超时（%d 秒），任务 ID: %s"
                    % (int(time.monotonic() - started), task_id)
                )

    # ==================== FUNCTION ====================

    def generate_video(self, **kwargs):
        """TE_image_pro_jimeng_video_2：四渠道提交 → 轮询 → 下载 → VIDEO 包装。"""
        _ensure_not_interrupted()
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(_MSG_EMPTY_PROMPT)
        channel_label = str(kwargs.get("渠道选择") or _CHANNEL2_LABEL).strip()
        model_name = _CHANNEL_TO_MODEL.get(channel_label)
        if model_name is None:
            raise ValueError("不支持的渠道选择: %s" % channel_label)
        is_channel5 = channel_label == _CHANNEL5_LABEL
        is_sora_v3_channel = channel_label in (_CHANNEL4_LABEL, _CHANNEL5_LABEL)
        max_prompt_chars = _CHANNEL_PROMPT_LIMITS.get(channel_label, _PROMPT_MAX_CHARS_G)
        if len(prompt) > max_prompt_chars:
            raise ValueError("prompt 最多 %d 个字符，当前 %d" % (max_prompt_chars, len(prompt)))
        duration_value = _normalize_duration_value(kwargs.get("duration"))
        poll_interval_s = _clamp_int(kwargs.get("poll_interval_s"), 2, 60, 5)
        bypass_proxy = bool(kwargs.get("绕过代理"))
        # seed：保留参数；新接口不写入请求体

        api_key, base_url = self._resolve_key_and_url(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        logger.info("渠道选择: %s（model: %s）" % (channel_label, model_name))
        session = _build_session(bypass_proxy)

        # ---- 比例与尺寸（spec §3.5） ----
        aspect_ratio = str(kwargs.get("aspect_ratio") or "16:9").strip()
        if is_sora_v3_channel:
            ratio = _normalize_sora_v3_ratio(aspect_ratio)
            size_value = _resolve_fast_20_size(ratio)
        else:
            ratio = _normalize_ratio(aspect_ratio)
            size_value = _resolve_longxia_size(ratio)
        logger.info("比例: %s，尺寸: %s" % (ratio, size_value))

        # ---- 参考图（9 口 IMAGE，spec §3.2） ----
        image_tensors = [
            kwargs.get(name)
            for name in ("image", "image_2", "image_3", "image_4", "image_5",
                         "image_6", "image_7", "image_8", "image_9")
            if kwargs.get(name) is not None
        ]
        max_images = _MAX_REFERENCE_IMAGES_CHANNEL5 if is_channel5 else _MAX_REFERENCE_IMAGES
        image_files = []
        for tensor in image_tensors:
            parts = _image_tensor_to_file_tuples(tensor, start_index=len(image_files))
            if len(image_files) + len(parts) > max_images:
                raise ValueError("%s 最多只能连接 %d 张参考图" % (channel_label, max_images))
            image_files.extend(parts)
        if image_files:
            logger.info("参考图: %d 张" % len(image_files))

        # ---- 参考音频（3 口 AUDIO，重打包 WAV + 时长校验，spec §3.4 步骤 2） ----
        audio_inputs = [
            kwargs.get(name)
            for name in ("audio", "audio_2", "audio_3")
            if kwargs.get(name) is not None
        ]
        if audio_inputs and is_channel5:
            raise ValueError("%s 不支持参考音频，请断开 audio 输入" % channel_label)
        if len(audio_inputs) > _MAX_REFERENCE_AUDIOS:
            raise ValueError(
                "%s 最多只能连接 %d 路参考音频" % (channel_label, _MAX_REFERENCE_AUDIOS)
            )
        audio_files = []
        total_audio_seconds = 0.0
        for index, audio_input in enumerate(audio_inputs):
            wav_bytes, duration = _audio_input_to_wav_bytes(audio_input)
            if duration < _MIN_REFERENCE_AUDIO_SECONDS or duration > _MAX_REFERENCE_AUDIO_SECONDS:
                raise ValueError(
                    "参考音频 %d 时长 %.1f 秒，无法确认音频时长，当前节点要求单个音频 2-15 秒"
                    % (index + 1, duration)
                )
            if len(wav_bytes) > _MAX_REFERENCE_AUDIO_BYTES:
                raise ValueError("参考音频 %d 超过 15MB" % (index + 1))
            audio_files.append(("reference_audio_%d.wav" % (index + 1), "audio/wav", wav_bytes))
            total_audio_seconds += duration
        if audio_files:
            logger.info("参考音频累计时长: %.1f 秒" % total_audio_seconds)
            if total_audio_seconds > _MAX_REFERENCE_AUDIO_SECONDS:
                raise ValueError(
                    "全部参考音频累计 %.1f 秒，不能超过 %.1f 秒"
                    % (total_audio_seconds, _MAX_REFERENCE_AUDIO_SECONDS)
                )

        # ---- 素材提交方式（spec §3.4 步骤 3，三种方式并存） ----
        payload = {
            "model": model_name,
            "prompt": prompt,
            "duration": duration_value,
            "aspect_ratio": ratio,
            "size": size_value,
        }
        if is_sora_v3_channel:
            payload["resolution"] = _SORA_V3_FIXED_RESOLUTION
        if image_files:
            over_limit = [part for part in image_files if len(part[2]) > _MAX_REFERENCE_IMAGE_BYTES]
            if over_limit:
                raise ValueError("参考图 %s 超过 30MB" % over_limit[0][0])
            oversized = [part for part in image_files if len(part[2]) > _INLINE_TO_UPLOAD_IMAGE_BYTES]
            if oversized:
                # 任一参考图超 15MB → 整组转图床 URL（内置 token 换 URL）
                logger.info("素材提交方式: 图床 URL")
                payload["image_urls"] = [
                    _upload_file_to_te_image_host(session, part) for part in image_files
                ]
            elif is_sora_v3_channel:
                logger.info("图片提交方式: data URI(JSON image_urls)")
                payload["image_urls"] = [_file_tuple_to_data_uri(part) for part in image_files]
            else:
                logger.info("素材提交方式: b64_json")
                payload["reference_images"] = [
                    _file_tuple_to_b64_material(part) for part in image_files
                ]
        if audio_files:
            logger.info("音频提交方式: b64_json(JSON reference_audios)")
            payload["reference_audios"] = [
                _file_tuple_to_b64_material(part) for part in audio_files
            ]

        # ---- 提交任务（spec §3.4 步骤 4） ----
        logger.info("提交视频任务 payload: %s" % _summarize_payload_for_log(payload))
        if is_sora_v3_channel:
            submit_url = _resolve_fast_20_submit_url(base_url)
        else:
            submit_url = _resolve_jimeng_submit_url(base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        try:
            resp = session.post(
                submit_url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                timeout=(15, 300),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("提交任务失败: %s" % exc) from exc
        submit_body = _read_json_response_or_raise(resp, "提交任务失败")
        if not isinstance(submit_body, dict):
            raise RuntimeError("返回 JSON 结构异常：%s" % _summarize_payload_for_log(submit_body))
        task_id = _extract_task_id(submit_body)
        if not task_id:
            raise RuntimeError("接口未返回 task_id：%s" % _summarize_payload_for_log(submit_body))
        logger.info("任务 ID: %s" % task_id)

        # ---- 轮询 → 下载（spec §3.4 步骤 5/6） ----
        video_url, last_status_data = self._poll_task_video(
            session, api_key, base_url, task_id, poll_interval_s, is_sora_v3_channel
        )
        video_path = _download_video(session, video_url, api_key)
        video = _make_video_from_file(video_path)
        response_text = _summarize_payload_for_log(last_status_data, max_chars=1200)
        return (video, video_url, task_id, response_text)

NODE_CLASS_MAPPINGS = {'TE_image_pro_jimeng_video_2': BananaJimengVideoNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_jimeng_video_2': 'TE MAN JM Video 2'}
