# GPT_Image_2_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_GPT_Image_2_Generator`。静态分析（字符串池 / pefile 导入导出表）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

ComfyUI **节点模块**（不在 `__init__.py:21-33` 的 `SKIP_MODULES` 中，会被自动加载）：TE MAN 的 **TE MAN GPT Image 2 & 2.5 图像生成节点**，通过 OpenAI 兼容 Images API（可选 Chat Completions 兼容线路）做文生图 / 图生图，内置 10 种"快捷功能"中文提示词模板（导演故事板、九/四宫格分镜、黑白速写、白底三/四视图），并用 `task_runner.BatchGenerationRunner` 做多张图并发生成。

原始工程路径证据 [高]：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\GPT_Image_2_Generator.c`（Cython 生成物）、`custom_nodes/TE_image/source_py_backup/GPT_Image_2_Generator.py`、模块限定名 `custom_nodes.TE_image.GPT_Image_2_Generator` —— 插件曾名 `TE_image`。

交叉协作（本模块内出现的外部模块名 [高]）：

| 依赖 | 本模块中的证据串 |
|---|---|
| `api_client` | `api_client`、`API_CLIENT`、`GeminiApiClient`、借用 `_get_session` / `_resolve_timeout` / `_suppress_insecure_warning` / `extract_openai_content` 等名 |
| `config_manager` | `config_manager`、`CONFIG_MANAGER`、`ConfigManager`、`load_api_key`、`get_effective_api_base_url`、`sanitize_api_key`、`load_max_workers`、`masked_key` |
| `image_codec` | `image_codec`、`ImageCodec`、`ErrorCanvas`、`prepare_input_images`、`prepare_input_image_data_urls`、`prepare_input_image_file_parts`、`base64_to_tensor_parallel`、`build_preview_tuple`、`build_error_tensor_from_text`、`extract_numpy_images`、`decode_workers` |
| `task_runner` | `task_runner`、`BatchGenerationRunner`、`InterruptProcessingException`、`interrupt_checker`、`stagger_delay`、`thread_id` |
| ComfyUI | `comfy.model_management`、`throw_exception_if_processing_interrupted`、`comfy.utils`、`ProgressBar`、`update_absolute` |
| 三方 | `torch`（`List[torch.Tensor]`）、`requests`（`session` / `post` / `RequestException` / `raise_for_status` / `verify`）、`base64`、`json`（`dumps`/`ensure_ascii`）、`random`（`randint`）、PIL、typing |

## 2. Python API

### 2.1 导出
- PE 导出表唯一符号：`PyInit_GPT_Image_2_Generator` [高]。
- DLL 导入仅 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / CRT —— **无 WS2_32**，网络全部经 Python 层 `requests` 完成 [高]。

### 2.2 模块级常量与对象（名称均为字符串池直接证据 [高]，内容/取值见 §3、§6）
- `TEGPTImage2Node` —— 节点类 [高]。
- `API_CLIENT`（大写别名，指向 `GeminiApiClient`；具体 import 形式未确认）[中→高]。
- `CONFIG_MANAGER`（`ConfigManager` 实例或类）[中]。`IMAGE_CODEC` / `ImageCodec` 同理 [中]。
- `PLUGIN_DIR`、`MODULE_DIR`、`source_py_backup` [高]（模块目录探测，配合 `os.path`：`abspath`/`dirname`/`basename`）[中]。
- 配置/选项常量：`_MODEL_NAME`、`_MODEL_OPTIONS`、`_SIZE_RATIO_OPTIONS`、`_RESOLUTION_OPTIONS`、`_RESOLUTION_CONFIGS`、`_LEGACY_SIZE_TO_RATIO`、`_IMG2IMG_ENDPOINT_OPTIONS`、`_DEFAULT_OUTPUT_FORMAT`、`_DEFAULT_BACKGROUND`、`QUICK_FUNCTION_OPTIONS` / `QUICK_FUNCTION_PREFIXES` / `QUICK_FUNCTION_NONE` / `QUICK_FUNCTION_DIRECTOR_STORYBOARD` / `QUICK_FUNCTION_BLACK_WHITE_STORYBOARD`、`DIRECTOR_STORYBOARD_PROMPT_PREFIX` / `DIRECTOR_STORYBOARD_PROMPT_SUFFIX`、`BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX` [高]。
- 错误截断常量：`_MAX_API_ERROR_TEXT_LENGTH`、`_MAX_DISPLAY_ERROR_LENGTH`；错误文案片段 `...（错误响应已截断）`、`HTTP ` [高]。
- `_suppress_insecure_warning` —— verify_ssl=False 时屏蔽 urllib3 告警（`enable`/`disable`/`isenabled`，与 api_client 同模式）[中]。
- 类型注解残留（编译期嵌入 [高]）：`Tuple[Any, List, bool, bool, bool]`、`Tuple[List[str], str]`、`Tuple[str, str]`、`Tuple[str, Optional[Dict[str, Any]]]`、`Dict[str, Dict[str, Any]]`、`Dict[str, Any]`、`List[torch.Tensor]`、`Optional[str]`。

### 2.3 方法清单（qualname 字符串 [高]）

`TEGPTImage2Node`：`__init__`、`INPUT_TYPES`、`generate_images`、以及私有方法（推断为主干流程顺序）：
`_ensure_not_interrupted`、`_build_failure_result`、`_normalize_resolution`、`_normalize_size_text`、`_get_resolution_config`、`_normalize_ratio_label`、`_resolve_request_size`、`_resolve_effective_img2img_endpoint_mode`、`_should_use_line1_edits_for_1k_img2img`、`_resolve_request_model`、`_should_strip_line2_optional_fields`、`_strip_line2_optional_fields`、`_resolve_key_and_url`、`_build_gpt_image_2_request`、`_resolve_gpt_image_2_endpoint`、`_resolve_gpt_image_2_task_endpoint`、`_normalize_task_result`、`_poll_gpt_image_2_task`、`_send_sync_gpt_image_2_request`、`_extract_sync_gpt_image_2_content`、`_extract_chat_completions_content`（内含 `append_url` / `collect_from_text` 闭包）、`_generate_single_image_gpt_image_2`、`_generate_with_gpt_image_2_api`（内含 `progress_callback` / `lambda`）[高]。另有模块级 `_format_api_error_payload`、`_format_http_error_response` [高]。

### 2.4 ComfyUI 注册 [高（pyd 串）+ 前端 JS 互证]

| 项 | 值 | 证据 |
|---|---|---|
| NODE_CLASS_MAPPINGS 键 | **`TE_image_pro_gpt_image_2`** | pyd 字符串 `TE_image_pro_gpt_image_2` [高]；前端 `web/js/grok_prompt_image_mentions.js` 的 `GPT_IMAGE_MODEL_NODE_TYPE='TE_image_pro_gpt_image_2'` [高] |
| 显示名 | **`TE MAN GPT Image 2 & 2.5`** | pyd 字符串 [高] |
| CATEGORY | **`TE MAN/GPT`** | pyd 字符串 `TE MAN/GPT` [高] |
| DESCRIPTION | `使用 gpt-image-2 通过 OpenAI Images API 进行文生图或图生图` | pyd 字符串 [高] |
| FUNCTION | `generate_images` | qualname + 单独字符串 [高] |
| OUTPUT_NODE | 存在 `OUTPUT_NODE` 字符串 → 推断为 UI 预览输出节点 [中] | — |
| RETURN_TYPES | 候选串 `IMAGE`、`STRING` 均在池中 [高]；`RETURN_NAMES` 存在但成员未确认。结合 `Tuple...` 注解与摘要串，推断含输出图与摘要文本 [中] |

前端 JS 互证 [高]：`web/js/grok_prompt_image_mentions.js` 为该节点注册 9 个图片输入 `{name: 'image_N', label: '图片N'}`（N=1..9）、「提示词输入接口」（widget `prompt`）、widget `模型选择`（选项 `'GPT Image 2','GPT Image 2.5'` —— 对应 pyd 串 `GPT Image 2`/`GPT Image 2.5`），及默认提示词 `一只戴着墨镜的白色猫咪，电影感，细节丰富`（pyd 同串）。

## 3. 节点规格

### 3.1 输入参数（名称与 tooltip 均有字符串证据；归属合并 [高]，具体默认值多为编译期常数 → 未确认）

| 参数（推断名） | 类型 | 默认/选项 | 证据 / 说明 |
|---|---|---|---|
| `model_choice`（模型选择） | combo | `GPT Image 2` / `GPT Image 2.5` | tooltip：`选择 GPT Image 2 或 GPT Image 2.5 模型系列` [高]；JS 同选项 [高] |
| `prompt` | STRING multiline | `一只戴着墨镜的白色猫咪，电影感，细节丰富` | 错误校验文案 `请输入提示词`；默认值 JS+pyd 同串 [高] |
| 上游文本（forceInput 输入口） | STRING | — | tooltip：`连接上游文本后优先使用该内容；未连接时使用节点内的增强提示词框`；`forceInput`、`connected_prompt`、`final_prompt_text`、README v3.x「增加独立的提示词输入接口」[高] |
| `image_1`..`image_9` | IMAGE（可选） | — | 9 个口：`参考/编辑输入图像 1..9（可选）`[高]；JS `image_1..image_9` [高]；字段名 `image_1`..`image_9` 在请求文件构造中出现 [高] |
| 比例（`actual_ratio`/`normalized_ratio` 所指） | combo | 见 §3.4 比例表 | tooltip：`选择需要生成的分辨率比例`；`_SIZE_RATIO_OPTIONS` [中] |
| 分辨率 | combo | `1K / 2K / 4K`（另有 `Auto` 字面串） | tooltip：`1K / 2K / 4K；分辨率不同,价格不同`、标签 `分辨率(价格不同)`；`_RESOLUTION_OPTIONS`；"Auto" 大写字面串存在但归属未确认 [中] |
| `quality`（质量） | combo | 未确认 | `request_quality`、日志前缀 `质量: ` [中]；仅见 `high`、`auto` 字面串，选项表未确认 [低] |
| `background`（背景） | combo | 未确认 | `request_background`、`_DEFAULT_BACKGROUND`、日志前缀 `背景: ` [中] |
| `output_format`（输出格式） | combo | 未确认（`png` 串存在） | `request_output_format`、`_DEFAULT_OUTPUT_FORMAT`、日志前缀 `输出格式: ` [中] |
| 图生图接口（`img2img_endpoint_mode`/线路选择） | combo | 见 §3.3 | tag：`图生图接口`；日志 `线路选择: `、`线路1`/`线路2`；选项串 `chat_completions(img2img)`、`edits`、`generations(img2img)` [中→高] |
| `batch_size`（批次数量） | INT | 未确认 | tooltip：`生成批次数量；每个批次生成 1 张图`；日志 `批次数量: ` [高] |
| `seed` | INT（`control_after_generate`） | — | tooltip：`仅用于 ComfyUI 工作流记录，不写入请求体`；`seed`、`current_seed`、`base_seed`、`randint`（随机种子）[高] |
| `quick_function_value`（快捷功能） | combo | 见 §3.5 | tag：`快捷功能`、tooltip：`使用快捷功能生成`、`quick_prefix` [高] |
| `api_key` | STRING | 空=config.ini | tooltip：`API Key；留空则使用 config.ini 中配置`；错误：`请在 config.ini 中配置 API Key 或在节点中填写`、`请填写有效的 API Key` [高] |
| `api_base_url` | STRING | 空=config.ini | tooltip：`服务地址；留空则使用 config.ini 中配置`；错误：`请在 config.ini 中配置 API URL 或在节点中填写`、`未配置有效的 API Base URL` [高] |
| `bypass_proxy` | BOOLEAN | 未确认 | tooltip：`需要忽略系统代理/梯子时开启`、`绕过代理` [高] |
| `verify_ssl` | BOOLEAN | 未确认 | 串 `verify_ssl`、`verify` [中] |
| `filename_prefix` | STRING | 未确认 | 串 `filename_prefix` [中]；本节点仅见 `OUTPUT_NODE`+`build_preview_tuple`，**未发现** 磁盘保存/`folder_paths` 证据 → 用途未确认（可能仅前缀参数） |

### 3.2 模型解析（`_resolve_request_model`）
- `_MODEL_OPTIONS` 支持 `GPT Image 2` → `gpt-image-2`、`GPT Image 2.5` → `gpt-image-2.5` [中→高]（两组字面串均在池中）。
- 分辨率后缀 `model_prefix`：字面串 `gpt-image-2-1k`、`gpt-image-2-2k`、`gpt-image-2-4k`、独立串 `-1k` [高] → 推断 GPT Image 2 按 `1K/2K/4K` 追加 `-1k/-2k/-4k` [中]。`gpt-image-2.5` 无后缀变体串（未确认是否同样追加）。

### 3.3 请求格式（OpenAI 兼容接口；本节为呼叫格式核心）

**端点解析**（`_resolve_gpt_image_2_endpoint` / `_resolve_gpt_image_2_task_endpoint`）[高]：
- 文生图 JSON：`POST {base}/v1/images/generations`
- 图生图 multipart：`POST {base}/v1/images/edits`
- Chat 线路：`POST {base}/v1/chat/completions`
- 异步任务轮询：`GET {base}/v1/images/tasks/{task_id}`
- 兼容 base 已含 `/v1` 的短后缀：`/images/generations`、`/images/edits`、`/chat/completions`、`/images/tasks/`（与 `api_client` 的 URL 构建双表同模式）。
- 失败：`未配置有效的 API Base URL`。

**请求头** [高]：`Authorization: Bearer <api_key>`（`Bearer `、`Authorization`）、`Content-Type: application/json`（JSON 线路）；edits 线路为 multipart `files`（经 `prepare_input_image_file_parts`）[中→高]。

**请求体字段**（key 均有字面串 [高]；是否在 `edits` 中作为 form data 发送 [中]）：
- `model`（见 §3.2）、`prompt`（`prompt_text`/`final_prompt_text`/`prompt`）、`size`（`request_size` → `_resolve_request_size`；`WxH` 字面量格式见 §3.4）、`quality`（`request_quality`）、`background`（`request_background`）、`output_format`（`request_output_format`）。
- 图生图按模式切换 [中]：`chat_completions(img2img)` → POST `/v1/chat/completions`，body `messages`（含 `role`/`content`，输入图以 `data:image/...;base64` / `image_data_url` 形态入内容）[中]；`edits` → `/v1/images/edits` + `files`（字段 `image_1..image_9`，中文名 `输入图像: N` 日志）[中]；`generations(img2img)` → `/v1/images/generations`（历史兼容选项，串 `use_generations_for_img2img`、`use_chat_completions_for_img2img` 为旧字段名 [高]）。
- **GPT Image 2.5 的线路修正** [高（日志原文）]：`线路1：1K 图生图走 edits 但模型保持 gpt-image-2，2K/4K 保持原线路`；`线路2：统一走 edits，且 1K 改用 gpt-image-2-1k`。对应逻辑 `_resolve_effective_img2img_endpoint_mode` + `_should_use_line1_edits_for_1k_img2img` + `_should_strip_line2_optional_fields`/`_strip_line2_optional_fields`（剥除可选字段）[中]。
- `stream` 串存在，具体用途未确认（可能是 chat 请求可见流开关或 api_client 带出名）[低]。`user` 串存在，未确认（可能为 OpenAI `user` 参数）[低]。

**同步响应解析**：
- Images 同步（`/v1/images/generations|edits`）：`response_data` → 取 `data[]` 数组（`direct_items`、`top_data`、`nested_data`、`nested_items`），每项 `b64_json` 或 `url`；URL 下载失败 → `下载图片失败: `；无数据 → `响应中无可用图像数据`、`响应中无图像数据: ` / `: status=`[高]。
- Chat Completions（`_extract_chat_completions_content`）：无 `choices` → `chat/completions 响应中没有 choices`；取 `choices[0].message`（`message`、`content`、`images`、`output_text`、`text_content`），URL 用正则 `https?://[^\s'"<>]+` 从 text/`message.images[].image_url.url` 抽取并用 `seen_urls` 去重（`append_url`、`collect_from_text`），下载失败 → `下载 chat/completions 图片失败: `；无图像（仅文本）→ `chat/completions 响应中无可用图像数据`[高]。同名提取工具 `extract_openai_content` 亦在池中（api_client 提供）[中]。
- **异步线路**：提交后响应中取 `task_id` → 日志 `gpt-image-2 收到 task_id，开始自动轮询: `、` TE GPT image 2 任务`；`_poll_gpt_image_2_task` 用 `max_attempts`/`interval_seconds` 轮询 `GET /v1/images/tasks/{task_id}`，读 `task_status`/`status`；失败 → `gpt-image-2 异步任务失败: `、`gpt-image-2 异步任务超时，task_id=`（`TimeoutError`）、查询异常 → `gpt-image-2 任务查询失败: `；轮询循环日志 `gpt-image-2 任务轮询 `…` 完成，但未返回任何图片`[高]。

