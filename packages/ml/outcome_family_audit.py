from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.ml.outcome_probe import (
    ML_OUTCOME_HORIZONS,
    MLOutcomeFeasibilityProbe,
    _normalized_split,
)
from packages.ml.universe_probe import ML_HISTORY_ORIGIN_DATE


ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION = (
    "ml-outcome-family-audit-v2-natr14-schema-reconciled-split-censored-grid"
)
ML_VOLATILITY_FEATURE = "natr_14"
ML_VOLATILITY_THRESHOLD_GRID = (0.5, 1.0, 1.5, 2.0)
ML_VOLATILITY_HORIZON_SCALING = "sqrt_sessions"
ML_FEATURE_PARQUET_READ_MODE = "union_by_name"
ML_NATR_ABS_TOLERANCE = 1e-10
ML_NATR_REL_TOLERANCE = 1e-8


@dataclass(frozen=True, slots=True)
class VolatilityFeatureIntegrityEvidence:
    base_candidate_rows: int
    base_candidate_symbols: int
    feature_join_rows: int
    feature_join_symbols: int
    stored_natr_finite_rows: int
    stored_natr_positive_rows: int
    stored_natr_zero_rows: int
    stored_natr_negative_rows: int
    derived_natr_positive_rows: int
    comparable_rows: int
    mismatched_rows: int
    mismatch_fraction: float
    median_stored_natr: float | None
    median_derived_natr: float | None
    max_abs_difference: float | None
    parquet_read_mode: str
    full_population_reconciled: bool
    stored_vs_derived_reconciled: bool


@dataclass(frozen=True, slots=True)
class VolatilityThresholdEvidence:
    multiplier: float
    up_rows: int
    down_rows: int
    neutral_rows: int
    directional_rows: int
    up_fraction: float
    down_fraction: float
    neutral_fraction: float
    directional_fraction: float
    up_fraction_of_directional: float


@dataclass(frozen=True, slots=True)
class VolatilityHorizonEvidence:
    horizon_sessions: int
    candidate_rows: int
    labelable_rows: int
    split_censored_rows: int
    usable_rows: int
    usable_fraction: float
    adjacent_label_overlap_sessions: int
    median_start_natr: float | None
    median_scaled_move: float | None
    thresholds: tuple[VolatilityThresholdEvidence, ...]


@dataclass(frozen=True, slots=True)
class MLOutcomeFamilyAuditReport:
    contract_version: str
    generated_at_utc: str
    history_start: str
    history_end: str
    wall_seconds: float
    candidate_rows: int
    candidate_symbols: int
    volatility_eligible_rows: int
    volatility_eligible_symbols: int
    feature_integrity: VolatilityFeatureIntegrityEvidence
    volatility_feature: str
    volatility_horizon_scaling: str
    threshold_grid: tuple[float, ...]
    horizons: tuple[VolatilityHorizonEvidence, ...]
    split_crossing_windows_censored: bool
    exact_session_continuity_required: bool
    same_provider_ticker_required: bool
    endpoint_outcome_only: bool
    path_barrier_selected: bool
    path_barrier_reason: str
    prediction_label_policy_locked: bool
    source_split_evidence_path: str
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def natr_values_match(stored: float, derived: float) -> bool:
    difference = abs(float(stored) - float(derived))
    tolerance = ML_NATR_ABS_TOLERANCE + ML_NATR_REL_TOLERANCE * abs(float(derived))
    return difference <= tolerance


def scaled_move_threshold(*, natr_14: float, horizon_sessions: int, multiplier: float) -> float:
    if natr_14 <= 0:
        raise ValueError("natr_14 must be positive")
    if horizon_sessions < 1:
        raise ValueError("horizon_sessions must be positive")
    if multiplier <= 0:
        raise ValueError("multiplier must be positive")
    return float(natr_14) * math.sqrt(float(horizon_sessions)) * float(multiplier)


def classify_scaled_return(
    *,
    forward_return: float,
    natr_14: float,
    horizon_sessions: int,
    multiplier: float,
) -> str:
    threshold = scaled_move_threshold(
        natr_14=natr_14,
        horizon_sessions=horizon_sessions,
        multiplier=multiplier,
    )
    if forward_return >= threshold:
        return "UP"
    if forward_return <= -threshold:
        return "DOWN"
    return "NEUTRAL"


