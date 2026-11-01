# TE_MAN_Text_Tools.pyd 逆向规格

> 来源：PE32+ x86-64 Windows DLL，Cython 3.1.2 limited API (abi3) 编译（`_cython_3_1_2limited_fastcallnofinalize` 字符串），入口 `PyInit_TE_MAN_Text_Tools`。仅依赖 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / api-ms-win-crt-runtime（无 WS2_32——HTTP 走 Python 侧 `requests`）。静态分析（导入导出表 + ASCII/UTF-8 字符串 + objdump 局部反汇编核对）。
> 置信度说明：[高] = 字符串/导入/反汇编直接证据；[中] = 强暗示推断；[低] = 猜测；无法确定写"未确认"。
> 编译源路径 [高]：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_MAN_Text_Tools.c` ← 源文件 `custom_nodes/TE_image/source_py_backup/TE_MAN_Text_Tools.py`，模块限定名 `custom_nodes.TE_image.TE_MAN_Text_Tools`（插件前身包名 TE_image）。

## 1. 模块定位

这是 TE_MAN（前身 TE_image）插件中 README「**文本工具节点**」（v3.x 更新日志标题：「TE MAN 文本工具节点更新…面向提示词扩写、分镜生成和视频提示词优化」段落）对应的 ComfyUI 节点模块：内置 OpenAI 兼容 **Responses API** 文本调用链，把用户一句描述按 4 种「快捷功能」生成——生图提示词扩写、生视频提示词优化、9 段九宫格（3x3）分镜中文提示词、自定义命令处理。`__init__.py` 不在 SKIP_MODULES 中，会被节点加载器自动加载。

## 2. Python API

- 导出：`PyInit_TE_MAN_Text_Tools`（导出表唯一符号）[高]
- Python 侧依赖 [高，符号字符串]：`requests`（`Session`、`post`、`headers`、`timeout`、`trust_env`）、`re`（`IGNORECASE`、`search`）、`json`（`loads`、`dumps`）、`typing`（`Optional`、`Dict`、`Tuple`、`List`、`Any`）、`comfy`/`comfy.model_management`、`inspect`（Cython 代码对象自省）、本地支撑库 `config_manager`（`ConfigManager`，模块内符号 `CONFIG_MANAGER`、`load_api_key`、`get_effective_api_base_url`、`sanitize_api_key`）、`logger`。
- 类 `TEMANTextToolsNode` [高，符号字符串]；方法 [高]：
  - `INPUT_TYPES`（classmethod，qualname `TEMANTextToolsNode.INPUT_TYPES`）
  - `IS_CHANGED`
  - `process_text`（qualname `TEMANTextToolsNode.process_text`）
- 模块级私有函数（qualname 全部为 `custom_nodes.TE_image.TE_MAN_Text_Tools.*`）[高]：
  - `_ensure_not_interrupted(throw_exception_if_processing_interrupted)` — 中断检测（配合 `comfy.model_management`）[高，符号]
  - `_resolve_responses_url(api_base_url)`、`_resolve_key_and_url(api_key)`、`_read_json_response_or_raise(resp)`、`_extract_output_text(response_data)`（含 genexpr）、`_strip_json_code_fence(text)`、`_parse_json_object(text)`、`_extract_storyboard_prompts(parsed)`、`_pretty_json(parsed)`、`_base_quality_tags(style_hint)`、`_build_storyboard_instructions(aspect_ratio)`、`_build_image_prompt_instructions(output_language)`、`_build_video_prompt_instructions(output_language)`、`_build_instructions(quick_function, ...)`、`_build_user_text(input_text, custom_command, ...)`、`_build_responses_payload(model, instructions, user_text, max_output_tokens, ...)`、`_post_responses(endpoint, payload, timeout_s, ...)`
  - 常量 [高，符号字符串]：`QUICK_FUNCTION_OPTIONS`、`QUICK_FUNCTION_CUSTOM`、`QUICK_FUNCTION_IMAGE_PROMPT`、`QUICK_FUNCTION_VIDEO_PROMPT`、`QUICK_FUNCTION_STORYBOARD_9`、`MODULE_DIR`、`PLUGIN_DIR`
- 节点注册 [高]：
  - `NODE_CLASS_MAPPINGS` 键：**`TE_image_pro_text_tools`**
  - `NODE_DISPLAY_NAME_MAPPINGS`：**`TE MAN Text文本处理`**
  - `CATEGORY`：**`TE MAN/Text`**；`FUNCTION`：**`process_text`**；`OUTPUT_NODE` 存在（字符串 `OUTPUT_NODE`）[高]（无 `OUTPUT_NODE` 布尔值证据，推测为 True [低]）

签名与参数名（objdump 反汇编：`process_text` 前导对每个参数做 `PyUnicode_Type`/`PyLong_Type` 匹配 + `__Pyx_ArgTypeTest` 风格报错，.getParam(type_check helper @0x180011ca0) 传入的参数名字符串直接可见）[高]：

- str 型参数（0x180018328 = `PyUnicode_Type` 判定）[高]：`输入文本`、`快捷功能`、`api_key`、`api_base_url`、`model`、`画面比例`、`输出语言`、`快捷功能自定义`
- int 型参数（0x180018220 = `PyLong_Type` 判定）[高]：`max_output_tokens`、`seed`、`timeout_s`
- float 型参数 [高]：`temperature`（唯一走 `PyFloat_AsDouble` + 默认值双精度常量 0x3FE6666666666666 = **0.7** 的参数，反汇编 0x18000bc74–0x18000bcb0 等）
- 另有未在类型检查序列直出的参数（如 `绕过代理`、`style_hint`），未确认其是否同为 process_text 形参，还是仅在节点部件/其它函数使用 [低]。

## 3. 节点规格（TE MAN Text文本处理 / TE_image_pro_text_tools）

说明：下表参数名 = INPUT_TYPES / process_text 形参名（反汇编直接证据 [高]）；「UI 标签」列中，`输入文本 / 快捷功能 / 画面比例 / 输出语言 / 快捷功能自定义` 本身即参数名（同时也是中文名）；`绕过代理` 为参数 `bypass_proxy` 的可见标签字符串 [中]（`label` 字段字符串存在与否未确认，标签与参数可能同名）。

| 参数 | 推断类型 | 默认值/选项 | tooltip（原文摘录） | 证据 |
|---|---|---|---|---|
| `输入文本` | STRING（multiline=True 概率高 [中]，字符串 `multiline`） | 示例占位文本「一个穿红色旗袍的女性站在雨夜霓虹街道，手持折扇，电影感光影」[中，默认值候选字符串] | 「输入剧情、简短提示词或需要处理的文本」 | [高] |
| `快捷功能` | COMBO | 选项（中文显示值）[高]：「扩写生图提示词」「扩写生视频提示词」「9段分镜提示词」「自定义」；内部常量键 [高]：`QUICK_FUNCTION_IMAGE_PROMPT` / `QUICK_FUNCTION_VIDEO_PROMPT` / `QUICK_FUNCTION_STORYBOARD_9` / `QUICK_FUNCTION_CUSTOM`（中文值↔常量键的映射关系 未确认） | 「选择要执行的一次性文本处理功能」 | [高] |
| `画面比例` | COMBO | `1:1, 16:9, 9:16, 4:3, 3:4, 5:4, 4:5, 21:9, 9:21`（字符串字面量齐全） | 「主要用于 9段分镜 的 grid_aspect_ratio 和提示词方向」 | [高] |
| `输出语言` | COMBO | `中文`、`English`（其余选项 未确认） | 「控制非 9 段分镜功能的输出语言；9 段分镜固定中文」 | [高] |
| `快捷功能自定义` | STRING（可能带 `forceInput` [低]，字符串 `forceInput` 存在） | 无 | 「快捷功能选择“自定义”时生效；输入内容会添加到用户提示词前面」 | [高] |
| `style_hint` | STRING（风格提示，未确认是否为独立输入参数） | 未确认（字符串 `style_hint`、独立 `Cinematic` 字样存在，用于 `_base_quality_tags` 与「，风格：」拼接 [中]） | 未确认 | [中] |
| `temperature` | FLOAT | 0.7（双精度常量）[中]；提示「创意程度；如果服务端模型不支持，可调回默认或更低」 | [高] |
| `max_output_tokens` | INT | 未确认（tooltip「最大输出 token，9段分镜建议 4096 或更高」，4096 是否为默认值 未确认） | [高] |
| `timeout_s` | INT（反汇编按 PyLong 判定） | 未确认（tooltip「请求超时时间（秒）」） | [高] |
| `seed` | INT（PyLong [高]，带 `control_after_generate` 字段 [高]） | 未确认 | 「仅用于 ComfyUI 触发重新执行，不会写入请求体」 | [高] |
| `model` | STRING | 默认候选 `gpt-5.5` [中，字符串存在；是否默认值未确认] | 「Responses API 模型名称，按你的中转/服务端支持填写」 | [高] |
| `api_key` | STRING | 空→读 config.ini | 「API Key；留空则读取 config.ini」 | [高] |
| `api_base_url` | STRING | 空→读 config.ini | 「服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses」 | [高] |
| `bypass_proxy` | BOOLEAN（`BOOLEAN` 字符串） | False [低] | 「需要忽略系统代理/梯子时开启」（标签「绕过代理」） | [中] |

required / optional 分组归属 未确认（分组键字符串后未锁定到具体条目）；`IS_CHANGED` 的实现语义（是否仅哈希输入用于缓存失效）未确认 [低]。
与显示名相邻的字符串 `文本输出`、`快捷功能` 等（0x1a010 区），以及返回候选名 `text_output` / `prompt_text` / `json_output` / `storyboard_prompts` / `output_text`（符号字符串 [高）]

**返回值**：`RETURN_TYPES` / `RETURN_NAMES` 存在 [高]；模块初始化处存在 `PyTuple_Pack(2, ...)` 构造的若干二元组（objdump 0x1800eca0/0x1800ecc5/0x1800ecee，未能静态解出成员）→ 推断返回为 **2 元组 STRING** [低]，候选输出名从符号字符串取：`text_output`、`prompt_text`、`json_output`、`storyboard_prompts`（9 分镜时逐条提示词）[中]。确切成员 未确认。

### process_text 行为流（按 helper 名序 + 消息串重建）

1. `_ensure_not_interrupted(throw_exception_if_processing_interrupted)`：ComfyUI 中断时抛出（`comfy.model_management` 字符串佐证）[中]。
2. `_resolve_key_and_url`：`api_key` 为空 → 从 `ConfigManager.load_api_key()`（config.ini `[gemini] api_key`，见 spec/config_manager.md）读取；`api_base_url` 为空 → `get_effective_api_base_url()`。报错文案：「请在 config.ini 中配置 API Key 或在节点中填写」「请在 config.ini 中配置 API URL 或在节点中填写」「未配置有效的 API URL」[高]。
3. `_resolve_responses_url`：把 base URL 规整成 Responses 端点（字符串 `/v1`、`/responses`、`/v1/responses` 三件套 + tooltip「可填到 /v1 或 /v1/responses」互证）[高]。
4. `_build_instructions(快捷功能)` 按快捷功能分发系统指令（全文见 §5/§6）：
   - 扩写生图提示词：好莱坞电影摄影指导人设 + 「八维精细化脑补」扩充准则 + 示例 + 「输出结构（严格遵守）…一篇字数在500字左右的中文详细扩充描述…」[高]
   - 扩写生视频提示词：「你是生视频提示词优化专家」+ 4 条要求（保留主体/明确动作/避免冲突动作/输出语言）[高]
   - 9段分镜提示词：「你是九宫格(3x3)分镜提示词专家」+ 视觉锁定/特定镜头强化/随机排列/纯净 JSON 输出 + 镜头变量库（景别/视角/构图白名单）+ 硬性约束（9 镜精确含 2 Back View、2 OTS、2 POV、2 Front View、1 高张力视角；禁用 Medium Shot/Long Shot/Close-up；prompt_text 必须中文；shots 恰 9 项，shot_number「分镜1」~「分镜9」）+ 固定输出 JSON 模板（`grid_layout: "3x3"`、`grid_aspect_ratio` ←`画面比例`、`global_watermark` `position: bottom_center / size: small`）[高]
   - 自定义：用户前置命令 + 「请严格按照用户输入开头的自定义命令处理后续文本。」；自定义命令为空时报「快捷功能选择“自定义”时，请连接“快捷功能自定义”并输入自定义命令」[高]
5. `_build_user_text`：用户文本为主体；自定义命令加在最前 [高]；9 分镜时附加「请将下面内容作为固定视觉锚点 Base_Prompt。每个 prompt_text 都必须保留这些核心视觉锚点并生成九宫格分镜。Base_Prompt: <输入文本>」[高]；无输入时默认指令「请根据当前快捷功能完成文本处理。」[中]。
6. `_build_responses_payload` + `_post_responses`：`requests.Session` POST `{base}/v1/responses`，头 `Content-Type: application/json`、`Authorization: Bearer <key>`；`绕过代理` 开启时 `Session.trust_env = False` 忽略系统代理（`trust_env` 符号 + tooltip 互证）[高]；载荷含 `model`、`instructions`、`input/user_text`、`temperature`、`max_output_tokens`（字段名与函数参数一致；`seed` 明确不进请求体 [高，tooltip]）。`model` 为空报「请填写 model」[高]。日志（TE_MAN logger）：`TE MAN Text文本处理: function=<快捷功能>, model=<model>, endpoint=<端点>, Body: <载荷>` [高]。
7. `_read_json_response_or_raise`：非 2xx → `Responses API 请求失败：HTTP <status_code>`（含 `, Body: ` / `<empty body>` 调试摘录）[高]；非 JSON → `Responses API 返回的不是 JSON：<body>` [高]。
8. `_extract_output_text`：从标准 Responses 结构 `output` 数组（`type`/`content`/`text`/`output_text` 符号字符串）提取文本；缺文本 → `Responses API 未返回可用文本：` / `Responses API 返回 JSON 结构异常：` [高]。
9. 文本后处理：`_strip_json_code_fence`（正则 `` ```(?:json)?\s*([\s\S]*?)\s*``` ``，`IGNORECASE`）+ `_parse_json_object`；仅 9 分镜走 `_extract_storyboard_prompts`：读取 `shots[].prompt_text`（`shot_number`「分镜1」~「分镜9」校验，json.loads/`shots` 符号互证），输出 9 条中文分镜提示词；`_pretty_json`（`indent=2` + `ensure_ascii=False` 符号）生成可展示 JSON 字符串 [中]。
10. 返回提示词/JSON 文本（见上）。

## 4. 外部依赖与副作用

- **网络** [高]：OpenAI 兼容 **Responses API**（`POST {base}/v1/responses`，`content`/`output` 结构解析）；服务地址可指向任意中转/自建站，如 `https://api.xxx.com`（原文）；认证 `Authorization: Bearer <API Key>`。
- **代理** [中]：`bypass_proxy` 开启时 requests `Session.trust_env=False`；未开启则默认走系统代理。
- **文件系统** [高]：无直接读写；经 `config_manager` 读 `<模块目录>/config.ini`（`[gemini] api_key` / `api_base_url`，参见 spec/config_manager.md）。
- **第三方库** [高]：`requests`；ComfyUI 内部 `comfy.model_management`（中断检测）[中]。
- 无 API Key 加解密、无图片编解码、无磁盘输出（无 base64/XOR/编码类符号，与 config_manager 的 obfuscation 无交叉）[高]。

