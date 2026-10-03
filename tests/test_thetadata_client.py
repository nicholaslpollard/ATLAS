from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from packages.providers.thetadata import client


class _FakeThetaClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def _frame(self):
        return pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "expiration": date(2025, 2, 21),
                    "strike": 100.0,
                    "right": "call",
                    "timestamp": datetime(2025, 1, 6, 9, 34, 59),
                    "bid_size": 10,
                    "bid_exchange": 1,
                    "bid": 1.0,
                    "bid_condition": 0,
                    "ask_size": 12,
                    "ask_exchange": 2,
                    "ask": 1.1,
                    "ask_condition": 0,
                }
            ]
        )

    def option_at_time_quote(self, **kwargs):
        self.calls.append(("option_at_time_quote", kwargs))
        return self._frame()

    def option_history_open_interest(self, **kwargs):
        self.calls.append(("option_history_open_interest", kwargs))
        frame = self._frame()[["symbol", "expiration", "strike", "right", "timestamp"]].copy()
        frame["open_interest"] = 250
        return frame

    def option_history_binomial_greeks_first_order(self, **kwargs):
        self.calls.append(("option_history_binomial_greeks_first_order", kwargs))
        frame = self._frame()[
            ["symbol", "expiration", "strike", "right", "timestamp", "bid", "ask"]
        ].copy()
        frame["delta"] = 0.5
        frame["theta"] = -0.05
        frame["vega"] = 0.12
        frame["rho"] = 0.04
        frame["epsilon"] = 0.01
        frame["lambda"] = 4.0
        frame["implied_vol"] = 0.3
        frame["iv_error"] = 0.0
        frame["underlying_timestamp"] = datetime(2025, 1, 6, 9, 34, 59)
        frame["underlying_price"] = 101.0
        return frame


@pytest.fixture
def fake_client(monkeypatch):
    fake = _FakeThetaClient()
    monkeypatch.setattr(client, "_client", lambda: fake)
    client._thread_state.library_version = "1.0.12"
    yield fake
    client.reset_thread_client_for_tests()


def test_version_tuple_and_minimum_contract():
    assert client._version_tuple("1.0.12") == (1, 0, 12)
    assert client._version_tuple("1.0.9") >= client.MIN_API_KEY_LIBRARY
    assert client.TARGET_LIBRARY_VERSION == "1.0.12"


def test_dataframe_records_are_canonical_and_datetime_safe():
    frame = pd.DataFrame(
        [
            {
                "b": 2.0,
                "a": date(2025, 1, 6),
                "t": datetime(2025, 1, 6, 9, 35),
            }
        ]
    )
    rows = client._records_from_dataframe(frame)
    raw = client._canonical_bytes(rows)

    assert rows == (
        {
            "b": 2.0,
            "a": "2025-01-06",
            "t": "2025-01-06T09:35:00",
        },
    )
    assert raw == (
        b'[{"a":"2025-01-06","b":2.0,"t":"2025-01-06T09:35:00"}]\n'
    )


def test_at_time_surface_maps_to_direct_library_method(fake_client):
    response = client.option_at_time_quote_surface(
        symbol="AAPL",
        date_et="2025-01-06",
        time_of_day_et="09:35:00.000",
        max_dte=75,
    )

    name, params = fake_client.calls[-1]
    assert name == "option_at_time_quote"
    assert params == {
        "symbol": "AAPL",
        "start_date": date(2025, 1, 6),
        "end_date": date(2025, 1, 6),
        "time_of_day": "09:35:00.000",
        "expiration": "*",
        "strike": "*",
        "right": "call",
        "max_dte": 75,
    }
    assert response.transport == "THETADATA_PYTHON_LIBRARY_GRPC"
    assert response.library_version == "1.0.12"
    assert response.evidence_encoding == "CANONICAL_PROVIDER_DATAFRAME_JSON"
    assert response.http_status == 200
    assert len(response.rows) == 1


def test_exact_at_time_quote_maps_selected_contract(fake_client):
    client.option_at_time_quote(
        symbol="AAPL",
        expiration="2025-02-21",
        strike="100.0",
        right="call",
        date_et="2025-01-06",
        time_of_day_et="10:07:00.000",
    )

    name, params = fake_client.calls[-1]
    assert name == "option_at_time_quote"
    assert params["expiration"] == date(2025, 2, 21)
    assert params["strike"] == "100.0"
    assert params["start_date"] == date(2025, 1, 6)
    assert params["end_date"] == date(2025, 1, 6)
    assert params["time_of_day"] == "10:07:00.000"


def test_open_interest_surface_maps_to_direct_library_method(fake_client):
    response = client.option_history_open_interest_surface(
        symbol="AAPL",
        date_et="2025-01-06",
        max_dte=75,
    )

    name, params = fake_client.calls[-1]
    assert name == "option_history_open_interest"
    assert params == {
        "symbol": "AAPL",
        "date": date(2025, 1, 6),
        "expiration": "*",
        "strike": "*",
        "right": "call",
        "max_dte": 75,
    }
    assert response.rows[0]["open_interest"] == 250


def test_binomial_greeks_maps_exact_minute_and_dividend(fake_client):
    response = client.option_history_binomial_first_order_greeks_at_minute(
        symbol="AAPL",
        expiration="2025-02-21",
        date_et="2025-01-06",
        annual_dividend=1.0,
    )

    name, params = fake_client.calls[-1]
    assert name == "option_history_binomial_greeks_first_order"
    assert params == {
        "symbol": "AAPL",
        "expiration": date(2025, 2, 21),
        "strike": "*",
        "right": "call",
        "date": date(2025, 1, 6),
        "start_time": "09:35:00.000",
        "end_time": "09:35:00.000",
        "interval": "1m",
        "annual_dividend": 1.0,
        "rate_type": "sofr",
        "version": "1",
        "binomial_steps": 101,
    }
    assert response.rows[0]["delta"] == 0.5


def test_binomial_greeks_rejects_negative_dividend():
    with pytest.raises(ValueError, match="annual_dividend"):
        client.option_history_binomial_first_order_greeks_at_minute(
            symbol="AAPL",
            expiration="2025-02-21",
            date_et="2025-01-06",
            annual_dividend=-0.01,
        )


def test_call_does_not_echo_external_exception_message(monkeypatch):
    class _Broken:
        def option_at_time_quote(self, **kwargs):
            raise RuntimeError("secret-token-should-not-be-echoed")

    monkeypatch.setattr(client, "_client", lambda: _Broken())
    with pytest.raises(client.ThetaDataError) as exc:
        client.option_at_time_quote_surface(
            symbol="AAPL",
            date_et="2025-01-06",
            time_of_day_et="09:35:00.000",
        )

    assert "RuntimeError" in str(exc.value)
    assert "secret-token" not in str(exc.value)
