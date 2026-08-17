"""
Rock-Paper-Scissors Agent App server (best-of-3).

Runs two channels in one process via anyio task group:
- stdio MCP: exposes tools to the Agent, sends notifications on user moves
  and on rematch requests
- uvicorn HTTP: serves the built Web UI as static files, WebSocket for
  real-time match state

Both channels share a single RpsServer instance (in-memory match state +
SQLite history), so a user's WS move/rematch can trigger an MCP notification,
and an Agent's tool call can push a WS update — all within one event loop.
"""

from __future__ import annotations

import os
import sys
import uuid
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

from .db import HistoryDB
from .game import (
    MOVE_LABELS,
    RESULT_TEXT,
    WINS_NEEDED,
    GameState,
    judge,
    match_winner,
)
from .log import initialize as log_init, log
from .prompts import load_prompt

APP_ROOT = Path(__file__).resolve().parent.parent.parent
UI_DIR = APP_ROOT / "ui"
ICON_PATH = APP_ROOT / "icon.png"
DATA_DIR = APP_ROOT / "data"
LOG_PATH = APP_ROOT / "rps.log"

VALID_MOVES = {"rock", "paper", "scissors"}

# MCP notification source — must match the mcp.json key
SOURCE = "rock-paper-scissors"

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
        name="start_game",
        description=load_prompt("start_game"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
    types.Tool(
        name="play_move",
        description=load_prompt("play_move"),
        inputSchema={
            "type": "object",
            "required": ["move"],
            "properties": {
                "move": {
                    "type": "string",
                    "enum": ["rock", "paper", "scissors"],
                    "description": "你的出招",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="get_game_state",
        description=load_prompt("get_game_state"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
    types.Tool(
        name="get_game_history",
        description=load_prompt("get_game_history"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
    types.Tool(
        name="end_game",
        description=load_prompt("end_game"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
]


# --- Shared server state ----------------------------------------------------


class RpsServer:
    """Holds match state, DB, and bridges between MCP and WS channels."""

    def __init__(self) -> None:
        self.db = HistoryDB(DATA_DIR / "history.db")
        self.state: GameState | None = None
        self._write_stream: object | None = None
        # 每条 WS 连接绑定其 (agentId, sessionId)，由 webview URL 的 query 参数传入。
        # 平台不通过 env 注入 agent/session，只能从工具调用或 WS 连接获取；
        # WS query 让"用户首次操作"也能立即带上通知所需的上下文。
        self._ws_clients: dict[WebSocket, tuple[str, str]] = {}

    def set_write_stream(self, stream: object) -> None:
        self._write_stream = stream

    # --- MCP tool handlers ---

    async def start_game(self, agent_id: str, session_id: str) -> str:
        """Start a new best-of-3 match. Ends the previous one if it exists."""
        if self.state:
            self.db.end_game(
                self.state.game_id,
                self.state.user_score,
                self.state.agent_score,
                self.state.winner,
            )
            log(
                "INFO",
                "previous_match_ended",
                game_id=self.state.game_id,
            )

        game_id = str(uuid.uuid4())
        self.state = GameState(
            game_id=game_id, agent_id=agent_id, session_id=session_id
        )
        self.db.start_game(game_id, agent_id, session_id)
        log(
            "INFO",
            "match_started",
            game_id=game_id,
            agent_id=agent_id,
            session_id=session_id,
        )

        await self._push_state()
        return (
            f"游戏已开始！三局两胜，先赢{WINS_NEEDED}局者获胜。"
            "请用户在右侧面板出招。"
        )

    async def _end_current_match(self, by: str) -> None:
        """End the in-progress match as a forfeit (winner=None).

        Shared by the MCP end_game tool and the WS end_game button.
        Caller must guard: only call when a match exists and is in progress.
        """
        self.state.game_over = True
        self.state.waiting_for_agent = False
        self.state.user_move_pending = None
        self.db.end_game(
            self.state.game_id,
            self.state.user_score,
            self.state.agent_score,
            None,
        )
        log(
            "INFO",
            "match_ended_by_request",
            by=by,
            game_id=self.state.game_id,
            score=f"{self.state.user_score}:{self.state.agent_score}",
        )
        await self._push_state()

    async def end_game(self) -> str:
        """End the current match as a forfeit (Agent-initiated)."""
        if not self.state:
            return "暂无比赛进行中"
        if self.state.game_over:
            return "整场已结束，请调用 start_game 开始新一场"
        await self._end_current_match(by="agent")
        return (
            f"本局已结束（中途结束），"
            f"最终比分 用户{self.state.user_score}:"
            f"Agent{self.state.agent_score}"
        )

    async def play_move(
        self, move: str, agent_id: str, session_id: str
    ) -> str:
        """Judge the Agent's move against the user's pending move (best-of-3)."""
        if not self.state:
            return "比赛还没开始，请先调用 start_game"
        if self.state.game_over:
            return "整场已结束，请调用 start_game 开始新一场"
        if not self.state.waiting_for_agent or not self.state.user_move_pending:
            return "用户还没出招，请等待用户出招后再调用 play_move"
        if move not in VALID_MOVES:
            return f"无效的出招: {move}，请使用 rock/paper/scissors"

        user_move = self.state.user_move_pending
        result = judge(user_move, move)

        self.state.last_user_move = user_move
        self.state.last_agent_move = move
        self.state.last_result = result

        # 平局：重出，不计分、不推进局号
        if result == "draw":
            self.db.add_round(
                self.state.game_id,
                self.state.round_no,
                user_move,
                move,
                result,
                self.state.user_score,
                self.state.agent_score,
            )
            self.state.waiting_for_agent = False
            self.state.user_move_pending = None
            log(
                "INFO",
                "round_draw",
                round=self.state.round_no,
                score=f"{self.state.user_score}:{self.state.agent_score}",
            )
            await self._push_state()
            return (
                f"第{self.state.round_no}局："
                f"你出了{MOVE_LABELS[move]},"
                f"用户出了{MOVE_LABELS[user_move]},"
                f"平局，重出！"
                f"当前比分 用户{self.state.user_score}:"
                f"Agent{self.state.agent_score}"
            )

        # 分胜负：胜方计 1 分
        if result == "user_win":
            self.state.user_score += 1
        else:
            self.state.agent_score += 1

        self.db.add_round(
            self.state.game_id,
            self.state.round_no,
            user_move,
            move,
            result,
            self.state.user_score,
            self.state.agent_score,
        )

        reply_prefix = (
            f"第{self.state.round_no}局："
            f"你出了{MOVE_LABELS[move]},"
            f"用户出了{MOVE_LABELS[user_move]},"
            f"{RESULT_TEXT[result]}！"
        )

        # 检查整场胜负
        winner = match_winner(self.state.user_score, self.state.agent_score)
        if winner:
            self.state.game_over = True
            self.state.winner = winner
            self.db.end_game(
                self.state.game_id,
                self.state.user_score,
                self.state.agent_score,
                winner,
            )
            verdict = "你赢了整场！" if winner == "agent" else "用户赢了整场！"
            log(
                "INFO",
                "match_over",
                winner=winner,
                score=f"{self.state.user_score}:{self.state.agent_score}",
            )
            reply = (
                f"{reply_prefix}整场结束，{verdict}"
                f"最终比分 用户{self.state.user_score}:"
                f"Agent{self.state.agent_score}"
            )
        else:
            self.state.round_no += 1
            reply = (
                f"{reply_prefix}"
                f"当前比分 用户{self.state.user_score}:"
                f"Agent{self.state.agent_score}"
            )

        self.state.waiting_for_agent = False
        self.state.user_move_pending = None

        await self._push_state()
        return reply

    def get_game_state(self) -> str:
        if not self.state:
            return "暂无比赛进行中"
        if self.state.game_over:
            verdict = "你赢" if self.state.winner == "agent" else "用户赢"
            return (
                f"整场已结束，{verdict}，"
                f"最终比分 用户{self.state.user_score}:"
                f"Agent{self.state.agent_score}。"
                f"调用 start_game 开始新一场"
            )
        turn = (
            "轮到你出招"
            if self.state.waiting_for_agent
            else "等待用户出招"
        )
        return (
            f"当前比分 用户{self.state.user_score}:"
            f"Agent{self.state.agent_score},"
            f"第{self.state.round_no}局（三局两胜）,{turn}"
        )

    def get_game_history(self) -> str:
        history = self.db.get_history()
        if not history:
            return "暂无历史记录"

        parts = [f"共{len(history)}场"]
        for i, game in enumerate(history, 1):
            u, a = game["userScore"], game["agentScore"]
            if not game["endedAt"]:
                status = "进行中"
            elif game["winner"] == "user":
                status = "用户胜"
            elif game["winner"] == "agent":
                status = "Agent胜"
            else:
                status = "中途结束"
            parts.append(
                f"第{i}场 {u}:{a} {status}"
                f"（{len(game['rounds'])}轮）"
            )
        return "。".join(parts)

    # --- WebSocket handler ---

    async def handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        agent_id = websocket.query_params.get("agentId", "")
        session_id = websocket.query_params.get("sessionId", "")
        self._ws_clients[websocket] = (agent_id, session_id)
        log(
            "INFO",
            "ws_connected",
            clients=len(self._ws_clients),
            has_context=bool(agent_id and session_id),
        )

        await websocket.send_json(
            {
                "type": "init",
                "state": self.state.to_dict() if self.state else None,
                "history": self.db.get_history(completed_only=True),
            }
        )

        try:
            while True:
                msg = await websocket.receive_json()
                mtype = msg.get("type")
                if mtype == "move":
                    await self._on_user_move(websocket, msg.get("move", ""))
                elif mtype == "rematch":
                    await self._on_rematch(websocket)
                elif mtype == "start_game":
                    await self._on_start_game(websocket)
                elif mtype == "end_game":
                    await self._on_end_game(websocket)
        except WebSocketDisconnect:
            pass
        except Exception as e:
            log("WARN", "ws_error", error=str(e))
        finally:
            self._ws_clients.pop(websocket, None)
            log(
                "INFO",
                "ws_disconnected",
                clients=len(self._ws_clients),
            )

    # --- Internal helpers ---

    async def _push_state(self) -> None:
        """Broadcast current match state + completed history to all WS clients."""
        await self._broadcast_ws(
            {
                "type": "update",
                "state": self.state.to_dict() if self.state else None,
                "history": self.db.get_history(completed_only=True),
            }
        )

    async def _on_user_move(self, ws: WebSocket, move: str) -> None:
        """Record the user's move and notify the Agent."""
        if move not in VALID_MOVES:
            log("WARN", "invalid_move", move=move)
            return

        if not self.state or self.state.game_over:
            log("WARN", "move_ignored", reason="no match or match over")
            return
        if self.state.waiting_for_agent:
            log("WARN", "move_ignored", reason="not user's turn")
            return

        self.state.user_move_pending = move
        self.state.last_user_move = move
        self.state.waiting_for_agent = True

        await self._send_notification(ws, "用户已出招，轮到你出招了")
        await self._push_state()

    async def _on_rematch(self, ws: WebSocket) -> None:
        """User clicked 'rematch' — notify the Agent to start a new match."""
        if not self.state or not self.state.game_over:
            log(
                "WARN",
                "rematch_ignored",
                reason="no finished match to rematch",
            )
            return
        await self._send_notification(
            ws, "用户想再来一局，请调用 start_game 开始新一场"
        )
        log("INFO", "rematch_requested")

    async def _on_start_game(self, ws: WebSocket) -> None:
        """User clicked 'start game' — notify the Agent to begin a match."""
        if self.state and not self.state.game_over:
            log("WARN", "start_ignored", reason="match in progress")
            return
        await self._send_notification(
            ws, "用户想开始一局剪刀石头布，请调用 start_game"
        )
        log("INFO", "start_game_requested")

    async def _on_end_game(self, ws: WebSocket) -> None:
        """User clicked 'end game' — end the match immediately and notify Agent."""
        if not self.state or self.state.game_over:
            log("WARN", "end_game_ignored", reason="no match or match over")
            return
        await self._send_notification(ws, "用户已结束本局（中途结束）")
        await self._end_current_match(by="user")

    async def _send_notification(
        self, ws: WebSocket, content: str
    ) -> None:
        """Push a notifications/app message through the stdio write stream.

        Context (agentId/sessionId) comes from the triggering WS connection's
        query params — set by the desktop when it loads the app webview. Falls
        back to skipping with a warning if the platform didn't pass context.
        """
        if not self._write_stream:
            log("WARN", "notification_skipped", reason="no write_stream")
            return

        agent_id, session_id = self._ws_clients.get(ws, ("", ""))
        if not agent_id or not session_id:
            log("WARN", "notification_skipped", reason="no agent/session context")
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


# --- Starlette HTTP app -----------------------------------------------------


def create_http_app(server: RpsServer) -> Starlette:
    async def icon(_request):
        return FileResponse(ICON_PATH)

    async def mobile_page(_request):
        return FileResponse(UI_DIR / "mobile.html")

    routes = [
        Route("/icon.png", icon),
        Route("/mobile", mobile_page),
        WebSocketRoute("/ws", server.handle_websocket),
        # Mobile page derives its WS URL from its own path (/mobile → /mobile/ws),
        # so expose a second WS endpoint sharing the same handler.
        WebSocketRoute("/mobile/ws", server.handle_websocket),
        # Static UI build (index.html + assets/). html=True serves
        # index.html at "/". Must be last so /icon.png, /mobile, /ws win first.
        Mount(
            "/",
            app=StaticFiles(directory=str(UI_DIR), html=True),
            name="ui",
        ),
    ]
    return Starlette(routes=routes)


# --- MCP handler factories --------------------------------------------------


def _make_handlers(server: RpsServer):
    async def handle_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=TOOLS)

    async def handle_call_tool(_ctx, params) -> types.CallToolResult:
        args = params.arguments or {}
        name = params.name

        if name == "start_game":
            text = await server.start_game(
                args.get("agentId", ""), args.get("sessionId", "")
            )
        elif name == "play_move":
            text = await server.play_move(
                args.get("move", ""),
                args.get("agentId", ""),
                args.get("sessionId", ""),
            )
        elif name == "get_game_state":
            text = server.get_game_state()
        elif name == "get_game_history":
            text = server.get_game_history()
        elif name == "end_game":
            text = await server.end_game()
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

    server = RpsServer()
    http_app = create_http_app(server)

    mcp = Server(SOURCE, version="0.1.0", instructions=load_prompt("instructions"))
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
