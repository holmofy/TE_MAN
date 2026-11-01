# -*- coding: utf-8 -*-
"""te_man_open.shared.idea_desk —— TE MAN 构想台（Idea Desk）后端核心库。

逆向规格: spec/TE_MAN_Chat.md。

本模块对应原版 TE_MAN_Chat.pyd 的全部非路由逻辑：

- SQLite 会话库 ``te_man_idea_desk.db``（WAL + 外键级联，
  sessions / messages / kv_store 三表 + ALTER 迁移）
- 构想台配置 ``config_IdeaDesk.ini``（多供应商 providers_json，脱敏读取）
- 多后端 5 种 HTTP 请求格式（OpenAI Chat / Codex Responses / Claude /
  Gemini / LM Studio）：URL 解析、消息转换（含图片 inline/base64）、
  请求头与 SSE 流解析
- Skill 执行器（SKILL.md / meta.yaml / references 按需加载 +
  ``<te_man_skill_state>`` 状态协议）
- 图片附件管理（``te_man_idea_desk_attachments`` 目录）
- turn 编排（_ACTIVE_TURNS 注册表 + 取消旗标）

依赖约定：sqlite3 / json / re / base64 / threading 等标准库顶层导入；
aiohttp / requests / PIL / image_codec 一律惰性导入。
本文件不注册任何 ComfyUI 节点（原版即无节点），路由层见
nodes/TE_MAN_Chat.py。
"""

import base64
import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("te_man_open.idea_desk")

# ---------------------------------------------------------------------------
# 模块级常量（名称来自 spec/TE_MAN_Chat.md §2，均为 [高] 字符串证据）
# ---------------------------------------------------------------------------

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_DIR = os.path.dirname(MODULE_DIR)
DATA_DIR = MODULE_DIR
CONFIG_PATH = os.path.join(MODULE_DIR, "config_IdeaDesk.ini")
CONFIG_SECTION = "ideadesk"

ROUTE_PREFIX = "/te_man/copilot"

CHAT_DB_PATH = os.path.join(DATA_DIR, "te_man_idea_desk.db")
CHAT_ATTACHMENT_DIR = os.path.join(DATA_DIR, "te_man_idea_desk_attachments")

#: Skill 目录：优先包内 skills/，回退插件根目录 skills/（原版为 TE_image/skills）
_SKILL_DIR_CANDIDATES = [
    os.path.join(MODULE_DIR, "skills"),
    os.path.join(PLUGIN_DIR, "skills"),
]
SKILLS_DIR = next((p for p in _SKILL_DIR_CANDIDATES if os.path.isdir(p)), _SKILL_DIR_CANDIDATES[0])

SKILL_MD = "SKILL.md"
SKILL_CN_MD = "SKILL.cn.md"
SKILL_META = "meta.yaml"
SKILL_REFERENCES_DIR = "references"

SKILL_STATE_PATTERN = r"<te_man_skill_state>\s*(\{.*?\})\s*</te_man_skill_state>"
_SKILL_STATE_RE = re.compile(SKILL_STATE_PATTERN, re.DOTALL)
_SKILL_FRONTMATTER_RE = re.compile(r"^([\w-]+):\s*(.*)$")
_SKILL_ID_CLEAN_RE = re.compile(r"[^a-zA-Z0-9_-]+")

SKILL_EXECUTION_PROTOCOL = (
    "你是 TE MAN 构想台的 Skill 执行器 严格遵循当前 Skill，并遵守以下交互协议：\n"
    "1. 只完成当前 Skill 能在文本对话中完成的工作。"
    "Skill 提到画布/联网工具或 Hub agent 时，不得声称已经执行；应输出对应方案提示词，"
    "或说明需要连接的 ComfyUI 节点。\n"
    "2. 信息不足或到达确认门时，先提问并等待用户，再继续执行。\n"
    "3. 回复正文之后必须追加一个状态标记，格式：\n"
    '<te_man_skill_state>{"stage":"当前阶段","options":["选项1","选项2"],'
    '"load_references":[],"final":false}</te_man_skill_state>\n'
    "4. options 保持 2-6 项供用户快速选择；final=true 表示当前 Skill 已完成。\n"
    "5. Skill 要求读取 reference 时，必须先把相对路径写入 load_references，"
    "等待系统把 reference 全文追加回对话后再继续。\n"
    "（简化实现：以上协议为按 spec 碎片重组的等价文本，非逐字还原）"
)

DEFAULT_SYSTEM_PROMPT = (
    "你是 TE MAN 构想台，一个专注 ComfyUI、提示词创作的中文助手。"
    "可以帮助用户创作,也可以回答任何问题,回答要清晰、实用、直接。"
)
DEFAULT_MODEL = "gpt-5.6-sol"
DEFAULT_REQUEST_FORMAT = "responses"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_HISTORY_LIMIT = 24

#: 5 种请求格式 → 显示名（key 集合覆盖 spec §3.1 的 chat_completions/codex/claude/gemini/lmstudio）
REQUEST_FORMATS = {
    "responses": "Codex /v1/responses",
    "openai_chat": "OpenAI Chat /v1/chat/completions",
    "claude": "Claude /v1/messages",
    "gemini": "Gemini /v1beta/models/{model}:streamGenerateContent",
    "lmstudio": "LM Studio /api/v1/chat",
}

MAX_PROVIDERS = 12
MAX_ATTACHMENTS_PER_MESSAGE = 4
MAX_ATTACHMENT_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_HISTORY_ATTACHMENTS = 8
MAX_SKILL_ROUNDS = 3

PLACEHOLDER_API_KEYS = {"your-api-key-here", "yourapikeyhere", "your_api_key_here"}

ATTACHMENT_EXTENSIONS = {"png", "jpg"}
ATTACHMENT_MIME_TYPES = {"png": "image/png", "jpg": "image/jpeg"}
_ATTACHMENT_ID_RE = re.compile(r"^[a-f0-9]{32}$")

ANTHROPIC_VERSION = "2023-06-01"

CONFIG_KEY_API_KEY = "api_key"
CONFIG_KEY_API_BASE_URL = "api_base_url"
CONFIG_KEY_MODEL = "model"
CONFIG_KEY_REQUEST_FORMAT = "request_format"
CONFIG_KEY_TEMPERATURE = "temperature"
CONFIG_KEY_HISTORY_LIMIT = "history_limit"
CONFIG_KEY_SYSTEM_PROMPT = "system_prompt"
CONFIG_KEY_PROVIDERS = "providers_json"
CONFIG_KEY_ACTIVE_PROVIDER_ID = "active_provider_id"
CONFIG_KEY_FALLBACK_MODEL = "fallback_model"

_GEMINI_ENDPOINT_RE = re.compile(r"/v1beta/models/[^/]+:(?:streamGenerateContent|generateContent)$")
_GEMINI_KEY_MASK_RE = re.compile(r"([?&](?:key|api_key)=)([^&]+)")

_CHAT_DB_LOCK = threading.RLock()
_TURN_LOCK = threading.RLock()
_ACTIVE_TURNS: Dict[str, Dict[str, Any]] = {}

__all__ = [
    "ROUTE_PREFIX", "CHAT_DB_PATH", "CHAT_ATTACHMENT_DIR", "SKILLS_DIR",
    "REQUEST_FORMATS", "DEFAULT_SYSTEM_PROMPT", "DEFAULT_MODEL",
    "DEFAULT_REQUEST_FORMAT", "PLACEHOLDER_API_KEYS",
    "ChatStore", "get_chat_store",
    "read_copilot_settings", "public_settings_payload", "write_copilot_settings",
    "resolve_provider_settings", "run_copilot_turn", "cancel_turn",
    "turn_key", "save_chat_attachment", "attachment_path", "remove_attachment_files",
    "discover_skills", "get_skill", "read_skill_reference", "build_skill_system_prompt",
    "parse_skill_reply",
]


# ---------------------------------------------------------------------------
# 通用小工具
# ---------------------------------------------------------------------------

def _chat_now_ms() -> int:
    """当前毫秒时间戳。"""
    return int(time.time() * 1000)


