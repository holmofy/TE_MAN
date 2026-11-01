# Sora_2_Video_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_Sora_2_Video_Generator`。静态分析（strings / PE 导入导出表，字符串按文件内偏移定位）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

TE_MAN 插件的 **ComfyUI 视频生成节点模块**（会被 `__init__.py` 的加载器自动 import）。提供单个节点 `BananaSora2VideoNode`，通过第三方中转站的「OpenAI videos 风格」异步 API（提交 → task_id → 轮询 → 下载 video_url）生成 Sora 2 视频并下载到 `ComfyUI/output`。README 佐证（v-x 更新日志第 362 行）：「增加 sora2 节点，支持 sora2 生成视频」[高]。

原始编译路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Sora_2_Video_Generator.c`，限定名 `custom_nodes.TE_image.Sora_2_Video_Generator` [高]（同其他 pyd，旧包名 TE_image 残留）。

### 与 api_client 的协议层关系（重点）

**结论：本模块不 import api_client，自带独立的 HTTP 层（requests.Session），是 api_client「OpenAI videos 兼容协议」的平行实现。**

- 负证据 [高]：整个二进制中 `api_client` / `GeminiApiClient` 出现次数为 **0**（strings 全量核对）。模块自身 import 的 Python 包（字符串证据）：`requests`、`config_manager`、`image_codec`、`comfy`、`comfy.comfy_types`、`comfy_api.input_impl`、`comfy.model_management`、`folder_paths`、`urllib.parse`（`urljoin`）、`base64`、`numpy`、`json`、`time`、`typing`、`sys` [高]。
- 协议共性 [高]：与 api_client.md §3.4/§4 记录的视频协议完全同族——提交 `POST {base}/v1/videos`（共同字符串 `/v1/videos`）+ 轮询任务状态 + Bearer 认证 + 状态字面量集合高度重合（`completed / succeeded / ready / finished / failed / cancelled / canceled / expired / progress`，api_client 侧为 `SUCCESS / FAILURE / failed / completed / progress`）。
- 协议差异 [高]：
  - User-Agent 不同：本模块 `ComfyUI-TE_MAN/1.0`，api_client 为 `ComfyUI-TE_API/1.0`。
  - api_client 用后台线程 + `_interruptible_post` 实现中断响应；本模块无 `_interruptible_*` 符号，改为**每轮询循环调用 `_ensure_not_interrupted`**（配合 `comfy.model_management` 的 `throw_exception_if_processing_interrupted`）[中]。
  - api_client 有 SSE 流式 / 重试退避 / 连接预算设施；本模块无 `Connection: close 重试`、`alt=sse` 等符号——单次调用 + 轮询 [高（负证据）]。
  - api_client 内置轮询字段候选 `/v1/videos/ +task_id` 与本模块轮询端点一致 [中]。

即：**Sora 节点走同一套中转站协议族（`/v1/videos` 异步任务），但协议层代码独立复制了一份，不复用 api_client**；推测上游同一批生成器源码经裁剪而成（同目录 `source_py_backup`）[低]。

## 2. Python API

- 导出：`PyInit_Sora_2_Video_Generator`（唯一导出符号）[高]；PE 导入依赖仅 python3.dll / KERNEL32 / VCRUNTIME140 / CRT——无 WS2_32，网络全部经 Python 层 [高]。
- 模块级函数（qualname 字符串证据，顺序按二进制符号表 [高]）[中]（形参名来自局部变量名与字符串邻接推断）：
  - `_ensure_not_interrupted()` — 轮询中途检查 ComfyUI 中断
  - `_resolve_videos_url(api_base_url)` — 归一化并拼出提交端点（局部名 `api_base_url / resolved_url`，内部用 `urljoin`、后缀 `/videos`、`/v1/videos`）[高/中]
  - `_resolve_key_and_url(api_key, api_url)` — 解析最终 Key + URL（局部名 `api_key / api_url / resolved_key / masked_key / enable`；空值回退 config_manager）[中]
  - `_extract_task_id(response_json)` — 从创建响应提取 `task_id`（局部名 `response_json / task_id`，另有 `id`）[高/中]
  - `_extract_task_status(response_json)` — 提取 `status`（局部名还有 `state / code`）[高/中]
  - `_extract_video_url(response_json)` — 提取 `video_url / url / video_id` 等 [高/中]
  - `_extract_error_message(response_json)` — 提取 `error / message` [高/中]
  - `_encode_image_to_data_url(image_tensor)` — 图生视频参考图 → data URL（委托 `image_codec.encode_numpy_image_to_api_data_url`，检查 `ndim / shape`，依赖 numpy）[高]
  - `_get_output_dir()` — `folder_paths.get_output_directory` + `abspath/isdir/makedirs/exist_ok` [高]
  - `_download_video(video_url, headers, timeout_s, ...)` — 流式下载（`stream / iter_content / chunk_size / open / splitext / .mp4 / sora2_video_` 文件名前缀）[高]
  - `_poll_task_until_completed(status_url, headers, timeout_s, poll_interval_s, ...)` — 轮询循环（`time.sleep`、`session.get`）[高/中]
- 类 `BananaSora2VideoNode`（ComfyUI 节点），方法 `INPUT_TYPES`（classmethod 痕迹）与 `generate_video`（FUNCTION 指向）[高]。
- 模块常量：`_DEFAULT_MODEL`（值 `sora-2` [高/中]）、`_HAS_COMFY_VIDEO`（探测 comfy 视频类型可用性）、`CONFIG_MANAGER` / `ConfigManager`（Singleton，构造参数证据 `MODULE_DIR`）、默认提示词字面量 `"A cinematic orange cat walking slowly through a rainy neon street at night."` [高]（用作 prompt 默认值或示例 [低]）。
- `OUTPUT_NODE`、`RETURN_TYPES`、`RETURN_NAMES`、`CATEGORY`、`INPUT_TYPES`、`tooltip` 等 ComfyUI 属性字符串齐全 [高]。
- Cython `__test__` doctest 支持串 [高]，具体 doctest 内容 未确认。

### ComfyUI 节点注册 [高]

| 键（推断） | 值 | 证据 |
|---|---|---|
| `NODE_CLASS_MAPPINGS` 键 | `BananaSora2VideoNode` | 字符串 `NODE_CLASS_MAPPINGS` + 类名 |
| `NODE_CLASS_MAPPINGS` 值（键名） | `TE_image_pro_sora2_video` | 字符串（旧 `TE_image` 系命名残留，参考同类节点键名风格）[中] |
| `NODE_DISPLAY_NAME_MAPPINGS` 显示名 | `TE MAN sora2 video` | 字符串 [高，键值绑定 未确认] |
| `CATEGORY` | `TE MAN/Sora` | 字符串 |
| `FUNCTION` | `generate_video` | 字符串 |

## 3. 节点规格（BananaSora2VideoNode）

### 3.1 输入参数

参数名与类型标记均来自字符串证据；分组（required/optional 顺序）与默认值多为推断，单数、轮询参数具体 数值 未确认。

| 参数 | 类型/选项 | 证据 | 推断 |
|---|---|---|---|
| `prompt` | STRING（`multiline`） | 「用于生成视频的提示词」tooltip、「请输入 prompt」校验、`prompt_text` 局部名 | 必填 [中]；空值报「请输入 prompt」[中]；默认值可能为内置猫片示例句 [低] |
| `model` | STRING | 「模型名称，默认 sora-2」tooltip；`_DEFAULT_MODEL`=`sora-2`；`effective_model` 局部名 | 默认 `sora-2`；无其他模型字面量（如 sora-2-pro 不存在）[高] |
| `aspect_ratio` | STRING 选项集 | 二进制字面量仅 `16:9`、`9:16` 两个比例串 | 选项 likely `[16:9, 9:16]`，顺序未确认；其他选项（如 1:1）不存在 [高（负证据）] |
| `resolution` | STRING 选项集 | 二进制字面量仅 `720p`（`/v1/videos` 紧邻处） | `720p` 为可选值（likely 默认）；完整选项列表 未确认（未发现 1080p/480p/auto）[中] |
| `seconds` | INT 或 STRING | 「视频时长（秒）」tooltip；`seconds_value` 局部名；独立字符串 `"12"` 存在 | 时长选项可能含 `12`（Sora 系 4/8/12 档，仅 `"12"` 字面量存在）[低]；类型/默认 未确认 |
| `seed` | INT + `control_after_generate` | 0x19f40 处 `prompt, model, aspect_ratio, resolution, seconds, seed` 参数名序列 [高]；字符串 `control_after_generate`；tooltip「仅供 ComfyUI 工作流使用；不会写入请求体」 | ComfyUI 种子，不进请求体 [高（tooltip 原文）] |
| `image`（IMAGE） | IMAGE（optional） | 「参考图片（可选），接入后走图生视频，写入 image_url」tooltip；局部 `image_tensor / has_image / image_url`；请求体含 `image_url` 字段 [高] | 图生视频，编码为 data URL 写入 `image_url`；不传时走文生视频 [高] |
| `api_key` | STRING | 「API Key；留空则读取 config.ini」tooltip；`_resolve_key_and_url` 回退 `config_manager.load_api_key` | 留空读 config.ini `[gemini] api_key` [高] |
| `api_url` | STRING | 「服务地址，如 https://socdabat.it.com（不要带 /v1/videos）」tooltip；回退 `config_manager.get_effective_api_base_url` [中] | 中转站 base URL；节点自行拼接 `/v1/videos` [高] |
| `timeout_s`（名 未确认，candidates：`timeout_s / timeout`） | INT 或 FLOAT | 「总超时（秒），包含创建任务」tooltip；`timeout_s` 局部名贯穿下载/轮询 | 总超时，覆盖创建+轮询+下载 [高（语义）/名 [中]] |
| `poll_interval_s`（名 未确认） | 数字 | 字符串 `poll_interval_s`（两处） | 轮询间隔秒，默认值 未确认 |
| `bypass_proxy` | BOOLEAN | 「需要忽略系统代理/梯子时开启」tooltip；局部 `bypass_proxy / trust_env / enable / session` | bypass_proxy=True 时 requests.Session `trust_env=False`（绕过系统代理）[中] |

INPUT_TYPES 结构字面量佐证：`required / optional / default / tooltip / multiline` 字符串齐全 [高]。

### 3.2 输出

- `RETURN_TYPES` [中]：运行时二选一——检测 `_HAS_COMFY_VIDEO`（探测 `comfy.comfy_types` / `comfy_api.input_impl` 与 `VideoFromFile`）：可用时返回 ComfyUI 视频对象（`VIDEO` 类型，`VideoFromFile` 包装本地文件）；不可用时回退字符串路径（存在 `STRING` 字面量与 `video_path` 局部名）。具体回退形态 未确认。
- `RETURN_NAMES`：候选 `video / video_path / video_url`（均有字符串），绑定关系 未确认。
- `OUTPUT_NODE = True` [中]（字面量存在；节点会下载并保存文件，符合 OUTPUT_NODE 语义）。

### 3.3 关键行为流程（generate_video）

1. **校验**：prompt 为空 →「请输入 prompt」[中]；参考图多于 1 张 → 告警「参考图输入 N 张，当前接口只使用第 1 张」并只取第 0 张 [高]；日志「参考图: 1 张」[高]。
2. **图生视频编码**：`_encode_image_to_data_url` → `image_codec.encode_numpy_image_to_api_data_url`；numpy 缺失报「缺少图像依赖（numpy）: 」；维度非法报「不支持的 IMAGE 维度: 」+ `ndim` [高]。
3. **解析 Key/URL**：`_resolve_key_and_url`——节点值优先，为空回退 config.ini（`请在 config.ini 中配置 API Key/URL 或在节点中填写`）；无有效 URL →「未配置有效的 API URL」[高]。日志输出脱敏值：`API URL: [已脱敏]`、`API Key: <masked_key>`、`Model: <model>` [高]。
4. **拼端点**：`_resolve_videos_url` 用 `urljoin` 把 base 归一化到 `/v1/videos`（若 base 已带 `/videos`/`/v1/videos` 走另一种拼法，逻辑细节 未确认）[高：`/videos`、`/v1/videos`、`urljoin` 字符串；tooltip 明示"不要带 /v1/videos"]。
5. **提交任务**：POST JSON（`json.dumps / ensure_ascii`、`Content-Type: application/json`），请求体字段（来自字符串与 tooltip）[中]：`model / prompt（prompt_text）/ seconds（seconds_value）/ aspect_ratio / resolution / image_url`（`seed` 明确不写入 seed）。响应取 `task_id`（兜底 `id`）；缺失 →「创建任务成功，但未返回 task_id」并附「响应片段: 」[高]。成功日志「任务ID: 」[高]。
6. **轮询**：`_poll_task_until_completed` → GET `status_url`（应为 `{提交端点}/{task_id}`，含 `video_id` 局部名，未确认拼法 [中]）。每轮：`_ensure_not_interrupted()`（ComfyUI 中断即抛出，`throw_exception_if_processing_interrupted`）[高]；打印「任务状态: <status> | 进度: <progress>」[高]。状态字面量 [高]：终态成功 `completed / succeeded / ready / finished`；失败 `failed / cancelled / canceled / expired / error`；进行中 `progress / pending?（未确认）`；异常兜底 `unknown / state / code`。成功而缺 URL →「任务已完成，但未返回 video_url」[高]。HTTP 异常 →「查询任务失败: 」「: HTTP <code>」。超预算 →「视频任务轮询超时（<timeout_s> s）」[高]。
7. **失败转换**：任务失败 →「视频任务失败: </message>」（消息来自 `_extract_error_message` 的 `error/message` 字段）；另有语串「上游任务失败」[高，触发点 未确认]。
8. **下载**：`_download_video` 流式拉取最终 `video_url`（`User-Agent: ComfyUI-TE_MAN/1.0`、`Accept-Encoding: identity` [中]），文件名 `sora2_video_` + 时间戳 + 从 URL `splitext` 的扩展（缺省 `.mp4`），保存到 `folder_paths.get_output_directory()`（`makedirs exist_ok`）；日志「开始下载视频到 ComfyUI/output ...」「视频已保存: <path>」「Video: <url/path>」「下载视频失败: 」[高]。
9. **进度推送**：存在 `PromptServer / _DummyPromptServer / progress / server` 字符串[中]——与 `comfy.model_management` 的中断检查同源模式（仓库内 7 个视频/图像 pyd 均含 `_DummyPromptServer`），推断为"提示服务器不可用时的空桩 + 轮询进度转发"，具体机制 未确认。

## 4. 外部依赖与副作用

### 网络端点 [高/中]

| 端点 | 方法/用途 | 证据 |
|---|---|---|
| `POST {base}/v1/videos` | 创建 Sora 视频任务 | `/v1/videos`、`/videos`、`urljoin`、`post`、tooltip「（不要带 /v1/videos）」[高] |
| `GET {base}/v1/videos/{task_id}`（拼法 未确认） | 轮询任务状态 | `status_url`、`get`、`task_id`、`video_id`、与 api_client `/v1/videos/ +id` 同构 [中] |
| `GET {video_url}`（第三方/ 中转站直链） | 下载 mp4 | `_download_video`、`.mp4`、`iter_content` [高] |

- 示例中转站域名字符串：`https://socdabat.it.com`（tooltip 示例值，非硬编码默认）[高]。
- 请求头 [高]：`Authorization: Bearer <key>`、`Content-Type: application/json`、`User-Agent: ComfyUI-TE_MAN/1.0`、`Accept-Encoding`（配合 `identity` 局部名，可能强制 `Accept-Encoding: identity` [中]）。
- 认证/脱敏 [高]：`masked_key`、`sanitize_api_key`（config_manager）、日志 `API Key: ` 与 `API URL: [已脱敏]`。
- 代理 [中]：`bypass_proxy` → `requests.Session` + `trust_env=False`；字面量「系统代理鉴权」「系统代理无鉴权」存在，含义 未确认（疑为代理探测/日志态）。
- SSL/proxies/verify 相关字符串缺失，`verify_ssl` 设置 未确认（疑默认 requests 默认）。

