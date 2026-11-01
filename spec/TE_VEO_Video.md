# TE_VEO_Video.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_VEO_Video`（PE 导出表唯一导出符号）。导入依赖仅 python3.dll / KERNEL32 / VCRUNTIME140 / CRT —— 无 WinSock，网络全走 Python 层 `requests` [高]。静态分析（pefile 导入/导出表 + ASCII/UTF-8 字符串提取）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

**节点模块**：TE_MAN（原包名 `custom_nodes.TE_image`，编译源路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_VEO_Video.c`、原始 .py 路径 `custom_nodes/TE_image/source_py_backup/TE_VEO_Video.py` [高]）中的 **Google VEO 视频生成节点**，注册为 ComfyUI 节点 `TE_image_pro_te_veo_video`（类 `BananaTEVeoVideoNode`，显示名 `TE MAN VEO Video`），对应 README v2.3 所述"TE VEO 节点，支持 VEO 3 fast 生成视频。支持首帧,首尾帧,图参"（README.md:363）。模块 docstring 原文：`ComfyUI 节点：TE veo video / - POST /v1/videos 提交任务 / - GET /v1/videos/{task_id} 轮询状态` [高]。任务日志标题 `🎬 TE veo video 任务` [高]。

## 2. Python API

- 导出：`PyInit_TE_VEO_Video` [高]。
- 模块级函数（qualname 全部来自 Cython 符号串 [高]；形参名来自紧邻符号 [中]）：
  - 中断：`_ensure_not_interrupted`（配合 `comfy.model_management.throw_exception_if_processing_interrupted` [高]）
  - URL/响应解析：`_resolve_videos_submit_url(api_base_url?)`、`_resolve_videos_fetch_url(task_id?)`、`_read_json_response_or_raise(resp?, label?)`、`_absolutize_url(raw_url?, endpoint?)`、`_extract_video_url(values?)`
  - 输出：`_get_output_dir`、`_download_video(video_url?, api_key?, timeout_s?)`（形参线索紧邻 [中]）
  - 类 `_DownloadedVideoFromFile`，方法 `save_to`（含英文注释原文 `Keep downloaded API videos usable when PyAV cannot stream-copy them.` [高]）—— 下载视频的 ComfyUI VIDEO 类型包装/回退保存器
  - 图像编码：`_scale_image_tensor_to_total_pixels_if_needed`（内部符号 `resolution_steps`、`_OFFICIAL_SCALE_METHOD`、`_MAX_INPUT_IMAGE_MEGAPIXELS`、`common_upscale`、`nearest-exact` [高]）、`_encode_image_batch_to_data_urls`、`_encode_single_image_to_data_url`、`_encode_single_image_to_png_file_part`
  - 模型/尺寸归一化：`_normalize_output_profile(value?)`、`_normalize_model_variant`、`_resolve_video_model(output_profile?, model_variant?)`、`_resolve_video_size(aspect_ratio?, ...)`、`_resolve_720p_video_size`、`_is_auto_video_option`、`_summarize_for_log`
- 类 `BananaTEVeoVideoNode`：唯一节点类，方法 `INPUT_TYPES`、`_resolve_key_and_url`、`generate_video`（含子生成器 genexpr）[高]。
- 模块常量 [高，名称]：`_FAST_MODEL_NAME_720P / _FAST_MODEL_NAME_1080P / _FAST_MODEL_NAME_4K / _FAST_MODEL_NAME_1080P_FL / _FAST_MODEL_NAME_4K_FL`、`_LITE_MODEL_NAME / _LITE_MODEL_VARIANT`、`_DEFAULT_MODEL_VARIANT / _DEFAULT_OUTPUT_PROFILE`、`_MODEL_VARIANT_OPTIONS / _OUTPUT_PROFILE_OPTIONS / _ROUTE_OPTIONS`、`CONFIG_MANAGER`、`MODULE_DIR`、`_HAS_COMFY_VIDEO`。
- ComfyUI 节点注册 [高]：`NODE_CLASS_MAPPINGS` 键 `TE_image_pro_te_veo_video`，显示名 `TE MAN VEO Video`，`CATEGORY: TE MAN/Veo`，`FUNCTION: generate_video`，`RETURN_TYPES / RETURN_NAMES / OUTPUT_NODE` 字符串存在 [高]。

## 3. 与 api_client 的协议层关系（重点）

**本模块不使用 `api_client.GeminiApiClient`** —— 与 Jimeng_Video_Generator 同属"自带协议层"的独立节点：

- 全文件 **0 处** `api_client` 字节命中（亦无 `GeminiApiClient / send_openai_request / poll_openai_task / send_video_request / poll_video_task / create_video_request_data` 任一符号），二进制内不存在对该模块的任何限定名引用 [高]。
- 但拥有与 api_client **同构的自研请求层**（符号/字符串 [高]）：`requests.Session`、`headers`、`post`、`iter_content`、`raise_for_status`、`timeout`、`trust_env`、`requests.exceptions / Timeout / RequestsJSONDecodeError / JSONDecodeError`、`Authorization: Bearer <key>`、`User-Agent: ComfyUI-TE_API/1.0`、`Content-Type: application/json`、代理旁路 `bypass_proxy / trust_env`、日志脱敏 `API URL: [已脱敏] / sanitize_api_key / masked_key`、`_ensure_not_interrupted` 中断协议。
- **复用的内部库**：
  - `config_manager`（符号 `config_manager / ConfigManager / CONFIG_MANAGER / load_api_key / get_effective_api_base_url / sanitize_api_key` [高]；该函数簇定义于 config_manager.pyd，见 spec/config_manager.md）—— API Key 与 Base URL 解析
  - `image_codec`（符号 `image_codec / encode_numpy_image_to_api_file_part` [高]，可能含 `encode_numpy_image_to_api_data_url` [中]；该函数定义于 image_codec.pyd，见 spec/image_codec.md）—— 参考图编码
  - `logger` [高]
- 与 api_client 的**字符串重合**（如 `/v1/videos`、`ComfyUI-TE_API/1.0`、`Bearer `）属同源复制的协议常量，**不是**调用关系 [高，基于零引用事实]。api_client 规格中 `/v1/videos` 提交/轮询端点的另一实现方即本模块。

## 4. 节点规格（BananaTEVeoVideoNode）

### 4.1 模型变体（model_variant，下拉 `_MODEL_VARIANT_OPTIONS`）

tooltip 原文 `选择要使用的视频生成模型。` [高]。出现的模型/变体字面量 [高]：

| 变体 | 模型字符串 | 说明 |
|---|---|---|
| `veo3.1-fast`（默认 [中]） | `veo_3_1-fast` | veo 3.1 fast；线路2 按 `veo_3_1-fast JSON 格式提交`（日志原文） |
| `veo3.1-lite` | `_LITE_MODEL_NAME` | lite 变体；`ignores_output_profile`（不使用清晰度档 [中]） |
| `omni-flash` | `omni_flash-10s` | omni-flash 线路2 按 `omni_flash-10s JSON 格式提交`；固定 10 秒（`duration=10` 片段 [中]） |

配套常量 `_FAST_MODEL_NAME_720P/1080P/4K/1080P_FL/4K_FL` [高，名称]：fast 模型按清晰度档解析出的提交模型名候选 `veo_3_1-fast / veo_3_1-fast-hd / veo_3_1-fast-4K / veo_3_1-fast-fl-hd / veo_3_1-fast-4K-fl` [高，字符串]；**档位 → 模型名的精确映射未确认**（`fl` 后缀用途未确认）。

### 4.2 清晰度档（output_profile，下拉 `_OUTPUT_PROFILE_OPTIONS`）

tooltip 原文 `清晰度（默认 720p；1080p 改走 multipart + input_reference[] 接口。` [高，后半句紧邻拼接]。`720p / 1080p / 1080P / 4K` 字面量均出现 [高]；`_DEFAULT_OUTPUT_PROFILE` 疑为 `720p` [中]。归一化 `_normalize_output_profile`，分支标志 `uses_multipart_profile / ignores_output_profile / requested_output_profile / effective_output_profile` [高，名称]。分辨率档位与请求方式的关联（1080p→multipart，720p→JSON data URL）为 tooltip 直接陈述 [高]；**4K 档是否也走 multipart 未确认**。

### 4.3 线路（route，下拉 `_ROUTE_OPTIONS`）

tooltip 原文 `选择接口线路，默认使用线路1；如果某个线路不可用，可以切换其他线路尝试。` [高]。选项标签 `线路1 / 线路2 / 线路3` [高]；另有回退提示 ` (当前模型不使用该线路，已按线路1处理)` 与 ` (omni-flash 固定按 …方式提交)` [高]。内部标志：`route_choice / route_effective / uses_fast_route2 / uses_omni_route2` [高，名称]。

- **线路1（默认）**：`POST /v1/videos` JSON 提交 + `GET /v1/videos/{task_id}` 轮询（docstring 原文）[高]；图像以 data URL / multipart 提交（见 4.6）
- **线路2**：veo fast → `veo_3_1-fast` JSON 格式（首帧/首尾帧/参考图统一走 `input_reference` 字段，日志 `veo 3.1 fast 线路2模式: 首帧按 input_reference 参考图提交`、`…首尾帧按 input_reference 多参考图提交`、`…参考图生视频，input_reference=…`、`…文生视频` [高]）；omni-flash → `omni_flash-10s` JSON 格式（`firstFrameBase64 / lastFrameBase64 / referenceImagesBase64` 字段 [高]）。线路2 限制：`线路2 images 最多只支持 3 张`、`veo 3.1 fast 线路2接口实际只接受单个 input_reference 字符串，已只使用第 1 张参考图，忽略其余 …`、`omni-flash 线路2暂不支持首帧/首尾帧模式，请改用参考图输入 reference_image_1/2/3`、`omni-flash 不支持首帧/首尾帧模式，请改用文生视频或参考图模式` [高]
- **线路3**：仅存在标签 `线路3` [高]；其端点/格式/适用模型**未确认**

### 4.4 输入参数（INPUT_TYPES 形参名 = 字符串证据 [高]；类型/默认值除注明外 [中]）

- `prompt`（STRING, multiline）：tooltip 原文 `用于生成视频的提示词` [高]；空值报 `请输入 prompt` [高]；默认示例文本 `一只可爱的小狗在花园里玩耍` [高]
- `api_key`：tooltip 原文 `API Key；留空则读取 config.ini` [高]；空 config 报 `请在 config.ini 中配置 API Key 或在节点中填写` [高]
- `api_url`：tooltip 原文（字节级原样）`服务地址不要带 /v1/videos）`（存在不成对的 `）`，源码疑为拼接/笔误 [高]）；空 config 报 `请在 config.ini 中配置 API URL 或在节点中填写` / `未配置有效的 API URL` [高]
- `model_variant`（下拉）：`选择要使用的视频生成模型。`（见 4.1）
- `output_profile`（清晰度，下拉）：见 4.2
- `route`（线路选择，下拉）：见 4.3
- `aspect_ratio`：tooltip 原文 `视频比例，对应接口参数 aspectRatio` [高]；合法值 `16:9 / 9:16`（ASCII 直证 [高]；`1:1` 未出现，**是否支持未确认**）；请求体字段 `aspectRatio` [高]
- 首尾帧（IMAGE，可选）：`first_frame_image`、`last_frame_image` [高]；tooltip 线索 `首帧参考`、`尾帧参考。必须和首帧参考一起使用，不能单独使用`、`尾帧参考不能单独使用，请同时接入首帧参考` [高]；`，不支持首尾帧`（拼在某模型的能力说明里，归属未确认 [高，片段]）。编码为 `first_frame.png / last_frame.png` 文件部件（`<file:first_frame.png>`、`<file:last_frame.png>` 日志占位 [高]）
- 多图参考（IMAGE，可选 ×3）：`reference_image_1 / reference_image_2 / reference_image_3`，tooltip `多图参考 1/2/3` [高]；约束原文：`参考图最多只支持 3 张`、`参考图模式下至少需要接入 1 张参考图`、`多图参考模式与首帧/尾帧模式不能同时使用，请二选一`、`接入后不能再接多图参考输入`、`只接这一路时也会走参考图模式`、`… 只支持 1 张图，当前是 …`、`不支持的 IMAGE 维度: …`（tensor 维度错误）[高]。模式判定符号：`has_first_frame / has_last_frame / has_reference_images / text_to_video / single_reference / multi_reference / first_last_frame / first_frame / reference_inputs / input_reference_values` [高，名称]
- `seed`（INT）：类型字符串 `INT` 与形参 `seed` 紧邻 `duration` [高，片段]；tooltip/默认值未确认
- `duration`：形参字符串 `duration` + 片段 `，duration=10`（omni-flash 固定 10 秒语境）[高，名称；用户可调范围未确认]
- `poll_interval_s`：tooltip 原文 `轮询间隔（秒）` [高]；默认值未确认
- `bypass_proxy`（BOOLEAN）：tooltip 原文 `需要忽略系统代理/梯子时开启` [高]；类型 `BOOLEAN` 直证 [高]
- `control_after_generate`：ComfyUI seed 配件约定 [高，名称]；`仅供 ComfyUI 工作流使用；不会写入请求体`（tooltip 原文 [高]）
- 提示：`… 没有可用图像`（空图输入报错片段 [高]）；`缺少图像依赖（numpy）: …` [高]

### 4.5 返回

- `RETURN_TYPES / RETURN_NAMES / OUTPUT_NODE` 存在 [高]。推断返回 **VIDEO 类型** [中]：类型串 `VIDEO`、`comfy.comfy_types`、`comfy_api.input_impl`、`VideoFromFile`、`get_stream_source`、`_HAS_COMFY_VIDEO`（未装 ComfyUI 视频类型时的回退开关，回退值未确认）。保存线索 [中]：`te_veo_video_`（文件名前缀）、`.mp4`、`subfolder`、`filename`、`save_to`、`视频已保存: …`；`output_codec / output_format / codec / animated` 疑为 `save_to(...)` 的保存参数 [低]。
- 日志行（Mode/Model/Size/Task ID/Aspect Ratio）[高]：`模式: 文生视频 | 首帧生视频 | 首尾帧生视频`、`模型选择: …`、`线路选择: …`、`清晰度: …`、`Size: …`、`Task ID: …`、`Aspect Ratio: …`、`API: …`、`API Key: …`（打码）、`API URL: [已脱敏]`、`<data-image len=…>`（日志截断占位）。

### 4.6 关键行为（generate_video 流程，按字符串拓扑 [高/中]）

1. **解析 key/url**：`_resolve_key_and_url` → `load_api_key`（config.ini `[gemini]` 段）+ `get_effective_api_base_url`（见 config_manager spec）；日志打码 [高]
2. **校验输入**：prompt 非空；模式互斥判定（首帧/首尾帧 vs 多图参考，二选一 [高]）；尾帧必须伴随首帧 [高]；参考图 ≤3 张、至少 1 张 [高]
3. **图像预处理与编码**：
   - `_scale_image_tensor_to_total_pixels_if_needed`：按 `_MAX_INPUT_IMAGE_MEGAPIXELS` 与 `resolution_steps` 把输入 tensor 缩放到接口允许的总像素内（`common_upscale` 插值 `nearest-exact`，`_OFFICIAL_SCALE_METHOD` [高，名称]）
   - 三套提交编码并存 [高]：JSON data URL（`data:image/…;base64,…`，日志 `… 张（转 data URL）`）、multipart PNG 文件部件（`_encode_single_image_to_png_file_part`，`content-type`，日志 `… 张（multipart 文件）`）、线路2 的 `input_reference` 字段（首帧单张；首尾帧多参考）
   - multipart 分支标志 `uses_multipart_profile / multipart_form_fields / submit_data_field / files` [高，名称]
4. **提交任务**：`submit_url / submit_endpoint / submit_data / submit_resp`；`json.dumps(ensure_ascii)`；`POST {base}/v1/videos`；请求头 `Authorization: Bearer <key>`、`Content-Type: application/json`、`User-Agent: ComfyUI-TE_API/1.0` [高]；失败报 `提交任务失败: …`；未拿到 id 报 `接口未返回 task_id：…`（响应字段候选 `taskId / task_id / nested_task_id` [高]）
5. **轮询**：`GET {base}/v1/videos/{task_id}`；`fetch_url / fetch_endpoint / status_resp / status_payload / last_status_payload / task_result`；`poll_interval_s + time.sleep`；`_ensure_not_interrupted` 响应 ComfyUI 中断 [高]。状态字面量：成功 `succeeded / completed / success / SUCCESS`，失败 `failed / failure / fail_reason`（终态集合的精确成员未确认）[高]。视频 URL 字段候选 [高]：`downloadUrl / download_url / video_url / content_url`；`_extract_video_url` 提取、`_absolutize_url` 补全相对地址（`urljoin / netloc / scheme` [高]）
6. **下载与保存**：`_download_video`（`iter_content / chunk_size / ProgressBar / comfy.utils`），日志 `视频生成完成，正在下载视频...`、`开始下载视频到 ComfyUI/output ...` [高]；`_DownloadedVideoFromFile.save_to` 处理 PyAV 无法 stream-copy 的情况（英文注释原文），失败回退保留原始 MP4：`PyAV 二次封装视频失败，已保留原始 MP4 数据完成保存: …`、`复制后的视频文件为空`（`copyfile / shutil / getsize` [高]）；成功日志 `视频已保存: …` [高]
7. **错误兜底**：整体失败报 `视频生成失败: …`；`未知错误` 占位 [高]

## 5. 外部依赖与副作用

### 网络端点

| 端点 | 用途 | 证据 | 置信度 |
|---|---|---|---|
| `POST {base}/v1/videos` | 提交视频任务 | docstring `POST /v1/videos 提交任务`、字符串 `/v1/videos`、`/videos`、`post` | [高] |
| `GET {base}/v1/videos/{task_id}` | 轮询任务状态 | docstring `GET /v1/videos/{task_id} 轮询状态`、`/v1/videos/`、`/videos/` | [高] |
| 视频 URL（轮询响应内） | 下载成片，可能为相对路径（`_absolutize_url` 补全） | `downloadUrl / download_url / content_url / video_url / urljoin` | [高/字段候选] |

- 认证：`Authorization: Bearer <API Key>`（`Bearer ` + `Authorization` [高]）；API Key 来源：节点输入或 config.ini `[gemini] api_key`（经 config_manager `load_api_key` [高]）
- Base URL 来源：节点输入或 config.ini（`get_effective_api_base_url`；样例 `https://teynex.com`，归属 config_manager [中]）；tooltip 明确 `服务地址不要带 /v1/videos）`（原文，不成对括号为源串原样）[高]
- 请求头：`Content-Type: application/json`、`User-Agent: ComfyUI-TE_API/1.0`、multipart 时自定 `content-type` [高]
- 代理：`bypass_proxy` → `trust_env`（忽略系统代理）[高]

