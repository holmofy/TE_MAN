# -*- coding: utf-8 -*-
"""te_man_open · TE_Image_Compress_Test

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

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

    def process_image(self, **kwargs):
        """TODO: 按 spec/TE_Image_Compress_Test.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_compress_test': TEImageCompressTestNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_compress_test': 'TE MAN 图片缩放压缩测试'}
