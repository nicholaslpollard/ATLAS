from __future__ import annotations

import hashlib
import json
from datetime import datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from packages.data import marketdata_massive_dia_aggregate_surface_v1 as surface


EASTERN = ZoneInfo("America/New_York")


def _epoch_seconds(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(16, 0), tzinfo=EASTERN).timestamp())


def _epoch_millis(date_text: str) -> int:
    d = datetime.fromisoformat(date_text).date()
    return int(datetime.combine(d, time(0, 0), tzinfo=EASTERN).timestamp() * 1000)


def _write_raw(path, payload):
    encoded = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "bytes": len(encoded),
    }


def test_surface_classification() -> None:
    assert (
        surface._classify_surface(daily_present=True, minute_rows=3)
        == "DAILY_AND_MINUTE_AGGREGATES_PRESENT"
    )
    assert (
        surface._classify_surface(daily_present=True, minute_rows=0)
        == "DAILY_PRESENT_MINUTE_ABSENT"
    )
    assert (
        surface._classify_surface(daily_present=False, minute_rows=3)
        == "DAILY_ABSENT_MINUTE_PRESENT"
    )
    assert (
        surface._classify_surface(daily_present=False, minute_rows=0)
        == "DAILY_AND_MINUTE_AGGREGATES_ABSENT"
    )


class _FakeMassive:
    def __init__(self, controls: set[str]):
        self.controls = controls
        self.calls = []

    def get_json(self, path, params=None):
        self.calls.append((path, params))
        session_date = path.rsplit("/", 2)[1]
        results = []
        if session_date in self.controls:
            results = [
                {
                    "t": _epoch_millis(session_date),
                    "o": 1.0,
                    "h": 1.1,
                    "l": 0.9,
                    "c": 1.0,
                    "v": 2,
                }
            ]
        return {
            "status": "OK",
            "ticker": surface.CONTRACT["target"]["massive_ticker"],
            "resultsCount": len(results),
            "results": results,
        }


def test_end_to_end_surface_consistency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    dates = [
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
        "2026-08-06",
        "2026-08-07",
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
    ]
    controls = {
        "2026-08-03",
        "2026-08-04",
        "2026-08-05",
        "2026-08-11",
    }

    source_root = tmp_path / "source"
    quote_receipt = _write_raw(
        source_root / "quotes.json",
        {
            "s": "ok",
            "optionSymbol": [surface.CONTRACT["target"]["option_symbol"]] * 9,
            "last": [1.0] * 9,
            "volume": [1, 2, 3, 0, 0, 0, 4, 0, 0],
            "bid": [0.9] * 9,
            "ask": [1.1] * 9,
            "updated": [_epoch_seconds(d) for d in dates],
        },
    )
    aggregate_receipt = _write_raw(
        source_root / "daily.json",
        {
            "status": "OK",
            "results": [
                {
                    "t": _epoch_millis(d),
                    "o": 1.0,
                    "h": 1.1,
                    "l": 0.9,
                    "c": 1.0,
                    "v": 2,
                }
                for d in sorted(controls)
            ],
        },
    )
    source = {
        "anchors": [
            {
                "root": "DIA",
                "option_symbol": surface.CONTRACT["target"]["option_symbol"],
                "passed": False,
                "marketdata_quote_rows": 9,
                "massive_aggregate_rows": 4,
                "overlap_sessions": 4,
                "quote_raw_receipt": quote_receipt,
                "massive_raw_receipt": aggregate_receipt,
            }
        ]
    }
    monkeypatch.setattr(surface, "load_failed_validation_report", lambda settings: source)

    fake = _FakeMassive(controls)
    report = surface.run_marketdata_massive_dia_aggregate_surface_v1(
        SimpleNamespace(project_root=tmp_path),
        massive_client=fake,
    )

    assert report["status"] == "AGGREGATE_SURFACES_CONSISTENT"
    assert report["surface_consistent"] is True
    assert len(report["records"]) == 9
    assert len(fake.calls) == 9
    assert all(
        (item["minute_aggregate_rows"] > 0) == item["daily_present"]
        for item in report["records"]
    )
    assert report["limitations"][
        "cannot_distinguish_no_raw_trades_from_ineligible_raw_trades"
    ] is True
    assert report["authority"]["historical_price_authority"] is False


def test_surface_inconsistency_is_not_a_pass(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    records = [
        {
            "disposition": "DAILY_AND_MINUTE_AGGREGATES_PRESENT",
        },
        {
            "disposition": "DAILY_ABSENT_MINUTE_PRESENT",
        },
    ]
    assert surface._surface_consistent(records) is False
