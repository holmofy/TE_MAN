# -*- coding: utf-8 -*-
"""te_man_open · TE_Audio_Save_Load

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

class TEAudioSaveLoad:
    """TE MAN 加载音频&保存音频 Audio

    注册名: TE_audio_save_load
    规格:   spec/TE_Audio_Save_Load.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'load_trim_save_audio'
    OUTPUT_NODE = True
    DESCRIPTION = '加载或接收音频，按开始时间和结束时间裁切，保存后继续输出同一份音频。'
    RETURN_TYPES = ('AUDIO',)
    RETURN_NAMES = ('audio',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'upload_audio': (('',), {'default': '', 'audio_upload': True, 'tooltip': '可选。左侧 audio 未连接时，从 ComfyUI input 目录选择或上传音频。'}), 'start_time': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 4294967295, 'step': 0.01, 'display_name': '开始时间（秒）', 'tooltip': '从原音频的这个时间点开始保留。'}), 'end_time': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 4294967295, 'step': 0.01, 'display_name': '结束时间（秒）', 'tooltip': '保留到原音频的这个时间点。0 表示自动使用原音频结尾，加载后会显示真实时长。'}), 'speed': ('FLOAT', {'default': 1.0, 'min': 0.1, 'max': 4.0, 'step': 0.1, 'display_name': '变速倍率', 'tooltip': '1.0 为原速；小于 1.0 放慢，大于 1.0 加快。'}), 'filename_prefix': ('STRING', {'default': 'audio/TE_MAN_%Y-%m-%d-%H-%M-%S', 'display_name': '文件名前缀', 'tooltip': '保存到 ComfyUI/output。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S。'}), 'format': (('flac', 'mp3', 'opus'), {'default': 'flac', 'display_name': '保存格式'})}, 'optional': {'audio': ('AUDIO', {'tooltip': '接入后优先使用这里的音频，并覆盖本地加载选择。'}), '保存文件名': ('STRING', {'forceInput': True, 'tooltip': '可选。接入文本后覆盖上方文件名前缀。'})}, 'hidden': {'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def load_trim_save_audio(self, **kwargs):
        """TODO: 按 spec/TE_Audio_Save_Load.md 实现。输入经 kwargs 传入。"""
        raise NotImplementedError

NODE_CLASS_MAPPINGS = {'TE_audio_save_load': TEAudioSaveLoad}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_audio_save_load': 'TE MAN 加载音频&保存音频 Audio'}
