from __future__ import annotations

import hashlib
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
from packages.ml.identity_probe import MLHistoricalIdentityProbe
from packages.ml.universe_probe import ML_HISTORY_ORIGIN_DATE
from packages.providers.massive.corporate_actions import MassiveCorporateActionsProvider


ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION = (
    "ml-outcome-feasibility-probe-v1-contiguous-horizons-provider-split-adjustment-audit"
)
ML_OUTCOME_HORIZONS = (1, 3, 5, 10, 20)
ML_NEAR_ZERO_RETURN = 0.005
ML_MATERIAL_SPLIT_RATIO_CHANGE = 0.20
ML_SPLIT_RESIDUAL_TOLERANCE = 0.15


@dataclass(frozen=True, slots=True)
class HorizonOutcomeEvidence:
    horizon_sessions: int
    candidate_rows: int
    labelable_rows: int
    labelable_fraction: float
    censored_rows: int
    split_crossing_rows: int
    split_crossing_fraction_of_labelable: float
    positive_rows: int
    negative_rows: int
    near_zero_rows: int
    abs_return_ge_25pct_rows: int
    abs_return_ge_50pct_rows: int
    abs_return_ge_100pct_rows: int
    non_split_abs_return_ge_50pct_rows: int
    return_quantiles: dict[str, float | None]


@dataclass(frozen=True, slots=True)
class SplitAdjustmentEvidence:
    fetched_split_events: int
    fetched_split_symbols: int
    material_split_events: int
    diagnostic_material_split_events: int
    unadjusted_like_events: int
    adjusted_like_events: int
    ambiguous_events: int
    median_abs_raw_return: float | None
    median_abs_expected_ratio_residual: float | None


@dataclass(frozen=True, slots=True)
class MLOutcomeFeasibilityProbeReport:
    contract_version: str
    generated_at_utc: str
    history_start: str
    history_end: str
    wall_seconds: float
    candidate_rows: int
    candidate_symbols: int
    horizons: tuple[HorizonOutcomeEvidence, ...]
    split_adjustment: SplitAdjustmentEvidence
    exact_session_continuity_required: bool
    same_provider_ticker_required: bool
    ticker_text_splicing_used: bool
    corporate_action_evidence_source: str
    label_policy_locked: bool
    split_evidence_path: str
    split_evidence_sha256: str
    report_path: str


def _fraction(numerator: int, denominator: int) -> float:
    return 0.0 if denominator <= 0 else float(numerator) / float(denominator)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _normalized_split(item: dict[str, Any]) -> dict[str, object] | None:
    ticker = str(item.get("ticker") or "").strip()
    raw_date = str(item.get("execution_date") or "").strip()
    if not ticker or not raw_date:
        return None
    try:
        execution_date = date.fromisoformat(raw_date)
    except ValueError:
        return None
    return {
        "id": str(item.get("id") or "") or None,
        "ticker": ticker,
        "execution_date": execution_date,
        "adjustment_type": str(item.get("adjustment_type") or "") or None,
        "split_from": _optional_float(item.get("split_from")),
        "split_to": _optional_float(item.get("split_to")),
        "historical_adjustment_factor": _optional_float(item.get("historical_adjustment_factor")),
    }