## 5. 错误处理与用户可见文案

| 消息 | 触发场景 |
|---|---|
| 「请在 config.ini 中配置 API Key 或在节点中填写」 | api_key 留空且配置无 Key [高] |
| 「请在 config.ini 中配置 API URL 或在节点中填写」 | api_base_url 留空且配置无 URL [高] |
| 「未配置有效的 API URL」`RuntimeError` | URL 规整失败 [高] |
| 「请填写 model」`ValueError` | model 为空 [高] |
| 「Responses API 请求失败：HTTP <code>」 | HTTP 非 2xx（含 `Body:` 摘录，空体记 `<empty body>`）[高] |
| 「Responses API 返回的不是 JSON：<body>」 | 响应体不可解析 [高] |
| 「Responses API 未返回可用文本：」 | Responses 结构中无 output_text [高] |
| 「Responses API 返回 JSON 结构异常：」 | JSON 解析/结构不符 [高] |
| 「快捷功能选择“自定义”时，请连接“快捷功能自定义”并输入自定义命令」 | 自定义功能未接自定义命令 [高] |
| 日志 `TE MAN Text文本处理: function=..., model=..., endpoint=..., Body: ...` | 每次请求前的 logger 输出 [高] |

## 6. 证据附录（关键字符串原样摘录，分组去噪）

