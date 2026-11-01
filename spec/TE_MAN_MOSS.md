# TE_MAN_MOSS.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出入口 `PyInit_TE_MAN_MOSS`。静态分析（字符串 / 导入导出表 / 前端 JS 字符串表交叉核对）。
> 佐证材料：README.md v3.8（该章节即本模块的功能说明）、`web/js/te_man_moss_box.js`（与 Box 节点配套的前端脚本）、`config.ini`。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

TE MAN v3.8 新增节点模块，包含两个 ComfyUI 节点：**「TE MAN MOSS 增强版式规划/增强提示词」（TEMossLayoutNode）** 与 **「TE MAN MOSS 增强边界框/增强提示词」（TEMossBoxNode）**。前者把一句话提示词扩写成整图描述 + 槽位描述并生成框位，输出可喂给 MOSS-Image 的 layout 提示词；后者提供画布拖拽框位可视化编辑，并把（上游或编辑后的)元素列表编译成最终 MOSS layout 提示词。原文："一句话提示词 -> 自动扩写文案与画面 -> 按内置版式生成框位 -> 编译成 MOSS-Image layout 提示词"。[高]

## 2. Python API

### 导出
- `PyInit_TE_MAN_MOSS`（ EXPORT 表唯一符号）[高]
- 构建信息：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_MAN_MOSS.c`、`custom_nodes/TE_image/source_py_backup/TE_MAN_MOSS.py`，模块属 `custom_nodes.TE_image` 包 [高]
- PE 导入仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll`（无 WS2_32 等网络库；HTTP 请求经由导入的 `TE_Qwen_Image_2_1_Prompt_Enhancer` / api 体系完成）[高]

### 类与函数（qualname 直接证据）[高]
| 对象 | 推断签名 / 用途 |
|---|---|
| `TEMossLayoutNode.plan` | 节点主执行（FUNCTION 名 `plan`）[高] |
| `TEMossBoxNode.compile` | 节点主执行（FUNCTION 名 `compile`）[高] |
| `TEMossLayoutNode.INPUT_TYPES` / `TEMossBoxNode.INPUT_TYPES` | [高] |
| `_fonts` | 按优先级找一个能显示中文的字体（`msyhbd.ttc`→`msyh.ttc`→`simhei.ttf`→`arial.ttf` 顺序未确认，但四个字体名与 `C:\Windows\Fonts\` 均存在），失败退回 PIL `load_default` [高=tooltip 原文] |
| `_extract_json` + lambda | 尽力从模型输出里抠出 JSON（对象或数组），抠不出来返回 None；配合去 markdown 围栏的正则 `^```[A-Za-z]*\s*` / `\s*```\s*$`、误分隔符清理 `,\s*([}\]])` [高] |
| `_plain_caption` | 只扩写模式兜底：模型直接回正文（非 JSON）时把正文当 caption [高=行为有中文注释] |
| `_norm_number` / `_to_1000` + lambda | 数值规范 / 把任意坐标标定到 0-1000 [高=qualname、中文注释"0-1000"] |
| `_to_centered_bbox` | 0-1000 元素 bbox -> MOSS 模型侧居中 yxyx 整数坐标，与 `comfy_extras/nodes_moss_image.py` 的 `MOSSImageLayoutPrompt` 完全一致（先换回像素 ceil，再减画布中心）[高=docstring 原文] |
| `_slot_type` + genexpr | 推断槽位类型 text/obj（参数 `declared` 为声明类型）[高=qualname] |
| `_normalize_elements` + genexpr | 把任意来源的框数据整理成 `[{role, type, text, desc, bbox}]`，bbox 为 0-1000 [高=注释原文] |
| `_split_elements` / `_grow_span` | 逐槽位拆分 / 把过窄的区间围绕中心撑到 `minimum` 再压回 0-1000 [高] |
| `_payload_bbox` / `_auto_bbox` / `_auto_elements` | 模型给的 bbox（0-1000，xyxy）→ yxyx 整数框，不可用整体返回 None；兜底纵向均分（"自动排版的兜底：按模型给的顺序纵向均分，留出边距"）[高] |
| `_preset_elements` | 把 slots 内容落到 `LAYOUT_PRESETS` 内置骨架 [高] |
| `_build_layout_prompt` | 组装系统/用户 prompt（占位符 `{reply_shape}` `{slot_names}` `{slot_types_line}` `{layout_rules}` `{language_rules}` `{caption_rules}` 均为字符串证据）[高] |
| `_wrap` | 文本换行（预览绘制用，`max_width`、`PIL ImageDraw textlength`）[中] |
| `_tensor_from_image` / `_preview_ui` / `_with_preview` / `_render_preview` | 预览图生成并把预览挂到节点自身（"把预览图挂到节点自身，这样不用再接 PreviewImage 也能直接看见框"）[高] |
| `_generate_text` | 三后端统一入口（参数 `system_prompt`/`user_prompt`/`max_length`）[中] |
| `_slot_description` + genexpr | 槽位描述文本生成 [高=qualname] |
| `_request_local` / `_request_api` | llama.cpp 请求 / OpenAI 兼容 `/responses` 请求 [高=qualname] |
| `_llm_file_choices` | 枚举 `models/LLM` 下模型文件 [高] |
| `_resolve_api_key` | API key 解析，留空时读取 TE MAN 的 config.ini [高=tooltip 原文] |
| 模块常量 | `LAYOUT_PRESETS`、`PRESET_CHOICES`、`AUTO_PRESET`、`CAPTION_PRESET`、`RAW_PRESET`、`SYSTEM_PROMPT`、`CAPTION_SYSTEM_PROMPT`、`REPLY_SHAPE`、`AUTO_REPLY_SHAPE`、`LAYOUT_RULES`、`AUTO_LAYOUT_RULES`、`CAPTION_RULES`、`LANGUAGE_RULES`、`OBJECT_HINTS`、`LOCAL_MODELS`、`DEFAULT_API_MODEL`、`DEFAULT_API_BASE_URL`、`DEFAULT_CONTEXT_LENGTH` [高=字符串存在] |

### 节点注册 [高]
- `NODE_CLASS_MAPPINGS` 键：`TE_image_pro_moss_layout` → `TEMossLayoutNode`；`TE_image_pro_moss_box` → `TEMossBoxNode`（与前端 JS `NODE_TYPE='TE_image_pro_moss_box'` 一致 [高]）
- `NODE_DISPLAY_NAME_MAPPINGS`：`TE MAN MOSS 增强版式规划/增强提示词`、`TE MAN MOSS 增强边界框/增强提示词`
- `CATEGORY = "TE MAN/MOSS"` [高]

## 3. 节点规格

### 3.1 TEMossLayoutNode（注册名 TE_image_pro_moss_layout）

布局节点：扩写 → 出框位 → 编译。`OUTPUT_NODE=True`（OUTPUT_NODE/save_images 字符串存在），输出"版式预览图"。

**输入参数**（tooltip 为直接证据；参数键名已由动态 introspection 实锤，完整 INPUT_TYPES 全表见文末 §7.1。与早前推断的主要出入：`版式选择`/`输出语言`/`本地模型`/`API模型(responses格式)` 就是中文键名；本地生成上限参数叫 `max_length`（非 max_output_tokens/context_length）；另有此前未发现的 `增强方式`（CLIP / 本地 llama.cpp / API 三选一，默认 CLIP）与 `生成后卸载本地模型`（BOOLEAN，默认 True）两个参数；`seed` 也是节点参数（默认 0，max 281474976710655））：

| 参数（推断） | 类型 | 说明（tooltip 原文） |
|---|---|---|
| `prompt` | STRING（multiline） | "一句话需求"："输入一句话，自动扩写文案与画面，并按选中版式生成边界框，输出可直接喂给 MOSS-Image 的 layout 提示词"[高=行为描述；已确认：键名 `prompt`，默认 `"一张音乐节海报"`（动态回填） |
| `版式选择`（早先推断键名 `preset`） | COMBO（默认 `竖版海报`） | "版式选择"（§3.1.1 六种）[高；键名已确认 `版式选择`（动态回填） |
| `输出语言` | COMBO（默认中文） | "输出语言"："扩写出来的整图描述和元素描述用什么语言；JSON 字段/slot 名和 text/obj 结构值始终是英文"[高；键名已确认 `输出语言`，选项 `中文`/`英文`（动态回填） |
| `clip` | CLIP 输入（optional，forceInput） | "增强方式为 CLIP 时使用；其它方式接着也没关系。"CLIP 模式"调 CLIPLoader 里那个文本模型，采样参数全部用 clip.generate 自己的默认值" [高；已确认 forceInput=True（动态回填） |
| `本地模型` | COMBO（唯一选项 `（请把模型放到 models/LLM）`） | "models/LLM 下的本地模型，仅「本地 llama.cpp」使用；其它方式不用管。"[高] |
| `max_length` / `生成后卸载本地模型` | INT / BOOLEAN | "CLIP 与本地 llama.cpp 的生成上限（新增 token）；API 模式不发送此限制"、"生成完就释放显存，避免和后面的 MOSS 出图抢显存；要连续调版式可以关掉" [高；已确认：键名为 `max_length`（默认 4096，min 256 / max 8192 / step 64）与 `生成后卸载本地模型`（默认 True）；早先推断的 max_output_tokens/context_length/unload 键名不成立（动态回填） |
| `api_base_url` / `API模型(responses格式)` / `api_key` | STRING | 默认 `https://teynex.com` / `deepseek-v4.1-flash` / `""`；"仅 API 使用；按 OpenAI 兼容的 /responses 接口调用"、"仅 API 使用；填服务端 /responses 接口认识的模型名"、"留空时读取 TE MAN 的 config.ini" [高；键名与默认值已确认（动态回填） |

