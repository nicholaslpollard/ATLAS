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


PHASE32_SEMANTIC_V2_CONTRACT_VERSION = (
    "phase32-semantic-feasibility-v2-source-scope-aware-no-market-outcomes"
)
PHASE32_ACCEPTED_CORE_V2_FINGERPRINT = (
    "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
)
PHASE32_REJECTED_SEMANTIC_V1_FINGERPRINT = (
    "ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82"
)
PHASE32_SEMANTIC_V2_RESEARCH_START = "2021-08-16"
PHASE32_SEMANTIC_V2_SAMPLE_PER_WINDOW = 6
PHASE32_SEMANTIC_V2_IDENTITY_RULE = (
    "EXACT_ACCESSION_PLUS_ZERO_PADDED_CIK_PLUS_SEC_RECONCILIATION"
)
PHASE32_SEMANTIC_V2_TICKER_RULE = (
    "MAPPING_METADATA_ONLY_NOT_IDENTITY_EMPTY_OR_HISTORICAL_DIFFERENCE_ALLOWED_AND_RECORDED"
)
PHASE32_SEMANTIC_V2_SUPPORT_RULE = (
    "NONBLANK_SUPPORTING_TEXT_LINKED_TO_EXACT_ACCESSION_CIK_DATE_AND_TAXONOMY;"
    "ITEMS_TEXT_SCOPE_CHECK_DIAGNOSTIC_ONLY"
)
PHASE32_SEMANTIC_V2_ALPHA_HYPOTHESES_FROZEN = False
PHASE32_SEMANTIC_V2_TARGET_OUTCOME_READS_ALLOWED = False
PHASE32_SEMANTIC_V2_PROTECTED_OUTCOME_READS_ALLOWED = False
PHASE32_SEMANTIC_V2_PROVIDER_WRITES = 0
PHASE32_SEMANTIC_V2_BROKER_READS = 0
PHASE32_SEMANTIC_V2_BROKER_WRITES = 0
PHASE32_SEMANTIC_V2_ORDER_WRITES = 0
PHASE32_SEMANTIC_V2_PAPER_SUBMITS = 0
PHASE32_SEMANTIC_V2_LIVE_WRITES = 0
PHASE32_SEMANTIC_V2_AUTOMATION_WRITES = 0
PHASE32_SEMANTIC_V2_AUTOMATIC_BROKER_FAILOVER = False


@dataclass(frozen=True, slots=True)
class Phase32SemanticV2ProbeWindow:
    label: str
    start_date: str
    end_date: str


PHASE32_SEMANTIC_V2_PROBE_WINDOWS = (
    Phase32SemanticV2ProbeWindow("research_boundary", "2021-08-16", "2021-08-20"),
    Phase32SemanticV2ProbeWindow("early_history", "2022-01-03", "2022-01-07"),
    Phase32SemanticV2ProbeWindow("mid_history", "2023-08-14", "2023-08-18"),
    Phase32SemanticV2ProbeWindow("development_boundary", "2026-05-04", "2026-05-08"),
    Phase32SemanticV2ProbeWindow("protected_boundary", "2026-08-07", "2026-08-11"),
)


