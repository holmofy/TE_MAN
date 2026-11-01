# -*- coding: utf-8 -*-
"""te_man_open · Save_Video_With_Frame_Capture

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TESaveVideoWithFrameCapture:
    """TE MAN 保存视频video

    注册名: TE_image_pro_save_video
    规格:   spec/Save_Video_With_Frame_Capture.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'save_video_and_output'
    OUTPUT_NODE = True
    DESCRIPTION = '保存输入视频到 ComfyUI 输出目录，并在节点前端提供暂停预览与截取当前帧功能。'
    RETURN_TYPES = ('VIDEO',)
    RETURN_NAMES = ('video',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'local_video': (('',), {'default': '', 'tooltip': '可选。左侧 video 未连接时，使用这里选择 input 目录中的本地视频。'}), 'filename_prefix': ('STRING', {'default': 'TE_MAN_Video', 'tooltip': '保存到 output 目录时使用的文件名前缀。'})}, 'optional': {'video': ('VIDEO', {'tooltip': '要保存的视频输入。接入后会优先使用这里的视频，并覆盖本地视频选择。'})}, 'hidden': {'unique_id': 'UNIQUE_ID', 'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def save_video_and_output(self, **kwargs):
        """TODO: 按 spec/Save_Video_With_Frame_Capture.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_save_video': TESaveVideoWithFrameCapture}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_save_video': 'TE MAN 保存视频video'}
