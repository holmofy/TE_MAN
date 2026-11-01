# TE_HappyH_Video.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_HappyH_Video`（PE 导出表唯一导出符号）。导入依赖仅 python3.dll / KERNEL32 / VCRUNTIME140 / CRT —— 无 WinSock，网络全走 Python 层 `requests` [高]。静态分析（pefile 导入/导出表 + ASCII/UTF-8 字符串提取）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

**节点模块**：TE_MAN（原包名 `custom_nodes.TE_image`，编译源路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_HappyH_Video.c`、原始 .py 路径 `custom_nodes/TE_image/source_py_backup/TE_HappyH_Video.py` [高]）中的 **HappyHorse（快乐马）视频生成节点**，注册名 `TE_image_pro_happyh_video`（类 `TEHappyHVideoNode`，显示名 `TE MAN HappyH Video`，CATEGORY `TE MAN/HappyHorse`）[高]。对应 README v3.8 更新日志「增加 TE happyh video 节点 支持快乐马」（README.md:349）[高]。模块 docstring 原文：`ComfyUI 节点：TE MAN HappyH Video / - POST /v1/videos 提交任务 / - GET /v1/videos/{task_id} 轮询状态` [高]。任务日志标题 `TE MAN HappyH Video 任务`（与 `***` 分隔符字符串共存，疑为 logger 边框装饰 [中]）。模型名固定为 `happyhorse-video`（常量 `_FIXED_MODEL_NAME`）[高]。

与 VEO/Jimeng 节点同属"自带协议层"的独立视频节点（详见 §4）。

## 2. Python API

- 导出：`PyInit_TE_HappyH_Video` [高]。
- 模块级函数（qualname 来自 Cython 符号串 [高]；形参名来自紧邻符号 [中]）：
  - 中断：`_ensure_not_interrupted`（调用 `comfy.model_management.throw_exception_if_processing_interrupted` [高]）
  - 认证/URL：`_resolve_key_and_url(api_key?, api_url?)`（返回注解 `Tuple[str, str]`，即 resolved_key + base url [中]）、`_resolve_submit_url(api_base_url?)`、`_resolve_task_url(task_id?, api_base_url?)`
  - 响应解析：`_read_json_response_or_raise(resp?, label?)`、`_absolutize_url(raw_url?, endpoint?)`、`_extract_task_id`、`_extract_task_status`、`_extract_failure_message`、`_extract_video_url(values?)`
  - 输出：`_get_output_dir`、`_download_video(video_url?, timeout_s?)` [中，形参推断]
  - 图像编码：`_encode_image_batch_to_file_parts`（返回注解 `Tuple[List[Tuple[str, Tuple[Any, ...]]], Dict[str, Any]]`，即 requests multipart files 列表 + 摘要 [中]）、`_append_reference_batches(target_batches?)`、`_merge_reference_images`、`_summarize_for_log(items?)`
  - 分辨率：`_normalize_resolution_name(resolution?)`、`_ratio_to_size(ratio?, ...)`（tooltip：`会转换成 size，例如 16:9 -> 1280x720` [高]）
- 类 `TEHappyHVideoNode`：唯一节点类，方法 `INPUT_TYPES`、`_resolve_mode_and_model(mode?, image_count?)`、`_build_multipart_parts(prompt_text?, model_name?, image_files?, duration? ...)`、`generate_video` [高]。
- 模块常量 [高，名称]：`_MODE_AUTO / _MODE_T2V / _MODE_I2V / _MODE_R2V`、`_MODE_TO_MODEL`、`_FIXED_MODEL_NAME`、`_FIXED_RESOLUTION_NAME`、`_RATIO_OPTIONS`、`_DEFAULT_BASE_URL`、`CONFIG_MANAGER`、`PLUGIN_DIR`、`MODULE_DIR`、`_HAS_COMFY_VIDEO`。
  - `_MODE_*` 对应中文选项标签：`自动` / `文生视频` / `首帧生视频` / `多图参考` [高] —— **已确认：`_MODE_AUTO="自动"`、`_MODE_T2V="文生视频"`、`_MODE_I2V="首帧生视频"`、`_MODE_R2V="多图参考"`（动态回填）**。
  - **常量值已确认（动态回填）**：`_DEFAULT_BASE_URL = ""`（空串！无硬编码默认 URL，全靠 config.ini 或节点输入）、`_FIXED_MODEL_NAME = "happyhorse-video"`、`_FIXED_RESOLUTION_NAME = "720P"`、`_MODE_TO_MODEL = {"文生视频": "happyhorse-video", "首帧生视频": "happyhorse-video", "多图参考": "happyhorse-video"}`（各模式映射值全部实锤，均为 `happyhorse-video`）、`_RATIO_OPTIONS = ["16:9","9:16","1:1","4:3","3:4","4:5","5:4","9:21","21:9"]`（顺序实锤）、`_HAS_COMFY_VIDEO = True`。
  - **UI 形参名修正（动态回填）**：比例下拉的最终形参名为 **`ratio`**（非 `ratio`/`aspect_ratio` 存疑状态，实锤为 `ratio`）。
- ComfyUI 节点注册 [高]：`NODE_CLASS_MAPPINGS` 键 `TE_image_pro_happyh_video`，显示名 `TE MAN HappyH Video`，`CATEGORY: TE MAN/HappyHorse`，`FUNCTION: generate_video`，`RETURN_TYPES / RETURN_NAMES / OUTPUT_NODE / INPUT_TYPES / tooltip / required / optional` 字符串均存在 [高]。

## 3. 与 TE_Prompt_Text 的 TE_H3_REFERENCES 对接（H3 参考素材机制）

用户假设"TE_Prompt_Text.pyd 输出 TE_H3_REFERENCES 口对接本模块"——**二进制证据显示对接方式不同，需修正**：

1. `TE_H3_REFERENCES` 是前端注入的 **ComfyUI 类型化插座名**，不是本模块的类型：`TE_HappyH_Video.pyd` 内 **0 处** `TE_H3_REFERENCES` / `TE_H3_Reference_Bridge` 字节命中 [高，全文件搜索]。`TE_Prompt_Text.pyd` 与 `TE_H3_Prompt_Enhancer.pyd` 各含 1 处 `TE_H3_REFERENCES` [高]。
2. web/js/te_prompt_text.js 揭示该插座的实际接线 [高，JS 原文]：
   - `ensureH3ReferenceOutput`：给 `TE_prompt_text` 节点添加输出 `addOutput('H3参考素材','TE_H3_REFERENCES')`；
   - `ensureH3ReferenceInput`：给 `TE_H3_Prompt_Enhancer` 节点添加输入 `addInput('H3参考素材','TE_H3_REFERENCES')`；
   - 即 **TE_H3_REFERENCES 链路是 TE_Prompt_Text → TE_H3_Prompt_Enhancer（H3 提示词增强节点）**，HappyH 视频节点不在这条插座链上。
3. TE_Prompt_Text → 本模块的真实桥接是 **@ 提及菜单的 target 配置**（JS `PROMPT_TEXT_TARGET_CONFIGS['TE_image_pro_happyh_video']`）[高]：
   ```js
   'TE_image_pro_happyh_video': {'imageInputs': Array.from({length:9}, (_,i) =>
       ({name:'image_'+(i+1), label:'图片'+(i+1), insertText:'图'+(i+1)}))}
   ```
   即提示词中的 `图1`…`图9` 标记（编辑器渲染为 chip）一一对应本节点 `image_1`…`image_9` 图像输入。
4. 本节点自身 tooltip 另给出 API 侧标记语法：`多图参考模式可用 [Image 1]`、`[Image 2] `、`指代图片`（碎片拼接，原文疑为「多图参考模式可用 [Image 1]、[Image 2] 指代图片」）[高] —— 多图参考模式下提交给 HappyHorse 服务的 prompt 用 `[Image N]` 指代第 N 张参考图。`图N`（前端插入）与 `[Image N]`（节点 tooltip 文档）两套标记各自生效的环节（编辑器 chip vs API 请求体）为合理推断 [中]；服务端具体解析哪种 未确认。

## 4. 节点规格（TEHappyHVideoNode）

### 4.1 模式（mode，下拉；`_resolve_mode_and_model`）

| 选项 | 内部常量 | 行为（均来自中文串 [高]） |
|---|---|---|
| `自动`（疑默认 [中]） | `_MODE_AUTO` | tooltip：`自动：无图=文生视频，1图=首帧生视频，多图=多图参考` —— **已确认：默认 `自动`（动态回填）** |
| `文生视频` | `_MODE_T2V` | `文生视频模式不接收图片；如需传图请选择自动` |
| `首帧生视频` | `_MODE_I2V` | `首帧生视频模式必须且只能输入 1 张图片` |
| `多图参考` | `_MODE_R2V` | `多图参考模式需要 1-9 张参考图`；上限校验 `HappyHorse 多图参考最多支持 9 张图片，当前输入 N 张` |

`_MODE_TO_MODEL` 将模式映射到模型名 —— **已确认：三模式（文生视频/首帧生视频/多图参考）映射值均为 `happyhorse-video`（动态回填）**。`不支持的模式: ` 为模式归一化失败报错 [高]。

### 4.2 输入参数（INPUT_TYPES）

类型名 `STRING / INT / BOOLEAN / IMAGE / VIDEO` 与 `required / optional / tooltip / multiline / default / min / max` 键均存在 [高]。分组与默认值已由动态回填（§7.2）全部实锤，下表为原静态分析标注：

**required [已确认分组（动态回填）]**：`prompt / api_key / api_base_url / mode / ratio / duration` 六项。
- `prompt`：STRING multiline，tooltip `用于生成视频的提示词。多图参考模式可用 [Image 1]、[Image 2] 指代图片。`（tooltip 全文实锤，原碎片拼接推断证实），带 `defaultInput: true` 标记 [高]；空值报错 `请输入 prompt` [高]。默认值实锤：`一座由硬纸板和瓶盖搭建的微型城市，在夜晚焕发出生机。一列硬纸板火车缓缓驶过，小灯点缀其间，照亮前路。`（动态回填）。
- `mode`：下拉（§4.1），枚举 `["自动","文生视频","首帧生视频","多图参考"]`，默认 `自动`（动态回填）。
- `ratio`：下拉，**形参名实锤为 `ratio`**，枚举 9 项（顺序见 §2 常量回填），默认 `16:9`，tooltip `会转换成 size，例如 16:9 -> 1280x720`（动态回填）。
- `duration`：**已确认：STRING 单选下拉（非 INT），枚举 `["3","4","5","6","7","8","9","10","11","12","13","14","15"]` 共 13 档，默认 `"5"`**，tooltip `视频时长（秒），范围 3-15`（动态回填）。
- `api_key`：STRING 单行，默认 `""`，tooltip `API Key；留空则读取 config.ini`（动态回填：归入 required）。
- `api_base_url`（正文原记 `api_url`）：STRING 单行，默认 `""`，tooltip `API 地址，例如 https://newapi.xxx.com 或完整的 /v1/videos 地址`（动态回填：归入 required，形参名实锤为 `api_base_url`）。

