# -*- coding: utf-8 -*-
"""te_man_open · TE_Asset_Library_routes —— TE_MAN 资产素材库 HTTP 路由层。

逆向规格: spec/TE_Asset_Library.md（含 §9 动态 introspection 回填节）。

⚠️ 本文件说明（请勿删除）：
1. 原版当前发布构建中，TE_Asset_Library 模块**不注册任何 ComfyUI 节点**
   （真机 introspection 实测：NODE_CLASS_MAPPINGS = {}、NODE_DISPLAY_NAME_MAPPINGS = {}，
   全插件 30 个运行时节点中无任何本模块节点，见 spec §9.1）。
   因此本复刻文件**故意不定义 NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS**，
   只复刻 11 条 /te_asset_library/* HTTP 路由（模块导入副作用）。
   请勿在本文件中添加节点注册——契约检查（tools/check_contract.py）会报"多余注册"。
2. 本文件不是 codegen 骨架（不会被 tools/codegen_skeletons.py 覆盖）。
3. PIL / aiohttp / folder_paths / torch 一律惰性导入：契约检查会 import te_man_open
   从而加载本模块，顶层仅允许标准库依赖。
"""

import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 模块级常量（全部为动态 introspection 实锤值，spec/TE_Asset_Library.md §9.2）
# ---------------------------------------------------------------------------

ASSET_ROOT_NAME = 'TE_MAN'
DEFAULT_PROJECT = '默认项目'
DEFAULT_CATEGORIES = ['人物', '产品', '场景', '背景', '提示词', '音频']
TEXT_CATEGORY = '提示词'
AUDIO_CATEGORY = '音频'
ASSET_KIND_IMAGE = 'image'
ASSET_KIND_TEXT = 'text'
ASSET_KIND_AUDIO = 'audio'
TEXT_PREVIEW_MAX_CHARS = 220
TE_CUSTOM_SAVE_IMAGE_TYPE = 'te_custom_save'

#: 受保护分类（后端精确成员未实锤；取前端解码集合 + 后端 '音频' 串证据，spec §3.2）
PROTECTED_CATEGORIES = {'__all__', '全部', '未分类', '', TEXT_CATEGORY, AUDIO_CATEGORY}

IMAGE_CONTENT_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.gif': 'image/gif',
}
TEXT_CONTENT_TYPES = {'.txt': 'text/plain'}
AUDIO_CONTENT_TYPES = {
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
    '.flac': 'audio/flac',
    '.ogg': 'audio/ogg',
    '.opus': 'audio/opus',
    '.m4a': 'audio/mp4',
    '.aac': 'audio/aac',
    '.wma': 'audio/x-ms-wma',
}
IMAGE_EXTENSIONS = set(IMAGE_CONTENT_TYPES)
TEXT_EXTENSIONS = set(TEXT_CONTENT_TYPES)
AUDIO_EXTENSIONS = set(AUDIO_CONTENT_TYPES)
ASSET_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS | AUDIO_EXTENSIONS

#: 文件名 stem 非法字符正则（spec §8.2）
_FILENAME_STEM_ILLEGAL_RE = re.compile(r'[<>:"|?*\x00-\x1f]+')

#: 提示词自动命名模板（spec §6）
_PROMPT_STEM_FORMAT = 'TE_MAN_prompt_%Y%m%d_%H%M%S'

#: 缩略图默认边长（前端取 Math.min(viewSize*2, 220)）
_THUMBNAIL_DEFAULT_SIZE = 220

_ROUTES_REGISTERED = False
_ROUTE_REGISTER_THREAD_STARTED = False


# ---------------------------------------------------------------------------
# 路径与安全
# ---------------------------------------------------------------------------

def _input_dir() -> Path:
    """ComfyUI input 目录（folder_paths 惰性导入）。"""
    import folder_paths

    return Path(folder_paths.get_input_directory())


def _asset_root() -> Path:
    """素材库物理根：<ComfyUI_input>/TE_MAN。"""
    return _input_dir() / ASSET_ROOT_NAME


