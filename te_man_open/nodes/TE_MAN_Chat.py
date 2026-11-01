# -*- coding: utf-8 -*-
"""te_man_open · TE_MAN_Chat —— TE MAN 构想台（Idea Desk）HTTP 路由层。

逆向规格: spec/TE_MAN_Chat.md。

⚠️ 本文件说明（请勿删除）：
1. 原版 TE_MAN_Chat.pyd **不注册任何 ComfyUI 节点**（spec §2：存在
   NODE_CLASS_MAPPINGS 字符串但无 INPUT_TYPES 等节点特征，推断仅导出空映射），
   它是"构想台"后端服务：在 PromptServer 上注册 12 条 ``/te_man/copilot/*``
   REST 路由，供前端 web/js/te_man_chat.js 的悬浮 AI 聊天面板调用。
   因此本复刻文件**故意不定义 NODE_CLASS_MAPPINGS / NODE_DISPLAY_NAME_MAPPINGS**，
   请勿在本文件中添加节点注册——契约检查（tools/check_contract.py）会报"多余注册"。
2. 本文件不是 codegen 骨架（不会被 tools/codegen_skeletons.py 覆盖）。
3. aiohttp / requests / PIL 一律惰性导入：契约检查会 import te_man_open
   从而加载本模块，顶层仅允许标准库依赖。
4. 核心逻辑（SQLite 会话库 / 多后端请求格式 / Skill 执行器 / 附件管理 /
   turn 编排）在 te_man_open/shared/idea_desk.py，本文件只做路由与事件派发。
"""

import json
import logging
import os
import threading
import time
from typing import Any, Dict

from ..shared import idea_desk

logger = logging.getLogger("te_man_open.te_man_chat")

ROUTES_REGISTERED = False
_ROUTE_REGISTER_THREAD_STARTED = False

#: 事件别名（spec §3.2：message.delta / chat.end 与正式事件名共存于二进制，
#: 确切分工未确认；此处统一只发正式事件名）
EVENT_TURN_STARTED = "teman_copilot_turn_started"
EVENT_TEXT_DELTA = "teman_copilot_text_delta"
EVENT_TURN_COMPLETED = "teman_copilot_turn_completed"
EVENT_TURN_FAILED = "teman_copilot_turn_failed"

__all__ = ["register_routes"]


# ---------------------------------------------------------------------------
# HTTP 支撑
# ---------------------------------------------------------------------------

def _json_ok(data: Dict[str, Any] = None, status: int = 200):
    from aiohttp import web  # 惰性导入

    body = dict(data or {})
    body.setdefault("success", True)
    return web.json_response(body, status=status)


def _json_error(message: str, status: int = 400):
    from aiohttp import web  # 惰性导入

    return web.json_response({"success": False, "error": str(message)}, status=status)


async def _read_json_payload(request) -> Dict[str, Any]:
    """读取并校验 JSON 请求体（文案 spec §5）。"""
    try:
        raw = await request.read()
    except Exception as e:  # noqa: BLE001
        raise ValueError("读取请求体失败: {}".format(e)) from None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("请求内容必须是 JSON 对象") from None
    if not isinstance(payload, dict):
        raise ValueError("请求内容必须是 JSON 对象")
    return payload


def _require_panel_id(payload: Dict[str, Any]) -> str:
    panel_id = str(payload.get("panel_id") or "").strip()
    if not panel_id:
        raise ValueError("缺少 panel_id")
    return panel_id


def _send_event(event: str, data: Dict[str, Any]) -> None:
    """经 PromptServer.send_sync 推送事件（前端 api.addEventListener 消费）。"""
    try:
        from server import PromptServer  # 惰性导入

        instance = getattr(PromptServer, "instance", None)
        if instance is not None:
            instance.send_sync(event, data)
    except Exception:  # noqa: BLE001
        logger.debug("构想台事件派发失败: %s", event, exc_info=True)


# ---------------------------------------------------------------------------
# 12 条路由处理器（spec §3 路由表）
# ---------------------------------------------------------------------------

