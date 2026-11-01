# TE_Prompt_Text.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出 `PyInit_TE_Prompt_Text`。静态分析（字符串/导入导出表）+ 交叉比对前端明文 `web/js/te_prompt_text.js`、README v3.6。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

ComfyUI **节点模块**（不在 `__init__.py` 的 `SKIP_MODULES` 中，因此会被自动加载并注册）。实现文本展示/提示词编辑节点 **`TE_prompt_text`**（显示名 `TE MAN MiniMaxH3增强提示词Prompt TEXT`），是 MiniMax H3（HappyH3）视频工作流中"提示词文本"环节：带富文本编辑器、`@` 提及菜单插入参考素材标记（`<Picture N>` / `<Video N>` / `<Audio N>`），并经 ComfyUI PromptServer 暴露一个参考图/参考视频预览路由。

- 原始源路径：`custom_nodes/TE_image/source_py_backup/TE_Prompt_Text.py` [高]（旧包名 `TE_image`，与 save_image_with_output_core 的 qualname 前缀一致，说明本插件曾叫 `TE_image`）。
- **与 `TE_image_pro_*` 家族的关系（核对任务要求）**：本模块内 **0 处** `TE_image_pro` 字符串，**不属于** save_image_with_output_core.pyd 遍历的 `TE_image_pro_*` 提示词节点族（`TE_image_pro_special_async2` / `TE_image_pro_banana` / `TE_image_pro_gpt_image_2` / `TE_image_pro_grok_image`，见 spec/save_image_with_output_core.md）。它注册为独立类名 `TE_prompt_text` [高]。关联方式是：save_image_with_output_core.pyd 中确实出现字符串 `te_prompt_text`（连同 `format_prompt_text`、`get_serialized_node_prompt_text`、`te_saved_prompt_text`）[高]，说明保存节点会序列化/恢复本节点的提示词；且前端 `te_prompt_text.js` 把 `TE_image_pro_grok_image`、`TE_image_pro_happyh_video` 列为**下游提示词目标**（`PROMPT_TEXT_TARGET_CONFIGS`）——即本节点与该族是"上下游互补"关系，非同族。[中]
- 前端配套：`web/js/te_prompt_text.js`，扩展名 `TE.PromptText` [高]（JS 明文）。该 JS 里 `PROMPT_TEXT_NODE_CLASS`、`prompt` 输入目标、`'TE_prompt_text'`、`'reference_labels'`、`'TE_H3_REFERENCES'`、`'/te_prompt_text/view_reference'` 与 pyd 字符串一一对应。

## 2. Python API

- 导出符号：仅 `PyInit_TE_Prompt_Text`（导出表）[高]。
- 导入：`python3.dll`（limited API abi3）、`KERNEL32.dll`、`VCRUNTIME140.dll`、CRT runtime。**无 WS2_32**——模块自身不做网络请求，路由只是被别人请求 [高]。
- 运行期导入（仅存在名字符串，间接证据）：`aiohttp`、`folder_paths` [中]。

### 模块级对象

| 对象 | 证据 | 推断 |
|---|---|---|
| `TEPromptTextNode` | qualname `custom_nodes.TE_image.TE_Prompt_Text.TEPromptTextNode`；方法 `INPUT_TYPES`、`build_text` | ComfyUI 节点类 [高] |
| `te_prompt_text_view_reference` | qualname `custom_nodes.TE_image.TE_Prompt_Text.te_prompt_text_view_reference`；伴随 `__pyx_scope_struct__te_prompt_text_view_reference`、`_is_coroutine`、"cannot reuse already awaited coroutine" 等 coroutine 字符串 | **async 函数**，预览路由处理器 [高] |
| `_resolve_reference_preview_path` | qualname `custom_nodes.TE_image.TE_Prompt_Text._resolve_reference_preview_path`；参数名 `filename`、`subfolder`、`image_type`；局部名 `image_path` | 解析查询参数 → ComfyUI 目录内的实际图片路径，供路由调用 [高] |

### ComfyUI 节点注册

- `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` 字符串存在 [高]。
- 注册键：`TE_prompt_text` [高]。
- 显示名：`TE MAN MiniMaxH3增强提示词Prompt TEXT` [高]（pyd 内完整 UTF-8 字面量；README v3.6 第 2 条同款名称）。
- `CATEGORY`：`TE MAN/Utils` [高]。注意 pyd 中另有 `TE MAN MiniMaxH3` 是显示名被 ASCII 抽取器截断后的片段（中文断开了连续 ASCII），不是另一个 CATEGORY [中]。
- `FUNCTION`：`build_text` [高]（qualname 精确到 `TEPromptTextNode.build_text`）。

