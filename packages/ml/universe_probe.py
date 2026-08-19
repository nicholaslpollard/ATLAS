from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY


ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION = (
    "ml-training-universe-probe-v1-historical-observation-survivorship-identity-audit"
)
ML_HISTORY_ORIGIN_DATE = date(2021, 8, 16)
ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS = 250_000.0
ML_LONG_GAP_CALENDAR_DAYS = 30
ML_EXTREME_RETURN_ABS_1 = 0.50
ML_EXTREME_RETURN_ABS_2 = 1.00


@dataclass(frozen=True, slots=True)
class AnnualUniverseEvidence:
    year: int
    observation_rows: int
    unique_symbols: int
    rows_absent_current_reference: int
    rows_absent_current_reference_fraction: float
    complete_feature_rows: int
    liquid_complete_rows: int
    liquid_complete_rows_absent_current_reference: int
    liquid_complete_rows_absent_current_reference_fraction: float


@dataclass(frozen=True, slots=True)
class MLTrainingUniverseProbeReport:
    contract_version: str
    generated_at_utc: str
    history_start: str
    history_end: str
    wall_seconds: float
    historical_bar_rows: int
    historical_feature_rows: int
    historical_unique_symbols: int
    feature_unique_symbols: int
    current_reference_symbols: int
    current_universe_symbols: int
    historical_symbols_absent_current_reference: int
    historical_symbols_absent_current_universe: int
    historical_rows_absent_current_reference: int
    historical_rows_absent_current_reference_fraction: float
    complete_feature_rows: int
    liquid_complete_rows: int
    liquid_complete_rows_absent_current_reference: int
    liquid_complete_rows_absent_current_reference_fraction: float
    adjustment_state_counts: dict[str, int]
    symbols_with_long_gap: int
    long_gap_count: int
    maximum_calendar_gap_days: int
    consecutive_return_pair_count: int
    abs_return_ge_50pct_count: int
    abs_return_ge_100pct_count: int
    survivorship_gap_observed: bool
    current_snapshot_safe_as_historical_training_universe: bool
    historical_identity_policy_locked: bool
    label_policy_locked: bool
    annual_evidence: tuple[AnnualUniverseEvidence, ...]
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def _count_dict(rows: list[tuple[object, object]]) -> dict[str, int]:
    return {"<NULL>" if key is None else str(key): int(value) for key, value in rows}