**版式选择（preset）六种** [高=所有选项行使原文]:
1. **竖版海报 / 横版横幅 / 方形** —— 固定版式骨架（`LAYOUT_PRESETS`），"内置版式骨架，坐标按比例存，换画布尺寸不用重算"。已确认（动态回填）：骨架为纯 `[role, type, 比例坐标]` 三元组，不含任何示例文案；实际 role 集合为——竖版海报 `title/subtitle/hero/detail/footer`、横版横幅 `title/subtitle/hero/footer`、方形 `title/hero/caption`（早先猜的 `panel`/`scene` 不在骨架里，`detail` 是此前漏掉的）；坐标为 0–1 的 `(x, y, w, h)` 比例（"骨架坐标按比例存" 推断成立）。早先认作"骨架内置示例"的 `夏日音乐节`/`一张音乐节海报`/`enormous cream serif capitals, centred`/`stage truss silhouettes, crowd, warm haze` 实为 Box 节点 `boxes` widget 的演示默认 JSON（title=text 槽、hero=obj 槽），不属 LAYOUT_PRESETS。
2. **自动排版(官方skill)**（内部值 `auto`）[高=字符串存在] —— "由模型给每个槽位写位置，seed 变了版式也会变"。系统 prompt 用 `AUTO_LAYOUT_RULES`（"Layout (you own the composition): 每个槽位必须含 bbox [xmin,ymin,xmax,ymax] 0-1000 比例坐标…"，槽位名由模型自选 "3 to 6 short role names… such as title, subtitle, hero, caption, footer"），`AUTO_REPLY_SHAPE` 的 JSON 形状为：
   `{"caption": "<caption>", "slots": {"<slot name>": {"type": "text|obj", "bbox": [...], "text": "...", "desc": "..."}}}` [高=动态实锤，AUTO_REPLY_SHAPE 确含 type/bbox 键]
