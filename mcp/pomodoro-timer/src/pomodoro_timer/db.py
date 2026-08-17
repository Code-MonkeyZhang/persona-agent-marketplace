"""
SQLite persistence for pomodoro focus sessions and app settings.

Uses stdlib sqlite3 with PRAGMA user_version for forward-only migrations.
Two tables: focus_sessions (one row per completed/interrupted focus) and
app_settings (single-row, id=1).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .log import log

_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS focus_sessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at   TEXT NOT NULL,
    ended_at     TEXT NOT NULL,
    duration_min INTEGER NOT NULL,
    intent       TEXT DEFAULT '',
    completed    INTEGER NOT NULL DEFAULT 1,
    agent_id     TEXT DEFAULT '',
    session_id   TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_focus_started ON focus_sessions(started_at);

CREATE TABLE IF NOT EXISTS app_settings (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    focus_min       INTEGER NOT NULL DEFAULT 25,
    short_break_min INTEGER NOT NULL DEFAULT 5,
    long_break_min  INTEGER NOT NULL DEFAULT 15,
    focus_per_round INTEGER NOT NULL DEFAULT 4
);
"""

# v2: unify short_break_min + long_break_min into single break_min.
# SQLite cannot DROP COLUMN before 3.35, so rebuild the table.
_SCHEMA_V2 = """
CREATE TABLE app_settings_new (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    focus_min       INTEGER NOT NULL DEFAULT 25,
    break_min       INTEGER NOT NULL DEFAULT 5,
    focus_per_round INTEGER NOT NULL DEFAULT 4
);
INSERT INTO app_settings_new (id, focus_min, break_min, focus_per_round)
    SELECT id, focus_min, short_break_min, focus_per_round FROM app_settings;
DROP TABLE app_settings;
ALTER TABLE app_settings_new RENAME TO app_settings;
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FocusDB:
    """SQLite-backed focus session and settings store."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        self._conn.commit()
        log("INFO", "db_ready", path=str(db_path))

    def _migrate(self) -> None:
        version = self._conn.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            self._conn.executescript(_SCHEMA_V1)
            self._conn.execute("INSERT OR IGNORE INTO app_settings (id) VALUES (1)")
            self._conn.execute("PRAGMA user_version = 1")
            log("INFO", "db_migrated", version=1)
        if version < 2:
            self._conn.executescript(_SCHEMA_V2)
            self._conn.execute("PRAGMA user_version = 2")
            log("INFO", "db_migrated", version=2)

    def record_session(
        self,
        started_at: str,
        ended_at: str,
        duration_min: int,
        intent: str,
        completed: bool,
        agent_id: str,
        session_id: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO focus_sessions "
            "(started_at, ended_at, duration_min, intent, completed, "
            "agent_id, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                started_at, ended_at, duration_min, intent,
                1 if completed else 0, agent_id, session_id,
            ),
        )
        self._conn.commit()

    def get_history(self, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM focus_sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_sessions_for_month(self, year: int, month: int) -> list[dict]:
        """Return all sessions whose started_at falls in the given month.

        Uses string comparison on ISO 8601 started_at with 1-day padding
        to account for timezone offsets.
        """
        start = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end = f"{year + 1:04d}-01-01"
        else:
            end = f"{year:04d}-{month + 1:02d}-01"
        # Pad by 1 day on each side for timezone safety
        start_dt = datetime.fromisoformat(start) - timedelta(days=1)
        end_dt = datetime.fromisoformat(end) + timedelta(days=1)
        rows = self._conn.execute(
            "SELECT * FROM focus_sessions "
            "WHERE started_at >= ? AND started_at < ? "
            "ORDER BY started_at ASC",
            (start_dt.isoformat(), end_dt.isoformat()),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        """Return today and week aggregate stats (completed sessions only)."""
        today_row = self._conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(duration_min), 0) AS mins "
            "FROM focus_sessions "
            "WHERE date(started_at) = date('now') AND completed = 1"
        ).fetchone()
        week_row = self._conn.execute(
            "SELECT COUNT(*) AS cnt, COALESCE(SUM(duration_min), 0) AS mins "
            "FROM focus_sessions "
            "WHERE date(started_at) >= date('now', '-6 days') AND completed = 1"
        ).fetchone()
        return {
            "today_count": today_row["cnt"],
            "today_minutes": today_row["mins"],
            "week_count": week_row["cnt"],
            "week_minutes": week_row["mins"],
        }

    def get_settings(self) -> dict:
        row = self._conn.execute(
            "SELECT focus_min, break_min, focus_per_round "
            "FROM app_settings WHERE id = 1"
        ).fetchone()
        return dict(row)

    def update_settings(
        self,
        focus_min: int,
        break_min: int,
        focus_per_round: int,
    ) -> None:
        self._conn.execute(
            "UPDATE app_settings SET focus_min = ?, break_min = ?, "
            "focus_per_round = ? WHERE id = 1",
            (focus_min, break_min, focus_per_round),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