**optional [已确认分组（动态回填）]**：`seed / image_1…image_9 / poll_interval_s / timeout_s / 绕过代理`。
- `seed`：INT，默认 `-1`，min `-1` / max `2147483647`，`control_after_generate` 开启，tooltip `仅供 ComfyUI 工作流使用；不会写入请求体`（原 tooltip 推断证实，动态回填）；**不写入请求体已由 tooltip 直证**。
- `image_1`…`image_9`：IMAGE ×9，tooltip `首帧/参考图 1`、`参考图 2`…`参考图 9` [高]；**不带 control_after_generate**（原 [中] 推断修正，动态回填）。
- `poll_interval_s`：INT，默认 `15`，min `5` / max `60`，tooltip `轮询间隔（秒），官方建议约 15 秒`（动态回填）。
- `timeout_s`：INT，默认 `900`，min `120` / max `3600`，tooltip `任务最长等待时间（秒）`（形参名实锤 `timeout_s`，动态回填）。
- `绕过代理`（正文原记 `bypass_proxy`）：BOOLEAN，默认 `false`，tooltip `需要忽略系统代理/梯子时开启`（动态回填）。
- `resolution` 下拉**未暴露**：INPUT_TYPES 无 resolution 参数（原 §4.2 "resolution 疑为两档 720p/1080p" 修正——分辨率档位不作为 UI 输入，`_FIXED_RESOLUTION_NAME = "720P"` 内部固定，动态回填）。
- `watermark` 字符串存在 [高]：**已确认：不是 UI 参数**（INPUT_TYPES 无此项，仅疑为提交体内部字段，动态回填）。

