# -*- coding: utf-8 -*-
"""te_man_open · Grok_Image_Generator（原 Grok_Image_Generator.pyd 的纯 Python 复刻）

ComfyUI 节点：Grok /v1/chat/completions 图像生成
使用 chat.completions + image_config 传递图片生成参数：
- 文生图：model = grok-imagine-image
- 图生图：model = grok-imagine-image-edit
- 尺寸与张数通过 image_config 控制

grok2api typically returns markdown like: ![id](/v1/files/image/xxx) or ![id](https://...)

实现依据 spec/Grok_Image_Generator.md（含动态 introspection 回填节）：
- 端点族 /v1/chat/completions、/v1/images/generations、/v1/images/edits、
  /v1/files/image/（带鉴权下载，四种代理策略回退，LRU 下载缓存容量 16）
- SSE 流解析（data: 块 + [DONE]），markdown/URL/base64 多重正则提取图片
- 多任务并发走 shared.task_runner.BatchGenerationRunner，
  中断经 comfy.model_management 透传
- 失败槽用 shared.image_codec.ErrorCanvas 生成错误图，保证输出不断裂
- requests/torch/numpy/PIL/comfy 全部惰性导入
"""

from __future__ import annotations

import base64
import codecs
import json
import re
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urljoin

from ..shared.config_manager import ConfigManager
from ..shared.image_codec import IMAGE_CODEC, ErrorCanvas
from ..shared.logger import logger
from ..shared.task_runner import BatchGenerationRunner, InterruptProcessingException

__all__ = [
    "BananaGrokImageSafePyNode",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]


# ==================== 模块常量（spec §7.2 动态回填实锤值） ====================

#: 请求 UA（spec §3.6/§4 原文串）
_USER_AGENT = "ComfyUI-TE_API/1.0"

#: 模型名（spec §2 docstring 实锤）
_MODEL_TEXT_TO_IMAGE = "grok-imagine-image"
_MODEL_IMAGE_EDIT = "grok-imagine-image-edit"

#: 输入图缩放（spec §7.2：_MAX_INPUT_IMAGE_MEGAPIXELS=1.0；包装层 _ENABLE_INPUT_IMAGE_AUTOSCALE=False 默认关闭）
_ENABLE_INPUT_IMAGE_AUTOSCALE = False
_MAX_INPUT_IMAGE_MEGAPIXELS = 1.0
_OFFICIAL_SCALE_METHOD = "nearest-exact"

#: 下载 LRU 缓存（spec §7.2：容量定值 16）
_IMAGE_DOWNLOAD_CACHE: "OrderedDict[str, bytes]" = OrderedDict()
_IMAGE_DOWNLOAD_CACHE_LOCK = threading.Lock()
_IMAGE_DOWNLOAD_CACHE_MAX = 16

_DATA_URI_PREFIX = "data:image"
_DATA_URI_MARKER = ";base64,"
_BASE64_BLOB_MIN_LENGTH = 256

#: 图生图 image_url 格式测试（spec §7.1：包装层运行时不暴露，仅常量存续；基类内部逻辑保留）
_EDIT_IMAGE_URL_FORMAT_OPTION_NAME = "图生图image_url格式测试"
_EDIT_IMAGE_URL_FORMAT_OBJECT = "对象格式"

#: /v1/images/edits multipart 最多携带的输入图数量（spec §3.5 docstring：up to 16 images）
_MAX_EDIT_INPUT_IMAGES = 16

# ==================== 响应解析正则（spec §6.4 原文） ====================

_URL_RE = re.compile(r"https?://[^\s\"'<>\\)]+")
_MD_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_IMAGE_EXT_RE = re.compile(r"\.(png|jpg|jpeg|webp|gif|bmp)(\?|#|$)", re.IGNORECASE)
_BASE64_BLOB_RE = re.compile(r"^[A-Za-z0-9+/=\r\n]+$")
#: base64 字段键名探测（spec §6.4）
_B64_FIELD_KEY_RE = re.compile(r"(?:^|_)(?:b64|base64)(?:_|$)", re.IGNORECASE)
#: 文本字段键名探测（spec §6.4）
_TEXT_FIELD_KEY_RE = re.compile(r"(?:content|text|delta|message|output)", re.IGNORECASE)
#: JSON 头探测（spec §6.4 `^[\[{]`）
_JSON_HEAD_RE = re.compile(r"^[\[{]")

#: 资源回链路径（spec §6.3：/v1/files/image/ /files/image/ /files/）
_FILES_IMAGE_PATH_MARKERS = ("/v1/files/image/", "/files/image/", "/files/")

#: 快捷功能（spec §7.2 实锤：7 项选项 + 前缀映射）
QUICK_FUNCTION_NONE = "无"
QUICK_FUNCTION_OPTIONS = (
    "无",
    "白底三视图",
    "白底四视图",
    "九宫格[剧情]分镜",
    "九宫格[场景]分镜",
    "四宫格[剧情]分镜",
    "四宫格[视角]分镜",
)

