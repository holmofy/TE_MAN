# image_codec.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，PyInit_image_codec。主模块路径字符串 `custom_nodes/TE_image/source_py_backup/image_codec.py`（构建机路径 `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\`）。静态分析（字符串/导入导出表）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

TE_MAN（原始包名 TE_image）插件的**内部图像编解码支撑库**，非 ComfyUI 节点：不在 `NODE_CLASS_MAPPINGS` 中注册（本 pyd 全部字符串中无 `INPUT_TYPES` / `CATEGORY` / `RETURN_TYPES` 等节点注册字符串），且在 `__init__.py:26` 的 `SKIP_MODULES` 集合中显式排除。文档串自述：**"负责 Tensor/Base64 转换"**、**"缓存与实时预览构建"**、**"统一的错误画布与字体管理"**。被 11 个节点 pyd 消费（见第 4 节）。

## 2. Python API

- 导出：`PyInit_image_codec`（唯一导出符号）
- 模块合法名：`custom_nodes.TE_image.image_codec` [高]
- 无 ComfyUI 节点注册（支撑库）

### 2.1 模块级公开函数 [高，函数名直接取自字符串]

| 函数 | 参数名（来自 Cython 参数表字符串） | 返回类型注解 | 功能推断 |
|---|---|---|---|
| `_log_codec_message` | `level`, `message`；同域另有 `logger_instance` [中] | 未确认 | 统一的编解码日志输出 |
| `encode_pil_image_to_api_bytes` | 未确认（消费方 TE_Image_Compress / TE_MAN_Chat 直接引用）| `Tuple[bytes, str, str]` [中，该注解紧邻 `_data_url_from_parts` 域] | PIL 图 → (字节, MIME, 扩展名) 三元组 |
| `encode_numpy_image_to_api_parts` | `np_image` [中] | `List[Tuple[str, Tuple[str, bytes, str]]]` 系注解之一 [中] | numpy 图 → API multipart parts |
| `encode_numpy_image_to_api_data_url` | `np_image` [中] | `str`（data URL）[中] | numpy 图 → `data:` + `;base64,` URL |
| `encode_numpy_image_to_api_file_part` | `field_name`, `filename`, `filename_prefix` [中] | `Tuple[str, str, str, bytes]` [中，注解直接相邻] | numpy 图 → (field_name, filename, mime_type, bytes) 文件部件 |

### 2.2 类 `ImageCodec` [高]

`__init__(cache_size)` — `cache_size` 为参数名 [高]；实例属性：`_image_cache`（`OrderedDict` + `move_to_end`/`popitem` = LRU 淘汰）、`_cache_lock`（`threading` 锁）、`_cache_size`、`_maybe_interrupt`（`Optional[Callable[[], None]]` 类型的回调属性）[中]。

方法（均为 [高]，名称取自 `custom_nodes.TE_image.image_codec.ImageCodec.*` 限定名）：

| 方法 | 已知参数名 | 返回注解（相邻域字符串） | 功能 |
|---|---|---|---|
| `_maybe_interrupt` | — | — | 检查 ComfyUI 中断挂起状态（联动 `comfy.model_management` 的 `InterruptProcessingException` / `ensure_not_interrupted` / `pending`）|
| `_tensor_cache_key` | — | — | tensor → 缓存键（`hashlib` + `hexdigest`）|
| `_get_cached_image_b64` / `_set_cached_image_b64` | `cache_key`, `value` | — | LRU 读写缓存 |
| `extract_numpy_images` | — | `List[np.ndarray]` [高] | tensor 批次 → numpy 数组列表（`detach`/`unsqueeze`/`expand_dims`/`stack`/`clamp`/`nanmax`/`float32`→`uint8`/`ascontiguousarray`）|
| `_pil_to_api_image_bytes` | — | `Tuple[bytes, str, str]` [中] | PIL 图按 MIME 编码为字节 |
| `_np_image_to_api_image` | — | `Optional[Tuple[str, Image.Image, int]]` [高] | numpy → (MIME/格式, PIL 图, quality) [中] |
| `_data_url_from_parts` | `base64_value`, `mime_type` | — | 拼接 `data:{mime};base64,{b64}`（字面串 `data:`、`;base64,`）|
| `_split_data_url` | — | `Tuple[str, str]` [高，注解相邻] | data URL → (mime_type, base64_value) |
| `_extension_from_mime` | `mime_type`, `_extension` | — | MIME → 扩展名（表内字符串：`image/png`、`image/jpeg`、`image/webp`、`image/gif`；`splitext`）|
| `tensor_to_base64` / `tensor_to_data_url` | `tensor` | — | torch tensor → base64 / data URL（`b64encode`，走 `_pil_to_api_image_bytes`）|
| `prepare_input_images` | `tensors`, `filename_prefix` | — | 批量准备输入图（含压缩逻辑，见 3.1）|
| `prepare_input_image_data_urls` | — | — | 批量 → data URL 列表（`data_urls`）|
| `prepare_input_image_file_parts` | `field_name`, `filename_prefix` | `List[Tuple[str, Tuple[str, bytes, str]]]` [高，注解直接相邻] | 批量 → API 文件部件 |
| `base64_to_tensor_single` | `b64_str` | — | 单张 base64 → tensor（`b64decode`/`fromarray`/`from_numpy`）|
| `base64_to_tensor_parallel` | `base64_strings`, `max_workers`, `log_prefix` | `List[torch.Tensor]` [高] | 并行批量解码：`ThreadPoolExecutor` + `submit`/`as_completed`/`future_to_index`/`cancel_futures`/`shutdown`；`effective_workers` = min(`max_workers`, `cpu_count`, `worker_cap`) [中]；计时日志 `decode_start`/`decode_time` |
| `build_preview_tuple` | `batch_index`, `max_size` | — | 生成 ComfyUI 实时预览（`preview_image`/`preview_tensor`/`preview_array`；失败走 `ErrorCanvas`）|