### 文件系统与配置 [高]

- 写：`ComfyUI/output`（`folder_paths.get_output_directory`），文件 `sora2_video_*.mp4`（前缀字符串 `sora2_video_`）。
- 读：`config.ini`（本包目录，同 config_manager 全局 `[gemini]` 段：`api_key`、`api_base_url`；tooltip「留空则读取 config.ini」直证）；经 `CONFIG_MANAGER`（`ConfigManager(MODULE_DIR)`）单例。
- 不写注册表、无内存注入迹象 [高]（PE 导入表无 WS2_32/ADVAPI32）。

### Python 库依赖 [高]

`requests`（Session/get/post/stream/iter_content）、`urllib.parse`（urljoin）、`base64`、`json`（dumps/ensure_ascii）、`numpy`（可选，缺失有专门提示）、`image_codec`（`encode_numpy_image_to_api_data_url`）、`config_manager`、`folder_paths`、`comfy.model_management`（中断检查）、`comfy.comfy_types` / `comfy_api.input_impl`（视频类型探测）、`typing`（Optional/Any/List/Dict/Tuple）、`time`、`sys`、`logger`（本包）。

## 5. 错误处理与用户可见文案（全部 中文串原文摘录）

| 消息 | 触发场景（推断） |
|---|---|
| `请输入 prompt` | prompt 为空 |
| `参考图输入 {N} 张，当前接口只使用第 1 张` | 多图输入告警（f-string） |
| `参考图: 1 张` | 单图输入信息日志 |
| `不支持的 IMAGE 维度: {ndim}` | image_tensor 维度非法 |
| `缺少图像依赖（numpy）: {e}` | numpy Import 失败 |
| `未配置有效的 API Key`/`请在 config.ini 中配置 API Key 或在节点中填写` | key 解析失败 |
| `未配置有效的 API URL`/`请在 config.ini 中配置 API URL 或在节点中填写` | URL 解析失败 |
| `API URL: [已脱敏]` / `API Key: {masked}` / `Model: {model}` | 请求前调试日志 |
| `API 调用失败: {e}`（含 `: HTTP {code}`） | 创建任务异常 |
| `查询任务失败: {e}` | 轮询请求异常 |
| `创建任务成功，但未返回 task_id` / `响应片段: {snippet}` | 提交响应无 id |
| `返回内容为空` | 响应空 |
| `任务ID: {id}` | 创建成功日志 |
| `任务状态: {status} \| 进度: {progress}` | 轮询进度日志 |
| `视频任务失败: {msg}` | 任务终态失败 |
| `上游任务失败` | 失败归类消息（上下文 未确认） |
| `视频任务轮询超时（{timeout_s} s）` | 轮询超总时 |
| `任务已完成，但未返回 video_url` | 成功终态缺 URL |
| `开始下载视频到 ComfyUI/output ...` / `视频已保存: {path}` / `Video: {video}` / `下载视频失败: {e}` | 下载阶段 |
| `系统代理鉴权` / `系统代理无鉴权` | 代理相关日志，含义 未确认 |
| `Sora2 视频生成任务` | （docstring/描述） |

