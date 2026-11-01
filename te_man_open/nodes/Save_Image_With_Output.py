# -*- coding: utf-8 -*-
"""te_man_open · Save_Image_With_Output

TE MAN 加载图像&保存图像 Image（TE_image_pro_save_image_with_output）纯 Python 复刻。
规格：spec/Save_Image_With_Output.md（含动态 introspection 回填节）。

本文件由 tools/codegen_skeletons.py 生成骨架；INPUT_TYPES 契约块保持逐字段一致，
实现只落在 FUNCTION 指向的 save_images_and_output 中。核心路径校验/预览序列化/
张量加载逻辑复用 shared/save_output_core（对应原版 save_image_with_output_core）。
"""

import os
import re
import time

try:
    from ..shared import save_output_core as _core
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared import save_output_core as _core

DEFAULT_SAVE_PATH_LABEL = '默认'
CUSTOM_FILENAME_TIME_FORMAT = 'TE_MAN_%Y-%m-%d-%H-%M-%S'

#: 非法文件名字符（原版正则原样）
INVALID_FILENAME_CHARS_RE = '[<>:"/\\|?*\x00-\x1f]+'

#: 官方 ui 通道的目录类型
OFFICIAL_UI_IMAGE_TYPES = ('output', 'temp', 'input')

_MSG_NO_IMAGES = ('images 未连接，且当前节点没有可用图像。'
                  '请先连接 images 输入，或先让这颗节点至少保存一次图像。')
_MSG_REPLAY_MISSING = ('当前节点找到了预览图记录，但对应图片文件已不存在。'
                       '请重新连接 images 再运行一次。')
_MSG_BAD_SAVE_PATH = ('保存位置必须是绝对目录，例如 F:\\test\\images。'
                      '默认或留空则使用 ComfyUI 默认 output。')


def _normalize_filename_prefix(prefix) -> str:
    """清洗非法文件名字符为 '_'；'/' 保留（子目录前缀语义），'..' 段防御性替换。"""
    text = str(prefix or '').strip()
    if not text:
        return CUSTOM_FILENAME_TIME_FORMAT
    segments = []
    for segment in text.split('/'):
        if segment in ('', '.', '..'):
            segments.append('_' if segment == '..' else segment)
            continue
        segments.append(re.sub(INVALID_FILENAME_CHARS_RE, '_', segment))
    return '/'.join(segments)


def _expand_time_placeholders(prefix) -> str:
    """对前缀应用时间格式（TE_MAN_%Y-%m-%d-%H-%M-%S 等）。"""
    text = str(prefix or '')
    try:
        return time.strftime(text, time.localtime())
    except Exception:  # noqa: BLE001  # 未识别的 % 片段按原文保留
        return text


def _get_output_dir():
    import folder_paths
    return folder_paths.get_output_directory()


def _normalize_save_path(save_path):
    """'默认'/留空 → 官方 output；非空值要求绝对目录并向上兜底建目录。"""
    text = str(save_path or '').strip()
    if not text or text == DEFAULT_SAVE_PATH_LABEL:
        return _get_output_dir()
    expanded = os.path.expandvars(os.path.expanduser(text))
    if not os.path.isabs(expanded):
        raise ValueError(_MSG_BAD_SAVE_PATH)
    normalized = os.path.normpath(expanded)
    os.makedirs(normalized, exist_ok=True)
    return normalized


def _is_absolute_save_path(save_path) -> bool:
    """是否为用户指定的外部位保存路径（'默认'/留空除外）。"""
    text = str(save_path or '').strip()
    if not text or text == DEFAULT_SAVE_PATH_LABEL:
        return False
    return _core._is_absolute_path(text)


def _is_inside_directory(directory, target_path) -> bool:
    """target_path 是否位于 directory 内（防逃逸；ntpath normcase/commonpath 套式）。"""
    normcase = getattr(os.path, 'normcase', None)
    if normcase is not None:
        directory = normcase(directory)
        target_path = normcase(target_path)
    try:
        return os.path.commonpath([os.path.abspath(directory),
                                   os.path.abspath(target_path)]) == os.path.abspath(directory)
    except ValueError:
        return False


