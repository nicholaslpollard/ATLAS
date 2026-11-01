from __future__ import annotations

"""V89 deterministic synthetic minute bars; no source GETs or broker orders."""

from datetime import date,datetime,timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from packages.simulation.spy_v89_six_family_causal_registry import (
    FAMILIES,V89Error,evaluate,verified,
)

ET=ZoneInfo("America/New_York")
SHA="a"*64
DAY="2024-01-02"


def bars(opens,closes,*,highs=None,lows=None):
    assert len(opens)==len(closes)
    result=[]
    for i,(o,c) in enumerate(zip(opens,closes)):
        at=datetime(2024,1,2,9,30,tzinfo=ET)+timedelta(minutes=i)
        high=max(o,c)+(highs[i] if highs else .01)
        low=min(o,c)-(lows[i] if lows else .01)
        result.append({
            "minute_at_et":at.isoformat(),
            "available_at_et":(at+timedelta(minutes=1)).isoformat(),
            "open":str(o),"high":str(high),
            "low":str(low),"close":str(c),
        })
    return result


def run(family,source,**kw):
    return evaluate(family,session=DAY,stock_source_sha=SHA,bars=source,
                    market_session_verified=True,**kw)


def test_registry_six_distinct_clocks_and_thresholds_frozen():
    assert len(FAMILIES)==6
    assert set(x["decision"] for x in FAMILIES.values())=={"09:35:01","09:40:01"}
    assert "failed_breakout_fade_0940" not in FAMILIES
    assert "orb_continuation_0940" not in FAMILIES
    assert "gap_fade_0935" not in FAMILIES


def test_five_minute_impulse_call_put_and_no_signal_are_signed():
    up=bars([100,100.05,100.10,100.15,100.20],
            [100.05,100.10,100.15,100.20,100.25])
    down=bars([100,99.95,99.90,99.85,99.80],
              [99.95,99.90,99.85,99.80,99.75])
    for original,wanted in [(up,"CALL"),(down,"PUT")]:
        result=run("impulse_0935",original)
        assert result["direction"]==wanted
        assert verified(result)
        assert result["decision_at_et"].endswith("09:35:01-05:00")
        assert result["actual_orders"]==result["broker_fills"]==0
    none=bars([100]*5,[100]*5)
    assert run("impulse_0935",none)["status"]=="NO_SIGNAL"


def test_ten_minute_acceleration_and_early_reversal_are_different_rules():
    a=bars([100,100.03,100.06,100.09,100.12,
            100.15,100.20,100.25,100.30,100.35],
           [100.03,100.06,100.09,100.12,100.15,
            100.20,100.25,100.30,100.35,100.40])
    b=bars([100,100.08,100.16,100.24,100.32,
            100.40,100.32,100.25,100.18,100.11],
           [100.08,100.16,100.24,100.32,100.40,
            100.32,100.25,100.18,100.11,100.04])
    assert run("acceleration_0940",a)["direction"]=="CALL"
    assert run("early_reversal_0940",b)["direction"]=="PUT"
    assert run("acceleration_0940",b)["direction"] is None


def test_pullback_resume_and_gap_followthrough_keep_source_clocks():
    p=bars([100,100.08,100.16,100.24,100.32,
            100.40,100.32,100.26,100.21,100.20],
           [100.08,100.16,100.24,100.32,100.40,
            100.32,100.26,100.21,100.20,100.22])
    assert run("pullback_resume_0940",p)["direction"]=="CALL"
    prior={
        "prior_close":"99.25",
        "prior_close_at_et":"2023-12-29T15:59:00-05:00",
        "prior_close_available_at_et":"2023-12-29T16:00:00-05:00",
    }
    g=bars([100,100.03,100.06,100.09,100.12,
            100.15,100.18,100.20,100.22,100.24],
           [100.03,100.06,100.09,100.12,100.15,
            100.18,100.20,100.22,100.24,100.26])
    gap=run("gap_followthrough_0940",g,**prior)
    assert gap["direction"]=="CALL"
    assert gap["features"]["prior_close_publication_independently_proven"] is False
    with pytest.raises(V89Error,match="PRIOR_SESSION_CLOSE"):
        run("gap_followthrough_0940",g)


def test_compression_release_needs_true_second_range_contracting():
    up=bars(
        [100.0,100.1,100.2,100.3,100.35,100.39,100.40,100.41,100.42,100.43],
        [100.1,100.2,100.3,100.35,100.39,100.40,100.41,100.42,100.43,100.44],
    )
    assert run("compression_release_0940",up)["direction"]=="CALL"


def test_future_or_missing_minute_and_naive_timestamps_fail_closed():
    source=bars([100]*10,[100.02]*10)
    bad=[dict(x) for x in source]
    bad[-1]["available_at_et"]="2024-01-02T09:41:00-05:00"
    with pytest.raises(V89Error,match="FUTURE"):
        run("acceleration_0940",bad)
    with pytest.raises(V89Error,match="EXACT_CLOSED_MINUTES"):
        run("acceleration_0940",source[:-1])
    bad=[dict(x) for x in source]
    bad[0]["available_at_et"]="2024-01-02T09:31:00"
    with pytest.raises(V89Error,match="NAIVE"):
        run("acceleration_0940",bad)
