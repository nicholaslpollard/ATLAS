from datetime import date

from packages.aggregation.sessionizer import session_boundaries
from packages.core.market_calendar import MarketCalendar


def test_august_session_boundaries_are_session_anchored():
    d = date(2026, 8, 14)
    bounds = session_boundaries(d, MarketCalendar())
    # EDT is UTC-4 in August.
    assert bounds.premarket_start_utc.isoformat() == "2026-08-14T08:00:00+00:00"
    assert bounds.regular_open_utc.isoformat() == "2026-08-14T13:30:00+00:00"
    assert bounds.regular_close_utc.isoformat() == "2026-08-14T20:00:00+00:00"
    assert bounds.after_hours_end_utc.isoformat() == "2026-08-15T00:00:00+00:00"
