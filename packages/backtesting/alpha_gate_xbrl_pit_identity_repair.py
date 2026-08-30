from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from packages.backtesting.alpha_gate_xbrl_pit_audit import (
    XBRL_PIT_AUDIT_CONTRACT,
    XBRL_PIT_AUDIT_FINGERPRINT,
    XBRL_PIT_EVIDENCE_RELATIVE,
    XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS,
    XBRL_PIT_MIN_ACCEPTANCE_DECISIONS,
    XBRL_PIT_MIN_COMPANYFACTS_SUCCESS,
    XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS,
    XBRL_PIT_MIN_SEC_METADATA_RECONCILED,
    XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS,
    XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS,
    XBRL_PIT_REPORT_RELATIVE,
    XBRLPITAuditError,
    _normalize_cik,
    _resolve_identity,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file


XBRL_PIT_IDENTITY_REPAIR_CONTRACT = (
    "alpha-gate-xbrl-pit-audit-v2-targeted-common-stock-active-only-identity-repair-no-market-outcomes"
)
XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT = (
    "e17cf5539fbd5d3d0c31514d5fbed97332f046eb98af05dfaa0039a8c127304f"
)
XBRL_PIT_IDENTITY_REPAIR_REASON = (
    "MASSIVE_HISTORICAL_DATE_ACTIVE_FALSE_AND_NON_COMMON_TYPES_EXPANDED_NONTRADABLE_UNIVERSE"
)
XBRL_PIT_IDENTITY_REPAIR_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/xbrl_pit_audit_v2/source_audit.json"
)

