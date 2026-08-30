from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

import exchange_calendars as xcals

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import InstrumentIdentityQuality
from packages.core.settings import AtlasSettings
from packages.instruments.identity import IDENTITY_CONTRACT_VERSION, InstrumentIdentityResolver
from packages.providers.massive.xbrl_pit import MassiveCIKPITReferenceProvider
from packages.providers.sec_edgar_archive import (
    SECArchiveTextDocument,
    SECEDGARArchiveClient,
)


BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT = (
    "alpha-gate-sec-beneficial-ownership-feasibility-v1-schedule13d13g-source-only-no-market-outcomes"
)
BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE = "083c0a5742b161cf4b7c04d5bf0246f3057f6c19"
BENEFICIAL_OWNERSHIP_MECHANISM = "PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE"
BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT = (
    "f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb"
)
BENEFICIAL_OWNERSHIP_SOURCE_START = date(2016, 1, 1)
BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF = date(2026, 8, 11)
BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE = date(2024, 12, 18)
BENEFICIAL_OWNERSHIP_ALLOWED_FORMS = (
    "SC 13D",
    "SC 13D/A",
    "SC 13G",
    "SC 13G/A",
    "SCHEDULE 13D",
    "SCHEDULE 13D/A",
    "SCHEDULE 13G",
    "SCHEDULE 13G/A",
)
BENEFICIAL_OWNERSHIP_FORM_CLASSES = (
    "13D_INITIAL",
    "13D_AMENDMENT",
    "13G_INITIAL",
    "13G_AMENDMENT",
)
BENEFICIAL_OWNERSHIP_ERAS = ("legacy", "structured")
BENEFICIAL_OWNERSHIP_STRATA = tuple(
    f"{era}:{form_class}"
    for era in BENEFICIAL_OWNERSHIP_ERAS
    for form_class in BENEFICIAL_OWNERSHIP_FORM_CLASSES
)
BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM = 25
BENEFICIAL_OWNERSHIP_SAMPLE_SIZE = 200
BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM = 50
BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS = 190
BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED = 190
BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED = 190
BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED = 190
BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED = 185
BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS = 190
BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS = 140
BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS = 90
BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS = 90
BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS = 130
BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM = 22
BENEFICIAL_OWNERSHIP_ALPHA_HYPOTHESES_FROZEN = False
BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED = False
BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED = False
BENEFICIAL_OWNERSHIP_PROVIDER_READS_ALLOWED = True
BENEFICIAL_OWNERSHIP_PROVIDER_WRITES = 0
BENEFICIAL_OWNERSHIP_BROKER_READS = 0
BENEFICIAL_OWNERSHIP_BROKER_WRITES = 0
BENEFICIAL_OWNERSHIP_ORDER_WRITES = 0
BENEFICIAL_OWNERSHIP_PAPER_SUBMITS = 0
BENEFICIAL_OWNERSHIP_LIVE_WRITES = 0
BENEFICIAL_OWNERSHIP_AUTOMATION_WRITES = 0
BENEFICIAL_OWNERSHIP_AUTOMATIC_BROKER_FAILOVER = False
BENEFICIAL_OWNERSHIP_EVIDENCE_RELATIVE = Path("pre_phase33_beneficial_ownership/v1")
BENEFICIAL_OWNERSHIP_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/beneficial_ownership_feasibility_v1/source_audit.json"
)

