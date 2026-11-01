# save_image_with_output_core.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，PyInit_save_image_with_output_core。静态分析（字符串/导入导出表）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

内部支撑库（非节点），为 `Save_Image_With_Output.pyd`（节点类 `TE_image_pro_save_image_with_output`，见前端 `web/js/save_image_with_output_clipspace.js` 中 `beforeRegisterNodeDef` 判断字符串）提供"自定义保存路径保存图像节点"的全部核心逻辑：外部绝对路径保存解析、保存后预览图（含 token 校验）与提示词的序列化/恢复、输入图片枚举与张量加载。在 `__init__.py` 的 `SKIP_MODULES` 中被列为跳过模块（`"save_image_with_output_core"`，第 29 行），不参与 ComfyUI 节点注册。

## 2. Python API

- 导出（EXPORT 表仅一项）：`PyInit_save_image_with_output_core`
- 源文件路径（Cython 编译注释字符串）：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\save_image_with_output_core.c`，即源 `custom_nodes/TE_image/source_py_backup/save_image_with_output_core.py`
- 模块限定名：`custom_nodes.TE_image.save_image_with_output_core`
- **无 ComfyUI 节点注册**：二进制中无 `NODE_CLASS_MAPPINGS` / `INPUT_TYPES` / `RETURN_TYPES` / `CATEGORY` 字符串（依据：全字符串扫描未见）。
- 模块级公开对象（全部以完整限定名字符串出现在 .rdata 属性表，依出现顺序）：

| 对象 | 推断签名 | 置信度 |
|---|---|---|
| `_is_absolute_path` | `(path) -> bool` | [高]（名+实现线索 ntpath） |
| `_normalize_file_path` | `(path) -> str` | [高] |
| `_has_supported_image_extension` | `(filename) -> bool` | [高] |
| `make_custom_save_token` | `(path) -> str` | [高] |
| `build_custom_save_image_info` | `(path/filename) -> dict`（filename/subfolder/type/path/token） | [高] |
| `resolve_custom_save_image_path` | `(path) -> ...`（校验并解析外部路径） | [高] |
| `resolve_image_info_path` | `(image_info) -> str` | [高] |
| `resolve_ui_image_path` | `(type, filename, subfolder, path, token) -> str` | [高] |
| `load_cached_images` | `(directory_type / image_info) -> list` | [高] |
| `read_image_metadata` | `(image_path) -> dict` | [高] |
| `sorted_prompt_nodes`（含内嵌 `sort_key`） | `(nodes) -> sorted list` | [高] |
| `extract_text_from_prompt_graph` | `(prompt_data) -> str` | [高] |
| `format_prompt_text` | `(text) -> str` | [高] |
| `load_prompt_text_from_image_path` | `(image_path) -> str` | [高] |
| `load_prompt_text_from_ui_images` | `(ui_images, ...) -> str` | [高] |
| `get_connected_node_id` | `(node_id, prompt, widget_input_map) -> str` | [高]（签名细节[低]） |
| `normalize_extra_pnginfo` | `(extra_pnginfo) -> dict`（fallback `{}`，字符串 `setdefault` 佐证） | [中] |
| `normalize_node_id` | `(node_id) -> str`（`UnknownNode` 兜底） | [高] |
| `find_workflow_node` | `(workflow, node_id) -> dict` | [高] |
| `get_serialized_node_preview_images` | `(node) -> list`（键 `te_saved_preview_images`） | [高] |
| `get_serialized_node_prompt_text` | `(node) -> str`（键 `te_saved_prompt_text`） | [高] |
| `find_te_prompt_from_prompt_graph` | `(prompt, node_id, ...) -> str` | [高] |
| `build_prompt_ui_text` | `(text) -> str`（截断+提示语） | [高] |
| `get_input_image_choices` | `() -> list[str]` | [高] |
| `load_input_image_tensor`（含内嵌 `lambda`） | `(image) -> torch.Tensor` | [高] |

被 `Save_Image_With_Output.pyd` 实际复用的符号（在该节点模块字符串中同时出现：`load_cached_images`、`resolve_custom_save_image_path`/`_resolve_custom_save_image_path`、`build_custom_save_image_info`/`_build_custom_save_image_info`、`load_input_image_tensor`/`_load_input_image_tensor`、`get_input_image_choices`/`_get_input_image_choices`、`find_te_prompt_from_prompt_graph`/`_find_te_prompt_from_prompt_graph`、`build_prompt_ui_text`/`_build_prompt_ui_text`、`_TE_PROMPT_METADATA_KEY` —— [高]，据此确认本模块是节点模块的上游依赖库）。

### 模块级常量（字符串名 + 推断值）

| 常量 | 推断值 | 依据 | 置信度 |
|---|---|---|---|
| `TE_CUSTOM_SAVE_IMAGE_TYPE` | `'te_custom_save'` | 前端 `save_image_with_output_clipspace.js` 中明文 `TE_CUSTOM_SAVE_IMAGE_TYPE='te_custom_save'`；pyd 内两字符串同在 | [高] |
| `SERIALIZED_PROMPT_KEY` | `'te_saved_prompt_text'` | 前端同文件 `te_saved_prompt_text`；pyd 内字符串在 `get_serialized_node_prompt_text` 附近 | [高] |
| `SERIALIZED_IMAGES_KEY` | `'te_saved_preview_images'` | 前端同文件 `te_saved_preview_images`；同类节点 `save_video_with_frame_capture.js` 明文 `SERIALIZED_PROMPT_KEY='te_saved_prompt_text'` 佐证命名模式 | [高] |
| `TE_PROMPT_SOURCE_CLASSES` | 含 `('TE_image_pro_special_async2','TE_image_pro_banana','TE_image_pro_gpt_image_2','TE_image_pro_grok_image')` 中的类名 | 四个类名字符串全部存在于 pyd，且分别在对应生成器 pyd（GPT_Image_2_Generator/Gemini_Imagen_Generator/Grok_Image_Generator 等）中也出现，是插件内提示词输出节点的注册类名 | [中]（是否为该元组全部成员未确认） |
| `TE_PROMPT_METADATA_KEY` | 值未确认（可能为 `'parameters'`，即 ComfyUI PNG 元数据键；`parameters` 字符串在 pyd 中存在） | [中/低] |
| `TE_CUSTOM_SAVE_ALLOWED_EXTENSIONS` | 推断含 `.png .jpg .jpeg .webp .gif .bmp` | 扩展名字符串在 pyd 中成组出现；另有 `MPO`（PIL 多图 JPEG 格式名）——是否属该集合未确认 | [中] |
| `NODE_IMAGE_CACHE` | 模块级图片缓存字典 | 名符在，配合 `stat`/`st_mtime_ns`/`st_size`/`st_mtime` 冷却失效线索 | [高] |
| `PROMPT_UI_MAX_CHARS` | 数值未确认 | 名符在，配合截断消息 | [高]（值 [未确认]） |

## 3. 内部接口（支撑库，非节点）

对 `Save_Image_With_Output.pyd` 提供的两组能力，按前端协同行为还原：

### A. 外部路径保存与预览回放（te_custom_save 通道）

- 工作流：节点保存时若填了绝对路径 → 图片存入用户目录；前端预览 URL 带 `type=te_custom_save` + `path=...` + `token=...`（[高]：前端 `parseImageInfoFromSrc` 明文逻辑——`type===TE_CUSTOM_SAVE_IMAGE_TYPE` 时读取 `path`、`token` 两个 query 参数并构造 `{filename, subfolder:'', type, path, token}`）。核心库负责：
  1. `resolve_custom_save_image_path`：校验招到的外部路径——校验失败逐条对应中文错误（见 §5）；存在性校验（`isfile`、消息 `图片不存在: `）。
  2. `make_custom_save_token`：对路径做 `hashlib.sha256(...).hexdigest()` 生成 token（[中]：`sha256`、`hexdigest`、`token` 字符串紧邻此函数名出现）。
  3. `build_custom_save_image_info`：把 `filename/subfolder/type/path/token` 打包成 ui 委托的 image info dict（[高]：前端同名解析字段一致）。
  4. `resolve_ui_image_path`：预览请求路径还原 + token 复核，token 不匹配报 `外部图片预览 token 无效`（[高]）。
- `_is_absolute_path` / `_normalize_file_path`：使用 `ntpath`（`isabs`、`normcase`、`abspath`、`commonpath`、`relpath`、`splitext`、`basename`）与 `expanduser`、`expandvars` 对用户输入做展开/归一化（[高]：`ntpath` + 上述方法名字符串）。

### B. 缓存图片/输入图片与提示词回填

- `load_cached_images`：按目录类型取目录（`folder_paths.get_directory_by_type` / `get_output_directory` 线索：字符串 `get_directory_by_type`、`subfolder`、`output`；另外 `get_input_directory`、`get_annotated_filepath` 存在），用 `walk`/`isfile`/`sorted` + `folder_paths.filter_files_content_types`（[高]：该名符）过滤，返回文件列表缓存到 `NODE_IMAGE_CACHE`，用 `stat.st_mtime_ns/st_size` 判断失效（[中]）。目录类型不识别时抛 `不支持的图片目录类型: `。
- `get_input_image_choices`：枚举 input 目录可选项（`folder_paths.get_input_directory` + `_has_supported_image_extension` + `sorted`，[中]）。
- `load_input_image_tensor`：PIL 打开 → `ImageOps.exif_transpose` → `convert('RGB')`（字符串 `RGB`、`mode`、`exif_transpose`，[中]）→ `numpy` 数组 `astype(np.float32)` → `torch.from_numpy(...).unsqueeze(0)`（`from_numpy`、`unsqueeze`、`dim`、`astype`、`float32`、`torch`、`np`，[高]为张量加载链证据）。内嵌 lambda 用作排序 key（`load_input_image_tensor.lambda` 限定名）。
- 提示词链路：
  - `read_image_metadata` + `load_prompt_text_from_image_path`：从已保存图片读取元数据（`json.loads`、`TE_PROMPT_METADATA_KEY`、`parameters`），无元数据时报 `当前图片没有可读取的提示词元数据`（[高]）。
  - `load_prompt_text_from_ui_images`：从 ui image info 反查文件再走上面路径（[中]）。
  - `extract_text_from_prompt_graph`：递归遍历序列化 prompt（`prompt_data`、`inputs`、`visited` 集合 `PySet_Contains/PySet_Add`、防环），命中 `class_type` ∈ `TE_PROMPT_SOURCE_CLASSES` 的节点提取其文本输入（`extract_text_from_prompt_graph` 名 + `visited` 线索，[中]）。`sorted_prompt_nodes.sort_key` 对节点排序（可能按图拓扑/编号，未确认具体键）。
  - `find_workflow_node` / `normalize_node_id` / `get_connected_node_id`：在 `extra_pnginfo['workflow']['nodes']` 里按 id/`properties`/`type` 定位节点，找不到用 `UnknownNode` 占位（[高]）。
  - `get_serialized_node_preview_images` / `get_serialized_node_prompt_text`：读取前端存回节点 properties 的 `te_saved_preview_images` / `te_saved_prompt_text`（[高]）。
  - `find_te_prompt_from_prompt_graph`：组合函数，优先取序列化文本，否则从 prompt 图向上游 TE 提示词节点找（[中]）。
  - `build_prompt_ui_text` / `format_prompt_text`：规范文本并截断——超越 `PROMPT_UI_MAX_CHARS` 时截断后加 `......` 后缀并附 `提示词过长，节点内已截断显示`（[高]：三串同区出现）；多段提示词用 `==========` 分隔线拼接（[中]）。
  - 节点最终以 `te_prompt_text`（`Save_Image_With_Output` 的输入侧字段名，前端 `setStoredPromptText(this, _0x3c17b0?.['te_prompt_text'])`，[高]）回传给上层节点使用；`Save_Image_With_Output.pyd` 另有 `_write_prompt_txt_for_image`（保存同名 `.txt` 提示词文件，README "新增 `保存提示词` 输入口" 印证）但该 txt 写盘逻辑不在本核心库字符串中出现。

### 输出契约（对 Save_Image_With_Output 节点）

iu 输出条目形如 `{filename, subfolder, type: 'te_custom_save'|'output', path?: ..., token?: ...}`（[高]：pyd 字符串与前端解析字段一一对应）；前端把这些条目保存进节点 `properties[te_saved_preview_images]`、文本存 `properties[te_saved_prompt_text]`，供刷新/工作流载入后 `restorePreviewImages`/提示词面板还原（前端同一 JS 文件行为，非核心库职责）。

## 4. 外部依赖与副作用

- **无网络依赖**：IMPORT 表仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll`（无 WS2_32/ADVAPI32），纯本地模块。
- ComfyUI 内置 `folder_paths`：`get_directory_by_type`、`get_input_directory`、`get_output_directory`（间接）、`get_annotated_filepath`、`filter_files_content_types`（[高]字符串）。
- 第三方库：`torch`（张量输出）、`numpy`、`PIL`（`Image`、`ImageOps.exif_transpose`、`ImageSequence`——动图帧处理迹象，[中]）。
- 标准库以字符串引用：`hashlib`（sha256/hexdigest）、`json`（dumps/loads/indent/ensure_ascii）、`ntpath`、`inspect`、`types.MethodType`、`asyncio.coroutines`（签到 coroutine 支持样板）、`os` 系（`stat`、`isfile`、`walk`、`expanduser`、`expandvars`、`abspath`）。
- 文件系统副作用：只读为主（读取已保存图片、枚举目录）；无写盘字符串（不写 txt/图片，写盘由上层节点模块完成，如 `_write_prompt_txt_for_image` 属 `Save_Image_With_Output.pyd`）。
- 模块级可变状态：`NODE_IMAGE_CACHE` 图片缓存（含 mtime/size 失效）。

