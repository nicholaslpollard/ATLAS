from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from packages.backtesting import successor_development_outcomes as outcomes
from packages.backtesting.successor_runner_contract import (
    SUCCESSOR_RUNNER_CONTRACT,
    canonical_sha256,
    frozen_authority_contract,
)
from packages.core.enums import DataProvider, DatasetType, SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import (
    SUCCESSOR_INTRADAY_RULE_CONTRACT,
    SuccessorIntradaySignal,
)


def _daily_frame(*, start: date = date(2026, 3, 2), rows: int = 24) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for index in range(rows):
        session = start + timedelta(days=index)
        base = 100.0 + index
        records.append(
            {
                "instrument_id": "inst-1",
                "ticker": "XYZ",
                "session_date": session.isoformat(),
                "signal_available_at_utc": datetime.combine(
                    session, datetime.min.time(), tzinfo=UTC
                )
                + timedelta(hours=21),
                "open": base,
                "high": base + 2.0,
                "low": base - 2.0,
                "close": base + 1.0,
            }
        )
    return pd.DataFrame.from_records(records)


def _signal(*, available: datetime, direction: str = "LONG") -> SuccessorIntradaySignal:
    return SuccessorIntradaySignal(
        contract=SUCCESSOR_INTRADAY_RULE_CONTRACT,
        policy_id="pract_vwap_reclaim_reject_v1",
        session_date=available.date().isoformat(),
        ready=True,
        fired=True,
        direction=direction,
        signal_available_at_utc=available.isoformat(),
        reason_codes=("TEST_SIGNAL",),
        evidence={},
    )


def _bar(
    stamp: datetime,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float | None = None,
) -> CanonicalBar:
    return CanonicalBar(
        symbol="XYZ",
        timestamp_utc=stamp,
        session_date=stamp.astimezone(outcomes.MARKET_TZ).date(),
        timeframe=Timeframe.MINUTE_1,
        session_segment=SessionSegment.REGULAR,
        open=open_price,
        high=high,
        low=low,
        close=open_price if close is None else close,
        volume=1_000.0,
        vwap=open_price,
        transaction_count=10,
        provider=DataProvider.ALPACA,
        dataset=DatasetType.STOCK_MINUTE_AGGREGATES,
        source_id="synthetic-test",
        is_adjusted=False,
    )


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")


def test_validate_accepted_preflight_binds_exact_self_consistent_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_payload = {
        "contract": SUCCESSOR_RUNNER_CONTRACT,
        "fixture": "accepted-source-boundary",
    }
    runner_fp = canonical_sha256(contract_payload)
    contract = {**contract_payload, "fingerprint": runner_fp}
    run_fp = "1" * 64
    source_manifest = {
        "binding": {"source_binding_group_count": outcomes.ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT},
        "minute": {"unit_count": outcomes.ACCEPTED_SUCCESSOR_MINUTE_SOURCE_UNITS},
        "authority": frozen_authority_contract(),
    }
    summary = {
        "status": "COMPLETE_PREOUTCOME_SOURCE_VERIFICATION",
        "contract": SUCCESSOR_RUNNER_CONTRACT,
        "runner_contract_fingerprint": runner_fp,
        "source_verification": {
            "run_fingerprint": run_fp,
            "group_count": outcomes.ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT,
        },
        "source_manifest_fingerprint": canonical_sha256(source_manifest),
        "historical_outcomes_opened": False,
        "authority": frozen_authority_contract(),
    }
    monkeypatch.setattr(outcomes, "ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT", runner_fp)
    monkeypatch.setattr(outcomes, "ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT", run_fp)
    root = tmp_path.resolve()
    artifact_root = (
        root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_preflight"
        / runner_fp[:16]
    )
    _write_json(artifact_root / "preoutcome_contract.json", contract)
    _write_json(artifact_root / "source_manifest.json", source_manifest)
    _write_json(artifact_root / "summary.json", summary)

    accepted = outcomes.validate_accepted_successor_preflight(
        root, runner_contract_fingerprint=runner_fp
    )

    assert accepted.runner_contract_fingerprint == runner_fp
    assert accepted.source_verification_run_fingerprint == run_fp
    assert accepted.source_group_count == 493
    assert accepted.minute_source_units == 59_768
    assert accepted.summary_path.endswith("summary.json")


