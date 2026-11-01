# TE_Qwen_Image_2_1_Prompt_Enhancer.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出 `PyInit_TE_Qwen_Image_2_1_Prompt_Enhancer`。静态分析（导入/导出表 + ASCII/UTF-8 字符串提取）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

ComfyUI **节点模块**（不在 `__init__.py` 的 `SKIP_MODULES` 中，自动加载注册）。实现 **TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)** 节点：对 Qwen Image 2.1 的文生图/图生图提示词做增强，支持三种增强方式——**本地官方PE**（Qwen 官方 PE 模型，分文生图 PE / 图生图 PE）、**本地LLaMA**（本地 Qwen 视觉大模型 + mmproj，经 llama-cpp-python）、**API**（在线 OpenAI 兼容 chat 接口）。内置官方提示词工程规则（文生图版 + 图生图编辑版两套长系统提示词皆编译进二进制，不依赖外部模板文件）。与 README v3.7.2 第 1 条描述一致 [高]。

- 原始源路径：`custom_nodes/TE_image/source_py_backup/TE_Qwen_Image_2_1_Prompt_Enhancer.py`（编译单元 `...\.c` 同伴）[高]；旧包名 `TE_image`（qualname 前缀 `custom_nodes.TE_image.`），与项目内其他 pyd 一致。
- 典型上游：`TE_Prompt_Text` / `TE_H3_Prompt_Enhancer` 输出 `STRING` 接到本节点"输入提示词"；典型下游：Qwen Image 2.1 生成类节点 [中——README 工作流链接 + 前端 `te_prompt_text.js` 把提示词节点下游定位到 `QwenTE_ImageInfer` 节点的 `提示词` 输入 [高（JS 明文）]]。

## 2. Python API

- 导出：仅 `PyInit_TE_Qwen_Image_2_1_Prompt_Enhancer` [高]。
- 导入：`python3.dll`（limited ABI）、`KERNEL32.dll`、`VCRUNTIME140.dll`、CRT；无 WS2_32/网络库——网络经由 Python 层 `requests` [高]。
- 运行期依赖（仅名字符串证据）：`requests`、`llama_cpp`（可选）、`torch`、`numpy`、`PIL`、`comfy`、`comfy.sd`、`comfy.model_management`、`folder_paths`、`os`、`re`、`json`、`base64`、`hashlib`、`io`、`gc`、`pathlib`、`inspect`、`importlib(.util)`、`logging`、`dataclasses`、`typing` [高]；TE MAN 内部库 `config_manager`（`ConfigManager`、`load_api_key`、`sanitize_api_key`、`get_full_path_or_raise`）与 `logger` [高——字符串存在]。

### 模块级对象（qualname 全部为 `custom_nodes.TE_image.TE_Qwen_Image_2_1_Prompt_Enhancer.*` [高]）

| 对象 | 方法/字段 | 推断 |
|---|---|---|
| `TEQwenImage21PromptEnhancer` | `INPUT_TYPES`、`enhance_prompt`、`TE_MAN_CONCURRENT_ELIGIBLE`、`soft_empty_cache` | 节点类 [高]；`TE_MAN_CONCURRENT_ELIGIBLE` 为 TE MAN 并发执行兼容标记（同包 task_runner 约定）[中] |
| `TEQwenImage21OfficialStorage` | 类方法 `load` / `unload` | "本地官方PE"模型的全局缓存与卸载 [高（qualname）] |
| `TEQwenImage21OfficialModel` | dataclass（`TEQwenImage21OfficialModel | None`、`object | None`、`extra_template_arguments` 等字段名） | 官方 PE 已加载模型包装 [中] |
| `TEQwenImage21LocalStorage` | 类方法 `load` / `unload` | "本地LLaMA" llama model/ctx 的全局缓存与卸载 [高（qualname）] |
| `TEQwenImage21LocalModel` | — | 本地 llama 模型包装 [高（名）] |

### 内部函数族（qualname 直接证据 [高]）

