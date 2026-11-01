# Jimeng_Video_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_Jimeng_Video_Generator`（PE 导出表唯一导出符号）。静态分析（pefile 导入/导出表 + ASCII/UTF-8 字符串提取）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

**节点模块**：TE_MAN（原包名 `custom_nodes.TE_image`，编译源路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Jimeng_Video_Generator.c`、原始 .py 路径 `custom_nodes/TE_image/source_py_backup/Jimeng_Video_Generator.py` [高]）中的**即梦/Seedance 2.0（LongXia）视频生成节点**，注册为 ComfyUI 节点 `BananaJimengVideoNode`，对应 README 所述"TE JM 节点，支持 JM 生成视频"（README.md:364）。即梦 API 后端的 teynex.com API 站（README.md:397，[中]）。

## 2. Python API

- 导出：`PyInit_Jimeng_Video_Generator` [高]。
- 导入依赖：python3.dll / KERNEL32 / VCRUNTIME140 / CRT —— 无 WinSock，网络全走 Python 层 `requests` [高]。
- 模块级函数（qualname 全部来自 Cython 符号串 [高]）：
  - `_ensure_not_interrupted` —— 配合 `comfy.model_management` 的 `throw_exception_if_processing_interrupted` [高]，轮询期间响应 ComfyUI 中断
  - URL 解析器：`_resolve_video_base_url(api_base_url?)`、`_resolve_jimeng_submit_url`、`_resolve_jimeng_fetch_url(task_id?)`、`_resolve_fast_20_submit_url`、`_resolve_fast_20_fetch_url(task_id?)`（形参线索：`task_id` 紧邻符号 [中]）
  - 输出：`_get_output_dir`、`_download_video(video_url, api_key?, timeout_s?)`（形参线索：`video_url / api_key / timeout_s` 紧邻 [中]）
  - 音频：`_get_audio_duration_seconds_from_waveform_input`、`_get_wav_duration_seconds(file_bytes?)`、`_validate_audio_duration(source_label?)`、`_audio_input_to_wav_bytes`
  - 媒体：`_media_input_to_bytes(default_ext?, label?)`、`_image_tensor_to_upload_file_parts`、`_upload_file_to_te_image_host(file_part?)`、`_file_tuple_to_b64_material(file_tuple?, fallback_filename?)`、`_file_tuple_to_data_uri(fallback_mime?)`
  - 协议解析：`_read_json_response_or_raise`、`_extract_jimeng_video_url`、`_extract_uploaded_file_url`、`_extract_task_id`、`_extract_task_payload`
  - 归一化：`_normalize_duration_value`、`_normalize_ratio`、`_normalize_sora_v3_ratio`、`_resolve_longxia_size`、`_resolve_fast_20_size`
  - 日志：`_summarize_payload_for_log`（配合 `<base64 len=`、`<data_uri len=` 截断占位 [高]）
- 类 `BananaJimengVideoNode`：唯一节点类，方法 `INPUT_TYPES`、`_resolve_key_and_url`、`generate_video`（含子生成器 genexpr）[高]。
- ComfyUI 节点注册 [高]：
  - `NODE_CLASS_MAPPINGS` 键：`TE_image_pro_jimeng_video_2`（web/js/grok_prompt_image_mentions.js 也以此 type 引用该节点 [高]）
  - 显示名（`NODE_DISPLAY_NAME_MAPPINGS`）：`TE MAN JM Video 2`
  - `CATEGORY`：`TE MAN/Jimeng`；`FUNCTION`：`generate_video`
  - 对前端另存在 `TE_image_pro_jimeng_video_2_fast` 节点 type 引用（web/js），但本 pyd 无对应 qualname/注册键 → **不是本模块注册，归属模块未确认**

与 api_client 的协议层关系：**本模块不使用 `api_client.GeminiApiClient`**。全文件无 api_client 任何符号（无 `send_openai_request / poll_openai_task / GeminiApiClient` 等），但自有完整的 `requests` 直连设施：`requests.Session / Session() / iter_content / raise_for_status / trust_env / timeout / headers`、自建 submit/fetch URL 构造器、自建 payload 构建 [高]。它与 config_manager 复用（`ConfigManager / load_api_key / get_effective_api_base_url / sanitize_api_key / CONFIG_MANAGER` [高]，该函数簇定义于 config_manager.pyd [高，见 spec/config_manager.md]），与 image_codec 复用（`encode_numpy_image_to_api_file_part / image_codec / base64_to_tensor?`——`encode_numpy_image_to_api_file_part` 定义于 image_codec [高，见 spec/image_codec.md]）。即本节点是**自带协议层**的独立节点，不走 api_client 的统一请求层 [高]。

## 3. 节点规格（BananaJimengVideoNode）

### 3.1 五渠道模型（module docstring 原文 + 说明字符串 [高]）

> 模块 docstring 原文：`ComfyUI 节点：LongXia-V Seedance 2.0 视频生成 / - 参考图/音频使用 b64_json 提交 / - POST /v1/videos 创建任务 / - GET /v1/videos/{task_id} 轮询状态`（为旧描述，与现行渠道说明见下）

渠道说明原文：`渠道2(2.0)：LongXia-G-Seedance-2.0；渠道3(2.0)：seedance2.0-full-9img；渠道4(2.0)：sora-v3-pro；渠道5(2.0fast)：sora-v3-fast`

| 渠道 | 模型常量 | 模型字符串 | 前端标签默认 |
|---|---|---|---|
| 渠道2(2.0) | `_JIMENG_SEEDANCE_MODEL_G` | `LongXia-G-Seedance-2.0` [高] | 默认渠道（web/js `getJimengChannel` 默认 `渠道2(2.0)` [高]） |
| 渠道3(2.0) | `_JIMENG_SEEDANCE_MODEL_FULL_9IMG` | `seedance2.0-full-9img` [高] | — |
| 渠道4(2.0) | `_JIMENG_SEEDANCE_MODEL_SORA_V3_PRO` | `sora-v3-pro` [高] | — |
| 渠道5(2.0fast) | `_JIMENG_SEEDANCE_MODEL_SORA_V3_FAST` | `sora-v3-fast` [高] | — |
| （遗留） | `_JIMENG_SEEDANCE_MODEL_V` | `LongXia-V-Seedance-2.0` [高]，另有提示 `LongXia-V-Seedance-2.0 必须至少连接 1 张参考图` | **已确认：不出现在渠道下拉**——运行时暴露的 `_CHANNEL_OPTIONS` 仅 4 项（见回填 §7），`_ALL_CHANNEL_OPTIONS`（10 项）仅存留旧标签（动态回填） |

渠道分支判定辅助：`is_channel2 / is_channel3 / is_channel4 / is_channel5 / is_sora_v3_channel / is_legacy_channel4`；旧标签 `_LEGACY_CHANNEL4_LABEL` 原文 `渠道4(2.0fast)`（新 sora-v3-pro 4(2.0) 与旧 fast 标签来源 [高]）。`_ALL_CHANNEL_OPTIONS / _CHANNEL_OPTIONS / _CHANNEL2~5_LABEL` [高]。

### 3.2 输入参数（INPUT_TYPES 形参名 = 字符串证据 [高]；类型/默认值已由 §7.2 动态回填实锤）

- `prompt`（STRING, multiline）：tooltip 原文 `用于生成视频的提示词；渠道2用 @image1/@audio1，渠道3用 @图1/@audio1，渠道4支持最多 3 路参考音频，渠道5不支持音频` [高]；空值报 `请输入 prompt` [高]；按渠道限长 `_PROMPT_MAX_CHARS_G / _V / _FAST_20 / _SORA_V3_FAST` —— **已确认：G=3500 / V=3999 / FAST_20=4096 / SORA_V3_FAST=4096**（动态回填），超限报 `prompt 最多 … 个字符，当前 …` [高]。默认提示文本例：`@image1 是主体，镜头缓慢推进，保持主体一致，电影感光影，自然运动。` [高]
- `api_key`：tooltip 原文 `API Key；留空则读取 config.ini` [高]；空 config 时报 `请在 config.ini 中配置 API Key 或在节点中填写` [高]
- `api_base_url`：tooltip 原文 `服务地址（不要带 /v1/videos）` [高]；空时报 `请在 config.ini 中配置 API URL 或在节点中填写` / `未配置有效的 API URL` [高]。**已确认：INPUT_TYPES 暴露的形参名为 `api_base_url`（默认值 `https://tem.588186.xyz`），正文所记 `api_url` 为内部局部名/字符串证据，非最终 UI 形参名（动态回填）**
- `渠道选择`（`channel_choice`，下拉）：`_CHANNEL_OPTIONS` 选项 = 渠道2(2.0)/渠道3(2.0)/渠道4(2.0)/渠道5(2.0fast) [高] —— **已确认：默认 `渠道2(2.0)`，归入 optional 分组（动态回填）**
- `aspect_ratio`（比例）：tooltip 原文 `视频比例；渠道4/渠道5支持全部比例，其他渠道仅使用 16:9 / 9:16 / 1:1` [高]；下拉枚举 [高]：`21:9 / 1:1 / 4:3 / 3:4 / 16:9 / 9:16`（默认 `16:9`）[高]；`_normalize_ratio`（窄集）与 `_normalize_sora_v3_ratio`（渠道4/5）—— **已确认：`_SORA_V3_ASPECT_RATIOS = ["21:9","1:1","4:3","3:4","16:9","9:16"]`（动态回填）**
- `resolution`（可选，渠道4/5）：`_SORA_V3_FIXED_RESOLUTION` —— **已确认：值 `"720p"`，且它不是 UI 输入**：INPUT_TYPES 无 resolution 参数，仅内部固定（动态回填）
- 参考图 9 个 IMAGE 口：`image, image_2 … image_9`（前端命名一致 [高，web/js]；tooltip 原文 `第一张参考图，提交为 reference_images[0]，提示词中用 [img1] 引用` + `第二~第九张参考图（可选）` [高]）。渠道上限：`LongXia-V-Seedance-2.0 必须至少连接 1 张参考图`、`… 最多只能连接 …`；`_MAX_REFERENCE_IMAGES = 9`（**已确认 9 张，动态回填**）、`_MAX_REFERENCE_IMAGES_CHANNEL5 = 4`（**已确认 4 张，动态回填**[中，与 web/js 对渠道4/5 过滤 image…image_4 的行为一致 [高]]）。超限报 `不支持的 IMAGE 维度: …`（tensor 维度错误）
- 可选 AUDIO 口 3 个：`audio, audio_2, audio_3`，tooltip 原文 `参考音频（可选），提交为 reference_audios[0]，提示词中用 [audio1] 引用` 及 `第二个/第三个参考音频…reference_audios[1]/[2]…[audio2]/[audio3] 引用` [高]。音频约束 [高]：单个 2-15 秒（`_MIN_REFERENCE_AUDIO_SECONDS`/`_MAX_REFERENCE_AUDIO_SECONDS` —— **已确认：2.0 / 15.0，动态回填**）+ 累计 ≤15 秒（`全部参考音频累计 …秒，不能超过 …` `参考音频累计时长: …`）；渠道5 不支持音频（`… 不支持参考音频，请断开 audio 输入`）；渠道4 最多 3 路 —— **已确认：`_MAX_REFERENCE_AUDIOS = 3`、`_MAX_REFERENCE_AUDIO_BYTES = 15728640`（15 MB）、`_MAX_REFERENCE_IMAGE_BYTES = 31457280`（30 MB）（动态回填）**
- `bypass_proxy`（BOOLEAN）：tooltip 原文 `需要忽略系统代理/梯子时开启` [高] —— **已确认：UI 形参名为 `绕过代理`，默认 false（动态回填）**
- `poll_interval_s`：**已确认：INT，默认 5，min 2 / max 60（动态回填）**
- 其余：**已确认结论** —— `duration` 是唯一暴露的下拉输入（枚举仅 `"15"`，固定 15 秒）；`resolution` / `size` / `minsize` 不作为独立输入暴露，`duration_value / size_value / resolution_value` 为内部归一化局部名（动态回填）

