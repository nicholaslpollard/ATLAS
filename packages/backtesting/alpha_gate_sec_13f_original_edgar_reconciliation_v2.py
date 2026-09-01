from __future__ import annotations

import hashlib
import json
import re
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
    _archive_from_local,
)
from packages.backtesting.alpha_gate_sec_13f_feasibility_v2 import (
    SEC_13F_FEASIBILITY_V2_CONTRACT,
    SEC_13F_FEASIBILITY_V2_FINGERPRINT,
    SEC_13F_RAW_RELATIVE_V2,
    SEC_13F_REPORT_RELATIVE_V2,
)
from packages.backtesting.alpha_gate_sec_13f_original_edgar_reconciliation import (
    SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
    SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS,
    SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
    SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_RAW_RELATIVE,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
    SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
    SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
    SEC_13F_ORIGINAL_EDGAR_SOURCE,
    SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
    _collect_bulk_affected,
    reconcile_accession_cusips,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.providers.sec_13f_datasets import SEC13FDatasetClient
from packages.providers.sec_edgar_archive import (
    SECEDGARArchiveClient,
    sec_archive_submission_url,
    sec_quarter_master_index_url,
)


SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT = (
    "alpha-gate-sec-13f-original-edgar-reconciliation-v2-master-index-authoritative-locator-"
    "same-frozen-population-source-only-no-market-outcomes"
)
SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT = (
    "88402d747d52c4631f12661aa5d8d35738f114775795243c82ab123d6c22cf61"
)
SEC_13F_ORIGINAL_EDGAR_V2_LOCATOR_SOURCE = "SEC_EDGAR_2016_Q1_MASTER_INDEX"
SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_YEAR = 2016
SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_QUARTER = 1
SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_URL = sec_quarter_master_index_url(
    year=SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_YEAR,
    quarter=SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_QUARTER,
)
SEC_13F_ORIGINAL_EDGAR_V2_REUSE_V1_CACHE_AFTER_LOCATOR_CONFIRMATION = True
SEC_13F_ORIGINAL_EDGAR_V2_REPORT_RELATIVE = Path(
    "strategy_evaluation/pre_phase33/sec_13f_feasibility_v2/"
    "original_edgar_reconciliation_v2.json"
)

_ACCESSION_RE = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
        "v1_contract": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
        "v1_fingerprint": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
        "anchor": SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR,
        "expected_malformed_accessions": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
        "expected_malformed_rows": SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS,
        "source": SEC_13F_ORIGINAL_EDGAR_SOURCE,
        "locator_source": SEC_13F_ORIGINAL_EDGAR_V2_LOCATOR_SOURCE,
        "master_index_year": SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_YEAR,
        "master_index_quarter": SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_QUARTER,
        "master_index_url": SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_URL,
        "reuse_v1_immutable_cache_after_locator_confirmation": (
            SEC_13F_ORIGINAL_EDGAR_V2_REUSE_V1_CACHE_AFTER_LOCATOR_CONFIRMATION
        ),
        "cusip_repair_allowed": SEC_13F_ORIGINAL_EDGAR_CUSIP_REPAIR_ALLOWED,
        "atlas_identity_allowed": SEC_13F_ORIGINAL_EDGAR_ATLAS_IDENTITY_ALLOWED,
        "target_outcomes_allowed": SEC_13F_ORIGINAL_EDGAR_TARGET_OUTCOMES_ALLOWED,
        "protected_outcomes_allowed": SEC_13F_ORIGINAL_EDGAR_PROTECTED_OUTCOMES_ALLOWED,
        "scientific_freeze_allowed": SEC_13F_ORIGINAL_EDGAR_SCIENTIFIC_FREEZE_ALLOWED,
        "phase33_signal_to_trade_authority": SEC_13F_ORIGINAL_EDGAR_PHASE33_AUTHORITY,
    }


def sec_13f_original_edgar_reconciliation_v2_fingerprint() -> str:
    return hashlib.sha256(_canonical_json(_fingerprint_payload()).encode("utf-8")).hexdigest()


