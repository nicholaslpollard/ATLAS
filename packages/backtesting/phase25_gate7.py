from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

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
from packages.regimes.calibration import RegimeCalibration
from packages.regimes.persistence_probe import confirm_states
from packages.regimes.split_origin_policy import MARKET_SECTOR_HISTORY_ORIGIN_DATE
from packages.regimes.state_engine import compute_regime_state_history
from packages.regimes.ticker_persistence_policy import TICKER_SELECTED_CONFIRMATION_SESSIONS
from packages.regimes.ticker_probe import candidate_ticker_state
from packages.schemas.discovery_score import DiscoveryDirection
from packages.strategies.registry import DEFAULT_STRATEGY_REGISTRY
from packages.strategies.router import StrategyRouter, StrategyRoutingContext

from .phase25_gate6 import (
    PHASE25_GATE6_POPULATION_CONTRACT_VERSION,
    PHASE25_GATE6_REPORT_CONTRACT_VERSION,
    Phase25Gate6DiscoveryReconstruction,
)
from .phase25_gate6_policy import phase25_gate6_policy_fingerprint
from .phase25_gate6_validation import (
    PHASE25_GATE6_VALIDATION_CONTRACT_VERSION,
    Phase25Gate6IndependentValidator,
)
from .phase25_gate7_policy import (
    PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED,
    PHASE25_GATE7_PROVIDER_READS,
    PHASE25_GATE7_PROVIDER_WRITES,
    PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY,
    PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED,
    PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED,
    PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED,
    PHASE25_GATE7_SUPPORT_REPLACEMENT_ALLOWED,
    phase25_gate7_policy_fingerprint,
)
from .phase25_policy import (
    PHASE25_BROKER_READS,
    PHASE25_BROKER_WRITES,
    PHASE25_LIVE_WRITES,
    PHASE25_ORDER_WRITES,
    PHASE25_PAPER_SUBMITS,
    PHASE25_PHASE11_SUPPORT_WRITES,
    PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
    PHASE25_ROUTE_REPLAY_ORIGIN,
)


PHASE25_GATE7_REPORT_CONTRACT_VERSION = (
    "phase25-gate7-report-v1-exact-pit-market-ticker-route-context"
)
PHASE25_GATE7_CONTEXT_CONTRACT_VERSION = (
    "phase25-gate7-context-v1-warm-hot-market-ticker"
)
PHASE25_GATE7_ROUTE_CONTRACT_VERSION = (
    "phase25-gate7-route-v1-production-strategy-router-no-rule-evaluation"
)


class Phase25Gate7Error(RuntimeError):
    pass