### 2.3 类 `ErrorCanvas` [高]

错误画布与字体管理器。`__init__(max_size)` — `max_size` 为参数名 [高]；属性 `_font_cache`、`_image_cache` 推断同 LRU 模式 [中]。

| 方法 | 已知参数名 | 功能 |
|---|---|---|
| `_get_error_font_paths` | — | 候选字体路径：`msyh.ttc`、`msyh.ttf`、`msjh.ttc`、`simhei.ttf`、`msmincho.ttc`（微软雅黑/微软正黑/黑体/明朝），取自 `%WINDIR%\Fonts`（字面串 `Fonts`、`WINDIR`、`windir`、`environ`、`abspath`、`exists`）及模块目录 `MODULE_DIR` [中] |
| `_load_error_font` | — | `ImageFont.truetype` 逐候选加载，失败回退 `ImageFont.load_default`；带缓存 [中] |
| `_wrap_text_segments` | `max_width`；另有 `segments`/`stripped`/`wrapped` | 按像素宽度折行（`textlength`/`getbbox`）[中] |
| `build_error_image_tensor` | `title`, `lines` | 用 PIL 绘制错误信息画布 → tensor（`ImageDraw.ImageDraw`、`rectangle`、`alpha_composite`；配色 `background`/`title_color`/`text_color`/`accent`；排版 `font_title`/`font_body`/`line_height`/`margin`/`max_text_width`/`max_y`）|
| `build_error_tensor_from_text` | — | 由文本直接构建错误 tensor（供各节点pyd 在 API 出错时生成可视化错误图）|

### 2.4 模块级压缩配置常量 [高，名称直接出现]

- `_ENABLE_INPUT_IMAGE_COMPRESSION`（开关，"enable"/"disable"/"isenabled"）
- `_INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES`（阈值；日志文本写明 **1MB**）
- `_INPUT_IMAGE_JPEG_QUALITY`（JPEG 质量；具体数值未确认）

## 3. 节点规格

本模块不是节点模块，无 `NODE_CLASS_MAPPINGS`。为内部接口，见第 2 节。

**注意**：该库被 11 个节点 pyd 当作公共编码工具消费 [高，各 pyd 内出现 `custom_nodes.TE_image.image_codec` 限定名]：

- `GPT_Image_2_Generator`：`ImageCodec` + `prepare_input_images` / `prepare_input_image_data_urls` / `prepare_input_image_file_parts` / `base64_to_tensor_parallel` / `build_preview_tuple` / `ErrorCanvas`（最重度使用者）
- `Gemini_Imagen_Generator`：`prepare_input_image_data_urls` / `base64_to_tensor_parallel` / `build_preview_tuple` / `ErrorCanvas`
- `Grok_Image_Generator`：`base64_to_tensor_single` / `encode_numpy_image_to_api_file_part`
- `Grok_Video_Generator`：`encode_numpy_image_to_api_data_url` / `encode_numpy_image_to_api_file_part`
- `TE_Image_Compress`（及 `_Test`）：`encode_pil_image_to_api_bytes`
- `TE_MAN_Chat`：`encode_pil_image_to_api_bytes`
- 另有 `Jimeng_Video_Generator` / `Sora_2_Video_Generator` / `TE_HappyH_Video` / `TE_VEO_Video` 引用（具体函数名未逐一确认）