### 3.3 返回

- **已确认（动态回填）：`RETURN_TYPES = [VIDEO, STRING, STRING, STRING]`，`RETURN_NAMES = ["video", "video_url", "task_id", "response"]`，`OUTPUT_NODE = True`**。`_HAS_COMFY_VIDEO = True`（运行环境装有 ComfyUI 视频类型）；返回 `VIDEO` 类型用 `VideoFromFile` 包装本地 mp4，`video_url` 输出最终下载地址，`task_id` 输出任务 ID，`response` 输出响应摘要 [动态实锤，原推断全部验证]
- 下载文件命名前缀 `jimeng_video_`，保存到 `_get_output_dir`（`get_output_directory` / `folder_paths` [高]）

### 3.4 关键行为（generate_video 流程，按字符串拓扑 [高/中]）

1. **解析 key/url**：`_resolve_key_and_url` → `load_api_key`（config.ini `[gemini]` 段，见 config_manager spec [中]）+ `get_effective_api_base_url`；日志打码：`API Key: …`（`sanitize_api_key / masked_key`）、`API URL: [已脱敏]` [高]
2. **校验输入**：prompt 非空、各渠道参考图/音频数量与时长校验（见 3.2）；音频经 `_audio_input_to_wav_bytes` 重打包为 WAV（`wave` 模块符号：`getframerate/setnchannels/setsampwidth/setframerate/writeframes/getnframes` [高]；torch 波形路径用 `soundfile / numpy / int16 / transpose / tobytes` [高]，缺依赖报 `缺少音频依赖（numpy）: … / 缺少音频依赖（numpy/torch）: …` [高]）
3. **素材编码**（三套提交方式并存，按渠道选择，逐渠道映射未确认 [高/映射未确认]）：
   - `b64_json` → JSON `reference_images`（camelCase 别名 `referenceImages`）/ `reference_audios`（`referenceAudios`）（tooltip："提交为 reference_images[i]/reference_audios[i]"）[高]；日志 `素材提交方式: b64_json`、`音频提交方式: b64_json(JSON reference_audios)`
   - `data URI`（`data:;base64,`）→ JSON `image_urls` 或 `image/images`（日志 `图片提交方式: data URI(JSON image_urls)`、`素材提交方式: data URI(JSON image/images)`）[高]
   - **图床 URL**：`_upload_file_to_te_image_host` 上传 → `_extract_uploaded_file_url`（日志 `素材提交方式: 图床 URL`、`图床上传成功`、`图床上传失败: …`、`图床上传成功，但未解析到 url`）[高]；大小阈值 —— **已确认（动态回填）：`_MAX_REFERENCE_IMAGE_BYTES = 31457280`（30 MB）针对参考图，`_MAX_REFERENCE_AUDIO_BYTES = 15728640`（15 MB）针对参考音频，`_MAX_REFERENCE_AUDIOS = 3` 为音频路数上限**
