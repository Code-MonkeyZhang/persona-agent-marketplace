"""
Pomodoro Timer Agent App server.

Runs two channels in one process via anyio task group:
- stdio MCP: exposes tools (start / stop / query_stats / get_timer_state)
  to the Agent, sends notifications on user actions and timer events
- uvicorn HTTP: serves the built Web UI as static files, WebSocket for
  real-time timer state

Both channels share a single PomodoroServer instance. The timer runs as an
asyncio Task; when it fires, the server records the session, notifies the
Agent, and auto-starts the next phase (break or idle).

Notification routing follows the "按任务记账" principle: the agentId /
sessionId that started the current focus cycle receive ALL notifications
for that cycle, regardless of which session later queries or views the panel.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anyio
import mcp.types as types
import uvicorn
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.message import SessionMessage
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from .db import FocusDB
from .log import initialize as log_init, log
from .prompts import load_prompt
from .timer import (
    PHASE_FOCUS,
    PHASE_IDLE,
    PHASE_LABELS,
    PHASE_LONG_BREAK,
    PHASE_SHORT_BREAK,
    TimerSettings,
    TimerState,
)

APP_ROOT = Path(__file__).resolve().parent.parent.parent
UI_DIR = APP_ROOT / "ui"
ICON_PATH = APP_ROOT / "icon.png"
DATA_DIR = APP_ROOT / "data"
LOG_PATH = APP_ROOT / "pomodoro.log"

SOURCE = "pomodoro-timer"

# --- Tool definitions -------------------------------------------------------

_INJECTED_PARAMS = {
    "agentId": {
        "type": "string",
        "description": "平台自动注入，无需填写",
    },
    "sessionId": {
        "type": "string",
        "description": "平台自动注入，无需填写",
    },
}

TOOLS = [
    types.Tool(
        name="start",
        description=load_prompt("start"),
        inputSchema={
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "本次专注的意图描述（可选）",
                },
                "duration_min": {
                    "type": "integer",
                    "description": "专注时长（分钟），不传用默认值",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="stop",
        description=load_prompt("stop"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
    types.Tool(
        name="query_stats",
        description=load_prompt("query_stats"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
    types.Tool(
        name="get_timer_state",
        description=load_prompt("get_timer_state"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
]


def _now_ms() -> int:
    return int(time.time() * 1000)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _format_duration(seconds: int) -> str:
    """Format seconds as a human-readable duration.

    - exact minutes: "25 分钟"
    - under a minute: "30 秒"
    - mixed: "4 分 30 秒"
    """
    minutes, secs = divmod(seconds, 60)
    if secs == 0:
        return f"{minutes} 分钟"
    if minutes == 0:
        return f"{secs} 秒"
    return f"{minutes} 分 {secs} 秒"


# --- Shared server state ----------------------------------------------------


class PomodoroServer:
    """Holds timer state, DB, and bridges between MCP and WS channels."""

    def __init__(self) -> None:
        self.db = FocusDB(DATA_DIR / "focus.db")
        settings = self.db.get_settings()
        self.state = TimerState(settings=TimerSettings(**settings))
        self._write_stream: object | None = None
        self._ws_clients: dict[WebSocket, tuple[str, str]] = {}
        self._timer_task: asyncio.Task | None = None
        self._focus_duration_sec: int = 0
        self._notify_start_tmpl = load_prompt("notify_start")
        self._notify_end_tmpl = load_prompt("notify_end")
        self._notify_break_end_tmpl = load_prompt("notify_break_end")

    def set_write_stream(self, stream: object) -> None:
        self._write_stream = stream

    # --- Timer phase management ---

    def _schedule_phase_end(self, duration_seconds: int) -> None:
        """Schedule the phase-end callback. Cancels any pending timer."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        self._timer_task = asyncio.create_task(
            self._phase_timer(duration_seconds)
        )

    async def _phase_timer(self, duration_seconds: int) -> None:
        """Sleep for duration then trigger phase end. Clears task ref first
        so _schedule_phase_end inside _on_phase_end won't self-cancel."""
        try:
            await asyncio.sleep(duration_seconds)
            self._timer_task = None
            await self._on_phase_end()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self._timer_task = None
            log("ERROR", "phase_timer_failed", error=str(e))
            await self._push_state()

    async def _on_phase_end(self) -> None:
        """Called when the countdown reaches zero."""
        if self.state.phase == PHASE_FOCUS:
            await self._handle_focus_end()
        elif self.state.phase in (PHASE_SHORT_BREAK, PHASE_LONG_BREAK):
            await self._handle_break_end()

    async def _handle_focus_end(self) -> None:
        """Record session, notify, auto-start the appropriate break."""
        duration_sec = self._focus_duration_sec
        try:
            self.db.record_session(
                self.state.started_at, _now_iso(),
                duration_sec, self.state.intent, True,
                self.state.focus_agent_id, self.state.focus_session_id,
            )
        except Exception as e:
            log("ERROR", "record_session_failed", error=str(e))

        await self._notify(
            self._notify_end_tmpl.format(
                summary=f"共 {_format_duration(duration_sec)}"
            )
        )

        self.state.focus_count_in_round += 1
        if self.state.focus_count_in_round >= self.state.settings.focus_per_round:
            self._begin_break(PHASE_LONG_BREAK)
            self.state.focus_count_in_round = 0
        else:
            self._begin_break(PHASE_SHORT_BREAK)

        log(
            "INFO", "focus_ended",
            duration_sec=duration_sec,
            count=self.state.focus_count_in_round,
        )
        await self._push_state()
        await self._push_data()

    async def _handle_break_end(self) -> None:
        """Notify and return to idle."""
        break_type = "短" if self.state.phase == PHASE_SHORT_BREAK else "长"
        content = self._notify_break_end_tmpl.format(break_type=break_type)
        await self._notify(content)
        self._reset_to_idle()
        log("INFO", "break_ended", type=self.state.phase)
        await self._push_state()

    def _begin_break(self, break_type: str) -> None:
        """Set state to a break phase and schedule its timer.

        Long break = break_min * 3; short break = break_min.
        """
        base = self.state.settings.break_min
        duration = base * 3 if break_type == PHASE_LONG_BREAK else base
        self.state.phase = break_type
        self.state.running = True
        self.state.ends_at = _now_ms() + duration * 60 * 1000
        self.state.remaining_seconds = duration * 60
        self._schedule_phase_end(duration * 60)

    def _reset_to_idle(self) -> None:
        """Reset timer state to idle without touching the timer task."""
        self.state.phase = PHASE_IDLE
        self.state.running = False
        self.state.ends_at = None
        self.state.remaining_seconds = 0
        self.state.intent = ""
        self._focus_duration_sec = 0

    def _elapsed_seconds(self) -> int:
        """Calculate elapsed focus seconds from total minus remaining."""
        if self.state.running:
            remaining = max(0, int((self.state.ends_at - _now_ms()) / 1000))
        else:
            remaining = self.state.remaining_seconds
        return max(0, self._focus_duration_sec - remaining)

    # --- Focus start / stop (shared by MCP and WS) ---

    async def _start_focus(
        self,
        intent: str,
        duration_min: int | None,
        agent_id: str,
        session_id: str,
        by_user: bool,
    ) -> int:
        """Start a focus phase. Returns the actual duration in minutes."""
        actual = duration_min or self.state.settings.focus_min
        self.state.phase = PHASE_FOCUS
        self.state.running = True
        self.state.intent = intent
        self.state.started_at = _now_iso()
        self.state.focus_agent_id = agent_id
        self.state.focus_session_id = session_id
        self.state.ends_at = _now_ms() + actual * 60 * 1000
        self.state.remaining_seconds = actual * 60
        self._focus_duration_sec = actual * 60
        self._schedule_phase_end(actual * 60)

        intent_clause = f"，意图：{intent}" if intent else ""
        content = self._notify_start_tmpl.format(
            duration=actual, intent_clause=intent_clause,
        )
        await self._notify(content)

        log(
            "INFO", "focus_started",
            by="user" if by_user else "agent",
            duration=actual, intent=intent,
        )
        await self._push_state()
        return actual

    async def _do_stop(self, by_user: bool) -> None:
        """Stop the timer, record partial if focus, return to idle."""
        was_focus = self.state.phase == PHASE_FOCUS
        elapsed_sec = self._elapsed_seconds() if was_focus else 0

        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None

        if was_focus and elapsed_sec >= 1:
            try:
                self.db.record_session(
                    self.state.started_at, _now_iso(),
                    elapsed_sec, self.state.intent, False,
                    self.state.focus_agent_id, self.state.focus_session_id,
                )
            except Exception as e:
                log("ERROR", "record_session_failed", error=str(e))

        if was_focus:
            await self._notify(
                self._notify_end_tmpl.format(
                    summary=f"中途停止，已专注 {_format_duration(elapsed_sec)}"
                )
            )

        self._reset_to_idle()
        log(
            "INFO", "timer_stopped",
            was_focus=was_focus, elapsed_sec=elapsed_sec,
            by="user" if by_user else "agent",
        )
        await self._push_state()
        if was_focus and elapsed_sec >= 1:
            await self._push_data()

    # --- MCP tool handlers ---

    async def tool_start(
        self, intent: str, duration_min: int | None,
        agent_id: str, session_id: str,
    ) -> str:
        if self.state.phase != PHASE_IDLE:
            return "计时器正在运行中，请先停止当前计时"
        actual = await self._start_focus(
            intent, duration_min, agent_id, session_id, by_user=False,
        )
        return f"专注已开始，{actual} 分钟"

    async def tool_stop(self) -> str:
        if self.state.phase == PHASE_IDLE:
            return "计时器未在运行"
        await self._do_stop(by_user=False)
        return "计时器已停止"

    def query_stats(self) -> str:
        stats = self.db.get_stats()
        parts = [
            f"今日：{stats['today_count']} 个番茄钟，"
            f"累计 {_format_duration(stats['today_seconds'])}",
            f"本周：{stats['week_count']} 个番茄钟，"
            f"累计 {_format_duration(stats['week_seconds'])}",
        ]
        history = self.db.get_history(5)
        if history:
            parts.append("最近专注：")
            for h in history:
                status = "完成" if h["completed"] else "中断"
                parts.append(
                    f"  {h['intent'] or '无意图'}，"
                    f"{_format_duration(h['duration_sec'])}，{status}"
                )
        return "。".join(parts)

    def get_timer_state(self) -> str:
        if self.state.phase == PHASE_IDLE:
            return "当前空闲，无计时器运行"
        phase_label = PHASE_LABELS.get(self.state.phase, self.state.phase)
        if self.state.running:
            remaining_sec = max(
                0, int((self.state.ends_at - _now_ms()) / 1000)
            )
        else:
            remaining_sec = self.state.remaining_seconds
        parts = [
            f"当前阶段：{phase_label}",
            f"剩余：{remaining_sec // 60} 分 {remaining_sec % 60} 秒",
        ]
        if self.state.phase == PHASE_FOCUS:
            if self.state.intent:
                parts.append(f"意图：{self.state.intent}")
            parts.append(
                f"本轮第 {self.state.focus_count_in_round + 1} 个 / "
                f"共 {self.state.settings.focus_per_round} 个"
            )
        if not self.state.running:
            parts.append("（已暂停）")
        return "，".join(parts)

    # --- WebSocket handler ---

    async def handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        agent_id = websocket.query_params.get("agentId", "")
        session_id = websocket.query_params.get("sessionId", "")
        self._ws_clients[websocket] = (agent_id, session_id)
        log(
            "INFO", "ws_connected",
            clients=len(self._ws_clients),
            has_context=bool(agent_id and session_id),
        )

        await websocket.send_json({
            "type": "init",
            "state": self.state.to_dict(),
            "history": self.db.get_history(),
            "stats": self.db.get_stats(),
        })

        try:
            while True:
                msg = await websocket.receive_json()
                mtype = msg.get("type")
                if mtype == "start":
                    await self._on_ws_start(websocket, msg.get("intent", ""), msg.get("duration_min"))
                elif mtype == "pause":
                    await self._on_ws_pause()
                elif mtype == "resume":
                    await self._on_ws_resume()
                elif mtype == "stop":
                    await self._on_ws_stop(websocket)
                elif mtype == "update_settings":
                    await self._on_ws_update_settings(msg.get("settings", {}))
                elif mtype == "get_month":
                    year = int(msg.get("year", 0))
                    month = int(msg.get("month", 0))
                    sessions = self.db.get_sessions_for_month(year, month)
                    await websocket.send_json({
                        "type": "month_data",
                        "sessions": sessions,
                    })
        except WebSocketDisconnect:
            pass
        except Exception as e:
            log("WARN", "ws_error", error=str(e))
        finally:
            self._ws_clients.pop(websocket, None)
            log("INFO", "ws_disconnected", clients=len(self._ws_clients))

    # --- WS event handlers ---

    async def _on_ws_start(self, ws: WebSocket, intent: str, duration_min: int | None = None) -> None:
        if self.state.phase != PHASE_IDLE:
            log("WARN", "start_ignored", reason="timer running")
            return
        agent_id, session_id = self._ws_clients.get(ws, ("", ""))
        await self._start_focus(
            intent, duration_min, agent_id, session_id, by_user=True,
        )

    async def _on_ws_stop(self, ws: WebSocket) -> None:
        if self.state.phase == PHASE_IDLE:
            log("WARN", "stop_ignored", reason="not running")
            return
        await self._do_stop(by_user=True)

    async def _on_ws_pause(self) -> None:
        if not self.state.running or self.state.phase == PHASE_IDLE:
            return
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
            self._timer_task = None
        self.state.remaining_seconds = max(
            0, int((self.state.ends_at - _now_ms()) / 1000)
        )
        self.state.running = False
        log("INFO", "timer_paused", remaining=self.state.remaining_seconds)
        await self._push_state()

    async def _on_ws_resume(self) -> None:
        if self.state.running or self.state.phase == PHASE_IDLE:
            return
        self.state.ends_at = _now_ms() + self.state.remaining_seconds * 1000
        self.state.running = True
        self._schedule_phase_end(self.state.remaining_seconds)
        log("INFO", "timer_resumed", remaining=self.state.remaining_seconds)
        await self._push_state()

    async def _on_ws_update_settings(self, data: dict) -> None:
        clamped = _clamp_settings(data)
        self.db.update_settings(**clamped)
        self.state.settings = TimerSettings(**clamped)
        log("INFO", "settings_updated", **clamped)
        await self._push_state()

    # --- Notification & broadcast helpers ---

    async def _notify(self, content: str) -> None:
        """Push a notifications/app message to the session that started
        the current focus cycle (按任务记账). Uses focus_agent_id /
        focus_session_id from state, not the current WS viewer."""
        if not self._write_stream:
            log("WARN", "notification_skipped", reason="no write_stream")
            return
        agent_id = self.state.focus_agent_id
        session_id = self.state.focus_session_id
        if not agent_id or not session_id:
            log("WARN", "notification_skipped", reason="no agent/session")
            return
        notification = types.JSONRPCNotification(
            jsonrpc="2.0",
            method="notifications/app",
            params={
                "agentId": agent_id,
                "sessionId": session_id,
                "source": SOURCE,
                "content": content,
            },
        )
        await self._write_stream.send(SessionMessage(message=notification))
        log("INFO", "notification_sent", content=content)

    async def _push_state(self) -> None:
        await self._broadcast_ws({"type": "state", "state": self.state.to_dict()})

    async def _push_data(self) -> None:
        await self._broadcast_ws({
            "type": "data",
            "history": self.db.get_history(),
            "stats": self.db.get_stats(),
        })

    async def _broadcast_ws(self, data: dict) -> None:
        """Send a message to all connected WS clients, dropping dead ones."""
        dead: set[WebSocket] = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._ws_clients.pop(ws, None)


