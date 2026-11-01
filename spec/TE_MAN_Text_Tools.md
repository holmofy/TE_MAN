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
  - `CATEGORY`：**`TE MAN/Text`**；`FUNCTION`：**`process_text`**；**已确认：`OUTPUT_NODE = True`（动态回填）**

签名与参数名（objdump 反汇编：`process_text` 前导对每个参数做 `PyUnicode_Type`/`PyLong_Type` 匹配 + `__Pyx_ArgTypeTest` 风格报错，.getParam(type_check helper @0x180011ca0) 传入的参数名字符串直接可见）[高]：

- str 型参数（0x180018328 = `PyUnicode_Type` 判定）[高]：`输入文本`、`快捷功能`、`api_key`、`api_base_url`、`model`、`画面比例`、`输出语言`、`快捷功能自定义`
- int 型参数（0x180018220 = `PyLong_Type` 判定）[高]：`max_output_tokens`、`seed`、`timeout_s`
- float 型参数 [高]：`temperature`（唯一走 `PyFloat_AsDouble` + 默认值双精度常量 0x3FE6666666666666 = **0.7** 的参数，反汇编 0x18000bc74–0x18000bcb0 等）
- 另有未在类型检查序列直出的参数：**`绕过代理` 已确认为 INPUT_TYPES optional 参数（BOOLEAN，默认 False，动态回填）**；`style_hint` **已确认不在运行时 INPUT_TYPES 中（动态回填）**——它只是内部 helper（`_base_quality_tags`）的形参，非节点输入。

## 3. 节点规格（TE MAN Text文本处理 / TE_image_pro_text_tools）

说明：下表参数名 = INPUT_TYPES / process_text 形参名（反汇编直接证据 [高]；**required/optional 分组与全部默认值已由动态 introspection 实锤，全表见 §7.1**）；「UI 标签」列中，`输入文本 / 快捷功能 / 画面比例 / 输出语言 / 快捷功能自定义 / 绕过代理` 均直接就是 INPUT_TYPES 的中文参数键名（动态回填，不存在 `label` 转换层）。

| 参数 | 推断类型 | 默认值/选项 | tooltip（原文摘录） | 证据 |
|---|---|---|---|---|
| `输入文本` | STRING（required，**已确认 multiline=True**，动态回填） | **已确认：默认值即示例占位文本「一个穿红色旗袍的女性站在雨夜霓虹街道，手持折扇，电影感光影」**（动态回填） | 「输入剧情、简短提示词或需要处理的文本」 | [高] |
| `快捷功能` | COMBO（required） | **已确认**选项精确顺序：`9段分镜提示词`、`扩写生图提示词`、`扩写生视频提示词`、`自定义`（4 项，**默认 `9段分镜提示词`**）；常量映射实锤：`QUICK_FUNCTION_STORYBOARD_9="9段分镜提示词"`、`QUICK_FUNCTION_IMAGE_PROMPT="扩写生图提示词"`、`QUICK_FUNCTION_VIDEO_PROMPT="扩写生视频提示词"`、`QUICK_FUNCTION_CUSTOM="自定义"`（动态回填） | 「选择要执行的一次性文本处理功能」 | [高] |
| `画面比例` | COMBO（required） | **已确认**选项精确顺序：`16:9, 9:16, 1:1, 4:3, 3:4, 4:5, 5:4, 21:9, 9:21`（9 项，**默认 `16:9`**，早先按字符串序排的 1:1 在前不成立） | 「主要用于 9段分镜 的 grid_aspect_ratio 和提示词方向」 | [高] |
| `输出语言` | COMBO（required） | **已确认：仅 `中文`、`English` 两项**（默认 `中文`），无其余选项（动态回填） | 「控制非 9 段分镜功能的输出语言；9 段分镜固定中文」 | [高] |
| `快捷功能自定义` | STRING（optional，**已确认 forceInput=True**，动态回填） | 无 | 「快捷功能选择“自定义”时生效；输入内容会添加到用户提示词前面」 | [高] |
| `style_hint` | STRING（风格提示） | **已确认：非节点输入参数**（动态回填）——字符串 `style_hint`、`Cinematic` 属内部 `_base_quality_tags(style_hint)` helper 形参与「，风格：」拼接 | — | 已闭合 |
| `temperature` | FLOAT（required） | **已确认：默认 0.7，min 0.0 / max 2.0 / step 0.05**（动态回填）；提示「创意程度；如果服务端模型不支持，可调回默认或更低」 | [高] |
| `max_output_tokens` | INT（required） | **已确认：默认 4096，min 256 / max 32768 / step 256**（动态回填，tooltip 建议 4096 即默认） | [高] |
| `timeout_s` | INT（**optional**，动态回填） | **已确认：默认 300，min 30 / max 1800** | 「请求超时时间（秒）」 | [高] |
| `seed` | INT（**optional**，PyLong [高]） | **已确认：默认 -1，min -1 / max 2147483647，`control_after_generate: true`**（动态回填） | 「仅用于 ComfyUI 触发重新执行，不会写入请求体」 | [高] |
| `model` | STRING（required） | **已确认：默认 `gpt-5.5`**（动态回填） | 「Responses API 模型名称，按你的中转/服务端支持填写」 | [高] |
| `api_key` | STRING（required） | 默认 `""`，空→读 config.ini | 「API Key；留空则读取 config.ini」 | [高] |
| `api_base_url` | STRING（required） | 默认 `""`，空→读 config.ini | 「服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses」 | [高] |
| `绕过代理` | BOOLEAN（**optional**；参数键名即中文 `绕过代理`，动态回填） | **已确认：默认 False** | 「需要忽略系统代理/梯子时开启」 | [高] |

