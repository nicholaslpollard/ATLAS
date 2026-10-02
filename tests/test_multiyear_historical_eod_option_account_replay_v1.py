from __future__ import annotations

from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    CONTRACT as EOD_PROBE_CONTRACT,
)
from packages.data.multiyear_marketdata_eod_standard_contract_admission_v1 import (
    CONTRACT as ADMISSION_CONTRACT,
)
from packages.data.multiyear_native_stock_open_v1 import CONTRACT as NATIVE_CONTRACT
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    build_historical_eod_option_scenario,
    replay_historical_eod_option_account,
)
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def stamp(text: str) -> int:
    return int(datetime.fromisoformat(text).timestamp())


def raw_body(symbol: str, *, delayed_exit: bool = False) -> bytes:
    sessions = [
        "2022-03-03T16:00:00-05:00",
        "2022-03-04T16:00:00-05:00",
        "2022-03-07T16:00:00-05:00",
    ]
    return json.dumps({
        "s": "ok",
        "optionSymbol": [symbol] * 3,
        "updated": [stamp(x) for x in sessions],
        "bid": [1.00, 1.10, 1.20],
        "ask": [1.10, 1.20, 1.30],
        "bidSize": [3, 4, 5],
        "askSize": [3, 4, 5],
        "volume": [20, 0 if delayed_exit else 25, 30],
        "underlyingPrice": [100.0, 101.0, 102.0],
    }, sort_keys=True).encode("utf-8")


def req(symbol: str):
    query = {
        "option_symbol": symbol,
        "from_inclusive": "2022-03-03",
        "to_exclusive": "2022-03-19",
    }
    rid = _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
    return {
        **query,
        "request_identity": rid,
        "member_case_ids": [],
        "source_only_not_validated_trade": True,
    }


def mark(*, side: str, session: str, price: str, positive_volume: bool):
    return {
        "session_et": session,
        "snapshot_updated_at_utc": datetime.fromisoformat(
            session + "T16:00:00-05:00"
        ).astimezone(ZoneInfo("UTC")).isoformat(),
        "snapshot_updated_at_et": session + "T16:00:00-05:00",
        "option_price_per_share": price,
        "option_price_side": side,
        "displayed_size_contracts": 3,
        "reported_volume_contracts": "20" if positive_volume else "0",
        "underlying_price_same_snapshot": "100",
        "two_sided": True,
        "positive_displayed_size": True,
        "positive_reported_volume": positive_volume,
        "updated_is_1600_et": True,
        "documented_same_row_stock_option_snapshot": True,
    }


