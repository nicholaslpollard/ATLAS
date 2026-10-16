from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.simulation.options_native_pair_account_v1 import (
    SyntheticPairEventV1, SyntheticPairIntentV1, SyntheticPairMarkV1,
    replay_synthetic_pair_account,
)
from packages.strategies.options_native_pair_v1 import NativePairError


AT = datetime(2022, 1, 10, 15, 1, tzinfo=UTC)
CALL, PUT = "O:SPY220218C00470000", "O:SPY220218P00470000"
EXIT = AT + timedelta(days=1)
END = EXIT + timedelta(minutes=5)


def intent(**changes):
    return replace(SyntheticPairIntentV1(
        "a", AT, CALL, PUT, "10", "9", "a" * 64, True,
    ), **changes)


def event(eid, kind, *, symbol=CALL, at=None, **changes):
    clock = at or (AT + timedelta(seconds=1) if kind == "BUY" else EXIT)
    return replace(SyntheticPairEventV1(
        event_id=eid, case_id="a", kind=kind, executed_at_utc=clock,
        available_at_utc=clock, option_symbol=None if kind == "REQUEST_EXIT" else symbol,
        price_per_share="10" if kind in {"BUY", "SELL"} else None,
        terminal_unfilled_confirmed=kind == "CANCEL_ENTRY",
    ), **changes)


def fills():
    return (event("buy-call", "BUY"), event("buy-put", "BUY", symbol=PUT, price_per_share="9"))


def round_trip():
    return (*fills(), event("request", "REQUEST_EXIT"),
            event("sell-call", "SELL", at=EXIT + timedelta(seconds=1), price_per_share="12"),
            event("sell-put", "SELL", symbol=PUT, at=EXIT + timedelta(seconds=2), price_per_share="11"))


def replay(events=(), *, intents=None, **kwargs):
    return replay_synthetic_pair_account(
        intents if intents is not None else (intent(),), tuple(events),
        **({"as_of_utc": END, "entry_fee_per_contract": "0.65", "exit_fee_per_contract": "0.65"} | kwargs),
    )


def test_pending_pair_reserves_full_debit_and_both_exit_fees_without_a_fill():
    report = replay()
    assert report["settled_cash"] == "100000.00"
    assert report["entry_cash_reserved"] == "1901.30"
    assert report["exit_fees_reserved"] == "1.30"
    assert report["available_settled_cash"] == "98097.40"
    assert report["ending_equity"] is None
    assert report["historical_fills_verified"] == 0
    assert not any(report["authority"].values())


def test_exact_two_leg_cash_fees_realized_pnl_and_separate_sale_settlement():
    report = replay(round_trip())
    assert report["settled_cash"] == "98097.40"
    assert report["unsettled_sale_proceeds"] == "2300.00"
    assert report["ending_equity"] == "100397.40"
    assert report["modeled_realized_pnl"] == "397.40"
    assert report["entry_cash_reserved"] == report["exit_fees_reserved"] == "0.00"
    assert report["completed_pairs"] == 1
    assert report["unsettled_sale_count"] == 2
    sales = [row for row in report["ledger"] if row["kind"] == "MODELED_SELL"]
    assert sales[0]["gross_sale_proceeds"] == "1200.00"
    assert sales[0]["removed_entry_basis"] == "1000.65"
    assert sales[0]["realized_pnl"] == "198.70"
    assert sum((Decimal(row["cash_delta"]) for row in report["ledger"]), Decimal(0)) == Decimal("397.40")
    settled = replay((*round_trip(), event("settle-call", "SETTLE", reference_fill_id="sell-call",
                                         at=END - timedelta(seconds=1))))
    assert settled["settled_cash"] == "99297.40"
    assert settled["unsettled_sale_proceeds"] == "1100.00"
    assert settled["ending_equity"] == report["ending_equity"]
    assert settled["modeled_realized_pnl"] == report["modeled_realized_pnl"]
    assert settled["ledger"][-1]["cash_delta"] == "0.00"


def test_one_filled_leg_is_exposure_and_terminal_cancel_releases_only_unfilled_leg():
    partial = replay(fills()[:1])
    assert partial["decisions"][0]["status"] == "OPEN_ENTRY_LEG_EXPOSURE"
    assert partial["entry_cash_reserved"] == "900.65"
    assert partial["exit_fees_reserved"] == "1.30"
    cancel = event("cancel-put", "CANCEL_ENTRY", symbol=PUT)
    report = replay((*fills()[:1], cancel))
    assert report["decisions"][0]["status"] == "OPEN_RESIDUAL_LEG_EXPOSURE"
    assert report["settled_cash"] == "98999.35"
    assert report["entry_cash_reserved"] == "0.00"
    assert report["exit_fees_reserved"] == "0.65"
    assert report["ending_equity"] is None
    assert report["completed_pairs"] == 0
    closed = replay((*fills()[:1], cancel, event("request", "REQUEST_EXIT"),
                     event("sell", "SELL", at=EXIT + timedelta(seconds=1), price_per_share="11")))
    assert closed["decisions"][0]["status"] == "ABORTED_PAIR_EXPOSURE_CLOSED"
    assert closed["ending_equity"] == "100098.70"
    assert closed["completed_pairs"] == 0


