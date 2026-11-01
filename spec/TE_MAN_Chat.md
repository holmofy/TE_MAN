# TE_MAN_Chat.pyd 逆向规格

> 来源：PE32+ x86-64, Cython 3.1.2 (abi3) 编译，`PyInit_TE_MAN_Chat`。静态分析（字符串 / 导入导出表 / 前端参照）。
> 置信度说明：[高] = 字符串直接证据；[中] = 强暗示推断；[低] = 猜测。

## 1. 模块定位

**不是 ComfyUI 节点，而是"TE MAN 构想台"（Idea Desk / AI 助手）的后端服务模块**：不提供任何画布节点，而是在 ComfyUI PromptServer 上注册 `/te_man/copilot/*` REST + SSE 路由，供前端 `web/js/te_man_chat.js` 的悬浮 AI 聊天面板调用。核心职责：多供应商/多请求格式的大模型调用路由（OpenAI Chat、Codex Responses、Claude、Gemini、LM Studio）、多话题会话持久化（SQLite）、图片附件管理、Skill 执行器。

前导源文件路径：`F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_MAN_Chat.c`（源包名 `custom_nodes.TE_image.TE_MAN_Chat`）[高]。

## 2. Python API

- 导出：`PyInit_TE_MAN_Chat` [高]。
- ComfyUI 节点注册：二进制中存在 `NODE_CLASS_MAPPINGS` / `NODE_DISPLAY_NAME_MAPPINGS` 字符串，但**不存在** `INPUT_TYPES`、`RETURN_TYPES`、`CATEGORY`、`FUNCTION` 等节点特征字符串 → 推断仅导出空映射（模块无节点），未确认是否为空或仅作兼容占位 [中]。
- 模块级函数（按 Cython 限定名还原，全部 [高]，名称来自 `custom_nodes.TE_image.TE_MAN_Chat.<fn>` 字符串表）：
  - Skill 系统：`_read_text_file`、`_parse_skill_frontmatter`、`_read_skill_meta_value`、`_list_skill_references`、`_discover_skills`、`_normalize_skill_id`、`_get_skill`、`_read_skill_body`、`_read_skill_reference`、`_build_skill_system_prompt`、`_parse_skill_reply`
  - 配置：`_read_config`、`_ensure_config_section`、`_sanitize_api_key`、`_mask_api_key`、`_normalize_temperature`、`_normalize_history_limit`、`_normalize_request_format`、`_normalize_provider_id`、`_provider_from_legacy`、`_normalize_stored_provider`、`_read_provider_config`、`_public_provider`、`_read_copilot_settings`、`_write_copilot_settings`
  - 会话持久化：`_chat_now_ms`、`_chat_db_connection`、`_init_chat_database`、`_load_chat_json`、`_save_chat_json`、`_as_int_ms`、`_as_bool`、`_normalize_chat_message`、`_normalize_skill_options`、`_normalize_skill_state`、`_normalize_chat_session`、`_read_chat_workspace`、`_save_chat_workspace_meta`、`_attachment_ids_from_messages`、`_remove_attachment_files`、`_upsert_chat_session`、`_delete_chat_session`、`_turn_key`
  - 请求构造/路由：`_resolve_provider_settings`、`_remove_known_endpoint_suffix`、`_resolve_chat_completions_url`、`_resolve_responses_url`、`_resolve_claude_messages_url`、`_resolve_lm_studio_chat_url`、`_resolve_gemini_stream_url`、`_resolve_endpoint`、`_mask_url_for_log`、`_safe_text`、`_build_chat_messages`、`_build_request_payload`、`_build_headers`、`_extract_delta_text`、`_iter_stream_json`、`_request_stream_text`、`_parse_json_object`
  - 附件：`_attachment_url`、`_attachment_path`、`_normalize_chat_attachments`、`_read_attachment_data`、`_message_attachments`、`_save_chat_attachment`
  - 会话编排：`_normalize_history`、`_messages_without_system`、`_limit_history_attachments`、`_send_event`、`_remove_turn`、`_run_copilot_turn`、`_cancel_turn`、`_json_error`
  - 路由注册：`_register_routes`、`_register_routes_when_ready`（内部 `_wait_for_server`）
