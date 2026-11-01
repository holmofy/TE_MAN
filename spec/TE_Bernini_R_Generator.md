# TE_Bernini_R_Generator.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_Bernini_R_Generator`。静态分析（字符串/导入导出表）+ 明文后端 `te_bernini_backend/` 对照。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

`TE_Bernini_R_Generator.pyd` 是 TE_MAN（打包目录名 `TE_image`）的 **Wan2.2 双噪声（High/Low Noise 两阶段）视频生成节点**，是 `te_bernini_backend/`（kijai ComfyUI-WanVideoWrapper 的改造私有版）的**负有节点注册义务的明文包装层编译产物**。后端 `__init__.py` 明文写明：

- [高] "The public node is TE_Bernini_R_Generator.py; backend modules are imported lazily by that wrapper."（te_bernini_backend/__init__.py）

即本 pyd 不含任何模型/采样逻辑，其 `generate`/`enhance_prompt` 方法把 Wan 管线节点串起来并**延迟导入**后端包（`_ensure_backend_package` / `_import_backend_module`）。Cython 痕迹 [高]：

- `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Bernini_R_Generator.c`（源文件路径，TE_image = 本插件打包名）
- `custom_nodes.TE_image.TE_Bernini_R_Generator.*`（模块限定名）

README.md 中未出现 "Bernini"（grep 无命中），该节点为 **未在 README 中记录的隐藏/新增节点**。

## 2. Python API

- 导出：`PyInit_TE_Bernini_R_Generator` [高]
- IMPORT：python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime（无 WS2_32，网络走 requests 由 Python 层发出）[高]

### 模块内部函数（qualname 直接证据 [高]）

| 函数 | 推断职责 |
|---|---|
| `_detect_comfy_root` | 检测 ComfyUI 根目录（`COMFY_ROOT`/`PLUGIN_DIR`/`MODULE_DIR` 字符串） |
| `_backend_candidates` / `_resolve_backend_dir` | 枚举 `te_bernini_backend` 目录候选位置（`BACKEND_DIR_NAME`） |
| `_backend_package_name` / `_ensure_backend_package` | 把后端目录注册为包名 `_te_image_bernini_backend_`（改包名导入，避免与其他插件的同名 WanVideoWrapper 模块互相污染 [中]） |
| `_import_backend_module` | 延迟导入 `nodes.py` / `nodes_model_loading.py` / `nodes_sampler.py`（三文件名字符串均在 [高]） |
| `_wan_modules` / `_WAN_CACHE` | 后端节点类句柄集合；进程级缓存 [中] |
| `_get_input(kwargs, chinese_name, english_name)` | 输入参数读取辅助（参数带中英文双名 [高]，见 §5 tooltip） |
| `_pick_default` / `_normalize_model_name` / `_pick_lora_default` | 从 `folder_paths.get_filename_list` 等列表里挑默认模型（`folder_paths`、`get_filename_list` 字符串 [高]） |
| `_select_accel_lora` / `_apply_block_swap_and_lora` | 选/挂加速 LoRA + BlockSwap 参数（`WanVideoSetBlockSwap`、`WanVideoSetLoRAs`、`WanVideoLoraSelectMulti` 字符串 [高]） |
| `_resolve_responses_url` / `_resolve_key_and_url` / `_read_json_response_or_raise` / `_extract_output_text` / `_build_responses_payload` / `_post_responses` | 调用 OpenAI 风格 **Responses API**（`/v1/responses`、`Bearer `、`Authorization`、`Content-Type`、`application/json` [高]） |
| `_resolve_bernini_task_type` / `_bernini_task_label` / `_bernini_template_text` / `_bernini_system_prompt` / `_safe_reference_count` / `_bernini_local_prompt` / `_extract_rewritten_text` | 任务分类 → 官方模板 → 本地/API 双模式提示词改写（模板常量 `BERNINI_R2V_TEMPLATE`、`BERNINI_VR2V_TEMPLATE`、`BERNINI_V2V_TEMPLATE`、`BERNINI_T2V_A14B_EN_SYS_PROMPT`、`BERNINI_DEFAULT_SYSTEM_PROMPT`、`BERNINI_TASK_OPTIONS`、`BERNINI_TASK_DISPLAY_TO_CODE`、`BERNINI_TASK_CODE_TO_LABEL` [高]） |
| `_make_block_swap_args(blocks_to_swap)` | 组装块交换参数（`blocks_to_swap`、`vace_blocks_to_swap`、`block_swap_blocks`、`block_swap_debug` [高]） |
| `_ensure_not_interrupted` | 调用 ComfyUI 中断标记以中止生成（`throw_exception_if_processing_interrupted` [高]） |

### 节点注册（NODE_CLASS_MAPPINGS 键 → 类）

[已确认]（动态回填，NODE_CLASS_MAPPINGS 常量实测；DISPLAY 名同为实锤）：