class MLOutcomeFeasibilityProbe:
    """Measure strategy-neutral forward-label feasibility before a target is locked."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        corporate_actions: MassiveCorporateActionsProvider | None = None,
    ) -> None:
        self.settings = settings
        self.identity = MLHistoricalIdentityProbe(settings)
        self.paths = self.identity.paths
        self.corporate_actions = corporate_actions or MassiveCorporateActionsProvider(settings)

    def report_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "outcome_feasibility_probe" / f"{end_date.year:04d}" / f"{end_date}.json"

    def split_evidence_path(self, end_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "outcome_feasibility_probe" / f"{end_date.year:04d}" / f"{end_date}-splits.jsonl"

    def _fetch_splits(self, end_date: date) -> tuple[list[dict[str, object]], Path, str]:
        normalized = [
            row
            for item in self.corporate_actions.splits(
                start_date=ML_HISTORY_ORIGIN_DATE,
                end_date=end_date,
            )
            if (row := _normalized_split(item)) is not None
        ]
        normalized.sort(key=lambda row: (str(row["execution_date"]), str(row["ticker"]), str(row["id"] or "")))
        payload = "".join(
            json.dumps(
                {
                    **row,
                    "execution_date": str(row["execution_date"]),
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
            for row in normalized
        )
        target = self.split_evidence_path(end_date)
        atomic_write_text(target, payload)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return normalized, target, digest

    def _prepare_label_views(
        self,
        con: Any,
        end_date: date,
        splits: list[dict[str, object]],
    ) -> None:
        identity_paths = self.identity._required_paths(end_date)
        self.identity._prepare_views(con, end_date, identity_paths)
        eligible = self.identity._eligibility_sql()
        safe = "identity_status IN ('AUTHORITATIVE_INTERVAL', 'UNIQUE_REFERENCE_NO_REUSE')"

        bar_glob = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        start = ML_HISTORY_ORIGIN_DATE.isoformat()
        end = end_date.isoformat()
        con.execute(
            f"""
            CREATE TEMP VIEW ml_label_bars AS
            SELECT
                symbol,
                CAST(session_date AS DATE) AS session_date,
                close,
                high,
                low
            FROM read_parquet({sql_string(bar_glob)}, hive_partitioning=true)
            WHERE CAST(session_date AS DATE) BETWEEN DATE '{start}' AND DATE '{end}'
              AND close > 0
            """
        )
        con.execute(
            """
            CREATE TEMP VIEW ml_label_sessions AS
            SELECT
                session_date,
                row_number() OVER (ORDER BY session_date) AS session_seq
            FROM (SELECT DISTINCT session_date FROM ml_label_bars)
            """
        )
        lead_columns = []
        for horizon in ML_OUTCOME_HORIZONS:
            lead_columns.extend(
                [
                    f"lead(s.session_seq, {horizon}) OVER w AS future_seq_{horizon}",
                    f"lead(b.session_date, {horizon}) OVER w AS future_date_{horizon}",
                    f"lead(b.close, {horizon}) OVER w AS future_close_{horizon}",
                ]
            )
        con.execute(
            f"""
            CREATE TEMP VIEW ml_label_indexed AS
            SELECT
                b.symbol,
                b.session_date,
                b.close,
                b.high,
                b.low,
                s.session_seq,
                {', '.join(lead_columns)}
            FROM ml_label_bars b
            INNER JOIN ml_label_sessions s USING (session_date)
            WINDOW w AS (PARTITION BY b.symbol ORDER BY s.session_seq)
            """
        )
        con.execute(
            f"""
            CREATE TEMP VIEW ml_gate3_candidates AS
            SELECT
                e.symbol,
                e.session_date,
                e.selected_instrument_id AS instrument_id,
                b.* EXCLUDE (symbol, session_date)
            FROM ml_identity_evidence e
            INNER JOIN ml_label_indexed b
              ON b.symbol = e.symbol AND b.session_date = e.session_date
            WHERE {safe} AND ({eligible})
            """
        )

        split_frame = pd.DataFrame.from_records(
            splits,
            columns=[
                "id",
                "ticker",
                "execution_date",
                "adjustment_type",
                "split_from",
                "split_to",
                "historical_adjustment_factor",
            ],
        )
        if split_frame.empty:
            split_frame = pd.DataFrame(
                {
                    "id": pd.Series(dtype="string"),
                    "ticker": pd.Series(dtype="string"),
                    "execution_date": pd.Series(dtype="datetime64[ns]"),
                    "adjustment_type": pd.Series(dtype="string"),
                    "split_from": pd.Series(dtype="float64"),
                    "split_to": pd.Series(dtype="float64"),
                    "historical_adjustment_factor": pd.Series(dtype="float64"),
                }
            )
        con.register("ml_split_events_input", split_frame)
        con.execute(
            """
            CREATE TEMP VIEW ml_split_events AS
            SELECT
                CAST(id AS VARCHAR) AS id,
                CAST(ticker AS VARCHAR) AS ticker,
                CAST(execution_date AS DATE) AS execution_date,
                CAST(adjustment_type AS VARCHAR) AS adjustment_type,
                CAST(split_from AS DOUBLE) AS split_from,
                CAST(split_to AS DOUBLE) AS split_to,
                CAST(historical_adjustment_factor AS DOUBLE) AS historical_adjustment_factor
            FROM ml_split_events_input
            """
        )

    def _horizon_evidence(self, con: Any, horizon: int) -> HorizonOutcomeEvidence:
        valid = f"future_seq_{horizon} = session_seq + {horizon} AND future_close_{horizon} > 0"
        ret = f"(future_close_{horizon} / close) - 1.0"
        split_exists = (
            f"EXISTS (SELECT 1 FROM ml_split_events s WHERE s.ticker = c.symbol "
            f"AND s.execution_date > c.session_date AND s.execution_date <= c.future_date_{horizon})"
        )
        row = con.execute(
            f"""
            SELECT
                count(*) AS candidate_rows,
                count(*) FILTER (WHERE {valid}) AS labelable_rows,
                count(*) FILTER (WHERE {valid} AND {split_exists}) AS split_crossing_rows,
                count(*) FILTER (WHERE {valid} AND {ret} > 0) AS positive_rows,
                count(*) FILTER (WHERE {valid} AND {ret} < 0) AS negative_rows,
                count(*) FILTER (WHERE {valid} AND abs({ret}) < {ML_NEAR_ZERO_RETURN}) AS near_zero_rows,
                count(*) FILTER (WHERE {valid} AND abs({ret}) >= 0.25) AS abs_ge_25,
                count(*) FILTER (WHERE {valid} AND abs({ret}) >= 0.50) AS abs_ge_50,
                count(*) FILTER (WHERE {valid} AND abs({ret}) >= 1.00) AS abs_ge_100,
                count(*) FILTER (WHERE {valid} AND abs({ret}) >= 0.50 AND NOT {split_exists}) AS nonsplit_abs_ge_50,
                quantile_cont({ret}, 0.01) FILTER (WHERE {valid}) AS q01,
                quantile_cont({ret}, 0.05) FILTER (WHERE {valid}) AS q05,
                quantile_cont({ret}, 0.25) FILTER (WHERE {valid}) AS q25,
                quantile_cont({ret}, 0.50) FILTER (WHERE {valid}) AS q50,
                quantile_cont({ret}, 0.75) FILTER (WHERE {valid}) AS q75,
                quantile_cont({ret}, 0.95) FILTER (WHERE {valid}) AS q95,
                quantile_cont({ret}, 0.99) FILTER (WHERE {valid}) AS q99
            FROM ml_gate3_candidates c
            """
        ).fetchone()
        candidate_rows = int(row[0])
        labelable_rows = int(row[1])
        split_crossing_rows = int(row[2])
        quantile_names = ("p01", "p05", "p25", "p50", "p75", "p95", "p99")
        return HorizonOutcomeEvidence(
            horizon_sessions=horizon,
            candidate_rows=candidate_rows,
            labelable_rows=labelable_rows,
            labelable_fraction=_fraction(labelable_rows, candidate_rows),
            censored_rows=candidate_rows - labelable_rows,
            split_crossing_rows=split_crossing_rows,
            split_crossing_fraction_of_labelable=_fraction(split_crossing_rows, labelable_rows),
            positive_rows=int(row[3]),
            negative_rows=int(row[4]),
            near_zero_rows=int(row[5]),
            abs_return_ge_25pct_rows=int(row[6]),
            abs_return_ge_50pct_rows=int(row[7]),
            abs_return_ge_100pct_rows=int(row[8]),
            non_split_abs_return_ge_50pct_rows=int(row[9]),
            return_quantiles={
                name: _optional_float(value)
                for name, value in zip(quantile_names, row[10:], strict=True)
            },
        )

    def _split_adjustment_evidence(
        self,
        con: Any,
        splits: list[dict[str, object]],
    ) -> SplitAdjustmentEvidence:
        con.execute(
            f"""
            CREATE TEMP VIEW ml_material_split_diagnostic AS
            WITH material AS (
                SELECT
                    s.*,
                    ss.session_seq
                FROM ml_split_events s
                INNER JOIN ml_label_sessions ss ON ss.session_date = s.execution_date
                WHERE s.split_from > 0
                  AND s.split_to > 0
                  AND abs((s.split_to / s.split_from) - 1.0) >= {ML_MATERIAL_SPLIT_RATIO_CHANGE}
            )
            SELECT
                m.ticker,
                m.execution_date,
                m.adjustment_type,
                m.split_from,
                m.split_to,
                prev.close AS previous_close,
                curr.close AS execution_close,
                (curr.close / prev.close) - 1.0 AS raw_return,
                (curr.close / (prev.close * (m.split_from / m.split_to))) - 1.0 AS expected_ratio_residual
            FROM material m
            INNER JOIN ml_label_indexed curr
              ON curr.symbol = m.ticker AND curr.session_seq = m.session_seq
            INNER JOIN ml_label_indexed prev
              ON prev.symbol = m.ticker AND prev.session_seq = m.session_seq - 1
            WHERE prev.close > 0 AND curr.close > 0
            """
        )
        row = con.execute(
            f"""
            SELECT
                count(*),
                count(*) FILTER (
                    WHERE abs(expected_ratio_residual) <= {ML_SPLIT_RESIDUAL_TOLERANCE}
                      AND abs(raw_return) > {ML_SPLIT_RESIDUAL_TOLERANCE}
                ),
                count(*) FILTER (WHERE abs(raw_return) <= {ML_SPLIT_RESIDUAL_TOLERANCE}),
                median(abs(raw_return)),
                median(abs(expected_ratio_residual))
            FROM ml_material_split_diagnostic
            """
        ).fetchone()
        diagnostic = int(row[0])
        unadjusted_like = int(row[1])
        adjusted_like = int(row[2])
        ambiguous = diagnostic - unadjusted_like - adjusted_like
        material = sum(
            1
            for item in splits
            if _optional_float(item.get("split_from"))
            and _optional_float(item.get("split_to"))
            and abs(
                float(item["split_to"]) / float(item["split_from"]) - 1.0
            ) >= ML_MATERIAL_SPLIT_RATIO_CHANGE
        )
        return SplitAdjustmentEvidence(
            fetched_split_events=len(splits),
            fetched_split_symbols=len({str(item["ticker"]) for item in splits}),
            material_split_events=material,
            diagnostic_material_split_events=diagnostic,
            unadjusted_like_events=unadjusted_like,
            adjusted_like_events=adjusted_like,
            ambiguous_events=ambiguous,
            median_abs_raw_return=_optional_float(row[3]),
            median_abs_expected_ratio_residual=_optional_float(row[4]),
        )

    def run(self, end_date: date) -> MLOutcomeFeasibilityProbeReport:
        started = perf_counter()
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")
        splits, split_path, split_sha = self._fetch_splits(end_date)
        con = connect_utc(":memory:")
        try:
            self._prepare_label_views(con, end_date, splits)
            candidate = con.execute(
                "SELECT count(*), count(DISTINCT symbol) FROM ml_gate3_candidates"
            ).fetchone()
            horizons = tuple(
                self._horizon_evidence(con, horizon) for horizon in ML_OUTCOME_HORIZONS
            )
            split_adjustment = self._split_adjustment_evidence(con, splits)
        finally:
            con.close()

        target = self.report_path(end_date)
        report = MLOutcomeFeasibilityProbeReport(
            contract_version=ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            candidate_rows=int(candidate[0]),
            candidate_symbols=int(candidate[1]),
            horizons=horizons,
            split_adjustment=split_adjustment,
            exact_session_continuity_required=True,
            same_provider_ticker_required=True,
            ticker_text_splicing_used=False,
            corporate_action_evidence_source="Massive /stocks/v1/splits",
            label_policy_locked=False,
            split_evidence_path=str(split_path),
            split_evidence_sha256=split_sha,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