- 模块级常量（名称）：`ROUTE_PREFIX`、`SKILLS_DIR`、`SKILL.md` / `SKILL.cn.md` 文件名、`SKILL_STATE_PATTERN`、`SKILL_EXECUTION_PROTOCOL`、`DEFAULT_SYSTEM_PROMPT`、`DEFAULT_MODEL`、`DEFAULT_REQUEST_FORMAT`、`DEFAULT_TEMPERATURE`、`DEFAULT_HISTORY_LIMIT`、`DEFAULT_*`（value 均 [中] 语义，具体数值不可见）、`REQUEST_FORMATS`、`MAX_PROVIDERS`、`MAX_ATTACHMENTS_PER_MESSAGE`、`MAX_ATTACHMENT_UPLOAD_BYTES`、`MAX_HISTORY_ATTACHMENTS`、`PLACEHOLDER_API_KEYS`、`CHAT_DB_PATH`、`CHAT_ATTACHMENT_DIR`、`DATA_DIR`、`PLUGIN_DIR`、`MODULE_DIR`、`CONFIG_PATH`、`CONFIG_SECTION`、`_CHAT_DB_LOCK`、`_TURN_LOCK`、`_ACTIVE_TURNS`、`_ROUTES_REGISTERED`、`_ROUTE_REGISTER_THREAD_STARTED`（全部 [高] 名称）。
- 引用同插件明文/内部库：导入 `image_codec` 模块并调用 `encode_pil_image_to_api_bytes` [高]（README 声明 image_codec 为内部支撑库）。

## 3. 内部接口（服务端路由）

路由前缀 `ROUTE_PREFIX = "/te_man/copilot"` [高]；完整路径由前端混淆 JS 确认 [高]。
启动方式：导入时若 `PromptServer` 尚未就绪，启动 daemon 线程 `TEManIdeaDeskRouteRegister` 轮询等待（`_wait_for_server`）；超时警告文案 [高]：`TE MAN 构想台路由未注册：PromptServer 尚未就绪` / `TE MAN 构想台路由注册超时：PromptServer 未就绪`，注册成功后 `TE MAN 构想台路由已注册`。

| 路由 | 处理函数（`_register_routes.<locals>.<fn>`） | 推断行为 |
|---|---|---|
| `/te_man/copilot/bootstrap` | `te_man_copilot_bootstrap` | 面板启动一次性拉取：供应商设置（脱敏）、可用 Skill 列表、工作区会话列表/当前话题 [中] |
| `/te_man/copilot/settings` GET/POST | `te_man_copilot_get_settings` / `te_man_copilot_save_settings` | 读/写 `config_IdeaDesk.ini` 的供应商设置，保存时校验"请填写 Gemini 模型名称"[高] |
| `/te_man/copilot/skills` | `te_man_copilot_skills` | 枚举 `SKILLS_DIR`（`TE_image/skills`）下的 Skill 元数据 [高] |
| `/te_man/copilot/workspace` | `te_man_copilot_workspace` | 读取会话树 + 消息 + `workspace_state`（前端自定义状态存 kv_store）[中] |
| `/te_man/copilot/workspace/meta` | `te_man_copilot_workspace_meta` | 保存 `{currentSessionId, workspace_meta, workspace_state}` 类前端元数据 [中] |
| `/te_man/copilot/topic/upsert` | `te_man_copilot_topic_upsert` | 创建/更新话题（sessions 表 upsert）[高] |
| `/te_man/copilot/topic/delete` | `te_man_copilot_topic_delete` | 删除话题 + 级联删除消息与图片附件文件 [高] |
| `/te_man/copilot/turn` | `te_man_copilot_turn` | 发起一轮对话（异步流式，见 §3.3）[高] |
| `/te_man/copilot/stop` | `te_man_copilot_stop` | 取消进行中的 turn（`_cancel_turn`、`"cancelled"`）[高] |
| `/te_man/copilot/attachment` POST | `te_man_copilot_upload_attachment` | multipart 上传图片（`json_fields`/`FileReader`）→ 存 `te_man_idea_desk_attachments` 目录 [高] |
| `/te_man/copilot/attachment/{attachment_id}` GET | `te_man_copilot_get_attachment` | `FileResponse` 返回图片，`Cache-Control: private, max-age=86400` [高] |

请求校验（[高] 文案）：`请求内容必须是 JSON 对象`、`缺少 panel_id`、`未配置有效的 API URL`、`选择的供应商不存在，请重新打开构想台设置并保存`。

### 3.1 后端路由逻辑（多请求格式）

`REQUEST_FORMATS` 覆盖 5 种请求格式（每种都有独立的 URL 解析函数 + 消息转换函数，全部 [高]）：