def _build_png_metadata(te_prompt_text, prompt, extra_pnginfo):
    """PNG text chunks 元数据：workflow/prompt 序列化 + 自有 te_prompt_text 键。"""
    try:  # ComfyUI SaveImage 同款开关
        from comfy.cli_args import args
        disable_metadata = bool(getattr(args, 'disable_metadata', False))
    except Exception:  # noqa: BLE001
        disable_metadata = False
    if disable_metadata:
        return None
    try:
        from PIL.PngImagePlugin import PngInfo
    except Exception as e:  # noqa: BLE001
        raise RuntimeError('PNG 元数据组件不可用: ' + str(e)) from e
    metadata = PngInfo()
    if prompt is not None:
        metadata.add_text('prompt', _core.dumps_metadata_value(prompt))
    if extra_pnginfo:
        for key, value in extra_pnginfo.items():
            metadata.add_text(str(key), _core.dumps_metadata_value(value))
    # 自有键写纯文本（load_prompt_text_from_image_path 直接读字符串，不做 json 解码）
    metadata.add_text(_core.TE_PROMPT_METADATA_KEY,
                      _core.format_prompt_text(te_prompt_text))
    return metadata


def _make_unique_png_filename(directory, base_name, batch_number=None):
    """生成不冲突的 PNG 文件名；batch_number 提供时按 '_00005' 编号格式追加。"""
    base, ext = os.path.splitext(base_name)
    if not ext:
        ext = '.png'
    if batch_number is not None:
        return '{}_{:05d}{}'.format(base, batch_number, ext)
    candidate = base + ext
    counter = 1
    while os.path.exists(os.path.join(directory, candidate)):
        candidate = '{}_{:05d}{}'.format(base, counter, ext)
        counter += 1
    return candidate


def _save_images_to_directory(images_tensor, directory, base_name, pnginfo):
    """逐张落盘：numpy→clip→uint8→Image.fromarray→save(..., pnginfo, compress_level)。"""
    import numpy as np
    from PIL import Image
    array = images_tensor.cpu().numpy() if hasattr(images_tensor, 'cpu') \
        else np.asarray(images_tensor)
    if array.ndim == 3:  # 单张 HWC → 批量 BHWC
        array = array[None]
    saved_paths = []
    for batch_number in range(array.shape[0]):
        frame = (array[batch_number].clip(0.0, 1.0).astype(np.float32) * 255.0) \
            .astype(np.uint8)
        image = Image.fromarray(frame)
        filename = _make_unique_png_filename(directory, base_name, batch_number
                                             if array.shape[0] > 1 else None)
        target = os.path.join(directory, filename)
        kwargs = {'compress_level': 4}
        if pnginfo is not None:
            kwargs['pnginfo'] = pnginfo
        image.save(target, format='PNG', **kwargs)
        saved_paths.append(target)
    return saved_paths


def _write_prompt_txt_for_image(image_path, prompt_text):
    """与图片同目录、同文件名写 .txt（UTF-8）。"""
    if not prompt_text:
        return None
    txt_path = os.path.splitext(image_path)[0] + '.txt'
    with open(txt_path, 'w', encoding='utf-8') as handle:
        handle.write(prompt_text)
    return txt_path


def _output_ui_image_info(target_path, custom=False):
    """单张落盘结果 → ui image info（官方 output 通道 / te_custom_save 通道）。"""
    if custom:
        return _core.build_custom_save_image_info(target_path)
    return {
        'filename': os.path.basename(target_path),
        'subfolder': '',
        'type': 'output',
    }


def _official_ui_image_info(filename, subfolder='', image_type='output'):
    return {'filename': filename, 'subfolder': subfolder, 'type': image_type}


def _paths_to_ui_images(saved_paths, custom=False):
    return [_output_ui_image_info(path, custom=custom) for path in saved_paths]


def _build_save_ui(ui_images, te_prompt_text):
    return {'ui_images': list(ui_images), 'te_prompt_text': te_prompt_text}


