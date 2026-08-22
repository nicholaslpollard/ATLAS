from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from packages.portfolio.phase13_policy import (
    PHASE13_HORIZON_SESSIONS,
    PHASE13_MAX_ABS_CORRELATION,
    PHASE13_MAX_GROSS_NOTIONAL_FRACTION,
    PHASE13_MAX_OPEN_POSITIONS,
    PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION,
    PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED,
    PHASE13_RISK_PER_TRADE_FRACTION,
    phase13_policy_fingerprint,
    phase13_policy_payload,
)
from packages.portfolio.thesis import build_trade_geometry
from packages.risk.engine import evaluate_portfolio_risk
from packages.schemas.case_file import (
    GeometryStatus,
    PortfolioRiskStatus,
    PortfolioSnapshot,
    TradeGeometry,
)
from packages.schemas.deep_research import (
    AnalogueDistribution,
    AnalogueQuality,
    DeepResearchCase,
    EmpiricalPathScenarios,
    ScenarioQuantiles,
)
from packages.schemas.discovery_score import DiscoveryDirection


def _quantiles(*, p10: float = 0.01, p75: float = 0.05) -> ScenarioQuantiles:
    return ScenarioQuantiles(
        p05=p10,
        p10=p10,
        p25=p10,
        median=(p10 + p75) / 2.0,
        p75=p75,
        p90=p75,
        p95=p75,
        mean=(p10 + p75) / 2.0,
    )


def _research(direction: DiscoveryDirection, *, mae_p10: float = -0.03, mfe_p75: float = 0.06) -> DeepResearchCase:
    return DeepResearchCase(
        instrument_id="figi:test",
        ticker="TEST",
        as_of_date=date(2026, 8, 14),
        direction=direction,
        market_state="BULL",
        ticker_state="UPTREND" if direction == DiscoveryDirection.BULLISH else "DOWNTREND",
        phase11_candidate_sha256="a" * 64,
        research_source_fingerprint="b" * 64,
        similarity_feature_names=("natr_14",),
        current_feature_values={"natr_14": 0.02},
        eligible_pool_rows=1000,
        analogue_distribution=AnalogueDistribution(rows=100, unique_instruments=50),
        analogue_quality=AnalogueQuality(
            status="ADEQUATE",
            analogue_count=100,
            unique_instruments=50,
            first_session_date=date(2020, 1, 2),
            last_session_date=date(2026, 1, 2),
            mean_distance=0.5,
            median_distance=0.4,
            p90_distance=0.8,
            path_rows=100,
            path_coverage=1.0,
            reason_codes=("ADEQUATE",),
        ),
        scenarios=EmpiricalPathScenarios(
            available=True,
            draw_count=10_000,
            seed=1,
            source_path_rows=100,
            session_1=_quantiles(),
            session_2=_quantiles(),
            session_3=_quantiles(),
            max_adverse_excursion=_quantiles(p10=mae_p10, p75=-0.01),
            max_favorable_excursion=_quantiles(p10=0.01, p75=mfe_p75),
            terminal_positive_rate=0.6,
            reason_codes=("AVAILABLE",),
        ),
        analogue_artifact_path="analogues.parquet",
        analogue_artifact_sha256="c" * 64,
        path_artifact_path="paths.parquet",
        path_artifact_sha256="d" * 64,
        research_complete=True,
        reason_codes=("COMPLETE",),
    )


def test_phase13_policy_is_fixed_before_case_results() -> None:
    payload = phase13_policy_payload()
    assert PHASE13_HORIZON_SESSIONS == 3
    assert PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED is False
    assert PHASE13_RISK_PER_TRADE_FRACTION == 0.005
    assert PHASE13_MAX_SINGLE_NAME_NOTIONAL_FRACTION == 0.10
    assert PHASE13_MAX_GROSS_NOTIONAL_FRACTION == 1.0
    assert PHASE13_MAX_OPEN_POSITIONS == 10
    assert PHASE13_MAX_ABS_CORRELATION == 0.80
    assert payload["instrument"]["primary_instrument"] == "EQUITY"
    assert payload["authority"] == {"production_ml_writes": 0, "broker_writes": 0, "order_writes": 0}
    assert len(phase13_policy_fingerprint()) == 64


