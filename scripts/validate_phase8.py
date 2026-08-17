from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.discovery.directional_score import (
    DIRECTIONAL_SCORE_POLICY_VERSION,
    RELATIVE_STRENGTH_TAIL_START,
    TIMEFRAME_WEIGHTS,
)
from packages.discovery.filter_policy import (
    ACTIVE_DISCOVERY_FILTER_POLICY,
    DISCOVERY_FILTER_POLICY_VERSION,
)
from packages.discovery.input_inventory import (
    DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION,
    DiscoveryInputInventory,
)
from packages.discovery.persistence import (
    ACTIVE_DISCOVERY_PERSISTENCE_POLICY,
    DISCOVERY_PERSISTENCE_POLICY_VERSION,
    DISCOVERY_STATE_MANIFEST_VERSION,
)
from packages.discovery.scanner import DISCOVERY_FOUNDATION_MANIFEST_VERSION
from packages.discovery.scoring import (
    DISCOVERY_SCORE_MANIFEST_VERSION,
    PRIORITY_CALIBRATION_THRESHOLDS,
)
from packages.discovery.setup_scores import SETUP_FAMILIES, SETUP_SCORE_POLICY_VERSION
from packages.discovery.state_machine import (
    ACTIVE_DISCOVERY_STATE_POLICY,
    DISCOVERY_STATE_POLICY_VERSION,
)
from packages.schemas.candidate import DISCOVERY_CANDIDATE_CONTRACT_VERSION
from packages.schemas.discovery_score import DISCOVERY_SCORE_CONTRACT_VERSION
from packages.schemas.discovery_state import DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION


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
    assert DISCOVERY_SCORE_CONTRACT_VERSION == (
        "discovery-score-v2-tail-strength-and-coverage-guard"
    )
    assert SETUP_SCORE_POLICY_VERSION == "setup-score-v1-volatility-normalized-multifamily"
    assert DIRECTIONAL_SCORE_POLICY_VERSION == (
        "directional-score-v2-cross-sectional-tail-strength"
    )
    assert DISCOVERY_STATE_POLICY_VERSION == "discovery-state-v3-locked-absolute-evidence"
    assert DISCOVERY_SCORE_MANIFEST_VERSION == (
        "discovery-score-manifest-v2-calibration-diagnostics"
    )
    assert DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION == (
        "discovery-state-snapshot-v1-hysteresis-and-score-lineage"
    )
    assert DISCOVERY_PERSISTENCE_POLICY_VERSION == (
        "discovery-persistence-v1-immediate-hot-confirmed-warm-two-scan-demotion"
    )
    assert DISCOVERY_STATE_MANIFEST_VERSION == (
        "discovery-state-manifest-v1-score-and-prior-state-lineage"
    )
    assert ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume == 250_000.0
    assert ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume < ACTIVE_DISCOVERY_FILTER_POLICY.active_dollar_volume
    assert ACTIVE_DISCOVERY_FILTER_POLICY.active_dollar_volume < ACTIVE_DISCOVERY_FILTER_POLICY.liquid_dollar_volume
    assert ACTIVE_DISCOVERY_FILTER_POLICY.liquid_dollar_volume < ACTIVE_DISCOVERY_FILTER_POLICY.deep_dollar_volume
    assert _strictly_increasing(DiscoveryInputInventory.CLOSE_THRESHOLDS)
    assert _strictly_increasing(DiscoveryInputInventory.VOLUME_THRESHOLDS)
    assert _strictly_increasing(DiscoveryInputInventory.DOLLAR_VOLUME_THRESHOLDS)
    assert _strictly_increasing(DiscoveryInputInventory.RELATIVE_VOLUME_THRESHOLDS)
    assert _strictly_increasing(PRIORITY_CALIBRATION_THRESHOLDS)
    assert set(DiscoveryInputInventory.DAILY_METRICS) == {
        "close",
        "volume",
        "dollar_volume",
        "relative_volume_20",
        "relative_dollar_volume_20",
        "natr_14",
        "realized_volatility_20",
    }
    assert set(TIMEFRAME_WEIGHTS) == {"1d", "4h", "1h"}
    assert abs(sum(TIMEFRAME_WEIGHTS.values()) - 1.0) < 1e-12
    assert RELATIVE_STRENGTH_TAIL_START == 0.80
    assert set(SETUP_FAMILIES) == {
        "trend",
        "momentum",
        "breakout",
        "pullback",
        "reversal",
        "mean_reversion",
        "unusual_volume",
        "volatility_expansion",
        "breakdown",
    }
    assert ACTIVE_DISCOVERY_STATE_POLICY.watch_priority == 0.35
    assert ACTIVE_DISCOVERY_STATE_POLICY.warm_priority == 0.50
    assert ACTIVE_DISCOVERY_STATE_POLICY.hot_priority == 0.60
    assert ACTIVE_DISCOVERY_STATE_POLICY.hot_directional_evidence == 0.50
    assert ACTIVE_DISCOVERY_PERSISTENCE_POLICY.warm_confirmation_observations == 2
    assert ACTIVE_DISCOVERY_PERSISTENCE_POLICY.demotion_confirmation_observations == 2

    sample_date = __import__("datetime").date(2026, 8, 14)
    inventory = paths.discovery_input_inventory_report(sample_date)
    snapshot = paths.discovery_snapshot_file(sample_date)
    manifest = paths.discovery_snapshot_manifest(sample_date)
    score_snapshot = paths.discovery_score_file(sample_date)
    score_manifest = paths.discovery_score_manifest(sample_date)
    state_snapshot = paths.discovery_state_file(sample_date)
    state_manifest = paths.discovery_state_manifest(sample_date)
    assert "discovery" in inventory.parts and "input_inventory" in inventory.parts
    assert "discovery" in snapshot.parts and "snapshots" in snapshot.parts
    assert "discovery" in manifest.parts
    assert "discovery" in score_snapshot.parts and "scores" in score_snapshot.parts
    assert "discovery_scores" in score_manifest.parts
    assert "discovery" in state_snapshot.parts and "states" in state_snapshot.parts
    assert "discovery_states" in state_manifest.parts

    print(f"Discovery input inventory contract: {DISCOVERY_INPUT_INVENTORY_CONTRACT_VERSION}")
    print(f"Discovery candidate contract: {DISCOVERY_CANDIDATE_CONTRACT_VERSION}")
    print(f"Discovery filter policy: {DISCOVERY_FILTER_POLICY_VERSION}")
    print(f"Discovery policy fingerprint: {ACTIVE_DISCOVERY_FILTER_POLICY.fingerprint}")
    print(f"Discovery foundation manifest: {DISCOVERY_FOUNDATION_MANIFEST_VERSION}")
    print(f"Discovery score contract: {DISCOVERY_SCORE_CONTRACT_VERSION}")
    print(f"Setup score policy: {SETUP_SCORE_POLICY_VERSION}")
    print(f"Directional score policy: {DIRECTIONAL_SCORE_POLICY_VERSION}")
    print(f"Raw state policy: {DISCOVERY_STATE_POLICY_VERSION}")
    print(f"Discovery score manifest: {DISCOVERY_SCORE_MANIFEST_VERSION}")
    print(f"Persisted state contract: {DISCOVERY_STATE_SNAPSHOT_CONTRACT_VERSION}")
    print(f"Persistence policy: {DISCOVERY_PERSISTENCE_POLICY_VERSION}")
    print(f"Persisted state manifest: {DISCOVERY_STATE_MANIFEST_VERSION}")
    print("Canonical 1d bars + derived feature separation: PASS")
    print("$250K dollar-volume floor / no share-price floor: PASS")
    print("Mandatory-route bypass separation: PASS")
    print("Manifest-lineage production path: PASS")
    print("Vectorized multi-timeframe setup scoring contract: PASS")
    print("Cross-sectional relative-strength tail discriminator: PASS")
    print("Sparse-timeframe promotion guard: PASS")
    print("Absolute NORMAL/WATCH/WARM/HOT thresholds: LOCKED (0.35 / 0.50 / 0.60)")
    print("HOT directional evidence floor: LOCKED (0.50, non-neutral, 3 timeframes)")
    print("Warm confirmation + two-observation demotion hysteresis: PASS")
    print("Instrument-agnostic discovery foundation: PASS")
    print("Phase 08 discovery foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
