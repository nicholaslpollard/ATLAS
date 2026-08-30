from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import exchange_calendars as xcals

from packages.backtesting.alpha_gate_xbrl_feasibility import (
    XBRL_REPORT_RELATIVE,
    xbrl_feasibility_fingerprint,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_xbrl import SECCompanyFactsDocument, SECXBRLCompanyFactsClient
from packages.providers.sec_xbrl_pit import SECOriginalFilingMetadata, SECXBRLPITMetadataClient


XBRL_PIT_AUDIT_CONTRACT = (
    "alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes"
)
XBRL_PIT_ENTRY_FEASIBILITY_FINGERPRINT = (
    "6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152"
)
XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT = (
    "33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9"
)
XBRL_PIT_AUDIT_FINGERPRINT = (
    "50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c"
)
XBRL_PIT_MECHANISM = "PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY"
XBRL_PIT_SOURCE_START = date(2016, 1, 1)
XBRL_PIT_SOURCE_CUTOFF = date(2026, 8, 11)
XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE = 40
XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER = 5
XBRL_PIT_MIN_COMPANYFACTS_SUCCESS = 36
XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS = 180
XBRL_PIT_MIN_SEC_METADATA_RECONCILED = 170
XBRL_PIT_MIN_ACCEPTANCE_DECISIONS = 170
XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS = 120
XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS = 30
XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS = 0
XBRL_PIT_ALLOWED_FORMS = ("10-Q", "10-K")
XBRL_PIT_ALLOWED_TAGS = (
    "Assets",
    "NetIncomeLoss",
    "NetCashProvidedByUsedInOperatingActivities",
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "GrossProfit",
    "CostOfRevenue",
    "CostOfGoodsAndServicesSold",
)
XBRL_PIT_EVIDENCE_RELATIVE = Path("pre_phase33_xbrl_pit_audit/v1")
XBRL_PIT_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/xbrl_pit_audit_v1/source_audit.json"
)
XBRL_PIT_ALPHA_HYPOTHESES_FROZEN = False
XBRL_PIT_TARGET_OUTCOME_READS_ALLOWED = False
XBRL_PIT_PROTECTED_OUTCOME_READS_ALLOWED = False
XBRL_PIT_PROVIDER_WRITES = 0
XBRL_PIT_BROKER_READS = 0
XBRL_PIT_BROKER_WRITES = 0
XBRL_PIT_ORDER_WRITES = 0
XBRL_PIT_PAPER_SUBMITS = 0
XBRL_PIT_LIVE_WRITES = 0
XBRL_PIT_AUTOMATION_WRITES = 0
_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


class XBRLPITAuditError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise XBRLPITAuditError(f"CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


def _parse_date(value: object, *, field: str) -> date:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise XBRLPITAuditError(f"invalid {field}: {value!r}") from exc
    if parsed.isoformat() != text:
        raise XBRLPITAuditError(f"invalid {field}: {value!r}")
    return parsed


def _accepted_feasibility_evidence_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "feasibility_fingerprint": report.get("feasibility_fingerprint"),
        "status": report.get("status"),
        "source_inventory_unique_ciks": report.get("source_inventory_unique_ciks"),
        "sample_size": report.get("sample_size"),
        "successful_documents": report.get("successful_documents"),
        "failed_documents": report.get("failed_documents"),
        "accrual_history_ready": report.get("accrual_history_ready"),
        "profitability_history_ready": report.get("profitability_history_ready"),
        "group_history_ready_counts": report.get("group_history_ready_counts"),
        "target_outcome_rows_read": report.get("target_outcome_rows_read"),
        "protected_return_rows_read": report.get("protected_return_rows_read"),
        "protected_holdout_consumed": report.get("protected_holdout_consumed"),
        "provider_reads_performed": report.get("provider_reads_performed"),
        "provider_writes_performed": report.get("provider_writes_performed"),
        "broker_reads_performed": report.get("broker_reads_performed"),
        "broker_writes_performed": report.get("broker_writes_performed"),
        "order_writes_performed": report.get("order_writes_performed"),
        "paper_submits_performed": report.get("paper_submits_performed"),
        "live_writes_performed": report.get("live_writes_performed"),
        "automation_writes_performed": report.get("automation_writes_performed"),
    }