| request_format | 端点解析 | 消息转换 | 网络/流式细节 |
|---|---|---|---|
| `openai_chat`（key 近似 `chat_completions`） | 基地址去已知后缀后拼 `/v1/chat/completions`（`_resolve_chat_completions_url`；后缀列表含 `/v1/chat/completions`、`/chat/completions`、`/v1/responses`、`/v1/messages`、`/api/v1/chat`、`/v1beta/models/…`、`/v1/images/edits`、`/v1/images/generations` 等 `_remove_known_endpoint_suffix`） | `_message_to_openai_chat`（`image_url` 型 content） | SSE：`data:` 行 + 终止哨兵 `[DONE]`，`choices[].delta` |
| `codex`（OpenAI Responses，显示名 `Codex /v1/responses`） | `_resolve_responses_url` → `/v1/responses` | `_message_to_responses`（`input` / `input_text` / `input_image`、`instructions`） | 事件 `response.output_text.delta` / `output_text` |
| `claude`（`Claude /v1/messages`） | `_resolve_claude_messages_url` → `/v1/messages` | `_message_to_claude`（`content_block_delta`） | SSE `event:` / `content_block_delta`；头 `x-api-key` + `anthropic-version` + `anthropic`（版本值 `2023-06-01` [中]，与该字符串相邻） |
| `gemini`（`Gemini /v1beta/models/{model}:streamGenerateContent`） | `_resolve_gemini_stream_url` → `/v1beta/models/{model}:streamGenerateContent?alt=sse&key=…` [高]；正则 `/v1beta/models/[^/]+:(?:streamGenerateContent\|generateContent)$` 兼容用户自填完整端点 | `_message_to_gemini`（`contents`/`parts`/`inlineData:{"mimeType","data"}` base64，`systemInstruction`，`generationConfig`） | 回复解析 `candidates/candidate`；URL 日志脱敏正则 `([?&](?:key\|api_key)=)([^&]+)` → `\1***` |
| `lmstudio`（`LM Studio /api/v1/chat`） | `_resolve_lm_studio_chat_url` → `/api/v1/chat`（`is_lm_studio` 标志） | `_build_lm_studio_input`（纯文本 input） | **不支持图片**：`LM Studio /api/v1/chat 当前只支持文本，请改用 OpenAI Chat 格式的视觉模型接口` [高] |

- 认证：`_build_headers` 依格式设置 `Authorization: Bearer ` / `x-api-key` / 或把 key 放 Gemini 查询串 [高]。
- 传输：Python `requests` + `iter_lines`/`raise_for_status`（[高]，伴随串），SSE 判断 `is_sse`，Gemini `streamGenerateContent` 兼容非 SSE 的 JSON 分块缓冲（`json_buffer`）[中]。
- 回退：供应商可配 `fallback_model`（key 名 [高]，语义为请求失败时换模型重试，见日志 `retry:` [中]）。
- 图片编码：附件经 `image_codec.encode_pil_image_to_api_bytes`（PIL `ImageOps.exif_transpose`，白色填充 `ffffff` [低]）转字节再 base64/inline。
- **关于"CLIP / 本地 llama.cpp"路由：本 pyd 中不存在 clip / llama / gguf / qwen 字符串** —— 那类多后端属于 MOSS/Qwen 增强节点（README §v4.1、§TE_Qwen），构想台只有上述 5 种 HTTP 请求格式；"本地"仅以 LM Studio（本地 HTTP 服务）与各家 OpenAI 兼容自建端点形式出现 [高：字符串缺席 + 逻辑自洽]。

### 3.2 会话管理

- 存储：SQLite，`CHAT_DB_PATH = te_man_idea_desk.db`，目录 `DATA_DIR`；启用 `PRAGMA journal_mode=WAL`、`PRAGMA foreign_keys=ON`；线程锁 `_CHAT_DB_LOCK`（RLock）[高]。
- 表结构（DDL 全文在二进制中，[高]）：
  - `sessions(id, title, system_prompt, skill_state, auto_title, created_at, updated_at)`；索引 `idx_te_man_sessions_updated`
  - `messages(id, session_id, sort_order, role, text, attachments_json, tone, hidden, created_at)`，外键 `ON DELETE CASCADE`；索引 `idx_te_man_messages_session_order`
  - `kv_store(key, value, updated_at)` — 存 `workspace_state` 等前端元数据（`SELECT value FROM kv_store WHERE key = ?` / upsert）