### INPUT_TYPES（推断）

pyd 中成组出现的输入构造字符串：`required`、`STRING`、`multiline`、`tooltip`、`format`?（未见）、widget 名 `text`、`reference_labels` [高；结构为推断]。结合前端 JS 引用同名 widget（`getWidgetByName(node,'text')`、`'reference_labels'`，且两个 widget 都被 `hideOriginalTextWidget` 隐藏、由 DOM 编辑器接管）：

```python
# 已确认：与运行时 INPUT_TYPES 逐字段一致（动态回填；tooltip 含句号）
required = {
    "text": ("STRING", {"multiline": True, "default": "",
        "tooltip": "增强提示词文本。输入 @ 可选择下游节点已连接的图片、视频和音频引用。"}),
    "reference_labels": ("STRING", {"multiline": True, "default": "",
        "tooltip": "由前端根据 H3 官方节点的素材连接自动生成。"}),
}
```
- 中文 tooltip 原文（pyd 内完整字面量）："增强提示词文本。输入 @ 可选择下游节点已连接的图片、视频和音频引用"、"由前端根据 H3 官方节点的素材连接自动生成" [高]。
- **已确认：两参数均含 `default: ""`（动态回填）**。
- **已确认：无 `optional` 输入，亦无 hidden 输入（动态回填）**。

### RETURN_TYPES / RETURN_NAMES（已确认，动态回填）

- 候选字符串：`STRING`、`TE_H3_REFERENCES`、`H3参考素材`、`text` [高（字符串均存在）]。
- 前端在 `beforeRegisterNodeDef` 中检查 `nodeData.output.includes('TE_H3_REFERENCES')` 才给节点加输出 **`H3参考素材`（类型 `TE_H3_REFERENCES`）**；TE_H3_Prompt_Enhancer 一侧则通过 `ensureH3ReferenceInput` 加同名输入 [高（JS 明文）]。
- **已确认：`RETURN_TYPES = ("STRING", "TE_H3_REFERENCES")`，`RETURN_NAMES = ("text", "H3参考素材")`（动态回填）**——第一个输出口名就是 `text`（"增强提示词文本"候选不成立），元组顺序与早先推断一致。

## 3. 节点规格

### TE_prompt_text（TEPromptTextNode）

**定位**：MiniMax H3/HappyH3 工作流的提示词文本源节点。

**输入**
| 参数 | 类型 | 说明 | 置信度 |
|---|---|---|---|
| `text` | STRING, multiline | 提示词正文；运行时基本由前端 DOM 编辑器 `te_prompt_editor`（`serialize:false` 的 addDOMWidget）写入，原 textarea 控件被隐藏 | widget 名 [高]，赋值机制 [中] |
| `reference_labels` | STRING, multiline | 参考素材标记清单（如 `<Picture 1>`、`<Video 2>`、`<Audio 1>` 各占一行），由前端根据下游 H3 节点连接自动同步，用户不手填 | [高] |

**输出**：**已确认 `STRING`（口名 `text`）+ `TE_H3_REFERENCES`（口名 `H3参考素材`，与 `TE_H3_Prompt_Enhancer` 的同名输入对接）**（动态回填）。另：运行时无 `OUTPUT_NODE`、无 `DESCRIPTION` 键（非输出节点，节点级描述缺省）。

**关键行为（字符串流程推断）**
1. `build_text`：把 `text`（必要时联动 `reference_labels`）整理为提示词字符串返回；同时产出 `TE_H3_REFERENCES` 输出供 H3 链路使用 [中]。pyd 中出现 `strip`、`split`、`join`、`pop`、`replace`（Cython 调用的方法名字符串），暗示对文本做行级去重/拼接（前端 JS 的 `getReferenceLabelText` 恰好是"取 insertText 去重、按行 join"）[中]。
2. 前端交互（te_prompt_text.js 明文，行为归前端、本 pyd 只供定义与路由）：富文本编辑器把标记渲染成图片 chip；输入 `@` 弹出提及菜单，选项来自**下游目标的连接**：`TE_image_pro_grok_image`（image/image_2/image_3 → 图1/图2/图3）、`TE_image_pro_happyh_video`（image_1..image_9 → 图1..图9）、官方 `MiniMax H3 Reference to Video`（`ref_image_N` → `<Picture N>`、`ref_video_N` → `<Video N>`、`ref_audio_N` → `<Audio N>`）、`MiniMax H3 Image to Video`（`first_frame` → `<Picture 1>`、`last_frame` → `<Picture 2>`），并与 `TE_H3_Prompt_Enhancer`、`TE_H3_Reference_Bridge`、`TE_text_display`、`QwenTE_ImageInfer` 链路互通 [高]。
3. 预览路由 `GET /te_prompt_text/view_reference`（见下）为 `@` 菜单 chip 提供缩略图（JS `buildViewUrl` 以 `filename/type/subfolder/rand` 拼查询串，`Cache-Control: no-store`）[高]。

