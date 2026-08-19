from __future__ import annotations

import json
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
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.outcome_family_audit import MLOutcomeFamilyAudit
from packages.ml.universe_probe import ML_HISTORY_ORIGIN_DATE
from packages.regimes.calibration import RegimeCalibration
from packages.regimes.state_engine import compute_regime_state_history
from packages.regimes.threshold_policy import REGIME_HISTORY_ORIGIN_DATE


ML_FEATURE_LEAKAGE_AUDIT_CONTRACT_VERSION = (
    "ml-feature-leakage-audit-v1-core33-postclose-market-regime-availability"
)
ML_FEATURE_PARQUET_READ_MODE_GATE5 = "union_by_name"
ML_OBSERVATION_AVAILABILITY_RULE = "POST_SESSION_CLOSE_AFTER_DAILY_FEATURE_MATERIALIZATION"
ML_ALLOWED_CORE_RAW_DEPENDENCIES = frozenset({"high", "low", "close", "volume"})
ML_PROHIBITED_MODEL_INPUT_FIELDS = (
    "future_date",
    "future_close",
    "forward_return",
    "prediction_label",
    "split_crossing",
)
ML_MARKET_REGIME_CANDIDATE_FIELDS = (
    "composite",
    "structure",
    "momentum",
    "volatility",
    "efficiency",
    "participation",
)


@dataclass(frozen=True, slots=True)
class CoreFeatureIntegrityEvidence:
    feature_count: int
    candidate_rows: int
    candidate_symbols: int
    candidate_distinct_keys: int
    feature_join_rows: int
    feature_join_symbols: int
    feature_join_distinct_keys: int
    non_numeric_feature_names: tuple[str, ...]
    rows_with_any_bad_feature: int
    bad_rows_by_feature: dict[str, int]
    full_population_reconciled: bool
    all_features_numeric: bool
    all_joined_features_finite: bool
    registry_dependencies_point_in_time_safe: bool


@dataclass(frozen=True, slots=True)
class RegimeContextEvidence:
    market_history_rows: int
    market_history_first_date: str | None
    market_history_last_date: str | None
    candidate_rows_with_market_context: int
    candidate_market_context_fraction: float
    market_context_point_in_time_replayable: bool
    market_context_candidate_fields: tuple[str, ...]
    sector_history_rows: int
    sector_history_symbols: int
    sector_history_replayable: bool
    sector_instrument_attachment_accepted: bool
    ticker_historical_attachment_accepted: bool
    sector_exclusion_reason: str
    ticker_exclusion_reason: str


@dataclass(frozen=True, slots=True)
class MLFeatureLeakageAuditReport:
    contract_version: str
    generated_at_utc: str
    history_start: str
    history_end: str
    wall_seconds: float
    audit_status: str
    parquet_read_mode: str
    observation_availability_rule: str
    core_feature_names: tuple[str, ...]
    prohibited_input_fields: tuple[str, ...]
    core_features: CoreFeatureIntegrityEvidence
    regime_context: RegimeContextEvidence
    production_feature_policy_locked: bool
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def core_registry_dependencies_are_point_in_time_safe() -> bool:
    return all(
        set(definition.dependencies).issubset(ML_ALLOWED_CORE_RAW_DEPENDENCIES)
        for definition in CORE_FEATURE_REGISTRY.all()
    )


