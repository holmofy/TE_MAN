# Save_Video_With_Frame_Capture.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，PyInit_Save_Video_With_Frame_Capture。静态分析（字符串/导入导出表 + 前端 JS `web/js/save_video_with_frame_capture.js` 交叉验证）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

ComfyUI **节点模块**（不在 `__init__.py` 的 `SKIP_MODULES` 中），单一节点 `TESaveVideoWithFrameCapture`（显示名 `TE MAN 保存视频video`）：把左侧 `VIDEO` 输入或本地视频保存到 ComfyUI `output` 目录，并配套前端（`web/js/save_video_with_frame_capture.js`）在节点内提供视频预览、暂停/播放与"截取当前帧"（把当前帧存为 PNG 并在画布上生成一张 `TE_image_pro_save_image_with_output` 图片节点）。对应 README v2.1「TE 保存视频节点支持加载本地视频」与 v1.1「支持一键截取视频帧，截出图片」[高]。

## 2. Python API

- 导出（EXPORT 表仅一项）：`PyInit_Save_Video_With_Frame_Capture`
- 源文件路径（Cython 编译注释字符串）：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Save_Video_With_Frame_Capture.c`，即源 `custom_nodes/TE_image/source_py_backup/Save_Video_With_Frame_Capture.py`
- 模块限定名：`custom_nodes.TE_image.Save_Video_With_Frame_Capture`
- 模块级函数（.rdata 属性表按声明序，全部 [高]，签名细节标注明）：

| 对象 | 推断签名 / 作用 | 置信度 |
|---|---|---|
| `_get_input_video_choices()` | 枚举 input 目录本地视频供 `local_video` 下拉框：`folder_paths.get_input_directory` + `listdir` + `folder_paths.filter_files_content_types`（内容类型 `"video"` 字符串在列）+ 视频扩展名白名单（`PyList_Sort` 导入佐证排序） | 名[高]/细节[中] |
| `_load_local_video(...)` | 按选择加载本地视频：`folder_paths.get_annotated_filepath` / `exists_annotated_filepath` 校验（`视频文件不存在: `），`open`+`seek` 后交给 `VideoFromFile` | [高] |
| `_normalize_extension(ext)` | 规范扩展名：`strip`+`lower`+去点前缀（裸名 `avi/mp4/mkv/gif/mov/webm` 与带点 `.avi/.mp4/.mkv/.gif/.mov/.webm/.ts` 同在）；返回类型标注 `str`（限定名后紧跟 `str` 字符串） | [高] |
| `_extract_video_source(video, local_video)` | 取视频源：左侧 `video` 优先，未连接时回退 `local_video`（与 tooltip 文案一致）；都不给则报 `未提供可保存的视频`；不认识的类型报 `不支持的 VIDEO 输入类型: `（局部变量名 `video_input_type` 用于拼错误消息） | [高] |
| `_seek_stream_start(video)` | 调 `video.get_stream_source()` 后 `seek(0)` 把流复位（`get_stream_source`、`seek` 字符串） | [中] |
| `_guess_video_extension(video)` | 用 `video.get_container_format()`（`get_container_format` 字符串，容器名 `matroska`、`mpegts`）查 `_VIDEO_EXT_BY_CONTAINER` 猜输出扩展名 | [高] |
| `_validate_saved_video(target_path)` | 保存后校验：`os.path.isfile` + `os.path.getsize`（>0），失败对应 `视频文件保存失败：未生成输出文件` / `视频文件保存失败：输出文件为空`；`Invalid video file: ` 亦在此链路 | [高] |
| `_save_video_via_video_object(video, ...)` | 通过 VIDEO 对象自身落盘：调 `video.save_to(...)`（`save_to` 字符串，ComfyUI VideoInput 的保存方法）写 `target_path` | [中]（ComfyUI API 常识佐证） |
| `_copy_video_source(source, target_path)` | 纯文件复制兜底：`shutil.copyfile` / `copyfileobj`+`open` | [高] |
| `_save_video_to_output(video_source, filename_prefix, ...)（细节未确认）` | 编排保存：`folder_paths.get_output_directory` / `get_save_image_path` + `%05d`（字符串 `05d`，模仿 SaveImage 的计数命名）生成文件名 → makedirs → 上面两条路径之一落盘 → 校验；局部变量 `output_dir`、`saved_name`、`target_path` | 流程[高]/签名[低] |
| `_find_te_prompt_from_prompt_graph(...)` | 薄封装，转调 `save_image_with_output_core.find_te_prompt_from_prompt_graph`（模块名 + 两套限定名 `_find_...`/`find_...` 同在） | [高] |
| `_build_prompt_ui_text(...)` | 薄封装，转调 `save_image_with_output_core.build_prompt_ui_text`（同上成对限定名） | [高] |

- 类：`TESaveVideoWithFrameCapture`（限定名 `TESaveVideoWithFrameCapture` [高]），方法 `__init__` / `IS_CHANGED` / `INPUT_TYPES` / `save_video_and_output` / `VALIDATE_INPUTS`（五者的完整限定名字符串均在二进制中 [高]）。

## 3. 节点规格

### 3.0 注册与元数据 [高]

- 注册键：`TE_image_pro_save_video`（前端 JS `VIDEO_NODE_CLASS` 字符串表明文同值，双证 [高]）
- 显示名：`TE MAN 保存视频video`（字符串原文 @0xfe80 [高]，与姊妹节点 `TE MAN 加载音频&保存音频 Audio` 命名风格一致）
- `CATEGORY = "TE MAN/Utils"`（字符串 @0x11358 [高]）
- `FUNCTION = "save_video_and_output"`（方法限定名 [高]）
- `OUTPUT_NODE` 属性存在（字符串 @0x10d10），本节点是输出节点 [高]
- `DESCRIPTION = "保存输入视频到 ComfyUI 输出目录，并在节点前端提供暂停预览与截取当前帧功能"`（字符串 @0x11490 [高]）
- `SEARCH_ALIASES` 属性存在（字符串 @0x10df0）；候选值为英文搜索别名 `save video`、`save video with preview`、`export video`、`video output`（四串均在 [中]，是否恰好为该四项未确认）
- `RETURN_TYPES` / `RETURN_NAMES` 属性名字符串均存在（@0x11438 / @0x10178），但值无法从字符串还原；节点 `save_video_and_output` 存在局部变量 `result`（`{"ui": ..., "result": ...}` 风格）。前端 `onExecuted` 只消费 ui 里的 `video` 与 `te_prompt_text`，故最可能为空返回 tuple；是否附带 `VIDEO` 透传输出为**未确认**。

### 3.1 输入参数（INPUT_TYPES，存在 `required` / `hidden` / `optional` 键 [高]）

| 名称 | 类型 | 备注 | 置信度 |
|---|---|---|---|
| `video` | `VIDEO` | 左侧视频输入；tooltip `要保存的视频输入` + `接入后会优先使用这里的视频，并覆盖本地视频选择` | [高] |
| `local_video` | COMBO（`_get_input_video_choices()` 动态选项） | tooltip `左侧 video 未连接时，使用这里选择 input 目录中的本地视频`；前端"加载视频"按钮上传到 `/upload/image`（`type=input`）后把文件名注入该下拉框 | [高] |
| `filename_prefix` | `"STRING"`（默认值推断 `TE_MAN_Video`） | tooltip `保存到 output 目录时使用的文件名前缀`；默认值依据：`TE_MAN_Video` 字符串紧邻 `required` 出现、符合 TE 系前缀惯例（对照 Grok_Video_Generator `grok_video_`） | 名称[高]/默认值[中] |
| hidden：`unique_id`(=`UNIQUE_ID`)、`prompt`(=`PROMPT`)、`extra_pnginfo`(=`EXTRA_PNGINFO`) | — | 供 te_prompt_text 提取与 ui 回传 | [高] |

`optional` 键存在（@0x118f8），但对应可选输入内容**未确认**（可能为空或承载上述输入的可选项属性）。

### 3.2 返回 / ui 契约 [高]（键名有据，结构为推断）

- 局部变量 `ui_video`（@0xff40）→ `return {"ui": {...}, "result": ...}`；ui 键：
  - `video`：`[{filename, subfolder, type: 'output'}]` 列表（局部 `saved_name`；前端 `buildViewUrl` 读 `filename/subfolder/type` 且默认 `type='output'`，[高]）
  - `te_prompt_text`：`_build_prompt_ui_text(_find_te_prompt_from_prompt_graph(prompt, unique_id, extra_pnginfo, ...))` 的结果（三串同在 [高]）；前端把它存进节点 properties `te_saved_prompt_text`，截帧生成的新图片节点会继承该提示词（前端明文逻辑）
- `IS_CHANGED` 存在，返回 `float('nan')` 的可能性高（字符串 `nan` @0x10f28 + `PyFloat_FromString` 导入，永不匹配 → 每次都重新执行；[中]）
- `VALIDATE_INPUTS` 存在（限定名 [高]），校验内容**未确认**（推测校验 `local_video`/`filename_prefix`，[低]）

### 3.3 关键行为链 [高]（按字符串流还原）

1. `_extract_video_source`：`video` 未连接 → 取 `local_video`；两者皆无 → 抛 `ValueError`(未提供可保存的视频 / 请连接左侧 video，或在节点里选择本地视频)。
2. 有 VIDEO 对象 → `_seek_stream_start` 复位流 → `_guess_video_extension`（依 `get_container_format` 查 `_VIDEO_EXT_BY_CONTAINER`，容器 `matroska`/`mpegts`；候选扩展 `.webm/.ts` 等，完整映射**未确认**）→ `_normalize_extension` 规范化 → `_save_video_via_video_object` 调 `video.save_to(target_path)`。
3. 或者直接复制文件：`_copy_video_source` 用 `shutil.copyfile`/`copyfileobj`（本地文件路径直拷，[高]）。
4. `_save_video_to_output`：`folder_paths.get_output_directory` + `get_save_image_path` 计算最终路径与 `%05d` 序号命名，`makedirs(..., exist_ok=True)`（`exist_ok` 字符串），保存后 `_validate_saved_video`（`isfile`+`getsize`）；失败时 `remove` 清理（`remove` 字符串存在，[中]）。
5. 生成 ui：`video` 列表（`saved_name`）+ `te_prompt_text`；前端用 `/view?filename=...&subfolder=...&type=output` 在节点内做视频预览，配合暂停（`暂停预览`/`播放预览`）与截帧按钮（`截取当前帧`，忙碌态 `截取中...`）。

## 4. 外部依赖与副作用

- **无网络依赖**：IMPORT 表仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、`api-ms-win-crt-runtime-l1-1-0.dll`（无 WS2_32）[高]。上传/预览的网络交互全部在前端 JS（`/upload/image`、`/view`）。
- ComfyUI 内置 `folder_paths`：`get_output_directory`、`get_save_image_path`、`get_input_directory`、`get_annotated_filepath`、`exists_annotated_filepath`、`filter_files_content_types` [高]。
- `comfy_api.input_impl` + `VideoFromFile`，并用 `_HAS_COMFY_VIDEO` 标志守卫导入失败（`ImportError` 字符串在列）[高]；Video 对象方法 `get_stream_source`、`get_container_format`、`save_to` [中]。
- 内部支撑库 `save_image_with_output_core`：仅复用提示词链路 `find_te_prompt_from_prompt_graph`、`build_prompt_ui_text`（`te_prompt_text` 最终经 ui 回传）[高]。
- 标准库：`shutil`（copyfile/copyfileobj）、`pathlib`（Path/PathLike）、`typing`（Tuple/Any）、`os` 系（listdir/makedirs/remove/isfile/getsize/exists/exist_ok/join）、`open`/`seek`/`read`（流操作）。
- 文件系统副作用：**写** ComfyUI `output` 目录视频文件（`makedirs`、文件命名 `%05d`）；读 `input` 目录视频；失败时清理临时/残缺文件 `remove` [中]。
- 类型兼容依赖：`comfy.comfy_types`（VIDEO 类型定义处，@0x11568）[中]。

## 5. 错误处理与用户可见文案

| 消息 | 触发场景（推断） | 置信度 |
|---|---|---|
| `未提供可保存的视频` | video 与 local_video 均为空（_extract_video_source） | [高] |
| `请连接左侧 video，或在节点里选择本地视频` | 同上，附带的操作提示 | [高] |
| `视频文件不存在: ` | `_load_local_video` 找不到所选本地视频 | [高] |
| `不支持的 VIDEO 输入类型: ` | `_extract_video_source` 收到无法识别的 VIDEO 对象类型（用 `video_input_type` 拼接） | [高] |
| `Invalid video file: ` | `_load_local_video`/`_validate_saved_video` 中 VideoFromFile 构建或校验失败 | [高] |
| `视频文件保存失败：未生成输出文件` | `_validate_saved_video`：target_path 不是文件 | [高] |
| `视频文件保存失败：输出文件为空` | `_validate_saved_video`：`getsize <= 0` | [高] |

异常类型引用：`ValueError`、`RuntimeError`、`ImportError`（其余 RuntimeErrorWarning 等为 Cython 样板）[高]。

前端侧用户可见文案（明文，佐证行为闭环）：`暂停预览`/`播放预览`、`截取当前帧`/`截取中...`、`加载视频`、`上传中`、以及截帧失败提示 `当前节点还没有可截帧的视频。`、`视频还没加载完成，暂时不能截帧。`、`创建截图画布失败。`、`当前帧转图片失败。`、`上传截帧图片失败。`、`当前画布还没准备好，无法创建截图节点。`。

## 6. 证据附录

**模块/限定名与源路径**（ASCII）：
- `F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\Save_Video_With_Frame_Capture.c`
- `custom_nodes/TE_image/source_py_backup/Save_Video_With_Frame_Capture.py`
- `custom_nodes.TE_image.Save_Video_With_Frame_Capture`（每个函数/方法的 `__qualname__` 前缀）

**声明序（.rdata 属性表，0xe9e0–0x118c0）**：
```
_get_input_video_choices → _load_local_video → _normalize_extension → _extract_video_source
→ _seek_stream_start → _guess_video_extension → _validate_saved_video
→ _save_video_via_video_object → _copy_video_source → _save_video_to_output
→ TESaveVideoWithFrameCapture(.__init__ / .IS_CHANGED / .INPUT_TYPES
   / .save_video_and_output / .VALIDATE_INPUTS)
