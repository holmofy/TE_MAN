# -*- coding: utf-8 -*-
"""te_man_open · TE_Text_Display

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TETextDisplayNode:
    """TE MAN TEXT文本展示

    注册名: TE_text_display
    规格:   spec/TE_Text_Display.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'show_text'
    OUTPUT_NODE = True
    DESCRIPTION = '显示、编辑并继续输出文本。可连接上游文本，也可直接在节点内输入。'
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('text',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'text': ('STRING', {'multiline': True, 'default': '', 'tooltip': '节点内文本。未连接 input_text 时会作为输出文本。'})}, 'optional': {'input_text': ('STRING', {'forceInput': True, 'tooltip': '可选上游文本。连接后优先显示并输出这里的内容。'}), 'use_edited_text': ('BOOLEAN', {'default': False}), 'edited_from_text': ('STRING', {'default': ''})}, 'hidden': {'unique_id': 'UNIQUE_ID', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def show_text(self, **kwargs):
        """TODO: 按 spec/TE_Text_Display.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_text_display': TETextDisplayNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_text_display': 'TE MAN TEXT文本展示'}
