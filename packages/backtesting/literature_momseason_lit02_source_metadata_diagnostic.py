from __future__ import annotations

import hashlib
import json
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings

from .literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
    LIT02_SOURCE_METADATA_CONTRACT,
    LIT02_SOURCE_METADATA_INCOMPLETE,
    LIT02_SOURCE_METADATA_REPORT,
    LIT02_SOURCE_METADATA_STORAGE_ROOT,
)
from .literature_momseason_lit02_source_feasibility import (
    LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT,
)
from .literature_momseason_lit01_closeout import MomSeasonLIT01Closeout
from .literature_momseason_source import canonical_json


LIT02_SOURCE_METADATA_DIAGNOSTIC_CONTRACT = (
    "lit02-source-metadata-unresolved-diagnostic-v1-cached-manifests-no-provider-reads"
)
LIT02_SOURCE_METADATA_DIAGNOSTIC_STATUS = (
    "LIT02_SOURCE_METADATA_UNRESOLVED_DIAGNOSTIC_READY"
)
LIT02_SOURCE_METADATA_DIAGNOSTIC_REPORT = "d.json"

LIT02_ACCEPTED_SOURCE_METADATA_CLASSIFICATION_FINGERPRINT = (
    "636fb4bce1d5cd1501c535159e053dd39f5a301f9991b919b00ed2c8cc2e872c"
)
LIT02_ACCEPTED_SOURCE_METADATA_REPORT_FINGERPRINT = (
    "0f739c24013d6490e76c15461a1e5c69149fa09105b94c631f3e0a64fa43b2ca"
)
LIT02_ACCEPTED_SOURCE_METADATA_CASES = 199
LIT02_ACCEPTED_SOURCE_METADATA_RESOLVED = 36
LIT02_ACCEPTED_SOURCE_METADATA_UNRESOLVED = 163


def _fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _require_zero(report: Mapping[str, object], field: str) -> None:
    if int(report.get(field) or 0) != 0:
        raise RuntimeError(f"LIT-02 source diagnostic safety field is nonzero: {field}")


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


