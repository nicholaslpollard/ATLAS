from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import (
    ActionabilityPolicy,
    EconomicCandidate,
    InstrumentKind,
    TradeExpressionMode,
)
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.simulation.account_state import (
    SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION,
    SimulationAccountEventKind,
    SimulationAccountLedger,
    SimulationAccountStateError,
    apply_competing_decisions,
    apply_simulation_decision,
    initialize_simulation_account,
    release_stock_reservation,
    replay_account_ledger,
)
from packages.simulation.account_state_contract import (
    SIMULATION_ACCOUNT_STATE_CONTRACT,
    SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT,
    contract_fingerprint,
)
from packages.simulation.decision_record import build_simulation_decision_record


CREATED = datetime(2026, 9, 16, 4, 0, tzinfo=UTC)
DECIDED = CREATED + timedelta(minutes=1)
CUTOFF = CREATED - timedelta(minutes=1)
SOURCE_FP = "4" * 64


def _threshold() -> MoveThresholdProbability:
    return MoveThresholdProbability(
        threshold_fraction=0.01,
        favorable_touch_probability=0.40,
        adverse_touch_probability=0.25,
        favorable_before_adverse_probability=0.32,
        adverse_before_favorable_probability=0.14,
        same_interval_collision_probability=0.04,
        median_favorable_time=10.0,
    )


def _forecast(
    *,
    instrument_id: str = "iid-xyz",
    ticker: str = "XYZ",
) -> UnderlyingMoveTimeForecast:
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=instrument_id,
        ticker=ticker,
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=CREATED,
        evidence_cutoff_utc=CUTOFF,
        horizon_unit=ForecastHorizonUnit.MINUTES,
        horizon_value=390,
        method_id="account-state-fixture-v1",
        source_label="account state fixture",
        source_fingerprint=SOURCE_FP,
        sample_size=1_000,
        reference_price=100.0,
        mean_signed_return=0.008,
        median_signed_return=0.005,
        p10_signed_return=-0.020,
        p25_signed_return=-0.006,
        p75_signed_return=0.018,
        p90_signed_return=0.035,
        probability_positive_return=0.58,
        mean_mfe=0.022,
        mean_mae=0.009,
        thresholds=(_threshold(),),
        uncertainty_score=0.30,
        reason_codes=("FIXTURE",),
    )


def _stock_inputs() -> StockEconomicsInputs:
    return StockEconomicsInputs(
        position_notional_dollars=10_000.0,
        capital_required_dollars=5_000.0,
        entry_slippage_bps=5.0,
        exit_slippage_bps=5.0,
        round_trip_commission_dollars=1.0,
        round_trip_fees_dollars=1.0,
        horizon_borrow_cost_dollars=0.0,
        horizon_financing_cost_dollars=2.0,
        net_probability_profit=0.50,
        liquidity_score=0.85,
        executable=True,
        risk_budget_ok=True,
        shortable_if_bearish=True,
    )


def _policy(**overrides: object) -> ActionabilityPolicy:
    payload: dict[str, object] = {
        "min_expected_net_value": 50.0,
        "min_expected_return_on_capital": 0.01,
        "min_probability_profit": 0.45,
        "max_expected_loss_to_gain_ratio": 0.50,
        "max_execution_cost_to_expected_gain_ratio": 0.10,
        "min_liquidity_score": 0.80,
        "material_superiority_ratio": 1.25,
    }
    payload.update(overrides)
    return ActionabilityPolicy(**payload)


def _option(identifier: str = "OPT-XYZ-A") -> EconomicCandidate:
    return EconomicCandidate(
        identifier=identifier,
        kind=InstrumentKind.OPTION,
        capital_required=1_000.0,
        expected_net_value=60.0,
        expected_return_on_capital=0.060,
        probability_profit=0.52,
        expected_gain_dollars=100.0,
        expected_loss_dollars=40.0,
        execution_cost_dollars=5.0,
        liquidity_score=0.90,
        preference_score=0.020,
        executable=True,
        risk_budget_ok=True,
        scenario_complete=True,
        option_contract_complete=True,
        greeks_complete=True,
        iv_context_complete=True,
        liquidity_context_complete=True,
        event_context_complete=True,
    )


def _record(
    *,
    decided: datetime = DECIDED,
    instrument_id: str = "iid-xyz",
    ticker: str = "XYZ",
    policy: ActionabilityPolicy | None = None,
    mode: TradeExpressionMode = TradeExpressionMode.STOCKS_ONLY,
    option_candidates: tuple[EconomicCandidate, ...] = (),
):
    return build_simulation_decision_record(
        decision_created_utc=decided,
        forecast=_forecast(instrument_id=instrument_id, ticker=ticker),
        stock_inputs=_stock_inputs(),
        actionability_policy=policy or _policy(),
        trade_expression_mode=mode,
        option_candidates=option_candidates,
    )


