from __future__ import annotations

from copy import deepcopy

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    CONTRACT as CASEBOOK_CONTRACT, SOURCE_PAIR, STOCK_GAP, NO_PAIR,
)
from packages.simulation.multiyear_account_readiness_v1 import (
    AccountReadinessError, build_replay_readiness,
)


def sample_casebook():
    rows = []
    for case, right, status, source in (
        ("case1", "call", SOURCE_PAIR, "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY"),
        ("case1", "put", NO_PAIR, "NO_PIT_SELECTED_CONTRACT"),
        ("case2", "call", STOCK_GAP, "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY"),
        ("case2", "put", NO_PAIR, "QUOTE_HISTORY_NOT_ACQUIRED"),
    ):
        option = None if source == "NO_PIT_SELECTED_CONTRACT" else "O:ABC220121C00100000"
        raw_close = {"status": "VERIFIED_NATIVE_RAW_EOD_CLOSE"} if status == SOURCE_PAIR else (
            {"status": "NO_RAW_NATIVE_DAILY_BAR_FOR_EXACT_SESSION"} if status == STOCK_GAP else None
        )
        rows.append({
            "case_right_id": case + (":C" if right == "call" else ":P"),
            "original_case_id": case, "right": right, "year": "2022",
            "ticker": "ABC",
            "option_symbol": option, "original_quote_history_status": source,
            "source_join_status": status,
            "first_later_option_source": {"observed_ask_per_share": "2"} if status != NO_PAIR else None,
            "next_later_option_source": {"observed_bid_per_share": "3"} if status != NO_PAIR else None,
            "entry_session_native_source": raw_close,
            "next_session_native_source": raw_close,
            "same_session_evidence_is_not_same_clock_evidence": True,
            "deliverable_and_multiplier_verified": False,
            "executable_fill_or_account_pnl_authority": False,
        })
    document = {
        "contract": CASEBOOK_CONTRACT,
        "status": "FULL_COHORT_DATED_SOURCE_CASEBOOK_NOT_TRADE_REPLAY",
        "original_case_denominator": 2,
        "original_right_memberships": 4,
        "dated_option_and_stock_source_rights": 1,
        "provider_requests": 0, "protected_2026_outcomes_read": 0,
        "synchronized_clock_pairs_proven": 0, "option_fills_verified": 0,
        "account_pnl_authority": False, "rows": rows,
    }
    document["casebook_fingerprint"] = _fingerprint(document)
    return document


def resign(value):
    value["casebook_fingerprint"] = _fingerprint({
        k: v for k, v in value.items() if k != "casebook_fingerprint"
    })


def test_full_right_slot_census_never_infers_trades_from_dated_pair():
    output = build_replay_readiness(
        sample_casebook(), expected_cases=2, expected_source_fp=None,
    )
    assert output["original_case_denominator"] == 2
    assert output["original_right_memberships"] == 4
    assert len(output["rows"]) == 4
    assert all(row["historical_trade_admitted"] is False for row in output["rows"])
    assert output["dated_option_stock_source_rights"] == 1
    assert output["actual_same_clock_qualified_rights"] == 0
    assert output["actual_executable_option_trades"] == 0
    assert output["historical_account_pnl"] is None
    assert output["by_blocker"] == {
        "EXACT_NATIVE_DAILY_PRICE_GAP": 1,
        "EXACT_OPTION_QUOTE_HISTORY_NOT_ACQUIRED": 1,
        "NO_PIT_SELECTED_CONTRACT": 1,
        "SOURCE_DATES_PAIRED_BUT_CLOCK_DELIVERABLE_AND_FILL_UNPROVEN": 1,
    }
    assert output["by_year"]["2026"]["original_right_slots"] == 0
    assert sum(output["by_year"]["2022"]["blockers"].values()) == 4
    assert output["provider_requests"] == 0
    assert output["historical_account_pnl_authority"] is False


def test_tampered_source_signature_fails_closed():
    doc = sample_casebook()
    doc["rows"][0]["source_join_status"] = "ACTUAL_FILL"
    with pytest.raises(ValueError, match="fingerprint"):
        build_replay_readiness(doc, expected_cases=2, expected_source_fp=None)


def test_resigned_source_cannot_promote_clock_or_deliverable():
    doc = sample_casebook()
    doc["rows"][0]["deliverable_and_multiplier_verified"] = True
    resign(doc)
    with pytest.raises(AccountReadinessError, match="authority"):
        build_replay_readiness(doc, expected_cases=2, expected_source_fp=None)


def test_wrong_original_case_right_or_year_cannot_drop_from_denominator():
    doc = sample_casebook()
    doc["rows"][3]["case_right_id"] = "case2:C"
    resign(doc)
    with pytest.raises(AccountReadinessError, match="case/right"):
        build_replay_readiness(doc, expected_cases=2, expected_source_fp=None)


def test_source_fingerprint_pin_is_enforced():
    with pytest.raises(AccountReadinessError, match="lineage"):
        build_replay_readiness(sample_casebook(), expected_cases=2,
                               expected_source_fp="0" * 64)


def test_no_pair_with_selected_unacquired_quote_classifies_exact_gap():
    doc = sample_casebook()
    report = build_replay_readiness(doc, expected_cases=2, expected_source_fp=None)
    assert report["by_blocker"]["EXACT_OPTION_QUOTE_HISTORY_NOT_ACQUIRED"] == 1
    assert report["actual_executable_option_trades"] == 0
