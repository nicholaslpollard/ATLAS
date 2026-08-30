from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY = "4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7"
EXPECTED_ACCEPTANCE = "531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde"
EXPECTED_PREDICTOR_SHA = "c5b171557d173bdf0095aecfaf660b8660f2480d233fa9c5a55f138b86c1f3f9"
EXPECTED_FILING_SHA = "18fd036f8718bba9920395627f0e233cd9cead41d03decb31f29d5bdf0a3ff31"


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    development = read("packages/backtesting/phase32_development.py")
    runner = read("scripts/run_phase32_development.py")
    scientific = read("docs/phase32_scientific_contract.md")
    workflow = read(".github/workflows/phase32-tests.yml")
    for path, source in (
        ("packages/backtesting/phase32_development.py", development),
        ("scripts/run_phase32_development.py", runner),
    ):
        ast.parse(source, filename=path)

    from packages.backtesting.phase32_development import (
        PHASE32_DEVELOPMENT_BOUNDARY_EXIT,
        PHASE32_DEVELOPMENT_OUTCOME_CONTRACT_VERSION,
        PHASE32_DEVELOPMENT_SIGNAL_CONTRACT_VERSION,
        PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION,
        PHASE32_FINALIST_ARTIFACT_CONTRACT_VERSION,
        PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT,
    )
    from packages.backtesting.phase32_policy import (
        PHASE32_CANDIDATES,
        PHASE32_INTERNAL_MIN_EVENT_ROWS,
        PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
        PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
        PHASE32_INTERNAL_PURGE_SESSIONS,
        PHASE32_MULTIPLE_TESTING_METHOD,
        PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED,
        PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED,
        PHASE32_SELECTION_MIN_EVENT_ROWS,
        PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
        PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
        PHASE32_SELECTION_WINNER_RULE,
        phase32_policy_fingerprint,
    )
    from packages.backtesting.phase32_predictor_acceptance import (
        PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256,
        PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256,
    )

    checks = {
        "policy_fingerprint_exact": phase32_policy_fingerprint() == EXPECTED_POLICY,
        "independent_acceptance_exact": PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT == EXPECTED_ACCEPTANCE,
        "predictor_sha_exact": PHASE32_TARGET_ACQUISITION_PREDICTOR_SHA256 == EXPECTED_PREDICTOR_SHA,
        "filing_entity_sha_exact": PHASE32_TARGET_ACQUISITION_FILING_ENTITY_SHA256 == EXPECTED_FILING_SHA,
        "exact_five_hypotheses": len(PHASE32_CANDIDATES) == 5,
        "global_holm_exact": PHASE32_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_5",
        "selection_sample_gates_exact": (
            PHASE32_SELECTION_MIN_EVENT_ROWS,
            PHASE32_SELECTION_MIN_SIGNAL_SESSIONS,
            PHASE32_SELECTION_MIN_UNIQUE_INSTRUMENTS,
        ) == (500, 200, 200),
        "internal_sample_gates_exact": (
            PHASE32_INTERNAL_MIN_EVENT_ROWS,
            PHASE32_INTERNAL_MIN_SIGNAL_SESSIONS,
            PHASE32_INTERNAL_MIN_UNIQUE_INSTRUMENTS,
        ) == (150, 60, 60),
        "five_session_purge_exact": PHASE32_INTERNAL_PURGE_SESSIONS == 5,
        "winner_rule_exact": PHASE32_SELECTION_WINNER_RULE == "highest_primary_selection_LCB_then_candidate_id",
        "runner_up_disabled": PHASE32_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_predictor_metadata_allowed": PHASE32_PROTECTED_PREDICTORS_BEFORE_FINALISTS_ALLOWED is True,
        "protected_returns_closed": PHASE32_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False,
        "outer_boundary_exact": PHASE32_DEVELOPMENT_BOUNDARY_EXIT.isoformat() == "2026-05-11",
        "development_contracts_present": all(bool(value) for value in (
            PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            PHASE32_DEVELOPMENT_OUTCOME_CONTRACT_VERSION,
            PHASE32_DEVELOPMENT_SIGNAL_CONTRACT_VERSION,
            PHASE32_FINALIST_ARTIFACT_CONTRACT_VERSION,
        )),
        "independent_acceptance_precedes_market_read": (
            development.index("_load_development_predictors()")
            < development.index("_development_outcomes(", development.index("def run(self)"))
            and "source_report_sha256" in development
            and "PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT" in development
        ),
        "execution_ticker_preflight_fail_closed": (
            "resolve_execution_tickers" in development
            and "execution ticker is ambiguous before outcomes" in development
            and development.index("resolve_execution_tickers(development_rows, filing_rows)")
            < development.index("def _development_outcomes")
        ),
        "exact_open_t5_spy_geometry": all(token in development for token in (
            'result["stock_return"] = result["exit_close"] / result["entry_open"] - 1.0',
            'result["spy_return"] = result["spy_exit_close"] / result["spy_entry_open"] - 1.0',
            'result["primary_gross_return"] = direction * (result["stock_return"] - result["spy_return"])',
            'result["unhedged_gross_return"] = direction * result["stock_return"]',
            "PHASE32_OUTCOME_HORIZON_SESSIONS + 1",
        )),
        "exact_bar_session_join_no_nearest_substitution": (
            "se.session_date = CAST(p.decision_session AS DATE)" in development
            and "sx.session_date = CAST(p.exit_session AS DATE)" in development
            and "se.symbol = p.execution_ticker" in development
            and "sx.symbol = p.execution_ticker" in development
        ),
        "accepted_split_evidence_reused": (
            "MLOutcomeFeasibilityProbe" in development
            and "split_evidence_sha256" in development
            and "split_crossing_censored_rows" in development
        ),
        "previous_session_regime_only": (
            'result["prior_state_session"] = result["decision_session"].map(previous)' in development
            and '"prior_market_state"' in development
            and "persist_exact_interval_ticker_states" in development
            and "prior_ticker_state" in development
        ),
        "complete_frozen_stage_gates": all(token in development for token in (
            "min_unique_instruments",
            "primary_mean_positive",
            "primary_lcb_positive",
            "stress_mean_positive",
            "unhedged_primary_mean_positive",
            "year_robustness",
            "market_state_robustness",
            "ticker_state_robustness",
            "session_concentration",
            "instrument_concentration",
            "deflated_sharpe_probability",
            "holm_bonferroni",
        )),
        "empty_folds_not_dropped": (
            "tuple(None for _ in range(fold_count))" in development
            and "for fold in range(fold_count)" in development
        ),
        "no_provider_broker_execution_import": not any(token in development.lower() for token in (
            "from packages.providers", "import packages.providers",
            "from packages.brokers", "import packages.brokers",
            "from packages.execution", "import packages.execution",
            ".submit_order(", ".place_order(",
        )),
        "runner_announces_one_way_boundary": (
            "Development market outcomes: AUTHORIZED / READ IN THIS STEP" in runner
            and "Protected stock/SPY returns: FORBIDDEN / UNREAD" in runner
        ),
        "scientific_contract_matches_previous_state_rule": (
            "previous XNYS session" in scientific
            and "HOLM_BONFERRONI_GLOBAL_5" in scientific
            and "one finalist per direction" in scientific
        ),
        "unit_tests_present": (PROJECT_ROOT / "tests" / "unit" / "test_phase32_development.py").is_file(),
        "ci_validator_present": (
            "Validate Phase 32 development-only contracts" in workflow
            and "python scripts/validate_phase32_development.py" in workflow
        ),
    }

    print(f"Phase 32 policy fingerprint: {phase32_policy_fingerprint()}")
    print(f"Phase 32 independent acceptance: {PHASE32_TARGET_INDEPENDENT_ACCEPTANCE_FINGERPRINT}")
    print(f"Phase 32 development contract: {PHASE32_DEVELOPMENT_STUDY_CONTRACT_VERSION}")
    for name, passed in checks.items():
        print(f"  {name}: {passed}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 32 development-only contract validation failed: " + ", ".join(failed))
    print("ATLAS Phase 32 development-only SEC 8-K contracts: PASS")
    print("- independent source/predictor acceptance is pinned before market outcomes")
    print("- development uses exact open-to-T+5-close SPY-relative outcomes")
    print("- frozen execution-ticker lineage is resolved before outcome reads")
    print("- split crossings and missing exact stock paths are censored fail-closed")
    print("- selection/internal robustness uses previous-session accepted regimes")
    print("- protected stock/SPY returns remain unread")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
