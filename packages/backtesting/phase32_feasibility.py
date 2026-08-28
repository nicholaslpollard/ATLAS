from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase32 import MassivePhase32SECIndexClient
from packages.providers.sec_edgar import SECEDGARClient, SECSubmissionRecord


PHASE32_FEASIBILITY_CONTRACT_VERSION = (
    "phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes"
)
PHASE32_SOURCE_PHASE31_MERGE = "ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4"
PHASE32_DECLARED_MASSIVE_PLAN = "Stocks Starter"
PHASE32_ALPHA_HYPOTHESES_FROZEN = False
PHASE32_TARGET_OUTCOME_READS_ALLOWED = False
PHASE32_PROTECTED_OUTCOME_READS_ALLOWED = False
PHASE32_PROVIDER_READS_ALLOWED = True
PHASE32_PROVIDER_WRITES = 0
PHASE32_BROKER_READS = 0
PHASE32_BROKER_WRITES = 0
PHASE32_ORDER_WRITES = 0
PHASE32_PAPER_SUBMITS = 0
PHASE32_LIVE_WRITES = 0
PHASE32_AUTOMATION_WRITES = 0
PHASE32_AUTOMATIC_BROKER_FAILOVER = False
PHASE32_PUBLIC_AVAILABILITY_RULE = (
    "FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME"
)
PHASE32_SEC_SAMPLE_PER_WINDOW = 12


@dataclass(frozen=True, slots=True)
class Phase32ProbeWindow:
    label: str
    start_date: str
    end_date: str


PHASE32_PROBE_WINDOWS = (
    Phase32ProbeWindow("research_boundary", "2021-08-16", "2021-08-20"),
    Phase32ProbeWindow("mid_history", "2023-08-14", "2023-08-18"),
    Phase32ProbeWindow("development_boundary", "2026-05-04", "2026-05-08"),
    Phase32ProbeWindow("protected_boundary", "2026-08-07", "2026-08-11"),
)


class Phase32FeasibilityError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise Phase32FeasibilityError(f"invalid frozen probe date {value!r}") from exc


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE32_FEASIBILITY_CONTRACT_VERSION,
        "source_phase31_merge": PHASE32_SOURCE_PHASE31_MERGE,
        "declared_massive_plan": PHASE32_DECLARED_MASSIVE_PLAN,
        "probe_windows": [asdict(window) for window in PHASE32_PROBE_WINDOWS],
        "massive_source": "MassiveRESTClient:/stocks/filings/vX/index:form_type=8-K",
        "sec_source": "SECEDGARClient:data.sec.gov/submissions",
        "sec_sample_per_window": PHASE32_SEC_SAMPLE_PER_WINDOW,
        "public_availability_rule": PHASE32_PUBLIC_AVAILABILITY_RULE,
        "alpha_hypotheses_frozen": PHASE32_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": PHASE32_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": PHASE32_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": PHASE32_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": PHASE32_PROVIDER_WRITES,
            "broker_reads": PHASE32_BROKER_READS,
            "broker_writes": PHASE32_BROKER_WRITES,
            "order_writes": PHASE32_ORDER_WRITES,
            "paper_submits": PHASE32_PAPER_SUBMITS,
            "live_writes": PHASE32_LIVE_WRITES,
            "automation_writes": PHASE32_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE32_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase32_feasibility_fingerprint() -> str:
    raw = json.dumps(
        _fingerprint_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _immutable_write(path: Path, text: str, *, label: str) -> str:
    expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if path.is_file():
        existing_sha = sha256_file(path)
        if existing_sha != expected_sha:
            raise Phase32FeasibilityError(
                f"Phase32 {label} evidence drifted for immutable artifact {path}; "
                f"existing={existing_sha} current={expected_sha}"
            )
        return existing_sha
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    if sha256_file(path) != expected_sha:
        raise Phase32FeasibilityError(f"immutable Phase32 {label} hash mismatch: {path}")
    return expected_sha


def _jsonl_text(rows: tuple[dict[str, Any], ...]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    )


def _sample_rows(rows: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        accession = str(row.get("accession_number") or "")
        if accession and accession not in unique:
            unique[accession] = row
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda row: (
                str(row.get("filing_date") or ""),
                str(row.get("accession_number") or ""),
            ),
        )
    )
    if len(ordered) <= PHASE32_SEC_SAMPLE_PER_WINDOW:
        return ordered
    half = PHASE32_SEC_SAMPLE_PER_WINDOW // 2
    return ordered[:half] + ordered[-half:]


