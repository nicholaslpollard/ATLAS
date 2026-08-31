from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Callable, Iterable

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.providers.sec_13f_datasets import (
    SEC13FDatasetArchive,
    SEC13FDatasetClient,
    SEC_13F_DATASET_MAX_RESPONSE_BYTES,
    SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES,
    SEC_13F_REQUIRED_TABLES,
    validate_13f_zip_structure,
)


SEC_13F_FEASIBILITY_CONTRACT = (
    "alpha-gate-sec-13f-feasibility-v1-official-bulk-source-only-no-market-outcomes"
)
SEC_13F_FEASIBILITY_FINGERPRINT = (
    "8959769669d4c2e51b86627b8c03a67509a339698025683108cbda4e287fb310"
)
SEC_13F_SOURCE_MAIN_MERGE = "579e94d0dfe861e37c25d2d67099f44c4f1c2351"
SEC_13F_MECHANISM_CANDIDATE = (
    "PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION"
)
SEC_13F_SOURCE = (
    "SEC_FORM13F_QUARTERLY_DATASETS:"
    "www.sec.gov/files/structureddata/data/form-13f-data-sets"
)
SEC_13F_ANCHORS = (
    (
        "2016Q1",
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
        "2016q1_form13f.zip",
    ),
    (
        "2020Q2",
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
        "2020q2_form13f.zip",
    ),
    (
        "2023Q1",
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
        "2023q1_form13f.zip",
    ),
    (
        "2025MAM",
        "https://www.sec.gov/files/structureddata/data/form-13f-data-sets/"
        "01mar2025-31may2025_form13f.zip",
    ),
)
SEC_13F_ALLOWED_SUBMISSION_TYPES = ("13F-HR", "13F-HR/A", "13F-NT", "13F-NT/A")
SEC_13F_MIN_INITIAL_HR_SUBMISSIONS_PER_ANCHOR = 500
SEC_13F_MIN_INITIAL_HR_INFOTABLE_ROWS_PER_ANCHOR = 50_000
SEC_13F_MIN_UNIQUE_INITIAL_HR_MANAGERS_PER_ANCHOR = 500
SEC_13F_MIN_VALID_INITIAL_HR_CUSIP_FRACTION = 0.995
SEC_13F_MAX_SUBMISSION_ACCESSION_DUPLICATES = 0
SEC_13F_MAX_INFOTABLE_PRIMARY_KEY_DUPLICATES = 0
SEC_13F_MAX_INFOTABLE_ORPHAN_ROWS = 0
SEC_13F_MAX_INITIAL_HR_FILING_BEFORE_PERIOD_VIOLATIONS = 0
SEC_13F_MIN_CALENDAR_YEAR_SPAN_INCLUSIVE = 10
SEC_13F_PROTECTED_SOURCE_CUTOFF = date(2025, 5, 31)
SEC_13F_ALPHA_HYPOTHESES_FROZEN = False
SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY = False
SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED = False
SEC_13F_ORIGINAL_FILING_RECONCILIATION_REQUIRED_LATER = True
SEC_13F_TARGET_OUTCOME_READS_ALLOWED = False
SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED = False
SEC_13F_PROVIDER_READS_ALLOWED = True
SEC_13F_PROVIDER_WRITES = 0
SEC_13F_BROKER_READS = 0
SEC_13F_BROKER_WRITES = 0
SEC_13F_ORDER_WRITES = 0
SEC_13F_PAPER_SUBMITS = 0
SEC_13F_LIVE_WRITES = 0
SEC_13F_AUTOMATION_WRITES = 0
SEC_13F_AUTOMATIC_BROKER_FAILOVER = False
SEC_13F_PHASE33_SIGNAL_TO_TRADE_AUTHORITY = False

SEC_13F_RAW_RELATIVE = Path("regulatory/sec/form13f/feasibility_v1")
SEC_13F_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_13f_feasibility_v1/source_census.json"
)

