# TE_Batch_Tools.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_Batch_Tools`。静态分析（字符串 / 导入导出表 / 配套前端 `web/js/te_man_batch_tools.js` / README.md）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

**节点模块**（不在 `__init__.py` 的 `SKIP_MODULES` 中，会被加载器作为节点导入）。包含 3 个 ComfyUI 节点：
批量提示词卡片段落、批量图片列表段段、批量增强设置（共享调度参数）。README.md §4–6（"新增 TE MAN 批量提示词节点 / TE MAN 批量图片节点 / 新增批量增强设置节点"）与之一一对应 [高]。

与 **task_runner.pyd 的关系：无后端调用关系**。在本模块全部字节中检索 `task_runner`、`BatchGenerationRunner`、`Interrupt`、`ThreadPool`、`concurrent` 均 **0 命中**（bytecount 实测）[高]；
反向也成立：spec/task_runner.md 记录的调用方是 GPT_Image_2_Generator / Gemini_Imagen_Generator / Grok_Image_Generator，不含本模块。
两者的"批次"是两套独立机制 [高（字符串层面）/ 行为差异见 §1.2]：

| | task_runner.pyd | TE_Batch_Tools |
|---|---|---|
| 并发模型 | 进程内 ThreadPoolExecutor 一次队列并发跑任务 | 前端逐条入队（一次排队一条，循环 N 次） |
| 位置 | 后端 Python | 前端 JS `te_man_batch_tools.js`（扩展名 `TE.ManBatchTools`，JS import 串直接证据） |
| 中断 | 后端 InterruptProcessingException | 前端 `__teBatchStopRequested` 旗标 + DELETE /queue 清空未开始任务 |

即：本模块的"批量执行"是 **前端逐条提交调度**，task_runner 的线程池批次并发与它互不引用 [高]。

## 2. Python API

- 导出：`PyInit_TE_Batch_Tools`（PE 导出表唯一导出符号）。
- 原始源码路径（编译期嵌入）[高]：
  - `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Batch_Tools.c`
  - `custom_nodes/TE_image/source_py_backup/TE_Batch_Tools.py`
  - 原包名 `custom_nodes.TE_image`，现打包为 TE_MAN。
- 模块级函数（qualname 串直接证据）[高]：
  - `_clean_prompt_line(str)` —— 清洗单条提示词行（去 bullet/序号前缀，见 §4.1）
  - `_prompts_from_json_data(...)` —— 从 JSON 卡片数据提取提示词列表
  - `parse_batch_prompts(...)` —— 统一提示词解析入口（JSON 卡片 / 逐行 / `---` 分段 / 代码围栏）
  - `_normalize_index(index, total)` —— 参数名直证 [高]；越界/负数校验（见 §5 错误）
  - `_parse_image_list(image_list, max_images)` —— 参数名直证 [高]
  - `_filename_stem(name)` —— 取不带扩展名的文件名（tooltip 级证据："输出用不带后缀的文件名；加载仍用完整 name"）
- 节点类（qualname 串）[高]：`TEMANBatchPromptNode`、`TEMANBatchImageNode`、`TEMANBatchEnhancedSettingsNode`
- 模块级常量名 [高]：`BATCH_SETTINGS_TYPE`、`BATCH_SCOPE_OPTIONS`（与 `只执行当前线` / `执行整个工作流` 两个串并存）。
- ComfyUI 注册（键名 + 显示名 + CATEGORY 均为字面串）[高]：

| NODE_CLASS_MAPPINGS 键 | 显示名（NODE_DISPLAY_NAME_MAPPINGS） | CATEGORY |
|---|---|---|
| `TE_MAN_Batch_Prompt` | `TE MAN 批量提示词` | `TE MAN/Batch` |
| `TE_MAN_Batch_Image` | `TE MAN 批量图片` | `TE MAN/Batch` |
| `TE_MAN_Batch_Enhanced_Settings` | `TE MAN 批量增强设置` | `TE MAN/Batch` |

自定义 IO 类型 [高]：`TE_BATCH_ENHANCED_SETTINGS`（增强设置节点输出 / 批量节点可选输入 `增强设置`）。前端常量 `SETTINGS_NODE='TE_MAN_Batch_Enhanced_Settings'` 与之互证。

## 3. 节点规格