## 4. 外部依赖与副作用

### 导入表 [高]
- DLL 导入仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll` —— 无网络库，本模块自身不做网络请求（API 调用均在 api_client 等消费方）。
- Python 侧依赖（字符串证据）：`torch`（`torch.Tensor`、`detach`、`unsqueeze`、`from_numpy`、`stack`）、`numpy`（`np.ndarray`、`asarray`、`astype`、`tobytes`、`nanmax`）、`PIL`（`Image.Image`、`ImageFont.ImageFont`、`ImageDraw.ImageDraw`、`alpha_composite`、`fromarray`、`BytesIO`、`optimize`、`progressive`、`quality`）、`threading`、`collections.OrderedDict`、`concurrent.futures`（`ThreadPoolExecutor`）、`hashlib`、`typing`、`base64`、`inspect`（`cline_in_traceback` 同域）。
- `comfy.model_management` [高，限定名直接出现]：`InterruptProcessingException`、`ensure_not_interrupted` —— 与 ComfyUI 的执行中断机制联动（队列被取消时抛出/检查 `pending` 中断状态）。

### 文件系统
- 无常规文件读写 [中]；只读访问 `%WINDIR%\Fonts` 下字体文件（`exists` 探测 [中]）。
- 配置键：无 `config.ini` 相关字符串；压缩三项常量的来源（内置字面量 vs 环境变量）未确认。

### 网络
- 无端点/URL 字符串（除 data URL scheme）。认证逻辑不在本模块。

## 5. 错误处理与用户可见文案

| 消息 | 触发场景 [中] |
|---|---|
| `"必须提供 tensor 或 numpy 图像数据用于编码"` | 编码入口收到空/非法输入 |
| `"无法从 tensor 中提取有效图像数据"` | `extract_numpy_images` 拿不到有效数据 |
| `"输入图像超过1MB，已单次JPEG压缩: "`（后接 `KB -> ` 尺寸对比） | 输入超大 PNG，触发一次性 JPEG 压缩 |
| `"输入图像超过1MB，但JPEG压缩收益不足，保留PNG: "` | 压缩后无体积收益，放弃压缩 |
| `"输入图像单次压缩失败，保留PNG: "` | 压缩过程抛异常的兜底 |
| `"图片解码失败: "` | base64 → tensor 解码异常 |
| `"实时预览生成失败: 批次 "` | `build_preview_tuple` 失败（后接 `batch_index`）|
| `" 张图片完成，耗时: "` | `base64_to_tensor_parallel` 完成统计（前接张数，接 `decode_time`）|

错误画布（ErrorCanvas）在 API 请求失败时生成带标题/正文的图像 tensor，使节点可不中断而输出可视化错误图 [中，由消费方 GPT/Gemini 均引用 `build_error_tensor_from_text` + `ErrorCanvas` 佐证]。

## 6. 证据附录

### 模块身份
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\image_codec.c
custom_nodes/TE_image/source_py_backup/image_codec.py
custom_nodes.TE_image.image_codec
PyInit_image_codec
Interpreter change detected - this module can only be loaded into one interpreter per process.
Module 'image_codec' has already been imported. Re-initialisation is not supported.
```

### 模块级函数名（Cython 限定名对）
```
_log_codec_message / encode_pil_image_to_api_bytes / encode_numpy_image_to_api_parts
encode_numpy_image_to_api_data_url / encode_numpy_image_to_api_file_part
```