**模块/节点注册**
```
custom_nodes/TE_image/source_py_backup/TE_MAN_Text_Tools.py
TE_image_pro_text_tools / TE MAN Text文本处理 / TE MAN/Text
process_text / INPUT_TYPES / IS_CHANGED / FUNCTION / CATEGORY / RETURN_TYPES / RETURN_NAMES / OUTPUT_NODE
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / CONFIG_MANAGER
```

**配置/网络**
```
requests / Session / post / headers / Content-Type / application/json
Authorization / "Bearer " / trust_env / timeout / compact / status_code
/v1  /responses  /v1/responses
config.ini  API Key  API URL
```

**快捷功能与 UI**
```
QUICK_FUNCTION_OPTIONS / QUICK_FUNCTION_IMAGE_PROMPT / QUICK_FUNCTION_VIDEO_PROMPT
QUICK_FUNCTION_STORYBOARD_9 / QUICK_FUNCTION_CUSTOM
扩写生图提示词  扩写生视频提示词  9段分镜提示词  自定义
输入文本  快捷功能  画面比例  输出语言  快捷功能自定义  绕过代理
1:1 16:9 9:16 4:3 3:4 5:4 4:5 21:9 9:21
中文  English  multiline  forceInput  control_after_generate  required  optional
一个穿红色旗袍的女性站在雨夜霓虹街道，手持折扇，电影感光影
```