4. **提交任务**：`submit_url / submit_endpoint / submit_resp / submit_data`；json.dumps `ensure_ascii`；payload 日志 `提交视频任务 payload: …`（经 `_summarize_payload_for_log` + `ComfyUI-TE_API/1.0` UA 用于 `API: ` 日志行 [高]）；失败报 `提交任务失败: …`、未拿到 id 报 `接口未返回 task_id：…` [高]
5. **轮询**：`fetch_url / status_resp / status_data / last_status_data`；`poll_interval_s + time.sleep`；状态字面量 [高]：`succeeded / completed / success / SUCCESS`（成功）、`failed / FAILURE / fail_reason`（失败）、`cancelled / canceled / expired`、终态集合 `terminal_success / terminal_failed`、进行中 `progress / ready / finished`；响应字段别名 [高]：`taskId / task_id / videoUrl / video_url / download_url / direct_url / result_url / videos / data / progress`；错误报 `返回 JSON 结构异常：… / 返回的不是 JSON / 视频…失败: … / 任务完成，但未解析到视频 URL / 未提供有效的任务 ID`；HTTP 检查 `raise_for_status`、`HTTP …`
6. **下载**：`_download_video`（`iter_content / chunk_size / ProgressBar / comfy.utils`），日志 `开始下载视频到 ComfyUI/output ...` [高]；中断通过 `_ensure_not_interrupted` + `comfy.model_management.throw_exception_if_processing_interrupted` [高]
7. 请求头 [高]：`Authorization: Bearer <key>`（`Bearer ` + `Authorization`）、`Content-Type: application/json`、`Accept`、`User-Agent: ComfyUI-TE_API/1.0`、`comfy_api.input_impl`（ComfyUI 官方上传输入实现，用途未确认）

