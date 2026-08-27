from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.ml.final_acceptance_policy import (
    ML_FINAL_ACCEPTANCE_HOLDOUT_END,
    ML_FINAL_ACCEPTANCE_HOLDOUT_START,
    ML_FINAL_ACCEPTANCE_PURGE_SESSIONS,
)
from packages.ml.outcome_probe import MLOutcomeFeasibilityProbe

from .phase25_gate7 import (
    PHASE25_GATE7_CONTEXT_CONTRACT_VERSION,
    PHASE25_GATE7_REPORT_CONTRACT_VERSION,
    Phase25Gate7RouteContextReplay,
)
from .phase25_gate7_validation import (
    PHASE25_GATE7_VALIDATION_CONTRACT_VERSION,
    Phase25Gate7IndependentValidator,
)
from .phase26_policy import (
    PHASE26_AUTOMATION_WRITES,
    PHASE26_BROKER_READS,
    PHASE26_BROKER_WRITES,
    PHASE26_CANDIDATES,
    PHASE26_LIVE_WRITES,
    PHASE26_ORDER_WRITES,
    PHASE26_OUTCOME_HORIZON_SESSIONS,
    PHASE26_PAPER_SUBMITS,
    PHASE26_PROTECTED_END,
    PHASE26_PROTECTED_START,
    PHASE26_PROVIDER_READS,
    PHASE26_PROVIDER_WRITES,
    PHASE26_RESEARCH_START,
    phase26_policy_fingerprint,
)
from .phase26_signals import apply_composite_scores


PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION = (
    "phase26-observation-report-v1-production-path-native-protected-blind"
)
PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION = (
    "phase26-development-observation-v1-exact-pit-three-session-return"
)
PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION = (
    "phase26-protected-predictor-v1-no-outcome-fields"
)
PHASE26_UPSTREAM_THROUGH_DATE = date.fromisoformat(PHASE26_PROTECTED_END)
PHASE26_OUTCOME_EVIDENCE_END = date(2026, 8, 14)
PHASE26_SPLIT_EVIDENCE_END = PHASE26_OUTCOME_EVIDENCE_END
PHASE26_OUTCOME_FIELDS = (
    "future_date",
    "future_close",
    "forward_return",
    "directional_return",
)


