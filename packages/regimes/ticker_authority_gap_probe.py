from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc

from .ticker_authority_probe import NEEDS_COMPOSITE_FIGI_EVENT, TickerAuthorityProbe, authority_status


TICKER_AUTHORITY_GAP_PROBE_CONTRACT_VERSION = (
    "ticker-authority-gap-probe-v1-cached-unresolved-event-timeline-audit"
)

CURRENT_TICKER_ABSENT = "CURRENT_TICKER_ABSENT"
CURRENT_EVENT_AFTER_AS_OF = "CURRENT_EVENT_AFTER_AS_OF"
CURRENT_TICKER_NOT_ACTIVE_AT_AS_OF = "CURRENT_TICKER_NOT_ACTIVE_AT_AS_OF"
CONFLICTED_EVENT_DATE = "CONFLICTED_EVENT_DATE"
NO_AUTHORITATIVE_EVENTS = "NO_AUTHORITATIVE_EVENTS"
UNCLASSIFIED = "UNCLASSIFIED"


@dataclass(frozen=True, slots=True)
class TickerAuthorityGapProbeReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    probe_status: str
    cached_unresolved_count: int
    reason_counts: dict[str, int]
    gaps: tuple[dict[str, object], ...]
    report_path: str


def classify_gap(
    *,
    current_ticker: str,
    as_of_date: date,
    events: list[tuple[date, str]],
) -> str:
    if not events:
        return NO_AUTHORITATIVE_EVENTS

    by_date: dict[date, set[str]] = {}
    for event_date, ticker in events:
        by_date.setdefault(event_date, set()).add(ticker)
    if any(len(tickers) > 1 for tickers in by_date.values()):
        return CONFLICTED_EVENT_DATE

    current_dates = sorted(event_date for event_date, ticker in events if ticker == current_ticker)
    if not current_dates:
        return CURRENT_TICKER_ABSENT
    if current_dates[0] > as_of_date:
        return CURRENT_EVENT_AFTER_AS_OF

    ordered = sorted(events)
    active_ticker: str | None = None
    for event_date, ticker in ordered:
        if event_date <= as_of_date:
            active_ticker = ticker
        else:
            break
    if active_ticker != current_ticker:
        return CURRENT_TICKER_NOT_ACTIVE_AT_AS_OF
    return UNCLASSIFIED


class TickerAuthorityGapProbe:
    """Explain cached authoritative event files that still lack a current interval."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.probe = TickerAuthorityProbe(settings)
        self.paths = self.probe.paths

    def report_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "ticker_authority_gap_probe" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def _inventory_rows(self, as_of_date: date) -> list[dict[str, object]]:
        paths = self.probe._required_paths(as_of_date)
        con = connect_utc(":memory:")
        try:
            self.probe._prepare_population(con, paths)
            self.probe._prepare_identity(con, paths, as_of_date)
            return self.probe._frame(con)
        finally:
            con.close()

    def _events_for_instrument(self, instrument_id: str) -> list[tuple[date, str]]:
        path = self.paths.ticker_events_file(instrument_id)
        if not path.is_file():
            return []
        con = connect_utc(":memory:")
        try:
            rows = con.execute(
                """
                SELECT CAST(event_date AS DATE), ticker
                FROM read_parquet(?)
                WHERE coalesce(continuity_authority, FALSE) = TRUE
                ORDER BY event_date, ticker
                """,
                [str(path)],
            ).fetchall()
        finally:
            con.close()
        return [(row[0], str(row[1])) for row in rows]

    def run(self, as_of_date: date) -> TickerAuthorityGapProbeReport:
        started = perf_counter()
        generated_at = datetime.now(UTC)
        rows = self._inventory_rows(as_of_date)
        gaps: list[dict[str, object]] = []
        reason_counts: dict[str, int] = {}

        for row in rows:
            instrument_id = str(row.get("instrument_id") or "")
            ticker = str(row.get("ticker") or "")
            event_file = self.paths.ticker_events_file(instrument_id)
            if not event_file.is_file():
                continue
            composite_figi = str(row.get("composite_figi") or "").strip().upper()
            status = authority_status(
                alias_count=int(row.get("alias_count") or 0),
                reuse_identity_count=int(row.get("reuse_identity_count") or 0),
                authoritative_current_interval_count=int(row.get("authoritative_current_interval_count") or 0),
                has_composite_figi=bool(composite_figi),
            )
            if status != NEEDS_COMPOSITE_FIGI_EVENT:
                continue

            events = self._events_for_instrument(instrument_id)
            reason = classify_gap(current_ticker=ticker, as_of_date=as_of_date, events=events)
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
            gaps.append(
                {
                    "instrument_id": instrument_id,
                    "ticker": ticker,
                    "composite_figi": composite_figi,
                    "alias_count": int(row.get("alias_count") or 0),
                    "reuse_identity_count": int(row.get("reuse_identity_count") or 0),
                    "reason": reason,
                    "events": tuple(
                        {"event_date": event_date.isoformat(), "ticker": event_ticker}
                        for event_date, event_ticker in events
                    ),
                }
            )

        gaps.sort(key=lambda item: (str(item["ticker"]), str(item["instrument_id"])))
        target = self.report_path(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)
        report = TickerAuthorityGapProbeReport(
            contract_version=TICKER_AUTHORITY_GAP_PROBE_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=generated_at.isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            cached_unresolved_count=len(gaps),
            reason_counts=dict(sorted(reason_counts.items())),
            gaps=tuple(gaps),
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
