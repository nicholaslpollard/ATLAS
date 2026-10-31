from __future__ import annotations

from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

import pytest

from packages.simulation.spy_v80_exit_price_protection_shadow import _signed
from scripts import run_spy_v80_signed_exit_price_protection as v80


def synth(date_str,policy,lag):
    t=f"{date_str}T10:00:01-04:00"
    a=f"{date_str}T10:00:{lag+1:02d}-04:00"
    inner=_signed({
        "parent_v65_sha":"a"*64,
        "original_option_archive_sha256":"b"*64,
        "selected_contract":{"symbol":"SPY"},
        "actual_broker_fills":0,"provider_requests":0,
        "status":"CLOSED_QUOTE_REFERENCE",
        "trade_net_pnl":"52.60",
        "events":[
            {"type":"ORIGINAL_ENTRY_REUSED","qty":3,
             "at_et":f"{date_str}T09:35:00-04:00","debit_plus_fees":"301.95"},
            {"type":"EXIT_INTENT","trigger_at_et":t,
             "reference_bid":"1.24","earliest_action":a},
            {"type":"MODELED_SELL_TO_CLOSE_BID_REFERENCE",
             "at_et":a,"qty":3,"observed_bid":"1.19",
             "observed_bid_size":10,"actual_broker_fill":False,
             "limit_order_fill_guaranteed":False},
        ],
    })
    return _signed({
        "contract":"atlas-v76-preregistered-multi-exit-causal-quote-research-v1",
        "session":date_str,"policy":policy,"lag_seconds":lag,
        "parent_v65_sha":"a"*64,
        "original_source_sha256":"b"*64,
        "status":"CLOSED_QUOTE_REFERENCE","reason":"REGISTERED_VARIANT_STOP",
        "trade_net_pnl":"52.60","provider_calls":0,"broker_orders":0,
        "v74_inner_quote_shadow_report":inner,
    })


def sample_zip(path):
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED) as z:
        for month in range(7,13):
            m=f"2025{month:02d}"
            count=11 if month==12 else 10
            manifests=[]
            for policy in v80.POLICIES:
                for lag in v80.LAGS:
                    rec=[]
                    for day in range(1,count+1):
                        d=f"2025-{month:02d}-{day:02d}"
                        doc=synth(d,policy,lag)
                        filename=f"{d}_{policy}_{lag}s.json.gz"
                        compressed=gzip.compress(json.dumps(doc,sort_keys=True).encode(),mtime=0)
                        z.writestr(f"original\\{m}\\{filename}",compressed)
                        rec.append({
                            "session":d,"status":doc["status"],"reason":doc["reason"],
                            "net_pnl":doc["trade_net_pnl"],
                            "stored_file":filename,
                            "stored_gzip_sha256":hashlib.sha256(compressed).hexdigest(),
                            "event_report_sha":doc["fingerprint"],
                            "original_row_fingerprint":doc["parent_v65_sha"],
                        })
                    manifests.append({
                        "name":policy,"lag_seconds":lag,
                        "closed_trade_count":count,"unresolved_days":[],
                        "daily_event_receipts":rec,
                    })
            month_doc=_signed({
                "contract":"atlas-v76-preregistered-multi-exit-causal-quote-research-v1",
                "provider_calls":0,"broker_orders":0,
                "actual_historical_broker_option_fills":0,
                "policies":manifests,
            })
            z.writestr(f"original\\{m}\\summary.json",json.dumps(month_doc))


def test_six_month_original_journals_roundtrip_and_no_broker_calls(tmp_path):
    source=tmp_path/"source.zip"
    sample_zip(source)
    outputs=[]
    result=v80.run(source,tmp_path/"reports",callback=outputs.append)
    assert result["original_journals_sha_and_signature_verified"]==244
    assert result["scenarios_written"]==976
    assert result["broker_orders"]==result["provider_calls"]==0
    assert result["actual_realized_option_pnl"] is None
    assert all(v=={"ADVERSE_DRIFT_OUTSIDE_PRICE_PROTECTION":61}
               for v in result["marketability_counts"].values())
    assert (tmp_path/"reports"/"daily_price_protection.json").is_file()
    assert outputs[0].startswith("STAGE_START V80")
    assert any(x.startswith("PROGRESS_100PCT") for x in outputs)
    assert outputs[-1].startswith("COMPLETE V80")


def test_corrupted_compressed_archive_fails_closed(tmp_path):
    source=tmp_path/"source.zip"
    sample_zip(source)
    damaged=tmp_path/"bad.zip"
    with zipfile.ZipFile(source) as original,zipfile.ZipFile(damaged,"w") as rewritten:
        for name in original.namelist():
            data=original.read(name)
            if name.endswith(".json.gz") and "202507" in name and "runner" in name:
                data=data+b"x"
            rewritten.writestr(name,data)
    with pytest.raises(ValueError,match="COMPRESSED_ORIGINAL_SHA_MISMATCH"):
        v80.run(damaged,tmp_path/"blocked",callback=lambda _:None)
    assert not (tmp_path/"blocked").exists()
