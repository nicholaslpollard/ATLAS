from __future__ import annotations

import copy

import pytest

from packages.simulation import spy_v46_provisional_signal as v46


def _case(day="2023-06-05", *, origin="ORIGINAL_V43"):
    both = {
        "call": {"bid": 4.0, "ask": 4.1, "status": "PRETRADE_QUOTE_0959_PASSES"},
        "put": {"bid": 4.0, "ask": 4.1, "status": "PRETRADE_QUOTE_0959_PASSES"},
    }
    return {
        "date_et": day,
        "cohort_origin": origin,
        "status": "TWO_CLOCK_SOURCE_QUALITY_PASSES",
        "expiration": "2023-07-07",
        "strike": "420",
        "spot_0959": 420,
        "quote_quality": {"pretrade_0959": both},
    }


def _feature(day="2023-06-05", vol="0.3"):
    return {
        "original_entry_date_et": day,
        "conditional_unadjusted_raw_volatility": vol,
        "forecast_source_historical_pit_qualified": False,
        "frozen_expiration_et": "2023-07-07",
        "frozen_strike": "420",
    }


def test_hypothetical_screen_does_not_promote_profit_or_trade(monkeypatch):
    monkeypatch.setattr(v46, "_validate", lambda _a, _b: ([_case()], {"2023-06-05": _feature()}))
    monkeypatch.setattr(v46, "american_lr_implied_volatility", lambda *args, **kwargs: 0.2)
    result = v46.evaluate({"fingerprint": "source45"}, {"fingerprint": "source37"})
    assert result["status_counts"] == {"ROBUST_HYPOTHETICAL_LONG": 1}
    assert len(result["cases"][0]["scenario_results"]) == 3
    assert all("HYPOTHETICAL" in r["hypothetical_decision"] for r in result["cases"][0]["scenario_results"])
    assert result["historical_profitability"] is None
    assert result["historical_trades_entered"] is None
    assert result["rates_and_dividends_are_historical_pit"] is False
    assert result["retrospective_raw_return_proxy_is_historical_pit"] is False
    assert result["fingerprint"] == v46._fingerprint({k:v for k,v in result.items() if k != "fingerprint"})


def test_unqualified_and_suspicious_are_not_turned_into_model_signals(monkeypatch):
    a = _case()
    b = _case("2018-04-02", origin="V44_OI_ALTERNATE_VARIANT")
    c = _case("2023-06-19")
    c["status"] = "SOURCE_QUALITY_NOT_ELIGIBLE"
    monkeypatch.setattr(v46, "_validate", lambda _a, _b: (
        [a,b,c], {a["date_et"]:_feature(), b["date_et"]:_feature("2018-04-02"),
                   c["date_et"]:_feature("2023-06-19")}
    ))
    monkeypatch.setattr(v46, "american_lr_implied_volatility", lambda *args, **kwargs: 0.2)
    result = v46.evaluate({"fingerprint": "source45"}, {"fingerprint": "source37"})
    assert result["status_counts"] == {
        "ROBUST_HYPOTHETICAL_LONG": 1,
        "IDENTICAL_CROSS_RIGHT_QUOTES_REVIEW": 1,
        "SOURCE_QUALITY_REJECTED": 1,
    }
    assert result["by_origin"]["V44_OI_ALTERNATE_VARIANT"] == {"IDENTICAL_CROSS_RIGHT_QUOTES_REVIEW": 1}
    assert all(x["historical_trade_pnl"] is None for x in result["cases"])


def test_missing_prior_proxy_is_not_zero_or_abstain(monkeypatch):
    monkeypatch.setattr(v46, "_validate", lambda _a, _b: (
        [_case()], {"2023-06-05": _feature(vol=None)}
    ))
    result = v46.evaluate({"fingerprint": "source45"}, {"fingerprint": "source37"})
    assert result["status_counts"] == {"RAW_PREVIOUS_20_RETURN_PROXY_UNAVAILABLE": 1}


def test_original_frozen_identity_is_immutable(monkeypatch):
    bad = _feature()
    bad["frozen_strike"] = "421"
    monkeypatch.setattr(v46, "_validate", lambda _a, _b: ([_case()], {"2023-06-05": bad}))
    with pytest.raises(v46.ProvisionalScreenError, match="ORIGINAL_FROZEN_IDENTITY_CHANGED"):
        v46.evaluate({"fingerprint": "source45"}, {"fingerprint": "source37"})


def test_parent_fingerprint_and_historical_authority_must_be_verified():
    with pytest.raises(v46.ProvisionalScreenError, match="INTEGRITY"):
        v46._validate({"contract": v46.V45_CONTRACT, "fingerprint": "f"*64}, {})
    with pytest.raises(v46.ProvisionalScreenError, match="INVALID"):
        v46._positive_number(float("nan"), "QUOTE")
    with pytest.raises(v46.ProvisionalScreenError, match="MATURITY"):
        v46._model_maturity_years("2023-06-05", "2023-06-06")


def test_scenario_dependent_state_is_distinct_from_real_entry(monkeypatch):
    monkeypatch.setattr(v46, "_validate", lambda _a, _b: ([_case()], {"2023-06-05": _feature()}))
    def model(right, *, rate, **kwargs):
        return {0.01: 0.2, 0.04: 0.3, 0.08: 0.4}[rate]
    monkeypatch.setattr(v46, "american_lr_implied_volatility", model)
    result = v46.evaluate({"fingerprint": "a"}, {"fingerprint": "b"})
    assert result["status_counts"] == {"SCENARIO_DEPENDENT_OR_UNSOLVABLE": 1}
    assert result["historical_profitability"] is None
