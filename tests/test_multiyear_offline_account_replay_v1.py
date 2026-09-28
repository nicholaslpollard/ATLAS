from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest

from packages.simulation.multiyear_offline_account_replay_v1 import (
    OfflineAccountReplayError, ReplayLeg, ReplayPolicy, ReplaySignal,
    compare_synthetic_modes, replay_synthetic_account,
)
from scripts.run_multiyear_offline_account_replay_v1 import _fixture


def test_four_modes_share_exact_original_population_and_no_actual_authority():
    signals = _fixture()
    output = compare_synthetic_modes(signals, policy=ReplayPolicy(
        initial_cash="10000.00", max_open_positions=1,
    ))
    assert set(output) == {"STOCK", "CALL", "PUT", "ABSTAIN"}
    assert all(v["original_case_denominator"] == 2 for v in output.values())
    assert all(v["historical_account_pnl_authority"] is False
               and v["provider_requests"] == 0 and v["paper"] is False
               and v["live"] is False for v in output.values())
    assert all(v["by_year"]["2026"]["original_cases"] == 0 for v in output.values())
    assert output["STOCK"]["synthetic_round_trips"] == 1
    assert output["STOCK"]["ending_cash"] == "10017.10"
    assert output["CALL"]["synthetic_round_trips"] == 1
    assert output["CALL"]["ending_cash"] == "10394.80"
    assert output["PUT"]["ending_cash"] == "9443.50"
    assert output["ABSTAIN"]["ending_cash"] == "10000.00"
    assert output["ABSTAIN"]["synthetic_round_trips"] == 0


def test_ledger_conserves_cash_uses_ask_to_enter_bid_to_exit_and_two_side_fees():
    result = replay_synthetic_account(
        _fixture(), mode="CALL", policy=ReplayPolicy(
            initial_cash="10000.00", max_open_positions=1,
        ),
    )
    assert [x["kind"] for x in result["ledger"]] == ["MODELED_ENTRY", "MODELED_EXIT"]
    assert result["ledger"][0]["units"] == 4
    assert result["ledger"][0]["cash_delta"] == "-802.60"
    assert result["ledger"][0]["exit_fees_reserved"] == "2.60"
    assert result["ledger"][1]["cash_delta"] == "1197.40"
    assert result["ledger"][1]["exit_fees_reserved"] == "0.00"
    assert result["decisions"][0]["modeled_net_pnl"] == "394.80"
    assert result["end_open_positions"] == 0
    assert result["ending_reserved_exit_fees"] == "0.00"


def test_overlapping_signals_rejected_at_position_limit_not_silently_dropped():
    result = replay_synthetic_account(
        _fixture(), mode="STOCK", policy=ReplayPolicy(max_open_positions=1),
    )
    assert result["by_year"]["2022"]["original_cases"] == 2
    assert result["by_year"]["2022"]["statuses"] == {
        "MAX_CONCURRENT_POSITIONS_REACHED": 1, "SYNTHETIC_ROUND_TRIP_MODELED": 1,
    }
    assert result["decisions"][1]["modeled_net_pnl"] is None


def test_missing_option_and_unknown_deliverable_are_explicit_no_trades():
    signals = _fixture()
    unqualified = replace(signals[0], call=replace(
        signals[0].call, standard_deliverable_verified=False,
    ))
    output = replay_synthetic_account([unqualified, signals[1]], mode="CALL")
    assert output["synthetic_round_trips"] == 0
    assert output["by_year"]["2022"]["statuses"] == {
        "NO_SYNTHETIC_CALL_LEG": 1, "UNVERIFIED_CONTRACT_DELIVERABLE": 1,
    }
    assert output["ledger"] == []
    assert output["ending_cash"] == output["initial_cash"]


