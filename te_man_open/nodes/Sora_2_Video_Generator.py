# -*- coding: utf-8 -*-
"""te_man_open · Sora_2_Video_Generator

本文件由 tools/codegen_skeletons.py 自动生成骨架。
INPUT_TYPES 为与原版逐字段一致的真机契约；请实现各 FUNCTION 方法。

te_man_open 纯 Python 复刻（spec/Sora_2_Video_Generator.md 含动态回填节）：
Sora2 视频生成任务 ——「OpenAI videos 风格」异步协议：
- POST {base}/v1/videos 提交任务拿 task_id
- GET  {base}/v1/videos/{task_id} 轮询状态（成功 completed/succeeded/ready/finished，
  失败 failed/cancelled/canceled/expired/error）
- 流式下载 video_url 到 ComfyUI/output（前缀 sora2_video_）

本节点自建 requests.Session 直连（不复用 api_client，spec §1 负证据：
UA 为 ComfyUI-TE_MAN/1.0，与 api_client 的 ComfyUI-TE_API/1.0 不同），
含 trust_env 代理开关；requests/torch/numpy/comfy 系全部函数内惰性导入。
seed 仅供 ComfyUI 工作流使用，不写入请求体（tooltip 实锤）。
"""

import json
import os
import time
from urllib.parse import urljoin

try:  # 包内相对导入；以文件方式直载时回退绝对导入
    from ..shared.config_manager import CONFIG_MANAGER
    from ..shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_data_url
    from ..shared.logger import logger
except ImportError:  # pragma: no cover - 直接以文件方式加载时兜底
    from te_man_open.shared.config_manager import CONFIG_MANAGER
    from te_man_open.shared.image_codec import IMAGE_CODEC, encode_numpy_image_to_api_data_url
    from te_man_open.shared.logger import logger


# ==================== 模块常量（spec §7 动态回填实锤值） ====================

def _probe_comfy_video():
    """探测 comfy_api 的 VideoFromFile 是否可用（_HAS_COMFY_VIDEO 守卫）。"""
    try:
        from comfy_api.input_impl import VideoFromFile  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        try:
            from comfy_api.latest.input_impl import VideoFromFile  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False


#: ComfyUI 视频支持可用性（真机 introspection 实锤值：True）
_HAS_COMFY_VIDEO = _probe_comfy_video()

#: 默认模型（spec 实锤 _DEFAULT_MODEL = "sora-2"）
_DEFAULT_MODEL = "sora-2"

#: UA（spec 实锤：本模块 UA 与 api_client 不同，为 ComfyUI-TE_MAN/1.0）
_USER_AGENT = "ComfyUI-TE_MAN/1.0"

#: 输出文件名前缀（配 URL splitext 得到的扩展名，缺省 .mp4）
_OUTPUT_FILE_PREFIX = "sora2_video_"

#: 视频任务状态机（字符串直接证据，spec 附录）
_VIDEO_DONE_STATUS = frozenset({"completed", "succeeded", "ready", "finished"})
_VIDEO_FAILED_STATUS = frozenset({"failed", "cancelled", "canceled", "expired", "error"})

#: 轮询间隔为内部固定值（poll_interval_s 不作为 UI 输入暴露，spec §7.2 修正）
_POLL_INTERVAL_S = 5.0

_MSG_EMPTY_PROMPT = "请输入 prompt"
_MSG_NO_KEY = "请在 config.ini 中配置 API Key 或在节点中填写"
_MSG_NO_URL = "请在 config.ini 中配置 API URL 或在节点中填写"
_MSG_INVALID_URL = "未配置有效的 API URL"


# ==================== 中断 / 会话 / 日志辅助 ====================

def _ensure_not_interrupted():
    """轮询中途检查 ComfyUI 中断（comfy.model_management 协议，非 ComfyUI 环境为 no-op）。"""
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


def _masked_key(api_key):
    """日志打码：保留首尾 4 位。"""
    key = str(api_key or "").strip()
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * 8 + key[-4:]


def _build_session(bypass_proxy):
    """自建 requests.Session 直连（本模块不复用 api_client）；绕代理时 trust_env=False。"""
    import requests  # 惰性导入

    session = requests.Session()
    if bypass_proxy:
        session.trust_env = False
        session.proxies = {}
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


