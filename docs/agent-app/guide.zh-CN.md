# Agent App 开发指南

> 语言：**中文** | [English](./guide.en.md)

这份指南面向想在 persona-agent 商城发布 Agent App 的开发者。读完它，你应该能从零写出一个可以上架的 Agent App。

## 目录

1. [什么是 Agent App](#1-什么是-agent-app)
2. [技术选型与运行环境](#2-技术选型与运行环境)
3. [目录结构](#3-目录结构)
4. [配置 mcp.json](#4-配置-mcpjson)
5. [双通道服务器](#5-双通道服务器)
6. [生命周期与实例模型](#6-生命周期与实例模型)
7. [与 Agent 交互](#7-与-agent-交互)
8. [Web UI 开发](#8-web-ui-开发)
9. [发布到商城](#9-发布到商城)
10. [发布 Checklist](#10-发布-checklist)
11. [FAQ](#11-faq)
12. [真实示例](#12-真实示例)

---

## 1. 什么是 Agent App

Agent App 本质上是 **MCP Server + Web UI** 的组合：

- **面向用户的一面**是 Web UI——一个可视化界面，用户点击、拖拽、输入，直接和 Agent 互动
- **面向 Agent 的一面**是 MCP 协议——一个标准的 MCP Server，暴露一组工具。Agent 不需要知道这是个"有界面的 App"，它只看到工具列表，正常调用即可

两面由你的服务器连接：用户在界面上的操作经 MCP 通知传达给 Agent；Agent 的回应通过界面更新反馈给用户。

### 整体架构

```
┌──────────────────────────────────┐
│  客户端（Desktop / Mobile）       │
│  WebView → 主服务器 URL           │
└──────────────┬───────────────────┘
               │ HTTP + WebSocket
┌──────────────▼───────────────────┐
│  主服务器（persona-agent）        │
│  MCP 发现 / 反向代理 / Agent 调度 │
└──────────────┬───────────────────┘
               │ MCP 协议（stdio）+ 反向代理
┌──────────────▼───────────────────┐
│  你的 Agent App（独立进程）        │
│  MCP Server + Web UI + 数据存储   │
└──────────────────────────────────┘
```

你的 App 完全自治：自己决定怎么存数据、怎么渲染页面、怎么推送更新。主服务器只做两件事——MCP 消息转发，以及把 `/apps/{name}/` 反向代理到你的 HTTP 端口。

### 一次完整交互

以剪刀石头布为例：

```
用户点击"剪刀" ──WebSocket──→ Agent App 服务器
                                    │
                     MCP 通知："用户已出招，轮到你出招了"
                                    │
                               Agent 收到消息
                                    │
                     Tool Use：play_move("石头")
                                    │
                         Agent App 判定：石头 > 剪刀
                                    │
                     ┌──────────────┴──────────────┐
                     │                              │
               Web UI 更新                  Agent 对话更新
          "✌️ vs ✊ 你输了"            "哈哈我赢了！再来？"
```

整个流程中 Agent 走的是完全标准的 MCP Tool Use，不需要任何特殊机制。

## 2. 技术选型与运行环境

**后端：任意语言。** 只要能实现 MCP stdio Server + HTTP Server 即可。目前所有已上架 App 均为 Python + [uv](https://docs.astral.sh/uv/)，平台安装链路对 `runtime: "uv"` 商品有完整支持（自动 `uv sync` 预装依赖），推荐照此选型。

**前端：任意框架。** React、Vue、纯 HTML 都行。构建后的产物就是普通静态文件。

**渲染环境是 WebView**：桌面端用 Electron 的 `<webview>`（Chromium 内核），移动端用 `react-native-webview`（iOS 为 WKWebView，Android 为系统 WebView）。两端加载的是**同一个 URL**（主服务器反向代理的 `/apps/{name}/`），页面是标准 HTML/CSS/JS，不存在平台兼容问题。凡是 Safari / Chrome 能跑的技术——Canvas、WebGL、three.js、数据可视化库——都能跑。

**关键认知：用户机器上没有 Node。** 你的一切前端构建必须在**打包期**（发布前）完成，产物提交进仓库。运行时你的服务器只做静态文件托管，用户下载即跑，不需要任何构建工具。

## 3. 目录结构

Agent App 商品放在本仓 `mcp/<name>/` 下。以已上架的 `rock-paper-scissors` 为例，**发布物**结构如下（可直接浏览 [mcp/rock-paper-scissors](../../mcp/rock-paper-scissors) 对照）：

```
mcp/rock-paper-scissors/
├── mcp.json            ← 启动配置（见第 4 节）
├── pyproject.toml      ← 依赖声明 + 入口脚本
├── uv.lock             ← 锁定依赖版本（保证 uv sync 可复现，必须提交）
├── icon.png            ← App 图标（商城卡片 + 运行时 App 栏共用一份）
├── README.md           ← 面向用户/作者的说明
├── src/                ← Python 后端源码
└── ui/                 ← 前端构建产物（必须随仓库提交！）
    ├── index.html      ← 桌面端页面
    ├── mobile.html     ← 移动端页面
    └── assets/
```

### 开发仓 vs 发布物

开发时你可以在自己的仓库里保留前端源码；**发布到商城时必须剥离**：

| 保留 | 剥离 |
|---|---|
| `mcp.json` / `pyproject.toml` / `uv.lock` | `web/`（前端源码） |
| `src/`（后端源码） | `node_modules/` |
| `ui/`（构建产物） | `data/`（运行时 SQLite 数据） |
| `icon.png` / `README.md` | 日志文件、`*.egg-info` 等构建产物 |
| | PRD / 开发计划等过程文档 |

### 易踩的坑

- **`.gitignore` 勿排除 `ui/`**。新建前端项目的 `.gitignore` 默认排除构建输出目录（如 `dist/`），商品化时必须改为允许提交 `ui/`，否则上传的是空壳
- **`uv.lock` 必须提交**。安装时平台执行 `uv sync`，没有锁文件就无法保证依赖可复现
- **数据目录不要进仓库**。运行时数据写在 `data/`（或类似目录）并在 `.gitignore` 排除即可，用户机器上会自动生成

## 4. 配置 mcp.json

`mcp.json` 是你的 App 的启动配置，安装时平台读取它、替换占位符后写入用户配置。完整模板：

```json
{
  "type": "stdio",
  "command": "uv",
  "args": ["run", "--directory", "${SERVERS_DIR}/your-app", "your-app"],
  "agentApp": true,
  "supportedUI": ["desktop", "mobile"]
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `command` / `args` | 启动命令。`${SERVERS_DIR}` 是占位符，安装时替换为用户机器上的实际安装目录 |
| `agentApp: true` | **Agent App 的身份标记**。整份 JSON 会透传进用户配置，没有它就只是一个普通 MCP Server，不会出现在「应用」Tab 和 App 栏 |
| `supportedUI` | 声明支持的界面形态。`"desktop"` / `"mobile"` 至少填一个，两个都支持就都填 |

`args` 末段的 `your-app` 是 `pyproject.toml` 里声明的入口脚本名（`[project.scripts]`），保持与文件夹名一致最省心。

### 三级同名约定（硬约束）

**文件夹名 === `mcp/index.json` 条目 `path` 的末段 === 安装后 `mcp.json` 的 key === MCP 通知的 `source` 字段值。** 四者必须是同一个字符串（lowercase kebab-case）。平台多处按名字对齐，任何一处不一致都会导致安装失败或通知被丢弃。

## 5. 双通道服务器

你的进程需要同时提供两个通道：

- **stdio**：MCP 协议通信——工具列表返回、工具调用处理、给 Agent 发通知
- **HTTP 端口**：托管 `ui/` 静态文件、给你的前端提供 API 和 WebSocket

### 硬性规则

1. **先启动 HTTP，再启动 MCP。** 平台通过 MCP 的 `connect()` 启动你，握手成功后立即注册反向代理。此时你的 HTTP 服务必须已就绪，否则代理失败
2. **端口从环境变量 `APP_PORT` 读取。** 平台启动你之前会分配好端口并注入；读不到就直接退出报错
3. **stdout 禁止写任何日志。** stdio 模式下 stdout 是 MCP 协议通道，一行日志就会破坏 JSON-RPC。日志走 stderr 或写文件
4. **父进程退出时自行终止。** 你是主服务器的子进程，主服务器崩溃后没人管你——必须检测到连接断开就退出，避免遗留孤儿进程占用端口。Node.js 监听 IPC channel 的 `disconnect` 事件；Python 下 stdio 流关闭时 `stdio_server()` 所在任务组会自动结束，进程随之退出

### Python 实现要点（已验证）

以下要点在已上架 App 中全部验证过，照做可以避开主要深坑：

- 用 mcp SDK 的低层 API（`Server` + `stdio_server`），**不要用 `FastMCP.run()`**——它会独占事件循环，HTTP 服务起不来
- 两个通道用 `anyio.create_task_group()` 并发，**不能用 `asyncio.gather()`**——后者与 anyio 任务管理不兼容
- 给 Agent 发通知：`stdio_server()` 返回的 `write_stream` 是内存流，直接构造 `SessionMessage(message=JSONRPCNotification(...))` 然后 `await write_stream.send(...)`，不经过 `ServerSession`
- uvicorn 必须设 `log_config=None` + `access_log=False`，否则启动日志污染 stdout 破坏协议
- 当前依赖 `mcp>=2.0.0`，工具注册用 `server.add_request_handler("tools/list", types.PaginatedRequestParams, handler)` 而非 `@server.list_tools()` 装饰器

### 最小骨架

下面是从 [rock-paper-scissors 的 server.py](../../mcp/rock-paper-scissors/src/rock_paper_scissors/server.py) 提炼的最小骨架，融合了上述全部要点，约 100 行即可跑起一个合法的 Agent App：

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

# 通知的 source —— 必须与文件夹名 / mcp.json 的 key 一致（三级同名）
SOURCE = "your-app"

# 平台注入的参数：工具 schema 里声明为可选，平台每次调用会无条件补上
_INJECTED_PARAMS = {
    "agentId": {"type": "string", "description": "平台自动注入，无需填写"},
    "sessionId": {"type": "string", "description": "平台自动注入，无需填写"},
}

TOOLS = [
    types.Tool(
        name="do_something",
        description="让 Agent 触发某个动作",
        inputSchema={
            "type": "object",
            "properties": {
                "arg": {"type": "string"},
                **_INJECTED_PARAMS,
            },
        },
    ),
]

state: dict = {}  # 你的业务状态；持久化推荐 SQLite
ws_clients: set[WebSocket] = set()
write_stream_ref: object | None = None


async def handle_websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    ws_clients.add(websocket)
    # agentId / sessionId 由平台加载 WebView 时写进 URL query，通知时要用
    ctx = (websocket.query_params.get("agentId", ""),
           websocket.query_params.get("sessionId", ""))
    websocket.scope["ctx"] = ctx
    try:
        await websocket.send_json({"type": "init", "state": state})
        while True:
            msg = await websocket.receive_json()
            # 用户在界面上的操作：处理 + 通知 Agent
            await on_user_action(websocket, msg)
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(websocket)


async def on_user_action(ws: WebSocket, msg: dict) -> None:
    # ...处理用户操作、更新 state...
    agent_id, session_id = ws.scope["ctx"]
    if agent_id and session_id and write_stream_ref is not None:
        notification = types.JSONRPCNotification(
            jsonrpc="2.0",
            method="notifications/app",
            params={
                "agentId": agent_id,
                "sessionId": session_id,
                "source": SOURCE,
                "content": "用户做了某个操作，请决定下一步",
            },
        )
        await write_stream_ref.send(SessionMessage(message=notification))
    for client in ws_clients:
        await client.send_json({"type": "update", "state": state})


def create_http_app() -> Starlette:
    async def icon(_request):
        return FileResponse(ICON_PATH)  # App 栏运行时图标

    async def mobile_page(_request):
        return FileResponse(UI_DIR / "mobile.html")

    return Starlette(routes=[
        Route("/icon.png", icon),
        Route("/mobile", mobile_page),
        WebSocketRoute("/ws", handle_websocket),
        WebSocketRoute("/mobile/ws", handle_websocket),
        # 静态 ui/（index.html + assets/）。必须放最后，让上面的路由优先
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
        log_config=None,   # 禁止 uvicorn 日志污染 stdout
        access_log=False,
    ))

    global write_stream_ref
    async with stdio_server() as (read_stream, write_stream):
        write_stream_ref = write_stream
        async with anyio.create_task_group() as tg:
            tg.start_soon(uv.serve)  # 先 HTTP
            tg.start_soon(           # 再 MCP
                mcp.run, read_stream, write_stream,
                mcp.create_initialization_options(),
            )


if __name__ == "__main__":
    anyio.run(run)
```

HTTP 路由约定说明：

| 路由 | 作用 |
|---|---|
| `/` | 静态托管 `ui/`（`html=True` 使 `/` 返回 `index.html`） |
| `/mobile` | 返回 `mobile.html`（移动端 WebView 加载这个路径；其 WS 地址按自身路径推导，所以同时暴露 `/mobile/ws`） |
| `/icon.png` | 返回根目录 `icon.png`——运行时 App 栏图标经反向代理 `/apps/{name}/icon.png` 消费的就是它 |
| `/ws` | 前端 WebSocket |

## 6. 生命周期与实例模型

**你的 App 全局只跑一份进程**，所有配置了它的人格（Agent）共用这一份。这决定了三件事：

1. **多段对话可能同时使用你的 App。** 不同人格、不同会话发起的任务会交织到达——这就是第 7 节"按任务存 sessionId"存在的原因
2. **持久化数据只有一份。** 所有使用方读写同一个磁盘位置，怎么存由你决定。推荐 SQLite（自带并发锁）；**避免裸写 JSON 文件**——多个任务同时写同一个 JSON 很容易写坏
3. **人格隔离需要你自己做。** 如果某些数据要按人格分开存（比如不同人格的存档），平台不提供人格标识的存储分区，需要你自行约定存储布局；默认行为是共享

进程随主服务器启动与退出：主服务器启动时拉起所有已注册 App，退出时全体终止；你的进程崩溃时，主服务器会感知到连接断开，把 App 标记为「已停止」并清理路由，不会自动重启。

## 7. 与 Agent 交互

交互完全走 MCP 协议，没有任何平台私有的调用接口。你只需要理解四件事：

### 7.1 工具调用

在 `tools/list` 里正常暴露工具。可见性与普通 MCP Server 一致：人格配置里加了你的 App，该人格的 Agent 就能看到并调用你的工具；Agent 是 LLM，会根据对话上下文自然决定何时调用。

### 7.2 agentId / sessionId 的注入

平台在**每次工具调用**时，自动把当前对话的 `agentId` 和 `sessionId` 注入到工具参数里（无条件覆盖，不信任模型填的值）。你要做的是：

- 工具定义里把这两个参数声明为**可选**（见第 5 节骨架的 `_INJECTED_PARAMS`）——平台一定补上，模型不会填
- 从参数里取出它们，用于记账和发通知

### 7.3 按任务存 sessionId（硬约定，最容易违反的一条）

**不存在全局的"回话地址"。你必须按"事情"记录 sessionId**：每个会产生后续通知的任务（一局游戏、一个计时器、一次占卜），在创建时就把当时的 `agentId` 和 `sessionId` 存进这个任务的数据里；之后与该任务有关的所有通知，都从任务里取出这两个值发送。纯查询类工具（查状态、查历史）不产生通知，也不改变任何任务的归属。

为什么必须这样——番茄时钟反例。假设用错误的"谁最后调用了工具就通知谁"规则：

1. 人格甲的 Session A 调用 `start_timer`（3 分钟）→ 计时器启动
2. 人格甲的 Session B 调用 `list_tasks`（纯查询）→ "回话地址"被错误地切到 Session B
3. 3 分钟后计时结束，提醒发到了 Session B——而 Session B 从未交代过这个计时

正确做法：`start_timer` 创建计时器时记下"它属于 Session A"，`list_tasks` 只是查询、不影响归属，计时结束时通知回到 Session A。

另一个上下文来源：**WebSocket 连接的 query 参数**。平台加载 WebView 时会把 `agentId` / `sessionId` 附在 URL 上（见第 5 节骨架），你的 WS handler 读取并绑定到连接上——这样"用户在界面上发起的首次操作"也能立即带上通知所需的上下文，不必等 Agent 先调用过工具。

### 7.4 通知格式（固定四字段）

用户在界面上做了操作需要告知 Agent 时，通过 MCP 通知发送，method 为 `notifications/app`，params 固定四字段，**字段名不可更改**：

```json
{
  "method": "notifications/app",
  "params": {
    "agentId": "归属 Agent 的 id",
    "sessionId": "发起该任务的 Session id",
    "source": "App 名称（与 mcp.json 的 key 一致）",
    "content": "给 Agent 看的自然语言消息"
  }
}
```

- `sessionId` 不能留空字符串（会被校验直接丢弃）
- 主服务器投递前会校验"发送连接、声明的 Agent、Session 归属"三者一致，乱填会被丢弃
- 目标 Session 已被用户删除时，通知会被丢弃并记日志，不会转投别的对话

### 7.5 信息边界（博弈类 App 必读）

**通知只该告诉 Agent「发生了什么类型的事 + 该做什么」，不该泄露影响公平或保密的信息。**

剪刀石头布是现成的例子：用户出招后发给 Agent 的通知是"用户已出招，轮到你出招了"——**故意不写用户出了什么**。如果写成"用户出了剪刀"，Agent 作为 LLM 会直接出克制招（布），用户必输。判定结束后才允许在工具返回值里告知双方的招式。

原则：Agent 决策时能知道什么、判定后才该知道什么，严格分开。

## 8. Web UI 开发

页面就是普通网页，没有特殊框架或协议要求：

- **拿初始数据**：加载后 `fetch` 你自己的 API
- **收更新**：开一条 WebSocket，数据变更（不管是 Agent 通过工具改的、用户在页面上改的、还是业务逻辑自己变的）都由你的服务器主动推送，页面收到就更新

### 硬性约束

1. **静态资源必须用相对路径。** 页面挂在反向代理 `/apps/{name}/` 下，绝对路径（如 Vite 默认的 `/assets/x.js`）会 404。用 Vite 必须配 `base: './'`，让产物以 `./assets/x.js` 引用——这是用框架最容易踩的坑
2. **禁止 `window.open`。** 桌面端主进程会拒绝新窗口并把请求转给系统浏览器，用户会从面板跳出去。弹层、新视图一律在页面内实现
3. **必须提供桌面和移动两套页面。** `ui/index.html`（桌面）+ `ui/mobile.html`（移动），移动端 WebView 加载的是 `/mobile` 路径。`mcp.json` 的 `supportedUI` 如实声明

### 开发期调试

前端源码与后端不在同一端口时（如 Vite dev server），配 `server.proxy` 把 `/ws`、API 转发到后端端口即可；生产构建不需要。

### 移动端的请求路径（了解即可）

App 的 HTTP 服务跑在**桌面电脑**上，手机不可能直连电脑的 localhost。实际路径是：

```
手机 WebView 的 fetch() / WebSocket()
  → Cloudflare Tunnel（公网）
  → 桌面主服务器
  → 看到 /apps/{name}/ 前缀 → 反向代理 → 你的 HTTP 服务
```

对页面来说这就是标准的同源模型——写相对路径，主服务器按前缀转发，你不用关心用户在哪端打开。

### 重前端（WebGL / three.js 等）

架构上没有限制（WebView 就是 Safari / Chrome 同款引擎，带 WebGL 和硬件加速），但注意工程问题：three.js + 模型动辄几 MB，移动端走隧道加载会慢，要做压缩 / 分包；低端 Android 的 GPU 驱动弱，需要降面数、简化着色器；重 3D 场景要单独做手机调优版。

## 9. 发布到商城

### 9.1 放置商品

商品放在本仓 `mcp/<name>/` 下（结构与第 3 节一致）。**没有单独的 `apps/` 目录**——Agent App 就是在 MCP 商品上加 `agentApp: true` 标记，商城按这个字段把它分进「应用」Tab（不标记则是普通「MCP」Tab 商品）。

### 9.2 登记清单（mcp/index.json）

在本仓 [`mcp/index.json`](../../mcp/index.json) 里照现有格式追加一条：

```json
{
  "name": "你的 App 显示名",
  "description": "一句话简介，商城卡片上展示",
  "author": "你的名字",
  "homepage": "https://github.com/Code-MonkeyZhang/persona-agent-marketplace/tree/main/mcp/your-app",
  "path": "mcp/your-app",
  "logo": "icon.png",
  "runtime": "uv",
  "agentApp": true
}
```

| 字段 | 说明 |
|---|---|
| `name` / `description` | 商城卡片显示名与简介 |
| `path` | 商品路径，末段必须与文件夹名一致（三级同名） |
| `logo` | 商城卡片图标，指向商品内的 `icon.png` |
| `runtime: "uv"` | 声明 uv 运行时，安装时会自动 `uv sync` 预装依赖 |
| `agentApp: true` | **Agent App 标记**，进「应用」Tab 的唯一依据 |

### 9.3 图标两用

`icon.png` 一份文件两处消费，打包时验证两条路径都能出图：

- **商城卡片**：经 `index.json` 的 `logo` 字段引用（安装时下载到本地显示）
- **运行时 App 栏**：经反向代理 `/apps/{name}/icon.png`，由你的 HTTP 服务提供（第 5 节骨架的 `/icon.png` 路由）

### 9.4 提交

Fork 本仓 → 加商品目录 + 登记 `index.json` → 提 Pull Request。**禁止使用 Git LFS**（会破坏应用的 raw 下载机制）。

## 10. 发布 Checklist

发布前逐条勾选：

- [ ] 文件夹名 === `index.json` 条目 `path` 末段 === `mcp.json` key === 通知 `source`（三级同名）
- [ ] `mcp.json` 含 `agentApp: true` + 如实的 `supportedUI`
- [ ] `ui/` 构建产物已提交（`.gitignore` 没有排除它）
- [ ] `uv.lock` 已提交
- [ ] 已剥离：`web/` 源码、`node_modules/`、`data/`、日志、`*.egg-info`、过程文档
- [ ] 前端静态资源全部相对路径（Vite `base: './'`）
- [ ] Web UI 无 `window.open`
- [ ] 提供桌面（`index.html`）+ 移动（`mobile.html`）两套页面（若声明了 `supportedUI`）
- [ ] 先启动 HTTP 再启动 MCP；端口读 `APP_PORT`
- [ ] stdout 无任何日志输出（日志走 stderr / 文件）
- [ ] 工具定义里 `agentId` / `sessionId` 为可选参数
- [ ] 每个会产生通知的任务创建时记录了 `sessionId` + `agentId`（无全局回话地址）
- [ ] 通知固定四字段 `agentId` / `sessionId` / `source` / `content`，`sessionId` 不留空
- [ ] 博弈类 App：通知不泄露影响公平的信息
- [ ] 持久化用 SQLite（或等价并发安全方案），非裸写 JSON
- [ ] 父进程退出时自行终止（无孤儿进程）
- [ ] `icon.png` 存在，且商城卡片 / 运行时两条路径都能出图
- [ ] 未使用 Git LFS

## 11. FAQ

**Q：Agent App 的界面，本质是什么？**
一张普通网页，被塞进嵌入式浏览器引擎渲染。桌面端 Electron `<webview>`（Chromium），移动端 `react-native-webview`（WKWebView / 系统 WebView）。两端加载同一 URL，页面就是标准 HTML/CSS/JS。

**Q：支持哪些前端技术？能跑 three.js / WebGL 吗？**
能。WebView 用的就是 Safari / Chrome 同款渲染引擎，带 WebGL 和硬件加速。协议层（MCP 工具调用、通知）和渲染层完全解耦——Agent 调工具 → 你的 server 改数据 → WebSocket 推前端 → 前端重绘，3D 绘制全在客户端。瓶颈在移动端隧道下的加载性能和手机 GPU（见第 8 节）。

**Q：页面怎么和后端通信？**
和普通 Web 应用一样：`fetch()` 一问一答拿初始数据，WebSocket 持久连接收实时推送。不要用 fetch 轮询。

**Q：移动端的请求怎么走到我的服务器？**
手机 WebView 的请求 → Cloudflare Tunnel → 桌面主服务器 → `/apps/{name}/` 前缀反向代理 → 你的 HTTP 服务。对页面是同源的，写相对路径即可（见第 8 节）。

**Q：这和用浏览器打开网页有什么区别？**
协议层面没区别。区别在环境：WebView 没有地址栏 / 标签页 / 前进后退，URL 由 App 锁定加载；存储独立分区，与系统浏览器互不干扰。返回、刷新等交互得你在页面里自己做。

**Q：一个用户有多个 Agent 人格，数据会串吗？**
数据默认全局一份（见第 6 节）。消息不会串——前提是你遵守"按任务存 sessionId"（第 7.3 节）。需要按人格隔离数据时，自行设计存储布局。

## 12. 真实示例

仓内三个已上架的 Agent App，各自示范一类典型形态，开发时建议对照参考：

| 商品 | 示范点 |
|---|---|
| [mcp/rock-paper-scissors](../../mcp/rock-paper-scissors) | 博弈类：双通道最小完整实现、通知信息边界（不泄露用户招式）、WS query 携带 agentId/sessionId |
| [mcp/pomodoro-timer](../../mcp/pomodoro-timer) | 计时通知类：「按任务存 sessionId」的正面教材（计时结束通知回到发起计时的那段对话）、SQLite 统计 |
| [mcp/health-manager](../../mcp/health-manager) | 数据记录类：Agent 在对话里记数据、面板自动更新趋势图、双端 UI |

三者都包含完整的 `mcp.json` / `pyproject.toml` / `uv.lock` / `ui/` 产物，可作为发布物的结构模板。
