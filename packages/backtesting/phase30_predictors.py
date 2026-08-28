from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_left
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.market_calendar import MarketCalendar, get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file
from packages.providers.massive.phase30 import parse_news_timestamp

from .phase30_acquisition import (
    PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
    phase30_news_shard_windows,
)
from .phase30_policy import (
    PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
    PHASE30_AUTOMATION_WRITES,
    PHASE30_BROKER_READS,
    PHASE30_BROKER_WRITES,
    PHASE30_DECISION_BUFFER_MINUTES,
    PHASE30_DEVELOPMENT_END,
    PHASE30_LIVE_WRITES,
    PHASE30_NEWS_BASELINE_SESSIONS,
    PHASE30_NEWS_WARMUP_START,
    PHASE30_ORDER_WRITES,
    PHASE30_OUTER_PURGE_DATES,
    PHASE30_PAPER_SUBMITS,
    PHASE30_PROTECTED_END,
    PHASE30_PROTECTED_START,
    PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_WRITES,
    PHASE30_RESEARCH_START,
    phase30_policy_fingerprint,
)


PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION = (
    "phase30-predictor-report-v1-metadata-only-news-shock-no-market-outcomes"
)
PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION = (
    "phase30-development-news-shock-v1-metadata-only-no-market-outcomes"
)
PHASE30_PROTECTED_NEWS_SHOCK_CONTRACT_VERSION = (
    "phase30-protected-news-shock-v1-metadata-only-no-market-outcomes"
)

PHASE30_PREDICTOR_FIELDS = (
    "contract_version",
    "phase30_policy_fingerprint",
    "ticker",
    "session_date",
    "session_close_utc",
    "decision_cutoff_utc",
    "current_unique_article_count",
    "previous_20_log1p_mean",
    "news_surprise",
)
PHASE30_FORBIDDEN_MARKET_FIELDS = (
    "future_date",
    "future_close",
    "forward_return",
    "directional_return",
    "d1_return_1",
)


class Phase30PredictorError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Phase30SessionPoint:
    index: int
    session_date: date
    regular_close_utc: datetime
    decision_cutoff_utc: datetime


