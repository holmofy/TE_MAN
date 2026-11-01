# -*- coding: utf-8 -*-
"""te_man_open · TE_MAN_MOSS

本文件由 tools/codegen_skeletons.py 自动生成骨架，FUNCTION 方法已按
spec/TE_MAN_MOSS.md（含动态 introspection 回填节）实现。
INPUT_TYPES 为与原版逐字段一致的真机契约；禁止改动契约块与类属性。

模块顶层只依赖标准库；PIL / torch / llama_cpp / requests / comfy 系一律函数内惰性导入。
"""

import json
import math
import os
import re
import time

# =========================================================================
# 模块常量（值与 spec/TE_MAN_MOSS.md §7.2 真机 introspection 实锤逐字一致）
# =========================================================================

PRESET_CHOICES = ['竖版海报', '横版横幅', '方形', '自动排版(官方skill)', '只扩写(无框位)', '直出(不进行任何处理)']
AUTO_PRESET = '自动排版(官方skill)'
CAPTION_PRESET = '只扩写(无框位)'
RAW_PRESET = '直出(不进行任何处理)'
DEFAULT_API_BASE_URL = 'https://teynex.com'
DEFAULT_API_MODEL = 'deepseek-v4.1-flash'
DEFAULT_CONTEXT_LENGTH = 8192
LOCAL_MODELS = ['（请把模型放到 models/LLM）']
OBJECT_HINTS = ['hero', 'object', 'obj', 'image', 'photo', 'visual', 'scene', 'panel', 'illustration']
LANGUAGE_RULES = {'中文': 'Write "caption" and every "desc" in Chinese. The caption must be 500-800 Chinese characters and never shorter than 500. JSON keys, slot names and the values "text" / "obj" stay in English.', '英文': 'Write "caption" and every "desc" in English. The caption must be 300-500 words and never shorter than 300. JSON keys, slot names and the values "text" / "obj" stay in English.'}
REPLY_SHAPE = '{"caption": "<caption>", "slots": {"<slot name>": {"text": "<visible copy>", "desc": "<appearance>"}}}'
AUTO_REPLY_SHAPE = '{"caption": "<caption>", "slots": {"<slot name>": {"type": "text|obj", "bbox": [<xmin>, <ymin>, <xmax>, <ymax>], "text": "<visible copy>", "desc": "<appearance>"}}}'
AUTO_LAYOUT_RULES = 'Layout (you own the composition):\n- Every slot MUST contain "bbox": [xmin, ymin, xmax, ymax], four integers from 0 to 1000 that are proportions of the canvas, never pixel coordinates and never beyond 1000. 0 is the left or top edge, 1000 is the right or bottom edge. The first and third numbers are the left and right edge, the second and fourth are the top and bottom edge. xmin < xmax and ymin < ymax. A slot without it is discarded.\n- Decide the hierarchy yourself: one dominant element, the reading order of the rest, and how much air the picture needs. Keep at least 40 units of clear margin inside the canvas for every text slot.\n- Size each text box to the copy it holds: a short title needs a wide box with tall glyphs, a longer line or a paragraph needs a box tall enough for several lines. Two text boxes must never overlap.\n- Use text slots only when the request needs copy laid over the picture. A portrait, landscape, street scene, still life or product shot needs none: every slot is then "obj", and text inside the scene (shop signs, labels) is described inside its obj desc.\n- Use one box per independent placement and group the parts that always move together. Natural overlap between boxes is allowed.\n- A box is a placement annotation, not a visible frame, border, panel or sticker. Never restate coordinates or box positions in "caption" or "desc".\n- Example slot: {"type": "text", "bbox": [40, 40, 960, 150], "text": "...", "desc": "..."}. The numbers only show the format; choose your own.'
CAPTION_RULES = '"caption" describes the finished picture as it looks. Write it as flowing natural language, never a comma-separated tag list, in two to four paragraphs ordered by space or by the viewer\'s eye, and never shorter than the length the Language rule asks for. Open with the medium and the subject, never with a verb. Build it from these facets, and cover a facet only when the scene has content for it: subject (appearance, age range, build, hairstyle, each garment and its material, accessories, skin or surface texture); action (body orientation, limb positions, weight distribution, what the hands are doing, gaze, expression, all holding in a single frame); space (foreground, midground and background, relative positions, occlusion, distances, what appears at the frame edges); setting (architecture, furniture, props, signs of use, and the details that place the scene in a time and place); framing (shot size, camera height, viewing angle, perspective strength, where the subject sits in the frame); light (direction and height of the key light, hardness, colour temperature, practical sources, and how the light falls on skin, fabric, glass, metal and wet ground); tone (palette, contrast, grain, medium, texture detail, atmosphere). Every sentence must add visible detail that was not stated before; never pad, repeat, or stack quality words such as "masterpiece", "8k" or "best quality". If the caption falls short of the required length, add the missing visible detail from a facet you skipped instead of restating what you already wrote. Never mention boxes, coordinates, slots, JSON, pixel sizes or aspect ratios. Never describe the picture as an edit: no "replace", "remove", "keep", "preserve", "the original" or "same as".'
CAPTION_SYSTEM_PROMPT = 'You are a prompt writer for an image generation model.\n\nThe user sends one short request, often in Chinese. Expand it into a complete description of the finished image. This image has no overlaid copy and no layout: it is a plain picture.\n\nReply with this exact JSON shape and nothing else:\n{"caption": "<caption>"}\n\nLanguage:\n- {language_rules}\n\n{caption_rules}\n\n- Do not output "slots", "items", "bbox" or element descriptions.\n- Text that exists inside the scene — shop signs, plaques, banners, product labels, screen content — is part of the picture: describe it in the caption, never as copy to overlay.\n- Respect the user\'s subject, count, style and exclusions. Do not invent brands, real people, prices or dates the user did not give.\n- Describe only what is visible: no tool steps and no generation parameters.\n- Output JSON only. No markdown fences, no preface, no explanation.\n'
SYSTEM_PROMPT = 'You are a layout planner for an image generation model that consumes a JSON layout prompt.\n\nThe user sends one short request, often in Chinese. Turn it into the finished image it describes: a designed poster when the request is one, a complete frame with no added type when it is a portrait, landscape, street scene or still life.\n\nReply with this exact JSON shape and nothing else:\n{reply_shape}\n\nSlot names you may use: {slot_names}\n{slot_types_line}\n{layout_rules}\nLanguage:\n- {language_rules}\n- Visible copy stays in the user\'s original language and punctuation.\n\n{caption_rules} Never describe where the copy or the empty space for type sits: placement comes from the boxes.\n\n"desc" describes that element only and never repeats, quotes or paraphrases the copy. A text slot gets one sentence, at most 30 Chinese characters or 20 English words: typeface category and weight, colour, size relative to its box, alignment, line count, letter spacing, and the surface it sits on (no panel, a semi-transparent panel, a drop shadow, a stroke). An obj slot gets at most two sentences: subject and clothing detail, materials and surface texture, pose or orientation, what it overlaps, and how the light falls on it. Every word must describe something a camera could see. Never write purpose, mood, effect, atmosphere or evaluation: no "ensure readability", "conveys", "echoes the design", "supports the subject", "provides a perfect foil", "works as a call to action" or similar. If a sentence cannot be photographed, delete it. Do not state where the element sits, how large it is or how much space it takes; its box already defines that.\n\n- A slot typed "text" MUST include "text". A slot typed "obj" MUST NOT include "text".\n- Keep visible copy exactly as the user wrote it, in its original language and punctuation. Never translate, shorten or duplicate it.\n- If a text slot needs copy and the user gave none, write short, real, topic-appropriate copy in the user\'s language. Never write placeholders such as "headline here", "your text", "some text" or "标题".\n- Text that exists inside the scene is part of the picture, not layout copy: shop signs, street plaques, banners, product labels, screen content, book covers, graffiti. Describe that text inside the desc of the object that carries it, and never turn it into a text slot, a "text" field or a separate visible copy.\n- Respect the user\'s subject, count, style and exclusions. Do not invent brands, real people, prices or dates the user did not give.\n- Describe only what is visible: no tool steps, no generation parameters and no coordinate arithmetic.\n- Output JSON only. No markdown fences, no preface, no explanation.\n'
LAYOUT_PRESETS = {'竖版海报': [['title', 'text', [0.07, 0.055, 0.86, 0.13]], ['subtitle', 'text', [0.07, 0.205, 0.72, 0.055]], ['hero', 'obj', [0.05, 0.285, 0.9, 0.465]], ['detail', 'text', [0.07, 0.775, 0.6, 0.075]], ['footer', 'text', [0.07, 0.885, 0.45, 0.05]]], '横版横幅': [['title', 'text', [0.06, 0.14, 0.46, 0.3]], ['subtitle', 'text', [0.06, 0.46, 0.4, 0.1]], ['hero', 'obj', [0.42, 0.06, 0.52, 0.88]], ['footer', 'text', [0.06, 0.82, 0.3, 0.06]]], '方形': [['title', 'text', [0.08, 0.08, 0.84, 0.15]], ['hero', 'obj', [0.05, 0.26, 0.9, 0.5]], ['caption', 'text', [0.08, 0.8, 0.84, 0.09]]], '自动排版(官方skill)': None}

