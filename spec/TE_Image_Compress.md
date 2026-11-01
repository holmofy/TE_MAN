# TE_Image_Compress.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_Image_Compress`。静态分析（字符串池 / pefile 导入导出表 / image_codec.pyd 交叉核对 / 姊妹模块 TE_Image_Compress_Test.pyd 对照）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

ComfyUI **节点模块**（不在 `__init__.py:21-33` 的 `SKIP_MODULES` 中，会被自动加载）：TE MAN 的 **"TE MAN 图片压缩"** 工具节点。接收上游 IMAGE 张量，模拟"发送给在线 API"的图像编码流程——先用共享编解码库 `image_codec.encode_pil_image_to_api_bytes` 按规则（PNG 超 1MB 时单次 JPEG quality=90）压缩，再打包回张量输出，并给出输入/输出的尺寸与体积报告。README 未单独介绍此节点（grep `压缩` 无命中），属未写进文档的 Utils 小工具。

原始工程路径证据 [高]：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Image_Compress.c`（Cython 生成物）、`custom_nodes/TE_image/source_py_backup/TE_Image_Compress.py`、模块限定名 `custom_nodes.TE_image.TE_Image_Compress`——插件曾名 `TE_image`。

姊妹测试模块 [高]：`TE_Image_Compress_Test.pyd` 同时存在，注册键 `TE_image_pro_compress_test`、显示名"TE MAN 图片缩放压缩测试"，其字符串自述压缩规则为 **"压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG"**——测试节点直接印出了生产节点的压缩策略，本节点行为与之一致（见 §3/§4）。

## 2. Python API

### 2.1 导出
- PE 导出表唯一符号：`PyInit_TE_Image_Compress` [高]。
- DLL 导入仅 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / CRT——无网络库，本模块自身不做任何网络请求 [高]。

### 2.2 模块级对象（名称均为字符串池直接证据 [高]）
- `PLUGIN_DIR`、`MODULE_DIR` [高]——模块目录定位，配合 `os.path`：`abspath`/`dirname`/`basename`/`dirname` [高]（推断同插件其余模块的目录探测模式 [中]）。
- `logger`（`.logger` 包日志器，调用方式未确认）[中]；`disable`/`isenabled` 等词符也在池中，疑似同款日志/告警开关，未确认。
- 第三方导入：`torch`（`from_numpy`/`float32`）、`numpy`（`np`/`asarray`/`astype`/`uint8`/`repeat`/`stack`/`nanmax`/`insert`/`copy`/`from_numpy`）、`PIL.Image`（`Image`/`fromarray`）、`io.BytesIO`、`typing.Tuple/List/Any` [高]。
- 内部支撑导入：`image_codec` → `encode_pil_image_to_api_bytes` [高]（复用关系详见 §4）。

### 2.3 函数清单（qualname 字符串 [高]）
模块级私有辅助（`custom_nodes.TE_image.TE_Image_Compress.*` 限定名）：
- `_shape_to_hw_text`（内含 `<locals>.genexpr`）——把 shape 转成 "H×W" 类文本，用于日志/报告 [高，行为为中推断]。
- `_tensor_to_bhwc_array`——张量 → B,H,W,C 数组（`ndim`/`shape`/`axis`/`repeat`/`insert` 等词符佐证维度规整）[高，行为为中推断]。
- `_sample_to_pil`——单样本数组 → PIL 图（`Image.fromarray`/`astype`/`uint8`/`clip`/`RGB`）[高，行为为中推断]。
- `_pil_to_rgb_sample`——PIL 图 → RGB 单样本数组（`RGB`/`asarray`/`float32`）[高，行为为中推断]。
- `_compress_sample_once_if_needed`——对单样本执行"至多一次"的按需压缩（名称即直接证据；实现推断调用 `encode_pil_image_to_api_bytes`）[高，调用链为中推断]。

### 2.4 ComfyUI 注册 [高]

| 项 | 值 | 证据（pyd 字符串池原文） |
|---|---|---|
| NODE_CLASS_MAPPINGS 键 | **`TE_image_pro_compress`** | `TE_image_pro_compress` [高] |
| 显示名 | **`TE MAN 图片压缩`** | `TE MAN 图片压缩` [高] |
| CATEGORY | **`TE MAN/Utils`** | `TE MAN/Utils` [高] |
| 类名 | `TEImageCompressNode` | 限定名 `custom_nodes.TE_image.TE_Image_Compress.TEImageCompressNode` [高] |
| FUNCTION | `compress_image` | `compress_image` + 限定名 `…TEImageCompressNode.compress_image` [高] |
| RETURN_TYPES | `IMAGE` | `IMAGE`、`RETURN_TYPES`、`RETURN_NAMES` 均在池中 [高] |
| OUTPUT_NODE | 未确认 | 池中仅见 `output`/`output_samples` 词符，无法判定是否设置 UI 输出 [未确认]。→ **已确认（动态回填）：`OUTPUT_NODE` 属性不存在（introspection 读出为 null），非输出节点，纯转换管线** |

## 3. 节点规格（TEImageCompressNode）

### 3.1 输入（INPUT_TYPES）
- 仅存在 `required` 字段（池中词符 [高]）；未发现任何可选组或前端 widget 控件名 [未确认]。
- `required` 内参数，按证据还原 [中]：
  - **`image`**（`IMAGE`）：池中 `image`、`image_value`；`INPUT_TYPES` 限定名 + `required`。上游图像张量输入，唯一确定存在的参数 [中→高]。
  - 其余参数：节点无 tooltip / 枚举文案字符串，除 `image` 外**未确认**是否还有其他参数。池中 `float` 一词更可能是 `float32`/`PyFloat` 词符碎片，不足以证明存在 FLOAT 输入 [未确认]。

### 3.2 返回
- `RETURN_TYPES = (IMAGE,)`，返回名列表存在（`RETURN_NAMES` 串在池中，具体名称未确认；姊妹测试节点有"处理后图片"命名，本节点池中有"压缩后图片"——推断 RETURN_NAMES = `("压缩后图片",)` [中]）。→ **已确认（动态回填）：`RETURN_TYPES=("IMAGE",)`、`RETURN_NAMES=("压缩后图片",)`**。

### 3.3 关键行为（compress_image，按字符串流程还原 [中]）
1. 接收 `image` 张量 → `_tensor_to_bhwc_array` 拆成批次逐样本处理（`batch`/`shape`/`ndim`/`stack`/`axis`/`insert`/`repeat` 词符）。维度校验失败时报"输入图像维度异常: "（`ValueError`）[高，消息直接证据]。
2. 每个样本经 `_sample_to_pil` 转 PIL；对超出规则的样本调用 `_compress_sample_once_if_needed` → `image_codec.encode_pil_image_to_api_bytes`，得到 `(bytes, mime, ext)` 后回读 BytesIO、经 `_pil_to_rgb_sample` 转回 float32 RGB 样本（`BytesIO`/`float32`/`RGB`/`tobytes` 类词符）[中]。
3. 压缩规则（生产节点侧为推断；规则原文来自姊妹测试节点字符串 [中]）：**PNG 体积超 1MB 时做单次 JPEG quality=90 压缩，且仅当 JPEG 产物更小时才改用 JPEG，否则保留 PNG**。即"至多压缩一次、收益不足则回退 PNG"。
4. 全部样本经 `torch.stack` 组回 `[B,H,W,C]` 批量张量，`RETURN_TYPES=("IMAGE",)` 输出 [中]。
5. 输出日志：`"TE 图片压缩完成: "` 前缀 + 统计文本（`_shape_to_hw_text`/` -> `/`: ` 词符，推断拼接输入→输出尺寸/体积对比）[高（前缀串）/中（内容）]。

### 3.4 与姊妹测试节点的分工
- 本节点（`TE_image_pro_compress`）：无界面产物，纯"输入图 → 压缩图"管线，可串接在生图与 API 生成节点之间。
- 测试节点（`TE_image_pro_compress_test`，同 CATEGORY `TE MAN/Utils`）：带缩放选项（"只缩放"/"只压缩"/"缩放+压缩"、"缩放目标: 约 1.0MP"、ComfyUI 缩放失败回退 PIL 最近邻）并输出"压缩报告"（原图/缩放后/最终模拟发送体积）。它公开了共享压缩规则的原文，可作为本节点行为的对照证据。

## 4. 外部依赖与副作用

### 4.1 image_codec.pyd 复用关系（已核对，确认复用）
- 本 pyd 字符串池直接包含：`image_codec`、`encode_pil_image_to_api_bytes` [高]。
- `image_codec.pyd` 侧同样存在 `encode_pil_image_to_api_bytes`（限定名 `custom_nodes.TE_image.image_codec.encode_pil_image_to_api_bytes`）及其返回注解 `Tuple[bytes, str, str]` [高]；spec/image_codec.md 第 3 节亦已将 `TE_Image_Compress` 列为该函数的消费方——两侧证据互证。
- 复用含义：压缩编解码（格式选择、quality、MIME/扩展名判定、超 1MB 规则）全部集中在共享库；本节点只负责张量↔PIL 的批量搬运、按需触发与报告。image_codec 内部证据：`1MB`、`JPEG`、`quality`、`optimize`、`webp`、`png`、`_ENABLE_INPUT_IMAGE_COMPRESSION` 开关、消息"输入图像超过1MB，已单次JPEG压缩: " / "输入图像超过1MB，但JPEG压缩收益不足，保留PNG: " [高]。
- 除 `encode_pil_image_to_api_bytes` 外，本节点未引用 ImageCodec 类 / ErrorCanvas / base64 解码等其它 codec 能力（池中无对应串）[高]。
- 压缩阈值常量（image_codec 模块 `__dict__` 实测，动态回填）：**`_ENABLE_INPUT_IMAGE_COMPRESSION = True`（总开关，实锤布尔值）、`_INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES = 1048576`（恰为 1MB = 1024×1024 字节）、`_INPUT_IMAGE_JPEG_QUALITY = 90`**——正文"PNG 超 1MB / quality=90"的全部数值均已实锤。

### 4.2 其他依赖与副作用
- 网络：**无**（无 URL/端点/API Key 串；DLL 无 WS2_32）[高]。
- 文件系统：无读写路径证据（仅目录探测用 `os.path` 词符）[高]。
- 配置：本模块无 config.ini 键名 [高]；image_codec 侧存在压缩总开关名 `_ENABLE_INPUT_IMAGE_COMPRESSION`（可能来自环境变量或常量，具体读取方式未确认）[中]。
- 第三方库调用迹象：torch / numpy / PIL / io.BytesIO / typing（§2.2）[高]。

## 5. 错误处理与用户可见文案

| 消息（原文） | 触发场景 |
|---|---|
| `输入图像维度异常: ` | `image` 张量维度不符合预期（非 3/4 维图像张量等），抛 `ValueError` [高（串+ValueError 词符）] |
| `TE 图片压缩完成: ` | 每次成功执行的 info 日志前缀，后接统计（尺寸/体积对比，具体格式未确认）[高（前缀）/中（内容）] |
| `TE MAN 图片压缩` | 节点显示名 [高] |
| `压缩后图片` | 推断为输出槽显示名 / 日志用词 [中] |

（本节点不使用 image_codec 的 ErrorCanvas 错误画布——池中无 `ErrorCanvas`/`build_error_tensor_from_text` 串 [高]；失败直接抛异常。）

## 6. 证据附录

### 6.1 身份与注册
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Image_Compress.c
custom_nodes/TE_image/source_py_backup/TE_Image_Compress.py
custom_nodes.TE_image.TE_Image_Compress
PyInit_TE_Image_Compress
TEImageCompressNode / TEImageCompressNode.INPUT_TYPES / TEImageCompressNode.compress_image
TE_image_pro_compress / TE MAN 图片压缩 / TE MAN/Utils
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / INPUT_TYPES / FUNCTION / CATEGORY / RETURN_TYPES / RETURN_NAMES
```