def test_account_state_contract_identity_and_authority_boundary_are_frozen() -> None:
    assert contract_fingerprint() == SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT
    assert SIMULATION_ACCOUNT_STATE_CONTRACT_FINGERPRINT == (
        "2460956a47dfa3f73c157b5e2f60aa710b10dabb0c1a7115309056d06c1a588b"
    )
    assert SIMULATION_ACCOUNT_STATE_CONTRACT_VERSION == "atlas-simulation-account-state-v1"
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["accounting_model"] == (
        "RESERVED_CAPITAL_NO_FILL_NO_PNL_V1"
    )
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["provider_reads"] == 0
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["broker_reads"] == 0
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["broker_writes"] == 0
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["fill_simulation_authority"] is False
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["realized_pnl_authority"] is False
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["mark_to_market_authority"] is False
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["paper_authority"] is False
    assert SIMULATION_ACCOUNT_STATE_CONTRACT["live_authority"] is False


def test_initial_state_is_deterministic_and_fully_unreserved() -> None:
    first = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    second = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    assert first.state.state_fingerprint == second.state.state_fingerprint
    assert first.ledger.ledger_fingerprint == second.ledger.ledger_fingerprint
    assert first.state.cash == 100_000.0
    assert first.state.equity == 100_000.0
    assert first.state.reserved_capital == 0.0
    assert first.state.gross_exposure == 0.0
    assert first.state.stock_reservations == ()
    assert first.ledger.events == ()


def test_stock_decision_reserves_capital_and_tracks_gross_exposure() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    record = _record()
    transition = apply_simulation_decision(account, record)
    state = transition.account.state
    assert transition.idempotent_reuse is False
    assert transition.event is not None
    assert transition.event.kind == SimulationAccountEventKind.RESERVE_STOCK
    assert transition.event.decision_record_fingerprint == record.record_fingerprint
    assert state.cash == pytest.approx(95_000.0)
    assert state.reserved_capital == pytest.approx(5_000.0)
    assert state.gross_exposure == pytest.approx(10_000.0)
    assert state.equity == pytest.approx(100_000.0)
    assert len(state.stock_reservations) == 1
    reservation = state.stock_reservations[0]
    assert reservation.decision_record_fingerprint == record.record_fingerprint
    assert reservation.reserved_capital == pytest.approx(5_000.0)
    assert reservation.gross_exposure == pytest.approx(10_000.0)


def test_release_restores_capital_without_inventing_pnl() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    reserved = apply_simulation_decision(account, _record()).account
    released = release_stock_reservation(
        reserved,
        decision_record_fingerprint=reserved.state.stock_reservations[0].decision_record_fingerprint,
        released_utc=DECIDED + timedelta(minutes=5),
    )
    assert released.event is not None
    assert released.event.kind == SimulationAccountEventKind.RELEASE_STOCK
    assert released.account.state.cash == pytest.approx(100_000.0)
    assert released.account.state.reserved_capital == 0.0
    assert released.account.state.gross_exposure == 0.0
    assert released.account.state.equity == pytest.approx(100_000.0)
    assert released.account.state.stock_reservations == ()
    assert released.account.state.realized_pnl_authority is False
    assert released.account.state.mark_to_market_authority is False


def test_insufficient_cash_rejects_without_changing_account_amounts() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=1_000.0)
    transition = apply_simulation_decision(account, _record())
    assert transition.event is not None
    assert transition.event.kind == SimulationAccountEventKind.REJECT_INSUFFICIENT_CAPITAL
    assert transition.reason_codes == ("INSUFFICIENT_UNRESERVED_CAPITAL",)
    assert transition.account.state.cash == 1_000.0
    assert transition.account.state.reserved_capital == 0.0
    assert transition.account.state.gross_exposure == 0.0
    assert transition.account.state.stock_reservations == ()


def test_abstain_and_option_selection_are_audited_without_stock_reservation() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    abstain_record = _record(policy=_policy(min_expected_net_value=10_000.0))
    abstained = apply_simulation_decision(account, abstain_record)
    assert abstained.event is not None
    assert abstained.event.kind == SimulationAccountEventKind.ABSTAIN
    assert abstained.account.state.reserved_capital == 0.0

    option_record = _record(
        decided=DECIDED + timedelta(minutes=1),
        mode=TradeExpressionMode.OPTIONS_ONLY,
        option_candidates=(_option(),),
    )
    option_rejected = apply_simulation_decision(abstained.account, option_record)
    assert option_rejected.event is not None
    assert option_rejected.event.kind == SimulationAccountEventKind.REJECT_UNSUPPORTED_OPTION
    assert option_rejected.reason_codes == ("OPTION_ACCOUNT_SEMANTICS_NOT_ACCEPTED",)
    assert option_rejected.account.state.cash == 100_000.0
    assert option_rejected.account.state.reserved_capital == 0.0
    assert option_rejected.account.state.gross_exposure == 0.0