### 文件系统

- 写 `ComfyUI/output`：下载视频，前缀 `te_veo_video_`，扩展名 `.mp4`；`makedirs / exist_ok / abspath / splitext / basename / dirname / relpath` [高]
- 读 config.ini（经 config_manager）[高]
- 临时文件线索：`first_frame.png / last_frame.png / reference_*.png / <file:…>`（multipart 文件部件命名）[高]

### 第三方库

`requests`（含 `requests.exceptions / Timeout / RequestsJSONDecodeError / JSONDecodeError`）、`numpy`（`array / astype / from_numpy / dtype / uint8 / unsqueeze / squeeze / movedim`）、`torch`、`PIL/BytesIO`（`base64`）、`json`（`dumps/loads`）、`time`（`sleep`）、`math / os / sys / shutil / inspect / typing(Tuple[str, str] / Optional / Dict / List / Any)`、`urllib.parse`（`urljoin / urlparse / urlencode 线索`）、`gc / logging / warnings（isenabled / disable）` [高，符号]；ComfyUI 内部：`comfy.utils(ProgressBar) / comfy.model_management / comfy.comfy_types / comfy_api.input_impl(VideoFromFile) / folder_paths(get_output_directory / get_output_dir) / PromptServer(_DummyPromptServer 兜底)` [高]；`_HAS_COMFY_VIDEO` 检测 ComfyUI 视频类型可用性 [高，名称]。

