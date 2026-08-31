from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_REPORT_RELATIVE,
    _canonical_json,
    _direct_rows,
    _parent_report_exact,
    _submission_metadata_for_targets,
)
from packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility import (
    EARNINGS_INNOVATION_REPORT_RELATIVE,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_edgar import SECEDGARClient
from packages.providers.sec_xbrl import SECXBRLCompanyFactsClient


EARNINGS_INNOVATION_PIT_DIAGNOSTIC_CONTRACT = (
    "alpha-gate-sec-earnings-innovation-pit-audit-diagnostics-v1-source-only-no-market-outcomes"
)
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_FINGERPRINT = (
    "745c11fd29f752980404b128ec26d081e3e4df16342f0f6c66e32d201bcb52dd"
)
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_PURPOSE = (
    "IDENTIFY_EXACT_PERIOD_CONTEXT_AMBIGUITIES_AND_ACCESSION_METADATA_CONTRADICTIONS_ONLY"
)
EARNINGS_INNOVATION_PIT_FAILED_REPORT_SHA256 = (
    "3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a"
)
EARNINGS_INNOVATION_PIT_FAILED_EXPECTED = {
    "status": "PIT_AUDIT_FAIL",
    "original_accession_candidate_observations": 5902,
    "period_context_ambiguities": 3,
    "accession_metadata_contradictions": 6,
    "audited_observations": 5896,
    "target_outcome_rows_read": 0,
    "protected_return_rows_read": 0,
    "protected_holdout_consumed": False,
}
EARNINGS_INNOVATION_PIT_DIAGNOSTIC_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v1_diagnostics/source_diagnostics.json"
)


class EarningsInnovationPITDiagnosticError(RuntimeError):
    pass


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_CONTRACT,
        "parent_pit_audit_contract": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
        "parent_pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
        "purpose": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_PURPOSE,
        "gate_changes": False,
        "market_outcomes_allowed": False,
        "protected_outcomes_allowed": False,
    }


