# -*- coding: utf-8 -*-
"""save_output_core —— save_image_with_output_core.pyd 的纯 Python 复刻。

内部支撑库（非节点），为 Save_Image_With_Output / Save_Video_With_Frame_Capture /
/grid_split 等节点提供共享核心逻辑（规格见 spec/save_image_with_output_core.md）：

- 外部绝对路径保存解析与校验（te_custom_save 通道 + token 复核）
- 保存后预览图 image info 的打包（filename/subfolder/type/path/token）
- input/output 目录图片枚举缓存 NODE_IMAGE_CACHE（mtime/size 失效）
- 提示词回填链（图片元数据 / prompt 图上溯 / 截断规范）

约定：torch / PIL / numpy / folder_paths / ComfyUI 系全部惰性导入，
模块顶层只依赖标准库；本模块绝不写盘（只读），写盘由上层节点完成。
"""

import hashlib
import json
import os

try:  # 兼容 ntpath（原版运行于 Windows）：os.path 会随平台自动选择
    import os.path as _path
except ImportError:  # pragma: no cover
    _path = None


# ==================== 模块级常量（真机动态回填实锤值） ====================

#: 前端 save_image_with_output_clipspace.js 明文同值
TE_CUSTOM_SAVE_IMAGE_TYPE = 'te_custom_save'

#: 前端把回放预览/提示词写回节点 properties 的键
SERIALIZED_IMAGES_KEY = 'te_saved_preview_images'
SERIALIZED_PROMPT_KEY = 'te_saved_prompt_text'

#: 本插件自有 PNG 元数据键（动态回填修正：非 ComfyUI 标准 'parameters'，后者是兜底键）
TE_PROMPT_METADATA_KEY = 'te_prompt_text'

#: 节点内提示词展示上限（动态回填实锤：4000）
PROMPT_UI_MAX_CHARS = 4000

#: 目录枚举缓存（mtime/size 失效），真机快照实测为空 dict 的模块级可变缓存
NODE_IMAGE_CACHE = {}

#: 外部预览允许的图片扩展名（扩展名字符串成组出现在 pyd；是否含 MPO 未实测，暂不含）
TE_CUSTOM_SAVE_ALLOWED_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp')

#: TE 提示词源节点类名（pyd 中四个类名同在，是否为完整元组未实测，按现有证据取 4 项）
TE_PROMPT_SOURCE_CLASSES = (
    'TE_image_pro_special_async2',
    'TE_image_pro_banana',
    'TE_image_pro_gpt_image_2',
    'TE_image_pro_grok_image',
)

_TRUNCATE_SUFFIX = '......'
_TRUNCATE_NOTICE = '提示词过长，节点内已截断显示'
_PROMPT_SEPARATOR = '=========='
_UNKNOWN_NODE_PLACEHOLDER = 'UnknownNode'

OFFICIAL_UI_IMAGE_TYPES = ('output', 'temp', 'input')


# ==================== A. 外部路径保存与预览回放（te_custom_save 通道） ====================

def _is_absolute_path(path) -> bool:
    """判断（先做 expandvars/expanduser 展开）后的路径是否为绝对路径。"""
    if path is None:
        return False
    text = str(path)
    if not text.strip():
        return False
    expanded = _path.expandvars(_path.expanduser(text))
    return _path.isabs(expanded)


def _normalize_file_path(path) -> str:
    """归一化用户输入的外部路径：expandvars → expanduser → normpath。"""
    if path is None:
        raise ValueError('非法的图片路径')
    text = str(path).strip()
    if not text:
        raise ValueError('非法的图片路径')
    text = _path.expandvars(_path.expanduser(text))
    text = _path.normpath(text)
    if not text:
        raise ValueError('非法的图片路径')
    return text


def _has_supported_image_extension(filename) -> bool:
    """文件名（或完整路径）是否带白名单内的图片扩展名。"""
    if not filename:
        return False
    ext = _path.splitext(str(filename))[1].lower()
    return ext in TE_CUSTOM_SAVE_ALLOWED_EXTENSIONS