- 模型/文件选择：`_llm_file_choices`（主模型列表）、`_official_pe_choices`（官方 PE 模型列表）、`_detect_model_family(model_name)`（识别 qwen3.5/3.6/3.8 及 VL 变体）、`_validate_gguf_shards(file_label)`、`_llama_argument_supported`、`_raise_llama_unavailable`、`_llama_cpp_package` / `_llama_cpp_import_error`。
- llama 加载准备：`_prepare_llama_dll_search_path`（`os.add_dll_directory`、`PATH`/`environ`、`_dll_directory_handles`）、`_reset_llm_state`。
- handler 工厂：`_create_multimodal_handler(mmproj_path)`、`_create_qwen35_handler`（`reasoning_effort`、`chat_template_override`；报错"创建 Qwen35ChatHandler 失败"）、`_adapt_qwen38_template(chat_template)`、`_create_qwen38_vision_handler`、`_create_qwen38_text_handler`（内部 `token_text(token_id, model)`、`qwen38_formatter`；含 `enable_thinking`、`preserve_thinking` 局部名）。
- 会话/推理：`_call_chat_completion(params)`、`_request_local(config→mmproj, context_length)`、`_request_official_pe(pe_model…, max_output_tokens, seed)`、`_request_api(system_prompt)`、`_local_config`。
- 后处理：`_clean_think_blocks(text)`、`_repair_mojibake(value)`、`_strip_code_fence`、`_parse_result`、`_extract_response_text(data)`（局部 `read_content`）。
- 输入准备：`_build_api_input(user_prompt, image_base64_list)`、`_image_to_jpeg_base64(image, max_edge)`、`_resize_image_tensor_max_pixels(image_tensor, max_pixels, max_edge)`。
- 认证/端点：`_resolve_api_key(api_key)`、`_resolve_api_url(api_base_url)`、`_normalize_seed(seed_value)`。
- 模板/策略：`_build_system_prompt(base_prompt, output_language, …)`、`_text_signature`、`_settings_signature(values→encode)`（缓存指纹 `settings_fingerprint`、`sha256(hexdigest)`）。

### ComfyUI 节点注册 [高（字符串）/中（键值归属)]

- `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` / `CATEGORY` / `FUNCTION` / `RETURN_TYPES` / `RETURN_NAMES` / `OUTPUT_NODE` 字符串均存在。
- 注册键：`TE_Qwen_Image_2_1_Prompt_Enhancer`（已确认，动态回填实测单键）。
- 显示名：`TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)` [高]。
- `CATEGORY`：`TE MAN/Prompt`（已确认，动态回填）。
- `FUNCTION`：`enhance_prompt` [高（qualname）]。
- 输出：已确认 `RETURN_TYPES = ("STRING",)`、`RETURN_NAMES = ("增强提示词",)`，且 `OUTPUT_NODE = true`（动态回填）——单输出口，无 `wh_ratio`/`ratio_follow` 附加口。

## 3. 节点规格：TEQwenImage21PromptEnhancer

### 3.1 输入参数

`enhance_prompt` 的形参之一整排以连续 C 字符串出现（紧跟其 qualname 之后），与前端惯例互证（同插件 `te_prompt_text.js` 明文调用 `getOriginNodeFromInput(node,'输入提示词')`，说明 TE_MAN 增强节点用**中文输入键**）[高]：

| 输入键 | 中文 tooltip（摘录，原文见 §5/§6） | 选项/类型 |
|---|---|---|
| `输入提示词` | `输入要增强的文生图或图生图需求` | STRING/multiline [中] |
| `任务模式` | `任务模式为文生图/图生图`（见下拉生效条件 tooltip） | 下拉：`文生图` / `图生图` [中——两值字符串均存在] |
| `输出语言` | `控制增强提示词的描述语言`…`不要根据用户输入语言…改变这个选择` | 下拉：`中文` / `英文` [中——两值字符串均存在] |
| `增强方式` | —— | 下拉：`API` / `本地` / `本地官方PE` [中——三值字符串均存在；显示名"(本地orAPI)"] |
| `文生图PE模型` | `本地官方 PE 的文生图模型，增强方式选择本地官方PE且任务模式为文生图时生效` | 下拉：来自 `models/text_encoders` [高]；**空列表回退选项 = `（请把模型放到 models/text_encoders）`（动态回填）** |
| `图生图PE模型` | `本地官方 PE 的图生图模型，增强方式选择本地官方PE且任务模式为图生图时生效` | 下拉：来自 `models/text_encoders` [高]；同上回退选项（动态回填） |
| `主模型` | `本地 Qwen 视觉模型，文件放在 ComfyUI/models/LLM/`（报错提示 `（请把模型放到 models/LLM）`） | 下拉：GGUF 来自 `models/LLM` [高]；**空列表回退选项 = `（请把模型放到 models/LLM）`（动态回填）** |
| `最大生成token` | `本地模型最大生成 token。API 模式不发送此限制` | INT：default 4096，min 256，max 32768，step 256（动态回填） |
| `上下文长度` | `本地模型的 llama.cpp 上下文长度；数值越大通常占用越多显存。API 模式不使用此设置` | INT：default 8192，min 1024，max 327680，step 256（动态回填） |