def _sec_record(
    row: dict[str, Any],
    metadata: SECSubmissionRecord,
    source_record_sha: str,
) -> dict[str, object]:
    filing_date = str(row["filing_date"])
    acceptance_date = metadata.acceptance_datetime[:10]
    return {
        "accession_number": str(row["accession_number"]),
        "cik": str(row["cik"]),
        "ticker": row.get("ticker"),
        "massive_filing_date": filing_date,
        "massive_filing_url": str(row["filing_url"]),
        "sec_source_url": metadata.source_url,
        "sec_accession_number": metadata.accession_number,
        "sec_issuer_cik": metadata.issuer_cik,
        "sec_filing_date": metadata.filing_date,
        "sec_form": metadata.form,
        "acceptance_datetime": metadata.acceptance_datetime,
        "acceptance_local_date": acceptance_date,
        "acceptance_date_differs_from_massive_filing_date": acceptance_date != filing_date,
        "sec_filing_date_differs_from_massive_filing_date": metadata.filing_date != filing_date,
        "item_codes": list(metadata.item_codes),
        "primary_document": metadata.primary_document,
        "sec_source_record_sha256": source_record_sha,
    }


class Phase32EightKFeasibility:
    """Prove 8-K discovery and official SEC metadata provenance without outcomes."""

    def __init__(
        self,
        settings: AtlasSettings,
        index_client: MassivePhase32SECIndexClient,
        sec_client: SECEDGARClient,
    ) -> None:
        self.settings = settings
        self.index_client = index_client
        self.sec_client = sec_client
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "phase32_sec_8k_feasibility" / "v2"
        self.report_root = derived_root / "strategy_evaluation" / "phase32" / "v2"

    def report_path(self) -> Path:
        return self.report_root / "phase32_8k_feasibility.json"

    def index_path(self, label: str) -> Path:
        return self.evidence_root / "massive_index" / f"{label}.jsonl"

    def sec_record_path(self, label: str, accession: str) -> Path:
        safe = accession.replace("/", "_").replace("\\", "_")
        return self.evidence_root / "sec_submissions" / label / f"{safe}.json"

    def run(self) -> dict[str, object]:
        window_reports: list[dict[str, object]] = []
        total_index_rows = 0
        total_ticker_linked = 0
        total_sec_records = 0
        total_item_codes = 0
        total_pages = 0

        for window in PHASE32_PROBE_WINDOWS:
            start = _parse_date(window.start_date)
            end = _parse_date(window.end_date)
            result = self.index_client.eight_k_window(start_date=start, end_date=end)
            rows = tuple(dict(row) for row in result.rows)
            index_sha = _immutable_write(
                self.index_path(window.label), _jsonl_text(rows), label="Massive index"
            )
            sample = _sample_rows(rows)
            sec_records: list[dict[str, object]] = []
            for row in sample:
                metadata = self.sec_client.filing_metadata(
                    cik=row["cik"],
                    accession_number=str(row["accession_number"]),
                    filing_date=str(row["filing_date"]),
                )
                source_record_sha = _immutable_write(
                    self.sec_record_path(window.label, str(row["accession_number"])),
                    metadata.source_record_json,
                    label="SEC submissions record",
                )
                sec_records.append(_sec_record(row, metadata, source_record_sha))

            ticker_values = {
                str(row["ticker"])
                for row in rows
                if isinstance(row.get("ticker"), str) and str(row["ticker"]).strip()
            }
            accession_matches = all(
                record["accession_number"] == record["sec_accession_number"]
                for record in sec_records
            )
            form_matches = all(record["sec_form"] == "8-K" for record in sec_records)
            filing_date_matches = all(
                record["sec_filing_date"] == record["massive_filing_date"]
                for record in sec_records
            )
            acceptance_complete = all(bool(record["acceptance_datetime"]) for record in sec_records)
            item_bearing = sum(1 for record in sec_records if record["item_codes"])
            unique_items = sorted(
                {
                    str(item)
                    for record in sec_records
                    for item in record["item_codes"]  # type: ignore[union-attr]
                }
            )
            mismatch_count = sum(
                1
                for record in sec_records
                if bool(record["acceptance_date_differs_from_massive_filing_date"])
            )
            sec_date_mismatch_count = sum(
                1
                for record in sec_records
                if bool(record["sec_filing_date_differs_from_massive_filing_date"])
            )
            window_reports.append(
                {
                    "label": window.label,
                    "start_date": window.start_date,
                    "end_date": window.end_date,
                    "index_rows": len(rows),
                    "ticker_linked_rows": sum(
                        1
                        for row in rows
                        if isinstance(row.get("ticker"), str) and str(row["ticker"]).strip()
                    ),
                    "unique_tickers": len(ticker_values),
                    "successful_massive_pages": result.page_count,
                    "massive_request_ids": list(result.request_ids),
                    "massive_index_sha256": index_sha,
                    "sec_sample_rows": len(sample),
                    "sec_records_fetched": len(sec_records),
                    "sec_accession_matches": accession_matches,
                    "sec_original_8k_matches": form_matches,
                    "sec_filing_date_matches": filing_date_matches,
                    "acceptance_datetime_complete": acceptance_complete,
                    "sec_records_with_item_codes": item_bearing,
                    "unique_item_codes": unique_items,
                    "acceptance_date_massive_filing_date_mismatch_count": mismatch_count,
                    "sec_filing_date_massive_filing_date_mismatch_count": sec_date_mismatch_count,
                    "sec_records": sec_records,
                    "nonempty": bool(rows),
                    "ticker_linked_nonempty": bool(ticker_values),
                    "sec_sample_nonempty": bool(sec_records),
                    "item_codes_present": item_bearing > 0,
                }
            )
            total_index_rows += len(rows)
            total_ticker_linked += sum(
                1
                for row in rows
                if isinstance(row.get("ticker"), str) and str(row["ticker"]).strip()
            )
            total_sec_records += len(sec_records)
            total_item_codes += sum(len(record["item_codes"]) for record in sec_records)  # type: ignore[arg-type]
            total_pages += result.page_count

        checks = {
            "source_phase31_merge_frozen": PHASE32_SOURCE_PHASE31_MERGE
            == "ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4",
            "all_probe_windows_nonempty": all(bool(w["nonempty"]) for w in window_reports),
            "all_probe_windows_have_ticker_linkage": all(
                bool(w["ticker_linked_nonempty"]) for w in window_reports
            ),
            "all_probe_windows_have_sec_samples": all(
                bool(w["sec_sample_nonempty"]) for w in window_reports
            ),
            "all_sampled_accessions_reconcile": all(
                bool(w["sec_accession_matches"]) for w in window_reports
            ),
            "all_sampled_forms_are_original_8k": all(
                bool(w["sec_original_8k_matches"]) for w in window_reports
            ),
            "all_sampled_sec_filing_dates_match_massive": all(
                bool(w["sec_filing_date_matches"]) for w in window_reports
            ),
            "all_sampled_acceptance_datetimes_complete": all(
                bool(w["acceptance_datetime_complete"]) for w in window_reports
            ),
            "all_probe_windows_have_item_codes": all(
                bool(w["item_codes_present"]) for w in window_reports
            ),
            "alpha_hypotheses_not_frozen": PHASE32_ALPHA_HYPOTHESES_FROZEN is False,
            "target_outcomes_forbidden": PHASE32_TARGET_OUTCOME_READS_ALLOWED is False,
            "protected_outcomes_forbidden": PHASE32_PROTECTED_OUTCOME_READS_ALLOWED is False,
            "provider_reads_bounded_and_authorized": PHASE32_PROVIDER_READS_ALLOWED is True,
            "acceptance_timestamp_rule_frozen_for_feasibility": PHASE32_PUBLIC_AVAILABILITY_RULE
            == "FIRST_XNYS_SESSION_STRICTLY_AFTER_SEC_ACCEPTANCE_DATETIME",
            "external_mutation_authority_zero": all(
                value == 0
                for value in (
                    PHASE32_PROVIDER_WRITES,
                    PHASE32_BROKER_READS,
                    PHASE32_BROKER_WRITES,
                    PHASE32_ORDER_WRITES,
                    PHASE32_PAPER_SUBMITS,
                    PHASE32_LIVE_WRITES,
                    PHASE32_AUTOMATION_WRITES,
                )
            ),
            "automatic_broker_failover_disabled": PHASE32_AUTOMATIC_BROKER_FAILOVER is False,
        }
        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, object] = {
            "contract_version": PHASE32_FEASIBILITY_CONTRACT_VERSION,
            "phase32_feasibility_fingerprint": phase32_feasibility_fingerprint(),
            "source_phase31_merge": PHASE32_SOURCE_PHASE31_MERGE,
            "declared_massive_plan": PHASE32_DECLARED_MASSIVE_PLAN,
            "massive_endpoint": "/stocks/filings/vX/index",
            "massive_form_type": "8-K",
            "sec_source": "data.sec.gov/submissions",
            "public_availability_rule": PHASE32_PUBLIC_AVAILABILITY_RULE,
            "alpha_hypotheses_frozen": False,
            "windows": window_reports,
            "total_index_rows": total_index_rows,
            "total_ticker_linked_rows": total_ticker_linked,
            "total_sec_records_fetched": total_sec_records,
            "total_item_codes": total_item_codes,
            "successful_massive_pages": total_pages,
            "target_outcome_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "phase33_signal_to_trade_entry_satisfied": False,
            "checks": checks,
            "pass": all(checks.values()),
            "report_path": str(report_path.resolve()),
        }
        atomic_write_text(
            report_path,
            json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        )
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase32FeasibilityError(
                "Phase32 SEC 8-K feasibility checks failed: " + ", ".join(failed)
            )
        return report
