from __future__ import annotations

from datetime import datetime,timedelta,timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.providers.alpaca.client import AlpacaMarketDataClient,AlpacaApiPage
from scripts.run_spy_v62_historical_spot_capture import (
    StockQuoteSourceError,_clock_parts,_quote_candidate,collect,
)

DAY="2025-06-13"


def v61(tmp):
    record={
        "contract":"atlas-v61-independent-action-side-source-readiness-v1",
        "session":DAY,
        "target_decision_at_et":DAY+"T10:00:01-04:00",
        "independent_current_spot_tick_verified":False,
        "side_aware_bsm_reference_status":"ABSTAIN_MISSING_INDEPENDENT_MODEL_INPUTS",
        "original_account_report_fingerprint":"b"*64,
    }
    record["fingerprint"]=_fingerprint(record)
    p=tmp/"v61.json"
    p.write_text(json.dumps(record),encoding="utf8")
    return p


def q(t,bid="598.12",ask="598.14"):
    return {"t":DAY+"T"+t+"-04:00","bp":float(bid),"ap":float(ask),
            "bs":8,"as":6,"bx":"N","ax":"P","c":["R"],"z":"C"}


def page(rows,token,next_token):
    obj={"symbol":"SPY","quotes":rows,"next_page_token":next_token}
    raw=json.dumps(obj,separators=(",",":")).encode()
    return AlpacaApiPage(
        request_name="v62_historical_spy_stock_quotes",
        url="https://data.alpaca.markets/v2/stocks/SPY/quotes",
        http_status=200,raw_body=raw,payload=obj,
        response_headers={},page_token_used=token,
        next_page_token=next_token,
    )


def client_factory(pages,seen):
    class Fake:
        def __init__(self,settings):
            self.settings=settings
        def historical_stock_quote_page(self,**kwargs):
            seen.append(kwargs)
            return pages[len(seen)-1]
    return Fake


def test_nanosecond_boundary_never_leaks_future_quote():
    target=datetime.fromisoformat(DAY+"T10:00:01-04:00")
    from scripts.run_spy_v62_historical_spot_capture import _target_clock
    t=_target_clock(target)
    assert _clock_parts(DAY+"T10:00:01.000000001-04:00")>t
    assert _clock_parts(DAY+"T10:00:00.999999999-04:00")<t
    start=t-Decimal(3)
    end=t+Decimal(1)
    a,reason=_quote_candidate(q("10:00:01.000000001"),cutoff=t,first=start,last=end)
    assert a is None and reason=="FUTURE_OR_STALE_QUOTE"
    a,reason=_quote_candidate(q("10:00:00.999999999"),cutoff=t,first=start,last=end)
    assert reason is None
    assert a["age_seconds_at_decision"]=="1E-9"


def test_multpage_raw_original_archives_and_latest_only_prior_quote(tmp_path):
    seen=[]
    pages=[
        page([q("09:59:59.000000000"),q("10:00:00.999999999")],None,"second"),
        page([q("10:00:01.000000001",bid="599",ask="599.1"),
              q("10:00:01.500000000",bid="610",ask="610.1")],"second",None),
    ]
    captured=collect(v61(tmp_path),tmp_path/"archive",
                     client_factory=client_factory(pages,seen),
                     settings_factory=lambda *x:object(),
                     progress=lambda _:None)
    assert captured["status"]=="COMPLETE_SOURCE_WINDOW"
    assert len(seen)==2
    assert all(x["feed"]=="sip" for x in seen)
    assert all(x["symbol"]=="SPY" for x in seen)
    assert captured["original_quote_rows"]==4
    assert captured["quote_rejection_counts"]=={"FUTURE_OR_STALE_QUOTE":2}
    best=captured["latest_past_only_stock_nbbo"]
    assert best["original_quote_clock"]==DAY+"T10:00:00.999999999-04:00"
    assert best["indicative_mid_not_executable"]=="598.13"
    assert best["bid_size_native"]==8
    assert captured["historical_bsm_fair_value"] is None
    assert captured["side_aware_valuation_eligible"] is False
    assert captured["actual_broker_orders"]==0
    assert captured["alpaca_stock_provider_pages"]==2
    for idx,p in enumerate(pages,1):
        raw=(tmp_path/"archive"/f"page_{idx:04d}.json").read_bytes()
        assert raw==p.raw_body
        assert captured["original_pages"][idx-1]["raw_sha256"]==hashlib.sha256(raw).hexdigest()
    assert captured["fingerprint"]==_fingerprint({
        k:v for k,v in captured.items() if k!="fingerprint"})