| 注册键（推断） | 类（qualname 证据） | 显示名（字符串 [高]） | CATEGORY |
|---|---|---|---|
| `TE_Bernini_R_Generator`（已确认，动态回填） | `TEBerniniRGenerator` | "TE MAN Bernini" [高] | `TE MAN/Bernini` 已确认（动态回填） |
| `TE_Bernini_Prompt_Enhancer`（已确认，动态回填） | `TEBerniniPromptEnhancer` | "TE MAN Bernini 提示词增强(本地orAPI)" [高] | `TE MAN/Bernini` 已确认（动态回填） |

无 `WEB_DIRECTORY` 痕迹。**动态回填更正**：`OUTPUT_NODE=true` 实测挂在 `TEBerniniPromptEnhancer`（提示词增强节点）上，主生成节点 `TEBerniniRGenerator` 未标 OUTPUT_NODE。

## 3. 节点规格

### 3.1 TEBerniniRGenerator（主生成节点）

- RETURN_TYPES：已确认 `("IMAGE", "STRING")`、`RETURN_NAMES = ("图像", "状态")`（动态回填）——即除图像外还输出"状态"文本口。
- FUNCTION = "generate" [高]
- CATEGORY = "TE MAN/Bernini" 已确认（动态回填）；主节点无 OUTPUT_NODE（动态回填更正，见 §2 注册表注）。
- 行为流程（日志串 [高] 顺序）：`TE Bernini-R: encoding text → : building Bernini context latents → : loading HIGH noise model → : sampling HIGH stage(bernini-high) → : loading LOW noise model(bernini-low) → : sampling LOW stage → : decoding samples → 完成`。

输入参数（名称全部来自 pyd 字符串 [高]；类型/默认值依后端同名参数推断 [中]，除非注明）：

**视频画幅/帧 [中]**：`width`、`height`、`num_frames`（仅字符串存在；默认值未确认）。→ **动态回填更正**：运行时 INPUT_TYPES 使用中文键 `宽度/高度/帧数`（default 832/480/81，见 §7.1）；`width` 等英文键为内部变量名。

**两阶段噪声模型 [高]**（文件名直串）：
- 高噪模型默认 `Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors`（`high_noise_model` / `high_model` / `bernini_high` / `high_lora`）
- 低噪模型默认 `Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors`（`low_noise_model` / `low_model` / `bernini_low` / `low_lora`）
- 量化档位串（ choices 证据 [高]）：`fp8_e4m3fn`、`fp8_e4m3fn_scaled`、`fp8_e4m3fn_scaled_fast`、`fp8_e4m3fn_fast`、`fp8_e5m2`、`fp8_e5m2_scaled`、`fp8_e5m2_scaled_fast`、`fp8_e5m2_fast`、`fp16_fast`、`fp16`（`model_quantization`、`text_quantization`、`base_precision`、`model_precision`、`text_precision`、`vae_precision` / `high_fp8`、`low_fp8`）

**加速 LoRA [高]**：`enable_accel_lora`（`enable`）、`high_accel_lora`/`low_accel_lora`、`high_accel_lora_strength`/`low_accel_lora_strength`（FLOAT 类互串 `FLOAT`/`low_accel_lora_strength`）；默认文件（直串 [高]）：
- `Wan-Lighting\Wan2.2 - t2v_A14b_high_noise_lora_rank64_lightx2v_4step_1217.safetensors`（`DEFAULT_HIGH_ACCEL_LORA`）
- `Wan-Lighting\Wan2.2 - t2v_A14b_low_noise_lora_rank64_lightx2v_4step_1217.safetensors`（`DEFAULT_LOW_ACCEL_LORA`）
- LoRA 档位候选含 `4step`、`lightx2v`（字符串 [高]）；`BACKEND_LORA_NONE`/`LORA_NONE` 为禁用项 [中]

**BlockSwap/显存 [高]**：`BlockSwap块数`、`blocks_to_swap`、`vace_blocks_to_swap`；`offload_img_emb`、`offload_txt_emb`、`offload_device`、`low_mem_load`、`vram_management_args`、`force_offload`。

**注意力/编译（ATTENTION_OPTIONS、SCHEDULER_OPTIONS 常量名 [高]；选项 [中] 对应后端 choices）**：`attention_mode` ∈ `sageattn`、`sageattn_3`、`sageattn_compiled`、`radial_sage_attention`、`flash_attn_2`、`flash_attn_3`；`rope_function`、`rms_norm_function`、`normalization`、`compile_args`。

**调度/步数（[高] 字符串；[中] 默认抄后端 WanVideoScheduler：steps=30、shift=5.0、euler/unipc）**：
- `high_scheduler` / `low_scheduler`（scheduler 选项含 `euler`、`unipc`、`dpm++`、`dpm++_sde`、`flowmatch_causvid` [高]，与后端 scheduler_list 对应 [中]）
- `steps`、`shift`、`high_end_step`、`low_start_step`（校验错误见 §5：低噪从 `low_start_step` 起、高噪到 `high_end_step` 止，两阶段互补拆分总步数）
- `high_cfg`、`low_cfg`（FLOAT，置信采样 CFG [中]）

