# -*- coding: utf-8 -*-
"""te_man_open · TE_Qwen_Image_2_1_Prompt_Enhancer

TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)：对 Qwen Image 2.1 的
文生图/图生图提示词做增强，三条链路——

- API：OpenAI 兼容 chat 接口（/v1/chat/completions，兼容 /v1/responses），
  api_key 留空读 config.ini，对 api.deepseek.com / teynex.com 特判端点
- 本地官方PE：comfy.sd.load_clip 加载 models/text_encoders 的 PE 模型
  （comfy/folder_paths 惰性导入，ComfyUI 不可用时抛中文错误）
- 本地（LLaMA）：llama-cpp-python 加载 models/LLM 的 GGUF + mmproj
  （llama_cpp 惰性导入，未安装时抛中文错误指明 pip install llama-cpp-python）

两套 Qwen 官方提示词工程系统提示词（文生图版 + 图生图编辑版）：spec 只收录了
标题行与结构要点（§6.4），原文全文未随逆向导出，此处为功能等价模板，
**待与官方 PE 模板校准**（文件内已标注）。

实现依据 spec/TE_Qwen_Image_2_1_Prompt_Enhancer.md（含动态回填节）：
- rewritten_prompt JSON 协议解析为纯文本；单输出 (增强提示词,)
- 最大生成token 4096 / 上下文长度 8192 / seed control_after_generate
- 生成后自动卸载模型（本地模式 unload/释放，官方 PE 走
  comfy.model_management.unload_all/soft_empty_cache 兼容路径）
- torch/numpy/PIL/requests/llama_cpp/comfy 系全部函数内惰性导入；
  模块顶层只有标准库 + 本包支撑库
"""

import base64
import gc
import hashlib
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from ..shared.config_manager import CONFIG_MANAGER
from ..shared.logger import logger

__all__ = [
    "TEQwenImage21PromptEnhancer",
    "NODE_CLASS_MAPPINGS",
    "NODE_DISPLAY_NAME_MAPPINGS",
    "DEFAULT_API_BASE_URL",
    "DEFAULT_API_MODEL",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_CONTEXT_LENGTH",
]

# ==================== 模块常量（spec §7.2 实锤值） ====================

DEFAULT_API_BASE_URL = "https://teynex.com"
DEFAULT_API_MODEL = "deepseek-v4.1-flash"
DEFAULT_MAX_OUTPUT_TOKENS = 4096
DEFAULT_CONTEXT_LENGTH = 8192
DEFAULT_IMAGE_MAX_EDGE = 2048
DEFAULT_IMAGE_MAX_PIXELS = 1048576

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.dirname(MODULE_DIR)

_MODE_TEXT2IMAGE = "文生图"
_MODE_IMAGE2IMAGE = "图生图"
_METHOD_LOCAL = "本地"
_METHOD_OFFICIAL_PE = "本地官方PE"
_METHOD_API = "API"
_MODE_MMPROJ_NONE = "无"

_MODEL_EXTENSIONS = (".gguf", ".safetensors", ".pt", ".pth", ".bin")
_MMPROJ_EXTENSIONS = (".gguf", ".bin", ".safetensors")

#: GGUF 分片校验正则（spec §6.5 原文）
_GGUF_SHARD_RE = re.compile(
    r"^(?P<prefix>.+)-(?P<index>\d{5})-of-(?P<total>\d{5})(?P<extension>\.gguf)$"
)

_CODE_FENCE_RE = re.compile(r"```(?:json|text|markdown)?\s*([\s\S]*?)\s*```", re.IGNORECASE)

# spec §3.2 步骤 3：剔除两套系统提示词间冲突小节的正则（原文摘录）
_CONFLICT_LANG_RULES = [
    re.compile(r"\n\*\*FIRST — there are TWO separate language decisions\.[\s\S]*?(?=\n#|\n## Output [Ff]ormat|\Z)"),
    re.compile(r"\n## Language\n[\s\S]*?(?=\n## Output [Ff]ormat|\n#|\Z)"),
]

# ==================== Qwen 官方提示词工程系统提示词 ====================
# spec §6.4 仅收录标题行「# Image Prompt Rewriting Expert」「# Edit Prompt
# Enhancer — General (v2, 精简版)」、输出 JSON 协议
# {"rewritten_prompt": ..., "wh_ratio": ...} 与若干规则要点；
# 原文全文未随逆向导出 —— 以下为功能等价还原，**待与官方 PE 模板校准**。

QWEN_T2I_SYSTEM_PROMPT = """# Image Prompt Rewriting Expert

You turn a user's image request into one long, richly detailed paragraph that a text-to-image model can render directly.

## Rules
1. Keep the user's subject, scene and intent unchanged; never invent a different story.
2. Expand with concrete visual detail: subject appearance, clothing, pose, props, environment layers (foreground / midground / background), weather and air feel, composition and camera, light direction and color palette.
3. Describe motion-free still-image qualities only (no multi-beat actions, no timeline).
4. Do not add plot, dialogue, or meta commentary.
5. Keep any text the user wants visible in the image inside English double quotes, verbatim.
6. Keep proper nouns and brand names verbatim.

## Output format
Respond with ONLY one JSON object and nothing else:
{"rewritten_prompt": "<the description>", "wh_ratio": "<e.g. 3:2>"}
- rewritten_prompt: one long paragraph in the language selected by the node.
- wh_ratio: the aspect ratio you infer from the request, formatted "w:h" (e.g. "16:9", "3:2"); use "1:1" when unclear."""

