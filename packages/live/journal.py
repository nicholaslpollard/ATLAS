from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import TextIO

from packages.core.enums import LiveFeedMode
from packages.core.settings import AtlasSettings
from packages.core.timestamps import to_utc
from packages.data.paths import MarketDataPaths


class LiveEventJournal:
    """Append provisional provider events for later finalized-data reconciliation."""

    def __init__(self, settings: AtlasSettings, *, flush_every: int = 100) -> None:
        if flush_every < 1:
            raise ValueError("flush_every must be at least 1")
        self.paths = MarketDataPaths(settings)
        self.flush_every = flush_every
        self._handles: dict[date, TextIO] = {}
        self._pending: dict[date, int] = {}

    def _handle(self, session_date: date) -> TextIO:
        handle = self._handles.get(session_date)
        if handle is not None:
            return handle
        path = self.paths.live_journal_file(session_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = path.open("a", encoding="utf-8", newline="")
        self._handles[session_date] = handle
        self._pending[session_date] = 0
        return handle

    def append(
        self,
        raw_event: dict[str, object],
        *,
        session_date: date,
        received_at_utc: datetime,
        feed_mode: LiveFeedMode,
    ) -> Path:
        record = dict(raw_event)
        record["_atlas_received_at_utc"] = to_utc(received_at_utc).isoformat()
        record["_atlas_feed_mode"] = feed_mode.value
        handle = self._handle(session_date)
        handle.write(json.dumps(record, separators=(",", ":"), sort_keys=True) + "\n")
        pending = self._pending[session_date] + 1
        self._pending[session_date] = pending
        if pending >= self.flush_every:
            handle.flush()
            self._pending[session_date] = 0
        return self.paths.live_journal_file(session_date)

    def flush(self) -> None:
        for session_date, handle in self._handles.items():
            handle.flush()
            self._pending[session_date] = 0

    def close(self) -> None:
        for handle in self._handles.values():
            try:
                handle.flush()
            finally:
                handle.close()
        self._handles.clear()
        self._pending.clear()

    def __enter__(self) -> "LiveEventJournal":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