**文本编码（[高]）**：`text_encoder`（默认 `umt5-xxl-enc-fp8_e4m3fn.safetensors` 直串）、`text_device`、`use_cpu_cache`、`use_disk_cache`、`use_text_disk_cache`、`text_encoders`、`text_embeds`；类 `WanVideoTextEncodeCached` [高]。

**VAE（[高]）**：`vae_model`（候选含 `wan2.2_vae`、`wan_2.1_vae`、`wan_2.1_vae_confyui`、`Wan2_1_VAE_bf16.safetensors` 直串）、`vae_precision`、`enable_vae_tiling`、`tiled_vae`、`tiled_vae_encode`、`tiled_vae_decode`；类 `WanVideoVAELoader` [高]。

**解码分块（[高]）**：`decode_tile_x`、`decode_tile_stride_x`、`decode_tile_y`、`decode_tile_stride_y`（校验见 §5）；类 `WanVideoDecode` [高]。

**多参考上下文 / 任务（仅部分）**：`reference_image_1..8`（8 个槽位直串 [高]）、`reference_video`、`source_video`、`ref_max_size`、`reference_count`、`reference_image_`（前缀拼接 [高]）。这些输入喂给后端 `WanAnimatePlusBernini`（`process`、`WANVIDIMAGE_EMBEDS`、`image_embeds`、`wan2.2_vae` 编码 in-context latents，`context_latents` 由后端 `nodes.py:2537` WanAnimatePlusBernini.process 输出 [高]）。

### 3.2 TEBerniniPromptEnhancer（提示词增强节点）

- FUNCTION = "enhance_prompt" [高]；RETURN_TYPES 已确认 `("STRING", "STRING")`、RETURN_NAMES 已确认 `("增强提示词(API)", "提示词模版(本地)")`（动态回填）——两个输出口分别对应 API 增强结果与本地模板文本。
- OUTPUT_NODE = true 已确认（动态回填）；`has_IS_CHANGED = true` 已确认（动态回填，用于缓存 [中]）。
- 输入 [高/中]：
  - `mode`（`prompt_mode`）：`本地` vs `API`（`增强提示词(API)`、`提示词模版(本地)`、`本地模板不依赖接口；API增强会调用 Responses API` tooltip [高]）
  - `user_prompt`（tooltip "输入原始提示词或简短需求" [高]）
  - `task_type`（tooltip "按 Bernini 的视频任务分类选择模板" [高]；选项 = BERNINI_TASK_OPTIONS，中文标签见下）
  - `template_text`（`提示词模版(本地)` 自定义模板覆盖 [中]）
  - `temperature`（tooltip "创意程度；如果服务端模型不支持，可调回默认或更低" [高]）
  - `max_output_tokens`（tooltip "最大输出 token，API 增强时使用" [高]）
  - `api_key`（tooltip "API Key；留空则读取 config.ini" [高]）、`api_base_url`/`api_url`（tooltip "服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses" [高]）、`model`（tooltip "Responses API 模型名称，按你的中转/服务端支持填写" [高]，默认 `gpt-5.5` 直串 [中]）、`timeout`（tooltip "请求超时时间（秒）" [高]）、`bypass_proxy`（tooltip "需要忽略系统代理/梯子时开启" [高]，`trust_env` 字符串佐证 [中]）
- 行为：`_bernini_local_prompt`（本地模板）或 `_post_responses`（Responses API，payload 含 `model`/`instructions`/`user_text`）→ `_extract_rewritten_text` 取 `rewritten_text`（官方模板要求 `Return ONLY a JSON object with one key: "rewritten_text"` [高]）。
- 有 `IS_CHANGED`（已确认 `has_IS_CHANGED=true`，动态回填），用于缓存 [中]。

### 任务分类（prompt enhancer 的 task_type 选项 [高]）

- `文生视频(t2v)` → `BERNINI_T2V_A14B_EN_SYS_PROMPT`（"电影导演"茶艺改写模板全文，见 §6）
- `图生视频(r2v)` → `BERNINI_R2V_TEMPLATE`（"subject-driven" image0/1 短指令+长指令模板 [高]）
- `视频改视频(v2v)` → `BERNINI_V2V_TEMPLATE`（"Task: Video Editing" V2V 模板 [高]）
- `动作迁移/参考改视频(rv2v)` → `BERNINI_VR2V_TEMPLATE`（reference-image-guided editing 模板 [高]）
- `大幅度动作改视频(mv2v)` → 模板常量名未在字符串中找到（未确认；动态回填证实：模块常量中确无 mv2v 独立模板，选项在 `BERNINI_TASK_OPTIONS` 中存在）
- `image_num` 字段 tooltip："仅用于 r2v/rv2v 官方增强模板里的 image_num 描述" [高]；动态回填：对应 required 参数 `参考图数量`（INT，default 1，min 1，max 8，step 1）