### 3.5 尺寸/时长归一化 [高]

- `_resolve_longxia_size`（渠道2/3）+ `_SIZE_BY_RATIO` —— **已确认配对（动态回填）：`16:9 → 1280x720`、`9:16 → 720x1280`、`1:1 → 720x720`**
- `_resolve_fast_20_size`（渠道4/5）+ `_FAST_20_SIZE_BY_RATIO`；`_SORA_V3_FIXED_RESOLUTION = "720p"` [高] —— **已确认配对（动态回填）：`16:9 → 1920x1080`、`9:16 → 1080x1920`、`1:1 → 1080x1080`**
- 时长：`_normalize_duration_value` + **已确认：`video-v1-15s` = 常量 `_JIMENG_SEEDANCE_MODEL_FAST_20` 的值（旧 Fast 2.0 渠道模型名，现行 `_CHANNEL_OPTIONS` 不再暴露该渠道，动态回填）**；`视频时长固定 15 秒`；音频轮询进度行含 `s / 15s`

## 4. 外部依赖与副作用

### 网络端点

| 端点 | 用途 | 证据 | 置信度 |
|---|---|---|---|
| `POST {base}/v1/videos`（docstring）、路径候选 `{base}/v1/video/generations`（或 `/video/generations`） | 提交任务（渠道2/3，`_resolve_jimeng_submit_url`） | 字符串 `/v1/videos`、`/v1/video/generations`、`/video/generations`、docstring `POST /v1/videos` | docstring [高]；各路径→渠道归属未确认 |
| `POST {base}/…`（`_resolve_fast_20_submit_url`，对应渠道4/5 sora-v3-pro/fast） | 提交任务（渠道4/5） | `submit_url` 分支符；具体路径未确认 | 未确认 |
| `GET {base}/v1/videos/{task_id}`（docstring）、候选 `/v1/videos/videos` | 轮询状态（`/v1/videos/videos` 出现两次但用途未确认） | docstring `GET /v1/videos/{task_id}` [高]；`/v1/videos/videos` 存在 [高] | 归属未确认 |
| `http://teh.tetae.top:40061/api/index.php` | 图床上传 API（`_TE_IMAGE_HOST_UPLOAD_URL` 候选，`图床上传 API: …`） | 原文 [高] | 作为默认值 [中] |
| `https://tem.588186.xyz` | **已确认：`api_base_url` 输入的硬编码默认值（视频 API 默认服务地址）** | 原文 [高] | **已证实为默认值（动态回填）** |
| 图床响应路径片段 `/content`、`uploads`、`files` | `_extract_uploaded_file_url` 从上传响应提取 URL | 原文 [高] | [中] |

