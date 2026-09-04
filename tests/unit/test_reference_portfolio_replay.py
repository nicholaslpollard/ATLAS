from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import pandas as pd
import pytest

from packages.backtesting.reference_portfolio_policy import (
    reference_portfolio_policy_fingerprint,
)
from packages.backtesting.reference_portfolio_replay import (
    ReferenceAccountPortfolioReplay,
    ReferencePortfolioReplayError,
)
from packages.backtesting.reference_strategy_runner import (
    ProtectedMasterWindowError,
    reference_input_fingerprint,
)
from packages.features.reference_daily import REFERENCE_DAILY_FEATURE_FINGERPRINT
from packages.schemas.reference_portfolio import ReferencePortfolioDecisionStatus
from packages.schemas.strategy import StrategyDirection
from packages.schemas.strategy_lab import (
    OpportunityDisposition,
    OpportunityOutcomeStatus,
    ReferenceExitReason,
    ReferenceHistoricalRun,
    ReferenceOpportunityRecord,
)
from packages.strategies.reference_library import REFERENCE_STRATEGY_CATALOG


SESSIONS = (date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6))


def _bars(*instrument_ids: str) -> pd.DataFrame:
    rows = []
    for index, instrument_id in enumerate(instrument_ids):
        ticker = f"T{index}"
        for session, open_price, close_price in zip(
            SESSIONS, (99.0, 100.0, 109.0), (99.0, 101.0, 110.0), strict=True
        ):
            rows.append(
                {
                    "instrument_id": instrument_id,
                    "ticker": ticker,
                    "session_date": session,
                    "timestamp_utc": datetime.combine(
                        session, datetime.min.time(), tzinfo=UTC
                    ),
                    "open": open_price,
                    "high": max(open_price, close_price) + 1.0,
                    "low": min(open_price, close_price) - 1.0,
                    "close": close_price,
                    "volume": 1_000_000.0,
                    "unadjusted_close": close_price,
                    "pit_active": True,
                    "security_type": "CS",
                    "identity_clear": True,
                    "price_adjustment_mode": "SPLIT_ADJUSTED",
                    "raw_price_lineage_id": "test-lineage",
                }
            )
    return pd.DataFrame(rows)


def _opportunity(
    *,
    instrument_id: str,
    ticker: str,
    strategy_id: str,
    direction: StrategyDirection,
    exit_price: float,
) -> ReferenceOpportunityRecord:
    specification = REFERENCE_STRATEGY_CATALOG.get(strategy_id)
    entry_price = 100.0
    stop = 95.0 if direction == StrategyDirection.LONG else 105.0
    target = 110.0 if direction == StrategyDirection.LONG else 90.0
    gross = (
        exit_price / entry_price - 1.0
        if direction == StrategyDirection.LONG
        else 1.0 - exit_price / entry_price
    )
    opportunity_id = hashlib.sha256(
        f"{instrument_id}:{strategy_id}:{SESSIONS[0]}".encode("utf-8")
    ).hexdigest()
    return ReferenceOpportunityRecord(
        opportunity_id=opportunity_id,
        strategy_id=strategy_id,
        strategy_policy_fingerprint=specification.fingerprint(),
        family=specification.family,
        direction=direction,
        instrument_id=instrument_id,
        ticker=ticker,
        signal_session=SESSIONS[0],
        signal_timestamp_utc=datetime(2025, 1, 2, 21, 0, tzinfo=UTC),
        market_regime="UNAVAILABLE",
        sector_regime="UNAVAILABLE",
        ticker_regime="UNAVAILABLE",
        volatility_bucket="MEDIUM_2_TO_4PCT",
        liquidity_bucket="LIQUID_20_TO_100M",
        universe_eligible=True,
        disposition=OpportunityDisposition.SELECTED_INDEPENDENT_REPLAY,
        reason_codes=("SIGNAL_FIRED", "SELECTED:INDEPENDENT_STRATEGY_REPLAY"),
        selected_for_independent_replay=True,
        counterfactual_only=False,
        entry_session=SESSIONS[1],
        entry_price=entry_price,
        initial_stop_price=stop,
        target_price=target,
        quantity=50,
        initial_risk_per_share=5.0,
        outcome_status=OpportunityOutcomeStatus.EXITED,
        exit_session=SESSIONS[2],
        exit_price=exit_price,
        exit_reason=ReferenceExitReason.PROFIT_TARGET,
        holding_sessions=2,
        gross_directional_return=gross,
        net_directional_returns_by_cost_bps={"10": gross - 0.001},
        primary_net_directional_return=gross - 0.001,
        risk_multiple=gross * entry_price / 5.0,
        maximum_favorable_excursion=max(gross, 0.0),
        maximum_adverse_excursion=min(gross, 0.0),
    )


