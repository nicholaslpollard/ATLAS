from __future__ import annotations

from pathlib import Path

from packages.backtesting.phase30_closeout import (
    PHASE30_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE30_CLOSEOUT_REPORT_CONTRACT_VERSION,
)
from packages.backtesting.phase30_policy import (
    PHASE30_SELECTION_MIN_RAW_ROWS,
    PHASE30_SELECTION_MIN_SIGNAL_SESSIONS,
    phase30_policy_fingerprint,
)
from packages.backtesting.phase30_validation import (
    PHASE30_INDEPENDENT_VALIDATION_CONTRACT_VERSION,
)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    validation_path = root / "packages" / "backtesting" / "phase30_validation.py"
    closeout_path = root / "packages" / "backtesting" / "phase30_closeout.py"
    runner_path = root / "scripts" / "run_phase30_closeout.py"
    audit_path = root / "docs" / "phase30_end_to_end_anti_workaround_audit.md"
    future_path = root / "docs" / "future_news_sentiment_and_option_fair_value.md"

    validation = validation_path.read_text(encoding="utf-8")
    closeout = closeout_path.read_text(encoding="utf-8")
    runner = runner_path.read_text(encoding="utf-8")
    audit = audit_path.read_text(encoding="utf-8") if audit_path.is_file() else ""
    future = future_path.read_text(encoding="utf-8") if future_path.is_file() else ""
    validation_lower = validation.lower()

    forbidden_validation_tokens = (
        "from .phase30_development",
        "import phase30_development",
        "protected_news_shocks.parquet",
        "protected_confirmation",
        ".place_order(",
        ".submit_order(",
        ".cancel_order(",
    )
    checks = {
        "policy_fingerprint_exact": len(phase30_policy_fingerprint()) == 64,
        "independent_contract_present": PHASE30_INDEPENDENT_VALIDATION_CONTRACT_VERSION
        in validation,
        "closeout_contract_present": PHASE30_CLOSEOUT_REPORT_CONTRACT_VERSION in closeout,
        "audit_contract_present": PHASE30_ARCHITECTURE_AUDIT_CONTRACT_VERSION in audit,
        "audit_disposition_pass": "**Disposition:** PASS" in audit,
        "independent_reconstructs_exact_join": "ON n.ticker = p.ticker" in validation
        and "CAST(n.session_date AS DATE) = CAST(p.as_of_date AS DATE)" in validation,
        "independent_ranks_before_reaction": validation.find("tail_count =")
        < validation.find("candidate.required_reaction_sign"),
        "independent_uses_frozen_sample_gates": "PHASE30_SELECTION_MIN_RAW_ROWS" in validation
        and "PHASE30_SELECTION_MIN_SIGNAL_SESSIONS" in validation
        and PHASE30_SELECTION_MIN_RAW_ROWS == 750
        and PHASE30_SELECTION_MIN_SIGNAL_SESSIONS == 250,
        "independent_does_not_import_development": not any(
            token in validation_lower for token in forbidden_validation_tokens[:2]
        ),
        "independent_no_protected_or_order_path": not any(
            token in validation_lower for token in forbidden_validation_tokens[2:]
        ),
        "closeout_requires_empty_finalists": 'disposition != "ACCEPTED_NEGATIVE"' in closeout
        and '"finalists_empty"' in closeout,
        "closeout_requires_protected_unread": '"protected_returns_unread"' in closeout
        and '"protected_holdout_unconsumed"' in closeout,
        "runner_calls_independent_before_closeout": runner.find("Phase30IndependentNegativeValidator(settings).run()")
        < runner.find("Phase30Closeout(settings).run()"),
        "future_alpaca_note_preserves_phase30": "Alpaca" in future
        and "does not alter" in future,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    print("ATLAS Phase 30 independent-validation / closeout contracts")
    for name, passed in checks.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    if failed:
        raise SystemExit("Phase30 closeout contract validation failed: " + ", ".join(failed))
    print("Overall: PASS")


if __name__ == "__main__":
    main()
