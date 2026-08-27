from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_acquisition import (
    PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION,
    phase30_news_acquisition_bounds,
    phase30_news_shard_windows,
)
from packages.backtesting.phase30_feasibility import phase30_feasibility_fingerprint
from packages.backtesting.phase30_policy import (
    PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
    PHASE30_AUTOMATIC_BROKER_FAILOVER,
    PHASE30_AUTOMATION_WRITES,
    PHASE30_BROKER_READS,
    PHASE30_BROKER_WRITES,
    PHASE30_CANDIDATES,
    PHASE30_CURRENT_REACTION_FIELD,
    PHASE30_DECISION_BUFFER_MINUTES,
    PHASE30_LIVE_WRITES,
    PHASE30_MAX_FINALISTS_PER_DIRECTION,
    PHASE30_MULTIPLE_TESTING_METHOD,
    PHASE30_NEWS_BASELINE_SESSIONS,
    PHASE30_NEWS_SURPRISE_TRANSFORM,
    PHASE30_ORDER_WRITES,
    PHASE30_PAPER_SUBMITS,
    PHASE30_POLICY_CONTRACT_VERSION,
    PHASE30_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_WRITES,
    PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
    PHASE30_SOURCE_PHASE29_MERGE,
    phase30_policy_fingerprint,
)


EXPECTED_POLICY_FINGERPRINT = (
    "341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8"
)
EXPECTED_FEASIBILITY_FINGERPRINT = (
    "04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312"
)
EXPECTED_CANDIDATES = (
    "news_shock_aligned_continuation_long",
    "news_shock_aligned_continuation_short",
    "news_shock_counterreaction_reversal_long",
    "news_shock_counterreaction_reversal_short",
)


