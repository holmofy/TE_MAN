# -*- coding: utf-8 -*-
"""te_man_open · Sora_2_Video_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class BananaSora2VideoSafePyNode:
    """TE MAN sora2 video

    注册名: TE_image_pro_sora2_video
    规格:   spec/Sora_2_Video_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Sora'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': 'A cinematic orange cat walking slowly through a rainy neon street at night.', 'tooltip': '用于生成视频的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址，如 https://socdabat.it.com（不要带 /v1/videos）'}), 'model': ('STRING', {'default': 'sora-2', 'multiline': False, 'tooltip': '模型名称，默认 sora-2'}), 'aspect_ratio': (('16:9', '9:16'), {'default': '16:9', 'tooltip': '画面比例'}), 'resolution': (('720p',), {'default': '720p', 'tooltip': '分辨率'}), 'seconds': (('4', '8', '12'), {'default': '8', 'tooltip': '视频时长（秒）'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image': ('IMAGE', {'tooltip': '参考图片（可选），接入后走图生视频，写入 image_url'}), 'timeout_s': ('INT', {'default': 900, 'min': 30, 'max': 3600, 'tooltip': '总超时（秒），包含创建任务、轮询和下载'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'})}}
        # --8<-- 契约结束 --8<--

    def generate_video(self, **kwargs):
        """TODO: 按 spec/Sora_2_Video_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_sora2_video': BananaSora2VideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_sora2_video': 'TE MAN sora2 video'}
