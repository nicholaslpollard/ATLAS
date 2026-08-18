from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any, Iterable

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths

from .persistence_probe import confirm_states
from .ticker_history_probe import (
    AUTHORITATIVE_CURRENT_INTERVAL,
    CURRENT_ALIAS_NO_CONFLICT,
    TickerHistoryProbe,
    history_status,
    operational_history_depth,
)
from .ticker_probe import candidate_ticker_state


TICKER_PERSISTENCE_PROBE_CONTRACT_VERSION = (
    "ticker-persistence-probe-v1-safe-history-composite-vs-dimensional-confirmation"
)
TICKER_PERSISTENCE_CONFIRMATION_WINDOWS = (2, 3)
TICKER_PERSISTENCE_MAX_HISTORY_SESSIONS = 252
TICKER_PERSISTENCE_DEPTH_GRID = (2, 5, 20, 60, 126, 252)
TICKER_PERSISTENCE_POLICY_NAMES = (
    "composite_confirm_2",
    "composite_confirm_3",
    "dimensional_confirm_2",
    "dimensional_confirm_3",
)


@dataclass(frozen=True, slots=True)
class TickerPersistenceProbeReport:
    contract_version: str
    generated_at_utc: str
    as_of_date: str
    wall_seconds: float
    probe_status: str
    history_safety_note: str
    gap_policy_note: str
    max_history_sessions: int
    confirmation_windows: tuple[int, ...]
    route_population_count: int
    safe_history_instrument_count: int
    blocked_history_instrument_count: int
    state_observation_count: int
    state_instrument_count: int
    state_depth_counts: dict[str, int]
    raw_state_counts: dict[str, int]
    raw_state_diagnostics: dict[str, float | int | None]
    raw_dimension_diagnostics: dict[str, dict[str, float | int | None]]
    top_raw_transitions: tuple[dict[str, object], ...]
    candidate_policies: dict[str, dict[str, float | int | None]]
    report_path: str


def ticker_state_family(state: str) -> str:
    if state in {"STRONG_UPTREND", "UPTREND", "PULLBACK_UP", "TRANSITION_UP"}:
        return "UP"
    if state in {"STRONG_DOWNTREND", "DOWNTREND", "BOUNCE_DOWN", "TRANSITION_DOWN"}:
        return "DOWN"
    return "MIXED"


def split_contiguous_sequences(
    trading_dates: Iterable[date],
    values: Iterable[str],
    session_ordinals: dict[date, int],
) -> list[list[str]]:
    pairs = list(zip(trading_dates, values, strict=True))
    if not pairs:
        return []
    result: list[list[str]] = []
    current: list[str] = []
    previous_ordinal: int | None = None
    for trading_date, value in pairs:
        ordinal = session_ordinals.get(trading_date)
        if ordinal is None:
            if current:
                result.append(current)
            current = []
            previous_ordinal = None
            continue
        if previous_ordinal is not None and ordinal != previous_ordinal + 1:
            if current:
                result.append(current)
            current = []
        current.append(str(value))
        previous_ordinal = ordinal
    if current:
        result.append(current)
    return result


def _run_lengths(states: list[str]) -> list[int]:
    if not states:
        return []
    lengths: list[int] = []
    current = states[0]
    length = 1
    for state in states[1:]:
        if state == current:
            length += 1
        else:
            lengths.append(length)
            current = state
            length = 1
    lengths.append(length)
    return lengths


