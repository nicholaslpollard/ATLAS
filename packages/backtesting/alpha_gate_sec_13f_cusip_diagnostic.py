from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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
from packages.providers.sec_13f_datasets import SEC13FDatasetArchive, SEC13FDatasetClient


SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT = (
    "alpha-gate-sec-13f-cusip-diagnostic-v1-source-only-preserved-gate0-evidence"
)
SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR = "2016Q1"
SEC_13F_CUSIP_DIAGNOSTIC_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_13f_feasibility_v2/cusip_diagnostic_v1.json"
)
SEC_13F_CUSIP_DIAGNOSTIC_PROVIDER_READS = 0
SEC_13F_CUSIP_DIAGNOSTIC_TARGET_OUTCOME_READS = 0
SEC_13F_CUSIP_DIAGNOSTIC_PROTECTED_RETURN_READS = 0
SEC_13F_CUSIP_DIAGNOSTIC_SCIENTIFIC_FREEZE_ALLOWED = False
SEC_13F_CUSIP_DIAGNOSTIC_PHASE33_AUTHORITY = False


def _top(counter: Counter[str], limit: int = 25) -> list[dict[str, object]]:
    return [{"value": value, "rows": rows} for value, rows in counter.most_common(limit)]


def diagnose_13f_cusips(archive: SEC13FDatasetArchive) -> dict[str, Any]:
    """Classify CUSIP-shape defects without repairing, mapping, or opening outcomes."""
    members = _table_members(archive)
    submissions: dict[str, dict[str, str]] = {}

    with zipfile.ZipFile(io.BytesIO(archive.raw_bytes)) as handle:
        for row in _rows(handle, members["SUBMISSION.tsv"], _REQUIRED_SUBMISSION_FIELDS):
            accession = row["ACCESSION_NUMBER"]
            if accession and accession not in submissions:
                submissions[accession] = row

        valid_cusips: set[str] = set()
        issuer_class_valid: dict[tuple[str, str], set[str]] = defaultdict(set)
        malformed: list[dict[str, str]] = []
        length_counts: Counter[str] = Counter()
        malformed_value_counts: Counter[str] = Counter()
        malformed_accession_counts: Counter[str] = Counter()
        initial_hr_rows = 0

        for row in _rows(handle, members["INFOTABLE.tsv"], _REQUIRED_INFOTABLE_FIELDS):
            accession = row["ACCESSION_NUMBER"]
            submission = submissions.get(accession)
            if submission is None or submission["SUBMISSIONTYPE"] != "13F-HR":
                continue
            initial_hr_rows += 1
            cusip = row["CUSIP"].strip()
            length_counts[str(len(cusip))] += 1
            issuer_key = (row["NAMEOFISSUER"].strip().upper(), row["TITLEOFCLASS"].strip().upper())
            if len(cusip) == 9:
                valid_cusips.add(cusip)
                issuer_class_valid[issuer_key].add(cusip)
                continue
            malformed_value_counts[cusip or "<BLANK>"] += 1
            malformed_accession_counts[accession] += 1
            malformed.append(
                {
                    "accession": accession,
                    "cik": submission["CIK"],
                    "cusip": cusip,
                    "issuer": row["NAMEOFISSUER"],
                    "title_of_class": row["TITLEOFCLASS"],
                    "issuer_key_name": issuer_key[0],
                    "issuer_key_class": issuer_key[1],
                }
            )

    padded_candidate_rows = 0
    padded_candidate_unique_values: set[str] = set()
    issuer_class_single_candidate_rows = 0
    issuer_class_single_candidate_unique_values: set[str] = set()
    both_signals_agree_rows = 0
    samples: list[dict[str, object]] = []

    for item in malformed:
        cusip = item["cusip"]
        padded_candidate = cusip.rjust(9, "0") if 0 < len(cusip) < 9 else ""
        padded_present = bool(padded_candidate and padded_candidate in valid_cusips)
        issuer_key = (item["issuer_key_name"], item["issuer_key_class"])
        issuer_candidates = sorted(issuer_class_valid.get(issuer_key, set()))
        single_issuer_candidate = issuer_candidates[0] if len(issuer_candidates) == 1 else ""

        if padded_present:
            padded_candidate_rows += 1
            padded_candidate_unique_values.add(cusip)
        if single_issuer_candidate:
            issuer_class_single_candidate_rows += 1
            issuer_class_single_candidate_unique_values.add(cusip)
        if padded_present and single_issuer_candidate == padded_candidate:
            both_signals_agree_rows += 1

        if len(samples) < 100:
            samples.append(
                {
                    "accession": item["accession"],
                    "cik": item["cik"],
                    "cusip_raw": cusip,
                    "cusip_length": len(cusip),
                    "issuer": item["issuer"],
                    "title_of_class": item["title_of_class"],
                    "left_zero_pad_candidate": padded_candidate or None,
                    "left_zero_pad_candidate_seen_as_valid_in_same_archive": padded_present,
                    "same_issuer_class_single_valid_cusip": single_issuer_candidate or None,
                }
            )

    malformed_rows = len(malformed)
    blank_rows = sum(1 for item in malformed if not item["cusip"])
    short_nonblank_rows = sum(1 for item in malformed if 0 < len(item["cusip"]) < 9)
    long_rows = sum(1 for item in malformed if len(item["cusip"]) > 9)
    nonblank_nine_char_rows = initial_hr_rows - malformed_rows

    return {
        "contract_version": SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT,
        "source_sha256": archive.source_sha256,
        "source_url": archive.source_url,
        "initial_hr_rows": initial_hr_rows,
        "nine_char_rows": nonblank_nine_char_rows,
        "malformed_rows": malformed_rows,
        "malformed_fraction": malformed_rows / initial_hr_rows if initial_hr_rows else 0.0,
        "blank_rows": blank_rows,
        "short_nonblank_rows": short_nonblank_rows,
        "long_rows": long_rows,
        "cusip_length_histogram": dict(sorted(length_counts.items(), key=lambda item: int(item[0]))),
        "unique_malformed_values": len(malformed_value_counts),
        "top_malformed_values": _top(malformed_value_counts),
        "malformed_accessions": len(malformed_accession_counts),
        "top_malformed_accessions": _top(malformed_accession_counts),
        "left_zero_pad_candidate_seen_as_valid_rows": padded_candidate_rows,
        "left_zero_pad_candidate_seen_as_valid_unique_raw_values": len(padded_candidate_unique_values),
        "same_issuer_class_single_valid_cusip_rows": issuer_class_single_candidate_rows,
        "same_issuer_class_single_valid_cusip_unique_raw_values": len(
            issuer_class_single_candidate_unique_values
        ),
        "both_diagnostic_signals_agree_rows": both_signals_agree_rows,
        "samples": samples,
        "interpretation_boundary": (
            "Diagnostic matches are evidence only. They do not authorize CUSIP repair, "
            "CUSIP-to-ATLAS identity, scientific freeze, or market-outcome reads."
        ),
    }


