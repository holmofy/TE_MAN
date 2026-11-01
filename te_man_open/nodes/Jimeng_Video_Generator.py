# -*- coding: utf-8 -*-
"""te_man_open · Jimeng_Video_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class BananaJimengVideoNode:
    """TE MAN JM Video 2

    注册名: TE_image_pro_jimeng_video_2
    规格:   spec/Jimeng_Video_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Jimeng'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'task_id', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '@image1 是主体，镜头缓慢推进，保持主体一致，电影感光影，自然运动。', 'tooltip': '用于生成视频的提示词；渠道2用 @image1/@audio1，渠道3用 @图1/@audio1，渠道4支持最多 3 路参考音频，渠道5不支持音频。'}), 'duration': (('15',), {'default': '15', 'tooltip': '视频时长固定 15 秒'}), 'aspect_ratio': (('21:9', '1:1', '4:3', '3:4', '16:9', '9:16'), {'default': '16:9', 'tooltip': '视频比例；渠道4/渠道5支持全部比例，其他渠道仅使用 16:9 / 9:16 / 1:1。'})}, 'optional': {'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': 'https://tem.588186.xyz', 'multiline': False, 'tooltip': '服务地址（不要带 /v1/videos）'}), 'image': ('IMAGE', {'tooltip': '第一张参考图，提交为 reference_images[0]，提示词中用 [img1] 引用'}), 'image_2': ('IMAGE', {'tooltip': '第二张参考图（可选）'}), 'image_3': ('IMAGE', {'tooltip': '第三张参考图（可选）'}), 'image_4': ('IMAGE', {'tooltip': '第四张参考图（可选）'}), 'image_5': ('IMAGE', {'tooltip': '第五张参考图（可选）'}), 'image_6': ('IMAGE', {'tooltip': '第六张参考图（可选）'}), 'image_7': ('IMAGE', {'tooltip': '第七张参考图（可选）'}), 'image_8': ('IMAGE', {'tooltip': '第八张参考图（可选）'}), 'image_9': ('IMAGE', {'tooltip': '第九张参考图（可选）'}), 'audio': ('AUDIO', {'tooltip': '参考音频（可选），提交为 reference_audios[0]，提示词中用 [audio1] 引用'}), 'audio_2': ('AUDIO', {'tooltip': '第二个参考音频（可选），提交为 reference_audios[1]，提示词中用 [audio2] 引用'}), 'audio_3': ('AUDIO', {'tooltip': '第三个参考音频（可选），提交为 reference_audios[2]，提示词中用 [audio3] 引用'}), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 2147483647, 'tooltip': '保留参数；新接口不写入请求体'}), 'poll_interval_s': ('INT', {'default': 5, 'min': 2, 'max': 60, 'tooltip': '轮询间隔（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '渠道选择': (('渠道2(2.0)', '渠道3(2.0)', '渠道4(2.0)', '渠道5(2.0fast)'), {'default': '渠道2(2.0)', 'tooltip': '渠道2(2.0)：LongXia-G-Seedance-2.0；渠道3(2.0)：seedance2.0-full-9img；渠道4(2.0)：sora-v3-pro；渠道5(2.0fast)：sora-v3-fast。'})}}
        # --8<-- 契约结束 --8<--

    def generate_video(self, **kwargs):
        """TODO: 按 spec/Jimeng_Video_Generator.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_image_pro_jimeng_video_2': BananaJimengVideoNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_jimeng_video_2': 'TE MAN JM Video 2'}
