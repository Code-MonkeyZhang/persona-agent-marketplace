"""
SQLite persistence for health data.

The store is split into per-module tables:
- profile: single-row table of static attributes like height
- daily_metrics: one row per date, holding weight / blood pressure / heart rate
- strength_records: best-performance points per exercise for the fitness module
- workout_entries: workout diary entries for the fitness module
- diet_entries: per-food diet records for the diet module
- settings: simple key-value store for preferences like the diet calorie goal

Schema versioning via PRAGMA user_version enables automatic migration on app
startup — users updating the app get schema changes applied transparently.
On first launch (v0 → v1) existing CSV data is imported without modifying the
original file.
"""

from __future__ import annotations

import csv
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .log import log

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS profile (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    height      REAL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS daily_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL UNIQUE,
    weight      REAL,
    systolic    INTEGER,
    diastolic   INTEGER,
    heart_rate  INTEGER,
    note        TEXT,
    created_at  TEXT NOT NULL
);
"""

_SCHEMA_V2 = """
CREATE TABLE IF NOT EXISTS strength_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    exercise    TEXT NOT NULL,
    metric      TEXT NOT NULL,
    value       REAL NOT NULL,
    unit        TEXT,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workout_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    exercise    TEXT NOT NULL,
    sets        INTEGER,
    reps        INTEGER,
    weight      REAL,
    feeling     TEXT,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS diet_entries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    date        TEXT NOT NULL,
    meal        TEXT,
    food_text   TEXT NOT NULL,
    calories    INTEGER NOT NULL,
    note        TEXT,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key         TEXT PRIMARY KEY,
    value       TEXT NOT NULL
);
"""

_SCHEMA_V3 = "ALTER TABLE profile ADD COLUMN name TEXT;"

_SCHEMA_V4 = """
ALTER TABLE diet_entries ADD COLUMN quantity TEXT;
ALTER TABLE diet_entries ADD COLUMN carbs_g REAL;
ALTER TABLE diet_entries ADD COLUMN protein_g REAL;
ALTER TABLE diet_entries ADD COLUMN fat_g REAL;
"""

_SCHEMA_V5 = "ALTER TABLE workout_entries ADD COLUMN calories INTEGER;"

_SCHEMA_V6 = "ALTER TABLE strength_records ADD COLUMN category TEXT;"

_DIET_MEALS = {"breakfast", "lunch", "dinner", "snack"}
_GOAL_MODES = {"auto", "manual"}

# Macro target share of the calorie goal, and kcal per gram for conversion
_MACRO_RATIOS = {"carbs": 0.50, "protein": 0.25, "fat": 0.25}
_KCAL_PER_GRAM = {"carbs": 4, "protein": 4, "fat": 9}

_HEART_RATE_RE = re.compile(r"心率(\d+)")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HealthDB:
    """SQLite-backed health metric store."""

    # Ranges are sanity bounds to catch absurd input, not medical norms
    _RANGES = {
        "weight": (20, 300),
        "systolic": (60, 250),
        "diastolic": (40, 200),
        "heart_rate": (30, 250),
        "height": (50, 250),
        "strength_value": (1, 500),
        "sets": (1, 100),
        "reps": (1, 500),
        "workout_weight": (0, 500),
        "workout_calories": (0, 3000),
        "calories": (0, 5000),
        "diet_goal": (500, 10000),
        "carbs": (0, 500),
        "protein": (0, 500),
        "fat": (0, 500),
        "macro_goal": (0, 1000),
    }

    def __init__(self, db_path: Path, csv_path: Path | None = None) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._migrate(csv_path)
        log("INFO", "db_ready", path=str(db_path))

    @property
    def schema_version(self) -> int:
        return self._conn.execute("PRAGMA user_version").fetchone()[0]

    # --- Schema migration ---------------------------------------------------

    def _migrate(self, csv_path: Path | None) -> None:
        """Apply schema migrations based on PRAGMA user_version."""
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]

        if version < 1:
            self._conn.executescript(_SCHEMA_V1)
            self._conn.execute("PRAGMA user_version = 1")
            if csv_path and csv_path.exists():
                count = self._import_csv(csv_path)
                log("INFO", "db_migrated", version=1, csv_imported=count)
            else:
                log("INFO", "db_migrated", version=1, csv_imported=0)
            self._conn.commit()

        if version < 2:
            self._conn.executescript(_SCHEMA_V2)
            self._conn.execute("PRAGMA user_version = 2")
            self._conn.commit()
            log("INFO", "db_migrated", version=2)

        if version < 3:
            self._conn.execute(_SCHEMA_V3)
            self._conn.execute("PRAGMA user_version = 3")
            self._conn.commit()
            log("INFO", "db_migrated", version=3)

        if version < 4:
            self._conn.executescript(_SCHEMA_V4)
            self._conn.execute("PRAGMA user_version = 4")
            self._conn.commit()
            log("INFO", "db_migrated", version=4)

        if version < 5:
            self._conn.execute(_SCHEMA_V5)
            self._conn.execute("PRAGMA user_version = 5")
            self._conn.commit()
            log("INFO", "db_migrated", version=5)

        if version < 6:
            self._conn.execute(_SCHEMA_V6)
            self._conn.execute("PRAGMA user_version = 6")
            self._conn.commit()
            log("INFO", "db_migrated", version=6)

    def _import_csv(self, csv_path: Path) -> int:
        """Import existing daily_metrics.csv data. Original file stays untouched."""
        imported = 0
        with open(csv_path, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                date = (row.get("日期") or "").strip()
                if not date:
                    continue
                weight = _parse_float(row.get("体重(kg)"))
                systolic = _parse_int(row.get("收缩压(高压)"))
                diastolic = _parse_int(row.get("舒张压(低压)"))
                note = (row.get("备注") or "").strip()
                heart_rate = None
                m = _HEART_RATE_RE.search(note)
                if m:
                    heart_rate = int(m.group(1))
                self._conn.execute(
                    "INSERT OR IGNORE INTO daily_metrics "
                    "(date, weight, systolic, diastolic, heart_rate, note, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (date, weight, systolic, diastolic, heart_rate, note, _now()),
                )
                imported += 1
        return imported

    # --- Profile ------------------------------------------------------------

    def set_profile(self, height: float) -> None:
        """Upsert height into the single-row profile table."""
        self._validate("height", height)
        self._conn.execute(
            "INSERT INTO profile (id, height, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET height = excluded.height, "
            "updated_at = excluded.updated_at",
            (height, _now()),
        )
        self._conn.commit()

    def set_name(self, name: str) -> None:
        """Upsert the user's display name into the single-row profile table."""
        self._conn.execute(
            "INSERT INTO profile (id, name, updated_at) VALUES (1, ?, ?) "
            "ON CONFLICT(id) DO UPDATE SET name = excluded.name, "
            "updated_at = excluded.updated_at",
            (name, _now()),
        )
        self._conn.commit()

    def get_profile(self) -> dict | None:
        row = self._conn.execute(
            "SELECT height, name, updated_at FROM profile WHERE id = 1"
        ).fetchone()
        if not row:
            return None
        if row["height"] is None and row["name"] is None:
            return None
        return {
            "height": row["height"],
            "name": row["name"],
            "updatedAt": row["updated_at"],
        }

    # --- Daily metrics ------------------------------------------------------

    def record_weight(self, date: str, weight: float, note: str | None = None) -> dict:
        """Record body weight for a date. Returns current + previous + change."""
        self._validate("weight", weight)
        prev = self._latest("weight", date)
        self._upsert_metric(date, weight=weight, note=note)
        return self._diff("weight", weight, prev)

    def record_blood_pressure(
        self,
        date: str,
        systolic: int,
        diastolic: int,
        heart_rate: int | None = None,
        note: str | None = None,
    ) -> dict:
        """Record blood pressure and optional heart rate. Returns comparison."""
        self._validate("systolic", systolic)
        self._validate("diastolic", diastolic)
        if heart_rate is not None:
            self._validate("heart_rate", heart_rate)
        prev = self._latest("bp", date)
        fields: dict = {"systolic": systolic, "diastolic": diastolic}
        if heart_rate is not None:
            fields["heart_rate"] = heart_rate
        if note:
            fields["note"] = note
        self._upsert_metric(date, **fields)
        return self._diff_bp(systolic, diastolic, heart_rate, prev)

    def get_latest(self, metric: str | None = None) -> dict | None:
        """Return the most recent metric record. Optional filter by type."""
        if metric == "weight":
            row = self._conn.execute(
                "SELECT * FROM daily_metrics WHERE weight IS NOT NULL "
                "ORDER BY date DESC LIMIT 1"
            ).fetchone()
        elif metric == "blood_pressure":
            row = self._conn.execute(
                "SELECT * FROM daily_metrics WHERE systolic IS NOT NULL "
                "ORDER BY date DESC LIMIT 1"
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM daily_metrics ORDER BY date DESC LIMIT 1"
            ).fetchone()
        return _row_to_dict(row) if row else None

    def get_all_metrics(self) -> list[dict]:
        """Return all daily metric records ordered by date (for charting)."""
        rows = self._conn.execute(
            "SELECT * FROM daily_metrics ORDER BY date ASC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # --- Fitness (strength records + workout diary) -------------------------

    def record_strength(
        self,
        date: str,
        exercise: str,
        metric: str,
        value: float,
        unit: str | None = None,
        category: str | None = None,
        note: str | None = None,
    ) -> dict:
        """Record a best-performance point. Returns current + previous + change."""
        self._validate("strength_value", value)
        prev = self._conn.execute(
            "SELECT * FROM strength_records WHERE exercise = ? AND metric = ? "
            "AND date < ? ORDER BY date DESC, id DESC LIMIT 1",
            (exercise, metric, date),
        ).fetchone()
        self._conn.execute(
            "INSERT INTO strength_records (date, exercise, metric, value, unit, category, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (date, exercise, metric, value, unit, category, note, _now()),
        )
        self._conn.commit()
        result: dict = {"exercise": exercise, "metric": metric, "value": value, "category": category}
        if prev and prev["value"] is not None:
            result["previous"] = prev["value"]
            result["previousDate"] = prev["date"]
            result["change"] = round(value - prev["value"], 1)
        return result

    def record_workout(
        self,
        date: str,
        exercise: str,
        sets: int | None = None,
        reps: int | None = None,
        weight: float | None = None,
        feeling: str | None = None,
        calories: int | None = None,
        note: str | None = None,
    ) -> dict:
        """Record one workout diary entry."""
        if sets is not None:
            self._validate("sets", sets)
        if reps is not None:
            self._validate("reps", reps)
        if weight is not None:
            self._validate("workout_weight", weight)
        if calories is not None:
            self._validate("workout_calories", calories)
        self._conn.execute(
            "INSERT INTO workout_entries (date, exercise, sets, reps, weight, feeling, calories, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date, exercise, sets, reps, weight, feeling, calories, note, _now()),
        )
        self._conn.commit()
        return {"date": date, "exercise": exercise, "sets": sets, "reps": reps, "weight": weight, "calories": calories}

    def get_strength_records(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM strength_records ORDER BY date ASC, id ASC"
        ).fetchall()
        return [_strength_to_dict(r) for r in rows]

    def get_workout_entries(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM workout_entries ORDER BY date DESC, id DESC"
        ).fetchall()
        return [_workout_to_dict(r) for r in rows]

    def update_workout_entry(self, entry_id: int, **fields) -> dict | None:
        """Patch a workout entry by id.

        - 只改 fields 里出现的字段，未传入的保持原样
        - 校验数值范围
        - 找不到记录返回 None
        """
        row = self._conn.execute(
            "SELECT * FROM workout_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            return None

        col_map = {
            "exercise": "exercise",
            "sets": "sets",
            "reps": "reps",
            "weight": "weight",
            "feeling": "feeling",
            "calories": "calories",
            "date": "date",
            "note": "note",
        }
        updates: dict = {}
        for friendly, col in col_map.items():
            if friendly not in fields:
                continue
            val = fields[friendly]
            if friendly in ("sets", "reps") and val is not None:
                self._validate(friendly, val)
            if friendly == "weight" and val is not None:
                self._validate("workout_weight", val)
            if friendly == "calories" and val is not None:
                self._validate("workout_calories", val)
            updates[col] = val

        if updates:
            set_clause = ", ".join(f"{c} = ?" for c in updates)
            self._conn.execute(
                f"UPDATE workout_entries SET {set_clause} WHERE id = ?",
                [*updates.values(), entry_id],
            )
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM workout_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return _workout_to_dict(row)

    def delete_workout_entry(self, entry_id: int) -> bool:
        """Delete a workout entry by id. Returns whether a row was removed."""
        cur = self._conn.execute("DELETE FROM workout_entries WHERE id = ?", (entry_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # --- Diet ---------------------------------------------------------------

    def record_diet(
        self,
        date: str,
        food_text: str,
        calories: int,
        meal: str | None = None,
        quantity: str | None = None,
        carbs: float | None = None,
        protein: float | None = None,
        fat: float | None = None,
        note: str | None = None,
    ) -> dict:
        """Record one diet entry. Returns the day's running calorie total."""
        if meal is not None and meal not in _DIET_MEALS:
            raise ValueError(f"未知餐别 {meal}，应为 {'/'.join(sorted(_DIET_MEALS))}")
        self._validate("calories", calories)
        for name, val in (("carbs", carbs), ("protein", protein), ("fat", fat)):
            if val is not None:
                self._validate(name, val)
        self._conn.execute(
            "INSERT INTO diet_entries "
            "(date, meal, food_text, quantity, calories, carbs_g, protein_g, fat_g, note, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (date, meal, food_text, quantity, calories, carbs, protein, fat, note, _now()),
        )
        self._conn.commit()
        total = self._conn.execute(
            "SELECT COALESCE(SUM(calories), 0) AS total FROM diet_entries WHERE date = ?",
            (date,),
        ).fetchone()["total"]
        return {"date": date, "food": food_text, "calories": calories, "dailyTotal": total}

    def update_diet_entry(self, entry_id: int, **fields) -> dict | None:
        """Patch a diet entry by id.

        - 只改 fields 里出现的字段，未传入的保持原样
        - 校验餐别枚举与数值范围
        - 找不到记录返回 None
        """
        row = self._conn.execute(
            "SELECT * FROM diet_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            return None

        # tool 友好名 -> 列名
        col_map = {
            "food": "food_text",
            "calories": "calories",
            "meal": "meal",
            "quantity": "quantity",
            "carbs": "carbs_g",
            "protein": "protein_g",
            "fat": "fat_g",
            "note": "note",
            "date": "date",
        }
        updates: dict = {}
        for friendly, col in col_map.items():
            if friendly not in fields:
                continue
            val = fields[friendly]
            if friendly == "meal" and val is not None and val not in _DIET_MEALS:
                raise ValueError(
                    f"未知餐别 {val}，应为 {'/'.join(sorted(_DIET_MEALS))}"
                )
            if friendly in ("calories", "carbs", "protein", "fat") and val is not None:
                self._validate(friendly, val)
            updates[col] = val

        if updates:
            set_clause = ", ".join(f"{c} = ?" for c in updates)
            self._conn.execute(
                f"UPDATE diet_entries SET {set_clause} WHERE id = ?",
                [*updates.values(), entry_id],
            )
            self._conn.commit()

        row = self._conn.execute(
            "SELECT * FROM diet_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        return _diet_to_dict(row)

    def delete_diet_entry(self, entry_id: int) -> bool:
        """Delete a diet entry by id. Returns whether a row was removed."""
        cur = self._conn.execute("DELETE FROM diet_entries WHERE id = ?", (entry_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_diet_entries(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM diet_entries ORDER BY date ASC, id ASC"
        ).fetchall()
        return [_diet_to_dict(r) for r in rows]

    # --- Settings (diet calorie goal, macro goals, goal mode) --------------

    def _set_setting(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._conn.commit()

    def _get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_diet_goal(self, goal: int) -> None:
        self._validate("diet_goal", goal)
        self._set_setting("diet_goal", str(goal))

    def get_diet_goal(self) -> int | None:
        raw = self._get_setting("diet_goal")
        return int(raw) if raw is not None else None

    def set_goal_mode(self, mode: str) -> None:
        """Switch macro-goal resolution between auto (derived) and manual."""
        if mode not in _GOAL_MODES:
            raise ValueError(f"未知目标模式 {mode}，应为 {'/'.join(sorted(_GOAL_MODES))}")
        self._set_setting("goal_mode", mode)

    def set_macro_goals(self, carbs: int, protein: int, fat: int) -> None:
        """Store manual macro goals (grams) and switch to manual mode."""
        for val in (carbs, protein, fat):
            self._validate("macro_goal", val)
        self._set_setting("carb_goal", str(carbs))
        self._set_setting("protein_goal", str(protein))
        self._set_setting("fat_goal", str(fat))
        self._set_setting("goal_mode", "manual")

    def get_macro_goals(self) -> dict:
        """Resolve effective macro goals by mode.

        - auto: derive grams from the calorie goal via fixed ratios
        - manual: read stored grams
        Returns {mode, carbs, protein, fat}; grams are None when not resolvable.
        """
        mode = self._get_setting("goal_mode", "auto")
        if mode == "manual":
            return {
                "mode": "manual",
                "carbs": _parse_int(self._get_setting("carb_goal")),
                "protein": _parse_int(self._get_setting("protein_goal")),
                "fat": _parse_int(self._get_setting("fat_goal")),
            }
        calorie = self.get_diet_goal()
        if calorie is None:
            return {"mode": "auto", "carbs": None, "protein": None, "fat": None}
        return {
            "mode": "auto",
            "carbs": round(calorie * _MACRO_RATIOS["carbs"] / _KCAL_PER_GRAM["carbs"]),
            "protein": round(calorie * _MACRO_RATIOS["protein"] / _KCAL_PER_GRAM["protein"]),
            "fat": round(calorie * _MACRO_RATIOS["fat"] / _KCAL_PER_GRAM["fat"]),
        }

    # --- Snapshot for WebSocket push ---------------------------------------

    def get_snapshot(self) -> dict:
        """Return full state for the frontend, namespaced by module."""
        macro = self.get_macro_goals()
        return {
            "basics": {
                "profile": self.get_profile(),
                "metrics": self.get_all_metrics(),
            },
            "diet": {
                "entries": self.get_diet_entries(),
                "goal": self.get_diet_goal(),
                "goalMode": macro["mode"],
                "macroGoals": {
                    "carbs": macro["carbs"],
                    "protein": macro["protein"],
                    "fat": macro["fat"],
                },
            },
            "fitness": {
                "strengthRecords": self.get_strength_records(),
                "workouts": self.get_workout_entries(),
            },
        }

    # --- Internal helpers ---------------------------------------------------

    def _validate(self, name: str, value: float) -> None:
        lo, hi = self._RANGES[name]
        if not (lo <= value <= hi):
            raise ValueError(f"{name}值 {value} 超出合理范围 {lo}-{hi}")

    def _latest(self, kind: str, before_date: str) -> sqlite3.Row | None:
        """Fetch the previous record of a given kind before a date."""
        if kind == "weight":
            return self._conn.execute(
                "SELECT * FROM daily_metrics "
                "WHERE weight IS NOT NULL AND date < ? ORDER BY date DESC LIMIT 1",
                (before_date,),
            ).fetchone()
        return self._conn.execute(
            "SELECT * FROM daily_metrics "
            "WHERE systolic IS NOT NULL AND date < ? ORDER BY date DESC LIMIT 1",
            (before_date,),
        ).fetchone()

    def _upsert_metric(self, date: str, **fields) -> None:
        """Insert or update a daily metric row by date."""
        row = self._conn.execute(
            "SELECT id FROM daily_metrics WHERE date = ?", (date,)
        ).fetchone()
        if row:
            set_clauses = ", ".join(f"{k} = ?" for k in fields)
            values = list(fields.values()) + [row["id"]]
            self._conn.execute(
                f"UPDATE daily_metrics SET {set_clauses} WHERE id = ?", values
            )
        else:
            cols = ["date", "created_at"] + list(fields.keys())
            placeholders = ", ".join("?" for _ in cols)
            values = [date, _now()] + list(fields.values())
            self._conn.execute(
                f"INSERT INTO daily_metrics ({', '.join(cols)}) "
                f"VALUES ({placeholders})",
                values,
            )
        self._conn.commit()

    @staticmethod
    def _diff(field: str, current: float, prev: sqlite3.Row | None) -> dict:
        """Build a comparison result for a single numeric metric."""
        result: dict = {"current": current}
        if prev and prev[field] is not None:
            result["previous"] = prev[field]
            result["previousDate"] = prev["date"]
            result["change"] = round(current - prev[field], 1)
        return result

    @staticmethod
    def _diff_bp(
        systolic: int,
        diastolic: int,
        heart_rate: int | None,
        prev: sqlite3.Row | None,
    ) -> dict:
        """Build a comparison result for blood pressure + heart rate."""
        result: dict = {"systolic": systolic, "diastolic": diastolic}
        if heart_rate is not None:
            result["heartRate"] = heart_rate
        if prev and prev["systolic"] is not None:
            result["prevSystolic"] = prev["systolic"]
            result["prevDiastolic"] = prev["diastolic"]
            result["previousDate"] = prev["date"]
            result["systolicChange"] = systolic - prev["systolic"]
            result["diastolicChange"] = diastolic - prev["diastolic"]
        return result

    def close(self) -> None:
        self._conn.close()


# --- Module-level helpers --------------------------------------------------


def _parse_float(val: str | None) -> float | None:
    s = (val or "").strip()
    return float(s) if s else None


def _parse_int(val: str | None) -> int | None:
    s = (val or "").strip()
    return int(s) if s else None


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "date": row["date"],
        "weight": row["weight"],
        "systolic": row["systolic"],
        "diastolic": row["diastolic"],
        "heartRate": row["heart_rate"],
        "note": row["note"],
    }


def _strength_to_dict(row: sqlite3.Row) -> dict:
    return {
        "date": row["date"],
        "exercise": row["exercise"],
        "metric": row["metric"],
        "value": row["value"],
        "unit": row["unit"],
        "category": row["category"],
        "note": row["note"],
    }


def _workout_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "date": row["date"],
        "exercise": row["exercise"],
        "sets": row["sets"],
        "reps": row["reps"],
        "weight": row["weight"],
        "feeling": row["feeling"],
        "calories": row["calories"],
        "note": row["note"],
    }


def _diet_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "date": row["date"],
        "meal": row["meal"],
        "food": row["food_text"],
        "quantity": row["quantity"],
        "calories": row["calories"],
        "carbs": row["carbs_g"],
        "protein": row["protein_g"],
        "fat": row["fat_g"],
        "note": row["note"],
    }