def test_incomplete_pages_are_not_admitted_even_when_prior_quote_seen(tmp_path):
    seen=[]
    pages=[page([q("10:00:00.1")],"sentinel","sentinel")]
    class Infinite:
        def __init__(self,settings):pass
        def historical_stock_quote_page(self,**kwargs):
            seen.append(kwargs)
            obj={"symbol":"SPY","quotes":[q("10:00:00.1")],
                 "next_page_token":"next_"+str(len(seen))}
            raw=json.dumps(obj).encode()
            return AlpacaApiPage("v62", "",200,raw,obj,{},
                                 kwargs["page_token"],obj["next_page_token"])
    report=collect(v61(tmp_path),tmp_path/"archive",
                   client_factory=Infinite,settings_factory=lambda _:object(),
                   progress=lambda _:None)
    assert len(seen)==12
    assert report["status"]=="CENSORED_TOO_MANY_HISTORICAL_PAGES"
    assert report["latest_past_only_stock_nbbo"] is None
    assert report["side_aware_valuation_eligible"] is False
    assert len(report["original_pages"])==12


def test_source_request_method_bounds_endpoint_and_never_invokes_trading():
    client=object.__new__(AlpacaMarketDataClient)
    client.cfg=SimpleNamespace(base_url="https://data.alpaca.markets")
    recorded=[]
    def request(**kwargs):
        recorded.append(kwargs)
        return "synthetic"
    client._request_json=request
    out=client.historical_stock_quote_page(
        symbol="SPY",start=DAY+"T09:59:58-04:00",
        end=DAY+"T10:00:02-04:00",feed="sip",
        page_limit=10000)
    assert out=="synthetic"
    assert recorded[0]["path"]=="v2/stocks/SPY/quotes"
    assert recorded[0]["params"]["feed"]=="sip"
    assert recorded[0]["request_name"]=="v62_historical_spy_stock_quotes"
    with pytest.raises(ValueError,match="SYMBOL_OR_FEED_INVALID"):
        client.historical_stock_quote_page(
            symbol="GME",start=DAY+"T09:59:58-04:00",
            end=DAY+"T10:00:02-04:00")
    with pytest.raises(ValueError,match="TIME_WINDOW_INVALID"):
        client.historical_stock_quote_page(
            symbol="SPY",start=DAY+"T09:59:58-04:00",
            end=DAY+"T10:00:22-04:00")


def test_action_quote_missing_or_invalid_never_claimed_to_be_fair(tmp_path):
    seen=[]
    p=page([q("10:00:01.000000001"),q("10:00:01.7")],None,None)
    report=collect(v61(tmp_path),tmp_path/"archive",
                   client_factory=client_factory([p],seen),
                   settings_factory=lambda _:object(),progress=lambda _:None)
    assert report["status"]=="COMPLETE_SOURCE_WINDOW"
    assert report["latest_past_only_stock_nbbo"] is None
    assert report["independent_spot_quote_archive_exists"] is False
    assert report["side_aware_valuation_eligible"] is False


def test_original_report_requires_correct_sha_and_immutable_output(tmp_path):
    path=v61(tmp_path)
    (tmp_path/"archive").mkdir()
    with pytest.raises(StockQuoteSourceError,match="IMMUTABLE_OUTPUT_DIRECTORY_EXISTS"):
        collect(path,tmp_path/"archive",progress=lambda _:None)
    row=json.loads(path.read_text())
    row["session"]="2025-06-12"
    path.write_text(json.dumps(row))
    with pytest.raises(Exception,match="FINGERPRINT"):
        collect(path,tmp_path/"new",progress=lambda _:None)