QWEN_EDIT_SYSTEM_PROMPT = """# Edit Prompt Enhancer — General (v2, 精简版)

You rewrite a user's image-editing request into one precise instruction paragraph for an image editing model that receives one or more reference images.

## Rules
1. Keep the user's edit intent exactly; describe the expected visible result, not the procedure.
2. Anchor each change to a reference image with <image1> / <image2> / ... markers when multiple images are provided (the main image is <image1>).
3. State what must stay unchanged (identity, layout, style) as explicitly as what must change.
4. Resolve ambiguous pronouns into concrete nouns; never reference "the image" without a marker.
5. Keep any text the user wants visible in the image inside English double quotes, verbatim.
6. Do not add meta commentary, options, or explanations.

## Ratio decision
- If the user asks to keep the original framing, set "ratio_follow": true and copy the input ratio into "wh_ratio".
- If the user asks for a new aspect ratio, set "ratio_follow": false and put the requested ratio in "wh_ratio".
- Exactly one of the two states must hold; never output both or neither.

## Output format
Respond with ONLY one JSON object and nothing else:
{"rewritten_prompt": "<the description>", "wh_ratio": "<e.g. 3:2>", "ratio_follow": "<true|false>"}"""

QWEN_OUTPUT_POLICY = """# Node output controls
- 节点选择的输出语言是最终描述语言的最高依据，不要根据用户输入语言改变这个选择。
- 不发明用户未给定的画面文字；用户要求显示在图片中的文字保持原文。
- 只输出纯文本结果：禁止思维链、禁止解释、禁止代码围栏、禁止在 JSON 之外输出任何字符。"""

QWEN_OFFICIAL_PE_POLICY = """## Official PE output protocol
- The official PE model still emits JSON internally; the node extracts `rewritten_prompt` only.
- 除 rewritten_prompt 外的内部字段（wh_ratio / ratio_follow 等）由节点消化，不得出现在最终输出中。"""

# 语言强化句（spec §3.2 步骤 3：末尾按输出语言追加，句式为 spec 原文）
_LANG_RULE_CN = (
    "最终语言规则（优先级最高）：节点选择的输出语言是“中文”。"
    "除用户明确要求显示在图片中的文字、专有名词和品牌名外，最终提示词的全部描述性文字必须使用“中文”。"
)
_LANG_RULE_EN = (
    "The selected output language is English. All descriptive text of the final prompt must be "
    "written in English, except user-requested visible text, proper nouns and brand names. "
    "Stop immediately after closing the JSON object."
)


# ==================== 系统提示词组装 ====================

def _build_system_prompt(
    base_prompt: str,
    output_language: str,
    method: str,
) -> str:
    """按 spec §3.2 步骤 3 组装系统提示词：基底 + 去冲突 + 输出策略 + 语言强化句。"""
    prompt = base_prompt
    for pattern in _CONFLICT_LANG_RULES:
        prompt = pattern.sub("", prompt)
    parts = [prompt.strip(), QWEN_OUTPUT_POLICY.strip()]
    if method == _METHOD_OFFICIAL_PE:
        parts.append(QWEN_OFFICIAL_PE_POLICY.strip())
    if str(output_language) == "英文":
        parts.append(_LANG_RULE_EN)
    else:
        parts.append(_LANG_RULE_CN)
    return "\n\n".join(p for p in parts if p)


# ==================== 通用小工具 ====================

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


def _normalize_seed(seed_value: Any) -> int:
    """seed 归一：负值回退 0（本地模式使用，API 不发送）。"""
    try:
        value = int(seed_value)
    except (TypeError, ValueError):
        return 0
    return value if value >= 0 else 0


def _settings_signature(values: Tuple[Any, ...]) -> str:
    """设置指纹（sha256 hexdigest），用于日志 settings_sha256 与缓存复用判定。"""
    digest = hashlib.sha256()
    for value in values:
        digest.update(repr(value).encode("utf-8", "replace"))
        digest.update(b"\x00")
    return digest.hexdigest()


def _strip_code_fence(text: str) -> str:
    """剥掉模型输出外层代码围栏（spec：```(?:json|text|markdown)?...）。"""
    value = str(text or "").strip()
    match = _CODE_FENCE_RE.search(value)
    if match:
        return match.group(1).strip()
    return value


def _clean_think_blocks(text: str) -> str:
    """清理思考块（spec §3.2 步骤 5 的正则族）。"""
    value = str(text or "")
    patterns = (
        re.compile(r"<think\b[^>]*>[\s\S]*?</think>", re.IGNORECASE),
        re.compile(r"<think\b[^>]*>.*$", re.IGNORECASE | re.DOTALL),
        re.compile(r"<思考>[\s\S]*?</思考>"),
        re.compile(r"```thinking\b[\s\S]*?```", re.IGNORECASE),
        re.compile(r"```thought\b[\s\S]*?```", re.IGNORECASE),
    )
    for pattern in patterns:
        value = pattern.sub("", value)
    return value.strip()


