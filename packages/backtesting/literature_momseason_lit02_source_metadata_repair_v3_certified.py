from __future__ import annotations

import re
from datetime import date
from typing import Mapping

from .literature_momseason_lit02_source_metadata import _fingerprint, _normalize_cik, _plain_sec_text
from .literature_momseason_lit02_source_metadata_repair_v2 import _candidate_core, _select_latest_ready
from .literature_momseason_lit02_source_metadata_repair_v2_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
    _execution_contexts_certified,
    parse_explicit_sec_ticker_change_v2_certified,
    parse_sec_terminal_transaction_v2_certified,
)
from .literature_momseason_lit02_source_metadata_repair_v3 import (
    LIT02_REPAIR_V3_SEC_ALLOWED_FORMS,
    LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
    MomSeasonLIT02SourceMetadataRepairV3,
    lit02_repair_v3_source_expansion_fingerprint,
)


LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION = (
    "lit02-source-metadata-repair-v3-parser-certified-v2-context-plus-explicit-defined-term-v1"
)

_TERM_TOKEN = (
    r"(?:Per\s+Share\s+Merger\s+Consideration|Merger\s+Consideration|"
    r"Offer\s+Price|Cash\s+Consideration)"
)
_TERM_REFERENCE = re.compile(
    rf"(?is:\b(?:converted|cancelled|canceled)\b.{{0,700}}?"
    rf"\bright\s+to\s+receive\b.{{0,180}}?(?:the\s+)?"
    rf"(?P<term>{_TERM_TOKEN})\b)"
)
_TERM_DEFINITION_AFTER_VALUE = re.compile(
    rf"(?is:\$\s*(?P<value>\d+(?:\.\d+)?)\b.{{0,100}}?"
    rf"\bper\s+(?:common\s+)?share\b.{{0,220}}?"
    rf"(?:the\s+)?[\"'“”]?(?P<term>{_TERM_TOKEN})[\"'“”]?)"
)
_TERM_DEFINITION_BEFORE_VALUE = re.compile(
    rf"(?is:\b(?P<term>{_TERM_TOKEN})\b.{{0,180}}?"
    rf"\$\s*(?P<value>\d+(?:\.\d+)?)\b.{{0,120}}?"
    rf"\bper\s+(?:common\s+)?share\b)"
)
_CONTINGENT_RE = re.compile(r"(?is:\b(?:CVR|contingent\s+value\s+right)\b)")


def _normalize_term(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).upper()


def _defined_cash_terms(plain: str) -> dict[str, list[dict[str, object]]]:
    definitions: dict[str, list[dict[str, object]]] = {}
    seen: set[tuple[str, float, str]] = set()
    for pattern in (_TERM_DEFINITION_AFTER_VALUE, _TERM_DEFINITION_BEFORE_VALUE):
        for match in pattern.finditer(plain):
            try:
                value = float(match.group("value"))
            except (TypeError, ValueError):
                continue
            if value <= 0.0:
                continue
            term = _normalize_term(match.group("term"))
            start = max(0, match.start() - 220)
            end = min(len(plain), match.end() + 220)
            excerpt = plain[start:end]
            key = (term, value, _fingerprint(excerpt))
            if key in seen:
                continue
            seen.add(key)
            definitions.setdefault(term, []).append(
                {
                    "value": value,
                    "excerpt": excerpt[:1400],
                    "contingent": bool(_CONTINGENT_RE.search(excerpt)),
                }
            )
    return definitions


