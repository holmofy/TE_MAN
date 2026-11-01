# -*- coding: utf-8 -*-
"""te_man_open · TE_VEO_Video

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

te_man_open 纯 Python 复刻（spec/TE_VEO_Video.md 含动态回填节）：
ComfyUI 节点：TE veo video
- POST /v1/videos 提交任务
- GET /v1/videos/{task_id} 轮询状态

本节点自建 requests.Session 直连（不复用 api_client / task_runner，spec §3 负证据）：
720p 默认 JSON 提交；1080p 强制改走 multipart + input_reference[] 接口；
首帧/尾帧/最多 3 张多图参考互斥校验；输入图超 1.0MP 自动缩放（nearest-exact）；
omni-flash 固定 duration=10。无硬编码默认 URL（_DEFAULT_BASE_URL=""，spec 实锤）。
requests/torch/numpy/comfy 系全部函数内惰性导入，模块顶层只有标准库导入。
"""

import base64
import json
import math
import os
import shutil
import time
from urllib.parse import urljoin, urlparse

try:  # 包内相对导入；以文件方式直载时回退绝对导入
    from ..shared.config_manager import CONFIG_MANAGER
    from ..shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_data_url
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared.config_manager import CONFIG_MANAGER
    from te_man_open.shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_data_url
    from te_man_open.shared.logger import logger


# ==================== 模块常量（spec §8.1 动态回填实锤值） ====================

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

#: 模型档位映射常量（spec §8.1 动态回填实锤；fl = 首尾帧变体）
_FAST_MODEL_NAME_720P = "veo3.1-fast"
_FAST_MODEL_NAME_1080P = "veo_3_1-fast-hd"
_FAST_MODEL_NAME_4K = "veo_3_1-fast-4K"
_FAST_MODEL_NAME_1080P_FL = "veo_3_1-fast-fl-hd"
_FAST_MODEL_NAME_4K_FL = "veo_3_1-fast-4K-fl"

#: lite / omni 变体（spec 实锤）
_LITE_MODEL_NAME = "veo3.1-lite"
_LITE_MODEL_VARIANT = "veo3.1-lite"
_OMNI_FLASH_MODEL_NAME = "omni_flash-10s"  # 字符串证据，spec §4.1
_OMNI_FLASH_DURATION = 10  # omni-flash 固定 10 秒

#: 默认档位（spec §8.1）
_DEFAULT_MODEL_VARIANT = "veo 3.1 fast"
_DEFAULT_OUTPUT_PROFILE = "720p"

#: 输入图总像素限幅（对齐 ComfyUI「Scale Image to Total Pixels」，spec 实锤值）
_MAX_INPUT_IMAGE_MEGAPIXELS = 1.0
_OFFICIAL_SCALE_METHOD = "nearest-exact"

#: 输出文件名前缀与 UA（te_veo_video_ / ComfyUI-TE_API/1.0，spec 实锤）
_OUTPUT_FILE_PREFIX = "te_veo_video_"
_USER_AGENT = "ComfyUI-TE_API/1.0"

#: 无硬编码默认 URL（VEO 与 Jimeng 不同，spec §4.4 实锤）
_DEFAULT_BASE_URL = ""

#: 内部超时（契约未暴露 timeout_s 输入，取内部固定值）
_SUBMIT_TIMEOUT_S = 600
_POLL_TIMEOUT_S = 3600
_DOWNLOAD_TIMEOUT_S = 600

#: 任务状态机（字符串证据，spec §4.6 步骤 5）
_VIDEO_DONE_STATUS = frozenset({"succeeded", "completed", "success"})
_VIDEO_FAILED_STATUS = frozenset({"failed", "failure"})

#: 分辨率字面量表（spec 证据附录：六种字面量，按 16:9 / 9:16 映射）
_VIDEO_SIZE_TABLE = {
    "720p": {"16:9": "1280x720", "9:16": "720x1280"},
    "1080p": {"16:9": "1920x1080", "9:16": "1080x1920"},
    "4k": {"16:9": "3840x2160", "9:16": "2160x3840"},
}

_MSG_EMPTY_PROMPT = "请输入 prompt"
_MSG_NO_KEY = "请在 config.ini 中配置 API Key 或在节点中填写"
_MSG_NO_URL = "请在 config.ini 中配置 API URL 或在节点中填写"
_MSG_INVALID_URL = "未配置有效的 API URL"
_MSG_UNKNOWN_ERROR = "未知错误"


# ==================== 中断 / 会话 / 日志辅助 ====================

