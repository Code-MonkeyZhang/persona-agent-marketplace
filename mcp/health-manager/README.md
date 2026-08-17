# Health Manager Agent App

个人健康指标（体重、血压、心率）记录 Agent App。Agent 通过 MCP 工具记录和查询数据，用户可在 Web UI 查看实时更新。

## 工具列表

本服务向 Agent 暴露以下工具（`agentId` / `sessionId` 由平台自动注入，无需填写）：

| 工具名称 | 参数 | 功能描述 |
| :-- | :-- | :-- |
| `get_body_metrics` | `metric?`: weight/blood_pressure | 查最近一条体征（体重/血压/心率）+ 身高/称呼 |
| `update_body_metrics` | `weight?`, `systolic?`, `diastolic?`, `heart_rate?`, `height?`, `name?`, `date?`, `note?` | 记录或修改体征，部分更新，传过去日期可改历史 |
| `record_strength` | `exercise`, `metric`, `value`, `unit?`, `date?`, `note?` | 记力量成绩，自动对比上次 |
| `get_strength_history` | `exercise` | 查某动作的力量记录 |
| `record_workout` | `exercise`, `sets?`, `reps?`, `weight?`, `feeling?`, `date?`, `note?` | 记一次训练 |
| `get_workout_diary` | `limit?` | 查运动日记 |
| `record_diet` | `food`, `calories`, `carbs`, `protein`, `fat`, `meal?`, `quantity?`, `date?`, `note?` | 记一条饮食，三大宏量必填，返回当日累计卡路里 |
| `get_diet_log` | `date?` | 查某天饮食清单，每条带 [编号] |
| `update_diet` | `entry_id`, 其余字段可选 | 按编号修改一条饮食（patch），常用于补填宏量 |
| `delete_diet` | `entry_id` | 按编号删除一条饮食 |
| `set_diet_goals` | `goal?`, `carbs?`, `protein?`, `fat?` | 设饮食目标，部分更新，三个宏量需同时给 |
| `get_diet_goals` | 无 | 查卡路里目标 + 三大宏量目标（含模式） |

## Agent 通知

本服务**不向 Agent 主动推送通知**。所有交互均由 Agent 发起工具调用；用户在 Web UI 的操作（如设置身高）只更新数据库并通过 WebSocket 刷新前端，不会触发对 Agent 的通知。

## 开发

```bash
cd agent-apps/health-manager
uv sync
APP_PORT=<port> uv run python -m health_manager
```
