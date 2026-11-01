# -*- coding: utf-8 -*-
"""te_man_open · TE_HappyH_Video

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

te_man_open 纯 Python 复刻（spec/TE_HappyH_Video.md 含动态回填节）：
- HappyHorse（快乐马）视频节点，固定模型 happyhorse-video，
  分辨率档位 _FIXED_RESOLUTION_NAME="720P" 内部固定（非 UI 输入）
- 模式 自动/文生视频/首帧生视频/多图参考（自动按图片数量分流：
  无图=文生视频，1图=首帧生视频，多图=多图参考）
- multipart/form-data 提交（参考图走 input_reference[] 字段）到 {base}/v1/videos
  → 轮询 GET /v1/videos/{task_id}（状态机 SUCCEEDED/COMPLETED/SUCCESS、
  FAILED/FAILURE/ERROR、其余 UNKNOWN 继续轮询）→ 流式下载 te_happyh_video_*.mp4
本节点自建 requests.Session 直连（不复用 api_client，spec §4.5 负证据），
含 trust_env 代理开关；requests/torch/numpy/comfy 系全部惰性导入。
"""

import json
import os
import re
import time
from urllib.parse import urljoin, urlparse

try:  # 包内相对导入；以文件方式直载时回退绝对导入
    from ..shared.config_manager import CONFIG_MANAGER
    from ..shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_file_part
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared.config_manager import CONFIG_MANAGER
    from te_man_open.shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_file_part
    from te_man_open.shared.logger import logger


# ==================== 模块常量（spec §7.1 动态回填实锤值） ====================

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
_OUTPUT_FILE_PREFIX = "te_happyh_video_"

#: 模式常量（spec §7.1 实锤）
_MODE_AUTO = "自动"
_MODE_T2V = "文生视频"
_MODE_I2V = "首帧生视频"
_MODE_R2V = "多图参考"
_MODE_OPTIONS = [_MODE_AUTO, _MODE_T2V, _MODE_I2V, _MODE_R2V]

#: 固定模型与分辨率档位（spec §7.1 实锤）
_FIXED_MODEL_NAME = "happyhorse-video"
_FIXED_RESOLUTION_NAME = "720P"
_MODE_TO_MODEL = {
    _MODE_T2V: "happyhorse-video",
    _MODE_I2V: "happyhorse-video",
    _MODE_R2V: "happyhorse-video",
}

#: 比例 9 档（spec §7.1 顺序实锤）
_RATIO_OPTIONS = ["16:9", "9:16", "1:1", "4:3", "3:4", "4:5", "5:4", "9:21", "21:9"]

#: 默认服务地址（spec §7.1 实锤：空串，无硬编码默认 URL，全靠 config.ini 或节点输入）
_DEFAULT_BASE_URL = ""

#: 参考图上限（多图参考 1-9 张）
_MAX_REFERENCE_IMAGES = 9

#: 任务状态机（spec §4.4 步骤 6 字面量实锤）
_TERMINAL_SUCCESS_STATUS = frozenset({"succeeded", "completed", "success"})
_TERMINAL_FAILED_STATUS = frozenset({"failed", "failure", "error"})

