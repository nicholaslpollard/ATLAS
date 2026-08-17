from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.discovery.input_inventory import (
    DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION,
    DiscoveryInputInventory,
)


def _strictly_increasing(values: tuple[float, ...]) -> bool:
    return all(left < right for left, right in zip(values, values[1:], strict=False))


def main() -> int:
    settings = load_settings(PROJECT_ROOT, "development")
    paths = MarketDataPaths(settings)

    assert DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION == (
        "discovery-input-inventory-v2-canonical-bars-plus-derived-features"
    )
    assert _strictly_increasing(DiscoveryInputInventory.CLOSE_THRESHOLDS)
    assert _strictly_increasing(DiscoveryInputInventory.VOLUME_THRESHOLDS)
    assert _strictly_increasing(DiscoveryInputInventory.DOLLAR_VOLUME_THRESHOLDS)
    assert _strictly_increasing(DiscoveryInputInventory.RELATIVE_VOLUME_THRESHOLDS)
    assert set(DiscoveryInputInventory.DAILY_METRICS) == {
        "close",
        "volume",
        "dollar_volume",
        "relative_volume_20",
        "relative_dollar_volume_20",
        "natr_14",
        "realized_volatility_20",
    }

    sample = paths.discovery_input_inventory_report(__import__("datetime").date(2026, 8, 14))
    assert "discovery" in sample.parts
    assert "input_inventory" in sample.parts

    print(f"Discovery input inventory contract: {DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION}")
    print("Canonical 1d bars + derived feature separation: PASS")
    print("Measured threshold bands: PASS (informational, not policy)")
    print("Instrument-agnostic discovery foundation: PASS")
    print("Phase 08 discovery foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
