# grid_split_core.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3, `_cython_3_1_2limited_fastcallnofinalize`) 编译，导出 `PyInit_grid_split_core`。静态分析（字符串/导入导出表 + 常量池/反汇编核验）。
> 置信度说明：[高] = 字符串或常量初始化序列直接证据；[中] = 强暗示推断；[低] = 猜测；无法确定的写"未确认"。

## 1. 模块定位

内部支撑库（非 ComfyUI 节点，在 `__init__.py` 的 `SKIP_MODULES` 中）：九宫格/分镜切图核心。接收 ComfyUI 前端传来的图片信息（filename/subfolder/type），把图片按行×列拆分为多个小图并保存到 ComfyUI input 目录；若图片上有黑色分隔线，则按黑线位置智能切分，否则按行列均分。被 `grid_split_routes.pyd`（HTTP 路由层）调用：
`grid_split_routes.py` 第 17 行：`from .grid_split_core import split_image_to_grid_input_files`，在 `POST /te_image/grid_split`（payload: `image_info` / `rows` / `cols`）中调用 [高]。

## 2. Python API

- 导出符号：`PyInit_grid_split_core`（PyInit 标准入口）[高]
- 源文件（Cython 注释保留的编译源路径）：`custom_nodes/TE_image/source_py_backup/grid_split_core.py`（构建机路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\grid_split_core.c`）[高]
- 模块内全部函数限定名（qualname 字符串直接证据）[高]：
  - `_get_pixel_luma`
  - `_is_dark_separator_pixel`
  - `_detect_dark_bands`
  - `_select_separator_bands`（内嵌 `<locals>.search` 与 `<locals>.search.<locals>.<lambda>`）
  - `_build_axis_slices_from_bands`
  - `_build_equal_axis_slices`
  - `_detect_grid_slices_from_black_lines`（含 `<locals>.genexpr`）
  - `_resolve_ui_image_path`
  - `_sanitize_filename_stem`
  - `split_image_to_grid_input_files` ← 唯一对外 API
- 推断签名 [中]（参数名 image_info/rows/cols 见 routes 双胞胎调用 + 限定名字符串；`typing` 的 `Optional/Tuple/Dict/Any/List/Sequence` 字符串存在，应有类型注解；具体注解内容未确认）：

  ```python
  def split_image_to_grid_input_files(image_info, rows, cols) -> List[Dict[str, Any]]:
      ...
  ```

- ComfyUI 节点注册：无（无 NODE_CLASS_MAPPINGS / INPUT_TYPES / CATEGORY 字符串；也不注册 HTTP 路由，路由在 grid_split_routes 层）[高]

## 3. 内部接口（支撑库，非节点）

### split_image_to_grid_input_files(image_info, rows, cols)

流程（按函数 имен 字符串顺序与错误消息推断，[中] 除非另注）：

1. 校验 `rows`、`cols`：`<= 0` 时抛 `ValueError("rows 和 cols 必须大于 0")` [高]。
2. `_resolve_ui_image_path(image_info)` 解析图片实际路径：输入 dict 键 `filename` / `subfolder` / `type`（三者字符串均在常量名表中）[高]；目录基址经 `folder_paths.get_input_directory` / ComfyUI 目录类型解析 [中]；模块同时 import 了 `save_image_with_output_core` 的 `resolve_image_info_path`（以及 `_resolve_shared_image_info_path`）——三组字符串均在内名表中，路径解析应复用了 Save_Image_With_Output 的共享逻辑 [中，具体分工未确认]。
3. 打开图片：PIL `Image.open`（有 `open`/`load`/`close` 上下文管理），`ImageOps.exif_transpose`（EXIF 方向矫正；`exif_transpose`/`ImageOps`/`RGBA` 字符串），无尺寸时抛 `ValueError("当前图片尺寸无效，无法拆分")` [高]。
4. 黑线检测 `_detect_grid_slices_from_black_lines`：
   - `_get_pixel_luma(pixel)`：亮度 = `0.2126*R + 0.7152*G + 0.0722*B`（BT.709 权重；常量池中 0.2126/0.7152/0.0722 三个 double 在同一初始化批次内由 `PyFloat_FromDouble` 创建，且 `_get_pixel_luma` 是模块内唯一像素级函数）[高，系数本身；"用于 luma 的位置"为强推断]。像素暗判定阈值为 `GRID_SEPARATOR_LUMA_THRESHOLD = 26`（0–255 亮度尺度）[高，见 §4 常量核验]。
   - `_is_dark_separator_pixel`：判定单个像素是否属于黑色分隔线（可能含 RGBA alpha 考虑，`RGBA` 字符串存在）[低/未确认细节]。
   - `_detect_dark_bands(horizontal/vertical, axis)`：按水平/垂直两个方向扫描行/列，统计暗像素比例（`averageRatio`）与连续暗带 `thickness`、`start`/`end`/`center` [中，来自变量名字符串]。
   - 带筛选：带厚 ≥ `GRID_SEPARATOR_MIN_BAND_THICKNESS = 2` px、暗率 ≥ `GRID_SEPARATOR_DARK_RATIO_THRESHOLD = 0.9` 才算分隔带 [高，常量绑定见下]。
   - `_select_separator_bands(bands, segment_count)` + 内嵌 `search` 与打分 `lambda`（`best_score`/`separator_count`/`internal_bands`）：在候选带中选出最佳组合，一般目标分隔带数 = 行数-1 / 列数-1 [中]。
   - `_build_axis_slices_from_bands(separator_bands)`：按分隔带把该轴切成段，得到 `(start, end)` 切片（`start_index`/`axis`/`dimension` 字符串）；另有 `min_allowed_width` / `min_allowed_height` 过滤过窄切片 [中]。
   - 检测不到有效黑线时 `_build_equal_axis_slices(rows, cols)` 等分切分 [中]。
5. 裁切并落盘：逐 `(row, col)` 用 `image.crop`（`crop` 字符串）切出小图，`.convert("RGB")`（`RGB`/`convert` 字符串），`save(..., format="PNG")`（`save`/`PNG`/`format` 字符串）保存到 `folder_paths.get_input_directory()`（input 根目录，无子目录）[中]。
6. 文件名 [中，元素均有字符串证据但拼接方式未确认]：`{净化后的源图 stem}_grid_{行/列编号}{:02d}.png` —— 涉及字符串：`_grid_`（分隔符中缀）、`02d`（2 位零填充 format spec，配合 `format`）、`.png`、`te_grid`（`_sanitize_filename_stem` 空 stem 时回退名，同类实现在 routes 中的回退是 `te_crop`）、净化正则 `[^a-zA-Z0-9._-]+`、`strip`/`._-`。
   - `uuid4` + `hex` 字符串存在：可能用于文件名防重 [低/未确认]，注意 routes 双胞胎的裁切用 `uuid4().hex[:10]`。
7. 返回值 [高（键名）/中（结构）]：`List[Dict]`，每项 `{"filename": ..., "subfolder": ..., "type": "input"}` —— 键名 `filename`/`subfolder`/`type` 与值 `"input"` 均为内名表字符串，且 routes 层把该结果逐项原样放进响应 `{"success": True, "images": [...]}` [高]。

### 模块级常量（黑线检测参数，全部可在初始化机器码中核验）

| 名称 | 值 | 证据 | 置信度 |
|---|---|---|---|
| `GRID_SEPARATOR_LUMA_THRESHOLD` | `26` (int) | 初始化序列 `mov $0x1a,%ecx; call PyLong_FromLong; → 缓存槽 0x1c2f0`，随后 `PyDict_SetItem(模块字典, 名槽 0x1bea8=GRID_SEPARATOR_LUMA_THRESHOLD, 该槽)` | 高 |
| `GRID_SEPARATOR_DARK_RATIO_THRESHOLD` | `0.9` (float) | `movsd 0x17ee0(=0.9); call PyFloat_FromDouble → 槽 0x1c290`，接着 `PyDict_SetItem(名槽 0x1bea0=GRID_SEPARATOR_DARK_RATIO_THRESHOLD, 0x1c290)` | 高 |
| `GRID_SEPARATOR_MIN_BAND_THICKNESS` | `2` (int) | `mov $0x2,%ecx; call PyLong_FromLong → 槽 0x1c2c8`，`PyDict_SetItem(名槽 0x1beb0=GRID_SEPARATOR_MIN_BAND_THICKNESS, 0x1c2c8)` | 高 |

名槽定位方法：Cython 字符串表基址 `0x180017060`（每项 `{const char* s; len|flags}` 0x10 字节，初始化循环把 PyUnicode 顺序写入槽数组 `0x18001be80 + 8*i`）；表内序号 4/5/6 分别为 `GRID_SEPARATOR_DARK_RATIO_THRESHOLD`（len 36）/`GRID_SEPARATOR_LUMA_THRESHOLD`（len 30）/`GRID_SEPARATOR_MIN_BAND_THICKNESS`（len 34）。

其他在常量池出现但角色未映射的数值：`0.02, 0.0722, 0.2126, 0.5, 0.7152, 1.0, -1.0, 4.0, 24.0`（另有整型缓存 `0,1,2,3,4,10,16,26,255,320,-1`）。`4.0` 在代码中以 `mulsd`（×4 缩放）出现两次 [低]。`24.0`/`0.2` 在同一段代码（疑与 `min_allowed_width/height` 或 `averageRatio` 相关）被加载 [低]。三个 GRID_* 常量已确定，其余用途未确认。

## 4. 外部依赖与副作用

- PE 导入表（加载时）[高]：`python3.dll`（limited API，PyFloat/PyLong/PyDict/PyUnicode 全大杂烩）、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll`。无 WS2_32/USER32/ADVAPI32 → 纯计算库，无网络/注册表行为 [高]。
- 运行时 Python import（字符串证据，经 `PyImport_ImportModule`/`getattr` 动态进行）[高]：
  - `PIL`（`PIL`/`Image`/`ImageOps`/`exif_transpose`/`crop`/`convert`/`save`/`close`/`open`/`load`）
  - `folder_paths`（`get_input_directory`）
  - `save_image_with_output_core`（`resolve_image_info_path`、`_resolve_shared_image_info_path` —— 与保存节点共享图片路径解析，含路径穿越防护）
  - `uuid`（`uuid4`）、`pathlib`（`Path`、`stem`）、`typing`（Optional/Tuple/Dict/Any/List/Sequence）；`re`（净化正则 `[^a-zA-Z0-9._-]+` 暗示，`re`/`os` 为短串未被提取 [中]）
