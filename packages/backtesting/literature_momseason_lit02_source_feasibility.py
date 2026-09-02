from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_development_source_diagnostic import (
    LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_REPORT,
    LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
)
from .literature_momseason_lit01_closeout import (
    LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_REPORT,
    LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS,
    MomSeasonLIT01Closeout,
)
from .literature_momseason_lit02_source_policy import (
    LIT02_LIT01_CLOSEOUT_FINGERPRINT,
    LIT02_REQUIRED_SOURCE_COVERAGE,
    LIT02_RETURN_PATHS,
    LIT02_SOURCE_CONTRACT_VERSION,
    LIT02_SOURCE_POLICY_STATUS,
    lit02_source_policy_fingerprint,
)
from .literature_momseason_source import canonical_json


LIT02_SOURCE_FEASIBILITY_PLAN_STATUS = "LIT02_DELISTING_AWARE_SOURCE_FEASIBILITY_PLAN_READY"
LIT02_SOURCE_FEASIBILITY_PLAN_CONTRACT = (
    "lit02-delisting-aware-source-feasibility-plan-v1-lit01-missing-keys-source-only"
)

# Keep the persisted LIT-02 namespace deliberately compact.  The surrounding
# literature research root is already deep, and atomic_write_text writes a sibling
# PID/UUID temp file before promotion.  Long semantic directory/file names can push
# otherwise valid Windows paths beyond the legacy MAX_PATH boundary.  Full semantic
# identity remains inside the JSON contract/status/fingerprints; these names are
# storage locators only.
LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT = "l2"
LIT02_SOURCE_FEASIBILITY_PLAN_FILE = "p.json"
LIT02_SOURCE_FEASIBILITY_REPORT_FILE = "r.json"


def _require_zero(report: Mapping[str, object], field: str, *, label: str) -> None:
    if int(report.get(field) or 0) != 0:
        raise RuntimeError(f"LIT-02 source-feasibility {label} safety field is nonzero: {field}")


