# Grok_Video_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出 `PyInit_Grok_Video_Generator`。静态分析（ASCII/UTF-8 字符串扫描 + 导入导出表），未跑代码。
> 置信度说明：[高] = 字符串直接/相邻证据；[中] = 强暗示推断；[低] = 猜测；无法确定的写"未确认"。

## 1. 模块定位

TE_MAN 插件的 **Grok 视频生成节点模块**（非 SKIP_MODULES 支撑库），内含两个 ComfyUI 节点类：
- `BananaGrokVideoNode` —— Grok 视频（grok-imagine-video 系列，线路1/线路2 双接口）
- `BananaGrokVideo3Node` —— Grok Video 3（grok-video-3 / grok-video-3-pro，chat/completions SSE 流式 + 异步任务）

模块限定名为 `custom_nodes.TE_image.Grok_Video_Generator`（源路径 `F:\ComfyUI_portable_TE_v260130\...\source_py_backup\Grok_Video_Generator.py`）[高]，说明包曾名 `TE_image`。README v2.1「grok 视频支持线路2，异步方式」与本模块的线路/异步结构吻合 [高]。

## 2. Python API

### 2.1 导出
- `PyInit_Grok_Video_Generator` [高]（唯一导出符号）
- 模块 docstring 原文 [高]：
  ```
  ComfyUI 节点：Grok 视频生成
  - 线路1：图片编码为 Base64 data URI，以 images 数组请求 /v1/videos JSON 接口
  - 线路2：图片编码为 Base64 data URI，以 image_url 字段请求 /v1/videos JSON 接口
  ```

### 2.2 模块级内部函数（限定名直接证据 [高]）
| 函数 | 推断作用 | 参数名（局部名字符串 [高]） |
|---|---|---|
| `_ensure_not_interrupted` | 检查 ComfyUI 中断（配 `throw_exception_if_processing_interrupted`、`comfy.model_management`） | — |
| `_resolve_chat_completions_url(api_base_url)` | 拼 `{base}/v1/chat/completions`（字符串 `/v1/chat/completions`），错误时提示「服务地址不要带 /v1/videos）」 | `api_base_url` |
| `_resolve_videos_url(api_base_url)` | 拼 `{base}/v1/videos`（字符串 `/v1/videos`、`/v1`、`/videos`、rstrip） | `api_base_url` |
| `_pick_video_url` / `_extract_video_url_from_response(response_json)` | 从 JSON 抽视频 URL（正则 `_URL_RE`=`https?://[^\s"'<>\\]+`、`_VIDEO_EXT_RE`=`\.(mp4|webm|mov|mkv)(\?|#|$)`、`_VIDEO_TAG_SRC_RE`=`<video ... src=...>`，IGNORECASE） | `response_json` |
| `_scale_image_tensor_to_total_pixels_if_needed(image_tensor, ...)` | 输入图按总像素自动缩放（`resolution_steps`、torch `movedim`/`unsqueeze`/`squeeze`/`nearest-exact`） | `image_tensor`、`resolution_steps` |
| `_encode_image_batch_to_data_urls` / `_encode_image_batch_to_png_files` | IMAGE 批 → Base64 data URI 列表 / PNG 文件部件；调用 `image_codec.encode_numpy_image_to_api_data_url` / `encode_numpy_image_to_api_file_part`（见 §5） | `field_name` |
| `_shape_to_hw_text` / `_count_batch_images` | 形状描述、统计批内张数（genexpr） | `shape` |
| `_scale_reference_image_if_needed(snapshot, label, image_tensor)` | 参考图超限缩放（`_MAX_INPUT_IMAGE_MEGAPIXELS`、`_OFFICIAL_SCALE_METHOD`，对齐 ComfyUI「Scale Image to Total Pixels」） | `label` |
| `_get_output_dir` / `_download_video(video_url, headers, timeout_s)` | 输出目录解析 / 流式下载（`stream`、`iter_content`、`chunk_size`、Accept-Encoding） | `video_url`、`timeout_s`、`headers` |
| `_video_config_payload(seconds, size, resolution_name, preset)` | 组装分辨率/时长配置字段 | `seconds`、`size`、`resolution_name`、`preset` |
| `_line1_ratio_from_size` | 线路1：由 `1792x1024` 等 size 字符串反推 aspect_ratio（错误「线路1不支持 size=」「…，已回退为 16:9」） | — |
| `_extract_video_task_id` / `_extract_video_task_status` | 从任务 JSON 抽 `video_id` / `status` | — |
| `_post_videos_async_and_get_download_url(endpoint, request_payload, ...)` | 线路的异步任务提交 + 轮询 → 下载 URL | `endpoint`、`request_payload` |
| `_resolve_grok_video_3_model_and_seconds` | 6s → `grok-video-3`；10/15s → `grok-video-3-pro`（文案「6 秒自动使用 grok-video-3；10/15 秒自动使用 grok-video-3-pro」） | — |
| `_post_grok_video_3_async_and_get_download_url(prompt_text, aspect_ratio, seconds_value, model, ...)` | Grok Video 3 提交 + SSE/轮询 → 下载 URL | 上述 |
| `BananaGrokVideoNode._extract_video_result_from_sse`（模块级同名函数） | 解析 SSE：`data:` 事件块 DoS 至 `[DONE]`（`consume_event_block`、`raw_events`、`decode_unicode`、`raw_text`） | — |

