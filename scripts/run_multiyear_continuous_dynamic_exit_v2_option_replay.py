from __future__ import annotations

"""Run Continuous Dynamic Exit V2 historical EOD CALL diagnostics."""

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
from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    REPLAY_CONTRACT,
    SCENARIO_CONTRACT,
    build_continuous_dynamic_exit_v2_scenario,
    build_continuous_paired_diagnostics,
    persist_diagnostics,
    persist_replay,
    persist_scenario,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    replay_strategy_aligned_eod_call_account,
)


class ContinuousDynamicExitV2RunnerError(ValueError):
    pass


def _artifact(settings, stem: str, fingerprint: str) -> tuple[Path, dict]:
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise ContinuousDynamicExitV2RunnerError("artifact fingerprint invalid")
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise ContinuousDynamicExitV2RunnerError(
            f"required artifact unavailable: {path}"
        )
    return path, _read_object(path)


def _safe_last_2025_signal_session() -> date:
    sessions = get_market_calendar().sessions_in_range(
        date(2025, 1, 1),
        date(2025, 12, 31),
    )
    if len(sessions) < 6:
        raise ContinuousDynamicExitV2RunnerError(
            "2025 exchange calendar incomplete"
        )
    return sessions[-6]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run Continuous Dynamic Exit V2 CALL diagnostics. Each trade receives "
            "case-specific stop/target levels derived from strictly-prior training "
            "MFE/MAE and return quartiles."
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

    print("ATLAS CONTINUOUS DYNAMIC EXIT V2 EOD OPTION REPLAY", flush=True)
    print(
        "  ZERO provider GETs. CALL only. Entry selection is reused; V2 parameterizes "
        "each eligible trade's stop/target from strictly-prior training distributions.",
        flush=True,
    )
    print(
        "  Formula: stop <- mean(mean_MAE, |negative P25 return|), "
        "target <- mean(mean_MFE, positive P75 return), clipped inside the "
        "researched 1-3% / 2-5% envelope with minimum target/stop=1.5x.",
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
            raise ContinuousDynamicExitV2RunnerError(
                "base option scenario unavailable"
            )
        base = _read_object(base_path)
        _check_signature(base, "scenario_fingerprint")
        if (
            base.get("contract") != BASE_SCENARIO_CONTRACT
            or base.get("provider_requests") != 0
            or base.get("protected_2026_outcomes_read") != 0
            or base.get("historical_account_pnl_authority") is not False
        ):
            raise ContinuousDynamicExitV2RunnerError(
                "base option scenario authority changed"
            )

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
            "  target scope: 2021-01-01 -> "
            f"{safe_end.isoformat()} (five-session horizon remains inside 2025)",
            flush=True,
        )

        daily_cases, source = load_daily_exit_cases(
            ROOT,
            start_session=date(2021, 1, 1),
            end_session=safe_end,
            duckdb_threads=args.duckdb_threads,
        )
        print(
            "  continuous_exit_source_cases="
            f"{len(daily_cases)} usable / "
            f"{source['eligible_daily_long_cases']} selected daily LONG; "
            f"{source['insufficient_prior_path_evidence_cases']} lack prior path support",
            flush=True,
        )

        scenario = build_continuous_dynamic_exit_v2_scenario(
            base,
            plan,
            handoff,
            daily_cases,
            safe_last_signal_session=safe_end,
            read_verified_body=local_verified_quote_body_reader(settings, plan),
        )
        scenario_path, scenario_action = persist_scenario(settings, scenario)
        print(
            f"  scenario={scenario_action} / {scenario_path}",
            flush=True,
        )
        print(
            "  "
            f"continuous_policy_cases={scenario['continuous_exit_policy_cases']} "
            f"source_ready={scenario['source_ready_strategy_aligned_round_trips']} "
            f"exact_exit_source_gap="
            f"{scenario['entry_ready_but_exact_strategy_exit_source_gap']} "
            f"stock_exit_not_after_option_eod_entry="
            f"{scenario['stock_exit_not_after_option_eod_entry']}",
            flush=True,
        )
        print(f"  stop_distribution={scenario['stop_distribution']}", flush=True)
        print(
            f"  target_distribution={scenario['target_distribution']}",
            flush=True,
        )
        for year, values in scenario["by_year"].items():
            print(f"  continuous_scenario_year={year} {values}", flush=True)

        diagnostics = build_continuous_paired_diagnostics(
            scenario,
            option_slippage_per_share=args.option_slippage_per_share,
            option_entry_fee_per_contract=args.option_entry_fee_per_contract,
            option_exit_fee_per_contract=args.option_exit_fee_per_contract,
        )
        diagnostic_path, diagnostic_action = persist_diagnostics(
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
            scenario,
            policy=account_policy,
            max_positions_per_family=args.max_positions_per_family,
            one_active_position_per_ticker=True,
            expected_scenario_contract=SCENARIO_CONTRACT,
            replay_contract=REPLAY_CONTRACT,
        )
        replay_path, replay_action = persist_replay(settings, replay)
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
        print(
            f"  strict_account_rejections={replay['rejections']}",
            flush=True,
        )
        for year, values in replay["by_year"].items():
            print(f"  strict_account_year={year} {values}", flush=True)

        print(
            "  COMPLETE provider_requests=0 protected_2026_outcomes_read=0 "
            "historical_fills_verified=0 historical_account_pnl_authority=False "
            "strategy_evidence_authority=False",
            flush=True,
        )
        print(
            "  NOTE paired-source-ready diagnostics condition on future exact-exit "
            "observation availability and are NOT a causal portfolio result.",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"CONTINUOUS DYNAMIC EXIT V2 OPTION REPLAY STOPPED: "
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