### 3.4 尺寸体系（`_RESOLUTION_CONFIGS` + `size_map`；字面串全部直接出现 [高]）

比例标签池：`1:1, 16:9, 9:16, 2:3, 3:2, 4:3, 3:4, 5:4, 4:5, 7:3, 3:7`（11 项；成员归入 `_SIZE_RATIO_OPTIONS` 逐一归属未确认；"7:3/3:7" 为超宽口径）。`_LEGACY_SIZE_TO_RATIO` + `_normalize_size_text` + `_normalize_ratio_label` 用于兼容旧工作流保存的 `WxH` 尺寸文本 [中]。

`WxH` 字面量（按分辨率档位推断 [中]，同口像素量级归档；个别条目档位归属未确认）：
- 1K：`1024x1024`、`1280x720/720x1280`、`1152x864/864x1152`、`1248x832/832x1248`、`1120x896/896x1120`、`1456x624/624x1456`
- 2K：`2048x2048`、`2560x1440/1440x2560`、`2304x1728/1728x2304`、`2496x1664/1664x2496`、`2240x1792/1792x2240`、`2560x3200/3200x2560`
- 4K：`2880x2880`、`3840x2160/2160x3840`、`3264x2448/2448x3264`、`3504x2336/2336x3504`、`3696x1584/1584x3696`、`3024x1296/1296x3024`