def test_validate_accepted_preflight_rejects_corrupt_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contract_payload = {"contract": SUCCESSOR_RUNNER_CONTRACT, "fixture": "boundary"}
    runner_fp = canonical_sha256(contract_payload)
    run_fp = "2" * 64
    monkeypatch.setattr(outcomes, "ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT", runner_fp)
    monkeypatch.setattr(outcomes, "ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT", run_fp)
    root = tmp_path.resolve()
    artifact_root = (
        root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_preflight"
        / runner_fp[:16]
    )
    source_manifest = {
        "binding": {"source_binding_group_count": 493},
        "minute": {"unit_count": 59_768},
        "authority": frozen_authority_contract(),
    }
    _write_json(
        artifact_root / "preoutcome_contract.json",
        {**contract_payload, "fingerprint": runner_fp},
    )
    _write_json(artifact_root / "source_manifest.json", source_manifest)
    _write_json(
        artifact_root / "summary.json",
        {
            "status": "COMPLETE_PREOUTCOME_SOURCE_VERIFICATION",
            "contract": SUCCESSOR_RUNNER_CONTRACT,
            "runner_contract_fingerprint": runner_fp,
            "source_verification": {"run_fingerprint": run_fp, "group_count": 493},
            "source_manifest_fingerprint": "0" * 64,
            "historical_outcomes_opened": False,
            "authority": frozen_authority_contract(),
        },
    )

    with pytest.raises(outcomes.SuccessorDevelopmentOutcomeError, match="manifest fingerprint"):
        outcomes.validate_accepted_successor_preflight(
            root, runner_contract_fingerprint=runner_fp
        )


def test_daily_diagnostic_uses_next_open_and_frozen_1_5_20_closes() -> None:
    frame = _daily_frame()
    result = outcomes.evaluate_daily_diagnostic_outcome(
        policy_id="pract_trend_pullback_ema_v1",
        economic_family_id="trend_pullback",
        instrument=frame,
        signal_position=0,
        direction="LONG",
        universe_eligible=True,
        common_context={"market_regime": "TEST"},
    )

    assert result.status == "COMPLETE"
    assert result.entry_price == pytest.approx(101.0)
    assert result.horizon_exit_prices == {"1": 102.0, "5": 106.0, "20": 121.0}
    assert result.gross_directional_returns["1"] == pytest.approx(102.0 / 101.0 - 1.0)
    assert result.gross_directional_returns["20"] == pytest.approx(121.0 / 101.0 - 1.0)
    expected_100bps = (102.0 * 0.995 - 101.0 * 1.005) / 101.0
    assert result.net_directional_returns_by_cost_bps["100"]["1"] == pytest.approx(
        expected_100bps
    )
    assert result.maximum_favorable_excursion_20 == pytest.approx(122.0 / 101.0 - 1.0)
    assert result.maximum_adverse_excursion_20 == pytest.approx(99.0 / 101.0 - 1.0)
    assert len(result.outcome_fingerprint) == 64


def test_daily_diagnostic_rejects_universe_before_opening_future() -> None:
    frame = _daily_frame(rows=1)
    result = outcomes.evaluate_daily_diagnostic_outcome(
        policy_id="ma_trend_cross_50_200_long_v1",
        economic_family_id="trend_following",
        instrument=frame,
        signal_position=0,
        direction="LONG",
        universe_eligible=False,
        common_context={},
    )
    assert result.status == "UNIVERSE_REJECTED"
    assert result.entry_price is None
    assert result.horizon_exit_prices == {"1": None, "5": None, "20": None}


def test_daily_diagnostic_marks_insufficient_future() -> None:
    frame = _daily_frame(rows=1)
    result = outcomes.evaluate_daily_diagnostic_outcome(
        policy_id="pract_rsi2_mean_reversion_v1",
        economic_family_id="rsi2_mean_reversion",
        instrument=frame,
        signal_position=0,
        direction="SHORT",
        universe_eligible=True,
        common_context={},
    )
    assert result.status == "INSUFFICIENT_FUTURE"
    assert result.entry_price is None


