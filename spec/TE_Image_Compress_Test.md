# TE_Image_Compress_Test.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_Image_Compress_Test`。静态分析（字符串池 / pefile 导入导出表），并与已完成规格 `spec/TE_Image_Compress.md`（正式节点）及 `spec/image_codec.md`（共享编解码库）交叉对照。
> 置信度说明：[高] = 字符串/导入导出直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

ComfyUI **节点模块**（不在 `__init__.py:21-33` 的 `SKIP_MODULES` 中，会被自动加载），是正式节点 **`TE_image_pro_compress`（TE MAN 图片压缩）的姊妹"测试/实验"节点**：注册键 `TE_image_pro_compress_test`，显示名 **"TE MAN 图片缩放压缩测试"**。与正式节点同属 `TE MAN/Utils` 分类，行为基础相同（张量↔PIL 搬运 + `image_codec.encode_pil_image_to_api_bytes` 按需压缩），但在其上叠加了**可选的降采样（缩放）**与**面向用户的 STRING "压缩报告"输出**，把原本藏在 `image_codec` 内部的压缩规则显式打印出来。README 未见介绍（grep `compress|缩放|压缩` 无命中），属未写进文档的调试/实验工具。

原始工程路径证据 [高]：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Image_Compress_Test.c`、`custom_nodes/TE_image/source_py_backup/TE_Image_Compress_Test.py`、模块合法名 `custom_nodes.TE_image.TE_Image_Compress_Test`（插件曾名 `TE_image`，与正式节点同一源目录）。

## 2. Python API

### 2.1 导出与导入
- PE 导出表唯一符号：`PyInit_TE_Image_Compress_Test` [高]。
- DLL 导入仅 `python3.dll` / `KERNEL32.dll` / `VCRUNTIME140.dll` / `api-ms-win-crt-runtime-l1-1-0.dll`——**无网络库（无 WS2_32），本模块自身不做任何网络请求** [高]。

### 2.2 模块级对象（字符串池直接证据，除注明外均为 [高]）
- `PLUGIN_DIR`、`MODULE_DIR`、`source_py_backup`——目录定位，配合 `os.path`（`abspath`/`dirname`/`basename`）[高]。
- `MODE_OPTIONS`、`MODE_SCALE_ONLY`、`MODE_COMPRESS_ONLY`、`MODE_SCALE_AND_COMPRESS`——模块级处理模式常量 [高]；对应中文取值 `只缩放` / `只压缩` / `缩放+压缩`（对应关系为语义推断 [中]，三者均在池中 [高]）。→ **已确认（动态回填）：`MODE_COMPRESS_ONLY="只压缩"`、`MODE_SCALE_ONLY="只缩放"`、`MODE_SCALE_AND_COMPRESS="缩放+压缩"`，`MODE_OPTIONS=["只压缩","只缩放","缩放+压缩"]`（运行时列表实测，注意"只压缩"在首位）**。
- `OFFICIAL_SCALE_METHOD`——官方缩放方法常量 [高]，推断取值 `nearest-exact`（该串在池中，且 ComfyUI `common_upscale` 支持此方法名）[中]。→ **已确认：`OFFICIAL_SCALE_METHOD="nearest-exact"`（动态回填）**。
- `DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS`——缩放目标百万像素常量 [高]；具体数值为编译期常量未入池，依据报告串 `缩放目标: 约 1.0MP` 推断默认 **1.0 MP** [中]。→ **已确认：`DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS=1.0`（运行时浮点常量实测，动态回填）**。
- `logger`（`.logger` 包日志器）；`enable`/`disable`/`disabled`/`isenabled` 词符同正式节点，疑似日志开关，未确认。
- 第三方导入：`torch`（`from_numpy`/`float32`/`stack`/`movedim`/`unsqueeze`/`squeeze`）、`numpy`（`np`/`asarray`/`astype`/`uint8`/`repeat`/`insert`/`nanmax`）、`PIL.Image`（`Image`/`fromarray`/`RGB`）+ `PIL.Image.Resampling`（`Resampling`/`NEAREST`）、`io.BytesIO`、`math`、`str` 格式化（`round`/`.1f`/`format`）、`typing.Tuple`、`Image` 的 `resize`/`save` [高，各词符均在池]。
- ComfyUI 导入：`comfy.utils` + `common_upscale` [高，限定名直接在池中]——**正式节点（TE_Image_Compress）不引用 comfy.utils**，这是两者的重要区别。
- 内部支撑导入：`image_codec` → `encode_pil_image_to_api_bytes` [高]（复用关系见 §4.1）。
- 独立短串 `Image` 的 `mode` 属性证据与参数名 `mode` 可能共用池串，见 §3.1 说明 [中]。

### 2.3 函数清单（qualname 字符串 [高]，限定名前缀 `custom_nodes.TE_image.TE_Image_Compress_Test.*`）
模块级私有辅助，其中前 4 个与正式节点同名同构（对照 `spec/TE_Image_Compress.md` §2.3）：
- `_shape_to_hw_text`（含 `<locals>.genexpr`）——shape → "H×W" 类文本（短串 `x` 在池中，推断作为维度连接符 [中]）。
- `_tensor_to_bhwc_array`——张量 → B,H,W,C 批次数组（`ndim`/`shape`/`axis`/`repeat`/`insert` 佐证维度规整）。
- `_sample_to_pil`——单样本数组 → PIL 图（`fromarray`/`astype`/`uint8`/`clip` 类词符）。
- `_pil_to_rgb_sample`——PIL 图 → float32 RGB 样本（`RGB`/`asarray`/`float32`）。
- ★ 测试节点独有：
  - `_png_size_bytes`——把 PIL 图编码为内存 PNG 并返回字节数（`save` + `BytesIO` + `getvalue` 词符佐证；`image/png` 也在此模块池中，仅用于体积探测，不用于输出编码）[高（名称）/中（实现）]。
  - `_scale_sample_to_total_pixels_if_needed`——若样本总像素超过目标（`DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS`）则降采样到约目标像素（`math` 词符推测用 `sqrt` 求缩放系数 [中]；`common_upscale`/`movedim`/`unsqueeze`/`squeeze` 佐证先转 torch 再走 ComfyUI 官方缩放，失败回退 `Image.resize` + `Resampling.NEAREST`，回退消息原文见 §5）[高（名称与消息）/中（实现）]。
  - `_compress_sample_once_if_needed`——"至多一次"按需压缩（调用 `encode_pil_image_to_api_bytes`，与生产节点同链路）[高（名称）/中（调用链）]。

### 2.4 ComfyUI 注册 [高]

| 项 | 值 | 证据（pyd 字符串池原文） |
|---|---|---|
| NODE_CLASS_MAPPINGS 键 | **`TE_image_pro_compress_test`** | `TE_image_pro_compress_test` |
| 显示名 | **`TE MAN 图片缩放压缩测试`** | 同名串 |
| CATEGORY | **`TE MAN/Utils`** | `TE MAN/Utils` |
| 类名 | `TEImageCompressTestNode` | 限定名 `…TEImageCompressTestNode.INPUT_TYPES` / `…process_image` |
| FUNCTION | **`process_image`** | `process_image` + 限定名 `…TEImageCompressTestNode.process_image` |
| RETURN_TYPES | **`(IMAGE, STRING)`** | 池中同时有 `IMAGE` 与 `STRING`、`RETURN_TYPES`、`RETURN_NAMES` [高]；顺序推断 image 在前、report 在后 [中]。→ **顺序已确认：IMAGE 在前、STRING 在后（动态回填）** |
| RETURN_NAMES | **`("处理后图片", "压缩报告")`** | `处理后图片`、`压缩报告` 均在池中 [高]。→ **已确认（动态回填）** |
| OUTPUT_NODE | 无证据 | 池中无 `OUTPUT_NODE`/`preview` 串，推断未设置 UI 输出 [中（缺失证据）]。→ **已确认（动态回填）：`OUTPUT_NODE` 属性不存在（introspection 读出为 null），非输出节点** |

## 3. 节点规格（TEImageCompressTestNode）

### 3.1 输入（INPUT_TYPES）
- `required` 必有（词符 [高]）；无 `OPTIONAL` 词符 [高（缺失）]。→ **已确认（动态回填）：无 optional/hidden 组，全部参数在 required**。
- 推断参数 [中→高]：
  - **`image`**（`IMAGE`）：上游图像张量，池中 `image`/`image_value`/`output_samples`。→ **已确认（动态回填）**。
  - **`mode`**（COMBO）：方式下拉，选项 `MODE_OPTIONS` = `只缩放`/`只压缩`/`缩放+压缩` 三者之一列表（池中 `MODE_OPTIONS` 与三个中文串 [高]）；默认值未入池 **未确认**（池中有 `default` 词符，推断 INPUT 配置含 default 项 [中]）。说明：池中同时存在独立中文串 `处理方式`（出现 2 次）与报告前缀 `处理方式: `（1 次）；且 `process_image` 限定名旁也紧邻出现一次 `处理方式`。最可能的解释：`mode` 为参数名/键，`处理方式` 为该参数的用户标签或报告用词，但 ComfyUI 挂接点（tooltip/label）无 `tooltip`/`label` 词符佐证，**未确认**。→ **动态回填更正：实际参数名就是中文 `处理方式`（非 `mode`）**——COMBO 选项 `["只压缩","只缩放","缩放+压缩"]`、默认 `"只压缩"`、无 tooltip；`mode` 并非 INPUT_TYPES 参数名（池中 `mode` 应为 PIL Image 的 `.mode` 属性访问串，与 §2.2 末条"独立短串 `Image` 的 `mode` 属性"吻合）。
  - **`megapixels`**（数值型，FLOAT 推断）：缩放目标，池中参数名 `megapixels` [高]；默认值未知，推断 `DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS` = 1.0（依据固定文案 `缩放目标: 约 1.0MP`）[中]。类型（FLOAT/INT）未确认。→ **动态回填更正：INPUT_TYPES 中没有 `megapixels` 参数**——缩放目标不可由用户调整，固定取模块常量 `DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS=1.0`；池中 `megapixels` 为函数内部局部名/常量名。
- 说明：`缩放目标: 约 1.0MP` 为无缩进的完整字面串 [高]——若 `megapixels` 可由用户改为其他值，报告仍打印该固定文案则与动态取值矛盾，故也可能它是报告中的固定说明行或 UI 文案，两种用法**未确认**。→ **已确认（动态回填）：为报告中的固定说明行**——因缩放目标不可由用户设置（无对应输入参数），报告恒打印该固定文案，两种解释中的后者成立。

### 3.2 返回
- `RETURN_TYPES = (IMAGE, STRING)`：`处理后图片`（IMAGE，同正式节点的压缩产物管线）+ `压缩报告`（STRING，多行报告文本）[高（两名称在池）/中（顺序对应）]。
- 报告内容由 `report_lines`/`report`/`format`/`round`/`KB`/`.1f` 等词符支持的逐行拼接而成，行结构见 §3.3 第 5 步。

### 3.3 关键行为（process_image，按字符串流程还原 [中]）
1. `image` 张量 → `_tensor_to_bhwc_array` 拆批逐样本（`batch`/`index`/`enumerate`）；维度失败抛 `ValueError("输入图像维度异常: ")` [高（消息原文）]。
2. 每样本 `_sample_to_pil` 后先测 **`original_png_size` = `_png_size_bytes(pil)`**（当前图按 PNG 内存编码测体积），记录 `original_shape`（两变量名均在池中 [高]）。
3. **缩放分支**（`do_scale` 词符 [高]，即 mode ∈ {只缩放, 缩放+压缩}）：若总像素超 `megapixels` 目标 → `_scale_sample_to_total_pixels_if_needed`：优先 `comfy.utils.common_upscale`（方法 `OFFICIAL_SCALE_METHOD`=`nearest-exact` [中]），异常回退 `Image.resize + Resampling.NEAREST` 并输出消息"测试节点调用 ComfyUI 缩放失败，使用 PIL 最近邻备用缩放: " [高]；随后记录 `after_scale_shape`、`after_scale_png_size = _png_size_bytes(...)`（变量名均在池 [高]）。mode=只压缩/无溢出时跳过，`scaled` 词符佐证有"是否缩放过"状态 [中]。
4. **压缩分支**（`do_compress` 词符 [高]，即 mode ∈ {只压缩, 缩放+压缩}）：`_compress_sample_once_if_needed` → `image_codec.encode_pil_image_to_api_bytes` 得 `(bytes, final_mime, _path 扩展名)`，BytesIO 回读 → `_pil_to_rgb_sample` 转回 float32 RGB 样本；`final_size`/`final_mime` 变量名在池 [高]。
5. **报告拼接**（`report_lines`/`join`/`format` 推断 [中]，行字面串均直接证据 [高]）——修复后的报告结构（带缩进的行池中带两个前导空格）：
   - `处理方式: ` + 模式值；`缩放目标: 约 1.0MP`（无缩进行 [高]）
   - `  原图尺寸: ` + `_shape_to_hw_text(original_shape)`；`  原图 PNG 体积: ` + KB 文本（`KB`/`round`/`.1f` 词符）
   - `  是否缩放: ` + `是`/否（独立短串 `是` 在池中 [中]；`否` 未确认）
   - `  缩放后尺寸: `、`  缩放后 PNG 体积: `（仅缩放分支时）
   - `  最终模拟发送体积: `、`  最终模拟发送格式: `
   - 尾行规则说明：`压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG`（无缩进完整字面串 [高]）
   - 拼为 `压缩报告` STRING 输出（`压缩报告` 作为报告标题/输出名的用法未确认）。
6. 样本组回 `[B,H,W,C]` 批量张量（`stack`/`output_samples`/`IMAGE`），随 STRING 报告一起返回。
7. 完成日志：`TE 图片缩放压缩测试完成: ` 前缀（[高]，与正式节点的 `TE 图片压缩完成: ` 不同）+ 统计（内容格式未确认；池中 `图片 ` 碎片疑似批内索引文案 [低]）。

### 3.4 与正式节点 TE_Image_Compress.pyd 的差异（重点对比）
共同点 [高]：同一源目录 `custom_nodes/TE_image/source_py_backup/`；共享 5 个同名辅助函数（`_shape_to_hw_text`/`_tensor_to_bhwc_array`/`_sample_to_pil`/`_pil_to_rgb_sample`/`_compress_sample_once_if_needed`）；同样复用 `image_codec.encode_pil_image_to_api_bytes`；同样只做一次 JPEG q=90 的超 1MB 压缩且收益不足回退 PNG；同样的维度错误消息 `输入图像维度异常: `；DLL 导入表相同（无网络库）。

| 维度 | 正式节点（TE_Image_Compress） | 测试节点（本模块） | 置信度 |
|---|---|---|---|
| 注册键 / 显示名 | `TE_image_pro_compress` / `TE MAN 图片压缩` | `TE_image_pro_compress_test` / `TE MAN 图片缩放压缩测试` | [高] |
| 执行方法 FUNCTION | `compress_image` | **`process_image`** | [高] |
| 输入 | 仅 `image`（其余未确认） | `image` + **`处理方式`（三种处理方式下拉，参数名即中文）**；缩放目标为固定常量 1.0MP（无用户输入参数） | 测试侧已确认（动态回填），正式侧仅 image 已确认（动态回填） || 输出 | 仅 IMAGE（"压缩后图片"） | **IMAGE + STRING（"压缩报告"）** | [高] |
| 缩放能力 | 无 | **有**：超目标像素时先缩放（`comfy.utils.common_upscale` + PIL 最近邻回退） | 测试侧 [高]，正式侧依据其池中无 common_upscale/comfy.utils 词符 [中（缺失证据）] |
| 独有辅助函数 | 无 | `_png_size_bytes`（PNG 体积探测）、`_scale_sample_to_total_pixels_if_needed`（降采样） | [高] |
| 与 comfy 的耦合 | 无 comfy 词符 | `comfy.utils`/`common_upscale` | [高] |
| 调试输出 | 仅 info 日志前缀 | **多行"压缩报告"**（处理方式/缩放目标/原图尺寸与 PNG 体积/是否缩放/缩放后尺寸与体积/最终模拟发送体积与格式/压缩规则说明） | [高] |
| 压缩规则透明度 | 规则实现在 `image_codec` 内部，节点不打印 | **规则原文明文打印**："压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG" | [高] |
| 完成日志前缀 | `TE 图片压缩完成: ` | `TE 图片缩放压缩测试完成: ` | [高] |
| 格式/体积探测 | 不探测 PNG 体积 | `_png_size_bytes` 三点测体积（原图/缩放后/最终发送） | [高] |

即：测试节点是"带仪表盘的放大版正式节点"——正式节点把编排（张量搬运 + 按需触发压缩）交给用户看不见；测试节点把每一步（缩放与否、PNG 体积、最终 mime/体积）都显式报告，方便调试与调参。

## 4. 外部依赖与副作用

### 4.1 image_codec.pyd 复用（同正式节点，已确认）
- 本 pyd 字符串池直接包含 `image_codec`、`encode_pil_image_to_api_bytes` [高]；`spec/image_codec.md` 第 3 节已把 `TE_Image_Compress`(+`_Test`) 列为该函数消费方，两侧互证。
- 压缩编解码（1MB 阈值、JPEG quality=90、收益判断、回退 PNG）全部在共享库；本模块另有 `_ENABLE_INPUT_IMAGE_COMPRESSION` 等常量的消费关系未确认（池中无这些常量名，仅 `image_codec` 函数名 [高]）。
- 未引用 `ImageCodec` 类 / `ErrorCanvas` / base64 解码等其他 codec 能力（池中无对应串）[高（缺失证据）]。

### 4.2 其他依赖与副作用
- **comfy.utils（新增依赖）**：`comfy.utils` + `common_upscale` [高]，且以 try/except 包裹（`ImportError` 词符 + 回退消息 [中]）——ComfyUI 缩放失败不影响节点运行（PIL 兜底）。
- 网络：**无**（无 URL/端点/API Key 串；DLL 无 WS2_32）[高]。
- 文件系统：无读写路径证据（仅目录探测 `os.path` 词符）[高]。
- 配置：无 config.ini 键名 [高]；`DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS`/`OFFICIAL_SCALE_METHOD` 为模块常量，数值未入池 [未确认]。
- 第三方库：torch / numpy / PIL（Image、Resampling）/ io.BytesIO / math / typing [高]。

## 5. 错误处理与用户可见文案（中文全集，无遗漏）

| 消息（原文） | 触发场景 [中] |
|---|---|
| `输入图像维度异常: ` | image 张量维度异常，抛 `ValueError`（`ValueError` 词符在池 [高]）——与正式节点同一消息 |
| `测试节点调用 ComfyUI 缩放失败，使用 PIL 最近邻备用缩放: ` | comfy.utils.common_upscale 异常（含 ImportError），回退 PIL `Resampling.NEAREST`，节点不失败 |
| `TE 图片缩放压缩测试完成: ` | 每次成功执行的 info 日志前缀（后接统计，格式未确认） |
| `压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG` | 打印进压缩报告的规则说明（同 image_codec 内部实际逻辑） |
| `TE MAN 图片缩放压缩测试` / `处理后图片` / `压缩报告` | 节点显示名 / 返回槽名 |
| 报告行前缀：`处理方式: `、`缩放目标: 约 1.0MP`、`  原图尺寸: `、`  原图 PNG 体积: `、`  是否缩放: `、`  缩放后尺寸: `、`  缩放后 PNG 体积: `、`  最终模拟发送体积: `、`  最终模拟发送格式: ` | STRING 输出逐行内容 |
| （无 ErrorCanvas/错误画布） | 池中无 `ErrorCanvas`/`build_error_tensor_from_text` 串 [高（缺失证据）]，失败直接抛异常，与正式节点一致 |

## 6. 证据附录

### 6.1 身份与注册
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Image_Compress_Test.c
custom_nodes/TE_image/source_py_backup/TE_Image_Compress_Test.py
custom_nodes.TE_image.TE_Image_Compress_Test
PyInit_TE_Image_Compress_Test
TEImageCompressTestNode / TEImageCompressTestNode.INPUT_TYPES / TEImageCompressTestNode.process_image
TE_image_pro_compress_test / TE MAN 图片缩放压缩测试 / TE MAN/Utils
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / INPUT_TYPES / FUNCTION / CATEGORY / RETURN_TYPES / RETURN_NAMES
```

