from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from packages.core.enums import Timeframe
from packages.features.engine import compute_core_features
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.materialization import ACTIVE_FEATURE_PERSISTENCE_POLICY
from packages.features.momentum import rsi_wilder
from packages.features.partition_store import feature_dependency_fingerprint
from packages.features.volatility import atr_wilder


def main() -> int:
    closes = pd.Series(
        [
            44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10,
            45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28,
            46.28, 46.00, 46.03, 46.41, 46.22, 45.64, 46.21,
        ]
    )
    rsi = rsi_wilder(closes, 14)
    if not np.isclose(rsi.iloc[14], 70.46413502109705, atol=1e-12, rtol=0.0):
        raise RuntimeError("Wilder RSI reference-vector validation failed")

    high = pd.Series([10.0, 12.0, 13.0, 14.0])
    low = pd.Series([8.0, 9.0, 11.0, 10.0])
    close = pd.Series([9.0, 11.0, 12.0, 13.0])
    atr = atr_wilder(high, low, close, 3)
    if not np.isclose(atr.iloc[3], 26.0 / 9.0, atol=1e-12, rtol=0.0):
        raise RuntimeError("Wilder ATR reference-vector validation failed")

    timestamps = pd.date_range("2026-08-14 13:30:00+00:00", periods=25, freq="min")
    rows: list[dict[str, object]] = []
    for symbol, base in (("TPC", 100.0), ("TpC", 10.0)):
        for offset, timestamp in enumerate(timestamps):
            price = base + offset
            rows.append(
                {
                    "symbol": symbol,
                    "timestamp_utc": timestamp,
                    "high": price + 1.0,
                    "low": price - 1.0,
                    "close": price,
                    "volume": 1000.0 + offset,
                }
            )
    output = compute_core_features(pd.DataFrame(rows))
    if output["symbol"].drop_duplicates().tolist() != ["TPC", "TpC"]:
        raise RuntimeError("Feature engine violated provider-native ticker case")
    if output.attrs.get("feature_contract_version") != CORE_FEATURE_CONTRACT_VERSION:
        raise RuntimeError("Feature engine did not publish its contract version")
    if output.attrs.get("feature_registry_fingerprint") != CORE_FEATURE_REGISTRY.fingerprint():
        raise RuntimeError("Feature engine registry fingerprint mismatch")

    policy = ACTIVE_FEATURE_PERSISTENCE_POLICY
    for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1):
        if policy.tier_for(timeframe) != "permanent":
            raise RuntimeError(f"{timeframe.value} measured feature persistence tier mismatch")
    if policy.benchmark_candidates:
        raise RuntimeError("all Phase 6 persistence benchmark candidates should be resolved")
    if policy.tier_for(Timeframe.MINUTE_15) != "on_demand":
        raise RuntimeError("15m should remain on-demand/cache")
    if policy.tier_for(Timeframe.MINUTE_1) != "current_state_only":
        raise RuntimeError("1m should remain current-state-only")

    source_sha = "a" * 64
    dependency_a = feature_dependency_fingerprint(
        source_sha256=source_sha,
        input_state_fingerprint="state-a",
    )
    dependency_b = feature_dependency_fingerprint(
        source_sha256=source_sha,
        input_state_fingerprint="state-b",
    )
    if dependency_a == dependency_b:
        raise RuntimeError("feature partition fingerprint ignored incoming recursive state")

    print(f"NumPy: {np.__version__}")
    print(f"pandas: {pd.__version__}")
    print(f"Feature contract: {CORE_FEATURE_CONTRACT_VERSION}")
    print(f"Registered core features: {len(CORE_FEATURE_REGISTRY.all())}")
    print(f"Registry fingerprint: {CORE_FEATURE_REGISTRY.fingerprint()}")
    print("Wilder RSI reference vector: PASS")
    print("Wilder ATR reference vector: PASS")
    print("Provider-native ticker separation: PASS")
    print("Measured persistence tiers: PASS (1d, 4h, 1h permanent)")
    print("State-dependent partition fingerprint: PASS")
    print("Phase 06 feature foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
