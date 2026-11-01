# -*- coding: utf-8 -*-
"""te_man_open · TE_MAN_Text_Tools

TE MAN Text文本处理节点：内置 OpenAI 兼容 Responses API 文本调用链，
把用户一句描述按 4 种「快捷功能」生成——扩写生图提示词、扩写生视频提示词、
9 段九宫格(3x3)分镜中文提示词、自定义命令处理。

实现依据 spec/TE_MAN_Text_Tools.md（含动态 introspection 回填节）：
- POST {base}/v1/responses，Authorization: Bearer，绕过代理时 Session.trust_env=False
- api_key/api_base_url 留空经 config_manager（config.ini [gemini]）回退
- 9 段分镜输出严格 JSON（grid_layout/grid_aspect_ratio/global_watermark/shots），
  grid_aspect_ratio 由「画面比例」注入系统指令模板
- requests 惰性导入；模块顶层只有标准库 + 本包支撑库
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from ..shared.config_manager import CONFIG_MANAGER
from ..shared.logger import logger

__all__ = [
    "TEMANTextToolsNode",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "QUICK_FUNCTION_OPTIONS",
    "MODULE_DIR",
    "PLUGIN_DIR",
]


# ==================== 模块常量（spec §7.2 实锤） ====================

QUICK_FUNCTION_STORYBOARD_9 = "9段分镜提示词"
QUICK_FUNCTION_IMAGE_PROMPT = "扩写生图提示词"
QUICK_FUNCTION_VIDEO_PROMPT = "扩写生视频提示词"
QUICK_FUNCTION_CUSTOM = "自定义"
#: 选项精确顺序（动态回填实锤）
QUICK_FUNCTION_OPTIONS = (
    QUICK_FUNCTION_STORYBOARD_9,
    QUICK_FUNCTION_IMAGE_PROMPT,
    QUICK_FUNCTION_VIDEO_PROMPT,
    QUICK_FUNCTION_CUSTOM,
)

#: 模块目录 = 插件根目录（config.ini 读取根，spec §7.2）
MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = MODULE_DIR

#: 画质词（_base_quality_tags 默认 style_hint="Cinematic" 的输出，spec §6 字面量）
_BASE_QUALITY_TAGS = "电影感光影，细节丰富，主体清晰，空间层次明确，画面统一，适合 AI 生图"

#: 默认参考画面比例分母（指令里的方向提示）
_DEFAULT_RATIO_HINT = "16:9"

#: JSON 代码围栏剥离正则（spec：`` ```(?:json)?\s*([\s\S]*?)\s*``` ``，IGNORECASE）
_CODE_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

#: 分镜号校验：分镜1 ~ 分镜9
_STORYBOARD_SHOT_RE = re.compile(r"^分镜([1-9])$")


# ==================== 系统指令（按 spec §6 节选原文拼装） ====================
# 说明：spec 只收录了关键片段（§6「系统指令要点(节选原文)」），全文未随二进制
# 逆向导出；此处按 spec 节选原文 + 硬性约束清单做功能等价还原，未确认句以
# spec 字面串为准，不做臆造扩写。

_IMAGE_PROMPT_INSTRUCTIONS = """你是一位拥有好莱坞级别审美的电影摄影指导兼高级文学创作者。你将收到一段简短的画面描述或剧情设定。请将其极度扩充并转化为极具“电影感（Cinematic）”的详尽画面描述文本，供 AI 文生图模型直接使用。

# 扩充方向准则（八维精细化脑补）
1.【人物基础设定】补全人物的年龄感、体型、姿态、表情、发型发色与气质。
2.【穿着与装饰】补全服装材质、层次、颜色、磨损与配饰细节。
3.【特定的物品/道具】补全关键道具的形态、材质、新旧与摆放方式。
4.【天气与空气感】补全天气、时间、空气中的颗粒、雾气、雨雪与温度感。
5.【详细背景与环境】补全场景层次：前景、中景、远景与空间纵深。
6.【构图与摄影机】明确景别、机位高度、镜头焦段感与透视关系。
7.【光影与色彩】明确主光方向、软硬、色温、对比与整体色彩倾向。
8.【画质与标签】补充画质词与风格标签。

