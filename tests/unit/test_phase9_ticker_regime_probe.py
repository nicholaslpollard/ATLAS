from packages.core.enums import Timeframe
from packages.regimes.ticker_probe import (
    TICKER_REGIME_PROBE_CONTRACT_VERSION,
    TICKER_REGIME_REQUIRED_HISTORY_SESSIONS,
    TICKER_REGIME_TIMEFRAMES,
    candidate_ticker_state,
    daily_structure_state,
    intraday_direction_state,
    short_alignment_state,
    ticker_momentum_state,
)


def test_ticker_regime_probe_contract_is_locked():
    assert TICKER_REGIME_PROBE_CONTRACT_VERSION == (
        "ticker-regime-probe-v1-routed-multitimeframe-identity-history-audit"
    )
    assert TICKER_REGIME_REQUIRED_HISTORY_SESSIONS == 252
    assert TICKER_REGIME_TIMEFRAMES == (
        Timeframe.DAY_1,
        Timeframe.HOUR_4,
        Timeframe.HOUR_1,
    )


def test_daily_structure_state_boundaries():
    assert daily_structure_state(6) == "STRONG_UP"
    assert daily_structure_state(4) == "STRONG_UP"
    assert daily_structure_state(3) == "UP"
    assert daily_structure_state(2) == "UP"
    assert daily_structure_state(1) == "MIXED"
    assert daily_structure_state(-1) == "MIXED"
    assert daily_structure_state(-2) == "DOWN"
    assert daily_structure_state(-3) == "DOWN"
    assert daily_structure_state(-4) == "STRONG_DOWN"
    assert daily_structure_state(-6) == "STRONG_DOWN"


def test_intraday_direction_and_short_alignment():
    assert intraday_direction_state(5) == "UP"
    assert intraday_direction_state(3) == "UP"
    assert intraday_direction_state(2) == "MIXED"
    assert intraday_direction_state(-2) == "MIXED"
    assert intraday_direction_state(-3) == "DOWN"
    assert short_alignment_state("UP", "UP") == "ALIGNED_UP"
    assert short_alignment_state("DOWN", "DOWN") == "ALIGNED_DOWN"
    assert short_alignment_state("UP", "DOWN") == "MIXED"
    assert short_alignment_state("UP", "MIXED") == "MIXED"


def test_ticker_momentum_uses_rsi_neutral_band():
    assert ticker_momentum_state(return_1=0.01, rsi_14=60.0, macd_hist=0.2) == "POSITIVE"
    assert ticker_momentum_state(return_1=-0.01, rsi_14=40.0, macd_hist=-0.2) == "NEGATIVE"
    assert ticker_momentum_state(return_1=0.01, rsi_14=50.0, macd_hist=-0.2) == "MIXED"
    assert ticker_momentum_state(return_1=-0.01, rsi_14=50.0, macd_hist=0.2) == "MIXED"


def test_candidate_ticker_state_preserves_context_not_strategy_selection():
    assert candidate_ticker_state(
        daily_structure="STRONG_UP",
        short_alignment="ALIGNED_UP",
        momentum="POSITIVE",
    ) == "STRONG_UPTREND"
    assert candidate_ticker_state(
        daily_structure="UP",
        short_alignment="ALIGNED_DOWN",
        momentum="NEGATIVE",
    ) == "PULLBACK_UP"
    assert candidate_ticker_state(
        daily_structure="DOWN",
        short_alignment="ALIGNED_UP",
        momentum="POSITIVE",
    ) == "BOUNCE_DOWN"
    assert candidate_ticker_state(
        daily_structure="MIXED",
        short_alignment="ALIGNED_UP",
        momentum="POSITIVE",
    ) == "TRANSITION_UP"
    assert candidate_ticker_state(
        daily_structure="MIXED",
        short_alignment="MIXED",
        momentum="MIXED",
    ) == "RANGE_MIXED"
