#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线自检：不联网、不依赖 torch/ComfyUI，验证两个节点文件的纯 Python 逻辑。"""
import base64
import io
import json
import sys

sys.path.insert(0, ".")

from PIL import Image

from te_man_open.nodes.Grok_Image_Generator import (
    QUICK_FUNCTION_OPTIONS, QUICK_FUNCTION_PREFIXES,
    _absolutize_url, _collect_image_items_from_event_stream,
    _decode_valid_base64_image_bytes, _extract_image_refs_from_text,
    _is_valid_image_bytes, _looks_like_base64_blob, _resolve_chat_completions_url,
    _resolve_images_edits_url, _resolve_images_generations_url,
    _walk_json_for_image_items, BananaGrokImageSafePyNode,
)
from te_man_open.nodes.GPT_Image_2_Generator import (
    QUICK_FUNCTION_OPTIONS as GPT_QF, DIRECTOR_STORYBOARD_PROMPT_PREFIX,
    _format_api_error_payload, _resolve_gpt_image_2_endpoint,
    _resolve_gpt_image_2_task_endpoint, TEGPTImage2SafePyNode,
)

ok = True
def check(name, cond):
    global ok
    print(("PASS " if cond else "FAIL ") + name)
    ok = ok and bool(cond)

# ---------- Grok ----------
check("grok 快捷功能 7 项", QUICK_FUNCTION_OPTIONS == ("无", "白底三视图", "白底四视图", "九宫格[剧情]分镜", "九宫格[场景]分镜", "四宫格[剧情]分镜", "四宫格[视角]分镜"))
check("grok 前缀映射齐全", set(QUICK_FUNCTION_PREFIXES) == set(QUICK_FUNCTION_OPTIONS) and QUICK_FUNCTION_PREFIXES["白底三视图"].startswith("三视图（正面"))
check("grok chat url 纯主机", _resolve_chat_completions_url("http://localhost:8000") == "http://localhost:8000/v1/chat/completions")
check("grok chat url 带 /v1", _resolve_chat_completions_url("http://x.com/v1") == "http://x.com/v1/chat/completions")
check("grok chat url 带端点", _resolve_chat_completions_url("http://x.com/v1/chat/completions") == "http://x.com/v1/chat/completions")
check("grok generations url", _resolve_images_generations_url("x.com").endswith("/v1/images/generations"))
check("grok edits url", _resolve_images_edits_url("http://x.com/v1") == "http://x.com/v1/images/edits")
check("grok 绝对化 /v1/files", _absolutize_url("/v1/files/image/abc", api_base_url="http://h:8000/v1") == "http://h:8000/v1/files/image/abc")
check("grok 绝对化外链", _absolutize_url("https://a.com/x.png") == "https://a.com/x.png")

md = "![id](/v1/files/image/xxx) and ![b](https://a.com/p/q.jpg) text"
refs = _extract_image_refs_from_text(md)
check("grok markdown/URL 提取", refs == ["/v1/files/image/xxx", "https://a.com/p/q.jpg"])

# 生成一张真实 PNG 用于 base64 校验
buf = io.BytesIO(); Image.new("RGB", (128, 128), (255, 0, 0)).save(buf, format="PNG")
png = buf.getvalue()
b64 = base64.b64encode(png).decode()
check("grok 合法图片字节", _is_valid_image_bytes(png) and not _is_valid_image_bytes(b"not an image!!"))
check("grok base64 解码", _decode_valid_base64_image_bytes("data:image/png;base64," + b64) == png)
check("grok base64 blob 判定", _looks_like_base64_blob(b64) and not _looks_like_base64_blob("hello"))

items, texts = [], []
_walk_json_for_image_items(
    {"data": {"ai_message": "![x](/v1/files/image/a)", "b64_json": b64, "images": [{"image_url": {"url": "https://z.com/i.webp"}}]}},
    items, texts,
)
check("grok JSON 递归提取", any(i["kind"] == "base64" for i in items)
      and any(i["value"] == "https://z.com/i.webp" for i in items)
      and any("/v1/files/image/a" in r for r in _extract_image_refs_from_text("\n".join(texts))))

# SSE 流：伪 response
sse = ('data: {"choices":[{"delta":{"content":"partial ![p](/v1/files/image/s1)"}}]}\n\n'
       'data: {"data": {"b64_json": "%s"}}\n\n' % b64) + "data: [DONE]\n\n"
class FakeResp:
    def iter_content(self, chunk_size=8192):
        for i in range(0, len(sse), 7):
            yield sse[i:i+7].encode()
sse_items, sse_texts = _collect_image_items_from_event_stream(FakeResp())
check("grok SSE 解析", any(i["value"] == "/v1/files/image/s1" for i in sse_items)
      and any(i["kind"] == "base64" for i in sse_items))

# INPUT_TYPES 契约保持
it = BananaGrokImageSafePyNode.INPUT_TYPES()
check("grok INPUT_TYPES 键序", list(it["required"]) == ["prompt", "api_key", "api_base_url", "image_count", "size"])
check("grok 快捷功能默认", it["optional"]["快捷功能"][1]["default"] == "无")