### 3.5 "快捷功能"提示词模板（QUICK_FUNCTION_*；选项与文案均字面串 [高]）

选项标签（共 10 项，含 NONE；`QUICK_FUNCTION_OPTIONS` 成员归属逐一未确认，标签存在 [高]）：
`NONE`、`导演故事板`、`九宫格[剧情]分镜`、`九宫格[导演]分镜`、`九宫格[场景]分镜`、`四宫格[剧情]分镜`、`四宫格[视角]分镜`、`黑白素写故事板`（pyd 中如此写，README 写"黑白速写故事板"）、`白底三视图`、`白底四视图`。

内置长模板（全部为完整可提取文本 [高]，汇总）：
- **导演故事板**（`DIRECTOR_STORYBOARD_PROMPT_PREFIX`/`SUFFIX`）：`请生成一张中文专业电影故事板图片，用作 Seedance 2.0 视频生成模型的参考图`……含用户可填字段（`画面比例`：`默认 16:9 横版`/`如果我填写 9:16，则生成 9:16 竖版`；`画面风格`：`都市情绪短片/商业广告感/生活纪实感/轻科幻感/悬疑感/动作电影感/温暖治愈感/唯美国风`；`特殊要求`/`动作节奏`/`光影`/`色彩和镜头语言`），生成要求 `- 不要漫画风，不要草图风，不要海报构图，不要水印，不要乱码`，版面布局（顶部信息栏｜类型｜15秒｜镜头数｜布局｜画面比例｜、左锚点栏 18%~22%、右侧核心分镜区 70%~75%、底部标签栏 `Lighting:｜Mood:｜Style:｜Audio:｜Camera:｜Keywords:`），清晰度限制（`密集小字/复杂图例/过多箭头/杂乱 UI/粗边框/乱码文字/无关字幕/摄像机设备/漫画风/草图风/儿童绘本风/过度插画风/海报构图/单张大图冒充分镜`）。
- **九宫格[剧情]分镜**：`根据提供的 剧情概述 / 画面主题 / 参考图，生成一张…3x3 九宫格分镜图，共 9 个连续镜头`……`人物外观/服装风格/体型比例/面部特征`一致性约束、`每个画面之间被清晰的黑色实线分割`、`没有任何文字/字母或标签`。**四宫格[剧情]分镜** 为其 2x2 四镜头变体。
- **九宫格[场景]分镜**：`生成一张严格的3x3九宫格图像，纯视觉展示`（中央透视效果图 / 俯视 / 地面纹理 / 左右墙 / 四角视角 + 两个材质道具特写，`绝对不要生成任何解释性文字或图表排版`）。**四宫格[视角]分镜** 为 2x2 四视角变体（透视/俯视/正前方/正后方）。
- **黑白素写故事板**（`BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX`）：`按照输入的故事脚本生成15秒视频的9宫格故事板，保持16:9宽屏`，`黑白铅笔速写风格与彩色标注系统`（红=身体运动/蓝=摄影机运动/绿=取景构图/橙=灯光方向/紫=声音情感/黑=镜头笔记）。
- **白底三视图 / 白底四视图**：`三视图（正面/侧面/背面），白色纯色背景，人物角色设计图`；`参照原图生成人物面部特写搭配全身三视图组合画面；画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照/侧面全身照/背面全身照…严格对齐人物人体比例，杜绝透视畸变…`（推断前者→三视图、后者→四视图 [中]）。
- 另有英文模板片段 `storyboard sheet, ` + `…black UI layout, grid panel composition, professional film storyboard,` [高]，与哪个选项绑定未确认 [低]。