# 快捷功能前缀模板（spec §6.5 / §7.2 QUICK_FUNCTION_PREFIXES 原文）
_QUICK_PREFIX_WHITE_BG_3VIEW = (
    "三视图（正面、侧面、背面），白色纯色背景，人物角色设计图，"
)
_QUICK_PREFIX_WHITE_BG_4VIEW = (
    "参照原图生成人物面部特写搭配全身三视图组合画面； "
    "画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照 / 侧面全身照 / 背面全身照，"
    "所有内容整合在 同一画幅内；采用纯白色背景，严格对齐人物人体比例 ，"
    "杜绝透视畸变问题，各视图之间间距均匀规整,无文字描述"
)
# 以下分镜模板按 spec §6.5 原文片段依 `+` 顺序直接拼接
_QUICK_PREFIX_STORY_9 = (
    "根据提供的"
    "剧情概述 / 画面主题 / 参考图"
    "，生成一张具有清晰叙事推进关系的 3×3 九宫格分镜图，共 9 个连续镜头"
    "全部镜头发生在同一场景与同一时间轴内，九个画面之间必须存在明确的前后承接关系，"
    "形成连续的动作/视线或情绪推进，而不是彼此孤立的画面拼接"
    "分镜采用电影镜头语言进行自由发挥：在整体叙事推进中自然涵盖远景/中景/近景与特写等不同景别，"
    "并根据剧情需要灵活使用正视/侧视/背视/过肩/内反打/轻微俯仰等视角变化，"
    "用于强化空间关系/人物心理与节奏起伏"
    "镜头景别与角度不与编号固定绑定，而是由剧情发展自动选择最合适的表现方式，"
    "使九个镜头整体读起来具备真实影视分镜的流动感"
    "当用户仅提供剧情文字时，应主动补全合理的场景结构/人物站位/行动路线与镜头关系，"
    "使画面具备清晰空间逻辑；当用户提供参考图时，应将其作为人物外观/服装风格/色彩倾向与整体美术气质的统一依据，"
    "并在全部九个镜头中严格继承，不得随镜头推进出现风格变化或角色漂移"
    "在全部九个分镜中，人物的外观/服装/体型比例/面部特征保持一致，整体色彩倾向与光照条件统一，"
    "仅允许人物动作/姿态以及镜头远近和角度发生变化，"
    "不得出现角色变形/肢体缺失/结构错乱或美术风格断裂，纯视觉展示，没有任何文字/字母或标签，"
    "每个画面之间被清晰的黑色实线分割"
)
# 四宫格[剧情]分镜：同上结构，将"3×3 九宫格/九个"替换为"2×2 四宫格/四个"（spec §6.5）
_QUICK_PREFIX_STORY_4 = (
    "根据提供的"
    "剧情概述 / 画面主题 / 参考图"
    "，生成一张具有清晰叙事推进关系的 2×2 四宫格分镜图，共 4 个连续镜头"
    "全部镜头发生在同一场景与同一时间轴内，四个画面之间必须存在明确的前后承接关系，"
    "形成连续的动作/视线或情绪推进，而不是彼此孤立的画面拼接"
    "分镜采用电影镜头语言进行自由发挥：在整体叙事推进中自然涵盖远景/中景/近景与特写等不同景别，"
    "并根据剧情需要灵活使用正视/侧视/背视/过肩/内反打/轻微俯仰等视角变化，"
    "用于强化空间关系/人物心理与节奏起伏"
    "镜头景别与角度不与编号固定绑定，而是由剧情发展自动选择最合适的表现方式，"
    "使四个镜头整体读起来具备真实影视分镜的流动感"
    "当用户仅提供剧情文字时，应主动补全合理的场景结构/人物站位/行动路线与镜头关系，"
    "使画面具备清晰空间逻辑；当用户提供参考图时，应将其作为人物外观/服装风格/色彩倾向与整体美术气质的统一依据，"
    "并在全部四个镜头中严格继承，不得随镜头推进出现风格变化或角色漂移"
    "在全部四个分镜中，人物的外观/服装/体型比例/面部特征保持一致，整体色彩倾向与光照条件统一，"
    "仅允许人物动作/姿态以及镜头远近和角度发生变化，"
    "不得出现角色变形/肢体缺失/结构错乱或美术风格断裂，纯视觉展示，没有任何文字/字母或标签，"
    "每个画面之间被清晰的黑色实线分割"
)
_QUICK_PREFIX_SCENE_9 = (
    "生成一张严格的3x3九宫格图像，纯视觉展示"
    "正中央为场景标准透视效果图；正上方为俯视角度画面；正下方为地面纹理视角；"
    "左侧为左侧墙壁平视画面；右侧为右侧墙壁平视画面；"
    "四个角落分别是：正前方视角/正后方视角以及两个无文字的材质道具特写"
    "要求：九个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，"
)
_QUICK_PREFIX_VIEW_4 = (
    "生成一张严格的2x2四宫格图像，纯视觉展示"
    "场景标准透视效果图；俯视角度画面；正正前方视角；正后方视角"
    "要求：四个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，"
)

QUICK_FUNCTION_PREFIXES: Dict[str, str] = {
    "无": "",
    "白底三视图": _QUICK_PREFIX_WHITE_BG_3VIEW,
    "白底四视图": _QUICK_PREFIX_WHITE_BG_4VIEW,
    "九宫格[剧情]分镜": _QUICK_PREFIX_STORY_9,
    "九宫格[场景]分镜": _QUICK_PREFIX_SCENE_9,
    "四宫格[剧情]分镜": _QUICK_PREFIX_STORY_4,
    "四宫格[视角]分镜": _QUICK_PREFIX_VIEW_4,
}

#: 文生图尺寸契约选项（包装层 INPUT_TYPES 顺序）
_VALID_SIZES = ("1024x1024", "1280x720", "720x1280", "1792x1024", "1024x1792")

#: 共享支撑实例
CONFIG_MANAGER = ConfigManager()
ERROR_CANVAS = ErrorCanvas()


# ==================== URL 解析（spec §3.2 端点归一函数族） ====================

def _normalize_base_url(api_base_url: str) -> str:
    """归一 base：补 http:// 前缀、去尾斜杠；为空报 未配置有效的 API URL。"""
    base = str(api_base_url or "").strip()
    if not base:
        raise ValueError("未配置有效的 API URL")
    if not re.match(r"^https?://", base, re.IGNORECASE):
        base = "http://" + base
    return base.rstrip("/")


def _resolve_endpoint_url(api_base_url: str, path_v1: str, path_short: str) -> str:
    """兼容：base 已带完整端点 / 已带 /v1 / 纯主机三种写法。"""
    base = _normalize_base_url(api_base_url)
    lowered = base.lower()
    for suffix in (path_v1, path_short):
        if lowered.endswith(suffix):
            return base
    if lowered.endswith("/v1"):
        return base + path_short
    return base + path_v1


def _resolve_chat_completions_url(api_base_url: str) -> str:
    return _resolve_endpoint_url(api_base_url, "/v1/chat/completions", "/chat/completions")


def _resolve_images_generations_url(api_base_url: str) -> str:
    return _resolve_endpoint_url(api_base_url, "/v1/images/generations", "/images/generations")


def _resolve_images_edits_url(api_base_url: str) -> str:
    return _resolve_endpoint_url(api_base_url, "/v1/images/edits", "/images/edits")


