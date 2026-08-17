from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.regimes.calibration import (
    REGIME_CALIBRATION_CONTRACT_VERSION,
    REGIME_CALIBRATION_QUANTILES,
)
from packages.regimes.classification_probe import REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION
from packages.regimes.input_inventory import (
    CLASSIFICATION_FIELD_CANDIDATES,
    MARKET_PROXY_TICKERS,
    REGIME_INPUT_INVENTORY_CONTRACT_VERSION,
    SECTOR_PROXY_TICKERS,
)
from packages.regimes.persistence_probe import (
    REGIME_PERSISTENCE_CONFIRMATION_WINDOWS,
    REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION,
)
from packages.regimes.policy_probe import REGIME_POLICY_PROBE_CONTRACT_VERSION


def main() -> int:
    assert REGIME_INPUT_INVENTORY_CONTRACT_VERSION == (
        "regime-input-inventory-v1-local-breadth-benchmark-sector-proxy-audit"
    )
    assert REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION == (
        "regime-classification-probe-v1-massive-sic-point-in-time"
    )
    assert REGIME_CALIBRATION_CONTRACT_VERSION == (
        "regime-calibration-v2-historical-continuous-proxy-distributions"
    )
    assert REGIME_POLICY_PROBE_CONTRACT_VERSION == (
        "regime-policy-probe-v1-quartile-dimensional-no-hysteresis"
    )
    assert REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION == (
        "regime-persistence-probe-v1-dimension-confirmation-grid"
    )
    assert REGIME_PERSISTENCE_CONFIRMATION_WINDOWS == (2, 3)
    assert REGIME_CALIBRATION_QUANTILES == (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
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
    classification_probe = paths.regime_classification_probe_report(sample_date)
    calibration = paths.regime_calibration_report(sample_date)
    policy_probe = paths.regime_policy_probe_report(sample_date)
    persistence_probe = paths.regime_persistence_probe_report(sample_date)
    assert "regimes" in inventory.parts and "input_inventory" in inventory.parts
    assert "regimes" in classification_probe.parts and "classification_probe" in classification_probe.parts
    assert "regimes" in calibration.parts and "calibration" in calibration.parts
    assert "regimes" in policy_probe.parts and "policy_probe" in policy_probe.parts
    assert "regimes" in persistence_probe.parts and "persistence_probe" in persistence_probe.parts
    assert len({inventory, classification_probe, calibration, policy_probe, persistence_probe}) == 5

    print(f"Regime input inventory contract: {REGIME_INPUT_INVENTORY_CONTRACT_VERSION}")
    print(f"Classification probe contract: {REGIME_CLASSIFICATION_PROBE_CONTRACT_VERSION}")
    print(f"Calibration contract: {REGIME_CALIBRATION_CONTRACT_VERSION}")
    print(f"Candidate policy probe contract: {REGIME_POLICY_PROBE_CONTRACT_VERSION}")
    print(f"Persistence probe contract: {REGIME_PERSISTENCE_PROBE_CONTRACT_VERSION}")
    print(f"Persistence confirmation grid: {', '.join(str(v) for v in REGIME_PERSISTENCE_CONFIRMATION_WINDOWS)} sessions")
    print(f"Market proxy basket: {', '.join(MARKET_PROXY_TICKERS)}")
    print(f"Sector proxy basket: {', '.join(SECTOR_PROXY_TICKERS)}")
    print("Point-in-time classification source: Massive Ticker Overview SIC industry facts")
    print("SIC-to-sector/GICS mapping: NOT LOCKED; no guessed crosswalk")
    print("Historical calibration evidence: ACCEPTED FOR POLICY PROBING")
    print("Continuous proxy trend evidence: EMA20 distance + EMA20 slope")
    print("Raw policy stability evidence: CHATTER OBSERVED; persistence comparison required")
    print("Persistence policy status: DIAGNOSTIC ONLY; 2-session vs 3-session confirmation")
    print("Point-in-time production thresholds: STILL REQUIRED AFTER PERSISTENCE SELECTION")
    print("Production market/sector/ticker regime policy: NOT YET LOCKED")
    print("Phase 09 regime evidence foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
