from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from packages.backtesting.alpha_gate_beneficial_ownership_feasibility import (
    BENEFICIAL_OWNERSHIP_ALLOWED_FORMS,
    BENEFICIAL_OWNERSHIP_ALPHA_HYPOTHESES_FROZEN,
    BENEFICIAL_OWNERSHIP_AUTOMATIC_BROKER_FAILOVER,
    BENEFICIAL_OWNERSHIP_AUTOMATION_WRITES,
    BENEFICIAL_OWNERSHIP_BROKER_READS,
    BENEFICIAL_OWNERSHIP_BROKER_WRITES,
    BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
    BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_LIVE_WRITES,
    BENEFICIAL_OWNERSHIP_MECHANISM,
    BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
    BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED,
    BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM,
    BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED,
    BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED,
    BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
    BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM,
    BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
    BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED,
    BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
    BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS,
    BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
    BENEFICIAL_OWNERSHIP_ORDER_WRITES,
    BENEFICIAL_OWNERSHIP_PAPER_SUBMITS,
    BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED,
    BENEFICIAL_OWNERSHIP_PROVIDER_READS_ALLOWED,
    BENEFICIAL_OWNERSHIP_PROVIDER_WRITES,
    BENEFICIAL_OWNERSHIP_QUARTERS,
    BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
    BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM,
    BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
    BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF,
    BENEFICIAL_OWNERSHIP_SOURCE_START,
    BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE,
    BENEFICIAL_OWNERSHIP_STRATA,
    BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE,
    BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED,
    BeneficialOwnershipFeasibilityError,
    BeneficialOwnershipIndexRow,
    BeneficialOwnershipSourceFeasibility,
    _decision_session,
    _resolve_identity,
    beneficial_ownership_feasibility_fingerprint,
    parse_master_index,
    parse_submission_metadata,
    select_stratified_sample,
)
from packages.core.atomic_io import atomic_write_text
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES,
    SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
)


BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT = (
    "alpha-gate-sec-beneficial-ownership-source-repair-v2-master-index-role-bounded-index-size-no-market-outcomes"
)
BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT = (
    "78bf3f18368114a5a6073e8a4d66a0c13ee29a5da78b8adeb1d71b1f10c6f78c"
)
BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD = "37194556012bc6df3f5e5579f2dacdcb5bed738b"
BENEFICIAL_OWNERSHIP_V1_FAILURE_ACCESSION = "0001193125-16-687002"
BENEFICIAL_OWNERSHIP_V1_FAILURE_REASON = (
    "conflicting SEC master-index metadata for accession 0001193125-16-687002"
)
BENEFICIAL_OWNERSHIP_V1_INDEX_SUCCESS = 9
BENEFICIAL_OWNERSHIP_V1_INDEX_FAILURES = 34
BENEFICIAL_OWNERSHIP_V1_DISCOVERY_ROWS_BEFORE_FAILURE = 49_349
BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED = BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED
BENEFICIAL_OWNERSHIP_REPAIR_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/beneficial_ownership_feasibility_v2/source_audit.json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _repair_fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
        "parent_feasibility_contract": BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
        "parent_feasibility_fingerprint": BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
        "v1_failed_head": BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD,
        "v1_failure_accession": BENEFICIAL_OWNERSHIP_V1_FAILURE_ACCESSION,
        "v1_failure_reason": BENEFICIAL_OWNERSHIP_V1_FAILURE_REASON,
        "quarter_index_max_response_bytes": SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES,
        "submission_max_response_bytes": SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
        "master_index_cik_role": "INDEXED_ARCHIVE_ENTITY_NOT_SUBJECT_SECURITY_IDENTITY",
        "duplicate_accession_rule": (
            "SAME_ACCESSION_REQUIRES_EXACT_FORM_DATE_ERA_FORM_CLASS_STRATUM_"
            "THEN_DETERMINISTIC_CANONICAL_INDEX_ROW"
        ),
        "subject_cik_source": "SEC_COMPLETE_SUBMISSION_HEADER_SUBJECT_COMPANY",
        "identity_rule": (
            "EXACT_HEADER_SUBJECT_CIK_DECISION_DATE_COMMON_STOCK_"
            "STRONG_OR_MEDIUM_EXACTLY_ONE_INSTRUMENT"
        ),
        "numeric_gates_unchanged": {
            "quarter_indexes": BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
            "min_discovered_per_stratum": BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM,
            "sample_per_stratum": BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM,
            "sample_size": BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
            "min_submission_success": BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
            "min_accession_reconciled": BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED,
            "min_form_reconciled": BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED,
            "min_filing_date_reconciled": BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED,
            "min_subject_cik_extracted": BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED,
            "min_acceptance_decisions": BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
            "min_unique_subject_ciks": BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
            "min_structured_xml_markers": BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
            "min_legacy_cusip_markers": BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
            "min_unambiguous_common_stock_mappings": (
                BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS
            ),
            "min_parsed_per_stratum": BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM,
        },
        "alpha_hypotheses_frozen": BENEFICIAL_OWNERSHIP_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": BENEFICIAL_OWNERSHIP_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": BENEFICIAL_OWNERSHIP_PROVIDER_WRITES,
            "broker_reads": BENEFICIAL_OWNERSHIP_BROKER_READS,
            "broker_writes": BENEFICIAL_OWNERSHIP_BROKER_WRITES,
            "order_writes": BENEFICIAL_OWNERSHIP_ORDER_WRITES,
            "paper_submits": BENEFICIAL_OWNERSHIP_PAPER_SUBMITS,
            "live_writes": BENEFICIAL_OWNERSHIP_LIVE_WRITES,
            "automation_writes": BENEFICIAL_OWNERSHIP_AUTOMATION_WRITES,
            "automatic_broker_failover": BENEFICIAL_OWNERSHIP_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def beneficial_ownership_source_repair_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_repair_fingerprint_payload()).encode("utf-8")).hexdigest()


