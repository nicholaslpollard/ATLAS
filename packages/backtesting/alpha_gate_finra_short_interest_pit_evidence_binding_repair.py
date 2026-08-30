from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from packages.backtesting.alpha_gate_finra_short_interest_pit_audit import (
    FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES,
    FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT,
    FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT,
    FINRA_SHORT_INTEREST_REPORT_RELATIVE_PIT,
)
from packages.backtesting.alpha_gate_finra_short_interest_predictor import (
    FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE,
    FINRAShortInterestPredictorBuilder,
    FINRAShortInterestPredictorError,
)
from packages.core.atomic_io import atomic_write_text
from packages.features.partition_store import sha256_file


FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_CONTRACT = (
    "alpha-gate-finra-short-interest-pit-evidence-binding-repair-v1-"
    "semantic-pass-evidence-no-market-outcomes"
)
FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256 = (
    "4fb3abc3e561fd4187efbf60967127230f14d37204d21b5ccb910c40a4469845"
)
FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT = (
    "12491a2008d6d629e55d395ad3228ea069e538254a64b03d9046e9cc5ebe169a"
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def pit_evidence_binding_payload(report: dict[str, Any]) -> dict[str, Any]:
    parent = report.get("accepted_feasibility_report")
    parent = parent if isinstance(parent, dict) else {}
    file_reports = report.get("file_reports")
    file_reports = file_reports if isinstance(file_reports, list) else []
    return {
        "repair_contract": FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_CONTRACT,
        "pit_audit_contract": report.get("contract_version"),
        "pit_audit_fingerprint": report.get("pit_audit_fingerprint"),
        "pit_status": report.get("status"),
        "pit_pass": report.get("pass"),
        "parent_feasibility_report_sha256": parent.get("sha256"),
        "accepted_counts": {
            "immutable_exchange_listed_rows": report.get("immutable_exchange_listed_rows"),
            "pit_eligible_rows": report.get("pit_eligible_rows"),
            "unique_pit_instruments": report.get("unique_pit_instruments"),
            "files_with_2500_pit_rows": report.get("files_with_2500_pit_rows"),
            "finra_source_files_read": report.get("finra_source_files_read"),
            "massive_reference_snapshots_read": report.get("massive_reference_snapshots_read"),
        },
        "status_counts": report.get("status_counts"),
        "gates": report.get("gates"),
        "source_dates": [item.get("settlement_date") for item in file_reports if isinstance(item, dict)],
        "authority": {
            "alpha_hypotheses_frozen": report.get("alpha_hypotheses_frozen"),
            "performance_evaluated": report.get("performance_evaluated"),
            "target_outcome_rows_read": report.get("target_outcome_rows_read"),
            "protected_return_rows_read": report.get("protected_return_rows_read"),
            "protected_holdout_consumed": report.get("protected_holdout_consumed"),
            "provider_writes_performed": report.get("provider_writes_performed"),
            "broker_reads_performed": report.get("broker_reads_performed"),
            "broker_writes_performed": report.get("broker_writes_performed"),
            "order_writes_performed": report.get("order_writes_performed"),
            "paper_submits_performed": report.get("paper_submits_performed"),
            "live_writes_performed": report.get("live_writes_performed"),
            "automation_writes_performed": report.get("automation_writes_performed"),
            "automatic_broker_failover": report.get("automatic_broker_failover"),
        },
    }


def pit_evidence_binding_fingerprint(report: dict[str, Any]) -> str:
    payload = pit_evidence_binding_payload(report)
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def validate_accepted_pit_evidence(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise FINRAShortInterestPredictorError(
            f"accepted PIT audit report is missing: {path}"
        )
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise FINRAShortInterestPredictorError(
            "accepted PIT audit report is not valid UTF-8 JSON"
        ) from exc
    if not isinstance(report, dict):
        raise FINRAShortInterestPredictorError("accepted PIT audit report is not an object")
    if report.get("contract_version") != FINRA_SHORT_INTEREST_PIT_AUDIT_CONTRACT:
        raise FINRAShortInterestPredictorError("accepted PIT audit contract drifted")
    if report.get("pit_audit_fingerprint") != FINRA_SHORT_INTEREST_PIT_AUDIT_FINGERPRINT:
        raise FINRAShortInterestPredictorError("accepted PIT audit fingerprint drifted")
    if report.get("status") != "PIT_AUDIT_PASS" or report.get("pass") is not True:
        raise FINRAShortInterestPredictorError("accepted PIT audit is not PASS")
    if report.get("failures") != []:
        raise FINRAShortInterestPredictorError("accepted PIT audit contains failures")

    file_reports = report.get("file_reports")
    if not isinstance(file_reports, list) or len(file_reports) != len(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES):
        raise FINRAShortInterestPredictorError("accepted PIT audit source-file cardinality drifted")
    source_dates = tuple(
        str(item.get("settlement_date"))
        for item in file_reports
        if isinstance(item, dict)
    )
    if source_dates != tuple(FINRA_SHORT_INTEREST_FROZEN_SETTLEMENT_DATES):
        raise FINRAShortInterestPredictorError("accepted PIT audit settlement dates drifted")
    for item in file_reports:
        if not isinstance(item, dict):
            raise FINRAShortInterestPredictorError("accepted PIT audit file report is malformed")
        source_sha = str(item.get("source_sha256") or "")
        if len(source_sha) != 64 or any(ch not in "0123456789abcdef" for ch in source_sha.lower()):
            raise FINRAShortInterestPredictorError("accepted PIT audit source hash is malformed")

    parent = report.get("accepted_feasibility_report")
    if not isinstance(parent, dict) or parent.get("sha256") != FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256:
        raise FINRAShortInterestPredictorError(
            "accepted feasibility report SHA-256 drifted inside PIT evidence"
        )

    observed_binding = pit_evidence_binding_fingerprint(report)
    if observed_binding != FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_FINGERPRINT:
        raise FINRAShortInterestPredictorError(
            "accepted PIT semantic evidence binding drifted"
        )

    return {
        "path": str(path),
        "report_sha256": sha256_file(path),
        "binding_fingerprint": observed_binding,
    }


class FINRAShortInterestPredictorEvidenceBindingRepair(FINRAShortInterestPredictorBuilder):
    """Narrow repair for the development runner's PIT evidence-binding defect."""

    def _validate_pit_evidence(self) -> str:
        path = self.derived_root / FINRA_SHORT_INTEREST_REPORT_RELATIVE_PIT
        evidence = validate_accepted_pit_evidence(path)
        self._accepted_pit_evidence = evidence
        return evidence["path"]

    def run(self) -> dict[str, Any]:
        report = super().run()
        evidence = getattr(self, "_accepted_pit_evidence", None)
        if not isinstance(evidence, dict):
            raise FINRAShortInterestPredictorError(
                "PIT evidence repair metadata was not established"
            )
        report["accepted_pit_audit_report_sha256"] = evidence["report_sha256"]
        report["accepted_feasibility_report_sha256"] = (
            FINRA_SHORT_INTEREST_ACCEPTED_FEASIBILITY_REPORT_SHA256
        )
        report["pit_evidence_binding_repair_contract"] = (
            FINRA_SHORT_INTEREST_PIT_EVIDENCE_BINDING_REPAIR_CONTRACT
        )
        report["pit_evidence_binding_repair_fingerprint"] = evidence[
            "binding_fingerprint"
        ]
        report_path = self.derived_root / FINRA_SHORT_INTEREST_PREDICTOR_REPORT_RELATIVE
        atomic_write_text(
            report_path, json.dumps(report, indent=2, sort_keys=True) + "\n"
        )
        return report
