from __future__ import annotations

import hashlib
import re
from datetime import date
from typing import Mapping

from .literature_momseason_lit02_source_metadata import (
    _fingerprint,
    _normalize_cik,
    _plain_sec_text,
    parse_explicit_sec_ticker_change,
)
from .literature_momseason_lit02_source_metadata_repair_v2 import (
    LIT02_SOURCE_METADATA_REPAIR_V2_CONTRACT,
    _DATE_TOKEN_V2,
    _DIRECT_TICKER_CHANGE,
    _DISTRIBUTION_PATTERN,
    _GENERIC_CASH_PATTERNS,
    _SUCCESSOR_TICKER_PATTERNS_V2,
    _candidate_core,
    _float_values,
    _parse_date_v2,
    _select_latest_ready,
    MomSeasonLIT02SourceMetadataRepairV2,
)


LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION = (
    "lit02-source-metadata-repair-v2-parser-certified-context-forward-window-v1"
)

_EXECUTION_PATTERNS_CERTIFIED = (
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
        rf"(?is:\b(?:closing\s+date|effective\s+date)\b\s*(?:was|is|:)?\s*"
        rf"(?P<date>{_DATE_TOKEN_V2}).{{0,1400}}?"
        rf"\b(?:completed|consummated|closed|merged\s+with\s+and\s+into)\b)"
    ),
)

