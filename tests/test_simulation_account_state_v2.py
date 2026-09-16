from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from packages.execution.option_economics import (
    OptionEconomicsInputs,
    build_option_economic_candidate,
)
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import ActionabilityPolicy, TradeExpressionMode
from packages.schemas.case_file import OptionCandidateEvidence
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
    forecast_fingerprint,
)
from packages.simulation.account_state_v2 import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION,
    SimulationAccountStateV2Error,
    SimulationAccountV2EventKind,
    apply_competing_decisions_v2,
    apply_simulation_decision_v2,
    initialize_simulation_account_v2,
    release_option_reservation_v2,
    release_stock_reservation_v2,
    replay_account_v2_ledger,
)
from packages.simulation.account_state_v2_contract import (
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT,
    SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)
from packages.simulation.decision_record import build_simulation_decision_record
from packages.simulation.option_reservation import (
    LongOptionReservationInputs,
    build_long_option_reservation_terms,
)


CREATED = datetime(2026, 9, 16, 5, 0, tzinfo=UTC)
DECIDED = CREATED + timedelta(minutes=1)
CUTOFF = CREATED - timedelta(minutes=1)
SOURCE_FP = "a" * 64
SCENARIO_FP = "b" * 64
EVENT_FP = "c" * 64


def _threshold() -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=0.01,
        favorable_touch_probability=0.45,
        adverse_touch_probability=0.25,
        favorable_before_adverse_probability=0.34,
        adverse_before_favorable_probability=0.13,
        same_interval_collision_probability=0.04,
        median_favorable_time=10.0,
    )


def _forecast(
    *,
    ticker: str = "XYZ",
    instrument_id: str = "iid-xyz",
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    created_utc: datetime = CREATED,
) -> UnderlyingMoveTimeForecast:
    bearish = direction == DiscoveryDirection.BEARISH
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=instrument_id,
        ticker=ticker,
        direction=direction,
        forecast_created_utc=created_utc,
        evidence_cutoff_utc=created_utc - timedelta(minutes=1),
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
        method_id="account-v2-fixture",
        source_label="account v2 fixture",
        source_fingerprint=SOURCE_FP,
        sample_size=1_000,
        reference_price=100.0,
        mean_signed_return=-0.012 if bearish else 0.008,
        median_signed_return=-0.008 if bearish else 0.005,
        p10_signed_return=-0.045 if bearish else -0.020,
        p25_signed_return=-0.022 if bearish else -0.006,
        p75_signed_return=0.006 if bearish else 0.018,
        p90_signed_return=0.018 if bearish else 0.035,
        probability_positive_return=0.34 if bearish else 0.58,
        mean_mfe=0.030 if bearish else 0.022,
        mean_mae=0.012 if bearish else 0.009,
        thresholds=(_threshold(),),
        uncertainty_score=0.30,
        reason_codes=("FIXTURE",),
    )


def _option(
    *,
    contract_type: str = "call",
    delta: float = 0.55,
    contract_ticker: str | None = None,
) -> OptionCandidateEvidence:
    return OptionCandidateEvidence(
        contract_ticker=contract_ticker
        or (
            "O:XYZ261016C00100000"
            if contract_type == "call"
            else "O:XYZ261016P00100000"
        ),
        contract_type=contract_type,
        expiration_date=date(2026, 10, 16),
        dte=30,
        strike=100.0,
        bid=4.8,
        ask=5.2,
        mid=5.0,
        spread_to_mid=0.08,
        open_interest=1_000,
        volume=200,
        delta=delta,
        implied_volatility=0.30,
        eligible=True,
        reason_codes=("FIXTURE_OPTION",),
    )


