from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from packages.simulation.multiyear_offline_account_replay_v1 import (
    EXIT_FILL_CONTRACT, OfflineAccountReplayError, ReplayPolicy,
    SyntheticOptionExitFillV1, compare_synthetic_modes, replay_synthetic_account,
)
from packages.simulation.offline_option_exit_retry_v1 import build_option_exit_retry_plan
from scripts.run_multiyear_offline_account_replay_v1 import _fixture


FIRST = datetime(2022, 1, 5, 14, 35, tzinfo=UTC)
SECOND = FIRST + timedelta(minutes=1)
POLICY = ReplayPolicy(initial_cash="10000.00", fraction_of_available_cash="1.00",
                      maximum_units_per_position=35, max_open_positions=1)


def fill(fill_id="invented-1", at=FIRST, contracts=11, price="1.35", **changes):
    fields = dict(fill_id=fill_id, option_symbol=_fixture()[0].call.symbol,
                  executed_at_utc=at, available_at_utc=at, contracts=contracts,
                  execution_per_share=price, source_integrity_qualified=True,
                  execution_clock_qualified=True)
    return SyntheticOptionExitFillV1(**(fields | changes))


def signal_with(*fills, mode="CALL", **changes):
    signal = _fixture()[0]
    leg = replace(getattr(signal, mode.lower()), entry_per_share="1.30",
                  exit_at_utc=None, exit_per_share=None, exit_fill_fixtures=fills,
                  **changes)
    return replace(signal, **{mode.lower(): leg})


def replay(*fills, as_of=None, policy=POLICY):
    return replay_synthetic_account([signal_with(*fills)], mode="CALL", policy=policy,
                                    as_of_utc=as_of)


def assert_cash_identity(report):
    remaining_debit = sum((Decimal(p["entry_debit"]) for p in report["open_positions"]), Decimal(0))
    assert Decimal(report["ending_cash"]) == (
        Decimal(report["initial_cash"]) + Decimal(report["modeled_realized_pnl"]) - remaining_debit)
    assert Decimal(report["ending_reserved_exit_fees"]) == sum(
        (Decimal(p["reserved_exit_fee"]) for p in report["open_positions"]), Decimal(0))


def test_explicit_eleven_contract_fill_retains_twenty_four_cost_basis_and_fee_reserve():
    report = replay(fill())
    assert report["option_exit_fill_contract"] == EXIT_FILL_CONTRACT
    assert [e["kind"] for e in report["ledger"]] == ["MODELED_ENTRY", "MODELED_PARTIAL_EXIT"]
    assert report["ending_cash"] == "6905.10"
    assert report["modeled_realized_pnl"] == "40.70"
    assert report["ending_reserved_exit_fees"] == "15.60"
    assert report["ending_equity"] is None and report["modeled_realized_cash_change"] is None
    assert report["synthetic_round_trips"] == 0
    assert report["open_positions"] == [{
        "case_id": _fixture()[0].case_id, "symbol": fill().option_symbol, "kind": "CALL",
        "units": 24, "entry_debit": "3135.60", "reserved_exit_fee": "15.60",
        "terminal_market_mark": None, "unrealized_pnl": None,
    }]
    decision = report["decisions"][0]
    assert decision["units"] == 35
    assert decision["closed_units"] == 11 and decision["remaining_units"] == 24
    assert decision["modeled_net_pnl"] is None
    assert decision["modeled_realized_pnl"] == "40.70"
    assert decision["status"] == "OPEN_PARTIALLY_EXITED_UNMARKED"
    event = report["ledger"][1]
    assert event["allocated_entry_debit"] == "1437.15"
    assert event["exit_fee"] == "7.15" and event["cash_delta"] == "1477.85"
    assert report["provider_requests"] == report["historical_fills_verified"] == 0
    assert report["historical_account_pnl_authority"] is report["paper"] is report["live"] is False
    assert_cash_identity(report)