def _get_output_dir():
    """输出目录：ComfyUI/output（folder_paths 可用时），否则回退 ./output。"""
    try:
        import folder_paths  # 仅 ComfyUI 环境存在

        output_dir = folder_paths.get_output_directory()
    except Exception:  # noqa: BLE001  纯 Python 环境回退
        output_dir = os.path.join(os.getcwd(), "output")
    output_dir = os.path.abspath(output_dir)
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _sanitize_response_text(text, max_chars=800):
    """响应文本脱敏：data URI / 大段 base64 打码 + 截断。"""
    import re

    value = str(text or "")
    value = re.sub(
        r"data:[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+",
        lambda m: m.group(0).split(";base64,", 1)[0] + ";base64,<base64 omitted>",
        value,
    )
    value = re.sub(r"[A-Za-z0-9+/=]{512,}", "<base64 omitted>", value)
    if len(value) > max_chars:
        value = value[:max_chars] + "... <truncated>"
    return value


# ==================== URL / 响应解析（模块级函数名对齐 spec §2） ====================

def _resolve_videos_url(api_base_url):
    """归一化 base 并拼出提交端点 `{base}/v1/videos`（urljoin，spec §2/§3.3 步骤 4）。"""
    base = str(api_base_url or "").strip().rstrip("/")
    if not base:
        raise ValueError(_MSG_INVALID_URL)
    if base.endswith("/videos"):
        return base
    if base.endswith("/v1") or "/v1/" in base:
        return base + "/videos"
    return urljoin(base + "/", "v1/videos")


def _extract_task_id(response_json):
    """从创建响应提取 task_id（兜底 id；兼容 data 包裹层）。"""
    if not isinstance(response_json, dict):
        return ""
    nodes = [response_json]
    data = response_json.get("data")
    if isinstance(data, dict):
        nodes.insert(0, data)
    for node in nodes:
        for key in ("task_id", "taskId", "id"):
            value = node.get(key)
            if value:
                return str(value)
    return ""


def _extract_task_status(response_json):
    """提取任务状态（status 兜底 state / code）。"""
    if not isinstance(response_json, dict):
        return ""
    data = response_json.get("data")
    for node in (data if isinstance(data, dict) else None, response_json):
        if isinstance(node, dict):
            status = node.get("status") or node.get("state") or node.get("code")
            if status:
                return str(status)
    return ""


def _extract_progress(response_json):
    """提取轮询进度字段（progress，可为数字或字符串）。"""
    if not isinstance(response_json, dict):
        return ""
    data = response_json.get("data")
    for node in (data if isinstance(data, dict) else None, response_json):
        if isinstance(node, dict):
            progress = node.get("progress")
            if progress is not None and progress != "":
                return str(progress)
    return ""


def _extract_video_url(response_json):
    """提取视频地址（video_url / url / video / downloadUrl，兼容 data 包裹层与嵌套字典）。"""
    if not isinstance(response_json, dict):
        return ""
    nodes = [response_json]
    data = response_json.get("data")
    if isinstance(data, dict):
        nodes.insert(0, data)
    for node in nodes:
        for key in ("video_url", "videoUrl", "url", "downloadUrl", "download_url"):
            value = node.get(key)
            if isinstance(value, dict):
                value = value.get("url") or value.get("video_url") or value.get("downloadUrl")
            if isinstance(value, str) and value:
                return value
        nested = node.get("video")
        if isinstance(nested, dict):
            value = nested.get("url") or nested.get("video_url")
            if isinstance(value, str) and value:
                return value
        if isinstance(nested, str) and nested:
            return nested
    return ""


def _extract_error_message(response_json):
    """提取失败消息（error / message 字段，error 可为字典或字符串）。"""
    if not isinstance(response_json, dict):
        return ""
    data = response_json.get("data")
    for node in (data if isinstance(data, dict) else None, response_json):
        if not isinstance(node, dict):
            continue
        for key in ("message", "error"):
            value = node.get(key)
            if isinstance(value, dict):
                value = value.get("message") or value.get("error") or ""
            if isinstance(value, str) and value.strip():
                return value.strip()
    return ""