def _option_inputs(forecast: UnderlyingMoveTimeForecast) -> OptionEconomicsInputs:
    return OptionEconomicsInputs(
        contracts=2,
        contract_multiplier=100.0,
        capital_required_dollars=1_050.0,
        holding_period_calendar_days=5.0,
        expected_terminal_premium_per_share=6.2,
        favorable_terminal_premium_per_share=8.0,
        adverse_terminal_premium_per_share=2.5,
        model_probability_profit=0.58,
        scenario_model_id="fixture-option-scenario-v1",
        scenario_model_fingerprint=SCENARIO_FP,
        scenario_forecast_fingerprint=forecast_fingerprint(forecast),
        gamma=0.04,
        theta_per_calendar_day=-0.08,
        vega_per_one_iv_fraction=12.0,
        iv_percentile=0.60,
        skew_signal=-0.10,
        term_structure_signal=0.05,
        risk_free_rate=0.04,
        dividend_yield=0.01,
        event_within_horizon=False,
        event_risk_acceptable=True,
        event_context_fingerprint=EVENT_FP,
        liquidity_score=0.90,
        exit_slippage_dollars=8.0,
        round_trip_commission_dollars=2.0,
        round_trip_fees_dollars=1.0,
        executable=True,
        risk_budget_ok=True,
        model_reference_premium_per_share=5.5,
    )


def _stock_inputs(*, capital: float = 5_000.0, notional: float = 10_000.0) -> StockEconomicsInputs:
    return StockEconomicsInputs(
        position_notional_dollars=notional,
        capital_required_dollars=capital,
        entry_slippage_bps=5.0,
        exit_slippage_bps=5.0,
        round_trip_commission_dollars=1.0,
        round_trip_fees_dollars=1.0,
        horizon_borrow_cost_dollars=0.0,
        horizon_financing_cost_dollars=2.0,
        net_probability_profit=0.50,
        liquidity_score=0.90,
        executable=True,
        risk_budget_ok=True,
        shortable_if_bearish=True,
    )


def _policy() -> ActionabilityPolicy:
    return ActionabilityPolicy(
        min_expected_net_value=0.0,
        min_expected_return_on_capital=0.0,
        min_probability_profit=0.0,
        max_expected_loss_to_gain_ratio=10.0,
        max_execution_cost_to_expected_gain_ratio=10.0,
        min_liquidity_score=0.0,
        material_superiority_ratio=1.0,
    )


def _option_case(
    *,
    direction: DiscoveryDirection = DiscoveryDirection.BULLISH,
    created_utc: datetime = CREATED,
    fee_reserve: float = 3.0,
):
    forecast = _forecast(direction=direction, created_utc=created_utc)
    option = _option(
        contract_type="put" if direction == DiscoveryDirection.BEARISH else "call",
        delta=-0.45 if direction == DiscoveryDirection.BEARISH else 0.55,
    )
    economics = build_option_economic_candidate(
        forecast=forecast,
        option=option,
        inputs=_option_inputs(forecast),
    )
    assert economics.candidate is not None
    record = build_simulation_decision_record(
        decision_created_utc=created_utc + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(economics.candidate,),
    )
    terms = build_long_option_reservation_terms(
        record=record,
        option_economics=economics,
        option=option,
        inputs=LongOptionReservationInputs(cash_fee_reserve_dollars=fee_reserve),
    )
    return record, terms


def _stock_record(*, created_utc: datetime = CREATED + timedelta(minutes=2)):
    forecast = _forecast(
        ticker="ABC",
        instrument_id="iid-abc",
        created_utc=created_utc,
    )
    return build_simulation_decision_record(
        decision_created_utc=created_utc + timedelta(minutes=1),
        forecast=forecast,
        stock_inputs=_stock_inputs(),
        actionability_policy=_policy(),
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )


def test_v2_contract_identity_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT_FINGERPRINT == (
        "1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5"
    )
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT_VERSION == (
        "atlas-simulation-account-state-v2-stock-option-reservations"
    )
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["margin_inference"] is False
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["collateral_inference"] is False
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["leverage_inference"] is False
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["stock_accounting_arithmetic_reuses_v1"] is True
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["stock_candidate_fingerprint_lineage_required"] is True
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["paper_authority"] is False
    assert SIMULATION_ACCOUNT_STATE_V2_CONTRACT["live_authority"] is False


def test_initial_state_is_deterministic_and_separates_stock_from_option_totals() -> None:
    first = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    second = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    assert first == second
    assert first.state.state_fingerprint == second.state.state_fingerprint
    assert first.state.cash == pytest.approx(20_000.0)
    assert first.state.stock_reserved_capital == 0.0
    assert first.state.option_reserved_capital == 0.0
    assert first.state.stock_gross_notional == 0.0
    assert first.state.option_abs_delta_equivalent_notional == 0.0