def make_custom_save_token(path) -> str:
    """对归一化后的外部绝对路径做 sha256 hexdigest 生成预览 token。

    [中] 依据：sha256/hexdigest/token 三串紧邻该函数名出现；
    是否加盐/截断未实测，此处取"归一化路径的完整 sha256 hexdigest"。
    """
    normalized = _normalize_file_path(path)
    on_windows = os.name == 'nt'
    if on_windows:  # ntpath.normcase：Windows 下大小写/分隔符不敏感，token 随之稳定
        normalized = _path.normcase(normalized)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def build_custom_save_image_info(path, filename=None) -> dict:
    """把外部绝对路径打包成 ui 委托的 image info（dict）。

    字段与前端 save_image_with_output_clipspace.js 的 parseImageInfoFromSrc 一一对应：
    {filename, subfolder: '', type: 'te_custom_save', path, token}
    """
    normalized = _normalize_file_path(path)
    return {
        'filename': filename or _path.basename(normalized),
        'subfolder': '',
        'type': TE_CUSTOM_SAVE_IMAGE_TYPE,
        'path': normalized,
        'token': make_custom_save_token(normalized),
    }


def resolve_custom_save_image_path(path) -> str:
    """校验并解析外部绝对保存路径，逐步对应规格 §5 的中文错误。"""
    if path is None or not str(path).strip():
        raise ValueError('缺少外部图片路径')
    if not _is_absolute_path(path):
        raise ValueError('外部图片路径必须是绝对路径')
    normalized = _normalize_file_path(path)
    if not _has_supported_image_extension(normalized):
        raise ValueError('外部预览只支持常见图片格式')
    if not os.path.isfile(normalized):
        raise FileNotFoundError('图片不存在: ' + normalized)
    return normalized


def _directory_by_type(directory_type) -> str:
    """目录类型 → ComfyUI 目录（folder_paths 系惰性导入）。"""
    try:
        import folder_paths
    except Exception as e:  # noqa: BLE001
        raise ValueError('不支持的图片目录类型: ' + str(directory_type)) from e
    if directory_type == 'output':
        return folder_paths.get_output_directory()
    if directory_type == 'input':
        return folder_paths.get_input_directory()
    try:
        result = folder_paths.get_directory_by_type(directory_type)
    except Exception:
        result = None
    if result:
        return result
    raise ValueError('不支持的图片目录类型: ' + str(directory_type))


def _check_subfolder_inside(directory, subfolder) -> str:
    """规范化 subfolder 并做目录穿越校验，非法时抛错。"""
    text = _path.normpath(str(subfolder or '').replace('\\', '/').strip('/'))
    if not text or text == '.':
        return ''
    if text.startswith('..') or _path.isabs(str(subfolder or '')):
        raise ValueError('非法的图片子目录')
    base = _path.abspath(directory)
    joined = _path.abspath(_path.join(base, text))
    if _path.relpath(joined, base).startswith('..'):
        raise ValueError('非法的图片子目录')
    return text


def resolve_image_info_path(image_info) -> str:
    """把 ui image info（dict）解析为磁盘路径，并做 token/穿越校验。"""
    if not isinstance(image_info, dict):
        raise ValueError('缺少图片文件名')
    image_type = str(image_info.get('type') or 'output')
    filename = image_info.get('filename')
    if not filename:
        raise ValueError('缺少图片文件名')

    if image_type == TE_CUSTOM_SAVE_IMAGE_TYPE:
        path = image_info.get('path')
        if path is None or not str(path).strip():
            raise ValueError('缺少外部图片路径')
        resolved = resolve_custom_save_image_path(path)
        token = str(image_info.get('token') or '')
        if token and token != make_custom_save_token(resolved):
            raise ValueError('外部图片预览 token 无效')
        return resolved

    if image_type in OFFICIAL_UI_IMAGE_TYPES:
        directory = _directory_by_type(image_type)
        subfolder = _check_subfolder_inside(directory, image_info.get('subfolder') or '')
        full = _path.join(directory, subfolder, str(filename)) if subfolder else _path.join(
            directory, str(filename))
        full = _path.normpath(full)
        if not os.path.isfile(full):
            raise FileNotFoundError('图片不存在: ' + str(filename))
        return full

    raise ValueError('不支持的图片目录类型: ' + image_type)


def resolve_ui_image_path(image_type, filename, subfolder='', path=None, token=None) -> str:
    """预览请求参数(type/filename/subfolder/path/token) → 磁盘路径 + token 复核。"""
    info = {
        'type': image_type,
        'filename': filename,
        'subfolder': subfolder or '',
    }
    if path:
        info['path'] = path
    if token:
        info['token'] = token
    return resolve_image_info_path(info)


# ==================== B. 缓存图片/输入图片与提示词回填 ====================

