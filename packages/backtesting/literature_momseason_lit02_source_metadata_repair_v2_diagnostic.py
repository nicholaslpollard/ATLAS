from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_lit01_closeout import MomSeasonLIT01Closeout
from .literature_momseason_lit02_source_feasibility import LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT
from .literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
)
from .literature_momseason_lit02_source_metadata_repair_v2 import (
    LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
    LIT02_SOURCE_METADATA_REPAIR_V2_REPORT,
    LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE,
    LIT02_SOURCE_METADATA_REPAIR_V2_STORAGE_ROOT,
)
from .literature_momseason_source import canonical_json


LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_CONTRACT = (
    "lit02-repair-v2-residual-diagnostic-v1-cached-m2-manifests-no-provider-reads"
)
LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_STATUS = (
    "LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_READY"
)
LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_REPORT = "d2.json"

# Accepted exact-target-machine repair-v2 evidence from head
# b51857461f7034591b32079ad126ea9c7ffa7310.
LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT = (
    "6d11081f7acf39783a9c6b2fde8119a1f19f9b8b3b87be0ab3fac59a8381faa2"
)
LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT = (
    "dca474d2d88c09f904c33e33659fbb88e4cdadcecd9d40666971b4482a1c657e"
)
LIT02_ACCEPTED_REPAIR_V2_CASES = 199
LIT02_ACCEPTED_REPAIR_V2_RESOLVED = 96
LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED = 103
LIT02_ACCEPTED_REPAIR_V2_NEWLY_RESOLVED = 60


def _fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _classification_fingerprint(case_results: list[dict[str, object]]) -> str:
    return _fingerprint(
        sorted(
            (
                {
                    "case_id": row.get("case_id"),
                    "resolution_status": row.get("resolution_status"),
                    "path_id": row.get("path_id"),
                    "classification": row.get("classification"),
                    "unresolved_reasons": row.get("unresolved_reasons"),
                }
                for row in case_results
            ),
            key=lambda item: str(item.get("case_id") or ""),
        )
    )


def _require_zero(report: Mapping[str, object], field: str) -> None:
    if int(report.get(field) or 0) != 0:
        raise RuntimeError(f"LIT-02 repair-v2 residual diagnostic safety field is nonzero: {field}")