### 6.2 函数与变量名（Cython 限定名对 / 局部名）
```
_shape_to_hw_text / _shape_to_hw_text.<locals>.genexpr
_tensor_to_bhwc_array / _sample_to_pil / _pil_to_rgb_sample
_png_size_bytes / _scale_sample_to_total_pixels_if_needed / _compress_sample_once_if_needed
process_image / __defaults__ / __pyx_defaults / __pyx_scope_struct__genexpr
MODE_OPTIONS / MODE_SCALE_ONLY / MODE_COMPRESS_ONLY / MODE_SCALE_AND_COMPRESS
OFFICIAL_SCALE_METHOD / DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS
do_scale / do_compress / scaled / megapixels / image_value / sample / batch / index
original_shape / original_png_size / after_scale_shape / after_scale_png_size
final_size / final_mime / _path / output_samples / report / report_lines
resample / resize / common_upscale / movedim / unsqueeze / squeeze / getvalue / save
```

### 6.3 库与词符
```
torch / numpy / np / PIL / Image / fromarray / RGB / Resampling / NEAREST / nearest-exact
BytesIO / io / asarray / astype / uint8 / float32 / repeat / insert / stack / nanmax
from_numpy / movedim / unsqueeze / squeeze / math / round / .1f / format / KB / x
comfy / comfy.utils / common_upscale / image_codec / encode_pil_image_to_api_bytes
os / sys / str / inspect / typing / Tuple / logger / enable / disable / disabled / isenabled
abspath / dirname / basename / replace / PLUGIN_DIR / MODULE_DIR / source_py_backup
default / ValueError / ImportError / STRING / IMAGE / required / image / mode
```