**9 段分镜 JSON 模板（含占位的完整片段）**
```
{
  "grid_layout": "3x3",
  "grid_aspect_ratio": "<画面比例>",
  "global_watermark": {
    "position": "bottom_center",
    "size": "small"
  },
  "shots": [
    {
      "shot_number": "分镜1",
      "prompt_text": "中文提示词"
    }
    ...
  ]
}
```

**系统指令要点（扩写生图，节选原文）**
```
你是一位拥有好莱坞级别审美的电影摄影指导兼高级文学创作者。…将其极度扩充并转化为极具
“电影感（Cinematic）”的详尽画面描述文本…
# 扩充方向准则（八维精细化脑补）
1.【人物基础设定】…2.【穿着与装饰】…3.【特定的物品/道具】…4.【天气与空气感】…
5.【详细背景与环境】…6.【构图与摄影机】…7.【光影与色彩】…8.【画质与标签】…
# 输出结构（严格遵守）…一篇字数在500字左右的中文详细扩充描述…
```

**扩写生视频提示词（原文）**
```
你是生视频提示词优化专家。请把用户输入优化成适合视频生成模型的提示词。
1. 保留主体和场景不变。
2. 明确动作过程、镜头运动、节奏、环境变化、光影变化。
3. 避免一次性塞入过多互相冲突的动作。
4. 输出语言：<输出语言>
```