def test_both_unfilled_cancellations_leave_no_cash_change_and_no_completed_trade():
    report = replay((event("cc", "CANCEL_ENTRY"), event("cp", "CANCEL_ENTRY", symbol=PUT)))
    assert report["ending_equity"] == "100000.00"
    assert report["available_settled_cash"] == "100000.00"
    assert report["decisions"][0]["status"] == "UNFILLED_PAIR_CANCELED"
    assert report["completed_pairs"] == 0


def test_one_exit_retains_original_other_leg_reserve_and_unknown_equity():
    report = replay(round_trip()[:-1])
    assert report["positions"][0]["option_symbol"] == PUT
    assert report["positions"][0]["entry_debit"] == "900.65"
    assert report["exit_fees_reserved"] == "0.65"
    assert report["unsettled_sale_proceeds"] == "1200.00"
    assert report["modeled_realized_pnl"] == "198.70"
    assert report["ending_equity"] is None


def test_unsettled_profit_cannot_increase_new_entry_budget_and_future_settlement_cannot_backdate_it():
    rich = tuple(replace(e, price_per_share="100") if e.kind == "SELL" else e for e in round_trip())
    next_at = AT + timedelta(days=8)  # Jan 18 follows MLK holiday
    next_intent = intent(case_id="b", at_utc=next_at, call_limit_per_share="25", put_limit_per_share="25")
    settle = (
        event("sc", "SETTLE", at=next_at + timedelta(minutes=1), reference_fill_id="sell-call"),
        event("sp", "SETTLE", symbol=PUT, at=next_at + timedelta(minutes=1), reference_fill_id="sell-put"),
    )
    late = replay((*rich, *settle), intents=(intent(), next_intent), as_of_utc=next_at + timedelta(minutes=2))
    assert late["decisions"][1]["status"] == "PAIR_RISK_BUDGET_EXCEEDED"
    early_settle = tuple(replace(e, executed_at_utc=next_at, available_at_utc=next_at) for e in settle)
    early = replay((*rich, *early_settle), intents=(intent(), next_intent), as_of_utc=next_at + timedelta(minutes=2))
    assert early["decisions"][1]["status"] == "PAIR_ENTRY_PENDING"
    assert early["settled_cash"] == late["settled_cash"] == "118097.40"


def test_sale_receipt_availability_controls_slot_without_retroactive_entry_removal():
    next_at = AT + timedelta(days=8)
    delayed = tuple(replace(e, available_at_utc=next_at + timedelta(minutes=1)) if e.kind == "SELL" else e for e in round_trip())
    report = replay(delayed, intents=(intent(), intent(case_id="b", at_utc=next_at)),
                    as_of_utc=next_at + timedelta(minutes=2))
    assert report["decisions"][1]["status"] == "PAIR_SLOT_OCCUPIED"
    assert report["completed_pairs"] == 1
    assert report["ending_equity"] == "100397.40"


def test_unqualified_fill_or_cancel_moves_no_cash_and_releases_no_reserve():
    before = replay()
    report = replay((replace(fills()[0], qualified=False),
                     event("cancel", "CANCEL_ENTRY", symbol=PUT, qualified=False)))
    for key in ("settled_cash", "entry_cash_reserved", "exit_fees_reserved", "ending_equity"):
        assert report[key] == before[key]
    assert all(row["cash_delta"] == "0.00" for row in report["ledger"])


@pytest.mark.parametrize("changes", [
    {"observed_at_utc": END - timedelta(seconds=1)},
    {"available_at_utc": END + timedelta(seconds=1)}, {"qualified": False},
])
def test_missing_stale_late_or_unqualified_marks_leave_equity_unknown(changes):
    mark = replace(SyntheticPairMarkV1("a", CALL, END, END, "9", True), **changes)
    report = replay(fills(), marks=(mark, SyntheticPairMarkV1("a", PUT, END, END, "8", True)))
    assert report["ending_equity"] is None
    assert report["positions"][0]["market_value"] is None
    assert report["positions"][1]["market_value"] == "800.00"


def test_zero_fresh_bid_is_a_known_mark_without_forced_exit_or_intrinsic_settlement():
    marks = tuple(SyntheticPairMarkV1("a", symbol, END, END, "0", True) for symbol in (CALL, PUT))
    report = replay(fills(), marks=marks)
    assert report["ending_equity"] == "98098.70"
    assert report["modeled_liquidation_equity"] == "98097.40"
    assert report["exit_fees_reserved"] == "1.30"
    assert len(report["positions"]) == 2
    assert report["modeled_realized_pnl"] == "0.00"


