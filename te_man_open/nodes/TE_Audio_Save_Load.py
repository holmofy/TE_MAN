# -*- coding: utf-8 -*-
"""te_man_open · TE_Audio_Save_Load

TE MAN 加载音频&保存音频 Audio（TE_audio_save_load）纯 Python 复刻。
规格：spec/TE_Audio_Save_Load.md（含动态 introspection 回填节）。

流程：audio 输入优先否则 upload_audio → 按 start/end 裁切 → 0.1-4.0 变速
（torch linspace 重采样式）→ 保存 FLAC/MP3/OPUS 到 ComfyUI/output（前缀默认
audio/TE_MAN_%Y-%m-%d-%H-%M-%S，支持时间占位）→ 继续输出同一份音频。
保存复用 comfy_extras.nodes_audio.AudioSaveHelper 与 comfy_api.latest 的
get_save_audio_ui（惰性导入，失败抛中文错误）；torch/av/ComfyUI 系全部惰性导入。
"""

import hashlib
import math
import os
import re
import time

try:
    from ..shared import save_output_core as _core
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared import save_output_core as _core

#: 动态回填实锤：与 filename_prefix 默认值一致
DEFAULT_FILENAME_PREFIX = 'audio/TE_MAN_%Y-%m-%d-%H-%M-%S'

#: 保存格式枚举（INPUT_TYPES 契约同值）；mp3 品质在方法内部固定 128k
SUPPORTED_FORMATS = ('flac', 'mp3', 'opus')
_MP3_QUALITY = '128k'

#: 加载侧扩展名白名单（规格未实测完整集合，取 av 可解码的常见音频格式）
_LOAD_EXTENSIONS = ('.flac', '.mp3', '.opus', '.wav', '.ogg', '.m4a', '.aac', '.wma')

#: 时间占位符正则（规格原文）
_TIME_PLACEHOLDER_RE = re.compile(r'%(?:Y|m|d|H|M|S)(?![A-Za-z])')

_MSG_NO_AUDIO = '请连接 audio 输入，或点击“加载音频”选择一个本地音频文件。'


def _get_audio_choices() -> list:
    """扫描 ComfyUI input 目录生成音频文件下拉列表（空白项由契约静态给出）。"""
    names = []
    try:
        import folder_paths
        input_dir = folder_paths.get_input_directory()
        files = os.listdir(input_dir)
        try:
            files = folder_paths.filter_files_content_types(files, ['audio', 'video'])
        except Exception:  # noqa: BLE001
            pass
        names = [f for f in files
                 if os.path.splitext(f)[1].lower() in _LOAD_EXTENSIONS]
    except Exception:  # noqa: BLE001
        return []
    return sorted(names)


def _load_audio(upload_audio):
    """加载音频为 ComfyUI AUDIO dict：av 解码 → f32 PCM → unsqueeze(0)。

    返回 ({"waveform": [1, C, T], "sample_rate": sr}, duration 秒)。
    """
    if not upload_audio:
        raise ValueError(_MSG_NO_AUDIO)
    try:
        import folder_paths
        if not folder_paths.exists_annotated_filepath(upload_audio):
            raise ValueError('音频文件不存在: ' + str(upload_audio))
        audio_path = folder_paths.get_annotated_filepath(upload_audio)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError('音频文件不存在: ' + str(upload_audio)) from e

    ext = os.path.splitext(audio_path)[1].lower()
    if ext and ext not in _LOAD_EXTENSIONS:
        raise ValueError('不支持的音频格式: ' + os.path.basename(audio_path))

    import av
    import torch

    def f32_pcm(wav):
        """Convert audio to float 32 bits PCM format.（ComfyUI nodes_audio 同款）"""
        if wav.dtype.is_floating_point:
            return wav
        if wav.dtype == torch.int16:
            return wav.float() / (2 ** 15)
        if wav.dtype == torch.int32:
            return wav.float() / (2 ** 31)
        raise ValueError('Unsupported wav dtype: {}'.format(wav.dtype))

    try:
        with av.open(audio_path) as container:
            if not container.streams.audio:
                raise ValueError('不支持的音频格式: ' + os.path.basename(audio_path))
            stream = container.streams.audio[0]
            sample_rate = stream.codec_context.sample_rate
            n_channels = stream.channels
            frames = []
            for frame in container.decode(streams=stream.index):
                buf = torch.from_numpy(frame.to_ndarray())
                if buf.shape[0] != n_channels:
                    buf = buf.view(-1, n_channels).t()
                frames.append(buf)
            if not frames:
                raise ValueError('不支持的音频格式: ' + os.path.basename(audio_path))
            wav = torch.cat(frames, dim=1)
            wav = f32_pcm(wav)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError('音频文件不存在: ' + str(upload_audio)) from e

    audio = {'waveform': wav.unsqueeze(0), 'sample_rate': int(sample_rate)}
    duration = wav.shape[-1] / float(sample_rate) if sample_rate else 0.0
    return audio, duration


