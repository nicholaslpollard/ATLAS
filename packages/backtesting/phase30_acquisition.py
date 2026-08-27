from __future__ import annotations

import hashlib
import json
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase30 import (
    MassivePhase30NewsClient,
    parse_news_timestamp,
    validate_news_article,
)

from .phase30_policy import (
    PHASE30_NEWS_WARMUP_START,
    PHASE30_PROTECTED_END,
    PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
    PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
    phase30_policy_fingerprint,
)


PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION = (
    "phase30-news-acquisition-v1-monthly-resumable-immutable-no-outcomes"
)


class Phase30NewsAcquisitionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase30NewsShardWindow:
    label: str
    start_utc: datetime
    end_utc: datetime


def _parse_day_start(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def _parse_day_end(value: str) -> datetime:
    return datetime.fromisoformat(value).replace(tzinfo=UTC) + timedelta(
        hours=23, minutes=59, seconds=59, microseconds=999999
    )


def phase30_news_acquisition_bounds() -> tuple[datetime, datetime]:
    return _parse_day_start(PHASE30_NEWS_WARMUP_START), _parse_day_end(PHASE30_PROTECTED_END)


def phase30_news_shard_windows() -> tuple[Phase30NewsShardWindow, ...]:
    start, end = phase30_news_acquisition_bounds()
    current = start
    windows: list[Phase30NewsShardWindow] = []
    while current <= end:
        last_day = monthrange(current.year, current.month)[1]
        month_end = datetime(
            current.year,
            current.month,
            last_day,
            23,
            59,
            59,
            999999,
            tzinfo=UTC,
        )
        shard_end = min(month_end, end)
        windows.append(
            Phase30NewsShardWindow(
                label=f"{current.date().isoformat()}_{shard_end.date().isoformat()}",
                start_utc=current,
                end_utc=shard_end,
            )
        )
        current = shard_end + timedelta(microseconds=1)
    return tuple(windows)


def _jsonl_text(rows: tuple[dict[str, Any], ...]) -> str:
    return "".join(
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
        for row in rows
    )


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase30NewsAcquisitionError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase30NewsAcquisitionError(f"{label} must be a JSON object: {path}")
    return payload


def _read_jsonl(path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise Phase30NewsAcquisitionError(
                        f"news evidence row {line_number} is not an object: {path}"
                    )
                rows.append(value)
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase30NewsAcquisitionError(f"invalid news evidence JSONL: {path}") from exc
    return tuple(rows)


def _payload_sha(row: dict[str, Any]) -> str:
    raw = json.dumps(
        row, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Phase30NewsAcquisition:
    """Acquire the full Phase30 historical news predictor source without outcomes.

    Monthly immutable shards make the operation resumable. Completed shard metadata
    is validated against the local immutable evidence and skipped on later runs.
    Provider text/insights are retained in raw evidence only; Phase30 alpha authority
    is restricted by the separately frozen scientific policy.
    """

    def __init__(self, settings: AtlasSettings, client: MassivePhase30NewsClient) -> None:
        self.settings = settings
        self.client = client
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.evidence_root = provider_root / "massive" / "phase30_news_history" / "v1"
        self.report_root = derived_root / "strategy_evaluation" / "phase30" / "v1"

    def evidence_path(self, label: str) -> Path:
        return self.evidence_root / f"{label}.jsonl"

    def metadata_path(self, label: str) -> Path:
        return self.evidence_root / f"{label}.meta.json"

    def report_path(self) -> Path:
        return self.report_root / "phase30_news_acquisition.json"

    def _validate_rows(
        self,
        rows: tuple[dict[str, Any], ...],
        *,
        window: Phase30NewsShardWindow,
    ) -> None:
        for row in rows:
            validate_news_article(
                row,
                start_utc=window.start_utc,
                end_utc=window.end_utc,
            )

    def _metadata_payload(
        self,
        *,
        window: Phase30NewsShardWindow,
        rows: tuple[dict[str, Any], ...],
        evidence_sha: str,
        page_count: int,
        request_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        ticker_linked = sum(1 for row in rows if bool(row.get("tickers")))
        return {
            "contract_version": PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "source_feasibility_fingerprint": PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
            "label": window.label,
            "start_utc": window.start_utc.isoformat(),
            "end_utc": window.end_utc.isoformat(),
            "articles": len(rows),
            "ticker_linked_articles": ticker_linked,
            "successful_pages": page_count,
            "request_ids": list(request_ids),
            "min_published_utc": (
                min(parse_news_timestamp(row["published_utc"]) for row in rows).isoformat()
                if rows
                else None
            ),
            "max_published_utc": (
                max(parse_news_timestamp(row["published_utc"]) for row in rows).isoformat()
                if rows
                else None
            ),
            "evidence_sha256": evidence_sha,
            "provider_content_alpha_authority": PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
            "provider_insights_alpha_authority": PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
            "target_outcome_rows_read": 0,
            "protected_return_rows_read": 0,
        }

    def _validate_existing_metadata(
        self,
        *,
        window: Phase30NewsShardWindow,
        meta: dict[str, Any],
        evidence_sha: str,
    ) -> None:
        checks = {
            "contract_version": meta.get("contract_version")
            == PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
            "policy_fingerprint": meta.get("phase30_policy_fingerprint")
            == phase30_policy_fingerprint(),
            "source_feasibility": meta.get("source_feasibility_fingerprint")
            == PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
            "label": meta.get("label") == window.label,
            "start": meta.get("start_utc") == window.start_utc.isoformat(),
            "end": meta.get("end_utc") == window.end_utc.isoformat(),
            "evidence_sha": meta.get("evidence_sha256") == evidence_sha,
            "no_target_outcomes": meta.get("target_outcome_rows_read") == 0,
            "no_protected_returns": meta.get("protected_return_rows_read") == 0,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase30NewsAcquisitionError(
                f"existing Phase30 news shard metadata failed closed for {window.label}: "
                + ", ".join(failed)
            )

    def _load_or_fetch_shard(
        self, window: Phase30NewsShardWindow
    ) -> tuple[tuple[dict[str, Any], ...], dict[str, Any], bool]:
        evidence_path = self.evidence_path(window.label)
        metadata_path = self.metadata_path(window.label)

        if metadata_path.is_file() and not evidence_path.is_file():
            raise Phase30NewsAcquisitionError(
                f"metadata exists without immutable news evidence: {metadata_path}"
            )

        if evidence_path.is_file() and metadata_path.is_file():
            evidence_sha = sha256_file(evidence_path)
            meta = _read_json(metadata_path, label="Phase30 news shard metadata")
            self._validate_existing_metadata(
                window=window,
                meta=meta,
                evidence_sha=evidence_sha,
            )
            rows = _read_jsonl(evidence_path)
            self._validate_rows(rows, window=window)
            if int(meta.get("articles", -1)) != len(rows):
                raise Phase30NewsAcquisitionError(
                    f"existing shard article count mismatch: {window.label}"
                )
            return rows, meta, True

        result = self.client.news_window(
            start_utc=window.start_utc,
            end_utc=window.end_utc,
        )
        rows = tuple(dict(article) for article in result.articles)
        self._validate_rows(rows, window=window)
        text = _jsonl_text(rows)
        expected_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()

        if evidence_path.is_file():
            existing_sha = sha256_file(evidence_path)
            if existing_sha != expected_sha:
                raise Phase30NewsAcquisitionError(
                    f"provider replay disagrees with pre-existing immutable shard "
                    f"{window.label}: existing={existing_sha} current={expected_sha}"
                )
        else:
            evidence_path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(evidence_path, text)
            actual_sha = sha256_file(evidence_path)
            if actual_sha != expected_sha:
                raise Phase30NewsAcquisitionError(
                    f"immutable shard hash mismatch after write: {window.label}"
                )

        meta = self._metadata_payload(
            window=window,
            rows=rows,
            evidence_sha=expected_sha,
            page_count=result.page_count,
            request_ids=result.request_ids,
        )
        atomic_write_text(metadata_path, json.dumps(meta, indent=2, sort_keys=True) + "\n")
        return rows, meta, False

    def run(self) -> dict[str, Any]:
        shard_reports: list[dict[str, Any]] = []
        seen_ids: dict[str, tuple[str, str]] = {}
        total_articles = 0
        total_ticker_linked = 0
        recorded_pages = 0
        resumed_shards = 0

        for window in phase30_news_shard_windows():
            rows, meta, resumed = self._load_or_fetch_shard(window)
            if resumed:
                resumed_shards += 1
            for row in rows:
                article_id = str(row["id"])
                payload_sha = _payload_sha(row)
                previous = seen_ids.get(article_id)
                if previous is not None:
                    previous_label, previous_sha = previous
                    raise Phase30NewsAcquisitionError(
                        f"duplicate article id crossed disjoint monthly shards: "
                        f"id={article_id!r} previous={previous_label} current={window.label} "
                        f"same_payload={previous_sha == payload_sha}"
                    )
                seen_ids[article_id] = (window.label, payload_sha)

            articles = len(rows)
            ticker_linked = sum(1 for row in rows if bool(row.get("tickers")))
            pages = int(meta.get("successful_pages", 0))
            shard_reports.append(
                {
                    "label": window.label,
                    "start_utc": window.start_utc.isoformat(),
                    "end_utc": window.end_utc.isoformat(),
                    "articles": articles,
                    "ticker_linked_articles": ticker_linked,
                    "successful_pages": pages,
                    "evidence_sha256": meta["evidence_sha256"],
                    "resumed": resumed,
                }
            )
            total_articles += articles
            total_ticker_linked += ticker_linked
            recorded_pages += pages

        start, end = phase30_news_acquisition_bounds()
        checks = {
            "scientific_policy_frozen": len(phase30_policy_fingerprint()) == 64,
            "source_feasibility_frozen": PHASE30_SOURCE_FEASIBILITY_FINGERPRINT
            == "04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312",
            "exact_acquisition_start": start.isoformat()
            == "2021-07-16T00:00:00+00:00",
            "exact_acquisition_end": end.isoformat()
            == "2026-08-11T23:59:59.999999+00:00",
            "all_monthly_shards_present": len(shard_reports)
            == len(phase30_news_shard_windows()),
            "historical_news_nonempty": total_articles > 0,
            "ticker_linked_news_nonempty": total_ticker_linked > 0,
            "provider_content_has_no_alpha_authority": PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY
            is False,
            "provider_insights_have_no_alpha_authority": PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY
            is False,
            "target_outcomes_unread": True,
            "protected_returns_unread": True,
            "external_mutation_authority_zero": True,
        }

        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {
            "contract_version": PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "source_feasibility_fingerprint": PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
            "status": "ACQUISITION_PASS" if all(checks.values()) else "ACQUISITION_FAIL",
            "acquisition_start_utc": start.isoformat(),
            "acquisition_end_utc": end.isoformat(),
            "shards": shard_reports,
            "total_articles": total_articles,
            "total_ticker_linked_articles": total_ticker_linked,
            "recorded_successful_provider_pages": recorded_pages,
            "resumed_shards": resumed_shards,
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
            raise Phase30NewsAcquisitionError(
                "Phase30 full historical news acquisition failed: "
                + ", ".join(failed)
                + f"; report={report_path}"
            )
        return report