def parse_13f_hr_master_index(text: str) -> dict[str, str]:
    """Return accession -> exact SEC archive filename from an official master.idx."""
    resolved: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.rstrip("\r\n")
        parts = line.split("|")
        if len(parts) != 5:
            continue
        _cik, _company, form_type, _filed, filename = (part.strip() for part in parts)
        if form_type != "13F-HR":
            continue
        if not filename.startswith("edgar/data/") or not filename.endswith(".txt"):
            raise SEC13FFeasibilityError(
                f"SEC 13F master index returned an unexpected archive filename: {filename!r}"
            )
        accession = filename.rsplit("/", 1)[-1][:-4]
        if not _ACCESSION_RE.fullmatch(accession):
            raise SEC13FFeasibilityError(
                f"SEC 13F master index returned an invalid accession filename: {filename!r}"
            )
        sec_archive_submission_url(filename)
        existing = resolved.get(accession)
        if existing is not None and existing != filename:
            raise SEC13FFeasibilityError(
                f"SEC 13F master index maps accession to multiple filenames: {accession}"
            )
        resolved[accession] = filename
    return resolved


def _submission_identity_matches(text: str, accession: str) -> bool:
    head = text[:100_000]
    return (
        f"<SEC-DOCUMENT>{accession}.txt" in head
        or f"ACCESSION NUMBER:\t\t{accession}" in head
        or f"ACCESSION NUMBER: {accession}" in head
        or accession in head
    )


def _archive_cik_from_filename(filename: str) -> str:
    parts = filename.split("/")
    if len(parts) != 4 or parts[0:2] != ["edgar", "data"] or not parts[2].isdigit():
        raise SEC13FFeasibilityError(
            f"SEC 13F master-index filename has invalid archive CIK structure: {filename!r}"
        )
    return str(int(parts[2]))