认证：视频 API 用 `Authorization: Bearer <API Key>` [高]；图床用 `_TE_IMAGE_HOST_TOKEN` [高] —— **已确认：默认 token 字符串即 `1c17b11693cb5ec63859b091c5b9c1b2`，上传 URL 默认值即 `http://teh.tetae.top:40061/api/index.php`（动态回填）**。

### 文件系统
- 写 `ComfyUI/output`（`jimeng_video_` 前缀、`makedirs/exists/exist_ok/isdir/isfile/abspath/splitext/basename/dirname`）[高]
- 读 config.ini（经 config_manager：`load_api_key` 读 `[gemini] api_key`、`get_effective_api_base_url` 读 `api_base_url`；config.ini 样例另含 `max_workers = 4`、`network_workers_cap = 4`）[高/键归属见 config_manager spec]

### 第三方库
`requests`（含 `requests.exceptions / Timeout / RequestsJSONDecodeError / JSONDecodeError`）[高]、`numpy / torch / soundfile(SoundFile) / wave / mimetypes / base64 / json / time(sleep) / typing(Tuple, Optional, List) / wave` [高]；ComfyUI 内部：`comfy.utils(ProgressBar) / comfy.model_management / comfy.comfy_types / folder_paths / PromptServer(_DummyPromptServer 兜底) / comfy_api.input_impl` [高]。

### 多任务并发
- **节点内部无并发编排**：一次 `generate_video` 单线程走 提交→sleep 轮询→下载 全程，无 `threading.Thread / ThreadPoolExecutor / BatchGenerationRunner` 痕迹（对比 task_runner spec 的 `BatchGenerationRunner/InterruptProcessingException` 符号在本 pyd 中都不存在）[高]
- 并发能力来自外部：ComfyUI 多 worker 调度 + config.ini `max_workers = 4 / network_workers_cap = 4` 与 TE 启动器（README v2.1 "支持 API 并发"，config.ini 样例键 [高]）；本 pyd 未引用 `task_runner.load_max_workers` 等符号 → 是否消费这些配置未确认，[中] 结论：多任务并发 = 多个该节点实例并行执行，每个实例独占一次长连接轮询

## 5. 错误处理与用户可见文案

[高] 均为字符串原文；"…" 为 f-string 拼接点：

