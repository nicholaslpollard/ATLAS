from __future__ import annotations

import hashlib
import json
import re
import time
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Mapping

from packages.core.atomic_io import atomic_write_text
from packages.core.exceptions import ProviderError
from packages.core.settings import AtlasSettings
from packages.providers.sec_edgar import (
    SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP,
    sec_company_submissions_url,
)
from packages.providers.sec_edgar_archive import SEC_ARCHIVE_SCIENTIFIC_SUBMISSION_MAX_RESPONSE_BYTES

from .literature_momseason_lit02_source_feasibility import LIT02_SOURCE_FEASIBILITY_STORAGE_ROOT
from .literature_momseason_lit02_source_metadata import (
    LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
    LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
    LIT02_REQUIRED_SOURCE_COVERAGE,
    LIT02_SEC_RELEVANT_ITEMS,
    LIT02_SOURCE_METADATA_IDENTITY_CACHE,
    LIT02_SOURCE_METADATA_INCOMPLETE,
    LIT02_SOURCE_METADATA_READY,
    LIT02_SOURCE_METADATA_REPORT,
    LIT02_SOURCE_METADATA_STORAGE_ROOT,
    _columnar_rows,
    _declared_shard_urls,
    _fingerprint,
    _normalize_cik,
    _plain_sec_text,
    _submission_rows,
    parse_explicit_sec_ticker_change,
)
from .literature_momseason_lit02_source_metadata_diagnostic import (
    LIT02_SOURCE_METADATA_DIAGNOSTIC_REPORT,
)
from .literature_momseason_lit02_source_metadata_transport import (
    MomSeasonLIT02SourceMetadataTransportSafe,
)
from .literature_momseason_source import canonical_json


LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT = (
    "lit02-source-metadata-repair-v2-contextual-sec-execution-370d-6k-no-prices"
)
LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_READY = "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_READY"
LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE = "LIT02_DELISTING_AWARE_SOURCE_COVERAGE_INCOMPLETE"
LIT02_SOURCE_METADATA_REPAIR_V2_STORAGE_ROOT = "m2"
LIT02_SOURCE_METADATA_REPAIR_V2_REPORT = "r.json"

LIT02_ACCEPTED_V1_CLASSIFICATION_FINGERPRINT = (
    "636fb4bce1d5cd1501c535159e053dd39f5a301f9991b919b00ed2c8cc2e872c"
)
LIT02_ACCEPTED_V1_REPORT_FINGERPRINT = (
    "0f739c24013d6490e76c15461a1e5c69149fa09105b94c631f3e0a64fa43b2ca"
)
LIT02_ACCEPTED_DIAGNOSTIC_FINGERPRINT = (
    "6253178a77b26d5fa1ae9e99e5ff2036fab913ce9a5b3560a1989f6a6d1a3a2e"
)
LIT02_ACCEPTED_V1_CASES = 199
LIT02_ACCEPTED_V1_RESOLVED = 36
LIT02_ACCEPTED_V1_UNRESOLVED = 163

LIT02_REPAIR_V2_SEC_LOOKBACK_DAYS = 370
LIT02_REPAIR_V2_SEC_FORWARD_DAYS = 10
LIT02_REPAIR_V2_SEC_MAX_CANDIDATE_FILINGS = 128
LIT02_REPAIR_V2_SEC_ALLOWED_FORMS = frozenset({"8-K", "8-K/A", "6-K", "6-K/A"})

_MONTHS = {
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
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_MONTH_WORD = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sep\.?|Sept\.?|Oct\.?|Nov\.?|Dec\.?)"
)
_DATE_TOKEN_V2 = rf"(?:{_MONTH_WORD}\s+\d{{1,2}},\s+\d{{4}}|\d{{4}}-\d{{2}}-\d{{2}})"

_EXECUTION_PATTERNS = (
    re.compile(
        rf"(?is:\bOn\s+(?P<date>{_DATE_TOKEN_V2})\s*,.{{0,1000}}?"
        rf"\b(?:merger|mergers|transaction|acquisition|business\s+combination)\b.{{0,400}}?"
        rf"\b(?:was|were|has\s+been|had\s+been)?\s*"
        rf"(?:completed|consummated|closed|effected|became\s+effective)\b)"
    ),
    re.compile(
        rf"(?is:\bOn\s+(?P<date>{_DATE_TOKEN_V2})\s*,.{{0,1000}}?"
        rf"\b(?:completed|consummated|closed|effected)\b.{{0,400}}?"
        rf"\b(?:merger|mergers|transaction|acquisition|business\s+combination)\b)"
    ),
    re.compile(
        rf"(?is:\bOn\s+(?P<date>{_DATE_TOKEN_V2})\s*,.{{0,1200}}?"
        rf"\bmerged\s+with\s+and\s+into\b)"
    ),
    re.compile(
        rf"(?is:\b(?:merger|mergers|transaction|acquisition|business\s+combination)\b.{{0,500}}?"
        rf"\b(?:was|were|has\s+been|had\s+been)?\s*"
        rf"(?:completed|consummated|closed|effected|became\s+effective)\b.{{0,220}}?"
        rf"\b(?:on|as\s+of)\s+(?P<date>{_DATE_TOKEN_V2}))"
    ),
    re.compile(
        rf"(?is:\b(?:completed|consummated|closed)\b.{{0,400}}?"
        rf"\b(?:merger|mergers|transaction|acquisition|business\s+combination)\b.{{0,220}}?"
        rf"\b(?:on|as\s+of)\s+(?P<date>{_DATE_TOKEN_V2}))"
    ),
    re.compile(
        rf"(?is:\b(?:closing\s+date|effective\s+date)\b\s*(?:was|is|:)??\s*"
        rf"(?P<date>{_DATE_TOKEN_V2}).{{0,1400}}?"
        rf"\b(?:completed|consummated|closed|merged\s+with\s+and\s+into)\b)"
    ),
)

