# -*- coding: utf-8 -*-
"""te_man_open.shared.image_codec —— image_codec.pyd 的纯 Python 复刻。

逆向规格: spec/image_codec.md（含末尾"动态 introspection 回填节"）。

原版自述（编译保留的类 docstring，运行时实锤）:
- ImageCodec: 负责 Tensor/Base64 转换、缓存与实时预览构建。
- ErrorCanvas: 统一的错误画布与字体管理。

实现约定:
- torch / PIL / numpy 一律惰性导入（函数内 import），
  模块顶层仅依赖标准库，保证无 ComfyUI/torch 环境下亦可加载。
- 与 comfy.model_management 的中断机制联动：try import，失败则 no-op。
"""

import base64
import hashlib
import logging
import os
import tempfile
import threading
import time
import uuid
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from typing import Callable, Dict, List, Optional, Tuple

__all__ = [
    "ImageCodec",
    "ErrorCanvas",
    "IMAGE_CODEC",
    "MODULE_DIR",
    "encode_pil_image_to_api_bytes",
    "encode_numpy_image_to_api_parts",
    "encode_numpy_image_to_api_data_url",
    "encode_numpy_image_to_api_file_part",
]

# ---------------------------------------------------------------------------
# 模块级常量（动态 introspection 实锤值，见 spec/image_codec.md 回填节 (b)）
# ---------------------------------------------------------------------------

#: 模块目录（原版真机值为插件目录，字体回退候选之一）
MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

#: 输入图压缩开关（默认 True）
_ENABLE_INPUT_IMAGE_COMPRESSION = True

#: 输入图压缩阈值（= 1 MiB，对应日志文案「输入图像超过1MB…」）
_INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES = 1048576

#: 单次 JPEG 压缩的质量因子
_INPUT_IMAGE_JPEG_QUALITY = 90

#: base64_to_tensor_parallel 的 worker 上限（原版数值未确认，取保守值）
_DECODE_WORKER_CAP = 8

#: MIME → 扩展名映射（表内字符串证据：image/png / image/jpeg / image/webp / image/gif）
_MIME_TO_EXTENSION: Dict[str, str] = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

_CODEC_LOGGER = logging.getLogger("te_man_open.image_codec")


def _log_codec_message(level, message, logger_instance=None):
    """统一的编解码日志输出。

    level 支持 logging 级别 int 或名称字符串（如 "INFO"）；
    logger_instance 允许消费方注入自带 logger。
    """
    logger = logger_instance if logger_instance is not None else _CODEC_LOGGER
    try:
        if isinstance(level, str):
            level = getattr(logging, level.upper(), logging.INFO)
        logger.log(level, message)
    except Exception:  # noqa: BLE001  日志永不影响主流程
        pass


def _rgba(color):
    """把 (r,g,b) / (r,g,b,a) 配色归一为 RGBA 四元组。"""
    color = tuple(color)
    if len(color) == 3:
        return color + (255,)
    return color


def _pil_save_bytes(pil_image, fmt, **save_kwargs):
    """PIL 图编码为指定格式字节。"""
    buffer = BytesIO()
    pil_image.save(buffer, format=fmt, **save_kwargs)
    return buffer.getvalue()


def _numpy_array_to_uint8_hwc(arr):
    """numpy 数组 → uint8 HWC（2 维灰度/单通道扩展，float 0-1 或 0-255 幅值归一）。"""
    import numpy as np

    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.ndim == 3 and arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)
    if arr.ndim != 3 or arr.shape[-1] not in (3, 4):
        raise ValueError("无法从 tensor 中提取有效图像数据")
    if arr.dtype != np.uint8:
        arr_f = arr.astype(np.float32)
        maxv = float(np.nanmax(arr_f)) if arr_f.size else 1.0
        if not np.isfinite(maxv) or maxv <= 0.0:
            maxv = 1.0
        scale = 1.0 if maxv <= 1.0 + 1e-6 else 255.0 / maxv
        arr = np.clip(arr_f * scale + 0.5, 0.0, 255.0).astype(np.uint8)
    return np.ascontiguousarray(arr)