### 4.3 返回（RETURN_TYPES / RETURN_NAMES）

- **已确认（动态回填）：`RETURN_TYPES = [VIDEO, STRING, STRING, STRING]`，`RETURN_NAMES = ["video", "video_url", "task_id", "response"]`，`OUTPUT_NODE = True`**。类型池中出现 `VIDEO` [高]。`VideoFromFile`（`comfy_api.input_impl`）包装下载的 mp4；`video_url` 输出下载地址、`task_id` 输出任务 ID、`response` 输出响应摘要；`_HAS_COMFY_VIDEO = True`（标准环境恒走 VIDEO 分支）。OUTPUT_NODE 行为：下载并预览视频（`results` + ui 输出模式 [中]）。

### 4.4 关键行为流程（generate_video）

1. **校验**：prompt 非空；按 mode 校验图片数量（§4.1）；`不支持的 IMAGE 维度: ` / `不支持的参考图维度: `（tensor `ndim` 校验 [高]）。
2. **合并参考图**：`_append_reference_batches` + `_merge_reference_images` 把 9 路图像 batch 顺序合并（`merged_images`，日志 `Input images: N 张` [高]）。
3. **编码**：`_encode_image_batch_to_file_parts` 经 `image_codec.encode_numpy_image_to_api_file_part` 把每帧编码为 PNG 文件部件（`.png`、`mime_type`、`basename`、`splitext` 字符串 [高]）；缺 numpy 报 `缺少图像依赖（numpy）: ` [高]。
4. **提交**：`POST {base}/v1/videos`，**multipart/form-data**（`multipart upload`、files 字段 **`input_reference[]`** [高]）；字段含 `model`、`prompt`、`duration`、`resolution`/`size`、`watermark` 等 [中，字段归属]；头部 `Authorization: Bearer <key>`、`User-Agent: ComfyUI-TE_API/1.0`、`content-type` [高]；日志 `Submit API: `、`提交任务接口`、`Task ID: `、`任务ID: ` [高]；响应取 `taskId`（驼峰字段 [高]），缺失报 `接口未返回 task_id：`。
5. **轮询**：`GET /v1/videos/{task_id}`（`/videos/`、`/v1/videos/` [高]），日志 `轮询任务接口`、`任务状态: `、`继续轮询` [高]；进度条 `comfy.utils.ProgressBar` + `progress_guess`（按 `started_at`/`elapsed` 估算 [中]）；每次循环 `_ensure_not_interrupted` 响应 ComfyUI 中断 [高]。
6. **终态判定**：成功态 `SUCCEEDED / COMPLETED / SUCCESS`，失败态 `FAILED / FAILURE / ERROR`，其余 `UNKNOWN` 继续轮询 [高，状态字面量]；字段名 `taskStatus`、`status`、`data`、`output`、`results`、`videos`、`url`、`content_url`、`video_url` 为多候选提取键 [高，`_extract_*` 配套]。超时报 `HappyHorse 任务轮询超时（N 秒）` [高]。
7. **下载**：`_download_video` 流式下载（`stream=True`、`iter_content`、`chunk_size`）到 `folder_paths.get_output_directory()`（日志 `开始下载视频到 ComfyUI/output ...` [高]），文件名前缀 **`te_happyh_video_`** + `.mp4` [高]（时间戳构成方式 未确认）；日志 `视频已保存: ` [高]。
8. **日志脱敏**：`sanitize_api_key` / `masked_key` / `API Key: ` / `API URL: [已脱敏]` / `payload_summary`（`json.dumps(..., ensure_ascii=False)` [高]）。

