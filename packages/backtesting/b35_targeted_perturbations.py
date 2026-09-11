from __future__ import annotations

import hashlib
import itertools
import json
import math
import os
import time as monotonic_time
from collections import Counter, deque
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Sequence

import pandas as pd

import packages.backtesting.b35_parallel_replay as parallel
from packages.backtesting.b35_development_authorization import validate_development_authorization
from packages.backtesting.b35_development_context import summarize_regular_session
from packages.backtesting.b35_development_replay import (
    B35DevelopmentReplayError,
    _SymbolHistory,
    _canonical_bars,
    _completed_group,
    _current_regular_open,
    _evaluate_setups,
    _first_regular_bar,
    _group_units,
    _premarket_volume,
    _receipt_id,
    _sha256_file,
    _split_between,
    _split_epoch,
    _stable_hash,
)
from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentSourcePlan,
    B35DevelopmentUnitBinding,
    validate_source_plan,
)
from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.backtesting.b35_replay_guard import ensure_read_start_marker, serialized_replay
from packages.backtesting.b35_setup_scan import (
    first_fired_hvd,
    first_fired_opening_range,
    first_fired_premarket_relvol,
)
from packages.backtesting.b35_split_evidence import load_b35_split_evidence
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.enums import SessionSegment
from packages.core.execution_profile import ParallelResearchExecutionProfile
from packages.schemas.strategy import StrategyDirection
from packages.strategies.b35_conditional_evidence_contract import (
    ALL_IN_ROUND_TRIP_COST_GRID_BPS,
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
    ROBUSTNESS_PERTURBATIONS,
)
from packages.strategies.intraday_opening_pack import (
    B34_INTRADAY_PACK_CONTRACT,
    GAP_MIN_ABS_PCT,
    HVD_DAILY_LOOKBACK_SESSIONS,
    MARKET_TZ,
    OPENING_RANGE_ENTRY_CUTOFF,
    OPENING_RANGE_START,
    PREMARKET_BREAKOUT_CUTOFF,
    PREMARKET_CONSOLIDATION_MAX_RANGE_PCT,
    PREMARKET_END,
    PREMARKET_LOOKBACK_SESSIONS,
    PREMARKET_RELVOL_MIN,
    IntradaySetupResult,
    premarket_snapshot,
)

B35_TARGETED_PERTURBATION_CONTRACT = (
    "atlas-b35-targeted-minute-perturbations-v1-diagnostic-no-promotion"
)
B35_ACCEPTED_ROBUSTNESS_FINGERPRINT = (
    "c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107"
)
B35_TARGETED_AUTHORIZATION_CONTRACT = (
    "atlas-b35-targeted-minute-perturbation-authorization-v1-explicit"
)


@dataclass(frozen=True, slots=True)
class PerturbationVariant:
    variant_id: str
    family: str
    strategy_id: str
    parameter: str
    value: float
    baseline: bool


def _variants() -> tuple[PerturbationVariant, ...]:
    rows: list[PerturbationVariant] = []
    for strategy_id in B34_STRATEGY_IDS:
        for value in ROBUSTNESS_PERTURBATIONS["entry_delay_minutes"]:
            rows.append(
                PerturbationVariant(
                    variant_id=f"entry_delay_minutes:{int(value)}:{strategy_id}",
                    family="entry_delay_minutes",
                    strategy_id=strategy_id,
                    parameter="entry_delay_minutes",
                    value=float(value),
                    baseline=int(value) == 0,
                )
            )
    for value in ROBUSTNESS_PERTURBATIONS["gap_threshold_multiplier"]:
        rows.append(
            PerturbationVariant(
                variant_id=f"gap_threshold_multiplier:{float(value):.1f}:b34_gap_continuation_v1",
                family="gap_threshold_multiplier",
                strategy_id="b34_gap_continuation_v1",
                parameter="gap_threshold_multiplier",
                value=float(value),
                baseline=float(value) == 1.0,
            )
        )
    for value in ROBUSTNESS_PERTURBATIONS["opening_range_minutes"]:
        rows.append(
            PerturbationVariant(
                variant_id=f"opening_range_minutes:{int(value)}:b34_opening_range_breakout_15m_v1",
                family="opening_range_minutes",
                strategy_id="b34_opening_range_breakout_15m_v1",
                parameter="opening_range_minutes",
                value=float(value),
                baseline=int(value) == 15,
            )
        )
    for value in ROBUSTNESS_PERTURBATIONS["premarket_relvol_threshold_multiplier"]:
        rows.append(
            PerturbationVariant(
                variant_id=f"premarket_relvol_threshold_multiplier:{float(value):.1f}:b34_premarket_relvol_consolidation_v1",
                family="premarket_relvol_threshold_multiplier",
                strategy_id="b34_premarket_relvol_consolidation_v1",
                parameter="premarket_relvol_threshold_multiplier",
                value=float(value),
                baseline=float(value) == 1.0,
            )
        )
    for strategy_id in (
        "b34_premarket_relvol_consolidation_v1",
        "b34_highest_volume_day_style_v1",
    ):
        for value in ROBUSTNESS_PERTURBATIONS["premarket_consolidation_range_multiplier"]:
            rows.append(
                PerturbationVariant(
                    variant_id=f"premarket_consolidation_range_multiplier:{float(value):.1f}:{strategy_id}",
                    family="premarket_consolidation_range_multiplier",
                    strategy_id=strategy_id,
                    parameter="premarket_consolidation_range_multiplier",
                    value=float(value),
                    baseline=float(value) == 1.0,
                )
            )
    return tuple(rows)