### 主节点"中文任务名 → 英文名"双语言参数（[高]）

`_get_input` 接受 `(kwargs, chinese_name, english_name)`，`chinese_name`/`english_name` 为独立字符串证据 [高]，节点参数支持中英文别名读取（兼容旧工作流 [低]）。

## 4. 外部依赖与副作用

### 网络（Responses API [高]）
- 端点拼接规则：接受 `https://api.xxx.com`、`.../v1`、`.../v1/responses` 三种形态，`_resolve_responses_url` 归一为 `/v1/responses`（tooltip 直串 + `"/v1"`、`"/v1/responses"`、`"/responses"` 字符串 [高]）
- 默认服务地址字符串：`https://tem.588186.xyz` [高]（作者自建中转；动态回填：确认即 Prompt Enhancer 节点 `api_base_url` 的出厂默认值）
- 认证：`Authorization: Bearer <key>`（`Bearer ` 串 [高]）；key 来源 = 节点输入 或 **config_manager**（`ConfigManager`、`get_effective_api_base_url`、`load_api_key`、`sanitize_api_key`、`CONFIG_MANAGER` 字符串 [高]）
- 请求：requests `Session`（`requests`、`Session`、`trust_env`、`validate=False` 未确认），JSON payload `{model, instructions, user_text, max_output_tokens}`/含 `temperature` [高]（`_build_responses_payload(model, instructions, user_text, max_output_tokens)` qualname）
- 仅当 mode=API 才有网络副作用；`mode=api, model=` 日志串 [高]

### 文件系统
- 延迟导入并注册 `te_bernini_backend` 包 → `sys` 注册为 `_te_image_bernini_backend_` [高]
- checkpoint 读取走 `folder_paths.get_filename_list` / `getlorapath`（`diffusion_models`、`text_encoders`、`vae_models`、`lora_models`、`gguf_models` 分类字符串 [高]），支持 GGUF 分片（`unet_gguf`、`gguf` [高]）
- 文本嵌入缓存：`use_text_disk_cache`/`use_disk_cache`、`WanVideoTextEmbedBridge` 未确认；`text_embed_cache` 目录于后端存在 [高]（te_bernini_backend/text_embed_cache/）

### 第三方库迹象
- `comfy.model_management`、`comfy` [高]；`model_management` [高]
- `hashlib`/`urandom`/`md5`（`hexdigest` [高]）：IS_CHANGED 键/缓存 [中]
- `importlib.machinery`、`ModuleSpec`、`import_module` [高]：动态包注册
- 后端类全名（与 pyd 字符串一一对应，均存在于 te_bernini_backend 源码 [高]）：`WanVideoModelLoader`、`WanVideoVAELoader`、`WanVideoTextEncodeCached`、`WanVideoSetLoRAs`、`WanVideoLoraSelectMulti`、`WanVideoSetBlockSwap`、`WanVideoSchedulerv2`、`WanVideoSamplerv2`、`WanVideoDecode`、`WanAnimatePlusBernini`

### 模型运行时（te_bernini_backend 提供的证据）
- 两阶段采样：HIGH 模型采 `high_samples`，LOW 模型采 `low_samples`（字符串 `high_samples`、`low_samples` [高]），最后解码输出
- `WanAnimatePlusBernini`（te_bernini_backend/nodes.py:2537）: VAE 编码 source_video/reference_video/reference_image_1..8 成 `context_latents`（"per-stream source_id RoPE" 注释 [高]）
- 后端改动注释（te_bernini_backend/nodes.py 头部版权）：Modified from kijai WanVideoWrapper，添加 prefix_frames、transition_video、canvas_expansion_px、WanAnimatePlus signature widget [高]

## 5. 错误处理与用户可见文案

| 消息（原文摘录） | 触发场景 |
|---|---|
| `TE Bernini-R 内置后端未找到，节点需要随 TE_image 一起发布 ` | `_resolve_backend_dir` 找不到 te_bernini_backend 目录 [高] |
| `TE Bernini-R 内置后端加载失败：` | `_import_backend_module` 导入异常 [高] |
| `TE Bernini-R: encoding text/loading HIGH noise model/building Bernini context latents/sampling HIGH stage/loading VAE/sampling LOW stage/loading LOW noise model/decoding samples/完成` | generate 各阶段进度日志 [高] |
| `TE Bernini-R: applying ... acceleration LoRA` / `-end | accel_lora=` | 挂加速 LoRA 日志 [高] |
| `TE Bernini-R 完成 | size=... | frames=... | steps=... | prompt=...` | 成功汇总日志（格式碎片拼接 [中]） |
| `低噪开始步不能大于步数` | 校验 `low_start_step` vs `steps` [高] |
| `高噪结束步不能大于步数` | 校验 `high_end_step` vs `steps` [高] |
| `解码分块X 必须大于 解码步长X` / `解码分块Y 必须大于 解码步长Y` | 校验 decode tile 参数 [高] |
| `请在 config.ini 中配置 API Key 或在节点中填写` / `请在 config.ini 中配置 API URL 或在节点中填写` | prompt enhancer API 模式缺 Key/URL [高] |
| `未配置有效的 API URL` | URL 归一化失败 [高] |
| `Responses API 请求失败：HTTP <code>` / `, endpoint=..., Body: ...` | HTTP 非 2xx [高] |
| `Responses API 返回的不是 JSON：` / `Responses API 返回 JSON 结构异常：` | 响应解析失败 [高] |
| `TE Bernini prompt enhancer: API 增强失败: ` / `TE Bernini prompt enhancer: API 未返回可用文本` / `TE Bernini prompt enhancer: API ...`（`TE Bernini prompt enhancer: task=..., mode=api, model=...`） | enhancer API 模式进度/失败 [高] |
| `用户原始 prompt: ...` | 本地改写日志 [高] |
| `bad video` | infer 输入视频无效 [中] |