def _is_inside(child: Path, parent: Path) -> bool:
    """路径越界校验：resolve + relative_to，失败回退 commonpath（防 ``..`` 逃逸）。"""
    try:
        child_res = Path(child).resolve()
        parent_res = Path(parent).resolve()
    except Exception:  # noqa: BLE001
        return False
    try:
        child_res.relative_to(parent_res)
        return True
    except ValueError:
        pass
    try:
        return os.path.commonpath([str(child_res), str(parent_res)]) == str(parent_res)
    except ValueError:
        return False


def _clean_segment(value: Any) -> str:
    """路径段清洗：折叠空白 ``\\s+``、去逗号，剥离首尾空白与路径分隔符。"""
    segment = re.sub(r'\s+', ' ', str(value or '')).replace(',', ' ').strip()
    return segment.strip('/\\') if segment else ''


def _clean_filename_stem(value: Any) -> str:
    """文件名清洗：非法字符 ``[<>:"|?*\\x00-\\x1f]+`` 替换为下划线。"""
    stem = _FILENAME_STEM_ILLEGAL_RE.sub('_', str(value or '')).strip()
    return stem.strip(' .') if stem else ''


def _dedupe_path(target: Path) -> Path:
    """目标文件已存在时去重改名（``<stem>_2``、``<stem>_3`` …）。"""
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    counter = 2
    while True:
        candidate = target.with_name('{}_{}{}'.format(stem, counter, suffix))
        if not candidate.exists():
            return candidate
        counter += 1


def _ensure_default_structure() -> None:
    """首次运行建库根、默认项目与默认分类（含提示词分类）。"""
    root = _asset_root()
    project_dir = root / DEFAULT_PROJECT
    project_dir.mkdir(parents=True, exist_ok=True)
    for category in DEFAULT_CATEGORIES:
        (project_dir / category).mkdir(exist_ok=True)


def _ensure_prompt_category(project: str) -> None:
    """保证指定项目下存在「提示词」分类目录。"""
    (_asset_root() / project / TEXT_CATEGORY).mkdir(parents=True, exist_ok=True)


def _project_dir(project: Any) -> Path:
    """解析项目目录（非法段/越界报错）。"""
    name = _clean_segment(project)
    if not name:
        raise ValueError('非法项目路径')
    target = _asset_root() / name
    if not _is_inside(target, _asset_root()) or name in ('.', '..'):
        raise ValueError('非法项目路径')
    return target


def _category_dir(project: Any, category: Any) -> Path:
    """解析分类目录（非法段/越界报错）。"""
    project_path = _project_dir(project)
    name = _clean_segment(category)
    if not name:
        raise ValueError('非法分类路径')
    target = project_path / name
    if not _is_inside(target, project_path) or name in ('.', '..'):
        raise ValueError('非法分类路径')
    return target


def _normalize_asset_relative_path(relative_path: Any) -> Tuple[str, str, str]:
    """把素材相对路径归一化为 (project, category, filename)。

    接受 ``TE_MAN/项目/分类/文件名`` 或 ``项目/分类/文件名``（去掉根前缀后的
    三段式，spec §3.1）；段数不符报「素材路径需要是 项目/分类/文件名」。
    """
    raw = str(relative_path or '').replace('\\', '/').strip().strip('/')
    if not raw:
        raise ValueError('素材路径需要是 项目/分类/文件名')
    parts = [p for p in raw.split('/') if p and p not in ('.',)]
    if parts and parts[0] == ASSET_ROOT_NAME:
        parts = parts[1:]
    if len(parts) != 3:
        raise ValueError('素材路径需要是 项目/分类/文件名')
    project = _clean_segment(parts[0])
    category = _clean_segment(parts[1])
    filename = os.path.basename(parts[2])
    if not project or not category or not filename or filename in ('..',):
        raise ValueError('素材路径需要是 项目/分类/文件名')
    return project, category, filename


def _resolve_asset_path(relative_path: Any) -> Path:
    """解析素材相对路径 → 库内实际文件路径（存在性 + 越界校验）。"""
    project, category, filename = _normalize_asset_relative_path(relative_path)
    root = _asset_root()
    target = root / project / category / filename
    if not _is_inside(target, root):
        raise ValueError('非法素材路径')
    if not target.is_file():
        raise FileNotFoundError('素材不存在: {}'.format(relative_path))
    return target