def load_cached_images(directory_type):
    """按目录类型枚举图片，缓存进 NODE_IMAGE_CACHE（mtime/size 失效）。

    directory_type 可传 'output'/'temp'/'input'，也可直接传含 type 的 image info dict。
    返回按文件修改时间新者优先排序的 info list（filename/subfolder/type/path）。
    """
    if isinstance(directory_type, dict):
        directory_type = directory_type.get('type') or 'output'
    directory = _directory_by_type(directory_type)
    stat = os.stat(directory)
    cache_key = (str(directory_type), directory)
    cached = NODE_IMAGE_CACHE.get(cache_key)
    if cached is not None and cached.get('mtime_ns') == stat.st_mtime_ns \
            and cached.get('size') == stat.st_size:
        return list(cached['images'])

    images = []
    for root, dirs, files in os.walk(directory):
        dirs.sort()
        files = sorted(files)
        try:
            import folder_paths
            files = folder_paths.filter_files_content_types(files, ['image'])
        except Exception:  # noqa: BLE001  # 无 ComfyUI 时退化为扩展名白名单
            pass
        for name in files:
            if not _has_supported_image_extension(name):
                continue
            full = _path.join(root, name)
            try:
                mtime = os.path.getmtime(full)
            except OSError:
                continue
            rel = _path.relpath(full, directory)
            subfolder = _path.dirname(rel).replace(os.sep, '/')
            images.append({
                'filename': name,
                'subfolder': '' if subfolder == '.' else subfolder,
                'type': directory_type,
                'path': full,
                'mtime': mtime,
            })
    # 内嵌排序 key（对应原版 load_input_image_tensor.lambda 的排序线索）
    images.sort(key=lambda item: (-item['mtime'], item['filename']))
    NODE_IMAGE_CACHE[cache_key] = {
        'images': images,
        'mtime_ns': stat.st_mtime_ns,
        'size': stat.st_size,
    }
    return list(images)


def read_image_metadata(image_path) -> dict:
    """读取已保存图片（PNG text chunks 优先）的元数据 dict。"""
    if not os.path.isfile(image_path):
        raise FileNotFoundError('图片不存在: ' + image_path)
    try:
        from PIL import Image
    except Exception as e:  # noqa: BLE001
        raise ValueError('无法读取图像文件: ' + str(e)) from e
    try:
        with Image.open(image_path) as img:
            metadata = {}
            text = getattr(img, 'text', None)
            if isinstance(text, dict):
                metadata.update({str(k): v for k, v in text.items() if isinstance(v, str)})
            for k, v in (img.info or {}).items():
                if isinstance(v, str) and k not in metadata:
                    metadata[str(k)] = v
            return metadata
    except OSError as e:
        raise ValueError('无法读取图像文件: ' + str(e)) from e


def sorted_prompt_nodes(nodes):
    """对序列化 prompt 的节点做排序（数字 id 优先，非数字按字符串）。

    返回 [(node_id, node_data), ...]。
    """
    if isinstance(nodes, dict):
        items = list(nodes.items())
    elif isinstance(nodes, (list, tuple)):
        items = [(n.get('id', index) if isinstance(n, dict) else index, n)
                 for index, n in enumerate(nodes)]
    else:
        items = []

    def sort_key(entry):
        node_id = entry[0]
        try:
            return (0, int(str(node_id)), '')
        except (TypeError, ValueError):
            return (1, 0, str(node_id))

    return sorted(items, key=sort_key)


def _iter_text_inputs(node) -> list:
    """取节点的字符串文本输入。"""
    inputs = node.get('inputs') or {} if isinstance(node, dict) else {}
    return [v for v in inputs.values() if isinstance(v, str) and v.strip()]


def _upstream_ids(prompt_data, node) -> list:
    """从节点 inputs 中取上游连接（值为 [node_id, slot] 形式）的 node_id 列表。"""
    result = []
    if not isinstance(node, dict):
        return result
    for value in (node.get('inputs') or {}).values():
        if isinstance(value, (list, tuple)) and value and isinstance(value[0], (str, int)):
            result.append(value[0])
    return result


def _find_prompt_key(prompt_data, node_id):
    """在 prompt 图中定位 node_id 的实际键（兼容 int/str 两种形态）。"""
    if not isinstance(prompt_data, dict):
        return None
    if node_id in prompt_data:
        return node_id
    try:
        as_int = int(str(node_id))
    except (TypeError, ValueError):
        return None
    return as_int if as_int in prompt_data else (str(node_id) if str(node_id) in prompt_data else None)


def _lookup_node(prompt_data, node_id):
    """按 id 取 prompt 图节点（兼容 int/str 键与连接引用形态不一致的情况）。"""
    if not isinstance(prompt_data, dict):
        return None
    if node_id in prompt_data:
        return prompt_data[node_id]
    key = _find_prompt_key(prompt_data, node_id)
    return prompt_data.get(key) if key is not None else None


