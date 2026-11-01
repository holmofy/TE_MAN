# TE_Asset_Library.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，导出 `PyInit_TE_Asset_Library`；依赖 python3.dll / KERNEL32.dll / VCRUNTIME140.dll / api-ms-win-crt-runtime（无网络库绑定，网络路由走 aiohttp Python 层）。
> 静态分析证据：导入导出表 + ASCII/UTF-8 字符串（含 Cython 字符串表聚类）+ 明文孪生前端 `web/js/te_asset_library.js`（已反混淆解码，其 226 条字符串表与后端常量逐一对应）。
> 置信度：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测；"未确认" = 证据不足。

## 1. 模块定位

TE_MAN 资产素材库的**后端节点 + HTTP 路由模块**：维护 `<ComfyUI_input>/TE_MAN/` 下的"项目 / 分类 / 素材文件"三级目录素材库（图片、提示词文本、音频三类），向外暴露 11 个 `/te_asset_library/*` 路由供前端资产库面板与 3D 导演台调用，并注册一个 ComfyUI 节点 `TEAssetLibrary`（从素材库加载图片为 IMAGE 张量）。模块内含完整独立实现（不经 `core` 分层），原源码路径证据：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Asset_Library.c` → `custom_nodes/TE_image/source_py_backup/TE_Asset_Library.py` [高]。由 `__init__.py` 自动加载器加载（不在 `SKIP_MODULES` 中）[高]。

## 2. Python API

### 导出
- `PyInit_TE_Asset_Library`（PE 导出表唯一符号）[高]
- `__all__`、`NODE_CLASS_MAPPINGS`、`NODE_DISPLAY_NAME_MAPPINGS`（字符串常量在列）[高]

### 注册的 ComfyUI 节点
| NODE_CLASS_MAPPINGS 键 | 显示名 | CATEGORY | FUNCTION |
|---|---|---|---|
| `TEAssetLibrary`（节点类名字符串与 `custom_nodes.TE_image.TE_Asset_Library.TEAssetLibrary` 共现）[高] | 未确认（pyd 中未见显示名字符串常量） | `TE MAN/Utils` [高，字符串 `TE MAN/Utils`] | `load_asset` [高] |

> **动态回填重要更正**：GitHub Actions Windows+ComfyUI 真机实测中，`TE_MAN.TE_Asset_Library` 模块导入成功且 `TEAssetLibrary` 类存在（module `custom_nodes.TE_image.TE_Asset_Library`），但该模块加载后的 `NODE_CLASS_MAPPINGS` 与 `NODE_DISPLAY_NAME_MAPPINGS` 均为**空字典 `{}`**（常量实测），且整个插件的 30 个运行时注册节点中**不含任何 TE_Asset_Library 节点**——即当前发布构建中此模块不注册 ComfyUI 节点，仅作为 HTTP 路由/素材库服务模块存在。pyd 内的节点注册代码在运行时呈空映射（或注册被门控关闭）。上表的"TEAssetLibrary 节点"仅为 pyd 静态字符串证据，其 INPUT_TYPES 无法从运行时获得，涉及该节点的"未确认"项维持原状。

### 模块级函数完整清单（来自 Cython 限定名符号表，全部 [高]）
- 路径/安全：`_input_dir`、`_asset_root`、`_is_inside`、`_clean_segment`、`_clean_filename_stem`、`_ensure_default_structure`、`_ensure_prompt_category`、`_project_dir`、`_category_dir`、`_normalize_asset_relative_path`、`_resolve_asset_path`、`_resolve_image_asset_path`、`_resolve_text_asset_path`、`_input_relative_path`、`_is_image_path`、`_is_text_path`、`_is_audio_path`、`_is_asset_path`
- 列表/元数据：`_view_image_info`、`_iter_image_files`、`_iter_asset_files`、`_image_dimensions`、`_read_text_file`、`_text_preview`、`_text_stats`、`_image_asset_record`、`_text_asset_record`、`_audio_asset_record`、`_asset_record`、`_project_records`、`_list_assets`、`_all_asset_choices`
- 写入/复制：`_resolve_source_image`、`_resolve_source_audio`、`_dedupe_path`、`_copy_to_library`、`_normalize_text_value`、`_default_prompt_filename_stem`、`_write_text_to_library`、`_infer_project_category`、`_rename_asset`、`_delete_asset`、`_delete_category`、`_load_image_tensor`
- 路由/I/O：`_json_error`、`te_asset_library_list`、`_handle_te_asset_library_project`、`_handle_te_asset_library_category`、`_handle_te_asset_library_delete_category`、`te_asset_library_add`、`te_asset_library_audio_add`、`te_asset_library_text_add`、`_handle_te_asset_library_text_get`、`_handle_te_asset_library_rename`、`_handle_te_asset_library_delete`、`te_asset_library_thumbnail`

## 3. 素材库目录结构（重点）

物理根目录（即符号 `_asset_root`）~~[中高]~~ → **已确认（动态回填）**：`ASSET_ROOT_NAME = "TE_MAN"`：

```
<ComfyUI_input>/TE_MAN/            ← ASSET_ROOT_NAME 指向的根（值推断为 "TE_MAN"，见 3.1）
└── <项目>/                        ← 默认 "默认项目"（DEFAULT_PROJECT）
    └── <分类>/                    ← 人物 / 产品 / 场景 / 背景 / 3D导演台 / ...（用户可建）
        ×                        ├── *.png|jpg|jpeg|webp|...  图片素材
        ×                        ├── 提示词 分类：*.txt         提示词文本素材
        ×                        └── 音频  分类：*.wav|mp3|...  音频素材
