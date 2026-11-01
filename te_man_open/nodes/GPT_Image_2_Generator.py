# -*- coding: utf-8 -*-
"""te_man_open · GPT_Image_2_Generator（原 GPT_Image_2_Generator.pyd 的纯 Python 复刻）

TE MAN GPT Image 2 & 2.5 图像生成节点：通过 OpenAI 兼容 Images API
（可选 Chat Completions 兼容线路）做文生图 / 图生图，内置 10 种"快捷功能"
中文提示词模板，并用 task_runner.BatchGenerationRunner 做多张图并发生成。

实现依据 spec/GPT_Image_2_Generator.md（含动态 introspection 回填节）：
- 端点族 /v1/images/generations（JSON）、/v1/images/edits（multipart
  image_1..image_9）、/v1/chat/completions（图生图线路）、
  /v1/images/tasks/{task_id}（异步轮询）
- 尺寸由 比例×档位 WxH 映射表解析；模型 gpt-image-2[-1k/-2k/-4k] /
  gpt-image-2.5 由"模型选择"决定
- 线路1：1K 图生图走 edits 但模型保持 gpt-image-2，2K/4K 保持原线路；
  线路2：统一走 edits，且 1K 改用 gpt-image-2-1k
- 并发 BatchGenerationRunner、失败槽 ErrorCanvas 错误图、config_manager 配置
- requests/torch/PIL/numpy/comfy 系全部惰性导入
"""

from __future__ import annotations

import base64
import json
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from ..shared.config_manager import ConfigManager
from ..shared.image_codec import IMAGE_CODEC, ErrorCanvas
from ..shared.logger import logger
from ..shared.task_runner import BatchGenerationRunner, InterruptProcessingException

__all__ = [
    "TEGPTImage2SafePyNode",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
]


# ==================== 模块常量 ====================

#: 请求 UA（与 api_client / Grok 节点同风格）
_USER_AGENT = "ComfyUI-TE_API/1.0"

_MODEL_NAME = "gpt-image-2"
#: "模型选择" → 基础模型（spec §3.2）
_MODEL_OPTIONS: Dict[str, str] = {
    "GPT Image 2": "gpt-image-2",
    "GPT Image 2.5": "gpt-image-2.5",
}

_SIZE_RATIO_OPTIONS = (
    "Auto", "1:1", "16:9", "9:16", "3:2", "2:3", "4:3", "3:4", "5:4", "4:5", "7:3", "3:7",
)
_RESOLUTION_OPTIONS = ("1K", "2K", "4K")

# 比例 × 档位 → WxH 映射（spec §3.4 全部字面量；其中 5:4/4:5 与 7:3/3:7 在
# 2K/4K 档的归属 spec 标注未确认，此处按同口像素量级归档：
# 2K≈4MP 取 2240x1792 组与 3024x1296 组；4K≈8MP 取 3200x2560 组与 3696x1584 组）
_RESOLUTION_CONFIGS: Dict[str, Dict[str, str]] = {
    "1K": {
        "1:1": "1024x1024",
        "16:9": "1280x720", "9:16": "720x1280",
        "3:2": "1248x832", "2:3": "832x1248",
        "4:3": "1152x864", "3:4": "864x1152",
        "5:4": "1120x896", "4:5": "896x1120",
        "7:3": "1456x624", "3:7": "624x1456",
    },
    "2K": {
        "1:1": "2048x2048",
        "16:9": "2560x1440", "9:16": "1440x2560",
        "3:2": "2496x1664", "2:3": "1664x2496",
        "4:3": "2304x1728", "3:4": "1728x2304",
        "5:4": "2240x1792", "4:5": "1792x2240",
        "7:3": "3024x1296", "3:7": "1296x3024",
    },
    "4K": {
        "1:1": "2880x2880",
        "16:9": "3840x2160", "9:16": "2160x3840",
        "3:2": "3504x2336", "2:3": "2336x3504",
        "4:3": "3264x2448", "3:4": "2448x3264",
        "5:4": "3200x2560", "4:5": "2560x3200",
        "7:3": "3696x1584", "3:7": "1584x3696",
    },
}

#: 旧工作流保存的 WxH 尺寸文本 → 比例标签（spec §3.4 _LEGACY_SIZE_TO_RATIO）
_LEGACY_SIZE_TO_RATIO: Dict[str, str] = {}
for _tier_configs in _RESOLUTION_CONFIGS.values():
    for _ratio, _size in _tier_configs.items():
        _LEGACY_SIZE_TO_RATIO.setdefault(_size, _ratio)

#: 图生图线路（spec §3.3 日志原文；"generations(img2img)" 为历史兼容选项）
_IMG2IMG_ENDPOINT_OPTIONS = ("chat_completions(img2img)", "edits", "generations(img2img)")
#: 未暴露参数的默认值（spec §7.1：包装层运行时裁剪，仅字面串证据）
_DEFAULT_OUTPUT_FORMAT = "png"
_DEFAULT_BACKGROUND = "auto"
_DEFAULT_QUALITY = "high"

#: 错误截断长度（spec §7.2 动态回填实锤）
_MAX_API_ERROR_TEXT_LENGTH = 500
_MAX_DISPLAY_ERROR_LENGTH = 600

#: 异步任务轮询参数（spec 未确认具体数值，取合理默认）
_TASK_POLL_MAX_ATTEMPTS = 120
_TASK_POLL_INTERVAL_SECONDS = 3.0

#: chat 响应 URL 提取正则（spec §6.3 `https?://[^\s'"<>]+`）
_CHAT_URL_RE = re.compile(r"https?://[^\s'\"<>]+")

#: 同步响应异步任务标记
_TASK_ID_MARKERS = ("succeeded", "success", "completed", "complete", "done", "ok")
_TASK_FAILED_MARKERS = ("failed", "failure", "error", "cancelled", "canceled")

# ==================== 快捷功能模板 ====================

QUICK_FUNCTION_NONE = "无"
QUICK_FUNCTION_DIRECTOR_STORYBOARD = "导演故事板"
QUICK_FUNCTION_BLACK_WHITE_STORYBOARD = "黑白素写故事板"
#: 10 项精确顺序（spec §7.2 动态回填实锤）
QUICK_FUNCTION_OPTIONS = (
    "无",
    "白底三视图",
    "白底四视图",
    "九宫格[剧情]分镜",
    "九宫格[场景]分镜",
    "九宫格[导演]分镜",
    "四宫格[剧情]分镜",
    "四宫格[视角]分镜",
    "导演故事板",
    "黑白素写故事板",
)

