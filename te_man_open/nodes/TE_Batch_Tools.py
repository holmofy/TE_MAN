# -*- coding: utf-8 -*-
"""te_man_open · TE_Batch_Tools
本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

============================ 批量执行机制说明 ============================
TE MAN 批量工具的"批量执行"由**前端扩展驱动**（web/js/te_man_batch_tools.js，
扩展名 TE.ManBatchTools），后端节点内不做任何批量循环：
1. 前端把卡片/图片列表序列化进隐藏输入 prompts_json / image_list；
2. 批量执行时，前端从 `从指定编号继续`(1 基) 开始逐条：把本次条目编号写入
   `index` widget →（可选按 `执行范围` 裁剪语图）→ graphToPrompt 入队
   api.queuePrompt(-1, prompt) → 每条等待 `执行间隔时间` 秒
   （最小让步 MIN_QUEUE_YIELD_MS=0x50）；
3. 因此节点 FUNCTION 只做"按 index 取第 N 条"这一件事；
   随机顺序（Fisher-Yates 洗牌）、最大任务数截断、停止时 DELETE /queue
   清空未开始任务等调度行为全部发生在前端。
`增强设置` 节点同样只是把 4 个参数打包为 TE_BATCH_ENHANCED_SETTINGS 输出，
实际消费主要在前端（沿输入 link 找到设置节点读 widget 值）。
========================================================================"""

import hashlib
import json
import re

BATCH_SETTINGS_TYPE = 'TE_BATCH_ENHANCED_SETTINGS'
BATCH_SCOPE_OPTIONS = ['只执行当前线', '执行整个工作流']

# ---------------------------------------------------------------------------
# 提示词解析（spec/TE_Batch_Tools.md §4.1，前后端同源正则，字节级还原）
# ---------------------------------------------------------------------------

#: 单行清洗：去 bullet（- * •）与序号（1. / 1、 / 1） / 一、）前缀
_CLEAN_PROMPT_PREFIX_RE = re.compile(
    r'^\s*(?:[-*•]\s+|\d{1,4}[.、）]\s*|[一二三四五六七八九十百]+[、.)）]\s*)')
#: `---` 分段分隔线
_SEPARATOR_LINE_RE = re.compile(r'^\s*-{3,}\s*$')
#: ```json 围栏提取（DOTALL/IGNORECASE）
_CODE_FENCE_RE = re.compile(r'```(?:json)?\s*(.*?)```', re.DOTALL | re.IGNORECASE)


def _clean_prompt_line(line):
    """清洗单条提示词行：去 bullet/序号前缀 + 首尾空白。"""
    text = '' if line is None else str(line)
    return _CLEAN_PROMPT_PREFIX_RE.sub('', text).strip()


def _prompts_from_json_data(data):
    """JSON 卡片数据 → 提示词列表。

    支持三种卡片形态：
    - 字符串数组
    - [{prompt: ...}] / [{text: ...}] / [{content: ...}] 对象数组
    - {"prompts": [...]} / {"items": [...]} 包装
    """
    items = None
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ('prompts', 'items', 'cards', 'list'):
            value = data.get(key)
            if isinstance(value, list):
                items = value
                break
        if items is None:
            items = [data]
    if items is None:
        return []
    prompts = []
    for item in items:
        if isinstance(item, str):
            prompts.append(item)
        elif isinstance(item, dict):
            for key in ('prompt', 'text', 'content', 'value'):
                if isinstance(item.get(key), str):
                    prompts.append(item[key])
                    break
    return [p for p in (_clean_prompt_line(p) for p in prompts) if p]


def parse_batch_prompts(raw_text):
    """统一提示词解析入口（JSON 卡片 / 逐行 / `---` 分段 / ```json 围栏）。"""
    text = '' if raw_text is None else str(raw_text)
    if not text.strip():
        return []

    # 1) 代码围栏：提取 ```json ... ``` 内容后按 JSON/文本再解析
    fence_match = _CODE_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # 2) JSON 优先（数组或包装对象）
    stripped = text.strip()
    if stripped.startswith('[') or stripped.startswith('{'):
        try:
            data = json.loads(stripped)
            prompts = _prompts_from_json_data(data)
            if prompts:
                return prompts
        except json.JSONDecodeError:
            pass

    # 3) `---` 分段（分隔线切大段，段内逐行合并）
    lines = text.splitlines()
    if any(_SEPARATOR_LINE_RE.match(line) for line in lines):
        prompts = []
        current = []
        for line in lines:
            if _SEPARATOR_LINE_RE.match(line):
                if current:
                    prompts.append('\n'.join(current))
                    current = []
            else:
                current.append(line)
        if current:
            prompts.append('\n'.join(current))
        return [p for p in (_clean_prompt_line(p) for p in prompts) if p]

    # 4) 逐行（每行一条，含 bullet/序号清洗）
    return [p for p in (_clean_prompt_line(line) for line in lines) if p]


