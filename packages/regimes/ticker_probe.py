from __future__ import annotations

import json
from collections import Counter, defaultdict
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


TICKER_REGIME_PROBE_CONTRACT_VERSION = (
    "ticker-regime-probe-v1-routed-multitimeframe-identity-history-audit"
)
TICKER_REGIME_REQUIRED_HISTORY_SESSIONS = 252
TICKER_REGIME_TIMEFRAMES = (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1)


@dataclass(frozen=True, slots=True)
class TickerRegimeProbeReport:
    contract_version: str
    as_of_date: str
    generated_at_utc: str
    wall_seconds: float
    probe_status: str
    population_note: str
    identity_note: str
    route_population_count: int
    discovery_count: int
    position_count: int
    watchlist_count: int
    custom_count: int
    duplicate_current_tickers: int
    identity_single_alias_count: int
    identity_multi_alias_count: int
    authoritative_multi_alias_count: int
    current_timeframe_coverage: dict[str, int]
    all_three_timeframe_count: int
    single_alias_history_252_ready_count: int
    single_alias_history_lt252_count: int
    multi_alias_requires_continuity_count: int
    candidate_state_count: int
    candidate_state_counts: dict[str, int]
    daily_structure_counts: dict[str, int]
    short_alignment_counts: dict[str, int]
    momentum_counts: dict[str, int]
    risk_metric_quantiles: dict[str, dict[str, float | None]]
    candidate_state_samples: dict[str, tuple[str, ...]]
    report_path: str


def _relation_vote(left: float, right: float) -> int:
    if left > right:
        return 1
    if left < right:
        return -1
    return 0


def daily_structure_state(score: int) -> str:
    if score >= 4:
        return "STRONG_UP"
    if score >= 2:
        return "UP"
    if score <= -4:
        return "STRONG_DOWN"
    if score <= -2:
        return "DOWN"
    return "MIXED"


def intraday_direction_state(score: int) -> str:
    if score >= 3:
        return "UP"
    if score <= -3:
        return "DOWN"
    return "MIXED"


def short_alignment_state(direction_4h: str, direction_1h: str) -> str:
    if direction_4h == "UP" and direction_1h == "UP":
        return "ALIGNED_UP"
    if direction_4h == "DOWN" and direction_1h == "DOWN":
        return "ALIGNED_DOWN"
    return "MIXED"


def ticker_momentum_state(*, return_1: float, rsi_14: float, macd_hist: float) -> str:
    score = _relation_vote(return_1, 0.0) + _relation_vote(macd_hist, 0.0)
    if rsi_14 >= 55.0:
        score += 1
    elif rsi_14 <= 45.0:
        score -= 1
    if score >= 2:
        return "POSITIVE"
    if score <= -2:
        return "NEGATIVE"
    return "MIXED"


def candidate_ticker_state(
    *,
    daily_structure: str,
    short_alignment: str,
    momentum: str,
) -> str:
    if daily_structure in {"UP", "STRONG_UP"}:
        if short_alignment == "ALIGNED_DOWN":
            return "PULLBACK_UP"
        if (
            daily_structure == "STRONG_UP"
            and short_alignment == "ALIGNED_UP"
            and momentum == "POSITIVE"
        ):
            return "STRONG_UPTREND"
        return "UPTREND"
    if daily_structure in {"DOWN", "STRONG_DOWN"}:
        if short_alignment == "ALIGNED_UP":
            return "BOUNCE_DOWN"
        if (
            daily_structure == "STRONG_DOWN"
            and short_alignment == "ALIGNED_DOWN"
            and momentum == "NEGATIVE"
        ):
            return "STRONG_DOWNTREND"
        return "DOWNTREND"
    if short_alignment == "ALIGNED_UP":
        return "TRANSITION_UP"
    if short_alignment == "ALIGNED_DOWN":
        return "TRANSITION_DOWN"
    return "RANGE_MIXED"


def _quantiles(series: pd.Series) -> dict[str, float | None]:
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return {key: None for key in ("p10", "p25", "p50", "p75", "p90")}
    return {
        "p10": float(numeric.quantile(0.10)),
        "p25": float(numeric.quantile(0.25)),
        "p50": float(numeric.quantile(0.50)),
        "p75": float(numeric.quantile(0.75)),
        "p90": float(numeric.quantile(0.90)),
    }


