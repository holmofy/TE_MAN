# -*- coding: utf-8 -*-
"""te_man_open · TE_Text_Display

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。
"""

import hashlib

try:
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 独立加载时兜底为标准 logging
    import logging

    logger = logging.getLogger("te_man_open")

#: 工作流元数据序列化键（与前端 web/js/te_text_display.js 共享的明文常量，spec §7.2）
SERIALIZED_TEXT_KEY = 'te_text_display_saved_text'
SERIALIZED_PREVIEW_KEY = 'te_text_display_preview_text'
SERIALIZED_SOURCE_KEY = 'te_text_display_source_text'

#: IS_CHANGED 日志中 input_text 未解析时的占位串（spec §3.3 字符串原文）
INPUT_TEXT_UNAVAILABLE_TEXT = 'unavailable (linked inputs are not resolved here)'


def _normalize_text(value):
    """文本规范化：嵌套列表/元组按行拼接为多行文本（对照前端 normalizeText）。"""
    if value is None:
        return ''
    if isinstance(value, (list, tuple)):
        return '\n'.join(_normalize_text(item) for item in value)
    return str(value)


def _first_dict(*candidates):
    """返回第一个 dict 类型的候选（extra_pnginfo / workflow 等取值兜底）。"""
    for item in candidates:
        if isinstance(item, dict):
            return item
    return {}


def _normalize_unique_id(value):
    """unique_id 归一为字符串；缺失时返回 None。"""
    if value is None:
        return None
    return str(value)


def _text_signature(*parts):
    """sha256 文本指纹：各分片以 NUL 分隔后 utf-8 编码，返回 hexdigest（spec §3.3）。"""
    digest = hashlib.sha256()
    for part in parts:
        digest.update(b'\x00')
        digest.update(str(part if part is not None else '').encode('utf-8'))
    return digest.hexdigest()


def _update_execution_metadata(extra_pnginfo, unique_id, saved_text, preview_text, source_text):
    """把文本回写进 extra_pnginfo['workflow']['nodes'][*]['properties']（spec §3.2）。

    按 unique_id 匹配节点；unique_id 缺失时回退按节点类型匹配，
    使保存的工作流 JSON 中持久保留节点文本（前端 onConfigure 据此恢复）。
    """
    workflow = _first_dict(extra_pnginfo).get('workflow')
    if not isinstance(workflow, dict):
        return
    nodes = workflow.get('nodes')
    if not isinstance(nodes, list):
        return
    for node in nodes:
        if not isinstance(node, dict):
            continue
        if unique_id is not None:
            if str(node.get('id')) != str(unique_id):
                continue
        elif node.get('type') != 'TE_text_display':
            continue
        properties = node.get('properties')
        if not isinstance(properties, dict):
            properties = {}
            node['properties'] = properties
        properties[SERIALIZED_TEXT_KEY] = saved_text
        properties[SERIALIZED_PREVIEW_KEY] = preview_text
        properties[SERIALIZED_SOURCE_KEY] = source_text


class TETextDisplayNode:
    """TE MAN TEXT文本展示

    注册名: TE_text_display
    规格:   spec/TE_Text_Display.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Utils'
    FUNCTION = 'show_text'
    OUTPUT_NODE = True
    DESCRIPTION = '显示、编辑并继续输出文本。可连接上游文本，也可直接在节点内输入。'
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('text',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'text': ('STRING', {'multiline': True, 'default': '', 'tooltip': '节点内文本。未连接 input_text 时会作为输出文本。'})}, 'optional': {'input_text': ('STRING', {'forceInput': True, 'tooltip': '可选上游文本。连接后优先显示并输出这里的内容。'}), 'use_edited_text': ('BOOLEAN', {'default': False}), 'edited_from_text': ('STRING', {'default': ''})}, 'hidden': {'unique_id': 'UNIQUE_ID', 'extra_pnginfo': 'EXTRA_PNGINFO'}}
        # --8<-- 契约结束 --8<--

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        """缓存指纹：sha256(text/edited_from/unique_id)，文本变化即触发重执行。

        input_text 为 forceInput 连接输入，在 IS_CHANGED 阶段不参与哈希，
        日志中以占位串标明（spec §3.3）。
        """
        text = _normalize_text(kwargs.get('text', ''))
        edited_from_text = _normalize_text(kwargs.get('edited_from_text', ''))
        unique_id = _normalize_unique_id(kwargs.get('unique_id'))
        if kwargs.get('input_text') is not None:
            input_text_repr = repr(kwargs.get('input_text'))
        else:
            input_text_repr = INPUT_TEXT_UNAVAILABLE_TEXT
        fingerprint = _text_signature(text, edited_from_text, unique_id or '')
        logger.info(
            'TE Text Display IS_CHANGED node=%s input_text=%s text=[%s] edited_from=[%s] fingerprint=[%s]'
            % (unique_id, input_text_repr, text, edited_from_text, fingerprint)
        )
        return fingerprint

    def show_text(self, text='', input_text=None, use_edited_text=False, edited_from_text='', unique_id=None, extra_pnginfo=None, **kwargs):
        """执行：input_text 有连接时优先，否则输出节点内 text 控件内容。

        - 返回 ``{"ui": {...}, "result": (output_text,)}``，ui 载荷供前端
          onExecuted 预览（默认键 ``text``，上游原文放 ``input_text``）；
        - ``use_edited_text`` / ``edited_from_text`` 的编辑态语义由前端控件
          维护（编辑结果本身就保存在 ``text`` 控件里），后端仅透传记录；
        - 通过 _update_execution_metadata 把文本持久化进工作流 properties。
        """
        text = _normalize_text(text)
        edited_from_text = _normalize_text(edited_from_text)
        has_upstream = input_text is not None
        upstream_text = _normalize_text(input_text) if has_upstream else ''
        if has_upstream:
            selected = 'input_text'
            output_text = upstream_text
        else:
            selected = 'text'
            output_text = text
        unique_id = _normalize_unique_id(unique_id)
        logger.info(
            'TE Text Display execute node=%s selected=%s text=[%s] input_text=[%s] edited_from=[%s] output=[%s]'
            % (unique_id, selected, text, upstream_text, edited_from_text, output_text)
        )
        _update_execution_metadata(
            extra_pnginfo,
            unique_id,
            saved_text=text,
            preview_text=output_text,
            source_text=upstream_text,
        )
        return {'ui': {'text': output_text, 'input_text': upstream_text}, 'result': (output_text,)}

NODE_CLASS_MAPPINGS = {'TE_text_display': TETextDisplayNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_text_display': 'TE MAN TEXT文本展示'}
