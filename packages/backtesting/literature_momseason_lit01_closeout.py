from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_development import (
    MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
    MOMSEASON_DEVELOPMENT_REPORT,
    MOMSEASON_DEVELOPMENT_ROOT,
    MOMSEASON_DEVELOPMENT_SOURCE_INCOMPLETE,
)
from .literature_momseason_development_source_diagnostic import (
    LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_REPORT,
    LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
)
from .literature_momseason_native_population import MOMSEASON_NATIVE_POPULATION_ROOT
from .literature_momseason_research_freeze import MOMSEASON_RESEARCH_FREEZE_ROOT
from .literature_momseason_source import MOMSEASON_SOURCE_ROOT_RELATIVE, canonical_json


LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_CONTRACT = (
    "lit01-source-incomplete-closeout-v1-frozen-contract-no-reclassification-no-protected"
)
LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS = "LIT01_CLOSED_SOURCE_INTEGRITY_INCONCLUSIVE"
LIT01_SOURCE_INCONCLUSIVE_CLASSIFICATION = "SOURCE_INTEGRITY_INCONCLUSIVE"
LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_REPORT = "lit01_source_inconclusive_closeout.json"


def _nested_mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise RuntimeError(f"LIT-01 closeout requires mapping field: {label}")
    return value


def _require_zero(report: Mapping[str, object], field: str, *, label: str) -> None:
    if int(report.get(field) or 0) != 0:
        raise RuntimeError(f"LIT-01 closeout {label} safety field is nonzero: {field}")