_ACCESSION_RE = re.compile(r"(?P<accession>\d{10}-\d{2}-\d{6})\.txt$")
_ACCEPTANCE_RE = re.compile(r"<ACCEPTANCE-DATETIME>\s*(\d{14})", re.IGNORECASE)
_HEADER_ACCESSION_RE = re.compile(
    r"ACCESSION NUMBER:\s*(\d{10}-\d{2}-\d{6})", re.IGNORECASE
)
_HEADER_FORM_RE = re.compile(r"CONFORMED SUBMISSION TYPE:\s*([^\r\n<]+)", re.IGNORECASE)
_FILED_AS_OF_RE = re.compile(r"FILED AS OF DATE:\s*(\d{8})", re.IGNORECASE)
_CIK_RE = re.compile(r"(?:CENTRAL INDEX KEY:|<CIK>)\s*(\d+)", re.IGNORECASE)
_NAME_RE = re.compile(r"(?:COMPANY CONFORMED NAME:|<CONFORMED-NAME>)\s*([^\r\n<]+)", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class BeneficialOwnershipIndexRow:
    index_cik: str
    company_name: str
    form: str
    filing_date: str
    filename: str
    accession_number: str
    era: str
    form_class: str
    stratum: str


@dataclass(frozen=True, slots=True)
class BeneficialOwnershipSubmissionMetadata:
    accession_number: str | None
    acceptance_datetime: str | None
    filing_date: str | None
    form: str | None
    subject_cik: str | None
    subject_name: str | None
    structured_primary_xml_marker: bool
    cusip_marker: bool
    event_date_marker: bool
    item4_marker: bool


class BeneficialOwnershipFeasibilityError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _quarter_sequence() -> tuple[tuple[int, int], ...]:
    quarters: list[tuple[int, int]] = []
    year, quarter = 2016, 1
    while (year, quarter) <= (2026, 3):
        quarters.append((year, quarter))
        quarter += 1
        if quarter == 5:
            year += 1
            quarter = 1
    return tuple(quarters)


BENEFICIAL_OWNERSHIP_QUARTERS = _quarter_sequence()
BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT = len(BENEFICIAL_OWNERSHIP_QUARTERS)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
        "source_xbrl_merge": BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE,
        "mechanism": BENEFICIAL_OWNERSHIP_MECHANISM,
        "source_start": BENEFICIAL_OWNERSHIP_SOURCE_START.isoformat(),
        "source_cutoff": BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF.isoformat(),
        "structured_compliance_date": BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE.isoformat(),
        "quarter_index_count": BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
        "allowed_forms": list(BENEFICIAL_OWNERSHIP_ALLOWED_FORMS),
        "sample_per_stratum": BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM,
        "strata": list(BENEFICIAL_OWNERSHIP_STRATA),
        "sample_size": BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
        "min_discovered_per_stratum": BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM,
        "min_submission_success": BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
        "min_accession_reconciled": BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED,
        "min_form_reconciled": BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED,
        "min_filing_date_reconciled": BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED,
        "min_subject_cik_reconciled": BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED,
        "min_acceptance_decisions": BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
        "min_unique_subject_ciks": BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
        "min_structured_xml_markers": BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
        "min_legacy_cusip_markers": BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
        "min_unambiguous_common_stock_mappings": BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS,
        "min_parsed_per_stratum": BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM,
        "index_source": "SEC:www.sec.gov/Archives/edgar/full-index/YYYY/QTR#/master.idx",
        "submission_source": "SEC:www.sec.gov/Archives/edgar/data/.../*.txt",
        "identity_source": "Massive:/v3/reference/tickers?cik=...&date=...&active=true&type=CS",
        "decision_rule": "FIRST_XNYS_SESSION_OPEN_STRICTLY_AFTER_SEC_ACCEPTANCE",
        "sample_rule": "HASH_RANK_ACCESSION_WITHIN_ERA_X_FORM_CLASS_STRATUM",
        "identity_rule": "EXACT_SUBJECT_CIK_DECISION_DATE_COMMON_STOCK_STRONG_OR_MEDIUM_EXACTLY_ONE_INSTRUMENT",
        "alpha_hypotheses_frozen": BENEFICIAL_OWNERSHIP_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": BENEFICIAL_OWNERSHIP_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": BENEFICIAL_OWNERSHIP_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": BENEFICIAL_OWNERSHIP_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": BENEFICIAL_OWNERSHIP_PROVIDER_WRITES,
            "broker_reads": BENEFICIAL_OWNERSHIP_BROKER_READS,
            "broker_writes": BENEFICIAL_OWNERSHIP_BROKER_WRITES,
            "order_writes": BENEFICIAL_OWNERSHIP_ORDER_WRITES,
            "paper_submits": BENEFICIAL_OWNERSHIP_PAPER_SUBMITS,
            "live_writes": BENEFICIAL_OWNERSHIP_LIVE_WRITES,
            "automation_writes": BENEFICIAL_OWNERSHIP_AUTOMATION_WRITES,
            "automatic_broker_failover": BENEFICIAL_OWNERSHIP_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def beneficial_ownership_feasibility_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _normalize_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        raise BeneficialOwnershipFeasibilityError(f"CIK is not numeric: {value!r}")
    return str(int(text)).zfill(10)


def _form_class(form: str) -> str:
    normalized = form.strip().upper()
    if normalized in {"SC 13D", "SCHEDULE 13D"}:
        return "13D_INITIAL"
    if normalized in {"SC 13D/A", "SCHEDULE 13D/A"}:
        return "13D_AMENDMENT"
    if normalized in {"SC 13G", "SCHEDULE 13G"}:
        return "13G_INITIAL"
    if normalized in {"SC 13G/A", "SCHEDULE 13G/A"}:
        return "13G_AMENDMENT"
    raise BeneficialOwnershipFeasibilityError(f"unsupported beneficial-ownership form: {form!r}")


def _era(filing_date: date) -> str:
    return "structured" if filing_date >= BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE else "legacy"


def _accession_from_filename(filename: str) -> str:
    match = _ACCESSION_RE.search(filename.strip())
    if match is None:
        raise BeneficialOwnershipFeasibilityError(
            f"SEC master index filename lacks expected accession: {filename!r}"
        )
    return match.group("accession")


def parse_master_index(text: str) -> tuple[BeneficialOwnershipIndexRow, ...]:
    header_seen = False
    rows: list[BeneficialOwnershipIndexRow] = []
    for raw_line in text.splitlines():
        line = raw_line.strip("\r\n")
        if not header_seen:
            if line.strip().upper() == "CIK|COMPANY NAME|FORM TYPE|DATE FILED|FILENAME":
                header_seen = True
            continue
        if not line or line.startswith("-") or "|" not in line:
            continue
        parts = line.split("|")
        if len(parts) != 5:
            continue
        cik_text, company_name, form, filed_text, filename = (part.strip() for part in parts)
        form = form.upper()
        if form not in BENEFICIAL_OWNERSHIP_ALLOWED_FORMS:
            continue
        try:
            filed = date.fromisoformat(filed_text)
        except ValueError:
            continue
        if filed < BENEFICIAL_OWNERSHIP_SOURCE_START or filed > BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF:
            continue
        cik = _normalize_cik(cik_text)
        accession = _accession_from_filename(filename)
        form_class = _form_class(form)
        era = _era(filed)
        rows.append(
            BeneficialOwnershipIndexRow(
                index_cik=cik,
                company_name=company_name,
                form=form,
                filing_date=filed.isoformat(),
                filename=filename,
                accession_number=accession,
                era=era,
                form_class=form_class,
                stratum=f"{era}:{form_class}",
            )
        )
    if not header_seen:
        raise BeneficialOwnershipFeasibilityError("SEC master index header was not found")
    return tuple(rows)


def _dedupe_discovery(rows: Iterable[BeneficialOwnershipIndexRow]) -> tuple[BeneficialOwnershipIndexRow, ...]:
    by_accession: dict[str, BeneficialOwnershipIndexRow] = {}
    for row in rows:
        prior = by_accession.get(row.accession_number)
        if prior is not None and prior != row:
            raise BeneficialOwnershipFeasibilityError(
                f"conflicting SEC master-index metadata for accession {row.accession_number}"
            )
        by_accession[row.accession_number] = row
    return tuple(
        sorted(by_accession.values(), key=lambda row: (row.filing_date, row.accession_number, row.index_cik))
    )


def select_stratified_sample(
    rows: Iterable[BeneficialOwnershipIndexRow],
) -> tuple[BeneficialOwnershipIndexRow, ...]:
    grouped: dict[str, list[BeneficialOwnershipIndexRow]] = defaultdict(list)
    for row in rows:
        grouped[row.stratum].append(row)
    sample: list[BeneficialOwnershipIndexRow] = []
    for stratum in BENEFICIAL_OWNERSHIP_STRATA:
        ranked = sorted(
            grouped.get(stratum, []),
            key=lambda row: (
                hashlib.sha256(
                    f"{row.accession_number}:{BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT}".encode("ascii")
                ).hexdigest(),
                row.accession_number,
            ),
        )
        sample.extend(ranked[:BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM])
    return tuple(sorted(sample, key=lambda row: (row.stratum, row.accession_number)))


def _subject_block(text: str) -> str | None:
    upper = text.upper()
    markers = ("SUBJECT COMPANY:", "<SUBJECT-COMPANY>")
    starts = [upper.find(marker) for marker in markers if upper.find(marker) >= 0]
    if not starts:
        return None
    start = min(starts)
    end_candidates: list[int] = []
    for marker in ("FILED BY:", "REPORTING-OWNER:", "</SUBJECT-COMPANY>", "</SEC-HEADER>", "<DOCUMENT>"):
        pos = upper.find(marker, start + 1)
        if pos >= 0:
            end_candidates.append(pos)
    end = min(end_candidates) if end_candidates else min(len(text), start + 50_000)
    return text[start:end]


def _parse_acceptance(raw: str | None) -> str | None:
    if raw is None:
        return None
    try:
        naive = datetime.strptime(raw, "%Y%m%d%H%M%S")
    except ValueError:
        return None
    eastern = naive.replace(tzinfo=ZoneInfo("America/New_York"))
    return eastern.isoformat()


def parse_submission_metadata(text: str) -> BeneficialOwnershipSubmissionMetadata:
    accession_match = _HEADER_ACCESSION_RE.search(text)
    acceptance_match = _ACCEPTANCE_RE.search(text)
    form_match = _HEADER_FORM_RE.search(text)
    filed_match = _FILED_AS_OF_RE.search(text)
    block = _subject_block(text)

    subject_cik = None
    subject_name = None
    if block:
        cik_match = _CIK_RE.search(block)
        name_match = _NAME_RE.search(block)
        if cik_match:
            subject_cik = _normalize_cik(cik_match.group(1))
        if name_match:
            subject_name = name_match.group(1).strip()

    filed_date = None
    if filed_match:
        try:
            filed_date = datetime.strptime(filed_match.group(1), "%Y%m%d").date().isoformat()
        except ValueError:
            filed_date = None

    normalized_form = form_match.group(1).strip().upper() if form_match else None
    upper = text.upper()
    return BeneficialOwnershipSubmissionMetadata(
        accession_number=accession_match.group(1) if accession_match else None,
        acceptance_datetime=_parse_acceptance(acceptance_match.group(1) if acceptance_match else None),
        filing_date=filed_date,
        form=normalized_form,
        subject_cik=subject_cik,
        subject_name=subject_name,
        structured_primary_xml_marker="PRIMARY_DOC.XML" in upper,
        cusip_marker="CUSIP" in upper,
        event_date_marker="DATE OF EVENT WHICH REQUIRES FILING" in upper,
        item4_marker=bool(re.search(r"\bITEM\s*4\b", upper)),
    )


def _decision_session(acceptance_datetime: str) -> date:
    try:
        accepted = datetime.fromisoformat(acceptance_datetime)
    except ValueError as exc:
        raise BeneficialOwnershipFeasibilityError(
            f"invalid SEC acceptance datetime: {acceptance_datetime!r}"
        ) from exc
    if accepted.tzinfo is None:
        raise BeneficialOwnershipFeasibilityError("SEC acceptance datetime must be timezone-aware")
    accepted_utc = accepted.astimezone(UTC)
    calendar = xcals.get_calendar("XNYS")
    start = accepted.date()
    sessions = calendar.sessions_in_range(start, start + timedelta(days=14))
    for session in sessions:
        session_open = calendar.session_open(session).to_pydatetime().astimezone(UTC)
        if session_open > accepted_utc:
            return session.date()
    raise BeneficialOwnershipFeasibilityError(
        f"could not resolve XNYS decision session after {acceptance_datetime}"
    )


def _resolve_identity(
    rows: Iterable[dict[str, Any]], *, subject_cik: str, as_of_date: date
) -> dict[str, Any]:
    resolver = InstrumentIdentityResolver()
    resolved: dict[str, dict[str, Any]] = {}
    evidence: list[dict[str, Any]] = []
    for raw in rows:
        row = dict(raw)
        try:
            row_cik = _normalize_cik(row.get("cik"))
        except BeneficialOwnershipFeasibilityError:
            evidence.append({"ticker": row.get("ticker"), "status": "reference_cik_missing"})
            continue
        if row_cik != subject_cik:
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


class BeneficialOwnershipSourceFeasibility:
    """Source-only SEC 13D/13G chronology and identity feasibility gate."""

    def __init__(
        self,
        settings: AtlasSettings,
        archive_client: SECEDGARArchiveClient,
        reference_provider: MassiveCIKPITReferenceProvider,
    ) -> None:
        self.settings = settings
        self.archive_client = archive_client
        self.reference_provider = reference_provider
        self.derived_root = settings.resolved_path(settings.data.paths.derived)
        self.provider_root = settings.resolved_path(settings.data.paths.provider)
        self.evidence_root = self.provider_root / BENEFICIAL_OWNERSHIP_EVIDENCE_RELATIVE
        self.source_reads: Counter[str] = Counter()
        self.cache_hits: Counter[str] = Counter()

    def _cached_index(self, year: int, quarter: int) -> SECArchiveTextDocument:
        path = self.evidence_root / "indexes" / f"{year}_QTR{quarter}_master.idx"
        if path.is_file():
            self.cache_hits["sec_index"] += 1
            text = path.read_text(encoding="utf-8")
            sha_path = path.with_suffix(path.suffix + ".sha256")
            source_sha256 = (
                sha_path.read_text(encoding="ascii").strip()
                if sha_path.is_file()
                else hashlib.sha256(text.encode("utf-8")).hexdigest()
            )
            return SECArchiveTextDocument(
                source_url=f"cache:{path}", text=text, source_sha256=source_sha256
            )
        self.source_reads["sec_index"] += 1
        document = self.archive_client.quarter_master_index(year=year, quarter=quarter)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, document.text)
        atomic_write_text(path.with_suffix(path.suffix + ".sha256"), document.source_sha256 + "\n")
        return document

    def _cached_submission(self, row: BeneficialOwnershipIndexRow) -> SECArchiveTextDocument:
        path = self.evidence_root / "submissions" / f"{row.accession_number}.txt"
        if path.is_file():
            self.cache_hits["sec_submission"] += 1
            text = path.read_text(encoding="utf-8")
            sha_path = path.with_suffix(path.suffix + ".sha256")
            source_sha256 = (
                sha_path.read_text(encoding="ascii").strip()
                if sha_path.is_file()
                else hashlib.sha256(text.encode("utf-8")).hexdigest()
            )
            return SECArchiveTextDocument(
                source_url=f"cache:{path}", text=text, source_sha256=source_sha256
            )
        self.source_reads["sec_submission"] += 1
        document = self.archive_client.complete_submission(filename=row.filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, document.text)
        atomic_write_text(path.with_suffix(path.suffix + ".sha256"), document.source_sha256 + "\n")
        return document

    def _cached_reference(self, *, cik: str, as_of_date: date) -> list[dict[str, Any]]:
        path = self.evidence_root / "massive_reference" / as_of_date.isoformat() / f"{cik}.json"
        if path.is_file():
            self.cache_hits["massive_reference"] += 1
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise BeneficialOwnershipFeasibilityError(f"invalid cached Massive evidence: {path}")
            if value.get("subject_cik") != cik or value.get("as_of_date") != as_of_date.isoformat():
                raise BeneficialOwnershipFeasibilityError(
                    f"cached Massive CIK/date evidence mismatch: {path}"
                )
            rows = value.get("rows")
            if not isinstance(rows, list):
                raise BeneficialOwnershipFeasibilityError(f"invalid cached Massive rows: {path}")
            return [dict(row) for row in rows if isinstance(row, dict)]

        self.source_reads["massive_reference"] += 1
        rows = self.reference_provider.tradable_common_stock_snapshot(cik=cik, as_of_date=as_of_date)
        value = {
            "subject_cik": cik,
            "as_of_date": as_of_date.isoformat(),
            "rows": rows,
            "rows_sha256": hashlib.sha256(
                "".join(_canonical_json(row) + "\n" for row in rows).encode("utf-8")
            ).hexdigest(),
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")
        return rows

    def run(self) -> dict[str, Any]:
        actual_fingerprint = beneficial_ownership_feasibility_fingerprint()
        if actual_fingerprint != BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT:
            raise BeneficialOwnershipFeasibilityError(
                f"frozen feasibility fingerprint drifted: {actual_fingerprint}"
            )
        if BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT != 43:
            raise BeneficialOwnershipFeasibilityError("frozen quarter index count drifted")
        if IDENTITY_CONTRACT_VERSION != "instrument-identity-v4-no-issuer-level-medium-collapse":
            raise BeneficialOwnershipFeasibilityError("instrument identity contract drifted")

        discovery: list[BeneficialOwnershipIndexRow] = []
        index_reports: list[dict[str, Any]] = []
        index_failures: list[dict[str, Any]] = []
        for index, (year, quarter) in enumerate(BENEFICIAL_OWNERSHIP_QUARTERS, start=1):
            try:
                document = self._cached_index(year, quarter)
                rows = parse_master_index(document.text)
                discovery.extend(rows)
                index_reports.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "source_url": document.source_url,
                        "source_sha256": document.source_sha256,
                        "eligible_rows": len(rows),
                    }
                )
            except Exception as exc:
                index_failures.append(
                    {
                        "year": year,
                        "quarter": quarter,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index == 1 or index % 5 == 0 or index == len(BENEFICIAL_OWNERSHIP_QUARTERS):
                print(
                    f"Beneficial-ownership index progress: {index}/{len(BENEFICIAL_OWNERSHIP_QUARTERS)} "
                    f"success={len(index_reports)} failures={len(index_failures)} eligible_rows={len(discovery)}"
                )

        discovered = _dedupe_discovery(discovery)
        discovered_by_stratum = Counter(row.stratum for row in discovered)
        sample = select_stratified_sample(discovered)
        sample_by_stratum = Counter(row.stratum for row in sample)

        sampled_reports: list[dict[str, Any]] = []
        submission_failures: list[dict[str, Any]] = []
        parsed_per_stratum: Counter[str] = Counter()
        accession_reconciled = 0
        form_reconciled = 0
        filing_date_reconciled = 0
        subject_cik_reconciled = 0
        acceptance_decisions = 0
        structured_xml_markers = 0
        legacy_cusip_markers = 0
        unambiguous_mappings = 0
        unique_subject_ciks: set[str] = set()
        mapping_statuses: Counter[str] = Counter()
        item4_markers = 0
        event_date_markers = 0

        for index, row in enumerate(sample, start=1):
            try:
                document = self._cached_submission(row)
                metadata = parse_submission_metadata(document.text)
                parsed_per_stratum[row.stratum] += 1

                accession_ok = metadata.accession_number == row.accession_number
                form_ok = metadata.form == row.form
                subject_ok = metadata.subject_cik == row.index_cik
                filing_date_ok = metadata.filing_date == row.filing_date
                if accession_ok:
                    accession_reconciled += 1
                if form_ok:
                    form_reconciled += 1
                if filing_date_ok:
                    filing_date_reconciled += 1
                if subject_ok:
                    subject_cik_reconciled += 1
                    unique_subject_ciks.add(row.index_cik)
                if row.era == "structured" and metadata.structured_primary_xml_marker:
                    structured_xml_markers += 1
                if row.era == "legacy" and metadata.cusip_marker:
                    legacy_cusip_markers += 1
                if metadata.item4_marker:
                    item4_markers += 1
                if metadata.event_date_marker:
                    event_date_markers += 1

                decision_date = None
                identity = {
                    "status": "NOT_ATTEMPTED",
                    "unique_instrument_count": 0,
                    "instruments": [],
                    "mapping_evidence": [],
                }
                if metadata.acceptance_datetime:
                    decision_date = _decision_session(metadata.acceptance_datetime)
                    acceptance_decisions += 1
                if subject_ok and decision_date is not None:
                    reference_rows = self._cached_reference(cik=row.index_cik, as_of_date=decision_date)
                    identity = _resolve_identity(
                        reference_rows, subject_cik=row.index_cik, as_of_date=decision_date
                    )
                    mapping_statuses[identity["status"]] += 1
                    if identity["status"] == "UNAMBIGUOUS_PIT_INSTRUMENT":
                        unambiguous_mappings += 1

                sampled_reports.append(
                    {
                        "index_row": asdict(row),
                        "submission_source_url": document.source_url,
                        "submission_source_sha256": document.source_sha256,
                        "metadata": asdict(metadata),
                        "accession_reconciled": accession_ok,
                        "form_reconciled": form_ok,
                        "subject_cik_reconciled": subject_ok,
                        "filing_date_reconciled": filing_date_ok,
                        "decision_session": decision_date.isoformat() if decision_date else None,
                        "identity": identity,
                    }
                )
            except Exception as exc:
                submission_failures.append(
                    {
                        "accession_number": row.accession_number,
                        "stratum": row.stratum,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
            if index == 1 or index % 10 == 0 or index == len(sample):
                print(
                    f"Beneficial-ownership submission progress: {index}/{len(sample)} "
                    f"parsed={len(sampled_reports)} failures={len(submission_failures)} unambiguous={unambiguous_mappings}"
                )

        stratum_discovery_gate = {
            stratum: int(discovered_by_stratum.get(stratum, 0)) >= BENEFICIAL_OWNERSHIP_MIN_DISCOVERED_PER_STRATUM
            for stratum in BENEFICIAL_OWNERSHIP_STRATA
        }
        stratum_sample_exact = {
            stratum: int(sample_by_stratum.get(stratum, 0)) == BENEFICIAL_OWNERSHIP_SAMPLE_PER_STRATUM
            for stratum in BENEFICIAL_OWNERSHIP_STRATA
        }
        stratum_parsed_gate = {
            stratum: int(parsed_per_stratum.get(stratum, 0)) >= BENEFICIAL_OWNERSHIP_MIN_PARSED_PER_STRATUM
            for stratum in BENEFICIAL_OWNERSHIP_STRATA
        }
        gates = {
            "quarter_indexes_exact": len(index_reports) == BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT and not index_failures,
            "discovered_per_stratum_min": all(stratum_discovery_gate.values()),
            "sample_per_stratum_exact": all(stratum_sample_exact.values()),
            "sample_size_exact": len(sample) == BENEFICIAL_OWNERSHIP_SAMPLE_SIZE,
            "submission_success_min": len(sampled_reports) >= BENEFICIAL_OWNERSHIP_MIN_SUBMISSION_SUCCESS,
            "accession_reconciled_min": accession_reconciled >= BENEFICIAL_OWNERSHIP_MIN_ACCESSION_RECONCILED,
            "form_reconciled_min": form_reconciled >= BENEFICIAL_OWNERSHIP_MIN_FORM_RECONCILED,
            "filing_date_reconciled_min": filing_date_reconciled >= BENEFICIAL_OWNERSHIP_MIN_FILING_DATE_RECONCILED,
            "subject_cik_reconciled_min": subject_cik_reconciled >= BENEFICIAL_OWNERSHIP_MIN_SUBJECT_CIK_RECONCILED,
            "acceptance_decisions_min": acceptance_decisions >= BENEFICIAL_OWNERSHIP_MIN_ACCEPTANCE_DECISIONS,
            "unique_subject_ciks_min": len(unique_subject_ciks) >= BENEFICIAL_OWNERSHIP_MIN_UNIQUE_SUBJECT_CIKS,
            "structured_xml_markers_min": structured_xml_markers >= BENEFICIAL_OWNERSHIP_MIN_STRUCTURED_XML_MARKERS,
            "legacy_cusip_markers_min": legacy_cusip_markers >= BENEFICIAL_OWNERSHIP_MIN_LEGACY_CUSIP_MARKERS,
            "unambiguous_common_stock_mappings_min": unambiguous_mappings >= BENEFICIAL_OWNERSHIP_MIN_UNAMBIGUOUS_COMMON_STOCK_MAPPINGS,
            "parsed_per_stratum_min": all(stratum_parsed_gate.values()),
        }
        passed = all(gates.values())

        report = {
            "contract_version": BENEFICIAL_OWNERSHIP_FEASIBILITY_CONTRACT,
            "feasibility_fingerprint": BENEFICIAL_OWNERSHIP_FEASIBILITY_FINGERPRINT,
            "source_xbrl_merge": BENEFICIAL_OWNERSHIP_SOURCE_XBRL_MERGE,
            "mechanism": BENEFICIAL_OWNERSHIP_MECHANISM,
            "status": "FEASIBILITY_PASS" if passed else "FEASIBILITY_FAIL",
            "pass": passed,
            "alpha_hypotheses_frozen": False,
            "performance_evaluated": False,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
            "protected_holdout_consumed": False,
            "provider_reads_allowed": True,
            "provider_reads_performed": int(sum(self.source_reads.values())),
            "provider_read_breakdown": dict(sorted(self.source_reads.items())),
            "cache_hit_breakdown": dict(sorted(self.cache_hits.items())),
            "provider_writes_performed": 0,
            "broker_reads_performed": 0,
            "broker_writes_performed": 0,
            "order_writes_performed": 0,
            "paper_submits_performed": 0,
            "live_writes_performed": 0,
            "automation_writes_performed": 0,
            "automatic_broker_failover": False,
            "source_start": BENEFICIAL_OWNERSHIP_SOURCE_START.isoformat(),
            "source_cutoff": BENEFICIAL_OWNERSHIP_SOURCE_CUTOFF.isoformat(),
            "structured_compliance_date": BENEFICIAL_OWNERSHIP_STRUCTURED_COMPLIANCE_DATE.isoformat(),
            "quarter_index_count": BENEFICIAL_OWNERSHIP_QUARTER_INDEX_COUNT,
            "successful_indexes": len(index_reports),
            "failed_indexes": len(index_failures),
            "discovered_eligible_filings": len(discovered),
            "discovered_by_stratum": dict(sorted(discovered_by_stratum.items())),
            "sample_rule": "HASH_RANK_ACCESSION_WITHIN_ERA_X_FORM_CLASS_STRATUM",
            "sample_size": len(sample),
            "sample_by_stratum": dict(sorted(sample_by_stratum.items())),
            "submission_success": len(sampled_reports),
            "submission_failures": len(submission_failures),
            "parsed_per_stratum": dict(sorted(parsed_per_stratum.items())),
            "accession_reconciled": accession_reconciled,
            "form_reconciled": form_reconciled,
            "filing_date_reconciled": filing_date_reconciled,
            "subject_cik_reconciled": subject_cik_reconciled,
            "acceptance_decisions": acceptance_decisions,
            "unique_subject_ciks": len(unique_subject_ciks),
            "structured_xml_markers": structured_xml_markers,
            "legacy_cusip_markers": legacy_cusip_markers,
            "item4_markers_diagnostic": item4_markers,
            "event_date_markers_diagnostic": event_date_markers,
            "unambiguous_common_stock_mappings": unambiguous_mappings,
            "mapping_statuses": dict(sorted(mapping_statuses.items())),
            "stratum_discovery_gate": stratum_discovery_gate,
            "stratum_sample_exact": stratum_sample_exact,
            "stratum_parsed_gate": stratum_parsed_gate,
            "gates": gates,
            "index_reports": index_reports,
            "index_failures": index_failures,
            "sampled_reports": sampled_reports,
            "failures": submission_failures,
            "next_scientific_action": (
                "If feasibility passes, freeze a finite Schedule 13D/13G alpha family, exact ownership/purpose semantics, "
                "chronology, outcomes, costs, dependence, multiplicity, robustness, winner/finalist rules, and protected "
                "policy before any market outcomes."
            ),
        }

        report_path = self.derived_root / BENEFICIAL_OWNERSHIP_REPORT_RELATIVE
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(report_path)
        return report