def _load_replay_images(unique_id, extra_pnginfo):
    """回放本节点上一次保存的图像（节点 properties te_saved_preview_images）。"""
    from PIL import Image
    workflow_node = _core.find_workflow_node(
        _core.normalize_extra_pnginfo(extra_pnginfo).get('workflow'), unique_id)
    infos = _core.get_serialized_node_preview_images(workflow_node)
    if not infos:
        return None
    frames = []
    import numpy as np
    for info in infos:
        try:
            image_path = _core.resolve_image_info_path(info)
        except FileNotFoundError as e:  # noqa: PERF203
            raise ValueError(_MSG_REPLAY_MISSING) from e
        except ValueError:  # token/路径非法等，同样按丢失处理
            raise ValueError(_MSG_REPLAY_MISSING)
        with Image.open(image_path) as img:
            img = img.convert('RGB')
            frames.append(np.asarray(img).astype(np.float32) / 255.0)
    if not frames:
        return None
    import torch
    return torch.from_numpy(np.stack(frames, axis=0))


def _register_view_saved_route():
    """GET /te_image/view_saved —— PromptServer 惰性导入注册，不可用则跳过。

    返回 aiohttp FileResponse 直接回图；异常 → json_response({status/error/success})。
    响应头固定 Cache-Control: no-store, max-age=0 与 Pragma: no-cache 防缓存。
    """
    try:
        from server import PromptServer
        from aiohttp import web
    except Exception:  # noqa: BLE001  # 非 ComfyUI 环境（契约检查等）
        return
    routes = getattr(PromptServer.instance, 'routes', None)
    if routes is None:
        return

    async def te_image_view_saved(request):
        query = request.query
        try:
            path = _core.resolve_ui_image_path(
                query.get('type', ''),
                query.get('filename', ''),
                query.get('subfolder', ''),
                query.get('path'),
                query.get('token', ''),
            )
            if not os.path.isfile(path):
                raise FileNotFoundError('图片不存在: ' + path)
            headers = {'Cache-Control': 'no-store, max-age=0', 'Pragma': 'no-cache'}
            return web.FileResponse(path, headers=headers)
        except FileNotFoundError as e:
            return web.json_response(
                {'status': 'error', 'error': str(e), 'success': False}, status=404)
        except Exception as e:  # noqa: BLE001
            return web.json_response(
                {'status': 'error', 'error': str(e), 'success': False}, status=400)

    try:
        routes.get('/te_image/view_saved')(te_image_view_saved)
    except Exception:  # noqa: BLE001  # 路由已存在（重复加载）等情况
        pass


_register_view_saved_route()


