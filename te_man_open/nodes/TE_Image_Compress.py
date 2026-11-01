# -*- coding: utf-8 -*-
"""te_man_open · TE_Image_Compress

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

import io

try:
    from ..shared.image_codec import encode_pil_image_to_api_bytes
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 独立加载时兜底
    import logging

    logger = logging.getLogger("te_man_open")

    def encode_pil_image_to_api_bytes(pil_image):
        raise ImportError("te_man_open.shared.image_codec 不可用，请以 te_man_open 包形式导入")


def _shape_to_hw_text(shape):
    """shape → "HxW" 类文本（genexpr 拼接，连接符 'x' 为原版字符串池词符）。"""
    return 'x'.join(str(int(value)) for value in shape)


def _tensor_to_bhwc_array(image):
    """IMAGE 张量 → float32 [B,H,W,C] 批次数组（维度校验失败抛中文 ValueError）。"""
    import numpy as np

    if hasattr(image, "detach"):  # torch.Tensor（不显式 import torch，避免多余依赖）
        tensor = image.detach()
        try:
            tensor = tensor.cpu()
        except Exception:  # noqa: BLE001  已在 CPU 时忽略
            pass
        arr = tensor.numpy()
    else:
        arr = np.asarray(image)

    arr = np.asarray(arr, dtype=np.float32)
    if arr.ndim == 3:
        arr = arr[np.newaxis, ...]  # 单张 [H,W,C] → [1,H,W,C]
    if arr.ndim != 4 or arr.shape[-1] < 3:
        raise ValueError("输入图像维度异常: " + str(arr.shape))
    if arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)
    return arr


def _sample_to_pil(sample):
    """单样本数组 → uint8 RGB PIL 图（0-1 / 0-255 幅值归一 + clip）。"""
    import numpy as np
    from PIL import Image

    arr = np.asarray(sample, dtype=np.float32)
    maxv = float(np.nanmax(arr)) if arr.size else 1.0
    if not np.isfinite(maxv) or maxv <= 0.0:
        maxv = 1.0
    scale = 1.0 if maxv <= 1.0 + 1e-6 else 255.0 / maxv
    arr = np.clip(arr * scale + 0.5, 0.0, 255.0).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    elif arr.shape[-1] == 1:
        arr = np.repeat(arr, 3, axis=-1)
    return Image.fromarray(np.ascontiguousarray(arr[:, :, :3]), "RGB")


def _pil_to_rgb_sample(pil_image):
    """PIL 图 → float32 0-1 RGB 单样本数组。"""
    import numpy as np

    arr = np.asarray(pil_image.convert("RGB"), dtype=np.float32) / 255.0
    return np.ascontiguousarray(arr)


def _compress_sample_once_if_needed(pil_image):
    """单样本"至多一次"按需压缩：encode_pil_image_to_api_bytes → 回读 PIL。

    返回 (PIL 图, 最终字节数, MIME, 扩展名)。
    """
    from PIL import Image

    data, mime, extension = encode_pil_image_to_api_bytes(pil_image)
    with io.BytesIO(data) as buffer:
        restored = Image.open(buffer)
        restored.load()
    return restored.convert("RGB"), len(data), mime, extension


class TEImageCompressNode:
    """TE MAN 图片压缩

    注册名: TE_image_pro_compress
    规格:   spec/TE_Image_Compress.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'compress_image'
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('压缩后图片',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'image': ('IMAGE',)}}
        # --8<-- 契约结束 --8<--

    def compress_image(self, image=None, **kwargs):
        """逐样本转 PIL → image_codec 按需压缩（PNG 超 1MB 单次 JPEG q90）→ 组回批量张量。"""
        import numpy as np
        import torch

        batch = _tensor_to_bhwc_array(image)
        output_samples = []
        total_final_bytes = 0
        final_mimes = []
        for sample in batch:
            pil_image = _sample_to_pil(sample)
            pil_image, final_size, final_mime, _extension = _compress_sample_once_if_needed(pil_image)
            total_final_bytes += final_size
            if final_mime not in final_mimes:
                final_mimes.append(final_mime)
            output_samples.append(_pil_to_rgb_sample(pil_image))

        output = torch.from_numpy(np.stack(output_samples).astype(np.float32))
        logger.info(
            'TE 图片压缩完成: 图片 %s -> %s, 最终模拟发送体积 %d KB, 格式 %s'
            % (
                _shape_to_hw_text(tuple(batch.shape[1:3])),
                _shape_to_hw_text(tuple(output.shape[1:3])),
                total_final_bytes // 1024,
                '/'.join(final_mimes),
            )
        )
        return (output,)

NODE_CLASS_MAPPINGS = {'TE_image_pro_compress': TEImageCompressNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_compress': 'TE MAN 图片压缩'}