def _absolutize_url(raw_url: str, endpoint: str = "", api_base_url: str = "") -> str:
    """相对地址（/v1/files/image/xxx）→ 绝对地址。"""
    raw = str(raw_url or "").strip()
    if raw.startswith(("http://", "https://")):
        return raw
    base = str(api_base_url or endpoint or "").strip()
    if not base:
        return raw
    if base and not re.match(r"^https?://", base, re.IGNORECASE):
        base = "http://" + base
    if raw.startswith("/"):
        parsed = urlparse(base if base.endswith("/") else base + "/")
        return "%s://%s%s" % (parsed.scheme, parsed.netloc, raw)
    return urljoin(base if base.endswith("/") else base + "/", raw)


def _classify_image_ref(ref: str) -> str:
    """引用分类：base64（data URI）或 url。"""
    return "base64" if str(ref).startswith(_DATA_URI_PREFIX) else "url"


# ==================== base64 / 图片字节工具（spec §2 函数名） ====================

def _looks_like_base64_blob(value: str) -> bool:
    """^[A-Za-z0-9+/=\r\n]+$ 且长度达到阈值才视为 base64 载荷。"""
    text = str(value or "")
    return len(text) >= _BASE64_BLOB_MIN_LENGTH and bool(_BASE64_BLOB_RE.match(text))


def _normalize_base64_image(value: str) -> str:
    """剥 data URI 前缀与全部空白，得到纯净 base64。"""
    text = str(value or "").strip()
    if text.startswith(_DATA_URI_PREFIX):
        index = text.find(_DATA_URI_MARKER)
        if index >= 0:
            text = text[index + len(_DATA_URI_MARKER):]
    return re.sub(r"\s+", "", text)


def _decode_valid_base64_image_bytes(value: str) -> Optional[bytes]:
    """base64 → 合法图片字节；不可解码返回 None。"""
    cleaned = _normalize_base64_image(value)
    if not cleaned or not _BASE64_BLOB_RE.match(cleaned):
        return None
    try:
        raw = base64.b64decode(cleaned, validate=False)
    except Exception:  # noqa: BLE001
        return None
    return raw if _is_valid_image_bytes(raw) else None


def _is_valid_image_bytes(data: Optional[bytes]) -> bool:
    """图片魔数校验：PNG / JPEG / GIF / WEBP / BMP。"""
    if not data or len(data) < 12:
        return False
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True
    if data[:3] == b"\xff\xd8\xff":
        return True
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True
    if data[:2] == b"BM":
        return True
    return False


# ==================== 响应提取（spec §2/§3.4） ====================

def _push_unique_image_items(items: List[Dict[str, str]], new_items: List[Dict[str, str]]) -> None:
    """按 (kind, value 前缀) 去重追加图片条目。"""
    seen = {(item.get("kind"), str(item.get("value"))[:256]) for item in items}
    for item in new_items:
        key = (item.get("kind"), str(item.get("value"))[:256])
        if key not in seen:
            seen.add(key)
            items.append(item)


def _walk_json_for_image_items(node: Any, items: List[Dict[str, str]], texts: List[str]) -> None:
    """JSON 对象递归遍历：抓文本字段 / base64 字段 / URL 值（spec §3.4）。"""
    if isinstance(node, dict):
        for key, value in node.items():
            lowered = str(key).lower()
            if isinstance(value, str):
                if _B64_FIELD_KEY_RE.search(lowered) and value:
                    _push_unique_image_items(items, [{"kind": "base64", "value": value}])
                elif _TEXT_FIELD_KEY_RE.search(lowered) and value:
                    texts.append(value)
                elif value.startswith(_DATA_URI_PREFIX):
                    _push_unique_image_items(items, [{"kind": "base64", "value": value}])
                elif value.startswith(("http://", "https://")) and (
                    _IMAGE_EXT_RE.search(value) or any(m in value for m in _FILES_IMAGE_PATH_MARKERS)
                ):
                    _push_unique_image_items(items, [{"kind": "url", "value": value}])
            else:
                _walk_json_for_image_items(value, items, texts)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _walk_json_for_image_items(value, items, texts)


def _extract_image_refs_from_text(text: str) -> List[str]:
    """markdown 图片 / 图片扩展名 URL / 资源回链路径 多重正则提取。"""
    refs: List[str] = []
    if not text:
        return refs
    for match in _MD_IMAGE_RE.finditer(text):
        ref = match.group(1).strip()
        if ref and ref not in refs:
            refs.append(ref)
    for match in _URL_RE.finditer(text):
        ref = match.group(0).strip()
        if ref in refs:
            continue
        if _IMAGE_EXT_RE.search(ref) or any(marker in ref for marker in _FILES_IMAGE_PATH_MARKERS):
            refs.append(ref)
    return refs


def _extract_first_image_ref_from_chat_response(response_data: Any) -> Optional[str]:
    """chat 响应中的第一个图片引用（仅用于日志/回退判断）。"""
    items: List[Dict[str, str]] = []
    texts: List[str] = []
    _walk_json_for_image_items(response_data, items, texts)
    if items:
        return items[0].get("value")
    refs = _extract_image_refs_from_text("\n".join(texts))
    return refs[0] if refs else None


def _decode_response_text(raw: bytes) -> str:
    """utf-8-sig / gb18030 解码兜底（spec §3.4）。"""
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except Exception:  # noqa: BLE001
            continue
    return raw.decode("utf-8", errors="replace")


def _collect_image_items_from_response(response: Any) -> Tuple[List[Dict[str, str]], str]:
    """非流式 JSON 响应 → (图片条目, 聚合文本)。"""
    text = _decode_response_text(response.content or b"")
    try:
        data = json.loads(text)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("响应非 JSON: %s" % text[:200]) from exc
    items: List[Dict[str, str]] = []
    texts: List[str] = []
    _walk_json_for_image_items(data, items, texts)
    _merge_text_refs_into_items(items, texts)
    return items, "\n".join(texts)


def _merge_text_refs_into_items(items: List[Dict[str, str]], texts: List[str]) -> None:
    """聚合文本中的 markdown/URL/base64 引用并入条目列表（多重正则提取，去重）。"""
    if not texts:
        return
    for ref in _extract_image_refs_from_text("\n".join(texts)):
        _push_unique_image_items(items, [{"kind": _classify_image_ref(ref), "value": ref}])


