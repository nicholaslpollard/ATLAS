from __future__ import annotations

"""Candidate-only ZSL April-2026 actions from the already-proven native ledger.

The 2026-captured Alpaca archival ledger is NOT qualified as complete or
point-in-time. Absence of a record never proves an absence of a split.
"""

from datetime import date
import re
from typing import Any, Iterable

from packages.data.intraday_semantics_audit import _action_symbols

CONTRACT = "atlas-b34-zsl-april-action-candidate-projection-v1-source-only"
SYMBOL = "ZSL"
START = date(2026, 4, 1)
END = date(2026, 4, 30)
EXPECTED_PAGES = 379
EXPECTED_RECORDS = 378362
MAX_RECORDS = 500000
MAX_CANDIDATES = 128
SHA = re.compile(r"^[a-f0-9]{64}$")
EVENT_DATE_FIELDS = ("ex_date", "effective_date", "execution_date")


class ZslActionCandidateError(ValueError):
    pass


def project_archived_candidates(
    records: Iterable[dict[str, Any]], page_hashes: list[str], *,
    expected_records: int = EXPECTED_RECORDS,
) -> dict[str, Any]:
    """Select original dated or undated ZSL candidates, preserving source ordinals."""
    if (len(page_hashes) != EXPECTED_PAGES
            or any(not isinstance(h, str) or not SHA.fullmatch(h)
                   for h in page_hashes)
            or expected_records != EXPECTED_RECORDS):
        raise ZslActionCandidateError("B34_ARCHIVE_SOURCE_RECEIPTS_UNQUALIFIED")

    count, seen, selected = 0, set(), []
    for row in records:
        count += 1
        if count > MAX_RECORDS:
            raise ZslActionCandidateError("ARCHIVE_LEDGER_ROW_CAP_EXCEEDED")
        if not isinstance(row, dict):
            raise ZslActionCandidateError("MALFORMED_ORIGINAL_ACTION_RECORD")
        payload, typ = row.get("payload"), row.get("action_type")
        page, index = row.get("source_page_index"), row.get("source_record_index")
        if (not isinstance(payload, dict) or not isinstance(typ, str) or not typ
                or type(page) is not int or not 0 <= page < len(page_hashes)
                or type(index) is not int or index < 0):
            raise ZslActionCandidateError("MALFORMED_ORIGINAL_ACTION_ORDINAL")
        ordinal = (typ, page, index)
        if ordinal in seen:
            raise ZslActionCandidateError("DUPLICATE_ORIGINAL_ACTION_ORDINAL")
        seen.add(ordinal)
        if SYMBOL not in _action_symbols(payload):
            continue

        dates = []
        for field in EVENT_DATE_FIELDS:
            raw = payload.get(field)
            if raw is not None:
                if not isinstance(raw, str):
                    raise ZslActionCandidateError("MALFORMED_ZSL_EVENT_DATE")
                try:
                    when = date.fromisoformat(raw)
                except ValueError as exc:
                    raise ZslActionCandidateError("MALFORMED_ZSL_EVENT_DATE") from exc
                dates.append(when.isoformat())
        if dates and not any(START <= date.fromisoformat(x) <= END for x in dates):
            continue

        selected.append({
            "action_type": typ,
            "source_page_index": page,
            "source_record_index": index,
            "manifest_recorded_page_sha256": page_hashes[page],
            "recorded_event_dates": dates,
            "effective_date_state": (
                "RECORDED_DATES_NOT_PIT_PROOF" if dates
                else "UNKNOWN_EVENT_DATE"
            ),
            "payload": payload,
            "historically_available_at": None,
            "point_in_time_qualified": False,
            "split_comparability_qualified": False,
        })
        if len(selected) > MAX_CANDIDATES:
            raise ZslActionCandidateError("TOO_MANY_ZSL_CANDIDATES_FOR_BOUNDED_REPORT")
    if count != expected_records:
        raise ZslActionCandidateError("NATIVE_ACTION_LEDGER_COUNT_CHANGED")
    return {
        "contract": CONTRACT,
        "archive_records_checked": count,
        "zsl_candidate_count": len(selected),
        "zsl_split_type_candidates": sum(
            "split" in x["action_type"].lower() for x in selected
        ),
        "zsl_undated_candidates": sum(
            not x["recorded_event_dates"] for x in selected
        ),
        "zsl_action_candidates": selected,
        "archival_zero_action_coverage_proved": False,
        "corporate_action_completeness_qualified": False,
        "historical_publication_revisions_qualified": False,
        "split_comparable_premarket_volume_qualified": False,
        "signal_authority": False,
        "provider_requests": 0,
        "broker_requests": 0,
        "protected_outcomes_opened": 0,
    }