_STRONG_CASH_PATTERNS = (
    re.compile(
        r"(?is:\beach\s+(?:issued\s+and\s+outstanding\s+)?share\b.{0,800}?"
        r"\b(?:converted|cancelled|canceled)\b.{0,500}?\bright\s+to\s+receive\b.{0,260}?"
        r"\$\s*(?P<value>\d+(?:\.\d+)?)\b)"
    ),
    re.compile(
        r"(?is:\b(?:per\s+share\s+merger\s+consideration|merger\s+consideration|per\s+share\s+price)\b"
        r".{0,180}?\$\s*(?P<value>\d+(?:\.\d+)?)\b)"
    ),
    re.compile(
        r"(?is:\$\s*(?P<value>\d+(?:\.\d+)?)\s+in\s+cash\b.{0,100}?\bper\s+share\b)"
    ),
)
_GENERIC_CASH_PATTERNS = (
    re.compile(
        r"(?is:\$\s*(?P<value>\d+(?:\.\d+)?)\s*(?:in\s+cash\s*)?"
        r"\b(?:per\s+share|for\s+each\s+share)\b)"
    ),
    re.compile(
        r"(?is:\bcash\s+consideration\b.{0,180}?\$\s*(?P<value>\d+(?:\.\d+)?)\b)"
    ),
)
_STRONG_SHARE_PATTERNS = (
    re.compile(
        r"(?is:\beach\s+(?:issued\s+and\s+outstanding\s+)?share\b.{0,900}?"
        r"\b(?:converted|exchangeable)\b.{0,500}?\bright\s+to\s+receive\b.{0,220}?"
        r"(?P<value>\d+(?:\.\d+)?)\s+(?:shares?|common\s+shares?|ordinary\s+shares?)\b)"
    ),
    re.compile(
        r"(?is:\bexchange\s+ratio\b.{0,120}?\b(?:of|equal\s+to|:)\s*"
        r"(?P<value>\d+(?:\.\d+)?)\b)"
    ),
)
_DISTRIBUTION_PATTERN = re.compile(
    r"(?is:\b(?:liquidating|liquidation|terminal|final)\s+distribution\b.{0,220}?"
    r"\$\s*(?P<value>\d+(?:\.\d+)?)\b)"
)
_SUCCESSOR_TICKER_PATTERNS_V2 = (
    re.compile(
        r"(?is:\b(?:combined\s+company|surviving\s+corporation|successor|parent)\b.{0,700}?"
        r"\b(?:trade|trading|traded|listed)\b.{0,180}?"
        r"\b(?:symbol|ticker)\b\s*(?:of|:)?\s*[\"'“”]?"
        r"(?P<ticker>(?-i:[A-Z][A-Z0-9.-]{0,9}))[\"'“”]?)"
    ),
    re.compile(
        r"(?is:\b(?:trade|trading|traded|listed)\b.{0,160}?\bunder\b.{0,80}?"
        r"\b(?:the\s+)?(?:new\s+)?(?:symbol|ticker)\b\s*[\"'“”]?"
        r"(?P<ticker>(?-i:[A-Z][A-Z0-9.-]{0,9}))[\"'“”]?)"
    ),
)

_SCHEDULED_TICKER_CHANGE = re.compile(
    rf"(?is:\b(?:commence|begin|start)\s+trading\b.{{0,220}}?"
    rf"\bunder\b.{{0,70}}?\b(?:trading\s+)?symbol\b\s*[\"'“”]?"
    rf"(?P<new>(?-i:[A-Z][A-Z0-9.-]{{0,9}}))[\"'“”]?.{{0,220}}?"
    rf"\b(?:on|effective)\s+(?P<date>{_DATE_TOKEN_V2}).{{0,500}}?"
    rf"\b(?:until\s+that\s+time|previously|formerly|present\s+symbol)\b.{{0,220}}?"
    rf"\b(?:symbol|ticker)\b\s*[\"'“”]?"
    rf"(?P<old>(?-i:[A-Z][A-Z0-9.-]{{0,9}}))[\"'“”]?)"
)
_DIRECT_TICKER_CHANGE = re.compile(
    rf"(?is:\b(?:trading\s+)?(?:symbol|ticker)\b.{{0,160}}?"
    rf"\b(?:changed|changes|change)\s+from\s+[\"'“”]?"
    rf"(?P<old>(?-i:[A-Z][A-Z0-9.-]{{0,9}}))[\"'“”]?\s+to\s+[\"'“”]?"
    rf"(?P<new>(?-i:[A-Z][A-Z0-9.-]{{0,9}}))[\"'“”]?.{{0,220}}?"
    rf"\b(?:effective|commencing|beginning|on)\b(?:\s+(?:on|as\s+of))?\s*"
    rf"(?P<date>{_DATE_TOKEN_V2}))"
)