模板拼接：`_generate_with_gpt_image_2_api` 内 `quick_prefix`/`QUICK_FUNCTION_PREFIXES` 与 `connected_prompt_text`/`final_prompt_text` 组合，用户提示词 + 快捷前/后缀生成 `final_prompt_text` [中]。

### 3.6 多任务并发与运行时行为

- **`BatchGenerationRunner`（task_runner）** [高]：`generate_images` 把 `batch_size` 个生成任务交给 `BatchGenerationRunner`（证据串同名 + `tasks`/`actual_workers`/`continue_on_error`/`progress_bar`/`stagger_delay`/`thread_id`）；`actual_workers` 推断来自 `CONFIG_MANAGER.load_max_workers`（并受 `network_workers_cap` 约束，config.ini `max_workers = 4`）[中]。`_generate_single_image_gpt_image_2` 为线程 worker；并带相邻日志 `开始请求...`/`批次 `…`/`总批次`[中]。
- **进度条** [高]：`comfy.utils` + `ProgressBar` + `update_absolute`；内部 `progress_callback(completed_count, total_count)`、日志 `完成 - 生成 `、`s，平均 `（配 `.2f` 浮点格式）、`总耗时: `、`平均速度`、` 张/s`。
- **中断处理** [高]：`comfy.model_management.throw_exception_if_processing_interrupted` + `InterruptProcessingException`；`_ensure_not_interrupted`/`interrupt_checker` 在长请求间隙轮询；被取消日志 ` 已取消`、`canceled`/`cancelled`；失败结果经 `_build_failure_result` + `ErrorCanvas` / `build_error_tensor_from_text` 生成占位错误图（`error_canvas`/`error_tensor`），配合 `continue_on_error` 输出不中断 [中→高]。
- **图像解码返回** [高]：API 返回的 `b64` 列表 → `base64_to_tensor_parallel`（`decoded_tensors`/`decoded_tensor`/`decoded_count`/`decode_workers`）→ `build_preview_tuple`（UI `images` 预览）→ 输出 `IMAGE`；摘要 `summary_text`（`成功生成 `…` / 失败 `…` 成功获取 N 张图像`、`成功生成`/`生成失败`、`实际尺寸: `、`实际分辨率`）。`prepare_input_images` / `extract_numpy_images` 处理输入图 tensor → base64（`image_base64`、`b64encode`）。
- **脱敏日志** [高]：`使用 API Base URL: [已脱敏]`、`使用 API Key: `（配 `sanitize_api_key`/`masked_key`）、`配置缺失`、`请在 config.ini 或节点输入中填写有效配置`、`未知错误`、`未生成任何图像`。

## 4. 外部依赖与副作用

### 4.1 网络（全部经 Python `requests`；DLL 本身无 WinSock [高]）
- 端点：`/v1/images/generations`、`/v1/images/edits`、`/v1/chat/completions`、`/v1/images/tasks/{task_id}`（GET 轮询）+ 无 `/v1` 短后缀变体 [高]。
- 认证：`Authorization: Bearer {api_key}` [高]；API Key 来源优先级：节点输入 → `config.ini`（`ConfigManager.load_api_key`，节名样例 `[gemini]`）[中→高，详见 config_manager.md]；Base URL 同理（`get_effective_api_base_url`、`http://`/`https://` 前缀检查 [中]）。
- 代理：`bypass_proxy` 直传 api_client 的 session 构造（`trust_env`/`proxies` 语义见 api_client.md §3.5）[中]；`verify_ssl`；`_suppress_insecure_warning` 屏蔽 InsecureRequestWarning [中]。
- 超时：`_resolve_timeout` → `connect_timeout`/`read_timeout`（数值未确认）；请求中断通过后台线程 + `threading` 辅助（`async_compat`/日志 `异步兼容: ` 推断为该机制的开关参数，归属未确认 [低→中]）。

