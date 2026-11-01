# -*- coding: utf-8 -*-
"""te_man_open · TE_3D_Director

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEMan3DDirectorNode:
    """TE MAN 3D导演台

    注册名: TE_3D_Director
    规格:   spec/TE_3D_Director.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/3D'
    FUNCTION = 'export_scene'
    OUTPUT_NODE = True
    DESCRIPTION = '打开 TE MAN 3D导演台，编辑角色、道具、机位和姿势，并输出场景 JSON 与构图提示词。'
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('scene_json', '示例提示词')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'scene_json': ('STRING', {'multiline': True, 'default': '{}', 'tooltip': '3D导演台保存的场景 JSON。通常由前端面板自动写入。'}), 'composition_prompt': ('STRING', {'multiline': True, 'default': '让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面', 'display_name': '示例提示词', 'label': '示例提示词', 'tooltip': '示例提示词，可根据导演台截图和参考图自行补充修改。'})}}
        # --8<-- 契约结束 --8<--

    def export_scene(self, **kwargs):
        """TODO: 按 spec/TE_3D_Director.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_3D_Director': TEMan3DDirectorNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_3D_Director': 'TE MAN 3D导演台'}