_REQUIRED_SUBMISSION_FIELDS = {
    "ACCESSION_NUMBER",
    "FILING_DATE",
    "SUBMISSIONTYPE",
    "CIK",
    "PERIODOFREPORT",
}
_REQUIRED_COVERPAGE_FIELDS = {
    "ACCESSION_NUMBER",
    "REPORTCALENDARORQUARTER",
    "FILINGMANAGER_NAME",
    "REPORTTYPE",
}
_REQUIRED_INFOTABLE_FIELDS = {
    "ACCESSION_NUMBER",
    "INFOTABLE_SK",
    "NAMEOFISSUER",
    "TITLEOFCLASS",
    "CUSIP",
    "VALUE",
    "SSHPRNAMT",
    "SSHPRNAMTTYPE",
    "PUTCALL",
    "INVESTMENTDISCRETION",
    "VOTING_AUTH_SOLE",
    "VOTING_AUTH_SHARED",
    "VOTING_AUTH_NONE",
}
_MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


class SEC13FFeasibilityError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": SEC_13F_FEASIBILITY_CONTRACT,
        "source_main_merge": SEC_13F_SOURCE_MAIN_MERGE,
        "mechanism_candidate": SEC_13F_MECHANISM_CANDIDATE,
        "source": SEC_13F_SOURCE,
        "anchors": [{"label": label, "url": url} for label, url in SEC_13F_ANCHORS],
        "required_tables": list(SEC_13F_REQUIRED_TABLES),
        "allowed_submission_types": list(SEC_13F_ALLOWED_SUBMISSION_TYPES),
        "min_initial_hr_submissions_per_anchor": SEC_13F_MIN_INITIAL_HR_SUBMISSIONS_PER_ANCHOR,
        "min_initial_hr_infotable_rows_per_anchor": SEC_13F_MIN_INITIAL_HR_INFOTABLE_ROWS_PER_ANCHOR,
        "min_unique_initial_hr_managers_per_anchor": SEC_13F_MIN_UNIQUE_INITIAL_HR_MANAGERS_PER_ANCHOR,
        "min_valid_initial_hr_cusip_fraction": SEC_13F_MIN_VALID_INITIAL_HR_CUSIP_FRACTION,
        "max_submission_accession_duplicates": SEC_13F_MAX_SUBMISSION_ACCESSION_DUPLICATES,
        "max_infotable_primary_key_duplicates": SEC_13F_MAX_INFOTABLE_PRIMARY_KEY_DUPLICATES,
        "max_infotable_orphan_rows": SEC_13F_MAX_INFOTABLE_ORPHAN_ROWS,
        "max_initial_hr_filing_before_period_violations": SEC_13F_MAX_INITIAL_HR_FILING_BEFORE_PERIOD_VIOLATIONS,
        "min_calendar_year_span_inclusive": SEC_13F_MIN_CALENDAR_YEAR_SPAN_INCLUSIVE,
        "max_compressed_bytes_per_anchor": SEC_13F_DATASET_MAX_RESPONSE_BYTES,
        "max_uncompressed_bytes_per_anchor": SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES,
        "protected_source_cutoff": SEC_13F_PROTECTED_SOURCE_CUTOFF.isoformat(),
        "alpha_hypotheses_frozen": SEC_13F_ALPHA_HYPOTHESES_FROZEN,
        "cusip_to_atlas_identity_authority": SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY,
        "full_history_acquisition_allowed": SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED,
        "original_filing_reconciliation_required_later": SEC_13F_ORIGINAL_FILING_RECONCILIATION_REQUIRED_LATER,
        "target_outcome_reads_allowed": SEC_13F_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": SEC_13F_PROVIDER_READS_ALLOWED,
        "provider_writes": SEC_13F_PROVIDER_WRITES,
        "broker_reads": SEC_13F_BROKER_READS,
        "broker_writes": SEC_13F_BROKER_WRITES,
        "order_writes": SEC_13F_ORDER_WRITES,
        "paper_submits": SEC_13F_PAPER_SUBMITS,
        "live_writes": SEC_13F_LIVE_WRITES,
        "automation_writes": SEC_13F_AUTOMATION_WRITES,
        "automatic_broker_failover": SEC_13F_AUTOMATIC_BROKER_FAILOVER,
        "phase33_signal_to_trade_authority": SEC_13F_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
    }


