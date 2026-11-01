# -*- coding: utf-8 -*-
"""te_man_open · Gemini_Imagen_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

te_man_open 纯 Python 复刻（spec/Gemini_Imagen_Generator.md 含动态回填节）：
- TE_image_pro_banana（BananaGeminiImageSafePyNode）：三协议生图
  Gemini原生API → api_client.generateContent；OpenAI Images → /v1/images/*；
  OpenAI Chat → /v1/chat/completions 多模态
- TE_image_pro_special_async2（BananaGeminiAsyncSafePyNode）：特渠异步，
  /v1/videos 提交-轮询-下载返回图像，模型名按分辨率+比例自动拼接
requests/torch/PIL/numpy/comfy 系一律惰性导入。
"""

import base64
import time

try:  # 包内相对导入；以文件方式直载时回退绝对导入
    from ..shared.api_client import API_CLIENT, sanitize_api_key
    from ..shared.config_manager import CONFIG_MANAGER
    from ..shared.image_codec import IMAGE_CODEC, ErrorCanvas
    from ..shared.task_runner import (
        BatchGenerationRunner,
        InterruptProcessingException,
    )
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared.api_client import API_CLIENT, sanitize_api_key
    from te_man_open.shared.config_manager import CONFIG_MANAGER
    from te_man_open.shared.image_codec import IMAGE_CODEC, ErrorCanvas
    from te_man_open.shared.task_runner import (
        BatchGenerationRunner,
        InterruptProcessingException,
    )
    from te_man_open.shared.logger import logger


# ==================== 快捷功能常量（真机 introspection 实锤，spec §7.2） ====================

QUICK_FUNCTION_NONE = "无"
QUICK_FUNCTION_OPTIONS = (
    "无", "白底三视图", "白底四视图", "九宫格[剧情]分镜",
    "九宫格[场景]分镜", "四宫格[剧情]分镜", "四宫格[视角]分镜",
)

# 模板全文与 Grok_Image 模块同文（spec/Grok_Image_Generator.md §6.5 原文还原）；
# 其中"白底三视图"→短模板、"白底四视图"→长模板的归属为动态回填实锤。
_QUICK_TEMPLATE_STORY_9 = (
    "根据提供的剧情概述 / 画面主题 / 参考图，"
    "生成一张具有清晰叙事推进关系的 3×3 九宫格分镜图，共 9 个连续镜头"
    "全部镜头发生在同一场景与同一时间轴内，九个画面之间必须存在明确的前后承接关系，"
    "形成连续的动作/视线或情绪推进，而不是彼此孤立的画面拼接"
    "分镜采用电影镜头语言进行自由发挥：在整体叙事推进中自然涵盖远景/中景/近景与特写等不同景别，"
    "并根据剧情需要灵活使用正视/侧视/背视/过肩/内反打/轻微俯仰等视角变化，"
    "用于强化空间关系/人物心理与节奏起伏"
    "镜头景别与角度不与编号固定绑定，而是由剧情发展自动选择最合适的表现方式，"
    "使九个镜头整体读起来具备真实影视分镜的流动感"
    "当用户仅提供剧情文字时，应主动补全合理的场景结构/人物站位/行动路线与镜头关系，"
    "使画面具备清晰空间逻辑；当用户提供参考图时，应将其作为人物外观/服装风格/色彩倾向"
    "与整体美术气质的统一依据，并在全部九个镜头中严格继承，"
    "不得随镜头推进出现风格变化或角色漂移"
    "在全部九个分镜中，人物的外观/服装/体型比例/面部特征保持一致，整体色彩倾向与光照条件统一，"
    "仅允许人物动作/姿态以及镜头远近和角度发生变化，"
    "不得出现角色变形/肢体缺失/结构错乱或美术风格断裂，纯视觉展示，"
    "没有任何文字/字母或标签，每个画面之间被清晰的黑色实线分割"
)
_QUICK_TEMPLATE_STORY_4 = _QUICK_TEMPLATE_STORY_9.replace(
    "3×3 九宫格分镜图，共 9 个连续镜头", "2×2 四宫格分镜图，共 4 个连续镜头"
).replace("九个画面之间", "四个画面之间").replace(
    "使九个镜头整体", "使四个镜头整体"
).replace("全部九个镜头中", "全部四个镜头中").replace(
    "全部九个分镜中", "全部四个分镜中"
)
_QUICK_TEMPLATE_SCENE_9 = (
    "生成一张严格的3x3九宫格图像，纯视觉展示"
    "正中央为场景标准透视效果图；正上方为俯视角度画面；正下方为地面纹理视角；"
    "左侧为左侧墙壁平视画面；右侧为右侧墙壁平视画面；"
    "四个角落分别是：正前方视角/正后方视角以及两个无文字的材质道具特写"
    "要求：九个画面光影逻辑完全统一，全方位展示空间，"
    "绝对不要生成任何解释性文字或图表排版，"
)
_QUICK_TEMPLATE_VIEW_4 = (
    "生成一张严格的2x2四宫格图像，纯视觉展示"
    "场景标准透视效果图；俯视角度画面；正正前方视角；正后方视角"
    "要求：四个画面光影逻辑完全统一，全方位展示空间，"
    "绝对不要生成任何解释性文字或图表排版，"
)
_QUICK_TEMPLATE_WHITE_BG_3 = (
    "三视图（正面、侧面、背面），白色纯色背景，人物角色设计图，"
)
_QUICK_TEMPLATE_WHITE_BG_4 = (
    "参照原图生成人物面部特写搭配全身三视图组合画面； "
    "画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照 / 侧面全身照 / 背面全身照，"
    "所有内容整合在 同一画幅内；采用纯白色背景，严格对齐人物人体比例 ，"
    "杜绝透视畸变问题，各视图之间间距均匀规整,无文字描述"
)

