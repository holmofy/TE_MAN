# -*- coding: utf-8 -*-
"""te_man_open · Grok_Video_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

te_man_open 纯 Python 复刻（spec/Grok_Video_Generator.md 含动态回填节）：
- 线路1：图片编码为 Base64 data URI，以 images 数组请求 /v1/videos JSON 接口
  （同步直返 video_url 或异步 task_id 轮询 → 下载 MP4；resolution 480p/720p）
- 线路2（默认）：图片编码为 Base64 data URI，以 image_url 字段请求
  /v1/chat/completions（model 固定 grok-imagine-video2，seconds 10/15，SSE 流解析）
本节点自建 requests.Session 直连（不复用 api_client，spec §4.1 负证据），
含 trust_env 代理开关与鉴权下载校验；requests/torch/comfy 系惰性导入。
"""

import json
import math
import os
import re
import time

try:  # 包内相对导入；以文件方式直载时回退绝对导入
    from ..shared.config_manager import CONFIG_MANAGER
    from ..shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_data_url
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared.config_manager import CONFIG_MANAGER
    from te_man_open.shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_data_url
    from te_man_open.shared.logger import logger


# ==================== 模块常量（spec §7.2 动态回填实锤值） ====================

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

#: 参考图总像素限幅（对齐 ComfyUI「Scale Image to Total Pixels」）
_MAX_INPUT_IMAGE_MEGAPIXELS = 1.0
_OFFICIAL_SCALE_METHOD = "nearest-exact"

#: 输出文件名前缀（配 .mp4）与 UA
_OUTPUT_FILE_PREFIX = "grok_video_"
_USER_AGENT = "ComfyUI-TE_API/1.0"

#: 视频任务状态机（字符串直接证据，spec 附录）
_VIDEO_DONE_STATUS = frozenset({"ready", "completed", "finished", "succeeded"})
_VIDEO_FAILED_STATUS = frozenset({"failed", "expired", "canceled", "cancelled"})

#: 视频 URL 抽取正则（spec 附录原文）
_URL_RE = re.compile(r"https?://[^\s\"'<>\\]+")
_VIDEO_EXT_RE = re.compile(r"\.(mp4|webm|mov|mkv)(\?|#|$)", re.IGNORECASE)
_VIDEO_TAG_SRC_RE = re.compile(r"<video[^>]*\bsrc=[\"']([^\"']+)[\"']", re.IGNORECASE)

_MSG_EMPTY_PROMPT = "请输入 prompt"
_MSG_NO_KEY = "请在 config.ini 中配置 API Key 或在节点中填写"
_MSG_NO_URL = "请在 config.ini 中配置 API URL 或在节点中填写"
_MSG_INVALID_URL = "未配置有效的 API URL"


# ==================== 会话 / 鉴权 / 代理 ====================

