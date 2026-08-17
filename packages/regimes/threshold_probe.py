from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from time import perf_counter

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .calibration import BASKET_METRICS, BREADTH_METRICS, PROXY_METRICS, RegimeCalibration, basket_daily
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS
from .persistence_probe import (
    REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION,
    agreement_diagnostics,
    persist_market_states,
    persist_sector_states,
    _sector_agreement,
    _transition_summary,
)
from .policy_probe import (
    MARKET_CONTINUOUS_STRUCTURE_METRICS,
    MARKET_MOMENTUM_BREADTH_METRICS,
    MARKET_STRUCTURE_METRICS,
    _counts,
    _market_daily_states,
    _percentages,
    _sector_daily_states,
    composite_market_state,
    composite_sector_state,
    efficiency_state,
    market_structure_state,
    momentum_state,
    participation_state,
    quartile_vote,
    run_diagnostics,
    sector_structure_state,
    volatility_state,
)


REGIME_THRESHOLD_PROBE_CONTRACT_VERSION = (
    "regime-threshold-probe-v1-prior-only-252-policy-grid"
)
REGIME_THRESHOLD_TRAINING_SESSIONS = 252
REGIME_THRESHOLD_POLICY_NAMES = (
    "frozen_252",
    "expanding_252",
    "rolling_252",
)
REGIME_SELECTED_CONFIRMATION_SESSIONS = 2

MARKET_THRESHOLD_METRICS = tuple(
    dict.fromkeys(
        MARKET_STRUCTURE_METRICS
        + MARKET_CONTINUOUS_STRUCTURE_METRICS
        + MARKET_MOMENTUM_BREADTH_METRICS
        + (
            "median_rsi_14",
            "positive_return_1",
            "median_natr_14",
            "median_realized_volatility_20",
            "median_directional_efficiency_20",
        )
    )
)
MARKET_THRESHOLD_SNAPSHOT_METRICS = (
    "close_above_ema_50",
    "close_above_ema_200",
    "median_price_distance_ema_20",
    "median_ema_20_slope_1",
    "median_natr_14",
)
SECTOR_THRESHOLD_METRICS = (
    "return_1",
    "price_distance_ema_20",
    "ema_20_slope_1",
    "rsi_14",
    "natr_14",
    "realized_volatility_20",
    "directional_efficiency_20",
)


@dataclass(frozen=True, slots=True)
class RegimeThresholdProbeReport:
    contract_version: str
    persistence_probe_contract_version: str
    generated_at_utc: str
    start_date: str
    end_date: str
    wall_seconds: float
    probe_status: str
    point_in_time_note: str
    selected_confirmation_sessions: int
    training_sessions: int
    policy_names: tuple[str, ...]
    evaluation_session_count: int
    first_evaluation_date: str
    last_evaluation_date: str
    market_candidates: dict[str, dict[str, object]]
    sector_evaluation_observation_count: int
    sector_candidates: dict[str, dict[str, object]]
    report_path: str


def threshold_series(series: pd.Series, policy_name: str, quantile: float) -> pd.Series:
    """Return prior-only threshold values aligned to each current observation.

    All policies require the same 252-session seed history. The current observation is
    never included in its own threshold calculation.
    """

    if policy_name not in REGIME_THRESHOLD_POLICY_NAMES:
        raise ValueError(f"unknown threshold policy: {policy_name}")
    numeric = pd.to_numeric(series, errors="coerce")
    if policy_name == "frozen_252":
        if len(numeric) < REGIME_THRESHOLD_TRAINING_SESSIONS:
            return pd.Series(float("nan"), index=numeric.index, dtype="float64")
        value = float(numeric.iloc[:REGIME_THRESHOLD_TRAINING_SESSIONS].quantile(quantile))
        result = pd.Series(value, index=numeric.index, dtype="float64")
        result.iloc[:REGIME_THRESHOLD_TRAINING_SESSIONS] = float("nan")
        return result
    prior = numeric.shift(1)
    if policy_name == "expanding_252":
        return prior.expanding(min_periods=REGIME_THRESHOLD_TRAINING_SESSIONS).quantile(quantile)
    return prior.rolling(
        window=REGIME_THRESHOLD_TRAINING_SESSIONS,
        min_periods=REGIME_THRESHOLD_TRAINING_SESSIONS,
    ).quantile(quantile)


