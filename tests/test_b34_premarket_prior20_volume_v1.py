from __future__ import annotations

from datetime import UTC, date, datetime, time
from pathlib import Path
from types import SimpleNamespace
import json
import subprocess
import sys

import pytest

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.data.b34_premarket_decision_context_v1 import PremarketContextError
from packages.data.b34_premarket_prior20_volume_v1 import (
    PRIOR_SESSIONS, review_prior20,
)
from packages.schemas.market import CanonicalBar
import scripts.review_b34_premarket_prior20_volume_v1 as cli


DAY = date(2026, 4, 30)
SRC = "alpaca:sip:1Min:raw:asof=-:v2:unit=synthetic-Apr2026"


def bar(day: date, hour: int, minute: int, volume: int, *,
        close: float = 10.0, segment=SessionSegment.PREMARKET,
        adjusted=False) -> CanonicalBar:
    dt = datetime(day.year, day.month, day.day, hour + 4, minute, tzinfo=UTC)
    return CanonicalBar(
        symbol="ZSL", timestamp_utc=dt, session_date=day,
        timeframe=Timeframe.MINUTE_1, session_segment=segment,
        open=close, high=close + .01, low=close - .01, close=close,
        volume=volume, vwap=close, transaction_count=1,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id=SRC, is_adjusted=adjusted, provider_timestamp_utc=dt
    )


def previous():
    days = MarketCalendar().sessions_in_range(date(2026, 4, 1),
                                                date(2026, 4, 29))
    assert len(days) == 20
    return days


def current():
    return [
        bar(DAY, 9, 0, 250),
        bar(DAY, 9, 19, 200),
        bar(DAY, 9, 20, 150),
        bar(DAY, 9, 29, 500),
        bar(DAY, 9, 30, 1_000, segment=SessionSegment.REGULAR),
        bar(DAY, 9, 34, 600, segment=SessionSegment.REGULAR),
        bar(DAY, 9, 35, 999_999, segment=SessionSegment.REGULAR),
    ]


def historical(dates):
    return {
        d: [
            bar(d, 9, 0, 100), bar(d, 9, 19, 200),
            bar(d, 9, 20, 300), bar(d, 9, 29, 400),
        ] for d in dates
    }


def test_exact_20_sessions_same_time_comparison_and_no_trading_authority():
    days = previous()
    report = review_prior20(
        symbol="ZSL", current_session=DAY, current_bars=current(),
        prior_sessions=days, prior_bars_by_session=historical(days)
    )
    assert report["provider_requests"] == 0
    assert report["signal_authority"] is False
    assert report["split_or_corporate_action_history_checked"] is False
    assert len(report["snapshots"]) == 3
    a, b, c = report["snapshots"]
    assert a["decision_clock_et"] == "09:20:00"
    assert a["current_observed_premarket_volume"] == 450
    assert a["prior_20_median_observed_premarket_volume"] == 300
    assert a["raw_volume_ratio_diagnostic_only"] == pytest.approx(1.5)
    assert b["decision_clock_et"] == "09:30:00"
    assert b["current_observed_premarket_volume"] == 1100
    assert b["prior_20_median_observed_premarket_volume"] == 1000
    assert b["raw_volume_ratio_diagnostic_only"] == pytest.approx(1.1)
    assert c["decision_clock_et"] == "09:35:00"
    assert c["raw_volume_ratio_diagnostic_only"] == pytest.approx(1.1)
    assert all(x["prior_sessions_with_observed_premarket"] == 20
               and x["volume_ratio_admissible_as_strategy_input"] is False
               for x in report["snapshots"])


def test_future_prices_and_later_volume_cannot_change_prior_context():
    days = previous()
    early = review_prior20(
        symbol="ZSL", current_session=DAY, current_bars=current(),
        prior_sessions=days, prior_bars_by_session=historical(days)
    )
    changed = current()[:6] + [
        bar(DAY, 9, 35, 10**9, close=999,
            segment=SessionSegment.REGULAR),
    ]
    late = review_prior20(
        symbol="ZSL", current_session=DAY, current_bars=changed,
        prior_sessions=days, prior_bars_by_session=historical(days)
    )
    assert early == late


def test_missing_prior_session_observation_does_not_impute_zero():
    days = previous()
    history = historical(days)
    history[days[0]] = []
    report = review_prior20(
        symbol="ZSL", current_session=DAY, current_bars=current(),
        prior_sessions=days, prior_bars_by_session=history
    )
    for row in report["snapshots"]:
        assert row["prior_sessions_with_observed_premarket"] == 19
        assert row["prior_sessions_missing_premarket"] == [days[0].isoformat()]
        assert row["prior_20_median_observed_premarket_volume"] is None
        assert row["raw_volume_ratio_diagnostic_only"] is None


