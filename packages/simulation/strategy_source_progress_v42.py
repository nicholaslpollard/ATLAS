from __future__ import annotations

"""V42 timestamped progress/heartbeat for long historical source acquisition.

Monitor only: no provider dispatch or source filtering occurs here.
It never predicts that a future demand will be a cache hit or a provider call.
"""

from datetime import datetime
import os
from pathlib import Path
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PROGRESS_CONTRACT = "atlas-source-runtime-progress-v42"
DEFAULT_HEARTBEAT_SECONDS = 15.0
DEFAULT_PROGRESS_EVERY = 25


def _duration(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


class SourceProgressMonitor:
    """Thread-safe console + retained progress log with periodic heartbeat.

    The background thread only emits progress for a running foreground source
    operation. It never makes requests, modifies data, or runs acquisition
    outside the active command.
    """

    def __init__(
        self, log_path: Path, *,
        expected_source_uses: int | None = None,
        heartbeat_seconds: float = DEFAULT_HEARTBEAT_SECONDS,
        every: int = DEFAULT_PROGRESS_EVERY,
    ) -> None:
        if (expected_source_uses is not None and
                (type(expected_source_uses) is not int or expected_source_uses < 0)):
            raise ValueError("EXPECTED_SOURCE_USES_INVALID")
        if heartbeat_seconds <= 0 or every < 1:
            raise ValueError("PROGRESS_INTERVAL_INVALID")
        self.log_path = log_path
        self.expected = expected_source_uses
        self.heartbeat_seconds = heartbeat_seconds
        self.every = every
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._file = None
        self._start = 0.0
        self._active_since = 0.0
        self._active = "startup"
        self._phase = "initializing"
        self._counts: dict = {}
        self._completed = 0
        self._last_printed_completed = 0
        self._last_heartbeat = 0.0

    def __enter__(self):
        if self.log_path.is_symlink() or self.log_path.exists():
            raise ValueError("PROGRESS_LOG_EXISTS_OR_LINK")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.log_path.open("x", encoding="utf-8", buffering=1)
        self._start = time.monotonic()
        self._active_since = self._start
        self._last_heartbeat = self._start
        with self._lock:
            self._emit_locked("START")
        self._thread = threading.Thread(
            target=self._heartbeat_loop, name="atlas-acquisition-progress",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=max(5.0, self.heartbeat_seconds + 2))
        with self._lock:
            self._phase = "ended"
            self._active = "none"
            self._emit_locked("STOPPED_WITH_ERROR" if exc_type else "FINISHED")
            if self._file is not None:
                self._file.flush()
                self._file.close()
                self._file = None

    def _heartbeat_loop(self):
        while not self._stop.wait(self.heartbeat_seconds):
            with self._lock:
                self._emit_locked("HEARTBEAT")

    def _emit_locked(self, event: str, error: str | None = None):
        elapsed = max(0.0, time.monotonic() - self._start)
        completed = self._completed
        total = "unknown" if self.expected is None else str(self.expected)
        pct = (
            ""
            if not self.expected else
            f" ({100.0 * min(completed, self.expected) / self.expected:.1f}%)"
        )
        rough_eta = "learning"
        if self.expected is not None and completed >= 25 and elapsed > 0:
            remaining = max(0, self.expected - completed)
            rough_eta = _duration(elapsed / completed * remaining)
        rate = completed / elapsed if elapsed > 0 else 0.0
        active_age = max(0.0, time.monotonic() - self._active_since)
        counts = self._counts
        line = (
            f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}]"
            f" {event}"
            f" completed={completed}/{total}{pct}"
            f" fetched={counts.get('provider_fetch_successes', 0)}"
            f" cache={counts.get('persisted_cache_hits', 0)}"
            f" provider_calls={counts.get('provider_dispatch_attempts', 0)}"
            f" no_data={counts.get('source_uses_explicit_no_data', 0)}"
            f" errors={counts.get('source_uses_failed_or_unresolved', 0)}"
            f" elapsed={_duration(elapsed)}"
            f" rate={rate:.2f}_source_uses/s"
            f" eta_rough={rough_eta}"
            f" active={self._active}"
            f" phase={self._phase}"
            f" active_for={_duration(active_age)}"
        )
        if error is not None:
            line += f" error={error[:160].replace(chr(10), ' ')}"
        print(line, flush=True)
        if self._file is not None:
            self._file.write(line + "\n")
            self._file.flush()
        self._last_heartbeat = time.monotonic()
        self._last_printed_completed = completed

    def event(self, kind: str, data: dict) -> None:
        with self._lock:
            self._counts = dict(data["counts"])
            current = f"{data['date_et']}:{data['purpose']}"
            if kind == "source_started":
                self._active = current
                self._phase = "checking_cache_or_source"
                self._active_since = time.monotonic()
                if self._counts.get("source_uses_requested") == 1:
                    self._emit_locked("FIRST_SOURCE")
            elif kind == "provider_dispatch":
                self._phase = "provider_request_in_flight"
                self._active_since = time.monotonic()
            elif kind in ("source_done", "source_failed"):
                self._completed = (
                    self._counts.get("source_uses_resolved", 0)
                    + self._counts.get("source_uses_explicit_no_data", 0)
                    + self._counts.get("source_uses_failed_or_unresolved", 0)
                )
                self._phase = data.get("status", "finished")
                if (kind == "source_failed" or self._completed == 1 or
                        self._completed % self.every == 0 or
                        time.monotonic() - self._last_heartbeat >= self.heartbeat_seconds):
                    self._emit_locked("ERROR" if kind == "source_failed" else "PROGRESS",
                                      error=data.get("error"))
            else:
                raise ValueError("UNKNOWN_PROGRESS_EVENT")