### ImageCodec 方法（部分限定名摘录）
```
custom_nodes.TE_image.image_codec.ImageCodec.__init__
custom_nodes.TE_image.image_codec.ImageCodec._maybe_interrupt
custom_nodes.TE_image.image_codec.ImageCodec._tensor_cache_key
custom_nodes.TE_image.image_codec.ImageCodec._get_cached_image_b64
custom_nodes.TE_image.image_codec.ImageCodec._set_cached_image_b64
custom_nodes.TE_image.image_codec.ImageCodec.extract_numpy_images
custom_nodes.TE_image.image_codec.ImageCodec._pil_to_api_image_bytes
custom_nodes.TE_image.image_codec.ImageCodec._np_image_to_api_image
custom_nodes.TE_image.image_codec.ImageCodec._data_url_from_parts
custom_nodes.TE_image.image_codec.ImageCodec._split_data_url
custom_nodes.TE_image.image_codec.ImageCodec._extension_from_mime
custom_nodes.TE_image.image_codec.ImageCodec.tensor_to_base64
custom_nodes.TE_image.image_codec.ImageCodec.tensor_to_data_url
custom_nodes.TE_image.image_codec.ImageCodec.prepare_input_images
custom_nodes.TE_image.image_codec.ImageCodec.prepare_input_image_data_urls
custom_nodes.TE_image.image_codec.ImageCodec.prepare_input_image_file_parts
custom_nodes.TE_image.image_codec.ImageCodec.base64_to_tensor_single
custom_nodes.TE_image.image_codec.ImageCodec.base64_to_tensor_parallel
custom_nodes.TE_image.image_codec.ImageCodec.build_preview_tuple
```

### ErrorCanvas 方法
```
ErrorCanvas.__init__ / _get_error_font_paths / _load_error_font
_wrap_text_segments / build_error_image_tensor / build_error_tensor_from_text
统一的错误画布与字体管理
负责 Tensor/Base64 转换
缓存与实时预览构建
```

### 类型注解（相邻域）
```
List[np.ndarray] / List[torch.Tensor] / List[Tuple[str, Tuple[str, bytes, str]]]
Tuple[str, str, str, bytes] / Tuple[bytes, str, str] / Tuple[str, str] / Tuple[int, int]
Optional[torch.Tensor] / Optional[np.ndarray] / Optional[int] / Optional[str]
Optional[Callable[[], None]] / Optional[Tuple[str, Image.Image, int]]
```

### 缓存与并行
```
_image_cache  _cache_lock  _cache_size  _font_cache
OrderedDict  move_to_end  popitem  threading
ThreadPoolExecutor  submit  as_completed  future_to_index  cancel_futures  shutdown
effective_workers  worker_cap  max_workers  cpu_count
decode_start  decode_time
```

### 压缩与 MIME
```
_ENABLE_INPUT_IMAGE_COMPRESSION
_INPUT_IMAGE_COMPRESS_THRESHOLD_BYTES
_INPUT_IMAGE_JPEG_QUALITY
image/png  image/jpeg  image/webp  image/gif
data:  ;base64,  PNG:  KB ->
optimize  progressive  quality
```

### 字体候选（ErrorCanvas._get_error_font_paths）
```
msyh.ttc  msyh.ttf  msjh.ttc  simhei.ttf  msmincho.ttc
Fonts  WINDIR  windir  environ  MODULE_DIR  abspath  exists
load_default  truetype
```

### ComfyUI 联动
```
comfy.model_management  model_management
InterruptProcessingException  ensure_not_interrupted  pending
logger_instance  logger
```

### 消费方引用证据（`strings` 扫描各 pyd）
```
GPT_Image_2_Generator.pyd:   ErrorCanvas ImageCodec base64_to_tensor_parallel
                             build_error_tensor_from_text build_preview_tuple
                             extract_numpy_images prepare_input_image_data_urls
                             prepare_input_image_file_parts prepare_input_images
Gemini_Imagen_Generator.pyd: ErrorCanvas ImageCodec base64_to_tensor_parallel
                             build_error_tensor_from_text build_preview_tuple
                             prepare_input_image_data_urls
Grok_Image_Generator.pyd:    ImageCodec base64_to_tensor_single
                             encode_numpy_image_to_api_file_part
Grok_Video_Generator.pyd:    encode_numpy_image_to_api_data_url
                             encode_numpy_image_to_api_file_part
TE_Image_Compress.pyd(+Test):encode_pil_image_to_api_bytes
TE_MAN_Chat.pyd:             encode_pil_image_to_api_bytes
兴 Jimeng_Video_Generator.pyd / Sora_2_Video_Generator.pyd / TE_HappyH_Video.pyd
   / TE_VEO_Video.pyd 中各出现 1 处 image_codec 相关命名引用
```

### 未确认事项
- 具体默认值（`cache_size`、`max_workers`、`_INPUT_IMAGE_JPEG_QUALITY` 数值、画布 `max_size` 尺寸）为编译期常量，未在字符串中出现：**未确认**。
- `_log_codec_message` 完整签名：**未确认**。
- `Tuple[int, int]`（`decode_start`/`decode_time` 域附近）的归属：**未确认**。
