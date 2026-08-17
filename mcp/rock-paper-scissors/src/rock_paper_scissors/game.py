"""
Game state and judging logic for Rock-Paper-Scissors (best-of-3).

Pure logic — no I/O, no async. Shared between MCP tool handlers and WS handlers.

Match rules:
- A match is best-of-3: first side to WINS_NEEDED wins the match.
- A round is one move from each side. Draws replay the round: no score
  change, round number does not advance.
- Valid match scores are therefore 2-0 or 2-1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Move = Literal["rock", "paper", "scissors"]
Result = Literal["user_win", "agent_win", "draw"]
Winner = Literal["user", "agent"]

# First to this many round wins takes the match.
WINS_NEEDED = 2

MOVE_LABELS: dict[Move, str] = {
    "rock": "石头",
    "paper": "布",
    "scissors": "剪刀",
}

RESULT_TEXT: dict[Result, str] = {
    "user_win": "用户赢",
    "agent_win": "Agent赢",
    "draw": "平局",
}

# Which move beats which: key beats value.
_BEATS: dict[Move, Move] = {
    "rock": "scissors",
    "scissors": "paper",
    "paper": "rock",
}


def judge(user: Move, agent: Move) -> Result:
    """Judge a round. Returns who won from the user's perspective."""
    if user == agent:
        return "draw"
    if _BEATS[user] == agent:
        return "user_win"
    return "agent_win"


def match_winner(user_score: int, agent_score: int) -> Winner | None:
    """Return the match winner if someone reached WINS_NEEDED, else None."""
    if user_score >= WINS_NEEDED:
        return "user"
    if agent_score >= WINS_NEEDED:
        return "agent"
    return None


@dataclass
class GameState:
    """In-memory state for a single best-of-3 match.

    - round_no: current round number within the match (1-based)
    - user_score / agent_score: rounds won (first to WINS_NEEDED wins)
    - waiting_for_agent: True between the user's move and the agent's move
    - game_over / winner: set when someone reaches WINS_NEEDED
    - draws do not advance round_no or score (the round is replayed)
    """

    game_id: str
    agent_id: str
    session_id: str
    round_no: int = 1
    user_score: int = 0
    agent_score: int = 0
    last_user_move: Move | None = None
    last_agent_move: Move | None = None
    last_result: Result | None = None
    waiting_for_agent: bool = False
    user_move_pending: Move | None = None
    game_over: bool = False
    winner: Winner | None = None

    def to_dict(self) -> dict:
        """Serialize to a dict suitable for WS broadcast."""
        return {
            "gameId": self.game_id,
            "roundNo": self.round_no,
            "userScore": self.user_score,
            "agentScore": self.agent_score,
            "lastUserMove": self.last_user_move,
            "lastAgentMove": self.last_agent_move,
            "lastResult": self.last_result,
            "waitingForAgent": self.waiting_for_agent,
            "gameOver": self.game_over,
            "winner": self.winner,
        }