def _parse_date_v2(value: object) -> date | None:
    text = str(value or "").strip().strip(",")
    if not text:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    match = re.fullmatch(
        rf"(?P<month>{_MONTH_WORD})\s+(?P<day>\d{{1,2}}),\s+(?P<year>\d{{4}})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    month_key = match.group("month").lower().rstrip(".")
    month = _MONTHS.get(month_key)
    if month is None:
        return None
    try:
        return date(int(match.group("year")), month, int(match.group("day")))
    except ValueError:
        return None


def _float_values(text: str, patterns: tuple[re.Pattern[str], ...]) -> set[float]:
    values: set[float] = set()
    for pattern in patterns:
        for match in pattern.finditer(text):
            try:
                value = float(match.group("value"))
            except (TypeError, ValueError):
                continue
            if value > 0.0:
                values.add(value)
    return values


def _cash_values(text: str) -> set[float]:
    strong = _float_values(text, _STRONG_CASH_PATTERNS)
    return strong if strong else _float_values(text, _GENERIC_CASH_PATTERNS)


def _share_values(text: str) -> set[float]:
    return _float_values(text, _STRONG_SHARE_PATTERNS)


def _successor_tickers_v2(text: str, historical_ticker: str) -> set[str]:
    values: set[str] = set()
    for pattern in _SUCCESSOR_TICKER_PATTERNS_V2:
        for match in pattern.finditer(text):
            ticker = match.group("ticker").strip()
            if ticker and ticker != historical_ticker:
                values.add(ticker)
    return values


def _execution_contexts(plain: str, endpoint_session: date) -> list[tuple[date, str]]:
    contexts: dict[tuple[date, str], str] = {}
    for pattern in _EXECUTION_PATTERNS:
        for match in pattern.finditer(plain):
            parsed = _parse_date_v2(match.group("date"))
            if parsed is None or parsed > endpoint_session:
                continue
            start = max(0, match.start() - 2200)
            end = min(len(plain), match.end() + 3200)
            context = plain[start:end]
            key = (parsed, hashlib.sha256(context.encode("utf-8")).hexdigest()[:16])
            contexts[key] = context
    return [(item[0], contexts[item]) for item in sorted(contexts, key=lambda row: (row[0], row[1]))]


def parse_explicit_sec_ticker_change_v2(
    text: str,
    *,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    base = parse_explicit_sec_ticker_change(
        text,
        endpoint_session=endpoint_session,
        historical_ticker=historical_ticker,
    )
    if isinstance(base, Mapping) and base.get("status") == "READY":
        return dict(base)

    plain = _plain_sec_text(text)
    candidates: dict[tuple[str, str, date], str] = {}
    for pattern, rule in (
        (_DIRECT_TICKER_CHANGE, "EXPLICIT_SEC_TICKER_CHANGE_V2"),
        (_SCHEDULED_TICKER_CHANGE, "SEC_SCHEDULED_TICKER_CHANGE_WITH_ENDPOINT_IDENTITY_CONFIRMATION"),
    ):
        for match in pattern.finditer(plain):
            old = match.group("old").strip()
            new = match.group("new").strip()
            effective = _parse_date_v2(match.group("date"))
            if old != historical_ticker or old == new or effective is None or effective > endpoint_session:
                continue
            start = max(0, match.start() - 600)
            end = min(len(plain), match.end() + 600)
            candidates[(old, new, effective)] = rule + "\n" + plain[start:end]

    if not candidates:
        return base if isinstance(base, Mapping) else None
    latest_date = max(key[2] for key in candidates)
    latest = {key: value for key, value in candidates.items() if key[2] == latest_date}
    if len(latest) != 1:
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_EXPLICIT_TICKER_CHANGES_V2",
            "candidates": [
                {"old_ticker": key[0], "new_ticker": key[1], "effective_date": key[2].isoformat()}
                for key in sorted(latest)
            ],
        }
    (old, new, effective), evidence = next(iter(latest.items()))
    rule, excerpt = evidence.split("\n", 1)
    return {
        "status": "READY",
        "path_id": "TICKER_CONTINUITY",
        "old_ticker": old,
        "new_ticker": new,
        "effective_date": effective.isoformat(),
        "matched_excerpt": excerpt[:2200],
        "evidence_rule": rule,
    }


def _candidate_core(candidate: Mapping[str, object]) -> dict[str, object]:
    return {
        "path_id": candidate.get("path_id"),
        "effective_date": candidate.get("effective_date"),
        "old_ticker": candidate.get("old_ticker"),
        "new_ticker": candidate.get("new_ticker"),
        "cash_per_share": candidate.get("cash_per_share"),
        "share_exchange_ratio": candidate.get("share_exchange_ratio"),
        "distribution_per_share": candidate.get("distribution_per_share"),
        "successor_ticker": candidate.get("successor_ticker"),
    }


def parse_sec_terminal_transaction_v2(
    text: str,
    *,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    plain = _plain_sec_text(text)
    contexts = _execution_contexts(plain, endpoint_session)
    global_cash = _cash_values(plain)
    global_shares = _share_values(plain)
    global_distributions = {
        float(match.group("value"))
        for match in _DISTRIBUTION_PATTERN.finditer(plain)
        if float(match.group("value")) > 0.0
    }

    if not contexts:
        if not global_cash and not global_shares and not global_distributions:
            return None
        return {
            "status": "INCOMPLETE",
            "reason": "TERMINAL_TRANSACTION_EFFECTIVE_DATE_UNRESOLVED",
            "cash_values": sorted(global_cash),
            "share_ratios": sorted(global_shares),
            "distribution_values": sorted(global_distributions),
            "event_dates": [],
            "parser_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
        }

    ready: dict[str, dict[str, object]] = {}
    conflicts: list[dict[str, object]] = []
    context_dates: set[date] = set()
    for effective, context in contexts:
        context_dates.add(effective)
        cash_values = _cash_values(context)
        share_values = _share_values(context)
        distribution_values = {
            float(match.group("value"))
            for match in _DISTRIBUTION_PATTERN.finditer(context)
            if float(match.group("value")) > 0.0
        }
        successor_tickers = _successor_tickers_v2(context, historical_ticker)

        if distribution_values:
            if len(distribution_values) != 1:
                conflicts.append({
                    "reason": "MULTIPLE_TERMINAL_DISTRIBUTION_VALUES",
                    "values": sorted(distribution_values),
                    "effective_date": effective.isoformat(),
                })
                continue
            candidate = {
                "status": "READY",
                "path_id": "TERMINAL_DISTRIBUTION",
                "effective_date": effective.isoformat(),
                "distribution_per_share": next(iter(distribution_values)),
                "evidence_rule": "CONTEXTUAL_SEC_EXECUTED_TERMINAL_DISTRIBUTION_V2",
            }
        elif cash_values or share_values:
            if len(cash_values) > 1:
                conflicts.append({
                    "reason": "MULTIPLE_TERMINAL_CASH_VALUES",
                    "cash_values": sorted(cash_values),
                    "effective_date": effective.isoformat(),
                })
                continue
            if len(share_values) > 1:
                conflicts.append({
                    "reason": "MULTIPLE_TERMINAL_SHARE_RATIOS",
                    "share_ratios": sorted(share_values),
                    "effective_date": effective.isoformat(),
                })
                continue
            successor = next(iter(successor_tickers)) if len(successor_tickers) == 1 else None
            if cash_values and not share_values:
                candidate = {
                    "status": "READY",
                    "path_id": "TERMINAL_CASH",
                    "effective_date": effective.isoformat(),
                    "cash_per_share": next(iter(cash_values)),
                    "evidence_rule": "CONTEXTUAL_SEC_EXECUTED_CASH_CONSIDERATION_V2",
                }
            elif share_values and not cash_values:
                candidate = {
                    "status": "READY" if successor else "INCOMPLETE",
                    "path_id": "TERMINAL_STOCK",
                    "effective_date": effective.isoformat(),
                    "share_exchange_ratio": next(iter(share_values)),
                    "successor_ticker": successor,
                    "reason": None if successor else "SUCCESSOR_TICKER_IDENTITY_REQUIRED",
                    "evidence_rule": "CONTEXTUAL_SEC_EXECUTED_STOCK_CONSIDERATION_V2",
                }
            else:
                candidate = {
                    "status": "READY" if successor else "INCOMPLETE",
                    "path_id": "TERMINAL_MIXED",
                    "effective_date": effective.isoformat(),
                    "cash_per_share": next(iter(cash_values)),
                    "share_exchange_ratio": next(iter(share_values)),
                    "successor_ticker": successor,
                    "reason": None if successor else "SUCCESSOR_TICKER_IDENTITY_REQUIRED",
                    "evidence_rule": "CONTEXTUAL_SEC_EXECUTED_MIXED_CONSIDERATION_V2",
                }
        else:
            continue

        candidate["matched_excerpt"] = context[:2600]
        candidate["parser_version"] = LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT
        if candidate.get("status") == "READY":
            ready[_fingerprint(_candidate_core(candidate))] = candidate
        else:
            conflicts.append(candidate)

    if ready:
        candidates = list(ready.values())
        latest_date = max(date.fromisoformat(str(item["effective_date"])) for item in candidates)
        latest = [
            item for item in candidates
            if date.fromisoformat(str(item["effective_date"])) == latest_date
        ]
        latest_unique = {_fingerprint(_candidate_core(item)): item for item in latest}
        if len(latest_unique) == 1:
            return next(iter(latest_unique.values()))
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_CONTEXTUAL_TERMINAL_CLASSIFICATIONS",
            "effective_date": latest_date.isoformat(),
            "candidates": [_candidate_core(item) for item in latest_unique.values()],
        }

    if conflicts:
        reasons = sorted({str(item.get("reason") or "CONFLICT") for item in conflicts})
        if len(reasons) == 1:
            payload = dict(conflicts[0])
            payload["status"] = "CONFLICT" if str(payload.get("reason") or "").startswith("MULTIPLE_") else "INCOMPLETE"
            payload["all_event_dates"] = sorted(item.isoformat() for item in context_dates)
            return payload
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_CONTEXTUAL_TERMINAL_CONFLICTS",
            "reasons": reasons,
            "event_dates": sorted(item.isoformat() for item in context_dates),
        }

    if global_cash or global_shares or global_distributions:
        return {
            "status": "INCOMPLETE",
            "reason": "TERMINAL_TRANSACTION_CONTEXT_UNRESOLVED",
            "cash_values": sorted(global_cash),
            "share_ratios": sorted(global_shares),
            "distribution_values": sorted(global_distributions),
            "event_dates": sorted(item.isoformat() for item in context_dates),
        }
    return None


