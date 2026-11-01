from __future__ import annotations

"""V104 synthetic signed V55/V65 exact requirements, no provider traffic."""
from datetime import date,datetime,timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import (
    closed_bar_signal, replay_source,
)
from packages.simulation.spy_v103_offline_orb_causal_account import signed
from scripts.run_spy_v65_full_june_offline_simulator_readiness import (
    _source_requirement,
)
from scripts import run_spy_v104_original_orb_source_recovery as v104

ET=ZoneInfo("America/New_York")
SHA="a"*64


def bars(day):
    b=[]
    for i in range(6):
        at=datetime(day.year,day.month,day.day,9,30,tzinfo=ET)+timedelta(minutes=i)
        n="601" if i==5 else "600"
        b.append({"symbol":"SPY","timestamp_utc":at.astimezone(ZoneInfo("UTC")).isoformat(),
                  "open":n,"high":n,"low":n,"close":n})
    return b


def fixture(day, *, missing):
    sig=closed_bar_signal(bars(day),session=day,source_sha256=SHA,
                          source_unit_id="synthetic-original")
    req=_source_requirement(sig)
    query=_fingerprint(req)
    receipt={"query_id":query,"state":"NOT_REGISTERED" if missing else "ARCHIVED",
             "archive_sha256":None if missing else SHA}
    if missing:
        replay=replay_source(sig,None)
    else:
        source={"status":"CACHE_HIT","source_sha256":SHA,"query_id":query,
                "exact_requirement":req,"source_rows":[
            {"timestamp":day.isoformat()+"T09:36:01-04:00",
             "symbol":"SPY","expiration":day.isoformat(),
             "strike":"601","right":"call","bid":"1.00","ask":"1.02",
             "bid_size":5,"ask_size":5},
            {"timestamp":day.isoformat()+"T09:36:02-04:00",
             "symbol":"SPY","expiration":day.isoformat(),
             "strike":"601","right":"call","bid":"1.00","ask":"1.02",
             "bid_size":5,"ask_size":5},
        ]}
        replay=replay_source(sig,source)
        assert replay["status"]=="UNRESOLVED_POSITION"
    row=signed({"session":day.isoformat(),
        "signal_fingerprint":sig["fingerprint"],
        "exact_option_requirement":req,"exact_option_receipt":receipt,
        "standalone_replay_report":replay,
        "standalone_replay_disposition":replay["status"]})
    return signed({"contract":v104.V65,"session_reports":[row],
                   "provider_requests":0,"broker_orders":0})


def test_missing_and_unresolved_are_independent_populations():
    older=fixture(date(2025,6,9),missing=False)
    later=fixture(date(2026,1,5),missing=True)
    missing,unresolved,observed=v104.frozen_missing_and_exits({
        "2025-06":older,"2026-01":later})
    assert observed==2
    assert len(missing)==1 and missing[0]["session"]=="2026-01-05"
    assert missing[0]["source_query_id"]==_fingerprint(
        missing[0]["request"])
    assert len(unresolved)==1
    assert unresolved[0]["session"]=="2025-06-09"
    assert unresolved[0]["entry_debit_usd"] is not None
    assert unresolved[0]["no_substituted_expiry_or_exit_price"] is True
    assert unresolved[0]["reason"]=="NO_FRESH_15_30_QUOTE_FOR_LIQUIDATION"


def test_only_exact_original_source_demand_emitted():
    x=fixture(date(2026,1,5),missing=True)
    missing,_,_=v104.frozen_missing_and_exits({"2026-01":x})
    items=list(v104.demand_items(missing))
    assert len(items)==1
    assert items[0]["candidate_id"]=="V103_ORB_20260105"
    assert items[0]["purpose"]=="required_exact_1s_entry_exit_tape"
    assert items[0]["method"]=="option_history_exact_quote_tape"
    assert items[0]["kwargs"]["date_et"]=="2026-01-05"
    assert items[0]["kwargs"]["expiration"]=="2026-01-05"
    assert items[0]["kwargs"]["interval"]=="1s"


def test_tampered_original_signed_v55_or_session_cannot_be_promoted():
    original=fixture(date(2026,1,5),missing=True)
    original["session_reports"][0]["standalone_replay_report"]["censor_reason"]="FAKE"
    with pytest.raises(v104.V104Error,match="NOT_SIGNED"):
        v104.frozen_missing_and_exits({"2026-01":original})


def test_existing_ambiguous_dispatch_is_not_treated_as_first_time_missing():
    original=fixture(date(2026,1,5),missing=True)
    row=original["session_reports"][0]
    row["exact_option_receipt"]["state"]="IN_FLIGHT"
    altered=signed({k:v for k,v in row.items() if k!="fingerprint"})
    original=signed({"contract":v104.V65,"session_reports":[altered],
                     "provider_requests":0,"broker_orders":0})
    with pytest.raises(v104.V104Error,match="REQUIRES_REVIEW"):
        v104.frozen_missing_and_exits({"2026-01":original})


def test_original_master_holdout_source_dates_refused():
    row=fixture(date(2026,1,5),missing=True)["session_reports"][0]
    # Even if a malicious summary signature is recomputed, query date and
    # signed original session cannot drift into the protected 2026 source span.
    wrong=dict(row)
    wrong["session"]="2026-05-13"
    altered=signed({k:v for k,v in wrong.items() if k!="fingerprint"})
    report=signed({"contract":v104.V65,"session_reports":[altered],
                  "provider_requests":0,"broker_orders":0})
    with pytest.raises(v104.V104Error,match="SOURCE_SESSION_DUPLICATE_OR_BAD_SHA"):
        v104.frozen_missing_and_exits({"2026-01":report})


def test_signed_immutable_plan_file_fails_closed_on_overwrite(tmp_path):
    file=tmp_path/"plan.json"
    d=v104.write_once(file,{"contract":"v104-test","count":45})
    assert v104.verified(d)
    assert json.loads(file.read_text())==d
    with pytest.raises(v104.V104Error,match="IMMUTABLE"):
        v104.write_once(file,{"contract":"v104-test","count":0})


def test_original_sha_mismatch_refuses_provider_stage(tmp_path):
    path=tmp_path/"wrong.zip"
    path.write_bytes(b"not a matching original archive")
    with pytest.raises(v104.V104Error,match="ORIGINAL_ZIP_SHA"):
        v104.read_original_v103(path)
