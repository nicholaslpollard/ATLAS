from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from packages.backtesting.literature_momseason_adjusted_predictor_source import (
    MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
    MOMSEASON_ADJUSTED_PREDICTOR_FEED,
    MOMSEASON_ADJUSTED_PREDICTOR_ROLE,
    MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
    _unit_id,
    extract_single_session_adjusted_closes,
)
from packages.backtesting.literature_momseason_policy import (
    LITERATURE_MOMSEASON_PROTECTED_START,
    required_lag_reference_dates,
)
from packages.providers.alpaca.client import AlpacaApiPage, AlpacaMarketDataClient


class _RecordingClient(AlpacaMarketDataClient):
    def __init__(self) -> None:
        self.cfg = SimpleNamespace(
            base_url="https://data.alpaca.markets",
            symbol_batch_size=100,
            timeframe="1Day",
            adjustment="raw",
            feed="sip",
            asof="-",
            page_limit=10000,
        )
        self.calls: list[dict[str, object]] = []

    def _request_json(self, **kwargs):  # type: ignore[override]
        self.calls.append(dict(kwargs))
        return AlpacaApiPage(
            request_name=str(kwargs["request_name"]),
            url="https://example.invalid",
            http_status=200,
            raw_body=b"{}",
            payload={},
            response_headers={},
            page_token_used=kwargs.get("page_token_used"),
            next_page_token=None,
        )


def test_lag_endpoint_whitelist_remains_before_protected_window() -> None:
    endpoints = required_lag_reference_dates()
    assert endpoints
    assert max(endpoints) < LITERATURE_MOMSEASON_PROTECTED_START


def test_adjusted_endpoint_contract_is_lag_predictor_only() -> None:
    assert MOMSEASON_ADJUSTED_PREDICTOR_ROLE == "LAG_PREDICTOR_ENDPOINT"
    assert MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT == "all"
    assert MOMSEASON_ADJUSTED_PREDICTOR_FEED == "sip"
    assert MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME == "1Day"


def test_unit_id_is_deterministic_and_semantics_sensitive() -> None:
    session = date(2020, 8, 31)
    first = _unit_id(
        endpoint_session=session,
        batch_index=0,
        symbols=("AAA", "BBB"),
        plan_fingerprint="plan",
    )
    second = _unit_id(
        endpoint_session=session,
        batch_index=0,
        symbols=("AAA", "BBB"),
        plan_fingerprint="plan",
    )
    changed = _unit_id(
        endpoint_session=session,
        batch_index=1,
        symbols=("AAA", "BBB"),
        plan_fingerprint="plan",
    )
    assert first == second
    assert first != changed


def test_extract_single_session_adjusted_close_uses_exact_literal_and_date() -> None:
    payload = {
        "bars": {
            "AAA": [
                {"t": "2020-08-31T04:00:00Z", "c": 10.25},
            ],
            "BBB": [
                {"t": "2020-08-31T04:00:00Z", "c": 20.5},
            ],
        }
    }
    observed, anomalies = extract_single_session_adjusted_closes(
        payload,
        requested_symbols={"AAA", "BBB"},
        endpoint_session=date(2020, 8, 31),
    )
    assert observed == {"AAA": 10.25, "BBB": 20.5}
    assert anomalies == []


def test_extract_quarantines_unsubmitted_and_wrong_session_rows() -> None:
    payload = {
        "bars": {
            "AAA": [
                {"t": "2020-08-28T04:00:00Z", "c": 10.0},
            ],
            "OTHER": [
                {"t": "2020-08-31T04:00:00Z", "c": 99.0},
            ],
        }
    }
    observed, anomalies = extract_single_session_adjusted_closes(
        payload,
        requested_symbols={"AAA"},
        endpoint_session=date(2020, 8, 31),
    )
    assert observed == {}
    assert {str(row["type"]) for row in anomalies} == {
        "OUTSIDE_ENDPOINT_SESSION",
        "UNSUBMITTED_RESPONSE_SYMBOL",
    }


def test_alpaca_request_can_be_frozen_to_one_adjusted_historical_session() -> None:
    client = _RecordingClient()
    session = "2020-08-31"
    list(
        client.historical_bar_pages(
            symbols=["AAA", "BBB"],
            start=session,
            end=session,
            adjustment=MOMSEASON_ADJUSTED_PREDICTOR_ADJUSTMENT,
            asof=session,
            feed=MOMSEASON_ADJUSTED_PREDICTOR_FEED,
            timeframe=MOMSEASON_ADJUSTED_PREDICTOR_TIMEFRAME,
        )
    )
    assert len(client.calls) == 1
    params = client.calls[0]["params"]
    assert isinstance(params, dict)
    assert params["start"] == session
    assert params["end"] == session
    assert params["adjustment"] == "all"
    assert params["asof"] == session
    assert params["feed"] == "sip"
    assert params["timeframe"] == "1Day"
    assert client.cfg.adjustment == "raw"
    assert client.cfg.asof == "-"