### 4.2 文件系统与配置
- 读 `<插件目录>/config.ini`（键 `api_key`、`api_base_url`、`max_workers`、`network_workers_cap`、`bypass_proxy`，经 `ConfigManager`）[中→高，互证 config_manager.md]；本模块自身 `os.path`（`abspath`/`dirname`/`basename`）用于定位插件目录 [中]。
- 生成的图像**未发现**磁盘保存证据（无 `folder_paths`/`save` 串），仅 UI 预览输出 [中]；`filename_prefix` 用途未确认。

### 4.3 第三方库迹象
`torch`、`numpy`（经 image_codec）、`PIL`（`Image`/`BytesIO`）、`requests`、`threading`、`base64`、`json`、`random`、`time`、`typing`、`asyncio`（`async_compat`/协程标志 `_is_coroutine`，Cython 自带）[高]。

## 5. 错误处理与用户可见文案（均 pyd 原文 [高]）

| 消息 | 触发场景 |
|---|---|
| `请输入提示词` | prompt 为空校验 |
| `请填写有效的 API Key` / `请在 config.ini 中配置 API Key 或在节点中填写` | `_resolve_key_and_url` 找不到有效 Key |
| `请在 config.ini 中配置 API URL 或在节点中填写` / `未配置有效的 API Base URL` | 找不到有效 Base URL |
| `请在 config.ini 或节点输入中填写有效配置` | Key+URL 均缺失的汇总提示 |
| `配置缺失` / `使用 API Key: ` / `使用 API Base URL: [已脱敏]` | 运行日志（脱敏回显） |
| `gpt-image-2 请求失败: ` / `: status=`/`HTTP ` | 请求抛错 / HTTP 状态非 2xx 的摘要（经 `_format_api_error_payload`/`_format_http_error_response`，含 `...（错误响应已截断）` 截断） |
| `chat/completions 响应中没有 choices` | Chat 线路响应结构异常 |
| `chat/completions 响应中无可用图像数据` | Chat 线路只返回文本 |
| `下载 chat/completions 图片失败: ` / `下载图片失败: ` | 图片 URL 下载异常 |
| `响应中无可用图像数据` / `响应中无图像数据: ` | 同步 Images 响应无 data[ ] |
| `gpt-image-2 收到 task_id，开始自动轮询: ` / `gpt-image-2 任务轮询 …` | 提交进入异步轮询 |
| `gpt-image-2 异步任务失败: ` / `gpt-image-2 异步任务超时，task_id=` / `gpt-image-2 任务查询失败: ` / `…完成，但未返回任何图片` | 轮询各失败分支 |
| ` 已取消` / `生成失败` / `未生成任何图像` | 中断/全失败汇总 |
| `成功获取 N 张图像` / `成功生成 … / 失败 …` / `实际尺寸: ` / `实际分辨率` / `模式=`/`线路选择: `/`异步兼容: `/`输出格式: `/`背景: `/`质量: `/`模型: `/`分辨率: ` / `总耗时: ` / `平均速度` / `.2f` / `s，平均 ` / ` 张/s` | 过程与摘要日志 |

