from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from packages.backtesting.alpha_gate_beneficial_ownership_development import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_CONTRACT,
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_OUTCOMES_RELATIVE,
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_REPORT_RELATIVE,
    BENEFICIAL_OWNERSHIP_FINALIST_CONTRACT,
    BENEFICIAL_OWNERSHIP_FINALISTS_RELATIVE,
)
from packages.backtesting.alpha_gate_beneficial_ownership_predictor import (
    BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT,
    BENEFICIAL_OWNERSHIP_PREDICTOR_REPORT_RELATIVE,
    BENEFICIAL_OWNERSHIP_PREDICTOR_ROWS_RELATIVE,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
)
from packages.backtesting.alpha_gate_beneficial_ownership_transport_repair import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT,
)
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file


BENEFICIAL_OWNERSHIP_CLOSEOUT_CONTRACT = (
    "alpha-gate-beneficial-ownership-closeout-v1-development-negative-protected-unread"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_PROBE_CONTRACT = (
    "alpha-gate-beneficial-ownership-closeout-probe-v1-persisted-development-negative-no-provider-reads"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD = (
    "067dc13429c22dc4e789959f56644423f0947946"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_STATUS = "ACCEPTED_NEGATIVE_DEVELOPMENT"
BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT = (
    "c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_REPORT_SHA256 = (
    "3cfecc2841e71172d2f4575ec6e0ef4dfe3d08d36fd3a95c6237bffb33601e30"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_REPORT_SHA256 = (
    "28997b63b978d4ce44f9719b909075b6be38d50109633547db96881f84b2850b"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS_SHA256 = (
    "310c7b8edfd5324e57b888734febe9407decc4fb1f042c67a6de07d3a468a466"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256 = (
    "4c038c5f6578dc9ef946a3485b1584514dbc893b9da976522ed0373c0715b679"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_FINALISTS_SHA256 = (
    "d0cca3cbe1be332d010b7689b735244d40e760fa2f067e8c9fe1c47ce7b4fbca"
)
BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS = 3652
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS = 2763
BENEFICIAL_OWNERSHIP_ACCEPTED_PROTECTED_PREDICTOR_ROWS = 889
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS = 2412
BENEFICIAL_OWNERSHIP_ACCEPTED_MISSING_STOCK_PATH_ROWS = 306
BENEFICIAL_OWNERSHIP_ACCEPTED_SPLIT_CENSORED_ROWS = 46
BENEFICIAL_OWNERSHIP_ACCEPTED_PROVIDER_SOURCE_READS = 3133
BENEFICIAL_OWNERSHIP_ACCEPTED_STAGE_COUNTS = {"DEVELOPMENT": 2763, "PROTECTED": 889}
BENEFICIAL_OWNERSHIP_ACCEPTED_CANDIDATE_COUNTS = {
    "initial_13d_10_plus_long": 938,
    "initial_13d_5_to_10_long": 742,
    "initial_13g_10_plus_long": 272,
    "initial_13g_5_to_10_long": 1700,
}
BENEFICIAL_OWNERSHIP_ACCEPTED_SELECTION_START = "2021-08-16"
BENEFICIAL_OWNERSHIP_ACCEPTED_SELECTION_END = "2023-12-26"
BENEFICIAL_OWNERSHIP_ACCEPTED_INTERNAL_START = "2024-03-28"
BENEFICIAL_OWNERSHIP_ACCEPTED_INTERNAL_END = "2024-12-31"
BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_SESSION_COUNT = 850
BENEFICIAL_OWNERSHIP_ACCEPTED_SELECTION_SESSION_COUNT = 595
BENEFICIAL_OWNERSHIP_ACCEPTED_INTERNAL_SESSION_COUNT = 192
BENEFICIAL_OWNERSHIP_ACCEPTED_PURGE_SESSION_COUNT = 63
BENEFICIAL_OWNERSHIP_ACCEPTED_PURGE_FIRST = "2023-12-27"
BENEFICIAL_OWNERSHIP_ACCEPTED_PURGE_LAST = "2024-03-27"


class BeneficialOwnershipCloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise BeneficialOwnershipCloseoutError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BeneficialOwnershipCloseoutError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise BeneficialOwnershipCloseoutError(f"{label} must be a JSON object")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def beneficial_ownership_closeout_disposition(
    *,
    status: str,
    protected_return_eligible_finalists: list[str] | tuple[str, ...],
    protected_return_rows_read: int,
    protected_holdout_consumed: bool,
) -> tuple[str, bool]:
    if protected_return_rows_read != 0 or protected_holdout_consumed:
        raise BeneficialOwnershipCloseoutError(
            "negative closeout cannot follow a protected-return read"
        )
    if protected_return_eligible_finalists:
        return "PENDING_PROTECTED_CONFIRMATION", False
    if status in {
        "ACCEPTED_NEGATIVE_DEVELOPMENT",
        "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
    }:
        return "ACCEPTED_NEGATIVE", True
    raise BeneficialOwnershipCloseoutError(
        f"development status is not a negative-closeout state: {status!r}"
    )


def _require_zero_authority(report: Mapping[str, Any]) -> dict[str, bool]:
    return {
        "protected_returns_unread": int(report.get("protected_return_rows_read", -1)) == 0,
        "protected_holdout_unconsumed": report.get("protected_holdout_consumed") is False,
        "provider_writes_zero": int(report.get("provider_writes_performed", -1)) == 0,
        "broker_reads_zero": int(report.get("broker_reads_performed", -1)) == 0,
        "broker_writes_zero": int(report.get("broker_writes_performed", -1)) == 0,
        "orders_zero": int(report.get("order_writes_performed", -1)) == 0,
        "paper_zero": int(report.get("paper_submits_performed", -1)) == 0,
        "live_zero": int(report.get("live_writes_performed", -1)) == 0,
        "automation_zero": int(report.get("automation_writes_performed", -1)) == 0,
        "automatic_broker_failover_false": report.get("automatic_broker_failover") is False,
        "phase33_authority_false": report.get("phase33_signal_to_trade_authority") is False,
    }


def validate_beneficial_ownership_negative_closeout(settings: AtlasSettings) -> dict[str, Any]:
    """Validate only persisted target artifacts; perform no provider or new outcome reads."""
    derived_root = settings.resolved_path(settings.data.paths.derived)
    report_path = derived_root / BENEFICIAL_OWNERSHIP_DEVELOPMENT_REPORT_RELATIVE
    predictor_report_path = derived_root / BENEFICIAL_OWNERSHIP_PREDICTOR_REPORT_RELATIVE
    predictor_rows_path = derived_root / BENEFICIAL_OWNERSHIP_PREDICTOR_ROWS_RELATIVE
    outcome_path = derived_root / BENEFICIAL_OWNERSHIP_DEVELOPMENT_OUTCOMES_RELATIVE
    finalist_path = derived_root / BENEFICIAL_OWNERSHIP_FINALISTS_RELATIVE

    report = _read_json(report_path, "beneficial-ownership development report")
    predictor = _read_json(predictor_report_path, "beneficial-ownership predictor report")
    finalists = _read_json(finalist_path, "beneficial-ownership finalist artifact")
    for path, label in (
        (predictor_rows_path, "beneficial-ownership predictor rows"),
        (outcome_path, "beneficial-ownership development outcomes"),
    ):
        if not path.is_file():
            raise BeneficialOwnershipCloseoutError(f"missing {label}: {path}")

    hashes = {
        "development_report_sha256": sha256_file(report_path),
        "predictor_report_sha256": sha256_file(predictor_report_path),
        "predictor_rows_sha256": sha256_file(predictor_rows_path),
        "development_outcomes_sha256": sha256_file(outcome_path),
        "finalists_sha256": sha256_file(finalist_path),
    }
    boundaries = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    purge = boundaries.get("purge_sessions") if isinstance(boundaries.get("purge_sessions"), list) else []
    diagnostics = report.get("outcome_diagnostics") if isinstance(report.get("outcome_diagnostics"), dict) else {}
    eligible_raw = report.get("protected_return_eligible_finalists")
    eligible = [str(value) for value in eligible_raw] if isinstance(eligible_raw, list) else []
    disposition, accepted = beneficial_ownership_closeout_disposition(
        status=str(report.get("status") or ""),
        protected_return_eligible_finalists=eligible,
        protected_return_rows_read=int(report.get("protected_return_rows_read", -1)),
        protected_holdout_consumed=bool(report.get("protected_holdout_consumed")),
    )

    checks: dict[str, bool] = {
        "development_contract_exact": report.get("contract_version") == BENEFICIAL_OWNERSHIP_DEVELOPMENT_CONTRACT,
        "predictor_contract_exact": predictor.get("contract_version") == BENEFICIAL_OWNERSHIP_PREDICTOR_CONTRACT,
        "finalist_contract_exact": finalists.get("contract_version") == BENEFICIAL_OWNERSHIP_FINALIST_CONTRACT,
        "scientific_fingerprint_exact": report.get("scientific_fingerprint") == BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
        "predictor_scientific_fingerprint_exact": predictor.get("scientific_fingerprint") == BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
        "finalist_scientific_fingerprint_exact": finalists.get("scientific_fingerprint") == BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
        "development_implementation_fingerprint_exact": report.get("development_implementation_fingerprint") == BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        "finalist_implementation_fingerprint_exact": finalists.get("development_implementation_fingerprint") == BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        "development_status_exact": report.get("status") == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_STATUS,
        "development_report_pass": report.get("pass") is True,
        "development_report_sha_exact": hashes["development_report_sha256"] == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_REPORT_SHA256,
        "predictor_report_sha_exact": hashes["predictor_report_sha256"] == BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_REPORT_SHA256,
        "predictor_rows_sha_exact": hashes["predictor_rows_sha256"] == BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS_SHA256,
        "development_outcomes_sha_exact": hashes["development_outcomes_sha256"] == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256,
        "finalists_sha_exact": hashes["finalists_sha256"] == BENEFICIAL_OWNERSHIP_ACCEPTED_FINALISTS_SHA256,
        "predictor_rows_exact": int(predictor.get("predictor_rows", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS,
        "stage_counts_exact": predictor.get("stage_counts") == BENEFICIAL_OWNERSHIP_ACCEPTED_STAGE_COUNTS,
        "candidate_counts_exact": predictor.get("candidate_counts") == BENEFICIAL_OWNERSHIP_ACCEPTED_CANDIDATE_COUNTS,
        "provider_source_reads_exact": int(predictor.get("provider_source_reads", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_PROVIDER_SOURCE_READS,
        "predictor_outcome_blind": int(predictor.get("target_outcome_rows_read", -1)) == 0,
        "predictor_protected_blind": int(predictor.get("protected_return_rows_read", -1)) == 0 and predictor.get("protected_holdout_consumed") is False,
        "development_predictor_rows_exact": int(diagnostics.get("development_predictor_rows_opened", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS,
        "missing_stock_paths_exact": int(diagnostics.get("exact_stock_path_missing_rows", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_MISSING_STOCK_PATH_ROWS,
        "split_censored_rows_exact": int(diagnostics.get("split_crossing_censored_rows", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_SPLIT_CENSORED_ROWS,
        "usable_outcome_rows_exact": int(diagnostics.get("usable_development_rows", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS,
        "target_outcome_rows_exact": int(report.get("target_outcome_rows_read", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS,
        "protected_predictor_rows_exact": int(report.get("protected_predictor_rows_read_for_source_precheck", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_PROTECTED_PREDICTOR_ROWS,
        "selection_passers_empty": report.get("selection_passers") == [],
        "selection_winners_empty": report.get("selection_winners") == [],
        "internal_finalists_empty": report.get("internal_finalists") == [],
        "protected_source_prechecks_empty": report.get("protected_source_prechecks") == {},
        "protected_eligible_finalists_empty": eligible == [],
        "finalist_selection_winners_empty": finalists.get("selection_winners") == [],
        "finalist_internal_finalists_empty": finalists.get("internal_finalists") == [],
        "finalist_protected_prechecks_empty": finalists.get("protected_source_prechecks") == {},
        "finalist_protected_eligible_empty": finalists.get("protected_return_eligible_finalists") == [],
        "runner_up_substitution_false": finalists.get("runner_up_substitution_allowed") is False,
        "selection_start_exact": boundaries.get("selection_start") == BENEFICIAL_OWNERSHIP_ACCEPTED_SELECTION_START,
        "selection_end_exact": boundaries.get("selection_end") == BENEFICIAL_OWNERSHIP_ACCEPTED_SELECTION_END,
        "internal_start_exact": boundaries.get("internal_start") == BENEFICIAL_OWNERSHIP_ACCEPTED_INTERNAL_START,
        "internal_end_exact": boundaries.get("internal_end") == BENEFICIAL_OWNERSHIP_ACCEPTED_INTERNAL_END,
        "development_session_count_exact": int(boundaries.get("development_session_count", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_SESSION_COUNT,
        "selection_session_count_exact": int(boundaries.get("selection_session_count", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_SELECTION_SESSION_COUNT,
        "internal_session_count_exact": int(boundaries.get("internal_session_count", -1)) == BENEFICIAL_OWNERSHIP_ACCEPTED_INTERNAL_SESSION_COUNT,
        "purge_session_count_exact": len(purge) == BENEFICIAL_OWNERSHIP_ACCEPTED_PURGE_SESSION_COUNT,
        "purge_first_exact": bool(purge) and purge[0] == BENEFICIAL_OWNERSHIP_ACCEPTED_PURGE_FIRST,
        "purge_last_exact": bool(purge) and purge[-1] == BENEFICIAL_OWNERSHIP_ACCEPTED_PURGE_LAST,
        "predictor_report_sha_bound": report.get("predictor_report_sha256") == hashes["predictor_report_sha256"],
        "predictor_rows_sha_bound": report.get("predictor_rows_sha256") == hashes["predictor_rows_sha256"] and predictor.get("predictor_rows_sha256") == hashes["predictor_rows_sha256"],
        "development_outcomes_sha_bound": report.get("development_outcomes_sha256") == hashes["development_outcomes_sha256"],
        "finalists_sha_bound": report.get("finalists_sha256") == hashes["finalists_sha256"],
        "negative_disposition_exact": disposition == "ACCEPTED_NEGATIVE" and accepted,
    }
    checks.update(_require_zero_authority(report))
    checks["finalist_protected_returns_unread"] = int(finalists.get("protected_return_rows_read", -1)) == 0
    checks["finalist_holdout_unconsumed"] = finalists.get("protected_holdout_consumed") is False
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise BeneficialOwnershipCloseoutError(
            "beneficial-ownership negative closeout evidence failed: " + ", ".join(failed)
        )

    evidence = {
        "probe_contract": BENEFICIAL_OWNERSHIP_ACCEPTED_PROBE_CONTRACT,
        "accepted_development_target_head": BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        "scientific_fingerprint": BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
        "development_implementation_fingerprint": BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        "development_transport_repair_fingerprint": BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT,
        **hashes,
        "development_status": report.get("status"),
        "predictor_rows": BENEFICIAL_OWNERSHIP_ACCEPTED_PREDICTOR_ROWS,
        "development_predictor_rows": BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS,
        "development_outcome_rows": BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS,
        "protected_predictor_rows": BENEFICIAL_OWNERSHIP_ACCEPTED_PROTECTED_PREDICTOR_ROWS,
        "selection_passers": [],
        "selection_winners": [],
        "internal_finalists": [],
        "protected_return_eligible_finalists": [],
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "disposition": disposition,
        "phase33_signal_to_trade_authority": False,
    }
    evidence_fingerprint = _fingerprint(evidence)
    if evidence_fingerprint != BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT:
        raise BeneficialOwnershipCloseoutError(
            "beneficial-ownership closeout evidence fingerprint differs from accepted target evidence"
        )
    return {
        "contract_version": BENEFICIAL_OWNERSHIP_CLOSEOUT_CONTRACT,
        "pass": True,
        "disposition": disposition,
        "accepted_development_target_head": BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        "evidence_fingerprint": evidence_fingerprint,
        "evidence": evidence,
        "checks": checks,
        "historical_supported_alpha": 0,
        "phase33_signal_to_trade_authority": False,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "provider_reads_performed": 0,
        "provider_writes_performed": 0,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "automation_writes_performed": 0,
        "automatic_broker_failover": False,
    }
