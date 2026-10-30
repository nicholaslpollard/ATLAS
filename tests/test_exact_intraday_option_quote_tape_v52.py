from __future__ import annotations

from pathlib import Path

import pytest

from packages.providers.thetadata import client as theta
from packages.data import options_on_demand_source_cache_v38 as cache
from packages.providers.thetadata.client import ThetaDataResponse, _canonical_bytes


def query(**changes):
    return {
        "symbol":"SPY","date_et":"2025-06-09",
        "expiration":"2025-06-09","strike":"604",
        "right":"call","start_time_et":"09:36:00.000",
        "end_time_et":"15:30:00.000","interval":"1s",
        **changes,
    }


def test_sdk_worker_wrapper_is_exact_one_day_not_all_expiries(monkeypatch):
    observed=[]
    def fake(method,**kwargs):
        observed.append((method,kwargs))
        return object()
    monkeypatch.setattr(theta,"_call",fake)
    theta.option_history_exact_quote_tape(**query())
    assert observed[0][0]=="option_history_quote"
    assert observed[0][1]=={
        "symbol":"SPY","date":"2025-06-09",
        "expiration":"2025-06-09","strike":"604",
        "right":"call","interval":"1s",
        "start_time":"09:36:00.000","end_time":"15:30:00.000",
    }
    theta.option_history_exact_quote_tape(**query(interval="tick"))
    assert observed[1][1]["interval"]=="tick"


@pytest.mark.parametrize("changes",[
    {"expiration":"2025-06-06"},{"right":"both"},{"strike":"*"},
    {"interval":"1h"},{"start_time_et":"08:00:00.000"},
    {"end_time_et":"16:30:00.000"},
    {"start_time_et":"15:30:01.000","end_time_et":"15:30:00.000"},
])
def test_invalid_or_broad_history_source_refused_before_sdk(monkeypatch,changes):
    monkeypatch.setattr(theta,"_call",lambda *a,**k:pytest.fail("should never call SDK"))
    with pytest.raises(ValueError):
        theta.option_history_exact_quote_tape(**query(**changes))


def test_v38_exact_source_normalization_rejects_oversized_or_broad_input():
    original=cache.normalize_source_requirement("option_history_exact_quote_tape",query())
    assert original["kwargs"]["interval"]=="1s"
    assert original["kwargs"]["expiration"]==original["kwargs"]["date_et"]
    assert "option_history_exact_quote_tape" in cache.ALLOWED
    assert cache.normalize_source_requirement("option_history_exact_quote_tape",query(interval="tick"))["kwargs"]["interval"]=="tick"
    for change in [{"strike":"*"},{"interval":"1h"},{"right":"both"},
                   {"start_time_et":"10:20:00.000","end_time_et":"10:19:59.000"}]:
        with pytest.raises(cache.OnDemandSourceError):
            cache.normalize_source_requirement("option_history_exact_quote_tape",query(**change))


class FakeSettings:
    def __init__(self, root):
        self.root=root
        (root/"data/options").mkdir(parents=True,exist_ok=True)

    def assert_external_storage_binding(self,name):
        assert name=="options"

    def resolved_path(self,name):
        return self.root/name


def quote_response():
    rows=(
        {"symbol":"SPY","expiration":"2025-06-09","strike":604,
         "right":"call","timestamp":"2025-06-09T09:36:25.000-04:00",
         "bid":2.0,"ask":2.1,"bid_size":10,"ask_size":9},
        {"symbol":"SPY","expiration":"2025-06-09","strike":604,
         "right":"call","timestamp":"2025-06-09T09:36:26.000-04:00",
         "bid":2.02,"ask":2.12,"bid_size":11,"ask_size":10},
    )
    raw=_canonical_bytes(rows)
    return ThetaDataResponse(http_status=200,rows=rows,headers={},
        response_bytes=len(raw),elapsed_seconds=0.02,raw_body=raw,
        explicit_no_data=False)


def test_one_exact_tape_cached_and_reused_across_strategy_variants(tmp_path,monkeypatch):
    settings=FakeSettings(tmp_path)
    monkeypatch.setattr(cache,"MIN_FREE_STORAGE_BYTES",0)
    requests=[]
    def fetch(method,kwargs):
        requests.append((method,kwargs))
        return quote_response()
    first=cache.read_through_historical_options(settings,
          "option_history_exact_quote_tape",query(),provider_call=fetch)
    replay=cache.read_through_historical_options(settings,
          "option_history_exact_quote_tape",query(),provider_call=fetch)
    assert first["status"]=="FETCHED_AND_ARCHIVED"
    assert replay["status"]=="CACHE_HIT"
    assert len(first["source_rows"])==2
    assert first["query_id"]==replay["query_id"]
    assert first["source_sha256"]==replay["source_sha256"]
    assert len(requests)==1
    # Exact segmentation/interval requirements get NEW identities, not stale reuse.
    second=cache.read_through_historical_options(settings,
          "option_history_exact_quote_tape",query(interval="tick"),
          provider_call=fetch)
    third=cache.read_through_historical_options(settings,
          "option_history_exact_quote_tape",query(start_time_et="09:36:30.000"),
          provider_call=fetch)
    assert len({first["query_id"],second["query_id"],third["query_id"]})==3
    assert len(requests)==3
    assert all(m=="option_history_exact_quote_tape" for m,_ in requests)


def test_unqualified_tape_is_source_only_not_a_proven_fill(tmp_path,monkeypatch):
    settings=FakeSettings(tmp_path)
    monkeypatch.setattr(cache,"MIN_FREE_STORAGE_BYTES",0)
    first=cache.read_through_historical_options(settings,
          "option_history_exact_quote_tape",query(),
          provider_call=lambda m,k:quote_response())
    assert first["simulator_ready"] is False
    assert len(first["source_rows"])==2
