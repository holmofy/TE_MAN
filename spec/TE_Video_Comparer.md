# TE_Video_Comparer.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3, limited API, `_cython_3_1_2limited_fastcallnofinalize`) 编译，导出 `PyInit_TE_Video_Comparer`，仅导入 `python3.dll`/`KERNEL32.dll`/`VCRUNTIME140.dll`/ucrt。静态分析（字符串池 / 导入导出表 / 前端 JS 交叉验证）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；其余为"未确认"。

## 1. 模块定位

ComfyUI 视频对比节点模块（节点，非支撑库）。提供单个输出型节点 `TE_image_pro_video_comparer`（显示名 **"TE MAN 视频对比"**）：接收两路可选 VIDEO 输入，把视频保存到 ComfyUI temp 目录并回传元数据，由前端 DOM widget 在节点内叠加播放两视频、鼠标移动分界线实时对比（README v3.8.1 changelog §4"新增 TE MAN 视频对比节点"，L98-109）。Python 端只做"保存到 temp + 用 PyAV 读取时长/帧数/帧率"，全部交互在前端 `web/js/te_video_comparer.js`（混淆但可读）。

源文件证据（编译期路径）：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Video_Comparer.c`、`custom_nodes/TE_image/source_py_backup/TE_Video_Comparer.py`、模块限定名 `custom_nodes.TE_image.TE_Video_Comparer`（编译时包目录名为 `TE_image`，现已改名 TE_MAN；`__init__.py` 自动 glob `*.pyd` 加载并合并其 `NODE_CLASS_MAPPINGS`）。

## 2. Python API

- 导出符号：`PyInit_TE_Video_Comparer` [高，导出表]。
- 模块级公开对象：
  - 类 `TEMANVideoComparerNode` [高，限定名字符串 `custom_nodes.TE_image.TE_Video_Comparer.TEMANVideoComparerNode.*`]
  - 类方法/属性符号：`INPUT_TYPES`、`_save_preview`、`_read_preview_metadata`、`compare_videos`、`_read_preview_metadata.<locals>.genexpr` [高]
  - 模块属性：`NODE_CLASS_MAPPINGS`、`NODE_DISPLAY_NAME_MAPPINGS`、`__test__`（Cython doctest 占位）[高，池字符串]
- 类属性声明（属性名字符串均在池中）：`FUNCTION`、`RETURN_TYPES`、`RETURN_NAMES`、`CATEGORY`、`DESCRIPTION`、`OUTPUT_NODE` [高]。
- **ComfyUI 节点注册** [高]：
  - `NODE_CLASS_MAPPINGS: {"TE_image_pro_video_comparer": TEMANVideoComparerNode}` — 键串 `TE_image_pro_video_comparer`（pyd 池字符串），且前端 JS `NODE_TYPE='TE_image_pro_video_comparer'` 交叉一致。
  - `NODE_DISPLAY_NAME_MAPPINGS: {"TE_image_pro_video_comparer": "TE MAN 视频对比"}`（池中文串）。
  - `CATEGORY = "TE MAN/Utils"` [高，池字符串 `TE MAN/Utils`]
  - `DESCRIPTION = "在节点内叠加播放两个视频，鼠标移动分界线进行对比"` [高]
  - `FUNCTION = "compare_videos"` [高，池字符串；限定名 `TEMANVideoComparerNode.compare_videos`]
  - `OUTPUT_NODE = True` [中，属性名 `OUTPUT_NODE` 在池中；值为布尔常量，仅强暗示]。→ **已确认：`OUTPUT_NODE=True`（动态回填，实测布尔值）**
  - `RETURN_TYPES` / `RETURN_NAMES` 的**具体取值未确认**（值是代码常量，不产生字符串；池中有 `result`/`ui`/`a_videos`/`b_videos`/`saved_a`/`saved_b`，无 `a_video`/`b_video` 单数形式，无 `images`/`output`）。最可能形态 [低]：`{"ui": {"a_videos": [...], "b_videos": [...]}, "result": (...)}`，输出可能为空或透传 VIDEO。→ **已确认（动态回填）：`RETURN_TYPES=[]`、`RETURN_NAMES=[]`——均为运行时空列表实锤**，无 VIDEO 透传输出，节点为纯 UI 输出型（与图像对比节点同款模式）。
- 绑定的 backend：**无**（几乎无 Python 侧用户文案；全部 UI 在前端 JS）。

## 3. 节点规格（TE_image_pro_video_comparer）

### 输入（INPUT_TYPES）

池字符串证据：`required`、`optional`、`hidden`、`tooltip`、`VIDEO`、`video_a`、`video_b`、中文 tooltip 两条。

| 名称 | 类型 | 组 | tooltip | 置信度 |
|---|---|---|---|---|
| `video_a` | `VIDEO` | optional [中] | `对比视频 A（可选）` | [高] 名称/类型/tooltip；"optional 组"[中，依 tooltip 文案"（可选）"与池中有 `optional` 键]。→ **optional 组已确认（动态回填）** |
| `video_b` | `VIDEO` | optional [中] | `对比视频 B（可选）` | [高] 同上。→ **optional 组已确认（动态回填）** |

- `hidden` 组最可能含 `prompt: "PROMPT"` 与 `extra_pnginfo: "EXTRA_PNGINFO"` [中]：池同时有参数名 `prompt`、`extra_pnginfo`（与 `compare_videos` 同簇）与类型名 `PROMPT`、`EXTRA_PNGINFO`；无 `unique_id` 字符串。具体用途未确认（猜测用于把工作流信息写入保存的预览 [低]）。→ **成员已确认（动态回填）：hidden 恰为 `{"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}` 两项，无 `unique_id`**。
- `required` 键同时存在 [高，池字符串]，具体放什么未确认（可能为空组，也可能是 video_a/video_b 实际在 required 组——两种排布无法从字符串区分）。→ **已确认（动态回填）：`required` 为空 dict**，video_a/video_b 均在 optional——排布疑问就此定论。
- 无其他输入参数（池中无 default/int/float/combo 等痕迹）。→ **已确认（动态回填）**。

### 输入/输出数据结构（Python 端 → 前端）

`compare_videos` 返回 `{"ui": {"a_videos": [...], "b_videos": [...]}, "result": (...)}` [中，池串 `ui`/`result`/`a_videos`/`b_videos`；`onExecuted` 读 `_0xfa5a4f?.['a_videos']` 与 `['b_videos']` 交叉验证为 [高]]。每个条目（前端 `copyVideoData` 消费的字段）：

```
{"filename": ..., "subfolder": <str 默认""?>, "type": "temp", "frame_count": <int>, "frame_rate": <float>, "duration": <float>}
```

[高] — 后端池串 `filename`/`subfolder`/`type`/`temp`/`frame_count`/`frame_rate`/`duration` 与 JS `copyVideoData` 读的键名逐一对应（JS 中 type 兜底 `'temp'`）。后端还可能附加 `label` 字段 [低，池串 `label` 用途未确认；另有独立 1 字符串 `'a'`、`'b'`，疑似用于内部区分两路（如文件名组成或字段值）[中]]。

### 关键行为（按执行流程推断）

1. **`compare_videos(video_a=?, video_b=?, prompt=?, extra_pnginfo=?)`** [中，参数名都是池串；`self` 也在池簇中]：
   - 对每个提供的输入调用 `_save_preview` → 得 `saved_a` / `saved_b` [高，变量名池串]，保存到 temp 目录：`folder_paths.get_temp_directory()` + `os.makedirs(..., exist_ok=True)` + `os.path.join` + 文件名前缀 `te_man_video_compare_` + `uuid.uuid4().hex` [高，池串 `folder_paths`/`get_temp_directory`/`makedirs`/`exist_ok`/`join`/`temp_dir`/`te_man_video_compare_`/`uuid4`/`hex`/`os`/`path`；`uuid` 模块独立池串]。
   - 保存走 MP4 容器 / H264 编码方向 [中→高]：池串 `save_to`、`format`、`codec`、`VideoContainer.MP4`、`VideoCodec.H264`（`MP4`、`H264` 均为属性访问串）——符合 `comfy_api` 的 `Video.save_to(dst, format=VideoContainer.MP4, codec=VideoCodec.H264)` API；与 `comfy_api.latest` 导入串互证。
   - 随后对保存的文件调用 `_read_preview_metadata` 读取元数据，组装上文条目，返回 ui 字典。
2. **`_save_preview`** [高，限定名]：行为如上（save_to / temp / mp4 / uuid）。是否同时把 `prompt`/`extra_pnginfo` 写入某处 **未确认**。
3. **`_read_preview_metadata`** [高，限定名；含局部 genexpr]：用 **PyAV** 打开已保存的 mp4 读取视频元数据 [高] — 池证据：模块名 `av`、`open`、`container`、`__enter__`/`__exit__`（`with av.open(...)` 形态）、`streams`/`stream`/`video`（选视频流）、`mode`（PyAV 容器属性）、`codec`、`frames`、`average_rate`、`time_base`、`duration`、`frame_count`、`frame_rate`，以及内建 `next`、`sum`（流选择/求和的 genexpr 形态）。另见 `gc`、`isenabled`、`disable`、`enable` [中]——疑为 PyAV 常见的 gc 保护模式（`gc.isenabled()` → `gc.disable()` → 关闭后 `gc.enable()`），具体写法未确认。返回上文 6 字段元数据 [高，前端逐字段消费]。
4. 前端再消费这些字段（详见下"前端联动"）：流地址、同步播放、同步帧等全部计算均在浏览器侧；Python 端无渲染、无输出流。

### 前端联动（web/js/te_video_comparer.js，交叉验证）[高]

- 扩展名 `TEImage.VideoComparer`；`registerExtension` 的 `beforeRegisterNodeDef` 匹配 `nodeData.name === 'TE_image_pro_video_comparer'` 才注入。
- DOM widget：`node.addDOMWidget('te_video_comparer_preview','preview', el, {serialize:false, hideOnZoom:false})`，仅前端状态 `node.__teVideoComparer`。
- 视频 URL：`api.apiURL('/view?' + URLSearchParams({filename, type||'temp', subfolder||''}) + getAppURL())` — 与后端 `type:'temp'` 互证 [高]。
- 播放：双 video层 叠加 + 1px 白色分界线；B 层用 `clipPath inset(0 0 0 {position*100}%)` 裁剪；`pointermove`/`pointerdown` 在视频区移动分界线；点击视频区切换播放/暂停 [高]。A paused/ended 时 B 对齐 A 时间（`alignBToATime`）；启用同步帧后按帧号对齐（`alignBToAFrame`：`idx=round(a.currentTime*a.frame_rate)`，B 的 `currentTime = idx/b.frame_rate`）[高]。
- 控制条按钮：`同步播放/重新播放`（从头同步，`requestAnimationFrame` 循环保持同步、结束自动重播）、`播放速度 Nx`（悬停菜单，速度表 `0.25/0.5/0.75/1/1.2/1.5/2`）、`静音/音频 A/音频 B`（悬停菜单，控制两 video 的 `muted`）、`同步帧`（仅当 `a.frame_count===b.frame_count>0` 可用；seek 双方到同帧，2 秒超时兜底）、`全屏/退出全屏` [高，与 README L103-108 一致]。
- 进度条：`<input type=range 0..1000>` + 时间标签 `m:ss.xx / m:ss.xx`，masterDuration 取 A 视频 duration（兜底 aData.duration）[高]。
- **v3.7.3 修复（README L42"视频对比节点点击控制条不会再误触发画布的拖动和框选"）**：`controls` 对 `pointerdown/mousedown/dblclick`、`progressBar` 对 `pointerdown/mousedown` 注册 `stopPropagation`；每个按钮 click 亦 `preventDefault+stopPropagation`；预览区 `contextmenu` 被阻止 [高，JS 中 stopPropagation 循环直接可见]。
- 滚轮穿透：`forwardWheelToCanvas` 把预览上的 wheel 转发给 `app.canvas._mousewheel_callback`（保留画布缩放）[高]。
- 持久化："对比视频信息会保存到节点工作流"（README L109）— `onSerialize`/`onConfigure`（及 `getExtraMenuOptions` 存在时的对应包装）把 `{a: aData, b: bData}` 写入 `node.properties['te_video_comparer_videos']`（`SERIALIZED_VIDEOS_KEY='te_video_comparer_videos'`，池串 `te_video_comparer_videos`），刷新后 `onConfigure` 恢复 [高]。
- 布局常量：初始节点 460×390，`DEFAULT_ASPECT_RATIO=16/9`，`MIN_VIDEO_HEIGHT=180`，CONTROL 38px，PROGRESS 42px，previewTop=70；宽高比取首个 `loadedmetadata` 的 A 视频（B 仅在未设置时补）[高]。

## 4. 外部依赖与副作用

- **网络**：无后端网络依赖 [高] — 导入表仅 `python3.dll`/`KERNEL32`/`VCRUNTIME140`/ucrt（无 WS2_32/winHTTP）；池中无 http(s) URL。前端仅访问 ComfyUI 内建 `/view?` 接口取 temp 文件 [高]。
- **认证**：无 API Key / 无环境变量 / 无 config 键。
- **文件系统**：写 ComfyUI temp 目录：`folder_paths.get_temp_directory()` 下 `te_man_video_compare_<uuid4hex>.mp4` [高]；无读路径。
- **Python 依赖**：`av`（PyAV，元数据解析）、`os`、`gc`、`uuid`、`folder_paths`（ComfyUI）、`comfy_api.latest`（新 API：`VideoContainer`/`VideoCodec` 枚举；输入 `VIDEO` 对象支持 context manager 与 `save_to`）[高，均池串]。
- **前端**：`web/js/te_video_comparer.js` 由 `WEB_DIRECTORY='./web'` 加载（`__init__.py` L79）。

## 5. 错误处理与用户可见文案

后端几乎无用户可见文案（仅 4 条中文串，均为非错误类）：

| 文案 | 场景 |
|---|---|
| `TE MAN 视频对比` | 节点显示名 [高] |
| `在节点内叠加播放两个视频，鼠标移动分界线进行对比` | 节点 DESCRIPTION [高] |
| `对比视频 A（可选）` | `video_a` 输入 tooltip [高] |
| `对比视频 B（可选）` | `video_b` 输入 tooltip [高] |

错误处理：pyd 池内无 try/except 用户消息痕迹（没有"失败/错误/请"类中文串）；无法定位具体异常路径 — 未确认。前端侧（JS）自建兜底：seek 超时 2s 返回 false、`play().catch(()=>{})` 吞错、视频 `error` 事件处理等 [高]。

## 6. 证据附录

### 导入/导出表

```
IMPORT: python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime-l1-1-0.dll
EXPORT: PyInit_TE_Video_Comparer
```

### 源路径与命名

```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Video_Comparer.c
custom_nodes/TE_image/source_py_backup/TE_Video_Comparer.py
custom_nodes.TE_image.TE_Video_Comparer.TEMANVideoComparerNode.{INPUT_TYPES,_save_preview,compare_videos,_read_preview_metadata,_read_preview_metadata.<locals>.genexpr}
TE_image_pro_video_comparer
```

### 中文串（完整清单）

```
TE MAN 视频对比
在节点内叠加播放两个视频，鼠标移动分界线进行对比
对比视频 A（可选）
对比视频 B（可选）
```

### 字符串池关键簇（按 NUL 分隔的 2+ 字符原始条目，标注偏移）

```
54144 ui          54160 OUTPUT_NODE   54200 prompt      54208 MP4
54224 streams     54232 _read_preview_metadata        54256 result
54264 video_a     54280 VideoCodec    54356 sum         54368 average_rate
54384 uuid4       54392 compare_videos  54544 gc        54568 extra_pnginfo
54584 temp_dir    54600 te_man_video_compare_           54700 av
54744 required    54780 H264          54792 TE_image_pro_video_comparer
55232 duration    55504 isenabled     55520 saved_a     55528 TE MAN/Utils
55544 folder_paths  55600 makedirs    55648 RETURN_TYPES
55664 comfy_api.latest                55684 join        55712 tooltip
55792 VIDEO       55800 subfolder     55816 b_videos    55828 stream
55856 uuid        55864 'b'           55872 disable     55888 saved_b
55908 codec       55944 _save_preview 55960 frames      55968 temp
55976 format      55996 .mp4          56004 os          56008 a_videos
56020 label       56028 path          56040 optional    56056 FUNCTION
另: 51608 save_to / 51628 decode / 51636 close / 51648 time_base / 51672 frame_rate /
    51684 hidden / 51760 EXTRA_PNGINFO / 51776 exist_ok / 51820 open / 51840 VideoContainer /
    51856 hex / 51880 get_temp_directory / 52016 __enter__ / 52112 RETURN_NAMES /
    55896 __exit__ / 51975 'a'（1 字符串池条目）
```

### 前端 JS 关键常量（te_video_comparer.js 反混淆摘录）

```
NODE_TYPE='TE_image_pro_video_comparer'
SERIALIZED_VIDEOS_KEY='te_video_comparer_videos'（唯一池串长 26，用于 properties 键）
SPEEDS=[0.25,0.5,0.75,1,1.2,1.5,2]
videoUrl: api.apiURL('/view?' + params + app.getRandParam?.()||'')
onExecuted: setVideoPair(firstVideo(msg.a_videos), firstVideo(msg.b_videos))
controls:['pointerdown','mousedown','dblclick'] / progressBar:['pointerdown','mousedown'] → stopPropagation（v3.7.3 修复）
```

### 明确未确认项清单

1. `RETURN_TYPES`/`RETURN_NAMES` 具体取值（是否存在 VIDEO 透传输出）。→ **已解决（动态回填）：均为空列表 `[]`，无透传输出**。
2. video_a/video_b 究竟在 required 还是 optional 组（tooltip 文案指向 optional，但两种排布都能成立）。→ **已解决（动态回填）：均在 optional，required 为空 dict**。
3. `hidden` 组确切的键集合（仅确认 `PROMPT`/`EXTRA_PNGINFO` 串存在；`unique_id` 不存在）。→ **已解决（动态回填）：恰为 `{prompt: PROMPT, extra_pnginfo: EXTRA_PNGINFO}`**。
4. `prompt`/`extra_pnginfo` 隐藏参数在后端的具体用途。→ 仍未确认（introspection 不含方法体）。
5. `label` 字符串的确切用途（可能用于保存文件命名或 ui 字段）。→ 仍未确认。
6. gc 保护的精确代码模式（仅 `gc`/`isenabled`/`disable`/`enable` 四串）。→ 仍未确认。
7. pyd 内异常处理的用户可见消息（未发现）。→ 仍未确认。

## 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions `Windows-2025Server` + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载本 pyd 后运行时 introspection。以下均为 `INPUT_TYPES()` 实际返回值与模块 `__dict__` 直接读出。

### (a) INPUT_TYPES 实测全表

```python
{"required": {},                      # 运行时实测：空 dict
 "optional": {
    "video_a": ("VIDEO", {"tooltip": "对比视频 A（可选）"}),
    "video_b": ("VIDEO", {"tooltip": "对比视频 B（可选）"})},
 "hidden": {"prompt": "PROMPT", "extra_pnginfo": "EXTRA_PNGINFO"}}
```

实测要点：
- `video_a` / `video_b`：均在 optional 组，VIDEO 插槽，仅带 tooltip，无 forceInput/无 UI 标志。
- `required` 为空 dict——排布疑问（未确认项 #2）定论。
- hidden 恰两项，无 `unique_id`（未确认项 #3 定论）。
- 无 min/max/step 数值参数、无其他任何输入。

### (b) 节点元数据实测

| 项 | 实测值 |
|---|---|
| 注册键 | `TE_image_pro_video_comparer` |
| 显示名 | `TE MAN 视频对比` |
| 类名 | `TEMANVideoComparerNode`，模块 `custom_nodes.TE_image.TE_Video_Comparer` |
| `FUNCTION` | `compare_videos` |
| `CATEGORY` | `TE MAN/Utils` |
| `OUTPUT_NODE` | `True`（实测布尔值）——**已确认**（正文 [中]→实锤） |
| `RETURN_TYPES` | **`[]`（空列表）**——**已确认**：无 VIDEO 透传，纯 UI 输出节点 |
| `RETURN_NAMES` | **`[]`（空列表）**——**已确认** |

### (c) 模块常量实锤（运行时 `__dict__` 导出）

模块级常量仅有 `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS`（如上注册表），**无其他业务常量**——`te_man_video_compare_` 前缀、`MP4`/`H264` 编码方向等均为方法内部字面量/导入符号，不挂模块 `__dict__`。

### (d) 对正文"未确认"项的核对结论

- 未确认项 #1（RETURN_TYPES/RETURN_NAMES）：**已确认为空列表 `[]`**——"输出可能为空或透传 VIDEO"两说中的"空"成立，节点与图像对比节点同为 OUTPUT_NODE=True + 空 RETURN_TYPES 的纯 UI 输出模式。
- 未确认项 #2（required/optional 排布）：**已确认 video_a/video_b 在 optional**。
- 未确认项 #3（hidden 键集合）：**已确认恰两项、无 unique_id**。
- 未确认项 #4/#5/#6/#7（prompt/extra_pnginfo 用途、label 用途、gc 模式、异常消息）：introspection 不含方法体，仍为未确认。
