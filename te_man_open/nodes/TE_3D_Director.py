# -*- coding: utf-8 -*-
"""te_man_open · TE_3D_Director

本文件由 tools/codegen_skeletons.py 自动生成骨架，FUNCTION 方法已按
spec/TE_3D_Director.md（含动态 introspection 回填节）实现。
INPUT_TYPES 为与原版逐字段一致的真机契约；禁止改动契约块与类属性。

除节点本体外，本模块还复刻路由副作用：向 ComfyUI PromptServer 注册
``POST /te_3d_director/capture``，把前端 3D 面板导出的 PNG 截图写入
ComfyUI input 目录（canvas 模式）或资产素材库（library 模式）。
"""

import base64
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# 模块级常量（全部为动态 introspection 实锤值，spec/TE_3D_Director.md §2.2/§7.1）
# ---------------------------------------------------------------------------

DEFAULT_PROJECT = '默认项目'
DEFAULT_CATEGORY = '3D导演台'
DEFAULT_EXAMPLE_PROMPT = '让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面'
CAPTURE_FOLDER = 'TE_MAN_3D_Director'
ASSET_ROOT_NAME = 'TE_MAN'

#: 路由一次性注册标志（原版运行时同名状态量）
_ROUTES_REGISTERED = False
_ROUTE_REGISTER_THREAD_STARTED = False

_FILENAME_STEM_ILLEGAL_RE = re.compile(r'[<>:"|?*\x00-\x1f]+')
_CAPTURE_STEM_FORMAT = 'TE_MAN_3D_director_%Y%m%d_%H%M%S'


