from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase32 import MassivePhase32SECIndexClient
from packages.providers.massive.phase32_semantic import MassivePhase32SemanticClient
from packages.providers.sec_edgar import SECEDGARClient


PHASE32_SEMANTIC_CONTRACT_VERSION = (
    "phase32-semantic-feasibility-v1-massive-8k-disclosures-text-no-market-outcomes"
)
PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT = (
    "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
)
PHASE32_SEMANTIC_DECLARED_MASSIVE_PLAN = "Stocks Starter"
PHASE32_PROVIDER_PUBLISHED_DISCLOSURE_HISTORY = "January 2022"
PHASE32_SEMANTIC_SAFE_HISTORY_START = "2022-01-03"
PHASE32_SEMANTIC_SAMPLE_PER_COVERED_WINDOW = 6
PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN = False
PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED = False
PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED = False
PHASE32_SEMANTIC_PROVIDER_WRITES = 0
PHASE32_SEMANTIC_BROKER_READS = 0
PHASE32_SEMANTIC_BROKER_WRITES = 0
PHASE32_SEMANTIC_ORDER_WRITES = 0
PHASE32_SEMANTIC_PAPER_SUBMITS = 0
PHASE32_SEMANTIC_LIVE_WRITES = 0
PHASE32_SEMANTIC_AUTOMATION_WRITES = 0
PHASE32_SEMANTIC_AUTOMATIC_BROKER_FAILOVER = False


@dataclass(frozen=True, slots=True)
class Phase32SemanticProbeWindow:
    label: str
    start_date: str
    end_date: str
    covered_by_safe_history: bool


PHASE32_SEMANTIC_PROBE_WINDOWS = (
    Phase32SemanticProbeWindow("prepublished_boundary", "2021-08-16", "2021-08-20", False),
    Phase32SemanticProbeWindow("published_history_boundary", "2022-01-03", "2022-01-07", True),
    Phase32SemanticProbeWindow("mid_history", "2023-08-14", "2023-08-18", True),
    Phase32SemanticProbeWindow("development_boundary", "2026-05-04", "2026-05-08", True),
    Phase32SemanticProbeWindow("protected_boundary", "2026-08-07", "2026-08-11", True),
)


class Phase32SemanticFeasibilityError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise Phase32SemanticFeasibilityError(f"invalid frozen semantic probe date {value!r}") from exc


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE32_SEMANTIC_CONTRACT_VERSION,
        "accepted_v2_feasibility_fingerprint": PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT,
        "declared_massive_plan": PHASE32_SEMANTIC_DECLARED_MASSIVE_PLAN,
        "provider_published_disclosure_history": PHASE32_PROVIDER_PUBLISHED_DISCLOSURE_HISTORY,
        "safe_semantic_history_start": PHASE32_SEMANTIC_SAFE_HISTORY_START,
        "probe_windows": [asdict(window) for window in PHASE32_SEMANTIC_PROBE_WINDOWS],
        "sample_per_covered_window": PHASE32_SEMANTIC_SAMPLE_PER_COVERED_WINDOW,
        "sources": {
            "index": "/stocks/filings/vX/index?form_type=8-K",
            "disclosures": "/stocks/filings/8-K/vX/disclosures",
            "text": "/stocks/filings/8-K/vX/text",
            "taxonomy": "/stocks/taxonomies/vX/disclosures",
            "sec": "data.sec.gov/submissions",
        },
        "alpha_hypotheses_frozen": PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": PHASE32_SEMANTIC_PROVIDER_WRITES,
            "broker_reads": PHASE32_SEMANTIC_BROKER_READS,
            "broker_writes": PHASE32_SEMANTIC_BROKER_WRITES,
            "order_writes": PHASE32_SEMANTIC_ORDER_WRITES,
            "paper_submits": PHASE32_SEMANTIC_PAPER_SUBMITS,
            "live_writes": PHASE32_SEMANTIC_LIVE_WRITES,
            "automation_writes": PHASE32_SEMANTIC_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE32_SEMANTIC_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase32_semantic_feasibility_fingerprint() -> str:
    raw = json.dumps(
        _fingerprint_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _immutable_write(path: Path, text: str, *, label: str) -> str:
    expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if path.is_file():
        existing_sha = sha256_file(path)
        if existing_sha != expected_sha:
            raise Phase32SemanticFeasibilityError(
                f"Phase32 {label} evidence drifted for immutable artifact {path}; "
                f"existing={existing_sha} current={expected_sha}"
            )
        return existing_sha
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    if sha256_file(path) != expected_sha:
        raise Phase32SemanticFeasibilityError(
            f"immutable Phase32 {label} hash mismatch: {path}"
        )
    return expected_sha


def _jsonl_text(rows: tuple[dict[str, Any], ...]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    )


def _json_text(value: object) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ) + "\n"