_MSG_EMPTY_PROMPT = "请输入 prompt"
_MSG_NO_KEY = "请在 config.ini 中配置 API Key 或在节点中填写"
_MSG_NO_URL = "请在 config.ini 中配置 API URL 或在节点中填写，例如 https://newapi.xxx.com"
_MSG_INVALID_URL = "未配置有效的 API URL"
_MSG_INVALID_TASK_ID = "未提供有效的任务 ID"

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
    """日志打码：保留首尾 4 位（sanitize_api_key / masked_key）。"""
    key = str(api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 8 + key[-4:]


# ==================== URL 解析（spec §2 符号名） ====================

def _strip_base_url(api_base_url):
    """归一 base URL；允许完整的 /v1/videos 地址（tooltip 原文）。"""
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError(_MSG_NO_URL)
    if not base.startswith(("http://", "https://")):
        raise ValueError(_MSG_INVALID_URL)
    return base


def _resolve_submit_url(api_base_url):
    """提交端点：`{base}/v1/videos`（模块 docstring 实锤）；容忍 base 已带 /v1 或完整端点。"""
    base = _strip_base_url(api_base_url)
    if base.endswith("/v1/videos"):
        return base
    if base.endswith("/v1"):
        return base + "/videos"
    return base + "/v1/videos"


def _resolve_task_url(task_id, api_base_url):
    """轮询端点：`GET /v1/videos/{task_id}`（docstring 实锤）。"""
    if not str(task_id or "").strip():
        raise ValueError(_MSG_INVALID_TASK_ID)
    base = _strip_base_url(api_base_url)
    if base.endswith("/v1/videos"):
        return base + "/" + str(task_id).strip()
    return _resolve_submit_url(base) + "/" + str(task_id).strip()


def _absolutize_url(raw_url, endpoint):
    """相对 URL → 绝对 URL（urljoin，基于任务端点主机；spec §2 符号）。"""
    value = str(raw_url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://", "data:")):
        return value
    try:
        parsed = urlparse(endpoint or "")
        if parsed.scheme and parsed.netloc:
            return urljoin("%s://%s" % (parsed.scheme, parsed.netloc), value)
    except Exception:  # noqa: BLE001
        pass
    return value


# ==================== 归一化（spec §2 符号名） ====================

def _clamp_int(value, minimum, maximum, default):
    """整型限幅，解析失败取 default。"""
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, result))


def _normalize_duration_value(duration):
    """时长 STRING（"3".."15"）→ int，缺省 5。"""
    try:
        result = int(str(duration).strip())
    except (TypeError, ValueError):
        return 5
    return max(3, min(15, result))


def _normalize_resolution_name(resolution):
    """分辨率档位归一（_FIXED_RESOLUTION_NAME="720P" 内部固定，spec §2 符号）。"""
    value = str(resolution or "").strip().upper()
    return value or _FIXED_RESOLUTION_NAME


def _ratio_to_size(ratio):
    """ratio → size（tooltip 原文：例如 16:9 -> 1280x720）。

    复刻重建：720p 短边基准、长边取偶；16:9 -> 1280x720 与 tooltip 实锤一致。
    """
    match = re.fullmatch(r"(\d+)\s*:\s*(\d+)", str(ratio or "").strip())
    if not match:
        return "1280x720"
    ratio_w, ratio_h = int(match.group(1)), int(match.group(2))
    if ratio_w <= 0 or ratio_h <= 0:
        return "1280x720"
    if ratio_w >= ratio_h:
        height = 720
        width = int(round(720.0 * ratio_w / ratio_h))
    else:
        width = 720
        height = int(round(720.0 * ratio_h / ratio_w))
    width += width % 2
    height += height % 2
    return "%dx%d" % (width, height)


# ==================== 协议解析（spec §2 符号名） ====================