def _clamp_settings(data: dict) -> dict:
    """Validate and clamp settings values to allowed ranges."""
    return {
        "focus_min": max(1, min(90, int(data.get("focus_min", 25)))),
        "break_min": max(1, min(30, int(data.get("break_min", 5)))),
        "focus_per_round": max(1, min(8, int(data.get("focus_per_round", 4)))),
    }


# --- Starlette HTTP app -----------------------------------------------------


def create_http_app(server: PomodoroServer) -> Starlette:
    async def icon(_request):
        return FileResponse(ICON_PATH)

    async def mobile_page(_request):
        return FileResponse(UI_DIR / "mobile.html")

    routes = [
        Route("/icon.png", icon),
        Route("/mobile", mobile_page),
        WebSocketRoute("/ws", server.handle_websocket),
        WebSocketRoute("/mobile/ws", server.handle_websocket),
        Mount(
            "/",
            app=StaticFiles(directory=str(UI_DIR), html=True),
            name="ui",
        ),
    ]
    return Starlette(routes=routes)


# --- MCP handler factories --------------------------------------------------


def _make_handlers(server: PomodoroServer):
    async def handle_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=TOOLS)

    async def handle_call_tool(_ctx, params) -> types.CallToolResult:
        args = params.arguments or {}
        name = params.name

        if name == "start":
            text = await server.tool_start(
                args.get("intent", ""),
                args.get("duration_min"),
                args.get("agentId", ""),
                args.get("sessionId", ""),
            )
        elif name == "stop":
            text = await server.tool_stop()
        elif name == "query_stats":
            text = server.query_stats()
        elif name == "get_timer_state":
            text = server.get_timer_state()
        else:
            text = f"未知工具: {name}"

        log("INFO", "tool_called", tool=name)
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)]
        )

    return handle_list_tools, handle_call_tool