### 3.1 TEMANBatchPromptNode（TE_MAN_Batch_Prompt）

- FUNCTION：`get_prompt` [高]；另有 `IS_CHANGED`、`VALIDATE_INPUTS` [高]。
- DESCRIPTION：`TE MAN 批量提示词：卡片式管理多条提示词，可单项执行或批量执行` [高]。
- 输入参数（名称全部为字面串；槽位归类 [中]）：

| 名称 | 推断类型 | 证据 / 备注 | 置信度 |
|---|---|---|---|
| `prompts_json` | STRING（`default:"[]"`，**hidden: true**，由前端注入） | 前端 `setWidgetValue(node,'prompts_json',JSON.stringify(cards))`、`getPromptItems()`；错误串 `prompts_json 不是有效 JSON` | [高]（动态回填全证实） |
| `index` | INT（default 0，min 0，max 100000，step 1） | 前端逐条执行时写入该值；`_normalize_index(index,total)` | 已确认（动态回填） |
| `最大任务数` | INT（default 100，min 1，max 10000，step 1，tooltip `批量执行时前端用于防止误提交过多任务。`） | 前端 `makeBoundNumber(...,'最大任务数',100,1,10000)` | 已确认（动态回填） |
| `增强设置`（optional，`forceInput: true`） | `TE_BATCH_ENHANCED_SETTINGS` | tooltip `可连接 TE MAN 批量增强设置，控制执行范围、间隔、续跑编号和随机顺序。` | 已确认（动态回填） |
| `prompts`（optional，`forceInput: true`） | STRING | tooltip `可选上游文本。支持一行一条、编号列表或 JSON 数组。`——**实测键名为 `prompts` 而非 `raw_text`** | 已确认（动态回填，更正键名） |

> 动态回填更正：批量节点自身的 INPUT_TYPES 中**没有** `执行范围` COMBO（`只执行当前线/执行整个工作流` 只出现在增强设置节点，见 §3.3）；`raw_text` 推断键名不成立，实际为 optional 输入口 `prompts`（forceInput）。`prompts_json` 与 `image_list` 带 `hidden: true` 标记（隐藏 widget、由前端序列化注入）。

