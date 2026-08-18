from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths


TICKER_HISTORY_PROBE_CONTRACT_VERSION = (
    "ticker-history-probe-v1-current-alias-depth-reuse-continuity"
)
TICKER_HISTORY_DEPTH_GRID = (2, 5, 20, 60, 126, 252)

SINGLE_ALIAS_UNREUSED = "SINGLE_ALIAS_UNREUSED"
AUTHORITATIVE_CURRENT_INTERVAL = "AUTHORITATIVE_CURRENT_INTERVAL"
UNRESOLVED_MULTI_ALIAS = "UNRESOLVED_MULTI_ALIAS"
UNRESOLVED_TICKER_REUSE = "UNRESOLVED_TICKER_REUSE"


@dataclass(frozen=True, slots=True)
class TickerHistoryProbeReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    probe_status: str
    population_note: str
    safety_note: str
    route_population_count: int
    discovery_count: int
    position_count: int
    watchlist_count: int
    custom_count: int
    identity_single_alias_count: int
    identity_multi_alias_count: int
    current_alias_observation_count: int
    current_ticker_reuse_count: int
    authoritative_current_interval_count: int
    ambiguous_authoritative_current_interval_count: int
    safety_status_counts: dict[str, int]
    raw_current_alias_depth_counts: dict[str, int]
    identity_safe_depth_counts: dict[str, int]
    safe_depth_by_status: dict[str, dict[str, int]]
    unresolved_multi_alias_examples: tuple[dict[str, object], ...]
    unresolved_ticker_reuse_examples: tuple[dict[str, object], ...]
    report_path: str


def history_safety_status(
    *,
    alias_count: int,
    reuse_identity_count: int,
    authoritative_current_interval_count: int,
) -> str:
    """Classify how much historical ticker continuity ATLAS may safely claim."""

    if reuse_identity_count > 1:
        return UNRESOLVED_TICKER_REUSE
    if alias_count <= 1:
        return SINGLE_ALIAS_UNREUSED
    if authoritative_current_interval_count == 1:
        return AUTHORITATIVE_CURRENT_INTERVAL
    return UNRESOLVED_MULTI_ALIAS


def identity_safe_depth(
    *,
    status: str,
    observation_bounded_depth: int,
    authoritative_interval_depth: int,
) -> int:
    if status == SINGLE_ALIAS_UNREUSED:
        return max(0, int(observation_bounded_depth))
    if status == AUTHORITATIVE_CURRENT_INTERVAL:
        return max(0, int(authoritative_interval_depth))
    return 0


def depth_grid_counts(depths: pd.Series | list[int] | tuple[int, ...]) -> dict[str, int]:
    numeric = pd.to_numeric(pd.Series(depths), errors="coerce").fillna(0)
    return {
        f">={threshold}": int((numeric >= threshold).sum())
        for threshold in TICKER_HISTORY_DEPTH_GRID
    }


