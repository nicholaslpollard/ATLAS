from __future__ import annotations

"""V92 offline source evidence inventory: no network access."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.run_spy_v92_pre2024_original_minute_coverage import (
    V92Error,run,verified,
)


def test_frozen_2023_inventory_records_present_absent_and_bad_sha(tmp_path):
    root=tmp_path/"ckpts"/"native_units"/"1m"
    for m in (1,3):
        (root/"year=2023"/f"month={m:02d}").mkdir(parents=True)
    unit=lambda month:SimpleNamespace(
        year=2023,month=month,symbols=("SPY",),unit_id=f"spy{month}",
        canonical_sha256="a"*64,raw_bundle_sha256="b"*64,
        canonical_path=tmp_path/"canonical.parquet",
        raw_bundle_path=tmp_path/"raw.json.gz",
        checkpoint_path=tmp_path/"checkpoint.json",
    )
    visited=[]
    def discover(layout,*,target_year,target_month,progress):
        visited.append((target_year,target_month))
        return [unit(target_month)]
    def verify(u):
        return {"accepted":u.month==1,
                "errors":[] if u.month==1 else ["synthetic_corrupt_month"]}
    output=tmp_path/"inventory"
    r=run(output,layout=SimpleNamespace(checkpoints=tmp_path/"ckpts"),
          discover=discover,verifier=verify,
          start_year=2023,end_year=2023,reporter=lambda _:None)
    assert verified(r)
    assert r["months_examined"]==12
    assert r["available_original_spy_months_full_sha_verified"]==1
    assert r["absent_or_invalid_months"]==11
    assert r["provider_requests"]==r["broker_orders"]==0
    assert r["master_holdout_accessed"] is False
    inventory=json.loads((output/"original_month_inventory.json").read_text())
    assert verified(inventory)
    assert inventory["fingerprint"]==r["inventory_sha"]
    assert visited==[(2023,1),(2023,3)]
    assert inventory["counts"]=={
        "ORIGINAL_FULL_SHA_VERIFIED":1,
        "SOURCE_SHA_OR_FILE_INVALID":1,
        "MONTH_NOT_PRESENT_LOCALLY":10,
    }


def test_requires_unmodified_output_and_rejects_any_2024_or_later_read(tmp_path):
    with pytest.raises(V92Error,match="FROZEN_PRE2024"):
        run(tmp_path/"bad",start_year=2024,end_year=2024)
    assert not (tmp_path/"bad").exists()
    with pytest.raises(V92Error,match="FROZEN_PRE2024"):
        run(tmp_path/"bad2",start_year=2017,end_year=2023)
    existing=tmp_path/"existing";existing.mkdir()
    with pytest.raises(V92Error,match="OUTPUT_EXISTS"):
        run(existing,start_year=2023,end_year=2023)


def test_symlink_source_month_refused_without_discovery(tmp_path):
    root=tmp_path/"ckpts"/"native_units"/"1m"/"year=2023"
    root.mkdir(parents=True)
    target=tmp_path/"somewhere";target.mkdir()
    link=root/"month=01"
    try:
        link.symlink_to(target,target_is_directory=True)
    except OSError:
        pytest.skip("Windows symlink privilege unavailable")
    calls=[]
    output=tmp_path/"inventory"
    r=run(output,layout=SimpleNamespace(checkpoints=tmp_path/"ckpts"),
          discover=lambda *a,**k:calls.append(k),
          start_year=2023,end_year=2023,reporter=lambda _:None)
    assert verified(r)
    assert calls==[]
    doc=json.loads((output/"original_month_inventory.json").read_text())
    assert doc["months"][0]["status"]=="REJECTED_SYMLINK_MONTH"