def sequence_diagnostics(sequences: Iterable[list[str]]) -> dict[str, float | int | None]:
    observations = 0
    opportunities = 0
    transitions = 0
    flipbacks = 0
    run_lengths: list[int] = []
    instrument_rates: list[float] = []
    one_day_shares: list[float] = []

    for states in sequences:
        if not states:
            continue
        observations += len(states)
        opportunities += max(0, len(states) - 1)
        local_transitions = sum(left != right for left, right in zip(states, states[1:]))
        transitions += local_transitions
        local_runs = _run_lengths(states)
        run_lengths.extend(local_runs)
        flipbacks += sum(
            states[index - 1] == states[index + 1] and states[index] != states[index - 1]
            for index in range(1, len(states) - 1)
        )
        if len(states) > 1:
            instrument_rates.append(local_transitions / (len(states) - 1))
        if local_runs:
            one_day_shares.append(sum(length == 1 for length in local_runs) / len(local_runs))

    run_series = pd.Series(run_lengths, dtype="float64")
    return {
        "observation_count": observations,
        "transition_opportunity_count": opportunities,
        "transition_count": transitions,
        "transition_rate": None if opportunities == 0 else transitions / opportunities,
        "median_sequence_transition_rate": None if not instrument_rates else float(median(instrument_rates)),
        "run_count": len(run_lengths),
        "median_run_length": None if not run_lengths else float(median(run_lengths)),
        "p25_run_length": None if run_series.empty else float(run_series.quantile(0.25)),
        "p75_run_length": None if run_series.empty else float(run_series.quantile(0.75)),
        "one_session_run_share": None if not one_day_shares else sum(one_day_shares) / len(one_day_shares),
        "aba_flipback_count": flipbacks,
        "aba_flipback_per_transition": None if transitions == 0 else flipbacks / transitions,
    }


def agreement_diagnostics(
    raw_sequences: Iterable[list[str]],
    persisted_sequences: Iterable[list[str]],
) -> dict[str, float | int | None]:
    raw_list = list(raw_sequences)
    persisted_list = list(persisted_sequences)
    if len(raw_list) != len(persisted_list):
        raise ValueError("raw and persisted sequence collections must have equal length")
    total = 0
    exact = 0
    family = 0
    opposite = 0
    for raw, persisted in zip(raw_list, persisted_list, strict=True):
        if len(raw) != len(persisted):
            raise ValueError("raw and persisted sequences must align")
        for raw_state, persisted_state in zip(raw, persisted, strict=True):
            total += 1
            if raw_state == persisted_state:
                exact += 1
            raw_family = ticker_state_family(raw_state)
            persisted_family = ticker_state_family(persisted_state)
            if raw_family == persisted_family:
                family += 1
            if {raw_family, persisted_family} == {"UP", "DOWN"}:
                opposite += 1
    return {
        "observation_count": total,
        "exact_agreement_rate": None if total == 0 else exact / total,
        "direction_family_agreement_rate": None if total == 0 else family / total,
        "opposite_direction_mismatch_count": opposite,
        "opposite_direction_mismatch_rate": None if total == 0 else opposite / total,
    }


def dimensional_confirmed_states(
    structures: list[str],
    alignments: list[str],
    momentums: list[str],
    sessions_required: int,
) -> list[str]:
    if not (len(structures) == len(alignments) == len(momentums)):
        raise ValueError("ticker state dimensions must align")
    persisted_structure = confirm_states(structures, sessions_required)
    persisted_alignment = confirm_states(alignments, sessions_required)
    persisted_momentum = confirm_states(momentums, sessions_required)
    return [
        candidate_ticker_state(
            daily_structure=structure,
            short_alignment=alignment,
            momentum=momentum,
        )
        for structure, alignment, momentum in zip(
            persisted_structure,
            persisted_alignment,
            persisted_momentum,
            strict=True,
        )
    ]


def _depth_counts(depths: Iterable[int]) -> dict[str, int]:
    values = pd.Series(list(depths), dtype="int64")
    return {
        f">={threshold}": int((values >= threshold).sum())
        for threshold in TICKER_PERSISTENCE_DEPTH_GRID
    }


