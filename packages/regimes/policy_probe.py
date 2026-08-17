from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from statistics import median
from time import perf_counter

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .calibration import (
    BASKET_METRICS,
    BREADTH_METRICS,
    PROXY_METRICS,
    REGIME_CALIBRATION_CONTRACT_VERSION,
    RegimeCalibration,
    basket_daily,
    metric_quantiles,
)
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS


REGIME_POLICY_PROBE_CONTRACT_VERSION = (
    "regime-policy-probe-v1-quartile-dimensional-no-hysteresis"
)
MARKET_STRUCTURE_METRICS = (
    "close_above_ema_50",
    "close_above_ema_200",
    "ema_20_above_ema_50",
    "ema_50_above_ema_200",
)
MARKET_CONTINUOUS_STRUCTURE_METRICS = (
    "median_price_distance_ema_20",
    "median_ema_20_slope_1",
)
MARKET_MOMENTUM_BREADTH_METRICS = (
    "rsi_above_50",
    "macd_hist_positive",
)


@dataclass(frozen=True, slots=True)
class RegimePolicyProbeReport:
    contract_version: str
    calibration_contract_version: str
    generated_at_utc: str
    start_date: str
    end_date: str
    wall_seconds: float
    policy_status: str
    threshold_basis_note: str
    hysteresis_note: str
    market_session_count: int
    market_state_counts: dict[str, int]
    market_state_percentages: dict[str, float]
    market_dimension_counts: dict[str, dict[str, int]]
    market_transition_diagnostics: dict[str, float | int | None]
    end_date_market_state: dict[str, str | int | float | None]
    sector_observation_count: int
    sector_state_counts: dict[str, int]
    sector_state_percentages: dict[str, float]
    sector_transition_diagnostics: dict[str, dict[str, float | int | None]]
    end_date_sector_states: dict[str, dict[str, str | int | float | None]]
    report_path: str


def quartile_vote(value: float, summary: dict[str, float | None]) -> int:
    p25 = summary.get("p25")
    p75 = summary.get("p75")
    if pd.isna(value) or p25 is None or p75 is None:
        return 0
    if value <= p25:
        return -1
    if value >= p75:
        return 1
    return 0


def market_structure_state(score: int) -> str:
    if score >= 4:
        return "STRONG_UP"
    if score >= 2:
        return "UP"
    if score <= -4:
        return "STRONG_DOWN"
    if score <= -2:
        return "DOWN"
    return "MIXED"


def sector_structure_state(score: int) -> str:
    if score >= 3:
        return "STRONG_UP"
    if score >= 1:
        return "UP"
    if score <= -3:
        return "STRONG_DOWN"
    if score <= -1:
        return "DOWN"
    return "MIXED"


def momentum_state(score: int) -> str:
    if score >= 2:
        return "STRONG_POSITIVE"
    if score >= 1:
        return "POSITIVE"
    if score <= -2:
        return "STRONG_NEGATIVE"
    if score <= -1:
        return "NEGATIVE"
    return "MIXED"


def participation_state(value: float, summary: dict[str, float | None]) -> str:
    vote = quartile_vote(value, summary)
    if vote > 0:
        return "BROAD_POSITIVE"
    if vote < 0:
        return "BROAD_NEGATIVE"
    return "MIXED"


def volatility_state(
    natr_value: float,
    realized_volatility_value: float,
    natr_summary: dict[str, float | None],
    realized_volatility_summary: dict[str, float | None],
) -> str:
    values = (
        (natr_value, natr_summary),
        (realized_volatility_value, realized_volatility_summary),
    )
    if any(
        summary.get("p90") is not None and value >= float(summary["p90"])
        for value, summary in values
    ):
        return "STRESSED"
    if any(
        summary.get("p75") is not None and value >= float(summary["p75"])
        for value, summary in values
    ):
        return "ELEVATED"
    if all(
        summary.get("p25") is not None and value <= float(summary["p25"])
        for value, summary in values
    ):
        return "CALM"
    return "NORMAL"


def efficiency_state(value: float, summary: dict[str, float | None]) -> str:
    vote = quartile_vote(value, summary)
    if vote > 0:
        return "HIGH"
    if vote < 0:
        return "LOW"
    return "NORMAL"


def composite_market_state(structure: str, momentum: str, participation: str) -> str:
    positive = {"POSITIVE", "STRONG_POSITIVE"}
    negative = {"NEGATIVE", "STRONG_NEGATIVE"}
    if structure == "STRONG_UP" and momentum in positive and participation != "BROAD_NEGATIVE":
        return "STRONG_BULL"
    if structure in {"UP", "STRONG_UP"} and momentum not in negative:
        return "BULL"
    if structure == "STRONG_DOWN" and momentum in negative and participation != "BROAD_POSITIVE":
        return "STRONG_BEAR"
    if structure in {"DOWN", "STRONG_DOWN"} and momentum not in positive:
        return "BEAR"
    return "MIXED"