3. **只扩写(无框位)**（内部值 `caption_only`）[高] —— "只输出扩写后的整图描述，不产生元素列表"，`CAPTION_SYSTEM_PROMPT` 的 reply 形状为 `{"caption": "<caption>"}`[高]
4. **直出(不进行任何处理)**（内部值 `raw`）[高] —— "不调任何模型，prompt 原样传给下游"

**尺寸 widgets**（已确认：Layout 与 Box 两节点同有 `width`/`height`，两节点默认值一致：1024×1536，min 256 / max 4096 / step 16；动态回填）:
- `width` / `height`："输出画布宽度/高度，必须是 16 的倍数"（该 tooltip 属 Layout 节点；Box 节点同名 widget 无 tooltip）。两节点均无"字号"参数——Layout 侧字体大小相关参数不存在，早先的字号归属疑问作废。
- `无框位：当前只输出纯文本提示词`（caption_only/直出模式提示）：introspection 未采集到运行期 UI 消息，保持原样。

**系统 prompt 体系**（完整原文，[高]）：
- `SYSTEM_PROMPT`（版式规划共用骨架）："You are a layout planner for an image generation model that consumes a JSON layout prompt."——**已确认（动态回填）：`REPLY_SHAPE`（预设模式模板）为无 type/bbox 键的形状 `{"caption": "<caption>", "slots": {"<slot name>": {"text": "<visible copy>", "desc": "<appearance>"}}}`（bbox 由 `_preset_elements` 落预设骨架时补）；含 `"type": "text|obj"` 与 `bbox` 的是 `AUTO_REPLY_SHAPE`（自动排版模式，§6.2 附录中两行的括注对调了）**
- 规则正文：`LAYOUT_RULES`（"Every slot MUST contain bbox [xmin, ymin, xmax, ymax], four integers from 0 to 1000… text 槽位不得重叠、文本框尺寸视文案长度…"）
- `CAPTION_RULES`: "caption" describes the finished picture… 按主体/动作/空间/布景/取景/布光/色调 facets 分段，要求 300-500 词(英)或 500-800 字(中)，禁止出现框位/坐标/JSON/画布比例字样 [高]
- `LANGUAGE_RULES`: 中文 "Write caption and every desc in Chinese. The caption must be 500-800 Chinese characters and never shorter than 500. JSON keys, slot names and the values text/obj stay in English." / 英文 "…300-500 words and never shorter than 300…" [高]
- `OBJECT_HINTS`（role→obj 判定词）：`hero/object/obj/image/photo/visual/scene/…/illustration`（按 JS 一致词表 [高]; pyd 内 hero/obj/image/photo/visual/scene/illustration 全部出现）[高]
- 槽位 type 判定："Choose each slot's type: text for visible copy, obj for imagery"、"A slot typed text MUST include text. A slot typed obj MUST NOT include text." [高]

**输出（已确认，动态回填）**：
- `RETURN_TYPES = ("STRING", "STRING", "IMAGE", "STRING")`，`RETURN_NAMES = ("完整版式提示词", "元素列表", "版式预览图", "描述")`——第四输出口名是 **`描述`**（即扩写后的整图描述/caption，可接到「TE MAN MOSS 边界框」的上游描述），早先猜的"整图描述"口名与顺序（完整版式提示词/整图描述/元素列表/版式预览图）不成立。
- 元素条目结构 `[{role, type, text, desc, bbox}]`，bbox 为 `[ymin, xmin, ymax, xmax]` 0-1000 整数（"顺序与 ComfyUI 自带边界框一致"）[高]

**运行流程（有中文行为注解佐证）**[高]:
1. 按预设/自动/只扩写/直出四分支选择：
   - 预设（竖版海报/横版横幅/方形）：模型按 shape 出 slots → `_preset_elements` 落到固定骨架 `LAYOUT_PRESETS`
   - 自动排版：模型给 bbox → `_auto_bbox`（0-1000 xyxy→yxyx，超界"按比例截断"，槽位号失可整体返回 None）→ 兜底 `_auto_elements` 纵向均分（"TE MAN MOSS: 自动排版没有可用的框，退回纵向均分"）
   - 只扩写：模型直接回正文（非 JSON）→ `_plain_caption` 兜底；"截断的 JSON 不算"
   - 直出：prompt 原样输出，并输出 `TE MAN MOSS: 没有框位，只输出纯文本提示词`
2. `_to_1000`：把 slots 框位换算成 0-1000 整数（`_norm_number`/`_grow_span` 保证可容纳）
3. 输出 layout 提示词（单行紧凑 JSON，`ensure_ascii`/`separators`/`indent` 证据）+ 元素列表 + caption + 预览。

**palette 处理 Layout 节点侧**：Layout 产出的 `元素列表` 每条可含 `palette`（调色板颜色列表）字段，由 Box 节点端可视化编辑并传回 [中→JS 完整定论见 3.2]。

### 3.2 TEMossBoxNode（注册名 TE_image_pro_moss_box）

节点描述（原文）：在画布上拖拽画框，选中后编辑类型（"画面描述obj"/"排版文字"）、文字、描述和调色板 [高]。
- 设计动机（原文）："ComfyUI 自带的 Create Bounding Boxes 只在 Nodes 2.0 下渲染画布控件，这个节点把同样的编辑方式做进普通 DOM 控件，旧前端同样可用"（且刻意"不使用 comfy_api 的 V3 类型（io.BoundingBoxes 等）"，"在不开启 Nodes 2.0 的旧版前端里也能正常使用"）。[高]