def _parse_result(text: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """解析 rewritten_prompt JSON 协议，返回 (纯文本提示词, 解析出的 JSON 或 None)。

    失败/为空时回退到原文纯文本（spec §3.2 步骤 5）。
    """
    value = _clean_think_blocks(str(text or ""))
    candidate = _strip_code_fence(value)
    parsed: Optional[Dict[str, Any]] = None
    try:
        loaded = json.loads(candidate)
        if isinstance(loaded, dict):
            parsed = loaded
    except Exception:  # noqa: BLE001
        start, end = candidate.find("{"), candidate.rfind("}")
        if start >= 0 and end > start:
            try:
                loaded = json.loads(candidate[start : end + 1])
                if isinstance(loaded, dict):
                    parsed = loaded
            except Exception:  # noqa: BLE001
                parsed = None
    if parsed is not None:
        prompt = str(parsed.get("rewritten_prompt") or "").strip()
        if prompt:
            return prompt, parsed
    fallback = candidate.strip() or value.strip()
    return fallback, None


def _detect_model_family(model_name: str) -> str:
    """识别 qwen3.5/3.6/3.8 及 VL 变体（spec §2）。"""
    name = str(model_name or "").lower()
    family = "other"
    if "3.8" in name or "qwen3_8" in name:
        family = "qwen3.8"
    elif "3.6" in name or "qwen3_6" in name:
        family = "qwen3.6"
    elif "3.5" in name or "qwen3_5" in name:
        family = "qwen3.5"
    is_vl = "vl" in name.replace(".vl", "-vl") or "-vl" in name or "vision" in name
    return f"{family}{'-VL' if is_vl else ''}"


def _validate_gguf_shards(file_path: str) -> None:
    """GGUF 分片校验（spec §3.2 步骤 4 / §5 文案）。"""
    name = os.path.basename(file_path)
    match = _GGUF_SHARD_RE.match(name)
    if not match:
        return
    index, total = int(match.group("index")), int(match.group("total"))
    if index != 1:
        raise RuntimeError(
            f"选中了 GGUF 的第 {index} 个分片。请选择第一片："
            f"{match.group('prefix')}-00001-of-{match.group('total')}.gguf"
        )
    directory = os.path.dirname(file_path)
    missing = []
    for i in range(1, total + 1):
        shard = os.path.join(
            directory, f"{match.group('prefix')}-{i:05d}-of-{total:05d}{match.group('extension')}"
        )
        if not os.path.exists(shard):
            missing.append(os.path.basename(shard))
    if missing:
        raise RuntimeError(
            f"GGUF 分片不完整（共 {total} 个分片）。缺少分片：{'、'.join(missing)}"
        )


def _image_to_jpeg_base64(image: Any, max_edge: int = DEFAULT_IMAGE_MAX_EDGE) -> str:
    """ComfyUI IMAGE 张量 → JPEG base64 data URL（LANCZOS 缩放限边限像素）。"""
    import numpy as np  # 惰性导入
    from PIL import Image  # 惰性导入

    array = image
    if hasattr(image, "unsqueeze"):  # torch tensor: (H, W, C)
        array = image.unsqueeze(0).detach().cpu().float().numpy()
    elif hasattr(image, "detach"):
        array = image.detach().cpu().float().numpy()
    elif hasattr(image, "cpu"):
        array = image.cpu().float().numpy()
    array = np.asarray(array, dtype="float32")
    array = np.clip(array[0] if array.ndim == 4 else array, 0.0, 1.0)
    pil = Image.fromarray((array * 255.0).round().astype("uint8")).convert("RGB")

    width, height = pil.size
    scale = min(1.0, max_edge / max(width, height))
    if width * height > DEFAULT_IMAGE_MAX_PIXELS:
        scale = min(scale, (DEFAULT_IMAGE_MAX_PIXELS / float(width * height)) ** 0.5)
    if scale < 1.0:
        try:
            resample = Image.Resampling.LANCZOS
        except AttributeError:  # noqa: BLE001  旧版 Pillow
            resample = Image.LANCZOS
        pil = pil.resize((max(1, int(width * scale)), max(1, int(height * scale))), resample)

    buffer = io.BytesIO()
    pil.save(buffer, format="JPEG", quality=92)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _collect_image_data_urls(kwargs: Dict[str, Any]) -> List[str]:
    """收集 图生图 8 路图片输入 → JPEG base64 data URL 列表。"""
    keys = ("图片",) + tuple(f"图片{i}" for i in range(2, 9))
    data_urls: List[str] = []
    for key in keys:
        tensor = kwargs.get(key)
        if tensor is None:
            continue
        try:
            batch = tensor.shape[0] if hasattr(tensor, "shape") else 1
        except Exception:  # noqa: BLE001
            batch = 1
        for i in range(int(batch or 1)):
            item = tensor[i] if batch > 1 else tensor
            data_urls.append(_image_to_jpeg_base64(item))
    return data_urls


# ==================== API 端点/认证解析 ====================

def _resolve_api_key(api_key: str) -> str:
    """API Key：节点值优先，留空读 config.ini（经 sanitize 去空白与占位符）。"""
    key = str(api_key or "").strip()
    if not key:
        key = CONFIG_MANAGER.load_api_key() or ""
    if not key:
        raise RuntimeError("请在节点中填写 API Key，或在 config.ini 中配置 API Key")
    return key


def _normalize_base_url(api_base_url: str) -> str:
    base = str(api_base_url or "").strip()
    if not base:
        raise RuntimeError("未配置有效的 API URL")
    if not re.match(r"^https?://", base, re.IGNORECASE):
        base = "https://" + base
    return base.rstrip("/")


def _resolve_api_url_candidates(api_base_url: str) -> List[str]:
    """端点候选归一（spec：/v1/chat/completions 与 /v1/responses、/responses 候选；
    对 api.deepseek.com、https://teynex.com 特判 —— 具体规则 spec 标注未确认，
    此处按主机语义实现：DeepSeek 官方站走 /openai/v1/chat/completions，teynex 中转
    先 /v1/chat/completions 后 /v1/responses，其余站两种端点都作候选）。"""
    base = _normalize_base_url(api_base_url)
    lowered = base.lower()
    if lowered.endswith("/chat/completions"):
        return [base]
    if lowered.endswith(("/v1/responses", "/responses")):
        responses = base if lowered.endswith("/v1/responses") else base[: -len("/responses")] + "/v1/responses"
        return [responses]
    host = (urlsplit(base + "/").netloc or "").lower()
    path = (urlsplit(base + "/").path or "").rstrip("/")
    has_version = bool(re.search(r"/v\d+$", path))
    if "api.deepseek.com" in host:
        candidates = [base + "/chat/completions", base + "/v1/chat/completions"]
        if "/openai" not in lowered:
            stripped = re.sub(r"/v\d+$", "", base)
            candidates.insert(0, stripped + "/openai/v1/chat/completions")
        return candidates
    if "teynex.com" in host:
        return [base + "/v1/chat/completions", base + "/v1/responses"]
    if has_version:
        candidates = [base + "/chat/completions", base + "/responses"]
    else:
        candidates = [base + "/v1/chat/completions", base + "/v1/responses", base + "/chat/completions"]
    return candidates


def _extract_response_text(data: Any) -> str:
    """从 chat / responses 双协议提取文本（read_content 局部名与 spec 对应）。"""
    chunks: List[str] = []

    def read_content(content: Any) -> None:
        if isinstance(content, str) and content:
            chunks.append(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str) and text:
                        chunks.append(text)

    for choice in data.get("choices") or []:
        read_content((choice or {}).get("message", {}).get("content"))
    if chunks:
        return "".join(chunks)
    top = data.get("output_text")
    if isinstance(top, str) and top:
        return top
    for item in data.get("output") or []:
        if isinstance(item, dict):
            read_content(item.get("content"))
    if chunks:
        return "".join(chunks)
    return ""


def _request_api(
    endpoint_candidates: List[str],
    model: str,
    system_prompt: str,
    user_text: str,
    image_data_urls: List[str],
    timeout_s: int,
    api_key: str,
    bypass_proxy: bool,
) -> str:
    """API 分支：requests.post OpenAI 兼容 chat 接口（Bearer），404/405 时换下一候选。"""
    import requests  # 惰性导入

    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if image_data_urls:
        content: Any = [{"type": "text", "text": user_text}]
        for url in image_data_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_text})

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    body = {"model": model, "messages": messages}

    session = requests.Session()
    try:
        if bypass_proxy:
            session.trust_env = False
        last_status: Optional[int] = None
        last_body = ""
        for endpoint in endpoint_candidates:
            logger.info(
                f"TE Qwen Image 2.1 API generation starting model={model} "
                f"image_count={len(image_data_urls)} endpoint={endpoint}"
            )
            resp = session.post(endpoint, headers=headers, json=body, timeout=max(1, int(timeout_s)))
            status_code = int(getattr(resp, "status_code", 0) or 0)
            if status_code in (404, 405):
                last_status, last_body = status_code, (getattr(resp, "text", "") or "")[:300]
                continue
            if not (200 <= status_code < 300):
                raise RuntimeError(
                    f"API 调用失败 HTTP {status_code}，Body: {getattr(resp, 'text', '') or '<empty body>'}"
                )
            try:
                data = resp.json()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"API 返回格式异常：{getattr(resp, 'text', '') or '<empty body>'}") from exc
            output = _extract_response_text(data)
            if not output:
                raise RuntimeError("API 返回格式异常：响应中不含文本内容")
            logger.success(f"TE Qwen Image 2.1 API generation completed output=[{output[:80]}]")
            return output
        raise RuntimeError(f"API 调用失败 HTTP {last_status}，Body: {last_body or '<empty body>'}")
    finally:
        try:
            session.close()
        except Exception:  # noqa: BLE001
            pass