## 6. 证据附录

### 模块身份（原文）
```
PyInit_Sora_2_Video_Generator
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Sora_2_Video_Generator.c
custom_nodes/TE_image/source_py_backup/Sora_2_Video_Generator.py
custom_nodes.TE_image.Sora_2_Video_Generator
```

### 函数/类符号（qualname 序列）
```
_ensure_not_interrupted   _resolve_videos_url   _resolve_key_and_url
_extract_task_id          _extract_task_status  _extract_video_url
_extract_error_message    _encode_image_to_data_url   _get_output_dir
_download_video           _poll_task_until_completed
BananaSora2VideoNode.INPUT_TYPES   BananaSora2VideoNode.generate_video
_generate_视频流程局部名: api_base_url api_key api_url response_json endpoint status_url
video_url timeout_s headers prompt_text seconds_value effective_model resolved_key
masked_key image_url has_image image_tensor image_count final_data payload create_data
```

### 端点/URL/请求头
```
/videos   /v1/videos   urljoin   status_url   resolved_url   endpoint
https://socdabat.it.com     (tooltip 示例)
Authorization   Bearer    Content-Type   application/json
User-Agent   ComfyUI-TE_MAN/1.0   Accept-Encoding   identity
API URL: [已脱敏]   API Key:    masked_key   sanitize_api_key
```

