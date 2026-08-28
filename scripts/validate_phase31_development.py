from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY = "e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67"
EXPECTED_DEVELOPMENT_SHA = "a82ff3114febc0c6f7c13d5f045549b714edbf0fd66157ef93853be9ae90c49f"
EXPECTED_PROTECTED_SHA = "d3bcd2696463ec1e384919007a36570475f8cb0bf1e393f109f0accd24224e27"
EXPECTED_EVIDENCE_COUNTS = (2_992_608, 103_773, 5_870, 5_400, 343)


def read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    evidence = read("packages/backtesting/phase31_predictor_evidence.py")
    development = read("packages/backtesting/phase31_development.py")
    runner = read("scripts/run_phase31_development.py")
    scientific = read("docs/phase31_scientific_contract.md")
    workflow = read(".github/workflows/atlas-tests.yml")
    for path, source in (
        ("packages/backtesting/phase31_predictor_evidence.py", evidence),
        ("packages/backtesting/phase31_development.py", development),
        ("scripts/run_phase31_development.py", runner),
    ):
        ast.parse(source, filename=path)

    from packages.backtesting.phase31_development import (
        PHASE31_DEVELOPMENT_BOUNDARY_EXIT,
        PHASE31_DEVELOPMENT_OUTCOME_CONTRACT_VERSION,
        PHASE31_DEVELOPMENT_SIGNAL_CONTRACT_VERSION,
        PHASE31_DEVELOPMENT_STUDY_CONTRACT_VERSION,
        PHASE31_FINALIST_ARTIFACT_CONTRACT_VERSION,
    )
    from packages.backtesting.phase31_policy import (
        PHASE31_CANDIDATES,
        PHASE31_INTERNAL_MIN_UNIQUE_TICKERS,
        PHASE31_MULTIPLE_TESTING_METHOD,
        PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
        PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED,
        PHASE31_SELECTION_MIN_UNIQUE_TICKERS,
        PHASE31_SELECTION_WINNER_RULE,
        phase31_policy_fingerprint,
    )
    from packages.backtesting.phase31_predictor_evidence import (
        PHASE31_PREDICTOR_EVIDENCE_AUTHORITATIVE_ROWS,
        PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS,
        PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256,
        PHASE31_PREDICTOR_EVIDENCE_PROTECTED_ROWS,
        PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256,
        PHASE31_PREDICTOR_EVIDENCE_QUALIFIED_ACCESSIONS,
        PHASE31_PREDICTOR_EVIDENCE_RESOLVED_EVENTS,
    )

    counts = (
        PHASE31_PREDICTOR_EVIDENCE_AUTHORITATIVE_ROWS,
        PHASE31_PREDICTOR_EVIDENCE_QUALIFIED_ACCESSIONS,
        PHASE31_PREDICTOR_EVIDENCE_RESOLVED_EVENTS,
        PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_ROWS,
        PHASE31_PREDICTOR_EVIDENCE_PROTECTED_ROWS,
    )
    checks = {
        "policy_fingerprint_exact": phase31_policy_fingerprint() == EXPECTED_POLICY,
        "predictor_evidence_counts_exact": counts == EXPECTED_EVIDENCE_COUNTS,
        "development_predictor_sha_exact": PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256 == EXPECTED_DEVELOPMENT_SHA,
        "protected_predictor_sha_exact": PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256 == EXPECTED_PROTECTED_SHA,
        "exact_four_hypotheses": len(PHASE31_CANDIDATES) == 4,
        "global_holm_exact": PHASE31_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_4",
        "selection_unique_ticker_gate": PHASE31_SELECTION_MIN_UNIQUE_TICKERS == 250,
        "internal_unique_ticker_gate": PHASE31_INTERNAL_MIN_UNIQUE_TICKERS == 80,
        "winner_rule_exact": PHASE31_SELECTION_WINNER_RULE == "highest_primary_selection_LCB_then_candidate_id",
        "runner_up_disabled": PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_returns_finalist_only": PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False,
        "outer_boundary_exact": PHASE31_DEVELOPMENT_BOUNDARY_EXIT.isoformat() == "2026-05-11",
        "development_contracts_present": all(bool(value) for value in (
            PHASE31_DEVELOPMENT_STUDY_CONTRACT_VERSION,
            PHASE31_DEVELOPMENT_OUTCOME_CONTRACT_VERSION,
            PHASE31_DEVELOPMENT_SIGNAL_CONTRACT_VERSION,
            PHASE31_FINALIST_ARTIFACT_CONTRACT_VERSION,
        )),
        "predictor_evidence_validated_before_outcomes": (
            "validate_phase31_predictor_report(report)" in development
            and "PHASE31_PREDICTOR_EVIDENCE_DEVELOPMENT_SHA256" in development
            and "PHASE31_PREDICTOR_EVIDENCE_PROTECTED_SHA256" in development
        ),
        "protected_artifact_hash_only": (
            "sha256_file(protected_path)" in development
            and "read_parquet({sql_string(protected_path)})" not in development
            and '\"protected_candidate_rows_read\": 0' in development
            and '\"protected_return_rows_read\": 0' in development
        ),
        "exact_open_t20_spy_geometry": all(token in development for token in (
            'result["stock_return"] = result["exit_close"] / result["entry_open"] - 1.0',
            'result["spy_return"] = result["spy_exit_close"] / result["spy_entry_open"] - 1.0',
            'result["primary_gross_return"] = direction * (',
            'result["unhedged_gross_return"] = direction * result["stock_return"]',
            "PHASE31_OUTCOME_HORIZON_SESSIONS + 1",
        )),
        "exact_bar_session_join_no_nearest_substitution": (
            "n.session_date = CAST(b.session_date AS DATE)" in development
            and "se.session_date = CAST(p.decision_session AS DATE)" in development
            and "sx.session_date = CAST(p.exit_session AS DATE)" in development
        ),
        "accepted_split_evidence_reused": (
            "MLOutcomeFeasibilityProbe" in development
            and "split_evidence_sha256" in development
            and "split_crossing_censored_rows" in development
        ),
        "previous_session_regime_only": (
            'result["prior_state_session"] = result["decision_session"].map(previous)' in development
            and 'result["prior_market_state"]' in development
            and "persist_exact_interval_ticker_states" in development
            and "prior_ticker_state" in development
        ),
        "full_calendar_chronology_and_20_session_purge": (
            "chronological_boundaries" in development
            and "PHASE31_SELECTION_FRACTION" in development
            and "PHASE31_INTERNAL_PURGE_SESSIONS" in development
        ),
        "complete_frozen_stage_gates": all(token in development for token in (
            "min_unique_tickers",
            "primary_mean_positive",
            "primary_lcb_positive",
            "stress_mean_positive",
            "unhedged_primary_mean_positive",
            "year_robustness",
            "market_state_robustness",
            "ticker_state_robustness",
            "session_concentration",
            "ticker_concentration",
            "deflated_sharpe_probability",
            "holm_bonferroni",
        )),
        "candidate_membership_not_outcome_ranked": (
            'frame["cluster_candidate_id"]' in development
            and 'frame["broad_candidate_id"]' in development
            and "direction_tail_frame" not in development
            and "news_surprise" not in development
        ),
        "winner_tie_break_no_mean": "PHASE31_SELECTION_WINNER_RULE" in development,
        "no_provider_broker_execution_import": not any(token in development.lower() for token in (
            "from packages.providers",
            "import packages.providers",
            "from packages.brokers",
            "import packages.brokers",
            "from packages.execution",
            "import packages.execution",
            ".submit_order(",
            ".place_order(",
        )),
        "runner_announces_one_way_boundary": (
            "Development market outcomes: AUTHORIZED / READ IN THIS STEP" in runner
            and "Protected candidate rows/returns: FORBIDDEN / UNREAD" in runner
        ),
        "scientific_contract_requires_prior_state": "previous XNYS session's accepted state" in scientific,
        "unit_tests_present": (PROJECT_ROOT / "tests" / "unit" / "test_phase31_development.py").is_file(),
        "ci_validator_present": (
            "Validate Phase 31 development-only Form-4 contracts" in workflow
            and "python scripts/validate_phase31_development.py" in workflow
        ),
    }

    print(f"Phase 31 policy fingerprint: {phase31_policy_fingerprint()}")
    print(f"Phase 31 development contract: {PHASE31_DEVELOPMENT_STUDY_CONTRACT_VERSION}")
    for name, passed in checks.items():
        print(f"  {name}: {passed}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 31 development-only contract validation failed: " + ", ".join(failed))
    print("ATLAS Phase 31 development-only Form-4 contracts: PASS")
    print("- predictor membership is frozen before performance")
    print("- development uses exact open-to-T+20-close SPY-relative outcomes")
    print("- split crossings are censored from accepted read-only evidence")
    print("- selection/internal robustness uses previous-session accepted regimes")
    print("- protected candidate rows and protected returns remain unread")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
