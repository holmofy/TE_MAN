# TE_3D_Director.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出 `PyInit_TE_3D_Director`，仅导入 python3.dll / KERNEL32 / VCRUNTIME140 / CRT（静态分析：导入导出表 + 全量字符串表提取 + 前端 `web/js/te_3d_director.js` 明文常量互证）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

ComfyUI 节点模块：**TE MAN 3D导演台**（README v3.3 / v3.5 功能）。pyd 本体很薄——它只负责两件事：
1. 注册一个轻量 ComfyUI 节点 `TEMan3DDirectorNode`（"打开导演台"按钮 + 场景 JSON / 构图提示词的工作流出口）；
2. 向 ComfyUI `PromptServer`（aiohttp）注册截图落盘路由 `POST /te_3d_director/capture`，把前端 3D 面板导出的 PNG 截图写入 ComfyUI input 目录或资产素材库。

全部 3D 编辑逻辑（Three.js 人偶/机位/姿势/全景/骨骼）都在前端 `web/js/te_3d_director.js`（混淆 JS，非本 pyd）。模块指纹：源文件路径 `custom_nodes/TE_image/source_py_backup/TE_3D_Director.py`，原始包名 `custom_nodes.TE_image.TE_3D_Director` [高]。

## 2. Python API

### 2.1 导出
- `PyInit_TE_3D_Director`（唯一 DllExport）[高]

### 2.2 模块级对象（由 Cython qualname 字符串表逐一还原 [高]）

| 名称 | 性质 | 说明 |
|---|---|---|
| `_json_error` | 函数 | 构造错误 JSON 响应（见 §5）[中] |
| `_input_dir` | 函数 | 计算截图保存根目录，调用 `folder_paths.get_input_directory()` [高] |
| `_is_inside` | 函数 | 路径越界校验，用 `pathlib` `resolve/relative_to/commonpath/parents/exists`，防 `..` 逃逸（字符串 `..`、`resolve`、`relative_to`、`commonpath` 均在表中）[高] |
| `_clean_segment` | 函数 | 路径段清洗，空白折叠 `\s+`、逗号 `,` [高] |
| `_clean_filename_stem` | 函数 | 文件名清洗：`re` 正则 `[<>:"|?*\x00-\x1f]+` 替换 [高] |
| `_dedupe_path` | 函数 | 目标文件已存在时去重改名 [高] |
| `_decode_png_data_url` | 函数 | 解析 `data:image/png` URL → PNG 字节（`base64.b64decode`、`data:image/`、`image/png`、`.png`）[高] |
| `_image_info` | 函数 | `stat` 取 `st_size`/`st_mtime` → `size`/`mtime` 信息 [高] |
| `_asset_record` | 函数 | 构造资产库记录（字段含 `kind`、`name`、`mtime`、`size`、`project`、`category`、`asset` 等）[中] |
| `_target_dir_for_payload` | 函数 | 按 `save_mode` 决定落盘目录（见 §3.2）[高] |
| `te_3d_director_capture` | **async 函数** | 路由处理协程（存在 `__pyx_scope_struct__te_3d_director_capture`、`CoroutineType` 等 Cython 协程机制）[高] |
| `_register_routes` | 函数 | 实际注册路由到 `PromptServer.instance.routes`（`post`、`json_response` 来自 aiohttp）[高] |
| `_register_routes_when_ready` / 内嵌 `_wait_for_server` | 函数 | 服务器未就绪时用 daemon `threading.Thread` 后台注册，循环 `sleep` 等待 [高] |
| `TEMan3DDirectorNode` | 类 | ComfyUI 节点（`INPUT_TYPES`、`export_scene`）[高] |