其余输入（动态回填后归属与键名均已确认）：

| 候选键 | 证据 |
|---|---|
| `图片`（optional，**键名实测为 `图片` 而非"图生图参考图片"**） | tooltip `图生图参考图片。`；图生图主图输入（动态回填更正键名） |
| `图片2`…`图片8` | 七个 optional IMAGE 输入逐一实测（动态回填）；tooltip `图生图附加参考图片。`，合计 1+7=8 张 [高] |
| `mmproj` | required COMBO，选项含 `无`，default=`无`；tooltip `图生图需要选择对应的视觉投影文件。`（动态回填） |
| `seed` | required INT：default 0，min 0，max 18446744073709551615，step 1，**`control_after_generate: true`**；tooltip `本地模型随机种子。使用生成后控制可固定、递增、递减或随机化；API 模式不使用此设置`（动态回填全证实） |
| `启用思考` | required BOOLEAN，default=false；tooltip `仅本地官方 PE 生效。开启后模型先进行思考再输出提示词；关闭后直接生成提示词。`（动态回填） |
| `生成后自动卸载模型`（键名已确认） | required BOOLEAN，default=false；tooltip `本地生成完成后自动卸载 Qwen 模型并释放显存。`（动态回填） |
| `api_key`（required，键名实测为小写 `api_key`） | STRING，default=""，tooltip `API Key；留空时读取 TE MAN 的 config.ini。`（动态回填） |
| `api_base_url`（required） | STRING，default=`https://teynex.com`，非 multiline（动态回填） |
| `model`（required） | STRING，default=`deepseek-v4.1-flash`（动态回填，`DEFAULT_API_MODEL` 实锤） |

默认值/最小步长：~~Cython 以立即数存储，字符串表不可见——未确认~~ → **已全部确认（动态回填）**：`DEFAULT_API_BASE_URL="https://teynex.com"`、`DEFAULT_API_MODEL="deepseek-v4.1-flash"`、`DEFAULT_MAX_OUTPUT_TOKENS=4096`、`DEFAULT_CONTEXT_LENGTH=8192`、`DEFAULT_IMAGE_MAX_EDGE=2048`、`DEFAULT_IMAGE_MAX_PIXELS=1048576`。

### 3.2 执行流程（enhance_prompt，按字符串拓扑）

1. 入口日志 [高]：`TE Qwen Image 2.1 execute entered prompt=[%s] settings_sha256=%s mode=%s method=%s seed=%s auto_unload=%s image_count=%s api_key_set=%s`；空输入跳过：`TE Qwen Image 2.1 execute skipped: prompt is empty`。
2. 图生图校验 [高]：`图生图模式需要连接图片输入`；图片张量 → numpy（`unsqueeze/float32/astype`）→ PIL（`Image.fromarray`）→ JPEG base64（`BytesIO`、`data:image/jpeg;base64,`），按 `DEFAULT_IMAGE_MAX_EDGE/…_MAX_PIXELS` 用 `Resampling.LANCZOS|BICUBIC` 与 `_resize_image_tensor_max_pixels` 缩放。
3. 系统提示词组装 `_build_system_prompt` [高]：
   - 文生图模式基底 = `QWEN_T2I_SYSTEM_PROMPT`（"**# Image Prompt Rewriting Expert**"，行文规则见 §6 摘录；输出 JSON `{"rewritten_prompt": …, "wh_ratio": …}`）。
   - 图生图/编辑模式基底 = `QWEN_EDIT_SYSTEM_PROMPT`（"**# Edit Prompt Enhancer — General (v2, 精简版)**"，双语言决策 A/B、属性解缠、`<image1>/<image2>` 多图标注、`wh_ratio`/`ratio_follow` 互斥规则）。
   - `_remove_conflicting_language_rules` 用正则剔除两段冲突小节（`\n\*\*FIRST …there are TWO separate language decisions\.`… 与 `\n## Language\n[\s\S]*?`，保 `\n## Output [Ff]ormat`）[高]。
   - 注入 `QWEN_OUTPUT_POLICY`（"Node output controls"：`输出语言` 决定描述语言；不发明用户未给定的画面文字；只输出纯文本、禁思维链）与 `QWEN_OFFICIAL_PE_POLICY`（"Official PE output protocol"：内部仍输出 JSON，节点只取 `rewritten_prompt`）[高]。
   - 末尾按 `输出语言` 追加中文/英文强化句 [高]（`节点选择的输出语言是中文…必须使用中文…` / `The selected output language is English. …Stop immediately after closing the JSON object`）。最终语言规则最高优先级句式：`最终语言规则（优先级最高）：节点选择的输出语言是"…"。除用户明确要求显示在图片中的文字、专有名词和品牌名外，最终提示词的全部描述性文字必须使用"…"。` [高]。