# ==================== 本地官方PE：全局缓存与卸载 ====================

class TEQwenImage21OfficialModel:
    """官方 PE 已加载模型包装（spec §2：dataclass 语义的轻量复刻）。"""

    def __init__(self, model: Any, extra_template_arguments: Optional[Dict[str, Any]] = None):
        self.model = model
        self.extra_template_arguments = extra_template_arguments or {}


class TEQwenImage21OfficialStorage:
    """「本地官方PE」模型的全局缓存与卸载（spec §2：类方法 load/unload）。"""

    _model: Optional[TEQwenImage21OfficialModel] = None
    _label: str = ""

    @classmethod
    def load(cls, pe_model: str, enable_thinking: bool) -> TEQwenImage21OfficialModel:
        """comfy.sd.load_clip 加载 models/text_encoders 的 PE 模型（惰性导入）。"""
        try:
            import folder_paths  # 惰性导入
            from comfy import sd as comfy_sd  # 惰性导入
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"本地官方PE 模式需要 ComfyUI 环境（comfy.sd / folder_paths）：{exc}"
            ) from exc

        from comfy.sd import CLIPType  # 惰性导入；类型枚举仅在 ComfyUI 内可用

        path = _resolve_pe_model_path(pe_model, "text_encoders")
        clip_type = getattr(CLIPType, "QWEN_IMAGE", None)
        if clip_type is None:
            raise RuntimeError("当前 ComfyUI 版本不支持 CLIPType.QWEN_IMAGE，无法加载官方 PE 模型")
        logger.info(f"TE Qwen Image 2.1 official PE loading model={pe_model}")
        clip = comfy_sd.load_clip(
            ckpt_paths=[path],
            embedding_directory=folder_paths.get_folder_paths("text_encoders"),
            clip_type=clip_type,
        )
        cls._model = TEQwenImage21OfficialModel(
            clip,
            {"enable_thinking": bool(enable_thinking)},
        )
        cls._label = pe_model
        logger.success(f"TE Qwen Image 2.1 official PE loaded model={pe_model}")
        return cls._model

    @classmethod
    def unload(cls) -> bool:
        """卸载官方 PE 模型并释放显存（unload_model_and_clones + soft_empty_cache 兼容路径）。"""
        if cls._model is None:
            logger.info("TE Qwen Image 2.1 official PE unload skipped: no model is loaded")
            return False
        try:
            from comfy import model_management  # 惰性导入

            unload = getattr(model_management, "unload_model_and_clones", None)
            if callable(unload):
                unload()
            unload_all = getattr(model_management, "unload_all_models", None)
            if callable(unload_all):
                unload_all()
            soft_empty_cache = getattr(model_management, "soft_empty_cache", None)
            if callable(soft_empty_cache):
                soft_empty_cache()
        except Exception:  # noqa: BLE001  非 ComfyUI 环境：尽力回收
            pass
        cls._model = None
        cls._label = ""
        gc.collect()
        logger.info("TE Qwen Image 2.1 official PE model unloaded")
        return True


