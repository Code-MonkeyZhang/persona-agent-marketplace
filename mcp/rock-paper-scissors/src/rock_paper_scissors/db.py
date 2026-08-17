"""
SQLite persistence for best-of-3 match history.

Two tables:
- games: one row per match (start_game → someone reaches WINS_NEEDED, or
  abandoned when a new match starts)
- rounds: one row per round (each play_move result, including draws that
  were replayed — same round_no can appear multiple times)

Uses stdlib sqlite3 with synchronous calls — data volume is tiny and
operations complete in microseconds, so event-loop blocking is negligible.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .log import log

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id          TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL,
    ended_at    TEXT,
    user_score  INTEGER NOT NULL DEFAULT 0,
    agent_score INTEGER NOT NULL DEFAULT 0,
    winner      TEXT,
    agent_id    TEXT NOT NULL,
    session_id  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS rounds (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id            TEXT NOT NULL REFERENCES games(id),
    round_no           INTEGER NOT NULL,
    timestamp          TEXT NOT NULL,
    user_move          TEXT NOT NULL,
    agent_move         TEXT NOT NULL,
    result             TEXT NOT NULL,
    user_score_after   INTEGER NOT NULL,
    agent_score_after  INTEGER NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class HistoryDB:
    """SQLite-backed match history store."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()
        log("INFO", "db_ready", path=str(db_path))

    def _migrate(self) -> None:
        """Add `winner` column to legacy games tables (pre-best-of-3)."""
        cols = {c["name"] for c in self._conn.execute("PRAGMA table_info(games)")}
        if "winner" not in cols:
            self._conn.execute("ALTER TABLE games ADD COLUMN winner TEXT")
            log("INFO", "db_migrated", change="added winner column to games")

    def start_game(
        self, game_id: str, agent_id: str, session_id: str
    ) -> None:
        self._conn.execute(
            "INSERT INTO games (id, started_at, agent_id, session_id) "
            "VALUES (?, ?, ?, ?)",
            (game_id, _now(), agent_id, session_id),
        )
        self._conn.commit()

    def end_game(
        self,
        game_id: str,
        user_score: int,
        agent_score: int,
        winner: str | None = None,
    ) -> None:
        self._conn.execute(
            "UPDATE games SET ended_at = ?, user_score = ?, agent_score = ?, "
            "winner = ? WHERE id = ?",
            (_now(), user_score, agent_score, winner, game_id),
        )
        self._conn.commit()

    def add_round(
        self,
        game_id: str,
        round_no: int,
        user_move: str,
        agent_move: str,
        result: str,
        user_score: int,
        agent_score: int,
    ) -> None:
        self._conn.execute(
            "INSERT INTO rounds "
            "(game_id, round_no, timestamp, user_move, agent_move, "
            "result, user_score_after, agent_score_after) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                game_id,
                round_no,
                _now(),
                user_move,
                agent_move,
                result,
                user_score,
                agent_score,
            ),
        )
        self._conn.commit()

    def get_history(self, completed_only: bool = False) -> list[dict]:
        """Return games with their rounds, newest game first.

        - completed_only=True: exclude in-progress matches (ended_at IS NULL).
          Used for the Web UI history panel so an active match never leaks in.
        - completed_only=False: all matches. Used for the Agent's
          get_game_history tool, which needs to see the current match too.
        """
        query = "SELECT * FROM games"
        if completed_only:
            query += " WHERE ended_at IS NOT NULL"
        query += " ORDER BY started_at DESC"
        games = self._conn.execute(query).fetchall()

        result = []
        for g in games:
            rounds = self._conn.execute(
                # Order by id (insertion order) so replayed draws stay in sequence
                "SELECT * FROM rounds WHERE game_id = ? ORDER BY id",
                (g["id"],),
            ).fetchall()
            result.append(
                {
                    "gameId": g["id"],
                    "startedAt": g["started_at"],
                    "endedAt": g["ended_at"],
                    "userScore": g["user_score"],
                    "agentScore": g["agent_score"],
                    "winner": g["winner"],
                    "rounds": [
                        {
                            "roundNo": r["round_no"],
                            "userMove": r["user_move"],
                            "agentMove": r["agent_move"],
                            "result": r["result"],
                        }
                        for r in rounds
                    ],
                }
            )
        return result

    def close(self) -> None:
        self._conn.close()
