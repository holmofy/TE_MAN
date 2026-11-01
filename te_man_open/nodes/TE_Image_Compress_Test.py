# -*- coding: utf-8 -*-
"""te_man_open · TE_Image_Compress_Test

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

import io
import math

try:
    from ..shared.image_codec import encode_pil_image_to_api_bytes
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 独立加载时兜底
    import logging

    logger = logging.getLogger("te_man_open")

    def encode_pil_image_to_api_bytes(pil_image):
        raise ImportError("te_man_open.shared.image_codec 不可用，请以 te_man_open 包形式导入")

#: 处理方式常量（动态 introspection 实锤，spec 回填节 (c)）
MODE_COMPRESS_ONLY = '只压缩'
MODE_SCALE_ONLY = '只缩放'
MODE_SCALE_AND_COMPRESS = '缩放+压缩'
MODE_OPTIONS = [MODE_COMPRESS_ONLY, MODE_SCALE_ONLY, MODE_SCALE_AND_COMPRESS]

#: ComfyUI 官方缩放方法（动态回填实锤）
OFFICIAL_SCALE_METHOD = 'nearest-exact'

#: 缩放目标百万像素（动态回填实锤：1.0，无用户输入参数，报告打印固定说明行）
DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS = 1.0
SCALE_TARGET_TEXT = '缩放目标: 约 1.0MP'

#: 压缩规则说明（原版字符串池原文）
COMPRESSION_RULE_TEXT = '压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG'


def _shape_to_hw_text(shape):
    """shape → "HxW" 类文本（genexpr 拼接，连接符 'x' 为原版字符串池词符）。"""
    return 'x'.join(str(int(value)) for value in shape)


def _kb_text(size_bytes):
    """字节数 → KB 文本（%.1f KB，词符 KB / round / .1f）。"""
    return '%.1f KB' % (float(size_bytes) / 1024.0)


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


def _png_size_bytes(pil_image):
    """PIL 图按 PNG 内存编码并返回字节数（仅体积探测，不用于输出编码）。"""
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG', optimize=True)
    return len(buffer.getvalue())


def _scale_sample_to_total_pixels_if_needed(pil_image):
    """总像素超过 DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS 时降采样到约目标像素。

    优先 ComfyUI 官方缩放 common_upscale（nearest-exact），
    失败/不可用回退 PIL Image.resize + Resampling.NEAREST（中文兜底日志）。
    返回 (缩放后 PIL 图, 是否发生了缩放)。
    """
    width, height = pil_image.size
    total_pixels = float(width) * float(height)
    target_pixels = DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS * 1000000.0
    if total_pixels <= target_pixels:
        return pil_image, False

    factor = math.sqrt(target_pixels / total_pixels)
    new_width = max(1, int(round(width * factor)))
    new_height = max(1, int(round(height * factor)))

    scaled = None
    try:
        import numpy as np
        import torch
        from PIL import Image
        from comfy.utils import common_upscale

        sample = np.asarray(pil_image.convert("RGB"), dtype=np.float32) / 255.0
        tensor = torch.from_numpy(sample).movedim(-1, 0).unsqueeze(0)  # [1,C,H,W]
        upscaled = common_upscale(tensor, new_width, new_height, OFFICIAL_SCALE_METHOD, 'disabled')
        arr = upscaled.squeeze(0).movedim(0, -1).cpu().numpy()
        scaled = Image.fromarray(
            np.clip(arr * 255.0 + 0.5, 0.0, 255.0).astype('uint8'), 'RGB'
        )
    except Exception as exc:  # noqa: BLE001  ImportError 与缩放异常统一兜底
        logger.warning('测试节点调用 ComfyUI 缩放失败，使用 PIL 最近邻备用缩放: %s' % exc)
        scaled = None

    if scaled is None:
        from PIL import Image

        try:
            resample = Image.Resampling.NEAREST
        except AttributeError:  # 老版本 Pillow
            resample = Image.NEAREST
        scaled = pil_image.convert('RGB').resize((new_width, new_height), resample)
    return scaled, True


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


class TEImageCompressTestNode:
    """TE MAN 图片缩放压缩测试

    注册名: TE_image_pro_compress_test
    规格:   spec/TE_Image_Compress_Test.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'process_image'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('处理后图片', '压缩报告')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'image': ('IMAGE',), '处理方式': (('只压缩', '只缩放', '缩放+压缩'), {'default': '只压缩'})}}
        # --8<-- 契约结束 --8<--

    def process_image(self, image=None, 处理方式=MODE_COMPRESS_ONLY, **kwargs):
        """三模式处理（只压缩/只缩放/缩放+压缩），输出 (IMAGE, STRING 压缩报告)。"""
        mode = 处理方式 or MODE_COMPRESS_ONLY
        do_scale = mode in (MODE_SCALE_ONLY, MODE_SCALE_AND_COMPRESS)
        do_compress = mode in (MODE_COMPRESS_ONLY, MODE_SCALE_AND_COMPRESS)

        import numpy as np
        import torch

        batch = _tensor_to_bhwc_array(image)
        output_samples = []
        report_sections = []
        for index, sample in enumerate(batch):
            pil_image = _sample_to_pil(sample)
            original_shape = (int(sample.shape[0]), int(sample.shape[1]))
            original_png_size = _png_size_bytes(pil_image)

            scaled = False
            after_scale_shape = None
            after_scale_png_size = None
            if do_scale:
                pil_image, scaled = _scale_sample_to_total_pixels_if_needed(pil_image)
                if scaled:
                    after_scale_shape = (int(pil_image.height), int(pil_image.width))
                    after_scale_png_size = _png_size_bytes(pil_image)

            final_size = original_png_size
            final_mime = 'image/png'
            if do_compress:
                pil_image, final_size, final_mime, _extension = _compress_sample_once_if_needed(pil_image)
            output_samples.append(_pil_to_rgb_sample(pil_image))

            lines = [
                '处理方式: ' + mode,
                SCALE_TARGET_TEXT,
                '  原图尺寸: ' + _shape_to_hw_text(original_shape),
                '  原图 PNG 体积: ' + _kb_text(original_png_size),
                '  是否缩放: ' + ('是' if scaled else '否'),
            ]
            if scaled:
                lines.append('  缩放后尺寸: ' + _shape_to_hw_text(after_scale_shape))
                lines.append('  缩放后 PNG 体积: ' + _kb_text(after_scale_png_size))
            lines.append('  最终模拟发送体积: ' + _kb_text(final_size))
            lines.append('  最终模拟发送格式: ' + final_mime)
            lines.append(COMPRESSION_RULE_TEXT)
            if len(batch) > 1:
                lines.insert(0, '图片 %d:' % (index + 1))
            report_sections.append('\n'.join(lines))

        output = torch.from_numpy(np.stack(output_samples).astype(np.float32))
        report = '\n\n'.join(report_sections)
        logger.info(
            'TE 图片缩放压缩测试完成: %d 张图片, 处理方式 %s' % (len(output_samples), mode)
        )
        return (output, report)

NODE_CLASS_MAPPINGS = {'TE_image_pro_compress_test': TEImageCompressTestNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_compress_test': 'TE MAN 图片缩放压缩测试'}
