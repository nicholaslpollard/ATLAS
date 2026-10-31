from __future__ import annotations

from datetime import date
import json

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts import run_spy_v70_causal_portfolio_ledger as v70


def fabricate(tmp_path, *, unresolved=False, invalid_fee=False, bad_archive=False):
    folder = tmp_path / "source"
    folder.mkdir()
    originals = []
    fresh = []
    for day, cash_flow in (
        ("2025-06-23", ("493.95", "982.05", "488.10")),
        ("2025-06-24", None),
        ("2025-06-25", ("403.95", "199.05", "-204.90")),
    ):
        needed = cash_flow is not None
        req = {
            "method": "option_history_exact_quote_tape",
            "kwargs": {
                "symbol": "SPY", "date_et": day, "expiration": day,
                "right": "call", "strike": "600", "interval": "1s"
            }
        } if needed else None
        receipt = {
            "state": "NOT_REGISTERED" if bad_archive else "ARCHIVED",
            "query_id": _fingerprint(req), "archive_sha256": "f" * 64,
        } if needed else None
        signal = v70.signed({
            "session": day, "selected_contract": {"symbol": "SPY"} if needed else None,
        })
        status = (
            "UNRESOLVED_POSITION" if unresolved and day == "2025-06-25"
            else "CLOSED_QUOTE_REFERENCE" if needed else "NO_SIGNAL"
        )
        events = []
        if needed:
            events.append({
                "type": "MODELED_ENTRY_QUOTE_REFERENCE",
                "qty": 3, "debit_plus_entry_fees": cash_flow[0],
                "broker_fill_verified": False,
            })
            if status == "CLOSED_QUOTE_REFERENCE":
                events.append({
                    "type": "MODELED_EXIT_QUOTE_REFERENCE",
                    "credit_less_exit_fees": cash_flow[1],
                    "broker_fill_verified": False,
                })
        report = v70.signed({
            "session": day,
            "status": status,
            "actual_fills": 0,
            "quote_reference_not_broker_execution": True,
            "starting_cash": "25000.00",
            "source_query_id": receipt["query_id"] if receipt else None,
            "source_sha256": receipt["archive_sha256"] if receipt else None,
            "events": events,
            "entry_debit": cash_flow[0] if needed else None,
            "exit_credit": (
                "982.05" if invalid_fee and day == "2025-06-25"
                else cash_flow[1]
            ) if needed and status == "CLOSED_QUOTE_REFERENCE" else None,
            "trade_net_pnl": cash_flow[2]
                if needed and status == "CLOSED_QUOTE_REFERENCE" else None,
            "terminal_equity_if_resolved": (
                "25488.10" if day == "2025-06-23" else "24795.10"
            ) if needed and status == "CLOSED_QUOTE_REFERENCE" else (
                "25000.00" if not needed else None
            ),
            "policy": {"lag_seconds": 1, "max_adverse_pct": "1"},
            "censor_reason": "UNQUALIFIED_EXIT_QUOTE_PATH" if status ==
                "UNRESOLVED_POSITION" else None,
        })
        row = v70.signed({
            "session": day,
            "signal_fingerprint": signal["fingerprint"],
            "selected_contract": signal["selected_contract"],
            "exact_option_requirement": req,
            "exact_option_receipt": receipt,
            "native_minute_source_sha256": "b" * 64,
            "standalone_replay_report": report,
            "standalone_replay_disposition": status,
        })
        fresh.append(row)
        original = dict(row)
        if needed:
            original["exact_option_receipt"] = {
                **receipt, "state": "NOT_REGISTERED"
            }
            original = v70.signed({
                k: v for k, v in original.items() if k != "fingerprint"
            })
        originals.append(original)
    original_doc = v70.signed({
        "contract": v70.V65, "session_reports": originals,
        "provider_requests": 0, "broker_orders": 0,
    })
    replay_doc = v70.signed({
        "contract": v70.V65, "session_reports": fresh,
        "provider_requests": 0, "broker_orders": 0,
        "option_source_state_counts": {"ARCHIVED": 2},
    })
    source_doc = v70.signed({
        "contract": v70.V69, "original_preflight_sha": original_doc["fingerprint"],
        "broker_orders": 0,
        "runtime_source_receipt": {
            "contract": v70.V39, "source_uses_requested": 2,
        }
    })
    chunk = v70.signed({
        "contract": v70.V69,
        "start": "2025-06-23", "end": "2025-06-25",
        "weekdays": 3, "selected_option_contracts": 2,
        "original_v65_preflight_sha": original_doc["fingerprint"],
        "original_v65_post_source_sha": replay_doc["fingerprint"],
        "unresolved_source_requirements": [],
        "unresolved_positions": int(unresolved),
    })
    summary = v70.signed({
        "contract": v70.V69, "start": "2025-06-23",
        "end": "2025-06-25", "weekdays": 3,
        "broker_orders": 0, "chunks": 1, "completed_chunk_reports": 1,
        "unresolved_source_or_underlying_chunks": 0,
        "all_strategy_source_demands_persisted_or_blocker_reported": True,
        "status": "COMPLETE_SOURCE_CENSUS_WITH_OPEN_POSITIONS"
            if unresolved else "COMPLETE_SOURCE_CENSUS_QUOTE_REFERENCE_ONLY",
        "chunk_summaries": [{
            "index": 1, "status": "SOURCE_CHECKED_AND_REPLAYED",
            "fingerprint": chunk["fingerprint"],
            "blocked": False, "unresolved_sources": 0,
            "unresolved_positions": int(unresolved),
        }],
    })
    for name, doc in (
        ("summary.json", summary),
        ("chunk_0001.summary.json", chunk),
        ("chunk_0001.preflight.json", original_doc),
        ("chunk_0001.replay.json", replay_doc),
        ("chunk_0001.sources.json", source_doc),
    ):
        (folder / name).write_text(json.dumps(doc), encoding="utf8")
    return folder, summary


