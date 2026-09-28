# Agent App Developer Guide

> Language: English | **中文**

This guide is for developers who want to publish an Agent App to the persona-agent marketplace. By the end you should be able to build a publishable Agent App from scratch. It covers only what is specific to apps, and the requirements shared by every MCP product are in the [MCP publishing guide](../mcp/guide.en.md).

## Contents

1. [What is an Agent App](#1-what-is-an-agent-app)
2. [Tech Stack & Runtime Environment](#2-tech-stack--runtime-environment)
3. [Directory Structure](#3-directory-structure)
4. [The mcp.json Config](#4-the-mcpjson-config)
5. [The Dual-Channel Server](#5-the-dual-channel-server)
6. [Lifecycle & Instance Model](#6-lifecycle--instance-model)
7. [Interacting with the Agent](#7-interacting-with-the-agent)
8. [Web UI Development](#8-web-ui-development)
9. [Publishing to the Marketplace](#9-publishing-to-the-marketplace)
10. [Publishing Checklist](#10-publishing-checklist)
11. [FAQ](#11-faq)
12. [Real Examples](#12-real-examples)

---

## 1. What is an Agent App

An Agent App is essentially an **MCP Server + Web UI** combination:

- **The user-facing side** is a Web UI — a visual interface where the user clicks, drags, and types to interact with the Agent
- **The Agent-facing side** is the MCP protocol — a standard MCP Server exposing a set of tools. The Agent never needs to know it is "an app with a UI"; it just sees a tool list and calls it as usual

Your server connects the two sides: user actions on the UI are relayed to the Agent via MCP notifications, and the Agent's responses are fed back to the user through UI updates.

### Overall Architecture

```
┌──────────────────────────────────┐
│  Client (Desktop / Mobile)       │
│  WebView → main server URL       │
└──────────────┬───────────────────┘
               │ HTTP + WebSocket
┌──────────────▼───────────────────┐
│  Main server (persona-agent)     │
│  MCP discovery / proxy / Agent   │
└──────────────┬───────────────────┘
               │ MCP protocol (stdio) + reverse proxy
┌──────────────▼───────────────────┐
│  Your Agent App (own process)    │
│  MCP Server + Web UI + storage   │
└──────────────────────────────────┘
```

Your app is fully autonomous: you decide how to store data, render pages, and push updates. The main server does exactly two things — relay MCP messages, and reverse-proxy `/apps/{name}/` to your HTTP port.

### A Complete Interaction

Using rock-paper-scissors as an example:

```
User clicks "scissors" ──WebSocket──→ Agent App server
                                    │
                     MCP notification: "User has moved, your turn"
                                    │
                               Agent receives
                                    │
                     Tool Use: play_move("rock")
                                    │
                         Agent App judges: rock > scissors
                                    │
                     ┌──────────────┴──────────────┐
                     │                              │
               Web UI update                Agent chat update
          "✌️ vs ✊ you lose"            "Haha I win! Again?"
```

Throughout this flow the Agent uses nothing but standard MCP Tool Use — no special mechanism involved.

## 2. Tech Stack & Runtime Environment

**Backend: any language.** As long as you can implement an MCP stdio Server + an HTTP Server. All currently published apps use Python + [uv](https://docs.astral.sh/uv/); the platform's install pipeline has full support for `runtime: "uv"` products (automatic `uv sync` pre-install), so this is the recommended stack.

**Frontend: any framework.** React, Vue, plain HTML — all fine. The build output is just ordinary static files.

**The rendering environment is a WebView**: Electron's `<webview>` (Chromium) on desktop, `react-native-webview` (WKWebView on iOS, system WebView on Android) on mobile. Both load the **same URL** (the main server's reverse proxy at `/apps/{name}/`); the page is standard HTML/CSS/JS with no platform compatibility issues. Anything Safari / Chrome can run — Canvas, WebGL, three.js, charting libraries — works here.

**Key fact: there is no Node on the user's machine.** All frontend builds must happen at **package time** (before publishing), with the output committed to the repo. At runtime your server only serves static files — users download and run, no build tools needed.

## 3. Directory Structure

An Agent App product lives under `mcp/<name>/` in this repo. Taking the published `rock-paper-scissors` as an example, the **published product** looks like this (browse [mcp/rock-paper-scissors](../../mcp/rock-paper-scissors) to compare):

```
mcp/rock-paper-scissors/
├── mcp.json            ← launch config (see section 4)
├── pyproject.toml      ← dependencies + entry script
├── uv.lock             ← locked dependency versions (reproducible uv sync; must commit)
├── icon.png            ← app icon (marketplace card + runtime app bar share one file)
├── README.md           ← notes for users/authors
├── src/                ← Python backend source
└── ui/                 ← frontend build output (MUST be committed!)
    ├── index.html      ← desktop page
    ├── mobile.html     ← mobile page
    └── assets/
```

### Dev Repo vs Published Product

During development you may keep frontend sources in your own repo; **strip them when publishing** to this marketplace:

| Keep | Strip |
|---|---|
| `mcp.json` / `pyproject.toml` / `uv.lock` | `web/` (frontend sources) |
| `src/` (backend source) | `node_modules/` |
| `ui/` (build output) | `data/` (runtime SQLite data) |
| `icon.png` / `README.md` | log files, `*.egg-info` and other build artifacts |
| | PRDs / dev plans and other process docs |

### Common Pitfalls

- **Don't let `.gitignore` exclude `ui/`.** Fresh frontend projects ignore build output directories (like `dist/`) by default; you must change that so `ui/` gets committed — otherwise you upload an empty shell
- **`uv.lock` must be committed.** The installer runs `uv sync`; without a lockfile dependency resolution is not reproducible
- **Keep runtime data out of the repo.** Write runtime data to `data/` (or similar) and ignore it; it will be generated on the user's machine

## 4. The mcp.json Config

`mcp.json` is your app's launch config. At install time the platform reads it, substitutes the placeholder, and writes it into the user's config. Full template:

```json
{
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--directory", "${SERVERS_DIR}/your-app", "your-app"],
  "agentApp": true,
  "supportedUI": ["desktop", "mobile"]
}
```

Field reference:

| Field | Description |
|---|---|
| `command` / `args` | Launch command. `${SERVERS_DIR}` is a placeholder replaced with the actual install directory on the user's machine |
| `agentApp: true` | **The Agent App marker.** The whole JSON is passed through into the user's config; without this flag your product is just a plain MCP server and never appears in the "Apps" tab or the app bar |
| `supportedUI` | Declares supported UI variants. Fill in at least one of `"desktop"` / `"mobile"`; both if you support both |

The trailing `your-app` in `args` is the entry script declared in `pyproject.toml` (`[project.scripts]`); keeping it identical to the folder name is the simplest choice.

### The Same-Name Rule (hard constraint)

**Folder name === the last segment of the `path` in `mcp/index.json` === the installed `mcp.json` key === the `source` field of MCP notifications.** All four must be the same lowercase-kebab-case string. The platform aligns things by name everywhere; any mismatch breaks installation or gets notifications dropped.

## 5. The Dual-Channel Server

Your process must serve two channels at once:

- **stdio**: MCP protocol traffic — tool listing, tool calls, notifications to the Agent
- **An HTTP port**: serving the static files under `ui/`, plus APIs and a WebSocket for your frontend

### Hard Rules

1. **Start HTTP before MCP.** The platform launches you via MCP `connect()` and registers the reverse proxy as soon as the handshake succeeds. Your HTTP server must be ready by then, or the proxy fails
2. **Read the port from the `APP_PORT` environment variable.** The platform allocates the port and injects it before starting you; exit with an error if it is missing
3. **Never write logs to stdout.** In stdio mode stdout is the MCP protocol channel — a single log line corrupts JSON-RPC. Log to stderr or a file
4. **Exit when the parent process dies.** You are a child of the main server; if it crashes nobody manages you. You must detect the disconnection and terminate to avoid orphan processes hogging ports. In Node.js listen to the IPC channel's `disconnect` event; in Python, the `stdio_server()` task group ends automatically when the stdio streams close, taking the process down with it

### Python Essentials (verified)

The following points are all verified in published apps; following them avoids the main pitfalls:

- Use the mcp SDK's low-level API (`Server` + `stdio_server`); **do NOT use `FastMCP.run()`** — it monopolizes the event loop and the HTTP server never starts
- Run both channels concurrently with `anyio.create_task_group()`; **`asyncio.gather()` does not work** — it is incompatible with anyio task management
- Sending a notification: the `write_stream` returned by `stdio_server()` is an in-memory stream — construct a `SessionMessage(message=JSONRPCNotification(...))` and `await write_stream.send(...)`, no `ServerSession` involved
- uvicorn must be configured with `log_config=None` + `access_log=False`, otherwise its startup logs pollute stdout and break the protocol
- The dependency is `mcp>=2.0.0`; register tools with `server.add_request_handler("tools/list", types.PaginatedRequestParams, handler)` instead of the `@server.list_tools()` decorator

### Minimal Skeleton

Below is a minimal skeleton distilled from [rock-paper-scissors' server.py](../../mcp/rock-paper-scissors/src/rock_paper_scissors/server.py), incorporating every point above — about 100 lines for a fully valid Agent App:

```python
"""Minimal Agent App: MCP server (stdio) + HTTP/WebSocket server."""
import os
import sys
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

APP_ROOT = Path(__file__).resolve().parent.parent.parent
UI_DIR = APP_ROOT / "ui"
ICON_PATH = APP_ROOT / "icon.png"

# Notification source — must match the folder name / mcp.json key (same-name rule)
SOURCE = "your-app"

# Platform-injected params: declare them optional in tool schemas;
# the platform unconditionally fills them on every call
_INJECTED_PARAMS = {
    "agentId": {"type": "string", "description": "Injected by the platform; no need to fill"},
    "sessionId": {"type": "string", "description": "Injected by the platform; no need to fill"},
}

TOOLS = [
    types.Tool(
        name="do_something",
        description="Trigger an action for the Agent",
        inputSchema={
            "type": "object",
            "properties": {
                "arg": {"type": "string"},
                **_INJECTED_PARAMS,
            },
        },
    ),
]

state: dict = {}  # your business state; SQLite recommended for persistence
ws_clients: set[WebSocket] = set()
write_stream_ref: object | None = None


async def handle_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    ws_clients.add(websocket)
    # agentId / sessionId are attached to the URL when the platform loads the WebView
    ctx = (websocket.query_params.get("agentId", ""),
           websocket.query_params.get("sessionId", ""))
    websocket.scope["ctx"] = ctx
    try:
        await websocket.send_json({"type": "init", "state": state})
        while True:
            msg = await websocket.receive_json()
            # user actions from the UI: handle + notify the Agent
            await on_user_action(websocket, msg)
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(websocket)


async def on_user_action(ws: WebSocket, msg: dict) -> None:
    # ...handle the user action, update state...
    agent_id, session_id = ws.scope["ctx"]
    if agent_id and session_id and write_stream_ref is not None:
        notification = types.JSONRPCNotification(
            jsonrpc="2.0",
            method="notifications/app",
            params={
                "agentId": agent_id,
                "sessionId": session_id,
                "source": SOURCE,
                "content": "The user did something; decide the next step",
            },
        )
        await write_stream_ref.send(SessionMessage(message=notification))
    for client in ws_clients:
        await client.send_json({"type": "update", "state": state})


def create_http_app() -> Starlette:
    async def icon(_request):
        return FileResponse(ICON_PATH)  # runtime app-bar icon

    async def mobile_page(_request):
        return FileResponse(UI_DIR / "mobile.html")

    return Starlette(routes=[
        Route("/icon.png", icon),
        Route("/mobile", mobile_page),
        WebSocketRoute("/ws", handle_websocket),
        WebSocketRoute("/mobile/ws", handle_websocket),
        # Static ui/ (index.html + assets/). Must be last so the routes above win
        Mount("/", app=StaticFiles(directory=str(UI_DIR), html=True)),
    ])


async def run() -> None:
    port = int(os.environ.get("APP_PORT", "0"))
    if port == 0:
        print("APP_PORT not set", file=sys.stderr)
        sys.exit(1)

    mcp = Server(SOURCE, version="0.1.0")

    async def handle_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=TOOLS)

    async def handle_call_tool(_ctx, params) -> types.CallToolResult:
        args = params.arguments or {}
        text = f"done: {args.get('arg', '')}"
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=text)]
        )

    mcp.add_request_handler(
        "tools/list", types.PaginatedRequestParams, handle_list_tools
    )
    mcp.add_request_handler(
        "tools/call", types.CallToolRequestParams, handle_call_tool
    )

    uv = uvicorn.Server(uvicorn.Config(
        app=create_http_app(),
        host="127.0.0.1",
        port=port,
        log_config=None,   # keep uvicorn logs off stdout
        access_log=False,
    ))

    global write_stream_ref
    async with stdio_server() as (read_stream, write_stream):
        write_stream_ref = write_stream
        async with anyio.create_task_group() as tg:
            tg.start_soon(uv.serve)  # HTTP first
            tg.start_soon(           # then MCP
                mcp.run, read_stream, write_stream,
                mcp.create_initialization_options(),
            )


if __name__ == "__main__":
    anyio.run(run)
```

HTTP route conventions:

| Route | Purpose |
|---|---|
| `/` | Static hosting of `ui/` (`html=True` makes `/` return `index.html`) |
| `/mobile` | Returns `mobile.html` (loaded by the mobile WebView; its WS URL is derived from its own path, hence the extra `/mobile/ws`) |
| `/icon.png` | Returns the root `icon.png` — the runtime app bar consumes it via the proxied `/apps/{name}/icon.png` |
| `/ws` | Frontend WebSocket |

## 6. Lifecycle & Instance Model

**Your app runs exactly one process globally**, shared by every persona (Agent) that configures it. This implies three things:

1. **Multiple conversations may use your app at the same time.** Tasks from different personas and sessions can interleave — which is exactly why "store sessionId per task" exists (section 7)
2. **There is exactly one copy of persistent data.** All users read and write the same disk location; how you store it is up to you. SQLite is recommended (built-in concurrency locking); **avoid raw JSON files** — concurrent writes to one JSON file corrupt it easily
3. **Persona isolation is your job.** If some data must be separated per persona (e.g. separate save files), the platform provides no persona-scoped storage — design your own layout; the default is shared

The process follows the main server's lifecycle: all registered apps start with it and terminate with it; if your process crashes, the main server notices the broken connection, marks the app "stopped", and cleans up routes — it does not restart you.

## 7. Interacting with the Agent

All interaction goes through the MCP protocol — no platform-proprietary call interfaces. You need to understand four things:

### 7.1 Tool Calls

Expose tools normally via `tools/list`. Visibility is identical to a plain MCP server: personas that configure your app get its tools; the Agent, being an LLM, naturally decides when to call them based on context.

### 7.2 agentId / sessionId Injection

On **every tool call** the platform automatically injects the current conversation's `agentId` and `sessionId` into the tool arguments (unconditionally overwritten — values the model fills in are not trusted). What you do:

- Declare both params as **optional** in tool definitions (see `_INJECTED_PARAMS` in the section 5 skeleton) — the platform always fills them; the model never does
- Read them out of the arguments for bookkeeping and notifications

### 7.3 Store sessionId Per Task (hard rule, the most violated one)

**There is no global "reply address". You must record the sessionId per *thing*:** every task that will produce later notifications (a game, a timer, a divination) stores the then-current `agentId` and `sessionId` in the task's data at creation; all later notifications about that task take the two values from the task. Purely read-only tools (query status, query history) produce no notifications and must not change any task's ownership.

Why this is mandatory — the pomodoro counter-example. Suppose the wrong "notify whoever called last" rule:

1. Persona A's Session A calls `start_timer` (3 min) → timer starts
2. Persona A's Session B calls `list_tasks` (pure query) → the "reply address" wrongly switches to Session B
3. 3 minutes later the reminder lands in Session B — which never asked for a timer

The correct behavior: `start_timer` records "this timer belongs to Session A" at creation; `list_tasks` is just a query and changes nothing; when the timer ends, the notification goes back to Session A.

The other context source: **WebSocket query params**. When loading the WebView, the platform appends `agentId` / `sessionId` to the URL (see the section 5 skeleton); your WS handler reads and binds them to the connection — so a "first-ever user action on the UI" also carries the context needed for notifications, without waiting for the Agent to call a tool first.

### 7.4 Notification Format (fixed four fields)

To inform the Agent of a user action, send an MCP notification with method `notifications/app` and a fixed params shape — **field names are not negotiable**:

```json
{
  "method": "notifications/app",
  "params": {
    "agentId": "id of the owning Agent",
    "sessionId": "id of the Session that started the task",
    "source": "App name (same as the mcp.json key)",
    "content": "natural-language message for the Agent"
  }
}
```

- `sessionId` must not be an empty string (validation drops it)
- Before delivery the main server checks that the sending connection, the declared Agent, and the Session ownership all agree; fabricated values are dropped
- If the target Session has been deleted by the user, the notification is dropped and logged — it is never re-routed to another conversation

### 7.5 Information Boundaries (must-read for game apps)

**A notification should only tell the Agent *what kind of thing happened + what to do next* — never leak information that affects fairness or confidentiality.**

Rock-paper-scissors is the canonical example: after the user moves, the notification says "the user has moved, your turn" — **deliberately without saying what the user played**. If it said "user played scissors", the Agent (an LLM) would simply play the counter-move and always win. The actual moves may only be revealed in tool results after the round is judged.

Principle: what the Agent may know at decision time and what it may know only after judgment are strictly separated.

## 8. Web UI Development

The page is an ordinary web page — no special framework or protocol:

- **Initial data**: `fetch` your own API after load
- **Updates**: keep a WebSocket open; every data change (whether made by the Agent via tools, by the user on the page, or by your own logic) is pushed by your server; the page just re-renders

### Hard Constraints

1. **Static assets must use relative paths.** The page is served under the proxy at `/apps/{name}/`; absolute paths (like Vite's default `/assets/x.js`) 404. Configure `base: './'` in Vite so the output references `./assets/x.js` — the single most common framework pitfall
2. **No `window.open`.** The desktop main process refuses new windows and hands the URL to the system browser, yanking the user out of the panel. Implement popups and sub-views inside the page
3. **Provide both desktop and mobile pages.** `ui/index.html` (desktop) + `ui/mobile.html` (mobile); the mobile WebView loads the `/mobile` path. Declare `supportedUI` in `mcp.json` accordingly

### Development-time Debugging

If your frontend dev server runs on a different port than the backend (e.g. Vite dev server), configure `server.proxy` to forward `/ws` and API routes to the backend port; production builds need none of this.

### The Mobile Request Path (nice to know)

Your HTTP server runs on the **desktop computer**; a phone cannot reach the computer's localhost directly. The actual path:

```
phone WebView's fetch() / WebSocket()
  → Cloudflare Tunnel (public internet)
  → desktop main server
  → /apps/{name}/ prefix → reverse proxy → your HTTP server
```

From the page's perspective this is plain same-origin — write relative paths and let the main server forward by prefix; you don't care which client the user opened.

### Heavy Frontends (WebGL / three.js etc.)

Architecturally unrestricted (the WebView is the same engine as Safari / Chrome, with WebGL and hardware acceleration), but mind the engineering side: three.js plus models easily reaches several MB and loads slowly over the mobile tunnel — compress / split; low-end Android GPUs are weak — reduce geometry and simplify shaders; build a dedicated mobile-tuned variant for heavy 3D scenes.

## 9. Publishing to the Marketplace

### 9.1 Place the Product

Products live under `mcp/<name>/` in this repo (structure per section 3). **There is no separate `apps/` directory** — an Agent App is simply an MCP product with the `agentApp: true` marker; the marketplace uses that field to bucket it into the "Apps" tab (without the marker it is a plain "MCP" tab product).

### 9.2 Register It (mcp/index.json)

Append an entry in the existing format to this repo's [`mcp/index.json`](../../mcp/index.json):

```json
{
  "name": "Your App display name",
  "description": "One-line summary shown on the marketplace card",
  "author": "your name",
  "homepage": "https://github.com/Code-MonkeyZhang/persona-agent-marketplace/tree/main/mcp/your-app",
  "path": "mcp/your-app",
  "logo": "icon.png",
  "runtime": "uv",
  "agentApp": true
}
```

| Field | Description |
|---|---|
| `name` / `description` | Display name and summary on the marketplace card |
| `path` | Product path; its last segment must equal the folder name (same-name rule) |
| `logo` | Marketplace card icon, pointing at the product's `icon.png` |
| `runtime: "uv"` | Declares the uv runtime; install runs `uv sync` to pre-install dependencies |
| `agentApp: true` | **The Agent App marker** — the only thing that puts you in the "Apps" tab |

### 9.3 One Icon, Two Consumers

`icon.png` is consumed in two places; verify both render before publishing:

- **Marketplace card**: referenced via the `logo` field in `index.json` (downloaded and shown locally at install)
- **Runtime app bar**: via the proxied `/apps/{name}/icon.png`, served by your HTTP server (the `/icon.png` route in the section 5 skeleton)

### 9.4 Submit

Fork this repo → add the product directory + register in `index.json` → open a Pull Request. **Do not use Git LFS** (it breaks the app's raw download mechanism).

## 10. Publishing Checklist

Tick every item before publishing:

- [ ] Folder name === `index.json` path's last segment === `mcp.json` key === notification `source` (same-name rule)
- [ ] `mcp.json` contains `agentApp: true` + an honest `supportedUI`
- [ ] `ui/` build output committed (not excluded by `.gitignore`)
- [ ] `uv.lock` committed
- [ ] Stripped: `web/` sources, `node_modules/`, `data/`, logs, `*.egg-info`, process docs
- [ ] All frontend assets use relative paths (Vite `base: './'`)
- [ ] No `window.open` in the Web UI
- [ ] Both desktop (`index.html`) and mobile (`mobile.html`) pages provided (if declared in `supportedUI`)
- [ ] HTTP starts before MCP; port read from `APP_PORT`
- [ ] Nothing written to stdout (logs go to stderr / file)
- [ ] `agentId` / `sessionId` declared optional in tool definitions
- [ ] Every notification-producing task records `sessionId` + `agentId` at creation (no global reply address)
- [ ] Notifications carry the fixed four fields `agentId` / `sessionId` / `source` / `content`; `sessionId` never empty
- [ ] Game apps: notifications leak no fairness-affecting information
- [ ] Persistence uses SQLite (or an equally concurrency-safe scheme), not raw JSON writes
- [ ] Process self-terminates when the parent dies (no orphans)
- [ ] `icon.png` exists and renders via both the card and runtime paths
- [ ] No Git LFS

## 11. FAQ

**Q: What is the Agent App UI, essentially?**
An ordinary web page rendered inside an embedded browser engine: Electron `<webview>` (Chromium) on desktop, `react-native-webview` (WKWebView / system WebView) on mobile. Both load the same URL; the page is standard HTML/CSS/JS.

**Q: Which frontend technologies work? Does three.js / WebGL run?**
Yes. The WebView uses the same engine as Safari / Chrome, with WebGL and hardware acceleration. The protocol layer (MCP tool calls, notifications) and the rendering layer are fully decoupled — Agent calls a tool → your server mutates data → WebSocket pushes → the page repaints; 3D drawing happens entirely client-side. The bottleneck is load performance over the mobile tunnel and phone GPUs (see section 8).

**Q: How does the page talk to the backend?**
Like any web app: `fetch()` request-response for initial data, a persistent WebSocket for pushed updates. Do not poll with fetch.

**Q: How do mobile requests reach my server?**
Phone WebView → Cloudflare Tunnel → desktop main server → `/apps/{name}/` prefix reverse proxy → your HTTP server. Same-origin from the page's perspective — just use relative paths (see section 8).

**Q: How is this different from opening the page in a browser?**
Protocol-wise, not at all. The differences are environmental: the WebView has no address bar / tabs / back-forward, the URL is fixed by the host app, and storage is partitioned away from the system browser. You build your own back/refresh affordances inside the page.

**Q: A user has multiple Agent personas — will data cross over?**
Data is globally single-copy by default (see section 6). Messages do not cross over — provided you follow "store sessionId per task" (section 7.3). For per-persona data isolation, design your own storage layout.

## 12. Real Examples

Three published Agent Apps in this repo, each demonstrating a typical shape — recommended references during development:

| Product | Demonstrates |
|---|---|
| [mcp/rock-paper-scissors](../../mcp/rock-paper-scissors) | Games: minimal complete dual-channel implementation, notification information boundaries (never leaks the user's move), WS query params carrying agentId/sessionId |
| [mcp/pomodoro-timer](../../mcp/pomodoro-timer) | Timers & notifications: the model student of "store sessionId per task" (the end-of-timer notification returns to the conversation that started it), SQLite statistics |
| [mcp/health-manager](../../mcp/health-manager) | Data recording: Agent records data in chat, the panel updates trend charts automatically, dual-UI |

All three include complete `mcp.json` / `pyproject.toml` / `uv.lock` / `ui/` outputs and work as structural templates for your product.
