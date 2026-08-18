from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.instruments.ticker_events import TickerEventStore

from .ticker_authority_probe import (
    NEEDS_COMPOSITE_FIGI_EVENT,
    TickerAuthorityProbe,
    authority_status,
)


TICKER_AUTHORITY_BATCH_CONTRACT_VERSION = (
    "ticker-authority-batch-v1-composite-figi-sequential-resumable"
)
TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT = 25
TICKER_AUTHORITY_BATCH_MAX_ERRORS = 3


@dataclass(frozen=True, slots=True)
class TickerAuthorityCandidate:
    instrument_id: str
    ticker: str
    composite_figi: str
    alias_count: int
    reuse_identity_count: int


@dataclass(frozen=True, slots=True)
class TickerAuthorityBatchReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    requested_limit: int
    candidate_count_before: int
    attempted_count: int
    synced_count: int
    skipped_count: int
    provider_error_count: int
    authoritative_result_count: int
    event_count_total: int
    with_events_count: int
    zero_events_count: int
    resolved_interval_count_before: int
    resolved_interval_count_after: int
    resolution_gain: int
    unresolved_with_composite_figi_after: int
    provider_sync_candidates_after: int
    stopped_on_error_budget: bool
    outcomes: tuple[dict[str, object], ...]
    report_path: str


def select_provider_candidates(
    rows: list[dict[str, object]],
    *,
    cached_instrument_ids: set[str],
    limit: int,
) -> list[TickerAuthorityCandidate]:
    """Select deterministic uncached Composite-FIGI authority candidates."""

    if limit <= 0:
        raise ValueError("limit must be positive")

    candidates: list[TickerAuthorityCandidate] = []
    for row in rows:
        instrument_id = str(row.get("instrument_id") or "").strip()
        ticker = str(row.get("ticker") or "").strip()
        composite_figi = str(row.get("composite_figi") or "").strip().upper()
        if not instrument_id or not ticker or instrument_id in cached_instrument_ids:
            continue
        status = authority_status(
            alias_count=int(row.get("alias_count") or 0),
            reuse_identity_count=int(row.get("reuse_identity_count") or 0),
            authoritative_current_interval_count=int(
                row.get("authoritative_current_interval_count") or 0
            ),
            has_composite_figi=bool(composite_figi),
        )
        if status != NEEDS_COMPOSITE_FIGI_EVENT:
            continue
        candidates.append(
            TickerAuthorityCandidate(
                instrument_id=instrument_id,
                ticker=ticker,
                composite_figi=composite_figi,
                alias_count=int(row.get("alias_count") or 0),
                reuse_identity_count=int(row.get("reuse_identity_count") or 0),
            )
        )

    candidates.sort(key=lambda item: (item.instrument_id, item.ticker))
    return candidates[:limit]


class TickerAuthorityBatch:
    """Enrich a bounded set of unresolved identities with authoritative events.

    The endpoint is queried sequentially. Existing event files are treated as durable
    checkpoints and skipped by candidate selection, so reruns resume rather than
    refetch. Provider errors are recorded, and the batch stops once the small error
    budget is exhausted.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.probe = TickerAuthorityProbe(settings)
        self.paths = self.probe.paths
        self.store = TickerEventStore(settings)

    def _inventory_rows(self, as_of_date: date) -> list[dict[str, object]]:
        paths = self.probe._required_paths(as_of_date)
        con = connect_utc(":memory:")
        try:
            self.probe._prepare_population(con, paths)
            self.probe._prepare_identity(con, paths, as_of_date)
            return self.probe._frame(con)
        finally:
            con.close()

    def _cached_instrument_ids(self) -> set[str]:
        root = (
            self.settings.resolved_path(self.settings.data.paths.canonical)
            / "corporate_actions"
            / "massive"
            / "ticker_events"
        )
        if not root.exists():
            return set()
        result: set[str] = set()
        for path in root.glob("instrument_id=*/*.parquet"):
            parent = path.parent.name
            if parent.startswith("instrument_id="):
                result.add(parent.split("=", 1)[1])
        return result

    def _report_path(self, generated_at: datetime, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        stamp = generated_at.strftime("%Y-%m-%dT%H%M%SZ")
        return (
            root
            / "regimes"
            / "ticker_authority_sync"
            / f"{as_of_date.year:04d}"
            / f"{as_of_date}"
            / f"{stamp}.json"
        )

    def run(
        self,
        as_of_date: date,
        *,
        limit: int = TICKER_AUTHORITY_BATCH_DEFAULT_LIMIT,
        max_errors: int = TICKER_AUTHORITY_BATCH_MAX_ERRORS,
    ) -> TickerAuthorityBatchReport:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if max_errors <= 0:
            raise ValueError("max_errors must be positive")

        started = perf_counter()
        generated_at = datetime.now(UTC)
        before = self.probe.run(as_of_date)
        rows = self._inventory_rows(as_of_date)
        selected = select_provider_candidates(
            rows,
            cached_instrument_ids=self._cached_instrument_ids(),
            limit=limit,
        )

        outcomes: list[dict[str, object]] = []
        provider_errors = 0
        synced = 0
        skipped = 0
        authoritative_results = 0
        total_events = 0
        with_events = 0
        zero_events = 0
        stopped = False

        for candidate in selected:
            try:
                result = self.store.sync_for_ticker(candidate.ticker, as_of_date)
            except ProviderError as exc:
                provider_errors += 1
                outcomes.append(
                    {
                        "instrument_id": candidate.instrument_id,
                        "ticker": candidate.ticker,
                        "composite_figi": candidate.composite_figi,
                        "status": "PROVIDER_ERROR",
                        "error": str(exc),
                    }
                )
                if provider_errors >= max_errors:
                    stopped = True
                    break
                continue

            if result.skipped:
                skipped += 1
                status = "SKIPPED"
            else:
                synced += 1
                status = "SYNCED"
            if result.continuity_authority:
                authoritative_results += 1
            event_count = int(result.event_count)
            total_events += event_count
            if event_count > 0:
                with_events += 1
            else:
                zero_events += 1
            outcomes.append(
                {
                    "instrument_id": candidate.instrument_id,
                    "ticker": candidate.ticker,
                    "composite_figi": candidate.composite_figi,
                    "status": status,
                    "continuity_authority": bool(result.continuity_authority),
                    "event_count": event_count,
                }
            )

        # Each single-ticker sync currently maintains derived views. Rebuild once more
        # at batch end as an explicit completion barrier before the post-inventory.
        self.store.rebuild_derived_views()
        after = self.probe.run(as_of_date)
        target = self._report_path(generated_at, as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        report = TickerAuthorityBatchReport(
            contract_version=TICKER_AUTHORITY_BATCH_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=generated_at.isoformat(),
            wall_seconds=perf_counter() - started,
            requested_limit=limit,
            candidate_count_before=before.provider_sync_candidate_count,
            attempted_count=len(outcomes),
            synced_count=synced,
            skipped_count=skipped,
            provider_error_count=provider_errors,
            authoritative_result_count=authoritative_results,
            event_count_total=total_events,
            with_events_count=with_events,
            zero_events_count=zero_events,
            resolved_interval_count_before=before.resolved_authoritative_interval_count,
            resolved_interval_count_after=after.resolved_authoritative_interval_count,
            resolution_gain=(
                after.resolved_authoritative_interval_count
                - before.resolved_authoritative_interval_count
            ),
            unresolved_with_composite_figi_after=(
                after.unresolved_with_composite_figi_count
            ),
            provider_sync_candidates_after=after.provider_sync_candidate_count,
            stopped_on_error_budget=stopped,
            outcomes=tuple(outcomes),
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