def _mapping(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


def _candidate_rows(instrument_results: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for instrument in instrument_results:
        evidence_rows = instrument.get("sec_evidence") or []
        if not isinstance(evidence_rows, list):
            continue
        for evidence in evidence_rows:
            if not isinstance(evidence, Mapping):
                continue
            base = {
                "instrument_id": instrument.get("instrument_id"),
                "accession_number": evidence.get("accession_number"),
                "filing_date": evidence.get("filing_date"),
                "form": evidence.get("form"),
                "submission_source_sha256": evidence.get("submission_source_sha256"),
            }
            for kind, field in (
                ("ticker_change", "ticker_change_candidate"),
                ("terminal", "terminal_candidate"),
            ):
                candidate = _mapping(evidence.get(field))
                if candidate is not None:
                    rows.append({**base, "candidate_kind": kind, "candidate": candidate})
    return rows


def _reason_mechanisms(reasons: list[str]) -> set[str]:
    mechanisms: set[str] = set()
    for reason in reasons:
        if reason == "COMPOSITE_FIGI_UNAVAILABLE":
            mechanisms.add("IDENTITY_NO_COMPOSITE_FIGI")
        elif reason == "MASSIVE_TICKER_EVENTS_NOT_FOUND":
            mechanisms.add("MASSIVE_EVENT_SOURCE_NOT_FOUND")
        elif reason == "NO_ADMISSIBLE_OFFICIAL_SEC_EVIDENCE_V2":
            mechanisms.add("SEC_NO_ADMISSIBLE_OFFICIAL_EVIDENCE_V2")
        elif reason == "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED":
            mechanisms.add("SEC_TERMINAL_EFFECTIVE_DATE_UNRESOLVED")
        elif reason == "TERMINAL_TRANSACTION_CONTEXT_UNRESOLVED":
            mechanisms.add("SEC_TERMINAL_CONTEXT_UNRESOLVED")
        elif reason == "MULTIPLE_TERMINAL_CASH_VALUES":
            mechanisms.add("SEC_MULTIPLE_TERMINAL_CASH_VALUES")
        elif reason == "SUCCESSOR_TICKER_IDENTITY_REQUIRED":
            mechanisms.add("SEC_SUCCESSOR_TICKER_IDENTITY_REQUIRED")
        elif reason == "MULTIPLE_SEC_READY_CLASSIFICATIONS_AT_LATEST_EFFECTIVE_DATE":
            mechanisms.add("SEC_LATEST_EFFECTIVE_DATE_CLASSIFICATION_CONFLICT")
        elif reason.startswith(
            "LIT-02 repair-v2 SEC source lookup exceeded bounded candidate filing count:"
        ):
            mechanisms.add("SEC_CANDIDATE_FILING_BOUND_EXCEEDED")
        else:
            mechanisms.add(f"OTHER::{reason}")
    return mechanisms


def _value_profile(candidate: Mapping[str, object]) -> str:
    kinds: list[str] = []
    if _list(candidate.get("cash_values")) or candidate.get("cash_per_share") is not None:
        kinds.append("CASH")
    if _list(candidate.get("share_ratios")) or candidate.get("share_exchange_ratio") is not None:
        kinds.append("SHARES")
    if _list(candidate.get("distribution_values")) or candidate.get("distribution_per_share") is not None:
        kinds.append("DISTRIBUTION")
    return "+".join(kinds) if kinds else "NO_VALUE_PATTERN"


def _case_diagnostic(row: Mapping[str, object]) -> dict[str, object]:
    reasons = sorted({str(value) for value in (row.get("unresolved_reasons") or []) if str(value)})
    instrument_results = [
        dict(item)
        for item in (row.get("instrument_results") or [])
        if isinstance(item, Mapping)
    ]
    candidates = _candidate_rows(instrument_results)

    identities: list[dict[str, object]] = []
    massive_rows: list[dict[str, object]] = []
    sec_filing_keys: set[tuple[str, str, str]] = set()
    sec_forms: Counter[str] = Counter()
    for instrument in instrument_results:
        identity = _mapping(instrument.get("identity")) or {}
        identities.append(
            {
                "instrument_id": instrument.get("instrument_id"),
                "identity_status": identity.get("identity_status"),
                "composite_figi": identity.get("composite_figi"),
                "cik": identity.get("cik"),
                "aliases": identity.get("aliases"),
            }
        )
        massive = _mapping(instrument.get("massive_evidence"))
        if massive is not None:
            massive_rows.append(
                {
                    "instrument_id": instrument.get("instrument_id"),
                    "query_identifier": massive.get("query_identifier"),
                    "provider_status": massive.get("provider_status"),
                    "source_available": massive.get("source_available"),
                    "event_count": massive.get("event_count"),
                }
            )
        evidence_rows = instrument.get("sec_evidence") or []
        if not isinstance(evidence_rows, list):
            continue
        for evidence in evidence_rows:
            if not isinstance(evidence, Mapping):
                continue
            form = str(evidence.get("form") or "UNKNOWN")
            sec_forms[form] += 1
            sec_filing_keys.add(
                (
                    str(instrument.get("instrument_id") or ""),
                    str(evidence.get("accession_number") or ""),
                    str(evidence.get("submission_source_sha256") or ""),
                )
            )

    candidate_status_counts: Counter[str] = Counter()
    candidate_reason_counts: Counter[str] = Counter()
    candidate_kind_counts: Counter[str] = Counter()
    value_profile_counts: Counter[str] = Counter()
    date_unresolved_profiles: Counter[str] = Counter()
    context_unresolved_profiles: Counter[str] = Counter()
    cash_conflict_sets: list[list[float]] = []
    candidate_summaries: list[dict[str, object]] = []

    for item in candidates:
        candidate = dict(item["candidate"])
        kind = str(item.get("candidate_kind") or "UNKNOWN")
        status = str(candidate.get("status") or "UNKNOWN")
        reason = str(candidate.get("reason") or "")
        candidate_kind_counts[kind] += 1
        candidate_status_counts[status] += 1
        if reason:
            candidate_reason_counts[reason] += 1
        profile = _value_profile(candidate)
        value_profile_counts[profile] += 1
        if reason == "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED":
            date_unresolved_profiles[profile] += 1
        if reason == "TERMINAL_TRANSACTION_CONTEXT_UNRESOLVED":
            context_unresolved_profiles[profile] += 1
        if reason == "MULTIPLE_TERMINAL_CASH_VALUES":
            values: list[float] = []
            for value in _list(candidate.get("cash_values")):
                try:
                    values.append(float(value))
                except (TypeError, ValueError):
                    pass
            if values:
                cash_conflict_sets.append(sorted(set(values)))

        event_dates = [str(value) for value in _list(candidate.get("event_dates")) if str(value)]
        all_event_dates = [
            str(value) for value in _list(candidate.get("all_event_dates")) if str(value)
        ]
        candidate_summaries.append(
            {
                "instrument_id": item.get("instrument_id"),
                "accession_number": item.get("accession_number"),
                "filing_date": item.get("filing_date"),
                "form": item.get("form"),
                "candidate_kind": kind,
                "status": status,
                "reason": reason or None,
                "path_id": candidate.get("path_id"),
                "effective_date": candidate.get("effective_date"),
                "event_dates": event_dates,
                "all_event_dates": all_event_dates,
                "value_profile": profile,
                "cash_values": candidate.get("cash_values"),
                "share_ratios": candidate.get("share_ratios"),
                "distribution_values": candidate.get("distribution_values"),
                "successor_ticker": candidate.get("successor_ticker"),
                "new_ticker": candidate.get("new_ticker"),
            }
        )

    figi_available = any(bool(str(item.get("composite_figi") or "").strip()) for item in identities)
    cik_available = any(bool(str(item.get("cik") or "").strip()) for item in identities)
    massive_404 = any(item.get("provider_status") == "HTTP_404_NOT_FOUND" for item in massive_rows)
    candidate_bound = any(
        reason.startswith("LIT-02 repair-v2 SEC source lookup exceeded bounded candidate filing count:")
        for reason in reasons
    )

    if candidate_bound:
        sec_evidence_mode = "SEC_CANDIDATE_FILING_BOUND_EXCEEDED"
    elif len(sec_filing_keys) == 0:
        sec_evidence_mode = "NO_SEC_FILINGS_MATERIALIZED_V2"
    elif len(candidates) == 0:
        sec_evidence_mode = "SEC_FILINGS_NO_CANDIDATE_PATTERN_V2"
    elif any(item["candidate"].get("status") == "READY" for item in candidates):
        sec_evidence_mode = "SEC_READY_CANDIDATE_PRESENT_BUT_CASE_UNRESOLVED_V2"
    else:
        sec_evidence_mode = "SEC_ONLY_INCOMPLETE_OR_CONFLICT_CANDIDATES_V2"

    return {
        "case_id": row.get("case_id"),
        "endpoint_session": row.get("endpoint_session"),
        "historical_ticker": row.get("historical_ticker"),
        "instrument_ids": list(row.get("instrument_ids") or []),
        "unresolved_reasons": reasons,
        "reason_combination": " + ".join(reasons) if reasons else "UNSPECIFIED",
        "mechanisms": sorted(_reason_mechanisms(reasons)),
        "figi_available": figi_available,
        "cik_available": cik_available,
        "massive_404": massive_404,
        "identity": identities,
        "massive_evidence": massive_rows,
        "sec_evidence_mode": sec_evidence_mode,
        "sec_filing_rows": len(sec_filing_keys),
        "sec_form_counts": dict(sorted(sec_forms.items())),
        "sec_candidate_rows": len(candidates),
        "candidate_kind_counts": dict(sorted(candidate_kind_counts.items())),
        "candidate_status_counts": dict(sorted(candidate_status_counts.items())),
        "candidate_reason_counts": dict(sorted(candidate_reason_counts.items())),
        "value_profile_counts": dict(sorted(value_profile_counts.items())),
        "date_unresolved_value_profiles": dict(sorted(date_unresolved_profiles.items())),
        "context_unresolved_value_profiles": dict(sorted(context_unresolved_profiles.items())),
        "cash_conflict_value_sets": cash_conflict_sets,
        "candidate_summaries": candidate_summaries,
    }


def build_repair_v2_residual_diagnostic(
    *,
    source_report: Mapping[str, object],
    case_results: list[dict[str, object]],
) -> dict[str, object]:
    if source_report.get("status") != LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic requires accepted incomplete repair-v2")
    if source_report.get("contract_version") != LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic contract mismatch")
    if source_report.get("source_policy_fingerprint") != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic policy fingerprint mismatch")
    if source_report.get("feasibility_plan_fingerprint") != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic plan fingerprint mismatch")
    if (
        source_report.get("classification_fingerprint")
        != LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT
    ):
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic classification fingerprint mismatch")
    if source_report.get("report_fingerprint") != LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic report fingerprint mismatch")
    if int(source_report.get("feasibility_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_CASES:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic case count mismatch")
    if int(source_report.get("resolved_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_RESOLVED:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic resolved count mismatch")
    if int(source_report.get("unresolved_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic unresolved count mismatch")
    if int(source_report.get("newly_resolved_cases") or 0) != LIT02_ACCEPTED_REPAIR_V2_NEWLY_RESOLVED:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic newly-resolved count mismatch")
    if len(case_results) != LIT02_ACCEPTED_REPAIR_V2_CASES:
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic did not load all 199 manifests")

    case_ids = [str(row.get("case_id") or "") for row in case_results]
    if any(not value for value in case_ids) or len(set(case_ids)) != len(case_ids):
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic manifest IDs missing or duplicated")
    if _classification_fingerprint(case_results) != LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT:
        raise RuntimeError("LIT-02 repair-v2 residual manifests do not reproduce accepted classification")

    for field in (
        "economic_outcome_values_read",
        "new_price_or_return_provider_reads",
        "protected_return_rows_read",
        "broker_reads_performed",
        "broker_writes_performed",
        "order_writes_performed",
        "paper_submits_performed",
        "live_writes_performed",
    ):
        _require_zero(source_report, field)
    if bool(source_report.get("protected_holdout_consumed")):
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic refuses consumed protected holdout")
    if bool(source_report.get("lit02_economic_design_unblocked")):
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic refuses unblocked economic design")
    if bool(source_report.get("phase33_signal_to_trade_authority")):
        raise RuntimeError("LIT-02 repair-v2 residual diagnostic refuses Phase33 authority")

    unresolved = [
        row for row in case_results if str(row.get("resolution_status") or "") != "RESOLVED"
    ]
    if len(unresolved) != LIT02_ACCEPTED_REPAIR_V2_UNRESOLVED:
        raise RuntimeError("LIT-02 repair-v2 residual unresolved manifest count mismatch")

    details = [_case_diagnostic(row) for row in unresolved]
    reason_counts: Counter[str] = Counter()
    reason_combination_counts: Counter[str] = Counter()
    reason_pair_counts: Counter[str] = Counter()
    mechanism_counts: Counter[str] = Counter()
    sec_mode_counts: Counter[str] = Counter()
    sec_form_counts: Counter[str] = Counter()
    candidate_reason_counts: Counter[str] = Counter()
    candidate_status_counts: Counter[str] = Counter()
    date_value_profiles: Counter[str] = Counter()
    context_value_profiles: Counter[str] = Counter()
    endpoint_year_counts: Counter[str] = Counter()
    ticker_counts: Counter[str] = Counter()

    for detail in details:
        reasons = [str(value) for value in detail["unresolved_reasons"]]
        for reason in reasons:
            reason_counts[reason] += 1
        reason_combination_counts[str(detail["reason_combination"])] += 1
        for left, right in combinations(sorted(reasons), 2):
            reason_pair_counts[f"{left} + {right}"] += 1
        for mechanism in detail["mechanisms"]:
            mechanism_counts[str(mechanism)] += 1
        sec_mode_counts[str(detail["sec_evidence_mode"])] += 1
        sec_form_counts.update({str(k): int(v) for k, v in detail["sec_form_counts"].items()})
        candidate_reason_counts.update(
            {str(k): int(v) for k, v in detail["candidate_reason_counts"].items()}
        )
        candidate_status_counts.update(
            {str(k): int(v) for k, v in detail["candidate_status_counts"].items()}
        )
        date_value_profiles.update(
            {str(k): int(v) for k, v in detail["date_unresolved_value_profiles"].items()}
        )
        context_value_profiles.update(
            {str(k): int(v) for k, v in detail["context_unresolved_value_profiles"].items()}
        )
        endpoint = str(detail.get("endpoint_session") or "")
        endpoint_year_counts[endpoint[:4] if len(endpoint) >= 4 else "UNKNOWN"] += 1
        ticker_counts[str(detail.get("historical_ticker") or "")] += 1

    repeated_tickers = [
        {"historical_ticker": ticker, "unresolved_cases": count}
        for ticker, count in sorted(ticker_counts.items(), key=lambda item: (-item[1], item[0]))
        if ticker and count > 1
    ]
    no_figi_with_cik = sum(
        1 for detail in details if not bool(detail["figi_available"]) and bool(detail["cik_available"])
    )
    no_figi_no_cik = sum(
        1 for detail in details if not bool(detail["figi_available"]) and not bool(detail["cik_available"])
    )
    massive_404_with_cik = sum(
        1 for detail in details if bool(detail["massive_404"]) and bool(detail["cik_available"])
    )
    candidate_bound_cases = sum(
        1 for detail in details if detail["sec_evidence_mode"] == "SEC_CANDIDATE_FILING_BOUND_EXCEEDED"
    )
    no_sec_materialized_cases = sum(
        1 for detail in details if detail["sec_evidence_mode"] == "NO_SEC_FILINGS_MATERIALIZED_V2"
    )
    no_candidate_pattern_cases = sum(
        1 for detail in details if detail["sec_evidence_mode"] == "SEC_FILINGS_NO_CANDIDATE_PATTERN_V2"
    )
    incomplete_conflict_cases = sum(
        1
        for detail in details
        if detail["sec_evidence_mode"] == "SEC_ONLY_INCOMPLETE_OR_CONFLICT_CANDIDATES_V2"
    )
    ready_but_unresolved_cases = sum(
        1
        for detail in details
        if detail["sec_evidence_mode"] == "SEC_READY_CANDIDATE_PRESENT_BUT_CASE_UNRESOLVED_V2"
    )
    cash_conflict_cases = sum(1 for detail in details if detail["cash_conflict_value_sets"])

    diagnostic: dict[str, object] = {
        "status": LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_STATUS,
        "contract_version": LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_CONTRACT,
        "repair_v2_contract_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
        "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
        "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
        "repair_v2_classification_fingerprint": LIT02_ACCEPTED_REPAIR_V2_CLASSIFICATION_FINGERPRINT,
        "repair_v2_report_fingerprint": LIT02_ACCEPTED_REPAIR_V2_REPORT_FINGERPRINT,
        "feasibility_cases": len(case_results),
        "resolved_cases": LIT02_ACCEPTED_REPAIR_V2_RESOLVED,
        "newly_resolved_cases": LIT02_ACCEPTED_REPAIR_V2_NEWLY_RESOLVED,
        "unresolved_cases": len(details),
        "source_coverage": LIT02_ACCEPTED_REPAIR_V2_RESOLVED / LIT02_ACCEPTED_REPAIR_V2_CASES,
        "required_source_coverage": 1.0,
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_combination_counts": dict(
            sorted(reason_combination_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "reason_pair_counts": dict(
            sorted(reason_pair_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "mechanism_counts": dict(
            sorted(mechanism_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "sec_evidence_mode_counts": dict(sorted(sec_mode_counts.items())),
        "sec_form_counts": dict(sorted(sec_form_counts.items())),
        "candidate_status_counts": dict(sorted(candidate_status_counts.items())),
        "candidate_reason_counts": dict(
            sorted(candidate_reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "date_unresolved_value_profiles": dict(
            sorted(date_value_profiles.items(), key=lambda item: (-item[1], item[0]))
        ),
        "context_unresolved_value_profiles": dict(
            sorted(context_value_profiles.items(), key=lambda item: (-item[1], item[0]))
        ),
        "identity_gap_cases": {
            "no_figi_but_cik_available": no_figi_with_cik,
            "no_figi_and_no_cik": no_figi_no_cik,
            "massive_404_but_cik_available": massive_404_with_cik,
        },
        "sec_residual_case_modes": {
            "candidate_filing_bound_exceeded": candidate_bound_cases,
            "no_sec_filings_materialized": no_sec_materialized_cases,
            "filings_without_candidate_pattern": no_candidate_pattern_cases,
            "only_incomplete_or_conflict_candidates": incomplete_conflict_cases,
            "ready_candidate_present_but_case_unresolved": ready_but_unresolved_cases,
        },
        "multiple_cash_value_conflict_cases": cash_conflict_cases,
        "unresolved_by_endpoint_year": dict(sorted(endpoint_year_counts.items())),
        "repeated_unresolved_tickers": repeated_tickers,
        "case_details": details,
        "provider_reads_performed": 0,
        "economic_outcome_values_read": 0,
        "new_price_or_return_provider_reads": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "lit02_economic_design_unblocked": False,
        "phase33_signal_to_trade_authority": False,
        "production_authority": False,
        "next_action": (
            "Use this cached residual breakdown to decide whether a prospectively justified general "
            "source mechanism can resolve the remaining 103 cases. Do not weaken the 100% source gate, "
            "do not create ticker-specific exceptions, and do not read price/return outcomes. If the "
            "remaining mechanisms are not source-resolvable under the provider/public-source stack, "
            "close LIT-02 as source-infeasible rather than forcing an economic test."
        ),
    }
    diagnostic["diagnostic_fingerprint"] = _fingerprint(
        {key: value for key, value in diagnostic.items() if key != "case_details"}
    )
    return diagnostic


class MomSeasonLIT02RepairV2ResidualDiagnostic:
    """Zero-provider-read diagnostic over accepted repair-v2 cached case manifests."""

    def __init__(self, settings: AtlasSettings) -> None:
        lit01 = MomSeasonLIT01Closeout(settings)
        self.root = (
            lit01.root
            / LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT
            / LIT02_SOURCE_METADATA_REPAIR_V2_STORAGE_ROOT
        )

    def source_report_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_REPAIR_V2_REPORT

    def report_path(self) -> Path:
        return self.root / LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_REPORT

    def _case_manifest_paths(self) -> list[Path]:
        return sorted(
            path
            for path in self.root.glob("*.json")
            if path.name not in {
                LIT02_SOURCE_METADATA_REPAIR_V2_REPORT,
                LIT02_REPAIR_V2_RESIDUAL_DIAGNOSTIC_REPORT,
            }
        )

    def run(self) -> dict[str, object]:
        source_path = self.source_report_path()
        if not source_path.is_file():
            raise RuntimeError(f"LIT-02 repair-v2 source report is required: {source_path}")
        source_report = json.loads(source_path.read_text(encoding="utf-8"))

        case_results: list[dict[str, object]] = []
        for path in self._case_manifest_paths():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT:
                continue
            if payload.get("source_policy_fingerprint") != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT:
                continue
            if payload.get("feasibility_plan_fingerprint") != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT:
                continue
            result = payload.get("result")
            if isinstance(result, Mapping):
                case_results.append(dict(result))

        report = build_repair_v2_residual_diagnostic(
            source_report=source_report,
            case_results=case_results,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        output = dict(report)
        output["report_path"] = str(self.report_path())
        return output