## 6. 证据附录（关键字符串摘录，分组、去噪）

### 6.1 节点注册
```
TE_image_pro_gpt_image_2    TE MAN GPT Image 2 & 2.5    TE MAN/GPT
使用 gpt-image-2 通过 OpenAI Images API 进行文生图或图生图
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / INPUT_TYPES / RETURN_TYPES / RETURN_NAMES / FUNCTION / CATEGORY / DESCRIPTION / OUTPUT_NODE / IMAGE / STRING / forceInput
```

### 6.2 方法名（qualname，TEGPTImage2Node.*）
```
__init__ _ensure_not_interrupted _build_failure_result _normalize_resolution
_normalize_size_text _get_resolution_config _normalize_ratio_label _resolve_request_size
_resolve_effective_img2img_endpoint_mode _should_use_line1_edits_for_1k_img2img
_resolve_request_model _should_strip_line2_optional_fields _strip_line2_optional_fields
_resolve_key_and_url _build_gpt_image_2_request _resolve_gpt_image_2_endpoint
_resolve_gpt_image_2_task_endpoint _normalize_task_result _poll_gpt_image_2_task
_send_sync_gpt_image_2_request _extract_sync_gpt_image_2_content
_extract_chat_completions_content(_append_url/collect_from_text/genexpr)
_generate_single_image_gpt_image_2 _generate_with_gpt_image_2_api(progress_callback)
generate_images   _format_api_error_payload _format_http_error_response
```

### 6.3 端点与请求
```
/v1/images/generations /v1/images/edits /v1/chat/completions /v1/images/tasks/
/images/generations /images/edits /chat/completions /images/tasks/
http:// https:// Authorization Bearer  Content-Type application/json
model prompt size quality background output_format stream user
task_id task_status status data b64_json url image_url image_data_url data:image/
messages role content choices direct_items top_data nested_data nested_items
files image_1..image_9 seen_urls https?://[^\s'"<>]+
json.dumps ensure_ascii post session verify verify_ssl b64encode utf-8
_resolve_timeout connect_timeout read_timeout TimeoutError RequestException raise_for_status
```

### 6.4 并发 / 中断 / 进度
```
task_runner BatchGenerationRunner continue_on_error actual_workers stagger_delay thread_id
load_max_workers max_attempts interval_seconds avg_time sum
comfy.model_management throw_exception_if_processing_interrupted InterruptProcessingException
current_thread threading sleep interrupt_checker canceled cancelled
comfy.utils ProgressBar update_absolute progress_callback completed_count total_count batch_size
```

### 6.5 常量 / 选项
```
_MODEL_NAME _MODEL_OPTIONS _SIZE_RATIO_OPTIONS _RESOLUTION_OPTIONS _RESOLUTION_CONFIGS
_LEGACY_SIZE_TO_RATIO _IMG2IMG_ENDPOINT_OPTIONS _DEFAULT_OUTPUT_FORMAT _DEFAULT_BACKGROUND
QUICK_FUNCTION_OPTIONS/PREFIXES/NONE/DIRECTOR_STORYBOARD/BLACK_WHITE_STORYBOARD
DIRECTOR_STORYBOARD_PROMPT_PREFIX/SUFFIX BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX
GPT Image 2 / GPT Image 2.5 / gpt-image-2 / gpt-image-2.5 / -1k
gpt-image-2-1k gpt-image-2-2k gpt-image-2-4k
1:1 16:9 9:16 2:3 3:2 4:3 3:4 5:4 4:5 7:3 3:7
1024x1024 1280x720 720x1280 1152x864 864x1152 1248x832 832x1248 1120x896 896x1120 1456x624 624x1456
2048x2048 2560x1440 1440x2560 2304x1728 1728x2304 2496x1664 1664x2496 2240x1792 1792x2240 2560x3200 3200x2560
2880x2880 3840x2160 2160x3840 3264x2448 2448x3264 3504x2336 2336x3504 3696x1584 1584x3696 3024x1296 1296x3024
png auto Auto high
```

