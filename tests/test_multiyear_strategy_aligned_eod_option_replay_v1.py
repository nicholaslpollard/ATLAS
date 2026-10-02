from __future__ import annotations

from datetime import datetime
import hashlib
import json
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from packages.backtesting.recurrent_successor_daily_exit_sweep import DailyPathBar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
)
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy
from packages.simulation.multiyear_strategy_aligned_eod_option_replay_v1 import (
    StrategyExitPolicy,
    build_strategy_aligned_eod_option_scenario,
    replay_strategy_aligned_eod_call_account,
)
from scripts.run_multiyear_strategy_aligned_eod_option_replay_v1 import (
    main as strategy_aligned_runner_main,
)


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def stamp(text: str) -> int:
    return int(datetime.fromisoformat(text).timestamp())


def raw_body(symbol: str, *, exit_volume: int = 30) -> bytes:
    sessions = [
        "2022-03-03T16:00:00-05:00",
        "2022-03-08T16:00:00-05:00",
    ]
    return json.dumps({
        "s": "ok",
        "optionSymbol": [symbol, symbol],
        "updated": [stamp(value) for value in sessions],
        "bid": [1.00, 1.20],
        "ask": [1.10, 1.30],
        "bidSize": [5, 4],
        "askSize": [5, 4],
        "volume": [25, exit_volume],
        "underlyingPrice": [100.0, 104.0],
    }, sort_keys=True).encode("utf-8")


def bars(*, early_target: bool):
    highs = [106.0, 101.0, 101.0, 101.0, 101.0] if early_target else [101.0] * 5
    days = ["2022-03-02", "2022-03-03", "2022-03-04", "2022-03-07", "2022-03-08"]
    return tuple(
        DailyPathBar(
            session_offset=index,
            session_date=datetime.fromisoformat(day).date(),
            open=100.0,
            high=highs[index - 1],
            low=99.0,
            close=100.5,
        )
        for index, day in enumerate(days, start=1)
    )


def daily_case(cid: str, *, early_target: bool, score: float):
    return SimpleNamespace(
        opportunity=SimpleNamespace(
            opportunity_id=cid,
            economic_family_id="family-a",
            selector_score=score,
        ),
        bars=bars(early_target=early_target),
    )