### 6.2 函数与变量名（Cython 限定名对）
```
_shape_to_hw_text / _shape_to_hw_text.<locals>.genexpr
_tensor_to_bhwc_array / _sample_to_pil / _pil_to_rgb_sample
_compress_sample_once_if_needed
output_samples / image_value / _final_size / _final_mime / _path
required / image / batch / output / value / sample
```

### 6.3 库与词符
```
torch / numpy / np / PIL / Image / fromarray / BytesIO / io
asarray / astype / uint8 / float32 / repeat / stack / nanmax / insert / copy
from_numpy / clip / cpu / RGB / ndim / shape / axis / genexpr
os / sys / inspect / typing / Tuple / List / Any
abspath / dirname / basename / replace / open / path
PLUGIN_DIR / MODULE_DIR / source_py_backup
logger / disable / isenabled / ValueError / ImportError
image_codec / encode_pil_image_to_api_bytes
TE_MAN/Utils 中的 Utils、' -> '、': '（报告拼接碎片）
```

### 6.4 中文文案（全集，无遗漏）
```
TE MAN 图片压缩
压缩后图片
TE 图片压缩完成: 
输入图像维度异常: 
```

### 6.5 姊妹测试节点 TE_Image_Compress_Test.pyd 关键串（对照用）
```
TE_image_pro_compress_test / TE MAN 图片缩放压缩测试 / TE MAN/Utils
压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG
缩放目标: 约 1.0MP / 只缩放 / 只压缩 / 缩放+压缩 / 压缩报告
原图 PNG 体积 / 缩放后 PNG 体积 / 最终模拟发送体积 / 处理方式 / 是否缩放
测试节点调用 ComfyUI 缩放失败，使用 PIL 最近邻备用缩放: 
```