def _masked_key(api_key):
    """日志打码：保留首尾 4 位。"""
    key = str(api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 8 + key[-4:]


def _ensure_not_interrupted():
    """统一的中断检查，复用 ComfyUI 原生取消机制。"""
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


def _log_proxy_policy(bypass_proxy, has_key):
    """代理/鉴权判级日志（直连/系统代理 × 无鉴权/鉴权，spec §4.1）。"""
    mode = "直连" if bypass_proxy else "系统代理"
    auth = "鉴权" if has_key else "无鉴权"
    logger.info("网络策略: %s%s" % (mode, auth))


# ==================== URL / payload 构建 ====================

def _strip_base_url(api_base_url):
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError(_MSG_INVALID_URL)
    return base


def _resolve_videos_url(api_base_url):
    """拼 `{base}/v1/videos`；用户误带 /v1/videos 时按 spec 文案报错。"""
    base = _strip_base_url(api_base_url)
    if "/v1/videos" in base:
        raise ValueError("服务地址不要带 /v1/videos）")
    if base.endswith("/v1"):
        return base + "/videos"
    return base + "/v1/videos"


def _resolve_chat_completions_url(api_base_url):
    """拼 `{base}/v1/chat/completions`。"""
    base = _strip_base_url(api_base_url)
    if "/chat/completions" in base:
        return base
    if base.endswith("/v1"):
        return base + "/chat/completions"
    return base + "/v1/chat/completions"


def _video_config_payload(seconds, size, resolution_name, preset, include_line1_fields=True):
    """组装分辨率/时长配置字段。

    线路1通过 resolution 字段提交分辨率（另提交 size/preset）；
    线路2不提交 resolution/preset/size（spec §7.1 tooltip 原文）。
    """
    payload = {}
    try:
        payload["seconds"] = int(str(seconds))
    except (TypeError, ValueError):
        payload["seconds"] = 10
    if include_line1_fields:
        payload["size"] = str(size)
        payload["resolution"] = str(resolution_name)
        payload["preset"] = str(preset)
    return payload


def _line1_ratio_from_size(size):
    """线路1：由 `1792x1024` 等 size 字符串反推 aspect_ratio。

    仅接受约分后命中 16:9 / 9:16 / 1:1 / 2:3 / 3:2 的尺寸；
    其余（如 1792x1024=7:4）返回 None，由调用方回退 16:9。
    """
    match = re.fullmatch(r"(\d+)\s*[xX×]\s*(\d+)", str(size or "").strip())
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        return None
    divisor = math.gcd(width, height)
    ratio = "%d:%d" % (width // divisor, height // divisor)
    return ratio if ratio in ("16:9", "9:16", "1:1", "2:3", "3:2") else None


# ==================== 响应解析 ====================

def _looks_like_video_url(value):
    """URL 形态判定：带视频扩展名或 data:video 前缀。"""
    return bool(value) and (
        bool(_VIDEO_EXT_RE.search(value)) or str(value).startswith("data:video")
    )


def _pick_video_url(node):
    """递归在响应结构中抽取视频 URL（命名键优先，含 video 语义键的 http(s) 值）。"""
    if isinstance(node, dict):
        for key in ("video_url", "videoUrl", "download_url", "downloadUrl", "url", "video"):
            value = node.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://", "data:")):
                if _looks_like_video_url(value) or "video" in key.lower():
                    return value
        for value in node.values():
            found = _pick_video_url(value)
            if found:
                return found
    elif isinstance(node, (list, tuple)):
        for item in node:
            found = _pick_video_url(item)
            if found:
                return found
    return ""


def _extract_video_url_from_response(response_json):
    """从 JSON 抽视频 URL：结构化递归 + 正则 / <video src> 兜底。"""
    found = _pick_video_url(response_json)
    if found:
        return found
    try:
        text = (
            response_json
            if isinstance(response_json, str)
            else json.dumps(response_json, ensure_ascii=False, default=str)
        )
    except (TypeError, ValueError):
        text = str(response_json)
    for url in _VIDEO_TAG_SRC_RE.findall(text):
        if url:
            return url
    for url in _URL_RE.findall(text):
        if _VIDEO_EXT_RE.search(url):
            return url
    return ""


def _extract_video_task_id(payload):
    """从任务 JSON 抽 video_id / task_id / id。"""
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    for node in (data if isinstance(data, dict) else None, payload):
        if isinstance(node, dict):
            for key in ("video_id", "videoId", "task_id", "taskId", "id"):
                value = node.get(key)
                if value:
                    return str(value)
    return ""


def _extract_video_task_status(payload):
    """从任务 JSON 抽 status。"""
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    for node in (data if isinstance(data, dict) else None, payload):
        if isinstance(node, dict):
            status = node.get("status") or node.get("state")
            if status:
                return str(status)
    return ""


def _collect_event_text(event):
    """从 SSE 事件 JSON 的 choices/delta/message 中收集文本。"""
    texts = []
    if isinstance(event, dict):
        for choice in event.get("choices") or []:
            for part in (choice.get("delta"), choice.get("message")):
                if isinstance(part, dict):
                    content = part.get("content")
                    if isinstance(content, str):
                        texts.append(content)
        message = event.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            texts.append(message["content"])
        if isinstance(event.get("text"), str):
            texts.append(event["text"])
    return "".join(texts)


def _sanitize_response_text(text, max_chars=800):
    """响应文本脱敏：data URI / 大段 base64 打码 + 截断。"""
    value = str(text or "")
    value = re.sub(
        r"data:[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+",
        lambda m: m.group(0).split(";base64,", 1)[0] + ";base64,<base64 omitted>",
        value,
    )
    value = re.sub(r"[A-Za-z0-9+/=]{512,}", "<base64 omitted>", value)
    if len(value) > max_chars:
        value = value[:max_chars] + "... <truncated>"
    return value


def _extract_video_result_from_sse(response):
    """解析 SSE：`data:` 事件块消费直至 [DONE]。

    结构化事件字段（video_url 等命名键）优先于 delta 文本中出现的 URL；
    返回 (video_url, task_id, sanitized_raw_text)。
    """
    raw_lines = []
    structural_url = ""
    text_url = ""
    task_id = ""
    for raw_line in response.iter_lines(decode_unicode=False):
        if isinstance(raw_line, bytes):
            line = raw_line.decode("utf-8", "replace")
        else:
            line = str(raw_line)
        raw_lines.append(line)
        stripped = line.strip()
        if not stripped or not stripped.startswith("data:"):
            continue
        data_text = stripped[len("data:"):].strip()
        if data_text == "[DONE]":
            break
        if not data_text:
            continue
        try:
            event = json.loads(data_text)
        except ValueError:
            event = None
            if not text_url:
                for url in _URL_RE.findall(data_text):
                    if _VIDEO_EXT_RE.search(url):
                        text_url = url
                        break
        if isinstance(event, dict):
            structural = _pick_video_url(event)
            if structural:
                structural_url = structural  # 后到的事件覆盖（最终结果通常在末尾）
            if not task_id:
                task_id = _extract_video_task_id(event)
            if not structural and not text_url:
                for url in _URL_RE.findall(_collect_event_text(event)):
                    if _VIDEO_EXT_RE.search(url):
                        text_url = url
                        break
    return structural_url or text_url, task_id, _sanitize_response_text("\n".join(raw_lines))


# ==================== 输入图处理 ====================

def _scale_image_tensor_to_total_pixels_if_needed(image_tensor, label="参考图"):
    """输入图按总像素自动缩放（仅当超过 _MAX_INPUT_IMAGE_MEGAPIXELS 时降采样）。"""
    import torch  # 惰性导入

    if not isinstance(image_tensor, torch.Tensor) or image_tensor.ndim < 3:
        return image_tensor
    height, width = int(image_tensor.shape[-3]), int(image_tensor.shape[-2])
    total = height * width
    limit = int(_MAX_INPUT_IMAGE_MEGAPIXELS * 1000 * 1000)
    if total <= limit:
        logger.info(
            "未缩放: %s (%dx%d，未超过约 %.1fMP)"
            % (label, width, height, _MAX_INPUT_IMAGE_MEGAPIXELS)
        )
        return image_tensor
    scale = math.sqrt(limit / float(total))
    new_height = max(1, int(height * scale))
    new_width = max(1, int(width * scale))
    batched = image_tensor if image_tensor.ndim == 4 else image_tensor.unsqueeze(0)
    moved = batched.movedim(-1, 1)  # BHWC → BCHW
    scaled = torch.nn.functional.interpolate(
        moved, size=(new_height, new_width), mode=_OFFICIAL_SCALE_METHOD
    )
    result = scaled.movedim(1, -1)
    if image_tensor.ndim != 4:
        result = result.squeeze(0)
    logger.info(
        "自动缩放: %s %dx%d -> %dx%d (目标约 %.1fMP)"
        % (label, width, height, new_width, new_height, _MAX_INPUT_IMAGE_MEGAPIXELS)
    )
    return result


def _count_batch_images(image_tensor):
    """统计批内张数（BHWC 取 shape[0]，其余按 1 张）。"""
    try:
        if image_tensor is not None and image_tensor.ndim == 4:
            return int(image_tensor.shape[0])
    except AttributeError:
        pass
    return 1 if image_tensor is not None else 0


def _shape_to_hw_text(shape):
    """形状 → 'HxW' 描述文本。"""
    try:
        return "%dx%d" % (int(shape[-3]), int(shape[-2]))
    except (TypeError, IndexError, ValueError):
        return str(tuple(shape))


def _encode_image_batch_to_data_urls(image_tensor):
    """IMAGE 批 → Base64 data URI 列表。"""
    images = IMAGE_CODEC.extract_numpy_images(image_tensor)
    return [encode_numpy_image_to_api_data_url(image) for image in images]


# ==================== VIDEO 输出包装 ====================

def _make_video_from_file(path):
    """VideoFromFile 包装（惰性导入，_HAS_COMFY_VIDEO 为 False 时报环境不支持）。"""
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

class BananaGrokVideoSafePyNode:
    """TE MAN Grok Video

    注册名: TE_image_pro_grok_video
    规格:   spec/Grok_Video_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Grok'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '生成一个西瓜切开里面是棉花糖的视频', 'tooltip': '用于生成视频的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址不要带 /v1/videos）'}), 'model': ('STRING', {'default': 'grok-imagine-video', 'multiline': False, 'tooltip': '线路1使用此模型；线路2固定使用 grok-imagine-video2'}), 'seconds': (('10', '15'), {'default': '10', 'tooltip': '视频时长（秒）'}), 'size': (('720x1280', '1280x720', '1024x1792', '1792x1024'), {'default': '1280x720', 'tooltip': '画面尺寸'}), 'resolution_name': (('480p', '720p'), {'default': '720p', 'tooltip': '线路1通过 resolution 字段提交的分辨率；线路2不提交此值'}), 'preset': (('fun', 'normal', 'spicy', 'custom'), {'default': 'normal', 'tooltip': '旧工作流兼容项；线路2当前 JSON 请求不再提交此值'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image': ('IMAGE', {'tooltip': '参考图片 1（可选）'}), 'image_2': ('IMAGE', {'tooltip': '参考图片 2（可选）'}), 'image_3': ('IMAGE', {'tooltip': '参考图片 3（可选）'}), 'image_4': ('IMAGE', {'tooltip': '参考图片 4（可选）'}), 'image_5': ('IMAGE', {'tooltip': '参考图片 5（可选）'}), 'timeout_s': ('INT', {'default': 600, 'min': 30, 'max': 3600, 'tooltip': '请求超时（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '线路选择': (('线路1', '线路2'), {'default': '线路2', 'tooltip': '线路12'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 配置解析（spec §3.1 步骤 2） ====================

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

    # ==================== 线路1：/v1/videos images 数组 ====================

    def _run_line1(self, session, api_key, base_url, prompt, model_name, seconds,
                   size, resolution_name, preset, data_url, timeout_s):
        """线路1：Base64 data URI -> JSON images，POST /v1/videos。"""
        _ensure_not_interrupted()
        ratio = _line1_ratio_from_size(size)
        if ratio is None:
            logger.warning("线路1不支持 size=%s，已回退为 16:9" % size)
            ratio = "16:9"
        payload = {
            "prompt": prompt,
            "model": model_name or "grok-imagine-video",
            "images": [data_url] if data_url else [],
            "aspect_ratio": ratio,
        }
        payload.update(_video_config_payload(
            seconds, size, resolution_name, preset, include_line1_fields=True
        ))
        endpoint = _resolve_videos_url(base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        logger.info("传图方式: Base64 data URI -> JSON images")
        logger.info(" 开始请求... POST /v1/videos")
        response = session.post(
            endpoint, json=payload, headers=headers, timeout=(15, timeout_s), stream=False
        )
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(
                "API 调用失败: HTTP %s，响应片段: %s"
                % (status_code, _sanitize_response_text(getattr(response, "text", ""), 200))
            )
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError("API 调用失败: 返回内容为空或非 JSON")
        video_url = _extract_video_url_from_response(body)
        if video_url:
            return video_url, _sanitize_response_text(json.dumps(body, ensure_ascii=False, default=str))
        task_id = _extract_video_task_id(body)
        if task_id:
            logger.info("提交成功: task_id=%s" % task_id)
            return self._post_videos_async_and_get_download_url(
                session, api_key, base_url, task_id, timeout_s
            )
        raise RuntimeError(
            "未在响应中解析到视频 URL。响应片段: "
            + _sanitize_response_text(getattr(response, "text", ""), 200)
        )

    def _post_videos_async_and_get_download_url(self, session, api_key, base_url,
                                                task_id, timeout_s):
        """线路的异步任务提交 + 轮询 → 下载 URL（状态机按 spec 附录）。"""
        status_url = _resolve_videos_url(base_url) + "/" + str(task_id)
        headers = {"Authorization": "Bearer %s" % api_key, "User-Agent": _USER_AGENT}
        started = time.monotonic()
        poll_interval = 5.0
        attempt = 0
        while True:
            _ensure_not_interrupted()
            elapsed = time.monotonic() - started
            if elapsed > timeout_s:
                raise RuntimeError(
                    "异步视频任务轮询超时（%.0fs）。任务ID: %s" % (elapsed, task_id)
                )
            attempt += 1
            try:
                resp = session.get(status_url, headers=headers, timeout=(15, 60))
            except Exception as exc:  # noqa: BLE001
                logger.warning("查询视频任务失败: %s" % exc)
                time.sleep(poll_interval)
                continue
            status_code = getattr(resp, "status_code", 0)
            if status_code >= 400:
                logger.warning("查询视频任务失败: HTTP %s" % status_code)
                time.sleep(poll_interval)
                continue
            try:
                body = resp.json()
            except ValueError:
                logger.warning(
                    "查询视频任务返回非 JSON: %s" % _sanitize_response_text(getattr(resp, "text", ""), 120)
                )
                time.sleep(poll_interval)
                continue
            status = _extract_video_task_status(body).lower()
            if attempt % 10 == 0:
                logger.info("任务状态: %s (尝试 %d)" % (status or "unknown", attempt))
            if status in _VIDEO_DONE_STATUS:
                video_url = _extract_video_url_from_response(body)
                if not video_url:
                    raise RuntimeError(
                        "异步视频任务成功，但未解析到下载地址。响应片段: "
                        + _sanitize_response_text(json.dumps(body, ensure_ascii=False, default=str), 200)
                    )
                return video_url, _sanitize_response_text(json.dumps(body, ensure_ascii=False, default=str))
            if status in _VIDEO_FAILED_STATUS:
                raise RuntimeError(
                    "异步视频任务失败。响应片段: "
                    + _sanitize_response_text(json.dumps(body, ensure_ascii=False, default=str), 200)
                )
            time.sleep(poll_interval)

    # ==================== 线路2：/v1/chat/completions SSE ====================

    def _run_line2(self, session, api_key, base_url, prompt, seconds, data_url, timeout_s):
        """线路2：Base64 data URI -> JSON image_url，POST /v1/chat/completions（SSE）。"""
        _ensure_not_interrupted()
        # 线路2固定使用 grok-imagine-video2（tooltip 原文）
        content = [{"type": "text", "text": prompt}]
        if data_url:
            content.append({"type": "image_url", "image_url": {"url": data_url}})
        payload = {
            "model": "grok-imagine-video2",
            "messages": [{"role": "user", "content": content}],
            "stream": True,
        }
        payload.update(_video_config_payload(
            seconds, "", "", "", include_line1_fields=False
        ))
        endpoint = _resolve_chat_completions_url(base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
            "Accept": "text/event-stream",
        }
        logger.info("传图方式: Base64 data URI -> JSON image_url")
        logger.info(" 开始请求... POST /v1/chat/completions（SSE 流式）")
        response = session.post(
            endpoint, json=payload, headers=headers, timeout=(15, timeout_s), stream=True
        )
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(
                "API 调用失败: HTTP %s，响应片段: %s"
                % (status_code, _sanitize_response_text(getattr(response, "text", ""), 200))
            )
        try:
            video_url, task_id, response_text = _extract_video_result_from_sse(response)
        finally:
            try:
                response.close()
            except Exception:  # noqa: BLE001
                pass
        if video_url:
            return video_url, response_text
        if task_id:
            logger.info("流式返回任务 ID: %s，转入 /v1/videos 轮询" % task_id)
            return self._post_videos_async_and_get_download_url(
                session, api_key, base_url, task_id, timeout_s
            )
        raise RuntimeError("未在响应中解析到视频 URL。响应片段: " + response_text[:200])

    # ==================== 下载（spec §3.1 步骤 7） ====================

    def _download_video(self, session, video_url, api_key, route, timeout_s):
        """流式分块下载到 ComfyUI output，grok_video_ 前缀命名；线路1要求鉴权下载。"""
        _ensure_not_interrupted()
        require_auth_download = (route == "线路1")
        if require_auth_download and not api_key:
            raise RuntimeError("下载视频失败: 当前线路要求鉴权下载，但未提供 Authorization 头")
        headers = {"User-Agent": _USER_AGENT, "Accept-Encoding": "identity"}
        if api_key:
            headers["Authorization"] = "Bearer %s" % api_key
        logger.info("开始下载视频到 ComfyUI/output ...")
        try:
            import folder_paths  # 仅 ComfyUI 环境存在

            output_dir = folder_paths.get_output_directory()
        except Exception:  # noqa: BLE001  纯 Python 环境回退
            output_dir = os.path.join(os.getcwd(), "output")
        os.makedirs(output_dir, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, "%s%s.mp4" % (_OUTPUT_FILE_PREFIX, stamp))
        counter = 1
        while os.path.exists(path):
            path = os.path.join(
                output_dir, "%s%s_%d.mp4" % (_OUTPUT_FILE_PREFIX, stamp, counter)
            )
            counter += 1
        total = 0
        try:
            with session.get(video_url, headers=headers, stream=True, timeout=(15, timeout_s)) as resp:
                status_code = getattr(resp, "status_code", 0)
                if status_code >= 400:
                    raise RuntimeError("下载视频失败: HTTP %s" % status_code)
                with open(path, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        total += len(chunk)
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("下载视频失败: %s" % exc) from exc
        if total <= 0:
            raise RuntimeError("下载视频失败: 返回内容为空")
        logger.info("视频已保存: %s（大小: %d KB）" % (path, total // 1024))
        return path

    # ==================== FUNCTION ====================

    def generate_video(self, **kwargs):
        """TE_image_pro_grok_video：线路1 /v1/videos 或线路2 chat/completions SSE。"""
        _ensure_not_interrupted()
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(_MSG_EMPTY_PROMPT)
        route = str(kwargs.get("线路选择") or "线路2")
        model_name = str(kwargs.get("model") or "grok-imagine-video").strip()
        seconds = str(kwargs.get("seconds") or "10")
        size = str(kwargs.get("size") or "1280x720")
        resolution_name = str(kwargs.get("resolution_name") or "720p")
        preset = str(kwargs.get("preset") or "normal")
        # seed：仅供 ComfyUI 工作流使用，不写入请求体
        try:
            timeout_s = max(30, int(kwargs.get("timeout_s") or 600))
        except (TypeError, ValueError):
            timeout_s = 600
        bypass_proxy = bool(kwargs.get("绕过代理"))

        api_key, base_url = self._resolve_key_and_url(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        logger.info("线路选择: %s" % route)
        session = _build_session(bypass_proxy)
        _log_proxy_policy(bypass_proxy, bool(api_key))

        # ---- 参考图：无论几张，接口实际仅发送第 1 张（自动缩放 + data URI 编码） ----
        input_tensors = [
            kwargs.get(name)
            for name in ("image", "image_2", "image_3", "image_4", "image_5")
            if kwargs.get(name) is not None
        ]
        data_url = ""
        if input_tensors:
            if len(input_tensors) > 1:
                logger.info("参考图收到 %d 张，当前接口仅发送第 1 张" % len(input_tensors))
            first_tensor = _scale_image_tensor_to_total_pixels_if_needed(input_tensors[0], "参考图")
            logger.info("参考图: %s，张数: %d" % (_shape_to_hw_text(first_tensor.shape), _count_batch_images(first_tensor)))
            data_url = _encode_image_batch_to_data_urls(first_tensor)[0]

        if route == "线路1":
            video_url, response_text = self._run_line1(
                session, api_key, base_url, prompt, model_name, seconds,
                size, resolution_name, preset, data_url, timeout_s
            )
        else:
            video_url, response_text = self._run_line2(
                session, api_key, base_url, prompt, seconds, data_url, timeout_s
            )
        if not video_url:
            raise RuntimeError("未在响应中解析到视频 URL。响应片段: " + response_text[:200])

        video_path = self._download_video(session, video_url, api_key, route, timeout_s)
        logger.info("生成成功")
        video = _make_video_from_file(video_path)
        return (video, video_url, response_text)

NODE_CLASS_MAPPINGS = {'TE_image_pro_grok_video': BananaGrokVideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_grok_video': 'TE MAN Grok Video'}