# ---------- GPT ----------
n = TEGPTImage2SafePyNode
check("gpt 快捷功能 10 项顺序", GPT_QF[0] == "无" and GPT_QF[5] == "九宫格[导演]分镜" and GPT_QF[-1] == "黑白素写故事板")
check("gpt 导演故事板前缀", DIRECTOR_STORYBOARD_PROMPT_PREFIX.startswith("请生成一张中文专业电影故事板图片") and DIRECTOR_STORYBOARD_PROMPT_PREFIX.endswith("【故事内容】："))
check("gpt 尺寸 1K 16:9", n._resolve_request_size("1K", "16:9") == "1280x720")
check("gpt 尺寸 4K 5:4", n._resolve_request_size("4K", "5:4") == "3200x2560")
check("gpt 尺寸 2K 7:3", n._resolve_request_size("2K", "7:3") == "3024x1296")
check("gpt Auto", n._resolve_request_size("1K", "Auto") == "auto")
check("gpt 旧 WxH 兼容", n._normalize_ratio_label("1280x720") == "16:9")
check("gpt 未知比例回退", n._normalize_ratio_label("9:99") == "16:9")
check("gpt 模型 2→-2k", n._resolve_request_model("GPT Image 2", "2K") == "gpt-image-2-2k")
check("gpt 模型 2.5 无后缀", n._resolve_request_model("GPT Image 2.5", "4K") == "gpt-image-2.5")
check("gpt 线路1 1K 图生图保持 gpt-image-2", n._resolve_request_model("GPT Image 2", "1K", img2img=True, line_choice="线路1") == "gpt-image-2")
check("gpt 线路2 1K 图生图 → -1k", n._resolve_request_model("GPT Image 2", "1K", img2img=True, line_choice="线路2") == "gpt-image-2-1k")
check("gpt 线路1 1K 图生图走 edits", n._resolve_effective_img2img_endpoint_mode("线路1", "1K", True) == "edits")
check("gpt 线路1 2K 图生图保持 chat", n._resolve_effective_img2img_endpoint_mode("线路1", "2K", True) == "chat_completions")
check("gpt 线路2 统一 edits", n._resolve_effective_img2img_endpoint_mode("线路2", "4K", True) == "edits")
check("gpt 文生图走 generations", n._resolve_effective_img2img_endpoint_mode("线路2", "1K", False) == "generations")
check("gpt 线路2 剥可选字段", n._strip_line2_optional_fields({"model": "m", "quality": "high", "background": "auto", "output_format": "png"}) == {"model": "m"})
check("gpt 任务端点", _resolve_gpt_image_2_task_endpoint("http://x.com/v1", "t1") == "http://x.com/v1/images/tasks/t1")
check("gpt generations 端点", _resolve_gpt_image_2_endpoint("http://x.com", "/v1/images/generations", "/images/generations") == "http://x.com/v1/images/generations")
check("gpt 错误截断 500", len(_format_api_error_payload("x" * 900)) == 500 + len("...（错误响应已截断）"))

# chat 提取
gi = TEGPTImage2SafePyNode()
resp = {"choices": [{"message": {"content": "see https://img.a.com/1.png ok",
                                 "images": [{"image_url": {"url": "https://img.a.com/2.png"}}]}}]}
b, u = gi._extract_chat_completions_content(resp)
check("gpt chat 提取+去重", u == ["https://img.a.com/1.png", "https://img.a.com/2.png"] and not b)
try:
    gi._extract_chat_completions_content({"no": "choices"})
    check("gpt chat 无 choices 报错", False)
except RuntimeError as e:
    check("gpt chat 无 choices 报错", "没有 choices" in str(e))

# 同步 Images 提取 + task_id
sync = {"created": 1, "data": [{"b64_json": b64}, {"url": "https://d/3.jpg"}], "task_id": "abc"}
b64s, urls, tid = gi._extract_sync_gpt_image_2_content(sync)
check("gpt 同步提取", len(b64s) == 1 and urls == ["https://d/3.jpg"] and tid == "abc")

# 任务结果归一
norm = gi._normalize_task_result({"task_status": "SUCCESS", "data": [{"url": "https://d/4.png"}]})
check("gpt 任务归一", norm["status"] == "success" and norm["url_list"] == ["https://d/4.png"])

# 快捷功能拼接
p = n._compose_quick_function_prompt("内容", "白底三视图")
check("gpt 前缀拼接", p.startswith("三视图（正面、侧面、背面") and p.endswith("内容"))
p2 = n._compose_quick_function_prompt("内容", "黑白素写故事板")
check("gpt 黑白素写后缀拼接", p2.startswith("内容") and "16:9宽屏" in p2)
p3 = n._compose_quick_function_prompt("内容", "导演故事板")
check("gpt 导演故事板前后缀", "【故事内容】：内容" in p3 and p3.rstrip().endswith("。"))

print("\n== ALL PASS ==" if ok else "\n== SOME FAILED ==")
sys.exit(0 if ok else 1)
