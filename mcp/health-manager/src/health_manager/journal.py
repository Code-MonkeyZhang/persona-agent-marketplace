"""Per-date journal files with pre-write snapshots.

The journal is one markdown file per date under the journal root and the file
name is the date, so directory order is the timeline and a bad write can only
damage the single entry it touches. Every overwrite first copies the current
file into the snapshot directory and only the newest few snapshots per entry
are kept.
"""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from .log import log

KEEP_SNAPSHOTS = 5

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Reserved non-date stem holding the pinned foundational history card.
BASICS_STEM = "basics"


def _parse_title(text: str) -> str | None:
    """First level-one heading of an entry, or None when it has none."""
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# ") and len(s) > 2:
            return s[2:].strip()
        if s:
            break
    return None


def _mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()


class JournalStore:
    """Dated journal entries stored as markdown files in one directory."""

    def __init__(
        self,
        root: Path,
        snapshot_root: Path | None = None,
        keep: int = KEEP_SNAPSHOTS,
    ) -> None:
        self._root = root
        self._snapshot_root = snapshot_root
        self._keep = keep
        self._root.mkdir(parents=True, exist_ok=True)

    def _entry_path(self, date: str) -> Path:
        if not _DATE_RE.match(date):
            raise ValueError(f"日期 {date} 格式应为 YYYY-MM-DD")
        return self._root / f"{date}.md"

    @property
    def _basics_path(self) -> Path:
        return self._root / f"{BASICS_STEM}.md"

    def read_basics(self) -> dict | None:
        """The foundational history entry, or None when it was never written."""
        path = self._basics_path
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        return {
            "date": BASICS_STEM,
            "title": _parse_title(text),
            "content": text,
            "updatedAt": _mtime(path),
        }

    def write_basics(self, content: str) -> dict:
        """Create or replace the foundational history entry.

        - Snapshots the existing file first when a snapshot root is set
        - The entry is pinned by design and never joins the dated timeline
        """
        path = self._basics_path
        if path.exists():
            self._snapshot(path)
        path.write_text(content, encoding="utf-8")
        return {
            "date": BASICS_STEM,
            "title": _parse_title(content),
            "updatedAt": _mtime(path),
        }

    def list_entries(self) -> list[dict]:
        """Index of all entries, most recent first.

        - Returns one {date, title, content, updatedAt} per dated file
        - The full text rides along so the WS snapshot can render the view
        - The reserved basics entry stays out of the timeline
        """
        entries = []
        for path in self._root.glob("*.md"):
            if path.stem == BASICS_STEM:
                continue
            text = path.read_text(encoding="utf-8")
            entries.append(
                {
                    "date": path.stem,
                    "title": _parse_title(text),
                    "content": text,
                    "updatedAt": _mtime(path),
                }
            )
        entries.sort(key=lambda e: e["date"], reverse=True)
        return entries

    def read(self, date: str) -> dict | None:
        """Full entry of a date including content, or None when absent."""
        path = self._entry_path(date)
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8")
        return {
            "date": date,
            "title": _parse_title(text),
            "content": text,
            "updatedAt": _mtime(path),
        }

    def write(self, date: str, content: str, title: str | None = None) -> dict:
        """Create or replace the entry of a date.

        - Snapshots the existing file first when a snapshot root is set
        - A given title is prepended as heading unless content opens with one
        """
        path = self._entry_path(date)
        if path.exists():
            self._snapshot(path)
        if title and not content.lstrip().startswith("# "):
            content = f"# {title}\n\n{content}"
        path.write_text(content, encoding="utf-8")
        return {
            "date": date,
            "title": _parse_title(content),
            "updatedAt": _mtime(path),
        }

    def _snapshot(self, path: Path) -> None:
        """Copy the current entry into the snapshot dir and prune old copies."""
        if self._snapshot_root is None:
            return
        entry_dir = self._snapshot_root / path.stem
        entry_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        shutil.copy2(path, entry_dir / f"{stamp}.md")
        olds = sorted(entry_dir.glob("*.md"))
        # only prune once the entry holds more than the kept quota
        if len(olds) > self._keep:
            for old in olds[: len(olds) - self._keep]:
                old.unlink()
        log("INFO", "journal_snapshot_saved", entry=path.stem, kept=min(len(olds), self._keep))