### 6.6 image_codec.pyd 侧佐证串
```
custom_nodes.TE_image.image_codec.encode_pil_image_to_api_bytes
Tuple[bytes, str, str]
1MB / JPEG / quality / optimize / webp / png / _ENABLE_INPUT_IMAGE_COMPRESSION
输入图像超过1MB，已单次JPEG压缩: 
输入图像超过1MB，但JPEG压缩收益不足，保留PNG: 
输入图像单次压缩失败，保留PNG: 
```

## 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions `Windows-2025Server` + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载本 pyd 后运行时 introspection。以下均为 `INPUT_TYPES()` 实际返回值与模块 `__dict__` 直接读出。

### (a) INPUT_TYPES 实测全表

```python
{"required": {"image": ("IMAGE",)},
 "optional": None,   # 运行时无 optional 组
 "hidden": None}     # 运行时无 hidden 组
```

实测要点：
- 全节点**仅一个参数** `image`（IMAGE 插槽），选项字典为空 dict——无 tooltip、无 min/max/step、无任何 UI 标志。正文 §3.1"除 image 外未确认是否还有其他参数"就此定论：**没有其他参数**。
- 正文 §3.1 池中 `float` 词符疑为 FLOAT 输入的猜测可排除：无任何数值型输入。

### (b) 节点元数据实测