**输入/输出（对应关系含 [中]，参数名与 widget 名为字符串证据）[高]**：
- 输入：
  - `上游元素列表`（STRING，forceInput；JS `SRC_INPUT`，legacy 别名 `boxes_src`/`上游框数据`——均即 '上游元素列表'；`caption_src`/`上游描述`）："连接后首次运行会把框载入画布，之后以画布编辑为准；上游内容变了会重新载入"（`last_incoming`/`te_moss_last`/`te_moss_apply` 状态字段追踪 [高]）
  - `上游描述`：布局原始 caption（"不接上游描述时使用的整图描述，编译后成为 summary.caption"）
- Widget：
  - `boxes`："框列表 JSON，由画布自动维护；bbox 为 [ymin, xmin, ymax, xmax]，0-1000 整数，顺序与 ComfyUI 自带边界框一致" [高]
  - `width` / `height`：画布尺寸
  - `整图描述`（CAPTION_WIDGET）、`last_incoming`（隐藏，multiline，"内部状态：上一次已经载入画布的上游元素列表，由节点自己维护"，"前端不显示这个输入框"）[高]
- 输出：面板输出至少含 `完整版式提示词`、`版式预览图`（与 Layout 同名子集推断 [中]）；判据同上。

**`compile()` 编译行为（docstring/佐证）：**[高]
- 输入源：画布 `boxes` 元素列表（或上游 `上游元素列表`）
- 逐框换算成 MOSS-Image 侧坐标：`_to_centered_bbox`："0-1000 元素 bbox -> MOSS 模型侧居中 yxyx 整数坐标，与 comfy_extras/nodes_moss_image.py 的 MOSSImageLayoutPrompt 完全一致：先换回像素，小数边向外取整（ceil），再减去画布中心"。坐标名字符串 `abs_centralized`、`yxyx` [高] —— 即最终 layout JSON 中 bbox 的坐标系为 `abs_centralized`、`yxyx` [高（字符串与注释）/ 中（字段级对应细节未确认）]
- 产出 "编译成 MOSS-Image 的 layout 提示词（单行紧凑 JSON）"，并 `TE MAN MOSS 边界框: 没有解析到有效框，检查 bbox 是否为 [ymin,xmin,ymax,xmax]` 校验失败报错
- **palette**：每个元素条目随框写入 `palette` 钮色列表（JS 端逐框编辑，"调色板"5 色上限，"第一个颜色同时是框编号标签的颜色；点击改色，右键删除"；`palette` 键在 JS 序列化与 pyd 中均出现 [高]）。pyd 中另有 `color_palette` 标识符 [高]——可能为编译偏后或内部别名，exact 挂接层未确认。
  - Layout 节点 palette 行为同源（README："调色板最多 5 个颜色，随框写进 layout JSON 的 palette"）[高=README 描述]

**框类型自动判定**：JS `boxType`：若 `type==='text'||'obj'` 直接采用；否则用 role/desc/label 与 OBJECT_HINTS 匹配判 'obj' [高]（与 py `_slot_type` 对齐）。

**预览图**（两节点可能共用 `_preview_ui/_render_preview` 代码）[中]：
- "画一张框位预览图/旧前端也能当普通图片看"、"把预览图挂到节点自身，这样不用再接 PreviewImage" [高]
- 绘制：PIL `Image`/`ImageDraw`/`ImageFont.truetype`，`rectangle`/`outline`/`fill`/`textlength`，中文优先字体 `msyhbd.ttc`/`msyh.ttc`/`simhei.ttf`/`arial.ttf`（C:\Windows\Fonts\）→ 退回 `load_default` [高]
- 颜色（JS 恒常量 [高]）：文字框 `#78c896`、画面框 `#e0966a`，矩形边框 `#3a3a42`

**前端行为（已是 JS 端实现，py 侧配合状态字段）**[高=JS 字符串表]：
- 工具栏四按钮：
  1. **生成版式**："把上游的框载入画布"（已接上游元素列表时）
  2. **重新生成版式**："按当前提示词重跑版式规划，并把结果载入画布"/"换一个随机种子重跑版式规划"（上游必须已接 "先在「上游元素列表」接上版式规划"）
  3. **生成图片**："运行下游出图节点"（未接提示"下游没有接出图节点"，通过 `noise_seed` widget 查找下游）
  4. **重新生成图片**："换一批随机种子重跑下游出图节点"（改 `noise_seed` 后重新 queue + 轮询 `/queue`，`graphToPrompt`/`fetchApi`/`partial_execution_targets`/`target_id` 证据）
- 编辑面板字段：**画面描述obj / 排版文字**（类型切换），**文本**、**描述**、**调色板**（≤5 色，"添加一个颜色"，右键删除），bar 工具：**网格**（grid 开关）、**删除所选**、**全部清除**；"拖拽新建文本框，Shift+拖拽新建画面框"。
- 状态反馈："运行中…"，`pending`/`queue_pending`/`exec` 错误轮询"查询执行状态失败"，浏览器标签页标题加 `✦MOSS`。

## 4. 外部依赖与副作用

- **网络端点**：API 模式按 **OpenAI 兼容 `/responses`** 接口请求（字符串证据 `仅 API 使用；按 OpenAI 兼容的 /responses 接口调用`、`/responses`）；- `DEFAULT_API_MODEL = "deepseek-v4.1-flash"` [高=字符串]。**已确认：`DEFAULT_API_BASE_URL = "https://teynex.com"`（动态回填，且与节点参数 `api_base_url` 默认值一致）**。api_key 留空时读取 TE MAN 的 config.ini（`_resolve_api_key`）[高；具体 config 键名未确认]
- **模块依赖**：`TE_Qwen_Image_2_1_Prompt_Enhancer` 模块的 `TEQwenImage21LocalStorage`——本地 llama.cpp（`models/LLM`、支持 `mmproj`）与 CLIP 的文本后端实现；未加载时报"未加载 Qwen 节点模块，无法使用本地 llama.cpp / 无法使用 API"。[高]
- **文件系统**：
  - 读：`models/LLM` 下 gguf/mmproj 文件（枚举 `[高]`）、`C:\Windows\Fonts\*.ttc|ttf`、TE MAN `config.ini`（API key）
  - 写：预览图保存（"TE MAN MOSS 预览图保存失败: %s"；正式路径如 `TE MAN MOSS/` 下未确认 [未确认保存路径与文件名格式]）