def _resolve_pe_model_path(pe_model: str, folder: str) -> str:
    """把下拉选项解析为实际模型文件路径（找不到模型文件时报错）。"""
    import folder_paths  # 惰性导入

    name = str(pe_model or "").strip()
    if not name or name.startswith("（请把模型放到"):
        raise RuntimeError(
            "未找到官方 PE 模型，请把 qwen_image_2.1_pe 模型放到 models/text_encoders/。"
            "（请把模型放到 models/text_encoders）"
        )
    candidates = []
    for base in folder_paths.get_folder_paths(folder):
        candidates.append(os.path.join(base, name))
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    raise RuntimeError(f"找不到模型文件：{name}")


def _resolve_llm_model_path(model_label: str) -> str:
    """把主模型下拉选项解析为 models/LLM 下的实际文件路径。"""
    import folder_paths  # 惰性导入

    name = str(model_label or "").strip()
    if not name or name.startswith("（请把模型放到"):
        raise RuntimeError("未找到可用主模型，请把模型放到 ComfyUI/models/LLM/ 后重启。")
    for base in folder_paths.get_folder_paths("LLM"):
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate):
            return candidate
    raise RuntimeError(f"找不到模型文件：{name}")


def _resolve_mmproj_path(mmproj_label: str) -> str:
    """把 mmproj 下拉选项解析为实际文件路径。"""
    import folder_paths  # 惰性导入

    name = str(mmproj_label or "").strip()
    if not name or name == _MODE_MMPROJ_NONE or name.startswith("（请把模型放到"):
        raise RuntimeError("图生图需要选择对应的视觉投影文件")
    for base in folder_paths.get_folder_paths("LLM"):
        candidate = os.path.join(base, name)
        if os.path.isfile(candidate):
            return candidate
    raise RuntimeError(f"找不到 mmproj 文件：{name}")


