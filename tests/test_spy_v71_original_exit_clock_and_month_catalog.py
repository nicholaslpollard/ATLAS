from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_spy_v71_original_exit_clock_and_month_catalog as v71


def sample_reports(tmp_path):
    folder = tmp_path / "june"
    folder.mkdir()
    rejected_days = set(v71.EXPECTED_REJECTS)
    rows = []
    start = date(2025, 6, 2)
    selected = []
    for i in range(29):
        day = start + timedelta(days=i)
        if day.weekday() >= 5:
            continue
        s = day.isoformat()
        has_contract = day.weekday() in (0, 2, 4)
        if has_contract:
            selected.append(s)
        contract = ({
            "symbol": "SPY", "date_et": s, "expiration": s,
            "strike": "598", "right": "call",
        } if has_contract else None)
        req = ({
            "method": "option_history_exact_quote_tape",
            "provider": "thetadata",
            "kwargs": {**contract, "interval": "1s"}
        } if contract else None)
        receipt = ({
            "state": "ARCHIVED", "query_id": v71._fingerprint(req),
            "archive_sha256": "f" * 64,
        } if req else None)
        events = []
        status = "NO_SIGNAL"
        if has_contract:
            status = ("UNRESOLVED_POSITION" if s in rejected_days
                      else "NO_ENTRY")
        if s in rejected_days:
            events = [
                {"type": "MODELED_ENTRY_QUOTE_REFERENCE",
                 "ask": "1.23", "qty": 4, "at_et": s + "T09:37:02-04:00"},
                {"type": "EXIT_SOURCE_REJECTION",
                 "at_et": s + "T10:00:01-04:00",
                 "reason": "QUOTE_SPREAD_ABOVE_15_PERCENT", "row": 1},
            ]
        report = v71.signed({
            "session": s, "status": status,
            "censor_reason": "UNQUALIFIED_EXIT_QUOTE_PATH"
                if s in rejected_days else None,
            "events": events,
            "source_query_id": receipt["query_id"] if receipt else None,
            "source_sha256": receipt["archive_sha256"] if receipt else None,
            "actual_fills": 0, "quote_reference_not_broker_execution": True,
        })
        row = v71.signed({
            "session": s, "signal_fingerprint": "a" * 64,
            "native_minute_source_sha256": "b" * 64,
            "selected_contract": contract, "exact_option_receipt": receipt,
            "exact_option_requirement": req,
            "standalone_replay_report": report,
        })
        rows.append(row)
    assert len(rows) == 21 and len(selected) == 13
    pre = v71.signed({
        "contract": v71.V65, "session_reports": rows
    })
    post = v71.signed({
        "contract": v71.V65, "session_reports": rows,
        "option_source_state_counts": {"ARCHIVED": 13}
    })
    src = v71.signed({
        "contract": v71.V69, "original_preflight_sha": pre["fingerprint"],
        "runtime_source_receipt": {
            "source_uses_requested": 13, "source_uses_resolved": 13,
        }
    })
    chunk = v71.signed({
        "contract": v71.V69, "original_v65_preflight_sha": pre["fingerprint"],
        "original_v65_post_source_sha": post["fingerprint"],
        "source_state_counts": {"ARCHIVED": 13},
        "unresolved_positions": 2,
        "unresolved_source_requirements": []
    })
    top = v71.signed({
        "contract": v71.V69,
        "start": "2025-06-02", "end": "2025-06-30",
        "weekdays": 21, "unresolved_option_positions": 2,
        "unresolved_source_or_underlying_chunks": 0,
        "chunks": 1, "broker_orders": 0,
        "chunk_summaries": [{"fingerprint": chunk["fingerprint"]}],
    })
    for name, doc in (
        ("summary.json", top),
        ("chunk_0001.summary.json", chunk),
        ("chunk_0001.replay.json", post),
        ("chunk_0001.preflight.json", pre),
        ("chunk_0001.sources.json", src),
    ):
        (folder / name).write_text(json.dumps(doc), encoding="utf8")
    return folder, top, rows


def quote_source(row):
    day = row["session"]
    contract = row["selected_contract"]
    return {
        "query_id": row["exact_option_receipt"]["query_id"],
        "exact_requirement": row["exact_option_requirement"],
        "source_sha256": "f" * 64,
        "source_rows": [
            {"timestamp_et": day+"T10:00:00-04:00",
             "bid": "1.02", "ask": "1.03", "bid_size": 10, "ask_size": 8},
            {"timestamp_et": day+"T10:00:01-04:00",
             "bid": "0.76", "ask": "1.25", "bid_size": 10, "ask_size": 8},
            {"timestamp_et": day+"T10:00:02-04:00",
             "bid": "0.82", "ask": "0.83", "bid_size": 8, "ask_size": 8},
            {"timestamp_et": day+"T10:00:03-04:00",
             "bid": "0.62", "ask": "0.63", "bid_size": 9, "ask_size": 9},
        ],
    }


