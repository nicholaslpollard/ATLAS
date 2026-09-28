from __future__ import annotations

"""Targeted native raw unit source from immutable request pairs, no provider reads."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

import packages.data.multiyear_native_eod_close_source_v1 as m
from packages.data.alpaca_v2_acquisition import UNIT_CONTRACT
from packages.data.marketdata_accepted_stock_candidate_export_v1 import _file_sha
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_option_stock_eod_preflight_v1 import CONTRACT as DEMAND_CONTRACT


def _signed(x, k):
    x[k] = _fingerprint(x)
    return x


def _source(monkeypatch):
    native = _signed({
        "provider_requests": 0, "protected_outcomes_read": 0,
        "accepted_native_source": {"source_fingerprint": "genuine-test"},
    }, "source_fingerprint")
    monkeypatch.setattr(m, "NATIVE_FP", native["source_fingerprint"])
    tickets = []
    for i, day in enumerate(("2022-03-03", "2022-03-07"), 1):
        tickets.append({
            "request_identity": str(i) * 64, "ticker": "TEST",
            "instrument_id": "UUID-1", "session_et": day,
            "stock_close_has_not_been_read": True,
            "required_native_field": "RAW_AS_TRADED_1DAY_REGULAR_CLOSE",
        })
    demand = _signed({
        "contract": DEMAND_CONTRACT, "status": "OFFLINE_NATIVE_STOCK_EOD_DEMAND_NOT_SOURCE_PROOF",
        "accepted_native_fingerprint": native["source_fingerprint"],
        "provider_requests": 0, "protected_2026_outcomes_read": 0,
        "native_raw_closes_read": 0, "portfolio_pnl_authority": False,
        "requests": tickets,
    }, "demand_fingerprint")
    return native, demand


def test_read_bounded_original_unit_preserves_exact_missing_gap(tmp_path):
    root = tmp_path / "native-v2"
    layout = SimpleNamespace(
        root=root, checkpoints=root / "checkpoints",
        canonical_daily=root / "canonical",
    )
    uid = "a" * 64
    record = {
        "unit_id": uid, "year": 2022, "batch_index": 0,
        "policy_sha256": "b" * 64, "universe_sha256": "c" * 64,
        "symbols": ["TEST"],
    }
    part = Path("year=2022") / "batch=0000"
    checkpoint = layout.checkpoints / "native_units" / "1d" / part / (uid[:20] + ".json")
    canonical = layout.canonical_daily / part / (uid[:20] + ".parquet")
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    try:
        con.execute("""
            CREATE TABLE original AS SELECT
            'TEST'::VARCHAR AS symbol, DATE '2022-03-03' AS session_date,
            100.0::DOUBLE AS open, 101.5::DOUBLE AS close,
            'alpaca'::VARCHAR AS provider, 'stock_daily_aggregates'::VARCHAR AS dataset,
            '1d'::VARCHAR AS timeframe, 'regular'::VARCHAR AS session_segment,
            FALSE AS is_adjusted, ?::VARCHAR AS source_id
        """, [f"alpaca:sip:1Day:raw:asof=-:v2:unit={uid}"])
        con.execute("COPY original TO '" + str(canonical).replace("'", "''") + "' (FORMAT PARQUET)")
    finally:
        con.close()
    cp = {
        "contract": UNIT_CONTRACT, "status": "COMPLETE",
        "unit_id": uid, "unit": record, "policy_sha256": record["policy_sha256"],
        "universe_sha256": record["universe_sha256"],
        "canonical": {"path": str(canonical), "sha256": _file_sha(canonical)},
        "provider_rejections": [],
    }
    checkpoint.write_text(json.dumps(cp), encoding="utf-8")
    wanted = [
        {"request_identity": "1" * 64, "ticker": "TEST", "instrument_id": "UUID-1",
         "session_et": "2022-03-03"},
        {"request_identity": "2" * 64, "ticker": "TEST", "instrument_id": "UUID-1",
         "session_et": "2022-03-07"},
    ]
    rows, evidence = m._read_one_unit(record, layout, wanted)
    assert evidence["verified_exact_pairs"] == 1
    assert [x["status"] for x in rows] == [
        "VERIFIED_NATIVE_RAW_EOD_CLOSE", "NO_RAW_NATIVE_DAILY_BAR_FOR_EXACT_SESSION"
    ]
    assert rows[0]["raw_as_traded_close"] == "101.5"
    assert rows[0]["option_clock_match_proven"] is False
    canonical.write_bytes(b"tampered")
    with pytest.raises(m.NativeEodCloseError, match="SHA"):
        m._read_one_unit(record, layout, wanted)


def test_requested_units_only_and_immutable_source(monkeypatch, tmp_path):
    native, demand = _source(monkeypatch)
    record = {"unit_id": "u1", "year": 2022, "symbols": ["TEST"]}
    def plan_reader(settings, source, pairs):
        assert pairs == {
            ("TEST", date(2022,3,3)), ("TEST", date(2022,3,7))
        }
        return [record], {
            "native_acceptance_fingerprint": "a" * 64,
            "native_plan_sha256": "b" * 64,
        }, SimpleNamespace()
    monkeypatch.setattr(m, "_accepted_native_plan", plan_reader)
    calls = []
    def reader(r, layout, items):
        calls.append(r["unit_id"])
        return [
            {
                "request_identity": x["request_identity"],
                "status": "VERIFIED_NATIVE_RAW_EOD_CLOSE",
                "session_et": x["session_et"],
                "native_canonical_sha256": "c" * 64,
            } for x in items
        ], {"native_unit_id": r["unit_id"], "native_canonical_sha256": "c" * 64}
    settings = SimpleNamespace(
        resolved_path=lambda p: tmp_path / p,
        assert_external_storage_binding=lambda p:
            None if p == "options" else pytest.fail("wrong source binding"),
    )
    out = m.resolve_native_eod_closes(
        settings, native, demand, workers=3, unit_reader=reader,
    )
    assert calls == ["u1"]
    assert out["unique_native_daily_units_verified"] == 1
    assert out["verified_exact_native_raw_closes"] == 2
    assert out["provider_requests"] == 0
    path, status = m.persist_native_eod_closes(settings, out)
    assert status == "WRITTEN_IMMUTABLE_NATIVE_CLOSE_SOURCE"
    assert m.persist_native_eod_closes(settings, out)[0] == path
    path.write_text("modified", encoding="utf-8")
    with pytest.raises(ValueError):
        m.persist_native_eod_closes(settings, out)


def test_protected_2026_request_fails_before_native_read(monkeypatch, tmp_path):
    native, demand = _source(monkeypatch)
    demand["requests"][0]["session_et"] = "2026-03-03"
    demand = _signed({k: v for k, v in demand.items() if k != "demand_fingerprint"},
                     "demand_fingerprint")
    monkeypatch.setattr(m, "_accepted_native_plan",
                        lambda *_: pytest.fail("must not read 2026 native source"))
    settings = SimpleNamespace(assert_external_storage_binding=lambda c: None)
    with pytest.raises(m.NativeEodCloseError, match="protected"):
        m.resolve_native_eod_closes(settings, native, demand)