QUICK_FUNCTION_PREFIXES = {
    "无": "",
    "白底三视图": _QUICK_TEMPLATE_WHITE_BG_3,
    "白底四视图": _QUICK_TEMPLATE_WHITE_BG_4,
    "九宫格[剧情]分镜": _QUICK_TEMPLATE_STORY_9,
    "九宫格[场景]分镜": _QUICK_TEMPLATE_SCENE_9,
    "四宫格[剧情]分镜": _QUICK_TEMPLATE_STORY_4,
    "四宫格[视角]分镜": _QUICK_TEMPLATE_VIEW_4,
}


def _apply_quick_function_prompt(prompt, quick_function_value):
    """将所选快捷功能预设前缀拼到 prompt 前面（spec §3.4）。"""
    prefix = QUICK_FUNCTION_PREFIXES.get(str(quick_function_value or QUICK_FUNCTION_NONE), "")
    text = str(prompt or "").strip()
    if prefix:
        return prefix + text
    return text


# ==================== fix 内部测试渠道常量（spec §4.2） ====================

# base64 + 逐字节 XOR 0x07 混淆的后备 Base URL，解码结果为 https://api666.zeabur.app
_FIX_API_BASE_URL_ENC = "b3Nzd3Q9KChmd24xMTEpfWJmZXJ1KWZ3dw=="
_FIX_XOR_KEY = 0x07
# _FIX_API_KEY_PREFIX：原版前缀字面值未实锤（spec §7.3 核对为"未采集"），留占位空串；
# 置空时 _is_fix_mode 恒为 False，fix 后备 Base URL 不会生效——待抓包校准后回填。
_FIX_API_KEY_PREFIX = ""


def _decode_fix_api_base_url():
    """base64 解码后逐字节 XOR 0x07；失败时按 spec 文案回退默认配置。"""
    try:
        raw = base64.b64decode(_FIX_API_BASE_URL_ENC)
        return bytes(byte ^ _FIX_XOR_KEY for byte in raw).decode("utf-8")
    except Exception:  # noqa: BLE001
        logger.warning("解码内部测试 Base URL 失败，将回退到默认配置")
        return ""


_FIX_API_BASE_URL = _decode_fix_api_base_url()


def _is_fix_mode(api_key):
    """fix/内部测试渠道识别：API Key 命中内置前缀时启用后备 Base URL。"""
    return bool(_FIX_API_KEY_PREFIX) and str(api_key or "").startswith(_FIX_API_KEY_PREFIX)


# ==================== 通用工具 ====================

_API_FORMAT_MODE_LOGS = {
    "Gemini原生API": " 使用 Gemini 原生 API 模式",
    "OpenAI Images API": " 使用 OpenAI Images API 模式",
    "OpenAI Chat API": " 使用 OpenAI Chat API 模式",
}


