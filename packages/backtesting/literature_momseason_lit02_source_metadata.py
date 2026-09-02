from __future__ import annotations

import gzip
import hashlib
import html
import json
import re
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.providers.massive.reference_data import MassiveReferenceProvider
from packages.providers.sec_edgar import (
    SECEDGARClient,
    SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
    sec_company_submissions_url,
    sec_submission_shard_url,
)
from packages.providers.sec_edgar_archive import (
    SECEDGARArchiveClient,
    SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES,
    sec_archive_submission_url,
)

from .literature_momseason_lit01_closeout import MomSeasonLIT01Closeout
from .literature_momseason_lit02_source_feasibility import (
    LIT02_SOURCE_FEASIBILITY_PLAN_FILE,
    LIT02_SOURCE_FEASIBILITY_PLAN_STATUS,
    LIT02_SOURCE_FEASIBILITY_REPORT_FILE,
    LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT,
)
from .literature_momseason_lit02_source_policy import (
    LIT02_REQUIRED_SOURCE_COVERAGE,
    LIT02_SOURCE_POLICY_STATUS,
)
from .literature_momseason_source import (
    MOMSEASON_SOURCE_ROOT_RELATIVE,
    canonical_json,
)


LIT02_SOURCE_METADATA_CONTRACT = (
    "lit02-source-metadata-classification-v1-frozen-plan-massive-figi-sec-8k-no-prices"
)
LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT = (
    "4768ac204a68bbc7d89fa64c96574934d1e4149169cd6c222ef16be5bc1367ae"
)
LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT = (
    "c9200212a67171ee7c712a64224263241d622d2e8fe494ce0bc13843a8052880"
)
LIT02_ACCEPTED_FEASIBILITY_REPORT_FINGERPRINT = (
    "019f97866fe6e47c0b3f8eb1ce2b508ac6315d919d807aeeaa9d2e729fcc0255"
)

LIT02_SOURCE_METADATA_STORAGE_ROOT = "m"
LIT02_SOURCE_METADATA_IDENTITY_CACHE = "i.json"
LIT02_SOURCE_METADATA_REPORT = "r.json"

LIT02_SOURCE_METADATA_READY = "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_READY"
LIT02_SOURCE_METADATA_INCOMPLETE = "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_INCOMPLETE"

LIT02_SEC_LOOKBACK_DAYS = 62
LIT02_SEC_FORWARD_DAYS = 10
LIT02_SEC_MAX_CANDIDATE_FILINGS = 24
LIT02_SEC_ALLOWED_FORMS = frozenset({"8-K", "8-K/A"})
LIT02_SEC_RELEVANT_ITEMS = frozenset({"2.01", "3.01", "5.03", "8.01"})
LIT02_IDENTITY_QUALITIES = frozenset({"strong", "medium"})
LIT02_IDENTITY_NEARBY_DAYS = 124

_MONTH_NAMES = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
_MONTH_TOKEN = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s+\d{4}"
)
_DATE_TOKEN = rf"(?:{_MONTH_TOKEN}|\d{{4}}-\d{{2}}-\d{{2}})"

_TICKER_CHANGE_RE = re.compile(
    r"(?is:\b(?:trading|ticker)\s+symbol\b.{0,500}?"
    r"\b(?:will\s+change|changed|changes|change)\s+from\s+"
    r'["\'“”]?(?P<old>[A-Za-z][A-Za-z0-9.-]{0,12})["\'“”]?\s+'
    r'\bto\b\s+["\'“”]?(?P<new>[A-Za-z][A-Za-z0-9.-]{0,12})["\'“”]?)'
)

_CASH_PATTERNS = (
    re.compile(
        r"(?is:\b(?:each|every)\b.{0,160}?\bshare\b.{0,320}?"
        r"\b(?:converted\s+into|right\s+to\s+receive)\b.{0,180}?"
        r"\$\s*(?P<value>\d+(?:\.\d+)?)\b.{0,80}?\b(?:cash|per\s+share)\b)"
    ),
    re.compile(
        r"(?is:\$\s*(?P<value>\d+(?:\.\d+)?)\s*(?:in\s+cash\s*)?"
        r"\b(?:per\s+share|for\s+each\s+share)\b)"
    ),
    re.compile(
        r"(?is:\b(?:cash|merger)\s+consideration\b.{0,140}?"
        r"\$\s*(?P<value>\d+(?:\.\d+)?)\s*(?:in\s+cash\s*)?\bper\s+share\b)"
    ),
)
_SHARE_RATIO_PATTERNS = (
    re.compile(
        r"(?is:\b(?:each|every)\b.{0,160}?\bshare\b.{0,320}?"
        r"\b(?:converted\s+into|right\s+to\s+receive|exchangeable\s+for)\b.{0,180}?"
        r"(?P<value>\d+(?:\.\d+)?)\s+(?:shares?|common\s+shares?|ordinary\s+shares?)\b)"
    ),
    re.compile(
        r"(?is:\bexchange\s+ratio\b.{0,80}?\b(?:of|equal\s+to)\b\s*"
        r"(?P<value>\d+(?:\.\d+)?)\b)"
    ),
)
_DISTRIBUTION_RE = re.compile(
    r"(?is:\b(?:liquidating|liquidation|terminal|final)\s+distribution\b.{0,180}?"
    r"\$\s*(?P<value>\d+(?:\.\d+)?)\s*(?:in\s+cash\s*)?\bper\s+share\b)"
)
_SUCCESSOR_TICKER_PATTERNS = (
    re.compile(
        r"(?is:\b(?:combined\s+company|surviving\s+corporation|successor|parent)\b.{0,500}?"
        r"\b(?:trade|trading|traded|listed)\b.{0,140}?"
        r'\b(?:symbol|ticker)\b\s*(?:of|:)?\s*["\'“”]?'
        r'(?P<ticker>(?-i:[A-Z][A-Z0-9.-]{0,9}))["\'“”]?)'
    ),
    re.compile(
        r"(?is:\b(?:common\s+stock|common\s+shares)\b.{0,260}?"
        r"\b(?:trade|trading|traded|listed)\b.{0,140}?"
        r'\bunder\b.{0,60}?\b(?:symbol|ticker)\b\s*["\'“”]?'
        r'(?P<ticker>(?-i:[A-Z][A-Z0-9.-]{0,9}))["\'“”]?)'
    ),
)