def fixture():
    call_symbol = "TEST220318C00100000"
    put_symbol = "TEST220318P00100000"
    call_req = req(call_symbol)
    put_req = req(put_symbol)
    call_req["member_case_ids"] = ["one:C"]
    put_req["member_case_ids"] = ["two:P"]

    call_raw = raw_body(call_symbol, delayed_exit=True)
    put_raw = raw_body(put_symbol, delayed_exit=False)
    raws = {
        call_req["request_identity"]: call_raw,
        put_req["request_identity"]: put_raw,
    }
    shas = {rid: hashlib.sha256(raw).hexdigest() for rid, raw in raws.items()}

    plan = signed({
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "requested_case_denominator": 2,
        "unique_physical_quote_queries": 2,
        "requests": [call_req, put_req],
        "memberships": [],
        "provider_requests": 0,
        "strategy_authority": False,
    }, "plan_fingerprint")

    handoff_rows = []
    for cid, symbol, request in (
        ("one:C", call_symbol, call_req),
        ("two:P", put_symbol, put_req),
    ):
        handoff_rows.append({
            "case_right_id": cid,
            "original_case_id": cid.split(":")[0],
            "year": "2022",
            "right": "call" if cid.endswith(":C") else "put",
            "option_symbol": symbol,
            "quote_request_identity": request["request_identity"],
            "quote_history_status": "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
            "quote_source_request_identity": request["request_identity"],
            "quote_source_from_inclusive": request["from_inclusive"],
            "quote_source_to_exclusive": request["to_exclusive"],
            "quote_source_is_clipped_recovery": False,
            "quote_body_sha256": shas[request["request_identity"]],
            "observed_quote_rows": 3,
        })
    handoff_rows.extend([
        {
            "case_right_id": "one:P",
            "original_case_id": "one",
            "year": "2022",
            "right": "put",
            "option_symbol": None,
            "quote_request_identity": None,
            "quote_history_status": "NO_PIT_SELECTED_CONTRACT",
        },
        {
            "case_right_id": "two:C",
            "original_case_id": "two",
            "year": "2022",
            "right": "call",
            "option_symbol": None,
            "quote_request_identity": None,
            "quote_history_status": "NO_PIT_SELECTED_CONTRACT",
        },
    ])
    handoff = signed({
        "contract": HANDOFF_CONTRACT,
        "status": "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY",
        "selection_fingerprint": "s" * 64,
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_census_fingerprint": "c" * 64,
        "original_case_denominator": 2,
        "original_right_memberships": 4,
        "selected_case_right_memberships": 2,
        "unique_quote_queries": 2,
        "rows": handoff_rows,
        "provider_requests": 0,
        "portfolio_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }, "handoff_fingerprint")

    probe_rows = [
        {
            "case_right_id": "one:C",
            "original_case_id": "one",
            "year": "2022",
            "right": "call",
            "ticker": "TEST",
            "option_symbol": call_symbol,
            "entry": mark(
                side="ASK", session="2022-03-03", price="1.10",
                positive_volume=True,
            ),
            "exit": mark(
                side="BID", session="2022-03-04", price="1.10",
                positive_volume=False,
            ),
            "expiration": "2022-03-18",
            "forced_exit_strictly_before_expiry_candidate": True,
        },
        {
            "case_right_id": "two:P",
            "original_case_id": "two",
            "year": "2022",
            "right": "put",
            "ticker": "TEST",
            "option_symbol": put_symbol,
            "entry": mark(
                side="ASK", session="2022-03-03", price="1.10",
                positive_volume=True,
            ),
            "exit": mark(
                side="BID", session="2022-03-04", price="1.10",
                positive_volume=True,
            ),
            "expiration": "2022-03-18",
            "forced_exit_strictly_before_expiry_candidate": True,
        },
    ]
    probe = signed({
        "contract": EOD_PROBE_CONTRACT,
        "status": "DOCUMENTED_EOD_REFERENCE_PROBE_NO_TRADE_AUTHORITY",
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": 2,
        "original_right_memberships": 4,
        "dated_pair_work_items": 2,
        "rows": probe_rows,
        "provider_requests": 0,
        "historical_option_trades_admitted": 0,
        "historical_account_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }, "probe_fingerprint")

    admission_rows = []
    for row in probe_rows:
        admission_rows.append({
            "case_right_id": row["case_right_id"],
            "original_case_id": row["original_case_id"],
            "year": row["year"],
            "right": row["right"],
            "ticker": row["ticker"],
            "option_symbol": row["option_symbol"],
            "decision_at_utc": "2022-03-03T14:35:00+00:00",
            "provider_standard_chain_classification": True,
            "provider_standard_100_share_model_multiplier": 100,
            "independent_occ_deliverable_multiplier_verified": False,
            "entry_source_shape_ready_without_future_exit": True,
            "causal_entry_ready_model_source_shape": True,
            "later_exit_source_shape_ready":
                row["exit"]["positive_reported_volume"],
            "entry_and_later_exit_model_source_shape":
                row["exit"]["positive_reported_volume"],
            "future_exit_used_for_entry_admission": False,
            "historical_trade_admitted": False,
            "historical_account_pnl_authority": False,
        })
    admission = signed({
        "contract": ADMISSION_CONTRACT,
        "status": (
            "PROVIDER_STANDARD_EOD_CAUSAL_ADMISSION_AUDIT_"
            "MODELED_MULTIPLIER_ONLY"
        ),
        "selection_fingerprint": "s" * 64,
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "eod_probe_fingerprint": probe["probe_fingerprint"],
        "original_case_denominator": 2,
        "original_right_memberships": 4,
        "dated_pair_work_items": 2,
        "causal_entry_ready_model_source_shape": 2,
        "future_exit_used_for_entry_admission": False,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "historical_option_trades_admitted": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "rows": admission_rows,
    }, "audit_fingerprint")

    native = {
        "contract": NATIVE_CONTRACT,
        "status": "MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY",
        "case_denominator": 2,
        "protected_outcomes_read": 0,
        "rows": [
            {
                "case_id": "one",
                "ticker": "TEST",
                "policy_id": "P",
                "signal_session": "2022-03-02",
                "planned_option_decision_at_utc":
                    "2022-03-03T14:35:00+00:00",
            },
            {
                "case_id": "two",
                "ticker": "TEST",
                "policy_id": "P",
                "signal_session": "2022-03-02",
                "planned_option_decision_at_utc":
                    "2022-03-03T14:35:00+00:00",
            },
        ],
    }
    native["source_fingerprint"] = _fingerprint(native)
    native_fp = native["source_fingerprint"]

    def reader(request, slot):
        rid = slot["quote_source_request_identity"]
        raw = raws[rid]
        return request, raw, {
            "body_sha256": shas[rid],
            "safe_summary": {"observed_rows": 3},
        }

    return native, native_fp, plan, handoff, probe, admission, reader


def test_scenario_resolves_first_later_liquid_exit_without_entry_lookahead():
    native, native_fp, plan, handoff, probe, admission, reader = fixture()
    scenario = build_historical_eod_option_scenario(
        native, plan, handoff, probe, admission,
        read_verified_body=reader,
        expected_original_cases=2,
        expected_native_fingerprint=native_fp,
    )
    assert scenario["causal_entry_ready_rights"] == 2
    assert scenario["entry_ready_resolved_exit_rights"] == 2
    assert scenario["entry_ready_unresolved_exit_rights"] == 0

    call = next(
        case["call"] for case in scenario["cases"] if case["case_id"] == "one"
    )
    assert call["entry"]["session_et"] == "2022-03-03"
    # 03-04 had zero volume, so the causal daily exit attempt advances to 03-07.
    assert call["resolved_exit"]["session_et"] == "2022-03-07"
    assert call["resolved_exit"]["bid_per_share"] == "1.2"
    assert scenario["future_exit_used_for_entry_admission"] is False


def test_call_and_put_replays_remain_separate_modes():
    native, native_fp, plan, handoff, probe, admission, reader = fixture()
    scenario = build_historical_eod_option_scenario(
        native, plan, handoff, probe, admission,
        read_verified_body=reader,
        expected_original_cases=2,
        expected_native_fingerprint=native_fp,
    )
    policy = ReplayPolicy(
        initial_cash="100000.00",
        fraction_of_available_cash="0.10",
        max_open_positions=5,
        option_slippage_per_share="0.00",
        option_entry_fee_per_contract="0.65",
        option_exit_fee_per_contract="0.65",
    )
    call = replay_historical_eod_option_account(
        scenario, mode="CALL", policy=policy
    )
    put = replay_historical_eod_option_account(
        scenario, mode="PUT", policy=policy
    )

    assert call["mode_interpretation"] == "DIRECTION_ALIGNED_PRIMARY"
    assert put["mode_interpretation"] == "COUNTERFACTUAL_DIAGNOSTIC"
    assert call["causal_entry_source_rights"] == 1
    assert put["causal_entry_source_rights"] == 1
    assert call["completed_round_trips"] == 1
    assert put["completed_round_trips"] == 1
    assert call["historical_account_pnl_authority"] is False
    assert put["historical_account_pnl_authority"] is False
    assert call["provider_requests"] == 0
    assert put["provider_requests"] == 0
    assert call["protected_2026_outcomes_read"] == 0
    assert put["protected_2026_outcomes_read"] == 0


def test_unresolved_admitted_exit_remains_open_and_suppresses_terminal_equity():
    native, native_fp, plan, handoff, probe, admission, reader = fixture()
    scenario = build_historical_eod_option_scenario(
        native, plan, handoff, probe, admission,
        read_verified_body=reader,
        expected_original_cases=2,
        expected_native_fingerprint=native_fp,
    )
    one = next(case for case in scenario["cases"] if case["case_id"] == "one")
    one["call"]["resolved_exit"] = None
    one["call"]["exit_resolution"] = (
        "NO_LATER_QUALIFIED_LIQUID_EOD_BID_BEFORE_EXPIRY_OR_2026"
    )
    scenario["entry_ready_resolved_exit_rights"] -= 1
    scenario["entry_ready_unresolved_exit_rights"] += 1
    scenario["scenario_fingerprint"] = _fingerprint({
        key: value
        for key, value in scenario.items()
        if key != "scenario_fingerprint"
    })

    report = replay_historical_eod_option_account(
        scenario,
        mode="CALL",
        policy=ReplayPolicy(
            initial_cash="100000.00",
            fraction_of_available_cash="0.10",
            max_open_positions=5,
            option_slippage_per_share="0.00",
            option_entry_fee_per_contract="0.65",
            option_exit_fee_per_contract="0.65",
        ),
    )
    assert report["admitted_positions"] == 1
    assert report["completed_round_trips"] == 0
    assert report["end_open_positions"] == 1
    assert report["ending_equity"] is None
    assert report["modeled_total_return_on_initial_cash_if_fully_closed"] is None
    decision = next(
        row for row in report["decisions"] if row["case_id"] == "one"
    )
    assert decision["status"] == "OPEN_UNRESOLVED_NO_QUALIFIED_PREEXPIRY_EXIT"
    assert report["historical_account_pnl_authority"] is False
