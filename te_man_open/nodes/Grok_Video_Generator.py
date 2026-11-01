# -*- coding: utf-8 -*-
"""te_man_open · Grok_Video_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class BananaGrokVideoSafePyNode:
    """TE MAN Grok Video

    注册名: TE_image_pro_grok_video
    规格:   spec/Grok_Video_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Grok'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '生成一个西瓜切开里面是棉花糖的视频', 'tooltip': '用于生成视频的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址不要带 /v1/videos）'}), 'model': ('STRING', {'default': 'grok-imagine-video', 'multiline': False, 'tooltip': '线路1使用此模型；线路2固定使用 grok-imagine-video2'}), 'seconds': (('10', '15'), {'default': '10', 'tooltip': '视频时长（秒）'}), 'size': (('720x1280', '1280x720', '1024x1792', '1792x1024'), {'default': '1280x720', 'tooltip': '画面尺寸'}), 'resolution_name': (('480p', '720p'), {'default': '720p', 'tooltip': '线路1通过 resolution 字段提交的分辨率；线路2不提交此值'}), 'preset': (('fun', 'normal', 'spicy', 'custom'), {'default': 'normal', 'tooltip': '旧工作流兼容项；线路2当前 JSON 请求不再提交此值'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image': ('IMAGE', {'tooltip': '参考图片 1（可选）'}), 'image_2': ('IMAGE', {'tooltip': '参考图片 2（可选）'}), 'image_3': ('IMAGE', {'tooltip': '参考图片 3（可选）'}), 'image_4': ('IMAGE', {'tooltip': '参考图片 4（可选）'}), 'image_5': ('IMAGE', {'tooltip': '参考图片 5（可选）'}), 'timeout_s': ('INT', {'default': 600, 'min': 30, 'max': 3600, 'tooltip': '请求超时（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '线路选择': (('线路1', '线路2'), {'default': '线路2', 'tooltip': '线路12'})}}
        # --8<-- 契约结束 --8<--

    def generate_video(self, **kwargs):
        """TODO: 按 spec/Grok_Video_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_grok_video': BananaGrokVideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_grok_video': 'TE MAN Grok Video'}
