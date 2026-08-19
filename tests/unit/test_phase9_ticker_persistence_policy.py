from packages.regimes.ticker_persistence_policy import (
    TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION,
    TICKER_SELECTED_CONFIRMATION_SESSIONS,
    TICKER_SELECTED_PERSISTENCE_MODE,
    TICKER_SELECTED_PERSISTENCE_POLICY_NAME,
)


def test_gate10_selected_ticker_persistence_policy_is_locked() -> None:
    assert TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION == (
        "ticker-persistence-policy-v1-two-session-dimensional-confirmation"
    )
    assert TICKER_SELECTED_CONFIRMATION_SESSIONS == 2
    assert TICKER_SELECTED_PERSISTENCE_MODE == "dimensional"
    assert TICKER_SELECTED_PERSISTENCE_POLICY_NAME == "dimensional_confirm_2"


def test_gate10_selected_policy_name_matches_mode_and_window() -> None:
    assert TICKER_SELECTED_PERSISTENCE_POLICY_NAME == (
        f"{TICKER_SELECTED_PERSISTENCE_MODE}_confirm_{TICKER_SELECTED_CONFIRMATION_SESSIONS}"
    )
