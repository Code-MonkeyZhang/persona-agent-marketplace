# Health Manager Agent App

个人身体管理 Agent App：体征（体重/血压/心率）、饮食（卡路里与宏量）、健身（训练与能力）与疾病（化验/影像病理/病历）。Agent 通过 MCP 工具记录和查询数据，用户可在 Web UI 查看实时更新。

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
| `update_workout` | `entry_id`, 其余字段可选 | 按编号修改一条训练（patch） |
| `delete_workout` | `entry_id` | 按编号删除一条训练 |
| `record_diet` | `food`, `calories`, `carbs`, `protein`, `fat`, `meal?`, `quantity?`, `date?`, `note?` | 记一条饮食，三大宏量必填，返回当日累计卡路里 |
| `get_diet_log` | `date?` | 查某天饮食清单，每条带 [编号] |
| `update_diet` | `entry_id`, 其余字段可选 | 按编号修改一条饮食（patch），常用于补填宏量 |
| `delete_diet` | `entry_id` | 按编号删除一条饮食 |
| `set_diet_goals` | `goal?`, `carbs?`, `protein?`, `fat?` | 设饮食目标，部分更新，三个宏量需同时给 |
| `get_diet_goals` | 无 | 查卡路里目标 + 三大宏量目标（含模式） |
| `record_lab_result` | `items`（每项 analyte + value_num/value_text）、`date?` | 批量录一次化验，指标名自动归一、判偏高偏低，返回逐项与上次对比 |
| `get_lab_history` | `analyte`, `limit?` | 查某指标历史，每条带 [编号]、参考范围与标记 |
| `list_lab_analytes` | 无 | 按大类列已录指标与最新值 |
| `update_lab_result` | `entry_id`, 其余字段可选 | 按编号修改一条化验，改完重算标记 |
| `delete_lab_result` | `entry_id` | 按编号删除一条化验 |
| `record_imaging_finding` | `exam_type`, `finding_text`, `date?`, `note?` | 录一条影像病理结论 |
| `get_imaging_history` | `exam_type?`, `limit?` | 查影像病理，按时间倒序 |
| `get_health_journal` | `date?` | 读病历，不带日期返回索引，带日期返回全文 |
| `update_health_journal` | `date`, `content`, `title?` | 写某日病历，按日期一文件，写前自动快照 |
| `get_health_basics` | 无 | 读置顶的病史基础，含个人信息、过敏史、既往病史 |
| `update_health_basics` | `content` | 整篇替换病史基础，写前自动快照 |

## Agent 通知

本服务**不向 Agent 主动推送通知**。所有交互均由 Agent 发起工具调用；用户在 Web UI 的操作（如设置身高、编辑病历）只更新数据并通过 WebSocket 刷新前端，不会触发对 Agent 的通知。

## 开发

```bash
cd agent-apps/health-manager
uv sync
APP_PORT=<port> uv run python -m health_manager
```

测试与演示数据：

```bash
uv run pytest                                # 后端测试
uv run python scripts/seed_mock.py           # 重建演示数据库
uv run python scripts/import_legacy.py       # 一次性导入存量化验与病历
```