# —— spec 内省常量表未实锤、按 §3.1/§6.2 摘录等价重建的部分 ——
AUTO_SLOT_NAMES = '3 to 6 short role names you choose, in visual order, such as title, subtitle, hero, caption, footer'
AUTO_SLOT_TYPES_LINE = 'Choose each slot\'s "type": text for visible copy, obj for imagery.'

# 预览图配色（与 web/js/te_man_moss_box.js 恒常量一致）
COLOR_TEXT = '#78c896'
COLOR_OBJ = '#e0966a'
BORDER = '#3a3a42'
PREVIEW_BG = '#1c1c20'

_FONT_CANDIDATES = (
    r'C:\Windows\Fonts\msyhbd.ttc',
    r'C:\Windows\Fonts\msyh.ttc',
    r'C:\Windows\Fonts\simhei.ttf',
    r'C:\Windows\Fonts\arial.ttf',
    '/System/Library/Fonts/PingFang.ttc',
    '/System/Library/Fonts/STHeiti Light.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
)

_FENCE_START_RE = re.compile(r'^```[A-Za-z]*\s*')
_FENCE_END_RE = re.compile(r'\s*```\s*$')
_TRAILING_COMMA_RE = re.compile(r',\s*([}\]])')

#: 元素框最小跨度（0-1000 标度），过窄时由 _grow_span 围绕中心撑开
MIN_ELEMENT_SPAN = 12


# ==================== 小工具 ====================

def _fill(template, **values):
    """按占位符逐个替换（模板内含 JSON 花括号，不能用 str.format）。"""
    out = str(template or '')
    for key, value in values.items():
        out = out.replace('{' + key + '}', str(value))
    return out


