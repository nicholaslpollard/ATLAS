from __future__ import annotations

import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Callable

from packages.backtesting.alpha_gate_sec_13f_cusip_diagnostic import (
    SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR,
    SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT,
    SEC_13F_CUSIP_DIAGNOSTIC_REPORT_RELATIVE,
)
from packages.backtesting.alpha_gate_sec_13f_feasibility import (
    SEC13FFeasibilityError,
    _REQUIRED_INFOTABLE_FIELDS,
    _REQUIRED_SUBMISSION_FIELDS,
    _archive_from_local,
    _rows,
    _table_members,
)
from packages.backtesting.alpha_gate_sec_13f_feasibility_v2 import (
    SEC_13F_FEASIBILITY_V2_CONTRACT,
    SEC_13F_FEASIBILITY_V2_FINGERPRINT,
    SEC_13F_RAW_RELATIVE_V2,
    SEC_13F_REPORT_RELATIVE_V2,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_13f_datasets import SEC13FDatasetClient
from packages.providers.sec_edgar_archive import (
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
    SECEDGARArchiveClient,
    sec_archive_submission_url,
)


SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT = (
    "alpha-gate-sec-13f-original-edgar-reconciliation-v1-all-malformed-accessions-source-only-no-market-outcomes"
)
SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT = (
    "6b28e6e7eac599d1f795fed2de200c0886f49b91af29a699faa98a043521c91c"
)
SEC_13F_ORIGINAL_EDGAR_SOURCE = "SEC_EDGAR_COMPLETE_SUBMISSION"
SEC_13F_ORIGINAL_EDGAR_PATH_TEMPLATE = (
    "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}.txt"
)
SEC_13F_ORIGINAL_EDGAR_CUSIP_TAG_SOURCE = "ORIGINAL_13F_INFORMATION_TABLE_XML"
SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS = 374
SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS = 10_431
SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED = False
SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED = False
SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED = False
SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED = False
SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED = False
SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY = False
SEC_13F_ORIGINAL_EDGAR_RAW_RELATIVE = Path(
    "regulatory/sec/form13f/original_edgar_reconciliation_v1/2016Q1"
)
SEC_13F_ORIGINAL_EDGAR_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_13f_feasibility_v2/"
    "original_edgar_reconciliation_v1.json"
)

_XML_BLOCK_RE = re.compile(r"<XML>\s*(.*?)\s*</XML>", re.IGNORECASE | re.DOTALL)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
        "gate0_contract": SEC_13F_FEASIBILITY_V2_CONTRACT,
        "gate0_fingerprint": SEC_13F_FEASIBILITY_V2_FINGERPRINT,
        "diagnostic_contract": SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT,
        "anchor": SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR,
        "expected_malformed_accessions": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
        "expected_malformed_rows": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS,
        "source": SEC_13F_ORIGINAL_EDGAR_SOURCE,
        "source_path_template": SEC_13F_ORIGINAL_EDGAR_PATH_TEMPLATE,
        "max_submission_bytes": SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
        "cusip_tag_source": SEC_13F_ORIGINAL_EDGAR_CUSIP_TAG_SOURCE,
        "cusip_repair_allowed": SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
        "atlas_identity_allowed": SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
        "target_outcomes_allowed": SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
        "protected_outcomes_allowed": SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
        "scientific_freeze_allowed": SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
        "phase33_signal_to_trade_authority": SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
    }


def sec_13f_original_edgar_reconciliation_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def extract_original_13f_cusips(text: str) -> dict[str, Any]:
    """Extract CUSIP elements from original EDGAR XML blocks without modifying values."""
    blocks = _XML_BLOCK_RE.findall(text)
    cusips: list[str] = []
    parse_errors: list[str] = []
    parsed_blocks = 0
    for block in blocks:
        try:
            root = ET.fromstring(block)
        except ET.ParseError as exc:
            parse_errors.append(str(exc))
            continue
        parsed_blocks += 1
        for element in root.iter():
            local_name = str(element.tag).split("}")[-1].split(":")[-1].lower()
            if local_name != "cusip":
                continue
            cusips.append(str(element.text or "").strip())
    return {
        "xml_blocks": len(blocks),
        "xml_blocks_parsed": parsed_blocks,
        "xml_parse_errors": len(parse_errors),
        "xml_parse_error_samples": parse_errors[:5],
        "cusips": cusips,
    }