def accepted_feasibility_evidence_fingerprint(report: dict[str, Any]) -> str:
    return _sha256_text(_canonical_json(_accepted_feasibility_evidence_payload(report)))


def _audit_policy_payload() -> dict[str, Any]:
    return {
        "contract_version": XBRL_PIT_AUDIT_CONTRACT,
        "entry_feasibility_fingerprint": XBRL_PIT_ENTRY_FEASIBILITY_FINGERPRINT,
        "entry_evidence_fingerprint": XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT,
        "mechanism": XBRL_PIT_MECHANISM,
        "source_start": XBRL_PIT_SOURCE_START.isoformat(),
        "source_cutoff": XBRL_PIT_SOURCE_CUTOFF.isoformat(),
        "audit_issuer_sample_size": XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE,
        "max_accessions_per_issuer": XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER,
        "issuer_selection_rule": "SHA256_CIK_PLUS_AUDIT_CONTRACT_ASCENDING_FROM_FEASIBILITY_READY_ISSUERS",
        "accession_selection_rule": "EVENLY_SPACED_FILED_DATE_ORDER_INCLUDE_ENDPOINTS",
        "allowed_forms": list(XBRL_PIT_ALLOWED_FORMS),
        "companyfacts_source": "SEC:data.sec.gov/api/xbrl/companyfacts/CIK##########.json",
        "submissions_source": "SEC:data.sec.gov/submissions/CIK##########.json_AND_DECLARED_SHARDS",
        "identity_source": "Massive:/v3/reference/tickers?cik=...&date=...&active=...",
        "decision_rule": "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE",
        "fact_version_rule": "EXACT_ACCESSION_VERSIONED_NEVER_OVERWRITE_ACROSS_ACCESSIONS",
        "same_accession_conflict_rule": "FAIL_CLOSED_ON_DISTINCT_VALUES_FOR_SAME_SEMANTIC_CONTEXT",
        "identity_contract": IDENTITY_CONTRACT_VERSION,
        "identity_rule": "EXACT_CIK_DATE_FILTER_STRONG_OR_MEDIUM_AND_EXACTLY_ONE_UNIQUE_INSTRUMENT",
        "min_companyfacts_success": XBRL_PIT_MIN_COMPANYFACTS_SUCCESS,
        "min_selected_original_filings": XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS,
        "min_sec_metadata_reconciled": XBRL_PIT_MIN_SEC_METADATA_RECONCILED,
        "min_acceptance_decisions": XBRL_PIT_MIN_ACCEPTANCE_DECISIONS,
        "min_unambiguous_identity_mappings": XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS,
        "min_issuers_with_3_unambiguous_mappings": XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS,
        "max_same_accession_context_conflicts": XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS,
        "alpha_hypotheses_frozen": XBRL_PIT_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": XBRL_PIT_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": XBRL_PIT_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_writes": XBRL_PIT_PROVIDER_WRITES,
        "broker_reads": XBRL_PIT_BROKER_READS,
        "broker_writes": XBRL_PIT_BROKER_WRITES,
        "order_writes": XBRL_PIT_ORDER_WRITES,
        "paper_submits": XBRL_PIT_PAPER_SUBMITS,
        "live_writes": XBRL_PIT_LIVE_WRITES,
        "automation_writes": XBRL_PIT_AUTOMATION_WRITES,
    }