class Phase26ObservationError(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase26ObservationError(f"missing required JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase26ObservationError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase26ObservationError(f"JSON evidence must be an object: {path}")
    return value


def _rank_percentile(frame: pd.DataFrame, source: str, target: str) -> None:
    values = pd.to_numeric(frame[source], errors="coerce")
    frame[target] = values.groupby(frame["as_of_date"], sort=False).rank(
        method="average", pct=True
    )


def add_phase26_derived_fields(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in (
        "daily_open",
        "daily_close",
        "prior_close",
        "close_5_sessions_ago",
        "close_20_sessions_ago",
        "d1_realized_volatility_20",
    ):
        result[column] = pd.to_numeric(result[column], errors="coerce")

    result["gap_return"] = np.where(
        (result["daily_open"] > 0) & (result["prior_close"] > 0),
        result["daily_open"] / result["prior_close"] - 1.0,
        np.nan,
    )
    result["intraday_return"] = np.where(
        (result["daily_open"] > 0) & (result["daily_close"] > 0),
        result["daily_close"] / result["daily_open"] - 1.0,
        np.nan,
    )
    result["return_5d"] = np.where(
        (result["daily_close"] > 0) & (result["close_5_sessions_ago"] > 0),
        result["daily_close"] / result["close_5_sessions_ago"] - 1.0,
        np.nan,
    )
    result["return_20d"] = np.where(
        (result["daily_close"] > 0) & (result["close_20_sessions_ago"] > 0),
        result["daily_close"] / result["close_20_sessions_ago"] - 1.0,
        np.nan,
    )
    result["vol_scaled_return_20d"] = np.where(
        result["d1_realized_volatility_20"] > 0,
        result["return_20d"] / result["d1_realized_volatility_20"],
        np.nan,
    )

    _rank_percentile(result, "return_20d", "cs_return_20d_pct")
    _rank_percentile(
        result,
        "vol_scaled_return_20d",
        "cs_vol_scaled_return_20d_pct",
    )
    _rank_percentile(
        result,
        "d1_realized_volatility_20",
        "cs_realized_volatility_20_pct",
    )
    _rank_percentile(result, "d1_bb_width_20", "cs_bb_width_20_pct")
    _rank_percentile(result, "d1_dollar_volume", "cs_dollar_volume_pct")
    return apply_composite_scores(result)


class Phase26ObservationBuilder:
    """Build development outcomes and protected predictors from the Phase25 production path.

    The protected artifact deliberately contains no return/outcome columns. Protected
    returns are computed later only if development/internal evaluation freezes finalists.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase26" / "v1" / "observations"

    def report_path(self) -> Path:
        return self.root / "observation_report.json"

    def development_path(self) -> Path:
        return self.root / "development_observations.parquet"

    def protected_predictors_path(self) -> Path:
        return self.root / "protected_predictors.parquet"

    def _upstream_context(self) -> tuple[pd.DataFrame, Path, Path, dict[str, object]]:
        gate7 = Phase25Gate7RouteContextReplay(self.settings)
        report_path = gate7.report_path(PHASE26_UPSTREAM_THROUGH_DATE)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE7_REPORT_CONTRACT_VERSION:
            raise Phase26ObservationError("Phase25 Gate7 report contract mismatch")
        if report.get("pass") is not True:
            raise Phase26ObservationError("Phase25 Gate7 report is not passing")

        validation_path = Phase25Gate7IndependentValidator(self.settings).report_path(
            PHASE26_UPSTREAM_THROUGH_DATE
        )
        validation = _read_json(validation_path)
        if validation.get("contract_version") != PHASE25_GATE7_VALIDATION_CONTRACT_VERSION:
            raise Phase26ObservationError("Phase25 Gate7 validation contract mismatch")
        if validation.get("pass") is not True:
            raise Phase26ObservationError("Phase25 Gate7 independent validation is not passing")

        context_path = gate7.context_path(PHASE26_UPSTREAM_THROUGH_DATE)
        if not context_path.is_file():
            raise Phase26ObservationError("Phase25 Gate7 context is missing")
        context_sha = sha256_file(context_path)
        if report.get("context_sha256") != context_sha:
            raise Phase26ObservationError("Phase25 Gate7 context SHA mismatch")
        if validation.get("context_sha256") != context_sha:
            raise Phase26ObservationError("Phase25 Gate7 validation is not bound to context SHA")

        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"""
                SELECT *
                FROM read_parquet({sql_string(context_path)})
                ORDER BY as_of_date, instrument_id
                """
            ).fetch_df()
        finally:
            con.close()
        if frame.empty:
            raise Phase26ObservationError("Phase25 Gate7 context is empty")
        if set(frame["contract_version"].astype(str)) != {PHASE25_GATE7_CONTEXT_CONTRACT_VERSION}:
            raise Phase26ObservationError("Phase25 Gate7 context row contract mismatch")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        frame["safe_start_date"] = pd.to_datetime(frame["safe_start_date"]).dt.date
        frame["safe_end_date"] = pd.to_datetime(frame["safe_end_date"]).dt.date
        if frame.duplicated(["as_of_date", "instrument_id"], keep=False).any():
            raise Phase26ObservationError("Phase25 Gate7 context contains duplicate candidate keys")
        return frame, context_path, validation_path, report

    def _split_evidence(self) -> tuple[pd.DataFrame, Path, str]:
        path = MLOutcomeFeasibilityProbe(self.settings).split_evidence_path(
            PHASE26_SPLIT_EVIDENCE_END
        )
        if not path.is_file():
            raise Phase26ObservationError(
                "accepted split evidence through the Phase26 outcome endpoint is missing: "
                f"{path}"
            )
        records: list[dict[str, object]] = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                if not isinstance(payload, dict):
                    continue
                ticker = str(payload.get("ticker") or "").strip()
                raw_date = str(payload.get("execution_date") or "").strip()
                if not ticker or not raw_date:
                    continue
                try:
                    execution_date = date.fromisoformat(raw_date)
                except ValueError:
                    continue
                records.append({"ticker": ticker, "execution_date": execution_date})
        frame = pd.DataFrame.from_records(records, columns=["ticker", "execution_date"])
        if frame.empty:
            frame = pd.DataFrame(
                {
                    "ticker": pd.Series(dtype="string"),
                    "execution_date": pd.Series(dtype="datetime64[ns]"),
                }
            )
        return frame, path, sha256_file(path)

    def _session_frame(self) -> pd.DataFrame:
        start = date.fromisoformat(PHASE26_RESEARCH_START)
        sessions = tuple(self.calendar.sessions_in_range(start, PHASE26_OUTCOME_EVIDENCE_END))
        if not sessions or sessions[0] != start or sessions[-1] != PHASE26_OUTCOME_EVIDENCE_END:
            raise Phase26ObservationError("Phase26 exchange-session calendar does not cover frozen scope")
        return pd.DataFrame(
            {"session_date": list(sessions), "session_seq": list(range(len(sessions)))}
        )

    def _development_label_end(self, sessions: pd.DataFrame) -> tuple[date, tuple[date, ...]]:
        protected_start = date.fromisoformat(PHASE26_PROTECTED_START)
        ordered = sessions["session_date"].tolist()
        try:
            start_index = ordered.index(protected_start)
        except ValueError as exc:
            raise Phase26ObservationError("protected start is not in exchange calendar") from exc
        horizon = int(PHASE26_OUTCOME_HORIZON_SESSIONS)
        label_end_index = start_index - horizon - 1
        if label_end_index < 0:
            raise Phase26ObservationError("insufficient history before protected period")
        label_end = ordered[label_end_index]
        purge = tuple(ordered[label_end_index + 1 : start_index])
        accepted_purge = tuple(date.fromisoformat(value) for value in ML_FINAL_ACCEPTANCE_PURGE_SESSIONS)
        if purge != accepted_purge:
            raise Phase26ObservationError(
                f"Phase26 purge boundary drift: computed={purge} accepted={accepted_purge}"
            )
        if PHASE26_PROTECTED_START != ML_FINAL_ACCEPTANCE_HOLDOUT_START:
            raise Phase26ObservationError("Phase26 protected start drifted from accepted holdout")
        if PHASE26_PROTECTED_END != ML_FINAL_ACCEPTANCE_HOLDOUT_END:
            raise Phase26ObservationError("Phase26 protected end drifted from accepted holdout")
        return label_end, purge

    def _prepare_tables(
        self,
        con: Any,
        *,
        context: pd.DataFrame,
        sessions: pd.DataFrame,
        splits: pd.DataFrame,
    ) -> None:
        con.execute("SET preserve_insertion_order=false")
        con.register("p26_context_input", context)
        con.register("p26_sessions_input", sessions)
        con.register("p26_splits_input", splits)
        con.execute(
            """
            CREATE TEMP TABLE p26_context AS
            SELECT * FROM p26_context_input
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE p26_sessions AS
            SELECT CAST(session_date AS DATE) AS session_date, CAST(session_seq AS BIGINT) AS session_seq
            FROM p26_sessions_input
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE p26_splits AS
            SELECT CAST(ticker AS VARCHAR) AS ticker, CAST(execution_date AS DATE) AS execution_date
            FROM p26_splits_input
            """
        )
        con.execute(
            """
            CREATE TEMP TABLE p26_intervals AS
            SELECT DISTINCT interval_key, instrument_id, ticker, safe_start_date, safe_end_date
            FROM p26_context
            """
        )

        bar_1d = self.paths.glob_for_timeframe(Timeframe.DAY_1)
        feat_1d = self.paths.feature_glob(Timeframe.DAY_1)
        bar_4h = self.paths.glob_for_timeframe(Timeframe.HOUR_4)
        feat_4h = self.paths.feature_glob(Timeframe.HOUR_4)
        bar_1h = self.paths.glob_for_timeframe(Timeframe.HOUR_1)
        feat_1h = self.paths.feature_glob(Timeframe.HOUR_1)

        con.execute(
            f"""
            CREATE TEMP TABLE p26_label_bars AS
            SELECT
                b.symbol,
                CAST(b.session_date AS DATE) AS session_date,
                s.session_seq,
                CAST(b.open AS DOUBLE) AS open,
                CAST(b.close AS DOUBLE) AS close
            FROM read_parquet({sql_string(bar_1d)}, union_by_name=true, hive_partitioning=false) b
            INNER JOIN p26_sessions s ON s.session_date = CAST(b.session_date AS DATE)
            WHERE b.close IS NOT NULL AND isfinite(CAST(b.close AS DOUBLE)) AND b.close > 0
              AND b.open IS NOT NULL AND isfinite(CAST(b.open AS DOUBLE)) AND b.open > 0
            """
        )

        con.execute(
            f"""
            CREATE TEMP TABLE p26_daily AS
            SELECT
                i.interval_key,
                i.instrument_id,
                i.ticker,
                CAST(b.session_date AS DATE) AS session_date,
                s.session_seq,
                CAST(b.open AS DOUBLE) AS daily_open,
                CAST(b.close AS DOUBLE) AS daily_close,
                CAST(f.return_1 AS DOUBLE) AS d1_return_1,
                CAST(f.rsi_14 AS DOUBLE) AS d1_rsi_14,
                CAST(f.macd_hist_12_26_9 AS DOUBLE) AS d1_macd_hist_12_26_9,
                CAST(f.natr_14 AS DOUBLE) AS d1_natr_14,
                CAST(f.price_distance_ema_20 AS DOUBLE) AS d1_price_distance_ema_20,
                CAST(f.directional_efficiency_20 AS DOUBLE) AS d1_directional_efficiency_20,
                CAST(f.relative_dollar_volume_20 AS DOUBLE) AS d1_relative_dollar_volume_20,
                CAST(f.bb_position_20 AS DOUBLE) AS d1_bb_position_20,
                CAST(f.drawdown_20 AS DOUBLE) AS d1_drawdown_20,
                CAST(f.relative_volume_20 AS DOUBLE) AS d1_relative_volume_20,
                CAST(f.breakout_distance_20 AS DOUBLE) AS d1_breakout_distance_20,
                CAST(f.bb_width_20 AS DOUBLE) AS d1_bb_width_20,
                CAST(f.volume_zscore_20 AS DOUBLE) AS d1_volume_zscore_20,
                CAST(f.breakdown_distance_20 AS DOUBLE) AS d1_breakdown_distance_20,
                CAST(f.range_position_20 AS DOUBLE) AS d1_range_position_20,
                CAST(f.ema_20_slope_1 AS DOUBLE) AS d1_ema_20_slope_1,
                CAST(f.realized_volatility_20 AS DOUBLE) AS d1_realized_volatility_20,
                CAST(f.dollar_volume AS DOUBLE) AS d1_dollar_volume
            FROM read_parquet({sql_string(bar_1d)}, union_by_name=true, hive_partitioning=false) b
            INNER JOIN read_parquet({sql_string(feat_1d)}, union_by_name=true, hive_partitioning=false) f
              ON f.symbol = b.symbol AND f.timestamp_utc = b.timestamp_utc
            INNER JOIN p26_intervals i
              ON i.ticker = b.symbol
             AND CAST(b.session_date AS DATE) BETWEEN CAST(i.safe_start_date AS DATE) AND CAST(i.safe_end_date AS DATE)
            INNER JOIN p26_sessions s ON s.session_date = CAST(b.session_date AS DATE)
            """
        )

        con.execute(
            """
            CREATE TEMP TABLE p26_daily_enriched AS
            SELECT
                d.*,
                p1.daily_close AS prior_close,
                p5.daily_close AS close_5_sessions_ago,
                p20.daily_close AS close_20_sessions_ago
            FROM p26_daily d
            LEFT JOIN p26_daily p1
              ON p1.interval_key = d.interval_key AND p1.session_seq = d.session_seq - 1
            LEFT JOIN p26_daily p5
              ON p5.interval_key = d.interval_key AND p5.session_seq = d.session_seq - 5
            LEFT JOIN p26_daily p20
              ON p20.interval_key = d.interval_key AND p20.session_seq = d.session_seq - 20
            """
        )

        for name, bar_path, feature_path, prefix in (
            ("p26_h4", bar_4h, feat_4h, "h4"),
            ("p26_h1", bar_1h, feat_1h, "h1"),
        ):
            con.execute(
                f"""
                CREATE TEMP TABLE {name} AS
                SELECT * EXCLUDE (rn) FROM (
                    SELECT
                        i.interval_key,
                        CAST(b.session_date AS DATE) AS session_date,
                        CAST(f.rsi_14 AS DOUBLE) AS {prefix}_rsi_14,
                        CAST(f.macd_hist_12_26_9 AS DOUBLE) AS {prefix}_macd_hist_12_26_9,
                        CAST(f.price_distance_ema_20 AS DOUBLE) AS {prefix}_price_distance_ema_20,
                        row_number() OVER (
                            PARTITION BY i.interval_key, CAST(b.session_date AS DATE)
                            ORDER BY b.timestamp_utc DESC
                        ) AS rn
                    FROM read_parquet({sql_string(bar_path)}, union_by_name=true, hive_partitioning=false) b
                    INNER JOIN read_parquet({sql_string(feature_path)}, union_by_name=true, hive_partitioning=false) f
                      ON f.symbol = b.symbol
                     AND f.timestamp_utc = b.timestamp_utc
                     AND f.session_segment = b.session_segment
                    INNER JOIN p26_intervals i
                      ON i.ticker = b.symbol
                     AND CAST(b.session_date AS DATE) BETWEEN CAST(i.safe_start_date AS DATE) AND CAST(i.safe_end_date AS DATE)
                    WHERE b.session_segment = 'regular'
                ) WHERE rn = 1
                """
            )

        con.execute(
            """
            CREATE TEMP TABLE p26_predictors AS
            SELECT
                c.contract_version AS upstream_contract_version,
                CAST(c.as_of_date AS DATE) AS as_of_date,
                c.instrument_id,
                c.ticker,
                c.effective_state,
                c.direction,
                c.top_setup,
                CAST(c.priority_score AS DOUBLE) AS priority_score,
                c.market_state,
                c.sector_state,
                c.raw_ticker_state,
                c.effective_ticker_state,
                CAST(c.persistence_depth AS BIGINT) AS persistence_depth,
                c.identity_quality,
                CAST(c.safe_start_date AS DATE) AS safe_start_date,
                CAST(c.safe_end_date AS DATE) AS safe_end_date,
                c.interval_key,
                d.session_seq,
                d.daily_open,
                d.daily_close,
                d.prior_close,
                d.close_5_sessions_ago,
                d.close_20_sessions_ago,
                d.d1_return_1,
                d.d1_rsi_14,
                d.d1_macd_hist_12_26_9,
                d.d1_natr_14,
                d.d1_price_distance_ema_20,
                d.d1_directional_efficiency_20,
                d.d1_relative_dollar_volume_20,
                d.d1_bb_position_20,
                d.d1_drawdown_20,
                d.d1_relative_volume_20,
                d.d1_breakout_distance_20,
                d.d1_bb_width_20,
                d.d1_volume_zscore_20,
                d.d1_breakdown_distance_20,
                d.d1_range_position_20,
                d.d1_ema_20_slope_1,
                d.d1_realized_volatility_20,
                d.d1_dollar_volume,
                h4.h4_rsi_14,
                h4.h4_macd_hist_12_26_9,
                h4.h4_price_distance_ema_20,
                h1.h1_rsi_14,
                h1.h1_macd_hist_12_26_9,
                h1.h1_price_distance_ema_20
            FROM p26_context c
            LEFT JOIN p26_daily_enriched d
              ON d.interval_key = c.interval_key AND d.session_date = CAST(c.as_of_date AS DATE)
            LEFT JOIN p26_h4 h4
              ON h4.interval_key = c.interval_key AND h4.session_date = CAST(c.as_of_date AS DATE)
            LEFT JOIN p26_h1 h1
              ON h1.interval_key = c.interval_key AND h1.session_date = CAST(c.as_of_date AS DATE)
            ORDER BY c.as_of_date, c.instrument_id
            """
        )

    def _predictor_frame(self, con: Any) -> pd.DataFrame:
        frame = con.execute(
            "SELECT * FROM p26_predictors ORDER BY as_of_date, instrument_id"
        ).fetch_df()
        if frame.empty:
            raise Phase26ObservationError("Phase26 predictor reconstruction is empty")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        frame["safe_start_date"] = pd.to_datetime(frame["safe_start_date"]).dt.date
        frame["safe_end_date"] = pd.to_datetime(frame["safe_end_date"]).dt.date
        if frame.duplicated(["as_of_date", "instrument_id"], keep=False).any():
            raise Phase26ObservationError("Phase26 predictors contain duplicate candidate keys")
        return add_phase26_derived_fields(frame)

    def _development_outcomes(
        self,
        con: Any,
        predictors: pd.DataFrame,
        *,
        label_end: date,
    ) -> tuple[pd.DataFrame, int]:
        development = predictors.loc[predictors["as_of_date"] <= label_end].copy()
        con.register("p26_development_predictors", development)
        horizon = int(PHASE26_OUTCOME_HORIZON_SESSIONS)
        raw = con.execute(
            f"""
            SELECT
                p.*,
                fs.session_date AS future_date,
                fb.close AS future_close,
                CASE WHEN fb.close > 0 AND p.daily_close > 0
                     THEN fb.close / p.daily_close - 1.0 ELSE NULL END AS forward_return,
                EXISTS (
                    SELECT 1 FROM p26_splits s
                    WHERE s.ticker = p.ticker
                      AND s.execution_date > p.as_of_date
                      AND s.execution_date <= fs.session_date
                ) AS split_crossing
            FROM p26_development_predictors p
            LEFT JOIN p26_sessions fs ON fs.session_seq = p.session_seq + {horizon}
            LEFT JOIN p26_label_bars fb
              ON fb.symbol = p.ticker AND fb.session_date = fs.session_date
            ORDER BY p.as_of_date, p.instrument_id
            """
        ).fetch_df()
        raw["as_of_date"] = pd.to_datetime(raw["as_of_date"]).dt.date
        raw["future_date"] = pd.to_datetime(raw["future_date"], errors="coerce").dt.date
        split_censored = int(raw["split_crossing"].fillna(False).astype(bool).sum())
        usable = raw.loc[
            raw["future_date"].notna()
            & pd.to_numeric(raw["future_close"], errors="coerce").gt(0)
            & ~raw["split_crossing"].fillna(False).astype(bool)
        ].copy()
        usable["forward_return"] = pd.to_numeric(usable["forward_return"], errors="coerce")
        usable["directional_return"] = np.where(
            usable["direction"].astype(str) == "bullish",
            usable["forward_return"],
            -usable["forward_return"],
        )
        usable = usable.drop(columns=["split_crossing"])
        usable.insert(0, "contract_version", PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION)
        if not usable.empty and max(usable["future_date"]) >= date.fromisoformat(PHASE26_PROTECTED_START):
            raise Phase26ObservationError(
                "development outcome endpoint crossed into protected strategy-return period"
            )
        return usable, split_censored

    def _protected_predictors(self, predictors: pd.DataFrame) -> pd.DataFrame:
        start = date.fromisoformat(PHASE26_PROTECTED_START)
        end = date.fromisoformat(PHASE26_PROTECTED_END)
        protected = predictors.loc[
            (predictors["as_of_date"] >= start) & (predictors["as_of_date"] <= end)
        ].copy()
        protected.insert(0, "contract_version", PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION)
        forbidden = [field for field in PHASE26_OUTCOME_FIELDS if field in protected.columns]
        if forbidden:
            raise Phase26ObservationError(
                "protected predictor artifact contains outcome fields: " + ", ".join(forbidden)
            )
        return protected

    def _write_parquet(self, frame: pd.DataFrame, target: Path, *, order_by: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            con.register("p26_write_frame", frame)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"COPY (SELECT * FROM p26_write_frame ORDER BY {order_by}) "
                f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
                f"ROW_GROUP_SIZE {row_group_size})"
            )
            promote(temp, target)
        finally:
            con.close()

    def run(self) -> dict[str, object]:
        if any(
            value != 0
            for value in (
                PHASE26_PROVIDER_READS,
                PHASE26_PROVIDER_WRITES,
                PHASE26_BROKER_READS,
                PHASE26_BROKER_WRITES,
                PHASE26_ORDER_WRITES,
                PHASE26_PAPER_SUBMITS,
                PHASE26_LIVE_WRITES,
                PHASE26_AUTOMATION_WRITES,
            )
        ):
            raise Phase26ObservationError("Phase26 observation build must remain external-write/read free")

        context, context_path, gate7_validation_path, gate7_report = self._upstream_context()
        splits, split_path, split_sha = self._split_evidence()
        sessions = self._session_frame()
        label_end, purge_sessions = self._development_label_end(sessions)

        con = connect_utc(":memory:")
        try:
            self._prepare_tables(con, context=context, sessions=sessions, splits=splits)
            predictors = self._predictor_frame(con)
            development, split_censored = self._development_outcomes(
                con, predictors, label_end=label_end
            )
        finally:
            con.close()
        protected = self._protected_predictors(predictors)

        if development.empty:
            raise Phase26ObservationError("Phase26 development outcome population is empty")
        if protected.empty:
            raise Phase26ObservationError("Phase26 protected predictor population is empty")

        development_path = self.development_path()
        protected_path = self.protected_predictors_path()
        self._write_parquet(
            development,
            development_path,
            order_by="as_of_date, instrument_id",
        )
        self._write_parquet(
            protected,
            protected_path,
            order_by="as_of_date, instrument_id",
        )

        candidate_fields = sorted(
            {
                condition.feature
                for candidate in PHASE26_CANDIDATES
                for condition in candidate.conditions
            }
        )
        feature_complete = development[candidate_fields].notna().all(axis=1)
        predictor_context_rows = int(len(predictors))
        development_context_rows = int((predictors["as_of_date"] <= label_end).sum())
        protected_context_rows = int(
            (
                (predictors["as_of_date"] >= date.fromisoformat(PHASE26_PROTECTED_START))
                & (predictors["as_of_date"] <= date.fromisoformat(PHASE26_PROTECTED_END))
            ).sum()
        )
        purge_context_rows = int(predictors["as_of_date"].isin(purge_sessions).sum())

        checks = {
            "policy_frozen": len(PHASE26_CANDIDATES) == 24,
            "upstream_gate7_pass": gate7_report.get("pass") is True,
            "candidate_context_unique": not predictors.duplicated(
                ["as_of_date", "instrument_id"], keep=False
            ).any(),
            "development_nonempty": len(development) > 0,
            "protected_predictors_nonempty": len(protected) > 0,
            "protected_outcome_fields_absent": not any(
                field in protected.columns for field in PHASE26_OUTCOME_FIELDS
            ),
            "development_endpoints_preprotected": max(development["future_date"])
            < date.fromisoformat(PHASE26_PROTECTED_START),
            "protected_return_reads_zero": True,
            "sector_mapping_not_fabricated": context["sector_state"].isna().all(),
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase26ObservationError(
                "Phase26 observation checks failed: " + ", ".join(failed)
            )

        report_path = self.report_path()
        report: dict[str, object] = {
            "contract_version": PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
            "phase26_policy_fingerprint": phase26_policy_fingerprint(),
            "upstream_through_date": PHASE26_UPSTREAM_THROUGH_DATE.isoformat(),
            "outcome_evidence_end": PHASE26_OUTCOME_EVIDENCE_END.isoformat(),
            "gate7_context_sha256": sha256_file(context_path),
            "gate7_validation_sha256": sha256_file(gate7_validation_path),
            "split_evidence_path": str(split_path.resolve()),
            "split_evidence_sha256": split_sha,
            "predictor_context_rows": predictor_context_rows,
            "development_boundary_label_end": label_end.isoformat(),
            "development_boundary_purge_sessions": [item.isoformat() for item in purge_sessions],
            "development_context_rows": development_context_rows,
            "development_usable_rows": int(len(development)),
            "development_candidate_all_fields_complete_rows": int(feature_complete.sum()),
            "development_split_censored_rows": split_censored,
            "protected_context_rows": protected_context_rows,
            "protected_predictor_rows": int(len(protected)),
            "purge_context_rows": purge_context_rows,
            "protected_return_reads": 0,
            "development_sha256": sha256_file(development_path),
            "protected_predictors_sha256": sha256_file(protected_path),
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