def _request_official_pe(
    official: TEQwenImage21OfficialModel,
    system_prompt: str,
    user_text: str,
    image_data_urls: List[str],
    max_output_tokens: int,
    seed: int,
) -> str:
    """官方 PE 推理。

    原版在该分支的推理执行细节（如何在 ComfyUI CLIP 封装上完成对话生成）
    spec 标注未确认；此复刻采用保守策略：尝试经底层 torch 模型的 generate
    接口自回归生成，环境不具备时抛出中文错误说明。
    """
    import torch  # 惰性导入

    clip = official.model
    cond_stage = getattr(clip, "cond_stage_model", None)
    tokenizer = getattr(clip, "tokenizer", None)
    if cond_stage is None or tokenizer is None:
        raise RuntimeError("本地官方PE 推理失败：CLIP 封装缺少 cond_stage_model / tokenizer")

    messages_text = f"{system_prompt}\n\nUser: {user_text}\nAssistant:"
    try:
        tokens = tokenizer.tokenize(messages_text)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"本地官方PE tokenize 失败：{exc}") from exc

    input_ids = None
    if isinstance(tokens, dict):
        for value in tokens.values():
            if isinstance(value, dict):
                value = value.get("input_ids")
            if hasattr(value, "__getitem__"):
                try:
                    input_ids = value[0]
                    break
                except Exception:  # noqa: BLE001
                    continue
    if input_ids is None:
        raise RuntimeError("本地官方PE 推理失败：无法从 ComfyUI tokenizer 取得 input_ids")

    underlying = getattr(cond_stage, "model", cond_stage)
    generate = getattr(underlying, "generate", None)
    if not callable(generate):
        raise RuntimeError(
            "本地官方PE 推理在当前 ComfyUI 环境不可用：底层 Qwen 文本编码器未暴露 "
            "generate 自回归接口。请改用「本地」（LLaMA）或「API」增强方式。"
        )
    device = next(underlying.parameters()).device if hasattr(underlying, "parameters") else "cpu"
    if hasattr(torch, "manual_seed"):
        torch.manual_seed(int(seed))
    inputs = torch.as_tensor([list(input_ids)], device=device)
    with torch.no_grad():
        output_ids = generate(
            inputs,
            max_new_tokens=max(256, int(max_output_tokens)),
            do_sample=True,
            temperature=0.7,
            top_p=0.8,
            top_k=20,
        )
    new_tokens = output_ids[0][inputs.shape[1]:] if output_ids.shape[1] > inputs.shape[1] else output_ids[0]
    try:
        decode = getattr(underlying, "decode", None)
        if callable(decode):
            text = decode(new_tokens, skip_special_tokens=True)
        elif hasattr(tokenizer, "untokenize"):
            text = tokenizer.untokenize(new_tokens)
        else:
            text = ""
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"本地官方PE 解码失败：{exc}") from exc
    if isinstance(text, list):
        text = "".join(str(t) for t in text)
    if not text:
        raise RuntimeError("模型返回为空，可能只生成了思考内容但没有最终提示词。请提高最大生成token后重试。")
    return text


# ==================== 本地LLaMA：全局缓存与卸载 ====================

class TEQwenImage21LocalModel:
    """本地 llama 模型包装（Llama 实例 + mmproj 路径）。"""

    def __init__(self, llama: Any, model_path: str, mmproj_path: str = ""):
        self.llama = llama
        self.model_path = model_path
        self.mmproj_path = mmproj_path


class TEQwenImage21LocalStorage:
    """「本地LLaMA」llama model 的全局缓存与卸载（spec §2：类方法 load/unload）。"""

    _model: Optional[TEQwenImage21LocalModel] = None
    _label: str = ""

    @classmethod
    def _same_config(cls, model_path: str, mmproj_path: str, context_length: int) -> bool:
        if cls._model is None:
            return False
        return (
            cls._model.model_path == model_path
            and cls._model.mmproj_path == mmproj_path
            and getattr(cls._model.llama, "n_ctx", None) == int(context_length)
        )

    @classmethod
    def load(
        cls,
        model_label: str,
        mmproj_label: str,
        context_length: int,
        need_vision: bool,
    ) -> TEQwenImage21LocalModel:
        """llama-cpp-python 加载 GGUF（+mmproj）；分片校验与中文错误按 spec §5。"""
        try:
            from llama_cpp import Llama  # 惰性导入
        except Exception as exc:  # noqa: BLE001
            import sys

            raise RuntimeError(
                "未检测到 llama-cpp-python（llama_cpp），请先安装/更新该依赖："
                "pip install llama-cpp-python\n"
                f"原始导入错误：{exc}\n当前 Python：{sys.executable}"
            ) from exc

        model_path = _resolve_llm_model_path(model_label)
        _validate_gguf_shards(model_path)
        mmproj_path = ""
        if need_vision:
            if not mmproj_label or mmproj_label == _MODE_MMPROJ_NONE:
                raise RuntimeError("图生图模式需要选择 mmproj 视觉投影文件")
            mmproj_path = _resolve_mmproj_path(mmproj_label)
        elif mmproj_label and mmproj_label != _MODE_MMPROJ_NONE:
            mmproj_path = _resolve_mmproj_path(mmproj_label)

        if cls._same_config(model_path, mmproj_path, context_length):
            logger.info(f"TE Qwen Image 2.1 local model reusing model={model_label}")
            return cls._model

        cls.unload()
        logger.info(f"TE Qwen Image 2.1 local model loading model={model_label}")
        kwargs: Dict[str, Any] = {
            "model_path": model_path,
            "n_ctx": int(context_length),
            "n_gpu_layers": -1,
            "verbose": False,
        }
        if mmproj_path:
            kwargs["chat_handler"] = _create_multimodal_handler(mmproj_path)
        try:
            llama = Llama(**kwargs)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"加载本地模型失败：{exc}") from exc
        cls._model = TEQwenImage21LocalModel(llama, model_path, mmproj_path)
        cls._label = model_label
        logger.success(f"TE Qwen Image 2.1 local model loaded model={model_label}")
        return cls._model

    @classmethod
    def unload(cls) -> bool:
        """卸载本地 llama 模型并释放内存。"""
        had_model = cls._model is not None
        if cls._model is not None:
            logger.info(f"TE Qwen Image 2.1 local model unloading loaded={cls._label}")
            llama = cls._model.llama
            close = getattr(llama, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass
            del llama
            cls._model = None
            cls._label = ""
            gc.collect()
            logger.info("TE Qwen Image 2.1 local model unloaded")
        return had_model


def _create_multimodal_handler(mmproj_path: str) -> Any:
    """按 llama-cpp-python 能力挑选多模态 handler（spec §2 handler 工厂族）。"""
    import llama_cpp  # 惰性导入

    for attr in ("Qwen35ChatHandler", "Qwen3VLChatHandler", "Qwen25VLChatHandler", "Llava15ChatHandler"):
        handler_cls = getattr(llama_cpp, attr, None)
        if handler_cls is not None:
            try:
                return handler_cls(clip_model_path=mmproj_path, verbose=False)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(f"创建 {attr} 失败：{exc}") from exc
    raise RuntimeError(
        "当前 llama-cpp-python 不支持 Qwen35ChatHandler / Qwen3VLChatHandler / "
        "Qwen3.8 视觉聊天处理器 / Qwen3.8 聊天模板，请更新 llama-cpp-python。"
    )


def _request_local(
    local: TEQwenImage21LocalModel,
    system_prompt: str,
    user_text: str,
    image_data_urls: List[str],
    max_output_tokens: int,
    seed: int,
) -> str:
    """本地 LLaMA 推理：create_chat_completion（视觉输入以 image_url 载荷注入）。"""
    messages: List[Dict[str, Any]] = [{"role": "system", "content": system_prompt}]
    if image_data_urls:
        content: Any = [{"type": "text", "text": user_text}]
        for index, url in enumerate(image_data_urls, start=1):
            content.append({"type": "image_url", "image_url": {"url": url}})
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": user_text})
    try:
        output = local.llama.create_chat_completion(
            messages=messages,
            max_tokens=max(256, int(max_output_tokens)),
            temperature=0.7,
            top_p=0.8,
            top_k=20,
            min_p=0.0,
            seed=int(seed),
        )
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"本地模型推理失败：{exc}") from exc
    text = _extract_response_text(output if isinstance(output, dict) else {})
    if not text:
        raise RuntimeError("模型返回为空，可能只生成了思考内容但没有最终提示词。请提高最大生成token后重试。")
    return text


