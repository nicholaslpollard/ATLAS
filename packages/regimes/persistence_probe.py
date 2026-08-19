from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from statistics import median
from time import perf_counter

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .calibration import RegimeCalibration, basket_daily
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS
from .policy_probe import (
    REGIME_POLICY_PROBE_CONTRACT_VERSION,
    _counts,
    _market_daily_states,
    _percentages,
    _sector_daily_states,
    composite_market_state,
    composite_sector_state,
    run_diagnostics,
)


REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION = (
    "regime-persistence-probe-v1-dimension-confirmation-grid"
)
REGIME_PERSISTENCE_CONFIRMATION_WINDOWS = (2, 3)
MARKET_PERSISTED_DIMENSIONS = (
    "structure",
    "momentum",
    "participation",
    "volatility",
    "efficiency",
)
SECTOR_PERSISTED_DIMENSIONS = (
    "structure",
    "momentum",
    "volatility",
    "efficiency",
)


@dataclass(frozen=True, slots=True)
class RegimePersistenceProbeReport:
    contract_version: str
    policy_probe_contract_version: str
    generated_at_utc: str
    start_date: str
    end_date: str
    wall_seconds: float
    probe_status: str
    persistence_basis_note: str
    threshold_basis_note: str
    confirmation_windows: tuple[int, ...]
    market_session_count: int
    raw_market_transition_diagnostics: dict[str, float | int | None]
    market_candidates: dict[str, dict[str, object]]
    sector_observation_count: int
    raw_sector_transition_summary: dict[str, float | int | None]
    sector_candidates: dict[str, dict[str, object]]
    report_path: str


def confirm_states(raw_states: list[str], sessions_required: int) -> list[str]:
    """Require consecutive observations of a new state before committing the switch.

    The first observation initializes state immediately. A candidate state must then be
    observed ``sessions_required`` consecutive times before replacing the persisted
    state. Returning to the persisted state clears the pending candidate. A different
    candidate restarts the streak at one.
    """

    if isinstance(sessions_required, bool) or not isinstance(sessions_required, int):
        raise TypeError("sessions_required must be an integer")
    if sessions_required < 1:
        raise ValueError("sessions_required must be at least 1")
    if not raw_states:
        return []

    current = raw_states[0]
    pending: str | None = None
    streak = 0
    persisted = [current]

    for raw in raw_states[1:]:
        if raw == current:
            pending = None
            streak = 0
        else:
            if raw == pending:
                streak += 1
            else:
                pending = raw
                streak = 1
            if streak >= sessions_required:
                current = raw
                pending = None
                streak = 0
        persisted.append(current)
    return persisted


def direction_family(state: str) -> str:
    if state in {"BULL", "STRONG_BULL"}:
        return "BULL"
    if state in {"BEAR", "STRONG_BEAR"}:
        return "BEAR"
    return "MIXED"


def agreement_diagnostics(
    raw_states: list[str],
    persisted_states: list[str],
) -> dict[str, float | int | None]:
    if len(raw_states) != len(persisted_states):
        raise ValueError("raw and persisted state sequences must have equal length")
    total = len(raw_states)
    if total == 0:
        return {
            "observation_count": 0,
            "exact_agreement_rate": None,
            "direction_family_agreement_rate": None,
            "opposite_direction_mismatch_count": 0,
            "opposite_direction_mismatch_rate": None,
        }

    exact = 0
    family = 0
    opposite = 0
    for raw, persisted in zip(raw_states, persisted_states, strict=True):
        if raw == persisted:
            exact += 1
        raw_family = direction_family(raw)
        persisted_family = direction_family(persisted)
        if raw_family == persisted_family:
            family += 1
        if {raw_family, persisted_family} == {"BULL", "BEAR"}:
            opposite += 1
    return {
        "observation_count": total,
        "exact_agreement_rate": exact / total,
        "direction_family_agreement_rate": family / total,
        "opposite_direction_mismatch_count": opposite,
        "opposite_direction_mismatch_rate": opposite / total,
    }


