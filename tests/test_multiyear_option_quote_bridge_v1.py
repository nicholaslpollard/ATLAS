from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from packages.data import multiyear_option_quote_bridge_v1 as bridge
from packages.data.multiyear_demand_quote_cache_v1 import freeze_quote_demand


def _case(case_id: str, ticker: str, signal: str, entry: str, expiry: str,
          price: str) -> tuple[dict, dict]:
    decision = entry + "T14:35:00+00:00"
    raw = {
        "case_id": case_id, "ticker": ticker, "signal_session": signal,
        "entry_session": entry, "expiration": expiry,
        "planned_option_decision_at_utc": decision,
        "native_source_status": "VERIFIED_NATIVE_RAW_OPEN_NEEDS_ORIGINAL_PIT_CHAIN",
        "raw_underlying_price": price,
    }
    old = {
        "case_id": case_id, "ticker": ticker, "signal_session": signal,
        "entry_session": entry, "expiration": expiry, "decision_at_utc": decision,
        "year": signal[:4], "original_reconciliation": "",
        "source_disposition": "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE",
        "original_2022_option_symbol_pointer": None,
        "original_2022_chain_body_sha256_pointer": None,
        "original_source_pointer": None,
        "news_prior_24h": 0, "news_prior_7d": 1,
    }
    return raw, old


def _fixture():
    a_raw, a_old = _case("case22", "ADNT", "2022-01-03", "2022-01-04",
                         "2022-02-18", "49.22")
    a_old["source_disposition"] = "ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH"
    a_old["original_reconciliation"] = "ORIGINAL_2022_PREFERRED_CALL_PLAN_POINTER_REUSED"
    a_old["original_2022_option_symbol_pointer"] = "ADNT220218C00049000"
    a_old["original_2022_chain_body_sha256_pointer"] = "a" * 64
    a_old["original_source_pointer"] = {"chain_request_identity": "b" * 64}
    b_raw, b_old = _case("case23", "ABCD", "2023-01-03", "2023-01-04",
                         "2023-02-17", "101")
    query_id = "c" * 64
    return (
        {"source_fingerprint": bridge.NATIVE_FP, "rows": [a_raw, b_raw]},
        {"crosswalk_fingerprint": bridge.CROSSWALK_FP, "cases": [a_old, b_old]},
        {"demand_fingerprint": bridge.DEMAND_FP, "requests": [
            {"physical_request_identity": query_id, "member_case_ids": ["case23"]}
        ]},
        {"overlap_fingerprint": bridge.OVERLAP_FP, "rows": [
            {"physical_request_identity": query_id,
             "source_status": "NO_LOCAL_MATCHING_PHYSICAL_CHAIN_SOURCE"}
        ]},
    )


def _rows():
    return (
        {"optionSymbol": "ABCD230217C00100000", "side": "call", "strike": 100},
        {"optionSymbol": "ABCD230217C00102000", "side": "call", "strike": 102},
        {"optionSymbol": "ABCD230217P00100000", "side": "put", "strike": 100},
        {"optionSymbol": "ABCD230217P00102000", "side": "put", "strike": 102},
    )


def test_nearest_atm_tie_otm_not_future_volume_or_bid() -> None:
    rows = (*_rows(),)
    call = bridge.select_structural_option(
        rows, ticker="ABCD", expiry="2023-02-17",
        right="call", raw_open=Decimal("101"))
    put = bridge.select_structural_option(
        rows, ticker="ABCD", expiry="2023-02-17",
        right="put", raw_open=Decimal("101"))
    assert call["option_symbol"] == "ABCD230217C00102000"
    assert put["option_symbol"] == "ABCD230217P00100000"
    assert call["strike"] == "102"


def test_full_case_join_reuses_original_2022_and_new_2023_with_both_rights() -> None:
    native, crosswalk, demand, overlap = _fixture()
    calls = []
    def reader(identity, **kwargs):
        calls.append((identity, kwargs))
        return "VERIFIED_PIT_CHAIN", _rows(), "d" * 64
    result = bridge.assemble_case_selections(
        native, crosswalk, demand, overlap, right="both",
        source_reader=reader,
        accepted_original_2022_symbols={"ADNT220218C00049000"},
        expected_case_denominator=2, expected_physical_source_count=1,
    )
    assert result["original_case_denominator"] == 2
    assert result["original_right_memberships"] == 4
    assert result["selected_case_right_memberships"] == 3
    by_id = {x["case_id"]: x for x in result["cases"]}
    assert by_id["case22:C"]["option_symbol"] == "ADNT220218C00049000"
    assert by_id["case23:C"]["option_symbol"] == "ABCD230217C00102000"
    assert by_id["case23:P"]["option_symbol"] == "ABCD230217P00100000"
    assert all(x["source_body_sha256"] for x in result["cases"])
    assert result["by_status"]["NO_ORIGINAL_PHYSICAL_CHAIN_IDENTITY"] == 1
    assert result["provider_requests"] == 0
    assert len(calls) == 2  # same source memo is caller supplied reader contract


def test_right_policy_does_not_preselect_unrequested_put() -> None:
    native, crosswalk, demand, overlap = _fixture()
    result = bridge.assemble_case_selections(
        native, crosswalk, demand, overlap, right="call",
        source_reader=lambda *args, **kwargs: ("VERIFIED_PIT_CHAIN", _rows(), "d" * 64),
        accepted_original_2022_symbols={"ADNT220218C00049000"},
        expected_case_denominator=2, expected_physical_source_count=1,
    )
    assert len(result["cases"]) == 2
    assert {r["right"] for r in result["cases"]} == {"call"}
    assert result["original_right_memberships"] == 2


def test_bridge_output_is_valid_existing_exact_quote_demand() -> None:
    native, crosswalk, demand, overlap = _fixture()
    result = bridge.assemble_case_selections(
        native, crosswalk, demand, overlap, right="call",
        source_reader=lambda *args, **kwargs: ("VERIFIED_PIT_CHAIN", _rows(), "d" * 64),
        accepted_original_2022_symbols={"ADNT220218C00049000"},
        expected_case_denominator=2, expected_physical_source_count=1,
    )
    quote = freeze_quote_demand(
        result["cases"], asof_utc=datetime(2026, 9, 27, 22, tzinfo=UTC),
        last_completed_session=date(2026, 9, 25),
    )
    assert quote["requested_case_denominator"] == 2
    assert quote["unique_physical_quote_queries"] == 2
    assert quote["provider_requests"] == 0
    assert all(r["from_inclusive"].startswith(("2022", "2023")) for r in quote["requests"])
    assert all(m["disposition"] == "SOURCE_DEMAND_READY" for m in quote["memberships"])


def test_no_date_or_occ_identity_backdating() -> None:
    native, crosswalk, demand, overlap = _fixture()
    crosswalk["cases"][1]["decision_at_utc"] = "2023-01-05T14:35:00+00:00"
    with pytest.raises(bridge.MultiYearQuoteBridgeError, match="chronology"):
        bridge.assemble_case_selections(
            native, crosswalk, demand, overlap, right="call",
            source_reader=lambda *args, **kwargs: ("VERIFIED_PIT_CHAIN", _rows(), "d" * 64),
            accepted_original_2022_symbols={"ADNT220218C00049000"},
            expected_case_denominator=2, expected_physical_source_count=1,
        )
    with pytest.raises(bridge.MultiYearQuoteBridgeError, match="OCC"):
        bridge.select_structural_option(
            ({"optionSymbol": "ZZZZ230217C00100000", "side": "call", "strike": 100},),
            ticker="ABCD", expiry="2023-02-17", right="call", raw_open=Decimal("101"),
        )
