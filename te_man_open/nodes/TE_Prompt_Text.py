# -*- coding: utf-8 -*-
"""te_man_open · TE_Prompt_Text

本文件由 tools/codegen_skeletons.py 自动生成骨架，FUNCTION 方法已按
spec/TE_Prompt_Text.md（含动态 introspection 回填节）实现。
INPUT_TYPES 为与原版逐字段一致的真机契约；禁止改动契约块与类属性。

除节点本体外，本模块还复刻路由副作用：向 ComfyUI PromptServer 注册
``GET /te_prompt_text/view_reference``，为前端 @ 提及菜单的素材 chip 提供预览图。
"""

import os
import re
from typing import Any, Dict, List, Tuple

#: @ 提及标记（``<Picture N>`` / ``<Video N>`` / ``<Audio N>``）解析正则
REFERENCE_PATTERN = re.compile(r'<\s*(Picture|Video|Audio)\s+(\d+)\s*>', re.IGNORECASE)

#: 标记名 → 素材种类
_REFERENCE_KINDS = {'Picture': 'image', 'Video': 'video', 'Audio': 'audio'}


class TEPromptTextNode:
    """TE MAN MiniMaxH3增强提示词Prompt TEXT

    注册名: TE_prompt_text
    规格:   spec/TE_Prompt_Text.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'build_text'
    RETURN_TYPES = ('STRING', 'TE_H3_REFERENCES')
    RETURN_NAMES = ('text', 'H3参考素材')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'text': ('STRING', {'multiline': True, 'default': '', 'tooltip': '增强提示词文本。输入 @ 可选择下游节点已连接的图片、视频和音频引用。'}), 'reference_labels': ('STRING', {'multiline': True, 'default': '', 'tooltip': '由前端根据 H3 官方节点的素材连接自动生成。'})}}
        # --8<-- 契约结束 --8<--

    def build_text(self, **kwargs):
        """整理提示词文本，并从 reference_labels 解析出素材引用列表。

        ``reference_labels`` 由前端按下游 H3 节点连接自动生成（每个
        ``<Picture N>`` / ``<Video N>`` / ``<Audio N>`` 标记占一行），此处解析为
        去重后的引用列表（``{"label", "kind", "index"}``），作为
        ``TE_H3_REFERENCES`` 输出供 TE_H3_Prompt_Enhancer / TE_H3_Reference_Bridge
        的"H3参考素材"输入口消费（其 ``_reference_labels`` 再从中提取标签清单）。
        """
        text = str(kwargs.get('text') or '')
        reference_labels = str(kwargs.get('reference_labels') or '')
        return (text, _parse_reference_labels(reference_labels))


def _parse_reference_labels(reference_labels: str) -> List[Dict[str, Any]]:
    """把标记清单解析为引用列表（保持出现顺序、按规范形式去重）。"""
    references: List[Dict[str, Any]] = []
    seen = set()
    for match in REFERENCE_PATTERN.finditer(str(reference_labels or '')):
        kind_name = match.group(1).capitalize()
        index = int(match.group(2))
        label = '<{} {}>'.format(kind_name, index)
        if label in seen:
            continue
        seen.add(label)
        references.append({'label': label, 'kind': _REFERENCE_KINDS[kind_name], 'index': index})
    return references


NODE_CLASS_MAPPINGS = {'TE_prompt_text': TEPromptTextNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_prompt_text': 'TE MAN MiniMaxH3增强提示词Prompt TEXT'}


# ---------------------------------------------------------------------------
# 预览路由：GET /te_prompt_text/view_reference
# ---------------------------------------------------------------------------

def _resolve_reference_preview_path(
    filename: Any, subfolder: Any = '', image_type: Any = 'input'
) -> str:
    """解析查询参数 → ComfyUI 目录内的实际图片路径。

    校验链与 5 条中文错误文案严格按 spec/TE_Prompt_Text.md §5：
    缺少图片文件名 / 无效的图片文件名 / 无效的图片目录类型 /
    图片路径超出允许目录 / 图片文件不存在。
    """
    filename = str(filename or '').strip()
    if not filename:
        raise ValueError('缺少图片文件名')

    import folder_paths  # 惰性导入

    annotated = folder_paths.annotated_filepath(filename)
    if not annotated:
        raise ValueError('无效的图片文件名')

    image_type = str(image_type or 'input').strip() or 'input'
    base = folder_paths.get_directory_by_type(image_type)
    if not base:
        raise ValueError('无效的图片目录类型')

    rel = os.path.normpath(str(subfolder or '').strip())
    if rel in ('.', os.curdir):
        rel = ''
    full = os.path.join(base, rel, annotated) if rel else os.path.join(base, annotated)

    real_base = os.path.realpath(base)
    real_full = os.path.realpath(full)
    try:
        inside = os.path.commonpath([real_base, real_full]) == real_base
    except ValueError:
        inside = False
    if not inside:
        raise ValueError('图片路径超出允许目录')
    if not os.path.isfile(real_full):
        raise FileNotFoundError('图片文件不存在')
    return real_full


async def te_prompt_text_view_reference(request):
    """路由处理器：命中返回 FileResponse（``Cache-Control: no-store, max-age=0``）。"""
    from aiohttp import web  # 惰性导入

    query = request.rel_url.query
    try:
        image_path = _resolve_reference_preview_path(
            filename=query.get('filename'),
            subfolder=query.get('subfolder') or '',
            # 前端 buildViewUrl 发送的是 `type` 参数；`image_type` 兼容规格命名
            image_type=query.get('type') or query.get('image_type') or 'input',
        )
    except FileNotFoundError as e:
        return web.json_response({'error': str(e)}, status=404)
    except PermissionError:
        return web.json_response({'error': '图片文件不存在'}, status=404)
    except ValueError as e:
        return web.json_response({'error': str(e)}, status=400)

    headers = {'Cache-Control': 'no-store, max-age=0'}
    return web.FileResponse(image_path, headers=headers)


def _json_error(message: str, status: int = 400):
    """统一错误响应（与 spec §3 "异常 → json_response {"error": ...}" 对应）。"""
    from aiohttp import web  # 惰性导入

    return web.json_response({'error': str(message)}, status=status)


def _register_routes(prompt_server) -> None:
    """把预览路由注册到 ``PromptServer.instance.routes``（一次性）。"""
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED:
        return
    routes = getattr(prompt_server, 'routes', None)
    if routes is None:
        return
    routes.get('/te_prompt_text/view_reference')(te_prompt_text_view_reference)
    _ROUTES_REGISTERED = True


def _register_routes_when_ready() -> None:
    """后台轮询等待 PromptServer 就绪（daemon 线程）。"""
    import time

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


_ROUTES_REGISTERED = False
_ROUTE_REGISTER_THREAD_STARTED = False


def _schedule_route_registration() -> None:
    """PromptServer 可用则立即注册；不可用则 daemon 线程延迟注册。"""
    global _ROUTE_REGISTER_THREAD_STARTED
    try:
        from server import PromptServer  # 惰性导入（非 ComfyUI 环境直接跳过）
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
        name='te-man-prompt-text-route-register',
        daemon=True,
    ).start()


_schedule_route_registration()
