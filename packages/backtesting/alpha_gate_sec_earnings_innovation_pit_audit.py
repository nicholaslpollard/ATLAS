from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import exchange_calendars as xcals
import pandas as pd

from packages.backtesting.alpha_gate_sec_earnings_innovation_feasibility import (
    EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS,
    EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
    EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
    EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS,
    EARNINGS_INNOVATION_MECHANISM,
    EARNINGS_INNOVATION_REPORT_RELATIVE,
    EARNINGS_INNOVATION_SAMPLE_SIZE,
    EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS,
    _duration_days,
    _extract_eps_entries,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_edgar import (
    SECEDGARClient,
    sec_company_submissions_url,
    sec_submission_shard_url,
)
from packages.providers.sec_xbrl import SECCompanyFactsDocument, SECXBRLCompanyFactsClient


EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT = (
    "alpha-gate-sec-earnings-innovation-pit-audit-v1-original-accession-acceptance-source-only-no-market-outcomes"
)
EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT = (
    "423528f7518273f91432ee0cfaf0f43fec8cf33fa11a59f40af5523b4f9d6baa"
)
EARNINGS_INNOVATION_PIT_PARENT_TARGET_HEAD = "48720381a6cdf3963d75b023e3c1176ebbf674de"
EARNINGS_INNOVATION_PIT_ORIGINAL_ACCESSION_RULE = (
    "EARLIEST_NON_AMENDMENT_10Q_OR_10K_PER_ISSUER_PERIOD_END_WITH_UNAMBIGUOUS_DIRECT_QUARTER_CONTEXT_AND_VALUE"
)
EARNINGS_INNOVATION_PIT_AMENDMENT_RULE = "10Q_A_AND_10K_A_CHRONOLOGY_ONLY_NEVER_PREDICTOR_READY"
EARNINGS_INNOVATION_PIT_ACCEPTANCE_SOURCE = (
    "OFFICIAL_SEC_SUBMISSIONS_ACCEPTANCE_DATETIME_ROOT_OR_DECLARED_HISTORICAL_SHARD"
)
EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE = (
    "FIRST_XNYS_REGULAR_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE"
)
EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM = "NOT_ESTABLISHED_PIT_PERIODIC_FILING_ONLY"
EARNINGS_INNOVATION_PIT_MIN_COMPANYFACTS_HASH_MATCHES = 300
EARNINGS_INNOVATION_PIT_MIN_SUBMISSIONS_ROOT_SUCCESS = 295
EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS = 4000
EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS = 160
EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS = 130
EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION = 0.95
EARNINGS_INNOVATION_PIT_MIN_CALENDAR_YEARS_OBSERVED = 8
EARNINGS_INNOVATION_PIT_MAX_PERIOD_CONTEXT_AMBIGUITIES = 0
EARNINGS_INNOVATION_PIT_MAX_ACCESSION_METADATA_CONTRADICTIONS = 0
EARNINGS_INNOVATION_PIT_MAX_ACCEPTANCE_NOT_AFTER_PERIOD_END = 0
EARNINGS_INNOVATION_PIT_MAX_DECISION_SESSION_ERRORS = 0
EARNINGS_INNOVATION_PIT_ALPHA_HYPOTHESES_FROZEN = False
EARNINGS_INNOVATION_PIT_TARGET_OUTCOME_READS_ALLOWED = False
EARNINGS_INNOVATION_PIT_PROTECTED_OUTCOME_READS_ALLOWED = False
EARNINGS_INNOVATION_PIT_PROVIDER_WRITES = 0
EARNINGS_INNOVATION_PIT_BROKER_READS = 0
EARNINGS_INNOVATION_PIT_BROKER_WRITES = 0
EARNINGS_INNOVATION_PIT_ORDER_WRITES = 0
EARNINGS_INNOVATION_PIT_PAPER_SUBMITS = 0
EARNINGS_INNOVATION_PIT_LIVE_WRITES = 0
EARNINGS_INNOVATION_PIT_AUTOMATION_WRITES = 0
EARNINGS_INNOVATION_PIT_AUTOMATIC_BROKER_FAILOVER = False
EARNINGS_INNOVATION_PIT_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False

EARNINGS_INNOVATION_PIT_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v1/source_audit.json"
)
EARNINGS_INNOVATION_PIT_ROWS_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_earnings_innovation_pit_audit_v1/pit_rows.jsonl"
)