def _mapping(value: object) -> dict[str, object] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _candidate_rows(
    instrument_results: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for instrument in instrument_results:
        sec_evidence = instrument.get("sec_evidence") or []
        if not isinstance(sec_evidence, list):
            continue
        for evidence in sec_evidence:
            if not isinstance(evidence, Mapping):
                continue
            base = {
                "instrument_id": instrument.get("instrument_id"),
                "accession_number": evidence.get("accession_number"),
                "filing_date": evidence.get("filing_date"),
                "form": evidence.get("form"),
                "items": evidence.get("items"),
                "submission_source_url": evidence.get("submission_source_url"),
                "submission_source_sha256": evidence.get("submission_source_sha256"),
            }
            for kind, field in (
                ("ticker_change", "ticker_change_candidate"),
                ("terminal", "terminal_candidate"),
            ):
                candidate = _mapping(evidence.get(field))
                if candidate is None:
                    continue
                rows.append({**base, "candidate_kind": kind, "candidate": candidate})
    return rows


def _case_diagnostic(row: Mapping[str, object]) -> dict[str, object]:
    reasons = sorted({str(value) for value in (row.get("unresolved_reasons") or []) if str(value)})
    instrument_results = [
        dict(item)
        for item in (row.get("instrument_results") or [])
        if isinstance(item, Mapping)
    ]
    candidates = _candidate_rows(instrument_results)

    sec_filing_keys: set[tuple[str, str, str]] = set()
    sec_ready = 0
    sec_incomplete = 0
    sec_conflict = 0
    terminal_date_zero = 0
    terminal_date_multiple = 0
    multiple_cash_candidates = 0
    multiple_cash_value_sets: list[list[float]] = []
    candidate_summaries: list[dict[str, object]] = []

    for instrument in instrument_results:
        sec_evidence = instrument.get("sec_evidence") or []
        if isinstance(sec_evidence, list):
            for evidence in sec_evidence:
                if not isinstance(evidence, Mapping):
                    continue
                sec_filing_keys.add(
                    (
                        str(instrument.get("instrument_id") or ""),
                        str(evidence.get("accession_number") or ""),
                        str(evidence.get("submission_source_sha256") or ""),
                    )
                )

    for item in candidates:
        candidate = dict(item["candidate"])
        status = str(candidate.get("status") or "")
        if status == "READY":
            sec_ready += 1
        elif status == "INCOMPLETE":
            sec_incomplete += 1
        elif status == "CONFLICT":
            sec_conflict += 1

        reason = str(candidate.get("reason") or "")
        event_dates = candidate.get("event_dates")
        event_date_list = list(event_dates) if isinstance(event_dates, list) else []
        if reason in {
            "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED",
            "TERMINAL_DISTRIBUTION_EFFECTIVE_DATE_UNRESOLVED",
        }:
            if len(event_date_list) == 0:
                terminal_date_zero += 1
            elif len(event_date_list) > 1:
                terminal_date_multiple += 1

        if reason == "MULTIPLE_TERMINAL_CASH_VALUES":
            multiple_cash_candidates += 1
            values = candidate.get("cash_values")
            if isinstance(values, list):
                normalized: list[float] = []
                for value in values:
                    try:
                        normalized.append(float(value))
                    except (TypeError, ValueError):
                        pass
                if normalized:
                    multiple_cash_value_sets.append(sorted(set(normalized)))

        candidate_summaries.append(
            {
                "instrument_id": item.get("instrument_id"),
                "accession_number": item.get("accession_number"),
                "filing_date": item.get("filing_date"),
                "candidate_kind": item.get("candidate_kind"),
                "status": status,
                "reason": reason or None,
                "path_id": candidate.get("path_id"),
                "event_dates": event_date_list,
                "cash_values": candidate.get("cash_values"),
                "share_ratios": candidate.get("share_ratios"),
                "values": candidate.get("values"),
                "old_ticker": candidate.get("old_ticker"),
                "new_ticker": candidate.get("new_ticker"),
                "successor_ticker": candidate.get("successor_ticker"),
            }
        )

    identities: list[dict[str, object]] = []
    massive_rows: list[dict[str, object]] = []
    for instrument in instrument_results:
        identity = _mapping(instrument.get("identity")) or {}
        massive = _mapping(instrument.get("massive_evidence"))
        identities.append(
            {
                "instrument_id": instrument.get("instrument_id"),
                "identity_status": identity.get("identity_status"),
                "composite_figi": identity.get("composite_figi"),
                "cik": identity.get("cik"),
                "aliases": identity.get("aliases"),
                "safe_identity_rows": identity.get("safe_identity_rows"),
                "nearby_identity_rows": identity.get("nearby_identity_rows"),
                "identity_conflicts": identity.get("identity_conflicts"),
            }
        )
        if massive is not None:
            massive_rows.append(
                {
                    "instrument_id": instrument.get("instrument_id"),
                    "query_identifier": massive.get("query_identifier"),
                    "provider_status": massive.get("provider_status"),
                    "source_available": massive.get("source_available"),
                    "event_count": massive.get("event_count"),
                    "candidate": massive.get("candidate"),
                }
            )

    figi_available = any(bool(str(item.get("composite_figi") or "").strip()) for item in identities)
    cik_available = any(bool(str(item.get("cik") or "").strip()) for item in identities)
    massive_404 = any(item.get("provider_status") == "HTTP_404_NOT_FOUND" for item in massive_rows)

    if len(sec_filing_keys) == 0:
        sec_evidence_mode = "NO_SEC_FILINGS_MATERIALIZED"
    elif len(candidates) == 0:
        sec_evidence_mode = "SEC_FILINGS_NO_CANDIDATE_PATTERN"
    elif sec_ready > 0:
        sec_evidence_mode = "SEC_READY_CANDIDATE_PRESENT_BUT_CASE_UNRESOLVED"
    else:
        sec_evidence_mode = "SEC_ONLY_INCOMPLETE_OR_CONFLICT_CANDIDATES"

    mechanisms: set[str] = set()
    if "COMPOSITE_FIGI_UNAVAILABLE" in reasons:
        mechanisms.add("IDENTITY_NO_COMPOSITE_FIGI")
    if "MASSIVE_TICKER_EVENTS_NOT_FOUND" in reasons:
        mechanisms.add("MASSIVE_EVENT_SOURCE_NOT_FOUND")
    if "NO_ADMISSIBLE_SEC_8K_EVIDENCE" in reasons:
        mechanisms.add("SEC_NO_ADMISSIBLE_8K_EVIDENCE")
    if "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED" in reasons:
        if terminal_date_zero:
            mechanisms.add("SEC_TERMINAL_DATE_ZERO_MATCHES")
        if terminal_date_multiple:
            mechanisms.add("SEC_TERMINAL_DATE_MULTIPLE_MATCHES")
        if not terminal_date_zero and not terminal_date_multiple:
            mechanisms.add("SEC_TERMINAL_DATE_UNRESOLVED_UNCATEGORIZED")
    if "MULTIPLE_TERMINAL_CASH_VALUES" in reasons:
        mechanisms.add("SEC_MULTIPLE_CASH_VALUES")
    if "MULTIPLE_SEC_READY_CLASSIFICATIONS" in reasons:
        mechanisms.add("SEC_MULTIPLE_READY_CLASSIFICATIONS")
    if "SUCCESSOR_TICKER_IDENTITY_REQUIRED" in reasons:
        mechanisms.add("SUCCESSOR_TICKER_IDENTITY_REQUIRED")
    if "SUCCESSOR_TICKER_OVERVIEW_NOT_FOUND" in reasons:
        mechanisms.add("SUCCESSOR_TICKER_OVERVIEW_NOT_FOUND")

    return {
        "case_id": row.get("case_id"),
        "endpoint_session": row.get("endpoint_session"),
        "historical_ticker": row.get("historical_ticker"),
        "instrument_ids": list(row.get("instrument_ids") or []),
        "unresolved_reasons": reasons,
        "reason_combination": " + ".join(reasons) if reasons else "UNSPECIFIED",
        "mechanisms": sorted(mechanisms),
        "identity": identities,
        "figi_available": figi_available,
        "cik_available": cik_available,
        "massive_404": massive_404,
        "massive_evidence": massive_rows,
        "sec_evidence_mode": sec_evidence_mode,
        "sec_filing_rows": len(sec_filing_keys),
        "sec_candidate_rows": len(candidates),
        "sec_ready_candidates": sec_ready,
        "sec_incomplete_candidates": sec_incomplete,
        "sec_conflict_candidates": sec_conflict,
        "terminal_effective_date_zero_match_candidates": terminal_date_zero,
        "terminal_effective_date_multiple_match_candidates": terminal_date_multiple,
        "multiple_cash_value_candidates": multiple_cash_candidates,
        "multiple_cash_value_sets": multiple_cash_value_sets,
        "candidate_summaries": candidate_summaries,
    }


def build_source_metadata_diagnostic(
    *,
    source_report: Mapping[str, object],
    case_results: list[dict[str, object]],
) -> dict[str, object]:
    if source_report.get("status") != LIT02_SOURCE_METADATA_INCOMPLETE:
        raise RuntimeError("LIT-02 source diagnostic requires the accepted incomplete source census")
    if source_report.get("contract_version") != LIT02_SOURCE_METADATA_CONTRACT:
        raise RuntimeError("LIT-02 source diagnostic source contract mismatch")
    if (
        str(source_report.get("source_policy_fingerprint") or "")
        != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
    ):
        raise RuntimeError("LIT-02 source diagnostic policy fingerprint mismatch")
    if (
        str(source_report.get("feasibility_plan_fingerprint") or "")
        != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
    ):
        raise RuntimeError("LIT-02 source diagnostic plan fingerprint mismatch")
    if (
        str(source_report.get("classification_fingerprint") or "")
        != LIT02_ACCEPTED_SOURCE_METADATA_CLASSIFICATION_FINGERPRINT
    ):
        raise RuntimeError("LIT-02 source diagnostic classification fingerprint mismatch")
    if (
        str(source_report.get("report_fingerprint") or "")
        != LIT02_ACCEPTED_SOURCE_METADATA_REPORT_FINGERPRINT
    ):
        raise RuntimeError("LIT-02 source diagnostic report fingerprint mismatch")

    if int(source_report.get("feasibility_cases") or 0) != LIT02_ACCEPTED_SOURCE_METADATA_CASES:
        raise RuntimeError("LIT-02 source diagnostic case count mismatch")
    if int(source_report.get("resolved_cases") or 0) != LIT02_ACCEPTED_SOURCE_METADATA_RESOLVED:
        raise RuntimeError("LIT-02 source diagnostic resolved count mismatch")
    if int(source_report.get("unresolved_cases") or 0) != LIT02_ACCEPTED_SOURCE_METADATA_UNRESOLVED:
        raise RuntimeError("LIT-02 source diagnostic unresolved count mismatch")
    if len(case_results) != LIT02_ACCEPTED_SOURCE_METADATA_CASES:
        raise RuntimeError("LIT-02 source diagnostic did not load all 199 case manifests")

    case_ids = [str(row.get("case_id") or "") for row in case_results]
    if any(not value for value in case_ids) or len(set(case_ids)) != len(case_ids):
        raise RuntimeError("LIT-02 source diagnostic case manifest IDs are missing or duplicated")
    observed_classification = _classification_fingerprint(case_results)
    if observed_classification != LIT02_ACCEPTED_SOURCE_METADATA_CLASSIFICATION_FINGERPRINT:
        raise RuntimeError("LIT-02 source diagnostic case manifests do not reproduce accepted classification")

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
        raise RuntimeError("LIT-02 source diagnostic refuses a consumed protected holdout")
    if bool(source_report.get("lit02_economic_design_unblocked")):
        raise RuntimeError("LIT-02 source diagnostic refuses an already-unblocked economic design")

    unresolved = [
        row for row in case_results if str(row.get("resolution_status") or "") != "RESOLVED"
    ]
    if len(unresolved) != LIT02_ACCEPTED_SOURCE_METADATA_UNRESOLVED:
        raise RuntimeError("LIT-02 source diagnostic unresolved manifest count mismatch")

    details = [_case_diagnostic(row) for row in unresolved]
    reason_counts: Counter[str] = Counter()
    reason_combo_counts: Counter[str] = Counter()
    mechanism_counts: Counter[str] = Counter()
    sec_mode_counts: Counter[str] = Counter()
    reason_pairs: Counter[str] = Counter()
    endpoint_year_counts: Counter[str] = Counter()
    ticker_counts: Counter[str] = Counter()

    for detail in details:
        reasons = [str(value) for value in detail["unresolved_reasons"]]
        for reason in reasons:
            reason_counts[reason] += 1
        reason_combo_counts[str(detail["reason_combination"])] += 1
        for mechanism in detail["mechanisms"]:
            mechanism_counts[str(mechanism)] += 1
        sec_mode_counts[str(detail["sec_evidence_mode"])] += 1
        for left, right in combinations(sorted(reasons), 2):
            reason_pairs[f"{left} + {right}"] += 1
        endpoint = str(detail.get("endpoint_session") or "")
        endpoint_year_counts[endpoint[:4] if len(endpoint) >= 4 else "UNKNOWN"] += 1
        ticker_counts[str(detail.get("historical_ticker") or "")] += 1

    repeated_tickers = [
        {"historical_ticker": ticker, "unresolved_cases": count}
        for ticker, count in sorted(ticker_counts.items(), key=lambda item: (-item[1], item[0]))
        if ticker and count > 1
    ]

    date_zero_cases = sum(
        1 for detail in details if int(detail["terminal_effective_date_zero_match_candidates"]) > 0
    )
    date_multiple_cases = sum(
        1 for detail in details if int(detail["terminal_effective_date_multiple_match_candidates"]) > 0
    )
    cash_conflict_cases = sum(
        1 for detail in details if int(detail["multiple_cash_value_candidates"]) > 0
    )
    no_figi_with_cik = sum(
        1 for detail in details if not bool(detail["figi_available"]) and bool(detail["cik_available"])
    )
    no_figi_no_cik = sum(
        1 for detail in details if not bool(detail["figi_available"]) and not bool(detail["cik_available"])
    )
    massive_404_with_cik = sum(
        1 for detail in details if bool(detail["massive_404"]) and bool(detail["cik_available"])
    )

    diagnostic: dict[str, object] = {
        "status": LIT02_SOURCE_METADATA_DIAGNOSTIC_STATUS,
        "contract_version": LIT02_SOURCE_METADATA_DIAGNOSTIC_CONTRACT,
        "source_metadata_contract_version": LIT02_SOURCE_METADATA_CONTRACT,
        "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
        "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
        "source_classification_fingerprint": LIT02_ACCEPTED_SOURCE_METADATA_CLASSIFICATION_FINGERPRINT,
        "source_report_fingerprint": LIT02_ACCEPTED_SOURCE_METADATA_REPORT_FINGERPRINT,
        "feasibility_cases": len(case_results),
        "resolved_cases": LIT02_ACCEPTED_SOURCE_METADATA_RESOLVED,
        "unresolved_cases": len(details),
        "reason_counts": dict(sorted(reason_counts.items())),
        "reason_combination_counts": dict(
            sorted(reason_combo_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "reason_pair_counts": dict(
            sorted(reason_pairs.items(), key=lambda item: (-item[1], item[0]))
        ),
        "mechanism_counts": dict(
            sorted(mechanism_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "sec_evidence_mode_counts": dict(sorted(sec_mode_counts.items())),
        "terminal_effective_date_cases": {
            "zero_explicit_event_date_match": date_zero_cases,
            "multiple_explicit_event_date_matches": date_multiple_cases,
        },
        "multiple_cash_value_conflict_cases": cash_conflict_cases,
        "identity_gap_cases": {
            "no_figi_but_cik_available": no_figi_with_cik,
            "no_figi_and_no_cik": no_figi_no_cik,
            "massive_404_but_cik_available": massive_404_with_cik,
        },
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
        "phase33_signal_to_trade_authority": False,
        "lit02_economic_design_unblocked": False,
        "next_action": (
            "Use the cached source-only mechanism breakdown to define the smallest outcome-independent "
            "metadata-source/parser repairs. Preserve the 100% coverage gate and do not read price/return outcomes."
        ),
    }
    diagnostic["diagnostic_fingerprint"] = _fingerprint(
        {
            key: value
            for key, value in diagnostic.items()
            if key != "case_details"
        }
    )
    return diagnostic


class MomSeasonLIT02SourceMetadataDiagnostic:
    """Read-only diagnostic over the accepted 199 cached source-metadata case manifests."""

    def __init__(self, settings: AtlasSettings) -> None:
        lit01 = MomSeasonLIT01Closeout(settings)
        self.root = (
            lit01.root
            / LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT
            / LIT02_SOURCE_METADATA_STORAGE_ROOT
        )

    def source_report_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_REPORT

    def report_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_DIAGNOSTIC_REPORT

    def _case_manifest_paths(self) -> list[Path]:
        return sorted(
            path
            for path in self.root.glob("*.json")
            if path.name not in {"i.json", "r.json", LIT02_SOURCE_METADATA_DIAGNOSTIC_REPORT}
        )

    def run(self) -> dict[str, object]:
        source_path = self.source_report_path()
        if not source_path.is_file():
            raise RuntimeError(f"LIT-02 source metadata report is required: {source_path}")
        source_report = json.loads(source_path.read_text(encoding="utf-8"))

        case_results: list[dict[str, object]] = []
        for path in self._case_manifest_paths():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != LIT02_SOURCE_METADATA_CONTRACT:
                continue
            if (
                payload.get("source_policy_fingerprint")
                != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
                or payload.get("feasibility_plan_fingerprint")
                != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
            ):
                continue
            result = payload.get("result")
            if isinstance(result, Mapping):
                case_results.append(dict(result))

        report = build_source_metadata_diagnostic(
            source_report=source_report,
            case_results=case_results,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        result = dict(report)
        result["report_path"] = str(self.report_path())
        return result
