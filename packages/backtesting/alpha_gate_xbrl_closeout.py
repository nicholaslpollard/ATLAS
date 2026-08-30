from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from packages.backtesting.alpha_gate_xbrl_development import (
    XBRL_DEVELOPMENT_CONTRACT,
    XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    XBRL_DEVELOPMENT_OUTCOMES_RELATIVE,
    XBRL_DEVELOPMENT_REPORT_RELATIVE,
    XBRL_FINALISTS_RELATIVE,
)
from packages.backtesting.alpha_gate_xbrl_predictor import (
    XBRL_PREDICTOR_CONTRACT,
    XBRL_PREDICTOR_REPORT_RELATIVE,
    XBRL_PREDICTOR_ROWS_RELATIVE,
)
from packages.backtesting.alpha_gate_xbrl_scientific_policy import XBRL_SCIENTIFIC_FINGERPRINT
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file


XBRL_CLOSEOUT_CONTRACT = "alpha-gate-xbrl-closeout-v1-development-negative-protected-unread"
XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD = "58e7c9b60ba59d250a7c91e282daefa4aef3c2b9"
XBRL_ACCEPTED_DEVELOPMENT_STATUS = "ACCEPTED_NEGATIVE_DEVELOPMENT"
XBRL_ACCEPTED_EVIDENCE_FINGERPRINT = "291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91"
XBRL_ACCEPTED_DEVELOPMENT_REPORT_SHA256 = "50bf99956ca95d725764b16bc5ae622b5ffe9dbfbadb4e63afa591a4aef998c6"
XBRL_ACCEPTED_PREDICTOR_REPORT_SHA256 = "246bc1df65ce923b83167ea65f7e25b266657dec30fdcfd841e4bae260fbdb16"
XBRL_ACCEPTED_PREDICTOR_ROWS_SHA256 = "9b3526527d2d45433f5970d768155c9763c16bc8d0772fdc526659ec1aabd14a"
XBRL_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256 = "17be9dd103902ea0e9f39c172b7dfb0cf3d552b6f743bd8101c7f836b8500b55"
XBRL_ACCEPTED_FINALISTS_SHA256 = "c5cfddbe30b597d115560a9611e8bf3bef5bcb76f7c59f5d5f5a071db458945f"
XBRL_ACCEPTED_PREDICTOR_ROWS = 5536
XBRL_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS = 4157
XBRL_ACCEPTED_PROTECTED_PREDICTOR_ROWS = 1379
XBRL_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS = 3963
XBRL_ACCEPTED_MISSING_STOCK_PATH_ROWS = 123
XBRL_ACCEPTED_SPLIT_CENSORED_ROWS = 71
XBRL_ACCEPTED_PROVIDER_SOURCE_READS = 3415
XBRL_ACCEPTED_STAGE_COUNTS = {"DEVELOPMENT": 4157, "PROTECTED": 1379}
XBRL_ACCEPTED_CANDIDATE_COUNTS = {
    "accrual_quality_deterioration_short": 1027,
    "accrual_quality_improvement_long": 1109,
    "cash_profitability_deterioration_short": 1174,
    "cash_profitability_improvement_long": 1098,
    "gross_profitability_deterioration_short": 512,
    "gross_profitability_improvement_long": 616,
}
XBRL_ACCEPTED_SELECTION_START = "2021-08-16"
XBRL_ACCEPTED_SELECTION_END = "2023-12-26"
XBRL_ACCEPTED_INTERNAL_START = "2024-03-28"
XBRL_ACCEPTED_INTERNAL_END = "2024-12-31"
XBRL_ACCEPTED_DEVELOPMENT_SESSION_COUNT = 850
XBRL_ACCEPTED_SELECTION_SESSION_COUNT = 595
XBRL_ACCEPTED_INTERNAL_SESSION_COUNT = 192
XBRL_ACCEPTED_INTERNAL_PURGE_SESSION_COUNT = 63
XBRL_ACCEPTED_INTERNAL_PURGE_FIRST = "2023-12-27"
XBRL_ACCEPTED_INTERNAL_PURGE_LAST = "2024-03-27"