## 5. 错误处理与用户可见文案

中文消息（全部为字符串证据，原文摘录）：

| 消息 | 触发场景（推断） | 置信度 |
|---|---|---|
| `缺少图片文件名` | image info 未带 filename | [高] |
| `非法的图片路径` | 路径归一/校验失败（含 path traversal 检查的可能性，`commonpath`/`relpath` 佐证，未确认细节） | [高]/细节[低] |
| `非法的图片子目录` | subfolder 越界/非法 | [高] |
| `缺少外部图片路径` | type=te_custom_save 但无 path 参数 | [高] |
| `外部图片路径必须是绝对路径` | 外部路径非绝对（`_is_absolute_path` 入口） | [高] |
| `外部预览只支持常见图片格式` | 外部路径扩展名不在白名单 | [高] |
| `外部图片预览 token 无效` | `token != make_custom_save_token(path)` | [高] |
| `图片不存在: ` | 外部路径校验的文件不存在 | [高] |
| `无法读取图像文件: ` | PIL 打开失败（OSError 等） | [高] |
| `不支持的图片目录类型: ` | `get_directory_by_type` 返回非法类型 | [高] |
| `当前图片没有可读取的提示词元数据` | `load_prompt_text_from_image_path` 无元数据 | [高] |
| `提示词过长，节点内已截断显示` | `build_prompt_ui_text` 超过 `PROMPT_UI_MAX_CHARS` 截断时附加 | [高] |
| `......` | 截断省略号后缀 | [高] |