### 2.3 ComfyUI 节点注册
- 模块定义 `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` / `CATEGORY` / `FUNCTION` / `OUTPUT_NODE` / `RETURN_TYPES` / `RETURN_NAMES`（皆有符号串）[高]。
- `CATEGORY = "TE MAN/Grok"` [高]；`FUNCTION = "generate_video"` [高]（限定名含 `generate_video`）。
- 显示名 `TE MAN Grok Video` [高]。明文补丁 `zzzz_grok_autoscale_patch.py` 把注册键 `"TE_image_pro_grok_video"` 指向 SafePY 包装类 `BananaGrokVideoSafePyNode`（它 `from .Grok_Video_Generator import BananaGrokVideoNode as _BaseGrokVideoNode` 后改写 INPUT_TYPES/generate_video）[高]。即：实际注册的是包装，`BananaGrokVideoNode` 是包装的基类。
- `BananaGrokVideo3Node` 未出现在任何明文注册/包装中；其注册键与显示名 **未确认**（pyd 中有 `TE_image_pro_grok_video`、`BananaGrokVideo3Node.INPUT_TYPES` 限定名，但没有第三个 UI 字符串可对应）。
- 常量：`grok_video_`（输出文件名前缀，配 `.mp4`/`.png`）[高]；`User-Agent: ComfyUI-TE_API/1.0` [高]。
- 模块还含 `PromptServer` / `_DummyPromptServer` 兜底与 `_legacy_inputs`（旧工作流兼容标记，对应文案「旧工作流兼容项；线路2当前 JSON 请求不再提交此值」）[中]。

## 3. 节点规格

### 3.1 BananaGrokVideoNode（显示名 TE MAN Grok Video）

参数表以下列证据合成：pyd 局部名字符串 + 明文包装 `Grok_Safe_PY.py::BananaGrokVideoSafePyNode.generate_video` 签名（kwarg 名与默认值是**直接代码证据**，非推断）：
> `prompt, api_key="", api_base_url="", model="grok-imagine-video", seconds="10", size="1792x1024", resolution_name="720p", preset="normal", seed=-1, image, image_2..image_5, timeout_s=600, 绕过代理=False, 线路选择="线路1"`

