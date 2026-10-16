from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal, localcontext

import pytest

from packages.core.market_calendar import get_market_calendar
from packages.strategies.options_native_economic_returns_v1 import (
    SyntheticEconomicIntervalV1, build_synthetic_pilot_economic_returns,
)
from packages.strategies.options_native_pair_v1 import NativePairError
from packages.strategies.options_native_pilot_v1 import SyntheticPilotVarianceInputV1, screen_synthetic_pilot_variance
from packages.strategies.options_native_pilot_v1_contract import IMPLIED_INPUT_FINGERPRINT

CUTOFF = datetime(2020, 1, 6, 15, tzinfo=UTC)


def window():
    calendar = get_market_calendar("XNYS")
    days = calendar.sessions_in_range((CUTOFF - timedelta(days=75)).date(), CUTOFF.date())
    closes = [calendar.regular_open_close(d)[1] for d in days]
    closes = [x for x in closes if x < CUTOFF][-21:]
    return tuple(SyntheticEconomicIntervalV1(a, b, b + timedelta(seconds=30),
                 "100", "100", "1", "0", "a" * 64, True, True) for a, b in zip(closes, closes[1:]))


def build(rows=None):
    return build_synthetic_pilot_economic_returns(rows if rows is not None else window(), feature_cutoff_utc=CUTOFF)


def test_explicit_no_action_window_emits_twenty_returns_for_existing_variance_screen_only():
    report = build()
    assert report["status"] == "FIXTURE_ECONOMIC_WINDOW_READY"
    assert len(report["prior_returns"]) == 20
    assert all(r.log_return == "0" for r in report["prior_returns"])
    assert report["account_cash_credited"] == "0.00"
    assert not any(report["authority"].values())
    screen = screen_synthetic_pilot_variance(SyntheticPilotVarianceInputV1(
        CUTOFF, CUTOFF + timedelta(days=32), tuple(report["prior_returns"]), "0.1", "0.1",
        CUTOFF, CUTOFF, IMPLIED_INPUT_FINGERPRINT, True, True, True, True,
    ))
    assert screen["reasons"] == ["NO_POSITIVE_FORECAST_VARIANCE_GAP"]


@pytest.mark.parametrize("before,after,factor,cash", [
    ("100", "50", "2", "0"),  # forward split preserves one old share's wealth
    ("100", "1000", "0.1", "0"),  # reverse split
    ("100", "98", "1", "2"),  # ex-date entitlement; no payment-date cash credit
    ("100", "49", "2", "2"),  # cash explicitly PER OLD SHARE on the split date
])
def test_split_or_ex_dividend_price_drop_is_not_a_spurious_economic_loss(before, after, factor, cash):
    rows = list(window())
    # Last interval avoids changing a shared following close.
    rows[-1] = replace(rows[-1], prior_raw_close=before, current_raw_close=after,
                       split_new_shares_per_old=factor, ex_date_cash_per_original_share=cash)
    report = build(tuple(rows))
    assert report["prior_returns"][-1].log_return == "0"
    assert report["account_cash_credited"] == "0.00"


def test_negative_price_return_and_deterministic_log_precision_are_preserved():
    rows = list(window())
    rows[-1] = replace(rows[-1], current_raw_close="99")
    expected = build(tuple(rows))
    with localcontext() as ctx:
        ctx.prec = 6
        actual = build(tuple(rows))
    assert expected == actual
    assert Decimal(actual["prior_returns"][-1].log_return) < 0
    screen = screen_synthetic_pilot_variance(SyntheticPilotVarianceInputV1(
        CUTOFF, CUTOFF + timedelta(days=32), tuple(actual["prior_returns"]), "0.1", "0.1",
        CUTOFF, CUTOFF, IMPLIED_INPUT_FINGERPRINT, True, True, True, True,
    ))
    assert screen["reasons"] == ["NO_POSITIVE_FORECAST_VARIANCE_GAP"]


@pytest.mark.parametrize("change,reason", [
    ({"complete_action_coverage_qualified": False}, "ACTION_COVERAGE_UNQUALIFIED"),
    ({"publication_and_revision_clocks_qualified": False}, "PUBLICATION_OR_REVISION_CLOCK"),
    ({"inputs_available_at_utc": CUTOFF + timedelta(minutes=2)}, "PUBLICATION_OR_REVISION_CLOCK"),
    ({"split_new_shares_per_old": None}, "MISSING_SPLIT_OR_CASH"),
    ({"ex_date_cash_per_original_share": None}, "MISSING_SPLIT_OR_CASH"),
    ({"cash_basis": "UNSPECIFIED_POST_SPLIT_SHARE"}, "AMBIGUOUS_CASH_SHARE_BASIS"),
    ({"unsupported_action_present": True}, "UNSUPPORTED_NONCASH_OR_IDENTITY_ACTION"),
])
def test_one_unqualified_interval_invalidates_the_whole_fixed_window(change, reason):
    rows = list(window())
    rows[5] = replace(rows[5], **change)
    report = build(tuple(rows))
    assert report["status"] == "FIXTURE_ABSTAIN"
    assert report["prior_returns"] == []
    assert any(reason in r for r in report["reasons"])


@pytest.mark.parametrize("change", [
    {"current_raw_close": "NaN"}, {"ex_date_cash_per_original_share": "-1"},
    {"split_new_shares_per_old": "0"}, {"origin": "HISTORICAL"},
    {"inputs_available_at_utc": datetime(2019, 1, 1, tzinfo=UTC)},
])
def test_invalid_or_historical_fixture_fails_closed(change):
    rows = list(window())
    rows[-1] = replace(rows[-1], **change)
    with pytest.raises(NativePairError):
        build(tuple(rows))


def test_window_cannot_drop_duplicate_or_disagree_on_shared_close():
    rows = window()
    for broken in (rows[:-1], (*rows[:-1], rows[0]), (*rows[:5], replace(rows[5], prior_raw_close="99"), *rows[6:])):
        with pytest.raises(NativePairError):
            build(tuple(broken))