def _normalize_index(index, total):
    """index 校验：负数/越界抛 ValueError（文案 spec §5）。"""
    try:
        value = int(index)
    except (TypeError, ValueError):
        value = -1
    if value < 0:
        raise ValueError('index must be >= 0')
    if total <= 0:
        raise ValueError('TE MAN 批量提示词为空' if total == 0 else 'index out of range (0..0)')
    if value >= total:
        raise ValueError('index out of range (0..{})'.format(total - 1))
    return value


def _filename_stem(name):
    """取不带扩展名的文件名（输出用不带后缀的文件名；加载仍用完整 name）。"""
    text = '' if name is None else str(name)
    return text.rsplit('.', 1)[0] if '.' in text.rsplit('/', 1)[-1].rsplit('\\', 1)[-1] else text


def _parse_image_list(image_list, max_images):
    """图片名单解析：逐行 / JSON 数组；过滤空行与注释；限 max_images（0 不限制）。"""
    text = '' if image_list is None else str(image_list)
    names = []
    stripped = text.strip()
    if stripped.startswith('[') or stripped.startswith('{'):
        try:
            data = json.loads(stripped)
            if isinstance(data, list):
                names = [item if isinstance(item, str) else str(item.get('name') or '')
                         for item in data if isinstance(item, (str, dict))]
        except json.JSONDecodeError:
            names = []
    if not names:
        for line in text.splitlines():
            name = _clean_prompt_line(line)
            if name and not name.startswith('#'):
                names.append(name)
    seen, unique = set(), []
    for name in names:
        name = name.strip()
        if name and name not in seen:
            seen.add(name)
            unique.append(name)
    if max_images and isinstance(max_images, int) and max_images > 0:
        unique = unique[:max_images]
    return unique