异常类型引用：`ValueError`、`PermissionError`、`FileNotFoundError`、`RuntimeError`/`RuntimeWarning`（Cython 样板部分 `Module ... Re-initialisation` 等与业务无关）。

## 6. 证据附录

**模块/限定名与源路径**（ASCII）：
- `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\save_image_with_output_core.c`
- `custom_nodes/TE_image/source_py_backup/save_image_with_output_core.py`
- `custom_nodes.TE_image.save_image_with_output_core`（每个函数的 __qualname__ 均带此前缀，共 24 个函数 + 2 个内嵌 `sort_key`/`lambda`）

**常量与键名**（ASCII/UTF-8 混合）：
```
NODE_IMAGE_CACHE   TE_PROMPT_METADATA_KEY   TE_PROMPT_SOURCE_CLASSES
TE_CUSTOM_SAVE_ALLOWED_EXTENSIONS   TE_CUSTOM_SAVE_IMAGE_TYPE   PROMPT_UI_MAX_CHARS
SERIALIZED_PROMPT_KEY   SERIALIZED_IMAGES_KEY   te_custom_save
te_saved_prompt_text   te_saved_preview_images   te_prompt_text
UnknownNode   parameters   prompt_value   input_value   prompt_data   extra_pnginfo
```

**TE 提示词源节点类名**（TE_PROMPT_SOURCE_CLASSES 候选成员）：
```
TE_image_pro_special_async2   TE_image_pro_banana
TE_image_pro_gpt_image_2      TE_image_pro_grok_image
```

