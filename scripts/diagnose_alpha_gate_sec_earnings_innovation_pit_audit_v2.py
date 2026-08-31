from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_diagnostics_v2 import (
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT,
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_GUARD,
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_PURPOSE,
    EarningsInnovationPITDiagnosticV2Error,
    SECEarningsInnovationPITDiagnosticsV2,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.sec_edgar import SECEDGARClient
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient


def main() -> int:
    print("ATLAS Pre-Phase33 — SEC Earnings-Innovation PIT Failure Diagnostics V2")
    print(f"Diagnostic contract: {EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT}")
    print(f"Diagnostic fingerprint: {EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT}")
    print(f"Purpose: {EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_PURPOSE}")
    print(f"Failed-audit guard: {EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_GUARD}")
    print("V1 diagnostic hash guard defect: PRESERVED / NOT REUSED")
    print("Original PIT_AUDIT_FAIL artifact: READ-ONLY / STRUCTURALLY VERIFIED")
    print("Frozen PIT acceptance gates: UNCHANGED")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = SECEarningsInnovationPITDiagnosticsV2(
            load_settings(), SECXBRLCompanyFactsClient(), SECEDGARClient()
        ).run()
    except (EarningsInnovationPITDiagnosticV2Error, ProviderError, OSError, ValueError) as exc:
        print("SEC earnings-innovation PIT diagnostics V2: NOT COMPLETE")
        print(f"Reason: {exc}")
        print("No frozen gate, market outcome, protected evidence, or trading authority was changed.")
        return 2

    print()
    print(
        "SEC earnings-innovation PIT diagnostics V2: "
        + ("COMPLETE" if report["diagnostic_complete"] else "INCOMPLETE")
    )
    print(f"Preserved failed PIT report SHA-256: {report['preserved_failed_report_sha256']}")
    print(f"Failed PIT report structurally verified: {report['preserved_failed_report_verified']}")
    print(f"Feasibility parent report SHA-256: {report['feasibility_parent_report_sha256']}")
    print(f"Company Facts hash matches: {report['companyfacts_hash_matches']}")
    print(f"Period-context diagnostic count: {report['period_context_diagnostic_count']}")
    for index, row in enumerate(report["period_context_diagnostics"], start=1):
        print(f"PERIOD_DIAGNOSTIC_{index}: {json.dumps(row, sort_keys=True)}")
    print(f"SEC submissions root success: {report['submissions_root_success']}")
    print(f"SEC submissions shard reads: {report['submissions_shard_reads']}")
    print(f"Missing accession metadata count: {report['missing_accession_metadata_count']}")
    print(f"Accession-metadata diagnostic count: {report['accession_metadata_diagnostic_count']}")
    for index, row in enumerate(report["accession_metadata_diagnostics"], start=1):
        print(f"METADATA_DIAGNOSTIC_{index}: {json.dumps(row, sort_keys=True)}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Diagnostic report: {report['report_path']}")
    print(f"Complete: {report['diagnostic_complete']}")
    return 0 if report["diagnostic_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