### ComfyUI 注册/属性
```
NODE_CLASS_MAPPINGS   NODE_DISPLAY_NAME_MAPPINGS   TE_image_pro_sora2_video
BananaSora2VideoNode   TE MAN sora2 video   TE MAN/Sora   FUNCTION   generate_video
OUTPUT_NODE   RETURN_TYPES   RETURN_NAMES   CATEGORY   tooltip   required   optional
multiline   default   control_after_generate
comfy.comfy_types   comfy_api.input_impl   VideoFromFile   VIDEO   _HAS_COMFY_VIDEO
```

### 输入参数（参数名序列 @0x19efc 起）
```
prompt  model  aspect_ratio  resolution  seconds  seed   [(INPUT_TYPES 形参序)]
IMAGE   BOOLEAN   STRING   INT   poll_interval_s   bypass_proxy   trust_env
```
字面量选项：`16:9` / `9:16`（比例）、`720p`（分辨率）、`"12"`（时长相关，语义未确认）；未发现 `1:1 / 1080p / auto / portrait / landscape / sora-2-pro`。

### 协议字段/状态字面量
```
model   prompt   seconds   aspect_ratio   resolution   image_url   id   task_id
status   state   code   error   message   url   video_url   video_id   progress
completed   succeeded   ready   finished   failed   cancelled   canceled   expired   unknown   progress
```