# ==================== 节点 ====================

class TEQwenImage21PromptEnhancer:
    """TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)

    注册名: TE_Qwen_Image_2_1_Prompt_Enhancer
    规格:   spec/TE_Qwen_Image_2_1_Prompt_Enhancer.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Prompt'
    FUNCTION = 'enhance_prompt'
    OUTPUT_NODE = True
    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('增强提示词',)

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'输入提示词': ('STRING', {'default': '', 'multiline': True, 'tooltip': '输入要增强的文生图或图生图需求。'}), '任务模式': (('文生图', '图生图'), {'default': '文生图'}), '输出语言': (('中文', '英文'), {'default': '中文', 'tooltip': '控制增强提示词的描述语言。用户明确要求的画面文字保持原文。'}), '增强方式': (('本地', '本地官方PE', 'API'), {'default': '本地'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空时读取 TE MAN 的 config.ini。'}), 'api_base_url': ('STRING', {'default': 'https://teynex.com', 'multiline': False}), 'model': ('STRING', {'default': 'deepseek-v4.1-flash', 'multiline': False}), '文生图PE模型': (('（请把模型放到 models/text_encoders）',), {'tooltip': '本地官方 PE 的文生图模型，增强方式选择本地官方PE且任务模式为文生图时生效。'}), '图生图PE模型': (('（请把模型放到 models/text_encoders）',), {'tooltip': '本地官方 PE 的图生图模型，增强方式选择本地官方PE且任务模式为图生图时生效。'}), '主模型': (('（请把模型放到 models/LLM）',), {'tooltip': '本地 Qwen 视觉模型，文件放在 ComfyUI/models/LLM/。'}), 'mmproj': (('无',), {'default': '无', 'tooltip': '图生图需要选择对应的视觉投影文件。'}), '最大生成token': ('INT', {'default': 4096, 'min': 256, 'max': 32768, 'step': 256, 'tooltip': '本地模型最大生成 token。API 模式不发送此限制。'}), '上下文长度': ('INT', {'default': 8192, 'min': 1024, 'max': 327680, 'step': 256, 'tooltip': '本地模型的 llama.cpp 上下文长度；数值越大通常占用越多显存。API 模式不使用此设置。'}), 'seed': ('INT', {'default': 0, 'min': 0, 'max': 18446744073709551615, 'step': 1, 'control_after_generate': True, 'tooltip': '本地模型随机种子。使用生成后控制可固定、递增、递减或随机化；API 模式不使用此设置。'}), '生成后自动卸载模型': ('BOOLEAN', {'default': False, 'tooltip': '本地生成完成后自动卸载 Qwen 模型并释放显存。'}), '启用思考': ('BOOLEAN', {'default': False, 'tooltip': '仅本地官方 PE 生效。开启后模型先进行思考再输出提示词；关闭后直接生成提示词。'})}, 'optional': {'图片': ('IMAGE', {'tooltip': '图生图参考图片。'}), '图片2': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片3': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片4': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片5': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片6': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片7': ('IMAGE', {'tooltip': '图生图附加参考图片。'}), '图片8': ('IMAGE', {'tooltip': '图生图附加参考图片。'})}}
        # --8<-- 契约结束 --8<--

    def enhance_prompt(self, **kwargs):
        """按「增强方式」三分支增强提示词，输出 rewritten_prompt 纯文本。"""
        user_text = str(kwargs.get('输入提示词') or '').strip()
        task_mode = str(kwargs.get('任务模式') or _MODE_TEXT2IMAGE)
        output_language = str(kwargs.get('输出语言') or '中文')
        method = str(kwargs.get('增强方式') or _METHOD_LOCAL)
        max_output_tokens = int(kwargs.get('最大生成token') or DEFAULT_MAX_OUTPUT_TOKENS)
        context_length = int(kwargs.get('上下文长度') or DEFAULT_CONTEXT_LENGTH)
        seed = _normalize_seed(kwargs.get('seed') or 0)
        auto_unload = bool(kwargs.get('生成后自动卸载模型') or False)
        enable_thinking = bool(kwargs.get('启用思考') or False)

        if not user_text:
            logger.info("TE Qwen Image 2.1 execute skipped: prompt is empty")
            return ("",)

        # 图生图校验 + 图片收集（主图 + 附加图，共 8 路）
        image_data_urls: List[str] = []
        if task_mode == _MODE_IMAGE2IMAGE:
            image_data_urls = _collect_image_data_urls(kwargs)
            if not image_data_urls:
                raise RuntimeError("图生图模式需要连接图片输入")

        settings_sha = _settings_signature(
            (user_text, task_mode, output_language, method, max_output_tokens,
             context_length, seed, auto_unload, enable_thinking, len(image_data_urls))
        )
        logger.info(
            f"TE Qwen Image 2.1 execute entered prompt=[{user_text[:60]}] settings_sha256={settings_sha[:16]} "
            f"mode={task_mode} method={method} seed={seed} auto_unload={auto_unload} "
            f"image_count={len(image_data_urls)}"
        )

        # 系统提示词：文生图版 / 图生图编辑版基底 + 输出策略 + 语言强化句
        base_prompt = QWEN_T2I_SYSTEM_PROMPT if task_mode == _MODE_TEXT2IMAGE else QWEN_EDIT_SYSTEM_PROMPT
        system_prompt = _build_system_prompt(base_prompt, output_language, method)

        try:
            if method == _METHOD_API:
                api_key = _resolve_api_key(str(kwargs.get('api_key') or ''))
                candidates = _resolve_api_url_candidates(str(kwargs.get('api_base_url') or ''))
                model = str(kwargs.get('model') or DEFAULT_API_MODEL).strip() or DEFAULT_API_MODEL
                raw = _request_api(
                    candidates, model, system_prompt, user_text, image_data_urls,
                    300, api_key, bool(kwargs.get('绕过代理') or False),
                )
                prompt_text, _parsed = _parse_result(raw)
            elif method == _METHOD_OFFICIAL_PE:
                if task_mode == _MODE_TEXT2IMAGE:
                    pe_label = str(kwargs.get('文生图PE模型') or '')
                else:
                    pe_label = str(kwargs.get('图生图PE模型') or '')
                official = TEQwenImage21OfficialStorage.load(pe_label, enable_thinking)
                raw = _request_official_pe(
                    official, system_prompt, user_text, image_data_urls,
                    max_output_tokens, seed,
                )
                prompt_text, _parsed = _parse_result(raw)
                if auto_unload:
                    TEQwenImage21OfficialStorage.unload()
            else:  # 本地（LLaMA）
                local = TEQwenImage21LocalStorage.load(
                    str(kwargs.get('主模型') or ''),
                    str(kwargs.get('mmproj') or _MODE_MMPROJ_NONE),
                    context_length,
                    need_vision=bool(image_data_urls),
                )
                raw = _request_local(
                    local, system_prompt, user_text, image_data_urls,
                    max_output_tokens, seed,
                )
                prompt_text, _parsed = _parse_result(raw)
                if auto_unload:
                    TEQwenImage21LocalStorage.unload()
        except Exception as exc:  # noqa: BLE001
            logger.error(f"TE Qwen Image 2.1 execute failed: {exc}")
            raise RuntimeError(f"TE MAN Qwen Image 2.1 提示词增强失败：{exc}") from exc

        if not prompt_text:
            raise RuntimeError("模型返回为空，可能只生成了思考内容但没有最终提示词。请提高最大生成token后重试。")
        logger.success(f"TE Qwen Image 2.1 execute completed output=[{prompt_text[:80]}]")
        return (prompt_text,)


NODE_CLASS_MAPPINGS = {'TE_Qwen_Image_2_1_Prompt_Enhancer': TEQwenImage21PromptEnhancer}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_Qwen_Image_2_1_Prompt_Enhancer': 'TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)'}