def _extract_stream_text_fragments(block_text: str) -> List[str]:
    """data: 块兜底文本抽取（无法 JSON 解析时按正则抓引用/片段）。"""
    fragments: List[str] = []
    if not block_text:
        return fragments
    try:
        data = json.loads(block_text)
    except Exception:  # noqa: BLE001
        fragments.extend(_extract_image_refs_from_text(block_text))
        return fragments
    items: List[Dict[str, str]] = []
    texts: List[str] = []
    _walk_json_for_image_items(data, items, texts)
    fragments.extend("%s\x00%s" % (item["kind"], item["value"]) for item in items)
    fragments.extend(texts)
    return fragments


def _collect_image_items_from_event_stream(response: Any) -> Tuple[List[Dict[str, str]], str]:
    """SSE 流解析：data: 块切分 + [DONE] 终止 + JSON 递归遍历（spec §3.4）。"""
    items: List[Dict[str, str]] = []
    texts: List[str] = []
    decoder = codecs.getincrementaldecoder("utf-8")("replace")
    buffer = ""
    done = False
    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue
        if isinstance(chunk, str):
            chunk = chunk.encode("utf-8", errors="replace")
        buffer += decoder.decode(chunk)
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
            elif line.startswith("{"):
                payload = line  # 裸 JSON 行兜底
            else:
                texts.append(line)
                continue
            if payload == "[DONE]":
                done = True
                break
            try:
                data = json.loads(payload)
            except Exception:  # noqa: BLE001
                texts.extend(_extract_image_refs_from_text(payload))
                continue
            _walk_json_for_image_items(data, items, texts)
        if done:
            break
    buffer += decoder.decode(b"", final=True)
    if buffer.strip() and not done:
        tail = buffer.strip()
        try:
            data = json.loads(tail)
            _walk_json_for_image_items(data, items, texts)
        except Exception:  # noqa: BLE001
            texts.extend(_extract_image_refs_from_text(tail))
    _merge_text_refs_into_items(items, texts)
    return items, "\n".join(texts)


# ==================== 图片下载（spec §3.6：四策略回退 + LRU） ====================

def _cache_get(key: str) -> Optional[bytes]:
    with _IMAGE_DOWNLOAD_CACHE_LOCK:
        value = _IMAGE_DOWNLOAD_CACHE.get(key)
        if value is not None:
            _IMAGE_DOWNLOAD_CACHE.move_to_end(key)
        return value


def _cache_put(key: str, value: bytes) -> None:
    with _IMAGE_DOWNLOAD_CACHE_LOCK:
        _IMAGE_DOWNLOAD_CACHE[key] = value
        _IMAGE_DOWNLOAD_CACHE.move_to_end(key)
        while len(_IMAGE_DOWNLOAD_CACHE) > _IMAGE_DOWNLOAD_CACHE_MAX:
            _IMAGE_DOWNLOAD_CACHE.popitem(last=False)