### 6.4 中文文案（UTF-8 全集，逐条原样）
```
TE MAN 图片缩放压缩测试
处理后图片
压缩报告
处理方式                 （独立串 ×2）
处理方式:                （报告行前缀）
缩放目标: 约 1.0MP
压缩规则: PNG 超过 1MB 时，单次 JPEG quality=90；JPEG 更小时才使用 JPEG
  原图尺寸: 
  原图 PNG 体积: 
  是否缩放: 
  缩放后尺寸: 
  缩放后 PNG 体积: 
  最终模拟发送体积: 
  最终模拟发送格式: 
只缩放 / 只压缩 / 缩放+压缩
是                       （独立短串 [中]；"否" 未确认）
TE 图片缩放压缩测试完成: 
输入图像维度异常: 
测试节点调用 ComfyUI 缩放失败，使用 PIL 最近邻备用缩放: 
```
（另有碎片 ` PNG `×2、`: PNG `、` 1MB `、` JPEG quality=90`、`JPEG `、` JPEG`——经字节核对均为"压缩规则"整串的子片段，非独立文案。）

### 6.5 正式节点教训引证（本规格的对照基线，全文见 spec/TE_Image_Compress.md）
```
TE_image_pro_compress / TE MAN 图片压缩 / compress_image / 压缩后图片 / TE 图片压缩完成: 
输入图像维度异常:   （两节点共用）
正式节点池中无：comfy.utils / common_upscale / STRING / 压缩报告 / mode / megapixels 等测试侧词符
```

