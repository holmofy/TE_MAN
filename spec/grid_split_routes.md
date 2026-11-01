# grid_split_routes.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出入口 `PyInit_grid_split_routes`。静态分析（字符串/导入导出表）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

这是 **HTTP 路由模块（内部支撑库），不是 ComfyUI 节点模块**。它在 ComfyUI 的 `PromptServer` 上注册两个 aiohttp POST 路由（`/te_image/grid_split`、`/te_image/crop_image`），为前端 `web/js/` 提供图片九宫格切分和裁切到 input 目录的能力。注意 `__init__.py` 的 `SKIP_MODULES` 包含 `grid_split_core` 但**不包含** `grid_split_routes`，因此它会被作为"节点模块"导入——但它不注册任何节点（pyd 中无 `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` 字符串），导入副作用就是注册路由。[高]

## 2. Python API

### 导出
- `PyInit_grid_split_routes`（EXPORT 表唯一导出符号）[高]
- 构建信息：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\grid_split_routes.c`、`custom_nodes/TE_image/source_py_backup/grid_split_routes.py` [高]（Cython 生成 .c 的原始路径；模块属 `custom_nodes.TE_image` 包）
- PE 导入仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll` [高]

### 模块级公开对象（qualname 直接证据）[高]
| 对象 | 推断签名（与孪生 .py 一致） |
|---|---|
| `_json_error` | `(message, status=400) -> aiohttp.web.json_response`（返回 `{"success": False, "error": str(message)}`） |
| `_resolve_ui_image_path` | `(image_info) -> str`（pyd 中仍存在 qualname，但见 §7 差异说明） |
| `_sanitize_filename_stem` | `(value) -> str`（正则 `[^a-zA-Z0-9._-]+` 清洗，兜底 `"te_crop"`） |
| `crop_image_to_input_file` | `(image_info, crop) -> {filename, subfolder, type}` |
| `te_image_grid_split` | `async (request) -> json_response`（路由 `/te_image/grid_split`） |
| `te_image_crop_image` | `async (request) -> json_response`（路由 `/te_image/crop_image`） |

### 节点注册
无。`NODE_CLASS_MAPPINGS` 等节点注册字符串完全缺失。[高]

### 依赖的模块（字符串证据）
- `aiohttp`（`web`、`json_response`）、`server` / `PromptServer` / `instance` / `routes`、`folder_paths`、`PIL`（`Image`、`ImageOps`、`exif_transpose`）、`pathlib`、`uuid`（`uuid4`）、`json`（`JSONDecodeError`）、`os`、`re` [高]
- `grid_split_core` + `split_image_to_grid_input_files` [高]
- **pyd 新增**：`save_image_with_output_core`、`resolve_image_info_path`、`_resolve_shared_image_info_path`（明文孪生 .py 中没有，见 §7）[高（字符串存在）/中（引用方式未确认）]

## 3. 路由规格（内部接口）

### 路由 1：`POST /te_image/grid_split` [高]
- 请求 JSON（键名直接证据 `image_info`、`rows`、`cols`）[高]：
  ```json
  { "image_info": {"type": "output|input|temp", "filename": "…", "subfolder": "…"},
    "rows": N, "cols": M }
  ```
- 行为：调用 `grid_split_core.split_image_to_grid_input_files(image_info=…, rows=…, cols=…)`，把源图切分为 N×M 张切片存入 input 目录 [高委托，具体切分逻辑由 grid_split_core.pyd 提供，本模块不含]。
- 成功响应：`{"success": true, "images": […]}`（键 `success`/`images`）[高]

### 路由 2：`POST /te_image/crop_image` [高]
- 请求 JSON：`{ "image_info": {…}, "crop": {"x": n, "y": n, "width": n, "height": n} }`
  （`image_info`/`crop`/`width`/`height` 为直接证据 [高]；`x`/`y` 单字节串无鉴别力，按孪生 .py 推断 [中]）
- `crop_image_to_input_file` 行为（与孪生 .py 一致，相应字符串均在 pyd 中）[高]：
  1. 解析源图路径（pyd 版委托共享解析器，见 §7）；
  2. `ImageOps.exif_transpose` 纠正方向 → `convert("RGBA")`；
  3. 裁切区域钳制到图像边界后 `convert("RGB")`；
  4. 文件名 `{源文件名净化后的stem}_crop_{uuid4().hex[:10]}.png`（证据 `_sanitize_filename_stem` 正则 `[^a-zA-Z0-9._-]+`、`te_crop`、`_crop_`），PNG 写入 input 目录（`get_input_directory`、`exif_transpose`、`uuid4`）；
  5. 返回 `{"success": true, "image": {"filename", "subfolder": "", "type": "input"}}`（键 `filename`/`subfolder`/`input`/`image`）[高]

## 4. 外部依赖与副作用