def composite_sector_state(structure: str, momentum: str) -> str:
    positive = {"POSITIVE", "STRONG_POSITIVE"}
    negative = {"NEGATIVE", "STRONG_NEGATIVE"}
    if structure == "STRONG_UP" and momentum in positive:
        return "STRONG_BULL"
    if structure in {"UP", "STRONG_UP"} and momentum not in negative:
        return "BULL"
    if structure == "STRONG_DOWN" and momentum in negative:
        return "STRONG_BEAR"
    if structure in {"DOWN", "STRONG_DOWN"} and momentum not in positive:
        return "BEAR"
    return "MIXED"


def run_diagnostics(states: list[str]) -> dict[str, float | int | None]:
    if not states:
        return {
            "observation_count": 0,
            "transition_count": 0,
            "transition_rate": None,
            "run_count": 0,
            "median_run_length": None,
            "one_day_run_count": 0,
            "one_day_run_share": None,
        }
    run_lengths: list[int] = []
    current = states[0]
    length = 1
    for state in states[1:]:
        if state == current:
            length += 1
        else:
            run_lengths.append(length)
            current = state
            length = 1
    run_lengths.append(length)
    transitions = len(run_lengths) - 1
    one_day_runs = sum(length == 1 for length in run_lengths)
    denominator = len(states) - 1
    return {
        "observation_count": len(states),
        "transition_count": transitions,
        "transition_rate": None if denominator <= 0 else transitions / denominator,
        "run_count": len(run_lengths),
        "median_run_length": float(median(run_lengths)),
        "one_day_run_count": one_day_runs,
        "one_day_run_share": one_day_runs / len(run_lengths),
    }


def _counts(values: pd.Series) -> dict[str, int]:
    if values.empty:
        return {}
    counts = values.value_counts().sort_index()
    return {str(key): int(value) for key, value in counts.items()}


def _percentages(counts: dict[str, int], total: int) -> dict[str, float]:
    return {key: (0.0 if total <= 0 else value / total) for key, value in counts.items()}


def _market_daily_states(breadth: pd.DataFrame, market_basket: pd.DataFrame) -> pd.DataFrame:
    breadth_data = breadth.copy()
    basket_data = market_basket.copy()
    breadth_data["trading_date"] = pd.to_datetime(breadth_data["trading_date"]).dt.date
    basket_data["trading_date"] = pd.to_datetime(basket_data["trading_date"]).dt.date
    breadth_quantiles = metric_quantiles(breadth_data, BREADTH_METRICS)
    basket_quantiles = metric_quantiles(basket_data, BASKET_METRICS)
    joined = breadth_data.merge(
        basket_data,
        on="trading_date",
        how="inner",
        validate="one_to_one",
    )
    rows: list[dict[str, object]] = []
    for _, row in joined.iterrows():
        structure_score = sum(
            quartile_vote(float(row[metric]), breadth_quantiles[metric])
            for metric in MARKET_STRUCTURE_METRICS
        ) + sum(
            quartile_vote(float(row[metric]), basket_quantiles[metric])
            for metric in MARKET_CONTINUOUS_STRUCTURE_METRICS
        )
        momentum_score = sum(
            quartile_vote(float(row[metric]), breadth_quantiles[metric])
            for metric in MARKET_MOMENTUM_BREADTH_METRICS
        ) + quartile_vote(float(row["median_rsi_14"]), basket_quantiles["median_rsi_14"])
        structure = market_structure_state(structure_score)
        momentum = momentum_state(momentum_score)
        participation = participation_state(
            float(row["positive_return_1"]),
            breadth_quantiles["positive_return_1"],
        )
        volatility = volatility_state(
            float(row["median_natr_14"]),
            float(row["median_realized_volatility_20"]),
            basket_quantiles["median_natr_14"],
            basket_quantiles["median_realized_volatility_20"],
        )
        efficiency = efficiency_state(
            float(row["median_directional_efficiency_20"]),
            basket_quantiles["median_directional_efficiency_20"],
        )
        rows.append(
            {
                "trading_date": row["trading_date"],
                "structure_score": structure_score,
                "structure": structure,
                "momentum_score": momentum_score,
                "momentum": momentum,
                "participation": participation,
                "volatility": volatility,
                "efficiency": efficiency,
                "composite": composite_market_state(structure, momentum, participation),
            }
        )
    return pd.DataFrame(rows)