# 与 Grok_Image_Generator 模块同文的模板（spec §6.5/§7.2：其余 7 项与 Grok 同文）
_QUICK_PREFIX_WHITE_BG_3VIEW = (
    "三视图（正面、侧面、背面），白色纯色背景，人物角色设计图，"
)
_QUICK_PREFIX_WHITE_BG_4VIEW = (
    "参照原图生成人物面部特写搭配全身三视图组合画面； "
    "画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照 / 侧面全身照 / 背面全身照，"
    "所有内容整合在 同一画幅内；采用纯白色背景，严格对齐人物人体比例 ，"
    "杜绝透视畸变问题，各视图之间间距均匀规整,无文字描述"
)
_QUICK_PREFIX_STORY_9 = (
    "根据提供的"
    "剧情概述 / 画面主题 / 参考图"
    "，生成一张具有清晰叙事推进关系的 3×3 九宫格分镜图，共 9 个连续镜头"
    "全部镜头发生在同一场景与同一时间轴内，九个画面之间必须存在明确的前后承接关系，"
    "形成连续的动作/视线或情绪推进，而不是彼此孤立的画面拼接"
    "分镜采用电影镜头语言进行自由发挥：在整体叙事推进中自然涵盖远景/中景/近景与特写等不同景别，"
    "并根据剧情需要灵活使用正视/侧视/背视/过肩/内反打/轻微俯仰等视角变化，"
    "用于强化空间关系/人物心理与节奏起伏"
    "镜头景别与角度不与编号固定绑定，而是由剧情发展自动选择最合适的表现方式，"
    "使九个镜头整体读起来具备真实影视分镜的流动感"
    "当用户仅提供剧情文字时，应主动补全合理的场景结构/人物站位/行动路线与镜头关系，"
    "使画面具备清晰空间逻辑；当用户提供参考图时，应将其作为人物外观/服装风格/色彩倾向与整体美术气质的统一依据，"
    "并在全部九个镜头中严格继承，不得随镜头推进出现风格变化或角色漂移"
    "在全部九个分镜中，人物的外观/服装/体型比例/面部特征保持一致，整体色彩倾向与光照条件统一，"
    "仅允许人物动作/姿态以及镜头远近和角度发生变化，"
    "不得出现角色变形/肢体缺失/结构错乱或美术风格断裂，纯视觉展示，没有任何文字/字母或标签，"
    "每个画面之间被清晰的黑色实线分割"
)
_QUICK_PREFIX_STORY_4 = (
    "根据提供的"
    "剧情概述 / 画面主题 / 参考图"
    "，生成一张具有清晰叙事推进关系的 2×2 四宫格分镜图，共 4 个连续镜头"
    "全部镜头发生在同一场景与同一时间轴内，四个画面之间必须存在明确的前后承接关系，"
    "形成连续的动作/视线或情绪推进，而不是彼此孤立的画面拼接"
    "分镜采用电影镜头语言进行自由发挥：在整体叙事推进中自然涵盖远景/中景/近景与特写等不同景别，"
    "并根据剧情需要灵活使用正视/侧视/背视/过肩/内反打/轻微俯仰等视角变化，"
    "用于强化空间关系/人物心理与节奏起伏"
    "镜头景别与角度不与编号固定绑定，而是由剧情发展自动选择最合适的表现方式，"
    "使四个镜头整体读起来具备真实影视分镜的流动感"
    "当用户仅提供剧情文字时，应主动补全合理的场景结构/人物站位/行动路线与镜头关系，"
    "使画面具备清晰空间逻辑；当用户提供参考图时，应将其作为人物外观/服装风格/色彩倾向与整体美术气质的统一依据，"
    "并在全部四个镜头中严格继承，不得随镜头推进出现风格变化或角色漂移"
    "在全部四个分镜中，人物的外观/服装/体型比例/面部特征保持一致，整体色彩倾向与光照条件统一，"
    "仅允许人物动作/姿态以及镜头远近和角度发生变化，"
    "不得出现角色变形/肢体缺失/结构错乱或美术风格断裂，纯视觉展示，没有任何文字/字母或标签，"
    "每个画面之间被清晰的黑色实线分割"
)
_QUICK_PREFIX_SCENE_9 = (
    "生成一张严格的3x3九宫格图像，纯视觉展示"
    "正中央为场景标准透视效果图；正上方为俯视角度画面；正下方为地面纹理视角；"
    "左侧为左侧墙壁平视画面；右侧为右侧墙壁平视画面；"
    "四个角落分别是：正前方视角/正后方视角以及两个无文字的材质道具特写"
    "要求：九个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，"
)
_QUICK_PREFIX_VIEW_4 = (
    "生成一张严格的2x2四宫格图像，纯视觉展示"
    "场景标准透视效果图；俯视角度画面；正正前方视角；正后方视角"
    "要求：四个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，"
)
#: 九宫格[导演]分镜 英文模板（spec §7.2 实锤绑定此项）
_QUICK_PREFIX_DIRECTOR_GRID_9 = (
    "storyboard sheet, 九宫格,black UI layout, grid panel composition, professional film storyboard,"
)

QUICK_FUNCTION_PREFIXES: Dict[str, str] = {
    "无": "",
    "白底三视图": _QUICK_PREFIX_WHITE_BG_3VIEW,
    "白底四视图": _QUICK_PREFIX_WHITE_BG_4VIEW,
    "九宫格[剧情]分镜": _QUICK_PREFIX_STORY_9,
    "九宫格[场景]分镜": _QUICK_PREFIX_SCENE_9,
    "九宫格[导演]分镜": _QUICK_PREFIX_DIRECTOR_GRID_9,
    "四宫格[剧情]分镜": _QUICK_PREFIX_STORY_4,
    "四宫格[视角]分镜": _QUICK_PREFIX_VIEW_4,
    # spec §7.2：导演故事板 / 黑白素写故事板 的 PREFIXES 映射为 ""，
    # 正文改由 DIRECTOR_STORYBOARD_PROMPT_PREFIX/SUFFIX 与
    # BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX 拼接
    "导演故事板": "",
    "黑白素写故事板": "",
}

