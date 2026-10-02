from __future__ import annotations

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    CONTRACT as EOD_PROBE_CONTRACT,
)
from packages.data.multiyear_marketdata_eod_standard_contract_admission_v1 import (
    EodStandardContractAdmissionError,
    build_eod_standard_contract_admission_audit,
)
from packages.data.multiyear_option_quote_bridge_v1 import (
    CONTRACT as SELECTION_CONTRACT,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
)


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def snapshot(*, entry: bool) -> dict:
    return {
        "documented_same_row_stock_option_snapshot": True,
        "updated_is_1600_et": True,
        "two_sided": True,
        "positive_displayed_size": True,
        "positive_reported_volume": entry,
    }


def fixture():
    cases = [
        {
            "case_id": "case:C",
            "original_case_id": "case",
            "ticker": "TEST",
            "option_symbol": "TEST220318C00100000",
            "right": "call",
            "expiration": "2022-03-18",
            "decision_at_utc": "2022-03-03T14:35:00+00:00",
            "source_request_identity": "a" * 64,
            "source_body_sha256": "1" * 64,
        },
        {
            "case_id": "case:P",
            "original_case_id": "case",
            "ticker": "TEST",
            "option_symbol": "TEST220318P00100000",
            "right": "put",
            "expiration": "2022-03-18",
            "decision_at_utc": "2022-03-03T14:35:00+00:00",
            "source_request_identity": "b" * 64,
            "source_body_sha256": "2" * 64,
        },
    ]
    selection = signed({
        "contract": SELECTION_CONTRACT,
        "status": "OFFLINE_PIT_CONTRACT_IDENTITIES_ONLY",
        "original_case_denominator": 1,
        "right_policy": "both",
        "original_right_memberships": 2,
        "selected_case_right_memberships": 2,
        "cases": cases,
        "coverage": [],
        "provider_requests": 0,
        "strategy_authority": False,
    }, "selection_fingerprint")

    handoff = signed({
        "contract": HANDOFF_CONTRACT,
        "status": "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY",
        "selection_fingerprint": selection["selection_fingerprint"],
        "quote_plan_fingerprint": "q" * 64,
        "source_census_fingerprint": "c" * 64,
        "original_case_denominator": 1,
        "original_right_memberships": 2,
        "selected_case_right_memberships": 2,
        "unique_quote_queries": 2,
        "rows": [],
        "provider_requests": 0,
        "option_fills_verified": 0,
        "portfolio_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }, "handoff_fingerprint")

    probe = signed({
        "contract": EOD_PROBE_CONTRACT,
        "status": "DOCUMENTED_EOD_REFERENCE_PROBE_NO_TRADE_AUTHORITY",
        "source_handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": 1,
        "original_right_memberships": 2,
        "dated_pair_work_items": 2,
        "provider_requests": 0,
        "historical_option_trades_admitted": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "rows": [
            {
                "case_right_id": "case:C",
                "original_case_id": "case",
                "year": "2022",
                "right": "call",
                "ticker": "TEST",
                "option_symbol": "TEST220318C00100000",
                "entry": snapshot(entry=True),
                "exit": snapshot(entry=False),
                "forced_exit_strictly_before_expiry_candidate": True,
            },
            {
                "case_right_id": "case:P",
                "original_case_id": "case",
                "year": "2022",
                "right": "put",
                "ticker": "TEST",
                "option_symbol": "TEST220318P00100000",
                "entry": snapshot(entry=True),
                "exit": snapshot(entry=True),
                "forced_exit_strictly_before_expiry_candidate": True,
            },
        ],
    }, "probe_fingerprint")

    by_id = {row["case_id"]: row for row in cases}

    def verifier(row):
        source = by_id[row["case_id"]]
        return {
            "request_identity": source["source_request_identity"],
            "body_sha256": source["source_body_sha256"],
            "snapshot_date": "2022-03-02",
            "expiration": source["expiration"],
            "strike_window": "95-105",
            "nonstandard_parameter_present": False,
            "provider_default_nonstandard_false_applies": True,
            "provider_standard_chain_classification": True,
        }

    return selection, handoff, probe, verifier


def test_causal_entry_does_not_use_future_exit_liquidity():
    selection, handoff, probe, verifier = fixture()
    out = build_eod_standard_contract_admission_audit(
        selection,
        handoff,
        probe,
        verify_standard_chain=verifier,
        expected_original_cases=1,
    )
    assert out["dated_pair_work_items"] == 2
    assert out["provider_standard_at_selection"] == 2
    assert out["entry_eod_clock_liquidity_source_shape"] == 2
    assert out["causal_entry_ready_model_source_shape"] == 2
    assert out["later_exit_eod_clock_liquidity_source_shape"] == 1
    assert out["entry_and_later_exit_model_source_shape"] == 1
    assert out["future_exit_used_for_entry_admission"] is False
    call = next(row for row in out["rows"] if row["right"] == "call")
    assert call["causal_entry_ready_model_source_shape"] is True
    assert call["later_exit_source_shape_ready"] is False
    assert call["entry_and_later_exit_model_source_shape"] is False
    assert call["provider_standard_100_share_model_multiplier"] == 100
    assert call["independent_occ_deliverable_multiplier_verified"] is False
    assert out["historical_option_trades_admitted"] == 0
    assert out["historical_account_pnl"] is None


def test_entry_failure_is_not_rescued_by_future_exit():
    selection, handoff, probe, verifier = fixture()
    probe["rows"][0]["entry"]["positive_reported_volume"] = False
    probe["rows"][0]["exit"]["positive_reported_volume"] = True
    probe["probe_fingerprint"] = _fingerprint({
        key: value
        for key, value in probe.items()
        if key != "probe_fingerprint"
    })
    out = build_eod_standard_contract_admission_audit(
        selection,
        handoff,
        probe,
        verify_standard_chain=verifier,
        expected_original_cases=1,
    )
    assert out["causal_entry_ready_model_source_shape"] == 1
    assert out["later_exit_eod_clock_liquidity_source_shape"] == 2
    call = next(row for row in out["rows"] if row["right"] == "call")
    assert call["causal_entry_ready_model_source_shape"] is False
    assert call["later_exit_source_shape_ready"] is True


def test_nonstandard_or_unverified_chain_cannot_be_promoted():
    selection, handoff, probe, verifier = fixture()

    def bad_verifier(row):
        value = verifier(row)
        value["provider_standard_chain_classification"] = False
        return value

    with pytest.raises(
        EodStandardContractAdmissionError,
        match="did not prove standard-filter",
    ):
        build_eod_standard_contract_admission_audit(
            selection,
            handoff,
            probe,
            verify_standard_chain=bad_verifier,
            expected_original_cases=1,
        )
