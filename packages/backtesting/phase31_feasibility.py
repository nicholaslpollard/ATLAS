from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase31 import MassivePhase31Form4Client, parse_form4_date


PHASE31_FEASIBILITY_CONTRACT_VERSION = (
    "phase31-feasibility-v1-sec-form4-insider-transactions-no-market-outcomes"
)
PHASE31_SOURCE_PHASE30_MERGE = "bf673ad82886e7172db0d54a33dd9612fa9ea29e"
PHASE31_DECLARED_MASSIVE_PLAN = "Stocks Starter"
PHASE31_ALPHA_HYPOTHESES_FROZEN = False
PHASE31_TARGET_OUTCOME_READS_ALLOWED = False
PHASE31_PROTECTED_OUTCOME_READS_ALLOWED = False
PHASE31_PROVIDER_READS_ALLOWED = True
PHASE31_PROVIDER_WRITES = 0
PHASE31_BROKER_READS = 0
PHASE31_BROKER_WRITES = 0
PHASE31_ORDER_WRITES = 0
PHASE31_PAPER_SUBMITS = 0
PHASE31_LIVE_WRITES = 0
PHASE31_AUTOMATION_WRITES = 0
PHASE31_AUTOMATIC_BROKER_FAILOVER = False
PHASE31_PUBLIC_AVAILABILITY_RULE = "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE"


@dataclass(frozen=True, slots=True)
class Phase31ProbeWindow:
    label: str
    start_date: str
    end_date: str


PHASE31_PROBE_WINDOWS = (
    Phase31ProbeWindow("research_boundary", "2021-08-16", "2021-08-20"),
    Phase31ProbeWindow("mid_history", "2023-08-14", "2023-08-18"),
    Phase31ProbeWindow("development_boundary", "2026-05-04", "2026-05-08"),
    Phase31ProbeWindow("protected_boundary", "2026-08-07", "2026-08-11"),
)


PHASE31_COMPLETENESS_FIELDS = (
    "accession_number",
    "filing_date",
    "issuer_cik",
    "owner_cik",
    "tickers",
    "record_type",
    "transaction_code",
    "transaction_date",
    "transaction_shares",
    "transaction_price_per_share",
    "transaction_value",
    "shares_owned_following_transaction",
    "direct_or_indirect",
    "security_type",
    "is_officer",
    "is_director",
    "is_ten_percent_owner",
    "aff_10b5_one",
    "transaction_timeliness",
)


class Phase31FeasibilityError(RuntimeError):
    pass


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise Phase31FeasibilityError(f"invalid frozen probe date {value!r}") from exc


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE31_FEASIBILITY_CONTRACT_VERSION,
        "source_phase30_merge": PHASE31_SOURCE_PHASE30_MERGE,
        "declared_massive_plan": PHASE31_DECLARED_MASSIVE_PLAN,
        "probe_windows": [asdict(window) for window in PHASE31_PROBE_WINDOWS],
        "provider_path": "MassiveRESTClient:/stocks/filings/vX/form-4",
        "form_type": "4",
        "query_sort": "filing_date.asc",
        "query_page_limit": 10000,
        "public_availability_rule": PHASE31_PUBLIC_AVAILABILITY_RULE,
        "alpha_hypotheses_frozen": PHASE31_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": PHASE31_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": PHASE31_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": PHASE31_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": PHASE31_PROVIDER_WRITES,
            "broker_reads": PHASE31_BROKER_READS,
            "broker_writes": PHASE31_BROKER_WRITES,
            "order_writes": PHASE31_ORDER_WRITES,
            "paper_submits": PHASE31_PAPER_SUBMITS,
            "live_writes": PHASE31_LIVE_WRITES,
            "automation_writes": PHASE31_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE31_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase31_feasibility_fingerprint() -> str:
    raw = json.dumps(_fingerprint_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _jsonl_text(rows: tuple[dict[str, Any], ...]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    )


def _immutable_write(path: Path, text: str) -> str:
    expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if path.is_file():
        existing_sha = sha256_file(path)
        if existing_sha != expected_sha:
            raise Phase31FeasibilityError(
                f"Form 4 feasibility evidence drifted for immutable artifact {path}; "
                f"existing={existing_sha} current={expected_sha}"
            )
        return existing_sha
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        raise Phase31FeasibilityError(f"immutable evidence hash mismatch after write: {path}")
    return actual_sha


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, dict, set)):
        return bool(value)
    return True