- 配置/认证：`请在 config.ini 中配置 API URL 或在节点中填写`；`未配置有效的 API URL`；`请在 config.ini 中配置 API Key 或在节点中填写`；日志脱敏 `API URL: [已脱敏]` / `API Key: <masked>`
- 输入校验：`请输入 prompt`；`prompt 最多 … 个字符，当前 …`；`LongXia-V-Seedance-2.0 必须至少连接 1 张参考图`；`… 最多只能连接 …`；`不支持的 IMAGE 维度: …`；`不支持的 AUDIO 维度: …`；`未提供有效的 AUDIO 输入`；`AUDIO 输入为空`；`AUDIO 输入缺少有效的 sample_rate`；`图片为空，无法编码为 data URI`；`… 为空，无法编码为 b64_json`；`… 超过 15MB`；`… 超过 30MB`
- 音频：`无法确认音频时长，当前节点要求单个音频 2-15 秒，全部音频累计不超过 15 秒`；`… 秒，不能超过 …`；`全部参考音频累计 …`；`参考音频累计时长: …`；`… 不支持参考音频，请断开 audio 输入`；`缺少音频依赖（numpy）: …`；`缺少音频依赖（numpy/torch）: …`
- 图床：`图床上传失败: …`；`图床上传成功，但未解析到 url`；`图床上传 API: …`；`… MB) -> 图床 URL`
- 任务提交/轮询：`提交任务失败: …`；`接口未返回 task_id：…`；`返回 JSON 结构异常：…`；`… 返回的不是 JSON`；`视频生成失败: …`；`任务完成，但未解析到视频 URL`；`未提供有效的任务 ID`；`视频生成完成，已获取下载地址`（成功日志）
- 下载：`开始下载视频到 ComfyUI/output ...`
- 默认提示（prompt 占位/示例）：`@image1 是主体，镜头缓慢推进，保持主体一致，电影感光影，自然运动`

## 6. 证据附录

### 端点/路径（原文）
```
/v1/videos          /v1/videos/videos     /v1/video/generations     /video/generations
/v1/videos/{task_id}（docstring）          /content   uploads  files
http://teh.tetae.top:40061/api/index.php   https://tem.588186.xyz   1c17b11693cb5ec63859b091c5b9c1b2
```

### 请求头（原文）
```
Authorization   Bearer    Content-Type   application/json   Accept
User-Agent   ComfyUI-TE_API/1.0
```

### 模型/常量名（原文）
```
_JIMENG_SEEDANCE_MODEL_G       LongXia-G-Seedance-2.0
_JIMENG_SEEDANCE_MODEL_V       LongXia-V-Seedance-2.0
_JIMENG_SEEDANCE_MODEL_FULL_9IMG   seedance2.0-full-9img
_JIMENG_SEEDANCE_MODEL_SORA_V3_PRO  sora-v3-pro
_JIMENG_SEEDANCE_MODEL_SORA_V3_FAST sora-v3-fast
_JIMENG_SEEDANCE_MODEL_FAST_20
video-v1-15s
_TE_IMAGE_HOST_UPLOAD_URL   _TE_IMAGE_HOST_TOKEN
PROMPT_MAX_CHARS_G/_V/_FAST_20/_SORA_V3_FAST
SIZE_BY_RATIO  _FAST_20_SIZE_BY_RATIO  _SORA_V3_ASPECT_RATIOS  _SORA_V3_FIXED_RESOLUTION
MIN/MAX_REFERENCE_AUDIO_SECONDS  MAX_REFERENCE_AUDIOS  MAX_REFERENCE_AUDIO_BYTES
MAX_REFERENCE_IMAGES  MAX_REFERENCE_IMAGES_CHANNEL5  MAX_REFERENCE_IMAGE_BYTES
CHANNEL_OPTIONS  _ALL_CHANNEL_OPTIONS  _CHANNEL2/3/4/5_LABEL  _LEGACY_CHANNEL4_LABEL
```

### 请求体/响应字段（原文）
```
image  images  image_urls  reference_images  referenceImages  reference_audio(s)  referenceAudios
taskId  task_id  videoUrl  video_url  download_url  direct_url  result_url
status  progress  fail_reason  data  videos  filename  mime_type  content-type
succeeded  completed  success  SUCCESS  failed  FAILURE  cancelled  canceled  expired
terminal_success  terminal_failed  ready  finished
```

### 波形/WAV 处理符号（原文）
```
wave: getframerate setnchannels setsampwidth setframerate writeframes getnframes
torch/numpy/soundfile: sampling_rate  SoundFile  samplerate  int16  transpose  tobytes
BytesIO  astype  reshape
```

### 节点注册（原文）
```
NODE_CLASS_MAPPINGS  NODE_DISPLAY_NAME_MAPPINGS  INPUT_TYPES  FUNCTION  CATEGORY  RETURN_TYPES
RETURN_NAMES  OUTPUT_NODE  TE_image_pro_jimeng_video_2  TE MAN JM Video 2  TE MAN/Jimeng
BananaJimengVideoNode  generate_video
```