def _filtered_sec_rows_v2(
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
        if not accession or form not in LIT02_REPAIR_V2_SEC_ALLOWED_FORMS:
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
        if form.startswith("8-K") and items and not (items & LIT02_SEC_RELEVANT_ITEMS):
            continue
        unique[accession] = {
            "accession_number": accession,
            "filing_date": filing_date.isoformat(),
            "form": form,
            "items": sorted(items),
            "primary_document": str(row.get("primaryDocument") or "").strip() or None,
        }
    ordered = sorted(unique.values(), key=lambda item: (str(item["filing_date"]), str(item["accession_number"])))
    if len(ordered) > LIT02_REPAIR_V2_SEC_MAX_CANDIDATE_FILINGS:
        raise RuntimeError(
            "LIT-02 repair-v2 SEC source lookup exceeded bounded candidate filing count: "
            f"{len(ordered)} > {LIT02_REPAIR_V2_SEC_MAX_CANDIDATE_FILINGS}"
        )
    return ordered


def _select_latest_ready(candidates: list[dict[str, object]]) -> tuple[dict[str, object] | None, str | None]:
    if not candidates:
        return None, None
    dated: list[tuple[date, dict[str, object]]] = []
    for item in candidates:
        try:
            effective = date.fromisoformat(str(item.get("effective_date") or ""))
        except ValueError:
            continue
        dated.append((effective, item))
    if not dated:
        return None, "READY_CANDIDATE_EFFECTIVE_DATE_INVALID"
    latest_date = max(item[0] for item in dated)
    latest = [item[1] for item in dated if item[0] == latest_date]
    unique = {_fingerprint(_candidate_core(item)): item for item in latest}
    if len(unique) != 1:
        return None, "MULTIPLE_SEC_READY_CLASSIFICATIONS_AT_LATEST_EFFECTIVE_DATE"
    return next(iter(unique.values())), None


def _report_fingerprint(report: Mapping[str, object]) -> str:
    return _fingerprint({
        key: value
        for key, value in report.items()
        if key not in {
            "source_metadata_provider_reads",
            "massive_source_metadata_reads",
            "sec_source_metadata_reads",
            "cached_case_manifests_reused",
        }
    })


class MomSeasonLIT02SourceMetadataRepairV2(MomSeasonLIT02SourceMetadataTransportSafe):
    """Outcome-free v2 source repair over only the accepted v1 unresolved LIT-02 cases."""

    def __init__(self, settings: AtlasSettings, **kwargs: object) -> None:
        super().__init__(settings, **kwargs)
        self.v1_root = self.root
        self.root = self.feasibility_root / LIT02_SOURCE_METADATA_REPAIR_V2_STORAGE_ROOT

    def identity_cache_path(self) -> Path:
        return self.v1_root / LIT02_SOURCE_METADATA_IDENTITY_CACHE

    def report_path(self) -> Path:
        return self.root / LIT02_SOURCE_METADATA_REPAIR_V2_REPORT

    def case_path(self, case_id: str) -> Path:
        key = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
        return self.root / f"{key}.json"

    def _v1_case_path(self, case_id: str) -> Path:
        key = hashlib.sha256(case_id.encode("utf-8")).hexdigest()[:12]
        return self.v1_root / f"{key}.json"

    def _require_v1_state(self) -> str:
        source_path = self.v1_root / LIT02_SOURCE_METADATA_REPORT
        diagnostic_path = self.v1_root / LIT02_SOURCE_METADATA_DIAGNOSTIC_REPORT
        identity_path = self.identity_cache_path()
        if not source_path.is_file() or not diagnostic_path.is_file() or not identity_path.is_file():
            raise RuntimeError("LIT-02 accepted v1 source report, diagnostic, and identity cache are required")
        source = json.loads(source_path.read_text(encoding="utf-8"))
        diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        if source.get("classification_fingerprint") != LIT02_ACCEPTED_V1_CLASSIFICATION_FINGERPRINT:
            raise RuntimeError("LIT-02 accepted v1 classification fingerprint mismatch")
        if source.get("report_fingerprint") != LIT02_ACCEPTED_V1_REPORT_FINGERPRINT:
            raise RuntimeError("LIT-02 accepted v1 source report fingerprint mismatch")
        if diagnostic.get("diagnostic_fingerprint") != LIT02_ACCEPTED_DIAGNOSTIC_FINGERPRINT:
            raise RuntimeError("LIT-02 accepted diagnostic fingerprint mismatch")
        if int(source.get("feasibility_cases") or 0) != LIT02_ACCEPTED_V1_CASES:
            raise RuntimeError("LIT-02 accepted v1 case count mismatch")
        if int(source.get("resolved_cases") or 0) != LIT02_ACCEPTED_V1_RESOLVED:
            raise RuntimeError("LIT-02 accepted v1 resolved count mismatch")
        if int(source.get("unresolved_cases") or 0) != LIT02_ACCEPTED_V1_UNRESOLVED:
            raise RuntimeError("LIT-02 accepted v1 unresolved count mismatch")
        for field in (
            "economic_outcome_values_read",
            "new_price_or_return_provider_reads",
            "protected_return_rows_read",
            "broker_reads_performed",
            "broker_writes_performed",
            "order_writes_performed",
            "paper_submits_performed",
            "live_writes_performed",
        ):
            if int(source.get(field) or 0) != 0:
                raise RuntimeError(f"LIT-02 accepted v1 safety field is nonzero: {field}")
        if bool(source.get("protected_holdout_consumed")):
            raise RuntimeError("LIT-02 accepted v1 consumed protected holdout")
        fingerprint = str(identity.get("identity_evidence_fingerprint") or "")
        if not fingerprint:
            raise RuntimeError("LIT-02 accepted identity fingerprint missing")
        return fingerprint

    def _load_v1_case(self, case: Mapping[str, object]) -> dict[str, object]:
        case_id = str(case.get("case_id") or "")
        path = self._v1_case_path(case_id)
        if not path.is_file():
            raise RuntimeError(f"LIT-02 accepted v1 case manifest missing: {case_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        result = payload.get("result")
        if not isinstance(result, Mapping):
            raise RuntimeError(f"LIT-02 accepted v1 case result invalid: {case_id}")
        return dict(result)

    def _load_cached_case(self, case: Mapping[str, object]) -> dict[str, object] | None:
        path = self.case_path(str(case.get("case_id") or ""))
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if (
            payload.get("contract_version") != LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT
            or payload.get("source_policy_fingerprint") != LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT
            or payload.get("feasibility_plan_fingerprint") != LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT
            or payload.get("base_classification_fingerprint") != LIT02_ACCEPTED_V1_CLASSIFICATION_FINGERPRINT
            or payload.get("base_diagnostic_fingerprint") != LIT02_ACCEPTED_DIAGNOSTIC_FINGERPRINT
            or payload.get("case_input_fingerprint") != _fingerprint(dict(case))
            or not isinstance(payload.get("result"), Mapping)
        ):
            return None
        return dict(payload["result"])

    def _write_case(self, case: Mapping[str, object], result: Mapping[str, object]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.case_path(str(case["case_id"])),
            canonical_json({
                "contract_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
                "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
                "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
                "base_classification_fingerprint": LIT02_ACCEPTED_V1_CLASSIFICATION_FINGERPRINT,
                "base_diagnostic_fingerprint": LIT02_ACCEPTED_DIAGNOSTIC_FINGERPRINT,
                "case_id": case["case_id"],
                "case_input_fingerprint": _fingerprint(dict(case)),
                "result": dict(result),
                "economic_outcome_values_read": 0,
                "new_price_or_return_provider_reads": 0,
                "protected_return_rows_read": 0,
                "protected_holdout_consumed": False,
            }) + "\n",
        )

    def _sec_candidate_filings_v2(self, *, cik: str, endpoint_session: date) -> tuple[list[dict[str, object]], str]:
        start_date = endpoint_session - timedelta(days=LIT02_REPAIR_V2_SEC_LOOKBACK_DAYS)
        end_date = endpoint_session + timedelta(days=LIT02_REPAIR_V2_SEC_FORWARD_DAYS)
        root_url = sec_company_submissions_url(cik=cik)
        try:
            payload, root_text = self._sec_get_json(root_url)
        except ProviderError as exc:
            if "404" in str(exc):
                return [], "SEC_COMPANY_SUBMISSIONS_NOT_FOUND"
            raise
        rows = _submission_rows(payload)
        shard_urls = _declared_shard_urls(payload, start_date=start_date, end_date=end_date)
        if len(shard_urls) > SEC_EDGAR_MAX_ARCHIVE_SHARDS_PER_LOOKUP:
            raise RuntimeError("LIT-02 repair-v2 SEC declared-shard bound changed")
        for shard_url in shard_urls:
            shard_payload, _ = self._sec_get_json(shard_url)
            rows.extend(_submission_rows(shard_payload))
        return (
            _filtered_sec_rows_v2(rows, start_date=start_date, end_date=end_date),
            hashlib.sha256(root_text.encode("utf-8")).hexdigest(),
        )

    def _sec_resolution_v2(
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
            filings, submissions_sha = self._sec_candidate_filings_v2(cik=cik, endpoint_session=endpoint_session)
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
            ticker_candidate = parse_explicit_sec_ticker_change_v2(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            terminal_candidate = parse_sec_terminal_transaction_v2(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            evidence_rows.append({
                **filing,
                "submission_source_url": document.source_url,
                "submission_source_sha256": document.source_sha256,
                "company_submissions_sha256": submissions_sha,
                "ticker_change_candidate": ticker_candidate,
                "terminal_candidate": terminal_candidate,
            })
            for candidate in (ticker_candidate, terminal_candidate):
                if not isinstance(candidate, Mapping):
                    continue
                status = str(candidate.get("status") or "")
                if status == "READY":
                    ready_candidates.append({
                        **dict(candidate),
                        "source_url": document.source_url,
                        "source_sha256": document.source_sha256,
                        "accession_number": accession,
                        "filing_date": filing["filing_date"],
                        "form": filing["form"],
                    })
                elif status in {"INCOMPLETE", "CONFLICT"}:
                    incomplete_reasons.append(str(candidate.get("reason") or status))

        candidate, conflict = _select_latest_ready(ready_candidates)
        if conflict:
            return None, evidence_rows, [conflict]
        if candidate is None:
            return None, evidence_rows, sorted(set(incomplete_reasons or ["NO_ADMISSIBLE_OFFICIAL_SEC_EVIDENCE_V2"]))

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
        elif path_id in {"TERMINAL_STOCK", "TERMINAL_MIXED"}:
            successor_ticker = str(candidate.get("successor_ticker") or "")
            if not successor_ticker:
                return None, evidence_rows, ["SUCCESSOR_TICKER_IDENTITY_REQUIRED"]
            overview = self._massive_overview(successor_ticker, endpoint_session)
            if overview is None:
                return None, evidence_rows, ["SUCCESSOR_TICKER_OVERVIEW_NOT_FOUND"]
            candidate["successor_identity"] = {
                "ticker": successor_ticker,
                "composite_figi": str(overview.get("composite_figi") or "").strip().upper() or None,
                "cik": _normalize_cik(overview.get("cik")),
                "primary_exchange": overview.get("primary_exchange"),
                "security_type": overview.get("type"),
            }
        return candidate, evidence_rows, []

    def _retry_instrument(
        self,
        *,
        v1_instrument: Mapping[str, object],
        endpoint_session: date,
        historical_ticker: str,
    ) -> dict[str, object]:
        if v1_instrument.get("resolution_status") == "RESOLVED":
            return dict(v1_instrument)
        identity = v1_instrument.get("identity")
        if not isinstance(identity, Mapping):
            return dict(v1_instrument)
        sec_candidate, sec_evidence, sec_reasons = self._sec_resolution_v2(
            identity=identity,
            endpoint_session=endpoint_session,
            historical_ticker=historical_ticker,
        )
        if sec_candidate is not None:
            return {
                "instrument_id": v1_instrument.get("instrument_id"),
                "identity": dict(identity),
                "resolution_status": "RESOLVED",
                "path_id": sec_candidate.get("path_id"),
                "classification": sec_candidate,
                "unresolved_reasons": [],
                "massive_evidence": v1_instrument.get("massive_evidence"),
                "sec_evidence": sec_evidence,
                "repair_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
            }
        persistent: set[str] = set()
        prior = {str(value) for value in (v1_instrument.get("unresolved_reasons") or []) if str(value)}
        for reason in (
            "COMPOSITE_FIGI_UNAVAILABLE",
            "MASSIVE_TICKER_EVENTS_NOT_FOUND",
            "MULTIPLE_COMPOSITE_FIGIS",
            "MULTIPLE_CIKS",
        ):
            if reason in prior:
                persistent.add(reason)
        persistent.update(sec_reasons)
        return {
            "instrument_id": v1_instrument.get("instrument_id"),
            "identity": dict(identity),
            "resolution_status": "UNRESOLVED",
            "path_id": None,
            "classification": None,
            "unresolved_reasons": sorted(persistent or {"SOURCE_UNRESOLVED_V2"}),
            "massive_evidence": v1_instrument.get("massive_evidence"),
            "sec_evidence": sec_evidence,
            "repair_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
        }

    def run(self, *, force: bool = False) -> dict[str, object]:
        cases, _ = self._load_and_require_plan()
        identity_fingerprint = self._require_v1_state()
        results: list[dict[str, object]] = []
        cached_cases = 0
        retried_cases = 0
        reused_v1_resolved = 0
        started = time.monotonic()
        total = len(cases)
        print(
            "[LIT-02][REPAIR-V2] started | "
            f"cases={total} | base_resolved={LIT02_ACCEPTED_V1_RESOLVED} | "
            f"base_unresolved={LIT02_ACCEPTED_V1_UNRESOLVED} | "
            f"lookback={LIT02_REPAIR_V2_SEC_LOOKBACK_DAYS}d | forms={sorted(LIT02_REPAIR_V2_SEC_ALLOWED_FORMS)}"
        )
        print(
            "[LIT-02][REPAIR-V2] economic outcomes disabled | protected reads disabled | "
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
                v1_result = self._load_v1_case(case)
                if v1_result.get("resolution_status") == "RESOLVED":
                    result = dict(v1_result)
                    result["source_repair_v2_action"] = "V1_RESOLVED_REUSED"
                    reused_v1_resolved += 1
                    mode = "v1-reuse"
                else:
                    instrument_results = [
                        self._retry_instrument(
                            v1_instrument=dict(item),
                            endpoint_session=endpoint,
                            historical_ticker=ticker,
                        )
                        for item in (v1_result.get("instrument_results") or [])
                        if isinstance(item, Mapping)
                    ]
                    result = self._aggregate_case(case, instrument_results)
                    result["source_repair_v2_action"] = "V1_UNRESOLVED_RETRIED_WITH_V2"
                    retried_cases += 1
                    mode = "repair-v2"
                self._write_case(case, result)
            results.append(result)

            elapsed = time.monotonic() - started
            rate = index / elapsed if elapsed > 0 else 0.0
            remaining = (total - index) / rate if rate > 0 else 0.0
            print(
                f"[LIT-02][REPAIR-V2] case {index}/{total} {(index / total) * 100.0:.1f}% "
                f"| elapsed={elapsed:.1f}s ETA={remaining:.1f}s | {endpoint} {ticker} "
                f"| mode={mode} | status={result.get('resolution_status')} "
                f"| path={result.get('path_id') or 'SOURCE_UNRESOLVED'} | provider_reads={self.provider_reads}"
            )

        total_resolved = sum(1 for item in results if item.get("resolution_status") == "RESOLVED")
        path_counts = Counter(str(item.get("path_id") or "SOURCE_UNRESOLVED") for item in results)
        reason_counts = Counter()
        for item in results:
            if item.get("resolution_status") == "RESOLVED":
                continue
            for reason in item.get("unresolved_reasons") or []:
                reason_counts[str(reason)] += 1
        coverage = total_resolved / total if total else 0.0
        ready = total > 0 and coverage >= LIT02_REQUIRED_SOURCE_COVERAGE
        classification_fingerprint = _fingerprint(sorted(({
            "case_id": item.get("case_id"),
            "resolution_status": item.get("resolution_status"),
            "path_id": item.get("path_id"),
            "classification": item.get("classification"),
            "unresolved_reasons": item.get("unresolved_reasons"),
        } for item in results), key=lambda item: str(item.get("case_id") or "")))
        report: dict[str, object] = {
            "status": LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_READY if ready else LIT02_SOURCE_METADATA_REPAIR_V2_STATUS_INCOMPLETE,
            "contract_version": LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
            "source_policy_fingerprint": LIT02_ACCEPTED_SOURCE_POLICY_FINGERPRINT,
            "feasibility_plan_fingerprint": LIT02_ACCEPTED_FEASIBILITY_PLAN_FINGERPRINT,
            "base_classification_fingerprint": LIT02_ACCEPTED_V1_CLASSIFICATION_FINGERPRINT,
            "base_source_report_fingerprint": LIT02_ACCEPTED_V1_REPORT_FINGERPRINT,
            "base_diagnostic_fingerprint": LIT02_ACCEPTED_DIAGNOSTIC_FINGERPRINT,
            "identity_evidence_fingerprint": identity_fingerprint,
            "feasibility_cases": total,
            "base_resolved_cases": LIT02_ACCEPTED_V1_RESOLVED,
            "base_unresolved_cases": LIT02_ACCEPTED_V1_UNRESOLVED,
            "resolved_cases": total_resolved,
            "unresolved_cases": total - total_resolved,
            "newly_resolved_cases": total_resolved - LIT02_ACCEPTED_V1_RESOLVED,
            "source_coverage": coverage,
            "required_source_coverage": LIT02_REQUIRED_SOURCE_COVERAGE,
            "path_counts": dict(sorted(path_counts.items())),
            "unresolved_reason_counts": dict(sorted(reason_counts.items())),
            "classification_fingerprint": classification_fingerprint,
            "repair_v2_sec_lookback_days": LIT02_REPAIR_V2_SEC_LOOKBACK_DAYS,
            "repair_v2_sec_forward_days": LIT02_REPAIR_V2_SEC_FORWARD_DAYS,
            "repair_v2_sec_allowed_forms": sorted(LIT02_REPAIR_V2_SEC_ALLOWED_FORMS),
            "source_metadata_provider_reads": self.provider_reads,
            "massive_source_metadata_reads": self._massive_reads,
            "sec_source_metadata_reads": self._sec_reads,
            "cached_case_manifests_reused": cached_cases,
            "v1_resolved_cases_reused": reused_v1_resolved,
            "v1_unresolved_cases_retried": retried_cases,
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
                "If exact-head source coverage is 100%, freeze a fresh/non-reused LIT-02 economic-development design before any economic outcome read."
                if ready
                else "Diagnose remaining source-unresolved cases; do not weaken the 100% source gate or read price/return outcomes."
            ),
        }
        report["report_fingerprint"] = _report_fingerprint(report)
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path(), canonical_json(report) + "\n")
        output = dict(report)
        output["report_path"] = str(self.report_path())
        return output
