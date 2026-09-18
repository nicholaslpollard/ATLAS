from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from packages.core.enums import (
    LiveConnectionState,
    LiveFeedMode,
    LiveFreshness,
    SessionSegment,
)
from packages.schemas.live_market import (
    LiveMinuteAggregate,
    LiveSessionStatus,
    LiveStateSnapshot,
    LiveSymbolState,
)
from packages.simulation.current_market_snapshot_source import (
    CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT,
    CurrentMarketSnapshotSourceError,
    capture_current_market_snapshot_source_v1,
    load_current_market_snapshot_source_v1,
)


def _snapshot(*, generated_minute: int = 5) -> LiveStateSnapshot:
    generated = datetime(
        2026, 9, 18, 20, generated_minute, tzinfo=UTC
    )
    minute = LiveMinuteAggregate(
        symbol="AAPL",
        bar_start_utc=datetime(2026, 9, 18, 20, 4, tzinfo=UTC),
        bar_end_utc=datetime(2026, 9, 18, 20, 5, tzinfo=UTC),
        session_date=date(2026, 9, 18),
        session_segment=SessionSegment.AFTER_HOURS,
        open=200.0,
        high=201.0,
        low=199.5,
        close=200.5,
        volume=10_000.0,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        received_at_utc=generated,
    )
    return LiveStateSnapshot(
        generated_at_utc=generated,
        feed_mode=LiveFeedMode.DELAYED,
        expected_delay_seconds=900,
        connection_state=LiveConnectionState.SUBSCRIBED,
        subscriptions=("AM.*",),
        session=LiveSessionStatus(
            as_of_utc=generated,
            local_date=date(2026, 9, 18),
            is_exchange_session=True,
            session_segment=SessionSegment.AFTER_HOURS,
            regular_open_utc=datetime(
                2026, 9, 18, 13, 30, tzinfo=UTC
            ),
            regular_close_utc=datetime(
                2026, 9, 18, 20, 0, tzinfo=UTC
            ),
        ),
        received_events=1,
        accepted_events=1,
        observed_symbol_count=1,
        last_received_at_utc=generated,
        symbols=(
            LiveSymbolState(
                symbol="AAPL",
                as_of_utc=generated,
                minute=minute,
                minute_freshness=LiveFreshness.FRESH,
                quote=None,
                quote_freshness=LiveFreshness.UNKNOWN,
            ),
        ),
    )


def _write_current(path: Path, snapshot: LiveStateSnapshot, *, indent: int = 2) -> bytes:
    raw = (
        json.dumps(
            snapshot.model_dump(mode="json"),
            indent=indent,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return raw


def test_current_market_snapshot_source_contract_fingerprint_is_frozen() -> None:
    assert (
        CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT
        == "5a5f6bc707868056e47b758667c8a127c9a16af8676f3eaa323b6066a9d26eba"
    )


def test_capture_archives_exact_validated_bytes_and_replays_by_sha(tmp_path) -> None:
    current = tmp_path / "live" / "market_state" / "current.json"
    checkpoint = (
        tmp_path
        / "live"
        / "simulation"
        / "recurrent_lifecycle"
        / "current.json"
    )
    raw = _write_current(current, _snapshot())

    source = capture_current_market_snapshot_source_v1(
        current_snapshot_path=current,
        recurrent_checkpoint_path=checkpoint,
    )

    assert source.archive_path.read_bytes() == raw
    assert source.archive_path.name == f"{source.raw_sha256}.json"
    assert source.evidence_source_id == (
        f"live-market-state:{source.raw_sha256}"
    )
    assert source.evidence_source_fingerprint == source.raw_sha256
    assert source.feed_mode == "delayed"
    assert source.connection_state == "subscribed"
    assert source.session_segment == "after_hours"
    assert source.symbol_count == 1
    assert source.snapshot.symbols[0].minute_freshness == LiveFreshness.FRESH
    assert source.snapshot.symbols[0].quote is None

    restored = load_current_market_snapshot_source_v1(
        recurrent_checkpoint_path=checkpoint,
        raw_sha256=source.raw_sha256,
    )
    assert restored == source


def test_exact_archive_reuse_is_idempotent(tmp_path) -> None:
    current = tmp_path / "current.json"
    checkpoint = tmp_path / "runtime" / "current.json"
    _write_current(current, _snapshot())

    first = capture_current_market_snapshot_source_v1(
        current_snapshot_path=current,
        recurrent_checkpoint_path=checkpoint,
    )
    second = capture_current_market_snapshot_source_v1(
        current_snapshot_path=current,
        recurrent_checkpoint_path=checkpoint,
    )

    assert second == first
    assert tuple(first.archive_path.parent.glob("*.json")) == (
        first.archive_path,
    )


def test_format_change_changes_raw_sha_but_not_semantic_fingerprint(tmp_path) -> None:
    current = tmp_path / "current.json"
    checkpoint = tmp_path / "runtime" / "current.json"
    snapshot = _snapshot()

    _write_current(current, snapshot, indent=2)
    first = capture_current_market_snapshot_source_v1(
        current_snapshot_path=current,
        recurrent_checkpoint_path=checkpoint,
    )

    _write_current(current, snapshot, indent=4)
    second = capture_current_market_snapshot_source_v1(
        current_snapshot_path=current,
        recurrent_checkpoint_path=checkpoint,
    )

    assert second.raw_sha256 != first.raw_sha256
    assert second.semantic_fingerprint == first.semantic_fingerprint
    assert second.snapshot == first.snapshot
    assert second.archive_path != first.archive_path


def test_archive_tamper_fails_closed(tmp_path) -> None:
    current = tmp_path / "current.json"
    checkpoint = tmp_path / "runtime" / "current.json"
    _write_current(current, _snapshot())

    source = capture_current_market_snapshot_source_v1(
        current_snapshot_path=current,
        recurrent_checkpoint_path=checkpoint,
    )
    source.archive_path.write_text('{"tampered": true}\n', encoding="utf-8")

    with pytest.raises(
        CurrentMarketSnapshotSourceError,
        match="changed or collided",
    ):
        capture_current_market_snapshot_source_v1(
            current_snapshot_path=current,
            recurrent_checkpoint_path=checkpoint,
        )
    with pytest.raises(
        CurrentMarketSnapshotSourceError,
        match="raw SHA-256 mismatch",
    ):
        load_current_market_snapshot_source_v1(
            recurrent_checkpoint_path=checkpoint,
            raw_sha256=source.raw_sha256,
        )


def test_invalid_or_missing_current_snapshot_fails_closed(tmp_path) -> None:
    current = tmp_path / "current.json"
    checkpoint = tmp_path / "runtime" / "current.json"

    with pytest.raises(
        CurrentMarketSnapshotSourceError,
        match="could not stat",
    ):
        capture_current_market_snapshot_source_v1(
            current_snapshot_path=current,
            recurrent_checkpoint_path=checkpoint,
        )

    current.write_text('{"not": "a live snapshot"}\n', encoding="utf-8")
    with pytest.raises(
        CurrentMarketSnapshotSourceError,
        match="LiveStateSnapshot validation",
    ):
        capture_current_market_snapshot_source_v1(
            current_snapshot_path=current,
            recurrent_checkpoint_path=checkpoint,
        )
