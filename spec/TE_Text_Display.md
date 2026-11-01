# TE_Text_Display.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_Text_Display`。静态分析（字符串/导入导出表），并对照同包明文前端 `web/js/te_text_display.js`（其混淆字符串表中保留 `TE_text_display`、`te_text_display_saved_text` 等明文常量，可交叉验证后端字符串）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

TE MAN 插件的**ComfyUI 节点模块**（不在 `__init__.py` SKIP_MODULES 中）——「文本展示」节点：在工作流画布上查看、编辑文本并继续作为文本输出。README v3.8 更新日志：「新增 **TE MAN TEXT文本展示** 节点，可在工作流里直接查看、编辑、复制、粘贴文本，并继续作为文本输出连接到其他节点。节点内置横排快捷按钮」（README.md L283）[高]。
原始编译路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Text_Display.c`，模块限定名 `custom_nodes.TE_image.TE_Text_Display` [高]。

## 2. Python API

- 导出：`PyInit_TE_Text_Display`（唯一导出符号）[高]；导入仅 `python3.dll / KERNEL32 / VCRUNTIME140 / api-ms-win-crt-runtime`，无网络/文件专项 API [高]。
- 模块级工具函数（qualname 字符串直接证据）[高]：
  - `_normalize_text`（内含 `<locals>.genexpr` 生成器表达式，用于递归/规范化文本，如把列表拼接为多行——对照 JS 版 `normalizeText` 的 `Array.isArray → map → join('\n')` 行为，[中]）
  - `_text_signature`（未确认——推测为生成文本指纹/签名串的辅助函数，仅名字符证据）
  - `_first_dict`（未确认——按函数名推测：从若干候选 dict（如 `extra_pnginfo` / `workflow`）中取第一个可用 dict）
  - `_normalize_unique_id`（未确认）
  - `_update_execution_metadata`（执行时把文本写入工作流元数据，见 §3.3）
- 模块引用的第三方/标准库（字符串证据）：`inspect`、`logging` / `getLogger`、`hashlib` / `sha256` / `hexdigest` [高]；`logger`、`disable` 字符串存在，是否为模块级 logger 实例未确认。
- **ComfyUI 节点注册** [高]：
  - `NODE_CLASS_MAPPINGS`：`"TE_text_display"` → 类 `TETextDisplayNode`
  - `NODE_DISPLAY_NAME_MAPPINGS`：`"TE_text_display"` → `"TE MAN TEXT文本展示"`
  - `CATEGORY`：`"TE MAN/Utils"`
  - `FUNCTION`：`show_text`；`OUTPUT_NODE = True`（字符串 `OUTPUT_NODE` 存在；前端 `onExecuted` 消费其 ui 载荷 [中]）
  - `RETURN_TYPES`：**已确认 `("STRING",)`**，`RETURN_NAMES`：**已确认 `("text",)`（动态回填）**——早先据 `output_text` 字符串推断的口名 `("output_text",)` 不成立，实际口名为 `text`。

## 3. 节点规格：TETextDisplayNode

### 3.1 输入（INPUT_TYPES）

`INPUT_TYPES`、`required`、`optional`、`hidden`、`STRING`、`BOOLEAN`、`multiline`、`forceInput`、`default`、`tooltip` 等键全部在二进制中出现 [高]；**各参数归属已由动态 introspection 全部实锤（动态回填，全表见 §7.1）**：

- `input_text` — `STRING`，optional，**已确认 `forceInput: True`（动态回填）**。tooltip 原文：「可选上游文本。连接后优先显示并输出这里的内容。」[高]（该 tooltip 与 `unique_id`、`TE_text_display`、`throw` 相邻；前端 `hasUpstreamText` 检查 `node.inputs.some(i => i.name === 'input_text' && i.link != null)` 证实 input_text 是 socket 名 [高，JS]）
- `text` — `STRING`，required，`{"multiline": True, "default": ''}` **已确认（动态回填）**，tooltip 原文：「节点内文本。未连接 input_text 时会作为输出文本。」[高]（tooltip 内含 ` input_text ` 占位，二进制中单独出现该片段）
- `use_edited_text` — `BOOLEAN`，optional，**已确认默认 `False`（动态回填）**（`BOOLEAN` + `default` 字符串；JS 中 `OVERRIDE_WIDGET_NAME='use_edited_text'` 的控件被创建后隐藏，且 `value===true` 时被重置为 `false` [高，JS]）
- `edited_from_text` — `STRING`，optional，**已确认默认 `''`（单行、非 multiline、非 forceInput）（动态回填）**（JS 中 `EDITED_FROM_WIDGET_NAME='edited_from_text'`，同样被隐藏并被 `widgets_values=[text, false, edited_from_text]` 序列化 [高，JS]）
- **hidden**：**已确认 `{"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"}`（动态回填）**——两项同时存在，完整清单就此闭合。

### 3.2 执行（show_text / FUNCTION）

日志格式串原文：`"TE Text Display execute node=%s selected=%s text=[%s] input_text=[%s] edited_from=[%s] output=[%s]"` [高]。
行为推断（`selected`,`text`,`input_text`,`edited_from` 四值组合 + tooltip 文案）：

1. **文本选择**：`input_text` 有连接时优先采用其内容（「连接后优先显示并输出这里的内容」[高]），否则用节点内 `text`（「未连接 input_text 时会作为输出文本」[高]）。`selected` 字段即所选来源（值域未确认；JS 端 `widgets_values` 第二位 `use_edited_text=False` 会在执行后被重置，推测与"编辑内容 vs 上游内容"的选择有关 [低]——具体语义未确认）。
2. **返回**：`{"ui": {"text": 显示文本, "input_text": 上游原文}, "result": (output_text,)}` [中]（证据：`ui` 字符串紧邻 `UNIQUE_ID`/`OUTPUT_NODE`；JS `onExecuted` 调 `extractExecutedText(payload, <默认键>)` 与 `extractExecutedText(payload, 'input_text')` 取回两值并做对照/预览写入 [高，JS]；默认键按 JS 用途推断为 `"text"` [中]）。`output_text` 作为 RETURN 输出供下游节点连接 [高]。
3. **元数据回写** `_update_execution_metadata`：把当前文本写入 `extra_pnginfo["workflow"]["nodes"][*]["properties"]` 下键 `te_text_display_saved_text` / `te_text_display_preview_text` / `te_text_display_source_text`（SERIALIZED_TEXT_KEY / SERIALIZED_PREVIEW_KEY / SERIALIZED_SOURCE_KEY，与 JS 中同名字面量完全一致 [高]；写法路径为推断 [中]）。作用：保存的工作流 JSON 里持久保留节点文本（前端据此实现 onConfigure 恢复）[中，JS]。

### 3.3 IS_CHANGED（缓存控制）

- 格式串原文：`"TE Text Display IS_CHANGED node=%s input_text=%s text=[%s] edited_from=[%s] fingerprint=[%s]"` [高]。
- `input_text` 未解析时打印占位串 `"unavailable (linked inputs are not resolved here)"` [高]。
- 指纹算法：`hashlib.sha256(...text/edited_from/unique_id...).hexdigest()` [中]（`hashlib`、`sha256`、`hexdigest`、`encode`、`utf-8`、`changed_value`、`fingerprint` 字符串齐备；参与哈希的字段组合与返回"恒变/不变"策略未确认。`changed_value` 字符串暗示可能返回哨兵对象 `<>` 以强制每次执行——用于让画布文本每次刷新/编辑即时生效，[低]）。

## 4. 外部依赖与副作用

- **无网络端点、无认证、无文件系统读写** [高]：导入表无 WS2_32/ADVAPI32，字符串中无 URL/API Key/config 键。
- 唯一副作用是把文本写入工作流元数据（`extra_pnginfo` → `workflow → nodes → properties`）[中]。
- 第三方库迹象：仅标准库 `inspect / logging / hashlib` [高]。
- **前端配套逻辑**（`web/js/te_text_display.js`，与后端共享常量）[高，JS]：
  - 文本控件名 `text`；隐藏控件 `use_edited_text`、`edied_from_text`（原文 `edited_from_text`）；
  - 序列化键 `te_text_display_saved_text`（保存文本）、`te_text_display_preview_text`（预览文本）、`te_text_display_source_text`（上游原文）、`te_text_display_edited_from_text`（编辑所基于的原文）；
  - 节点内横排动作条 `te_text_display_action_bar`：按钮「复制」「粘贴」「清空」「加入素材库」（后者调用 `window.TEImageAssetLibrary.addNodeTextToLibrary`，未就绪时弹窗「素材库前端还没准备好，请刷新页面后重试。」）；
  - `onExecuted` 上预览后端返回文本；上游断开时 `onConnectionsChange` 清除预览；`serialize` 时回写序列化键。

## 5. 错误处理与用户可见文案

无后端异常消息证据（除 Cython 运行时错误模板外，无任何 `try/except` 相关中文文案）[高]。用户可见文案汇总：

| 文案 | 位置/场景 | 置信度 |
|---|---|---|
| 「显示、编辑并继续输出文本。可连接上游文本，也可直接在节点内输入。」 | `__doc__`（类或模块 docstring） | [高] |
| 「TE MAN TEXT文本展示」 | NODE_DISPLAY_NAME_MAPPINGS 显示名 | [高] |
| 「可选上游文本。连接后优先显示并输出这里的内容。」 | `input_text` tooltip | [高] |
| 「节点内文本。未连接 input_text 时会作为输出文本。」 | `text` tooltip | [高] |
| `unavailable (linked inputs are not resolved here)` | IS_CHANGED 日志中 input_text 占位 | [高] |
| `TE Text Display IS_CHANGED node=%s input_text=%s text=[%s] edited_from=[%s] fingerprint=[%s]` | IS_CHANGED 调试日志 | [高] |
| `TE Text Display execute node=%s selected=%s text=[%s] input_text=[%s] edited_from=[%s] output=[%s]` | show_text 调试日志 | [高] |

## 6. 证据附录

**注册/映射**：`TE_text_display`、`TETextDisplayNode`、`NODE_CLASS_MAPPINGS`、`NODE_DISPLAY_NAME_MAPPINGS`、`TE MAN TEXT文本展示`、`TE MAN/Utils`、`INPUT_TYPES`、`CATEGORY`、`FUNCTION`、`show_text`、`TETextDisplayNode.show_text`、`TETextDisplayNode.IS_CHANGED`、`TETextDisplayNode.INPUT_TYPES`、`OUTPUT_NODE`、`RETURN_TYPES`、`RETURN_NAMES`、`output_text`、`STRING`、`BOOLEAN`。

**方法/工具函数 qualname**：`custom_nodes.TE_image.TE_Text_Display._normalize_text`（及 `.genexpr`）、`._text_signature`、`._first_dict`、`._normalize_unique_id`、`._update_execution_metadata`；源路径 `custom_nodes/TE_image/source_py_backup/TE_Text_Display.py`；本地变量名证据：`self`、`cls`、`kwargs`、`value`、`edited`、`source_text`、`result`、`nodes`、`id`、`changed_value`、`available`、`upstream`、`item`。

**输入常量**：`input_text`、`text`、`use_edited_text`、`edited_from_text`、`multiline`、`forceInput`、`default`、`tooltip`、`required`、`optional`、`hidden`、`UNIQUE_ID`、`unique_id`、`EXTRA_PNGINFO`、`extra_pnginfo`、`workflow`、`properties`。

**序列化键（pyd 与 JS 字面量一致）**：`te_text_display_saved_text`、`te_text_display_preview_text`、`te_text_display_source_text`（+JS 侧 `te_text_display_edited_from_text`）。

**指纹/哈希**：`hashlib`、`sha256`、`hexdigest`、`encode`、`utf-8`、`changed_value`、`fingerprint=%s`（位于 IS_CHANGED 格式串内）。

**中文原文摘录**：
- `显示、编辑并继续输出文本。可连接上游文本，也可直接在节点内输入。`
- `可选上游文本。连接后优先显示并输出这里的内容。`
- `节点内文本。未连接 input_text 时会作为输出文本。`

**未确认项清单**：`_text_signature`/`_first_dict`/`_normalize_unique_id` 的具体实现与签名；`use_edited_text`/`edited_from_text` 的精确执行语义；IS_CHANGED 是否返回恒变哨兵。已由动态回填闭合：hidden 输入完整清单（`unique_id`+`extra_pnginfo`）；INPUT_TYPES 各参数类型/默认值/分组。另：ui 载荷默认键是否为 `"text"` 仍未确认（introspection 不采集运行期 ui 载荷）。

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows Server 2025 + ComfyUI（Python 3.13.16）真实环境 import 后的自省结果；运行时模块显示为 `custom_nodes.TE_image.TE_Text_Display`（`TE_image` 为插件原名），模块文件 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN\TE_Text_Display.pyd`。本节所有值均为运行时实锤。

