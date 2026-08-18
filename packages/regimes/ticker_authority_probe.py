from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths


TICKER_AUTHORITY_PROBE_CONTRACT_VERSION = (
    "ticker-authority-probe-v1-unresolved-composite-figi-cache-audit"
)

NOT_REQUIRED = "NOT_REQUIRED"
RESOLVED_AUTHORITATIVE_INTERVAL = "RESOLVED_AUTHORITATIVE_INTERVAL"
AMBIGUOUS_AUTHORITATIVE_INTERVAL = "AMBIGUOUS_AUTHORITATIVE_INTERVAL"
NEEDS_COMPOSITE_FIGI_EVENT = "NEEDS_COMPOSITE_FIGI_EVENT"
UNRESOLVED_NO_COMPOSITE_FIGI = "UNRESOLVED_NO_COMPOSITE_FIGI"


@dataclass(frozen=True, slots=True)
class TickerAuthorityProbeReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    probe_status: str
    route_population_count: int
    discovery_count: int
    position_count: int
    watchlist_count: int
    custom_count: int
    multi_alias_count: int
    ticker_reuse_count: int
    authority_status_counts: dict[str, int]
    unresolved_identity_count: int
    unresolved_with_composite_figi_count: int
    unresolved_without_composite_figi_count: int
    resolved_authoritative_interval_count: int
    ambiguous_authoritative_interval_count: int
    cached_event_file_count: int
    provider_sync_candidate_count: int
    provider_sync_candidate_examples: tuple[dict[str, object], ...]
    unresolved_no_figi_examples: tuple[dict[str, object], ...]
    report_path: str


def authority_status(
    *,
    alias_count: int,
    reuse_identity_count: int,
    authoritative_current_interval_count: int,
    has_composite_figi: bool,
) -> str:
    """Classify whether provider ticker-event enrichment is still required."""

    if authoritative_current_interval_count > 1:
        return AMBIGUOUS_AUTHORITATIVE_INTERVAL
    if authoritative_current_interval_count == 1:
        return RESOLVED_AUTHORITATIVE_INTERVAL
    if alias_count > 1 or reuse_identity_count > 1:
        return NEEDS_COMPOSITE_FIGI_EVENT if has_composite_figi else UNRESOLVED_NO_COMPOSITE_FIGI
    return NOT_REQUIRED