def _run(frame: pd.DataFrame, *opportunities: ReferenceOpportunityRecord) -> ReferenceHistoricalRun:
    return ReferenceHistoricalRun(
        run_fingerprint="a" * 64,
        input_fingerprint=reference_input_fingerprint(frame),
        catalog_fingerprint=REFERENCE_STRATEGY_CATALOG.fingerprint(),
        feature_fingerprint=REFERENCE_DAILY_FEATURE_FINGERPRINT,
        input_rows=len(frame),
        input_instruments=frame["instrument_id"].nunique(),
        first_session=min(frame["session_date"]),
        last_session=max(frame["session_date"]),
        opportunities=opportunities,
        summary_by_strategy={},
        condition_slices={},
    )


def test_account_replay_sizes_cash_position_costs_and_equity_deterministically() -> None:
    frame = _bars("figi:LONG")
    opportunity = _opportunity(
        instrument_id="figi:LONG",
        ticker="T0",
        strategy_id="ma_trend_cross_50_200_long_v1",
        direction=StrategyDirection.LONG,
        exit_price=110.0,
    )
    independent = _run(frame, opportunity)
    first = ReferenceAccountPortfolioReplay().run(frame, independent)
    second = ReferenceAccountPortfolioReplay().run(frame, independent)

    assert first.replay_fingerprint == second.replay_fingerprint
    assert first.portfolio_policy_fingerprint == reference_portfolio_policy_fingerprint()
    assert first.admitted_positions == first.completed_positions == 1
    assert first.decisions[0].status == ReferencePortfolioDecisionStatus.ADMITTED
    assert first.decisions[0].admitted_quantity == 49
    assert len(first.simulated_orders) == 2
    assert first.total_transaction_cost == pytest.approx(5.145)
    assert first.position_outcomes[0].net_pnl == pytest.approx(484.855)
    assert first.final_equity == pytest.approx(100_484.855)
    assert first.total_return == pytest.approx(0.00484855)
    assert first.open_positions_at_end == 0
    assert first.broker_writes == first.paper_submits == first.live_writes == 0


def test_short_candidate_is_retained_but_rejected_until_borrow_is_modeled() -> None:
    frame = _bars("figi:SHORT")
    opportunity = _opportunity(
        instrument_id="figi:SHORT",
        ticker="T0",
        strategy_id="macd_shift_12_26_9_short_v1",
        direction=StrategyDirection.SHORT,
        exit_price=90.0,
    )
    result = ReferenceAccountPortfolioReplay().run(frame, _run(frame, opportunity))
    assert result.admitted_positions == result.completed_positions == 0
    assert result.final_equity == 100_000.0
    assert result.decisions[0].status == ReferencePortfolioDecisionStatus.REJECTED
    assert result.decisions[0].reason_codes == (
        "SHORT_REJECTED:BORROW_AND_LOCATE_NOT_MODELED",
    )
    assert result.simulated_orders == ()


def test_same_instrument_collision_admits_one_without_outcome_based_ranking() -> None:
    frame = _bars("figi:SAME")
    first = _opportunity(
        instrument_id="figi:SAME",
        ticker="T0",
        strategy_id="ma_trend_cross_50_200_long_v1",
        direction=StrategyDirection.LONG,
        exit_price=110.0,
    )
    second = _opportunity(
        instrument_id="figi:SAME",
        ticker="T0",
        strategy_id="macd_shift_12_26_9_long_v1",
        direction=StrategyDirection.LONG,
        exit_price=80.0,
    )
    result = ReferenceAccountPortfolioReplay().run(frame, _run(frame, first, second))
    assert result.admitted_positions == 1
    assert sum(
        item.status == ReferencePortfolioDecisionStatus.REJECTED for item in result.decisions
    ) == 1
    assert any("INSTRUMENT_ALREADY_ACTIVE" in item.reason_codes for item in result.decisions)
    admitted = next(
        item for item in result.decisions if item.status == ReferencePortfolioDecisionStatus.ADMITTED
    )
    # MOMENTUM sorts before MOVING_AVERAGE_TREND even though this candidate loses;
    # the fixed selector does not peek at realized performance.
    assert admitted.strategy_id == "macd_shift_12_26_9_long_v1"


def test_portfolio_replay_rejects_input_fingerprint_drift() -> None:
    frame = _bars("figi:LONG")
    opportunity = _opportunity(
        instrument_id="figi:LONG",
        ticker="T0",
        strategy_id="ma_trend_cross_50_200_long_v1",
        direction=StrategyDirection.LONG,
        exit_price=110.0,
    )
    independent = _run(frame, opportunity)
    changed = frame.copy()
    changed.loc[0, "close"] = 98.0
    with pytest.raises(ReferencePortfolioReplayError, match="exact independent replay input"):
        ReferenceAccountPortfolioReplay().run(changed, independent)


def test_portfolio_replay_rejects_master_protected_window_before_outcomes() -> None:
    frame = _bars("figi:LONG")
    independent = _run(frame)
    protected = frame.copy()
    protected["session_date"] = date(2026, 6, 1)
    with pytest.raises(ProtectedMasterWindowError, match="master protected window"):
        ReferenceAccountPortfolioReplay().run(protected, independent)