def build_lit01_closeout_report(
    diagnostic: Mapping[str, object],
    development_report: Mapping[str, object],
) -> dict[str, object]:
    """Close the frozen LIT-01 attempt without reclassifying its economic signal."""

    if diagnostic.get("status") != LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS:
        raise RuntimeError("LIT-01 closeout diagnostic status is not source-incomplete-ready")
    if development_report.get("status") != MOMSEASON_DEVELOPMENT_SOURCE_INCOMPLETE:
        raise RuntimeError("LIT-01 closeout development status is not source-incomplete")

    diagnostic_freeze = str(diagnostic.get("freeze_fingerprint") or "")
    development_freeze = str(development_report.get("freeze_fingerprint") or "")
    if diagnostic_freeze != MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT:
        raise RuntimeError("LIT-01 closeout diagnostic freeze fingerprint mismatch")
    if development_freeze != MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT:
        raise RuntimeError("LIT-01 closeout development freeze fingerprint mismatch")

    plan = _nested_mapping(development_report.get("plan"), label="development.plan")
    holdings_fingerprint = str(diagnostic.get("holdings_fingerprint") or "")
    target_plan_fingerprint = str(diagnostic.get("target_plan_fingerprint") or "")
    if holdings_fingerprint != str(plan.get("holdings_fingerprint") or ""):
        raise RuntimeError("LIT-01 closeout holdings fingerprint mismatch")
    if target_plan_fingerprint != str(plan.get("target_plan_fingerprint") or ""):
        raise RuntimeError("LIT-01 closeout target-plan fingerprint mismatch")
    if int(diagnostic.get("holdings_rows") or 0) != int(plan.get("holdings_rows") or 0):
        raise RuntimeError("LIT-01 closeout holdings row count mismatch")
    if int(diagnostic.get("target_plan_rows") or 0) != int(plan.get("target_plan_rows") or 0):
        raise RuntimeError("LIT-01 closeout target-plan row count mismatch")

    if int(diagnostic.get("missing_target_units") or 0) != 0:
        raise RuntimeError("LIT-01 closeout requires all frozen target units to be materialized")
    unavailable_plan_rows = int(diagnostic.get("unavailable_plan_rows") or 0)
    unavailable_source_keys = int(diagnostic.get("unavailable_source_keys") or 0)
    blocked_holdings = int(diagnostic.get("blocked_holdings") or 0)
    if unavailable_plan_rows <= 0 or unavailable_source_keys <= 0 or blocked_holdings <= 0:
        raise RuntimeError("LIT-01 closeout requires demonstrated frozen source incompleteness")

    evaluation = _nested_mapping(development_report.get("evaluation"), label="development.evaluation")
    if bool(evaluation.get("source_complete")):
        raise RuntimeError("LIT-01 closeout cannot source-close a complete evaluation")
    complete_returns = int(evaluation.get("complete_holding_returns") or 0)
    unavailable_returns = int(evaluation.get("unavailable_holding_returns") or 0)
    if complete_returns <= 0:
        raise RuntimeError("LIT-01 closeout requires opened development outcomes")
    if unavailable_returns <= 0:
        raise RuntimeError("LIT-01 closeout requires unavailable development returns")
    if blocked_holdings != unavailable_returns:
        raise RuntimeError("LIT-01 closeout diagnostic/development blocked-return count mismatch")

    development_outcomes_opened = int(development_report.get("development_outcome_rows_read") or 0)
    if development_outcomes_opened <= 0:
        raise RuntimeError("LIT-01 closeout development outcome read count is not positive")

    finalist = evaluation.get("family_finalist")
    if finalist not in (None, False):
        raise RuntimeError("LIT-01 closeout refuses a positive family-finalist result")
    finalist_hypotheses = evaluation.get("finalist_hypotheses") or []
    if finalist_hypotheses:
        raise RuntimeError("LIT-01 closeout refuses nonempty finalist hypotheses")

    for label, report in (("diagnostic", diagnostic), ("development", development_report)):
        for field in (
            "protected_return_rows_read",
            "broker_reads_performed",
            "broker_writes_performed",
            "order_writes_performed",
            "paper_submits_performed",
            "live_writes_performed",
        ):
            _require_zero(report, field, label=label)
        if bool(report.get("protected_holdout_consumed")):
            raise RuntimeError(f"LIT-01 closeout {label} consumed the protected holdout")

    _require_zero(diagnostic, "provider_reads_performed", label="diagnostic")

    closeout: dict[str, object] = {
        "status": LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS,
        "contract_version": LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_CONTRACT,
        "scientific_classification": LIT01_SOURCE_INCONCLUSIVE_CLASSIFICATION,
        "economic_signal_classification": "NOT_REACHED",
        "alpha_rejection": False,
        "alpha_support": False,
        "family_finalist": None,
        "finalist_hypotheses": [],
        "lit01_inference_performed": False,
        "lit01_source_contract_changed": False,
        "development_outcomes_opened": True,
        "development_outcome_rows_read": development_outcomes_opened,
        "development_complete_holding_returns": complete_returns,
        "development_unavailable_holding_returns": unavailable_returns,
        "unavailable_plan_rows": unavailable_plan_rows,
        "unavailable_provider_source_keys": unavailable_source_keys,
        "unavailable_status_counts": dict(diagnostic.get("unavailable_status_counts") or {}),
        "blocked_holdings_by_hypothesis": dict(
            diagnostic.get("blocked_holdings_by_hypothesis") or {}
        ),
        "holdings_rows": int(diagnostic.get("holdings_rows") or 0),
        "target_plan_rows": int(diagnostic.get("target_plan_rows") or 0),
        "freeze_fingerprint": diagnostic_freeze,
        "holdings_fingerprint": holdings_fingerprint,
        "target_plan_fingerprint": target_plan_fingerprint,
        "provider_reads_performed": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "phase33_signal_to_trade_authority": False,
        "production_authority": False,
        "next_scientific_action": (
            "Define and freeze a new delisting-aware monthly return source contract before "
            "reading outcomes under that new contract; preserve LIT-01 unchanged and do not "
            "reinterpret its source-incomplete development evidence."
        ),
    }
    closeout["closeout_fingerprint"] = hashlib.sha256(
        canonical_json(closeout).encode("utf-8")
    ).hexdigest()
    return closeout


class MomSeasonLIT01Closeout:
    """Local-only closeout for the frozen, source-incomplete LIT-01 attempt."""

    def __init__(self, settings: AtlasSettings) -> None:
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = (
            derived
            / MOMSEASON_SOURCE_ROOT_RELATIVE
            / "total_return_source"
            / MOMSEASON_NATIVE_POPULATION_ROOT
            / MOMSEASON_RESEARCH_FREEZE_ROOT
            / MOMSEASON_DEVELOPMENT_ROOT
        )

    def diagnostic_path(self) -> Path:
        return self.root / LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_REPORT

    def development_report_path(self) -> Path:
        return self.root / MOMSEASON_DEVELOPMENT_REPORT

    def report_path(self) -> Path:
        return self.root / LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_REPORT

    def run(self) -> dict[str, object]:
        if not self.diagnostic_path().is_file():
            raise RuntimeError(f"LIT-01 closeout diagnostic is required: {self.diagnostic_path()}")
        if not self.development_report_path().is_file():
            raise RuntimeError(
                f"LIT-01 closeout development report is required: {self.development_report_path()}"
            )
        diagnostic = json.loads(self.diagnostic_path().read_text(encoding="utf-8"))
        development = json.loads(self.development_report_path().read_text(encoding="utf-8"))
        report = build_lit01_closeout_report(diagnostic, development)
        self.report_path().parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        result = dict(report)
        result["report_path"] = str(self.report_path())
        return result
