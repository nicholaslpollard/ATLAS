from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate8 import Phase25Gate8DevelopmentAttribution, Phase25Gate8Error
from packages.backtesting.phase25_gate8_validation import (
    Phase25Gate8IndependentValidationError,
    Phase25Gate8IndependentValidator,
)
from packages.backtesting.phase25_gate9 import Phase25Gate9Error, Phase25Gate9Robustness
from packages.backtesting.phase25_gate9_validation import (
    Phase25Gate9IndependentValidationError,
    Phase25Gate9IndependentValidator,
)
from packages.backtesting.phase25_gate10 import Phase25Gate10Error, Phase25Gate10ProtectedConfirmation
from packages.backtesting.phase25_gate10_validation import (
    Phase25Gate10IndependentValidationError,
    Phase25Gate10IndependentValidator,
)
from packages.backtesting.phase25_gate11 import Phase25Gate11Closeout, Phase25Gate11Error
from packages.backtesting.phase25_gate11_validation import (
    Phase25Gate11IndependentValidationError,
    Phase25Gate11IndependentValidator,
)
from packages.backtesting.phase25_gate8_policy import (
    phase25_gate8_policy_fingerprint,
    phase25_gate9_policy_fingerprint,
    phase25_gate10_policy_fingerprint,
    phase25_gate11_policy_fingerprint,
)
from packages.core.settings import load_settings


def _mean10(item: dict[str, object], key: str) -> object:
    summary = dict(item[key])
    return dict(dict(summary["aggregate_by_cost_bps"])["10"]).get("mean_return")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run all remaining Phase25 route-fidelity evidence gates in one provider-free/local cumulative pass. "
            "Gates8-9 are development-only; Gate10 reads protected evidence only for frozen Gate9 finalists; "
            "Gate11 performs diagnostic closeout and never changes Phase11 support."
        )
    )
    parser.add_argument("--through", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    print("ATLAS Phase 25 — Cumulative Remaining Evidence Gates 8–11")
    print(f"Through session: {args.through}")
    print(f"Gate8 policy: {phase25_gate8_policy_fingerprint()}")
    print(f"Gate9 policy: {phase25_gate9_policy_fingerprint()}")
    print(f"Gate10 policy: {phase25_gate10_policy_fingerprint()}")
    print(f"Gate11 policy: {phase25_gate11_policy_fingerprint()}")
    print("Provider/broker/order/PAPER/LIVE/support writes: NONE")
    print("Interactive confirmation: NOT REQUIRED")

    settings = load_settings()
    try:
        print("\n[Gate8] Development-only incumbent attribution")
        gate8 = Phase25Gate8DevelopmentAttribution(settings).run(through_date=args.through)
        gate8v = Phase25Gate8IndependentValidator(settings).run(through_date=args.through)
        print(f"Route rows matched to accepted research source: {gate8['research_source_matched_route_rows']} / {gate8['route_eligible_rows']}")
        print(f"Research-source route coverage: {float(gate8['research_source_route_coverage_fraction']):.4%}")
        print(f"Development rule-fired signal rows: {gate8['development_rule_fired_signal_rows']}")
        print(f"Candidates with >=1 rule fire: {gate8['development_candidates_with_any_rule_fire']}")
        for item_raw in gate8["strategy_results"]:
            item = dict(item_raw)
            print(
                f"  {item['strategy_id']}: broad10={_mean10(item, 'broad_comparator')} "
                f"production10={_mean10(item, 'production_path')} delta={item['primary_10bps_mean_delta']}"
            )
        print(f"Gate8 independent validation: {gate8v['pass']}")

        print("\n[Gate9] Preregistered robustness + internal validation")
        gate9 = Phase25Gate9Robustness(settings).run(through_date=args.through)
        gate9v = Phase25Gate9IndependentValidator(settings).run(through_date=args.through)
        print(f"Selected after development + global Holm: {gate9['selected_strategy_ids']}")
        print(f"Finalists after internal validation: {gate9['finalist_strategy_ids']}")
        for item_raw in gate9["selection_results"]:
            item = dict(item_raw)
            failed = [name for name, passed in dict(item['checks']).items() if not passed]
            print(
                f"  {item['strategy_id']}: basic={item['basic_pass']} "
                f"holm={dict(item['multiplicity']).get('rejected_null', False)} "
                f"selected={item['selection_pass']} failed={failed}"
            )
        print(f"Gate9 independent validation: {gate9v['pass']}")

        print("\n[Gate10] Frozen-finalist protected confirmation")
        gate10 = Phase25Gate10ProtectedConfirmation(settings).run(through_date=args.through)
        gate10v = Phase25Gate10IndependentValidator(settings).run(through_date=args.through)
        print(f"Disposition: {gate10['disposition']}")
        print(f"Protected evidence reads: {gate10['protected_evidence_reads']}")
        print(f"Confirmed strategies: {gate10['confirmed_strategy_ids']}")
        for item_raw in gate10.get("protected_results", []):
            item = dict(item_raw)
            failed = [name for name, passed in dict(item['checks']).items() if not passed]
            print(f"  {item['strategy_id']}: confirmed={item['confirmed']} failed={failed}")
        print(f"Gate10 independent validation: {gate10v['pass']}")

        print("\n[Gate11] Cumulative diagnostic closeout")
        gate11 = Phase25Gate11Closeout(settings).run(through_date=args.through)
        gate11v = Phase25Gate11IndependentValidator(settings).run(through_date=args.through)
        print(f"Verdict: {gate11['verdict']}")
        print(f"Next boundary: {gate11['next_boundary']}")
        print(f"Failure counts: {gate11['failure_counts']}")
        print(f"Phase11 support map unchanged: {gate11['phase11_support_map_unchanged']}")
        print(f"Gate11 independent validation: {gate11v['pass']}")
    except (
        Phase25Gate8Error,
        Phase25Gate8IndependentValidationError,
        Phase25Gate9Error,
        Phase25Gate9IndependentValidationError,
        Phase25Gate10Error,
        Phase25Gate10IndependentValidationError,
        Phase25Gate11Error,
        Phase25Gate11IndependentValidationError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        print("\nCumulative status: BLOCKED")
        print(f"Reason: {exc}")
        print("Do not delete evidence or rerun provider acquisition. Reconcile this local evidence boundary first.")
        return 2

    print("\nCumulative status: COMPLETE")
    print(f"Gate8 report: {gate8['report_path']}")
    print(f"Gate9 report: {gate9['report_path']}")
    print(f"Gate10 report: {gate10['report_path']}")
    print(f"Gate11 report: {gate11['report_path']}")
    print("Provider reads/writes performed by Gates8–11: 0 / 0")
    print("Broker/order/PAPER/LIVE writes: 0 / 0 / 0 / 0")
    print("Phase11 support writes: 0")
    print("Pass: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