def sec_13f_feasibility_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def _parse_sec_date(value: object) -> date | None:
    text = str(value or "").strip().upper()
    match = re.fullmatch(r"(\d{2})-([A-Z]{3})-(\d{4})", text)
    if match is None:
        return None
    day = int(match.group(1)); month = _MONTHS.get(match.group(2)); year = int(match.group(3))
    if month is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _table_members(archive: SEC13FDatasetArchive) -> dict[str, str]:
    structure = validate_13f_zip_structure(archive)
    members = structure.get("table_members")
    if not isinstance(members, dict):
        raise SEC13FFeasibilityError("SEC 13F ZIP table-member map is missing")
    return {str(key): str(value) for key, value in members.items()}


def _rows(handle: zipfile.ZipFile, member: str, required_fields: set[str]) -> Iterable[dict[str, str]]:
    with handle.open(member, "r") as raw:
        with io.TextIOWrapper(raw, encoding="utf-8-sig", newline="") as text:
            reader = csv.DictReader(text, delimiter="\t")
            fields = {str(field or "").strip() for field in (reader.fieldnames or [])}
            missing = sorted(required_fields - fields)
            if missing:
                raise SEC13FFeasibilityError(f"{member} missing required columns: {','.join(missing)}")
            for row in reader:
                yield {str(key or "").strip(): str(value or "").strip() for key, value in row.items()}