class XBRLCloseoutError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise XBRLCloseoutError(f"missing {label}: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise XBRLCloseoutError(f"invalid {label}: {path}") from exc
    if not isinstance(value, dict):
        raise XBRLCloseoutError(f"{label} must be a JSON object")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def xbrl_closeout_disposition(
    *,
    status: str,
    protected_return_eligible_finalists: list[str] | tuple[str, ...],
    protected_return_rows_read: int,
    protected_holdout_consumed: bool,
) -> tuple[str, bool]:
    if protected_return_rows_read != 0 or protected_holdout_consumed:
        raise XBRLCloseoutError("negative closeout cannot follow a protected-return read")
    if protected_return_eligible_finalists:
        return "PENDING_PROTECTED_CONFIRMATION", False
    if status in {
        "ACCEPTED_NEGATIVE_DEVELOPMENT",
        "ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT",
    }:
        return "ACCEPTED_NEGATIVE", True
    raise XBRLCloseoutError(f"development status is not a negative-closeout state: {status!r}")


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


def validate_xbrl_negative_closeout(settings: AtlasSettings) -> dict[str, Any]:
    derived_root = settings.resolved_path(settings.data.paths.derived)
    report_path = derived_root / XBRL_DEVELOPMENT_REPORT_RELATIVE
    predictor_report_path = derived_root / XBRL_PREDICTOR_REPORT_RELATIVE
    predictor_rows_path = derived_root / XBRL_PREDICTOR_ROWS_RELATIVE
    outcome_path = derived_root / XBRL_DEVELOPMENT_OUTCOMES_RELATIVE
    finalist_path = derived_root / XBRL_FINALISTS_RELATIVE

    report = _read_json(report_path, "XBRL development report")
    predictor = _read_json(predictor_report_path, "XBRL predictor report")
    finalists = _read_json(finalist_path, "XBRL finalist artifact")

    report_sha = sha256_file(report_path)
    predictor_report_sha = sha256_file(predictor_report_path)
    predictor_rows_sha = sha256_file(predictor_rows_path)
    outcome_sha = sha256_file(outcome_path)
    finalist_sha = sha256_file(finalist_path)

    boundaries = report.get("boundaries") if isinstance(report.get("boundaries"), dict) else {}
    purge = boundaries.get("purge_sessions") if isinstance(boundaries.get("purge_sessions"), list) else []
    diagnostics = report.get("outcome_diagnostics") if isinstance(report.get("outcome_diagnostics"), dict) else {}
    eligible = report.get("protected_return_eligible_finalists")
    eligible_list = [str(value) for value in eligible] if isinstance(eligible, list) else []
    disposition, accepted = xbrl_closeout_disposition(
        status=str(report.get("status") or ""),
        protected_return_eligible_finalists=eligible_list,
        protected_return_rows_read=int(report.get("protected_return_rows_read", -1)),
        protected_holdout_consumed=bool(report.get("protected_holdout_consumed")),
    )

    checks: dict[str, bool] = {
        "development_contract_exact": report.get("contract_version") == XBRL_DEVELOPMENT_CONTRACT,
        "predictor_contract_exact": predictor.get("contract_version") == XBRL_PREDICTOR_CONTRACT,
        "scientific_fingerprint_exact": report.get("scientific_fingerprint") == XBRL_SCIENTIFIC_FINGERPRINT,
        "predictor_scientific_fingerprint_exact": predictor.get("scientific_fingerprint") == XBRL_SCIENTIFIC_FINGERPRINT,
        "development_implementation_fingerprint_exact": report.get("development_implementation_fingerprint") == XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        "development_status_exact": report.get("status") == XBRL_ACCEPTED_DEVELOPMENT_STATUS,
        "development_report_pass": report.get("pass") is True,
        "development_report_sha_exact": report_sha == XBRL_ACCEPTED_DEVELOPMENT_REPORT_SHA256,
        "predictor_report_sha_exact": predictor_report_sha == XBRL_ACCEPTED_PREDICTOR_REPORT_SHA256,
        "predictor_rows_sha_exact": predictor_rows_sha == XBRL_ACCEPTED_PREDICTOR_ROWS_SHA256,
        "development_outcomes_sha_exact": outcome_sha == XBRL_ACCEPTED_DEVELOPMENT_OUTCOMES_SHA256,
        "finalists_sha_exact": finalist_sha == XBRL_ACCEPTED_FINALISTS_SHA256,
        "predictor_rows_exact": int(predictor.get("predictor_rows", -1)) == XBRL_ACCEPTED_PREDICTOR_ROWS,
        "stage_counts_exact": predictor.get("stage_counts") == XBRL_ACCEPTED_STAGE_COUNTS,
        "candidate_counts_exact": predictor.get("candidate_counts") == XBRL_ACCEPTED_CANDIDATE_COUNTS,
        "provider_source_reads_exact": int(predictor.get("source_reads_performed", -1)) == XBRL_ACCEPTED_PROVIDER_SOURCE_READS,
        "predictor_outcome_blind": int(predictor.get("target_outcome_rows_read", -1)) == 0,
        "predictor_protected_blind": int(predictor.get("protected_return_rows_read", -1)) == 0 and predictor.get("protected_holdout_consumed") is False,
        "development_predictor_rows_exact": int(diagnostics.get("development_predictor_rows_opened", -1)) == XBRL_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS,
        "missing_stock_paths_exact": int(diagnostics.get("exact_stock_path_missing_rows", -1)) == XBRL_ACCEPTED_MISSING_STOCK_PATH_ROWS,
        "split_censored_rows_exact": int(diagnostics.get("split_crossing_censored_rows", -1)) == XBRL_ACCEPTED_SPLIT_CENSORED_ROWS,
        "usable_outcome_rows_exact": int(diagnostics.get("usable_development_rows", -1)) == XBRL_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS,
        "target_outcome_rows_exact": int(report.get("target_outcome_rows_read", -1)) == XBRL_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS,
        "protected_predictor_rows_exact": int(report.get("protected_predictor_rows_read_for_source_precheck", -1)) == XBRL_ACCEPTED_PROTECTED_PREDICTOR_ROWS,
        "selection_passers_empty": report.get("selection_passers") == [],
        "selection_winners_empty": report.get("selection_winners") == [],
        "internal_finalists_empty": report.get("internal_finalists") == [],
        "protected_source_prechecks_empty": report.get("protected_source_prechecks") == {},
        "protected_eligible_finalists_empty": eligible_list == [],
        "finalist_selection_winners_empty": finalists.get("selection_winners") == [],
        "finalist_internal_finalists_empty": finalists.get("internal_finalists") == [],
        "finalist_protected_prechecks_empty": finalists.get("protected_source_prechecks") == {},
        "finalist_protected_eligible_empty": finalists.get("protected_return_eligible_finalists") == [],
        "runner_up_substitution_false": finalists.get("runner_up_substitution_allowed") is False,
        "selection_start_exact": boundaries.get("selection_start") == XBRL_ACCEPTED_SELECTION_START,
        "selection_end_exact": boundaries.get("selection_end") == XBRL_ACCEPTED_SELECTION_END,
        "internal_start_exact": boundaries.get("internal_start") == XBRL_ACCEPTED_INTERNAL_START,
        "internal_end_exact": boundaries.get("internal_end") == XBRL_ACCEPTED_INTERNAL_END,
        "development_session_count_exact": int(boundaries.get("development_session_count", -1)) == XBRL_ACCEPTED_DEVELOPMENT_SESSION_COUNT,
        "selection_session_count_exact": int(boundaries.get("selection_session_count", -1)) == XBRL_ACCEPTED_SELECTION_SESSION_COUNT,
        "internal_session_count_exact": int(boundaries.get("internal_session_count", -1)) == XBRL_ACCEPTED_INTERNAL_SESSION_COUNT,
        "purge_session_count_exact": len(purge) == XBRL_ACCEPTED_INTERNAL_PURGE_SESSION_COUNT,
        "purge_first_exact": bool(purge) and purge[0] == XBRL_ACCEPTED_INTERNAL_PURGE_FIRST,
        "purge_last_exact": bool(purge) and purge[-1] == XBRL_ACCEPTED_INTERNAL_PURGE_LAST,
        "predictor_report_sha_bound": report.get("predictor_report_sha256") == predictor_report_sha,
        "predictor_rows_sha_bound": report.get("predictor_rows_sha256") == predictor_rows_sha and predictor.get("predictor_rows_sha256") == predictor_rows_sha,
        "development_outcomes_sha_bound": report.get("development_outcomes_sha256") == outcome_sha,
        "finalist_sha_bound": report.get("finalists_sha256") == finalist_sha,
        "finalist_scientific_fingerprint_exact": finalists.get("scientific_fingerprint") == XBRL_SCIENTIFIC_FINGERPRINT,
        "finalist_implementation_fingerprint_exact": finalists.get("development_implementation_fingerprint") == XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        "negative_disposition_exact": disposition == "ACCEPTED_NEGATIVE" and accepted,
    }
    checks.update(_require_zero_authority(report))
    checks["finalist_protected_returns_unread"] = int(finalists.get("protected_return_rows_read", -1)) == 0
    checks["finalist_holdout_unconsumed"] = finalists.get("protected_holdout_consumed") is False
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise XBRLCloseoutError("XBRL negative closeout evidence failed: " + ", ".join(failed))

    evidence = {
        "closeout_contract": XBRL_CLOSEOUT_CONTRACT,
        "accepted_development_target_head": XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
        "scientific_fingerprint": XBRL_SCIENTIFIC_FINGERPRINT,
        "development_implementation_fingerprint": XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
        "development_report_sha256": report_sha,
        "predictor_report_sha256": predictor_report_sha,
        "predictor_rows_sha256": predictor_rows_sha,
        "development_outcomes_sha256": outcome_sha,
        "finalists_sha256": finalist_sha,
        "development_status": report.get("status"),
        "predictor_rows": XBRL_ACCEPTED_PREDICTOR_ROWS,
        "development_predictor_rows": XBRL_ACCEPTED_DEVELOPMENT_PREDICTOR_ROWS,
        "development_outcome_rows": XBRL_ACCEPTED_DEVELOPMENT_OUTCOME_ROWS,
        "protected_predictor_rows": XBRL_ACCEPTED_PROTECTED_PREDICTOR_ROWS,
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
    if evidence_fingerprint != XBRL_ACCEPTED_EVIDENCE_FINGERPRINT:
        raise XBRLCloseoutError("XBRL closeout evidence fingerprint differs from accepted target evidence")
    return {
        "contract_version": XBRL_CLOSEOUT_CONTRACT,
        "pass": True,
        "disposition": disposition,
        "accepted_development_target_head": XBRL_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
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
