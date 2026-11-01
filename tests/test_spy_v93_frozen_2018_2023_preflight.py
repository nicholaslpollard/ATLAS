from __future__ import annotations

"""Synthetic V93 pre-provider source verification and immutable SHA ancestry."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from scripts import run_spy_v93_frozen_2018_2023_preflight as v93


def fixture(folder):
    months=[]
    for y in v93.YEARS:
        for m in range(1,13):
            months.append({
                "year":y,"month":m,
                "status":"ORIGINAL_FULL_SHA_VERIFIED",
                "unit_id":f"unit{y}-{m:02d}",
                "canonical_sha256":"a"*64,
                "raw_bundle_sha256":"b"*64,
                "original_full_sha_verified":True,
            })
    inventory=v93.signed({
        "contract":"atlas-v92-pre2024-original-spy-monthly-minute-inventory-v1-month-inventory-v1",
        "date_boundary_start":"2018-01-01",
        "date_boundary_end":"2023-12-31",
        "months":months,
        "no_option_data_accessed":True,
        "no_provider_or_broker_clients":True,
    })
    report=v93.signed({
        "contract":"atlas-v92-pre2024-original-spy-monthly-minute-inventory-v1",
        "inventory_sha":inventory["fingerprint"],
        "months_examined":72,
        "available_original_spy_months_full_sha_verified":72,
        "absent_or_invalid_months":0,
        "broker_orders":0,"provider_requests":0,
    })
    folder.mkdir()
    for path,obj in [
        ("original_month_inventory.json",inventory),
        ("summary.json",report),
    ]:
        (folder/path).write_text(json.dumps(obj))
    return inventory,report,months


def fake_discover(layout,*,target_year,target_month,progress):
    return [SimpleNamespace(
        year=target_year,month=target_month,symbols=("SPY",),
        unit_id=f"unit{target_year}-{target_month:02d}",
        canonical_sha256="a"*64,raw_bundle_sha256="b"*64,
        canonical_path=Path("not_a_symlink"),
        raw_bundle_path=Path("not_a_symlink"),
        checkpoint_path=Path("not_a_symlink"),
    )]


def test_v93_frozen_inventory_72_months_rehashed_before_any_options(tmp_path):
    src=tmp_path/"v92"
    inv,report,_=fixture(src)
    output=tmp_path/"v93"
    with patch.object(v93,"EXPECTED_V92_INVENTORY_SHA",inv["fingerprint"]), \
         patch.object(v93,"EXPECTED_V92_SUMMARY_SHA",report["fingerprint"]):
        result=v93.run(src,output,
                       layout=SimpleNamespace(),
                       discover=fake_discover,
                       verify=lambda _:{"accepted":True},
                       reporter=lambda _:None)
    assert v93.verified(result)
    assert result["full_source_months_sha_reverified"]==72
    assert result["provider_calls"]==result["broker_orders"]==0
    assert result["protected_master_2026_holdout_accessed"] is False
    assert len(result["historical_cohorts"])==6
    assert (output/"preflight.json").exists()


def test_v93_modified_v92_root_fails_before_output_creation(tmp_path):
    src=tmp_path/"v92"
    fixture(src)
    out=tmp_path/"never_created"
    with pytest.raises(v93.V93Error,match="EVIDENCE_ROOTS_OR_CENSUS"):
        v93.run(src,out,layout=SimpleNamespace(),discover=fake_discover,
                verify=lambda _:{"accepted":True})
    assert not out.exists()


def test_v93_different_local_original_source_is_rejected_even_if_v92_signed(tmp_path):
    src=tmp_path/"v92"
    inv,report,_=fixture(src)
    out=tmp_path/"never_created"
    with patch.object(v93,"EXPECTED_V92_INVENTORY_SHA",inv["fingerprint"]), \
         patch.object(v93,"EXPECTED_V92_SUMMARY_SHA",report["fingerprint"]):
        with pytest.raises(v93.V93Error,match="SOURCE_BYTES_DIFFER"):
            v93.run(src,out,layout=SimpleNamespace(),discover=fake_discover,
                verify=lambda _:{"accepted":False})
    assert not out.exists()
