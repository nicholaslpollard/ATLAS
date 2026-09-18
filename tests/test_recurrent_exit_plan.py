from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from packages.schemas.case_file import (
    EvidenceAvailability,
    GeometryStatus,
    InstrumentKind as CaseInstrumentKind,
    InstrumentSelection,
    NewsContextSummary,
    Phase13CaseFile,
    PortfolioRiskAssessment,
    PortfolioRiskStatus,
    TradeGeometry,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.execution.trade_expression import InstrumentKind
from packages.simulation.open_position_state import SimulatedOpenPositionV1
from packages.simulation.recurrent_exit_plan import (
    RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT,
    RecurrentStockExitPlanError,
    build_recurrent_stock_exit_plan_v1,
    phase13_case_fingerprint,
)


OPENED = datetime(2026, 9, 18, 15, 0, tzinfo=UTC)


def _position(*, entry_price: float = 102.0) -> SimulatedOpenPositionV1:
    return SimulatedOpenPositionV1(
        source_account_state_fingerprint="1" * 64,
        decision_record_fingerprint="2" * 64,
        candidate_fingerprint="3" * 64,
        fill_fingerprint="4" * 64,
        funding_terms_fingerprint="5" * 64,
        reservation_fingerprint="6" * 64,
        option_reservation_terms_fingerprint=None,
        option_economics_result_fingerprint=None,
        instrument_kind=InstrumentKind.STOCK,
        instrument_id="iid-AAPL",
        ticker="AAPL",
        direction=DiscoveryDirection.BULLISH,
        candidate_identifier="STOCK:AAPL",
        option_contract_ticker=None,
        option_contract_type=None,
        opened_utc=OPENED,
        quantity=100.0,
        quantity_unit="SHARES",
        entry_price_per_unit=entry_price,
        contract_multiplier=1.0,
        entry_book_value_dollars=entry_price * 100.0,
        entry_fees_dollars=2.0,
        all_in_cash_cost_basis_dollars=entry_price * 100.0 + 2.0,
        original_reserved_capital_dollars=entry_price * 100.0,
        supplemental_cash_consumed_dollars=2.0,
        unspent_reserve_returned_dollars=0.0,
        stock_gross_entry_exposure_dollars=entry_price * 100.0,
        option_premium_at_risk_dollars=0.0,
        option_signed_delta_equivalent_entry_reference_dollars=0.0,
        option_abs_delta_equivalent_entry_reference_dollars=0.0,
        reason_codes=("TEST_POSITION",),
    )


def _case(
    *,
    risk: float = 0.05,
    reward: float = 0.10,
    as_of: date = date(2026, 9, 18),
) -> Phase13CaseFile:
    reference = 100.0
    geometry = TradeGeometry(
        status=GeometryStatus.AVAILABLE,
        direction=DiscoveryDirection.BULLISH,
        horizon_sessions=3,
        reference_entry=reference,
        stop=reference * (1.0 - risk),
        target=reference * (1.0 + reward),
        risk_fraction=risk,
        reward_fraction=reward,
        reward_to_risk=reward / risk,
        natr_14=0.03,
        empirical_mae_p10=-risk,
        empirical_mfe_p75=reward,
        reference_only_not_fill=True,
        reason_codes=("TEST_PHASE13_GEOMETRY",),
    )
    return Phase13CaseFile(
        instrument_id="iid-AAPL",
        ticker="AAPL",
        as_of_date=as_of,
        direction=DiscoveryDirection.BULLISH,
        phase12_case_sha256="a" * 64,
        phase12_research_complete=True,
        market_state="risk_on",
        ticker_state="trend",
        news_context=NewsContextSummary(
            availability=EvidenceAvailability.UNAVAILABLE,
            cutoff_utc=OPENED,
            lookback_calendar_days=7,
            article_count=0,
            positive_count=0,
            neutral_count=0,
            negative_count=0,
            sentiment_score=None,
            reason_codes=("TEST_NEWS_UNAVAILABLE",),
        ),
        instrument_selection=InstrumentSelection(
            primary_kind=CaseInstrumentKind.EQUITY,
            primary_ticker="AAPL",
            option_chain_availability=EvidenceAvailability.UNAVAILABLE,
            reason_codes=("TEST_EQUITY_PRIMARY",),
        ),
        geometry=geometry,
        portfolio_risk=PortfolioRiskAssessment(
            status=PortfolioRiskStatus.ADMISSIBLE,
            proposed_risk_budget=500.0,
            proposed_quantity=100,
            proposed_notional=10_000.0,
            projected_single_name_fraction=0.10,
            projected_gross_fraction=0.10,
            max_abs_correlation=0.10,
            open_positions_before=0,
            proposed_quantity_is_order=False,
            reason_codes=("TEST_RISK_ADMISSIBLE",),
        ),
        phase14_review_ready=True,
        reason_codes=("TEST_PHASE13_READY",),
    )


def test_exit_plan_contract_fingerprint_is_frozen() -> None:
    assert (
        RECURRENT_STOCK_EXIT_PLAN_CONTRACT_FINGERPRINT
        == "dbd30c744aef9b0eef3ec2c8c209826c711fb6c0f9ba5572af3f48e5ec125a72"
    )


def test_exit_plan_transfers_fractions_to_actual_fill_not_reference_prices() -> None:
    position = _position(entry_price=102.0)
    case = _case(risk=0.05, reward=0.10)
    plan = build_recurrent_stock_exit_plan_v1(
        source_recurrent_state_fingerprint="f" * 64,
        position=position,
        phase13_case=case,
        plan_created_utc=OPENED,
    )
    assert plan.reference_entry_price_per_unit == pytest.approx(100.0)
    assert plan.reference_stop_price_per_unit == pytest.approx(95.0)
    assert plan.reference_target_price_per_unit == pytest.approx(110.0)
    assert plan.actual_entry_price_per_unit == pytest.approx(102.0)
    assert plan.stop_price_per_unit == pytest.approx(96.9)
    assert plan.target_price_per_unit == pytest.approx(112.2)
    assert plan.stop_price_per_unit != pytest.approx(
        plan.reference_stop_price_per_unit
    )
    assert plan.target_price_per_unit != pytest.approx(
        plan.reference_target_price_per_unit
    )
    assert plan.reference_absolute_prices_executable is False
    assert plan.price_exit_trigger_authority is False
    assert plan.time_exit_trigger_enabled is False
    assert plan.close_fill_authority is False
    assert plan.phase13_case_fingerprint == phase13_case_fingerprint(case)


def test_exit_plan_rejects_phase13_case_after_position_open() -> None:
    with pytest.raises(
        RecurrentStockExitPlanError,
        match="cannot postdate position open",
    ):
        build_recurrent_stock_exit_plan_v1(
            source_recurrent_state_fingerprint="f" * 64,
            position=_position(),
            phase13_case=_case(as_of=date(2026, 9, 19)),
            plan_created_utc=OPENED,
        )


def test_exit_plan_rejects_identity_mismatch() -> None:
    case = _case().model_copy(update={"ticker": "MSFT"})
    with pytest.raises(
        RecurrentStockExitPlanError,
        match="identity does not match",
    ):
        build_recurrent_stock_exit_plan_v1(
            source_recurrent_state_fingerprint="f" * 64,
            position=_position(),
            phase13_case=case,
            plan_created_utc=OPENED,
        )