def main() -> None:
    policy_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase30_policy.py"
    ).read_text(encoding="utf-8")
    acquisition_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase30_acquisition.py"
    ).read_text(encoding="utf-8")
    runner_source = (
        PROJECT_ROOT / "scripts" / "run_phase30_news_acquisition.py"
    ).read_text(encoding="utf-8")
    spec_path = PROJECT_ROOT / "docs" / "phase30_scientific_contract.md"
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else ""

    start, end = phase30_news_acquisition_bounds()
    candidate_ids = tuple(candidate.candidate_id for candidate in PHASE30_CANDIDATES)
    mutation_values = (
        PHASE30_PROVIDER_WRITES,
        PHASE30_BROKER_READS,
        PHASE30_BROKER_WRITES,
        PHASE30_ORDER_WRITES,
        PHASE30_PAPER_SUBMITS,
        PHASE30_LIVE_WRITES,
        PHASE30_AUTOMATION_WRITES,
    )
    forbidden_acquisition_tokens = (
        "directional_return",
        "forward_return",
        "future_close",
        "outcome_evidence",
        "read_parquet",
        "duckdb_connection",
        "phase26_observations",
    )
    forbidden_external_authority_tokens = (
        "packages.brokers",
        "packages.execution",
        "submit_order",
        "place_order",
        "paper_submit",
        "live_write",
    )

    checks = {
        "policy_contract_present": bool(PHASE30_POLICY_CONTRACT_VERSION),
        "policy_fingerprint_exact": phase30_policy_fingerprint()
        == EXPECTED_POLICY_FINGERPRINT,
        "feasibility_lineage_exact": PHASE30_SOURCE_FEASIBILITY_FINGERPRINT
        == EXPECTED_FEASIBILITY_FINGERPRINT
        and phase30_feasibility_fingerprint() == EXPECTED_FEASIBILITY_FINGERPRINT,
        "phase29_merge_lineage_exact": PHASE30_SOURCE_PHASE29_MERGE
        == "87c9450e1b21606b83489f16ff326235ae92eb2b",
        "exact_four_hypotheses": candidate_ids == EXPECTED_CANDIDATES,
        "metadata_only_news_alpha": PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS
        == ("id", "published_utc", "tickers")
        and PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY is False
        and PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY is False,
        "provider_text_not_authorized_in_policy": all(
            token not in policy_source
            for token in (
                'score_field="title"',
                'score_field="description"',
                'score_field="insights"',
            )
        ),
        "event_timing_buffer_frozen": PHASE30_DECISION_BUFFER_MINUTES == 30,
        "news_baseline_frozen": PHASE30_NEWS_BASELINE_SESSIONS == 20
        and PHASE30_NEWS_SURPRISE_TRANSFORM
        == (
            "log1p(current_unique_article_count)-"
            "mean(log1p(previous_20_session_counts_with_zeros))"
        ),
        "current_reaction_field_is_observation_time_daily_return": PHASE30_CURRENT_REACTION_FIELD
        == "d1_return_1",
        "global_holm_family_exact": PHASE30_MULTIPLE_TESTING_METHOD
        == "HOLM_BONFERRONI_GLOBAL_4",
        "finalist_cardinality_and_no_runner_up_frozen": PHASE30_MAX_FINALISTS_PER_DIRECTION
        == 1
        and PHASE30_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_returns_finalist_only": PHASE30_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED
        is False,
        "external_mutation_authority_zero": all(value == 0 for value in mutation_values)
        and PHASE30_AUTOMATIC_BROKER_FAILOVER is False,
        "full_acquisition_contract_present": bool(PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION),
        "full_acquisition_bounds_exact": start.isoformat()
        == "2021-07-16T00:00:00+00:00"
        and end.isoformat() == "2026-08-11T23:59:59.999999+00:00",
        "monthly_acquisition_is_resumable": len(phase30_news_shard_windows()) > 1
        and "resumed_shards" in acquisition_source
        and "metadata_path" in acquisition_source,
        "monthly_shard_completeness_fails_closed": "all_monthly_shards_nonempty"
        in acquisition_source
        and "all_monthly_shards_have_ticker_linked_news" in acquisition_source,
        "acquisition_reconciles_authorized_feasibility_metadata": (
            "feasibility_metadata_reconciled_" in acquisition_source
            and "authorized news metadata drifted from immutable feasibility evidence"
            in acquisition_source
            and "feasibility_evidence_path" in acquisition_source
        ),
        "acquisition_reuses_accepted_news_adapter": "MassivePhase30NewsClient"
        in acquisition_source
        and ".news_window(" in acquisition_source,
        "acquisition_has_no_market_outcome_reader": not any(
            token in acquisition_source.lower() for token in forbidden_acquisition_tokens
        ),
        "acquisition_has_no_broker_execution_authority": not any(
            token in acquisition_source.lower() for token in forbidden_external_authority_tokens
        ),
        "runner_states_frozen_hypotheses_and_unread_outcomes": (
            "Scientific hypotheses: FROZEN (4 total; global Holm family = 4)"
            in runner_source
            and "Target/protected market outcomes: FORBIDDEN / UNREAD" in runner_source
        ),
        "scientific_spec_present": spec_path.is_file(),
        "scientific_spec_locks_metadata_only_boundary": (
            "FROZEN BEFORE ANY PHASE30 MARKET-OUTCOME READ" in spec_text
            and "authorized news alpha fields: `id`, `published_utc`, `tickers`" in spec_text
            and "Exactly four frozen hypotheses" in spec_text
            and "runner-up substitution: forbidden" in spec_text
        ),
    }

    print(f"Phase 30 feasibility fingerprint: {phase30_feasibility_fingerprint()}")
    print(f"Phase 30 policy fingerprint: {phase30_policy_fingerprint()}")
    print(f"Phase 30 scientific policy contract: {PHASE30_POLICY_CONTRACT_VERSION}")
    print(f"Phase 30 acquisition contract: {PHASE30_NEWS_ACQUISITION_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit(
            "Phase 30 frozen scientific contract validation failed: " + ", ".join(failed)
        )
    print("Phase 30 frozen scientific contract: PASS")


if __name__ == "__main__":
    main()
