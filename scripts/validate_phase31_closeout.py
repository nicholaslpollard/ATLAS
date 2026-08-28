from __future__ import annotations

from pathlib import Path

from packages.backtesting.phase31_closeout import (
    PHASE31_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE31_CLOSEOUT_REPORT_CONTRACT_VERSION,
)
from packages.backtesting.phase31_policy import (
    PHASE31_SELECTION_MIN_RAW_ROWS,
    PHASE31_SELECTION_MIN_SIGNAL_SESSIONS,
    PHASE31_SELECTION_MIN_UNIQUE_TICKERS,
    phase31_policy_fingerprint,
)
from packages.backtesting.phase31_validation import (
    PHASE31_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    validation_path = root / "packages" / "backtesting" / "phase31_validation.py"
    closeout_path = root / "packages" / "backtesting" / "phase31_closeout.py"
    runner_path = root / "scripts" / "run_phase31_closeout.py"
    audit_path = root / "docs" / "phase31_end_to_end_anti_workaround_audit.md"
    workflow_path = root / ".github" / "workflows" / "atlas-tests.yml"

    validation = validation_path.read_text(encoding="utf-8")
    closeout = closeout_path.read_text(encoding="utf-8")
    runner = runner_path.read_text(encoding="utf-8")
    audit = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    workflow = workflow_path.read_text(encoding="utf-8") if workflow_path.is_file() else ""
    validation_lower = validation.lower()

    forbidden_validation_tokens = (
        "from .phase31_development",
        "import phase31_development",
        "protected_form4_events.parquet",
        "protected_confirmation",
        ".place_order(",
        ".submit_order(",
        ".cancel_order(",
    )
    checks = {
        "policy_fingerprint_exact": len(phase31_policy_fingerprint()) == 64,
        "independent_contract_present": PHASE31_INDEPENDENT_VALIDATION_CONTRACT_VERSION
        in validation,
        "closeout_contract_present": PHASE31_CLOSEOUT_REPORT_CONTRACT_VERSION in closeout,
        "audit_contract_present": PHASE31_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit,
        "audit_disposition_pass": "**Disposition:** PASS" in audit,
        "independent_reconstructs_exact_path": "se.session_open AS entry_open" in validation
        and "sx.session_close AS exit_close" in validation
        and "split_crossing" in validation,
        "independent_uses_frozen_sample_gates": "PHASE31_SELECTION_MIN_RAW_ROWS" in validation
        and "PHASE31_SELECTION_MIN_SIGNAL_SESSIONS" in validation
        and "PHASE31_SELECTION_MIN_UNIQUE_TICKERS" in validation
        and PHASE31_SELECTION_MIN_RAW_ROWS == 750
        and PHASE31_SELECTION_MIN_SIGNAL_SESSIONS == 250
        and PHASE31_SELECTION_MIN_UNIQUE_TICKERS == 250,
        "independent_does_not_import_development": not any(
            token in validation_lower for token in forbidden_validation_tokens[:2]
        ),
        "independent_no_protected_or_order_path": not any(
            token in validation_lower for token in forbidden_validation_tokens[2:]
        ),
        "independent_hash_binds_protected": "sha256_file(protected_path)" in validation,
        "closeout_requires_empty_finalists": 'disposition != "ACCEPTED_NEGATIVE"' in closeout
        and '"finalists_empty"' in closeout,
        "closeout_requires_protected_unread": '"protected_returns_unread"' in closeout
        and '"protected_holdout_unconsumed"' in closeout,
        "closeout_blocks_phase32_on_negative": '"negative_disposition_blocks_phase32"' in closeout
        and '"phase32_entry_satisfied"' in closeout,
        "runner_calls_independent_before_closeout": runner.find(
            "Phase31IndependentNegativeValidator(settings).run()"
        )
        < runner.find("Phase31Closeout(settings).run()"),
        "workflow_runs_closeout_validator": "python scripts/validate_phase31_closeout.py"
        in workflow,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    print("ATLAS Phase 31 independent-validation / closeout contracts")
    for name, passed in checks.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    if failed:
        raise SystemExit("Phase31 closeout contract validation failed: " + ", ".join(failed))
    print("Overall: PASS")


if __name__ == "__main__":
    main()
