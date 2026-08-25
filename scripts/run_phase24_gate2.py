from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase24_gate1_policy import phase24_gate1_policy_fingerprint
from packages.backtesting.phase24_gate2 import Phase24Gate2Error, Phase24Gate2Research
from packages.backtesting.phase24_gate2_validation import (
    Phase24Gate2IndependentValidator,
    Phase24Gate2ValidationError,
)
from packages.core.settings import load_settings


def main() -> None:
    print("ATLAS Phase 24 Strategy Evidence Challenger — Gate 2")
    print(f"Locked Gate 1 policy: {phase24_gate1_policy_fingerprint()}")
    print("Scope: DEVELOPMENT SELECTION + INTERNAL VALIDATION ONLY")
    print("Protected evidence: DISABLED / UNREAD")
    print("Provider/broker/order/PAPER/LIVE authority: NONE")
    settings = load_settings()
    try:
        result = Phase24Gate2Research(settings).run(progress=lambda message: print(f"  {message}"))
        validation = Phase24Gate2IndependentValidator(settings).run()
    except (Phase24Gate2Error, Phase24Gate2ValidationError, ValueError) as exc:
        print("Gate 2 status: BLOCKED")
        print(f"Reason: {exc}")
        print("No protected/provider/broker/order retry or fallback is authorized.")
        raise SystemExit(2) from None

    print("Gate 2 status: COMPLETE")
    print(f"Selection report: {result['selection_report_path']}")
    print(f"Selection lock: {result['selection_lock_path']}")
    print(f"Internal validation: {result['internal_validation_report_path']}")
    print(f"Finalist lock: {result['finalist_lock_path']}")
    print(f"Independent validation: {validation['report_path']}")
    print(f"Preregistered challengers: {result['challenger_count']}")
    print(f"Selection basic-pass variants: {result['selection_basic_pass_count']}")
    print(f"Selection multiplicity-pass variants: {result['selection_multiplicity_pass_count']}")
    print(f"Frozen family/direction selections: {result['selected_count']}")
    print(f"Fresh finalists after internal validation: {result['fresh_finalist_count']}")
    print(f"Fresh finalist IDs: {result['fresh_finalist_strategy_ids']}")
    print(f"Protected evidence reads: {result['protected_evidence_reads']}")
    print(f"Provider reads: {result['provider_reads']}")
    print(f"Broker reads: {result['broker_reads']}")
    print(f"Order/PAPER/LIVE writes: {result['order_writes']} / {result['paper_submits']} / {result['live_writes']}")
    print(f"Phase 11 support writes: {result['phase11_support_writes']}")
    print(f"Independent validation pass: {validation['pass']}")
    print(f"Pass: {result['pass'] and validation['pass']}")


if __name__ == "__main__":
    main()