def _safe_depth_summary(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for status, subset in frame.groupby("safety_status", sort=True, observed=True):
        result[str(status)] = {
            "instrument_count": int(len(subset)),
            **depth_grid_counts(subset["safe_depth"]),
        }
    return result


class TickerHistoryProbe:
    """Measure identity-safe current-alias history before ticker persistence is locked.

    Raw current-symbol depth is diagnostic only because ticker text can be renamed or
    reused. Safe depth is deliberately conservative:

    * a single observed, unreused alias is counted only from its first reference
      observation onward;
    * a multi-alias identity is counted only inside one exact provider-authoritative
      current validity interval;
    * reused tickers and unresolved multi-alias identities receive no claimed safe
      historical depth until stronger continuity evidence exists.

    No old/new ticker series are spliced in this probe.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    def report_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "ticker_history_probe" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def _required_paths(self, as_of_date: date) -> dict[str, Path]:
        result = {
            "universe": self.paths.universe_snapshot_file(as_of_date),
            "discovery_state": self.paths.discovery_state_file(as_of_date),
            "ticker_observations": self.paths.ticker_observations_file(),
        }
        missing = [f"{name}: {path}" for name, path in result.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Ticker history safety probe inputs are missing:\n  " + "\n  ".join(missing)
            )
        return result

    def _prepare_population(self, con: Any, paths: dict[str, Path]) -> dict[str, int]:
        universe = self._safe(paths["universe"])
        discovery = self._safe(paths["discovery_state"])
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_ticker_history_population AS
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
            FROM atlas_ticker_history_population
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
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_history_alias_counts AS
            SELECT instrument_id, count(DISTINCT ticker) AS alias_count
            FROM read_parquet('{observations}')
            GROUP BY instrument_id
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_history_current_alias AS
            SELECT
                instrument_id,
                ticker,
                min(first_observed_date) AS first_observed_date,
                max(last_observed_date) AS last_observed_date,
                sum(observation_count) AS observation_count
            FROM read_parquet('{observations}')
            GROUP BY instrument_id, ticker
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_history_reuse AS
            SELECT ticker, count(DISTINCT instrument_id) AS reuse_identity_count
            FROM read_parquet('{observations}')
            GROUP BY ticker
            """
        )

        intervals = self.paths.authoritative_ticker_intervals_file()
        if intervals.is_file():
            source = self._safe(intervals)
            as_of = as_of_date.isoformat()
            con.execute(
                f"""
                CREATE TEMP VIEW atlas_history_authoritative_current AS
                SELECT
                    p.instrument_id,
                    p.ticker,
                    count(i.instrument_id) FILTER (
                        WHERE i.valid_from_date <= DATE '{as_of}'
                          AND (i.valid_to_date_exclusive IS NULL OR DATE '{as_of}' < i.valid_to_date_exclusive)
                          AND coalesce(i.continuity_authority, TRUE)
                    ) AS current_interval_count,
                    max(i.valid_from_date) FILTER (
                        WHERE i.valid_from_date <= DATE '{as_of}'
                          AND (i.valid_to_date_exclusive IS NULL OR DATE '{as_of}' < i.valid_to_date_exclusive)
                          AND coalesce(i.continuity_authority, TRUE)
                    ) AS current_interval_from
                FROM atlas_ticker_history_population p
                LEFT JOIN read_parquet('{source}') i
                  ON i.instrument_id = p.instrument_id
                 AND i.ticker = p.ticker
                GROUP BY p.instrument_id, p.ticker
                """
            )
        else:
            con.execute(
                """
                CREATE TEMP VIEW atlas_history_authoritative_current AS
                SELECT
                    instrument_id,
                    ticker,
                    0::BIGINT AS current_interval_count,
                    CAST(NULL AS DATE) AS current_interval_from
                FROM atlas_ticker_history_population
                """
            )

    def _history_depth_frame(self, con: Any, as_of_date: date) -> pd.DataFrame:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        as_of = as_of_date.isoformat()
        return con.execute(
            f"""
            WITH feature_history AS (
                SELECT
                    f.symbol,
                    CAST(f.timestamp_utc AS DATE) AS trading_date
                FROM read_parquet('{feature_glob}', union_by_name=true, hive_partitioning=false) f
                INNER JOIN (
                    SELECT DISTINCT ticker FROM atlas_ticker_history_population
                ) p ON p.ticker = f.symbol
                WHERE CAST(f.timestamp_utc AS DATE) <= DATE '{as_of}'
                  AND f.ema_20 IS NOT NULL AND isfinite(f.ema_20)
                  AND f.ema_50 IS NOT NULL AND isfinite(f.ema_50)
                  AND f.ema_200 IS NOT NULL AND isfinite(f.ema_200)
                  AND f.rsi_14 IS NOT NULL AND isfinite(f.rsi_14)
                  AND f.macd_hist_12_26_9 IS NOT NULL AND isfinite(f.macd_hist_12_26_9)
                  AND f.natr_14 IS NOT NULL AND isfinite(f.natr_14)
                  AND f.realized_volatility_20 IS NOT NULL AND isfinite(f.realized_volatility_20)
                  AND f.directional_efficiency_20 IS NOT NULL AND isfinite(f.directional_efficiency_20)
            )
            SELECT
                p.instrument_id,
                p.ticker,
                coalesce(a.alias_count, 0) AS alias_count,
                coalesce(r.reuse_identity_count, 0) AS reuse_identity_count,
                c.first_observed_date,
                c.last_observed_date,
                coalesce(ai.current_interval_count, 0) AS authoritative_current_interval_count,
                ai.current_interval_from,
                count(f.trading_date) AS raw_current_alias_depth,
                count(f.trading_date) FILTER (
                    WHERE c.first_observed_date IS NOT NULL
                      AND f.trading_date >= c.first_observed_date
                ) AS observation_bounded_depth,
                count(f.trading_date) FILTER (
                    WHERE ai.current_interval_count = 1
                      AND ai.current_interval_from IS NOT NULL
                      AND f.trading_date >= ai.current_interval_from
                ) AS authoritative_interval_depth
            FROM atlas_ticker_history_population p
            LEFT JOIN atlas_history_alias_counts a USING (instrument_id)
            LEFT JOIN atlas_history_current_alias c
              ON c.instrument_id = p.instrument_id AND c.ticker = p.ticker
            LEFT JOIN atlas_history_reuse r ON r.ticker = p.ticker
            LEFT JOIN atlas_history_authoritative_current ai
              ON ai.instrument_id = p.instrument_id AND ai.ticker = p.ticker
            LEFT JOIN feature_history f ON f.symbol = p.ticker
            GROUP BY
                p.instrument_id,
                p.ticker,
                a.alias_count,
                r.reuse_identity_count,
                c.first_observed_date,
                c.last_observed_date,
                ai.current_interval_count,
                ai.current_interval_from
            ORDER BY p.instrument_id
            """
        ).fetch_df()

    @staticmethod
    def _example_rows(frame: pd.DataFrame, status: str, limit: int = 20) -> tuple[dict[str, object], ...]:
        subset = frame.loc[frame["safety_status"] == status].head(limit)
        result: list[dict[str, object]] = []
        for _, row in subset.iterrows():
            result.append(
                {
                    "instrument_id": str(row["instrument_id"]),
                    "ticker": str(row["ticker"]),
                    "alias_count": int(row["alias_count"]),
                    "reuse_identity_count": int(row["reuse_identity_count"]),
                    "raw_current_alias_depth": int(row["raw_current_alias_depth"]),
                }
            )
        return tuple(result)

    def run(self, as_of_date: date) -> TickerHistoryProbeReport:
        started = perf_counter()
        paths = self._required_paths(as_of_date)
        target = self.report_path(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        con = connect_utc(":memory:")
        try:
            routes = self._prepare_population(con, paths)
            self._prepare_identity(con, paths, as_of_date)
            frame = self._history_depth_frame(con, as_of_date)
        finally:
            con.close()

        if len(frame) != routes["population"]:
            raise ValueError("ticker history audit frame does not match routed population")

        statuses: list[str] = []
        safe_depths: list[int] = []
        for _, row in frame.iterrows():
            status = history_safety_status(
                alias_count=int(row["alias_count"]),
                reuse_identity_count=int(row["reuse_identity_count"]),
                authoritative_current_interval_count=int(row["authoritative_current_interval_count"]),
            )
            statuses.append(status)
            safe_depths.append(
                identity_safe_depth(
                    status=status,
                    observation_bounded_depth=int(row["observation_bounded_depth"]),
                    authoritative_interval_depth=int(row["authoritative_interval_depth"]),
                )
            )
        frame["safety_status"] = statuses
        frame["safe_depth"] = safe_depths

        status_counts = dict(sorted(Counter(statuses).items()))
        alias_numeric = pd.to_numeric(frame["alias_count"], errors="coerce").fillna(0)
        report = TickerHistoryProbeReport(
            contract_version=TICKER_HISTORY_PROBE_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=datetime.now(UTC).isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            population_note=(
                "Phase 8 discovery-state instruments plus Phase 7 POSITION/WATCHLIST/CUSTOM routed overrides."
            ),
            safety_note=(
                "Raw ticker-text history is diagnostic only. Identity-safe depth is bounded by first exact reference "
                "observation for single unreused aliases or by one exact authoritative current validity interval; "
                "unresolved alias/reuse cases are not spliced."
            ),
            route_population_count=routes["population"],
            discovery_count=routes["discovery"],
            position_count=routes["position"],
            watchlist_count=routes["watchlist"],
            custom_count=routes["custom"],
            identity_single_alias_count=int((alias_numeric <= 1).sum()),
            identity_multi_alias_count=int((alias_numeric > 1).sum()),
            current_alias_observation_count=int(frame["first_observed_date"].notna().sum()),
            current_ticker_reuse_count=int((pd.to_numeric(frame["reuse_identity_count"], errors="coerce").fillna(0) > 1).sum()),
            authoritative_current_interval_count=int((pd.to_numeric(frame["authoritative_current_interval_count"], errors="coerce").fillna(0) == 1).sum()),
            ambiguous_authoritative_current_interval_count=int((pd.to_numeric(frame["authoritative_current_interval_count"], errors="coerce").fillna(0) > 1).sum()),
            safety_status_counts=status_counts,
            raw_current_alias_depth_counts=depth_grid_counts(frame["raw_current_alias_depth"]),
            identity_safe_depth_counts=depth_grid_counts(frame["safe_depth"]),
            safe_depth_by_status=_safe_depth_summary(frame),
            unresolved_multi_alias_examples=self._example_rows(frame, UNRESOLVED_MULTI_ALIAS),
            unresolved_ticker_reuse_examples=self._example_rows(frame, UNRESOLVED_TICKER_REUSE),
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