_PARENT_FIXED_EVIDENCE: dict[str, object] = {
    "source_inventory_unique_ciks": 4400,
    "sample_size": 300,
    "successful_documents": 300,
    "failed_documents": 0,
    "eps_documents": 265,
    "history_ready_issuers": 204,
    "sue_baseline_ready_issuers": 170,
    "direct_quarter_observations": 5905,
    "calendar_years_observed": list(range(2013, 2027)),
    "same_accession_context_conflicts": 0,
}


class EarningsInnovationPITAuditError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
        "parent_contract": EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
        "parent_fingerprint": EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
        "parent_target_head": EARNINGS_INNOVATION_PIT_PARENT_TARGET_HEAD,
        "mechanism": EARNINGS_INNOVATION_MECHANISM,
        "parent_fixed_evidence": _PARENT_FIXED_EVIDENCE,
        "original_accession_rule": EARNINGS_INNOVATION_PIT_ORIGINAL_ACCESSION_RULE,
        "amendment_rule": EARNINGS_INNOVATION_PIT_AMENDMENT_RULE,
        "acceptance_source": EARNINGS_INNOVATION_PIT_ACCEPTANCE_SOURCE,
        "decision_session_rule": EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE,
        "min_companyfacts_hash_matches": EARNINGS_INNOVATION_PIT_MIN_COMPANYFACTS_HASH_MATCHES,
        "min_submissions_root_success": EARNINGS_INNOVATION_PIT_MIN_SUBMISSIONS_ROOT_SUCCESS,
        "min_original_accession_audited_observations": EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS,
        "min_audited_history_ready_issuers": EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS,
        "min_audited_sue_baseline_ready_issuers": EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS,
        "min_acceptance_proven_fraction": EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION,
        "min_calendar_years_observed": EARNINGS_INNOVATION_PIT_MIN_CALENDAR_YEARS_OBSERVED,
        "max_period_context_ambiguities": EARNINGS_INNOVATION_PIT_MAX_PERIOD_CONTEXT_AMBIGUITIES,
        "max_accession_metadata_contradictions": EARNINGS_INNOVATION_PIT_MAX_ACCESSION_METADATA_CONTRADICTIONS,
        "max_acceptance_not_after_period_end": EARNINGS_INNOVATION_PIT_MAX_ACCEPTANCE_NOT_AFTER_PERIOD_END,
        "max_decision_session_errors": EARNINGS_INNOVATION_PIT_MAX_DECISION_SESSION_ERRORS,
        "alpha_hypotheses_frozen": EARNINGS_INNOVATION_PIT_ALPHA_HYPOTHESES_FROZEN,
        "announcement_timing_claim": EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM,
        "target_outcome_reads_allowed": EARNINGS_INNOVATION_PIT_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": EARNINGS_INNOVATION_PIT_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_writes": EARNINGS_INNOVATION_PIT_PROVIDER_WRITES,
        "broker_reads": EARNINGS_INNOVATION_PIT_BROKER_READS,
        "broker_writes": EARNINGS_INNOVATION_PIT_BROKER_WRITES,
        "order_writes": EARNINGS_INNOVATION_PIT_ORDER_WRITES,
        "paper_submits": EARNINGS_INNOVATION_PIT_PAPER_SUBMITS,
        "live_writes": EARNINGS_INNOVATION_PIT_LIVE_WRITES,
        "automation_writes": EARNINGS_INNOVATION_PIT_AUTOMATION_WRITES,
        "automatic_broker_failover": EARNINGS_INNOVATION_PIT_AUTOMATIC_BROKER_FAILOVER,
        "phase33_signal_to_trade_authority": EARNINGS_INNOVATION_PIT_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    }


