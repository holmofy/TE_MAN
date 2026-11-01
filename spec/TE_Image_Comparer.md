# TE_Image_Comparer.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_Image_Comparer`。静态分析（字符串/导入导出表）+ 交叉验证（`web/js/te_image_comparer.js`、`README.md`、`__init__.py`）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

ComfyUI **节点模块**（非支撑库）：实现"TE MAN 图像对比"节点，将两张输入图片在同一预览区域内叠加显示、通过鼠标拖动分界线对比，并提供放大镜功能。由 `__init__.py` 的目录扫描机制动态加载（`directory.glob` → `importlib.import_module` → 合并 `NODE_CLASS_MAPPINGS`，第 39–58 行）。

原源码路径（编译时残留）：`custom_nodes/TE_image/source_py_backup/TE_Image_Comparer.py`，模块限定名 `custom_nodes.TE_image.TE_Image_Comparer`；编译机器路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Image_Comparer.c`。

## 2. Python API

- 导出：`PyInit_TE_Image_Comparer`（PE 导出表唯一符号）[高]
- 导入：仅 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / `api-ms-win-crt-runtime-l1-1-0.dll`。**无网络库（WS2_32 等）、无 GDI/注册表依赖**，纯 Python 逻辑节点 [高]
- Cython 限定 API 构建 flavor：`_cython_3_1_2limited_fastcallnofinalize` [高]

### 模块级公开对象

- 类 `TEMANImageComparerNode` [高]（qualname 串 `custom_nodes.TE_image.TE_Image_Comparer.TEMANImageComparerNode`）
  - 方法：`__init__`（内含一个局部 genexpr，用途未确认）、`INPUT_TYPES`、`compare_images` [高]（qualname 串）
- 注册表：`NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` [高]（字符串存在，且 `__init__.py` 第 57–58 行读取二者）

### ComfyUI 节点注册 [高]

| 项 | 值 | 证据 |
|---|---|---|
| 注册键 | `TE_image_pro_image_comparer` | pyd 字符串；与前端 JS 常量 `NODE_TYPE='TE_image_pro_image_comparer'` 交叉一致 |
| 显示名 | `TE MAN 图像对比` | pyd 中文字符串 |
| CATEGORY | `TE MAN/Utils` | pyd 字符串 |
| FUNCTION | `compare_images` | pyd 字符串（方法名） |
| DESCRIPTION | `在节点内叠加显示两张图片，可拖动分界线进行对比` | pyd 中文字符串 |
| OUTPUT_NODE | 推断为 `True` [中] | `OUTPUT_NODE` 字符串存在；节点产出 UI 图片流（前端 `onExecuted` 接收），与 SaveImage 类节点模式一致。→ **已确认：`OUTPUT_NODE=True`（动态回填，实测布尔值）** |

## 3. 节点规格：TEMANImageComparerNode

### 输入参数（INPUT_TYPES）

- `image_a`：类型 `IMAGE`，位于 `optional` 组，tooltip `对比图片 A（可选）` [高]（字符串 `image_a`、`IMAGE`、`optional`、`required`、`tooltip` 及中文 tooltip 均在）。→ **已确认（动态回填）**
- `image_b`：类型 `IMAGE`，位于 `optional` 组，tooltip `对比图片 B（可选）` [高]。→ **已确认（动态回填）**
- hidden 输入：推断包含 `prompt`（`"PROMPT"`）与 `extra_pnginfo`（`"EXTRA_PNGINFO"`）[中]（字符串 `hidden`、`PROMPT`、`EXTRA_PNGINFO` 存在；这是 SaveImage 系节点的标准 hidden 集）。→ **已确认（动态回填）：hidden 恰为 `{"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}` 两项，无 `unique_id`**
- 两个图片输入均为可选（tooltip 明写"可选"），允许单图对比 [高]
- `required` 组为**空 dict**（动态回填实测）——正文池中 `required` 串的归属就此定论：键存在但无成员。

### 返回

- `RETURN_TYPES` / `RETURN_NAMES` 字符串存在 [高]；具体元组内容未确认。存在 `IMAGE` 字符串，推断可能返回 `("IMAGE",)`（如返回对比结果图）或仿 SaveImage 返回空元组 [低，未确认]。→ **已确认（动态回填）：`RETURN_TYPES=[]`、`RETURN_NAMES=[]`——均为运行时空列表实锤**。节点无任何输出插槽（与 SaveImage 同款模式），`IMAGE` 池串属输入类型引用而非返回类型；"返回 ('IMAGE',)"的猜测被推翻。
- 实际对前端的输出：`compare_images` 产出 `ui.images` 文件引用列表（前端 JS `onExecuted` 消费，`result` / `images` 字符串佐证）[中]

### 关键行为（compare_images）

1. 将 A/B 图片批（内部变量名 `a_images`、`b_images` [高]）写入 ComfyUI **temp 输出目录**：
   - `folder_paths` 模块 + `get_temp_directory` 字符串 [高]
   - 复用/仿照 ComfyUI `SaveImage.save_images` 的落盘流程：字符串 `SaveImage`、`save_images`、`output_dir`、`prefix_append`、`compress_level`、`extra_pnginfo`、`prompt`、`images` 与 `nodes`（`from nodes import SaveImage` 的迹象）[中]
   - 文件名前缀相关字符串：`te_man_compare.` 与 `_temp_compare_` [高]——推断保存的前缀/子路径与二者之一相关，精确组合方式未确认
2. 生成随机后缀防撞名：字符串 `random`、`choice`、`range` 与字符表 `abcdefghijklmnopqrstupvxyz`（原样含拼写异常，缺 `w` 且 `u` 重复）[高]——推断 `''.join(random.choice(...) for _ in range(N))` 形式的随机串 [中]
3. 返回 UI 结果供前端显示 [中]；前端 JS 通过 `/view?filename=...&type=temp&subfolder=...` 拉取已保存图片（`imageUrl()` 中 `type` 默认 `'temp'`）——与后端写 temp 目录交叉印证 [高]

### 前端配套（web/js/te_image_comparer.js，交叉验证）

前端为混淆 JS，以下来自其字符串表与常量：

- 注册扩展 `registerExtension`，在 `onNodeCreated` 定制节点：固定布局常量 `NODE_HEIGHT=0x14a`(330)、`MIN_IMAGE_HEIGHT=0x104`(260)、`CONTROL_HEIGHT=0x26`(38) 等 [高]
- 叠加绘制：`onDrawForeground` 绘制 A/B 叠加图与细分界线；`onMouseMove` 调整分界线位置（README："鼠标在图片区域移动时即可调整 A、B 图片的显示分界线，分界线保持细线显示"）[高]
- **放大镜**：`magnifierEnabled` 开关按钮，圆形放大区 `MAGNIFIER_RADIUS=0x78`(120px)，`DEFAULT_MAGNIFIER_ZOOM=3`，倍率滑条 `MIN_MAGNIFIER_ZOOM=2` / `MAX_MAGNIFIER_ZOOM=7`，悬停 `magnificationHover` 显示滑条（宽 210px）（与 README v3.x "放大镜按钮…默认放大 3 倍…2-7 倍之间调整" 一致）[高]
- 序列化持久化：图片引用存入 `properties['te_image_comparer_images']`（`SERIALIZED_IMAGES_KEY`），并写入 `widgets_values` 与自定义 widget 值，`onSerialize` / `onConfigure` 恢复 [高]
- **Nodes 2.0 适配**（即 README 所述"图像对比节点在 Nodes 2.0 下对比界面与鼠标交互已修复"）：
  - `isVueNodeMode()` 检测 Vue 节点模式；在节点 DOM 元素上创建 overlay（class `te-image-comparer-overlay`）
  - 绑定 `pointerdown/pointermove/pointerup/pointerenter/pointerleave` → 转发到节点 `onMouseDown/onMouseMove/onMouseUp/onMouseEnter/onMouseLeave`，坐标经 `toComparerLocalPos` 按画布 `ds.scale` 换算，并 `preventDefault/stopPropagation/stopImmediatePropagation` 阻断事件冒泡到画布（防止误触发画布拖动/框选）[高]

## 4. 外部依赖与副作用

- **网络端点：无。** 无任何 URL/API Key/网络库导入 [高]
- **文件系统写入：** ComfyUI temp 输出目录（`folder_paths.get_temp_directory()`）[中]；写对比预览图文件，前缀见 `te_man_compare.` / `_temp_compare_` [高（字符串）/中（用途）]
- **第三方/内部模块引用迹象**：`folder_paths`、`nodes`（SaveImage）、`random`、`inspect`（Cython 运行时）、`types`、`asyncio.coroutines`（Cython 内部）[中]

## 5. 错误处理与用户可见文案

本模块中文串极少，无独立错误消息（错误处理依赖 ComfyUI 框架与 SaveImage 流程）：

- `对比图片 A（可选）` —— image_a 输入的 tooltip [高]
- `对比图片 B（可选）` —— image_b 输入的 tooltip [高]
- `在节点内叠加显示两张图片，可拖动分界线进行对比` —— 节点 DESCRIPTION [高]
- `TE MAN 图像对比` —— 节点显示名 [高]
- 输入图片缺失处理：前端 `firstImage()`/`copyImageData()` 对空引用返回 `null`，对应"两输入均可选"的设计 [中]

## 6. 证据附录

### 注册与结构（pyd 字符串）
```
PyInit_TE_Image_Comparer
TE_image_pro_image_comparer
TE MAN 图像对比
TE MAN/Utils
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS
TEMANImageComparerNode
custom_nodes.TE_image.TE_Image_Comparer.TEMANImageComparerNode.__init__
custom_nodes.TE_image.TE_Image_Comparer.TEMANImageComparerNode.__init__.genexpr
custom_nodes.TE_image.TE_Image_Comparer.TEMANImageComparerNode.INPUT_TYPES
custom_nodes.TE_image.TE_Image_Comparer.TEMANImageComparerNode.compare_images
custom_nodes/TE_image/source_py_backup/TE_Image_Comparer.py
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Image_Comparer.c
```

### 节点定义与行为（pyd 字符串，去 Cython 运行时噪声）
```
在节点内叠加显示两张图片，可拖动分界线进行对比
对比图片 A（可选） / 对比图片 B（可选）
image_a / image_b / a_images / b_images / images
IMAGE / optional / required / tooltip / hidden
FUNCTION / CATEGORY / RETURN_TYPES / RETURN_NAMES / OUTPUT_NODE / DESCRIPTION
compare_images / SaveImage / save_images / output_dir / prefix_append / compress_level
folder_paths / get_temp_directory / _temp_compare_ / te_man_compare.
PROMPT / EXTRA_PNGINFO / prompt / extra_pnginfo
random / choice / range / abcdefghijklmnopqrstupvxyz
result / value / nodes
```

### 前端交叉验证（web/js/te_image_comparer.js）
```
NODE_TYPE='TE_image_pro_image_comparer'
SERIALIZED_IMAGES_KEY='te_image_comparer_images'
NODE_HEIGHT=0x14a  MIN_IMAGE_HEIGHT=0x104  CONTROL_HEIGHT=0x26
DEFAULT_MAGNIFIER_ZOOM=0x3  MIN_MAGNIFIER_ZOOM=0x2  MAX_MAGNIFIER_ZOOM=0x7  MAGNIFIER_RADIUS=0x78
'pointerdown'/'pointermove'/'pointerup' → onMouseDown/onMouseMove/onMouseUp …
'te-image-comparer-overlay' / 'onDrawForeground' / 'onExecuted' / 'onSerialize' / 'onConfigure'
api.apiURL('/view?' + {filename, type:'temp', subfolder, ...})
字符串表含：'magnifierEnabled','magnifierZoom','magnifierHover','magnificationHover','vueNodesMode','stopPropagation'
```

### README（/Users/holmofy/Downloads/TE_MAN/README.md）
- 第 42 行：「图像对比节点在 Nodes 2.0 下对比界面与鼠标交互已修复」
- 第 90–96 行：新增 TE MAN 图像对比节点——同区域叠加显示、鼠标移动调整分界线（细线）、放大镜默认 3 倍、倍率 2–7 倍可调

## 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions `Windows-2025Server` + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载本 pyd 后运行时 introspection。以下均为 `INPUT_TYPES()` 实际返回值与模块 `__dict__` 直接读出。

### (a) INPUT_TYPES 实测全表

```python
{"required": {},                      # 运行时实测：空 dict
 "optional": {
    "image_a": ("IMAGE", {"tooltip": "对比图片 A（可选）"}),
    "image_b": ("IMAGE", {"tooltip": "对比图片 B（可选）"})},
 "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}
```

实测要点：
- `image_a` / `image_b`：均在 optional 组，IMAGE 插槽，仅带 tooltip，无 forceInput/无 UI 标志。
- `required` 为空 dict（键存在但无成员）——正文"`required` 串存在"的归属定论。
- hidden 恰两项：`prompt: PROMPT`、`extra_pnginfo: EXTRA_PNGINFO`，**无 `unique_id`**（正文 [中] 推断证实且收窄）。
- 无 min/max/step 数值参数。

### (b) 节点元数据实测

| 项 | 实测值 |
|---|---|
| 注册键 | `TE_image_pro_image_comparer` |
| 显示名 | `TE MAN 图像对比` |
| 类名 | `TEMANImageComparerNode`，模块 `custom_nodes.TE_image.TE_Image_Comparer` |
| `FUNCTION` | `compare_images` |
| `CATEGORY` | `TE MAN/Utils` |
| `OUTPUT_NODE` | `True`（实测布尔值）——**已确认**（正文 [中] 推断定论） |
| `RETURN_TYPES` | **`[]`（空列表）**——**已确认**：无输出插槽，仿 SaveImage 纯输出节点模式 |
| `RETURN_NAMES` | **`[]`（空列表）**——**已确认** |

### (c) 模块常量实锤（运行时 `__dict__` 导出）

模块级常量仅有 `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS`（如上注册表），**无其他业务常量**——前缀串 `te_man_compare.` / `_temp_compare_` 等为函数内部字面量，不挂模块 `__dict__`。

### (d) 对正文"未确认"项的核对结论

- `RETURN_TYPES`/`RETURN_NAMES`：**已确认为空列表 `[]`**——节点是"仅 UI 输出、无数据输出插槽"的对比预览节点（OUTPUT_NODE=True + 空 RETURN_TYPES，SaveImage 同款模式），正文两种猜测中"仿 SaveImage 返回空元组"的方向正确，且运行时形态为空 list。
- `OUTPUT_NODE=True`：**已确认**。
- hidden 集合：**已确认恰为 `PROMPT` + `EXTRA_PNGINFO`**。
- `required` 组：**已确认为空**。
- `te_man_compare.` / `_temp_compare_` 的精确组合方式、随机后缀长度：introspection 不含方法体，仍为未确认。