模块级常量（字符串名 + 前端明文互证）：
- `DEFAULT_PROJECT = '默认项目'`、`DEFAULT_CATEGORY = '3D导演台'`、`DEFAULT_EXAMPLE_PROMPT = '让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面'`（前端 JS 常量 `DEFAULT_PROJECT/DEFAULT_CATEGORY/DEFAULT_EXAMPLE_PROMPT` 明文同值，pyd 中三个常量名与值字符串共现）[高]
- `CAPTURE_FOLDER = 'TE_MAN_3D_Director'` [已确认：常量名与值动态实锤（动态回填）；前端全景上传子目录 `TE_MAN_3D_Director/Panoramas` 与之同根]
- `ASSET_ROOT_NAME = 'TE_MAN'` [已确认：动态实锤（动态回填）；为资产素材库根名]
- 运行期开关：`_ROUTES_REGISTERED`、`_ROUTE_REGISTER_THREAD_STARTED`（一次性注册标志）[高]

### 2.3 ComfyUI 节点注册
- `NODE_CLASS_MAPPINGS` 键：`TE_3D_Director` [高]（pyd 字符串；前端 `NODE_CLASS='TE_3D_Director'` 明文互证）
- `NODE_DISPLAY_NAME_MAPPINGS`：`'TE MAN 3D导演台'` [高]
- `CATEGORY`：`'TE MAN/3D'` [高]
- `FUNCTION`：`'export_scene'` [高]；`OUTPUT_NODE` 为Truthy [高]（字符串在 0x144d0 与其他节点属性区共现）
- `DESCRIPTION`：`打开 TE MAN 3D导演台，编辑角色、道具、机位和姿势，并输出场景 JSON 与构图提示词。` [高]

## 3. 节点规格