### 6.6 未确认事项汇总
- `mode` 输入的默认值与三个选项的枚举顺序：未确认（编译期常量不入池）。→ 动态回填已解决：参数名实为中文 `处理方式`，默认 `"只压缩"`，顺序见回填节。
- `megapixels` 的确切类型（FLOAT/INT）与默认值：未确认（1.0 为文案推断）。→ 动态回填已解决：无此输入参数，缩放目标固定为常量 1.0。
- `DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS`、`OFFICIAL_SCALE_METHOD` 的实际常量值（推测 1.0 / "nearest-exact"）：[中]。→ 动态回填已确认：`1.0` / `"nearest-exact"`。
- 独立串 `处理方式`（无冒号）的挂接点（INPUT 标签还是报告用词）：未确认（无 `tooltip`/`label` 词符佐证）。→ 动态回填已解决：两者皆是——既是 INPUT 参数名，也是报告行前缀 `处理方式: ` 的用词来源。
- `否` 是否作为 `是否缩放: ` 的取值存在：未确认（仅一处可疑字节命中）。→ 仍未确认（introspection 不含方法体字符串）。
- 压缩报告各行的拼接格式（`{:.1f} KB` 等）：[中]，具体字符串未确认。→ 仍未确认。

## 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions `Windows-2025Server` + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载本 pyd 后运行时 introspection。以下均为 `INPUT_TYPES()` 实际返回值与模块 `__dict__` 直接读出。**本节包含对正文 §3.1 的两处重要更正（参数名 `mode`→`处理方式`、无 `megapixels` 输入）。**