## 6. 证据附录

### 6.1 模板常量与默认模型（直串）
```
BERNINI_T2V_A14B_EN_SYS_PROMPT / BERNINI_DEFAULT_SYSTEM_PROMPT
BERNINI_R2V_TEMPLATE / BERNINI_VR2V_TEMPLATE / BERNINI_V2V_TEMPLATE
BERNINI_TASK_OPTIONS / BERNINI_TASK_DISPLAY_TO_CODE / BERNINI_TASK_CODE_TO_LABEL
SCHEDULER_OPTIONS / ATTENTION_OPTIONS
DEFAULT_HIGH_ACCEL_LORA / DEFAULT_LOW_ACCEL_LORA / BACKEND_LORA_NONE / LORA_NONE
Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors
Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors
umt5-xxl-enc-fp8_e4m3fn.safetensors
Wan2_1_VAE_bf16.safetensors
Wan-Lighting\Wan2.2 - t2v_A14b_high_noise_lora_rank64_lightx2v_4step_1217.safetensors
Wan-Lighting\Wan2.2 - t2v_A14b_low_noise_lora_rank64_lightx2v_4step_1217.safetensors
https://tem.588186.xyz / https://api.xxx.com / gpt-5.5
```

### 6.2 t2v 官方中文系统提示词（`你是一位电影导演…` 全文要点 [高]）
- 时间/光源/光线强度/色调/光线角度/镜头尺寸/拍摄角度/构图 的有限枚举（"如果prompt没有特别说明则选 Day time!!!"、"默认选择Medium shot或Wide shot"、"若原始prompt中有运镜的描述，则取消添加此项"）
- 完善主体特征、背景细节；不加氛围文学描写；动作改写过程描述；2D 不加电影美学；天空改湛蓝；60-200 字全英文输出
- 附 4 条英文示例 prompt（含 "Anime-style thick-painted style" 例子）
- **包含 NSFW 规避转化指令（第 8/9/10 条：将特定内容替换为高美感 prompt，而非拒答）—— 逆向时仅作为字符串事实记录** [高]

### 6.3 r2v / v2v / rv2v 官方英文模板要点 [高]
- R2V（BERNINI_R2V_TEMPLATE）："Return ONLY a JSON object with one key: \"rewritten_text\""，Part 1 短指令 + Part 2 长指令，主体用 `image0/image1…` 指代，"Do NOT hallucinate details not visible in the images"
- V2V（BERNINI_V2V_TEMPLATE）：`Task: Video Editing`、Modifications+Preservations 两段式、"Concretization"（把模糊指代改为具体具名实体），含 15 条任务分类（Replacement/Addition/Removal/Subtitle Removal/Depth/Sketch/Colorization/Inpainting/Detection/Stylization/Mixed/Camera Movement/Perspective/Focus/Other）
- RV2V（BERNINI_VR2V_TEMPLATE）：前 3 帧为源视频帧（frame0..2）、后续为参考图（image0..），"no parentheses"、"English only"、单段改写指令 + 目标视频描述

