from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from packages.strategies.options_native_pair_v1 import (
    NativePairError, SyntheticPairQuoteV1, SyntheticPairSurfaceV1,
    SyntheticPairExitReviewV1, construct_synthetic_pilot_pair, review_synthetic_pilot_exit,
)
from packages.simulation.options_native_pair_account_v1 import synthetic_pair_intent


CUTOFF = datetime(2022, 1, 10, 15, tzinfo=UTC)


def quote(right="C", strike="00470000", expiry="220211", **changes):
    return replace(SyntheticPairQuoteV1(
        option_symbol=f"O:SPY{expiry}{right}{strike}",
        observed_at_utc=CUTOFF, available_at_utc=CUTOFF + timedelta(seconds=1),
        bid="9.50", ask="10.00", bid_size=1, ask_size=1, open_interest=100,
        oi_state_session=date(2022, 1, 7),
        oi_available_at_utc=datetime(2022, 1, 10, 12, tzinfo=UTC),
        source_qualified=True, option_hours_qualified=True,
        standard_deliverable_verified=True, reported_volume=0,
    ), **changes)


def surface(**changes):
    return replace(SyntheticPairSurfaceV1(
        case_id="weekly-fixture", feature_cutoff_utc=CUTOFF, spot="470.00",
        spot_observed_at_utc=CUTOFF, spot_available_at_utc=CUTOFF,
        roster_available_at_utc=CUTOFF, source_fingerprint="a" * 64,
        complete_identity_roster_qualified=True, spot_source_qualified=True,
        quotes=(quote(), quote("P")),
    ), **changes)


def test_pair_is_geometry_candidate_with_zero_volume_not_a_signal_or_fill():
    report = construct_synthetic_pilot_pair(surface())
    assert report["status"] == "FIXTURE_PAIR_CANDIDATE"
    assert report["reference_ask_debit_before_fees"] == "2000.00"
    assert report["selected_exact_symbols"] == ["O:SPY220211C00470000", "O:SPY220211P00470000"]
    assert report["variance_signal_bound"] is False
    assert report["historical_performance_evidence"] is False
    assert not any(report["authority"].values())
    intent = synthetic_pair_intent(surface(), fixture_signal_passed=True)
    assert intent.pair_fingerprint == report["pair_fingerprint"]
    assert intent.at_utc == CUTOFF + timedelta(minutes=1)
    assert intent.call_limit_per_share == intent.put_limit_per_share == "10.00"


def test_earliest_expiry_then_nearest_common_strike_and_lower_tie_precede_liquidity():
    rows = tuple(quote(right, strike, expiry) for expiry, strike in (
        ("220211", "00469000"), ("220211", "00471000"), ("220218", "00470000"),
    ) for right in ("C", "P"))
    report = construct_synthetic_pilot_pair(surface(quotes=tuple(reversed(rows))))
    assert report["expiration"] == "2022-02-11"
    assert report["strike"] == "469"
    assert report["selected_exact_symbols"] == ["O:SPY220211C00469000", "O:SPY220211P00469000"]
    failed = tuple(replace(q, bid="0") if q.option_symbol == "O:SPY220211C00469000" else q for q in rows)
    blocked = construct_synthetic_pilot_pair(surface(quotes=failed))
    assert blocked["status"] == "FIXTURE_ABSTAIN"
    assert blocked["selected_exact_symbols"] == report["selected_exact_symbols"]
    assert blocked["reference_ask_debit_before_fees"] is None


def test_missing_common_strike_in_first_expiry_does_not_choose_later_expiry():
    report = construct_synthetic_pilot_pair(surface(quotes=(
        quote(), quote("P", "00471000"), quote(expiry="220218"), quote("P", expiry="220218"),
    )))
    assert report["reasons"] == ["EARLIEST_EXPIRATION_HAS_NO_COMMON_STRIKE"]
    assert report["selected_exact_symbols"] == []


