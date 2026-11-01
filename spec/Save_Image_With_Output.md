# Save_Image_With_Output.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，PyInit_Save_Image_With_Output。静态分析：导入导出表、ASCII/UTF-8 字符串提取、**反汇编（objdump，还原了 Cython 字符串槽位表 280 项，并对 INPUT_TYPES / 类属性构造代码逐条解码）**。
> 置信度说明：[高] = 字符串/反汇编直接证据；[中] = 强暗示推断；[低] = 猜测；未确认项在 §7 汇总。

## 1. 模块定位

节点模块（ComfyUI 自定义节点外壳），注册节点 `TE_image_pro_save_image_with_output`，显示名 `TE MAN 加载图像&保存图像 Image`（README 中"加载保存图像节点"），分类 `TE MAN/Utils`。职责：**保存输入图像到 ComfyUI 默认 `output` 或用户指定的绝对路径目录，同时把同一批图像从右侧继续输出（passthrough），并附带"选择/上传图像 + 预览记录回放 + 提示词 .txt 落盘"能力**。本模块只做节点层编排（参数解析、路径/文件名归一化、文件落盘、ui 组装、HTTP 预览路由），核心路径校验/预览序列化/张量加载逻辑全部复用内部支撑库 `save_image_with_output_core`（见 `spec/save_image_with_output_core.md`）。`__init__.py` 的 `SKIP_MODULES` 未列入本模块（第 21–33 行），故经通用加载器正常注册。

## 2. Python API