def _collect_bulk_affected(archive: Any) -> tuple[dict[str, dict[str, Any]], int]:
    members = _table_members(archive)
    submissions: dict[str, dict[str, str]] = {}
    affected: set[str] = set()
    malformed_rows = 0

    with zipfile.ZipFile(io.BytesIO(archive.raw_bytes)) as handle:
        for row in _rows(handle, members["SUBMISSION.tsv"], _REQUIRED_SUBMISSION_FIELDS):
            accession = row["ACCESSION_NUMBER"]
            if accession and accession not in submissions:
                submissions[accession] = row

        for row in _rows(handle, members["INFOTABLE.tsv"], _REQUIRED_INFOTABLE_FIELDS):
            accession = row["ACCESSION_NUMBER"]
            submission = submissions.get(accession)
            if submission is None or submission["SUBMISSIONTYPE"] != "13F-HR":
                continue
            if len(row["CUSIP"].strip()) != 9:
                affected.add(accession)
                malformed_rows += 1

    grouped: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(io.BytesIO(archive.raw_bytes)) as handle:
        for row in _rows(handle, members["INFOTABLE.tsv"], _REQUIRED_INFOTABLE_FIELDS):
            accession = row["ACCESSION_NUMBER"]
            if accession not in affected:
                continue
            submission = submissions.get(accession)
            if submission is None or submission["SUBMISSIONTYPE"] != "13F-HR":
                continue
            item = grouped.setdefault(
                accession,
                {
                    "accession": accession,
                    "cik": str(int(submission["CIK"])),
                    "bulk_cusips": [],
                },
            )
            item["bulk_cusips"].append(row["CUSIP"].strip())

    return grouped, malformed_rows


def _invalid_counter(values: list[str]) -> Counter[str]:
    return Counter(value for value in values if len(value) != 9)


def reconcile_accession_cusips(
    *,
    accession: str,
    cik: str,
    bulk_cusips: list[str],
    original_text: str,
    source_url: str,
    source_sha256: str,
    source_mode: str,
) -> dict[str, Any]:
    parsed = extract_original_13f_cusips(original_text)
    original_cusips = list(parsed["cusips"])
    bulk_counter = Counter(bulk_cusips)
    original_counter = Counter(original_cusips)
    bulk_invalid = _invalid_counter(bulk_cusips)
    original_invalid = _invalid_counter(original_cusips)

    exact_malformed_rows_preserved = sum(
        min(count, original_counter.get(value, 0)) for value, count in bulk_invalid.items()
    )
    padded_candidate_rows_in_original = sum(
        min(count, original_counter.get(value.rjust(9, "0"), 0))
        for value, count in bulk_invalid.items()
        if 0 < len(value) < 9
    )

    row_count_match = len(original_cusips) == len(bulk_cusips)
    exact_counter_match = row_count_match and original_counter == bulk_counter

    if int(parsed["xml_parse_errors"]) > 0 and not original_cusips:
        classification = "ORIGINAL_XML_PARSE_FAILURE"
    elif int(parsed["xml_parse_errors"]) > 0:
        classification = "ORIGINAL_XML_PARTIAL_PARSE"
    elif not original_cusips:
        classification = "NO_ORIGINAL_CUSIP_TAGS"
    elif not row_count_match:
        classification = "CUSIP_ROW_COUNT_MISMATCH"
    elif exact_counter_match and original_invalid:
        classification = "AS_FILED_MALFORMED_CUSIP_CONFIRMED"
    elif exact_counter_match:
        classification = "EXACT_COUNTER_MATCH_NO_MALFORMED_ORIGINAL"
    elif not original_invalid:
        classification = "BULK_FLATTENING_DIFFERS_FROM_VALID_ORIGINAL"
    elif exact_malformed_rows_preserved > 0:
        classification = "MIXED_AS_FILED_AND_BULK_DIFFERENCE"
    else:
        classification = "BULK_OR_SOURCE_DIFFERENCE_UNRESOLVED"

    return {
        "accession": accession,
        "cik": cik,
        "source_url": source_url,
        "source_sha256": source_sha256,
        "source_mode": source_mode,
        "classification": classification,
        "bulk_rows": len(bulk_cusips),
        "bulk_nine_char_cusip_rows": sum(1 for value in bulk_cusips if len(value) == 9),
        "bulk_malformed_cusip_rows": sum(bulk_invalid.values()),
        "bulk_unique_malformed_values": len(bulk_invalid),
        "original_cusip_rows": len(original_cusips),
        "original_nine_char_cusip_rows": sum(1 for value in original_cusips if len(value) == 9),
        "original_malformed_cusip_rows": sum(original_invalid.values()),
        "original_unique_malformed_values": len(original_invalid),
        "row_count_match": row_count_match,
        "exact_cusip_multiset_match": exact_counter_match,
        "bulk_malformed_rows_exactly_preserved_in_original": exact_malformed_rows_preserved,
        "bulk_short_rows_left_zero_pad_candidate_present_in_original": padded_candidate_rows_in_original,
        "xml_blocks": int(parsed["xml_blocks"]),
        "xml_blocks_parsed": int(parsed["xml_blocks_parsed"]),
        "xml_parse_errors": int(parsed["xml_parse_errors"]),
        "xml_parse_error_samples": list(parsed["xml_parse_error_samples"]),
        "bulk_top_malformed_values": [
            {"value": value, "rows": rows} for value, rows in bulk_invalid.most_common(10)
        ],
        "original_top_malformed_values": [
            {"value": value, "rows": rows} for value, rows in original_invalid.most_common(10)
        ],
    }


