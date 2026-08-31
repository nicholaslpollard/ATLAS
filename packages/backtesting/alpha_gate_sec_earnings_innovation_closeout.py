from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_audit import (
    EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
    EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_REPORT_RELATIVE,
)
from packages.backtesting.alpha_gate_sec_earnings_innovation_pit_diagnostics_v2 import (
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT,
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT,
    EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_REPORT_RELATIVE,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings


EARNINGS_INNOVATION_CLOSEOUT_CONTRACT = (
    "alpha-gate-sec-earnings-innovation-closeout-v1-"
    "pit-source-integrity-failure-no-market-outcomes"
)
EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT = (
    "29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc"
)
EARNINGS_INNOVATION_SOURCE_DISPOSITION = "ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE"
EARNINGS_INNOVATION_ACCEPTED_FAILED_PIT_REPORT_SHA256 = (
    "ca5d5494b9c4be0158bd5d89c2f5b70aae0ba3a717a4af60f437bf4eaad37cea"
)
EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256 = (
    "3c299447e0ed8fd48d10c8cc792cf57396d87378cb21575e219b624c6a50566a"
)
EARNINGS_INNOVATION_CLOSEOUT_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_earnings_innovation_source_only_closeout_v1/closeout.json"
)

_EXPECTED_PERIOD_SIGNATURES = (
    (
        "0001728688",
        "2018-09-30",
        "0001728688-18-000027",
        (("2018-06-26", "2018-09-30", 0.08), ("2018-07-01", "2018-09-30", 0.09)),
    ),
    (
        "0001758488",
        "2019-06-30",
        "0001193125-19-222179",
        (("2019-03-21", "2019-06-30", -0.31), ("2019-04-01", "2019-06-30", 0.05)),
    ),
    (
        "0002028935",
        "2024-09-30",
        "0001213900-25-001637",
        (("2024-06-19", "2024-09-30", -0.02), ("2024-07-01", "2024-09-30", -0.02)),
    ),
)

_EXPECTED_METADATA_SIGNATURES = (
    ("0000036377", "0001558370-19-009110", "10-Q", "2019-10-25", "10-Q", "2019-10-24"),
    ("0000079282", "0001564590-20-034396", "10-Q", "2020-07-30", "10-Q", "2020-07-29"),
    ("0000319201", "0000319201-20-000047", "10-K", "2020-08-10", "10-K", "2020-08-07"),
    ("0000912093", "0000912093-16-000032", "10-Q", "2016-08-26", "10-Q/A", "2016-08-26"),
    ("0000912093", "0000912093-16-000032", "10-Q", "2016-08-26", "10-Q/A", "2016-08-26"),
    ("0001173313", "0001213900-17-005701", "10-Q", "2017-05-22", "10-Q/A", "2017-05-22"),
)


class EarningsInnovationCloseoutError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _load_json_with_sha(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise EarningsInnovationCloseoutError(f"required closeout evidence is missing: {path}")
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarningsInnovationCloseoutError(f"closeout evidence is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(value, dict):
        raise EarningsInnovationCloseoutError(f"closeout evidence root is not an object: {path}")
    return value, digest


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": EARNINGS_INNOVATION_CLOSEOUT_CONTRACT,
        "parent_pit_audit_contract": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
        "parent_pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
        "diagnostic_contract": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT,
        "diagnostic_fingerprint": EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT,
        "source_disposition": EARNINGS_INNOVATION_SOURCE_DISPOSITION,
        "failed_pit_report_sha256": EARNINGS_INNOVATION_ACCEPTED_FAILED_PIT_REPORT_SHA256,
        "feasibility_parent_report_sha256": EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256,
        "period_context_ambiguities": 3,
        "accession_metadata_contradictions": 6,
        "audited_observations": 5896,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
        "repair_allowed_under_v1": False,
    }


def earnings_innovation_closeout_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _period_signature(row: dict[str, Any]) -> tuple[object, ...]:
    semantics: list[tuple[str, str, float]] = []
    for item in row.get("earliest_semantics", []):
        if not isinstance(item, list) or len(item) != 3:
            raise EarningsInnovationCloseoutError("diagnostic period semantics are malformed")
        semantics.append((str(item[0]), str(item[1]), float(item[2])))
    return (
        str(row.get("issuer_cik") or ""),
        str(row.get("period_end") or ""),
        str(row.get("earliest_accession") or ""),
        tuple(sorted(semantics)),
    )


def _metadata_signature(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("issuer_cik") or ""),
        str(row.get("accession_number") or ""),
        str(row.get("companyfacts_form") or ""),
        str(row.get("companyfacts_filed") or ""),
        str(row.get("submissions_form") or ""),
        str(row.get("submissions_filing_date") or ""),
    )


