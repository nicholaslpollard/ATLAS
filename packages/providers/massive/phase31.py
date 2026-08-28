from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any

from packages.core.exceptions import ProviderError

from .rest import MassiveRESTClient


PHASE31_FORM4_ENDPOINT = "/stocks/filings/vX/form-4"
PHASE31_FORM4_FORM_TYPE = "4"
PHASE31_FORM4_SORT = "filing_date.asc"
PHASE31_FORM4_PAGE_LIMIT = 10000


@dataclass(frozen=True, slots=True)
class Phase31Form4WindowResult:
    rows: tuple[dict[str, Any], ...]
    page_count: int
    request_ids: tuple[str, ...]


def parse_form4_date(value: object, *, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise ProviderError(f"Massive Form 4 row is missing {field}")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ProviderError(f"Massive Form 4 {field} is not YYYY-MM-DD: {value!r}") from exc


def validate_form4_row(item: dict[str, Any], *, start_date: date, end_date: date) -> None:
    accession = item.get("accession_number")
    if not isinstance(accession, str) or not accession.strip():
        raise ProviderError("Massive Form 4 row is missing a nonblank accession_number")

    filing_date = parse_form4_date(item.get("filing_date"), field="filing_date")
    if filing_date < start_date or filing_date > end_date:
        raise ProviderError(
            f"Massive Form 4 row {accession!r} filing_date is outside the requested window"
        )

    form_type = item.get("form_type")
    if form_type != PHASE31_FORM4_FORM_TYPE:
        raise ProviderError(
            f"Massive Form 4 feasibility requested original Form 4 only but received {form_type!r}"
        )

    for field in ("issuer_cik", "owner_cik", "record_type"):
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ProviderError(f"Massive Form 4 row {accession!r} is missing {field}")

    tickers = item.get("tickers")
    if tickers is not None:
        if not isinstance(tickers, list):
            raise ProviderError(f"Massive Form 4 row {accession!r} tickers must be a list")
        for ticker in tickers:
            if not isinstance(ticker, str) or not ticker.strip():
                raise ProviderError(
                    f"Massive Form 4 row {accession!r} contains an invalid ticker association"
                )

    if item.get("record_type") == "transaction":
        # Preserve provider-native missing/blank transaction_code evidence unchanged.
        # Whether the accession is scientifically admissible is a downstream,
        # outcome-free source-quality decision; the transport layer must not erase
        # the raw row before that classifier can quarantine it fail-closed.
        code = item.get("transaction_code")
        if code is not None and not isinstance(code, str):
            raise ProviderError(
                f"Massive Form 4 transaction row {accession!r} has non-string transaction_code"
            )
        transaction_date = item.get("transaction_date")
        if transaction_date is not None:
            parse_form4_date(transaction_date, field="transaction_date")


def _canonical_row(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_key(item: dict[str, Any]) -> tuple[object, ...]:
    return (
        parse_form4_date(item["filing_date"], field="filing_date"),
        str(item.get("accession_number") or ""),
        str(item.get("owner_cik") or ""),
        str(item.get("record_type") or ""),
        str(item.get("transaction_date") or ""),
        str(item.get("transaction_code") or ""),
        str(item.get("security_title") or ""),
        _canonical_row(item),
    )


class MassivePhase31Form4Client:
    """Read-only Massive Form-4 adapter for Phase31 feasibility/provenance.

    The adapter deliberately exposes no market outcomes, broker/account state, or
    trading authority. Provider-native ticker strings and full raw row objects are
    preserved exactly as returned, including source-quality defects that must be
    classified downstream rather than silently repaired or dropped.
    """

    def __init__(self, rest: MassiveRESTClient) -> None:
        self.rest = rest

    def form4_window(self, *, start_date: date, end_date: date) -> Phase31Form4WindowResult:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")

        params = {
            "filing_date.gte": start_date.isoformat(),
            "filing_date.lte": end_date.isoformat(),
            "form_type": PHASE31_FORM4_FORM_TYPE,
            "limit": PHASE31_FORM4_PAGE_LIMIT,
            "sort": PHASE31_FORM4_SORT,
        }

        rows: list[dict[str, Any]] = []
        request_ids: list[str] = []
        page_count = 0

        for page in self.rest.iter_pages(PHASE31_FORM4_ENDPOINT, params):
            page_count += 1
            request_id = page.get("request_id")
            if request_id is not None:
                if not isinstance(request_id, str) or not request_id.strip():
                    raise ProviderError("Massive Form 4 request_id must be nonblank when present")
                request_ids.append(request_id)

            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive Form 4 response results must be a list")
            for raw in results:
                if not isinstance(raw, dict):
                    raise ProviderError("Massive Form 4 result must be an object")
                item = dict(raw)
                validate_form4_row(item, start_date=start_date, end_date=end_date)
                rows.append(item)

        return Phase31Form4WindowResult(
            rows=tuple(sorted(rows, key=_sort_key)),
            page_count=page_count,
            request_ids=tuple(request_ids),
        )