def _analyze_archive(label: str, archive: SEC13FDatasetArchive) -> dict[str, Any]:
    structure = validate_13f_zip_structure(archive)
    members = _table_members(archive)
    submissions: dict[str, dict[str, str]] = {}
    submission_types: Counter[str] = Counter()
    submission_duplicates = 0; invalid_submission_types = 0
    initial_hr_ciks: set[str] = set(); initial_hr_period_years: set[int] = set()
    initial_hr_filing_before_period = 0; max_filing_date: date | None = None

    with zipfile.ZipFile(io.BytesIO(archive.raw_bytes)) as handle:
        for row in _rows(handle, members["SUBMISSION.tsv"], _REQUIRED_SUBMISSION_FIELDS):
            accession = row["ACCESSION_NUMBER"]
            if not accession:
                raise SEC13FFeasibilityError(f"{label}: blank SUBMISSION accession")
            if accession in submissions:
                submission_duplicates += 1; continue
            submission_type = row["SUBMISSIONTYPE"]
            submission_types[submission_type] += 1
            if submission_type not in SEC_13F_ALLOWED_SUBMISSION_TYPES:
                invalid_submission_types += 1
            filing = _parse_sec_date(row["FILING_DATE"]); period = _parse_sec_date(row["PERIODOFREPORT"])
            if filing is None or period is None:
                raise SEC13FFeasibilityError(f"{label}: invalid SUBMISSION filing/period date for {accession}")
            max_filing_date = filing if max_filing_date is None else max(max_filing_date, filing)
            submissions[accession] = row
            if submission_type == "13F-HR":
                cik = row["CIK"]
                if not cik.isdigit():
                    raise SEC13FFeasibilityError(f"{label}: initial 13F-HR contains nonnumeric CIK {cik!r}")
                initial_hr_ciks.add(str(int(cik))); initial_hr_period_years.add(period.year)
                if filing < period:
                    initial_hr_filing_before_period += 1

        initial_hr_manager_names: set[str] = set(); coverpage_orphans = 0
        for row in _rows(handle, members["COVERPAGE.tsv"], _REQUIRED_COVERPAGE_FIELDS):
            accession = row["ACCESSION_NUMBER"]; submission = submissions.get(accession)
            if submission is None:
                coverpage_orphans += 1; continue
            if submission["SUBMISSIONTYPE"] == "13F-HR" and row["FILINGMANAGER_NAME"]:
                initial_hr_manager_names.add(row["FILINGMANAGER_NAME"])

        infotable_rows = 0; initial_hr_infotable_rows = 0; orphan_infotable_rows = 0; duplicate_info_keys = 0
        seen_info_keys: set[tuple[str, str]] = set(); valid_cusip_rows = 0; figi_populated_rows = 0
        initial_hr_unique_cusips: set[str] = set(); putcall_counts: Counter[str] = Counter()
        for row in _rows(handle, members["INFOTABLE.tsv"], _REQUIRED_INFOTABLE_FIELDS):
            infotable_rows += 1; accession = row["ACCESSION_NUMBER"]; info_key = (accession, row["INFOTABLE_SK"])
            if info_key in seen_info_keys: duplicate_info_keys += 1
            else: seen_info_keys.add(info_key)
            submission = submissions.get(accession)
            if submission is None:
                orphan_infotable_rows += 1; continue
            if submission["SUBMISSIONTYPE"] != "13F-HR": continue
            initial_hr_infotable_rows += 1; cusip = row["CUSIP"].strip()
            if len(cusip) == 9:
                valid_cusip_rows += 1; initial_hr_unique_cusips.add(cusip)
            if str(row.get("FIGI") or "").strip(): figi_populated_rows += 1
            putcall_counts[str(row.get("PUTCALL") or "").strip().upper() or "NONE"] += 1

    valid_cusip_fraction = valid_cusip_rows / initial_hr_infotable_rows if initial_hr_infotable_rows else 0.0
    return {
        "label": label, "source_url": archive.source_url, "source_sha256": archive.source_sha256,
        "compressed_bytes": archive.compressed_bytes, "member_count": int(structure["member_count"]),
        "total_uncompressed_bytes": int(structure["total_uncompressed_bytes"]), "required_tables": list(SEC_13F_REQUIRED_TABLES),
        "submission_rows": len(submissions) + submission_duplicates, "unique_submission_accessions": len(submissions),
        "submission_accession_duplicates": submission_duplicates, "submission_type_counts": dict(sorted(submission_types.items())),
        "invalid_submission_types": invalid_submission_types, "initial_hr_submissions": submission_types["13F-HR"],
        "initial_hr_unique_ciks": len(initial_hr_ciks), "initial_hr_unique_manager_names": len(initial_hr_manager_names),
        "coverpage_orphan_rows": coverpage_orphans, "initial_hr_period_years": sorted(initial_hr_period_years),
        "initial_hr_filing_before_period_violations": initial_hr_filing_before_period,
        "max_filing_date": max_filing_date.isoformat() if max_filing_date else None,
        "infotable_rows": infotable_rows, "initial_hr_infotable_rows": initial_hr_infotable_rows,
        "infotable_orphan_rows": orphan_infotable_rows, "infotable_primary_key_duplicates": duplicate_info_keys,
        "initial_hr_valid_cusip_rows": valid_cusip_rows, "initial_hr_valid_cusip_fraction": valid_cusip_fraction,
        "initial_hr_unique_cusips": len(initial_hr_unique_cusips), "initial_hr_figi_populated_rows": figi_populated_rows,
        "initial_hr_putcall_counts": dict(sorted(putcall_counts.items())),
    }


def _atomic_write_bytes(path: Path, raw: bytes) -> None:
    temp = unique_temp_path(path)
    try:
        with temp.open("wb") as handle:
            handle.write(raw); handle.flush()
        replace_with_retry(temp, path)
    except Exception:
        try: temp.unlink(missing_ok=True)
        except OSError: pass
        raise


def _archive_from_local(path: Path, url: str) -> SEC13FDatasetArchive:
    if path.stat().st_size > SEC_13F_DATASET_MAX_RESPONSE_BYTES:
        raise SEC13FFeasibilityError(f"local SEC 13F archive exceeds frozen cap: {path}")
    raw = path.read_bytes()
    archive = SEC13FDatasetArchive(source_url=url, source_sha256=hashlib.sha256(raw).hexdigest(), raw_bytes=raw)
    validate_13f_zip_structure(archive); return archive