class TEMANBatchEnhancedSettingsNode:
    """TE MAN 批量增强设置

    注册名: TE_MAN_Batch_Enhanced_Settings
    规格:   spec/TE_Batch_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Batch'
    FUNCTION = 'build_settings'
    DESCRIPTION = 'TE MAN 批量增强设置：连接到批量提示词/批量图片节点，控制批量执行范围、间隔、续跑编号和随机顺序。'
    RETURN_TYPES = ('TE_BATCH_ENHANCED_SETTINGS',)
    RETURN_NAMES = ('增强设置',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'执行间隔时间': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 86400.0, 'step': 0.1, 'tooltip': '每提交 1 个任务后等待的秒数。0 表示立即提交下一个。'}), '从指定编号继续': ('INT', {'default': 1, 'min': 1, 'max': 100000, 'step': 1, 'tooltip': '从第几个编号开始批量执行。1 表示从第一项开始。'}), '随机编号执行': ('BOOLEAN', {'default': False, 'tooltip': '开启后，在当前范围内随机顺序提交。'}), '执行范围': (('只执行当前线', '执行整个工作流'), {'default': '只执行当前线', 'tooltip': '默认只执行当前批量节点连接出去的流程；需要全工作流时改为执行整个工作流。'})}}
        # --8<-- 契约结束 --8<--

    def build_settings(self, **kwargs):
        """打包 4 个参数为 TE_BATCH_ENHANCED_SETTINGS。

        节点本身不做调度：实际消费主要在前端
        （te_man_batch_tools.js 沿输入 link 读 widget 值驱动批量入队）。
        下游如需在 Python 侧消费，按同一 dict 形状读取：
        {scope, start_number, random, interval}
        （键名为 spec §6.2 池中实锤串；selected/safe_index 无调用方证据，不实现）
        """
        values = self._extract(kwargs)
        settings = {
            'scope': values.get('执行范围') or BATCH_SCOPE_OPTIONS[0],
            'start_number': int(values.get('从指定编号继续') or 1),
            'random': bool(values.get('随机编号执行') or False),
            'interval': float(values.get('执行间隔时间') or 0.0),
        }
        # 原版返回字典被谁读取未确认（spec §3.3）；为兼容潜在的 Python 下游，
        # 同时以 NamedTuple 形式暴露（可按字段或索引访问，仍与 dict 同键）。
        return BatchEnhancedSettings(**settings)

    @staticmethod
    def _extract(kwargs):
        """输入经 kwargs 传入（含中文键）。"""
        return kwargs


class TEMANBatchImageNode:
    """TE MAN 批量图片

    注册名: TE_MAN_Batch_Image
    规格:   spec/TE_Batch_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Batch'
    FUNCTION = 'load_image'
    DESCRIPTION = 'TE MAN 批量图片：多图列表管理，可单项执行或批量执行。'
    RETURN_TYPES = ('IMAGE', 'STRING', 'STRING')
    RETURN_NAMES = ('输出图片', '图片文件名', '编号')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'image_list': ('STRING', {'multiline': True, 'default': '', 'hidden': True}), 'index': ('INT', {'default': 0, 'min': 0, 'max': 100000, 'step': 1}), 'max_images': ('INT', {'default': 0, 'min': 0, 'max': 100000, 'step': 1, 'tooltip': '0 表示不限制。'}), '最大任务数': ('INT', {'default': 100, 'min': 1, 'max': 10000, 'step': 1, 'tooltip': '批量执行时前端用于防止误提交过多任务。'})}, 'optional': {'增强设置': ('TE_BATCH_ENHANCED_SETTINGS', {'forceInput': True, 'tooltip': '可连接 TE MAN 批量增强设置，控制执行范围、间隔、续跑编号和随机顺序。'})}}
        # --8<-- 契约结束 --8<--

    def _load_one(self, name):
        """单张图片 → (IMAGE tensor, 完整文件名, stem)。多帧图（ImageSequence）
        拼接为 [frames, H, W, C] 张量（spec：torch/cat/dim 证据，简化实现）。"""
        import folder_paths
        import numpy as np
        import torch
        from PIL import Image, ImageOps, ImageSequence

        path = folder_paths.get_annotated_filepath(name)
        try:
            image = Image.open(path)
        except Exception as e:  # noqa: BLE001
            raise ValueError('图片读取失败：{}'.format(e)) from e
        with image:
            frames = []
            for frame in ImageSequence.Iterator(image):
                oriented = ImageOps.exif_transpose(frame)
                if oriented is None:
                    oriented = frame
                frames.append(np.array(oriented.convert('RGB')).astype(np.float32) / 255.0)
        try:
            tensor = torch.from_numpy(np.stack(frames, axis=0))
        except Exception as e:  # noqa: BLE001
            raise ValueError('图片读取失败：{}'.format(e)) from e
        return tensor, name, _filename_stem(name)

    def load_image(self, **kwargs):
        """按 index 从 image_list 取一项加载（实际批量循环由前端驱动）。"""
        image_list = kwargs.get('image_list') or ''
        index = kwargs.get('index') or 0
        max_images = kwargs.get('max_images') or 0

        names = _parse_image_list(image_list, max_images)
        if not names:
            raise ValueError('没有找到有效图片')
        safe_index = _normalize_index(index, len(names))
        tensor, full_name, stem = self._load_one(names[safe_index])
        return (tensor, full_name, str(safe_index))

    def IS_CHANGED(self, **kwargs):
        """缓存键：image_list + index 的 SHA256（列表内容变化才重新加载）。"""
        material = '{}\u0000{}'.format(kwargs.get('image_list') or '', kwargs.get('index') or 0)
        return hashlib.sha256(material.encode('utf-8')).hexdigest()

    def VALIDATE_INPUTS(self, **kwargs):
        """名单逐项校验存在性（folder_paths.exists_annotated_filepath/isfile）。"""
        import folder_paths

        image_list = kwargs.get('image_list') or ''
        max_images = kwargs.get('max_images') or 0
        for name in _parse_image_list(image_list, max_images):
            path = folder_paths.get_annotated_filepath(name)
            if not folder_paths.exists_annotated_filepath(name):
                return '图片不存在：{}'.format(name)
            import os

            if not os.path.isfile(path):
                return '图片不存在：{}'.format(name)
        return True