def test_invalid_calendar_or_wrong_raw_source_fails_closed():
    days = previous()
    with pytest.raises(PremarketContextError, match="SESSION_CALENDAR_MISMATCH"):
        review_prior20(
            symbol="ZSL", current_session=DAY, current_bars=current(),
            prior_sessions=days[:-1], prior_bars_by_session=historical(days[:-1])
        )
    bad = historical(days)
    bad[days[0]][0] = bad[days[0]][0].model_copy(
        update={"is_adjusted": True}
    )
    with pytest.raises(PremarketContextError, match="CANONICAL_SOURCE_MISMATCH"):
        review_prior20(
            symbol="ZSL", current_session=DAY, current_bars=current(),
            prior_sessions=days, prior_bars_by_session=bad
        )
    with pytest.raises(PremarketContextError, match="SCOPE_NOT_APPROVED"):
        review_prior20(
            symbol="ZSL", current_session=date(2026, 5, 13),
            current_bars=current(), prior_sessions=days,
            prior_bars_by_session=historical(days)
        )


def test_bounded_operator_review_uses_one_accepted_april_source(
    tmp_path, monkeypatch
):
    days = previous()
    source = tmp_path / "april.parquet"
    source.write_bytes(b"no-market-data-fixture")
    report_file = tmp_path / "b34.json"
    report_file.write_text(json.dumps({
        "sample_classes": [{
            "sample_class": "liquid_symbol_day",
            "canonical_path": str(source), "symbol": "ZSL",
            "session_date": DAY.isoformat(),
        }]
    }), encoding="utf-8")
    monkeypatch.setattr(
        cli, "ROOT", tmp_path
    )
    monkeypatch.setattr(
        cli.V2Layout, "beneath",
        lambda _: SimpleNamespace(validation=tmp_path)
    )
    report_file.rename(tmp_path / "b34_intraday_semantics_audit.json")
    scopes_reviewed = []

    def pinned_review(*, sample_classes):
        scopes_reviewed.append(sample_classes)
        return {
            "samples": [{
                "sample_class": "liquid_symbol_day",
                "symbol": "ZSL", "session_date": DAY.isoformat(),
                "source_row_count": 720,
                "verified_canonical_sha256": "a" * 64
            }],
            "accepted_b34_evidence_sha256": "b" * 64
        }

    monkeypatch.setattr(cli, "run_review", pinned_review)
    monkeypatch.setattr(
        cli.MarketCalendar, "sessions_in_range",
        lambda self, start, end: days
    )
    monkeypatch.setattr(cli, "_read_current", lambda path: current())
    calls = []

    def fake_query(path, *, symbol, first, last_exclusive):
        calls.append((path, symbol, first, last_exclusive))
        return [b.model_dump(mode="python") for day in days
                for b in historical(days)[day]]

    monkeypatch.setattr(cli, "_query_prior_premarket", fake_query)
    report = cli.run_with_current()
    assert scopes_reviewed == [("liquid_symbol_day",)]
    assert report["contract"] == cli.CONTRACT
    assert report["source_contract"] == (
        "atlas-b34-premarket-prior20-volume-observation-v1-no-signal"
    )
    assert len(calls) == 1
    assert calls[0] == (source, "ZSL", days[0], DAY)
    assert report["provider_requests"] == 0
    assert report["prior_rows_read"] == 80
    assert report["snapshots"][0]["raw_volume_ratio_diagnostic_only"] == 1.5
    audit = cli._save(report, tmp_path / "out")
    assert audit == cli._save(report, tmp_path / "out")
    assert len(list((tmp_path / "out").glob("*.json"))) == 1
    assert json.loads(audit.read_text())["fingerprint"] == cli._fingerprint(report)


@pytest.mark.parametrize("invocation", ["direct", "module"])
def test_real_command_line_imports_without_provider_or_source_access(invocation):
    # --help exits during argparse, before local source or provider reads.
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "review_b34_premarket_prior20_volume_v1.py"
    command = ([sys.executable, str(script)] if invocation == "direct"
               else [sys.executable, "-m",
                     "scripts.review_b34_premarket_prior20_volume_v1"])
    completed = subprocess.run(
        [*command, "--help"], cwd=root, capture_output=True, text=True,
        timeout=30, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "--no-write" in completed.stdout
