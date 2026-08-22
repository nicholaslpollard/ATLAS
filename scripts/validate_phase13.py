from __future__ import annotations

from packages.portfolio.phase13_engine import PHASE13_MANIFEST_CONTRACT_VERSION
from packages.portfolio.phase13_policy import (
    PHASE13_BROKER_WRITES,
    PHASE13_HORIZON_SESSIONS,
    PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED,
    PHASE13_ORDER_WRITES,
    PHASE13_PRIMARY_INSTRUMENT,
    PHASE13_PRODUCTION_ML_WRITES,
    PHASE13_SECTOR_CONCENTRATION_POLICY,
    phase13_policy_fingerprint,
)
from packages.portfolio.phase13_source import PHASE13_INPUT_CONTRACT_VERSION
from packages.portfolio.phase13_validation import PHASE13_VALIDATION_CONTRACT_VERSION
from packages.schemas.case_file import PHASE13_CASE_FILE_CONTRACT_VERSION, Phase13CaseFile


def main() -> None:
    fields = set(Phase13CaseFile.model_fields)
    forbidden_execution_fields = {
        "broker",
        "order",
        "order_id",
        "fill",
        "fill_id",
        "execution",
        "execution_id",
    }
    checks = {
        "horizon_three_sessions": PHASE13_HORIZON_SESSIONS == 3,
        "equity_primary": PHASE13_PRIMARY_INSTRUMENT == "EQUITY",
        "option_relative_value_not_accepted": PHASE13_OPTION_RELATIVE_VALUE_MODEL_ACCEPTED is False,
        "sector_mapping_not_guessed": PHASE13_SECTOR_CONCENTRATION_POLICY
        == "UNAVAILABLE_NO_AUTHORITATIVE_TICKER_TO_SECTOR_MAPPING",
        "case_schema_has_no_execution_fields": not fields.intersection(forbidden_execution_fields),
        "production_ml_writes_zero": PHASE13_PRODUCTION_ML_WRITES == 0,
        "broker_writes_zero": PHASE13_BROKER_WRITES == 0,
        "order_writes_zero": PHASE13_ORDER_WRITES == 0,
        "policy_fingerprint_present": len(phase13_policy_fingerprint()) == 64,
    }
    failed = sorted(name for name, value in checks.items() if not value)
    print(f"Phase 13 input contract: {PHASE13_INPUT_CONTRACT_VERSION}")
    print(f"Phase 13 case contract: {PHASE13_CASE_FILE_CONTRACT_VERSION}")
    print(f"Phase 13 manifest contract: {PHASE13_MANIFEST_CONTRACT_VERSION}")
    print(f"Phase 13 validation contract: {PHASE13_VALIDATION_CONTRACT_VERSION}")
    print(f"Phase 13 policy fingerprint: {phase13_policy_fingerprint()}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if failed:
        raise SystemExit("Phase 13 static validation failed: " + ", ".join(failed))
    print("Phase 13 Context, Instrument, Geometry, and Portfolio Risk contracts: PASS")


if __name__ == "__main__":
    main()
