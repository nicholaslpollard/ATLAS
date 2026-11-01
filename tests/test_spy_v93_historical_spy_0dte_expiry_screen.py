from __future__ import annotations

"""V93 historical SPY 0DTE eligibility: base weekly schedule, not PnL."""

from datetime import date

from scripts.run_spy_v89_six_family_source_batch import regular_spy_zero_dte_schedule_eligible as eligible


def test_2018_tuesday_thursday_were_not_standard_spy_0dte_weeklies():
    assert not eligible(date(2018,1,2))  # Tue
    assert not eligible(date(2018,1,4))  # Thu
    assert eligible(date(2018,1,3))      # Wed
    assert eligible(date(2018,1,5))      # Fri


def test_first_2018_monday_expiry_is_later_than_first_february_listing():
    assert not eligible(date(2018,2,19))
    assert eligible(date(2018,2,26))
    assert not eligible(date(2018,3,1))


def test_2022_daily_spy_weeklies_started_only_late_november():
    assert not eligible(date(2022,11,15)) # Tue prior to launch
    assert eligible(date(2022,11,22))     # Tuesday weekly
    assert not eligible(date(2022,11,17)) # Thursday not yet expiring
    assert eligible(date(2022,12,1))      # first regular Thursday trading session


def test_newer_periods_keep_original_per_session_decisions_unchanged():
    for d in [date(2023,4,3),date(2023,4,4),
              date(2023,4,5),date(2023,4,6),
              date(2024,1,2),date(2025,12,18)]:
        assert eligible(d)


def test_weekends_never_get_zero_dte():
    assert not eligible(date(2021,6,12))
    assert not eligible(date(2021,6,13))