### 与其他节点族的差异（对照 Jimeng_Video_Generator spec）

- 无图床上传、无音频输入、无渠道 4/5（sora-v3）体系；引入**清晰度档 + 模型变体 + 线路**三正交选择与首帧/首尾帧模式 [高，对照]
- 同样**不走 api_client**、不走 task_runner（无 `task_runner / BatchGenerationRunner` 符号 [高]），单实例单线程 提交→轮询→下载；并发靠 ComfyUI 多实例

## 6. 错误处理与用户可见文案

[高] 均为字符串原文；"…" 为 f-string 拼接点：

- 配置/认证：`请在 config.ini 中配置 API URL 或在节点中填写`；`未配置有效的 API URL`；`请在 config.ini 中配置 API Key 或在节点中填写`；日志脱敏 `API URL: [已脱敏]`、`API Key: <masked>`（`sanitize_api_key / masked_key`）
- 输入校验：`请输入 prompt`；`参考图模式下至少需要接入 1 张参考图`；`参考图最多只支持 3 张`；`线路2 images 最多只支持 3 张`；`多图参考模式与首帧/尾帧模式不能同时使用，请二选一`；`接入后不能再接多图参考输入`；`只接这一路时也会走参考图模式`；`尾帧参考不能单独使用，请同时接入首帧参考`；`… 只支持 1 张图，当前是 …`；`不支持的 IMAGE 维度: …`；`… 没有可用图像`；`缺少图像依赖（numpy）: …`
- 线路/模型能力：` (当前模型不使用该线路，已按线路1处理)`；`omni-flash 线路2暂不支持首帧/首尾帧模式，请改用参考图输入 reference_image_1/2/3`；`omni-flash 不支持首帧/首尾帧模式，请改用文生视频或参考图模式`；`veo 3.1 fast 线路2接口实际只接受单个 input_reference 字符串，已只使用第 1 张参考图，忽略其余 …`；`，不支持首尾帧`（片段）
- 任务提交/轮询：`提交任务失败: …`；`接口未返回 task_id：…`；`返回 JSON 结构异常：…`；`… 返回的不是 JSON`（`… 返回的不是 JSON。HTTP …`）；`未提供有效的任务 ID`；`视频生成失败: …`；`未知错误`
- 下载/保存：`视频生成完成，正在下载视频...`；`开始下载视频到 ComfyUI/output ...`；`PyAV 二次封装视频失败，已保留原始 MP4 数据完成保存: …`；`复制后的视频文件为空`；`视频已保存: …`
- 过程日志：`🎬 TE veo video 任务`；`模式: 文生视频 / 首帧生视频 / 首尾帧生视频`；`线路2模式: 文生视频 / 图生视频参考图，images=… / 参考图生视频，input_reference=…`；`veo 3.1 fast 线路2模式: 首帧按 input_reference 参考图提交 / 首尾帧按 input_reference 多参考图提交 / 文生视频`；`omni-flash 线路2: 按 omni_flash-10s JSON 格式提交，size=…`；`veo 3.1 fast 线路2: 按 veo_3_1-fast JSON 格式提交，size=…`；`模型选择: / 线路选择: / 清晰度: / Size: / Task ID: / Aspect Ratio: / Mode: / Model: / API: `
- 日志截断占位：`<data-image len=…>`、`<file:first_frame.png> / <file:last_frame.png> / <file:reference_…png>`（`_summarize_for_log`，配合 `… 张（data URL）/ … 张（multipart 文件）/ … 张（转 data URL）`）

