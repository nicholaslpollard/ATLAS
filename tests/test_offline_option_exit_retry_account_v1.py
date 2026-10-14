from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from packages.simulation.multiyear_offline_account_replay_v1 import (
    OfflineAccountReplayError, ReplayPolicy, replay_synthetic_account,
)
from packages.simulation.offline_option_exit_retry_v1 import (
    SyntheticExitQuoteV1, build_option_exit_retry_plan,
    restore_option_exit_retry_cursor,
)
from scripts.run_multiyear_offline_account_replay_v1 import _fixture


def fixture(**plan_overrides):
    signal = _fixture()[0]
    fields = dict(
        option_symbol=signal.call.symbol, expiration=signal.call.expiration,
        opened_at_utc=signal.call.entry_at_utc,
        requested_exit_at_utc=datetime(2022, 1, 5, 14, 35, tzinfo=UTC),
        deadline_at_utc=datetime(2022, 1, 5, 14, 40, tzinfo=UTC),
        retry_interval_seconds=60, maximum_attempts=3, maximum_quote_age_seconds=30,
    )
    plan = build_option_exit_retry_plan(**(fields | plan_overrides))
    signal = replace(signal, call=replace(signal.call, exit_at_utc=None,
                      exit_per_share=None, exit_retry_plan=plan))
    return signal, plan


def quote(symbol, at, **overrides):
    fields = dict(option_symbol=symbol, observed_at_utc=at, available_at_utc=at,
                  bid_per_share="3.00", ask_per_share="3.10", bid_size_contracts=100,
                  source_integrity_qualified=True, observation_clock_qualified=True)
    return SyntheticExitQuoteV1(**(fields | overrides))


def test_missing_quote_then_qualified_retry_closes_once_and_reconciles_cash():
    signal, p = fixture()
    first, second, third = p.attempt_times_utc
    prices = {(signal.case_id, second): quote(p.option_symbol, second),
              (signal.case_id, third): quote(p.option_symbol, third, bid_per_share="9.00", ask_per_share="9.10")}
    report = replay_synthetic_account([signal], mode="CALL",
        policy=ReplayPolicy(initial_cash="10000.00"), exit_quotes=prices)
    assert [e["kind"] for e in report["ledger"]] == [
        "MODELED_ENTRY", "MODELED_EXIT_ATTEMPT_UNRESOLVED", "MODELED_EXIT",
    ]
    assert report["ledger"][1]["reason"] == "NO_QUOTE"
    assert report["ledger"][1]["cash_delta"] == "0.00"
    assert report["ledger"][1]["cash_after"] == "9197.40"
    assert report["ledger"][1]["exit_fees_reserved"] == "2.60"
    assert report["ledger"][2]["at_utc"] == second.isoformat()
    assert report["ending_cash"] == "10394.80"
    assert report["modeled_realized_pnl"] == "394.80"
    assert report["ending_equity"] == report["ending_cash"]
    assert report["end_open_positions"] == 0
    assert report["ending_reserved_exit_fees"] == "0.00"
    record = report["option_exit_retries"][0]
    restored = restore_option_exit_retry_cursor(record["cursor"],
        expected_fingerprint=record["cursor_fingerprint"], expected_plan_fingerprint=p.fingerprint)
    assert len(restored.attempts) == 2
    assert restored.ready_quote.bid_per_share == "3.00"
    assert report["provider_requests"] == 0 and report["historical_account_pnl_authority"] is False


