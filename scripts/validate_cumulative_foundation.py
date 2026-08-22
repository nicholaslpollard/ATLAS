from __future__ import annotations

from packages.data.alpaca_backfill_policy import (
    ALPACA_BACKFILL_END,
    ALPACA_BACKFILL_START,
    ALPACA_MASSIVE_SEAM_START,
)
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.regimes.split_origin_policy import (
    INTRADAY_POLICY,
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    TICKER_HISTORY_ORIGIN_DATE,
)
from packages.validation.cumulative_acceptance import CUMULATIVE_FOUNDATION_VALIDATION_VERSION
from packages.validation.cumulative_policy import (
    CUMULATIVE_ANOMALY_THRESHOLDS_POSTHOC_FORBIDDEN,
    CUMULATIVE_AUDIT_BROKER_WRITES,
    CUMULATIVE_AUDIT_CANONICAL_WRITES,
    CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS,
    CUMULATIVE_AUDIT_FEATURE_WRITES,
    CUMULATIVE_AUDIT_MODEL_WRITES,
    CUMULATIVE_AUDIT_REGIME_WRITES,
    CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION,
    CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION,
    CUMULATIVE_STATISTICAL_DIAGNOSTICS_ARE_NONAUTHORITATIVE,
    cumulative_policy_fingerprint,
    validate_cumulative_policy,
)


def main() -> None:
    validate_cumulative_policy()
    checks = {
        "history_starts_2016_01_04": str(ALPACA_BACKFILL_START) == "2016-01-04",
        "alpaca_preseam_authority_locked": str(ALPACA_BACKFILL_END) == "2021-08-15",
        "massive_authority_starts_2021_08_16": str(ALPACA_MASSIVE_SEAM_START) == "2021-08-16",
        "market_sector_regime_origin_2016": MARKET_SECTOR_HISTORY_ORIGIN_DATE == ALPACA_BACKFILL_START,
        "ticker_regime_origin_massive": TICKER_HISTORY_ORIGIN_DATE == ALPACA_MASSIVE_SEAM_START,
        "no_synthetic_pre2021_intraday": INTRADAY_POLICY
        == "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL",
        "core_feature_count_exact_33": len(CORE_FEATURE_REGISTRY.all()) == 33,
        "canonical_writes_zero": CUMULATIVE_AUDIT_CANONICAL_WRITES == 0,
        "feature_writes_zero": CUMULATIVE_AUDIT_FEATURE_WRITES == 0,
        "regime_writes_zero": CUMULATIVE_AUDIT_REGIME_WRITES == 0,
        "model_writes_zero": CUMULATIVE_AUDIT_MODEL_WRITES == 0,
        "broker_writes_zero": CUMULATIVE_AUDIT_BROKER_WRITES == 0,
        "external_provider_calls_zero": CUMULATIVE_AUDIT_EXTERNAL_PROVIDER_CALLS == 0,
        "statistical_diagnostics_nonauthoritative": CUMULATIVE_STATISTICAL_DIAGNOSTICS_ARE_NONAUTHORITATIVE,
        "posthoc_anomaly_thresholds_forbidden": CUMULATIVE_ANOMALY_THRESHOLDS_POSTHOC_FORBIDDEN,
        "policy_fingerprint_present": len(cumulative_policy_fingerprint()) == 64,
    }
    print(f"Cumulative audit contract: {CUMULATIVE_FOUNDATION_AUDIT_CONTRACT_VERSION}")
    print(f"Cumulative acceptance contract: {CUMULATIVE_FOUNDATION_ACCEPTANCE_VERSION}")
    print(f"Cumulative independent validation contract: {CUMULATIVE_FOUNDATION_VALIDATION_VERSION}")
    print(f"Cumulative audit policy fingerprint: {cumulative_policy_fingerprint()}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Cumulative foundation static validation failed: " + ", ".join(failed))
    print("ATLAS Cumulative Data & Lineage Integrity contracts: PASS")


if __name__ == "__main__":
    main()
