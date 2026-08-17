"""
Health Manager Agent App server.

Runs two channels in one process via anyio task group:
- stdio MCP: exposes recording / query tools to the Agent
- uvicorn HTTP: serves the built Web UI as static files, WebSocket for
  real-time metric updates

Both channels share a single HealthDB instance, so an Agent's tool call writes
data and pushes a WebSocket update to the frontend — all within one event loop.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

import anyio
import mcp.types as types
import uvicorn
from mcp.server import Server
from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.responses import FileResponse
from starlette.routing import Mount, Route, WebSocketRoute
from starlette.staticfiles import StaticFiles
from starlette.websockets import WebSocket, WebSocketDisconnect

from .db import HealthDB
from .log import initialize as log_init, log
from .prompts import load_prompt

APP_ROOT = Path(__file__).resolve().parent.parent.parent
UI_DIR = APP_ROOT / "ui"
ICON_PATH = APP_ROOT / "icon.png"
DATA_DIR = APP_ROOT / "data"
REAL_DB_PATH = DATA_DIR / "health.db"
MOCK_DB_PATH = DATA_DIR / "health.mock.db"
MOCK_FLAG_PATH = DATA_DIR / "mock_mode"
CSV_PATH = APP_ROOT / "health-profile" / "refine_data" / "health_data" / "daily_metrics.csv"
LOG_PATH = APP_ROOT / "health-manager.log"

SOURCE = "health-manager"
VERSION = "0.2.0"


def _read_mock_flag() -> bool:
    """Whether the server should serve mock data. Persisted in data/mock_mode."""
    return MOCK_FLAG_PATH.exists() and MOCK_FLAG_PATH.read_text(encoding="utf-8").strip() == "1"


def _write_mock_flag(on: bool) -> None:
    MOCK_FLAG_PATH.write_text("1" if on else "0", encoding="utf-8")

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
        name="get_body_metrics",
        description=load_prompt("get_body_metrics"),
        inputSchema={
            "type": "object",
            "properties": {
                "metric": {
                    "type": "string",
                    "enum": ["weight", "blood_pressure"],
                    "description": "筛选最近一条指标类型，可选。不填返回最近一条综合体征记录",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="update_body_metrics",
        description=load_prompt("update_body_metrics"),
        inputSchema={
            "type": "object",
            "properties": {
                "weight": {
                    "type": "number",
                    "description": "体重 kg",
                },
                "systolic": {
                    "type": "integer",
                    "description": "收缩压 mmHg，与 diastolic 同时填写",
                },
                "diastolic": {
                    "type": "integer",
                    "description": "舒张压 mmHg，与 systolic 同时填写",
                },
                "heart_rate": {
                    "type": "integer",
                    "description": "心率 bpm",
                },
                "height": {
                    "type": "number",
                    "description": "身高 cm",
                },
                "name": {
                    "type": "string",
                    "description": "用户称呼",
                },
                "date": {
                    "type": "string",
                    "description": "体征日期 YYYY-MM-DD，可选，默认今天。传过去某天即修改那天",
                },
                "note": {
                    "type": "string",
                    "description": "备注，可选",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="record_strength",
        description=load_prompt("record_strength"),
        inputSchema={
            "type": "object",
            "required": ["exercise", "metric", "value"],
            "properties": {
                "exercise": {
                    "type": "string",
                    "description": "动作名，自由文本，如自由卧推/俯卧撑/深蹲/100米跑",
                },
                "metric": {
                    "type": "string",
                    "description": "指标名称，自由文本，如最大重量/最多次数/用时/单次消耗",
                },
                "value": {
                    "type": "number",
                    "description": "成绩数值（kg / reps / s / kcal 等，取决于 metric）",
                },
                "category": {
                    "type": "string",
                    "description": "分类，如上半身/下半身/有氧",
                },
                "unit": {
                    "type": "string",
                    "description": "单位，可选，默认按 metric 推定（kg/reps/s/kcal/min 等）",
                },
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD，可选，默认今天",
                },
                "note": {
                    "type": "string",
                    "description": "备注，可选",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="get_strength_history",
        description=load_prompt("get_strength_history"),
        inputSchema={
            "type": "object",
            "required": ["exercise"],
            "properties": {
                "exercise": {
                    "type": "string",
                    "description": "动作名",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="record_workout",
        description=load_prompt("record_workout"),
        inputSchema={
            "type": "object",
            "required": ["exercise"],
            "properties": {
                "exercise": {
                    "type": "string",
                    "description": "动作名，如深蹲/卧推",
                },
                "sets": {
                    "type": "integer",
                    "description": "组数，可选",
                },
                "reps": {
                    "type": "integer",
                    "description": "每组次数，可选",
                },
                "weight": {
                    "type": "number",
                    "description": "重量 kg，可选",
                },
                "calories": {
                    "type": "integer",
                    "description": "消耗卡路里。用户没报时，根据动作和强度自行估算合理值",
                },
                "feeling": {
                    "type": "string",
                    "description": "练完感觉，可选",
                },
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD，可选，默认今天",
                },
                "note": {
                    "type": "string",
                    "description": "备注，可选",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="get_workout_diary",
        description=load_prompt("get_workout_diary"),
        inputSchema={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "返回最近 N 条，可选，默认 10",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="update_workout",
        description=load_prompt("update_workout"),
        inputSchema={
            "type": "object",
            "required": ["entry_id"],
            "properties": {
                "entry_id": {
                    "type": "integer",
                    "description": "要修改的运动记录编号，来自 get_workout_diary 返回里的 [编号]",
                },
                "exercise": {
                    "type": "string",
                    "description": "动作名",
                },
                "sets": {
                    "type": "integer",
                    "description": "组数",
                },
                "reps": {
                    "type": "integer",
                    "description": "每组次数",
                },
                "weight": {
                    "type": "number",
                    "description": "重量 kg",
                },
                "calories": {
                    "type": "integer",
                    "description": "消耗卡路里",
                },
                "feeling": {
                    "type": "string",
                    "description": "练完感觉",
                },
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD",
                },
                "note": {
                    "type": "string",
                    "description": "备注",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="delete_workout",
        description=load_prompt("delete_workout"),
        inputSchema={
            "type": "object",
            "required": ["entry_id"],
            "properties": {
                "entry_id": {
                    "type": "integer",
                    "description": "要删除的运动记录编号，来自 get_workout_diary 返回里的 [编号]",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="record_diet",
        description=load_prompt("record_diet"),
        inputSchema={
            "type": "object",
            "required": ["food", "calories", "carbs", "protein", "fat"],
            "properties": {
                "food": {
                    "type": "string",
                    "description": "食物名称",
                },
                "calories": {
                    "type": "integer",
                    "description": "卡路里。用户没报时，根据食物自行估算一个合理值",
                },
                "meal": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                    "description": "餐别，可选",
                },
                "quantity": {
                    "type": "string",
                    "description": "份量文本，如 1大碗/半盘/2个，可选",
                },
                "carbs": {
                    "type": "number",
                    "description": "碳水克数。用户没报时根据食物自行估算",
                },
                "protein": {
                    "type": "number",
                    "description": "蛋白质克数。用户没报时根据食物自行估算",
                },
                "fat": {
                    "type": "number",
                    "description": "脂肪克数。用户没报时根据食物自行估算",
                },
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD，可选，默认今天",
                },
                "note": {
                    "type": "string",
                    "description": "备注，可选，可写维生素等非结构化营养信息",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="get_diet_log",
        description=load_prompt("get_diet_log"),
        inputSchema={
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD，可选，默认今天",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="update_diet",
        description=load_prompt("update_diet"),
        inputSchema={
            "type": "object",
            "required": ["entry_id"],
            "properties": {
                "entry_id": {
                    "type": "integer",
                    "description": "要修改的饮食记录编号，来自 get_diet_log 返回里的 [编号]",
                },
                "food": {
                    "type": "string",
                    "description": "食物名称",
                },
                "calories": {
                    "type": "integer",
                    "description": "卡路里",
                },
                "meal": {
                    "type": "string",
                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                    "description": "餐别",
                },
                "quantity": {
                    "type": "string",
                    "description": "份量文本",
                },
                "carbs": {
                    "type": "number",
                    "description": "碳水克数",
                },
                "protein": {
                    "type": "number",
                    "description": "蛋白质克数",
                },
                "fat": {
                    "type": "number",
                    "description": "脂肪克数",
                },
                "date": {
                    "type": "string",
                    "description": "日期 YYYY-MM-DD",
                },
                "note": {
                    "type": "string",
                    "description": "备注",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="delete_diet",
        description=load_prompt("delete_diet"),
        inputSchema={
            "type": "object",
            "required": ["entry_id"],
            "properties": {
                "entry_id": {
                    "type": "integer",
                    "description": "要删除的饮食记录编号，来自 get_diet_log 返回里的 [编号]",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="set_diet_goals",
        description=load_prompt("set_diet_goals"),
        inputSchema={
            "type": "object",
            "properties": {
                "goal": {
                    "type": "integer",
                    "description": "每日卡路里目标",
                },
                "carbs": {
                    "type": "integer",
                    "description": "碳水目标 g，三个宏量需同时填写并切到手动模式",
                },
                "protein": {
                    "type": "integer",
                    "description": "蛋白质目标 g，三个宏量需同时填写并切到手动模式",
                },
                "fat": {
                    "type": "integer",
                    "description": "脂肪目标 g，三个宏量需同时填写并切到手动模式",
                },
                **_INJECTED_PARAMS,
            },
        },
    ),
    types.Tool(
        name="get_diet_goals",
        description=load_prompt("get_diet_goals"),
        inputSchema={
            "type": "object",
            "properties": dict(_INJECTED_PARAMS),
        },
    ),
]


# --- Shared server state ----------------------------------------------------


class HealthServer:
    """Holds DB state and bridges between MCP and WS channels."""

    def __init__(self) -> None:
        # Real DB imports the existing CSV history; mock DB is seeded by script.
        self._real_db = HealthDB(REAL_DB_PATH, csv_path=CSV_PATH)
        self._mock_db = HealthDB(MOCK_DB_PATH)
        self._mock_on = _read_mock_flag()
        self._ws_clients: set[WebSocket] = set()
        log("INFO", "server_ready", mock_on=self._mock_on)

    @property
    def db(self) -> HealthDB:
        """The currently active DB — real or mock, switchable at runtime."""
        return self._mock_db if self._mock_on else self._real_db

    @property
    def mock_on(self) -> bool:
        return self._mock_on

    def toggle_mock(self) -> bool:
        """Flip the mock/real data source and persist the choice."""
        self._mock_on = not self._mock_on
        _write_mock_flag(self._mock_on)
        log("INFO", "mock_toggled", mock_on=self._mock_on)
        return self._mock_on

    # --- MCP tool handlers ---

    def get_body_metrics(self, metric: str | None = None) -> str:
        """Read latest body metrics plus the static profile (height/name)."""
        latest = self.db.get_latest(metric)
        profile = self.db.get_profile()
        parts: list[str] = []
        if profile:
            bits = []
            if profile.get("name"):
                bits.append(f"称呼 {profile['name']}")
            if profile.get("height"):
                bits.append(f"身高 {profile['height']}cm")
            if bits:
                parts.append("，".join(bits))
        if latest:
            parts.append(_fmt_latest(latest))
        return "。".join(parts) if parts else "暂无记录"

    def update_body_metrics(
        self,
        weight: float | None = None,
        systolic: int | None = None,
        diastolic: int | None = None,
        heart_rate: int | None = None,
        height: float | None = None,
        name: str | None = None,
        date: str | None = None,
        note: str | None = None,
    ) -> str:
        """Partial write of body metrics. Only provided fields change.

        - weight / 血压 保留与上次记录的对比反馈
        - 心率只在同时给血压时一并记录
        - 传过去的日期即修改那天
        """
        date = date or _today()
        parts: list[str] = []
        try:
            if weight is not None:
                r = self.db.record_weight(date, weight, note)
                log("INFO", "weight_recorded", date=date, weight=weight)
                parts.append(_fmt_weight(r, date))
            if systolic is not None or diastolic is not None or heart_rate is not None:
                if systolic is None or diastolic is None:
                    return "血压需同时提供收缩压和舒张压，心率可一并记"
                r = self.db.record_blood_pressure(
                    date, systolic, diastolic, heart_rate, note
                )
                log(
                    "INFO",
                    "bp_recorded",
                    date=date,
                    systolic=systolic,
                    diastolic=diastolic,
                    heart_rate=heart_rate,
                )
                parts.append(_fmt_bp(r, date))
            if height is not None:
                self.db.set_profile(height)
                log("INFO", "profile_set", height=height)
                parts.append(f"身高已设为 {height}cm")
            if name is not None:
                self.db.set_name(name)
                log("INFO", "name_set", name=name)
                parts.append(f"称呼已设为 {name}")
        except ValueError as e:
            return str(e)
        return "。".join(parts) if parts else "没有提供任何要更新的字段"

    # --- Fitness tools ---

    def record_strength(
        self,
        exercise: str,
        metric: str,
        value: float,
        unit: str | None = None,
        category: str | None = None,
        date: str | None = None,
        note: str | None = None,
    ) -> str:
        date = date or _today()
        try:
            result = self.db.record_strength(date, exercise, metric, value, unit, category, note)
            log("INFO", "strength_recorded", date=date, exercise=exercise, metric=metric, value=value, category=category)
            return _fmt_strength(result, date)
        except ValueError as e:
            return str(e)

    def record_workout(
        self,
        exercise: str,
        sets: int | None = None,
        reps: int | None = None,
        weight: float | None = None,
        calories: int | None = None,
        feeling: str | None = None,
        date: str | None = None,
        note: str | None = None,
    ) -> str:
        date = date or _today()
        try:
            result = self.db.record_workout(date, exercise, sets, reps, weight, feeling, calories, note)
            log("INFO", "workout_recorded", date=date, exercise=exercise, sets=sets, reps=reps, calories=calories)
            return _fmt_workout(result, date)
        except ValueError as e:
            return str(e)

    def update_workout(self, entry_id: int, **fields) -> str:
        """Patch a workout entry by id. Only provided fields change."""
        try:
            result = self.db.update_workout_entry(entry_id, **fields)
            if result is None:
                return f"找不到编号 {entry_id} 的运动记录"
            log("INFO", "workout_updated", entry_id=entry_id, fields=list(fields.keys()))
            return _fmt_workout_entry(result)
        except ValueError as e:
            return str(e)

    def delete_workout(self, entry_id: int) -> str:
        ok = self.db.delete_workout_entry(entry_id)
        if not ok:
            return f"找不到编号 {entry_id} 的运动记录"
        log("INFO", "workout_deleted", entry_id=entry_id)
        return f"已删除编号 {entry_id} 的运动记录"

    def get_strength_history(self, exercise: str) -> str:
        records = [r for r in self.db.get_strength_records() if r["exercise"] == exercise]
        if not records:
            return f"暂无「{exercise}」的能力记录"
        return _fmt_strength_history(exercise, records)

    def get_workout_diary(self, limit: int | None = None) -> str:
        entries = self.db.get_workout_entries()
        if limit:
            entries = entries[:limit]
        if not entries:
            return "暂无运动日记"
        return _fmt_workout_diary(entries)

    # --- Diet tools ---

    def record_diet(
        self,
        food: str,
        calories: int,
        meal: str | None = None,
        quantity: str | None = None,
        carbs: float | None = None,
        protein: float | None = None,
        fat: float | None = None,
        date: str | None = None,
        note: str | None = None,
    ) -> str:
        date = date or _today()
        try:
            result = self.db.record_diet(
                date, food, calories, meal, quantity, carbs, protein, fat, note
            )
            log(
                "INFO",
                "diet_recorded",
                date=date,
                food=food,
                calories=calories,
                meal=meal,
                carbs=carbs,
                protein=protein,
                fat=fat,
            )
            return _fmt_diet(result)
        except ValueError as e:
            return str(e)

    def get_diet_log(self, date: str | None = None) -> str:
        date = date or _today()
        entries = [e for e in self.db.get_diet_entries() if e["date"] == date]
        if not entries:
            return f"{date} 暂无饮食记录"
        return _fmt_diet_log(date, entries)

    def update_diet(self, entry_id: int, **fields) -> str:
        """Patch a diet entry by id. Only provided fields change."""
        try:
            result = self.db.update_diet_entry(entry_id, **fields)
            if result is None:
                return f"找不到编号 {entry_id} 的饮食记录"
            log("INFO", "diet_updated", entry_id=entry_id, fields=list(fields.keys()))
            return _fmt_diet_entry(result)
        except ValueError as e:
            return str(e)

    def delete_diet(self, entry_id: int) -> str:
        ok = self.db.delete_diet_entry(entry_id)
        if not ok:
            return f"找不到编号 {entry_id} 的饮食记录"
        log("INFO", "diet_deleted", entry_id=entry_id)
        return f"已删除编号 {entry_id} 的饮食记录"

    # --- Diet goal tools ---

    def set_diet_goals(
        self,
        goal: int | None = None,
        carbs: int | None = None,
        protein: int | None = None,
        fat: int | None = None,
    ) -> str:
        """Partial write of diet goals. Macros must come as a complete set."""
        parts: list[str] = []
        try:
            if goal is not None:
                self.db.set_diet_goal(goal)
                log("INFO", "diet_goal_set", goal=goal)
                parts.append(f"每日卡路里目标 {goal} kcal")
            if carbs is not None or protein is not None or fat is not None:
                if carbs is None or protein is None or fat is None:
                    return "三大宏量目标需同时提供（碳水/蛋白质/脂肪）"
                self.db.set_macro_goals(carbs, protein, fat)
                log("INFO", "macro_goals_set", carbs=carbs, protein=protein, fat=fat)
                parts.append(f"宏量目标 碳水 {carbs}g/蛋白质 {protein}g/脂肪 {fat}g（手动模式）")
        except ValueError as e:
            return str(e)
        return "已设置：" + "，".join(parts) if parts else "没有提供任何要设置的目标"

    def get_diet_goals(self) -> str:
        goal = self.db.get_diet_goal()
        macro = self.db.get_macro_goals()
        if goal is None and macro["carbs"] is None:
            return "尚未设置任何饮食目标"
        parts = []
        if goal is not None:
            parts.append(f"每日卡路里目标 {goal} kcal")
        if macro["carbs"] is not None:
            mode_label = "手动" if macro["mode"] == "manual" else "自动"
            parts.append(
                f"宏量目标（{mode_label}）碳水 {macro['carbs']}g/蛋白质 {macro['protein']}g/脂肪 {macro['fat']}g"
            )
        return "，".join(parts)

    # --- WebSocket handler ---

    async def handle_websocket(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._ws_clients.add(websocket)
        log("INFO", "ws_connected", clients=len(self._ws_clients))

        await websocket.send_json({"type": "init", **self._snapshot()})

        try:
            while True:
                msg = await websocket.receive_json()
                mtype = msg.get("type")
                try:
                    if mtype == "set_height":
                        self.db.set_profile(float(msg["height"]))
                        log("INFO", "height_set_via_ws", height=msg["height"])
                    elif mtype == "set_name":
                        self.db.set_name(str(msg["name"]))
                        log("INFO", "name_set_via_ws", name=msg["name"])
                    elif mtype == "set_diet_goal":
                        self.db.set_diet_goal(int(msg["goal"]))
                        log("INFO", "diet_goal_set_via_ws", goal=msg["goal"])
                    elif mtype == "set_goal_mode":
                        self.db.set_goal_mode(str(msg["mode"]))
                        log("INFO", "goal_mode_set_via_ws", mode=msg["mode"])
                    elif mtype == "set_macro_goals":
                        self.db.set_macro_goals(
                            int(msg["carbs"]), int(msg["protein"]), int(msg["fat"])
                        )
                        log(
                            "INFO",
                            "macro_goals_set_via_ws",
                            carbs=msg["carbs"],
                            protein=msg["protein"],
                            fat=msg["fat"],
                        )
                    elif mtype == "toggle_mock":
                        now_mock = self.toggle_mock()
                        log("INFO", "mock_toggled_via_ws", mock_on=now_mock)
                    else:
                        continue
                    await self.broadcast()
                except (ValueError, KeyError) as e:
                    await websocket.send_json({"type": "error", "message": str(e)})
        except WebSocketDisconnect:
            pass
        finally:
            self._ws_clients.discard(websocket)
            log("INFO", "ws_disconnected", clients=len(self._ws_clients))

    def _snapshot(self) -> dict:
        """Full state for the frontend: module data plus server meta."""
        return {
            **self.db.get_snapshot(),
            "mockOn": self._mock_on,
            "version": VERSION,
            "schemaVersion": self.db.schema_version,
        }

    async def broadcast(self) -> None:
        """Push the full snapshot to all connected WS clients."""
        snapshot = {"type": "update", **self._snapshot()}
        dead: set[WebSocket] = set()
        for ws in self._ws_clients:
            try:
                await ws.send_json(snapshot)
            except Exception:
                dead.add(ws)
        self._ws_clients -= dead


# --- Formatting helpers -----------------------------------------------------


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _fmt_weight(result: dict, date: str) -> str:
    current = result["current"]
    if "previous" not in result:
        return f"已记录：{date} 体重 {current}kg"
    change = result["change"]
    if change < 0:
        detail = f"减轻 {abs(change)}kg"
    elif change > 0:
        detail = f"增加 {change}kg"
    else:
        detail = "持平"
    return (
        f"已记录：{date} 体重 {current}kg。"
        f"上次 {result['previous']}kg（{result['previousDate']}），{detail}"
    )


def _fmt_bp(result: dict, date: str) -> str:
    parts = [f"已记录：{date} 血压 {result['systolic']}/{result['diastolic']}"]
    if "heartRate" in result:
        parts.append(f"心率 {result['heartRate']}")
    if "prevSystolic" in result:
        sc = result["systolicChange"]
        dc = result["diastolicChange"]
        parts.append(
            f"上次 {result['prevSystolic']}/{result['prevDiastolic']}"
            f"（{result['previousDate']}），变化 {sc:+d}/{dc:+d}"
        )
    return "。".join(parts)


def _fmt_latest(row: dict) -> str:
    parts = [row["date"]]
    if row["weight"] is not None:
        parts.append(f"体重 {row['weight']}kg")
    if row["systolic"] is not None:
        bp = f"血压 {row['systolic']}/{row['diastolic']}"
        if row["heartRate"] is not None:
            bp += f" 心率 {row['heartRate']}"
        parts.append(bp)
    return "，".join(parts)


_MEAL_LABELS = {"breakfast": "早餐", "lunch": "午餐", "dinner": "晚餐", "snack": "加餐"}


def _fmt_strength(result: dict, date: str) -> str:
    category = result.get("category")
    prefix = f"[{category}] " if category else ""
    text = f"已记录：{date} {prefix}{result['exercise']} {result['metric']} {result['value']}"
    if "previous" in result:
        change = result["change"]
        detail = "持平" if change == 0 else f"{'涨' if change > 0 else '降'} {abs(change)}"
        text += f"。上次 {result['previous']}（{result['previousDate']}），{detail}"
    return text


def _fmt_workout(result: dict, date: str) -> str:
    parts = [f"已记录：{date} {result['exercise']}"]
    if result.get("sets") is not None:
        if result.get("reps") is not None:
            parts.append(f"{result['sets']} × {result['reps']}")
        else:
            parts.append(f"{result['sets']} sets")
    if result.get("weight") is not None:
        parts.append(f"{result['weight']} kg")
    if result.get("calories") is not None:
        parts.append(f"{result['calories']} kcal")
    return " ".join(parts)


def _fmt_workout_entry(e: dict) -> str:
    parts = [f"已更新：[{e['id']}] {e['exercise']}"]
    if e.get("calories") is not None:
        parts.append(f"{e['calories']} kcal")
    return " ".join(parts)


def _fmt_strength_history(exercise: str, records: list[dict]) -> str:
    lines = [f"{exercise} 能力记录："]
    for r in records:
        lines.append(f"{r['date']} {r['metric']} {r['value']}")
    return "\n".join(lines)


def _fmt_workout_diary(entries: list[dict]) -> str:
    lines = []
    for e in entries:
        parts = [f"[{e['id']}]", e["date"], e["exercise"]]
        if e.get("sets") is not None:
            if e.get("reps") is not None:
                parts.append(f"{e['sets']} × {e['reps']}")
            else:
                parts.append(f"{e['sets']} sets")
        if e.get("weight") is not None:
            parts.append(f"{e['weight']} kg")
        if e.get("calories") is not None:
            parts.append(f"{e['calories']} kcal")
        lines.append(" ".join(parts))
    return "\n".join(lines)


def _fmt_diet(result: dict) -> str:
    return (
        f"已记录：{result['food']} {result['calories']} kcal。"
        f"今日累计 {result['dailyTotal']} kcal"
    )


def _fmt_diet_entry(e: dict) -> str:
    macros = f"碳水 {e['carbs']}/蛋白质 {e['protein']}/脂肪 {e['fat']}"
    return f"已更新：[{e['id']}] {e['food']} {e['calories']} kcal（{macros}）"


def _fmt_diet_log(date: str, entries: list[dict]) -> str:
    total = sum(e["calories"] for e in entries)
    lines = [f"{date} 饮食（共 {total} kcal）："]
    for e in entries:
        meal = _MEAL_LABELS.get(e["meal"], "") if e["meal"] else ""
        prefix = f"{meal} " if meal else ""
        qty = f" · {e['quantity']}" if e.get("quantity") else ""
        lines.append(f"[{e['id']}] {prefix}{e['food']}{qty} {e['calories']} kcal")
    return "\n".join(lines)


# --- Starlette HTTP app -----------------------------------------------------


def create_http_app(server: HealthServer) -> Starlette:
    async def icon(_request):
        return FileResponse(ICON_PATH)

    async def mobile_page(_request):
        return FileResponse(UI_DIR / "mobile.html")

    routes = [
        Route("/icon.png", icon),
        Route("/mobile", mobile_page),
        WebSocketRoute("/ws", server.handle_websocket),
        # Mobile page derives its WS URL from its own path (/mobile → /mobile/ws)
        WebSocketRoute("/mobile/ws", server.handle_websocket),
        # Static UI build (index.html + mobile.html + assets/). Must be last.
        Mount(
            "/",
            app=StaticFiles(directory=str(UI_DIR), html=True),
            name="ui",
        ),
    ]
    return Starlette(routes=routes)


# --- MCP handler factories --------------------------------------------------


def _make_handlers(server: HealthServer):
    async def handle_list_tools(_ctx, _params) -> types.ListToolsResult:
        return types.ListToolsResult(tools=TOOLS)

    async def handle_call_tool(_ctx, params) -> types.CallToolResult:
        args = params.arguments or {}
        name = params.name

        if name == "get_body_metrics":
            text = server.get_body_metrics(args.get("metric"))
        elif name == "update_body_metrics":
            text = server.update_body_metrics(
                weight=args.get("weight"),
                systolic=args.get("systolic"),
                diastolic=args.get("diastolic"),
                heart_rate=args.get("heart_rate"),
                height=args.get("height"),
                name=args.get("name"),
                date=args.get("date"),
                note=args.get("note"),
            )
            await server.broadcast()
        elif name == "record_strength":
            text = server.record_strength(
                exercise=args["exercise"],
                metric=args["metric"],
                value=args["value"],
                unit=args.get("unit"),
                category=args.get("category"),
                date=args.get("date"),
                note=args.get("note"),
            )
            await server.broadcast()
        elif name == "record_workout":
            text = server.record_workout(
                exercise=args["exercise"],
                sets=args.get("sets"),
                reps=args.get("reps"),
                weight=args.get("weight"),
                calories=args.get("calories"),
                feeling=args.get("feeling"),
                date=args.get("date"),
                note=args.get("note"),
            )
            await server.broadcast()
        elif name == "get_strength_history":
            text = server.get_strength_history(args["exercise"])
        elif name == "get_workout_diary":
            text = server.get_workout_diary(args.get("limit"))
        elif name == "update_workout":
            patch_keys = (
                "exercise", "sets", "reps", "weight",
                "calories", "feeling", "date", "note",
            )
            fields = {k: args[k] for k in patch_keys if k in args}
            text = server.update_workout(args["entry_id"], **fields)
            await server.broadcast()
        elif name == "delete_workout":
            text = server.delete_workout(args["entry_id"])
            await server.broadcast()
        elif name == "record_diet":
            text = server.record_diet(
                food=args["food"],
                calories=args["calories"],
                meal=args.get("meal"),
                quantity=args.get("quantity"),
                carbs=args.get("carbs"),
                protein=args.get("protein"),
                fat=args.get("fat"),
                date=args.get("date"),
                note=args.get("note"),
            )
            await server.broadcast()
        elif name == "get_diet_log":
            text = server.get_diet_log(args.get("date"))
        elif name == "update_diet":
            # 只把 Agent 实际传入的字段下发给 patch，未传入的不动
            patch_keys = (
                "food", "calories", "meal", "quantity",
                "carbs", "protein", "fat", "date", "note",
            )
            fields = {k: args[k] for k in patch_keys if k in args}
            text = server.update_diet(args["entry_id"], **fields)
            await server.broadcast()
        elif name == "delete_diet":
            text = server.delete_diet(args["entry_id"])
            await server.broadcast()
        elif name == "set_diet_goals":
            text = server.set_diet_goals(
                goal=args.get("goal"),
                carbs=args.get("carbs"),
                protein=args.get("protein"),
                fat=args.get("fat"),
            )
            await server.broadcast()
        elif name == "get_diet_goals":
            text = server.get_diet_goals()
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

    server = HealthServer()
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
        log("INFO", "stdio_ready")

        async with anyio.create_task_group() as tg:
            tg.start_soon(
                mcp.run,
                read_stream,
                write_stream,
                mcp.create_initialization_options(),
            )
            tg.start_soon(uv_server.serve)