def _absolutize_url(raw_url, endpoint):
    """相对地址补全（urljoin，同 VEO 节点协议）；已是绝对地址原样返回。"""
    value = str(raw_url or "").strip()
    if not value:
        return ""
    if value.startswith(("http://", "https://")) or "://" in value:
        return value
    return urljoin(endpoint, value)


def _encode_image_to_data_url(image_tensor):
    """图生视频参考图 → data URL（委托 image_codec，维度校验按 spec §3.3 步骤 2）。"""
    try:
        import numpy  # noqa: F401  仅探测依赖，缺失给专门文案
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("缺少图像依赖（numpy）: %s" % exc) from exc
    if image_tensor is None:
        raise ValueError("没有可用图像")
    ndim = getattr(image_tensor, "ndim", None)
    if ndim is not None and int(ndim) not in (3, 4):
        raise ValueError("不支持的 IMAGE 维度: %d" % int(ndim))
    images = IMAGE_CODEC.extract_numpy_images(image_tensor)
    if not images:
        raise ValueError("没有可用图像")
    return encode_numpy_image_to_api_data_url(images[0])


def _count_batch_images(image_tensor):
    """统计批内张数（BHWC 取 shape[0]，其余按 1 张）。"""
    try:
        if image_tensor is not None and image_tensor.ndim == 4:
            return int(image_tensor.shape[0])
    except AttributeError:
        pass
    return 1 if image_tensor is not None else 0


def _make_video_from_file(path):
    """VideoFromFile 包装（惰性导入，_HAS_COMFY_VIDEO 为 False 时报环境不支持）。"""
    if not _HAS_COMFY_VIDEO:
        raise RuntimeError("当前 ComfyUI 环境缺少 comfy_api 视频支持，无法返回 VIDEO 输出")
    last_error = None
    for module_path in ("comfy_api.input_impl", "comfy_api.latest.input_impl"):
        try:
            module = __import__(module_path, fromlist=["VideoFromFile"])
            return module.VideoFromFile(path)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    raise RuntimeError("Invalid video file: %s (%s)" % (os.path.basename(path), last_error))


