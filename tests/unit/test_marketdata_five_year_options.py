from __future__ import annotations

import io
import json
import urllib.error

import pytest

from packages.providers.marketdata_app import client
from packages.data.marketdata_five_year_options_qualification import CONTRACT, _choose_contract


class _FakeResponse:
    def __init__(self, payload: dict[str, object], *, status: int = 200) -> None:
        self.status = status
        self.headers = {"x-api-credits-used": "1"}
        self._raw = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def test_array_rows_decodes_columnar_payload() -> None:
    payload = {
        "s": "ok",
        "optionSymbol": ["A", "B"],
        "strike": [100, 105],
        "openInterest": [123, 456],
    }
    assert client.array_rows(payload) == (
        {"optionSymbol": "A", "strike": 100, "openInterest": 123},
        {"optionSymbol": "B", "strike": 105, "openInterest": 456},
    )


def test_array_rows_rejects_mismatched_columns() -> None:
    with pytest.raises(client.MarketDataError):
        client.array_rows(
            {
                "s": "ok",
                "optionSymbol": ["A", "B"],
                "strike": [100],
            }
        )


def test_get_json_accepts_http_203_cached_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        return _FakeResponse(
            {
                "s": "ok",
                "optionSymbol": ["AAPL261016C00250000"],
                "strike": [250],
            },
            status=203,
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    response = client.get_json(
        "options/chain/AAPL/",
        params={"date": "2026-09-01"},
        token="test-token",
        max_attempts=1,
    )
    assert response.http_status == 203
    assert response.payload["s"] == "ok"


def test_get_json_fails_closed_on_plan_entitlement_402(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=402,
            msg="payment required",
            hdrs={},
            fp=io.BytesIO(
                json.dumps(
                    {"s": "error", "errmsg": "historical data outside plan"}
                ).encode("utf-8")
            ),
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(client.MarketDataError) as captured:
        client.get_json(
            "options/chain/SPY/",
            params={"date": "2021-10-01"},
            token="test-token",
            max_attempts=1,
        )
    assert captured.value.http_status == 402


def test_choose_contract_prefers_nearest_atm_call() -> None:
    rows = (
        {
            "optionSymbol": "SPY261016C00550000",
            "side": "call",
            "strike": 550,
            "underlyingPrice": 601,
        },
        {
            "optionSymbol": "SPY261016C00600000",
            "side": "call",
            "strike": 600,
            "underlyingPrice": 601,
        },
        {
            "optionSymbol": "SPY261016P00600000",
            "side": "put",
            "strike": 600,
            "underlyingPrice": 601,
        },
    )
    assert _choose_contract(rows)["optionSymbol"] == "SPY261016C00600000"


def test_starter_trial_anchors_use_deep_aapl_and_recent_general_tickers() -> None:
    anchors = CONTRACT["starter_trial_anchors"]
    assert anchors[0] == {
        "root": "AAPL",
        "date": "2021-10-01",
        "scope": "deep_aapl",
    }
    assert all(
        item["date"] >= "2025-09-23"
        for item in anchors[1:]
    )
    assert {item["root"] for item in anchors[1:]} == {"SPY", "MSFT", "NVDA", "QQQ"}