def dedupe_discovery_v2(
    rows: Iterable[BeneficialOwnershipIndexRow],
) -> tuple[tuple[BeneficialOwnershipIndexRow, ...], int]:
    """Collapse multi-entity index associations without changing filing-level semantics."""

    by_accession: dict[str, BeneficialOwnershipIndexRow] = {}
    duplicate_associations = 0
    for row in rows:
        prior = by_accession.get(row.accession_number)
        if prior is None:
            by_accession[row.accession_number] = row
            continue

        prior_semantics = (
            prior.form,
            prior.filing_date,
            prior.era,
            prior.form_class,
            prior.stratum,
        )
        row_semantics = (
            row.form,
            row.filing_date,
            row.era,
            row.form_class,
            row.stratum,
        )
        if prior_semantics != row_semantics:
            raise BeneficialOwnershipFeasibilityError(
                "conflicting SEC master-index filing semantics for accession "
                f"{row.accession_number}: {prior_semantics!r} != {row_semantics!r}"
            )

        duplicate_associations += 1
        by_accession[row.accession_number] = min(
            (prior, row),
            key=lambda item: (
                item.filename,
                item.index_cik,
                item.company_name,
            ),
        )

    deduped = tuple(
        sorted(
            by_accession.values(),
            key=lambda row: (row.filing_date, row.accession_number, row.index_cik, row.filename),
        )
    )
    return deduped, duplicate_associations


def authoritative_subject_cik(metadata: object) -> str | None:
    subject_cik = getattr(metadata, "subject_cik", None)
    if subject_cik is None:
        return None
    text = str(subject_cik).strip()
    return text or None


