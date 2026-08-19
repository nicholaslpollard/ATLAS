from packages.regimes.hierarchy_audit import (
    REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION,
    REGIME_HIERARCHY_INDUSTRY_POLICY,
    REGIME_HIERARCHY_SECTOR_ASSIGNMENT_POLICY,
    hierarchy_ready,
    sector_layer_valid,
)
from packages.regimes.input_inventory import SECTOR_PROXY_TICKERS


def test_gate13_hierarchy_contract_and_classification_policies_are_explicit() -> None:
    assert REGIME_HIERARCHY_AUDIT_CONTRACT_VERSION == (
        "regime-hierarchy-integrity-v1-market-sector-proxy-optional-sic-ticker"
    )
    assert REGIME_HIERARCHY_INDUSTRY_POLICY == "OPTIONAL_AUTHORITATIVE_SIC_ONLY"
    assert REGIME_HIERARCHY_SECTOR_ASSIGNMENT_POLICY == "NO_GUESSED_CROSSWALK"


def test_sector_layer_requires_exact_expected_proxy_set_and_effective_states() -> None:
    sectors = {
        ticker: {"effective": {"composite": "BULL"}}
        for ticker in SECTOR_PROXY_TICKERS
    }
    exact, effective = sector_layer_valid(sectors)
    assert exact is True
    assert effective == len(SECTOR_PROXY_TICKERS)


def test_sector_layer_rejects_missing_or_extra_proxy() -> None:
    sectors = {
        ticker: {"effective": {"composite": "MIXED"}}
        for ticker in SECTOR_PROXY_TICKERS[:-1]
    }
    sectors["FAKE"] = {"effective": {"composite": "MIXED"}}
    exact, effective = sector_layer_valid(sectors)
    assert exact is False
    assert effective == len(SECTOR_PROXY_TICKERS) - 1


def test_hierarchy_ready_requires_exact_route_and_identity_alignment() -> None:
    assert hierarchy_ready(
        market_snapshot_valid=True,
        sector_exact_set=True,
        sector_effective_state_count=len(SECTOR_PROXY_TICKERS),
        routed_expected_count=8034,
        ticker_record_count=8034,
        ticker_unique_instrument_count=8034,
        route_exact_match_count=8034,
        missing_routed_count=0,
        extra_ticker_state_count=0,
        current_ticker_mismatch_count=0,
    ) is True


def test_hierarchy_ready_fails_on_ticker_identity_mismatch() -> None:
    assert hierarchy_ready(
        market_snapshot_valid=True,
        sector_exact_set=True,
        sector_effective_state_count=len(SECTOR_PROXY_TICKERS),
        routed_expected_count=8034,
        ticker_record_count=8034,
        ticker_unique_instrument_count=8034,
        route_exact_match_count=8033,
        missing_routed_count=0,
        extra_ticker_state_count=0,
        current_ticker_mismatch_count=1,
    ) is False
