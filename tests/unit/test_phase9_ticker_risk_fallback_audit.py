import pandas as pd

from packages.regimes.ticker_risk_fallback_audit import (
    TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION,
    directional_ordinal_diagnostics,
    history_cohort_counts,
)


def test_gate11_fallback_audit_contract_is_explicit() -> None:
    assert TICKER_RISK_FALLBACK_AUDIT_CONTRACT_VERSION == (
        "ticker-risk-fallback-audit-v1-current-severity-and-history-cohorts"
    )


def test_directional_ordinal_diagnostics_separates_under_and_overstatement() -> None:
    diagnostics = directional_ordinal_diagnostics(
        pd.Series(["CALM", "NORMAL", "CALM", "STRESSED", "ELEVATED"]),
        pd.Series(["CALM", "ELEVATED", "STRESSED", "NORMAL", "NORMAL"]),
    )
    assert diagnostics["comparison_count"] == 5
    assert diagnostics["exact_count"] == 1
    assert diagnostics["under_one_count"] == 1
    assert diagnostics["under_two_plus_count"] == 1
    assert diagnostics["over_one_count"] == 1
    assert diagnostics["over_two_plus_count"] == 1


def test_directional_ordinal_diagnostics_tracks_stressed_understatement() -> None:
    diagnostics = directional_ordinal_diagnostics(
        pd.Series(["CALM", "NORMAL", "ELEVATED", "STRESSED"]),
        pd.Series(["STRESSED", "STRESSED", "STRESSED", "STRESSED"]),
    )
    assert diagnostics["stressed_reference_count"] == 4
    assert diagnostics["stressed_as_calm_or_normal_count"] == 2
    assert diagnostics["stressed_as_calm_or_normal_rate"] == 0.5


def test_history_cohort_counts_are_exclusive_and_exhaustive() -> None:
    frame = pd.DataFrame(
        {"prior_count_252": [0, 19, 20, 59, 60, 125, 126, 251, 252, 252]}
    )
    assert history_cohort_counts(frame) == {
        "<20": 2,
        "20-59": 2,
        "60-125": 2,
        "126-251": 2,
        ">=252": 2,
    }
