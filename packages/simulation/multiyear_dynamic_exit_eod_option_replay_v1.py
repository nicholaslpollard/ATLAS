from __future__ import annotations

"""Dynamic-Exit-V1-aligned historical EOD CALL diagnostics.

The selector is rebuilt point-in-time through the safe 2025 boundary using the same
Dynamic Exit V1 algorithm:
- only completed prior folds may train a current fold;
- the current fold is fully assigned before any of its outcomes are revealed;
- the last eight completed folds are eligible training context;
- supported context cells choose the highest positive robust LCB action;
- unsupported/non-positive contexts ABSTAIN.

Option entry remains the accepted first later-session EOD ask.  For selected dynamic
actions, the existing strategy-aligned source mapper resolves the stock STOP/TARGET/TIME
exit session and requires an exact qualified option EOD bid on that same session.

Two outputs are intentionally separated:
1. strict causal account replay, where unresolved exact-exit evidence keeps capital
   occupied because no fallback/settlement rule is invented;
2. paired-observation diagnostics over every dynamically selected source-ready
   entry/exit pair.  The latter is conditional on having both observations and is NOT
   a causal portfolio result.
"""

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path
import statistics
from typing import Any, Sequence

from packages.backtesting.recurrent_successor_daily_exit_sweep import DailyPathCase
from packages.backtesting.recurrent_successor_dynamic_exit_v1 import (
    _choose_action,
    _reveal_action_outcomes,
)
from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    ABSTAIN_ACTION_ID,
    DYNAMIC_EXIT_ACTIONS,
    LOOKBACK_COMPLETED_FOLDS,
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
    dynamic_exit_action_id,
)
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    SCENARIO_CONTRACT as STATIC_SCENARIO_CONTRACT,
)

ASSIGNMENT_CONTRACT = "atlas-multiyear-bounded-dynamic-exit-assignments-v1"
SCENARIO_CONTRACT = "atlas-multiyear-dynamic-exit-eod-option-scenario-v1"
REPLAY_CONTRACT = "atlas-multiyear-dynamic-exit-eod-option-replay-v1"
DIAGNOSTIC_CONTRACT = "atlas-multiyear-dynamic-exit-eod-option-paired-diagnostics-v1"
ASSIGNMENT_REL = "data/options/derived/multiyear_bounded_dynamic_exit_assignments_v1"
SCENARIO_REL = "data/options/derived/multiyear_dynamic_exit_eod_option_scenario_v1"
REPLAY_REL = "data/options/derived/multiyear_dynamic_exit_eod_option_replay_v1"
DIAGNOSTIC_REL = (
    "data/options/derived/multiyear_dynamic_exit_eod_option_paired_diagnostics_v1"
)


class DynamicExitEodOptionReplayError(ValueError):
    pass