_STRONG_CASH_PATTERNS_CERTIFIED = (
    re.compile(
        r"(?is:\beach\b.{0,260}?\bshare\b.{0,900}?\bright\s+to\s+receive\b.{0,320}?"
        r"\$\s*(?P<value>\d+(?:\.\d+)?)\b)"
    ),
    re.compile(
        r"(?is:\beach\b.{0,260}?\bshare\b.{0,900}?"
        r"\b(?:converted|cancelled|canceled)\b.{0,520}?"
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

_STRONG_SHARE_PATTERNS_CERTIFIED = (
    re.compile(
        r"(?is:\beach\b.{0,260}?\bshare\b.{0,900}?\bright\s+to\s+receive\b.{0,320}?"
        r"(?P<value>\d+(?:\.\d+)?)\s+(?:shares?|common\s+shares?|ordinary\s+shares?)\b)"
    ),
    re.compile(
        r"(?is:\bexchange\s+ratio\b.{0,120}?\b(?:of|equal\s+to|:)\s*"
        r"(?P<value>\d+(?:\.\d+)?)\b)"
    ),
)

_SCHEDULED_TICKER_CHANGE_CERTIFIED = re.compile(
    rf"(?is:\b(?:commence|begin|start)\s+trading\b.{{0,260}}?"
    rf"\bunder\b.{{0,90}}?\b(?:trading\s+)?symbol\b\s*[\"'“”]?"
    rf"(?P<new>(?-i:[A-Z][A-Z0-9.-]{{0,9}}))[\"'“”]?.{{0,260}}?"
    rf"\b(?:on|effective)\s+(?P<date>{_DATE_TOKEN_V2}).{{0,520}}?"
    rf"\buntil\s+that\s+time\b.{{0,260}}?"
    rf"\b(?:present\s+)?(?:symbol|ticker)\b\s*[\"'“”]?"
    rf"(?P<old>(?-i:[A-Z][A-Z0-9.-]{{0,9}}))[\"'“”]?)"
)


def _cash_values_certified(text: str) -> set[float]:
    strong = _float_values(text, _STRONG_CASH_PATTERNS_CERTIFIED)
    return strong if strong else _float_values(text, _GENERIC_CASH_PATTERNS)


def _share_values_certified(text: str) -> set[float]:
    return _float_values(text, _STRONG_SHARE_PATTERNS_CERTIFIED)


def _successor_tickers_certified(text: str, historical_ticker: str) -> set[str]:
    values: set[str] = set()
    for pattern in _SUCCESSOR_TICKER_PATTERNS_V2:
        for match in pattern.finditer(text):
            ticker = match.group("ticker").strip()
            if ticker and ticker != historical_ticker:
                values.add(ticker)
    return values


def _execution_contexts_certified(
    plain: str,
    endpoint_session: date,
) -> list[tuple[date, str]]:
    contexts: dict[tuple[date, str], str] = {}
    for pattern in _EXECUTION_PATTERNS_CERTIFIED:
        for match in pattern.finditer(plain):
            parsed = _parse_date_v2(match.group("date"))
            if parsed is None or parsed > endpoint_session:
                continue
            # Consideration normally follows the executed-event sentence. Keep only a
            # very small prefix so historical/proposed values earlier in the filing do
            # not leak back into the executed transaction context.
            start = max(0, match.start() - 120)
            end = min(len(plain), match.end() + 3200)
            context = plain[start:end]
            key = (parsed, hashlib.sha256(context.encode("utf-8")).hexdigest()[:16])
            contexts[key] = context
    return [
        (item[0], contexts[item])
        for item in sorted(contexts, key=lambda row: (row[0], row[1]))
    ]


def parse_explicit_sec_ticker_change_v2_certified(
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
        (
            _SCHEDULED_TICKER_CHANGE_CERTIFIED,
            "SEC_SCHEDULED_TICKER_CHANGE_WITH_ENDPOINT_IDENTITY_CONFIRMATION",
        ),
    ):
        for match in pattern.finditer(plain):
            old = match.group("old").strip()
            new = match.group("new").strip()
            effective = _parse_date_v2(match.group("date"))
            if (
                old != historical_ticker
                or old == new
                or effective is None
                or effective > endpoint_session
            ):
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
                {
                    "old_ticker": key[0],
                    "new_ticker": key[1],
                    "effective_date": key[2].isoformat(),
                }
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
        "parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
    }


def parse_sec_terminal_transaction_v2_certified(
    text: str,
    *,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    plain = _plain_sec_text(text)
    contexts = _execution_contexts_certified(plain, endpoint_session)
    global_cash = _cash_values_certified(plain)
    global_shares = _share_values_certified(plain)
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
            "parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
        }

    ready: dict[str, dict[str, object]] = {}
    conflicts: list[dict[str, object]] = []
    context_dates: set[date] = set()
    for effective, context in contexts:
        context_dates.add(effective)
        cash_values = _cash_values_certified(context)
        share_values = _share_values_certified(context)
        distribution_values = {
            float(match.group("value"))
            for match in _DISTRIBUTION_PATTERN.finditer(context)
            if float(match.group("value")) > 0.0
        }
        successor_tickers = _successor_tickers_certified(context, historical_ticker)

        if distribution_values:
            if len(distribution_values) != 1:
                conflicts.append(
                    {
                        "reason": "MULTIPLE_TERMINAL_DISTRIBUTION_VALUES",
                        "values": sorted(distribution_values),
                        "effective_date": effective.isoformat(),
                    }
                )
                continue
            candidate: dict[str, object] = {
                "status": "READY",
                "path_id": "TERMINAL_DISTRIBUTION",
                "effective_date": effective.isoformat(),
                "distribution_per_share": next(iter(distribution_values)),
                "evidence_rule": "CONTEXTUAL_SEC_EXECUTED_TERMINAL_DISTRIBUTION_V2",
            }
        elif cash_values or share_values:
            if len(cash_values) > 1:
                conflicts.append(
                    {
                        "reason": "MULTIPLE_TERMINAL_CASH_VALUES",
                        "cash_values": sorted(cash_values),
                        "effective_date": effective.isoformat(),
                    }
                )
                continue
            if len(share_values) > 1:
                conflicts.append(
                    {
                        "reason": "MULTIPLE_TERMINAL_SHARE_RATIOS",
                        "share_ratios": sorted(share_values),
                        "effective_date": effective.isoformat(),
                    }
                )
                continue
            successor = (
                next(iter(successor_tickers)) if len(successor_tickers) == 1 else None
            )
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
        candidate["parser_certification"] = LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION
        if candidate.get("status") == "READY":
            ready[_fingerprint(_candidate_core(candidate))] = candidate
        else:
            conflicts.append(candidate)

    if ready:
        candidates = list(ready.values())
        latest_date = max(
            date.fromisoformat(str(item["effective_date"])) for item in candidates
        )
        latest = [
            item
            for item in candidates
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
            payload["status"] = (
                "CONFLICT"
                if str(payload.get("reason") or "").startswith("MULTIPLE_")
                else "INCOMPLETE"
            )
            payload["all_event_dates"] = sorted(
                item.isoformat() for item in context_dates
            )
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


class MomSeasonLIT02SourceMetadataRepairV2Certified(MomSeasonLIT02SourceMetadataRepairV2):
    """Repair-v2 with the CI-certified forward contextual parser."""

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
            filings, submissions_sha = self._sec_candidate_filings_v2(
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
            ticker_candidate = parse_explicit_sec_ticker_change_v2_certified(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            terminal_candidate = parse_sec_terminal_transaction_v2_certified(
                document.text,
                endpoint_session=endpoint_session,
                historical_ticker=historical_ticker,
            )
            evidence_rows.append(
                {
                    **filing,
                    "submission_source_url": document.source_url,
                    "submission_source_sha256": document.source_sha256,
                    "company_submissions_sha256": submissions_sha,
                    "ticker_change_candidate": ticker_candidate,
                    "terminal_candidate": terminal_candidate,
                    "parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
                }
            )
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
                            "form": filing["form"],
                        }
                    )
                elif status in {"INCOMPLETE", "CONFLICT"}:
                    incomplete_reasons.append(
                        str(candidate.get("reason") or status)
                    )

        candidate, conflict = _select_latest_ready(ready_candidates)
        if conflict:
            return None, evidence_rows, [conflict]
        if candidate is None:
            return (
                None,
                evidence_rows,
                sorted(
                    set(
                        incomplete_reasons
                        or ["NO_ADMISSIBLE_OFFICIAL_SEC_EVIDENCE_V2"]
                    )
                ),
            )

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
                "composite_figi": (
                    str(overview.get("composite_figi") or "").strip().upper() or None
                ),
                "cik": _normalize_cik(overview.get("cik")),
                "primary_exchange": overview.get("primary_exchange"),
                "security_type": overview.get("type"),
            }
        candidate["parser_certification"] = LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION
        return candidate, evidence_rows, []
