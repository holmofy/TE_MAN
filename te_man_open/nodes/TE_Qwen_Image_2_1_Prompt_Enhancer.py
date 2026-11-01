# -*- coding: utf-8 -*-
"""te_man_open · TE_Qwen_Image_2_1_Prompt_Enhancer

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEQwenImage21PromptEnhancer:
    """TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)

    注册名: TE_Qwen_Image_2_1_Prompt_Enhancer
    规格:   spec/TE_Qwen_Image_2_1_Prompt_Enhancer.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Prompt'
    FUNCTION = 'enhance_prompt'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('增强提示词',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入提示词': ('STRING', {'default': '', 'multiline': True, 'tooltip': '输入要增强的文生图或图生图需求。'}), '任务模式': (('文生图', '图生图'), {'default': '文生图'}), '输出语言': (('中文', '英文'), {'default': '中文', 'tooltip': '控制增强提示词的描述语言。用户明确要求的画面文字保持原文。'}), '增强方式': (('本地', '本地官方PE', 'API'), {'default': '本地'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空时读取 TE MAN 的 config.ini。'}), 'api_base_url': ('STRING', {'default': 'https://teynex.com', 'multiline': False}), 'model': ('STRING', {'default': 'deepseek-v4.1-flash', 'multiline': False}), '文生图PE模型': (('（请把模型放到 models/text_encoders）',), {'tooltip': '本地官方 PE 的文生图模型，增强方式选择本地官方PE且任务模式为文生图时生效。'}), '图生图PE模型': (('（请把模型放到 models/text_encoders）',), {'tooltip': '本地官方 PE 的图生图模型，增强方式选择本地官方PE且任务模式为图生图时生效。'}), '主模型': (('（请把模型放到 models/LLM）',), {'tooltip': '本地 Qwen 视觉模型，文件放在 ComfyUI/models/LLM/。'}), 'mmproj': (('无',), {'default': '无', 'tooltip': '图生图需要选择对应的视觉投影文件。'}), '最大生成token': ('INT', {'default': 4096, 'min': 256, 'max': 32768, 'step': 256, 'tooltip': '本地模型最大生成 token。API 模式不发送此限制。'}), '上下文长度': ('INT', {'default': 8192, 'min': 1024, 'max': 327680, 'step': 256, 'tooltip': '本地模型的 llama.cpp 上下文长度；数值越大通常占用越多显存。API 模式不使用此设置。'}), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 18446744073709551615, 'step': 1, 'control_after_generate': True, 'tooltip': '本地模型随机种子。使用生成后控制可固定、递增、递减或随机化；API 模式不使用此设置。'}), '生成后自动卸载模型': ('BOOLEAN', {'default': False, 'tooltip': '本地生成完成后自动卸载 Qwen 模型并释放显存。'}), '启用思考': ('BOOLEAN', {'default': False, 'tooltip': '仅本地官方 PE 生效。开启后模型先进行思考再输出提示词；关闭后直接生成提示词。'})}, 'optional': {'图片': ('IMAGE', {'tooltip': '图生图参考图片。'}), '图片2': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片3': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片4': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片5': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片6': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片7': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片8': ('IMAGE', {'tooltip': '图生图附加参考图片。'})}}
        # --8<-- 契约结束 --8<--

    def enhance_prompt(self, **kwargs):
        """TODO: 按 spec/TE_Qwen_Image_2_1_Prompt_Enhancer.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_Qwen_Image_2_1_Prompt_Enhancer': TEQwenImage21PromptEnhancer}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_Qwen_Image_2_1_Prompt_Enhancer': 'TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)'}