class TickerRegimeProbe:
    """Inventory identity-safe ticker-regime inputs and candidate current states.

    The probe population is the Phase 8 discovery-state population plus any Phase 7
    POSITION/WATCHLIST/CUSTOM routed instruments. Candidate state labels are diagnostic
    only. Multi-alias identities are measured but their historical symbol series are not
    spliced until authoritative continuity handling is explicitly validated.
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
            "bar_1d": self.paths.canonical_file(Timeframe.DAY_1, as_of_date),
            "feature_1d": self.paths.feature_file(Timeframe.DAY_1, as_of_date),
            "bar_4h": self.paths.derived_file(Timeframe.HOUR_4, as_of_date),
            "feature_4h": self.paths.feature_file(Timeframe.HOUR_4, as_of_date),
            "bar_1h": self.paths.derived_file(Timeframe.HOUR_1, as_of_date),
            "feature_1h": self.paths.feature_file(Timeframe.HOUR_1, as_of_date),
        }
        missing = [f"{name}: {path}" for name, path in result.items() if not path.is_file()]
        if missing:
            raise FileNotFoundError("Ticker regime probe inputs are missing:\n  " + "\n  ".join(missing))
        return result

    def _prepare_population(self, con: Any, paths: dict[str, Path]) -> dict[str, int]:
        universe = self._safe(paths["universe"])
        discovery = self._safe(paths["discovery_state"])
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_ticker_population AS
            WITH u AS (
                SELECT instrument_id, ticker, security_type, routes, discovery_eligible
                FROM read_parquet('{universe}')
            ), d AS (
                SELECT instrument_id, ticker AS discovery_ticker, effective_state, direction, top_setup
                FROM read_parquet('{discovery}')
            )
            SELECT
                u.instrument_id,
                u.ticker,
                u.security_type,
                u.routes,
                u.discovery_eligible,
                d.effective_state AS discovery_state,
                d.direction AS discovery_direction,
                d.top_setup,
                d.instrument_id IS NOT NULL AS in_discovery_state,
                count(*) OVER (PARTITION BY u.ticker) AS current_ticker_identity_count
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
                count(*) FILTER (WHERE list_contains(routes, 'custom')),
                count(DISTINCT ticker) FILTER (WHERE current_ticker_identity_count > 1)
            FROM atlas_ticker_population
            """
        ).fetchone()
        return {
            "population": int(row[0]),
            "discovery": int(row[1]),
            "position": int(row[2]),
            "watchlist": int(row[3]),
            "custom": int(row[4]),
            "duplicate_tickers": int(row[5]),
        }

    def _prepare_identity(self, con: Any) -> tuple[int, int, int]:
        observations = self.paths.ticker_observations_file()
        intervals = self.paths.authoritative_ticker_intervals_file()
        if observations.is_file():
            con.execute(
                f"""
                CREATE TEMP VIEW atlas_alias_counts AS
                SELECT instrument_id, count(DISTINCT ticker) AS alias_count
                FROM read_parquet('{self._safe(observations)}')
                GROUP BY instrument_id
                """
            )
        else:
            con.execute(
                """
                CREATE TEMP VIEW atlas_alias_counts AS
                SELECT instrument_id, 1::BIGINT AS alias_count
                FROM atlas_ticker_population
                """
            )
        if intervals.is_file():
            con.execute(
                f"""
                CREATE TEMP VIEW atlas_authoritative_intervals AS
                SELECT instrument_id, count(*) AS interval_count
                FROM read_parquet('{self._safe(intervals)}')
                GROUP BY instrument_id
                """
            )
        else:
            con.execute(
                """
                CREATE TEMP VIEW atlas_authoritative_intervals AS
                SELECT instrument_id, 0::BIGINT AS interval_count
                FROM atlas_ticker_population
                """
            )
        row = con.execute(
            """
            SELECT
                count(*) FILTER (WHERE coalesce(a.alias_count, 1) <= 1),
                count(*) FILTER (WHERE coalesce(a.alias_count, 1) > 1),
                count(*) FILTER (
                    WHERE coalesce(a.alias_count, 1) > 1
                      AND coalesce(i.interval_count, 0) >= coalesce(a.alias_count, 1)
                )
            FROM atlas_ticker_population p
            LEFT JOIN atlas_alias_counts a USING (instrument_id)
            LEFT JOIN atlas_authoritative_intervals i USING (instrument_id)
            """
        ).fetchone()
        return int(row[0]), int(row[1]), int(row[2])

    def _prepare_current_timeframe(
        self,
        con: Any,
        *,
        timeframe: Timeframe,
        bar_path: Path,
        feature_path: Path,
    ) -> None:
        suffix = timeframe.value.replace("", "")
        view = f"atlas_tf_{suffix}"
        bar = self._safe(bar_path)
        feature = self._safe(feature_path)
        if timeframe == Timeframe.DAY_1:
            con.execute(
                f"""
                CREATE TEMP VIEW {view} AS
                SELECT * EXCLUDE (rn) FROM (
                    SELECT
                        b.symbol,
                        b.timestamp_utc,
                        b.close,
                        f.ema_20,
                        f.ema_50,
                        f.ema_200,
                        f.return_1,
                        f.rsi_14,
                        f.macd_hist_12_26_9,
                        f.ema_20_slope_1,
                        f.natr_14,
                        f.realized_volatility_20,
                        f.directional_efficiency_20,
                        row_number() OVER (PARTITION BY b.symbol ORDER BY b.timestamp_utc DESC) AS rn
                    FROM read_parquet('{bar}') b
                    INNER JOIN read_parquet('{feature}') f
                      ON f.symbol = b.symbol AND f.timestamp_utc = b.timestamp_utc
                ) WHERE rn = 1
                """
            )
            return
        con.execute(
            f"""
            CREATE TEMP VIEW {view} AS
            SELECT * EXCLUDE (rn) FROM (
                SELECT
                    b.symbol,
                    b.timestamp_utc,
                    b.session_segment,
                    b.close,
                    f.ema_20,
                    f.ema_50,
                    f.rsi_14,
                    f.macd_hist_12_26_9,
                    f.ema_20_slope_1,
                    row_number() OVER (PARTITION BY b.symbol ORDER BY b.timestamp_utc DESC) AS rn
                FROM read_parquet('{bar}') b
                INNER JOIN read_parquet('{feature}') f
                  ON f.symbol = b.symbol
                 AND f.timestamp_utc = b.timestamp_utc
                 AND f.session_segment = b.session_segment
                WHERE b.session_segment = 'regular'
            ) WHERE rn = 1
            """
        )

    def _history_counts(self, con: Any, as_of_date: date) -> None:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        con.execute(
            f"""
            CREATE TEMP VIEW atlas_daily_history_counts AS
            SELECT
                f.symbol,
                count(*) FILTER (
                    WHERE f.ema_20 IS NOT NULL AND isfinite(f.ema_20)
                      AND f.ema_50 IS NOT NULL AND isfinite(f.ema_50)
                      AND f.ema_200 IS NOT NULL AND isfinite(f.ema_200)
                      AND f.rsi_14 IS NOT NULL AND isfinite(f.rsi_14)
                      AND f.macd_hist_12_26_9 IS NOT NULL AND isfinite(f.macd_hist_12_26_9)
                      AND f.natr_14 IS NOT NULL AND isfinite(f.natr_14)
                      AND f.realized_volatility_20 IS NOT NULL AND isfinite(f.realized_volatility_20)
                      AND f.directional_efficiency_20 IS NOT NULL AND isfinite(f.directional_efficiency_20)
                ) AS complete_history_sessions
            FROM read_parquet('{feature_glob}', union_by_name=true, hive_partitioning=false) f
            INNER JOIN (
                SELECT DISTINCT ticker
                FROM atlas_ticker_population
                WHERE current_ticker_identity_count = 1
            ) p ON p.ticker = f.symbol
            WHERE CAST(f.timestamp_utc AS DATE) <= ?
            GROUP BY f.symbol
            """,
            [as_of_date],
        )

    def _candidate_frame(self, con: Any) -> pd.DataFrame:
        return con.execute(
            """
            SELECT
                p.instrument_id,
                p.ticker,
                p.security_type,
                p.routes,
                p.in_discovery_state,
                p.discovery_state,
                p.discovery_direction,
                p.top_setup,
                coalesce(a.alias_count, 1) AS alias_count,
                coalesce(i.interval_count, 0) AS authoritative_interval_count,
                coalesce(h.complete_history_sessions, 0) AS complete_history_sessions,
                d.close AS close_1d,
                d.ema_20 AS ema20_1d,
                d.ema_50 AS ema50_1d,
                d.ema_200 AS ema200_1d,
                d.return_1 AS return1_1d,
                d.rsi_14 AS rsi_1d,
                d.macd_hist_12_26_9 AS macd_hist_1d,
                d.ema_20_slope_1 AS ema20_slope_1d,
                d.natr_14 AS natr_1d,
                d.realized_volatility_20 AS realized_vol_1d,
                d.directional_efficiency_20 AS efficiency_1d,
                h4.close AS close_4h,
                h4.ema_20 AS ema20_4h,
                h4.ema_50 AS ema50_4h,
                h4.rsi_14 AS rsi_4h,
                h4.macd_hist_12_26_9 AS macd_hist_4h,
                h4.ema_20_slope_1 AS ema20_slope_4h,
                h1.close AS close_1h,
                h1.ema_20 AS ema20_1h,
                h1.ema_50 AS ema50_1h,
                h1.rsi_14 AS rsi_1h,
                h1.macd_hist_12_26_9 AS macd_hist_1h,
                h1.ema_20_slope_1 AS ema20_slope_1h
            FROM atlas_ticker_population p
            LEFT JOIN atlas_alias_counts a USING (instrument_id)
            LEFT JOIN atlas_authoritative_intervals i USING (instrument_id)
            LEFT JOIN atlas_daily_history_counts h ON h.symbol = p.ticker
            LEFT JOIN atlas_tf_1d d ON d.symbol = p.ticker
            LEFT JOIN atlas_tf_4h h4 ON h4.symbol = p.ticker
            LEFT JOIN atlas_tf_1h h1 ON h1.symbol = p.ticker
            WHERE p.current_ticker_identity_count = 1
            ORDER BY p.instrument_id
            """
        ).fetch_df()

    @staticmethod
    def _complete(frame: pd.DataFrame, columns: tuple[str, ...]) -> pd.Series:
        return frame.loc[:, list(columns)].notna().all(axis=1)

    def run(self, as_of_date: date) -> TickerRegimeProbeReport:
        started = perf_counter()
        paths = self._required_paths(as_of_date)
        target = self.paths.ticker_regime_probe_report(as_of_date)
        target.parent.mkdir(parents=True, exist_ok=True)

        con = connect_utc(":memory:")
        try:
            route_counts = self._prepare_population(con, paths)
            single_alias_count, multi_alias_count, authoritative_multi_alias_count = self._prepare_identity(con)
            self._prepare_current_timeframe(
                con,
                timeframe=Timeframe.DAY_1,
                bar_path=paths["bar_1d"],
                feature_path=paths["feature_1d"],
            )
            self._prepare_current_timeframe(
                con,
                timeframe=Timeframe.HOUR_4,
                bar_path=paths["bar_4h"],
                feature_path=paths["feature_4h"],
            )
            self._prepare_current_timeframe(
                con,
                timeframe=Timeframe.HOUR_1,
                bar_path=paths["bar_1h"],
                feature_path=paths["feature_1h"],
            )
            self._history_counts(con, as_of_date)
            frame = self._candidate_frame(con)
            coverage_row = con.execute(
                """
                SELECT
                    count(*) FILTER (WHERE d.symbol IS NOT NULL),
                    count(*) FILTER (WHERE h4.symbol IS NOT NULL),
                    count(*) FILTER (WHERE h1.symbol IS NOT NULL),
                    count(*) FILTER (
                        WHERE d.symbol IS NOT NULL AND h4.symbol IS NOT NULL AND h1.symbol IS NOT NULL
                    )
                FROM atlas_ticker_population p
                LEFT JOIN atlas_tf_1d d ON d.symbol = p.ticker
                LEFT JOIN atlas_tf_4h h4 ON h4.symbol = p.ticker
                LEFT JOIN atlas_tf_1h h1 ON h1.symbol = p.ticker
                WHERE p.current_ticker_identity_count = 1
                """
            ).fetchone()
        finally:
            con.close()

        coverage = {
            "1d": int(coverage_row[0]),
            "4h_regular": int(coverage_row[1]),
            "1h_regular": int(coverage_row[2]),
        }
        all_three = int(coverage_row[3])

        daily_cols = (
            "close_1d",
            "ema20_1d",
            "ema50_1d",
            "ema200_1d",
            "return1_1d",
            "rsi_1d",
            "macd_hist_1d",
            "ema20_slope_1d",
            "natr_1d",
            "realized_vol_1d",
            "efficiency_1d",
        )
        h4_cols = ("close_4h", "ema20_4h", "ema50_4h", "rsi_4h", "macd_hist_4h", "ema20_slope_4h")
        h1_cols = ("close_1h", "ema20_1h", "ema50_1h", "rsi_1h", "macd_hist_1h", "ema20_slope_1h")
        complete = self._complete(frame, daily_cols + h4_cols + h1_cols)
        candidates = frame.loc[complete].copy()

        state_counts: Counter[str] = Counter()
        structure_counts: Counter[str] = Counter()
        alignment_counts: Counter[str] = Counter()
        momentum_counts: Counter[str] = Counter()
        samples: dict[str, list[str]] = defaultdict(list)

        for _, row in candidates.iterrows():
            structure_score = sum(
                (
                    _relation_vote(float(row["close_1d"]), float(row["ema20_1d"])),
                    _relation_vote(float(row["close_1d"]), float(row["ema50_1d"])),
                    _relation_vote(float(row["close_1d"]), float(row["ema200_1d"])),
                    _relation_vote(float(row["ema20_1d"]), float(row["ema50_1d"])),
                    _relation_vote(float(row["ema50_1d"]), float(row["ema200_1d"])),
                    _relation_vote(float(row["ema20_slope_1d"]), 0.0),
                )
            )
            structure = daily_structure_state(structure_score)

            score_4h = sum(
                (
                    _relation_vote(float(row["close_4h"]), float(row["ema20_4h"])),
                    _relation_vote(float(row["close_4h"]), float(row["ema50_4h"])),
                    _relation_vote(float(row["rsi_4h"]), 50.0),
                    _relation_vote(float(row["macd_hist_4h"]), 0.0),
                    _relation_vote(float(row["ema20_slope_4h"]), 0.0),
                )
            )
            score_1h = sum(
                (
                    _relation_vote(float(row["close_1h"]), float(row["ema20_1h"])),
                    _relation_vote(float(row["close_1h"]), float(row["ema50_1h"])),
                    _relation_vote(float(row["rsi_1h"]), 50.0),
                    _relation_vote(float(row["macd_hist_1h"]), 0.0),
                    _relation_vote(float(row["ema20_slope_1h"]), 0.0),
                )
            )
            direction_4h = intraday_direction_state(score_4h)
            direction_1h = intraday_direction_state(score_1h)
            alignment = short_alignment_state(direction_4h, direction_1h)
            momentum = ticker_momentum_state(
                return_1=float(row["return1_1d"]),
                rsi_14=float(row["rsi_1d"]),
                macd_hist=float(row["macd_hist_1d"]),
            )
            state = candidate_ticker_state(
                daily_structure=structure,
                short_alignment=alignment,
                momentum=momentum,
            )
            structure_counts.update([structure])
            alignment_counts.update([alignment])
            momentum_counts.update([momentum])
            state_counts.update([state])
            if len(samples[state]) < 10:
                samples[state].append(str(row["ticker"]))

        single_alias = frame.loc[pd.to_numeric(frame["alias_count"], errors="coerce").fillna(1) <= 1]
        ready_252 = int(
            (pd.to_numeric(single_alias["complete_history_sessions"], errors="coerce").fillna(0) >= TICKER_REGIME_REQUIRED_HISTORY_SESSIONS).sum()
        )
        lt_252 = int(len(single_alias) - ready_252)

        risk_quantiles = {
            "natr_14": _quantiles(candidates["natr_1d"]),
            "realized_volatility_20": _quantiles(candidates["realized_vol_1d"]),
            "directional_efficiency_20": _quantiles(candidates["efficiency_1d"]),
        }

        report = TickerRegimeProbeReport(
            contract_version=TICKER_REGIME_PROBE_CONTRACT_VERSION,
            as_of_date=as_of_date.isoformat(),
            generated_at_utc=datetime.now(UTC).isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="EVIDENCE_ONLY",
            population_note=(
                "Phase 8 discovery-state instruments plus Phase 7 POSITION/WATCHLIST/CUSTOM routed overrides."
            ),
            identity_note=(
                "Candidate current states use exact current ticker facts. Multi-alias instrument histories are measured but not spliced until authoritative continuity is validated."
            ),
            route_population_count=route_counts["population"],
            discovery_count=route_counts["discovery"],
            position_count=route_counts["position"],
            watchlist_count=route_counts["watchlist"],
            custom_count=route_counts["custom"],
            duplicate_current_tickers=route_counts["duplicate_tickers"],
            identity_single_alias_count=single_alias_count,
            identity_multi_alias_count=multi_alias_count,
            authoritative_multi_alias_count=authoritative_multi_alias_count,
            current_timeframe_coverage=coverage,
            all_three_timeframe_count=all_three,
            single_alias_history_252_ready_count=ready_252,
            single_alias_history_lt252_count=lt_252,
            multi_alias_requires_continuity_count=multi_alias_count,
            candidate_state_count=int(len(candidates)),
            candidate_state_counts=dict(sorted(state_counts.items())),
            daily_structure_counts=dict(sorted(structure_counts.items())),
            short_alignment_counts=dict(sorted(alignment_counts.items())),
            momentum_counts=dict(sorted(momentum_counts.items())),
            risk_metric_quantiles=risk_quantiles,
            candidate_state_samples={key: tuple(value) for key, value in sorted(samples.items())},
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
