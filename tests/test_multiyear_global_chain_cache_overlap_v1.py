from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

import packages.data.multiyear_global_chain_cache_overlap_v1 as m
from packages.data.marketdata_candidate_batch_plan_v1 import _digest
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from test_multiyear_physical_chain_source_demand_v1 import _inputs
from packages.data.multiyear_physical_chain_source_demand_v1 import (
    freeze_physical_chain_source_demand,
)


@pytest.fixture(scope="module")
def demand():
    cross,inv=_inputs()
    return freeze_physical_chain_source_demand(cross,inv)


def _candidate(req,low=None,high=None,status="COMPLETE"):
    lo,hi=m._window(req["params"]["strike"])
    low=lo if low is None else Decimal(str(low))
    high=hi if high is None else Decimal(str(high))
    params={
        "date":req["snapshot_date"],"expiration":req["expiration"],
        "strike":f"{low:.2f}-{high:.2f}",
    }
    rid=_digest({"ticker":req["ticker"],"params":params,"mode":"HISTORICAL_EOD"})
    return {
        "request_identity":rid,"ticker":req["ticker"],"key":m._key(req),
        "strike_window":(low,high),"receipt_fingerprint":"a"*64,
        "original_status":status,"body_sha256":"b"*64,
        "body_bytes":101,"row_count":8,
    }


def _pointer(c):
    return {
        "source_request_identity":c["request_identity"],
        "source_status": "VERIFIED_NO_DATA" if c["original_status"]=="QUARANTINED"
                         else "COMPLETE",
        "source_body_sha256":c["body_sha256"],
        "source_receipt_fingerprint":c["receipt_fingerprint"],
        "source_strike_window":[str(x) for x in c["strike_window"]],
        "original_observed_rows":c["row_count"],"source_bytes":c["body_bytes"],
        "source_2025_pilot":False,"original_2025_no_data_proof":
            "c"*64 if c["original_status"]=="QUARANTINED" else None,
    }


def _freeze(doc,candidates,orphan=None):
    key_index=defaultdict(list)
    for item in candidates:
        key_index[item["key"]].append(item)
    return m.freeze_global_overlap(
        doc,key_index,orphan or {},verify_source=_pointer,
        catalog_fingerprint="d"*64,
        metadata_counts={"receipts":len(candidates),
                         "attempts":len(candidates)+(len(orphan or {})),
                         "orphan_attempts":len(orphan or {})},
    )


def test_full_exact_and_wider_reuse_without_any_paid_requests(demand):
    one,two=demand["requests"][:2]
    old=_candidate(one)
    wider=_candidate(two,
        low=m._window(two["params"]["strike"])[0]-Decimal("1.00"),
        high=m._window(two["params"]["strike"])[1]+Decimal("1.00"),
    )
    out=_freeze(demand,[old,wider])
    by_id={r["physical_request_identity"]:r for r in out["rows"]}
    for source in (old,wider):
        row=by_id[next(req["physical_request_identity"]
            for req in (one,two) if m._key(req)==source["key"])]
        assert row["source_status"]==m.REUSE
        assert row["reused_physical_source"]["source_request_identity"]==source["request_identity"]
        assert row["historical_option_fill_verified"] is False
    assert out["accepted_case_denominator"]==14902
    assert out["candidate_case_memberships"]==7838
    assert out["unique_physical_preview_queries"]==len(demand["requests"])
    assert out["provider_requests"]==out["new_paid_requests_authorized"]==0
    assert out["by_status"][m.MISSING]==len(demand["requests"])-2
    assert out["overlap_fingerprint"]==_fingerprint({
        k:v for k,v in out.items() if k!="overlap_fingerprint"
    })


def test_partial_strikes_never_claim_complete_or_proven_paid_demand(demand):
    req=demand["requests"][2]
    lo,hi=m._window(req["params"]["strike"])
    part=_candidate(req,high=hi-Decimal("0.01"))
    out=_freeze(demand,[part])
    row=next(x for x in out["rows"]
             if x["physical_request_identity"]==req["physical_request_identity"])
    assert row["source_status"]==m.PARTIAL
    assert row["reused_physical_source"] is None
    assert len(row["verified_existing_overlaps"])==1
    assert row["verified_existing_overlaps"][0]["full_window"] is False
    assert row["eligible_for_automatic_paid_retry"] is False


def test_no_data_only_exact_scope_other_strikes_missing(demand):
    req=demand["requests"][2]
    gap=_candidate(req,status="QUARANTINED")
    out=_freeze(demand,[gap])
    row=next(x for x in out["rows"]
             if x["physical_request_identity"]==req["physical_request_identity"])
    assert row["source_status"]==m.EXACT_GAP
    assert row["provider_market_absence_proven"] is False
    assert row["reused_physical_source"] is None
    different=_candidate(req,high=m._window(req["params"]["strike"])[1]-Decimal(".01"),
                         status="QUARANTINED")
    out2=_freeze(demand,[different])
    row2=next(x for x in out2["rows"]
             if x["physical_request_identity"]==req["physical_request_identity"])
    assert row2["source_status"]==m.MISSING
    assert row2["provider_market_absence_proven"] is False