def test_retry_exhaustion_retains_position_fees_and_unknown_equity():
    signal, p = fixture()
    report = replay_synthetic_account([signal], mode="CALL")
    assert report["replay_horizon_utc"] == p.deadline_at_utc.isoformat()
    assert report["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXIT_RETRY_LIMIT"
    assert [e["reason"] for e in report["ledger"][1:]] == ["NO_QUOTE"] * 3
    assert report["end_open_positions"] == 1
    assert report["ending_cash"] == "90168.15"
    assert report["ending_reserved_exit_fees"] == "31.85"
    assert report["ending_equity"] is None
    assert report["modeled_realized_pnl"] == "0.00"
    assert report["modeled_realized_cash_change"] is None


def test_deadline_and_later_expiry_never_invent_settlement_or_release_cash():
    signal, p = fixture(maximum_attempts=64)
    at_deadline = replay_synthetic_account([signal], mode="CALL")
    assert at_deadline["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXIT_RETRY_DEADLINE"
    after_expiry = replay_synthetic_account([signal], mode="CALL",
        as_of_utc=datetime(2022, 1, 24, 14, 35, tzinfo=UTC))
    assert after_expiry["decisions"][0]["status"] == "OPEN_UNRESOLVED_EXPIRY_OR_ASSIGNMENT"
    assert after_expiry["ledger"] == at_deadline["ledger"]
    assert after_expiry["ending_cash"] == at_deadline["ending_cash"]
    assert after_expiry["ending_reserved_exit_fees"] == at_deadline["ending_reserved_exit_fees"]
    assert after_expiry["ending_equity"] is None


def test_future_quote_values_cannot_change_entry_or_earlier_snapshot():
    signal, p = fixture()
    first, second, third = p.attempt_times_utc
    before = replay_synthetic_account([signal], mode="CALL", as_of_utc=first)
    altered = replay_synthetic_account([signal], mode="CALL", as_of_utc=first,
        exit_quotes={(signal.case_id, second): quote(p.option_symbol, second, bid_per_share="999", ask_per_share="1000")})
    assert altered == before
    assert len(before["ledger"]) == 2
    assert before["decisions"][0]["status"] == "OPEN_AWAITING_EXIT_RETRY"


def test_missing_quote_keeps_slot_occupied_for_competing_entry():
    a, p = fixture()
    second_entry = p.attempt_times_utc[1]
    b = replace(a, case_id="second", ticker="XYZ", stock=None, put=None,
                call=replace(a.call, symbol="O:XYZ220121C00100000",
                             entry_at_utc=second_entry, exit_retry_plan=None))
    report = replay_synthetic_account([a, b], mode="CALL",
                                      policy=ReplayPolicy(max_open_positions=1))
    assert report["decisions"][1]["status"] == "MAX_CONCURRENT_POSITIONS_REACHED"
    assert report["decisions"][1]["units"] == 0
    assert report["end_open_positions"] == 1


def test_successful_retry_releases_slot_before_entry_at_same_clock():
    a, p = fixture()
    at = p.attempt_times_utc[1]
    b = replace(a, case_id="second", ticker="XYZ", stock=None, put=None,
                call=replace(a.call, symbol="O:XYZ220121C00100000", entry_at_utc=at,
                             exit_retry_plan=None))
    report = replay_synthetic_account([b, a], mode="CALL",
        policy=ReplayPolicy(max_open_positions=1),
        exit_quotes={(a.case_id, at): quote(p.option_symbol, at)})
    assert report["decisions"][1]["units"] > 0
    kinds = [e["kind"] for e in report["ledger"]]
    assert kinds == ["MODELED_ENTRY", "MODELED_EXIT_ATTEMPT_UNRESOLVED", "MODELED_EXIT", "MODELED_ENTRY"]
    assert report["ledger"][2]["at_utc"] == report["ledger"][3]["at_utc"]


def test_rejected_entry_does_not_read_future_retry_quotes():
    signal, p = fixture()
    rejected = replace(signal, call=replace(signal.call, source_integrity_qualified=False))
    class ForbiddenQuotes(dict):
        def get(self, *_):
            pytest.fail("rejected entry cannot inspect future quotes")
    report = replay_synthetic_account([rejected], mode="CALL", exit_quotes=ForbiddenQuotes())
    assert report["ledger"] == []
    assert report["decisions"][0]["status"] == "UNQUALIFIED_SOURCE_INTEGRITY"
    assert "option_exit_retries" not in report


@pytest.mark.parametrize("changes", [
    {"exit_at_utc": datetime(2022, 1, 5, 21, 0, tzinfo=UTC), "exit_per_share": "3.00"},
    {"symbol": "O:XYZ220121C00100000"},
    {"entry_at_utc": datetime(2022, 1, 4, 20, 0, tzinfo=UTC)},
    {"exit_source_integrity_qualified": True},
])
def test_retry_plan_cannot_be_transplanted_or_combined_with_fixed_exit(changes):
    signal, _ = fixture()
    with pytest.raises(OfflineAccountReplayError, match="retry plan"):
        replay_synthetic_account([replace(signal, call=replace(signal.call, **changes))], mode="CALL")


def test_new_retry_path_requires_positive_bid_and_sufficient_size():
    signal, p = fixture()
    first, second, third = p.attempt_times_utc
    report = replay_synthetic_account([signal], mode="CALL", exit_quotes={
        (signal.case_id, first): quote(p.option_symbol, first, bid_per_share="0"),
        (signal.case_id, second): quote(p.option_symbol, second, bid_size_contracts=1),
    })
    assert [e["reason"] for e in report["ledger"][1:]] == [
        "NO_EXECUTABLE_BID", "INSUFFICIENT_DISPLAYED_BID_SIZE", "NO_QUOTE",
    ]
    assert report["synthetic_round_trips"] == 0
    assert report["ending_equity"] is None


def test_wrong_contract_quote_cannot_trigger_an_alternate_instrument_exit():
    signal, p = fixture()
    at = p.attempt_times_utc[0]
    report = replay_synthetic_account([signal], mode="CALL",
        exit_quotes={(signal.case_id, at): quote("O:OTHER220121C00100000", at)})
    assert report["ledger"][1]["reason"] == "QUOTE_CONTRACT_MISMATCH"
    assert report["end_open_positions"] == 1


def test_retry_quotes_for_unchosen_mode_are_not_read_and_legacy_shape_is_preserved():
    signal, p = fixture()
    class ForbiddenQuotes(dict):
        def get(self, *_):
            pytest.fail("unchosen option mode cannot inspect retry quotes")
    stock = replay_synthetic_account([signal], mode="STOCK", exit_quotes=ForbiddenQuotes())
    baseline = replay_synthetic_account([_fixture()[0]], mode="STOCK")
    assert stock == baseline
    assert "option_exit_retries" not in stock


def test_future_only_retry_snapshot_has_no_attempts_and_keeps_entry_capital():
    signal, p = fixture()
    before = replay_synthetic_account([signal], mode="CALL",
        as_of_utc=p.requested_exit_at_utc - timedelta(seconds=1))
    assert len(before["ledger"]) == 1
    assert before["option_exit_retries"][0]["cursor"]["attempts"] == []
    assert before["decisions"][0]["status"] == "OPEN_EXIT_NOT_REQUESTED_YET"
    assert before["ending_cash"] == "90168.15"
    assert before["ending_reserved_exit_fees"] == "31.85"


def test_option_slippage_is_charged_once_only_after_a_qualified_quote():
    signal, p = fixture()
    at = p.attempt_times_utc[1]
    policy = ReplayPolicy(initial_cash="10000.00", option_slippage_per_share="0.25")
    before = replay_synthetic_account([signal], mode="CALL", policy=policy,
                                      as_of_utc=p.attempt_times_utc[0])
    after = replay_synthetic_account([signal], mode="CALL", policy=policy,
        exit_quotes={(signal.case_id, at): quote(p.option_symbol, at)})
    assert before["ledger"][0]["units"] == 4
    assert before["ending_cash"] == "9097.40"
    assert before["ending_reserved_exit_fees"] == "2.60"
    assert after["ledger"][:2] == before["ledger"]
    assert after["ledger"][2]["cash_delta"] == "1097.40"
    assert after["ending_cash"] == "10194.80"
    assert after["modeled_realized_pnl"] == "194.80"


def test_put_retry_uses_the_exact_put_and_cohort_order_is_deterministic():
    original = _fixture()[0]
    _, call_plan = fixture()
    p = build_option_exit_retry_plan(
        option_symbol=original.put.symbol, expiration=original.put.expiration,
        opened_at_utc=original.put.entry_at_utc,
        requested_exit_at_utc=call_plan.requested_exit_at_utc,
        deadline_at_utc=call_plan.deadline_at_utc,
        retry_interval_seconds=60, maximum_attempts=3, maximum_quote_age_seconds=30,
    )
    signal = replace(original, put=replace(original.put, exit_at_utc=None,
                      exit_per_share=None, exit_retry_plan=p))
    other = _fixture()[1]
    at = p.attempt_times_utc[1]
    quotes = {(signal.case_id, at): quote(p.option_symbol, at, bid_per_share="0.70", ask_per_share="0.80")}
    policy = ReplayPolicy(initial_cash="10000.00")
    first = replay_synthetic_account([signal, other], mode="PUT", policy=policy, exit_quotes=quotes)
    assert first == replay_synthetic_account([other, signal], mode="PUT", policy=policy, exit_quotes=quotes)
    assert first["ending_cash"] == "9443.50"
    assert first["synthetic_round_trips"] == 1