4. 三条请求分支 [高（分支名）]：
   - **API**：`_resolve_api_key`（留空读 config.ini）→ `sanitize_api_key`；`_resolve_api_url` → `requests.post`，`Authorization: Bearer <key>`、`Content-Type: application/json`；`model` 默认候选 `deepseek-v4.1-flash` [中]；端点候选 `/v1/chat/completions` 与 `/v1/responses`/`/responses`，并对 `api.deepseek.com`、`https://teynex.com` 特判 [高（串）/中（规则）——具体归一化规则未确认]；`max_tokens` 不随"最大生成token"（tooltip：`API 模式不发送此限制`）。
   - **本地官方PE**：文生图用 `文生图PE模型`、图生图用 `图生图PE模型`；模型经 `comfy.sd.load_clip(ckpt_paths=…, clip_type=CLIPType.QWEN_IMAGE?, embedding_directory=…)` 由 ComfyUI 加载（`comfy_sd/load_clip/ckpt_paths/clip_type/CLIPType/QWEN_IMAGE/text_encoders/embeddings/unload_model_and_clones/ctx_checkpoints/all_devices/soft_empty_cache` 字符串整套存在 [高]；`CLIPType.QWEN_IMAGE` 精确成员归属 [中]）；`TEQwenImage21OfficialStorage.load/unload` 缓存管理；`_request_official_pe(max_output_tokens, seed…)` 推理，采样 `temperature/top_p/top_k/min_p`、`reasoning_effort`（候选值可见 `xhigh` [低]）；`启用思考`→thinking。官方 PE 的**推理执行细节**（ComfyUI CLIP 上如何完成对话生成）未确认。
   - **本地LLaMA（"本地"）**：`_prepare_llama_dll_search_path` → 校验 `llama_cpp` 可导入（否则 `未检测到 llama-cpp-python（llama_cpp），请先安装/更新该依赖。原始导入错误：…当前 Python：…`）→ `_validate_gguf_shards`（分片 regex `^(?P<prefix>.+)-(?P<index>\d{5})-of-(?P<total>\d{5})(?P<extension>\.gguf)$`；错误：`GGUF 分片不完整（共 N 个分片）`、`缺少分片：`、`请选择第一片：`、`选中了 GGUF 的第 N 个分片`）→ `Llama(model_path…, n_ctx, n_gpu_layers, …)`+ handler：
     - qwen3.5(.VL)/qwen3.6(-VL) → `Qwen35ChatHandler` 或 `Qwen3VLChatHandler`（需 llama-cpp-python 支持，否则报"不支持 Qwen35ChatHandler/Qwen3VLChatHandler，请更新 llama-cpp-python"）；
     - qwen3.8(.VL) → 自定义 `_create_qwen38_text_handler` / `_create_qwen38_vision_handler` / `GenericMTMDChatHandler`（`llama_cpp.llama_multimodal`、`chat_formatter_to_chat_completion_handler`、`Jinja2ChatFormatter`；`_adapt_qwen38_template` 把含 `<|image_pad|>` 的占位替换为 `{{- '<|vision_start|>' }}…{%- if item.image_url is string %}…url %}{%- endif %}{{- '<|vision_end|>' }}`）；缺模板：`Qwen3.8 GGUF 缺少 tokenizer.chat_template`；有 image_pad 却无视觉能力：`Qwen3.8 聊天模板包含 <|image_pad|>，但无法适配视觉输入`；mmproj 必须已选。
     - `_local_config(mmproj, context_length)`、采样参数 `temperature/top_p/top_k/min_p/repeat_penalty/repetition_penalty/presence_penalty/frequency_penalty/do_sample/stop/max_tokens`，`seed` 仅本地模式使用。
