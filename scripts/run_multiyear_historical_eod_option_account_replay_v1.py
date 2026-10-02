from __future__ import annotations

"""Build and run the first receipt-bound modeled historical EOD option replay."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import PLAN_REL
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    OUTPUT_REL as EOD_PROBE_REL,
    local_verified_quote_body_reader,
)
from packages.data.multiyear_marketdata_eod_standard_contract_admission_v1 import (
    CONTRACT as ADMISSION_CONTRACT,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    NATIVE_FP,
    NATIVE_REL,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    OUTPUT_REL as HANDOFF_REL,
    _check_signature,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    build_historical_eod_option_scenario,
    persist_historical_eod_option_account_replay,
    persist_historical_eod_option_scenario,
    replay_historical_eod_option_account,
)
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy


class HistoricalEodReplayRunnerError(ValueError):
    pass


def _artifact(settings, stem: str, fingerprint: str) -> tuple[Path, dict]:
    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
        raise HistoricalEodReplayRunnerError("artifact fingerprint invalid")
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise HistoricalEodReplayRunnerError(
            f"required artifact is unavailable: {path}"
        )
    return path, _read_object(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Build the receipt-bound historical EOD option scenario and replay "
            "CALL primary plus PUT counterfactual account modes"
        )
    )
    parser.add_argument(
        "--admission",
        type=Path,
        required=True,
        help=(
            "Exact multiyear_marketdata_eod_standard_contract_admission_v1 "
            "artifact"
        ),
    )
    parser.add_argument("--initial-cash", default="100000.00")
    parser.add_argument("--allocation-fraction", default="0.10")
    parser.add_argument("--max-open-positions", type=int, default=5)
    parser.add_argument("--option-slippage-per-share", default="0.00")
    parser.add_argument("--option-entry-fee-per-contract", default="0.65")
    parser.add_argument("--option-exit-fee-per-contract", default="0.65")
    args = parser.parse_args(argv)

    print("ATLAS MULTIYEAR HISTORICAL EOD OPTION ACCOUNT REPLAY V1", flush=True)
    print(
        "  MODELED historical EOD scenario; ZERO provider GETs; "
        "no verified fill/P&L authority.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")

        admission_path = (
            args.admission
            if args.admission.is_absolute()
            else settings.resolved_path(args.admission)
        )
        if admission_path.is_symlink() or not admission_path.is_file():
            raise HistoricalEodReplayRunnerError(
                "admission audit artifact unavailable"
            )
        admission = _read_object(admission_path)
        _check_signature(admission, "audit_fingerprint")
        if admission.get("contract") != ADMISSION_CONTRACT:
            raise HistoricalEodReplayRunnerError("admission audit contract changed")

        probe_path, probe = _artifact(
            settings,
            EOD_PROBE_REL,
            admission["eod_probe_fingerprint"],
        )
        _check_signature(probe, "probe_fingerprint")
        handoff_path, handoff = _artifact(
            settings,
            HANDOFF_REL,
            admission["handoff_fingerprint"],
        )
        _check_signature(handoff, "handoff_fingerprint")
        plan_path, plan = _artifact(
            settings,
            PLAN_REL,
            handoff["quote_plan_fingerprint"],
        )
        _check_signature(plan, "plan_fingerprint")

        native_path = settings.resolved_path(NATIVE_REL)
        if native_path.is_symlink() or not native_path.is_file():
            raise HistoricalEodReplayRunnerError("accepted native source unavailable")
        native = _read_object(native_path)
        _check_signature(native, "source_fingerprint")
        if native.get("source_fingerprint") != NATIVE_FP:
            raise HistoricalEodReplayRunnerError("accepted native source changed")

        print(f"  admission={admission_path}", flush=True)
        print(f"  probe={probe_path}", flush=True)
        print(f"  handoff={handoff_path}", flush=True)
        print(f"  quote_plan={plan_path}", flush=True)
        print(f"  native_source={native_path}", flush=True)

        scenario = build_historical_eod_option_scenario(
            native,
            plan,
            handoff,
            probe,
            admission,
            read_verified_body=local_verified_quote_body_reader(
                settings, plan
            ),
        )
        scenario_path, scenario_action = persist_historical_eod_option_scenario(
            settings, scenario
        )
        print(
            f"  scenario={scenario_action} / {scenario_path}",
            flush=True,
        )
        print(
            "  "
            f"causal_entry_ready_rights={scenario['causal_entry_ready_rights']} "
            f"resolved_exit_rights={scenario['entry_ready_resolved_exit_rights']} "
            f"unresolved_exit_rights="
            f"{scenario['entry_ready_unresolved_exit_rights']} "
            f"unique_histories_decoded="
            f"{scenario['unique_physical_quote_histories_decoded']}",
            flush=True,
        )
        for year, values in scenario["by_year"].items():
            print(f"  scenario_year={year} {values}", flush=True)

        policy = ReplayPolicy(
            initial_cash=args.initial_cash,
            fraction_of_available_cash=args.allocation_fraction,
            max_open_positions=args.max_open_positions,
            option_slippage_per_share=args.option_slippage_per_share,
            option_entry_fee_per_contract=args.option_entry_fee_per_contract,
            option_exit_fee_per_contract=args.option_exit_fee_per_contract,
        )

        reports = {}
        for mode in ("CALL", "PUT"):
            report = replay_historical_eod_option_account(
                scenario, mode=mode, policy=policy
            )
            replay_path, replay_action = (
                persist_historical_eod_option_account_replay(
                    settings, report
                )
            )
            reports[mode] = report
            print(
                f"  {mode.lower()}_replay={replay_action} / {replay_path}",
                flush=True,
            )
            print(
                "  "
                f"mode={mode} "
                f"source_entry_ready={report['causal_entry_source_rights']} "
                f"admitted={report['admitted_positions']} "
                f"completed={report['completed_round_trips']} "
                f"open_end={report['end_open_positions']} "
                f"peak_open={report['peak_open_positions']} "
                f"ending_cash={report['ending_cash']} "
                f"ending_equity={report['ending_equity']} "
                f"modeled_realized_pnl={report['modeled_realized_pnl']} "
                f"fully_closed_return="
                f"{report['modeled_total_return_on_initial_cash_if_fully_closed']}",
                flush=True,
            )
            for year, values in report["by_year"].items():
                print(f"  {mode}_year={year} {values}", flush=True)

        print(
            "  COMPLETE provider_requests=0 protected_2026_outcomes_read=0 "
            "historical_fills_verified=0 historical_account_pnl_authority=False "
            "strategy_evidence_authority=False",
            flush=True,
        )
        print(
            "  CALL is the direction-aligned primary replay for the accepted daily-LONG "
            "cohort; PUT is counterfactual diagnostic only.",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"HISTORICAL EOD OPTION REPLAY STOPPED: "
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