→ _find_te_prompt_from_prompt_graph → _build_prompt_ui_text（后置于 INPUT_TYPES 区，Cython 生成顺序）
```

**节点注册与搜索（UTF-8/ASCII 混合，按偏移）**：
```
TE MAN 保存视频video(0xfe80)   save video(0x11698)   save video with preview(0x10ee8)
export video(0x10100)   video output(0x10fd8)   SEARCH_ALIASES(0x10df0)
TE_image_pro_save_video(0x11090)   TE MAN/Utils(0x11358)   DESCRIPTION(0xff30)
OUTPUT_NODE(0x10d10)   FUNCTION(0x11908)   NODE_CLASS_MAPPINGS(0x11410)
NODE_DISPLAY_NAME_MAPPINGS(0x11308)   RETURN_TYPES(0x11438)   RETURN_NAMES(0x10178)
required(0x11040)   optional(0x118f8)   hidden(0xff54)   tooltip(0x11560)   default(0xff78)
```

**输入/UI 键名**：
```
video(0xff4c)   VIDEO(0x10e24)   local_video(0x11598)   filename_prefix(0x10d28)
STRING(0x11424)   TE_MAN_Video(0x11050)   05d(0x1147c)
unique_id(0x117e0)/UNIQUE_ID   prompt(0x10d48)/PROMPT(0x1172c)   extra_pnginfo/EXTRA_PNGINFO
ui_video(0xff40)   saved_name(0x111a0)   result(0x10de4)   te_prompt_text(0x11810)
video_input_type(0x11828)   nan(0x10f28)（IS_CHANGED → float('nan') 推断）   save_to(0xff28)
```
> 注：`save_to` 为 ComfyUI `VideoInput` 对象的落盘方法名（`_save_video_via_video_object` 链路）；`path` 字符串另在列（@0x118b8，供 ui 条目或路径用途）。

**视频扩展名与容器**：
```
.avi(0x11038) .gif(0x10ce8) .mkv(0x10ce0) .mov(0x11290) .mp4(0x11858) .ts(0x11198) .webm(0x11164)
裸名 avi(0xff04) mp4(0x10110) mkv(0x10118) gif(0x11068) webm(0x11368) mov(0x11854)
容器： matroska(0x10e98)   mpegts(0x10f2c)   映射表名 _VIDEO_EXT_BY_CONTAINER(0x11020)
（完整映射对未确认；前端上传 accept：video/webm,video/mp4,video/x-matroska,image/gif,video/quicktime,video/x-msvideo）
```

**folder_paths / 文件操作 / 核心 API**：
```
folder_paths   get_output_directory   get_save_image_path   get_input_directory
get_annotated_filepath   exists_annotated_filepath   filter_files_content_types
shutil copyfile copyfileobj   makedirs exist_ok   listdir isfile getsize exists remove
join strip lower pop open seek read   pathlib Path PathLike   typing Tuple Any str
comfy_api.input_impl VideoFromFile get_stream_source get_container_format
_has_comfyVideo→ _HAS_COMFY_VIDEO   comfy.comfy_types
save_image_with_output_core   find_te_prompt_from_prompt_graph   build_prompt_ui_text
```

**前端协同（web/js/save_video_with_frame_capture.js，混淆但字符串表 + 逻辑可读）**：
- `VIDEO_NODE_CLASS='TE_image_pro_save_video'`、`IMAGE_NODE_CLASS='TE_image_pro_save_image_with_output'`
- `SERIALIZED_VIDEO_KEY='te_saved_preview_videos'`、`SERIALIZED_PROMPT_KEY='te_saved_prompt_text'`（与 save_image_with_output_core 规格中的序列化键同套式）
- 节点内 DOM 预览 `te_videopreview` + 动作条按钮：加载视频（上传 `/upload/image` → 注入 `local_video` 下拉）、暂停预览/播放预览、截取当前帧（canvas 抓帧 → `<源视频名>_frame_<毫秒>ms.png` 上传 → 以 `TE_image_pro_save_image_with_output` 新建图片节点，复制本节点 `filename_prefix`，还原预览图并继承 `te_saved_prompt_text`）
- `onExecuted` 读取 `video`（兜底 `images`/`videos`）与 `te_prompt_text`；与后端 ui 契约吻合

**未确认项汇总**：`RETURN_TYPES`/`RETURN_NAMES` 具体值（是否含 VIDEO 透传输出）、`optional` 分组内容、`filename_prefix` 默认值是否为 `TE_MAN_Video`、`_VIDEO_EXT_BY_CONTAINER` 的完整容器→扩展名映射、`VALIDATE_INPUTS` 校验范围、`SEARCH_ALIASES` 是否恰为 `save video / save video with preview / export video / video output` 四项、`IS_CHANGED` 返回 `float('nan')` 的确定性、`_save_video_to_output` 的确切参数表。