def _sample_accessions(
    disclosure_rows: tuple[dict[str, Any], ...],
    index_accessions: set[str],
) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for row in disclosure_rows:
        accession = str(row.get("accession_number") or "")
        if accession and accession in index_accessions and accession not in seen:
            seen.add(accession)
            ordered.append(accession)
    limit = PHASE32_SEMANTIC_SAMPLE_PER_COVERED_WINDOW
    if len(ordered) <= limit:
        return tuple(ordered)
    half = limit // 2
    return tuple(ordered[:half] + ordered[-half:])


def _normalized_grounding_text(value: object) -> str:
    text = str(value or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _supporting_text_is_grounded(supporting_text: object, items_text: object) -> bool:
    supporting = _normalized_grounding_text(supporting_text)
    items = _normalized_grounding_text(items_text)
    return bool(supporting) and supporting in items


def _taxonomy_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("primary_category") or ""),
        str(row.get("secondary_category") or ""),
        str(row.get("tertiary_category") or ""),
    )


class Phase32SemanticSourceFeasibility:
    """Qualify semantic 8-K source coverage/provenance before hypotheses or returns."""

    def __init__(
        self,
        settings: AtlasSettings,
        index_client: MassivePhase32SECIndexClient,
        semantic_client: MassivePhase32SemanticClient,
        sec_client: SECEDGARClient,
    ) -> None:
        self.settings = settings
        self.index_client = index_client
        self.semantic_client = semantic_client
        self.sec_client = sec_client
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "phase32_sec_8k_semantic_feasibility" / "v1"
        self.report_root = derived_root / "strategy_evaluation" / "phase32" / "semantic_v1"

    def report_path(self) -> Path:
        return self.report_root / "phase32_8k_semantic_feasibility.json"

    def run(self) -> dict[str, object]:
        taxonomy_result = self.semantic_client.taxonomy()
        taxonomy_rows = tuple(dict(row) for row in taxonomy_result.rows)
        taxonomy_sha = _immutable_write(
            self.evidence_root / "taxonomy.jsonl",
            _jsonl_text(taxonomy_rows),
            label="Massive disclosure taxonomy",
        )
        taxonomy_keys = {_taxonomy_key(row) for row in taxonomy_rows}
        taxonomy_versions = sorted(
            {str(row.get("taxonomy") or "") for row in taxonomy_rows if row.get("taxonomy")}
        )

        window_reports: list[dict[str, object]] = []
        total_disclosures = 0
        total_index_rows = 0
        total_samples = 0
        total_text_records = 0
        total_sec_records = 0

        for window in PHASE32_SEMANTIC_PROBE_WINDOWS:
            start = _parse_date(window.start_date)
            end = _parse_date(window.end_date)

            index_result = self.index_client.eight_k_window(start_date=start, end_date=end)
            index_rows = tuple(dict(row) for row in index_result.rows)
            index_sha = _immutable_write(
                self.evidence_root / "massive_index" / f"{window.label}.jsonl",
                _jsonl_text(index_rows),
                label="Massive semantic-gate index",
            )

            disclosure_result = self.semantic_client.disclosures_window(
                start_date=start, end_date=end
            )
            disclosure_rows = tuple(dict(row) for row in disclosure_result.rows)
            disclosure_sha = _immutable_write(
                self.evidence_root / "massive_disclosures" / f"{window.label}.jsonl",
                _jsonl_text(disclosure_rows),
                label="Massive 8-K disclosures",
            )

            index_by_accession: dict[str, list[dict[str, Any]]] = {}
            for row in index_rows:
                accession = str(row.get("accession_number") or "")
                if accession:
                    index_by_accession.setdefault(accession, []).append(row)
            index_accessions = set(index_by_accession)
            overlapping_disclosures = tuple(
                row
                for row in disclosure_rows
                if str(row.get("accession_number") or "") in index_accessions
            )

            sampled_accessions: tuple[str, ...] = ()
            sample_reports: list[dict[str, object]] = []
            if window.covered_by_safe_history:
                sampled_accessions = _sample_accessions(
                    disclosure_rows, index_accessions
                )
                for accession in sampled_accessions:
                    rows_for_accession = tuple(
                        row
                        for row in overlapping_disclosures
                        if str(row.get("accession_number") or "") == accession
                    )
                    index_matches = tuple(index_by_accession[accession])
                    first_disclosure = rows_for_accession[0]
                    cik = str(first_disclosure["cik"])
                    filing_date_text = str(first_disclosure["filing_date"])
                    filing_date = _parse_date(filing_date_text)

                    text_rows = self.semantic_client.eight_k_text(
                        cik=cik, filing_date=filing_date
                    )
                    exact_text_rows = tuple(
                        dict(row)
                        for row in text_rows
                        if str(row.get("accession_number") or "") == accession
                    )
                    if len(exact_text_rows) != 1:
                        raise Phase32SemanticFeasibilityError(
                            f"Phase32 semantic source expected exactly one original 8-K text row "
                            f"for {accession}, found {len(exact_text_rows)}"
                        )
                    text_row = exact_text_rows[0]
                    text_sha = _immutable_write(
                        self.evidence_root
                        / "massive_text"
                        / window.label
                        / f"{accession}.json",
                        _json_text(text_row),
                        label="Massive 8-K text",
                    )

                    sec_record = self.sec_client.filing_metadata(
                        cik=cik,
                        accession_number=accession,
                        filing_date=filing_date_text,
                    )
                    sec_sha = _immutable_write(
                        self.evidence_root
                        / "sec_submissions"
                        / window.label
                        / f"{accession}.json",
                        sec_record.source_record_json,
                        label="SEC semantic-gate submissions record",
                    )

                    disclosure_tickers = {
                        str(ticker)
                        for row in rows_for_accession
                        for ticker in (row.get("tickers") or [])
                        if isinstance(ticker, str) and ticker.strip()
                    }
                    index_tickers = {
                        str(row["ticker"])
                        for row in index_matches
                        if isinstance(row.get("ticker"), str)
                        and str(row["ticker"]).strip()
                    }
                    ticker_aligned = bool(disclosure_tickers & index_tickers)
                    category_valid = all(
                        _taxonomy_key(row) in taxonomy_keys
                        for row in rows_for_accession
                    )
                    supporting_text_grounded = all(
                        _supporting_text_is_grounded(
                            row.get("supporting_text"), text_row.get("items_text")
                        )
                        for row in rows_for_accession
                    )
                    sec_reconciled = (
                        sec_record.accession_number == accession
                        and sec_record.form == "8-K"
                        and sec_record.filing_date == filing_date_text
                        and bool(sec_record.acceptance_datetime)
                    )

                    sample_reports.append(
                        {
                            "accession_number": accession,
                            "cik": cik,
                            "filing_date": filing_date_text,
                            "disclosure_rows": len(rows_for_accession),
                            "index_rows": len(index_matches),
                            "disclosure_tickers": sorted(disclosure_tickers),
                            "index_tickers": sorted(index_tickers),
                            "ticker_aligned": ticker_aligned,
                            "taxonomy_categories_valid": category_valid,
                            "supporting_text_grounded_in_items_text": supporting_text_grounded,
                            "sec_accession_form_filing_date_acceptance_reconciled": sec_reconciled,
                            "massive_text_sha256": text_sha,
                            "sec_source_record_sha256": sec_sha,
                        }
                    )
                    total_text_records += 1
                    total_sec_records += 1

            window_reports.append(
                {
                    "label": window.label,
                    "start_date": window.start_date,
                    "end_date": window.end_date,
                    "covered_by_safe_history": window.covered_by_safe_history,
                    "index_rows": len(index_rows),
                    "index_sha256": index_sha,
                    "index_pages": index_result.page_count,
                    "index_request_ids": list(index_result.request_ids),
                    "disclosure_rows": len(disclosure_rows),
                    "disclosure_sha256": disclosure_sha,
                    "disclosure_pages": disclosure_result.page_count,
                    "disclosure_request_ids": list(disclosure_result.request_ids),
                    "original_8k_overlap_rows": len(overlapping_disclosures),
                    "sampled_accessions": list(sampled_accessions),
                    "sample_reports": sample_reports,
                    "covered_window_nonempty": (
                        bool(disclosure_rows) if window.covered_by_safe_history else True
                    ),
                    "covered_window_has_original_8k_overlap": (
                        bool(overlapping_disclosures)
                        if window.covered_by_safe_history
                        else True
                    ),
                    "covered_window_has_sample": (
                        bool(sampled_accessions) if window.covered_by_safe_history else True
                    ),
                    "sample_ticker_alignment_pass": all(
                        bool(sample["ticker_aligned"]) for sample in sample_reports
                    ),
                    "sample_taxonomy_pass": all(
                        bool(sample["taxonomy_categories_valid"])
                        for sample in sample_reports
                    ),
                    "sample_text_grounding_pass": all(
                        bool(sample["supporting_text_grounded_in_items_text"])
                        for sample in sample_reports
                    ),
                    "sample_sec_reconciliation_pass": all(
                        bool(
                            sample[
                                "sec_accession_form_filing_date_acceptance_reconciled"
                            ]
                        )
                        for sample in sample_reports
                    ),
                }
            )
            total_disclosures += len(disclosure_rows)
            total_index_rows += len(index_rows)
            total_samples += len(sampled_accessions)

        covered_reports = [
            report
            for report in window_reports
            if bool(report["covered_by_safe_history"])
        ]
        checks = {
            "accepted_v2_feasibility_fingerprint_pinned": (
                PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT
                == "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
            ),
            "taxonomy_nonempty": bool(taxonomy_rows),
            "taxonomy_has_versions": bool(taxonomy_versions),
            "all_covered_windows_nonempty": all(
                bool(report["covered_window_nonempty"])
                for report in covered_reports
            ),
            "all_covered_windows_overlap_original_8k_index": all(
                bool(report["covered_window_has_original_8k_overlap"])
                for report in covered_reports
            ),
            "all_covered_windows_have_samples": all(
                bool(report["covered_window_has_sample"])
                for report in covered_reports
            ),
            "all_sampled_tickers_align": all(
                bool(report["sample_ticker_alignment_pass"])
                for report in covered_reports
            ),
            "all_sampled_categories_exist_in_frozen_taxonomy": all(
                bool(report["sample_taxonomy_pass"])
                for report in covered_reports
            ),
            "all_sampled_supporting_text_is_grounded": all(
                bool(report["sample_text_grounding_pass"])
                for report in covered_reports
            ),
            "all_sampled_sec_records_reconcile": all(
                bool(report["sample_sec_reconciliation_pass"])
                for report in covered_reports
            ),
            "alpha_hypotheses_not_frozen": (
                PHASE32_SEMANTIC_ALPHA_HYPOTHESES_FROZEN is False
            ),
            "target_outcomes_forbidden": (
                PHASE32_SEMANTIC_TARGET_OUTCOME_READS_ALLOWED is False
            ),
            "protected_outcomes_forbidden": (
                PHASE32_SEMANTIC_PROTECTED_OUTCOME_READS_ALLOWED is False
            ),
            "external_mutation_authority_zero": all(
                value == 0
                for value in (
                    PHASE32_SEMANTIC_PROVIDER_WRITES,
                    PHASE32_SEMANTIC_BROKER_READS,
                    PHASE32_SEMANTIC_BROKER_WRITES,
                    PHASE32_SEMANTIC_ORDER_WRITES,
                    PHASE32_SEMANTIC_PAPER_SUBMITS,
                    PHASE32_SEMANTIC_LIVE_WRITES,
                    PHASE32_SEMANTIC_AUTOMATION_WRITES,
                )
            ),
            "automatic_broker_failover_disabled": (
                PHASE32_SEMANTIC_AUTOMATIC_BROKER_FAILOVER is False
            ),
        }

        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, object] = {
            "contract_version": PHASE32_SEMANTIC_CONTRACT_VERSION,
            "phase32_semantic_feasibility_fingerprint": (
                phase32_semantic_feasibility_fingerprint()
            ),
            "accepted_v2_feasibility_fingerprint": (
                PHASE32_ACCEPTED_V2_FEASIBILITY_FINGERPRINT
            ),
            "declared_massive_plan": PHASE32_SEMANTIC_DECLARED_MASSIVE_PLAN,
            "provider_published_disclosure_history": (
                PHASE32_PROVIDER_PUBLISHED_DISCLOSURE_HISTORY
            ),
            "safe_semantic_history_start": PHASE32_SEMANTIC_SAFE_HISTORY_START,
            "taxonomy_versions": taxonomy_versions,
            "taxonomy_rows": len(taxonomy_rows),
            "taxonomy_pages": taxonomy_result.page_count,
            "taxonomy_request_ids": list(taxonomy_result.request_ids),
            "taxonomy_sha256": taxonomy_sha,
            "windows": window_reports,
            "total_index_rows": total_index_rows,
            "total_disclosure_rows": total_disclosures,
            "total_sampled_accessions": total_samples,
            "total_text_records_fetched": total_text_records,
            "total_sec_records_fetched": total_sec_records,
            "target_outcome_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "phase33_signal_to_trade_entry_satisfied": False,
            "provider_writes": PHASE32_SEMANTIC_PROVIDER_WRITES,
            "broker_reads": PHASE32_SEMANTIC_BROKER_READS,
            "broker_writes": PHASE32_SEMANTIC_BROKER_WRITES,
            "order_writes": PHASE32_SEMANTIC_ORDER_WRITES,
            "paper_submits": PHASE32_SEMANTIC_PAPER_SUBMITS,
            "live_writes": PHASE32_SEMANTIC_LIVE_WRITES,
            "automation_writes": PHASE32_SEMANTIC_AUTOMATION_WRITES,
            "automatic_broker_failover": (
                PHASE32_SEMANTIC_AUTOMATIC_BROKER_FAILOVER
            ),
            "checks": checks,
            "pass": all(checks.values()),
            "report_path": str(report_path),
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not bool(report["pass"]):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase32SemanticFeasibilityError(
                "Phase32 semantic source feasibility failed: " + ", ".join(failed)
            )
        return report