def extract_text_from_prompt_graph(prompt_data, start_node_id=None) -> str:
    """递归遍历序列化 prompt（visited 防环），命中 TE_PROMPT_SOURCE_CLASSES
    的节点后提取其文本输入；多段用 '==========' 分隔线拼接。

    prompt_data 为完整 prompt 图 {node_id: node}；start_node_id 提供时仅从该节点
    向上游回溯（find_te_prompt_from_prompt_graph 使用），否则扫描全图。
    """
    texts = []
    visited = set()

    if start_node_id is not None:
        root_key = _find_prompt_key(prompt_data or {}, start_node_id)
        roots = [root_key] if root_key is not None else []
    else:
        roots = [node_id for node_id, _ in sorted_prompt_nodes(prompt_data or {})]

    def walk(node_id, node):
        key = str(node_id)
        if key in visited:
            return
        visited.add(key)
        if not isinstance(node, dict):
            return
        class_type = node.get('class_type') or node.get('type')
        if class_type in TE_PROMPT_SOURCE_CLASSES:
            texts.extend(_iter_text_inputs(node))
        for upstream_id in _upstream_ids(prompt_data, node):
            walk(upstream_id, _lookup_node(prompt_data, upstream_id))

    for root in roots:
        walk(root, _lookup_node(prompt_data, root))

    return format_prompt_text(_PROMPT_SEPARATOR.join(texts))


def format_prompt_text(text) -> str:
    """规范化提示词文本（\r\n → \n，去首尾空白）。"""
    if text is None:
        return ''
    return str(text).replace('\r\n', '\n').strip()


def load_prompt_text_from_image_path(image_path) -> str:
    """从已保存图片元数据读取提示词（自有键 te_prompt_text，兜底 ComfyUI 'parameters'）。"""
    metadata = read_image_metadata(image_path)
    value = metadata.get(TE_PROMPT_METADATA_KEY) or metadata.get('parameters')
    if not value:
        raise ValueError('当前图片没有可读取的提示词元数据')
    return format_prompt_text(value)


def load_prompt_text_from_ui_images(ui_images) -> str:
    """从 ui image info 列表逐条反查文件并读取提示词，多段用分隔线拼接。"""
    texts = []
    for info in ui_images or []:
        if not isinstance(info, dict):
            continue
        try:
            path = resolve_image_info_path(info)
            texts.append(load_prompt_text_from_image_path(path))
        except Exception:  # noqa: BLE001  # 单条失败不影响其余回放
            continue
    return format_prompt_text(_PROMPT_SEPARATOR.join(texts))


def get_connected_node_id(node_id, prompt, widget_input_map=None) -> str:
    """在 prompt 图中从 node_id 向上游查找连接节点 id。

    优先返回类名属于 TE_PROMPT_SOURCE_CLASSES 的上游节点；未命中返回 ''。
    widget_input_map（{输入名: 提示}）当前仅用于表达"关注哪些输入"的调用语义，
    实现按全部连接输入回溯（规格签名细节[低]）。
    """
    if not isinstance(prompt, dict):
        return ''
    root_key = _find_prompt_key(prompt, node_id)
    if root_key is None:
        return ''
    visited = set()
    queue = [(root_key, prompt[root_key])]
    while queue:
        qid, qnode = queue.pop(0)
        key = str(qid)
        if key in visited:
            continue
        visited.add(key)
        if not isinstance(qnode, dict):
            continue
        for upstream_id in _upstream_ids(prompt, qnode):
            upstream = _lookup_node(prompt, upstream_id)
            if not isinstance(upstream, dict):
                continue
            class_type = upstream.get('class_type') or upstream.get('type')
            if class_type in TE_PROMPT_SOURCE_CLASSES:
                return str(upstream_id)
            queue.append((upstream_id, upstream))
    return ''


def normalize_extra_pnginfo(extra_pnginfo) -> dict:
    """extra_pnginfo → dict（非 dict 时兜底 {}，保证含 workflow 键）。"""
    result = dict(extra_pnginfo) if isinstance(extra_pnginfo, dict) else {}
    result.setdefault('workflow', {})
    return result


def normalize_node_id(node_id) -> str:
    """node_id → 字符串，空值兜底 'UnknownNode' 占位。"""
    if node_id is None:
        return _UNKNOWN_NODE_PLACEHOLDER
    text = str(node_id).strip()
    return text or _UNKNOWN_NODE_PLACEHOLDER