def _fingerprint(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _plain_sec_text(text: str) -> str:
    value = html.unescape(text)
    value = re.sub(r"(?is)<script\b.*?</script>", " ", value)
    value = re.sub(r"(?is)<style\b.*?</style>", " ", value)
    value = re.sub(r"(?is)<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _parse_date_token(value: str) -> date | None:
    text = str(value or "").strip().strip(",")
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    match = re.fullmatch(
        r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    try:
        return date(
            int(match.group("year")),
            _MONTH_NAMES[match.group("month").lower()],
            int(match.group("day")),
        )
    except ValueError:
        return None


def _effective_dates_in_context(context: str) -> set[date]:
    patterns = (
        re.compile(
            rf"(?is:\b(?:effective|commencing|beginning)(?:\s+(?:on|as\s+of))?\s+"
            rf"(?P<date>{_DATE_TOKEN}))"
        ),
        re.compile(
            rf"(?is:\b(?:became\s+effective|becomes\s+effective)\b.{{0,80}}?"
            rf"\b(?:on|as\s+of)\s+(?P<date>{_DATE_TOKEN}))"
        ),
    )
    values: set[date] = set()
    for pattern in patterns:
        for match in pattern.finditer(context):
            parsed = _parse_date_token(match.group("date"))
            if parsed is not None:
                values.add(parsed)
    return values


def parse_explicit_sec_ticker_change(
    text: str,
    *,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    plain = _plain_sec_text(text)
    candidates: dict[tuple[str, str, date], str] = {}
    for match in _TICKER_CHANGE_RE.finditer(plain):
        old = match.group("old").strip()
        new = match.group("new").strip()
        if old != historical_ticker or old == new:
            continue
        start = max(0, match.start() - 500)
        end = min(len(plain), match.end() + 500)
        context = plain[start:end]
        for effective_date in _effective_dates_in_context(context):
            if effective_date <= endpoint_session:
                candidates[(old, new, effective_date)] = context[:1800]
    if not candidates:
        return None
    if len(candidates) != 1:
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_EXPLICIT_TICKER_CHANGES",
            "candidates": [
                {
                    "old_ticker": old,
                    "new_ticker": new,
                    "effective_date": effective.isoformat(),
                }
                for old, new, effective in sorted(candidates)
            ],
        }
    (old, new, effective), excerpt = next(iter(candidates.items()))
    return {
        "status": "READY",
        "path_id": "TICKER_CONTINUITY",
        "old_ticker": old,
        "new_ticker": new,
        "effective_date": effective.isoformat(),
        "matched_excerpt": excerpt,
        "evidence_rule": "EXPLICIT_SEC_TICKER_CHANGE_WITH_EFFECTIVE_DATE",
    }


def _terminal_event_dates(plain: str, endpoint_session: date) -> set[date]:
    patterns = (
        re.compile(
            rf"(?is:\bOn\s+(?P<date>{_DATE_TOKEN})\s*,.{{0,700}}?"
            rf"\b(?:completed|consummated|closed|merged\s+with\s+and\s+into)\b.{{0,260}}?"
            rf"\b(?:merger|acquisition|transaction|company|corporation)\b)"
        ),
        re.compile(
            rf"(?is:\b(?:merger|acquisition|transaction)\b.{{0,280}}?"
            rf"\b(?:was\s+)?(?:completed|consummated|closed|became\s+effective)\b.{{0,160}}?"
            rf"\b(?:on|as\s+of)\s+(?P<date>{_DATE_TOKEN}))"
        ),
        re.compile(
            rf"(?is:\b(?:completed|consummated|closed)\b.{{0,220}}?"
            rf"\b(?:merger|acquisition|transaction)\b.{{0,160}}?"
            rf"\b(?:on|as\s+of)\s+(?P<date>{_DATE_TOKEN}))"
        ),
        re.compile(
            rf"(?is:\b(?:effective\s+time|merger)\b.{{0,220}}?"
            rf"\b(?:occurred|became\s+effective)\b.{{0,120}}?"
            rf"\b(?:on|as\s+of)\s+(?P<date>{_DATE_TOKEN}))"
        ),
    )
    values: set[date] = set()
    for pattern in patterns:
        for match in pattern.finditer(plain):
            parsed = _parse_date_token(match.group("date"))
            if parsed is not None and parsed <= endpoint_session:
                values.add(parsed)
    return values


def _unique_float_matches(
    plain: str,
    patterns: tuple[re.Pattern[str], ...],
) -> set[float]:
    values: set[float] = set()
    for pattern in patterns:
        for match in pattern.finditer(plain):
            try:
                value = float(match.group("value"))
            except (TypeError, ValueError):
                continue
            if value > 0.0:
                values.add(value)
    return values


def _successor_tickers(plain: str, historical_ticker: str) -> set[str]:
    values: set[str] = set()
    for pattern in _SUCCESSOR_TICKER_PATTERNS:
        for match in pattern.finditer(plain):
            ticker = match.group("ticker").strip()
            if ticker and ticker != historical_ticker:
                values.add(ticker)
    return values


def parse_sec_terminal_transaction(
    text: str,
    *,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    plain = _plain_sec_text(text)
    event_dates = _terminal_event_dates(plain, endpoint_session)
    distribution_matches = {
        float(match.group("value"))
        for match in _DISTRIBUTION_RE.finditer(plain)
        if float(match.group("value")) > 0.0
    }
    cash_values = _unique_float_matches(plain, _CASH_PATTERNS)
    share_ratios = _unique_float_matches(plain, _SHARE_RATIO_PATTERNS)
    successor_tickers = _successor_tickers(plain, historical_ticker)

    if distribution_matches:
        if len(distribution_matches) != 1:
            return {
                "status": "CONFLICT",
                "reason": "MULTIPLE_TERMINAL_DISTRIBUTION_VALUES",
                "values": sorted(distribution_matches),
            }
        if len(event_dates) != 1:
            return {
                "status": "INCOMPLETE",
                "reason": "TERMINAL_DISTRIBUTION_EFFECTIVE_DATE_UNRESOLVED",
                "values": sorted(distribution_matches),
                "event_dates": sorted(item.isoformat() for item in event_dates),
            }
        return {
            "status": "READY",
            "path_id": "TERMINAL_DISTRIBUTION",
            "effective_date": next(iter(event_dates)).isoformat(),
            "distribution_per_share": next(iter(distribution_matches)),
            "evidence_rule": "EXPLICIT_SEC_TERMINAL_DISTRIBUTION_PER_SHARE",
        }

    if not cash_values and not share_ratios:
        return None
    if len(event_dates) != 1:
        return {
            "status": "INCOMPLETE",
            "reason": "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED",
            "cash_values": sorted(cash_values),
            "share_ratios": sorted(share_ratios),
            "event_dates": sorted(item.isoformat() for item in event_dates),
        }
    if len(cash_values) > 1:
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_TERMINAL_CASH_VALUES",
            "cash_values": sorted(cash_values),
        }
    if len(share_ratios) > 1:
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_TERMINAL_SHARE_RATIOS",
            "share_ratios": sorted(share_ratios),
        }

    effective_date = next(iter(event_dates)).isoformat()
    if cash_values and not share_ratios:
        return {
            "status": "READY",
            "path_id": "TERMINAL_CASH",
            "effective_date": effective_date,
            "cash_per_share": next(iter(cash_values)),
            "evidence_rule": "EXPLICIT_SEC_EXECUTED_CASH_CONSIDERATION",
        }

    successor_ticker = next(iter(successor_tickers)) if len(successor_tickers) == 1 else None
    if share_ratios and not cash_values:
        return {
            "status": "READY" if successor_ticker else "INCOMPLETE",
            "path_id": "TERMINAL_STOCK",
            "effective_date": effective_date,
            "share_exchange_ratio": next(iter(share_ratios)),
            "successor_ticker": successor_ticker,
            "reason": None if successor_ticker else "SUCCESSOR_TICKER_IDENTITY_REQUIRED",
            "evidence_rule": "EXPLICIT_SEC_EXECUTED_STOCK_CONSIDERATION",
        }
    return {
        "status": "READY" if successor_ticker else "INCOMPLETE",
        "path_id": "TERMINAL_MIXED",
        "effective_date": effective_date,
        "cash_per_share": next(iter(cash_values)),
        "share_exchange_ratio": next(iter(share_ratios)),
        "successor_ticker": successor_ticker,
        "reason": None if successor_ticker else "SUCCESSOR_TICKER_IDENTITY_REQUIRED",
        "evidence_rule": "EXPLICIT_SEC_EXECUTED_MIXED_CONSIDERATION",
    }


def classify_massive_ticker_events(
    raw_events: list[dict[str, object]],
    *,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    by_date: dict[date, set[str]] = defaultdict(set)
    for raw in raw_events:
        if str(raw.get("type") or "").strip().lower() != "ticker_change":
            continue
        change = raw.get("ticker_change")
        if not isinstance(change, Mapping):
            continue
        ticker = str(change.get("ticker") or "").strip()
        if not ticker:
            continue
        try:
            event_date = date.fromisoformat(str(raw.get("date") or ""))
        except ValueError:
            continue
        by_date[event_date].add(ticker)

    for event_date, tickers in by_date.items():
        if len(tickers) > 1:
            return {
                "status": "CONFLICT",
                "reason": "MASSIVE_TICKER_EVENT_DATE_CONFLICT",
                "event_date": event_date.isoformat(),
                "tickers": sorted(tickers),
            }

    eligible = [event_date for event_date in by_date if event_date <= endpoint_session]
    if not eligible:
        return None
    latest = max(eligible)
    resolved = next(iter(by_date[latest]))
    if resolved == historical_ticker:
        return None
    return {
        "status": "READY",
        "path_id": "TICKER_CONTINUITY",
        "old_ticker": historical_ticker,
        "new_ticker": resolved,
        "effective_date": latest.isoformat(),
        "evidence_rule": "MASSIVE_COMPOSITE_FIGI_TICKER_EVENT",
    }


def _normalize_cik(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    return str(int(text)).zfill(10)


def select_identity_authorities(
    rows: list[dict[str, object]],
    *,
    endpoint_session: date,
    instrument_id: str,
) -> dict[str, object]:
    safe_rows = [
        row
        for row in rows
        if str(row.get("identity_quality") or "").strip().lower()
        in LIT02_IDENTITY_QUALITIES
    ]
    nearby = []
    for row in safe_rows:
        try:
            snapshot_date = date.fromisoformat(str(row.get("snapshot_date") or ""))
        except ValueError:
            continue
        if abs((snapshot_date - endpoint_session).days) <= LIT02_IDENTITY_NEARBY_DAYS:
            nearby.append(row)
    relevant = nearby or safe_rows
    aliases = sorted(
        {
            str(row.get("ticker") or "").strip()
            for row in relevant
            if str(row.get("ticker") or "").strip()
        }
    )
    figis = sorted(
        {
            str(row.get("composite_figi") or "").strip().upper()
            for row in safe_rows
            if str(row.get("composite_figi") or "").strip()
        }
    )
    ciks = sorted(
        {
            value
            for value in (_normalize_cik(row.get("cik")) for row in safe_rows)
            if value is not None
        }
    )
    conflicts: list[str] = []
    if len(figis) > 1:
        conflicts.append("MULTIPLE_COMPOSITE_FIGIS")
    if len(ciks) > 1:
        conflicts.append("MULTIPLE_CIKS")
    return {
        "instrument_id": instrument_id,
        "aliases": aliases,
        "composite_figi": figis[0] if len(figis) == 1 else None,
        "cik": ciks[0] if len(ciks) == 1 else None,
        "identity_status": "CONFLICT" if conflicts else "READY",
        "identity_conflicts": conflicts,
        "safe_identity_rows": len(safe_rows),
        "nearby_identity_rows": len(nearby),
    }


def _columnar_rows(block: object) -> list[dict[str, object]]:
    if not isinstance(block, Mapping):
        return []
    accessions = block.get("accessionNumber")
    if not isinstance(accessions, list):
        return []
    fields = ("accessionNumber", "filingDate", "form", "items", "primaryDocument")
    rows: list[dict[str, object]] = []
    for index in range(len(accessions)):
        row: dict[str, object] = {}
        for field in fields:
            values = block.get(field)
            row[field] = values[index] if isinstance(values, list) and index < len(values) else ""
        rows.append(row)
    return rows


def _submission_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    rows = _columnar_rows(payload)
    filings = payload.get("filings")
    if isinstance(filings, Mapping):
        rows.extend(_columnar_rows(filings.get("recent")))
    return rows


def _declared_shard_urls(
    payload: Mapping[str, object],
    *,
    start_date: date,
    end_date: date,
) -> list[str]:
    filings = payload.get("filings")
    files = filings.get("files") if isinstance(filings, Mapping) else None
    candidates: list[tuple[date, date, str]] = []
    if isinstance(files, list):
        for item in files:
            if not isinstance(item, Mapping):
                continue
            try:
                filing_from = date.fromisoformat(str(item.get("filingFrom") or ""))
                filing_to = date.fromisoformat(str(item.get("filingTo") or ""))
            except ValueError:
                continue
            if filing_from > filing_to or filing_to < start_date or filing_from > end_date:
                continue
            candidates.append(
                (filing_from, filing_to, sec_submission_shard_url(item.get("name")))
            )
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    if len(candidates) > SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP:
        raise RuntimeError(
            "LIT-02 SEC source lookup exceeded bounded declared-shard count: "
            f"{len(candidates)} > {SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP}"
        )
    return [item[2] for item in candidates]


def _filtered_sec_rows(
    rows: list[dict[str, object]],
    *,
    start_date: date,
    end_date: date,
) -> list[dict[str, object]]:
    unique: dict[str, dict[str, object]] = {}
    for row in rows:
        accession = str(row.get("accessionNumber") or "").strip()
        form = str(row.get("form") or "").strip()
        filing_text = str(row.get("filingDate") or "").strip()
        if not accession or form not in LIT02_SEC_ALLOWED_FORMS:
            continue
        try:
            filing_date = date.fromisoformat(filing_text)
        except ValueError:
            continue
        if not (start_date <= filing_date <= end_date):
            continue
        items = {
            item.strip()
            for item in re.split(r"[,;]", str(row.get("items") or ""))
            if item.strip()
        }
        if items and not (items & LIT02_SEC_RELEVANT_ITEMS):
            continue
        unique[accession] = {
            "accession_number": accession,
            "filing_date": filing_date.isoformat(),
            "form": form,
            "items": sorted(items),
            "primary_document": str(row.get("primaryDocument") or "").strip() or None,
        }
    ordered = sorted(
        unique.values(),
        key=lambda item: (str(item["filing_date"]), str(item["accession_number"])),
    )
    if len(ordered) > LIT02_SEC_MAX_CANDIDATE_FILINGS:
        raise RuntimeError(
            "LIT-02 SEC source lookup exceeded bounded candidate filing count: "
            f"{len(ordered)} > {LIT02_SEC_MAX_CANDIDATE_FILINGS}"
        )
    return ordered


def build_source_coverage_report(
    *,
    case_results: list[dict[str, object]],
    provider_reads: int,
    massive_provider_reads: int,
    sec_provider_reads: int,
    cached_cases: int,
    identity_evidence_fingerprint: str,
) -> dict[str, object]:
    total = len(case_results)
    resolved = sum(
        1
        for row in case_results
        if str(row.get("resolution_status") or "") == "RESOLVED"
    )
    path_counts = Counter(
        str(row.get("path_id") or "SOURCE_UNRESOLVED") for row in case_results
    )
    unresolved_reasons = Counter()
    for row in case_results:
        if str(row.get("resolution_status") or "") == "RESOLVED":
            continue
        reasons = row.get("unresolved_reasons") or []
        if isinstance(reasons, list) and reasons:
            for reason in reasons:
                unresolved_reasons[str(reason)] += 1
        else:
            unresolved_reasons["UNSPECIFIED"] += 1

    coverage = (resolved / total) if total else 0.0
    ready = total > 0 and coverage >= LIT02_REQUIRED_SOURCE_COVERAGE
    report: dict[str, object] = {
        "status": (
            LIT02_SOURCE_METADATA_READY if ready else LIT02_SOURCE_METADATA_INCOMPLETE
        ),
        "contract_version": LIT02_SOURCE_METADATA_CONTRACT,
        "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
        "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
        "required_source_coverage": LIT02_REQUIRED_SOURCE_COVERAGE,
        "feasibility_cases": total,
        "resolved_cases": resolved,
        "unresolved_cases": total - resolved,
        "source_coverage": coverage,
        "path_counts": dict(sorted(path_counts.items())),
        "unresolved_reason_counts": dict(sorted(unresolved_reasons.items())),
        "classification_fingerprint": _fingerprint(
            sorted(
                (
                    {
                        "case_id": row.get("case_id"),
                        "resolution_status": row.get("resolution_status"),
                        "path_id": row.get("path_id"),
                        "classification": row.get("classification"),
                        "unresolved_reasons": row.get("unresolved_reasons"),
                    }
                    for row in case_results
                ),
                key=lambda item: str(item.get("case_id") or ""),
            )
        ),
        "identity_evidence_fingerprint": identity_evidence_fingerprint,
        "source_metadata_provider_reads": int(provider_reads),
        "massive_source_metadata_reads": int(massive_provider_reads),
        "sec_source_metadata_reads": int(sec_provider_reads),
        "cached_case_manifests_reused": int(cached_cases),
        "economic_outcome_values_read": 0,
        "new_price_or_return_provider_reads": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "phase33_signal_to_trade_authority": False,
        "production_authority": False,
        "lit02_economic_design_unblocked": ready,
        "fresh_confirmatory_reuse_of_lit01_2021_09_to_2026_04": False,
        "next_action": (
            "Freeze a new LIT-02 economic-development design on fresh/non-reused evidence."
            if ready
            else "Diagnose SOURCE_UNRESOLVED cases by source-only mechanism; do not read price/return outcomes."
        ),
    }
    report["report_fingerprint"] = _fingerprint(
        {
            key: value
            for key, value in report.items()
            if key
            not in {
                "source_metadata_provider_reads",
                "massive_source_metadata_reads",
                "sec_source_metadata_reads",
                "cached_case_manifests_reused",
            }
        }
    )
    return report


class MomSeasonLIT02SourceMetadata:
    """Acquire and classify source-only evidence for the frozen 199-case LIT-02 plan."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        massive: MassiveReferenceProvider | None = None,
        sec_submissions: SECEDGARClient | None = None,
        sec_archive: SECEDGARArchiveClient | None = None,
    ) -> None:
        self.settings = settings
        self.lit01 = MomSeasonLIT01Closeout(settings)
        self.feasibility_root = self.lit01.root / LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT
        self.root = self.feasibility_root / LIT02_SOURCE_METADATA_STORAGE_ROOT
        derived = settings.resolved_path(settings.data.paths.derived)
        self.reference_root = derived / MOMSEASON_SOURCE_ROOT_RELATIVE / "reference"

        self.massive = massive or MassiveReferenceProvider(settings)
        self.sec_submissions = sec_submissions
        self.sec_archive = sec_archive

        self._massive_event_cache: dict[str, list[dict[str, object]]] = {}
        self._massive_overview_cache: dict[tuple[str, date], dict[str, object] | None] = {}
        self._sec_json_cache: dict[str, tuple[dict[str, object], str]] = {}
        self._sec_submission_cache: dict[str, object] = {}
        self._massive_reads = 0
        self._sec_reads = 0

    @property
    def provider_reads(self) -> int:
        return self._massive_reads + self._sec_reads

    def plan_path(self) -> Path:
        return self.feasibility_root / LIT02_SOURCE_FEASIBILITY_PLAN_FILE

    def feasibility_report_path(self) -> Path:
        return self.feasibility_root / LIT02_SOURCE_FEASIBILITY_REPORT_FILE

    def identity_cache_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_IDENTITY_CACHE

    def report_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_REPORT

    def case_path(self, case_id: str) -> Path:
        key = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
        return self.root / f"{key}.json"

    def _load_and_require_plan(
        self,
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        if not self.plan_path().is_file() or not self.feasibility_report_path().is_file():
            raise RuntimeError("LIT-02 accepted source-feasibility plan/report are required")
        payload = json.loads(self.plan_path().read_text(encoding="utf-8"))
        report = json.loads(self.feasibility_report_path().read_text(encoding="utf-8"))
        cases = payload.get("cases")
        if not isinstance(cases, list):
            raise RuntimeError("LIT-02 feasibility plan cases are missing")
        if report.get("status") != LIT02_SOURCE_FEASIBILITY_PLAN_STATUS:
            raise RuntimeError("LIT-02 feasibility plan status mismatch")
        if report.get("source_contract_status") != LIT02_SOURCE_POLICY_STATUS:
            raise RuntimeError("LIT-02 source policy status mismatch")
        if (
            str(report.get("source_policy_fingerprint") or "")
            != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
        ):
            raise RuntimeError("LIT-02 accepted source policy fingerprint mismatch")
        if (
            str(report.get("feasibility_plan_fingerprint") or "")
            != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
        ):
            raise RuntimeError("LIT-02 accepted feasibility plan fingerprint mismatch")
        if (
            str(report.get("report_fingerprint") or "")
            != LIT02_ACCEPTED_FEASIBILITY_REPORT_FINGERPRINT
        ):
            raise RuntimeError("LIT-02 accepted feasibility report fingerprint mismatch")
        if int(report.get("feasibility_cases") or 0) != 199 or len(cases) != 199:
            raise RuntimeError("LIT-02 accepted feasibility population is not 199 cases")
        if int(report.get("economic_outcome_values_read") or 0) != 0:
            raise RuntimeError("LIT-02 feasibility freeze opened economic outcomes")
        if int(report.get("new_price_or_return_provider_reads") or 0) != 0:
            raise RuntimeError("LIT-02 feasibility freeze opened price/return provider data")
        if int(report.get("protected_return_rows_read") or 0) != 0:
            raise RuntimeError("LIT-02 feasibility freeze opened protected outcomes")
        if bool(report.get("protected_holdout_consumed")):
            raise RuntimeError("LIT-02 feasibility freeze consumed protected holdout")
        return [dict(item) for item in cases if isinstance(item, Mapping)], report

    def _identity_rows_from_cache(
        self,
        cases: list[dict[str, object]],
    ) -> tuple[dict[str, list[dict[str, object]]], str, bool]:
        path = self.identity_cache_path()
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if (
                payload.get("contract_version") == LIT02_SOURCE_METADATA_CONTRACT
                and payload.get("feasibility_plan_fingerprint")
                == LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
                and isinstance(payload.get("rows_by_instrument"), dict)
                and str(payload.get("identity_evidence_fingerprint") or "")
            ):
                rows_by_instrument = {
                    str(key): [
                        dict(row) for row in value if isinstance(row, Mapping)
                    ]
                    for key, value in payload["rows_by_instrument"].items()
                    if isinstance(value, list)
                }
                return (
                    rows_by_instrument,
                    str(payload["identity_evidence_fingerprint"]),
                    True,
                )

        needed_ids = sorted(
            {
                str(instrument_id)
                for case in cases
                for instrument_id in (case.get("instrument_ids") or [])
                if str(instrument_id)
            }
        )
        needed = set(needed_ids)
        rows_by_instrument: dict[str, list[dict[str, object]]] = {
            instrument_id: [] for instrument_id in needed_ids
        }
        files = sorted(self.reference_root.glob("date=*/active_stock_snapshot.jsonl.gz"))
        if not files:
            raise RuntimeError(
                f"LIT-02 source identity snapshots are missing: {self.reference_root}"
            )

        started = time.monotonic()
        for index, path_item in enumerate(files, start=1):
            date_text = path_item.parent.name.removeprefix("date=")
            with gzip.open(path_item, "rt", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if not isinstance(row, Mapping):
                        continue
                    instrument_id = str(row.get("instrument_id") or "")
                    if instrument_id not in needed:
                        continue
                    rows_by_instrument[instrument_id].append(
                        {
                            "snapshot_date": date_text,
                            "instrument_id": instrument_id,
                            "identity_quality": str(row.get("identity_quality") or ""),
                            "ticker": str(row.get("ticker") or ""),
                            "composite_figi": row.get("composite_figi"),
                            "cik": row.get("cik"),
                            "primary_exchange": row.get("primary_exchange"),
                            "security_type": row.get("security_type"),
                            "active": bool(row.get("active", True)),
                        }
                    )
            if index == 1 or index == len(files) or index % 10 == 0:
                elapsed = time.monotonic() - started
                print(
                    f"[LIT-02][IDENTITY] snapshots {index}/{len(files)} "
                    f"{(index / len(files)) * 100.0:.1f}% | elapsed={elapsed:.1f}s "
                    f"| file={path_item.parent.name}"
                )

        normalized = {
            instrument_id: sorted(
                rows,
                key=lambda row: (
                    str(row.get("snapshot_date") or ""),
                    str(row.get("ticker") or ""),
                ),
            )
            for instrument_id, rows in rows_by_instrument.items()
        }
        evidence_fingerprint = _fingerprint(normalized)
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            path,
            canonical_json(
                {
                    "contract_version": LIT02_SOURCE_METADATA_CONTRACT,
                    "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
                    "instrument_ids": needed_ids,
                    "rows_by_instrument": normalized,
                    "identity_evidence_fingerprint": evidence_fingerprint,
                    "provider_reads_performed": 0,
                    "economic_outcome_values_read": 0,
                    "protected_return_rows_read": 0,
                }
            )
            + "\n",
        )
        return normalized, evidence_fingerprint, False

    def _massive_ticker_events(
        self,
        composite_figi: str,
    ) -> list[dict[str, object]]:
        cached = self._massive_event_cache.get(composite_figi)
        if cached is not None:
            return cached
        self._massive_reads += 1
        raw = self.massive.ticker_events(composite_figi)
        rows = [dict(item) for item in raw if isinstance(item, Mapping)]
        self._massive_event_cache[composite_figi] = rows
        return rows

    def _massive_overview(
        self,
        ticker: str,
        endpoint_session: date,
    ) -> dict[str, object] | None:
        key = (ticker, endpoint_session)
        if key in self._massive_overview_cache:
            return self._massive_overview_cache[key]
        self._massive_reads += 1
        try:
            value = dict(self.massive.ticker_overview(ticker, endpoint_session))
        except ProviderError as exc:
            if "404" in str(exc):
                value = None
            else:
                raise
        self._massive_overview_cache[key] = value
        return value

    def _ensure_sec_clients(
        self,
    ) -> tuple[SECEDGARClient, SECEDGARArchiveClient]:
        if self.sec_submissions is None:
            self.sec_submissions = SECEDGARClient()
        if self.sec_archive is None:
            self.sec_archive = SECEDGARArchiveClient(
                submission_max_response_bytes=SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
            )
        if (
            self.sec_archive.submission_max_response_bytes
            != SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES
        ):
            raise RuntimeError("LIT-02 SEC scientific archive bound changed")
        return self.sec_submissions, self.sec_archive

    def _sec_get_json(
        self,
        url: str,
    ) -> tuple[dict[str, object], str]:
        cached = self._sec_json_cache.get(url)
        if cached is not None:
            return cached
        submissions, _archive = self._ensure_sec_clients()
        self._sec_reads += 1
        payload, text = submissions.get_json(url)
        value = (dict(payload), text)
        self._sec_json_cache[url] = value
        return value

    def _sec_get_submission(self, filename: str):
        url = sec_archive_submission_url(filename)
        cached = self._sec_submission_cache.get(url)
        if cached is not None:
            return cached
        _submissions, archive = self._ensure_sec_clients()
        self._sec_reads += 1
        document = archive.complete_submission(filename=filename)
        self._sec_submission_cache[url] = document
        return document

    def _sec_candidate_filings(
        self,
        *,
        cik: str,
        endpoint_session: date,
    ) -> tuple[list[dict[str, object]], str]:
        start_date = endpoint_session - timedelta(days=LIT02_SEC_LOOKBACK_DAYS)
        end_date = endpoint_session + timedelta(days=LIT02_SEC_FORWARD_DAYS)
        root_url = sec_company_submissions_url(cik=cik)
        try:
            payload, root_text = self._sec_get_json(root_url)
        except ProviderError as exc:
            if "404" in str(exc):
                return [], "SEC_COMPANY_SUBMISSIONS_NOT_FOUND"
            raise
        rows = _submission_rows(payload)
        for shard_url in _declared_shard_urls(
            payload,
            start_date=start_date,
            end_date=end_date,
        ):
            shard_payload, _shard_text = self._sec_get_json(shard_url)
            rows.extend(_submission_rows(shard_payload))
        filtered = _filtered_sec_rows(
            rows,
            start_date=start_date,
            end_date=end_date,
        )
        return filtered, hashlib.sha256(root_text.encode("utf-8")).hexdigest()

    def _verify_successor_identity(
        self,
        *,
        successor_ticker: str,
        endpoint_session: date,
        predecessor: Mapping[str, object],
    ) -> tuple[bool, dict[str, object] | None, str]:
        overview = self._massive_overview(successor_ticker, endpoint_session)
        if overview is None:
            return False, None, "SUCCESSOR_TICKER_OVERVIEW_NOT_FOUND"
        successor_figi = (
            str(overview.get("composite_figi") or "").strip().upper() or None
        )
        successor_cik = _normalize_cik(overview.get("cik"))
        predecessor_figi = (
            str(predecessor.get("composite_figi") or "").strip().upper() or None
        )
        predecessor_cik = _normalize_cik(predecessor.get("cik"))
        consistent = bool(
            (
                predecessor_figi
                and successor_figi
                and predecessor_figi == successor_figi
            )
            or (
                predecessor_cik
                and successor_cik
                and predecessor_cik == successor_cik
            )
        )
        evidence = {
            "ticker": successor_ticker,
            "composite_figi": successor_figi,
            "cik": successor_cik,
            "primary_exchange": overview.get("primary_exchange"),
            "security_type": overview.get("type"),
        }
        return (
            consistent,
            evidence,
            "IDENTITY_MATCH" if consistent else "SUCCESSOR_IDENTITY_MISMATCH",
        )

    def _sec_resolution(
        self,
        *,
        identity: Mapping[str, object],
        endpoint_session: date,
        historical_ticker: str,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
        cik = str(identity.get("cik") or "").strip()
        if not cik:
            return None, [], ["CIK_UNAVAILABLE_FOR_SEC_SOURCE"]
        try:
            filings, submissions_sha = self._sec_candidate_filings(
                cik=cik,
                endpoint_session=endpoint_session,
            )
        except RuntimeError as exc:
            return None, [], [str(exc)]

        evidence_rows: list[dict[str, object]] = []
        ready_candidates: list[dict[str, object]] = []
        incomplete_reasons: list[str] = []
        for filing in filings:
            accession = str(filing["accession_number"])
            if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession):
                incomplete_reasons.append("SEC_ACCESSION_FORMAT_INVALID")
                continue
            filename = f"edgar/data/{int(cik)}/{accession}.txt"
            document = self._sec_get_submission(filename)
            ticker_candidate = parse_explicit_sec_ticker_change(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            terminal_candidate = parse_sec_terminal_transaction(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            row = {
                **filing,
                "submission_source_url": document.source_url,
                "submission_source_sha256": document.source_sha256,
                "company_submissions_sha256": submissions_sha,
                "ticker_change_candidate": ticker_candidate,
                "terminal_candidate": terminal_candidate,
            }
            evidence_rows.append(row)

            for candidate in (ticker_candidate, terminal_candidate):
                if not isinstance(candidate, Mapping):
                    continue
                status = str(candidate.get("status") or "")
                if status == "READY":
                    ready_candidates.append(
                        {
                            **dict(candidate),
                            "source_url": document.source_url,
                            "source_sha256": document.source_sha256,
                            "accession_number": accession,
                            "filing_date": filing["filing_date"],
                        }
                    )
                elif status in {"INCOMPLETE", "CONFLICT"}:
                    incomplete_reasons.append(
                        str(candidate.get("reason") or status)
                    )

        unique_ready: dict[str, dict[str, object]] = {}
        for candidate in ready_candidates:
            key = _fingerprint(
                {
                    "path_id": candidate.get("path_id"),
                    "effective_date": candidate.get("effective_date"),
                    "old_ticker": candidate.get("old_ticker"),
                    "new_ticker": candidate.get("new_ticker"),
                    "cash_per_share": candidate.get("cash_per_share"),
                    "share_exchange_ratio": candidate.get("share_exchange_ratio"),
                    "distribution_per_share": candidate.get("distribution_per_share"),
                    "successor_ticker": candidate.get("successor_ticker"),
                }
            )
            unique_ready[key] = candidate

        if len(unique_ready) > 1:
            return None, evidence_rows, ["MULTIPLE_SEC_READY_CLASSIFICATIONS"]
        if not unique_ready:
            return (
                None,
                evidence_rows,
                incomplete_reasons or ["NO_ADMISSIBLE_SEC_8K_EVIDENCE"],
            )

        candidate = next(iter(unique_ready.values()))
        path_id = str(candidate.get("path_id") or "")
        if path_id == "TICKER_CONTINUITY":
            successor_ticker = str(candidate.get("new_ticker") or "")
            consistent, successor_identity, reason = self._verify_successor_identity(
                successor_ticker=successor_ticker,
                endpoint_session=endpoint_session,
                predecessor=identity,
            )
            if not consistent:
                return None, evidence_rows, [reason]
            candidate["successor_identity"] = successor_identity
            return candidate, evidence_rows, []

        if path_id in {"TERMINAL_STOCK", "TERMINAL_MIXED"}:
            successor_ticker = str(candidate.get("successor_ticker") or "")
            if not successor_ticker:
                return None, evidence_rows, ["SUCCESSOR_TICKER_IDENTITY_REQUIRED"]
            overview = self._massive_overview(successor_ticker, endpoint_session)
            if overview is None:
                return None, evidence_rows, ["SUCCESSOR_TICKER_OVERVIEW_NOT_FOUND"]
            candidate["successor_identity"] = {
                "ticker": successor_ticker,
                "composite_figi": (
                    str(overview.get("composite_figi") or "").strip().upper() or None
                ),
                "cik": _normalize_cik(overview.get("cik")),
                "primary_exchange": overview.get("primary_exchange"),
                "security_type": overview.get("type"),
            }
            return candidate, evidence_rows, []

        return candidate, evidence_rows, []

    def _resolve_instrument(
        self,
        *,
        instrument_id: str,
        identity_rows: list[dict[str, object]],
        endpoint_session: date,
        historical_ticker: str,
    ) -> dict[str, object]:
        identity = select_identity_authorities(
            identity_rows,
            endpoint_session=endpoint_session,
            instrument_id=instrument_id,
        )
        unresolved: list[str] = list(identity.get("identity_conflicts") or [])
        if str(identity.get("identity_status") or "") == "CONFLICT":
            return {
                "instrument_id": instrument_id,
                "identity": identity,
                "resolution_status": "UNRESOLVED",
                "path_id": None,
                "classification": None,
                "unresolved_reasons": unresolved,
                "massive_evidence": None,
                "sec_evidence": [],
            }

        composite_figi = str(identity.get("composite_figi") or "").strip()
        if composite_figi:
            raw_events = self._massive_ticker_events(composite_figi)
            massive_candidate = classify_massive_ticker_events(
                raw_events,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            massive_evidence = {
                "query_identifier": composite_figi,
                "query_identifier_type": "composite_figi",
                "source_sha256": _fingerprint(raw_events),
                "event_count": len(raw_events),
                "candidate": massive_candidate,
            }
            if isinstance(massive_candidate, Mapping):
                if massive_candidate.get("status") == "READY":
                    return {
                        "instrument_id": instrument_id,
                        "identity": identity,
                        "resolution_status": "RESOLVED",
                        "path_id": "TICKER_CONTINUITY",
                        "classification": dict(massive_candidate),
                        "unresolved_reasons": [],
                        "massive_evidence": massive_evidence,
                        "sec_evidence": [],
                    }
                if massive_candidate.get("status") == "CONFLICT":
                    reason = str(
                        massive_candidate.get("reason")
                        or "MASSIVE_TICKER_EVENT_CONFLICT"
                    )
                    return {
                        "instrument_id": instrument_id,
                        "identity": identity,
                        "resolution_status": "UNRESOLVED",
                        "path_id": None,
                        "classification": None,
                        "unresolved_reasons": [reason],
                        "massive_evidence": massive_evidence,
                        "sec_evidence": [],
                    }
                unresolved.append(
                    str(
                        massive_candidate.get("reason")
                        or "MASSIVE_TICKER_EVENT_UNRESOLVED"
                    )
                )
        else:
            massive_evidence = None
            unresolved.append("COMPOSITE_FIGI_UNAVAILABLE")

        sec_candidate, sec_evidence, sec_reasons = self._sec_resolution(
            identity=identity,
            endpoint_session=endpoint_session,
            historical_ticker=historical_ticker,
        )
        if sec_candidate is not None:
            return {
                "instrument_id": instrument_id,
                "identity": identity,
                "resolution_status": "RESOLVED",
                "path_id": sec_candidate.get("path_id"),
                "classification": sec_candidate,
                "unresolved_reasons": [],
                "massive_evidence": massive_evidence,
                "sec_evidence": sec_evidence,
            }
        unresolved.extend(sec_reasons)
        return {
            "instrument_id": instrument_id,
            "identity": identity,
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": sorted(set(unresolved)),
            "massive_evidence": massive_evidence,
            "sec_evidence": sec_evidence,
        }

    def _aggregate_case(
        self,
        case: Mapping[str, object],
        instrument_results: list[dict[str, object]],
    ) -> dict[str, object]:
        resolved = [
            row
            for row in instrument_results
            if row.get("resolution_status") == "RESOLVED"
        ]
        unresolved = [
            row
            for row in instrument_results
            if row.get("resolution_status") != "RESOLVED"
        ]
        reasons: set[str] = set()
        for row in unresolved:
            reasons.update(
                str(value) for value in (row.get("unresolved_reasons") or [])
            )
        if unresolved:
            return {
                "case_id": case.get("case_id"),
                "endpoint_session": case.get("endpoint_session"),
                "historical_ticker": case.get("historical_ticker"),
                "instrument_ids": list(case.get("instrument_ids") or []),
                "resolution_status": "UNRESOLVED",
                "path_id": None,
                "classification": None,
                "unresolved_reasons": sorted(
                    reasons or {"INSTRUMENT_SOURCE_UNRESOLVED"}
                ),
                "instrument_results": instrument_results,
            }

        path_ids = {str(row.get("path_id") or "") for row in resolved}
        if len(path_ids) != 1:
            return {
                "case_id": case.get("case_id"),
                "endpoint_session": case.get("endpoint_session"),
                "historical_ticker": case.get("historical_ticker"),
                "instrument_ids": list(case.get("instrument_ids") or []),
                "resolution_status": "UNRESOLVED",
                "path_id": None,
                "classification": None,
                "unresolved_reasons": ["MULTI_INSTRUMENT_RETURN_PATH_CONFLICT"],
                "instrument_results": instrument_results,
            }

        path_id = next(iter(path_ids))
        classifications = [row.get("classification") for row in resolved]
        class_core = [
            {
                key: value
                for key, value in dict(item).items()
                if key
                not in {
                    "source_url",
                    "source_sha256",
                    "accession_number",
                    "filing_date",
                    "matched_excerpt",
                }
            }
            for item in classifications
            if isinstance(item, Mapping)
        ]
        if len({_fingerprint(item) for item in class_core}) > 1:
            return {
                "case_id": case.get("case_id"),
                "endpoint_session": case.get("endpoint_session"),
                "historical_ticker": case.get("historical_ticker"),
                "instrument_ids": list(case.get("instrument_ids") or []),
                "resolution_status": "UNRESOLVED",
                "path_id": None,
                "classification": None,
                "unresolved_reasons": ["MULTI_INSTRUMENT_ECONOMIC_FACT_CONFLICT"],
                "instrument_results": instrument_results,
            }
        return {
            "case_id": case.get("case_id"),
            "endpoint_session": case.get("endpoint_session"),
            "historical_ticker": case.get("historical_ticker"),
            "instrument_ids": list(case.get("instrument_ids") or []),
            "resolution_status": "RESOLVED",
            "path_id": path_id,
            "classification": class_core[0] if class_core else None,
            "unresolved_reasons": [],
            "instrument_results": instrument_results,
        }

    def _load_cached_case(
        self,
        case: Mapping[str, object],
    ) -> dict[str, object] | None:
        case_id = str(case.get("case_id") or "")
        path = self.case_path(case_id)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("contract_version") != LIT02_SOURCE_METADATA_CONTRACT
            or payload.get("source_policy_fingerprint")
            != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
            or payload.get("feasibility_plan_fingerprint")
            != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
            or payload.get("case_id") != case_id
            or payload.get("case_input_fingerprint") != _fingerprint(dict(case))
            or not isinstance(payload.get("result"), Mapping)
        ):
            return None
        return dict(payload["result"])

    def _write_case(
        self,
        case: Mapping[str, object],
        result: Mapping[str, object],
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.case_path(str(case["case_id"])),
            canonical_json(
                {
                    "contract_version": LIT02_SOURCE_METADATA_CONTRACT,
                    "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
                    "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
                    "case_id": case["case_id"],
                    "case_input_fingerprint": _fingerprint(dict(case)),
                    "result": dict(result),
                    "economic_outcome_values_read": 0,
                    "new_price_or_return_provider_reads": 0,
                    "protected_return_rows_read": 0,
                    "protected_holdout_consumed": False,
                }
            )
            + "\n",
        )

    def run(self, *, force: bool = False) -> dict[str, object]:
        cases, _freeze_report = self._load_and_require_plan()
        identity_rows, identity_fingerprint, identity_cached = (
            self._identity_rows_from_cache(cases)
        )

        case_results: list[dict[str, object]] = []
        cached_cases = 0
        started = time.monotonic()
        total = len(cases)
        print(
            "[LIT-02][SOURCE] started | "
            f"cases={total} | policy={LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT[:12]}... "
            f"| plan={LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT[:12]}... "
            f"| identity_cache={'reused' if identity_cached else 'built'}"
        )
        print(
            "[LIT-02][SOURCE] price/return reads disabled | protected reads disabled | "
            f"SEC submission ceiling={SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES}"
        )

        for index, case in enumerate(cases, start=1):
            endpoint = date.fromisoformat(str(case["endpoint_session"]))
            ticker = str(case["historical_ticker"])
            cached = None if force else self._load_cached_case(case)
            if cached is not None:
                result = cached
                cached_cases += 1
                mode = "cache"
            else:
                instrument_results = []
                for instrument_id in case.get("instrument_ids") or []:
                    instrument_text = str(instrument_id)
                    instrument_results.append(
                        self._resolve_instrument(
                            instrument_id=instrument_text,
                            identity_rows=identity_rows.get(instrument_text, []),
                            endpoint_session=endpoint,
                            historical_ticker=ticker,
                        )
                    )
                result = self._aggregate_case(case, instrument_results)
                self._write_case(case, result)
                mode = "source"

            case_results.append(result)
            elapsed = time.monotonic() - started
            rate = index / elapsed if elapsed > 0 else 0.0
            remaining = (total - index) / rate if rate > 0 else 0.0
            print(
                f"[LIT-02][SOURCE] case {index}/{total} {(index / total) * 100.0:.1f}% "
                f"| elapsed={elapsed:.1f}s ETA={remaining:.1f}s | {endpoint} {ticker} "
                f"| mode={mode} | status={result.get('resolution_status')} "
                f"| path={result.get('path_id') or 'SOURCE_UNRESOLVED'} "
                f"| provider_reads={self.provider_reads}"
            )

        report = build_source_coverage_report(
            case_results=case_results,
            provider_reads=self.provider_reads,
            massive_provider_reads=self._massive_reads,
            sec_provider_reads=self._sec_reads,
            cached_cases=cached_cases,
            identity_evidence_fingerprint=identity_fingerprint,
        )
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        result = dict(report)
        result["report_path"] = str(self.report_path())
        return result