### 6.4 输入/输出类型/可选字段碎片 [高]
```
IMAGE / STRING / BOOLEAN / FLOAT / INT / STRING_BIN
INPUT_TYPES / RETURN_TYPES / RETURN_NAMES / REQUIRED / OPTIONAL(未拆出) / OUTPUT_NODE / IS_CHANGED / FUNCTION / CATEGORY / tooltip / multiline / choices
reference_image_1..8 / reference_video / source_video / ref_img / ref_max_size / reference_count / image_num / image_embeds / num_frames / width / height
high_model / low_model / high_lora / low_lora / high_fp8 / low_fp8 / high_samples / low_samples
high_scheduler / low_scheduler / high_cfg / low_cfg / steps / shift / high_end_step / low_start_step / add_noise_to_samples / riflex_freq_index
text_encoder / text_embeds / text_precision / text_quantization / text_device / use_cpu_cache / use_disk_cache / use_text_disk_cache / negative_text_embeds? (_negative_text_embeds [高])
vae_model / vae_precision / wan2_1_vae / wan2.2_vae / wan_2.1_vae / wan_2.1_vae_confyui
decode_tile_x/y / decode_tile_stride_x/y / decode
attention_mode / rope_function / rms_norm_function / normalization / compile_args
blocks_to_swap / vace_blocks_to_swap / block_swap_blocks / block_swap_debug / block_swap_args / vram_management_args / prefetch_blocks / low_mem_load
lora_models / merge_loras / setlora / prev_lora / getlorapath / lora_name / strength / extra_model / extra_args
enable / enabled / disabled / prompt / negative_prompt / Prompt
seed ~~未确认~~ → 已确认：`种子`（INT，default 666，min 0，max 18446744073709551615，动态回填）
```

### 6.5 与明文后端对接的节点类（pyd 字符串 ↔ 后端源码位置   [高]）
| pyd 字符串 | te_bernini_backend 定义处 |
|---|---|
| WanVideoSetBlockSwap | nodes.py:51 |
| WanVideoTextEncodeCached | nodes.py:197 |
| WanVideoDecode | nodes.py:2319 |
| WanAnimatePlusBernini | nodes.py:2537 |
| WanVideoLoraSelectMulti | nodes_model_loading.py:502 |
| WanVideoSetLoRAs | nodes_model_loading.py:729 |
| WanVideoModelLoader | nodes_model_loading.py:1077 |
| WanVideoVAELoader | nodes_model_loading.py:1873 |
| WanVideoSamplerv2 | nodes_sampler.py:2891 |
| WanVideoSchedulerv2 | nodes_sampler.py:3030 |

### 6.6 未确认项清单（动态回填核对后状态）
- ~~节点注册键~~ **已确认**：`TE_Bernini_R_Generator` / `TE_Bernini_Prompt_Enhancer`（NODE_CLASS_MAPPINGS 常量实测，动态回填）
- `seed` / `generate_latents` 输入与随机种子处理 [低] → **部分证实**：主节点确有 `种子`（INT，default 666，min 0，max 18446744073709551615，无 step）输入（动态回填）；`generate_latents` 未见对应输入，内部处理仍未确认
- `negative_prompt` 默认值 → **已确认**：`负面提示词` STRING multiline，default `"bad video"`（动态回填）；前端 UI 挂载仍未在前端 JS 中证实 [低]
- 默认 `api_base_url` → **已确认**：`https://tem.588186.xyz` 即节点出厂默认（动态回填）
- `mv2v`（大幅度动作改视频）对应的模板常量名 [低] → 保留未确认：模块常量实测仅有 `BERNINI_R2V_TEMPLATE`、`BERNINI_V2V_TEMPLATE`、`BERNINI_VR2V_TEMPLATE`、`BERNINI_T2V_A14B_EN_SYS_PROMPT`、`BERNINI_DEFAULT_SYSTEM_PROMPT`，**无独立 mv2v 模板常量**（mv2v 选项存在于 `BERNINI_TASK_OPTIONS` 中，动态回填）

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 2025 Server + Python 3.13.16 + ComfyUI 真实加载后的运行时 introspection（module 显示为 `custom_nodes.TE_image.TE_Bernini_R_Generator`）。模块文件为 `TE_Bernini_R_Generator.pyd`。

### 7.1 TEBerniniRGenerator（TE_Bernini_R_Generator）——INPUT_TYPES 全表

- FUNCTION=`generate`；CATEGORY=`TE MAN/Bernini`；OUTPUT_NODE 未设置；`has_IS_CHANGED=false`、`has_VALIDATE_INPUTS=false`。
- RETURN_TYPES=`("IMAGE","STRING")`；RETURN_NAMES=`("图像","状态")`。
- required（22 项）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `高噪模型` | COMBO（动态文件列表，空回退 `[]`） | default=`Wan22_Bernini_HIGH_fp8_e4m3fn_scaled.safetensors` |
| `低噪模型` | COMBO（动态文件列表） | default=`Wan22_Bernini_LOW_fp8_e4m3fn_scaled.safetensors` |
| `VAE模型` | COMBO（动态文件列表） | default=`Wan2_1_VAE_bf16.safetensors` |
| `文本编码器` | COMBO（动态文件列表） | default=`umt5-xxl-enc-fp8_e4m3fn.safetensors` |
| `启用加速LoRA` | BOOLEAN | default=true |
| `高噪加速LoRA` | COMBO | 选项含 `无`，default=`无` |
| `高噪LoRA强度` | FLOAT | default 1.0，min -10.0，max 10.0，step 0.0001 |
| `低噪加速LoRA` | COMBO | 选项含 `无`，default=`无` |
| `低噪LoRA强度` | FLOAT | default 1.0，min -10.0，max 10.0，step 0.0001 |
| `提示词` | STRING | multiline=true，default="" |
| `负面提示词` | STRING | multiline=true，default=`bad video` |
| `宽度` | INT | default 832，min 16，max 8192，step 16 |
| `高度` | INT | default 480，min 16，max 8192，step 16 |
| `帧数` | INT | default 81，min 1，max 8192，step 4 |
| `种子` | INT | default 666，min 0，max 18446744073709551615（无 step） |
| `步数` | INT | default 8，min 1，max 1000 |
| `Shift` | FLOAT | default 5.0，min 0.0，max 1000.0，step 0.01 |
| `高噪CFG` | FLOAT | default 1.0，min 0.0，max 30.0，step 0.01 |
| `低噪CFG` | FLOAT | default 1.0，min 0.0，max 30.0，step 0.01 |
| `高噪结束步` | INT | default 4，min 1，max 1000 |
| `低噪开始步` | INT | default 4，min 0，max 1000 |
| `采样器` | COMBO | `["euler","unipc","dpm++","dpm++_sde","ddim","flowmatch_causvid"]`，default=`euler` |