class Phase32SemanticV2FeasibilityError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise Phase32SemanticV2FeasibilityError(
            f"invalid frozen semantic V2 probe date {value!r}"
        ) from exc


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE32_SEMANTIC_V2_CONTRACT_VERSION,
        "accepted_core_v2_fingerprint": PHASE32_ACCEPTED_CORE_V2_FINGERPRINT,
        "rejected_semantic_v1_fingerprint": PHASE32_REJECTED_SEMANTIC_V1_FINGERPRINT,
        "research_start": PHASE32_SEMANTIC_V2_RESEARCH_START,
        "probe_windows": [asdict(window) for window in PHASE32_SEMANTIC_V2_PROBE_WINDOWS],
        "sample_per_window": PHASE32_SEMANTIC_V2_SAMPLE_PER_WINDOW,
        "sources": {
            "index": "/stocks/filings/vX/index?form_type=8-K",
            "disclosures": "/stocks/filings/8-K/vX/disclosures",
            "text": "/stocks/filings/8-K/vX/text",
            "taxonomy": "/stocks/taxonomies/vX/disclosures",
            "sec": "data.sec.gov/submissions",
        },
        "identity_rule": PHASE32_SEMANTIC_V2_IDENTITY_RULE,
        "ticker_rule": PHASE32_SEMANTIC_V2_TICKER_RULE,
        "support_rule": PHASE32_SEMANTIC_V2_SUPPORT_RULE,
        "alpha_hypotheses_frozen": PHASE32_SEMANTIC_V2_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": PHASE32_SEMANTIC_V2_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": PHASE32_SEMANTIC_V2_PROTECTED_OUTCOME_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": PHASE32_SEMANTIC_V2_PROVIDER_WRITES,
            "broker_reads": PHASE32_SEMANTIC_V2_BROKER_READS,
            "broker_writes": PHASE32_SEMANTIC_V2_BROKER_WRITES,
            "order_writes": PHASE32_SEMANTIC_V2_ORDER_WRITES,
            "paper_submits": PHASE32_SEMANTIC_V2_PAPER_SUBMITS,
            "live_writes": PHASE32_SEMANTIC_V2_LIVE_WRITES,
            "automation_writes": PHASE32_SEMANTIC_V2_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE32_SEMANTIC_V2_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase32_semantic_v2_fingerprint() -> str:
    raw = json.dumps(
        _fingerprint_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _immutable_write(path: Path, text: str, *, label: str) -> str:
    expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if path.is_file():
        existing_sha = sha256_file(path)
        if existing_sha != expected_sha:
            raise Phase32SemanticV2FeasibilityError(
                f"Phase32 semantic V2 {label} evidence drifted for immutable artifact {path}; "
                f"existing={existing_sha} current={expected_sha}"
            )
        return existing_sha
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    if sha256_file(path) != expected_sha:
        raise Phase32SemanticV2FeasibilityError(
            f"immutable Phase32 semantic V2 {label} hash mismatch: {path}"
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
    limit = PHASE32_SEMANTIC_V2_SAMPLE_PER_WINDOW
    if len(ordered) <= limit:
        return tuple(ordered)
    half = limit // 2
    return tuple(ordered[:half] + ordered[-half:])


def _normalized_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _ordered_token_coverage(needle: object, haystack: object) -> float:
    needle_tokens = _normalized_text(needle).split()
    haystack_tokens = _normalized_text(haystack).split()
    if not needle_tokens:
        return 0.0
    cursor = 0
    matched = 0
    for token in haystack_tokens:
        if cursor < len(needle_tokens) and token == needle_tokens[cursor]:
            cursor += 1
            matched += 1
    return matched / len(needle_tokens)


def _taxonomy_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("primary_category") or ""),
        str(row.get("secondary_category") or ""),
        str(row.get("tertiary_category") or ""),
    )


def _padded_cik(value: object) -> str:
    text = str(value or "").strip()
    if not text.isdigit():
        return ""
    return text.zfill(10)


def _ticker_relation(
    disclosure_tickers: set[str], index_tickers: set[str], text_ticker: str | None
) -> str:
    if not disclosure_tickers and not index_tickers and text_ticker is None:
        return "ALL_UNMAPPED"
    if disclosure_tickers & index_tickers:
        return "DISCLOSURE_INDEX_OVERLAP"
    if text_ticker is not None and text_ticker in disclosure_tickers:
        return "DISCLOSURE_TEXT_AGREE_INDEX_DIFFERS"
    if text_ticker is not None and text_ticker in index_tickers:
        return "INDEX_TEXT_AGREE_DISCLOSURE_DIFFERS"
    return "OTHER_MAPPED_DISAGREEMENT"