def _sector_daily_states(sector_frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in SECTOR_PROXY_TICKERS:
        subset = sector_frame.loc[sector_frame["symbol"] == ticker].copy()
        if subset.empty:
            continue
        quantiles = metric_quantiles(subset, PROXY_METRICS)
        for _, row in subset.iterrows():
            structure_score = (
                (1 if float(row["close"]) > float(row["ema_50"]) else -1)
                + (1 if float(row["close"]) > float(row["ema_200"]) else -1)
                + quartile_vote(float(row["price_distance_ema_20"]), quantiles["price_distance_ema_20"])
                + quartile_vote(float(row["ema_20_slope_1"]), quantiles["ema_20_slope_1"])
            )
            momentum_score = (
                quartile_vote(float(row["return_1"]), quantiles["return_1"])
                + quartile_vote(float(row["rsi_14"]), quantiles["rsi_14"])
                + (1 if float(row["macd_hist_12_26_9"]) > 0.0 else -1)
            )
            structure = sector_structure_state(structure_score)
            momentum = momentum_state(momentum_score)
            rows.append(
                {
                    "trading_date": row["trading_date"],
                    "symbol": ticker,
                    "structure_score": structure_score,
                    "structure": structure,
                    "momentum_score": momentum_score,
                    "momentum": momentum,
                    "volatility": volatility_state(
                        float(row["natr_14"]),
                        float(row["realized_volatility_20"]),
                        quantiles["natr_14"],
                        quantiles["realized_volatility_20"],
                    ),
                    "efficiency": efficiency_state(
                        float(row["directional_efficiency_20"]),
                        quantiles["directional_efficiency_20"],
                    ),
                    "composite": composite_sector_state(structure, momentum),
                }
            )
    return pd.DataFrame(rows)


def _snapshot(row: pd.Series) -> dict[str, str | int | float | None]:
    return {
        "trading_date": str(pd.Timestamp(row["trading_date"]).date()),
        "structure_score": int(row["structure_score"]),
        "structure": str(row["structure"]),
        "momentum_score": int(row["momentum_score"]),
        "momentum": str(row["momentum"]),
        "participation": None if "participation" not in row.index else str(row["participation"]),
        "volatility": str(row["volatility"]),
        "efficiency": str(row["efficiency"]),
        "composite": str(row["composite"]),
    }


class RegimePolicyProbe:
    """Measure candidate state balance/chatter before production policy is locked.

    Full-window p25/p75 thresholds make this intentionally retrospective. The probe is
    not a point-in-time performance backtest; it is a raw state-frequency and stability
    diagnostic. Hysteresis is deliberately absent so any chatter remains visible.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calibration = RegimeCalibration(settings)
        self.paths = self.calibration.paths

    def build(self, start_date: date, end_date: date) -> RegimePolicyProbeReport:
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        started = perf_counter()
        breadth = self.calibration._breadth_daily(start_date, end_date)
        proxies = self.calibration._proxy_frame(start_date, end_date)
        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        market_states = _market_daily_states(breadth, basket_daily(market_frame))
        sector_states = _sector_daily_states(sector_frame)
        if market_states.empty:
            raise ValueError("candidate policy probe produced no market states")
        if sector_states.empty:
            raise ValueError("candidate policy probe produced no sector states")

        market_counts = _counts(market_states["composite"])
        market_dimension_counts = {
            dimension: _counts(market_states[dimension])
            for dimension in ("structure", "momentum", "participation", "volatility", "efficiency")
        }
        sector_counts = _counts(sector_states["composite"])
        sector_transition: dict[str, dict[str, float | int | None]] = {}
        end_sector: dict[str, dict[str, str | int | float | None]] = {}
        for ticker in SECTOR_PROXY_TICKERS:
            subset = sector_states.loc[sector_states["symbol"] == ticker].sort_values("trading_date")
            if subset.empty:
                continue
            sector_transition[ticker] = run_diagnostics(subset["composite"].tolist())
            end_sector[ticker] = _snapshot(subset.iloc[-1])

        target = self.paths.regime_policy_probe_report(end_date)
        report = RegimePolicyProbeReport(
            contract_version=REGIME_POLICY_PROBE_CONTRACT_VERSION,
            calibration_contract_version=REGIME_CALIBRATION_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            policy_status="CANDIDATE_ONLY",
            threshold_basis_note=(
                "Retrospective full-window p25/p75 bands measure state balance and raw transition behavior only; "
                "they are not point-in-time performance evidence or production thresholds."
            ),
            hysteresis_note="NONE; raw no-hysteresis stability baseline",
            market_session_count=int(len(market_states)),
            market_state_counts=market_counts,
            market_state_percentages=_percentages(market_counts, len(market_states)),
            market_dimension_counts=market_dimension_counts,
            market_transition_diagnostics=run_diagnostics(market_states["composite"].tolist()),
            end_date_market_state=_snapshot(market_states.iloc[-1]),
            sector_observation_count=int(len(sector_states)),
            sector_state_counts=sector_counts,
            sector_state_percentages=_percentages(sector_counts, len(sector_states)),
            sector_transition_diagnostics=sector_transition,
            end_date_sector_states=end_sector,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