- **状态与属性**：`_request_local`、`_request_api`、`thinking`（输入参数，`thinking` 出现在局部标识符 [中]）
- **不刻意使用 comfy_api V3 类型（io.BoundingBoxes），避免依赖 Nodes 2.0；兼容旧前端的 DOM 画布**。[高]
- `SKIP_MODULES` 中不含 `TE_MAN_MOSS`，即它会作为节点模块被正常加载 [高=读 `__init__.py`]。

## 5. 错误处理与用户可见文案 [高]

| 文案 | 触发场景 |
|---|---|
| `TE MAN MOSS: 模型输出不是合法 JSON，退化为纯文本提示词: %s` | 模型回包非 JSON |
| `TE MAN MOSS 生成失败，退化为纯文本提示词: %s` | 生成流程异常兜底 |
| `TE MAN MOSS: 只扩写没有拿到 caption，退回原 prompt（输出 %d 字）: %s` | caption_only 模式失败 |
| `TE MAN MOSS: 没有框位，只输出纯文本提示词` | 无框位模式输出 |
| `TE MAN MOSS: 自动排版没有可用的框，退回纵向均分` | auto 模式 `_auto_bbox` 整体返 None |
| `TE MAN MOSS: 自动排版的槽位 %s 不是对象: %s` | auto 槽位非 dict |
| `TE MAN MOSS: 自动排版的槽位 %s 框不可用: %s` | auto 槽位 bbox 不可用 |
| `TE MAN MOSS: 自动排版有坐标超出 0-1000，按比例截断: %s` | 越界收序 |
| `TE MAN MOSS 边界框: 没有解析到有效框，检查 bbox 是否为 [ymin,xmin,ymax,xmax]` | compile 无有效框 |
| `TE MAN MOSS 预览图保存失败: %s` | 预览写盘失败 |
| `增强方式为 CLIP 时需要连接 clip 输入` | CLIP 校验 |
| `未加载 Qwen 节点模块，无法使用本地 llama.cpp` / `…无法使用 API` | 模块依赖缺失 |
| `无框位：当前只输出纯文本提示词` | caption_only/raw 模式 |

## 6. 证据附录

### 6.1 文件与注册
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_MAN_MOSS.c
custom_nodes/TE_image/source_py_backup/TE_MAN_MOSS.py
custom_nodes.TE_image.TE_MAN_MOSS
TE_image_pro_moss_layout / TE_image_pro_moss_box
TEMossLayoutNode / TEMossBoxNode
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / INPUT_TYPES / RETURN_TYPES / RETURN_NAMES
CATEGORY: 'TE MAN/MOSS'    OUTPUT_NODE    FUNCTION: plan / compile
teynex: https://teynex.com
description: 一句话提示词 -> 自动扩写文案与画面 -> 按内置版式生成框位 -> 编译成 MOSS-Image layout 提示词
刻意不使用 comfy_api 的 V3 类型（io.BoundingBoxes 等），所以在不开启 Nodes 2.0 的旧版前端里也能正常使用
```

### 6.2 模式 / 骨架 / 系统 prompt 相关
```
LAYOUT_PRESETS / PRESET_CHOICES / AUTO_PRESET / CAPTION_PRESET / RAW_PRESET
LAYOUT_RULES / AUTO_LAYOUT_RULES / CAPTION_RULES / LANGUAGE_RULES / OBJECT_HINTS
CAPTION_SYSTEM_PROMPT / SYSTEM_PROMPT / AUTO_REPLY_SHAPE / REPLY_SHAPE
LOCAL_MODELS / DEFAULT_API_MODEL / DEFAULT_API_BASE_URL / DEFAULT_CONTEXT_LENGTH
'deepseek-v4.1-flash' / 'abs_centralized' / mmproj / models/LLM
竖版海报 / 横版横幅 / 方形 / 自动排版(官方skill) / 只扩写(无框位) / 直出(不进行任何处理)
夏日音乐节 / 一张音乐节海报 / enormous cream serif capitals, centred / stage truss silhouettes, crowd, warm haze
REPLY 形状(JSON 原文)：
 {"caption": "<caption>", "slots": {"<slot name>": {"type": "text|obj", "bbox": [<xmin>, <ymin>, <xmax>, <ymax>], "text": "<visible copy>", "desc": "<appearance>"}}}
 {"caption": "<caption>", "slots": {"<slot name>": {"text": "<visible copy>", "desc": "<appearance>"}}}   （AUTO_REPLY_SHAPE）
 {"caption": "<caption>"}   （CAPTION_SYSTEM_PROMPT）