class MLTrainingUniverseProbe:
    """Audit historical ML population safety before labels or models are designed.

    The current Phase 07/08 universe is a point-in-time routing population, not a
    historical training universe. This probe measures how much historical daily
    evidence belongs to symbols that are absent from the current reference/universe,
    whether provider adjustment state is usable for forward labels, and how fragmented
    provider-symbol histories are. It deliberately does not create stable historical
    identities or select a label/model policy.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.feature_names = tuple(definition.name for definition in CORE_FEATURE_REGISTRY.all())

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "training_universe_probe" / f"{end_date.year:04d}" / f"{end_date}.json"

    def _required_paths(self, end_date: date) -> dict[str, Path]:
        paths = {
            "reference": self.paths.reference_snapshot_file(end_date),
            "universe": self.paths.universe_snapshot_file(end_date),
        }
        missing = [f"{name}: {path}" for name, path in paths.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Phase 10 ML universe probe point-in-time inputs are missing:\n  "
                + "\n  ".join(missing)
            )
        return paths

    def _prepare_views(self, con: Any, end_date: date, paths: dict[str, Path]) -> None:
        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        start = ML_HISTORY_ORIGIN_DATE.isoformat()
        end = end_date.isoformat()

        con.execute(
            f"""
            CREATE TEMP VIEW ml_bars AS
            SELECT
                symbol,
                CAST(session_date AS DATE) AS session_date,
                close,
                volume,
                is_adjusted
            FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true)
            WHERE CAST(session_date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW ml_features AS
            SELECT *, CAST(timestamp_utc AS DATE) AS feature_date
            FROM read_parquet({sql_string(feature_glob)}, hive_partitioning=true)
            WHERE CAST(timestamp_utc AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW current_reference AS
            SELECT DISTINCT ticker
            FROM read_parquet({sql_string(paths['reference'])})
            WHERE ticker IS NOT NULL
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW current_universe AS
            SELECT DISTINCT ticker
            FROM read_parquet({sql_string(paths['universe'])})
            WHERE ticker IS NOT NULL
            """
        )

        complete_expression = " AND ".join(f"f.{name} IS NOT NULL" for name in self.feature_names)
        con.execute(
            f"""
            CREATE TEMP VIEW ml_observations AS
            SELECT
                b.symbol,
                b.session_date,
                b.close,
                b.volume,
                b.is_adjusted,
                (b.close * b.volume) AS source_dollar_volume,
                r.ticker IS NOT NULL AS in_current_reference,
                u.ticker IS NOT NULL AS in_current_universe,
                ({complete_expression}) AS complete_features
            FROM ml_bars b
            LEFT JOIN ml_features f
              ON f.symbol = b.symbol
             AND f.feature_date = b.session_date
            LEFT JOIN current_reference r
              ON r.ticker = b.symbol
            LEFT JOIN current_universe u
              ON u.ticker = b.symbol
            """
        )

    def run(self, end_date: date) -> MLTrainingUniverseProbeReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")
        paths = self._required_paths(end_date)
        con = connect_utc(":memory:")
        try:
            self._prepare_views(con, end_date, paths)

            bars = con.execute(
                "SELECT count(*), count(DISTINCT symbol) FROM ml_bars"
            ).fetchone()
            features = con.execute(
                "SELECT count(*), count(DISTINCT symbol) FROM ml_features"
            ).fetchone()
            current_reference_symbols = int(
                con.execute("SELECT count(*) FROM current_reference").fetchone()[0]
            )
            current_universe_symbols = int(
                con.execute("SELECT count(*) FROM current_universe").fetchone()[0]
            )

            summary = con.execute(
                f"""
                SELECT
                    count(DISTINCT symbol) FILTER (WHERE NOT in_current_reference),
                    count(DISTINCT symbol) FILTER (WHERE NOT in_current_universe),
                    count(*) FILTER (WHERE NOT in_current_reference),
                    count(*) FILTER (WHERE complete_features),
                    count(*) FILTER (
                        WHERE complete_features
                          AND source_dollar_volume >= {ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS}
                    ),
                    count(*) FILTER (
                        WHERE complete_features
                          AND source_dollar_volume >= {ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS}
                          AND NOT in_current_reference
                    )
                FROM ml_observations
                """
            ).fetchone()

            adjustment_rows = con.execute(
                "SELECT is_adjusted, count(*) FROM ml_bars GROUP BY 1 ORDER BY 1"
            ).fetchall()

            gap_row = con.execute(
                f"""
                WITH ordered AS (
                    SELECT
                        symbol,
                        session_date,
                        lag(session_date) OVER (
                            PARTITION BY symbol ORDER BY session_date
                        ) AS previous_date
                    FROM ml_bars
                ), gaps AS (
                    SELECT
                        symbol,
                        date_diff('day', previous_date, session_date) AS gap_days
                    FROM ordered
                    WHERE previous_date IS NOT NULL
                )
                SELECT
                    count(DISTINCT symbol) FILTER (
                        WHERE gap_days >= {ML_LONG_GAP_CALENDAR_DAYS}
                    ),
                    count(*) FILTER (
                        WHERE gap_days >= {ML_LONG_GAP_CALENDAR_DAYS}
                    ),
                    coalesce(max(gap_days), 0)
                FROM gaps
                """
            ).fetchone()

            return_row = con.execute(
                f"""
                WITH ordered AS (
                    SELECT
                        symbol,
                        session_date,
                        close,
                        lag(close) OVER (
                            PARTITION BY symbol ORDER BY session_date
                        ) AS previous_close,
                        lag(session_date) OVER (
                            PARTITION BY symbol ORDER BY session_date
                        ) AS previous_date
                    FROM ml_bars
                    WHERE close > 0
                ), pairs AS (
                    SELECT
                        symbol,
                        session_date,
                        previous_date,
                        (close / previous_close) - 1.0 AS return_1
                    FROM ordered
                    WHERE previous_close > 0
                )
                SELECT
                    count(*),
                    count(*) FILTER (WHERE abs(return_1) >= {ML_EXTREME_RETURN_ABS_1}),
                    count(*) FILTER (WHERE abs(return_1) >= {ML_EXTREME_RETURN_ABS_2})
                FROM pairs
                """
            ).fetchone()

            annual_rows = con.execute(
                f"""
                SELECT
                    year(session_date) AS year,
                    count(*) AS observation_rows,
                    count(DISTINCT symbol) AS unique_symbols,
                    count(*) FILTER (WHERE NOT in_current_reference) AS absent_rows,
                    count(*) FILTER (WHERE complete_features) AS complete_rows,
                    count(*) FILTER (
                        WHERE complete_features
                          AND source_dollar_volume >= {ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS}
                    ) AS liquid_complete_rows,
                    count(*) FILTER (
                        WHERE complete_features
                          AND source_dollar_volume >= {ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS}
                          AND NOT in_current_reference
                    ) AS liquid_complete_absent_rows
                FROM ml_observations
                GROUP BY 1
                ORDER BY 1
                """
            ).fetchall()
        finally:
            con.close()

        historical_bar_rows = int(bars[0])
        historical_feature_rows = int(features[0])
        historical_rows_absent_current_reference = int(summary[2])
        liquid_complete_rows = int(summary[4])
        liquid_complete_absent = int(summary[5])
        annual = tuple(
            AnnualUniverseEvidence(
                year=int(row[0]),
                observation_rows=int(row[1]),
                unique_symbols=int(row[2]),
                rows_absent_current_reference=int(row[3]),
                rows_absent_current_reference_fraction=_fraction(int(row[3]), int(row[1])),
                complete_feature_rows=int(row[4]),
                liquid_complete_rows=int(row[5]),
                liquid_complete_rows_absent_current_reference=int(row[6]),
                liquid_complete_rows_absent_current_reference_fraction=_fraction(
                    int(row[6]), int(row[5])
                ),
            )
            for row in annual_rows
        )
        survivorship_gap_observed = historical_rows_absent_current_reference > 0
        target = self.report_path(end_date)
        report = MLTrainingUniverseProbeReport(
            contract_version=ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            historical_bar_rows=historical_bar_rows,
            historical_feature_rows=historical_feature_rows,
            historical_unique_symbols=int(bars[1]),
            feature_unique_symbols=int(features[1]),
            current_reference_symbols=current_reference_symbols,
            current_universe_symbols=current_universe_symbols,
            historical_symbols_absent_current_reference=int(summary[0]),
            historical_symbols_absent_current_universe=int(summary[1]),
            historical_rows_absent_current_reference=historical_rows_absent_current_reference,
            historical_rows_absent_current_reference_fraction=_fraction(
                historical_rows_absent_current_reference, historical_bar_rows
            ),
            complete_feature_rows=int(summary[3]),
            liquid_complete_rows=liquid_complete_rows,
            liquid_complete_rows_absent_current_reference=liquid_complete_absent,
            liquid_complete_rows_absent_current_reference_fraction=_fraction(
                liquid_complete_absent, liquid_complete_rows
            ),
            adjustment_state_counts=_count_dict(adjustment_rows),
            symbols_with_long_gap=int(gap_row[0]),
            long_gap_count=int(gap_row[1]),
            maximum_calendar_gap_days=int(gap_row[2]),
            consecutive_return_pair_count=int(return_row[0]),
            abs_return_ge_50pct_count=int(return_row[1]),
            abs_return_ge_100pct_count=int(return_row[2]),
            survivorship_gap_observed=survivorship_gap_observed,
            current_snapshot_safe_as_historical_training_universe=not survivorship_gap_observed,
            historical_identity_policy_locked=False,
            label_policy_locked=False,
            annual_evidence=annual,
            report_path=str(target),
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
