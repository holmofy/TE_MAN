# -*- coding: utf-8 -*-
"""te_man_open · TE_Image_Comparer

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

import os

#: 随机后缀字符表（原版字符串池原样保留：缺 w 且 u 重复，spec §3）
_RANDOM_SUFFIX_CHARS = 'abcdefghijklmnopqrstupvxyz'

#: 随机后缀长度（原版 range(N) 的 N 未确认，取 5）
_RANDOM_SUFFIX_LENGTH = 5

#: temp 落盘文件名前缀（原版字符串池原文）
_FILENAME_PREFIX = 'te_man_compare.'


def _get_temp_directory():
    """ComfyUI temp 输出目录；不可用时退回系统临时目录。"""
    try:
        import folder_paths  # 仅 ComfyUI 环境存在

        return folder_paths.get_temp_directory()
    except Exception:  # noqa: BLE001
        import tempfile

        return os.path.join(tempfile.gettempdir(), 'te_man_open_compare')


class TEMANImageComparerNode:
    """TE MAN 图像对比

    注册名: TE_image_pro_image_comparer
    规格:   spec/TE_Image_Comparer.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'compare_images'
    OUTPUT_NODE = True
    DESCRIPTION = '在节点内叠加显示两张图片，可拖动分界线进行对比。'
    RETURN_TYPES = ()
    RETURN_NAMES = ()

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {}, 'optional': {'image_a': ('IMAGE', {'tooltip': '对比图片 A（可选）'}), 'image_b': ('IMAGE', {'tooltip': '对比图片 B（可选）'})}, 'hidden': {'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def compare_images(self, image_a=None, image_b=None, prompt=None, extra_pnginfo=None, **kwargs):
        """仿 SaveImage 把 A/B 两批图片写入 temp 目录，返回 ui.images 供前端对比显示。

        文件名形如 ``te_man_compare.<随机后缀>.png``（随机后缀防撞名）；
        prompt / extra_pnginfo 按 SaveImage 惯例写入 PNG 文本元数据。
        OUTPUT_NODE 型节点：无 result tuple，仅返回 ``{"ui": {"images": [...]}}``。
        """
        import json
        import random

        import numpy as np
        from PIL import PngImagePlugin

        output_dir = _get_temp_directory()
        os.makedirs(output_dir, exist_ok=True)

        pnginfo = None
        if prompt is not None or extra_pnginfo is not None:
            pnginfo = PngImagePlugin.PngInfo()
            if prompt is not None:
                pnginfo.add_text('prompt', json.dumps(prompt))
            if isinstance(extra_pnginfo, dict):
                for key, value in extra_pnginfo.items():
                    pnginfo.add_text(key, json.dumps(value))

        results = []

        def _save_batch(image_tensor):
            import torch
            from PIL import Image

            if image_tensor is None:
                return
            if isinstance(image_tensor, torch.Tensor):
                frames = image_tensor.detach().cpu().numpy()
            else:
                frames = np.asarray(image_tensor)
            if frames.ndim == 3:
                frames = frames[np.newaxis, ...]
            for frame in frames:
                arr = np.clip(np.asarray(frame, dtype=np.float32) * 255.0, 0.0, 255.0).astype(np.uint8)
                if arr.ndim == 2:
                    arr = np.stack([arr] * 3, axis=-1)
                elif arr.shape[-1] == 1:
                    arr = np.repeat(arr, 3, axis=-1)
                mode = 'RGBA' if arr.shape[-1] == 4 else 'RGB'
                pil_image = Image.fromarray(np.ascontiguousarray(arr), mode)
                suffix = ''.join(random.choice(_RANDOM_SUFFIX_CHARS) for _ in range(_RANDOM_SUFFIX_LENGTH))
                filename = _FILENAME_PREFIX + suffix + '.png'
                save_kwargs = {'format': 'PNG', 'compress_level': 4}
                if pnginfo is not None:
                    save_kwargs['pnginfo'] = pnginfo
                pil_image.save(os.path.join(output_dir, filename), **save_kwargs)
                results.append({'filename': filename, 'subfolder': '', 'type': 'temp'})

        _save_batch(image_a)
        _save_batch(image_b)
        return {'ui': {'images': results}}

NODE_CLASS_MAPPINGS = {'TE_image_pro_image_comparer': TEMANImageComparerNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_image_comparer': 'TE MAN 图像对比'}
