from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.regimes.classification_probe import REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION
from packages.regimes.input_inventory import (
    CLASSIFICATION_FIELD_CANDIDATES,
    MARKET_PROXY_TICKERS,
    REGIME_INPUT_INVENTORY_CONTRACT_VERSION,
    SECTOR_PROXY_TICKERS,
)


def main() -> int:
    assert REGIME_INPUT_INVENTORY_CONTRACT_VERSION == (
        "regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit"
    )
    assert REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION == (
        "regime-classification-probe-v1-massive-sic-point-in-time"
    )
    assert MARKET_PROXY_TICKERS == ("SPY", "QQQ", "IWM", "DIA")
    assert SECTOR_PROXY_TICKERS == (
        "XLB",
        "XLC",
        "XLE",
        "XLF",
        "XLI",
        "XLK",
        "XLP",
        "XLRE",
        "XLU",
        "XLV",
        "XLY",
    )
    assert not (set(MARKET_PROXY_TICKERS) & set(SECTOR_PROXY_TICKERS))
    assert {"sector", "industry", "sic_code"}.issubset(CLASSIFICATION_FIELD_CANDIDATES)

    settings = load_settings(PROJECT_ROOT, "development")
    paths = MarketDataPaths(settings)
    sample_date = date(2026, 8, 14)
    inventory = paths.regime_input_inventory_report(sample_date)
    probe = paths.regime_classification_probe_report(sample_date)
    assert "regimes" in inventory.parts and "input_inventory" in inventory.parts
    assert "regimes" in probe.parts and "classification_probe" in probe.parts
    assert inventory != probe

    print(f"Regime input inventory contract: {REGIME_INPUT_INVENTORY_CONTRACT_VERSION}")
    print(f"Classification probe contract: {REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION}")
    print(f"Market proxy basket: {', '.join(MARKET_PROXY_TICKERS)}")
    print(f"Sector proxy basket: {', '.join(SECTOR_PROXY_TICKERS)}")
    print("Point-in-time classification source: Massive Ticker Overview SIC probe")
    print("Ticker-to-sector mapping: NOT YET LOCKED; no guessed crosswalk")
    print("Market/sector/ticker regime labels: NOT YET LOCKED")
    print("Phase 09 regime evidence foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