## 7. 证据附录

### 端点/路径（原文）
```
POST /v1/videos   GET /v1/videos/{task_id}（docstring 原文）
/v1/videos   /v1/videos/   /videos   /videos/   /v1   https://   http://   ://
```

### 请求头/认证（原文）
```
Authorization   Bearer    Content-Type   application/json   content-type
User-Agent   ComfyUI-TE_API/1.0   headers   trust_env   bypass_proxy
```

### 模型/清晰度/线路常量（原文）
```
_FAST_MODEL_NAME_720P  _FAST_MODEL_NAME_1080P  _FAST_MODEL_NAME_4K
_FAST_MODEL_NAME_1080P_FL  _FAST_MODEL_NAME_4K_FL  _LITE_MODEL_NAME  _LITE_MODEL_VARIANT
_DEFAULT_MODEL_VARIANT  _DEFAULT_OUTPUT_PROFILE  _MODEL_VARIANT_OPTIONS
_OUTPUT_PROFILE_OPTIONS  _ROUTE_OPTIONS
veo3.1-fast  veo3.1-lite  omni-flash  omni_flash-10s
veo_3_1-fast  veo_3_1-fast-hd  veo_3_1-fast-4K  veo_3_1-fast-fl-hd  veo_3_1-fast-4K-fl
720p  1080p  1080P  4K   线路1  线路2  线路3
```