### 4.5 协议层关系

本模块不使用 `api_client.GeminiApiClient`（与 VEO/Jimeng 同模式，自带 requests 协议层）。复用内部库 [高，符号证据]：
- `config_manager`（`ConfigManager / CONFIG_MANAGER / load_api_key / get_effective_api_base_url / sanitize_api_key / should_bypass_proxy(bypass_proxy)`）—— Key/URL 解析与代理旁路；
- `image_codec`（`encode_numpy_image_to_api_file_part`）—— 参考图 PNG 编码；
- `logger`（插件日志系统）；
- `comfy.model_management`（中断）、`comfy.utils`（ProgressBar）、`comfy.comfy_types`、`comfy_api.input_impl`（VideoFromFile）、`folder_paths`（输出目录）[高]；
- `_DummyPromptServer` 本地桩 [高，名称]——疑为无 PromptServer（headless）环境下的导入兼容桩 [低]。

## 5. 错误处理与用户可见文案

| 消息（原文） | 触发场景 |
|---|---|
| `请输入 prompt` | prompt 为空 |
| `文生视频模式不接收图片；如需传图请选择自动` | T2V + 有图 |
| `首帧生视频模式必须且只能输入 1 张图片` | I2V 图数 ≠ 1 |
| `多图参考模式需要 1-9 张参考图` | R2V 无图 |
| `HappyHorse 多图参考最多支持 9 张图片，当前输入 N 张` | R2V 图数 > 9 |
| `不支持的模式: ` | mode 归一化失败 |
| `未配置有效的 API URL` / `请在 config.ini 中配置 API URL 或在节点中填写，例如 https://newapi.xxx.com` | api_url 缺失 |
| `请在 config.ini 中配置 API Key 或在节点中填写` | api_key 缺失 |
| `缺少图像依赖（numpy）: ` | numpy 导入失败 |
| `不支持的 IMAGE 维度: ` / `不支持的参考图维度: ` | 输入 tensor 维度异常 |
| `提交任务失败: ` / `接口未返回 task_id：` / `未提供有效的任务 ID` | 提交阶段 |
| `查询任务失败: ` / `查询任务暂时失败: HTTP N`（继续轮询） | 轮询阶段 |
| ` 返回的不是 JSON` / ` 返回 JSON 结构异常：` / `HTTP N` / `, Body: ` / `, Content-Type: ` / `<empty body>` | 响应解析（`_read_json_response_or_raise`） |
| `HappyHorse 任务轮询超时（N 秒）` | 超过 timeout_s |
| `视频生成失败: ` / `任务成功但未返回 video_url：` | 失败态/无视频 URL |
| `不支持的模式` 类之外另有 `不支持的…维度` 两处 | 同上 |

