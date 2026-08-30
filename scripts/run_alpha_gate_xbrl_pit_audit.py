from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_pit_audit import (
    XBRL_PIT_AUDIT_CONTRACT,
    XBRL_PIT_AUDIT_FINGERPRINT,
    XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE,
    XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER,
    XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS,
    XBRL_PIT_MIN_ACCEPTANCE_DECISIONS,
    XBRL_PIT_MIN_COMPANYFACTS_SUCCESS,
    XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS,
    XBRL_PIT_MIN_SEC_METADATA_RECONCILED,
    XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS,
    XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS,
    XBRLPITAuditError,
    XBRLPITSourceAudit,
    xbrl_pit_audit_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_edgar import SEC_EDGAR_CONTACT_EMAIL_ENV
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient
from packages.providers.sec_xbrl_pit import SECXBRLPITMetadataClient


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — SEC XBRL PIT Source/Chronology/Identity Audit")
    print(f"Audit contract: {XBRL_PIT_AUDIT_CONTRACT}")
    print(f"Audit fingerprint: {xbrl_pit_audit_fingerprint()}")
    print(f"Frozen fingerprint expected: {XBRL_PIT_AUDIT_FINGERPRINT}")
    print(f"Audit issuers: {XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE}")
    print(f"Maximum original 10-Q/10-K accessions per issuer: {XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER}")
    print(
        "Frozen source gates: "
        f"companyfacts>={XBRL_PIT_MIN_COMPANYFACTS_SUCCESS} "
        f"selected_original_filings>={XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS} "
        f"sec_metadata>={XBRL_PIT_MIN_SEC_METADATA_RECONCILED} "
        f"acceptance_decisions>={XBRL_PIT_MIN_ACCEPTANCE_DECISIONS} "
        f"unambiguous_identity>={XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS} "
        f"issuers_with_3_mappings>={XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS} "
        f"same_accession_conflicts<={XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS}"
    )
    print("Company Facts source: official SEC data.sec.gov/api/xbrl/companyfacts")
    print("Filing chronology source: official SEC data.sec.gov/submissions + SEC-declared shards")
    print("PIT instrument identity source: Massive /v3/reference/tickers filtered by exact CIK + date")
    print(f"SEC fair-access identity: ATLAS + local {SEC_EDGAR_CONTACT_EMAIL_ENV} contact")
    print("Fact version rule: exact accession versioned; later accessions never overwrite earlier facts")
    print("Decision rule: first XNYS session open strictly after SEC acceptance")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        settings = load_settings()
        report = XBRLPITSourceAudit(
            settings,
            SECXBRLCompanyFactsClient(),
            SECXBRLPITMetadataClient(),
            MassiveCIKPITReferenceProvider(settings),
        ).run()
    except (XBRLPITAuditError, ProviderError, OSError, ValueError) as exc:
        print("XBRL PIT source audit: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No market outcome, protected read, alpha support, Phase33 entry, or trading authority was granted.")
        return 2

    print()
    print(f"XBRL PIT source audit: {report['status']}")
    print(f"Entry feasibility evidence fingerprint: {report['entry_feasibility_evidence_fingerprint']}")
    print(f"Entry feasibility report SHA-256: {report['entry_feasibility_report_sha256']}")
    print(f"Audit issuer sample: {report['audit_issuer_sample_size']}")
    print(f"Successful Company Facts documents: {report['companyfacts_success']}")
    print(f"Selected original 10-Q/10-K filings: {report['selected_original_filings']}")
    print(f"SEC metadata reconciled: {report['sec_metadata_reconciled']}")
    print(f"Acceptance-time decisions reconstructed: {report['acceptance_decisions']}")
    print(f"Unambiguous PIT instrument mappings: {report['unambiguous_identity_mappings']}")
    print(f"Issuers with >=3 unambiguous mappings: {report['issuers_with_3_unambiguous_mappings']}")
    print(f"Same-accession context conflicts: {report['same_accession_context_conflicts']}")
    print(f"Exact duplicate fact rows: {report['exact_duplicate_fact_rows']}")
    print(f"Repeated cross-accession contexts: {report['repeated_cross_accession_contexts']}")
    print(f"Revised cross-accession contexts: {report['revised_cross_accession_contexts']}")
    print(f"Cross-accession version rows preserved: {report['cross_accession_version_rows']}")
    print(f"Gates: {report['gates']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Provider source reads: {report['provider_reads_performed']} {report['provider_read_breakdown']}")
    print(f"Cache hits: {report['cache_hits']}")
    print(
        "Provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: "
        f"{report['provider_writes_performed']} / {report['broker_reads_performed']} / "
        f"{report['broker_writes_performed']} / {report['order_writes_performed']} / "
        f"{report['paper_submits_performed']} / {report['live_writes_performed']} / "
        f"{report['automation_writes_performed']}"
    )
    print(f"Audit report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