### 内部接口：预览路由

- 注册方式：模块初始化时取 `PromptServer`（实例单例字符串 `server`、`instance`），在 `routes` 上挂 `GET /te_prompt_text/view_reference` [高]。`asyncio.coroutines` 相关串印证 async handler [高]。
- 查询参数：`filename`、`subfolder`、`image_type`（`type`/`query`/`request` 字符串在表内）[高]。
- 路径解析 `_resolve_reference_preview_path`：
  - `folder_paths.annotated_filepath` + `folder_paths.get_directory_by_type`（目录类型 input/temp/output）[高]；
  - 结果用 `commonpath`/`realpath` 校验未越出目录根 [高（commonpath、realpath、os 风格 isfile 皆在字符串表）]。
- 响应：命中 → `aiohttp.FileResponse`（带 `Cache-Control: no-store, max-age=0`）[高]；异常 → `json_response` {"error": ...} [中]。

## 4. 外部依赖与副作用

- 网络端点：仅**本机 ComfyUI 路由** `/te_prompt_text/view_reference`（被请求方）。无出站 API、无 API Key、无常驻文件写入。导入表无 WS2_32，证实纯静态资源路由 [高]。
- 文件系统：**只读** ComfyUI 标准图片目录（input/temp/output，经 `folder_paths`）[高]。
- 配置键：无（无 config_manager 字样）[高]。
- 第三方库：aiohttp（服务器框架自带）、folder_paths [高]，标准库 os/asyncio/json（`json_response`）[中]。

## 5. 错误处理与用户可见文案

中文消息全部来自预览路由的参数/路径校验（附触发场景推断）：

| 消息 | 推断触发场景 |
|---|---|
| `缺少图片文件名` | query 中未提供 `filename` [高] |
| `无效的图片文件名` | `annotated_filepath`/校验未通过 [高] |
| `无效的图片目录类型` | `image_type` 不在 input/temp/output（`get_directory_by_type` 抛 ValueError）[高] |
| `图片路径超出允许目录` | realpath/commonpath 越界（路径穿越防护）[高] |
| `图片文件不存在` | 解析出的路径 `isfile` 为假 [高] |

异常类型字符串出现在表内：`ValueError`、`FileNotFoundError`、`PermissionError` [高]（PermissionError 可能对应文件不可读；归属哪个消息未确认）。

## 6. 证据附录

### 6.1 标识/注册（ASCII）
```
custom_nodes/TE_image/source_py_backup/TE_Prompt_Text.py
custom_nodes.TE_image.TE_Prompt_Text
custom_nodes.TE_image.TE_Prompt_Text.TEPromptTextNode.INPUT_TYPES
custom_nodes.TE_image.TE_Prompt_Text.TEPromptTextNode.build_text
custom_nodes.TE_image.TE_Prompt_Text.te_prompt_text_view_reference
custom_nodes.TE_image.TE_Prompt_Text._resolve_reference_preview_path
TE_prompt_text    TE_prompt_text_view_reference    TEPromptTextNode
NODE_CLASS_MAPPINGS    NODE_DISPLAY_NAME_MAPPINGS    RETURN_TYPES    RETURN_NAMES
INPUT_TYPES    FUNCTION    CATEGORY    TE MAN/Utils    STRING    multiline
required    tooltip    reference_labels    TE_H3_REFERENCES    H3参考素材
json_response    FileResponse    Cache-Control    no-store, max-age=0
routes    server    instance    query    filename    subfolder    image_type
get_directory_by_type    annotated_filepath    commonpath    realpath    isfile
aiohttp    asyncio.coroutines    folder_paths    strip    split    join    pop
default    output    error    request    value    labels    text
（PyInit_TE_Prompt_Text；导入：python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime）
```
注：`te_prompt_text_view_reference` 同时以独立符号出现（模块级函数），与 qualname 略不同截取位置。

### 6.2 中文文案（UTF-8 字面量，含偏移）
```
@0xc950  缺少图片文件名
@0xc978  图片路径超出允许目录
@0xd0f0  由前端根据 H3 官方节点的素材连接自动生成
@0xd190  无效的图片文件名
@0xd528  图片文件不存在
@0xd588  H3参考素材
@0xd628  TE MAN MiniMaxH3增强提示词Prompt TEXT
@0xd6a0  增强提示词文本。输入 @ 可选择下游节点已连接的图片、视频和音频引用
@0xd748  无效的图片目录类型
```
（0xd6a0 处正则被全角'。'截断为两段，实为同一字面量。）