def _trim_audio(audio, start_time, end_time, source_duration=None):
    """按 start/end 切片波形：math.floor/round 换算采样点并 clamp。

    end_time <= 0 表示自动使用原音频结尾。返回裁切后的 AUDIO dict。
    """
    waveform = audio['waveform']
    sample_rate = audio['sample_rate']
    total = waveform.shape[-1]
    if source_duration is None:
        source_duration = total / float(sample_rate) if sample_rate else 0.0

    actual_start = int(math.floor(start_time * sample_rate))
    actual_start = max(0, min(actual_start, total))
    if end_time is None or end_time <= 0:
        actual_end = total
    else:
        actual_end = int(round(end_time * sample_rate))
        actual_end = max(0, min(actual_end, total))
    if actual_end <= actual_start:
        raise ValueError('开始时间必须小于结束时间，并且位于原音频 '
                         '{:.3f} 秒范围内。'.format(source_duration))
    trimmed = waveform[..., actual_start:actual_end]
    return {'waveform': trimmed, 'sample_rate': sample_rate}


def _change_audio_speed(audio, speed):
    """变速：torch.linspace 重采样式时间伸缩（线性插值）；speed==1.0 跳过。"""
    if speed is None or abs(speed - 1.0) < 1e-9 or speed <= 0:
        return audio
    import torch
    waveform = audio['waveform']
    src_len = waveform.shape[-1]
    if src_len <= 1:
        return audio
    target_len = max(1, int(round(src_len / speed)))
    positions = torch.linspace(0, src_len - 1, target_len,
                               device=waveform.device, dtype=torch.float32)
    idx0 = positions.floor().to(torch.long).clamp(0, src_len - 1)
    idx1 = (idx0 + 1).clamp(0, src_len - 1)
    # 波形布局 [B, C, T]（或 [C, T]），插值作用在最后一维
    frac = (positions - idx0.to(torch.float32)).view(
        *([1] * (waveform.dim() - 1)), -1)
    processed = waveform[..., idx0] * (1.0 - frac) + waveform[..., idx1] * frac
    return {'waveform': processed.to(waveform.dtype), 'sample_rate': audio['sample_rate']}


def _expand_filename_time(prefix) -> str:
    """展开文件名中的时间占位符（%Y/%m/%d/%H/%M/%S，time.localtime + strftime）。"""
    text = str(prefix or '')
    if '%' not in text:
        return text

    def _expand(match):
        try:
            return time.strftime('%' + match.group()[1:], time.localtime())
        except Exception:  # noqa: BLE001
            return match.group()

    return _TIME_PLACEHOLDER_RE.sub(_expand, text)


def _normalize_audio_results(results):
    """把各版本 AudioSaveHelper 的返回统一为 [{filename, subfolder, type}]。"""
    if results is None:
        return []
    if isinstance(results, dict):
        payload = results.get('ui', results)
        items = payload.get('audio', []) if isinstance(payload, dict) else []
    else:
        items = getattr(results, 'results', results)
    normalized = []
    for item in items or []:
        if isinstance(item, dict):
            normalized.append({'filename': item.get('filename'),
                               'subfolder': item.get('subfolder', ''),
                               'type': item.get('type', 'output')})
        else:  # SavedResult 等带属性的对象
            normalized.append({'filename': getattr(item, 'filename', None),
                               'subfolder': getattr(item, 'subfolder', ''),
                               'type': getattr(item, 'type', 'output')})
    return normalized


