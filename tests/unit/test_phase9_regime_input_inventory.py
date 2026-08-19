from __future__ import annotations

from packages.regimes.input_inventory import (
    CLASSIFICATION_FIELD_CANDIDATES,
    MARKET_PROXY_TICKERS,
    REGIME_INPUT_INVENTORY_CONTRACT_VERSION,
    SECTOR_PROXY_TICKERS,
    ProxyEvidence,
    RegimeInputInventory,
    complete_proxy_count,
    state_population,
)


def _proxy(ticker: str, *, complete: bool = True) -> ProxyEvidence:
    return ProxyEvidence(
        ticker=ticker,
        has_daily_bar=complete,
        has_daily_feature=complete,
        has_regular_4h_feature=complete,
        has_regular_1h_feature=complete,
        close=100.0 if complete else None,
        return_1=0.01 if complete else None,
        ema_20=99.0 if complete else None,
        ema_50=98.0 if complete else None,
        ema_200=90.0 if complete else None,
        rsi_14=55.0 if complete else None,
        macd_hist_12_26_9=0.1 if complete else None,
        natr_14=0.02 if complete else None,
        realized_volatility_20=0.03 if complete else None,
        directional_efficiency_20=0.4 if complete else None,
    )


def test_phase9_inventory_contract_and_proxy_baskets_are_fixed() -> None:
    assert REGIME_INPUT_INVENTORY_CONTRACT_VERSION == (
        "regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit"
    )
    assert MARKET_PROXY_TICKERS == ("SPY", "QQQ", "IWM", "DIA")
    assert len(SECTOR_PROXY_TICKERS) == 11
    assert len(set(SECTOR_PROXY_TICKERS)) == 11
    assert not (set(MARKET_PROXY_TICKERS) & set(SECTOR_PROXY_TICKERS))


def test_sector_classification_candidates_do_not_imply_mapping() -> None:
    assert {"sector", "industry", "sic_code", "sic_description"}.issubset(
        CLASSIFICATION_FIELD_CANDIDATES
    )


def test_complete_proxy_count_requires_every_timeframe_input() -> None:
    proxies = {
        "SPY": _proxy("SPY"),
        "QQQ": _proxy("QQQ"),
        "IWM": _proxy("IWM", complete=False),
    }
    assert complete_proxy_count(proxies) == 2


def test_state_population_and_percentage_helpers() -> None:
    assert state_population({"normal": 7_371, "watch": 652, "hot": 11}) == 8_034
    assert RegimeInputInventory._percentage(5, 10) == 0.5
    assert RegimeInputInventory._percentage(1, 0) == 0.0