- optional（20 项）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `源视频或源图` | IMAGE | — |
| `参考视频` | IMAGE | — |
| `参考图1`…`参考图8` | IMAGE ×8 | — |
| `参考图最大边` | INT | default 832，min 16，max 8192，step 16 |
| `模型精度` | COMBO | `["bf16","fp16","fp32","fp16_fast"]`，default=`bf16` |
| `模型量化` | COMBO | `["disabled","fp8_e4m3fn","fp8_e4m3fn_scaled","fp8_e4m3fn_fast","fp8_e4m3fn_scaled_fast","fp8_e5m2","fp8_e5m2_scaled","fp8_e5m2_fast","fp8_e5m2_scaled_fast"]`，default=`disabled` |
| `注意力模式` | COMBO | `["sageattn","sdpa","flash_attn_2","flash_attn_3","sageattn_3","radial_sage_attention","sageattn_compiled"]`，default=`sageattn` |
| `VAE精度` | COMBO | `["bf16","fp16","fp32"]`，default=`bf16` |
| `文本精度` | COMBO | `["bf16","fp32"]`，default=`bf16` |
| `文本量化` | COMBO | `["disabled","fp8_e4m3fn"]`，default=`fp8_e4m3fn` |
| `文本编码设备` | COMBO | `["gpu","cpu"]`，default=`gpu` |
| `强制卸载` | BOOLEAN | default=true |
| `BlockSwap块数` | INT | default 30，min 0，max 40，step 1 |

- 无 hidden 输入；无 tooltip 属性（UI 提示全部由中文参数名承担）。
- 对 §3.1 的更正：静态分析推断的 `width/height/num_frames/seed` 英文键名实为中文键 `宽度/高度/帧数/种子`；默认值实测：步数=8（非后端默认 30）、Shift=5.0、帧数=81、高/低噪结束/开始步=4、CFG=1.0。

### 7.2 TEBerniniPromptEnhancer（TE_Bernini_Prompt_Enhancer）——INPUT_TYPES 全表

- FUNCTION=`enhance_prompt`；CATEGORY=`TE MAN/Bernini`；**OUTPUT_NODE=true**；`has_IS_CHANGED=true`、`has_VALIDATE_INPUTS=false`。
- RETURN_TYPES=`("STRING","STRING")`；RETURN_NAMES=`("增强提示词(API)","提示词模版(本地)")`。
- required：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `输入提示词` | STRING | multiline=true，default=""，tooltip=`输入原始提示词或简短需求` |
| `任务类型` | COMBO | `["文生视频(t2v)","视频改视频(v2v)","大幅度动作改视频(mv2v)","动作迁移/参考改视频(rv2v)","图生视频(r2v)"]`，default=`文生视频(t2v)`，tooltip=`按 Bernini 的视频任务分类选择模板` |
| `增强方式` | COMBO | `["本地模板","API增强"]`，default=`本地模板`，tooltip=`本地模板不依赖接口；API增强会调用 Responses API` |
| `参考图数量` | INT | default 1，min 1，max 8，step 1，tooltip=`仅用于 r2v/rv2v 官方增强模板里的 image_num 描述` |
| `api_key` | STRING | default=""，tooltip=`API Key；留空则读取 config.ini` |
| `api_base_url` | STRING | default=`https://tem.588186.xyz`，tooltip=`服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses` |
| `model` | STRING | default=`gpt-5.5`，tooltip=`Responses API 模型名称，按你的中转/服务端支持填写` |
| `max_output_tokens` | INT | default 2048，min 256，max 32768，step 256，tooltip=`最大输出 token，API 增强时使用` |
| `temperature` | FLOAT | default 0.7，min 0.0，max 2.0，step 0.05，tooltip=`创意程度；如果服务端模型不支持，可调回默认或更低` |