class TESaveImageWithOutput:
    """TE MAN 加载图像&保存图像 Image

    注册名: TE_image_pro_save_image_with_output
    规格:   spec/Save_Image_With_Output.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'save_images_and_output'
    OUTPUT_NODE = True
    DESCRIPTION = '保存输入图像到默认 output 或指定目录，同时将同一批图像继续从右侧输出，并支持普通、多图和全景预览。'
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('images',)
    SEARCH_ALIASES = ('save image with output', 'save and pass through', 'save image passthrough')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'upload_image': (('', 'example.png'), {'default': '', 'image_upload': True, 'tooltip': '可选。左侧 images 未连接时，使用这里选择或上传的图像；左侧 images 一旦有输入，会优先覆盖这里的选择。要清空选择，请手动选回空白项。'}), 'filename_prefix': ('STRING', {'default': 'TE_MAN_%Y-%m-%d-%H-%M-%S', 'display_name': '文件名前缀', 'label': '文件名前缀', 'tooltip': '保存文件名/前缀。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S。多张图会自动追加编号；需要接文本时请使用左侧「保存文件名」。'}), 'save_path': ('STRING', {'default': '默认', 'display_name': '保存位置', 'label': '保存位置', 'tooltip': '保存位置。默认或留空时保存到 ComfyUI 默认 output；填写时必须是绝对目录，例如 F:\\test\\images。'})}, 'optional': {'images': ('IMAGE', {'tooltip': '要保存并继续输出的图像。留空时会尝试使用本节点上一次保存过的图像。'}), '保存文件名': ('STRING', {'forceInput': True, 'tooltip': '可选。接入文本后会覆盖上方文件名前缀输入框，作为实际保存文件名。'}), '保存提示词': ('STRING', {'forceInput': True, 'tooltip': '可选。接入文本后，会用与图片相同的文件名在同目录保存 .txt。'})}, 'hidden': {'unique_id': 'UNIQUE_ID', 'prompt': 'PROMPT', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    def save_images_and_output(self, **kwargs):
        """保存输入图像并同批输出；ui 携带 ui_images + te_prompt_text。"""
        images = kwargs.get('images')
        upload_image = str(kwargs.get('upload_image') or '').strip()
        filename_prefix = kwargs.get('filename_prefix')
        save_path = kwargs.get('save_path')
        if save_path is None:
            save_path = DEFAULT_SAVE_PATH_LABEL
        保存文件名 = str(kwargs.get('保存文件名') or '').strip()
        # 旧版参数名兼容链：保存提示词 → save_prompt_text（spec §3.1 推断）
        保存提示词 = str(kwargs.get('保存提示词')
                        or kwargs.get('save_prompt_text') or '').strip()
        unique_id = kwargs.get('unique_id')
        prompt = kwargs.get('prompt')
        extra_pnginfo = kwargs.get('extra_pnginfo')

        # ---- 1. 图像来源三级回退：连接张量 → upload_image → 上一次保存的预览 ----
        if images is None:
            if upload_image:
                images = _core.load_input_image_tensor(upload_image)
            else:
                images = _load_replay_images(unique_id, extra_pnginfo)
        if images is None:
            raise ValueError(_MSG_NO_IMAGES)

        # ---- 2. 保存目录归一化（默认/留空 → output；否则要求绝对目录） ----
        custom = _is_absolute_save_path(save_path)
        output_dir = _normalize_save_path(save_path)

        # ---- 3. 文件名归一化：接「保存文件名」文本则覆盖前缀；支持时间占位 ----
        effective = 保存文件名 or _normalize_filename_prefix(filename_prefix)
        effective = _expand_time_placeholders(effective)

        # ---- 4~6. 落盘 + PNG 元数据 + 提示词 .txt ----
        # PNG 元数据写未截断提示词（供下次回放读取），ui 侧展示才做截断
        te_prompt_source = 保存提示词 or _core.find_te_prompt_from_prompt_graph(
            prompt, unique_id, extra_pnginfo)
        pnginfo = _build_png_metadata(_core.format_prompt_text(te_prompt_source),
                                      prompt, extra_pnginfo)

        saved_paths = []
        if custom:
            base = os.path.basename(effective) or 'image'
            saved_paths = _save_images_to_directory(images, output_dir, base, pnginfo)
            ui_images = _paths_to_ui_images(saved_paths, custom=True)
        else:
            import folder_paths
            full_output_folder, filename, counter, subfolder, _ = \
                folder_paths.get_save_image_path(effective, output_dir)
            os.makedirs(full_output_folder, exist_ok=True)
            import numpy as np
            from PIL import Image
            array = images.cpu().numpy() if hasattr(images, 'cpu') else np.asarray(images)
            if array.ndim == 3:
                array = array[None]
            for batch_number, frame in enumerate(array):
                frame = (np.clip(255.0 * frame, 0.0, 255.0).astype(np.float32)) \
                    .astype(np.uint8)
                file = filename.replace('%batch_num%', str(batch_number))
                file = '{}_{:05d}_.png'.format(file, counter)
                target = os.path.join(full_output_folder, file)
                kwargs_save = {'compress_level': 4}
                if pnginfo is not None:
                    kwargs_save['pnginfo'] = pnginfo
                Image.fromarray(frame).save(target, format='PNG', **kwargs_save)
                saved_paths.append(target)
                counter += 1
            ui_images = [_official_ui_image_info(os.path.basename(p), subfolder)
                         for p in saved_paths]

        # ---- 7. ui 组装与返回：te_prompt_text 经 build_prompt_ui_text 截断 ----
        te_prompt_ui = _core.build_prompt_ui_text(te_prompt_source)
        if 保存提示词:
            _write_prompt_txt_for_image(saved_paths[0], 保存提示词)

        return (images, {'ui': _build_save_ui(ui_images, te_prompt_ui)})

    def VALIDATE_INPUTS(self, save_path='', **kwargs):  # noqa: N802
        """执行前校验：save_path 非默认时必须是绝对目录（其余参数交执行期）。"""
        if save_path and str(save_path).strip() not in (DEFAULT_SAVE_PATH_LABEL, ''):
            if not _is_absolute_save_path(save_path):
                return _MSG_BAD_SAVE_PATH
        return True


NODE_CLASS_MAPPINGS = {'TE_image_pro_save_image_with_output': TESaveImageWithOutput}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_save_image_with_output': 'TE MAN 加载图像&保存图像 Image'}