### 其他标识
- 编译源：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Jimeng_Video_Generator.c`
- 前端联动：`web/js/grok_prompt_image_mentions.js` 以 `TE_image_pro_jimeng_video_2` 注册 @token 插入芯片：`[img1]`/`[audio1]`（channel4 插入文本）、`@image1/@audio1`（渠道2）、`@图1/@audio1`（渠道3）；该文件亦引用未在本 pyd 注册的 `TE_image_pro_jimeng_video_2_fast`
- 交叉引用模块：config_manager（`load_api_key / get_effective_api_base_url / sanitize_api_key / ConfigManager / CONFIG_MANAGER` [高]）、image_codec（`encode_numpy_image_to_api_file_part` [高]）、`comfy.model_management` 中断、`prompt_max_chars` 校验

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions 真实环境（`Windows-2025Server-10.0.26100`，Python 3.13.16，ComfyUI 目录 `D:\a\_temp\ComfyUI`，插件包 `custom_nodes/TE_MAN`）运行时 introspection 导出（`te_man_introspection.json`）。本节所有值为运行时实锤，非静态推断。
> 包装层说明：该节点**不经 `Grok_Safe_PY` SafePy 包装**——运行时注册直接指向 pyd 基类 `custom_nodes.TE_image.Jimeng_Video_Generator.BananaJimengVideoNode`（编译期限定名保留旧包名 TE_image），最终暴露参数表 = pyd 基类 INPUT_TYPES 原表。

### 7.1 节点注册（运行时实锤）

| 项 | 值 |
|---|---|
| 注册名 | `TE_image_pro_jimeng_video_2` |
| 运行时类 | `custom_nodes.TE_image.Jimeng_Video_Generator.BananaJimengVideoNode` |
| 显示名 | `TE MAN JM Video 2` |
| `FUNCTION` | `generate_video` |
| `CATEGORY` | `TE MAN/Jimeng` |
| `OUTPUT_NODE` | `True` |
| 节点 doc | `ComfyUI 节点：LongXia-V Seedance 2.0 视频生成 / - 参考图/音频使用 b64_json 提交 / - POST /v1/videos 创建任务 / - GET /v1/videos/{task_id} 轮询状态` |

### 7.2 INPUT_TYPES 全表（运行时实锤）

**required：**

| 参数 | 类型 | 枚举/约束 | 默认值 | tooltip 摘要 |
|---|---|---|---|---|
| `prompt` | STRING | multiline | `@image1 是主体，镜头缓慢推进，保持主体一致，电影感光影，自然运动。` | 渠道2用 @image1/@audio1，渠道3用 @图1/@audio1，渠道4支持最多 3 路参考音频，渠道5不支持音频 |
| `duration` | ["15"] | 单枚举 | `"15"` | 视频时长固定 15 秒 |
| `aspect_ratio` | ["21:9","1:1","4:3","3:4","16:9","9:16"] | 下拉 | `"16:9"` | 渠道4/渠道5支持全部比例，其他渠道仅使用 16:9 / 9:16 / 1:1 |

**optional：**

| 参数 | 类型 | 枚举/约束 | 默认值 | tooltip 摘要 |
|---|---|---|---|---|
| `api_key` | STRING | 单行 | `""` | API Key；留空则读取 config.ini |
| `api_base_url` | STRING | 单行 | `https://tem.588186.xyz` | 服务地址（不要带 /v1/videos） |
| `image` / `image_2` / `image_3` / `image_4` / `image_5` / `image_6` / `image_7` / `image_8` / `image_9` | IMAGE ×9 | — | — | 第 1~9 张参考图（可选），提交为 reference_images[0..8]，提示词中用 [img1]…[img9] 引用 |
| `audio` / `audio_2` / `audio_3` | AUDIO ×3 | — | — | 参考音频（可选），提交为 reference_audios[0..2]，提示词中用 [audio1]/[audio2]/[audio3] 引用 |
| `seed` | INT | min 0 / max 2147483647 | `0` | 保留参数；新接口不写入请求体 |
| `poll_interval_s` | INT | min 2 / max 60 | `5` | 轮询间隔（秒） |
| `绕过代理` | BOOLEAN | — | `false` | 需要忽略系统代理/梯子时开启 |
| `渠道选择` | ["渠道2(2.0)","渠道3(2.0)","渠道4(2.0)","渠道5(2.0fast)"] | 下拉 | `渠道2(2.0)` | 渠道2(2.0)：LongXia-G-Seedance-2.0；渠道3(2.0)：seedance2.0-full-9img；渠道4(2.0)：sora-v3-pro；渠道5(2.0fast)：sora-v3-fast |

**未暴露项修正**：正文 §3.2 所记 `resolution`、`bypass_proxy`（实际形参名为 `绕过代理`）、`api_url`（实际形参名为 `api_base_url`）按上表修正；`渠道选择` 归入 optional 而非 required。