Layout (you own the composition):
- Every slot MUST contain "bbox": [xmin, ymin, xmax, ymax], four integers from 0 to 1000 … never pixel coordinates … xmin < xmax and ymin < ymax. A slot without it is discarded.
Choose each slot's "type": text for visible copy, obj for imagery.
A slot typed "text" MUST include "text". A slot typed "obj" MUST NOT include "text".
Language (cn): Write "caption" and every "desc" in Chinese. The caption must be 500-800 Chinese characters and never shorter than 500. JSON keys, slot names and the values "text" / "obj" stay in English.
Language (en): 300-500 words and never shorter than 300.
3 to 6 short role names you choose, in visual order, such as title, subtitle, hero, caption, footer
```

### 6.3 内部 API / JIT 标识符
```
_fonts _extract_json _plain_caption _norm_number _to_1000 _to_centered_bbox _slot_type
_normalize_elements _split_elements _grow_span _payload_bbox _auto_bbox _auto_elements
_preset_elements _build_layout_prompt _wrap _tensor_from_image _preview_ui _with_preview
_render_preview _generate_text _slot_description _request_local _request_api
_llm_file_choices _resolve_api_key
ensure_ascii / separators / indent / ceil / floor / isfinite / box_ratio / minimum
CLIPLoader / clip.generate / TEQwenImage21LocalStorage / thinking
```

### 6.4 坐标系与元素结构
```
把任意来源的框数据整理成 [{role, type, text, desc, bbox}]，bbox 为 0-1000
bbox 为 [ymin, xmin, ymax, xmax]，0-1000 整数，顺序与 ComfyUI 自带边界框一致
模型给的 bbox（0-1000，xyxy）-> 0-1000 的 yxyx 整数框；不可用时返回 None
比例框 (x, y, w, h) -> ComfyUI 元素 bbox [ymin, xmin, ymax, xmax]，0-1000 整数
0-1000 元素 bbox -> MOSS 模型侧居中 yxyx 整数坐标
   与 comfy_extras/nodes_moss_image.py 的 MOSSImageLayoutPrompt 完全一致：
   先换回像素，小数边向外取整，再减去画布中心
取槽位里的框：兼容 bbox/box，四元数组、ymin.. 字典和 x/y/width/height 字典
palette / color_palette
```

### 6.5 前端 `te_man_moss_box.js`（佐证）
```
NODE_TYPE='TE_image_pro_moss_box'  BOXES_WIDGET='boxes'  CAPTION_WIDGET='整图描述'
LAST_WIDGET='last_incoming'  WIDTH/HEIGHT 'width'/'height'  SRC_INPUT='上游元素列表'
LEGACY_INPUTS={'boxes_src':'上游元素列表','上游框数据':'上游元素列表','caption_src':'上游描述'}
OBJECT_HINTS=['hero','object','obj','image','photo','visual','scene','…','illustration']
COLOR_TEXT='#78c896'  COLOR_OBJ='#e0966a'  BORDER='#3a3a42'
按钮/编辑(中文原文)：生成版式 / 重新生成版式 / 生成图片 / 重新生成图片
  删除所选 / 全部清除 / 网格 / 添加一个颜色 / 调色板 / 画面描述obj / 排版文字
  第一个颜色同时是框编号标签的颜色；点击改色，右键删除
  拖拽新建文本框，Shift+拖拽新建画面框
  已接上游元素列表：点「生成版式」把上游的框载入画布
  换一个随机种子重跑版式规划 / 换一批随机种子重跑下游出图节点
  运行下游出图节点 / 下游没有接出图节点 / 先在「上游元素列表」接上版式规划
状态: queue_pending / partial_execution_targets / target_id / output_node / noise_seed
      graphToPrompt / fetchApi / /queue / exec / pending
palette(最多 5 色)  bbox  role  type  text  desc
```

### 6.6 pixels(其它)
```
msyhbd.ttc  msyh.ttc  simhei.ttf  arial.ttf  C:\Windows\Fonts\  load_default
TE MAN MOSS 预览图保存失败: %s
```

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows Server 2025 + ComfyUI（Python 3.13.16）真实环境 import 后的自省结果；运行时模块显示为 `custom_nodes.TE_image.TE_MAN_MOSS`（`TE_image` 为插件原名），模块文件 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN\TE_MAN_MOSS.pyd`。本节所有值均为运行时实锤，不再标注置信度。

### 7.1 节点 INPUT_TYPES 全表（实锤）

#### TE_image_pro_moss_layout（TEMossLayoutNode）

注册元数据：`FUNCTION = "plan"`、`CATEGORY = "TE MAN/MOSS"`、`OUTPUT_NODE = True`、`RETURN_TYPES = ["STRING", "STRING", "IMAGE", "STRING"]`、`RETURN_NAMES = ["完整版式提示词", "元素列表", "版式预览图", "描述"]`；无 IS_CHANGED / VALIDATE_INPUTS / on_execute / check_lazy_status。节点 DESCRIPTION（原文）："输入一句话，自动扩写文案与画面，并按选中版式生成边界框，输出可直接喂给 MOSS-Image 的 layout 提示词。扩写可用 CLIP、本地 llama.cpp 或 API；选「只扩写(无框位)」只输出整图描述，选「直出(不进行任何处理)」则 prompt 原样输出。描述可接到「TE MAN MOSS 边界框」的上游描述。"

**required**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `增强方式` | COMBO | `CLIP` / `本地 llama.cpp` / `API`（3 项） | `CLIP` | 扩写用哪个模型。三者互不影响，没选中的后端参数可以留空。 |
| `prompt` | STRING, multiline | — | `一张音乐节海报` | 一句话需求。中文即可，模型会扩写成完整画面描述并保留中文文案。 |
| `版式选择` | COMBO | `竖版海报` / `横版横幅` / `方形` / `自动排版(官方skill)` / `只扩写(无框位)` / `直出(不进行任何处理)`（6 项） | `竖版海报` | 内置版式骨架，坐标按比例存，换画布尺寸不用重算；「自动排版(官方skill)」由模型给每个槽位写位置，seed 变了版式也会变；「只扩写(无框位)」只输出扩写后的整图描述，不产生元素列表；「直出(不进行任何处理)」不调任何模型，prompt 原样传给下游。 |
| `width` | INT | min 256 / max 4096 / step 16 | 1024 | 输出画布宽度，必须是 16 的倍数。 |
| `height` | INT | min 256 / max 4096 / step 16 | 1536 | 输出画布高度，必须是 16 的倍数。 |
| `max_length` | INT | min 256 / max 8192 / step 64 | 4096 | CLIP 与本地 llama.cpp 的生成上限（新增 token）；API 模式不发送此限制。 |
| `seed` | INT | min 0 / max 281474976710655 / step 1 | 0 | CLIP 与本地 llama.cpp 使用；API 模式忽略。 |
| `输出语言` | COMBO | `中文` / `英文`（2 项） | `中文` | 扩写出来的整图描述和元素描述用什么语言；JSON 字段、slot 名和 text/obj 结构值始终是英文。 |
| `本地模型` | COMBO | `（请把模型放到 models/LLM）`（1 项） | —（无 default 键） | models/LLM 下的本地模型，仅「本地 llama.cpp」使用；其它方式不用管。 |
| `生成后卸载本地模型` | BOOLEAN | — | True | 仅本地 llama.cpp。生成完就释放显存，避免和后面的 MOSS 出图抢显存；要连续调版式可以关掉。 |
| `api_base_url` | STRING | 单行 | `https://teynex.com` | 仅 API 使用；按 OpenAI 兼容的 /responses 接口调用。 |
| `API模型(responses格式)` | STRING | 单行 | `deepseek-v4.1-flash` | 仅 API 使用；填服务端 /responses 接口认识的模型名。 |
| `api_key` | STRING | 单行 | `""` | 仅 API 使用；留空时读取 TE MAN 的 config.ini。 |

