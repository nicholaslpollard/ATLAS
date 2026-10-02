from __future__ import annotations

"""Run frozen stock-exit-session-aligned historical EOD CALL replays."""

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.backtesting.recurrent_successor_daily_exit_confirmation_contract import (
    CANDIDATE_EXIT_POLICIES,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    load_daily_exit_cases,
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
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    StrategyExitPolicy,
    build_strategy_aligned_eod_option_scenario,
    persist_strategy_aligned_replay,
    persist_strategy_aligned_scenario,
    replay_strategy_aligned_eod_call_account,
)


class StrategyAlignedRunnerError(ValueError):
    pass


def _artifact(settings, stem: str, fingerprint: str) -> tuple[Path, dict]:
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise StrategyAlignedRunnerError("artifact fingerprint invalid")
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise StrategyAlignedRunnerError(f"required artifact unavailable: {path}")
    return path, _read_object(path)


def _safe_last_2025_signal_session() -> date:
    sessions = get_market_calendar().sessions_in_range(
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
    if len(sessions) < 6:
        raise StrategyAlignedRunnerError("2025 exchange calendar is incomplete")
    # A daily strategy signal needs five subsequent trading sessions. The sixth
    # session from the end is therefore the last signal whose entire five-session
    # path stays inside 2025.
    return sessions[-6]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run modeled CALL replays whose option exit attempt occurs at EOD on "
            "the frozen stock STOP/TARGET/TIME exit session."
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

    print("ATLAS MULTIYEAR STRATEGY-ALIGNED EOD OPTION REPLAY V1", flush=True)
    print(
        "  ZERO provider GETs. CALL only. Option exit = EOD bid on frozen stock "
        "strategy exit SESSION, not intraday stop/target touch time.",
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
            raise StrategyAlignedRunnerError("base scenario artifact unavailable")
        base = _read_object(base_path)
        _check_signature(base, "scenario_fingerprint")
        if base.get("contract") != BASE_SCENARIO_CONTRACT:
            raise StrategyAlignedRunnerError("base scenario contract changed")

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
            "  stock strategy source scope: 2021-01-01 -> "
            f"{safe_end.isoformat()} (last five-session path wholly inside 2025)",
            flush=True,
        )

        daily_cases, daily_source = load_daily_exit_cases(
            ROOT,
            start_session=date(2021, 1, 1),
            end_session=safe_end,
            duckdb_threads=args.duckdb_threads,
        )
        print(
            "  stock_exit_cases="
            f"{len(daily_cases)} sufficient-prior-path cases; "
            f"eligible_daily_long={daily_source['eligible_daily_long_cases']} "
            f"insufficient_prior_path="
            f"{daily_source['insufficient_prior_path_evidence_cases']}",
            flush=True,
        )

        replay_policy = ReplayPolicy(
            initial_cash=args.initial_cash,
            fraction_of_available_cash=args.allocation_fraction,
            max_open_positions=args.max_open_positions,
            option_slippage_per_share=args.option_slippage_per_share,
            option_entry_fee_per_contract=args.option_entry_fee_per_contract,
            option_exit_fee_per_contract=args.option_exit_fee_per_contract,
        )
        reader = local_verified_quote_body_reader(settings, plan)

        for stop, target in CANDIDATE_EXIT_POLICIES:
            policy = StrategyExitPolicy(
                stop_fraction=float(stop),
                target_fraction=float(target),
            )
            print(
                f"\n  STRATEGY POLICY {policy.policy_id}: building exact-session source map...",
                flush=True,
            )
            scenario = build_strategy_aligned_eod_option_scenario(
                base,
                plan,
                handoff,
                daily_cases,
                policy=policy,
                safe_last_signal_session=safe_end,
                read_verified_body=reader,
            )
            scenario_path, scenario_action = persist_strategy_aligned_scenario(
                settings, scenario
            )
            print(
                f"  scenario={scenario_action} / {scenario_path}",
                flush=True,
            )
            print(
                "  "
                f"usable_stock_exit_policy_cases="
                f"{scenario['usable_stock_exit_policy_cases']} "
                f"source_ready_strategy_aligned_round_trips="
                f"{scenario['source_ready_strategy_aligned_round_trips']} "
                f"entry_ready_exact_exit_source_gap="
                f"{scenario['entry_ready_but_exact_strategy_exit_source_gap']} "
                f"stock_exit_not_after_option_eod_entry="
                f"{scenario['stock_exit_not_after_option_eod_entry']} "
                f"protected_2026_stock_horizon_withheld="
                f"{scenario['protected_2026_stock_horizon_withheld']}",
                flush=True,
            )
            for year, values in scenario["by_year"].items():
                print(f"  {policy.policy_id}_scenario_year={year} {values}", flush=True)

            report = replay_strategy_aligned_eod_call_account(
                scenario,
                policy=replay_policy,
                max_positions_per_family=args.max_positions_per_family,
                one_active_position_per_ticker=True,
            )
            replay_path, replay_action = persist_strategy_aligned_replay(
                settings, report
            )
            print(
                f"  replay={replay_action} / {replay_path}",
                flush=True,
            )
            print(
                "  "
                f"policy={policy.policy_id} "
                f"source_ready={report['source_ready_strategy_aligned_round_trips']} "
                f"admitted={report['admitted_positions']} "
                f"completed={report['completed_round_trips']} "
                f"open_end={report['end_open_positions']} "
                f"peak_open={report['peak_open_positions']} "
                f"ending_cash={report['ending_cash']} "
                f"ending_equity={report['ending_equity']} "
                f"modeled_realized_pnl={report['modeled_realized_pnl']} "
                f"fully_closed_return="
                f"{report['modeled_total_return_if_fully_closed']}",
                flush=True,
            )
            print(
                f"  rejections={report['rejections']}",
                flush=True,
            )
            for year, values in report["by_year"].items():
                print(f"  {policy.policy_id}_account_year={year} {values}", flush=True)

        print(
            "\n  COMPLETE provider_requests=0 protected_2026_outcomes_read=0 "
            "historical_fills_verified=0 historical_account_pnl_authority=False "
            "strategy_evidence_authority=False",
            flush=True,
        )
        print(
            "  NOTE STOP/TARGET timing is session-level only: option exits use that "
            "session's EOD bid, not an intraday option quote.",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"STRATEGY-ALIGNED EOD OPTION REPLAY STOPPED: "
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