### (a) INPUT_TYPES 实测全表

```python
{"required": {
    "image":  ("IMAGE",),                                        # 选项字典为空 dict
    "处理方式": (["只压缩", "只缩放", "缩放+压缩"], {"default": "只压缩"})},
 "optional": None,
 "hidden": None}
```

实测要点：
- `image`：IMAGE 插槽，无 tooltip/无 UI 标志。
- **`处理方式`**：COMBO widget，参数名直接用中文标识符；选项列表运行时实测为 `["只压缩", "只缩放", "缩放+压缩"]`（与模块常量 `MODE_OPTIONS` 一致，"只压缩"在首位），`default="只压缩"`，无 tooltip/label。
- **没有 `megapixels` 输入参数**——正文 §3.1 对 `megapixels` 类型的疑问就此了结：缩放目标不接受用户输入。
- 无 optional/hidden 组，无 min/max/step 数值参数。

### (b) 节点元数据实测

| 项 | 实测值 |
|---|---|
| 注册键 | `TE_image_pro_compress_test` |
| 显示名 | `TE MAN 图片缩放压缩测试` |
| 类名 | `TEImageCompressTestNode`，模块 `custom_nodes.TE_image.TE_Image_Compress_Test` |
| `FUNCTION` | `process_image` |
| `CATEGORY` | `TE MAN/Utils` |
| `OUTPUT_NODE` | **不存在**（introspection 读出 null）——**已确认**非输出节点 |
| `RETURN_TYPES` | `("IMAGE", "STRING")` **已确认**（IMAGE 在前、STRING 在后） |
| `RETURN_NAMES` | `("处理后图片", "压缩报告")` **已确认** |