TARGETED_VARIANTS = _variants()
TARGETED_PERTURBATION_FINGERPRINT = hashlib.sha256(
    json.dumps(
        {
            "contract": B35_TARGETED_PERTURBATION_CONTRACT,
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "accepted_robustness_fingerprint": B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
            "variants": [asdict(item) for item in TARGETED_VARIANTS],
            "semantics": {
                "one_axis_at_a_time": True,
                "entry_delay": (
                    "intentionally shift the information-safe signal timestamp by N clock minutes, "
                    "then apply the unchanged B35 next-observed-bar-within-five-minutes outcome logic"
                ),
                "gap_threshold": "multiply frozen 2% absolute gap threshold; all other mechanics unchanged",
                "opening_range": (
                    "use observed regular bars starting 09:30 for N minutes; first post-range closed "
                    "breakout through 11:30; opposite range boundary remains stop"
                ),
                "premarket_relvol": "multiply frozen 2.0 relative-volume threshold; all other mechanics unchanged",
                "premarket_consolidation": (
                    "multiply frozen 3% consolidation maximum; applies independently to premarket-relvol "
                    "and HVD-style strategies; all other mechanics unchanged"
                ),
                "cost_grid_bps": list(ALL_IN_ROUND_TRIP_COST_GRID_BPS),
                "selector_refit": False,
                "promotion_authority": False,
            },
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
).hexdigest()


@dataclass(frozen=True, slots=True)
class B35PerturbationGroupTask:
    canonical_group_fingerprint: str
    perturbation_group_fingerprint: str
    units: tuple[B35DevelopmentUnitBinding, ...]
    start_session: date
    end_session: date
    source_fingerprint: str
    split_evidence_fingerprint: str
    development_authorization_id: str
    targeted_authorization_id: str
    canonical_strategy_counts: dict[str, dict[str, int]]
    output_path: str
    receipt_path: str

    @property
    def token(self) -> str:
        return self.perturbation_group_fingerprint[:20]


def _authorization_payload(
    *,
    plan: B35DevelopmentSourcePlan,
    split_evidence_fingerprint: str,
    development_authorization_id: str,
) -> dict[str, object]:
    return {
        "contract": B35_TARGETED_AUTHORIZATION_CONTRACT,
        "status": "AUTHORIZED_TARGETED_DEVELOPMENT_DIAGNOSTIC",
        "purpose": "B35_EXACT_TARGETED_MINUTE_PERTURBATION_REPLAY",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "accepted_robustness_fingerprint": B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
        "targeted_perturbation_fingerprint": TARGETED_PERTURBATION_FINGERPRINT,
        "source_fingerprint": plan.source_fingerprint,
        "split_evidence_fingerprint": split_evidence_fingerprint,
        "development_authorization_id": development_authorization_id,
        "start_session": plan.start_session.isoformat(),
        "end_session": plan.end_session.isoformat(),
        "consumed_master_rows_permitted": 0,
        "future_blind_rows_permitted": 0,
        "provider_calls_permitted": 0,
        "broker_reads_permitted": 0,
        "broker_writes_permitted": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
        "canonical_replay_rewrite": False,
        "selector_refit": False,
    }


def ensure_targeted_authorization(
    path: Path,
    *,
    plan: B35DevelopmentSourcePlan,
    split_evidence_fingerprint: str,
    development_authorization_id: str,
) -> dict[str, object]:
    path = path.resolve()
    required = _authorization_payload(
        plan=plan,
        split_evidence_fingerprint=split_evidence_fingerprint,
        development_authorization_id=development_authorization_id,
    )

    def validate(value: object) -> dict[str, object]:
        if not isinstance(value, dict):
            raise B35DevelopmentReplayError("targeted perturbation authorization is not an object")
        for key, expected in required.items():
            if value.get(key) != expected:
                raise B35DevelopmentReplayError(
                    f"targeted perturbation authorization {key} drifted"
                )
        raw_time = str(value.get("authorized_at_utc") or "")
        stamp = datetime.fromisoformat(raw_time)
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise B35DevelopmentReplayError(
                "targeted perturbation authorization timestamp is not aware"
            )
        actual = str(value.get("authorization_id") or "")
        expected_id = _stable_hash(
            {key: item for key, item in value.items() if key != "authorization_id"}
        )
        if actual != expected_id:
            raise B35DevelopmentReplayError(
                "targeted perturbation authorization self-hash drifted"
            )
        return value

    if path.is_file():
        return validate(json.loads(path.read_text(encoding="utf-8")))
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {**required, "authorized_at_utc": datetime.now(UTC).isoformat()}
    document["authorization_id"] = _stable_hash(document)
    atomic_write_text(
        path,
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    return validate(document)


def _result(
    *,
    strategy_id: str,
    session_date: date,
    direction: StrategyDirection,
    evidence: dict[str, object],
    reason: str,
) -> IntradaySetupResult:
    return IntradaySetupResult(
        contract=B34_INTRADAY_PACK_CONTRACT,
        strategy_id=strategy_id,
        session_date=session_date.isoformat(),
        ready=True,
        fired=True,
        direction=direction.value,
        reason_codes=(reason,),
        evidence=evidence,
    )


def _regular_bars(bars: Sequence[Any], session_date: date) -> list[Any]:
    return sorted(
        [
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment == SessionSegment.REGULAR
        ],
        key=lambda item: item.timestamp_utc,
    )


def _gap_variant(
    bars: Sequence[Any],
    *,
    session_date: date,
    prior_close: float,
    symbol_split_dates: Sequence[date],
    prior_session: date,
    multiplier: float,
) -> IntradaySetupResult | None:
    if multiplier == 1.0:
        for setup in _evaluate_setups(
            bars,
            session_date=session_date,
            history=_SymbolHistory(
                daily=[],
                premarket=[],
            ),
            symbol_split_dates=symbol_split_dates,
        ):
            if setup.strategy_id == "b34_gap_continuation_v1":
                return setup
        return None
    first = _first_regular_bar(bars, session_date)
    if first is None:
        return None
    if _split_between(symbol_split_dates, prior_session, session_date):
        return None
    gap_decision = first.timestamp_utc + timedelta(minutes=1)
    if gap_decision.astimezone(MARKET_TZ).time() > time(11, 31):
        return None
    current_open = float(first.open)
    threshold = GAP_MIN_ABS_PCT * multiplier
    gap_pct = current_open / float(prior_close) - 1.0
    if gap_pct >= threshold:
        direction = StrategyDirection.LONG
    elif gap_pct <= -threshold:
        direction = StrategyDirection.SHORT
    else:
        return None
    return _result(
        strategy_id="b34_gap_continuation_v1",
        session_date=session_date,
        direction=direction,
        reason="GAP_THRESHOLD_PERTURBATION_MET",
        evidence={
            "prior_regular_close": float(prior_close),
            "current_regular_open": current_open,
            "gap_pct": gap_pct,
            "threshold_abs_pct": threshold,
        },
    )


def _opening_range_variant(
    bars: Sequence[Any],
    *,
    session_date: date,
    minutes: int,
) -> IntradaySetupResult | None:
    if minutes == 15:
        return first_fired_opening_range(bars, session_date=session_date)
    regular = _regular_bars(bars, session_date)
    if not regular:
        return None
    start_dt = datetime.combine(session_date, OPENING_RANGE_START, tzinfo=MARKET_TZ)
    end_dt = start_dt + timedelta(minutes=minutes)
    opening = [
        bar
        for bar in regular
        if start_dt.time()
        <= bar.timestamp_utc.astimezone(MARKET_TZ).time()
        < end_dt.time()
    ]
    if not opening:
        return None
    high = max(float(bar.high) for bar in opening)
    low = min(float(bar.low) for bar in opening)
    for bar in regular:
        stamp = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if stamp < end_dt.time() or stamp > OPENING_RANGE_ENTRY_CUTOFF:
            continue
        close = float(bar.close)
        if close > high:
            direction = StrategyDirection.LONG
        elif close < low:
            direction = StrategyDirection.SHORT
        else:
            continue
        return _result(
            strategy_id="b34_opening_range_breakout_15m_v1",
            session_date=session_date,
            direction=direction,
            reason="OPENING_RANGE_MINUTES_PERTURBATION_BREAKOUT",
            evidence={
                "opening_range_high": high,
                "opening_range_low": low,
                "opening_range_observed_bars": len(opening),
                "breakout_bar_timestamp_utc": bar.timestamp_utc.isoformat(),
                "breakout_bar_close": close,
                "opening_range_minutes": minutes,
            },
        )
    return None


def _premarket_relvol_variant(
    bars: Sequence[Any],
    *,
    session_date: date,
    prior_premarket_volumes: Sequence[float],
    split_free_lookback: bool,
    relvol_multiplier: float = 1.0,
    consolidation_multiplier: float = 1.0,
) -> IntradaySetupResult | None:
    if relvol_multiplier == 1.0 and consolidation_multiplier == 1.0:
        return first_fired_premarket_relvol(
            bars,
            session_date=session_date,
            prior_premarket_volumes=prior_premarket_volumes,
            split_free_lookback=split_free_lookback,
        )
    if not split_free_lookback or len(prior_premarket_volumes) != PREMARKET_LOOKBACK_SESSIONS:
        return None
    baseline = float(median(prior_premarket_volumes))
    if baseline <= 0:
        return None
    decision = datetime.combine(
        session_date, PREMARKET_END, tzinfo=MARKET_TZ
    ).astimezone(UTC)
    snapshot = premarket_snapshot(
        bars, session_date=session_date, decision_time_utc=decision
    )
    if snapshot is None:
        return None
    relvol_threshold = PREMARKET_RELVOL_MIN * relvol_multiplier
    range_threshold = PREMARKET_CONSOLIDATION_MAX_RANGE_PCT * consolidation_multiplier
    if (
        snapshot.cumulative_volume / baseline < relvol_threshold
        or snapshot.consolidation_range_pct > range_threshold
    ):
        return None
    for bar in _regular_bars(bars, session_date):
        stamp = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if stamp < PREMARKET_END or stamp > PREMARKET_BREAKOUT_CUTOFF:
            continue
        if float(bar.close) <= float(snapshot.consolidation_high):
            continue
        return _result(
            strategy_id="b34_premarket_relvol_consolidation_v1",
            session_date=session_date,
            direction=StrategyDirection.LONG,
            reason="PREMARKET_PERTURBATION_BREAKOUT",
            evidence={
                **asdict(snapshot),
                "median_prior_20_premarket_volume": baseline,
                "premarket_relvol": snapshot.cumulative_volume / baseline,
                "relvol_threshold": relvol_threshold,
                "consolidation_max_range_pct": range_threshold,
                "breakout_bar_timestamp_utc": bar.timestamp_utc.isoformat(),
                "breakout_bar_close": float(bar.close),
            },
        )
    return None


def _hvd_consolidation_variant(
    bars: Sequence[Any],
    *,
    session_date: date,
    prior_regular_daily_volumes: Sequence[float],
    split_free_lookback: bool,
    consolidation_multiplier: float,
) -> IntradaySetupResult | None:
    if consolidation_multiplier == 1.0:
        return first_fired_hvd(
            bars,
            session_date=session_date,
            prior_regular_daily_volumes=prior_regular_daily_volumes,
            split_free_lookback=split_free_lookback,
        )
    if not split_free_lookback or len(prior_regular_daily_volumes) != HVD_DAILY_LOOKBACK_SESSIONS:
        return None
    highest = float(max(prior_regular_daily_volumes))
    if highest <= 0:
        return None
    decision = datetime.combine(
        session_date, PREMARKET_END, tzinfo=MARKET_TZ
    ).astimezone(UTC)
    snapshot = premarket_snapshot(
        bars, session_date=session_date, decision_time_utc=decision
    )
    if snapshot is None:
        return None
    range_threshold = PREMARKET_CONSOLIDATION_MAX_RANGE_PCT * consolidation_multiplier
    if (
        snapshot.cumulative_volume < highest
        or snapshot.consolidation_range_pct > range_threshold
    ):
        return None
    for bar in _regular_bars(bars, session_date):
        stamp = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if stamp < PREMARKET_END or stamp > PREMARKET_BREAKOUT_CUTOFF:
            continue
        if float(bar.close) <= float(snapshot.high):
            continue
        return _result(
            strategy_id="b34_highest_volume_day_style_v1",
            session_date=session_date,
            direction=StrategyDirection.LONG,
            reason="HVD_CONSOLIDATION_PERTURBATION_BREAKOUT",
            evidence={
                **asdict(snapshot),
                "highest_prior_252_daily_volume": highest,
                "premarket_volume_ratio_to_prior_max": snapshot.cumulative_volume / highest,
                "consolidation_max_range_pct": range_threshold,
                "breakout_bar_timestamp_utc": bar.timestamp_utc.isoformat(),
                "breakout_bar_close": float(bar.close),
            },
        )
    return None


def _shift_setup_for_entry_delay(
    setup: IntradaySetupResult,
    bars: Sequence[Any],
    session_date: date,
    delay_minutes: int,
) -> IntradaySetupResult:
    if delay_minutes == 0:
        return setup
    raw = setup.evidence.get("breakout_bar_timestamp_utc")
    if isinstance(raw, str) and raw:
        stamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    elif setup.strategy_id == "b34_gap_continuation_v1":
        first = _first_regular_bar(bars, session_date)
        if first is None:
            raise B35DevelopmentReplayError("gap perturbation has no regular bar")
        stamp = first.timestamp_utc
    else:
        raise B35DevelopmentReplayError(
            "entry-delay perturbation cannot identify the frozen signal bar"
        )
    shifted = stamp + timedelta(minutes=delay_minutes)
    evidence = dict(setup.evidence)
    evidence["breakout_bar_timestamp_utc"] = shifted.isoformat()
    evidence["intentional_entry_delay_minutes"] = delay_minutes
    return replace(setup, evidence=evidence)


def _metric_template(variant: PerturbationVariant) -> dict[str, object]:
    return {
        **asdict(variant),
        "fired": 0,
        "comparable": 0,
        "noncomparable": 0,
        "wins_50bps": 0,
        "gross_return_sum": 0.0,
        "risk_multiple_sum": 0.0,
        "mfe_sum": 0.0,
        "mae_sum": 0.0,
        "net_return_sums_by_cost_bps": {
            str(cost): 0.0 for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS
        },
        "status_counts": {},
        "direction_counts": {},
        "session_bitset_hex": "0x0",
        "symbols": [],
    }


def _record(
    metric: dict[str, object],
    outcome: Any,
    *,
    session_date: date,
    start_session: date,
    symbol: str,
) -> None:
    metric["fired"] = int(metric["fired"]) + 1
    status_counts = Counter(metric["status_counts"])
    status_counts[str(outcome.status)] += 1
    metric["status_counts"] = dict(status_counts)
    direction_counts = Counter(metric["direction_counts"])
    direction_counts[str(outcome.direction)] += 1
    metric["direction_counts"] = dict(direction_counts)
    mask = int(str(metric["session_bitset_hex"]), 16)
    offset = (session_date - start_session).days
    if offset < 0:
        raise B35DevelopmentReplayError("perturbation session precedes frozen start")
    metric["session_bitset_hex"] = hex(mask | (1 << offset))
    symbols = set(metric["symbols"])
    symbols.add(symbol)
    metric["symbols"] = sorted(symbols)
    if not outcome.comparable:
        metric["noncomparable"] = int(metric["noncomparable"]) + 1
        return
    metric["comparable"] = int(metric["comparable"]) + 1
    gross = float(outcome.gross_directional_return)
    metric["gross_return_sum"] = float(metric["gross_return_sum"]) + gross
    risk = outcome.risk_multiple
    if risk is not None:
        metric["risk_multiple_sum"] = float(metric["risk_multiple_sum"]) + float(risk)
    if outcome.maximum_favorable_excursion is not None:
        metric["mfe_sum"] = float(metric["mfe_sum"]) + float(outcome.maximum_favorable_excursion)
    if outcome.maximum_adverse_excursion is not None:
        metric["mae_sum"] = float(metric["mae_sum"]) + float(outcome.maximum_adverse_excursion)
    sums = dict(metric["net_return_sums_by_cost_bps"])
    for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS:
        value = float(outcome.net_directional_returns_by_cost_bps[str(cost)])
        sums[str(cost)] = float(sums[str(cost)]) + value
    metric["net_return_sums_by_cost_bps"] = sums
    if float(outcome.net_directional_returns_by_cost_bps["50"]) > 0:
        metric["wins_50bps"] = int(metric["wins_50bps"]) + 1


def _baseline_setup_by_strategy(
    canonical_setups: Sequence[IntradaySetupResult],
) -> dict[str, IntradaySetupResult]:
    result = {item.strategy_id: item for item in canonical_setups}
    if len(result) != len(canonical_setups):
        raise B35DevelopmentReplayError(
            "canonical B35 unexpectedly fired one strategy multiple times per symbol/session"
        )
    return result


def _evaluate_variant_setups(
    bars: Sequence[Any],
    *,
    session_date: date,
    history: _SymbolHistory,
    symbol_split_dates: Sequence[date],
    canonical_setups: Sequence[IntradaySetupResult],
) -> dict[str, IntradaySetupResult]:
    found: dict[str, IntradaySetupResult] = {}
    canonical = _baseline_setup_by_strategy(canonical_setups)
    prior = history.daily[-1] if history.daily else None
    if prior is None:
        return found

    for multiplier in ROBUSTNESS_PERTURBATIONS["gap_threshold_multiplier"]:
        variant_id = (
            f"gap_threshold_multiplier:{float(multiplier):.1f}:"
            "b34_gap_continuation_v1"
        )
        if float(multiplier) == 1.0:
            setup = canonical.get("b34_gap_continuation_v1")
        else:
            setup = _gap_variant(
                bars,
                session_date=session_date,
                prior_close=float(prior.close),
                symbol_split_dates=symbol_split_dates,
                prior_session=prior.session_date,
                multiplier=float(multiplier),
            )
        if setup is not None:
            found[variant_id] = setup

    for minutes in ROBUSTNESS_PERTURBATIONS["opening_range_minutes"]:
        variant_id = (
            f"opening_range_minutes:{int(minutes)}:"
            "b34_opening_range_breakout_15m_v1"
        )
        setup = (
            canonical.get("b34_opening_range_breakout_15m_v1")
            if int(minutes) == 15
            else _opening_range_variant(
                bars, session_date=session_date, minutes=int(minutes)
            )
        )
        if setup is not None:
            found[variant_id] = setup

    if len(history.premarket) >= PREMARKET_LOOKBACK_SESSIONS:
        prior_pm = history.premarket[-PREMARKET_LOOKBACK_SESSIONS:]
        pm_split_free = not _split_between(
            symbol_split_dates, prior_pm[0][0], session_date
        )
        prior_pm_values = [value for _day, value in prior_pm]
        for multiplier in ROBUSTNESS_PERTURBATIONS[
            "premarket_relvol_threshold_multiplier"
        ]:
            variant_id = (
                f"premarket_relvol_threshold_multiplier:{float(multiplier):.1f}:"
                "b34_premarket_relvol_consolidation_v1"
            )
            setup = (
                canonical.get("b34_premarket_relvol_consolidation_v1")
                if float(multiplier) == 1.0
                else _premarket_relvol_variant(
                    bars,
                    session_date=session_date,
                    prior_premarket_volumes=prior_pm_values,
                    split_free_lookback=pm_split_free,
                    relvol_multiplier=float(multiplier),
                )
            )
            if setup is not None:
                found[variant_id] = setup

        for multiplier in ROBUSTNESS_PERTURBATIONS[
            "premarket_consolidation_range_multiplier"
        ]:
            variant_id = (
                f"premarket_consolidation_range_multiplier:{float(multiplier):.1f}:"
                "b34_premarket_relvol_consolidation_v1"
            )
            setup = (
                canonical.get("b34_premarket_relvol_consolidation_v1")
                if float(multiplier) == 1.0
                else _premarket_relvol_variant(
                    bars,
                    session_date=session_date,
                    prior_premarket_volumes=prior_pm_values,
                    split_free_lookback=pm_split_free,
                    consolidation_multiplier=float(multiplier),
                )
            )
            if setup is not None:
                found[variant_id] = setup

    if len(history.daily) >= HVD_DAILY_LOOKBACK_SESSIONS:
        prior_daily = history.daily[-HVD_DAILY_LOOKBACK_SESSIONS:]
        daily_split_free = not _split_between(
            symbol_split_dates, prior_daily[0].session_date, session_date
        )
        daily_volumes = [item.regular_volume for item in prior_daily]
        for multiplier in ROBUSTNESS_PERTURBATIONS[
            "premarket_consolidation_range_multiplier"
        ]:
            variant_id = (
                f"premarket_consolidation_range_multiplier:{float(multiplier):.1f}:"
                "b34_highest_volume_day_style_v1"
            )
            setup = (
                canonical.get("b34_highest_volume_day_style_v1")
                if float(multiplier) == 1.0
                else _hvd_consolidation_variant(
                    bars,
                    session_date=session_date,
                    prior_regular_daily_volumes=daily_volumes,
                    split_free_lookback=daily_split_free,
                    consolidation_multiplier=float(multiplier),
                )
            )
            if setup is not None:
                found[variant_id] = setup
    return found


def _validate_group_baseline_parity(
    metrics: dict[str, dict[str, object]],
    canonical_strategy_counts: dict[str, dict[str, int]],
) -> None:
    for variant in TARGETED_VARIANTS:
        if not variant.baseline:
            continue
        expected = canonical_strategy_counts[variant.strategy_id]
        metric = metrics[variant.variant_id]
        actual = (
            int(metric["fired"]),
            int(metric["comparable"]),
            int(metric["noncomparable"]),
        )
        target = (
            int(expected["evaluated_fired"]),
            int(expected["comparable"]),
            int(expected["noncomparable"]),
        )
        if actual != target:
            raise B35DevelopmentReplayError(
                f"targeted perturbation baseline parity failed for {variant.variant_id}: "
                f"{actual!r} != {target!r}"
            )


def _run_group_task(task: B35PerturbationGroupTask) -> dict[str, object]:
    source = parallel._WORKER_SOURCE
    split_evidence = parallel._WORKER_SPLIT_EVIDENCE
    if source is None or split_evidence is None:
        raise B35DevelopmentReplayError("B35 perturbation worker was not initialized")
    if split_evidence.fingerprint != task.split_evidence_fingerprint:
        raise B35DevelopmentReplayError("B35 perturbation split fingerprint drifted")

    variants_by_id = {item.variant_id: item for item in TARGETED_VARIANTS}
    metrics = {
        item.variant_id: _metric_template(item)
        for item in TARGETED_VARIANTS
    }
    histories = {symbol: _SymbolHistory.empty() for symbol in task.units[0].symbols}

    for unit in task.units:
        frame = source.load_unit(
            unit,
            start_session=task.start_session,
            end_session=task.end_session,
        )
        if frame.empty:
            continue
        frame["session_date"] = pd.to_datetime(
            frame["session_date"], errors="raise"
        ).dt.date
        for (symbol, session_date), session_frame in frame.groupby(
            ["symbol", "session_date"], sort=True, observed=True
        ):
            symbol = str(symbol)
            if symbol not in histories:
                raise B35DevelopmentReplayError(
                    f"perturbation unit emitted symbol outside frozen batch: {symbol}"
                )
            if not isinstance(session_date, date):
                raise B35DevelopmentReplayError(
                    "perturbation session date is not a date"
                )
            bars = _canonical_bars(session_frame)
            current_open = _current_regular_open(bars, session_date)
            if current_open is None:
                pm_volume = _premarket_volume(bars, session_date)
                if pm_volume is not None:
                    histories[symbol].append_premarket(session_date, pm_volume)
                continue
            symbol_splits = split_evidence.split_dates_by_symbol.get(symbol, ())
            canonical_setups = _evaluate_setups(
                bars,
                session_date=session_date,
                history=histories[symbol],
                symbol_split_dates=symbol_splits,
            )

            for setup in canonical_setups:
                for delay in ROBUSTNESS_PERTURBATIONS["entry_delay_minutes"]:
                    variant_id = (
                        f"entry_delay_minutes:{int(delay)}:{setup.strategy_id}"
                    )
                    shifted = _shift_setup_for_entry_delay(
                        setup, bars, session_date, int(delay)
                    )
                    outcome = simulate_intraday_outcome(
                        shifted,
                        bars,
                        symbol=symbol,
                        session_date=session_date,
                    )
                    _record(
                        metrics[variant_id],
                        outcome,
                        session_date=session_date,
                        start_session=task.start_session,
                        symbol=symbol,
                    )

            setup_variants = _evaluate_variant_setups(
                bars,
                session_date=session_date,
                history=histories[symbol],
                symbol_split_dates=symbol_splits,
                canonical_setups=canonical_setups,
            )
            for variant_id, setup in setup_variants.items():
                if variant_id not in variants_by_id:
                    raise B35DevelopmentReplayError(
                        f"unexpected perturbation variant: {variant_id}"
                    )
                outcome = simulate_intraday_outcome(
                    setup,
                    bars,
                    symbol=symbol,
                    session_date=session_date,
                )
                _record(
                    metrics[variant_id],
                    outcome,
                    session_date=session_date,
                    start_session=task.start_session,
                    symbol=symbol,
                )

            pm_volume = _premarket_volume(bars, session_date)
            if pm_volume is not None:
                histories[symbol].append_premarket(session_date, pm_volume)
            current_epoch = _split_epoch(symbol_splits, session_date)
            daily_summary = summarize_regular_session(
                bars,
                session_date=session_date,
                split_factor=current_epoch,
            )
            if daily_summary is not None:
                histories[symbol].append_daily(daily_summary)

    _validate_group_baseline_parity(metrics, task.canonical_strategy_counts)

    output_path = Path(task.output_path)
    payload = {
        "contract": B35_TARGETED_PERTURBATION_CONTRACT,
        "status": "COMPLETE",
        "targeted_perturbation_fingerprint": TARGETED_PERTURBATION_FINGERPRINT,
        "canonical_group_fingerprint": task.canonical_group_fingerprint,
        "perturbation_group_fingerprint": task.perturbation_group_fingerprint,
        "source_fingerprint": task.source_fingerprint,
        "split_evidence_fingerprint": task.split_evidence_fingerprint,
        "development_authorization_id": task.development_authorization_id,
        "targeted_authorization_id": task.targeted_authorization_id,
        "unit_count": len(task.units),
        "metrics": [metrics[item.variant_id] for item in TARGETED_VARIANTS],
        "baseline_parity": "PASS",
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
    }
    temp = unique_temp_path(output_path)
    try:
        atomic_write_text(
            temp,
            json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
            + "\n",
            fsync=True,
        )
        replace_with_retry(temp, output_path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise

    receipt: dict[str, object] = {
        "contract": B35_TARGETED_PERTURBATION_CONTRACT,
        "status": "COMPLETE",
        "targeted_perturbation_fingerprint": TARGETED_PERTURBATION_FINGERPRINT,
        "canonical_group_fingerprint": task.canonical_group_fingerprint,
        "perturbation_group_fingerprint": task.perturbation_group_fingerprint,
        "source_fingerprint": task.source_fingerprint,
        "split_evidence_fingerprint": task.split_evidence_fingerprint,
        "development_authorization_id": task.development_authorization_id,
        "targeted_authorization_id": task.targeted_authorization_id,
        "unit_count": len(task.units),
        "output_path": str(output_path),
        "output_sha256": _sha256_file(output_path),
        "baseline_parity": "PASS",
    }
    receipt["receipt_id"] = _stable_hash(receipt)
    atomic_write_text(
        Path(task.receipt_path),
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    return receipt


def _completed_targeted_group(
    *,
    task: B35PerturbationGroupTask,
) -> dict[str, object] | None:
    output_path = Path(task.output_path)
    receipt_path = Path(task.receipt_path)
    if not receipt_path.is_file():
        if output_path.exists():
            output_path.unlink()
        return None
    value = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise B35DevelopmentReplayError(
            "targeted perturbation group receipt is not an object"
        )
    required = {
        "contract": B35_TARGETED_PERTURBATION_CONTRACT,
        "status": "COMPLETE",
        "targeted_perturbation_fingerprint": TARGETED_PERTURBATION_FINGERPRINT,
        "canonical_group_fingerprint": task.canonical_group_fingerprint,
        "perturbation_group_fingerprint": task.perturbation_group_fingerprint,
        "source_fingerprint": task.source_fingerprint,
        "split_evidence_fingerprint": task.split_evidence_fingerprint,
        "development_authorization_id": task.development_authorization_id,
        "targeted_authorization_id": task.targeted_authorization_id,
        "unit_count": len(task.units),
        "output_path": str(output_path),
        "baseline_parity": "PASS",
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise B35DevelopmentReplayError(
                f"targeted group receipt {key} drifted"
            )
    receipt_id = str(value.get("receipt_id") or "")
    if receipt_id != _stable_hash(
        {key: item for key, item in value.items() if key != "receipt_id"}
    ):
        raise B35DevelopmentReplayError(
            "targeted group receipt self-hash drifted"
        )
    if not output_path.is_file():
        raise B35DevelopmentReplayError(
            "targeted group output is missing"
        )
    if value.get("output_sha256") != _sha256_file(output_path):
        raise B35DevelopmentReplayError(
            "targeted group output hash drifted"
        )
    return value


def _group_fingerprint(
    *,
    canonical_group_fingerprint: str,
    task_units: Sequence[B35DevelopmentUnitBinding],
    targeted_authorization_id: str,
) -> str:
    return _stable_hash(
        {
            "contract": B35_TARGETED_PERTURBATION_CONTRACT,
            "targeted_perturbation_fingerprint": TARGETED_PERTURBATION_FINGERPRINT,
            "accepted_robustness_fingerprint": B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
            "canonical_group_fingerprint": canonical_group_fingerprint,
            "targeted_authorization_id": targeted_authorization_id,
            "units": [
                (unit.unit_id, unit.canonical_sha256)
                for unit in task_units
            ],
        }
    )


def _aggregate_group_outputs(
    group_outputs: Sequence[Path],
) -> list[dict[str, object]]:
    variants = {
        item.variant_id: _metric_template(item)
        for item in TARGETED_VARIANTS
    }
    for path in group_outputs:
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload["metrics"]:
            target = variants[str(item["variant_id"])]
            for field in (
                "fired",
                "comparable",
                "noncomparable",
                "wins_50bps",
            ):
                target[field] = int(target[field]) + int(item[field])
            for field in (
                "gross_return_sum",
                "risk_multiple_sum",
                "mfe_sum",
                "mae_sum",
            ):
                target[field] = float(target[field]) + float(item[field])
            sums = dict(target["net_return_sums_by_cost_bps"])
            for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS:
                key = str(cost)
                sums[key] = float(sums[key]) + float(
                    item["net_return_sums_by_cost_bps"][key]
                )
            target["net_return_sums_by_cost_bps"] = sums
            status = Counter(target["status_counts"])
            status.update(item["status_counts"])
            target["status_counts"] = dict(status)
            directions = Counter(target["direction_counts"])
            directions.update(item["direction_counts"])
            target["direction_counts"] = dict(directions)
            mask = int(str(target["session_bitset_hex"]), 16)
            mask |= int(str(item["session_bitset_hex"]), 16)
            target["session_bitset_hex"] = hex(mask)
            symbols = set(target["symbols"])
            symbols.update(item["symbols"])
            target["symbols"] = sorted(symbols)

    output: list[dict[str, object]] = []
    for variant in TARGETED_VARIANTS:
        item = variants[variant.variant_id]
        comparable = int(item["comparable"])
        fired = int(item["fired"])
        record = {
            key: item[key]
            for key in (
                "variant_id",
                "family",
                "strategy_id",
                "parameter",
                "value",
                "baseline",
                "fired",
                "comparable",
                "noncomparable",
                "wins_50bps",
                "status_counts",
                "direction_counts",
            )
        }
        record["unique_sessions"] = int(
            int(str(item["session_bitset_hex"]), 16).bit_count()
        )
        record["unique_instruments"] = len(item["symbols"])
        record["noncomparable_rate"] = (
            None if fired == 0 else int(item["noncomparable"]) / fired
        )
        record["win_rate_50bps"] = (
            None if comparable == 0 else int(item["wins_50bps"]) / comparable
        )
        record["mean_gross_return"] = (
            None if comparable == 0 else float(item["gross_return_sum"]) / comparable
        )
        record["mean_risk_multiple"] = (
            None if comparable == 0 else float(item["risk_multiple_sum"]) / comparable
        )
        record["mean_mfe"] = (
            None if comparable == 0 else float(item["mfe_sum"]) / comparable
        )
        record["mean_mae"] = (
            None if comparable == 0 else float(item["mae_sum"]) / comparable
        )
        record["mean_net_return_by_cost_bps"] = {
            str(cost): (
                None
                if comparable == 0
                else float(item["net_return_sums_by_cost_bps"][str(cost)])
                / comparable
            )
            for cost in ALL_IN_ROUND_TRIP_COST_GRID_BPS
        }
        output.append(record)
    return output


class B35TargetedPerturbationReplayEngine:
    def __init__(
        self,
        source: B35DevelopmentMinuteSource,
        *,
        execution_profile: ParallelResearchExecutionProfile,
        progress_interval_seconds: float = 60.0,
    ) -> None:
        self.source = source
        self.layout = source.layout
        self.execution_profile = execution_profile
        self.progress_interval_seconds = max(
            0.05, float(progress_interval_seconds)
        )

    @serialized_replay
    def run(
        self,
        plan: B35DevelopmentSourcePlan,
        *,
        output_root: Path,
        authorization: dict[str, object],
    ) -> dict[str, object]:
        validate_source_plan(plan)
        output_root = output_root.resolve()
        groups_root = output_root / "groups"
        groups_root.mkdir(parents=True, exist_ok=True)
        split_evidence = load_b35_split_evidence(self.layout)

        canonical_root = output_root.parents[2]
        development_authorization_path = (
            canonical_root / "development_outcome_authorization.json"
        )
        development_authorization = json.loads(
            development_authorization_path.read_text(encoding="utf-8")
        )
        development_authorization_id = validate_development_authorization(
            development_authorization,
            plan=plan,
            split_evidence=split_evidence,
        )
        required_auth = _authorization_payload(
            plan=plan,
            split_evidence_fingerprint=split_evidence.fingerprint,
            development_authorization_id=development_authorization_id,
        )
        for key, expected in required_auth.items():
            if authorization.get(key) != expected:
                raise B35DevelopmentReplayError(
                    f"targeted perturbation authorization {key} drifted"
                )
        targeted_authorization_id = str(
            authorization.get("authorization_id") or ""
        )
        if targeted_authorization_id != _stable_hash(
            {
                key: value
                for key, value in authorization.items()
                if key != "authorization_id"
            }
        ):
            raise B35DevelopmentReplayError(
                "targeted perturbation authorization self-hash drifted"
            )

        read_start_marker = ensure_read_start_marker(
            output_root,
            source_fingerprint=plan.source_fingerprint,
            split_evidence_fingerprint=split_evidence.fingerprint,
            authorization_id=targeted_authorization_id,
        )

        canonical_groups = _group_units(
            plan,
            split_evidence_fingerprint=split_evidence.fingerprint,
            authorization_id=development_authorization_id,
        )
        tasks: list[B35PerturbationGroupTask] = []
        for canonical_group_fingerprint, units in canonical_groups:
            canonical_token = canonical_group_fingerprint[:20]
            canonical_output = canonical_root / "groups" / f"{canonical_token}.jsonl"
            canonical_receipt_path = (
                canonical_root / "groups" / f"{canonical_token}.receipt.json"
            )
            canonical_receipt = _completed_group(
                canonical_receipt_path,
                canonical_output,
                units=units,
                group_fingerprint=canonical_group_fingerprint,
                source_fingerprint=plan.source_fingerprint,
                split_evidence_fingerprint=split_evidence.fingerprint,
                authorization_id=development_authorization_id,
            )
            if canonical_receipt is None:
                raise B35DevelopmentReplayError(
                    "targeted perturbation replay requires every canonical B35 group receipt"
                )
            perturbation_group_fingerprint = _group_fingerprint(
                canonical_group_fingerprint=canonical_group_fingerprint,
                task_units=units,
                targeted_authorization_id=targeted_authorization_id,
            )
            token = perturbation_group_fingerprint[:20]
            tasks.append(
                B35PerturbationGroupTask(
                    canonical_group_fingerprint=canonical_group_fingerprint,
                    perturbation_group_fingerprint=perturbation_group_fingerprint,
                    units=units,
                    start_session=plan.start_session,
                    end_session=plan.end_session,
                    source_fingerprint=plan.source_fingerprint,
                    split_evidence_fingerprint=split_evidence.fingerprint,
                    development_authorization_id=development_authorization_id,
                    targeted_authorization_id=targeted_authorization_id,
                    canonical_strategy_counts=canonical_receipt["strategy_counts"],
                    output_path=str(groups_root / f"{token}.json"),
                    receipt_path=str(groups_root / f"{token}.receipt.json"),
                )
            )

        receipts: dict[str, dict[str, object]] = {}
        pending: deque[B35PerturbationGroupTask] = deque()
        reused_units = 0
        for task in tasks:
            existing = _completed_targeted_group(task=task)
            if existing is None:
                pending.append(task)
            else:
                receipts[task.perturbation_group_fingerprint] = existing
                reused_units += int(existing["unit_count"])

        started_at_utc = datetime.now(UTC).isoformat()
        started = monotonic_time.monotonic()
        computed_groups = 0
        computed_units = 0
        reused_groups = len(receipts)
        total_groups = len(tasks)
        total_units = len(plan.units)

        def emit(
            state: str,
            active: list[str],
            error: str | None = None,
        ) -> None:
            payload = parallel._build_progress_payload(
                state=state,
                started_at_utc=started_at_utc,
                started_monotonic=started,
                profile=self.execution_profile,
                groups_total=total_groups,
                groups_completed=len(receipts),
                groups_reused_at_start=reused_groups,
                groups_computed_this_run=computed_groups,
                units_total=total_units,
                units_completed=reused_units + computed_units,
                units_reused_at_start=reused_units,
                units_computed_this_run=computed_units,
                active_group_tokens=active,
                last_error=error,
            )
            payload["contract"] = (
                "atlas-b35-targeted-perturbation-progress-v1-non-authoritative"
            )
            payload["targeted_perturbation_fingerprint"] = (
                TARGETED_PERTURBATION_FINGERPRINT
            )
            parallel._write_and_print_progress(output_root, payload)

        emit("RUNNING", [])
        executor: ProcessPoolExecutor | None = None
        inflight: dict[
            Future[dict[str, object]], B35PerturbationGroupTask
        ] = {}
        try:
            if pending:
                executor = ProcessPoolExecutor(
                    max_workers=self.execution_profile.replay_workers,
                    initializer=parallel._init_b35_worker,
                    initargs=(
                        str(self.source.settings.project_root),
                        self.execution_profile.duckdb_threads_per_worker,
                    ),
                )

                def fill() -> None:
                    while (
                        pending
                        and len(inflight)
                        < self.execution_profile.replay_workers
                    ):
                        task = pending.popleft()
                        inflight[executor.submit(_run_group_task, task)] = task

                fill()
                while inflight:
                    done, _ = wait(
                        tuple(inflight),
                        timeout=self.progress_interval_seconds,
                        return_when=FIRST_COMPLETED,
                    )
                    if not done:
                        emit(
                            "RUNNING",
                            [item.token for item in inflight.values()],
                        )
                        continue
                    for future in done:
                        task = inflight.pop(future)
                        receipt = future.result()
                        receipts[
                            task.perturbation_group_fingerprint
                        ] = receipt
                        computed_groups += 1
                        computed_units += int(receipt["unit_count"])
                    fill()
                    emit(
                        "RUNNING",
                        [item.token for item in inflight.values()],
                    )
        except KeyboardInterrupt:
            emit(
                "INTERRUPTING",
                [item.token for item in inflight.values()],
            )
            for future in inflight:
                future.cancel()
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)
                executor = None
            emit("INTERRUPTED", [])
            raise
        except BaseException as exc:
            for future in inflight:
                future.cancel()
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)
                executor = None
            emit("FAILED", [], f"{type(exc).__name__}: {exc}")
            raise
        finally:
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)

        if len(receipts) != total_groups:
            raise B35DevelopmentReplayError(
                "targeted perturbation receipt count did not reach frozen group total"
            )

        group_outputs = [
            Path(task.output_path)
            for task in tasks
        ]
        variant_results = _aggregate_group_outputs(group_outputs)
        receipt_ids = sorted(str(item["receipt_id"]) for item in receipts.values())
        summary: dict[str, object] = {
            "contract": B35_TARGETED_PERTURBATION_CONTRACT,
            "status": "COMPLETE",
            "completed_at_utc": datetime.now(UTC).isoformat(),
            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
            "accepted_robustness_fingerprint": B35_ACCEPTED_ROBUSTNESS_FINGERPRINT,
            "targeted_perturbation_fingerprint": TARGETED_PERTURBATION_FINGERPRINT,
            "source_fingerprint": plan.source_fingerprint,
            "split_evidence_fingerprint": split_evidence.fingerprint,
            "development_authorization_id": development_authorization_id,
            "targeted_authorization_id": targeted_authorization_id,
            "read_start_marker_id": str(read_start_marker["marker_id"]),
            "group_count": total_groups,
            "source_unit_count": total_units,
            "group_receipt_ids": receipt_ids,
            "variant_count": len(TARGETED_VARIANTS),
            "variant_results": variant_results,
            "baseline_equivalence": "PASS_ALL_GROUPS",
            "one_axis_at_a_time": True,
            "selector_refit": False,
            "canonical_replay_rewritten": False,
            "consumed_master_rows_read": 0,
            "future_blind_rows_read": 0,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "strategy_promotion": False,
            "selector_promotion": False,
        }
        summary["run_fingerprint"] = _stable_hash(
            {
                key: value
                for key, value in summary.items()
                if key != "completed_at_utc"
            }
        )
        atomic_write_text(
            output_root / "summary.json",
            json.dumps(summary, indent=2, sort_keys=True, default=str)
            + "\n",
            fsync=True,
        )
        emit("COMPLETE", [])
        return summary