```

### 3.1 根目录证据链 ~~[中高]~~ → 已确认（动态回填：`ASSET_ROOT_NAME="TE_MAN"` 常量实锤）
- 节点 docstring：「从 input/TE_MAN 项目素材库读取图片」[高]（pyd 原文 ` input/TE_MAN `）
- 前端面板始终显示物理位置：`'[data-role=summary]' = 'input/TE_MAN/' + state.project` [高]（`te_asset_library.js` 明文）
- 节点 tooltip：「素材路径，例如 TE_MAN/项目/人物/a.png」[高] —— 资产 `relative_path` 是 **input 相对路径并带 `TE_MAN/` 前缀**：前端 `imageInfoFromAsset(a)` 直接把 `relative_path` 按 `/` 切分出 `subfolder/filename`、`type='input'` 喂给 ComfyUI LoadImage [高]
- 内部路径归一化错误要求「素材路径需要是 项目/分类/文件名」（去掉 `TE_MAN` 根前缀后的三段式）[高]
- pyd 含独立的 `TE_MAN` 常量与 `get_input_directory` / `joinpath` 符号 [高]
- **特别澄清**：pyd 与前端中的 `assets` 字符串经前端表解码确认为 `/te_asset_library/list` **响应键**（`state['assets'] = resp[getter(0x21b)]`，0x21b→`'assets'`）[高]，**不是**磁盘目录层。前端 JS 明文模板中所有磁盘路径展示均为 `input/TE_MAN/<project>`。与 `spec/TE_3D_Director.md` 中推断的 `<input>/TE_MAN/assets/默认项目/3D导演台` 层级存在矛盾：本模块所有相对路径请求/响应均为"项目/分类/文件名"三段式，未见 `assets` 路径段——该矛盾未确认（3D Director 的 `assets` 常量同样可能为响应键或其自有记录键，需单独核验 TE_3D_Director）。

### 3.2 默认结构与常量 [高/中]
常量名（符号表）：`ASSET_ROOT_NAME`、`DEFAULT_PROJECT`、`DEFAULT_CATEGORIES`、`TEXT_CATEGORY`、`AUDIO_CATEGORY`、`PROTECTED_CATEGORIES`、`ASSET_KIND_IMAGE/TEXT/AUDIO`（kind 值 `image`/`text`/`audio` [高，前端常量同值]）。
值（pyd 中文常量 + 前端明文/解码交叉印证；**标注"动态回填"者为 introspection 实测实锤**）：
- `DEFAULT_PROJECT = '默认项目'` **已确认（动态回填）**
- `TEXT_CATEGORY = '提示词'` **已确认（动态回填）**
- `AUDIO_CATEGORY = '音频'` **已确认（动态回填）**
- `DEFAULT_CATEGORIES = ['人物', '产品', '场景', '背景', '提示词', '音频']`（**动态回填实测，六项、含'提示词'与'音频'、不含'未分类'、顺序即此**——将静态 [中] 的四成员候选升级为实锤）
- `PROTECTED_CATEGORIES`：**动态回填注意**——introspection 的模块常量表中**未出现** `PROTECTED_CATEGORIES` 键（实测仅见 `DEFAULT_CATEGORIES/TEXT_CATEGORY/AUDIO_CATEGORY/ASSET_KIND_*/TEXT_PREVIEW_MAX_CHARS` 等），其后端精确成员集合维持未确认（前端解码集合 `['__all__','全部','未分类','','提示词']` + 后端 `'音频'` 串证据不变）
- 前端伪分类 `DEFAULT_CATEGORY='__all__'`（UI 标签"全部"，protected），传给 /list 表示跨全部分类 [高]
- `_ensure_default_structure`：首次运行在建库根、默认项目与默认分类（ đồng 时为文本加入保证 `_ensure_prompt_category` 建 `'提示词'` 分类）[中，函数名+类别常量佐证；动态回填见常量实锤]

### 3.3 索引/元数据存储（重点）
**无索引文件/数据库**。素材元数据完全实时派生：`_project_records`/`_list_assets` 递归目录扫描（`Path.iterdir`、`rglob`、`is_file` 符号）+ 每文件统计生成记录 [高——pyd 中不存在任何索引文件名常量（无 `.json` 索引名），且记录构造器 `_image_asset_record`/`_text_asset_record`/`_audio_asset_record` 从 `stat`/`st_mtime`/`st_size`/图片尺寸/文本内容即时计算]。删除目录/文件即完成库更新（`unlink`、`shutil.rmtree`、`shutil.copy2`）[高]。
资产记录字段（响应/构造器符号 + 前端消费字段，[高]）：`name`、`relative_path`、`project`、`category`、`kind`、`mtime`、`size`、`filename_stem`；图片加 `width`、`height`、`image_info`；文本加 `text_preview`、`line_count`、`char_count`；音频加 `audio_info`（`{filename, subfolder, type}`）。
其它常量：`TEXT_PREVIEW_MAX_CHARS`（预览截断上限~~数值未确认~~ → **已确认 = 220，动态回填**）、`ASSET_EXTENSIONS` / `IMAGE_EXTENSIONS` / `TEXT_EXTENSIONS` / `AUDIO_EXTENSIONS` / `IMAGE_CONTENT_TYPES` / `TEXT_CONTENT_TYPES` / `AUDIO_CONTENT_TYPES`（后三者完整映射见 §9 动态回填表）。

各类型扩展名与 MIME（pyd 出现的原文串；**标注"动态回填"者为 `*_CONTENT_TYPES` 映射实测**）：
- 图片：`.png`、`.jpeg`、`.webp`[高]；`.jpg/.gif/.bmp` 未确认；`image/png`、`image/jpeg`、`image/webp`、`image/gif`、`image/bmp`、`image/*`——动态回填 `IMAGE_CONTENT_TYPES = {.png: image/png, .jpg: image/jpeg, .jpeg: image/jpeg, .webp: image/webp, .bmp: image/bmp, .gif: image/gif}`（六后缀齐，含 .jpg/.gif/.bmp，MIME 与串证据一致）
- 文本：`.txt` [高]，`text/plain`——动态回填 `TEXT_CONTENT_TYPES = {.txt: text/plain}`
- 音频：`.wav`、`.mp3`、`.flac`、`.opus`、`.m4a`[高]；`audio/wav`、`audio/mpeg`、`audio/flac`、`audio/ogg`、`audio/opus`、`audio/mp4`、`audio/aac`、`audio/x-ms-wma`、`audio/*`；~~`.ogg/.aac/.wma` 后缀未确认~~ → **动态回填 `AUDIO_CONTENT_TYPES = {.wav: audio/wav, .mp3: audio/mpeg, .flac: audio/flac, .ogg: audio/ogg, .opus: audio/opus, .m4a: audio/mp4, .aac: audio/aac, .wma: audio/x-ms-wma}`——八后缀全部实锤（含 .ogg/.aac/.wma），与 JS 判定正则完全一致**

## 4. 注册的 HTTP 路由（重点）

经 `PromptServer`（aiohttp `routes`，符号 `PromptServer`、`json_response`、`Response`、`rel_url`、`query`、`headers`、`method`）注册，共 11 条 [高，与前端调用一一对应]：

| 方法 | 路由 | 入参（前端调用实证） | 行为 |
|---|---|---|---|
| GET | `/te_asset_library/list?` | `project`、`category`（`__all__`=全部）、`query`（搜索） [中，URLSearchParams 构造] | 返回 `{'projects':[{name, categories:[{name,count}]}], 'current_project', 'current_category', 'assets':[记录…]}` [高] |
| POST | `/te_asset_library/project` | `{project}` [高] | 新建项目目录 [中] |
| POST | `/te_asset_library/category` | `{project, category}` [高] | 新建分类（默认提示"人物"）[高] |
| POST | `/te_asset_library/category/delete` | `{project, category}` [高] | 删除分类文件夹；受保护/非目录拒绝 [高] |
| POST | `/te_asset_library/add` | `{project, category, filename_stem, upload_image | image_info}` [高，前端字面 JSON] | 图片入库 |
| POST | `/te_asset_library/audio/add` | `{project, filename_stem, upload_audio | audio_info}` [高] | 音频入库，分类固定"音频" [高] |
| POST | `/te_asset_library/text/add` | `{project, title, text}` [高] | 提示词入库（`title` 留空自动命名 [高]） |
| GET | `/te_asset_library/text/get?` | 素材路径 + `limit_chars` [高，`limit_chars` 常量在列] | 返回文本内容 [中] |
| POST | `/te_asset_library/rename` | `{relative_path, new_name}` [高] | 素材更名 [高] |
| POST | `/te_asset_library/delete` | `{relative_path}` [高] | 删除单个素材文件 [高] |
| GET | `/te_asset_library/thumbnail?` | `path`、`size`（前端 `Math.min(viewSize*2, 220)`）[高] | 生成缩略图响应 |

入库来源解析（`te_asset_library_add`）[中高]：
- `upload_image`：ComfyUI input 目录内已上传文件（`get_input_directory`）[高]
- `image_info:{filename, subfolder, type}`：`type='input'|'output'` 走 `get_directory_by_type`；TE 自定义保存目录走 `save_image_with_output_core` 的 `resolve_custom_save_image_path` + 环境变量/常量 `TE_CUSTOM_SAVE_IMAGE_TYPE` [高，符号与名称直接共现]；失败报「不支持的图片目录类型: 」
- `filename_stem` 留空取源文件 stem 清洗（`_clean_filename_stem`，非法字符正则 `[<>:"|?*\x00-\x1f]+` [高]）
- `_dedupe_path` 重名冲突处理；`FileExistsError` 与「文件已存在: 」并存 [中——去重后缀规则与报错触发时机未确认]
- 因 `commonpath/is_symlink` 越界防护：「非法素材路径/非法项目路径/非法分类路径/非法图片路径/非法音频路径/非法目标路径」

缩略图实现 [高]：PIL 打开 → `exif_transpose` → `convert('RGB')` → `Resampling.LANCZOS` 缩到 `size` → 存 `BytesIO` WebP（`quality`）→ `web.WebP`；响应头 `Content-Type: image/webp`、`Cache-Control: no-cache`、`X-TE-Asset-MTime`（mtime 缓存校验）[高，全为字面常量]。

## 5. 节点规格：TEAssetLibrary

- **输入**（INPUT_TYPES，[中]——字段符号+tooltip 直接证据）：`asset_path`（required，动态候选列表来自 `_all_asset_choices` [中]；tooltip「素材路径，例如 TE_MAN/项目/人物/a.png」「也可以从 TE MAN 资产素材库面板拖拽生成加载图像节点」[高]）
- **VALIDATE_INPUTS** [高]：校验路径存在与扩展名合法：「图片不存在: 」「不支持的图片格式」（`_resolve_image_asset_path`）
- **返回** [中]：`RETURN_TYPES`/`RETURN_NAMES` 符号在列，`IMAGE` 常量在列；除 IMAGE 外是否输出 `image_info`/`width`/`height` 未确认
- **`load_asset`**：`relative_path` → `_resolve_image_asset_path` 越界/存在性校验 → `_load_image_tensor`（PIL `Image/ImageOps/ImageSequence` + numpy `astype(float32)` → torch `from_numpy`/`unsqueeze`，输出 CHW 张量）[高，符号共现]
- 前端交互面：双击/添加素材即在画布生成节点类型 `TE_image_pro_save_image_with_output`（图片）、`TE_audio_save_load`（音频）、`TE_text_display`（文本），并把 `relative_path` 写进对应 widget（`upload_image`/`upload_audio`）[高，前端明文]——即本节点/UI 面板与 save_image_with_output 体系通过 input 相对路径解耦。

与 3D 导演台的协作：`TE_3D_Director` 前端调用 `saveCapture('library')` → POST 其自有 `/te_3d_director/capture` 路由写入素材库对应目录（项目"默认项目"、分类"3D导演台"），随后调用本模块前端 API `window.TEImageAssetLibrary.refreshLibrary()/showPanel()` 刷新展示 [高，前端明文抓取]。TE_3D_Director.pyd 不 import 本模块（二进制无 `TE_Asset_Library` 串）[高]，自带 `_asset_record`/`relative_path` 复刻记录生成 [高]——其截图入库路径在本模块扫描结构下会自动被列出（无需登记）。其规格文档声称物理层级含 `assets` 段，本模块证据不支持该层级（见 3.1 矛盾说明）。

## 6. 外部依赖与副作用

- Python 侧第三方调用符号：`folder_paths`（input 目录定位）、`aiohttp`、`PIL`（Image/ImageOps/ImageSequence/Resampling/LANCZOS/exif_transpose）、`numpy`、`torch`、`shutil`（copy2/rmtree）、`pathlib`、`time`（`strftime`、`localtime`）、`json` [高]
- `save_image_with_output_core`（TE 自定义保存图目录）+ `TE_CUSTOM_SAVE_IMAGE_TYPE` [高]
- 读文件编码 `utf-8-sig`（BOM 兼容）与 `utf-8` [高]
- 文件系统副作用：在 `<input>/TE_MAN` 下 create/mkdir parents/copy2/unlink/rmtree [高]
- 无外部网络端点、无注册表访问（IMPORT 无 WS2_32/ADVAPI32）[高]；`X-TE-Asset-MTime` 为本地响应头，非远程 API
- 文本临时命名模板：`TE_MAN_prompt_%Y%m%d_%H%M%S`（strftime），与前端提示「留空则自动命名为 TE_MAN_prompt_年月日时分秒」一致 [高]

## 7. 错误处理与用户可见文案（pyd 中文常量全录 [高]）

| 消息 | 触发场景（推断 [中]） |
|---|---|
| 素材路径需要是 项目/分类/文件名 | relative_path 段数/解析失败 |
| 非法素材路径 / 非法项目路径 / 非法分类路径 / 非法目标路径 / 非法图片路径 / 非法音频路径 | 越界（`_is_inside`/`commonpath`）、段清洗失败 |
| 素材不存在:  / 提示词素材不存在:  / 图片不存在:  / 音频不存在:  / 分类不存在:  | resolve 未命中 |
| 不支持的素材格式 / 不支持的图片格式 / 不支持的文本格式 | 扩展名不在 *_EXTENSIONS |
| 不支持的图片目录类型:  / 不支持的音频目录类型:  | image_info/audio_info.type 无法解析为目录 |
| 只支持添加图片文件 / 只支持添加音频文件 | add / audio_add 传入非对应类型 |
| 没有找到可添加的图片 / 没有找到可添加的音频 | 请求缺 upload_* 与 *_info 两路来源 |
| 请先选择一个素材 | 删除/更名未选中 |
| 新文件名不能为空 | rename 空参 |
| 文件已存在:  | 复制/更名目标名冲突 |
| 提示词内容不能为空 | text_add 空 text |
| 只能删除素材库里的分类文件夹 | delete_category 目标不是目录 |
| 请选择一个可删除的分类 | 命中 PROTECTED_CATEGORIES / 空 |
| 非法素材库路径（TE_3D_Director 侧） | 3D 导演台 library 模式越界 |

前端面板文案（明文 JS，佐证交互 [高]）：「已添加到素材库：」「添加失败：」「已更名：」「更名失败：」「已删除：」「删除失败：」「已新建项目：」「新建项目失败：」「已新建分类：」「新建分类失败：」「删除分类失败：」「已添加提示词：」「添加音频失败：」「已加载 … 个素材」「复制失败」「创建节点失败：」「正在加载素材...」「这个项目/分类里还没有素材。可以从 TE 图像、音频或文本节点添加。」「点"添加"或双击素材创建对应节点。」

## 8. 证据附录

### 8.1 路由与接口（pyd ASCII/UTF-8 原文）
```
/te_asset_library/list  /te_asset_library/project  /te_asset_library/category
/te_asset_library/category/delete  /te_asset_library/add  /te_asset_library/audio/add
/te_asset_library/text/add  /te_asset_library/text/get  /te_asset_library/rename
/te_asset_library/delete  /te_asset_library/thumbnail
```

### 8.2 常量与配置名（pyd 原文）
```
ASSET_ROOT_NAME  DEFAULT_PROJECT  DEFAULT_CATEGORIES  PROTECTED_CATEGORIES
TEXT_CATEGORY  AUDIO_CATEGORY  ASSET_KIND_IMAGE  ASSET_KIND_TEXT  ASSET_KIND_AUDIO
ASSET_EXTENSIONS  IMAGE_EXTENSIONS  TEXT_EXTENSIONS  AUDIO_EXTENSIONS
IMAGE_CONTENT_TYPES  TEXT_CONTENT_TYPES  AUDIO_CONTENT_TYPES
TEXT_PREVIEW_MAX_CHARS  TE_CUSTOM_SAVE_IMAGE_TYPE
X-TE-Asset-MTime  Cache-Control  no-cache  image/webp  .webp  quality  LANCZOS  Resampling
limit_chars  utf-8-sig  TE_MAN_prompt_%Y%m%d_%H%M%S  [<>:"|?*\x00-\x1f]+
upload_image  upload_audio  image_info  audio_info  filename_stem  relative_path
```

### 8.3 数据键（pyd 原文，与前端消费一致）
```
projects  assets  current_project  current_category  query  kind  name  category  project
width  height  mtime  size  st_mtime  st_size  text_preview  line_count  char_count
subfolder  filename  type  image  text  audio  input  output  deleted  success  error  message  required
```

### 8.4 前端反混淆补充（`te_asset_library.js` 字符串表 R=65 解码）
```
0x1df = 提示词(=TEXT_CATEGORY)   0x21b = assets（/list 响应键→state['assets']）
0x22a = 未分类（PROTECTED 集合）   0x1c0 = TE_audio_save_load(AUDIO_NODE_CLASS)
0x234 = /te_asset_library/list?   0x1a2 = /te_asset_library/delete
0x1ad(解码得 relative_path=0x220 被 DEFAULT_CATEGORY='__all__' 字面量旁证)
IMAGE_NODE_CLASS='TE_image_pro_save_image_with_output'（明文）
```

### 8.5 原源码构建路径
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_Asset_Library.c
custom_nodes/TE_image/source_py_backup/TE_Asset_Library.py
```

### 8.6 README 交叉印证（功能面）
- 「资产素材库」「提示词素材库」「资产库新增独立的音频分类，可预览和再次添加音频」（README v3.8 功能与更新日志）
- 「一键把文本展示节点里的提示词加入素材库，按项目统一保存、预览、复制、重命名和再次添加到工作流」→ 对应 text_add (项目/分类"提示词")
- 3D 导演台「当前机位截图可发送至ComfyUI或加入资产库」

## 9. 动态 introspection 回填（Windows+ComfyUI 真机实测）

> 数据来源：GitHub Actions Windows 2025 Server + Python 3.13.16 + ComfyUI（`D:\a\_temp\ComfyUI`）真实加载后的运行时 introspection（module 显示为 `custom_nodes.TE_image.TE_Asset_Library`，TE_image 为插件原名）。模块文件为 `TE_Asset_Library.pyd`。

### 9.1 运行时注册状态（重要）

- 模块**导入成功**（`module_import_errors` 为空），`TEAssetLibrary` 类存在于模块命名空间。
- 但模块级 `NODE_CLASS_MAPPINGS = {}`、`NODE_DISPLAY_NAME_MAPPINGS = {}`（常量实测均为空字典），且全插件 30 个运行时注册节点中无任何本模块节点。
- **结论：当前发布构建中本模块不向 ComfyUI 注册节点**，§2/§5 所述节点仅为 pyd 内静态代码存在（或被门控关闭）。§5 节点规格中所有"未确认"项（显示名、INPUT_TYPES 全貌、RETURN_TYPES/RETURN_NAMES 元组）**维持未确认**——运行时无法取得这些信息。

### 9.2 模块常量实锤值（modules["TE_MAN.TE_Asset_Library"].constants）

| 常量 | 实测值 |
|---|---|
| `ASSET_ROOT_NAME` | `"TE_MAN"`（§3.1 根目录推断实锤） |
| `DEFAULT_PROJECT` | `"默认项目"` |
| `DEFAULT_CATEGORIES` | `["人物", "产品", "场景", "背景", "提示词", "音频"]`（六项，顺序即此） |
| `TEXT_CATEGORY` | `"提示词"` |
| `AUDIO_CATEGORY` | `"音频"` |
| `ASSET_KIND_IMAGE` / `ASSET_KIND_TEXT` / `ASSET_KIND_AUDIO` | `"image"` / `"text"` / `"audio"` |
| `TEXT_PREVIEW_MAX_CHARS` | `220`（§3.3 数值未确认 → 已确认） |
| `IMAGE_CONTENT_TYPES` | `{".png":"image/png", ".jpg":"image/jpeg", ".jpeg":"image/jpeg", ".webp":"image/webp", ".bmp":"image/bmp", ".gif":"image/gif"}` |
| `TEXT_CONTENT_TYPES` | `{".txt":"text/plain"}` |
| `AUDIO_CONTENT_TYPES` | `{".wav":"audio/wav", ".mp3":"audio/mpeg", ".flac":"audio/flac", ".ogg":"audio/ogg", ".opus":"audio/opus", ".m4a":"audio/mp4", ".aac":"audio/aac", ".wma":"audio/x-ms-wma"}` |
| `TE_CUSTOM_SAVE_IMAGE_TYPE` | `"te_custom_save"`（§4 save_image_with_output 联动类型实锤） |
| `NODE_CLASS_MAPPINGS` | `{}`（空——见 9.1） |
| `NODE_DISPLAY_NAME_MAPPINGS` | `{}`（空） |

### 9.3 对正文"未确认"项的核对结论

| 正文位置 | 结论 |
|---|---|
| §2 注册表显示名"未确认" | 维持未确认（运行时映射为空，无法取得显示名） |
| §3.1 根目录 `ASSET_ROOT_NAME` 值推断 `"TE_MAN"` | 已确认（动态回填） |
| §3.2 `DEFAULT_PROJECT`/`TEXT_CATEGORY`/`AUDIO_CATEGORY` | 已确认（动态回填，见 9.2） |
| §3.2 `DEFAULT_CATEGORIES` 成员与顺序未确认 | 已确认：六项 `人物/产品/场景/背景/提示词/音频`（不含"未分类"） |
| §3.2 `PROTECTED_CATEGORIES` 后端精确成员 | 维持未确认（introspection 常量表中无此键） |
| §3.3 `TEXT_PREVIEW_MAX_CHARS` 数值未确认 | 已确认：220 |
| §3.3 `.jpg/.gif/.bmp` 图片后缀未确认 | 已确认（经 `IMAGE_CONTENT_TYPES` 间接实锤，六后缀齐） |
| §3.3 `.ogg/.aac/.wma` 音频后缀未确认 | 已确认（经 `AUDIO_CONTENT_TYPES` 实锤，八后缀齐） |
| §4 11 条路由 | 维持原结论（introspection 不覆盖 aiohttp 路由，无新证据） |
| §5 节点 INPUT_TYPES / RETURN 元组 | 维持未确认（运行时无节点注册，见 9.1） |
| §3.1 与 TE_3D_Director 的 `assets` 层级矛盾 | 维持未确认（需单独核验 TE_3D_Director，本模块数据不变） |
