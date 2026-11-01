# -*- coding: utf-8 -*-
"""te_man_open · TE_Bernini_R_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEBerniniPromptEnhancer:
    """TE MAN Bernini 提示词增强(本地orAPI)

    注册名: TE_Bernini_Prompt_Enhancer
    规格:   spec/TE_Bernini_R_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Bernini'
    FUNCTION = 'enhance_prompt'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('增强提示词(API)', '提示词模版(本地)')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入提示词': ('STRING', {'default': '', 'multiline': True, 'tooltip': '输入原始提示词或简短需求'}), '任务类型': (('文生视频(t2v)', '视频改视频(v2v)', '大幅度动作改视频(mv2v)', '动作迁移/参考改视频(rv2v)', '图生视频(r2v)'), {'default': '文生视频(t2v)', 'tooltip': '按 Bernini 的视频任务分类选择模板'}), '增强方式': (('本地模板', 'API增强'), {'default': '本地模板', 'tooltip': '本地模板不依赖接口；API增强会调用 Responses API'}), '参考图数量': ('INT', {'default': 1, 'min': 1, 'max': 8, 'step': 1, 'tooltip': '仅用于 r2v/rv2v 官方增强模板里的 image_num 描述'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': 'https://tem.588186.xyz', 'multiline': False, 'tooltip': '服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses'}), 'model': ('STRING', {'default': 'gpt-5.5', 'multiline': False, 'tooltip': 'Responses API 模型名称，按你的中转/服务端支持填写'}), 'max_output_tokens': ('INT', {'default': 2048, 'min': 256, 'max': 32768, 'step': 256, 'tooltip': '最大输出 token，API 增强时使用'}), 'temperature': ('FLOAT', {'default': 0.7, 'min': 0.0, 'max': 2.0, 'step': 0.05, 'tooltip': '创意程度；如果服务端模型不支持，可调回默认或更低'})}, 'optional': {'timeout_s': ('INT', {'default': 300, 'min': 30, 'max': 1800, 'tooltip': '请求超时时间（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'})}}
        # --8<-- 契约结束 --8<--

    def enhance_prompt(self, **kwargs):
        """TODO: 按 spec/TE_Bernini_R_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

class TEBerniniRGenerator:
    """TE MAN Bernini

    注册名: TE_Bernini_R_Generator
    规格:   spec/TE_Bernini_R_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Bernini'
    FUNCTION = 'generate'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('图像', '状态')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'高噪模型': ((), {'default': 'Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors'}), '低噪模型': ((), {'default': 'Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors'}), 'VAE模型': ((), {'default': 'Wan2_1_VAE_bf16.safetensors'}), '文本编码器': ((), {'default': 'umt5-xxl-enc-fp8_e4m3fn.safetensors'}), '启用加速LoRA': ('BOOLEAN', {'default': True}), '高噪加速LoRA': (('无',), {'default': '无'}), '高噪LoRA强度': ('FLOAT', {'default': 1.0, 'min': -10.0, 'max': 10.0, 'step': 0.0001}), '低噪加速LoRA': (('无',), {'default': '无'}), '低噪LoRA强度': ('FLOAT', {'default': 1.0, 'min': -10.0, 'max': 10.0, 'step': 0.0001}), '提示词': ('STRING', {'default': '', 'multiline': True}), '负面提示词': ('STRING', {'default': 'bad video', 'multiline': True}), '宽度': ('INT', {'default': 832, 'min': 16, 'max': 8192, 'step': 16}), '高度': ('INT', {'default': 480, 'min': 16, 'max': 8192, 'step': 16}), '帧数': ('INT', {'default': 81, 'min': 1, 'max': 8192, 'step': 4}), '种子': ('INT', {'default': 666, 'min': 0, 'max': 18446744073709551615}), '步数': ('INT', {'default': 8, 'min': 1, 'max': 1000}), 'Shift': ('FLOAT', {'default': 5.0, 'min': 0.0, 'max': 1000.0, 'step': 0.01}), '高噪CFG': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 30.0, 'step': 0.01}), '低噪CFG': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 30.0, 'step': 0.01}), '高噪结束步': ('INT', {'default': 4, 'min': 1, 'max': 1000}), '低噪开始步': ('INT', {'default': 4, 'min': 0, 'max': 1000}), '采样器': (('euler', 'unipc', 'dpm++', 'dpm++_sde', 'ddim', 'flowmatch_causvid'), {'default': 'euler'})}, 'optional': {'源视频或源图': ('IMAGE',), '参考视频': ('IMAGE',), '参考图1': ('IMAGE',), '参考图2': ('IMAGE',), '参考图3': ('IMAGE',), '参考图4': ('IMAGE',), '参考图5': ('IMAGE',), '参考图6': ('IMAGE',), '参考图7': ('IMAGE',), '参考图8': ('IMAGE',), '参考图最大边': ('INT', {'default': 832, 'min': 16, 'max': 8192, 'step': 16}), '模型精度': (('bf16', 'fp16', 'fp32', 'fp16_fast'), {'default': 'bf16'}), '模型量化': (('disabled', 'fp8_e4m3fn', 'fp8_e4m3fn_scaled', 'fp8_e4m3fn_fast', 'fp8_e4m3fn_scaled_fast', 'fp8_e5m2', 'fp8_e5m2_scaled', 'fp8_e5m2_fast', 'fp8_e5m2_scaled_fast'), {'default': 'disabled'}), '注意力模式': (('sageattn', 'sdpa', 'flash_attn_2', 'flash_attn_3', 'sageattn_3', 'radial_sage_attention', 'sageattn_compiled'), {'default': 'sageattn'}), 'VAE精度': (('bf16', 'fp16', 'fp32'), {'default': 'bf16'}), '文本精度': (('bf16', 'fp32'), {'default': 'bf16'}), '文本量化': (('disabled', 'fp8_e4m3fn'), {'default': 'fp8_e4m3fn'}), '文本编码设备': (('gpu', 'cpu'), {'default': 'gpu'}), '强制卸载': ('BOOLEAN', {'default': True}), 'BlockSwap块数': ('INT', {'default': 30, 'min': 0, 'max': 40, 'step': 1})}}
        # --8<-- 契约结束 --8<--

    def generate(self, **kwargs):
        """TODO: 按 spec/TE_Bernini_R_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_Bernini_Prompt_Enhancer': TEBerniniPromptEnhancer, 'TE_Bernini_R_Generator': TEBerniniRGenerator}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_Bernini_Prompt_Enhancer': 'TE MAN Bernini 提示词增强(本地orAPI)', 'TE_Bernini_R_Generator': 'TE MAN Bernini'}
