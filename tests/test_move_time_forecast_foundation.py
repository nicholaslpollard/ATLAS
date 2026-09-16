from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)
from packages.schemas.move_time_forecast_contract import (
    MOVE_TIME_FORECAST_CONTRACT,
    MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)


SOURCE_FP = "1" * 64
CREATED = datetime(2026, 9, 16, 2, 0, tzinfo=UTC)
CUTOFF = CREATED - timedelta(minutes=1)


def _threshold(
    threshold: float,
    favorable: float,
    adverse: float,
    favorable_first: float,
    adverse_first: float,
    median_time: float | None,
    collision: float = 0.0,
) -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=threshold,
        favorable_touch_probability=favorable,
        adverse_touch_probability=adverse,
        favorable_before_adverse_probability=favorable_first,
        adverse_before_favorable_probability=adverse_first,
        same_interval_collision_probability=collision,
        median_favorable_time=median_time,
    )


def _available(**overrides: object) -> UnderlyingMoveTimeForecast:
    payload: dict[str, object] = {
        "availability": ForecastAvailability.AVAILABLE,
        "instrument_id": "iid-xyz",
        "ticker": "XYZ",
        "direction": DiscoveryDirection.BULLISH,
        "forecast_created_utc": CREATED,
        "evidence_cutoff_utc": CUTOFF,
        "horizon_unit": ForecastHorizonUnit.MINUTES,
        "horizon_value": 390,
        "method_id": "fixture-empirical-v1",
        "source_label": "fixture accepted path evidence",
        "source_fingerprint": SOURCE_FP,
        "sample_size": 1_000,
        "reference_price": 100.0,
        "mean_signed_return": 0.008,
        "median_signed_return": 0.005,
        "p10_signed_return": -0.020,
        "p25_signed_return": -0.006,
        "p75_signed_return": 0.018,
        "p90_signed_return": 0.035,
        "probability_positive_return": 0.58,
        "mean_mfe": 0.022,
        "mean_mae": 0.009,
        "thresholds": (
            _threshold(0.03, 0.12, 0.08, 0.10, 0.05, 35.0),
            _threshold(0.01, 0.40, 0.25, 0.35, 0.15, 8.0),
            _threshold(0.02, 0.22, 0.14, 0.19, 0.08, 18.0),
        ),
        "uncertainty_score": 0.35,
        "reason_codes": ("EMPIRICAL_FIXTURE",),
    }
    payload.update(overrides)
    return UnderlyingMoveTimeForecast(**payload)


def test_contract_fingerprint_and_authority_are_frozen() -> None:
    assert contract_fingerprint() == MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT
    assert MOVE_TIME_FORECAST_CONTRACT_FINGERPRINT == (
        "93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1"
    )
    assert MOVE_TIME_FORECAST_CONTRACT["forecast_target"] == (
        "UNDERLYING_PRICE_PATH_BEFORE_INSTRUMENT_SELECTION"
    )
    assert MOVE_TIME_FORECAST_CONTRACT["threshold_probabilities_are_underlying_only"] is True
    assert MOVE_TIME_FORECAST_CONTRACT["historical_option_pnl_claimed"] is False
    assert MOVE_TIME_FORECAST_CONTRACT["instrument_selection_authority"] is False
    assert MOVE_TIME_FORECAST_CONTRACT["broker_reads"] == 0
    assert MOVE_TIME_FORECAST_CONTRACT["broker_writes"] == 0
    assert MOVE_TIME_FORECAST_CONTRACT["paper_authority"] is False
    assert MOVE_TIME_FORECAST_CONTRACT["live_authority"] is False
    assert MOVE_TIME_FORECAST_CONTRACT["promotion_authority"] is False


def test_available_directional_forecast_sorts_thresholds_and_is_deterministic() -> None:
    forecast = _available()
    assert [item.threshold_fraction for item in forecast.thresholds] == [0.01, 0.02, 0.03]
    first = forecast_fingerprint(forecast)
    second = forecast_fingerprint(_available())
    assert first == second
    assert len(first) == 64
    assert forecast.underlying_only is True
    assert forecast.historical_option_pnl_claimed is False
    assert forecast.instrument_selection_authority is False


def test_unavailable_forecast_can_carry_identity_and_reasons_but_no_distribution() -> None:
    forecast = UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.UNAVAILABLE,
        instrument_id="iid-missing",
        ticker="MISS",
        direction=DiscoveryDirection.NEUTRAL,
        forecast_created_utc=CREATED,
        evidence_cutoff_utc=CUTOFF,
        horizon_unit=ForecastHorizonUnit.SESSIONS,
        horizon_value=5,
        method_id="no-supported-evidence",
        source_label="fixture unavailable",
        source_fingerprint=SOURCE_FP,
        reason_codes=("INSUFFICIENT_SUPPORTED_EVIDENCE",),
    )
    assert forecast.sample_size is None
    assert forecast.reference_price is None
    assert forecast.thresholds == ()


