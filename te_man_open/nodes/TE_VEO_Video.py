# -*- coding: utf-8 -*-
"""te_man_open · TE_VEO_Video

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class BananaTEVeoVideoSafePyNode:
    """TE MAN VEO Video

    注册名: TE_image_pro_te_veo_video
    规格:   spec/TE_VEO_Video.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Veo'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO',)
    RETURN_NAMES = ('video',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只可爱的小狗在花园里玩耍', 'tooltip': '用于生成视频的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址不要带 /v1/videos）'}), 'aspect_ratio': (('16:9', '9:16'), {'default': '16:9', 'tooltip': '视频比例，对应接口参数 aspectRatio'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 2147483647, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'reference_image_1': ('IMAGE', {'tooltip': '多图参考 1。只接这一路时也会走参考图模式'}), 'reference_image_2': ('IMAGE', {'tooltip': '多图参考 2'}), 'reference_image_3': ('IMAGE', {'tooltip': '多图参考 3'}), 'first_frame_image': ('IMAGE', {'tooltip': '首帧参考。接入后不能再接多图参考输入'}), 'last_frame_image': ('IMAGE', {'tooltip': '尾帧参考。必须和首帧参考一起使用，不能单独使用'}), 'poll_interval_s': ('INT', {'default': 5, 'min': 2, 'max': 60, 'tooltip': '轮询间隔（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '清晰度': (('720p', '1080p'), {'default': '720p', 'tooltip': '默认 720p；1080p 改走 multipart + input_reference[] 接口。'}), '模型选择': (('veo 3.1 fast', 'veo3.1-lite', 'omni-flash'), {'default': 'veo 3.1 fast', 'tooltip': '选择要使用的视频生成模型。'}), '线路选择': (('线路1', '线路2'), {'default': '线路1', 'tooltip': '选择接口线路，默认使用线路1；如果某个线路不可用，可以切换其他线路尝试。'})}}
        # --8<-- 契约结束 --8<--

    def generate_video(self, **kwargs):
        """TODO: 按 spec/TE_VEO_Video.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_te_veo_video': BananaTEVeoVideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_te_veo_video': 'TE MAN VEO Video'}