class TEMANBatchPromptNode:
    """TE MAN 批量提示词

    注册名: TE_MAN_Batch_Prompt
    规格:   spec/TE_Batch_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Batch'
    FUNCTION = 'get_prompt'
    DESCRIPTION = 'TE MAN 批量提示词：卡片式管理多条提示词，可单项执行或批量执行。'
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('输出提示词', '编号')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompts_json': ('STRING', {'default': '[]', 'hidden': True}), 'index': ('INT', {'default': 0, 'min': 0, 'max': 100000, 'step': 1}), '最大任务数': ('INT', {'default': 100, 'min': 1, 'max': 10000, 'step': 1, 'tooltip': '批量执行时前端用于防止误提交过多任务。'})}, 'optional': {'增强设置': ('TE_BATCH_ENHANCED_SETTINGS', {'forceInput': True, 'tooltip': '可连接 TE MAN 批量增强设置，控制执行范围、间隔、续跑编号和随机顺序。'}), 'prompts': ('STRING', {'forceInput': True, 'tooltip': '可选上游文本。支持一行一条、编号列表或 JSON 数组。'})}}
        # --8<-- 契约结束 --8<--

    def get_prompt(self, **kwargs):
        """按 index 从四种来源取第 N 条提示词。

        来源优先级（spec §3.1/§4.1）：
        prompts_json（hidden，前端卡片序列化）优先；为空/解析无果时
        回退 optional 输入口 prompts（JSON 数组 / 逐行 / --- 分段 / ```json 围栏）。
        实际批量循环由前端写入 index 重新排队驱动，本节点只按 index 取值。
        """
        prompts_json = kwargs.get('prompts_json') or ''
        upstream = kwargs.get('prompts') or ''
        index = kwargs.get('index') or 0

        prompts = []
        if str(prompts_json).strip() not in ('', '[]'):
            stripped = str(prompts_json).strip()
            if stripped.startswith('[') or stripped.startswith('{'):
                try:
                    prompts = _prompts_from_json_data(json.loads(stripped))
                except json.JSONDecodeError:
                    raise ValueError('prompts_json 不是有效 JSON') from None
            else:
                # 前端除 JSON 外也可能注入逐行/分段文本（getPromptItems 同源规则）
                prompts = parse_batch_prompts(stripped)
        if not prompts and str(upstream).strip():
            prompts = parse_batch_prompts(upstream)
        if not prompts:
            raise ValueError('TE MAN 批量提示词为空')

        safe_index = _normalize_index(index, len(prompts))
        return (prompts[safe_index], str(safe_index))

    def IS_CHANGED(self, **kwargs):
        """缓存键：prompts_json + prompts + index 的 SHA256。"""
        material = '{}\u0000{}\u0000{}'.format(
            kwargs.get('prompts_json') or '', kwargs.get('prompts') or '', kwargs.get('index') or 0)
        return hashlib.sha256(material.encode('utf-8')).hexdigest()

    def VALIDATE_INPUTS(self, **kwargs):
        """prompts_json 可解析性预校验（文案 spec §5）。"""
        prompts_json = str(kwargs.get('prompts_json') or '').strip()
        if prompts_json and prompts_json != '[]' and (prompts_json.startswith('[') or prompts_json.startswith('{')):
            try:
                json.loads(prompts_json)
            except json.JSONDecodeError:
                return 'prompts_json 不是有效 JSON'
        return True


# ---------------------------------------------------------------------------
# 增强设置载体：NamedTuple（同字段名 + dict 同键），供 Python 下游消费
# ---------------------------------------------------------------------------

try:
    from typing import NamedTuple

    class BatchEnhancedSettings(NamedTuple):
        """TE_BATCH_ENHANCED_SETTINGS 载体。

        spec §6.2 池中实锤键 scope/start_number/interval 与本字段一一对应；
        NamedTuple 同时支持下标访问与 ._asdict() 转 dict。
        """

        scope: str
        start_number: int
        random: bool
        interval: float

        @property
        def settings(self):
            return self._asdict()
except ImportError:  # pragma: no cover
    BatchEnhancedSettings = dict  # type: ignore[assignment,misc]


NODE_CLASS_MAPPINGS = {'TE_MAN_Batch_Enhanced_Settings': TEMANBatchEnhancedSettingsNode, 'TE_MAN_Batch_Image': TEMANBatchImageNode, 'TE_MAN_Batch_Prompt': TEMANBatchPromptNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_MAN_Batch_Enhanced_Settings': 'TE MAN 批量增强设置', 'TE_MAN_Batch_Image': 'TE MAN 批量图片', 'TE_MAN_Batch_Prompt': 'TE MAN 批量提示词'}
