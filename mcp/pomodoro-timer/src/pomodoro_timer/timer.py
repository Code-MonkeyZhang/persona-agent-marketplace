"""
Timer state and settings dataclasses for the pomodoro timer.

Pure data holders — all state mutation logic lives in server.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PHASE_IDLE = "idle"
PHASE_FOCUS = "focus"
PHASE_SHORT_BREAK = "short_break"
PHASE_LONG_BREAK = "long_break"

PHASE_LABELS = {
    PHASE_IDLE: "空闲",
    PHASE_FOCUS: "专注",
    PHASE_SHORT_BREAK: "短休息",
    PHASE_LONG_BREAK: "长休息",
}


@dataclass
class TimerSettings:
    focus_min: int = 25
    break_min: int = 5
    focus_per_round: int = 4

    def to_dict(self) -> dict:
        return {
            "focus_min": self.focus_min,
            "break_min": self.break_min,
            "focus_per_round": self.focus_per_round,
        }


@dataclass
class TimerState:
    phase: str = PHASE_IDLE
    running: bool = False
    ends_at: float | None = None
    remaining_seconds: int = 0
    intent: str = ""
    focus_count_in_round: int = 0
    settings: TimerSettings = field(default_factory=TimerSettings)
    # Notification routing (按任务记账): stored when focus starts,
    # used by all notifications for this pomodoro cycle.
    started_at: str = ""
    focus_agent_id: str = ""
    focus_session_id: str = ""

    def to_dict(self) -> dict:
        return {
            "phase": self.phase,
            "running": self.running,
            "ends_at": self.ends_at,
            "remaining_seconds": self.remaining_seconds,
            "intent": self.intent,
            "focus_count_in_round": self.focus_count_in_round,
            "settings": self.settings.to_dict(),
        }