def earnings_innovation_pit_diagnostic_fingerprint() -> str:
    return hashlib.sha256(
        json.dumps(
            _fingerprint_payload(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()


def _load_json_with_sha(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise EarningsInnovationPITDiagnosticError(f"required local evidence is missing: {path}")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarningsInnovationPITDiagnosticError(f"local evidence is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EarningsInnovationPITDiagnosticError(f"local evidence root is not an object: {path}")
    return value, digest


def _verify_failed_audit(report: dict[str, Any], digest: str) -> None:
    if digest != EARNINGS_INNOVATION_PIT_FAILED_REPORT_SHA256:
        raise EarningsInnovationPITDiagnosticError(
            "original PIT_AUDIT_FAIL report hash changed; preserve the first failed audit before diagnosis"
        )
    if report.get("contract_version") != EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT:
        raise EarningsInnovationPITDiagnosticError("failed audit contract does not match frozen v1 contract")
    if report.get("pit_audit_fingerprint") != EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT:
        raise EarningsInnovationPITDiagnosticError("failed audit fingerprint does not match frozen v1 audit")
    for key, expected in EARNINGS_INNOVATION_PIT_FAILED_EXPECTED.items():
        if report.get(key) != expected:
            raise EarningsInnovationPITDiagnosticError(
                f"failed audit evidence drifted for {key}: {report.get(key)!r} != {expected!r}"
            )


def _select_with_diagnostics(
    cik: str, rows: Iterable[dict[str, Any]]
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("end") or "")].append(dict(row))

    selected: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for period_end, values in sorted(grouped.items()):
        if not period_end:
            diagnostics.append(
                {
                    "issuer_cik": cik,
                    "period_end": period_end,
                    "reason": "MISSING_PERIOD_END",
                    "candidate_rows": sorted(values, key=_canonical_json),
                }
            )
            continue
        ordered = sorted(values, key=lambda r: (str(r.get("filed") or ""), str(r.get("accn") or "")))
        first_key = (str(ordered[0].get("filed") or ""), str(ordered[0].get("accn") or ""))
        earliest = [
            row
            for row in ordered
            if (str(row.get("filed") or ""), str(row.get("accn") or "")) == first_key
        ]
        semantics = {
            (str(row.get("start") or ""), str(row.get("end") or ""), row.get("val"))
            for row in earliest
        }
        if len(semantics) != 1 or any(item[2] is None for item in semantics):
            diagnostics.append(
                {
                    "issuer_cik": cik,
                    "period_end": period_end,
                    "reason": "AMBIGUOUS_EARLIEST_PERIOD_CONTEXT",
                    "earliest_filed": first_key[0],
                    "earliest_accession": first_key[1],
                    "earliest_semantics": [list(item) for item in sorted(semantics, key=str)],
                    "earliest_rows": sorted(earliest, key=_canonical_json),
                    "all_period_rows": sorted(values, key=_canonical_json),
                }
            )
            continue
        selected.append(sorted(earliest, key=_canonical_json)[0])
    return tuple(selected), tuple(diagnostics)


class SECEarningsInnovationPITDiagnostics:
    """Source-only diagnostic replay of the failed PIT audit; never changes frozen gates."""

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
            earnings_innovation_pit_diagnostic_fingerprint()
            != EARNINGS_INNOVATION_PIT_DIAGNOSTIC_FINGERPRINT
        ):
            raise EarningsInnovationPITDiagnosticError("frozen PIT diagnostic fingerprint drifted")

        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        failed_path = derived_root / EARNINGS_INNOVATION_PIT_REPORT_RELATIVE
        failed_report, failed_sha256 = _load_json_with_sha(failed_path)
        _verify_failed_audit(failed_report, failed_sha256)

        feasibility_path = derived_root / EARNINGS_INNOVATION_REPORT_RELATIVE
        feasibility_report, _ = _load_json_with_sha(feasibility_path)
        if not _parent_report_exact(feasibility_report):
            raise EarningsInnovationPITDiagnosticError(
                "accepted feasibility parent no longer matches frozen Gate0 evidence"
            )

        sample_ciks = tuple(str(value) for value in feasibility_report["sample_ciks"])
        expected_hashes = {
            str(row.get("issuer_cik")): str(row.get("source_sha256"))
            for row in feasibility_report.get("issuer_reports", [])
            if isinstance(row, dict)
        }

        candidate_by_cik: dict[str, tuple[dict[str, Any], ...]] = {}
        period_diagnostics: list[dict[str, Any]] = []
        companyfacts_hash_matches = 0
        companyfacts_failures: list[dict[str, str]] = []

        for index, cik in enumerate(sample_ciks, start=1):
            try:
                document = self.companyfacts_client.company_facts(cik=cik)
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
                    "SEC earnings-innovation PIT diagnostics parent progress: "
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
                    self.submissions_client, cik=cik, targets=targets
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
                    "SEC earnings-innovation PIT diagnostics chronology progress: "
                    f"{index}/{len(sample_ciks)} roots={submissions_root_success} "
                    f"contradictions={len(metadata_diagnostics)} missing={len(missing_metadata)}"
                )

        report_path = derived_root / EARNINGS_INNOVATION_PIT_DIAGNOSTIC_REPORT_RELATIVE
        report = {
            "contract_version": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_CONTRACT,
            "diagnostic_fingerprint": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_FINGERPRINT,
            "purpose": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_PURPOSE,
            "parent_pit_audit_contract": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
            "parent_pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
            "preserved_failed_report_path": str(failed_path),
            "preserved_failed_report_sha256": failed_sha256,
            "preserved_failed_report_verified": True,
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
            "diagnostic_complete": (
                companyfacts_hash_matches == len(sample_ciks)
                and not companyfacts_failures
                and submissions_root_success == len(sample_ciks)
                and not submissions_failures
                and len(period_diagnostics)
                == EARNINGS_INNOVATION_PIT_FAILED_EXPECTED["period_context_ambiguities"]
                and len(metadata_diagnostics)
                == EARNINGS_INNOVATION_PIT_FAILED_EXPECTED[
                    "accession_metadata_contradictions"
                ]
                and not missing_metadata
            ),
            "report_path": str(report_path),
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