def build_bounded_dynamic_exit_assignments(
    daily_cases: Sequence[DailyPathCase],
    *,
    target_start: date,
    safe_end: date,
) -> dict[str, Any]:
    """Rebuild Dynamic Exit V1 choices through safe_end with no 2026 outcomes."""
    if not daily_cases:
        raise DynamicExitEodOptionReplayError("no bounded dynamic-exit daily cases")
    indexed = list(daily_cases)
    if any(case.opportunity.signal_session > safe_end for case in indexed):
        raise DynamicExitEodOptionReplayError(
            "bounded dynamic selector received post-safe-end case"
        )

    by_fold: dict[int, list[int]] = defaultdict(list)
    for index, case in enumerate(indexed):
        by_fold[int(case.opportunity.fold_id)].append(index)
    ordered_folds = sorted(by_fold)
    known_outcomes: dict[tuple[int, str], float] = {}
    rows: list[dict[str, Any]] = []

    for fold_id in ordered_folds:
        training_folds = [
            prior
            for prior in ordered_folds
            if fold_id - LOOKBACK_COMPLETED_FOLDS <= prior < fold_id
        ]
        training_indexes = [
            index
            for prior in training_folds
            for index in by_fold[prior]
        ]
        current_indexes = by_fold[fold_id]

        frozen: list[tuple[int, Any]] = []
        for current_index in current_indexes:
            choice = _choose_action(
                cases=indexed,
                current_index=current_index,
                training_indexes=training_indexes,
                outcomes=known_outcomes,
            )
            frozen.append((current_index, choice))

        # Current-fold paths become available only after every current decision is frozen.
        _reveal_action_outcomes(indexed, current_indexes, known_outcomes)

        for current_index, choice in frozen:
            case = indexed[current_index]
            item = case.opportunity
            if not target_start <= item.signal_session <= safe_end:
                continue
            row = {
                "opportunity_id": item.opportunity_id,
                "fold_id": int(item.fold_id),
                "policy_id": item.policy_id,
                "economic_family_id": item.economic_family_id,
                "ticker": item.ticker,
                "instrument_id": item.instrument_id,
                "signal_session": item.signal_session.isoformat(),
                "selector_score": item.selector_score,
                "action_id": choice.action_id,
                "stop_fraction": choice.stop_fraction,
                "target_fraction": choice.target_fraction,
                "fallback_level": choice.fallback_level,
                "context_dimensions": list(choice.context_dimensions),
                "context_key": list(choice.context_key),
                "training_cases": choice.training_cases,
                "training_sessions": choice.training_sessions,
                "training_instruments": choice.training_instruments,
                "training_fold_min": choice.training_fold_min,
                "training_fold_max": choice.training_fold_max,
                "training_cutoff_session": (
                    None
                    if choice.training_cutoff_session is None
                    else choice.training_cutoff_session.isoformat()
                ),
                "selected_lcb_net_return": choice.selected_lcb_net_return,
                "selected_mean_trade_net_return":
                    choice.selected_mean_trade_net_return,
                "selected_probability_positive":
                    choice.selected_probability_positive,
                "reason": choice.reason,
                "current_case_future_path_used_for_selection": False,
                "current_fold_outcomes_used_for_selection": False,
            }
            rows.append(row)

    rows.sort(key=lambda row: (row["signal_session"], row["opportunity_id"]))
    if len({row["opportunity_id"] for row in rows}) != len(rows):
        raise DynamicExitEodOptionReplayError(
            "bounded dynamic assignment identities are not unique"
        )

    selected = [row for row in rows if row["action_id"] != ABSTAIN_ACTION_ID]
    action_counts = Counter(str(row["action_id"]) for row in selected)
    abstain_reasons = Counter(
        str(row["reason"])
        for row in rows
        if row["action_id"] == ABSTAIN_ACTION_ID
    )
    result = {
        "contract": ASSIGNMENT_CONTRACT,
        "status": "BOUNDED_DYNAMIC_EXIT_V1_ASSIGNMENTS_NO_2026_OUTCOMES",
        "source_dynamic_exit_contract_fingerprint":
            RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
        "training_source_start": min(
            case.opportunity.signal_session for case in indexed
        ).isoformat(),
        "target_start": target_start.isoformat(),
        "safe_end": safe_end.isoformat(),
        "lookback_completed_folds": LOOKBACK_COMPLETED_FOLDS,
        "available_cases_through_safe_end": len(indexed),
        "target_assignment_cases": len(rows),
        "selected_cases": len(selected),
        "abstained_cases": len(rows) - len(selected),
        "selection_rate": len(selected) / len(rows) if rows else 0.0,
        "selected_action_counts": dict(sorted(action_counts.items())),
        "abstain_reasons": dict(sorted(abstain_reasons.items())),
        "current_case_future_path_used_for_selection": False,
        "current_fold_outcomes_used_for_selection": False,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "strategy_evidence_authority": False,
        "rows": rows,
    }
    result["assignment_fingerprint"] = _fingerprint(result)
    return result