5. 响应后处理 [高]：`_clean_think_blocks`（`<think\b[^>]*>.*?\n\n\n*`?`、`<思考>.*?</思考>`、"```thinking\b.*?```"、"```thought\b.*?```"、"```(?:json|text|markdown)?\s*([\s\S]*?)\s*```"）；`_repair_mojibake`（0xE5/0xE8 前缀+双层连续字节还原，字母表 `0123456789abcdef…ABCDEF` [中]）；`_strip_code_fence`；`_parse_result` 解析 `rewritten_prompt`（失败/为空则报警并在官方 PE/本地模式回退到原文纯文本 [中]）。空产出报：`模型返回为空，可能只生成了思考内容但没有最终提示词。请提高最大生成token后重试。`
6. 模型复用与缓存 [高]：`_text_signature`（上次提示词）+`_settings_signature`（sha256 设置指纹）决定 `TE Qwen Image 2.1 local model reusing/loaded/unloaded/unloading model=%s` 与官方 PE 对应日志；`生成后自动卸载模型` 开启或签名变化则 unload（官方 PE 走 `comfy.model_management.unload_model_and_clones` + `soft_empty_cache` [中]）。
7. 出口 [高]：`TE Qwen Image 2.1 execute completed output=[%s]` / `…API generation completed…` / `…official PE generation completed…`；异常统一包装为 `TE MAN Qwen Image 2.1 提示词增强失败：<原因>`（logger `TE Qwen Image 2.1 execute failed`），ComfyUI 收到异常消息。

### 3.3 返回

- `STRING`（增强后的提示词纯文本，名 `增强提示词`）。已确认单输出口 `RETURN_TYPES=("STRING",)`、`RETURN_NAMES=("增强提示词",)`、`OUTPUT_NODE=true`（动态回填）；不追加 `wh_ratio`/`ratio_follow` 输出口。

## 4. 外部依赖与副作用

- **网络端点** [高（串存在）/中（规则）]：OpenAI 兼容 chat API；候选路径 `/v1/chat/completions`、`/v1/responses`、`/responses`、`/v1`；特判主机 `api.deepseek.com` 与 `https://teynex.com`（插件作者中转站，`config.ini` 样例 `api_base_url = https://teynex.com` [高]；默认模型候选 `deepseek-v4.1-flash` [中]）。默认 base URL 为两者之一——**已确认（动态回填）：`https://teynex.com`**（`DEFAULT_API_BASE_URL` 常量实锤；默认模型 `DEFAULT_API_MODEL="deepseek-v4.1-flash"` 同步实锤）。
- **认证**：`Authorization: Bearer <API Key>`；Key 来源优先级：节点输入 > `config.ini`（经 `config_manager.load_api_key`，`[gemini]` 段示例样例文件）；日志/请求前 `sanitize_api_key` 打码 [高]。
- **文件系统**：
  - 读：`ComfyUI/models/LLM/`（主模型 GGUF + mmproj，`folder_paths.get_folder_paths('LLM')`）、`models/text_encoders`（官方 PE，`folder_paths.get_filename_list`，扩展名过滤 `.gguf`/`.safetensors`/`.pt/.pth/.bin` [中]）；`config.ini`；GGUF 多分片文件（`-00001-of-…`）。
  - 写：无写文件证据——introspection 亦无写文件迹象（动态回填核对，维持无写文件结论）。
- **配置键**：`config.ini` 的 `api_key`、`api_base_url` [高；`[gemini]` 段归属沿用 api_client/config_manager 与 sibling spec]。
- **第三方库**：`llama-cpp-python`（可选，含 multimodal handlers）、`requests`、`torch/numpy/PIL`、`comfy.*`、`folder_paths`、TE MAN `config_manager`/`logger` [高（名字符串）]。
- **副作用**：DLL 搜索路径修改（`os.add_dll_directory`、`PATH`）；显存管理（`comfy.model_management.unload_model_and_clones/ctx_checkpoints/all_devices/soft_empty_cache`）；进程级模块缓存（Storage 单例 `should_unload/had_model/memory_clear`）[高——符号存在]。
- **并发**：类属性 `TE_MAN_CONCURRENT_ELIGIBLE`——允许该节点被 TE_MAN 并发执行器并行 [中（task_runner 系插件约定）]。

## 5. 错误处理与用户可见文案

