from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Barrier, Lock
from zoneinfo import ZoneInfo

import pytest

from packages.backtesting.b35_development_source import (
    B35DevelopmentSourceError,
    _validate_native_plan_record,
    validate_source_plan,
)
from packages.backtesting.b35_replay_guard import (
    ensure_read_start_marker,
    replay_execution_lock,
)
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.data.alpaca_v2_acquisition import build_native_plan
from packages.schemas.market import CanonicalBar
from packages.strategies.intraday_opening_pack import IntradaySetupResult
from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome

ET = ZoneInfo("America/New_York")
DAY = date(2026, 4, 30)


def _bar(minute: int, *, open_: float, high: float, low: float, close: float) -> CanonicalBar:
    stamp = datetime(2026, 4, 30, 9, minute, tzinfo=ET).astimezone(UTC)
    return CanonicalBar(
        symbol="TEST", timestamp_utc=stamp, session_date=DAY, timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR, open=open_, high=high, low=low, close=close,
        volume=100.0, vwap=close, transaction_count=2, provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES, source_id="alpaca:sip:1Min:raw:asof=-:v2:unit=test",
        is_adjusted=False, provider_timestamp_utc=stamp,
    )


def _gap() -> IntradaySetupResult:
    return IntradaySetupResult(
        contract="b34", strategy_id="b34_gap_continuation_v1", session_date=DAY.isoformat(),
        ready=True, fired=True, direction="LONG", reason_codes=("GAP_THRESHOLD_MET",),
        evidence={"prior_regular_close": 100.0},
    )


def test_entry_delay_is_measured_from_information_safe_decision() -> None:
    bars = (
        _bar(30, open_=103, high=104, low=102, close=103),
        # decision becomes safe at 09:31; first observed entry at 09:36 is exactly +5 minutes
        _bar(36, open_=104, high=105, low=103, close=104),
        _bar(37, open_=104, high=112, low=104, close=112),
    )
    outcome = simulate_intraday_outcome(_gap(), bars, symbol="TEST", session_date=DAY)
    assert outcome.entry_bar_timestamp_utc == bars[1].timestamp_utc.isoformat()
    assert outcome.status == "EXITED"


def test_exact_target_open_exits_before_later_same_bar_stop() -> None:
    bars = (
        _bar(30, open_=103, high=104, low=102, close=103),
        _bar(31, open_=104, high=105, low=103, close=104),
        # target is 112. Opening exactly there resolves target before the later low.
        _bar(32, open_=112, high=113, low=99, close=100),
    )
    outcome = simulate_intraday_outcome(_gap(), bars, symbol="TEST", session_date=DAY)
    assert outcome.exit_price == 112
    assert outcome.exit_reason == "TARGET_GAP_NO_BETTER_THAN_TARGET"
    assert outcome.same_bar_collision_adverse_first is False


def test_writer_generated_plan_record_schema_is_accepted_and_string_int_rejected() -> None:
    unit = next(
        item
        for item in build_native_plan(
            symbols=["TEST"], start=date(2026, 4, 1), cutoff=date(2026, 4, 30),
            universe_sha256="a" * 64, policy_sha256="b" * 64, batch_size=1,
        )
        if item.canonical_timeframe == "1m"
    )
    record = json.loads(json.dumps(asdict(unit)))
    _validate_native_plan_record(record, 1)
    bad = dict(record)
    bad["year"] = "2026"
    with pytest.raises(B35DevelopmentSourceError, match="integer schema"):
        _validate_native_plan_record(bad, 1)


def test_stale_in_memory_source_plan_fingerprint_is_rejected() -> None:
    from packages.backtesting.b35_development_source import B35DevelopmentSourcePlan
    plan = B35DevelopmentSourcePlan(
        contract="atlas-b35-development-minute-source-v2-native-plan-exact-path-physical",
        b35_preoutcome_fingerprint=__import__(
            "packages.strategies.b35_conditional_evidence_contract", fromlist=["B35_PREOUTCOME_FINGERPRINT"]
        ).B35_PREOUTCOME_FINGERPRINT,
        start_session=date(2026, 4, 1), end_session=date(2026, 4, 30), units=(),
        native_plan_sha256="a" * 64, native_plan_file_sha256="b" * 64, source_fingerprint="c" * 64,
    )
    # Empty/mutated plans can never retain a trusted old fingerprint.
    with pytest.raises(B35DevelopmentSourceError):
        validate_source_plan(plan)


def test_concurrent_replay_lock_serializes_threads(tmp_path: Path) -> None:
    active = 0
    maximum = 0
    state_lock = Lock()
    barrier = Barrier(2)

    def worker() -> None:
        nonlocal active, maximum
        barrier.wait()
        with replay_execution_lock(tmp_path, source_fingerprint="d" * 64):
            with state_lock:
                active += 1
                maximum = max(maximum, active)
            import time as _time
            _time.sleep(0.05)
            with state_lock:
                active -= 1

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _x: worker(), range(2)))
    assert maximum == 1
    assert not (tmp_path / ".b35_replay.lock").exists()


def test_read_start_marker_is_self_hash_bound_and_idempotent(tmp_path: Path) -> None:
    first = ensure_read_start_marker(
        tmp_path, source_fingerprint="a" * 64, split_evidence_fingerprint="b" * 64, authorization_id="c" * 64
    )
    second = ensure_read_start_marker(
        tmp_path, source_fingerprint="a" * 64, split_evidence_fingerprint="b" * 64, authorization_id="c" * 64
    )
    assert first == second
    assert first["status"] == "DEVELOPMENT_OUTCOME_READ_STARTED"
    assert first["consumed_master_rows_permitted"] == 0