- 导出（EXPORT 表仅一项）：`PyInit_Save_Image_With_Output`
- 源文件路径（Cython 编译注释字符串）：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Save_Image_With_Output.c`，即源 `custom_nodes/TE_image/Save_Image_With_Output.py`
- 模块限定名：`custom_nodes.TE_image.Save_Image_With_Output`
- 节点注册（反汇编直接证实，`0x1800111F7`–`0x180011280` 两处 `PyDict_SetItem`）：
  - `NODE_CLASS_MAPPINGS['TE_image_pro_save_image_with_output'] = TESaveImageWithOutput`
  - `NODE_DISPLAY_NAME_MAPPINGS['TE_image_pro_save_image_with_output'] = 'TE MAN 加载图像&保存图像 Image'`

### 2.1 类 `TESaveImageWithOutput`（类属性均经反汇编证实）

| 属性 | 值 | 证据 | 置信度 |
|---|---|---|---|
| `RETURN_TYPES` | `('IMAGE',)` | `PyTuple_Pack(1, 'IMAGE')` → 存入 `0x18001FF60`，再 `PyDict_SetItem(RETURN_TYPES, ...)`（`0x18000E708`、`0x180010BE5`） | [高] |
| `RETURN_NAMES` | `('images',)` | `PyTuple_Pack(1, 'images')` → `0x18001FF68` → `PyDict_SetItem(RETURN_NAMES, ...)`（`0x18000E72A`、`0x180010C13`） | [高] |
| `FUNCTION` | `'save_images_and_output'` | `PyDict_SetItem(FUNCTION, 'save_images_and_output')`（`0x180010C3E`） | [高] |
| `OUTPUT_NODE` | `True` | `PyDict_SetItem(OUTPUT_NODE, True)`（`0x180010C69`，True 使用缓存指针 `0x180017408`） | [高] |
| `CATEGORY` | `'TE MAN/Utils'` | `PyDict_SetItem(CATEGORY, 'TE MAN/Utils')`（`0x180010C94`） | [高] |
| `DESCRIPTION` | `保存输入图像到默认 output 或指定目录，同时将同一批图像继续从右侧输出，并支持普通、多图和全景预览。` | 字符串表 idx 204；`PyDict_SetItem(DESCRIPTION, ...)`（`0x180010CBF`） | [高] |
| `SEARCH_ALIASES` | `('save image with output', 'save and pass through', 'save image passthrough')` | `PyTuple_Pack(3, 三个英文字符串)` → `PyDict_SetItem(SEARCH_ALIASES, ...)`（`0x180010CEA`–`0x180010D2E`）；三个英文短语在中文字符串槽位居同一区段，此前"英文短语用途"疑问就此定论 | [高] |
| `INPUT_TYPES` / `VALIDATE_INPUTS` / `save_images_and_output` / `_save_images_to_directory` / `_paths_to_ui_images` | cyfunction（限定名字符串 `TESaveImageWithOutput.<名>`） | 方法表构造（`0x180010D51` 等，以限定名 + 模块名 `custom_nodes.TE_image.Save_Image_With_Output` 注册） | [高] |

### 2.2 模块级函数（qualname 字符串 + 声明序）

`_normalize_filename_prefix` → `_write_prompt_txt_for_image` → `_normalize_save_path` → `_is_absolute_save_path` → `_is_inside_directory` → `_build_png_metadata` → `_make_unique_png_filename` → `_output_ui_image_info` → `_official_ui_images` → `_build_save_ui` → `te_image_view_saved`（**唯一 async 函数**：存在 `__pyx_scope_struct__te_image_view_saved` 与 coroutine 样板，即 HTTP 路由处理器）

### 2.3 模块级常量

| 常量 | 值/含义 | 依据 | 置信度 |
|---|---|---|---|
| `DEFAULT_SAVE_PATH_LABEL` | `'默认'` | save_path 的 `default` 项为 `GetModuleGlobal(DEFAULT_SAVE_PATH_LABEL)`（`0x180006AA5`），字符串表 idx 60 有独立 `'默认'`；前端明文 `DEFAULT_SAVE_PATH_LABEL='默认'` | [高] |
| `CUSTOM_FILENAME_TIME_FORMAT` | `'TE_MAN_%Y-%m-%d-%H-%M-%S'` | filename_prefix 的 `default` 为 `GetModuleGlobal(CUSTOM_FILENAME_TIME_FORMAT)`（`0x18000693E`）；tooltip "支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S" | [高] |
| `INVALID_FILENAME_CHARS_RE` | `'[<>:"/\\|?*\x00-\x1f]+'` | 正则串原样在字符串表（idx 279）；配套 `'_'`/`'_'`/`'+'`/`re`/`sub` 槽位——`_normalize_filename_prefix` 用 `re.sub` 把非法字符替换为 `_` | [高] |
| `LEGACY_FILENAME_PREFIX_DEFAULTS` | 旧版文件名前缀集合（是否存在 `'ComfyUI'` 一项未确认——`'ComfyUI'` 字符串在表中，前端有 `LEGACY_DEFAULT_SAVE_PATH_VALUES={'','ComfyUI'}` 套式先例，但这是 save_path 侧的旧值） | 名符在字符串表 [高]；值 [中] |
| `OFFICIAL_UI_IMAGE_TYPES` | `('output','temp','input')` 推断 | 名符在表 [高]；`'temp'/'output'/'input'` 三串同在，前端明文 `OFFICIAL_PREVIEW_IMAGE_TYPES={'output','temp','input'}` | 值 [中] |
| `IMAGE_TEXT_EXTENSIONS` | 未确认；名符在表，配合 `.png/.jpg/.jpeg/.webp` 与 `_build_png_metadata`/`read_image_metadata` 用途，推断为"可携带文字元数据的图片扩展名"集合 | 名符 [高]；值 [低] |
| `_NODE_IMAGE_CACHE` / `_SERIALIZED_IMAGES_KEY` / `_TE_PROMPT_METADATA_KEY` | 从 core 导入的别名（见 §3.5） | 名符在表 | [高] |
| `('token','')` 二元组 | PyModule 初始化里 `PyTuple_Pack(2,'token','')` 建于 `0x18001FF58`；推测是 `request.query.get('token','')` 语义相关的常量（如 fallback dict），真实用途未确认 | [低] |

### 2.4 与 core 的对接（节点 → 支撑库别名导入）

模块内出现 core 侧 `save_image_with_output_core` 导入名，且每个被复用的 core 符号都有"无下划线 + 下划线前缀"成对字符串（`load_cached_images`/`_load_cached_images` 等 12 组），推断为 `from custom_nodes.TE_image.save_image_with_output_core import X as _X` 风格的 `_X = X` 别名层 [中→高]。对照表：

| 节点模块引用 | core 提供 | 本模块中的用途（推断） |
|---|---|---|
| `_get_input_image_choices` / `get_input_image_choices` | 同名函数 | `INPUT_TYPES` 里 upload_image 组合框的选项列表（构造代码 `0x1800067A0` 直接 `GetModuleGlobal `_get_input_image_choices`→无参调用`） |
| `_load_input_image_tensor` / `load_input_image_tensor` | 同名函数 | upload_image（input 目录）→ tensor |
| `_resolve_custom_save_image_path` / `resolve_custom_save_image_path` | 同名函数 | 外部保存路径校验（含 `_is_absolute_save_path`/`_is_inside_directory` 配套） |
| `_build_custom_save_image_info` / `build_custom_save_image_info` | 同名函数 | ui image info 组装（filename/subfolder/type/path/token） |
| `_load_cached_images` / `load_cached_images` | 同名函数 | 目录枚举缓存（配合 `cache_key`/`cached_images`/`NODE_IMAGE_CACHE`） |
| `_load_prompt_text_from_image_path` / `_load_prompt_text_from_ui_images` | 同名函数 | 从已存图/回放条目读提示词 |
| `_find_te_prompt_from_prompt_graph` / `_build_prompt_ui_text` | 同名函数 | 从 prompt 图上溯 TE 提示词节点 + 文本截断规范 |
| `_get_serialized_node_preview_images` / `_get_serialized_node_prompt_text` | 同名函数 | 读节点 properties 里的历史预览/提示词（"至少保存一次图像"回放） |
| `_TE_PROMPT_METADATA_KEY` / `_SERIALIZED_IMAGES_KEY` / `_NODE_IMAGE_CACHE` | `TE_PROMPT_METADATA_KEY`/`SERIALIZED_IMAGES_KEY`/`NODE_IMAGE_CACHE` | 常量复用 |

## 3. 节点规格

### 3.1 INPUT_TYPES（反汇编逐条还原，`0x180006750`–`0x180006FE0`）

```python
{"required": {
    "upload_image":   (choices列表, {"default": "", "image_upload": True,
                        "tooltip": "可选。左侧 images 未连接时，使用这里选择或上传的图像；左侧 images 一旦有输入，会优先覆盖这里的选择。要清空选择，请手动选回空白项。"}),
    "filename_prefix": ("STRING", {"default": CUSTOM_FILENAME_TIME_FORMAT,   # 'TE_MAN_%Y-%m-%d-%H-%M-%S'
                        "display_name": "文件名前缀", "label": "文件名前缀",
                        "tooltip": "保存文件名/前缀。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S。多张图会自动追加编号；需要接文本时请使用左侧「保存文件名」。"}),
    "save_path":      ("STRING", {"default": DEFAULT_SAVE_PATH_LABEL,        # '默认'
                        "display_name": "保存位置", "label": "保存位置",
                        "tooltip": "保存位置必须是绝对目录，例如 F:\\test\\images。默认或留空则使用 ComfyUI 默认 output。"})},
 "optional": {
    "images":  ("IMAGE", {"tooltip": "要保存并继续输出的图像。留空时会尝试使用本节点上一次保存过的图像。"}),
    "保存文件名": ("STRING", {"forceInput": True,
                        "tooltip": "可选。接入文本后会覆盖上方文件名前缀输入框，作为实际保存文件名。"}),
    "保存提示词": ("STRING", {"forceInput": True,
                        "tooltip": "可选。接入文本后，会用与图片相同的文件名在同目录保存 .txt。"})},
 "hidden": {"unique_id": "UNIQUE_ID", "prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}
```

要点（均有构造代码地址佐证）：
- `upload_image` 的元组第 0 位是**运行时选项列表**：先 `GetModuleGlobal('_get_input_image_choices')` 再无参调用（`0x1800067A0`/`0x1800067F2`），即 input 目录现有图像清单；`image_upload: True` 与 `default=''` 使其呈现 LoadImage 式"选择或上传"空白项 [高]。
- **可选输入名直接使用中文标识符**「保存文件名」「保存提示词」（`PyDict_SetItem(optional, '保存文件名', …)` `0x180006DDC`；`…'保存提示词', …)` `0x180006ED3`），Python 3 合法；tooltip 中「保存文件名」的角括号引用与此吻合 [高]。
- 两者的 `forceInput: True`（值为 `True`，`0x180006D29`/`0x180006E20`），即节点左侧的两个文本输入口；README"新增 `保存提示词` 输入口"印证 [高]。
- 选项字典带自定义键 `display_name` + `label`（TE MAN 前端用其绘制横排控件）[高]。
- `images` 为 optional（IMAGE 型）：未连接时节点退化为"加载 upload_image"或回放"上一次保存"的图像（见 §3.3）[高]。
- 执行函数内另以 `save_prompt_text` 名字取参（`0x180009192` 等两处 kw 查找）——推断为旧版参数名兼容链：取「保存提示词」的同时也会 `get('save_prompt_text')` 兜底（前端 `LEGACY_WIDGET_NAMES={'text','te_prompt'}` 佐证历经 text→te_prompt→保存提示词 的迁移）[中]。

### 3.2 执行流程概要（字符串流程推断，标注置信度）

`save_images_and_output`（方法本体 `0x1800085xx`–`0x1800097xx` 区域，含大量 core 别名调用）大致：

1. **图像来源三级回退**：connected `images` 张量 → `upload_image`（`_load_input_image_tensor`；失败抛 `Invalid image file: `，[高]）→ `_get_serialized_node_preview_images` 回放本节点上一次保存的图像（`_is_absolute_save_path`/`_resolve_custom_save_image_path` 把 `te_custom_save` 条目还原为张量/路径）。三处全空时报错（见 §5 "images 未连接…"）[中→高，靠消息与字符串链]。
2. **路径归一化**（`_normalize_save_path`/`_is_absolute_save_path`）：`'默认'` 或留空 → `folder_paths.get_output_directory()`；非空值要求绝对路径（`isabs`/`abspath`/`expanduser`/`expandvars`），非法时抛出与 tooltip 同文案的错误（`ValueError` 槽位 + save_path tooltip 串 3 处引用之一，[中]）；`makedirs(exist_ok=True)` 建目录（字符串 `makedirs`/`exist_ok`）[高]。
3. **文件名归一化**（`_normalize_filename_prefix`）：`re.sub(INVALID_FILENAME_CHARS_RE, '_', …)` 清洗非法字符；若接了「保存文件名」文本则以其覆盖 filename_prefix 作为实际文件名（tooltip 原文）；` strftime(…, localtime)` 应用 `TE_MAN_%Y-%m-%d-%H-%M-%S` 时间格式 [高]。
4. **落盘**（`_save_images_to_directory`）：逐张 `numpy` 数组 → `clip` → `uint8` → `Image.fromarray` → `save(..., pnginfo=…, compress_level=…)`；`_make_unique_png_filename`（`base_name`/`splitext`/`batch_number`/`'05'` 编号格式 [中]）保证多图/重名不冲突；`comfy.cli_args.args.disable_metadata` 为真时跳过元数据（`comfy.cli_args`/`args`/`disable`/`disable_metadata` 四串，ComfyUI SaveImage 同款）[高]。
5. **PNG 元数据**（`_build_png_metadata`）：`PIL.PngImagePlugin.PngInfo` + `add_text`，写入 workflow/prompt 序列化（`extra_pnginfo`/`json.dumps`/`dumps`）与 `TE_PROMPT_METADATA_KEY` 提示词（`_find_te_prompt_from_prompt_graph` 提取，键名复用 core 常量）[中]。
6. **提示词 .txt**（`_write_prompt_txt_for_image`）：接入「保存提示词」文本后，`open(..., 'w', encoding='utf-8').write(...)` 在图片同目录写同名 `.txt`（str `.txt`、`write`/`utf-8`/`encoding`）[高]。
7. **ui 组装与返回**：`_build_save_ui`/`_output_ui_image_info` 输出 `{'ui_images': [...], 'te_prompt_text': <规范化提示词>}`（`ui`/`ui_images`/`te_prompt_text`/`prompt_text`/`serialized_ui_images` 槽位；`te_prompt_text` 经 `build_prompt_ui_text` 截断）。自定义路径时条目走 core 的 `build_custom_save_image_info`（type=`te_custom_save`+`path`+`token` 语义，type 常量值在 core，本模块不含该字符串）；官方目录条目为普通 `{filename, subfolder, type}` [高·字段名 / 中·具体 markup]。前端 `onExecuted` 读取这两个键并把 `ui_images` 存入 `properties['te_saved_preview_images']`、文本存 `properties['te_saved_prompt_text']`，供刷新/载入后还原（明文 JS）[高]。
8. 结果对象含 `result`/`success`/`saved_paths`（`saved_paths` 槽位 [中]：已保存绝对路径列表，语义未完全确认）。

### 3.3 加载/回放语义（前端协同）

- `VALIDATE_INPUTS` 存在（qualname 字符串），具体校验项未还原（未确认）。
- 前端把 `properties['te_saved_preview_images']` 回放为节点预览，文件缺失时后端/前端给出"对应图片文件已不存在"提示（§5）。`properties['te_multi_input_enabled']`（前端明文）支持多图输入查看与全景预览——均为 `web/js/save_image_with_output_clipspace.js` 实现的 NodeUI 能力（自绘预览、提示词面板、裁切、全景查看、动作条），节点 pyd 本体不含这些 UI 逻辑 [高·边界划分]。
- 前端裁切/切图调用的 `/te_image/crop_image`、`/te_image/grid_split` HTTP 接口**不属于本模块**（本模块字符串表中唯一路由为 `/te_image/view_saved`）[高]。

### 3.4 输出契约

`(IMAGE, 'images')` 直通；`OUTPUT_NODE=True`，ui 键：`ui_images`（列表）+ `te_prompt_text`（字符串）[高]。

### 3.5 HashMapRoute：`GET /te_image/view_saved`（模块自建路由）

- 注册形态（推断）：`@PromptServer.instance.routes.get('/te_image/view_saved')`，处理器为模块级 async 函数 `te_image_view_saved`。依据：import 链 `LocatePyTuple('PromptServer')` → `server` 模块名（`0x18000F231`–`0x18000F2BD`）、`aiohttp` 导入、`routes`/`get`/`instance` 槽位、`te_image_view_saved` 的 coroutine 样板与挂接点（`0x18000C4AD`）[高·存在性 / 中·装饰器写法]。
- 请求参数：`filename`、`subfolder`、`type`、`path`、`token`（前端明文构造 `api.apiURL('/te_image/view_saved?' + URLSearchParams{filename,subfolder,type,path,token})`）[高]。
- 返回：成功 → `aiohttp.web.FileResponse` 直接回图；异常 → `json_response({status/error/success})`；响应头固定 `Cache-Control: no-store, max-age=0` 和 `Pragma: no-cache` 防缓存 [高·字符串]。
- 路径解析：`type` ∈ `OFFICIAL_UI_IMAGE_TYPES` 时走 ComfyUI 官方目录（`folder_paths`/`get_output_directory`/`get_directory_by_type` 语义，`isfile`/`exists`/`dirname`/`basename`/`splitext`/`join`）；否则按 `_resolve_custom_save_image_path` + `_is_inside_directory`（`ntpath.normcase/commonpath/relpath`，防逃逸）校验外部绝对路径与 `token`（core 内 token=sha256 路径签名）[中·分发细节 / 高·函数名与前端解析字段一一对应]。
- 该路由是"自定义保存路径"预览能正常显示的关键：前端对 `type==='te_custom_save'` 条目一律改打本路由 [高·前端明文]。

## 4. 外部依赖与副作用

- **无网络客户端依赖**：PE IMPORT 表仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll`；HTTP 仅作为 aiohttp 服务器端点 [高]。
- ComfyUI 内置：`folder_paths`（`get_output_directory`/`get_annotated_filepath`/`exists_annotated_filepath`）、`server`（`from server import PromptServer`）、`comfy.cli_args`（`args.disable_metadata`）[高·indirect 字符串]。
- 第三方：`aiohttp`（路由/响应）、`PIL`（`PIL.PngImagePlugin.PngInfo`、`Image`、`fromarray`）、`numpy`（`np`、`astype`、`uint8`、`clip`）、`torch`/`cpu`（张量与设备，[中]——张量加载主体在 core）。
- 标准库：`json`（dumps/loads）、`re`（sub/compile）、`os`、`time`（`strftime`/`localtime`）、`ntpath`、`re`、`gc`、`asyncio.coroutines`（Cython 样板）。
- 文件系统副作用（写）：按 `save_path` 落盘图片（默认 ComfyUI `output`；自定义绝对路径下 `makedirs`）、同名 `.txt` 提示词文件 [高]。
- 模块级状态：`_NODE_IMAGE_CACHE`（缓存目录枚举，`cache_key`/`cached_images`，含 mtime/size 失效语义——沿用 core 套路 [中]）。

## 5. 错误处理与用户可见文案

| 消息（原文） | 触发场景（推断） | 置信度 |
|---|---|---|
| `images 未连接，且当前节点没有可用图像。请先连接 images 输入，或先让这颗节点至少保存一次图像。` | images/upload_image/历史记录三者皆空 | [高] |
| `当前节点找到了预览图记录，但对应图片文件已不存在。请重新连接 images 再运行一次。` | 回放条目指向的文件被删除 | [高] |
| `保存位置必须是绝对目录，例如 F:\test\images。默认或留空则使用 ComfyUI 默认 output。` | save_path 填写非绝对路径（`_normalize_save_path` 抛 ValueError；与 save_path tooltip 同文案） | [高·文案 / 中·抛错点] |
| `Invalid image file: ` | `_load_input_image_tensor` 打开 upload_image/OpenImage 失败 | [高] |
| 异常类型引用：`ValueError`、`PermissionError`、`FileNotFoundError`、`RuntimeError`（部分为 Cython 样板） | 落盘权限/路径错误等 | [中] |
| 兜底消息 `Invalid image` 系列/其它中文运行时消息 | 未发现独立串 | — |

（token 校验失败、外部分类非法等细消息在 core 库中，由共享函数抛出；见 core 规格 §5。）

## 6. 证据附录

**模块/限定名与源路径**（ASCII）：
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Save_Image_With_Output.c
custom_nodes/TE_image/source_py_backup/Save_Image_With_Output.py
custom_nodes.TE_image.Save_Image_With_Output
TE_image_pro_save_image_with_output   TE MAN/Utils
TE MAN 加载图像&保存图像 Image
```

**反汇编确证的类属性构造**（PyDict_SetItem 键值序，地址→键）：
```
0x180010BE5 RETURN_TYPES = 0x18001FF60  ← PyTuple_Pack(1,'IMAGE')        @0x18000E708
0x180010C13 RETURN_NAMES = 0x18001FF68  ← PyTuple_Pack(1,'images')       @0x18000E72A
0x180010C3E FUNCTION    = 'save_images_and_output'
0x180010C69 OUTPUT_NODE = True(0x180017408)
0x180010C94 CATEGORY    = 'TE MAN/Utils'
0x180010CBF DESCRIPTION = idx204 长描述
0x180010D2E SEARCH_ALIASES = PyTuple_Pack(3,'save image with output','save and pass through','save image passthrough') @0x180010CEA
0x1800111F7 NODE_CLASS_MAPPINGS['TE_image_pro_save_image_with_output'] = class
0x18001126F NODE_DISPLAY_NAME_MAPPINGS['TE_image_pro_save_image_with_output'] = 'TE MAN 加载图像&保存图像 Image'
```

**字符串槽位表**：Cython 表基址 `0x180019660`（文件偏移 0x18A60，280 个 16 字节表项 {char* s; n|flags<<32}），PyObject 槽位基址 `0x18001FFA0`（InitStrings 循环 `0x18000E060`–`0x18000E110`，表项/槽位同步 `+16`/`+8` 递增）。280 个字符串全部被代码引用（地址→表项映射见分析脚本输出），这是本文各结论"字符串证据"的基准。

**参数构造地址**（INPUT_TYPES，`0x180006750` 起）：
```
0x1800067A0 GetModuleGlobal('_get_input_image_choices') → 无参调用        (upload_image 选项)
0x180006830/85F/87A default=''/image_upload=True/tooltip                   (upload_image options)
0x1800068F7 required['upload_image']
0x18000693E GetModuleGlobal('CUSTOM_FILENAME_TIME_FORMAT') → default       (filename_prefix)
0x1800069AD 未另证→ label/display_name='文件名前缀', tooltip=idx48/50 0x180006A60 required['filename_prefix']
0x180006AA5 GetModuleGlobal('DEFAULT_SAVE_PATH_LABEL') → default ('默认')    (save_path)
0x180006B15 label/display_name='保存位置', tooltip=idx6/11                 0x180006BC8 required['save_path']
0x180006BF4 required→outer；0x180006CE4 optional['images']=(IMAGE,{tooltip})
0x180006D29 forceInput=True → optional['保存文件名'] @0x180006DDC
0x180006E20 forceInput=True → optional['保存提示词'] @0x180006ED3
0x180006F48/6F6A/6F8C hidden['unique_id']='UNIQUE_ID', ['prompt']='PROMPT', ['extra_pnginfo']='EXTRA_PNGINFO'
```

**核心复用符号（无下划线/下划线前缀双形态）**：
```
load_cached_images  resolve_custom_save_image_path  build_custom_save_image_info
load_input_image_tensor  get_input_image_choices  load_prompt_text_from_image_path
load_prompt_text_from_ui_images  find_te_prompt_from_prompt_graph  build_prompt_ui_text
get_serialized_node_preview_images  get_serialized_node_prompt_text
TE_PROMPT_METADATA_KEY  SERIALIZED_IMAGES_KEY  NODE_IMAGE_CACHE
（导入名）save_image_with_output_core
```

**文件名/落盘相关**：
```
CUSTOM_FILENAME_TIME_FORMAT  TE_MAN_%Y-%m-%d-%H-%M-%S  INVALID_FILENAME_CHARS_RE '[<>:"/\\|?*\x00-\x1f]+'
'05'(编号格式片段) base_name batch_number effective_filename_prefix splitext join makedirs exist_ok
PngInfo add_text pnginfo compress_level disable_metadata comfy.cli_args strftime localtime
fromarray astype uint8 clip np .png .jpg .jpeg .webp .txt open 'w' encoding utf-8 write
```

**路由相关**：
```
/te_image/view_saved  te_image_view_saved  PromptServer  server  aiohttp  routes  get  instance
FileResponse  json_response  status error success
Cache-Control  no-store, max-age=0  Pragma  no-cache
filename subfolder type path token  query request headers
OFFICIAL_UI_IMAGE_TYPES  output temp input  ('token','') 二元组 @0x18001FF58（具体用途未确认）
```

**前端跨证（web/js/save_image_with_output_clipspace.js，字符串表已解码）**：
```
SERIALIZED_IMAGES_KEY='te_saved_preview_images'  SERIALIZED_PROMPT_KEY='te_saved_prompt_text'
TE_CUSTOM_SAVE_IMAGE_TYPE='te_custom_save'  DEFAULT_SAVE_PATH_LABEL='默认'
LEGACY_DEFAULT_SAVE_PATH_VALUES={'','ComfyUI'}  OFFICIAL_PREVIEW_IMAGE_TYPES={'output','temp','input'}
LEGACY_WIDGET_NAMES={'text','te_prompt'}  SERIALIZED_MULTI_INPUT_KEY='te_multi_input_enabled'
preview URL: api['apiURL']('/te_image/view_saved?'+URLSearchParams{filename,subfolder,type,path,token})
onExecuted: setStoredPromptText(this, msg?.['te_prompt_text']) / mergePreviewImages(ui_images)
save_path 控件 label '保存位置'；旧值 {'','ComfyUI'} 迁移显示为 '默认'
（/te_image/crop_image、/te_image/grid_split 属其它模块的路由）
```

**跨模块互证**：
- `save_image_with_output_core.pyd`：含全部被复用符号本体（core 规格第 2/3 节），本模块是它的唯一节点外壳。
- `__init__.py`：`SKIP_MODULES` 只跳过 `save_image_with_output_core` 等 11 项，本模块被通用加载器注册（第 51–63 行合并 NODE_CLASS_MAPPINGS）。
- `README.md`："首创保存图像节点支持自定义保存路径——填写绝对路径时，可直接保存到计算机内任意指定目录。留空时仍保存到 ComfyUI 默认 output"（§332）；"新增 `保存提示词` 输入口，接入文本后会在保存图片的同时保存同名 `.txt` 提示词文件"（§251）；"TE MAN 加载图像&保存图像 Image 节点新增保存文件名、多图查看和全景图查看能力"（§248）——与 INPUT_TYPES/执行流全部对应。

**未确认项汇总**：
- `LEGACY_FILENAME_PREFIX_DEFAULTS`、`IMAGE_TEXT_EXTENSIONS` 的具体值；`OFFICIAL_UI_IMAGE_TYPES` 是否恰为三元素（强暗示）。
- `VALIDATE_INPUTS` 的具体校验逻辑（函数存在，行为未还原）。
- `('token','')` 二元组（@0x18001FF58）的实际用途。
- `save_images_and_output` 结果对象里 `saved_paths`/`success`/`status`/`result` 的具体结构与 ui 键之外的 result 通道。
- 旧参数名兼容链「保存提示词」→`save_prompt_text`→`text`/`te_prompt` 的确切优先级顺序。
- `_make_unique_png_filename` 编号格式（`'05'` 推断为 5 位补零）与 `_build_png_metadata` 的完整键集合。
- 反汇编只覆盖模块级结构（类属性/INPUT_TYPES/路由/导入），方法体内的具体分支（如三级回退的精确顺序）依据消息与调用链推断。