| 项 | 实测值 |
|---|---|
| 注册键 | `TE_image_pro_compress` |
| 显示名 | `TE MAN 图片压缩` |
| 类名 | `TEImageCompressNode`，模块 `custom_nodes.TE_image.TE_Image_Compress` |
| `FUNCTION` | `compress_image` |
| `CATEGORY` | `TE MAN/Utils` |
| `OUTPUT_NODE` | **不存在**（introspection 读出 null）——**已确认**：非输出节点，纯 IMAGE→IMAGE 转换管线，与 §2.4 "未确认"项定论 |
| `RETURN_TYPES` | `("IMAGE",)` **已确认** |
| `RETURN_NAMES` | `("压缩后图片",)` **已确认**（正文 [中] 推断升级为实锤） |

### (c) 模块常量实锤（运行时 `__dict__` 导出）

| 常量 | 实测值 |
|---|---|
| `MODULE_DIR` / `PLUGIN_DIR` | `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN`（真机安装目录；同一值的两个别名） |
| `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` | 如上注册表 |
| 其余 | 模块级无其他业务常量——**压缩阈值（1MB）与 quality（90）不在本模块**，全部收敛在 `image_codec` 模块（见 (d)） |

### (d) 压缩阈值常量实锤（来自 `TE_MAN.image_codec` 模块 `__dict__`）

正文 §4.1 "image_codec 侧存在 `_ENABLE_INPUT_IMAGE_COMPRESSION` 开关、具体读取方式未确认 [中]" 现已实锤（动态回填）：

| 常量（`TE_MAN.image_codec` 模块级） | 实测值 | 含义 |
|---|---|---|
| `_ENABLE_INPUT_IMAGE_COMPRESSION` | `True` | 压缩总开关，默认启用 |
| `_INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES` | `1048576` | 压缩触发阈值，恰为 1 MB（1024×1024 字节） |
| `_INPUT_IMAGE_JPEG_QUALITY` | `90` | 单次 JPEG 压缩质量 |

即 §3.3 的压缩规则定论：**PNG 编码后体积 > 1048576 字节时，做单次 JPEG quality=90 压缩；仅当 JPEG 产物更小时才改用 JPEG，否则保留 PNG**——三个数值全部为运行时常量实锤，不再依赖姊妹测试节点文案推断。

### (e) 对正文"未确认"项的核对结论

- §2.4 `OUTPUT_NODE`：**已确认不存在**（非输出节点）。
- §3.1 输入参数：**已确认仅 `image` 一个**，无 optional/hidden 组。
- §3.2 `RETURN_NAMES=("压缩后图片",)`：**已确认**。
- 压缩阈值 1MB / JPEG quality=90 / 总开关 `True`：**已确认**（常量在 `image_codec` 模块，见 (d)）。
- `_compress_sample_once_if_needed` 内部调用链、完成日志的统计格式：introspection 不含方法体，仍为未确认。
