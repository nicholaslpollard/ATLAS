from __future__ import annotations

from datetime import datetime
import hashlib
import json
from zoneinfo import ZoneInfo

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    MarketDataEodClockProbeError,
    _decode_snapshot_rows,
    _decoded_key,
    build_marketdata_eod_clock_liquidity_probe,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
)
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    CONTRACT as CASEBOOK_CONTRACT,
)
from packages.simulation.multiyear_historical_execution_requirements_v1 import (
    CONTRACT as PROOF_CONTRACT,
)

EASTERN = ZoneInfo("America/New_York")


def signed(value, field):
    value[field] = _fingerprint(value)
    return value


def stamp(text: str) -> int:
    return int(datetime.fromisoformat(text).timestamp())


DEFAULT_UPDATED_TIMES = (
    "2022-03-03T16:00:00-05:00",
    "2022-03-04T16:00:00-05:00",
)


def raw_body(
    symbol: str, *, underlying=True, sizes=True, volume=True,
    updated_times: tuple[str, str] = DEFAULT_UPDATED_TIMES,
) -> bytes:
    return json.dumps({
        "s": "ok",
        "optionSymbol": [symbol, symbol],
        "updated": [stamp(value) for value in updated_times],
        "bid": [1.00, 1.20],
        "ask": [1.10, 1.30],
        "bidSize": [4, 5] if sizes else [0, 0],
        "askSize": [3, 4] if sizes else [0, 0],
        "volume": [25, 30] if volume else [0, 0],
        "underlyingPrice": [100.25, 101.50] if underlying else [None, None],
    }, sort_keys=True).encode("utf-8")


def request(symbol: str):
    query = {
        "option_symbol": symbol,
        "from_inclusive": "2022-01-01",
        "to_exclusive": "2022-03-19",
    }
    rid = _fingerprint({"contract": QUOTE_CONTRACT, "query": query})
    return {
        **query,
        "request_identity": rid,
        "member_case_ids": [],
        "source_only_not_validated_trade": True,
    }


def mark(
    symbol: str, session: str, updated: str, bid: str, ask: str, *,
    body_sha: str, request_identity: str,
):
    return {
        "stage": "ENTRY_SOURCE_NOT_EXECUTION",
        "option_observation_identity": "o" * 64,
        "session_et": session,
        "option_symbol": symbol,
        "physical_quote_body_sha256": body_sha,
        "quote_request_identity": request_identity,
        "provider_updated_at_utc_not_publication_proof":
            datetime.fromisoformat(updated).astimezone(
                ZoneInfo("UTC")
            ).isoformat(),
        "source_bid_per_share_not_fill": bid,
        "source_ask_per_share_not_fill": ask,
        "underlying": "TEST",
        "native_close_request_identity": "n",
        "native_unit_id": "unit",
        "native_canonical_sha256": "a" * 64,
        "raw_daily_close_not_synchronized_mark": "100",
        "same_session_only_not_common_clock": True,
        "publication_availability_verified": False,
        "stock_option_common_clock_verified": False,
        "historical_trade_execution_authority": False,
    }