_V1_EXPECTED_COUNTS = {
    "audit_issuer_sample_size": 40,
    "companyfacts_success": 40,
    "selected_original_filings": 200,
    "sec_metadata_reconciled": 198,
    "acceptance_decisions": 198,
    "unambiguous_identity_mappings": 139,
    "issuers_with_3_unambiguous_mappings": 28,
    "same_accession_context_conflicts": 0,
    "target_outcome_rows_read": 0,
    "protected_return_rows_read": 0,
    "protected_holdout_consumed": False,
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _repair_policy_payload() -> dict[str, Any]:
    return {
        "contract_version": XBRL_PIT_IDENTITY_REPAIR_CONTRACT,
        "entry_v1_contract": XBRL_PIT_AUDIT_CONTRACT,
        "entry_v1_fingerprint": XBRL_PIT_AUDIT_FINGERPRINT,
        "entry_v1_status": "AUDIT_FAIL",
        "entry_v1_counts": dict(_V1_EXPECTED_COUNTS),
        "repair_reason": XBRL_PIT_IDENTITY_REPAIR_REASON,
        "identity_source": "Massive:/v3/reference/tickers?cik=...&date=...&active=true&type=CS",
        "identity_rule": (
            "EXACT_CIK_DATE_ACTIVE_COMMON_STOCK_ONLY_STRONG_OR_MEDIUM_EXACTLY_ONE_UNIQUE_INSTRUMENT"
        ),
        "min_companyfacts_success": XBRL_PIT_MIN_COMPANYFACTS_SUCCESS,
        "min_selected_original_filings": XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS,
        "min_sec_metadata_reconciled": XBRL_PIT_MIN_SEC_METADATA_RECONCILED,
        "min_acceptance_decisions": XBRL_PIT_MIN_ACCEPTANCE_DECISIONS,
        "min_unambiguous_identity_mappings": XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS,
        "min_issuers_with_3_unambiguous_mappings": XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS,
        "max_same_accession_context_conflicts": XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS,
        "target_outcome_reads_allowed": False,
        "protected_outcome_reads_allowed": False,
        "provider_writes": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "order_writes": 0,
        "paper_submits": 0,
        "live_writes": 0,
        "automation_writes": 0,
    }


def xbrl_pit_identity_repair_fingerprint() -> str:
    return _sha256_text(_canonical_json(_repair_policy_payload()))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise XBRLPITAuditError(f"required source-only evidence is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise XBRLPITAuditError(f"source-only evidence root is not an object: {path}")
    return value


def _validate_v1_failure(report: dict[str, Any]) -> None:
    if report.get("contract_version") != XBRL_PIT_AUDIT_CONTRACT:
        raise XBRLPITAuditError("local v1 PIT report contract differs from the frozen audit contract")
    if report.get("audit_fingerprint") != XBRL_PIT_AUDIT_FINGERPRINT:
        raise XBRLPITAuditError("local v1 PIT report fingerprint differs from the frozen audit fingerprint")
    if report.get("status") != "AUDIT_FAIL" or report.get("pass") is not False:
        raise XBRLPITAuditError("identity repair requires the preserved target-machine v1 AUDIT_FAIL evidence")
    for field, expected in _V1_EXPECTED_COUNTS.items():
        if report.get(field) != expected:
            raise XBRLPITAuditError(
                f"local v1 PIT failure evidence differs at {field}: expected={expected!r} actual={report.get(field)!r}"
            )
    for field in (
        "provider_writes_performed",
        "broker_reads_performed",
        "broker_writes_performed",
        "order_writes_performed",
        "paper_submits_performed",
        "live_writes_performed",
        "automation_writes_performed",
    ):
        if report.get(field) != 0:
            raise XBRLPITAuditError(f"v1 PIT evidence contains forbidden authority at {field}")
    issuers = report.get("issuer_reports")
    if not isinstance(issuers, list) or len(issuers) != 40:
        raise XBRLPITAuditError("v1 PIT issuer evidence is not exactly 40 issuer reports")


class XBRLPITIdentitySemanticsRepair:
    """Replay only v1 identity decisions under corrected tradable-common-stock semantics.

    The v1 SEC Company Facts, accession, SEC acceptance-time, and Massive response
    caches are preserved.  This repair reads those local source-only artifacts and
    changes only eligibility semantics that v1 proved were incorrect:

    * Massive ``active`` is evaluated on the historical query date, so only
      ``active=true`` is tradable on that decision session.
    * ``market=stocks`` includes preferreds, warrants, rights, units, ETFs, and
      other instruments, so the common-equity strategy universe requires
      ``type=CS``.

    No provider call, market outcome, protected return, or trading authority is
    introduced by this replay.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.provider_root = settings.resolved_path(settings.data.paths.provider)

    def _active_common_stock_rows(self, *, cik: str, as_of_date: date) -> list[dict[str, Any]]:
        path = (
            self.provider_root
            / XBRL_PIT_EVIDENCE_RELATIVE
            / "massive_reference"
            / as_of_date.isoformat()
            / f"{cik}.json"
        )
        value = _load_json(path)
        if value.get("issuer_cik") != cik or value.get("as_of_date") != as_of_date.isoformat():
            raise XBRLPITAuditError(f"cached Massive PIT identity evidence mismatch: {path}")
        rows = value.get("rows")
        if not isinstance(rows, list):
            raise XBRLPITAuditError(f"cached Massive PIT identity rows are invalid: {path}")
        eligible: list[dict[str, Any]] = []
        for raw in rows:
            if not isinstance(raw, dict):
                continue
            try:
                row_cik = _normalize_cik(raw.get("cik"))
            except XBRLPITAuditError:
                continue
            if row_cik != cik:
                continue
            if raw.get("active") is not True:
                continue
            if str(raw.get("type") or "").strip().upper() != "CS":
                continue
            eligible.append(dict(raw))
        return eligible

    def run(self) -> dict[str, Any]:
        if xbrl_pit_identity_repair_fingerprint() != XBRL_PIT_IDENTITY_REPAIR_FINGERPRINT:
            raise XBRLPITAuditError("frozen XBRL PIT identity-repair fingerprint drifted")

        v1_path = self.derived_root / XBRL_PIT_REPORT_RELATIVE
        v1 = _load_json(v1_path)
        _validate_v1_failure(v1)

        unambiguous_identity_mappings = 0
        issuer_mapping_counts: Counter[str] = Counter()
        identity_status_counts: Counter[str] = Counter()
        replayed_identity_decisions = 0
        cache_files_read = 0
        issuer_reports: list[dict[str, Any]] = []

        for issuer in v1["issuer_reports"]:
            if not isinstance(issuer, dict):
                raise XBRLPITAuditError("v1 issuer report contains a non-object row")
            cik = _normalize_cik(issuer.get("issuer_cik"))
            repaired_issuer = {
                "issuer_cik": cik,
                "entity_name": issuer.get("entity_name"),
                "filings": [],
            }
            filings = issuer.get("filings")
            if not isinstance(filings, list):
                raise XBRLPITAuditError(f"v1 issuer report has invalid filing evidence: {cik}")
            for filing in filings:
                if not isinstance(filing, dict):
                    continue
                repaired_filing: dict[str, Any] = {
                    "accession_number": filing.get("accession_number"),
                    "filing_date": filing.get("filing_date"),
                    "form": filing.get("form"),
                    "decision_session": filing.get("decision_session"),
                    "v1_identity_status": filing.get("status"),
                }
                decision_text = str(filing.get("decision_session") or "").strip()
                if not decision_text:
                    repaired_filing["status"] = "NO_V1_DECISION_SESSION"
                    repaired_issuer["filings"].append(repaired_filing)
                    continue
                try:
                    decision = date.fromisoformat(decision_text)
                except ValueError as exc:
                    raise XBRLPITAuditError(
                        f"invalid preserved v1 decision session for {cik}: {decision_text!r}"
                    ) from exc
                rows = self._active_common_stock_rows(cik=cik, as_of_date=decision)
                cache_files_read += 1
                replayed_identity_decisions += 1
                identity = _resolve_identity(rows, issuer_cik=cik, as_of_date=decision)
                repaired_filing["eligible_active_common_stock_rows"] = len(rows)
                repaired_filing["identity"] = identity
                repaired_filing["status"] = identity["status"]
                identity_status_counts[identity["status"]] += 1
                if identity["status"] == "UNAMBIGUOUS_PIT_INSTRUMENT":
                    unambiguous_identity_mappings += 1
                    issuer_mapping_counts[cik] += 1
                repaired_issuer["filings"].append(repaired_filing)
            repaired_issuer["unambiguous_mapping_count"] = issuer_mapping_counts[cik]
            issuer_reports.append(repaired_issuer)

        issuers_with_3_unambiguous = sum(count >= 3 for count in issuer_mapping_counts.values())
        gates = {
            "audit_issuer_sample_exact": v1["audit_issuer_sample_size"] == 40,
            "companyfacts_success_min": v1["companyfacts_success"] >= XBRL_PIT_MIN_COMPANYFACTS_SUCCESS,
            "selected_original_filings_min": (
                v1["selected_original_filings"] >= XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS
            ),
            "sec_metadata_reconciled_min": (
                v1["sec_metadata_reconciled"] >= XBRL_PIT_MIN_SEC_METADATA_RECONCILED
            ),
            "acceptance_decisions_min": v1["acceptance_decisions"] >= XBRL_PIT_MIN_ACCEPTANCE_DECISIONS,
            "unambiguous_identity_mappings_min": (
                unambiguous_identity_mappings >= XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS
            ),
            "issuers_with_3_unambiguous_mappings_min": (
                issuers_with_3_unambiguous >= XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS
            ),
            "same_accession_context_conflicts_max": (
                v1["same_accession_context_conflicts"] <= XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS
            ),
        }
        passed = all(gates.values())
        report = {
            "contract_version": XBRL_PIT_IDENTITY_REPAIR_CONTRACT,
            "audit_fingerprint": xbrl_pit_identity_repair_fingerprint(),
            "status": "AUDIT_PASS" if passed else "AUDIT_FAIL",
            "pass": passed,
            "repair_reason": XBRL_PIT_IDENTITY_REPAIR_REASON,
            "v1_report_path": str(v1_path),
            "v1_report_sha256": sha256_file(v1_path),
            "v1_contract_version": XBRL_PIT_AUDIT_CONTRACT,
            "v1_audit_fingerprint": XBRL_PIT_AUDIT_FINGERPRINT,
            "v1_status": "AUDIT_FAIL",
            "v1_unambiguous_identity_mappings": 139,
            "v1_issuers_with_3_unambiguous_mappings": 28,
            "identity_source": "Massive:/v3/reference/tickers?cik=...&date=...&active=true&type=CS",
            "identity_rule": (
                "EXACT_CIK_DATE_ACTIVE_COMMON_STOCK_ONLY_STRONG_OR_MEDIUM_EXACTLY_ONE_UNIQUE_INSTRUMENT"
            ),
            "replayed_identity_decisions": replayed_identity_decisions,
            "cache_files_read": cache_files_read,
            "provider_reads_performed": 0,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "audit_issuer_sample_size": v1["audit_issuer_sample_size"],
            "companyfacts_success": v1["companyfacts_success"],
            "selected_original_filings": v1["selected_original_filings"],
            "sec_metadata_reconciled": v1["sec_metadata_reconciled"],
            "acceptance_decisions": v1["acceptance_decisions"],
            "same_accession_context_conflicts": v1["same_accession_context_conflicts"],
            "unambiguous_identity_mappings": unambiguous_identity_mappings,
            "issuers_with_3_unambiguous_mappings": issuers_with_3_unambiguous,
            "identity_status_counts": dict(sorted(identity_status_counts.items())),
            "gates": gates,
            "issuer_reports": issuer_reports,
            "next_scientific_action": (
                "If this targeted source-semantics repair passes, preserve v1 AUDIT_FAIL and v2 AUDIT_PASS, "
                "then freeze the finite XBRL fundamental hypothesis/outcome/cost/statistical/protected-evidence "
                "contract before any market outcome is opened."
            ),
        }
        report_path = self.derived_root / XBRL_PIT_IDENTITY_REPAIR_REPORT_RELATIVE
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