class TEMan3DDirectorNode:
    """TE MAN 3D导演台

    注册名: TE_3D_Director
    规格:   spec/TE_3D_Director.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/3D'
    FUNCTION = 'export_scene'
    OUTPUT_NODE = True
    DESCRIPTION = '打开 TE MAN 3D导演台，编辑角色、道具、机位和姿势，并输出场景 JSON 与构图提示词。'
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('scene_json', '示例提示词')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'scene_json': ('STRING', {'multiline': True, 'default': '{}', 'tooltip': '3D导演台保存的场景 JSON。通常由前端面板自动写入。'}), 'composition_prompt': ('STRING', {'multiline': True, 'default': '让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面', 'display_name': '示例提示词', 'label': '示例提示词', 'tooltip': '示例提示词，可根据导演台截图和参考图自行补充修改。'})}}
        # --8<-- 契约结束 --8<--

    def export_scene(self, **kwargs):
        """节点主执行：场景 JSON 与构图提示词的工作流出口。

        pyd 本体很薄（"透传为主"，spec §7.2），前端面板经 onSerialize/onConfigure
        把编辑结果回写进 scene_json / composition_prompt 两个 widget，这里原样输出。
        """
        scene_json = kwargs.get('scene_json')
        composition_prompt = kwargs.get('composition_prompt')
        if scene_json is None:
            scene_json = '{}'
        if composition_prompt is None:
            composition_prompt = DEFAULT_EXAMPLE_PROMPT
        return (scene_json, composition_prompt)


NODE_CLASS_MAPPINGS = {'TE_3D_Director': TEMan3DDirectorNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_3D_Director': 'TE MAN 3D导演台'}


# ---------------------------------------------------------------------------
# 路由支撑函数（qualname 与原版一一对应，spec/TE_3D_Director.md §6.1）
# ---------------------------------------------------------------------------

def _json_error(message: str, status: int = 400):
    """统一错误响应：``{'success': False, 'error': <message>}``。"""
    from aiohttp import web  # 惰性导入

    return web.json_response({'success': False, 'error': str(message)}, status=status)


def _input_dir() -> Path:
    """截图保存根目录 = ComfyUI input 目录（folder_paths 惰性导入）。"""
    import folder_paths

    return Path(folder_paths.get_input_directory())


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


def _decode_png_data_url(data_url: Any) -> bytes:
    """解析 ``data:image/png;base64,...`` → PNG 字节。

    错误文案（spec §5）：截图数据为空 / 截图数据必须是 base64 图片 / 只支持 PNG 截图。
    """
    data_url = str(data_url or '').strip()
    if not data_url:
        raise ValueError('截图数据为空')
    if not data_url.startswith('data:image/'):
        raise ValueError('截图数据必须是 base64 图片')
    header, _, b64_part = data_url.partition(',')
    content_type = header.split(':', 1)[-1].split(';', 1)[0].strip().lower()
    if content_type != 'image/png':
        raise ValueError('只支持 PNG 截图')
    if not b64_part:
        raise ValueError('截图数据必须是 base64 图片')
    try:
        return base64.b64decode(b64_part)
    except Exception:  # noqa: BLE001
        raise ValueError('截图数据必须是 base64 图片') from None


def _image_info(path: Path) -> Dict[str, Any]:
    """汇总图片信息：stat 的 ``st_size``/``st_mtime`` → ``size``/``mtime``。"""
    stat = path.stat()
    input_root = _input_dir()
    try:
        subfolder = path.parent.resolve().relative_to(input_root.resolve()).as_posix()
    except ValueError:
        subfolder = ''
    subfolder = '' if subfolder == '.' else subfolder
    return {
        'filename': path.name,
        'subfolder': subfolder,
        'type': 'input',
        'size': stat.st_size,
        'mtime': stat.st_mtime,
    }


def _asset_record(path: Path, project: str, category: str, relative_path: str) -> Dict[str, Any]:
    """构造资产库记录（kind/name/mtime/size/project/category/asset）。

    原版资产素材库无索引文件，元数据由目录扫描实时派生
    （spec/TE_Asset_Library.md §3.3），此处记录仅随响应返回供前端即时展示。
    """
    stat = path.stat()
    return {
        'kind': 'image',
        'name': path.name,
        'filename_stem': path.stem,
        'relative_path': relative_path,
        'project': project,
        'category': category,
        'asset': relative_path,
        'mtime': stat.st_mtime,
        'size': stat.st_size,
    }


def _target_dir_for_payload(payload: Dict[str, Any]) -> Tuple[Path, bool]:
    """按 ``save_mode`` 决定落盘目录。

    - ``'library'``（资产库模式）→ input/``ASSET_ROOT_NAME``/``assets``/项目/分类；
      越界报 ``非法素材库路径``。
    - 其他（``'canvas'``）→ input/``CAPTURE_FOLDER``；越界报 ``非法截图路径``。

    返回 ``(目标目录, is_library)``。
    """
    save_mode = str(payload.get('save_mode') or 'canvas').strip().lower()
    project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
    category = _clean_segment(payload.get('category')) or DEFAULT_CATEGORY
    input_root = _input_dir()

    if save_mode == 'library':
        base = input_root / ASSET_ROOT_NAME / 'assets'
        target = base / project / category
        if not _is_inside(target, base):
            raise ValueError('非法素材库路径')
        return target, True

    target = input_root / CAPTURE_FOLDER
    if not _is_inside(target, input_root):
        raise ValueError('非法截图路径')
    return target, False


async def te_3d_director_capture(request):
    """路由处理器：``POST /te_3d_director/capture``（spec §3.2 流程）。"""
    from aiohttp import web  # 惰性导入

    try:
        raw = await request.read()
    except Exception as e:  # noqa: BLE001
        return _json_error('读取请求体失败: {}'.format(e), 400)
    try:
        payload = json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _json_error('请求体不是有效的 JSON。', 400)
    if not isinstance(payload, dict):
        return _json_error('请求体不是有效的 JSON。', 400)

    try:
        png_bytes = _decode_png_data_url(payload.get('image_data'))
        target_dir, is_library = _target_dir_for_payload(payload)
        target_dir.mkdir(parents=True, exist_ok=True)

        stem = _clean_filename_stem(payload.get('filename_stem'))
        if not stem:  # 留空回退时间戳（spec §3.2 步骤 4）
            stem = time.strftime(_CAPTURE_STEM_FORMAT, time.localtime())
        target = _dedupe_path(target_dir / '{}.png'.format(stem))
        with open(str(target), 'wb') as fh:
            fh.write(png_bytes)

        info = _image_info(target)
        subfolder = str(info.get('subfolder') or '')
        relative_path = '{}/{}'.format(subfolder, info['filename']) if subfolder else str(info['filename'])
        response: Dict[str, Any] = {
            'success': True,
            'image': {'filename': info['filename'], 'subfolder': subfolder, 'type': 'input'},
            'target_path': str(target),
            'relative_path': relative_path,
            'status': 'saved',
        }
        if is_library:
            project = _clean_segment(payload.get('project')) or DEFAULT_PROJECT
            category = _clean_segment(payload.get('category')) or DEFAULT_CATEGORY
            response['asset_record'] = _asset_record(target, project, category, relative_path)
            response['message'] = '已加入资产库'
        return web.json_response(response)
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error('{}'.format(e), 500)


def _register_routes(prompt_server) -> None:
    """把截图落盘路由注册到 ``PromptServer.instance.routes``（一次性）。"""
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return
    routes = getattr(prompt_server, 'routes', None)
    if routes is None:
        return
    routes.post('/te_3d_director/capture')(te_3d_director_capture)
    _ROUTES_REGISTERED = True


def _register_routes_when_ready() -> None:
    """后台轮询等待 PromptServer 就绪（daemon 线程，内嵌 _wait_for_server 语义）。"""
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
    """PromptServer 可用则立即注册；不可用（尚未初始化）则 daemon 线程延迟注册。"""
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
    threading.Thread(
        target=_register_routes_when_ready,
        name='te-man-3d-director-route-register',
        daemon=True,
    ).start()


_schedule_route_registration()
