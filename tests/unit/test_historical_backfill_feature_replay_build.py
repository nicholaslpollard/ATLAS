from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from packages.features.historical_backfill_replay import (
    DROP_AT_PROVIDER_SEAM,
    TRANSFER_IDENTITY_STATE,
)
from packages.features.historical_backfill_replay_build import (
    GATE9_DAILY_REPLAY_CONTRACT_VERSION,
    GATE9_DAILY_REPLAY_ROLE,
    apply_lifecycle_events,
    lifecycle_content_fingerprint,
    replay_source_fingerprint,
    year_source_fingerprint,
)
from packages.features.incremental import IncrementalFeatureEngine


def _bar(timestamp: datetime, close: float) -> dict[str, object]:
    return {
        "timestamp_utc": timestamp,
        "high": close + 1.0,
        "low": close - 1.0,
        "close": close,
        "volume": 1000.0,
    }


def _transfer_event() -> dict[str, object]:
    return {
        "event_date": date(2020, 1, 6),
        "event_type": TRANSFER_IDENTITY_STATE,
        "source_symbol": "OLD",
        "target_symbol": "NEW",
        "reason": "SAFE_NAME_CHANGE_CHAIN",
        "identity_chain_id": "chain",
        "segment_id": "segment",
        "handoff_gap_calendar_days": 3,
        "seam_decision": None,
    }


def _drop_event(symbol: str = "NEW") -> dict[str, object]:
    return {
        "event_date": date(2021, 8, 16),
        "event_type": DROP_AT_PROVIDER_SEAM,
        "source_symbol": symbol,
        "target_symbol": None,
        "reason": "RESET_AT_PROVIDER_SEAM",
        "identity_chain_id": None,
        "segment_id": None,
        "handoff_gap_calendar_days": None,
        "seam_decision": "RESET_AT_PROVIDER_SEAM",
    }


def test_gate9_daily_replay_contract_is_isolated_candidate_work() -> None:
    assert GATE9_DAILY_REPLAY_CONTRACT_VERSION.startswith(
        "historical-backfill-feature-replay-v1"
    )
    assert GATE9_DAILY_REPLAY_ROLE == "ISOLATED_DAILY_FEATURE_REPLAY_NOT_PRODUCTION"


def test_apply_lifecycle_transfer_moves_exact_recursive_state() -> None:
    start = datetime(2020, 1, 2, 14, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="OLD", **_bar(start, 100.0))
    engine.update(symbol="OLD", **_bar(start + timedelta(days=1), 110.0))

    counts = apply_lifecycle_events(engine, [_transfer_event()])

    assert counts["events"] == 1
    assert counts["identity_transfers"] == 1
    assert engine.has_state("OLD") is False
    assert engine.has_state("NEW") is True
    result = engine.update(symbol="NEW", **_bar(start + timedelta(days=4), 121.0))
    assert result["return_1"] == pytest.approx(0.1)


def test_apply_lifecycle_drop_resets_next_observation_and_is_idempotent() -> None:
    start = datetime(2021, 8, 13, 13, 30, tzinfo=UTC)
    engine = IncrementalFeatureEngine()
    engine.update(symbol="NEW", **_bar(start, 100.0))

    first = apply_lifecycle_events(engine, [_drop_event()])
    second = apply_lifecycle_events(engine, [_drop_event()])

    assert first["seam_drop_events"] == 1
    assert first["seam_drop_hits"] == 1
    assert first["seam_drop_misses"] == 0
    assert second["seam_drop_events"] == 1
    assert second["seam_drop_hits"] == 0
    assert second["seam_drop_misses"] == 1
    fresh = engine.update(symbol="NEW", **_bar(start + timedelta(days=3), 150.0))
    assert fresh["return_1"] is None
    assert fresh["log_return_1"] is None
    assert fresh["obv"] == 0.0


def test_apply_lifecycle_unknown_event_fails_closed() -> None:
    engine = IncrementalFeatureEngine()
    with pytest.raises(RuntimeError, match="unsupported lifecycle event"):
        apply_lifecycle_events(
            engine,
            [
                {
                    "event_date": date(2020, 1, 1),
                    "event_type": "GUESS_CONTINUITY",
                    "source_symbol": "OLD",
                }
            ],
        )


def test_lifecycle_content_fingerprint_is_order_independent_but_content_sensitive() -> None:
    transfer = _transfer_event()
    drop = _drop_event()
    assert lifecycle_content_fingerprint([transfer, drop]) == lifecycle_content_fingerprint(
        [drop, transfer]
    )
    changed = dict(drop)
    changed["source_symbol"] = "OTHER"
    assert lifecycle_content_fingerprint([transfer, drop]) != lifecycle_content_fingerprint(
        [transfer, changed]
    )


def _replay_fingerprint(**overrides: str) -> str:
    values = {
        "preflight_source_fingerprint": "preflight",
        "canonical_inventory_fingerprint": "canonical",
        "production_feature_baseline_fingerprint": "features",
        "lifecycle_fingerprint": "lifecycle",
    }
    values.update(overrides)
    return replay_source_fingerprint(**values)


def test_replay_source_fingerprint_binds_all_parent_evidence() -> None:
    baseline = _replay_fingerprint()
    assert len(baseline) == 64
    for field in (
        "preflight_source_fingerprint",
        "canonical_inventory_fingerprint",
        "production_feature_baseline_fingerprint",
        "lifecycle_fingerprint",
    ):
        assert _replay_fingerprint(**{field: f"changed-{field}"}) != baseline


def _year_fingerprint(**overrides: object) -> str:
    values: dict[str, object] = {
        "replay_source_fingerprint_value": "replay",
        "year": 2020,
        "input_state_fingerprint": "state",
        "canonical_rows": [
            {
                "session_date": "2020-01-02",
                "relative_path": "stocks/1d/year=2020/date=2020-01-02/part-000.parquet",
                "sha256": "source",
            }
        ],
        "lifecycle_events": [_transfer_event()],
    }
    values.update(overrides)
    return year_source_fingerprint(**values)  # type: ignore[arg-type]


def test_year_source_fingerprint_binds_prior_state_source_and_lifecycle() -> None:
    baseline = _year_fingerprint()
    assert len(baseline) == 64
    assert _year_fingerprint(input_state_fingerprint="other-state") != baseline
    changed_source = [
        {
            "session_date": "2020-01-02",
            "relative_path": "stocks/1d/year=2020/date=2020-01-02/part-000.parquet",
            "sha256": "changed-source",
        }
    ]
    assert _year_fingerprint(canonical_rows=changed_source) != baseline
    assert _year_fingerprint(lifecycle_events=[_drop_event("OLD")]) != baseline


def test_year_source_fingerprint_is_stable_across_input_order() -> None:
    first = {
        "session_date": "2020-01-02",
        "relative_path": "a",
        "sha256": "1",
    }
    second = {
        "session_date": "2020-01-03",
        "relative_path": "b",
        "sha256": "2",
    }
    left = _year_fingerprint(canonical_rows=[first, second])
    right = _year_fingerprint(canonical_rows=[second, first])
    assert left == right
