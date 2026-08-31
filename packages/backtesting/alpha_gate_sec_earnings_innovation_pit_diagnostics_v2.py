from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility import (
    EARNINGS_INNOVATION_REPORT_RELATIVE,
)
from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_REPORT_RELATIVE,
    _direct_rows,
    _parent_report_exact,
    _submission_metadata_for_targets,
)
from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_diagnostics import (
    _load_json_with_sha,
    _select_with_diagnostics,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_edgar import SECEDGARClient
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient


EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT = (
    "alpha-gate-sec-earnings-innovation-pit-audit-diagnostics-v2-source-only-no-market-outcomes"
)
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT = (
    "399e7d0bece8088e63c4835566d276b51375a5031d81f4db4781675351a87961"
)
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_PURPOSE = (
    "IDENTIFY_EXACT_PERIOD_CONTEXT_AMBIGUITIES_AND_ACCESSION_METADATA_CONTRADICTIONS_ONLY"
)
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_GUARD = (
    "STRUCTURAL_EXACT_FAILED_AUDIT_PLUS_PARENT_REPORT_SHA256"
)
EARNINGS_INNOVATION_FEASIBILITY_PARENT_REPORT_SHA256 = (
    "3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a"
)
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v2_diagnostics/source_diagnostics.json"
)

_FAILED_GATES = {
    "parent_report_exact": True,
    "parent_sample_exact": True,
    "companyfacts_hash_matches_min": True,
    "parent_semantics_reconciled": True,
    "submissions_root_success_min": True,
    "audited_observations_min": True,
    "audited_history_ready_issuers_min": True,
    "audited_sue_baseline_ready_issuers_min": True,
    "acceptance_proven_fraction_min": True,
    "calendar_years_observed_min": True,
    "period_context_ambiguities_max": False,
    "accession_metadata_contradictions_max": False,
    "acceptance_not_after_period_end_max": True,
    "decision_session_errors_max": True,
}

_FAILED_EXACT = {
    "status": "PIT_AUDIT_FAIL",
    "pass": False,
    "parent_report_sha256": EARNINGS_INNOVATION_FEASIBILITY_PARENT_REPORT_SHA256,
    "companyfacts_hash_matches": 300,
    "companyfacts_failures": [],
    "parent_semantics_reconciled": True,
    "recomputed_direct_quarter_observations": 5905,
    "recomputed_history_ready_issuers": 204,
    "recomputed_sue_baseline_ready_issuers": 170,
    "original_accession_candidate_observations": 5902,
    "period_context_ambiguities": 3,
    "submissions_root_success": 300,
    "submissions_root_failures": [],
    "submissions_shard_reads": 23,
    "missing_accession_metadata": 0,
    "accession_metadata_contradictions": 6,
    "acceptance_not_after_period_end": 0,
    "decision_session_errors": 0,
    "audited_observations": 5896,
    "audited_history_ready_issuers": 204,
    "audited_sue_baseline_ready_issuers": 170,
    "calendar_years_observed": list(range(2013, 2027)),
    "target_outcome_rows_read": 0,
    "protected_return_rows_read": 0,
    "protected_holdout_consumed": False,
    "provider_reads_performed": 623,
    "provider_writes_performed": 0,
    "broker_reads_performed": 0,
    "broker_writes_performed": 0,
    "order_writes_performed": 0,
    "paper_submits_performed": 0,
    "live_writes_performed": 0,
    "automation_writes_performed": 0,
    "phase33_signal_to_trade_authority": False,
}


class EarningsInnovationPITDiagnosticV2Error(RuntimeError):
    pass


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT,
        "parent_pit_audit_contract": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
        "parent_pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
        "purpose": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_PURPOSE,
        "failed_audit_guard": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_GUARD,
        "gate_changes": False,
        "market_outcomes_allowed": False,
        "protected_outcomes_allowed": False,
    }