# 导演故事板：spec §3.5/§7.2 确认了首句、可填字段名、生成要求、版面四区布局与
# 清晰度限制的要点，但未采集全文 —— 以下按已实锤要点组织，模板全文待抓包校准
DIRECTOR_STORYBOARD_PROMPT_PREFIX = (
    "请生成一张中文专业电影故事板图片，用作 Seedance 2.0 视频生成模型的参考图。\n"
    "请先阅读【故事内容】，再按下方要求扩写为约 15 秒、多镜头的专业电影分镜故事板。\n"
    "【画面比例】：默认 16:9 横版；如果我填写 9:16，则生成 9:16 竖版。\n"
    "【画面风格】：从「都市情绪短片/商业广告感/生活纪实感/轻科幻感/悬疑感/动作电影感/"
    "温暖治愈感/唯美国风」中选择与故事最匹配的一种，并在全部镜头中保持统一。\n"
    "【特殊要求】：如动作节奏、光影、色彩和镜头语言等；若未指定，请按剧情需要自行合理安排。\n"
    "【生成要求】：\n"
    "- 不要漫画风，不要草图风，不要海报构图，不要水印，不要乱码\n"
    "- 每个分镜画面为写实质感的电影帧，镜头之间具备清晰的叙事推进关系\n"
    "- 版面为一张完整的故事板图，而不是单张大图冒充分镜\n"
    "【故事内容】："
)
DIRECTOR_STORYBOARD_PROMPT_SUFFIX = (
    "\n【版面布局】：\n"
    "- 顶部信息栏：项目名｜类型｜15秒｜镜头数｜布局｜画面比例｜\n"
    "- 左侧锚点栏占画面宽度 18%~22%：纵向排列镜头编号与时长标签\n"
    "- 右侧核心分镜区占画面宽度 70%~75%：按行排布各镜头画面\n"
    "- 底部标签栏：Lighting:｜Mood:｜Style:｜Audio:｜Camera:｜Keywords:\n"
    "【清晰度限制】：避免密集小字/复杂图例/过多箭头/杂乱 UI/粗边框/乱码文字/无关字幕/"
    "摄像机设备/漫画风/草图风/儿童绘本风/过度插画风/海报构图/单张大图冒充分镜。"
)
# 黑白素写故事板：spec §3.5/§7.2 确认前两句与彩色标注系统要点，模板全文待抓包校准
BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX = (
    "\n按照输入的故事脚本生成15秒视频的9宫格故事板，保持16:9宽屏。\n"
    "采用黑白铅笔速写风格与彩色标注系统："
    "红=身体运动，蓝=摄影机运动，绿=取景构图，橙=灯光方向，紫=声音情感，黑=镜头笔记。\n"
    "九个画面按时间顺序排布，逐格保持角色外观与场景一致性；"
    "除彩色标注线条外不出现其他彩色渲染，画面中不出现解释性长文字。"
)

#: 共享支撑实例
CONFIG_MANAGER = ConfigManager()
ERROR_CANVAS = ErrorCanvas()


# ==================== 通用小工具 ====================

def _ensure_not_interrupted() -> None:
    """ComfyUI 中断透传（spec §3.6：throw_exception_if_processing_interrupted + InterruptProcessingException）。"""
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001  非 ComfyUI 环境
        return
    throw = getattr(model_management, "throw_exception_if_processing_interrupted", None)
    if callable(throw):
        throw()
        return
    ensure = getattr(model_management, "ensure_not_interrupted", None)
    if callable(ensure):
        ensure()


def _make_comfy_progress_bar(total: int):
    """comfy.utils.ProgressBar 工厂（comfy 不可用时返回 None，runner 自行兜底）。"""
    try:
        from comfy.utils import ProgressBar  # 惰性导入

        return ProgressBar(int(total))
    except Exception:  # noqa: BLE001
        return None


def _resolve_timeout(timeout_s: Any = None) -> Tuple[float, float]:
    """归一为 (connect_timeout, read_timeout)（spec §4.1 _resolve_timeout 同模式）。"""
    try:
        value = float(timeout_s) if timeout_s is not None else 300.0
    except (TypeError, ValueError):
        value = 300.0
    value = max(5.0, value)
    return (min(15.0, value), value)


def _masked_key(api_key: str) -> str:
    key = str(api_key or "")
    if len(key) <= 8:
        return "..."
    return "%s...%s" % (key[:4], key[-4:])


def _format_api_error_payload(payload_text: Any) -> str:
    """错误响应载荷截断（_MAX_API_ERROR_TEXT_LENGTH=500，spec §7.2 实锤）。"""
    text = str(payload_text or "").strip()
    if len(text) > _MAX_API_ERROR_TEXT_LENGTH:
        return text[:_MAX_API_ERROR_TEXT_LENGTH] + "...（错误响应已截断）"
    return text


def _format_display_text(text: str) -> str:
    """展示文本截断（_MAX_DISPLAY_ERROR_LENGTH=600）。"""
    value = str(text or "").strip()
    if len(value) > _MAX_DISPLAY_ERROR_LENGTH:
        return value[:_MAX_DISPLAY_ERROR_LENGTH] + "...（错误响应已截断）"
    return value


def _format_http_error_response(response: Any) -> str:
    try:
        body = response.text
    except Exception:  # noqa: BLE001
        body = ""
    return "HTTP %s: %s" % (getattr(response, "status_code", "?"), _format_api_error_payload(body))


def _normalize_base_url(api_base_url: str) -> str:
    """归一 base：http(s):// 前缀检查（spec §4.1）；为空报 未配置有效的 API Base URL。"""
    base = str(api_base_url or "").strip()
    if not base:
        raise ValueError("未配置有效的 API Base URL")
    if not re.match(r"^https?://", base, re.IGNORECASE):
        base = "http://" + base
    return base.rstrip("/")


def _origin_of(base_url: str) -> str:
    parsed = urlparse(base_url if base_url.endswith("/") else base_url + "/")
    return "%s://%s" % (parsed.scheme, parsed.netloc)


def _resolve_gpt_image_2_endpoint(api_base_url: str, path_v1: str, path_short: str) -> str:
    """端点解析：兼容 base 已带完整端点 / 已带 /v1 / 纯主机三种写法。"""
    base = _normalize_base_url(api_base_url)
    lowered = base.lower()
    for suffix in (path_v1, path_short):
        if lowered.endswith(suffix):
            return base
    if lowered.endswith("/v1"):
        return base + path_short
    return base + path_v1


def _resolve_gpt_image_2_task_endpoint(api_base_url: str, task_id: str) -> str:
    """异步任务轮询端点：{base}/v1/images/tasks/{task_id}。"""
    base = _normalize_base_url(api_base_url)
    lowered = base.lower()
    if lowered.endswith("/v1"):
        return base + "/images/tasks/" + str(task_id)
    if lowered.endswith("/images/tasks/"):
        return base + str(task_id)
    return base + "/v1/images/tasks/" + str(task_id)