def earnings_innovation_pit_audit_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _load_parent_report(path: Path) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise EarningsInnovationPITAuditError(f"accepted earnings-innovation feasibility report is missing: {path}")
    raw = path.read_bytes()
    report_sha = hashlib.sha256(raw).hexdigest()
    try:
        report = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EarningsInnovationPITAuditError("accepted feasibility report is not valid UTF-8 JSON") from exc
    if not isinstance(report, dict):
        raise EarningsInnovationPITAuditError("accepted feasibility report root is not an object")
    return report, report_sha


def _parent_report_exact(report: dict[str, Any]) -> bool:
    if report.get("contract_version") != EARNINGS_INNOVATION_FEASIBILITY_CONTRACT:
        return False
    if report.get("feasibility_fingerprint") != EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT:
        return False
    if report.get("status") != "FEASIBILITY_PASS" or report.get("pass") is not True:
        return False
    for key, expected in _PARENT_FIXED_EVIDENCE.items():
        if report.get(key) != expected:
            return False
    if report.get("target_outcome_rows_read") != 0:
        return False
    if report.get("protected_return_rows_read") != 0 or report.get("protected_holdout_consumed") is not False:
        return False
    sample = report.get("sample_ciks")
    return isinstance(sample, list) and len(sample) == EARNINGS_INNOVATION_SAMPLE_SIZE and len(set(sample)) == EARNINGS_INNOVATION_SAMPLE_SIZE


def _direct_rows(document: SECCompanyFactsDocument) -> tuple[dict[str, Any], ...]:
    lower, upper = EARNINGS_INNOVATION_DIRECT_QUARTER_DURATION_DAYS
    return tuple(
        row for row in _extract_eps_entries(document)
        if (days := _duration_days(row)) is not None and lower <= days <= upper
    )


def _as_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _select_original_period_rows(rows: Iterable[dict[str, Any]]) -> tuple[tuple[dict[str, Any], ...], int]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("end") or "")].append(dict(row))
    selected: list[dict[str, Any]] = []
    ambiguities = 0
    for period_end, values in sorted(grouped.items()):
        if not period_end:
            ambiguities += 1
            continue
        ordered = sorted(values, key=lambda r: (str(r.get("filed") or ""), str(r.get("accn") or "")))
        first_key = (str(ordered[0].get("filed") or ""), str(ordered[0].get("accn") or ""))
        earliest = [r for r in ordered if (str(r.get("filed") or ""), str(r.get("accn") or "")) == first_key]
        semantics = {
            (str(r.get("start") or ""), str(r.get("end") or ""), _as_float(r.get("val")))
            for r in earliest
        }
        if len(semantics) != 1 or None in {item[2] for item in semantics}:
            ambiguities += 1
            continue
        selected.append(sorted(earliest, key=lambda r: _canonical_json(r))[0])
    return tuple(selected), ambiguities


def _columnar_rows(block: object) -> tuple[dict[str, object], ...]:
    if not isinstance(block, dict):
        return ()
    accessions = block.get("accessionNumber")
    if not isinstance(accessions, list):
        return ()
    fields = ("accessionNumber", "filingDate", "acceptanceDateTime", "form", "primaryDocument")
    rows: list[dict[str, object]] = []
    for index in range(len(accessions)):
        row: dict[str, object] = {}
        for field in fields:
            values = block.get(field)
            row[field] = values[index] if isinstance(values, list) and index < len(values) else ""
        rows.append(row)
    return tuple(rows)


