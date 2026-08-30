from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
    BENEFICIAL_OWNERSHIP_ALLOWED_FORMS,
    BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
    BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_MECHANISM,
    BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
    BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM,
    BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED,
    BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
    BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM,
    BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
    BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
    BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS,
    BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
    BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
    BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM,
    BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
    BENEFICIAL_OWNERSHIP_STRATA,
    BeneficialOwnershipFeasibilityError,
)
from packages.backtesting.alpha_gate_beneficial_ownership_source_repair import (
    BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED,
    BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
    BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD,
    BENEFICIAL_OWNERSHIP_V1_FAILURE_REASON,
    BeneficialOwnershipSourceFeasibilityV2,
    beneficial_ownership_source_repair_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_edgar import SEC_EDGAR_CONTACT_EMAIL_ENV
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES,
    SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
    SECEDGARArchiveClient,
)


def main() -> int:
    print("ATLAS Pre-Phase33 Alpha Gate — SEC Schedule 13D/13G Beneficial Ownership Source Repair V2")
    print(f"Parent feasibility contract: {BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT}")
    print(f"Parent feasibility fingerprint: {BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT}")
    print(f"Targeted source-repair contract: {BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT}")
    print(f"Targeted source-repair fingerprint: {beneficial_ownership_source_repair_fingerprint()}")
    print(f"Expected repair fingerprint: {BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT}")
    print(f"Mechanism: {BENEFICIAL_OWNERSHIP_MECHANISM}")
    print(
        f"Preserved v1 NOT ACCEPTED result: head={BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD}; "
        f"reason={BENEFICIAL_OWNERSHIP_V1_FAILURE_REASON}"
    )
    print("Root-cause repair 1: SEC quarterly master.idx response bound raised to a still-bounded 64,000,000 bytes")
    print(
        "Root-cause repair 2: master-index CIK is preserved as index/archive entity provenance; "
        "SUBJECT COMPANY CIK from the official complete-submission header is the security identity authority"
    )
    print(
        "Duplicate-accession rule: differing index associations are collapsed only when accession/form/date/era/form-class/stratum "
        "agree exactly; filing-semantic conflicts still fail closed"
    )
    print("Discovery source: official SEC www.sec.gov/Archives/edgar/full-index quarterly master indexes")
    print("Submission source: official SEC complete submission .txt archives")
    print("PIT identity source: Massive /v3/reference/tickers exact header subject-CIK/date active common stock")
    print(f"SEC fair-access identity: ATLAS + local {SEC_EDGAR_CONTACT_EMAIL_ENV} contact")
    print(
        f"Transport bounds: quarterly_index={SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES} bytes; "
        f"submission={SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES} bytes"
    )
    print(
        f"Frozen source window: 2016-01-01..2026-08-11; quarterly indexes={BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT}"
    )
    print(f"Allowed forms: {list(BENEFICIAL_OWNERSHIP_ALLOWED_FORMS)}")
    print(
        f"Stratified sample: {BENEFICIAL_OWNERSHIP_SAMPLE_SIZE} total = "
        f"{BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM} x {len(BENEFICIAL_OWNERSHIP_STRATA)} strata"
    )
    print(f"Strata: {list(BENEFICIAL_OWNERSHIP_STRATA)}")
    print(
        "Frozen numeric source gates retained: "
        f"discovered_per_stratum>={BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM}; "
        f"submission_success>={BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS}; "
        f"filing_date_reconciled>={BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED}; "
        f"subject_cik_extracted>={BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED}; "
        f"acceptance_decisions>={BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS}; "
        f"unique_subject_ciks>={BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS}; "
        f"structured_xml_markers>={BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS}; "
        f"legacy_cusip_markers>={BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS}; "
        f"unambiguous_common_stock_mappings>={BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS}; "
        f"parsed_per_stratum>={BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM}"
    )
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Market prices/returns/target outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider writes / broker / order / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        settings = load_settings()
        report = BeneficialOwnershipSourceFeasibilityV2(
            settings,
            SECEDGARArchiveClient(),
            MassiveCIKPITReferenceProvider(settings),
        ).run()
    except (BeneficialOwnershipFeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("SEC beneficial-ownership source repair v2: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No alpha hypothesis, Phase33 entry, protected read, or trading authority was granted.")
        return 2

    print()
    print(f"SEC beneficial-ownership source repair v2: {report['status']}")
    print(
        f"Quarter indexes: success={report['successful_indexes']} failures={report['failed_indexes']} "
        f"expected={report['quarter_index_count']}"
    )
    print(f"Raw discovered index rows: {report['raw_discovery_rows']}")
    print(
        "Duplicate accession/index associations collapsed under exact filing semantics: "
        f"{report['duplicate_accession_associations_collapsed']}"
    )
    print(f"Discovered eligible filings: {report['discovered_eligible_filings']}")
    print(f"Discovered by stratum: {report['discovered_by_stratum']}")
    print(f"Sample size: {report['sample_size']}")
    print(f"Sample by stratum: {report['sample_by_stratum']}")
    print(
        f"Submission parse: success={report['submission_success']} failures={report['submission_failures']}"
    )
    print(f"Parsed per stratum: {report['parsed_per_stratum']}")
    print(f"Accession reconciled: {report['accession_reconciled']}")
    print(f"Form reconciled: {report['form_reconciled']}")
    print(f"Filing date reconciled: {report['filing_date_reconciled']}")
    print(f"Authoritative SUBJECT COMPANY CIK extracted: {report['subject_cik_extracted']}")
    print(
        "SUBJECT COMPANY CIK equals master-index CIK (diagnostic only): "
        f"{report['subject_cik_equals_index_cik_diagnostic']}"
    )
    print(f"Acceptance/decision sessions reconstructed: {report['acceptance_decisions']}")
    print(f"Unique subject CIKs: {report['unique_subject_ciks']}")
    print(f"Structured-era primary XML markers: {report['structured_xml_markers']}")
    print(f"Legacy-era CUSIP markers: {report['legacy_cusip_markers']}")
    print(f"13D Item 4 markers (diagnostic): {report['item4_markers_diagnostic']}")
    print(f"Event-date markers (diagnostic): {report['event_date_markers_diagnostic']}")
    print(f"Unambiguous PIT common-stock mappings: {report['unambiguous_common_stock_mappings']}")
    print(f"Mapping statuses: {report['mapping_statuses']}")
    print(f"Gates: {report['gates']}")
    print(f"Provider reads: {report['provider_reads_performed']} {report['provider_read_breakdown']}")
    print(f"Cache hits: {report['cache_hit_breakdown']}")
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
    print(f"Feasibility report: {report['report_path']}")
    print(f"Next scientific action: {report['next_scientific_action']}")
    print(f"Pass: {report['pass']}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