def _attach_thresholds(
    frame: pd.DataFrame,
    metrics: tuple[str, ...],
    policy_name: str,
) -> pd.DataFrame:
    data = frame.copy()
    for metric in metrics:
        data[f"{metric}__p25"] = threshold_series(data[metric], policy_name, 0.25)
        data[f"{metric}__p75"] = threshold_series(data[metric], policy_name, 0.75)
        if metric in {"median_natr_14", "median_realized_volatility_20", "natr_14", "realized_volatility_20"}:
            data[f"{metric}__p90"] = threshold_series(data[metric], policy_name, 0.90)
    return data


def _summary_from_row(row: pd.Series, metric: str) -> dict[str, float | None]:
    result: dict[str, float | None] = {
        "p25": None if pd.isna(row[f"{metric}__p25"]) else float(row[f"{metric}__p25"]),
        "p75": None if pd.isna(row[f"{metric}__p75"]) else float(row[f"{metric}__p75"]),
    }
    p90_key = f"{metric}__p90"
    if p90_key in row.index:
        result["p90"] = None if pd.isna(row[p90_key]) else float(row[p90_key])
    return result


def _market_point_in_time_states(
    breadth: pd.DataFrame,
    market_basket: pd.DataFrame,
    policy_name: str,
) -> pd.DataFrame:
    breadth_data = breadth.copy()
    basket_data = market_basket.copy()
    breadth_data["trading_date"] = pd.to_datetime(breadth_data["trading_date"]).dt.date
    basket_data["trading_date"] = pd.to_datetime(basket_data["trading_date"]).dt.date
    joined = breadth_data.merge(basket_data, on="trading_date", how="inner", validate="one_to_one")
    joined = joined.sort_values("trading_date").reset_index(drop=True)
    joined = _attach_thresholds(joined, MARKET_THRESHOLD_METRICS, policy_name)
    required = [f"{metric}__p25" for metric in MARKET_THRESHOLD_METRICS]
    data = joined.dropna(subset=required).reset_index(drop=True)
    rows: list[dict[str, object]] = []
    for _, row in data.iterrows():
        structure_score = sum(
            quartile_vote(float(row[metric]), _summary_from_row(row, metric))
            for metric in MARKET_STRUCTURE_METRICS
        ) + sum(
            quartile_vote(float(row[metric]), _summary_from_row(row, metric))
            for metric in MARKET_CONTINUOUS_STRUCTURE_METRICS
        )
        momentum_score = sum(
            quartile_vote(float(row[metric]), _summary_from_row(row, metric))
            for metric in MARKET_MOMENTUM_BREADTH_METRICS
        ) + quartile_vote(
            float(row["median_rsi_14"]),
            _summary_from_row(row, "median_rsi_14"),
        )
        structure = market_structure_state(structure_score)
        momentum = momentum_state(momentum_score)
        participation = participation_state(
            float(row["positive_return_1"]),
            _summary_from_row(row, "positive_return_1"),
        )
        volatility = volatility_state(
            float(row["median_natr_14"]),
            float(row["median_realized_volatility_20"]),
            _summary_from_row(row, "median_natr_14"),
            _summary_from_row(row, "median_realized_volatility_20"),
        )
        efficiency = efficiency_state(
            float(row["median_directional_efficiency_20"]),
            _summary_from_row(row, "median_directional_efficiency_20"),
        )
        result: dict[str, object] = {
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
        for metric in MARKET_THRESHOLD_SNAPSHOT_METRICS:
            for quantile in ("p25", "p75", "p90"):
                key = f"{metric}__{quantile}"
                if key in row.index and not pd.isna(row[key]):
                    result[key] = float(row[key])
        rows.append(result)
    return pd.DataFrame(rows)


def _sector_point_in_time_states(
    sector_frame: pd.DataFrame,
    policy_name: str,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for ticker in SECTOR_PROXY_TICKERS:
        subset = sector_frame.loc[sector_frame["symbol"] == ticker].sort_values("trading_date").reset_index(drop=True).copy()
        if subset.empty:
            continue
        data = _attach_thresholds(subset, SECTOR_THRESHOLD_METRICS, policy_name)
        required = [f"{metric}__p25" for metric in SECTOR_THRESHOLD_METRICS]
        data = data.dropna(subset=required).reset_index(drop=True)
        for _, row in data.iterrows():
            structure_score = (
                (1 if float(row["close"]) > float(row["ema_50"]) else -1)
                + (1 if float(row["close"]) > float(row["ema_200"]) else -1)
                + quartile_vote(
                    float(row["price_distance_ema_20"]),
                    _summary_from_row(row, "price_distance_ema_20"),
                )
                + quartile_vote(
                    float(row["ema_20_slope_1"]),
                    _summary_from_row(row, "ema_20_slope_1"),
                )
            )
            momentum_score = (
                quartile_vote(float(row["return_1"]), _summary_from_row(row, "return_1"))
                + quartile_vote(float(row["rsi_14"]), _summary_from_row(row, "rsi_14"))
                + (1 if float(row["macd_hist_12_26_9"]) > 0.0 else -1)
            )
            structure = sector_structure_state(structure_score)
            momentum = momentum_state(momentum_score)
            rows.append(
                {
                    "trading_date": pd.Timestamp(row["trading_date"]).date(),
                    "symbol": ticker,
                    "structure_score": structure_score,
                    "structure": structure,
                    "momentum_score": momentum_score,
                    "momentum": momentum,
                    "volatility": volatility_state(
                        float(row["natr_14"]),
                        float(row["realized_volatility_20"]),
                        _summary_from_row(row, "natr_14"),
                        _summary_from_row(row, "realized_volatility_20"),
                    ),
                    "efficiency": efficiency_state(
                        float(row["directional_efficiency_20"]),
                        _summary_from_row(row, "directional_efficiency_20"),
                    ),
                    "composite": composite_sector_state(structure, momentum),
                }
            )
    return pd.DataFrame(rows)


def _snapshot(row: pd.Series) -> dict[str, str | int | float | None]:
    result: dict[str, str | int | float | None] = {
        "trading_date": str(pd.Timestamp(row["trading_date"]).date()),
        "composite": str(row["composite"]),
        "structure": str(row["structure"]),
        "momentum": str(row["momentum"]),
        "volatility": str(row["volatility"]),
        "efficiency": str(row["efficiency"]),
    }
    if "participation" in row.index:
        result["participation"] = str(row["participation"])
    return result


def _market_threshold_snapshot(frame: pd.DataFrame) -> dict[str, dict[str, float | None]]:
    if frame.empty:
        return {}
    row = frame.iloc[-1]
    result: dict[str, dict[str, float | None]] = {}
    for metric in MARKET_THRESHOLD_SNAPSHOT_METRICS:
        result[metric] = {}
        for quantile in ("p25", "p75", "p90"):
            key = f"{metric}__{quantile}"
            if key in row.index:
                result[metric][quantile] = None if pd.isna(row[key]) else float(row[key])
    return result


class RegimeThresholdProbe:
    """Compare point-in-time-safe threshold memory policies after persistence selection.

    Every candidate uses the same first 252 fully warmed sessions as seed history and
    starts evaluation on the next session. Thresholds for an observation are computed
    only from earlier observations. The chosen two-session dimensional confirmation is
    then applied before composite market/sector states are evaluated.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calibration = RegimeCalibration(settings)
        self.paths = self.calibration.paths

    def build(self, start_date: date, end_date: date) -> RegimeThresholdProbeReport:
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        started = perf_counter()
        breadth = self.calibration._breadth_daily(start_date, end_date)
        proxies = self.calibration._proxy_frame(start_date, end_date)
        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        market_basket = basket_daily(market_frame)
        if len(breadth) <= REGIME_THRESHOLD_TRAINING_SESSIONS:
            raise ValueError("threshold probe requires more than 252 fully warmed market sessions")

        retrospective_market = persist_market_states(
            _market_daily_states(breadth, market_basket),
            REGIME_SELECTED_CONFIRMATION_SESSIONS,
        )
        retrospective_sector = persist_sector_states(
            _sector_daily_states(sector_frame),
            REGIME_SELECTED_CONFIRMATION_SESSIONS,
        )

        market_candidates: dict[str, dict[str, object]] = {}
        sector_candidates: dict[str, dict[str, object]] = {}
        first_eval: str | None = None
        last_eval: str | None = None
        evaluation_count: int | None = None
        sector_eval_count: int | None = None

        for policy_name in REGIME_THRESHOLD_POLICY_NAMES:
            raw_market = _market_point_in_time_states(breadth, market_basket, policy_name)
            persisted_market = persist_market_states(
                raw_market,
                REGIME_SELECTED_CONFIRMATION_SESSIONS,
            )
            if persisted_market.empty:
                raise ValueError(f"threshold policy {policy_name} produced no market states")
            market_dates = pd.to_datetime(persisted_market["trading_date"]).dt.date
            reference_market = retrospective_market.loc[
                pd.to_datetime(retrospective_market["trading_date"]).dt.date.isin(set(market_dates))
            ].sort_values("trading_date").reset_index(drop=True)
            candidate_market = persisted_market.sort_values("trading_date").reset_index(drop=True)
            if len(reference_market) != len(candidate_market):
                raise ValueError("point-in-time and retrospective market frames are not aligned")
            market_counts = _counts(candidate_market["composite"])
            market_candidates[policy_name] = {
                "state_counts": market_counts,
                "state_percentages": _percentages(market_counts, len(candidate_market)),
                "transition_diagnostics": run_diagnostics(candidate_market["composite"].astype(str).tolist()),
                "retrospective_reference_agreement": agreement_diagnostics(
                    reference_market["composite"].astype(str).tolist(),
                    candidate_market["composite"].astype(str).tolist(),
                ),
                "end_date_state": _snapshot(candidate_market.iloc[-1]),
                "end_thresholds": _market_threshold_snapshot(raw_market),
            }

            raw_sector = _sector_point_in_time_states(sector_frame, policy_name)
            persisted_sector = persist_sector_states(
                raw_sector,
                REGIME_SELECTED_CONFIRMATION_SESSIONS,
            )
            sector_dates = set(pd.to_datetime(persisted_sector["trading_date"]).dt.date)
            reference_sector = retrospective_sector.loc[
                pd.to_datetime(retrospective_sector["trading_date"]).dt.date.isin(sector_dates)
            ].sort_values(["symbol", "trading_date"]).reset_index(drop=True)
            candidate_sector = persisted_sector.sort_values(["symbol", "trading_date"]).reset_index(drop=True)
            if len(reference_sector) != len(candidate_sector):
                raise ValueError("point-in-time and retrospective sector frames are not aligned")
            sector_counts = _counts(candidate_sector["composite"])
            end_sector: dict[str, dict[str, str | int | float | None]] = {}
            for ticker in SECTOR_PROXY_TICKERS:
                subset = candidate_sector.loc[candidate_sector["symbol"] == ticker].sort_values("trading_date")
                if not subset.empty:
                    end_sector[ticker] = _snapshot(subset.iloc[-1])
            sector_candidates[policy_name] = {
                "state_counts": sector_counts,
                "state_percentages": _percentages(sector_counts, len(candidate_sector)),
                "transition_summary": _transition_summary(candidate_sector),
                "retrospective_reference_agreement": _sector_agreement(
                    reference_sector,
                    candidate_sector,
                ),
                "end_date_states": end_sector,
            }

            current_first = str(pd.Timestamp(candidate_market.iloc[0]["trading_date"]).date())
            current_last = str(pd.Timestamp(candidate_market.iloc[-1]["trading_date"]).date())
            if first_eval is None:
                first_eval = current_first
                last_eval = current_last
                evaluation_count = len(candidate_market)
                sector_eval_count = len(candidate_sector)
            elif (
                current_first != first_eval
                or current_last != last_eval
                or len(candidate_market) != evaluation_count
                or len(candidate_sector) != sector_eval_count
            ):
                raise ValueError("point-in-time threshold candidates do not share one evaluation window")

        assert first_eval is not None and last_eval is not None
        assert evaluation_count is not None and sector_eval_count is not None
        target = self.paths.regime_threshold_probe_report(end_date)
        report = RegimeThresholdProbeReport(
            contract_version=REGIME_THRESHOLD_PROBE_CONTRACT_VERSION,
            persistence_probe_contract_version=REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="DIAGNOSTIC_ONLY",
            point_in_time_note=(
                "All thresholds use strictly prior observations. Frozen_252 fixes the first 252-session bands; "
                "expanding_252 uses all prior history after the same seed; rolling_252 uses only the prior 252 sessions."
            ),
            selected_confirmation_sessions=REGIME_SELECTED_CONFIRMATION_SESSIONS,
            training_sessions=REGIME_THRESHOLD_TRAINING_SESSIONS,
            policy_names=REGIME_THRESHOLD_POLICY_NAMES,
            evaluation_session_count=evaluation_count,
            first_evaluation_date=first_eval,
            last_evaluation_date=last_eval,
            market_candidates=market_candidates,
            sector_evaluation_observation_count=sector_eval_count,
            sector_candidates=sector_candidates,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report
