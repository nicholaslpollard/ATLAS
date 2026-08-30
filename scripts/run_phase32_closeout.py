from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_closeout import (
    PHASE32_ACCEPTED_AUDIT_FINGERPRINT,
    PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT,
    PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256,
    PHASE32_CLOSEOUT_REPORT_CONTRACT_VERSION,
    Phase32Closeout,
    Phase32CloseoutError,
)
from packages.backtesting.phase32_policy import phase32_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 32 — Negative Closeout")
    print(f"Frozen scientific policy fingerprint: {phase32_policy_fingerprint()}")
    print(f"Closeout contract: {PHASE32_CLOSEOUT_REPORT_CONTRACT_VERSION}")
    print(f"Accepted finalist audit fingerprint: {PHASE32_ACCEPTED_AUDIT_FINGERPRINT}")
    print(f"Accepted protected plan fingerprint: {PHASE32_ACCEPTED_PROTECTED_PLAN_FINGERPRINT}")
    print(f"Accepted protected plan rows SHA-256: {PHASE32_ACCEPTED_PROTECTED_PLAN_ROWS_SHA256}")
    print("Protected stock/SPY returns: FORBIDDEN / UNREAD")
    print("Provider network / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = Phase32Closeout(load_settings()).run()
    except (Phase32CloseoutError, OSError, ValueError) as exc:
        print("Phase 32 negative closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Stop here. Do not open protected returns, substitute a finalist, or alter the frozen policy.")
        return 2

    print("Phase 32 negative closeout: PASS")
    print(f"Disposition: {report['phase32_disposition']}")
    print(
        "Protected source-only population: "
        f"rows={report['protected_source_only_event_rows']} "
        f"sessions={report['protected_source_only_signal_sessions']} "
        f"instruments={report['protected_source_only_unique_instruments']}"
    )
    print(
        "Frozen minimums: "
        f"rows={report['protected_min_event_rows']} "
        f"sessions={report['protected_min_signal_sessions']} "
        f"instruments={report['protected_min_unique_instruments']}"
    )
    print(f"Failed source-only gate: {report['failed_protected_source_gate']}")
    print(f"Supported candidates: {report['supported_candidate_ids']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Historical supported alpha count after Phase32: {report['historical_supported_alpha_count_after_phase32']}")
    print(f"Phase33 entry satisfied: {report['phase33_entry_satisfied']}")
    print("Provider/broker/order/PAPER/LIVE/automation activity: 0 / 0 / 0 / 0 / 0 / 0")
    print("Next project action: merge Phase32 as ACCEPTED_NEGATIVE; Phase33 remains blocked; open only a materially different alpha mechanism next.")
    print("Pass: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