### 3.1 TEMan3DDirectorNode
ComfyUI 侧本质是"面板入口 + 数据出口"。前端在节点上注入两类东西 [高，来自 te_3d_director.js 明文：
- 顶部动作按钮 widget：`{name: ACTION_WIDGET, type:'custom', serialize:false}`，label `打开 TE MAN 3D导演台`，高 34px，点击打开 3D 悬浮面板——**这是前端 createDirectorActionWidget 生成的，不属于 pyd INPUT_TYPES** [高]。
- 序列化属性：`te_3d_director_scene_json` / `te_3d_director_prompt`，并回写 widget `scene_json` / `composition_prompt`（`SCENE_WIDGET`/`PROMPT_WIDGET`、`onSerialize`/`onConfigure` 覆写）[高]。

**输入（INPUT_TYPES.required，已确认——运行时 INPUT_TYPES 仅此两项，动态回填）**

| 参数 | 类型 | 默认值 | 依据 |
|---|---|---|---|
| `scene_json` | STRING, multiline, tooltip「3D导演台保存的场景 JSON。通常由前端面板自动写入。」 | **已确认：`'{}'`（动态回填）** | 参数名 + tooltip 字符串直接证据 [高]；默认值动态实锤 |
| `composition_prompt` | STRING, multiline, 带 `display_name`/`label` = `示例提示词`, tooltip：`示例提示词，可根据导演台截图和参考图自行补充修改。` | **已确认：`DEFAULT_EXAMPLE_PROMPT` 原文（动态回填）** | [高] |

**已确认不存在于 INPUT_TYPES**：`filename_stem`、`add_to_library`（动态回填）——两者是路由 payload/内部变量，不是节点输入；节点亦无 optional / hidden 输入。

**返回**
- **已确认：`RETURN_TYPES = ("STRING", "STRING")`，`RETURN_NAMES = ("scene_json", "示例提示词")`（动态回填）**——与描述文本"输出场景 JSON 与构图提示词"吻合；第二个口名是 `示例提示词`（与 composition_prompt 参数的 display_name 同名），非 `composition_prompt`。
- `export_scene` 是否 `async`：未确认（路由协程已确认 async；节点方法仅见 qualname；introspection 未采集协程标志）。

### 3.2 路由 `POST /te_3d_director/capture`（te_3d_director_capture）

请求（前端 `saveCapture()` 发送的 JSON body，[高] 来自 JS 明文）：
```json
{ "image_data": "<data:image/png;base64,...>", "save_mode": "canvas" | "library",
  "project": "默认项目", "category": "3D导演台" }
```

流程（全部步骤均有字符串佐证）：
1. 读请求体，失败 → `读取请求体失败: <e>`；`json.loads` 抛 `JSONDecodeError` → `请求体不是有效的 JSON。` [高]
2. 校验 `image_data`：空 → `截图数据为空`；非 `data:image/` 前缀或 `image/png` → `截图数据必须是 base64 图片` / `只支持 PNG 截图`；`base64.b64decode` 得到 PNG 字节 [高]
3. `_target_dir_for_payload`：`save_mode` 取 `lower()`；`'library'`（资产库模式）→ 落到 input 目录下 `ASSET_ROOT_NAME`/`assets`/（project）`默认项目`/（category）`3D导演台` 结构（`assets`、`project`、`category` 字符串佐证）[中]；否则（`'canvas'`）→ input 目录下 `CAPTURE_FOLDER`（`TE_MAN_3D_Director`）[中]；越界目录分别报 `非法素材库路径` / `非法截图路径` [高]
4. 文件名：优先取 payload 的 `filename_stem`（`_clean_filename_stem` 清洗非法字符），为空则 `fallback` 到 `strftime('TE_MAN_3D_director_%Y%m%d_%H%M%S', localtime)`；`_clean_segment` 折叠空白；冲突时 `_dedupe_path` 加后缀；写入 `.png` 文件（`open`/`write`/`'wb'`/`mkdir(exist_ok=True)`）[高/中混合]
5. 汇总图片信息 `_image_info`（`stat`：`st_size`→`size`、`st_mtime`→`mtime`）[高]
6. 资产库模式（`is_library`，`is_library` 字符串佐证）追加资产记录 `_asset_record` 到资产素材库索引（索引文件维护在资产库核心模块，跨模块，未确认）[中]
7. 响应 `json_response`：`{'success': True, 'image': {'filename': ..., 'subfolder': ..., 'type': 'input'}, ...}` [高——前端消费 `resp.success`/`resp.error`/`resp.image` 三个键]，其余键（`target_path`、`relative_path`、`status`、`message`）存在字符串，具体结构未确认。

前端三种消费路径（te_3d_director.js 明文 [高]）：
- `save_mode='canvas'`：响应 `image` 交给 `createCanvasImageNode`，在画布创建 `TE_image_pro_save_image_with_output` 节点接收截图（"发送至ComfyUI"）；
- `save_mode='library'`：入资产库后调用 `window.TEImageAssetLibrary.refreshLibrary({quiet:true})`（"加入资产库"）；
- 另有纯前端 `downloadCapture()`（浏览器直接下载，不经 pyd）。
- 全景图上传不改走本路由，改用 ComfyUI 标准 `POST /upload/image`，`subfolder='TE_MAN_3D_Director/Panoramas'` [高]。

## 4. 外部依赖与副作用

- **无网络外呼**：IMPORT 表无 WS2_32/网络库；字符串中无任何 URL/域名/API Key [高]。所有 HTTP 行为都是本地 aiohttp 服务端路由。
- Python 依赖（字符串佐证 [高]）：`folder_paths`（ComfyUI，`get_input_directory`）、`PromptServer`（aiohttp `routes.post`、`json_response`、`request`）、`aiohttp`、`base64`、`json`（`JSONDecodeError`）、`threading`（`Thread`、`daemon`）、`pathlib`、`os`/`Path`、`time`（`localtime`、`strftime`）、`re`、`asyncio`（`sleep`、`asyncio.coroutines`）。
- **文件系统写入**（副作用）：
  - 截图：`<ComfyUI_input>/TE_MAN_3D_Director/*.png`（save_mode 非 library）[中]
  - 资产库：`<ComfyUI_input>/<TE_MAN>/assets/默认项目/3D导演台/…` + 资产库索引 [中]
  - 全景图（前端经标准 `/upload/image`）：`<ComfyUI_input>/TE_MAN_3D_Director/Panoramas/` [高]
- 无 torch / 无 API 客户端调用；与 `config.ini`、`api_client` 等支撑库无字符串关联 [高]。

## 5. 错误处理与用户可见文案

| 消息 | 触发场景 |
|---|---|
| `读取请求体失败: <e>` | 路由读 HTTP body 异常（带异常拼接）[高] |
| `请求体不是有效的 JSON。` | body 不是合法 JSON（json.loads/JSONDecodeError）[高] |
| `截图数据为空` | payload 无 `image_data` [高] |
| `截图数据必须是 base64 图片` | `image_data` 不是合法 data URL/base64 [高] |
| `只支持 PNG 截图` | data URL 的 content_type 不是 `image/png`（字符串 `只支持 PNG 截图`）[高] |
| `非法截图路径` | 目标路径逃出 input 目录（save_mode 非 library）[高] |
| `非法素材库路径` | 资产库目标路径逃出 assets 根 [高] |

错误统一经 `_json_error` 以 `{'success': False, 'error': ...}` 返回 [中]（前端仅校验 `resp.success`/`resp.error`，与之吻合 [高]）。

## 6. 证据附录

### 6.1 Cython qualname 符号表（完整列表，源 .py 的全部函数）
```
custom_nodes.TE_image.TE_3D_Director._json_error
custom_nodes.TE_image.TE_3D_Director._input_dir
custom_nodes.TE_image.TE_3D_Director._is_inside
custom_nodes.TE_image.TE_3D_Director._clean_segment
custom_nodes.TE_image.TE_3D_Director._clean_filename_stem
custom_nodes.TE_image.TE_3D_Director._dedupe_path
custom_nodes.TE_image.TE_3D_Director._decode_png_data_url
custom_nodes.TE_image.TE_3D_Director._image_info
custom_nodes.TE_image.TE_3D_Director._asset_record
custom_nodes.TE_image.TE_3D_Director._target_dir_for_payload
custom_nodes.TE_image.TE_3D_Director.te_3d_director_capture
custom_nodes.TE_image.TE_3D_Director._register_routes
custom_nodes.TE_image.TE_3D_Director._register_routes_when_ready._wait_for_server
custom_nodes.TE_image.TE_3D_Director._register_routes_when_ready
custom_nodes.TE_image.TE_3D_Director.TEMan3DDirectorNode.INPUT_TYPES
custom_nodes.TE_image.TE_3D_Director.TEMan3DDirectorNode.export_scene
custom_nodes.TE_image.source_py_backup.TE_3D_Director.c   (编译源)
custom_nodes/TE_image/source_py_backup/TE_3D_Director.py  (源文件)
```

### 6.2 中文与交互字符串（rdata 0x13370–0x14f00 连续常量区）
```
读取请求体失败:   请求体不是有效的 JSON。  截图数据为空
截图数据必须是 base64 图片   只支持 PNG 截图
非法素材库路径   非法截图路径
存场景 JSON。通常由前端面板自动写入
打开 TE MAN 3D导演台，编辑角色、道具、机位和姿势，并输出场景 JSON 与构图提示词。
让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面
示例提示词   示例提示词，可根据导演台截图和参考图自行补充修改。
3D导演台   默认项目   TE MAN 3D导演台   TE MAN/3D
```

### 6.3 节点注册/属性字符串
```
NODE_CLASS_MAPPINGS  NODE_DISPLAY_NAME_MAPPINGS  display_name
TE_3D_Director  CATEGORY  TE MAN/3D  FUNCTION  export_scene
OUTPUT_NODE  RETURN_TYPES  RETURN_NAMES  REQUIRED  STRING  INPUT_TYPES
DESCRIPTION  tooltip  multiline  validate  label
_Routes id: /te_3d_director/capture  post  PromptServer  aiohttp  json_response
_ROUTES_REGISTERED  _ROUTE_REGISTER_THREAD_STARTED  daemon  Thread  sleep
```

### 6.4 文件名/路径/清洗字符串
```
TE_MAN_3D_director_%Y%m%d_%H%M%S   filename_stem   timeout: strftime  localtime  fallback
_clean_filename_stem  _clean_segment  _dedupe_path   \s+   ,   [<>:"|?*\x00-\x1f]+
CAPTURE_FOLDER  TE_MAN_3D_Director  .png  input  assets  size  mtime  st_size  st_mtime
image  image_data  data_url  data:image/  image/png  content_type  base64  b64decode
payload  request  type: wb  write  open  mkdir  exist_ok
project  category  is_library  save_mode  add_to_library  target_path  target_dir  relative_path
ASSET_ROOT_NAME  DEFAULT_PROJECT  DEFAULT_CATEGORY  get: stat  commonpath  relative_to  parents
resolve  ..  非法截图路径  非法素材库路径
```

### 6.5 前端互证（web/js/te_3d_director.js 头部明文常量，未混淆段）
```js
const EXTENSION_NAME='TEImagePro.3DDirector', NODE_CLASS='TE_3D_Director',
      IMAGE_NODE_CLASS='TE_image_pro_save_image_with_output',
      SCENE_WIDGET='scene_json', PROMPT_WIDGET='composition_prompt',
      PROP_SCENE='te_3d_director_scene_json', PROP_PROMPT='te_3d_director_prompt',
      DEFAULT_PROJECT='默认项目', DEFAULT_CATEGORY='3D导演台',
      PANORAMA_SUBFOLDER='TE_MAN_3D_Director/Panoramas',
      ACTION_WIDGET_LABEL='打开 TE MAN 3D导演台',
      DEFAULT_EXAMPLE_PROMPT='让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面'
```
路由调用（混淆插桩处明文）：
```js
await api.fetchApi('/te_3d_director/capture', {method:'POST',
  headers:{'Content-Type':'application/json'},
  body: JSON.stringify({image_data: this.captureDataUrl(), save_mode: mode,
                        project: DEFAULT_PROJECT, category: DEFAULT_CATEGORY})})
// 响应: resp.success / resp.error / resp.image -> createCanvasImageNode(node, resp.image)
```

### 6.6 未确认事项汇总
- `RETURN_TYPES`/`RETURN_NAMES` 具体值 —— **已确认：`("STRING", "STRING")` / `("scene_json", "示例提示词")`（动态回填，见 §3.1）**。
- `export_scene` 是否 async、内部是否做除透传/组装外的工作。（introspection 未采集协程标志，保持未确认）
- `filename_stem`、`add_to_library` 究竟是节点 INPUT_TYPES 输入还是路由/内部变量 —— **已确认：两者都不在 INPUT_TYPES 中，为路由 payload/内部变量（动态回填）**。
- `'{}'` 是否为 `scene_json` 默认值 —— **已确认：是（动态回填）**；`CAPTURE_FOLDER`/`ASSET_ROOT_NAME` 的确切取值 —— **已确认：`'TE_MAN_3D_Director'` / `'TE_MAN'`（动态回填）**。
- `_target_dir_for_payload` 中 save_mode 分支值（前端仅用 `'canvas'`/`'library'` 两种；pyd 内 `'input'` 字符串的用途未确认）。（introspection 不覆盖路由内部，保持未确认）
- 资产库索引文件的写入方（推测由资产库核心模块持有，`_asset_record` 只产出记录）。（保持未确认）

## 7. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows Server 2025 + ComfyUI（Python 3.13.16）真实环境 import 后的自省结果；运行时模块显示为 `custom_nodes.TE_image.TE_3D_Director`（`TE_image` 为插件原名），模块文件 `D:\a\_temp\ComfyUI\custom_nodes\TE_MAN\TE_3D_Director.pyd`。本节所有值均为运行时实锤。

### 7.1 节点 INPUT_TYPES 全表（实锤）

#### TE_3D_Director（TEMan3DDirectorNode）

注册元数据：`FUNCTION = "export_scene"`、`CATEGORY = "TE MAN/3D"`、`OUTPUT_NODE = True`、`RETURN_TYPES = ["STRING", "STRING"]`、`RETURN_NAMES = ["scene_json", "示例提示词"]`；无 IS_CHANGED / VALIDATE_INPUTS / on_execute / check_lazy_status。节点 DESCRIPTION（原文）："打开 TE MAN 3D导演台，编辑角色、道具、机位和姿势，并输出场景 JSON 与构图提示词。"显示名（node_display_name_mappings）：`TE MAN 3D导演台`。

**required**：

| 参数名 | 类型 | 选项 / 约束 | 默认值 | tooltip（原文摘要） |
|---|---|---|---|---|
| `scene_json` | STRING, multiline | — | `{}` | 3D导演台保存的场景 JSON。通常由前端面板自动写入。 |
| `composition_prompt` | STRING, multiline（带 `display_name: 示例提示词`、`label: 示例提示词`） | — | 让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面 | 示例提示词，可根据导演台截图和参考图自行补充修改。 |

**optional / hidden**：无。

运行时模块级常量实锤：`ASSET_ROOT_NAME = "TE_MAN"`、`CAPTURE_FOLDER = "TE_MAN_3D_Director"`、`DEFAULT_CATEGORY = "3D导演台"`、`DEFAULT_PROJECT = "默认项目"`、`DEFAULT_EXAMPLE_PROMPT = "让镜头角度和人物在场景中的站位关系按照 图1 中的设定, 把蓝色人偶替换为 图2 人物,把粉色人偶替换为 图3 人物,双方在城市街道见面"`（§2.2 三个 [中] 常量全部转实锤）；`_ROUTES_REGISTERED = False`（introspection 时刻路由尚未注册）、`_ROUTE_REGISTER_THREAD_STARTED = True`（后台注册线程已启动——与 §2.2 `_register_routes_when_ready` 的 daemon 线程机制吻合）。

### 7.2 "未确认"项核对结果

| 原文位置 | 结论 |
|---|---|
| §2.2 `CAPTURE_FOLDER` / `ASSET_ROOT_NAME` 取值 [中] | **已确认：`"TE_MAN_3D_Director"` / `"TE_MAN"`（动态回填）** |
| §3.1 INPUT_TYPES 仅 scene_json + composition_prompt？ | **已确认：是，required 恰此两项，无 optional/hidden（动态回填）**；`filename_stem`、`add_to_library` 均非节点输入（属路由 payload/内部变量） |
| §3.1 `scene_json` 默认 `'{}'` [中] | **已确认：`'{}'`（动态回填）** |
| §3.1 `composition_prompt` 默认与 label | **已确认：默认 = DEFAULT_EXAMPLE_PROMPT 原文；`display_name`/`label` = `示例提示词`（动态回填）** |
| §3.1 `RETURN_TYPES`/`RETURN_NAMES` | **已确认：`["STRING", "STRING"]` / `["scene_json", "示例提示词"]`（动态回填）**——两字符串输出，无 IMAGE |
| §3.1 `OUTPUT_NODE` Truthy [高] | **已确认：True（动态回填）** |
| §3.1 `export_scene` 是否 async | introspection 未采集协程标志，保持未确认 |
| §6.6 `_target_dir_for_payload` save_mode 分支 / `'input'` 字符串用途 | introspection 不覆盖路由内部逻辑，保持未确认 |
| §6.6 资产库索引文件写入方 | 保持未确认（跨模块） |

另注：节点主执行 `export_scene` 本体在 introspection 中无 method_docs，内部行为仍是黑盒（pyd 很薄、透传为主的基本判断不受影响）。