**optional**：`clip`（CLIP，forceInput=True，tooltip "增强方式为 CLIP 时使用；其它方式接着也没关系。"）。**hidden**：无。

#### TE_image_pro_moss_box（TEMossBoxNode）

注册元数据：`FUNCTION = "compile"`、`CATEGORY = "TE MAN/MOSS"`、`OUTPUT_NODE = True`、`RETURN_TYPES = ["STRING", "STRING", "IMAGE"]`、`RETURN_NAMES = ["完整版式提示词", "元素列表", "版式预览图"]`。节点 DESCRIPTION（原文）："画布拖拽画框，选中后可编辑类型、文字、描述、调色板。可直接接「TE MAN MOSS 增强版式规划/增强提示词」的元素列表输出。"类 docstring 证实"ComfyUI 自带的 Create Bounding Boxes 只在 Nodes 2.0 下渲染画布控件，这个节点把同样的编辑方式做进普通 DOM 控件，旧前端同样可用"。

**required**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `整图描述` | STRING, multiline | — | `""` | 不接「上游描述」时使用的整图描述，编译后成为 summary.caption。前端不显示这个输入框。 |
| `boxes` | STRING, multiline | JSON 框列表 | 演示 JSON（见下） | 框列表 JSON，由画布自动维护。bbox 为 [ymin, xmin, ymax, xmax]，0-1000 整数，顺序与 ComfyUI 自带边界框一致。 |
| `width` | INT | min 256 / max 4096 / step 16 | 1024 | （无 tooltip） |
| `height` | INT | min 256 / max 4096 / step 16 | 1536 | （无 tooltip） |

`boxes` 默认值（原文 JSON，演示数据实锤——`夏日音乐节` 挂 title（text 槽），`enormous cream serif capitals, centred` 是其 desc；`stage truss silhouettes, crowd, warm haze` 挂 hero（obj 槽））：

```json
[
 {"role": "title", "type": "text", "text": "夏日音乐节",
  "desc": "enormous cream serif capitals, centred", "bbox": [55, 70, 185, 930]},
 {"role": "hero", "type": "obj",
  "desc": "stage truss silhouettes, crowd, warm haze", "bbox": [285, 50, 750, 950]}
]
```

**optional**：
- `上游元素列表`（STRING，forceInput=True，tooltip "接「TE MAN MOSS 增强版式规划/增强提示词」的元素列表。连接后首次运行会把框载入画布，之后以画布编辑为准；上游内容变了会重新载入。"）
- `上游描述`（STRING，forceInput=True，tooltip "可接上游的整图描述。连接后优先使用它。"）
- `last_incoming`（STRING, multiline，默认 `""`，tooltip "内部状态：上一次已经载入画布的上游元素列表，由节点自己维护。"）——位于 **optional 分组而非 hidden**（§3.2 早先称"隐藏"按分组语义修正；前端确实不显示它）。

**hidden**：无。

### 7.2 模块常量实锤值（动态采集）

pyd 模块 `TE_MAN.TE_MAN_MOSS`（运行时模块 docstring 原文："TE MAN MOSS\n\nMOSS-Image 版式规划与边界框。…刻意不使用 comfy_api 的 V3 类型（io.BoundingBoxes 等），所以在不开启 Nodes 2.0 的旧版前端里也能正常使用。"）：

- `AUTO_PRESET = "自动排版(官方skill)"`；`CAPTION_PRESET = "只扩写(无框位)"`；`RAW_PRESET = "直出(不进行任何处理)"`
- `PRESET_CHOICES = ["竖版海报", "横版横幅", "方形", "自动排版(官方skill)", "只扩写(无框位)", "直出(不进行任何处理)"]`（与版式选择下拉一致）
- `DEFAULT_API_BASE_URL = "https://teynex.com"`（§4 推断转实锤）；`DEFAULT_API_MODEL = "deepseek-v4.1-flash"`；`DEFAULT_CONTEXT_LENGTH = 8192`（此前仅知名，未知名值）
- `LOCAL_MODELS = ["（请把模型放到 models/LLM）"]`
- `OBJECT_HINTS = ["hero", "object", "obj", "image", "photo", "visual", "scene", "panel", "illustration"]`（完整 9 项，与 JS 词表一致）
- `LAYOUT_PRESETS`（完整实锤，`[role, type, (x, y, w, h)]` 0–1 比例）：
  - `竖版海报`：title/text `[0.07, 0.055, 0.86, 0.13]`；subtitle/text `[0.07, 0.205, 0.72, 0.055]`；hero/obj `[0.05, 0.285, 0.9, 0.465]`；detail/text `[0.07, 0.775, 0.6, 0.075]`；footer/text `[0.07, 0.885, 0.45, 0.05]`
  - `横版横幅`：title/text `[0.06, 0.14, 0.46, 0.3]`；subtitle/text `[0.06, 0.46, 0.4, 0.1]`；hero/obj `[0.42, 0.06, 0.52, 0.88]`；footer/text `[0.06, 0.82, 0.3, 0.06]`
  - `方形`：title/text `[0.08, 0.08, 0.84, 0.15]`；hero/obj `[0.05, 0.26, 0.9, 0.5]`；caption/text `[0.08, 0.8, 0.84, 0.09]`
  - `自动排版(官方skill)`：`null`（骨架由模型现场给框）