def test_two_slices_complete_once_and_reconcile_total_trade_pnl():
    report = replay(fill(), fill("invented-2", SECOND, 24, "1.00"))
    assert [e["kind"] for e in report["ledger"]] == [
        "MODELED_ENTRY", "MODELED_PARTIAL_EXIT", "MODELED_EXIT",
    ]
    assert report["ending_cash"] == report["ending_equity"] == "9289.50"
    assert report["modeled_realized_pnl"] == report["modeled_realized_cash_change"] == "-710.50"
    assert report["synthetic_round_trips"] == 1 and report["end_open_positions"] == 0
    assert report["ending_reserved_exit_fees"] == "0.00"
    assert report["decisions"][0]["modeled_net_pnl"] == "-710.50"
    assert report["ledger"][2]["modeled_net_pnl"] == "-751.20"
    assert_cash_identity(report)


def test_late_report_never_backdates_cash_or_changes_earlier_snapshot():
    later = SECOND + timedelta(minutes=5)
    delayed = fill(available_at_utc=later)
    cutoff = FIRST + timedelta(seconds=30)
    assert replay(delayed, as_of=cutoff) == replay(as_of=cutoff)
    before = replay(delayed, as_of=cutoff)
    after = replay(delayed, as_of=later)
    assert after["ledger"][:1] == before["ledger"]
    assert after["ledger"][1]["at_utc"] == later.isoformat()
    assert after["ledger"][1]["executed_at_utc"] == FIRST.isoformat()
    assert after["replay_horizon_utc"] == later.isoformat()


def test_future_execution_price_quantity_and_flags_do_not_change_reached_snapshot():
    baseline = replay(fill(), as_of=FIRST)
    future = fill("invented-future", SECOND, 100000, "999.99",
                  source_integrity_qualified=False)
    assert replay(fill(), future, as_of=FIRST) == baseline
    with pytest.raises(OfflineAccountReplayError, match="remaining position"):
        replay(fill(), replace(future, source_integrity_qualified=True), as_of=SECOND)


@pytest.mark.parametrize("gate,reason", [
    ("source_integrity_qualified", "UNQUALIFIED_SOURCE_INTEGRITY"),
    ("execution_clock_qualified", "UNQUALIFIED_EXECUTION_CLOCK"),
])
def test_unqualified_execution_keeps_cash_cost_basis_and_all_reserved_fees(gate, reason):
    before = replay(as_of=FIRST)
    report = replay(fill(**{gate: False}))
    assert report["ending_cash"] == before["ending_cash"] == "5427.25"
    assert report["ending_reserved_exit_fees"] == "22.75"
    assert report["open_positions"] == before["open_positions"]
    assert report["ledger"][1]["kind"] == "MODELED_EXIT_FILL_REJECTED"
    assert report["ledger"][1]["reason"] == reason
    assert report["ledger"][1]["cash_delta"] == "0.00"
    assert report["modeled_realized_pnl"] == "0.00"
    assert report["decisions"][0]["status"] == "OPEN_UNQUALIFIED_EXIT_SOURCE"
    assert_cash_identity(report)


def test_unqualified_later_execution_does_not_erase_prior_partial_realization():
    report = replay(fill(), fill("invented-bad", SECOND, 24, source_integrity_qualified=False))
    assert report["decisions"][0]["status"] == "OPEN_PARTIALLY_EXITED_UNMARKED"
    assert report["modeled_realized_pnl"] == "40.70"
    assert report["open_positions"][0]["units"] == 24
    assert_cash_identity(report)


