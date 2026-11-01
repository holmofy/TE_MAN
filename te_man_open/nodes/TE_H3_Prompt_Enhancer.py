# -*- coding: utf-8 -*-
"""te_man_open · TE_H3_Prompt_Enhancer

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEH3PromptEnhancer:
    """TE MAN MiniMax H3 AI提示词增强(本地orAPI)

    注册名: TE_H3_Prompt_Enhancer
    规格:   spec/TE_H3_Prompt_Enhancer.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Prompt'
    FUNCTION = 'enhance_prompt'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('增强提示词(API)', '提示词模版(本地)')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入提示词': ('STRING', {'default': '', 'multiline': True, 'tooltip': '输入剧情、动作、运镜、对白和引用标签，例如 <Picture 1>。'}), '任务类型': (('全参考模式(Reference to Video)', '文生视频(T2VA)', '首帧图生视频(I2VA)', '首尾帧视频(FL2VA)', '尾帧图生视频(L2VA)'), {'default': '全参考模式(Reference to Video)', 'tooltip': '按实际使用的 MiniMax H3 节点和首尾帧连接状态选择。'}), '视频时长': ('FLOAT', {'default': 5.0, 'min': 1.0, 'max': 150.0, 'step': 0.5, 'tooltip': '用于规划镜头时间戳；H3 推荐生成时长约 5-15 秒。'}), '参考素材说明': ('STRING', {'default': '', 'multiline': True, 'tooltip': '可选。按标签说明素材内容和用途；未说明时 AI 不会臆造素材细节。'}), '增强方式': (('本地模板', 'API增强'), {'default': '本地模板', 'tooltip': '本地模板不调用接口；API增强直接输出可用于 H3 的中文提示词。'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini。'}), 'api_base_url': ('STRING', {'default': 'https://teynex.com', 'multiline': False, 'tooltip': 'Responses API 服务地址，可填写到域名、/v1 或 /v1/responses。'}), 'model': ('STRING', {'default': 'gpt-5.6-sol', 'multiline': False, 'tooltip': '服务端支持的 Responses API 模型名称。'}), 'max_output_tokens': ('INT', {'default': 4096, 'min': 512, 'max': 32768, 'step': 256}), 'temperature': ('FLOAT', {'default': 0.6, 'min': 0.0, 'max': 2.0, 'step': 0.05})}, 'optional': {'H3参考素材': ('TE_H3_REFERENCES', {'tooltip': '连接 TE MAN MiniMaxH3增强提示词Prompt TEXT 的 H3参考素材输出。'}), 'timeout_s': ('INT', {'default': 300, 'min': 30, 'max': 1800, 'tooltip': 'API 请求超时时间（秒）。'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理时开启。'})}}
        # --8<-- 契约结束 --8<--

    def enhance_prompt(self, **kwargs):
        """TODO: 按 spec/TE_H3_Prompt_Enhancer.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_H3_Prompt_Enhancer': TEH3PromptEnhancer}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_H3_Prompt_Enhancer': 'TE MAN MiniMax H3 AI提示词增强(本地orAPI)'}


class TEH3ReferenceBridge:
    """TE MAN H3素材转接口

    注册名: TE_H3_Reference_Bridge
    规格:   spec/TE_H3_Prompt_Enhancer.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'convert'
    RETURN_TYPES = ('STRING', 'TE_H3_REFERENCES')
    RETURN_NAMES = ('text', 'H3素材')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'text': ('STRING', {'forceInput': True, 'tooltip': '连接上游提示词文本。'}), 'reference_labels': ('STRING', {'default': '', 'multiline': True, 'tooltip': '由前端根据 H3 官方节点的素材连接自动生成。'})}}
        # --8<-- 契约结束 --8<--

    def convert(self, **kwargs):
        """TODO: 按 spec/TE_H3_Prompt_Enhancer.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_H3_Reference_Bridge': TEH3ReferenceBridge}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_H3_Reference_Bridge': 'TE MAN H3素材转接口'}
