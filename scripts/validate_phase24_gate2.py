from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase24_gate1_policy import (
    PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION,
    PHASE24_GATE1_PROTECTED_EVIDENCE_READS,
    phase24_gate1_policy_fingerprint,
)
from packages.backtesting.phase24_gate2 import (
    PHASE24_GATE2_CONTRACT_VERSION,
    PHASE24_PROTECTED_START_DATE,
    build_challenger_registry,
)
from packages.backtesting.phase24_gate2_validation import (
    PHASE24_GATE2_VALIDATION_CONTRACT_VERSION,
)


def _text(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def main() -> None:
    engine = _text("packages/backtesting/phase24_gate2.py")
    validator = _text("packages/backtesting/phase24_gate2_validation.py")
    cli = _text("scripts/run_phase24_gate2.py")
    registry = build_challenger_registry()
    forbidden = (
        "MassiveRESTClient(",
        "WebullSandboxBroker(",
        "AlpacaPaperBroker(",
        ".submit(",
        ".cancel(",
        ".close_position(",
        "Phase14AuditEngine(",
        "submit_authorized_plan(",
    )
    selection_lock_pos = engine.find("atomic_write_text(self.selection_lock_path")
    internal_validation_pos = engine.find('progress(f"internal validation')
    checks = {
        "gate1_policy_fingerprint_present": len(phase24_gate1_policy_fingerprint()) == 64,
        "gate2_contract_present": PHASE24_GATE2_CONTRACT_VERSION.startswith("phase24-gate2-v1-"),
        "gate2_validation_contract_present": PHASE24_GATE2_VALIDATION_CONTRACT_VERSION.startswith("phase24-gate2-validation-v1-"),
        "challenger_registry_exact_28": len(registry.all()) == 28,
        "protected_start_is_exact": PHASE24_PROTECTED_START_DATE.isoformat() == "2026-05-12",
        "protected_reads_disabled_by_gate1": PHASE24_GATE1_PROTECTED_EVIDENCE_READS is False,
        "gate0_current_excluded_from_selection": PHASE24_GATE1_GATE0_CURRENT_EVIDENCE_USED_FOR_SELECTION is False,
        "engine_has_explicit_preprotected_sql_guard": "session_date < DATE" in engine
        and "Gate 2 cannot query protected evidence" in engine,
        "selection_lock_written_before_internal_validation": 0 <= selection_lock_pos < internal_validation_pos,
        "no_second_best_fallback": '"fallback_to_second_best_after_internal_failure": False' in engine,
        "finalist_lock_keeps_protected_authority_false": '"protected_evaluation_authority": False' in engine,
        "engine_has_no_provider_broker_execution_calls": all(token not in engine for token in forbidden),
        "validator_has_no_provider_broker_execution_calls": all(token not in validator for token in forbidden),
        "cli_has_no_arbitrary_strategy_or_threshold_args": "argparse" not in cli
        and "--strategy" not in cli
        and "--threshold" not in cli
        and "--ticker" not in cli,
        "cli_runs_independent_validation": "Phase24Gate2IndependentValidator(settings).run()" in cli,
        "cli_declares_protected_unread": "Protected evidence: DISABLED / UNREAD" in cli,
        "gate2_does_not_import_protected_holdout_end": "ML_WALK_FORWARD_FINAL_HOLDOUT_END" not in engine,
        "phase11_support_mutation_not_imported": "classify_strategy_support" not in engine
        and "StrategySupportDecision" not in engine,
    }
    print(f"Phase 24 Gate 1 policy fingerprint: {phase24_gate1_policy_fingerprint()}")
    print(f"Phase 24 Gate 2 contract: {PHASE24_GATE2_CONTRACT_VERSION}")
    print(f"Phase 24 Gate 2 validation: {PHASE24_GATE2_VALIDATION_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 24 Gate 2 static validation failed: " + ", ".join(failed))
    print("Phase 24 Gate 2 development-only challenger contracts: PASS")


if __name__ == "__main__":
    main()