def _summarize_for_log(payload, max_chars=600):
    """payload/响应摘要：base64/data URI 打码 + 截断。"""
    def _summarize_node(node):
        if isinstance(node, dict):
            return {str(key): _summarize_node(value) for key, value in node.items()}
        if isinstance(node, (list, tuple)):
            return [_summarize_node(item) for item in node]
        if isinstance(node, str):
            if node.startswith("data:") and ";base64," in node:
                return "<data_uri len=%d>" % len(node)
            if len(node) >= 512 and re.fullmatch(r"[A-Za-z0-9+/=]{512,}", node):
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
    """HTTP 检查 + JSON 解析（spec §5：返回的不是 JSON / HTTP N / Body / Content-Type）。"""
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
            "%s 返回的不是 JSON（HTTP %s, Content-Type: %s, Body: %s）"
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
    """从任务 JSON 抽 taskId（驼峰字段实锤，spec §4.4 步骤 4）。"""
    for node in _iter_task_nodes(payload):
        for key in ("taskId", "task_id", "id"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _extract_task_status(payload):
    """从任务 JSON 抽任务状态（taskStatus / status）。"""
    for node in _iter_task_nodes(payload):
        for key in ("taskStatus", "status"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _extract_failure_message(payload):
    """从任务 JSON 抽失败原因（message / error / fail_msg / fail_reason / code）。"""
    for node in _iter_task_nodes(payload):
        for key in ("message", "error", "fail_msg", "fail_reason", "failReason"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _pick_video_url_node(node):
    """递归在响应结构中抽取视频 URL（output/results/videos 容器 + 命名键）。"""
    if isinstance(node, dict):
        for key in ("video_url", "videoUrl", "download_url", "content_url", "url", "video"):
            value = node.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://", "data:")):
                if "video" in key.lower() or key == "content_url" or re.search(
                    r"\.(mp4|webm|mov|mkv)(\?|#|$)", value, re.IGNORECASE
                ):
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


def _extract_video_url(payload):
    """从任务 JSON 抽视频 URL（url / content_url / video_url 多候选键，spec §4.4 步骤 6）。"""
    return _pick_video_url_node(payload)


# ==================== 参考图编码（spec §4.4 步骤 2/3） ====================

def _append_reference_batches(target_list, image_tensor, start_index):
    """把一路 IMAGE 端口 batch 的各帧编码为 PNG 文件部件，顺序追加。"""
    if image_tensor is None:
        return
    ndim = getattr(image_tensor, "ndim", None)
    if ndim not in (3, 4):
        raise ValueError("不支持的 IMAGE 维度: %s" % ndim)
    try:
        frames = IMAGE_CODEC.extract_numpy_images(image_tensor)
    except ImportError as exc:  # noqa: BLE001  缺 numpy
        raise RuntimeError("缺少图像依赖（numpy）: %s" % exc) from exc
    for offset, frame in enumerate(frames):
        _field, filename, mime_type, data = encode_numpy_image_to_api_file_part(
            frame,
            field_name="input_reference[]",
            filename_prefix="reference_%d" % (start_index + offset),
        )
        target_list.append((filename, mime_type, data))


def _encode_image_batch_to_file_parts(image_tensors):
    """9 路 IMAGE 端口 → 合并参考图列表 [(filename, mime_type, bytes), ...]。"""
    merged_images = []
    for tensor in image_tensors:
        _append_reference_batches(merged_images, tensor, start_index=len(merged_images))
    return merged_images


def _summarize_items(items):
    """参考图列表摘要文本（文件名 + 大小）。"""
    return ", ".join("%s(%dKB)" % (name, len(data) // 1024) for name, _mime, data in items)


# ==================== 输出 / VIDEO 包装 ====================

def _get_output_dir():
    """ComfyUI output 目录（folder_paths.get_output_directory）。"""
    try:
        import folder_paths  # 仅 ComfyUI 环境存在

        return folder_paths.get_output_directory()
    except Exception:  # noqa: BLE001
        return os.path.join(os.getcwd(), "output")


def _make_video_from_file(path):
    """VideoFromFile 包装（comfy_api 惰性导入，_HAS_COMFY_VIDEO 为 False 时报环境不支持）。"""
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
    """流式分块下载到 ComfyUI/output，te_happyh_video_ 前缀命名。"""
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


class TEHappyHVideoSafePyNode:
    """TE MAN HappyH Video

    注册名: TE_image_pro_happyh_video
    规格:   spec/TE_HappyH_Video.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/HappyHorse'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'task_id', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一座由硬纸板和瓶盖搭建的微型城市，在夜晚焕发出生机。一列硬纸板火车缓缓驶过，小灯点缀其间，照亮前路。', 'tooltip': '用于生成视频的提示词。多图参考模式可用 [Image 1]、[Image 2] 指代图片。', 'defaultInput': True}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API 地址，例如 https://newapi.xxx.com 或完整的 /v1/videos 地址'}), 'mode': (('自动', '文生视频', '首帧生视频', '多图参考'), {'default': '自动', 'tooltip': '自动：无图=文生视频，1图=首帧生视频，多图=多图参考。'}), 'ratio': (('16:9', '9:16', '1:1', '4:3', '3:4', '4:5', '5:4', '9:21', '21:9'), {'default': '16:9', 'tooltip': '会转换成 size，例如 16:9 -> 1280x720'}), 'duration': (('3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15'), {'default': '5', 'tooltip': '视频时长（秒），范围 3-15'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 2147483647, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image_1': ('IMAGE', {'tooltip': '首帧/参考图 1'}), 'image_2': ('IMAGE', {'tooltip': '参考图 2'}), 'image_3': ('IMAGE', {'tooltip': '参考图 3'}), 'image_4': ('IMAGE', {'tooltip': '参考图 4'}), 'image_5': ('IMAGE', {'tooltip': '参考图 5'}), 'image_6': ('IMAGE', {'tooltip': '参考图 6'}), 'image_7': ('IMAGE', {'tooltip': '参考图 7'}), 'image_8': ('IMAGE', {'tooltip': '参考图 8'}), 'image_9': ('IMAGE', {'tooltip': '参考图 9'}), 'poll_interval_s': ('INT', {'default': 15, 'min': 5, 'max': 60, 'tooltip': '轮询间隔（秒），官方建议约 15 秒'}), 'timeout_s': ('INT', {'default': 900, 'min': 120, 'max': 3600, 'tooltip': '任务最长等待时间（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 配置解析（spec §4.4 步骤 1） ====================

    def _resolve_key_and_url(self, api_key, api_base_url):
        """key/URL 缺省 → config.ini（[gemini] api_key / api_base_url 明文或混淆值）。

        注意：HappyH 的 _DEFAULT_BASE_URL 为空串（spec §7.1 实锤），无内置默认站，
        仅读显式配置（api_base_url / api_base_url_enc），缺失时报
        「请在 config.ini 中配置 API URL 或在节点中填写，例如 …」。
        """
        key = str(api_key or "").strip() or (CONFIG_MANAGER.load_api_key() or "")
        if not key:
            raise ValueError(_MSG_NO_KEY)
        url = str(api_base_url or "").strip()
        if not url:
            # get_effective_api_base_url 会在配置缺失时回退内置默认站（teynex.com），
            # 与 HappyH 无默认站的行为不符，故此处只取显式配置层。
            url = CONFIG_MANAGER._get_configured_base_url() or ""
        if not url:
            raise ValueError(_MSG_NO_URL)
        logger.info("API Key: %s" % _masked_key(key))
        logger.info("API URL: [已脱敏]")
        return key, url

    # ==================== 模式解析（spec §4.1 _resolve_mode_and_model） ====================

    def _resolve_mode_and_model(self, mode, image_count):
        """模式归一 + 自动分流：无图=文生视频，1图=首帧生视频，多图=多图参考。"""
        mode_text = str(mode or "").strip()
        if mode_text == _MODE_AUTO:
            if image_count == 0:
                effective_mode = _MODE_T2V
            elif image_count == 1:
                effective_mode = _MODE_I2V
            else:
                effective_mode = _MODE_R2V
        elif mode_text in (_MODE_T2V, _MODE_I2V, _MODE_R2V):
            effective_mode = mode_text
        else:
            raise ValueError("不支持的模式: %s" % mode_text)
        model_name = _MODE_TO_MODEL.get(effective_mode) or _FIXED_MODEL_NAME
        return effective_mode, model_name

    # ==================== multipart 构建（spec §4.4 步骤 4） ====================

    def _build_multipart_parts(self, prompt_text, model_name, image_files, duration_value,
                               size_value, resolution_name):
        """组装 multipart 表单：字段 model/prompt/duration/resolution/size/watermark
        + files 字段 input_reference[]。"""
        data = {
            "model": model_name or _FIXED_MODEL_NAME,
            "prompt": prompt_text,
            "duration": str(duration_value),
            "resolution": resolution_name,
            "size": size_value,
            "watermark": "false",
        }
        files = [
            ("input_reference[]", (filename, data_bytes, mime_type or "image/png"))
            for filename, mime_type, data_bytes in image_files
        ]
        return data, files

    # ==================== 轮询（spec §4.4 步骤 5/6） ====================

    def _poll_task_video(self, session, api_key, base_url, task_id, poll_interval_s, timeout_s):
        """轮询 GET /v1/videos/{task_id}；SUCCEEDED/COMPLETED/SUCCESS 成功，
        FAILED/FAILURE/ERROR 失败，其余 UNKNOWN 继续轮询。"""
        if not str(task_id or "").strip():
            raise ValueError(_MSG_INVALID_TASK_ID)
        task_url = _resolve_task_url(task_id, base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        # 进度条按 elapsed 估算（comfy.utils.ProgressBar，非 ComfyUI 环境跳过）
        progress_bar = None
        try:
            from comfy.utils import ProgressBar  # 惰性导入

            total_ticks = max(1, int(timeout_s / max(1, poll_interval_s)))
            progress_bar = ProgressBar(total_ticks)
        except Exception:  # noqa: BLE001
            progress_bar = None
        started = time.monotonic()
        while True:
            _ensure_not_interrupted()
            time.sleep(poll_interval_s)
            if progress_bar is not None:
                progress_bar.update(1)
            try:
                resp = session.get(task_url, headers=headers, timeout=(15, 60))
            except Exception as exc:  # noqa: BLE001  网络抖动继续轮询
                logger.warning("查询任务暂时失败: %s" % exc)
                continue
            if getattr(resp, "status_code", 0) >= 400:
                logger.warning("查询任务暂时失败: HTTP %s" % getattr(resp, "status_code", 0))
                if time.monotonic() - started > timeout_s:
                    raise RuntimeError(
                        "HappyHorse 任务轮询超时（%d 秒）" % int(time.monotonic() - started)
                    )
                continue
            body = _read_json_response_or_raise(resp, "查询任务失败")
            status_raw = _extract_task_status(body)
            status = str(status_raw or "").strip().lower()
            logger.info("任务状态: %s" % (status.upper() or "UNKNOWN"))
            if status in _TERMINAL_SUCCESS_STATUS:
                video_url = _absolutize_url(_extract_video_url(body), task_url)
                if not video_url:
                    raise RuntimeError(
                        "任务成功但未返回 video_url：%s" % _summarize_for_log(body)
                    )
                return video_url, body
            if status in _TERMINAL_FAILED_STATUS:
                raise RuntimeError(
                    "视频生成失败: %s" % (_extract_failure_message(body) or status or "未知原因")
                )
            logger.info("继续轮询")
            if time.monotonic() - started > timeout_s:
                raise RuntimeError(
                    "HappyHorse 任务轮询超时（%d 秒）" % int(time.monotonic() - started)
                )

    # ==================== FUNCTION ====================

    def generate_video(self, **kwargs):
        """TE_image_pro_happyh_video：multipart 提交 → 轮询 → 下载 → VIDEO 包装。"""
        _ensure_not_interrupted()
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(_MSG_EMPTY_PROMPT)
        mode = str(kwargs.get("mode") or _MODE_AUTO).strip()
        ratio = str(kwargs.get("ratio") or "16:9").strip()
        duration_value = _normalize_duration_value(kwargs.get("duration"))
        poll_interval_s = _clamp_int(kwargs.get("poll_interval_s"), 5, 60, 15)
        timeout_s = _clamp_int(kwargs.get("timeout_s"), 120, 3600, 900)
        bypass_proxy = bool(kwargs.get("绕过代理"))
        # seed：仅供 ComfyUI 工作流使用；不会写入请求体

        api_key, base_url = self._resolve_key_and_url(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        session = _build_session(bypass_proxy)

        # ---- 合并参考图（spec §4.4 步骤 2/3） ----
        image_tensors = [
            kwargs.get(name)
            for name in ("image_1", "image_2", "image_3", "image_4", "image_5",
                         "image_6", "image_7", "image_8", "image_9")
            if kwargs.get(name) is not None
        ]
        try:
            image_files = _encode_image_batch_to_file_parts(image_tensors)
        except ValueError as exc:
            message = str(exc)
            if "无法从 tensor 中提取有效图像数据" in message:
                raise ValueError("不支持的参考图维度: %s" % message) from exc
            raise
        image_count = len(image_files)
        if image_files:
            logger.info("Input images: %d 张（multipart upload）: %s"
                        % (image_count, _summarize_items(image_files)))

        # ---- 模式解析与数量校验（spec §4.1/§4.4 步骤 1） ----
        effective_mode, model_name = self._resolve_mode_and_model(mode, image_count)
        if effective_mode == _MODE_T2V and image_count > 0:
            raise ValueError("文生视频模式不接收图片；如需传图请选择自动")
        if effective_mode == _MODE_I2V and image_count != 1:
            raise ValueError("首帧生视频模式必须且只能输入 1 张图片")
        if effective_mode == _MODE_R2V:
            if image_count == 0:
                raise ValueError("多图参考模式需要 1-9 张参考图")
            if image_count > _MAX_REFERENCE_IMAGES:
                raise ValueError(
                    "HappyHorse 多图参考最多支持 9 张图片，当前输入 %d 张" % image_count
                )

        # ---- 比例 → size（spec §4.2 tooltip） ----
        size_value = _ratio_to_size(ratio)
        resolution_name = _normalize_resolution_name(_FIXED_RESOLUTION_NAME)
        logger.info("Mode: %s" % effective_mode)
        logger.info("Model: %s" % model_name)
        logger.info("Resolution: %s" % size_value)
        logger.info("Resolution name: %s" % resolution_name)
        logger.info("Duration: %d" % duration_value)
        logger.info("Size: %s" % size_value)

        # ---- multipart 提交（spec §4.4 步骤 4） ----
        form_data, files = self._build_multipart_parts(
            prompt, model_name, image_files, duration_value, size_value, resolution_name
        )
        logger.info("payload_summary: %s" % _summarize_for_log(form_data))
        submit_url = _resolve_submit_url(base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        logger.info("Submit API: %s" % submit_url)
        try:
            resp = session.post(
                submit_url,
                data=form_data,
                files=files or None,
                headers=headers,
                timeout=(15, 300),
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("提交任务失败: %s" % exc) from exc
        submit_body = _read_json_response_or_raise(resp, "提交任务失败")
        task_id = _extract_task_id(submit_body)
        if not task_id:
            raise RuntimeError("接口未返回 task_id：%s" % _summarize_for_log(submit_body))
        logger.info("Task ID: %s（任务ID: %s）" % (task_id, task_id))

        # ---- 轮询 → 下载（spec §4.4 步骤 5-7） ----
        video_url, last_status_data = self._poll_task_video(
            session, api_key, base_url, task_id, poll_interval_s, timeout_s
        )
        video_path = _download_video(session, video_url, api_key, timeout_s)
        logger.info("视频生成完成: %s" % video_path)
        video = _make_video_from_file(video_path)
        response_text = _summarize_for_log(last_status_data, max_chars=1200)
        return (video, video_url, task_id, response_text)

NODE_CLASS_MAPPINGS = {'TE_image_pro_happyh_video': TEHappyHVideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_happyh_video': 'TE MAN HappyH Video'}