### 6.6 协作模块符号
```
api_client API_CLIENT GeminiApiClient _get_session _resolve_timeout _suppress_insecure_warning
extract_openai_content async_compat
config_manager CONFIG_MANAGER ConfigManager load_api_key get_effective_api_base_url
sanitize_api_key masked_key load_max_workers
image_codec ImageCodec ErrorCanvas prepare_input_images prepare_input_image_data_urls
prepare_input_image_file_parts base64_to_tensor_parallel decode_workers decoded_tensors
build_preview_tuple build_error_tensor_from_text extract_numpy_images image_base64
task_runner progress_bar PLUGIN_DIR MODULE_DIR source_py_backup
torch List[torch.Tensor] requests session
```

### 6.7 未确认事项汇总
- `quality`/`background`/`output_format` 的具体选项表与默认值（仅见 `high`/`auto`/`png`/`Auto`孤立串）——未确认。
- `_RESOLUTION_CONFIGS` 中 2K/4K 档位对个别尺寸（如 2560x3200 与 3696x1584 组）的精确归属——未确认。
- `RETURN_TYPES`/`RETURN_NAMES` 的完整成员（仅 IMAGE/STRING 两串存在）——未确认。
- `stream`、`user` 两个孤立键的用途——未确认。
- 本节点向 GeminiApiClient 调用的确切方法名（send_openai_request / poll_openai_task 等在 api_client 中存在，但本 pyd 未直接出现这些名；本模块自建 `_poll_gpt_image_2_task` 等自有方法）——未确认。
- `filename_prefix` 的实际用途（未见磁盘写盘证据）——未确认。
- 前端 JS 曾含 `TE_image_pro_special_async2` 等其他节点，与本模块无关，勿混淆。

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 环境真实加载采集（`Windows-2025Server-10.0.26100`，Python 3.13.16，ComfyUI 目录 `D:\a\_temp\ComfyUI`，TE_MAN 无导入错误）。实际注册类是明文包装层 `TE_MAN.Grok_Safe_PY.TEGPTImage2SafePyNode`（经 `zzzz_grok_autoscale_patch` 以同名注册键覆盖），下表为**包装层最终暴露**的完整参数表；pyd 基类 `TEGPTImage2Node` 的内部行为不受影响。

### 7.1 运行时 INPUT_TYPES 全表（`TE_image_pro_gpt_image_2`，包装层暴露）

**required：**

| 参数 | 类型 | 选项 / 默认值 | 约束 | tooltip（原文） |
|---|---|---|---|---|
| `prompt` | STRING multiline | 默认 `一只戴着墨镜的白色猫咪，电影感，细节丰富` | — | `gpt-image-2 提示词` |
| `api_key` | STRING | 默认 `""` | — | `API Key；留空则使用 config.ini 中配置` |
| `api_base_url` | STRING | 默认 `""` | — | `服务地址；留空则使用 config.ini 中配置` |
| `batch_size` | INT | 默认 `1` | min 1 / max 8 | `生成批次数量；每个批次生成 1 张图` |
| `分辨率(价格不同)` | combo | `1K, 2K, 4K`，默认 `1K` | — | `1K / 2K / 4K；分辨率不同,价格不同。` |
| `size` | combo | `Auto, 1:1, 16:9, 9:16, 3:2, 2:3, 4:3, 3:4, 5:4, 4:5, 7:3, 3:7`（**12 项，Auto 为首选项**），默认 `16:9` | — | `选择需要生成的分辨率比例。` |

**optional：**

| 参数 | 类型 | 选项 / 默认值 | 约束 | tooltip（原文） |
|---|---|---|---|---|
| `seed` | INT | 默认 `-1` | min -1 / max 102400 / `control_after_generate: true` | `仅用于 ComfyUI 工作流记录，不写入请求体。` |
| `image_1` … `image_9` | IMAGE（9 个口） | — | — | `参考/编辑输入图像 N（可选）` |
| `线路选择` | combo | `线路1, 线路2`，默认 `线路1` | — | `线路1：1K 图生图走 edits 但模型保持 gpt-image-2，2K/4K 保持原线路。线路2：统一走 edits，且 1K 改用 gpt-image-2-1k。`（与 §3.3 日志原文互证） |
| `绕过代理` | BOOLEAN | 默认 `false` | — | `需要忽略系统代理/梯子时开启` |
| `快捷功能` | combo | `无, 白底三视图, 白底四视图, 九宫格[剧情]分镜, 九宫格[场景]分镜, 九宫格[导演]分镜, 四宫格[剧情]分镜, 四宫格[视角]分镜, 导演故事板, 黑白素写故事板`（**10 项，顺序实锤**），默认 `无` | — | `使用快捷功能生成。` |

**运行时未暴露**（包装层裁剪，§3.1 中相关推断行据此修正）：`模型选择`/`model_choice` 下拉（GPT Image 2 vs 2.5 的选择不在 Python INPUT_TYPES 中，属前端 JS widget 侧行为）、`quality`、`background`、`output_format`、`verify_ssl`、`filename_prefix`、上游文本 forceInput 输入口。节点 `DESCRIPTION = "使用 gpt-image-2 通过 OpenAI Images API 进行文生图或图生图。"`（带句号，实锤）。