- 文件系统副作用 [高]：向 ComfyUI **input 目录**写入若干 PNG 切片文件（`PNG`/`.png`/`input` 字符串）。
- 配置：无 config.ini / 环境变量 / URL / API Key 痕迹 [高]。

## 5. 错误处理与用户可见文案

全部用户可见中文消息只有 2 条（UTF-8 提取，完整去重）[高]：

| 消息 | 类型 | 触发场景 |
|---|---|---|
| `rows 和 cols 必须大于 0` | `ValueError` | rows 或 cols ≤ 0（routes 层转 HTTP 400） |
| `当前图片尺寸无效，无法拆分` | `ValueError` | 图片宽/高无效（routes 层转 HTTP 400） |

routes 层还可能因 `_resolve_ui_image_path` 抛 FileNotFoundError（404）/ValueError（400）——错误文本由 save_image_with_output_core 的共享路径解析产生，在本模块字符串中未见 [未确认]。

## 6. 证据附录

### 6.1 编译身份
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\grid_split_core.c
custom_nodes/TE_image/source_py_backup/grid_split_core.py
_cython_3_1_2limited_fastcallnofinalize
Module 'grid_split_core' has already been imported. Re-initialisation is not supported.
```

### 6.2 函数限定名（ qualname）
```
custom_nodes.TE_image.grid_split_core._get_pixel_luma
custom_nodes.TE_image.grid_split_core._is_dark_separator_pixel
custom_nodes.TE_image.grid_split_core._detect_dark_bands
custom_nodes.TE_image.grid_split_core._select_separator_bands
custom_nodes.TE_image.grid_split_core._select_separator_bands.search
custom_nodes.TE_image.grid_split_core._select_separator_bands.search.lambda
custom_nodes.TE_image.grid_split_core._build_axis_slices_from_bands
custom_nodes.TE_image.grid_split_core._build_equal_axis_slices
custom_nodes.TE_image.grid_split_core._detect_grid_slices_from_black_lines
custom_nodes.TE_image.grid_split_core._detect_grid_slices_from_black_lines.genexpr
custom_nodes.TE_image.grid_split_core._resolve_ui_image_path
custom_nodes.TE_image.grid_split_core._sanitize_filename_stem
custom_nodes.TE_image.grid_split_core.split_image_to_grid_input_files
```

### 6.3 内名表精选（去掉 Cython 噪声）
```
GRID_SEPARATOR_LUMA_THRESHOLD  GRID_SEPARATOR_DARK_RATIO_THRESHOLD  GRID_SEPARATOR_MIN_BAND_THICKNESS
rows  cols  image_info  filename  subfolder  type  input  input(PNG格式) PNG  RGBA  RGB  convert
crop  save  open  load  close  format  _grid_  02d  .png  te_grid  [^a-zA-Z0-9._-]+  strip  ._-
Path  stem  join  path  uuid4  hex  PIL  Image  ImageOps  exif_transpose  folder_paths
get_input_directory  save_image_with_output_core  resolve_image_info_path
_resolve_shared_image_info_path  horizontal  vertical  axis  band  bands  thickness
averageRatio  internal_bands  separator_bands  separator_count  segment_count
best_score  selected  sorted  start  end  start_index  center  dimension  value  key
min_allowed_width  min_allowed_height  typing  Tuple  Dict  Any  List  Optional  Sequence
```

### 6.4 常量池（.rdata 0x17eb0–0x17f28，影响结果的 double/int）
```
0.02 | 0.0722 | 0.2 | 0.2126 | 0.5 | 0.7152 | 0.9 | 1.0 | 4.0 | 24.0 | 255(int缓存) | 26(int缓存)
初始化批次（PyFloat_FromDouble / PyLong_FromLong → 缓存槽 → PyDict_SetItem 写模块字典）：
  0x1c290 ← 0.9      → GRID_SEPARATOR_DARK_RATIO_THRESHOLD
  0x1c2f0 ← PyLong(26) → GRID_SEPARATOR_LUMA_THRESHOLD
  0x1c2c8 ← PyLong(2)  → GRID_SEPARATOR_MIN_BAND_THICKNESS
```

### 6.5 中文消息（完整提取，无遗漏）
```
rows 和 cols 必须大于 0
当前图片尺寸无效，无法拆分
```

### 6.6 关联文件链
- 调用方：`grid_split_routes.py`（明文双胞胎）L17 `from .grid_split_core import split_image_to_grid_input_files`；L106 `images = split_image_to_grid_input_files(image_info=image_info, rows=rows, cols=cols)`；响应 L107 `{"success": True, "images": images}` → 每项即本模块返回的 `{"filename","subfolder","type":"input"}`。
- 共享依赖：`save_image_with_output_core.pyd` 的 `resolve_image_info_path`。
