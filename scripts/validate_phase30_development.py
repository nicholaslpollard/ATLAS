from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_development import (
    PHASE30_DEVELOPMENT_POPULATION_CONTRACT_VERSION,
    PHASE30_DEVELOPMENT_STUDY_CONTRACT_VERSION,
    PHASE30_FINALIST_ARTIFACT_CONTRACT_VERSION,
    PHASE30_PREDICTION_ARTIFACT_CONTRACT_VERSION,
    PHASE30_SIGNAL_ARTIFACT_CONTRACT_VERSION,
)
from packages.backtesting.phase30_policy import (
    PHASE30_CANDIDATES,
    PHASE30_CURRENT_REACTION_FIELD,
    PHASE30_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE30_MULTIPLE_TESTING_METHOD,
    PHASE30_OUTCOME_HORIZON_SESSIONS,
    PHASE30_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE30_SIGNAL_TAIL_FRACTION,
    phase30_policy_fingerprint,
)


EXPECTED_POLICY_FINGERPRINT = (
    "341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8"
)
EXPECTED_CANDIDATES = (
    "news_shock_aligned_continuation_long",
    "news_shock_aligned_continuation_short",
    "news_shock_counterreaction_reversal_long",
    "news_shock_counterreaction_reversal_short",
)


def main() -> None:
    development_path = PROJECT_ROOT / "packages" / "backtesting" / "phase30_development.py"
    runner_path = PROJECT_ROOT / "scripts" / "run_phase30_development.py"
    test_path = PROJECT_ROOT / "tests" / "unit" / "test_phase30_development.py"
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "atlas-tests.yml"

    development_source = development_path.read_text(encoding="utf-8")
    runner_source = runner_path.read_text(encoding="utf-8")
    workflow_source = workflow_path.read_text(encoding="utf-8")
    lowered = development_source.lower()

    candidate_ids = tuple(candidate.candidate_id for candidate in PHASE30_CANDIDATES)
    forbidden_protected_access = (
        ".protected_path()",
        ".protected_predictors_path()",
        "protected_relative_value_predictors",
        "protected_network_predictors",
    )
    forbidden_external_authority = (
        "from packages.providers",
        "import packages.providers",
        "from packages.brokers",
        "import packages.brokers",
        "from packages.execution",
        "import packages.execution",
        ".submit_order(",
        ".place_order(",
        ".cancel_order(",
    )
    # This guard is intentionally scoped to ticker semantics. Generic `.upper()` /
    # `.lower()` checks are invalid here because unrelated configuration handling
    # (for example Parquet compression names) legitimately uses case conversion.
    forbidden_ticker_transform_or_remap = (
        '["ticker"].str.upper(',
        '["ticker"].str.lower(',
        "['ticker'].str.upper(",
        "['ticker'].str.lower(",
        "ticker.upper(",
        "ticker.lower(",
        "upper(n.ticker)",
        "lower(n.ticker)",
        "upper(p.ticker)",
        "lower(p.ticker)",
        "collate nocase",
        "ticker_alias",
        "symbol_map",
        "ticker_map",
        "ticker_remap",
    )

    checks = {
        "policy_fingerprint_exact": phase30_policy_fingerprint()
        == EXPECTED_POLICY_FINGERPRINT,
        "exact_four_hypotheses": candidate_ids == EXPECTED_CANDIDATES,
        "reaction_field_exact": PHASE30_CURRENT_REACTION_FIELD == "d1_return_1",
        "outcome_horizon_exact": PHASE30_OUTCOME_HORIZON_SESSIONS == 3,
        "same_session_direction_minimum_exact": PHASE30_MIN_DIRECTION_ROWS_PER_SESSION == 5,
        "signal_tail_exact": PHASE30_SIGNAL_TAIL_FRACTION == 0.20,
        "global_holm_exact": PHASE30_MULTIPLE_TESTING_METHOD
        == "HOLM_BONFERRONI_GLOBAL_4",
        "runner_up_disabled": PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_returns_finalist_only": PHASE30_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED
        is False,
        "development_contracts_present": all(
            bool(value)
            for value in (
                PHASE30_DEVELOPMENT_STUDY_CONTRACT_VERSION,
                PHASE30_DEVELOPMENT_POPULATION_CONTRACT_VERSION,
                PHASE30_PREDICTION_ARTIFACT_CONTRACT_VERSION,
                PHASE30_SIGNAL_ARTIFACT_CONTRACT_VERSION,
                PHASE30_FINALIST_ARTIFACT_CONTRACT_VERSION,
            )
        ),
        "reuses_accepted_phase26_development_artifact": (
            "Phase26ObservationBuilder" in development_source
            and "self.phase26.development_path()" in development_source
            and "PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION" in development_source
        ),
        "reuses_phase30_predictor_artifact": (
            "Phase30NewsPredictorBuilder" in development_source
            and "self.news.development_path()" in development_source
            and "PHASE30_DEVELOPMENT_NEWS_SHOCK_CONTRACT_VERSION" in development_source
        ),
        "exact_ticker_session_join": (
            "ON n.ticker = p.ticker" in development_source
            and "CAST(n.session_date AS DATE) = CAST(p.as_of_date AS DATE)"
            in development_source
        ),
        "no_ticker_normalization_or_remap": not any(
            token in lowered for token in forbidden_ticker_transform_or_remap
        ),
        "direction_tail_precedes_reaction_split": (
            "def direction_tail_frame" in development_source
            and "session+direction before the frozen reaction-sign split" in development_source
            and "predictions = ranked.loc[_reaction_mask(ranked, candidate)].copy()"
            in development_source
        ),
        "deterministic_outcome_free_tie_break": (
            '["phase30_score", "instrument_id"]' in development_source
            and "ascending=[False, True]" in development_source
            and "news_surprise_desc_then_instrument_id_asc" in development_source
        ),
        "minimum_direction_rows_fail_closed": (
            "len(group) < PHASE30_MIN_DIRECTION_ROWS_PER_SESSION" in development_source
        ),
        "fixed_tail_uses_ceil": (
            "math.ceil(PHASE30_SIGNAL_TAIL_FRACTION * len(ordered))"
            in development_source
        ),
        "development_only_boundary_exact": (
            "PHASE30_DEVELOPMENT_END" in development_source
            and "development_boundary_label_end" in development_source
        ),
        "full_calendar_chronology_and_purge": (
            "chronological_boundaries" in development_source
            and "PHASE30_SELECTION_FRACTION" in development_source
            and "PHASE30_PURGE_SESSIONS" in development_source
        ),
        "complete_selection_statistics": all(
            token in development_source
            for token in (
                "PHASE30_PRIMARY_COST_BPS",
                "PHASE30_STRESS_COST_BPS",
                "PHASE30_BOOTSTRAP_REPLICATES",
                "PHASE30_SELECTION_MIN_RAW_ROWS",
                "PHASE30_MIN_POSITIVE_YEAR_FRACTION",
                "PHASE30_MIN_POSITIVE_REGIME_FRACTION",
                "PHASE30_MAX_SINGLE_SESSION_ROW_FRACTION",
                "PHASE30_MAX_SINGLE_TICKER_ROW_FRACTION",
                "holm_bonferroni",
                "deflated_sharpe_probability",
            )
        ),
        "winner_and_finalist_direction_limits": (
            "PHASE30_MAX_SELECTION_WINNERS_PER_DIRECTION" in development_source
            and "finalist_directions" in development_source
            and "runner_up_substitution_allowed" in development_source
        ),
        "protected_accessor_absent": not any(
            token in development_source for token in forbidden_protected_access
        ),
        "protected_reads_explicitly_zero": (
            '"protected_candidate_rows_read": 0' in development_source
            and '"protected_return_rows_read": 0' in development_source
            and '"protected_holdout_consumed": False' in development_source
        ),
        "no_provider_broker_execution_authority": not any(
            token in lowered for token in forbidden_external_authority
        ),
        "runner_announces_one_way_boundary": (
            "Development outcomes: AUTHORIZED / READ IN THIS STEP" in runner_source
            and "Protected candidates/returns: FORBIDDEN / UNREAD" in runner_source
        ),
        "runner_never_claims_support_before_confirmation": (
            "SUPPORTED" not in runner_source
        ),
        "unit_tests_present": test_path.is_file(),
        "ci_validator_present": (
            "Validate Phase 30 development-only selection contracts" in workflow_source
            and "python scripts/validate_phase30_development.py" in workflow_source
        ),
    }

    print(f"Phase 30 policy fingerprint: {phase30_policy_fingerprint()}")
    print(f"Phase 30 development contract: {PHASE30_DEVELOPMENT_STUDY_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit(
            "Phase 30 development-only contract validation failed: "
            + ", ".join(failed)
        )
    print("Phase 30 development-only selection contracts: PASS")


if __name__ == "__main__":
    main()