- 迁移：`ALTER TABLE sessions ADD COLUMN system_prompt/skill_state`、`ALTER TABLE messages ADD COLUMN attachments_json/hidden` + `PRAGMA table_info(...)` 探测 [高]（旧版 JSON 存量兼容：`_load_chat_json`/`_save_chat_json` [中]）。
- 话题（topic）= session：`_upsert_chat_session`（含 title/system_prompt/skill_state/autoTitle）、`_delete_chat_session`（删 `messages` 后再删会话并清理附件文件，失败文案 [高]）。每话题可设独立 system prompt（README 引证）。上限提示 `MAX_SESSIONS`/`MAX_MESSAGES_PER_SESSION` 仅见前端（36/80，`te_man_chat.js` [高]），后端数值未确认。
- 消息字段：`attachments_json`（附件 id 列表）、`tone`（未确认语义，疑似气泡样式/创作入口标识）、`hidden`（本地隐藏不发给模型 [中]）。
- 并发：`_ACTIVE_TURNS` 记录进行中的 turn，键 `_turn_key`（panel_id+会话），`_TURN_LOCK` 序列化写入；`/stop` 置 `"cancelled"`；同一会话多话题并行即"多话题并行"（README 引证）。生命周期事件（`send_sync`，前端 `api.addEventListener`）：
  `teman_copilot_turn_started` / `teman_copilot_text_delta` / `teman_copilot_turn_completed` / `teman_copilot_turn_failed`，另有 `message.delta`、`chat.end` 作为事件别名/负载键共存于二进制（确切分工未确认）[高 名称 / 低 语义]。

### 3.3 图片附件

- 每附件 id 须匹配 `^[a-f0-9]{32}$`（32 位 hex，uuid4().hex [中]）[高]。
- `MAX_ATTACHMENTS_PER_MESSAGE`（前端=4 [高] / 后端值未确认）、`MAX_ATTACHMENT_UPLOAD_BYTES`（前端与文案均为 20MB：`单张图片不能超过 20MB` [高]）、`MAX_HISTORY_ATTACHMENTS`（历史携带图片上限，数值未确认）。
- 允许类型 `_ATTACHMENT_EXTENSIONS`/`_ATTACHMENT_MIME_TYPES`：可见 `image/png`、`image/jpeg`（webp 等 [未确认]）。
- 保存目录 `te_man_idea_desk_attachments`；列表返回脱敏后的 `api_key_hint`/`has_api_key` [中]；删除会话时 `_remove_attachment_files` 清理（`TE MAN 构想台清理图片附件失败: ` [高]）。
- 错误文案 [高]：`图片附件为空，请重新上传后再发送`、`图片附件不存在，请重新上传后再发送`、`图片格式处理失败`、`无法读取图片文件: `。

### 3.4 Skill（话题级流程执行器）

- 目录：`SKILLS_DIR`（`TE_image/skills`，文案 [高]）。每个 Skill 目录含 `SKILL.md`（英文主体）/`SKILL.cn.md`（中文主体）/ `meta.yaml`（frontmatter：`display-name-zh:`、`summary-cn:`；仓库现存样例为两键）+ `references/` 子目录附件文档（仓库样例引证）。
- `_parse_skill_frontmatter` 用 `^([\w-]+):\s*(.*)$` 逐行解析；`_normalize_skill_id` 用 `[^a-zA-Z0-9_-]+` 清洗。
- 执行协议 `SKILL_EXECUTION_PROTOCOL` 系统提示（全文埋在二进制，[高]）：AI 以 `你是 TE MAN 构想台的 Skill 执行器` 开工，回复末尾必须附状态标记：
  `<te_man_skill_state>{"stage":"...","options":[...],"load_references":[],"final":true|false}</te_man_skill_state>`;
  引用文件按需加载（`load_references` → `_read_skill_reference` 把文件全文以 `===== reference: <名> =====` 追加回对话并让模型重答），路径越界保护文案 [高]：`Skill reference 路径超出 Skill 目录`；`Skill reference 不存在：` [高]。