| 文案（原文） | 触发场景 |
|---|---|
| `TE MAN Qwen Image 2.1 提示词增强失败：<异常>` | enhance_prompt 顶层异常包装 [高] |
| `图生图模式需要连接图片输入` / `图生图模式需要选择 mmproj 视觉投影文件` / `图生图需要选择对应的视觉投影文件` | 图生图校验 [高] |
| `未找到官方 PE 模型，请把 qwen_image_2.1_pe 模型放到 models/text_encoders/。（请把模型放到 models/text_encoders）` | PE 下拉为空 [高] |
| `未找到可用主模型，请把模型放到 ComfyUI/models/LLM/ 后重启。` | 主模型下拉为空 [高] |
| `找不到模型文件：` / `找不到 mmproj 文件：` | 选择的文件不存在 [高] |
| `未检测到 llama-cpp-python（llama_cpp）。请先安装/更新该依赖。\n原始导入错误：…\n当前 Python：…` | llama_cpp 导入失败 [高] |
| `当前 llama-cpp-python 不支持 Qwen35ChatHandler / Qwen3VLChatHandler / Qwen3.8 视觉聊天处理器 / Qwen3.8 聊天模板，请更新 llama-cpp-python。`（四条） | handler 能力检测失败 [高] |
| `创建 Qwen35ChatHandler 失败` | handler 构造异常 [高] |
| `Qwen3.8 GGUF 缺少 tokenizer.chat_template。` / `Qwen3.8 聊天模板包含 <|image_pad|>，但无法适配视觉输入。` | 模板适配 [高] |
| `GGUF 分片不完整（共 N 个分片）…缺少分片：…请选择第一片：…选中了 GGUF 的第 N 个分片` | 分片校验提示 [高] |
| `请在节点中填写 API Key，或在 config.ini 中配置 API Key` / `未配置有效的 API URL` / `API 调用失败 HTTP <code>` / `API 返回格式异常：` | API 分支 [高] |
| `本地模型返回格式异常：` | 本地分支 [高] |
| `模型返回为空，可能只生成了思考内容但没有最终提示词。请提高最大生成token后重试。` | 产出为空 [高] |
| `当前为 API 模式：只输出最终增强后的提示词纯文本，不要输出 JSON` / `当前为本地模式：…` | 注入到请求的策略文本（非错误）[高] |

## 6. 证据附录

### 6.1 节点注册与输入键（原文摘录）

```
TEQwenImage21PromptEnhancer.enhance_prompt
输入提示词 / 任务模式 / 输出语言 / 增强方式 / 文生图PE模型 / 图生图PE模型 / 主模型 / 最大生成token / 上下文长度   ← 连续 C 串
启 用 思考 / 生成后自动卸载模型 / 图生图参考图片 / 图生图附加参考图片 / 图片2 / 图片3 / 图片4 / 图片5 / 图片6 / 图片7 / 图片8
required / optional / input(输入类型) / STRING / multiline / INT / BOOLEAN / IMAGE / tooltip / default
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / RETURN_TYPES / RETURN_NAMES / OUTPUT_NODE / CATEGORY / FUNCTION
TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI) / TE MAN/Prompt
```

### 6.2 模型家族与 handler

```
qwen3.5 / qwen3.6 / qwen3.8 / Qwen3-VL / Qwen3.5-VL / Qwen3.6-VL / Qwen3.8-VL
Qwen35ChatHandler / Qwen3VLChatHandler / GenericMTMDChatHandler
llama_cpp.llama_chat_format / llama_cpp.llama_multimodal / chat_formatter_to_chat_completion_handler / Jinja2ChatFormatter
create_chat_completion / add_vision_id / <|image_pad|> / <|vision_start|>/ <|image_soft_token|>/ <|end_of_turn|>/ <|start_of_turn|>user
_reasoning_effort 候选可见: xhigh（归属未确认）; progressive（归属未确认）
```

### 6.3 端点/认证/请求

```
Bearer  / Authorization / Content-Type application/json / requests post
/v1/chat/completions / /v1/responses / /responses / /v1
api.deepseek.com / https://teynex.com / deepseek-v4.1-flash / Bearer
DEFAULT_API_BASE_URL / DEFAULT_API_MODEL / max_tokens / temperature / top_p / top_k / min_p
presence_penalty / frequency_penalty / repeat_penalty / repetition_penalty / do_sample
data:image/jpeg;base64, / choices / output_text / reasoning / status_code
```

### 6.4 系统提示词/策略常量

```
QWEN_T2I_SYSTEM_PROMPT / QWEN_EDIT_SYSTEM_PROMPT / QWEN_OUTPUT_POLICY / QWEN_OFFICIAL_PE_POLICY
QWEN_IMAGE（与 _create_qwen35_handler、clip_type 邻近）
"# Image Prompt Rewriting Expert - You turn a user's image request into one long English paragraph…"
"# Edit Prompt Enhancer — General (v2, 精简版)" / "**FIRST — there are TWO separate language decisions.…"
"## Official PE output protocol - The node extracts `rewritten_prompt`…"
"{"rewritten_prompt": "<the description>", "wh_ratio": "<e.g. 3:2>"}"
```

### 6.5 文件/模型校验与缓存