进度/成功日志：`Mode: ` / `Model: ` / `Resolution: ` / `Resolution name: ` / `Duration: ` / `Input images: N 张（multipart upload）` / `Size: ` / ` len=` / `Task ID: ` / `任务ID: ` / `任务状态: ` / `继续轮询` / `视频生成完成: ` / `开始下载视频到 ComfyUI/output ...` / `视频已保存: ` / `API Key: ` / `API URL: [已脱敏]` [高]。

## 6. 证据附录

**注册/常量**：`TE_image_pro_happyh_video`、`TEHappyHVideoNode`、`TE MAN HappyH Video`、`TE MAN/HappyHorse`、`NODE_CLASS_MAPPINGS`、`NODE_DISPLAY_NAME_MAPPINGS`、`FUNCTION`、`OUTPUT_NODE`、`happyhorse-video`、`_FIXED_MODEL_NAME`、`_FIXED_RESOLUTION_NAME`、`_RATIO_OPTIONS`、`_MODE_AUTO/_MODE_T2V/_MODE_I2V/_MODE_R2V`、`_MODE_TO_MODEL`、`_DEFAULT_BASE_URL`、`CONFIG_MANAGER`、`PLUGIN_DIR`、`MODULE_DIR`、`_HAS_COMFY_VIDEO`。

**模式/校验文案**：`自动：无图=文生视频`、`图=首帧生视频`、`多图=多图参考`、`文生视频模式不接收图片`、`如需传图请选择自动`、`首帧生视频模式必须且只能输入 1 张图片`、`多图参考模式需要 1-9 张参考图`、`HappyHorse 多图参考最多支持 9 张图片，当前输入 `、`首帧/参考图 1`、`参考图 2`…`参考图 9`、`多图参考模式可用 [Image 1]`、`[Image 2] `、`指代图片`。

**参数 tooltip**：`API 地址，例如 https://newapi.xxx.com 或完整的 /v1/videos 地址`、`API Key；留空则读取 config.ini`、`需要忽略系统代理/梯子时开启`、`任务最长等待时间（秒）`、`轮询间隔（秒），官方建议约 15 秒`、`视频时长（秒），范围 3-15`、`用于生成视频的提示词`、`会转换成 size`、`例如 16:9 -> 1280x720`、`仅供 ComfyUI 工作流使用`、`不会写入请求体`、`任务最长等待时间（秒）`。

**比例字面量**：`16:9`、`9:16`、`1:1`、`4:3`、`3:4`、`21:9`、`9:21`、`4:5`、`5:4`；分辨率 `720p`、`720P`、`1080p`、`1080`。