def find_workflow_node(workflow, node_id) -> dict:
    """在 workflow['nodes'] 列表里按 id 定位前端节点 dict，找不到返回 {}。"""
    if not isinstance(workflow, dict):
        return {}
    target = normalize_node_id(node_id)
    for node in workflow.get('nodes') or []:
        if not isinstance(node, dict):
            continue
        if normalize_node_id(node.get('id')) == target:
            return node
    return {}


def get_serialized_node_preview_images(node) -> list:
    """读前端存回节点 properties 的 te_saved_preview_images。"""
    if not isinstance(node, dict):
        return []
    properties = node.get('properties') or {}
    value = (properties or {}).get(SERIALIZED_IMAGES_KEY)
    if isinstance(value, list):
        return value
    return []


def get_serialized_node_prompt_text(node) -> str:
    """读前端存回节点 properties 的 te_saved_prompt_text。"""
    if not isinstance(node, dict):
        return ''
    properties = node.get('properties') or {}
    value = (properties or {}).get(SERIALIZED_PROMPT_KEY)
    return format_prompt_text(value)


def find_te_prompt_from_prompt_graph(prompt, node_id, extra_pnginfo=None) -> str:
    """组合函数：优先取节点 properties 里的序列化文本，否则从 prompt 图向上游
    TE 提示词节点回溯提取。"""
    workflow_node = find_workflow_node(
        normalize_extra_pnginfo(extra_pnginfo).get('workflow'), node_id)
    serialized = get_serialized_node_prompt_text(workflow_node)
    if serialized:
        return serialized
    if not isinstance(prompt, dict):
        return ''
    if _find_prompt_key(prompt, node_id) is not None:
        walked = extract_text_from_prompt_graph(prompt, start_node_id=node_id)
        if walked:
            return walked
    # 起始节点不在图中或上游无 TE 提示词节点时，退化为全图扫描
    return extract_text_from_prompt_graph(prompt)


def build_prompt_ui_text(text) -> str:
    """规范文本并按 PROMPT_UI_MAX_CHARS 截断（'......' 后缀 + 截断提示语）。"""
    normalized = format_prompt_text(text)
    if len(normalized) > PROMPT_UI_MAX_CHARS:
        return normalized[:PROMPT_UI_MAX_CHARS] + _TRUNCATE_SUFFIX + _TRUNCATE_NOTICE
    return normalized


def get_input_image_choices() -> list:
    """枚举 ComfyUI input 目录现有图片（供 upload_image 组合框）。"""
    try:
        import folder_paths
        input_dir = folder_paths.get_input_directory()
        files = os.listdir(input_dir)
        try:
            files = folder_paths.filter_files_content_types(files, ['image'])
        except Exception:  # noqa: BLE001
            pass
        return sorted(name for name in files if _has_supported_image_extension(name))
    except Exception:  # noqa: BLE001
        return []


def load_input_image_tensor(image):
    """把 input 目录选中的图片加载为 ComfyUI IMAGE 张量（torch 惰性导入）。

    链路与规格一致：PIL 打开 → ImageOps.exif_transpose → convert('RGB')
    → numpy astype(float32)/255 → torch.from_numpy → unsqueeze(0)。
    """
    if not image:
        raise ValueError('Invalid image file: ')
    try:
        import folder_paths
        image_path = folder_paths.get_annotated_filepath(image)
    except Exception:  # noqa: BLE001  # 无 ComfyUI 时按相对路径处理
        image_path = image
    if not os.path.isfile(image_path):
        raise ValueError('Invalid image file: ' + str(image))
    try:
        from PIL import Image, ImageOps
        import numpy as np
        import torch
    except Exception as e:  # noqa: BLE001
        raise ValueError('无法读取图像文件: ' + str(e)) from e
    try:
        with Image.open(image_path) as img:
            img = ImageOps.exif_transpose(img)
            img = img.convert('RGB')
            represents = np.asarray(img).astype(np.float32) / 255.0
            return torch.from_numpy(represents).unsqueeze(0)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError('无法读取图像文件: ' + str(e)) from e


def make_prompt_image_metadata(prompt_text, workflow=None) -> dict:
    """便捷打包：供节点侧往 PNG text chunks 写入的自有键元数据。"""
    return {TE_PROMPT_METADATA_KEY: format_prompt_text(prompt_text), 'workflow': workflow}


def dumps_metadata_value(value) -> str:
    """把 prompt/workflow 序列化为 PNG 元数据字符串（dumps/indent/ensure_ascii）。"""
    return json.dumps(value, indent=2, ensure_ascii=False)
