from __future__ import annotations

"""Offline scenario sweeps over the existing explicitly SYNTHETIC account replay.

This runner makes no market-data/broker calls, cannot read provider archives, and
never labels fixture outcomes as historical, PAPER, or LIVE performance.
"""

from dataclasses import asdict, dataclass, fields, replace
from datetime import datetime
from hashlib import sha256
from itertools import product
import json
import re
from typing import Any, Mapping, Sequence

from packages.simulation.multiyear_offline_account_replay_v1 import (
    ORIGIN, MODES, ReplayPolicy, ReplaySignal, replay_synthetic_account,
)

CONTRACT = "atlas-offline-strategy-sweep-fastlane-v1-synthetic-only"
MAX_STRATEGIES = 12
MAX_CASES = 20000
MAX_VARIANTS = 64
SWEEP_FIELDS = frozenset({
    "fraction_of_available_cash", "max_open_positions",
    "maximum_units_per_position", "stock_slippage_bps",
    "option_slippage_per_share", "stock_entry_fee", "stock_exit_fee",
    "option_entry_fee_per_contract", "option_exit_fee_per_contract",
})
IDENTIFIER = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")


class FastlaneError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StrategyFixture:
    strategy_id: str
    mode: str
    signals: tuple[ReplaySignal, ...]


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             default=str).encode("utf-8")).hexdigest()


def _validate_strategies(strategies: Sequence[StrategyFixture]) -> None:
    if not isinstance(strategies, (tuple, list)) or not 1 <= len(strategies) <= MAX_STRATEGIES:
        raise FastlaneError("STRATEGY_COUNT_OUT_OF_BOUNDS")
    if len({s.strategy_id for s in strategies}) != len(strategies):
        raise FastlaneError("DUPLICATE_STRATEGY_ID")
    if sum(len(s.signals) for s in strategies) > MAX_CASES:
        raise FastlaneError("CASE_BUDGET_EXCEEDED")
    for spec in strategies:
        if (not isinstance(spec, StrategyFixture)
                or not isinstance(spec.strategy_id, str)
                or IDENTIFIER.fullmatch(spec.strategy_id) is None
                or spec.mode not in MODES or not isinstance(spec.signals, tuple)
                or not spec.signals):
            raise FastlaneError("INVALID_STRATEGY_FIXTURE")
        for signal in spec.signals:
            if not isinstance(signal, ReplaySignal) or signal.origin != ORIGIN:
                raise FastlaneError("HISTORICAL_SOURCE_NOT_ADMITTED")
            signal.validate()
        if len({s.case_id for s in spec.signals}) != len(spec.signals):
            raise FastlaneError("DUPLICATE_CASE_ID_WITHIN_STRATEGY")


def _policies(grid: Mapping[str, list[Any]]) -> list[tuple[dict[str, Any], ReplayPolicy]]:
    if not isinstance(grid, dict) or not grid or set(grid) - SWEEP_FIELDS:
        raise FastlaneError("INVALID_POLICY_GRID")
    keys = sorted(grid)
    choices: list[list[Any]] = []
    variants = 1
    example = ReplayPolicy()
    for key in keys:
        vals = grid[key]
        if not isinstance(vals, list) or not 1 <= len(vals) <= 8:
            raise FastlaneError("GRID_AXIS_OUT_OF_BOUNDS")
        if len({(type(v).__name__, str(v)) for v in vals}) != len(vals):
            raise FastlaneError("DUPLICATE_GRID_AXIS_VALUE")
        expected = type(getattr(example, key))
        if any(type(v) is not expected for v in vals):
            raise FastlaneError("GRID_VALUE_TYPE_MISMATCH")
        variants *= len(vals)
        if variants > MAX_VARIANTS:
            raise FastlaneError("TOO_MANY_SCENARIOS")
        choices.append(vals)
    result = []
    for values in product(*choices):
        overrides = dict(zip(keys, values))
        policy = replace(example, **overrides)
        policy.validate()
        result.append((overrides, policy))
    return result


def _summary(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "case_count": result["original_case_denominator"],
        "synthetic_round_trips": result["synthetic_round_trips"],
        "modeled_realized_pnl": result["modeled_realized_pnl"],
        "ending_cash": result["ending_cash"],
        "ending_equity": result["ending_equity"],
        "open_positions": result["end_open_positions"],
        "by_year": result["by_year"],
        "historical_account_pnl_authority": False,
    }


def run_fixture_sweep(
    strategies: Sequence[StrategyFixture], policy_grid: Mapping[str, list[Any]],
    *, include_combined: bool = True, as_of_utc: datetime | None = None,
) -> dict[str, Any]:
    """Run single strategies independently and same-mode strategies with shared cash.

    Combined results use a single replay account and account policy, NOT the sum
    of separately capitalized single-strategy P&Ls. Mixed STOCK/CALL/PUT
    portfolios intentionally stay blocked until a true multi-asset adapter exists.
    No configuration is ranked or promoted based on these fixture outcomes.
    """
    _validate_strategies(strategies)
    if type(include_combined) is not bool:
        raise FastlaneError("INVALID_COMBINED_FLAG")
    policies = _policies(policy_grid)
    modes = {s.mode for s in strategies}
    can_combine = len(modes) == 1 and len(strategies) > 1
    combined = []
    if include_combined and can_combine:
        combined = [signal for s in strategies for signal in s.signals]
        if len({s.case_id for s in combined}) != len(combined):
            raise FastlaneError("CROSS_STRATEGY_CASE_COLLISION")
    output: list[dict[str, Any]] = []
    for overrides, policy in policies:
        row: dict[str, Any] = {
            "scenario_id": _fingerprint(overrides)[:16],
            "policy_overrides": overrides,
            "individual": {},
        }
        for spec in strategies:
            replay = replay_synthetic_account(list(spec.signals), mode=spec.mode,
                                             policy=policy, as_of_utc=as_of_utc)
            row["individual"][spec.strategy_id] = _summary(replay)
        if include_combined and can_combine:
            replay = replay_synthetic_account(combined, mode=strategies[0].mode,
                                             policy=policy, as_of_utc=as_of_utc)
            row["combined_shared_capital"] = _summary(replay)
        output.append(row)
    combined_status = ("NOT_REQUESTED" if not include_combined else
                       "SINGLE_STRATEGY_ONLY" if len(strategies) == 1 else
                       "SAME_MODE_SHARED_CAPITAL_FIXTURE_ONLY" if can_combine else
                       "MIXED_ASSET_COMBINATION_NOT_QUALIFIED")
    result = {
        "contract": CONTRACT,
        "data_origin": ORIGIN,
        "status": "SYNTHETIC_DIAGNOSTIC_ONLY",
        "strategies": [{"strategy_id": x.strategy_id, "mode": x.mode,
                        "case_count": len(x.signals)} for x in strategies],
        "scenario_count": len(output),
        "combined_status": combined_status,
        "as_of_utc": as_of_utc.isoformat() if as_of_utc is not None else None,
        "scenarios": output,
        "provider_requests": 0,
        "broker_requests": 0,
        "historical_performance_qualified": False,
        "strategy_promotions": 0,
        "paper": False, "live": False,
    }
    result["report_fingerprint"] = _fingerprint(result)
    return result
