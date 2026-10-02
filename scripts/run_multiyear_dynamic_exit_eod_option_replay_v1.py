from __future__ import annotations

"""Run bounded Dynamic Exit V1 historical EOD CALL diagnostics."""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    load_daily_exit_cases,
)
from packages.backtesting.recurrent_successor_dynamic_exit_v1_contract import (
    ABSTAIN_ACTION_ID,
    DYNAMIC_EXIT_ACTIONS,
    RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
    dynamic_exit_action_id,
)
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import PLAN_REL
from packages.data.multiyear_observed_option_quote_timeline_v1 import (
    local_verified_quote_body_reader,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    OUTPUT_REL as HANDOFF_REL,
    _check_signature,
)
from packages.simulation.multiyear_dynamic_exit_eod_option_replay_v1 import (
    REPLAY_CONTRACT,
    SCENARIO_CONTRACT,
    build_bounded_dynamic_exit_assignments,
    build_paired_observation_diagnostics,
    combine_dynamic_action_scenarios,
    persist_dynamic_assignments,
    persist_dynamic_replay,
    persist_dynamic_scenario,
    persist_paired_diagnostics,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    StrategyExitPolicy,
    build_strategy_aligned_eod_option_scenario,
    replay_strategy_aligned_eod_call_account,
)


class DynamicExitOptionRunnerError(ValueError):
    pass


def _artifact(settings, stem: str, fingerprint: str) -> tuple[Path, dict]:
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise DynamicExitOptionRunnerError("artifact fingerprint invalid")
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise DynamicExitOptionRunnerError(f"required artifact unavailable: {path}")
    return path, _read_object(path)


