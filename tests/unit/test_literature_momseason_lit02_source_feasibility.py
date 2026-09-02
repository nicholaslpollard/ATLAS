from __future__ import annotations

from copy import deepcopy

import pytest

from packages.backtesting.literature_momseason_development_source_diagnostic import (
    LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
)
from packages.backtesting.literature_momseason_lit01_closeout import (
    LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS,
)
from packages.backtesting.literature_momseason_lit02_source_feasibility import (
    LIT02_SOURCE_FEASIBILITY_PLAN_STATUS,
    build_lit02_source_feasibility_plan,
)
from packages.backtesting.literature_momseason_lit02_source_policy import (
    LIT02_LIT01_CLOSEOUT_FINGERPRINT,
    LIT02_PROHIBITED_REPAIRS,
    LIT02_REQUIRED_SOURCE_COVERAGE,
    LIT02_RETURN_PATHS,
    LIT02_SOURCE_POLICY_STATUS,
    lit02_source_policy_fingerprint,
    lit02_source_policy_payload,
)


def _closeout() -> dict[str, object]:
    return {
        "status": LIT01_SOURCE_INCONCLUSIVE_CLOSEOUT_STATUS,
        "closeout_fingerprint": LIT02_LIT01_CLOSEOUT_FINGERPRINT,
        "economic_signal_classification": "NOT_REACHED",
        "alpha_rejection": False,
        "alpha_support": False,
        "family_finalist": None,
        "unavailable_provider_source_keys": 2,
        "unavailable_plan_rows": 3,
        "development_unavailable_holding_returns": 4,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
    }


def _diagnostic() -> dict[str, object]:
    return {
        "status": LIT01_DEVELOPMENT_SOURCE_DIAGNOSTIC_STATUS,
        "missing_target_units": 0,
        "unavailable_source_keys": 2,
        "unavailable_plan_rows": 3,
        "blocked_holdings": 4,
        "provider_reads_performed": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
        "details": [
            {
                "endpoint_session": "2022-10-31",
                "historical_ticker": "TWTR",
                "availability_status": "ZERO_BAR",
                "instrument_ids": ["ins_twtr"],
                "prior_holding_hits": 0,
                "target_holding_hits": 2,
                "blocked_holdings": 2,
                "hypotheses": ["momseason_short_year1", "momseason_years2_5"],
                "target_months": ["2022-10"],
            },
            {
                "endpoint_session": "2022-10-31",
                "historical_ticker": "PING",
                "availability_status": "ZERO_BAR",
                "instrument_ids": ["ins_ping_a", "ins_ping_a"],
                "prior_holding_hits": 1,
                "target_holding_hits": 1,
                "blocked_holdings": 2,
                "hypotheses": ["momseason_years2_5"],
                "target_months": ["2022-10"],
            },
        ],
    }


def test_source_policy_is_frozen_and_outcome_safe() -> None:
    payload = lit02_source_policy_payload()
    assert payload["status"] == LIT02_SOURCE_POLICY_STATUS
    assert payload["required_source_coverage"] == 1.0
    assert payload["feasibility_inputs"]["lit01_return_signs_or_magnitudes_allowed"] is False
    assert payload["feasibility_inputs"]["new_price_or_return_reads_allowed"] is False
    assert payload["safety"]["protected_outcome_reads_allowed"] is False
    assert payload["safety"]["phase33_authority"] is False
    assert len(lit02_source_policy_fingerprint()) == 64


def test_return_paths_cover_continuity_and_terminal_economics() -> None:
    path_ids = {item.path_id for item in LIT02_RETURN_PATHS}
    assert path_ids == {
        "ORDINARY_MONTH_END",
        "TICKER_CONTINUITY",
        "TERMINAL_CASH",
        "TERMINAL_STOCK",
        "TERMINAL_MIXED",
        "TERMINAL_DISTRIBUTION",
    }
    assert LIT02_REQUIRED_SOURCE_COVERAGE == 1.0
    assert "ARBITRARY_LAST_TRADED_PRICE" in LIT02_PROHIBITED_REPAIRS
    assert "ZERO_FILL_UNAVAILABLE_RETURN" in LIT02_PROHIBITED_REPAIRS