### 分辨率字面量（原文）
```
720x1280  1280x720  1920x1080  1080x1920  3840x2160  2160x3840
16:9  9:16  aspectRatio  aspect_ratio  size=  resolved_size  _resolve_video_size
_resolve_720p_video_size  resolution_steps  _OFFICIAL_SCALE_METHOD  _MAX_INPUT_IMAGE_MEGAPIXELS
common_upscale  nearest-exact  megapixels  duration=10  duration  seed  INT  BOOLEAN
```

### 请求体/响应字段（原文）
```
input_reference  input_reference[]  input_references  firstFrameBase64  lastFrameBase64
referenceImagesBase64  reference_image_1/2/3  reference_image_urls  image_urls
aspectRatio  model  size  duration  prompt  seed
taskId  task_id  nested_task_id  task_result  status  progress  fail_reason
downloadUrl  download_url  video_url  content_url  url  raw_url  endpoint
succeeded  completed  success  SUCCESS  failed  failure
multipart_form_fields  submit_data_field  files  uses_multipart_profile
```

### 节点注册/模式判定（原文）
```
NODE_CLASS_MAPPINGS  NODE_DISPLAY_NAME_MAPPINGS  INPUT_TYPES  FUNCTION  CATEGORY
RETURN_TYPES  RETURN_NAMES  OUTPUT_NODE  tooltip
TE_image_pro_te_veo_video  TE MAN VEO Video  TE MAN/Veo  te_veo_video_
BananaTEVeoVideoNode  generate_video  _resolve_key_and_url  _summarize_for_log
has_first_frame  has_last_frame  has_reference_images  text_to_video
single_reference  multi_reference  first_last_frame  first_frame  last_frame_image
first_frame_image  reference_inputs  input_reference_values  route_choice  route_effective
uses_fast_route2  uses_omni_route2  ignores_output_profile  uses_multipart_profile
requested_output_profile  effective_output_profile  _is_auto_video_option  auto
```

### 关键 docstring / 注释（原文摘录）
```
ComfyUI 节点：TE veo video
- POST /v1/videos 提交任务
- GET /v1/videos/{task_id} 轮询状态
Keep downloaded API videos usable when PyAV cannot stream-copy them.
（_DownloadedVideoFromFile.save_to 内英文注释）
仅供 ComfyUI 工作流使用；不会写入请求体（control_after_generate tooltip）
```

### 其他标识
- 编译源：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_VEO_Video.c` [高]
- 交叉引用模块：config_manager（`load_api_key / get_effective_api_base_url / sanitize_api_key / ConfigManager / CONFIG_MANAGER` [高]）、image_codec（`encode_numpy_image_to_api_file_part` [高]）、logger [高]；**不引用 api_client / task_runner**（0 字节命中 [高]）
- 前端联动：`web/js/` 中未发现 `te_veo` 引用（grep 无命中 [高]）—— 与 grok/jimeng 不同，该节点无专属前端扩展