def test_intraday_target_and_cost_grid() -> None:
    session = date(2026, 4, 1)
    available = datetime(2026, 4, 1, 14, 31, tzinfo=UTC)
    signal = _signal(available=available)
    bars = [
        _bar(available, open_price=100.0, high=100.5, low=99.5),
        _bar(available + timedelta(minutes=1), open_price=100.5, high=102.2, low=100.2),
    ]
    result = outcomes.simulate_successor_intraday_outcome(
        signal,
        bars,
        economic_family_id="vwap_reclaim_reject",
        symbol="XYZ",
        session_date=session,
        stop_price=99.0,
    )
    assert result.status == "EXITED"
    assert result.exit_reason == "TARGET_2R"
    assert result.entry_price == pytest.approx(100.0)
    assert result.target_price == pytest.approx(102.0)
    assert result.exit_price == pytest.approx(102.0)
    assert result.risk_multiple == pytest.approx(2.0)
    assert set(result.net_directional_returns_by_cost_bps) == {"0", "10", "25", "50", "100"}


def test_intraday_same_bar_collision_is_adverse_first() -> None:
    available = datetime(2026, 4, 1, 14, 31, tzinfo=UTC)
    result = outcomes.simulate_successor_intraday_outcome(
        _signal(available=available),
        [_bar(available, open_price=100.0, high=102.5, low=98.5)],
        economic_family_id="vwap_reclaim_reject",
        symbol="XYZ",
        session_date=date(2026, 4, 1),
        stop_price=99.0,
    )
    assert result.exit_reason == "STOP_AND_TARGET_SAME_BAR_ADVERSE_FIRST"
    assert result.exit_price == pytest.approx(99.0)
    assert result.same_bar_collision_adverse_first is True
    assert result.risk_multiple == pytest.approx(-1.0)


def test_intraday_later_stop_gap_uses_worse_open() -> None:
    available = datetime(2026, 4, 1, 14, 31, tzinfo=UTC)
    bars = [
        _bar(available, open_price=100.0, high=100.4, low=99.4),
        _bar(available + timedelta(minutes=1), open_price=98.5, high=99.0, low=98.0),
    ]
    result = outcomes.simulate_successor_intraday_outcome(
        _signal(available=available),
        bars,
        economic_family_id="vwap_reclaim_reject",
        symbol="XYZ",
        session_date=date(2026, 4, 1),
        stop_price=99.0,
    )
    assert result.exit_reason == "STOP_GAP_WORSE_OPEN"
    assert result.exit_price == pytest.approx(98.5)
    assert result.risk_multiple == pytest.approx(-1.5)


def test_intraday_entry_delay_over_five_minutes_is_noncomparable() -> None:
    available = datetime(2026, 4, 1, 14, 31, tzinfo=UTC)
    first_bar = _bar(
        available + timedelta(minutes=6), open_price=100.0, high=100.2, low=99.8
    )
    result = outcomes.simulate_successor_intraday_outcome(
        _signal(available=available),
        [first_bar],
        economic_family_id="vwap_reclaim_reject",
        symbol="XYZ",
        session_date=date(2026, 4, 1),
        stop_price=99.0,
    )
    assert result.status == "NONCOMPARABLE_ENTRY_DELAY"
    assert result.entry_price is None


def test_intraday_duplicate_timestamps_fail_closed() -> None:
    available = datetime(2026, 4, 1, 14, 31, tzinfo=UTC)
    duplicate = _bar(available, open_price=100.0, high=100.2, low=99.8)
    with pytest.raises(outcomes.SuccessorDevelopmentOutcomeError, match="duplicate"):
        outcomes.simulate_successor_intraday_outcome(
            _signal(available=available),
            [duplicate, duplicate],
            economic_family_id="vwap_reclaim_reject",
            symbol="XYZ",
            session_date=date(2026, 4, 1),
            stop_price=99.0,
        )
