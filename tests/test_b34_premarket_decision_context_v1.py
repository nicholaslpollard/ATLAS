from __future__ import annotations

from datetime import UTC, date, datetime, time
import hashlib
import json
from types import SimpleNamespace

import pytest

from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.data.b34_premarket_decision_context_v1 import (
    B34_LAST_SAFE_SESSION, PremarketContextError,
    build_context, build_three_cutoffs,
)
from packages.data.intraday_semantics_audit import B34_MAX_SAMPLE_DATE
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import B34_INTRADAY_PACK_FINGERPRINT
import scripts.review_b34_premarket_decision_context_v1 as runner


DAY = date(2026, 4, 30)
SRC = "alpaca:sip:1Min:raw:asof=-:v2:unit=synthetic-test-only"


def bar(hour: int, minute: int, *, close: float, volume: float,
        segment: SessionSegment, symbol: str = "TEST",
        source_id: str = SRC, day: date = DAY) -> CanonicalBar:
    # 2026-04-30 is EDT; both timestamps preserve the UTC left minute edge.
    stamp = datetime(day.year, day.month, day.day, hour + 4, minute, tzinfo=UTC)
    return CanonicalBar(
        symbol=symbol, timestamp_utc=stamp, session_date=day,
        timeframe=Timeframe.MINUTE_1, session_segment=segment,
        open=close, high=close + 0.02, low=close - 0.02, close=close,
        volume=volume, vwap=close, transaction_count=10,
        provider=DataProvider.ALPACA, dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id=source_id, is_adjusted=False, provider_timestamp_utc=stamp,
    )


def fixture_bars() -> list[CanonicalBar]:
    return [
        bar(9, 0, close=10.00, volume=100, segment=SessionSegment.PREMARKET),
        bar(9, 19, close=10.20, volume=200, segment=SessionSegment.PREMARKET),
        bar(9, 29, close=10.30, volume=300, segment=SessionSegment.PREMARKET),
        bar(9, 30, close=10.45, volume=400, segment=SessionSegment.REGULAR),
        bar(9, 34, close=10.60, volume=500, segment=SessionSegment.REGULAR),
        bar(9, 35, close=80.00, volume=9000, segment=SessionSegment.REGULAR),
        bar(10, 0, close=900.00, volume=99999, segment=SessionSegment.REGULAR),
    ]


def snapshots(bars):
    return build_three_cutoffs(bars, symbol="TEST", session_date=DAY)


def test_three_clocks_exclude_current_and_future_one_minute_bars():
    pre, opened, decision = snapshots(fixture_bars())
    a, b, c = (ctx["features"] for ctx in (pre, opened, decision))
    assert pre["decision_et"].endswith("09:20:00-04:00")
    assert pre["feature_status"] == "OBSERVED_PREMARKET_CONTEXT"
    assert a["premarket_observed_minutes"] == 2
    assert a["premarket_cumulative_volume"] == 300
    assert a["premarket_last_close"] == 10.20
    assert a["regular_observed_closed_minutes"] == 0
    assert b["premarket_observed_minutes"] == 3
    assert b["premarket_cumulative_volume"] == 600
    assert b["premarket_last_close"] == 10.30
    assert b["regular_observed_closed_minutes"] == 0
    assert c["premarket_observed_minutes"] == 3
    assert c["regular_observed_closed_minutes"] == 2
    assert c["regular_last_closed_price"] == 10.60
    assert c["regular_opening_range_high_so_far"] == pytest.approx(10.62)
    assert c["regular_last_vs_premarket_close_pct"] == pytest.approx(10.6/10.3 - 1)
    assert all(ctx["provider_requests"] == 0 for ctx in (pre, opened, decision))
    assert all(ctx["protected_outcomes_opened"] == 0 for ctx in (pre, opened, decision))


def test_future_price_mutations_cannot_change_any_decision_snapshot():
    original = fixture_bars()
    future_changed = original[:5] + [
        bar(9, 35, close=1000, volume=1e8, segment=SessionSegment.REGULAR),
        bar(11, 0, close=100, volume=2e8, segment=SessionSegment.REGULAR),
    ]
    assert snapshots(original) == snapshots(future_changed)
    assert snapshots(original) == snapshots(reversed(original))


def test_clock_boundary_exactly_0920_and_0935_is_not_used_early():
    rows = fixture_bars() + [
        bar(9, 20, close=50, volume=7000, segment=SessionSegment.PREMARKET)
    ]
    pre, open_, at_935 = snapshots(rows)
    assert pre["features"]["premarket_observed_minutes"] == 2
    assert open_["features"]["premarket_observed_minutes"] == 4
    assert at_935["features"]["regular_observed_closed_minutes"] == 2


def test_absent_trade_minutes_are_not_zero_filled_or_called_halts():
    empty = snapshots([])
    assert all(ctx["feature_status"] == "NO_OBSERVED_PREMARKET_BARS" for ctx in empty)
    for ctx in empty:
        f = ctx["features"]
        assert f["premarket_observed_minutes"] == 0
        assert f["premarket_last_close"] is None
        assert f["regular_last_closed_price"] is None
        assert f["premarket_volume_rel_20"] is None
        assert f["prior_regular_close_gap"] is None
        assert f["option_bid_ask"] is None