def _read_json(path: Path, *, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise Phase30PredictorError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Phase30PredictorError(f"invalid {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase30PredictorError(f"{label} must be a JSON object: {path}")
    return payload


def phase30_session_grid(calendar: MarketCalendar) -> tuple[Phase30SessionPoint, ...]:
    start = date.fromisoformat(PHASE30_NEWS_WARMUP_START)
    protected_end = date.fromisoformat(PHASE30_PROTECTED_END)
    # News published after the final regular close can map to the next exchange
    # session. Extend the calendar only for deterministic event-time assignment;
    # no news is acquired beyond the frozen protected end.
    end = protected_end + timedelta(days=14)
    sessions = tuple(calendar.sessions_in_range(start, end))
    if not sessions or sessions[0] != start:
        raise Phase30PredictorError(
            "Phase30 warmup start is not the first exchange session in the frozen grid"
        )

    result: list[Phase30SessionPoint] = []
    buffer = timedelta(minutes=PHASE30_DECISION_BUFFER_MINUTES)
    for index, session_date in enumerate(sessions):
        _, regular_close = calendar.regular_open_close(session_date)
        if regular_close.tzinfo is None:
            raise Phase30PredictorError("exchange calendar returned timezone-naive close")
        regular_close = regular_close.astimezone(UTC)
        result.append(
            Phase30SessionPoint(
                index=index,
                session_date=session_date,
                regular_close_utc=regular_close,
                decision_cutoff_utc=regular_close - buffer,
            )
        )
    return tuple(result)


def effective_session_index(
    published_utc: datetime,
    decision_cutoffs: tuple[datetime, ...],
) -> int:
    if published_utc.tzinfo is None:
        raise Phase30PredictorError("news publication timestamp must be timezone-aware")
    index = bisect_left(decision_cutoffs, published_utc.astimezone(UTC))
    if index >= len(decision_cutoffs):
        raise Phase30PredictorError(
            "news publication does not map to an exchange session in the assignment grid"
        )
    return index


def build_news_shock_records(
    *,
    counts: dict[tuple[str, int], int],
    sessions: tuple[Phase30SessionPoint, ...],
    start_date: date,
    end_date: date,
    contract_version: str,
) -> list[dict[str, Any]]:
    if start_date > end_date:
        raise Phase30PredictorError("news-shock output date range is reversed")
    if PHASE30_NEWS_BASELINE_SESSIONS != 20:
        raise Phase30PredictorError("Phase30 news baseline drifted from frozen 20 sessions")

    policy_fingerprint = phase30_policy_fingerprint()
    records: list[dict[str, Any]] = []
    for (ticker, session_index), current_count in sorted(
        counts.items(),
        key=lambda value: (
            sessions[value[0][1]].session_date,
            value[0][0],
        ),
    ):
        point = sessions[session_index]
        if point.session_date < start_date or point.session_date > end_date:
            continue
        if current_count < 1:
            continue
        if session_index < PHASE30_NEWS_BASELINE_SESSIONS:
            raise Phase30PredictorError(
                f"insufficient frozen news warmup for {ticker!r} on {point.session_date}"
            )

        prior_counts = (
            counts.get((ticker, prior_index), 0)
            for prior_index in range(
                session_index - PHASE30_NEWS_BASELINE_SESSIONS,
                session_index,
            )
        )
        previous_mean = sum(math.log1p(value) for value in prior_counts) / float(
            PHASE30_NEWS_BASELINE_SESSIONS
        )
        surprise = math.log1p(current_count) - previous_mean
        record = {
            "contract_version": contract_version,
            "phase30_policy_fingerprint": policy_fingerprint,
            "ticker": ticker,
            "session_date": point.session_date.isoformat(),
            "session_close_utc": point.regular_close_utc.isoformat(),
            "decision_cutoff_utc": point.decision_cutoff_utc.isoformat(),
            "current_unique_article_count": int(current_count),
            "previous_20_log1p_mean": float(previous_mean),
            "news_surprise": float(surprise),
        }
        if tuple(record) != PHASE30_PREDICTOR_FIELDS:
            raise Phase30PredictorError("Phase30 predictor row field order drifted")
        if any(field in record for field in PHASE30_FORBIDDEN_MARKET_FIELDS):
            raise Phase30PredictorError("Phase30 predictor row contains a market outcome field")
        records.append(record)
    return records


def _write_immutable_parquet(
    settings: AtlasSettings,
    *,
    records: list[dict[str, Any]],
    target: Path,
) -> tuple[str, bool]:
    target.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame.from_records(records, columns=list(PHASE30_PREDICTOR_FIELDS))
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase30_predictor_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"""
            COPY (
                SELECT *
                FROM phase30_predictor_write
                ORDER BY session_date, ticker
            )
            TO {sql_string(temp)}
            (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
            """
        )
    finally:
        con.close()

    new_sha = sha256_file(temp)
    if target.is_file():
        existing_sha = sha256_file(target)
        if existing_sha != new_sha:
            temp.unlink(missing_ok=True)
            raise Phase30PredictorError(
                f"immutable Phase30 predictor evidence drifted: {target}"
            )
        temp.unlink(missing_ok=True)
        return existing_sha, True

    promote(temp, target)
    actual_sha = sha256_file(target)
    if actual_sha != new_sha:
        raise Phase30PredictorError(
            f"Phase30 predictor hash mismatch after immutable write: {target}"
        )
    return actual_sha, False


class Phase30NewsPredictorBuilder:
    """Build metadata-only Phase30 news-shock predictors from immutable local news.

    This stage has no market-data, Phase26, outcome, provider-network, broker, order,
    PAPER, or LIVE authority. It only turns the already-acquired immutable news
    evidence into the predictor specified by the frozen Phase30 scientific policy.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        provider_root = settings.resolved_path(settings.data.paths.provider)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        self.news_root = provider_root / "massive" / "phase30_news_history" / "v1"
        self.phase30_root = derived_root / "strategy_evaluation" / "phase30" / "v1"
        self.predictor_root = self.phase30_root / "predictors"

    def acquisition_report_path(self) -> Path:
        return self.phase30_root / "phase30_news_acquisition.json"

    def development_path(self) -> Path:
        return self.predictor_root / "development_news_shocks.parquet"

    def protected_path(self) -> Path:
        return self.predictor_root / "protected_news_shocks.parquet"

    def report_path(self) -> Path:
        return self.predictor_root / "predictor_report.json"

    def _validated_acquisition_shards(
        self,
    ) -> tuple[dict[str, Any], tuple[dict[str, Any], ...], str]:
        report = _read_json(
            self.acquisition_report_path(),
            label="Phase30 news acquisition report",
        )
        checks = {
            "contract": report.get("contract_version")
            == PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
            "policy": report.get("phase30_policy_fingerprint")
            == phase30_policy_fingerprint(),
            "pass": report.get("pass") is True,
            "status": report.get("status") == "ACQUISITION_PASS",
            "target_outcomes": int(report.get("target_outcome_rows_read", -1)) == 0,
            "protected_candidates": int(report.get("protected_candidate_rows_read", -1))
            == 0,
            "protected_returns": int(report.get("protected_return_rows_read", -1)) == 0,
            "provider_writes": int(report.get("provider_writes", -1)) == 0,
            "broker_reads": int(report.get("broker_reads", -1)) == 0,
            "broker_writes": int(report.get("broker_writes", -1)) == 0,
            "orders": int(report.get("order_writes", -1)) == 0,
            "paper": int(report.get("paper_submits", -1)) == 0,
            "live": int(report.get("live_writes", -1)) == 0,
            "automation": int(report.get("automation_writes", -1)) == 0,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase30PredictorError(
                "Phase30 acquisition lineage failed closed: " + ", ".join(failed)
            )

        raw_shards = report.get("shards")
        if not isinstance(raw_shards, list):
            raise Phase30PredictorError("Phase30 acquisition report has invalid shard list")
        shards: list[dict[str, Any]] = []
        expected_labels = tuple(window.label for window in phase30_news_shard_windows())
        actual_labels: list[str] = []
        lineage_hasher = hashlib.sha256()
        for raw in raw_shards:
            if not isinstance(raw, dict):
                raise Phase30PredictorError("Phase30 acquisition shard record is invalid")
            label = str(raw.get("label") or "")
            evidence_sha = str(raw.get("evidence_sha256") or "")
            if not label or len(evidence_sha) != 64:
                raise Phase30PredictorError("Phase30 acquisition shard lineage is incomplete")
            actual_labels.append(label)
            path = self.news_root / f"{label}.jsonl"
            if not path.is_file():
                raise Phase30PredictorError(f"missing immutable Phase30 news shard: {path}")
            actual_sha = sha256_file(path)
            if actual_sha != evidence_sha:
                raise Phase30PredictorError(
                    f"Phase30 news shard hash mismatch: {label}"
                )
            lineage_hasher.update(label.encode("utf-8"))
            lineage_hasher.update(b"\0")
            lineage_hasher.update(evidence_sha.encode("ascii"))
            lineage_hasher.update(b"\n")
            shards.append(raw)
        if tuple(actual_labels) != expected_labels:
            raise Phase30PredictorError(
                "Phase30 acquisition shard order/completeness drifted from frozen windows"
            )
        return report, tuple(shards), lineage_hasher.hexdigest()

    def _scan_authorized_news(
        self,
        *,
        shards: tuple[dict[str, Any], ...],
        sessions: tuple[Phase30SessionPoint, ...],
    ) -> tuple[dict[tuple[str, int], int], int, int]:
        if PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS != ("id", "published_utc", "tickers"):
            raise Phase30PredictorError("Phase30 authorized news fields drifted")
        if PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY is not False:
            raise Phase30PredictorError("provider content unexpectedly has Phase30 alpha authority")
        if PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY is not False:
            raise Phase30PredictorError("provider insights unexpectedly have Phase30 alpha authority")

        cutoffs = tuple(point.decision_cutoff_utc for point in sessions)
        counts: dict[tuple[str, int], int] = defaultdict(int)
        seen_article_ids: set[str] = set()
        article_count = 0
        ticker_link_count = 0

        for shard in shards:
            label = str(shard["label"])
            path = self.news_root / f"{label}.jsonl"
            try:
                handle = path.open("r", encoding="utf-8")
            except OSError as exc:
                raise Phase30PredictorError(f"cannot read Phase30 news shard: {path}") from exc
            with handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise Phase30PredictorError(
                            f"invalid JSON in Phase30 news shard {label}:{line_number}"
                        ) from exc
                    if not isinstance(raw, dict):
                        raise Phase30PredictorError(
                            f"non-object news row in {label}:{line_number}"
                        )

                    # Only these exact three provider fields are projected into the
                    # scientific feature path. Raw text/description/insights remain
                    # untouched provenance in the immutable acquisition evidence.
                    article_id = raw.get("id")
                    published_raw = raw.get("published_utc")
                    tickers_raw = raw.get("tickers")
                    if not isinstance(article_id, str) or not article_id.strip():
                        raise Phase30PredictorError(
                            f"invalid article id in {label}:{line_number}"
                        )
                    if article_id in seen_article_ids:
                        raise Phase30PredictorError(
                            f"duplicate article id in full Phase30 history: {article_id!r}"
                        )
                    seen_article_ids.add(article_id)

                    if not isinstance(tickers_raw, list):
                        raise Phase30PredictorError(
                            f"invalid ticker list for article {article_id!r}"
                        )
                    published = parse_news_timestamp(published_raw)
                    session_index = effective_session_index(published, cutoffs)

                    # Preserve exact provider-native ticker strings and case. Remove
                    # duplicates only within one article, without normalization.
                    exact_tickers: list[str] = []
                    seen_tickers: set[str] = set()
                    for ticker in tickers_raw:
                        if not isinstance(ticker, str) or not ticker.strip():
                            raise Phase30PredictorError(
                                f"invalid provider-native ticker for article {article_id!r}"
                            )
                        if ticker not in seen_tickers:
                            seen_tickers.add(ticker)
                            exact_tickers.append(ticker)

                    article_count += 1
                    ticker_link_count += len(exact_tickers)
                    for ticker in exact_tickers:
                        counts[(ticker, session_index)] += 1

        return dict(counts), article_count, ticker_link_count

    def run(self) -> dict[str, Any]:
        acquisition, shards, source_lineage_sha = self._validated_acquisition_shards()
        sessions = phase30_session_grid(self.calendar)
        counts, articles_scanned, ticker_links_scanned = self._scan_authorized_news(
            shards=shards,
            sessions=sessions,
        )

        development = build_news_shock_records(
            counts=counts,
            sessions=sessions,
            start_date=date.fromisoformat(PHASE30_RESEARCH_START),
            end_date=date.fromisoformat(PHASE30_DEVELOPMENT_END),
            contract_version=PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION,
        )
        protected = build_news_shock_records(
            counts=counts,
            sessions=sessions,
            start_date=date.fromisoformat(PHASE30_PROTECTED_START),
            end_date=date.fromisoformat(PHASE30_PROTECTED_END),
            contract_version=PHASE30_PROTECTED_NEWS_SHOCK_CONTRACT_VERSION,
        )

        development_dates = {row["session_date"] for row in development}
        protected_dates = {row["session_date"] for row in protected}
        purge_dates = set(PHASE30_OUTER_PURGE_DATES)
        if development_dates & purge_dates or protected_dates & purge_dates:
            raise Phase30PredictorError("Phase30 predictor outputs contain frozen outer-purge dates")
        if not development:
            raise Phase30PredictorError("Phase30 development news-shock predictor frame is empty")
        if not protected:
            raise Phase30PredictorError("Phase30 protected news-shock predictor frame is empty")

        development_sha, development_resumed = _write_immutable_parquet(
            self.settings,
            records=development,
            target=self.development_path(),
        )
        protected_sha, protected_resumed = _write_immutable_parquet(
            self.settings,
            records=protected,
            target=self.protected_path(),
        )

        development_tickers = len({str(row["ticker"]) for row in development})
        protected_tickers = len({str(row["ticker"]) for row in protected})
        checks = {
            "acquisition_passed": acquisition.get("pass") is True,
            "frozen_policy_exact": len(phase30_policy_fingerprint()) == 64,
            "metadata_only_alpha_fields": PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS
            == ("id", "published_utc", "tickers"),
            "provider_content_not_authorized": PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY is False,
            "provider_insights_not_authorized": PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY is False,
            "all_acquisition_shards_bound": len(shards) == len(phase30_news_shard_windows()),
            "articles_scanned_match_acquisition": articles_scanned
            == int(acquisition.get("total_articles", -1)),
            "development_nonempty": len(development) > 0,
            "protected_nonempty": len(protected) > 0,
            "development_has_no_market_fields": all(
                not any(field in row for field in PHASE30_FORBIDDEN_MARKET_FIELDS)
                for row in development
            ),
            "protected_has_no_market_fields": all(
                not any(field in row for field in PHASE30_FORBIDDEN_MARKET_FIELDS)
                for row in protected
            ),
            "outer_purge_absent": not (
                development_dates & purge_dates or protected_dates & purge_dates
            ),
            "target_outcomes_unread": True,
            "protected_returns_unread": True,
            "external_mutation_authority_zero": (
                PHASE30_PROVIDER_WRITES == 0
                and PHASE30_BROKER_READS == 0
                and PHASE30_BROKER_WRITES == 0
                and PHASE30_ORDER_WRITES == 0
                and PHASE30_PAPER_SUBMITS == 0
                and PHASE30_LIVE_WRITES == 0
                and PHASE30_AUTOMATION_WRITES == 0
            ),
        }

        report_path = self.report_path()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {
            "contract_version": PHASE30_PREDICTOR_REPORT_CONTRACT_VERSION,
            "phase30_policy_fingerprint": phase30_policy_fingerprint(),
            "source_acquisition_contract_version": PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
            "source_acquisition_report_path": str(self.acquisition_report_path().resolve()),
            "source_news_shards": len(shards),
            "source_news_lineage_sha256": source_lineage_sha,
            "articles_scanned": articles_scanned,
            "ticker_links_scanned": ticker_links_scanned,
            "development_rows": len(development),
            "development_tickers": development_tickers,
            "development_path": str(self.development_path().resolve()),
            "development_sha256": development_sha,
            "development_resumed_immutable": development_resumed,
            "protected_rows": len(protected),
            "protected_tickers": protected_tickers,
            "protected_path": str(self.protected_path().resolve()),
            "protected_sha256": protected_sha,
            "protected_resumed_immutable": protected_resumed,
            "provider_reads": 0,
            "provider_writes": 0,
            "target_outcome_rows_read": 0,
            "protected_candidate_rows_read": 0,
            "protected_return_rows_read": 0,
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
            raise Phase30PredictorError(
                "Phase30 predictor-only construction failed: " + ", ".join(failed)
            )
        return report