def test_long_and_short_geometry_use_empirical_bounded_rules() -> None:
    long_plan = build_trade_geometry(
        _research(DiscoveryDirection.BULLISH),
        reference_close=100.0,
        feature_values={"natr_14": 0.02},
    )
    assert long_plan.status == GeometryStatus.AVAILABLE
    assert long_plan.reference_entry == 100.0
    assert long_plan.stop == 97.0
    assert long_plan.target == 106.0
    assert long_plan.stop < long_plan.reference_entry < long_plan.target

    short_plan = build_trade_geometry(
        _research(DiscoveryDirection.BEARISH),
        reference_close=100.0,
        feature_values={"natr_14": 0.02},
    )
    assert short_plan.status == GeometryStatus.AVAILABLE
    assert short_plan.stop == 103.0
    assert short_plan.target == 94.0
    assert short_plan.stop > short_plan.reference_entry > short_plan.target


def test_geometry_fails_closed_when_empirical_reward_does_not_exceed_risk() -> None:
    plan = build_trade_geometry(
        _research(DiscoveryDirection.BULLISH, mae_p10=-0.04, mfe_p75=0.03),
        reference_close=100.0,
        feature_values={"natr_14": 0.02},
    )
    assert plan.status == GeometryStatus.UNAVAILABLE
    assert plan.reference_entry is None
    assert "EMPIRICAL_REWARD_DOES_NOT_EXCEED_RISK" in plan.reason_codes


def test_trade_geometry_schema_rejects_wrong_long_geometry() -> None:
    with pytest.raises(ValueError, match="LONG geometry"):
        TradeGeometry(
            status=GeometryStatus.AVAILABLE,
            direction=DiscoveryDirection.BULLISH,
            horizon_sessions=3,
            reference_entry=100.0,
            stop=101.0,
            target=110.0,
            risk_fraction=0.05,
            reward_fraction=0.10,
            reward_to_risk=2.0,
            natr_14=0.05,
            empirical_mae_p10=-0.04,
            empirical_mfe_p75=0.10,
            reason_codes=("TEST",),
        )


def test_portfolio_risk_is_broker_neutral_and_can_admit_or_reject() -> None:
    geometry = TradeGeometry(
        status=GeometryStatus.AVAILABLE,
        direction=DiscoveryDirection.BULLISH,
        horizon_sessions=3,
        reference_entry=100.0,
        stop=95.0,
        target=110.0,
        risk_fraction=0.05,
        reward_fraction=0.10,
        reward_to_risk=2.0,
        natr_14=0.05,
        empirical_mae_p10=-0.04,
        empirical_mfe_p75=0.10,
        reason_codes=("TEST",),
    )
    snapshot = PortfolioSnapshot(
        as_of_utc=datetime(2026, 8, 14, 21, 0, tzinfo=UTC),
        equity=100_000.0,
        cash=100_000.0,
        gross_market_value=0.0,
        source="synthetic-test",
        source_fingerprint="test",
    )
    accepted = evaluate_portfolio_risk(
        geometry,
        instrument_id="figi:test",
        ticker="TEST",
        snapshot=snapshot,
    )
    assert accepted.status == PortfolioRiskStatus.ADMISSIBLE
    assert accepted.proposed_quantity == 100
    assert accepted.proposed_notional == 10_000.0
    assert accepted.proposed_quantity_is_order is False

    tighter_geometry = geometry.model_copy(
        update={
            "stop": 97.0,
            "risk_fraction": 0.03,
            "reward_fraction": 0.06,
            "reward_to_risk": 2.0,
            "natr_14": 0.03,
            "empirical_mae_p10": -0.03,
            "empirical_mfe_p75": 0.06,
        }
    )
    rejected = evaluate_portfolio_risk(
        tighter_geometry,
        instrument_id="figi:test",
        ticker="TEST",
        snapshot=snapshot,
    )
    assert rejected.status == PortfolioRiskStatus.REJECTED
    assert "SINGLE_NAME_FAIL" in rejected.reason_codes


def test_missing_portfolio_snapshot_is_unavailable_not_guessed() -> None:
    geometry = TradeGeometry(
        status=GeometryStatus.AVAILABLE,
        direction=DiscoveryDirection.BULLISH,
        horizon_sessions=3,
        reference_entry=100.0,
        stop=95.0,
        target=110.0,
        risk_fraction=0.05,
        reward_fraction=0.10,
        reward_to_risk=2.0,
        natr_14=0.05,
        empirical_mae_p10=-0.04,
        empirical_mfe_p75=0.10,
        reason_codes=("TEST",),
    )
    result = evaluate_portfolio_risk(
        geometry,
        instrument_id="figi:test",
        ticker="TEST",
        snapshot=None,
    )
    assert result.status == PortfolioRiskStatus.UNAVAILABLE
    assert result.proposed_quantity is None