def _resolve_image_asset_path(relative_path: Any) -> Path:
    target = _resolve_asset_path(relative_path)
    if not _is_image_path(target.name):
        raise ValueError('不支持的图片格式')
    return target


def _resolve_text_asset_path(relative_path: Any) -> Path:
    target = _resolve_asset_path(relative_path)
    if not _is_text_path(target.name):
        raise ValueError('不支持的文本格式')
    return target


def _input_relative_path(path: Path) -> str:
    """文件 → input 相对路径（POSIX，带 ``TE_MAN/`` 前缀）。"""
    rel = Path(path).resolve().relative_to(_input_dir().resolve()).as_posix()
    return rel


def _is_image_path(name: Any) -> bool:
    return Path(str(name)).suffix.lower() in IMAGE_EXTENSIONS


def _is_text_path(name: Any) -> bool:
    return Path(str(name)).suffix.lower() in TEXT_EXTENSIONS


def _is_audio_path(name: Any) -> bool:
    return Path(str(name)).suffix.lower() in AUDIO_EXTENSIONS


def _is_asset_path(name: Any) -> bool:
    return Path(str(name)).suffix.lower() in ASSET_EXTENSIONS


# ---------------------------------------------------------------------------
# 列表 / 元数据（无索引文件，目录扫描实时派生）
# ---------------------------------------------------------------------------

def _iter_asset_files(directory: Path) -> List[Path]:
    """枚举目录下的素材文件（一层分类目录，不深入更深层）。"""
    if not directory.is_dir():
        return []
    files: List[Path] = []
    try:
        for entry in sorted(directory.iterdir()):
            if entry.is_file() and _is_asset_path(entry.name):
                files.append(entry)
    except OSError:
        return []
    return files


def _image_dimensions(path: Path) -> Optional[Tuple[int, int]]:
    """图片尺寸（PIL 惰性导入；失败返回 None）。"""
    try:
        from PIL import Image

        with Image.open(str(path)) as image:
            return image.size
    except Exception:  # noqa: BLE001
        return None


def _read_text_file(path: Path) -> str:
    """读文本素材（BOM 兼容 utf-8-sig，回退 utf-8）。"""
    try:
        with open(str(path), 'r', encoding='utf-8-sig') as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(str(path), 'r', encoding='utf-8', errors='replace') as fh:
            return fh.read()


def _text_preview(text: str) -> str:
    """预览截断（TEXT_PREVIEW_MAX_CHARS = 220）。"""
    cleaned = str(text or '').strip()
    if len(cleaned) <= TEXT_PREVIEW_MAX_CHARS:
        return cleaned
    return cleaned[:TEXT_PREVIEW_MAX_CHARS]


def _text_stats(text: str) -> Tuple[int, int]:
    """(line_count, char_count)。"""
    return len(text.splitlines()), len(text)


def _asset_record(path: Path, project: str, category: str, kind: str) -> Dict[str, Any]:
    """构造单条素材记录（字段与前端消费一一对应，spec §3.3）。"""
    stat = path.stat()
    record: Dict[str, Any] = {
        'name': path.name,
        'filename_stem': path.stem,
        'relative_path': _input_relative_path(path),
        'project': project,
        'category': category,
        'kind': kind,
        'mtime': stat.st_mtime,
        'size': stat.st_size,
    }
    if kind == ASSET_KIND_IMAGE:
        dimensions = _image_dimensions(path)
        info = {'filename': path.name, 'subfolder': '{}/{}/{}'.format(ASSET_ROOT_NAME, project, category), 'type': 'input'}
        if dimensions:
            record['width'], record['height'] = dimensions
        record['image_info'] = info
    elif kind == ASSET_KIND_TEXT:
        text = _read_text_file(path)
        line_count, char_count = _text_stats(text)
        record['text_preview'] = _text_preview(text)
        record['line_count'] = line_count
        record['char_count'] = char_count
    elif kind == ASSET_KIND_AUDIO:
        record['audio_info'] = {
            'filename': path.name,
            'subfolder': '{}/{}/{}'.format(ASSET_ROOT_NAME, project, category),
            'type': 'input',
        }
    return record