class Phase32SemanticSourceFeasibilityV2:
    """Corrected source-scope-aware semantic 8-K qualification before hypotheses/returns."""

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
        self.evidence_root = provider_root / "phase32_sec_8k_semantic_feasibility" / "v2"
        self.report_root = derived_root / "strategy_evaluation" / "phase32" / "semantic_v2"

    def report_path(self) -> Path:
        return self.report_root / "phase32_8k_semantic_feasibility_v2.json"

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
        ticker_relation_counts: dict[str, int] = {}
        lexical_exact_rows = 0
        lexical_total_rows = 0
        ordered_coverages: list[float] = []

        for window in PHASE32_SEMANTIC_V2_PROBE_WINDOWS:
            start = _parse_date(window.start_date)
            end = _parse_date(window.end_date)

            index_result = self.index_client.eight_k_window(start_date=start, end_date=end)
            index_rows = tuple(dict(row) for row in index_result.rows)
            index_sha = _immutable_write(
                self.evidence_root / "massive_index" / f"{window.label}.jsonl",
                _jsonl_text(index_rows),
                label="Massive semantic V2 index",
            )

            disclosure_result = self.semantic_client.disclosures_window(
                start_date=start, end_date=end
            )
            disclosure_rows = tuple(dict(row) for row in disclosure_result.rows)
            disclosure_sha = _immutable_write(
                self.evidence_root / "massive_disclosures" / f"{window.label}.jsonl",
                _jsonl_text(disclosure_rows),
                label="Massive semantic V2 disclosures",
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
            sampled_accessions = _sample_accessions(disclosure_rows, index_accessions)
            sample_reports: list[dict[str, object]] = []

            for accession in sampled_accessions:
                rows_for_accession = tuple(
                    row
                    for row in overlapping_disclosures
                    if str(row.get("accession_number") or "") == accession
                )
                index_matches = tuple(index_by_accession[accession])
                first_disclosure = rows_for_accession[0]
                cik = _padded_cik(first_disclosure.get("cik"))
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
                    raise Phase32SemanticV2FeasibilityError(
                        f"Phase32 semantic V2 expected exactly one original 8-K text row "
                        f"for {accession}, found {len(exact_text_rows)}"
                    )
                text_row = exact_text_rows[0]
                text_sha = _immutable_write(
                    self.evidence_root
                    / "massive_text"
                    / window.label
                    / f"{accession}.json",
                    _json_text(text_row),
                    label="Massive semantic V2 8-K text",
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
                    label="SEC semantic V2 submissions record",
                )

                cik_values = {
                    _padded_cik(row.get("cik"))
                    for row in (*rows_for_accession, *index_matches, text_row)
                }
                cik_values.discard("")
                sec_cik = _padded_cik(sec_record.issuer_cik)
                exact_cik_identity = (
                    len(cik_values) == 1
                    and cik in cik_values
                    and sec_cik == cik
                )
                filing_dates = {
                    str(row.get("filing_date") or "")
                    for row in (*rows_for_accession, *index_matches, text_row)
                }
                exact_filing_date_identity = filing_dates == {filing_date_text}
                category_valid = all(
                    _taxonomy_key(row) in taxonomy_keys for row in rows_for_accession
                )
                support_nonblank = all(
                    bool(_normalized_text(row.get("supporting_text")))
                    for row in rows_for_accession
                )
                sec_reconciled = (
                    sec_record.accession_number == accession
                    and sec_record.form == "8-K"
                    and sec_record.filing_date == filing_date_text
                    and bool(sec_record.acceptance_datetime)
                    and sec_cik == cik
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
                    if isinstance(row.get("ticker"), str) and str(row["ticker"]).strip()
                }
                raw_text_ticker = text_row.get("ticker")
                text_ticker = (
                    str(raw_text_ticker)
                    if isinstance(raw_text_ticker, str) and raw_text_ticker.strip()
                    else None
                )
                ticker_relation = _ticker_relation(
                    disclosure_tickers, index_tickers, text_ticker
                )
                ticker_relation_counts[ticker_relation] = (
                    ticker_relation_counts.get(ticker_relation, 0) + 1
                )

                lexical_rows: list[dict[str, object]] = []
                norm_items = _normalized_text(text_row.get("items_text"))
                for row in rows_for_accession:
                    norm_support = _normalized_text(row.get("supporting_text"))
                    exact_items_substring = bool(norm_support) and norm_support in norm_items
                    ordered_coverage = _ordered_token_coverage(
                        row.get("supporting_text"), text_row.get("items_text")
                    )
                    lexical_total_rows += 1
                    lexical_exact_rows += int(exact_items_substring)
                    ordered_coverages.append(ordered_coverage)
                    lexical_rows.append(
                        {
                            "category": list(_taxonomy_key(row)),
                            "supporting_text_nonblank": bool(norm_support),
                            "exact_normalized_substring_of_items_text": exact_items_substring,
                            "ordered_token_coverage_in_items_text": ordered_coverage,
                        }
                    )

                sample_reports.append(
                    {
                        "accession_number": accession,
                        "cik": cik,
                        "filing_date": filing_date_text,
                        "disclosure_rows": len(rows_for_accession),
                        "index_rows": len(index_matches),
                        "exact_cik_identity": exact_cik_identity,
                        "exact_filing_date_identity": exact_filing_date_identity,
                        "taxonomy_categories_valid": category_valid,
                        "supporting_text_nonblank": support_nonblank,
                        "sec_accession_form_filing_date_cik_acceptance_reconciled": sec_reconciled,
                        "disclosure_tickers": sorted(disclosure_tickers),
                        "index_tickers": sorted(index_tickers),
                        "text_ticker": text_ticker,
                        "ticker_relation": ticker_relation,
                        "ticker_used_as_identity": False,
                        "items_text_scope_diagnostics": lexical_rows,
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
                    "index_rows": len(index_rows),
                    "index_sha256": index_sha,
                    "index_pages": index_result.page_count,
                    "index_request_ids": list(index_result.request_ids),
                    "disclosure_rows": len(disclosure_rows),
                    "disclosure_sha256": disclosure_sha,
                    "disclosure_pages": disclosure_result.page_count,
                    "disclosure_request_ids": list(disclosure_result.request_ids),
                    "original_8k_overlap_rows": len(overlapping_disclosures),
                    "all_disclosures_overlap_original_8k_index": (
                        len(overlapping_disclosures) == len(disclosure_rows)
                    ),
                    "sampled_accessions": list(sampled_accessions),
                    "sample_reports": sample_reports,
                    "window_nonempty": bool(disclosure_rows),
                    "window_has_sample": bool(sampled_accessions),
                    "sample_identity_pass": all(
                        bool(sample["exact_cik_identity"])
                        and bool(sample["exact_filing_date_identity"])
                        for sample in sample_reports
                    ),
                    "sample_taxonomy_pass": all(
                        bool(sample["taxonomy_categories_valid"])
                        for sample in sample_reports
                    ),
                    "sample_support_pass": all(
                        bool(sample["supporting_text_nonblank"])
                        for sample in sample_reports
                    ),
                    "sample_sec_reconciliation_pass": all(
                        bool(
                            sample[
                                "sec_accession_form_filing_date_cik_acceptance_reconciled"
                            ]
                        )
                        for sample in sample_reports
                    ),
                }
            )
            total_disclosures += len(disclosure_rows)
            total_index_rows += len(index_rows)
            total_samples += len(sampled_accessions)

        checks = {
            "accepted_core_v2_fingerprint_pinned": (
                PHASE32_ACCEPTED_CORE_V2_FINGERPRINT
                == "978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4"
            ),
            "rejected_semantic_v1_fingerprint_preserved": (
                PHASE32_REJECTED_SEMANTIC_V1_FINGERPRINT
                == "ddab8e28f0e400033f2fd968c90e20f7e1619c0a10a29ebd7616050e1b502e82"
            ),
            "taxonomy_nonempty": bool(taxonomy_rows),
            "taxonomy_has_versions": bool(taxonomy_versions),
            "all_probe_windows_nonempty": all(
                bool(report["window_nonempty"]) for report in window_reports
            ),
            "all_probe_windows_overlap_original_8k_index_completely": all(
                bool(report["all_disclosures_overlap_original_8k_index"])
                for report in window_reports
            ),
            "all_probe_windows_have_samples": all(
                bool(report["window_has_sample"]) for report in window_reports
            ),
            "all_sampled_accession_cik_dates_reconcile": all(
                bool(report["sample_identity_pass"]) for report in window_reports
            ),
            "all_sampled_categories_exist_in_taxonomy": all(
                bool(report["sample_taxonomy_pass"]) for report in window_reports
            ),
            "all_sampled_supporting_text_nonblank": all(
                bool(report["sample_support_pass"]) for report in window_reports
            ),
            "all_sampled_sec_records_reconcile": all(
                bool(report["sample_sec_reconciliation_pass"])
                for report in window_reports
            ),
            "ticker_fields_not_used_as_filing_identity": all(
                not bool(sample["ticker_used_as_identity"])
                for report in window_reports
                for sample in report["sample_reports"]
            ),
            "alpha_hypotheses_not_frozen": (
                PHASE32_SEMANTIC_V2_ALPHA_HYPOTHESES_FROZEN is False
            ),
            "target_outcomes_forbidden": (
                PHASE32_SEMANTIC_V2_TARGET_OUTCOME_READS_ALLOWED is False
            ),
            "protected_outcomes_forbidden": (
                PHASE32_SEMANTIC_V2_PROTECTED_OUTCOME_READS_ALLOWED is False
            ),
            "external_mutation_authority_zero": all(
                value == 0
                for value in (
                    PHASE32_SEMANTIC_V2_PROVIDER_WRITES,
                    PHASE32_SEMANTIC_V2_BROKER_READS,
                    PHASE32_SEMANTIC_V2_BROKER_WRITES,
                    PHASE32_SEMANTIC_V2_ORDER_WRITES,
                    PHASE32_SEMANTIC_V2_PAPER_SUBMITS,
                    PHASE32_SEMANTIC_V2_LIVE_WRITES,
                    PHASE32_SEMANTIC_V2_AUTOMATION_WRITES,
                )
            ),
            "automatic_broker_failover_disabled": (
                PHASE32_SEMANTIC_V2_AUTOMATIC_BROKER_FAILOVER is False
            ),
        }

        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, object] = {
            "contract_version": PHASE32_SEMANTIC_V2_CONTRACT_VERSION,
            "phase32_semantic_v2_fingerprint": phase32_semantic_v2_fingerprint(),
            "accepted_core_v2_fingerprint": PHASE32_ACCEPTED_CORE_V2_FINGERPRINT,
            "rejected_semantic_v1_fingerprint": PHASE32_REJECTED_SEMANTIC_V1_FINGERPRINT,
            "research_start": PHASE32_SEMANTIC_V2_RESEARCH_START,
            "identity_rule": PHASE32_SEMANTIC_V2_IDENTITY_RULE,
            "ticker_rule": PHASE32_SEMANTIC_V2_TICKER_RULE,
            "support_rule": PHASE32_SEMANTIC_V2_SUPPORT_RULE,
            "taxonomy_versions": taxonomy_versions,
            "taxonomy_rows": len(taxonomy_rows),
            "taxonomy_pages": taxonomy_result.page_count,
            "taxonomy_request_ids": list(taxonomy_result.request_ids),
            "taxonomy_sha256": taxonomy_sha,
            "windows": window_reports,
            "ticker_relation_counts": ticker_relation_counts,
            "items_text_scope_diagnostics": {
                "disclosure_rows_checked": lexical_total_rows,
                "exact_normalized_substring_rows": lexical_exact_rows,
                "minimum_ordered_token_coverage": (
                    min(ordered_coverages) if ordered_coverages else None
                ),
                "mean_ordered_token_coverage": (
                    sum(ordered_coverages) / len(ordered_coverages)
                    if ordered_coverages
                    else None
                ),
                "is_acceptance_gate": False,
                "reason": (
                    "Massive 8-K Text is the core Items projection, while disclosure "
                    "supporting_text is defined against the filing; lexical comparison is diagnostic only."
                ),
            },
            "total_index_rows": total_index_rows,
            "total_disclosure_rows": total_disclosures,
            "total_sampled_accessions": total_samples,
            "total_text_records_fetched": total_text_records,
            "total_sec_records_fetched": total_sec_records,
            "target_outcome_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "phase33_signal_to_trade_entry_satisfied": False,
            "provider_writes": PHASE32_SEMANTIC_V2_PROVIDER_WRITES,
            "broker_reads": PHASE32_SEMANTIC_V2_BROKER_READS,
            "broker_writes": PHASE32_SEMANTIC_V2_BROKER_WRITES,
            "order_writes": PHASE32_SEMANTIC_V2_ORDER_WRITES,
            "paper_submits": PHASE32_SEMANTIC_V2_PAPER_SUBMITS,
            "live_writes": PHASE32_SEMANTIC_V2_LIVE_WRITES,
            "automation_writes": PHASE32_SEMANTIC_V2_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE32_SEMANTIC_V2_AUTOMATIC_BROKER_FAILOVER,
            "checks": checks,
            "pass": all(checks.values()),
            "report_path": str(report_path),
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not bool(report["pass"]):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase32SemanticV2FeasibilityError(
                "Phase32 semantic V2 source feasibility failed: " + ", ".join(failed)
            )
        return report
