from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase31_source_quality import (
    PHASE31_SOURCE_QUALITY_POLICY,
    Phase31Form4SourceQualityRepair,
    Phase31SourceQualityError,
    phase31_source_quality_fingerprint,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 31 — Form-4 Source-Quality Repair / Frozen-Evidence Replay")
    print(f"Frozen source-quality fingerprint: {phase31_source_quality_fingerprint()}")
    print(f"Policy: {PHASE31_SOURCE_QUALITY_POLICY}")
    print("Input: immutable failed-feasibility evidence + completed chronology diagnostic")
    print("Provider calls: DISABLED / ZERO")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Chronology rule: UNCHANGED")
    print("Raw provider evidence: PRESERVED")
    print("Repair rule: any transaction_date > filing_date contaminates the entire accession")
    print("Date coercion / field swaps / inferred reassignment: FORBIDDEN")
    print()

    settings = load_settings()
    try:
        report = Phase31Form4SourceQualityRepair(settings).run()
    except (Phase31SourceQualityError, OSError, ValueError) as exc:
        print("Phase 31 Form-4 source-quality repair: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Original FEASIBILITY_FAIL remains preserved. No scientific or trading authority granted.")
        return 2

    print("Phase 31 Form-4 source-quality repair: PASS")
    print(f"Raw rows preserved: {report['raw_rows']}")
    print(f"Chronology-violation seed rows: {report['chronology_violation_seed_rows']}")
    print(f"Contaminated accessions: {report['contaminated_accessions']}")
    print(f"Quarantined accession rows: {report['quarantined_accession_rows']}")
    print(f"Authoritative rows after fail-closed quarantine: {report['authoritative_rows']}")
    for window in report["windows"]:
        print(
            f"  {window['label']}: raw={window['raw_rows']} "
            f"seed_violations={window['chronology_violation_seed_rows']} "
            f"quarantined={window['quarantined_accession_rows']} "
            f"authoritative={window['authoritative_rows']} "
            f"transactions={window['authoritative_transaction_rows']} "
            f"tickers={window['authoritative_unique_tickers']} "
            f"P={window['authoritative_purchase_rows_P']} "
            f"S={window['authoritative_sale_rows_S']} "
            f"authoritative_sha256={window['authoritative_sha256']}"
        )
    print(f"Quarantine artifact: {report['quarantine_path']}")
    print(f"Quarantine SHA256: {report['quarantine_sha256']}")
    print(f"Repair report: {report['report_path']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Scientific-policy freeze authorized: {report['scientific_policy_freeze_authorized']}")
    print(f"Alpha support granted: {report['alpha_support_granted']}")
    print(f"Phase32 entry satisfied: {report['phase32_entry_satisfied']}")
    print(f"Pass: {report['pass']}")
    print()
    print("Interpretation: the original raw-feed FEASIBILITY_FAIL remains historical evidence.")
    print("A PASS here means Form-4 source evidence is usable only behind the frozen fail-closed quarantine.")
    print("It does not accept Phase31 and does not authorize any market-outcome read until the scientific contract is frozen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
