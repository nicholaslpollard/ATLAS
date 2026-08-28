from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from packages.core.exceptions import ProviderError

from .rest import MassiveRESTClient


PHASE32_SEC_INDEX_ENDPOINT = "/stocks/filings/vX/index"
PHASE32_SEC_INDEX_FORM_TYPE = "8-K"
PHASE32_SEC_INDEX_SORT = "filing_date.asc"
PHASE32_SEC_INDEX_PAGE_LIMIT = 10000
PHASE32_ALLOWED_FILING_HOSTS = {"www.sec.gov", "sec.gov"}


@dataclass(frozen=True, slots=True)
class Phase32SECIndexWindowResult:
    rows: tuple[dict[str, Any], ...]
    page_count: int
    request_ids: tuple[str, ...]


def parse_index_date(value: object, *, field: str) -> date:
    if not isinstance(value, str) or not value.strip():
        raise ProviderError(f"Massive SEC index row is missing {field}")
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise ProviderError(f"Massive SEC index {field} is not YYYY-MM-DD: {value!r}") from exc


def _nonblank_text(value: object, *, field: str) -> str:
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str) or not value.strip():
        raise ProviderError(f"Massive SEC index row is missing {field}")
    return value.strip()


def validate_sec_index_row(item: dict[str, Any], *, start_date: date, end_date: date) -> None:
    accession = _nonblank_text(item.get("accession_number"), field="accession_number")
    _nonblank_text(item.get("cik"), field="cik")
    filing_date = parse_index_date(item.get("filing_date"), field="filing_date")
    if filing_date < start_date or filing_date > end_date:
        raise ProviderError(
            f"Massive SEC index row {accession!r} filing_date is outside the requested window"
        )
    if item.get("form_type") != PHASE32_SEC_INDEX_FORM_TYPE:
        raise ProviderError(
            f"Phase32 requested original 8-K only but received {item.get('form_type')!r}"
        )

    filing_url = _nonblank_text(item.get("filing_url"), field="filing_url")
    parts = urlsplit(filing_url)
    if parts.scheme.lower() != "https" or parts.netloc.lower() not in PHASE32_ALLOWED_FILING_HOSTS:
        raise ProviderError(
            f"Massive SEC index row {accession!r} has non-SEC filing_url"
        )

    ticker = item.get("ticker")
    if ticker is not None and (not isinstance(ticker, str) or not ticker.strip()):
        raise ProviderError(
            f"Massive SEC index row {accession!r} has invalid provider-native ticker"
        )


def _canonical_row(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sort_key(item: dict[str, Any]) -> tuple[object, ...]:
    return (
        parse_index_date(item["filing_date"], field="filing_date"),
        str(item.get("accession_number") or ""),
        str(item.get("cik") or ""),
        str(item.get("ticker") or ""),
        _canonical_row(item),
    )


class MassivePhase32SECIndexClient:
    """Read-only Massive SEC EDGAR index adapter for Phase32 feasibility."""

    def __init__(self, rest: MassiveRESTClient) -> None:
        self.rest = rest

    def eight_k_window(
        self, *, start_date: date, end_date: date
    ) -> Phase32SECIndexWindowResult:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        params = {
            "filing_date.gte": start_date.isoformat(),
            "filing_date.lte": end_date.isoformat(),
            "form_type": PHASE32_SEC_INDEX_FORM_TYPE,
            "limit": PHASE32_SEC_INDEX_PAGE_LIMIT,
            "sort": PHASE32_SEC_INDEX_SORT,
        }
        rows: list[dict[str, Any]] = []
        request_ids: list[str] = []
        pages = 0
        for page in self.rest.iter_pages(PHASE32_SEC_INDEX_ENDPOINT, params):
            pages += 1
            request_id = page.get("request_id")
            if request_id is not None:
                if not isinstance(request_id, str) or not request_id.strip():
                    raise ProviderError("Massive SEC index request_id must be nonblank when present")
                request_ids.append(request_id)
            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive SEC index response results must be a list")
            for raw in results:
                if not isinstance(raw, dict):
                    raise ProviderError("Massive SEC index result must be an object")
                item = dict(raw)
                validate_sec_index_row(item, start_date=start_date, end_date=end_date)
                rows.append(item)
        return Phase32SECIndexWindowResult(
            rows=tuple(sorted(rows, key=_sort_key)),
            page_count=pages,
            request_ids=tuple(request_ids),
        )