### 7.3 返回值（运行时实锤）

`RETURN_TYPES = [VIDEO, STRING, STRING, STRING]`，`RETURN_NAMES = ["video", "video_url", "task_id", "response"]`，`OUTPUT_NODE = True`。

### 7.4 模块常量实锤值（Jimeng_Video_Generator）

```
NODE_CLASS_MAPPINGS   = {TE_image_pro_jimeng_video_2: BananaJimengVideoNode}
NODE_DISPLAY_NAME_MAPPINGS = {TE_image_pro_jimeng_video_2: TE MAN JM Video 2}
MODULE_DIR            = D:\a\_temp\ComfyUI\custom_nodes\TE_MAN
_HAS_COMFY_VIDEO      = True
_CHANNEL_OPTIONS      = ["渠道2(2.0)", "渠道3(2.0)", "渠道4(2.0)", "渠道5(2.0fast)"]
_ALL_CHANNEL_OPTIONS  = ["渠道1","渠道2","渠道2(2.0)","渠道3","渠道3(2.0)","渠道4","渠道4(2.0)","渠道4(2.0fast)","渠道5","渠道5(2.0fast)"]
_CHANNEL2_LABEL       = "渠道2(2.0)"    _CHANNEL3_LABEL = "渠道3(2.0)"
_CHANNEL4_LABEL       = "渠道4(2.0)"    _CHANNEL5_LABEL = "渠道5(2.0fast)"
_LEGACY_CHANNEL4_LABEL= "渠道4(2.0fast)"
_JIMENG_SEEDANCE_MODEL_G          = "LongXia-G-Seedance-2.0"
_JIMENG_SEEDANCE_MODEL_V          = "LongXia-V-Seedance-2.0"      # 遗留，不在 _CHANNEL_OPTIONS
_JIMENG_SEEDANCE_MODEL_FULL_9IMG  = "seedance2.0-full-9img"
_JIMENG_SEEDANCE_MODEL_SORA_V3_PRO= "sora-v3-pro"
_JIMENG_SEEDANCE_MODEL_SORA_V3_FAST = "sora-v3-fast"
_JIMENG_SEEDANCE_MODEL_FAST_20    = "video-v1-15s"                 # 旧 Fast 2.0 渠道模型，不再暴露
_PROMPT_MAX_CHARS_G            = 3500
_PROMPT_MAX_CHARS_V            = 3999
_PROMPT_MAX_CHARS_FAST_20      = 4096
_PROMPT_MAX_CHARS_SORA_V3_FAST = 4096
_SIZE_BY_RATIO          = {"16:9": "1280x720", "9:16": "720x1280", "1:1": "720x720"}      # 渠道2/3
_FAST_20_SIZE_BY_RATIO  = {"16:9": "1920x1080", "9:16": "1080x1920", "1:1": "1080x1080"}  # 渠道4/5
_SORA_V3_ASPECT_RATIOS  = ["21:9", "1:1", "4:3", "3:4", "16:9", "9:16"]
_SORA_V3_FIXED_RESOLUTION = "720p"
_MAX_REFERENCE_IMAGES           = 9
_MAX_REFERENCE_IMAGES_CHANNEL5  = 4
_MAX_REFERENCE_IMAGE_BYTES      = 31457280        # 30 MB
_MAX_REFERENCE_AUDIOS           = 3
_MAX_REFERENCE_AUDIO_BYTES      = 15728640        # 15 MB
_MAX_REFERENCE_AUDIO_SECONDS    = 15.0
_MIN_REFERENCE_AUDIO_SECONDS    = 2.0
_TE_IMAGE_HOST_UPLOAD_URL = "http://teh.tetae.top:40061/api/index.php"
_TE_IMAGE_HOST_TOKEN      = "1c17b11693cb5ec63859b091c5b9c1b2"
```

### 7.5 回填后仍未确认项

- 各渠道对应的提交/轮询 URL 精确路径（`_resolve_jimeng_submit_url` 与 `_resolve_fast_20_submit_url` 的拼法）——introspection 仅提取常量与 INPUT_TYPES，函数体不可见。
- 素材提交方式（b64_json / data URI / 图床 URL）的逐渠道映射——正文 §3.4 第 3 条的"逐渠道映射未确认"维持原状。
- `TE_image_pro_jimeng_video_2_fast` 前端 type 的归属模块——本次 introspection 全部 30 个注册节点中无此键，仍非本模块注册。
