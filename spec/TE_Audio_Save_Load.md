# TE_Audio_Save_Load.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出 `PyInit_TE_Audio_Save_Load`；IMPORT 仅 python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime（无网络、无 GDI 依赖）。静态分析（导出表/ASCII 与 UTF-8 字符串按文件偏移序提取，交叉对照 README 与 web/js）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；未确认处已标注。
> 原始源文件路径证据：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Audio_Save_Load.c`（Cython 生成）与 `custom_nodes/TE_image/source_py_backup/TE_Audio_Save_Load.py` [高]。

## 1. 模块定位

ComfyUI **节点模块**（非内部支撑库，不在 `SKIP_MODULES` 之列）：单一节点 `TEAudioSaveLoad`，把「加载/接收音频 → 按起止时间裁切 → 变速 → 保存到 ComfyUI/output → 继续输出同一份音频」集中在一个节点。对应 README v3.7「新增 TE MAN 加载音频&保存音频 Audio 节点」。

## 2. Python API

- 导出（PE 导出表）：`PyInit_TE_Audio_Save_Load` [高]
- 方法名命名空间：`custom_nodes.TE_image.TE_Audio_Save_Load.*`[高]。模块级函数：
  - `_get_audio_choices` —— 扫描 ComfyUI input 目录生成音频文件下拉列表 [高]
  - `_load_audio` —— 加载音频为 (waveform, sample_rate) [高]
  - `_trim_audio` —— 按 start/end 切片波形 [高]
  - `_change_audio_speed` —— 变速 [高]
  - `_expand_filename_time` —— 展开文件名中的时间占位符 [高]
- 类：`TEAudioSaveLoad`，方法 `INPUT_TYPES` / `load_trim_save_audio` / `VALIDATE_INPUTS` / `IS_CHANGED`（`IS_CHANGED` 内含 `<lambda>`，并有 `__pyx_scope_struct__IS_CHANGED` 闭包结构）[高]
- 节点注册 [高]：`NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` 存在；注册键 `TE_audio_save_load`（模块内唯一出现一次的类注册字符串）[中]；显示名 `TE MAN 加载音频&保存音频 Audio`（字符串原文 `TE MAN 加载音频&保存音频 Audio`）[高]；`CATEGORY` 值 `TE MAN/Utils` [高]。→ 注册键与显示名均已由动态回填证实（`TE_audio_save_load` / `TE MAN 加载音频&保存音频 Audio`）

## 3. 节点规格（TEAudioSaveLoad）

### 类属性标志 [高]
- `FUNCTION = "load_trim_save_audio"`（字符串同名）[高]。→ 已由动态回填证实
- `OUTPUT_NODE = True`（字符串 `OUTPUT_NODE`）[高]。→ **已确认：`OUTPUT_NODE=True`（动态回填，实测布尔值）**
- `RETURN_TYPES` / `RETURN_NAMES` / `DESCRIPTION` / `NODE_CLASS_MAPPINGS` 等键名字符串均存在 [高]；`RETURN_TYPES` 的具体元组值未在字符串表显式出现 → **未确认**，但输出输出端为 `AUDIO` 类型 pipes（`AUDIO` 字符串、局部名 `processed_audio`，且描述称「保存后继续输出同一份音频」）[中]；UI 返回变量名 `saved_ui` [高]。→ **已确认（动态回填）：`RETURN_TYPES=("AUDIO",)`、`RETURN_NAMES=("audio",)`——AUDIO 透传输出实锤**

### 输入（required / optional / hidden 分组，`required`、`optional`、`hidden` 字符串均在）[高]

**required [高]**（各输入均有 `tooltip`、 `display_name` 键字符串）：
> **动态回填重要更正**：真机 `INPUT_TYPES()` 实测的 required 参数名与下表静态推断的 `te_audio_*` 前缀命名**不一致**——实际参数名为 `start_time` / `end_time` / `speed` / `filename_prefix` / `format`，且**无 `quality` 参数**（mp3 品质固定 `128k`）；`te_audio_start_time` 等 `te_audio_` 前缀名应为其内部局部变量/前端属性键名（`te_audio_source_duration` 等确为前端属性键，见 §3 行为链），不是 INPUT_TYPES 参数名。静态还原与实测的详细对照见文末"动态 introspection 回填"节 (a)/(d)。

| 参数 | 类型/默认 | 证据 |
|---|---|---|
| `te_audio_start_time` | FLOAT，默认 0，min 0，标签「开始时间（秒）」 | 字符串 `te_audio_start_time`、`FLOAT`、`step`、tooltip「从原音频的这个时间点开始保留。」、校验「开始时间不能小于 0。」→ 实际参数名 **`start_time`**（动态回填；display_name/tooltip/min/step 证实，max=4294967295） |
| `te_audio_end_time` | FLOAT，默认 0（0=到结尾），标签「结束时间（秒）」 | `te_audio_end_time`、tooltip「保留到原音频的这个时间点。0 表示自动使用原音频结尾，加载后会显示真实时长。」、校验「结束时间不能小于 0；使用 0 表示原音频结尾。」→ 实际参数名 **`end_time`**（动态回填） |
| `te_audio_speed` | FLOAT，默认 1.0，范围 0.1–4.0，标签「变速倍率」 | `te_audio_speed`、tooltip「1.0 为原速；小于 1.0 放慢，大于 1.0 加快。」、校验「变速倍率必须大于 0。」「变速倍率必须在 0.1 到 4.0 之间。」、数值常量 `0.1`/`4.0` → 实际参数名 **`speed`**（动态回填；min=0.1/max=4.0/step=0.1 实测证实） |
| `file_format` | 下拉 `flac` / `mp3`，标签「保存格式」 | `file_format`、`flac`、`mp3`、`opus`（同列表出现，可能可选三种）、校验「不支持的音频格式: 」；默认值 **未确认**（README 称支持保存为 FLAC、MP3）→ 实际参数名 **`format`**，枚举 **`["flac","mp3","opus"]` 三项**、默认 **`"flac"`**（动态回填，[未确认]→实锤） |
| `quality` | STRING/combo，默认 `"128k"`（mp3 码率） | `quality`、`128k`（ComfyUI SaveAudioMP3 惯例）[中] → **动态回填更正：INPUT_TYPES 中无 `quality` 参数**，`128k` 为方法内部固定字面量 |
| `filename_prefix` | STRING，默认 `DEFAULT_FILENAME_PREFIX = "audio/TE_MAN_%Y-%m-%d-%H-%M-%S"`，标签/提示「保存文件名」「文件名前缀」 | 常量字符串 `audio/TE_MAN_%Y-%m-%d-%H-%M-%S` 恰邻 `SAVE 前缀上下文`（`DEFAULT_FILENAME_PREFIX` 于偏移 78160），tooltip「保存到 ComfyUI/output。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S」→ **已确认（动态回填）**，参数名/默认值/tooltip 全部实测吻合 |

**optional [高]**：
| 参数 | 说明 | 证据 |
|---|---|---|
| `upload_audio` | 音频文件下拉（choices 由 `_get_audio_choices` 生成），tooltip「可选。左侧 audio 未连接时，从 ComfyUI input 目录选择或上传音频。」；与 web/js 中 `getNodeUploadAudio` 读取 widget `upload_audio` 互相印证 | `upload_audio`、`audio_upload`（上传按钮键，同 ComfyUI LoadAudio 的 `"audio_upload": True` 惯例）、tooltip 全文。→ **已确认（动态回填）：`upload_audio` 在 optional 组，`audio_upload: True` 实测吻合** |
| `audio`（输入插槽） | AUDIO 类型输入；接上后优先于本地选择覆盖 `upload_audio` 选择，tooltip「接入后优先使用这里的音频，并覆盖本地加载选择。」 | `AUDIO`、`forceInput`、tooltip 全文；「audio」插槽名与 web/js `isAudioInputConnected` 检查 `inputs.find(name==='audio').link` 印证。→ **已确认（动态回填）：`audio` 在 optional 组，且实测选项字典**无** `forceInput` 键**（AUDIO 类型在 ComfyUI 默认即为左侧插槽，无需 forceInput） |
| filename 前缀文本输入 | STRING 接入文本后覆盖上方文件名前缀，参与计算 `effective_prefix` | tooltip「可选。接入文本后覆盖上方文件名前缀。」、局部名 `effective_prefix` **输入名未确认**（仅行为有据）。→ **已确认（动态回填）：输入名为中文 `保存文件名`，`forceInput: True`（与姊妹节点 TE_image_pro_save_image_with_output 的同名输入口同款）** |

**hidden [高（组）/中（成员）]**：`hidden` 分组字符串存在；成员含 `te_audio_input_connected`、`prompt`、`extra_pnginfo`（`hidden` 与 `te_audio_input_connected` 在常量表相邻，`prompt`/`extra_pnginfo`/`PROMPT` 字符串均在）；`te_audio_source_duration` 与 `input_audio_connected` 也极可能为 hidden 注入值 [中] —— web/js 确认前端会写 `te_audio_input_connected`、`te_audio_source_duration`、`te_saved_preview_audio` 等节点属性。用途：让后端知道 audio 插槽是否已连接、以及前端测得的原音频时长（秒），用于校验（见下）。→ **动态回填更正：INPUT_TYPES 返回的 hidden 组恰为 `{"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}` 两项**——`te_audio_input_connected`/`te_audio_source_duration` 不是 hidden 输入，而是前端写入节点 properties、后端经 `extra_pnginfo`（或 prompt 图节点 properties）间接读取的**前端持久化属性键**，原"hidden 注入值"归类需修正。

### 关键行为（按字符串流程推断）
1. **取音频**：`audio` 插槽已连接 → 直接用（`input_audio_connected`/`te_audio_input_connected`）；否则 `_load_audio` 从 input 目录加载 `upload_audio` 选择（`folder_paths.get_input_directory`、`exists_annotated_filepath`/`get_annotated_filepath`、`load audio` 步骤名、`load_audio_file`）；文件不存在 → 「音频文件不存在: 」。[高]
2. **VALIDATE_INPUTS**（执行前）：start ≥ 0；end ≥ 0；speed > 0 且 0.1–4.0；若有 `te_audio_source_duration`（或加载后实测时长），要求「开始时间必须小于结束时间，并且位于原音频 {duration:.3f} 秒范围内」（消息分片「开始时间必须小于结束时间」「并且位于原音频 」「 秒范围内。」+ 数字格式 `%.3f`、`math.isfinite`/`nan` 防御被前端传入 NaN 的时长）[高/中]。
3. **裁切**：`_trim_audio` 用 `math.floor`/`round`/`clamp` 换算采样点，对波形 tensor 按 `shape`/`sample_rate` 切 `chunk`（`trim audio` 步骤名），得到 `actual_start`/`actual_end`/`trimmed_audio` [高/中]。
4. **变速**：`_change_audio_speed`（`device`、`dtype`、`float32`、`unsqueeze`、`torch.linspace`）≈ 重采样式时间伸缩；speed==1.0 时跳过；`processed_audio` [中]。
5. **文件名展开**：`_expand_filename_time` 用正则 `%(?:Y|m|d|H|M|S)(?![A-Za-z])` 匹配占位符，经 `time.localtime` + `strftime` 展开 `%Y%m%d%H%M%S`；最终前缀 = 文本输入(若有，`strip` 后) 覆盖 `filename_prefix` → `effective_prefix` [高/中]。
6. **保存**：借助 ComfyUI 内部 `comfy_extras.nodes_audio.AudioSaveHelper` 与 `comfy_api.latest` 的 `get_save_audio_ui` 生成 UI 输出（`save audio` 步骤名、`save_options`、`metadata_class`、`EXTRA_PNGINFO`）；mp3 用 `128k` 品质、flac 无损输出到 `ComfyUI/output`（`makedirs` + `exist_ok`）[高/中]。
7. **输出**：`OUTPUT_NODE=True`，UI 携带保存后的音频信息（`saved_ui`、`ui`、`audio`）与输出时长（`te_audio_output_duration`）[中]；工作流返回 `AUDIO` 供下游继续使用 [中]。
8. **IS_CHANGED**：用 `hashlib.sha256` 对 effective_prefix/audio_path 相关内容求 `hexdigest`（`IS_CHANGED.lambda`、`digest`、`sha256`、`get_annotated_filepath`、`read`、`rb`），以此作为节点缓存判定（避免按文件 mtime 时的时区/复现问题）[中]。

另：字符串 `load audio` / `trim audio` / `save audio` 为三个处理步骤的内部步骤名/日志名 [高（存在）/低（去向未确认）]。

## 4. 外部依赖与副作用

- **无网络端点、无 API Key**（导入表只有 python3.dll/KERNEL32/VCRUNTIME140/CRT；字符串无 URL）[高]
- Python 依赖（字符串直接证据 [高]）：
  - `torch`（waveform/linspace/float32/device/dtype）
  - `folder_paths`（`get_input_directory`、`get_annotated_filepath`、`exists_annotated_filepath`、`recursive_search`、`filter_files_content_types`、`STRING`）
  - `hashlib`（`sha256`/`hexdigest`）、`math`（`floor`/`isfinite`/`nan`/`min`/`max`）、`time`（`localtime`/`strftime`）、`types`（`SimpleNamespace`）
  - ComfyUI 内部：`comfy_extras.nodes_audio`（`AudioSaveHelper`）、`comfy_api.latest`（`get_save_audio_ui`）→ 复用官方 SaveAudio/SaveAudioMP3 的编码与 UI 机制 [中]（`load_audio_file` 同样来自该体系）
- 文件系统 [高]：读 `ComfyUI input` 目录（音频素材选择/上传缓存）；写 `ComfyUI/output`（默认子路径 `audio/`，前缀含 `TE_MAN_%Y-%m-%d-%H-%M-%S`），`makedirs(..., exist_ok=True)`
- 前端协作 [高]：节点自定义 waveform「audio editor」预览（pyd 串 `audio editor` + README「内置音频波形预览，可拖动开始线和结束线」），web/js 通过节点属性 `te_audio_source_duration`、`te_audio_input_connected`、`te_saved_preview_audio`、`te_audio_preview`、`te_audio_auto_end`、`te_audio_action_bar` 与后端交互；节点同时接入资产素材库（web/js `/te_asset_library/audio/add`、`upload_audio` widget）[中]

## 5. 错误处理与用户可见文案

| 消息（原文） | 触发场景 |
|---|---|
| `请连接 audio 输入，或点击“加载音频”选择一个本地音频文件。` | audio 插槽未连接且未选择本地文件 [高] |
| `不支持的音频格式: `（后接文件名/后缀） | 所选文件扩展名不在 `SUPPORTED_FORMATS`（证据中出现 `flac`、`mp3`、`opus`；wav/ogg/wma 等**未确认**是否在列，README 资产库段落另提 wav/mp3/flac/ogg/opus/m4a/aac/wma）[高/中] |
| `音频文件不存在: ` | `upload_audio` 所选文件在 input 目录不可解析（`exists_annotated_filepath` 失败）[高] |
| `开始时间不能小于 0。` | VALIDATE_INPUTS [高] |
| `结束时间不能小于 0；使用 0 表示原音频结尾。` | VALIDATE_INPUTS [高] |
| `变速倍率必须大于 0。` / `变速倍率必须在 0.1 到 4.0 之间。` | VALIDATE_INPUTS [高] |
| `开始时间必须小于结束时间，并且位于原音频 {时长} 秒范围内。` | start ≥ end 或超出前端上报/实测时长的 0–duration 范围 [高] |
| tooltip（用户提示） | 「保存到 ComfyUI/output。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S」「1.0 为原速；小于 1.0 放慢，大于 1.0 加快。」「可选。左侧 audio 未连接时，从 ComfyUI input 目录选择或上传音频。」「可选。接入文本后覆盖上方文件名前缀。」「接入后优先使用这里的音频，并覆盖本地加载选择。」「从原音频的这个时间点开始保留。」「保留到原音频的这个时间点。0 表示自动使用原音频结尾，加载后会显示真实时长。」[高] |
| 节点 DESCRIPTION | 「加载或接收音频，按开始时间和结束时间裁切，保存后继续输出同一份音频。」[高] |

## 6. 证据附录（关键字符串摘录，按偏移分组）

**注册/结构**（68xxx–686xx，78xxx–787xx）：
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Audio_Save_Load.c
custom_nodes/TE_image/source_py_backup/TE_Audio_Save_Load.py
_get_audio_choices / _load_audio / _trim_audio / _change_audio_speed / _expand_filename_time
custom_nodes.TE_image.TE_Audio_Save_Load.TEAudioSaveLoad.{INPUT_TYPES,load_trim_save_audio,VALIDATE_INPUTS,IS_CHANGED,IS_CHANGED.lambda}
TEAudioSaveLoad / TE_audio_save_load / TE MAN 加载音频&保存音频 Audio / TE MAN/Utils
NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS / FUNCTION / OUTPUT_NODE / RETURN_TYPES / RETURN_NAMES / CATEGORY / DESCRIPTION / tooltip / display_name / required / optional / hidden
DEFAULT_FILENAME_PREFIX / SUPPORTED_FORMATS / audio/TE_MAN_%Y-%m-%d-%H-%M-%S
```

**输入与常量**：
```
audio / AUDIO / forceInput / upload_audio / audio_upload / audio editor
te_audio_start_time / te_audio_end_time / te_audio_speed / filename_prefix / effective_prefix
te_audio_input_connected / input_audio_connected / te_audio_source_duration / te_audio_output_duration
prompt / extra_pnginfo / EXTRA_PNGINFO / PROMPT
FLOAT / STRING / step / default / FORCE(em)（128k）
flac / mp3 / opus / AUDIO / audio
 0.1  /  4.0  /  1.0  /  0
%(?:Y|m|d|H|M|S)(?![A-Za-z])
```

**处理流程名**（72696–78856）：
```
load_audio_file / load audio / trim audio / save audio
chunk / start_time / actual_start / actual_end / end_time
trimmed_audio / processed_audio / saved_ui / save_options / source_duration
sha256 / hashlib / hexdigest / digest / read / rb
torch / linspace / unsqueeze / float32 / dtype / device / shape / sample_rate
math / floor / round / clamp / min / max / isfinite / nan / .3f
localtime / strftime / makedirs / exist_ok
folder_paths / get_input_directory / get_annotated_filepath / exists_annotated_filepath / recursive_search / filter_files_content_types
comfy_extras.nodes_audio / AudioSaveHelper / comfy_api.latest / get_save_audio_ui / metadata_class
```

**中文文案**（按偏移）：
```
72377  秒范围内。              72400 变速倍率必须大于 0。
72864 从原音频的这个时间点开始保留。
76264 变速倍率必须在 0.1 到 4.0 之间。
76368 请连接 audio 输入，或点击“加载音频”选择一个本地音频文件。
76560 保存到 ComfyUI/output。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S
76888 1.0 为原速；小于 1.0 放慢，大于 1.0 加快。
77024 可选。左侧 audio 未连接时，从 ComfyUI input 目录选择或上传音频。
77200 保留到原音频的这个时间点。0 表示自动使用原音频结尾，加载后会显示真实时长。
77480 TE MAN 加载音频&保存音频 Audio
77568 开始时间必须小于结束时间，并且位于原音频 … 秒范围内。
77632 开始时间（秒） / 结束时间（秒） / 变速倍率 / 保存格式 / 保存文件名 / 文件名前缀
77792 开始时间不能小于 0。
77888 接入后优先使用这里的音频，并覆盖本地加载选择。
77968 加载或接收音频，按开始时间和结束时间裁切，保存后继续输出同一份音频。
78184 可选。接入文本后覆盖上方文件名前缀。
78240 结束时间不能小于 0；使用 0 表示原音频结尾。
79392 不支持的音频格式:            79808 音频文件不存在:
```

**导入表**（佐证无网络/无注册表依赖）：
```
IMPORT: python3.dll, KERNEL32.dll, VCRUNTIME140.dll, api-ms-win-crt-runtime-l1-1-0.dll
EXPORT: PyInit_TE_Audio_Save_Load
```

## 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions `Windows-2025Server` + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载本 pyd 后运行时 introspection。以下均为 `INPUT_TYPES()` 实际返回值与模块 `__dict__` 直接读出。**本节包含对正文 §3 的多处重要更正（required 参数名不带 `te_audio_` 前缀、无 `quality` 参数、format 枚举含 opus、hidden 组仅两项）。**

### (a) INPUT_TYPES 实测全表

```python
{
  "required": {
    "start_time": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 4294967295, "step": 0.01,
                             "display_name": "开始时间（秒）",
                             "tooltip": "从原音频的这个时间点开始保留。"}),
    "end_time":   ("FLOAT", {"default": 0.0, "min": 0.0, "max": 4294967295, "step": 0.01,
                             "display_name": "结束时间（秒）",
                             "tooltip": "保留到原音频的这个时间点。0 表示自动使用原音频结尾，加载后会显示真实时长。"}),
    "speed":      ("FLOAT", {"default": 1.0, "min": 0.1, "max": 4.0, "step": 0.1,
                             "display_name": "变速倍率",
                             "tooltip": "1.0 为原速；小于 1.0 放慢，大于 1.0 加快。"}),
    "filename_prefix": ("STRING", {"default": "audio/TE_MAN_%Y-%m-%d-%H-%M-%S",
                             "display_name": "文件名前缀",
                             "tooltip": "保存到 ComfyUI/output。支持时间格式，例如 TE_MAN_%Y-%m-%d-%H-%M-%S。"}),
    "format":     (["flac", "mp3", "opus"], {"default": "flac", "display_name": "保存格式"})},
  "optional": {
    "upload_audio": ([运行时选项列表: ComfyUI input 目录现有音频, 空白项""在前],
                     {"default": "", "audio_upload": True,
                      "tooltip": "可选。左侧 audio 未连接时，从 ComfyUI input 目录选择或上传音频。"}),
    "audio":      ("AUDIO", {"tooltip": "接入后优先使用这里的音频，并覆盖本地加载选择。"}),
    "保存文件名":  ("STRING", {"forceInput": True,
                      "tooltip": "可选。接入文本后覆盖上方文件名前缀。"})},
  "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}
}
```

实测要点：
- **required 五个参数名均无 `te_audio_` 前缀**：`start_time` / `end_time` / `speed` / `filename_prefix` / `format`——正文表格中的 `te_audio_start_time` 等为静态推断命名，被实测推翻（应为内部局部名/前端属性键）。
- `start_time`/`end_time`：FLOAT，min=0.0、**max=4294967295**（2³²−1，实测值）、step=0.01、默认 0.0；display_name 与 tooltip 实测吻合。
- `speed`：FLOAT，min=0.1、max=4.0、step=0.1、默认 1.0——正文"0.1–4.0"范围实锤。
- `format`：COMBO，枚举 **`["flac", "mp3", "opus"]` 三项**（正文"opus 可能可选"定论），**默认 `"flac"`**（正文默认值未确认 → 实锤）。
- **无 `quality` 参数**——`128k` 为方法内部固定字面量，不是输入。
- `filename_prefix`：STRING，默认 `audio/TE_MAN_%Y-%m-%d-%H-%M-%S` 实测吻合。
- `upload_audio`：COMBO（空白项 `""` 在首位），`audio_upload: True`（LoadAudio 式"选择或上传"控件），在 **optional** 组。
- `audio`：AUDIO 插槽在 optional 组，实测选项字典**无** `forceInput` 键（AUDIO 类型默认即插槽形态，正文引用的 `forceInput` 串实为「保存文件名」的标志）。
- `保存文件名`：中文参数名 STRING 输入口，`forceInput: True`——正文"输入名未确认"就此定论。
- hidden 恰两项 `PROMPT` + `EXTRA_PNGINFO`，**无 `unique_id`**、无 `te_audio_input_connected`/`te_audio_source_duration`。

### (b) 节点元数据实测

| 项 | 实测值 |
|---|---|
| 注册键 | `TE_audio_save_load`（正文 [中]→实锤） |
| 显示名 | `TE MAN 加载音频&保存音频 Audio` |
| 类名 | `TEAudioSaveLoad`，模块 `custom_nodes.TE_image.TE_Audio_Save_Load` |
| `FUNCTION` | `load_trim_save_audio` |
| `CATEGORY` | `TE MAN/Utils` |
| `OUTPUT_NODE` | `True`（实测布尔值） |
| `RETURN_TYPES` | `("AUDIO",)` **已确认**（动态回填）——"保存后继续输出同一份音频"的透传输出实锤 |
| `RETURN_NAMES` | `("audio",)` **已确认**（动态回填） |

### (c) 模块常量实锤（运行时 `__dict__` 导出）

| 常量 | 实测值 |
|---|---|
| `DEFAULT_FILENAME_PREFIX` | `"audio/TE_MAN_%Y-%m-%d-%H-%M-%S"` **已确认**（与 filename_prefix 默认值一致） |
| `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` | 如上注册表 |
| 其余 | 模块级无其他业务常量；`SUPPORTED_FORMATS`（`flac`/`mp3`/`opus`）未出现在模块 `__dict__`——应为函数内部或以非导出名存在，格式枚举以 (a) 实测为准 |

### (d) 对正文"未确认"项的核对结论

- `RETURN_TYPES` 元组值：**已确认 `("AUDIO",)`，RETURN_NAMES `("audio",)`**。
- `file_format` 默认值与 opus 可选性：**已确认默认 `"flac"`、枚举 `["flac","mp3","opus"]`**（实际参数名 `format`）。
- filename 前缀文本输入名：**已确认为中文 `保存文件名`（forceInput=True）**。
- `quality` 参数：**已确认不存在**（`128k` 为内部字面量）。
- required 参数命名：**已确认为 `start_time`/`end_time`/`speed`/`filename_prefix`/`format`**——`te_audio_*` 前缀命名被推翻。
- hidden 成员：**已确认恰 `{prompt: PROMPT, extra_pnginfo: EXTRA_PNGINFO}`**；`te_audio_input_connected`/`te_audio_source_duration` 改判为前端 properties 键（经 extra_pnginfo 间接传递），非 hidden 输入。
- `audio` 插槽 `forceInput`：**实测无该标志**（AUDIO 类型默认即插槽，正文证据引用有误）。
- `SUPPORTED_FORMATS` 是否含 wav/ogg/wma 等：仍未确认（introspection 无方法体；保存格式枚举仅三者为 INPUT 层事实，文件扩展名校验范围是另一回事）。
- `IS_CHANGED` 的 sha256 细节、`te_audio_output_duration` 的 ui 去向：仍未确认。