def _ensure_not_interrupted():
    """统一的中断检查，复用 ComfyUI 原生取消机制（spec §3.0）。"""
    try:
        from comfy import model_management  # 惰性导入
    except Exception:  # noqa: BLE001  非 ComfyUI 环境
        return
    throw = (
        getattr(model_management, "throw_exception_if_processing_interrupted", None)
        or getattr(model_management, "throw_exception_if_interrupted", None)
    )
    if callable(throw):
        throw()
        return
    ensure = getattr(model_management, "ensure_not_interrupted", None)
    if callable(ensure):
        ensure()


def _collect_input_image_tensors(kwargs):
    """收集 image_1..image_9 中已连接的输入 tensor。"""
    tensors = []
    for index in range(1, 10):
        tensor = kwargs.get("image_%d" % index)
        if tensor is not None:
            tensors.append(tensor)
    return tensors


def _resolve_api_credentials(api_key_input, base_url_input):
    """API Key / Base URL 三级解析：节点输入 → config.ini → 内置默认站。"""
    api_key = str(api_key_input or "").strip()
    if not api_key:
        api_key = CONFIG_MANAGER.load_api_key() or ""
    if not api_key:
        raise ValueError("请在 config.ini 中配置 API Key 或在节点中填写")
    base_url = str(base_url_input or "").strip()
    if not base_url:
        base_url = CONFIG_MANAGER.get_effective_api_base_url("")
    if not base_url:
        raise ValueError("未配置有效的 API Base URL")
    logger.info("使用 API Key: %s" % sanitize_api_key(api_key))
    logger.info("使用 API Base URL: [已脱敏]")
    return api_key, base_url


def _stack_decoded_tensors(tensors):
    """多张 [1,H,W,C] tensor → 单一批次 tensor；尺寸不一致时零填充对齐。"""
    import torch  # 惰性导入

    clean = [t for t in tensors if t is not None]
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    max_h = max(int(t.shape[1]) for t in clean)
    max_w = max(int(t.shape[2]) for t in clean)
    aligned = []
    for t in clean:
        h, w = int(t.shape[1]), int(t.shape[2])
        if h == max_h and w == max_w:
            aligned.append(t)
            continue
        padded = torch.nn.functional.pad(t, (0, 0, 0, max_w - w, 0, max_h - h))
        aligned.append(padded)
    return torch.cat(aligned, dim=0)


def _build_failure_result(message, title="TE MAN 生成失败"):
    """构造统一的失败返回结构，便于上层聚合处理（ErrorCanvas 错误画布）。"""
    error_tensor = ErrorCanvas().build_error_tensor_from_text(message, title=title)
    return error_tensor, str(message or "未知错误")


def _on_batch_progress(result, completed_count, total_count, task):
    """批次完成回调：逐批日志。"""
    logger.info("批次 %s/%s 完成" % (completed_count, total_count))


def _decode_images_to_tensors(images_b64):
    """base64 列表 → [1,H,W,C] tensor 列表（并行解码）。"""
    if not images_b64:
        raise RuntimeError("完成，但未返回任何图片")
    return IMAGE_CODEC.base64_to_tensor_parallel(images_b64, log_prefix=" 开始解码 ")


_URL_VALUE_KEYS = frozenset({
    "url", "image_url", "imageUrl", "image", "img", "download_url",
    "downloadUrl", "output", "output_url", "file_url", "fileUrl",
})
_B64_VALUE_KEYS = frozenset({"b64_json", "image_base64", "base64", "data"})
_URL_LINE_RE = None  # 惰性编译占位：图像扩展名判定用
_IMAGE_EXT_RE = None


def _extract_async_image_payloads(payload):
    """从 /v1/videos 图像任务响应中提取 (b64_images, image_urls)。

    递归遍历：data URI / b64 字段直接收 base64；疑似图像 URL 收集后由调用方下载。
    （spec：parsed_image_urls / input_image_urls；响应字段细节未实锤，按宽容匹配实现）
    """
    import re as _re

    image_ext_re = _re.compile(r"\.(png|jpe?g|webp|gif)(\?|#|$)", _re.IGNORECASE)
    b64_chars_re = _re.compile(r"[A-Za-z0-9+/=\s]+")
    b64_images = []
    image_urls = []

    def _walk(node, parent_key=""):
        if isinstance(node, dict):
            for key, value in node.items():
                _walk(value, str(key))
        elif isinstance(node, (list, tuple)):
            for item in node:
                _walk(item, parent_key)
        elif isinstance(node, str):
            text = node.strip()
            if not text:
                return
            if text.startswith("data:image/") and ";base64," in text:
                b64_images.append(text.split(";base64,", 1)[1])
                return
            lowered_key = parent_key.lower()
            if any(marker in lowered_key for marker in ("b64", "base64")):
                if len(text) >= 256 and b64_chars_re.fullmatch(text):
                    b64_images.append(_re.sub(r"\s+", "", text))
                return
            if text.startswith(("http://", "https://")):
                if parent_key.lower() in _URL_VALUE_KEYS or image_ext_re.search(text):
                    image_urls.append(text)

    _walk(payload)
    # 去重保序
    b64_images = list(dict.fromkeys(b64_images))
    image_urls = list(dict.fromkeys(image_urls))
    return b64_images, image_urls


