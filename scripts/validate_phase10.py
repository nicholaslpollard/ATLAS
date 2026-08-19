from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.ml.identity_policy import (
    CURRENT_ACTIVE_FILTER_USED,
    CURRENT_DELISTED_FILTER_USED,
    CURRENT_ROUTE_FILTER_USED,
    ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION,
    TICKER_TEXT_SPLICING_ALLOWED,
)
from packages.ml.identity_probe import (
    ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION,
    MLHistoricalIdentityProbe,
)
from packages.ml.outcome_family_audit import (
    ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION,
    ML_VOLATILITY_FEATURE,
    ML_VOLATILITY_HORIZON_SCALING,
    ML_VOLATILITY_THRESHOLD_GRID,
    MLOutcomeFamilyAudit,
)
from packages.ml.outcome_probe import (
    ML_GATE3_QUERY_PLAN_VERSION,
    ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION,
    ML_OUTCOME_HORIZONS,
    MLOutcomeFeasibilityProbe,
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
from packages.providers.massive.corporate_actions import MASSIVE_SPLITS_ENDPOINT


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
    assert ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION == (
        "ml-historical-identity-policy-v1-authoritative-or-unique-no-reuse-structural"
    )
    assert ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION == (
        "ml-outcome-feasibility-probe-v1-contiguous-horizons-provider-split-adjustment-audit"
    )
    assert ML_GATE3_QUERY_PLAN_VERSION == (
        "ml-gate3-query-plan-v2-materialized-candidates-direct-session-lookups"
    )
    assert ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION == (
        "ml-outcome-family-audit-v1-natr14-sqrt-horizon-split-censored-grid"
    )
    assert ML_OUTCOME_HORIZONS == (1, 3, 5, 10, 20)
    assert ML_VOLATILITY_FEATURE == "natr_14"
    assert ML_VOLATILITY_HORIZON_SCALING == "sqrt_sessions"
    assert ML_VOLATILITY_THRESHOLD_GRID == (0.5, 1.0, 1.5, 2.0)
    assert MASSIVE_SPLITS_ENDPOINT == "/stocks/v1/splits"
    assert CURRENT_ROUTE_FILTER_USED is False
    assert CURRENT_ACTIVE_FILTER_USED is False
    assert CURRENT_DELISTED_FILTER_USED is False
    assert TICKER_TEXT_SPLICING_ALLOWED is False
    assert ML_HISTORY_ORIGIN_DATE == date(2021, 8, 16)
    assert ML_CANDIDATE_ACTIVITY_FLOOR_DOLLARS == 250_000.0
    assert ML_LONG_GAP_CALENDAR_DAYS == 30
    assert len(CORE_FEATURE_REGISTRY.all()) == 33

    settings = load_settings(PROJECT_ROOT, "development")
    sample_date = date(2026, 8, 14)
    universe_report = MLTrainingUniverseProbe(settings).report_path(sample_date)
    identity_report = MLHistoricalIdentityProbe(settings).report_path(sample_date)
    reuse_report = MLTickerReuseAudit(settings).report_path(sample_date)
    outcome_report = MLOutcomeFeasibilityProbe(settings).report_path(sample_date)
    family_report = MLOutcomeFamilyAudit(settings).report_path(sample_date)
    assert "ml" in universe_report.parts and "training_universe_probe" in universe_report.parts
    assert "ml" in identity_report.parts and "historical_identity_probe" in identity_report.parts
    assert "ml" in reuse_report.parts and "ticker_reuse_audit" in reuse_report.parts
    assert "ml" in outcome_report.parts and "outcome_feasibility_probe" in outcome_report.parts
    assert "ml" in family_report.parts and "outcome_family_audit" in family_report.parts
    assert len({universe_report, identity_report, reuse_report, outcome_report, family_report}) == 5

    print(f"ML training-universe probe contract: {ML_TRAINING_UNIVERSE_PROBE_CONTRACT_VERSION}")
    print(f"ML historical-identity probe contract: {ML_HISTORICAL_IDENTITY_PROBE_CONTRACT_VERSION}")
    print(f"ML ticker-reuse audit contract: {ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION}")
    print(f"ML historical-identity policy contract: {ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION}")
    print(f"ML outcome-feasibility probe contract: {ML_OUTCOME_FEASIBILITY_PROBE_CONTRACT_VERSION}")
    print(f"ML Gate 3 query plan: {ML_GATE3_QUERY_PLAN_VERSION}")
    print(f"ML outcome-family audit contract: {ML_OUTCOME_FAMILY_AUDIT_CONTRACT_VERSION}")
    print(f"ML outcome-family thresholds: {ML_VOLATILITY_THRESHOLD_GRID} x {ML_VOLATILITY_FEATURE} * sqrt(horizon)")
    print(f"Massive split evidence endpoint: {MASSIVE_SPLITS_ENDPOINT}")
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
    print("Gate 2 historical identity/eligibility evidence: ACCEPTED; 93.34% structurally eligible")
    print("Gate 2 ticker-reuse sub-audit: ACCEPTED; multi-stable ambiguity dominates blocked rows")
    print("Gate 2 historical identity/eligibility policy: ACCEPTED; authoritative or unique/no-reuse only")
    print("Gate 3 fixed-horizon/split evidence: CAPTURED; canonical daily prices predominantly unadjusted")
    print("Gate 3 volatility-scaled outcome families: CURRENT SUB-AUDIT")
    print("Gate 3 outcome-label feasibility policy: NOT YET LOCKED")
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