def fixture(*, exit_volume: int = 30):
    symbol = "TEST220318C00100000"
    query = {
        "option_symbol": symbol,
        "from_inclusive": "2022-03-02",
        "to_exclusive": "2022-03-19",
    }
    rid = _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
    request = {
        **query,
        "request_identity": rid,
        "member_case_ids": ["early:C", "late:C"],
        "source_only_not_validated_trade": True,
    }
    raw = raw_body(symbol, exit_volume=exit_volume)
    sha = hashlib.sha256(raw).hexdigest()

    plan = signed({
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "requested_case_denominator": 2,
        "unique_physical_quote_queries": 1,
        "requests": [request],
        "memberships": [],
        "provider_requests": 0,
        "strategy_authority": False,
    }, "plan_fingerprint")

    handoff = signed({
        "contract": HANDOFF_CONTRACT,
        "status": "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY",
        "selection_fingerprint": "s" * 64,
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_census_fingerprint": "c" * 64,
        "original_case_denominator": 2,
        "original_right_memberships": 4,
        "selected_case_right_memberships": 2,
        "unique_quote_queries": 1,
        "rows": [
            {
                "case_right_id": "early:C",
                "original_case_id": "early",
                "year": "2022",
                "right": "call",
                "option_symbol": symbol,
                "quote_request_identity": rid,
                "quote_history_status": "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
                "quote_source_request_identity": rid,
                "quote_source_from_inclusive": "2022-03-02",
                "quote_source_to_exclusive": "2022-03-19",
                "quote_source_is_clipped_recovery": False,
                "quote_body_sha256": sha,
                "observed_quote_rows": 2,
            },
            {
                "case_right_id": "early:P",
                "original_case_id": "early",
                "year": "2022",
                "right": "put",
                "option_symbol": None,
                "quote_request_identity": None,
                "quote_history_status": "NO_PIT_SELECTED_CONTRACT",
            },
            {
                "case_right_id": "late:C",
                "original_case_id": "late",
                "year": "2022",
                "right": "call",
                "option_symbol": symbol,
                "quote_request_identity": rid,
                "quote_history_status": "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
                "quote_source_request_identity": rid,
                "quote_source_from_inclusive": "2022-03-02",
                "quote_source_to_exclusive": "2022-03-19",
                "quote_source_is_clipped_recovery": False,
                "quote_body_sha256": sha,
                "observed_quote_rows": 2,
            },
            {
                "case_right_id": "late:P",
                "original_case_id": "late",
                "year": "2022",
                "right": "put",
                "option_symbol": None,
                "quote_request_identity": None,
                "quote_history_status": "NO_PIT_SELECTED_CONTRACT",
            },
        ],
        "provider_requests": 0,
        "portfolio_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }, "handoff_fingerprint")

    entry_at = datetime.fromisoformat(
        "2022-03-03T16:00:00-05:00"
    ).astimezone(ZoneInfo("UTC")).isoformat()
    cases = []
    for cid in ("early", "late"):
        cases.append({
            "case_id": cid,
            "year": "2022",
            "ticker": "TEST",
            "policy_id": "policy-a",
            "signal_session": "2022-03-01",
            "decision_at_utc": "2022-03-02T14:35:00+00:00",
            "call": {
                "case_right_id": f"{cid}:C",
                "original_case_id": cid,
                "year": "2022",
                "right": "call",
                "ticker": "TEST",
                "option_symbol": symbol,
                "status": "ENTRY_READY_MODELED_STANDARD_EOD",
                "entry": {
                    "at_utc": entry_at,
                    "session_et": "2022-03-03",
                    "ask_per_share": "1.1",
                    "displayed_ask_size_contracts": 5,
                    "reported_volume_contracts": "25",
                    "underlying_price_same_snapshot": "100",
                    "physical_quote_request_identity": rid,
                    "physical_quote_body_sha256": sha,
                },
                "resolved_exit": None,
                "exit_resolution": "PENDING",
                "modeled_multiplier": 100,
                "provider_standard_multiplier_model_only": True,
                "protected_2026_outcomes_read": 0,
            },
            "put": None,
        })

    base = signed({
        "contract": BASE_SCENARIO_CONTRACT,
        "status": "MODELED_HISTORICAL_EOD_OPTION_SCENARIO_NO_FILL_AUTHORITY",
        "native_source_fingerprint": "n" * 64,
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "eod_probe_fingerprint": "e" * 64,
        "admission_audit_fingerprint": "a" * 64,
        "original_case_denominator": 2,
        "original_right_memberships": 4,
        "dated_rights": 2,
        "causal_entry_ready_rights": 2,
        "entry_ready_resolved_exit_rights": 0,
        "entry_ready_unresolved_exit_rights": 2,
        "unique_physical_quote_histories_decoded": 1,
        "exit_policy": "FIRST_SUBSEQUENT_QUALIFIED_LIQUID_EOD_BID_BEFORE_EXPIRY",
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "future_exit_used_for_entry_admission": False,
        "protected_2026_outcomes_read": 0,
        "provider_requests": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "by_year": {},
        "cases": cases,
    }, "scenario_fingerprint")

    daily = [
        daily_case("early", early_target=True, score=2.0),
        daily_case("late", early_target=False, score=1.0),
    ]

    def reader(request_value, slot):
        assert request_value["request_identity"] == rid
        assert slot["quote_source_request_identity"] == rid
        return request_value, raw, {
            "body_sha256": sha,
            "safe_summary": {"observed_rows": 2},
        }

    return base, plan, handoff, daily, reader


def test_strategy_exit_before_option_entry_is_not_admitted():
    base, plan, handoff, daily, reader = fixture()
    scenario = build_strategy_aligned_eod_option_scenario(
        base,
        plan,
        handoff,
        daily,
        policy=StrategyExitPolicy(0.02, 0.05),
        safe_last_signal_session=datetime.fromisoformat("2025-12-20").date(),
        read_verified_body=reader,
        expected_original_cases=2,
    )
    early = next(case for case in scenario["cases"] if case["case_id"] == "early")
    late = next(case for case in scenario["cases"] if case["case_id"] == "late")
    assert early["strategy_aligned_status"] == "STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY"
    assert late["strategy_aligned_status"] == "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
    assert late["stock_exit"]["disposition"] == "TIME"
    assert late["stock_exit"]["session_et"] == "2022-03-08"
    assert late["strategy_exit_option_mark"]["session_et"] == "2022-03-08"
    assert late["strategy_exit_option_mark"]["bid_per_share"] == "1.2"
    assert scenario["source_ready_strategy_aligned_round_trips"] == 1
    assert scenario["future_option_exit_used_for_entry_admission"] is False


def test_exact_strategy_exit_liquidity_gap_stays_open_after_entry():
    base, plan, handoff, daily, reader = fixture(exit_volume=0)
    scenario = build_strategy_aligned_eod_option_scenario(
        base,
        plan,
        handoff,
        daily,
        policy=StrategyExitPolicy(0.02, 0.05),
        safe_last_signal_session=datetime.fromisoformat("2025-12-20").date(),
        read_verified_body=reader,
        expected_original_cases=2,
    )
    late = next(case for case in scenario["cases"] if case["case_id"] == "late")
    assert late["strategy_aligned_status"] == "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP"

    report = replay_strategy_aligned_eod_call_account(
        scenario,
        policy=ReplayPolicy(
            initial_cash="100000.00",
            fraction_of_available_cash="0.10",
            max_open_positions=10,
            option_slippage_per_share="0.00",
            option_entry_fee_per_contract="0.65",
            option_exit_fee_per_contract="0.65",
        ),
        max_positions_per_family=3,
    )
    assert report["admitted_positions"] == 1
    assert report["completed_round_trips"] == 0
    assert report["end_open_positions"] == 1
    assert report["ending_equity"] is None
    assert report["modeled_total_return_if_fully_closed"] is None
    row = next(item for item in report["decisions"] if item["case_id"] == "late")
    assert row["account_status"] == "OPEN_UNRESOLVED_EXACT_STRATEGY_EXIT_SOURCE_GAP"


def test_strategy_aligned_ready_round_trip_closes_on_exact_session():
    base, plan, handoff, daily, reader = fixture()
    scenario = build_strategy_aligned_eod_option_scenario(
        base,
        plan,
        handoff,
        daily,
        policy=StrategyExitPolicy(0.02, 0.05),
        safe_last_signal_session=datetime.fromisoformat("2025-12-20").date(),
        read_verified_body=reader,
        expected_original_cases=2,
    )
    report = replay_strategy_aligned_eod_call_account(
        scenario,
        policy=ReplayPolicy(
            initial_cash="100000.00",
            fraction_of_available_cash="0.10",
            max_open_positions=10,
            option_slippage_per_share="0.00",
            option_entry_fee_per_contract="0.65",
            option_exit_fee_per_contract="0.65",
        ),
        max_positions_per_family=3,
    )
    assert report["admitted_positions"] == 1
    assert report["completed_round_trips"] == 1
    assert report["end_open_positions"] == 0
    assert report["ending_equity"] is not None
    assert report["modeled_total_return_if_fully_closed"] is not None
    row = next(item for item in report["decisions"] if item["case_id"] == "late")
    assert row["account_status"] == "MODELED_STRATEGY_ALIGNED_EOD_ROUND_TRIP"
    assert row["exit_at_utc"].startswith("2022-03-08")


def test_strategy_aligned_runner_imports_end_to_end():
    assert callable(strategy_aligned_runner_main)