```
^(?P<prefix>.+)-(?P<index>\d{5})-of-(?P<total>\d{5})(?P<extension>\.gguf)$ / -00001-of- / .gguf / .safetensors / .pt / .pth / .bin
mmproj / is_mmproj / clip_model_path / model_path / models_dir / LLM / text_encoders
settings_fingerprint / sha256= / digests… / hexdigest
unload_model_and_clones / soft_empty_cache / ctx_checkpoints / all_devices / memory_clear
```

### 6.6 完整日志行（原文）

```
TE Qwen Image 2.1 execute entered prompt=[%s] settings_sha256=%s mode=%s method=%s seed=%s auto_unload=%s image_count=%s api_key_set=%s
TE Qwen Image 2.1 execute skipped: prompt is empty
TE Qwen Image 2.1 execute failed
TE Qwen Image 2.1 execute completed output=[%s]
TE Qwen Image 2.1 official PE loading model=%s
TE Qwen Image 2.1 official PE loaded model=%s
TE Qwen Image 2.1 official PE reusing loaded model=%s
TE Qwen Image 2.1 official PE generation starting model=%s seed=%s thinking=%s image_count=%s prompt=[%s]
TE Qwen Image 2.1 official PE generation completed output=[%s]
TE Qwen Image 2.1 official PE unloading model=%s
TE Qwen Image 2.1 official PE model unloaded=%s
TE Qwen Image 2.1 official PE unload skipped: no model is loaded
TE Qwen Image 2.1 local model loading model=%s
TE Qwen Image 2.1 local model loaded model=%s
TE Qwen Image 2.1 local model reusing model=%s
TE Qwen Image 2.1 local model unloading loaded=%s
TE Qwen Image 2.1 local model unloaded
TE Qwen Image 2.1 API generation starting model=%s image_count=%s prompt=[%s]
TE Qwen Image 2.1 API generation completed output=[%s]
```

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 2025 Server + Python 3.13.16 + ComfyUI 真实加载后的运行时 introspection（module 显示为 `custom_nodes.TE_image.TE_Qwen_Image_2_1_Prompt_Enhancer`）。模块文件为 `TE_Qwen_Image_2_1_Prompt_Enhancer.pyd`。

### 7.1 TEQwenImage21PromptEnhancer——INPUT_TYPES 全表

- FUNCTION=`enhance_prompt`；CATEGORY=`TE MAN/Prompt`；**OUTPUT_NODE=true**；`has_IS_CHANGED=false`、`has_VALIDATE_INPUTS=false`（缓存判定在 `enhance_prompt` 内部按 `_settings_signature` 处理，不依赖 IS_CHANGED）；无 `has_check_lazy_status`/`has_on_execute`。
- RETURN_TYPES=`("STRING",)`；RETURN_NAMES=`("增强提示词",)`。
- required：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `输入提示词` | STRING | multiline=true，default=""，tooltip=`输入要增强的文生图或图生图需求。` |
| `任务模式` | COMBO | `["文生图","图生图"]`，default=`文生图` |
| `输出语言` | COMBO | `["中文","英文"]`，default=`中文`，tooltip=`控制增强提示词的描述语言。用户明确要求的画面文字保持原文。` |
| `增强方式` | COMBO | `["本地","本地官方PE","API"]`，default=`本地` |
| `api_key` | STRING | default=""，非 multiline，tooltip=`API Key；留空时读取 TE MAN 的 config.ini。` |
| `api_base_url` | STRING | default=`https://teynex.com`，非 multiline |
| `model` | STRING | default=`deepseek-v4.1-flash`，非 multiline |
| `文生图PE模型` | COMBO | 空列表回退选项 `（请把模型放到 models/text_encoders）`，tooltip=`本地官方 PE 的文生图模型，增强方式选择本地官方PE且任务模式为文生图时生效。` |
| `图生图PE模型` | COMBO | 同上回退选项，tooltip=`本地官方 PE 的图生图模型，增强方式选择本地官方PE且任务模式为图生图时生效。` |
| `主模型` | COMBO | 空列表回退选项 `（请把模型放到 models/LLM）`，tooltip=`本地 Qwen 视觉模型，文件放在 ComfyUI/models/LLM/。` |
| `mmproj` | COMBO | 选项含 `无`，default=`无`，tooltip=`图生图需要选择对应的视觉投影文件。` |
| `最大生成token` | INT | default 4096，min 256，max 32768，step 256，tooltip=`本地模型最大生成 token。API 模式不发送此限制。` |
| `上下文长度` | INT | default 8192，min 1024，max 327680，step 256，tooltip=`本地模型的 llama.cpp 上下文长度；数值越大通常占用越多显存。API 模式不使用此设置。` |
| `seed` | INT | default 0，min 0，max 18446744073709551615，step 1，**control_after_generate=true**，tooltip=`本地模型随机种子。使用生成后控制可固定、递增、递减或随机化；API 模式不使用此设置。` |
| `生成后自动卸载模型` | BOOLEAN | default=false，tooltip=`本地生成完成后自动卸载 Qwen 模型并释放显存。` |
| `启用思考` | BOOLEAN | default=false，tooltip=`仅本地官方 PE 生效。开启后模型先进行思考再输出提示词；关闭后直接生成提示词。` |