# 输出结构（严格遵守）
只输出一篇字数在500字左右的中文详细扩充描述，不要输出任何解释、标题或代码围栏。描述末尾以「，风格：」引出风格提示（默认 Cinematic），并以画质标签收束：电影感光影，细节丰富，主体清晰，空间层次明确，画面统一，适合 AI 生图"""

_VIDEO_PROMPT_INSTRUCTIONS_TEMPLATE = """你是生视频提示词优化专家。请把用户输入优化成适合视频生成模型的提示词。
1. 保留主体和场景不变。
2. 明确动作过程、镜头运动、节奏、环境变化、光影变化。
3. 避免一次性塞入过多互相冲突的动作。
4. 输出语言：{output_language}"""

_STORYBOARD_INSTRUCTIONS_TEMPLATE = """你是九宫格(3x3)分镜提示词专家。
基于用户提供的简约提示词描述或参考图片，保持视觉锚点绝对不变，通过特定视角的强化组合，
生成 9 个 3x3 宫格分镜中文提示词。

# 视觉锁定
用户文本是固定视觉锚点 Base_Prompt：人物身份、服装、道具、场景与光影氛围在 9 个分镜中必须保持绝对一致，不得替换场景或改变主体设定。

# 特定镜头强化与随机排列
9 个分镜必须精确包含：2 背后 Back View / 2 过肩 Over-the-Shoulder / 2 POV / 2 正面 Front View / 1 自由高张力视角；严禁使用 Medium Shot、Long Shot、Close-up。
镜头变量库（每个分镜只允许从下列白名单组合中取值，不得自造词）：
- 景别：Full Shot / Medium Long Shot / Extreme Wide Shot / Insert Shot / Aerial Shot
- 视角：Back View / Over-the-Shoulder / POV / Front View / High Angle / Low Angle / Dutch Angle / Top-down / Worm's-eye View
- 构图：Rule of Thirds / Center Composition / Leading Lines / Foreground Framing / Negative Space / Symmetry
镜头组合随机排列，不要按固定顺序堆叠同组视角。

# 纯净 JSON 输出
只输出一个 JSON 对象，禁止输出解释文字、前言或代码围栏，结构严格如下：
{json_template}