# --- Dual-channel runner ----------------------------------------------------


async def run() -> None:
    """Start uvicorn HTTP and stdio MCP concurrently."""
    port = int(os.environ.get("APP_PORT", "0"))
    if port == 0:
        log("ERROR", "APP_PORT_not_set")
        sys.exit(1)

    log_init(LOG_PATH)

    server = PomodoroServer()
    http_app = create_http_app(server)

    mcp = Server(
        SOURCE, version="0.2.0", instructions=load_prompt("instructions")
    )
    handle_list, handle_call = _make_handlers(server)
    mcp.add_request_handler(
        "tools/list", types.PaginatedRequestParams, handle_list
    )
    mcp.add_request_handler(
        "tools/call", types.CallToolRequestParams, handle_call
    )

    uv_config = uvicorn.Config(
        app=http_app,
        host="127.0.0.1",
        port=port,
        log_config=None,
        access_log=False,
    )
    uv_server = uvicorn.Server(uv_config)

    log("INFO", "starting_dual_channel", port=port)

    async with stdio_server() as (read_stream, write_stream):
        server.set_write_stream(write_stream)
        log("INFO", "stdio_ready")

        async with anyio.create_task_group() as tg:
            tg.start_soon(
                mcp.run,
                read_stream,
                write_stream,
                mcp.create_initialization_options(),
            )
            tg.start_soon(uv_server.serve)
