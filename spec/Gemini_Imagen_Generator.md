# Gemini_Imagen_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_Gemini_Imagen_Generator`。静态分析（PE 导入/导出表 + ASCII/UTF-8 字符串 + 编码常量人工解码 + web/js 交叉引用）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

TE_MAN 插件中 **Gemini / "Banana"（Nano Banana，即 Gemini 图像模型）系列生图的在线 API 节点模块**，也是包内最大的节点 pyd（~399KB）。
自述 docstring（UTF-8 串）：
- `ComfyUI节点: NanoBanana图像生成，适配Gemini兼容端点` / `支持从config.ini读取API Key`（BananaImageNode）
- `ComfyUI 节点：Banana 特渠图像生成（固定 OpenAI Chat API 流式模式）`+`模型名称由分辨率和比例自动拼接，不暴露给前端用户手动输入`（BananaSpecialChannelNode）
- `ComfyUI 节点：TE banana特渠（/v1/videos 异步图像生成）`+`支持文生图与图生图；先提交任务，再轮询任务状态，完成后下载图片输出`（BananaSpecialAsyncNode）

原始编译路径：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Gemini_Imagen_Generator.py`，Python 包名 `custom_nodes.TE_image.Gemini_Imagen_Generator` [高]。

## 2. Python API

- 导出：`PyInit_Gemini_Imagen_Generator`（唯一导出）[高]。
- 导入表仅 `python3.dll / KERNEL32 / VCRUNTIME140 / CRT` —— **无 WinSock**，网络全部经 Python 层（`api_client.GeminiApiClient`，基于 requests）[高：导入表；请求层交叉引用 spec/api_client.md]。
- 模块级单例：`CONFIG_MANAGER`（`config_manager.ConfigManager`）、`API_CLIENT`（`api_client.GeminiApiClient`）[高：字符串字面量 `CONFIG_MANAGER`、`API_CLIENT`、`ConfigManager`、`GeminiApiClient`]。另有 `_DummyPromptServer`（PromptServer 不可用时的替身，具体用法 未确认）[高：名字存在]。
- 节点类（qualname 字符串 [高]）：
  - `BananaImageNode` — 主节点，四种 API 协议可选
  - `BananaSpecialChannelNode` — 特渠固定 Chat 流式
  - `BananaSpecialAsyncNode` — 特渠异步 `/v1/videos`
- 模块级工具函数（qualname [高]）：`_looks_like_base64_blob`、`_sanitize_debug_payload`、`_format_debug_payload`、`_sanitize_output_text`（内嵌 `_replace_data_uri`）、`_sanitize_error_text`、`_apply_quick_function_prompt(prompt, quick_function_value)`。
- ComfyUI 注册 [高 `NODE_CLASS_MAPPINGS`/`NODE_DISPLAY_NAME_MAPPINGS`/`CATEGORY`/`FUNCTION`/`RETURN_TYPES`/`RETURN_NAMES`/`OUTPUT_NODE`/`INPUT_TYPES` 字符串齐备]：
  - `TE_image_pro_banana`（映射键，字符串原文）[高]。显示名推断为 `TE MAN Gemini Image`（同区显示名类字符串）[中]。CATEGORY：`TE_MAN/Gemini`（字符串原文）[高]。
  - BananaSpecialChannelNode、BananaSpecialAsyncNode 的注册键 **未确认**；`TE_image_pro_special_async2`（web/js/grok_prompt_image_mentions.js 中，9 图片输入）与"特渠异步"节点特征吻合，推断为 BananaSpecialAsyncNode 的键 [中]；特渠流式键未确认。
  - 任务日志前缀（字符串原文）：`TE MAN Gemini 图像生成任务`、` Gemini 图像生成任务 (OpenAI API)`、` Gemini 图像生成任务 (Chat API)`、` Banana 特渠图像生成任务`、` TE banana特渠异步图像生成任务`、` Banana 特渠图像生成任务`。

## 3. 节点规格

### 3.0 通用机制

- **批次/多任务并发**（重点）[高：全部名字来自符号串]：
  - 输入 `batch_size` tooltip：`一次请求中要生成的图片数量，范围 1~8`。
  - 大批量循环拆批，各协议日志原文：`OpenAI 模式将循环调用 `、`Chat API 模式将循环调用 `、`Banana 特渠模式将循环调用 `（`...将循环调用 N 张图片...`）。
  - 并发执行利用 `task_runner.BatchGenerationRunner`（符号 `BatchGenerationRunner`、`run`、`tasks`）+ 工作线程与进度条 `comfy.utils.ProgressBar`（`progress_bar`、`progress_callback`、`completed_count/total_count`）。
  - 并发度控制：`max_workers`、`configured_workers`、`actual_workers`、`load_max_workers`、`load_network_workers_cap`、`configured_network_cap`、`network_workers_cap`、`peak_mode`（峰值模式，语义 未确认）、`stagger_delay`（错峰发起，语义 未确认）。
  - 发起计时同步对象：`request_start_lock` / `request_start_time` / `request_start_event` / `request_start_time_holder`；统计：`total_time`、`avg_time`、`time_info`、`平均速度`、`总耗时: `、`start_time`、`elapsed`。
  - 中断透传：`comfy.model_management.InterruptProcessingException`；`_ensure_not_interrupted` docstring：`统一的中断检查，复用 ComfyUI 原生取消机制`；另 `throw_exception_if_processing_interrupted`、`interrupt_checker`、` 已取消`。
- **解码管线**（image_codec 协作）[高：符号串]：输入 `IMAGE` 张量 → `prepare_input_image_data_urls`（转 data URL）→ 请求返回 base64 → `ImageCodec` 并行解码 `base64_to_tensor_parallel` / `decode_workers` / `decoded_tensors`；日志 ` 开始解码 `、` 图片解码完成，耗时 `。
- **失败呈现**：`build_error_tensor_from_text` + `ErrorCanvas`（image_codec）生成错误画布张量；`_build_failure_result` docstring：`构造统一的失败返回结构，便于上层聚合处理`；`build_preview_tuple` 组装预览 [中：仅名字]。
- **整体校验**：`continue_on_error`、部分失败汇总 `部分批次未返回图片：请求 ` + ` 张，实际上只生成 ` + ` 张图像（比例: `（含 `，分辨率: `）。

### 3.1 BananaImageNode

- FUNCTION 推断 `generate_images` / `generate_single_image`（`生成单张图片（用于并发）`，tooltip 原文）[高：方法名与中文串都在]。
- 输入（名称按 `_generate_with_gemini_api` 形参串与 tooltip 对应关系 [中]；类型 [中]）：
  - `prompt`：STRING 多行，`生成图像的文本提示词，可多行描述内容`；默认大概率 `一只可爱的小猫`（孤立中文串）[低]。
  - `api_key`：`调用服务的 API Key；留空则优先使用 config.ini 中的配置`；
  - `api_base_url`：`API 服务地址；留空则使用 config.ini 中的配置`；
  - API 协议（`model_type`）选项 tooltip 原文：`选择API格式：Gemini原生API | OpenAI Images API (/v1/images/*) | OpenAI Chat API (/v1/chat/completions)`；选项字符串：`Gemini原生API`、`Gemini原生流式`（第五种流式变体，走 `send_stream_request`，日志 `Gemini流式: `、`，流式=true`）、`OpenAI Images API`、`OpenAI Chat API` [高：选项串；归属到下拉 [中]]。
  - `batch_size`：INT，`一次请求中要生成的图片数量，范围 1~8`；
  - `aspect_ratio`：`生成图像的宽高比例，Auto 为由服务端自动决定`（默认 `Auto` [中]）；
  - `image_size`：`生成分辨率：1K / 2K / 4K`（`1K/2K/4K` 字符串）；
  - `top_p`：FLOAT，`采样参数 Top-P，数值越低越保守，越高多样性越强`；
  - `seed`：INT，`随机种子，-1 为自动随机；固定种子可复现同一输出`（`control_after_generate`、`base_seed`、`current_seed`、`随机种子: `）；
  - `quick_function`：`快捷功能`（`QUICK_FUNCTION_OPTIONS`/`QUICK_FUNCTION_PREFIXES`/`QUICK_FUNCTION_NONE`；tooltip `使用快捷功能生成`），选项即 3.4 的一键预设 [中：归并]；
  - `request_timeout`（ 连带 `connect_timeout`/`base_read_timeout`/`read_timeout` 解析）、`verify_ssl`（BOOLEAN）、`bypass_proxy`（BOOLEAN，标签 `绕过代理`，tooltip 合并缓存的 `梯子速度不佳`/`不可靠时开启`）[中]；
  - `image_1` … `image_9`：可选 IMAGE，tooltip 原文 `参考图像 {N}，可为空；用于图生图或多图融合` [高]。前端 JS（grok_prompt_image_mentions.js）对 `TE_image_pro_banana` 定义 9 个图片输入、`@图N` 引用 inserText [高]。
- 返回：`RETURN_TYPES` 含 `IMAGE` 与 `STRING`（两者都是该区裸类型字符串），配合 `build_preview_tuple`,OUTPUT_NODE 串存在 [中：具体元组序列/return_names 未确认]。
- 三条协议路径（方法名 [高]；请求体构建在 api_client 完成，字段证据见 spec/api_client.md §3.3）：
  1. `_generate_with_gemini_api` → `create_request_data(...)` + `send_request`/（流式时）`send_stream_request`；解析 `extract_content`。响应侧关注 `candidates`、`finishReason`（`模型未生成图片（finishReason=`、`NO_IMAGE`）[高]。
  2. `_generate_with_openai_api` → `create_openai_request_data`（返回 `(data_dict, files_list, is_img2img)`，text2img/img2img 由此转换，`response_format` 支持 `b64_json`）+ `send_openai_request`（同步路径而非轮询）+ `extract_openai_content` [高：函数名与 `api_response_format` 证据；调用链归属 [中]]。
  3. `_generate_with_chat_api` → `_generate_single_image_chat` → `create_chat_request_data` + `send_chat_request`（或 `send_chat_request_stream` 流式）+ `extract_chat_content`；无图但有字时报 `模型仅返回文本: `、`；模型返回文本: ` [高]。
- 并发拆分：`_generate_single_image_*` 是"用于并发"的单次任务函数（tooltip 原文），由 BatchGenerationRunner 多线程执行；`lambda2/3/4` 为排序/聚合闭包（具体 未确认）[高：qualname 存在]。

### 3.2 BananaSpecialChannelNode

- 固定 OpenAI Chat API 流式模式，不暴露模型下拉（docstring 原文见 §1）[高]。
- `_build_special_model_name`：请求模型名 = `_SPECIAL_MODEL_PREFIX` + `分辨率` + `比例` 拼接：
  - `分辨率；会自动拼接到模型名称中`、`图片比例；会自动映射到对应模型名`（tooltip 原文）；
  - `_SPECIAL_IMAGE_SIZES`（`1K/2K/4K`）、`_SPECIAL_ASPECT_RATIOS`（值 未确认，范围内一般含 `Auto` 及比例别名）；
  - `_SPECIAL_MODEL_PREFIX` 值 未确认（C 立即数）；日志 `使用基础模型: ` / `实际请求模型: `。
- 执行：`generate_images` → `_generate_with_special_stream_chat`（单批）→ `_generate_single_image_special_stream` → Chat 流式请求 → `extract_chat_content` [高：方法名]。
- 日志前缀 ` Banana 特渠图像生成任务`、循环提示 `Banana 特渠模式将循环调用 ` [高]。

### 3.3 BananaSpecialAsyncNode

- "特渠异步"：经 `/v1/videos` 端点做**异步图像生成**（docstring 原文：先提交任务，再轮询任务状态，完成后下载图片输出）[高]。
- 执行：`generate_images` → `_build_async_model_name`（`基础模型；会自动根据下方分辨率拼接实际请求模型名`；`_ASYNC_BASE_MODELS`、`_ASYNC_IMAGE_SIZES`、`_ASYNC_ASPECT_RATIOS`、`normalized_base_model`/`normalized_ratio`/`normalized_size`）→ `_generate_with_async_videos_api` → `_generate_single_image_special_async`：
  - 提交：`create_video_request_data` → `send_video_request` → `submit_response`；失败 `接口未返回任务 ID`（`task_id=` 日志）；
  - 轮询：`poll_video_task` + `poll_interval` / `max_poll_attempts` / `_status_endpoint`（api_client 的状态端点候选 `/v1/videos/{id}`、`/v1/images/tasks/{id}`，见其 spec）；
  - 提取/下载：`extract_video_content` / `parsed_image_urls`；日志 `://张` 附近 ` 参考图片 URL: `、`raw_input_url`、`input_image_urls`（支持图片通道与 URL 输入两种 [中]）；
  - 解码：`base64_to_tensor_parallel`（`input_images_b64`/`base64_images`）。
- 日志前缀 ` TE banana特渠异步图像生成任务`、`/v1/videos `、循环提示 `TE banana特渠将循环调用 ` [高]。

### 3.4 快捷功能预设（QUICK_FUNCTION 前缀提示词）

`_apply_quick_function_prompt` 将所选预设前缀拼到 prompt 前面（`QUICK_FUNCTION_PREFIXES` + `QUICK_FUNCTION_NONE`）[高：名字]。完整中文长提示词原文包含其中（节选 [高]）：
- `四宫格[剧情]分镜`：`根据提供的` + `剧情概述 / 画面主题 / 参考图` + `，生成一张具有清晰叙事推进关系的 2` + `2 四宫格分镜图，共 4 个连续镜头`……（整段约 15 句的视角/景别/一致性规则，结尾 `每个画面之间被清晰的黑色实线分割`）
- `九宫格[剧情]分镜`：同构 3x3 版本（`共 9 个连续镜头`）。
- `四宫格[视角]分镜`：`生成一张严格的2x2四宫格图像，纯视觉展示` + `场景标准透视效果图；俯视角度画面；正正前方视角；正后方视角` + `要求：四个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，`。
- `九宫格[场景]分镜`：`生成一张严格的3x3九宫格图像，纯视觉展示` + `正中央为场景标准透视效果图；正上方为俯视角度画面；正下方为地面纹理视角；左侧为左侧墙壁平视画面；右侧为右侧墙壁平视画面；四个角落分别是：正前方视角` + `正后方视角以及两个无文字的材质道具特写` ……。
- `白底三视图`：`参照原图生成人物面部特写搭配全身三视图组合画面； 画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照` + `侧面全身照` + `背面全身照，所有内容整合在 同一画幅内；采用纯白色背景，严格对齐人物人体比例 ，杜绝透视畸变问题，各视图之间间距均匀规整,无文字描述`；及短版前缀 `三视图（正面` `侧面全照`/`背面），白色纯色背景，人物角色设计图，`。
- `白底四视图`（同区字符串，正文细节与三视图稿不明 [中]）。

（长文各段由 `，`等分片形式编入，拼接顺序按 region 紧邻关系还原，[中]。）

## 4. 外部依赖与副作用

### 4.1 与内部支撑库协作（重点）

| 支撑库 | 使用点（符号串）[高] | 协作说明 |
|---|---|---|
| `config_manager` | `CONFIG_MANAGER`、`ConfigManager`、`load_api_key`、`get_effective_api_base_url`、`sanitize_api_key`、`load_max_workers`、`load_network_workers_cap`、`config.ini`、`解码内部测试 Base URL 失败，将回退到默认配置` | 节点读 `config.ini [gemini]` 的 `api_key`/`api_base_url`；Key 留空时回退节点输入；Key 日志打码；URL 未配时回退默认（config.ini 样例 `https://teynex.com`）；`max_workers`/`network_workers_cap` 控制并发。`MODULE_DIR`、`_decode_api_base_url` 串亦在本模块出现（测试节 URL 解码工具复用）。 |
| `api_client` | `API_CLIENT`、`GeminiApiClient`、`create_request_data`、`create_openai_request_data`、`create_chat_request_data`、`create_video_request_data`、`send_request`、`send_stream_request`、`send_openai_request`、`send_chat_request`、`send_chat_request_stream`、`send_video_request`、`poll_openai_task`、`poll_video_task`、`submit_response`、`extract_content`、`extract_openai_content`、`extract_chat_content`、`extract_video_content`、`_stream_endpoint`、`_status_endpoint`、`stagger_delay`、`retry_broken_stream` | 所有 HTTP/SSE/轮询经由 `GeminiApiClient`；本模块只组装参数与业务编排。端点表：Gemini `{base}/v1beta/models/{model}(:generateContent|:streamGenerateContent?alt=sse)`；OpenAI Images `{base}/v1/images/*`；Chat `{base}/v1/chat/completions`；特渠异步 `POST {base}/v1/videos` + 轮询 `/v1/videos/{task_id}`、`/v1/images/tasks/{task_id}`；认证 `Authorization: Bearer <key>`（详见 spec/api_client.md §4）。 |
| `image_codec` | `ImageCodec`、`ErrorCanvas`、`base64_to_tensor_parallel`、`build_error_tensor_from_text`、`build_preview_tuple`、`prepare_input_image_data_urls` | 输入图 tensor→dataURL，响应 base64→tensor 并行解码；错误文本→PNG 错误画布。与 spec/image_codec.md 的"消费方引用证据"一致。 |
| `task_runner` | `BatchGenerationRunner`、`tasks`、`InterruptProcessingException`、`throw_exception_if_processing_interrupted`、`interrupt_checker` | 批次/多图并发执行与 ComfyUI 中断透传（详见 spec/task_runner.md）。 |
| ComfyUI | `comfy.model_management`、`comfy.utils`、`ProgressBar`、`PromptServer`、`update_absolute`、`OUTPUT_NODE` | 进度条、中断异常、输出节点声明。 |

### 4.2 网络与配置键

- 端点：见 4.1 表与 spec/api_client.md §4（区间 Base URL：`config.ini [gemini] api_base_url = https://teynex.com` 样例 [高]）。
- 模型名清单（字符串原文 [高]）：`nano-banana-2`、`nano-banana-pro`、`gemini-2.0-flash-exp`、`gemini-3.1-flash-image-preview`、`gemini-3-pro-image-preview`、`gemini-3-pro-image`。归属：
  - `is_pro_image_model` / `pro_image_models` 集合判断（2K/4K 分辨率能力，由 `生成分辨率：1K / 2K / 4K` 推断），成员推断为 `nano-banana-pro`、`gemini-3-pro-image*` [中]；
  - `nano-banana-2`（api_client 中 OpenAI 请求默认模型）[中]；`gemini-2.0-flash-exp` 可能为 Gemini 原生模式的默认/候选 [低：归属未确认]。
  - 实际请求名日志 `模型名称: `、`使用模型: `、`实际请求模型: `、`使用基础模型: `。
- 文件系统：`config.ini`（读 key/url/workers）[高]；`banana_gemini_test.local.ini` 测试节（env `BANANA_GEMINI_USE_LOCAL_TEST`，见 spec/config_manager.md）[中：本模块交互推断]。
- 内嵌混淆常量（**重点发现**）：
  - `_FIX_API_BASE_URL_ENC` = base64 `b3Nzd3Q9KChmd24xMTEpfWJmZXJ1KWZ3dw==` → 逐字节 XOR 0x07 → **`https://api666.zeabur.app`**（人工解码验证 [高：解码过程可复现]）。配合 `_FIX_API_KEY_PREFIX`（前缀字面值 未确认，仅名字）与 `is_fix_mode`、`fix`、`raw_input_key` 符号 —— 机制推断：**模块内置一个"fix/内部测试专用渠道"的后备 Base URL（zeabur 部署）+ 特定前缀 API Key 识别**，解码失败时提示回退默认配置 [中：流程串联推断]。
  - `0123456789abcdef0123456789ABCDEF`（十六进制字母表）、`_DEBUG_BASE64_KEYS`、`masked_key` —— 推断为 Key 打码/调试脱敏工具 [低]。
  - `Peace and love`、`一只快乐的小猫` —— 孤立彩蛋/示例字符串（用途 未确认）。
- 网络/代理/SSL：`verify_ssl_flag`、`bypass_proxy_flag`、`connect_timeout`、`base_read_timeout`、`read_timeout`、`request_timeout`、`max_retries` —— 传递给 api_client 会话层 [高：参数名]。

## 5. 错误处理与用户可见文案

中文消息（UTF-8 串原文，括号内为触发场景推断 [中]）：

- `请在 config.ini 中配置 API Key 或在节点中填写` / `请在 config.ini 或节点输入中填写有效 API Key` —— 无可用 Key。
- `使用 API Key: `（脱敏日志）、`使用 API Base URL: [已脱敏]` —— 启动诊断。
- ` 使用 Gemini 原生 API 模式` / ` 使用 OpenAI Images API 模式` / ` 使用 OpenAI Chat API 模式` —— 协议模式日志。
- ` 开始请求...` / `🚀/️ 请求`（含表情主导的进度短语）—— 请求发起。
- ` 完成 - 生成 ` / ` 成功生成 ` / ` 成功生成 `、` 张图片` / ` 张图片...` / ` 张，实际生成` —— 批次完成。
- `完成，但未返回任何图片`（两次出现）—— 某批次/整体无图。
- `模型未生成图片（finishReason=`（含 `NO_IMAGE` 与长解释 `模型未生成任何图片（finishReason=NO_IMAGE，一般表示当前提示或参考图不触发图像输出，可能是内容被过滤或未通过安全审查）`）—— Gemini 原生无图原因。
- `模型未给出图片或说明文本，可能是服务端策略或参数设置导致本次未产出图片` —— 双路皆空。
- `模型仅返回文本: ` / `；模型返回文本: ` —— Chat 模式无图仅有字。
- `未生成任何图像` / `未知错误` / `生成失败` / `任务完成` / ` 已取消` —— 结果汇总与中断。
- `部分批次未返回图片：请求 ` + ` 张，实际上只生成 ` + ` 张图像（比例: ` + `，分辨率: ` + ` 张，请查看上方各批次日志中的'未返回任何图片'提示` —— 部分失败聚合。
- ` 开始解码 ` / ` 图片解码完成，耗时 ` —— 解码阶段日志。
- `接口未返回任务 ID` / `: task_id=` —— 特渠异步提交。
- `解码内部测试 Base URL 失败，将回退到默认配置` —— fix 渠道解码失败。
- `梯子速度不佳` / `不可靠时开启` —— bypass_proxy tooltip 片段。
- `统一的中断检查，复用 ComfyUI 原生取消机制` —— 中断函数 docstring。

## 6. 证据附录

### 6.1 模块身份（ASCII/qualname）
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Gemini_Imagen_Generator.c
custom_nodes/TE_image/source_py_backup/Gemini_Imagen_Generator.py
custom_nodes.TE_image.Gemini_Imagen_Generator(.BananaImageNode/.BananaSpecialChannelNode/.BananaSpecialAsyncNode)
EXPORT: PyInit_Gemini_Imagen_Generator   IMPORT: python3.dll, KERNEL32.dll, VCRUNTIME140.dll, api-ms-win-crt-runtime-l1-1-0.dll
```

### 6.2 注册与 UI
```
NODE_CLASS_MAPPINGS NODE_DISPLAY_NAME_MAPPINGS INPUT_TYPES RETURN_TYPES RETURN_NAMES FUNCTION CATEGORY OUTPUT_NODE required optional tooltip
TE_image_pro_banana     TE MAN/Gemini   TE MAN Gemini Image   STRING FLOAT INT BOOLEAN IMAGE
```

### 6.3 请求字段/协议相关
```
model_type batch_size aspect_ratio image_size top_p seed control_after_generate response_format b64_json
text2img img2img is_img2img files stream/流式=true use_gemini_stream candidates finishReason task_id poll_interval
max_poll_attempts submit_response status_response api_endpoint request_data input_images_b64 base64_images
data:image/(?P<mime>[a-zA-Z0-9.+-]+);base64,(?P<data>[A-Za-z0-9+/=\s]+)
(?<![A-Za-z0-9+/=])([A-Za-z0-9+/=]{512,})(?![A-Za-z0-9+/=])
[A-Za-z0-9+/=]+  [A-Za-z0-9+/=]{512,}  _LONG_BASE64_RE _DATA_IMAGE_RE
```
（正则用于识别响应文本里裸 base64 / data URI 图片，交互细节 未确认。）

### 6.4 模型名与混淆常量
```
gemini-3-pro-image-preview  gemini-3.1-flash-image-preview  gemini-3-pro-image
gemini-2.0-flash-exp  nano-banana-2  nano-banana-pro
b3Nzd3Q9KChmd24xMTEpfWJmZXJ1KWZ3dw==  --XOR 0x07-->  https://api666.zeabur.app
0123456789abcdef0123456789ABCDEF
```

### 6.5 并发/执行
```
BatchGenerationRunner run tasks worker_fn ThreadPool……(在 task_runner)
generate_images generate_single_image 生成单张图片（用于并发）
max_workers actual_workers configured_workers network_workers_cap load_max_workers load_network_workers_cap
concurrent_mode peak_mode stagger_delay continue_on_error progress_bar progress_callback completed_count total_count
request_start_lock request_start_time request_start_event request_start_time_holder
total_time avg_time 总耗时: 平均速度 [批次  ] 批次  批次数量:  总批次
```

### 6.6 内部协作符号
```
CONFIG_MANAGER  ConfigManager  load_api_key  get_effective_api_base_url  sanitize_api_key  MODULE_DIR
API_CLIENT  GeminiApiClient  create_request_data  create_openai_request_data  create_chat_request_data
create_video_request_data  send_request  send_stream_request  send_openai_request  send_chat_request
send_chat_request_stream  send_video_request  poll_openai_task  poll_video_task  submit_response
extract_content  extract_openai_content  extract_chat_content  extract_video_content
_stream_endpoint  _status_endpoint
ImageCodec  ErrorCanvas  base64_to_tensor_parallel  build_error_tensor_from_text  build_preview_tuple
prepare_input_image_data_urls  input_tensors  image_tensor  error_tensor  error_canvas decoded_tensors
comfy.model_management  comfy.utils  PromptServer  _DummyPromptServer  update_absolute
```

### 6.7 前端交互（web/js/grok_prompt_image_mentions.js）
```
'TE_image_pro_banana': 9 个 imageInputs（image_1..image_9, 图片1..9, @图N）
'TE_image_pro_special_async2': 9 个 imageInputs（image_1..image_9, 图片1..9, @图N）
```

### 未确认事项
- 两个特渠节点（BananaSpecialChannelNode / BananaSpecialAsyncNode）的准确注册键与显示名；`TE_image_pro_special_async2` 与特渠异步的对应为强推断。
- INPUT_TYPES 的容器分组（required/optional 划分）、默认值、类型精确元组（RETURN_TYPES/RETURN_NAMES 完整序列）——C 定义常量不可字符串化。
- `_SPECIAL_MODEL_PREFIX` 实际前缀值、`_FIX_API_KEY_PREFIX` 实际前缀值、`_ASYNC_BASE_MODELS` 成员列表、快取功能选项行的完整枚举顺序。
- `peak_mode`、`stagger_delay`、`_DummyPromptServer` 的确切用法；特渠异步响应是否复用视频接口扩展字段（`duration` 等）。
- `gemini-2.0-flash-exp` 等模型名的具体绑定（OpenAI 模式默认 vs Gemini 模式候选）。

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 环境真实加载采集（`Windows-2025Server-10.0.26100`，Python 3.13.16，ComfyUI 目录 `D:\a\_temp\ComfyUI`，TE_MAN 无导入错误）。本模块 pyd 类经明文包装层 `TE_MAN.Grok_Safe_PY` 暴露：`BananaImageNode` → `BananaGeminiImageSafePyNode`（键 `TE_image_pro_banana`）、`BananaSpecialAsyncNode` → `BananaGeminiAsyncSafePyNode`（键 `TE_image_pro_special_async2`），包装层在做输入图处理前透传参数。下表为**包装层最终暴露**的完整参数表。

### 7.1 运行时 INPUT_TYPES 全表

#### `TE_image_pro_banana`（BananaGeminiImageSafePyNode → 基类 BananaImageNode，显示名 `TE MAN Gemini Image`）

**required：**

| 参数 | 类型 | 选项 / 默认值 | 约束 | tooltip（原文） |
|---|---|---|---|---|
| `prompt` | STRING multiline | 默认 `一只可爱的小猫` | — | `生成图像的文本提示词，可多行描述内容、风格等` |
| `api_key` | STRING | 默认 `""` | — | `调用服务的 API Key；留空则优先使用 config.ini 中的配置` |
| `api_base_url` | STRING | 默认 `""` | — | `API 服务地址；留空则使用 config.ini 中的配置` |
| `model_type` | **STRING（非下拉）** | 默认 `gemini-3.1-flash-image-preview` | multiline false | `模型名称）`（原文即带右括号错字） |
| `batch_size` | INT | 默认 `1` | min 1 / max 8 | `一次请求中要生成的图片数量，范围 1~8` |
| `aspect_ratio` | combo | `Auto, 1:1, 9:16, 16:9, 21:9, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4`（**11 项，含 21:9**），默认 `Auto` | — | `生成图像的宽高比例，Auto 为由服务端自动决定` |
| `API格式` | combo | `Gemini原生API, OpenAI Images API, OpenAI Chat API`，默认 `Gemini原生API` | — | `选择API格式：Gemini原生API \| OpenAI Images API (/v1/images/*) \| OpenAI Chat API (/v1/chat/completions)` |

**optional：** `seed`（INT，默认 -1，min -1 / max 102400，control_after_generate true，tooltip `随机种子，-1 为自动随机；固定种子可复现同一输出`）、`top_p`（FLOAT，默认 **0.95**，min 0.0 / max 1.0 / step 0.01）、`image_size`（combo `1K/2K/4K`，默认 **`2K`**，tooltip `分辨率`）、`image_1`…`image_9`（IMAGE，tooltip `参考图像 N，可为空；用于图生图或多图融合`）、`绕过代理`（BOOLEAN 默认 false，tooltip `梯子速度不佳、不可靠时开启`）、`快捷功能`（combo 7 项同 Grok_Image 模块，默认 `无`）。

**运行时未暴露**：`Gemini原生流式` 选项（四种协议下拉被包装层裁成三种）、`request_timeout`、`verify_ssl`（§3.1 末行的超时/SSL 参数推断不成立）。

#### `TE_image_pro_special_async2`（BananaGeminiAsyncSafePyNode → 基类 BananaSpecialAsyncNode，显示名 **`TE MAN Gemini 特渠`**）

**required：**

| 参数 | 类型 | 选项 / 默认值 | 约束 | tooltip（原文） |
|---|---|---|---|---|
| `prompt` | STRING multiline | 默认 `一只快乐的小猫` | — | `生成图像的文本提示词` |
| `api_key` / `api_base_url` | STRING | 默认 `""` | — | 同上 |
| `model_type` | combo | `nano-banana-pro, nano-banana-2`，默认 `nano-banana-pro` | — | `基础模型；会自动根据下方分辨率拼接实际请求模型名` |
| `batch_size` | INT | 默认 `1` | min 1 / max 8 | `一次请求中要生成的图片数量，范围 1~8` |
| `aspect_ratio` | combo | `1:1, 16:9, 9:16, 4:3, 3:4`（5 项，**无 Auto**），默认 `4:3` | — | `宽高比` |
| `image_size` | combo | `1K, 2K, 4K`，默认 `1K` | — | `分辨率；会自动拼接到模型名称中` |

**optional：** `seed`、`image_1`…`image_9`、`绕过代理`、`快捷功能`（同上）。

#### `BananaSpecialChannelNode`（特渠固定 Chat 流式）

**已确认：当前发行版运行时未注册**——全量 30 个注册节点中没有任何键指向该类（`NODE_CLASS_MAPPINGS` 与其 `BananaImageNode`/`BananaSpecialAsyncNode` 均不含），即特渠流式节点在本版本不暴露给前端。

**注册元数据（实锤）**：两节点均为 `FUNCTION = "generate_images"`、`CATEGORY = "TE MAN/Gemini"`（**勘误**：§2 写作 `TE_MAN/Gemini`，实际为空格分隔的 `TE MAN/Gemini`）、`OUTPUT_NODE = True`、`RETURN_TYPES = ["IMAGE", "STRING"]`、`RETURN_NAMES = ["images", "text"]`；`method_docs`：`generate_single_image` → `生成单张图片（用于并发）`。

### 7.2 模块常量实锤值（动态采集，pyd 模块 `TE_MAN.Gemini_Imagen_Generator`）

- `MODULE_DIR = D:\a\_temp\ComfyUI\custom_nodes\TE_MAN`
- 基类层 `NODE_CLASS_MAPPINGS["TE_image_pro_banana"] = custom_nodes.TE_image.Gemini_Imagen_Generator.BananaImageNode`、显示名 `TE MAN Gemini Image`
- `QUICK_FUNCTION_NONE = "无"`；`QUICK_FUNCTION_OPTIONS`（7 项）：`无, 白底三视图, 白底四视图, 九宫格[剧情]分镜, 九宫格[场景]分镜, 四宫格[剧情]分镜, 四宫格[视角]分镜`；`QUICK_FUNCTION_PREFIXES` 各模板全文与 Grok_Image 模块同文，归属映射实锤：`白底三视图` → 短前缀 `三视图（正面、侧面、背面），白色纯色背景，人物角色设计图，`；`白底四视图` → 长模板 `参照原图生成人物面部特写搭配全身三视图组合画面；…`（§3.4 §6.5 中两句三视图文本的归属就此定案）
- **`_FIX_API_BASE_URL_ENC` / `_FIX_API_KEY_PREFIX` / `_SPECIAL_MODEL_PREFIX` / `_ASYNC_BASE_MODELS` / `_ASYNC_IMAGE_SIZES` / `_ASYNC_ASPECT_RATIOS` 未被 introspection 以模块常量形式采集**（推断为类属性或非常量容器）；静态解码值 `https://api666.zeabur.app`（XOR 0x07，§4.2）仍是唯一证据。 `_ASYNC_BASE_MODELS` / `_ASYNC_IMAGE_SIZES` / `_ASYNC_ASPECT_RATIOS` 的**成员可经包装层下拉间接实锤**：`["nano-banana-pro","nano-banana-2"]` / `["1K","2K","4K"]` / `["1:1","16:9","9:16","4:3","3:4"]`（默认 nano-banana-pro / 1K / 4:3）。

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2 / 末节 两个特渠节点的注册键与显示名 | **已确认：`TE_image_pro_special_async2` = 特渠异步（显示名 `TE MAN Gemini 特渠`）；特渠流式（BananaSpecialChannelNode）当前版本未注册**（动态回填） |
| §2 显示名 `TE MAN Gemini Image`（原[中]） | **已确认（动态回填）**；CATEGORY 勘误为 `TE MAN/Gemini` |
| 末节 `TE_image_pro_special_async2` 对应关系[中] | **已确认（动态回填）** |
| §3.1 `prompt` 默认 `一只可爱的小猫`（原[低]） | **已确认（动态回填）** |
| §3.1 `aspect_ratio` 选项与默认 Auto | **已确认：11 项（含 21:9），默认 Auto（动态回填）** |
| §3.1 `top_p` 默认值 | **已确认：0.95，step 0.01（动态回填）** |
| §3.1 `model_type` 下拉四种选项 | **已确认：运行时仅三种（`Gemini原生流式` 被包装层裁剪），且实际参数名为 `API格式`；`model_type` 在 banana 节点是自由 STRING（默认 gemini-3.1-flash-image-preview），在特渠异步节点是下拉（动态回填）** |
| §3.1 超时/verify_ssl 参数 | **已确认：运行时未暴露（动态回填）** |
| §3.2 `_SPECIAL_MODEL_PREFIX` 值 | 未采集，保持未确认（该节点未注册，意义有限） |
| §3.3 `_ASYNC_BASE_MODELS` / `_ASYNC_IMAGE_SIZES` / `_ASYNC_ASPECT_RATIOS` 成员 | **已确认（经下拉间接实锤）：见 §7.2（动态回填）** |
| §4.2 `_FIX_API_KEY_PREFIX` 实际前缀值 | 未采集，保持未确认 |
| §4.2 `一只快乐的小猫` 孤立彩蛋串 | **已确认：是特渠异步节点 `prompt` 默认值（动态回填）** |
| 末节 `peak_mode`/`stagger_delay`/`_DummyPromptServer` 用法 | 未采集，保持未确认 |
| 末节 `RETURN_TYPES` / `RETURN_NAMES` 完整序列 | **已确认：两节点均 `("IMAGE", "STRING")` / `("images", "text")`（动态回填）** |
| 末节 `gemini-2.0-flash-exp` 绑定 | 未采集，保持未确认；`gemini-3.1-flash-image-preview` **已确认**为 banana 节点 `model_type` 默认值（动态回填） |