def test_long_option_reservation_debits_exact_cash_and_keeps_stock_notional_zero() -> None:
    record, terms = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)

    transition = apply_simulation_decision_v2(account, record, option_terms=terms)
    state = transition.account.state

    assert transition.event is not None
    assert transition.event.kind == SimulationAccountV2EventKind.RESERVE_OPTION
    assert state.cash == pytest.approx(20_000.0 - 1_043.0)
    assert state.option_reserved_capital == pytest.approx(1_043.0)
    assert state.option_max_loss_cash == pytest.approx(1_043.0)
    assert state.option_premium_at_risk == pytest.approx(1_040.0)
    assert state.option_signed_delta_equivalent_notional == pytest.approx(11_000.0)
    assert state.option_abs_delta_equivalent_notional == pytest.approx(11_000.0)
    assert state.stock_reserved_capital == 0.0
    assert state.stock_gross_notional == 0.0
    assert state.cash + state.stock_reserved_capital + state.option_reserved_capital == pytest.approx(state.equity)


def test_bearish_put_preserves_negative_signed_option_exposure() -> None:
    record, terms = _option_case(direction=DiscoveryDirection.BEARISH)
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    state = apply_simulation_decision_v2(account, record, option_terms=terms).account.state
    assert state.option_signed_delta_equivalent_notional == pytest.approx(-9_000.0)
    assert state.option_abs_delta_equivalent_notional == pytest.approx(9_000.0)
    assert state.stock_gross_notional == 0.0


def test_stock_and_option_reservations_share_cash_but_not_exposure_fields() -> None:
    option_record, terms = _option_case()
    stock_record = _stock_record()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)

    after_option = apply_simulation_decision_v2(account, option_record, option_terms=terms).account
    after_stock = apply_simulation_decision_v2(after_option, stock_record).account

    assert after_stock.state.option_reserved_capital == pytest.approx(1_043.0)
    assert after_stock.state.stock_reserved_capital == pytest.approx(5_000.0)
    assert after_stock.state.cash == pytest.approx(13_957.0)
    assert after_stock.state.stock_gross_notional == pytest.approx(10_000.0)
    assert after_stock.state.option_abs_delta_equivalent_notional == pytest.approx(11_000.0)
    assert after_stock.state.total_reserved_capital == pytest.approx(6_043.0)


def test_missing_option_terms_are_ledgered_as_fail_closed_rejection() -> None:
    record, _ = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    transition = apply_simulation_decision_v2(account, record)
    assert transition.event is not None
    assert transition.event.kind == SimulationAccountV2EventKind.REJECT_MISSING_OPTION_TERMS
    assert transition.account.state.cash == pytest.approx(20_000.0)
    assert transition.account.state.option_reserved_capital == 0.0
    assert transition.account.state.as_of_utc == record.decision_created_utc


def test_insufficient_cash_rejects_option_without_mutating_amounts() -> None:
    record, terms = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=1_000.0)
    transition = apply_simulation_decision_v2(account, record, option_terms=terms)
    assert transition.event is not None
    assert transition.event.kind == SimulationAccountV2EventKind.REJECT_INSUFFICIENT_CAPITAL
    assert transition.account.state.cash == pytest.approx(1_000.0)
    assert transition.account.state.option_reserved_capital == 0.0
    assert transition.account.state.option_abs_delta_equivalent_notional == 0.0


def test_option_terms_must_match_exact_decision_lineage() -> None:
    record_a, _ = _option_case()
    record_b, terms_b = _option_case(created_utc=CREATED + timedelta(minutes=10))
    assert record_a.record_fingerprint != record_b.record_fingerprint
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    with pytest.raises(SimulationAccountStateV2Error, match="decision lineage"):
        apply_simulation_decision_v2(account, record_a, option_terms=terms_b)


def test_option_release_restores_exact_cash_without_creating_pnl() -> None:
    record, terms = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    reserved = apply_simulation_decision_v2(account, record, option_terms=terms).account
    released = release_option_reservation_v2(
        reserved,
        decision_record_fingerprint=record.record_fingerprint,
        released_utc=record.decision_created_utc + timedelta(minutes=5),
    )
    state = released.account.state
    assert released.event is not None
    assert released.event.kind == SimulationAccountV2EventKind.RELEASE_OPTION
    assert state.cash == pytest.approx(20_000.0)
    assert state.equity == pytest.approx(20_000.0)
    assert state.option_reserved_capital == 0.0
    assert state.option_max_loss_cash == 0.0
    assert state.option_premium_at_risk == 0.0
    assert state.option_abs_delta_equivalent_notional == 0.0
    assert state.option_reservations == ()


