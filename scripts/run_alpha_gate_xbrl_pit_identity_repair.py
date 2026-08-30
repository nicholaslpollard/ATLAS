from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_pit_identity_repair import (
    XBRL_PIT_IDENTITY_REPAIR_CONTRACT,
    XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT,
    XBRL_PIT_IDENTITY_REPAIR_REASON,
    XBRLPITIdentitySemanticsRepair,
    xbrl_pit_identity_repair_fingerprint,
)
from packages.backtesting.alpha_gate_xbrl_pit_audit import XBRLPITAuditError
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS XBRL PIT Targeted Identity-Semantics Repair")
    print(f"Repair contract: {XBRL_PIT_IDENTITY_REPAIR_CONTRACT}")
    print(f"Repair fingerprint: {xbrl_pit_identity_repair_fingerprint()}")
    print(f"Frozen fingerprint expected: {XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT}")
    print(f"Repair reason: {XBRL_PIT_IDENTITY_REPAIR_REASON}")
    print("Preserved v1 result: AUDIT_FAIL (139 mappings / 28 issuers with >=3 mappings)")
    print("Corrected Massive identity semantics: exact CIK + historical date + active=true + type=CS")
    print("Same 40 issuers, same accessions, same SEC chronology, same numeric gates")
    print("This replay reads existing local source-only caches; no provider calls are performed")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = XBRLPITIdentitySemanticsRepair(load_settings()).run()
    except (XBRLPITAuditError, OSError, ValueError) as exc:
        print("XBRL PIT targeted identity repair: NOT ACCEPTED")
        print(f"Reason: {exc}")
        return 2

    print(f"XBRL PIT targeted identity repair: {report['status']}")
    print(f"Preserved v1 report SHA-256: {report['v1_report_sha256']}")
    print(f"Replayed identity decisions: {report['replayed_identity_decisions']}")
    print(f"Local Massive cache files read: {report['cache_files_read']}")
    print(f"Identity status counts: {report['identity_status_counts']}")
    print(f"Unambiguous PIT common-stock mappings: {report['unambiguous_identity_mappings']}")
    print(f"Issuers with >=3 unambiguous common-stock mappings: {report['issuers_with_3_unambiguous_mappings']}")
    print(f"Gates: {report['gates']}")
    print(f"Provider reads performed: {report['provider_reads_performed']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(
        "Provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: "
        f"{report['provider_writes_performed']} / {report['broker_reads_performed']} / "
        f"{report['broker_writes_performed']} / {report['order_writes_performed']} / "
        f"{report['paper_submits_performed']} / {report['live_writes_performed']} / "
        f"{report['automation_writes_performed']}"
    )
    print(f"Repair report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