class SEC13FCusipDiagnostic:
    """Read-only diagnostic over the already-preserved Gate0 v2 SEC archive."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings

    def run(self) -> dict[str, Any]:
        canonical_root = self.settings.resolved_path(self.settings.data.paths.canonical)
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        gate0_report_path = derived_root / SEC_13F_REPORT_RELATIVE_V2
        diagnostic_path = derived_root / SEC_13F_CUSIP_DIAGNOSTIC_REPORT_RELATIVE

        if not gate0_report_path.is_file():
            raise SEC13FFeasibilityError(
                "SEC 13F v2 Gate0 report is missing; diagnostic will not fetch or reconstruct it"
            )
        gate0 = json.loads(gate0_report_path.read_text(encoding="utf-8"))
        if gate0.get("contract_version") != SEC_13F_FEASIBILITY_V2_CONTRACT:
            raise SEC13FFeasibilityError("SEC 13F v2 Gate0 report contract drifted")
        if gate0.get("policy_fingerprint") != SEC_13F_FEASIBILITY_V2_FINGERPRINT:
            raise SEC13FFeasibilityError("SEC 13F v2 Gate0 report fingerprint drifted")

        anchor = next(
            (
                item
                for item in gate0.get("anchors", [])
                if isinstance(item, dict) and item.get("label") == SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR
            ),
            None,
        )
        if anchor is None:
            raise SEC13FFeasibilityError("SEC 13F v2 Gate0 2016Q1 anchor is missing")

        source_url = str(anchor.get("source_url") or "")
        filename = SEC13FDatasetClient.validate_url(source_url)
        raw_path = canonical_root / SEC_13F_RAW_RELATIVE_V2 / filename
        if not raw_path.is_file():
            raise SEC13FFeasibilityError(
                f"preserved SEC 13F v2 2016Q1 archive is missing; do not refetch: {raw_path}"
            )
        actual_sha = hashlib.sha256(raw_path.read_bytes()).hexdigest()
        if actual_sha != anchor.get("source_sha256"):
            raise SEC13FFeasibilityError("preserved SEC 13F v2 2016Q1 archive hash changed")

        if diagnostic_path.is_file():
            existing = json.loads(diagnostic_path.read_text(encoding="utf-8"))
            if (
                existing.get("contract_version") != SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT
                or existing.get("source_sha256") != actual_sha
            ):
                raise SEC13FFeasibilityError(
                    "existing SEC 13F CUSIP diagnostic conflicts with preserved evidence"
                )
            return existing

        archive = _archive_from_local(raw_path, source_url)
        result = diagnose_13f_cusips(archive)
        result.update(
            {
                "anchor": SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR,
                "gate0_status_preserved": gate0.get("status"),
                "gate0_pass_preserved": bool(gate0.get("pass")),
                "gate0_report_path": str(gate0_report_path),
                "raw_path": str(raw_path),
                "governance": {
                    "provider_reads_performed": SEC_13F_CUSIP_DIAGNOSTIC_PROVIDER_READS,
                    "target_outcome_rows_read": SEC_13F_CUSIP_DIAGNOSTIC_TARGET_OUTCOME_READS,
                    "protected_return_rows_read": SEC_13F_CUSIP_DIAGNOSTIC_PROTECTED_RETURN_READS,
                    "protected_holdout_consumed": False,
                    "scientific_freeze_allowed": SEC_13F_CUSIP_DIAGNOSTIC_SCIENTIFIC_FREEZE_ALLOWED,
                    "phase33_signal_to_trade_authority": SEC_13F_CUSIP_DIAGNOSTIC_PHASE33_AUTHORITY,
                },
            }
        )
        atomic_write_text(
            diagnostic_path,
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
        return result