def xbrl_pit_audit_fingerprint() -> str:
    return _sha256_text(_canonical_json(_audit_policy_payload()))


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise XBRLPITAuditError(f"required source-only evidence is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise XBRLPITAuditError(f"source-only evidence root is not an object: {path}")
    return value


def _validate_feasibility_report(report: dict[str, Any]) -> None:
    if xbrl_feasibility_fingerprint() != XBRL_PIT_ENTRY_FEASIBILITY_FINGERPRINT:
        raise XBRLPITAuditError("feasibility policy fingerprint drifted before PIT audit")
    actual = accepted_feasibility_evidence_fingerprint(report)
    if actual != XBRL_PIT_ACCEPTED_FEASIBILITY_EVIDENCE_FINGERPRINT:
        raise XBRLPITAuditError(
            f"local feasibility evidence differs from accepted target result: {actual}"
        )
    issuer_reports = report.get("issuer_reports")
    sample_ciks = report.get("sample_ciks")
    if not isinstance(issuer_reports, list) or not isinstance(sample_ciks, list):
        raise XBRLPITAuditError("accepted feasibility report is missing issuer/sample evidence")
    normalized_reports = [_normalize_cik(row.get("issuer_cik")) for row in issuer_reports if isinstance(row, dict)]
    normalized_sample = [_normalize_cik(value) for value in sample_ciks]
    if len(normalized_reports) != 200 or len(set(normalized_reports)) != 200:
        raise XBRLPITAuditError("accepted feasibility issuer report population is not exactly 200 unique CIKs")
    if set(normalized_reports) != set(normalized_sample):
        raise XBRLPITAuditError("accepted feasibility sample CIKs differ from issuer report CIKs")
    accrual = sum(bool(row.get("accrual_history_ready")) for row in issuer_reports if isinstance(row, dict))
    profitability = sum(bool(row.get("profitability_history_ready")) for row in issuer_reports if isinstance(row, dict))
    if accrual != 170 or profitability != 92:
        raise XBRLPITAuditError("accepted feasibility per-issuer readiness does not reproduce 170/92")
    group_counts: Counter[str] = Counter()
    for row in issuer_reports:
        if not isinstance(row, dict):
            continue
        groups = row.get("concept_groups")
        if not isinstance(groups, dict):
            raise XBRLPITAuditError("accepted feasibility issuer report is missing concept groups")
        for group_id, summary in groups.items():
            if isinstance(summary, dict) and int(summary.get("period_end_count") or 0) >= 8:
                group_counts[str(group_id)] += 1
    expected_groups = {
        "assets": 174,
        "cost_of_revenue": 97,
        "gross_profit": 78,
        "net_income": 180,
        "operating_cash_flow": 180,
        "revenue": 136,
    }
    if dict(sorted(group_counts.items())) != expected_groups:
        raise XBRLPITAuditError("accepted feasibility group readiness counts do not reproduce")


def _select_audit_issuers(report: dict[str, Any]) -> tuple[str, ...]:
    issuer_reports = report["issuer_reports"]
    ready = {
        _normalize_cik(row["issuer_cik"])
        for row in issuer_reports
        if isinstance(row, dict)
        and (bool(row.get("accrual_history_ready")) or bool(row.get("profitability_history_ready")))
    }
    if len(ready) < XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE:
        raise XBRLPITAuditError("feasibility-ready issuer population is too small for frozen PIT audit sample")
    ranked = sorted(
        ready,
        key=lambda cik: (
            hashlib.sha256(f"{cik}:{XBRL_PIT_AUDIT_CONTRACT}".encode("ascii")).hexdigest(),
            cik,
        ),
    )
    return tuple(ranked[:XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE])


def _extract_relevant_entries(document: SECCompanyFactsDocument) -> tuple[dict[str, Any], ...]:
    namespace = document.facts.get("us-gaap")
    if not isinstance(namespace, dict):
        return ()
    rows: list[dict[str, Any]] = []
    for tag in XBRL_PIT_ALLOWED_TAGS:
        concept = namespace.get(tag)
        if not isinstance(concept, dict):
            continue
        units = concept.get("units")
        if not isinstance(units, dict):
            continue
        for unit, entries in sorted(units.items()):
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                form = str(entry.get("form") or "").strip()
                if form not in XBRL_PIT_ALLOWED_FORMS:
                    continue
                filed_text = str(entry.get("filed") or "").strip()
                try:
                    filed = date.fromisoformat(filed_text)
                except ValueError:
                    continue
                if filed < XBRL_PIT_SOURCE_START or filed > XBRL_PIT_SOURCE_CUTOFF:
                    continue
                accession = str(entry.get("accn") or "").strip()
                end = str(entry.get("end") or "").strip()
                if not _ACCESSION_RE.fullmatch(accession) or not end:
                    continue
                try:
                    date.fromisoformat(end)
                except ValueError:
                    continue
                if entry.get("val") is None:
                    continue
                rows.append(
                    {
                        "tag": tag,
                        "unit": str(unit),
                        "start": entry.get("start"),
                        "end": end,
                        "filed": filed.isoformat(),
                        "form": form,
                        "accn": accession,
                        "fy": entry.get("fy"),
                        "fp": entry.get("fp"),
                        "frame": entry.get("frame"),
                        "val": entry.get("val"),
                    }
                )
    rows.sort(
        key=lambda row: (
            str(row["filed"]),
            str(row["accn"]),
            str(row["tag"]),
            str(row["unit"]),
            str(row["start"]),
            str(row["end"]),
            str(row["fy"]),
            str(row["fp"]),
            str(row["frame"]),
            _canonical_json(row["val"]),
        )
    )
    return tuple(rows)


def _group_accessions(entries: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        grouped[str(row["accn"])].append(dict(row))
    out: list[dict[str, Any]] = []
    for accession, rows in grouped.items():
        filing_dates = {str(row["filed"]) for row in rows}
        forms = {str(row["form"]) for row in rows}
        out.append(
            {
                "accession_number": accession,
                "filing_dates": sorted(filing_dates),
                "forms": sorted(forms),
                "clean": len(filing_dates) == 1 and len(forms) == 1,
                "filing_date": next(iter(filing_dates)) if len(filing_dates) == 1 else None,
                "form": next(iter(forms)) if len(forms) == 1 else None,
                "rows": sorted(rows, key=_canonical_json),
            }
        )
    out.sort(key=lambda item: (str(item.get("filing_date") or "9999-99-99"), item["accession_number"]))
    return tuple(out)


def _select_accessions(groups: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    clean = [dict(group) for group in groups if bool(group.get("clean"))]
    if len(clean) <= XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER:
        return tuple(clean)
    last = len(clean) - 1
    denominator = XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER - 1
    indices = [(index * last) // denominator for index in range(XBRL_PIT_MAX_ACCESSIONS_PER_ISSUER)]
    return tuple(clean[index] for index in indices)


def _same_accession_context_conflicts(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    values_by_context: dict[tuple[str, ...], set[str]] = defaultdict(set)
    full_rows: set[str] = set()
    total = 0
    for row in rows:
        total += 1
        key = tuple(
            str(row.get(field) if row.get(field) is not None else "")
            for field in ("tag", "unit", "start", "end", "fy", "fp", "frame")
        )
        values_by_context[key].add(_canonical_json(row.get("val")))
        full_rows.add(_canonical_json(row))
    conflicts = sum(len(values) > 1 for values in values_by_context.values())
    exact_duplicates = total - len(full_rows)
    return conflicts, exact_duplicates


def _version_summary(entries: Iterable[dict[str, Any]]) -> dict[str, int]:
    versions: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        key = tuple(
            str(row.get(field) if row.get(field) is not None else "")
            for field in ("tag", "unit", "start", "end", "fy", "fp", "frame")
        )
        versions[key].append(dict(row))
    repeated_contexts = 0
    revised_contexts = 0
    version_rows = 0
    for rows in versions.values():
        accessions = {str(row["accn"]) for row in rows}
        if len(accessions) <= 1:
            continue
        repeated_contexts += 1
        version_rows += len(rows)
        if len({_canonical_json(row.get("val")) for row in rows}) > 1:
            revised_contexts += 1
    return {
        "repeated_cross_accession_contexts": repeated_contexts,
        "revised_cross_accession_contexts": revised_contexts,
        "cross_accession_version_rows": version_rows,
    }


def _decision_session(acceptance_datetime: str) -> date:
    normalized = acceptance_datetime.strip().replace("Z", "+00:00")
    try:
        accepted = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise XBRLPITAuditError(f"invalid SEC acceptance datetime: {acceptance_datetime!r}") from exc
    if accepted.tzinfo is None:
        raise XBRLPITAuditError("SEC acceptance datetime must be timezone-aware")
    accepted_utc = accepted.astimezone(UTC)
    calendar = xcals.get_calendar("XNYS")
    sessions = calendar.sessions_in_range(accepted.date(), accepted.date() + timedelta(days=14))
    for session in sessions:
        session_open = calendar.session_open(session).to_pydatetime().astimezone(UTC)
        if session_open > accepted_utc:
            return session.date()
    raise XBRLPITAuditError(f"could not resolve XNYS decision session after {acceptance_datetime}")


def _resolve_identity(
    rows: Iterable[dict[str, Any]], *, issuer_cik: str, as_of_date: date
) -> dict[str, Any]:
    resolver = InstrumentIdentityResolver()
    resolved: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            row_cik = _normalize_cik(row.get("cik"))
        except XBRLPITAuditError:
            evidence.append({"ticker": row.get("ticker"), "status": "reference_cik_missing"})
            continue
        if row_cik != issuer_cik:
            evidence.append({"ticker": row.get("ticker"), "status": "reference_cik_mismatch"})
            continue
        try:
            instrument_id, identity_key, quality = resolver.resolve(row, as_of_date)
        except ValueError:
            evidence.append({"ticker": row.get("ticker"), "status": "unresolvable_reference_row"})
            continue
        if quality not in {InstrumentIdentityQuality.STRONG, InstrumentIdentityQuality.MEDIUM}:
            evidence.append({"ticker": row.get("ticker"), "status": "fallback_identity"})
            continue
        resolved[instrument_id] = {
            "instrument_id": instrument_id,
            "identity_key": identity_key,
            "identity_quality": str(quality),
            "ticker": row.get("ticker"),
            "primary_exchange": row.get("primary_exchange"),
            "security_type": row.get("type"),
            "composite_figi": row.get("composite_figi"),
            "share_class_figi": row.get("share_class_figi"),
        }
        evidence.append(
            {
                "ticker": row.get("ticker"),
                "status": "resolved",
                "instrument_id": instrument_id,
                "identity_quality": str(quality),
            }
        )
    instruments = sorted(resolved.values(), key=lambda item: item["instrument_id"])
    if not instruments:
        status = "NO_ELIGIBLE_PIT_INSTRUMENT"
    elif len(instruments) == 1:
        status = "UNAMBIGUOUS_PIT_INSTRUMENT"
    else:
        status = "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS"
    return {
        "status": status,
        "unique_instrument_count": len(instruments),
        "instruments": instruments,
        "mapping_evidence": evidence,
    }


class XBRLPITSourceAudit:
    """Independent source-only PIT audit after accepted XBRL feasibility."""

    def __init__(
        self,
        settings: AtlasSettings,
        companyfacts_client: SECXBRLCompanyFactsClient,
        submissions_client: SECXBRLPITMetadataClient,
        reference_provider: MassiveCIKPITReferenceProvider,
    ) -> None:
        self.settings = settings
        self.companyfacts_client = companyfacts_client
        self.submissions_client = submissions_client
        self.reference_provider = reference_provider
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.evidence_root = self.provider_root / XBRL_PIT_EVIDENCE_RELATIVE
        self.cache_hits: Counter[str] = Counter()
        self.source_reads: Counter[str] = Counter()

    def _cached_companyfacts(self, cik: str) -> dict[str, Any]:
        path = self.evidence_root / "companyfacts" / f"{cik}.json"
        if path.is_file():
            self.cache_hits["companyfacts"] += 1
            value = _load_json(path)
            if _normalize_cik(value.get("issuer_cik")) != cik:
                raise XBRLPITAuditError(f"cached Company Facts CIK mismatch: {path}")
            return value
        self.source_reads["companyfacts"] += 1
        document = self.companyfacts_client.company_facts(cik=cik)
        entries = _extract_relevant_entries(document)
        value = {
            "issuer_cik": document.issuer_cik,
            "entity_name": document.entity_name,
            "source_url": document.source_url,
            "source_sha256": document.source_sha256,
            "relevant_entries_sha256": _sha256_text("".join(_canonical_json(row) + "\n" for row in entries)),
            "entries": list(entries),
        }
        atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return value

    def _cached_submission(
        self, *, cik: str, accession: str, filing_date: str, form: str
    ) -> dict[str, Any]:
        path = self.evidence_root / "submissions" / cik / f"{accession}.json"
        if path.is_file():
            self.cache_hits["submissions"] += 1
            value = _load_json(path)
        else:
            self.source_reads["submissions"] += 1
            metadata = self.submissions_client.filing_metadata(
                cik=cik,
                accession_number=accession,
                filing_date=filing_date,
                allowed_forms=(form,),
            )
            value = asdict(metadata)
            atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        if _normalize_cik(value.get("issuer_cik")) != cik:
            raise XBRLPITAuditError(f"cached SEC metadata CIK mismatch: {path}")
        if value.get("accession_number") != accession:
            raise XBRLPITAuditError(f"cached SEC metadata accession mismatch: {path}")
        if value.get("filing_date") != filing_date or value.get("form") != form:
            raise XBRLPITAuditError(f"cached SEC metadata form/date mismatch: {path}")
        return value

    def _cached_reference(self, *, cik: str, as_of_date: date) -> list[dict[str, Any]]:
        path = self.evidence_root / "massive_reference" / as_of_date.isoformat() / f"{cik}.json"
        if path.is_file():
            self.cache_hits["massive_reference"] += 1
            value = _load_json(path)
            rows = value.get("rows")
            if value.get("issuer_cik") != cik or value.get("as_of_date") != as_of_date.isoformat():
                raise XBRLPITAuditError(f"cached Massive CIK/date evidence mismatch: {path}")
            if not isinstance(rows, list):
                raise XBRLPITAuditError(f"cached Massive CIK/date rows are invalid: {path}")
            return [dict(row) for row in rows if isinstance(row, dict)]
        self.source_reads["massive_reference"] += 1
        rows = self.reference_provider.cik_snapshot(cik=cik, as_of_date=as_of_date, include_inactive=True)
        value = {
            "issuer_cik": cik,
            "as_of_date": as_of_date.isoformat(),
            "rows": rows,
            "rows_sha256": _sha256_text("".join(_canonical_json(row) + "\n" for row in rows)),
        }
        atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return rows

    def run(self) -> dict[str, Any]:
        if xbrl_pit_audit_fingerprint() != XBRL_PIT_AUDIT_FINGERPRINT:
            raise XBRLPITAuditError("frozen XBRL PIT audit policy fingerprint drifted")
        if IDENTITY_CONTRACT_VERSION != "instrument-identity-v4-no-issuer-level-medium-collapse":
            raise XBRLPITAuditError("instrument identity contract drifted before XBRL PIT audit")

        feasibility_path = self.derived_root / XBRL_REPORT_RELATIVE
        feasibility = _load_json(feasibility_path)
        _validate_feasibility_report(feasibility)
        audit_ciks = _select_audit_issuers(feasibility)

        companyfacts_success = 0
        selected_original_filings = 0
        sec_metadata_reconciled = 0
        acceptance_decisions = 0
        unambiguous_identity_mappings = 0
        same_accession_context_conflicts = 0
        exact_duplicate_fact_rows = 0
        repeated_cross_accession_contexts = 0
        revised_cross_accession_contexts = 0
        cross_accession_version_rows = 0
        issuer_reports: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        issuer_mapping_counts: Counter[str] = Counter()

        for index, cik in enumerate(audit_ciks, start=1):
            issuer_result: dict[str, Any] = {"issuer_cik": cik, "filings": []}
            try:
                source = self._cached_companyfacts(cik)
            except Exception as exc:
                failures.append(
                    {"issuer_cik": cik, "stage": "companyfacts", "error_type": type(exc).__name__, "error": str(exc)}
                )
                issuer_result["status"] = "COMPANYFACTS_FAILURE"
                issuer_reports.append(issuer_result)
                continue

            companyfacts_success += 1
            entries = tuple(dict(row) for row in source.get("entries", []) if isinstance(row, dict))
            issuer_result.update(
                {
                    "entity_name": source.get("entity_name"),
                    "companyfacts_source_sha256": source.get("source_sha256"),
                    "relevant_entries_sha256": source.get("relevant_entries_sha256"),
                    "relevant_entry_count": len(entries),
                }
            )
            versioning = _version_summary(entries)
            issuer_result["versioning"] = versioning
            repeated_cross_accession_contexts += versioning["repeated_cross_accession_contexts"]
            revised_cross_accession_contexts += versioning["revised_cross_accession_contexts"]
            cross_accession_version_rows += versioning["cross_accession_version_rows"]

            groups = _group_accessions(entries)
            malformed_groups = [group for group in groups if not group["clean"]]
            issuer_result["accession_count"] = len(groups)
            issuer_result["malformed_accession_groups"] = len(malformed_groups)
            selected = _select_accessions(groups)
            issuer_result["selected_accessions"] = [group["accession_number"] for group in selected]
            selected_original_filings += len(selected)

            for group in selected:
                accession = str(group["accession_number"])
                filing_date = str(group["filing_date"])
                form = str(group["form"])
                rows = tuple(dict(row) for row in group["rows"])
                conflicts, duplicates = _same_accession_context_conflicts(rows)
                same_accession_context_conflicts += conflicts
                exact_duplicate_fact_rows += duplicates
                filing_result: dict[str, Any] = {
                    "accession_number": accession,
                    "filing_date": filing_date,
                    "form": form,
                    "fact_rows": len(rows),
                    "same_accession_context_conflicts": conflicts,
                    "exact_duplicate_fact_rows": duplicates,
                }
                if conflicts:
                    filing_result["status"] = "SAME_ACCESSION_CONTEXT_CONFLICT"
                    issuer_result["filings"].append(filing_result)
                    continue
                try:
                    metadata = self._cached_submission(
                        cik=cik, accession=accession, filing_date=filing_date, form=form
                    )
                except Exception as exc:
                    filing_result.update(
                        {"status": "SEC_METADATA_FAILURE", "error_type": type(exc).__name__, "error": str(exc)}
                    )
                    issuer_result["filings"].append(filing_result)
                    failures.append(
                        {
                            "issuer_cik": cik,
                            "accession_number": accession,
                            "stage": "sec_metadata",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
                    continue
                sec_metadata_reconciled += 1
                filing_result["sec_metadata_source_sha256"] = metadata.get("source_record_sha256")
                filing_result["acceptance_datetime"] = metadata.get("acceptance_datetime")
                try:
                    decision = _decision_session(str(metadata.get("acceptance_datetime") or ""))
                except Exception as exc:
                    filing_result.update(
                        {"status": "ACCEPTANCE_TIME_FAILURE", "error_type": type(exc).__name__, "error": str(exc)}
                    )
                    issuer_result["filings"].append(filing_result)
                    failures.append(
                        {
                            "issuer_cik": cik,
                            "accession_number": accession,
                            "stage": "acceptance_time",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
                    continue
                acceptance_decisions += 1
                filing_result["decision_session"] = decision.isoformat()
                try:
                    reference_rows = self._cached_reference(cik=cik, as_of_date=decision)
                    identity = _resolve_identity(reference_rows, issuer_cik=cik, as_of_date=decision)
                except Exception as exc:
                    filing_result.update(
                        {"status": "PIT_IDENTITY_SOURCE_FAILURE", "error_type": type(exc).__name__, "error": str(exc)}
                    )
                    issuer_result["filings"].append(filing_result)
                    failures.append(
                        {
                            "issuer_cik": cik,
                            "accession_number": accession,
                            "stage": "pit_identity",
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        }
                    )
                    continue
                filing_result["identity"] = identity
                filing_result["status"] = identity["status"]
                if identity["status"] == "UNAMBIGUOUS_PIT_INSTRUMENT":
                    unambiguous_identity_mappings += 1
                    issuer_mapping_counts[cik] += 1
                issuer_result["filings"].append(filing_result)

            issuer_result["unambiguous_mapping_count"] = issuer_mapping_counts[cik]
            issuer_result["status"] = "AUDITED"
            issuer_reports.append(issuer_result)
            if index == 1 or index % 5 == 0 or index == len(audit_ciks):
                print(
                    f"XBRL PIT audit progress: {index}/{len(audit_ciks)} "
                    f"companyfacts={companyfacts_success} filings={selected_original_filings} "
                    f"sec_ok={sec_metadata_reconciled} identity_ok={unambiguous_identity_mappings}"
                )

        issuers_with_3_unambiguous = sum(count >= 3 for count in issuer_mapping_counts.values())
        gates = {
            "audit_issuer_sample_exact": len(audit_ciks) == XBRL_PIT_AUDIT_ISSUER_SAMPLE_SIZE,
            "companyfacts_success_min": companyfacts_success >= XBRL_PIT_MIN_COMPANYFACTS_SUCCESS,
            "selected_original_filings_min": selected_original_filings >= XBRL_PIT_MIN_SELECTED_ORIGINAL_FILINGS,
            "sec_metadata_reconciled_min": sec_metadata_reconciled >= XBRL_PIT_MIN_SEC_METADATA_RECONCILED,
            "acceptance_decisions_min": acceptance_decisions >= XBRL_PIT_MIN_ACCEPTANCE_DECISIONS,
            "unambiguous_identity_mappings_min": (
                unambiguous_identity_mappings >= XBRL_PIT_MIN_UNAMBIGUOUS_IDENTITY_MAPPINGS
            ),
            "issuers_with_3_unambiguous_mappings_min": (
                issuers_with_3_unambiguous >= XBRL_PIT_MIN_ISSUERS_WITH_3_UNAMBIGUOUS_MAPPINGS
            ),
            "same_accession_context_conflicts_max": (
                same_accession_context_conflicts <= XBRL_PIT_MAX_SAME_ACCESSION_CONTEXT_CONFLICTS
            ),
        }
        passed = all(gates.values())
        report = {
            "contract_version": XBRL_PIT_AUDIT_CONTRACT,
            "audit_fingerprint": xbrl_pit_audit_fingerprint(),
            "entry_feasibility_fingerprint": XBRL_PIT_ENTRY_FEASIBILITY_FINGERPRINT,
            "entry_feasibility_evidence_fingerprint": accepted_feasibility_evidence_fingerprint(feasibility),
            "entry_feasibility_report_path": str(feasibility_path),
            "entry_feasibility_report_sha256": sha256_file(feasibility_path),
            "mechanism": XBRL_PIT_MECHANISM,
            "status": "AUDIT_PASS" if passed else "AUDIT_FAIL",
            "pass": passed,
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_performed": sum(self.source_reads.values()),
            "provider_read_breakdown": dict(sorted(self.source_reads.items())),
            "cache_hits": dict(sorted(self.cache_hits.items())),
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "audit_issuer_sample_size": len(audit_ciks),
            "audit_ciks": list(audit_ciks),
            "companyfacts_success": companyfacts_success,
            "selected_original_filings": selected_original_filings,
            "sec_metadata_reconciled": sec_metadata_reconciled,
            "acceptance_decisions": acceptance_decisions,
            "unambiguous_identity_mappings": unambiguous_identity_mappings,
            "issuers_with_3_unambiguous_mappings": issuers_with_3_unambiguous,
            "same_accession_context_conflicts": same_accession_context_conflicts,
            "exact_duplicate_fact_rows": exact_duplicate_fact_rows,
            "repeated_cross_accession_contexts": repeated_cross_accession_contexts,
            "revised_cross_accession_contexts": revised_cross_accession_contexts,
            "cross_accession_version_rows": cross_accession_version_rows,
            "fact_version_rule": "EXACT_ACCESSION_VERSIONED_NEVER_OVERWRITE_ACROSS_ACCESSIONS",
            "decision_rule": "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE",
            "identity_contract": IDENTITY_CONTRACT_VERSION,
            "gates": gates,
            "issuer_reports": issuer_reports,
            "failures": failures,
            "next_scientific_action": (
                "If this source audit passes, freeze the finite XBRL fundamental hypothesis family, "
                "outcome/cost/dependence/multiplicity/sample/winner/protected-evidence contract before "
                "any market outcome is opened."
            ),
        }
        report_path = self.derived_root / XBRL_PIT_REPORT_RELATIVE
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