def _normalize_task_status(value: Any) -> str:
    return str(value or "").strip().lower()


def _decode_response_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            return raw.decode(encoding)
        except Exception:  # noqa: BLE001
            continue
    return raw.decode("utf-8", errors="replace")


def _image_bytes_to_tensor(data: bytes):
    """图片字节 → float32 [1,H,W,C] tensor（惰性 torch/PIL，经 image_codec）。"""
    return IMAGE_CODEC.base64_to_tensor_single(base64.b64encode(data).decode("ascii"))


# ==================== 节点 ====================

class TEGPTImage2SafePyNode:
    """TE MAN GPT Image 2 & 2.5

    注册名: TE_image_pro_gpt_image_2
    规格:   spec/GPT_Image_2_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/OpenAI'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    DESCRIPTION = '使用 gpt-image-2 通过 OpenAI Images API 进行文生图或图生图。'
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只戴着墨镜的白色猫咪，电影感，细节丰富', 'tooltip': 'gpt-image-2 提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则使用 config.ini 中配置'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址；留空则使用 config.ini 中配置'}), 'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 8, 'tooltip': '生成批次数量；每个批次生成 1 张图'}), '分辨率(价格不同)': (('1K', '2K', '4K'), {'default': '1K', 'tooltip': '1K / 2K / 4K；分辨率不同,价格不同。'}), 'size': (('Auto', '1:1', '16:9', '9:16', '3:2', '2:3', '4:3', '3:4', '5:4', '4:5', '7:3', '3:7'), {'default': '16:9', 'tooltip': '选择需要生成的分辨率比例。'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅用于 ComfyUI 工作流记录，不写入请求体。'}), 'image_1': ('IMAGE', {'tooltip': '参考/编辑输入图像 1（可选）'}), 'image_2': ('IMAGE', {'tooltip': '参考/编辑输入图像 2（可选）'}), 'image_3': ('IMAGE', {'tooltip': '参考/编辑输入图像 3（可选）'}), 'image_4': ('IMAGE', {'tooltip': '参考/编辑输入图像 4（可选）'}), 'image_5': ('IMAGE', {'tooltip': '参考/编辑输入图像 5（可选）'}), 'image_6': ('IMAGE', {'tooltip': '参考/编辑输入图像 6（可选）'}), 'image_7': ('IMAGE', {'tooltip': '参考/编辑输入图像 7（可选）'}), 'image_8': ('IMAGE', {'tooltip': '参考/编辑输入图像 8（可选）'}), 'image_9': ('IMAGE', {'tooltip': '参考/编辑输入图像 9（可选）'}), '线路选择': (('线路1', '线路2'), {'default': '线路1', 'tooltip': '线路1：1K 图生图走 edits 但模型保持 gpt-image-2，2K/4K 保持原线路。线路2：统一走 edits，且 1K 改用 gpt-image-2-1k。'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '九宫格[导演]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜', '导演故事板', '黑白素写故事板'), {'default': '无', 'tooltip': '使用快捷功能生成。'}), '增强提示词输入': ('STRING', {'forceInput': True, 'tooltip': '连接上游文本后优先使用该内容；未连接时使用节点内的增强提示词框。'}), '模型选择': (('GPT Image 2', 'GPT Image 2.5'), {'default': 'GPT Image 2', 'tooltip': '选择 GPT Image 2 或 GPT Image 2.5 模型系列。'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 配置解析（spec §3.1 _resolve_key_and_url） ====================

    def _resolve_key_and_url(self, api_key: str = "", api_base_url: str = "") -> Tuple[str, str]:
        """API Key / Base URL：节点输入 → config.ini；两者皆缺报汇总提示。"""
        missing = []
        key = ""
        if str(api_key or "").strip():
            key = CONFIG_MANAGER.sanitize_api_key(api_key) or ""
        if not key:
            key = CONFIG_MANAGER.load_api_key() or ""
        if not key:
            missing.append("API Key")

        base = str(api_base_url or "").strip() or CONFIG_MANAGER.get_effective_api_base_url()
        if not base:
            missing.append("API URL")

        if len(missing) == 2:
            raise ValueError("请在 config.ini 或节点输入中填写有效配置")
        if missing:
            logger.warning(
                "请在 config.ini 中配置 %s 或在节点中填写" % ("API URL" if missing[0] == "API URL" else "API Key")
            )
            if missing[0] == "API Key":
                raise ValueError("请填写有效的 API Key")

        logger.info("使用 API Key: %s | 使用 API Base URL: [已脱敏]" % _masked_key(key))
        return key, base

    # ==================== 尺寸体系（spec §3.4） ====================

    @staticmethod
    def _normalize_resolution(resolution_label: Any) -> str:
        """分辨率标签归一：非 1K/2K/4K 时回退 1K。"""
        text = str(resolution_label or "1K").strip().upper()
        return text if text in _RESOLUTION_OPTIONS else "1K"

    @staticmethod
    def _get_resolution_config(resolution: str) -> Dict[str, str]:
        """档位 → 比例 → WxH 映射表。"""
        return _RESOLUTION_CONFIGS.get(resolution, _RESOLUTION_CONFIGS["1K"])

    @staticmethod
    def _normalize_size_text(size_label: Any) -> str:
        """旧工作流 WxH 尺寸文本 → 比例标签（_LEGACY_SIZE_TO_RATIO）。"""
        text = str(size_label or "").strip().lower().replace("×", "x")
        if text in _LEGACY_SIZE_TO_RATIO:
            return _LEGACY_SIZE_TO_RATIO[text]
        return str(size_label or "").strip()

    @staticmethod
    def _normalize_ratio_label(size_label: Any) -> str:
        """比例标签归一：未知标签回退 16:9（节点默认）。"""
        text = str(size_label or "").strip()
        if text == "Auto":
            return "Auto"
        if text in _RESOLUTION_CONFIGS["1K"]:
            return text
        legacy = TEGPTImage2SafePyNode._normalize_size_text(text)
        return legacy if legacy in _RESOLUTION_CONFIGS["1K"] else "16:9"

    @classmethod
    def _resolve_request_size(cls, resolution: Any, size_label: Any) -> str:
        """比例 × 档位 → WxH；Auto → "auto"（不指定具体像素）。"""
        ratio = cls._normalize_ratio_label(size_label)
        if ratio == "Auto":
            return "auto"
        return cls._get_resolution_config(cls._normalize_resolution(resolution)).get(ratio, "auto")

    # ==================== 模型与线路解析（spec §3.2/§3.3） ====================

    @staticmethod
    def _resolve_request_model(
        model_choice: Any,
        resolution: Any,
        img2img: bool = False,
        line_choice: str = "线路1",
    ) -> str:
        """"模型选择" + 分辨率档位 → 请求模型名。

        - GPT Image 2：按档位追加 -1k/-2k/-4k 后缀（字面串实锤）；
          线路1 + 1K 图生图 → 模型保持 gpt-image-2（无 -1k 后缀）；
          线路2 + 1K 图生图 → gpt-image-2-1k。
        - GPT Image 2.5：无后缀变体串（spec §3.2 未确认是否追加，取不追加）。
        """
        base_model = _MODEL_OPTIONS.get(str(model_choice or "GPT Image 2"), _MODEL_NAME)
        if base_model != _MODEL_NAME:
            return base_model
        tier = TEGPTImage2SafePyNode._normalize_resolution(resolution)
        if img2img and str(line_choice or "线路1") == "线路1" and tier == "1K":
            # 线路1：1K 图生图走 edits 但模型保持 gpt-image-2
            return _MODEL_NAME
        return "%s-%s" % (_MODEL_NAME, tier.lower())

    @staticmethod
    def _should_use_line1_edits_for_1k_img2img(line_choice: str, resolution: Any, img2img: bool) -> bool:
        """线路1 + 1K + 图生图 → 走 /v1/images/edits。"""
        return bool(img2img) and str(line_choice or "线路1") == "线路1" and (
            TEGPTImage2SafePyNode._normalize_resolution(resolution) == "1K"
        )

    @classmethod
    def _resolve_effective_img2img_endpoint_mode(
        cls, line_choice: str, resolution: Any, img2img: bool
    ) -> str:
        """图生图线路裁决（spec §3.3 GPT Image 2.5 的线路修正）。

        - 线路1：1K 图生图走 edits，2K/4K 保持原线路（chat_completions）；
        - 线路2：统一走 edits。
        """
        if not img2img:
            return "generations"
        line = str(line_choice or "线路1")
        if line == "线路2":
            return "edits"
        if cls._should_use_line1_edits_for_1k_img2img(line, resolution, img2img):
            return "edits"
        return "chat_completions"

    @staticmethod
    def _should_strip_line2_optional_fields(line_choice: str, mode: str) -> bool:
        """线路2（edits）剥除可选字段（quality/background/output_format）。"""
        return str(line_choice or "线路1") == "线路2" and mode == "edits"

    @staticmethod
    def _strip_line2_optional_fields(fields: Dict[str, Any]) -> Dict[str, Any]:
        """剥除可选字段副本（_should_strip_line2_optional_fields 的执行端）。"""
        cleaned = dict(fields)
        for key in ("quality", "background", "output_format"):
            cleaned.pop(key, None)
        return cleaned

    # ==================== 请求构造（spec §3.3 _build_gpt_image_2_request） ====================

    def _build_gpt_image_2_request(
        self,
        final_prompt_text: str,
        request_model: str,
        request_size: str,
        mode: str,
        input_tensors: List[Any],
        line_choice: str,
        api_base_url_value: str,
    ) -> Dict[str, Any]:
        """构造一次请求的 (endpoint_url, request_kwargs)。

        - generations → POST {base}/v1/images/generations（JSON）
        - edits → POST {base}/v1/images/edits（multipart image_1..image_9 + form）
        - chat_completions → POST {base}/v1/chat/completions（messages + data URL 输入图）
        """
        if mode == "edits":
            url = _resolve_gpt_image_2_endpoint(api_base_url_value, "/v1/images/edits", "/images/edits")
            files = self._prepare_input_image_file_parts(input_tensors)
            fields: Dict[str, Any] = {
                "model": request_model,
                "prompt": final_prompt_text,
                "size": request_size,
                "output_format": _DEFAULT_OUTPUT_FORMAT,
                "background": _DEFAULT_BACKGROUND,
                "quality": _DEFAULT_QUALITY,
            }
            if self._should_strip_line2_optional_fields(line_choice, mode):
                fields = self._strip_line2_optional_fields(fields)
            return {"url": url, "mode": mode, "files": files, "form": fields}

        if mode == "chat_completions":
            url = _resolve_gpt_image_2_endpoint(api_base_url_value, "/v1/chat/completions", "/chat/completions")
            content: Any = final_prompt_text
            if input_tensors:
                # 输入图统一以 data URL 入 content（spec §3.3 image_data_url 形态）
                parts: List[Dict[str, Any]] = [{"type": "text", "text": final_prompt_text}]
                for data_url in IMAGE_CODEC.prepare_input_image_data_urls(input_tensors):
                    parts.append({"type": "image_url", "image_url": {"url": data_url}})
                content = parts
            payload = {"model": request_model, "messages": [{"role": "user", "content": content}]}
            return {"url": url, "mode": mode, "json": payload}

        # 文生图 / 历史兼容 generations(img2img)
        url = _resolve_gpt_image_2_endpoint(api_base_url_value, "/v1/images/generations", "/images/generations")
        payload = {
            "model": request_model,
            "prompt": final_prompt_text,
            "size": request_size,
            "output_format": _DEFAULT_OUTPUT_FORMAT,
            "background": _DEFAULT_BACKGROUND,
            "quality": _DEFAULT_QUALITY,
        }
        return {"url": url, "mode": mode, "json": payload}

    def _prepare_input_image_file_parts(self, input_tensors: List[Any]) -> List[Tuple[str, Tuple[str, bytes, str]]]:
        """输入图 → multipart files（字段名 image_1..image_9，spec §3.1/§6.3）。"""
        try:
            parts: List[Tuple[str, Tuple[str, bytes, str]]] = []
            index = 0
            for tensor in input_tensors:
                for image in IMAGE_CODEC.extract_numpy_images(tensor):
                    index += 1
                    if index > 9:
                        break
                    field_name = "image_%d" % index
                    _field, filename, mime_type, data = IMAGE_CODEC.encode_numpy_image_to_api_file_part(
                        image, field_name=field_name, filename_prefix="image_%d" % index
                    )
                    parts.append((field_name, (filename, data, mime_type)))
        except ImportError as exc:  # noqa: BLE001
            raise RuntimeError("缺少图像依赖（numpy）: %s" % exc) from exc
        except ValueError as exc:  # noqa: BLE001
            raise RuntimeError("无法从 tensor 中提取有效图像数据: %s" % exc) from exc
        if not parts:
            raise RuntimeError("无法从 tensor 中提取有效图像数据: 无有效输入图像")
        return parts

    # ==================== 同步响应解析（spec §3.3） ====================

    @staticmethod
    def _collect_data_items(node: Any, b64_list: List[str], url_list: List[str]) -> None:
        """Images 同步响应：data[]（direct_items/top_data/nested_data/nested_items）逐项取 b64_json/url。"""
        if not isinstance(node, dict):
            return
        data = node.get("data")
        items: List[Any] = []
        if isinstance(data, list):
            items = data  # direct_items
        elif isinstance(data, dict):
            nested = data.get("data")
            if isinstance(nested, list):
                items = nested  # nested_items
            else:
                items = [data]  # nested_data
        for item in items:
            if not isinstance(item, dict):
                continue
            b64 = item.get("b64_json") or item.get("image") or item.get("base64")
            url = item.get("url")
            if b64:
                b64_list.append(re.sub(r"\s+", "", str(b64)))
            elif isinstance(url, str) and url.strip():
                url_list.append(url.strip())
            revised = item.get("revised_prompt")
            if revised:
                # revised_prompt 仅文本，不作为图像
                pass

    @staticmethod
    def _find_task_id(response_data: Any) -> Optional[str]:
        """在响应浅层查找 task_id（data 包一层也算）。"""
        if not isinstance(response_data, dict):
            return None
        for candidate in (response_data, response_data.get("data")):
            if isinstance(candidate, dict):
                value = candidate.get("task_id")
                if value:
                    return str(value)
        return None

    def _extract_sync_gpt_image_2_content(self, response_data: Any) -> Tuple[List[str], List[str], Optional[str]]:
        """同步 Images 响应 → (b64_list, url_list, task_id)。"""
        b64_list: List[str] = []
        url_list: List[str] = []
        # _collect_data_items 内部已处理 data 包一层的 nested_data/nested_items 结构
        self._collect_data_items(response_data, b64_list, url_list)
        return b64_list, url_list, self._find_task_id(response_data)

    def _extract_chat_completions_content(self, response_data: Any) -> Tuple[List[str], List[str]]:
        """chat/completions 响应 → (b64_list, url_list)。

        取 choices[0].message：content / images[].image_url.url / output_text / text；
        URL 用正则抽取并用 seen_urls 去重（append_url / collect_from_text 闭包）。
        """
        if not isinstance(response_data, dict):
            raise RuntimeError("chat/completions 响应中没有 choices")
        choices = response_data.get("choices")
        if not choices:
            raise RuntimeError("chat/completions 响应中没有 choices")
        first = choices[0] if isinstance(choices[0], dict) else {}
        message = first.get("message") if isinstance(first.get("message"), dict) else {}

        b64_list: List[str] = []
        url_list: List[str] = []
        seen_urls: set = set()

        def append_url(raw_url: Any) -> None:
            url = str(raw_url or "").strip()
            if not url or url in seen_urls:
                return
            seen_urls.add(url)
            if url.startswith("data:image/") and ";base64," in url:
                b64_list.append(re.sub(r"\s+", "", url.split(";base64,", 1)[1]))
            elif url.startswith(("http://", "https://")):
                url_list.append(url)

        def collect_from_text(text: Any) -> None:
            for match in _CHAT_URL_RE.finditer(str(text or "")):
                append_url(match.group(0))

        content = message.get("content")
        if isinstance(content, str):
            collect_from_text(content)
        elif isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "image_url" or "image_url" in part:
                    image_url = part.get("image_url")
                    if isinstance(image_url, dict):
                        append_url(image_url.get("url"))
                    elif isinstance(image_url, str):
                        append_url(image_url)
                elif part.get("text"):
                    collect_from_text(part.get("text"))
        for image in message.get("images") or []:
            if isinstance(image, dict):
                image_url = image.get("image_url")
                if isinstance(image_url, dict):
                    append_url(image_url.get("url"))
                elif isinstance(image_url, str):
                    append_url(image_url)
                else:
                    append_url(image.get("url"))
        collect_from_text(message.get("output_text"))
        collect_from_text(message.get("text"))

        if not b64_list and not url_list:
            raise RuntimeError("chat/completions 响应中无可用图像数据")
        return b64_list, url_list

    # ==================== 异步任务轮询（spec §3.3） ====================

    def _normalize_task_result(self, data: Any) -> Dict[str, Any]:
        """任务查询响应归一：统一 status / b64_list / url_list / error。"""
        status = ""
        error_text = ""
        b64_list: List[str] = []
        url_list: List[str] = []
        if isinstance(data, dict):
            payload = data.get("data") if isinstance(data.get("data"), dict) else data
            for key in ("task_status", "status", "state"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    status = _normalize_task_status(value)
                    break
            error_text = str(payload.get("error") or payload.get("message") or "")
            # _collect_data_items 内部已处理 data 包一层的嵌套结构
            self._collect_data_items(data, b64_list, url_list)
        return {"status": status, "b64_list": b64_list, "url_list": url_list, "error": error_text}

    def _poll_gpt_image_2_task(
        self,
        session: Any,
        api_base_url_value: str,
        api_key_value: str,
        task_id: str,
        timeout_value: Tuple[float, float],
        verify_ssl: bool = True,
    ) -> Dict[str, Any]:
        """GET /v1/images/tasks/{task_id} 轮询直至成功/失败/超时（max_attempts/interval_seconds）。"""
        url = _resolve_gpt_image_2_task_endpoint(api_base_url_value, task_id)
        headers = {
            "Authorization": "Bearer %s" % api_key_value,
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        last_error_text = ""
        for attempt in range(1, _TASK_POLL_MAX_ATTEMPTS + 1):
            _ensure_not_interrupted()
            try:
                response = session.get(url, headers=headers, timeout=timeout_value, verify=verify_ssl)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("gpt-image-2 任务查询失败: %s" % exc) from exc
            if response.status_code // 100 != 2:
                raise RuntimeError(
                    "gpt-image-2 任务查询失败: %s" % _format_http_error_response(response)
                )
            try:
                data = response.json()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("gpt-image-2 任务查询失败: 响应非 JSON: %s" % exc) from exc
            normalized = self._normalize_task_result(data)
            status = normalized["status"]
            if status in _TASK_ID_MARKERS or (normalized["b64_list"] or normalized["url_list"]):
                if normalized["b64_list"] or normalized["url_list"]:
                    logger.info("gpt-image-2 任务轮询 %d 次完成" % attempt)
                    return normalized
            if status in _TASK_FAILED_MARKERS:
                last_error_text = normalized["error"] or status or "unknown"
                raise RuntimeError("gpt-image-2 异步任务失败: %s" % _format_display_text(last_error_text))
            time.sleep(_TASK_POLL_INTERVAL_SECONDS)
        raise TimeoutError("gpt-image-2 异步任务超时，task_id=%s" % task_id)

    # ==================== 同步请求发送（spec §3.3 _send_sync_gpt_image_2_request） ====================

    def _send_sync_gpt_image_2_request(
        self,
        session: Any,
        api_key_value: str,
        request: Dict[str, Any],
        timeout_value: Tuple[float, float],
        verify_ssl: bool = True,
    ) -> Any:
        """发出单次同步请求并校验 HTTP 状态；异常归一为 gpt-image-2 请求失败。"""
        import requests  # 惰性导入

        url = request["url"]
        mode = request.get("mode")
        headers = {
            "Authorization": "Bearer %s" % api_key_value,
            "Accept": "application/json",
            "User-Agent": _USER_AGENT,
        }
        try:
            if mode == "edits":
                headers["Accept-Encoding"] = "gzip, deflate"
                response = session.post(
                    url,
                    files=request.get("files"),
                    data=request.get("form"),
                    headers=headers,
                    timeout=timeout_value,
                    verify=verify_ssl,
                )
            else:
                headers["Content-Type"] = "application/json"
                response = session.post(
                    url,
                    json=request.get("json"),
                    headers=headers,
                    timeout=timeout_value,
                    verify=verify_ssl,
                )
        except requests.exceptions.RequestException as exc:  # noqa: BLE001
            raise RuntimeError("gpt-image-2 请求失败: %s" % exc) from exc
        if response.status_code // 100 != 2:
            raise RuntimeError(
                "gpt-image-2 请求失败: %s" % _format_http_error_response(response)
            )
        return response

    # ==================== 单任务 worker（spec §3.6 _generate_single_image_gpt_image_2） ====================

    def _generate_single_image_gpt_image_2(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """线程 worker：单批次 1 张图（同步请求 → task_id 轮询 → 下载/解码）。"""
        import requests  # 惰性导入

        context = task["context"]
        bypass_proxy = bool(context["bypass_proxy"])
        verify_ssl = True
        timeout_value = _resolve_timeout(context["timeout_s"])

        try:
            _ensure_not_interrupted()
            session = requests.Session()
            session.trust_env = not bypass_proxy

            request = self._build_gpt_image_2_request(
                context["final_prompt_text"],
                context["request_model"],
                context["request_size"],
                context["mode"],
                context["input_tensors"],
                context["line_choice"],
                context["api_base_url_value"],
            )
            response = self._send_sync_gpt_image_2_request(
                session, context["api_key_value"], request, timeout_value, verify_ssl
            )
            try:
                response_data = response.json()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("gpt-image-2 请求失败: 响应非 JSON: %s" % exc) from exc

            b64_list: List[str] = []
            url_list: List[str] = []
            if context["mode"] == "chat_completions":
                b64_list, url_list = self._extract_chat_completions_content(response_data)
            else:
                sync_b64, sync_urls, sync_task_id = self._extract_sync_gpt_image_2_content(response_data)
                b64_list.extend(sync_b64)
                url_list.extend(sync_urls)
                if sync_task_id:
                    logger.info("gpt-image-2 收到 task_id，开始自动轮询: %s" % sync_task_id)
                    polled = self._poll_gpt_image_2_task(
                        session,
                        context["api_base_url_value"],
                        context["api_key_value"],
                        sync_task_id,
                        timeout_value,
                        verify_ssl,
                    )
                    b64_list.extend(polled.get("b64_list") or [])
                    url_list.extend(polled.get("url_list") or [])

            if not b64_list and not url_list:
                raise RuntimeError("响应中无可用图像数据: status=%s" % response.status_code)

            tensors = []
            for b64_value in b64_list:
                tensors.append(IMAGE_CODEC.base64_to_tensor_single(b64_value))
            for url in url_list:
                try:
                    data = self._download_image_bytes(session, context["api_key_value"], url, timeout_value, verify_ssl)
                except Exception as exc:  # noqa: BLE001
                    label = (
                        "下载 chat/completions 图片失败: %s" % exc
                        if context["mode"] == "chat_completions"
                        else "下载图片失败: %s" % exc
                    )
                    logger.warning(label)
                    continue
                tensors.append(_image_bytes_to_tensor(data))
            tensors = [t for t in tensors if t is not None]
            if not tensors:
                raise RuntimeError("响应中无可用图像数据")
            return {"tensors": tensors, "error": None}
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001
            return {"tensors": [], "error": str(exc) or "生成失败"}

    @staticmethod
    def _download_image_bytes(session: Any, api_key_value: str, url: str, timeout_value: Tuple[float, float], verify_ssl: bool = True) -> bytes:
        """带鉴权下载图片 URL（b64_json 缺失时回退 url 下载）。"""
        headers = {
            "Authorization": "Bearer %s" % api_key_value,
            "Accept": "image/*, application/json",
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": _USER_AGENT,
        }
        response = session.get(url, headers=headers, timeout=timeout_value, verify=verify_ssl, stream=True)
        response.raise_for_status()
        chunks: List[bytes] = []
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                chunks.append(chunk)
        data = b"".join(chunks)
        if not data:
            raise RuntimeError("下载内容为空")
        return data

    # ==================== 主入口（spec §3.6 _generate_with_gpt_image_2_api / generate_images） ====================

    def generate_images(self, **kwargs):
        """文生图 / 图生图主流程：batch_size 个任务交给 BatchGenerationRunner 并发。"""
        prompt = str(kwargs.get("prompt") or "")
        api_key = str(kwargs.get("api_key") or "")
        api_base_url = str(kwargs.get("api_base_url") or "")
        batch_size = max(1, int(kwargs.get("batch_size") or 1))
        resolution = kwargs.get("分辨率(价格不同)", "1K")
        size_label = kwargs.get("size", "16:9")
        line_choice = str(kwargs.get("线路选择") or "线路1")
        bypass_proxy = bool(kwargs.get("绕过代理") or False)
        quick_function_value = str(kwargs.get("快捷功能") or QUICK_FUNCTION_NONE)
        model_choice = str(kwargs.get("模型选择") or "GPT Image 2")
        connected_prompt = kwargs.get("增强提示词输入")
        seed = kwargs.get("seed", -1)  # 仅用于 ComfyUI 工作流记录，不写入请求体

        # 上游文本（forceInput）优先；未连接时用节点内提示词框（spec §3.1）
        base_prompt = str(connected_prompt) if str(connected_prompt or "").strip() else prompt
        base_prompt = base_prompt.strip()
        if not base_prompt:
            raise ValueError("请输入提示词")

        # 快捷功能拼接（spec §3.5：PREFIXES + 导演/黑白故事板 PREFIX/SUFFIX）
        final_prompt_text = self._compose_quick_function_prompt(
            base_prompt, quick_function_value
        )

        # 输入图（可选 image_1..image_9；包装层自动缩放默认关闭）
        input_tensors: List[Any] = [
            kwargs["image_%d" % index] for index in range(1, 10) if kwargs.get("image_%d" % index) is not None
        ]
        img2img = bool(input_tensors)

        api_key_value, api_base_url_value = self._resolve_key_and_url(api_key, api_base_url)

        tier = self._normalize_resolution(resolution)
        ratio_label = self._normalize_ratio_label(size_label)
        request_size = self._resolve_request_size(tier, ratio_label)
        mode = self._resolve_effective_img2img_endpoint_mode(line_choice, tier, img2img)
        request_model = self._resolve_request_model(model_choice, tier, img2img, line_choice)
        timeout_s = 300
        current_seed = int(seed) if isinstance(seed, (int, float)) else -1
        if current_seed < 0:
            current_seed = random.randint(0, 102400)

        logger.info(
            "TE GPT image 2 任务 | 模型: %s | 分辨率: %s | 实际尺寸: %s | 线路选择: %s | "
            "模式=%s | 批次数量: %d | 质量: %s | 背景: %s | 输出格式: %s | 种子: %d"
            % (
                request_model,
                tier,
                request_size,
                line_choice,
                mode,
                batch_size,
                _DEFAULT_QUALITY,
                _DEFAULT_BACKGROUND,
                _DEFAULT_OUTPUT_FORMAT,
                current_seed,
            )
        )

        context = {
            "final_prompt_text": final_prompt_text,
            "request_model": request_model,
            "request_size": request_size,
            "mode": mode,
            "input_tensors": input_tensors,
            "line_choice": line_choice,
            "api_key_value": api_key_value,
            "api_base_url_value": api_base_url_value,
            "bypass_proxy": bypass_proxy,
            "timeout_s": timeout_s,
        }

        tasks = [{"context": context, "task_index": index} for index in range(batch_size)]
        started = time.perf_counter()

        runner = BatchGenerationRunner(
            tasks=tasks,
            worker_fn=self._generate_single_image_gpt_image_2,
            batch_size=batch_size,
            continue_on_error=True,
            progress_bar=_make_comfy_progress_bar,
            logger=logger,
        )
        results = runner.run(
            ensure_not_interrupted=_ensure_not_interrupted,
            progress_bar=_make_comfy_progress_bar,
        )
        elapsed = time.perf_counter() - started

        # 聚合：成功槽收 tensor，失败槽 ErrorCanvas 错误图保证输出不断裂
        import torch  # 惰性导入

        decoded_tensors: List[Any] = []
        all_errors: List[str] = []
        total_generated_images = 0
        for task_index, result in enumerate(results):
            if result and result.get("tensors"):
                decoded_tensors.extend(result["tensors"])
                total_generated_images += len(result["tensors"])
            else:
                error_text = (result or {}).get("error") or "生成失败"
                all_errors.append("批次%d: %s" % (task_index + 1, error_text))
                decoded_tensors.append(
                    ERROR_CANVAS.build_error_tensor_from_text(
                        error_text, title="TE MAN GPT Image 2 请求错误"
                    )
                )

        if total_generated_images > 0:
            logger.success("成功生成 %d / 失败 %d，成功获取 %d 张图像" % (total_generated_images, len(all_errors), total_generated_images))
        else:
            logger.warning("生成失败 / 未生成任何图像")
        if all_errors:
            logger.error("Errors: " + " | ".join(all_errors))

        if decoded_tensors:
            images = decoded_tensors[0] if len(decoded_tensors) == 1 else torch.cat(decoded_tensors, dim=0)
        else:
            images = ERROR_CANVAS.build_error_tensor_from_text("未生成任何图像")

        avg_speed = (total_generated_images / elapsed) if elapsed > 0 else 0.0
        summary_lines = [
            "模型: %s" % request_model,
            "分辨率: %s" % tier,
            "实际尺寸: %s" % request_size,
            "线路选择: %s" % line_choice,
            "批次数量: %d" % batch_size,
            "成功生成 %d / 失败 %d，成功获取 %d 张图像" % (
                total_generated_images, len(all_errors), total_generated_images
            ),
            "总耗时: %.2fs，平均 %.2f 张/s" % (elapsed, avg_speed),
        ]
        if all_errors:
            summary_lines.append("Errors: " + " | ".join(all_errors))

        text = "\n".join(summary_lines)
        preview = IMAGE_CODEC.build_preview_tuple(images)
        if preview is not None:
            return {"ui": preview, "result": (images, text)}
        return (images, text)

    # ==================== 快捷功能拼接 ====================

    @staticmethod
    def _compose_quick_function_prompt(base_prompt: str, quick_function_value: str) -> str:
        """按选项组装 final_prompt_text（spec §3.5/§7.2 映射）。"""
        quick_prefix = QUICK_FUNCTION_PREFIXES.get(quick_function_value, "")
        if quick_function_value == QUICK_FUNCTION_DIRECTOR_STORYBOARD:
            # 导演故事板：PREFIX + 用户提示词 + SUFFIX
            return DIRECTOR_STORYBOARD_PROMPT_PREFIX + base_prompt + DIRECTOR_STORYBOARD_PROMPT_SUFFIX
        if quick_function_value == QUICK_FUNCTION_BLACK_WHITE_STORYBOARD:
            # 黑白素写故事板：用户提示词 + SUFFIX
            return base_prompt + BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX
        if quick_prefix:
            return quick_prefix + base_prompt
        return base_prompt

    # ==================== 失败结果（spec §3.6 _build_failure_result） ====================

    @staticmethod
    def _build_failure_result(error_text: str) -> Tuple[Any, str]:
        """失败结果：ErrorCanvas 错误图 + 错误文本（截断至展示上限）。"""
        display = _format_display_text(error_text)
        error_tensor = ERROR_CANVAS.build_error_tensor_from_text(
            display, title="TE MAN GPT Image 2 请求错误"
        )
        return error_tensor, display


NODE_CLASS_MAPPINGS = {'TE_image_pro_gpt_image_2': TEGPTImage2SafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_gpt_image_2': 'TE MAN GPT Image 2 & 2.5'}
