"""
Timer state and session config dataclasses for the pomodoro timer.

Pure data holders — all state mutation logic lives in server.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PHASE_IDLE = "idle"
PHASE_FOCUS = "focus"
PHASE_BREAK = "break"

PHASE_LABELS = {
    PHASE_IDLE: "空闲",
    PHASE_FOCUS: "专注",
    PHASE_BREAK: "休息",
}


@dataclass
class SessionConfig:
    """Definition of one focus session.

    A session runs `rounds` cycles of focus + break. Every round ends
    with its own break, including the last one.
    """

    focus_min: int = 25
    break_min: int = 5
    rounds: int = 1

    def to_dict(self) -> dict:
        return {
            "focus_min": self.focus_min,
            "break_min": self.break_min,
            "rounds": self.rounds,
        }


@dataclass
class TimerState:
    phase: str = PHASE_IDLE
    running: bool = False
    ends_at: float | None = None
    remaining_seconds: int = 0
    # Real total length of the current phase. The countdown ring reads
    # this directly instead of guessing from the session config.
    phase_total_seconds: int = 0
    intent: str = ""
    round_current: int = 0
    round_total: int = 0
    config: SessionConfig = field(default_factory=SessionConfig)
    # Notification routing (按任务记账): stored when the session starts,
    # used by both notifications for the whole session.
    owner_agent_id: str = ""
    owner_session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "running": self.running,
            "ends_at": self.ends_at,
            "remaining_seconds": self.remaining_seconds,
            "phase_total_seconds": self.phase_total_seconds,
            "intent": self.intent,
            "round_current": self.round_current,
            "round_total": self.round_total,
            "config": self.config.to_dict(),
        }