def _call_audio_save_helper(helper_cls, audio, fmt, filename_prefix, prompt,
                            extra_pnginfo):
    """按签名形态调用 AudioSaveHelper.save_audio；形态不匹配返回 None。"""
    import inspect
    func = getattr(helper_cls, 'save_audio', None)
    if func is None:
        return None
    try:
        params = list(inspect.signature(func).parameters)
    except (TypeError, ValueError):
        return None
    if 'folder_type' in params:  # 新式静态接口：交由 comfy_api.latest 分支处理
        return None
    kwargs = {}
    if 'filename_prefix' in params:
        kwargs['filename_prefix'] = filename_prefix
    if 'format' in params:
        kwargs['format'] = fmt
    if 'quality' in params:
        kwargs['quality'] = _MP3_QUALITY
    if 'prompt' in params:
        kwargs['prompt'] = prompt
    if 'extra_pnginfo' in params:
        kwargs['extra_pnginfo'] = extra_pnginfo
    if params and params[0] == 'self':  # 旧式实例方法（self 携带 output_dir/type）
        try:
            helper = helper_cls()
        except Exception:  # noqa: BLE001
            return None
        results = func(helper, audio, **kwargs)
    else:  # staticmethod / module-level 函数
        results = func(audio, **kwargs)
    return _normalize_audio_results(results)