| 输入 | 推断类型/默认 | 选项/说明 | 置信度 |
|---|---|---|---|
| prompt | STRING | 「用于生成视频的提示词」，空时「请输入 prompt」 | 高 |
| image, image_2..image_5 | IMAGE（可选） | 「线路1」文本；「Grok Video 3 输入图」组合；张数日志「…张（接口实际仅发送第 1 张）」→ 无论几张，接口只发第 1 张 | 高 |
| model | ["grok-imagine-video", "grok-imagine-video2"] | 「线路1使用此模型；线路2固定使用 grok-imagine-video2」；默认 grok-imagine-video | 高 |
| seconds | STRING/INT 选项 | 选项含 "6"、"10"、"15"（字符串直接证据）；tooltip「视频时长（秒）」 | 高 |
| size | ["1792x1024","1024x1792","1280x720","720x1280"] | tooltip「画面尺寸」？「清晰度，会写入 size」；线路1 用 `_line1_ratio_from_size` 反推比例；包装曾移除 `线路1清晰度` 名（向后兼容） | 中（tooltip 映射） |
| resolution_name | ["720p","480p","1080P"?] 等 | 「线路1通过 resolution 字段提交的分辨率；线路2不提交此值」，默认 720p | 中（完整选项列表未确认） |
| preset | ["normal","spicy","search"] | 三词相邻出现（268668/265124/265132）[高]；具体语义未确认 | 高(存在)/低(语义) |
| seed | INT, default -1 | `control_after_generate`；「仅供 ComfyUI 工作流使用；不会写入请求体」 | 高 |
| timeout_s | INT, default 600 | 「请求超时（秒）」 | 高 |
| 绕过代理 | BOOLEAN, default False | 「需要忽略系统代理/梯子时开启」；内部走 `Session.trust_env=False`（`trust_env`、`bypass_proxy` 符号）[高]；日志判级「直连无鉴权/直连鉴权/系统代理无鉴权/系统代理鉴权/…代理无鉴权」 | 高 |
| 线路选择 | ["线路1","线路2"] | 默认「线路1」；内部记作 `route`（`route_mode` 符号）[中]；另有串「线路12」「线路选择: 」日志 | 高 |
| api_key / api_base_url | STRING | 留空读 config_manager（见 §5）；「服务地址，如 https://api.example.com（不要带 /v1/videos）」 | 高 |
| aspect_ratio | STRING（旧输入） | 「画面比例，会写入 aspect_ratio」；选项字符 `16:9`/`9:16`/`1:1`/`2:3`/`3:2`；包装已把它从 required 中移除（兼容遗留） | 中 |

