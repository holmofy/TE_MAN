# api_client.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_api_client`。静态分析（strings / 导入导出表）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

内部支撑库（在 `__init__.py` SKIP_MODULES 中，不注册 ComfyUI 节点）。模块 docstring 自述："**封装与 Gemini 兼容图像接口交互的 HTTP 客户端**"。它是全部 *.pyd 生成器（GPT_Image_2 / Gemini_Imagen / Grok_Image / Grok_Video / Jimeng_Video / Sora_2 / TE_Bernini / TE_HappyH / TE_VEO / TE_MAN_Chat 等，未逐个验证，[低]）共用的网络请求层，统一封装：URL 构建、请求头/认证、中断响应式请求（后台线程）、SSE 流解析、轮询（task_id）、内容提取、余额（token 用量）查询。原始编译路径为 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\api_client.c`，Python 侧包名 `custom_nodes.TE_image.api_client` [高]。

## 2. Python API

- 导出：`PyInit_api_client` [高]；导入依赖仅 python3.dll / KERNEL32 / VCRUNTIME140 / CRT —— 无直接 WinSock 导入，网络走 Python 层 [高]。
- 模块路径字符串：`custom_nodes/TE_image/source_py_backup/api_client.py` [高]。
- 引用 `config_manager`（配置加载）与 `logger_instance`（logger 注入点） [高]。
- `__all__` 存在 [高]（具体内容未确认）。
- 模块级函数（均为下划线工具函数，非 ComfyUI 注册）：
  - `_looks_like_base64_blob(value)` [高，签名形参名 = 字符串证据]
  - `_sanitize_debug_payload(parent_key, items...)` [高]
  - `_format_debug_payload(...)` [高]
  - `_sanitize_text_payload(max_chars)`（内含嵌套函数 `_replace_data_uri`）[高]
  - `_shorten_url_for_log(max_len)` [高]
  - `sanitize_api_key(...)` [高] —— 日志中打码 API Key
- 类 `GeminiApiClient`：全部 HTTP 能力的承载者，方法见 §3。无 NODE_CLASS_MAPPINGS / INPUT_TYPES / CATEGORY 证据 —— 确认为纯内部库 [高]。

## 3. 内部接口（GeminiApiClient）

置信度：方法名全部来自 Cython 符号/qualname 字符串 [高]；参数名来自 `Optional[...]`/typing 字符串推断 [中]。

### 3.1 归一化
- `_normalize_aspect_ratio(aspect_ratio)`：宽高比别名表 `_ASPECT_RATIO_ALIASES`；出现的比例值：`1:1, 16:9, 21:9, 9:16, 4:3, 3:4, 2:3, 3:2, 5:4, 4:5` [高]
- `_normalize_image_size(image_size)`：合法值 `1K/2K/4K`（docstring 原文），另有 `auto` [中]（"auto" 可能是默认值）
- `_normalize_resolution(...)`：同上，产出 `normalized_aspect` / `normalized_size` [中]

### 3.2 输入图像处理
- `_split_input_image_payload`：把 base64 图片列表拆为请求可用载荷 [中]
- `_image_extension_from_mime(mime_type)`：mime→扩展名，证据：`image/png / image/jpeg / image/gif / image/webp`、`.png .jpeg .webp .jpg .gif` [高]
- `_input_image_to_data_url`：把输入图编为 `data:image/...;base64,...`（正则 `_DATA_IMAGE_RE`：`data:image/(?P<mime>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)`） [高]

### 3.3 请求体构建（四套协议）
1. `create_request_data(prompt, input_images_b64, model_type, ...)` — **Gemini 原生 generateContent 格式**。请求字段 [高]：`contents, inlineData, fileData, fileUri, mimeType, generationConfig, responseModalities, imageConfig, aspectRatio, imageSize`；响应字段：`candidates, finishReason, promptFeedback, usageMetadata, modelVersion, responseId` [高]
2. `create_openai_request_data(prompt, seed, aspect_ratio, model_type, image_size, response_format, input_images_b64, ...)` — **OpenAI 兼容图像 API**。docstring 原文：返回 `(data_dict, files_list, is_img2img)`；text2img → JSON，img2img → form data + multipart files；`response_format`（`url 或 b64_json`）[高]；带 `webhook` 回调参数 [高]
   - 默认模型字符串 `nano-banana-2` [中]（紧邻 create_request_data 相关符号，推断为模型默认值）
3. `create_chat_request_data(..., top_p, ...)` — **Chat Completions**（`messages, model, stream, top_p`）[高]
4. `create_video_request_data(prompt, input_image_urls, duration, ...)` — **视频生成**（`duration` 时长字段）[中]

### 3.4 发送与轮询
- `send_request(..., max_retries)` — Gemini generateContent，带重试（`_MAX_RETRIES`, `_BASE_BACKOFF`, `effective_max_retries`, `attempt_delay`）[高]
- `send_stream_request(..., stream_parser)` — Gemini `streamGenerateContent` SSE
- `send_openai_request(api_key, request_data, files, api_base_url, is_img2img, timeout, bypass_proxy, verify_ssl, webhook) -> task_id` — docstring 原文"异步任务ID"；失败报"API 未返回 task_id" [高]
- `poll_openai_task(api_key, task_id, api_base_url, timeout, bypass_proxy, verify_ssl, max_poll_attempts, poll_interval) -> "完整的任务响应数据（包含 status, data 等）"` [高]
- `send_video_request / poll_video_task / extract_video_content` — 视频提交/轮询/提取 [高]
- `send_chat_request / send_chat_request_stream` — Chat 同步与 SSE 流式（聚合为统一 `chat.completions` 结构，见 docstring）[高]

### 3.5 底层请求设施
- `_get_session()` — `requests.Session` + `HTTPAdapter(mount, pool_connections, pool_maxsize)`；代理控制：`trust_env, proxies, bypass_proxy, session_no_proxy`（绕过代理时另建无代理 session）[高]
- `_build_headers(...)` — 见 §4 请求头
- `_resolve_timeout(...)` → 返回 `(connect_timeout, read_timeout)`（`Tuple[float, float]` [高]）；默认值常量 `_DEFAULT_CONNECT_TIMEOUT` / `_DEFAULT_READ_TIMEOUT` 存在 [高]，**数值未确认**（编译期整数不可见字符串）
- `_interruptible_post / _interruptible_stream_post` — 核心设计（docstring 原文）："让网络请求在长耗时阶段也能响应 ComfyUI 的中断 / 使用后台线程发起请求，主线程轮询中断标志，必要时关闭 session 终止阻塞。支持 JSON 模式 payload(bytes) 与 Multipart 模式 data(dict)+files(list)"。实现符号：`threading.Thread(daemon), Event(done_event), resp_holder, result_holder, exc_holder, interrupt_checker` [高]
- `_ensure_not_interrupted(interrupt_checker)` [高]
- `_suppress_insecure_warning` — `filterwarnings / InsecureRequestWarning / urllib3 / disable_warnings`（verify_ssl=False 时屏蔽告警，模块级标志 `_INSECURE_WARNING_SUPPRESSED`）[高]
- `_summarize_error_response` — docstring 原文："提取对用户安全的错误摘要，避免暴露源站费用或请求 ID 等细节" [高]

### 3.6 URL 构建
- `_build_generate_content_url(base_url)`；`_build_stream_generate_content_url` [高]
  - 端点拼接证据：`v1beta/`, `/v1beta/models/`, `models/`, `:generateContent`, `:streamGenerateContent`, `?alt=sse`, `&alt=sse`, `alt=`
  → 即 `{base}/v1beta/models/{model}:generateContent` 与 `{base}/v1beta/models/{model}:streamGenerateContent?alt=sse` [高]
- `_build_chat_completions_url` — ` /v1/chat/completions`、`/chat/completions`（两种后缀兼容，可能 base 已含 /v1 时用短版）[中]
- `_build_balance_urls` — 余额查询多候选 URL：`/api/usage/token` [高]；候选集具体列表未确认
- `_status_endpoint` / `status_url` / `api_endpoint` — 轮询地址构建器 [高]；任务状态端点候选 [高]：`/v1/videos/`（+task_id）、`/v1/videos`、`/v1/images/tasks/`（图像任务轮询）

### 3.7 流式（SSE）解析
- 原语：`iter_lines, data: / event: 前缀, [DONE] 终止符, text/event-stream` [高]
- `_iter_json_objects_from_text(payload_text)`：`JSONDecoder.raw_decode` 松散抽取 JSON 对象（处理非标准流）[高]
- Gemini 流：`_consume_gemini_stream_event` → `_parse_gemini_stream_response`（内联 `_has_final_image_result` / `_flush_event`, `data_lines`）→ `_build_aggregated_gemini_stream_result`；聚合 `raw_events`；断流兜底："Gemini 流式响应尾部异常断开，但已收到有效内容，将继续使用已聚合结果" [高]
- Chat 流：`_consume_chat_stream_event` → `_collect_stream_chat_parts`（genexpr, choice0）→ `_parse_chat_stream_response` → `_build_aggregated_stream_result` [高]
- `_append_stream_text / _append_stream_image_candidate(seen_images 去重) / _append_image_once` [高]
- 断流判定 `_is_broken_stream_error`：匹配 `ConnectionError, ChunkedEncodingError, ProtocolError` 及报错文本：`connection reset / incomplete read / connection aborted / remote end closed / connection broken / bad status line / invalidchunklength / protocolerror / broken pipe / response ended prematurely` [高]；命中后"流式传输异常断开，尝试使用 Connection: close 重试一次"（头部 `Connection`）+ `retry_broken_stream / retry_headers` [高]

### 3.8 内容提取
- `extract_content(response_data)` — Gemini 响应 → `(images_b64_list, text)`（`Tuple[List[str], str]` [高]）；从 `candidates[].content.parts[].inlineData.data` 提取（`inlineData, mimeType, data` 字段）[中]
- `extract_openai_content` — docstring 给出响应结构原文：`"data": {"status": "SUCCESS", "data": {"data": [{"url": "...", "b64_json": "..."}]}}`；状态字面量 `SUCCESS / FAILURE / failed / completed / progress` [高]
- `extract_chat_content` — docstring 结构原文：`choices[].message.{content, images:["base64_1",...]}`；内含三个嵌套函数：`_append_b64 / _download_url_to_b64 / _extract_from_text`（genexpr）[高]
- 文本/链接提取正则 [高]：`\[.*?\]\((https?://[^\)]+)\)`（Markdown 链接）、`!\[[^\]]*\]\(([^)]+)\)`（Markdown 图片）、`<img[^>]+src=["']([^"']+)["']`（HTML img）、`data:image\/[a-zA-Z0-9.+-]+;base64,(...)`/`\"b64_json\"\s*:\s*\"([A-Za-z0-9+/=\s]+)\"`（裸 base64）、`(https?://[^\s\)\]\}>'\"\\]+)`（裸 URL）
- 下载：Markdown 图片 / Gemini 图片 URL → base64（`b64decode/b64encode, BytesIO`），记录 `download_started_at`、耗时，Content-Type 校验（"下载内容疑似非图片"）[高]
- 视频内容提取 `extract_video_content`（具体字段未确认）

### 3.9 余额 / Token 用量
- `fetch_token_usage(...)` → `_build_balance_urls` 得到候选 → 请求 `/api/usage/token`，认证头 `X-API-Key` [高]；文档提及 "token quota" [高]
- 兜底行为：404 →"404 未找到余额查询端点"；未配地址 →"未配置 Balance API 地址"；无 key →"请提供有效的 API Key 后再查询余额" [高]

## 4. 外部依赖与副作用

### 网络端点（全部相对 `api_base_url`，样例配置 `https://teynex.com`，见 config.ini `[gemini]` 段）[高]

| 协议 | 端点 | 用途 | 证据 |
|---|---|---|---|
| Gemini 原生 | `POST {base}/v1beta/models/{model}:generateContent` | 图像生成（同步） | `:generateContent` [高] |
| Gemini 原生 | `POST {base}/v1beta/models/{model}:streamGenerateContent?alt=sse` | 图像生成（SSE 流式） | `:streamGenerateContent`、`?alt=sse` [高] |
| OpenAI 兼容 | `POST {base}/v1/images/generations` | text2img（JSON） | [高] |
| OpenAI 兼容 | `POST {base}/v1/images/edits` | img2img（multipart） | [高] |
| Chat | `POST {base}/v1/chat/completions`（兼容 `/chat/completions`） | 文本/多模态对话 | [高] |
| 轮询 | `GET {base}/v1/videos/{task_id}`、`/v1/images/tasks/{task_id}`、以及 `_status_endpoint` 动态构建 | 异步任务状态查询 | [高/具体形参未确认] |
| 视频 | `POST {base}/v1/videos` | 视频生成提交（`/v1/videos` 多处出现） | [高] |
| 余额 | `{base}/api/usage/token`（多候选） | token 用量/余额查询 | [高] |

### 请求头与认证 [高]
- `Authorization: Bearer <API Key>`（`Bearer ` 存在；OpenAI 式全部接口）
- `X-API-Key: <key>`（余额接口）
- `X-Banana-Client`（自定义标识头）
- `User-Agent: ComfyUI-TE_API/1.0`
- `Content-Type: application/json`；流式另带 `Accept: text/event-stream`
- 断流重试追加 `Connection: close`
- Gemini 原生接口用哪种 key 传递（Bearer/查询参数/x-goog-api-key）**未确认**
- 日志脱敏：`sanitize_api_key`、`X-Banana-Client/Authorization` 头值经 `sanitized_key` 处理 [中]

### 行为配置
- 超时：`_DEFAULT_CONNECT_TIMEOUT` / `_DEFAULT_READ_TIMEOUT` [高，数值未确认]；可全局覆盖 `read_timeout_global` [高]
- 重试：`_RETRYABLE_STATUS`（[高，成员未确认]，结合"请求限流，延长等待时间"推断含 429 [低]）、`_MAX_RETRIES`、`_BASE_BACKOFF` [数值均未确认]
- 连接预算：`exceeded_connect_budget` — 连接阶段单独限时，超限报"连接阶段耗时过长或无法建立，请检查代理 / DNS 或 Base URL 域名是否可达" [高]
- 代理：`bypass_proxy` 时用无代理 Session（`trust_env=False` 推断 [中]）
- SSL：`verify_ssl` 透传 `session.verify`；False 时屏蔽 InsecureRequestWarning [高]
- 依赖 Python 库：`requests / urllib3 / threading / typing / urllib.parse / base64 / json / re / warnings / logger / config_manager` [高]

## 5. 错误处理与用户可见文案

[高] 均为字符串原文；"…"处为 f-string 拼接点：

- 认证/配置：`请填写有效的 API Key`；`API Key 无效或已过期`；`未配置有效的 API Base URL`；`请提供有效的 API Key 后再查询余额`；`未配置 Balance API 地址`
- 输入校验：`请输入提示词或提供至少一张参考图像`；`未提供有效的任务 ID`
- 网络：`网络连接失败: …`；`连接阶段耗时过长或无法建立，请检查代理`；`DNS 或 Base URL 域名是否可达`（拼接）；`模型响应过慢，超过读取时间上限`；`… 已超过读取上限 …`；`响应超时：总耗时 …`
- 中断/重试：`请求被中断或未获得响应`；`… 响应中途断开：`；`生成阶段连接被远端关闭：`；`… s 内未返回数据，可能仍在生成；为避免重复请求干扰，已停止自动重试`；`… 次请求失败（错误类型：…，请检查 API 服务与网络状态，或联系服务提供者`
- 定时/限流：`任务超时: 超过 … 次轮询仍未完成`；`轮询超时 (尝试 …`；`轮询请求限流，延长等待时间`；`轮询异常 (尝试 …`；`轮询超时: 网络不稳定或服务响应慢`
- 协议/解析：`接口返回数据格式异常`；`响应中无图像数据`；`响应中无图像地址`；`响应中无 choices 数据`；`解析 OpenAI 响应失败: …`；`解析 Chat API 响应失败: …`；`Chat API 响应中未解析到图片`；`Chat API finish_reason=…`；`流式请求结束，但未解析到有效响应`；`数据格式错误: …`；`API 未返回 task_id`；`轮询返回数据格式异常`；`轮询状态失败: HTTP …`；`远端返回异常（HTTP …`
- 流式断流：`Gemini 流式响应尾部异常断开，但已收到有效内容，将继续使用已聚合结果`；`流式传输异常断开，尝试使用 Connection: close 重试一次`；`流式响应尾部异常断开，但已收到有效内容，将继续使用已聚合结果`；`Chat Stream API 请求失败: `；`Gemini Stream API 请求失败: `
- 下载：`下载图片失败: …`；`下载失败，状态码: …`；`下载内容疑似非图片: Content-Type=…`；`下载生成图片失败`；`收到 Gemini 图片URL，开始下载:`；`收到 Markdown 图片URL，开始下载:`；`成功下载图片，大小: …`；`Gemini 图片URL下载完成，耗时 …`；`Markdown 图片下载完成，耗时 …`
- 余额：`余额不足：账户额度不足以完成本次请求，请充值后重试`；`余额查询失败，错误摘要: …`；`余额接口返回格式错误`；`404 未找到余额查询端点`
- 其他：`HTTP 状态码: …`；`HTTP 请求失败`；`content 前 300 字符预览: …`；`/v1/videos 请求失败: …`；`/v1/videos 轮询超时 (尝试 …`；`/v1/videos 轮询异常 (尝试 …`；`/v1/videos 任务状态: …`

调试脱敏机制 [中]：`_DEBUG_BASE64_KEYS` + `<base64 omitted chars=N>` 截断占位、`... <truncated chars=N>`、`_shorten_url_for_log`、`message keys=…` —— 长日志（base64/URL）替换为截断占位。

## 6. 证据附录

### 端点/URL（原文）
```
/v1beta/models/   /models/   v1beta/   :generateContent   :streamGenerateContent
?alt=sse   &alt=sse   alt=   :generate
/v1/images/generations   /v1/images/edits   /v1/chat/completions   /chat/completions
/v1/videos   /v1/videos/   /v1/images/tasks/   _status_endpoint   status_url
/api/usage/token
https://   http://   models/
```

### 请求头/认证（原文）
```
Authorization   Bearer    X-API-Key   X-Banana-Client
User-Agent   ComfyUI-TE_API/1.0   Content-Type   application/json
Accept   Connection   text/event-stream   Connection: close (retry_headers)
```

### 常量名（原文）
```
_DEFAULT_CONNECT_TIMEOUT   _DEFAULT_READ_TIMEOUT   read_timeout_global
_RETRYABLE_STATUS   _MAX_RETRIES   _BASE_BACKOFF   effective_max_retries
attempt_delay   retry_broken_stream   retry_headers   exceeded_connect_budget
_INSECURE_WARNING_SUPPRESSED   _ASPECT_RATIO_ALIASES   _DATA_IMAGE_RE
_DEBUG_BASE64_KEYS   _thread_local   global_start   fallback_images
```

### Gemini 协议字段（原文）
```
contents   inlineData   fileData   fileUri   mimeType   generationConfig
responseModalities   imageConfig   aspectRatio   imageSize
candidates   finishReason   promptFeedback   usageMetadata   modelVersion   responseId
```

### OpenAI 兼容响应结构（docstring 原文）
```
"data": { "status": "SUCCESS",
          "data": { "data": [ {"url": "...", "b64_json": "..."} ] } }
状态字面量: SUCCESS FAILURE failed completed progress   [DONE]
```

### Chat 响应结构（docstring 原文）
```
{ "choices": [ { "message": { "content": "...", "images": ["base64_1", "base64_2"] } } ] }
```

### 正则（原文）
```
data:image/(?P<mime>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)
data:image\/[a-zA-Z0-9.+-]+;base64,([A-Za-z0-9+/=\s]+)
\"b64_json\"\s*:\s*\"([A-Za-z0-9+/=\s]+)\"
!\[.*?\]\((https?://[^\)]+)\)      !\[[^\]]*\]\(([^)]+)\)
<img[^>]+src=["']([^"']+)["']      (https?://[^\s\)\]\}>'\"\\]+)
[A-Za-z0-9+/=]+   \s+
```

### 断流错误匹配词（原文）
```
connection reset   incomplete read   connection aborted   remote end closed
connection broken   bad status line   invalidchunklength   protocolerror
broken pipe   response ended prematurely   ChunkedEncodingError   ProtocolError
ConnectionError   ConnectTimeout   Timeout   HTTPError   RequestException
JSONDecodeError
```

### 会话/线程（原文）
```
requests.Session   HTTPAdapter   mount   pool_connections   pool_maxsize   trust_env
proxies   bypass_proxy   session_no_proxy   verify   threading   Thread   daemon
Event   done_event   resp_holder   result_holder   exc_holder   interrupt_checker
filterwarnings   InsecureRequestWarning   urllib3   disable_warnings
```

### docstring 关键句（原文摘录）
```
封装与 Gemini 兼容图像接口交互的 HTTP 客户端
让网络请求在长耗时阶段也能响应 ComfyUI 的中断 / 使用后台线程发起请求，
主线程轮询中断标志，必要时关闭 session 终止阻塞
返回 task_id: 异步任务ID (send_openai_request)
返回: (images_b64_list, text_response) / (data_dict, files_list, is_img2img)
提取对用户安全的错误摘要，避免暴露源站费用或请求 ID 等细节
```

### 其他标识
- 编译源：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\api_client.c` [高]
- 日志命名空间线索：`comfyui-te_api` [中]；外部配置引用：`config_manager` [高]
- 默认模型线索：`nano-banana-2` [中]；宽高比别名值与 `1K 2K 4K auto` 见 §3.1

## 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据源：GitHub Actions Windows + ComfyUI 真实环境运行时 introspection 快照，目标文件 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN\api_client.pyd`。以下为运行时模块属性/命名空间实测。

### (a) 模块 docstring
模块级 `__doc__` 为空。运行时证实正文引用的"封装与 Gemini 兼容图像接口交互的 HTTP 客户端"实为**类 `GeminiApiClient` 的 docstring**（原文：`封装与 Gemini 兼容图像接口交互的 HTTP 客户端。`），类的 `__module__` 报 `custom_nodes.TE_image.api_client`（编译期包名保留，真机目录已是 TE_MAN）。

### (b) 模块级常量（实锤值）
运行时模块常量表仅含：
| 常量 | 实测值 | 说明 |
|---|---|---|
| `MODULE_DIR` | `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN` | 真机运行目录 |

**关键负证据**：`_DEFAULT_CONNECT_TIMEOUT`、`_DEFAULT_READ_TIMEOUT`、`_MAX_RETRIES`、`_BASE_BACKOFF`、`_RETRYABLE_STATUS`、`_ASPECT_RATIO_ALIASES`、`_DEBUG_BASE64_KEYS`、`_INSECURE_WARNING_SUPPRESSED` 等常量名**未出现在模块级命名空间**——说明它们是**类属性或函数局部实现细节**（挂靠在 `GeminiApiClient` 上），而非模块级常量；数值仍未实测（此批 introspection 未下钻类属性）。"候选集具体列表未确认"（余额 URL、`_RETRYABLE_STATUS` 成员）维持未确认，但**归属层级已修正：类属性级，非模块级**。

### (c) function_docs（编译保留的 docstring）
模块命名空间中带 docstring 的对象仅捕获到 typing 导入名（`Any`/`Callable`/`Dict`/`List`/`Optional`/`Tuple`），业务函数无 docstring 保留，无新增。
类级命名空间实锤（imports 类文档）：
- `GeminiApiClient`：本模块自有类（doc 见上）。
- `HTTPAdapter`（`requests.adapters`）：完整 docstring 命中，其中参数文档 `pool_connections`（"The number of urllib3 connection pools to cache"）、`pool_maxsize`（"The maximum number of connections to save in the pool"）与 §3.5 `_get_session()` 的连接池参数一一对应——佐证连接池配置确实经 `HTTPAdapter(mount(...))` 注入。
- `InsecureRequestWarning`（`urllib3.exceptions`）：佐证 §3.5 `_suppress_insecure_warning` 的屏蔽对象。

### (d) 未确认项核对结论
- `__all__` 存在但内容未确认：维持（introspection 未导出该列表）。
- 超时/重试常量数值：**未确认（新增归属证据：非模块级，应在类属性中查找）**。
- 默认模型 `nano-banana-2` [中]：维持——运行时常量表中无该字符串常量（若为参数默认值则属函数签名默认，无法由此批数据证实）。
- Gemini 原生接口 key 传递方式：维持未确认。
- 佐证（consumers）：`nodes` 数据显示 `TE_image_pro_gpt_image_2`、`TE_image_pro_grok_image`、`TE_image_pro_grok_video`、`TE_image_pro_banana`、`TE_image_pro_sora2_video`、`TE_image_pro_happyh_video`、`TE_image_pro_te_veo_video`、`TE_image_pro_special_async2` 共 8 个注册节点的 `module` 字段同为 `TE_MAN.Grok_Safe_PY`——Grok_Safe_PY 是 api_client 的最大单一消费者聚合层（与静态"全部生成器共用网络层"结论吻合）。
