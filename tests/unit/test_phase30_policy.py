from __future__ import annotations

from packages.backtesting.phase30_policy import (
    PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS,
    PHASE30_CANDIDATES,
    PHASE30_CURRENT_REACTION_FIELD,
    PHASE30_DECISION_BUFFER_MINUTES,
    PHASE30_MULTIPLE_TESTING_METHOD,
    PHASE30_NEWS_BASELINE_SESSIONS,
    PHASE30_NEWS_SURPRISE_TRANSFORM,
    PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY,
    PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY,
    PHASE30_SOURCE_FEASIBILITY_FINGERPRINT,
    phase30_policy_fingerprint,
)


def test_phase30_policy_is_exact_finite_metadata_only_family() -> None:
    assert phase30_policy_fingerprint() == (
        "341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8"
    )
    assert PHASE30_SOURCE_FEASIBILITY_FINGERPRINT == (
        "04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312"
    )
    assert PHASE30_AUTHORIZED_NEWS_ALPHA_FIELDS == ("id", "published_utc", "tickers")
    assert PHASE30_PROVIDER_CONTENT_ALPHA_AUTHORITY is False
    assert PHASE30_PROVIDER_INSIGHTS_ALPHA_AUTHORITY is False
    assert PHASE30_DECISION_BUFFER_MINUTES == 30
    assert PHASE30_NEWS_BASELINE_SESSIONS == 20
    assert PHASE30_CURRENT_REACTION_FIELD == "d1_return_1"
    assert PHASE30_NEWS_SURPRISE_TRANSFORM == (
        "log1p(current_unique_article_count)-"
        "mean(log1p(previous_20_session_counts_with_zeros))"
    )
    assert PHASE30_MULTIPLE_TESTING_METHOD == "HOLM_BONFERRONI_GLOBAL_4"
    assert [candidate.candidate_id for candidate in PHASE30_CANDIDATES] == [
        "news_shock_aligned_continuation_long",
        "news_shock_aligned_continuation_short",
        "news_shock_counterreaction_reversal_long",
        "news_shock_counterreaction_reversal_short",
    ]
    assert [candidate.direction for candidate in PHASE30_CANDIDATES] == [
        "LONG",
        "SHORT",
        "LONG",
        "SHORT",
    ]
    assert [candidate.required_reaction_sign for candidate in PHASE30_CANDIDATES] == [
        "POSITIVE",
        "NEGATIVE",
        "NEGATIVE",
        "POSITIVE",
    ]