def test_chained_cash_and_original_fees_reconciled(tmp_path):
    folder, original = fabricate(tmp_path)
    dest = tmp_path / "ledger"
    result = v70.ledger(
        folder, dest, expected_summary_fingerprint=original["fingerprint"],
        emit=lambda message: None,
    )
    assert result["status"] == "COMPLETE_QUOTE_REFERENCE_CASH_LEDGER"
    assert result["initial_cash"] == "25000"
    assert result["terminal_cash_if_fully_resolved"] == "25283.20"
    assert result["realized_trade_pnl_before_any_blocker"] == "283.20"
    assert result["original_outcome_counts_before_blocker"] == {
        "CLOSED_QUOTE_REFERENCE": 2, "NO_SIGNAL": 1,
    }
    assert len(result["daily_reports"]) == 3
    d1 = v70.read_signed(dest / "2025-06-23.json", v70.CONTRACT)
    d2 = v70.read_signed(dest / "2025-06-24.json", v70.CONTRACT)
    d3 = v70.read_signed(dest / "2025-06-25.json", v70.CONTRACT)
    assert d1["balance_after"] == "25488.10"
    assert d2["balance_before"] == d2["balance_after"] == "25488.10"
    assert d3["balance_before"] == "25488.10"
    assert d3["balance_after"] == "25283.20"
    assert v70.read_signed(dest / "summary.json", v70.CONTRACT)["fingerprint"] == result["fingerprint"]
    assert result["broker_orders"] == result["additional_provider_requests"] == 0


def test_unqualified_open_exit_stops_account_before_future_sessions(tmp_path):
    folder, _ = fabricate(tmp_path, unresolved=True)
    dest = tmp_path / "ledger"
    result = v70.ledger(folder, dest, emit=lambda message: None)
    assert result["status"] == "CENSORED_OR_REPLAY_REQUIRED_CASH_LEDGER"
    assert result["terminal_cash_if_fully_resolved"] is None
    assert result["blocked_account_at"]["session"] == "2025-06-25"
    assert result["blocked_account_at"]["future_cash_is_unknown"] is True
    assert result["realized_trade_pnl_before_any_blocker"] == "488.10"
    assert result["session_reports_saved"] == 3
    assert result["completed_sessions_before_blocker"] == 2


def test_cannot_use_25k_position_size_if_cumulative_cash_insufficient(tmp_path):
    folder, _ = fabricate(tmp_path)
    result = v70.ledger(folder, tmp_path / "ledger",
                        starting_cash="200", emit=lambda message: None)
    assert result["terminal_cash_if_fully_resolved"] is None
    assert result["blocked_account_at"]["reason"] == "FROZEN_QUANTITY_REQUIRES_DYNAMIC_CASH_REPLAY"
    assert result["realized_trade_pnl_before_any_blocker"] == "0"
    assert result["session_reports_saved"] == 1


def test_wrong_reconciled_original_exit_fee_or_price_refuses_account(tmp_path):
    folder, _ = fabricate(tmp_path, invalid_fee=True)
    with pytest.raises(v70.V70Error, match="ORIGINAL_FEE_OR_CASH_EVENT_NOT_RECONCILED"):
        v70.ledger(folder, tmp_path / "ledger", emit=lambda message: None)


def test_missing_original_tape_is_not_false_no_entry(tmp_path):
    folder, _ = fabricate(tmp_path, bad_archive=True)
    with pytest.raises(v70.V70Error, match="MISSING_OR_MISMATCHED_ORIGINAL_TAPE"):
        v70.validated_sessions(folder)


def test_forged_parent_summary_fingerprint_blocks_before_writes(tmp_path):
    folder, summary = fabricate(tmp_path)
    with pytest.raises(v70.V70Error, match="PARENT_NOT_EXPECTED"):
        v70.ledger(
            folder, tmp_path / "ledger",
            expected_summary_fingerprint="0" * 64,
            emit=lambda message: None,
        )
    assert not (tmp_path / "ledger").exists()


def test_existing_output_refuses_overwrite(tmp_path):
    folder, _ = fabricate(tmp_path)
    dest = tmp_path / "ledger"
    dest.mkdir()
    with pytest.raises(v70.V70Error, match="OUTPUT_IMMUTABLE"):
        v70.ledger(folder, dest, emit=lambda message: None)