@pytest.mark.parametrize("changes,reason", [
    ({"source_qualified": False}, "SOURCE_OR_OPTION_HOURS_UNQUALIFIED"),
    ({"option_hours_qualified": False}, "SOURCE_OR_OPTION_HOURS_UNQUALIFIED"),
    ({"standard_deliverable_verified": False}, "DELIVERABLE_UNQUALIFIED"),
    ({"multiplier": 10}, "DELIVERABLE_UNQUALIFIED"),
    ({"observed_at_utc": None}, "QUOTE_CLOCK_UNKNOWN"),
    ({"available_at_utc": None}, "QUOTE_CLOCK_UNKNOWN"),
    ({"observed_at_utc": CUTOFF + timedelta(seconds=1)}, "QUOTE_FUTURE_STALE_OR_LATE"),
    ({"observed_at_utc": CUTOFF - timedelta(seconds=31)}, "QUOTE_FUTURE_STALE_OR_LATE"),
    ({"available_at_utc": CUTOFF + timedelta(seconds=61)}, "QUOTE_FUTURE_STALE_OR_LATE"),
    ({"available_at_utc": CUTOFF - timedelta(seconds=1)}, "QUOTE_FUTURE_STALE_OR_LATE"),
    ({"bid": None}, "MISSING_QUOTE_SIDE"),
    ({"ask": "0"}, "NONPOSITIVE_OR_CROSSED_QUOTE"),
    ({"bid": "11"}, "NONPOSITIVE_OR_CROSSED_QUOTE"),
    ({"bid": "5"}, "SPREAD_EXCEEDS_FROZEN_LIMIT"),
    ({"bid_size": 0}, "INSUFFICIENT_DISPLAYED_SIZE"),
    ({"ask_size": True}, "INSUFFICIENT_DISPLAYED_SIZE"),
    ({"open_interest": 99}, "OPEN_INTEREST_STATE_OR_AVAILABILITY_UNQUALIFIED"),
    ({"oi_state_session": date(2022, 1, 10)}, "OPEN_INTEREST_STATE_OR_AVAILABILITY_UNQUALIFIED"),
    ({"oi_available_at_utc": None}, "OPEN_INTEREST_STATE_OR_AVAILABILITY_UNQUALIFIED"),
    ({"oi_available_at_utc": CUTOFF + timedelta(seconds=61)}, "OPEN_INTEREST_STATE_OR_AVAILABILITY_UNQUALIFIED"),
    ({"oi_available_at_utc": datetime(2022, 1, 7, 20, tzinfo=UTC)}, "OPEN_INTEREST_STATE_OR_AVAILABILITY_UNQUALIFIED"),
])
def test_selected_leg_qualification_abstains_without_substitution(changes, reason):
    report = construct_synthetic_pilot_pair(surface(quotes=(quote(**changes), quote("P"))))
    assert report["status"] == "FIXTURE_ABSTAIN"
    assert "C:" + reason in report["reasons"]


def test_pair_clock_skew_is_independent_of_individual_freshness():
    report = construct_synthetic_pilot_pair(surface(quotes=(
        quote(observed_at_utc=CUTOFF - timedelta(seconds=2)), quote("P"),
    )))
    assert report["reasons"] == ["PAIR_QUOTE_OBSERVATION_SKEW"]


@pytest.mark.parametrize("changes,reason", [
    ({"complete_identity_roster_qualified": False}, "IDENTITY_ROSTER_UNQUALIFIED_OR_LATE"),
    ({"roster_available_at_utc": CUTOFF + timedelta(seconds=61)}, "IDENTITY_ROSTER_UNQUALIFIED_OR_LATE"),
    ({"spot_source_qualified": False}, "SPOT_SOURCE_OR_CLOCK_UNQUALIFIED"),
    ({"spot_observed_at_utc": CUTOFF - timedelta(seconds=61)}, "SPOT_SOURCE_OR_CLOCK_UNQUALIFIED"),
    ({"spot_observed_at_utc": CUTOFF + timedelta(seconds=1)}, "SPOT_SOURCE_OR_CLOCK_UNQUALIFIED"),
    ({"spot_available_at_utc": CUTOFF + timedelta(seconds=61)}, "SPOT_SOURCE_OR_CLOCK_UNQUALIFIED"),
])
def test_causal_spot_and_identity_roster_are_required(changes, reason):
    report = construct_synthetic_pilot_pair(surface(**changes))
    assert report["selected_exact_symbols"] == []
    assert reason in report["reasons"]


@pytest.mark.parametrize("clock", [
    CUTOFF.replace(tzinfo=None), CUTOFF + timedelta(days=1),
    CUTOFF + timedelta(seconds=1), datetime(2026, 1, 5, 15, tzinfo=UTC),
    datetime(2025, 11, 17, 15, tzinfo=UTC),
])
def test_scope_and_clock_fail_before_construction(clock):
    with pytest.raises(NativePairError):
        construct_synthetic_pilot_pair(surface(feature_cutoff_utc=clock))


