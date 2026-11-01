# -*- coding: utf-8 -*-
"""api_client —— TE MAN 插件网络请求层的纯 Python 复刻。

逆向规格: spec/api_client.md（静态逆向 + Windows 真机 introspection 回填）。

**封装与 Gemini 兼容图像接口交互的 HTTP 客户端**（原类 docstring 原文）。
四套协议共用一个 ``GeminiApiClient``：

1. Gemini 原生：``POST {base}/v1beta/models/{model}:generateContent``（同步）
   与 ``:streamGenerateContent?alt=sse``（SSE 流式）
2. OpenAI 兼容图像：``POST /v1/images/generations``（文生图 JSON）、
   ``POST /v1/images/edits``（图生图 multipart image_1..image_9）、
   异步任务 ``GET /v1/images/tasks/{id}`` 轮询
3. Chat Completions：``POST /v1/chat/completions``（同步 + SSE 流式）
4. 视频：``POST /v1/videos`` 提交拿 task_id → ``GET /v1/videos/{task_id}``
   轮询 → 流式下载
5. 余额：``GET /api/usage/token``（认证头 X-API-Key）

基础设施（spec §3.5/§3.7）：
- 可中断请求：后台线程发起，主线程轮询中断标志，必要时关闭 session 终止阻塞；
  comfy.model_management 惰性导入，不可用则降级普通请求
- 断流自动按 ``Connection: close`` 重试一次
- 轮询限流退避（429 延长等待时间）
- 日志脱敏：API Key / base64 / URL 截断打码
- 面向用户的中文错误摘要（避免暴露源站计费细节）

requests 为惰性导入；模块顶层只 import 标准库。
"""

import base64
import json
import logging as _stdlib_logging
import math
import re
import threading
import time
import warnings
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlsplit

try:  # 中断异常：与 task_runner / comfy.model_management 对齐
    from .task_runner import InterruptProcessingException
except Exception:  # noqa: BLE001  纯 Python 环境回退
    class InterruptProcessingException(Exception):
        """comfy 不可用时的中断异常回退。"""

try:  # 日志注入点（spec：logger_instance）
    from .logger import logger as _LOGGER_INSTANCE
except Exception:  # noqa: BLE001
    _LOGGER_INSTANCE = None

try:  # 配置注入点（spec：config_manager）
    from .config_manager import CONFIG_MANAGER as _CONFIG_MANAGER
except Exception:  # noqa: BLE001
    _CONFIG_MANAGER = None

_FALLBACK_LOGGER = _stdlib_logging.getLogger("comfyui-te_api")

__all__ = ["GeminiApiClient", "API_CLIENT", "sanitize_api_key"]


# ==================== 日志辅助 ====================

def _log(level: str, message: str) -> None:
    """经注入的 logger 输出；不可用时降级 stdlib logging。"""
    target = _LOGGER_INSTANCE if _LOGGER_INSTANCE is not None else _FALLBACK_LOGGER
    method = getattr(target, level, None)
    if callable(method):
        try:
            method(message)
            return
        except Exception:  # noqa: BLE001
            pass
    _FALLBACK_LOGGER.log(_stdlib_logging.INFO, message)


def _log_info(message: str) -> None:
    _log("info", message)


def _log_success(message: str) -> None:
    _log("success", message)


def _log_warning(message: str) -> None:
    _log("warning", message)


def _log_error(message: str) -> None:
    _log("error", message)


# ==================== 模块级工具函数 ====================

def sanitize_api_key(api_key: Optional[str]) -> str:
    """日志中打码 API Key：保留首尾 4 位，中间以 * 占位。"""
    if not api_key:
        return ""
    key = str(api_key).strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 8 + key[-4:]


# 正则（spec 附录原文）
_DATA_IMAGE_RE = re.compile(
    r"data:image/(?P<mime>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)"
)
_BASE64_CHARS_RE = re.compile(r"[A-Za-z0-9+/=\s]+")
_BASE64_JSON_KEY_RE = re.compile(r"\"b64_json\"\s*:\s*\"([A-Za-z0-9+/=\s]+)\"")
_MARKDOWN_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_MARKDOWN_LINK_RE = re.compile(r"\[.*?\]\((https?://[^\)]+)\)")
_HTML_IMG_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']")
_BARE_URL_RE = re.compile(r"(https?://[^\s\)\]\}>'\"\\]+)")
# 断流报错文本按去空格/连字符后匹配（invalidchunklength 等原文形态）
_BROKEN_STREAM_TEXT_RE = re.compile(
    "connectionreset|incompleteread|connectionaborted|remoteendclosed"
    "|connectionbroken|badstatusline|invalidchunklength|protocolerror"
    "|brokenpipe|responseendedprematurely",
    re.IGNORECASE,
)

# base64 调试脱敏键集合（spec：_DEBUG_BASE64_KEYS）
_DEBUG_BASE64_KEYS = frozenset(
    {"data", "b64_json", "inlineData", "image", "images", "image_url", "base64"}
)


def _looks_like_base64_blob(value: Any) -> bool:
    """判断字符串是否疑似 base64 大块体（用于日志脱敏）。"""
    if not isinstance(value, str) or len(value) < 256:
        return False
    if _BASE64_CHARS_RE.fullmatch(value) is None:
        return False
    return len(re.sub(r"\s+", "", value)) >= 256


def _sanitize_debug_payload(parent_key: Any, items: Iterable[Tuple[Any, Any]]) -> List[Tuple[str, Any]]:
    """对 (key, value) 序列做调试脱敏：base64 值替换为截断占位符。"""
    parent = str(parent_key) if parent_key is not None else ""
    sanitized: List[Tuple[str, Any]] = []
    for key, value in items:
        s_key = str(key)
        if isinstance(value, str):
            if (
                s_key in _DEBUG_BASE64_KEYS
                or (parent and parent in _DEBUG_BASE64_KEYS)
                or _looks_like_base64_blob(value)
            ):
                sanitized.append((s_key, f"<base64 omitted chars={len(value)}>"))
            else:
                sanitized.append((s_key, _shorten_url_for_log(value)))
        elif isinstance(value, dict):
            sanitized.append((s_key, dict(_sanitize_debug_payload(s_key, value.items()))))
        elif isinstance(value, (list, tuple)):
            sanitized.append(
                (s_key, [item[1] for item in _sanitize_debug_payload(s_key, [(i, v) for i, v in enumerate(value)])])
            )
        else:
            sanitized.append((s_key, value))
    return sanitized