def _date_string(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return str(pd.Timestamp(value).date())


class MLFeatureLeakageAudit:
    """Audit Gate 5 model-input availability without materializing a training dataset.

    Daily core features are legitimate only after the source session has completed and
    the Phase 6 daily feature partition has been materialized. The persisted
    ``timestamp_utc`` remains a market-data key; it is not treated as proof that the
    completed-session feature values existed earlier intraday.

    Market regime history is replayed from accepted Phase 9 point-in-time machinery.
    Sector and ticker histories are inventoried separately, but their instrument-level
    attachment is intentionally excluded until historical mapping semantics are proven
    safe for the Gate 2 observation population.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.family = MLOutcomeFamilyAudit(settings)
        self.base = self.family.base
        self.paths = self.base.paths
        self.regime_calibration = RegimeCalibration(settings)

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "feature_leakage_audit" / f"{end_date.year:04d}" / f"{end_date}.json"

    def _core_feature_evidence(self, con: Any, end_date: date) -> CoreFeatureIntegrityEvidence:
        definitions = CORE_FEATURE_REGISTRY.all()
        names = tuple(definition.name for definition in definitions)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        start = ML_HISTORY_ORIGIN_DATE.isoformat()
        end = end_date.isoformat()

        candidate = con.execute(
            """
            SELECT
                count(*) AS rows,
                count(DISTINCT symbol) AS symbols,
                count(DISTINCT (symbol, session_date)) AS distinct_keys
            FROM ml_gate3_candidates
            """
        ).fetchone()
        candidate_rows = int(candidate[0])
        candidate_symbols = int(candidate[1])
        candidate_keys = int(candidate[2])

        describe_sql = ", ".join(names)
        described = con.execute(
            f"""
            DESCRIBE SELECT {describe_sql}
            FROM read_parquet(
                {sql_string(feature_glob)},
                hive_partitioning=true,
                union_by_name=true
            )
            """
        ).fetchall()
        numeric_tokens = ("DOUBLE", "FLOAT", "DECIMAL", "BIGINT", "INTEGER", "SMALLINT", "TINYINT", "HUGEINT")
        non_numeric = tuple(
            str(row[0])
            for row in described
            if not any(token in str(row[1]).upper() for token in numeric_tokens)
        )

        bad_expressions = [
            (
                f"count(*) FILTER (WHERE f.{name} IS NULL "
                f"OR NOT isfinite(CAST(f.{name} AS DOUBLE))) AS bad_{index}"
            )
            for index, name in enumerate(names)
        ]
        any_bad = " OR ".join(
            f"f.{name} IS NULL OR NOT isfinite(CAST(f.{name} AS DOUBLE))"
            for name in names
        )
        row = con.execute(
            f"""
            WITH f AS (
                SELECT symbol, timestamp_utc, {describe_sql}
                FROM read_parquet(
                    {sql_string(feature_glob)},
                    hive_partitioning=true,
                    union_by_name=true
                )
                WHERE CAST(timestamp_utc AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
            ), joined AS (
                SELECT c.symbol AS candidate_symbol, c.session_date, f.*
                FROM ml_gate3_candidates c
                INNER JOIN f
                  ON f.symbol = c.symbol
                 AND CAST(f.timestamp_utc AS DATE) = c.session_date
            )
            SELECT
                count(*) AS join_rows,
                count(DISTINCT candidate_symbol) AS join_symbols,
                count(DISTINCT (candidate_symbol, session_date)) AS join_distinct_keys,
                count(*) FILTER (WHERE {any_bad}) AS any_bad_rows,
                {', '.join(bad_expressions)}
            FROM joined f
            """
        ).fetchone()

        join_rows = int(row[0])
        join_symbols = int(row[1])
        join_keys = int(row[2])
        rows_with_any_bad = int(row[3])
        bad_counts = {
            name: int(row[4 + index])
            for index, name in enumerate(names)
        }
        full_population = (
            candidate_rows == candidate_keys == join_rows == join_keys
            and candidate_symbols == join_symbols
        )
        registry_safe = core_registry_dependencies_are_point_in_time_safe()
        evidence = CoreFeatureIntegrityEvidence(
            feature_count=len(names),
            candidate_rows=candidate_rows,
            candidate_symbols=candidate_symbols,
            candidate_distinct_keys=candidate_keys,
            feature_join_rows=join_rows,
            feature_join_symbols=join_symbols,
            feature_join_distinct_keys=join_keys,
            non_numeric_feature_names=non_numeric,
            rows_with_any_bad_feature=rows_with_any_bad,
            bad_rows_by_feature=bad_counts,
            full_population_reconciled=full_population,
            all_features_numeric=(len(non_numeric) == 0),
            all_joined_features_finite=(rows_with_any_bad == 0),
            registry_dependencies_point_in_time_safe=registry_safe,
        )
        if not full_population:
            raise RuntimeError(
                "Gate 5 core-feature join failed accepted-population reconciliation: "
                f"candidate={candidate_rows:,}/{candidate_symbols:,}/{candidate_keys:,} "
                f"joined={join_rows:,}/{join_symbols:,}/{join_keys:,}"
            )
        if non_numeric:
            raise RuntimeError(
                "Gate 5 core-feature schema contains non-numeric model candidates: "
                + ", ".join(non_numeric)
            )
        if rows_with_any_bad != 0:
            offenders = ", ".join(
                f"{name}={count:,}" for name, count in bad_counts.items() if count
            )
            raise RuntimeError(
                "Gate 5 accepted population contains null/non-finite core features: " + offenders
            )
        if not registry_safe:
            raise RuntimeError("Gate 5 core feature registry references a non-point-in-time raw dependency")
        return evidence

    def _regime_context_evidence(self, con: Any, end_date: date) -> RegimeContextEvidence:
        breadth = self.regime_calibration._breadth_daily(REGIME_HISTORY_ORIGIN_DATE, end_date)
        proxies = self.regime_calibration._proxy_frame(REGIME_HISTORY_ORIGIN_DATE, end_date)
        _, effective_market, _, effective_sector = compute_regime_state_history(breadth, proxies)

        market_fields = ("trading_date",) + ML_MARKET_REGIME_CANDIDATE_FIELDS
        market = effective_market.loc[:, [field for field in market_fields if field in effective_market.columns]].copy()
        market["trading_date"] = pd.to_datetime(market["trading_date"]).dt.date
        con.register("ml_gate5_market_regime_history", market)
        coverage = con.execute(
            """
            SELECT
                count(*) FILTER (WHERE m.trading_date IS NOT NULL) AS covered_rows
            FROM ml_gate3_candidates c
            LEFT JOIN ml_gate5_market_regime_history m
              ON m.trading_date = c.session_date
            """
        ).fetchone()
        covered_rows = int(coverage[0])
        candidate_rows = int(con.execute("SELECT count(*) FROM ml_gate3_candidates").fetchone()[0])

        sector_symbols = 0
        if not effective_sector.empty and "symbol" in effective_sector.columns:
            sector_symbols = int(effective_sector["symbol"].nunique())

        return RegimeContextEvidence(
            market_history_rows=int(len(effective_market)),
            market_history_first_date=(
                None if effective_market.empty else _date_string(effective_market["trading_date"].min())
            ),
            market_history_last_date=(
                None if effective_market.empty else _date_string(effective_market["trading_date"].max())
            ),
            candidate_rows_with_market_context=covered_rows,
            candidate_market_context_fraction=_fraction(covered_rows, candidate_rows),
            market_context_point_in_time_replayable=not effective_market.empty,
            market_context_candidate_fields=ML_MARKET_REGIME_CANDIDATE_FIELDS,
            sector_history_rows=int(len(effective_sector)),
            sector_history_symbols=sector_symbols,
            sector_history_replayable=not effective_sector.empty,
            sector_instrument_attachment_accepted=False,
            ticker_historical_attachment_accepted=False,
            sector_exclusion_reason=(
                "Sector-proxy regime history is replayable, but attaching a historical stock observation "
                "to a sector proxy requires a date-safe instrument-to-sector mapping that Gate 5 has not accepted."
            ),
            ticker_exclusion_reason=(
                "The production ticker-state engine depends on date-specific routed-universe/discovery inputs. "
                "Current ticker state or current routing membership may not be projected backward onto the Gate 2 population."
            ),
        )

    def run(self, end_date: date) -> MLFeatureLeakageAuditReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")

        splits, _ = self.family._load_split_evidence(end_date)
        con = connect_utc(":memory:")
        try:
            self.base._prepare_label_views(con, end_date, splits)
            core = self._core_feature_evidence(con, end_date)
            regime = self._regime_context_evidence(con, end_date)
        finally:
            con.close()

        target = self.report_path(end_date)
        report = MLFeatureLeakageAuditReport(
            contract_version=ML_FEATURE_LEAKAGE_AUDIT_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            audit_status="EVIDENCE_ONLY",
            parquet_read_mode=ML_FEATURE_PARQUET_READ_MODE_GATE5,
            observation_availability_rule=ML_OBSERVATION_AVAILABILITY_RULE,
            core_feature_names=tuple(definition.name for definition in CORE_FEATURE_REGISTRY.all()),
            prohibited_input_fields=ML_PROHIBITED_MODEL_INPUT_FIELDS,
            core_features=core,
            regime_context=regime,
            production_feature_policy_locked=False,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