### 下载/输出
```
stream   iter_content   chunk_size   splitext   .mp4   sora2_video_   makedirs
exist_ok   abspath   isdir   exists   dirname   folder_paths   get_output_directory
ComfyUI/output   open
```

### 中断/进度
```
comfy.model_management   throw_exception_if_processing_interrupted
_ensure_not_interrupted   PromptServer   _DummyPromptServer   progress   server
```

### 日志与中文消息（原文）
```
请输入 prompt
参考图片（可选），接入后走图生视频，写入 image_url
参考图输入 ; 张，当前接口只使用第 1 张 ; 参考图: 1 张
模型名称，默认 sora-2 ; 视频时长（秒） ; 用于生成视频的提示词
总超时（秒），包含创建任务 ; 仅供 ComfyUI 工作流使用；不会写入请求体
服务地址，如 https://socdabat.it.com（不要带 /v1/videos）
API Key；留空则读取 config.ini ; 需要忽略系统代理/梯子时开启
API URL: [已脱敏]   未配置有效的 API URL   API URL   API Key   config.ini
缺少图像依赖（numpy）:    不支持的 IMAGE 维度:
创建任务成功，但未返回 task_id   响应片段:    任务ID:    返回内容为空
任务状态:   | 进度:    查询任务失败:    API 调用失败:    (: HTTP)
视频任务失败:    上游任务失败    视频任务轮询超时（    任务已完成，但未返回 video_url
开始下载视频到 ComfyUI/output ...   视频已保存:    Video:    下载视频失败:
系统代理鉴权   系统代理无鉴权   Sora2 视频生成任务
```

### 默认值常量
```
_DEFAULT_MODEL = sora-2   (effective_model)
默认示例 prompt: A cinematic orange cat walking slowly through a rainy neon street at night.
```
