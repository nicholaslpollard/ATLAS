from __future__ import annotations

import copy
from datetime import UTC, datetime

import packages.simulation.multiyear_option_decision_spot_v1 as module
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.multiyear_intraday_stock_exit_clock_v1 import (
    CONTRACT as INTRADAY_CLOCK_CONTRACT,
)


def _signed(body: dict) -> dict:
    value = copy.deepcopy(body)
    value["intraday_clock_fingerprint"] = _fingerprint(value)
    return value


def _clock_report() -> dict:
    rows = [
        {
            "case_id": "a",
            "year": "2025",
            "ticker": "ABC",
            "policy_id": "p",
            "economic_family_id": "f",
            "signal_session": "2025-01-03",
            "entry_session": "2025-01-06",
            "decision_at_utc": "2025-01-06T14:35:00+00:00",
            "raw_stock_open": "100",
            "option_symbol": "ABC250221C00100000",
            "causal_exit_action_at_utc": "2025-01-06T15:00:00+00:00",
            "minute_exit_disposition": "TARGET",
            "option_expression_clock_ready": True,
        },
        {
            "case_id": "b",
            "year": "2025",
            "ticker": "ABC",
            "policy_id": "p",
            "economic_family_id": "f",
            "signal_session": "2025-01-03",
            "entry_session": "2025-01-06",
            "decision_at_utc": "2025-01-06T14:35:00+00:00",
            "raw_stock_open": "50",
            "option_symbol": "ABC250221C00050000",
            "causal_exit_action_at_utc": "2025-01-07T15:00:00+00:00",
            "minute_exit_disposition": "TIME",
            "option_expression_clock_ready": True,
        },
        {
            "case_id": "c",
            "year": "2025",
            "ticker": "XYZ",
            "policy_id": "p2",
            "economic_family_id": "f2",
            "signal_session": "2025-01-03",
            "entry_session": "2025-01-06",
            "decision_at_utc": "2025-01-06T14:35:00+00:00",
            "raw_stock_open": "25",
            "option_symbol": "XYZ250221C00025000",
            "causal_exit_action_at_utc": "2025-01-06T14:34:00+00:00",
            "minute_exit_disposition": "STOP",
            "option_expression_clock_ready": False,
        },
    ]
    return _signed(
        {
            "contract": INTRADAY_CLOCK_CONTRACT,
            "pre2026_call_policy_stock_exit_cases": 3,
            "clock_ready_cases": 2,
            "option_quote_demand": {
                "entry_case_members": 2,
                "exit_case_members": 2,
                "unique_at_time_nbbo_queries": 4,
                "provider_requests_performed": 0,
            },
            "provider_requests": 0,
            "protected_2026_outcomes_read": 0,
            "historical_account_pnl_authority": False,
            "strategy_evidence_authority": False,
            "rows": rows,
        }
    )


def _small(monkeypatch) -> None:
    monkeypatch.setattr(module, "EXPECTED_CASES", 3)
    monkeypatch.setattr(module, "EXPECTED_CLOCK_READY", 2)
    monkeypatch.setattr(module, "EXPECTED_OLD_EXACT_DEMANDS", 4)


def _bar(stamp: str, close: float) -> dict:
    return {
        "timestamp_utc": datetime.fromisoformat(stamp).astimezone(UTC),
        "close": close,
    }


def test_selection_keeps_only_option_expressible_cases(monkeypatch):
    _small(monkeypatch)
    selected = module.select_decision_spot_cases(_clock_report())
    assert [row["case_id"] for row in selected] == ["a", "b"]
    assert all(row["decision_at_utc"].endswith("+00:00") for row in selected)


def test_0934_close_is_causal_but_0935_bar_is_not(monkeypatch):
    _small(monkeypatch)
    case = module.select_decision_spot_cases(_clock_report())[0]
    result = module.resolve_decision_spot(
        case,
        [
            _bar("2025-01-06T14:33:00+00:00", 101),
            _bar("2025-01-06T14:34:00+00:00", 102),
            _bar("2025-01-06T14:35:00+00:00", 110),
        ],
    )
    assert result["status"] == "CAUSAL_0935_DECISION_SPOT_READY"
    assert result["decision_spot"] == "102"
    assert result["source_bar_timestamp_utc"] == "2025-01-06T14:34:00+00:00"
    assert result["source_available_at_utc"] == "2025-01-06T14:35:00+00:00"
    assert result["source_staleness_seconds"] == 0.0
    assert result["baseline_moneyness_at_decision"] == "ITM"


def test_missing_completed_minute_fails_closed(monkeypatch):
    _small(monkeypatch)
    case = module.select_decision_spot_cases(_clock_report())[0]
    result = module.resolve_decision_spot(
        case,
        [_bar("2025-01-06T14:35:00+00:00", 100)],
    )
    assert result["status"] == "NO_COMPLETED_REGULAR_MINUTE_AVAILABLE_AT_0935"
    assert result["decision_spot"] is None


def test_report_groups_cases_into_provider_agnostic_candidate_surface(monkeypatch):
    _small(monkeypatch)
    report = _clock_report()
    cases = module.select_decision_spot_cases(report)
    resolved = [
        module.resolve_decision_spot(
            cases[0], [_bar("2025-01-06T14:34:00+00:00", 102)]
        ),
        module.resolve_decision_spot(
            cases[1], [_bar("2025-01-06T14:34:00+00:00", 51)]
        ),
    ]
    result = module.build_decision_spot_report(
        intraday_clock=report,
        source_metadata={"provider": "alpaca", "provider_calls": 0},
        resolved_rows=resolved,
    )
    demand = result["candidate_entry_surface_demand"]
    assert result["decision_spot_ready_cases"] == 2
    assert demand["case_members"] == 2
    assert demand["unique_underlying_date_clock_queries"] == 1
    assert demand["single_strike_preselection"] is False
    assert demand["provider_specific_request_shape_authorized"] is False
    assert demand["demands"][0]["member_case_ids"] == ["a", "b"]
    assert result["exit_source_stage"]["status"] == "DEFERRED_UNTIL_ENTRY_CONTRACT_SELECTION"
    assert result["provider_requests"] == 0