def close_sec_earnings_innovation_source_only(settings: AtlasSettings) -> dict[str, Any]:
    """Close the frozen v1 family from persisted source-only evidence.

    No provider, market-price, benchmark, broker, order, PAPER, LIVE, or automation
    access is performed by this closeout.
    """
    if earnings_innovation_closeout_fingerprint() != EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT:
        raise EarningsInnovationCloseoutError("frozen earnings-innovation closeout fingerprint drifted")

    derived_root = settings.resolved_path(settings.data.paths.derived)
    failed_path = derived_root / EARNINGS_INNOVATION_PIT_REPORT_RELATIVE
    diagnostic_path = derived_root / EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_REPORT_RELATIVE
    failed, failed_sha256 = _load_json_with_sha(failed_path)
    diagnostic, diagnostic_sha256 = _load_json_with_sha(diagnostic_path)

    period_signatures = tuple(
        sorted(_period_signature(row) for row in diagnostic.get("period_context_diagnostics", []))
    )
    metadata_signatures = tuple(
        sorted(_metadata_signature(row) for row in diagnostic.get("accession_metadata_diagnostics", []))
    )

    gates = failed.get("gates") if isinstance(failed.get("gates"), dict) else {}
    checks = {
        "failed_pit_report_sha_exact": failed_sha256 == EARNINGS_INNOVATION_ACCEPTED_FAILED_PIT_REPORT_SHA256,
        "failed_pit_contract_exact": failed.get("contract_version") == EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
        "failed_pit_fingerprint_exact": failed.get("pit_audit_fingerprint") == EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
        "failed_pit_status_exact": failed.get("status") == "PIT_AUDIT_FAIL" and failed.get("pass") is False,
        "failed_pit_parent_sha_exact": failed.get("parent_report_sha256") == EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256,
        "failed_pit_counts_exact": (
            failed.get("original_accession_candidate_observations") == 5902
            and failed.get("period_context_ambiguities") == 3
            and failed.get("accession_metadata_contradictions") == 6
            and failed.get("audited_observations") == 5896
        ),
        "failed_pit_only_frozen_source_gates_failed": (
            gates.get("period_context_ambiguities_max") is False
            and gates.get("accession_metadata_contradictions_max") is False
            and all(
                value is True
                for key, value in gates.items()
                if key not in {"period_context_ambiguities_max", "accession_metadata_contradictions_max"}
            )
        ),
        "diagnostic_contract_exact": diagnostic.get("contract_version") == EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_CONTRACT,
        "diagnostic_fingerprint_exact": diagnostic.get("diagnostic_fingerprint") == EARNINGS_INNOVATION_PIT_DIAGNOSTIC_V2_FINGERPRINT,
        "diagnostic_complete": diagnostic.get("diagnostic_complete") is True,
        "diagnostic_failed_report_sha_exact": diagnostic.get("preserved_failed_report_sha256") == EARNINGS_INNOVATION_ACCEPTED_FAILED_PIT_REPORT_SHA256,
        "diagnostic_parent_sha_exact": diagnostic.get("feasibility_parent_report_sha256") == EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256,
        "diagnostic_source_counts_exact": (
            diagnostic.get("companyfacts_hash_matches") == 300
            and diagnostic.get("period_context_diagnostic_count") == 3
            and diagnostic.get("submissions_root_success") == 300
            and diagnostic.get("accession_metadata_diagnostic_count") == 6
            and diagnostic.get("missing_accession_metadata_count") == 0
        ),
        "period_diagnostics_exact": period_signatures == _EXPECTED_PERIOD_SIGNATURES,
        "metadata_diagnostics_exact": metadata_signatures == _EXPECTED_METADATA_SIGNATURES,
        "diagnostic_source_failures_empty": (
            diagnostic.get("companyfacts_failures") == []
            and diagnostic.get("submissions_failures") == []
            and diagnostic.get("missing_accession_metadata") == []
        ),
        "target_outcomes_unread": failed.get("target_outcome_rows_read") == 0 and diagnostic.get("target_outcome_rows_read") == 0,
        "protected_returns_unread": failed.get("protected_return_rows_read") == 0 and diagnostic.get("protected_return_rows_read") == 0,
        "protected_holdout_unconsumed": failed.get("protected_holdout_consumed") is False and diagnostic.get("protected_holdout_consumed") is False,
        "phase33_authority_false": failed.get("phase33_signal_to_trade_authority") is False and diagnostic.get("phase33_signal_to_trade_authority") is False,
    }
    if not all(checks.values()):
        failed_checks = sorted(name for name, passed in checks.items() if not passed)
        raise EarningsInnovationCloseoutError(
            "SEC earnings-innovation source-only closeout evidence failed: " + ", ".join(failed_checks)
        )

    report_path = derived_root / EARNINGS_INNOVATION_CLOSEOUT_REPORT_RELATIVE
    report = {
        "contract_version": EARNINGS_INNOVATION_CLOSEOUT_CONTRACT,
        "closeout_fingerprint": EARNINGS_INNOVATION_CLOSEOUT_FINGERPRINT,
        "status": "CLOSED",
        "disposition": "ACCEPTED_NEGATIVE",
        "source_disposition": EARNINGS_INNOVATION_SOURCE_DISPOSITION,
        "failed_pit_report_sha256": failed_sha256,
        "diagnostic_report_sha256": diagnostic_sha256,
        "feasibility_parent_report_sha256": EARNINGS_INNOVATION_ACCEPTED_FEASIBILITY_PARENT_SHA256,
        "period_context_ambiguities": 3,
        "accession_metadata_contradictions": 6,
        "audited_observations": 5896,
        "checks": checks,
        "repair_allowed_under_v1": False,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
        "provider_reads_performed": 0,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "automation_writes_performed": 0,
        "next_scientific_action": (
            "Preregister a materially different economic/information alpha mechanism. "
            "Do not reinterpret, prune, or relax the frozen SEC earnings-innovation v1 source rules after observing this failure."
        ),
        "report_path": str(report_path),
    }
    atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report
