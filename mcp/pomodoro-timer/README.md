# 番茄时钟 Agent App

专注计时 Agent App。用户在 Web UI 上一次配好工作时长、休息时长、轮数，点开始。session 自动推进，工作结束自动进休息，休息结束自动开下一轮，全部轮次走完自动结束。Agent 在 session 开始与结束两个时刻收到 MCP notification，专注期间进入守护模式。每段工作自动写入 SQLite 记录。

## 工具列表

本服务向 Agent 暴露以下工具（`agentId` / `sessionId` 由平台自动注入，无需填写）：

| 工具名称 | 参数 | 功能描述 |
| :-- | :-- | :-- |
| `start` | `focus_min`: int, `break_min`: int, `rounds`: int 三者必传, `intent?`: string | 开始一个完整 session。以工作加休息为单元循环 rounds 次，自动跑完，无需手动接力 |
| `stop` | 无 | 中止当前 session。专注段被中止会记录已专注时长并标记为未完成 |
| `query_stats` | 无 | 查询今日/本周番茄钟数量、累计时长、最近专注记录 |
| `get_timer_state` | 无 | 查询实时状态：阶段、剩余时间、第几轮共几轮、意图 |

## Agent 通知

Agent App 在 session 开始与结束两个时刻通过 `notifications/app` 主动推送通知（params: `{agentId, sessionId, source, content}`）。Agent 自己调用 start / stop 也收到通知，因为它需要知道自己进入了或退出了守护模式。轮间自动切换不通知，计时与续轮由 App 自己完成。

通知的 `agentId` / `sessionId` 在 session 启动时记录，整个 session 的通知都发往这里（按任务记账），不受其他 session 查询的影响。

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
