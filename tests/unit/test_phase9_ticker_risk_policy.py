from packages.regimes.ticker_risk_policy import (
    TICKER_RISK_MODE_FULL,
    TICKER_RISK_MODE_IDENTITY_BLOCKED,
    TICKER_RISK_MODE_INSUFFICIENT,
    TICKER_RISK_MODE_NO_CURRENT_METRICS,
    TICKER_RISK_MODE_PROVISIONAL,
    TICKER_RISK_POLICY_CONTRACT_VERSION,
    TICKER_RISK_PRIMARY_WINDOW,
    TICKER_RISK_PROVISIONAL_WINDOW,
    TICKER_RISK_REFERENCE_AUDIT_WINDOW,
    ticker_risk_history_mode,
    ticker_risk_selected_window,
)


def test_gate11_risk_policy_contract_and_windows_are_locked() -> None:
    assert TICKER_RISK_POLICY_CONTRACT_VERSION == (
        "ticker-risk-policy-v1-126-primary-60-provisional-prior-only"
    )
    assert TICKER_RISK_PRIMARY_WINDOW == 126
    assert TICKER_RISK_PROVISIONAL_WINDOW == 60
    assert TICKER_RISK_REFERENCE_AUDIT_WINDOW == 252


def test_gate11_full_mode_starts_at_126_prior_sessions() -> None:
    mode = ticker_risk_history_mode(
        identity_safe=True,
        has_current_metrics=True,
        prior_sessions=126,
    )
    assert mode == TICKER_RISK_MODE_FULL
    assert ticker_risk_selected_window(mode) == 126


def test_gate11_provisional_mode_covers_60_through_125_prior_sessions() -> None:
    for prior_sessions in (60, 61, 125):
        mode = ticker_risk_history_mode(
            identity_safe=True,
            has_current_metrics=True,
            prior_sessions=prior_sessions,
        )
        assert mode == TICKER_RISK_MODE_PROVISIONAL
        assert ticker_risk_selected_window(mode) == 60


def test_gate11_less_than_60_prior_sessions_is_insufficient() -> None:
    mode = ticker_risk_history_mode(
        identity_safe=True,
        has_current_metrics=True,
        prior_sessions=59,
    )
    assert mode == TICKER_RISK_MODE_INSUFFICIENT
    assert ticker_risk_selected_window(mode) is None


def test_gate11_missing_metrics_and_identity_block_override_history_depth() -> None:
    assert ticker_risk_history_mode(
        identity_safe=True,
        has_current_metrics=False,
        prior_sessions=500,
    ) == TICKER_RISK_MODE_NO_CURRENT_METRICS
    assert ticker_risk_history_mode(
        identity_safe=False,
        has_current_metrics=True,
        prior_sessions=500,
    ) == TICKER_RISK_MODE_IDENTITY_BLOCKED
