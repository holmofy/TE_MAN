# Grok_Image_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_Grok_Image_Generator`。静态分析（字符串 / 导入导出表 / 分段上下文十六进制转储）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

TE_MAN 插件的 **Grok（xAI grok2api 系）图像生成 ComfyUI 节点**：文生图 + 图生图（最多 3 路参考图输入），
通过 OpenAI 风格的 `/v1/chat/completions`（`image_config` 参数）与 `/v1/images/{generations,edits}`、
`/v1/files/image/` 端点工作，内部用 `task_runner.BatchGenerationRunner` 做多请求并发。
原始源码路径（Cython 编译期嵌入）：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Grok_Image_Generator.py`，
模块限定名 `custom_nodes.TE_image.Grok_Image_Generator`（曾名为 TE_image 包）[高]。

运行时注册链（与明文参照源码 `Grok_Safe_PY.py` / `zzzz_grok_autoscale_patch.py` 互证）[高]：
`__init__.py` 按字母序加载模块（Grok_Image_Generator → Grok_Safe_PY → zzzz_grok_autoscale_patch），
`zzzz_grok_autoscale_patch.py:19` 以同一注册名 `TE_image_pro_grok_image` 用安全包装类
`BananaGrokImageSafePyNode`（继承本 pyd 的 `BananaGrokImageNode`，`Grok_Safe_PY.py:10`）**覆盖**注册，
因此实际执行的是包装类 → 本 pyd 基类；包装层仅在调用 `super().generate_images(...)` 前做输入图缩放与参数透传。

## 2. Python API

- 导出：`PyInit_Grok_Image_Generator`（PE 导出表唯一导出符号）[高]。
- 模块级公开对象（qualname 字符串直接证据）[高]：
  - **`class BananaGrokImageNode`**（被 `Grok_Safe_PY.py:10` 以此名 import，交叉确认）
  - 模块级函数：`_ensure_not_interrupted`、`_resolve_chat_completions_url(api_base_url, ...)`、`_resolve_images_generations_url`、`_resolve_images_edits_url`、`_pick_image_value`、`_looks_like_base64_blob`、`_extract_image_refs_from_text`、`_extract_first_image_ref_from_chat_response`、`_absolutize_url(raw_url, endpoint, ...)`、`_download_image_bytes(api_key, timeout_s, ...)`、`_is_valid_image_bytes`、`_normalize_downloaded_image_bytes`、`_normalize_base64_image`、`_decode_valid_base64_image_bytes`、`_decode_nested_payload_from_bytes`、`_extract_stream_text_fragments`、`_normalize_image_items_from_response`、`_push_unique_image_items`、`_collect_image_items_from_event_stream`、`_collect_image_items_from_response`、`_scale_image_tensor_to_total_pixels_if_needed`
  - 模块级正则常量：`_URL_RE`、`_MD_IMAGE_RE`、`_IMAGE_EXT_RE`、`_BASE64_BLOB_RE`、`_DATA_URI_PREFIX`；下载缓存 `_IMAGE_DOWNLOAD_CACHE` / `_IMAGE_DOWNLOAD_CACHE_MAX`；快捷功能常量 `QUICK_FUNCTION_NONE` / `QUICK_FUNCTION_OPTIONS` / `QUICK_FUNCTION_PREFIXES`；全局限幅常量 `_MAX_INPUT_IMAGE_MEGAPIXELS` / `_OFFICIAL_SCALE_METHOD` [高]
- 模块 docstring（原文）[高]：
  > `ComfyUI 节点：Grok /v1/chat/completions 图像生成` / `使用 chat.completions + image_config 传递图片生成参数：` / `- 文生图：model = grok-imagine-image` / `- 图生图：model = grok-imagine-image-edit` / `- 尺寸与张数通过 image_config 控制`
  另：`grok2api typically returns markdown like: ![id](/v1/files/image/xxx) or ![id](https://...)`（说明服务端为 grok2api 反代）[高]。
- **ComfyUI 节点注册** [高]：`NODE_CLASS_MAPPINGS["TE_image_pro_grok_image"]` → `NODE_DISPLAY_NAME_MAPPINGS["TE_image_pro_grok_image"] = "TE MAN Grok Image"`；`CATEGORY = "TE MAN/Grok"`；`FUNCTION = "generate_images"`；`OUTPUT_NODE` 字符串存在（是否置 True 未确认）。与 `zzzz_grok_autoscale_patch.py:19,35` 与 `save_image_with_output_core` 规格中提及的注册名一致。

## 3. 节点规格：`TE_image_pro_grok_image`（显示名 "TE MAN Grok Image"）

### 3.1 输入参数（`INPUT_TYPES`）

参数名与 tooltip 均为文件内原文字符串 [高]；类型与默认值依据 `Grok_Safe_PY.py:326-341` 包装层签名（其 `super().generate_images(**kwargs)` 即本 pyd 的形参契约）[高]：

| 参数 | 推断类型 / 默认值 | 依据 |
|---|---|---|
| `prompt` | STRING，默认 `"生成一张可爱的小猫图片"`，tooltip `用于生成图片的提示词` [高]；包装层强制 `defaultInput: True`（提示词可切换为连线输入）[高，`Grok_Safe_PY.py:317`] | 空时报错 `请输入 prompt` |
| `快捷功能` | STRING 选项（`QUICK_FUNCTION_OPTIONS`），默认 `"无"`（包装层签名 `快捷功能: str = "无"` + `QUICK_FUNCTION_NONE` 常量）[中]；tooltip `使用快捷功能生成` [高] | 见 3.4 |
| `api_key` | STRING，默认 `""`；tooltip：`API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）` [高] | 3.2 |
| `api_base_url` | STRING，默认 `""`；tooltip：`服务地址，如 http://localhost:8000（不要带 /v1/chat/completions）` [高] | 3.2 |
| `image_count` | INT，默认 1（包装层签名）；tooltip：`目标图片张数，对应 image_config.n` [高] | — |
| `size` | STRING 选项，默认 `"1024x1024"`；tooltip：`图片尺寸，对应 image_config.size` [高] | 响应中出现的尺寸值：`1024x1024`、`1024x1792`、`1280x720`、`1792x1024`、`720x1280`（共 5 个 [高]；选项顺序未确认） |
| `seed` | INT（`control_after_generate` 字符串在）[中]；tooltip：`仅供 ComfyUI 工作流使用；不会写入请求体` [高] | 不参与请求体 |
| `image` | IMAGE（optional），tooltip：`参考/编辑输入图片（可选）` + `填写时会以多模态 messages 方式发给 /v1/chat/completions` [高] | — |
| `image_2` | IMAGE（optional），tooltip：`第二路参考/编辑输入图片（可选）` [高] | — |
| `image_3` | IMAGE（optional），tooltip：`第三路参考/编辑输入图片（可选）` [高] | — |
| `timeout_s` | INT，默认 180（包装层签名 `timeout_s: int = 180`）[高]；tooltip：`请求超时（秒）` [高] | — |
| `绕过代理` | BOOLEAN，默认 False；tooltip：`需要忽略系统代理/梯子时开启` [高] | 对应内部串 `bypass_proxy` / `trust_env` |
| `图生图image_url格式测试` | STRING 选项，默认 `"对象格式"`（包装层签名默认值 [高]）；retry 格式测试开关，控制图生图多模态 content 里 image 的封装形态；**其余可选值 未确认**（二进制中唯一含"格式"的选项值即 `对象格式`） | 见 3.5 |

（`INPUT_TYPES` 中另含 `required / optional / choices / tooltip / defaultInput / control_after_generate` 结构键 [高]。）

### 3.2 密钥与 URL 解析（`_resolve_key_and_url`）

返回 `Tuple[str, str]`（类型注解字符串在）[高]，推断流程 [中]：

1. API Key：节点 `api_key` → `sanitize_api_key` 规整；否则 `ConfigManager(api_key config).load_api_key()`（tooltip 明言回退 `config.ini 的 gemini.api_key`）[高]；两者皆无 → 警告 `请在 config.ini 中配置 API Key 或在节点中填写`。
2. API URL：节点 `api_base_url` → `ConfigManager.get_effective_api_base_url()`；皆无 → `请在 config.ini 中配置 API URL 或在节点中填写` / 报 `未配置有效的 API URL` [高]。
3. 日志脱敏：`API URL: [已脱敏]`、`API Key: `（配 `masked_key` 遮蔽串 `"..."`，全量串 `"'"<>\)` 为剔除字符集的一部分）[中]。

URL 端点归一（独立函数族，均含 genexpr/局部名）[高]：`_resolve_chat_completions_url` → `/v1/chat/completions`；`_resolve_images_generations_url` → `/v1/images/generations`；`_resolve_images_edits_url` → `/v1/images/edits`。辅助串 `:/​/`、`http://`、`https://`、`/v1`、`/chat/completions`、`/images/generations`、`/images/edits`、`urljoin`/`urlparse`/`scheme`/`netloc` —— 兼容已带路径的 base 或直接填端点的写法（分支顺序未确认）。

### 3.3 执行流程与并发（`generate_images`）

- 入口方法 `FUNCTION = generate_images`；关键局部名 [高]：`final_prompt_text`、`input_data_urls`、`payload_variants`、`request_variant`、`quick_function_value`、`quick_prefix`、`image_mode`、`success_items`、`decoded_items`、`picked_items`、`picked_tensors`、`success_info`、`total_generated_images`、`completed_count`、`all_errors`、`normalized_size` —— 具体赋值逻辑未确认。
- **快捷功能前缀拼接**：`QUICK_FUNCTION_PREFIXES` 将选项值映射为追加/前置的中文模板（`final_prompt_text`），模板原文见附录 6.5 [高]；逐任务筛选 `task_index` [中]。
- **多任务并发（task_runner 协作）** [高]：字符串 `BatchGenerationRunner`、`task_runner`、`worker_fn`、`task_index`、`continue_on_error`、`batch_size`、`ProgressBar` 同时在本文件 .rdata；生成 `n × payload_variants` 的任务列表交给 `task_runner.BatchGenerationRunner.run(...)`（含 `continue_on_error`，推测为 True 以便统计 `Errors:`）并发执行（`_worker` 闭包内 `_call_generate_once` / `_call_edit_once`）。并发度如何取值 未确认（本文件无 `load_max_workers` / `cpu_count` 字符串）。
- **ComfyUI 中断透传** [高]：`_ensure_not_interrupted` + `throw_exception_if_processing_interrupted`（即 `comfy.model_management.throw_exception_if_processing_interrupted`）——任务间隙检查中断；`_progress_callback` 配 `comfy.utils.ProgressBar`，进度条标签 `"🖼️ Grok 图片生成任务"`（字节实测 `F0 9F 96 BC EF B8 8F`）[高]。
- 便捷日志分片 [高]：`Requests: 1 次`、`... 请求 ... 张图像（请求 ...`、`... 完成，返回 ... 张）`、`... 成功生成 ... 张可用图像`、`上游仅返回 ...`、`Input Images: `、`Requested Images: `、`Model: `、`Size: `、`Mode: `、`Quick Function: `、`API URL: [已脱敏]`、`Grok 图片生成任务`。
- **聚合与返回**：装配 `picked_tensors`（BASE64 → `image_codec.base64_to_tensor_single`）与下载 URL → tensor 的列表；失败任务经 `continue_on_error` 收集为 `Errors:`（日志原文字符串 `Errors:`）并可能仅通过 `torch.from_numpy`/`unsqueeze` 拼接 tensor。`RETURN_TYPES` / `RETURN_NAMES` 的具体 tuple 内容 **未确认**（仅键名字符串在；`IMAGE`/`images`/`STRING` 均在池中，推断输出为 `("IMAGE", ...)` [低]）。`build_preview_tuple`（image_codec 提供的实时预览）字符串在本文件，推断有 `preview_tensor` 展示路径 [中]。

### 3.4 文生图路径（`_call_generate_once`）

- 主路径：`POST /v1/chat/completions`，payload 含 `model`（`grok-imagine-image`）[高]、`messages`（role/content `open`/`user` 局部名）[中]、`image_config`（size/n，docstring 明言）[高]、可选 `stream: true`（`stream` / `decode_unicode` / `iter_content` / `chunk_size` 局部名）[中]。
- `payload_variants`：一次调用准备多个 payload 变体，失败后换下一 `request_variant` 重试，`all_errors` 汇总 [中]（变体具体差异 未确认）。
- SSE 解析：`text/event-stream`、按 блок `data: ` 切分、`consume_event_block`、JSON 对象递归遍历（regex 片段 `(?:content|text|delta|message|output)` 抓文本字段，`(?:^|_)(?:b64|base64)(?:_|$)` 抓 base64 字段键名）、终止 `data: [DONE]` [高]。
- 响应裁剪：`response_format: b64_json`（`b64_json` 局部名，OpenAI images API 风格）[中]；markdown 图引用提取：`_MD_IMAGE_RE = !\[[^\]]*\]\(([^)]+)\)`，`_URL_RE = https?://[^\s"'<>\\)]+`，`_IMAGE_EXT_RE = \.(png|jpg|jpeg|webp|gif|bmp)(\?|#|$)`、`_looks_like_base64_blob = ^[A-Za-z0-9+/=\r\n]+$`、data URI 前缀 `_DATA_URI_PREFIX = data:image`、`utf-8-sig` / `gb18030` 解码兜底 [高]。（响应 JSON 既可来自 `data.ai_message`、`content`、`text`、`data` 等，具体形态 未确认。）
- 备用路径：`/v1/images/generations`（`/images/generations` 字符串与 `_resolve_images_generations_url` 函数族在）[高] —— 变体或失败回退顺序 未确认。
- 取回结果处理：`_extract_first_image_ref_from_chat_response` → 相对地址 `_absolutize_url`（`/v1/files/image/...`，佐证串 `grok2api` 的 markdown 输出）→ `_download_image_bytes`。

### 3.5 图生图路径（`_call_edit_once` / `_build_edit_content`）

- 输入图编码：`_encode_image_tensor_to_png_files`，注释原文 [高]：
  > `Convert ComfyUI IMAGE tensor (BHWC, float[0..1]) into requests `files` list for multipart upload.` / `Returns up to 16 images for the `/v1/images/edits` API.`
  multipart 部件元组类型注解 `List[Tuple[str, Tuple[str, bytes, str]]]` [高]；编码失败报 `不支持的 IMAGE 维度: ` / `缺少图像依赖（numpy）: `。
- 主路径：`POST /v1/images/edits`（multipart `files` + `form` 字段）[高]，模型 `grok-imagine-image-edit` [高]。
- 并行路径：以多模态 `messages` 把 input images 作为 data-url 发到 `/v1/chat/completions`（tooltip `填写时会以多模态 messages 方式发给 /v1/chat/completions`，`input_data_urls`、`image_url`、`edit_object_image_url` 局部名）[高]；`图生图image_url格式测试` 在 `"对象格式"` 时使用 `edit_object_image_url`（即 `{"type":"image_url","image_url":{"url":...}}` 形态）[中]，其余形态 未确认。
- **尺寸强限** [高]：`Grok 图生图当前仅支持 1024x1024，已自动将 size 从 ` + ` 改为 1024x1024` —— 图生图时强制 1024x1024。
- 输入图预缩放：`_scale_image_tensor_to_total_pixels_if_needed`（megapixels / resolution_steps / `comfy.utils.common_upscale` / `nearest-exact` / `disabled` 裁剪，docstring：`Align oversized Grok input images with ComfyUI's "Scale Image to Total Pixels" logic. Only downscale when the source image exceeds the configured total pixels.`）[高]；上限常量 `_MAX_INPUT_IMAGE_MEGAPIXELS` 的数值 **未确认**（包装层 Grok_Safe_PY 中同名常量为 1.0，且包装层默认 `_ENABLE_INPUT_IMAGE_AUTOSCALE = False`，即包装层缩放默认关闭）[中]。

### 3.6 图片下载（`_download_image_bytes`）

带鉴权 `Authorization: Bearer <key>` 下载 `/v1/files/image/...` 或外链，流式 `iter_content` 计时；**四种"策略"标签**（日志 `| 策略: `）[高]：`直连无鉴权`、`直连鉴权`、`系统代理无鉴权`、`系统代理鉴权` —— 配合 `Requests Session` + `trust_env`（绕过代理时 `trust_env=False`）构成代理回退矩阵（矩阵顺序 未确认）。校验 `_is_valid_image_bytes`，可疑内容走 `_decode_nested_payload_from_bytes`（`^[\[{]` JSON 头探测）；`Accept-Encoding`/`application/json`/`Content-Type`/`User-Agent: ComfyUI-TE_API/1.0` [高]。结果进入 `_IMAGE_DOWNLOAD_CACHE`（`OrderedDict` + `move_to_end`/`popitem` = LRU，容量 `_IMAGE_DOWNLOAD_CACHE_MAX`，数值未确认）[高]。

### 3.7 与内部支撑模块的协作

- `config_manager` [高]：符号 `CONFIG_MANAGER`、`ConfigManager`、`load_api_key`、`get_effective_api_base_url`、`sanitize_api_key`、`MODULE_DIR` —— 构造一次性 ConfigManager 供 `_resolve_key_and_url` 与强制回退用；注意本文件**没有** `load_max_workers` / `network_workers_cap` / `should_bypass_proxy` 字符串（字节级 grep 为 False），即不读取并发/代理配置键，`绕过代理` 仅由节点参数控制 [高]。
- `image_codec` [高]：引用 `ImageCodec`、`base64_to_tensor_single`（单张 base64 → tensor）、模块函数 `encode_numpy_image_to_api_file_part`、`build_preview_tuple`（实时预览）；不引用 `ErrorCanvas` / `prepare_input_*`（grep False，与 image_codec.md §4 记录的 Grok 使用清单一致 [高]）。
- `task_runner` [高]：`BatchGenerationRunner` + `task_runner`（§3.3）。`InterruptProcessingException` 字符串不在本文件（grep False）→ 中断通过 `comfy.model_management.throw_exception_if_processing_interrupted` 直接触发 [高（负证据）]。
- `api_client`：**无任何字符串引用**（`api_client` / `APIClient` grep False）——本节点自持 `requests` 网络代码，不走 api_client.pyd [高（负证据）]。
- `save_image_with_output_core`：无引用（grep False）；该注册名 `TE_image_pro_grok_image` 仅在 save_image_with_output_core.pyd 的说明中被提及 [高（负证据）]。
- ComfyUI 核心 [高]：`comfy.model_management`（中断/资源检查，`model_management` 局部名），`comfy.utils.ProgressBar` + `common_upscale`，`PromptServer` + 自建 `_DummyPromptServer`（ComfyUI 不可用于预览推送时的占位对象 [中]），`torch`/`numpy`/`PIL`/`BytesIO`。

## 4. 外部依赖与副作用

- 网络端点 [高]：`{base}/v1/chat/completions`、`{base}/v1/images/generations`、`{base}/v1/images/edits`，资源回链 `{base}/v1/files/image/...`；认证 `Authorization: Bearer <api_key>`（`Bearer ` 字符串）+ `User-Agent: ComfyUI-TE_API/1.0`；服务端即 grok2api 风格反代。
- 配置 [高]：读 `config.ini` `[gemini] api_key / api_base_url`（经 config_manager.pyd）；节点参数优先。无文件写入迹象（`abspath`/`open` 串存在但用途未确认——`open` 可能仅为读响应文本，未确认）。
- 代理 [高]：默认 `Session.trust_env=True` 走系统代理；`绕过代理=True` 时禁用（`trust_env` / `直连无鉴权` / `系统代理…鉴权` 策略标签）。
- 内存缓存 [高]：下载图片字节 LRU（`_IMAGE_DOWNLOAD_CACHE`），容量常数未确认。
- 第三方库迹象 [高]：`requests`（Session/iter_content/timeout）、`torch`/`numpy`/`PIL(Image/RGB/.png)`、`comfy.utils`、`comfy.model_management`、`urllib.parse`、`collections(OrderedDict)`、`base64（b64encode/b64decode）`、`re`（`search/findall/match/fullmatch/compile/multiline/IGNORECASE`）。
- PE IMPORT 表 [高]：仅 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / `api-ms-win-crt-runtime-l1-1-0.dll`（无独立网络 DLL——HTTP 由 Python 层 requests 完成）。

## 5. 错误处理与用户可见文案

均为文件内原文字符串 [高]，触发场景为推断 [中]：

| 消息 | 触发场景 |
|---|---|
| `请输入 prompt` | prompt 为空 |
| `请在 config.ini 中配置 API Key 或在节点中填写` / `请在 config.ini 中配置 API URL 或在节点中填写` / `未配置有效的 API URL` | 密钥/地址解析失败 |
| `API 调用失败: ` / `响应非 JSON: ` / `响应解析失败: ` / `请求异常: ` | HTTP/解析异常 |
| `响应中未包含图片 data` / `响应已返回，但没有可解码图片` / `未在响应中解析到图片` / `生成结果为空（无可用图片）` / `生成失败：未返回任何有效图片` / `未生成任何图像` / `生成失败` | 返回无可用图 |
| `下载图片失败: ` | `/v1/files/image/...` 或外链下载失败 |
| `图片下载响应耗时: ` / `图片下载内容耗时: ` | 下载计时日志 |
| `Grok 图生图当前仅支持 1024x1024，已自动将 size 从 … 改为 1024x1024` | 图生图仍选了非 1024 尺寸时自动修正 |
| `不支持的 IMAGE 维度: ` / `缺少图像依赖（numpy）: ` | 输入 tensor 维度异常 / numpy 缺失 |
| `系统代理鉴权` 类"策略"标签 + `\| 策略: ` | 代理回退策略日志 |
| `Errors:` | `continue_on_error` 汇总失败任务 |
| 上游"仅文本"回复（疑似安全拒答，无独立文案串，归入 `上游仅返回 …`） | 未确认 |

## 6. 证据附录

### 6.1 源路径与 qualname（ASCII）

```text
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Grok_Image_Generator.c
custom_nodes/TE_image/source_py_backup/Grok_Image_Generator.py
custom_nodes.TE_image.Grok_Image_Generator
custom_nodes.TE_image.Grok_Image_Generator.BananaGrokImageNode.__init__ (含 lambda1)
custom_nodes.TE_image.Grok_Image_Generator.BananaGrokImageNode.INPUT_TYPES
custom_nodes.TE_image.Grok_Image_Generator.BananaGrokImageNode._resolve_key_and_url
custom_nodes.TE_image.Grok_Image_Generator.BananaGrokImageNode._call_generate_once
custom_nodes.TE_image.Grok_Image_Generator.BananaGrokImageNode._call_edit_once
custom_nodes.TE_image.Grok_Image_Generator.BananaGrokImageNode.generate_images (含 _worker / _progress_callback / lambda2 / lambda3)
```

### 6.2 节点注册与常量（原文字符串）

```text
TE_image_pro_grok_image      TE MAN Grok Image      TE MAN/Grok
FUNCTION  NODE_CLASS_MAPPINGS  NODE_DISPLAY_NAME_MAPPINGS  RETURN_TYPES  RETURN_NAMES  OUTPUT_NODE
CATEGORY  IMAGE  STRING  INT  BOOLEAN  required  optional  choices  tooltip  defaultInput  control_after_generate
QUICK_FUNCTION_NONE  QUICK_FUNCTION_OPTIONS  QUICK_FUNCTION_PREFIXES
_MAX_INPUT_IMAGE_MEGAPIXELS  _OFFICIAL_SCALE_METHOD(=nearest-exact)  _IMAGE_DOWNLOAD_CACHE  _IMAGE_DOWNLOAD_CACHE_MAX
_resolve_chat_completions_url  _resolve_images_generations_url  _resolve_images_edits_url
grok-imagine-image  grok-imagine-image-edit
```

### 6.3 端点 / 协议（原文字符串）

```text
/v1/chat/completions   /chat/completions   /v1/images/generations   /images/generations
/v1/images/edits       /images/edits       /v1/files/image/         /files/image/   /files/
text/event-stream      [DONE]      data:    Bearer     Authorization    User-Agent
ComfyUI-TE_API/1.0     application/json    Content-Type    Accept-Encoding    headers   session
b64_json   response_format   stream  decode_unicode  iter_content  chunk_size  timeout_s
```

### 6.4 响应解析（原文字符串）

```text
!\[[^\]]*\]\(([^)]+)\)                       ← _MD_IMAGE_RE
https?://[^\s\”'<>\\)]+                      ← _URL_RE
\.(png|jpg|jpeg|webp|gif|bmp)(\?|#|$)        ← _IMAGE_EXT_RE
^[A-Za-z0-9+/=\r\n]+$                        ← _BASE64_BLOB_RE
(?:^|_)(?:b64|base64)(?:_|$)                 ← base64 键名探测
(?:content|text|delta|message|output)        ← 文本字段探测
^[\[{]    utf-8-sig    gb18030    data:image    ;base64,
```

### 6.5 中文长文本（快捷功能模板，原文，含 ×）

- 三视图模板：`参照原图生成人物面部特写搭配全身三视图组合画面； 画面左侧放置超大尺寸人物面部特写，右侧依次排布正面全身照 / 侧面全身照 / 背面全身照，所有内容整合在 同一画幅内；采用纯白色背景，严格对齐人物人体比例 ，杜绝透视畸变问题，各视图之间间距均匀规整,无文字描述`
- 短三视图模板：`三视图（正面、侧面、背面），白色纯色背景，人物角色设计图，`（十六进制 `E4 B8 89 E8 A7 86 E5 9B BE EF BC 88 …`，其余接续部分通过 UTF-8 扫描获得）
- 九宫格[剧情]分镜：`根据提供的` + `剧情概述 / 画面主题 / 参考图` + `，生成一张具有清晰叙事推进关系的 3×3 九宫格分镜图，共 9 个连续镜头` + `全部镜头发生在同一场景与同一时间轴内，九个画面之间必须存在明确的前后承接关系，形成连续的动作/视线或情绪推进，而不是彼此孤立的画面拼接` + `分镜采用电影镜头语言进行自由发挥：在整体叙事推进中自然涵盖远景/中景/近景与特写等不同景别，并根据剧情需要灵活使用正视/侧视/背视/过肩/内反打/轻微俯仰等视角变化，用于强化空间关系/人物心理与节奏起伏` + `镜头景别与角度不与编号固定绑定，而是由剧情发展自动选择最合适的表现方式，使九个镜头整体读起来具备真实影视分镜的流动感` + `当用户仅提供剧情文字时，应主动补全合理的场景结构/人物站位/行动路线与镜头关系，使画面具备清晰空间逻辑；当用户提供参考图时，应将其作为人物外观/服装风格/色彩倾向与整体美术气质的统一依据，并在全部九个镜头中严格继承，不得随镜头推进出现风格变化或角色漂移` + `在全部九个分镜中，人物的外观/服装/体型比例/面部特征保持一致，整体色彩倾向与光照条件统一，仅允许人物动作/姿态以及镜头远近和角度发生变化，不得出现角色变形/肢体缺失/结构错乱或美术风格断裂，纯视觉展示，没有任何文字/字母或标签，每个画面之间被清晰的黑色实线分割`
- 四宫格[剧情]分镜：同上结构，将"3×3 九宫格/九个"替换为"2×2 四宫格/四个"
- 九宫格[场景]分镜：`生成一张严格的3x3九宫格图像，纯视觉展示` + `正中央为场景标准透视效果图；正上方为俯视角度画面；正下方为地面纹理视角；左侧为左侧墙壁平视画面；右侧为右侧墙壁平视画面；四个角落分别是：正前方视角/正后方视角以及两个无文字的材质道具特写` + `要求：九个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，`
- 四宫格[视角]分镜：`生成一张严格的2x2四宫格图像，纯视觉展示` + `场景标准透视效果图；俯视角度画面；正正前方视角；正后方视角` + `要求：四个画面光影逻辑完全统一，全方位展示空间，绝对不要生成任何解释性文字或图表排版，`
- （模板与选项值的归属映射中，剧情/场景/视角三项由字面匹配；`白底三视图`/`白底四视图` 与上面两个"三视图"模板的具体对应关系 未确认。）

### 6.6 输入输出与提示短句（原文字符串）

```text
用于生成图片的提示词           生成一张可爱的小猫图片
目标图片张数，对应 image_config.n    图片尺寸，对应 image_config.size
服务地址，如 http://localhost:8000（不要带 /v1/chat/completions）
API Key；留空则读取 config.ini 的 gemini.api_key（如你复用同一套配置）
使用快捷功能生成               请求超时（秒）
参考/编辑输入图片（可选）  第二路参考/编辑输入图片（可选）  第三路参考/编辑输入图片（可选）
填写时会以多模态 messages 方式发给 /v1/chat/completions
仅供 ComfyUI 工作流使用；不会写入请求体     需要忽略系统代理/梯子时开启
图生图image_url格式测试   对象格式
```

### 6.7 代理策略 / 下载缓存 / 并发（原文字符串）

```text
直连无鉴权   直连鉴权   系统代理无鉴权   系统代理鉴权   | 策略:    trust_env   bypass_proxy
s | 大小:    KB | 策略:    图片下载响应耗时:    图片下载内容耗时:
OrderedDict  move_to_end  popitem   _IMAGE_DOWNLOAD_CACHE
BatchGenerationRunner  task_runner  worker_fn  task_index  continue_on_error  batch_size  ProgressBar
throw_exception_if_processing_interrupted  _ensure_not_interrupted  _DummyPromptServer  PromptServer
```

### 6.8 负证据（字节级 grep，全文大小写敏感）

`api_client` / `APIClient` / `save_image_with_output_core` / `load_max_workers` / `network_workers_cap` / `should_bypass_proxy` / `_ENABLE_INPUT_IMAGE_AUTOSCALE` / `InterruptProcessingException` / `ThreadPool` / `ErrorCanvas` / `prepare_input` → 均不存在。

### 6.9 复核命令

```bash
strings -n 5 /Users/holmofy/Downloads/TE_MAN/Grok_Image_Generator.pyd | grep -E 'grok-imagine|/v1/|TE_image_pro_grok|QUICK_'
```
