from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_finalist_audit import (
    PHASE32_EXPECTED_FINALISTS,
    PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION,
    PHASE32_PROTECTED_PLAN_CONTRACT_VERSION,
    Phase32FinalistAuditError,
    Phase32FinalistBlindnessAudit,
)
from packages.backtesting.phase32_policy import phase32_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 32 — Independent Finalist Blindness / Lineage Audit")
    print(f"Frozen scientific policy fingerprint: {phase32_policy_fingerprint()}")
    print(f"Audit contract: {PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION}")
    print(f"Protected plan contract: {PHASE32_PROTECTED_PLAN_CONTRACT_VERSION}")
    print(f"Accepted development finalist target: {list(PHASE32_EXPECTED_FINALISTS)}")
    print("Development outcomes: already opened / independently recomputed in this audit")
    print("Protected predictor metadata: source-only / allowed")
    print("Protected stock/SPY returns: FORBIDDEN / UNREAD")
    print("Provider network / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = Phase32FinalistBlindnessAudit(load_settings()).run()
    except (Phase32FinalistAuditError, OSError, ValueError) as exc:
        print("Phase 32 finalist blindness / lineage audit: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Stop here. Do not open protected returns or alter the frozen scientific policy.")
        return 2

    gate = report["protected_source_only_sample_gate"]
    checks = gate["checks"]
    print("Phase 32 finalist blindness / lineage audit: PASS")
    print(f"Selection survivors independently reproduced: {report['selection_survivor_ids']}")
    print(f"Selection winners independently reproduced: {report['selection_winner_ids']}")
    print(f"Frozen finalists independently reproduced: {report['finalist_ids']}")
    print(
        "Protected finalist source-only population: "
        f"rows={gate['event_rows']} sessions={gate['signal_sessions']} "
        f"instruments={gate['unique_instruments']}"
    )
    print(
        "Protected source-only sample gates: "
        f"rows={checks['min_event_rows']} sessions={checks['min_signal_sessions']} "
        f"instruments={checks['min_unique_instruments']}"
    )
    print(f"Protected plan rows SHA-256: {report['protected_plan_rows_sha256']}")
    print(f"Protected plan fingerprint: {report['protected_plan_fingerprint']}")
    print(f"Finalist audit fingerprint: {report['audit_fingerprint']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print("Provider network/broker/order/PAPER/LIVE/automation activity: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Status: {report['status']}")
    if report["protected_return_authorized_after_fingerprint_freeze"]:
        print(
            "Next scientific action: freeze this exact audit fingerprint and protected-plan hashes "
            "into a finalist-only protected evaluator before any protected return read."
        )
    else:
        print(
            "Next scientific action: protected sample gates are impossible from source-only counts; "
            "close Phase32 negative without reading protected returns."
        )
    print("Pass: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