def combine_dynamic_action_scenarios(
    base_scenario: dict[str, Any],
    assignments: dict[str, Any],
    action_scenarios: dict[str, dict[str, Any]],
    *,
    safe_last_signal_session: date,
) -> dict[str, Any]:
    """Select each case from its pre-decided dynamic action scenario."""
    _check_signature(base_scenario, "scenario_fingerprint")
    _check_signature(assignments, "assignment_fingerprint")
    if (
        assignments.get("contract") != ASSIGNMENT_CONTRACT
        or assignments.get("protected_2026_outcomes_read") != 0
        or assignments.get("provider_requests") != 0
        or assignments.get("current_case_future_path_used_for_selection") is not False
        or assignments.get("current_fold_outcomes_used_for_selection") is not False
    ):
        raise DynamicExitEodOptionReplayError("dynamic assignment authority changed")

    assignment_by_id = {
        row["opportunity_id"]: row for row in assignments["rows"]
    }
    base_by_id = {row["case_id"]: row for row in base_scenario["cases"]}
    if len(base_by_id) != base_scenario["original_case_denominator"]:
        raise DynamicExitEodOptionReplayError("base option scenario denominator changed")

    action_case_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for action_id, scenario in action_scenarios.items():
        _check_signature(scenario, "scenario_fingerprint")
        if (
            scenario.get("contract") != STATIC_SCENARIO_CONTRACT
            or scenario.get("base_scenario_fingerprint")
                != base_scenario["scenario_fingerprint"]
            or scenario.get("safe_last_signal_session")
                != safe_last_signal_session.isoformat()
            or scenario.get("provider_requests") != 0
            or scenario.get("protected_2026_outcomes_read") != 0
        ):
            raise DynamicExitEodOptionReplayError(
                "dynamic action source scenario changed"
            )
        rows = {row["case_id"]: row for row in scenario["cases"]}
        if set(rows) != set(base_by_id):
            raise DynamicExitEodOptionReplayError(
                "dynamic action scenario denominator changed"
            )
        action_case_maps[action_id] = rows

    valid_actions = {
        dynamic_exit_action_id(stop, target)
        for stop, target in DYNAMIC_EXIT_ACTIONS
    }
    if not set(action_scenarios).issubset(valid_actions):
        raise DynamicExitEodOptionReplayError("unexpected dynamic action scenario")

    counts: Counter[str] = Counter()
    action_counts: Counter[str] = Counter()
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    output_cases: list[dict[str, Any]] = []

    for base in base_scenario["cases"]:
        cid = base["case_id"]
        signal_day = date.fromisoformat(base["signal_session"])
        assignment = assignment_by_id.get(cid)

        if signal_day > safe_last_signal_session:
            result = {
                "case_id": cid,
                "year": base["year"],
                "ticker": base["ticker"],
                "policy_id": base["policy_id"],
                "signal_session": base["signal_session"],
                "decision_at_utc": base["decision_at_utc"],
                "strategy_exit_policy": {
                    "policy_id": "DYNAMIC_EXIT_V1",
                    "action_id": None,
                },
                "economic_family_id": None,
                "selector_score": None,
                "stock_exit": None,
                "call": base.get("call"),
                "strategy_aligned_status": "PROTECTED_2026_STOCK_HORIZON_WITHHELD",
                "strategy_exit_option_mark": None,
                "dynamic_assignment": None,
                "future_option_exit_used_for_entry_admission": False,
                "protected_2026_outcomes_read": 0,
            }
        elif assignment is None:
            result = {
                "case_id": cid,
                "year": base["year"],
                "ticker": base["ticker"],
                "policy_id": base["policy_id"],
                "signal_session": base["signal_session"],
                "decision_at_utc": base["decision_at_utc"],
                "strategy_exit_policy": {
                    "policy_id": "DYNAMIC_EXIT_V1",
                    "action_id": None,
                },
                "economic_family_id": None,
                "selector_score": None,
                "stock_exit": None,
                "call": base.get("call"),
                "strategy_aligned_status":
                    "DYNAMIC_EXIT_INELIGIBLE_NO_PRIOR_PATH_ASSIGNMENT",
                "strategy_exit_option_mark": None,
                "dynamic_assignment": None,
                "future_option_exit_used_for_entry_admission": False,
                "protected_2026_outcomes_read": 0,
            }
        elif assignment["action_id"] == ABSTAIN_ACTION_ID:
            result = {
                "case_id": cid,
                "year": base["year"],
                "ticker": base["ticker"],
                "policy_id": base["policy_id"],
                "signal_session": base["signal_session"],
                "decision_at_utc": base["decision_at_utc"],
                "strategy_exit_policy": {
                    "policy_id": "DYNAMIC_EXIT_V1",
                    "action_id": ABSTAIN_ACTION_ID,
                },
                "economic_family_id": assignment["economic_family_id"],
                "selector_score": assignment["selector_score"],
                "stock_exit": None,
                "call": base.get("call"),
                "strategy_aligned_status": "DYNAMIC_EXIT_ABSTAIN",
                "strategy_exit_option_mark": None,
                "dynamic_assignment": assignment,
                "future_option_exit_used_for_entry_admission": False,
                "protected_2026_outcomes_read": 0,
            }
        else:
            action_id = str(assignment["action_id"])
            scenario_cases = action_case_maps.get(action_id)
            if scenario_cases is None:
                raise DynamicExitEodOptionReplayError(
                    f"missing source scenario for selected dynamic action {action_id}"
                )
            result = dict(scenario_cases[cid])
            result["strategy_exit_policy"] = {
                "policy_id": "DYNAMIC_EXIT_V1",
                "action_id": action_id,
                "stop_fraction": assignment["stop_fraction"],
                "target_fraction": assignment["target_fraction"],
            }
            result["dynamic_assignment"] = assignment
            action_counts[action_id] += 1

        status = str(result["strategy_aligned_status"])
        counts[status] += 1
        by_year[result["year"]][status] += 1
        output_cases.append(result)

    if len(output_cases) != base_scenario["original_case_denominator"]:
        raise DynamicExitEodOptionReplayError("dynamic option denominator changed")

    report = {
        "contract": SCENARIO_CONTRACT,
        "status": "MODELED_DYNAMIC_EXIT_V1_EOD_CALL_SCENARIO_NO_FILL_AUTHORITY",
        "base_scenario_fingerprint": base_scenario["scenario_fingerprint"],
        "dynamic_assignment_fingerprint": assignments["assignment_fingerprint"],
        "source_dynamic_exit_contract_fingerprint":
            assignments["source_dynamic_exit_contract_fingerprint"],
        "original_case_denominator": base_scenario["original_case_denominator"],
        "safe_last_signal_session": safe_last_signal_session.isoformat(),
        "strategy_exit_policy": {
            "policy_id": "DYNAMIC_EXIT_V1",
            "action_set": sorted(valid_actions),
            "abstain_action": ABSTAIN_ACTION_ID,
            "selection": "STRICTLY_PRIOR_COMPLETED_FOLDS_POINT_IN_TIME_CONTEXT",
        },
        "dynamic_selected_cases": sum(action_counts.values()),
        "dynamic_abstained_cases": counts["DYNAMIC_EXIT_ABSTAIN"],
        "dynamic_selected_action_counts": dict(sorted(action_counts.items())),
        "source_ready_strategy_aligned_round_trips":
            counts["STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"],
        "entry_ready_but_exact_strategy_exit_source_gap": (
            counts["STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING"]
            + counts["STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP"]
            + counts["STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW"]
        ),
        "stock_exit_not_after_option_eod_entry":
            counts["STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY"],
        "future_option_exit_used_for_entry_admission": False,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "by_status": dict(sorted(counts.items())),
        "by_year": {
            year: dict(sorted(counter.items()))
            for year, counter in by_year.items()
        },
        "cases": output_cases,
    }
    report["scenario_fingerprint"] = _fingerprint(report)
    return report