def test_unavailable_forecast_rejects_partial_distribution() -> None:
    with pytest.raises(ValidationError, match="unavailable forecast cannot carry a partial distribution"):
        UnderlyingMoveTimeForecast(
            availability=ForecastAvailability.UNAVAILABLE,
            instrument_id="iid-missing",
            ticker="MISS",
            direction=DiscoveryDirection.NEUTRAL,
            forecast_created_utc=CREATED,
            evidence_cutoff_utc=CUTOFF,
            horizon_unit=ForecastHorizonUnit.SESSIONS,
            horizon_value=5,
            method_id="no-supported-evidence",
            source_label="fixture unavailable",
            source_fingerprint=SOURCE_FP,
            reference_price=100.0,
            reason_codes=("INSUFFICIENT_SUPPORTED_EVIDENCE",),
        )


def test_available_forecast_rejects_missing_distribution_field() -> None:
    with pytest.raises(ValidationError, match="complete signed-return distribution"):
        _available(mean_mfe=None)


def test_signed_return_quantiles_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="quantiles must be monotonically ordered"):
        _available(p25_signed_return=0.02, median_signed_return=0.005)


def test_directional_available_forecast_requires_thresholds() -> None:
    with pytest.raises(ValidationError, match="directional available forecast requires path thresholds"):
        _available(thresholds=())


def test_neutral_forecast_cannot_define_favorable_path_thresholds() -> None:
    with pytest.raises(ValidationError, match="neutral forecast cannot define favorable/adverse thresholds"):
        _available(direction=DiscoveryDirection.NEUTRAL)


def test_neutral_available_forecast_can_carry_return_distribution_without_directional_thresholds() -> None:
    forecast = _available(direction=DiscoveryDirection.NEUTRAL, thresholds=())
    assert forecast.direction == DiscoveryDirection.NEUTRAL
    assert forecast.thresholds == ()


def test_threshold_probabilities_cannot_increase_with_larger_move() -> None:
    with pytest.raises(ValidationError, match="favorable-touch probability cannot rise"):
        _available(
            thresholds=(
                _threshold(0.01, 0.30, 0.25, 0.25, 0.15, 8.0),
                _threshold(0.02, 0.31, 0.10, 0.26, 0.06, 18.0),
            )
        )
    with pytest.raises(ValidationError, match="adverse-touch probability cannot rise"):
        _available(
            thresholds=(
                _threshold(0.01, 0.30, 0.20, 0.25, 0.12, 8.0),
                _threshold(0.02, 0.20, 0.21, 0.17, 0.13, 18.0),
            )
        )


def test_threshold_path_order_probabilities_must_be_coherent() -> None:
    with pytest.raises(ValidationError, match="favorable-first probability cannot exceed"):
        _threshold(0.01, 0.20, 0.20, 0.21, 0.10, 5.0)
    with pytest.raises(ValidationError, match="same-interval collision cannot exceed"):
        _threshold(0.01, 0.20, 0.10, 0.10, 0.05, 5.0, collision=0.11)


def test_favorable_timing_must_match_touch_probability_and_horizon() -> None:
    with pytest.raises(ValidationError, match="requires median favorable time"):
        _threshold(0.01, 0.20, 0.10, 0.15, 0.05, None)
    with pytest.raises(ValidationError, match="cannot carry favorable timing"):
        _threshold(0.01, 0.0, 0.10, 0.0, 0.05, 1.0)
    with pytest.raises(ValidationError, match="cannot exceed forecast horizon"):
        _available(
            horizon_value=30,
            thresholds=(_threshold(0.01, 0.20, 0.10, 0.15, 0.05, 31.0),),
        )


def test_forecast_rejects_future_evidence_and_naive_timestamps() -> None:
    with pytest.raises(ValidationError, match="cannot use evidence after"):
        _available(evidence_cutoff_utc=CREATED + timedelta(seconds=1))
    with pytest.raises(ValidationError, match="timezone-aware"):
        _available(forecast_created_utc=datetime(2026, 9, 16, 2, 0))


def test_forecast_rejects_nonfinite_values_and_non_hash_source_identity() -> None:
    with pytest.raises(ValidationError):
        _available(mean_signed_return=float("nan"))
    with pytest.raises(ValidationError):
        _available(source_fingerprint="not-a-sha")


def test_forecast_cannot_claim_option_pnl_or_any_trading_authority() -> None:
    forbidden = (
        "historical_option_pnl_claimed",
        "instrument_selection_authority",
        "broker_read_authority",
        "broker_write_authority",
        "paper_authority",
        "live_authority",
        "promotion_authority",
    )
    for field in forbidden:
        with pytest.raises(ValidationError, match="cannot grant trading or promotion authority"):
            _available(**{field: True})


def test_contract_identity_cannot_be_overridden() -> None:
    with pytest.raises(ValidationError, match="contract version mismatch"):
        _available(contract_version="wrong")
    with pytest.raises(ValidationError, match="contract fingerprint mismatch"):
        _available(contract_fingerprint="0" * 64)