- `_parse_skill_reply` 用 `SKILL_STATE_PATTERN = <te_man_skill_state>\s*(\{.*?\})\s*</te_man_skill_state>` 提取状态，流式播出时同步解析 `stage/options/final` 供 UI 门控（options 2–6 项相关字符串 [高]）。
- 状态提示文案 [高]：`Skill 已开启，请先在 Skill 设置中选择一个 Skill`、`选择的 Skill 已不存在，请重新打开 Skill 设置`、`没有发现可用 Skill，请把 Skill 安装到 TE_image/skills 目录`、`已加载 references：`、`可用 references：`、`当前 Skill：`。

### 3.5 请求格式选择的核心提示词

- `DEFAULT_SYSTEM_PROMPT`（模块字符串合并还原，[高]）：`你是 TE MAN 构想台，一个专注 ComfyUI 提示词创作和工作流设计的中文助手…`（前端 `te_man_chat.js` 内嵌完整版：`…专注 ComfyUI、提示词创作的中文助手。可以帮助用户创作,也可以回答任何问题,回答要清晰、实用、直接。`）。
- 话题可覆盖 system_prompt（`CONFIG_KEY_SYSTEM_PROMPT` + sessions.system_prompt），`_build_chat_messages` 组装：system → 历史（`_normalize_history` 限条数及附件数）→ 本轮消息；system 与历史分离用 `_messages_without_system`。

## 4. 外部依赖与副作用

- **网络（出站）**：调用用户配置的大模型端点——OpenAI Chat `/v1/chat/completions`、Responses `/v1/responses`（README/字符串中带 `Codex` 称谓）、Claude `/v1/messages`、Gemini `/v1beta/models/{model}:streamGenerateContent`、LM Studio `http://localhost:1234` 类 `/api/v1/chat` [高（端点串）/中（密码学细节）]。默认模型 `DEFAULT_MODEL`：二进制邻近出现 `gpt-5.6-sol`（推断为默认值 [中]，具体映射未确认）；日志格式 `…构想台: provider=…, endpoint=…, format=…, model=…` [高]。
- **网络（入站）**：在 PromptServer 注册 §3 路由（aiohttp，`rel_url`/`match_info`/`FileResponse`）[高]。
- **文件系统**：
  - `config_IdeaDesk.ini`（`CONFIG_PATH`，`CONFIG_SECTION=ideadesk` [中]）：键 `CONFIG_KEY_API_KEY / CONFIG_KEY_API_BASE_URL / CONFIG_KEY_MODEL / CONFIG_KEY_REQUEST_FORMAT / CONFIG_KEY_TEMPERATURE / CONFIG_KEY_HISTORY_LIMIT / CONFIG_KEY_SYSTEM_PROMPT / CONFIG_KEY_PROVIDERS / CONFIG_KEY_ACTIVE_PROVIDER_ID` [高]。多供应商（`_provider_from_legacy` 迁移旧单供应商键 → `providers_json`；上限 `MAX_PROVIDERS`，数值未确认）。
  - `TE_MAN_Chat` 附件目录 `te_man_idea_desk_attachments`；SQLite `te_man_idea_desk.db`。
- **配置脱敏**：`PLACEHOLDER_API_KEYS = {"your-api-key-here", "yourapikeyhere", "your_api_key_here"}`（[高]，实际为占位等效空）；`_public_provider` 返回 `api_key_hint`/`has_api_key` 而不发真实 key [中]。
- **第三方库**：`requests`（出站流式）、`aiohttp`（服务端）、`sqlite3`、`configparser`（`ConfigParser`/`has_section`/`add_section`/`interpolation`）、`PIL`（经 `image_codec`：`BytesIO`、`ImageOps`、`exif_transpose`、`interpolation`）、`base64`、`uuid4`、`urllib.parse`（quote）、`threading`（RLock/Thread）、`asyncio.coroutines`（Cython 协程顶层钩子）[高名称]。
- **导入表**：仅 `python3.dll`、`KERNEL32.dll`、`VCRUNTIME140.dll`、crt-runtime —— 自身无 WS2_32 直连，网络全部经由 Python 层库 [高]。
- **接收事件推送**：`PromptServer.send_sync`（`send_sync`+`routes` 字符串 [高]）。

## 5. 错误处理与用户可见文案