def test_missing_expiry_evidence_preserves_position_and_cash_instead_of_settling_intrinsic():
    expired = datetime(2022, 2, 22, 15, tzinfo=UTC)
    marks = tuple(SyntheticPairMarkV1("a", symbol, expired, expired, "0", True) for symbol in (CALL, PUT))
    report = replay(fills(), as_of_utc=expired, marks=marks)
    assert report["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXPIRY_OR_EXERCISE"
    assert len(report["positions"]) == 2
    assert report["exit_fees_reserved"] == "1.30"
    assert report["ending_equity"] is None
    assert all(row["mark_status"] == "EXPIRY_EXERCISE_UNRESOLVED" for row in report["positions"])


def test_receipt_order_does_not_change_result_and_unreached_prices_do_not_change_snapshot():
    rows = round_trip()
    assert replay(rows) == replay(tuple(reversed(rows)))
    early = AT + timedelta(minutes=1)
    a = replay(rows, as_of_utc=early)
    b = replay(tuple(replace(e, price_per_share="NaN") if e.kind == "SELL" else e for e in rows), as_of_utc=early)
    assert a == b
    with pytest.raises(NativePairError):
        replay(tuple(replace(e, price_per_share="NaN") if e.kind == "SELL" else e for e in rows))


def test_risk_boundary_includes_both_entry_and_reserved_exit_fees():
    cap = intent(call_limit_per_share="25", put_limit_per_share="25")
    assert replay(intents=(cap,))["decisions"][0]["status"] == "PAIR_RISK_BUDGET_EXCEEDED"
    assert replay(intents=(cap,), entry_fee_per_contract="0", exit_fee_per_contract="0")["decisions"][0]["status"] == "PAIR_ENTRY_PENDING"
    assert replay(intents=(intent(fixture_signal_passed=False),))["decisions"][0]["status"] == "FIXTURE_SIGNAL_ABSTAIN"


@pytest.mark.parametrize("kind", ["BUY", "SELL", "CANCEL_ENTRY", "SETTLE"])
def test_original_contract_membership_cannot_change(kind):
    kwargs = {"reference_fill_id": "sell"} if kind == "SETTLE" else {}
    with pytest.raises(NativePairError, match="original contract"):
        replay((event("bad", kind, symbol="O:SPY220218C00480000", **kwargs),))


@pytest.mark.parametrize("rows", [
    (event("x", "BUY"), event("x", "BUY", symbol=PUT)),
    (event("x", "BUY"), event("y", "BUY")),
    (event("cancel", "CANCEL_ENTRY"), event("buy", "BUY", at=EXIT + timedelta(seconds=1))),
    (event("buy", "BUY", price_per_share="10.01"),),
    (*fills(), event("sell", "SELL")),
    (*round_trip(), event("sell-again", "SELL", at=END)),
    (*round_trip(), event("s1", "SETTLE", at=END, reference_fill_id="sell-call"),
     event("s2", "SETTLE", at=END, reference_fill_id="sell-call")),
    (*round_trip(), event("s1", "SETTLE", symbol=PUT, at=END, reference_fill_id="sell-call")),
    (*fills(), event("s1", "SETTLE", reference_fill_id="missing-sale")),
    (event("cancel", "CANCEL_ENTRY", terminal_unfilled_confirmed=False),),
    (event("buy", "BUY", available_at_utc=AT),),
    (event("buy", "BUY", at=datetime(2022, 2, 19, 15, tzinfo=UTC)),),
])
def test_contradictory_execution_cancellation_or_settlement_fails_closed(rows):
    with pytest.raises(NativePairError):
        replay(rows, as_of_utc=datetime(2022, 2, 22, 15, tzinfo=UTC))


def test_fill_late_after_an_exit_request_retains_exposure_and_does_not_silently_abort_it():
    rows = (event("request", "REQUEST_EXIT"), event("buy", "BUY", at=EXIT + timedelta(seconds=1)),
            event("cancel", "CANCEL_ENTRY", symbol=PUT, at=EXIT + timedelta(seconds=2)))
    report = replay(rows)
    assert report["decisions"][0]["status"] == "OPEN_RESIDUAL_LEG_EXPOSURE"
    assert report["ending_equity"] is None
    assert report["exit_fees_reserved"] == "0.65"


@pytest.mark.parametrize("change", [
    {"origin": "HISTORICAL"}, {"pair_fingerprint": "not-a-hash"},
    {"put_symbol": CALL}, {"put_symbol": "O:SPY220218P00480000"},
    {"at_utc": AT + timedelta(days=1)}, {"at_utc": AT.replace(tzinfo=None)},
    {"call_limit_per_share": "NaN"},
])
def test_malformed_or_out_of_pilot_intent_is_rejected(change):
    with pytest.raises(NativePairError):
        replay(intents=(intent(**change),))


def test_fee_rounding_is_not_invented_from_a_fractional_cent_rate():
    with pytest.raises(NativePairError, match="cent precision"):
        replay(entry_fee_per_contract="0.655")