def test_duplicate_decision_and_release_are_idempotent() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    record = _record()
    first = apply_simulation_decision(account, record)
    duplicate = apply_simulation_decision(first.account, record)
    assert duplicate.idempotent_reuse is True
    assert duplicate.event is None
    assert duplicate.account.ledger.ledger_fingerprint == first.account.ledger.ledger_fingerprint

    released = release_stock_reservation(
        first.account,
        decision_record_fingerprint=record.record_fingerprint,
        released_utc=DECIDED + timedelta(minutes=5),
    )
    duplicate_release = release_stock_reservation(
        released.account,
        decision_record_fingerprint=record.record_fingerprint,
        released_utc=DECIDED + timedelta(minutes=6),
    )
    assert duplicate_release.idempotent_reuse is True
    assert duplicate_release.event is None
    assert duplicate_release.account.ledger.ledger_fingerprint == (
        released.account.ledger.ledger_fingerprint
    )


def test_competition_order_is_deterministic_and_independent_of_input_order() -> None:
    account_a = initialize_simulation_account(as_of_utc=CREATED, equity=7_500.0)
    account_b = initialize_simulation_account(as_of_utc=CREATED, equity=7_500.0)
    record_a = _record(instrument_id="iid-a", ticker="AAA")
    record_b = _record(instrument_id="iid-b", ticker="BBB")

    forward = apply_competing_decisions(account_a, (record_a, record_b))
    reverse = apply_competing_decisions(account_b, (record_b, record_a))

    assert forward.ordered_decision_fingerprints == reverse.ordered_decision_fingerprints
    assert forward.account.state.state_fingerprint == reverse.account.state.state_fingerprint
    assert forward.account.ledger.ledger_fingerprint == reverse.account.ledger.ledger_fingerprint
    kinds = tuple(
        transition.event.kind
        for transition in forward.transitions
        if transition.event is not None
    )
    assert kinds.count(SimulationAccountEventKind.RESERVE_STOCK) == 1
    assert kinds.count(SimulationAccountEventKind.REJECT_INSUFFICIENT_CAPITAL) == 1
    assert forward.account.state.reserved_capital == pytest.approx(5_000.0)
    assert forward.account.state.cash == pytest.approx(2_500.0)


def test_ledger_replay_reconstructs_exact_state_and_fingerprints() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    record_a = _record(instrument_id="iid-a", ticker="AAA")
    record_b = _record(
        decided=DECIDED + timedelta(minutes=1),
        instrument_id="iid-b",
        ticker="BBB",
    )
    applied = apply_competing_decisions(account, (record_b, record_a)).account
    released = release_stock_reservation(
        applied,
        decision_record_fingerprint=record_a.record_fingerprint,
        released_utc=DECIDED + timedelta(minutes=5),
    ).account

    replayed = replay_account_ledger(released.ledger)
    assert replayed.state.state_fingerprint == released.state.state_fingerprint
    assert replayed.ledger.ledger_fingerprint == released.ledger.ledger_fingerprint
    assert tuple(event.event_fingerprint for event in replayed.ledger.events) == tuple(
        event.event_fingerprint for event in released.ledger.events
    )


def test_ledger_replay_fails_closed_on_tampered_state_lineage() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    applied = apply_simulation_decision(account, _record()).account
    event = applied.ledger.events[0]
    tampered_event = replace(event, after_state_fingerprint="0" * 64)
    tampered_ledger = SimulationAccountLedger(
        contract_version=applied.ledger.contract_version,
        contract_fingerprint=applied.ledger.contract_fingerprint,
        initial_equity=applied.ledger.initial_equity,
        initial_as_of_utc=applied.ledger.initial_as_of_utc,
        initial_state_fingerprint=applied.ledger.initial_state_fingerprint,
        events=(tampered_event,),
    )
    with pytest.raises(SimulationAccountStateError, match="after-state fingerprint"):
        replay_account_ledger(tampered_ledger)


def test_state_and_ledger_do_not_grant_execution_or_trading_authority() -> None:
    account = initialize_simulation_account(as_of_utc=CREATED, equity=100_000.0)
    state = apply_simulation_decision(account, _record()).account.state
    assert state.provider_read_authority is False
    assert state.provider_write_authority is False
    assert state.broker_read_authority is False
    assert state.broker_write_authority is False
    assert state.order_creation_authority is False
    assert state.fill_simulation_authority is False
    assert state.realized_pnl_authority is False
    assert state.mark_to_market_authority is False
    assert state.paper_authority is False
    assert state.live_authority is False
    assert state.promotion_authority is False
    assert state.confluence_authority is False


def test_chronology_and_unknown_release_fail_closed() -> None:
    account = initialize_simulation_account(as_of_utc=DECIDED, equity=100_000.0)
    stale_record = _record(decided=DECIDED - timedelta(seconds=1))
    with pytest.raises(SimulationAccountStateError, match="cannot precede"):
        apply_simulation_decision(account, stale_record)
    with pytest.raises(SimulationAccountStateError, match="not found"):
        release_stock_reservation(
            account,
            decision_record_fingerprint="a" * 64,
            released_utc=DECIDED + timedelta(minutes=1),
        )