- **无外联网络请求**：本模块只提供本地 loopback HTTP 服务；PE IMPORT 表无 WS2_32 等 [高]。
- **文件系统**：
  - 读：由 `image_info` 指定的目录（type 经 `folder_paths.get_directory_by_type` 解析——该字符串已移入共享库，见 §7；`type`/`output`/`input` 字符串存在 [高]，`temp` 未检出 [未确认 pyd 分支是否支持 temp]）。
  - 写：`folder_paths.get_input_directory()` 下生成随机命名的 PNG（切片由 `split_image_to_grid_input_files` 写；裁切由本模块写）[高]。
  - 子目录穿透防护（`../` 攻击）逻辑在孪生 .py 中由 `_resolve_ui_image_path` 完成；pyd 中该调用委托给共享库。
- **运行条件**：仅当 `PromptServer.instance` 可用（`PromptServer`、`instance`、`routes` 字符串）时才注册路由，路由是模块导入的副作用 [高]。

## 5. 错误处理与用户可见文案

统一错误格式：`{"success": false, "error": <str>}` + HTTP status（`_json_error`）[高]。

| 消息 | status | 触发场景 | 置信度 |
|---|---|---|---|
| `请求体不是有效的 JSON。` | 400 | 请求体 `JSONDecodeError` | [高] |
| `读取请求体失败: {exc}` | 400 | 读请求体其他异常 | [高] |
| `图片不存在: {filename}` | 404（`FileNotFoundError` 分支） | 源图缺失 | [中]（消息本体不在本 pyd 中，在共享库中，见 §7） |
| `裁切尺寸必须大于 0` | 400 | crop 宽/高 ≤ 0 | [高] |
| `当前图片尺寸无效，无法裁切。` | 400 | 打开后尺寸为零 | [高] |
| `不支持的图片目录类型: {type}` / `缺少图片文件名` / `非法的图片子目录` / `非法的图片路径` | 400 | 路径解析与目录穿越校验 | [高]（存在于 `save_image_with_output_core.pyd`，pyd 版本经共享函数抛出） |
| 其他未分类异常 | 500 | 兜底 `Exception` 分支 | [高]（孪生 .py 结构 + `FileNotFoundError`/`ValueError` 字符串） |

## 6. 证据附录

### 6.1 导入 / 导出
```
IMPORT: python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime-l1-1-0.dll
EXPORT: PyInit_grid_split_routes
```

### 6.2 模块身份与构建
```
custom_nodes/TE_image/source_py_backup/grid_split_routes.py
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\grid_split_routes.c
custom_nodes.TE_image.grid_split_routes.<各函数 qualname>
_cython_3_1_2limited_fastcallnofinalize
```

### 6.3 路由与有效载荷键
```
/te_image/grid_split   /te_image/crop_image
image_info  rows  cols  crop  width  height  type  output  input
success  error  images  image  filename  subfolder  status  message
```

### 6.4 裁切实现线索
```
exif_transpose  convert  strip  format  uuid4  _crop_  te_crop
[^a-zA-Z0-9._-]+  get_input_directory  Image  ImageOps  PIL: edge 钳制逻辑与孪生 .py 一致
```

### 6.5 与明文孪生 .py 的差异（核心发现）
- `__init__.py` SKIP_MODULES 含 `grid_split_core`、`save_image_with_output_core`（其中内容已证实存在于对应 pyd）。
- pyd 中**存在**而 .py 中**没有**的字符串：
  ```
  save_image_with_output_core    resolve_image_info_path    _resolve_shared_image_info_path
  ```
  且 `resolve_image_info_path` 的完整实现（含 `_has_supported_image_extension`、`resolve_image_info_path` 等 qualname 及全部路径校验消息）位于同仓库 `save_image_with_output_core.pyd`；`grid_split_core.pyd` 也引用相同的 `resolve_image_info_path` / `_resolve_shared_image_info_path` / `save_image_with_output_core`。
- pyd 中**缺失**而 .py 中**有**的字符串（`_resolve_ui_image_path` 的内联实现与消息）：
  ```
  不支持的图片目录类型:   缺少图片文件名   非法的图片子目录   非法的图片路径   图片不存在:
  get_directory_by_type
  ```
  → 推断：**pyd 是较新版本，把图片信息路径解析委托给了共享的 `save_image_with_output_core.resolve_image_info_path`（或经 `grid_split_core._resolve_shared_image_info_path` 转发）**，而不是在 `_resolve_ui_image_path` 内联实现目录白名单和路径穿越校验；`_resolve_ui_image_path` 在 pyd 中仍保留有函数（qualname 仍注册），推测为委托包装或兼容入口 [中]。
- 其余行为（两个路由、载荷键、裁切逻辑、文件名生成、错误消息）pyd 与 .py 一致 [高]。
- 未确认项：`temp` 目录类型分支、`x`/`y` crop 键、pyd 版对共享解析器的确切调用点（from-import 还是属性访问）。

## 7. 版本差异结论

`grid_split_routes.pyd` ≈ `grid_split_routes.py` 的进化版：功能不变（两个标准格分/裁切路由），实现上把路径解析与目录穿越校验下沉到共享核心库 `save_image_with_output_core`，与 `grid_split_core`（其 pyd 同样引用 `resolve_image_info_path`）形成统一的"共享图片信息解析"层。明文 .py 是较旧的内联实现，可继续作为行为参照。
