from __future__ import annotations

"""Synthetic full-denominator, no-PnL integrated source casebook checks."""

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

import packages.data.integrated_2022_casebook_v1 as m
from packages.data.offline_news_context_v1 import OfflineNewsContext
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint


def _sample():
    source = {}
    rows = []
    for i in range(m.EXPECTED_OPPORTUNITIES):
        shard = i % 71
        oid = f"opportunity-{i:04d}"
        if i < 5:
            status = "NO_LATER_TWO_SIDED_REFERENCE"
        elif i < 14:
            status = "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE"
        else:
            status = "ENTRY_AND_NEXT_REFERENCE_AVAILABLE"
        entry = "2022-03-04" if status != "NO_LATER_TWO_SIDED_REFERENCE" else None
        next_day = "2022-03-07" if status == "ENTRY_AND_NEXT_REFERENCE_AVAILABLE" else None
        rows.append({
            "shard_index": shard, "opportunity_id": oid, "ticker": "TEST",
            "option_symbol": "TEST220318C00010000",
            "source_signal_session": "2022-03-02",
            "stock_decision_session_et": "2022-03-03",
            "expiration": "2022-03-18",
            "structural_rank": 0,
            "selection_never_uses_later_liquidity": True,
            "reference_status": status,
            "first_later_two_sided_session": entry,
            "first_later_eod_ask_reference_per_share": "1.2" if entry else None,
            "subsequent_two_sided_session": next_day,
            "subsequent_eod_bid_reference_per_share": "1.1" if next_day else None,
            "hypothetical_ask_to_next_bid_reference_fraction":
                "-0.083333" if next_day else None,
        })
        source[(shard, oid)] = {
            "opportunity_id": oid, "ticker": "TEST",
            "signal_session": "2022-03-02",
            "decision_at_utc": "2022-03-03T14:35:00+00:00",
            "expiration": "2022-03-18", "side": "call",
            "price_origin": "ACCEPTED_NATIVE_RAW_1DAY_ENTRY_OPEN",
            "underlying_price_basis": "RAW_AS_TRADED",
            "raw_underlying_price": "10.0",
        }
    return {
        "rows": rows, "reference_fingerprint": m.EXPECTED_EOD_REFERENCE,
    }, source, OfflineNewsContext(
        {"TEST": [datetime(2022, 3, 3, 13, tzinfo=UTC)]},
        {"accepted_v2_fingerprint": "b" * 64}, 1,
    )


def test_full_original_denominator_is_preserved_and_never_calls_a_provider(tmp_path):
    reference, source, news = _sample()
    progress = []
    report = m.assemble_casebook(reference, source, news, progress=progress.append)
    assert report["full_structural_denominator"] == 2643
    assert report["distinct_tickers"] == 1
    assert report["prior_24h_news_opportunities"] == 2643
    assert report["prior_7d_news_opportunities"] == 2643
    assert report["option_reference_dispositions"] == {
        "ENTRY_AND_NEXT_REFERENCE_AVAILABLE": 2629,
        "ENTRY_REFERENCE_ONLY_NO_SUBSEQUENT_REFERENCE": 9,
        "NO_LATER_TWO_SIDED_REFERENCE": 5,
    }
    assert report["authority"]["same_clock_stock_option_pnl"] is False
    assert report["provider_requests"] == report["protected_outcomes_read"] == 0
    assert all(row["stock_option_common_clock_comparison_ready"] is False
               for row in report["rows"])
    assert report["rows"][0]["first_later_option_eod_session"] is None
    assert report["rows"][-1]["next_later_option_eod_session"] == "2022-03-07"
    assert progress[-1]["opportunities"] == 2643
    assert report["casebook_fingerprint"] == _fingerprint({
        k: v for k, v in report.items() if k != "casebook_fingerprint"
    })
    settings = SimpleNamespace(resolved_path=lambda path: tmp_path / path)
    path, action = m.write_casebook(settings, report)
    assert path.is_file() and action == "WRITTEN_NEW_CASEBOOK"
    assert m.write_casebook(settings, report)[1] == "REUSED_IDENTICAL_CASEBOOK"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(m.IntegratedCasebookError, match="immutable casebook"):
        m.write_casebook(settings, report)


def test_reject_same_day_option_quote_and_stock_time_identity():
    reference, source, news = _sample()
    row = reference["rows"][14]
    row["first_later_two_sided_session"] = "2022-03-03"
    with pytest.raises(m.IntegratedCasebookError, match="decision-day"):
        m.assemble_casebook(reference, source, news)
    row["first_later_two_sided_session"] = "2022-03-04"
    source[(row["shard_index"], row["opportunity_id"])]["decision_at_utc"] = (
        "2022-03-03T14:30:00+00:00"
    )
    with pytest.raises(m.IntegratedCasebookError, match="identity drifted"):
        m.assemble_casebook(reference, source, news)


def test_source_missing_or_wrong_news_cannot_fake_common_clock():
    reference, source, news = _sample()
    key = (reference["rows"][0]["shard_index"], reference["rows"][0]["opportunity_id"])
    del source[key]
    with pytest.raises(m.IntegratedCasebookError, match="stock source missing"):
        m.assemble_casebook(reference, source, news)
    reference, source, news = _sample()
    reference["rows"][15]["subsequent_two_sided_session"] = "2022-03-04"
    with pytest.raises(m.IntegratedCasebookError, match="strictly later"):
        m.assemble_casebook(reference, source, news)