def _norm_number(value):
    """数值规范：可转有限浮点则返回，否则 None。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _grow_span(low, high, minimum=MIN_ELEMENT_SPAN):
    """把过窄的区间围绕中心撑到 minimum，再压回 0-1000。"""
    low = int(round(low))
    high = int(round(high))
    if high - low < minimum:
        center = (low + high) // 2
        low = center - minimum // 2
        high = low + minimum
    low = max(0, min(1000, low))
    high = max(0, min(1000, high))
    if high - low < minimum:
        low = max(0, min(1000 - minimum, high - minimum))
        high = low + minimum
    return low, high


def _to_1000(ratio):
    """比例框 (x, y, w, h) -> ComfyUI 元素 bbox [ymin, xmin, ymax, xmax]，0-1000 整数。"""
    x = _norm_number(ratio[0]) or 0.0
    y = _norm_number(ratio[1]) or 0.0
    w = _norm_number(ratio[2]) or 0.0
    h = _norm_number(ratio[3]) or 0.0
    xmin, xmax = _grow_span(x * 1000.0, (x + w) * 1000.0)
    ymin, ymax = _grow_span(y * 1000.0, (y + h) * 1000.0)
    return [ymin, xmin, ymax, xmax]


def _slot_type(role, declared=None):
    """推断槽位类型 text/obj（declared 为声明类型，role 按 OBJECT_HINTS 判定）。"""
    declared = str(declared or '').strip().lower()
    if declared in ('text', 'obj'):
        return declared
    label = str(role or '').lower()
    if any(str(hint) in label for hint in OBJECT_HINTS):
        return 'obj'
    return 'text'


def _slot_description(slot):
    """槽位描述文本：优先 desc，其次 caption。"""
    return next((str(slot[key]).strip() for key in ('desc', 'caption')
                 if isinstance(slot, dict) and slot.get(key)), '')


def _payload_bbox(slot, order='yxyx'):
    """取槽位里的框：兼容 bbox/box、四元数组、ymin.. 字典和 x/y/width/height 字典。

    返回规范化的 (xmin, ymin, xmax, ymax) 浮点 0-1000；不可用返回 None。
    四元数组按 order 解读：元素存储为 [ymin, xmin, ymax, xmax]（yxyx），
    模型侧按 AUTO_LAYOUT_RULES 为 [xmin, ymin, xmax, ymax]（xyxy）。
    """
    if not isinstance(slot, dict):
        return None
    raw = slot.get('bbox')
    if raw is None:
        raw = slot.get('box')
    if isinstance(raw, (list, tuple)) and len(raw) == 4:
        values = [_norm_number(v) for v in raw]
        if any(v is None for v in values):
            return None
        a, b, c, d = values
        if order == 'xyxy':
            xmin, ymin, xmax, ymax = a, b, c, d
        else:
            ymin, xmin, ymax, xmax = a, b, c, d
    elif isinstance(raw, dict):
        if all(key in raw for key in ('ymin', 'xmin', 'ymax', 'xmax')):
            ymin = _norm_number(raw.get('ymin'))
            xmin = _norm_number(raw.get('xmin'))
            ymax = _norm_number(raw.get('ymax'))
            xmax = _norm_number(raw.get('xmax'))
            if None in (ymin, xmin, ymax, xmax):
                return None
        elif all(key in raw for key in ('x', 'y', 'width', 'height')):
            x = _norm_number(raw.get('x'))
            y = _norm_number(raw.get('y'))
            w = _norm_number(raw.get('width'))
            h = _norm_number(raw.get('height'))
            if None in (x, y, w, h):
                return None
            xmin, ymin, xmax, ymax = x, y, x + w, y + h
        else:
            return None
    else:
        return None
    if max(xmin, ymin, xmax, ymax) <= 1.0:
        # 0-1 比例输入按 0-1000 换算
        xmin, ymin, xmax, ymax = xmin * 1000.0, ymin * 1000.0, xmax * 1000.0, ymax * 1000.0
    if xmin > xmax:
        xmin, xmax = xmax, xmin
    if ymin > ymax:
        ymin, ymax = ymax, ymin
    if xmax - xmin < 1.0 or ymax - ymin < 1.0:
        return None
    return (xmin, ymin, xmax, ymax)


def _auto_bbox(slots):
    """模型给的 bbox（0-1000，xyxy）-> 0-1000 的 yxyx 整数框；不可用时返回 None。"""
    boxes = {}
    for name, slot in (slots or {}).items():
        label = str(name)
        if not isinstance(slot, dict):
            print('TE MAN MOSS: 自动排版的槽位 %s 不是对象: %s' % (label, slot))
            return None
        bbox = _payload_bbox(slot, order='xyxy')
        if bbox is None:
            print('TE MAN MOSS: 自动排版的槽位 %s 框不可用: %s' % (label, slot.get('bbox')))
            return None
        xmin, ymin, xmax, ymax = bbox
        if any(v < 0.0 or v > 1000.0 for v in (xmin, ymin, xmax, ymax)):
            print('TE MAN MOSS: 自动排版有坐标超出 0-1000，按比例截断: %s' % label)
        xmin = max(0.0, min(1000.0, xmin))
        xmax = max(0.0, min(1000.0, xmax))
        ymin = max(0.0, min(1000.0, ymin))
        ymax = max(0.0, min(1000.0, ymax))
        if not (xmin < xmax and ymin < ymax):
            print('TE MAN MOSS: 自动排版的槽位 %s 框不可用: %s' % (label, slot.get('bbox')))
            return None
        boxes[label] = [int(round(ymin)), int(round(xmin)), int(round(ymax)), int(round(xmax))]
    return boxes or None


def _auto_elements(slots, boxes):
    """自动排版：直接用模型给的框；任一槽位的框不可用就整体返回 None。"""
    if not boxes:
        return None
    elements = []
    for name, bbox in boxes.items():
        slot = (slots or {}).get(name)
        slot = slot if isinstance(slot, dict) else {}
        typ = _slot_type(name, slot.get('type'))
        elements.append({
            'role': str(name),
            'type': typ,
            'text': str(slot.get('text') or '') if typ == 'text' else '',
            'desc': _slot_description(slot),
            'bbox': list(bbox),
        })
    return elements or None


def _split_elements(slots):
    """自动排版的兜底：按模型给的顺序纵向均分，留出边距。"""
    slots = slots if isinstance(slots, dict) else {}
    names = [str(name) for name in slots]
    count = max(1, len(names))
    margin = 40
    usable = 1000 - margin * 2
    step = usable / float(count)
    elements = []
    for index, name in enumerate(names):
        slot = slots.get(name)
        slot = slot if isinstance(slot, dict) else {}
        typ = _slot_type(name, slot.get('type'))
        ymin, ymax = _grow_span(margin + index * step, margin + (index + 1) * step)
        elements.append({
            'role': name,
            'type': typ,
            'text': str(slot.get('text') or '') if typ == 'text' else '',
            'desc': _slot_description(slot),
            'bbox': [ymin, margin, ymax, 1000 - margin],
        })
    return elements


def _preset_elements(slots, skeleton):
    """把 slots 里的内容落到具体框位：预设骨架（bbox 由骨架补）。"""
    elements = []
    for role, typ, ratio in skeleton:
        slot = (slots or {}).get(role)
        slot = slot if isinstance(slot, dict) else {}
        elements.append({
            'role': str(role),
            'type': str(typ),
            'text': str(slot.get('text') or '') if typ == 'text' else '',
            'desc': _slot_description(slot),
            'bbox': _to_1000(ratio),
        })
    return elements


def _preset_layout_rules(skeleton):
    """预设版式的 layout 规则（组合固定，模型只负责填内容）。

    原文常量未在内省常量表中实锤，按 §3.1/§6.2 语义等价重建。
    """
    roles = ', '.join('"%s" (%s)' % (row[0], row[1]) for row in skeleton)
    return (
        'Layout (the composition is already decided):\n'
        '- The slots %s are listed in visual order; each keeps its fixed type and fixed box on the canvas.\n'
        '- Fill every listed slot: a text slot MUST include "text" plus "desc"; an obj slot MUST include only "desc".\n'
        '- Fit the copy to its box: a wide, short box wants one line of large copy, a taller box wants several lines.\n'
        '- Two text boxes must never carry the same copy.\n'
        '- Do not invent extra slots and never mention boxes or coordinates anywhere.' % roles
    )


def _extract_json(text):
    """尽力从模型输出里抠出 JSON（对象或数组），抠不出来返回 None。"""
    body = str(text or '').strip()
    if not body:
        return None
    body = _FENCE_START_RE.sub('', body)
    body = _FENCE_END_RE.sub('', body)
    body = _TRAILING_COMMA_RE.sub(r'\1', body)
    decoder = json.JSONDecoder()
    for index, char in enumerate(body):
        if char in '{[':
            try:
                value, _end = decoder.raw_decode(body, index)
                return value
            except ValueError:
                continue
    return None


def _plain_caption(text):
    """只扩写时模型直接回正文（不是 JSON）就把正文当 caption；截断的 JSON 不算。"""
    body = str(text or '').strip()
    if not body or body[0] in '{[':
        return None
    return body


def _incoming_text(value):
    """任意输入归一为文本（STRING forceInput 未连接时缺省）。"""
    if value is None:
        return ''
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode('utf-8', 'replace')
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:  # noqa: BLE001
        return str(value)


def _element_bbox(item):
    """元素框 -> 0-1000 的 [ymin, xmin, ymax, xmax] 整数；不可用返回 None。"""
    bbox = _payload_bbox(item, order='yxyx')
    if bbox is None:
        return None
    xmin, ymin, xmax, ymax = bbox
    xmin = int(round(max(0.0, min(1000.0, xmin))))
    xmax = int(round(max(0.0, min(1000.0, xmax))))
    ymin = int(round(max(0.0, min(1000.0, ymin))))
    ymax = int(round(max(0.0, min(1000.0, ymax))))
    if not (ymin < ymax and xmin < xmax):
        return None
    return [ymin, xmin, ymax, xmax]


def _normalize_elements(data):
    """把任意来源的框数据整理成 [{role, type, text, desc, bbox}]，bbox 为 0-1000。"""
    text = _incoming_text(data)
    items = None
    if text.strip():
        try:
            parsed = json.loads(text)
        except Exception:  # noqa: BLE001
            parsed = None
        if isinstance(parsed, dict):
            for key in ('elements', 'items', 'boxes'):
                if isinstance(parsed.get(key), list):
                    parsed = parsed[key]
                    break
        if isinstance(parsed, list):
            items = parsed
    if items is None and isinstance(data, (list, dict)):
        source = data
        if isinstance(source, dict):
            for key in ('elements', 'items', 'boxes'):
                if isinstance(source.get(key), list):
                    source = source[key]
                    break
        if isinstance(source, list):
            items = source
    elements = []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        bbox = _element_bbox(item)
        if bbox is None:
            continue
        typ = _slot_type(item.get('role'), item.get('type'))
        element = {'type': typ, 'bbox': bbox}
        role = str(item.get('role') or '').strip()
        if role:
            element['role'] = role
        if typ == 'text':
            element['text'] = str(item.get('text') or '')
        element['desc'] = str(item.get('desc') or item.get('caption') or '')
        palette = item.get('palette') or item.get('color_palette')
        if isinstance(palette, (list, tuple)) and palette:
            element['palette'] = [str(color) for color in palette][:5]
        elements.append(element)
    return elements


def _to_centered_bbox(bbox, width, height):
    """0-1000 元素 bbox -> MOSS 模型侧居中 yxyx 整数坐标。

    与 comfy_extras/nodes_moss_image.py 的 MOSSImageLayoutPrompt 完全一致：
    先换回像素，小数边向外取整，再减去画布中心。
    """
    try:
        import comfy_extras.nodes_moss_image  # noqa: F401  对照实现可用性探测
    except Exception:  # noqa: BLE001
        pass
    ymin, xmin, ymax, xmax = bbox
    width = int(width)
    height = int(height)
    return [
        math.floor(round(ymin * height / 1000.0, 9)) - height // 2,
        math.floor(round(xmin * width / 1000.0, 9)) - width // 2,
        math.ceil(round(ymax * height / 1000.0, 9)) - height // 2,
        math.ceil(round(xmax * width / 1000.0, 9)) - width // 2,
    ]


def _build_layout_prompt(elements, caption, width, height):
    """编译成 MOSS-Image 的 layout 提示词（单行紧凑 JSON）。"""
    items = []
    for element in elements:
        label = 'text' if element.get('type') == 'text' else 'object'
        item = {'label': label, 'caption': str(element.get('desc') or '')}
        if label == 'text':
            item['text'] = str(element.get('text') or '')
        palette = element.get('palette')
        if isinstance(palette, (list, tuple)) and palette:
            item['palette'] = [str(color) for color in palette][:5]
        item['bbox'] = _to_centered_bbox(element['bbox'], width, height)
        items.append(item)
    layout = {
        'summary': {'caption': str(caption or '').strip()},
        'items': items,
        'bbox_coord_space': 'abs_centralized',
        'bbox_format': 'yxyx',
    }
    return json.dumps(layout, ensure_ascii=False, separators=(',', ':'))


# ==================== 三后端文本生成 ====================

def _resolve_api_key(api_key):
    """API key 解析，留空时读取 TE MAN 的 config.ini。"""
    key = str(api_key or '').strip()
    if key:
        return key
    try:
        from te_man_open.shared.config_manager import CONFIG_MANAGER
    except Exception:  # noqa: BLE001
        try:
            from ..shared.config_manager import CONFIG_MANAGER  # type: ignore[no-redef]
        except Exception:  # noqa: BLE001
            return ''
    loader = getattr(CONFIG_MANAGER, 'load_api_key', None)
    if callable(loader):
        try:
            return str(loader() or '').strip()
        except Exception:  # noqa: BLE001
            return ''
    return ''


def _llm_search_dirs():
    dirs = []
    try:
        import folder_paths
        dirs.extend(folder_paths.get_folder_paths('LLM'))
    except Exception:  # noqa: BLE001
        pass
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.dirname(os.path.dirname(here))
    for candidate in (os.path.join(repo, 'models', 'LLM'),
                      os.path.join(repo, 'ComfyUI', 'models', 'LLM'),
                      os.path.join(here, 'models', 'LLM')):
        if candidate not in dirs:
            dirs.append(candidate)
    return [d for d in dirs if isinstance(d, str) and d]


def _llm_file_choices():
    """枚举 models/LLM 下模型文件。"""
    names = []
    for directory in _llm_search_dirs():
        try:
            if not os.path.isdir(directory):
                continue
            for name in sorted(os.listdir(directory)):
                if name.lower().endswith(('.gguf', '.bin')):
                    names.append(name)
        except Exception:  # noqa: BLE001
            continue
    return names


def _resolve_local_model(name):
    """把「本地模型」widget 值解析成 models/LLM 下的模型文件路径。"""
    target = str(name or '').strip()
    directories = _llm_search_dirs()
    if target:
        for directory in directories:
            candidate = os.path.join(directory, target)
            if os.path.isfile(candidate):
                return candidate
    for choice in _llm_file_choices():
        for directory in directories:
            candidate = os.path.join(directory, choice)
            if os.path.isfile(candidate):
                return candidate
    raise RuntimeError('未找到本地模型，请把模型放到 models/LLM')


def _request_clip(clip, system_prompt, user_prompt, max_length, seed):
    """CLIP 后端：调 CLIPLoader 里那个文本模型。采样参数全部用 clip.generate 自己的默认值。"""
    if clip is None or not callable(getattr(clip, 'generate', None)):
        raise RuntimeError('增强方式为 CLIP 时需要连接 clip 输入')
    full_prompt = system_prompt + '\n\n' + user_prompt
    generate = clip.generate
    try:
        result = generate(full_prompt, max_length=int(max_length), seed=int(seed))
    except TypeError:
        result = generate(full_prompt)
    if isinstance(result, (list, tuple)):
        result = result[0] if result else ''
    if isinstance(result, dict):
        result = result.get('text') or result.get('output_text') or ''
    return str(result or '').strip()


def _request_local(model_path, system_prompt, user_prompt, max_length, seed, unload=True):
    """本地 llama.cpp 请求（models/LLM 下的 gguf 模型）。"""
    try:
        from llama_cpp import Llama
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError('未加载 Qwen 节点模块，无法使用本地 llama.cpp') from exc
    load_kwargs = {'model_path': model_path, 'n_ctx': DEFAULT_CONTEXT_LENGTH,
                   'n_gpu_layers': -1, 'verbose': False}
    try:
        llm = Llama(seed=int(seed), **load_kwargs)
    except TypeError:
        llm = Llama(**load_kwargs)
    try:
        result = llm.create_chat_completion(
            messages=[{'role': 'system', 'content': system_prompt},
                      {'role': 'user', 'content': user_prompt}],
            max_tokens=int(max_length), seed=int(seed))
        choices = result.get('choices') or [{}]
        message = (choices[0] or {}).get('message') or {}
        return str(message.get('content') or '').strip()
    finally:
        if unload:
            # 生成完就释放显存，避免和后面的 MOSS 出图抢显存
            del llm
            import gc
            gc.collect()
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:  # noqa: BLE001
                pass


def _post_json(url, payload, api_key, timeout=600):
    body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    headers = {'Content-Type': 'application/json'}
    if api_key:
        headers['Authorization'] = 'Bearer ' + api_key
    try:
        import requests
    except Exception:  # noqa: BLE001
        requests = None
    if requests is not None:
        response = requests.post(url, data=body, headers=headers, timeout=timeout)
        if response.status_code >= 400:
            raise RuntimeError('HTTP %s: %s' % (response.status_code, str(response.text)[:200]))
        try:
            return response.json()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError('响应不是 JSON: %s' % exc) from exc
    from urllib.request import Request, urlopen
    request = Request(url, data=body, headers=headers)
    with urlopen(request, timeout=timeout):  # noqa: S310
        return json.loads(response.read().decode('utf-8'))


def _responses_output_text(data):
    """从 OpenAI 兼容 /responses（或 chat.completions 兼容形态）回包里取正文文本。"""
    if not isinstance(data, dict):
        return ''
    text = data.get('output_text') or data.get('text')
    if isinstance(text, str) and text.strip():
        return text.strip()
    parts = []
    for item in data.get('output') or []:
        if not isinstance(item, dict):
            continue
        for chunk in item.get('content') or []:
            if isinstance(chunk, dict) and chunk.get('text'):
                parts.append(str(chunk['text']))
            elif isinstance(chunk, str):
                parts.append(chunk)
    if not parts:
        for choice in data.get('choices') or []:
            message = (choice or {}).get('message') or {}
            if message.get('content'):
                parts.append(str(message['content']))
    return ''.join(parts).strip()


def _request_api(api_base_url, api_model, api_key, system_prompt, user_prompt):
    """OpenAI 兼容 /responses 请求（API 模式不发送 max_length 限制）。"""
    base = str(api_base_url or DEFAULT_API_BASE_URL).strip().rstrip('/')
    if not base:
        raise RuntimeError('未配置有效的 API URL')
    if base.endswith('/responses'):
        url = base
    elif base.endswith('/v1'):
        url = base + '/responses'
    else:
        url = base + '/v1/responses'
    payload = {
        'model': str(api_model or DEFAULT_API_MODEL),
        'input': [{'role': 'system', 'content': system_prompt},
                  {'role': 'user', 'content': user_prompt}],
    }
    data = _post_json(url, payload, api_key)
    text = _responses_output_text(data)
    if not text:
        raise RuntimeError('API 未返回可用文本')
    return text


def _generate_text(system_prompt, user_prompt, max_length, *, backend='CLIP', clip=None,
                   local_model='', seed=0, unload=True,
                   api_base_url=DEFAULT_API_BASE_URL, api_model=DEFAULT_API_MODEL, api_key=''):
    """三后端统一入口（system_prompt / user_prompt / max_length）。"""
    backend = str(backend or 'CLIP')
    if backend == 'CLIP':
        return _request_clip(clip, system_prompt, user_prompt, max_length, seed)
    if backend == '本地 llama.cpp':
        return _request_local(_resolve_local_model(local_model), system_prompt, user_prompt,
                              max_length, seed, unload=unload)
    if backend == 'API':
        return _request_api(api_base_url, api_model, _resolve_api_key(api_key),
                            system_prompt, user_prompt)
    raise RuntimeError('未知增强方式: %s' % backend)


# ==================== 版式预览图 ====================

def _fonts(size=12):
    """按优先级找一个能显示中文的字体，找不到就退回 PIL 内置字体。"""
    try:
        from PIL import ImageFont
    except Exception:  # noqa: BLE001
        return None
    for path in _FONT_CANDIDATES:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, int(size))
            except Exception:  # noqa: BLE001
                continue
    try:
        return ImageFont.load_default()
    except Exception:  # noqa: BLE001
        return None


def _wrap(draw, text, max_width, font, max_lines=6):
    """文本换行（预览绘制用，逐字符按 textlength 累加）。"""
    lines = []
    current = ''
    for char in str(text or ''):
        if char == '\n':
            lines.append(current)
            current = ''
            continue
        if current and draw.textlength(current + char, font=font) > max_width:
            lines.append(current)
            current = char
        else:
            current += char
        if len(lines) >= max_lines:
            current = ''
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if lines and len(lines) >= max_lines and current:
        lines[max_lines - 1] += '…'
    return lines[:max_lines] if lines else ['']


def _tag_ink(color):
    """框编号标签前景色：亮底用深字，深底用白字。"""
    text = str(color or '').lstrip('#')
    try:
        value = int(text[:6], 16)
    except (ValueError, TypeError):
        return '#ffffff'
    red = (value >> 16) & 0xFF
    green = (value >> 8) & 0xFF
    blue = value & 0xFF
    return '#141416' if 0.299 * red + 0.587 * green + 0.114 * blue > 150 else '#ffffff'


def _render_preview(elements, width, height):
    """画一张框位预览图。旧前端也能当普通图片看。"""
    try:
        from PIL import Image, ImageDraw
    except Exception:  # noqa: BLE001
        return None
    canvas_w = max(64, int(width))
    canvas_h = max(64, int(height))
    image = Image.new('RGBA', (canvas_w, canvas_h), PREVIEW_BG)
    draw = ImageDraw.Draw(image)
    font = _fonts(max(10, min(20, canvas_w // 60)))
    for index, element in enumerate(elements):
        bbox = element.get('bbox') or [0, 0, 0, 0]
        ymin, xmin, ymax, xmax = bbox
        x0 = xmin / 1000.0 * canvas_w
        y0 = ymin / 1000.0 * canvas_h
        x1 = xmax / 1000.0 * canvas_w
        y1 = ymax / 1000.0 * canvas_h
        color = COLOR_TEXT if element.get('type') == 'text' else COLOR_OBJ
        draw.rectangle([x0, y0, x1, y1], fill=color + '22', outline=BORDER, width=2)
        palette = element.get('palette') or []
        chip_fill = str(palette[0]) if palette else color
        chip_label = '%02d' % (index + 1)
        chip_width = max(16.0, draw.textlength(chip_label, font=font) + 8.0)
        chip_height = 15
        draw.rectangle([x0, y0, x0 + chip_width, y0 + chip_height], fill=chip_fill)
        draw.text((x0 + 4, y0 + 1), chip_label, fill=_tag_ink(chip_fill), font=font)
        if element.get('type') == 'text':
            body = '“%s”' % (element.get('text') or '')
            if element.get('desc'):
                body += ' — ' + str(element['desc'])
        else:
            body = str(element.get('desc') or '')
        if body and (y1 - y0) > 26 and (x1 - x0) > 30:
            max_lines = max(1, int((y1 - y0 - 22) // 14))
            for line_index, line in enumerate(_wrap(draw, body, x1 - x0 - 8, font, max_lines=max_lines)):
                draw.text((x0 + 5, y0 + 20 + line_index * 14), line, fill='#d8d8de', font=font)
    return image.convert('RGB')


def _tensor_from_image(image):
    """PIL 图 -> ComfyUI IMAGE 张量 (1, H, W, 3)，torch 不可用时返回 None。"""
    if image is None:
        return None
    try:
        import numpy as np
        import torch
    except Exception:  # noqa: BLE001
        return None
    array = np.asarray(image.convert('RGB'), dtype=np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


def _with_preview(image):
    """把预览图挂到节点自身，这样不用再接 PreviewImage 也能直接看见框。

    尽力保存到 output/TE MAN MOSS/ 下并作为 ui.images 返回；失败仅告警不阻塞。
    """
    if image is None:
        return []
    try:
        import folder_paths
        output_dir = folder_paths.get_output_directory()
    except Exception:  # noqa: BLE001
        return []
    try:
        subfolder = 'TE MAN MOSS'
        target = os.path.join(output_dir, subfolder)
        os.makedirs(target, exist_ok=True)
        filename = 'TE_MAN_MOSS_%s.png' % format(int(time.time() * 1000) % 100000000, '08d')
        image.save(os.path.join(target, filename))
        return [{'filename': filename, 'subfolder': subfolder, 'type': 'output'}]
    except Exception as exc:  # noqa: BLE001
        print('TE MAN MOSS 预览图保存失败: %s' % exc)
        return []


class TEMossBoxNode:
    """TE MAN MOSS 增强边界框/增强提示词

    注册名: TE_image_pro_moss_box
    规格:   spec/TE_MAN_MOSS.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/MOSS'
    FUNCTION = 'compile'
    OUTPUT_NODE = True
    DESCRIPTION = '画布拖拽画框，选中后可编辑类型、文字、描述、调色板。可直接接「TE MAN MOSS 增强版式规划/增强提示词」的元素列表输出。'
    RETURN_TYPES = ('STRING', 'STRING', 'IMAGE')
    RETURN_NAMES = ('完整版式提示词', '元素列表', '版式预览图')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'整图描述': ('STRING', {'multiline': True, 'default': '', 'tooltip': '不接「上游描述」时使用的整图描述，编译后成为 summary.caption。前端不显示这个输入框。'}), 'boxes': ('STRING', {'multiline': True, 'default': '[\n {\n  "role": "title",\n  "type": "text",\n  "text": "夏日音乐节",\n  "desc": "enormous cream serif capitals, centred",\n  "bbox": [\n   55,\n   70,\n   185,\n   930\n  ]\n },\n {\n  "role": "hero",\n  "type": "obj",\n  "desc": "stage truss silhouettes, crowd, warm haze",\n  "bbox": [\n   285,\n   50,\n   750,\n   950\n  ]\n }\n]', 'tooltip': '框列表 JSON，由画布自动维护。bbox 为 [ymin, xmin, ymax, xmax]，0-1000 整数，顺序与 ComfyUI 自带边界框一致。'}), 'width': ('INT', {'default': 1024, 'min': 256, 'max': 4096, 'step': 16}), 'height': ('INT', {'default': 1536, 'min': 256, 'max': 4096, 'step': 16})}, 'optional': {'上游元素列表': ('STRING', {'forceInput': True, 'tooltip': '接「TE MAN MOSS 增强版式规划/增强提示词」的元素列表。连接后首次运行会把框载入画布，之后以画布编辑为准；上游内容变了会重新载入。'}), '上游描述': ('STRING', {'forceInput': True, 'tooltip': '可接上游的整图描述。连接后优先使用它。'}), 'last_incoming': ('STRING', {'multiline': True, 'default': '', 'tooltip': '内部状态：上一次已经载入画布的上游元素列表，由节点自己维护。'})}}
        # --8<-- 契约结束 --8<--

    def compile(self, **kwargs):
        """把画布框位（或首次运行时上游载入的元素列表）编译成最终 MOSS layout 提示词。

        - 连接「上游元素列表」后首次运行会把框载入画布（经 ui.te_moss_apply 通知前端），
          之后以画布编辑为准；上游内容变了会重新载入（last_incoming 状态追踪）。
        - 逐框经 _to_centered_bbox 换成与 MOSSImageLayoutPrompt 一致的
          abs_centralized / yxyx 居中整数坐标，palette 随框写入 layout JSON。
        - 输出 (完整版式提示词, 元素列表, 版式预览图)，ui 携带 te_moss_apply / te_moss_last
          与预览图，前端画布据此同步。
        """
        get = kwargs.get
        boxes_text = str(get('boxes') or '[]')
        width = int(get('width') or 1024)
        height = int(get('height') or 1536)
        last_incoming = str(get('last_incoming') or '')

        incoming_text = _incoming_text(get('上游元素列表'))
        elements = None
        last_out = last_incoming
        if incoming_text.strip() and incoming_text != last_incoming:
            elements = _normalize_elements(incoming_text)
            last_out = incoming_text
        if not elements:
            elements = _normalize_elements(boxes_text)
        if not elements:
            raise ValueError('TE MAN MOSS 边界框: 没有解析到有效框，检查 bbox 是否为 [ymin,xmin,ymax,xmax]')

        caption_in = get('上游描述')
        caption = str(caption_in or '').strip() or str(get('整图描述') or '').strip()

        layout_prompt = _build_layout_prompt(elements, caption, width, height)
        elements_json = json.dumps(elements, ensure_ascii=False)

        image = _render_preview(elements, width, height)
        preview = _tensor_from_image(image)
        ui = {'te_moss_apply': elements, 'te_moss_last': last_out}
        images = _with_preview(image)
        if images:
            ui['images'] = images
        result = (layout_prompt, elements_json, preview)
        return {'ui': ui, 'result': result} if ui else {'result': result}