async def te_man_copilot_bootstrap(request):
    """GET /te_man/copilot/bootstrap —— 面板启动一次性拉取：设置（脱敏）+ 工作区。"""
    try:
        settings = idea_desk.read_copilot_settings()
        workspace = _workspace_state()
        payload = idea_desk.public_settings_payload(settings)
        payload["workspace_state"] = workspace
        return _json_ok(payload)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_get_settings(request):
    """GET /te_man/copilot/settings —— 脱敏设置。"""
    try:
        return _json_ok(idea_desk.public_settings_payload())
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_save_settings(request):
    """POST /te_man/copilot/settings —— 保存供应商设置（含 Gemini 模型名校验）。"""
    try:
        payload = await _read_json_payload(request)
        settings = idea_desk.write_copilot_settings(payload)
        return _json_ok(idea_desk.public_settings_payload(settings))
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_skills(request):
    """GET /te_man/copilot/skills —— 枚举 SKILLS_DIR 下可用 Skill。"""
    try:
        skills = idea_desk.discover_skills()
        result: Dict[str, Any] = {"skills": skills, "skills_dir": idea_desk.SKILLS_DIR}
        if not skills:
            result["message"] = "没有发现可用 Skill，请把 Skill 安装到 TE_image/skills 目录"
        return _json_ok(result)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_workspace(request):
    """GET /te_man/copilot/workspace —— 会话树 + 消息 + workspace_state。"""
    try:
        return _json_ok({
            "workspace_state": _workspace_state(),
        })
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_workspace_meta(request):
    """POST /te_man/copilot/workspace/meta —— 保存 currentSessionId 等前端元数据。"""
    try:
        payload = await _read_json_payload(request)
        _require_panel_id(payload)
        store = idea_desk.get_chat_store()
        for key in ("currentSessionId", "workspace_meta", "workspace_state"):
            if key in payload and payload[key] is not None:
                store.set_kv(key, payload[key])
        return _json_ok({"saved": True})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_topic_upsert(request):
    """POST /te_man/copilot/topic/upsert —— 创建/更新话题（sessions 表 upsert）。"""
    try:
        payload = await _read_json_payload(request)
        _require_panel_id(payload)
        session = payload.get("session")
        if not isinstance(session, dict) or not str(session.get("id") or "").strip():
            return _json_error("缺少会话数据", 400)
        store = idea_desk.get_chat_store()
        saved = store.upsert_session(session)
        workspace_meta = payload.get("workspace_meta")
        if isinstance(workspace_meta, dict):
            current_id = workspace_meta.get("currentSessionId")
            if current_id:
                store.set_kv("currentSessionId", str(current_id))
        return _json_ok({"session_id": saved["id"], "updatedAt": saved["updatedAt"]})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_topic_delete(request):
    """POST /te_man/copilot/topic/delete —— 删除话题 + 级联消息 + 附件清理。"""
    try:
        payload = await _read_json_payload(request)
        _require_panel_id(payload)
        session_id = str(payload.get("session_id") or payload.get("id") or "").strip()
        if not session_id:
            return _json_error("缺少 session_id", 400)
        store = idea_desk.get_chat_store()
        attachment_ids = store.delete_session(session_id)
        idea_desk.remove_attachment_files(attachment_ids)
        return _json_ok({"deleted": True, "session_id": session_id})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_turn(request):
    """POST /te_man/copilot/turn —— 发起一轮对话（worker 线程流式执行）。"""
    try:
        payload = await _read_json_payload(request)
        _require_panel_id(payload)
    except ValueError as e:
        return _json_error(str(e), 400)

    session_id = str(payload.get("session_id") or "").strip()
    if not session_id:
        return _json_error("缺少 session_id", 400)

    # 供应商预校验（快速失败，文案与 worker 内一致）
    try:
        idea_desk.resolve_provider_settings(payload)
    except ValueError as e:
        return _json_error(str(e), 400)

    turn_id = str(payload.get("turn_id") or "").strip()
    model = str(payload.get("model") or "").strip()
    idea_desk.register_turn(payload.get("panel_id"), session_id, turn_id, payload.get("message_id"), model)
    worker = threading.Thread(
        target=idea_desk.run_copilot_turn,
        args=(payload, _send_event),
        name="TEManIdeaDeskTurn",
        daemon=True,
    )
    worker.start()
    return _json_ok({"turn_id": turn_id, "accepted": True})


async def te_man_copilot_stop(request):
    """POST /te_man/copilot/stop —— 取消进行中的 turn（置 cancelled 旗标）。"""
    try:
        payload = await _read_json_payload(request)
        _require_panel_id(payload)
        cancelled = idea_desk.cancel_turn(
            payload.get("panel_id"),
            payload.get("session_id"),
            payload.get("turn_id") or "",
        )
        return _json_ok({"cancelled": bool(cancelled), "status": "cancelled"})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_upload_attachment(request):
    """POST /te_man/copilot/attachment —— multipart 上传图片（字段名 image）。"""
    try:
        post = await request.post()
        upload = post.get("image")
        if upload is None or not hasattr(upload, "file"):
            raise ValueError("图片附件为空，请重新上传后再发送")
        data = upload.file.read()
        attachment = idea_desk.save_chat_attachment(getattr(upload, "filename", ""), data)
        return _json_ok({"attachment": attachment})
    except ValueError as e:
        return _json_error(str(e), 400)
    except Exception as e:  # noqa: BLE001
        return _json_error(str(e), 500)


