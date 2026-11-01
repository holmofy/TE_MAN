# -*- coding: utf-8 -*-
"""te_man_open · TE_Batch_Tools

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEMANBatchEnhancedSettingsNode:
    """TE MAN 批量增强设置

    注册名: TE_MAN_Batch_Enhanced_Settings
    规格:   spec/TE_Batch_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Batch'
    FUNCTION = 'build_settings'
    DESCRIPTION = 'TE MAN 批量增强设置：连接到批量提示词/批量图片节点，控制批量执行范围、间隔、续跑编号和随机顺序。'
    RETURN_TYPES = ('TE_BATCH_ENHANCED_SETTINGS',)
    RETURN_NAMES = ('增强设置',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'执行间隔时间': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 86400.0, 'step': 0.1, 'tooltip': '每提交 1 个任务后等待的秒数。0 表示立即提交下一个。'}), '从指定编号继续': ('INT', {'default': 1, 'min': 1, 'max': 100000, 'step': 1, 'tooltip': '从第几个编号开始批量执行。1 表示从第一项开始。'}), '随机编号执行': ('BOOLEAN', {'default': False, 'tooltip': '开启后，在当前范围内随机顺序提交。'}), '执行范围': (('只执行当前线', '执行整个工作流'), {'default': '只执行当前线', 'tooltip': '默认只执行当前批量节点连接出去的流程；需要全工作流时改为执行整个工作流。'})}}
        # --8<-- 契约结束 --8<--

    def build_settings(self, **kwargs):
        """TODO: 按 spec/TE_Batch_Tools.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

class TEMANBatchImageNode:
    """TE MAN 批量图片

    注册名: TE_MAN_Batch_Image
    规格:   spec/TE_Batch_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Batch'
    FUNCTION = 'load_image'
    DESCRIPTION = 'TE MAN 批量图片：多图列表管理，可单项执行或批量执行。'
    RETURN_TYPES = ('IMAGE', 'STRING', 'STRING')
    RETURN_NAMES = ('输出图片', '图片文件名', '编号')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'image_list': ('STRING', {'multiline': True, 'default': '', 'hidden': True}), 'index': ('INT', {'default': 0, 'min': 0, 'max': 100000, 'step': 1}), 'max_images': ('INT', {'default': 0, 'min': 0, 'max': 100000, 'step': 1, 'tooltip': '0 表示不限制。'}), '最大任务数': ('INT', {'default': 100, 'min': 1, 'max': 10000, 'step': 1, 'tooltip': '批量执行时前端用于防止误提交过多任务。'})}, 'optional': {'增强设置': ('TE_BATCH_ENHANCED_SETTINGS', {'forceInput': True, 'tooltip': '可连接 TE MAN 批量增强设置，控制执行范围、间隔、续跑编号和随机顺序。'})}}
        # --8<-- 契约结束 --8<--

    def load_image(self, **kwargs):
        """TODO: 按 spec/TE_Batch_Tools.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

class TEMANBatchPromptNode:
    """TE MAN 批量提示词

    注册名: TE_MAN_Batch_Prompt
    规格:   spec/TE_Batch_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Batch'
    FUNCTION = 'get_prompt'
    DESCRIPTION = 'TE MAN 批量提示词：卡片式管理多条提示词，可单项执行或批量执行。'
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('输出提示词', '编号')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompts_json': ('STRING', {'default': '[]', 'hidden': True}), 'index': ('INT', {'default': 0, 'min': 0, 'max': 100000, 'step': 1}), '最大任务数': ('INT', {'default': 100, 'min': 1, 'max': 10000, 'step': 1, 'tooltip': '批量执行时前端用于防止误提交过多任务。'})}, 'optional': {'增强设置': ('TE_BATCH_ENHANCED_SETTINGS', {'forceInput': True, 'tooltip': '可连接 TE MAN 批量增强设置，控制执行范围、间隔、续跑编号和随机顺序。'}), 'prompts': ('STRING', {'forceInput': True, 'tooltip': '可选上游文本。支持一行一条、编号列表或 JSON 数组。'})}}
        # --8<-- 契约结束 --8<--

    def get_prompt(self, **kwargs):
        """TODO: 按 spec/TE_Batch_Tools.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_MAN_Batch_Enhanced_Settings': TEMANBatchEnhancedSettingsNode, 'TE_MAN_Batch_Image': TEMANBatchImageNode, 'TE_MAN_Batch_Prompt': TEMANBatchPromptNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_MAN_Batch_Enhanced_Settings': 'TE MAN 批量增强设置', 'TE_MAN_Batch_Image': 'TE MAN 批量图片', 'TE_MAN_Batch_Prompt': 'TE MAN 批量提示词'}