def test_orphaned_attempt_blocks_same_key_but_not_unrelated_query(demand):
    req=demand["requests"][1]
    old=_candidate(req)
    orphan={old["request_identity"]:{
        "request_identity":old["request_identity"],
        "key":old["key"],"strike_window":old["strike_window"],
        "intent_fingerprint":"f"*64,
    }}
    out=_freeze(demand,[],orphan)
    row=next(x for x in out["rows"]
             if x["physical_request_identity"]==req["physical_request_identity"])
    assert row["source_status"]==m.UNRESOLVED
    assert row["intersecting_orphan_attempt_ids"]==[old["request_identity"]]
    assert row["eligible_for_automatic_paid_retry"] is False
    assert out["by_status"][m.MISSING]==len(demand["requests"])-1


def test_signed_metadata_and_orphan_index_do_not_reopen_raw_chain(tmp_path):
    root=tmp_path/"cache"
    source={"ticker":"AAPL","params":{
        "date":"2025-07-01","expiration":"2025-08-15","strike":"100.00-110.00",
    }}
    rid=m._identity(source)
    paths=m._paths_root(root,rid)
    paths.receipt.parent.mkdir(parents=True)
    receipt={"contract":m.CHAIN_CONTRACT,"status":"COMPLETE",
             "request_identity":rid,"endpoint":"options/chain/AAPL/",
             "params":source["params"],"body_sha256":"b"*64,
             "body_bytes":101,"row_count":8}
    receipt["receipt_fingerprint"]=_fingerprint(receipt)
    paths.receipt.write_text(json.dumps(receipt),encoding="utf-8")
    attempt={"contract":m.CHAIN_CONTRACT,
             "status":"REQUEST_STARTED_CHARGE_UNKNOWN_UNTIL_RECEIPT",
             "request_identity":rid,"endpoint":receipt["endpoint"],
             "params":source["params"],"automatic_retry_permitted":False}
    attempt["intent_fingerprint"]=_fingerprint(attempt)
    paths.attempt.write_text(json.dumps(attempt),encoding="utf-8")
    by_key,orphan,catalog,counts=m._metadata_index(root)
    assert len(by_key[("AAPL","2025-07-01","2025-08-15")])==1
    assert orphan=={}
    assert counts=={"receipts":1,"attempts":1,"orphan_attempts":0,
                    "signed_proof_or_recovery_sidecars":0}
    assert len(catalog)==64
    sidecar={"request_identity":rid,"contract":"test-signed-sidecar",
             "status":"METADATA_ONLY_FIXTURE"}
    sidecar["recovery_fingerprint"]=_fingerprint(sidecar)
    paths.recovery.write_text(json.dumps(sidecar),encoding="utf-8")
    _,_,catalog_after,counts_after=m._metadata_index(root)
    assert counts_after["signed_proof_or_recovery_sidecars"]==1
    assert catalog_after!=catalog
    receipt["row_count"]=9
    paths.receipt.write_text(json.dumps(receipt),encoding="utf-8")
    with pytest.raises(m.GlobalChainOverlapError,match="receipt structure changed"):
        m._metadata_index(root)


def test_original_2025_closeout_matching_source_SHA_is_enforced(tmp_path,monkeypatch,demand):
    req=demand["requests"][0]
    candidate=_candidate(req)
    paths=m._paths_root(tmp_path,candidate["request_identity"])
    settings=SimpleNamespace(resolved_path=lambda x:tmp_path)
    fake={"status":"COMPLETE","body_sha256":"b"*64}
    monkeypatch.setattr(m,"_valid_receipt",lambda *args,**kw:fake)
    old25={candidate["request_identity"]:{
        "status":"REUSED_VERIFIED","raw_body_sha256":"b"*64,
    }}
    pointer=m._candidate({},candidate,settings=settings,
                         accepted25=old25,validated={})
    assert pointer["source_2025_pilot"] is True
    old25[candidate["request_identity"]]["raw_body_sha256"]="a"*64
    with pytest.raises(m.GlobalChainOverlapError,match="pilot receipt drift"):
        m._candidate({},candidate,settings=settings,accepted25=old25,validated={})


def test_forged_demand_and_coverage_count_fail_closed(demand):
    broken={**demand,"provider_requests":1}
    with pytest.raises(m.GlobalChainOverlapError,match="preview changed"):
        _freeze(broken,[])
    broken={**demand,"requests":demand["requests"][:-1]}
    broken["demand_fingerprint"]=_fingerprint({
        k:v for k,v in broken.items() if k!="demand_fingerprint"
    })
    with pytest.raises(m.GlobalChainOverlapError,match="preview changed"):
        _freeze(broken,[])
