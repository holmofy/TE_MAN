# -*- coding: utf-8 -*-
"""te_man_open · Save_Video_With_Frame_Capture

TE MAN 保存视频video（TE_image_pro_save_video）纯 Python 复刻。
规格：spec/Save_Video_With_Frame_Capture.md（含动态 introspection 回填节）。

VIDEO 连接或 local_video 选择 → VideoFromFile.save_to 或 shutil.copyfile →
isfile+getsize 校验 → ui.video + te_prompt_text；截帧 UI 由前端 JS 完成。
torch/av/ComfyUI 系全部惰性导入；INPUT_TYPES 契约块禁止手改。
"""

import os
import shutil

try:
    from ..shared import save_output_core as _core
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared import save_output_core as _core

#: 容器 → 输出扩展名（动态回填实锤：完整 9 对，运行时 dict 实测）
_VIDEO_EXT_BY_CONTAINER = {
    'mp4': '.mp4',
    'mov': '.mov',
    'webm': '.webm',
    'matroska': '.mkv',
    'mkv': '.mkv',
    'avi': '.avi',
    'mpegts': '.ts',
    'ts': '.ts',
    'gif': '.gif',
}

#: 前端上传 accept 对应的视频扩展名白名单（input 目录枚举兜底用）
_VIDEO_EXTENSIONS = ('.avi', '.gif', '.mkv', '.mov', '.mp4', '.ts', '.webm')

_HAS_COMFY_VIDEO = False

_MSG_NO_VIDEO = '未提供可保存的视频'
_MSG_NO_VIDEO_HINT = '请连接左侧 video，或在节点里选择本地视频'


def _get_input_video_choices() -> list:
    """枚举 input 目录本地视频（blank 项在前由 INPUT_TYPES 契约静态给出）。"""
    names = []
    try:
        import folder_paths
        input_dir = folder_paths.get_input_directory()
        files = os.listdir(input_dir)
        try:
            files = folder_paths.filter_files_content_types(files, ['video'])
        except Exception:  # noqa: BLE001  # 无该 API 时退化为扩展名白名单
            pass
        names = [f for f in files
                 if os.path.splitext(f)[1].lower() in _VIDEO_EXTENSIONS]
    except Exception:  # noqa: BLE001
        return []
    return sorted(names)


def _load_local_video(local_video):
    """按选择解析 input 目录本地视频路径。"""
    if not local_video:
        raise ValueError(_MSG_NO_VIDEO + '。' + _MSG_NO_VIDEO_HINT)
    try:
        import folder_paths
        if not folder_paths.exists_annotated_filepath(local_video):
            raise ValueError('视频文件不存在: ' + str(local_video))
        return folder_paths.get_annotated_filepath(local_video)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError('视频文件不存在: ' + str(local_video)) from e


def _normalize_extension(ext) -> str:
    """规范扩展名：strip + lower + 去点前缀。"""
    return str(ext or '').strip().lower().lstrip('.')


def _extract_video_source(video, local_video):
    """取视频源：左侧 video 优先，未连接时回退 local_video。

    返回 (video 对象或本地文件路径, is_file)。
    """
    if video is not None:
        return video, False
    if local_video:
        return _load_local_video(local_video), True
    raise ValueError(_MSG_NO_VIDEO + '。' + _MSG_NO_VIDEO_HINT)


def _seek_stream_start(video):
    """调 video.get_stream_source() 后 seek(0) 把流复位。"""
    try:
        stream = video.get_stream_source()
        if stream is not None and hasattr(stream, 'seek'):
            stream.seek(0)
    except Exception:  # noqa: BLE001  # 复位失败不阻塞保存
        pass


def _guess_video_extension(video) -> str:
    """用 video.get_container_format() 查 _VIDEO_EXT_BY_CONTAINER 猜扩展名。"""
    try:
        container = video.get_container_format()
    except Exception:  # noqa: BLE001
        container = None
    if container is not None:
        container = getattr(container, 'value', container)
        for token in str(container).lower().split(','):
            ext = _VIDEO_EXT_BY_CONTAINER.get(_normalize_extension(token))
            if ext:
                return ext
    return '.mp4'


def _validate_saved_video(target_path):
    """保存后校验：isfile + getsize>0，失败消息按规格原文。"""
    if not os.path.isfile(target_path):
        raise ValueError('视频文件保存失败：未生成输出文件')
    if os.path.getsize(target_path) <= 0:
        try:
            os.remove(target_path)
        except OSError:  # noqa: PERF203
            pass
        raise ValueError('视频文件保存失败：输出文件为空')


def _save_video_via_video_object(video, target_path):
    """通过 VIDEO 对象自身落盘（ComfyUI VideoInput.save_to）。"""
    try:
        video.save_to(target_path)
    except TypeError:  # 兼容无默认值的 save_to(path, format, codec, metadata)
        video.save_to(target_path, format=None, codec=None, metadata=None)