class TickerAuthorityProbe:
    """Inventory unresolved ticker identity cases before provider-event batch sync.

    This probe performs no network calls. It uses the point-in-time reference snapshot,
    stable instrument/ticker observations, and any already cached authoritative ticker
    intervals to determine which unresolved identities can be queried safely by
    Composite FIGI.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    def _required_paths(self, as_of_date: date) -> dict[str, Path]:
        result = {
            "universe": self.paths.universe_snapshot_file(as_of_date),
            "discovery_state": self.paths.discovery_state_file(as_of_date),
            "ticker_observations": self.paths.ticker_observations_file(),
            "reference_snapshot": self.paths.reference_snapshot_file(as_of_date),
        }
        missing = [f"{name}: {path}" for name, path in result.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Ticker authority inventory inputs are missing:\n  " + "\n  ".join(missing)
            )
        return result

    def _prepare_population(self, con: Any, paths: dict[str, Path]) -> dict[str, int]:
        universe = self._safe(paths["universe"])
        discovery = self._safe(paths["discovery_state"])
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_ticker_authority_population AS
            WITH u AS (
                SELECT instrument_id, ticker, routes
                FROM read_parquet('{universe}')
            ), d AS (
                SELECT instrument_id
                FROM read_parquet('{discovery}')
            )
            SELECT
                u.instrument_id,
                u.ticker,
                u.routes,
                d.instrument_id IS NOT NULL AS in_discovery_state
            FROM u
            LEFT JOIN d USING (instrument_id)
            WHERE d.instrument_id IS NOT NULL
               OR list_contains(u.routes, 'position')
               OR list_contains(u.routes, 'watchlist')
               OR list_contains(u.routes, 'custom')
            """
        )
        row = con.execute(
            """
            SELECT
                count(*),
                count(*) FILTER (WHERE in_discovery_state),
                count(*) FILTER (WHERE list_contains(routes, 'position')),
                count(*) FILTER (WHERE list_contains(routes, 'watchlist')),
                count(*) FILTER (WHERE list_contains(routes, 'custom'))
            FROM atlas_ticker_authority_population
            """
        ).fetchone()
        return {
            "population": int(row[0]),
            "discovery": int(row[1]),
            "position": int(row[2]),
            "watchlist": int(row[3]),
            "custom": int(row[4]),
        }

    def _prepare_identity(self, con: Any, paths: dict[str, Path], as_of_date: date) -> None:
        observations = self._safe(paths["ticker_observations"])
        reference = self._safe(paths["reference_snapshot"])
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_ticker_authority_alias_counts AS
            SELECT instrument_id, count(DISTINCT ticker) AS alias_count
            FROM read_parquet('{observations}')
            GROUP BY instrument_id
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_ticker_authority_reuse AS
            SELECT ticker, count(DISTINCT instrument_id) AS reuse_identity_count
            FROM read_parquet('{observations}')
            GROUP BY ticker
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_ticker_authority_reference AS
            SELECT instrument_id, ticker, composite_figi
            FROM read_parquet('{reference}')
            """
        )

        intervals = self.paths.authoritative_ticker_intervals_file()
        as_of = as_of_date.isoformat()
        if intervals.is_file():
            source = self._safe(intervals)
            con.execute(
                f"""
                CREATE TEMP VIEW atlas_ticker_authority_current_interval AS
                SELECT
                    p.instrument_id,
                    p.ticker,
                    count(i.instrument_id) FILTER (
                        WHERE i.valid_from_date <= DATE '{as_of}'
                          AND (i.valid_to_date_exclusive IS NULL OR DATE '{as_of}' < i.valid_to_date_exclusive)
                          AND coalesce(i.continuity_authority, TRUE)
                    ) AS current_interval_count
                FROM atlas_ticker_authority_population p
                LEFT JOIN read_parquet('{source}') i
                  ON i.instrument_id = p.instrument_id
                 AND i.ticker = p.ticker
                GROUP BY p.instrument_id, p.ticker
                """
            )
        else:
            con.execute(
                """
                CREATE TEMP VIEW atlas_ticker_authority_current_interval AS
                SELECT instrument_id, ticker, 0::BIGINT AS current_interval_count
                FROM atlas_ticker_authority_population
                """
            )

    def _frame(self, con: Any) -> list[dict[str, object]]:
        rows = con.execute(
            """
            SELECT
                p.instrument_id,
                p.ticker,
                coalesce(a.alias_count, 0) AS alias_count,
                coalesce(r.reuse_identity_count, 0) AS reuse_identity_count,
                ref.composite_figi,
                coalesce(i.current_interval_count, 0) AS authoritative_current_interval_count
            FROM atlas_ticker_authority_population p
            LEFT JOIN atlas_ticker_authority_alias_counts a USING (instrument_id)
            LEFT JOIN atlas_ticker_authority_reuse r ON r.ticker = p.ticker
            LEFT JOIN atlas_ticker_authority_reference ref
              ON ref.instrument_id = p.instrument_id AND ref.ticker = p.ticker
            LEFT JOIN atlas_ticker_authority_current_interval i
              ON i.instrument_id = p.instrument_id AND i.ticker = p.ticker
            ORDER BY p.instrument_id
            """
        ).fetchall()
        columns = (
            "instrument_id",
            "ticker",
            "alias_count",
            "reuse_identity_count",
            "composite_figi",
            "authoritative_current_interval_count",
        )
        return [dict(zip(columns, row)) for row in rows]

    @staticmethod
    def _examples(rows: list[dict[str, object]], status: str, limit: int = 20) -> tuple[dict[str, object], ...]:
        selected: list[dict[str, object]] = []
        for row in rows:
            if row["authority_status"] != status:
                continue
            selected.append(
                {
                    "instrument_id": str(row["instrument_id"]),
                    "ticker": str(row["ticker"]),
                    "alias_count": int(row["alias_count"]),
                    "reuse_identity_count": int(row["reuse_identity_count"]),
                    "composite_figi": str(row["composite_figi"] or ""),
                    "event_file_cached": bool(row["event_file_cached"]),
                }
            )
            if len(selected) >= limit:
                break
        return tuple(selected)

    def run(self, as_of_date: date) -> TickerAuthorityProbeReport:
        started = perf_counter()
        paths = self._required_paths(as_of_date)
        target = self.paths.ticker_authority_probe_report(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        con = connect_utc(":memory:")
        try:
            routes = self._prepare_population(con, paths)
            self._prepare_identity(con, paths, as_of_date)
            rows = self._frame(con)
        finally:
            con.close()

        if len(rows) != routes["population"]:
            raise ValueError("ticker authority inventory does not match routed population")

        statuses: list[str] = []
        for row in rows:
            composite_figi = str(row.get("composite_figi") or "").strip()
            status = authority_status(
                alias_count=int(row["alias_count"]),
                reuse_identity_count=int(row["reuse_identity_count"]),
                authoritative_current_interval_count=int(row["authoritative_current_interval_count"]),
                has_composite_figi=bool(composite_figi),
            )
            row["authority_status"] = status
            row["event_file_cached"] = self.paths.ticker_events_file(str(row["instrument_id"])).is_file()
            statuses.append(status)

        status_counts = dict(sorted(Counter(statuses).items()))
        unresolved_statuses = {
            AMBIGUOUS_AUTHORITATIVE_INTERVAL,
            NEEDS_COMPOSITE_FIGI_EVENT,
            UNRESOLVED_NO_COMPOSITE_FIGI,
        }
        unresolved = [row for row in rows if row["authority_status"] in unresolved_statuses]
        multi_alias_count = sum(int(row["alias_count"]) > 1 for row in rows)
        ticker_reuse_count = sum(int(row["reuse_identity_count"]) > 1 for row in rows)
        cached_event_count = sum(bool(row["event_file_cached"]) for row in rows)

        report = TickerAuthorityProbeReport(
            contract_version=TICKER_AUTHORITY_PROBE_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=datetime.now(UTC).isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            route_population_count=routes["population"],
            discovery_count=routes["discovery"],
            position_count=routes["position"],
            watchlist_count=routes["watchlist"],
            custom_count=routes["custom"],
            multi_alias_count=multi_alias_count,
            ticker_reuse_count=ticker_reuse_count,
            authority_status_counts=status_counts,
            unresolved_identity_count=len(unresolved),
            unresolved_with_composite_figi_count=sum(
                row["authority_status"] == NEEDS_COMPOSITE_FIGI_EVENT for row in rows
            ),
            unresolved_without_composite_figi_count=sum(
                row["authority_status"] == UNRESOLVED_NO_COMPOSITE_FIGI for row in rows
            ),
            resolved_authoritative_interval_count=sum(
                row["authority_status"] == RESOLVED_AUTHORITATIVE_INTERVAL for row in rows
            ),
            ambiguous_authoritative_interval_count=sum(
                row["authority_status"] == AMBIGUOUS_AUTHORITATIVE_INTERVAL for row in rows
            ),
            cached_event_file_count=cached_event_count,
            provider_sync_candidate_count=sum(
                row["authority_status"] == NEEDS_COMPOSITE_FIGI_EVENT
                and not bool(row["event_file_cached"])
                for row in rows
            ),
            provider_sync_candidate_examples=self._examples(rows, NEEDS_COMPOSITE_FIGI_EVENT),
            unresolved_no_figi_examples=self._examples(rows, UNRESOLVED_NO_COMPOSITE_FIGI),
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
