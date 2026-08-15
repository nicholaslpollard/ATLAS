from __future__ import annotations

from datetime import date

from packages.core.market_calendar import MarketCalendar
from packages.schemas.ingestion import ProviderFileDescriptor


def missing_remote_sessions(
    start_date: date,
    end_date: date,
    descriptors: list[ProviderFileDescriptor],
    calendar: MarketCalendar,
) -> list[date]:
    available = {item.trading_date for item in descriptors}
    return [session for session in calendar.sessions_in_range(start_date, end_date) if session not in available]