def _fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def build_lit02_source_feasibility_plan(
    *,
    closeout: Mapping[str, object],
    diagnostic: Mapping[str, object],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    """Freeze source-only stress cases from LIT-01 without reading return values."""

    if closeout.get("status") != LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS:
        raise RuntimeError("LIT-02 source feasibility requires accepted LIT-01 source-inconclusive closeout")
    if str(closeout.get("closeout_fingerprint") or "") != LIT02_LIT01_CLOSEOUT_FINGERPRINT:
        raise RuntimeError("LIT-02 source feasibility LIT-01 closeout fingerprint mismatch")
    if closeout.get("economic_signal_classification") != "NOT_REACHED":
        raise RuntimeError("LIT-02 source feasibility refuses a LIT-01 economic classification")
    if bool(closeout.get("alpha_rejection")) or bool(closeout.get("alpha_support")):
        raise RuntimeError("LIT-02 source feasibility refuses reclassified LIT-01 alpha evidence")
    if closeout.get("family_finalist") is not None:
        raise RuntimeError("LIT-02 source feasibility refuses a LIT-01 finalist classification")

    if diagnostic.get("status") != LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS:
        raise RuntimeError("LIT-02 source feasibility requires the accepted LIT-01 source diagnostic")
    if int(diagnostic.get("missing_target_units") or 0) != 0:
        raise RuntimeError("LIT-02 source feasibility requires all LIT-01 target units materialized")

    for label, report in (("closeout", closeout), ("diagnostic", diagnostic)):
        _require_zero(report, "protected_return_rows_read", label=label)
        _require_zero(report, "broker_reads_performed", label=label)
        _require_zero(report, "broker_writes_performed", label=label)
        _require_zero(report, "order_writes_performed", label=label)
        _require_zero(report, "paper_submits_performed", label=label)
        _require_zero(report, "live_writes_performed", label=label)
        if bool(report.get("protected_holdout_consumed")):
            raise RuntimeError(f"LIT-02 source feasibility {label} consumed protected holdout")
    _require_zero(diagnostic, "provider_reads_performed", label="diagnostic")

    unavailable_source_keys = int(diagnostic.get("unavailable_source_keys") or 0)
    unavailable_plan_rows = int(diagnostic.get("unavailable_plan_rows") or 0)
    blocked_holdings = int(diagnostic.get("blocked_holdings") or 0)
    if unavailable_source_keys <= 0 or unavailable_plan_rows <= 0 or blocked_holdings <= 0:
        raise RuntimeError("LIT-02 source feasibility requires demonstrated LIT-01 source incompleteness")
    if unavailable_source_keys != int(closeout.get("unavailable_provider_source_keys") or 0):
        raise RuntimeError("LIT-02 source feasibility unavailable source-key count mismatch")
    if unavailable_plan_rows != int(closeout.get("unavailable_plan_rows") or 0):
        raise RuntimeError("LIT-02 source feasibility unavailable plan-row count mismatch")
    if blocked_holdings != int(closeout.get("development_unavailable_holding_returns") or 0):
        raise RuntimeError("LIT-02 source feasibility blocked holding count mismatch")

    raw_details = diagnostic.get("details")
    if not isinstance(raw_details, list):
        raise RuntimeError("LIT-02 source feasibility diagnostic details are missing")
    if len(raw_details) != unavailable_source_keys:
        raise RuntimeError("LIT-02 source feasibility diagnostic detail count mismatch")

    allowed_paths = [item.path_id for item in LIT02_RETURN_PATHS if item.path_id != "ORDINARY_MONTH_END"]
    cases: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for raw in raw_details:
        if not isinstance(raw, Mapping):
            raise RuntimeError("LIT-02 source feasibility diagnostic detail is not an object")
        endpoint = str(raw.get("endpoint_session") or "").strip()
        ticker = str(raw.get("historical_ticker") or "").strip()
        status = str(raw.get("availability_status") or "").strip()
        instrument_ids = sorted({str(value) for value in (raw.get("instrument_ids") or []) if str(value)})
        if not endpoint or not ticker or not instrument_ids:
            raise RuntimeError("LIT-02 source feasibility diagnostic detail is missing identity fields")
        key = (endpoint, ticker)
        if key in seen:
            raise RuntimeError(f"duplicate LIT-02 feasibility source key: {endpoint} {ticker}")
        seen.add(key)
        if status != "ZERO_BAR":
            raise RuntimeError(
                "LIT-02 frozen feasibility population changed from accepted LIT-01 ZERO_BAR evidence: "
                f"{endpoint} {ticker} status={status!r}"
            )
        case_core = {
            "endpoint_session": endpoint,
            "historical_ticker": ticker,
            "instrument_ids": instrument_ids,
            "lit01_availability_status": status,
            "lit01_prior_holding_hits": int(raw.get("prior_holding_hits") or 0),
            "lit01_target_holding_hits": int(raw.get("target_holding_hits") or 0),
            "lit01_blocked_holdings": int(raw.get("blocked_holdings") or 0),
            "hypotheses": sorted({str(value) for value in (raw.get("hypotheses") or []) if str(value)}),
            "target_months": sorted({str(value) for value in (raw.get("target_months") or []) if str(value)}),
        }
        cases.append(
            {
                "case_id": "lit02case_" + _fingerprint(case_core)[:20],
                **case_core,
                "candidate_return_paths": allowed_paths,
                "resolution_status": "UNRESOLVED_PRE_SOURCE_READ",
            }
        )

    cases.sort(key=lambda item: (str(item["endpoint_session"]), str(item["historical_ticker"])))
    plan_fingerprint = _fingerprint(cases)
    policy_fingerprint = lit02_source_policy_fingerprint()
    report: dict[str, object] = {
        "status": LIT02_SOURCE_FEASIBILITY_PLAN_STATUS,
        "contract_version": LIT02_SOURCE_FEASIBILITY_PLAN_CONTRACT,
        "source_contract_version": LIT02_SOURCE_CONTRACT_VERSION,
        "source_contract_status": LIT02_SOURCE_POLICY_STATUS,
        "source_policy_fingerprint": policy_fingerprint,
        "lit01_closeout_fingerprint": LIT02_LIT01_CLOSEOUT_FINGERPRINT,
        "lit01_closeout_head": "d1d70946df53570afc23f547286b6a04b10b3ab6",
        "lit01_missing_source_keys_used": len(cases),
        "lit01_unavailable_plan_rows": unavailable_plan_rows,
        "lit01_blocked_holdings": blocked_holdings,
        "required_source_coverage": LIT02_REQUIRED_SOURCE_COVERAGE,
        "feasibility_cases": len(cases),
        "feasibility_plan_fingerprint": plan_fingerprint,
        "economic_outcome_values_read": 0,
        "new_price_or_return_provider_reads": 0,
        "source_metadata_provider_reads": 0,
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
        "fresh_confirmatory_reuse_of_lit01_2021_09_to_2026_04": False,
        "storage_namespace": LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT,
        "next_action": (
            "Acquire only source/identity/transaction metadata for the frozen feasibility cases; "
            "classify each case into an admissible return path or SOURCE_UNRESOLVED. Do not read "
            "new price/return outcomes during the feasibility gate."
        ),
    }
    report["report_fingerprint"] = _fingerprint(report)
    return cases, report


class MomSeasonLIT02SourceFeasibilityPlan:
    """Local-only LIT-02 source contract freeze and missing-case plan."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.lit01 = MomSeasonLIT01Closeout(settings)
        self.root: Path = self.lit01.root / LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT

    def closeout_path(self) -> Path:
        return self.lit01.root / LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_REPORT

    def diagnostic_path(self) -> Path:
        return self.lit01.root / LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_REPORT

    def plan_path(self) -> Path:
        return self.root / LIT02_SOURCE_FEASIBILITY_PLAN_FILE

    def report_path(self) -> Path:
        return self.root / LIT02_SOURCE_FEASIBILITY_REPORT_FILE

    def run(self) -> dict[str, object]:
        if not self.closeout_path().is_file():
            raise RuntimeError(f"LIT-02 source feasibility requires LIT-01 closeout: {self.closeout_path()}")
        if not self.diagnostic_path().is_file():
            raise RuntimeError(f"LIT-02 source feasibility requires LIT-01 diagnostic: {self.diagnostic_path()}")
        closeout = json.loads(self.closeout_path().read_text(encoding="utf-8"))
        diagnostic = json.loads(self.diagnostic_path().read_text(encoding="utf-8"))
        cases, report = build_lit02_source_feasibility_plan(closeout=closeout, diagnostic=diagnostic)
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.plan_path(), canonical_json({"cases": cases}) + "\n")
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        result = dict(report)
        result["plan_path"] = str(self.plan_path())
        result["report_path"] = str(self.report_path())
        return result
