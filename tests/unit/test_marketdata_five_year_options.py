from __future__ import annotations

import io
import json
import urllib.error
from types import SimpleNamespace

import pytest

from packages.providers.marketdata_app import client
from packages.data.marketdata_five_year_options_qualification import CONTRACT, _choose_qualification_contract


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


def test_marketdata_token_is_header_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = []

    def fake_urlopen(request, timeout):
        captured.append(request)
        return _FakeResponse(
            {
                "s": "ok",
                "optionSymbol": ["AAPL261016C00250000"],
                "strike": [250],
            }
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    client.get_json(
        "options/chain/AAPL/",
        params={"date": "2026-09-01"},
        token="super-secret-token",
        max_attempts=1,
    )

    assert len(captured) == 1
    assert captured[0].get_header("Authorization") == "Bearer super-secret-token"
    assert "super-secret-token" not in captured[0].full_url
    assert "token=" not in captured[0].full_url.lower()


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
    assert _choose_qualification_contract(rows)["optionSymbol"] == "SPY261016C00600000"


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


def test_rate_limit_snapshot_is_case_insensitive_and_numeric() -> None:
    assert client.rate_limit_snapshot(
        {
            "X-Api-Ratelimit-Limit": "10000",
            "x-api-ratelimit-remaining": "9997",
            "X-Api-Ratelimit-Reset": "1789997400",
            "X-Api-Ratelimit-Consumed": "3",
        }
    ) == {
        "limit": 10000,
        "remaining": 9997,
        "reset": 1789997400,
        "consumed": 3,
    }


def test_starter_trial_completion_uses_trial_anchor_count(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import packages.data.marketdata_five_year_options_qualification as qualification

    assert len(qualification.CONTRACT["starter_trial_anchors"]) == 5
    assert len(qualification.CONTRACT["anchors"]) == 6

    def fake_chain(underlying, *, date, dte, strike_limit, side=None):
        symbol = f"{underlying}261016C00100000"
        return client.MarketDataResponse(
            http_status=200,
            payload={
                "s": "ok",
                "optionSymbol": [symbol],
                "underlying": [underlying],
                "expiration": [1792180800],
                "side": ["call"],
                "strike": [100.0],
                "firstTraded": [1700000000],
                "dte": [dte],
                "bid": [1.0],
                "ask": [1.2],
                "mid": [1.1],
                "last": [1.1],
                "volume": [5],
                "openInterest": [10],
                "underlyingPrice": [100.0],
                "updated": [1790000000],
                "iv": [None],
                "delta": [None],
                "gamma": [None],
                "theta": [None],
                "vega": [None],
            },
            headers={
                "X-Api-Ratelimit-Limit": "10000",
                "X-Api-Ratelimit-Remaining": "9999",
                "X-Api-Ratelimit-Consumed": "1",
            },
            response_bytes=100,
            elapsed_seconds=0.01,
        )

    def fake_quotes(option_symbol, *, from_date, to_date):
        return client.MarketDataResponse(
            http_status=200,
            payload={
                "s": "ok",
                "optionSymbol": [option_symbol],
                "bid": [1.0],
                "ask": [1.2],
                "mid": [1.1],
                "last": [1.1],
                "volume": [5],
                "openInterest": [10],
                "underlyingPrice": [100.0],
                "updated": [1790000000],
                "iv": [None],
                "delta": [None],
                "gamma": [None],
                "theta": [None],
                "vega": [None],
            },
            headers={
                "X-Api-Ratelimit-Limit": "10000",
                "X-Api-Ratelimit-Remaining": "9998",
                "X-Api-Ratelimit-Consumed": "1",
            },
            response_bytes=100,
            elapsed_seconds=0.01,
        )

    monkeypatch.setattr(qualification, "historical_chain", fake_chain)
    monkeypatch.setattr(qualification, "historical_quote_series", fake_quotes)

    report = qualification.run_marketdata_five_year_options_qualification_v1(
        SimpleNamespace(project_root=tmp_path),
        starter_trial=True,
    )

    assert report["status"] == "QUALIFIED_FOR_STARTER_TRIAL_CAPABILITY"
    assert len(report["anchors"]) == 5
    assert report["all_anchor_chains_nonempty"] is True
    assert report["all_quote_series_nonempty"] is True
    assert report["open_interest_present_across_anchors"] is True
    assert report["required_schema_present_across_anchors"] is True
    assert report["historical_greeks_present_and_null_across_anchors"] is True
    assert report["broad_five_year_entitlement_proven"] is False
    assert report["observed_api_credits_consumed"] == 10

    paid_report = qualification.run_marketdata_five_year_options_qualification_v1(
        SimpleNamespace(project_root=tmp_path / "paid"),
        starter_trial=False,
    )
    assert paid_report["status"] == "QUALIFIED_FOR_FIVE_YEAR_EOD_ECONOMICS_CHALLENGER"
    assert len(paid_report["anchors"]) == 6
    assert paid_report["required_schema_present_across_anchors"] is True
    assert paid_report["historical_greeks_present_and_null_across_anchors"] is True
    assert paid_report["broad_five_year_entitlement_proven"] is True
    assert paid_report["observed_api_credits_consumed"] == 12


def test_get_json_does_not_retry_429(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_urlopen(request, timeout):
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            url=request.full_url,
            code=429,
            msg="credit limit reached",
            hdrs={"X-Api-Ratelimit-Remaining": "0"},
            fp=io.BytesIO(
                json.dumps({"s": "error", "errmsg": "credit limit reached"}).encode(
                    "utf-8"
                )
            ),
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(client.MarketDataError) as captured:
        client.get_json(
            "options/chain/SPY/",
            params={"date": "2026-09-01"},
            token="test-token",
            max_attempts=5,
            sleep=lambda _seconds: None,
        )

    assert captured.value.http_status == 429
    assert calls == 1