def test_duplicate_option_decision_and_release_are_idempotent() -> None:
    record, terms = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    first = apply_simulation_decision_v2(account, record, option_terms=terms)
    duplicate = apply_simulation_decision_v2(first.account, record, option_terms=terms)
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account == first.account

    release_time = record.decision_created_utc + timedelta(minutes=5)
    released = release_option_reservation_v2(
        first.account,
        decision_record_fingerprint=record.record_fingerprint,
        released_utc=release_time,
    )
    duplicate_release = release_option_reservation_v2(
        released.account,
        decision_record_fingerprint=record.record_fingerprint,
        released_utc=release_time + timedelta(minutes=1),
    )
    assert duplicate_release.idempotent_reuse is True
    assert duplicate_release.event is None
    assert duplicate_release.account == released.account


def test_stock_release_does_not_mutate_option_reservation() -> None:
    option_record, terms = _option_case()
    stock_record = _stock_record()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    account = apply_simulation_decision_v2(account, option_record, option_terms=terms).account
    account = apply_simulation_decision_v2(account, stock_record).account
    released = release_stock_reservation_v2(
        account,
        decision_record_fingerprint=stock_record.record_fingerprint,
        released_utc=stock_record.decision_created_utc + timedelta(minutes=5),
    ).account
    assert released.state.stock_reserved_capital == 0.0
    assert released.state.stock_gross_notional == 0.0
    assert released.state.option_reserved_capital == pytest.approx(1_043.0)
    assert released.state.option_abs_delta_equivalent_notional == pytest.approx(11_000.0)


def test_ledger_replay_reconstructs_exact_mixed_state() -> None:
    option_record, terms = _option_case()
    stock_record = _stock_record()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    account = apply_simulation_decision_v2(account, option_record, option_terms=terms).account
    account = apply_simulation_decision_v2(account, stock_record).account
    account = release_option_reservation_v2(
        account,
        decision_record_fingerprint=option_record.record_fingerprint,
        released_utc=stock_record.decision_created_utc + timedelta(minutes=5),
    ).account

    replayed = replay_account_v2_ledger(account.ledger)
    assert replayed == account
    assert replayed.state.state_fingerprint == account.state.state_fingerprint
    assert replayed.ledger.ledger_fingerprint == account.ledger.ledger_fingerprint


def test_tampered_ledger_lineage_fails_closed() -> None:
    record, terms = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    account = apply_simulation_decision_v2(account, record, option_terms=terms).account
    event = account.ledger.events[0]
    tampered_event = replace(event, before_state_fingerprint="d" * 64)
    tampered_ledger = replace(account.ledger, events=(tampered_event,))
    with pytest.raises(SimulationAccountStateV2Error, match="before-state fingerprint"):
        replay_account_v2_ledger(tampered_ledger)


def test_competition_order_is_deterministic_independent_of_input_order() -> None:
    option_record, terms = _option_case()
    stock_record = _stock_record()
    mapping = {option_record.record_fingerprint: terms}
    first_account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    second_account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    first = apply_competing_decisions_v2(
        first_account,
        (stock_record, option_record),
        option_terms_by_decision_fingerprint=mapping,
    )
    second = apply_competing_decisions_v2(
        second_account,
        (option_record, stock_record),
        option_terms_by_decision_fingerprint=mapping,
    )
    assert first.ordered_decision_fingerprints == second.ordered_decision_fingerprints
    assert first.account == second.account


def test_chronology_and_authority_fail_closed() -> None:
    record, terms = _option_case()
    account = initialize_simulation_account_v2(as_of_utc=CREATED, equity=20_000.0)
    account = apply_simulation_decision_v2(account, record, option_terms=terms).account
    with pytest.raises(SimulationAccountStateV2Error, match="cannot precede"):
        release_option_reservation_v2(
            account,
            decision_record_fingerprint=record.record_fingerprint,
            released_utc=CREATED,
        )
    with pytest.raises(SimulationAccountStateV2Error, match="cannot grant"):
        replace(account.state, broker_write_authority=True)