def test_full_june_provenance_and_causal_exit_window(tmp_path):
    folder, summary, rows = sample_reports(tmp_path)
    v, rejected = v71.validate_full_june(folder,
        expected_sha=summary["fingerprint"])
    assert v["fingerprint"] == summary["fingerprint"]
    assert sorted(rejected) == list(v71.EXPECTED_REJECTS)
    for day in v71.EXPECTED_REJECTS:
        row = rejected[day]
        cache = quote_source(row)
        result = v71.analyze_rejected_exit(
            row, setting=None,
            cache_reader=lambda *args: {
                "cache_evidence": "CACHE_HIT", "source": cache,
            })
        assert result["fingerprint"] == v71._fingerprint({
            k: v for k, v in result.items() if k != "fingerprint"
        })
        assert result["original_rejection_at_et"] == day + "T10:00:01-04:00"
        assert result["last_valid_quote_before_rejection"]["raw_bid"] == "1.02"
        assert (result["first_valid_quote_after_rejection"]["timestamp_et"] ==
                day + "T10:00:02-04:00")
        assert result["qualified_quote_count_after_rejection_within_60s"] == 2
        assert result["rejected_quote_counts"] == {
            "QUOTE_SPREAD_ABOVE_15_PERCENT": 1
        }
        assert result["skip_invalid_observation_authorized"] is False
        assert result["quote_reference_pnl_revised"] is False


def test_catalog_provides_month_metadata_without_automatically_sha_approving(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    month = checkpoints / "native_units/1m/year=2025/month=05"
    month.mkdir(parents=True)
    canonical = tmp_path / "original.parquet"
    raw = tmp_path / "original.json.gz"
    canonical.write_bytes(b"abc")
    raw.write_bytes(b"xyz")
    unit = SimpleNamespace(
        symbols=("SPY",),
        canonical_path=canonical,
        raw_bundle_path=raw,
        canonical_sha256="e" * 64,
        raw_bundle_sha256="d" * 64,
        unit_id="native_sha",
    )
    calls = []
    def discovery(layout, *, target_year, target_month, progress):
        calls.append((target_year, target_month))
        return (unit,)
    result = v71.native_month_catalog(
        layout=SimpleNamespace(checkpoints=checkpoints), discover=discovery,
    )
    assert calls == [(2025, 5)]
    assert result["ready_for_full_sha_verification"] == 1
    assert result["original_sha_verified_for_these_months"] is False
    assert result["months"][0]["status"] == (
        "READY_FOR_FULL_ORIGINAL_SHA_PREFLIGHT"
    )
    assert result["months"][0]["original_bytes"] == 6


def test_missing_archive_does_not_invent_exit_or_allow_provider_calls(tmp_path):
    _, _, rows = sample_reports(tmp_path)
    source_row = next(r for r in rows if r["session"] == "2025-06-04")
    with pytest.raises(v71.V71Error, match="ACQUIRE_REQUIRED"):
        v71.analyze_rejected_exit(
            source_row, setting=None,
            cache_reader=lambda *args: {
                "cache_evidence": "EXACT_QUERY_NOT_IN_INDEX", "source": None,
            },
        )


def test_report_sha_tamper_is_rejected(tmp_path):
    folder, summary, _ = sample_reports(tmp_path)
    p = folder / "chunk_0001.replay.json"
    altered = json.loads(p.read_text())
    altered["session_reports"][1]["session"] = "2050-01-01"
    p.write_text(json.dumps(altered))
    with pytest.raises(v71.V71Error, match="FINGERPRINT"):
        v71.validate_full_june(folder, expected_sha=summary["fingerprint"])


def test_immutable_output_rejected_before_source_calls(tmp_path):
    folder, summary, _ = sample_reports(tmp_path)
    out = tmp_path / "existing"
    out.mkdir()
    with pytest.raises(v71.V71Error, match="IMMUTABLE_OUTPUT"):
        v71.run(
            folder, out, expected_v69_sha=summary["fingerprint"],
            source_reader=lambda *args: pytest.fail("no source access allowed"),
        )
