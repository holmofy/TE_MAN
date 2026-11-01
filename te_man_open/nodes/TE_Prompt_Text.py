# -*- coding: utf-8 -*-
"""te_man_open · TE_Prompt_Text

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEPromptTextNode:
    """TE MAN MiniMaxH3增强提示词Prompt TEXT

    注册名: TE_prompt_text
    规格:   spec/TE_Prompt_Text.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'build_text'
    RETURN_TYPES = ('STRING', 'TE_H3_REFERENCES')
    RETURN_NAMES = ('text', 'H3参考素材')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'text': ('STRING', {'multiline': True, 'default': '', 'tooltip': '增强提示词文本。输入 @ 可选择下游节点已连接的图片、视频和音频引用。'}), 'reference_labels': ('STRING', {'multiline': True, 'default': '', 'tooltip': '由前端根据 H3 官方节点的素材连接自动生成。'})}}
        # --8<-- 契约结束 --8<--

    def build_text(self, **kwargs):
        """TODO: 按 spec/TE_Prompt_Text.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_prompt_text': TEPromptTextNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_prompt_text': 'TE MAN MiniMaxH3增强提示词Prompt TEXT'}