def _save_audio_official(audio, fmt, filename_prefix, prompt, extra_pnginfo):
    """复用 ComfyUI 官方音频保存组件（惰性导入，失败抛中文错误）。

    优先 comfy_extras.nodes_audio.AudioSaveHelper（TE 原版复用入口），
    兜底 comfy_api.latest 的 get_save_audio_ui。
    """
    errors = []
    try:
        from comfy_extras.nodes_audio import AudioSaveHelper
    except Exception as e:  # noqa: BLE001
        AudioSaveHelper = None
        errors.append('comfy_extras.nodes_audio.AudioSaveHelper 导入失败: {}'.format(e))
    if AudioSaveHelper is not None:
        try:
            results = _call_audio_save_helper(AudioSaveHelper, audio, fmt,
                                              filename_prefix, prompt, extra_pnginfo)
            if results:
                return results
        except Exception as e:  # noqa: BLE001
            errors.append('AudioSaveHelper.save_audio 调用失败: {}'.format(e))

    try:  # 路径二：comfy_api.latest.get_save_audio_ui（模块级导出或 UI 命名空间）
        import comfy_api.latest as latest
        get_save_audio_ui = getattr(latest, 'get_save_audio_ui', None)
        if get_save_audio_ui is None:
            ui = getattr(latest, 'UI', None)
            get_save_audio_ui = getattr(getattr(ui, 'AudioSaveHelper', None),
                                        'get_save_audio_ui', None)
        if get_save_audio_ui is None:
            raise ImportError('comfy_api.latest 中未找到 get_save_audio_ui')
        results = get_save_audio_ui(audio, filename_prefix=filename_prefix, cls=None,
                                    format=fmt, quality=_MP3_QUALITY)
        return _normalize_audio_results(results)
    except Exception as e:  # noqa: BLE001
        errors.append('comfy_api.latest.get_save_audio_ui 调用失败: {}'.format(e))

    raise RuntimeError('音频保存组件不可用：' + '；'.join(errors))


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
        """加载/裁切/变速/保存音频并透传；ui 携带保存结果与输出时长。"""
        audio = kwargs.get('audio')
        upload_audio = str(kwargs.get('upload_audio') or '').strip()
        start_time = float(kwargs.get('start_time') or 0.0)
        end_time = float(kwargs.get('end_time') or 0.0)
        speed = float(kwargs.get('speed') or 1.0)
        fmt = str(kwargs.get('format') or 'flac').strip().lower()
        保存文件名 = str(kwargs.get('保存文件名') or '').strip()
        prompt = kwargs.get('prompt')
        extra_pnginfo = kwargs.get('extra_pnginfo')

        # ---- 1. 取音频：audio 插槽优先，否则 upload_audio ----
        if audio is not None:
            source_audio = audio
            source_duration = self._audio_duration(audio)
        else:
            source_audio, source_duration = _load_audio(upload_audio)

        # ---- 2. 校验（VALIDATE_INPUTS 之外的运行期防御） ----
        self._validate_ranges(start_time, end_time, speed, source_duration)

        # ---- 3. 裁切 + 变速 ----
        processed = _trim_audio(source_audio, start_time, end_time, source_duration)
        processed = _change_audio_speed(processed, speed)

        # ---- 4. 文件名展开：接「保存文件名」文本则覆盖前缀；支持时间占位 ----
        effective_prefix = 保存文件名 or str(kwargs.get('filename_prefix')
                                            or DEFAULT_FILENAME_PREFIX)
        effective_prefix = _expand_filename_time(effective_prefix.strip())

        # ---- 5. 保存到 ComfyUI/output（复用官方 AudioSaveHelper 机制） ----
        results = _save_audio_official(processed, fmt, effective_prefix,
                                       prompt, extra_pnginfo)

        # ---- 6. 输出：AUDIO 透传 + ui（保存结果 + 输出时长） ----
        output_duration = self._audio_duration(processed)
        return (processed, {
            'ui': {
                'audio': results,
                'te_audio_output_duration': round(output_duration, 3),
            },
        })

    def VALIDATE_INPUTS(self, start_time=0.0, end_time=0.0, speed=1.0,  # noqa: N802
                        format='flac', **kwargs):  # noqa: A002
        """执行前校验：按规格 §5 原文逐条返回错误消息。"""
        if start_time < 0:
            return '开始时间不能小于 0。'
        if end_time < 0:
            return '结束时间不能小于 0；使用 0 表示原音频结尾。'
        if speed <= 0:
            return '变速倍率必须大于 0。'
        if speed < 0.1 or speed > 4.0:
            return '变速倍率必须在 0.1 到 4.0 之间。'
        if str(format).strip().lower() not in SUPPORTED_FORMATS:
            return '不支持的音频格式: ' + str(format)
        return True

    @classmethod
    def IS_CHANGED(cls, upload_audio='', **kwargs):
        """用 sha256 对所选本地音频内容求 hexdigest 作为缓存判定；无文件时返回 nan。"""
        upload_audio = str(upload_audio or '').strip()
        if not upload_audio:
            return float('nan')
        try:
            import folder_paths
            if not folder_paths.exists_annotated_filepath(upload_audio):
                return float('nan')
            audio_path = folder_paths.get_annotated_filepath(upload_audio)
            digest = hashlib.sha256()
            with open(audio_path, 'rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
            return digest.hexdigest()
        except Exception:  # noqa: BLE001
            return float('nan')

    @staticmethod
    def _audio_duration(audio) -> float:
        """AUDIO dict → 时长（秒）；math.isfinite 防御 NaN。"""
        if not isinstance(audio, dict):
            return 0.0
        waveform = audio.get('waveform')
        sample_rate = audio.get('sample_rate') or 0
        if waveform is None or not sample_rate:
            return 0.0
        duration = waveform.shape[-1] / float(sample_rate)
        if not math.isfinite(duration):
            return 0.0
        return duration

    @staticmethod
    def _validate_ranges(start_time, end_time, speed, source_duration):
        """运行期数值防御（输入控件已约束，hidden 传参可能绕过）。"""
        if start_time < 0:
            raise ValueError('开始时间不能小于 0。')
        if end_time < 0:
            raise ValueError('结束时间不能小于 0；使用 0 表示原音频结尾。')
        if speed <= 0:
            raise ValueError('变速倍率必须大于 0。')
        if speed < 0.1 or speed > 4.0:
            raise ValueError('变速倍率必须在 0.1 到 4.0 之间。')
        if math.isfinite(source_duration) and source_duration > 0 \
                and start_time >= source_duration and end_time > 0:
            raise ValueError('开始时间必须小于结束时间，并且位于原音频 '
                             '{:.3f} 秒范围内。'.format(source_duration))


NODE_CLASS_MAPPINGS = {'TE_audio_save_load': TEAudioSaveLoad}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_audio_save_load': 'TE MAN 加载音频&保存音频 Audio'}