- optional（9 项图片输入）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `图片` | IMAGE | tooltip=`图生图参考图片。` |
| `图片2`…`图片8` | IMAGE ×7 | tooltip=`图生图附加参考图片。` |

- 无 hidden 输入；下拉枚举 `文生图PE模型/图生图PE模型/主模型/mmproj` 为动态文件列表（实测环境无对应模型文件，故显示回退占位选项——这也直接暴露了空列表 fallback 文案）。

### 7.2 模块常量实锤值（modules["TE_MAN.TE_Qwen_Image_2_1_Prompt_Enhancer"].constants）

| 常量 | 实测值 |
|---|---|
| `DEFAULT_API_BASE_URL` | `"https://teynex.com"` |
| `DEFAULT_API_MODEL` | `"deepseek-v4.1-flash"` |
| `DEFAULT_MAX_OUTPUT_TOKENS` | `4096` |
| `DEFAULT_CONTEXT_LENGTH` | `8192` |
| `DEFAULT_IMAGE_MAX_EDGE` | `2048` |
| `DEFAULT_IMAGE_MAX_PIXELS` | `1048576` |
| `QWEN_T2I_SYSTEM_PROMPT` | "# Image Prompt Rewriter Expert" 文生图改写系统提示词（输出 JSON `{"rewritten_prompt", "wh_ratio"}`） |
| `QWEN_EDIT_SYSTEM_PROMPT` | "# Edit Prompt Enhancer — General (v2, 精简版)" 图生图编辑系统提示词（含双语言决策 A/B、`<image1>/<image2>` 多图标注、`wh_ratio`/`ratio_follow` 互斥规则） |
| `QWEN_OUTPUT_POLICY` | "Node output controls"：`输出语言` 为描述语言最高依据；只输出纯文本 |
| `QWEN_OFFICIAL_PE_POLICY` | "Official PE output protocol"：官方 PE 内部仍输出 JSON，节点只取 `rewritten_prompt` |
| `NODE_CLASS_MAPPINGS` | `{"TE_Qwen_Image_2_1_Prompt_Enhancer": TEQwenImage21PromptEnhancer}`（单键） |
| `NODE_DISPLAY_NAME_MAPPINGS` | `{"TE_Qwen_Image_2_1_Prompt_Enhancer": "TE MAN Qwen Image 2.1 AI提示词增强(本地orAPI)"}` |
| `PLUGIN_DIR` | `D:\a\_temp\ComfyUI\custom_nodes`（运行时值）；`MODULE_DIR` = `...\custom_nodes\TE_MAN` |

### 7.3 对正文"未确认"项的核对结论

| 正文位置 | 结论 |
|---|---|
| §2 注册键 [中] | 已确认：`TE_Qwen_Image_2_1_Prompt_Enhancer`（动态回填） |
| §2 输出元组其余成员未确认 | 已确认：单输出口 `("STRING",)` × `("增强提示词",)`，OUTPUT_NODE=true |
| §3.1 各 INT 默认值/min-max 未确认 | 已确认：`最大生成token` 4096(256-32768,step256)、`上下文长度` 8192(1024-327680,step256)、`seed` 0(0-2^64-1,step1,control_after_generate) |
| §3.1 `图生图参考图片` 键名 [中] | 更正：主图键名为 `图片`（"图生图参考图片"只是 tooltip） |
| §3.1 `API Key`/`API URL` 键名未确认 | 已确认：`api_key` / `api_base_url`（小写英文键） |
| §3.1 `生成后自动 unload` 键名未确认 | 已确认：`生成后自动卸载模型`，BOOLEAN default false |
| §3.1 常量默认值 6 项 | 已确认（见 7.2 表） |
| §3.3 是否追加 wh_ratio/ratio_follow 输出口未确认 | 已确认：不追加 |
| §4 默认 base URL 未确认 | 已确认：`https://teynex.com` |
| §3.2 端点归一化规则未确认 | 保留未确认（introspection 不含函数体） |