class TickerPersistenceProbe:
    """Measure ticker-regime chatter and persistence lag on Gate-9-safe histories."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)

    @staticmethod
    def _safe(path: Path | str) -> str:
        return str(path).replace("\\", "/").replace("'", "''")

    def report_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "regimes" / "ticker_persistence_probe" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def _safe_population(self, as_of_date: date) -> tuple[pd.DataFrame, int]:
        history_probe = TickerHistoryProbe(self.settings)
        paths = history_probe._required_paths(as_of_date)
        con = connect_utc(":memory:")
        try:
            routes = history_probe._prepare_population(con, paths)
            history_probe._prepare_identity(con, paths, as_of_date)
            frame = history_probe._history_depth_frame(con, as_of_date)
        finally:
            con.close()

        statuses: list[str] = []
        depths: list[int] = []
        starts: list[date | None] = []
        for _, row in frame.iterrows():
            status = history_status(
                alias_count=int(row["alias_count"]),
                reuse_identity_count=int(row["reuse_identity_count"]),
                authoritative_current_interval_count=int(row["authoritative_current_interval_count"]),
            )
            interval_depth = int(row["authoritative_interval_depth"])
            raw_depth = int(row["raw_current_alias_depth"])
            depth = operational_history_depth(
                status=status,
                raw_current_alias_depth=raw_depth,
                authoritative_interval_depth=interval_depth,
            )
            statuses.append(status)
            depths.append(depth)
            starts.append(
                pd.Timestamp(row["current_interval_from"]).date()
                if status == AUTHORITATIVE_CURRENT_INTERVAL and pd.notna(row["current_interval_from"])
                else None
            )
        frame = frame.copy()
        frame["history_status"] = statuses
        frame["operational_depth"] = depths
        frame["safe_start_date"] = starts
        safe = frame.loc[
            frame["history_status"].isin({CURRENT_ALIAS_NO_CONFLICT, AUTHORITATIVE_CURRENT_INTERVAL})
            & (frame["operational_depth"] >= 2),
            ["instrument_id", "ticker", "history_status", "operational_depth", "safe_start_date"],
        ].copy()
        safe["safe_start_date"] = pd.to_datetime(safe["safe_start_date"]).dt.date
        return safe, int(routes["population"])

    def _state_frame(self, safe_population: pd.DataFrame, as_of_date: date) -> pd.DataFrame:
        if safe_population.empty:
            return pd.DataFrame(
                columns=["instrument_id", "ticker", "trading_date", "daily_structure", "short_alignment", "momentum", "candidate_state"]
            )

        population = safe_population.copy()
        population["safe_start_date"] = population["safe_start_date"].where(
            population["safe_start_date"].notna(), date(1900, 1, 1)
        )
        con = connect_utc(":memory:")
        try:
            con.register("atlas_ticker_persistence_population", population)
            as_of = as_of_date.isoformat()
            bar_1d = self._safe(self.paths.glob_for_timeframe(Timeframe.DAY_1))
            feat_1d = self._safe(self.paths.feature_glob(Timeframe.DAY_1))
            bar_4h = self._safe(self.paths.glob_for_timeframe(Timeframe.HOUR_4))
            feat_4h = self._safe(self.paths.feature_glob(Timeframe.HOUR_4))
            bar_1h = self._safe(self.paths.glob_for_timeframe(Timeframe.HOUR_1))
            feat_1h = self._safe(self.paths.feature_glob(Timeframe.HOUR_1))

            query = f"""
            WITH daily AS (
                SELECT
                    p.instrument_id,
                    p.ticker,
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
                INNER JOIN atlas_ticker_persistence_population p ON p.ticker = b.symbol
                WHERE b.session_date <= DATE '{as_of}'
                  AND b.session_date >= p.safe_start_date
                  AND b.close IS NOT NULL AND isfinite(b.close)
                  AND f.ema_20 IS NOT NULL AND isfinite(f.ema_20)
                  AND f.ema_50 IS NOT NULL AND isfinite(f.ema_50)
                  AND f.ema_200 IS NOT NULL AND isfinite(f.ema_200)
                  AND f.return_1 IS NOT NULL AND isfinite(f.return_1)
                  AND f.rsi_14 IS NOT NULL AND isfinite(f.rsi_14)
                  AND f.macd_hist_12_26_9 IS NOT NULL AND isfinite(f.macd_hist_12_26_9)
                  AND f.ema_20_slope_1 IS NOT NULL AND isfinite(f.ema_20_slope_1)
            ),
            intraday_4h AS (
                SELECT * EXCLUDE (rn) FROM (
                    SELECT
                        p.instrument_id,
                        b.session_date AS trading_date,
                        b.close,
                        f.ema_20,
                        f.ema_50,
                        f.rsi_14,
                        f.macd_hist_12_26_9,
                        f.ema_20_slope_1,
                        row_number() OVER (
                            PARTITION BY p.instrument_id, b.session_date
                            ORDER BY b.timestamp_utc DESC
                        ) AS rn
                    FROM read_parquet('{bar_4h}', union_by_name=true, hive_partitioning=false) b
                    INNER JOIN read_parquet('{feat_4h}', union_by_name=true, hive_partitioning=false) f
                      ON f.symbol = b.symbol
                     AND f.timestamp_utc = b.timestamp_utc
                     AND f.session_segment = b.session_segment
                    INNER JOIN atlas_ticker_persistence_population p ON p.ticker = b.symbol
                    WHERE b.session_segment = 'regular'
                      AND b.session_date <= DATE '{as_of}'
                      AND b.session_date >= p.safe_start_date
                ) WHERE rn = 1
            ),
            intraday_1h AS (
                SELECT * EXCLUDE (rn) FROM (
                    SELECT
                        p.instrument_id,
                        b.session_date AS trading_date,
                        b.close,
                        f.ema_20,
                        f.ema_50,
                        f.rsi_14,
                        f.macd_hist_12_26_9,
                        f.ema_20_slope_1,
                        row_number() OVER (
                            PARTITION BY p.instrument_id, b.session_date
                            ORDER BY b.timestamp_utc DESC
                        ) AS rn
                    FROM read_parquet('{bar_1h}', union_by_name=true, hive_partitioning=false) b
                    INNER JOIN read_parquet('{feat_1h}', union_by_name=true, hive_partitioning=false) f
                      ON f.symbol = b.symbol
                     AND f.timestamp_utc = b.timestamp_utc
                     AND f.session_segment = b.session_segment
                    INNER JOIN atlas_ticker_persistence_population p ON p.ticker = b.symbol
                    WHERE b.session_segment = 'regular'
                      AND b.session_date <= DATE '{as_of}'
                      AND b.session_date >= p.safe_start_date
                ) WHERE rn = 1
            ),
            scores AS (
                SELECT
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
                INNER JOIN intraday_4h h4 USING (instrument_id, trading_date)
                INNER JOIN intraday_1h h1 USING (instrument_id, trading_date)
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
            ),
            dimensions AS (
                SELECT
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
            ),
            states AS (
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
            )
            SELECT * EXCLUDE (rn) FROM (
                SELECT
                    *,
                    row_number() OVER (
                        PARTITION BY instrument_id ORDER BY trading_date DESC
                    ) AS rn
                FROM states
            )
            WHERE rn <= {TICKER_PERSISTENCE_MAX_HISTORY_SESSIONS}
            ORDER BY instrument_id, trading_date
            """
            return con.execute(query).fetch_df()
        finally:
            con.close()

    def _segments(self, frame: pd.DataFrame) -> list[dict[str, list[str]]]:
        if frame.empty:
            return []
        start_date = pd.to_datetime(frame["trading_date"]).dt.date.min()
        end_date = pd.to_datetime(frame["trading_date"]).dt.date.max()
        sessions = self.calendar.sessions_in_range(start_date, end_date)
        ordinals = {session: index for index, session in enumerate(sessions)}
        segments: list[dict[str, list[str]]] = []
        for _, subset in frame.groupby("instrument_id", sort=True, observed=True):
            data = subset.sort_values("trading_date").reset_index(drop=True)
            dates = pd.to_datetime(data["trading_date"]).dt.date.tolist()
            split_points = [0]
            previous: int | None = None
            for index, trading_date in enumerate(dates):
                ordinal = ordinals.get(trading_date)
                if index > 0 and (ordinal is None or previous is None or ordinal != previous + 1):
                    split_points.append(index)
                previous = ordinal
            split_points.append(len(data))
            for left, right in zip(split_points, split_points[1:], strict=True):
                if right <= left:
                    continue
                piece = data.iloc[left:right]
                segments.append(
                    {
                        "candidate_state": piece["candidate_state"].astype(str).tolist(),
                        "daily_structure": piece["daily_structure"].astype(str).tolist(),
                        "short_alignment": piece["short_alignment"].astype(str).tolist(),
                        "momentum": piece["momentum"].astype(str).tolist(),
                    }
                )
        return segments

    @staticmethod
    def _top_transitions(segments: list[dict[str, list[str]]], limit: int = 20) -> tuple[dict[str, object], ...]:
        counts: Counter[tuple[str, str]] = Counter()
        for segment in segments:
            states = segment["candidate_state"]
            counts.update((left, right) for left, right in zip(states, states[1:]) if left != right)
        return tuple(
            {"from": left, "to": right, "count": int(count)}
            for (left, right), count in counts.most_common(limit)
        )

    def run(self, as_of_date: date) -> TickerPersistenceProbeReport:
        started = perf_counter()
        safe_population, route_population = self._safe_population(as_of_date)
        frame = self._state_frame(safe_population, as_of_date)
        target = self.report_path(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        depth_by_instrument = (
            frame.groupby("instrument_id", observed=True).size().astype(int)
            if not frame.empty
            else pd.Series(dtype="int64")
        )
        segments = self._segments(frame)
        raw_sequences = [segment["candidate_state"] for segment in segments]
        raw_diag = sequence_diagnostics(raw_sequences)

        dimension_diags = {
            dimension: sequence_diagnostics([segment[dimension] for segment in segments])
            for dimension in ("daily_structure", "short_alignment", "momentum")
        }

        raw_transitions = int(raw_diag["transition_count"] or 0)
        candidate_results: dict[str, dict[str, float | int | None]] = {}
        for sessions_required in TICKER_PERSISTENCE_CONFIRMATION_WINDOWS:
            composite_sequences = [
                confirm_states(segment["candidate_state"], sessions_required)
                for segment in segments
            ]
            dimensional_sequences = [
                dimensional_confirmed_states(
                    segment["daily_structure"],
                    segment["short_alignment"],
                    segment["momentum"],
                    sessions_required,
                )
                for segment in segments
            ]
            for policy_name, persisted_sequences in (
                (f"composite_confirm_{sessions_required}", composite_sequences),
                (f"dimensional_confirm_{sessions_required}", dimensional_sequences),
            ):
                diagnostics = sequence_diagnostics(persisted_sequences)
                agreement = agreement_diagnostics(raw_sequences, persisted_sequences)
                transitions = int(diagnostics["transition_count"] or 0)
                candidate_results[policy_name] = {
                    **diagnostics,
                    **agreement,
                    "transition_reduction_rate": (
                        None if raw_transitions == 0 else 1.0 - (transitions / raw_transitions)
                    ),
                }

        state_counts = Counter(frame["candidate_state"].astype(str).tolist()) if not frame.empty else Counter()
        report = TickerPersistenceProbeReport(
            contract_version=TICKER_PERSISTENCE_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            as_of_date=as_of_date.isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            history_safety_note=(
                "Only Gate-9 operationally safe current-alias history is analyzed. Exact authoritative current intervals bound reused/multi-alias tickers; unresolved histories are excluded. No ticker-text splice."
            ),
            gap_policy_note=(
                "Persistence and transition diagnostics reset across missing XNYS sessions; non-consecutive observations are never treated as a confirmation streak."
            ),
            max_history_sessions=TICKER_PERSISTENCE_MAX_HISTORY_SESSIONS,
            confirmation_windows=TICKER_PERSISTENCE_CONFIRMATION_WINDOWS,
            route_population_count=route_population,
            safe_history_instrument_count=int(len(safe_population)),
            blocked_history_instrument_count=int(route_population - len(safe_population)),
            state_observation_count=int(len(frame)),
            state_instrument_count=int(frame["instrument_id"].nunique()) if not frame.empty else 0,
            state_depth_counts=_depth_counts(depth_by_instrument.tolist()),
            raw_state_counts=dict(sorted(state_counts.items())),
            raw_state_diagnostics=raw_diag,
            raw_dimension_diagnostics=dimension_diags,
            top_raw_transitions=self._top_transitions(segments),
            candidate_policies={key: candidate_results[key] for key in sorted(candidate_results)},
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