def _safe_text(value: Any) -> str:
    """任意值 → 字符串（None/异常 → 空串）。"""
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:  # noqa: BLE001
        return ""


def _as_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def _as_int_ms(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _sanitize_api_key(value: Any) -> str:
    """占位等效空的 key 归一化为空串。"""
    key = _safe_text(value).strip()
    if not key or key in PLACEHOLDER_API_KEYS:
        return ""
    return key


def _mask_api_key(value: Any) -> str:
    """脱敏提示：前 4 后 4，中间省略。"""
    key = _sanitize_api_key(value)
    if not key:
        return ""
    if len(key) <= 8:
        return "****"
    return "{}****{}".format(key[:4], key[-4:])


def _mask_url_for_log(url: str) -> str:
    """日志用 URL 脱敏：Gemini 查询串 key/api_key → ***。"""
    return _GEMINI_KEY_MASK_RE.sub(r"\1***", _safe_text(url))


def _normalize_temperature(value: Any) -> float:
    try:
        temp = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TEMPERATURE
    return max(0.0, min(temp, 2.0))


def _normalize_history_limit(value: Any) -> int:
    try:
        limit = int(float(value))
    except (TypeError, ValueError):
        return DEFAULT_HISTORY_LIMIT
    return max(1, min(limit, 100))


_REQUEST_FORMAT_ALIASES = {
    "responses": "responses",
    "codex": "responses",
    "openai_chat": "openai_chat",
    "chat_completions": "openai_chat",
    "chat": "openai_chat",
    "openai": "openai_chat",
    "claude": "claude",
    "gemini": "gemini",
    "lmstudio": "lmstudio",
    "lm_studio": "lmstudio",
}


def _normalize_request_format(value: Any) -> str:
    fmt = _safe_text(value).strip().lower()
    return _REQUEST_FORMAT_ALIASES.get(fmt, DEFAULT_REQUEST_FORMAT)


def _normalize_provider_id(value: Any) -> str:
    pid = _safe_text(value).strip()
    if not pid:
        return ""
    return _SKILL_ID_CLEAN_RE.sub("_", pid)[:64] or ""


def _json_error_message(exc: Exception) -> str:
    """统一请求异常包装文案。"""
    return "TE MAN 构想台请求失败: {}".format(exc)


# ---------------------------------------------------------------------------
# SQLite 会话库（sessions / messages / kv_store，WAL + 外键级联）
# ---------------------------------------------------------------------------

_SESSION_DDL = (
    "CREATE TABLE IF NOT EXISTS sessions ("
    " id TEXT PRIMARY KEY,"
    " title TEXT NOT NULL DEFAULT '',"
    " system_prompt TEXT NOT NULL DEFAULT '',"
    " skill_state TEXT NOT NULL DEFAULT '',"
    " auto_title INTEGER NOT NULL DEFAULT 0,"
    " created_at INTEGER NOT NULL DEFAULT 0,"
    " updated_at INTEGER NOT NULL DEFAULT 0)",
    "CREATE INDEX IF NOT EXISTS idx_te_man_sessions_updated ON sessions(updated_at)",
    "CREATE TABLE IF NOT EXISTS messages ("
    " id TEXT PRIMARY KEY,"
    " session_id TEXT NOT NULL,"
    " sort_order INTEGER NOT NULL DEFAULT 0,"
    " role TEXT NOT NULL DEFAULT 'user',"
    " text TEXT NOT NULL DEFAULT '',"
    " attachments_json TEXT NOT NULL DEFAULT '[]',"
    " tone TEXT NOT NULL DEFAULT '',"
    " hidden INTEGER NOT NULL DEFAULT 0,"
    " created_at INTEGER NOT NULL DEFAULT 0,"
    " FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE)",
    "CREATE INDEX IF NOT EXISTS idx_te_man_messages_session_order ON messages(session_id, sort_order)",
    "CREATE TABLE IF NOT EXISTS kv_store ("
    " key TEXT PRIMARY KEY,"
    " value TEXT NOT NULL DEFAULT '',"
    " updated_at INTEGER NOT NULL DEFAULT 0)",
)

#: 旧库迁移：列探测 → ALTER TABLE（spec §3.2）
_MIGRATION_COLUMNS = {
    "sessions": [
        ("system_prompt", "TEXT NOT NULL DEFAULT ''"),
        ("skill_state", "TEXT NOT NULL DEFAULT ''"),
        ("auto_title", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "messages": [
        ("attachments_json", "TEXT NOT NULL DEFAULT '[]'"),
        ("tone", "TEXT NOT NULL DEFAULT ''"),
        ("hidden", "INTEGER NOT NULL DEFAULT 0"),
    ],
}


def _chat_db_connection() -> sqlite3.Connection:
    """新建 SQLite 连接（WAL + 外键开启）。"""
    conn = sqlite3.connect(CHAT_DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _init_chat_database(conn: sqlite3.Connection) -> None:
    """建表 + 索引 + PRAGMA table_info 列探测迁移。"""
    with conn:
        for ddl in _SESSION_DDL:
            conn.execute(ddl)
        for table, columns in _MIGRATION_COLUMNS.items():
            existing = {row["name"] for row in conn.execute("PRAGMA table_info({})".format(table))}
            for name, decl in columns:
                if name not in existing:
                    conn.execute("ALTER TABLE {} ADD COLUMN {} {}".format(table, name, decl))


class ChatStore:
    """构想台会话持久化（sessions/messages/kv_store 三表）。"""

    def __init__(self, db_path: str = CHAT_DB_PATH):
        self._path = db_path
        self._conn = _chat_db_connection()
        _init_chat_database(self._conn)

    # -- kv_store ---------------------------------------------------------

    def get_kv(self, key: str, default: Any = None) -> Any:
        with _CHAT_DB_LOCK:
            row = self._conn.execute(
                "SELECT value FROM kv_store WHERE key = ?", (key,)
            ).fetchone()
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (json.JSONDecodeError, TypeError):
            return row["value"]

    def set_kv(self, key: str, value: Any) -> None:
        payload = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        with _CHAT_DB_LOCK, self._conn:
            self._conn.execute(
                "INSERT INTO kv_store(key, value, updated_at) VALUES(?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (key, payload, _chat_now_ms()),
            )

    # -- sessions ---------------------------------------------------------

    def upsert_session(self, session: Dict[str, Any]) -> Dict[str, Any]:
        """创建/更新话题（含消息全量替换）。"""
        now = _chat_now_ms()
        session_id = _safe_text(session.get("id") or "").strip() or uuid.uuid4().hex
        title = _safe_text(session.get("title") or "").strip()
        system_prompt = _safe_text(session.get("systemPrompt") or session.get("system_prompt") or "")
        skill_state = session.get("skillState") or session.get("skill_state") or {}
        auto_title = 1 if _as_bool(session.get("autoTitle") or session.get("auto_title")) else 0
        created_at = _as_int_ms(session.get("createdAt") or session.get("created_at"), now)
        updated_at = _as_int_ms(session.get("updatedAt") or session.get("updated_at"), now)
        messages = session.get("messages") if isinstance(session.get("messages"), list) else []
        with _CHAT_DB_LOCK, self._conn:
            self._conn.execute(
                "INSERT INTO sessions(id, title, system_prompt, skill_state, auto_title, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET title = excluded.title,"
                " system_prompt = excluded.system_prompt, skill_state = excluded.skill_state,"
                " auto_title = excluded.auto_title, updated_at = excluded.updated_at",
                (session_id, title, system_prompt,
                 json.dumps(skill_state, ensure_ascii=False), auto_title, created_at, updated_at),
            )
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            for order, msg in enumerate(messages):
                if not isinstance(msg, dict):
                    continue
                message_id = _safe_text(msg.get("id") or "").strip() or uuid.uuid4().hex
                role = "assistant" if msg.get("role") == "assistant" else "user"
                attachments = msg.get("attachments")
                attachment_ids = _attachment_ids_from_payload(attachments)
                self._conn.execute(
                    "INSERT OR REPLACE INTO messages(id, session_id, sort_order, role, text,"
                    " attachments_json, tone, hidden, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (message_id, session_id, order, role, _safe_text(msg.get("text") or ""),
                     json.dumps(attachment_ids, ensure_ascii=False),
                     _safe_text(msg.get("tone") or ""), 1 if _as_bool(msg.get("hidden")) else 0,
                     _as_int_ms(msg.get("createdAt") or msg.get("created_at"), now)),
                )
        return {"id": session_id, "title": title, "updatedAt": updated_at}

    def delete_session(self, session_id: str) -> List[str]:
        """删除话题：先取附件 id，删 messages（级联由外键完成）再删会话，返回待清理附件。"""
        attachment_ids = self.session_attachment_ids(session_id)
        with _CHAT_DB_LOCK, self._conn:
            self._conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            self._conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        return attachment_ids

    def session_attachment_ids(self, session_id: str) -> List[str]:
        with _CHAT_DB_LOCK:
            rows = self._conn.execute(
                "SELECT attachments_json FROM messages WHERE session_id = ?", (session_id,)
            ).fetchall()
        ids: List[str] = []
        for row in rows:
            try:
                for aid in json.loads(row["attachments_json"] or "[]"):
                    if _ATTACHMENT_ID_RE.match(_safe_text(aid)) and aid not in ids:
                        ids.append(aid)
            except (json.JSONDecodeError, TypeError):
                continue
        return ids

    def load_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """单个会话（含消息，camelCase 输出，字段与前端 sessionPayload 一致）。"""
        with _CHAT_DB_LOCK:
            row = self._conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return None
            msg_rows = self._conn.execute(
                "SELECT * FROM messages WHERE session_id = ? ORDER BY sort_order ASC, created_at ASC",
                (session_id,),
            ).fetchall()
        return _session_row_to_payload(row, msg_rows)

    def list_sessions(self) -> List[Dict[str, Any]]:
        """全部会话（按 updated_at 倒序，含消息）。"""
        with _CHAT_DB_LOCK:
            session_rows = self._conn.execute(
                "SELECT * FROM sessions ORDER BY updated_at DESC"
            ).fetchall()
            result = []
            for row in session_rows:
                msg_rows = self._conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY sort_order ASC, created_at ASC",
                    (row["id"],),
                ).fetchall()
                result.append(_session_row_to_payload(row, msg_rows))
        return result

    def close(self) -> None:
        with _CHAT_DB_LOCK:
            try:
                self._conn.close()
            except Exception:  # noqa: BLE001
                pass


_STORE: Optional[ChatStore] = None
_STORE_LOCK = threading.Lock()


def get_chat_store() -> ChatStore:
    """进程内单例（线程安全初始化；DB 打不开时降级为每调用重试）。"""
    global _STORE
    if _STORE is None:
        with _STORE_LOCK:
            if _STORE is None:
                try:
                    _STORE = ChatStore()
                except sqlite3.Error as exc:
                    logger.error("TE MAN 构想台会话库初始化失败: %s", exc)
                    raise
    return _STORE


def _session_row_to_payload(row: sqlite3.Row, msg_rows: List[sqlite3.Row]) -> Dict[str, Any]:
    try:
        skill_state = json.loads(row["skill_state"] or "{}")
    except (json.JSONDecodeError, TypeError):
        skill_state = {}
    if not isinstance(skill_state, dict):
        skill_state = {}
    messages = []
    for m in msg_rows:
        try:
            attachments = json.loads(m["attachments_json"] or "[]")
        except (json.JSONDecodeError, TypeError):
            attachments = []
        messages.append({
            "id": m["id"],
            "role": m["role"],
            "text": m["text"] or "",
            "attachments": attachments if isinstance(attachments, list) else [],
            "tone": m["tone"] or "",
            "hidden": bool(m["hidden"]),
            "createdAt": m["created_at"],
        })
    return {
        "id": row["id"],
        "title": row["title"] or "",
        "autoTitle": bool(row["auto_title"]),
        "systemPrompt": row["system_prompt"] or "",
        "skillState": skill_state,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "messages": messages,
    }


def _attachment_ids_from_payload(attachments: Any) -> List[str]:
    """前端 attachments 数组 → 附件 id 列表（去重、合法 id 过滤）。"""
    ids: List[str] = []
    if not isinstance(attachments, list):
        return ids
    for item in attachments:
        aid = _safe_text(item.get("id") if isinstance(item, dict) else item).strip()
        if _ATTACHMENT_ID_RE.match(aid) and aid not in ids:
            ids.append(aid)
    return ids


# ---------------------------------------------------------------------------
# 构想台配置（config_IdeaDesk.ini [ideadesk]）
# ---------------------------------------------------------------------------

def _read_config() -> "configparser.ConfigParser":  # type: ignore[name-defined]
    import configparser

    parser = configparser.ConfigParser(interpolation=None)
    parser.read(CONFIG_PATH, encoding="utf-8")
    return parser


def _ensure_config_section(parser) -> None:
    if not parser.has_section(CONFIG_SECTION):
        parser.add_section(CONFIG_SECTION)


def _provider_from_legacy(section) -> Optional[Dict[str, Any]]:
    """旧单供应商键（api_key/api_base_url/...）→ provider dict。"""
    api_key = _sanitize_api_key(section.get(CONFIG_KEY_API_KEY, fallback=""))
    base_url = _safe_text(section.get(CONFIG_KEY_API_BASE_URL, fallback="")).strip()
    model = _safe_text(section.get(CONFIG_KEY_MODEL, fallback="")).strip()
    if not (api_key or base_url or model):
        return None
    return {
        "id": "default",
        "name": "默认供应商",
        "api_base_url": base_url,
        "api_key": api_key,
        "request_format": _normalize_request_format(section.get(CONFIG_KEY_REQUEST_FORMAT, fallback="")),
        "model": model,
        "fallback_model": _safe_text(section.get(CONFIG_KEY_FALLBACK_MODEL, fallback="")).strip(),
    }


def _normalize_stored_provider(raw: Any, index: int) -> Optional[Dict[str, Any]]:
    if not isinstance(raw, dict):
        return None
    base_url = _safe_text(raw.get("api_base_url") or raw.get("apiBaseUrl") or "").strip()
    provider = {
        "id": _normalize_provider_id(raw.get("id")) or "provider_{}".format(index + 1),
        "name": _safe_text(raw.get("name") or "").strip() or "未命名供应商",
        "api_base_url": base_url,
        "api_key": _sanitize_api_key(raw.get("api_key") or raw.get("apiKey")),
        "request_format": _normalize_request_format(raw.get("request_format") or raw.get("requestFormat")),
        "model": _safe_text(raw.get("model") or "").strip(),
        "fallback_model": _safe_text(raw.get("fallback_model") or raw.get("fallbackModel") or "").strip(),
    }
    return provider


def read_copilot_settings() -> Dict[str, Any]:
    """读取构想台设置（含旧键迁移，返回内部含明文 key 的 dict）。"""
    parser = _read_config()
    if not parser.has_section(CONFIG_SECTION):
        return {"providers": [], "active_provider_id": "", "temperature": DEFAULT_TEMPERATURE,
                "history_limit": DEFAULT_HISTORY_LIMIT, "system_prompt": "", "model": DEFAULT_MODEL}
    section = parser[CONFIG_SECTION]
    providers: List[Dict[str, Any]] = []
    raw_json = _safe_text(section.get(CONFIG_KEY_PROVIDERS, fallback="")).strip()
    if raw_json:
        try:
            raw_list = json.loads(raw_json)
            if isinstance(raw_list, list):
                for i, raw in enumerate(raw_list[:MAX_PROVIDERS]):
                    provider = _normalize_stored_provider(raw, i)
                    if provider:
                        providers.append(provider)
        except json.JSONDecodeError:
            logger.warning("TE MAN 构想台 providers_json 解析失败，忽略")
    if not providers:
        legacy = _provider_from_legacy(section)
        if legacy:
            providers.append(legacy)
    active_id = _normalize_provider_id(section.get(CONFIG_KEY_ACTIVE_PROVIDER_ID, fallback=""))
    if providers and not any(p["id"] == active_id for p in providers):
        active_id = providers[0]["id"]
    return {
        "providers": providers,
        "active_provider_id": active_id,
        "model": _safe_text(section.get(CONFIG_KEY_MODEL, fallback="")).strip() or DEFAULT_MODEL,
        "system_prompt": _safe_text(section.get(CONFIG_KEY_SYSTEM_PROMPT, fallback="")),
        "temperature": _normalize_temperature(section.get(CONFIG_KEY_TEMPERATURE, fallback="")),
        "history_limit": _normalize_history_limit(section.get(CONFIG_KEY_HISTORY_LIMIT, fallback="")),
    }


def _public_provider(provider: Dict[str, Any]) -> Dict[str, Any]:
    """供应商脱敏视图：只回 api_key_hint / has_api_key，不发真实 key。"""
    key = _sanitize_api_key(provider.get("api_key"))
    return {
        "id": provider["id"],
        "name": provider["name"],
        "api_base_url": provider.get("api_base_url", ""),
        "request_format": provider.get("request_format", DEFAULT_REQUEST_FORMAT),
        "model": provider.get("model", ""),
        "fallback_model": provider.get("fallback_model", ""),
        "api_key_hint": _mask_api_key(key),
        "has_api_key": bool(key),
    }


def public_settings_payload(settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """GET /settings 与 bootstrap 的公共设置区（脱敏）。"""
    settings = settings or read_copilot_settings()
    return {
        "model": settings.get("model") or DEFAULT_MODEL,
        "default_model": DEFAULT_MODEL,
        "request_formats": dict(REQUEST_FORMATS),
        "default_request_format": DEFAULT_REQUEST_FORMAT,
        "providers": [_public_provider(p) for p in settings.get("providers", [])],
        "active_provider_id": settings.get("active_provider_id", ""),
        "system_prompt": settings.get("system_prompt", ""),
        "temperature": settings.get("temperature", DEFAULT_TEMPERATURE),
        "history_limit": settings.get("history_limit", DEFAULT_HISTORY_LIMIT),
    }


def write_copilot_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    """保存构想台设置。校验失败抛 ValueError（文案见 spec §5）。"""
    import configparser

    providers_raw = payload.get("providers")
    providers: List[Dict[str, Any]] = []
    if isinstance(providers_raw, list):
        for i, raw in enumerate(providers_raw[:MAX_PROVIDERS]):
            provider = _normalize_stored_provider(raw, i)
            if provider:
                # 保存时前端可能不回传 key（只回 hint）：保留已存 key
                existing = read_copilot_settings()
                old = next((p for p in existing["providers"] if p["id"] == provider["id"]), None)
                if not provider["api_key"] and old:
                    provider["api_key"] = old["api_key"]
                providers.append(provider)
    if not providers:
        raise ValueError("至少需要保存一个供应商")

    active_id = _normalize_provider_id(payload.get("active_provider_id"))
    if not any(p["id"] == active_id for p in providers):
        active_id = providers[0]["id"]

    # Gemini 供应商必须填模型名（spec §3 校验文案）
    for provider in providers:
        if provider["request_format"] == "gemini" and not provider["model"]:
            raise ValueError("请填写 Gemini 模型名称")

    settings = {
        "providers": providers,
        "active_provider_id": active_id,
        "model": _safe_text(payload.get("model") or "").strip() or DEFAULT_MODEL,
        "system_prompt": _safe_text(payload.get("system_prompt") or ""),
        "temperature": _normalize_temperature(payload.get("temperature")),
        "history_limit": _normalize_history_limit(payload.get("history_limit")),
    }

    parser = _read_config()
    _ensure_config_section(parser)
    section = parser[CONFIG_SECTION]
    section[CONFIG_KEY_PROVIDERS] = json.dumps(
        [{**p} for p in providers], ensure_ascii=False)
    section[CONFIG_KEY_ACTIVE_PROVIDER_ID] = active_id
    section[CONFIG_KEY_MODEL] = settings["model"]
    section[CONFIG_KEY_SYSTEM_PROMPT] = settings["system_prompt"]
    section[CONFIG_KEY_TEMPERATURE] = str(settings["temperature"])
    section[CONFIG_KEY_HISTORY_LIMIT] = str(settings["history_limit"])
    # 旧单供应商键同步（向后兼容读取方）
    first = providers[0]
    section[CONFIG_KEY_API_KEY] = first.get("api_key", "")
    section[CONFIG_KEY_API_BASE_URL] = first.get("api_base_url", "")
    section[CONFIG_KEY_REQUEST_FORMAT] = first.get("request_format", DEFAULT_REQUEST_FORMAT)
    with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
        parser.write(fh)
    return settings


def resolve_provider_settings(payload: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """turn 请求 → (provider, settings)。

    校验顺序与文案（spec §5）：未配置有效的 API URL /
    选择的供应商不存在，请重新打开构想台设置并保存。
    """
    settings = read_copilot_settings()
    providers = settings["providers"]
    if not providers:
        raise ValueError("未配置有效的 API URL")
    provider_id = _safe_text(payload.get("provider_id") or "").strip()
    provider = None
    if provider_id:
        provider = next((p for p in providers if p["id"] == provider_id), None)
        if provider is None:
            raise ValueError("选择的供应商不存在，请重新打开构想台设置并保存")
    else:
        provider = next(
            (p for p in providers if p["id"] == settings["active_provider_id"]), None) or providers[0]
    if not _safe_text(provider.get("api_base_url")).strip():
        raise ValueError("未配置有效的 API URL")
    return provider, settings


# ---------------------------------------------------------------------------
# 端点解析（5 种请求格式，spec §3.1）
# ---------------------------------------------------------------------------

_KNOWN_ENDPOINT_SUFFIXES = (
    "/v1/chat/completions", "/chat/completions", "/v1/responses", "/responses",
    "/v1/messages", "/messages", "/api/v1/chat", "/v1beta", "/v1/images/edits",
    "/v1/images/generations",
)


def _remove_known_endpoint_suffix(base_url: str) -> str:
    """基地址去已知端点后缀（容错用户把完整端点填进 api_base_url）。"""
    url = _safe_text(base_url).strip().rstrip("/")
    changed = True
    while changed:
        changed = False
        lower = url.lower()
        for suffix in _KNOWN_ENDPOINT_SUFFIXES:
            if lower.endswith(suffix):
                url = url[: -len(suffix)].rstrip("/")
                changed = True
                break
    return url


def _join_url(base: str, path: str) -> str:
    return "{}{}".format(base.rstrip("/"), path)


def _resolve_chat_completions_url(base_url: str) -> str:
    return _join_url(_remove_known_endpoint_suffix(base_url), "/v1/chat/completions")


def _resolve_responses_url(base_url: str) -> str:
    return _join_url(_remove_known_endpoint_suffix(base_url), "/v1/responses")


def _resolve_claude_messages_url(base_url: str) -> str:
    return _join_url(_remove_known_endpoint_suffix(base_url), "/v1/messages")


def _resolve_lm_studio_chat_url(base_url: str) -> str:
    return _join_url(_remove_known_endpoint_suffix(base_url), "/api/v1/chat")


def _resolve_gemini_stream_url(base_url: str, model: str) -> str:
    raw = _safe_text(base_url).strip()
    if _GEMINI_ENDPOINT_RE.search(raw.rstrip("/")):
        url = raw.rstrip("/")
        if ":generateContent" in url:
            url = url.replace(":generateContent", ":streamGenerateContent")
    else:
        model_name = _safe_text(model).strip() or DEFAULT_MODEL
        url = _join_url(_remove_known_endpoint_suffix(raw), "/v1beta/models/{}:streamGenerateContent".format(model_name))
    return url


def resolve_endpoint(request_format: str, base_url: str, model: str, api_key: str) -> str:
    """统一端点解析入口。"""
    fmt = _normalize_request_format(request_format)
    if fmt == "openai_chat":
        return _resolve_chat_completions_url(base_url)
    if fmt == "responses":
        return _resolve_responses_url(base_url)
    if fmt == "claude":
        return _resolve_claude_messages_url(base_url)
    if fmt == "lmstudio":
        return _resolve_lm_studio_chat_url(base_url)
    if fmt == "gemini":
        url = _resolve_gemini_stream_url(base_url, model)
        key = _sanitize_api_key(api_key)
        if key:
            url = "{}{}alt=sse&key={}".format(url, "&" if "?" in url else "?", key)
        else:
            url = "{}{}alt=sse".format(url, "&" if "?" in url else "?")
        return url
    raise ValueError("未知的请求格式: {}".format(request_format))


def build_headers(request_format: str, api_key: str) -> Dict[str, str]:
    """按格式设置认证头（Gemini 走查询串，不设头）。"""
    fmt = _normalize_request_format(request_format)
    key = _sanitize_api_key(api_key)
    headers = {"Content-Type": "application/json"}
    if fmt == "claude":
        if key:
            headers["x-api-key"] = key
        headers["anthropic-version"] = ANTHROPIC_VERSION
    elif fmt != "gemini":
        if key:
            headers["Authorization"] = "Bearer {}".format(key)
    return headers


# ---------------------------------------------------------------------------
# 消息转换（含图片附件 → 各格式 inline/base64）
# ---------------------------------------------------------------------------

def _read_attachment_data(attachment: Any) -> Tuple[str, bytes]:
    """附件 id → (mime, bytes)。非法/缺失按 spec §5 文案报错。"""
    aid = _safe_text(attachment.get("id") if isinstance(attachment, dict) else attachment).strip()
    ext = _safe_text(attachment.get("extension") if isinstance(attachment, dict) else "").strip().lstrip(".").lower()
    if not _ATTACHMENT_ID_RE.match(aid) or ext not in ATTACHMENT_EXTENSIONS:
        raise ValueError("图片格式处理失败")
    path = os.path.join(CHAT_ATTACHMENT_DIR, "{}.{}".format(aid, ext))
    if not os.path.isfile(path):
        raise ValueError("图片附件不存在，请重新上传后再发送")
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except OSError as exc:
        raise ValueError("无法读取图片文件: {}".format(exc)) from exc
    if not data:
        raise ValueError("图片附件为空，请重新上传后再发送")
    return ATTACHMENT_MIME_TYPES[ext], data


def _attachment_b64(attachment: Any) -> Tuple[str, str]:
    """附件 → (mime, base64)。"""
    mime, data = _read_attachment_data(attachment)
    return mime, base64.b64encode(data).decode("ascii")


def _message_image_count(attachments: Any) -> int:
    return len(attachments) if isinstance(attachments, list) else 0


def _build_chat_messages(
    request_format: str,
    system_text: str,
    history: List[Dict[str, Any]],
    user_text: str,
    user_attachments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """统一消息装配 → 各格式请求体所需结构。

    返回 dict：
    - openai_chat / lmstudio: {"system": str|None, "messages": [...]}
    - responses: {"instructions": str, "input": [...]}
    - claude: {"system": str, "messages": [...]}
    - gemini: {"systemInstruction": {...}|None, "contents": [...]}
    """
    fmt = _normalize_request_format(request_format)
    history = _normalize_history(history)
    if fmt == "lmstudio" and any(_message_image_count(h.get("attachments")) for h in history):
        raise ValueError("LM Studio /api/v1/chat 当前只支持文本，请改用 OpenAI Chat 格式的视觉模型接口")
    if fmt == "lmstudio" and user_attachments:
        raise ValueError("LM Studio /api/v1/chat 当前只支持文本，请改用 OpenAI Chat 格式的视觉模型接口")

    if fmt in ("openai_chat", "lmstudio"):
        messages: List[Dict[str, Any]] = []
        if fmt == "openai_chat":
            if system_text:
                messages.append({"role": "system", "content": system_text})
        elif system_text:
            messages.append({"role": "system", "content": system_text})
        for msg in history:
            messages.append(_message_to_openai_chat(
                msg.get("role") or "user", _safe_text(msg.get("text") or ""),
                msg.get("attachments") or []))
        messages.append(_message_to_openai_chat("user", user_text, user_attachments))
        return {"messages": messages}

    if fmt == "responses":
        input_items = [
            _message_to_responses(m.get("role") or "user", _safe_text(m.get("text") or ""),
                                  m.get("attachments") or [])
            for m in history
        ]
        input_items.append(_message_to_responses("user", user_text, user_attachments))
        return {"instructions": system_text, "input": input_items}

    if fmt == "claude":
        messages = [
            _message_to_claude(m.get("role") or "user", _safe_text(m.get("text") or ""),
                               m.get("attachments") or [])
            for m in history
        ]
        messages.append(_message_to_claude("user", user_text, user_attachments))
        return {"system": system_text, "messages": messages}

    if fmt == "gemini":
        contents = [
            _message_to_gemini(m.get("role") or "user", _safe_text(m.get("text") or ""),
                               m.get("attachments") or [])
            for m in history
        ]
        contents.append(_message_to_gemini("user", user_text, user_attachments))
        return {
            "systemInstruction": {"parts": [{"text": system_text}]} if system_text else None,
            "contents": contents,
        }
    raise ValueError("未知的请求格式: {}".format(request_format))


def _normalize_history(history: Any) -> List[Dict[str, Any]]:
    """历史归一化：限角色、限条数、限附件数。"""
    result: List[Dict[str, Any]] = []
    if not isinstance(history, list):
        return result
    for item in history:
        if not isinstance(item, dict):
            continue
        role = "assistant" if item.get("role") == "assistant" else "user"
        text = _safe_text(item.get("text") or "")
        attachments = item.get("attachments") if isinstance(item.get("attachments"), list) else []
        attachments = [a for a in attachments if isinstance(a, dict) and a.get("id")][:MAX_HISTORY_ATTACHMENTS]
        if not text.strip() and not attachments:
            continue
        result.append({"role": role, "text": text, "attachments": attachments})
    settings_limit = _normalize_history_limit(read_copilot_settings().get("history_limit"))
    return result[-settings_limit:]


def _messages_without_system(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [m for m in messages if m.get("role") != "system"]


def _message_to_openai_chat(role: str, text: str, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """OpenAI Chat：无图 → 纯字符串 content；有图 → image_url data URL parts。"""
    if not attachments:
        return {"role": role, "content": text}
    parts: List[Dict[str, Any]] = []
    if text:
        parts.append({"type": "text", "text": text})
    for att in attachments[:MAX_ATTACHMENTS_PER_MESSAGE]:
        mime, b64 = _attachment_b64(att)
        parts.append({"type": "image_url", "image_url": {"url": "data:{};base64,{}".format(mime, b64)}})
    return {"role": role, "content": parts}


def _message_to_responses(role: str, text: str, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Codex Responses：input_text / input_image；assistant 用 output_text。"""
    if role == "assistant":
        return {"role": "assistant", "content": [{"type": "output_text", "text": text}]}
    parts: List[Dict[str, Any]] = []
    if text:
        parts.append({"type": "input_text", "text": text})
    for att in attachments[:MAX_ATTACHMENTS_PER_MESSAGE]:
        mime, b64 = _attachment_b64(att)
        parts.append({"type": "input_image", "image_url": "data:{};base64,{}".format(mime, b64), "detail": "auto"})
    return {"role": role, "content": parts}


def _message_to_claude(role: str, text: str, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Claude Messages：text block + image base64 source。"""
    parts: List[Dict[str, Any]] = []
    for att in attachments[:MAX_ATTACHMENTS_PER_MESSAGE]:
        mime, b64 = _attachment_b64(att)
        parts.append({"type": "image", "source": {"type": "base64", "media_type": mime, "data": b64}})
    if text:
        parts.append({"type": "text", "text": text})
    return {"role": role, "content": parts or [{"type": "text", "text": ""}]}


def _message_to_gemini(role: str, text: str, attachments: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Gemini：parts + inlineData base64；assistant 角色映射为 model。"""
    g_role = "model" if role == "assistant" else "user"
    parts: List[Dict[str, Any]] = []
    for att in attachments[:MAX_ATTACHMENTS_PER_MESSAGE]:
        mime, b64 = _attachment_b64(att)
        parts.append({"inlineData": {"mimeType": mime, "data": b64}})
    if text:
        parts.append({"text": text})
    return {"role": g_role, "parts": parts or [{"text": ""}]}


def _build_request_payload(
    request_format: str,
    model: str,
    temperature: float,
    chat: Dict[str, Any],
    stream: bool = True,
) -> Dict[str, Any]:
    """消息结构 → 各格式完整请求体。"""
    fmt = _normalize_request_format(request_format)
    model = _safe_text(model).strip() or DEFAULT_MODEL
    if fmt == "openai_chat":
        return {"model": model, "messages": chat["messages"], "temperature": temperature, "stream": stream}
    if fmt == "responses":
        payload = {"model": model, "input": chat["input"], "stream": stream}
        if chat.get("instructions"):
            payload["instructions"] = chat["instructions"]
        return payload
    if fmt == "claude":
        payload = {"model": model, "messages": chat["messages"], "max_tokens": 8192, "stream": stream}
        if chat.get("system"):
            payload["system"] = chat["system"]
        return payload
    if fmt == "gemini":
        payload: Dict[str, Any] = {"contents": chat["contents"]}
        if chat.get("systemInstruction"):
            payload["systemInstruction"] = chat["systemInstruction"]
        payload["generationConfig"] = {"temperature": temperature}
        return payload
    if fmt == "lmstudio":
        # 简化实现：LM Studio /api/v1/chat 纯文本 input（不支持图片）
        return {"model": model, "input": chat["messages"], "temperature": temperature, "stream": stream}
    raise ValueError("未知的请求格式: {}".format(request_format))


# ---------------------------------------------------------------------------
# SSE 流解析
# ---------------------------------------------------------------------------

def _extract_delta_text(request_format: str, obj: Any) -> str:
    """单条流事件 → 增量文本（不认识的结构返回空串）。"""
    if not isinstance(obj, dict):
        return ""
    fmt = _normalize_request_format(request_format)
    if fmt in ("openai_chat", "lmstudio"):
        choices = obj.get("choices")
        if isinstance(choices, list) and choices:
            delta = choices[0].get("delta") or choices[0].get("message") or {}
            return _safe_text(delta.get("content") or delta.get("text") or "")
        return ""
    if fmt == "responses":
        event_type = _safe_text(obj.get("type") or "")
        if event_type in ("response.output_text.delta", "output_text"):
            return _safe_text(obj.get("delta") or obj.get("text") or "")
        return ""
    if fmt == "claude":
        if obj.get("type") == "content_block_delta":
            delta = obj.get("delta") or {}
            return _safe_text(delta.get("text") or delta.get("partial_json") or "")
        return ""
    if fmt == "gemini":
        candidates = obj.get("candidates")
        if not isinstance(candidates, list) and "candidate" in obj:
            candidates = [obj.get("candidate")]
        if isinstance(candidates, list) and candidates:
            content = (candidates[0] or {}).get("content") or {}
            parts = content.get("parts") or []
            texts = [_safe_text(p.get("text") or "") for p in parts if isinstance(p, dict)]
            return "".join(texts)
        return ""
    return ""


def _is_stream_done(request_format: str, obj: Any) -> bool:
    """终止哨兵判断。"""
    if not isinstance(obj, dict):
        return False
    fmt = _normalize_request_format(request_format)
    if fmt in ("openai_chat",):
        return False  # [DONE] 在行级处理
    if fmt == "lmstudio":
        return bool(obj.get("done")) or _safe_text(obj.get("type")) == "response.completed"
    if fmt == "responses":
        return _safe_text(obj.get("type")) in ("response.completed", "response.done", "response.failed")
    if fmt == "claude":
        return _safe_text(obj.get("type")) in ("message_stop", "error")
    if fmt == "gemini":
        candidates = obj.get("candidates") if isinstance(obj.get("candidates"), list) else []
        if candidates and isinstance(candidates[0], dict) and candidates[0].get("finishReason"):
            return True
        # 兼容非标准分块把 finishReason 放顶层的情况
        if obj.get("finishReason"):
            return True
    return False


def _extract_json_objects(buffer: str) -> Tuple[List[Any], str]:
    """从缓冲提取完整 JSON 对象（Gemini 非 SSE 分块兼容，简化实现）。"""
    objects: List[Any] = []
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(buffer):
        ch = buffer[idx]
        if ch in " \t\r\n":
            idx += 1
            continue
        if ch not in "[{":
            idx += 1
            continue
        try:
            obj, end = decoder.raw_decode(buffer, idx)
        except json.JSONDecodeError:
            break
        objects.append(obj)
        idx = end
    return objects, buffer[idx:]


def _iter_stream_json(response, request_format: str):
    """流响应 → JSON 对象序列。

    - SSE：``data:`` 行 + ``event:`` 行，终止哨兵 ``[DONE]``
    - 非 SSE（Gemini JSON 分块）：json_buffer 增量提取（简化实现）
    """
    content_type = ""
    try:
        content_type = response.headers.get("Content-Type") or ""
    except Exception:  # noqa: BLE001
        pass
    is_sse = "text/event-stream" in content_type
    json_buffer = ""
    for raw_line in response.iter_lines(decode_unicode=False):
        if raw_line is None:
            continue
        line = raw_line.decode("utf-8", "replace") if isinstance(raw_line, (bytes, bytearray)) else str(raw_line)
        line = line.strip()
        if not line:
            continue
        if is_sse or line.startswith("data:") or line.startswith("event:"):
            if line.startswith("event:"):
                continue
            payload = line[5:].strip() if line.startswith("data:") else line
            if not payload or payload == "[DONE]":
                if payload == "[DONE]":
                    return
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, list):
                for item in obj:
                    yield item
            else:
                yield obj
        else:
            json_buffer += line
            objects, json_buffer = _extract_json_objects(json_buffer)
            for obj in objects:
                yield obj
    if json_buffer.strip():
        objects, _rest = _extract_json_objects(json_buffer)
        for obj in objects:
            yield obj


# ---------------------------------------------------------------------------
# Skill 执行器
# ---------------------------------------------------------------------------

def _read_text_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return fh.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def _parse_skill_frontmatter(text: str) -> Dict[str, str]:
    """frontmatter 逐行解析 ``^([\\w-]+):\\s*(.*)$``。"""
    meta: Dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped in ("---", ""):
            if meta and stripped == "---":
                break
            continue
        match = _SKILL_FRONTMATTER_RE.match(stripped)
        if match:
            meta[match.group(1)] = match.group(2).strip()
    return meta


def _read_skill_meta_value(meta: Dict[str, str], *keys: str) -> str:
    for key in keys:
        if meta.get(key):
            return meta[key]
    return ""


def _list_skill_references(skill_dir: str) -> List[str]:
    references_dir = os.path.join(skill_dir, SKILL_REFERENCES_DIR)
    if not os.path.isdir(references_dir):
        return []
    names = []
    for entry in sorted(os.listdir(references_dir)):
        if os.path.isfile(os.path.join(references_dir, entry)):
            names.append(entry)
    return names


def _normalize_skill_id(raw: Any) -> str:
    return _SKILL_ID_CLEAN_RE.sub("_", _safe_text(raw)).strip("_")[:80]


def _discover_skills() -> List[Dict[str, Any]]:
    """枚举 SKILLS_DIR 下含 SKILL.md / SKILL.cn.md / meta.yaml 的目录。"""
    skills: List[Dict[str, Any]] = []
    if not os.path.isdir(SKILLS_DIR):
        return skills
    for entry in sorted(os.listdir(SKILLS_DIR)):
        skill_dir = os.path.join(SKILLS_DIR, entry)
        if not os.path.isdir(skill_dir):
            continue
        body_path = None
        for name in (SKILL_MD, SKILL_CN_MD):
            if os.path.isfile(os.path.join(skill_dir, name)):
                body_path = os.path.join(skill_dir, name)
                break
        meta_path = os.path.join(skill_dir, SKILL_META)
        if body_path is None and not os.path.isfile(meta_path):
            continue
        meta: Dict[str, str] = {}
        if os.path.isfile(meta_path):
            meta = _parse_skill_frontmatter(_read_text_file(meta_path))
        body_head = _read_text_file(body_path)[:4000] if body_path else ""
        body_meta = _parse_skill_frontmatter(body_head)
        skill_id = _normalize_skill_id(entry)
        display_name = _read_skill_meta_value(meta, "display-name-zh", "display_name_zh", "name") or skill_id
        summary = _read_skill_meta_value(meta, "summary-cn", "summary_cn", "summary")
        references = _list_skill_references(skill_dir)
        skills.append({
            "id": skill_id,
            "name": skill_id,
            "display_name": display_name,
            "display_name_zh": display_name,
            "summary": summary,
            "summary_cn": summary,
            "description": _read_skill_meta_value(body_meta, "description"),
            "references": references,
        })
    return skills


def _get_skill(skill_id: Any) -> Optional[Dict[str, Any]]:
    wanted = _normalize_skill_id(skill_id)
    if not wanted:
        return None
    for skill in _discover_skills():
        if skill["id"] == wanted:
            return skill
    return None


def discover_skills() -> List[Dict[str, Any]]:
    """Skill 枚举公开入口（路由层使用）。"""
    return _discover_skills()


def get_skill(skill_id: Any) -> Optional[Dict[str, Any]]:
    """Skill 查找公开入口。"""
    return _get_skill(skill_id)


def read_skill_reference(skill: Dict[str, Any], name: Any) -> str:
    """reference 读取公开入口。"""
    return _read_skill_reference(skill, name)


def _read_skill_body(skill: Dict[str, Any]) -> str:
    """Skill 主体：中文版优先，缺失回退英文版。"""
    skill_dir = os.path.join(SKILLS_DIR, skill["id"])
    cn_path = os.path.join(skill_dir, SKILL_CN_MD)
    en_path = os.path.join(skill_dir, SKILL_MD)
    if os.path.isfile(cn_path):
        return _strip_frontmatter(_read_text_file(cn_path))
    if os.path.isfile(en_path):
        return _strip_frontmatter(_read_text_file(en_path))
    return ""


def _strip_frontmatter(text: str) -> str:
    if text.startswith("---"):
        end = text.find("---", 3)
        if end >= 0:
            return text[end + 3:].lstrip("\n")
    return text


def _read_skill_reference(skill: Dict[str, Any], name: Any) -> str:
    """读取 reference 全文（越界与缺失按 spec §3.4 文案报错）。"""
    skill_dir = os.path.join(SKILLS_DIR, skill["id"])
    references_dir = os.path.join(skill_dir, SKILL_REFERENCES_DIR)
    rel = _safe_text(name).strip().lstrip("/\\")
    target = os.path.realpath(os.path.join(references_dir, rel))
    if not target.startswith(os.path.realpath(references_dir) + os.sep):
        raise ValueError("Skill reference 路径超出 Skill 目录")
    if not os.path.isfile(target):
        raise ValueError("Skill reference 不存在：" + rel)
    return _read_text_file(target)


def build_skill_system_prompt(skill: Dict[str, Any]) -> str:
    """Skill 系统提示：协议 + Skill 全文 + references 清单。"""
    body = _read_skill_body(skill)
    references = skill.get("references") or []
    parts = [
        SKILL_EXECUTION_PROTOCOL,
        "",
        "当前 Skill：{}".format(skill.get("display_name") or skill["id"]),
    ]
    if body:
        parts.extend(["", "===== Skill 全文 =====", body])
    if references:
        parts.extend(["", "可用 references：" + "、".join(references)])
    return "\n".join(parts)


def parse_skill_reply(text: str) -> Tuple[str, Dict[str, Any]]:
    """从回复中提取 ``<te_man_skill_state>`` 状态标记。"""
    match = _SKILL_STATE_RE.search(text)
    if not match:
        return text, {}
    raw = match.group(1)
    cleaned = (text[:match.start()] + text[match.end():]).strip()
    try:
        state = json.loads(raw)
    except json.JSONDecodeError:
        state = {}
    if not isinstance(state, dict):
        state = {}
    state = {
        "stage": _safe_text(state.get("stage") or ""),
        "options": [ _safe_text(o) for o in state.get("options", []) if _safe_text(o)][:6],
        "load_references": [_safe_text(r) for r in state.get("load_references", []) if _safe_text(r)],
        "final": bool(state.get("final")),
    }
    return cleaned, state


# ---------------------------------------------------------------------------
# 图片附件
# ---------------------------------------------------------------------------

def attachment_path(attachment_id: str, extension: str) -> str:
    ext = _safe_text(extension).strip().lstrip(".").lower()
    return os.path.join(CHAT_ATTACHMENT_DIR, "{}.{}".format(attachment_id, ext))


def _attachment_url(attachment_id: str) -> str:
    return "{}/attachment/{}".format(ROUTE_PREFIX, attachment_id)


def save_chat_attachment(filename: str, data: bytes) -> Dict[str, Any]:
    """上传附件：EXIF 转正、白色填充、image_codec 编码 → png/jpg 落盘。"""
    if not data:
        raise ValueError("图片附件为空，请重新上传后再发送")
    if len(data) > MAX_ATTACHMENT_UPLOAD_BYTES:
        raise ValueError("单张图片不能超过 20MB")
    try:
        from io import BytesIO

        from PIL import Image, ImageOps

        with Image.open(BytesIO(data)) as image:
            oriented = ImageOps.exif_transpose(image)
            if oriented is None:
                oriented = image
            if oriented.mode not in ("RGB", "L"):
                background = Image.new("RGB", oriented.size, (255, 255, 255))
                rgba = oriented.convert("RGBA")
                background.paste(rgba, mask=rgba.split()[-1])
                oriented = background
            from .image_codec import encode_pil_image_to_api_bytes

            payload, mime, ext = encode_pil_image_to_api_bytes(oriented)
            width, height = oriented.size
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ValueError("图片格式处理失败") from exc

    attachment_id = uuid.uuid4().hex
    extension = ext.lstrip(".")
    os.makedirs(CHAT_ATTACHMENT_DIR, exist_ok=True)
    with open(attachment_path(attachment_id, extension), "wb") as fh:
        fh.write(payload)
    name = _safe_text(filename).strip() or "image.{}".format(extension)
    return {
        "id": attachment_id,
        "name": name,
        "mimeType": ATTACHMENT_MIME_TYPES.get(extension, mime),
        "extension": extension,
        "width": int(width),
        "height": int(height),
        "size": len(payload),
        "url": _attachment_url(attachment_id),
    }


def remove_attachment_files(attachment_ids: List[str]) -> None:
    """删除附件文件（失败仅告警：TE MAN 构想台清理图片附件失败: …）。"""
    for aid in attachment_ids:
        for ext in ATTACHMENT_EXTENSIONS:
            path = attachment_path(aid, ext)
            if not os.path.isfile(path):
                continue
            try:
                os.remove(path)
            except OSError as exc:
                logger.warning("TE MAN 构想台清理图片附件失败: %s", exc)


# ---------------------------------------------------------------------------
# turn 编排（多话题并行：key = panel_id + session_id）
# ---------------------------------------------------------------------------

def turn_key(panel_id: Any, session_id: Any) -> str:
    return "{}:{}".format(_safe_text(panel_id), _safe_text(session_id))


def register_turn(panel_id: Any, session_id: Any, turn_id: Any, message_id: Any, model: str) -> str:
    key = turn_key(panel_id, session_id)
    with _TURN_LOCK:
        _ACTIVE_TURNS[key] = {
            "turn_id": _safe_text(turn_id),
            "message_id": _safe_text(message_id),
            "model": _safe_text(model),
            "cancelled": False,
            "started_at": _chat_now_ms(),
        }
    return key


def cancel_turn(panel_id: Any, session_id: Any, turn_id: Any = "") -> bool:
    """/stop：置 cancelled 旗标（"cancelled"）。"""
    key = turn_key(panel_id, session_id)
    with _TURN_LOCK:
        entry = _ACTIVE_TURNS.get(key)
        if entry is None:
            return False
        if turn_id and _safe_text(turn_id) and entry.get("turn_id") != _safe_text(turn_id):
            return False
        entry["cancelled"] = True
        return True


def _release_turn(key: str) -> None:
    with _TURN_LOCK:
        _ACTIVE_TURNS.pop(key, None)


def _is_cancelled(key: str) -> bool:
    with _TURN_LOCK:
        entry = _ACTIVE_TURNS.get(key)
        return bool(entry and entry.get("cancelled"))


def run_copilot_turn(payload: Dict[str, Any], send_event: Callable[[str, Dict[str, Any]], None]) -> None:
    """执行一轮对话（在 worker 线程中同步运行，经 send_event 推送 SSE 事件）。

    payload 键（与前端 ROUTE_TURN 一致）：
    panel_id / turn_id / session_id / message_id / message / attachments /
    provider_id / request_format / model / system_prompt / temperature /
    history / skill_state

    事件：teman_copilot_turn_started / teman_copilot_text_delta /
    teman_copilot_turn_completed / teman_copilot_turn_failed
    （message.delta、chat.end 为二进制中共存的别名键，此处不再另发）
    """
    panel_id = payload.get("panel_id")
    session_id = _safe_text(payload.get("session_id") or "")
    message_id = _safe_text(payload.get("message_id") or "")
    turn_id = _safe_text(payload.get("turn_id") or "")
    key = turn_key(panel_id, session_id)

    base = {
        "panel_id": panel_id,
        "session_id": session_id,
        "turn_id": turn_id,
        "message_id": message_id,
    }

    def _fail(error: str) -> None:
        send_event("teman_copilot_turn_failed", {**base, "error": error,
                                                 "text": "TE MAN 构想台请求失败: " + error})

    try:
        provider, settings = resolve_provider_settings(payload)
    except ValueError as exc:
        _fail(str(exc))
        return

    request_format = _normalize_request_format(
        payload.get("request_format") or provider.get("request_format"))
    model = _safe_text(payload.get("model") or "").strip() or _safe_text(provider.get("model") or "").strip() or DEFAULT_MODEL
    temperature = _normalize_temperature(payload.get("temperature", settings.get("temperature")))
    user_text = _safe_text(payload.get("message") or "")
    user_attachments = payload.get("attachments") if isinstance(payload.get("attachments"), list) else []
    history = payload.get("history") if isinstance(payload.get("history"), list) else []
    skill_state_input = payload.get("skill_state") if isinstance(payload.get("skill_state"), dict) else {}

    if not user_text.strip() and not user_attachments:
        _fail("请输入内容或添加图片")
        return

    # --- Skill 门控 -------------------------------------------------------
    system_text = _safe_text(payload.get("system_prompt") or "").strip() or DEFAULT_SYSTEM_PROMPT
    skill: Optional[Dict[str, Any]] = None
    loaded_references: List[str] = []
    if _as_bool(skill_state_input.get("enabled")):
        selection = _safe_text(skill_state_input.get("selection") or skill_state_input.get("activeSkill") or "")
        if selection:
            skill = _get_skill(selection)
            if skill is None:
                _fail("选择的 Skill 已不存在，请重新打开 Skill 设置")
                return
            system_text = system_text + "\n\n" + build_skill_system_prompt(skill)
            loaded_references = [
                _safe_text(r) for r in skill_state_input.get("loadedReferences")
                or skill_state_input.get("loaded_references") or []
            ]

    send_event("teman_copilot_turn_started", {**base, "model": model})

    try:
        import requests
    except Exception as exc:  # noqa: BLE001
        _fail("requests 不可用: {}".format(exc))
        return

    final_text = ""
    final_skill_state: Dict[str, Any] = {}
    try:
        for round_index in range(MAX_SKILL_ROUNDS):
            if _is_cancelled(key):
                break
            chat = _build_chat_messages(request_format, system_text, history, user_text, user_attachments)
            payload_body = _build_request_payload(request_format, model, temperature, chat, stream=True)
            url = resolve_endpoint(request_format, provider["api_base_url"], model, provider.get("api_key", ""))
            headers = build_headers(request_format, provider.get("api_key", ""))
            logger.info("TE MAN 构想台: provider=%s, endpoint=%s, format=%s, model=%s",
                        provider["id"], _mask_url_for_log(url), request_format, model)
            response = requests.post(url, headers=headers, json=payload_body, stream=True, timeout=(10, 600))
            try:
                response.raise_for_status()
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError("HTTP {}: {}".format(getattr(response, "status_code", "?"), exc)) from exc

            round_text = ""
            try:
                for obj in _iter_stream_json(response, request_format):
                    if _is_cancelled(key):
                        break
                    if _is_stream_done(request_format, obj):
                        break
                    delta = _extract_delta_text(request_format, obj)
                    if delta:
                        round_text += delta
                        send_event("teman_copilot_text_delta", {**base, "text": delta})
            finally:
                try:
                    response.close()
                except Exception:  # noqa: BLE001
                    pass

            # --- Skill 状态协议：解析标记，按需加载 references 后重答 ------
            cleaned, parsed_state = parse_skill_reply(round_text)
            if skill is not None:
                pending = [name for name in parsed_state.get("load_references", [])
                           if name and name not in loaded_references]
                if pending and round_index + 1 < MAX_SKILL_ROUNDS and not parsed_state.get("final"):
                    reference_parts = []
                    for name in pending:
                        reference_parts.append("===== reference: {} =====\n{}".format(
                            name, _read_skill_reference(skill, name)))
                        loaded_references.append(name)
                    history = history + [
                        {"role": "assistant", "text": cleaned or round_text, "attachments": []},
                        {"role": "user", "text": "已加载 references：\n" + "\n\n".join(reference_parts)
                         + "\n已加载 references：" + "、".join(pending) + "，请继续。",
                         "attachments": []},
                    ]
                    continue
                final_skill_state = {
                    "enabled": True,
                    "selection": skill["id"],
                    "activeSkill": skill["id"],
                    "skillName": skill.get("display_name") or skill["id"],
                    "stage": _safe_text(parsed_state.get("stage") or ""),
                    "options": parsed_state.get("options") or [],
                    "loadedReferences": loaded_references,
                    "final": bool(parsed_state.get("final")),
                }
            final_text = cleaned if skill is not None and cleaned else round_text
            break
    except ValueError as exc:
        # 附件/Skill/参数类错误：文案本身面向用户，不套统一包装
        if _is_cancelled(key):
            send_event("teman_copilot_turn_completed",
                       {**base, "text": final_text, "status": "cancelled"})
        else:
            _fail(str(exc) or "请求失败")
        _release_turn(key)
        return
    except Exception as exc:  # noqa: BLE001
        # fallback_model 重试（spec：请求失败时换模型重试一次）
        fallback_model = _safe_text(provider.get("fallback_model") or "").strip()
        if fallback_model and fallback_model != model and not _is_cancelled(key):
            logger.warning("TE MAN 构想台 retry: %s -> %s", model, fallback_model)
            payload_retry = dict(payload)
            payload_retry["model"] = fallback_model
            payload_retry["history"] = history
            payload_retry.setdefault("panel_id", panel_id)
            # 简化实现：递归一次；递归内部不再有 fallback（模型相同则不进重试分支）
            _retry_once(payload_retry, send_event)
            return
        if _is_cancelled(key):
            send_event("teman_copilot_turn_completed",
                       {**base, "text": final_text, "status": "cancelled", "skill_state": final_skill_state or None})
            _release_turn(key)
            return
        logger.exception("TE MAN 构想台请求失败")
        _fail(str(exc) or "请求失败")
        _release_turn(key)
        return

    if _is_cancelled(key):
        send_event("teman_copilot_turn_completed",
                   {**base, "text": final_text, "status": "cancelled", "skill_state": final_skill_state or None})
    else:
        completed: Dict[str, Any] = {**base, "text": final_text, "skill_state": final_skill_state or None}
        send_event("teman_copilot_turn_completed", completed)
    _release_turn(key)


def _retry_once(payload: Dict[str, Any], send_event: Callable[[str, Dict[str, Any]], None]) -> None:
    """fallback 重试入口：清空 fallback_model 防止递归。"""
    try:
        provider, _settings = resolve_provider_settings(payload)
        provider = dict(provider)
        provider["fallback_model"] = ""
    except Exception:  # noqa: BLE001
        pass
    run_copilot_turn(payload, send_event)
