from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.identity_probe import (
    ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION,
    MLHistoricalIdentityProbe,
)
from packages.ml.reuse_audit import (
    ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION,
    MLTickerReuseAudit,
)
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
    assert ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION == (
        "ml-historical-identity-probe-v1-authority-unique-reference-structural-eligibility"
    )
    assert ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION == (
        "ml-ticker-reuse-audit-v1-stable-vs-weak-identity-authority-enrichment"
    )
    assert ML_HISTORY_ORIGIN_DATE == date(2021, 8, 16)
    assert ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS == 250_000.0
    assert ML_LONG_GAP_CALENDAR_DAYS == 30
    assert len(CORE_FEATURE_REGISTRY.all()) == 33

    settings = load_settings(PROJECT_ROOT, "development")
    sample_date = date(2026, 8, 14)
    universe_report = MLTrainingUniverseProbe(settings).report_path(sample_date)
    identity_report = MLHistoricalIdentityProbe(settings).report_path(sample_date)
    reuse_report = MLTickerReuseAudit(settings).report_path(sample_date)
    assert "ml" in universe_report.parts and "training_universe_probe" in universe_report.parts
    assert "ml" in identity_report.parts and "historical_identity_probe" in identity_report.parts
    assert "ml" in reuse_report.parts and "ticker_reuse_audit" in reuse_report.parts
    assert len({universe_report, identity_report, reuse_report}) == 3

    print(f"ML training-universe probe contract: {ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION}")
    print(f"ML historical-identity probe contract: {ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION}")
    print(f"ML ticker-reuse audit contract: {ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION}")
    print(f"Phase 10 gate count: {PHASE10_GATE_COUNT}")
    print(f"ML history origin: {ML_HISTORY_ORIGIN_DATE}")
    print(f"Core quantitative feature count: {len(CORE_FEATURE_REGISTRY.all())}")
    print(f"Candidate activity audit floor: ${ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS:,.0f} daily dollar volume")
    print("Current Phase 07/08 snapshot as historical ML population: REJECTED")
    print("Historical population basis: OBSERVATION-DRIVEN / CURRENT ROUTE NOT USED")
    print("Historical provider-native ticker case: EXACT / CASE-SENSITIVE")
    print("Historical ticker-text splicing: FORBIDDEN")
    print("Current active/delisted status as retrospective eligibility: FORBIDDEN")
    print("Gate 1 historical training-universe audit: ACCEPTED; survivorship/selection gap measured")
    print("Gate 2 historical identity/eligibility evidence: CURRENT")
    print("Gate 2 unresolved ticker reuse composition: CURRENT SUB-AUDIT")
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