def test_residual_occupies_slot_until_the_final_report_is_available():
    a = signal_with(fill())
    original_b = _fixture()[1]
    b = replace(original_b, call=replace(a.call, symbol="O:XYZ220121C00100000",
                                        entry_at_utc=FIRST, exit_fill_fixtures=()))
    partial = replay_synthetic_account([b, a], mode="CALL", policy=POLICY)
    assert partial["decisions"][1]["status"] == "MAX_CONCURRENT_POSITIONS_REACHED"
    full = replace(a, call=replace(a.call, exit_fill_fixtures=(fill(contracts=35),)))
    complete = replay_synthetic_account([b, full], mode="CALL", policy=POLICY)
    assert [e["kind"] for e in complete["ledger"]] == ["MODELED_ENTRY", "MODELED_EXIT", "MODELED_ENTRY"]
    delayed_full = replace(full, call=replace(full.call, exit_fill_fixtures=(
        fill(contracts=35, available_at_utc=SECOND),)))
    delayed = replay_synthetic_account([delayed_full, b], mode="CALL", policy=POLICY)
    assert delayed["decisions"][1]["status"] == "MAX_CONCURRENT_POSITIONS_REACHED"
    assert delayed["synthetic_round_trips"] == 1
    assert_cash_identity(partial)
    assert_cash_identity(complete)
    assert_cash_identity(delayed)


def test_unadmitted_entries_and_unchosen_modes_never_apply_execution_fixtures():
    a = signal_with(fill(), source_integrity_qualified=False)
    report = replay_synthetic_account([a], mode="CALL", policy=POLICY)
    assert report["ledger"] == [] and report["ending_cash"] == "10000.00"
    assert "option_exit_fill_contract" not in report
    stock = replay_synthetic_account([a], mode="STOCK")
    assert stock == replay_synthetic_account([_fixture()[0]], mode="STOCK")
    abstain = replay_synthetic_account([a], mode="ABSTAIN")
    assert abstain == replay_synthetic_account([_fixture()[0]], mode="ABSTAIN")