### 7.1 节点 INPUT_TYPES 全表（实锤）

#### TE_text_display（TETextDisplayNode）

注册元数据：`FUNCTION = "show_text"`、`CATEGORY = "TE MAN/Utils"`、`OUTPUT_NODE = True`、`RETURN_TYPES = ["STRING"]`、`RETURN_NAMES = ["text"]`；**`has_IS_CHANGED = True`**（IS_CHANGED 存在于节点上，§3.3 的缓存控制判断成立）、无 VALIDATE_INPUTS / on_execute / check_lazy_status。节点 DESCRIPTION（原文）："显示、编辑并继续输出文本。可连接上游文本，也可直接在节点内输入。"显示名（node_display_name_mappings）：`TE MAN TEXT文本展示`。

**required**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `text` | STRING, multiline | — | `""` | 节点内文本。未连接 input_text 时会作为输出文本。 |

**optional**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `input_text` | STRING（forceInput=True） | — | — | 可选上游文本。连接后优先显示并输出这里的内容。 |
| `use_edited_text` | BOOLEAN | — | False | （无 tooltip） |
| `edited_from_text` | STRING（单行） | — | `""` | （无 tooltip） |

**hidden**：`{"unique_id": "UNIQUE_ID", "extra_pnginfo": "EXTRA_PNGINFO"}`——完整清单两项，与 §3.1 双侧字符串互证吻合。