def build_paired_observation_diagnostics(
    scenario: dict[str, Any],
    *,
    option_slippage_per_share: str = "0.00",
    option_entry_fee_per_contract: str = "0.65",
    option_exit_fee_per_contract: str = "0.65",
) -> dict[str, Any]:
    """Summarize every exact observed dynamic entry/exit pair, not a portfolio."""
    _check_signature(scenario, "scenario_fingerprint")
    if (
        scenario.get("contract") != SCENARIO_CONTRACT
        or scenario.get("provider_requests") != 0
        or scenario.get("protected_2026_outcomes_read") != 0
        or scenario.get("strategy_evidence_authority") is not False
    ):
        raise DynamicExitEodOptionReplayError("dynamic paired scenario authority changed")

    slip = Decimal(option_slippage_per_share)
    fee_in = Decimal(option_entry_fee_per_contract)
    fee_out = Decimal(option_exit_fee_per_contract)
    if min(slip, fee_in, fee_out) < 0:
        raise DynamicExitEodOptionReplayError("negative modeled option cost")

    rows: list[dict[str, Any]] = []
    for case in scenario["cases"]:
        if (
            case.get("strategy_aligned_status")
            != "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
        ):
            continue
        call = case.get("call")
        mark = case.get("strategy_exit_option_mark")
        assignment = case.get("dynamic_assignment")
        if (
            not isinstance(call, dict)
            or not isinstance(call.get("entry"), dict)
            or not isinstance(mark, dict)
            or not isinstance(assignment, dict)
            or assignment.get("action_id") == ABSTAIN_ACTION_ID
        ):
            raise DynamicExitEodOptionReplayError(
                "source-ready dynamic pair lost entry/exit/assignment"
            )
        ask = Decimal(str(call["entry"]["ask_per_share"]))
        bid = Decimal(str(mark["bid_per_share"]))
        debit = (ask + slip) * Decimal(100) + fee_in
        credit = max(Decimal("0"), bid - slip) * Decimal(100) - fee_out
        pnl = credit - debit
        net_return = pnl / debit
        rows.append({
            "case_id": case["case_id"],
            "year": case["year"],
            "ticker": case["ticker"],
            "action_id": assignment["action_id"],
            "stop_fraction": assignment["stop_fraction"],
            "target_fraction": assignment["target_fraction"],
            "entry_session_et": call["entry"]["session_et"],
            "exit_session_et": mark["session_et"],
            "entry_ask_per_share": str(ask),
            "exit_bid_per_share": str(bid),
            "modeled_round_trip_fees_per_contract": str(fee_in + fee_out),
            "modeled_net_pnl_per_contract": str(pnl.quantize(Decimal("0.01"))),
            "modeled_net_return_on_premium": str(
                net_return.quantize(Decimal("0.00000001"))
            ),
        })

    def summary(items: list[dict[str, Any]]) -> dict[str, Any]:
        values = [
            float(Decimal(item["modeled_net_return_on_premium"]))
            for item in items
        ]
        pnls = [
            float(Decimal(item["modeled_net_pnl_per_contract"]))
            for item in items
        ]
        return {
            "pairs": len(items),
            "mean_net_return_on_premium": (
                None if not values else statistics.fmean(values)
            ),
            "median_net_return_on_premium": (
                None if not values else statistics.median(values)
            ),
            "probability_positive": (
                None
                if not values
                else sum(value > 0.0 for value in values) / len(values)
            ),
            "mean_net_pnl_per_contract": (
                None if not pnls else statistics.fmean(pnls)
            ),
            "median_net_pnl_per_contract": (
                None if not pnls else statistics.median(pnls)
            ),
        }

    by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_year: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_action[row["action_id"]].append(row)
        by_year[row["year"]].append(row)

    result = {
        "contract": DIAGNOSTIC_CONTRACT,
        "status": (
            "DYNAMIC_EXIT_V1_PAIRED_EOD_OBSERVATION_DIAGNOSTIC_"
            "NOT_CAUSAL_PORTFOLIO"
        ),
        "scenario_fingerprint": scenario["scenario_fingerprint"],
        "conditioning_on_future_exit_source": True,
        "causal_portfolio_result": False,
        "pair_selection_rule": (
            "DYNAMIC_ACTION_SELECTED_POINT_IN_TIME_AND_EXACT_ENTRY_EXIT_EOD_"
            "OBSERVATIONS_BOTH_AVAILABLE"
        ),
        "overall": summary(rows),
        "by_action": {
            key: summary(items) for key, items in sorted(by_action.items())
        },
        "by_year": {
            key: summary(items) for key, items in sorted(by_year.items())
        },
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "rows": rows,
    }
    result["diagnostic_fingerprint"] = _fingerprint(result)
    return result