def _ticker_values(rows: tuple[dict[str, Any], ...]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        tickers = row.get("tickers") or []
        if isinstance(tickers, list):
            values.update(ticker for ticker in tickers if isinstance(ticker, str) and ticker)
    return values


def _completeness(rows: tuple[dict[str, Any], ...]) -> dict[str, dict[str, object]]:
    total = len(rows)
    result: dict[str, dict[str, object]] = {}
    for field in PHASE31_COMPLETENESS_FIELDS:
        count = sum(1 for row in rows if _present(row.get(field)))
        result[field] = {
            "present": count,
            "total": total,
            "fraction": (count / total) if total else 0.0,
        }
    return result


def _canonical_duplicate_count(rows: tuple[dict[str, Any], ...]) -> int:
    counter = Counter(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        for row in rows
    )
    return sum(count - 1 for count in counter.values() if count > 1)


def _lag_stats(rows: tuple[dict[str, Any], ...]) -> dict[str, object]:
    lags: list[int] = []
    for row in rows:
        if row.get("record_type") != "transaction" or row.get("transaction_date") is None:
            continue
        filing = parse_form4_date(row.get("filing_date"), field="filing_date")
        transaction = parse_form4_date(row.get("transaction_date"), field="transaction_date")
        lags.append((filing - transaction).days)
    return {
        "rows_with_transaction_and_filing_dates": len(lags),
        "min_calendar_days": min(lags) if lags else None,
        "max_calendar_days": max(lags) if lags else None,
        "negative_lag_rows": sum(1 for lag in lags if lag < 0),
        "same_day_rows": sum(1 for lag in lags if lag == 0),
        "one_to_two_day_rows": sum(1 for lag in lags if 1 <= lag <= 2),
        "late_over_two_day_rows": sum(1 for lag in lags if lag > 2),
    }


class Phase31Form4Feasibility:
    """Acquire bounded Form-4 evidence and field statistics without market outcomes."""

    def __init__(self, settings: AtlasSettings, client: MassivePhase31Form4Client) -> None:
        self.settings = settings
        self.client = client
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "massive" / "phase31_form4_feasibility" / "v1"
        self.report_root = derived_root / "strategy_evaluation" / "phase31" / "v1"

    def report_path(self) -> Path:
        return self.report_root / "phase31_form4_feasibility.json"

    def evidence_path(self, label: str) -> Path:
        return self.evidence_root / f"{label}.jsonl"

    def run(self) -> dict[str, object]:
        window_reports: list[dict[str, object]] = []
        total_rows = 0
        total_transaction_rows = 0
        total_ticker_linked_rows = 0
        total_pages = 0
        aggregate_codes: Counter[str] = Counter()

        for window in PHASE31_PROBE_WINDOWS:
            start = _parse_date(window.start_date)
            end = _parse_date(window.end_date)
            result = self.client.form4_window(start_date=start, end_date=end)
            rows = tuple(dict(row) for row in result.rows)
            evidence_path = self.evidence_path(window.label)
            evidence_sha = _immutable_write(evidence_path, _jsonl_text(rows))

            transaction_rows = tuple(row for row in rows if row.get("record_type") == "transaction")
            transaction_codes = Counter(
                str(row.get("transaction_code"))
                for row in transaction_rows
                if _present(row.get("transaction_code"))
            )
            aggregate_codes.update(transaction_codes)
            ticker_linked_rows = sum(1 for row in rows if _present(row.get("tickers")))
            unique_accessions = {str(row["accession_number"]) for row in rows}
            unique_issuers = {str(row["issuer_cik"]) for row in rows}
            unique_owners = {str(row["owner_cik"]) for row in rows}
            unique_tickers = _ticker_values(rows)
            lag_stats = _lag_stats(rows)

            window_report: dict[str, object] = {
                "label": window.label,
                "start_date": window.start_date,
                "end_date": window.end_date,
                "rows": len(rows),
                "transaction_rows": len(transaction_rows),
                "ticker_linked_rows": ticker_linked_rows,
                "unique_accessions": len(unique_accessions),
                "unique_issuers": len(unique_issuers),
                "unique_owners": len(unique_owners),
                "unique_tickers": len(unique_tickers),
                "transaction_code_counts": dict(sorted(transaction_codes.items())),
                "purchase_rows_P": transaction_codes.get("P", 0),
                "sale_rows_S": transaction_codes.get("S", 0),
                "non_derivative_transaction_rows": sum(
                    1 for row in transaction_rows if row.get("security_type") == "non-derivative"
                ),
                "ten_b5_1_true_rows": sum(1 for row in transaction_rows if row.get("aff_10b5_one") is True),
                "ten_b5_1_false_rows": sum(1 for row in transaction_rows if row.get("aff_10b5_one") is False),
                "late_transaction_rows": sum(
                    1 for row in transaction_rows if row.get("transaction_timeliness") == "L"
                ),
                "canonical_duplicate_rows": _canonical_duplicate_count(rows),
                "field_completeness": _completeness(transaction_rows),
                "filing_transaction_lag": lag_stats,
                "successful_pages": result.page_count,
                "request_ids": list(result.request_ids),
                "evidence_path": str(evidence_path.resolve()),
                "evidence_sha256": evidence_sha,
                "nonempty": bool(rows),
                "transaction_nonempty": bool(transaction_rows),
                "ticker_linked_nonempty": ticker_linked_rows > 0,
            }
            window_reports.append(window_report)
            total_rows += len(rows)
            total_transaction_rows += len(transaction_rows)
            total_ticker_linked_rows += ticker_linked_rows
            total_pages += result.page_count

        negative_lag_rows = sum(
            int(report["filing_transaction_lag"]["negative_lag_rows"])  # type: ignore[index]
            for report in window_reports
        )
        checks = {
            "source_phase30_merge_frozen": PHASE31_SOURCE_PHASE30_MERGE
            == "bf673ad82886e7172db0d54a33dd9612fa9ea29e",
            "all_probe_windows_nonempty": all(bool(report["nonempty"]) for report in window_reports),
            "all_probe_windows_have_transactions": all(
                bool(report["transaction_nonempty"]) for report in window_reports
            ),
            "all_probe_windows_have_ticker_linkage": all(
                bool(report["ticker_linked_nonempty"]) for report in window_reports
            ),
            "purchase_population_present": aggregate_codes.get("P", 0) > 0,
            "sale_population_present": aggregate_codes.get("S", 0) > 0,
            "transaction_dates_do_not_postdate_filings": negative_lag_rows == 0,
            "all_evidence_hashes_present": all(
                len(str(report["evidence_sha256"])) == 64 for report in window_reports
            ),
            "alpha_hypotheses_not_frozen": PHASE31_ALPHA_HYPOTHESES_FROZEN is False,
            "target_outcomes_forbidden": PHASE31_TARGET_OUTCOME_READS_ALLOWED is False,
            "protected_outcomes_forbidden": PHASE31_PROTECTED_OUTCOME_READS_ALLOWED is False,
            "provider_reads_bounded_and_authorized": PHASE31_PROVIDER_READS_ALLOWED is True,
            "conservative_public_availability_rule_frozen": PHASE31_PUBLIC_AVAILABILITY_RULE
            == "NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE",
            "external_mutation_authority_zero": all(
                value == 0
                for value in (
                    PHASE31_PROVIDER_WRITES,
                    PHASE31_BROKER_READS,
                    PHASE31_BROKER_WRITES,
                    PHASE31_ORDER_WRITES,
                    PHASE31_PAPER_SUBMITS,
                    PHASE31_LIVE_WRITES,
                    PHASE31_AUTOMATION_WRITES,
                )
            ),
            "automatic_broker_failover_disabled": PHASE31_AUTOMATIC_BROKER_FAILOVER is False,
        }

        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, object] = {
            "contract_version": PHASE31_FEASIBILITY_CONTRACT_VERSION,
            "phase31_feasibility_fingerprint": phase31_feasibility_fingerprint(),
            "source_phase30_merge": PHASE31_SOURCE_PHASE30_MERGE,
            "declared_massive_plan": PHASE31_DECLARED_MASSIVE_PLAN,
            "provider_endpoint": "/stocks/filings/vX/form-4",
            "provider_endpoint_status": "EARLY_ACCESS_BETA_REVALIDATE_IF_SCHEMA_OR_PLAN_CHANGES",
            "status": "FEASIBILITY_PASS" if all(checks.values()) else "FEASIBILITY_FAIL",
            "alpha_hypotheses_frozen": False,
            "public_availability_rule": PHASE31_PUBLIC_AVAILABILITY_RULE,
            "windows": window_reports,
            "total_rows": total_rows,
            "total_transaction_rows": total_transaction_rows,
            "total_ticker_linked_rows": total_ticker_linked_rows,
            "aggregate_transaction_code_counts": dict(sorted(aggregate_codes.items())),
            "successful_provider_pages": total_pages,
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
            "checks": checks,
            "report_path": str(report_path.resolve()),
            "pass": all(checks.values()),
        }
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        if not report["pass"]:
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase31FeasibilityError(
                "Phase31 Form-4 feasibility failed: "
                + ", ".join(failed)
                + f"; report={report_path}"
            )
        return report