### 7.2 模块常量实锤值（动态采集）

pyd 模块 `TE_MAN.TE_Text_Display`（module docstring 为 `null`）除注册表外的常量：`SERIALIZED_PREVIEW_KEY = "te_text_display_preview_text"`、`SERIALIZED_SOURCE_KEY = "te_text_display_source_text"`、`SERIALIZED_TEXT_KEY = "te_text_display_saved_text"`——与 §3.2 元数据回写三键完全一致（JS 侧第四键 `te_text_display_edited_from_text` 仍为前端独有）。

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2 `RETURN_NAMES` = `("output_text",)` [中→高] | **已确认：`("text",)`（动态回填）——`output_text` 口名推断不成立**（该字符串应属其它节点/前端） |
| §3.1 `input_text` forceInput [中] | **已确认：forceInput=True、optional（动态回填）** |
| §3.1 `text` 控件属性 [中] | **已确认：required、multiline、default ""（动态回填）** |
| §3.1 `use_edited_text` 默认 False [中] | **已确认（动态回填）** |
| §3.1 `edited_from_text` 默认 '' [中] | **已确认：optional、单行 STRING、默认 ""（动态回填）** |
| §3.1 hidden 清单 [中→高] | **已确认：`unique_id` + `extra_pnginfo` 两项，清单闭合（动态回填）** |
| §2 `has_IS_CHANGED` | **已确认：True（动态回填）**——但"恒变哨兵 vs 指纹"策略 introspection 不可见，`changed_value`/sha256 指纹推断保持 |
| §3.2 ui 载荷默认键 `"text"` [中] | introspection 不采集运行期 ui 载荷，保持未确认 |
| §3.2 `selected` 值域 / `use_edited_text` 精确执行语义 | 保持未确认（运行时行为，需实测执行日志） |
| 未确认项清单中 `_text_signature`/`_first_dict`/`_normalize_unique_id` 实现 | introspection 无 method_docs，保持未确认 |
