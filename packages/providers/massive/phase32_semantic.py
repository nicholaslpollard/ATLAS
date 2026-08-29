from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.parse import urlsplit

from packages.core.exceptions import ProviderError

from .rest import MassiveRESTClient


PHASE32_DISCLOSURES_ENDPOINT = "/stocks/filings/8-K/vX/disclosures"
PHASE32_DISCLOSURES_PAGE_LIMIT = 1000
PHASE32_DISCLOSURES_SORT = "filing_date.asc"
PHASE32_TEXT_ENDPOINT = "/stocks/filings/8-K/vX/text"
PHASE32_TEXT_PAGE_LIMIT = 100
PHASE32_TEXT_SORT = "filing_date.asc"
PHASE32_TAXONOMY_ENDPOINT = "/stocks/taxonomies/vX/disclosures"
PHASE32_TAXONOMY_PAGE_LIMIT = 1000
PHASE32_TAXONOMY_SORT = "taxonomy.asc"
PHASE32_ALLOWED_FILING_HOSTS = {"www.sec.gov", "sec.gov"}


@dataclass(frozen=True, slots=True)
class Phase32DisclosureWindowResult:
    rows: tuple[dict[str, Any], ...]
    page_count: int
    request_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Phase32TaxonomyResult:
    rows: tuple[dict[str, Any], ...]
    page_count: int
    request_ids: tuple[str, ...]


def _nonblank_text(value: object, *, field: str) -> str:
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str) or not value.strip():
        raise ProviderError(f"Massive Phase32 semantic row is missing {field}")
    return value.strip()


def _parse_date(value: object, *, field: str) -> date:
    text = _nonblank_text(value, field=field)
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ProviderError(f"Massive Phase32 semantic {field} is not YYYY-MM-DD: {value!r}") from exc


def _validate_sec_url(value: object, *, field: str) -> str:
    text = _nonblank_text(value, field=field)
    parts = urlsplit(text)
    if parts.scheme.lower() != "https" or parts.netloc.lower() not in PHASE32_ALLOWED_FILING_HOSTS:
        raise ProviderError(f"Massive Phase32 semantic row has non-SEC {field}")
    return text


