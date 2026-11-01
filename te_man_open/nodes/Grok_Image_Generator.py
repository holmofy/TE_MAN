# -*- coding: utf-8 -*-
"""te_man_open · Grok_Image_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class BananaGrokImageSafePyNode:
    """TE MAN Grok Image

    注册名: TE_image_pro_grok_image
    规格:   spec/Grok_Image_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Grok'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '生成一张可爱的小猫图片', 'defaultInput': True, 'tooltip': '用于生成图片的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址，如 http://localhost:8000（不要带 /v1/chat/completions）'}), 'image_count': ('INT', {'default': 1, 'min': 1, 'max': 10, 'tooltip': '目标图片张数，对应 image_config.n'}), 'size': (('1024x1024', '1280x720', '720x1280', '1792x1024', '1024x1792'), {'default': '1024x1024', 'tooltip': '图片尺寸，对应 image_config.size'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image': ('IMAGE', {'tooltip': '参考/编辑输入图片（可选）。填写时会以多模态 messages 方式发给 /v1/chat/completions。'}), 'image_2': ('IMAGE', {'tooltip': '第二路参考/编辑输入图片（可选）。'}), 'image_3': ('IMAGE', {'tooltip': '第三路参考/编辑输入图片（可选）。'}), 'timeout_s': ('INT', {'default': 180, 'min': 30, 'max': 3600, 'tooltip': '请求超时（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜'), {'default': '无', 'tooltip': '使用快捷功能生成。'})}}
        # --8<-- 契约结束 --8<--

    def generate_images(self, **kwargs):
        """TODO: 按 spec/Grok_Image_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_grok_image': BananaGrokImageSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_grok_image': 'TE MAN Grok Image'}