| 文案（原文） | 触发场景 |
|---|---|
| `请填写 Gemini 模型名称` / `配置 API URL` / `配置 API Key` [高] | 设置保存/发起请求前校验 |
| `未配置有效的 API URL` [高] | turn 无可用端点 |
| `请求内容必须是 JSON 对象` / `缺少 panel_id` [高] | 路由入参校验 |
| `选择的供应商不存在，请重新打开构想台设置并保存` [高] | active_provider_id 悬空 |
| `LM Studio /api/v1/chat 当前只支持文本，请改用 OpenAI Chat 格式的视觉模型接口` [高] | 给 lm_studio 格式发消息时带图 |
| `单张图片不能超过 20MB` / `图片附件为空，请重新上传后再发送` / `图片附件不存在，请重新上传后再发送` / `图片格式处理失败` / `无法读取图片文件: ` [高] | 附件上传与构造请求 |
| `TE MAN 构想台请求失败: ` [高] | 请求异常统一包装（`format_exc`/`traceback` 相邻） |
| `TE MAN 构想台路由未注册：PromptServer 尚未就绪` / `注册超时` / `已注册` [高] | 模块加载期 |
| `没有发现可用 Skill，请把 Skill 安装到 TE_image/skills 目录` [高] | skills 列表为空 |
| `Skill 已开启…` / `选择的 Skill 已不存在…` / `Skill reference 不存在：` / `Skill reference 路径超出 Skill 目录` [高] | Skill 编排 |
| `TE MAN 构想台清理图片附件失败: ` [高] | 删除会话时清理附件 IO 异常 |
| `请输入内容或添加图片` [高] | 空消息占位/校验 |
| `图片格式支持 …（系统已自动转换）` 类提示（`?ffffff`/`image.` 字符串碎片）[低] | 附件格式自动转换提示（语义未确认） |

## 6. 与 MOSS 节点的关系

- **直接关系：无。** 本 pyd 全量字符串中不存在 `MOSS`/`moss`/版式/框位相关词 [高：字符串缺席]；`TE_MAN_MOSS.pyd`（注册版式规划/边界框节点，见 README v4.x，其增强后端三线为 CLIP/本地 llama.cpp/API）与前端 `te_man_moss_box.js` 也没有 `te_man_copilot` 调用痕迹（grep 仅命中各自文件）。两者关系是**同插件的并列功能模块**：构想台是通用 AI 助手聊天面板；MOSS 节点是画布上的 layout 提示词生成/编辑节点，其 API 增强走自己的端点（README 明示为 OpenAI 兼容 `/responses` 特调接口），并不经构想台路由 [中：结构 + 前端无交叉引用]。
- README v3.8 "构想台 AI/AI助手" 描述的技术能力（OpenAI Chat/Responses/Gemini/Claude、图片对话、Skill、多供应商）与本模块字符串一一对应 [高]。
- 二者潜在的间接联系（如某些话题种 Skill 产出 MOSS 喂图提示词）属于前端工作流层面的可能性，无代码证据 [未确认]。

## 7. 证据附录

### 7.1 模块与命名（ASCII）
```
F:\ComfyUI_portable_TE_v260130\ComfyUI\custom_nodes\TE_image\source_py_backup\TE_MAN_Chat.c
custom_nodes/TE_image/source_py_backup/TE_MAN_Chat.py
custom_nodes.TE_image.TE_MAN_Chat.*   # ~90 个限定函数名（见 §2）
EXPORT: PyInit_TE_MAN_Chat
```

### 7.2 路由（_module 字符串 + te_man_chat.js 常量）
```
/te_man/copilot  /bootstrap  /settings  /skills  /workspace  /workspace/meta
/topic/upsert  /topic/delete  /turn  /stop  /attachment  /attachment/{attachment_id}
ROUTE_PREFIX  ROUTES_REGISTERED  TEManIdeaDeskRouteRegister
```
前端（`te_man_chat.js` 反混淆出的明文常量）：`ROUTE_BOOTSTRAP='/te_man/copilot/bootstrap'`、`ROUTE_SETTINGS=…/settings`、`ROUTE_TURN=…/turn`、`ROUTE_WORKSPACE_META=…/workspace/meta`、`ROUTE_TOPIC_UPSERT=…/topic/upsert`、`ROUTE_TOPIC_DELETE=…/topic/delete`、`ROUTE_SKILLS=…/skills`、`PANEL_ID='te-man-copilot-panel'`；`MAX_SESSIONS=0x24`(36)、`MAX_MESSAGES_PER_SESSION=0x50`(80)、`MAX_ATTACHMENTS_PER_MESSAGE=0x4`、`MAX_ATTACHMENT_UPLOAD_BYTES=0x14*0x400*0x400`(20MB)。