async def te_man_copilot_get_attachment(request):
    """GET /te_man/copilot/attachment/{attachment_id} —— FileResponse 返回图片。"""
    from aiohttp import web  # 惰性导入

    attachment_id = str(request.match_info.get("attachment_id") or "").strip()
    if not idea_desk._ATTACHMENT_ID_RE.match(attachment_id):
        return _json_error("图片附件不存在，请重新上传后再发送", 404)
    path = None
    for ext in sorted(idea_desk.ATTACHMENT_EXTENSIONS):
        candidate = idea_desk.attachment_path(attachment_id, ext)
        if os.path.isfile(candidate):
            path = candidate
            break
    if path is None:
        return _json_error("图片附件不存在，请重新上传后再发送", 404)
    return web.FileResponse(
        path,
        headers={"Cache-Control": "private, max-age=86400"},
    )


# ---------------------------------------------------------------------------
# workspace_state 组装
# ---------------------------------------------------------------------------

def _workspace_state() -> Dict[str, Any]:
    """会话树 + currentSessionId（kv_store 优先，回退最新会话）。"""
    store = idea_desk.get_chat_store()
    sessions = store.list_sessions()
    current = store.get_kv("currentSessionId")
    current_id = str(current or "").strip()
    if current_id and not any(s["id"] == current_id for s in sessions):
        current_id = sessions[0]["id"] if sessions else ""
    if not current_id and sessions:
        current_id = sessions[0]["id"]
    return {"sessions": sessions, "currentSessionId": current_id}


# ---------------------------------------------------------------------------
# PromptServer 惰性导入注册（模块导入副作用，spec §3）
# ---------------------------------------------------------------------------

def register_routes(prompt_server) -> None:
    """把 12 条路由注册到 ``PromptServer.instance.routes``（一次性）。"""
    global ROUTES_REGISTERED
    if ROUTES_REGISTERED:
        return
    routes = getattr(prompt_server, "routes", None)
    if routes is None:
        return
    routes.get("/te_man/copilot/bootstrap")(te_man_copilot_bootstrap)
    routes.get("/te_man/copilot/settings")(te_man_copilot_get_settings)
    routes.post("/te_man/copilot/settings")(te_man_copilot_save_settings)
    routes.get("/te_man/copilot/skills")(te_man_copilot_skills)
    routes.get("/te_man/copilot/workspace")(te_man_copilot_workspace)
    routes.post("/te_man/copilot/workspace/meta")(te_man_copilot_workspace_meta)
    routes.post("/te_man/copilot/topic/upsert")(te_man_copilot_topic_upsert)
    routes.post("/te_man/copilot/topic/delete")(te_man_copilot_topic_delete)
    routes.post("/te_man/copilot/turn")(te_man_copilot_turn)
    routes.post("/te_man/copilot/stop")(te_man_copilot_stop)
    routes.post("/te_man/copilot/attachment")(te_man_copilot_upload_attachment)
    routes.get("/te_man/copilot/attachment/{attachment_id}")(te_man_copilot_get_attachment)
    ROUTES_REGISTERED = True


def _wait_for_server(timeout_seconds: float = 60.0) -> bool:
    """轮询等待 PromptServer 就绪。"""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            from server import PromptServer  # 惰性导入

            if getattr(PromptServer, "instance", None) is not None:
                return True
        except Exception:  # noqa: BLE001
            return False  # 非 ComfyUI 环境，放弃注册
        time.sleep(1.0)
    return False


def _register_routes_when_ready() -> None:
    """daemon 线程 TEManIdeaDeskRouteRegister：等待就绪后注册，带超时警告。"""
    if _wait_for_server():
        try:
            from server import PromptServer  # 惰性导入

            register_routes(PromptServer.instance)
            if ROUTES_REGISTERED:
                logger.info("TE MAN 构想台路由已注册")
                return
        except Exception:  # noqa: BLE001
            logger.warning("TE MAN 构想台路由注册失败", exc_info=True)
    if not ROUTES_REGISTERED:
        logger.warning("TE MAN 构想台路由注册超时：PromptServer 未就绪")


def _schedule_route_registration() -> None:
    """PromptServer 可用则立即注册；否则启动 daemon 线程延迟注册。"""
    global _ROUTE_REGISTER_THREAD_STARTED
    if ROUTES_REGISTERED:
        return
    try:
        from server import PromptServer  # 惰性导入
    except Exception:  # noqa: BLE001
        return  # 非 ComfyUI 环境（契约检查等），不注册
    if getattr(PromptServer, "instance", None) is not None:
        try:
            register_routes(PromptServer.instance)
            logger.info("TE MAN 构想台路由已注册")
        except Exception:  # noqa: BLE001
            logger.warning("TE MAN 构想台路由注册失败", exc_info=True)
        return
    if _ROUTE_REGISTER_THREAD_STARTED:
        return
    _ROUTE_REGISTER_THREAD_STARTED = True
    logger.warning("TE MAN 构想台路由未注册：PromptServer 尚未就绪")
    threading.Thread(
        target=_register_routes_when_ready,
        name="TEManIdeaDeskRouteRegister",
        daemon=True,
    ).start()


_schedule_route_registration()