@pytest.mark.parametrize("invalid_clock", [time(9, 19), time(9, 31), time(10, 0)])
def test_only_preregistered_clocks_are_allowed(invalid_clock):
    with pytest.raises(PremarketContextError, match="NOT_AUTHORIZED"):
        build_context(fixture_bars(), symbol="TEST", session_date=DAY,
                      decision_clock_et=invalid_clock)


def test_source_scope_blocks_splits_aliases_and_protected_dates():
    assert B34_LAST_SAFE_SESSION == B34_MAX_SAMPLE_DATE
    with pytest.raises(PremarketContextError, match="NOT_AUTHORIZED"):
        build_context([], symbol="TEST", session_date=date(2026, 5, 12),
                      decision_clock_et=time(9, 35))
    broken = fixture_bars()
    broken[0] = broken[0].model_copy(update={"is_adjusted": True})
    with pytest.raises(PremarketContextError, match="SOURCE_MISMATCH"):
        snapshots(broken)
    broken2 = fixture_bars()
    broken2[0] = broken2[0].model_copy(
        update={"source_id": "unverified:minute:snapshot"}
    )
    with pytest.raises(PremarketContextError, match="SOURCE_MISMATCH"):
        snapshots(broken2)


def test_duplicate_eligible_minute_fails_closed():
    with pytest.raises(PremarketContextError, match="DUPLICATE"):
        snapshots(fixture_bars() + [fixture_bars()[0]])


def test_source_review_uses_only_two_pinned_accepted_samples(tmp_path, monkeypatch):
    (tmp_path / "docs/evidence").mkdir(parents=True)
    validation = tmp_path / "data" / "validation"
    validation.mkdir(parents=True)
    canonical = tmp_path / "canonical.parquet"
    canonical.write_bytes(b"synthetic-canonical-bundle")
    sha = hashlib.sha256(canonical.read_bytes()).hexdigest()
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(json.dumps({"canonical": {"sha256": sha}}), encoding="utf-8")

    accepted = {
        "status": "ACCEPTED",
        "opening_premarket_pack": {"fingerprint": B34_INTRADAY_PACK_FINGERPRINT},
        "enhanced_evidence_sha256": "a" * 64,
        "paper_authority": False, "live_authority": False,
        "full_minute_materialization_authority": False,
    }
    (tmp_path / "docs/evidence/b34_final_closeout_acceptance.json").write_text(
        json.dumps(accepted), encoding="utf-8"
    )
    sample_rows = fixture_bars()[:5]
    samples = [
        {"sample_class": typ, "symbol": "TEST",
         "session_date": DAY.isoformat(), "row_count": 5,
         "unit_id": "pin", "canonical_path": str(canonical), "accepted": True}
        for typ in runner.SAMPLE_CLASSES
    ]
    report = {
        "contract": "atlas-b34-intraday-source-readiness-v2-ohlcv-pack-frozen",
        "status": "ACCEPTED", "source_readiness_accepted": True,
        "b34_package_ready_for_repository_acceptance": True,
        "provider_calls": 0, "broker_reads": 0, "broker_writes": 0,
        "protected_interval": {"overlapping_canonical_partitions_opened": 0},
        "opening_premarket_pack": {"fingerprint": B34_INTRADAY_PACK_FINGERPRINT},
        "evidence_sha256": "a" * 64, "sample_classes": samples,
        "unit_integrity": [{
            "unit_id": "pin", "accepted": True,
            "canonical_path": str(canonical), "checkpoint_path": str(checkpoint)
        }],
    }
    (validation / "b34_intraday_semantics_audit.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    monkeypatch.setattr(
        runner.V2Layout, "beneath",
        lambda _: SimpleNamespace(validation=validation),
    )
    calls = []

    def fake_sample(path, *, symbol, session_date):
        calls.append((path, symbol, session_date))
        return [b.model_dump(mode="json") for b in sample_rows]

    monkeypatch.setattr(runner, "_sample_rows", fake_sample)
    result = runner.run_review(tmp_path)
    assert len(result["samples"]) == 2
    assert len(calls) == 2
    assert all(s["source_row_count"] == 5 for s in result["samples"])
    assert all(len(s["context_snapshots"]) == 3 for s in result["samples"])
    assert all(s["context_snapshots"][2]["features"][
        "regular_observed_closed_minutes"] == 2 for s in result["samples"])
    assert result["provider_requests"] == 0
    assert result["protected_outcomes_opened"] == 0
    saved = runner._save(result, tmp_path)
    assert runner._save(result, tmp_path) == saved
    assert json.loads(saved.read_text(encoding="utf-8"))["fingerprint"] == (
        runner._fingerprint(result)
    )

    # The retained report is not an instruction to access a protected unit.
    report["sample_classes"][0]["session_date"] = "2026-05-12"
    (validation / "b34_intraday_semantics_audit.json").write_text(
        json.dumps(report), encoding="utf-8"
    )
    with pytest.raises(runner.PremarketSourceReviewError, match="PROTECTED"):
        runner.run_review(tmp_path)