- 返回：已确认 `RETURN_TYPES = ("STRING", "STRING")`、`RETURN_NAMES = ("输出提示词", "编号")`（动态回填）——即除提示词外还返回第二输出口"编号"。
- 行为（依前端 + 后端函数名综合）：
  1. 前端卡片 UI（新增/导入/txt分割导入/导入txt文件夹/清空）把卡片列表序列化进 `prompts_json`；`prompts_json` 支持 JSON 数组、逐行文本、`---` 分隔大段、\`\`\`json 围栏（JS 提示符串 `\n/ JSON / --- `）[高（前端串）]。
  2. 每次排队前，前端把本次 item 的编号写入 `index` widget，再 graphToPrompt 入队 [高（JS）]。
  3. 后端 `get_prompt` 用 `parse_batch_prompts` 解析出列表，`_normalize_index` 校验 `index`，返回第 index 条（`_clean_prompt_line` 已在前端做同样清洗，两边冗余实现同一正则）[中]。
- IS_CHANGED：`hashlib`/`sha256`/`hexdigest`/`encode`/`utf-8` 串齐全，推断返回输入串（prompts_json+index 等）的 SHA256 hexdigest 作为缓存键 [中]。

### 3.2 TEMANBatchImageNode（TE_MAN_Batch_Image）

- FUNCTION：`load_image` [高]；内部 `_load_one`（含 `<lambda>`）[高]；`IS_CHANGED`、`VALIDATE_INPUTS`（含 genexpr）[高]。
- DESCRIPTION：`TE MAN 批量图片：多图列表管理，可单项执行或批量执行` [高]。
- 输入参数：

| 名称 | 推断类型 | 证据 / 备注 | 置信度 |
|---|---|---|---|
| `image_list` | STRING（multiline，default ""，**hidden: true** 由前端注入） | tooltip `编号列表或 JSON 数组`；前端 `getImageNames/setImageNames` 按行 join；`_parse_image_list(image_list, max_images)` | 已确认（动态回填） |
| `index` | INT（default 0，min 0，max 100000，step 1） | 同 3.1；`_normalize_index` | 已确认（动态回填） |
| `max_images` | INT（default 0，min 0，max 100000，step 1，tooltip `0 表示不限制。`） | 0 为哨兵值 | 已确认（动态回填） |
| `最大任务数` | INT（default 100，min 1，max 10000，step 1） | 同 3.1 | 已确认（动态回填） |
| `增强设置`（optional，`forceInput: true`） | `TE_BATCH_ENHANCED_SETTINGS` | 同 3.1 | 已确认（动态回填） |

> 动态回填更正：批量图片节点同样**没有** `执行范围` 输入。

- 返回：已确认 `RETURN_TYPES = ("IMAGE", "STRING", "STRING")`、`RETURN_NAMES = ("输出图片", "图片文件名", "编号")`（动态回填）；tooltip `输出用不带后缀的文件名；加载仍用完整 name`（用于把文件名喂给保存节点当动态文件名，README §7 "保存文件名"输入口与之衔接）。
- 行为：
  - `VALIDATE_INPUTS`（genexpr）对名单逐项用 `folder_paths.exists_annotated_filepath`/`isfile` 校验，失败报 `图片不存在：…` [高名称]。
  - `load_image` 按 `index` 取一项：`get_annotated_filepath` → `open` → PIL 载入，失败报 `图片读取失败：…`；多帧图支持迹象：`ImageSequence`、`frames`、`width`/`height`、`torch`/`cat`/`dim`（多帧拼接张量）[低-中，未确认细节]。
  - 解析失败/空列表报 `没有找到有效图片` 或 `TE MAN 批量图片为空`。
- IS_CHANGED：同 3.1 的 SHA256 方案 [中]。

### 3.3 TEMANBatchEnhancedSettingsNode（TE_MAN_Batch_Enhanced_Settings）

- FUNCTION：`build_settings` [高]。
- DESCRIPTION：已确认完整原文 = `TE MAN 批量增强设置：连接到批量提示词/批量图片节点，控制批量执行范围、间隔、续跑编号和随机顺序。`（动态回填，含顿号"间隔"与句号）。
- 输入参数：**控件名即为中文串**（JS 按名读值 `getWidgetValue(节点,'执行范围'...)` 直证）[高]：

| 控件名 | 推断类型 | tooltip（字面串） | 置信度 |
|---|---|---|---|
| `执行范围` | COMBO：`只执行当前线` / `执行整个工作流`（default `只执行当前线`） | `默认只执行当前批量节点连接出去的流程；需要全工作流时改为执行整个工作流。` | 已确认（动态回填） |
| `从指定编号继续` | INT（default 1，min 1，max 100000，step 1） | `从第几个编号开始批量执行。1 表示从第一项开始。` | 已确认（动态回填） |
| `随机编号执行` | BOOLEAN（default false） | `开启后，在当前范围内随机顺序提交。` | 已确认（动态回填） |
| `执行间隔时间` | FLOAT（default 0.0，min 0.0，max 86400.0，step 0.1） | `每提交 1 个任务后等待的秒数。0 表示立即提交下一个。` | 已确认（动态回填） |

> 动态回填更正：增强设置节点的 INPUT_TYPES 只有上述 4 个 required 控件，**不含** `最大任务数`——该控件属于批量提示词/批量图片节点（default 100）。`BATCH_SETTINGS_TYPE = "TE_BATCH_ENHANCED_SETTINGS"`、`BATCH_SCOPE_OPTIONS = ["只执行当前线", "执行整个工作流"]` 两常量实测证实。

- 输出：类型 `TE_BATCH_ENHANCED_SETTINGS`；输出名已确认 = `增强设置`（动态回填）。
- 行为（README §6）：节点本身不做调度，只把 5 个参数打包（`build_settings`）。**实际消费主要发生在前端**：JS 沿批量节点 `增强设置` 输入的 link 找到该节点，读上述 5 个 widget 值，组装内部对象 `{intervalSeconds, startNumber, random, scope, connected}` 驱动批量入队 [高（JS 反编译片段直证）]。后端 `build_settings` 返回的字典被谁读取：未确认——池中英文键 `scope`/`start_number`/`interval`/`selected`/`max_images` 存在 [高（串）]，但它们更像 settings 字典的键；`TE_BATCH_ENHANCED_SETTINGS` 字符串全仓库只出现在本 .pyd 内（grep 实测），无其他节点消费迹象。

## 4. 关键行为细节（前端口径，均为 JS 直证）

### 4.1 提示词解析规则（前后端同源实现）

后端 `_clean_prompt_line` 内嵌正则（字节级还原）[高]：

```text
^\s*(?:[-*•]\s+|\d{1,4}[.、）]\s*|[一二三四五六七八九十百]+[、.)）]\s*)
^\s*-{3,}\s*$          # `---` 分段分隔线
```(?:json)?\s*(.*?)``` # 代码围栏提取 JSON（配 DOTALL/IGNORECASE 串）
```

即：卡片 JSON 数组 / 逐行文本 / `- `、`1.`、`1、`、`一、`等 bullet/序号清洗、`---` 分大段、\`\`\`json\`\`\` 围栏均支持。前端 JS 内有一字不差的同一正则（`'...[.)、）]\s*|[一二三四五六七八九十百]+[、.)）]\s*)/;return ...replace...'` 直证）[高]。

### 4.2 批量执行流程（前端扩展 `TE.ManBatchTools`）

1. UI：批量/单选执行、新增卡片、导入文本、txt分割导入、导入txt文件夹、添加图片/文件夹（`webkitdirectory`，深度 `FOLDER_IMAGE_MAX_DEPTH=5`）、清空、停止执行 [高（按钮字面串）]。
2. `getBatchSettings`：优先读连接的增强设置节点 widget，否则退回批量节点自带 widget；产出 `{intervalSeconds, startNumber, random, scope, connected}` [高]。
3. 批量执行：从 `startNumber`(1 基) 开始逐条：写入 `index` widget → scope==`只执行当前线` 时 `prunePromptToConnectedLine` 把 graphToPrompt 裁剪成语图分支（console 输出 `[TE MAN Batch] connected-line scope {label, sourceId, before, after}`）→ `api.queuePrompt(-1, prompt)` → 每条间隔 `max(60ms?..., intervalSeconds)`（`MIN_QUEUE_YIELD_MS=0x50`）→ 状态栏 `已提交 n/n条，间隔 Ns` [高（JS 串）]。
4. `random`：浏览器 Fisher-Yates 洗牌（`Math.random` 交换循环直证）；`最大任务数` 截断条数并告警 `… 个任务，超过最大任务数 …` [高]。
5. 停止：置 `__teBatchStopRequested`，并通过 `GET /queue` 找 `queue_pending` 的 `prompt_id`、`DELETE /queue` 清掉未开始任务，状态 `已清空提示词` / `没有可执行提示词`（README §4 "点停止执行会自动清理未开始的任务"）[高]。所有已提交 prompt_id 记在 `__teBatchSubmittedPromptIds` [高]。
6. 图片上传走 ComfyUI 标准接口：`POST /upload/image`（multipart `image/*`）、缩略图 `GET /view?filename=…&type=input` [高]。

## 5. 错误处理与用户可见文案

| 消息 | 触发场景 | 置信度 |
|---|---|---|
| `TE MAN 批量提示词为空` / `TE MAN 批量图片为空` | 列表无任何条目 | [高]（原文串） |
| `prompts_json 不是有效 JSON` | VALIDATE_INPUTS 阶段 json.loads 失败 | [高] |
| `图片不存在：…` | VALIDATE_INPUTS 中某文件名过不了 `exists_annotated_filepath/isfile`（genexpr 遍历） | [高]名称，[中]格式 |
| `图片读取失败：…` | load_image 打开/解码失败 | [高] |
| `没有找到有效图片` | `_parse_image_list` 过滤后为空 | [高] |
| `index must be >= 0` / `index out of range (0..` | `_normalize_index(index,total)` 对负数/越界抛 ValueError（后者为 f-string 截断） | [高] |
| 前端提示（JS）：`已清空提示词` / `没有可执行提示词` / `…条，当前第…` / `…个任务，超过最大任务数…` / `…张，点击 单选执行 才会执行` | 批量执行/停止/选择状态 | [高] |

## 6. 证据附录

### 6.1 源路径与 qualname（ASCII）

```text
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Batch_Tools.c
custom_nodes/TE_image/source_py_backup/TE_Batch_Tools.py
custom_nodes.TE_image.TE_Batch_Tools._clean_prompt_line
custom_nodes.TE_image.TE_Batch_Tools._prompts_from_json_data
custom_nodes.TE_image.TE_Batch_Tools.parse_batch_prompts
custom_nodes.TE_image.TE_Batch_Tools._normalize_index
custom_nodes.TE_image.TE_Batch_Tools._parse_image_list
custom_nodes.TE_image.TE_Batch_Tools._filename_stem
custom_nodes.TE_image.TE_Batch_Tools.TEMANBatchPromptNode.INPUT_TYPES / .get_prompt / .IS_CHANGED / .VALIDATE_INPUTS
custom_nodes.TE_image.TE_Batch_Tools.TEMANBatchImageNode.INPUT_TYPES / ._load_one(.lambda) / .load_image / .IS_CHANGED / .VALIDATE_INPUTS(.genexpr)
custom_nodes.TE_image.TE_Batch_Tools.TEMANBatchEnhancedSettingsNode.INPUT_TYPES / .build_settings
```

### 6.2 注册与类型常量（ASCII，去噪分组）

```text
注册:  NODE_CLASS_MAPPINGS  NODE_DISPLAY_NAME_MAPPINGS  CATEGORY  FUNCTION  DESCRIPTION
       TE_MAN_Batch_Prompt  TE_MAN_Batch_Image  TE_MAN_Batch_Enhanced_Settings  TE_MAN/Batch
类型:  STRING  INT  FLOAT  BOOLEAN  IMAGE  MULTILINE  TE_BATCH_ENHANCED_SETTINGS  BATCH_SETTINGS_TYPE
IO键:  raw_text  prompts_json  image_list  max_images  index  增强设置(required/optional/forceInput/tooltip/multiline/hidden/default 共现)
正则:  ```(?:json)?\s*(.*?)```   ^\s*-{3,}\s*$
       ^\s*(?:[-*\x{2022}]\s+|\d{1,4}[.、）]\s*|[一二三四五六七八九十百]+[、.)）]\s*)   （字节级还原 [高]）
导入:  json/loads  hashlib/sha256/hexdigest  PIL(Image/ImageOps/exif_transpose/ImageSequence/MPO)
       numpy(from_numpy/astype/float32)  torch(Tensor/from_numpy/cat/dim)  folder_paths(get_annotated_filepath/exists_annotated_filepath)
       node_helpers  inspect/asyncio.coroutines 等为 Cython 运行时噪音 [中]
其他键: scope  start_number  interval  selected  safe_index   max_images
       （作用未确认；`selected`/`safe_index` 无调用方证据）
```

### 6.3 中文文案（UTF-8 扫描原文）

```text
TE MAN 批量提示词 / TE MAN 批量图片 / TE MAN 批量增强设置
TE MAN 批量提示词：卡片式管理多条提示词，可单项执行或批量执行
TE MAN 批量图片：多图列表管理，可单项执行或批量执行
TE MAN 批量增强设置：连接到批量提示词/批量图片节点，控制批量执行范围
续跑编号和随机顺序
执行范围 / 只执行当前线 / 执行整个工作流
默认只执行当前批量节点连接出去的流程；需要全工作流时改为执行整个工作流
从指定编号继续 / 从第几个编号开始批量执行 / 1 表示从第一项开始
随机编号执行 / 开启后，在当前范围内随机顺序提交
执行间隔时间 / 每提交 1 个任务后等待的秒数 / 0 表示立即提交下一个
最大任务数 / 批量执行时前端用于防止误提交过多任务 / 0 表示不限制
可选上游文本 支持一行一条 / 编号列表或 JSON 数组
输出提示词 / 输出图片 / 图片文件名
输出用不带后缀的文件名；加载仍用完整 name
增强设置 / 可连接 TE MAN 批量增强设置，控制执行范围
错误:  TE MAN 批量提示词为空  TE MAN 批量图片为空  prompts_json 不是有效 JSON
       图片不存在：  图片读取失败：  没有找到有效图片
       index must be >= 0  index out of range (0..
```

### 6.4 前端佐证（web/js/te_man_batch_tools.js，PB 字符串表与明文 CSS/HTML）

```text
EXTENSION_NAME='TE.ManBatchTools'  PROMPT_NODE/IMAGE_NODE(=TE_MAN_Batch_Prompt/Image)  SETTINGS_NODE='TE_MAN_Batch_Enhanced_Settings'
SCOPE_CURRENT_LINE='只执行当前线'  SCOPE_FULL_WORKFLOW='执行整个工作流'
控件读取: getWidgetValue(节点,'随机编号执行',false) … 组装 {'intervalSeconds','startNumber','random','scope','connected'}
执行: ['index']=…,prunePromptToConnectedLine(…) → api.queuePrompt(-1,prompt) → '[TE MAN Batch] connected-line scope'
     状态 '已提交 '+(…)…，间隔 '…s'  ;  MIN_QUEUE_YIELD_MS=0x50
停止: __teBatchStopRequested  __teBatchSubmittedPromptIds  GET /queue → queue_pending/prompt_id → DELETE /queue（'删除排队提示词失败'）
按钮: 批量执行 单选执行 新增卡片 导入文本 txt分割导入 导入txt文件夹 添加图片 添加文件夹 清空 停止执行
     '已清空提示词' '没有可执行提示词' '…个任务，超过最大任务数…' '…张，点击 单选执行 才会执行'
上传: POST /upload/image  /view?filename=&type=input  webkitdirectory  FOLDER_IMAGE_MAX_DEPTH=0x5
隐藏widgets: hideWidgets(Prompt节点,['prompts_json','index','执行范围','最大任务数'])
            hideWidgets(Image节点, ['image_list','index','max_images','执行范围','最大任务数'])
```

### 6.5 与 task_runner 关系的复核命令

```bash
python -c "data=open('TE_Batch_Tools.pyd','rb').read();print([t for t in [b'task_runner',b'BatchGenerationRunner',b'Interrupt',b'ThreadPool',b'concurrent'] if t in data])"
# 期望输出 [] —— 两个"批次"机制互不引用
```

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 2025 Server + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载 `TE_MAN` 包后的运行时 introspection（module 显示为 `custom_nodes.TE_image.TE_Batch_Tools`，TE_image 为插件原名）。以下为节点定义的运行时精确值。

### 7.1 TEMANBatchPromptNode（TE_MAN_Batch_Prompt）

- FUNCTION=`get_prompt`；CATEGORY=`TE MAN/Batch`；DESCRIPTION=`TE MAN 批量提示词：卡片式管理多条提示词，可单项执行或批量执行。`；`has_IS_CHANGED=true`、`has_VALIDATE_INPUTS=true`（§3.1 的 IS_CHANGED/VALIDATE_INPUTS 推断证实）；无 OUTPUT_NODE；无 `has_check_lazy_status`/`has_on_execute`。
- RETURN_TYPES=`("STRING","STRING")`，RETURN_NAMES=`("输出提示词","编号")`。
- INPUT_TYPES（required）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `prompts_json` | STRING | `default="[]"`，**hidden=true** |
| `index` | INT | default 0，min 0，max 100000，step 1 |
| `最大任务数` | INT | default 100，min 1，max 10000，step 1，tooltip=`批量执行时前端用于防止误提交过多任务。` |

- INPUT_TYPES（optional）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `增强设置` | TE_BATCH_ENHANCED_SETTINGS | forceInput=true，tooltip=`可连接 TE MAN 批量增强设置，控制执行范围、间隔、续跑编号和随机顺序。` |
| `prompts` | STRING | forceInput=true，tooltip=`可选上游文本。支持一行一条、编号列表或 JSON 数组。` |

- hidden 输入：`prompts_json`（hidden 标记，前端注入卡片 JSON）。

### 7.2 TEMANBatchImageNode（TE_MAN_Batch_Image）

- FUNCTION=`load_image`；CATEGORY=`TE MAN/Batch`；DESCRIPTION=`TE MAN 批量图片：多图列表管理，可单项执行或批量执行。`；`has_IS_CHANGED=true`、`has_VALIDATE_INPUTS=true`；无 OUTPUT_NODE。
- RETURN_TYPES=`("IMAGE","STRING","STRING")`，RETURN_NAMES=`("输出图片","图片文件名","编号")`。
- INPUT_TYPES（required）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `image_list` | STRING | multiline=true，default=""，**hidden=true** |
| `index` | INT | default 0，min 0，max 100000，step 1 |
| `max_images` | INT | default 0，min 0，max 100000，step 1，tooltip=`0 表示不限制。` |
| `最大任务数` | INT | default 100，min 1，max 10000，step 1，tooltip=`批量执行时前端用于防止误提交过多任务。` |

- INPUT_TYPES（optional）：`增强设置`（TE_BATCH_ENHANCED_SETTINGS，forceInput=true，tooltip 同 7.1）。
- hidden 输入：`image_list`。

### 7.3 TEMANBatchEnhancedSettingsNode（TE_MAN_Batch_Enhanced_Settings）

- FUNCTION=`build_settings`；CATEGORY=`TE MAN/Batch`；DESCRIPTION=`TE MAN 批量增强设置：连接到批量提示词/批量图片节点，控制批量执行范围、间隔、续跑编号和随机顺序。`；`has_IS_CHANGED=false`、`has_VALIDATE_INPUTS=false`；无 OUTPUT_NODE。
- RETURN_TYPES=`("TE_BATCH_ENHANCED_SETTINGS",)`，RETURN_NAMES=`("增强设置",)`。
- INPUT_TYPES（全部 required，无 optional、无 hidden）：

| 参数 | 类型 | 附加属性 |
|---|---|---|
| `执行间隔时间` | FLOAT | default 0.0，min 0.0，max 86400.0，step 0.1，tooltip=`每提交 1 个任务后等待的秒数。0 表示立即提交下一个。` |
| `从指定编号继续` | INT | default 1，min 1，max 100000，step 1，tooltip=`从第几个编号开始批量执行。1 表示从第一项开始。` |
| `随机编号执行` | BOOLEAN | default false，tooltip=`开启后，在当前范围内随机顺序提交。` |
| `执行范围` | COMBO `["只执行当前线","执行整个工作流"]` | default=`只执行当前线`，tooltip=`默认只执行当前批量节点连接出去的流程；需要全工作流时改为执行整个工作流。` |

### 7.4 模块常量实锤值

| 常量 | 实测值 |
|---|---|
| `BATCH_SETTINGS_TYPE` | `"TE_BATCH_ENHANCED_SETTINGS"` |
| `BATCH_SCOPE_OPTIONS` | `["只执行当前线","执行整个工作流"]` |
| `NODE_CLASS_MAPPINGS` | `TE_MAN_Batch_Prompt / TE_MAN_Batch_Image / TE_MAN_Batch_Enhanced_Settings` → 三个类（键名与 §2 表完全一致） |
| `NODE_DISPLAY_NAME_MAPPINGS` | `TE MAN 批量提示词` / `TE MAN 批量图片` / `TE MAN 批量增强设置` |
| `function_docs._filename_stem` | `"输出用不带后缀的文件名；加载仍用完整 name。"`（§3.2 tooltip 归属证实） |

### 7.5 对正文"未确认"项的核对结论

| 正文位置 | 结论 |
|---|---|
| §3.1 返回"是否还返回 index/total：未确认" | 已确认：两输出口 `输出提示词`+`编号`（动态回填） |
| §3.1 `raw_text` 键名推断 | 不成立：实际 optional 输入口键名为 `prompts`（forceInput） |
| §3.1/3.2 `执行范围` COMBO 归属批量节点 [中] | 不成立：批量节点无此输入，只存在于增强设置节点 |
| §3.1/3.2 `index`、`最大任务数` 类型/默认值 [中] | 已确认（见 7.1/7.2 全表） |
| §3.2 返回类型 `("IMAGE","STRING")` [中] | 已确认，实为三输出口，末位 `编号`（动态回填） |
| §3.3 输入含 `最大任务数` | 不成立：增强设置节点仅 4 个控件 |
| §3.3 "输出名未确认" | 已确认：`增强设置`（动态回填） |
| §3.3 "后端 build_settings 返回的字典被谁读取：未确认" | 保留未确认（introspection 不含调用关系） |
| §3.1/3.2 IS_CHANGED=SHA256 方案 [中] | 部分证实：has_IS_CHANGED=true，具体哈希实现 introspection 不可见 |
| §6.2 "scope/start_number/interval/selected/safe_index 作用未确认" | 保留未确认（动态数据不含内部字典键用途） |