# 硬性约束
- shots 数组精确包含 9 个对象，不得多也不得少。
- shot_number 依次为「分镜1」到「分镜9」，顺序不可打乱。
- 每个 prompt_text 必须为中文，并保留 Base_Prompt 的核心视觉锚点。"""

_STORYBOARD_JSON_TEMPLATE = """{
  "grid_layout": "3x3",
  "grid_aspect_ratio": "__GRID_ASPECT_RATIO__",
  "global_watermark": {
    "position": "bottom_center",
    "size": "small"
  },
  "shots": [
    {
      "shot_number": "分镜1",
      "prompt_text": "中文提示词"
    }
  ]
}"""

_CUSTOM_INSTRUCTIONS = "请严格按照用户输入开头的自定义命令处理后续文本。"

_NO_INPUT_USER_TEXT = "请根据当前快捷功能完成文本处理。"

_STORYBOARD_USER_TEXT_TEMPLATE = (
    "请将下面内容作为固定视觉锚点 Base_Prompt。"
    "每个 prompt_text 都必须保留这些核心视觉锚点并生成九宫格分镜。"
    "Base_Prompt: {base_prompt}"
)


# ==================== 模块级 helper（与 spec §2 函数族同名同责） ====================

def _ensure_not_interrupted() -> None:
    """ComfyUI 中断检测（comfy.model_management 惰性导入，非 ComfyUI 环境跳过）。"""
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001
        return
    throw = getattr(model_management, "throw_exception_if_processing_interrupted", None)
    if callable(throw):
        throw()
        return
    ensure = getattr(model_management, "ensure_not_interrupted", None)
    if callable(ensure):
        ensure()


def _resolve_responses_url(api_base_url: str) -> str:
    """把用户填的服务地址归一为 Responses 端点（支持填到域名、/v1、/v1/responses）。"""
    base = str(api_base_url or "").strip()
    if not base:
        raise RuntimeError("未配置有效的 API URL")
    if not re.match(r"^https?://", base, re.IGNORECASE):
        base = "https://" + base
    base = base.rstrip("/")
    lowered = base.lower()
    if lowered.endswith("/v1/responses"):
        return base
    if lowered.endswith("/responses"):
        return base[: -len("/responses")] + "/v1/responses"
    if lowered.endswith("/v1"):
        return base + "/responses"
    return base + "/v1/responses"


def _resolve_key_and_url(api_key: str, api_base_url: str) -> Tuple[str, str]:
    """节点值 → config_manager 回退链解析最终 key/url（spec §3 行为流步骤 2）。"""
    resolved_key = str(api_key or "").strip()
    if not resolved_key:
        resolved_key = CONFIG_MANAGER.load_api_key() or ""
        if not resolved_key:
            raise RuntimeError("请在 config.ini 中配置 API Key 或在节点中填写")
    resolved_base_url = str(api_base_url or "").strip()
    if not resolved_base_url:
        resolved_base_url = CONFIG_MANAGER.get_effective_api_base_url() or ""
        if not resolved_base_url:
            raise RuntimeError("请在 config.ini 中配置 API URL 或在节点中填写")
    return resolved_key, resolved_base_url


def _read_json_response_or_raise(resp: Any) -> Dict[str, Any]:
    """解析 HTTP JSON 响应；非 2xx / 非 JSON 按 spec §5 文案报错。"""
    status_code = getattr(resp, "status_code", 0)
    try:
        body = resp.text or ""
    except Exception:  # noqa: BLE001
        body = ""
    if not (200 <= int(status_code) < 300):
        excerpt = body if body else "<empty body>"
        raise RuntimeError(f"Responses API 请求失败：HTTP {status_code}，Body: {excerpt}")
    try:
        return resp.json()
    except Exception:  # noqa: BLE001
        raise RuntimeError(f"Responses API 返回的不是 JSON：{body}")


def _extract_output_text(response_data: Any) -> str:
    """从 Responses 结构提取文本：output[].content[].text（type=output_text），兼容
    顶层 output_text 与 Chat 兼容 choices[].message.content。"""
    try:
        chunks: List[str] = []
        for item in response_data.get("output") or []:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        text = part.get("text")
                        if isinstance(text, str) and text:
                            if part.get("type") in (None, "output_text", "text"):
                                chunks.append(text)
            elif isinstance(item.get("text"), str) and item["text"]:
                chunks.append(item["text"])
        if chunks:
            return "".join(chunks)
        top = response_data.get("output_text")
        if isinstance(top, str) and top:
            return top
        if isinstance(top, list):
            joined = "".join(t for t in top if isinstance(t, str))
            if joined:
                return joined
        for choice in response_data.get("choices") or []:
            message = (choice or {}).get("message") or {}
            content = message.get("content")
            if isinstance(content, str) and content:
                return content
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Responses API 返回 JSON 结构异常：{exc}") from exc
    raise RuntimeError(
        f"Responses API 未返回可用文本：{json.dumps(response_data, ensure_ascii=False)[:500]}"
    )


def _strip_json_code_fence(text: str) -> str:
    """剥掉模型输出外层 ```json 围栏（spec 正则，IGNORECASE）。"""
    value = str(text or "").strip()
    match = _CODE_FENCE_RE.search(value)
    if match:
        return match.group(1).strip()
    return value


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """把文本解析为 JSON 对象；失败返回 None。"""
    value = str(text or "").strip()
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except Exception:  # noqa: BLE001
        # 容错：截取首个 { 到末个 } 再试一次
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(value[start : end + 1])
            except Exception:  # noqa: BLE001
                return None
        else:
            return None
    return parsed if isinstance(parsed, dict) else None


def _extract_storyboard_prompts(parsed: Dict[str, Any]) -> List[str]:
    """读取 shots[].prompt_text，校验分镜1~分镜9，输出 9 条中文分镜提示词。"""
    shots = parsed.get("shots")
    if not isinstance(shots, list):
        raise ValueError("9段分镜结果解析失败：缺少 shots 数组")
    prompts: Dict[int, str] = {}
    for shot in shots:
        if not isinstance(shot, dict):
            continue
        shot_number = str(shot.get("shot_number") or "").strip()
        match = _STORYBOARD_SHOT_RE.match(shot_number)
        if not match:
            continue
        text = str(shot.get("prompt_text") or "").strip()
        if text:
            prompts[int(match.group(1))] = text
    missing = [str(i) for i in range(1, 10) if i not in prompts]
    if missing:
        raise ValueError(f"9段分镜结果解析失败：缺少分镜 {'、'.join(missing)} 的 prompt_text")
    return [prompts[i] for i in range(1, 10)]


def _pretty_json(parsed: Dict[str, Any]) -> str:
    """可展示 JSON 字符串（indent=2 + ensure_ascii=False，spec 实锤符号）。"""
    return json.dumps(parsed, indent=2, ensure_ascii=False)


def _base_quality_tags(style_hint: str = "Cinematic") -> str:
    """画质标签（spec §6 字面量 + 「，风格：」前缀约定）。"""
    return f"，风格：{style_hint}。{_BASE_QUALITY_TAGS}"


def _build_image_prompt_instructions(output_language: str) -> str:
    """扩写生图提示词系统指令（八维精细化脑补，spec §6 节选原文拼装）。

    ``output_language`` 仅为签名对齐；扩写生图固定输出 500 字左右的中文详述。
    """
    del output_language
    return _IMAGE_PROMPT_INSTRUCTIONS


def _build_video_prompt_instructions(output_language: str) -> str:
    """扩写生视频提示词系统指令（spec §6 原文四条）。"""
    return _VIDEO_PROMPT_INSTRUCTIONS_TEMPLATE.format(output_language=output_language)


def _build_storyboard_instructions(aspect_ratio: str) -> str:
    """9 段分镜系统指令；grid_aspect_ratio 由「画面比例」注入 JSON 模板。"""
    template = _STORYBOARD_JSON_TEMPLATE.replace(
        "__GRID_ASPECT_RATIO__", str(aspect_ratio or _DEFAULT_RATIO_HINT)
    )
    return _STORYBOARD_INSTRUCTIONS_TEMPLATE.format(json_template=template)


def _build_instructions(quick_function: str, aspect_ratio: str, output_language: str) -> str:
    """按快捷功能分发系统指令（spec §3 行为流步骤 4）。"""
    if quick_function == QUICK_FUNCTION_STORYBOARD_9:
        return _build_storyboard_instructions(aspect_ratio)
    if quick_function == QUICK_FUNCTION_IMAGE_PROMPT:
        return _build_image_prompt_instructions(output_language)
    if quick_function == QUICK_FUNCTION_VIDEO_PROMPT:
        return _build_video_prompt_instructions(output_language)
    return _CUSTOM_INSTRUCTIONS


def _build_user_text(input_text: str, custom_command: str, quick_function: str) -> str:
    """组装用户文本：自定义命令加最前；9 分镜附加 Base_Prompt 锚点行（spec 步骤 5）。"""
    body = str(input_text or "").strip()
    command = str(custom_command or "").strip()
    if quick_function == QUICK_FUNCTION_STORYBOARD_9:
        if body:
            body = _STORYBOARD_USER_TEXT_TEMPLATE.format(base_prompt=body)
        else:
            body = _STORYBOARD_USER_TEXT_TEMPLATE.format(base_prompt=_NO_INPUT_USER_TEXT)
    if command:
        return command + "\n" + body if body else command
    if body:
        return body
    return _NO_INPUT_USER_TEXT


def _build_responses_payload(
    model: str,
    instructions: str,
    user_text: str,
    max_output_tokens: int,
    temperature: float,
) -> Dict[str, Any]:
    """Responses API 请求体（seed 明确不进请求体，spec 步骤 6）。"""
    model_name = str(model or "").strip()
    if not model_name:
        raise ValueError("请填写 model")
    return {
        "model": model_name,
        "instructions": instructions,
        "input": user_text,
        "temperature": float(temperature),
        "max_output_tokens": int(max_output_tokens),
    }


def _post_responses(
    endpoint: str,
    payload: Dict[str, Any],
    timeout_s: int,
    api_key: str,
    bypass_proxy: bool = False,
) -> Dict[str, Any]:
    """POST {base}/v1/responses（Session + Bearer；绕过代理时 trust_env=False）。"""
    import requests  # 惰性导入

    session = requests.Session()
    try:
        if bypass_proxy:
            session.trust_env = False
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        logger.info(
            f"TE MAN Text文本处理: function={payload.get('_function', '')}, "
            f"model={payload.get('model', '')}, endpoint={endpoint}, "
            f"Body: {json.dumps({k: v for k, v in payload.items() if k != '_function'}, ensure_ascii=False)}"
        )
        resp = session.post(endpoint, headers=headers, json=payload, timeout=max(1, int(timeout_s)))
        return _read_json_response_or_raise(resp)
    finally:
        try:
            session.close()
        except Exception:  # noqa: BLE001
            pass


# ==================== 节点 ====================

class TEMANTextToolsNode:
    """TE MAN Text文本处理

    注册名: TE_image_pro_text_tools
    规格:   spec/TE_MAN_Text_Tools.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Text'
    FUNCTION = 'process_text'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING', 'STRING')
    RETURN_NAMES = ('text', 'json')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入文本': ('STRING', {'multiline': True, 'default': '一个穿红色旗袍的女性站在雨夜霓虹街道，手持折扇，电影感光影', 'tooltip': '输入剧情、简短提示词或需要处理的文本'}), '快捷功能': (('9段分镜提示词', '扩写生图提示词', '扩写生视频提示词', '自定义'), {'default': '9段分镜提示词', 'tooltip': '选择要执行的一次性文本处理功能'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses'}), 'model': ('STRING', {'default': 'gpt-5.5', 'multiline': False, 'tooltip': 'Responses API 模型名称，按你的中转/服务端支持填写'}), '画面比例': (('16:9', '9:16', '1:1', '4:3', '3:4', '4:5', '5:4', '21:9', '9:21'), {'default': '16:9', 'tooltip': '主要用于 9段分镜 的 grid_aspect_ratio 和提示词方向'}), '输出语言': (('中文', 'English'), {'default': '中文', 'tooltip': '控制非 9 段分镜功能的输出语言；9 段分镜固定中文'}), 'max_output_tokens': ('INT', {'default': 4096, 'min': 256, 'max': 32768, 'step': 256, 'tooltip': '最大输出 token，9段分镜建议 4096 或更高'}), 'temperature': ('FLOAT', {'default': 0.7, 'min': 0.0, 'max': 2.0, 'step': 0.05, 'tooltip': '创意程度；如果服务端模型不支持，可调回默认或更低'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 2147483647, 'control_after_generate': True, 'tooltip': '仅用于 ComfyUI 触发重新执行，不会写入请求体'}), 'timeout_s': ('INT', {'default': 300, 'min': 30, 'max': 1800, 'tooltip': '请求超时时间（秒）'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'}), '快捷功能自定义': ('STRING', {'forceInput': True, 'tooltip': '快捷功能选择“自定义”时生效；输入内容会添加到用户提示词前面'})}}
        # --8<-- 契约结束 --8<--

    def process_text(self, **kwargs):
        """按「快捷功能」经 OpenAI 兼容 Responses API 处理文本。

        返回 (text, json)：
        - 9段分镜：text = 9 条中文分镜提示词（换行拼接），json = 完整 JSON（indent=2）
        - 其余功能：text = 模型输出文本，json = 解析出的 JSON 对象串（未解析出为 ""）
        """
        _ensure_not_interrupted()

        input_text = str(kwargs.get('输入文本') or '')
        quick_function = str(kwargs.get('快捷功能') or QUICK_FUNCTION_STORYBOARD_9)
        if quick_function not in QUICK_FUNCTION_OPTIONS:
            quick_function = QUICK_FUNCTION_STORYBOARD_9
        aspect_ratio = str(kwargs.get('画面比例') or _DEFAULT_RATIO_HINT)
        output_language = str(kwargs.get('输出语言') or '中文')
        model = str(kwargs.get('model') or '')
        max_output_tokens = int(kwargs.get('max_output_tokens') or 4096)
        temperature = float(kwargs.get('temperature') or 0.7)
        timeout_s = int(kwargs.get('timeout_s') or 300)
        bypass_proxy = bool(kwargs.get('绕过代理') or False)
        custom_command = str(kwargs.get('快捷功能自定义') or '').strip()

        # 自定义功能必须接自定义命令（spec §5 文案）
        if quick_function == QUICK_FUNCTION_CUSTOM and not custom_command:
            raise ValueError(
                "快捷功能选择“自定义”时，请连接“快捷功能自定义”并输入自定义命令"
            )

        # key/url 解析（config_manager 回退链）
        api_key, api_base_url = _resolve_key_and_url(
            str(kwargs.get('api_key') or ''), str(kwargs.get('api_base_url') or '')
        )
        endpoint = _resolve_responses_url(api_base_url)

        # 系统指令 + 用户文本 + 请求体
        instructions = _build_instructions(quick_function, aspect_ratio, output_language)
        user_text = _build_user_text(input_text, custom_command, quick_function)
        payload = _build_responses_payload(
            model, instructions, user_text, max_output_tokens, temperature
        )
        payload['_function'] = quick_function  # 仅用于日志，见 _post_responses

        response_data = _post_responses(endpoint, payload, timeout_s, api_key, bypass_proxy)

        # 文本后处理：剥围栏 → 解析 JSON
        output_text = _strip_json_code_fence(_extract_output_text(response_data))
        parsed = _parse_json_object(output_text)

        if quick_function == QUICK_FUNCTION_STORYBOARD_9:
            # 仅 9 分镜走逐条提取；解析失败时回退纯文本输出
            try:
                storyboard = (
                    _extract_storyboard_prompts(parsed)
                    if parsed is not None
                    else [line for line in (s.strip() for s in output_text.splitlines()) if line][:9]
                )
            except ValueError:
                storyboard = []
            if storyboard:
                text_output = "\n\n".join(storyboard)
                json_output = _pretty_json(parsed) if parsed is not None else output_text
            else:
                text_output = output_text
                json_output = output_text
        else:
            text_output = output_text
            json_output = _pretty_json(parsed) if parsed is not None else ""

        logger.success(
            f"TE MAN Text文本处理: 完成 function={quick_function}, "
            f"输出长度={len(text_output)}"
        )
        return (text_output, json_output)


NODE_CLASS_MAPPINGS = {'TE_image_pro_text_tools': TEMANTextToolsNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_text_tools': 'TE MAN Text文本处理'}
