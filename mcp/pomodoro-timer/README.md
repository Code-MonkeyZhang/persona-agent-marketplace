# 番茄时钟 Agent App

专注计时 Agent App。用户在 Web UI 上设定专注时长、写一句意图，点击开始。Agent App 管理计时器，在专注开始、专注结束、用户停止、休息结束四个时刻通过 MCP notification 通知 Agent。专注结束后自动写入 SQLite 记录。

## 工具列表

本服务向 Agent 暴露以下工具（`agentId` / `sessionId` 由平台自动注入，无需填写）：

| 工具名称 | 参数 | 功能描述 |
| :-- | :-- | :-- |
| `start` | `intent?`: string, `duration_min?`: int | 开始一段专注。不传时长用默认值（25 分钟） |
| `stop` | 无 | 停止当前计时器，回到空闲。专注中被停止会记录已完成时长（标记为未完成） |
| `query_stats` | 无 | 查询今日/本周番茄钟数量、累计时长、最近 10 条专注记录 |
| `get_timer_state` | 无 | 查询当前计时器实时状态：阶段、剩余分钟、意图、本轮进度 |

## Agent 通知

Agent App 在四个时刻通过 `notifications/app` 主动推送通知给 Agent（params: `{agentId, sessionId, source, content}`）。Agent 自己调用 start / stop 工具不触发通知。

通知所需的 `agentId` / `sessionId` 在用户首次开始专注时从 WebSocket 连接获取并存储，之后该番茄钟周期的所有通知都发往这个 session（按任务记账），不受其他 session 查询的影响。

| 触发时机 | 通知内容（content） |
| :-- | :-- |
| 用户开始专注 | `用户开始了番茄钟，预计 {duration} 分钟，意图：{intent}` |
| 用户停止专注 | `专注已结束，中途停止，已专注 {X 分 Y 秒}` |
| 专注自然结束 | `专注已结束，共 {X 分钟 / X 分 Y 秒}` |
| 休息结束 | `{短/长}休息结束了，是否继续下一个番茄钟？` |

## 开发

后端（Python MCP + HTTP/WS 双通道）：

```bash
cd agent-apps/pomodoro-timer
uv sync
APP_PORT=<port> uv run python -m pomodoro_timer
```

前端（React + Vite + Tailwind CSS + Lucide），构建产物写入 `ui/` 供后端静态托管：

```bash
cd agent-apps/pomodoro-timer/web
npm install
npm run build   # 产物输出到 ../ui/
```