def fixture(
    *, put_underlying=True, put_sizes=True, put_volume=True,
    put_updated_times: tuple[str, str] = DEFAULT_UPDATED_TIMES,
):
    call_symbol = "TEST220318C00100000"
    put_symbol = "TEST220318P00100000"
    call_req = request(call_symbol)
    put_req = request(put_symbol)
    call_req["member_case_ids"] = ["case:C"]
    put_req["member_case_ids"] = ["case:P"]
    call_raw = raw_body(call_symbol)
    put_raw = raw_body(
        put_symbol,
        underlying=put_underlying,
        sizes=put_sizes,
        volume=put_volume,
        updated_times=put_updated_times,
    )
    raw_by_id = {
        call_req["request_identity"]: call_raw,
        put_req["request_identity"]: put_raw,
    }
    sha_by_id = {
        rid: hashlib.sha256(raw).hexdigest()
        for rid, raw in raw_by_id.items()
    }
    updated_by_id = {
        call_req["request_identity"]: DEFAULT_UPDATED_TIMES,
        put_req["request_identity"]: put_updated_times,
    }
    plan = signed({
        "contract": QUOTE_CONTRACT,
        "status": "SOURCE_DEMAND_FROZEN_NO_PROVIDER_READS",
        "asof_utc": "2026-09-30T04:00:00+00:00",
        "rolling_five_year_floor": "2021-09-30",
        "last_completed_session": "2026-09-29",
        "requested_case_denominator": 2,
        "unique_physical_quote_queries": 2,
        "memberships": [],
        "requests": [call_req, put_req],
        "provider_requests": 0,
        "strategy_authority": False,
        "no_future_liquidity_contract_selection": True,
    }, "plan_fingerprint")

    handoff_rows = []
    casebook_rows = []
    proof_rows = []
    for right, symbol, req in (
        ("call", call_symbol, call_req),
        ("put", put_symbol, put_req),
    ):
        suffix = "C" if right == "call" else "P"
        cid = f"case:{suffix}"
        handoff_rows.append({
            "original_case_id": "case",
            "case_right_id": cid,
            "year": "2022",
            "right": right,
            "source_selection_status": "SELECTED_VERIFIED_PIT_CHAIN",
            "quote_history_status": "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
            "option_symbol": symbol,
            "quote_request_identity": req["request_identity"],
            "quote_body_sha256": sha_by_id[req["request_identity"]],
            "quote_source_request_identity": req["request_identity"],
            "quote_source_from_inclusive": req["from_inclusive"],
            "quote_source_to_exclusive": req["to_exclusive"],
            "quote_source_is_clipped_recovery": False,
            "original_quote_window_fully_reconstructed": True,
            "observed_quote_rows": 2,
        })
        casebook_rows.append({
            "case_right_id": cid,
            "original_case_id": "case",
            "year": "2022",
            "right": right,
            "ticker": "TEST",
            "instrument_id": "TEST",
            "option_symbol": symbol,
            "quote_source_request_identity": req["request_identity"],
            "quote_source_body_sha256": sha_by_id[req["request_identity"]],
            "source_join_status": "PAIRED_DATED_SOURCE_ONLY_UNSYNCHRONIZED",
        })
        source_sha = sha_by_id[req["request_identity"]]
        source_updated = updated_by_id[req["request_identity"]]
        entry = mark(
            symbol, "2022-03-03", source_updated[0],
            "1.0", "1.1",
            body_sha=source_sha,
            request_identity=req["request_identity"],
        )
        later = mark(
            symbol, "2022-03-04", source_updated[1],
            "1.2", "1.3",
            body_sha=source_sha,
            request_identity=req["request_identity"],
        )
        later["stage"] = "LATER_SOURCE_NOT_EXIT_EXECUTION"
        proof_rows.append({
            "case_right_id": cid,
            "original_case_id": "case",
            "year": "2022",
            "right": right,
            "ticker": "TEST",
            "option_symbol": symbol,
            "entry_source": entry,
            "later_source": later,
            "required_independent_proofs": [],
            "historical_entry_admitted": False,
            "historical_exit_admitted": False,
            "historical_trade_or_account_pnl_authority": False,
        })

    handoff = signed({
        "contract": HANDOFF_CONTRACT,
        "status": "OFFLINE_SOURCE_REUSE_HANDOFF_NO_TRADE_AUTHORITY",
        "selection_fingerprint": "s" * 64,
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_census_fingerprint": "c" * 64,
        "original_case_denominator": 1,
        "original_right_memberships": 2,
        "selected_case_right_memberships": 2,
        "unique_quote_queries": 2,
        "rows": handoff_rows,
        "provider_requests": 0,
        "option_fills_verified": 0,
        "portfolio_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }, "handoff_fingerprint")

    casebook = signed({
        "contract": CASEBOOK_CONTRACT,
        "status": "FULL_COHORT_DATED_SOURCE_CASEBOOK_NOT_TRADE_REPLAY",
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": 1,
        "original_right_memberships": 2,
        "rows": casebook_rows,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "synchronized_clock_pairs_proven": 0,
        "option_fills_verified": 0,
        "account_pnl_authority": False,
    }, "casebook_fingerprint")

    proof = signed({
        "contract": PROOF_CONTRACT,
        "status": "CLOCK_AND_DELIVERABLE_PROOF_DEMAND_SOURCE_ONLY",
        "casebook_fingerprint": casebook["casebook_fingerprint"],
        "readiness_fingerprint": "r" * 64,
        "original_case_denominator": 1,
        "original_right_memberships": 2,
        "dated_pair_work_items": 2,
        "dated_pair_source_marks": 4,
        "distinct_option_observations": 4,
        "distinct_original_native_close_queries": 2,
        "required_independent_proofs": [],
        "by_year": {},
        "rows": proof_rows,
        "provider_requests": 0,
        "historical_option_trades": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
    }, "proof_demand_fingerprint")

    def reader(req, slot):
        rid = slot["quote_source_request_identity"]
        raw = raw_by_id[rid]
        return req, raw, {
            "body_sha256": sha_by_id[rid],
            "safe_summary": {"observed_rows": 2},
        }

    return plan, handoff, casebook, proof, reader


def test_probe_projects_same_row_clock_liquidity_and_preexpiry_without_trade_authority():
    plan, handoff, casebook, proof, reader = fixture()
    out = build_marketdata_eod_clock_liquidity_probe(
        plan, handoff, casebook, proof,
        read_verified_body=reader,
        expected_original_cases=1,
    )
    assert out["dated_pair_work_items"] == 2
    assert out["unique_verified_physical_histories_decoded"] == 2
    assert out["documented_same_row_snapshot_candidates"] == 2
    assert out["documented_historical_eod_clock_shape_candidates"] == 2
    assert out["entry_exit_positive_size_and_volume_candidates"] == 2
    assert out["forced_pre_expiry_exit_candidates"] == 2
    assert out["exact_1600_et_entry_and_exit_snapshots"] == 2
    assert out["clock_liquidity_preexpiry_source_shape_candidates"] == 2
    assert out["option_quote_publication_or_retrieval_availability_verified"] == 0
    assert out["matched_executable_stock_option_clock_verified"] == 0
    assert out["point_in_time_option_deliverable_and_multiplier_verified"] == 0
    assert out["historical_option_trades_admitted"] == 0
    assert out["historical_account_pnl"] is None
    assert out["provider_requests"] == 0
    assert all(
        row["historical_trade_admitted"] is False
        and row["point_in_time_option_deliverable_and_multiplier_verified"] is False
        and row["option_quote_publication_or_retrieval_availability_verified"] is False
        and row["matched_executable_stock_option_clock_verified"] is False
        for row in out["rows"]
    )


def test_probe_retains_missing_same_row_or_liquidity_fields_as_explicit_gap():
    plan, handoff, casebook, proof, reader = fixture(
        put_underlying=False,
        put_sizes=False,
        put_volume=False,
    )
    out = build_marketdata_eod_clock_liquidity_probe(
        plan, handoff, casebook, proof,
        read_verified_body=reader,
        expected_original_cases=1,
    )
    assert out["documented_same_row_snapshot_candidates"] == 1
    assert out["documented_historical_eod_clock_shape_candidates"] == 1
    assert out["entry_exit_positive_size_and_volume_candidates"] == 1
    assert out["clock_liquidity_preexpiry_source_shape_candidates"] == 1
    put = next(row for row in out["rows"] if row["right"] == "put")
    assert put["status"] == "EOD_SNAPSHOT_OR_LIQUIDITY_OR_EXIT_POLICY_GAP"
    assert put["entry"]["underlying_price_same_snapshot"] is None
    assert put["historical_trade_admitted"] is False


def test_probe_fails_if_proof_mark_no_longer_matches_verified_body():
    plan, handoff, casebook, proof, reader = fixture()
    proof["rows"][0]["entry_source"]["source_ask_per_share_not_fill"] = "9.99"
    proof["proof_demand_fingerprint"] = _fingerprint({
        k: v for k, v in proof.items() if k != "proof_demand_fingerprint"
    })
    with pytest.raises(MarketDataEodClockProbeError, match="no longer matches"):
        build_marketdata_eod_clock_liquidity_probe(
            plan, handoff, casebook, proof,
            read_verified_body=reader,
            expected_original_cases=1,
        )


def test_probe_fails_if_proof_physical_source_provenance_changes():
    plan, handoff, casebook, proof, reader = fixture()
    proof["rows"][0]["entry_source"]["physical_quote_body_sha256"] = "f" * 64
    proof["proof_demand_fingerprint"] = _fingerprint({
        k: v for k, v in proof.items() if k != "proof_demand_fingerprint"
    })
    with pytest.raises(
        MarketDataEodClockProbeError,
        match="physical quote provenance changed",
    ):
        build_marketdata_eod_clock_liquidity_probe(
            plan, handoff, casebook, proof,
            read_verified_body=reader,
            expected_original_cases=1,
        )


def test_probe_fails_if_casebook_physical_source_provenance_changes():
    plan, handoff, casebook, proof, reader = fixture()
    casebook["rows"][0]["quote_source_body_sha256"] = "e" * 64
    casebook["casebook_fingerprint"] = _fingerprint({
        k: v for k, v in casebook.items() if k != "casebook_fingerprint"
    })
    proof["casebook_fingerprint"] = casebook["casebook_fingerprint"]
    proof["proof_demand_fingerprint"] = _fingerprint({
        k: v for k, v in proof.items() if k != "proof_demand_fingerprint"
    })
    with pytest.raises(
        MarketDataEodClockProbeError,
        match="casebook physical quote provenance changed",
    ):
        build_marketdata_eod_clock_liquidity_probe(
            plan, handoff, casebook, proof,
            read_verified_body=reader,
            expected_original_cases=1,
        )


def test_probe_requires_exact_1600_for_historical_eod_clock_shape():
    plan, handoff, casebook, proof, reader = fixture(
        put_updated_times=(
            "2022-03-03T15:59:00-05:00",
            "2022-03-04T16:00:00-05:00",
        ),
    )
    out = build_marketdata_eod_clock_liquidity_probe(
        plan, handoff, casebook, proof,
        read_verified_body=reader,
        expected_original_cases=1,
    )
    assert out["documented_same_row_snapshot_candidates"] == 2
    assert out["documented_historical_eod_clock_shape_candidates"] == 1
    assert out["clock_liquidity_preexpiry_source_shape_candidates"] == 1
    put = next(row for row in out["rows"] if row["right"] == "put")
    assert put["provider_documented_same_row_snapshot_candidate"] is True
    assert (
        put["provider_documented_historical_eod_clock_shape_candidate"]
        is False
    )
    assert put["status"] == "EOD_SNAPSHOT_OR_LIQUIDITY_OR_EXIT_POLICY_GAP"


def test_probe_index_preserves_unrelated_one_sided_physical_rows():
    symbol = "TEST220318C00100000"
    ticket = request(symbol)
    raw = json.dumps({
        "s": "ok",
        "optionSymbol": [symbol, symbol, symbol],
        "updated": [
            stamp("2022-03-02T16:00:00-05:00"),
            stamp("2022-03-03T16:00:00-05:00"),
            stamp("2022-03-04T16:00:00-05:00"),
        ],
        "bid": [0, 1.00, 1.20],
        "ask": [0.20, 1.10, 1.30],
        "bidSize": [0, 4, 5],
        "askSize": [1, 3, 4],
        "volume": [0, 25, 30],
        "underlyingPrice": [99.50, 100.25, 101.50],
    }, sort_keys=True).encode("utf-8")
    rows = _decode_snapshot_rows(raw, ticket, 3)
    assert rows[0]["two_sided"] is False
    assert _decoded_key(rows[0])[2] == 0
    assert rows[1]["two_sided"] is True
    assert rows[2]["two_sided"] is True
