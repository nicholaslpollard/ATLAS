from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_ACCEPTANCE_SOURCE,
    EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM,
    EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE,
    EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION,
    EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS,
    EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS,
    EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS,
    EarningsInnovationPITAuditError,
    SECEarningsInnovationPITAudit,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.sec_edgar import SECEDGARClient, SEC_EDGAR_CONTACT_EMAIL_ENV
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — SEC Earnings-Innovation PIT Source Audit")
    print(f"PIT audit contract: {EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT}")
    print(f"PIT audit fingerprint: {EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT}")
    print("Parent evidence: accepted 300-issuer diluted-EPS feasibility census")
    print(f"Acceptance source: {EARNINGS_INNOVATION_PIT_ACCEPTANCE_SOURCE}")
    print(f"Decision timing: {EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE}")
    print(
        "Frozen support gates: "
        f"audited observations>={EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS}; "
        f"history-ready issuers>={EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS}; "
        f"SUE-ready issuers>={EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS}; "
        f"acceptance coverage>={EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION:.0%}"
    )
    print(f"Earnings-announcement timing claim: {EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM}")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        report = SECEarningsInnovationPITAudit(
            load_settings(), SECXBRLCompanyFactsClient(), SECEDGARClient()
        ).run()
    except (EarningsInnovationPITAuditError, ProviderError, OSError, ValueError) as exc:
        print("SEC earnings-innovation PIT source audit: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No hypothesis, market outcome, protected read, Phase33 entry, or trading authority was granted.")
        return 2

    print()
    print(f"SEC earnings-innovation PIT source audit: {report['status']}")
    print(f"Parent report SHA-256: {report['parent_report_sha256']}")
    print(f"Company Facts hash matches: {report['companyfacts_hash_matches']}")
    print(f"Parent semantics reconciled: {report['parent_semantics_reconciled']}")
    print(f"Original-accession candidate observations: {report['original_accession_candidate_observations']}")
    print(f"Period-context ambiguities: {report['period_context_ambiguities']}")
    print(f"SEC submissions root success: {report['submissions_root_success']}")
    print(f"SEC submissions shard reads: {report['submissions_shard_reads']}")
    print(f"Missing accession metadata: {report['missing_accession_metadata']}")
    print(f"Metadata contradictions: {report['accession_metadata_contradictions']}")
    print(f"Acceptance chronology violations: {report['acceptance_not_after_period_end']}")
    print(f"Decision-session errors: {report['decision_session_errors']}")
    print(f"Audited observations: {report['audited_observations']}")
    print(f"Acceptance proven fraction: {report['acceptance_proven_fraction']:.6f}")
    print(f"Audited history-ready issuers: {report['audited_history_ready_issuers']}")
    print(f"Audited SUE-baseline-ready issuers: {report['audited_sue_baseline_ready_issuers']}")
    print(f"Calendar years observed: {report['calendar_years_observed']}")
    print(f"Gates: {report['gates']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(
        "Provider reads / writes / broker reads / writes / orders / PAPER / LIVE / automation: "
        f"{report['provider_reads_performed']} / {report['provider_writes_performed']} / "
        f"{report['broker_reads_performed']} / {report['broker_writes_performed']} / "
        f"{report['order_writes_performed']} / {report['paper_submits_performed']} / "
        f"{report['live_writes_performed']} / {report['automation_writes_performed']}"
    )
    print(f"PIT rows: {report['pit_rows_path']}")
    print(f"PIT audit report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