class SEC13FOriginalEdgarReconciliationV2:
    """Reconcile the same frozen population using master.idx as filename authority."""

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
        if report.get("contract_version") != SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT:
            raise SEC13FFeasibilityError("existing SEC 13F original-EDGAR v2 report contract drifted")
        if report.get("policy_fingerprint") != SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT:
            raise SEC13FFeasibilityError(
                "existing SEC 13F original-EDGAR v2 report fingerprint drifted"
            )
        for item in report.get("accessions", []):
            if not isinstance(item, dict):
                raise SEC13FFeasibilityError(
                    "existing SEC 13F original-EDGAR v2 accession is malformed"
                )
            accession = str(item.get("accession") or "")
            path = raw_root / f"{accession}.txt"
            if not path.is_file():
                raise SEC13FFeasibilityError(
                    f"accepted original EDGAR v2 source is missing; do not silently refetch: {path}"
                )
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != item.get("source_sha256"):
                raise SEC13FFeasibilityError(
                    f"accepted original EDGAR v2 source hash changed: {path}"
                )
        return report

    def run(self) -> dict[str, Any]:
        if (
            sec_13f_original_edgar_reconciliation_v2_fingerprint()
            != SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT
        ):
            raise SEC13FFeasibilityError("frozen SEC 13F original-EDGAR v2 fingerprint drifted")

        canonical_root = self.settings.resolved_path(self.settings.data.paths.canonical)
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        gate0_path = derived_root / SEC_13F_REPORT_RELATIVE_V2
        diagnostic_path = derived_root / SEC_13F_CUSIP_DIAGNOSTIC_REPORT_RELATIVE
        report_path = derived_root / SEC_13F_ORIGINAL_EDGAR_V2_REPORT_RELATIVE
        raw_root = canonical_root / SEC_13F_ORIGINAL_EDGAR_RAW_RELATIVE

        existing = self._existing_report(report_path, raw_root)
        if existing is not None:
            self.progress(
                "SEC 13F original-EDGAR v2 reconciliation already exists and is hash-valid; "
                "returning immutable report."
            )
            return existing

        if not gate0_path.is_file() or not diagnostic_path.is_file():
            raise SEC13FFeasibilityError(
                "preserved Gate0 and CUSIP diagnostic evidence are required before "
                "original EDGAR v2 reconciliation"
            )
        gate0 = json.loads(gate0_path.read_text(encoding="utf-8"))
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        if gate0.get("contract_version") != SEC_13F_FEASIBILITY_V2_CONTRACT:
            raise SEC13FFeasibilityError("SEC 13F Gate0 contract drifted")
        if gate0.get("policy_fingerprint") != SEC_13F_FEASIBILITY_V2_FINGERPRINT:
            raise SEC13FFeasibilityError("SEC 13F Gate0 fingerprint drifted")
        if diagnostic.get("contract_version") != SEC_13F_CUSIP_DIAGNOSTIC_CONTRACT:
            raise SEC13FFeasibilityError("SEC 13F CUSIP diagnostic contract drifted")
        if int(diagnostic.get("malformed_accessions") or 0) != (
            SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS
        ):
            raise SEC13FFeasibilityError(
                "SEC 13F malformed-accession count differs from frozen v2 reconciliation scope"
            )
        if int(diagnostic.get("malformed_rows") or 0) != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS:
            raise SEC13FFeasibilityError(
                "SEC 13F malformed-row count differs from frozen v2 reconciliation scope"
            )

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
            raise SEC13FFeasibilityError(
                "SEC 13F 2016Q1 bulk source hash no longer matches preserved evidence"
            )

        archive = _archive_from_local(bulk_path, source_url)
        affected, malformed_rows = _collect_bulk_affected(archive)
        if len(affected) != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS:
            raise SEC13FFeasibilityError(
                "reconstructed malformed-accession population differs from frozen v2 scope"
            )
        if malformed_rows != SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ROWS:
            raise SEC13FFeasibilityError(
                "reconstructed malformed-row population differs from frozen v2 scope"
            )

        self.progress(
            "SEC 13F v2 locator: reading official 2016 Q1 master.idx for exact archive filenames."
        )
        master_document = self.sec_archive_client.quarter_master_index(
            year=SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_YEAR,
            quarter=SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_QUARTER,
        )
        if master_document.source_url != SEC_13F_ORIGINAL_EDGAR_V2_MASTER_INDEX_URL:
            raise SEC13FFeasibilityError("SEC 13F v2 master-index source URL drifted")
        locator = parse_13f_hr_master_index(master_document.text)
        missing = sorted(accession for accession in affected if accession not in locator)
        if missing:
            raise SEC13FFeasibilityError(
                "official 2016 Q1 master.idx does not resolve every frozen malformed accession; "
                f"missing_count={len(missing)} first={missing[:5]}"
            )

        raw_root.mkdir(parents=True, exist_ok=True)
        complete_submission_reads = 0
        cache_reuse_count = 0
        results: list[dict[str, Any]] = []
        total = len(affected)
        locator_cik_differences = 0

        for index, accession in enumerate(sorted(affected), start=1):
            item = affected[accession]
            bulk_cik = str(item["cik"])
            filename = locator[accession]
            archive_cik = _archive_cik_from_filename(filename)
            original_url = sec_archive_submission_url(filename)
            local_path = raw_root / f"{accession}.txt"

            if archive_cik != str(int(bulk_cik)):
                locator_cik_differences += 1

            if local_path.is_file():
                original_text = local_path.read_text(encoding="utf-8")
                source_sha256 = hashlib.sha256(local_path.read_bytes()).hexdigest()
                if not _submission_identity_matches(original_text, accession):
                    raise SEC13FFeasibilityError(
                        f"cached original EDGAR source does not identify expected accession: {accession}"
                    )
                source_mode = "V1_IMMUTABLE_CACHE_REUSED_AFTER_MASTER_INDEX_CONFIRMATION"
                cache_reuse_count += 1
            else:
                document = self.sec_archive_client.complete_submission(filename=filename)
                if document.source_url != original_url:
                    raise SEC13FFeasibilityError(
                        f"SEC 13F v2 complete-submission URL drifted: {accession}"
                    )
                encoded = document.text.encode("utf-8")
                encoded_sha = hashlib.sha256(encoded).hexdigest()
                if encoded_sha != document.source_sha256:
                    raise SEC13FFeasibilityError(
                        f"original EDGAR submission could not be persisted losslessly as UTF-8: {accession}"
                    )
                if not _submission_identity_matches(document.text, accession):
                    raise SEC13FFeasibilityError(
                        f"fetched original EDGAR source does not identify expected accession: {accession}"
                    )
                atomic_write_text(local_path, document.text)
                original_text = document.text
                source_sha256 = document.source_sha256
                source_mode = "MASTER_INDEX_RESOLVED_OFFICIAL_SEC_FETCH_PERSISTED_IMMUTABLY"
                complete_submission_reads += 1

            reconciled = reconcile_accession_cusips(
                accession=accession,
                cik=archive_cik,
                bulk_cusips=list(item["bulk_cusips"]),
                original_text=original_text,
                source_url=original_url,
                source_sha256=source_sha256,
                source_mode=source_mode,
            )
            reconciled["bulk_submission_cik"] = bulk_cik
            reconciled["master_index_archive_cik"] = archive_cik
            reconciled["master_index_filename"] = filename
            reconciled["locator_cik_differs_from_bulk_cik"] = archive_cik != str(int(bulk_cik))
            results.append(reconciled)

            if index == 1 or index == total or index % 10 == 0:
                self.progress(
                    f"SEC 13F original EDGAR v2 {index}/{total}: {accession} "
                    f"bulk_bad={reconciled['bulk_malformed_cusip_rows']} "
                    f"original_bad={reconciled['original_malformed_cusip_rows']} "
                    f"class={reconciled['classification']} "
                    f"source={source_mode}"
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
            "contract_version": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_CONTRACT,
            "policy_fingerprint": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_V2_FINGERPRINT,
            "status": "RECONCILIATION_COMPLETE",
            "complete": len(results) == SEC_13F_ORIGINAL_EDGAR_EXPECTED_MALFORMED_ACCESSIONS,
            "source": SEC_13F_ORIGINAL_EDGAR_SOURCE,
            "locator_source": SEC_13F_ORIGINAL_EDGAR_V2_LOCATOR_SOURCE,
            "locator_source_url": master_document.source_url,
            "locator_source_sha256": master_document.source_sha256,
            "anchor": SEC_13F_CUSIP_DIAGNOSTIC_ANCHOR,
            "v1_contract_preserved": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_CONTRACT,
            "v1_fingerprint_preserved": SEC_13F_ORIGINAL_EDGAR_RECONCILIATION_FINGERPRINT,
            "v1_failure_boundary": (
                "PARTIAL_SOURCE_ACQUISITION_STOPPED_ON_DERIVED_ARCHIVE_PATH_HTTP_404; "
                "NO_FINAL_V1_REPORT; RAW_ORIGINAL_FILINGS_PRESERVED"
            ),
            "gate0_status_preserved": gate0.get("status"),
            "gate0_pass_preserved": bool(gate0.get("pass")),
            "bulk_source_sha256": bulk_sha,
            "affected_accessions": len(results),
            "bulk_malformed_rows": malformed_rows,
            "master_index_resolved_accessions": sum(1 for accession in affected if accession in locator),
            "master_index_archive_cik_differs_from_bulk_cik_accessions": locator_cik_differences,
            "v1_cache_reused_accessions": cache_reuse_count,
            "original_cusip_rows": original_total_rows,
            "original_nine_char_cusip_rows": original_total_rows - original_bad_rows,
            "original_malformed_cusip_rows": original_bad_rows,
            "original_nine_char_cusip_fraction": (
                (original_total_rows - original_bad_rows) / original_total_rows
                if original_total_rows
                else 0.0
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
                "provider_reads_performed": 1 + complete_submission_reads,
                "master_index_reads_performed": 1,
                "complete_submission_reads_performed": complete_submission_reads,
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
                "V2 changes only archive-location authority: exact complete-submission filenames come "
                "from official SEC 2016 Q1 master.idx. The frozen 374-accession/10,431-row population "
                "and CUSIP comparison are unchanged. No CUSIP is repaired, no ATLAS identity is "
                "granted, and no market outcome is opened."
            ),
            "next_scientific_action": (
                "CLASSIFY_ORIGINAL_SOURCE_DEFECT_VS_BULK_EXTRACTION_DEFECT_THEN_DECIDE_AUTHORITATIVE_"
                "SOURCE_REPAIR_OR_ACCEPTED_NEGATIVE_BEFORE_COMPLETE_CAPACITY_AND_SCIENTIFIC_FREEZE"
            ),
        }
        atomic_write_text(
            report_path,
            json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
        return result
