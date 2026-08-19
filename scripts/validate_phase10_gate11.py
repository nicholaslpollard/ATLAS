from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.ml.calibration_policy import (
    ML_CALIBRATION_ACCEPTED_METHOD,
    ML_CALIBRATION_ACCEPTED_MODEL,
    ML_CALIBRATION_ACCEPTED_OOS_ROWS,
    ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED,
    ML_CALIBRATION_POLICY_ACCEPTED,
    ML_CALIBRATION_POLICY_CONTRACT_VERSION,
    ML_CALIBRATION_POSTHOC_ENABLED,
)
from packages.ml.robustness_audit import (
    ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION,
    ML_ROBUSTNESS_AUDIT_STATUS,
    ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED,
    ML_ROBUSTNESS_MIN_SUPPORTED_FOLDS,
    ML_ROBUSTNESS_MIN_SUPPORTED_ROWS,
    ML_ROBUSTNESS_SEGMENT_FAMILIES,
    ML_ROBUSTNESS_SOURCE_PROBABILITIES,
    ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS,
)
from packages.ml.walk_forward_policy import ML_WALK_FORWARD_FINAL_HOLDOUT_START


def main() -> int:
    assert ML_CALIBRATION_POLICY_ACCEPTED is True
    assert ML_CALIBRATION_POLICY_CONTRACT_VERSION == (
        "ml-calibration-policy-v1-raw-no-posthoc-calibration"
    )
    assert ML_CALIBRATION_ACCEPTED_METHOD == "raw"
    assert ML_CALIBRATION_POSTHOC_ENABLED is False
    assert ML_CALIBRATION_ACCEPTED_MODEL == "hgb_leaf15_iter100"
    assert ML_CALIBRATION_ACCEPTED_OOS_ROWS == 3_978_577
    assert ML_CALIBRATION_FINAL_HOLDOUT_ACCESSED is False

    assert ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION == (
        "ml-robustness-audit-v1-raw-hgb-oos-market-liquidity-volatility-direction-time"
    )
    assert ML_ROBUSTNESS_AUDIT_STATUS == "EVIDENCE_ONLY"
    assert ML_ROBUSTNESS_SOURCE_PROBABILITIES == "GATE9_RAW_TEST_ARTIFACTS"
    assert ML_ROBUSTNESS_MIN_SUPPORTED_ROWS == 25_000
    assert ML_ROBUSTNESS_MIN_SUPPORTED_FOLDS == 2
    assert ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED is False
    assert ML_WALK_FORWARD_FINAL_HOLDOUT_START == "2026-05-12"
    assert ML_ROBUSTNESS_SEGMENT_FAMILIES == (
        "market_regime_composite",
        "market_regime_structure",
        "market_regime_momentum",
        "market_regime_volatility",
        "market_regime_efficiency",
        "market_regime_participation",
        "liquidity_bucket",
        "volatility_bucket",
        "predicted_class",
        "actual_class",
        "confidence_bucket",
        "calendar_year",
    )
    assert ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS == (
        "sector_regime",
        "ticker_regime",
        "risk_mode",
        "security_type",
    )

    print(f"ML Gate 10 calibration policy: {ML_CALIBRATION_POLICY_CONTRACT_VERSION}")
    print(
        "ML Gate 10 accepted probability output: "
        f"model={ML_CALIBRATION_ACCEPTED_MODEL} / method={ML_CALIBRATION_ACCEPTED_METHOD} / "
        f"posthoc={ML_CALIBRATION_POSTHOC_ENABLED}"
    )
    print(f"ML Gate 10 accepted OOS rows: {ML_CALIBRATION_ACCEPTED_OOS_ROWS:,}")
    print(f"ML Gate 11 robustness audit: {ML_ROBUSTNESS_AUDIT_CONTRACT_VERSION}")
    print(f"ML Gate 11 segment families: {ML_ROBUSTNESS_SEGMENT_FAMILIES}")
    print(f"ML Gate 11 unavailable snapshot-only segments: {ML_ROBUSTNESS_UNAVAILABLE_SEGMENTS}")
    print(
        "ML Gate 11 support rule: "
        f"rows>={ML_ROBUSTNESS_MIN_SUPPORTED_ROWS:,} / folds>={ML_ROBUSTNESS_MIN_SUPPORTED_FOLDS}"
    )
    print(
        "ML Gate 11 final holdout: "
        f"start={ML_WALK_FORWARD_FINAL_HOLDOUT_START} / accessed={ML_ROBUSTNESS_FINAL_HOLDOUT_ACCESSED}"
    )
    print("ML Gate 10 probability calibration policy: ACCEPTED; raw/no-posthoc selected")
    print("ML Gate 11 regime/segment robustness: CURRENT; target-machine audit not yet run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
