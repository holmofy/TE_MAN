# -*- coding: utf-8 -*-
"""te_man_open · TE_Video_Comparer

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

import os

#: temp 落盘文件名前缀（原版字符串池原文，uuid4 hex 补全）
_FILENAME_PREFIX = 'te_man_video_compare_'


def _get_temp_directory():
    """ComfyUI temp 输出目录；不可用时退回系统临时目录。"""
    try:
        import folder_paths  # 仅 ComfyUI 环境存在

        return folder_paths.get_temp_directory()
    except Exception:  # noqa: BLE001
        import tempfile

        return os.path.join(tempfile.gettempdir(), 'te_man_open_video_compare')


class TEMANVideoComparerNode:
    """TE MAN 视频对比

    注册名: TE_image_pro_video_comparer
    规格:   spec/TE_Video_Comparer.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'compare_videos'
    OUTPUT_NODE = True
    DESCRIPTION = '在节点内叠加播放两个视频，鼠标移动分界线进行对比。'
    RETURN_TYPES = ()
    RETURN_NAMES = ()

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {}, 'optional': {'video_a': ('VIDEO', {'tooltip': '对比视频 A（可选）'}), 'video_b': ('VIDEO', {'tooltip': '对比视频 B（可选）'})}, 'hidden': {'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def compare_videos(self, video_a=None, video_b=None, prompt=None, extra_pnginfo=None, **kwargs):
        """两路可选 VIDEO 存 temp（MP4/H264）后用 PyAV 读元数据，返回 ui 载荷。

        OUTPUT_NODE 型节点：无 result tuple，返回
        ``{"ui": {"a_videos": [...], "b_videos": [...]}}``，每个条目含
        filename/subfolder/type/frame_count/frame_rate/duration（前端
        copyVideoData 逐字段消费）。
        """
        saved_a = None
        saved_b = None
        if video_a is not None:
            saved_a = self._save_preview(video_a, label='a')
        if video_b is not None:
            saved_b = self._save_preview(video_b, label='b')

        a_videos = [self._read_preview_metadata(saved_a)] if saved_a else []
        b_videos = [self._read_preview_metadata(saved_b)] if saved_b else []
        return {'ui': {'a_videos': a_videos, 'b_videos': b_videos}}

    def _save_preview(self, video, label=''):
        """VIDEO 对象 → temp 目录 MP4/H264 文件。

        返回 ``{"filename", "subfolder", "type", "label", "path"}``；
        comfy_api 不可用时抛中文 ImportError（惰性导入）。
        """
        import uuid

        try:
            from comfy_api.latest import VideoContainer, VideoCodec  # 惰性导入
        except Exception as exc:  # noqa: BLE001  非 ComfyUI 环境 / 旧版无 comfy_api
            raise ImportError('视频对比节点需要 comfy_api（ComfyUI 新版 API）支持: %s' % exc)

        temp_dir = _get_temp_directory()
        os.makedirs(temp_dir, exist_ok=True)
        filename = _FILENAME_PREFIX + uuid.uuid4().hex + '.mp4'
        file_path = os.path.join(temp_dir, filename)
        video.save_to(file_path, format=VideoContainer.MP4, codec=VideoCodec.H264)
        return {
            'filename': filename,
            'subfolder': '',
            'type': 'temp',
            'label': label,
            'path': file_path,
        }

    def _read_preview_metadata(self, saved):
        """PyAV 打开已保存的 mp4，读取 frame_count / frame_rate / duration。

        采用原版同款 gc 保护模式（gc.isenabled → disable → 关闭后恢复）；
        av 不可用时抛中文 ImportError（惰性导入）。
        """
        import gc

        try:
            import av  # 惰性导入
        except Exception as exc:  # noqa: BLE001  非 ComfyUI 环境 / 未安装 PyAV
            raise ImportError('视频对比节点读取元数据需要 PyAV (av) 库: %s' % exc)

        file_path = saved.get('path') or os.path.join(_get_temp_directory(), saved.get('filename', ''))
        frame_count = 0
        frame_rate = 0.0
        duration = 0.0

        gc_was_enabled = gc.isenabled()
        gc.disable()
        try:
            with av.open(file_path) as container:
                stream = next(
                    (s for s in container.streams if getattr(s, 'type', '') == 'video'),
                    None,
                )
                if stream is None:
                    raise ValueError('视频文件中没有可用的视频流: %s' % os.path.basename(file_path))
                if stream.average_rate is not None:
                    frame_rate = float(stream.average_rate)
                frame_count = int(getattr(stream, 'frames', 0) or 0)
                if frame_count <= 0:
                    frame_count = sum(1 for _ in container.decode(stream))
                if getattr(stream, 'duration', None) and getattr(stream, 'time_base', None):
                    duration = float(stream.duration) * float(stream.time_base)
                if duration <= 0.0 and frame_rate > 0.0 and frame_count > 0:
                    duration = frame_count / frame_rate
                if duration <= 0.0 and getattr(container, 'duration', None):
                    duration = float(container.duration) / 1000000.0  # AV_TIME_BASE 微秒
        finally:
            if gc_was_enabled:
                gc.enable()

        return {
            'filename': saved.get('filename', ''),
            'subfolder': saved.get('subfolder', ''),
            'type': saved.get('type', 'temp'),
            'frame_count': frame_count,
            'frame_rate': frame_rate,
            'duration': duration,
            'label': saved.get('label', ''),
        }

NODE_CLASS_MAPPINGS = {'TE_image_pro_video_comparer': TEMANVideoComparerNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_video_comparer': 'TE MAN 视频对比'}