def _ensure_not_interrupted():
    """统一的中断检查，复用 ComfyUI 原生取消机制（非 ComfyUI 环境 no-op）。"""
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001
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


def _masked_key(api_key):
    """日志打码：保留首尾 4 位。"""
    key = str(api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 8 + key[-4:]


def _build_session(bypass_proxy):
    """自建 requests.Session 直连（本模块不复用 api_client）；绕代理时 trust_env=False。"""
    import requests  # 惰性导入

    session = requests.Session()
    if bypass_proxy:
        session.trust_env = False
        session.proxies = {}
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _get_output_dir():
    """输出目录：ComfyUI/output（folder_paths 可用时），否则回退 ./output。"""
    try:
        import folder_paths  # 仅 ComfyUI 环境存在

        output_dir = folder_paths.get_output_directory()
    except Exception:  # noqa: BLE001  纯 Python 环境回退
        output_dir = os.path.join(os.getcwd(), "output")
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _summarize_for_log(text, max_chars=600):
    """日志脱敏：data URL / 大段 base64 换成 <data-image len=…> 占位后截断。"""
    import re

    value = str(text or "")

    def _replace(match):
        return "<data-image len=%d>" % len(match.group(0))

    value = re.sub(
        r"data:[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+",
        _replace,
        value,
    )
    value = re.sub(r"[A-Za-z0-9+/=]{512,}", _replace, value)
    if len(value) > max_chars:
        value = value[:max_chars] + "... <truncated>"
    return value


def _read_json_response_or_raise(resp, label):
    """统一读取 JSON 响应：HTTP 错误 / 非 JSON 分别报错（spec §4.6 步骤 4）。"""
    status_code = getattr(resp, "status_code", 0)
    if status_code >= 400:
        raise RuntimeError(
            "%s失败: HTTP %s，响应片段: %s"
            % (label, status_code, _summarize_for_log(getattr(resp, "text", ""), 200))
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise RuntimeError(
            "%s返回的不是 JSON。HTTP %s，响应片段: %s"
            % (label, status_code, _summarize_for_log(getattr(resp, "text", ""), 200))
        ) from exc


# ==================== URL / 响应解析（模块级函数名对齐 spec §2） ====================

def _resolve_videos_submit_url(api_base_url):
    """拼提交端点 `{base}/v1/videos`。"""
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError(_MSG_INVALID_URL)
    if base.endswith("/videos"):
        return base
    if base.endswith("/v1") or "/v1/" in base:
        return base + "/videos"
    return urljoin(base + "/", "v1/videos")


def _resolve_videos_fetch_url(api_base_url, task_id):
    """拼轮询端点 `{base}/v1/videos/{task_id}`。"""
    return _resolve_videos_submit_url(api_base_url) + "/" + str(task_id)


def _absolutize_url(raw_url, endpoint):
    """相对地址补全（urljoin）；已是绝对地址原样返回。"""
    value = str(raw_url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")) or "://" in value:
        return value
    return urljoin(endpoint, value)


def _extract_video_url(values):
    """轮询响应抽视频地址：downloadUrl/download_url/video_url/content_url/url 依序尝试。"""
    if not isinstance(values, dict):
        return ""
    nodes = [values]
    for wrapper in ("data", "task_result", "result", "video"):
        nested = values.get(wrapper)
        if isinstance(nested, dict):
            nodes.insert(0, nested)
    for node in nodes:
        for key in ("downloadUrl", "download_url", "video_url", "videoUrl", "content_url", "url"):
            value = node.get(key)
            if isinstance(value, dict):
                value = value.get("url") or value.get("downloadUrl")
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _extract_task_id(payload):
    """提交响应抽任务 ID：taskId / task_id / id（兼容 data / task_result 包裹层）。"""
    if not isinstance(payload, dict):
        return ""
    nodes = [payload]
    for wrapper in ("data", "task_result", "result"):
        nested = payload.get(wrapper)
        if isinstance(nested, dict):
            nodes.insert(0, nested)
    for node in nodes:
        for key in ("taskId", "task_id", "id"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _extract_task_status(payload):
    """轮询响应抽状态（status 兜底 state）。"""
    if not isinstance(payload, dict):
        return ""
    data = payload.get("data")
    for node in (data if isinstance(data, dict) else None, payload):
        if isinstance(node, dict):
            status = node.get("status") or node.get("state")
            if status:
                return str(status)
    return ""


def _extract_fail_reason(payload):
    """失败消息：fail_reason / error / message，全部缺失时「未知错误」。"""
    if not isinstance(payload, dict):
        return _MSG_UNKNOWN_ERROR
    data = payload.get("data")
    for node in (data if isinstance(data, dict) else None, payload):
        if not isinstance(node, dict):
            continue
        for key in ("fail_reason", "failReason", "message", "error"):
            value = node.get(key)
            if isinstance(value, dict):
                value = value.get("message") or value.get("error") or ""
            if isinstance(value, str) and value.strip():
                return value.strip()
    return _MSG_UNKNOWN_ERROR


# ==================== 模型 / 尺寸归一化（模块级函数名对齐 spec §2） ====================

def _normalize_output_profile(value):
    """清晰度归一化：720p / 1080p / 4k（1080P、4K 等字面量统一归一）。"""
    text = str(value or "").strip().lower()
    if text in ("1080p", "1080"):
        return "1080p"
    if text in ("4k", "2160p"):
        return "4k"
    return "720p"


def _is_auto_video_option(value):
    """「auto」判定（spec §2 符号 _is_auto_video_option + 字面量 auto）。"""
    return str(value or "").strip().lower() == "auto"


def _resolve_video_size(aspect_ratio, output_profile):
    """比例 + 清晰度 → 六种尺寸字面量之一（spec 证据附录）。"""
    profile = _normalize_output_profile(output_profile)
    ratio = str(aspect_ratio or "16:9").strip()
    if _is_auto_video_option(ratio):
        ratio = "16:9"
    table = _VIDEO_SIZE_TABLE.get(profile, _VIDEO_SIZE_TABLE["720p"])
    size = table.get(ratio)
    if size is None:
        size = _VIDEO_SIZE_TABLE["720p"].get(ratio)
    if size is None:
        size = _VIDEO_SIZE_TABLE["720p"]["16:9"]
    return size


def _resolve_video_model(output_profile, model_variant, first_last_frame=False):
    """档位 → 模型名映射（_FAST_MODEL_NAME_* 常量；fl = 首尾帧变体）。"""
    variant = str(model_variant or _DEFAULT_MODEL_VARIANT).strip()
    if variant == _LITE_MODEL_VARIANT:
        return _LITE_MODEL_NAME
    if variant == "omni-flash":
        return _OMNI_FLASH_MODEL_NAME
    profile = _normalize_output_profile(output_profile)
    if profile == "1080p":
        return _FAST_MODEL_NAME_1080P_FL if first_last_frame else _FAST_MODEL_NAME_1080P
    if profile == "4k":
        return _FAST_MODEL_NAME_4K_FL if first_last_frame else _FAST_MODEL_NAME_4K
    return _FAST_MODEL_NAME_720P


def _uses_multipart_profile(output_profile, model_variant):
    """1080p/4K 档强制改走 multipart + input_reference[] 接口（tooltip 实锤）。"""
    variant = str(model_variant or _DEFAULT_MODEL_VARIANT).strip()
    if variant in (_LITE_MODEL_VARIANT, "omni-flash"):
        return False
    return _normalize_output_profile(output_profile) in ("1080p", "4k")


# ==================== 输入图处理 ====================

def _scale_image_tensor_to_total_pixels_if_needed(image_tensor, label="参考图"):
    """输入图按总像素自动缩放（仅当超过 _MAX_INPUT_IMAGE_MEGAPIXELS 时降采样）。"""
    if image_tensor is None:
        return None
    try:
        import torch  # 惰性导入
    except Exception:  # noqa: BLE001  非 torch 环境
        return image_tensor

    if not isinstance(image_tensor, torch.Tensor) or image_tensor.ndim < 3:
        return image_tensor
    height, width = int(image_tensor.shape[-3]), int(image_tensor.shape[-2])
    total = height * width
    limit = int(_MAX_INPUT_IMAGE_MEGAPIXELS * 1000 * 1000)
    if total <= limit:
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


def _encode_image_batch_to_data_urls(image_tensor, label="参考图"):
    """IMAGE 批 → Base64 data URI 列表（单路多张告警，只取第 1 张由调用方完成）。"""
    if image_tensor is None:
        raise ValueError("%s没有可用图像" % label)
    images = IMAGE_CODEC.extract_numpy_images(image_tensor)
    if not images:
        raise ValueError("%s没有可用图像" % label)
    if len(images) > 1:
        logger.warning("%s 只支持 1 张图，当前是 %d 张" % (label, len(images)))
    return [encode_numpy_image_to_api_data_url(image) for image in images]


def _encode_single_image_to_png_file_part(np_image, field_name, filename):
    """numpy 图 → multipart PNG 文件部件 (field_name, (filename, data, mime))。"""
    from io import BytesIO

    from PIL import Image

    images = IMAGE_CODEC.extract_numpy_images(np_image)
    if not images:
        raise ValueError("没有可用图像")
    pil_image = Image.fromarray(images[0])
    buffer = BytesIO()
    pil_image.save(buffer, format="PNG")
    return (field_name, (filename, buffer.getvalue(), "image/png"))


def _encode_image_batch_to_base64_list(image_tensor, label="参考图"):
    """IMAGE 批 → 裸 base64 列表（omni-flash referenceImagesBase64 字段用）。"""
    from io import BytesIO

    from PIL import Image

    if image_tensor is None:
        raise ValueError("%s没有可用图像" % label)
    images = IMAGE_CODEC.extract_numpy_images(image_tensor)
    if not images:
        raise ValueError("%s没有可用图像" % label)
    if len(images) > 1:
        logger.warning("%s 只支持 1 张图，当前是 %d 张" % (label, len(images)))
    results = []
    for image in images:
        pil_image = Image.fromarray(image)
        buffer = BytesIO()
        pil_image.save(buffer, format="PNG")
        results.append(base64.b64encode(buffer.getvalue()).decode("ascii"))
    return results


# ==================== VIDEO 输出包装 ====================

class _DownloadedVideoFromFile:
    """下载视频的 ComfyUI VIDEO 类型包装/回退保存器（spec §2/§4.5/§4.6 步骤 6）。

    Keep downloaded API videos usable when PyAV cannot stream-copy them.
    PyAV stream-copy 失败时保留原始 MP4 数据完成保存（shutil.copyfile 回退）。
    """

    def __init__(self, path, inner=None):
        self._path = str(path)
        self._inner = inner

    @property
    def file_path(self):
        return self._path

    def get_stream_source(self):
        """ComfyUI VIDEO 协议：优先委托 VideoFromFile，否则返回本地文件路径。"""
        if self._inner is not None:
            try:
                return self._inner.get_stream_source()
            except Exception:  # noqa: BLE001
                pass
        return self._path

    def save_to(self, path, format=None, codec=None, **kwargs):  # noqa: A002
        """保存视频；PyAV 二次封装失败时回退为原始 MP4 字节复制。"""
        full_path = str(path)
        if not os.path.isabs(full_path):
            resolved = ""
            try:
                import folder_paths  # 惰性导入，仅 ComfyUI 环境存在

                resolved = folder_paths.get_full_path("output", path) or ""
            except Exception:  # noqa: BLE001
                resolved = ""
            if not resolved:
                resolved = os.path.join(_get_output_dir(), str(path))
            full_path = resolved
        base_dir = os.path.dirname(full_path)
        if base_dir and not os.path.isdir(base_dir):
            os.makedirs(base_dir, exist_ok=True)
        if self._inner is not None:
            try:
                self._inner.save_to(full_path, format=format, codec=codec, **kwargs)
            except Exception as exc:  # noqa: BLE001  PyAV stream-copy 失败 → 保留原始 MP4
                logger.warning("PyAV 二次封装视频失败，已保留原始 MP4 数据完成保存: %s" % exc)
                self._copy_original_mp4(full_path)
        else:
            self._copy_original_mp4(full_path)
        if not os.path.isfile(full_path) or os.path.getsize(full_path) <= 0:
            raise RuntimeError("复制后的视频文件为空")
        logger.info("视频已保存: %s" % full_path)
        return full_path

    def _copy_original_mp4(self, full_path):
        """原始 MP4 字节复制回退（shutil.copyfile，保持下载原始数据可用）。"""
        temp_path = full_path + ".tmp_copy"
        shutil.copyfile(self._path, temp_path)
        os.replace(temp_path, full_path)

    def __getattr__(self, name):
        """其余 Video 协议方法（get_dimensions 等）委托给内部 VideoFromFile。"""
        if name.startswith("_") or self.__dict__.get("_inner") is None:
            raise AttributeError(name)
        return getattr(self.__dict__["_inner"], name)


def _make_video_from_file(path):
    """组装 VIDEO 输出：优先 VideoFromFile 内核，失败/缺失时回退纯字节复制包装。"""
    inner = None
    if _HAS_COMFY_VIDEO:
        for module_path in ("comfy_api.input_impl", "comfy_api.latest.input_impl"):
            try:
                module = __import__(module_path, fromlist=["VideoFromFile"])
                inner = module.VideoFromFile(path)
                break
            except Exception:  # noqa: BLE001
                inner = None
    return _DownloadedVideoFromFile(path, inner)


class BananaTEVeoVideoSafePyNode:
    """TE MAN VEO Video

    注册名: TE_image_pro_te_veo_video
    规格:   spec/TE_VEO_Video.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Veo'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO',)
    RETURN_NAMES = ('video',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只可爱的小狗在花园里玩耍', 'tooltip': '用于生成视频的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址不要带 /v1/videos）'}), 'aspect_ratio': (('16:9', '9:16'), {'default': '16:9', 'tooltip': '视频比例，对应接口参数 aspectRatio'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 2147483647, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'reference_image_1': ('IMAGE', {'tooltip': '多图参考 1。只接这一路时也会走参考图模式'}), 'reference_image_2': ('IMAGE', {'tooltip': '多图参考 2'}), 'reference_image_3': ('IMAGE', {'tooltip': '多图参考 3'}), 'first_frame_image': ('IMAGE', {'tooltip': '首帧参考。接入后不能再接多图参考输入'}), 'last_frame_image': ('IMAGE', {'tooltip': '尾帧参考。必须和首帧参考一起使用，不能单独使用'}), 'poll_interval_s': ('INT', {'default': 5, 'min': 2, 'max': 60, 'tooltip': '轮询间隔（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '清晰度': (('720p', '1080p'), {'default': '720p', 'tooltip': '默认 720p；1080p 改走 multipart + input_reference[] 接口。'}), '模型选择': (('veo 3.1 fast', 'veo3.1-lite', 'omni-flash'), {'default': 'veo 3.1 fast', 'tooltip': '选择要使用的视频生成模型。'}), '线路选择': (('线路1', '线路2'), {'default': '线路1', 'tooltip': '选择接口线路，默认使用线路1；如果某个线路不可用，可以切换其他线路尝试。'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 配置解析（spec §4.6 步骤 1） ====================

    def _resolve_key_and_url(self, api_key, api_base_url):
        """key/URL 缺省 → config.ini（[gemini] api_key / get_effective_api_base_url）。"""
        resolved_key = str(api_key or "").strip() or (CONFIG_MANAGER.load_api_key() or "")
        if not resolved_key:
            raise ValueError(_MSG_NO_KEY)
        url = (
            str(api_base_url or "").strip()
            or CONFIG_MANAGER.get_effective_api_base_url(_DEFAULT_BASE_URL)
        )
        if not url:
            raise ValueError(_MSG_NO_URL)
        logger.info("API Key: %s" % _masked_key(resolved_key))
        logger.info("API URL: [已脱敏]")
        return resolved_key, url

    # ==================== 模式判定与请求体组装 ====================

    @staticmethod
    def _collect_reference_tensors(kwargs):
        """收集参考图输入 → (reference_tensors, first_frame, last_frame)（保持 UI 顺序）。"""
        reference_tensors = [
            kwargs.get("reference_image_1"),
            kwargs.get("reference_image_2"),
            kwargs.get("reference_image_3"),
        ]
        return (
            [tensor for tensor in reference_tensors if tensor is not None],
            kwargs.get("first_frame_image"),
            kwargs.get("last_frame_image"),
        )

    @staticmethod
    def _validate_image_mode(reference_tensors, first_frame, last_frame):
        """互斥校验（spec §4.4/§4.6 步骤 2），返回模式名。"""
        has_first_frame = first_frame is not None
        has_last_frame = last_frame is not None
        has_reference_images = bool(reference_tensors)
        if has_last_frame and not has_first_frame:
            raise ValueError("尾帧参考不能单独使用，请同时接入首帧参考")
        if has_reference_images and (has_first_frame or has_last_frame):
            raise ValueError("多图参考模式与首帧/尾帧模式不能同时使用，请二选一")
        if len(reference_tensors) > 3:
            raise ValueError("参考图最多只支持 3 张")
        if has_first_frame and has_last_frame:
            return "首尾帧生视频"
        if has_first_frame:
            return "首帧生视频"
        if has_reference_images:
            return "参考图生视频"
        return "文生视频"

    def _build_route1_payload_and_files(self, mode, first_frame, last_frame, reference_tensors,
                                        model_name, model_variant, prompt, aspect_ratio,
                                        size, output_profile, uses_multipart):
        """线路1：720p 默认 JSON data URL；1080p/4K 档强制 multipart + input_reference[]。"""
        payload = {
            "model": model_name,
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "size": size,
        }
        if model_variant == "omni-flash":
            payload["duration"] = _OMNI_FLASH_DURATION  # omni-flash 固定 10 秒
        files = []
        if uses_multipart:
            if mode == "首帧生视频":
                files.append(_encode_single_image_to_png_file_part(
                    first_frame, "input_reference[]", "first_frame.png"
                ))
            elif mode == "首尾帧生视频":
                files.append(_encode_single_image_to_png_file_part(
                    first_frame, "input_reference[]", "first_frame.png"
                ))
                files.append(_encode_single_image_to_png_file_part(
                    last_frame, "input_reference[]", "last_frame.png"
                ))
            elif mode == "参考图生视频":
                for index, tensor in enumerate(reference_tensors, start=1):
                    files.append(_encode_single_image_to_png_file_part(
                        tensor, "input_reference[]", "reference_%d.png" % index
                    ))
            logger.info("图像提交: %d 张（multipart 文件）" % len(files))
            return payload, files
        if mode == "首帧生视频":
            payload["input_reference"] = _encode_image_batch_to_data_urls(
                first_frame, "首帧参考"
            )[0]
            logger.info("图像提交: 1 张（转 data URL）")
        elif mode == "首尾帧生视频":
            payload["input_references"] = [
                _encode_image_batch_to_data_urls(first_frame, "首帧参考")[0],
                _encode_image_batch_to_data_urls(last_frame, "尾帧参考")[0],
            ]
            logger.info("图像提交: 2 张（转 data URL）")
        elif mode == "参考图生视频":
            data_urls = []
            for index, tensor in enumerate(reference_tensors, start=1):
                data_urls.append(_encode_image_batch_to_data_urls(tensor, "参考图 %d" % index)[0])
            payload["input_references"] = data_urls
            logger.info("图像提交: %d 张（转 data URL）" % len(data_urls))
        return payload, files

    @staticmethod
    def _build_route2_payload(mode, first_frame, last_frame, reference_tensors,
                              model_variant, prompt, aspect_ratio, size):
        """线路2：veo fast 按 veo_3_1-fast JSON 格式；omni-flash 按 omni_flash-10s 格式。"""
        payload = {
            "prompt": prompt,
            "aspectRatio": aspect_ratio,
            "size": size,
        }
        if model_variant == "omni-flash":
            # omni-flash 线路2：omni_flash-10s JSON 格式，固定 duration=10
            payload["model"] = _OMNI_FLASH_MODEL_NAME
            payload["duration"] = _OMNI_FLASH_DURATION
            if mode in ("首帧生视频", "首尾帧生视频"):
                raise ValueError(
                    "omni-flash 线路2暂不支持首帧/首尾帧模式，请改用参考图输入 reference_image_1/2/3"
                )
            if mode == "参考图生视频":
                base64_values = []
                for index, tensor in enumerate(reference_tensors, start=1):
                    base64_values.extend(
                        _encode_image_batch_to_base64_list(tensor, "参考图 %d" % index)
                    )
                payload["referenceImagesBase64"] = base64_values
                logger.info("omni-flash 线路2模式: 图生视频参考图，images=%d 张" % len(base64_values))
            else:
                logger.info("线路2模式: 文生视频")
            return payload
        # veo 3.1 fast 线路2：veo_3_1-fast JSON 格式，首帧/首尾帧/参考图统一走 input_reference
        payload["model"] = "veo_3_1-fast"
        if mode == "首帧生视频":
            payload["input_reference"] = _encode_image_batch_to_data_urls(
                first_frame, "首帧参考"
            )[0]
            logger.info("veo 3.1 fast 线路2模式: 首帧按 input_reference 参考图提交")
        elif mode == "首尾帧生视频":
            payload["input_reference"] = _encode_image_batch_to_data_urls(
                first_frame, "首帧参考"
            )[0]
            logger.info("veo 3.1 fast 线路2模式: 首尾帧按 input_reference 多参考图提交")
            logger.warning(
                "veo 3.1 fast 线路2接口实际只接受单个 input_reference 字符串，"
                "已只使用第 1 张参考图，忽略其余 1 张"
            )
        elif mode == "参考图生视频":
            payload["input_reference"] = _encode_image_batch_to_data_urls(
                reference_tensors[0], "参考图 1"
            )[0]
            logger.info("线路2模式: 参考图生视频，input_reference=1 张")
            if len(reference_tensors) > 1:
                logger.warning(
                    "veo 3.1 fast 线路2接口实际只接受单个 input_reference 字符串，"
                    "已只使用第 1 张参考图，忽略其余 %d 张" % (len(reference_tensors) - 1)
                )
        else:
            logger.info("veo 3.1 fast 线路2模式: 文生视频")
        return payload

    # ==================== 提交 / 轮询（spec §4.6 步骤 4-5） ====================

    def _submit_task(self, session, api_key, submit_url, payload, files, timeout_s,
                     use_multipart=False):
        """POST {base}/v1/videos：720p JSON 提交 / 1080p multipart 提交，返回 task_id。"""
        headers = {"Authorization": "Bearer %s" % api_key, "User-Agent": _USER_AGENT}
        _ensure_not_interrupted()
        if use_multipart:
            logger.info("开始请求... POST /v1/videos（multipart + input_reference[]）")
            response = session.post(
                submit_url, data=payload, files=files or None, headers=headers,
                timeout=(15, timeout_s),
            )
        else:
            headers["Content-Type"] = "application/json"
            logger.info("开始请求... POST /v1/videos")
            logger.info("提交内容: %s" % _summarize_for_log(json.dumps(payload, ensure_ascii=False)))
            response = session.post(
                submit_url, json=payload, headers=headers, timeout=(15, timeout_s)
            )
        submit_resp = _read_json_response_or_raise(response, "提交任务")
        task_id = _extract_task_id(submit_resp)
        if not task_id:
            raise RuntimeError(
                "接口未返回 task_id：%s"
                % _summarize_for_log(json.dumps(submit_resp, ensure_ascii=False, default=str), 200)
            )
        return task_id

    def _poll_task_until_completed(self, session, api_key, fetch_url, submit_url,
                                   timeout_s, poll_interval_s):
        """GET {base}/v1/videos/{task_id} 轮询直至终态，返回下载地址。"""
        headers = {"Authorization": "Bearer %s" % api_key, "User-Agent": _USER_AGENT}
        started = time.monotonic()
        while True:
            _ensure_not_interrupted()
            elapsed = time.monotonic() - started
            if elapsed > timeout_s:
                raise RuntimeError("视频任务轮询超时（%d s）" % int(timeout_s))
            time.sleep(max(2.0, float(poll_interval_s)))
            try:
                resp = session.get(fetch_url, headers=headers, timeout=(15, 60))
                status_payload = _read_json_response_or_raise(resp, "查询任务")
            except Exception as exc:  # noqa: BLE001  单次查询失败不终止任务，继续轮询
                logger.warning("查询任务失败: %s" % exc)
                continue
            status = _extract_task_status(status_payload).lower()
            logger.info("任务状态: %s" % (status or "unknown"))
            if status in _VIDEO_DONE_STATUS:
                video_url = _absolutize_url(_extract_video_url(status_payload), submit_url)
                if not video_url:
                    raise RuntimeError("任务已完成，但未返回 video_url")
                return video_url
            if status in _VIDEO_FAILED_STATUS:
                raise RuntimeError("视频生成失败: %s" % _extract_fail_reason(status_payload))

    # ==================== 下载（spec §4.6 步骤 6） ====================

    def _download_video(self, session, video_url, api_key, timeout_s):
        """流式下载到 ComfyUI/output（te_veo_video_ 前缀），带进度条；返回本地路径。"""
        _ensure_not_interrupted()
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "User-Agent": _USER_AGENT,
            "Accept-Encoding": "identity",
        }
        logger.info("视频生成完成，正在下载视频...")
        logger.info("开始下载视频到 ComfyUI/output ...")
        output_dir = _get_output_dir()
        extension = os.path.splitext(os.path.basename(urlparse(video_url).path))[1]
        if not extension:
            extension = ".mp4"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, "%s%s%s" % (_OUTPUT_FILE_PREFIX, stamp, extension))
        counter = 1
        while os.path.exists(path):
            path = os.path.join(
                output_dir, "%s%s_%d%s" % (_OUTPUT_FILE_PREFIX, stamp, counter, extension)
            )
            counter += 1
        total = 0
        try:
            with session.get(
                video_url, headers=headers, stream=True, timeout=(15, timeout_s)
            ) as resp:
                status_code = getattr(resp, "status_code", 0)
                if status_code >= 400:
                    raise RuntimeError("下载视频失败: HTTP %s" % status_code)
                progress_bar = None
                try:
                    from comfy.utils import ProgressBar  # 惰性导入

                    content_length = int(resp.headers.get("Content-Length") or 0)
                    if content_length > 0:
                        progress_bar = ProgressBar(content_length)
                except Exception:  # noqa: BLE001  非 ComfyUI 环境
                    progress_bar = None
                with open(path, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        total += len(chunk)
                        if progress_bar is not None:
                            progress_bar.update(len(chunk))
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
        """TE_image_pro_te_veo_video：校验 → 提交 → 轮询 → 下载，返回 (VIDEO,)。"""
        logger.header("🎬 TE veo video 任务")
        _ensure_not_interrupted()
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(_MSG_EMPTY_PROMPT)
        model_variant = str(kwargs.get("模型选择") or _DEFAULT_MODEL_VARIANT).strip()
        requested_output_profile = str(kwargs.get("清晰度") or _DEFAULT_OUTPUT_PROFILE).strip()
        output_profile = _normalize_output_profile(requested_output_profile)
        route_choice = str(kwargs.get("线路选择") or "线路1").strip()
        aspect_ratio = str(kwargs.get("aspect_ratio") or "16:9").strip()
        # seed：仅供 ComfyUI 工作流使用，不写入请求体（tooltip 实锤）
        try:
            poll_interval_s = min(60, max(2, int(kwargs.get("poll_interval_s") or 5)))
        except (TypeError, ValueError):
            poll_interval_s = 5
        bypass_proxy = bool(kwargs.get("绕过代理"))

        # ---- 线路 / 清晰度的有效值归一（spec §4.3 回退提示原文） ----
        route_effective = route_choice
        if model_variant == _LITE_MODEL_VARIANT and route_choice != "线路1":
            route_effective = "线路1"
            logger.info("线路选择: %s (当前模型不使用该线路，已按线路1处理)" % route_choice)
        if model_variant == "omni-flash" and route_effective == "线路1":
            logger.info("线路选择: 线路1 (omni-flash 固定按 omni_flash-10s JSON 格式提交)")
        if model_variant == _LITE_MODEL_VARIANT:
            logger.info("清晰度: %s (当前模型不使用该档位)" % output_profile)
        else:
            logger.info("清晰度: %s" % output_profile)

        api_key, base_url = self._resolve_key_and_url(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        session = _build_session(bypass_proxy)

        # ---- 模式判定与互斥校验 ----
        reference_tensors, first_frame, last_frame = self._collect_reference_tensors(kwargs)
        for tensor in (first_frame, last_frame, *reference_tensors):
            _scale_image_tensor_to_total_pixels_if_needed(tensor)
        mode = self._validate_image_mode(reference_tensors, first_frame, last_frame)
        first_last_frame = (mode == "首尾帧生视频")
        model_name = _resolve_video_model(output_profile, model_variant, first_last_frame)
        size = _resolve_video_size(aspect_ratio, output_profile)
        logger.info("模式: %s" % mode)
        logger.info("模型选择: %s" % model_variant)
        logger.info("线路选择: %s" % route_effective)
        logger.info("Size: %s" % size)
        logger.info("Aspect Ratio: %s" % aspect_ratio)

        # ---- 组装请求体（线路1 JSON/multipart、线路2 两种 JSON 格式） ----
        uses_multipart = (
            route_effective == "线路1" and _uses_multipart_profile(output_profile, model_variant)
        )
        if route_effective == "线路2":
            payload = self._build_route2_payload(
                mode, first_frame, last_frame, reference_tensors,
                model_variant, prompt, aspect_ratio, size
            )
            files = []
        else:
            payload, files = self._build_route1_payload_and_files(
                mode, first_frame, last_frame, reference_tensors,
                model_name, model_variant, prompt, aspect_ratio, size,
                output_profile, uses_multipart
            )

        submit_url = _resolve_videos_submit_url(base_url)
        task_id = self._submit_task(
            session, api_key, submit_url, payload, files, _SUBMIT_TIMEOUT_S,
            use_multipart=uses_multipart,
        )
        logger.info("Task ID: %s" % task_id)
        fetch_url = _resolve_videos_fetch_url(base_url, task_id)
        video_url = self._poll_task_until_completed(
            session, api_key, fetch_url, submit_url,
            _POLL_TIMEOUT_S, poll_interval_s
        )
        video_path = self._download_video(session, video_url, api_key, _DOWNLOAD_TIMEOUT_S)
        video = _make_video_from_file(video_path)
        return (video,)

NODE_CLASS_MAPPINGS = {'TE_image_pro_te_veo_video': BananaTEVeoVideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_te_veo_video': 'TE MAN VEO Video'}
