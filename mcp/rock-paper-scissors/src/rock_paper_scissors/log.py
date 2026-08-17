"""
Structured JSON logger writing to a local file and stderr.

stdout is reserved exclusively for JSON-RPC — never log there.
The log file is truncated on each initialize() call for a clean start.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_log_file: Path | None = None


def initialize(log_path: Path) -> None:
    """Create or truncate the log file. Must be called before log()."""
    global _log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _log_file = log_path
    # Truncate (or create) the file
    _log_file.write_text("")
    sys.stderr.write(
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": "INFO",
                "event": "log_initialized",
                "path": str(log_path),
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    sys.stderr.flush()


def log(level: str, event: str, **data: object) -> None:
    """Write a structured JSON log line to both the log file and stderr."""
    line = (
        json.dumps(
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": level,
                "event": event,
                **data,
            },
            ensure_ascii=False,
        )
        + "\n"
    )
    if _log_file:
        with open(_log_file, "a") as f:
            f.write(line)
    sys.stderr.write(line)
    sys.stderr.flush()