def _format_debug_payload(payload: Any, max_chars: int = 600) -> str:
    """把 payload 序列化为脱敏 + 截断的调试字符串。

    超长时以 ``... <truncated chars=N>`` 结尾（spec 原文占位符）。
    """
    try:
        if isinstance(payload, dict):
            sanitized = dict(_sanitize_debug_payload("", list(payload.items())))
        elif isinstance(payload, (list, tuple)):
            sanitized = [item[1] for item in _sanitize_debug_payload("", list(enumerate(payload)))]
        else:
            sanitized = payload
        text = json.dumps(sanitized, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        text = str(payload)
    if len(text) > max_chars:
        omitted = len(text) - max_chars
        text = text[:max_chars] + f"... <truncated chars={omitted}>"
    return text


def _sanitize_text_payload(payload_text: Any, max_chars: int = 300) -> str:
    """对文本 payload 脱敏：data URI 打码 + 截断。"""

    def _replace_data_uri(match: "re.Match") -> str:
        return (
            f"data:image/{match.group('mime')};base64,"
            f"<base64 omitted chars={len(match.group('data'))}>"
        )

    text = str(payload_text or "")
    sanitized = _DATA_IMAGE_RE.sub(_replace_data_uri, text)
    sanitized = _BASE64_JSON_KEY_RE.sub(
        lambda m: '"b64_json":"<base64 omitted chars=%d>"' % len(re.sub(r"\s+", "", m.group(1))),
        sanitized,
    )
    if len(sanitized) > max_chars:
        omitted = len(sanitized) - max_chars
        sanitized = sanitized[:max_chars] + f"... <truncated chars={omitted}>"
    return sanitized


def _shorten_url_for_log(url: Any, max_len: int = 120) -> str:
    """日志中缩短 URL：去查询串 + 截断。"""
    if not isinstance(url, str):
        url = str(url)
    try:
        parts = urlsplit(url)
        if parts.query or parts.fragment:
            url = f"{parts.scheme}://{parts.netloc}{parts.path}?<query omitted>"
    except Exception:  # noqa: BLE001
        pass
    if len(url) > max_len:
        url = url[:max_len] + f"... <truncated chars={len(url) - max_len}>"
    return url


# ==================== 内部信号异常 ====================

class _PollRateLimited(Exception):
    """轮询命中 429 限流的内部信号。"""


# ==================== GeminiApiClient ====================

class GeminiApiClient:
    """封装与 Gemini 兼容图像接口交互的 HTTP 客户端。"""

    # ==================== 类级常量（真机 introspection：非模块级） ====================
    _DEFAULT_CONNECT_TIMEOUT = 15.0
    _DEFAULT_READ_TIMEOUT = 300.0
    _MAX_RETRIES = 3
    _BASE_BACKOFF = 2.0
    _RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
    _DEFAULT_POLL_ATTEMPTS = 120
    _DEFAULT_POLL_INTERVAL = 3.0
    _VIDEO_POLL_ATTEMPTS = 600
    _VIDEO_POLL_INTERVAL = 5.0
    _MAX_INPUT_IMAGES = 9

    _INSECURE_WARNING_SUPPRESSED = False

    _USER_AGENT = "ComfyUI-TE_API/1.0"

    # 宽高比别名表（spec §3.1 值集合；别名形态按常用写法补全）
    _ASPECT_RATIO_ALIASES: Dict[str, str] = {
        "1:1": "1:1", "1x1": "1:1", "square": "1:1",
        "16:9": "16:9", "16x9": "16:9", "1920:1080": "16:9", "1080:1920": "9:16",
        "landscape": "16:9", "widescreen": "16:9",
        "21:9": "21:9", "21x9": "21:9", "ultrawide": "21:9",
        "9:16": "9:16", "9x16": "9:16", "portrait": "9:16", "vertical": "9:16",
        "4:3": "4:3", "4x3": "4:3",
        "3:4": "3:4", "3x4": "3:4",
        "2:3": "2:3", "2x3": "2:3",
        "3:2": "3:2", "3x2": "3:2",
        "5:4": "5:4", "5x4": "5:4",
        "4:5": "4:5", "4x5": "4:5",
    }

    _IMAGE_SIZE_ALIASES: Dict[str, str] = {
        "1k": "1K", "2k": "2K", "4k": "4K",
        "1024": "1K", "2048": "2K", "4096": "4K",
        "auto": "auto",
    }

    # OpenAI 任务状态字面量（spec 附录）
    _OPENAI_TASK_DONE = frozenset({"SUCCESS", "completed"})
    _OPENAI_TASK_FAILED = frozenset({"FAILURE", "failed"})
    # 视频任务状态机
    _VIDEO_DONE = frozenset({"completed", "succeeded", "ready", "finished", "success"})
    _VIDEO_FAILED = frozenset(
        {"failed", "failure", "error", "cancelled", "canceled", "expired", "rejected"}
    )

    _MIME_EXTENSION_MAP: Dict[str, str] = {
        "image/png": ".png",
        "image/jpeg": ".jpeg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }

    def __init__(self) -> None:
        self._thread_local = threading.local()
        self._session_lock = threading.Lock()
        self._session_cache: Dict[Tuple[bool, bool], Any] = {}
        self._session_pool_connections = 10
        self._session_pool_maxsize = 10

    # ==================== 配置接入（防御式 getattr，失效时回退） ====================
    def _get_config(self):
        if _CONFIG_MANAGER is None:
            return None
        return _CONFIG_MANAGER

    def _get_api_key(self) -> str:
        """经 CONFIG_MANAGER 读取并规整 API Key；不可用/为空回退空串。"""
        cfg = self._get_config()
        if cfg is None:
            return ""
        loader = getattr(cfg, "load_api_key", None)
        if callable(loader):
            try:
                return loader() or ""
            except Exception:  # noqa: BLE001
                pass
        return ""

    def _get_base_url(self, override: Optional[str] = None, default: str = "") -> str:
        """Base URL：显式传参优先，否则取配置三级解析链。"""
        if override and str(override).strip():
            return str(override).strip()
        cfg = self._get_config()
        if cfg is not None:
            getter = getattr(cfg, "get_effective_api_base_url", None)
            if callable(getter):
                try:
                    url = getter(default or "")
                    if url:
                        return str(url).strip()
                except Exception:  # noqa: BLE001
                    pass
        return (default or "").strip()

    def _get_bypass_proxy(self, override: Optional[bool] = None) -> bool:
        if override is not None:
            return bool(override)
        cfg = self._get_config()
        if cfg is not None:
            for name in ("is_bypass_proxy", "should_bypass_proxy"):
                method = getattr(cfg, name, None)
                if callable(method):
                    try:
                        return bool(method())
                    except Exception:  # noqa: BLE001
                        pass
        return False

    def _get_read_timeout_override(self) -> Optional[float]:
        """read_timeout_global 全局覆盖（spec §4 行为配置）；未配置返回 None。"""
        cfg = self._get_config()
        if cfg is None:
            return None
        value = getattr(cfg, "read_timeout_global", None)
        if value is None:
            getter = getattr(cfg, "get_read_timeout_global", None)
            if callable(getter):
                try:
                    value = getter()
                except Exception:  # noqa: BLE001
                    value = None
        if value is None:
            return None
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed > 0 else None

    # ==================== 归一化（spec §3.1） ====================
    def _normalize_aspect_ratio(self, aspect_ratio: Any) -> Optional[str]:
        """宽高比别名归一：命中 _ASPECT_RATIO_ALIASES 则返回规范值，否则 None。"""
        if not aspect_ratio:
            return None
        text = str(aspect_ratio).strip().lower()
        text = text.replace("×", "x").replace("：", ":").replace("＊", "x")
        text = re.sub(r"\s+", "", text)
        if text in self._ASPECT_RATIO_ALIASES:
            return self._ASPECT_RATIO_ALIASES[text]
        match = re.fullmatch(r"(\d+)[:x](\d+)", text)
        if match:
            width, height = int(match.group(1)), int(match.group(2))
            if width > 0 and height > 0:
                divisor = math.gcd(width, height)
                reduced = f"{width // divisor}:{height // divisor}"
                if reduced in self._ASPECT_RATIO_ALIASES:
                    return reduced
        return None

    def _normalize_image_size(self, image_size: Any) -> Optional[str]:
        """图像尺寸归一：合法值 1K/2K/4K，另有 auto。"""
        if not image_size:
            return None
        text = str(image_size).strip().lower()
        return self._IMAGE_SIZE_ALIASES.get(text)

    def _normalize_resolution(
        self, aspect_ratio: Any = None, image_size: Any = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """产出 (normalized_aspect, normalized_size)。"""
        return self._normalize_aspect_ratio(aspect_ratio), self._normalize_image_size(image_size)

    # ==================== 输入图像处理（spec §3.2） ====================
    @staticmethod
    def _image_extension_from_mime(mime_type: Any) -> str:
        """mime → 扩展名；未知 mime 回退 .png。"""
        mime = str(mime_type or "").strip().lower().split(";")[0]
        return GeminiApiClient._MIME_EXTENSION_MAP.get(mime, ".png")

    @staticmethod
    def _sniff_image_mime(data: bytes) -> str:
        """按魔数嗅探 mime；未知回退 image/png。"""
        if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png"
        if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
            return "image/jpeg"
        if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif"
        if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            return "image/webp"
        return "image/png"

    def _input_image_to_data_url(self, image: Any) -> Optional[str]:
        """把输入图归一为 ``data:image/...;base64,...`` data URL。"""
        if isinstance(image, (bytes, bytearray)):
            b64 = base64.b64encode(bytes(image)).decode("ascii")
            mime = self._sniff_image_mime(bytes(image))
            return f"data:{mime};base64,{b64}"
        if not isinstance(image, str):
            return None
        text = image.strip()
        if not text:
            return None
        if text.startswith("data:image/") and ";base64," in text:
            return text
        if text.startswith("http://") or text.startswith("https://"):
            # URL 输入按原样返回（由各协议层决定 fileData / image_url 语义）
            return text
        if _BASE64_CHARS_RE.fullmatch(text) is not None:
            b64 = re.sub(r"\s+", "", text)
            mime = "image/png"
            try:
                mime = self._sniff_image_mime(base64.b64decode(b64, validate=False))
            except Exception:  # noqa: BLE001
                pass
            return f"data:{mime};base64,{b64}"
        return None

    def _split_input_image_payload(
        self, input_images_b64: Any
    ) -> List[Dict[str, str]]:
        """把 base64 图片列表拆为请求可用载荷：[{mime_type, data, data_url}]。"""
        if input_images_b64 is None:
            return []
        if isinstance(input_images_b64, (str, bytes, bytearray)):
            items: List[Any] = [input_images_b64]
        elif isinstance(input_images_b64, (list, tuple)):
            items = list(input_images_b64)
        else:
            return []
        payloads: List[Dict[str, str]] = []
        seen: set = set()
        for item in items:
            mime_hint = None
            if isinstance(item, (tuple, list)) and len(item) == 2:
                item, mime_hint = item[0], item[1]
            elif isinstance(item, dict):
                mime_hint = item.get("mimeType") or item.get("mime_type")
                item = item.get("data") or item.get("b64_json") or item.get("url")
            data_url = self._input_image_to_data_url(item) if item else None
            if not data_url:
                _log_warning("忽略了无法识别的输入图像，请提供 base64/dataURL/URL 形式")
                continue
            if data_url in seen:
                continue
            seen.add(data_url)
            if data_url.startswith("data:image/"):
                header, _, data = data_url.partition(";base64,")
                mime = header[len("data:"):] or (str(mime_hint) if mime_hint else "image/png")
                payloads.append(
                    {"mime_type": mime, "data": data, "data_url": data_url}
                )
            else:
                payloads.append(
                    {"mime_type": str(mime_hint or "image/png"), "data": "", "data_url": data_url}
                )
            if len(payloads) >= self._MAX_INPUT_IMAGES:
                _log_warning(f"输入图像数量超过上限 {self._MAX_INPUT_IMAGES}，已截断")
                break
        return payloads

    def _payload_to_part(self, payload: Dict[str, str]) -> Dict[str, Any]:
        """Gemini part：URL 走 fileData/fileUri，base64 走 inlineData。"""
        if payload["data_url"].startswith("data:image/"):
            return {
                "inlineData": {
                    "mimeType": payload["mime_type"],
                    "data": payload["data"],
                }
            }
        return {
            "fileData": {
                "mimeType": payload["mime_type"],
                "fileUri": payload["data_url"],
            }
        }

    # ==================== 请求体构建（spec §3.3） ====================
    def create_request_data(
        self,
        prompt: Any,
        input_images_b64: Any = None,
        model_type: Any = None,
        aspect_ratio: Any = None,
        image_size: Any = None,
        response_modalities: Optional[List[str]] = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Gemini 原生 generateContent 请求体（contents/parts/inlineData/fileData）。"""
        prompt_text = str(prompt or "").strip()
        payloads = self._split_input_image_payload(input_images_b64)
        if not prompt_text and not payloads:
            raise ValueError("请输入提示词或提供至少一张参考图像")
        parts: List[Dict[str, Any]] = []
        for payload in payloads:
            parts.append(self._payload_to_part(payload))
        if prompt_text:
            parts.append({"text": prompt_text})
        contents = [{"role": "user", "parts": parts}]
        generation_config: Dict[str, Any] = {
            "responseModalities": response_modalities or ["IMAGE", "TEXT"]
        }
        normalized_aspect, normalized_size = self._normalize_resolution(
            aspect_ratio, image_size
        )
        image_config: Dict[str, Any] = {}
        if normalized_aspect:
            image_config["aspectRatio"] = normalized_aspect
        if normalized_size and normalized_size != "auto":
            image_config["imageSize"] = normalized_size
        if image_config:
            generation_config["imageConfig"] = image_config
        request_data: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": generation_config,
        }
        if extra:
            request_data.update(extra)
        return request_data

    def create_openai_request_data(
        self,
        prompt: Any,
        seed: Any = None,
        aspect_ratio: Any = None,
        model_type: Any = None,
        image_size: Any = None,
        response_format: Any = "b64_json",
        input_images_b64: Any = None,
        webhook: Any = None,
        **extra: Any,
    ) -> Tuple[Dict[str, Any], List[Any], bool]:
        """OpenAI 兼容图像请求体。

        返回 ``(data_dict, files_list, is_img2img)``：text2img → JSON；
        img2img → form data + multipart files（image_1..image_9）。
        默认模型 ``nano-banana-2``。
        """
        prompt_text = str(prompt or "").strip()
        payloads = self._split_input_image_payload(input_images_b64)
        is_img2img = bool(payloads)
        data: Dict[str, Any] = {
            "model": str(model_type or "nano-banana-2"),
            "response_format": str(response_format or "b64_json"),
        }
        if prompt_text:
            data["prompt"] = prompt_text
        if seed is not None:
            data["seed"] = seed
        normalized_aspect, normalized_size = self._normalize_resolution(
            aspect_ratio, image_size
        )
        if normalized_aspect:
            data["aspect_ratio"] = normalized_aspect
        if normalized_size:
            data["image_size"] = normalized_size
        if webhook:
            data["webhook"] = webhook
        if extra:
            data.update(extra)
        files: List[Any] = []
        if is_img2img:
            for index, payload in enumerate(payloads, start=1):
                if not payload["data"]:
                    continue
                try:
                    raw = base64.b64decode(payload["data"])
                except Exception as e:  # noqa: BLE001
                    raise ValueError(f"输入图像数据解析失败: {e}") from e
                extension = self._image_extension_from_mime(payload["mime_type"])
                files.append(
                    (
                        f"image_{index}",
                        (f"image_{index}{extension}", raw, payload["mime_type"]),
                    )
                )
        return data, files, is_img2img

    def create_chat_request_data(
        self,
        prompt: Any = None,
        messages: Any = None,
        model: Any = None,
        input_images_b64: Any = None,
        stream: bool = False,
        temperature: Any = None,
        top_p: Any = None,
        max_tokens: Any = None,
        system_prompt: Any = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Chat Completions 请求体（messages/model/stream/top_p）。"""
        if messages:
            normalized_messages = [dict(m) for m in messages if isinstance(m, dict)]
        else:
            prompt_text = str(prompt or "").strip()
            payloads = self._split_input_image_payload(input_images_b64)
            if not prompt_text and not payloads:
                raise ValueError("请输入提示词或提供至少一张参考图像")
            content: Any = prompt_text
            if payloads:
                content_parts: List[Dict[str, Any]] = [
                    {"type": "text", "text": prompt_text}
                ]
                for payload in payloads:
                    content_parts.append(
                        {"type": "image_url", "image_url": {"url": payload["data_url"]}}
                    )
                content = content_parts
            normalized_messages = [{"role": "user", "content": content}]
            if system_prompt:
                normalized_messages.insert(
                    0, {"role": "system", "content": str(system_prompt)}
                )
        request_data: Dict[str, Any] = {
            "messages": normalized_messages,
            "model": str(model or "nano-banana-2"),
            "stream": bool(stream),
        }
        if temperature is not None:
            request_data["temperature"] = temperature
        if top_p is not None:
            request_data["top_p"] = top_p
        if max_tokens is not None:
            request_data["max_tokens"] = max_tokens
        if extra:
            request_data.update(extra)
        return request_data

    def create_video_request_data(
        self,
        prompt: Any,
        input_image_urls: Any = None,
        duration: Any = None,
        model: Any = None,
        aspect_ratio: Any = None,
        image_size: Any = None,
        seed: Any = None,
        **extra: Any,
    ) -> Dict[str, Any]:
        """视频生成请求体（duration 时长字段，/v1/videos 提交）。"""
        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            raise ValueError("请输入提示词或提供至少一张参考图像")
        if isinstance(input_image_urls, (str, bytes, bytearray)):
            image_urls: List[Any] = [input_image_urls]
        elif isinstance(input_image_urls, (list, tuple)):
            image_urls = list(input_image_urls)
        else:
            image_urls = []
        request_data: Dict[str, Any] = {"prompt": prompt_text}
        if model:
            request_data["model"] = str(model)
        if duration is not None:
            request_data["duration"] = duration
        normalized_aspect, normalized_size = self._normalize_resolution(
            aspect_ratio, image_size
        )
        if normalized_aspect:
            request_data["aspect_ratio"] = normalized_aspect
        if normalized_size:
            request_data["image_size"] = normalized_size
        if seed is not None:
            request_data["seed"] = seed
        if image_urls:
            normalized_urls = []
            for url in image_urls:
                if isinstance(url, str) and url.strip():
                    normalized_urls.append(url.strip())
            if normalized_urls:
                request_data["image_urls"] = normalized_urls
        if extra:
            request_data.update(extra)
        return request_data

    # ==================== URL 构建（spec §3.6） ====================
    @staticmethod
    def _join_base(base_url: str) -> str:
        return str(base_url or "").strip().rstrip("/")

    def _build_generate_content_url(self, base_url: str, model: str) -> str:
        base = self._join_base(base_url)
        model = str(model or "gemini-2.5-flash-image").strip("/")
        if base.endswith("/v1beta"):
            return f"{base}/models/{model}:generateContent"
        return f"{base}/v1beta/models/{model}:generateContent"

    def _build_stream_generate_content_url(self, base_url: str, model: str) -> str:
        url = self._build_generate_content_url(base_url, model)
        url = url.replace(":generateContent", ":streamGenerateContent")
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}alt=sse"

    def _build_chat_completions_url(self, base_url: str) -> str:
        base = self._join_base(base_url)
        if base.endswith("/chat/completions"):
            return base
        if re.search(r"/v\d+$", base) or base.endswith("/v1beta"):
            return f"{base}/chat/completions"
        return f"{base}/v1/chat/completions"

    def _build_balance_urls(self, base_url: str) -> List[str]:
        """余额查询多候选 URL（spec：候选具体列表未确认，主候选 /api/usage/token）。"""
        base = self._join_base(base_url)
        return [
            f"{base}/api/usage/token",
            f"{base}/v1/api/usage/token",
        ]

    def _status_endpoint(self, base_url: str, task_id: str, kind: str = "image") -> str:
        """轮询地址构建器：kind ∈ {image, video}。"""
        base = self._join_base(base_url)
        task_id = str(task_id or "").strip()
        if kind == "video":
            if base.endswith("/v1/videos"):
                return f"{base}/{task_id}"
            return f"{base}/v1/videos/{task_id}"
        if base.endswith("/v1/images/tasks"):
            return f"{base}/{task_id}"
        return f"{base}/v1/images/tasks/{task_id}"

    # ==================== 会话 / 头 / 超时（spec §3.5） ====================
    def _suppress_insecure_warning(self) -> None:
        """verify_ssl=False 时屏蔽 InsecureRequestWarning（模块级标志）。"""
        if GeminiApiClient._INSECURE_WARNING_SUPPRESSED:
            return
        try:
            import requests  # noqa: F401  惰性导入
            from urllib3.exceptions import InsecureRequestWarning

            warnings.filterwarnings("ignore", category=InsecureRequestWarning)
            try:
                import urllib3

                urllib3.disable_warnings(InsecureRequestWarning)
            except Exception:  # noqa: BLE001
                pass
            GeminiApiClient._INSECURE_WARNING_SUPPRESSED = True
        except Exception:  # noqa: BLE001
            pass

    def _get_session(
        self,
        bypass_proxy: bool = False,
        verify_ssl: bool = True,
    ) -> Any:
        """requests.Session + HTTPAdapter 连接池；绕代理时另建无代理会话。

        会话按 (bypass_proxy, verify_ssl) 缓存于线程局部（对应 _thread_local）。
        """
        key = (bool(bypass_proxy), bool(verify_ssl))
        cache = getattr(self._thread_local, "sessions", None)
        if cache is None:
            cache = {}
            self._thread_local.sessions = cache
        session = cache.get(key)
        if session is not None:
            try:
                return session
            except Exception:  # noqa: BLE001
                pass
        import requests
        from requests.adapters import HTTPAdapter

        session = requests.Session()
        if bypass_proxy:
            # trust_env=False + 空 proxies → 绕过系统代理（session_no_proxy）
            session.trust_env = False
            session.proxies = {}
        adapter = HTTPAdapter(
            pool_connections=self._session_pool_connections,
            pool_maxsize=self._session_pool_maxsize,
        )
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        session.verify = bool(verify_ssl)
        if not verify_ssl:
            self._suppress_insecure_warning()
        with self._session_lock:
            cache[key] = session
        return session

    def _build_headers(
        self,
        api_key: Any = None,
        *,
        stream: bool = False,
        auth_mode: str = "bearer",
        content_json: bool = True,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """请求头：Authorization: Bearer / X-API-Key + X-Banana-Client + UA。"""
        headers: Dict[str, str] = {
            "User-Agent": self._USER_AGENT,
            "X-Banana-Client": self._USER_AGENT,
        }
        key = str(api_key or "")
        if auth_mode == "x-api-key":
            headers["X-API-Key"] = key
        else:
            headers["Authorization"] = f"Bearer {key}"
            if content_json:
                headers["Content-Type"] = "application/json"
        if stream:
            headers["Accept"] = "text/event-stream"
        if extra_headers:
            headers.update(extra_headers)
        return headers

    def _resolve_timeout(self, timeout: Any = None) -> Tuple[float, float]:
        """归一为 (connect_timeout, read_timeout)；支持全局读取超时覆盖。"""
        connect_timeout = self._DEFAULT_CONNECT_TIMEOUT
        read_timeout = self._DEFAULT_READ_TIMEOUT
        override = self._get_read_timeout_override()
        if override:
            read_timeout = override
        if isinstance(timeout, (tuple, list)) and len(timeout) == 2:
            try:
                return (float(timeout[0]), float(timeout[1]))
            except (TypeError, ValueError):
                pass
        if timeout is not None:
            try:
                value = float(timeout)
                if value > 0:
                    read_timeout = value
            except (TypeError, ValueError):
                pass
        return (connect_timeout, read_timeout)

    # ==================== 可中断请求底座（spec §3.5） ====================
    def _ensure_not_interrupted(self, interrupt_checker: Any = None) -> None:
        """中断检查：优先调用注入回调，并联动 comfy.model_management（惰性）。"""
        if callable(interrupt_checker):
            interrupt_checker()
        try:
            from comfy import model_management  # 惰性导入，失败降级普通请求
        except Exception:  # noqa: BLE001  非 ComfyUI 环境
            return
        throw = getattr(model_management, "throw_exception_if_interrupted", None)
        if callable(throw):
            throw()
            return
        ensure = getattr(model_management, "ensure_not_interrupted", None)
        if callable(ensure):
            ensure()

    def _interruptible_request(
        self,
        session: Any,
        method: str,
        url: str,
        *,
        json_payload: Any = None,
        data: Any = None,
        files: Any = None,
        headers: Any = None,
        timeout: Any = None,
        interrupt_checker: Any = None,
        stream: bool = False,
    ) -> Any:
        """让网络请求在长耗时阶段也能响应中断。

        后台线程发起请求，主线程轮询中断标志，必要时关闭 session 终止阻塞。
        连接阶段单独限时（exceeded_connect_budget 语义），超限报连接错误。
        """
        connect_timeout, read_timeout = self._resolve_timeout(timeout)
        self._ensure_not_interrupted(interrupt_checker)
        done_event = threading.Event()
        resp_holder: Dict[str, Any] = {}
        exc_holder: List[BaseException] = []

        kwargs: Dict[str, Any] = {
            "headers": headers,
            "timeout": (connect_timeout, read_timeout),
            "stream": stream,
        }
        if files:
            kwargs["data"] = data if data is not None else {}
            kwargs["files"] = files
        elif json_payload is not None:
            kwargs["json"] = json_payload
        elif data is not None:
            kwargs["data"] = data

        def _worker() -> None:
            try:
                resp_holder["response"] = session.request(method, url, **kwargs)
            except BaseException as exc:  # noqa: BLE001  原样传回主线程
                exc_holder.append(exc)
            finally:
                done_event.set()

        thread = threading.Thread(target=_worker, name="TEManApiRequest", daemon=True)
        thread.start()
        global_start = time.monotonic()
        budget_deadline = global_start + connect_timeout + read_timeout
        while not done_event.wait(0.2):
            try:
                self._ensure_not_interrupted(interrupt_checker)
            except BaseException:
                session.close()
                raise
            now = time.monotonic()
            if now >= budget_deadline:
                session.close()
                elapsed = now - global_start
                if elapsed <= connect_timeout:
                    raise TimeoutError(
                        "连接阶段耗时过长或无法建立，请检查代理 / DNS 或 Base URL 域名是否可达"
                    )
                raise TimeoutError("模型响应过慢，超过读取时间上限")
        thread.join(timeout=1.0)
        if exc_holder:
            raise exc_holder[0]
        response = resp_holder.get("response")
        if response is None:
            raise RuntimeError("请求被中断或未获得响应")
        return response

    def _interruptible_post(
        self,
        session: Any,
        url: str,
        *,
        json_payload: Any = None,
        data: Any = None,
        files: Any = None,
        headers: Any = None,
        timeout: Any = None,
        interrupt_checker: Any = None,
    ) -> Any:
        """可中断 POST：支持 JSON 模式 payload(bytes) 与 Multipart 模式。"""
        return self._interruptible_request(
            session,
            "POST",
            url,
            json_payload=json_payload,
            data=data,
            files=files,
            headers=headers,
            timeout=timeout,
            interrupt_checker=interrupt_checker,
        )

    def _interruptible_stream_post(
        self,
        session: Any,
        url: str,
        *,
        json_payload: Any = None,
        headers: Any = None,
        timeout: Any = None,
        interrupt_checker: Any = None,
    ) -> Any:
        """可中断流式 POST（SSE）。"""
        return self._interruptible_request(
            session,
            "POST",
            url,
            json_payload=json_payload,
            headers=headers,
            timeout=timeout,
            interrupt_checker=interrupt_checker,
            stream=True,
        )

    def _interruptible_get(
        self,
        session: Any,
        url: str,
        *,
        headers: Any = None,
        timeout: Any = None,
        interrupt_checker: Any = None,
    ) -> Any:
        """可中断 GET（轮询/下载/余额查询）。"""
        return self._interruptible_request(
            session,
            "GET",
            url,
            headers=headers,
            timeout=timeout,
            interrupt_checker=interrupt_checker,
        )

    # ==================== 错误摘要（spec §3.5 / §5） ====================
    _FEE_DETAIL_RE = re.compile(r"request[_ -]?id|trace[_ -]?id", re.IGNORECASE)

    def _summarize_error_response(self, status_code: Any, response_text: Any = "") -> str:
        """提取对用户安全的错误摘要，避免暴露源站费用或请求 ID 等细节。"""
        status = status_code if status_code is not None else 0
        text = str(response_text or "")
        lowered = text.lower()
        if (
            status == 402
            or "余额不足" in text
            or "insufficient" in lowered
            or "quota exceeded" in lowered
            or "欠费" in text
        ):
            return "余额不足：账户额度不足以完成本次请求，请充值后重试"
        if status in (401, 403):
            return "API Key 无效或已过期"
        message = ""
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                error = payload.get("error")
                if isinstance(error, dict):
                    message = str(error.get("message") or error.get("code") or "")
                elif error is not None:
                    message = str(error)
                if not message:
                    message = str(payload.get("message") or "")
            elif isinstance(payload, str):
                message = payload
        except (ValueError, TypeError):
            message = text
        # 去除 URL 与请求 ID 等细节
        message = _BARE_URL_RE.sub("[URL]", message)
        message = self._FEE_DETAIL_RE.sub("[id]", message)
        message = _sanitize_text_payload(message, 200).strip()
        if message:
            return f"远端返回异常（HTTP {status}）: {message}"
        return f"远端返回异常（HTTP {status}）"

    @staticmethod
    def _is_broken_stream_error(exc: BaseException) -> bool:
        """断流判定：ChunkedEncoding/Protocol/Connection 异常及报错文本匹配。"""
        try:
            import requests
            from requests.exceptions import (
                ChunkedEncodingError,
                ConnectionError as RequestsConnectionError,
                ProtocolError,
            )

            if isinstance(exc, (ChunkedEncodingError, ProtocolError, RequestsConnectionError)):
                return True
        except Exception:  # noqa: BLE001  requests 不可用时仅做文本匹配
            pass
        text = str(exc).lower().replace(" ", "").replace("-", "")
        return bool(_BROKEN_STREAM_TEXT_RE.search(text))

    @staticmethod
    def _exception_type_name(exc: BaseException) -> str:
        return type(exc).__name__

    # ==================== SSE 原语（spec §3.7） ====================
    def _iter_json_objects_from_text(self, payload_text: Any) -> Iterable[Dict[str, Any]]:
        """JSONDecoder.raw_decode 松散抽取 JSON 对象（处理非标准流）。"""
        decoder = json.JSONDecoder()
        text = str(payload_text or "")
        index = 0
        length = len(text)
        while index < length:
            brace = text.find("{", index)
            if brace < 0:
                break
            try:
                obj, end = decoder.raw_decode(text, brace)
                if isinstance(obj, dict):
                    yield obj
                index = end
            except ValueError:
                index = brace + 1

    @staticmethod
    def _decode_stream_line(raw_line: Any) -> str:
        if raw_line is None:
            return ""
        if isinstance(raw_line, bytes):
            return raw_line.decode("utf-8", "replace")
        return str(raw_line)

    @staticmethod
    def _append_stream_text(state: Dict[str, Any], text: Any) -> None:
        if text:
            state["text"].append(str(text))

    @staticmethod
    def _append_image_once(state: Dict[str, Any], b64_data: Any, seen: set) -> None:
        if not b64_data:
            return
        normalized = re.sub(r"\s+", "", str(b64_data))
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        state["images"].append(normalized)

    def _append_stream_image_candidate(
        self, state: Dict[str, Any], b64_data: Any
    ) -> None:
        """流式图像候选去重收集（seen_images 去重）。"""
        self._append_image_once(state, b64_data, state.setdefault("seen_images", set()))

    # ---- Gemini 流 ----
    def _consume_gemini_stream_event(
        self, event_text: str, state: Dict[str, Any]
    ) -> None:
        if not event_text:
            return
        # [DONE] 终止符可能与其他数据行合入同一次 flush，先剥离再解析
        if "[DONE]" in event_text:
            state["done"] = True
            event_text = event_text.replace("[DONE]", " ")
            if not event_text.strip():
                return
        for event in self._iter_json_objects_from_text(event_text):
            state["raw_events"].append(event)
            if event.get("error"):
                raise RuntimeError(
                    self._summarize_error_response(200, json.dumps(event, ensure_ascii=False))
                )
            feedback = event.get("promptFeedback")
            if isinstance(feedback, dict) and feedback.get("blockReason"):
                raise RuntimeError(
                    f"请求被安全策略拦截: {feedback.get('blockReason')}"
                )
            for key in ("usageMetadata", "modelVersion", "responseId"):
                if event.get(key):
                    state[key] = event[key]
            for candidate in event.get("candidates") or []:
                if candidate.get("finishReason"):
                    state["finish_reason"] = candidate["finishReason"]
                content = candidate.get("content") or {}
                for part in content.get("parts") or []:
                    inline = part.get("inlineData") or {}
                    if inline.get("data"):
                        self._append_stream_image_candidate(state, inline["data"])
                        continue
                    file_data = part.get("fileData") or {}
                    uri = file_data.get("fileUri")
                    if uri:
                        state.setdefault("file_urls", []).append(uri)
                    elif part.get("text"):
                        self._append_stream_text(state, part["text"])

    def _flush_gemini_event(
        self, data_lines: List[str], state: Dict[str, Any]
    ) -> None:
        if not data_lines:
            return
        self._consume_gemini_stream_event("\n".join(data_lines), state)
        data_lines.clear()

    @staticmethod
    def _has_final_image_result(state: Dict[str, Any]) -> bool:
        return bool(state.get("images"))

    def _build_aggregated_gemini_stream_result(
        self, state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """聚合为 generateContent 兼容结构（extract_content 可直接解析）。"""
        parts: List[Dict[str, Any]] = []
        for image in state.get("images", []):
            parts.append(
                {"inlineData": {"mimeType": "image/png", "data": image}}
            )
        text = "".join(state.get("text", []))
        if text:
            parts.append({"text": text})
        result: Dict[str, Any] = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": parts},
                    "finishReason": state.get("finish_reason") or "STOP",
                }
            ],
        }
        for key in ("usageMetadata", "modelVersion", "responseId"):
            if state.get(key):
                result[key] = state[key]
        # 流聚合原始事件（调试与下游回放用）
        result["rawEvents"] = state.get("raw_events", [])
        result["streamFileUrls"] = list(state.get("file_urls", []))
        return result

    def _parse_gemini_stream_response(self, response: Any) -> Dict[str, Any]:
        """消费 Gemini SSE 流并聚合（断流但已有内容时使用已聚合结果）。"""
        state: Dict[str, Any] = {
            "raw_events": [],
            "images": [],
            "text": [],
            "seen_images": set(),
            "file_urls": [],
            "done": False,
        }
        data_lines: List[str] = []
        try:
            for raw_line in response.iter_lines(decode_unicode=False):
                line = self._decode_stream_line(raw_line)
                if not line.strip():
                    self._flush_gemini_event(data_lines, state)
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
                elif line.startswith("event:") or line.startswith(":"):
                    continue
                else:
                    data_lines.append(line.strip())
            self._flush_gemini_event(data_lines, state)
        except Exception as exc:  # noqa: BLE001
            if self._is_broken_stream_error(exc):
                # 断流时先冲刷尚未成事件的 data 行，避免丢失已收到的有效内容
                try:
                    self._flush_gemini_event(data_lines, state)
                except Exception:  # noqa: BLE001
                    pass
                if self._has_final_image_result(state) or state["text"]:
                    _log_warning(
                        "Gemini 流式响应尾部异常断开，但已收到有效内容，将继续使用已聚合结果"
                    )
                    return self._build_aggregated_gemini_stream_result(state)
                raise
            raise
        return self._build_aggregated_gemini_stream_result(state)

    # ---- Chat 流 ----
    def _collect_stream_chat_parts(self, event: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        """genexpr 逐个产出 choices[0] 的 delta / message 片段。"""
        choices = event.get("choices") or []
        first = choices[0] if choices else {}
        for part in (first.get("delta"), first.get("message")):
            if isinstance(part, dict):
                yield part

    def _consume_chat_stream_event(
        self, event_text: str, state: Dict[str, Any]
    ) -> None:
        if not event_text:
            return
        # [DONE] 终止符可能与其他数据行合入同一次 flush，先剥离再解析
        if "[DONE]" in event_text:
            state["done"] = True
            event_text = event_text.replace("[DONE]", " ")
            if not event_text.strip():
                return
        for event in self._iter_json_objects_from_text(event_text):
            state["raw_events"].append(event)
            if event.get("error"):
                raise RuntimeError(
                    self._summarize_error_response(200, json.dumps(event, ensure_ascii=False))
                )
            for part in self._collect_stream_chat_parts(event):
                content = part.get("content")
                if isinstance(content, str) and content:
                    self._append_stream_text(state, content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("text"):
                            self._append_stream_text(state, item["text"])
                images = part.get("images")
                if isinstance(images, (list, tuple)):
                    for image in images:
                        if isinstance(image, str):
                            self._append_stream_image_candidate(state, image)
                inline = part.get("inlineData") or {}
                if inline.get("data"):
                    self._append_stream_image_candidate(state, inline["data"])

    def _flush_chat_event(self, data_lines: List[str], state: Dict[str, Any]) -> None:
        if not data_lines:
            return
        self._consume_chat_stream_event("\n".join(data_lines), state)
        data_lines.clear()

    def _build_aggregated_stream_result(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """聚合为统一 chat.completions 结构。"""
        text = "".join(state.get("text", []))
        finish = state.get("finish_reason") or ("stop" if state.get("done") else None)
        result: Dict[str, Any] = {
            "object": "chat.completions",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": text,
                        "images": list(state.get("images", [])),
                    },
                    "finish_reason": finish or "stop",
                }
            ],
            "rawEvents": state.get("raw_events", []),
        }
        if state.get("usage"):
            result["usage"] = state["usage"]
        return result

    def _parse_chat_stream_response(self, response: Any) -> Dict[str, Any]:
        """消费 Chat SSE 流并聚合。"""
        state: Dict[str, Any] = {
            "raw_events": [],
            "images": [],
            "text": [],
            "seen_images": set(),
            "done": False,
            "finish_reason": None,
        }
        data_lines: List[str] = []
        try:
            for raw_line in response.iter_lines(decode_unicode=False):
                line = self._decode_stream_line(raw_line)
                if not line.strip():
                    self._flush_chat_event(data_lines, state)
                    continue
                if line.startswith("data:"):
                    data_lines.append(line[len("data:"):].strip())
                elif line.startswith("event:") or line.startswith(":"):
                    continue
                else:
                    data_lines.append(line.strip())
            self._flush_chat_event(data_lines, state)
        except Exception as exc:  # noqa: BLE001
            if self._is_broken_stream_error(exc):
                # 断流时先冲刷尚未成事件的 data 行，避免丢失已收到的有效内容
                try:
                    self._flush_chat_event(data_lines, state)
                except Exception:  # noqa: BLE001
                    pass
                if self._has_final_image_result(state) or state["text"]:
                    _log_warning(
                        "流式响应尾部异常断开，但已收到有效内容，将继续使用已聚合结果"
                    )
                    return self._build_aggregated_stream_result(state)
                raise
            raise
        return self._build_aggregated_stream_result(state)

    # ==================== Gemini 原生协议（spec §3.4） ====================
    def send_request(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        model: str,
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
        max_retries: Any = None,
    ) -> Dict[str, Any]:
        """Gemini generateContent 同步请求，带重试与限流退避。"""
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        url = self._build_generate_content_url(base_url, model)
        headers = self._build_headers(key)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        try:
            effective_max_retries = self._MAX_RETRIES if max_retries is None else int(max_retries)
        except (TypeError, ValueError):
            effective_max_retries = self._MAX_RETRIES
        last_error: Optional[str] = None
        for attempt in range(max(1, effective_max_retries)):
            try:
                self._ensure_not_interrupted(interrupt_checker)
                response = self._interruptible_post(
                    session,
                    url,
                    json_payload=request_data,
                    headers=headers,
                    timeout=timeout,
                    interrupt_checker=interrupt_checker,
                )
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, TimeoutError) and "连接阶段" in str(exc):
                    raise
                if isinstance(exc, TimeoutError):
                    raise TimeoutError(f"{exc}（已重试 {attempt + 1} 次）")
                last_error = f"{self._exception_type_name(exc)}: {_sanitize_text_payload(exc, 200)}"
                _log_warning(f"网络连接失败: {_shorten_url_for_log(_sanitize_text_payload(exc, 200))}")
                attempt_delay = self._BASE_BACKOFF * (2 ** attempt)
                time.sleep(attempt_delay)
                continue
            status_code = getattr(response, "status_code", 0)
            if status_code in self._RETRYABLE_STATUS:
                if status_code == 429:
                    _log_warning("请求限流，延长等待时间")
                else:
                    _log_warning(self._summarize_error_response(status_code, getattr(response, "text", "")))
                time.sleep(self._BASE_BACKOFF * (2 ** attempt))
                continue
            if status_code >= 400:
                raise RuntimeError(
                    self._summarize_error_response(status_code, getattr(response, "text", ""))
                )
            try:
                return response.json()
            except ValueError:
                _log_warning(
                    f"content 前 300 字符预览: {_sanitize_text_payload(getattr(response, 'text', ''), 300)}"
                )
                raise RuntimeError("接口返回数据格式异常")
        raise RuntimeError(
            f"{self._exception_type_name(RuntimeError(last_error or 'HTTPError'))} "
            f"{effective_max_retries} 次请求失败（错误类型：{last_error or 'HTTPError'}），"
            "请检查 API 服务与网络状态，或联系服务提供者"
        )

    def send_stream_request(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        model: str,
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
        stream_parser: Any = None,
    ) -> Dict[str, Any]:
        """Gemini streamGenerateContent SSE 流式请求（断流按 Connection: close 重试）。"""
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        url = self._build_stream_generate_content_url(base_url, model)
        headers = self._build_headers(key, stream=True)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        parser = stream_parser or self._parse_gemini_stream_response
        last_error: Optional[BaseException] = None
        for attempt in range(2):  # 首次 + Connection: close 重试一次
            retry_headers = dict(headers)
            retry_broken_stream = attempt == 1
            if retry_broken_stream:
                retry_headers["Connection"] = "close"
            try:
                response = self._interruptible_stream_post(
                    session,
                    url,
                    json_payload=request_data,
                    headers=retry_headers,
                    timeout=timeout,
                    interrupt_checker=interrupt_checker,
                )
                status_code = getattr(response, "status_code", 0)
                if status_code >= 400:
                    raise RuntimeError(
                        self._summarize_error_response(
                            status_code, getattr(response, "text", "")
                        )
                    )
                return parser(response)
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                if not self._is_broken_stream_error(exc) or retry_broken_stream:
                    if attempt == 0:
                        # 非断流错误：一次机会内不再重试，直接抛出带前缀的错误
                        raise RuntimeError(f"Gemini Stream API 请求失败: {_sanitize_text_payload(exc, 300)}") from exc
                    raise
                last_error = exc
                _log_warning(
                    f"流式传输异常断开，尝试使用 Connection: close 重试一次 "
                    f"（{_sanitize_text_payload(exc, 160)}）"
                )
                continue
        raise RuntimeError(f"Gemini Stream API 请求失败: {_sanitize_text_payload(last_error, 300)}")

    # ==================== OpenAI 兼容图像协议（spec §3.4） ====================
    @staticmethod
    def _extract_task_id(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        data = payload.get("data")
        for node in (data if isinstance(data, dict) else None, payload):
            if isinstance(node, dict):
                for key in ("task_id", "taskId", "id"):
                    value = node.get(key)
                    if value:
                        return str(value)
        return ""

    def send_openai_request(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        files: Any = None,
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        webhook: Any = None,
        interrupt_checker: Any = None,
    ) -> str:
        """OpenAI 兼容图像请求：返回 task_id（异步任务ID）。

        text2img → ``POST /v1/images/generations``（JSON）；
        img2img → ``POST /v1/images/edits``（multipart files）。
        """
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        is_multipart = bool(files)
        endpoint = "/v1/images/edits" if is_multipart else "/v1/images/generations"
        url = f"{self._join_base(base_url)}{endpoint}"
        headers = self._build_headers(key, content_json=not is_multipart)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        payload = dict(request_data) if request_data else {}
        if webhook and is_multipart and "webhook" not in payload:
            payload["webhook"] = webhook
        try:
            response = self._interruptible_post(
                session,
                url,
                json_payload=None if is_multipart else payload,
                data=payload if is_multipart else None,
                files=files if is_multipart else None,
                headers=headers,
                timeout=timeout,
                interrupt_checker=interrupt_checker,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"网络连接失败: {_sanitize_text_payload(exc, 200)}") from exc
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(
                self._summarize_error_response(status_code, getattr(response, "text", ""))
            )
        try:
            body = response.json()
        except ValueError:
            _log_warning(
                f"content 前 300 字符预览: {_sanitize_text_payload(getattr(response, 'text', ''), 300)}"
            )
            raise RuntimeError("接口返回数据格式异常")
        task_id = self._extract_task_id(body)
        if not task_id:
            raise RuntimeError("API 未返回 task_id")
        return task_id

    def _poll_task_once(
        self,
        session: Any,
        status_url: str,
        headers: Dict[str, str],
        timeout: Any,
        interrupt_checker: Any,
        prefix: str,
    ) -> Tuple[Any, Dict[str, Any]]:
        """单次轮询 GET：异常/限流/格式错误按 spec 文案抛 RuntimeError。"""
        try:
            response = self._interruptible_get(
                session,
                status_url,
                headers=headers,
                timeout=timeout,
                interrupt_checker=interrupt_checker,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"{prefix}轮询异常: {_sanitize_text_payload(exc, 200)}"
            ) from exc
        status_code = getattr(response, "status_code", 0)
        if status_code == 429:
            raise _PollRateLimited("轮询请求限流，延长等待时间")
        if status_code >= 400:
            if status_code == 401 or status_code == 403:
                raise RuntimeError("API Key 无效或已过期")
            raise ValueError(
                self._summarize_error_response(status_code, getattr(response, "text", ""))
            )
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError("轮询返回数据格式异常")
        if not isinstance(body, dict):
            raise RuntimeError("轮询返回数据格式异常")
        return response, body

    def poll_openai_task(
        self,
        api_key: Any,
        task_id: str,
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        max_poll_attempts: Any = None,
        poll_interval: Any = None,
        interrupt_checker: Any = None,
    ) -> Dict[str, Any]:
        """轮询 OpenAI 图像任务直至完成，返回完整任务响应数据（status/data 等）。"""
        if not task_id:
            raise ValueError("未提供有效的任务 ID")
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        try:
            attempts = int(max_poll_attempts) if max_poll_attempts is not None else self._DEFAULT_POLL_ATTEMPTS
        except (TypeError, ValueError):
            attempts = self._DEFAULT_POLL_ATTEMPTS
        try:
            interval = float(poll_interval) if poll_interval is not None else self._DEFAULT_POLL_INTERVAL
        except (TypeError, ValueError):
            interval = self._DEFAULT_POLL_INTERVAL
        status_url = self._status_endpoint(base_url, task_id, "image")
        headers = self._build_headers(key, content_json=False)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        wait = interval
        for attempt in range(1, max(1, attempts) + 1):
            try:
                self._ensure_not_interrupted(interrupt_checker)
                _, body = self._poll_task_once(
                    session,
                    status_url,
                    headers,
                    timeout,
                    interrupt_checker,
                    "",
                )
            except _PollRateLimited:
                wait = min(wait * 2.0, 30.0)
                _log_warning("轮询请求限流，延长等待时间")
                time.sleep(wait)
                continue
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc
            except RuntimeError as exc:
                _log_warning(f"轮询异常 (尝试 {attempt}/{attempts}): {_sanitize_text_payload(exc, 200)}")
                time.sleep(min(wait * 1.5, 30.0))
                continue
            status = self._extract_task_status(body)
            if status in self._OPENAI_TASK_DONE:
                return body
            if status in self._OPENAI_TASK_FAILED:
                raise RuntimeError(
                    self._summarize_task_failure(body, "任务失败")
                )
            if attempt % 10 == 0:
                _log_info(f"任务仍在处理中 (尝试 {attempt}/{attempts}, status={status or 'unknown'})")
            time.sleep(wait)
        raise TimeoutError(f"任务超时: 超过 {attempts} 次轮询仍未完成")

    @staticmethod
    def _extract_task_status(body: Dict[str, Any]) -> str:
        if not isinstance(body, dict):
            return ""
        data = body.get("data")
        for node in (data if isinstance(data, dict) else None, body):
            if isinstance(node, dict):
                status = node.get("status") or node.get("state") or node.get("phase")
                if status:
                    return str(status)
        return ""

    @staticmethod
    def _extract_task_failure_detail(body: Dict[str, Any]) -> str:
        if not isinstance(body, dict):
            return ""
        for node in (body.get("data") if isinstance(body.get("data"), dict) else None, body):
            if isinstance(node, dict):
                for key in ("error", "message", "detail", "reason"):
                    value = node.get(key)
                    if value:
                        return str(value)
        return ""

    def _summarize_task_failure(self, body: Dict[str, Any], fallback: str) -> str:
        """任务失败的用户安全摘要：余额问题识别 + 细节打码。"""
        detail = self._extract_task_failure_detail(body)
        lowered = detail.lower()
        if (
            detail
            and (
                "余额不足" in detail
                or "insufficient" in lowered
                or "quota exceeded" in lowered
                or "欠费" in detail
            )
        ):
            return "余额不足：账户额度不足以完成本次请求，请充值后重试"
        summary = re.sub(_BARE_URL_RE.pattern, "[URL]", detail) if detail else ""
        summary = _sanitize_text_payload(summary, 160).strip()
        if summary:
            return f"{fallback}: {summary}"
        return fallback

    # ==================== 视频协议（spec 附录 + 任务说明） ====================
    def send_video_request(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
    ) -> str:
        """提交视频生成（POST /v1/videos），返回 task_id。"""
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        url = f"{self._join_base(base_url)}/v1/videos"
        headers = self._build_headers(key)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        try:
            response = self._interruptible_post(
                session,
                url,
                json_payload=request_data,
                headers=headers,
                timeout=timeout,
                interrupt_checker=interrupt_checker,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"/v1/videos 请求失败: {_sanitize_text_payload(exc, 200)}") from exc
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(
                self._summarize_error_response(status_code, getattr(response, "text", ""))
            )
        try:
            body = response.json()
        except ValueError:
            raise RuntimeError("接口返回数据格式异常")
        task_id = self._extract_task_id(body)
        if not task_id:
            raise RuntimeError("API 未返回 task_id")
        return task_id

    def poll_video_task(
        self,
        api_key: Any,
        task_id: str,
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        max_poll_attempts: Any = None,
        poll_interval: Any = None,
        interrupt_checker: Any = None,
    ) -> Dict[str, Any]:
        """轮询视频任务（GET /v1/videos/{task_id}），完成态返回完整响应。"""
        if not task_id:
            raise ValueError("未提供有效的任务 ID")
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        try:
            attempts = int(max_poll_attempts) if max_poll_attempts is not None else self._VIDEO_POLL_ATTEMPTS
        except (TypeError, ValueError):
            attempts = self._VIDEO_POLL_ATTEMPTS
        try:
            interval = float(poll_interval) if poll_interval is not None else self._VIDEO_POLL_INTERVAL
        except (TypeError, ValueError):
            interval = self._VIDEO_POLL_INTERVAL
        status_url = self._status_endpoint(base_url, task_id, "video")
        headers = self._build_headers(key, content_json=False)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        wait = interval
        for attempt in range(1, max(1, attempts) + 1):
            try:
                self._ensure_not_interrupted(interrupt_checker)
                _, body = self._poll_task_once(
                    session,
                    status_url,
                    headers,
                    timeout,
                    interrupt_checker,
                    "/v1/videos ",
                )
            except _PollRateLimited:
                wait = min(wait * 2.0, 60.0)
                _log_warning("/v1/videos 轮询请求限流，延长等待时间")
                time.sleep(wait)
                continue
            except ValueError as exc:
                raise RuntimeError(str(exc)) from exc
            except RuntimeError as exc:
                _log_warning(
                    f"/v1/videos 轮询异常 (尝试 {attempt}/{attempts}): {_sanitize_text_payload(exc, 200)}"
                )
                time.sleep(min(wait * 1.5, 60.0))
                continue
            status = self._extract_task_status(body)
            if attempt % 10 == 0:
                _log_info(f"/v1/videos 任务状态: {status or 'unknown'} (尝试 {attempt}/{attempts})")
            if not status:
                time.sleep(wait)
                continue
            lowered = status.lower()
            if lowered in self._VIDEO_DONE:
                return body
            if lowered in self._VIDEO_FAILED:
                raise RuntimeError(
                    self._summarize_task_failure(body, f"/v1/videos 任务状态: {status}")
                )
            time.sleep(wait)
        raise TimeoutError(f"/v1/videos 轮询超时 (尝试 {attempts})")

    @staticmethod
    def _find_video_url(node: Any) -> str:
        """递归在响应中查找视频 URL。"""
        if isinstance(node, dict):
            for key in ("video_url", "videoUrl", "download_url", "downloadUrl", "url", "video"):
                value = node.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    return value
                if isinstance(value, str) and key in ("video",) and value.startswith("data:"):
                    return value
            for value in node.values():
                found = GeminiApiClient._find_video_url(value)
                if found:
                    return found
        elif isinstance(node, (list, tuple)):
            for item in node:
                found = GeminiApiClient._find_video_url(item)
                if found:
                    return found
        return ""

    def extract_video_content(self, response_data: Any) -> Tuple[str, str]:
        """提取视频内容：返回 (video_url, text)。"""
        text = ""
        if isinstance(response_data, dict):
            text = str(response_data.get("text") or response_data.get("message") or "")
        video_url = self._find_video_url(response_data)
        if not video_url:
            raise RuntimeError("响应中无视频地址")
        return video_url, text

    def download_video_content(
        self,
        api_key: Any,
        video_url: str,
        save_path: str,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
    ) -> str:
        """流式下载视频到指定路径。"""
        if not video_url:
            raise ValueError("响应中无视频地址")
        key = str(api_key or self._get_api_key())
        headers = self._build_headers(key, content_json=False)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        started_at = time.monotonic()
        try:
            response = self._interruptible_get(
                session,
                video_url,
                headers=headers,
                timeout=timeout,
                interrupt_checker=interrupt_checker,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"下载视频失败: {_sanitize_text_payload(exc, 200)}") from exc
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(f"下载失败，状态码: {status_code}")
        import os

        directory = os.path.dirname(os.path.abspath(save_path))
        os.makedirs(directory, exist_ok=True)
        total = 0
        try:
            with open(save_path, "wb") as handle:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    handle.write(chunk)
                    total += len(chunk)
        except OSError as exc:
            raise RuntimeError(f"下载视频失败: {exc}") from exc
        elapsed = time.monotonic() - started_at
        _log_success(f"成功下载视频，大小: {total} 字节，耗时 {elapsed:.1f}s → {save_path}")
        return save_path

    # ==================== Chat 协议（spec §3.4 / §3.8） ====================
    def send_chat_request(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
        max_retries: Any = None,
        download_images: bool = True,
    ) -> Tuple[List[str], str]:
        """Chat Completions 同步请求，返回 (images_b64, text)。"""
        payload = self.send_http_chat_request(
            api_key,
            request_data,
            api_base_url=api_base_url,
            timeout=timeout,
            bypass_proxy=bypass_proxy,
            verify_ssl=verify_ssl,
            interrupt_checker=interrupt_checker,
            max_retries=max_retries,
        )
        return self.extract_chat_content(
            payload,
            download_images=download_images,
            api_key=api_key,
            bypass_proxy=bypass_proxy,
            verify_ssl=verify_ssl,
        )

    def send_http_chat_request(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
        max_retries: Any = None,
    ) -> Dict[str, Any]:
        """Chat Completions 同步请求原样返回响应 JSON。"""
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        url = self._build_chat_completions_url(base_url)
        headers = self._build_headers(key, stream=bool(request_data.get("stream")))
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        try:
            effective_max_retries = self._MAX_RETRIES if max_retries is None else int(max_retries)
        except (TypeError, ValueError):
            effective_max_retries = self._MAX_RETRIES
        last_error: Optional[str] = None
        for attempt in range(max(1, effective_max_retries)):
            try:
                self._ensure_not_interrupted(interrupt_checker)
                response = self._interruptible_post(
                    session,
                    url,
                    json_payload=request_data,
                    headers=headers,
                    timeout=timeout,
                    interrupt_checker=interrupt_checker,
                )
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                if isinstance(exc, TimeoutError) and "连接阶段" in str(exc):
                    raise
                if isinstance(exc, TimeoutError):
                    raise TimeoutError(f"{exc}（已重试 {attempt + 1} 次）")
                last_error = f"{self._exception_type_name(exc)}: {_sanitize_text_payload(exc, 200)}"
                _log_warning(f"网络连接失败: {_sanitize_text_payload(exc, 200)}")
                time.sleep(self._BASE_BACKOFF * (2 ** attempt))
                continue
            status_code = getattr(response, "status_code", 0)
            if status_code in self._RETRYABLE_STATUS:
                if status_code == 429:
                    _log_warning("请求限流，延长等待时间")
                time.sleep(self._BASE_BACKOFF * (2 ** attempt))
                continue
            if status_code >= 400:
                raise RuntimeError(
                    self._summarize_error_response(status_code, getattr(response, "text", ""))
                )
            try:
                payload = response.json()
            except ValueError:
                _log_warning(
                    f"content 前 300 字符预览: {_sanitize_text_payload(getattr(response, 'text', ''), 300)}"
                )
                raise RuntimeError("接口返回数据格式异常")
            if not isinstance(payload, dict) or not payload.get("choices"):
                raise RuntimeError("响应中无 choices 数据")
            return payload
        raise RuntimeError(
            f"{effective_max_retries} 次请求失败（错误类型：{last_error or 'HTTPError'}），"
            "请检查 API 服务与网络状态，或联系服务提供者"
        )

    def _download_url_to_b64(
        self,
        url: str,
        api_key: Any = None,
        timeout: Any = None,
        source: str = "markdown",
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
    ) -> str:
        """下载图片 URL → base64（Content-Type 校验 + 耗时日志）。"""
        label_fetch = "Gemini 图片URL" if source == "gemini" else "Markdown 图片URL"
        label_done = "Gemini 图片" if source == "gemini" else "Markdown 图片"
        _log_info(f"收到 {label_fetch}，开始下载: {_shorten_url_for_log(url)}")
        key = str(api_key or self._get_api_key())
        headers = self._build_headers(key, content_json=False)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        download_started_at = time.monotonic()
        try:
            response = self._interruptible_get(
                session,
                url,
                headers=headers,
                timeout=timeout,
                interrupt_checker=interrupt_checker,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"下载图片失败: {_sanitize_text_payload(exc, 200)}") from exc
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(f"下载失败，状态码: {status_code}")
        content_type = (getattr(response, "headers", {}) or {}).get("Content-Type", "")
        if content_type and not content_type.lower().startswith("image/"):
            raise RuntimeError(f"下载内容疑似非图片: Content-Type={content_type}")
        image_bytes = b"".join(
            chunk for chunk in response.iter_content(chunk_size=64 * 1024) if chunk
        )
        elapsed = time.monotonic() - download_started_at
        _log_success(
            f"成功下载图片，大小: {len(image_bytes)} 字节"
            f"（{label_done}下载完成，耗时 {elapsed:.1f}s）"
        )
        return base64.b64encode(image_bytes).decode("ascii")

    def extract_chat_content(
        self,
        response_data: Any,
        download_images: bool = True,
        api_key: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
    ) -> Tuple[List[str], str]:
        """Chat 响应 → (images_b64, text)，含 URL 图像下载。"""
        images: List[str] = []
        texts: List[str] = []

        def _append_b64(value: Any) -> None:
            if not value:
                return
            normalized = re.sub(r"\s+", "", str(value))
            if normalized and normalized not in images:
                images.append(normalized)

        def _download_url_to_b64(url: str) -> str:
            return self._download_url_to_b64(
                url,
                api_key=api_key,
                source="markdown",
                bypass_proxy=bypass_proxy,
                verify_ssl=verify_ssl,
            )

        def _extract_from_text(text: str) -> None:
            matched_urls: List[str] = []
            for pattern in (_MARKDOWN_IMAGE_RE, _MARKDOWN_LINK_RE, _HTML_IMG_RE, _BARE_URL_RE):
                matched_urls.extend(pattern.findall(text))
            for url in matched_urls:
                url = url.strip()
                if url.startswith("data:image/") and ";base64," in url:
                    _append_b64(url.split(";base64,", 1)[1])
                    continue
                if not url.startswith(("http://", "https://")):
                    continue
                if download_images:
                    try:
                        _append_b64(_download_url_to_b64(url))
                    except Exception as e:  # noqa: BLE001
                        _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")

        choices = response_data.get("choices") if isinstance(response_data, dict) else None
        if isinstance(choices, list):
            for choice in choices:
                message = choice.get("message") or {}
                for image in message.get("images") or []:
                    if isinstance(image, str):
                        if image.startswith("data:image/") and ";base64," in image:
                            _append_b64(image.split(";base64,", 1)[1])
                        elif image.startswith(("http://", "https://")):
                            if download_images:
                                try:
                                    _append_b64(_download_url_to_b64(image))
                                except Exception as e:  # noqa: BLE001
                                    _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")
                        else:
                            _append_b64(image)
                for item in message.get("content") if isinstance(message.get("content"), list) else []:
                    if isinstance(item, dict):
                        inline = item.get("inlineData") or item.get("image") or {}
                        if isinstance(inline, dict):
                            if inline.get("data"):
                                _append_b64(inline["data"])
                            elif inline.get("url") and download_images:
                                try:
                                    _append_b64(_download_url_to_b64(str(inline["url"])))
                                except Exception as e:  # noqa: BLE001
                                    _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")
                content = message.get("content")
                if isinstance(content, str) and content:
                    texts.append(content)
        content = response_data.get("content") if isinstance(response_data, dict) else None
        if isinstance(content, str):
            texts.append(content)
        text = "\n".join(part for part in texts if part)
        if not images and text:
            _extract_from_text(text)
        if not images and not text:
            _log_warning("Chat API 响应中未解析到图片")
        return images, text

    def send_chat_request_stream(
        self,
        api_key: Any,
        request_data: Dict[str, Any],
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
        stream_parser: Any = None,
    ) -> Tuple[List[str], str]:
        """Chat Completions SSE 流式请求，聚合后返回 (images_b64, text)。"""
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请填写有效的 API Key")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置有效的 API Base URL")
        payload = dict(request_data) if request_data else {}
        payload["stream"] = True
        url = self._build_chat_completions_url(base_url)
        headers = self._build_headers(key, stream=True)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        parser = stream_parser or self._parse_chat_stream_response
        aggregated: Optional[Dict[str, Any]] = None
        retry_broken_stream = False
        for attempt in range(2):
            retry_headers = dict(headers)
            if retry_broken_stream:
                retry_headers["Connection"] = "close"
            try:
                response = self._interruptible_stream_post(
                    session,
                    url,
                    json_payload=payload,
                    headers=retry_headers,
                    timeout=timeout,
                    interrupt_checker=interrupt_checker,
                )
                status_code = getattr(response, "status_code", 0)
                if status_code >= 400:
                    raise RuntimeError(
                        self._summarize_error_response(
                            status_code, getattr(response, "text", "")
                        )
                    )
                aggregated = parser(response)
                break
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                if (
                    self._is_broken_stream_error(exc)
                    and not retry_broken_stream
                ):
                    retry_broken_stream = True
                    _log_warning("流式传输异常断开，尝试使用 Connection: close 重试一次")
                    continue
                raise RuntimeError(
                    f"Chat Stream API 请求失败: {_sanitize_text_payload(exc, 300)}"
                ) from exc
        if aggregated is None:
            raise RuntimeError("流式请求结束，但未解析到有效响应")
        images, text = self.extract_chat_content(
            aggregated,
            download_images=True,
            api_key=key,
            bypass_proxy=bypass_proxy,
            verify_ssl=verify_ssl,
        )
        finish_reason = ""
        try:
            finish_reason = str(
                (aggregated.get("choices") or [{}])[0].get("finish_reason") or ""
            )
        except Exception:  # noqa: BLE001
            finish_reason = ""
        if not images and not text and finish_reason not in ("stop", "STOP", ""):
            _log_warning(f"Chat API finish_reason={finish_reason}")
        return images, text

    # ==================== Gemini 内容提取（spec §3.8） ====================
    def extract_content(
        self,
        response_data: Any,
        download_images: bool = True,
        api_key: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
    ) -> Tuple[List[str], str]:
        """Gemini 响应 → (images_b64_list, text)。"""
        images: List[str] = []
        texts: List[str] = []
        if not isinstance(response_data, dict):
            raise RuntimeError("接口返回数据格式异常")
        candidates = response_data.get("candidates") or []
        for candidate in candidates:
            if candidate.get("finishReason") and str(candidate["finishReason"]) not in ("STOP", "MAX_LENGTH"):
                _log_warning(f"finishReason={candidate['finishReason']}")
            content = candidate.get("content") or {}
            for part in content.get("parts") or []:
                inline = part.get("inlineData") or {}
                data = inline.get("data")
                if data:
                    normalized = re.sub(r"\s+", "", str(data))
                    if normalized and normalized not in images:
                        images.append(normalized)
                    continue
                file_data = part.get("fileData") or {}
                uri = str(file_data.get("fileUri") or "")
                if uri.startswith(("http://", "https://")) and download_images:
                    try:
                        images.append(
                            self._download_url_to_b64(
                                uri,
                                api_key=api_key,
                                source="gemini",
                                bypass_proxy=bypass_proxy,
                                verify_ssl=verify_ssl,
                            )
                        )
                    except Exception as e:  # noqa: BLE001
                        _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")
                elif part.get("text"):
                    texts.append(str(part["text"]))
        text = "\n".join(texts)
        if not images and text:
            # 文本中的 Markdown 图片 URL → 下载为 base64
            markdown_images = _MARKDOWN_IMAGE_RE.findall(text)
            for url in markdown_images:
                url = url.strip()
                if url.startswith(("http://", "https://")) and download_images:
                    try:
                        images.append(
                            self._download_url_to_b64(
                                url,
                                api_key=api_key,
                                source="markdown",
                                bypass_proxy=bypass_proxy,
                                verify_ssl=verify_ssl,
                            )
                        )
                    except Exception as e:  # noqa: BLE001
                        _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")
        if not images and response_data.get("streamFileUrls"):
            for url in response_data["streamFileUrls"]:
                if url.startswith(("http://", "https://")) and download_images:
                    try:
                        images.append(
                            self._download_url_to_b64(
                                url,
                                api_key=api_key,
                                source="gemini",
                                bypass_proxy=bypass_proxy,
                                verify_ssl=verify_ssl,
                            )
                        )
                    except Exception as e:  # noqa: BLE001
                        _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")
        if not images:
            _log_warning("响应中无图像数据")
        return images, text

    def extract_openai_content(
        self,
        response_data: Any,
        download_images: bool = True,
        api_key: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
    ) -> Tuple[List[str], str]:
        """OpenAI 兼容响应 → (images_b64, text)。

        结构（docstring 原文）：
        ``"data": {"status": "SUCCESS", "data": {"data": [{"url": ..., "b64_json": ...}]}}``
        """
        images: List[str] = []
        texts: List[str] = []
        node = response_data if isinstance(response_data, dict) else {}
        data = node.get("data")
        inner = data if isinstance(data, dict) else node
        items: List[Any] = []
        inner_data = inner.get("data") if isinstance(inner, dict) else None
        if isinstance(inner_data, list):
            items = inner_data
        elif isinstance(inner_data, dict):
            # docstring 结构：data.data.data 为条目列表（多包一层）
            nested = inner_data.get("data")
            if isinstance(nested, list):
                items = nested
            else:
                items = [inner_data]
        if not items and isinstance(response_data, dict) and isinstance(response_data.get("data"), list):
            items = response_data["data"]
        for item in items:
            if not isinstance(item, dict):
                continue
            b64 = item.get("b64_json") or item.get("image") or item.get("base64")
            url = item.get("url")
            if b64:
                images.append(re.sub(r"\s+", "", str(b64)))
            elif url and isinstance(url, str):
                if url.startswith("data:image/") and ";base64," in url:
                    images.append(re.sub(r"\s+", "", url.split(";base64,", 1)[1]))
                elif url.startswith(("http://", "https://")):
                    if download_images:
                        try:
                            images.append(
                                self._download_url_to_b64(
                                    url,
                                    api_key=api_key,
                                    source="markdown",
                                    bypass_proxy=bypass_proxy,
                                    verify_ssl=verify_ssl,
                                )
                            )
                        except Exception as e:  # noqa: BLE001
                            _log_warning(f"下载图片失败: {_sanitize_text_payload(e, 200)}")
                else:
                    _log_warning("响应中无图像地址")
            revised = item.get("revised_prompt") or item.get("text")
            if revised:
                texts.append(str(revised))
        return images, "\n".join(texts)

    # ==================== 余额 / Token 用量（spec §3.9） ====================
    def fetch_token_usage(
        self,
        api_key: Any = None,
        api_base_url: Any = None,
        timeout: Any = None,
        bypass_proxy: Any = None,
        verify_ssl: bool = True,
        interrupt_checker: Any = None,
    ) -> Dict[str, Any]:
        """余额查询（GET /api/usage/token 候选，认证头 X-API-Key）。"""
        key = str(api_key or self._get_api_key())
        if not key:
            raise ValueError("请提供有效的 API Key 后再查询余额")
        base_url = self._get_base_url(api_base_url)
        if not base_url:
            raise ValueError("未配置 Balance API 地址")
        headers = self._build_headers(key, auth_mode="x-api-key", content_json=False)
        session = self._get_session(
            bypass_proxy=self._get_bypass_proxy(bypass_proxy), verify_ssl=verify_ssl
        )
        last_summary = ""
        for index, url in enumerate(self._build_balance_urls(base_url)):
            try:
                response = self._interruptible_get(
                    session,
                    url,
                    headers=headers,
                    timeout=timeout,
                    interrupt_checker=interrupt_checker,
                )
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                last_summary = f"网络连接失败: {_sanitize_text_payload(exc, 200)}"
                _log_warning(f"网络连接失败: {_shorten_url_for_log(_sanitize_text_payload(exc, 200))}")
                continue
            status_code = getattr(response, "status_code", 0)
            if status_code == 404:
                last_summary = "404 未找到余额查询端点"
                continue
            if status_code >= 400:
                if status_code in (401, 403):
                    raise ValueError("API Key 无效或已过期")
                last_summary = self._summarize_error_response(
                    status_code, getattr(response, "text", "")
                )
                continue
            try:
                payload = response.json()
            except ValueError:
                raise RuntimeError("余额接口返回格式错误")
            if not isinstance(payload, dict):
                raise RuntimeError("余额接口返回格式错误")
            return payload
        raise RuntimeError(f"余额查询失败，错误摘要: {last_summary}")


# ==================== 模块级单例 ====================

API_CLIENT = GeminiApiClient()