**已确认：required 分组 = `输入文本`、`快捷功能`、`api_key`、`api_base_url`、`model`、`画面比例`、`输出语言`、`max_output_tokens`、`temperature`；optional 分组 = `seed`、`timeout_s`、`绕过代理`、`快捷功能自定义`（动态回填，全表见 §7.1）**。`IS_CHANGED` 存在于节点（`has_IS_CHANGED = True`，动态回填）；其实现语义（是否仅哈希输入用于缓存失效）仍未确认。
与显示名相邻的字符串 `文本输出`、`快捷功能` 等（0x1a010 区），以及返回候选名 `text_output` / `prompt_text` / `json_output` / `storyboard_prompts` / `output_text`（符号字符串 [高]）

**返回值**：**已确认：`RETURN_TYPES = ("STRING", "STRING")`，`RETURN_NAMES = ("text", "json")`（动态回填）**——`json_output` 候选与实际口名 `json` 接近，`text_output`/`prompt_text`/`storyboard_prompts` 候选不成立（9 分镜的逐条提示词走 `text`/`json` 两个口输出）。

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

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows Server 2025 + ComfyUI（Python 3.13.16）真实环境 import 后的自省结果；运行时模块显示为 `custom_nodes.TE_image.TE_MAN_Text_Tools`（`TE_image` 为插件原名），模块文件 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN\TE_MAN_Text_Tools.pyd`。本节所有值均为运行时实锤。

### 7.1 节点 INPUT_TYPES 全表（实锤）

#### TE_image_pro_text_tools（TEMANTextToolsNode）

注册元数据：`FUNCTION = "process_text"`、`CATEGORY = "TE MAN/Text"`、`OUTPUT_NODE = True`、`RETURN_TYPES = ["STRING", "STRING"]`、`RETURN_NAMES = ["text", "json"]`；**`has_IS_CHANGED = True`**、无 VALIDATE_INPUTS / on_execute / check_lazy_status、无节点级 DESCRIPTION。显示名（node_display_name_mappings）：`TE MAN Text文本处理`。

**required**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `输入文本` | STRING, multiline | — | 一个穿红色旗袍的女性站在雨夜霓虹街道，手持折扇，电影感光影 | 输入剧情、简短提示词或需要处理的文本 |
| `快捷功能` | COMBO | `9段分镜提示词` / `扩写生图提示词` / `扩写生视频提示词` / `自定义`（4 项，此为精确顺序） | `9段分镜提示词` | 选择要执行的一次性文本处理功能 |
| `api_key` | STRING（单行） | — | `""` | API Key；留空则读取 config.ini |
| `api_base_url` | STRING（单行） | — | `""` | 服务地址，如 https://api.xxx.com；可填到 /v1 或 /v1/responses |
| `model` | STRING（单行） | — | `gpt-5.5` | Responses API 模型名称，按你的中转/服务端支持填写 |
| `画面比例` | COMBO | `16:9` / `9:16` / `1:1` / `4:3` / `3:4` / `4:5` / `5:4` / `21:9` / `9:21`（9 项，此为精确顺序） | `16:9` | 主要用于 9段分镜 的 grid_aspect_ratio 和提示词方向 |
| `输出语言` | COMBO | `中文` / `English`（仅 2 项） | `中文` | 控制非 9 段分镜功能的输出语言；9 段分镜固定中文 |
| `max_output_tokens` | INT | min 256 / max 32768 / step 256 | 4096 | 最大输出 token，9段分镜建议 4096 或更高 |
| `temperature` | FLOAT | min 0.0 / max 2.0 / step 0.05 | 0.7 | 创意程度；如果服务端模型不支持，可调回默认或更低 |

**optional**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `seed` | INT | min -1 / max 2147483647，`control_after_generate: true` | -1 | 仅用于 ComfyUI 触发重新执行，不会写入请求体 |
| `timeout_s` | INT | min 30 / max 1800 | 300 | 请求超时时间（秒） |
| `绕过代理` | BOOLEAN | — | False | 需要忽略系统代理/梯子时开启 |
| `快捷功能自定义` | STRING（forceInput=True） | — | — | 快捷功能选择“自定义”时生效；输入内容会添加到用户提示词前面 |

**hidden**：无。

要点：`快捷功能自定义` 是连线输入（forceInput），与 §3.5 自定义功能报错文案"请连接'快捷功能自定义'"吻合；`seed` 为 optional 且默认 -1。

### 7.2 模块常量实锤值（动态采集）

pyd 模块 `TE_MAN.TE_MAN_Text_Tools`（module docstring 为 `null`）：
- `QUICK_FUNCTION_STORYBOARD_9 = "9段分镜提示词"`、`QUICK_FUNCTION_IMAGE_PROMPT = "扩写生图提示词"`、`QUICK_FUNCTION_VIDEO_PROMPT = "扩写生视频提示词"`、`QUICK_FUNCTION_CUSTOM = "自定义"`、`QUICK_FUNCTION_OPTIONS` = 上列 4 项精确顺序（中文值↔常量键映射就此实锤）
- `MODULE_DIR = PLUGIN_DIR = <ComfyUI>/custom_nodes/TE_MAN`（真机为 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN`，即 config.ini 读取根）
- 依赖注入：`ConfigManager`（自 `custom_nodes.TE_image.config_manager`，docstring "集中管理 Banana Gemini 节点的配置与测试模式逻辑"）——与 §3 步骤 2 的 `_resolve_key_and_url` → `load_api_key()`/`get_effective_api_base_url()` 链路互证
- 模块级 `function_docs` 中仅 typing 别名（`Any/Dict/List/Optional/Tuple`），无业务函数 docstring——§3 的 helper 行为流仍以反汇编/字符串证据为准

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2 `OUTPUT_NODE` 推测 True [低] | **已确认：True（动态回填）** |
| §2 `绕过代理`/`style_hint` 是否 process_text/INPUT_TYPES 参数 | **已确认：`绕过代理` 是 optional BOOLEAN 输入（键名即中文，无 `bypass_proxy` 键、无 `label` 转换层）；`style_hint` 不在 INPUT_TYPES（内部 helper 形参）（动态回填）** |
| §3 required/optional 分组归属 | **已确认：见 §7.1（动态回填）** |
| §3 `输入文本` multiline/默认值 [中] | **已确认：multiline=True，默认值即旗袍示例文本（动态回填）** |
| §3 `快捷功能` 中文值↔常量键映射 未确认 | **已确认：映射见 §7.2；选项精确顺序 9段分镜→扩写生图→扩写生视频→自定义，默认 9段分镜提示词（动态回填）** |
| §3 `画面比例` 选项顺序（1:1 在前） | **已确认：运行时顺序为 16:9, 9:16, 1:1, 4:3, 3:4, 4:5, 5:4, 21:9, 9:21，默认 16:9（动态回填）** |
| §3 `输出语言` 其余选项 未确认 | **已确认：仅 `中文`/`English` 两项，无其余（动态回填）** |
| §3 `快捷功能自定义` 是否 forceInput [低] | **已确认：forceInput=True、optional（动态回填）** |
| §3 `temperature` 默认 0.7 [中] | **已确认：0.7，min 0.0/max 2.0/step 0.05（动态回填）** |
| §3 `max_output_tokens` 默认 未确认 | **已确认：4096，min 256/max 32768/step 256（动态回填）** |
| §3 `timeout_s` 默认 未确认 | **已确认：300，min 30/max 1800，optional（动态回填）** |
| §3 `seed` 默认 未确认 | **已确认：-1，min -1/max 2147483647，control_after_generate=true，optional（动态回填）** |
| §3 `model` 默认 `gpt-5.5` [中] | **已确认（动态回填）** |
| §3 返回值确切成员 未确认 | **已确认：`RETURN_TYPES=("STRING","STRING")`、`RETURN_NAMES=("text","json")`（动态回填）**；`text_output`/`prompt_text`/`storyboard_prompts` 候选不成立 |
| §3 `IS_CHANGED` 实现语义 [低] | **已确认其存在（has_IS_CHANGED=True）；语义（哈希/恒变）introspection 不可见，保持未确认** |

> 附注：运行时 INPUT_TYPES 中没有 `thinking`、`style_hint` 等额外参数；§3 表即完整参数集。
