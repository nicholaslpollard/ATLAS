from __future__ import annotations

from copy import deepcopy

import pytest

from packages.data.marketdata_candidate_batch_plan_v1 import (
    CandidateBatchPlanError,
    plan_candidate_chain_batches,
)


SOURCE = "a" * 64


def _opportunity(
    number: int,
    *,
    ticker: str = "SPY",
    price: str = "100.00",
    side: str = "call",
    snapshot_date: str = "2026-09-14",
    decision_at_utc: str = "2026-09-15T13:30:00+00:00",
    expiration: str = "2026-10-16",
) -> dict[str, object]:
    return {
        "opportunity_id": f"source-case-{number:04d}",
        "ticker": ticker,
        "snapshot_date": snapshot_date,
        "decision_at_utc": decision_at_utc,
        "raw_underlying_price": price,
        "underlying_price_basis": "RAW_AS_TRADED",
        "expiration": expiration,
        "side": side,
        "stock_source_sha256": SOURCE,
    }


def _plan(rows: list[dict[str, object]]) -> dict[str, object]:
    return plan_candidate_chain_batches({
        "purpose": "SOURCE_ACQUISITION_ONLY",
        "opportunities": rows,
    })


def test_fifty_pit_opportunities_share_one_historical_chain_query() -> None:
    rows = [
        _opportunity(i, price=str(100 + (i % 5) * 0.01),
                     side="put" if i % 2 else "call")
        for i in range(50)
    ]
    plan = _plan(rows)
    assert plan["opportunities"] == 50
    assert plan["shared_chain_requests"] == 1
    assert plan["nominal_chain_credits_if_each_response_has_1_to_1000_billable_symbols"] == 1
    assert plan["credit_estimate_not_guaranteed"] is True
    assert plan["provider_calls_performed"] == 0
    request = plan["requests"][0]
    assert request["endpoint"] == "options/chain/SPY/"
    assert request["params"]["date"] == "2026-09-14"
    assert request["params"]["expiration"] == "2026-10-16"
    assert request["params"]["strike"] == "92.00-108.05"
    assert request["requested_sides"] == ["call", "put"]
    assert len(request["opportunity_ids"]) == 50
    assert "side" not in request["params"]
    assert "strikeLimit" not in request["params"]


def test_plan_identity_is_invariant_to_input_order() -> None:
    rows = [_opportunity(i, price=str(100 + i / 100)) for i in range(8)]
    assert _plan(rows)["plan_fingerprint"] == _plan(list(reversed(rows)))["plan_fingerprint"]


def test_different_session_and_ticker_do_not_batch() -> None:
    rows = [
        _opportunity(1),
        _opportunity(2, ticker="QQQ"),
        _opportunity(
            3, snapshot_date="2026-09-15",
            decision_at_utc="2026-09-16T13:30:00Z",
        ),
    ]
    plan = _plan(rows)
    assert plan["shared_chain_requests"] == 3


def test_different_expiration_does_not_batch() -> None:
    plan = _plan([
        _opportunity(1),
        _opportunity(2, expiration="2026-10-23"),
    ])
    assert plan["shared_chain_requests"] == 2


def test_disjoint_strike_windows_do_not_get_merged() -> None:
    plan = _plan([_opportunity(1, price="100"), _opportunity(2, price="150")])
    assert plan["shared_chain_requests"] == 2


def test_same_day_eod_lookahead_fails_closed() -> None:
    with pytest.raises(CandidateBatchPlanError, match="must precede"):
        _plan([_opportunity(1, decision_at_utc="2026-09-14T23:59:00Z")])


def test_adjusted_stock_price_basis_is_rejected() -> None:
    row = _opportunity(1)
    row["underlying_price_basis"] = "SPLIT_ADJUSTED"
    with pytest.raises(CandidateBatchPlanError, match="incompatible stock price"):
        _plan([row])


def test_duplicate_opportunity_id_is_rejected() -> None:
    row = _opportunity(1)
    with pytest.raises(CandidateBatchPlanError, match="duplicate opportunity"):
        _plan([row, deepcopy(row)])


def test_missing_stock_source_hash_is_rejected() -> None:
    row = _opportunity(1)
    row["stock_source_sha256"] = ""
    with pytest.raises(CandidateBatchPlanError, match="stock-source SHA256"):
        _plan([row])


def test_future_snapshot_is_rejected() -> None:
    with pytest.raises(CandidateBatchPlanError, match="future snapshot"):
        _plan([_opportunity(
            1, snapshot_date="2099-01-01",
            decision_at_utc="2099-01-02T13:30:00Z",
            expiration="2099-02-17",
        )])


def test_invalid_expiration_horizon_is_rejected() -> None:
    with pytest.raises(CandidateBatchPlanError, match="DTE outside"):
        _plan([_opportunity(1, expiration="2026-09-15")])


def test_price_and_side_cannot_be_fabricated() -> None:
    row = _opportunity(1)
    row["raw_underlying_price"] = "-2"
    with pytest.raises(CandidateBatchPlanError, match="invalid stock price"):
        _plan([row])
    row = _opportunity(1)
    row["side"] = "both"
    with pytest.raises(CandidateBatchPlanError, match="side must"):
        _plan([row])


def test_extra_fields_and_unbounded_fanout_are_blocked() -> None:
    row = _opportunity(1)
    row["later_outcome"] = 100.0
    with pytest.raises(CandidateBatchPlanError, match="fields differ"):
        _plan([row])

    many = [_opportunity(i, ticker=f"A{i:03d}") for i in range(251)]
    with pytest.raises(CandidateBatchPlanError, match="250-group budget"):
        _plan(many)


def test_plan_produces_no_price_or_execution_authority() -> None:
    plan = _plan([_opportunity(1)])
    assert plan["purpose"] == "SOURCE_ACQUISITION_ONLY"
    assert plan["broker_calls_performed"] == 0
    assert plan["limitations"]["no_historical_option_fill_or_pnl_authority"]
    assert plan["limitations"]["no_automatic_contract_selection"]
    assert plan["limitations"]["no_historical_quote_paths_requested"]
