from __future__ import annotations

import argparse
from datetime import date

from packages.ai.phase14_closeout import Phase14Closeout
from packages.core.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the complete ATLAS Phase 14 independent AI audit and alert-artifact closeout."
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=None,
        help="Optional accepted Phase 13 date (YYYY-MM-DD). Defaults to accepted Phase 13 closeout.",
    )
    args = parser.parse_args()
    settings = load_settings()

    print("ATLAS Phase 14 Independent AI Audit and Alerting Closeout")
    print(
        "  safety: accepted Phase 13 review-ready cases only; AI audit is non-authoritative; "
        "alerts are local artifacts only; no production ML/broker/order/position writes"
    )
    closeout = Phase14Closeout(settings).run(
        as_of_date=args.as_of,
        progress=lambda message: print(f"  {message}"),
    )
    if closeout.get("pass") is not True:
        raise SystemExit("  Phase 14 closeout: FAIL")

    print("  AI-audit disposition:")
    print(f"    as-of:                         {closeout['as_of_date']}")
    print(f"    Phase 13 case files:            {int(closeout['phase13_case_count']):,}")
    print(f"    Phase 13 review-ready cases:    {int(closeout['phase13_review_ready_count']):,}")
    print(f"    AI review records:              {int(closeout['ai_review_count']):,}")
    print(f"    alert artifacts:                {int(closeout['alert_artifact_count']):,}")
    print(f"    disposition counts:             {closeout['disposition_counts']}")
    print(f"    provider initialized:           {closeout['provider_initialized']}")
    print(f"    provider calls:                 {int(closeout['provider_calls']):,}")
    print(f"    external deliveries:            {int(closeout['external_deliveries']):,}")
    print(f"    zero-review no-op:               {closeout['zero_review_noop']}")

    print("  independent final checks:")
    for name, value in closeout["checks"].items():
        print(f"    {name}: {value}")

    disposition = closeout["final_disposition"]
    print("  final disposition:")
    print(f"    Phase 14 accepted:                       {disposition['phase14_accepted']}")
    print(
        "    AI disposition is a trade signal:       "
        f"{not disposition['ai_disposition_is_review_not_trade_signal']}"
    )
    print(
        "    deterministic Phase 13 case changed:    "
        f"{not disposition['deterministic_phase13_case_remains_immutable']}"
    )
    print(
        "    alert artifacts externally delivered:   "
        f"{not disposition['alert_records_are_artifacts_not_external_deliveries']}"
    )
    print(
        "    AI has broker/order authority:           "
        f"{not disposition['ai_has_no_broker_or_order_authority']}"
    )
    print(f"    next phase:                              {disposition['next_phase']}")
    print(f"  final acceptance report: {closeout['report_path']}")
    print("  Phase 14 Independent AI Audit and Alerting: PASS")
    print("  Phase 15 Broker Execution and Outcome Learning: NEXT")


if __name__ == "__main__":
    main()
