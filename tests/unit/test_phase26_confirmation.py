from __future__ import annotations

from packages.backtesting.phase26_confirmation import protected_checks
from packages.backtesting.phase26_research import Phase26TrancheMetrics


def _metrics(**overrides: object) -> Phase26TrancheMetrics:
    values: dict[str, object] = {
        "raw_rows": 100,
        "signal_sessions": 30,
        "primary_mean_return": 0.01,
        "primary_median_trade_return": -0.001,
        "primary_trade_win_rate": 0.40,
        "primary_session_win_rate": 0.60,
        "primary_lcb": 0.001,
        "primary_bootstrap_p_value": 0.01,
        "stress_mean_return": 0.005,
        "max_single_session_row_fraction": 0.05,
        "fold_means": (0.01, -0.001, 0.02),
        "positive_folds": 2,
        "eligible_year_means": {},
        "positive_year_fraction": None,
        "eligible_market_state_means": {},
        "positive_market_state_fraction": None,
        "eligible_ticker_state_means": {},
        "positive_ticker_state_fraction": None,
        "session_sharpe": 0.5,
        "deflated_sharpe_probability": None,
        "deflated_sharpe_benchmark": None,
    }
    values.update(overrides)
    return Phase26TrancheMetrics(**values)  # type: ignore[arg-type]


def test_protected_confirmation_accepts_positive_expectancy_below_half_win_rate() -> None:
    checks = protected_checks(_metrics())
    assert all(checks.values())
    assert "primary_trade_win_rate" not in checks
    assert "primary_median_trade_return" not in checks


def test_protected_confirmation_rejects_negative_stress_economics() -> None:
    checks = protected_checks(_metrics(stress_mean_return=-0.0001))
    assert checks["stress_mean_positive"] is False
