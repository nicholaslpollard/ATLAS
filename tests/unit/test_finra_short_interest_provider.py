from __future__ import annotations

from io import BytesIO
from urllib.request import Request

import pytest

from packages.core.exceptions import ProviderError
from packages.providers.finra_short_interest import (
    FINRAShortInterestClient,
    finra_short_interest_url,
    is_exchange_listed_short_interest_row,
    parse_finra_short_interest_csv,
)


class _Headers:
    def get(self, key: str, default=None):
        return default


class _Response:
    def __init__(self, text: str) -> None:
        self._stream = BytesIO(text.encode("utf-8"))
        self.headers = _Headers()

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


def test_current_schema_is_parsed_and_exchange_listed() -> None:
    text = (
        "settlementDate,symbolCode,issueName,currentShortPositionQuantity,"
        "previousShortPositionQuantity,averageDailyVolumeQuantity,daysToCoverQuantity,"
        "marketClassCode,issuerServicesGroupExchangeCode,revisionFlag,stockSplitFlag\n"
        "2026-07-31,ABC,ABC Corp,1000,900,250,4.0,NMS,R,,\n"
    )
    parsed = parse_finra_short_interest_csv(
        text,
        expected_settlement_date="2026-07-31",
        source_url=finra_short_interest_url(settlement_date="2026-07-31"),
    )
    assert parsed.delimiter == ","
    assert len(parsed.rows) == 1
    assert parsed.rows[0]["current_short_position"] == 1000
    assert parsed.rows[0]["previous_short_position"] == 900
    assert is_exchange_listed_short_interest_row(parsed.rows[0]) is True


def test_historical_aliases_and_pipe_delimiter_are_supported() -> None:
    text = (
        "settlementDate|issueSymbolIdentifier|issueName|currentShortShareNumber|"
        "previousShortShareNumber|averageShortShareNumber|daysToCoverNumber|"
        "marketCategoryCode|issuerServicesGroupExchangeCode\n"
        "06/30/2022|XYZ|XYZ Inc|1200|1000|300|4|OTC|A\n"
    )
    parsed = parse_finra_short_interest_csv(
        text,
        expected_settlement_date="2022-06-30",
        source_url=finra_short_interest_url(settlement_date="2022-06-30"),
    )
    assert parsed.delimiter == "|"
    assert parsed.rows[0]["settlement_date"] == "2022-06-30"
    assert parsed.rows[0]["symbol"] == "XYZ"
    assert parsed.rows[0]["current_short_position"] == 1200
    assert is_exchange_listed_short_interest_row(parsed.rows[0]) is True


def test_missing_required_semantic_fails_closed() -> None:
    text = (
        "settlementDate,symbolCode,issuerServicesGroupExchangeCode\n"
        "2026-07-31,ABC,R\n"
    )
    with pytest.raises(ProviderError, match="missing required semantics"):
        parse_finra_short_interest_csv(
            text,
            expected_settlement_date="2026-07-31",
            source_url=finra_short_interest_url(settlement_date="2026-07-31"),
        )


def test_settlement_date_mismatch_fails_closed() -> None:
    text = (
        "settlementDate,symbolCode,currentShortPositionQuantity,"
        "issuerServicesGroupExchangeCode\n"
        "2026-07-15,ABC,1000,R\n"
    )
    with pytest.raises(ProviderError, match="settlement mismatch"):
        parse_finra_short_interest_csv(
            text,
            expected_settlement_date="2026-07-31",
            source_url=finra_short_interest_url(settlement_date="2026-07-31"),
        )


def test_negative_or_fractional_short_position_fails_closed() -> None:
    base = (
        "settlementDate,symbolCode,currentShortPositionQuantity,"
        "issuerServicesGroupExchangeCode\n"
    )
    for value in ("-1", "1.5"):
        with pytest.raises(ProviderError, match="finite nonnegative integer"):
            parse_finra_short_interest_csv(
                base + f"2026-07-31,ABC,{value},R\n",
                expected_settlement_date="2026-07-31",
                source_url=finra_short_interest_url(settlement_date="2026-07-31"),
            )


def test_client_is_get_only_bounded_and_cached() -> None:
    text = (
        "settlementDate,symbolCode,currentShortPositionQuantity,"
        "issuerServicesGroupExchangeCode\n"
        "2026-07-31,ABC,1000,R\n"
    )
    calls: list[Request] = []

    def opener(request: Request, timeout: float):
        calls.append(request)
        assert request.get_method() == "GET"
        assert timeout == 30.0
        return _Response(text)

    client = FINRAShortInterestClient(opener=opener, sleeper=lambda _: None)
    first = client.historical_file(settlement_date="2026-07-31")
    second = client.historical_file(settlement_date="2026-07-31")
    assert first is second
    assert len(calls) == 1
    assert calls[0].full_url == (
        "https://cdn.finra.org/equity/otcmarket/biweekly/shrt20260731.csv"
    )


def test_url_builder_rejects_noncanonical_date() -> None:
    with pytest.raises(ProviderError):
        finra_short_interest_url(settlement_date="07/31/2026")
