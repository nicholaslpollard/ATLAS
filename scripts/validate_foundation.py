from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.market_calendar import MarketCalendar
from packages.core.settings import load_settings
from packages.core.enums import SessionSegment


def main() -> int:
    settings = load_settings(ROOT)

    print(f"ATLAS project: {settings.project.name} {settings.project.version}")
    print(f"Environment: {settings.app.environment}")
    print(f"Trading mode: {settings.app.trading_mode}")
    print(f"Canonical timezone: {settings.app.canonical_timezone}")

    calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
    sample_session = date(2026, 8, 14)
    assert calendar.is_session(sample_session), "Expected 2026-08-14 to be a trading session"

    eastern = ZoneInfo(settings.data.calendar.market_timezone)
    regular_sample = datetime(2026, 8, 14, 10, 0, tzinfo=eastern)
    assert calendar.classify(regular_sample) == SessionSegment.REGULAR

    print("Configuration validation: PASS")
    print("Calendar/session validation: PASS")
    print("Phase 01 foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
