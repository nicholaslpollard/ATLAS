from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase30 import MassivePhase30NewsClient, parse_news_timestamp


PHASE30_FEASIBILITY_CONTRACT_VERSION = (
    "phase30-feasibility-v1-historical-news-pit-provenance-no-outcomes"
)
PHASE30_SOURCE_PHASE29_MERGE = "87c9450e1b21606b83489f16ff326235ae92eb2b"
PHASE30_PROVIDER_INSIGHTS_AUTHORITY = "RAW_PROVENANCE_ONLY_NOT_AUTHORIZED_FOR_ALPHA"
PHASE30_ALPHA_HYPOTHESES_FROZEN = False
PHASE30_TARGET_OUTCOME_READS_ALLOWED = False
PHASE30_PROTECTED_OUTCOME_READS_ALLOWED = False
PHASE30_PROVIDER_READS_ALLOWED = True
PHASE30_PROVIDER_WRITES = 0
PHASE30_BROKER_READS = 0
PHASE30_BROKER_WRITES = 0
PHASE30_ORDER_WRITES = 0
PHASE30_PAPER_SUBMITS = 0
PHASE30_LIVE_WRITES = 0
PHASE30_AUTOMATION_WRITES = 0
PHASE30_AUTOMATIC_BROKER_FAILOVER = False


@dataclass(frozen=True, slots=True)
class Phase30ProbeWindow:
    label: str
    start_utc: str
    end_utc: str


PHASE30_PROBE_WINDOWS = (
    Phase30ProbeWindow(
        label="research_start",
        start_utc="2021-08-16T00:00:00Z",
        end_utc="2021-08-16T23:59:59Z",
    ),
    Phase30ProbeWindow(
        label="development_end",
        start_utc="2026-05-06T00:00:00Z",
        end_utc="2026-05-06T23:59:59Z",
    ),
    Phase30ProbeWindow(
        label="protected_start",
        start_utc="2026-05-12T00:00:00Z",
        end_utc="2026-05-12T23:59:59Z",
    ),
    Phase30ProbeWindow(
        label="protected_end",
        start_utc="2026-08-11T00:00:00Z",
        end_utc="2026-08-11T23:59:59Z",
    ),
)


class Phase30FeasibilityError(RuntimeError):
    pass


def _parse_utc(value: str) -> datetime:
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise Phase30FeasibilityError(f"probe bound is not timezone-aware: {value}")
    return parsed.astimezone(UTC)


def _fingerprint_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE30_FEASIBILITY_CONTRACT_VERSION,
        "source_phase29_merge": PHASE30_SOURCE_PHASE29_MERGE,
        "probe_windows": [asdict(window) for window in PHASE30_PROBE_WINDOWS],
        "provider_path": "MassiveRESTClient:/v2/reference/news",
        "query_order": "asc",
        "query_sort": "published_utc",
        "query_page_limit": 1000,
        "provider_insights_authority": PHASE30_PROVIDER_INSIGHTS_AUTHORITY,
        "alpha_hypotheses_frozen": PHASE30_ALPHA_HYPOTHESES_FROZEN,
        "target_outcome_reads_allowed": PHASE30_TARGET_OUTCOME_READS_ALLOWED,
        "protected_outcome_reads_allowed": PHASE30_PROTECTED_OUTCOME_READS_ALLOWED,
        "provider_reads_allowed": PHASE30_PROVIDER_READS_ALLOWED,
        "external_mutation_authority": {
            "provider_writes": PHASE30_PROVIDER_WRITES,
            "broker_reads": PHASE30_BROKER_READS,
            "broker_writes": PHASE30_BROKER_WRITES,
            "order_writes": PHASE30_ORDER_WRITES,
            "paper_submits": PHASE30_PAPER_SUBMITS,
            "live_writes": PHASE30_LIVE_WRITES,
            "automation_writes": PHASE30_AUTOMATION_WRITES,
            "automatic_broker_failover": PHASE30_AUTOMATIC_BROKER_FAILOVER,
        },
    }


def phase30_feasibility_fingerprint() -> str:
    raw = json.dumps(_fingerprint_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _jsonl_text(rows: tuple[dict[str, object], ...]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    )


def _immutable_write(path: Path, text: str) -> str:
    expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if path.is_file():
        existing_sha = sha256_file(path)
        if existing_sha != expected_sha:
            raise Phase30FeasibilityError(
                f"historical news evidence drifted for immutable artifact {path}; "
                f"existing={existing_sha} current={expected_sha}"
            )
        return existing_sha
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, text)
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha:
        raise Phase30FeasibilityError(f"immutable evidence hash mismatch after write: {path}")
    return actual_sha