def persist_dynamic_assignments(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(value, "assignment_fingerprint")
    path = settings.resolved_path(
        f"{ASSIGNMENT_REL}_{value['assignment_fingerprint'][:16]}.json"
    )
    return _persist(path, value, "BOUNDED_DYNAMIC_EXIT_ASSIGNMENTS")


def persist_dynamic_scenario(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(value, "scenario_fingerprint")
    path = settings.resolved_path(
        f"{SCENARIO_REL}_{value['scenario_fingerprint'][:16]}.json"
    )
    return _persist(path, value, "DYNAMIC_EXIT_EOD_OPTION_SCENARIO")


def persist_dynamic_replay(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(value, "replay_fingerprint")
    path = settings.resolved_path(
        f"{REPLAY_REL}_{value['replay_fingerprint'][:16]}.json"
    )
    return _persist(path, value, "DYNAMIC_EXIT_EOD_OPTION_REPLAY")


def persist_paired_diagnostics(
    settings: AtlasSettings,
    value: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(value, "diagnostic_fingerprint")
    path = settings.resolved_path(
        f"{DIAGNOSTIC_REL}_{value['diagnostic_fingerprint'][:16]}.json"
    )
    return _persist(path, value, "DYNAMIC_EXIT_EOD_OPTION_PAIRED_DIAGNOSTICS")


def _persist(
    path: Path,
    value: dict[str, Any],
    label: str,
) -> tuple[Path, str]:
    import json

    raw = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise DynamicExitEodOptionReplayError(f"existing {label} path invalid")
        if path.read_text(encoding="utf-8") != raw:
            raise DynamicExitEodOptionReplayError(f"immutable {label} differs")
        return path, "REUSED_IMMUTABLE_" + label
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(raw)
        handle.flush()
    return path, "WRITTEN_IMMUTABLE_" + label
