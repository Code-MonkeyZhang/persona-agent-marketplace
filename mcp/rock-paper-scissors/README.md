# 剪刀石头布 Agent App

用户和 Agent 通过 Agent App 玩剪刀石头布（三局两胜）。用户在 Web UI 点按钮出招，Agent 通过 MCP 工具出招，服务器判定胜负。

## 工具列表

本服务向 Agent 暴露以下工具（`agentId` / `sessionId` 由平台自动注入，无需填写）：

| 工具名称 | 参数 | 功能描述 |
| :-- | :-- | :-- |
| `start_game` | 无 | 开始一局，初始化比分 |
| `play_move` | `move`: rock/paper/scissors | Agent 出招，服务器判定本局胜负并更新比分 |
| `get_game_state` | 无 | 查询当前比分与游戏阶段 |
| `get_game_history` | 无 | 查询历史对局记录 |
| `end_game` | 无 | 结束当前进行中的对局（弃权，计为中途结束，不计胜负） |

## Agent 通知

用户在 Web UI 的操作会通过 `notifications/app` 主动推送通知给 Agent（params: `{agentId, sessionId, source, content}`）。Agent 自己调用工具不会触发通知，只返回工具结果。

通知所需的 `agentId` / `sessionId` 由平台加载 App webview 时通过 URL query 参数（`?agentId=...&sessionId=...`）传入，UI 建立 WebSocket 时透传该 query，服务端据此为每条连接绑定上下文。因此用户**首次操作**（如点击「开始游戏」）即可带上完整上下文，无需依赖 Agent 先调用工具。

| 触发时机 | 通知内容（content） |
| :-- | :-- |
| 用户点击「开始游戏」 | 用户想开始一局剪刀石头布，请调用 start_game |
| 用户出招 | 用户已出招，轮到你出招了 |
| 用户点击「再来一局」 | 用户想再来一局，请调用 start_game 开始新一场 |
| 用户点击「结束游戏」 | 用户已结束本局（中途结束） |

## 开发

后端（Python MCP + HTTP/WS 双通道）：

```bash
cd agent-apps/rock-paper-scissors
uv sync
APP_PORT=<port> uv run python -m rock_paper_scissors
```

前端（React + Vite + Tailwind CSS + Lucide），构建产物写入 `ui/` 供后端静态托管：

```bash
cd agent-apps/rock-paper-scissors/web
npm install
npm run build   # 产物输出到 ../ui/
```