运行时还有自动缩放：`_scale_image_tensor_to_total_pixels_if_needed` + 「自动缩放: /未缩放: /(目标约 /(未超过约 …MP)」日志 [高]。

**行为流程（按字符串依赖重组）[中]：**
1. `_ensure_not_interrupted`（ComfyUI 中断即抛，`throw_exception_if_processing_interrupted`）。
2. `BananaGrokVideoNode._resolve_key_and_url`：key/URL 缺省 → `CONFIG_MANAGER.load_api_key()`（config.ini `[gemini] api_key`）、`get_effective_api_base_url()`；日志打码「API Key: (masked_key)」「API URL: [已脱敏]」。
3. 编码：`image_codec.encode_numpy_image_to_api_data_url` → data URI；线路1 走「Base64 data URI -> JSON images」，线路2 走「Base64 data URI -> JSON image_url」（两条日志明确）[高]。
4. `_video_config_payload` 组装 seconds/size/resolution/preset 字段（线路1 提交 resolution，线路2 不提交 [高]；线路1 若 size 不合要求回退 16:9 [高]）。
5. **同步路线**：POST `{base}/v1/videos`（`application/json`，`Authorization: Bearer <key>`），响应 JSON 经 `_extract_video_url_from_response` 抽 URL；失败文案「API 调用失败: /…HTTP …/返回内容为空/未在响应中解析到视频 URL。响应片段: …」。
6. **异步路线**（`use_async_videos` 符号 [高]；开关的 UI 名/默认值 未确认）：`_post_videos_async_and_get_download_url`：
   - POST `/v1/videos` 创建任务 → `_extract_video_task_id` 取 `video_id`（失败：「异步创建任务返回非 JSON: 」「异步创建任务成功，但未解析到 video_id。响应片段: 」）；
   - 轮询查询（`queries 查询视频任务失败: /查询视频任务返回非 JSON: `），状态机：成功集 `ready / completed / finished / succeeded`，失败集 `failed / expired / canceled / cancelled`（皆字符串直接证据）；`sleep` 间隔轮询，直至终态或超时：「异步视频任务轮询超时（…s）。任务ID: …」「异步视频任务失败。响应片段: 」；
   - 成功后 `_pick_video_url` 抽下载 URL → `_download_video`。
7. `_download_video`：`requests.Session` 流式分块下载（`iter_content`/`chunk_size`/`Accept-Encoding`）；若线路要求鉴权下载但无 Authorization →「下载视频失败: 当前线路要求鉴权下载，但未提供 Authorization 头」[高]；保存到 ComfyUI output（「开始下载视频到 ComfyUI/output ...」「视频已保存: …」，`grok_video_*` 前缀 + `.mp4`；`folder_paths.get_output_directory`）[高]。
8. 返回：`RETURN_TYPES` 含 `VIDEO`（并有 `VideoFromFile` / `_HAS_COMFY_VIDEO` / `comfy_api.input_impl` / `has_image` 符号，推断在 ComfyUI 带视频支持时用 VideoFromFile 包装视频为 VIDEO 输出，否则仅返回路径/预览 [中]）；`OUTPUT_NODE` [中]。
9. 各阶段间穿插 `_ensure_not_interrupted`（配合 `_legacy_inputs`）。

### 3.2 BananaGrokVideo3Node（Grok Video 3）

输入（字符串证据，UI 名→类型映射 [中]，具体完整 INPUT_TYPES 未确认）：

| 输入 | 证据与默认 |
|---|---|
| prompt | 「用于生成视频的提示词」；默认示例「猫咪听歌摇头晃脑，下大雨」（另一默认「生成一个西瓜切开里面是棉花糖的视频」更可能属于本节点）[中] |
| image / 输入图 | 「Grok Video 3 输入图」；编码为 Base64（线路 image_url 通道供线路2？未确认） |
| 参考图片/参考图片 1..5（可选） | 「参考图片（可选），会作为 input_reference 上传」[高]；「Grok Video 3 参考图收到 …张，当前接口仅发送第 1 张」→ 只发第 1 张 [高]；超限自动缩放（`_scale_reference_image_if_needed`，日志「自动缩放: /未缩放: 」）[高]；「input_reference[]」符号 [高] |
| seconds | 「6 秒自动使用 grok-video-3；10/15 秒自动使用 grok-video-3-pro」→ 选项 6/10/15 [高]；tooltip「视频时长（秒）」 |
| aspect_ratio | `16:9 / 9:16 / 1:1 / 2:3 / 3:2` 字符；错误「…，已回退为 16:9」[高] |
| api_key / api_base_url | 同上（note「API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）」）[高] |
| timeout（请求超时（秒））、seed、绕过代理 | 同 §3.1 |

**行为流程 [中]：**
1. `_resolve_key_and_url`（限定名 `BananaGrokVideo3Node._resolve_key_and_url`）[高]。
2. `_resolve_grok_video_3_model_and_seconds` 按时长选模型 [高]。
3. `_post_grok_video_3_async_and_get_download_url(prompt_text, aspect_ratio, seconds_value, model, …)`：POST `{base}/v1/chat/completions`（`_resolve_chat_completions_url`）[高]；接口以 SSE 流式返回（`data:` 块 + `[DONE]` 结束符，`decode_unicode`/`raw_text`）并调用 `_extract_video_result_from_sse` 消费事件块抽取视频/任务信息 [高]。
4. 若需轮询：任务状态/超时文案「Grok Video 3 异步任务失败。响应片段: 」「Grok Video 3 异步任务轮询超时（…s）。任务ID: …」「 Grok Video 3 任务」「重试」[高]。轮询端点具体格式 **未确认**（共享 `/v1/videos` 查询设施的可能性 [低]）。
5. 下载、保存、返回同 §3.1（共享 `_download_video`/`_get_output_dir`）[高，限定名共享]。

## 4. 外部依赖与副作用

### 4.1 网络端点与认证
- 端点（相对 base_url 拼）：`/v1/videos`（创建+查询，线路1/2）、`/v1/chat/completions`（Grok Video 3，SSE）[高]；`/videos`、`/v1`、`/content` 字符存在 [高]，`/content` 用途未确认（疑似下载 CDN 路径片段）[低]。
- 请求头：`Authorization: Bearer <api_key>`、`Content-Type: application/json`、`User-Agent: ComfyUI-TE_API/1.0`、`Accept-Encoding`（自动）[高]。
- 模型名：`grok-imagine-video`、`grok-imagine-video2`、`grok-video-3`、`grok-video-3-pro` [高]。
- 代理诊断：`trust_env`、四条「直连/系统代理 × 无鉴权/鉴权」日志串 [高]。

### 4.2 与内部支撑库协作
| 库 | 本模块引用的符号 [高——字符串] | 证据 |
|---|---|---|
| `config_manager` | `CONFIG_MANAGER`（全局实例）、`ConfigManager`、`load_api_key`、`get_effective_api_base_url`、`sanitize_api_key`、`masked_key` | K/V 直读 config.ini `[gemini] api_key` 与 base_url（见 spec/config_manager.md）；缺省错误文案三条：「请在 config.ini 中配置 API Key 或在节点中填写」「请在 config.ini 中配置 API URL 或在节点中填写」「未配置有效的 API URL」 |
| `image_codec` | `encode_numpy_image_to_api_data_url`（线路1/2 Base64 通道）、`encode_numpy_image_to_api_file_part`（PNG 文件部件；配 `files`、`field_name`、`.png`，用途未确认，疑似参考图上传通道）[低-中] | 见 spec/image_codec.md |
| `logger.py`（明文） | `logger` + `warning/info` 级调用 [中] | 符号串 |
| `api_client.pyd` / `task_runner.pyd` | **未引用**（字节搜索 `api_client`/`task_runner`=0 命中）[高] | 本模块自管 HTTP（requests.Session），不经过 api_client 封装 |
| `max_workers`/线程池 | **未出现**（`max_workers`/`concurrent`/`pool`/`executor` 均 0 命中）[高] | 带「Thread」的 3 处命中全是 Cython/Win32 内部名 |
| ComfyUI 生态 | `comfy.model_management`、`comfy.utils`(`common_upscale`)、`folder_paths.get_output_directory`、`comfy_api.input_impl`、`VideoFromFile`、`PromptServer`、`numpy/torch/requests/base64/json/re/math/io/typing` | 符号串 [高] |

### 4.3 文件系统
- 读：`config.ini`（经 config_manager）[高]。
- 写：ComfyUI 输出目录下 `grok_video_<...>.mp4`（另有 `.png` 触及，用意未确认）[中]。
- 日志打印 `<data_uri len=…>`、历史 `«线路…»` 等脱敏/摘要 [低]。

### 4.4 并发机制（重点澄清）
- **单次 `generate_video` 内不存在并发**：无线程池/asyncio.gather/并发请求的任何字符串证据 [高]；同步路线一请求一响应；异步路线 stick 到「提交→循环 sleep 轮询→下载」的串行单任务模型 [中]。
- 「多任务并发」由外部承担（README v2.1「与 ComfyUI TE 启动器配合，支持 API 并发」；v2.1「grok 视频支持线路2，异步方式」）：本模块以异步任务方式把创建/等待分离，多个节点实例可同时挂起各自轮询，由 ComfyUI 调度并行执行；TE 启动器侧并发能力不在本模块（未确认）[中]。
- `use_async_videos`（异步开关符号 [高]）是异步/同步的切换点；其 UI 输入名未确认。

## 5. 错误处理与用户可见文案

| 文案 | 触发场景 |
|---|---|
| 请输入 prompt | prompt 为空 |
| 请在 config.ini 中配置 API Key 或在节点中填写 / 请在 config.ini 中配置 API URL 或在节点中填写 / 未配置有效的 API URL | key/url 缺省或无效 |
| 未在响应中解析到视频 URL。响应片段: | 同步响应无视频 URL |
| 异步创建任务返回非 JSON: / 异步创建任务成功，但未解析到 video_id。响应片段: | 异步提交阶段 |
| 查询视频任务失败: / 查询视频任务返回非 JSON: | 异步轮询阶段 |
| 异步视频任务轮询超时（…s）。任务ID: … / Grok Video 3 异步任务轮询超时（…s） | 轮询超时 |
| 异步视频任务失败。响应片段: / Grok Video 3 异步任务失败。响应片段: | 任务终态失败 |
| API 调用失败: / : HTTP / 返回内容为空 | HTTP/请求异常 |
| 线路1不支持 size= / ，已回退为 16:9 | 线路1 参数非法回退 |
| 下载视频失败: / 下载视频失败: 当前线路要求鉴权下载，但未提供 Authorization 头 | 下载阶段 |
| 缺少图像依赖（numpy）: / 不支持的 IMAGE 维度: | 无 numpy / 图形形状异常 |
| 参考图收到 …张，当前接口仅发送第 1 张 / 参考图数量: / 参考图: / 多图日志 | 多图提示 |
| 自动缩放: / 未缩放: / (目标约 …MP) (未超过约 …MP) | 自动缩放决策信息 |
| 日志打码：API Key: (masked_key) / API URL: [已脱敏] | 认证脱敏 |

## 6. 证据附录

### 端点/协议
```
/v1/videos    /videos    /v1    /content    /chat/completions    /v1/chat/completions    [DONE]    data:
https?://[^\s\"'<>\\]+    \.(mp4|webm|mov|mkv)(\?|#|$)    <video[^>]*\bsrc=[\"']([^\"']+)[\"']    IGNORECASE
Authorization    Bearer     User-Agent    ComfyUI-TE_API/1.0    Content-Type    application/json    Accept-Encoding    trust_env
```
### 任务状态与字段
```
video_id    status    ready    completed    finished    succeeded    failed    expired    canceled    cancelled    unknown    disabled    id    create
视频任务查询：查询视频任务失败: /查询视频任务返回非 JSON: /异步视频任务轮询超时（…s）。任务ID: /异步视频任务成功，但未解析到 video_id
sleep    timeout    timeout_s    status_code    response_info
```
### 模型/选项
```
grok-imagine-video    grok-imagine-video2    grok-video-3    grok-video-3-pro
6 秒自动使用 grok-video-3；10/15 秒自动使用 grok-video-3-pro
1792x1024 1024x1792 1280x720 720x1280 720p 720P 480p 1080P    16:9 9:16 1:1 2:3 3:2    normal spicy search    6 10 15
```
### 文案（原样摘录）
```
ComfyUI 节点：Grok 视频生成
    - 线路1：图片编码为 Base64 data URI，以 images 数组请求 /v1/videos JSON 接口
    - 线路2：图片编码为 Base64 data URI，以 image_url 字段请求 /v1/videos JSON 接口
    将 ComfyUI 的 IMAGE tensor（BHWC, float[0..1]）编码成 data:image/...;base64,...
    返回 (图片数量, data_urls)
    Align oversized reference images with ComfyUI's "Scale Image to Total Pixels" logic.
    Only downscale when the source image exceeds the configured total pixels.
传图方式: Base64 data URI -> JSON images    传图方式: Base64 data URI -> JSON image_url
参考图片（可选），会作为 input_reference 上传    参考图片 1（可选）…5（可选）    input_reference[]
线路1通过 resolution 字段提交的分辨率；线路2不提交此值    线路1使用此模型；线路2固定使用 grok-imagine-video2
画面比例，会写入 aspect_ratio    清晰度，会写入 size    视频时长（秒）    请求超时（秒）    仅供 ComfyUI 工作流使用；不会写入请求体
旧工作流兼容项；线路2当前 JSON 请求不再提交此值    服务地址，如 https://api.example.com（不要带 /v1/videos）
需要忽略系统代理/梯子时开启    直连无鉴权 直连鉴权 系统代理无鉴权 系统代理鉴权 …代理无鉴权
开始下载视频到 ComfyUI/output ...    视频已保存: …    生成成功
API Key；留空则读取 config.ini    API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）
API Key:   API URL: [已脱敏]    线路选择:   线路1  线路2  线路12(未确认)    route_mode(内部名)  use_async_videos(内部名)
```
### 类/函数符号（去噪）
```
BananaGrokVideoNode    BananaGrokVideo3Node    INPUT_TYPES    _resolve_key_and_url    generate_video
_ensure_not_interrupted    _resolve_videos_url    _resolve_chat_completions_url    _post_videos_async_and_get_download_url
_post_grok_video_3_async_and_get_download_url    _resolve_grok_video_3_model_and_seconds    _extract_video_result_from_sse(.consume_event_block)
_extract_video_task_id    _extract_video_task_status    _extract_video_url_from_response    _pick_video_url
_video_config_payload    _line1_ratio_from_size    _scale_image_tensor_to_total_pixels_if_needed    _scale_reference_image_if_needed
_MAX_INPUT_IMAGE_MEGAPIXELS    _OFFICIAL_SCALE_METHOD    _encode_image_batch_to_data_urls    _encode_image_batch_to_png_files
_count_batch_images    _shape_to_hw_text    _get_output_dir    _download_video    _legacy_inputs    _DummyPromptServer
Category: TE MAN/Grok    Display: TE MAN Grok Video    key: TE_image_pro_grok_video    prefix: grok_video_
```

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 环境真实加载采集（`Windows-2025Server-10.0.26100`，Python 3.13.16，ComfyUI 目录 `D:\a\_temp\ComfyUI`，TE_MAN 无导入错误）。实际注册类是明文包装层 `TE_MAN.Grok_Safe_PY.BananaGrokVideoSafePyNode`（经 `zzzz_grok_autoscale_patch` 以同名注册键覆盖），下表为**包装层最终暴露**的完整参数表；pyd 基类 `BananaGrokVideoNode` 的内部行为（双线路 payload、轮询、下载）不受影响。

### 7.1 运行时 INPUT_TYPES 全表（`TE_image_pro_grok_video`，包装层暴露）

**required：**

| 参数 | 类型 | 选项 / 默认值 | 约束 | tooltip（原文） |
|---|---|---|---|---|
| `prompt` | STRING multiline | 默认 `生成一个西瓜切开里面是棉花糖的视频` | — | `用于生成视频的提示词`（该默认示例**实锤属于本节点**，非 GrokVideo3Node） |
| `api_key` | STRING | 默认 `""` | — | `API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）` |
| `api_base_url` | STRING | 默认 `""` | — | `服务地址不要带 /v1/videos）`（原文即缺少左半句的截断串） |
| `model` | **STRING（非下拉）** | 默认 `grok-imagine-video` | multiline false | `线路1使用此模型；线路2固定使用 grok-imagine-video2` |
| `seconds` | combo | `10, 15`（字符串选项），默认 `"10"` | — | `视频时长（秒）` |
| `size` | combo | `720x1280, 1280x720, 1024x1792, 1792x1024`，默认 **`1280x720`** | — | `画面尺寸` |
| `resolution_name` | combo | `480p, 720p`，默认 `720p` | — | `线路1通过 resolution 字段提交的分辨率；线路2不提交此值` |
| `preset` | combo | `fun, normal, spicy, custom`，默认 `normal` | — | `旧工作流兼容项；线路2当前 JSON 请求不再提交此值` |

**optional：**

| 参数 | 类型 | 选项 / 默认值 | 约束 | tooltip（原文） |
|---|---|---|---|---|
| `seed` | INT | 默认 `-1` | min -1 / max 102400 / `control_after_generate: true` | `仅供 ComfyUI 工作流使用；不会写入请求体` |
| `image` | IMAGE | — | — | `参考图片 1（可选）` |
| `image_2` … `image_5` | IMAGE（共 5 口） | — | — | `参考图片 N（可选）` |
| `timeout_s` | INT | 默认 `600` | min 30 / max 3600 | `请求超时（秒）` |
| `绕过代理` | BOOLEAN | 默认 `false` | — | `需要忽略系统代理/梯子时开启` |
| `线路选择` | combo | `线路1, 线路2`，默认 **`线路2`** | — | `线路12`（原文即截断串「线路12」，与静态分析的孤立串互证） |

**与 §3.1 静态合成表的差异（以运行时为准）**：`model` 是自由 STRING 而非两值下拉；`seconds` 仅 `10/15`（`6` 不在本节点下拉中）；`size` 默认 `1280x720`（包装签名曾写 `1792x1024`）且顺序不同；`preset` 下拉为 `fun/normal/spicy/custom`（**无 `search`**，spec 中三词相邻的 `search` 不入 UI）；`线路选择` 运行时默认 `线路2`；`aspect_ratio` 旧输入未暴露（与「包装已从 required 移除」一致）；`use_async_videos` 无独立 UI 开关（异步经 `线路选择=线路2` 承担）。

**注册元数据（实锤）**：`FUNCTION = "generate_video"`、`CATEGORY = "TE MAN/Grok"`、`OUTPUT_NODE = True`、`RETURN_TYPES = ["VIDEO", "STRING", "STRING"]`、`RETURN_NAMES = ["video", "video_url", "response"]`。

### 7.2 模块常量实锤值（动态采集，pyd 模块 `TE_MAN.Grok_Video_Generator`）

- `_HAS_COMFY_VIDEO = True`（§3.1 第 8 步 VIDEO 输出实锤在 ComfyUI 视频支持存在时启用）
- `_MAX_INPUT_IMAGE_MEGAPIXELS = 1.0`、`_OFFICIAL_SCALE_METHOD = "nearest-exact"`
- `MODULE_DIR = D:\a\_temp\ComfyUI\custom_nodes\TE_MAN`
- 基类层 `NODE_CLASS_MAPPINGS["TE_image_pro_grok_video"] = custom_nodes.TE_image.Grok_Video_Generator.BananaGrokVideoNode`、显示名 `TE MAN Grok Video`（随后被包装层覆盖为 SafePy 类）

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2.3 `OUTPUT_NODE`（原[中]） | **已确认：True（动态回填）** |
| §2.3 / §3.2 `BananaGrokVideo3Node` 注册键 | **已确认：当前发行版运行时未注册**——全量 30 个注册节点无第三个 Grok 视频键，Grok Video 3 节点在本版本不暴露（其 prompt 默认示例「生成一个西瓜切开里面是棉花糖的视频」实锤移入本节点）（动态回填） |
| §3.1 `RETURN_TYPES`（原[中]） | **已确认：`("VIDEO", "STRING", "STRING")` / `("video", "video_url", "response")`（动态回填）** |
| §3.1 `seconds` 选项 | **已确认：`10 / 15`（6 属未注册的 GrokVideo3Node）（动态回填）** |
| §3.1 `size` 默认与顺序 | **已确认：`720x1280, 1280x720, 1024x1792, 1792x1024`，默认 `1280x720`（动态回填）** |
| §3.1 `resolution_name` 完整选项 | **已确认：`480p / 720p`，默认 720p，无 1080P（动态回填）** |
| §3.1 `preset` 选项与语义 | **已确认选项：`fun / normal / spicy / custom`，默认 normal；语义未确认（动态回填）** |
| §3.1 `model` 两值下拉推断 | **已确认：字段为自由 STRING，`grok-imagine-video`/`grok-imagine-video2` 仅是 tooltip 说明而非选项（动态回填）** |
| §3.1 `线路选择` 默认 | **已确认：运行时默认 `线路2`（静态包装签名层的 `线路1` 不符，以 UI 实测为准）（动态回填）** |
| §4.4 `use_async_videos` 的 UI 输入名 | **已确认：运行时无此输入——异步/同步切换由 `线路选择` 承担（动态回填）** |
| §4.4 并发机制 | introspection 未采集到并发参数（与「无线程池」负证据一致），维持单任务串行 + 外部并发的结论 |
| `size` tooltip | **已确认：最终 UI 为 `画面尺寸`（「清晰度，会写入 size」未用于暴露的下拉）（动态回填）** |