def _download_image_bytes(
    api_key: str,
    timeout_s: float,
    url: str,
    bypass_proxy: bool = False,
    verify_ssl: bool = True,
    depth: int = 0,
) -> bytes:
    """带鉴权下载 /v1/files/image/... 或外链；四策略回退 + LRU 缓存。

    策略矩阵（spec §3.6，矩阵顺序未确认，按绕过代理意图分组）：
    - 绕过代理：直连鉴权 → 直连无鉴权
    - 走系统代理：系统代理鉴权 → 系统代理无鉴权
    """
    import requests  # 惰性导入

    cached = _cache_get(url)
    if cached is not None:
        return cached

    if bypass_proxy:
        strategies = (("直连鉴权", False, True), ("直连无鉴权", False, False))
    else:
        strategies = (("系统代理鉴权", True, True), ("系统代理无鉴权", True, False))

    last_error: Optional[Exception] = None
    timeout_value = max(5.0, float(timeout_s or 60))
    for label, trust_env, use_auth in strategies:
        try:
            session = requests.Session()
            session.trust_env = trust_env
            headers = {
                "User-Agent": _USER_AGENT,
                "Accept": "application/json, image/*",
                "Accept-Encoding": "gzip, deflate",
            }
            if use_auth and api_key:
                headers["Authorization"] = "Bearer %s" % api_key
            start = time.perf_counter()
            response = session.get(
                url,
                headers=headers,
                timeout=(min(15.0, timeout_value), timeout_value),
                verify=verify_ssl,
                stream=True,
            )
            response.raise_for_status()
            logger.info("图片下载响应耗时: %.2fs | 策略: %s" % (time.perf_counter() - start, label))
            content_start = time.perf_counter()
            chunks: List[bytes] = []
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    chunks.append(chunk)
            data = b"".join(chunks)
            logger.info(
                "图片下载内容耗时: %.2fs | 大小: %d KB | 策略: %s"
                % (time.perf_counter() - content_start, len(data) // 1024, label)
            )
            data = _normalize_downloaded_image_bytes(
                data,
                api_key=api_key,
                timeout_s=timeout_s,
                bypass_proxy=bypass_proxy,
                verify_ssl=verify_ssl,
                depth=depth,
            )
            if data and _is_valid_image_bytes(data):
                _cache_put(url, data)
                return data
            last_error = RuntimeError("下载内容不是有效图片")
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError("下载图片失败: %s" % last_error)


def _decode_nested_payload_from_bytes(data: bytes) -> List[Dict[str, str]]:
    r"""可疑内容（^[\[{] JSON 头）→ 递归提取图片条目。"""
    try:
        payload = json.loads(_decode_response_text(data))
    except Exception:  # noqa: BLE001
        return []
    items: List[Dict[str, str]] = []
    texts: List[str] = []
    _walk_json_for_image_items(payload, items, texts)
    _merge_text_refs_into_items(items, texts)
    return items


def _normalize_downloaded_image_bytes(
    data: Optional[bytes],
    api_key: str = "",
    timeout_s: float = 60,
    bypass_proxy: bool = False,
    verify_ssl: bool = True,
    depth: int = 0,
) -> Optional[bytes]:
    """下载结果规整：有效图片直接返回；JSON 嵌套载荷剥一层提取图片。"""
    if not data:
        return None
    if _is_valid_image_bytes(data):
        return data
    if depth >= 1 or not _JSON_HEAD_RE.match(_decode_response_text(data[:2])):
        return None
    for item in _decode_nested_payload_from_bytes(data):
        if item.get("kind") == "base64":
            decoded = _decode_valid_base64_image_bytes(item.get("value", ""))
            if decoded:
                return decoded
        else:
            nested_url = _absolutize_url(item.get("value", ""))
            if nested_url.startswith(("http://", "https://")):
                try:
                    nested = _download_image_bytes(
                        api_key,
                        timeout_s,
                        nested_url,
                        bypass_proxy=bypass_proxy,
                        verify_ssl=verify_ssl,
                        depth=depth + 1,
                    )
                except Exception:  # noqa: BLE001
                    continue
                if nested and _is_valid_image_bytes(nested):
                    return nested
    return None


# ==================== 输入图缩放（spec §3.5，包装层默认关闭） ====================

def _scale_image_tensor_to_total_pixels_if_needed(image_tensor, megapixels: float = _MAX_INPUT_IMAGE_MEGAPIXELS, resolution_steps: int = 1):
    """对齐 ComfyUI "Scale Image to Total Pixels" 逻辑；仅超过目标像素量才缩小。

    与 Grok_Safe_PY 包装层一致：`_ENABLE_INPUT_IMAGE_AUTOSCALE = False` 时原样返回。
    """
    if not _ENABLE_INPUT_IMAGE_AUTOSCALE:
        return image_tensor
    if image_tensor is None or not hasattr(image_tensor, "shape"):
        return image_tensor
    try:
        import math

        import numpy as np
        import torch
        import comfy.utils
    except Exception:  # noqa: BLE001
        return image_tensor

    is_torch_like = hasattr(image_tensor, "detach") and hasattr(image_tensor, "cpu")
    if is_torch_like:
        arr = image_tensor.detach().cpu().numpy()
    elif hasattr(image_tensor, "cpu"):
        arr = image_tensor.cpu().numpy()
    else:
        arr = np.array(image_tensor)

    original_ndim = arr.ndim
    if original_ndim == 3:
        arr = arr[None, ...]
    if arr.ndim != 4:
        return image_tensor

    target_total = float(megapixels) * 1024.0 * 1024.0
    step = max(1, int(resolution_steps or 1))
    resized_images: List[Any] = []
    changed = False

    for i in range(arr.shape[0]):
        img = arr[i]
        if img.ndim != 3:
            resized_images.append(img)
            continue
        source_height = int(img.shape[0])
        source_width = int(img.shape[1])
        if source_width <= 0 or source_height <= 0:
            resized_images.append(img)
            continue
        current_total = float(source_width * source_height)
        if current_total <= 0 or current_total <= target_total:
            resized_images.append(img)
            continue
        scale_by = math.sqrt(target_total / current_total)
        target_width = max(1, round(source_width * scale_by / step) * step)
        target_height = max(1, round(source_height * scale_by / step) * step)
        if target_width == source_width and target_height == source_height:
            resized_images.append(img)
            continue
        changed = True
        tensor_img = torch.from_numpy(img).movedim(-1, 0).unsqueeze(0)
        resized_tensor = comfy.utils.common_upscale(
            tensor_img, int(target_width), int(target_height), _OFFICIAL_SCALE_METHOD, "disabled"
        )
        resized = resized_tensor.squeeze(0).movedim(0, -1).cpu().numpy()
        resized_images.append(resized.astype(img.dtype, copy=False))

    if not changed:
        return image_tensor
    stacked = np.stack(resized_images, axis=0)
    if original_ndim == 3:
        stacked = stacked[0]
    if is_torch_like:
        return torch.from_numpy(stacked).to(device=image_tensor.device, dtype=image_tensor.dtype)
    return stacked


def scale_image_tensor_to_total_pixels_if_needed(image_tensor):
    """包装层同名公开入口（默认关闭，直通）。"""
    return _scale_image_tensor_to_total_pixels_if_needed(image_tensor)


# ==================== 中断 / 进度（spec §3.3） ====================

def _ensure_not_interrupted() -> None:
    """ComfyUI 中断透传：comfy.model_management.throw_exception_if_processing_interrupted。"""
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001  非 ComfyUI 环境
        return
    throw = getattr(model_management, "throw_exception_if_processing_interrupted", None)
    if callable(throw):
        throw()
        return
    ensure = getattr(model_management, "ensure_not_interrupted", None)
    if callable(ensure):
        ensure()


def _make_comfy_progress_bar(total: int):
    """comfy.utils.ProgressBar 工厂（comfy 不可用时返回 None，runner 自行兜底）。"""
    try:
        from comfy.utils import ProgressBar  # 惰性导入

        return ProgressBar(int(total))
    except Exception:  # noqa: BLE001
        return None


def _masked_key(api_key: str) -> str:
    """日志脱敏：遮蔽 API Key 中段。"""
    key = str(api_key or "")
    if len(key) <= 8:
        return "..."
    return "%s...%s" % (key[:4], key[-4:])


def _truncate_text(text: str, limit: int = 200) -> str:
    value = str(text or "").strip()
    if len(value) > limit:
        return value[:limit] + "...（错误响应已截断）"
    return value


# ==================== 节点 ====================

class BananaGrokImageSafePyNode:
    """TE MAN Grok Image

    注册名: TE_image_pro_grok_image
    规格:   spec/Grok_Image_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Grok'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '生成一张可爱的小猫图片', 'defaultInput': True, 'tooltip': '用于生成图片的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址，如 http://localhost:8000（不要带 /v1/chat/completions）'}), 'image_count': ('INT', {'default': 1, 'min': 1, 'max': 10, 'tooltip': '目标图片张数，对应 image_config.n'}), 'size': (('1024x1024', '1280x720', '720x1280', '1792x1024', '1024x1792'), {'default': '1024x1024', 'tooltip': '图片尺寸，对应 image_config.size'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image': ('IMAGE', {'tooltip': '参考/编辑输入图片（可选）。填写时会以多模态 messages 方式发给 /v1/chat/completions。'}), 'image_2': ('IMAGE', {'tooltip': '第二路参考/编辑输入图片（可选）。'}), 'image_3': ('IMAGE', {'tooltip': '第三路参考/编辑输入图片（可选）。'}), 'timeout_s': ('INT', {'default': 180, 'min': 30, 'max': 3600, 'tooltip': '请求超时（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜'), {'default': '无', 'tooltip': '使用快捷功能生成。'})}}
        # --8<-- 契约结束 --8<--

    # -- 配置解析（spec §3.2 _resolve_key_and_url） --------------------------

    def _resolve_key_and_url(self, api_key: str = "", api_base_url: str = "") -> Tuple[str, str]:
        """API Key / API URL 解析：节点参数优先 → config.ini [gemini]。"""
        key = ""
        if str(api_key or "").strip():
            key = CONFIG_MANAGER.sanitize_api_key(api_key) or ""
        if not key:
            key = CONFIG_MANAGER.load_api_key() or ""
        if not key:
            logger.warning("请在 config.ini 中配置 API Key 或在节点中填写")

        base = str(api_base_url or "").strip() or CONFIG_MANAGER.get_effective_api_base_url()
        if not base:
            logger.warning("请在 config.ini 中配置 API URL 或在节点中填写")
            raise ValueError("未配置有效的 API URL")

        logger.info("API URL: [已脱敏] | API Key: %s" % _masked_key(key))
        return key, base

    # -- 主入口 --------------------------------------------------------------

    def generate_images(
        self,
        prompt: str = "",
        api_key: str = "",
        api_base_url: str = "",
        image_count: int = 1,
        size: str = "1024x1024",
        seed: int = -1,
        image=None,
        image_2=None,
        image_3=None,
        timeout_s: int = 180,
        绕过代理: bool = False,
        **kwargs,
    ):
        """文生图 / 图生图主流程（seed 仅供 ComfyUI 工作流使用；不会写入请求体）。"""
        del seed  # 不写入请求体

        prompt_text = str(prompt or "").strip()
        if not prompt_text:
            raise ValueError("请输入 prompt")

        # 快捷功能前缀拼接（spec §3.3）
        quick_function_value = str(kwargs.get("快捷功能", QUICK_FUNCTION_NONE) or QUICK_FUNCTION_NONE)
        quick_prefix = QUICK_FUNCTION_PREFIXES.get(quick_function_value, "")
        final_prompt_text = (quick_prefix + prompt_text) if quick_prefix else prompt_text

        # 输入图（可选三路；包装层自动缩放默认关闭）
        input_tensors = [t for t in (image, image_2, image_3) if t is not None]
        if input_tensors:
            input_tensors = [scale_image_tensor_to_total_pixels_if_needed(t) for t in input_tensors]
        image_mode = "图生图" if input_tensors else "文生图"
        model_used = _MODEL_IMAGE_EDIT if input_tensors else _MODEL_TEXT_TO_IMAGE

        api_key_value, api_base_url_value = self._resolve_key_and_url(api_key, api_base_url)

        # 尺寸归一 + 图生图强限 1024x1024（spec §3.5）
        normalized_size = str(size or "1024x1024").strip() or "1024x1024"
        if normalized_size not in _VALID_SIZES:
            normalized_size = "1024x1024"
        if input_tensors and normalized_size != "1024x1024":
            logger.warning(
                "Grok 图生图当前仅支持 1024x1024，已自动将 size 从 %s 改为 1024x1024"
                % normalized_size
            )
            normalized_size = "1024x1024"

        image_count_value = max(1, int(image_count or 1))
        timeout_value = max(5, int(timeout_s or 180))
        bypass_proxy_value = bool(绕过代理)
        legacy_url_format = str(
            kwargs.get(_EDIT_IMAGE_URL_FORMAT_OPTION_NAME, _EDIT_IMAGE_URL_FORMAT_OBJECT)
            or _EDIT_IMAGE_URL_FORMAT_OBJECT
        )

        logger.info(
            "Grok 图片生成任务 | Mode: %s | Model: %s | Size: %s | "
            "Requested Images: %d | Input Images: %d | Quick Function: %s"
            % (
                image_mode,
                model_used,
                normalized_size,
                image_count_value,
                len(input_tensors),
                quick_function_value,
            )
        )

        # 多任务并发（spec §3.3：BatchGenerationRunner + continue_on_error）
        tasks: List[Dict[str, int]] = [{"task_index": index} for index in range(image_count_value)]
        started = time.perf_counter()

        def _worker(task: Dict[str, int]) -> Dict[str, Any]:
            try:
                _ensure_not_interrupted()
                if input_tensors:
                    image_bytes_list = self._call_edit_once(
                        final_prompt_text,
                        input_tensors,
                        api_key_value,
                        api_base_url_value,
                        normalized_size,
                        timeout_value,
                        bypass_proxy_value,
                        legacy_url_format,
                    )
                else:
                    image_bytes_list = self._call_generate_once(
                        final_prompt_text,
                        api_key_value,
                        api_base_url_value,
                        normalized_size,
                        timeout_value,
                        bypass_proxy_value,
                    )
                tensors = [self._image_bytes_to_tensor(data) for data in image_bytes_list]
                tensors = [t for t in tensors if t is not None]
                if not tensors:
                    return {"tensors": [], "error": "生成失败：未返回任何有效图片"}
                return {"tensors": tensors, "error": None}
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                return {"tensors": [], "error": str(exc) or "生成失败"}

        runner = BatchGenerationRunner(
            tasks=tasks,
            worker_fn=_worker,
            batch_size=len(tasks),
            continue_on_error=True,
            progress_bar=_make_comfy_progress_bar,
            logger=logger,
        )
        results = runner.run(
            ensure_not_interrupted=_ensure_not_interrupted,
            progress_bar=_make_comfy_progress_bar,
        )
        elapsed = time.perf_counter() - started

        # 聚合：成功槽收 tensor，失败槽用 ErrorCanvas 生成错误图保证输出不断裂
        import torch  # 惰性导入

        picked_tensors: List[Any] = []
        all_errors: List[str] = []
        total_generated_images = 0
        for task_index, result in enumerate(results):
            if result and result.get("tensors"):
                picked_tensors.extend(result["tensors"])
                total_generated_images += len(result["tensors"])
            else:
                error_text = (result or {}).get("error") or "生成失败"
                all_errors.append("任务%d: %s" % (task_index + 1, error_text))
                picked_tensors.append(
                    ERROR_CANVAS.build_error_tensor_from_text(
                        error_text, title="TE MAN Grok 请求错误"
                    )
                )

        if total_generated_images > 0:
            logger.success(
                "Grok 图片生成任务完成，返回 %d 张可用图像（耗时 %.2fs）"
                % (total_generated_images, elapsed)
            )
        else:
            logger.warning("生成失败：未返回任何有效图片")
        if all_errors:
            logger.error("Errors: " + " | ".join(all_errors))

        if picked_tensors:
            images = picked_tensors[0] if len(picked_tensors) == 1 else torch.cat(picked_tensors, dim=0)
        else:
            images = ERROR_CANVAS.build_error_tensor_from_text("生成失败：未返回任何有效图片")

        summary_lines = [
            "Grok 图片生成任务",
            "Input Images: %d" % len(input_tensors),
            "Requested Images: %d" % image_count_value,
            "Model: %s" % model_used,
            "Size: %s" % normalized_size,
            "Mode: %s" % image_mode,
            "Quick Function: %s" % quick_function_value,
            "成功生成 %d 张可用图像" % total_generated_images,
        ]
        if all_errors:
            summary_lines.append("Errors: " + " | ".join(all_errors))

        text = "\n".join(summary_lines)
        preview = IMAGE_CODEC.build_preview_tuple(images)
        if preview is not None:
            return {"ui": preview, "result": (images, text)}
        return (images, text)

    # -- 单张转换 ------------------------------------------------------------

    def _image_bytes_to_tensor(self, data: bytes):
        """图片字节 → float32 [1,H,W,C] tensor（解码失败返回 None 并记日志）。"""
        try:
            return IMAGE_CODEC.base64_to_tensor_single(
                base64.b64encode(data).decode("ascii")
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("响应已返回，但没有可解码图片: %s" % exc)
            return None

    # -- 结果条目 → 图片字节（spec §3.4） ------------------------------------

    def _resolve_items_to_bytes(
        self,
        items: List[Dict[str, str]],
        text: str,
        api_key_value: str,
        api_base_url_value: str,
        timeout_value: float,
        bypass_proxy_value: bool,
    ) -> List[bytes]:
        """图片条目（base64/URL）→ 合法图片字节列表。"""
        if not items and text:
            for ref in _extract_image_refs_from_text(text):
                items = items + [{"kind": _classify_image_ref(ref), "value": ref}]
        image_bytes_list: List[bytes] = []
        for item in items:
            kind = item.get("kind")
            value = str(item.get("value") or "")
            if kind == "base64":
                decoded = _decode_valid_base64_image_bytes(value)
                if decoded:
                    image_bytes_list.append(decoded)
                continue
            url = _absolutize_url(value, api_base_url=api_base_url_value)
            if not url.startswith(("http://", "https://")):
                continue
            image_bytes_list.append(
                _download_image_bytes(
                    api_key_value,
                    timeout_value,
                    url,
                    bypass_proxy=bypass_proxy_value,
                )
            )
        if not image_bytes_list:
            raise RuntimeError("响应已返回，但没有可解码图片")
        return image_bytes_list

    # -- 文生图（spec §3.4 _call_generate_once） -----------------------------

    def _call_generate_once(
        self,
        final_prompt_text: str,
        api_key_value: str,
        api_base_url_value: str,
        normalized_size: str,
        timeout_value: float,
        bypass_proxy_value: bool,
    ) -> List[bytes]:
        """POST /v1/chat/completions（payload 变体逐个尝试）→ /v1/images/generations 兜底。"""
        import requests  # 惰性导入

        all_errors: List[str] = []
        url = _resolve_chat_completions_url(api_base_url_value)
        payload_variants: List[Dict[str, Any]] = [
            {
                "model": _MODEL_TEXT_TO_IMAGE,
                "messages": [{"role": "user", "content": final_prompt_text}],
                "image_config": {"size": normalized_size, "n": 1},
                "stream": True,
            },
            {
                "model": _MODEL_TEXT_TO_IMAGE,
                "messages": [{"role": "user", "content": final_prompt_text}],
                "image_config": {"size": normalized_size, "n": 1},
                "stream": False,
            },
        ]

        for variant_index, request_variant in enumerate(payload_variants, start=1):
            stream = bool(request_variant.get("stream"))
            try:
                _ensure_not_interrupted()
                session = requests.Session()
                session.trust_env = not bypass_proxy_value
                headers = {
                    "Authorization": "Bearer %s" % api_key_value,
                    "Content-Type": "application/json",
                    "Accept": "text/event-stream" if stream else "application/json",
                    "Accept-Encoding": "gzip, deflate",
                    "User-Agent": _USER_AGENT,
                }
                response = session.post(
                    url,
                    json=request_variant,
                    headers=headers,
                    timeout=(min(15.0, timeout_value), timeout_value),
                    stream=stream,
                )
                if response.status_code // 100 != 2:
                    raise RuntimeError(
                        "API 调用失败: HTTP %s: %s"
                        % (response.status_code, _truncate_text(_decode_response_text(response.content or b"")))
                    )
                if stream:
                    items, text = _collect_image_items_from_event_stream(response)
                else:
                    items, text = _collect_image_items_from_response(response)
                return self._resolve_items_to_bytes(
                    items,
                    text,
                    api_key_value,
                    api_base_url_value,
                    timeout_value,
                    bypass_proxy_value,
                )
            except InterruptProcessingException:
                raise
            except Exception as exc:  # noqa: BLE001
                all_errors.append("请求变体%d: %s" % (variant_index, exc))

        # 备用路径：/v1/images/generations（spec §3.4）
        try:
            _ensure_not_interrupted()
            session = requests.Session()
            session.trust_env = not bypass_proxy_value
            headers = {
                "Authorization": "Bearer %s" % api_key_value,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": _USER_AGENT,
            }
            payload = {
                "model": _MODEL_TEXT_TO_IMAGE,
                "prompt": final_prompt_text,
                "n": 1,
                "size": normalized_size,
                "response_format": "b64_json",
            }
            response = session.post(
                _resolve_images_generations_url(api_base_url_value),
                json=payload,
                headers=headers,
                timeout=(min(15.0, timeout_value), timeout_value),
            )
            if response.status_code // 100 != 2:
                raise RuntimeError(
                    "API 调用失败: HTTP %s: %s"
                    % (response.status_code, _truncate_text(_decode_response_text(response.content or b"")))
                )
            items, text = _collect_image_items_from_response(response)
            return self._resolve_items_to_bytes(
                items,
                text,
                api_key_value,
                api_base_url_value,
                timeout_value,
                bypass_proxy_value,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            all_errors.append("images/generations 兜底: %s" % exc)

        raise RuntimeError("; ".join(all_errors) or "未在响应中解析到图片")

    # -- 图生图（spec §3.5 _call_edit_once / _build_edit_content） ------------

    def _encode_image_tensor_to_png_files(self, input_tensors: List[Any]) -> List[Tuple[str, Tuple[str, bytes, str]]]:
        """Convert ComfyUI IMAGE tensor (BHWC, float[0..1]) into requests `files` list for multipart upload.

        Returns up to 16 images for the `/v1/images/edits` API.
        """
        try:
            images: List[Any] = []
            for tensor in input_tensors:
                images.extend(IMAGE_CODEC.extract_numpy_images(tensor))
        except ImportError as exc:  # noqa: BLE001
            raise RuntimeError("缺少图像依赖（numpy）: %s" % exc) from exc
        except ValueError as exc:  # noqa: BLE001
            raise RuntimeError("不支持的 IMAGE 维度: %s" % exc) from exc
        if not images:
            raise RuntimeError("不支持的 IMAGE 维度: 无有效输入图像")
        parts: List[Tuple[str, Tuple[str, bytes, str]]] = []
        for index, image in enumerate(images[:_MAX_EDIT_INPUT_IMAGES], start=1):
            field_name, filename, mime_type, data = IMAGE_CODEC.encode_numpy_image_to_api_file_part(
                image, field_name="image", filename_prefix="image_%d" % index
            )
            parts.append((field_name, (filename, data, mime_type)))
        return parts

    def _build_edit_content(
        self,
        final_prompt_text: str,
        input_tensors: List[Any],
        url_format: str,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """多模态 messages content：输入图按 对象格式（image_url 对象）封装。"""
        input_data_urls: List[str] = []
        for tensor in input_tensors:
            for data_url in IMAGE_CODEC.prepare_input_image_data_urls(tensor):
                input_data_urls.append(data_url)
        content: List[Dict[str, Any]] = [{"type": "text", "text": final_prompt_text}]
        for data_url in input_data_urls:
            if url_format == _EDIT_IMAGE_URL_FORMAT_OBJECT:
                # 对象格式：{"type":"image_url","image_url":{"url":...}}
                content.append({"type": "image_url", "image_url": {"url": data_url}})
            else:
                # 其余形态未确认（spec §3.5）：退化为文本内联 data URL
                content.append({"type": "text", "text": data_url})
        return content, input_data_urls

    def _call_edit_once(
        self,
        final_prompt_text: str,
        input_tensors: List[Any],
        api_key_value: str,
        api_base_url_value: str,
        normalized_size: str,
        timeout_value: float,
        bypass_proxy_value: bool,
        url_format: str = _EDIT_IMAGE_URL_FORMAT_OBJECT,
    ) -> List[bytes]:
        """并行路径：多模态 messages → /v1/images/edits multipart 兜底（尺寸已强限 1024x1024）。"""
        import requests  # 惰性导入

        all_errors: List[str] = []
        edit_size = "1024x1024"

        # 变体 1：/v1/chat/completions 多模态 messages
        try:
            _ensure_not_interrupted()
            content, input_data_urls = self._build_edit_content(
                final_prompt_text, input_tensors, url_format
            )
            payload = {
                "model": _MODEL_IMAGE_EDIT,
                "messages": [{"role": "user", "content": content}],
                "image_config": {"size": edit_size, "n": 1},
                "stream": False,
            }
            session = requests.Session()
            session.trust_env = not bypass_proxy_value
            headers = {
                "Authorization": "Bearer %s" % api_key_value,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": _USER_AGENT,
            }
            response = session.post(
                _resolve_chat_completions_url(api_base_url_value),
                json=payload,
                headers=headers,
                timeout=(min(15.0, timeout_value), timeout_value),
            )
            if response.status_code // 100 != 2:
                raise RuntimeError(
                    "API 调用失败: HTTP %s: %s"
                    % (response.status_code, _truncate_text(_decode_response_text(response.content or b"")))
                )
            items, text = _collect_image_items_from_response(response)
            return self._resolve_items_to_bytes(
                items,
                text,
                api_key_value,
                api_base_url_value,
                timeout_value,
                bypass_proxy_value,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            all_errors.append("多模态 messages: %s" % exc)

        # 变体 2：/v1/images/edits multipart（files + form）
        try:
            _ensure_not_interrupted()
            files = self._encode_image_tensor_to_png_files(input_tensors)
            form = {
                "model": _MODEL_IMAGE_EDIT,
                "prompt": final_prompt_text,
                "size": edit_size,
                "n": "1",
                "response_format": "b64_json",
            }
            session = requests.Session()
            session.trust_env = not bypass_proxy_value
            headers = {
                "Authorization": "Bearer %s" % api_key_value,
                "Accept": "application/json",
                "Accept-Encoding": "gzip, deflate",
                "User-Agent": _USER_AGENT,
            }
            response = session.post(
                _resolve_images_edits_url(api_base_url_value),
                files=files,
                data=form,
                headers=headers,
                timeout=(min(15.0, timeout_value), timeout_value),
            )
            if response.status_code // 100 != 2:
                raise RuntimeError(
                    "API 调用失败: HTTP %s: %s"
                    % (response.status_code, _truncate_text(_decode_response_text(response.content or b"")))
                )
            items, text = _collect_image_items_from_response(response)
            return self._resolve_items_to_bytes(
                items,
                text,
                api_key_value,
                api_base_url_value,
                timeout_value,
                bypass_proxy_value,
            )
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            all_errors.append("images/edits: %s" % exc)

        raise RuntimeError("; ".join(all_errors) or "未在响应中解析到图片")


NODE_CLASS_MAPPINGS = {'TE_image_pro_grok_image': BananaGrokImageSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_grok_image': 'TE MAN Grok Image'}
