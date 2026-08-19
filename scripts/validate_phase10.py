from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.universe_probe import (
    ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS,
    ML_HISTORY_ORIGIN_DATE,
    ML_LONG_GAP_CALENDAR_DAYS,
    ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION,
    MLTrainingUniverseProbe,
)


PHASE10_GATE_COUNT = 13


def main() -> int:
    assert PHASE10_GATE_COUNT == 13
    assert ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION == (
        "ml-training-universe-probe-v1-historical-observation-survivorship-identity-audit"
    )
    assert ML_HISTORY_ORIGIN_DATE == date(2021, 8, 16)
    assert ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS == 250_000.0
    assert ML_LONG_GAP_CALENDAR_DAYS == 30
    assert len(CORE_FEATURE_REGISTRY.all()) == 33

    report = MLTrainingUniverseProbe(
        __import__("packages.core.settings", fromlist=["load_settings"]).load_settings(
            PROJECT_ROOT, "development"
        )
    ).report_path(date(2026, 8, 14))
    assert "ml" in report.parts and "training_universe_probe" in report.parts

    print(f"ML training-universe probe contract: {ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION}")
    print(f"Phase 10 gate count: {PHASE10_GATE_COUNT}")
    print(f"ML history origin: {ML_HISTORY_ORIGIN_DATE}")
    print(f"Core quantitative feature count: {len(CORE_FEATURE_REGISTRY.all())}")
    print(f"Candidate activity audit floor: ${ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS:,.0f} daily dollar volume")
    print("Current Phase 07/08 snapshot as historical ML population: NOT ASSUMED SAFE")
    print("Historical provider-native ticker case: EXACT / CASE-SENSITIVE")
    print("Historical ticker-text splicing: FORBIDDEN")
    print("Gate 1 historical training-universe audit: CURRENT")
    print("Gate 2 historical identity/eligibility policy: NOT YET LOCKED")
    print("Gate 3 outcome-label feasibility: NOT YET MEASURED")
    print("Gate 4 prediction-label policy: NOT YET LOCKED")
    print("Gate 5 point-in-time ML feature/leakage contract: NOT YET LOCKED")
    print("Gate 6 training-dataset materialization: NOT YET BUILT")
    print("Gate 7 walk-forward/embargo policy: NOT YET LOCKED")
    print("Gate 8 baseline probability models: NOT YET TRAINED")
    print("Gate 9 candidate model benchmark: NOT YET RUN")
    print("Gate 10 probability calibration policy: NOT YET LOCKED")
    print("Gate 11 segment/regime robustness: NOT YET VALIDATED")
    print("Gate 12 model registry + immutable prediction contract: NOT YET BUILT")
    print("Gate 13 final reproducibility/leakage/OOS validation: NOT YET RUN")
    print("Phase 10 model selection: NONE")
    print("Phase 10 ML evidence foundation: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