### (c) 模块常量实锤（运行时 `__dict__` 导出）

| 常量 | 实测值 |
|---|---|
| `DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS` | `1.0`（浮点）**已确认**——正文 [中] 推断定论 |
| `MODE_COMPRESS_ONLY` | `"只压缩"` **已确认** |
| `MODE_SCALE_ONLY` | `"只缩放"` **已确认** |
| `MODE_SCALE_AND_COMPRESS` | `"缩放+压缩"` **已确认** |
| `MODE_OPTIONS` | `["只压缩", "只缩放", "缩放+压缩"]`（列表，首项"只压缩"）**已确认** |
| `OFFICIAL_SCALE_METHOD` | `"nearest-exact"` **已确认**——正文 [中] 推断定论 |
| `MODULE_DIR` / `PLUGIN_DIR` | `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN`（真机安装目录） |
| `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` | 如上注册表 |

### (d) 对正文"未确认"项的核对结论

- **§3.1 更正 1**：COMBO 参数名是中文 `处理方式`（默认"只压缩"），不是 `mode`；池中 `mode` 为 PIL `Image.mode` 属性访问串。正文"mode 为参数名/键"的推断被推翻。
- **§3.1 更正 2**：无 `megapixels` 输入；缩放目标固定为模块常量 `DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS=1.0`，用户不可调。正文"`megapixels` 为输入参数"推断被推翻；`缩放目标: 约 1.0MP` 判定为报告固定说明行（因目标不可调，两种解释中的后者成立）。
- 模块常量 `MODE_*`/`OFFICIAL_SCALE_METHOD`/`DEFAULT_MAX_INPUT_IMAGE_MEGAPIXELS`：**全部实锤**（见 (c)），`MODE_*` 与三个中文串的对应关系由推断升级为确认。
- 独立串 `处理方式` 的挂接点：**已确认**——它就是 INPUT_TYPES 参数名（同时是报告行前缀用词）。
- `否` 是否为 `是否缩放: ` 取值、报告行拼接格式（`{:.1f} KB` 等）：introspection 不含方法体，仍为未确认。→ 仍未确认。