- optional：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `timeout_s` | INT | default 300，min 30，max 1800，tooltip=`请求超时时间（秒）` |
| `绕过代理` | BOOLEAN | default=false，tooltip=`需要忽略系统代理/梯子时开启` |

- 无 hidden 输入。

### 7.3 模块常量实锤值（modules["TE_MAN.TE_Bernini_R_Generator"].constants）

| 常量 | 实测值 |
|---|---|
| `ATTENTION_OPTIONS` | `["sageattn","sdpa","flash_attn_2","flash_attn_3","sageattn_3","radial_sage_attention","sageattn_compiled"]` |
| `SCHEDULER_OPTIONS` | `["euler","unipc","dpm++","dpm++_sde","ddim","flowmatch_causvid"]` |
| `BACKEND_DIR_NAME` | `"te_bernini_backend"` |
| `BACKEND_LORA_NONE` | `"none"`；`LORA_NONE` = `"无"` |
| `BERNINI_DEFAULT_SYSTEM_PROMPT` | `"You are a helpful assistant."` |
| `DEFAULT_HIGH_ACCEL_LORA` | `"Wan-Lighting\\Wan2.2 - t2v_A14b_high_noise_lora_rank64_lightx2v_4step_1217.safetensors"` |
| `DEFAULT_LOW_ACCEL_LORA` | `"Wan-Lighting\\Wan2.2 - t2v_A14b_low_noise_lora_rank64_lightx2v_4step_1217.safetensors"` |
| `BERNINI_TASK_OPTIONS` | `["文生视频(t2v)","视频改视频(v2v)","大幅度动作改视频(mv2v)","动作迁移/参考改视频(rv2v)","图生视频(r2v)"]` |
| `BERNINI_TASK_DISPLAY_TO_CODE` | `{"文生视频(t2v)":"t2v","视频改视频(v2v)":"v2v","大幅度动作改视频(mv2v)":"mv2v","动作迁移/参考改视频(rv2v)":"rv2v","图生视频(r2v)":"r2v"}`（`BERNINI_TASK_CODE_TO_LABEL` 为其逆映射） |
| `BERNINI_R2V_TEMPLATE` | subject-driven 双段指令模板（Part 1 短指令 + Part 2 长指令，占位符 `{image_num}`、`{original_text}`，要求返回 `{"rewritten_text": …}` JSON） |
| `BERNINI_V2V_TEMPLATE` | `Task: Video Editing` 模板（含 15 条任务分类，占位符 `{user_prompt}`） |
| `BERNINI_VR2V_TEMPLATE` | reference-image-guided editing 模板（前 3 帧 frame0-2 源视频 + `{image_num}` 张参考图） |
| `BERNINI_T2V_A14B_EN_SYS_PROMPT` | "你是一位电影导演…" 中文电影美学改写系统提示词（与 §6.2 一致，含第 8/9/10 条 NSFW 规避转化指令） |
| `NODE_CLASS_MAPPINGS` | `{"TE_Bernini_R_Generator": TEBerniniRGenerator, "TE_Bernini_Prompt_Enhancer": TEBerniniPromptEnhancer}` |
| `NODE_DISPLAY_NAME_MAPPINGS` | `{"TE_Bernini_R_Generator": "TE MAN Bernini", "TE_Bernini_Prompt_Enhancer": "TE MAN Bernini 提示词增强(本地orAPI)"}` |
| `_WAN_CACHE` | `{}`（进程级后端节点类缓存） |

### 7.4 对正文其他推断的核对结论

| 正文位置 | 结论 |
|---|---|
| §3.1 RETURN_TYPES `("IMAGE",)` [中] | 已确认，实为 `("IMAGE","STRING")` + 名称 `图像/状态`（动态回填） |
| §3.2 `mode`（`prompt_mode`）参数名 | 不成立：实测键名为 `增强方式`，选项为 `本地模板`/`API增强`（非"本地/API"） |
| §3.2 `user_prompt` 参数名 | 不成立：实测键名为 `输入提示词` |
| §3.2 `task_type` 参数名 | 不成立：实测键名为 `任务类型`；`template_text` 亦不存在于 INPUT_TYPES（本地模板直接从第二输出口输出） |
| §3.2 `timeout`/`bypass_proxy` 参数名 | 实测键名为 `timeout_s` / `绕过代理`（动态回填） |
| §3.2 model 默认 `gpt-5.5` [中] | 已确认（动态回填） |
| §3.2 `image_num` 字段 tooltip | 已确认：对应 required 参数 `参考图数量`（default 1，min 1，max 8） |
| §2 "Bernini-R 主节点为输出节点" | 更正：OUTPUT_NODE=true 属于 Prompt Enhancer 节点 |
| §6.4 "seed 未确认" | 已确认：`种子` INT default 666（动态回填） |
| §6.4 "negative_prompt" | 已确认：`负面提示词` default `bad video`（与 §5 "bad video" 的 [中] 推断"infer 输入视频无效"不同——实为负面提示词默认值，动态回填） |