def persist_market_states(frame: pd.DataFrame, sessions_required: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    data = frame.sort_values("trading_date").reset_index(drop=True).copy()
    for dimension in MARKET_PERSISTED_DIMENSIONS:
        data[dimension] = confirm_states(data[dimension].astype(str).tolist(), sessions_required)
    data["composite"] = [
        composite_market_state(structure, momentum, participation)
        for structure, momentum, participation in zip(
            data["structure"],
            data["momentum"],
            data["participation"],
            strict=True,
        )
    ]
    return data


def persist_sector_states(frame: pd.DataFrame, sessions_required: int) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    groups: list[pd.DataFrame] = []
    for symbol, subset in frame.groupby("symbol", sort=True, observed=True):
        data = subset.sort_values("trading_date").reset_index(drop=True).copy()
        for dimension in SECTOR_PERSISTED_DIMENSIONS:
            data[dimension] = confirm_states(
                data[dimension].astype(str).tolist(),
                sessions_required,
            )
        data["composite"] = [
            composite_sector_state(structure, momentum)
            for structure, momentum in zip(
                data["structure"],
                data["momentum"],
                strict=True,
            )
        ]
        data["symbol"] = symbol
        groups.append(data)
    return pd.concat(groups, ignore_index=True) if groups else frame.copy()


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


def _transition_summary(
    frame: pd.DataFrame,
) -> dict[str, float | int | None]:
    if frame.empty:
        return {
            "symbol_count": 0,
            "mean_transition_rate": None,
            "median_transition_rate": None,
            "max_transition_rate": None,
            "median_of_median_run_lengths": None,
            "mean_one_day_run_share": None,
        }
    rates: list[float] = []
    run_medians: list[float] = []
    one_day_shares: list[float] = []
    for _, subset in frame.groupby("symbol", sort=True, observed=True):
        diag = run_diagnostics(subset.sort_values("trading_date")["composite"].astype(str).tolist())
        if diag["transition_rate"] is not None:
            rates.append(float(diag["transition_rate"]))
        if diag["median_run_length"] is not None:
            run_medians.append(float(diag["median_run_length"]))
        if diag["one_day_run_share"] is not None:
            one_day_shares.append(float(diag["one_day_run_share"]))
    return {
        "symbol_count": int(frame["symbol"].nunique()),
        "mean_transition_rate": None if not rates else sum(rates) / len(rates),
        "median_transition_rate": None if not rates else float(median(rates)),
        "max_transition_rate": None if not rates else max(rates),
        "median_of_median_run_lengths": None if not run_medians else float(median(run_medians)),
        "mean_one_day_run_share": None if not one_day_shares else sum(one_day_shares) / len(one_day_shares),
    }


def _sector_agreement(
    raw: pd.DataFrame,
    persisted: pd.DataFrame,
) -> dict[str, float | int | None]:
    raw_ordered = raw.sort_values(["symbol", "trading_date"]).reset_index(drop=True).copy()
    persisted_ordered = persisted.sort_values(["symbol", "trading_date"]).reset_index(drop=True).copy()
    raw_ordered["trading_date"] = pd.to_datetime(raw_ordered["trading_date"]).dt.date
    persisted_ordered["trading_date"] = pd.to_datetime(persisted_ordered["trading_date"]).dt.date
    if not raw_ordered[["symbol", "trading_date"]].equals(
        persisted_ordered[["symbol", "trading_date"]]
    ):
        raise ValueError("raw and persisted sector frames are not aligned")
    return agreement_diagnostics(
        raw_ordered["composite"].astype(str).tolist(),
        persisted_ordered["composite"].astype(str).tolist(),
    )


class RegimePersistenceProbe:
    """Compare simple dimensional confirmation windows against the raw Gate 4 states.

    This remains a retrospective diagnostic because the underlying Gate 4 quartile
    bands are calculated over the full requested history. Its purpose is to measure the
    stability/lag trade-off of 2- and 3-session confirmation before any production
    persistence contract or point-in-time threshold policy is locked.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calibration = RegimeCalibration(settings)
        self.paths = self.calibration.paths

    def build(self, start_date: date, end_date: date) -> RegimePersistenceProbeReport:
        if start_date > end_date:
            raise ValueError("start_date must be on or before end_date")
        started = perf_counter()
        breadth = self.calibration._breadth_daily(start_date, end_date)
        proxies = self.calibration._proxy_frame(start_date, end_date)
        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        raw_market = _market_daily_states(breadth, basket_daily(market_frame))
        raw_sector = _sector_daily_states(sector_frame)
        if raw_market.empty or raw_sector.empty:
            raise ValueError("persistence probe requires non-empty Gate 4 raw states")

        raw_market_diag = run_diagnostics(raw_market["composite"].astype(str).tolist())
        raw_sector_summary = _transition_summary(raw_sector)
        market_candidates: dict[str, dict[str, object]] = {}
        sector_candidates: dict[str, dict[str, object]] = {}

        for sessions_required in REGIME_PERSISTENCE_CONFIRMATION_WINDOWS:
            key = f"confirm_{sessions_required}"
            persisted_market = persist_market_states(raw_market, sessions_required)
            market_counts = _counts(persisted_market["composite"])
            market_diag = run_diagnostics(persisted_market["composite"].astype(str).tolist())
            market_agreement = agreement_diagnostics(
                raw_market["composite"].astype(str).tolist(),
                persisted_market["composite"].astype(str).tolist(),
            )
            raw_rate = raw_market_diag["transition_rate"]
            new_rate = market_diag["transition_rate"]
            market_candidates[key] = {
                "sessions_required": sessions_required,
                "maximum_confirmation_lag_sessions": sessions_required - 1,
                "state_counts": market_counts,
                "state_percentages": _percentages(market_counts, len(persisted_market)),
                "transition_diagnostics": market_diag,
                "transition_rate_reduction": (
                    None
                    if raw_rate is None or new_rate is None or float(raw_rate) == 0.0
                    else 1.0 - float(new_rate) / float(raw_rate)
                ),
                "agreement": market_agreement,
                "end_date_state": _snapshot(persisted_market.iloc[-1]),
            }

            persisted_sector = persist_sector_states(raw_sector, sessions_required)
            sector_counts = _counts(persisted_sector["composite"])
            sector_summary = _transition_summary(persisted_sector)
            per_sector_transition: dict[str, dict[str, float | int | None]] = {}
            end_sector_states: dict[str, dict[str, str | int | float | None]] = {}
            for ticker in SECTOR_PROXY_TICKERS:
                subset = persisted_sector.loc[persisted_sector["symbol"] == ticker].sort_values(
                    "trading_date"
                )
                if subset.empty:
                    continue
                per_sector_transition[ticker] = run_diagnostics(
                    subset["composite"].astype(str).tolist()
                )
                end_sector_states[ticker] = _snapshot(subset.iloc[-1])
            raw_sector_rate = raw_sector_summary["mean_transition_rate"]
            persisted_sector_rate = sector_summary["mean_transition_rate"]
            sector_candidates[key] = {
                "sessions_required": sessions_required,
                "maximum_confirmation_lag_sessions": sessions_required - 1,
                "state_counts": sector_counts,
                "state_percentages": _percentages(sector_counts, len(persisted_sector)),
                "transition_summary": sector_summary,
                "mean_transition_rate_reduction": (
                    None
                    if raw_sector_rate is None
                    or persisted_sector_rate is None
                    or float(raw_sector_rate) == 0.0
                    else 1.0 - float(persisted_sector_rate) / float(raw_sector_rate)
                ),
                "agreement": _sector_agreement(raw_sector, persisted_sector),
                "per_sector_transition_diagnostics": per_sector_transition,
                "end_date_states": end_sector_states,
            }

        target = self.paths.regime_persistence_probe_report(end_date)
        report = RegimePersistenceProbeReport(
            contract_version=REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION,
            policy_probe_contract_version=REGIME_POLICY_PROBE_CONTRACT_VERSION,
            generated_at_utc=datetime.now(UTC).isoformat(),
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            wall_seconds=perf_counter() - started,
            probe_status="DIAGNOSTIC_ONLY",
            persistence_basis_note=(
                "Each raw dimension is confirmed independently for N consecutive sessions; the composite is then "
                "recomputed from persisted dimensions. First observation initializes immediately."
            ),
            threshold_basis_note=(
                "Underlying Gate 4 p25/p75 thresholds remain retrospective full-window diagnostic bands; this is "
                "not point-in-time performance evidence."
            ),
            confirmation_windows=REGIME_PERSISTENCE_CONFIRMATION_WINDOWS,
            market_session_count=int(len(raw_market)),
            raw_market_transition_diagnostics=raw_market_diag,
            market_candidates=market_candidates,
            sector_observation_count=int(len(raw_sector)),
            raw_sector_transition_summary=raw_sector_summary,
            sector_candidates=sector_candidates,
            report_path=str(target),
        )
        atomic_write_text(target, json.dumps(asdict(report), indent=2, sort_keys=True) + "\n")
        return report