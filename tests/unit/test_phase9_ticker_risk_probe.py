import pandas as pd

from packages.regimes.ticker_risk_probe import (
    EFFICIENCY_STATE_ORDER,
    RISK_STATE_ORDER,
    TICKER_RISK_LOOKBACK_WINDOWS,
    TICKER_RISK_PROBE_CONTRACT_VERSION,
    TICKER_RISK_REFERENCE_WINDOW,
    ordinal_agreement,
    self_relative_efficiency_state,
    self_relative_volatility_state,
)


def test_gate11_probe_contract_and_lookback_grid_are_explicit() -> None:
    assert TICKER_RISK_PROBE_CONTRACT_VERSION == (
        "ticker-risk-probe-v1-safe-self-relative-prior-only-lookback-grid"
    )
    assert TICKER_RISK_LOOKBACK_WINDOWS == (20, 60, 126, 252)
    assert TICKER_RISK_REFERENCE_WINDOW == 252


def test_self_relative_volatility_state_semantics() -> None:
    common = dict(
        natr_p25=1.0,
        natr_p75=2.0,
        natr_p90=3.0,
        realized_p25=0.10,
        realized_p75=0.20,
        realized_p90=0.30,
    )
    assert self_relative_volatility_state(natr_value=0.8, realized_volatility_value=0.08, **common) == "CALM"
    assert self_relative_volatility_state(natr_value=1.5, realized_volatility_value=0.15, **common) == "NORMAL"
    assert self_relative_volatility_state(natr_value=2.1, realized_volatility_value=0.15, **common) == "ELEVATED"
    assert self_relative_volatility_state(natr_value=1.5, realized_volatility_value=0.31, **common) == "STRESSED"


def test_self_relative_efficiency_state_semantics() -> None:
    assert self_relative_efficiency_state(value=0.10, p25=0.20, p75=0.70) == "LOW"
    assert self_relative_efficiency_state(value=0.50, p25=0.20, p75=0.70) == "NORMAL"
    assert self_relative_efficiency_state(value=0.80, p25=0.20, p75=0.70) == "HIGH"


def test_ordinal_agreement_reports_exact_and_within_one_level() -> None:
    diagnostics = ordinal_agreement(
        pd.Series(["CALM", "NORMAL", "ELEVATED", "STRESSED"]),
        pd.Series(["CALM", "ELEVATED", "ELEVATED", "ELEVATED"]),
        RISK_STATE_ORDER,
    )
    assert diagnostics["comparison_count"] == 4
    assert diagnostics["exact_agreement_rate"] == 0.5
    assert diagnostics["within_one_level_rate"] == 1.0
    assert diagnostics["two_or_more_level_mismatch_count"] == 0


def test_ordinal_agreement_detects_material_efficiency_inversion() -> None:
    diagnostics = ordinal_agreement(
        pd.Series(["LOW", "NORMAL", "HIGH"]),
        pd.Series(["HIGH", "NORMAL", "LOW"]),
        EFFICIENCY_STATE_ORDER,
    )
    assert diagnostics["comparison_count"] == 3
    assert diagnostics["exact_agreement_rate"] == 1 / 3
    assert diagnostics["two_or_more_level_mismatch_count"] == 2
    assert diagnostics["two_or_more_level_mismatch_rate"] == 2 / 3
    assert diagnostics["max_level_distance"] == 2