**folder_paths / 目录枚举**：
```
folder_paths   get_directory_by_type   get_input_directory   get_annotated_filepath
filter_files_content_types   images   walk   isfile   stat   st_mtime_ns   st_mtime   st_size
sorted   join   filename   image_name   subfolder   output   type   path   token
```

**扩展名/图像格式串**：
```
.png   .jpg   .jpeg   .webp   .gif   .bmp   MPO   RGB   exif_transpose   ImageSequence
ImageOps   Image   px   dim   unsqueeze   from_numpy   astype   float32   np   torch
```

**哈希/token**：
```
hashlib   sha256   hexdigest   token   ' token '（前后带空格的格式片段）
```

**序列化/文本处理**：
```
json(间接)   dumps   loads   indent   ensure_ascii   replace   strip   items   values
inputs   prompt_text   prompt   text   '=========='   '......'
```

**校验函数链（依 Cython 声明序）**：
```
_is_absolute_path → _normalize_file_path → _has_supported_image_extension
→ make_custom_save_token → build_custom_save_image_info → resolve_custom_save_image_path
→ resolve_image_info_path → resolve_ui_image_path → load_cached_images → read_image_metadata
→ sorted_prompt_nodes(.sort_key) → extract_text_from_prompt_graph → format_prompt_text
→ load_prompt_text_from_image_path → load_prompt_text_from_ui_images → get_connected_node_id
→ normalize_extra_pnginfo → normalize_node_id → find_workflow_node
→ get_serialized_node_preview_images → get_serialized_node_prompt_text
→ find_te_prompt_from_prompt_graph → build_prompt_ui_text → get_input_image_choices
→ load_input_image_tensor(.lambda)
```
（顺序 = .rdata 属性表中限定名字符串的出现顺序，即 Cython 的声明注册顺序，功能分组据此可信。）

