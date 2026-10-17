from __future__ import annotations

import json
from pathlib import Path

import pytest

from packages.providers.thetadata import client


class _FakeWorker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def request(self, method: str, kwargs: dict):
        self.calls.append((method, dict(kwargs)))
        if method == "option_history_open_interest":
            rows = [
                {
                    "symbol": kwargs["symbol"],
                    "expiration": "2025-02-21",
                    "strike": 100.0,
                    "right": "call",
                    "timestamp": "2025-01-06T06:30:00",
                    "open_interest": 250,
                }
            ]
        elif method == "option_history_binomial_greeks_first_order":
            rows = [
                {
                    "symbol": kwargs["symbol"],
                    "expiration": kwargs["expiration"],
                    "strike": 100.0,
                    "right": "call",
                    "timestamp": "2025-01-06T09:35:00",
                    "bid": 1.0,
                    "ask": 1.1,
                    "delta": 0.5,
                    "theta": -0.05,
                    "vega": 0.12,
                    "rho": 0.04,
                    "epsilon": 0.01,
                    "lambda": 4.0,
                    "implied_vol": 0.3,
                    "iv_error": 0.0,
                    "underlying_timestamp": "2025-01-06T09:35:00",
                    "underlying_price": 101.0,
                }
            ]
        else:
            rows = [
                {
                    "symbol": kwargs["symbol"],
                    "expiration": (
                        "2025-02-21"
                        if kwargs.get("expiration") == "*"
                        else kwargs.get("expiration")
                    ),
                    "strike": 100.0,
                    "right": "call",
                    "timestamp": "2025-01-06T09:34:59",
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
        return {
            "id": "fake",
            "ok": True,
            "method": method,
            "library_version": "1.0.12",
            "environment_fingerprint": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "rows": rows,
        }


@pytest.fixture
def fake_worker(monkeypatch):
    fake = _FakeWorker()
    monkeypatch.setattr(client, "_worker", lambda: fake)
    yield fake
    client.reset_thread_worker_for_tests()


def test_provider_python_default_is_isolated_repo_environment(monkeypatch):
    monkeypatch.delenv(client.THETADATA_PYTHON_ENV, raising=False)
    path = client.provider_python_path()

    assert client.DEFAULT_PROVIDER_VENV in path.parents
    assert ".provider_venvs" in str(path)
    assert "thetadata" in str(path)


def test_provider_python_override(monkeypatch, tmp_path):
    expected = tmp_path / "python-custom.exe"
    monkeypatch.setenv(client.THETADATA_PYTHON_ENV, str(expected))
    assert client.provider_python_path() == expected


def test_canonical_bytes_are_stable():
    rows = (
        {"b": 2.0, "a": "2025-01-06"},
    )
    assert client._canonical_bytes(rows) == b'[{"a":"2025-01-06","b":2.0}]\n'


def test_at_time_surface_maps_to_worker_library_method(fake_worker):
    response = client.option_at_time_quote_surface(
        symbol="AAPL",
        date_et="2025-01-06",
        time_of_day_et="09:35:00.000",
        max_dte=75,
    )

    name, params = fake_worker.calls[-1]
    assert name == "option_at_time_quote"
    assert params == {
        "symbol": "AAPL",
        "start_date": "2025-01-06",
        "end_date": "2025-01-06",
        "time_of_day": "09:35:00.000",
        "expiration": "*",
        "strike": "*",
        "right": "call",
        "max_dte": 75,
    }
    assert response.transport == "THETADATA_PYTHON_LIBRARY_ISOLATED_WORKER"
    assert response.library_version == "1.0.12"
    assert response.provider_environment_fingerprint == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    assert response.evidence_encoding == "CANONICAL_PROVIDER_DATAFRAME_JSON"
    assert response.http_status == 200
    assert len(response.rows) == 1


def test_exact_at_time_quote_maps_selected_contract(fake_worker):
    client.option_at_time_quote(
        symbol="AAPL",
        expiration="2025-02-21",
        strike="100.0",
        right="call",
        date_et="2025-01-06",
        time_of_day_et="10:07:00.000",
    )

    name, params = fake_worker.calls[-1]
    assert name == "option_at_time_quote"
    assert params["expiration"] == "2025-02-21"
    assert params["strike"] == "100.0"
    assert params["start_date"] == "2025-01-06"
    assert params["end_date"] == "2025-01-06"
    assert params["time_of_day"] == "10:07:00.000"


def test_open_interest_surface_maps_to_worker_library_method(fake_worker):
    response = client.option_history_open_interest_surface(
        symbol="AAPL",
        date_et="2025-01-06",
        max_dte=75,
    )

    name, params = fake_worker.calls[-1]
    assert name == "option_history_open_interest"
    assert params == {
        "symbol": "AAPL",
        "date": "2025-01-06",
        "expiration": "*",
        "strike": "*",
        "right": "call",
        "max_dte": 75,
    }
    assert response.rows[0]["open_interest"] == 250


def test_binomial_greeks_maps_exact_minute_and_dividend(fake_worker):
    response = client.option_history_binomial_first_order_greeks_at_minute(
        symbol="AAPL",
        expiration="2025-02-21",
        date_et="2025-01-06",
        annual_dividend=1.0,
    )

    name, params = fake_worker.calls[-1]
    assert name == "option_history_binomial_greeks_first_order"
    assert params == {
        "symbol": "AAPL",
        "expiration": "2025-02-21",
        "strike": "*",
        "right": "call",
        "date": "2025-01-06",
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


def test_worker_rejects_missing_provider_python(tmp_path):
    with pytest.raises(client.ThetaDataError, match="provider Python is unavailable"):
        client._Worker(tmp_path / "missing-python")