def _payload_rows(payload: dict[str, Any]) -> tuple[dict[str, object], ...]:
    direct = _columnar_rows(payload)
    if direct:
        return direct
    filings = payload.get("filings")
    if isinstance(filings, dict):
        return _columnar_rows(filings.get("recent"))
    return ()


def _parse_acceptance(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 14 and text.isdigit():
        try:
            return datetime.strptime(text, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("America/New_York"))
        except ValueError:
            return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _first_xnys_open_strictly_after(acceptance: datetime) -> tuple[str, str]:
    if acceptance.tzinfo is None:
        raise EarningsInnovationPITAuditError("SEC acceptance timestamp must be timezone-aware")
    instant = pd.Timestamp(acceptance).tz_convert("UTC")
    calendar = xcals.get_calendar("XNYS")
    start = (instant - pd.Timedelta(days=2)).date().isoformat()
    end = (instant + pd.Timedelta(days=14)).date().isoformat()
    for session in calendar.sessions_in_range(start, end):
        session_open = calendar.session_open(session)
        if session_open > instant:
            return session.date().isoformat(), session_open.isoformat()
    raise EarningsInnovationPITAuditError("could not resolve next XNYS regular-session open")


def _declared_shards_for_dates(files: object, dates: set[str]) -> tuple[str, ...]:
    if not isinstance(files, list) or not dates:
        return ()
    requested = {date.fromisoformat(value) for value in dates}
    exact: set[str] = set()
    adjacent: set[str] = set()
    for item in files:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        try:
            start = date.fromisoformat(str(item.get("filingFrom") or ""))
            end = date.fromisoformat(str(item.get("filingTo") or ""))
        except ValueError:
            continue
        if start > end or not name:
            continue
        for requested_date in requested:
            if start <= requested_date <= end:
                exact.add(name)
            elif min(abs((requested_date - start).days), abs((requested_date - end).days)) == 1:
                adjacent.add(name)
    return tuple(sorted(exact | adjacent))


def _submission_metadata_for_targets(
    client: SECEDGARClient,
    *,
    cik: str,
    targets: tuple[dict[str, Any], ...],
) -> tuple[dict[str, dict[str, object]], int]:
    root_url = sec_company_submissions_url(cik=cik)
    root, _ = client.get_json(root_url)
    filings = root.get("filings")
    recent = filings.get("recent") if isinstance(filings, dict) else None
    by_accession = {
        str(row.get("accessionNumber") or "").strip(): row
        for row in _columnar_rows(recent)
        if str(row.get("accessionNumber") or "").strip()
    }
    unresolved = [row for row in targets if str(row.get("accn") or "") not in by_accession]
    shard_reads = 0
    if unresolved and isinstance(filings, dict):
        dates = {str(row.get("filed") or "") for row in unresolved if row.get("filed")}
        for shard_name in _declared_shards_for_dates(filings.get("files"), dates):
            shard, _ = client.get_json(sec_submission_shard_url(shard_name))
            shard_reads += 1
            for row in _payload_rows(shard):
                accession = str(row.get("accessionNumber") or "").strip()
                if accession:
                    by_accession.setdefault(accession, row)
    wanted = {str(row.get("accn") or "") for row in targets}
    return {accn: row for accn, row in by_accession.items() if accn in wanted}, shard_reads


class SECEarningsInnovationPITAudit:
    """Source-only original-accession and SEC acceptance chronology audit."""

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
        if earnings_innovation_pit_audit_fingerprint() != EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT:
            raise EarningsInnovationPITAuditError("frozen earnings-innovation PIT audit fingerprint drifted")
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        parent_path = derived_root / EARNINGS_INNOVATION_REPORT_RELATIVE
        parent, parent_report_sha256 = _load_parent_report(parent_path)
        if not _parent_report_exact(parent):
            raise EarningsInnovationPITAuditError("accepted feasibility parent lineage does not match frozen Gate0 evidence")

        sample_ciks = tuple(str(value) for value in parent["sample_ciks"])
        expected_hashes = {
            str(row.get("issuer_cik")): str(row.get("source_sha256"))
            for row in parent.get("issuer_reports", []) if isinstance(row, dict)
        }
        companyfacts_hash_matches = 0
        recomputed_direct_observations = 0
        recomputed_history_ready = 0
        recomputed_sue_ready = 0
        candidate_by_cik: dict[str, tuple[dict[str, Any], ...]] = {}
        period_context_ambiguities = 0
        companyfacts_failures: list[dict[str, str]] = []

        for index, cik in enumerate(sample_ciks, start=1):
            try:
                document = self.companyfacts_client.company_facts(cik=cik)
                if document.source_sha256 == expected_hashes.get(cik):
                    companyfacts_hash_matches += 1
                rows = _direct_rows(document)
                unique_ends = {str(row["end"]) for row in rows}
                recomputed_direct_observations += len(unique_ends)
                recomputed_history_ready += int(len(unique_ends) >= EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS)
                recomputed_sue_ready += int(len(unique_ends) >= EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS)
                selected, ambiguities = _select_original_period_rows(rows)
                candidate_by_cik[cik] = selected
                period_context_ambiguities += ambiguities
            except Exception as exc:
                companyfacts_failures.append({"issuer_cik": cik, "error_type": type(exc).__name__, "error": str(exc)})
                candidate_by_cik[cik] = ()
            if index == 1 or index % 25 == 0 or index == len(sample_ciks):
                print(f"SEC earnings-innovation PIT parent recheck: {index}/{len(sample_ciks)} hash_matches={companyfacts_hash_matches} failures={len(companyfacts_failures)}")

        parent_semantics_reconciled = (
            recomputed_direct_observations == int(_PARENT_FIXED_EVIDENCE["direct_quarter_observations"])
            and recomputed_history_ready == int(_PARENT_FIXED_EVIDENCE["history_ready_issuers"])
            and recomputed_sue_ready == int(_PARENT_FIXED_EVIDENCE["sue_baseline_ready_issuers"])
        )

        original_candidates = sum(len(rows) for rows in candidate_by_cik.values())
        submissions_root_success = 0
        submissions_root_failures: list[dict[str, str]] = []
        submissions_shard_reads = 0
        metadata_contradictions = 0
        acceptance_not_after_period_end = 0
        decision_session_errors = 0
        audited_rows: list[dict[str, Any]] = []
        missing_accession_metadata = 0

        for index, cik in enumerate(sample_ciks, start=1):
            targets = candidate_by_cik[cik]
            try:
                metadata, shard_reads = _submission_metadata_for_targets(self.submissions_client, cik=cik, targets=targets)
                submissions_root_success += 1
                submissions_shard_reads += shard_reads
            except Exception as exc:
                submissions_root_failures.append({"issuer_cik": cik, "error_type": type(exc).__name__, "error": str(exc)})
                metadata = {}

            for row in targets:
                accession = str(row.get("accn") or "")
                source = metadata.get(accession)
                if source is None:
                    missing_accession_metadata += 1
                    continue
                source_form = str(source.get("form") or "").strip()
                source_filed = str(source.get("filingDate") or "").strip()
                if source_form != str(row.get("form") or "") or source_filed != str(row.get("filed") or ""):
                    metadata_contradictions += 1
                    continue
                acceptance = _parse_acceptance(source.get("acceptanceDateTime"))
                if acceptance is None:
                    missing_accession_metadata += 1
                    continue
                try:
                    period_end = date.fromisoformat(str(row.get("end") or ""))
                except ValueError:
                    metadata_contradictions += 1
                    continue
                if acceptance.date() <= period_end:
                    acceptance_not_after_period_end += 1
                    continue
                try:
                    decision_session, decision_open = _first_xnys_open_strictly_after(acceptance)
                except Exception:
                    decision_session_errors += 1
                    continue
                audited_rows.append({
                    "issuer_cik": cik,
                    "start": row.get("start"),
                    "end": row.get("end"),
                    "filed": row.get("filed"),
                    "form": row.get("form"),
                    "accession_number": accession,
                    "fy": row.get("fy"),
                    "fp": row.get("fp"),
                    "frame": row.get("frame"),
                    "diluted_eps_usd_per_share": row.get("val"),
                    "sec_acceptance_datetime": acceptance.isoformat(),
                    "decision_session": decision_session,
                    "decision_session_open_utc": decision_open,
                    "companyfacts_source_sha256": expected_hashes.get(cik),
                    "submission_source": EARNINGS_INNOVATION_PIT_ACCEPTANCE_SOURCE,
                })
            if index == 1 or index % 25 == 0 or index == len(sample_ciks):
                print(f"SEC earnings-innovation PIT chronology progress: {index}/{len(sample_ciks)} roots={submissions_root_success} audited={len(audited_rows)} missing_metadata={missing_accession_metadata}")

        audited_rows.sort(key=lambda r: (str(r["decision_session"]), str(r["issuer_cik"]), str(r["end"]), str(r["accession_number"])))
        audited_by_cik: defaultdict[str, set[str]] = defaultdict(set)
        observed_years: set[int] = set()
        for row in audited_rows:
            audited_by_cik[str(row["issuer_cik"])].add(str(row["end"]))
            observed_years.add(date.fromisoformat(str(row["end"])).year)
        audited_history_ready = sum(len(values) >= EARNINGS_INNOVATION_HISTORY_READY_MIN_DIRECT_QUARTERS for values in audited_by_cik.values())
        audited_sue_ready = sum(len(values) >= EARNINGS_INNOVATION_SUE_BASELINE_READY_MIN_DIRECT_QUARTERS for values in audited_by_cik.values())
        acceptance_fraction = len(audited_rows) / original_candidates if original_candidates else 0.0

        gates = {
            "parent_report_exact": True,
            "parent_sample_exact": len(sample_ciks) == EARNINGS_INNOVATION_SAMPLE_SIZE and len(set(sample_ciks)) == EARNINGS_INNOVATION_SAMPLE_SIZE,
            "companyfacts_hash_matches_min": companyfacts_hash_matches >= EARNINGS_INNOVATION_PIT_MIN_COMPANYFACTS_HASH_MATCHES,
            "parent_semantics_reconciled": parent_semantics_reconciled,
            "submissions_root_success_min": submissions_root_success >= EARNINGS_INNOVATION_PIT_MIN_SUBMISSIONS_ROOT_SUCCESS,
            "audited_observations_min": len(audited_rows) >= EARNINGS_INNOVATION_PIT_MIN_AUDITED_OBSERVATIONS,
            "audited_history_ready_issuers_min": audited_history_ready >= EARNINGS_INNOVATION_PIT_MIN_HISTORY_READY_ISSUERS,
            "audited_sue_baseline_ready_issuers_min": audited_sue_ready >= EARNINGS_INNOVATION_PIT_MIN_SUE_BASELINE_READY_ISSUERS,
            "acceptance_proven_fraction_min": acceptance_fraction >= EARNINGS_INNOVATION_PIT_MIN_ACCEPTANCE_PROVEN_FRACTION,
            "calendar_years_observed_min": len(observed_years) >= EARNINGS_INNOVATION_PIT_MIN_CALENDAR_YEARS_OBSERVED,
            "period_context_ambiguities_max": period_context_ambiguities <= EARNINGS_INNOVATION_PIT_MAX_PERIOD_CONTEXT_AMBIGUITIES,
            "accession_metadata_contradictions_max": metadata_contradictions <= EARNINGS_INNOVATION_PIT_MAX_ACCESSION_METADATA_CONTRADICTIONS,
            "acceptance_not_after_period_end_max": acceptance_not_after_period_end <= EARNINGS_INNOVATION_PIT_MAX_ACCEPTANCE_NOT_AFTER_PERIOD_END,
            "decision_session_errors_max": decision_session_errors <= EARNINGS_INNOVATION_PIT_MAX_DECISION_SESSION_ERRORS,
        }
        passed = all(gates.values())
        rows_path = derived_root / EARNINGS_INNOVATION_PIT_ROWS_RELATIVE
        report_path = derived_root / EARNINGS_INNOVATION_PIT_REPORT_RELATIVE
        atomic_write_text(rows_path, "".join(json.dumps(row, sort_keys=True) + "\n" for row in audited_rows))
        report = {
            "contract_version": EARNINGS_INNOVATION_PIT_AUDIT_CONTRACT,
            "pit_audit_fingerprint": EARNINGS_INNOVATION_PIT_AUDIT_FINGERPRINT,
            "mechanism": EARNINGS_INNOVATION_MECHANISM,
            "status": "PIT_AUDIT_PASS" if passed else "PIT_AUDIT_FAIL",
            "parent_contract": EARNINGS_INNOVATION_FEASIBILITY_CONTRACT,
            "parent_fingerprint": EARNINGS_INNOVATION_FEASIBILITY_FINGERPRINT,
            "parent_target_head": EARNINGS_INNOVATION_PIT_PARENT_TARGET_HEAD,
            "parent_report_sha256": parent_report_sha256,
            "parent_fixed_evidence": _PARENT_FIXED_EVIDENCE,
            "companyfacts_hash_matches": companyfacts_hash_matches,
            "companyfacts_failures": companyfacts_failures,
            "parent_semantics_reconciled": parent_semantics_reconciled,
            "recomputed_direct_quarter_observations": recomputed_direct_observations,
            "recomputed_history_ready_issuers": recomputed_history_ready,
            "recomputed_sue_baseline_ready_issuers": recomputed_sue_ready,
            "original_accession_candidate_observations": original_candidates,
            "period_context_ambiguities": period_context_ambiguities,
            "submissions_root_success": submissions_root_success,
            "submissions_root_failures": submissions_root_failures,
            "submissions_shard_reads": submissions_shard_reads,
            "missing_accession_metadata": missing_accession_metadata,
            "accession_metadata_contradictions": metadata_contradictions,
            "acceptance_not_after_period_end": acceptance_not_after_period_end,
            "decision_session_errors": decision_session_errors,
            "audited_observations": len(audited_rows),
            "acceptance_proven_fraction": acceptance_fraction,
            "audited_history_ready_issuers": audited_history_ready,
            "audited_sue_baseline_ready_issuers": audited_sue_ready,
            "calendar_years_observed": sorted(observed_years),
            "original_accession_rule": EARNINGS_INNOVATION_PIT_ORIGINAL_ACCESSION_RULE,
            "amendment_rule": EARNINGS_INNOVATION_PIT_AMENDMENT_RULE,
            "acceptance_source": EARNINGS_INNOVATION_PIT_ACCEPTANCE_SOURCE,
            "decision_session_rule": EARNINGS_INNOVATION_PIT_DECISION_SESSION_RULE,
            "announcement_timing_claim": EARNINGS_INNOVATION_PIT_ANNOUNCEMENT_TIMING_CLAIM,
            "alpha_hypotheses_frozen": False,
            "gates": gates,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_performed": (2 * EARNINGS_INNOVATION_SAMPLE_SIZE) + submissions_shard_reads,
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "phase33_signal_to_trade_authority": False,
            "pit_rows_path": str(rows_path),
            "report_path": str(report_path),
            "next_scientific_action": (
                "Freeze a separate PIT active-common-stock identity prerequisite before defining the earnings-innovation hypothesis family; market outcomes remain closed."
                if passed
                else "Preserve this PIT source audit exactly; diagnose only mechanical source/provenance defects without lowering frozen audit gates or opening market outcomes."
            ),
            "pass": passed,
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