def _canonical_row(item: dict[str, Any]) -> str:
    return json.dumps(item, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _request_id(page: dict[str, Any]) -> str | None:
    value = page.get("request_id")
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ProviderError("Massive Phase32 semantic request_id must be nonblank when present")
    return value.strip()


def validate_disclosure_row(item: dict[str, Any], *, start_date: date, end_date: date) -> None:
    accession = _nonblank_text(item.get("accession_number"), field="accession_number")
    _nonblank_text(item.get("cik"), field="cik")
    filing_date = _parse_date(item.get("filing_date"), field="filing_date")
    if filing_date < start_date or filing_date > end_date:
        raise ProviderError(
            f"Massive 8-K disclosure row {accession!r} filing_date is outside the requested window"
        )
    _validate_sec_url(item.get("filing_url"), field="filing_url")
    _nonblank_text(item.get("primary_category"), field="primary_category")
    _nonblank_text(item.get("secondary_category"), field="secondary_category")
    _nonblank_text(item.get("tertiary_category"), field="tertiary_category")
    _nonblank_text(item.get("supporting_text"), field="supporting_text")
    tickers = item.get("tickers")
    if tickers is None:
        return
    if not isinstance(tickers, list):
        raise ProviderError(f"Massive 8-K disclosure row {accession!r} tickers must be a list")
    for ticker in tickers:
        if not isinstance(ticker, str) or not ticker.strip():
            raise ProviderError(
                f"Massive 8-K disclosure row {accession!r} contains an invalid ticker"
            )


def validate_text_row(item: dict[str, Any], *, filing_date: date) -> None:
    accession = _nonblank_text(item.get("accession_number"), field="accession_number")
    _nonblank_text(item.get("cik"), field="cik")
    row_date = _parse_date(item.get("filing_date"), field="filing_date")
    if row_date != filing_date:
        raise ProviderError(
            f"Massive 8-K text row {accession!r} filing_date differs from requested date"
        )
    if item.get("form_type") != "8-K":
        raise ProviderError(
            f"Phase32 semantic source requested original 8-K only but received {item.get('form_type')!r}"
        )
    _validate_sec_url(item.get("filing_url"), field="filing_url")
    _nonblank_text(item.get("items_text"), field="items_text")
    ticker = item.get("ticker")
    if ticker is not None and (not isinstance(ticker, str) or not ticker.strip()):
        raise ProviderError(f"Massive 8-K text row {accession!r} has invalid ticker")


def validate_taxonomy_row(item: dict[str, Any]) -> None:
    _nonblank_text(item.get("taxonomy"), field="taxonomy")
    _nonblank_text(item.get("primary_category"), field="primary_category")
    _nonblank_text(item.get("secondary_category"), field="secondary_category")
    _nonblank_text(item.get("tertiary_category"), field="tertiary_category")
    description = item.get("description")
    if description is not None and (not isinstance(description, str) or not description.strip()):
        raise ProviderError("Massive disclosure taxonomy description must be nonblank when present")


class MassivePhase32SemanticClient:
    """Read-only Massive 8-K disclosure/text/taxonomy adapter for Phase32 source qualification."""

    def __init__(self, rest: MassiveRESTClient) -> None:
        self.rest = rest

    def disclosures_window(
        self, *, start_date: date, end_date: date
    ) -> Phase32DisclosureWindowResult:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        params = {
            "filing_date.gte": start_date.isoformat(),
            "filing_date.lte": end_date.isoformat(),
            "limit": PHASE32_DISCLOSURES_PAGE_LIMIT,
            "sort": PHASE32_DISCLOSURES_SORT,
        }
        rows: list[dict[str, Any]] = []
        request_ids: list[str] = []
        pages = 0
        for page in self.rest.iter_pages(PHASE32_DISCLOSURES_ENDPOINT, params):
            pages += 1
            request_id = _request_id(page)
            if request_id:
                request_ids.append(request_id)
            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive 8-K disclosures response results must be a list")
            for raw in results:
                if not isinstance(raw, dict):
                    raise ProviderError("Massive 8-K disclosure result must be an object")
                item = dict(raw)
                validate_disclosure_row(item, start_date=start_date, end_date=end_date)
                rows.append(item)
        rows.sort(
            key=lambda item: (
                str(item.get("filing_date") or ""),
                str(item.get("accession_number") or ""),
                str(item.get("primary_category") or ""),
                str(item.get("secondary_category") or ""),
                str(item.get("tertiary_category") or ""),
                _canonical_row(item),
            )
        )
        return Phase32DisclosureWindowResult(
            rows=tuple(rows), page_count=pages, request_ids=tuple(request_ids)
        )

    def eight_k_text(
        self, *, cik: object, filing_date: date
    ) -> tuple[dict[str, Any], ...]:
        cik_text = _nonblank_text(cik, field="cik")
        if not cik_text.isdigit():
            raise ProviderError(f"Massive 8-K text CIK must be numeric: {cik_text!r}")
        params = {
            "cik": cik_text.zfill(10),
            "filing_date": filing_date.isoformat(),
            "form_type": "8-K",
            "limit": PHASE32_TEXT_PAGE_LIMIT,
            "sort": PHASE32_TEXT_SORT,
        }
        rows: list[dict[str, Any]] = []
        for page in self.rest.iter_pages(PHASE32_TEXT_ENDPOINT, params):
            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive 8-K text response results must be a list")
            for raw in results:
                if not isinstance(raw, dict):
                    raise ProviderError("Massive 8-K text result must be an object")
                item = dict(raw)
                validate_text_row(item, filing_date=filing_date)
                rows.append(item)
        rows.sort(
            key=lambda item: (
                str(item.get("accession_number") or ""),
                str(item.get("ticker") or ""),
                _canonical_row(item),
            )
        )
        return tuple(rows)

    def taxonomy(self) -> Phase32TaxonomyResult:
        params = {
            "limit": PHASE32_TAXONOMY_PAGE_LIMIT,
            "sort": PHASE32_TAXONOMY_SORT,
        }
        rows: list[dict[str, Any]] = []
        request_ids: list[str] = []
        pages = 0
        for page in self.rest.iter_pages(PHASE32_TAXONOMY_ENDPOINT, params):
            pages += 1
            request_id = _request_id(page)
            if request_id:
                request_ids.append(request_id)
            results = page.get("results") or []
            if not isinstance(results, list):
                raise ProviderError("Massive disclosure taxonomy response results must be a list")
            for raw in results:
                if not isinstance(raw, dict):
                    raise ProviderError("Massive disclosure taxonomy result must be an object")
                item = dict(raw)
                validate_taxonomy_row(item)
                rows.append(item)
        rows.sort(
            key=lambda item: (
                str(item.get("taxonomy") or ""),
                str(item.get("primary_category") or ""),
                str(item.get("secondary_category") or ""),
                str(item.get("tertiary_category") or ""),
                _canonical_row(item),
            )
        )
        return Phase32TaxonomyResult(
            rows=tuple(rows), page_count=pages, request_ids=tuple(request_ids)
        )