class TEMossLayoutNode:
    """TE MAN MOSS 增强版式规划/增强提示词

    注册名: TE_image_pro_moss_layout
    规格:   spec/TE_MAN_MOSS.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/MOSS'
    FUNCTION = 'plan'
    OUTPUT_NODE = True
    DESCRIPTION = '输入一句话，自动扩写文案与画面，并按选中版式生成边界框，输出可直接喂给 MOSS-Image 的 layout 提示词。扩写可用 CLIP、本地 llama.cpp 或 API；选「只扩写(无框位)」只输出整图描述，选「直出(不进行任何处理)」则 prompt 原样输出。描述可接到「TE MAN MOSS 边界框」的上游描述。'
    RETURN_TYPES = ('STRING', 'STRING', 'IMAGE', 'STRING')
    RETURN_NAMES = ('完整版式提示词', '元素列表', '版式预览图', '描述')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'增强方式': (('CLIP', '本地 llama.cpp', 'API'), {'default': 'CLIP', 'tooltip': '扩写用哪个模型。三者互不影响，没选中的后端参数可以留空。'}), 'prompt': ('STRING', {'multiline': True, 'default': '一张音乐节海报', 'tooltip': '一句话需求。中文即可，模型会扩写成完整画面描述并保留中文文案。'}), '版式选择': (('竖版海报', '横版横幅', '方形', '自动排版(官方skill)', '只扩写(无框位)', '直出(不进行任何处理)'), {'default': '竖版海报', 'tooltip': '内置版式骨架，坐标按比例存，换画布尺寸不用重算；「自动排版(官方skill)」由模型给每个槽位写位置，seed 变了版式也会变；「只扩写(无框位)」只输出扩写后的整图描述，不产生元素列表；「直出(不进行任何处理)」不调任何模型，prompt 原样传给下游。'}), 'width': ('INT', {'default': 1024, 'min': 256, 'max': 4096, 'step': 16, 'tooltip': '输出画布宽度，必须是 16 的倍数。'}), 'height': ('INT', {'default': 1536, 'min': 256, 'max': 4096, 'step': 16, 'tooltip': '输出画布高度，必须是 16 的倍数。'}), 'max_length': ('INT', {'default': 4096, 'min': 256, 'max': 8192, 'step': 64, 'tooltip': 'CLIP 与本地 llama.cpp 的生成上限（新增 token）；API 模式不发送此限制。'}), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 281474976710655, 'step': 1, 'tooltip': 'CLIP 与本地 llama.cpp 使用；API 模式忽略。'}), '输出语言': (('中文', '英文'), {'default': '中文', 'tooltip': '扩写出来的整图描述和元素描述用什么语言；JSON 字段、slot 名和 text/obj 结构值始终是英文。'}), '本地模型': (('（请把模型放到 models/LLM）',), {'tooltip': 'models/LLM 下的本地模型，仅「本地 llama.cpp」使用；其它方式不用管。'}), '生成后卸载本地模型': ('BOOLEAN', {'default': True, 'tooltip': '仅本地 llama.cpp。生成完就释放显存，避免和后面的 MOSS 出图抢显存；要连续调版式可以关掉。'}), 'api_base_url': ('STRING', {'default': 'https://teynex.com', 'multiline': False, 'tooltip': '仅 API 使用；按 OpenAI 兼容的 /responses 接口调用。'}), 'API模型(responses格式)': ('STRING', {'default': 'deepseek-v4.1-flash', 'multiline': False, 'tooltip': '仅 API 使用；填服务端 /responses 接口认识的模型名。'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': '仅 API 使用；留空时读取 TE MAN 的 config.ini。'})}, 'optional': {'clip': ('CLIP', {'forceInput': True, 'tooltip': '增强方式为 CLIP 时使用；其它方式接着也没关系。'})}}
        # --8<-- 契约结束 --8<--

    def plan(self, **kwargs):
        """一句话 -> 扩写 + 自动框位 -> MOSS layout 提示词。

        增强方式 CLIP / 本地 llama.cpp / API 三选一（互不影响）；版式选择六种：
        三个内置骨架（竖版海报/横版横幅/方形）+ 自动排版(官方skill) + 只扩写(无框位) + 直出。
        输出 (完整版式提示词, 元素列表, 版式预览图, 描述)，元素 bbox 为 0-1000 的
        [ymin, xmin, ymax, xmax] 整数（顺序与 ComfyUI 自带边界框一致）。
        """
        get = kwargs.get
        backend = str(get('增强方式') or 'CLIP')
        prompt = str(get('prompt') or '')
        preset = str(get('版式选择') or PRESET_CHOICES[0])
        width = int(get('width') or 1024)
        height = int(get('height') or 1536)
        max_length = int(get('max_length') or 4096)
        seed = int(get('seed') or 0)
        language = str(get('输出语言') or '中文')
        unload = bool(get('生成后卸载本地模型', True))
        api_base_url = str(get('api_base_url') or DEFAULT_API_BASE_URL)
        api_model = str(get('API模型(responses格式)') or DEFAULT_API_MODEL)
        api_key = str(get('api_key') or '')
        local_model = str(get('本地模型') or '')
        clip = get('clip')
        language_rule = LANGUAGE_RULES.get(language) or LANGUAGE_RULES['中文']

        if preset == RAW_PRESET:
            # 直出：不调任何模型，prompt 原样传给下游
            print('TE MAN MOSS: 没有框位，只输出纯文本提示词')
            return self._finish(prompt, [], prompt, width, height)

        # 后端校验：配置问题直接报错，不退化为纯文本
        if backend == 'CLIP' and (clip is None or not callable(getattr(clip, 'generate', None))):
            raise RuntimeError('增强方式为 CLIP 时需要连接 clip 输入')
        if backend == '本地 llama.cpp':
            _resolve_local_model(local_model)

        def degrade(text):
            """退化为纯文本提示词：无框位、无编译。"""
            body = str(text or '').strip() or prompt
            return self._finish(body, [], body, width, height)

        if preset == CAPTION_PRESET:
            system = _fill(CAPTION_SYSTEM_PROMPT, language_rules=language_rule, caption_rules=CAPTION_RULES)
            caption = ''
            raw = ''
            try:
                raw = _generate_text(
                    system, prompt, max_length,
                    backend=backend, clip=clip, local_model=local_model,
                    seed=seed, unload=unload,
                    api_base_url=api_base_url, api_model=api_model, api_key=api_key)
                data = _extract_json(raw)
                if isinstance(data, dict):
                    caption = str(data.get('caption') or '').strip()
                if not caption:
                    caption = _plain_caption(raw) or ''
            except Exception as exc:  # noqa: BLE001
                print('TE MAN MOSS 生成失败，退化为纯文本提示词: %s' % exc)
            if not caption:
                print('TE MAN MOSS: 只扩写没有拿到 caption，退回原 prompt（输出 %d 字）: %s'
                      % (len(raw or ''), str(raw or '')[:120]))
                caption = prompt
            return self._finish(caption, [], caption, width, height)

        auto = preset == AUTO_PRESET
        skeleton = None if auto else LAYOUT_PRESETS.get(preset)
        if not auto and skeleton is None:
            skeleton = LAYOUT_PRESETS[PRESET_CHOICES[0]]
        reply_shape = AUTO_REPLY_SHAPE if auto else REPLY_SHAPE
        layout_rules = AUTO_LAYOUT_RULES if auto else _preset_layout_rules(skeleton)
        if auto:
            slot_names = AUTO_SLOT_NAMES
            slot_types_line = AUTO_SLOT_TYPES_LINE
        else:
            slot_names = ', '.join('"%s"' % row[0] for row in skeleton)
            slot_types_line = ('The slot types are fixed: '
                               + ', '.join('"%s" is %s' % (row[0], row[1]) for row in skeleton) + '.')
        system = _fill(SYSTEM_PROMPT, reply_shape=reply_shape, slot_names=slot_names,
                       slot_types_line=slot_types_line, layout_rules=layout_rules,
                       language_rules=language_rule, caption_rules=CAPTION_RULES)

        raw = ''
        try:
            raw = _generate_text(
                system, prompt, max_length,
                backend=backend, clip=clip, local_model=local_model,
                seed=seed, unload=unload,
                api_base_url=api_base_url, api_model=api_model, api_key=api_key)
        except Exception as exc:  # noqa: BLE001
            print('TE MAN MOSS 生成失败，退化为纯文本提示词: %s' % exc)
            return degrade(raw)

        data = _extract_json(raw)
        if not isinstance(data, dict) or not isinstance(data.get('slots'), dict):
            print('TE MAN MOSS: 模型输出不是合法 JSON，退化为纯文本提示词: %s' % (raw or ''))
            return degrade(raw)

        slots = data.get('slots') or {}
        caption = str(data.get('caption') or '').strip() or prompt
        if auto:
            boxes = _auto_bbox(slots)
            if boxes is None:
                print('TE MAN MOSS: 自动排版没有可用的框，退回纵向均分')
                elements = _split_elements(slots)
            else:
                elements = _auto_elements(slots, boxes)
        else:
            elements = _preset_elements(slots, skeleton)
        return self._finish(_build_layout_prompt(elements, caption, width, height),
                            elements, caption, width, height)

    def _finish(self, layout_prompt, elements, caption, width, height):
        """统一收尾：元素列表 JSON + 预览图（挂到节点自身）+ ui。"""
        elements_json = json.dumps(elements, ensure_ascii=False)
        image = _render_preview(elements, width, height)
        preview = _tensor_from_image(image)
        ui = {}
        images = _with_preview(image)
        if images:
            ui['images'] = images
        result = (layout_prompt, elements_json, preview, caption)
        return {'ui': ui, 'result': result} if ui else {'result': result}

NODE_CLASS_MAPPINGS = {'TE_image_pro_moss_box': TEMossBoxNode, 'TE_image_pro_moss_layout': TEMossLayoutNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_moss_box': 'TE MAN MOSS 增强边界框/增强提示词', 'TE_image_pro_moss_layout': 'TE MAN MOSS 增强版式规划/增强提示词'}