**中文消息全文**：
```
缺少图片文件名 / 非法的图片路径 / 非法的图片子目录 / 缺少外部图片路径
外部图片路径必须是绝对路径 / 外部预览只支持常见图片格式 / 外部图片预览 token 无效
图片不存在:  / 无法读取图像文件:  / 不支持的图片目录类型:
当前图片没有可读取的提示词元数据 / 提示词过长，节点内已截断显示
```

**跨模块互证**：
- `Save_Image_With_Output.pyd` 中出现本模块函数名的引用对（`resolve_custom_save_image_path`、`build_custom_save_image_info`、`load_cached_images`、`get_input_image_choices`、`load_input_image_tensor`、`find_te_prompt_from_prompt_graph`、`build_prompt_ui_text`、`TE_PROMPT_METADATA_KEY`）→ 本模块是其上游依赖。
- `web/js/save_image_with_output_clipspace.js`：`TE_CUSTOM_SAVE_IMAGE_TYPE='te_custom_save'`（明文）；preview URL 解析读取 `filename/subfolder/type` 与自定义通道的 `path/token`；节点类名 `TE_image_pro_save_image_with_output`；`te_saved_prompt_text`、`te_saved_preview_images`、`te_prompt_text` 均出现。
- `web/js/save_video_with_frame_capture.js`：`SERIALIZED_PROMPT_KEY='te_saved_prompt_text'`（同命名套式的姊妹节点）。
- `__init__.py` 第 29 行：`SKIP_MODULES` 含 `"save_image_with_output_core"`。
- `README.md` "首创保存图像节点支持自定义保存路径"："填写绝对路径时，可直接保存到计算机内任意指定目录。留空时仍保存到 ComfyUI 默认 `output`。" —— 与本库 `_is_absolute_path`/`resolve_custom_save_image_path` 行为吻合。

**未确认项汇总**：`TE_PROMPT_METADATA_KEY` 的具体值、`TE_PROMPT_SOURCE_CLASSES` 元组是否完整为上述 4 类、`TE_CUSTOM_SAVE_ALLOWED_EXTENSIONS` 是否含 `MPO`、`PROMPT_UI_MAX_CHARS` 的数值、`make_custom_save_token` 是否加盐/截断长度、`sorted_prompt_nodes.sort_key` 的排序键。
