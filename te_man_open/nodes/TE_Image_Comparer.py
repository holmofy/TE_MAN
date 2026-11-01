# -*- coding: utf-8 -*-
"""te_man_open · TE_Image_Comparer

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

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

    def compare_images(self, **kwargs):
        """TODO: 按 spec/TE_Image_Comparer.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_image_comparer': TEMANImageComparerNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_image_comparer': 'TE MAN 图像对比'}
