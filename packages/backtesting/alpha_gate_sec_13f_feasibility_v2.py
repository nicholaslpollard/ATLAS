from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from packages.backtesting.alpha_gate_sec_13f_feasibility import (
    SEC13FFeasibilityError,
    SEC_13F_ALLOWED_SUBMISSION_TYPES,
    SEC_13F_ANCHORS,
    SEC_13F_MAX_INFOTABLE_ORPHAN_ROWS,
    SEC_13F_MAX_INFOTABLE_PRIMARY_KEY_DUPLICATES,
    SEC_13F_MAX_INITIAL_HR_FILING_BEFORE_PERIOD_VIOLATIONS,
    SEC_13F_MAX_SUBMISSION_ACCESSION_DUPLICATES,
    SEC_13F_MECHANISM_CANDIDATE,
    SEC_13F_MIN_CALENDAR_YEAR_SPAN_INCLUSIVE,
    SEC_13F_MIN_INITIAL_HR_INFOTABLE_ROWS_PER_ANCHOR,
    SEC_13F_MIN_INITIAL_HR_SUBMISSIONS_PER_ANCHOR,
    SEC_13F_MIN_UNIQUE_INITIAL_HR_MANAGERS_PER_ANCHOR,
    SEC_13F_MIN_VALID_INITIAL_HR_CUSIP_FRACTION,
    SEC_13F_PROTECTED_SOURCE_CUTOFF,
    SEC_13F_SOURCE,
    _analyze_archive,
    _archive_from_local,
    _atomic_write_bytes,
    _gate_results,
)
from packages.backtesting.research_gate_freeze import RESEARCH_GATE_FREEZE_CONTRACT_VERSION
from packages.backtesting.research_population_coverage import (
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_13f_datasets import (
    SEC13FDatasetClient,
    SEC_13F_DATASET_MAX_RESPONSE_BYTES,
    SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES,
    SEC_13F_REQUIRED_TABLES,
)


SEC_13F_FEASIBILITY_V2_CONTRACT = (
    "alpha-gate-sec-13f-feasibility-v2-official-bulk-probe-only-no-market-outcomes"
)
SEC_13F_FEASIBILITY_V2_FINGERPRINT = (
    "4f41f7b1ca93bb76d559134d8ef74505ffd6a598e96676011ef515026d491696"
)
SEC_13F_FEASIBILITY_V2_SOURCE_MAIN_MERGE = "938747804e05357981faed79d696875cd7649f19"
SEC_13F_FEASIBILITY_V1_PREAUDIT_HEAD = "4f40b25d0a19d1485ef990e465ab064080c8cc06"

SEC_13F_FEASIBILITY_SCOPE = "PROBE_ONLY"
SEC_13F_CAPACITY_EVIDENCE_KIND = "BOUNDED_ANCHOR_PROBE"
SEC_13F_CAPACITY_EVIDENCE_COMPLETE = False
SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN = False
SEC_13F_SCIENTIFIC_FREEZE_ALLOWED = False
SEC_13F_PROSPECTIVE_RESEARCH_FREEZE_REQUIRED = True
SEC_13F_ALPHA_HYPOTHESES_FROZEN_V2 = False
SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY_V2 = False
SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED_V2 = False
SEC_13F_ORIGINAL_FILING_RECONCILIATION_REQUIRED_LATER_V2 = True
SEC_13F_TARGET_OUTCOME_READS_ALLOWED_V2 = False
SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED_V2 = False
SEC_13F_PROVIDER_READS_ALLOWED_V2 = True
SEC_13F_PROVIDER_WRITES_V2 = 0
SEC_13F_BROKER_READS_V2 = 0
SEC_13F_BROKER_WRITES_V2 = 0
SEC_13F_ORDER_WRITES_V2 = 0
SEC_13F_PAPER_SUBMITS_V2 = 0
SEC_13F_LIVE_WRITES_V2 = 0
SEC_13F_AUTOMATION_WRITES_V2 = 0
SEC_13F_AUTOMATIC_BROKER_FAILOVER_V2 = False
SEC_13F_PHASE33_SIGNAL_TO_TRADE_AUTHORITY_V2 = False

SEC_13F_RAW_RELATIVE_V2 = Path("regulatory/sec/form13f/feasibility_v2")
SEC_13F_REPORT_RELATIVE_V2 = Path(
    "strategy_evaluation/pre_phase33/sec_13f_feasibility_v2/source_census.json"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload_v2() -> dict[str, object]:
    return {
        "contract_version": SEC_13F_FEASIBILITY_V2_CONTRACT,
        "source_main_merge": SEC_13F_FEASIBILITY_V2_SOURCE_MAIN_MERGE,
        "preaudit_v1_head": SEC_13F_FEASIBILITY_V1_PREAUDIT_HEAD,
        "mechanism_candidate": SEC_13F_MECHANISM_CANDIDATE,
        "source": SEC_13F_SOURCE,
        "anchors": [{"label": label, "url": url} for label, url in SEC_13F_ANCHORS],
        "required_tables": list(SEC_13F_REQUIRED_TABLES),
        "allowed_submission_types": list(SEC_13F_ALLOWED_SUBMISSION_TYPES),
        "min_initial_hr_submissions_per_anchor": SEC_13F_MIN_INITIAL_HR_SUBMISSIONS_PER_ANCHOR,
        "min_initial_hr_infotable_rows_per_anchor": SEC_13F_MIN_INITIAL_HR_INFOTABLE_ROWS_PER_ANCHOR,
        "min_unique_initial_hr_managers_per_anchor": SEC_13F_MIN_UNIQUE_INITIAL_HR_MANAGERS_PER_ANCHOR,
        "min_valid_initial_hr_cusip_fraction": SEC_13F_MIN_VALID_INITIAL_HR_CUSIP_FRACTION,
        "max_submission_accession_duplicates": SEC_13F_MAX_SUBMISSION_ACCESSION_DUPLICATES,
        "max_infotable_primary_key_duplicates": SEC_13F_MAX_INFOTABLE_PRIMARY_KEY_DUPLICATES,
        "max_infotable_orphan_rows": SEC_13F_MAX_INFOTABLE_ORPHAN_ROWS,
        "max_initial_hr_filing_before_period_violations": SEC_13F_MAX_INITIAL_HR_FILING_BEFORE_PERIOD_VIOLATIONS,
        "min_calendar_year_span_inclusive": SEC_13F_MIN_CALENDAR_YEAR_SPAN_INCLUSIVE,
        "max_compressed_bytes_per_anchor": SEC_13F_DATASET_MAX_RESPONSE_BYTES,
        "max_uncompressed_bytes_per_anchor": SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES,
        "protected_source_cutoff": SEC_13F_PROTECTED_SOURCE_CUTOFF.isoformat(),
        "feasibility_scope": SEC_13F_FEASIBILITY_SCOPE,
        "capacity_evidence_kind": SEC_13F_CAPACITY_EVIDENCE_KIND,
        "capacity_evidence_complete": SEC_13F_CAPACITY_EVIDENCE_COMPLETE,
        "complete_source_scope_proven": SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN,
        "scientific_freeze_allowed": SEC_13F_SCIENTIFIC_FREEZE_ALLOWED,
        "prospective_research_freeze_required": SEC_13F_PROSPECTIVE_RESEARCH_FREEZE_REQUIRED,
        "research_gate_freeze_contract": RESEARCH_GATE_FREEZE_CONTRACT_VERSION,
        "alpha_hypotheses_frozen": SEC_13F_ALPHA_HYPOTHESES_FROZEN_V2,
        "cusip_to_atlas_identity_authority": SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY_V2,
        "full_history_acquisition_allowed": SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED_V2,
        "original_filing_reconciliation_required_later": SEC_13F_ORIGINAL_FILING_RECONCILIATION_REQUIRED_LATER_V2,
        "target_outcome_reads_allowed": SEC_13F_TARGET_OUTCOME_READS_ALLOWED_V2,
        "protected_outcome_reads_allowed": SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED_V2,
        "provider_reads_allowed": SEC_13F_PROVIDER_READS_ALLOWED_V2,
        "provider_writes": SEC_13F_PROVIDER_WRITES_V2,
        "broker_reads": SEC_13F_BROKER_READS_V2,
        "broker_writes": SEC_13F_BROKER_WRITES_V2,
        "order_writes": SEC_13F_ORDER_WRITES_V2,
        "paper_submits": SEC_13F_PAPER_SUBMITS_V2,
        "live_writes": SEC_13F_LIVE_WRITES_V2,
        "automation_writes": SEC_13F_AUTOMATION_WRITES_V2,
        "automatic_broker_failover": SEC_13F_AUTOMATIC_BROKER_FAILOVER_V2,
        "phase33_signal_to_trade_authority": SEC_13F_PHASE33_SIGNAL_TO_TRADE_AUTHORITY_V2,
    }


def sec_13f_feasibility_v2_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload_v2()).encode("utf-8")).hexdigest()


