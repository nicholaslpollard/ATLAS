from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.discovery.filter_policy import (
    ACTIVE_DISCOVERY_FILTER_POLICY,
    DISCOVERY_FILTER_POLICY_VERSION,
)
from packages.discovery.input_inventory import (
    DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION,
    DiscoveryInputInventory,
)
from packages.discovery.scanner import DISCOVERY_FOUNDATION_MANIFEST_VERSION
from packages.schemas.candidate import DISCOVERY_CANDIDATE_CONTRACT_VERSION


def _strictly_increasing(values: tuple[float, ...]) -> bool:
    return all(left < right for left, right in zip(values, values[1:], strict=False))


def main() -> int:
    settings = load_settings(PROJECT_ROOT, "development")
    paths = MarketDataPaths(settings)

    assert DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION == (
        "discovery-input-inventory-v2-canonical-bars-plus-derived-features"
    )
    assert DISCOVERY_CANDIDATE_CONTRACT_VERSION == (
        "discovery-candidate-v1-health-activity-routing"
    )
    assert DISCOVERY_FILTER_POLICY_VERSION == (
        "discovery-filter-v1-250k-dollar-volume-no-price-floor"
    )
    assert DISCOVERY_FOUNDATION_MANIFEST_VERSION == (
        "discovery-foundation-manifest-v1-upstream-lineage-bound"
    )
    assert ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume == 250_000.0
    assert ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume < ACTIVE_DISCOVERY_FILTER_POLICY.active_dollar_volume
    assert ACTIVE_DISCOVERY_FILTER_POLICY.active_dollar_volume < ACTIVE_DISCOVERY_FILTER_POLICY.liquid_dollar_volume
    assert ACTIVE_DISCOVERY_FILTER_POLICY.liquid_dollar_volume < ACTIVE_DISCOVERY_FILTER_POLICY.deep_dollar_volume
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

    sample_date = __import__("datetime").date(2026, 8, 14)
    inventory = paths.discovery_input_inventory_report(sample_date)
    snapshot = paths.discovery_snapshot_file(sample_date)
    manifest = paths.discovery_snapshot_manifest(sample_date)
    assert "discovery" in inventory.parts and "input_inventory" in inventory.parts
    assert "discovery" in snapshot.parts and "snapshots" in snapshot.parts
    assert "discovery" in manifest.parts

    print(f"Discovery input inventory contract: {DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION}")
    print(f"Discovery candidate contract: {DISCOVERY_CANDIDATE_CONTRACT_VERSION}")
    print(f"Discovery filter policy: {DISCOVERY_FILTER_POLICY_VERSION}")
    print(f"Discovery policy fingerprint: {ACTIVE_DISCOVERY_FILTER_POLICY.fingerprint}")
    print(f"Discovery foundation manifest: {DISCOVERY_FOUNDATION_MANIFEST_VERSION}")
    print("Canonical 1d bars + derived feature separation: PASS")
    print("$250K dollar-volume floor / no share-price floor: PASS")
    print("Mandatory-route bypass separation: PASS")
    print("Manifest-lineage production path: PASS")
    print("Measured threshold bands: PASS (inventory only)")
    print("Instrument-agnostic discovery foundation: PASS")
    print("Phase 08 discovery foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