def _copy_video_source(source, target_path):
    """纯文件复制兜底：shutil.copyfile。"""
    shutil.copyfile(source, target_path)


def _save_video_to_output(video_source, filename_prefix, is_file):
    """编排保存：get_save_image_path 计数命名 → save_to/copyfile → 校验。

    返回 (target_path, saved_name, subfolder)。
    """
    import folder_paths
    output_dir = folder_paths.get_output_directory()
    full_output_folder, filename, counter, subfolder, _ = \
        folder_paths.get_save_image_path(str(filename_prefix or 'TE_MAN_Video'),
                                         output_dir)
    os.makedirs(full_output_folder, exist_ok=True)

    if is_file:
        ext = os.path.splitext(str(video_source))[1].lower() or '.mp4'
        ext = '.' + _normalize_extension(ext)
    else:
        _seek_stream_start(video_source)
        ext = _guess_video_extension(video_source)

    while True:  # %05d 计数命名（模仿 SaveImage），重名时顺延
        saved_name = '{}_{:05d}{}'.format(filename, counter, ext)
        target_path = os.path.join(full_output_folder, saved_name)
        if not os.path.exists(target_path):
            break
        counter += 1

    if is_file:
        _copy_video_source(video_source, target_path)
    else:
        _save_video_via_video_object(video_source, target_path)
    _validate_saved_video(target_path)
    return target_path, saved_name, subfolder


def _build_prompt_ui_text(prompt, unique_id, extra_pnginfo) -> str:
    """薄封装，转调 core 的提示词链路 + 截断规范。"""
    return _core.build_prompt_ui_text(
        _core.find_te_prompt_from_prompt_graph(prompt, unique_id, extra_pnginfo))


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
    SEARCH_ALIASES = ('save video', 'save video with preview', 'export video', 'video output')

    def __init__(self):
        self._has_comfy_video = _probe_comfy_video()

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'local_video': (('',), {'default': '', 'tooltip': '可选。左侧 video 未连接时，使用这里选择 input 目录中的本地视频。'}), 'filename_prefix': ('STRING', {'default': 'TE_MAN_Video', 'tooltip': '保存到 output 目录时使用的文件名前缀。'})}, 'optional': {'video': ('VIDEO', {'tooltip': '要保存的视频输入。接入后会优先使用这里的视频，并覆盖本地视频选择。'})}, 'hidden': {'unique_id': 'UNIQUE_ID', 'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def save_video_and_output(self, **kwargs):
        """保存视频到 output 并透传；ui 携带 video 列表 + te_prompt_text。"""
        video = kwargs.get('video')
        local_video = str(kwargs.get('local_video') or '').strip()
        filename_prefix = kwargs.get('filename_prefix') or 'TE_MAN_Video'
        unique_id = kwargs.get('unique_id')
        prompt = kwargs.get('prompt')
        extra_pnginfo = kwargs.get('extra_pnginfo')

        # ---- 1. 视频源：video 优先，回退 local_video ----
        video_source, is_file = _extract_video_source(video, local_video)

        # ---- 2~4. 落盘（save_to / copyfile）+ isfile/getsize 校验 ----
        target_path, saved_name, subfolder = _save_video_to_output(
            video_source, filename_prefix, is_file)

        # ---- 5. 透传输出：未连接 VIDEO 时用 VideoFromFile 包装本地副本 ----
        if not is_file:
            output_video = video_source
        else:
            output_video = _make_video_from_file(target_path)

        return (output_video, {
            'ui': {
                'video': [{'filename': saved_name, 'subfolder': subfolder,
                           'type': 'output'}],
                'te_prompt_text': _build_prompt_ui_text(prompt, unique_id,
                                                        extra_pnginfo),
            },
        })

    def VALIDATE_INPUTS(self, local_video='', filename_prefix='', **kwargs):  # noqa: N802
        """执行前校验：local_video 选择非空时必须存在于 input 目录。"""
        if local_video:
            try:
                import folder_paths
                if not folder_paths.exists_annotated_filepath(local_video):
                    return '视频文件不存在: ' + str(local_video)
            except Exception as e:  # noqa: BLE001
                return '视频文件不存在: ' + str(local_video)
        return True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')


def _probe_comfy_video() -> bool:
    """探测 comfy_api.input_impl.VideoFromFile 是否可用（_HAS_COMFY_VIDEO 守卫）。"""
    try:
        from comfy_api.input_impl import VideoFromFile  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _make_video_from_file(path):
    """VideoFromFile 包装（惰性导入，失败按规格抛 Invalid video file）。"""
    try:
        from comfy_api.input_impl import VideoFromFile
        return VideoFromFile(path)
    except Exception as e:  # noqa: BLE001
        raise ValueError('Invalid video file: ' + os.path.basename(path)) from e


NODE_CLASS_MAPPINGS = {'TE_image_pro_save_video': TESaveVideoWithFrameCapture}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_save_video': 'TE MAN 保存视频video'}
