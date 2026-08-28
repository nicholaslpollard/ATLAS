from __future__ import annotations

from datetime import date

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.massive.phase31 import (
    PHASE31_FORM4_ENDPOINT,
    PHASE31_FORM4_FORM_TYPE,
    PHASE31_FORM4_PAGE_LIMIT,
    PHASE31_FORM4_SORT,
    MassivePhase31Form4Client,
)


def _row(*, filing_date: str, accession: str, ticker: str, code: str = "P") -> dict[str, object]:
    return {
        "accession_number": accession,
        "form_type": "4",
        "filing_date": filing_date,
        "issuer_cik": "0000000001",
        "owner_cik": "0000000002",
        "record_type": "transaction",
        "tickers": [ticker],
        "transaction_code": code,
        "transaction_date": filing_date,
        "transaction_shares": 100,
        "transaction_price_per_share": 10.0,
        "transaction_value": 1000.0,
    }


class FakeRest:
    def __init__(self, pages: list[dict[str, object]]) -> None:
        self.pages = pages
        self.path: str | None = None
        self.params: dict[str, object] | None = None

    def iter_pages(self, path: str, params: dict[str, object]):
        self.path = path
        self.params = dict(params)
        yield from self.pages


def test_form4_client_uses_frozen_query_contract_and_preserves_ticker_case() -> None:
    rest = FakeRest(
        [
            {
                "request_id": "req-1",
                "results": [
                    _row(filing_date="2023-08-15", accession="b", ticker="brk.b", code="S"),
                    _row(filing_date="2023-08-14", accession="a", ticker="BrK.B", code="P"),
                ],
            }
        ]
    )
    client = MassivePhase31Form4Client(rest)  # type: ignore[arg-type]
    result = client.form4_window(
        start_date=date(2023, 8, 14),
        end_date=date(2023, 8, 18),
    )

    assert rest.path == PHASE31_FORM4_ENDPOINT
    assert rest.params == {
        "filing_date.gte": "2023-08-14",
        "filing_date.lte": "2023-08-18",
        "form_type": PHASE31_FORM4_FORM_TYPE,
        "limit": PHASE31_FORM4_PAGE_LIMIT,
        "sort": PHASE31_FORM4_SORT,
    }
    assert [row["accession_number"] for row in result.rows] == ["a", "b"]
    assert [row["tickers"] for row in result.rows] == [["BrK.B"], ["brk.b"]]
    assert result.page_count == 1
    assert result.request_ids == ("req-1",)


def test_form4_client_rejects_amendment_when_original_form_requested() -> None:
    row = _row(filing_date="2023-08-14", accession="a", ticker="AAPL")
    row["form_type"] = "4/A"
    client = MassivePhase31Form4Client(FakeRest([{"results": [row]}]))  # type: ignore[arg-type]
    with pytest.raises(ProviderError, match="original Form 4 only"):
        client.form4_window(start_date=date(2023, 8, 14), end_date=date(2023, 8, 18))


def test_form4_client_rejects_out_of_window_filing_date() -> None:
    client = MassivePhase31Form4Client(
        FakeRest([{"results": [_row(filing_date="2023-08-19", accession="a", ticker="AAPL")]}])
    )  # type: ignore[arg-type]
    with pytest.raises(ProviderError, match="outside the requested window"):
        client.form4_window(start_date=date(2023, 8, 14), end_date=date(2023, 8, 18))
