from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY = "4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7"
EXPECTED_ACCEPTANCE = "531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde"
EXPECTED_FINALIST = "solvency_distress_short"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    audit = read("packages/backtesting/phase32_finalist_audit.py")
    runner = read("scripts/run_phase32_finalist_audit.py")
    unit = read("tests/unit/test_phase32_finalist_audit.py")
    workflow = read(".github/workflows/phase32-tests.yml")
    scientific = read("docs/phase32_scientific_contract.md")
    phase_doc = read("docs/phase32_sec_8k_material_event_alpha.md")
    development_doc = read("docs/phase32_development_evaluation.md")
    status = read("docs/current_status.md")

    for path, source in (
        ("packages/backtesting/phase32_finalist_audit.py", audit),
        ("scripts/run_phase32_finalist_audit.py", runner),
        ("tests/unit/test_phase32_finalist_audit.py", unit),
    ):
        ast.parse(source, filename=path)

    from packages.backtesting.phase32_finalist_audit import (
        PHASE32_EXPECTED_DEVELOPMENT_TARGET_ROWS,
        PHASE32_EXPECTED_DEVELOPMENT_USABLE_ROWS,
        PHASE32_EXPECTED_FINALISTS,
        PHASE32_EXPECTED_MISSING_EXACT_STOCK_PATH_ROWS,
        PHASE32_EXPECTED_SELECTION_SURVIVORS,
        PHASE32_EXPECTED_SELECTION_WINNERS,
        PHASE32_EXPECTED_SPLIT_CROSSING_ROWS,
        PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION,
        PHASE32_PROTECTED_PLAN_CONTRACT_VERSION,
        PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
    )
    from packages.backtesting.phase32_policy import (
        PHASE32_PROTECTED_FOLDS,
        PHASE32_PROTECTED_MIN_EVENT_ROWS,
        PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS,
        PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
        PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
        phase32_policy_fingerprint,
    )

    checks = {
        "policy_fingerprint_exact": phase32_policy_fingerprint() == EXPECTED_POLICY,
        "independent_acceptance_exact": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT == EXPECTED_ACCEPTANCE,
        "audit_contract_present": PHASE32_FINALIST_BLINDNESS_AUDIT_CONTRACT_VERSION.startswith("phase32-finalist-blindness-lineage-audit-v1"),
        "protected_plan_contract_present": PHASE32_PROTECTED_PLAN_CONTRACT_VERSION.startswith("phase32-protected-plan-v1"),
        "accepted_development_counts_pinned": (
            PHASE32_EXPECTED_DEVELOPMENT_TARGET_ROWS == 18_819
            and PHASE32_EXPECTED_DEVELOPMENT_USABLE_ROWS == 18_448
            and PHASE32_EXPECTED_MISSING_EXACT_STOCK_PATH_ROWS == 294
            and PHASE32_EXPECTED_SPLIT_CROSSING_ROWS == 79
        ),
        "accepted_selection_survivors_pinned": set(PHASE32_EXPECTED_SELECTION_SURVIVORS) == {
            "equity_issuance_short",
            "financial_integrity_adverse_short",
            "listing_distress_short",
            "share_repurchase_long",
            "solvency_distress_short",
        },
        "accepted_winners_pinned": PHASE32_EXPECTED_SELECTION_WINNERS == (
            "share_repurchase_long",
            "solvency_distress_short",
        ),
        "single_finalist_pinned": PHASE32_EXPECTED_FINALISTS == (EXPECTED_FINALIST,),
        "protected_sample_gates_exact": (
            PHASE32_PROTECTED_MIN_EVENT_ROWS == 50
            and PHASE32_PROTECTED_MIN_SIGNAL_SESSIONS == 20
            and PHASE32_PROTECTED_MIN_UNIQUE_INSTRUMENTS == 20
            and PHASE32_PROTECTED_FOLDS == 3
        ),
        "runner_up_disabled": PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "independent_from_development_implementation": (
            "from .phase32_development" not in audit
            and "import phase32_development" not in audit
        ),
        "independent_recomputes_return_geometry": all(token in audit for token in (
            'stock_return = frame["exit_close"] / frame["entry_open"] - 1.0',
            'spy_return = frame["spy_exit_close"] / frame["spy_entry_open"] - 1.0',
            "primary_gross = direction * (stock_return - spy_return)",
            "unhedged_gross = direction * stock_return",
        )),
        "independent_recomputes_bootstrap": (
            "independent_block_bootstrap" in audit
            and "PHASE32_BOOTSTRAP_REPLICATES" in audit
            and "PHASE32_BOOTSTRAP_BLOCK_SESSIONS" in audit
        ),
        "independent_recomputes_holm5": (
            "independent_holm_bonferroni" in audit
            and "PHASE32_MULTIPLE_TESTING_ALPHA" in audit
        ),
        "protected_plan_finalist_only": (
            "finalist_predictors" in audit
            and 'str(row.get("candidate_id") or "") in finalist_set' in audit
        ),
        "protected_plan_freezes_three_folds": (
            "protected_fold" in audit
            and "PHASE32_PROTECTED_FOLDS" in audit
        ),
        "protected_source_sample_precheck": (
            "protected_source_sample_gate" in audit
            and "protected_return_authorized_after_fingerprint_freeze" in audit
        ),
        "protected_returns_remain_zero": (
            '"protected_return_rows_read": 0' in audit
            and '"protected_holdout_consumed": False' in audit
            and "Protected stock/SPY returns: FORBIDDEN / UNREAD" in runner
        ),
        "no_market_data_provider_or_execution_path": not any(token in audit for token in (
            "MarketDataPaths",
            "glob_for_timeframe",
            "packages.providers",
            "packages.brokers",
            "packages.execution",
            ".submit_order(",
            ".place_order(",
        )),
        "plan_forbids_outcome_fields": "_PLAN_FORBIDDEN_FIELDS" in audit,
        "workflow_validator_present": "python scripts/validate_phase32_finalist_audit.py" in workflow,
        "workflow_unit_present": "tests/unit/test_phase32_finalist_audit.py" in workflow,
        "scientific_contract_requires_separate_audit": "blindness/lineage audit" in scientific,
        "phase_doc_records_development_finalist": EXPECTED_FINALIST in phase_doc,
        "development_doc_records_pass": "DEVELOPMENT PASS" in development_doc,
        "status_points_to_finalist_audit": "run_phase32_finalist_audit.py" in status,
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    print("ATLAS Phase 32 finalist blindness / lineage audit contracts")
    for name, passed in checks.items():
        print(f"  {name}: {'PASS' if passed else 'FAIL'}")
    if failed:
        raise SystemExit("Phase32 finalist audit contract validation failed: " + ", ".join(failed))
    print("Overall: PASS")
    print("- accepted development result is pinned before protected planning")
    print("- finalist identity is independently recomputed without importing the development implementation")
    print("- protected plan is finalist-only, source-only, and three-fold frozen")
    print("- source-only protected sample gates can block a needless holdout read")
    print("- protected stock/SPY returns remain unread")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