**网络/协议**：`POST /v1/videos`（docstring `- POST /v1/videos 提交任务`）、`- GET /v1/videos/{task_id} 轮询状态`、`/videos`、`/v1/videos/`、`multipart upload`、`input_reference[]`、`Authorization`、`Bearer `、`User-Agent`、`ComfyUI-TE_API/1.0`、`content-type`、`Session`、`trust_env`、`bypass_proxy`、`timeout`、`stream`、`iter_content`、`chunk_size`、`raise_for_status`、`urljoin`、`urlparse`、`scheme`、`netloc`、`http://`、`https://`、`://`、`data:`、`RequestsJSONDecodeError`、`requests.exceptions`。

**响应字段**：`taskId`、`taskStatus`、`status`、`data`、`output`、`results`、`videos`、`url`、`content_url`、`video_url`、`message`、`error`、`code`、`fail_msg`、`fail_reason`；终态 `SUCCEEDED/COMPLETED/SUCCESS/FAILED/FAILURE/ERROR/UNKNOWN`。

**输出**：`te_happyh_video_`、`.mp4`、`.png`、`mime_type`、`BytesIO`、`file_bytes`、`get_output_directory`、`makedirs`、`exist_ok`、`VideoFromFile`、`comfy_api.input_impl`、`VIDEO`、`encode_numpy_image_to_api_file_part`（image_codec）、`ProgressBar`（comfy.utils）。

**前端桥接（te_prompt_text.js）**：`'TE_image_pro_happyh_video':{'imageInputs':Array['from']({'length':0x9},…{'name':'image_'+(n+1),'label':'图片'+(n+1),'insertText':'图'+(n+1)})}`；`ensureH3ReferenceOutput(_0x…)&&…addOutput('H3参考素材','TE_H3_REFERENCES')`；`ensureH3ReferenceInput(…)&&…addInput('H3参考素材','TE_H3_REFERENCES')`（后者作用于 `TE_H3_Prompt_Enhancer`）。

**未确认清单（回填前）**：`_DEFAULT_BASE_URL` 具体值；`duration/poll_interval_s/timeout_s/mode/resolution` 默认值；ratio 参数名；`watermark` 是否为 UI 参数；`seed` 是否写入请求体；完整 `RETURN_NAMES`；`_HAS_COMFY_VIDEO=False` 回退；下载文件名时间戳格式；`_MODE_TO_MODEL` 各模式映射值（推测均为 `happyhorse-video`）；服务端解析 `图N` 还是 `[Image N]` 标记。
> → 其中大部分已在下方 §7 动态回填中关闭，剩余项见 §7.4。

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions 真实环境（`Windows-2025Server-10.0.26100`，Python 3.13.16，ComfyUI 目录 `D:\a\_temp\ComfyUI`，插件包 `custom_nodes/TE_MAN`）运行时 introspection 导出（`te_man_introspection.json`）。
> **包装层说明（重点）**：TE_HappyH_Video.pyd 的 `TEHappyHVideoNode` 是 pyd 基类；运行时 ComfyUI 实际注册的类是明文包装层 `Grok_Safe_PY.py` 中的 **`TE_MAN.Grok_Safe_PY.TEHappyHVideoSafePyNode`**（SafePy 类包装 pyd 基类）。`Grok_Safe_PY` 模块自身运行时 `NODE_CLASS_MAPPINGS` 为空 dict，最终注册映射为 `TE_image_pro_happyh_video → TEHappyHVideoSafePyNode`。下表即包装层最终暴露的参数表（SafePy 透传基类 INPUT_TYPES，无增减）。

### 7.1 节点注册（运行时实锤）

| 项 | 值 |
|---|---|
| 注册名 | `TE_image_pro_happyh_video` |
| 运行时类 | `TE_MAN.Grok_Safe_PY.TEHappyHVideoSafePyNode`（包装 pyd 基类 `custom_nodes.TE_image.TE_HappyH_Video.TEHappyHVideoNode`） |
| 显示名 | `TE MAN HappyH Video` |
| `FUNCTION` | `generate_video` |
| `CATEGORY` | `TE MAN/HappyHorse` |
| `OUTPUT_NODE` | `True` |
| 节点 doc | 无（`doc = null`，SafePy 包装类未透出基类 docstring） |

pyd 模块常量实锤（`TE_MAN.TE_HappyH_Video`，module file `TE_HappyH_Video.pyd`）：