def sec_13f_probe_population_coverage(anchors: list[dict[str, Any]]) -> dict[str, object]:
    aggregate_rows = sum(int(anchor.get("initial_hr_infotable_rows") or 0) for anchor in anchors)
    assessment = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="frozen_four_anchor_sec_13f_probe",
                rows=aggregate_rows,
                scope=PopulationScope.PROBE_ONLY,
                complete_scope=False,
                comparable_to_previous=True,
                grain="sec_13f_original_hr_holding_row",
                source=SEC_13F_SOURCE,
            ),
        )
    )
    return assessment.to_dict()


class SEC13FFeasibilityV2:
    """Audit-aligned bounded structural probe of official SEC Form 13F bulk data."""

    def __init__(self, settings: AtlasSettings, sec_client: SEC13FDatasetClient, *, progress: Callable[[str], None] | None = None) -> None:
        self.settings = settings
        self.sec_client = sec_client
        self.progress = progress or (lambda _message: None)

    def _existing_report(self, report_path: Path, raw_root: Path) -> dict[str, Any] | None:
        if not report_path.is_file():
            return None
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("contract_version") != SEC_13F_FEASIBILITY_V2_CONTRACT:
            raise SEC13FFeasibilityError("existing SEC 13F v2 report contract drifted")
        if report.get("policy_fingerprint") != SEC_13F_FEASIBILITY_V2_FINGERPRINT:
            raise SEC13FFeasibilityError("existing SEC 13F v2 report fingerprint drifted")
        for anchor in report.get("anchors", []):
            if not isinstance(anchor, dict):
                raise SEC13FFeasibilityError("existing SEC 13F v2 anchor is malformed")
            url = str(anchor.get("source_url") or "")
            filename = SEC13FDatasetClient.validate_url(url)
            path = raw_root / filename
            if not path.is_file():
                raise SEC13FFeasibilityError(f"accepted SEC 13F v2 raw anchor is missing; do not silently refetch: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != anchor.get("source_sha256"):
                raise SEC13FFeasibilityError(f"accepted SEC 13F v2 raw anchor hash changed: {path}")
        return report

    def run(self) -> dict[str, Any]:
        if sec_13f_feasibility_v2_fingerprint() != SEC_13F_FEASIBILITY_V2_FINGERPRINT:
            raise SEC13FFeasibilityError("frozen SEC 13F v2 feasibility fingerprint drifted")
        canonical_root = self.settings.resolved_path(self.settings.data.paths.canonical)
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        raw_root = canonical_root / SEC_13F_RAW_RELATIVE_V2
        report_path = derived_root / SEC_13F_REPORT_RELATIVE_V2
        existing = self._existing_report(report_path, raw_root)
        if existing is not None:
            self.progress("SEC 13F v2 bounded-probe evidence already exists and is hash-valid; returning immutable report.")
            return existing
        raw_root.mkdir(parents=True, exist_ok=True)
        anchors: list[dict[str, Any]] = []
        provider_reads = 0
        local_source_files_created = 0
        for index, (label, url) in enumerate(SEC_13F_ANCHORS, start=1):
            filename = SEC13FDatasetClient.validate_url(url)
            path = raw_root / filename
            self.progress(f"SEC 13F v2 bounded anchor {index}/{len(SEC_13F_ANCHORS)}: {label}")
            if path.is_file():
                archive = _archive_from_local(path, url)
                source_mode = "LOCAL_IMMUTABLE_SOURCE"
            else:
                archive = self.sec_client.fetch(url)
                provider_reads += 1
                _atomic_write_bytes(path, archive.raw_bytes)
                local_source_files_created += 1
                source_mode = "OFFICIAL_SEC_FETCH_PERSISTED_IMMUTABLY"
            report = _analyze_archive(label, archive)
            report["source_mode"] = source_mode
            report["local_path"] = str(path)
            anchors.append(report)
            self.progress(f"  {label}: submissions={report['initial_hr_submissions']} holdings={report['initial_hr_infotable_rows']} valid_cusip={report['initial_hr_valid_cusip_fraction']:.6f}")
        structural_gates = _gate_results(anchors)
        period_years = sorted({int(year) for anchor in anchors for year in anchor.get("initial_hr_period_years", [])})
        population_coverage = sec_13f_probe_population_coverage(anchors)
        structural_pass = all(structural_gates.values())
        result = {
            "contract_version": SEC_13F_FEASIBILITY_V2_CONTRACT,
            "policy_fingerprint": SEC_13F_FEASIBILITY_V2_FINGERPRINT,
            "source_main_merge": SEC_13F_FEASIBILITY_V2_SOURCE_MAIN_MERGE,
            "preaudit_v1_head": SEC_13F_FEASIBILITY_V1_PREAUDIT_HEAD,
            "mechanism_candidate": SEC_13F_MECHANISM_CANDIDATE,
            "source": SEC_13F_SOURCE,
            "status": "PROBE_FEASIBILITY_PASS" if structural_pass else "PROBE_FEASIBILITY_FAIL",
            "pass": structural_pass,
            "feasibility_scope": SEC_13F_FEASIBILITY_SCOPE,
            "capacity_evidence_kind": SEC_13F_CAPACITY_EVIDENCE_KIND,
            "capacity_evidence_complete": SEC_13F_CAPACITY_EVIDENCE_COMPLETE,
            "complete_source_scope_proven": SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN,
            "scientific_freeze_allowed": SEC_13F_SCIENTIFIC_FREEZE_ALLOWED,
            "anchors": anchors,
            "calendar_years_observed": period_years,
            "calendar_year_span_inclusive": period_years[-1] - period_years[0] + 1 if period_years else 0,
            "structural_gates": structural_gates,
            "population_coverage": population_coverage,
            "prospective_research_freeze": {
                "required": SEC_13F_PROSPECTIVE_RESEARCH_FREEZE_REQUIRED,
                "contract_version": RESEARCH_GATE_FREEZE_CONTRACT_VERSION,
                "assessment_performed": False,
                "reason": "A scientific freeze is not yet eligible: complete 13F source scope, PIT CUSIP-to-instrument identity, candidate hypotheses, sample/effective-sample rationale, costs, effect-size target, multiplicity arithmetic, and positive-path power calibration remain prospective prerequisites.",
            },
            "governance": {
                "alpha_hypotheses_frozen": SEC_13F_ALPHA_HYPOTHESES_FROZEN_V2,
                "cusip_to_atlas_identity_authority": SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY_V2,
                "full_history_acquisition_allowed": SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED_V2,
                "original_filing_reconciliation_required_later": SEC_13F_ORIGINAL_FILING_RECONCILIATION_REQUIRED_LATER_V2,
                "target_outcome_rows_read": 0,
                "protected_return_rows_read": 0,
                "protected_holdout_consumed": False,
                "provider_reads_performed": provider_reads,
                "provider_writes_performed": SEC_13F_PROVIDER_WRITES_V2,
                "local_source_files_created": local_source_files_created,
                "broker_reads_performed": SEC_13F_BROKER_READS_V2,
                "broker_writes_performed": SEC_13F_BROKER_WRITES_V2,
                "order_writes_performed": SEC_13F_ORDER_WRITES_V2,
                "paper_submits_performed": SEC_13F_PAPER_SUBMITS_V2,
                "live_writes_performed": SEC_13F_LIVE_WRITES_V2,
                "automation_writes_performed": SEC_13F_AUTOMATION_WRITES_V2,
                "automatic_broker_failover": SEC_13F_AUTOMATIC_BROKER_FAILOVER_V2,
                "phase33_signal_to_trade_authority": SEC_13F_PHASE33_SIGNAL_TO_TRADE_AUTHORITY_V2,
            },
            "next_scientific_action": "IF_PROBE_PASS_COMPLETE_SOURCE_CAPACITY_CENSUS_THEN_PIT_IDENTITY_AND_EDGAR_RECONCILIATION_THEN_POPULATION_FUNNEL_AND_POWER_CALIBRATION_BEFORE_SCIENCE_FREEZE",
        }
        atomic_write_text(report_path, json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return result