class MLOutcomeFamilyAudit:
    """Compare split-safe endpoint label families before Gate 4 locks a target.

    The v2 audit treats the permanent feature lake as a multi-file Parquet dataset
    whose early warm-up partitions can have weaker physical schemas than later
    partitions. Feature files are therefore unified by name, and NATR(14) is checked
    against its defining identity ATR(14) / current close over the exact accepted
    Gate 2 population before any outcome-family statistics are trusted.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.base = MLOutcomeFeasibilityProbe(settings)
        self.paths = self.base.paths

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return (
            root
            / "ml"
            / "outcome_family_audit"
            / f"{end_date.year:04d}"
            / f"{end_date}.json"
        )

    def _load_split_evidence(self, end_date: date) -> tuple[list[dict[str, object]], Path]:
        path = self.base.split_evidence_path(end_date)
        if not path.is_file():
            raise FileNotFoundError(
                "Gate 3 split evidence is missing; run probe_ml_outcome_feasibility.py first: "
                f"{path}"
            )
        result: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                normalized = _normalized_split(payload)
                if normalized is not None:
                    result.append(normalized)
        return result, path

    def _prepare_scaled_candidates(self, con: Any) -> VolatilityFeatureIntegrityEvidence:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        base = con.execute(
            "SELECT count(*), count(DISTINCT symbol) FROM ml_gate3_candidates"
        ).fetchone()
        base_rows = int(base[0])
        base_symbols = int(base[1])

        con.execute(
            f"""
            CREATE TEMP TABLE ml_gate3_feature_join AS
            SELECT
                c.symbol,
                c.session_date,
                c.instrument_id,
                c.close,
                c.session_seq,
                CAST(f.{ML_VOLATILITY_FEATURE} AS DOUBLE) AS stored_natr_14,
                CAST(f.atr_14 AS DOUBLE) AS atr_14,
                CASE
                    WHEN c.close > 0
                     AND f.atr_14 IS NOT NULL
                     AND isfinite(CAST(f.atr_14 AS DOUBLE))
                    THEN CAST(f.atr_14 AS DOUBLE) / c.close
                    ELSE NULL
                END AS derived_natr_14
            FROM ml_gate3_candidates c
            INNER JOIN read_parquet(
                {sql_string(feature_glob)},
                hive_partitioning=true,
                union_by_name=true
            ) f
              ON f.symbol = c.symbol
             AND CAST(f.timestamp_utc AS DATE) = c.session_date
            """
        )

        joined = con.execute(
            "SELECT count(*), count(DISTINCT symbol) FROM ml_gate3_feature_join"
        ).fetchone()
        join_rows = int(joined[0])
        join_symbols = int(joined[1])
        if join_rows != base_rows or join_symbols != base_symbols:
            raise RuntimeError(
                "Gate 3 volatility audit feature join failed full-population reconciliation: "
                f"base={base_rows:,}/{base_symbols:,} joined={join_rows:,}/{join_symbols:,}"
            )

        integrity = con.execute(
            f"""
            SELECT
                count(*) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                ) AS stored_finite,
                count(*) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                      AND stored_natr_14 > 0
                ) AS stored_positive,
                count(*) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                      AND stored_natr_14 = 0
                ) AS stored_zero,
                count(*) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                      AND stored_natr_14 < 0
                ) AS stored_negative,
                count(*) FILTER (
                    WHERE derived_natr_14 IS NOT NULL AND isfinite(derived_natr_14)
                      AND derived_natr_14 > 0
                ) AS derived_positive,
                count(*) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                      AND derived_natr_14 IS NOT NULL AND isfinite(derived_natr_14)
                ) AS comparable,
                count(*) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                      AND derived_natr_14 IS NOT NULL AND isfinite(derived_natr_14)
                      AND abs(stored_natr_14 - derived_natr_14)
                          > {ML_NATR_ABS_TOLERANCE}
                            + {ML_NATR_REL_TOLERANCE} * abs(derived_natr_14)
                ) AS mismatched,
                median(stored_natr_14) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                ) AS median_stored,
                median(derived_natr_14) FILTER (
                    WHERE derived_natr_14 IS NOT NULL AND isfinite(derived_natr_14)
                ) AS median_derived,
                max(abs(stored_natr_14 - derived_natr_14)) FILTER (
                    WHERE stored_natr_14 IS NOT NULL AND isfinite(stored_natr_14)
                      AND derived_natr_14 IS NOT NULL AND isfinite(derived_natr_14)
                ) AS max_difference
            FROM ml_gate3_feature_join
            """
        ).fetchone()

        comparable = int(integrity[5])
        mismatched = int(integrity[6])
        evidence = VolatilityFeatureIntegrityEvidence(
            base_candidate_rows=base_rows,
            base_candidate_symbols=base_symbols,
            feature_join_rows=join_rows,
            feature_join_symbols=join_symbols,
            stored_natr_finite_rows=int(integrity[0]),
            stored_natr_positive_rows=int(integrity[1]),
            stored_natr_zero_rows=int(integrity[2]),
            stored_natr_negative_rows=int(integrity[3]),
            derived_natr_positive_rows=int(integrity[4]),
            comparable_rows=comparable,
            mismatched_rows=mismatched,
            mismatch_fraction=_fraction(mismatched, comparable),
            median_stored_natr=_optional_float(integrity[7]),
            median_derived_natr=_optional_float(integrity[8]),
            max_abs_difference=_optional_float(integrity[9]),
            parquet_read_mode=ML_FEATURE_PARQUET_READ_MODE,
            full_population_reconciled=True,
            stored_vs_derived_reconciled=(comparable == base_rows and mismatched == 0),
        )
        if comparable != base_rows or mismatched != 0:
            raise RuntimeError(
                "Gate 3 volatility feature integrity failed: stored natr_14 does not "
                "reconcile exactly to atr_14 / close over the accepted population; "
                f"comparable={comparable:,}/{base_rows:,} mismatched={mismatched:,}."
            )

        con.execute(
            """
            CREATE TEMP TABLE ml_gate3_scaled_candidates AS
            SELECT
                symbol,
                session_date,
                instrument_id,
                close,
                session_seq,
                stored_natr_14 AS natr_14
            FROM ml_gate3_feature_join
            WHERE stored_natr_14 > 0
            """
        )
        return evidence

    def _horizon_evidence(self, con: Any, horizon: int) -> VolatilityHorizonEvidence:
        clean_valid = "future_date IS NOT NULL AND future_close > 0 AND NOT split_crossing"
        raw_return = "(future_close / close) - 1.0"
        scaled_move = f"natr_14 * sqrt({float(horizon)})"

        threshold_selects: list[str] = []
        for index, multiplier in enumerate(ML_VOLATILITY_THRESHOLD_GRID):
            threshold = f"({scaled_move}) * {float(multiplier)}"
            threshold_selects.extend(
                [
                    f"count(*) FILTER (WHERE {clean_valid} AND {raw_return} >= {threshold}) AS up_{index}",
                    f"count(*) FILTER (WHERE {clean_valid} AND {raw_return} <= -({threshold})) AS down_{index}",
                    f"count(*) FILTER (WHERE {clean_valid} AND {raw_return} < {threshold} AND {raw_return} > -({threshold})) AS neutral_{index}",
                ]
            )

        row = con.execute(
            f"""
            WITH outcome AS (
                SELECT
                    c.symbol,
                    c.session_date,
                    c.close,
                    c.natr_14,
                    fs.session_date AS future_date,
                    fb.close AS future_close,
                    EXISTS (
                        SELECT 1
                        FROM ml_split_events s
                        WHERE s.ticker = c.symbol
                          AND s.execution_date > c.session_date
                          AND s.execution_date <= fs.session_date
                    ) AS split_crossing
                FROM ml_gate3_scaled_candidates c
                LEFT JOIN ml_label_sessions fs
                  ON fs.session_seq = c.session_seq + {int(horizon)}
                LEFT JOIN ml_label_bars fb
                  ON fb.symbol = c.symbol
                 AND fb.session_date = fs.session_date
            )
            SELECT
                count(*) AS candidate_rows,
                count(*) FILTER (WHERE future_date IS NOT NULL AND future_close > 0) AS labelable_rows,
                count(*) FILTER (WHERE future_date IS NOT NULL AND future_close > 0 AND split_crossing) AS split_censored_rows,
                count(*) FILTER (WHERE {clean_valid}) AS usable_rows,
                median(natr_14) FILTER (WHERE {clean_valid}) AS median_start_natr,
                median({scaled_move}) FILTER (WHERE {clean_valid}) AS median_scaled_move,
                {', '.join(threshold_selects)}
            FROM outcome
            """
        ).fetchone()

        candidate_rows = int(row[0])
        labelable_rows = int(row[1])
        split_censored_rows = int(row[2])
        usable_rows = int(row[3])
        threshold_values = row[6:]
        thresholds: list[VolatilityThresholdEvidence] = []
        for index, multiplier in enumerate(ML_VOLATILITY_THRESHOLD_GRID):
            offset = index * 3
            up_rows = int(threshold_values[offset])
            down_rows = int(threshold_values[offset + 1])
            neutral_rows = int(threshold_values[offset + 2])
            directional_rows = up_rows + down_rows
            thresholds.append(
                VolatilityThresholdEvidence(
                    multiplier=float(multiplier),
                    up_rows=up_rows,
                    down_rows=down_rows,
                    neutral_rows=neutral_rows,
                    directional_rows=directional_rows,
                    up_fraction=_fraction(up_rows, usable_rows),
                    down_fraction=_fraction(down_rows, usable_rows),
                    neutral_fraction=_fraction(neutral_rows, usable_rows),
                    directional_fraction=_fraction(directional_rows, usable_rows),
                    up_fraction_of_directional=_fraction(up_rows, directional_rows),
                )
            )

        return VolatilityHorizonEvidence(
            horizon_sessions=horizon,
            candidate_rows=candidate_rows,
            labelable_rows=labelable_rows,
            split_censored_rows=split_censored_rows,
            usable_rows=usable_rows,
            usable_fraction=_fraction(usable_rows, candidate_rows),
            adjacent_label_overlap_sessions=max(0, horizon - 1),
            median_start_natr=_optional_float(row[4]),
            median_scaled_move=_optional_float(row[5]),
            thresholds=tuple(thresholds),
        )

    def run(self, end_date: date) -> MLOutcomeFamilyAuditReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")

        splits, split_path = self._load_split_evidence(end_date)
        con = connect_utc(":memory:")
        try:
            self.base._prepare_label_views(con, end_date, splits)
            feature_integrity = self._prepare_scaled_candidates(con)
            candidate = con.execute(
                "SELECT count(*), count(DISTINCT symbol) FROM ml_gate3_scaled_candidates"
            ).fetchone()
            horizons = tuple(
                self._horizon_evidence(con, horizon) for horizon in ML_OUTCOME_HORIZONS
            )
        finally:
            con.close()

        target = self.report_path(end_date)
        report = MLOutcomeFamilyAuditReport(
            contract_version=ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            candidate_rows=feature_integrity.base_candidate_rows,
            candidate_symbols=feature_integrity.base_candidate_symbols,
            volatility_eligible_rows=int(candidate[0]),
            volatility_eligible_symbols=int(candidate[1]),
            feature_integrity=feature_integrity,
            volatility_feature=ML_VOLATILITY_FEATURE,
            volatility_horizon_scaling=ML_VOLATILITY_HORIZON_SCALING,
            threshold_grid=ML_VOLATILITY_THRESHOLD_GRID,
            horizons=horizons,
            split_crossing_windows_censored=True,
            exact_session_continuity_required=True,
            same_provider_ticker_required=True,
            endpoint_outcome_only=True,
            path_barrier_selected=False,
            path_barrier_reason=(
                "Daily OHLC cannot order same-bar dual barrier touches without intraday path data; "
                "endpoint outcomes remain strategy-neutral."
            ),
            prediction_label_policy_locked=False,
            source_split_evidence_path=str(split_path),
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