def earnings_innovation_pit_diagnostic_v2_fingerprint() -> str:
    payload = json.dumps(
        _fingerprint_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _verify_failed_audit(report: dict[str, Any]) -> None:
    if report.get("contract_version") != EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT:
        raise EarningsInnovationPITDiagnosticV2Error(
            "failed audit contract does not match frozen v1 PIT audit"
        )
    if report.get("pit_audit_fingerprint") != EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT:
        raise EarningsInnovationPITDiagnosticV2Error(
            "failed audit fingerprint does not match frozen v1 PIT audit"
        )
    for key, expected in _FAILED_EXACT.items():
        if report.get(key) != expected:
            raise EarningsInnovationPITDiagnosticV2Error(
                f"failed audit evidence drifted for {key}: {report.get(key)!r} != {expected!r}"
            )
    if report.get("gates") != _FAILED_GATES:
        raise EarningsInnovationPITDiagnosticV2Error(
            "failed audit gate vector no longer matches the first observed PIT_AUDIT_FAIL"
        )

    fraction = report.get("acceptance_proven_fraction")
    expected_fraction = 5896 / 5902
    if not isinstance(fraction, (int, float)) or abs(float(fraction) - expected_fraction) > 1e-15:
        raise EarningsInnovationPITDiagnosticV2Error(
            "failed audit acceptance-proven fraction no longer matches 5896/5902"
        )


def _diagnostic_replay(
    *,
    sample_ciks: tuple[str, ...],
    expected_hashes: dict[str, str],
    companyfacts_client: SECXBRLCompanyFactsClient,
    submissions_client: SECEDGARClient,
) -> dict[str, Any]:
    candidate_by_cik: dict[str, tuple[dict[str, Any], ...]] = {}
    period_diagnostics: list[dict[str, Any]] = []
    companyfacts_hash_matches = 0
    companyfacts_failures: list[dict[str, str]] = []

    for index, cik in enumerate(sample_ciks, start=1):
        try:
            document = companyfacts_client.company_facts(cik=cik)
            if document.source_sha256 == expected_hashes.get(cik):
                companyfacts_hash_matches += 1
            selected, details = _select_with_diagnostics(cik, _direct_rows(document))
            candidate_by_cik[cik] = selected
            period_diagnostics.extend(details)
        except Exception as exc:
            companyfacts_failures.append(
                {"issuer_cik": cik, "error_type": type(exc).__name__, "error": str(exc)}
            )
            candidate_by_cik[cik] = ()
        if index == 1 or index % 25 == 0 or index == len(sample_ciks):
            print(
                "SEC earnings-innovation PIT diagnostics V2 parent progress: "
                f"{index}/{len(sample_ciks)} hash_matches={companyfacts_hash_matches} "
                f"period_diagnostics={len(period_diagnostics)} failures={len(companyfacts_failures)}"
            )

    metadata_diagnostics: list[dict[str, Any]] = []
    missing_metadata: list[dict[str, Any]] = []
    submissions_failures: list[dict[str, str]] = []
    submissions_root_success = 0
    submissions_shard_reads = 0

    for index, cik in enumerate(sample_ciks, start=1):
        targets = candidate_by_cik[cik]
        try:
            metadata, shard_reads = _submission_metadata_for_targets(
                submissions_client, cik=cik, targets=targets
            )
            submissions_root_success += 1
            submissions_shard_reads += shard_reads
        except Exception as exc:
            submissions_failures.append(
                {"issuer_cik": cik, "error_type": type(exc).__name__, "error": str(exc)}
            )
            metadata = {}

        for row in targets:
            accession = str(row.get("accn") or "")
            source = metadata.get(accession)
            if source is None:
                missing_metadata.append(
                    {
                        "issuer_cik": cik,
                        "accession_number": accession,
                        "companyfacts_row": row,
                    }
                )
                continue
            source_form = str(source.get("form") or "").strip()
            source_filed = str(source.get("filingDate") or "").strip()
            expected_form = str(row.get("form") or "").strip()
            expected_filed = str(row.get("filed") or "").strip()
            if source_form != expected_form or source_filed != expected_filed:
                metadata_diagnostics.append(
                    {
                        "issuer_cik": cik,
                        "accession_number": accession,
                        "companyfacts_form": expected_form,
                        "companyfacts_filed": expected_filed,
                        "submissions_form": source_form,
                        "submissions_filing_date": source_filed,
                        "companyfacts_row": row,
                        "submissions_row": source,
                    }
                )
        if index == 1 or index % 25 == 0 or index == len(sample_ciks):
            print(
                "SEC earnings-innovation PIT diagnostics V2 chronology progress: "
                f"{index}/{len(sample_ciks)} roots={submissions_root_success} "
                f"contradictions={len(metadata_diagnostics)} missing={len(missing_metadata)}"
            )

    return {
        "companyfacts_hash_matches": companyfacts_hash_matches,
        "companyfacts_failures": companyfacts_failures,
        "period_context_diagnostics": period_diagnostics,
        "period_context_diagnostic_count": len(period_diagnostics),
        "submissions_root_success": submissions_root_success,
        "submissions_shard_reads": submissions_shard_reads,
        "submissions_failures": submissions_failures,
        "missing_accession_metadata": missing_metadata,
        "missing_accession_metadata_count": len(missing_metadata),
        "accession_metadata_diagnostics": metadata_diagnostics,
        "accession_metadata_diagnostic_count": len(metadata_diagnostics),
    }


class SECEarningsInnovationPITDiagnosticsV2:
    """Corrected source-only replay of the first PIT audit failure."""

    def __init__(
        self,
        settings: AtlasSettings,
        companyfacts_client: SECXBRLCompanyFactsClient,
        submissions_client: SECEDGARClient,
    ) -> None:
        self.settings = settings
        self.companyfacts_client = companyfacts_client
        self.submissions_client = submissions_client

    def run(self) -> dict[str, Any]:
        if (
            earnings_innovation_pit_diagnostic_v2_fingerprint()
            != EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT
        ):
            raise EarningsInnovationPITDiagnosticV2Error(
                "frozen PIT diagnostic V2 fingerprint drifted"
            )

        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        failed_path = derived_root / EARNINGS_INNOVATION_PIT_REPORT_RELATIVE
        failed_report, failed_sha256 = _load_json_with_sha(failed_path)
        _verify_failed_audit(failed_report)

        feasibility_path = derived_root / EARNINGS_INNOVATION_REPORT_RELATIVE
        feasibility_report, feasibility_sha256 = _load_json_with_sha(feasibility_path)
        if feasibility_sha256 != EARNINGS_INNOVATION_FEASIBILITY_PARENT_REPORT_SHA256:
            raise EarningsInnovationPITDiagnosticV2Error(
                "accepted feasibility parent byte hash no longer matches the PIT failure lineage"
            )
        if not _parent_report_exact(feasibility_report):
            raise EarningsInnovationPITDiagnosticV2Error(
                "accepted feasibility parent no longer matches frozen Gate0 evidence"
            )

        sample_ciks = tuple(str(value) for value in feasibility_report["sample_ciks"])
        expected_hashes = {
            str(row.get("issuer_cik")): str(row.get("source_sha256"))
            for row in feasibility_report.get("issuer_reports", [])
            if isinstance(row, dict)
        }

        replay = _diagnostic_replay(
            sample_ciks=sample_ciks,
            expected_hashes=expected_hashes,
            companyfacts_client=self.companyfacts_client,
            submissions_client=self.submissions_client,
        )

        diagnostic_complete = (
            replay["companyfacts_hash_matches"] == len(sample_ciks)
            and not replay["companyfacts_failures"]
            and replay["submissions_root_success"] == len(sample_ciks)
            and not replay["submissions_failures"]
            and replay["period_context_diagnostic_count"] == 3
            and replay["accession_metadata_diagnostic_count"] == 6
            and replay["missing_accession_metadata_count"] == 0
        )

        report_path = derived_root / EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_REPORT_RELATIVE
        report = {
            "contract_version": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT,
            "diagnostic_fingerprint": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT,
            "purpose": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_PURPOSE,
            "failed_audit_guard": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_GUARD,
            "parent_pit_audit_contract": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
            "parent_pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
            "preserved_failed_report_path": str(failed_path),
            "preserved_failed_report_sha256": failed_sha256,
            "preserved_failed_report_verified": True,
            "feasibility_parent_report_sha256": feasibility_sha256,
            **replay,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "phase33_signal_to_trade_authority": False,
            "gate_changes": False,
            "diagnostic_complete": diagnostic_complete,
            "report_path": str(report_path),
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