def parse_sec_final_transaction_amendment_v3_certified(
    text: str,
    *,
    form: str,
    endpoint_session: date,
    historical_ticker: str,
) -> dict[str, object] | None:
    """Resolve only explicit executed-event defined cash terms in admitted v3 SEC forms."""

    base = parse_sec_terminal_transaction_v2_certified(
        text,
        endpoint_session=endpoint_session,
        historical_ticker=historical_ticker,
    )
    if isinstance(base, Mapping) and base.get("status") == "READY":
        result = dict(base)
        result["repair_v3_parser_certification"] = (
            LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
        )
        result["repair_v3_resolution_rule"] = "V2_CERTIFIED_CONTEXT_DIRECT_VALUE"
        return result

    if form not in LIT02_REPAIR_V3_SEC_ALLOWED_FORMS:
        return dict(base) if isinstance(base, Mapping) else None

    plain = _plain_sec_text(text)
    definitions = _defined_cash_terms(plain)
    if not definitions:
        return dict(base) if isinstance(base, Mapping) else None

    ready: dict[str, dict[str, object]] = {}
    conflicts: list[dict[str, object]] = []
    for effective, context in _execution_contexts_certified(plain, endpoint_session):
        references = {
            _normalize_term(match.group("term"))
            for match in _TERM_REFERENCE.finditer(context)
        }
        for term in sorted(references):
            rows = definitions.get(term) or []
            if not rows:
                continue
            values = sorted({float(row["value"]) for row in rows})
            if len(values) != 1:
                conflicts.append(
                    {
                        "reason": "MULTIPLE_DEFINED_TERMINAL_CASH_VALUES_V3",
                        "defined_term": term,
                        "cash_values": values,
                        "effective_date": effective.isoformat(),
                    }
                )
                continue
            if any(bool(row.get("contingent")) for row in rows):
                conflicts.append(
                    {
                        "reason": "CONTINGENT_CONSIDERATION_NOT_SUPPORTED_V3",
                        "defined_term": term,
                        "cash_values": values,
                        "effective_date": effective.isoformat(),
                    }
                )
                continue
            candidate: dict[str, object] = {
                "status": "READY",
                "path_id": "TERMINAL_CASH",
                "effective_date": effective.isoformat(),
                "cash_per_share": values[0],
                "defined_term": term,
                "matched_excerpt": context[:2600],
                "definition_excerpts": [str(row["excerpt"]) for row in rows[:4]],
                "evidence_rule": "OFFICIAL_SEC_EXECUTED_EVENT_EXPLICIT_DEFINED_CASH_TERM_V3",
                "parser_version": LIT02_SOURCE_METADATA_REPAIR_V3_CONTRACT,
                "base_parser_certification": LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION,
                "repair_v3_parser_certification": (
                    LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
                ),
                "repair_v3_resolution_rule": "EXPLICIT_EXECUTED_CONTEXT_TO_EXPLICIT_DEFINED_TERM",
            }
            ready[_fingerprint(_candidate_core(candidate))] = candidate

    if ready:
        candidates = list(ready.values())
        latest_date = max(date.fromisoformat(str(item["effective_date"])) for item in candidates)
        latest = [
            item
            for item in candidates
            if date.fromisoformat(str(item["effective_date"])) == latest_date
        ]
        unique = {_fingerprint(_candidate_core(item)): item for item in latest}
        if len(unique) == 1:
            return next(iter(unique.values()))
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_DEFINED_TERM_TERMINAL_CLASSIFICATIONS_V3",
            "effective_date": latest_date.isoformat(),
            "candidates": [_candidate_core(item) for item in unique.values()],
            "repair_v3_parser_certification": (
                LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
            ),
        }

    if conflicts:
        reasons = sorted({str(item["reason"]) for item in conflicts})
        if len(reasons) == 1:
            result = dict(conflicts[0])
            result["status"] = (
                "CONFLICT" if reasons[0].startswith("MULTIPLE_") else "INCOMPLETE"
            )
            result["repair_v3_parser_certification"] = (
                LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
            )
            return result
        return {
            "status": "CONFLICT",
            "reason": "MULTIPLE_DEFINED_TERM_CONFLICTS_V3",
            "reasons": reasons,
            "repair_v3_parser_certification": (
                LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
            ),
        }

    return dict(base) if isinstance(base, Mapping) else None


class MomSeasonLIT02SourceMetadataRepairV3Certified(MomSeasonLIT02SourceMetadataRepairV3):
    """Repair-v3 using the certified v2 parser plus explicit defined-term linkage."""

    def _sec_resolution_v3(
        self,
        *,
        identity: Mapping[str, object],
        endpoint_session: date,
        historical_ticker: str,
    ) -> tuple[dict[str, object] | None, list[dict[str, object]], list[str]]:
        cik = str(identity.get("cik") or "").strip()
        if not cik:
            return None, [], ["CIK_UNAVAILABLE_FOR_SEC_FINAL_TRANSACTION_SOURCE"]
        try:
            filings, submissions_sha = self._sec_candidate_filings_v3(
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
            terminal_candidate = parse_sec_final_transaction_amendment_v3_certified(
                document.text,
                form=str(filing["form"]),
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
                    "source_expansion_fingerprint": (
                        lit02_repair_v3_source_expansion_fingerprint()
                    ),
                    "base_parser_certification": (
                        LIT02_SOURCE_METADATA_REPAIR_V2_PARSER_CERTIFICATION
                    ),
                    "repair_v3_parser_certification": (
                        LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
                    ),
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
                            "source_expansion_fingerprint": (
                                lit02_repair_v3_source_expansion_fingerprint()
                            ),
                        }
                    )
                elif status in {"INCOMPLETE", "CONFLICT"}:
                    incomplete_reasons.append(str(candidate.get("reason") or status))

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
                        or [
                            "NO_ADMISSIBLE_OFFICIAL_SEC_FINAL_TRANSACTION_AMENDMENT_EVIDENCE_V3"
                        ]
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
        candidate["repair_v3_parser_certification"] = (
            LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
        )
        return candidate, evidence_rows, []