### 7.3 五种请求格式（ASCII）
```
OpenAI Chat /v1/chat/completions     Codex /v1/responses     Claude /v1/messages
LM Studio /api/v1/chat               Gemini /v1beta/models/模型名:streamGenerateContent
chat_completions  codex  claude  gemini  lmstudio  openai_chat  lm_studio
/v1/chat/completions  /v1/responses  /v1/messages  /api/v1/chat  /v1beta/models/
:streamGenerateContent  :generateContent$  alt=sse&key=  data:  [DONE]  event:
content_block_delta  response.output_text.delta  choices  candidates  contents  inlineData
Authorization=x-api-key  Bearer  anthropic-version  anthropic  2023-06-01  generationConfig
systemInstruction  instructions  input_text  input_image  image_url  output_text
```

### 7.4 会话/存储（ASCII）
```
te_man_idea_desk.db  PRAGMA journal_mode=WAL  PRAGMA foreign_keys=ON  PRAGMA table_info(sessions|messages)
CREATE TABLE IF NOT EXISTS kv_store(key,value,updated_at) / sessions(id,title,system_prompt,skill_state,auto_title,created_at,updated_at)
  / messages(id,session_id,sort_order,role,text,attachments_json,tone,hidden,created_at) FK ON DELETE CASCADE
idx_te_man_messages_session_order  idx_te_man_sessions_updated
ALTER TABLE sessions ADD COLUMN system_prompt/skill_state…  ALTER TABLE messages ADD COLUMN attachments_json/hidden…
INSERT INTO sessions … ON CONFLICT(id) DO UPDATE …    DELETE FROM sessions WHERE id = ?
workSpace 键: currentSessionId  workspace_state  workspace_meta  skillState  autoTitle  systemPrompt
```

### 7.5 Skill
```
SKILL_SKILLS 目录文案: 没有发现可用 Skill，请把 Skill 安装到 TE_image/skills 目录
文件: SKILL.md  SKILL.cn.md  meta.yaml  .yaml  references  ===== reference:  已加载 references：  可用 references：  当前 Skill：
frontmatter: display-name-zh  summary-cn  正则 ^([\w-]+):\s*(.*)$
协议片段:
  <te_man_skill_state>{"stage":"当前阶段","options":["选项1","选项2"],"load_references":[],"final":false}</te_man_skill_state>
  "你是 TE MAN 构想台的 Skill 执行器 严格遵循当前 Skill，并遵守以下交互协议：1. 只完成当前 Skill 能在文本对话中完成的工作…"
  "Skill 提到画布/联网工具或 Hub agent 时，不得声称已经执行；应输出对应方案提示词，或说明需要连接的 ComfyUI 节点"
  "2. 信息不足或到达确认门时，先提问并等待用户… 3. 回复正文之后必须追加一个状态标记… 5. Skill 要求读取 reference 时…必须先把相对路径写入 load_references…"
SKILL_STATE_PATTERN: <te_man_skill_state>\s*(\{.*?\})\s*</te_man_skill_state>
```

### 7.6 默认提示词 / 供应商
```
`你是 TE MAN 构想台，一个专注 ComfyUI 提示词创作和工作流设计的中文助手`（跨行碎段）
`请输入内容或添加图片`
gpt-5.6-sol   fallback_model   TEManIdeaDesk-（疑似标题/会话前缀）
PLACEHOLDER_API_KEYS: your-api-key-here / yourapikeyhere / your_api_key_here
config_IdeaDesk.ini  ideadesk  CONFIG_KEY_API_KEY/API_BASE_URL/MODEL/REQUEST_FORMAT/TEMPERATURE/HISTORY_LIMIT/SYSTEM_PROMPT/PROVIDERS/ACTIVE_PROVIDER_ID
```

### 7.7 与"本地 / CLIP / llama.cpp"路线的判别证据
二进制中不存在 `clip`、`llama`、`gguf`、`qwen`、`PE(提示词增强)` 等字符串（strings+UTF8 全文检索 0 命中），故构想台无 CLIP/本地 LLM 直连线路；README 中描述 CLIP/本地 llama.cpp 的段落属 MOSS 增强与 Qwen 增强节点，非本模块 [高]。

### 7.8 路由/事件名全量（ASCII 侧位聚类）
```
teman_copilot_turn_started  teman_copilot_text_delta  teman_copilot_turn_completed  teman_copilot_turn_failed
EVENT_TURN_STARTED/TEXT_DELTA/COMPLETED/FAILED  message.delta  chat.end  send_sync  routes
```
