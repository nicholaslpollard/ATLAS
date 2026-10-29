from __future__ import annotations

"""V42 timestamped milestone progress for long historical source acquisition.

Progress is displayed once at startup, at each 10 percent of a known workload,
and immediately when an error is observed. No heartbeat thread, background
provider work, or separate progress log is created.
"""

from datetime import datetime
import math
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PROGRESS_CONTRACT = "atlas-source-runtime-progress-v42"
MILESTONE_PERCENT = 10


def _duration(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class SourceProgressMonitor:
    """Report completed/total and observed throughput at 10% milestones.

    The caller knows its own exact demand denominator. There is no limitation
    on demand count, provider requests, or source reuse from this observer.
    """

    def __init__(self, *, expected_source_uses: int) -> None:
        if (type(expected_source_uses) is not int
                or expected_source_uses <= 0):
            raise ValueError("EXPECTED_SOURCE_USES_MUST_BE_POSITIVE")
        self.expected = expected_source_uses
        self._start = time.monotonic()
        self._counts: dict = {}
        self._completed = 0
        self._next_milestone = 1
        self._last_active = "initialization"
        self._last_status = "initializing"
        self._closed = False

    def __enter__(self):
        self._start = time.monotonic()
        self._emit("START")
        return self

    def __exit__(self, exc_type, exc, tb):
        self._closed = True
        if exc_type is not None:
            self._emit("STOPPED_WITH_ERROR", error=str(exc)[:160])
        elif self._completed != self.expected:
            self._emit("STOPPED_INCOMPLETE")
        # At 100% the final 10% milestone prints the last progress line.
        # The V40 CLI prints the overall final status and report path.

    def _emit(self, event: str, *, error: str | None = None) -> None:
        elapsed = max(0.0, time.monotonic() - self._start)
        throughput = self._completed / elapsed if elapsed > 0 else 0.0
        if self._completed >= 10 and elapsed > 0:
            rough_eta = _duration(
                max(0, self.expected - self._completed) / throughput
            )
        else:
            rough_eta = "learning"
        counts = self._counts
        line = (
            f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}]"
            f" {event} completed={self._completed}/{self.expected}"
            f" ({100 * self._completed / self.expected:.1f}%)"
            f" fetched={counts.get('provider_fetch_successes', 0)}"
            f" cached={counts.get('persisted_cache_hits', 0)}"
            f" provider_attempts={counts.get('provider_dispatch_attempts', 0)}"
            f" no_data={counts.get('source_uses_explicit_no_data', 0)}"
            f" errors={counts.get('source_uses_failed_or_unresolved', 0)}"
            f" elapsed={_duration(elapsed)}"
            f" throughput={throughput:.2f}_requirements/s"
            f" eta_rough={rough_eta}"
            f" last_source={self._last_active}"
            f" status={self._last_status}"
        )
        if error:
            line += f" error={error.replace(chr(10), ' ')[:160]}"
        print(line, flush=True)

    def event(self, kind: str, data: dict) -> None:
        if self._closed:
            raise ValueError("PROGRESS_MONITOR_ALREADY_CLOSED")
        counts = data["counts"]
        self._counts = dict(counts)
        self._last_active = f"{data['date_et']}:{data['purpose']}"
        if kind in ("source_started", "provider_dispatch"):
            return
        if kind not in ("source_done", "source_failed"):
            raise ValueError("UNKNOWN_PROGRESS_EVENT")
        self._last_status = data.get("status") or kind
        self._completed = (
            counts.get("source_uses_resolved", 0)
            + counts.get("source_uses_explicit_no_data", 0)
            + counts.get("source_uses_failed_or_unresolved", 0)
        )
        if kind == "source_failed":
            self._emit("ERROR", error=data.get("error"))
        if self._next_milestone <= 10 and (
            self._completed >= math.ceil(
                self.expected * self._next_milestone / 10
            )
        ):
            reached = self._next_milestone
            while (self._next_milestone <= 10
                   and self._completed >= math.ceil(
                       self.expected * self._next_milestone / 10
                   )):
                self._next_milestone += 1
            self._emit(f"PROGRESS_{reached * MILESTONE_PERCENT}PCT")