class Phase30NewsFeasibility:
    """Acquire bounded historical news evidence without reading market outcomes."""

    def __init__(self, settings: AtlasSettings, client: MassivePhase30NewsClient) -> None:
        self.settings = settings
        self.client = client
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "massive" / "phase30_news_feasibility" / "v1"
        self.report_root = derived_root / "strategy_evaluation" / "phase30" / "v1"

    def report_path(self) -> Path:
        return self.report_root / "phase30_news_feasibility.json"

    def evidence_path(self, label: str) -> Path:
        return self.evidence_root / f"{label}.jsonl"

    def run(self) -> dict[str, object]:
        window_reports: list[dict[str, object]] = []
        total_articles = 0
        total_ticker_linked = 0
        total_pages = 0

        for window in PHASE30_PROBE_WINDOWS:
            start = _parse_utc(window.start_utc)
            end = _parse_utc(window.end_utc)
            result = self.client.news_window(start_utc=start, end_utc=end)
            rows = tuple(dict(article) for article in result.articles)
            evidence_path = self.evidence_path(window.label)
            evidence_sha = _immutable_write(evidence_path, _jsonl_text(rows))

            ticker_linked = sum(1 for row in rows if bool(row.get("tickers")))
            insight_rows = sum(1 for row in rows if bool(row.get("insights")))
            min_published = (
                min(parse_news_timestamp(row["published_utc"]) for row in rows).isoformat()
                if rows
                else None
            )
            max_published = (
                max(parse_news_timestamp(row["published_utc"]) for row in rows).isoformat()
                if rows
                else None
            )
            report = {
                "label": window.label,
                "start_utc": window.start_utc,
                "end_utc": window.end_utc,
                "articles": len(rows),
                "ticker_linked_articles": ticker_linked,
                "articles_with_provider_insights": insight_rows,
                "successful_pages": result.page_count,
                "request_ids": list(result.request_ids),
                "min_published_utc": min_published,
                "max_published_utc": max_published,
                "evidence_path": str(evidence_path.resolve()),
                "evidence_sha256": evidence_sha,
                "nonempty": bool(rows),
                "ticker_linked_nonempty": ticker_linked > 0,
            }
            window_reports.append(report)
            total_articles += len(rows)
            total_ticker_linked += ticker_linked
            total_pages += result.page_count

        checks = {
            "source_phase29_merge_frozen": PHASE30_SOURCE_PHASE29_MERGE
            == "87c9450e1b21606b83489f16ff326235ae92eb2b",
            "all_exact_probe_windows_nonempty": all(
                bool(report["nonempty"]) for report in window_reports
            ),
            "all_probe_windows_have_ticker_linked_news": all(
                bool(report["ticker_linked_nonempty"]) for report in window_reports
            ),
            "all_evidence_hashes_present": all(
                len(str(report["evidence_sha256"])) == 64 for report in window_reports
            ),
            "alpha_hypotheses_not_frozen": PHASE30_ALPHA_HYPOTHESES_FROZEN is False,
            "target_outcomes_forbidden": PHASE30_TARGET_OUTCOME_READS_ALLOWED is False,
            "protected_outcomes_forbidden": PHASE30_PROTECTED_OUTCOME_READS_ALLOWED is False,
            "provider_reads_bounded_and_authorized": PHASE30_PROVIDER_READS_ALLOWED is True,
            "external_mutation_authority_zero": all(
                value == 0
                for value in (
                    PHASE30_PROVIDER_WRITES,
                    PHASE30_BROKER_READS,
                    PHASE30_BROKER_WRITES,
                    PHASE30_ORDER_WRITES,
                    PHASE30_PAPER_SUBMITS,
                    PHASE30_LIVE_WRITES,
                    PHASE30_AUTOMATION_WRITES,
                )
            ),
            "automatic_broker_failover_disabled": PHASE30_AUTOMATIC_BROKER_FAILOVER is False,
            "provider_insights_are_provenance_only": PHASE30_PROVIDER_INSIGHTS_AUTHORITY
            == "RAW_PROVENANCE_ONLY_NOT_AUTHORIZED_FOR_ALPHA",
        }

        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, object] = {
            "contract_version": PHASE30_FEASIBILITY_CONTRACT_VERSION,
            "phase30_feasibility_fingerprint": phase30_feasibility_fingerprint(),
            "source_phase29_merge": PHASE30_SOURCE_PHASE29_MERGE,
            "status": "FEASIBILITY_PASS" if all(checks.values()) else "FEASIBILITY_FAIL",
            "alpha_hypotheses_frozen": False,
            "provider_insights_authority": PHASE30_PROVIDER_INSIGHTS_AUTHORITY,
            "windows": window_reports,
            "total_articles": total_articles,
            "total_ticker_linked_articles": total_ticker_linked,
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
            raise Phase30FeasibilityError(
                "Phase30 historical-news feasibility failed: "
                + ", ".join(failed)
                + f"; report={report_path}"
            )
        return report