@pytest.mark.parametrize("rows", [
    (quote(), quote()), (quote(option_symbol="O:QQQ220211C00470000"), quote("P")),
    (quote(option_symbol="O:SPY220230C00470000"), quote("P")),
])
def test_ambiguous_or_changed_identity_fails_closed(rows):
    with pytest.raises(NativePairError):
        construct_synthetic_pilot_pair(surface(quotes=rows))


def test_outside_dte_band_is_not_geometry_fallback_and_unknown_source_is_not_an_intent():
    report = construct_synthetic_pilot_pair(surface(quotes=(quote(expiry="220121"), quote("P", expiry="220121"))))
    assert report["reasons"] == ["NO_EXPIRATION_IN_FROZEN_DTE_BAND"]
    with pytest.raises(NativePairError):
        synthetic_pair_intent(surface(spot_source_qualified=False), fixture_signal_passed=True)


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "1e999", " 10", 10.0])
def test_bad_decimal_input_fails_closed(bad):
    with pytest.raises(NativePairError):
        construct_synthetic_pilot_pair(surface(spot=bad))


def exit_review(**changes):
    return replace(SyntheticPairExitReviewV1(
        entry_order_eligible_utc=CUTOFF + timedelta(minutes=1),
        feature_cutoff_utc=CUTOFF + timedelta(days=1),
        call_symbol="O:SPY220211C00470000", put_symbol="O:SPY220211P00470000",
        variance_gap="0.001", variance_inputs_qualified=True,
    ), **changes)


@pytest.mark.parametrize("gap,action", [("0.001", "HOLD"), ("0", "REQUEST_EXIT"), ("-0.001", "REQUEST_EXIT")])
def test_daily_thesis_exit_rechecks_variance_and_preserves_contracts_and_capital(gap, action):
    review = exit_review(variance_gap=gap)
    result = review_synthetic_pilot_exit(review)
    assert result["action"] == action
    assert result["original_exact_symbols"] == [review.call_symbol, review.put_symbol]
    assert result["cash_released"] == "0.00"
    assert result["order_eligible_utc"] == "2022-01-11T15:01:00+00:00"


def test_missing_variance_cannot_disable_session_guard_and_holiday_is_not_a_session():
    before = review_synthetic_pilot_exit(exit_review(
        feature_cutoff_utc=datetime(2022, 1, 14, 15, tzinfo=UTC), variance_gap=None,
    ))
    guard = review_synthetic_pilot_exit(exit_review(
        feature_cutoff_utc=datetime(2022, 1, 18, 15, tzinfo=UTC), variance_gap=None,
    ))
    assert before["subsequent_sessions"] == 4 and before["action"] == "HOLD"
    assert guard["subsequent_sessions"] == 5 and guard["action"] == "REQUEST_EXIT"
    assert guard["reasons"] == ["MAXIMUM_HOLDING_SESSIONS_REACHED"]
    assert guard["variance_feature_state"] == "MISSING_OR_UNQUALIFIED"


def test_unqualified_feature_does_not_establish_thesis_exit_but_dte_guard_remains():
    early = review_synthetic_pilot_exit(exit_review(variance_gap="-1", variance_inputs_qualified=False))
    assert early["action"] == "HOLD"
    late = review_synthetic_pilot_exit(exit_review(
        feature_cutoff_utc=datetime(2022, 1, 28, 15, tzinfo=UTC), variance_gap=None,
    ))
    assert late["calendar_dte"] == 14
    assert "DTE_GUARD_REACHED" in late["reasons"]


@pytest.mark.parametrize("change", [
    {"feature_cutoff_utc": CUTOFF}, {"feature_cutoff_utc": CUTOFF + timedelta(days=7)},
    {"put_symbol": "O:SPY220211P00471000"}, {"variance_gap": "NaN"},
    {"feature_cutoff_utc": CUTOFF + timedelta(days=1, seconds=1)},
])
def test_exit_review_rejects_incompatible_identity_clock_or_numeric_state(change):
    with pytest.raises(NativePairError):
        review_synthetic_pilot_exit(exit_review(**change))