def _safe_last_2025_signal_session() -> date:
    sessions = get_market_calendar().sessions_in_range(
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
    if len(sessions) < 6:
        raise DynamicExitOptionRunnerError("2025 exchange calendar incomplete")
    return sessions[-6]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run bounded Dynamic Exit V1 CALL diagnostics through the safe 2025 "
            "boundary using exact stock-exit-session option EOD observations."
        )
    )
    parser.add_argument(
        "--base-scenario",
        type=Path,
        required=True,
        help="Exact immutable historical EOD option scenario artifact.",
    )
    parser.add_argument("--initial-cash", default="100000.00")
    parser.add_argument("--allocation-fraction", default="0.10")
    parser.add_argument("--max-open-positions", type=int, default=10)
    parser.add_argument("--max-positions-per-family", type=int, default=3)
    parser.add_argument("--option-slippage-per-share", default="0.00")
    parser.add_argument("--option-entry-fee-per-contract", default="0.65")
    parser.add_argument("--option-exit-fee-per-contract", default="0.65")
    parser.add_argument("--duckdb-threads", type=int, default=4)
    args = parser.parse_args(argv)

    print("ATLAS MULTIYEAR DYNAMIC EXIT V1 EOD OPTION REPLAY", flush=True)
    print(
        "  ZERO provider GETs. CALL only. Dynamic action uses strictly prior "
        "completed folds; current-fold outcomes cannot choose current actions.",
        flush=True,
    )
    print(
        "  Two outputs: strict causal account + all-source-ready paired EOD "
        "trade diagnostic (paired diagnostic is NOT a causal portfolio).",
        flush=True,
    )

    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")

        base_path = (
            args.base_scenario
            if args.base_scenario.is_absolute()
            else settings.resolved_path(args.base_scenario)
        )
        if base_path.is_symlink() or not base_path.is_file():
            raise DynamicExitOptionRunnerError("base option scenario unavailable")
        base = _read_object(base_path)
        _check_signature(base, "scenario_fingerprint")
        if (
            base.get("contract") != BASE_SCENARIO_CONTRACT
            or base.get("provider_requests") != 0
            or base.get("protected_2026_outcomes_read") != 0
        ):
            raise DynamicExitOptionRunnerError("base option scenario authority changed")

        handoff_path, handoff = _artifact(
            settings,
            HANDOFF_REL,
            base["handoff_fingerprint"],
        )
        _check_signature(handoff, "handoff_fingerprint")
        plan_path, plan = _artifact(
            settings,
            PLAN_REL,
            base["quote_plan_fingerprint"],
        )
        _check_signature(plan, "plan_fingerprint")

        safe_end = _safe_last_2025_signal_session()
        print(f"  base_scenario={base_path}", flush=True)
        print(f"  handoff={handoff_path}", flush=True)
        print(f"  quote_plan={plan_path}", flush=True)
        print(
            "  dynamic training scope: 2018-01-01 -> "
            f"{safe_end.isoformat()} (no 2026 outcomes)",
            flush=True,
        )
        print(
            "  option target scope: 2021-01-01 -> "
            f"{safe_end.isoformat()}",
            flush=True,
        )
        print(
            "  dynamic selector contract fingerprint: "
            + RECURRENT_SUCCESSOR_DYNAMIC_EXIT_V1_CONTRACT_FINGERPRINT,
            flush=True,
        )

        all_daily_cases, source = load_daily_exit_cases(
            ROOT,
            start_session=date(2018, 1, 1),
            end_session=safe_end,
            duckdb_threads=args.duckdb_threads,
        )
        print(
            "  bounded_dynamic_source_cases="
            f"{len(all_daily_cases)} usable; "
            f"eligible_daily_long={source['eligible_daily_long_cases']} "
            f"insufficient_prior_path="
            f"{source['insufficient_prior_path_evidence_cases']}",
            flush=True,
        )

        assignments = build_bounded_dynamic_exit_assignments(
            all_daily_cases,
            target_start=date(2021, 1, 1),
            safe_end=safe_end,
        )
        assignment_path, assignment_action = persist_dynamic_assignments(
            settings, assignments
        )
        print(
            f"  assignments={assignment_action} / {assignment_path}",
            flush=True,
        )
        print(
            "  "
            f"target_assignment_cases={assignments['target_assignment_cases']} "
            f"selected={assignments['selected_cases']} "
            f"abstained={assignments['abstained_cases']} "
            f"selection_rate={assignments['selection_rate']:.2%}",
            flush=True,
        )
        print(
            f"  selected_action_counts={assignments['selected_action_counts']}",
            flush=True,
        )
        print(
            f"  abstain_reasons={assignments['abstain_reasons']}",
            flush=True,
        )

        base_case_ids = {case["case_id"] for case in base["cases"]}
        target_daily_cases = tuple(
            case
            for case in all_daily_cases
            if case.opportunity.opportunity_id in base_case_ids
            and date(2021, 1, 1)
                <= case.opportunity.signal_session
                <= safe_end
        )
        if len({case.opportunity.opportunity_id for case in target_daily_cases}) != len(
            target_daily_cases
        ):
            raise DynamicExitOptionRunnerError(
                "target daily case identities are not unique"
            )

        selected_actions = set(assignments["selected_action_counts"])
        action_lookup = {
            dynamic_exit_action_id(stop, target): (float(stop), float(target))
            for stop, target in DYNAMIC_EXIT_ACTIONS
        }
        if not selected_actions.issubset(action_lookup):
            raise DynamicExitOptionRunnerError("bounded selector chose unknown action")

        reader = local_verified_quote_body_reader(settings, plan)
        decoded_cache: dict[str, list[dict]] = {}
        decoded_sha_cache: dict[str, str] = {}
        action_scenarios: dict[str, dict] = {}

        for index, action_id in enumerate(sorted(selected_actions), start=1):
            stop, target = action_lookup[action_id]
            print(
                f"  action_source_map {index}/{len(selected_actions)} "
                f"{action_id}: stop={stop:.0%} target={target:.0%}",
                flush=True,
            )
            action_scenarios[action_id] = build_strategy_aligned_eod_option_scenario(
                base,
                plan,
                handoff,
                target_daily_cases,
                policy=StrategyExitPolicy(stop, target),
                safe_last_signal_session=safe_end,
                read_verified_body=reader,
                decoded_cache=decoded_cache,
                decoded_sha_cache=decoded_sha_cache,
            )
            print(
                "    "
                f"source_ready="
                f"{action_scenarios[action_id]['source_ready_strategy_aligned_round_trips']} "
                f"exact_exit_gap="
                f"{action_scenarios[action_id]['entry_ready_but_exact_strategy_exit_source_gap']} "
                f"entry_after_stock_exit="
                f"{action_scenarios[action_id]['stock_exit_not_after_option_eod_entry']}",
                flush=True,
            )

        dynamic_scenario = combine_dynamic_action_scenarios(
            base,
            assignments,
            action_scenarios,
            safe_last_signal_session=safe_end,
        )
        scenario_path, scenario_action = persist_dynamic_scenario(
            settings, dynamic_scenario
        )
        print(
            f"  dynamic_scenario={scenario_action} / {scenario_path}",
            flush=True,
        )
        print(
            "  "
            f"dynamic_selected={dynamic_scenario['dynamic_selected_cases']} "
            f"dynamic_abstained={dynamic_scenario['dynamic_abstained_cases']} "
            f"source_ready="
            f"{dynamic_scenario['source_ready_strategy_aligned_round_trips']} "
            f"exact_exit_source_gap="
            f"{dynamic_scenario['entry_ready_but_exact_strategy_exit_source_gap']} "
            f"stock_exit_not_after_option_eod_entry="
            f"{dynamic_scenario['stock_exit_not_after_option_eod_entry']}",
            flush=True,
        )
        print(
            f"  dynamic_selected_action_counts="
            f"{dynamic_scenario['dynamic_selected_action_counts']}",
            flush=True,
        )
        for year, values in dynamic_scenario["by_year"].items():
            print(f"  dynamic_scenario_year={year} {values}", flush=True)

        diagnostics = build_paired_observation_diagnostics(
            dynamic_scenario,
            option_slippage_per_share=args.option_slippage_per_share,
            option_entry_fee_per_contract=args.option_entry_fee_per_contract,
            option_exit_fee_per_contract=args.option_exit_fee_per_contract,
        )
        diagnostic_path, diagnostic_action = persist_paired_diagnostics(
            settings, diagnostics
        )
        print(
            f"  paired_diagnostics={diagnostic_action} / {diagnostic_path}",
            flush=True,
        )
        overall = diagnostics["overall"]
        print(
            "  paired_source_ready "
            f"pairs={overall['pairs']} "
            f"mean_return_on_premium={overall['mean_net_return_on_premium']} "
            f"median_return_on_premium={overall['median_net_return_on_premium']} "
            f"probability_positive={overall['probability_positive']} "
            f"mean_pnl_per_contract={overall['mean_net_pnl_per_contract']} "
            f"median_pnl_per_contract={overall['median_net_pnl_per_contract']}",
            flush=True,
        )
        for action_id, values in diagnostics["by_action"].items():
            print(f"  paired_action={action_id} {values}", flush=True)
        for year, values in diagnostics["by_year"].items():
            print(f"  paired_year={year} {values}", flush=True)

        account_policy = ReplayPolicy(
            initial_cash=args.initial_cash,
            fraction_of_available_cash=args.allocation_fraction,
            max_open_positions=args.max_open_positions,
            option_slippage_per_share=args.option_slippage_per_share,
            option_entry_fee_per_contract=args.option_entry_fee_per_contract,
            option_exit_fee_per_contract=args.option_exit_fee_per_contract,
        )
        replay = replay_strategy_aligned_eod_call_account(
            dynamic_scenario,
            policy=account_policy,
            max_positions_per_family=args.max_positions_per_family,
            one_active_position_per_ticker=True,
            expected_scenario_contract=SCENARIO_CONTRACT,
            replay_contract=REPLAY_CONTRACT,
        )
        replay_path, replay_action = persist_dynamic_replay(settings, replay)
        print(
            f"  strict_account_replay={replay_action} / {replay_path}",
            flush=True,
        )
        print(
            "  strict_account "
            f"source_ready={replay['source_ready_strategy_aligned_round_trips']} "
            f"admitted={replay['admitted_positions']} "
            f"completed={replay['completed_round_trips']} "
            f"open_end={replay['end_open_positions']} "
            f"peak_open={replay['peak_open_positions']} "
            f"ending_cash={replay['ending_cash']} "
            f"ending_equity={replay['ending_equity']} "
            f"modeled_realized_pnl={replay['modeled_realized_pnl']} "
            f"fully_closed_return={replay['modeled_total_return_if_fully_closed']}",
            flush=True,
        )
        print(f"  strict_account_rejections={replay['rejections']}", flush=True)
        for year, values in replay["by_year"].items():
            print(f"  strict_account_year={year} {values}", flush=True)

        print(
            "  COMPLETE provider_requests=0 protected_2026_outcomes_read=0 "
            "historical_fills_verified=0 historical_account_pnl_authority=False "
            "strategy_evidence_authority=False",
            flush=True,
        )
        print(
            "  NOTE paired-source-ready diagnostics condition on exact future exit "
            "observation availability and are NOT a causal portfolio result.",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"DYNAMIC EXIT EOD OPTION REPLAY STOPPED: "
            f"{type(exc).__name__}: {exc}",
            flush=True,
        )
        print(
            "  No provider fallback or automatic paid request is authorized.",
            flush=True,
        )
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