def _finalize_results(results, total, aspect_ratio, image_size):
    """聚合各批次结果：成功则拼批次 tensor，全败则输出错误画布。"""
    tensors = []
    texts = []
    errors = []
    for batch_tensors, batch_text, ok in results:
        if ok:
            tensors.extend(batch_tensors or [])
            if batch_text:
                texts.append(str(batch_text))
        else:
            errors.append(str(batch_text or "未知错误"))
    if tensors:
        batch = _stack_decoded_tensors(tensors)
        text = "\n".join(texts)
        produced = int(batch.shape[0]) if batch is not None else 0
        if produced < total:
            logger.warning(
                "部分批次未返回图片：请求 %d 张，实际上只生成 %d 张图像（比例: %s，分辨率: %s）"
                "张，请查看上方各批次日志中的'未返回任何图片'提示"
                % (total, produced, aspect_ratio, image_size)
            )
        return batch, text
    if errors:
        message = "生成失败：" + " / ".join(errors)
    else:
        message = "完成，但未返回任何图片"
    return _build_failure_result(message)


class BananaGeminiImageSafePyNode:
    """TE MAN Gemini Image

    注册名: TE_image_pro_banana
    规格:   spec/Gemini_Imagen_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Gemini'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只可爱的小猫', 'tooltip': '生成图像的文本提示词，可多行描述内容、风格等'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': '调用服务的 API Key；留空则优先使用 config.ini 中的配置'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API 服务地址；留空则使用 config.ini 中的配置'}), 'model_type': ('STRING', {'default': 'gemini-3.1-flash-image-preview', 'multiline': False, 'tooltip': '模型名称）'}), 'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 8, 'tooltip': '一次请求中要生成的图片数量，范围 1~8'}), 'aspect_ratio': (('Auto', '1:1', '9:16', '16:9', '21:9', '2:3', '3:2', '3:4', '4:3', '4:5', '5:4'), {'default': 'Auto', 'tooltip': '生成图像的宽高比例，Auto 为由服务端自动决定'}), 'API格式': (('Gemini原生API', 'OpenAI Images API', 'OpenAI Chat API'), {'default': 'Gemini原生API', 'tooltip': '选择API格式：Gemini原生API | OpenAI Images API (/v1/images/*) | OpenAI Chat API (/v1/chat/completions)'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '随机种子，-1 为自动随机；固定种子可复现同一输出'}), 'top_p': ('FLOAT', {'default': 0.95, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'tooltip': '采样参数 Top-P，数值越低越保守，越高多样性越强'}), 'image_size': (('1K', '2K', '4K'), {'default': '2K', 'tooltip': '分辨率'}), 'image_1': ('IMAGE', {'tooltip': '参考图像 1，可为空；用于图生图或多图融合'}), 'image_2': ('IMAGE', {'tooltip': '参考图像 2，可为空；用于图生图或多图融合'}), 'image_3': ('IMAGE', {'tooltip': '参考图像 3，可为空；用于图生图或多图融合'}), 'image_4': ('IMAGE', {'tooltip': '参考图像 4，可为空；用于图生图或多图融合'}), 'image_5': ('IMAGE', {'tooltip': '参考图像 5，可为空；用于图生图或多图融合'}), 'image_6': ('IMAGE', {'tooltip': '参考图像 6，可为空；用于图生图或多图融合'}), 'image_7': ('IMAGE', {'tooltip': '参考图像 7，可为空；用于图生图或多图融合'}), 'image_8': ('IMAGE', {'tooltip': '参考图像 8，可为空；用于图生图或多图融合'}), 'image_9': ('IMAGE', {'tooltip': '参考图像 9，可为空；用于图生图或多图融合'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '梯子速度不佳、不可靠时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜'), {'default': '无', 'tooltip': '使用快捷功能生成。'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 协议路径（spec §3.1，方法名实锤） ====================

    def _generate_with_gemini_api(self, prompt, api_key, base_url, model,
                                  data_urls, aspect_ratio, image_size, bypass_proxy):
        """Gemini 原生 generateContent：create_request_data → send_request → extract_content。"""
        request_data = API_CLIENT.create_request_data(
            prompt,
            input_images_b64=data_urls,
            model_type=model,
            aspect_ratio=aspect_ratio,
            image_size=image_size,
        )
        logger.info("模型名称: %s" % model)
        logger.info(" 开始请求...")
        response = API_CLIENT.send_request(
            api_key,
            request_data,
            model=model,
            api_base_url=base_url,
            bypass_proxy=bypass_proxy,
        )
        finish_reason = ""
        candidates = response.get("candidates") or [] if isinstance(response, dict) else []
        if candidates:
            finish_reason = str(candidates[0].get("finishReason") or "")
        images, text = API_CLIENT.extract_content(
            response, api_key=api_key, bypass_proxy=bypass_proxy
        )
        if not images:
            reason = finish_reason or "NO_IMAGE"
            message = (
                "模型未生成图片（finishReason=%s，一般表示当前提示或参考图不触发图像输出，"
                "可能是内容被过滤或未通过安全审查）" % reason
            )
            if text:
                message += "；模型返回文本: %s" % str(text)[:120]
            raise RuntimeError(message)
        return _decode_images_to_tensors(images), text

    def _generate_with_openai_api(self, prompt, api_key, base_url, model, data_urls,
                                  aspect_ratio, image_size, seed, bypass_proxy):
        """OpenAI Images：create_openai_request_data → send_openai_request → 轮询 → 解析。"""
        data, files, is_img2img = API_CLIENT.create_openai_request_data(
            prompt,
            seed=seed if isinstance(seed, int) and seed >= 0 else None,
            aspect_ratio=aspect_ratio,
            model_type=model,
            image_size=image_size,
            response_format="b64_json",
            input_images_b64=data_urls,
        )
        logger.info("开始请求...（%s）" % ("img2img /v1/images/edits" if is_img2img else "text2img /v1/images/generations"))
        task_id = API_CLIENT.send_openai_request(
            api_key, data, files=files, api_base_url=base_url, bypass_proxy=bypass_proxy
        )
        logger.info("提交任务: task_id=%s" % task_id)
        body = API_CLIENT.poll_openai_task(
            api_key, task_id, api_base_url=base_url, bypass_proxy=bypass_proxy
        )
        images, text = API_CLIENT.extract_openai_content(
            body, api_key=api_key, bypass_proxy=bypass_proxy
        )
        if not images:
            if text:
                raise RuntimeError("模型仅返回文本: %s" % str(text)[:200])
            raise RuntimeError("完成，但未返回任何图片")
        return _decode_images_to_tensors(images), text

    def _generate_with_chat_api(self, prompt, api_key, base_url, model, data_urls,
                                top_p, bypass_proxy):
        """OpenAI Chat 多模态：create_chat_request_data → send_chat_request → 解析。"""
        request_data = API_CLIENT.create_chat_request_data(
            prompt=prompt,
            model=model,
            input_images_b64=data_urls,
            stream=False,
            top_p=top_p,
        )
        logger.info("开始请求...")
        images, text = API_CLIENT.send_chat_request(
            api_key, request_data, api_base_url=base_url, bypass_proxy=bypass_proxy
        )
        if not images:
            if text:
                raise RuntimeError("模型仅返回文本: %s" % str(text)[:200])
            raise RuntimeError(
                "模型未给出图片或说明文本，可能是服务端策略或参数设置导致本次未产出图片"
            )
        return _decode_images_to_tensors(images), text

    def _generate_single_image(self, task_index, prompt, api_key, base_url, model,
                               api_format, data_urls, aspect_ratio, image_size,
                               seed, top_p, bypass_proxy):
        """生成单张图片（用于并发）。由 BatchGenerationRunner 多线程执行。"""
        _ensure_not_interrupted()
        started = time.perf_counter()
        try:
            if api_format == "OpenAI Images API":
                tensors, text = self._generate_with_openai_api(
                    prompt, api_key, base_url, model, data_urls,
                    aspect_ratio, image_size, seed, bypass_proxy)
            elif api_format == "OpenAI Chat API":
                tensors, text = self._generate_with_chat_api(
                    prompt, api_key, base_url, model, data_urls, top_p, bypass_proxy)
            else:
                tensors, text = self._generate_with_gemini_api(
                    prompt, api_key, base_url, model, data_urls,
                    aspect_ratio, image_size, bypass_proxy)
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001  单批失败不拖垮整体
            logger.error("[批次 %s] 生成失败: %s" % (task_index + 1, exc))
            return None, str(exc or "未知错误"), False
        logger.info(
            "[批次 %s] 成功生成 %d 张图片，耗时 %.1fs"
            % (task_index + 1, len(tensors), time.perf_counter() - started)
        )
        return tensors, text, True

    def generate_images(self, **kwargs):
        """TE_image_pro_banana：三协议批次生图（并发拆批 + 中断透传 + 错误画布）。"""
        _ensure_not_interrupted()
        prompt = _apply_quick_function_prompt(
            kwargs.get("prompt"), kwargs.get("快捷功能") or QUICK_FUNCTION_NONE
        )
        api_format = str(kwargs.get("API格式") or "Gemini原生API")
        model = str(kwargs.get("model_type") or "gemini-3.1-flash-image-preview").strip()
        try:
            batch_size = max(1, int(kwargs.get("batch_size") or 1))
        except (TypeError, ValueError):
            batch_size = 1
        aspect_ratio = str(kwargs.get("aspect_ratio") or "Auto")
        image_size = str(kwargs.get("image_size") or "2K")
        seed = kwargs.get("seed")
        top_p = kwargs.get("top_p")
        bypass_proxy = bool(kwargs.get("绕过代理"))

        api_key, base_url = _resolve_api_credentials(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        if _is_fix_mode(api_key) and _FIX_API_BASE_URL:
            # fix/内部测试渠道：API Key 命中内置前缀时改走后备 Base URL（机制按 spec 推断）
            base_url = _FIX_API_BASE_URL
            logger.info("使用 API Base URL: [已脱敏]（fix 内部测试渠道）")

        image_tensors = _collect_input_image_tensors(kwargs)
        data_urls = IMAGE_CODEC.prepare_input_image_data_urls(image_tensors) if image_tensors else []

        logger.info("TE MAN Gemini 图像生成任务（批次数量: %d）" % batch_size)
        logger.info(_API_FORMAT_MODE_LOGS.get(api_format, _API_FORMAT_MODE_LOGS["Gemini原生API"]))
        if batch_size > 1:
            logger.info("将循环调用 %d 张图片" % batch_size)

        tasks = list(range(batch_size))

        def _worker(index):
            return self._generate_single_image(
                index, prompt, api_key, base_url, model, api_format, data_urls,
                aspect_ratio, image_size, seed, top_p, bypass_proxy)

        runner = BatchGenerationRunner(
            tasks, _worker, batch_size=batch_size, continue_on_error=True, logger=logger
        )
        start_time = time.perf_counter()
        results = runner.run(
            progress_callback=_on_batch_progress,
            max_workers=CONFIG_MANAGER.load_max_workers(),
            ensure_not_interrupted=_ensure_not_interrupted,
        )
        total_time = time.perf_counter() - start_time

        batch, text = _finalize_results(results, batch_size, aspect_ratio, image_size)
        produced = int(batch.shape[0]) if batch is not None else 0
        if produced:
            logger.info("总耗时: %.1fs，平均速度: %.1fs/张" % (total_time, total_time / produced))
        if batch is None:
            batch, text = _build_failure_result(text or "未知错误")
        preview = IMAGE_CODEC.build_preview_tuple(batch)
        if preview is not None:
            return (batch, text, preview)
        return (batch, text)

class BananaGeminiAsyncSafePyNode:
    """TE MAN Gemini 特渠

    注册名: TE_image_pro_special_async2
    规格:   spec/Gemini_Imagen_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Gemini'
    FUNCTION = 'generate_images'
    OUTPUT_NODE = True
    RETURN_TYPES = ('IMAGE', 'STRING')
    RETURN_NAMES = ('images', 'text')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': '一只快乐的小猫', 'tooltip': '生成图像的文本提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': '调用服务的 API Key；留空则优先使用 config.ini 中的配置'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API 服务地址；留空则使用 config.ini 中的配置'}), 'model_type': (('nano-banana-pro', 'nano-banana-2'), {'default': 'nano-banana-pro', 'tooltip': '基础模型；会自动根据下方分辨率拼接实际请求模型名'}), 'batch_size': ('INT', {'default': 1, 'min': 1, 'max': 8, 'tooltip': '一次请求中要生成的图片数量，范围 1~8'}), 'aspect_ratio': (('1:1', '16:9', '9:16', '4:3', '3:4'), {'default': '4:3', 'tooltip': '宽高比'}), 'image_size': (('1K', '2K', '4K'), {'default': '1K', 'tooltip': '分辨率；会自动拼接到模型名称中'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '随机种子，-1 为自动随机；固定种子可复现同一输出'}), 'image_1': ('IMAGE', {'tooltip': '参考图像 1，可为空；用于图生图或多图融合'}), 'image_2': ('IMAGE', {'tooltip': '参考图像 2，可为空；用于图生图或多图融合'}), 'image_3': ('IMAGE', {'tooltip': '参考图像 3，可为空；用于图生图或多图融合'}), 'image_4': ('IMAGE', {'tooltip': '参考图像 4，可为空；用于图生图或多图融合'}), 'image_5': ('IMAGE', {'tooltip': '参考图像 5，可为空；用于图生图或多图融合'}), 'image_6': ('IMAGE', {'tooltip': '参考图像 6，可为空；用于图生图或多图融合'}), 'image_7': ('IMAGE', {'tooltip': '参考图像 7，可为空；用于图生图或多图融合'}), 'image_8': ('IMAGE', {'tooltip': '参考图像 8，可为空；用于图生图或多图融合'}), 'image_9': ('IMAGE', {'tooltip': '参考图像 9，可为空；用于图生图或多图融合'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '梯子速度不佳、不可靠时开启'}), '快捷功能': (('无', '白底三视图', '白底四视图', '九宫格[剧情]分镜', '九宫格[场景]分镜', '四宫格[剧情]分镜', '四宫格[视角]分镜'), {'default': '无', 'tooltip': '使用快捷功能生成。'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 特渠异步常量（spec §7.2 下拉间接实锤） ====================

    _ASYNC_BASE_MODELS = ("nano-banana-pro", "nano-banana-2")
    _ASYNC_IMAGE_SIZES = ("1K", "2K", "4K")
    _ASYNC_ASPECT_RATIOS = ("1:1", "16:9", "9:16", "4:3", "3:4")

    def _build_async_model_name(self, base_model, aspect_ratio, image_size):
        """按分辨率 + 比例自动拼接实际请求模型名（spec §3.3）。

        注意：原版拼接字面格式未实锤（spec §7.2 标注为类属性/非常量容器、
        静态提取不到），此处按 ``{基础模型}_{尺寸}_{比例}`` 功能等价实现，
        待抓包校准后回填分隔符与字段顺序。
        """
        normalized_base_model = (
            str(base_model) if base_model in self._ASYNC_BASE_MODELS else self._ASYNC_BASE_MODELS[0]
        )
        normalized_size = (
            str(image_size) if image_size in self._ASYNC_IMAGE_SIZES else self._ASYNC_IMAGE_SIZES[0]
        )
        normalized_ratio = (
            str(aspect_ratio) if aspect_ratio in self._ASYNC_ASPECT_RATIOS else self._ASYNC_ASPECT_RATIOS[0]
        )
        actual_model = "%s_%s_%s" % (
            normalized_base_model, normalized_size, normalized_ratio.replace(":", "x")
        )
        logger.info("使用基础模型: %s" % normalized_base_model)
        logger.info("实际请求模型: %s" % actual_model)
        return actual_model

    def _generate_single_image_special_async(self, task_index, prompt, actual_model,
                                             api_key, base_url, aspect_ratio, image_size,
                                             data_urls, seed, bypass_proxy):
        """提交 /v1/videos → 轮询 → 提取图片 → 并行解码（spec §3.3）。"""
        _ensure_not_interrupted()
        started = time.perf_counter()
        try:
            request_data = API_CLIENT.create_video_request_data(
                prompt,
                input_image_urls=data_urls,
                model=actual_model,
                aspect_ratio=aspect_ratio,
                image_size=image_size,
                seed=seed if isinstance(seed, int) and seed >= 0 else None,
            )
            logger.info("/v1/videos 提交异步图像生成任务...")
            task_id = API_CLIENT.send_video_request(
                api_key, request_data, api_base_url=base_url, bypass_proxy=bypass_proxy
            )
            if not task_id:
                raise RuntimeError("接口未返回任务 ID")
            logger.info("提交成功: task_id=%s" % task_id)
            body = API_CLIENT.poll_video_task(
                api_key, task_id, api_base_url=base_url, bypass_proxy=bypass_proxy
            )
            b64_images, image_urls = _extract_async_image_payloads(body)
            for url in image_urls:
                # 复用 api_client 的鉴权下载（Content-Type 校验 + 脱敏日志）
                b64_images.append(
                    API_CLIENT._download_url_to_b64(
                        url, api_key=api_key, source="markdown", bypass_proxy=bypass_proxy
                    )
                )
            if not b64_images:
                raise RuntimeError("完成，但未返回任何图片")
            tensors = _decode_images_to_tensors(b64_images)
        except InterruptProcessingException:
            raise
        except Exception as exc:  # noqa: BLE001  单批失败不拖垮整体
            message = str(exc or "未知错误")
            if "task_id" in message and "接口未返回任务 ID" not in message:
                message = "接口未返回任务 ID"
            logger.error("[批次 %s] 生成失败: %s" % (task_index + 1, message))
            return None, message, False
        logger.info(
            "[批次 %s] 成功生成 %d 张图片，耗时 %.1fs"
            % (task_index + 1, len(tensors), time.perf_counter() - started)
        )
        return tensors, "", True

    def generate_images(self, **kwargs):
        """TE_image_pro_special_async2：/v1/videos 异步图像生成（提交-轮询-下载）。"""
        _ensure_not_interrupted()
        prompt = _apply_quick_function_prompt(
            kwargs.get("prompt"), kwargs.get("快捷功能") or QUICK_FUNCTION_NONE
        )
        base_model = str(kwargs.get("model_type") or self._ASYNC_BASE_MODELS[0])
        try:
            batch_size = max(1, int(kwargs.get("batch_size") or 1))
        except (TypeError, ValueError):
            batch_size = 1
        aspect_ratio = str(kwargs.get("aspect_ratio") or self._ASYNC_ASPECT_RATIOS[3])
        image_size = str(kwargs.get("image_size") or self._ASYNC_IMAGE_SIZES[0])
        seed = kwargs.get("seed")
        bypass_proxy = bool(kwargs.get("绕过代理"))

        actual_model = self._build_async_model_name(base_model, aspect_ratio, image_size)
        api_key, base_url = _resolve_api_credentials(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        if _is_fix_mode(api_key) and _FIX_API_BASE_URL:
            base_url = _FIX_API_BASE_URL
            logger.info("使用 API Base URL: [已脱敏]（fix 内部测试渠道）")

        image_tensors = _collect_input_image_tensors(kwargs)
        data_urls = IMAGE_CODEC.prepare_input_image_data_urls(image_tensors) if image_tensors else []

        logger.info(" TE banana特渠异步图像生成任务（批次数量: %d）" % batch_size)
        if batch_size > 1:
            logger.info("TE banana特渠将循环调用 %d 张图片" % batch_size)

        tasks = list(range(batch_size))

        def _worker(index):
            return self._generate_single_image_special_async(
                index, prompt, actual_model, api_key, base_url,
                aspect_ratio, image_size, data_urls, seed, bypass_proxy)

        runner = BatchGenerationRunner(
            tasks, _worker, batch_size=batch_size, continue_on_error=True, logger=logger
        )
        start_time = time.perf_counter()
        results = runner.run(
            progress_callback=_on_batch_progress,
            max_workers=CONFIG_MANAGER.load_max_workers(),
            ensure_not_interrupted=_ensure_not_interrupted,
        )
        total_time = time.perf_counter() - start_time

        batch, text = _finalize_results(results, batch_size, aspect_ratio, image_size)
        produced = int(batch.shape[0]) if batch is not None else 0
        if produced:
            logger.info("总耗时: %.1fs，平均速度: %.1fs/张" % (total_time, total_time / produced))
        if batch is None:
            batch, text = _build_failure_result(text or "未知错误")
        preview = IMAGE_CODEC.build_preview_tuple(batch)
        if preview is not None:
            return (batch, text, preview)
        return (batch, text)

NODE_CLASS_MAPPINGS = {'TE_image_pro_banana': BananaGeminiImageSafePyNode, 'TE_image_pro_special_async2': BananaGeminiAsyncSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_banana': 'TE MAN Gemini Image', 'TE_image_pro_special_async2': 'TE MAN Gemini 特渠'}