def _read_json(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise Phase25Gate7Error(f"missing required JSON evidence: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase25Gate7Error(f"invalid JSON evidence: {path}") from exc
    if not isinstance(value, dict):
        raise Phase25Gate7Error(f"JSON evidence must be an object: {path}")
    return value


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _safe(path: Path | str) -> str:
    return str(path).replace("\\", "/").replace("'", "''")


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return text or None


def persist_exact_interval_ticker_states(
    raw: pd.DataFrame,
    *,
    session_ordinals: dict[date, int],
) -> pd.DataFrame:
    """Apply accepted dimensional confirmation independently inside exact PIT intervals.

    A missing feature session breaks continuity.  The next available observation starts a
    new persistence segment and therefore initializes immediately, matching the accepted
    ticker persistence semantics without splicing across ticker changes or inactive gaps.
    """

    columns = [
        "interval_key",
        "instrument_id",
        "ticker",
        "trading_date",
        "raw_daily_structure",
        "raw_short_alignment",
        "raw_momentum",
        "raw_ticker_state",
        "effective_daily_structure",
        "effective_short_alignment",
        "effective_momentum",
        "effective_ticker_state",
        "persistence_depth",
    ]
    if raw.empty:
        return pd.DataFrame(columns=columns)

    records: list[dict[str, object]] = []
    for interval_key, subset in raw.groupby("interval_key", sort=True, observed=True):
        data = subset.sort_values("trading_date").reset_index(drop=True).copy()
        dates = pd.to_datetime(data["trading_date"]).dt.date.tolist()
        starts = [0]
        previous: int | None = None
        for index, trading_date in enumerate(dates):
            ordinal = session_ordinals.get(trading_date)
            if ordinal is None:
                raise Phase25Gate7Error(f"ticker-state date is outside replay calendar: {trading_date}")
            if index > 0 and (previous is None or ordinal != previous + 1):
                starts.append(index)
            previous = ordinal
        starts.append(len(data))

        for left, right in zip(starts[:-1], starts[1:], strict=True):
            segment = data.iloc[left:right].copy()
            structures = segment["daily_structure"].astype(str).tolist()
            alignments = segment["short_alignment"].astype(str).tolist()
            momentums = segment["momentum"].astype(str).tolist()
            effective_structures = confirm_states(
                structures, TICKER_SELECTED_CONFIRMATION_SESSIONS
            )
            effective_alignments = confirm_states(
                alignments, TICKER_SELECTED_CONFIRMATION_SESSIONS
            )
            effective_momentums = confirm_states(
                momentums, TICKER_SELECTED_CONFIRMATION_SESSIONS
            )
            for depth, (row, structure, alignment, momentum) in enumerate(
                zip(
                    segment.itertuples(index=False),
                    effective_structures,
                    effective_alignments,
                    effective_momentums,
                    strict=True,
                ),
                start=1,
            ):
                effective_state = candidate_ticker_state(
                    daily_structure=structure,
                    short_alignment=alignment,
                    momentum=momentum,
                )
                records.append(
                    {
                        "interval_key": str(interval_key),
                        "instrument_id": str(row.instrument_id),
                        "ticker": str(row.ticker),
                        "trading_date": row.trading_date,
                        "raw_daily_structure": str(row.daily_structure),
                        "raw_short_alignment": str(row.short_alignment),
                        "raw_momentum": str(row.momentum),
                        "raw_ticker_state": str(row.candidate_state),
                        "effective_daily_structure": structure,
                        "effective_short_alignment": alignment,
                        "effective_momentum": momentum,
                        "effective_ticker_state": effective_state,
                        "persistence_depth": depth,
                    }
                )
    return pd.DataFrame.from_records(records, columns=columns)


class Phase25Gate7RouteContextReplay:
    """Provider-free market/ticker regime routing over the accepted Gate6 population."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.router = StrategyRouter(DEFAULT_STRATEGY_REGISTRY)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase25" / "v1" / "gate7"

    def run_root(self, through_date: date) -> Path:
        return self.root / f"through={through_date}"

    def report_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "route_context_report.json"

    def context_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "route_context.parquet"

    def routes_path(self, through_date: date) -> Path:
        return self.run_root(through_date) / "route_decisions.parquet"

    def _gate6_evidence(
        self, through_date: date
    ) -> tuple[Path, dict[str, object], Path, dict[str, object], Path]:
        gate6_runner = Phase25Gate6DiscoveryReconstruction(self.settings)
        report_path = gate6_runner.report_path(through_date)
        report = _read_json(report_path)
        if report.get("contract_version") != PHASE25_GATE6_REPORT_CONTRACT_VERSION:
            raise Phase25Gate7Error("Gate6 report contract mismatch")
        if report.get("phase25_gate6_policy_fingerprint") != phase25_gate6_policy_fingerprint():
            raise Phase25Gate7Error("Gate6 policy fingerprint mismatch")
        if report.get("through_date") != through_date.isoformat() or report.get("pass") is not True:
            raise Phase25Gate7Error("Gate6 report is not accepted for requested through-date")

        validation_path = Phase25Gate6IndependentValidator(self.settings).report_path(through_date)
        validation = _read_json(validation_path)
        if validation.get("contract_version") != PHASE25_GATE6_VALIDATION_CONTRACT_VERSION:
            raise Phase25Gate7Error("Gate6 independent-validation contract mismatch")
        if validation.get("pass") is not True:
            raise Phase25Gate7Error("Gate6 independent validation is not passing")

        population_path = gate6_runner.population_path(through_date)
        if not population_path.is_file():
            raise Phase25Gate7Error("Gate6 WARM/HOT directional population is missing")
        if report.get("population_sha256") != sha256_file(population_path):
            raise Phase25Gate7Error("Gate6 population SHA does not match accepted report")
        return report_path, report, validation_path, validation, population_path

    def _sessions(self, through_date: date) -> tuple[date, ...]:
        if through_date < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate7Error("through-date predates route replay origin")
        if not self.calendar.is_session(through_date):
            raise Phase25Gate7Error(f"through-date is not an XNYS session: {through_date}")
        sessions = tuple(self.calendar.sessions_in_range(PHASE25_ROUTE_REPLAY_ORIGIN, through_date))
        if not sessions or sessions[0] != PHASE25_ROUTE_REPLAY_ORIGIN or sessions[-1] != through_date:
            raise Phase25Gate7Error("Gate7 exchange-session scope mismatch")
        return sessions

    def _load_population(self, path: Path) -> pd.DataFrame:
        con = connect_utc(":memory:")
        try:
            frame = con.execute(
                f"""
                SELECT contract_version, as_of_date, instrument_id, ticker,
                       raw_state, effective_state, direction, top_setup,
                       scored_timeframes, priority_score, bull_evidence, bear_evidence,
                       transition
                FROM read_parquet({sql_string(path)})
                ORDER BY as_of_date, instrument_id
                """
            ).fetch_df()
        finally:
            con.close()
        if frame.empty:
            raise Phase25Gate7Error("Gate6 WARM/HOT directional population is empty")
        if set(frame["contract_version"].astype(str)) != {PHASE25_GATE6_POPULATION_CONTRACT_VERSION}:
            raise Phase25Gate7Error("Gate6 population contract mismatch")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        duplicate = frame.duplicated(["as_of_date", "instrument_id"], keep=False)
        if bool(duplicate.any()):
            raise Phase25Gate7Error("Gate6 population contains duplicate session/instrument keys")
        if not set(frame["effective_state"].astype(str)).issubset({"warm", "hot"}):
            raise Phase25Gate7Error("Gate6 population contains non-WARM/HOT state")
        if not set(frame["direction"].astype(str)).issubset({"bullish", "bearish"}):
            raise Phase25Gate7Error("Gate6 population contains nondirectional rows")
        return frame

    def _market_states(self, through_date: date) -> pd.DataFrame:
        calibration = RegimeCalibration(self.settings)
        breadth = calibration._breadth_daily(MARKET_SECTOR_HISTORY_ORIGIN_DATE, through_date)
        proxies = calibration._proxy_frame(MARKET_SECTOR_HISTORY_ORIGIN_DATE, through_date)
        _, effective_market, _, _ = compute_regime_state_history(breadth, proxies)
        if effective_market.empty:
            raise Phase25Gate7Error("market regime reconstruction produced no effective history")
        result = effective_market[["trading_date", "composite"]].copy()
        result["trading_date"] = pd.to_datetime(result["trading_date"]).dt.date
        result = result.rename(columns={"composite": "market_state"})
        result["market_state"] = result["market_state"].astype(str)
        return result.drop_duplicates("trading_date", keep="last").sort_values("trading_date")

    def _exact_intervals(
        self,
        *,
        population: pd.DataFrame,
        sessions: tuple[date, ...],
    ) -> pd.DataFrame:
        pairs = population[["instrument_id", "ticker"]].drop_duplicates().copy()
        calendar = pd.DataFrame(
            {
                "as_of_date": list(sessions),
                "session_ordinal": list(range(len(sessions))),
            }
        )
        reference_glob = _safe(self.paths.reference_snapshot_glob())
        con = connect_utc(":memory:")
        try:
            con.register("p25_gate7_pairs", pairs)
            con.register("p25_gate7_sessions", calendar)
            intervals = con.execute(
                f"""
                WITH exact_rows AS (
                    SELECT DISTINCT
                        r.instrument_id,
                        r.ticker,
                        CAST(r.as_of_date AS DATE) AS as_of_date,
                        r.identity_quality
                    FROM read_parquet('{reference_glob}', union_by_name=true, hive_partitioning=false) r
                    INNER JOIN p25_gate7_pairs p
                      ON p.instrument_id = r.instrument_id AND p.ticker = r.ticker
                    INNER JOIN p25_gate7_sessions s
                      ON s.as_of_date = CAST(r.as_of_date AS DATE)
                    WHERE coalesce(r.active, FALSE) = TRUE
                ), ordered AS (
                    SELECT
                        e.*,
                        s.session_ordinal,
                        lag(s.session_ordinal) OVER (
                            PARTITION BY e.instrument_id, e.ticker ORDER BY s.session_ordinal
                        ) AS previous_ordinal,
                        lag(e.identity_quality) OVER (
                            PARTITION BY e.instrument_id, e.ticker ORDER BY s.session_ordinal
                        ) AS previous_quality
                    FROM exact_rows e
                    INNER JOIN p25_gate7_sessions s USING (as_of_date)
                ), marked AS (
                    SELECT *,
                        CASE
                            WHEN previous_ordinal IS NULL THEN 1
                            WHEN session_ordinal <> previous_ordinal + 1 THEN 1
                            WHEN identity_quality <> previous_quality THEN 1
                            ELSE 0
                        END AS segment_break
                    FROM ordered
                ), segmented AS (
                    SELECT *,
                        sum(segment_break) OVER (
                            PARTITION BY instrument_id, ticker
                            ORDER BY session_ordinal
                            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                        ) AS segment_id
                    FROM marked
                )
                SELECT
                    instrument_id,
                    ticker,
                    identity_quality,
                    segment_id,
                    min(as_of_date) AS safe_start_date,
                    max(as_of_date) AS safe_end_date,
                    count(*) AS exact_session_count
                FROM segmented
                GROUP BY instrument_id, ticker, identity_quality, segment_id
                ORDER BY instrument_id, ticker, safe_start_date
                """
            ).fetch_df()
        finally:
            con.close()
        if intervals.empty:
            raise Phase25Gate7Error("exact PIT interval reconstruction produced no rows")
        intervals["safe_start_date"] = pd.to_datetime(intervals["safe_start_date"]).dt.date
        intervals["safe_end_date"] = pd.to_datetime(intervals["safe_end_date"]).dt.date
        intervals["interval_key"] = [
            _stable_hash(
                {
                    "instrument_id": str(row.instrument_id),
                    "ticker": str(row.ticker),
                    "identity_quality": str(row.identity_quality),
                    "start": row.safe_start_date.isoformat(),
                    "end": row.safe_end_date.isoformat(),
                }
            )
            for row in intervals.itertuples(index=False)
        ]
        return intervals

    def _bind_population_intervals(
        self,
        population: pd.DataFrame,
        intervals: pd.DataFrame,
    ) -> pd.DataFrame:
        source = population.copy()
        source["_row_id"] = range(len(source))
        con = connect_utc(":memory:")
        try:
            con.register("p25_gate7_population", source)
            con.register("p25_gate7_intervals", intervals)
            bound = con.execute(
                """
                SELECT
                    p.* EXCLUDE (_row_id),
                    i.interval_key,
                    i.identity_quality,
                    i.safe_start_date,
                    i.safe_end_date,
                    i.exact_session_count
                FROM p25_gate7_population p
                INNER JOIN p25_gate7_intervals i
                  ON i.instrument_id = p.instrument_id
                 AND i.ticker = p.ticker
                 AND p.as_of_date BETWEEN i.safe_start_date AND i.safe_end_date
                ORDER BY p.as_of_date, p.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()
        if len(bound) != len(population):
            raise Phase25Gate7Error(
                f"exact PIT interval binding mismatch: population={len(population)} bound={len(bound)}"
            )
        bound["as_of_date"] = pd.to_datetime(bound["as_of_date"]).dt.date
        bound["safe_start_date"] = pd.to_datetime(bound["safe_start_date"]).dt.date
        bound["safe_end_date"] = pd.to_datetime(bound["safe_end_date"]).dt.date
        if bool(bound.duplicated(["as_of_date", "instrument_id"], keep=False).any()):
            raise Phase25Gate7Error("candidate row matched multiple exact PIT intervals")
        return bound

    def _raw_ticker_state_history(self, intervals: pd.DataFrame) -> pd.DataFrame:
        safe_intervals = intervals[
            ["interval_key", "instrument_id", "ticker", "safe_start_date", "safe_end_date"]
        ].copy()
        bar_1d = _safe(self.paths.glob_for_timeframe(Timeframe.DAY_1))
        feat_1d = _safe(self.paths.feature_glob(Timeframe.DAY_1))
        bar_4h = _safe(self.paths.glob_for_timeframe(Timeframe.HOUR_4))
        feat_4h = _safe(self.paths.feature_glob(Timeframe.HOUR_4))
        bar_1h = _safe(self.paths.glob_for_timeframe(Timeframe.HOUR_1))
        feat_1h = _safe(self.paths.feature_glob(Timeframe.HOUR_1))
        con = connect_utc(":memory:")
        try:
            con.register("p25_gate7_intervals", safe_intervals)
            return con.execute(
                f"""
                WITH daily AS (
                    SELECT
                        i.interval_key,
                        i.instrument_id,
                        i.ticker,
                        b.session_date AS trading_date,
                        b.close,
                        f.ema_20,
                        f.ema_50,
                        f.ema_200,
                        f.return_1,
                        f.rsi_14,
                        f.macd_hist_12_26_9,
                        f.ema_20_slope_1
                    FROM read_parquet('{bar_1d}', union_by_name=true, hive_partitioning=false) b
                    INNER JOIN read_parquet('{feat_1d}', union_by_name=true, hive_partitioning=false) f
                      ON f.symbol = b.symbol AND f.timestamp_utc = b.timestamp_utc
                    INNER JOIN p25_gate7_intervals i
                      ON i.ticker = b.symbol
                     AND b.session_date BETWEEN i.safe_start_date AND i.safe_end_date
                    WHERE b.close IS NOT NULL AND isfinite(b.close)
                      AND f.ema_20 IS NOT NULL AND isfinite(f.ema_20)
                      AND f.ema_50 IS NOT NULL AND isfinite(f.ema_50)
                      AND f.ema_200 IS NOT NULL AND isfinite(f.ema_200)
                      AND f.return_1 IS NOT NULL AND isfinite(f.return_1)
                      AND f.rsi_14 IS NOT NULL AND isfinite(f.rsi_14)
                      AND f.macd_hist_12_26_9 IS NOT NULL AND isfinite(f.macd_hist_12_26_9)
                      AND f.ema_20_slope_1 IS NOT NULL AND isfinite(f.ema_20_slope_1)
                ), intraday_4h AS (
                    SELECT * EXCLUDE (rn) FROM (
                        SELECT
                            i.interval_key,
                            i.instrument_id,
                            b.session_date AS trading_date,
                            b.close,
                            f.ema_20,
                            f.ema_50,
                            f.rsi_14,
                            f.macd_hist_12_26_9,
                            f.ema_20_slope_1,
                            row_number() OVER (
                                PARTITION BY i.interval_key, b.session_date
                                ORDER BY b.timestamp_utc DESC
                            ) AS rn
                        FROM read_parquet('{bar_4h}', union_by_name=true, hive_partitioning=false) b
                        INNER JOIN read_parquet('{feat_4h}', union_by_name=true, hive_partitioning=false) f
                          ON f.symbol = b.symbol
                         AND f.timestamp_utc = b.timestamp_utc
                         AND f.session_segment = b.session_segment
                        INNER JOIN p25_gate7_intervals i
                          ON i.ticker = b.symbol
                         AND b.session_date BETWEEN i.safe_start_date AND i.safe_end_date
                        WHERE b.session_segment = 'regular'
                    ) WHERE rn = 1
                ), intraday_1h AS (
                    SELECT * EXCLUDE (rn) FROM (
                        SELECT
                            i.interval_key,
                            i.instrument_id,
                            b.session_date AS trading_date,
                            b.close,
                            f.ema_20,
                            f.ema_50,
                            f.rsi_14,
                            f.macd_hist_12_26_9,
                            f.ema_20_slope_1,
                            row_number() OVER (
                                PARTITION BY i.interval_key, b.session_date
                                ORDER BY b.timestamp_utc DESC
                            ) AS rn
                        FROM read_parquet('{bar_1h}', union_by_name=true, hive_partitioning=false) b
                        INNER JOIN read_parquet('{feat_1h}', union_by_name=true, hive_partitioning=false) f
                          ON f.symbol = b.symbol
                         AND f.timestamp_utc = b.timestamp_utc
                         AND f.session_segment = b.session_segment
                        INNER JOIN p25_gate7_intervals i
                          ON i.ticker = b.symbol
                         AND b.session_date BETWEEN i.safe_start_date AND i.safe_end_date
                        WHERE b.session_segment = 'regular'
                    ) WHERE rn = 1
                ), scores AS (
                    SELECT
                        d.interval_key,
                        d.instrument_id,
                        d.ticker,
                        d.trading_date,
                        (
                            CASE WHEN d.close > d.ema_20 THEN 1 WHEN d.close < d.ema_20 THEN -1 ELSE 0 END +
                            CASE WHEN d.close > d.ema_50 THEN 1 WHEN d.close < d.ema_50 THEN -1 ELSE 0 END +
                            CASE WHEN d.close > d.ema_200 THEN 1 WHEN d.close < d.ema_200 THEN -1 ELSE 0 END +
                            CASE WHEN d.ema_20 > d.ema_50 THEN 1 WHEN d.ema_20 < d.ema_50 THEN -1 ELSE 0 END +
                            CASE WHEN d.ema_50 > d.ema_200 THEN 1 WHEN d.ema_50 < d.ema_200 THEN -1 ELSE 0 END +
                            CASE WHEN d.ema_20_slope_1 > 0 THEN 1 WHEN d.ema_20_slope_1 < 0 THEN -1 ELSE 0 END
                        ) AS structure_score,
                        (
                            CASE WHEN h4.close > h4.ema_20 THEN 1 WHEN h4.close < h4.ema_20 THEN -1 ELSE 0 END +
                            CASE WHEN h4.close > h4.ema_50 THEN 1 WHEN h4.close < h4.ema_50 THEN -1 ELSE 0 END +
                            CASE WHEN h4.rsi_14 > 50 THEN 1 WHEN h4.rsi_14 < 50 THEN -1 ELSE 0 END +
                            CASE WHEN h4.macd_hist_12_26_9 > 0 THEN 1 WHEN h4.macd_hist_12_26_9 < 0 THEN -1 ELSE 0 END +
                            CASE WHEN h4.ema_20_slope_1 > 0 THEN 1 WHEN h4.ema_20_slope_1 < 0 THEN -1 ELSE 0 END
                        ) AS score_4h,
                        (
                            CASE WHEN h1.close > h1.ema_20 THEN 1 WHEN h1.close < h1.ema_20 THEN -1 ELSE 0 END +
                            CASE WHEN h1.close > h1.ema_50 THEN 1 WHEN h1.close < h1.ema_50 THEN -1 ELSE 0 END +
                            CASE WHEN h1.rsi_14 > 50 THEN 1 WHEN h1.rsi_14 < 50 THEN -1 ELSE 0 END +
                            CASE WHEN h1.macd_hist_12_26_9 > 0 THEN 1 WHEN h1.macd_hist_12_26_9 < 0 THEN -1 ELSE 0 END +
                            CASE WHEN h1.ema_20_slope_1 > 0 THEN 1 WHEN h1.ema_20_slope_1 < 0 THEN -1 ELSE 0 END
                        ) AS score_1h,
                        (
                            CASE WHEN d.return_1 > 0 THEN 1 WHEN d.return_1 < 0 THEN -1 ELSE 0 END +
                            CASE WHEN d.macd_hist_12_26_9 > 0 THEN 1 WHEN d.macd_hist_12_26_9 < 0 THEN -1 ELSE 0 END +
                            CASE WHEN d.rsi_14 >= 55 THEN 1 WHEN d.rsi_14 <= 45 THEN -1 ELSE 0 END
                        ) AS momentum_score
                    FROM daily d
                    INNER JOIN intraday_4h h4 USING (interval_key, instrument_id, trading_date)
                    INNER JOIN intraday_1h h1 USING (interval_key, instrument_id, trading_date)
                    WHERE h4.close IS NOT NULL AND isfinite(h4.close)
                      AND h4.ema_20 IS NOT NULL AND isfinite(h4.ema_20)
                      AND h4.ema_50 IS NOT NULL AND isfinite(h4.ema_50)
                      AND h4.rsi_14 IS NOT NULL AND isfinite(h4.rsi_14)
                      AND h4.macd_hist_12_26_9 IS NOT NULL AND isfinite(h4.macd_hist_12_26_9)
                      AND h4.ema_20_slope_1 IS NOT NULL AND isfinite(h4.ema_20_slope_1)
                      AND h1.close IS NOT NULL AND isfinite(h1.close)
                      AND h1.ema_20 IS NOT NULL AND isfinite(h1.ema_20)
                      AND h1.ema_50 IS NOT NULL AND isfinite(h1.ema_50)
                      AND h1.rsi_14 IS NOT NULL AND isfinite(h1.rsi_14)
                      AND h1.macd_hist_12_26_9 IS NOT NULL AND isfinite(h1.macd_hist_12_26_9)
                      AND h1.ema_20_slope_1 IS NOT NULL AND isfinite(h1.ema_20_slope_1)
                ), dimensions AS (
                    SELECT
                        interval_key,
                        instrument_id,
                        ticker,
                        trading_date,
                        CASE
                            WHEN structure_score >= 4 THEN 'STRONG_UP'
                            WHEN structure_score >= 2 THEN 'UP'
                            WHEN structure_score <= -4 THEN 'STRONG_DOWN'
                            WHEN structure_score <= -2 THEN 'DOWN'
                            ELSE 'MIXED'
                        END AS daily_structure,
                        CASE
                            WHEN score_4h >= 3 AND score_1h >= 3 THEN 'ALIGNED_UP'
                            WHEN score_4h <= -3 AND score_1h <= -3 THEN 'ALIGNED_DOWN'
                            ELSE 'MIXED'
                        END AS short_alignment,
                        CASE
                            WHEN momentum_score >= 2 THEN 'POSITIVE'
                            WHEN momentum_score <= -2 THEN 'NEGATIVE'
                            ELSE 'MIXED'
                        END AS momentum
                    FROM scores
                )
                SELECT
                    *,
                    CASE
                        WHEN daily_structure IN ('UP', 'STRONG_UP') AND short_alignment = 'ALIGNED_DOWN' THEN 'PULLBACK_UP'
                        WHEN daily_structure = 'STRONG_UP' AND short_alignment = 'ALIGNED_UP' AND momentum = 'POSITIVE' THEN 'STRONG_UPTREND'
                        WHEN daily_structure IN ('UP', 'STRONG_UP') THEN 'UPTREND'
                        WHEN daily_structure IN ('DOWN', 'STRONG_DOWN') AND short_alignment = 'ALIGNED_UP' THEN 'BOUNCE_DOWN'
                        WHEN daily_structure = 'STRONG_DOWN' AND short_alignment = 'ALIGNED_DOWN' AND momentum = 'NEGATIVE' THEN 'STRONG_DOWNTREND'
                        WHEN daily_structure IN ('DOWN', 'STRONG_DOWN') THEN 'DOWNTREND'
                        WHEN short_alignment = 'ALIGNED_UP' THEN 'TRANSITION_UP'
                        WHEN short_alignment = 'ALIGNED_DOWN' THEN 'TRANSITION_DOWN'
                        ELSE 'RANGE_MIXED'
                    END AS candidate_state
                FROM dimensions
                ORDER BY interval_key, trading_date
                """
            ).fetch_df()
        finally:
            con.close()

    def _write_parquet(self, frame: pd.DataFrame, target: Path, *, order_by: str) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        con = connect_utc(":memory:")
        try:
            con.register("phase25_gate7_frame", frame)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"COPY (SELECT * FROM phase25_gate7_frame ORDER BY {order_by}) "
                f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
                f"ROW_GROUP_SIZE {row_group_size})"
            )
            promote(temp, target)
        finally:
            con.close()

    def run(self, *, through_date: date) -> dict[str, object]:
        if PHASE25_GATE7_PROVIDER_READS != 0 or PHASE25_GATE7_PROVIDER_WRITES != 0:
            raise Phase25Gate7Error("Gate7 must remain provider-free")
        if PHASE25_GATE7_OPERATIONAL_REGIME_WRITES_ALLOWED:
            raise Phase25Gate7Error("Gate7 may not write operational regime state")
        if PHASE25_GATE7_SECTOR_MAPPING_AUTHORITY:
            raise Phase25Gate7Error("Gate7 may not fabricate sector mapping")
        if not PHASE25_GATE7_STRATEGY_ROUTING_ALLOWED:
            raise Phase25Gate7Error("Gate7 strategy routing authority is unexpectedly disabled")
        if PHASE25_GATE7_STRATEGY_RULE_EVALUATION_ALLOWED or PHASE25_GATE7_STRATEGY_RETURNS_READ_ALLOWED:
            raise Phase25Gate7Error("Gate7 may not evaluate strategy rules or read returns")

        gate6_path, gate6, gate6_validation_path, _, population_path = self._gate6_evidence(
            through_date
        )
        sessions = self._sessions(through_date)
        session_ordinals = {session: index for index, session in enumerate(sessions)}
        population = self._load_population(population_path)
        if population["as_of_date"].min() < PHASE25_ROUTE_REPLAY_ORIGIN:
            raise Phase25Gate7Error("Gate6 population predates accepted replay origin")
        if population["as_of_date"].max() > through_date:
            raise Phase25Gate7Error("Gate6 population exceeds requested through-date")

        market = self._market_states(through_date)
        market_dates = set(market["trading_date"].tolist())
        missing_market = sorted(set(population["as_of_date"].tolist()) - market_dates)
        if missing_market:
            raise Phase25Gate7Error(
                "market regime history is missing candidate sessions: "
                + ", ".join(str(item) for item in missing_market[:20])
            )

        intervals = self._exact_intervals(population=population, sessions=sessions)
        bound = self._bind_population_intervals(population, intervals)
        raw_ticker = self._raw_ticker_state_history(intervals)
        persisted = persist_exact_interval_ticker_states(
            raw_ticker,
            session_ordinals=session_ordinals,
        )
        if not persisted.empty:
            persisted["trading_date"] = pd.to_datetime(persisted["trading_date"]).dt.date

        context = bound.merge(
            market,
            left_on="as_of_date",
            right_on="trading_date",
            how="left",
            validate="many_to_one",
        ).drop(columns=["trading_date"])
        if persisted.empty:
            context["raw_ticker_state"] = None
            context["effective_ticker_state"] = None
            context["persistence_depth"] = 0
        else:
            current_states = persisted[
                [
                    "interval_key",
                    "trading_date",
                    "raw_ticker_state",
                    "effective_ticker_state",
                    "persistence_depth",
                ]
            ].rename(columns={"trading_date": "as_of_date"})
            context = context.merge(
                current_states,
                on=["interval_key", "as_of_date"],
                how="left",
                validate="one_to_one",
            )
            context["persistence_depth"] = (
                pd.to_numeric(context["persistence_depth"], errors="coerce").fillna(0).astype(int)
            )
        if context["market_state"].isna().any():
            raise Phase25Gate7Error("candidate context contains unavailable market state")

        context["contract_version"] = PHASE25_GATE7_CONTEXT_CONTRACT_VERSION
        context["sector_state"] = None
        context = context[
            [
                "contract_version",
                "as_of_date",
                "instrument_id",
                "ticker",
                "effective_state",
                "direction",
                "top_setup",
                "priority_score",
                "market_state",
                "sector_state",
                "raw_ticker_state",
                "effective_ticker_state",
                "persistence_depth",
                "identity_quality",
                "safe_start_date",
                "safe_end_date",
                "interval_key",
            ]
        ].sort_values(["as_of_date", "instrument_id"]).reset_index(drop=True)

        route_records: list[dict[str, object]] = []
        for row in context.itertuples(index=False):
            ticker_state = _optional_text(row.effective_ticker_state)
            routing_context = StrategyRoutingContext(
                instrument_id=str(row.instrument_id),
                ticker=str(row.ticker),
                as_of_date=row.as_of_date,
                discovery_direction=DiscoveryDirection(str(row.direction)),
                market_state=str(row.market_state),
                sector_state=None,
                ticker_state=ticker_state,
            )
            for decision in self.router.route(routing_context):
                route_records.append(
                    {
                        "contract_version": PHASE25_GATE7_ROUTE_CONTRACT_VERSION,
                        "as_of_date": row.as_of_date,
                        "instrument_id": str(row.instrument_id),
                        "ticker": str(row.ticker),
                        "discovery_direction": str(row.direction),
                        "strategy_id": decision.strategy_id,
                        "strategy_family": decision.family.value,
                        "strategy_direction": decision.direction.value,
                        "direction_match": bool(decision.direction_match),
                        "market_state": str(row.market_state),
                        "market_fit": decision.market_fit.value,
                        "sector_state": None,
                        "sector_fit": decision.sector_fit.value,
                        "ticker_state": ticker_state,
                        "ticker_fit": decision.ticker_fit.value,
                        "eligible": bool(decision.eligible),
                    }
                )
        routes = pd.DataFrame.from_records(route_records)
        strategy_count = len(DEFAULT_STRATEGY_REGISTRY.all())
        if len(routes) != len(context) * strategy_count:
            raise Phase25Gate7Error("strategy route decision cardinality mismatch")

        key_columns = ["as_of_date", "instrument_id"]
        market_ok = routes.loc[
            routes["direction_match"] & (routes["market_fit"] != "blocked")
        ][key_columns].drop_duplicates()
        ticker_ok = routes.loc[
            routes["direction_match"]
            & (routes["market_fit"] != "blocked")
            & (routes["ticker_fit"] != "blocked")
        ][key_columns].drop_duplicates()
        eligible = routes.loc[routes["eligible"]][key_columns].drop_duplicates()

        context_path = self.context_path(through_date)
        routes_path = self.routes_path(through_date)
        self._write_parquet(context, context_path, order_by="as_of_date, instrument_id")
        self._write_parquet(
            routes,
            routes_path,
            order_by="as_of_date, instrument_id, strategy_id",
        )

        market_counts = dict(sorted(Counter(context["market_state"].astype(str)).items()))
        ticker_values = [
            _optional_text(value) or "<UNAVAILABLE>"
            for value in context["effective_ticker_state"].tolist()
        ]
        ticker_counts = dict(sorted(Counter(ticker_values).items()))
        identity_counts = dict(sorted(Counter(context["identity_quality"].astype(str)).items()))
        direction_counts = dict(sorted(Counter(context["direction"].astype(str)).items()))
        report_path = self.report_path(through_date)
        report: dict[str, object] = {
            "contract_version": PHASE25_GATE7_REPORT_CONTRACT_VERSION,
            "phase25_gate7_policy_fingerprint": phase25_gate7_policy_fingerprint(),
            "through_date": through_date.isoformat(),
            "replay_origin": PHASE25_ROUTE_REPLAY_ORIGIN.isoformat(),
            "gate6_report_sha256": sha256_file(gate6_path),
            "gate6_validation_sha256": sha256_file(gate6_validation_path),
            "gate6_population_sha256": sha256_file(population_path),
            "gate6_population_rows": int(len(population)),
            "gate6_reconciliation_events": int(gate6.get("reconciliation_event_count", 0)),
            "exact_pit_interval_count": int(len(intervals)),
            "ticker_raw_history_rows": int(len(raw_ticker)),
            "ticker_persisted_history_rows": int(len(persisted)),
            "context_rows": int(len(context)),
            "market_state_counts": market_counts,
            "ticker_state_counts": ticker_counts,
            "identity_quality_counts": identity_counts,
            "discovery_direction_counts": direction_counts,
            "strategy_count": strategy_count,
            "route_decision_rows": int(len(routes)),
            "direction_match_route_rows": int(routes["direction_match"].sum()),
            "market_route_compatible_candidates": int(len(market_ok)),
            "ticker_route_compatible_candidates": int(len(ticker_ok)),
            "fully_route_eligible_candidates": int(len(eligible)),
            "eligible_route_decisions": int(routes["eligible"].sum()),
            "sector_mapping_status": "UNAVAILABLE_NONBLOCKING",
            "context_sha256": sha256_file(context_path),
            "routes_sha256": sha256_file(routes_path),
            "provider_reads": PHASE25_GATE7_PROVIDER_READS,
            "provider_writes": PHASE25_GATE7_PROVIDER_WRITES,
            "operational_regime_writes": 0,
            "strategy_routing_performed": True,
            "strategy_rule_evaluation_performed": False,
            "strategy_returns_read": False,
            "support_replacement_authority": False,
            "broker_reads": PHASE25_BROKER_READS,
            "broker_writes": PHASE25_BROKER_WRITES,
            "order_writes": PHASE25_ORDER_WRITES,
            "paper_submits": PHASE25_PAPER_SUBMITS,
            "live_writes": PHASE25_LIVE_WRITES,
            "phase11_support_writes": PHASE25_PHASE11_SUPPORT_WRITES,
            "protected_strategy_evidence_reads": PHASE25_PROTECTED_STRATEGY_EVIDENCE_READS,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "context_path": str(context_path.resolve()),
            "routes_path": str(routes_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