**注册元数据（实锤）**：`FUNCTION = "generate_images"`、`CATEGORY = "TE MAN/OpenAI"`（**注意**：运行时 CATEGORY 为 `TE MAN/OpenAI`，与 pyd 静态串 `TE MAN/GPT` 不同——包装层覆盖了 CATEGORY）、`OUTPUT_NODE = True`、`RETURN_TYPES = ["IMAGE", "STRING"]`、`RETURN_NAMES = ["images", "text"]`。显示名 `TE MAN GPT Image 2 & 2.5`。

### 7.2 模块常量实锤值（动态采集，pyd 模块 `TE_MAN.GPT_Image_2_Generator`）

- `QUICK_FUNCTION_NONE = "无"`；`QUICK_FUNCTION_DIRECTOR_STORYBOARD = "导演故事板"`；`QUICK_FUNCTION_BLACK_WHITE_STORYBOARD = "黑白素写故事板"`
- `QUICK_FUNCTION_OPTIONS`（10 项精确顺序）：`无, 白底三视图, 白底四视图, 九宫格[剧情]分镜, 九宫格[场景]分镜, 九宫格[导演]分镜, 四宫格[剧情]分镜, 四宫格[视角]分镜, 导演故事板, 黑白素写故事板`
- `QUICK_FUNCTION_PREFIXES` 关键映射：`九宫格[导演]分镜` → `storyboard sheet, 九宫格,black UI layout, grid panel composition, professional film storyboard,`（§3.5 英文模板归属**实锤**绑定此项）；`导演故事板` → `""`、`黑白素写故事板` → `""`（正文改由 `DIRECTOR_STORYBOARD_PROMPT_PREFIX/SUFFIX` 与 `BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX` 拼接）；其余 7 项与 Grok_Image 模块同文
- `DIRECTOR_STORYBOARD_PROMPT_PREFIX`（`请生成一张中文专业电影故事板图片，用作 Seedance 2.0 视频生成模型的参考图。…【故事内容】：`）与 `DIRECTOR_STORYBOARD_PROMPT_SUFFIX`（【画面比例】/【画面风格】/【特殊要求】/【生成要求】/版面四区布局/【清晰度限制】全文）完整原文采集成功——§3.5 导演故事板模板全文实锤
- `BLACK_WHITE_STORYBOARD_PROMPT_SUFFIX` 全文实锤（§3.5 黑白素写故事板）
- `_MAX_API_ERROR_TEXT_LENGTH = 500`、`_MAX_DISPLAY_ERROR_LENGTH = 600`（错误截断长度定值）
- `MODULE_DIR` / `PLUGIN_DIR = D:\a\_temp\ComfyUI\custom_nodes\TE_MAN`；基类层 `NODE_CLASS_MAPPINGS["TE_image_pro_gpt_image_2"] = custom_nodes.TE_image.GPT_Image_2_Generator.TEGPTImage2Node`
- `_MODEL_NAME`、`_MODEL_OPTIONS`、`_SIZE_RATIO_OPTIONS`、`_RESOLUTION_OPTIONS`、`_RESOLUTION_CONFIGS`、`_LEGACY_SIZE_TO_RATIO`、`_IMG2IMG_ENDPOINT_OPTIONS`、`_DEFAULT_OUTPUT_FORMAT`、`_DEFAULT_BACKGROUND` 未被 introspection 采集（推断为非平铺常量/容器），取值仍未知

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2.4 / §6.7 `OUTPUT_NODE` | **已确认：True（动态回填）** |
| §2.4 / §6.7 `RETURN_TYPES` / `RETURN_NAMES` 完整成员 | **已确认：`("IMAGE", "STRING")` / `("images", "text")`（动态回填）** |
| §3.1 比例选项表（11 项，Auto 归属未确认） | **已确认：`size` 下拉共 12 项，`Auto` 为首选项（动态回填）** |
| §3.1 分辨率标签 / `_RESOLUTION_OPTIONS` | **已确认：标签为 `分辨率(价格不同)`，选项 `1K/2K/4K`，默认 `1K`（动态回填）** |
| §3.1 `quality` / `background` / `output_format` 选项表与默认值 | **已确认：包装层运行时不暴露这三个参数**（下拉被裁剪；选项表仍无法从 UI 得知）（动态回填） |
| §3.1 `batch_size` 默认值 | **已确认：默认 1，范围 1~8（动态回填）** |
| §3.1 `bypass_proxy` / `verify_ssl` / `filename_prefix` 默认值 | **已确认：`绕过代理` 默认 False；`verify_ssl`、`filename_prefix` 运行时未暴露**（动态回填） |
| §3.5 `QUICK_FUNCTION_OPTIONS` 成员归属与顺序 | **已确认：10 项精确顺序见 §7.2（动态回填）** |
| §3.5 英文模板片段绑定 | **已确认：绑定 `九宫格[导演]分镜`（动态回填）** |
| §6.7 `_RESOLUTION_CONFIGS` 各档位尺寸归属 | introspection 未采集该常量，保持未确认 |
| §6.7 `stream` / `user` 孤立键用途 | introspection 未涉及，保持未确认 |
| §6.7 `filename_prefix` 用途 | 运行时未暴露该输入，"可能仅前缀参数"的猜测维持，保持未确认 |

另注：运行时 `prompt` 不带 `defaultInput`（§2.4 前端 JS 的「提示词输入接口」为纯前端行为，Python 层未开放 forceInput 口）。