```
NODE_CLASS_MAPPINGS        = {TE_image_pro_happyh_video: TEHappyHVideoNode}   # pyd 侧原始映射
NODE_DISPLAY_NAME_MAPPINGS = {TE_image_pro_happyh_video: TE MAN HappyH Video}
MODULE_DIR = PLUGIN_DIR    = D:\a\_temp\ComfyUI\custom_nodes\TE_MAN
_HAS_COMFY_VIDEO           = True
_DEFAULT_BASE_URL          = ""        # 空串，无硬编码默认 URL
_FIXED_MODEL_NAME          = "happyhorse-video"
_FIXED_RESOLUTION_NAME     = "720P"
_MODE_AUTO = "自动"   _MODE_T2V = "文生视频"   _MODE_I2V = "首帧生视频"   _MODE_R2V = "多图参考"
_MODE_TO_MODEL             = {"文生视频": "happyhorse-video",
                              "首帧生视频": "happyhorse-video",
                              "多图参考": "happyhorse-video"}
_RATIO_OPTIONS             = ["16:9","9:16","1:1","4:3","3:4","4:5","5:4","9:21","21:9"]
```

### 7.2 INPUT_TYPES 全表（运行时实锤，包装层最终暴露参数表）

**required：**

| 参数 | 类型 | 枚举/约束 | 默认值 | tooltip 摘要 |
|---|---|---|---|---|
| `prompt` | STRING | multiline，`defaultInput: true` | `一座由硬纸板和瓶盖搭建的微型城市，在夜晚焕发出生机。一列硬纸板火车缓缓驶过，小灯点缀其间，照亮前路。` | 用于生成视频的提示词。多图参考模式可用 [Image 1]、[Image 2] 指代图片。 |
| `api_key` | STRING | 单行 | `""` | API Key；留空则读取 config.ini |
| `api_base_url` | STRING | 单行 | `""`（空 = 走 config.ini） | API 地址，例如 https://newapi.xxx.com 或完整的 /v1/videos 地址 |
| `mode` | ["自动","文生视频","首帧生视频","多图参考"] | 下拉 | `自动` | 自动：无图=文生视频，1图=首帧生视频，多图=多图参考。 |
| `ratio` | ["16:9","9:16","1:1","4:3","3:4","4:5","5:4","9:21","21:9"] | 下拉（9 档） | `"16:9"` | 会转换成 size，例如 16:9 -> 1280x720 |
| `duration` | ["3","4","5","6","7","8","9","10","11","12","13","14","15"] | 下拉（13 档） | `"5"` | 视频时长（秒），范围 3-15 |

**optional：**

| 参数 | 类型 | 枚举/约束 | 默认值 | tooltip 摘要 |
|---|---|---|---|---|
| `seed` | INT | min -1 / max 2147483647，`control_after_generate` 开启 | `-1` | 仅供 ComfyUI 工作流使用；不会写入请求体 |
| `image_1` / `image_2` / `image_3` / `image_4` / `image_5` / `image_6` / `image_7` / `image_8` / `image_9` | IMAGE ×9 | — | — | 首帧/参考图 1；参考图 2 … 参考图 9 |
| `poll_interval_s` | INT | min 5 / max 60 | `15` | 轮询间隔（秒），官方建议约 15 秒 |
| `timeout_s` | INT | min 120 / max 3600 | `900` | 任务最长等待时间（秒） |
| `绕过代理` | BOOLEAN | — | `false` | 需要忽略系统代理/梯子时开启 |

**未暴露项修正**：`resolution` 不作为 UI 输入（`_FIXED_RESOLUTION_NAME="720P"` 内部固定，原"疑为 720p/1080p 两档下拉"关闭）；`watermark` 不是 UI 参数；`api_url`→实锤形参名 `api_base_url`；`bypass_proxy`→实锤 UI 名 `绕过代理`；`duration` 为 STRING 下拉而非 INT。

### 7.3 返回值（运行时实锤）

`RETURN_TYPES = [VIDEO, STRING, STRING, STRING]`，`RETURN_NAMES = ["video", "video_url", "task_id", "response"]`，`OUTPUT_NODE = True`。

### 7.4 回填后仍未确认项

- 下载文件名时间戳格式（`te_happyh_video_` 前缀之后的部分）——函数体不可见。
- `_HAS_COMFY_VIDEO=False` 时的回退返回形态——真机环境恒为 True，未触发。
- 服务端解析 `图N`（前端 chip 标记）还是 `[Image N]`（tooltip 文档标记）——属服务端行为，introspection 不可见；但 tooltip 实锤全文 `多图参考模式可用 [Image 1]、[Image 2] 指代图片` 支持 `[Image N]` 为 API 侧标记的推断。
