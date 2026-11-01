# -*- coding: utf-8 -*-
"""te_man_open · TE_HappyH_Video

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEHappyHVideoSafePyNode:
    """TE MAN HappyH Video

    注册名: TE_image_pro_happyh_video
    规格:   spec/TE_HappyH_Video.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/HappyHorse'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'task_id', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一座由硬纸板和瓶盖搭建的微型城市，在夜晚焕发出生机。一列硬纸板火车缓缓驶过，小灯点缀其间，照亮前路。', 'tooltip': '用于生成视频的提示词。多图参考模式可用 [Image 1]、[Image 2] 指代图片。', 'defaultInput': True}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API 地址，例如 https://newapi.xxx.com 或完整的 /v1/videos 地址'}), 'mode': (('自动', '文生视频', '首帧生视频', '多图参考'), {'default': '自动', 'tooltip': '自动：无图=文生视频，1图=首帧生视频，多图=多图参考。'}), 'ratio': (('16:9', '9:16', '1:1', '4:3', '3:4', '4:5', '5:4', '9:21', '21:9'), {'default': '16:9', 'tooltip': '会转换成 size，例如 16:9 -> 1280x720'}), 'duration': (('3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13', '14', '15'), {'default': '5', 'tooltip': '视频时长（秒），范围 3-15'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 2147483647, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image_1': ('IMAGE', {'tooltip': '首帧/参考图 1'}), 'image_2': ('IMAGE', {'tooltip': '参考图 2'}), 'image_3': ('IMAGE', {'tooltip': '参考图 3'}), 'image_4': ('IMAGE', {'tooltip': '参考图 4'}), 'image_5': ('IMAGE', {'tooltip': '参考图 5'}), 'image_6': ('IMAGE', {'tooltip': '参考图 6'}), 'image_7': ('IMAGE', {'tooltip': '参考图 7'}), 'image_8': ('IMAGE', {'tooltip': '参考图 8'}), 'image_9': ('IMAGE', {'tooltip': '参考图 9'}), 'poll_interval_s': ('INT', {'default': 15, 'min': 5, 'max': 60, 'tooltip': '轮询间隔（秒），官方建议约 15 秒'}), 'timeout_s': ('INT', {'default': 900, 'min': 120, 'max': 3600, 'tooltip': '任务最长等待时间（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'})}}
        # --8<-- 契约结束 --8<--

    def generate_video(self, **kwargs):
        """TODO: 按 spec/TE_HappyH_Video.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_happyh_video': TEHappyHVideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_happyh_video': 'TE MAN HappyH Video'}