def _coerce_numpy_to_pil(np_image):
    """numpy 数组 / PIL 图 → PIL.Image（惰性导入 numpy/PIL）。

    支持 2 维灰度、HWC/RGBA、float 0-1 或 0-255 幅值，统一转 uint8。
    """
    import numpy as np
    from PIL import Image

    if np_image is None:
        raise ValueError("必须提供 tensor 或 numpy 图像数据用于编码")
    if isinstance(np_image, Image.Image):
        return np_image
    arr = _numpy_array_to_uint8_hwc(np_image)
    mode = "RGBA" if arr.shape[-1] == 4 else "RGB"
    return Image.fromarray(arr, mode=mode)


def _pil_image_to_tensor(pil_image):
    """PIL 图 → float32 0-1 图像 tensor，形状 [1,H,W,C]（惰性导入 numpy/torch）。"""
    import numpy as np
    import torch

    arr = np.asarray(pil_image.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


# ---------------------------------------------------------------------------
# 模块级公开函数（名称取自 Cython 限定名串，spec §2.1）
# ---------------------------------------------------------------------------

def encode_pil_image_to_api_bytes(pil_image) -> Tuple[bytes, str, str]:
    """PIL 图 → (字节, MIME, 扩展名) 三元组。

    压缩规则（编译期常量，动态回填实锤）:
    - `_ENABLE_INPUT_IMAGE_COMPRESSION=True` 且 PNG 编码体积超过
      `_INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES`(1 MiB) 时，做**单次**
      JPEG(q=`_INPUT_IMAGE_JPEG_QUALITY`=90) 压缩；
    - JPEG 无体积收益 → 保留 PNG；
    - 压缩过程抛异常 → 保留 PNG（日志兜底）。
    """
    if pil_image is None:
        raise ValueError("必须提供 tensor 或 numpy 图像数据用于编码")
    png_bytes = _pil_save_bytes(pil_image, "PNG", optimize=True)
    if not _ENABLE_INPUT_IMAGE_COMPRESSION:
        return png_bytes, "image/png", ".png"
    if len(png_bytes) <= _INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES:
        return png_bytes, "image/png", ".png"

    png_kb = len(png_bytes) // 1024
    try:
        jpeg_source = pil_image if pil_image.mode in ("RGB", "L") else pil_image.convert("RGB")
        jpeg_bytes = _pil_save_bytes(
            jpeg_source,
            "JPEG",
            quality=_INPUT_IMAGE_JPEG_QUALITY,
            optimize=True,
            progressive=True,
        )
    except Exception as exc:  # noqa: BLE001
        _log_codec_message(logging.WARNING, "输入图像单次压缩失败，保留PNG: " + repr(exc))
        return png_bytes, "image/png", ".png"

    jpeg_kb = len(jpeg_bytes) // 1024
    if len(jpeg_bytes) < len(png_bytes):
        _log_codec_message(
            logging.INFO,
            "输入图像超过1MB，已单次JPEG压缩: PNG: %d KB -> JPEG: %d KB" % (png_kb, jpeg_kb),
        )
        return jpeg_bytes, "image/jpeg", ".jpg"
    _log_codec_message(
        logging.INFO,
        "输入图像超过1MB，但JPEG压缩收益不足，保留PNG: PNG: %d KB" % png_kb,
    )
    return png_bytes, "image/png", ".png"


def encode_numpy_image_to_api_file_part(
    np_image,
    field_name: str = "image",
    filename: Optional[str] = None,
    filename_prefix: str = "image",
) -> Tuple[str, str, str, bytes]:
    """numpy 图 → (field_name, filename, mime_type, bytes) 文件部件。"""
    pil_image = _coerce_numpy_to_pil(np_image)
    data, mime_type, extension = encode_pil_image_to_api_bytes(pil_image)
    if not filename:
        filename = "%s%s" % (filename_prefix, extension)
    return field_name, filename, mime_type, data


def encode_numpy_image_to_api_parts(
    np_image,
    field_name: str = "image",
    filename: Optional[str] = None,
    filename_prefix: str = "image",
) -> List[Tuple[str, Tuple[str, bytes, str]]]:
    """numpy 图 → API multipart parts（requests `files=` 参数格式）。

    返回 `[(field_name, (filename, data, mime_type)), ...]`。
    """
    part_field, part_filename, mime_type, data = encode_numpy_image_to_api_file_part(
        np_image, field_name=field_name, filename=filename, filename_prefix=filename_prefix
    )
    return [(part_field, (part_filename, data, mime_type))]


def encode_numpy_image_to_api_data_url(np_image) -> str:
    """numpy 图 → `data:{mime};base64,{b64}` URL。"""
    pil_image = _coerce_numpy_to_pil(np_image)
    data, mime_type, _extension = encode_pil_image_to_api_bytes(pil_image)
    base64_value = base64.b64encode(data).decode("ascii")
    return "data:%s;base64,%s" % (mime_type or "image/png", base64_value)


# ---------------------------------------------------------------------------
# ImageCodec
# ---------------------------------------------------------------------------

class ImageCodec:
    """负责 Tensor/Base64 转换、缓存与实时预览构建。"""

    def __init__(self, cache_size: int = 64):
        self._cache_size = max(1, int(cache_size))
        self._image_cache: "OrderedDict[str, Tuple[str, str]]" = OrderedDict()
        self._cache_lock = threading.Lock()

    # -- 中断联动 -----------------------------------------------------------

    def _maybe_interrupt(self) -> None:
        """检查 ComfyUI 中断挂起状态；comfy 不可用时 no-op。

        中断挂起时由 comfy.model_management 抛出 InterruptProcessingException，
        本方法不吞异常、直接向上传播。
        """
        try:
            from comfy import model_management  # 惰性导入
        except Exception:  # noqa: BLE001  非 ComfyUI 环境
            return
        throw = getattr(model_management, "throw_exception_if_interrupted", None)
        if callable(throw):
            throw()
            return
        ensure = getattr(model_management, "ensure_not_interrupted", None)
        if callable(ensure):
            ensure()

    # -- LRU base64 缓存 ----------------------------------------------------

    def _tensor_cache_key(self, tensor) -> str:
        """tensor → 缓存键（shape + dtype + 原始字节的 sha256 hexdigest）。"""
        import torch

        if isinstance(tensor, torch.Tensor):
            t = tensor.detach()
            if t.device.type != "cpu":
                t = t.cpu()
            t = t.contiguous()
            digest = hashlib.sha256()
            digest.update(str(tuple(t.shape)).encode("utf-8"))
            digest.update(str(t.dtype).encode("utf-8"))
            digest.update(t.numpy().tobytes())
            return digest.hexdigest()
        return hashlib.sha256(repr(tensor).encode("utf-8", "replace")).hexdigest()

    def _get_cached_image_b64(self, cache_key: str) -> Optional[Tuple[str, str]]:
        """LRU 读缓存，命中则 move_to_end。缓存值为 (mime_type, base64)。"""
        with self._cache_lock:
            value = self._image_cache.get(cache_key)
            if value is not None:
                self._image_cache.move_to_end(cache_key)
            return value

    def _set_cached_image_b64(self, cache_key: str, value: Tuple[str, str]) -> None:
        """LRU 写缓存，超容量按 FIFO 淘汰。"""
        with self._cache_lock:
            self._image_cache[cache_key] = value
            self._image_cache.move_to_end(cache_key)
            while len(self._image_cache) > self._cache_size:
                self._image_cache.popitem(last=False)

    # -- tensor → numpy -----------------------------------------------------

    def extract_numpy_images(self, tensor) -> List:
        """tensor 批次 → uint8 HWC numpy 数组列表（惰性导入 numpy/torch）。"""
        import numpy as np
        import torch

        if tensor is None:
            raise ValueError("必须提供 tensor 或 numpy 图像数据用于编码")

        if isinstance(tensor, np.ndarray):
            return [_numpy_array_to_uint8_hwc(tensor)]
        if isinstance(tensor, (list, tuple)):
            images: List = []
            for item in tensor:
                images.extend(self.extract_numpy_images(item))
            return images

        if not isinstance(tensor, torch.Tensor):
            raise ValueError("无法从 tensor 中提取有效图像数据")

        frames = tensor.detach()
        if frames.ndim == 2:  # 单通道 mask [H,W]
            frames = frames.unsqueeze(-1).unsqueeze(0)
        elif frames.ndim == 3:  # 单张图 [H,W,C]
            frames = frames.unsqueeze(0)
        elif frames.ndim != 4:  # 批次 [B,H,W,C]
            raise ValueError("无法从 tensor 中提取有效图像数据")

        images = []
        for frame in frames:
            frame = frame.to(torch.float32)
            frame = torch.nan_to_num(frame, nan=0.0, posinf=1.0, neginf=0.0)
            maxv = float(torch.nanmax(frame)) if frame.numel() else 1.0
            if maxv > 1.0 + 1e-6:
                frame = frame / maxv  # 兼容 0-255 等任意幅值输入
            frame = frame.clamp(0.0, 1.0)
            arr = frame.mul(255.0).round().to(torch.uint8).cpu().numpy()
            if arr.ndim == 2:
                arr = np.stack([arr] * 3, axis=-1)
            elif arr.shape[-1] == 1:
                arr = np.repeat(arr, 3, axis=-1)
            images.append(np.ascontiguousarray(arr))
        if not images:
            raise ValueError("无法从 tensor 中提取有效图像数据")
        return images

    # -- 编码 ---------------------------------------------------------------

    def _pil_to_api_image_bytes(self, pil_image) -> Tuple[bytes, str, str]:
        """PIL 图按 MIME 编码为 (字节, MIME, 扩展名)，含 1MB 单次 JPEG 压缩规则。"""
        return encode_pil_image_to_api_bytes(pil_image)

    def _np_image_to_api_image(self, np_image) -> Optional[Tuple[str, object, int]]:
        """numpy → (MIME/格式, PIL 图, quality)。

        超过压缩阈值时计划走 JPEG(q=_INPUT_IMAGE_JPEG_QUALITY)，否则 PNG。
        """
        from PIL import Image  # noqa: F401  惰性导入

        pil_image = _coerce_numpy_to_pil(np_image)
        quality = _INPUT_IMAGE_JPEG_QUALITY
        if _ENABLE_INPUT_IMAGE_COMPRESSION:
            png_bytes = _pil_save_bytes(pil_image, "PNG", optimize=True)
            if len(png_bytes) > _INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES:
                return "image/jpeg", pil_image, quality
        return "image/png", pil_image, quality

    @staticmethod
    def _data_url_from_parts(base64_value: str, mime_type: str) -> str:
        """拼接 `data:{mime};base64,{b64}`。"""
        return "data:%s;base64,%s" % (mime_type or "image/png", base64_value)

    @staticmethod
    def _split_data_url(data_url: str) -> Tuple[str, str]:
        """data URL → (mime_type, base64_value)；非法输入抛 ValueError。"""
        value = str(data_url or "")
        if not value.startswith("data:"):
            raise ValueError("非法 data URL: 缺少 'data:' 前缀")
        body = value[len("data:"):]
        marker = ";base64,"
        if marker not in body:
            raise ValueError("非法 data URL: 缺少 ';base64,' 标记")
        mime_type, base64_value = body.split(marker, 1)
        return (mime_type or "image/png"), base64_value

    @staticmethod
    def _extension_from_mime(mime_type: str) -> str:
        """MIME → 扩展名（image/png / image/jpeg / image/webp / image/gif）。"""
        mime = (mime_type or "").split(";")[0].strip().lower()
        if mime in _MIME_TO_EXTENSION:
            return _MIME_TO_EXTENSION[mime]
        subtype = mime.rsplit("/", 1)[-1] if "/" in mime else ""
        return ("." + subtype) if subtype else ".png"

    def tensor_to_base64(self, tensor) -> str:
        """torch tensor → base64 字符串（走 LRU 缓存）。

        批次 tensor 仅编码第一张（多张场景请使用 prepare_input_images 系列）。
        """
        cache_key = self._tensor_cache_key(tensor)
        cached = self._get_cached_image_b64(cache_key)
        if cached is not None:
            return cached[1]

        images = self.extract_numpy_images(tensor)
        if len(images) > 1:
            _log_codec_message(
                logging.DEBUG,
                "tensor_to_base64: 批次含 %d 张图，仅编码第 1 张" % len(images),
            )
        data, mime_type, _extension = encode_pil_image_to_api_bytes(
            _coerce_numpy_to_pil(images[0])
        )
        base64_value = base64.b64encode(data).decode("ascii")
        self._set_cached_image_b64(cache_key, (mime_type, base64_value))
        return base64_value

    def tensor_to_data_url(self, tensor) -> str:
        """torch tensor → `data:{mime};base64,{b64}`（走 LRU 缓存）。"""
        cache_key = self._tensor_cache_key(tensor)
        cached = self._get_cached_image_b64(cache_key)
        if cached is not None:
            return self._data_url_from_parts(cached[1], cached[0])

        images = self.extract_numpy_images(tensor)
        if len(images) > 1:
            _log_codec_message(
                logging.DEBUG,
                "tensor_to_data_url: 批次含 %d 张图，仅编码第 1 张" % len(images),
            )
        data, mime_type, _extension = encode_pil_image_to_api_bytes(
            _coerce_numpy_to_pil(images[0])
        )
        base64_value = base64.b64encode(data).decode("ascii")
        self._set_cached_image_b64(cache_key, (mime_type, base64_value))
        return self._data_url_from_parts(base64_value, mime_type)

    # -- 批量准备输入图 ------------------------------------------------------

    def _iter_numpy_images(self, tensors) -> List:
        """tensors（批次 tensor / ndarray / list / PIL）→ uint8 HWC numpy 列表。"""
        import numpy as np
        from PIL import Image

        if tensors is None:
            raise ValueError("必须提供 tensor 或 numpy 图像数据用于编码")
        import torch  # 惰性导入

        if isinstance(tensors, torch.Tensor):
            return self.extract_numpy_images(tensors)
        if isinstance(tensors, np.ndarray):
            return self.extract_numpy_images(
                torch.from_numpy(np.ascontiguousarray(tensors))
            )

        images: List = []
        items = tensors if isinstance(tensors, (list, tuple)) else [tensors]
        for item in items:
            if isinstance(item, torch.Tensor):
                images.extend(self.extract_numpy_images(item))
            elif isinstance(item, np.ndarray):
                images.extend(self.extract_numpy_images(item))
            elif isinstance(item, Image.Image):
                images.append(np.ascontiguousarray(np.asarray(item)))
            else:
                raise ValueError("必须提供 tensor 或 numpy 图像数据用于编码")
        if not images:
            raise ValueError("必须提供 tensor 或 numpy 图像数据用于编码")
        return images

    def prepare_input_images(self, tensors, filename_prefix: str = "image") -> List[Tuple[bytes, str, str]]:
        """批量准备输入图 → [(data, mime_type, extension), ...]（含压缩逻辑）。"""
        encoded: List[Tuple[bytes, str, str]] = []
        for index, image in enumerate(self._iter_numpy_images(tensors)):
            try:
                encoded.append(encode_pil_image_to_api_bytes(_coerce_numpy_to_pil(image)))
            except Exception as exc:  # noqa: BLE001
                _log_codec_message(
                    logging.ERROR,
                    "%s[%d] 编码失败: %s" % (filename_prefix, index, exc),
                )
                raise
        return encoded

    def prepare_input_image_data_urls(self, tensors, filename_prefix: str = "image") -> List[str]:
        """批量准备输入图 → data URL 列表。"""
        data_urls: List[str] = []
        for image in self._iter_numpy_images(tensors):
            data, mime_type, _extension = encode_pil_image_to_api_bytes(
                _coerce_numpy_to_pil(image)
            )
            base64_value = base64.b64encode(data).decode("ascii")
            data_urls.append(self._data_url_from_parts(base64_value, mime_type))
        return data_urls

    def prepare_input_image_file_parts(
        self,
        tensors,
        field_name: str = "image",
        filename_prefix: str = "image",
    ) -> List[Tuple[str, Tuple[str, bytes, str]]]:
        """批量准备输入图 → API 文件部件（requests `files=` 参数格式）。

        返回 `[(field_name, (filename, data, mime_type)), ...]`。
        """
        parts: List[Tuple[str, Tuple[str, bytes, str]]] = []
        for index, image in enumerate(self._iter_numpy_images(tensors)):
            data, mime_type, extension = encode_pil_image_to_api_bytes(
                _coerce_numpy_to_pil(image)
            )
            filename = "%s_%d%s" % (filename_prefix, index, extension)
            parts.append((field_name, (filename, data, mime_type)))
        return parts

    # -- base64 → tensor ----------------------------------------------------

    def base64_to_tensor_single(self, b64_str: str):
        """单张 base64（或 data URL）→ float32 0-1 图像 tensor [1,H,W,C]。"""
        import numpy as np
        import torch
        from PIL import Image

        try:
            value = str(b64_str or "")
            if value.startswith("data:"):
                _mime_type, value = self._split_data_url(value)
            raw = base64.b64decode(value, validate=False)
            pil_image = Image.open(BytesIO(raw))
            pil_image.load()
            arr = np.asarray(pil_image.convert("RGB"), dtype=np.float32) / 255.0
            return torch.from_numpy(arr).unsqueeze(0)
        except Exception as exc:  # noqa: BLE001
            _log_codec_message(logging.ERROR, "图片解码失败: " + repr(exc))
            raise ValueError("图片解码失败: %s" % exc) from exc

    def base64_to_tensor_parallel(self, base64_strings, max_workers: Optional[int] = None, log_prefix: str = "") -> List:
        """并行批量解码 base64 → List[torch.Tensor]。

        effective_workers = min(max_workers, cpu_count, worker_cap)；
        任一解码失败 / 触发中断时取消剩余任务并向上抛出。
        """
        import torch  # noqa: F401  惰性导入（保证返回类型可用性检查一致）

        items = list(base64_strings or [])
        if not items:
            return []

        cpu_count = os.cpu_count() or 1
        worker_cap = _DECODE_WORKER_CAP
        effective_workers = max(1, min(max_workers or cpu_count, cpu_count, worker_cap))

        decode_start = time.perf_counter()
        results: List[Optional[torch.Tensor]] = [None] * len(items)
        executor = ThreadPoolExecutor(
            max_workers=effective_workers, thread_name_prefix="TEManDecode"
        )
        try:
            future_to_index = {
                executor.submit(self.base64_to_tensor_single, item): index
                for index, item in enumerate(items)
            }
            failure = None
            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    results[index] = future.result()
                except Exception as exc:  # noqa: BLE001
                    failure = exc
                    break
                self._maybe_interrupt()
            if failure is not None:
                raise failure
            for future in future_to_index:
                future.cancel()
        finally:
            try:
                executor.shutdown(wait=True, cancel_futures=True)
            except TypeError:  # Python < 3.9
                executor.shutdown(wait=True)

        decode_time = time.perf_counter() - decode_start
        _log_codec_message(
            logging.INFO,
            "%s%d 张图片完成，耗时: %.2fs" % (log_prefix, len(items), decode_time),
        )
        return results

    # -- 实时预览 -----------------------------------------------------------

    @staticmethod
    def _save_temp_preview(pil_image) -> Optional[Dict[str, str]]:
        """把预览图写入 ComfyUI temp 目录（不可用时退回系统临时目录）。"""
        filename = "TE_MAN_preview_%s.png" % uuid.uuid4().hex[:8]
        temp_dir = None
        try:
            import folder_paths  # 仅 ComfyUI 环境存在

            temp_dir = folder_paths.get_temp_directory()
        except Exception:  # noqa: BLE001
            temp_dir = os.path.join(tempfile.gettempdir(), "te_man_open_preview")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            pil_image.save(os.path.join(temp_dir, filename), format="PNG")
        except Exception:  # noqa: BLE001
            return None
        return {"filename": filename, "subfolder": "", "type": "temp"}

    def build_preview_tuple(self, tensor, batch_index: int = 0, max_size: int = 512) -> Optional[Dict]:
        """生成 ComfyUI 实时预览 tuple（`{"ui": {"images": [...]}}`）。

        batch_index 选择批次中的第几张；max_size 限制预览最长边。
        失败时记录「实时预览生成失败: 批次 N」并返回 None，
        消费方可据此走 ErrorCanvas 输出可视化错误图。
        """
        try:
            from PIL import Image

            images = self.extract_numpy_images(tensor)
            if not images:
                return None
            index = int(batch_index) % len(images)
            pil_image = Image.fromarray(images[index])
            if max_size and max(pil_image.size) > int(max_size):
                pil_image.thumbnail((int(max_size), int(max_size)))
            file_info = self._save_temp_preview(pil_image)
            if file_info is None:
                return None
            return {"ui": {"images": [file_info]}}
        except Exception as exc:  # noqa: BLE001
            _log_codec_message(
                logging.ERROR, "实时预览生成失败: 批次 %s: %s" % (batch_index, exc)
            )
            return None


#: 模块级单例（原版各节点共享同一编解码器与缓存）
IMAGE_CODEC = ImageCodec()


# ---------------------------------------------------------------------------
# ErrorCanvas
# ---------------------------------------------------------------------------

class ErrorCanvas:
    """统一的错误画布与字体管理。"""

    def __init__(self, max_size: int = 768):
        self._max_size = max(160, int(max_size))
        self._font_cache: "OrderedDict[int, object]" = OrderedDict()
        self._font_lock = threading.Lock()
        self._font_cache_size = 8
        self._image_cache: "OrderedDict[str, object]" = OrderedDict()
        self._image_lock = threading.Lock()
        self._image_cache_size = 16

    # -- 字体管理 -----------------------------------------------------------

    def _get_error_font_paths(self) -> List[str]:
        """逐候选收集中文字体路径（存在性过滤）。

        Windows: %WINDIR%\\Fonts 的 msyh/msjh/simhei/msmincho；
        macOS: /System/Library/Fonts 的 PingFang/STHeiti；
        Linux: 文泉驿 / Noto CJK 常见路径；
        最后附 MODULE_DIR 下随包字体目录（原版 MODULE_DIR 回退候选）。
        """
        candidates: List[str] = []

        windir = os.environ.get("WINDIR") or os.environ.get("windir")
        if windir:
            fonts_dir = os.path.join(windir, "Fonts")
            for name in ("msyh.ttc", "msyh.ttf", "msjh.ttc", "simhei.ttf", "msmincho.ttc"):
                candidates.append(os.path.abspath(os.path.join(fonts_dir, name)))

        mac_fonts = "/System/Library/Fonts"
        for name in (
            "PingFang.ttc",
            "STHeiti Light.ttc",
            "STHeiti Medium.ttc",
            "Hiragino Sans GB.ttc",
        ):
            candidates.append(os.path.join(mac_fonts, name))

        for path in (
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/noto-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/google-noto-sans-cjk/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/arphic/uming.ttc",
        ):
            candidates.append(path)

        for name in ("fonts/msyh.ttc", "fonts/simhei.ttf", "fonts/NotoSansSC-Regular.otf"):
            candidates.append(os.path.abspath(os.path.join(MODULE_DIR, name)))

        return [path for path in candidates if os.path.exists(path)]

    def _load_error_font(self, size: int = 18):
        """逐候选 ImageFont.truetype 加载，全部失败回退 load_default（带缓存）。"""
        key = max(1, int(size))
        with self._font_lock:
            cached = self._font_cache.get(key)
            if cached is not None:
                self._font_cache.move_to_end(key)
                return cached

        from PIL import ImageFont

        font = None
        for path in self._get_error_font_paths():
            try:
                font = ImageFont.truetype(path, key)
                break
            except Exception:  # noqa: BLE001
                continue
        if font is None:
            try:
                font = ImageFont.load_default(key)  # Pillow >= 10.1 支持字号
            except TypeError:
                font = ImageFont.load_default()

        with self._font_lock:
            self._font_cache[key] = font
            self._font_cache.move_to_end(key)
            while len(self._font_cache) > self._font_cache_size:
                self._font_cache.popitem(last=False)
        return font

    # -- 文本排版 -----------------------------------------------------------

    def _wrap_text_segments(self, draw, text, font, max_width: int) -> List[str]:
        """按像素宽度折行（textlength 测量，逐字符累积，兼容 CJK）。"""
        wrapped: List[str] = []
        for raw in str(text or "").splitlines() or [""]:
            stripped = raw.rstrip()
            if not stripped:
                wrapped.append("")
                continue
            current = ""
            for ch in stripped:
                candidate = current + ch
                try:
                    width = draw.textlength(candidate, font=font)
                except Exception:  # noqa: BLE001  老版本 Pillow 兜底
                    try:
                        width = font.getlength(candidate)
                    except Exception:  # noqa: BLE001
                        width = len(candidate) * float(getattr(font, "size", 16)) * 0.6
                if width <= max_width or not current:
                    current = candidate
                else:
                    wrapped.append(current)
                    current = ch
            if current:
                wrapped.append(current)
        return wrapped

    # -- 缓存 ---------------------------------------------------------------

    def _get_cached_tensor(self, cache_key: str):
        with self._image_lock:
            value = self._image_cache.get(cache_key)
            if value is not None:
                self._image_cache.move_to_end(cache_key)
            return value

    def _set_cached_tensor(self, cache_key: str, value) -> None:
        with self._image_lock:
            self._image_cache[cache_key] = value
            self._image_cache.move_to_end(cache_key)
            while len(self._image_cache) > self._image_cache_size:
                self._image_cache.popitem(last=False)

    # -- 错误画布 -----------------------------------------------------------

    def build_error_image_tensor(
        self,
        title: str,
        lines,
        background=(18, 20, 26),
        title_color=(255, 96, 96),
        text_color=(226, 228, 235),
        accent=(255, 96, 96),
    ):
        """用 PIL 绘制错误信息画布 → 图像 tensor（float32 0-1, [1,H,W,C]）。

        配色: background / title_color / text_color / accent；
        排版: font_title / font_body / line_height / margin / max_text_width / max_y。
        """
        import numpy as np
        import torch
        from PIL import Image, ImageDraw

        title_text = str(title or "TE MAN 错误")
        body_lines = [str(line) for line in (lines if lines is not None else [])] or ["未知错误"]

        cache_key = hashlib.sha1(
            (title_text + "\x00" + "\x00".join(body_lines) + "\x00%d" % self._max_size).encode(
                "utf-8", "replace"
            )
        ).hexdigest()
        cached = self._get_cached_tensor(cache_key)
        if cached is not None:
            return cached

        margin = 28
        width = max(320, int(self._max_size))
        font_title = self._load_error_font(26)
        font_body = self._load_error_font(18)

        # 先在临时画布上测量折行
        measure_img = Image.new("RGBA", (width, 8))
        measure_draw = ImageDraw.ImageDraw(measure_img)
        max_text_width = width - margin * 2
        wrapped_title = self._wrap_text_segments(measure_draw, title_text, font_title, max_text_width)
        wrapped_body: List[str] = []
        for line in body_lines:
            wrapped_body.extend(self._wrap_text_segments(measure_draw, line, font_body, max_text_width))

        title_line_height = int(float(getattr(font_title, "size", 26)) * 1.45)
        body_line_height = int(float(getattr(font_body, "size", 18)) * 1.5)
        height = (
            margin * 2
            + title_line_height * max(1, len(wrapped_title))
            + 26
            + body_line_height * max(1, len(wrapped_body))
        )
        height = max(120, height)
        max_y = height - margin

        canvas = Image.new("RGBA", (width, height), _rgba(background))
        draw = ImageDraw.ImageDraw(canvas)
        draw.rectangle([0, 0, width - 1, height - 1], outline=_rgba(accent), width=2)

        y = margin
        for segment in wrapped_title:
            draw.text((margin, y), segment, font=font_title, fill=_rgba(title_color))
            y += title_line_height

        # accent 分隔条画在独立图层后 alpha_composite
        divider = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        divider_draw = ImageDraw.ImageDraw(divider)
        divider_draw.rectangle([margin, y + 6, width - margin, y + 8], fill=_rgba(accent))
        canvas = Image.alpha_composite(canvas, divider)
        draw = ImageDraw.ImageDraw(canvas)

        y += 26
        for segment in wrapped_body:
            if y > max_y - body_line_height:
                draw.text(
                    (margin, max(margin, max_y - body_line_height)),
                    "…",
                    font=font_body,
                    fill=_rgba(text_color),
                )
                break
            draw.text((margin, y), segment, font=font_body, fill=_rgba(text_color))
            y += body_line_height

        arr = np.asarray(canvas.convert("RGB"), dtype=np.float32) / 255.0
        tensor = torch.from_numpy(arr).unsqueeze(0)
        self._set_cached_tensor(cache_key, tensor)
        return tensor

    def build_error_tensor_from_text(self, text, title: str = "TE MAN 请求错误"):
        """由文本直接构建错误 tensor（API 出错时输出可视化错误图）。"""
        body = [line for line in str(text or "").splitlines() if line.strip()] or ["未知错误"]
        return self.build_error_image_tensor(title, body)