def test_unqualified_clock_or_source_is_not_an_executable_synthetic_path():
    signal = _fixture()[0]
    for key, expected in (
        ("observation_clock_qualified", "UNQUALIFIED_OBSERVATION_CLOCK"),
        ("source_integrity_qualified", "UNQUALIFIED_SOURCE_INTEGRITY"),
    ):
        changed = replace(signal, call=replace(signal.call, **{key: False}))
        report = replay_synthetic_account([changed], mode="CALL")
        assert report["decisions"][0]["status"] == expected
        assert report["synthetic_round_trips"] == 0


def test_option_entry_is_not_retroactively_cancelled_by_future_expiry():
    signal = _fixture()[0]
    changed = replace(signal, call=replace(
        signal.call, expiration=date(2022, 1, 4),
        symbol="O:TEST220104C00100000",
    ))
    result = replay_synthetic_account([changed], mode="CALL")
    assert result["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXPIRY_OR_ASSIGNMENT"
    assert [x["kind"] for x in result["ledger"]] == ["MODELED_ENTRY"]
    assert result["ending_equity"] is None
    assert result["synthetic_round_trips"] == 0


def test_zero_option_exit_bid_is_valid_worthless_bid_with_realized_synthetic_loss():
    signal = _fixture()[0]
    changed = replace(signal, call=replace(signal.call, exit_per_share="0"))
    result = replay_synthetic_account(
        [changed], mode="CALL", policy=ReplayPolicy(initial_cash="10000.00"),
    )
    assert result["synthetic_round_trips"] == 1
    assert result["ending_cash"] == "9194.80"
    assert result["ledger"][1]["cash_delta"] == "-2.60"


def test_exit_at_same_instant_as_another_entry_releases_slot_first():
    a, b = _fixture()
    new_entry = a.call.exit_at_utc
    later = datetime(2022, 1, 6, 21, 0, tzinfo=UTC)
    new_b = replace(
        b, decision_at_utc=datetime(2022, 1, 4, 14, 35, tzinfo=UTC),
        call=replace(a.call, symbol="O:XYZ220121C00100000",
                     entry_at_utc=new_entry, exit_at_utc=later),
    )
    result = replay_synthetic_account(
        [new_b, a], mode="CALL", policy=ReplayPolicy(max_open_positions=1),
    )
    assert result["synthetic_round_trips"] == 2
    assert [x["kind"] for x in result["ledger"]] == [
        "MODELED_ENTRY", "MODELED_EXIT", "MODELED_ENTRY", "MODELED_EXIT",
    ]
    assert result["ledger"][1]["at_utc"] == result["ledger"][2]["at_utc"]


def test_results_are_deterministic_under_fixture_order_reversal():
    a, b = _fixture()
    first = replay_synthetic_account([a, b], mode="STOCK")
    second = replay_synthetic_account([b, a], mode="STOCK")
    assert first == second
    assert first["replay_fingerprint"] == second["replay_fingerprint"]


@pytest.mark.parametrize("bad", [
    "HISTORICAL_SOURCE", "LIVE", "REAL_QUOTE_FROM_CASEBOOK",
])
def test_historical_source_cannot_impersonate_synthetic_fixture(bad):
    signal = replace(_fixture()[0], origin=bad)
    with pytest.raises(OfflineAccountReplayError, match="nonfixture"):
        replay_synthetic_account([signal], mode="CALL")


def test_invalid_inputs_rejected_instead_of_backfilled():
    signal = _fixture()[0]
    with pytest.raises(OfflineAccountReplayError, match="duplicate"):
        replay_synthetic_account([signal, signal], mode="STOCK")
    with pytest.raises(OfflineAccountReplayError, match="allocation"):
        replay_synthetic_account([signal], mode="STOCK",
                                 policy=ReplayPolicy(fraction_of_available_cash="1.01"))
    with pytest.raises(OfflineAccountReplayError, match="entry side"):
        replay_synthetic_account([replace(signal, call=replace(
            signal.call, entry_per_share="NaN",
        ))], mode="CALL")
    with pytest.raises(OfflineAccountReplayError, match="nonchronological"):
        replay_synthetic_account([replace(signal, call=replace(
            signal.call, entry_at_utc=signal.decision_at_utc,
        ))], mode="CALL")


def test_option_fee_reservation_prevents_overcommit_to_second_entry():
    a, b = _fixture()
    second = replace(b, call=replace(
        a.call, symbol="O:XYZ220121C00100000",
    ))
    output = replay_synthetic_account(
        [a, second], mode="CALL", policy=ReplayPolicy(
            initial_cash="500.00", fraction_of_available_cash="1.0",
            max_open_positions=2, option_exit_fee_per_contract="100.00",
        ),
    )
    assert output["synthetic_round_trips"] == 1
    assert output["by_year"]["2022"]["statuses"]["INSUFFICIENT_CASH_FOR_ONE_UNIT"] == 1
    assert output["end_open_positions"] == 0
    assert output["ending_reserved_exit_fees"] == "0.00"


def test_occ_right_and_expiration_cannot_masquerade_as_other_contract():
    signal = _fixture()[0]
    with pytest.raises(OfflineAccountReplayError, match="OCC identity or right"):
        replay_synthetic_account([replace(signal, call=replace(
            signal.call, symbol="O:TEST220121P00100000",
        ))], mode="CALL")
    with pytest.raises(OfflineAccountReplayError, match="OCC expiry"):
        replay_synthetic_account([replace(signal, call=replace(
            signal.call, symbol="O:TEST220122C00100000",
        ))], mode="CALL")


def test_nonstandard_multiplier_not_modeled_as_standard_deliverable():
    signal = _fixture()[0]
    changed = replace(signal, call=replace(signal.call, multiplier=50))
    output = replay_synthetic_account([changed], mode="CALL")
    assert output["synthetic_round_trips"] == 0
    assert output["decisions"][0]["status"] == "UNVERIFIED_CONTRACT_DELIVERABLE"


def test_missing_future_exit_keeps_the_same_entry_and_unpriced_position():
    signal = _fixture()[0]
    no_exit = replace(signal, call=replace(
        signal.call, exit_at_utc=None, exit_per_share=None,
    ))
    completed = replay_synthetic_account([signal], mode="CALL")
    unresolved = replay_synthetic_account([no_exit], mode="CALL")
    assert [e for e in completed["ledger"] if e["kind"] == "MODELED_ENTRY"] == unresolved["ledger"]
    assert unresolved["synthetic_round_trips"] == 0
    assert unresolved["decisions"][0]["status"] == "OPEN_UNMARKED_NO_QUALIFIED_EXIT"
    assert unresolved["end_open_positions"] == 1
    assert unresolved["ending_cash"] == "9197.40"
    assert unresolved["ending_reserved_exit_fees"] == "2.60"
    assert unresolved["ending_equity"] is None
    assert unresolved["modeled_realized_cash_change"] is None
    assert unresolved["modeled_cash_flow_change"] == "-802.60"
    assert unresolved["modeled_realized_pnl"] == "0.00"
    assert unresolved["open_positions"][0]["unrealized_pnl"] is None


def test_quote_exit_clock_failure_cannot_cancel_preexisting_entry():
    signal = _fixture()[0]
    changed = replace(signal, call=replace(
        signal.call, exit_observation_clock_qualified=False,
    ))
    result = replay_synthetic_account([changed], mode="CALL")
    baseline = replay_synthetic_account([signal], mode="CALL")
    assert result["ledger"] == [baseline["ledger"][0]]
    assert result["decisions"][0]["status"] == "OPEN_UNQUALIFIED_EXIT_SOURCE"
    assert result["historical_account_pnl_authority"] is False


def test_asof_causality_keeps_full_cohort_and_never_leaks_future_exit_cash():
    signal = _fixture()[0]
    horizon = datetime(2022, 1, 4, 21, 0, tzinfo=UTC)
    in_progress = replay_synthetic_account(
        [signal], mode="CALL", as_of_utc=horizon,
    )
    assert len(in_progress["ledger"]) == 1
    assert in_progress["end_open_positions"] == 1
    assert in_progress["ending_equity"] is None
    assert in_progress["as_of_utc"] == horizon.isoformat()
    after = replay_synthetic_account(
        [signal], mode="CALL",
        as_of_utc=datetime(2022, 1, 5, 21, 0, tzinfo=UTC),
    )
    assert len(after["ledger"]) == 2
    assert after["ending_equity"] == after["ending_cash"]
    assert after["modeled_realized_pnl"] == after["modeled_realized_cash_change"]


def test_future_signal_and_future_entry_remain_in_full_denominator():
    a, b = _fixture()
    horizon = datetime(2022, 1, 3, 18, 0, tzinfo=UTC)
    report = replay_synthetic_account([a, b], mode="CALL", as_of_utc=horizon)
    assert report["original_case_denominator"] == 2
    assert report["by_year"]["2022"]["statuses"] == {
        "FUTURE_ENTRY_NOT_REACHED": 1, "NO_SYNTHETIC_CALL_LEG": 1,
    }
    assert report["ledger"] == []
    too_early = replay_synthetic_account(
        [a], mode="CALL",
        as_of_utc=datetime(2022, 1, 3, 14, 0, tzinfo=UTC),
    )
    assert too_early["decisions"][0]["status"] == "FUTURE_SIGNAL_NOT_REACHED"
    assert too_early["ending_cash"] == too_early["initial_cash"]


def test_exit_timestamp_and_price_are_atomic_not_made_up():
    signal = _fixture()[0]
    for key in ("exit_at_utc", "exit_per_share"):
        changed = replace(signal, call=replace(signal.call, **{key: None}))
        with pytest.raises(OfflineAccountReplayError, match="exit source price and clock"):
            replay_synthetic_account([changed], mode="CALL")
    with pytest.raises(OfflineAccountReplayError, match="exit source gate"):
        replay_synthetic_account([replace(signal, call=replace(
            signal.call, exit_source_integrity_qualified="yes",
        ))], mode="CALL")


def test_no_hindsight_entry_after_expiry_and_no_fabricated_settlement():
    signal = _fixture()[0]
    changed = replace(signal, call=replace(
        signal.call, expiration=date(2022, 1, 3),
        symbol="O:TEST220103C00100000",
    ))
    result = replay_synthetic_account([changed], mode="CALL")
    assert result["decisions"][0]["status"] == "EXPIRED_BEFORE_ENTRY"
    assert result["ledger"] == []
    expired_open = replay_synthetic_account([replace(
        signal, call=replace(signal.call, exit_at_utc=None, exit_per_share=None),
    )], mode="CALL", as_of_utc=datetime(2022, 1, 22, 21, 0, tzinfo=UTC))
    assert expired_open["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXPIRY_OR_ASSIGNMENT"
    assert expired_open["modeled_realized_pnl"] == "0.00"
    assert expired_open["ending_equity"] is None


def test_unqualified_future_exit_does_not_change_entry_capital_competition():
    a, b = _fixture()
    changed = replace(a, call=replace(
        a.call, exit_source_integrity_qualified=False,
    ))
    report = replay_synthetic_account(
        [changed, replace(b, call=replace(
            a.call, symbol="O:XYZ220121C00100000",
        ))], mode="CALL", policy=ReplayPolicy(max_open_positions=1),
    )
    assert report["end_open_positions"] == 1
    assert report["by_year"]["2022"]["statuses"] == {
        "MAX_CONCURRENT_POSITIONS_REACHED": 1, "OPEN_UNQUALIFIED_EXIT_SOURCE": 1,
    }
    assert report["synthetic_round_trips"] == 0