**9 段分镜指令要点（原文摘录）**
```
你是九宫格(3x3)分镜提示词专家。
基于用户提供的简约提示词描述或参考图片，保持视觉锚点绝对不变，通过特定视角的强化组合，
生成 9 个 3x3 宫格分镜中文提示词。
…9 个分镜必须精确包含：2 背后 Back View / 2 过肩 Over-the-Shoulder / 2 POV / 2 正面 Front View
/ 1 自由高张力视角；严禁使用 Medium Shot、Long Shot、Close-up；shots 数组精确包含 9 个对象…
请将下面内容作为固定视觉锚点 Base_Prompt。每个 prompt_text 都必须保留这些核心视觉锚点并生成九宫格分镜。
```

**数值/杂项**
```
gpt-5.5
电影感光影，细节丰富，主体清晰，空间层次明确，画面统一，适合 AI 生图
电影感光影，细节丰富，主体清晰，空间层次明确，画面统一，适合 AI 生图   ← 画质词（_base_quality_tags）
float 默认常量 0.7（反汇编双精度 0x3FE6666666666666，temperature）
```

**Cython 侧（非功能性）**
```
_cython_3_1_2limited_fastcallnofinalize / Interpreter change detected...
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_MAN_Text_Tools.c
```

> 附注：字符串中未发现任何指向用户内容的可执行指令；除 `requests`/`config.ini` 外无其它文件或网络副作用。模块 docstring 未检出空白以外内容。