def _gate_results(anchors: list[dict[str, Any]]) -> dict[str, bool]:
    years = sorted({int(year) for anchor in anchors for year in anchor.get("initial_hr_period_years", [])})
    span = years[-1] - years[0] + 1 if years else 0
    return {
        "anchor_count_exact": len(anchors) == len(SEC_13F_ANCHORS),
        "required_tables_all_anchors": all(anchor.get("required_tables") == list(SEC_13F_REQUIRED_TABLES) for anchor in anchors),
        "initial_hr_submissions_min_all_anchors": all(int(anchor.get("initial_hr_submissions") or 0) >= SEC_13F_MIN_INITIAL_HR_SUBMISSIONS_PER_ANCHOR for anchor in anchors),
        "initial_hr_infotable_rows_min_all_anchors": all(int(anchor.get("initial_hr_infotable_rows") or 0) >= SEC_13F_MIN_INITIAL_HR_INFOTABLE_ROWS_PER_ANCHOR for anchor in anchors),
        "initial_hr_managers_min_all_anchors": all(int(anchor.get("initial_hr_unique_ciks") or 0) >= SEC_13F_MIN_UNIQUE_INITIAL_HR_MANAGERS_PER_ANCHOR for anchor in anchors),
        "valid_cusip_fraction_min_all_anchors": all(float(anchor.get("initial_hr_valid_cusip_fraction") or 0.0) >= SEC_13F_MIN_VALID_INITIAL_HR_CUSIP_FRACTION for anchor in anchors),
        "submission_accession_duplicates_max": all(int(anchor.get("submission_accession_duplicates") or 0) <= SEC_13F_MAX_SUBMISSION_ACCESSION_DUPLICATES for anchor in anchors),
        "infotable_primary_key_duplicates_max": all(int(anchor.get("infotable_primary_key_duplicates") or 0) <= SEC_13F_MAX_INFOTABLE_PRIMARY_KEY_DUPLICATES for anchor in anchors),
        "infotable_orphan_rows_max": all(int(anchor.get("infotable_orphan_rows") or 0) <= SEC_13F_MAX_INFOTABLE_ORPHAN_ROWS for anchor in anchors),
        "initial_hr_chronology_violations_max": all(int(anchor.get("initial_hr_filing_before_period_violations") or 0) <= SEC_13F_MAX_INITIAL_HR_FILING_BEFORE_PERIOD_VIOLATIONS for anchor in anchors),
        "calendar_year_span_min": span >= SEC_13F_MIN_CALENDAR_YEAR_SPAN_INCLUSIVE,
        "protected_source_cutoff_respected": all(anchor.get("max_filing_date") is not None and date.fromisoformat(str(anchor["max_filing_date"])) <= SEC_13F_PROTECTED_SOURCE_CUTOFF for anchor in anchors),
        "invalid_submission_types_zero": all(int(anchor.get("invalid_submission_types") or 0) == 0 for anchor in anchors),
    }