def _kind_of(path: Path) -> str:
    if _is_image_path(path.name):
        return ASSET_KIND_IMAGE
    if _is_text_path(path.name):
        return ASSET_KIND_TEXT
    if _is_audio_path(path.name):
        return ASSET_KIND_AUDIO
    return ''


def _list_assets(project: str, category: str, query: str = '') -> List[Dict[str, Any]]:
    """扫描项目/分类目录，实时派生素材记录列表。"""
    root = _asset_root()
    project_path = root / project
    if not project_path.is_dir():
        return []
    if category and category != '__all__':
        category_dirs = [(category, project_path / category)]
    else:
        category_dirs = [
            (entry.name, entry)
            for entry in sorted(project_path.iterdir())
            if entry.is_dir()
        ]
    keyword = str(query or '').strip().lower()
    assets: List[Dict[str, Any]] = []
    for category_name, category_path in category_dirs:
        for path in _iter_asset_files(category_path):
            if keyword and keyword not in path.name.lower():
                continue
            kind = _kind_of(path)
            if not kind:
                continue
            assets.append(_asset_record(path, project, category_name, kind))
    assets.sort(key=lambda item: item['mtime'], reverse=True)
    return assets


def _project_records(project_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """全部项目的分类树：[{name, categories:[{name, count}]}]。"""
    root = _asset_root()
    if project_path is None:
        if not root.is_dir():
            return []
        projects = [entry for entry in sorted(root.iterdir()) if entry.is_dir()]
    else:
        projects = [project_path] if project_path.is_dir() else []
    records = []
    for project_dir in projects:
        categories = []
        for entry in sorted(project_dir.iterdir()):
            if not entry.is_dir():
                continue
            count = len(_iter_asset_files(entry))
            categories.append({'name': entry.name, 'count': count})
        records.append({'name': project_dir.name, 'categories': categories})
    return records


# ---------------------------------------------------------------------------
# 入库 / 写入
# ---------------------------------------------------------------------------

def _resolve_input_file(filename: Any, subfolder: Any = '') -> Path:
    """解析 input 目录内的已上传文件路径（越界防护）。"""
    name = str(filename or '').strip()
    if not name:
        raise ValueError('缺少图片文件名')
    base = _input_dir()
    rel = os.path.normpath(str(subfolder or '').strip())
    if rel in ('.', os.curdir):
        rel = ''
    if rel and (os.path.isabs(rel) or rel == '..' or rel.startswith('..' + os.sep)):
        raise ValueError('非法的图片子目录')
    full = os.path.join(str(base), rel, name) if rel else os.path.join(str(base), name)
    real_base = os.path.realpath(str(base))
    real_full = os.path.realpath(full)
    try:
        inside = os.path.commonpath([real_base, real_full]) == real_base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError('非法的图片路径')
    if not os.path.isfile(real_full):
        raise FileNotFoundError('图片不存在: {}'.format(name))
    return Path(real_full)


def _resolve_info_source_path(info: Any, kind_label: str) -> Path:
    """解析 ``image_info``/``audio_info`` 指向的源文件。

    - ``input``/``output``/``temp`` → ``folder_paths.get_directory_by_type``；
    - ``te_custom_save``（TE 自定义保存目录）→ 优先共享库
      ``save_output_core.resolve_custom_save_image_path``，不可用时取 info['path']
      做最小校验（绝对路径 + isfile）；
    - 其他 → 「不支持的图片目录类型: 」/「不支持的音频目录类型: 」。
    """
    if not isinstance(info, dict):
        raise ValueError('没有找到可添加的{}'.format(kind_label))
    image_type = str(info.get('type') or 'input').strip()
    filename = str(info.get('filename') or '').strip()
    subfolder = str(info.get('subfolder') or '').strip()

    if image_type == TE_CUSTOM_SAVE_IMAGE_TYPE:
        path_value = str(info.get('path') or '').strip()
        if not path_value:
            raise ValueError('缺少外部图片路径')
        try:  # 共享核心库（te_man_open 复刻包）
            from ..shared.save_output_core import resolve_custom_save_image_path as _resolver
        except Exception:  # noqa: BLE001
            try:  # 原版模块名
                from ..shared.save_image_with_output_core import resolve_custom_save_image_path as _resolver
            except Exception:  # noqa: BLE001
                _resolver = None
        if _resolver is not None:
            return Path(_resolver(path_value))
        expanded = os.path.abspath(os.path.expanduser(os.path.expandvars(path_value)))
        if not os.path.isabs(expanded):
            raise ValueError('外部图片路径必须是绝对路径')
        if not os.path.isfile(expanded):
            raise FileNotFoundError('图片不存在: {}'.format(path_value))
        return Path(expanded)

    try:
        import folder_paths
    except Exception as e:  # noqa: BLE001
        raise RuntimeError('无法解析图片目录: {}'.format(e)) from e
    base = folder_paths.get_directory_by_type(image_type)
    if not base:
        if kind_label == '音频':
            raise ValueError('不支持的音频目录类型: {}'.format(image_type))
        raise ValueError('不支持的图片目录类型: {}'.format(image_type))
    if not filename:
        raise ValueError('缺少图片文件名')
    full = os.path.join(str(base), subfolder, filename) if subfolder else os.path.join(str(base), filename)
    real_base = os.path.realpath(str(base))
    real_full = os.path.realpath(full)
    try:
        inside = os.path.commonpath([real_base, real_full]) == real_base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError('非法的图片路径')
    if not os.path.isfile(real_full):
        raise FileNotFoundError('图片不存在: {}'.format(filename))
    return Path(real_full)


def _copy_to_library(source: Path, target_dir: Path, filename_stem: str, expected_extensions: set) -> Path:
    """把源文件复制入库（copy2 + 去重改名）。"""
    if source.suffix.lower() not in expected_extensions:
        raise ValueError('不支持的素材格式')
    stem = _clean_filename_stem(filename_stem) or _clean_filename_stem(source.stem)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _dedupe_path(target_dir / '{}{}'.format(stem, source.suffix.lower()))
    shutil.copy2(str(source), str(target))
    return target


def _default_prompt_filename_stem() -> str:
    """提示词留空标题时的自动命名：TE_MAN_prompt_%Y%m%d_%H%M%S。"""
    return time.strftime(_PROMPT_STEM_FORMAT, time.localtime())


def _write_text_to_library(project: str, title: str, text: str) -> Path:
    """提示词文本入库（utf-8 写盘，重名去重）。"""
    content = str(text or '')
    if not content.strip():
        raise ValueError('提示词内容不能为空')
    stem = _clean_filename_stem(title) or _default_prompt_filename_stem()
    _ensure_prompt_category(project)
    target_dir = _asset_root() / project / TEXT_CATEGORY
    target_dir.mkdir(parents=True, exist_ok=True)
    target = _dedupe_path(target_dir / '{}.txt'.format(stem))
    with open(str(target), 'w', encoding='utf-8') as fh:
        fh.write(content)
    return target


# ---------------------------------------------------------------------------
# 删除 / 更名
# ---------------------------------------------------------------------------

def _rename_asset(relative_path: Any, new_name: Any) -> Path:
    """素材更名（保留原扩展名；目标重名去重）。"""
    source = _resolve_asset_path(relative_path)
    name = _clean_filename_stem(new_name)
    if not name:
        raise ValueError('新文件名不能为空')
    original_suffix = source.suffix
    if not Path(name).suffix and original_suffix:
        name = '{}{}'.format(name, original_suffix)
    target = source.with_name(name)
    if not _is_inside(target, source.parent):
        raise ValueError('非法目标路径')
    if target.exists():
        raise FileExistsError('文件已存在: {}'.format(target.name))
    source.rename(str(target))
    return target


def _delete_asset(relative_path: Any) -> None:
    """删除单个素材文件。"""
    target = _resolve_asset_path(relative_path)
    target.unlink()


def _delete_category(project: Any, category: Any) -> None:
    """删除分类文件夹（rmtree；受保护分类/非目录拒绝）。"""
    name = _clean_segment(category)
    if not name or name in PROTECTED_CATEGORIES:
        raise ValueError('请选择一个可删除的分类')
    target = _category_dir(project, name)
    if not target.is_dir():
        raise ValueError('只能删除素材库里的分类文件夹')
    shutil.rmtree(str(target))


# ---------------------------------------------------------------------------
# HTTP 支撑
# ---------------------------------------------------------------------------

def _json_error(message: str, status: int = 400):
    """统一错误响应：``{'success': False, 'error': <message>}``。"""
    from aiohttp import web  # 惰性导入

    return web.json_response({'success': False, 'error': str(message)}, status=status)


async def _read_json_payload(request) -> Dict[str, Any]:
    """读取并解析 JSON 请求体（错误文案与原版路由层一致）。"""
    try:
        raw = await request.read()
    except Exception as e:  # noqa: BLE001
        raise ValueError('读取请求体失败: {}'.format(e)) from None
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError('请求体不是有效的 JSON。') from None
    if not isinstance(payload, dict):
        raise ValueError('请求体不是有效的 JSON。')
    return payload


# ---------------------------------------------------------------------------
# 11 条路由处理器
# ---------------------------------------------------------------------------

async def te_asset_library_list(request):
    """GET /te_asset_library/list?project&category&query"""
    try:
        _ensure_default_structure()
        query = request.rel_url.query
        project = _clean_segment(query.get('project')) or DEFAULT_PROJECT
        category = str(query.get('category') or '__all__').strip() or '__all__'
        keyword = query.get('query') or ''
        if not (_asset_root() / project).is_dir():
            project = DEFAULT_PROJECT
            category = '__all__'
        assets = _list_assets(project, category, keyword)
        return _json_ok({
            'projects': _project_records(),
            'current_project': project,
            'current_category': category,
            'assets': assets,
        })
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def _handle_te_asset_library_project(request):
    """POST /te_asset_library/project {project} → 新建项目目录"""
    try:
        payload = await _read_json_payload(request)
        project = _clean_segment(payload.get('project'))
        if not project:
            return _json_error('非法项目路径', 400)
        target = _asset_root() / project
        if not _is_inside(target, _asset_root()):
            return _json_error('非法项目路径', 400)
        target.mkdir(parents=True, exist_ok=True)
        for category in DEFAULT_CATEGORIES:
            (target / category).mkdir(exist_ok=True)
        return _json_ok({'message': '已新建项目: {}'.format(project), 'project': project})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def _handle_te_asset_library_category(request):
    """POST /te_asset_library/category {project, category} → 新建分类"""
    try:
        payload = await _read_json_payload(request)
        project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
        category = _clean_segment(payload.get('category'))
        if not category:
            return _json_error('非法分类路径', 400)
        target = _category_dir(project, category)
        target.mkdir(parents=True, exist_ok=True)
        return _json_ok({'message': '已新建分类: {}'.format(category), 'project': project, 'category': category})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def _handle_te_asset_library_delete_category(request):
    """POST /te_asset_library/category/delete {project, category} → rmtree 分类"""
    try:
        payload = await _read_json_payload(request)
        project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
        category = payload.get('category')
        _delete_category(project, category)
        return _json_ok({'message': '已删除分类', 'project': project, 'category': _clean_segment(category)})
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except OSError as e:
        return _json_error('{}'.format(e), 500)


def _library_record_response(target: Path, project: str, category: str, message: str) -> Dict[str, Any]:
    record = _asset_record(target, project, category, _kind_of(target))
    return {
        'message': message,
        'asset': record,
        'relative_path': record['relative_path'],
    }


async def te_asset_library_add(request):
    """POST /te_asset_library/add {project, category, filename_stem, upload_image | image_info}"""
    try:
        payload = await _read_json_payload(request)
        project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
        category = _clean_segment(payload.get('category')) or DEFAULT_CATEGORIES[0]
        filename_stem = str(payload.get('filename_stem') or '').strip()

        upload_image = str(payload.get('upload_image') or '').strip()
        image_info = payload.get('image_info')
        if upload_image:
            source = _resolve_input_file(upload_image, payload.get('subfolder') or '')
        elif isinstance(image_info, dict):
            source = _resolve_info_source_path(image_info, '图片')
        else:
            return _json_error('没有找到可添加的图片', 400)
        if not _is_image_path(source.name):
            return _json_error('只支持添加图片文件', 400)

        target_dir = _category_dir(project, category)
        target = _copy_to_library(source, target_dir, filename_stem, IMAGE_EXTENSIONS)
        return _json_ok(_library_record_response(target, project, category, '已添加到素材库'))
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except FileExistsError as e:
        return _json_error(str(e), 409)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def te_asset_library_audio_add(request):
    """POST /te_asset_library/audio/add {project, filename_stem, upload_audio | audio_info}"""
    try:
        payload = await _read_json_payload(request)
        project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
        category = AUDIO_CATEGORY
        filename_stem = str(payload.get('filename_stem') or '').strip()

        upload_audio = str(payload.get('upload_audio') or '').strip()
        audio_info = payload.get('audio_info')
        if upload_audio:
            source = _resolve_input_file(upload_audio, payload.get('subfolder') or '')
        elif isinstance(audio_info, dict):
            source = _resolve_info_source_path(audio_info, '音频')
        else:
            return _json_error('没有找到可添加的音频', 400)
        if not _is_audio_path(source.name):
            return _json_error('只支持添加音频文件', 400)

        target_dir = _category_dir(project, category)
        target = _copy_to_library(source, target_dir, filename_stem, AUDIO_EXTENSIONS)
        return _json_ok(_library_record_response(target, project, category, '已添加到素材库'))
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except FileExistsError as e:
        return _json_error(str(e), 409)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def te_asset_library_text_add(request):
    """POST /te_asset_library/text/add {project, title, text} → 分类固定「提示词」"""
    try:
        payload = await _read_json_payload(request)
        project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
        title = str(payload.get('title') or '').strip()
        text = str(payload.get('text') or '')
        if not text.strip():
            return _json_error('提示词内容不能为空', 400)
        target = _write_text_to_library(project, title, text)
        return _json_ok(_library_record_response(target, project, TEXT_CATEGORY, '已添加提示词'))
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def _handle_te_asset_library_text_get(request):
    """GET /te_asset_library/text/get?relative_path&limit_chars → 返回文本内容"""
    try:
        query = request.rel_url.query
        relative_path = query.get('relative_path') or query.get('path') or ''
        target = _resolve_text_asset_path(relative_path)
        text = _read_text_file(target)
        limit_raw = query.get('limit_chars')
        if limit_raw:
            try:
                limit = int(limit_raw)
            except (TypeError, ValueError):
                limit = 0
            if limit > 0:
                text = text[:limit]
        return _json_ok({
            'text': text,
            'name': target.name,
            'relative_path': _input_relative_path(target),
            'line_count': len(text.splitlines()),
            'char_count': len(text),
        })
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def _handle_te_asset_library_rename(request):
    """POST /te_asset_library/rename {relative_path, new_name}"""
    try:
        payload = await _read_json_payload(request)
        relative_path = payload.get('relative_path')
        new_name = payload.get('new_name')
        if not str(relative_path or '').strip():
            return _json_error('请先选择一个素材', 400)
        target = _rename_asset(relative_path, new_name)
        project, category = target.parent.parent.name, target.parent.name
        return _json_ok(_library_record_response(target, project, category, '已更名: {}'.format(target.name)))
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except FileExistsError as e:
        return _json_error(str(e), 409)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def _handle_te_asset_library_delete(request):
    """POST /te_asset_library/delete {relative_path}"""
    try:
        payload = await _read_json_payload(request)
        relative_path = payload.get('relative_path')
        if not str(relative_path or '').strip():
            return _json_error('请先选择一个素材', 400)
        _delete_asset(relative_path)
        return _json_ok({'deleted': True, 'message': '已删除'})
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


async def te_asset_library_thumbnail(request):
    """GET /te_asset_library/thumbnail?path&size → PIL LANCZOS 缩略图（WebP）

    响应头：Content-Type: image/webp、Cache-Control: no-cache、X-TE-Asset-MTime。
    """
    from aiohttp import web  # 惰性导入

    try:
        query = request.rel_url.query
        relative_path = query.get('path') or query.get('relative_path') or ''
        target = _resolve_image_asset_path(relative_path)
        try:
            size = int(query.get('size') or _THUMBNAIL_DEFAULT_SIZE)
        except (TypeError, ValueError):
            size = _THUMBNAIL_DEFAULT_SIZE
        size = max(16, min(size, 1024))

        from PIL import Image, ImageOps

        with Image.open(str(target)) as image:
            oriented = ImageOps.exif_transpose(image).convert('RGB')
            oriented.thumbnail((size, size), Image.Resampling.LANCZOS)
            from io import BytesIO

            buffer = BytesIO()
            oriented.save(buffer, format='WEBP', quality=85)
        stat = target.stat()
        return web.Response(
            body=buffer.getvalue(),
            content_type='image/webp',
            headers={
                'Cache-Control': 'no-cache',
                'X-TE-Asset-MTime': str(int(stat.st_mtime)),
            },
        )
    except ValueError as e:
        return _json_error(str(e), 400)
    except FileNotFoundError as e:
        return _json_error(str(e), 404)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


def _json_ok(data: Dict[str, Any]):
    """统一成功响应：附带 success 标志。"""
    from aiohttp import web  # 惰性导入

    body = dict(data)
    body.setdefault('success', True)
    return web.json_response(body)


# ---------------------------------------------------------------------------
# PromptServer 惰性导入注册（模块导入副作用）
# ---------------------------------------------------------------------------

def _register_routes(prompt_server) -> None:
    """把 11 条路由注册到 ``PromptServer.instance.routes``（一次性）。"""
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return
    routes = getattr(prompt_server, 'routes', None)
    if routes is None:
        return
    routes.get('/te_asset_library/list')(te_asset_library_list)
    routes.post('/te_asset_library/project')(_handle_te_asset_library_project)
    routes.post('/te_asset_library/category')(_handle_te_asset_library_category)
    routes.post('/te_asset_library/category/delete')(_handle_te_asset_library_delete_category)
    routes.post('/te_asset_library/add')(te_asset_library_add)
    routes.post('/te_asset_library/audio/add')(te_asset_library_audio_add)
    routes.post('/te_asset_library/text/add')(te_asset_library_text_add)
    routes.get('/te_asset_library/text/get')(_handle_te_asset_library_text_get)
    routes.post('/te_asset_library/rename')(_handle_te_asset_library_rename)
    routes.post('/te_asset_library/delete')(_handle_te_asset_library_delete)
    routes.get('/te_asset_library/thumbnail')(te_asset_library_thumbnail)
    _ROUTES_REGISTERED = True


def _register_routes_when_ready() -> None:
    """后台轮询等待 PromptServer 就绪（daemon 线程）。"""
    while True:
        try:
            from server import PromptServer
        except Exception:  # noqa: BLE001  # 非 ComfyUI 环境，放弃注册
            return
        if getattr(PromptServer, 'instance', None) is not None:
            try:
                _register_routes(PromptServer.instance)
            except Exception:  # noqa: BLE001
                pass
            return
        time.sleep(1.0)


def _schedule_route_registration() -> None:
    """PromptServer 可用则立即注册；不可用则 daemon 线程延迟注册。"""
    global _ROUTE_REGISTER_THREAD_STARTED
    try:
        from server import PromptServer  # 惰性导入（契约检查等非 ComfyUI 环境无此模块）
    except Exception:  # noqa: BLE001
        return
    if getattr(PromptServer, 'instance', None) is not None:
        try:
            _register_routes(PromptServer.instance)
        except Exception:  # noqa: BLE001
            pass
        return
    if _ROUTE_REGISTER_THREAD_STARTED:
        return
    _ROUTE_REGISTER_THREAD_STARTED = True
    import threading

    threading.Thread(
        target=_register_routes_when_ready,
        name='te-man-asset-library-route-register',
        daemon=True,
    ).start()


_schedule_route_registration()