class BeneficialOwnershipSourceFeasibilityV2(BeneficialOwnershipSourceFeasibility):
    """Targeted v2 repair preserving v1 failure and all frozen numeric source gates."""

    def run(self) -> dict[str, Any]:
        if beneficial_ownership_feasibility_fingerprint() != BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT:
            raise BeneficialOwnershipFeasibilityError("parent v1 feasibility fingerprint drifted")
        actual_repair = beneficial_ownership_source_repair_fingerprint()
        if actual_repair != BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT:
            raise BeneficialOwnershipFeasibilityError(
                f"frozen source-repair fingerprint drifted: {actual_repair}"
            )
        if SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES != 64_000_000:
            raise BeneficialOwnershipFeasibilityError("SEC quarterly-index response boundary drifted")
        if SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES != 20_000_000:
            raise BeneficialOwnershipFeasibilityError("SEC submission response boundary drifted")
        if BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT != 43:
            raise BeneficialOwnershipFeasibilityError("frozen quarter index count drifted")
        if IDENTITY_CONTRACT_VERSION != "instrument-identity-v4-no-issuer-level-medium-collapse":
            raise BeneficialOwnershipFeasibilityError("instrument identity contract drifted")

        discovery: list[BeneficialOwnershipIndexRow] = []
        index_reports: list[dict[str, Any]] = []
        index_failures: list[dict[str, Any]] = []
        for index, (year, quarter) in enumerate(BENEFICIAL_OWNERSHIP_QUARTERS, start=1):
            try:
                document = self._cached_index(year, quarter)
                rows = parse_master_index(document.text)
                discovery.extend(rows)
                index_reports.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "source_url": document.source_url,
                        "source_sha256": document.source_sha256,
                        "eligible_rows": len(rows),
                    }
                )
            except Exception as exc:
                index_failures.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index == 1 or index % 5 == 0 or index == len(BENEFICIAL_OWNERSHIP_QUARTERS):
                print(
                    f"Beneficial-ownership v2 index progress: {index}/{len(BENEFICIAL_OWNERSHIP_QUARTERS)} "
                    f"success={len(index_reports)} failures={len(index_failures)} eligible_rows={len(discovery)}"
                )

        discovered, duplicate_accession_associations = dedupe_discovery_v2(discovery)
        discovered_by_stratum = Counter(row.stratum for row in discovered)
        sample = select_stratified_sample(discovered)
        sample_by_stratum = Counter(row.stratum for row in sample)

        sampled_reports: list[dict[str, Any]] = []
        submission_failures: list[dict[str, Any]] = []
        parsed_per_stratum: Counter[str] = Counter()
        accession_reconciled = 0
        form_reconciled = 0
        filing_date_reconciled = 0
        subject_cik_extracted = 0
        subject_cik_equals_index_cik = 0
        acceptance_decisions = 0
        structured_xml_markers = 0
        legacy_cusip_markers = 0
        unambiguous_mappings = 0
        unique_subject_ciks: set[str] = set()
        mapping_statuses: Counter[str] = Counter()
        item4_markers = 0
        event_date_markers = 0

        for index, row in enumerate(sample, start=1):
            try:
                document = self._cached_submission(row)
                metadata = parse_submission_metadata(document.text)
                parsed_per_stratum[row.stratum] += 1

                accession_ok = metadata.accession_number == row.accession_number
                form_ok = metadata.form == row.form
                filing_date_ok = metadata.filing_date == row.filing_date
                subject_cik = authoritative_subject_cik(metadata)
                subject_ok = subject_cik is not None

                if accession_ok:
                    accession_reconciled += 1
                if form_ok:
                    form_reconciled += 1
                if filing_date_ok:
                    filing_date_reconciled += 1
                if subject_ok and subject_cik is not None:
                    subject_cik_extracted += 1
                    unique_subject_ciks.add(subject_cik)
                    if subject_cik == row.index_cik:
                        subject_cik_equals_index_cik += 1
                if row.era == "structured" and metadata.structured_primary_xml_marker:
                    structured_xml_markers += 1
                if row.era == "legacy" and metadata.cusip_marker:
                    legacy_cusip_markers += 1
                if metadata.item4_marker:
                    item4_markers += 1
                if metadata.event_date_marker:
                    event_date_markers += 1

                decision_date = None
                identity = {
                    "status": "NOT_ATTEMPTED",
                    "unique_instrument_count": 0,
                    "instruments": [],
                    "mapping_evidence": [],
                }
                if metadata.acceptance_datetime:
                    decision_date = _decision_session(metadata.acceptance_datetime)
                    acceptance_decisions += 1
                if subject_cik is not None and decision_date is not None:
                    reference_rows = self._cached_reference(cik=subject_cik, as_of_date=decision_date)
                    identity = _resolve_identity(
                        reference_rows,
                        subject_cik=subject_cik,
                        as_of_date=decision_date,
                    )
                    mapping_statuses[identity["status"]] += 1
                    if identity["status"] == "UNAMBIGUOUS_PIT_INSTRUMENT":
                        unambiguous_mappings += 1

                sampled_reports.append(
                    {
                        "index_row": asdict(row),
                        "master_index_cik_role": "INDEXED_ARCHIVE_ENTITY_NOT_SUBJECT_SECURITY_IDENTITY",
                        "submission_source_url": document.source_url,
                        "submission_source_sha256": document.source_sha256,
                        "metadata": asdict(metadata),
                        "accession_reconciled": accession_ok,
                        "form_reconciled": form_ok,
                        "filing_date_reconciled": filing_date_ok,
                        "subject_cik_extracted": subject_ok,
                        "subject_cik_equals_index_cik_diagnostic": (
                            subject_cik == row.index_cik if subject_cik is not None else None
                        ),
                        "decision_session": decision_date.isoformat() if decision_date else None,
                        "identity_subject_cik": subject_cik,
                        "identity": identity,
                    }
                )
            except Exception as exc:
                submission_failures.append(
                    {
                        "accession_number": row.accession_number,
                        "stratum": row.stratum,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index == 1 or index % 10 == 0 or index == len(sample):
                print(
                    f"Beneficial-ownership v2 submission progress: {index}/{len(sample)} "
                    f"parsed={len(sampled_reports)} failures={len(submission_failures)} "
                    f"unambiguous={unambiguous_mappings}"
                )

        stratum_discovery_gate = {
            stratum: int(discovered_by_stratum.get(stratum, 0)) >= BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM
            for stratum in BENEFICIAL_OWNERSHIP_STRATA
        }
        stratum_sample_exact = {
            stratum: int(sample_by_stratum.get(stratum, 0)) == BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM
            for stratum in BENEFICIAL_OWNERSHIP_STRATA
        }
        stratum_parsed_gate = {
            stratum: int(parsed_per_stratum.get(stratum, 0)) >= BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM
            for stratum in BENEFICIAL_OWNERSHIP_STRATA
        }
        gates = {
            "quarter_indexes_exact": (
                len(index_reports) == BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT and not index_failures
            ),
            "discovered_per_stratum_min": all(stratum_discovery_gate.values()),
            "sample_per_stratum_exact": all(stratum_sample_exact.values()),
            "sample_size_exact": len(sample) == BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
            "submission_success_min": len(sampled_reports) >= BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
            "accession_reconciled_min": accession_reconciled >= BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED,
            "form_reconciled_min": form_reconciled >= BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED,
            "filing_date_reconciled_min": (
                filing_date_reconciled >= BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED
            ),
            "subject_cik_extracted_min": subject_cik_extracted >= BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_EXTRACTED,
            "acceptance_decisions_min": acceptance_decisions >= BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
            "unique_subject_ciks_min": len(unique_subject_ciks) >= BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
            "structured_xml_markers_min": structured_xml_markers >= BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
            "legacy_cusip_markers_min": legacy_cusip_markers >= BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
            "unambiguous_common_stock_mappings_min": (
                unambiguous_mappings >= BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS
            ),
            "parsed_per_stratum_min": all(stratum_parsed_gate.values()),
        }
        passed = all(gates.values())

        report = {
            "contract_version": BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_CONTRACT,
            "source_repair_fingerprint": BENEFICIAL_OWNERSHIP_SOURCE_REPAIR_FINGERPRINT,
            "parent_feasibility_contract": BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
            "parent_feasibility_fingerprint": BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
            "source_xbrl_merge": BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE,
            "mechanism": BENEFICIAL_OWNERSHIP_MECHANISM,
            "status": "FEASIBILITY_PASS" if passed else "FEASIBILITY_FAIL",
            "pass": passed,
            "v1_failure_preserved": {
                "head": BENEFICIAL_OWNERSHIP_V1_FAILED_HEAD,
                "status": "NOT_ACCEPTED",
                "reason": BENEFICIAL_OWNERSHIP_V1_FAILURE_REASON,
                "accession": BENEFICIAL_OWNERSHIP_V1_FAILURE_ACCESSION,
                "successful_indexes_before_failure": BENEFICIAL_OWNERSHIP_V1_INDEX_SUCCESS,
                "failed_indexes_before_failure": BENEFICIAL_OWNERSHIP_V1_INDEX_FAILURES,
                "discovery_rows_before_failure": BENEFICIAL_OWNERSHIP_V1_DISCOVERY_ROWS_BEFORE_FAILURE,
                "target_outcome_rows_read": 0,
                "protected_return_rows_read": 0,
                "protected_holdout_consumed": False,
            },
            "repair_semantics": {
                "quarter_index_max_response_bytes": SEC_ARCHIVE_INDEX_MAX_RESPONSE_BYTES,
                "submission_max_response_bytes": SEC_ARCHIVE_SUBMISSION_MAX_RESPONSE_BYTES,
                "master_index_cik_role": "INDEXED_ARCHIVE_ENTITY_NOT_SUBJECT_SECURITY_IDENTITY",
                "subject_cik_source": "SEC_COMPLETE_SUBMISSION_HEADER_SUBJECT_COMPANY",
                "identity_cik_source": "SEC_COMPLETE_SUBMISSION_HEADER_SUBJECT_COMPANY",
                "numeric_thresholds_changed": False,
            },
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_allowed": True,
            "provider_reads_performed": int(sum(self.source_reads.values())),
            "provider_read_breakdown": dict(sorted(self.source_reads.items())),
            "cache_hit_breakdown": dict(sorted(self.cache_hits.items())),
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "source_start": BENEFICIAL_OWNERSHIP_SOURCE_START.isoformat(),
            "source_cutoff": BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF.isoformat(),
            "structured_compliance_date": BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE.isoformat(),
            "allowed_forms": list(BENEFICIAL_OWNERSHIP_ALLOWED_FORMS),
            "quarter_index_count": BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
            "successful_indexes": len(index_reports),
            "failed_indexes": len(index_failures),
            "raw_discovery_rows": len(discovery),
            "duplicate_accession_associations_collapsed": duplicate_accession_associations,
            "discovered_eligible_filings": len(discovered),
            "discovered_by_stratum": dict(sorted(discovered_by_stratum.items())),
            "sample_rule": "HASH_RANK_ACCESSION_WITHIN_ERA_X_FORM_CLASS_STRATUM",
            "sample_size": len(sample),
            "sample_by_stratum": dict(sorted(sample_by_stratum.items())),
            "submission_success": len(sampled_reports),
            "submission_failures": len(submission_failures),
            "parsed_per_stratum": dict(sorted(parsed_per_stratum.items())),
            "accession_reconciled": accession_reconciled,
            "form_reconciled": form_reconciled,
            "filing_date_reconciled": filing_date_reconciled,
            "subject_cik_extracted": subject_cik_extracted,
            "subject_cik_equals_index_cik_diagnostic": subject_cik_equals_index_cik,
            "acceptance_decisions": acceptance_decisions,
            "unique_subject_ciks": len(unique_subject_ciks),
            "structured_xml_markers": structured_xml_markers,
            "legacy_cusip_markers": legacy_cusip_markers,
            "item4_markers_diagnostic": item4_markers,
            "event_date_markers_diagnostic": event_date_markers,
            "unambiguous_common_stock_mappings": unambiguous_mappings,
            "mapping_statuses": dict(sorted(mapping_statuses.items())),
            "stratum_discovery_gate": stratum_discovery_gate,
            "stratum_sample_exact": stratum_sample_exact,
            "stratum_parsed_gate": stratum_parsed_gate,
            "gates": gates,
            "index_reports": index_reports,
            "index_failures": index_failures,
            "sampled_reports": sampled_reports,
            "failures": submission_failures,
            "next_scientific_action": (
                "If feasibility passes, freeze a finite Schedule 13D/13G alpha family, exact ownership/purpose semantics, "
                "chronology, outcomes, costs, dependence, multiplicity, robustness, winner/finalist rules, and protected "
                "policy before any market outcomes."
            ),
        }

        report_path = self.derived_root / BENEFICIAL_OWNERSHIP_REPAIR_REPORT_RELATIVE
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