### 6.3 交叉印证（非 pyd 文件）
- `README.md` L171："**TE MAN MiniMaxH3增强提示词Prompt TEXT** 现已支持 ComfyUI 自带的 MiniMax H3 视频节点，可通过输入 `@` 选择已连接的参考素材并插入对应标记"——显示名与 `@` 功能直接印证。
- `web/js/te_prompt_text.js`（明文）：`PROMPT_TEXT_NODE_CLASS='TE_prompt_text'`、扩展 `TE.PromptText`、`PROMPT_TEXT_TARGET_CONFIGS`（TE_image_pro_grok_image / TE_image_pro_happyh_video / MiniMaxH3ReferenceToVideo / MiniMaxH3ImageToVideo）、`ensureH3ReferenceInput/Output('H3参考素材','TE_H3_REFERENCES')`、`buildViewUrl()` 拼 `/te_prompt_text/view_reference`、`syncReferenceLabels()` 写 `reference_labels` widget——与 pyd 字符串逐一对应。
- `save_image_with_output_core.pyd`：含 `te_prompt_text`、`te_saved_prompt_text`、`format_prompt_text` 等字符串——保存节点会序列化本节点提示词（两模块的接口耦合点）。
- `TE_H3_Prompt_Enhancer.pyd`：含 `TE_H3_REFERENCES`、`reference_labels`、`available_reference_labels`——下游增强节点的对接证据。

### 6.4 判非（显式否定）
- `grep 'TE_image_pro'` 于本模块字串 → **0 处命中**：本模块不是 `TE_image_pro_*` 提示词节点族成员；save_image_with_output_core 遍历的该族类名均不在本模块内。

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows Server 2025 + ComfyUI（Python 3.13.16）真实环境 import 后的自省结果；运行时模块显示为 `custom_nodes.TE_image.TE_Prompt_Text`（`TE_image` 为插件原名），模块文件 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN\TE_Prompt_Text.pyd`。本节所有值均为运行时实锤。

### 7.1 节点 INPUT_TYPES 全表（实锤）

#### TE_prompt_text（TEPromptTextNode）

注册元数据：`FUNCTION = "build_text"`、`CATEGORY = "TE MAN/Utils"`、`RETURN_TYPES = ["STRING", "TE_H3_REFERENCES"]`、`RETURN_NAMES = ["text", "H3参考素材"]`；无 `OUTPUT_NODE`（非输出节点）、无节点级 DESCRIPTION、无 IS_CHANGED / VALIDATE_INPUTS / on_execute / check_lazy_status。类 docstring 为 `null`（无）。显示名（node_display_name_mappings）：`TE MAN MiniMaxH3增强提示词Prompt TEXT`。

**required**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `text` | STRING, multiline | — | `""` | 增强提示词文本。输入 @ 可选择下游节点已连接的图片、视频和音频引用。 |
| `reference_labels` | STRING, multiline | — | `""` | 由前端根据 H3 官方节点的素材连接自动生成。 |

**optional / hidden**：无。

### 7.2 模块常量实锤值（动态采集）

pyd 模块 `TE_MAN.TE_Prompt_Text`（module docstring 为 `null`）除注册表外无业务常量：`NODE_CLASS_MAPPINGS = {"TE_prompt_text": TEPromptTextNode}`、`NODE_DISPLAY_NAME_MAPPINGS = {"TE_prompt_text": "TE MAN MiniMaxH3增强提示词Prompt TEXT"}`。模块引用 `server.PromptServer`（预览路由注册用），与 §2/§4 判断一致。

### 7.3 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2 INPUT_TYPES `default` 键是否用于两参数 | **已确认：两参数均 `default: ""`（动态回填）** |
| §2 是否还有 optional 输入 | **已确认：无 optional、无 hidden（动态回填）**——JS 里的 `'optional'` 一词与节点输入无关 |
| §2 `RETURN_TYPES`/`RETURN_NAMES` 顺序与命名 [中] | **已确认：`("STRING", "TE_H3_REFERENCES")` / `("text", "H3参考素材")`（动态回填）**；第一口名 `text`，"增强提示词文本"候选不成立 |
| §3 `build_text` 内部文本整理细节（strip/split/join 等） | introspection 无 method_docs，行为细节保持原推断 |
| §5 `PermissionError` 归属哪个消息 | introspection 不覆盖路由异常映射，保持未确认 |