class SEC13FFeasibility:
    """Bounded source-only census of official SEC Form 13F bulk data sets."""
    def __init__(self, settings: AtlasSettings, sec_client: SEC13FDatasetClient, *, progress: Callable[[str], None] | None = None) -> None:
        self.settings = settings; self.sec_client = sec_client; self.progress = progress or (lambda _message: None)

    def _existing_report(self, report_path: Path, raw_root: Path) -> dict[str, Any] | None:
        if not report_path.is_file(): return None
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("contract_version") != SEC_13F_FEASIBILITY_CONTRACT: raise SEC13FFeasibilityError("existing SEC 13F feasibility report contract drifted")
        if report.get("policy_fingerprint") != SEC_13F_FEASIBILITY_FINGERPRINT: raise SEC13FFeasibilityError("existing SEC 13F feasibility report fingerprint drifted")
        for anchor in report.get("anchors", []):
            if not isinstance(anchor, dict): raise SEC13FFeasibilityError("existing SEC 13F feasibility anchor is malformed")
            url = str(anchor.get("source_url") or ""); filename = SEC13FDatasetClient.validate_url(url); path = raw_root / filename
            if not path.is_file(): raise SEC13FFeasibilityError(f"accepted SEC 13F raw anchor is missing; do not silently refetch: {path}")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != anchor.get("source_sha256"): raise SEC13FFeasibilityError(f"accepted SEC 13F raw anchor hash changed: {path}")
        return report

    def run(self) -> dict[str, Any]:
        if sec_13f_feasibility_fingerprint() != SEC_13F_FEASIBILITY_FINGERPRINT: raise SEC13FFeasibilityError("frozen SEC 13F feasibility fingerprint drifted")
        canonical_root = self.settings.resolved_path(self.settings.data.paths.canonical); derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        raw_root = canonical_root / SEC_13F_RAW_RELATIVE; report_path = derived_root / SEC_13F_REPORT_RELATIVE
        existing = self._existing_report(report_path, raw_root)
        if existing is not None:
            self.progress("SEC 13F feasibility evidence already exists and hash-valid; returning immutable report."); return existing
        raw_root.mkdir(parents=True, exist_ok=True); anchors: list[dict[str, Any]] = []; provider_reads = 0; local_source_files_created = 0
        for index, (label, url) in enumerate(SEC_13F_ANCHORS, start=1):
            filename = SEC13FDatasetClient.validate_url(url); path = raw_root / filename; self.progress(f"SEC 13F anchor {index}/{len(SEC_13F_ANCHORS)}: {label}")
            if path.is_file(): archive = _archive_from_local(path, url); source_mode = "LOCAL_IMMUTABLE_SOURCE"
            else:
                archive = self.sec_client.fetch(url); provider_reads += 1; _atomic_write_bytes(path, archive.raw_bytes); local_source_files_created += 1; source_mode = "OFFICIAL_SEC_FETCH_PERSISTED_IMMUTABLY"
            report = _analyze_archive(label, archive); report["source_mode"] = source_mode; report["local_path"] = str(path); anchors.append(report)
            self.progress(f"  {label}: submissions={report['initial_hr_submissions']} holdings={report['initial_hr_infotable_rows']} valid_cusip={report['initial_hr_valid_cusip_fraction']:.6f}")
        gates = _gate_results(anchors); period_years = sorted({int(year) for anchor in anchors for year in anchor.get("initial_hr_period_years", [])})
        result = {
            "contract_version": SEC_13F_FEASIBILITY_CONTRACT, "policy_fingerprint": SEC_13F_FEASIBILITY_FINGERPRINT,
            "source_main_merge": SEC_13F_SOURCE_MAIN_MERGE, "mechanism_candidate": SEC_13F_MECHANISM_CANDIDATE,
            "source": SEC_13F_SOURCE, "status": "FEASIBILITY_PASS" if all(gates.values()) else "FEASIBILITY_FAIL", "pass": all(gates.values()),
            "anchors": anchors, "calendar_years_observed": period_years, "calendar_year_span_inclusive": period_years[-1] - period_years[0] + 1 if period_years else 0, "gates": gates,
            "governance": {
                "alpha_hypotheses_frozen": SEC_13F_ALPHA_HYPOTHESES_FROZEN, "cusip_to_atlas_identity_authority": SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY,
                "full_history_acquisition_allowed": SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED, "original_filing_reconciliation_required_later": SEC_13F_ORIGINAL_FILING_RECONCILIATION_REQUIRED_LATER,
                "target_outcome_rows_read": 0, "protected_return_rows_read": 0, "protected_holdout_consumed": False,
                "provider_reads_performed": provider_reads, "provider_writes_performed": SEC_13F_PROVIDER_WRITES, "local_source_files_created": local_source_files_created,
                "broker_reads_performed": SEC_13F_BROKER_READS, "broker_writes_performed": SEC_13F_BROKER_WRITES, "order_writes_performed": SEC_13F_ORDER_WRITES,
                "paper_submits_performed": SEC_13F_PAPER_SUBMITS, "live_writes_performed": SEC_13F_LIVE_WRITES, "automation_writes_performed": SEC_13F_AUTOMATION_WRITES,
                "automatic_broker_failover": SEC_13F_AUTOMATIC_BROKER_FAILOVER, "phase33_signal_to_trade_authority": SEC_13F_PHASE33_SIGNAL_TO_TRADE_AUTHORITY,
            },
            "next_scientific_action": "IF_FEASIBILITY_PASS_FREEZE_FULL_SOURCE_ACQUISITION_ORIGINAL_EDGAR_RECONCILIATION_AND_CUSIP_TO_ATLAS_PIT_IDENTITY_BEFORE_OUTCOMES",
        }
        atomic_write_text(report_path, json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n"); return result