class SEC13FOriginalEdgarReconciliation:
    """Reconcile every malformed 2016Q1 bulk accession to its original EDGAR submission."""

    def __init__(
        self,
        settings: AtlasSettings,
        sec_archive_client: SECEDGARArchiveClient,
        *,
        progress: Callable[[str], None] | None = None,
    ) -> None:
        self.settings = settings
        self.sec_archive_client = sec_archive_client
        self.progress = progress or (lambda _message: None)

    def _existing_report(self, report_path: Path, raw_root: Path) -> dict[str, Any] | None:
        if not report_path.is_file():
            return None
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if report.get("contract_version") != SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT:
            raise SEC13FFeasibilityError("existing SEC 13F original-EDGAR report contract drifted")
        if report.get("policy_fingerprint") != SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT:
            raise SEC13FFeasibilityError("existing SEC 13F original-EDGAR report fingerprint drifted")
        for item in report.get("accessions", []):
            if not isinstance(item, dict):
                raise SEC13FFeasibilityError("existing SEC 13F original-EDGAR accession is malformed")
            accession = str(item.get("accession") or "")
            path = raw_root / f"{accession}.txt"
            if not path.is_file():
                raise SEC13FFeasibilityError(
                    f"accepted original EDGAR source is missing; do not silently refetch: {path}"
                )
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != item.get("source_sha256"):
                raise SEC13FFeasibilityError(f"accepted original EDGAR source hash changed: {path}")
        return report

    def run(self) -> dict[str, Any]:
        if (
            sec_13f_original_edgar_reconciliation_fingerprint()
            != SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT
        ):
            raise SEC13FFeasibilityError("frozen SEC 13F original-EDGAR fingerprint drifted")

        canonical_root = self.settings.resolved_path(self.settings.data.paths.canonical)
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        gate0_path = derived_root / SEC_13F_REPORT_RELATIVE_V2
        diagnostic_path = derived_root / SEC_13F_CUSIP_DIAGNOSTIC_REPORT_RELATIVE
        report_path = derived_root / SEC_13F_ORIGINAL_EDGAR_REPORT_RELATIVE
        raw_root = canonical_root / SEC_13F_ORIGINAL_EDGAR_RAW_RELATIVE

        existing = self._existing_report(report_path, raw_root)
        if existing is not None:
            self.progress(
                "SEC 13F original-EDGAR reconciliation already exists and is hash-valid; returning immutable report."
            )
            return existing

        if not gate0_path.is_file() or not diagnostic_path.is_file():
            raise SEC13FFeasibilityError(
                "preserved Gate0 and CUSIP diagnostic evidence are required before original EDGAR reconciliation"
            )
        gate0 = json.loads(gate0_path.read_text(encoding="utf-8"))
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        if gate0.get("contract_version") != SEC_13F_FEASIBILITY_V2_CONTRACT:
            raise SEC13FFeasibilityError("SEC 13F Gate0 contract drifted")
        if gate0.get("policy_fingerprint") != SEC_13F_FEASIBILITY_V2_FINGERPRINT:
            raise SEC13FFeasibilityError("SEC 13F Gate0 fingerprint drifted")
        if diagnostic.get("contract_version") != SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT:
            raise SEC13FFeasibilityError("SEC 13F CUSIP diagnostic contract drifted")
        if int(diagnostic.get("malformed_accessions") or 0) != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS:
            raise SEC13FFeasibilityError("SEC 13F malformed-accession count differs from frozen reconciliation scope")
        if int(diagnostic.get("malformed_rows") or 0) != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS:
            raise SEC13FFeasibilityError("SEC 13F malformed-row count differs from frozen reconciliation scope")

        anchor = next(
            (
                item
                for item in gate0.get("anchors", [])
                if isinstance(item, dict) and item.get("label") == SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR
            ),
            None,
        )
        if anchor is None:
            raise SEC13FFeasibilityError("SEC 13F Gate0 2016Q1 anchor is missing")
        source_url = str(anchor.get("source_url") or "")
        bulk_filename = SEC13FDatasetClient.validate_url(source_url)
        bulk_path = canonical_root / SEC_13F_RAW_RELATIVE_V2 / bulk_filename
        if not bulk_path.is_file():
            raise SEC13FFeasibilityError(
                f"preserved SEC 13F 2016Q1 bulk archive is missing; do not refetch: {bulk_path}"
            )
        bulk_sha = hashlib.sha256(bulk_path.read_bytes()).hexdigest()
        if bulk_sha != anchor.get("source_sha256") or bulk_sha != diagnostic.get("source_sha256"):
            raise SEC13FFeasibilityError("SEC 13F 2016Q1 bulk source hash no longer matches preserved evidence")

        archive = _archive_from_local(bulk_path, source_url)
        affected, malformed_rows = _collect_bulk_affected(archive)
        if len(affected) != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS:
            raise SEC13FFeasibilityError("reconstructed malformed-accession population differs from frozen scope")
        if malformed_rows != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS:
            raise SEC13FFeasibilityError("reconstructed malformed-row population differs from frozen scope")

        raw_root.mkdir(parents=True, exist_ok=True)
        provider_reads = 0
        results: list[dict[str, Any]] = []
        total = len(affected)
        for index, accession in enumerate(sorted(affected), start=1):
            item = affected[accession]
            cik = str(item["cik"])
            filename = f"edgar/data/{cik}/{accession}.txt"
            original_url = sec_archive_submission_url(filename)
            local_path = raw_root / f"{accession}.txt"

            if local_path.is_file():
                original_text = local_path.read_text(encoding="utf-8")
                source_sha256 = hashlib.sha256(local_path.read_bytes()).hexdigest()
                source_mode = "LOCAL_IMMUTABLE_ORIGINAL_EDGAR"
            else:
                document = self.sec_archive_client.complete_submission(filename=filename)
                encoded = document.text.encode("utf-8")
                encoded_sha = hashlib.sha256(encoded).hexdigest()
                if encoded_sha != document.source_sha256:
                    raise SEC13FFeasibilityError(
                        f"original EDGAR submission could not be persisted losslessly as UTF-8: {accession}"
                    )
                atomic_write_text(local_path, document.text)
                original_text = document.text
                source_sha256 = document.source_sha256
                source_mode = "OFFICIAL_SEC_ORIGINAL_EDGAR_FETCH_PERSISTED_IMMUTABLY"
                provider_reads += 1

            reconciled = reconcile_accession_cusips(
                accession=accession,
                cik=cik,
                bulk_cusips=list(item["bulk_cusips"]),
                original_text=original_text,
                source_url=original_url,
                source_sha256=source_sha256,
                source_mode=source_mode,
            )
            results.append(reconciled)
            if index == 1 or index == total or index % 10 == 0:
                self.progress(
                    f"SEC 13F original EDGAR {index}/{total}: {accession} "
                    f"bulk_bad={reconciled['bulk_malformed_cusip_rows']} "
                    f"original_bad={reconciled['original_malformed_cusip_rows']} "
                    f"class={reconciled['classification']}"
                )

        classification_counts = Counter(str(item["classification"]) for item in results)
        classification_bulk_bad_rows: Counter[str] = Counter()
        for item in results:
            classification_bulk_bad_rows[str(item["classification"])] += int(
                item["bulk_malformed_cusip_rows"]
            )

        original_total_rows = sum(int(item["original_cusip_rows"]) for item in results)
        original_bad_rows = sum(int(item["original_malformed_cusip_rows"]) for item in results)
        result = {
            "contract_version": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
            "policy_fingerprint": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
            "status": "RECONCILIATION_COMPLETE",
            "complete": len(results) == SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
            "source": SEC_13F_ORIGINAL_EDGAR_SOURCE,
            "anchor": SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR,
            "gate0_status_preserved": gate0.get("status"),
            "gate0_pass_preserved": bool(gate0.get("pass")),
            "bulk_source_sha256": bulk_sha,
            "affected_accessions": len(results),
            "bulk_malformed_rows": malformed_rows,
            "original_cusip_rows": original_total_rows,
            "original_nine_char_cusip_rows": original_total_rows - original_bad_rows,
            "original_malformed_cusip_rows": original_bad_rows,
            "original_nine_char_cusip_fraction": (
                (original_total_rows - original_bad_rows) / original_total_rows if original_total_rows else 0.0
            ),
            "row_count_match_accessions": sum(1 for item in results if item["row_count_match"]),
            "exact_cusip_multiset_match_accessions": sum(
                1 for item in results if item["exact_cusip_multiset_match"]
            ),
            "bulk_malformed_rows_exactly_preserved_in_original": sum(
                int(item["bulk_malformed_rows_exactly_preserved_in_original"]) for item in results
            ),
            "bulk_short_rows_left_zero_pad_candidate_present_in_original": sum(
                int(item["bulk_short_rows_left_zero_pad_candidate_present_in_original"])
                for item in results
            ),
            "classification_counts": dict(sorted(classification_counts.items())),
            "classification_bulk_malformed_rows": dict(sorted(classification_bulk_bad_rows.items())),
            "accessions": results,
            "governance": {
                "provider_reads_performed": provider_reads,
                "provider_writes_performed": 0,
                "cusip_repair_performed": False,
                "atlas_identity_granted": False,
                "target_outcome_rows_read": 0,
                "protected_return_rows_read": 0,
                "protected_holdout_consumed": False,
                "scientific_freeze_allowed": False,
                "phase33_signal_to_trade_authority": False,
            },
            "interpretation_boundary": (
                "This census determines whether malformed bulk CUSIPs are already present in original "
                "as-filed 13F XML or differ from the original EDGAR submission. It does not repair CUSIPs, "
                "grant instrument identity, freeze hypotheses, or authorize outcome reads."
            ),
            "next_scientific_action": (
                "CLASSIFY_ORIGINAL_SOURCE_DEFECT_VS_BULK_EXTRACTION_DEFECT_THEN_DECIDE_AUTHORITATIVE_"
                "SOURCE_REPAIR_OR_ACCEPTED_NEGATIVE_BEFORE_COMPLETE_CAPACITY_AND_SCIENTIFIC_FREEZE"
            ),
        }
        atomic_write_text(report_path, json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
        return result