def test_valid_plan_freezes_missing_source_keys_without_outcomes() -> None:
    cases, report = build_lit02_source_feasibility_plan(
        closeout=_closeout(),
        diagnostic=_diagnostic(),
    )

    assert report["status"] == LIT02_SOURCE_FEASIBILITY_PLAN_STATUS
    assert report["source_contract_status"] == LIT02_SOURCE_POLICY_STATUS
    assert report["feasibility_cases"] == 2
    assert report["required_source_coverage"] == 1.0
    assert report["economic_outcome_values_read"] == 0
    assert report["new_price_or_return_provider_reads"] == 0
    assert report["source_metadata_provider_reads"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["fresh_confirmatory_reuse_of_lit01_2021_09_to_2026_04"] is False
    assert report["phase33_signal_to_trade_authority"] is False
    assert len(str(report["feasibility_plan_fingerprint"])) == 64
    assert len(str(report["report_fingerprint"])) == 64
    assert [case["historical_ticker"] for case in cases] == ["PING", "TWTR"]
    assert cases[0]["instrument_ids"] == ["ins_ping_a"]
    assert cases[0]["resolution_status"] == "UNRESOLVED_PRE_SOURCE_READ"
    assert "ORDINARY_MONTH_END" not in cases[0]["candidate_return_paths"]
    assert "TERMINAL_CASH" in cases[0]["candidate_return_paths"]


def test_plan_is_deterministic_under_diagnostic_detail_order() -> None:
    diagnostic = _diagnostic()
    reversed_diagnostic = deepcopy(diagnostic)
    reversed_diagnostic["details"] = list(reversed(diagnostic["details"]))

    cases_a, report_a = build_lit02_source_feasibility_plan(
        closeout=_closeout(), diagnostic=diagnostic
    )
    cases_b, report_b = build_lit02_source_feasibility_plan(
        closeout=_closeout(), diagnostic=reversed_diagnostic
    )
    assert cases_a == cases_b
    assert report_a["feasibility_plan_fingerprint"] == report_b["feasibility_plan_fingerprint"]


def test_plan_rejects_reclassified_lit01_alpha() -> None:
    closeout = _closeout()
    closeout["alpha_rejection"] = True
    with pytest.raises(RuntimeError, match="reclassified LIT-01 alpha evidence"):
        build_lit02_source_feasibility_plan(closeout=closeout, diagnostic=_diagnostic())


def test_plan_rejects_protected_consumption() -> None:
    closeout = _closeout()
    closeout["protected_holdout_consumed"] = True
    with pytest.raises(RuntimeError, match="consumed protected holdout"):
        build_lit02_source_feasibility_plan(closeout=closeout, diagnostic=_diagnostic())


def test_plan_rejects_nonzero_provider_reads_in_diagnostic() -> None:
    diagnostic = _diagnostic()
    diagnostic["provider_reads_performed"] = 1
    with pytest.raises(RuntimeError, match="provider_reads_performed"):
        build_lit02_source_feasibility_plan(closeout=_closeout(), diagnostic=diagnostic)


def test_plan_rejects_non_zero_bar_case() -> None:
    diagnostic = _diagnostic()
    diagnostic["details"][0]["availability_status"] = "PROVIDER_REJECTED"
    with pytest.raises(RuntimeError, match="changed from accepted LIT-01 ZERO_BAR evidence"):
        build_lit02_source_feasibility_plan(closeout=_closeout(), diagnostic=diagnostic)


def test_plan_rejects_detail_count_mismatch() -> None:
    diagnostic = _diagnostic()
    diagnostic["details"] = diagnostic["details"][:1]
    with pytest.raises(RuntimeError, match="detail count mismatch"):
        build_lit02_source_feasibility_plan(closeout=_closeout(), diagnostic=diagnostic)


def test_plan_rejects_lit01_fingerprint_mismatch() -> None:
    closeout = _closeout()
    closeout["closeout_fingerprint"] = "0" * 64
    with pytest.raises(RuntimeError, match="closeout fingerprint mismatch"):
        build_lit02_source_feasibility_plan(closeout=closeout, diagnostic=_diagnostic())