- `REPLY_SHAPE = {"caption": "<caption>", "slots": {"<slot name>": {"text": "<visible copy>", "desc": "<appearance>"}}}`（**预设模式模板，无 type/bbox 键**——bbox 由 `_preset_elements` 落骨架时补，修正 §6.2 附录括注的对调）；`AUTO_REPLY_SHAPE`（自动排版模板，**含 `"type": "text|obj"` 与 `bbox` 键**）；`AUTO_LAYOUT_RULES` 全文与 §6.2 摘录一致，且开头明确 **"bbox": [xmin, ymin, xmax, ymax]**（模型侧 xyxy 顺序）、"Keep at least 40 units of clear margin"、"Two text boxes must never overlap"、"text 槽仅在需要叠字时使用，纯画面请求所有槽都是 obj"
- `LANGUAGE_RULES`：中文→"caption must be 500-800 Chinese characters and never shorter than 500"；英文→"300-500 words and never shorter than 300"（与 §3.1 引文一致）
- 函数 docstring 实锤：`_auto_bbox`（"模型给的 bbox（0-1000，xyxy）-> 0-1000 的 yxyx 整数框；不可用时返回 None"）、`_to_centered_bbox`（"与 comfy_extras/nodes_moss_image.py 的 MOSSImageLayoutPrompt 完全一致：先换回像素，小数边向外取整，再减去画布中心"）、`_build_layout_prompt`（"编译成 MOSS-Image 的 layout 提示词（单行紧凑 JSON）"）、`_generate_text`（"调 CLIPLoader 里那个文本模型。采样参数全部用 clip.generate 自己的默认值"）、`_fonts`（"按优先级找一个能显示中文的字体，找不到就退回 PIL 内置字体"）、`_split_elements`（"自动排版的兜底：按模型给的顺序纵向均分，留出边距"）、`_payload_bbox`（"兼容 bbox/box、四元数组、ymin.. 字典和 x/y/width/height 字典"）
- `NODE_DISPLAY_NAME_MAPPINGS`：`TE_image_pro_moss_layout → "TE MAN MOSS 增强版式规划/增强提示词"`、`TE_image_pro_moss_box → "TE MAN MOSS 增强边界框/增强提示词"`

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2 `_fonts` 四字体优先顺序 | introspection 仅给 docstring（"按优先级…退回 PIL 内置字体"），顺序未采集，保持未确认 |
| §3.1 输入参数表各键名/默认值 | **已确认：见 §7.1 全表（动态回填）**；`preset`→`版式选择`、`language`→`输出语言`、`max_output_tokens/context_length/unload`→`max_length`/`生成后卸载本地模型`、`api_model`→`API模型(responses格式)`；新增 `增强方式`、`seed` 两参数 |
| §3.1.1 骨架 role 名与示例文案归属 | **已确认：骨架无示例文案；role 集合见 §7.2 LAYOUT_PRESETS（动态回填）**；demo 文案属 Box 节点 boxes 默认值 |
| §3.1 骨架坐标按比例存 [中] | **已确认：0–1 比例 (x,y,w,h)（动态回填）** |
| §3.1 尺寸 widgets 归属与默认值（MODULE 级未确认） | **已确认：两节点同有 width/height，均默认 1024×1536，min 256/max 4096/step 16（动态回填）**；"字号参数"不存在，归属疑问作废 |
| §3.1 `无框位：当前只输出纯文本提示词` 行为提示 | 运行期 UI 消息未被 introspection 采集，保持原样 |
| §3.1 Layout RETURN_TYPES/RETURN_NAMES 具体值 | **已确认：4 输出 `完整版式提示词/元素列表/版式预览图/描述`（动态回填）**；第四口名 `描述` 非"整图描述"，顺序亦与原推断不同 |
| §3.1 `REPLY_SHAPE`（预设）与 `AUTO_REPLY_SHAPE`（自动）形状归属 | **已确认：无 type/bbox 的形状属 `REPLY_SHAPE`（预设模式），含 type/bbox 的属 `AUTO_REPLY_SHAPE`（自动排版）——§6.2 附录中两行括注对调，已修正（动态回填）** |
| §3.2 Box 输出口（"与 Layout 同名子集推断 [中]"） | **已确认：`完整版式提示词/元素列表/版式预览图` 3 输出，恰为 Layout 前 3 项（动态回填）** |
| §3.2 `last_incoming` 归属（"隐藏"） | **已确认：在 optional 分组（非 hidden），multiline STRING 默认 ""（动态回填）**；"前端不显示"由其内部状态 tooltip 佐证 |
| §4 `DEFAULT_API_BASE_URL` 取值 [中] | **已确认：`https://teynex.com`（动态回填）** |
| §4 `DEFAULT_CONTEXT_LENGTH` 名值 | **已确认：8192（动态回填）** |
| §4 `_resolve_api_key` 具体 config 键名 | introspection 未采集 config 键名，保持未确认 |
| §4 预览图保存路径与文件名格式 | introspection 未采集，保持未确认 |
| §4 `thinking` 输入参数 | **已确认：运行时 INPUT_TYPES 无 `thinking` 参数（动态回填）**——该标识符非节点输入 |