class BananaSora2VideoSafePyNode:
    """TE MAN sora2 video

    注册名: TE_image_pro_sora2_video
    规格:   spec/Sora_2_Video_Generator.md（含动态 introspection 回填节）

    INPUT_TYPES 为真机契约，由 codegen 生成，禁止手改；
    实现工作只发生在 FUNCTION 指向的方法中。
    """

    CATEGORY = 'TE MAN/Sora'
    FUNCTION = 'generate_video'
    OUTPUT_NODE = True
    RETURN_TYPES = ('VIDEO', 'STRING', 'STRING')
    RETURN_NAMES = ('video', 'video_url', 'response')

    @classmethod
    def INPUT_TYPES(cls):
        # --8<-- 契约开始（codegen 生成）--8<--
        return {'required': {'prompt': ('STRING', {'multiline': True, 'default': 'A cinematic orange cat walking slowly through a rainy neon street at night.', 'tooltip': '用于生成视频的提示词'}), 'api_key': ('STRING', {'default': '', 'multiline': False, 'tooltip': 'API Key；留空则读取 config.ini'}), 'api_base_url': ('STRING', {'default': '', 'multiline': False, 'tooltip': '服务地址，如 https://socdabat.it.com（不要带 /v1/videos）'}), 'model': ('STRING', {'default': 'sora-2', 'multiline': False, 'tooltip': '模型名称，默认 sora-2'}), 'aspect_ratio': (('16:9', '9:16'), {'default': '16:9', 'tooltip': '画面比例'}), 'resolution': (('720p',), {'default': '720p', 'tooltip': '分辨率'}), 'seconds': (('4', '8', '12'), {'default': '8', 'tooltip': '视频时长（秒）'})}, 'optional': {'seed': ('INT', {'default': -1, 'min': -1, 'max': 102400, 'control_after_generate': True, 'tooltip': '仅供 ComfyUI 工作流使用；不会写入请求体'}), 'image': ('IMAGE', {'tooltip': '参考图片（可选），接入后走图生视频，写入 image_url'}), 'timeout_s': ('INT', {'default': 900, 'min': 30, 'max': 3600, 'tooltip': '总超时（秒），包含创建任务、轮询和下载'}), '绕过代理': ('BOOLEAN', {'default': False, 'tooltip': '需要忽略系统代理/梯子时开启'})}}
        # --8<-- 契约结束 --8<--

    # ==================== 配置解析（spec §3.3 步骤 3） ====================

    def _resolve_key_and_url(self, api_key, api_url):
        """key/URL 缺省 → config.ini（[gemini] api_key / get_effective_api_base_url）。"""
        resolved_key = str(api_key or "").strip() or (CONFIG_MANAGER.load_api_key() or "")
        if not resolved_key:
            raise ValueError(_MSG_NO_KEY)
        url = str(api_url or "").strip() or CONFIG_MANAGER.get_effective_api_base_url("")
        if not url:
            raise ValueError(_MSG_NO_URL)
        logger.info("API Key: %s" % _masked_key(resolved_key))
        logger.info("API URL: [已脱敏]")
        return resolved_key, url

    # ==================== 提交任务（spec §3.3 步骤 5） ====================

    def _submit_task(self, session, api_key, base_url, payload, timeout_s):
        """POST {base}/v1/videos 提交任务，返回 (task_id, response_json)。"""
        endpoint = _resolve_videos_url(base_url)
        headers = {
            "Authorization": "Bearer %s" % api_key,
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        logger.info("API URL: [已脱敏]")
        logger.info("Model: %s" % payload.get("model", _DEFAULT_MODEL))
        try:
            response = session.post(
                endpoint, json=payload, headers=headers, timeout=(15, timeout_s)
            )
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("API 调用失败: %s" % exc) from exc
        status_code = getattr(response, "status_code", 0)
        if status_code >= 400:
            raise RuntimeError(
                "API 调用失败: HTTP %s，响应片段: %s"
                % (status_code, _sanitize_response_text(getattr(response, "text", ""), 200))
            )
        try:
            response_json = response.json()
        except ValueError:
            raise RuntimeError("API 调用失败: 返回内容为空")
        task_id = _extract_task_id(response_json)
        if not task_id:
            raise RuntimeError(
                "创建任务成功，但未返回 task_id，响应片段: "
                + _sanitize_response_text(json.dumps(response_json, ensure_ascii=False, default=str), 200)
            )
        logger.info("任务ID: %s" % task_id)
        return task_id, response_json

    # ==================== 轮询（spec §3.3 步骤 6） ====================

    def _poll_task_until_completed(self, session, api_key, status_url, timeout_s):
        """GET {status_url} 轮询直至终态，返回 (video_url, final_response_json)。"""
        headers = {"Authorization": "Bearer %s" % api_key, "User-Agent": _USER_AGENT}
        started = time.monotonic()
        while True:
            _ensure_not_interrupted()
            elapsed = time.monotonic() - started
            if elapsed > timeout_s:
                raise RuntimeError("视频任务轮询超时（%d s）" % int(timeout_s))
            try:
                resp = session.get(status_url, headers=headers, timeout=(15, 60))
                if getattr(resp, "status_code", 0) >= 400:
                    raise RuntimeError(
                        "查询任务失败: HTTP %s" % getattr(resp, "status_code", 0)
                    )
                response_json = resp.json()
            except RuntimeError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("查询任务失败: %s" % exc)
                time.sleep(_POLL_INTERVAL_S)
                continue
            try:
                status = _extract_task_status(response_json).lower()
            except Exception as exc:  # noqa: BLE001
                logger.warning("查询任务失败: %s" % exc)
                time.sleep(_POLL_INTERVAL_S)
                continue
            progress = _extract_progress(response_json)
            logger.info("任务状态: %s | 进度: %s" % (status or "unknown", progress))
            if status in _VIDEO_DONE_STATUS:
                video_url = _absolutize_url(_extract_video_url(response_json), status_url)
                if not video_url:
                    raise RuntimeError("任务已完成，但未返回 video_url")
                return video_url, response_json
            if status in _VIDEO_FAILED_STATUS:
                message = _extract_error_message(response_json) or "上游任务失败"
                raise RuntimeError("视频任务失败: %s" % message)
            time.sleep(_POLL_INTERVAL_S)

    # ==================== 下载（spec §3.3 步骤 8） ====================

    def _download_video(self, session, video_url, api_key, timeout_s):
        """流式下载到 ComfyUI/output，文件名 sora2_video_ + 时间戳 + URL 扩展名。"""
        _ensure_not_interrupted()
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept-Encoding": "identity",
            "Authorization": "Bearer %s" % api_key,
        }
        logger.info("开始下载视频到 ComfyUI/output ...")
        output_dir = _get_output_dir()
        from urllib.parse import urlparse

        extension = os.path.splitext(os.path.basename(urlparse(video_url).path))[1]
        if not extension:
            extension = ".mp4"
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(output_dir, "%s%s%s" % (_OUTPUT_FILE_PREFIX, stamp, extension))
        counter = 1
        while os.path.exists(path):
            path = os.path.join(
                output_dir, "%s%s_%d%s" % (_OUTPUT_FILE_PREFIX, stamp, counter, extension)
            )
            counter += 1
        total = 0
        try:
            with session.get(
                video_url, headers=headers, stream=True, timeout=(15, timeout_s)
            ) as resp:
                status_code = getattr(resp, "status_code", 0)
                if status_code >= 400:
                    raise RuntimeError("下载视频失败: HTTP %s" % status_code)
                with open(path, "wb") as handle:
                    for chunk in resp.iter_content(chunk_size=256 * 1024):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        total += len(chunk)
        except RuntimeError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError("下载视频失败: %s" % exc) from exc
        if total <= 0:
            raise RuntimeError("下载视频失败: 返回内容为空")
        logger.info("视频已保存: %s（大小: %d KB）" % (path, total // 1024))
        return path

    # ==================== FUNCTION ====================

    def generate_video(self, **kwargs):
        """TE_image_pro_sora2_video：提交 → 轮询 → 下载，返回 (VIDEO, video_url, response)。"""
        _ensure_not_interrupted()
        prompt = str(kwargs.get("prompt") or "").strip()
        if not prompt:
            raise ValueError(_MSG_EMPTY_PROMPT)
        effective_model = str(kwargs.get("model") or _DEFAULT_MODEL).strip() or _DEFAULT_MODEL
        aspect_ratio = str(kwargs.get("aspect_ratio") or "16:9")
        resolution = str(kwargs.get("resolution") or "720p")
        seconds_value = str(kwargs.get("seconds") or "8")
        # seed：仅供 ComfyUI 工作流使用，不写入请求体（tooltip 实锤）
        try:
            timeout_s = min(3600, max(30, int(kwargs.get("timeout_s") or 900)))
        except (TypeError, ValueError):
            timeout_s = 900
        bypass_proxy = bool(kwargs.get("绕过代理"))

        api_key, base_url = self._resolve_key_and_url(
            kwargs.get("api_key"), kwargs.get("api_base_url")
        )
        session = _build_session(bypass_proxy)

        # ---- 参考图：多于 1 张时只取第 1 张（spec §3.3 步骤 1） ----
        image_tensor = kwargs.get("image")
        image_url = ""
        if image_tensor is not None:
            image_count = _count_batch_images(image_tensor)
            if image_count > 1:
                logger.info("参考图输入 %d 张，当前接口只使用第 1 张" % image_count)
            logger.info("参考图: 1 张")
            image_url = _encode_image_to_data_url(image_tensor)

        # ---- 请求体：model/prompt/seconds/aspect_ratio/resolution(+image_url)；无 seed ----
        payload = {
            "model": effective_model,
            "prompt": prompt,
            "seconds": seconds_value,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        if image_url:
            payload["image_url"] = image_url

        task_id, create_json = self._submit_task(session, api_key, base_url, payload, timeout_s)
        status_url = _resolve_videos_url(base_url) + "/" + str(task_id)
        video_url, final_json = self._poll_task_until_completed(
            session, api_key, status_url, timeout_s
        )
        video_path = self._download_video(session, video_url, api_key, timeout_s)
        logger.info("Video: %s" % video_url)
        video = _make_video_from_file(video_path)
        response_text = _sanitize_response_text(
            json.dumps(final_json, ensure_ascii=False, default=str)
        )
        return (video, video_url, response_text)

NODE_CLASS_MAPPINGS = {'TE_image_pro_sora2_video': BananaSora2VideoSafePyNode}
NODE_DISPLAY_NAME_MAPPINGS = {'TE_image_pro_sora2_video': 'TE MAN sora2 video'}