def test_zero_execution_price_uses_reserved_fee_and_leaves_residual_unsettled_after_expiry():
    report = replay(fill(price="0"), as_of=datetime(2022, 1, 24, 14, 35, tzinfo=UTC))
    assert report["ending_cash"] == "5420.10"
    assert report["modeled_realized_pnl"] == "-1444.30"
    assert report["ending_reserved_exit_fees"] == "15.60"
    assert report["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXPIRY_OR_ASSIGNMENT"
    assert report["ending_equity"] is None and report["end_open_positions"] == 1
    assert_cash_identity(report)


def test_execution_price_is_final_and_policy_does_not_apply_exit_slippage_twice():
    policy = replace(POLICY, option_slippage_per_share="0.25")
    report = replay(fill(), policy=policy)
    assert report["ledger"][0]["cash_delta"] == "-5447.75"
    assert report["ledger"][1]["cash_delta"] == "1477.85"
    assert report["modeled_realized_pnl"] == "-234.30"
    assert report["open_positions"][0]["entry_debit"] == "3735.60"
    assert_cash_identity(report)


def test_put_identity_and_execution_sequence_have_deterministic_results():
    put = _fixture()[0].put
    a = replace(fill(), option_symbol=put.symbol)
    b = replace(fill("invented-2", SECOND, 24, "1.00"), option_symbol=put.symbol)
    one = signal_with(a, b, mode="PUT")
    reversed_fills = signal_with(b, a, mode="PUT")
    report = replay_synthetic_account([one], mode="PUT", policy=POLICY)
    assert report == replay_synthetic_account([reversed_fills], mode="PUT", policy=POLICY)
    assert report["ending_cash"] == "9289.50"
    assert_cash_identity(report)


@pytest.mark.parametrize("changes,pattern", [
    ({"origin": "HISTORICAL_SOURCE"}, "fixture identity"),
    ({"fill_id": ""}, "fixture identity"),
    ({"option_symbol": "O:TEST220121P00100000"}, "exact option"),
    ({"contracts": 0}, "quantity"),
    ({"contracts": -1}, "quantity"),
    ({"contracts": True}, "quantity"),
    ({"contracts": 1.0}, "quantity"),
    ({"contracts": 100001}, "quantity"),
    ({"execution_per_share": "NaN"}, "price"),
    ({"execution_per_share": "-1"}, "price"),
    ({"execution_per_share": 1.35}, "decimal string"),
    ({"source_integrity_qualified": 1}, "boolean"),
    ({"execution_clock_qualified": None}, "boolean"),
    ({"executed_at_utc": FIRST.replace(tzinfo=None)}, "timezone-aware"),
    ({"available_at_utc": FIRST.replace(tzinfo=None)}, "timezone-aware"),
    ({"available_at_utc": FIRST - timedelta(seconds=1)}, "chronology"),
    ({"executed_at_utc": _fixture()[0].call.entry_at_utc}, "chronology"),
    ({"executed_at_utc": datetime(2022, 1, 24, 14, 35, tzinfo=UTC),
      "available_at_utc": datetime(2022, 1, 24, 14, 35, tzinfo=UTC)}, "chronology"),
])
def test_malformed_execution_fixtures_are_rejected(changes, pattern):
    with pytest.raises(OfflineAccountReplayError, match=pattern):
        replay(fill(**changes))


def test_duplicate_fills_oversells_and_fills_after_complete_close_fail_closed():
    with pytest.raises(OfflineAccountReplayError, match="duplicate"):
        replay(fill(), fill())
    with pytest.raises(OfflineAccountReplayError, match="remaining position"):
        replay(fill(contracts=36))
    with pytest.raises(OfflineAccountReplayError, match="fully closed"):
        replay(fill(contracts=35), fill("extra", SECOND, 1))
    a = signal_with(fill())
    b = replace(a, case_id="another-case")
    with pytest.raises(OfflineAccountReplayError, match="across cases"):
        replay_synthetic_account([a, b], mode="CALL", policy=POLICY)


def test_fixed_exit_stock_leg_retry_and_mutable_or_unbounded_fills_cannot_mix():
    a = signal_with(fill())
    retry = build_option_exit_retry_plan(
        option_symbol=a.call.symbol, expiration=a.call.expiration,
        opened_at_utc=a.call.entry_at_utc, requested_exit_at_utc=FIRST,
        deadline_at_utc=SECOND, retry_interval_seconds=60,
        maximum_attempts=2, maximum_quote_age_seconds=30,
    )
    for changes in (
        {"exit_at_utc": SECOND, "exit_per_share": "1.00"},
        {"exit_retry_plan": retry}, {"exit_source_integrity_qualified": True},
        {"exit_observation_clock_qualified": False},
        {"exit_fill_fixtures": [fill()]}, {"exit_fill_fixtures": (object(),)},
        {"exit_fill_fixtures": tuple(fill(str(i)) for i in range(65))},
    ):
        with pytest.raises(OfflineAccountReplayError):
            replay_synthetic_account([replace(a, call=replace(a.call, **changes))], mode="CALL")
    with pytest.raises(OfflineAccountReplayError, match="fixed option"):
        replay_synthetic_account([replace(a, stock=replace(a.stock,
            exit_at_utc=None, exit_per_share=None, exit_fill_fixtures=(fill(),)))], mode="STOCK")


def test_existing_four_mode_fingerprints_are_unchanged_without_opt_in_fills():
    reports = compare_synthetic_modes(_fixture())
    assert {mode: report["replay_fingerprint"] for mode, report in reports.items()} == {
        "STOCK": "bc86062cecaf6be02e6bd39f551040dd33b7b928dd45e393fc02c39722f7708e",
        "CALL": "484c6322ecf1b8c6e28aa91041c3ebdcff393c234fa6b6a124b0a4feb527218e",
        "PUT": "188e8ce1b9342f941600f2b36244cb52c2fbeb624ec6fcc0d6b6718747698a9e",
        "ABSTAIN": "8eee525efae721f46d049b404e29850d0ec89f229ac6ec008aa4814de74f8bdd",
    }
    assert all("option_exit_fill_contract" not in report for report in reports.values())
