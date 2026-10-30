from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
import pytest
from types import SimpleNamespace
import hashlib

from packages.data.spy_v51_native_minute_orb_inventory import preview, _verify_monthly_unit_with_progress

ET=ZoneInfo("America/New_York")


def bar(i,*,hi="101",lo="99",cl="100"):
    stamp=datetime(2025,6,9,9,30,tzinfo=ET)+timedelta(minutes=i)
    return {
        "timestamp_utc":stamp.astimezone(ZoneInfo("UTC")),
        "symbol":"SPY","open":"100","high":hi,"low":lo,"close":cl,
    }


def report(rows):
    return preview(rows,session=date(2025,6,9),
                   source_sha256="a"*64,source_unit_id="native_v2_sha_receipt")


def test_first_containing_minute_five_minute_range_source_preview_no_trade():
    a=[bar(i) for i in range(5)]
    a += [bar(5,hi="100.9",lo="99.2"),bar(6,hi="102",lo="99.5",cl="101.5")]
    r=report(a)
    assert r["opening_high"]=="101"
    assert r["opening_low"]=="99"
    assert r["first_possible_breakout_minute"]["minute_start_et"].startswith("2025-06-09T09:36:00")
    assert r["first_possible_breakout_minute"]["direction_possible"]=="CALL"
    assert r["first_possible_breakout_minute"]["minute_close_available_no_earlier_than_et"].startswith("2025-06-09T09:37:00")
    assert r["historical_pit_publication_proven"] is False
    assert r["historical_option_contract_selected"] is False
    assert r["strategy_pnl"] is None and r["provider_calls"]==0
    assert r["fingerprint"]


def test_unobserved_minute_cannot_hide_an_earlier_breakout():
    a=[bar(i) for i in range(5)]+[bar(7,hi="102",lo="100",cl="101")]
    r=report(a)
    assert r["first_possible_breakout_minute"] is None
    assert "MISSING_MINUTE_BEFORE_FIRST_POSSIBLE_BREAKOUT" in r["source_reason_codes"]


def test_source_double_breakout_minute_is_explicitly_ambiguous():
    a=[bar(i) for i in range(5)]+[bar(5,hi="102",lo="98")]
    r=report(a)
    assert r["first_possible_breakout_minute"]["direction_possible"]=="BOTH_AMBIGUOUS"
    assert "BOTH_BREAKOUT_DIRECTIONS_IN_FIRST_CANDIDATE_MINUTE" in r["source_reason_codes"]


def test_source_missing_opening_minute_is_not_a_strategy_loss():
    r=report([bar(0),bar(1),bar(3),bar(4),bar(5,hi="102",lo="99")])
    assert r["opening_range_completely_observed"] is False
    assert r["first_possible_breakout_minute"] is None
    assert r["strategy_pnl"] is None


def test_wrong_symbol_duplicate_crossed_or_out_of_session_data_rejected():
    a=[bar(i) for i in range(5)]
    with pytest.raises(ValueError,match="DUPLICATE"):
        report(a+[a[1]])
    wrong=[*a]
    wrong[0]=dict(wrong[0],symbol="QQQ")
    with pytest.raises(ValueError,match="MISMATCH"):
        report(wrong)
    wrong=[*a]
    wrong[1]=dict(wrong[1],high="50")
    with pytest.raises(ValueError,match="GEOMETRY"):
        report(wrong)
    wrong=[*a]
    wrong[1]=dict(wrong[1],timestamp_utc="2025-06-10T13:31:00+00:00")
    with pytest.raises(ValueError,match="MISMATCH"):
        report(wrong)


def test_full_original_sha_stream_reports_every_10pct_and_never_skips_raw_bundle(tmp_path):
    canon=tmp_path/"SPY-2025-06.parquet"
    raw=tmp_path/"original-source.tar"
    canonical_bytes=b"canonical" * 120
    raw_bytes=b"original-raw-source" * 200
    canon.write_bytes(canonical_bytes)
    raw.write_bytes(raw_bytes)
    unit=SimpleNamespace(
        checkpoint_path=tmp_path/"checkpoint.json",unit_id="test-native-unit",
        status="COMPLETE",canonical_path=canon,raw_bundle_path=raw,
        canonical_sha256=hashlib.sha256(canonical_bytes).hexdigest(),
        raw_bundle_sha256=hashlib.sha256(raw_bytes).hexdigest(),
    )
    lines=[]
    result=_verify_monthly_unit_with_progress(unit,lines.append)
    assert result["accepted"] is True
    assert "STAGE_START original monthly SHA verification" in lines[0]
    assert [f"PROGRESS_{x}PCT" for x in range(10,101,10)]==[
        next(line.split()[0] for line in lines if line.startswith(f"PROGRESS_{x}PCT"))
        for x in range(10,101,10)
    ]
    assert sum(line.startswith("SOURCE_VERIFIED") for line in lines)==2
    assert lines[-1].startswith("STAGE_PASS")
    raw.write_bytes(b"tampered original")
    changed=_verify_monthly_unit_with_progress(unit,lines.append)
    assert changed["accepted"] is False
    assert any("raw_bundle sha256 mismatch" in x for x in changed["errors"])
    assert lines[-1].startswith("STAGE_FAIL")
