from __future__ import annotations

from packages.backtesting.phase31_acquisition import (
    PHASE31_ACQUISITION_CONTRACT_VERSION,
    PHASE31_EXPECTED_MONTH_SHARDS,
    _partition_global_quarantine,
    phase31_month_shards,
)
from packages.backtesting.phase31_policy import (
    PHASE31_CANDIDATES,
    PHASE31_DEVELOPMENT_LAST_SIGNAL,
    PHASE31_OUTCOME_HORIZON_SESSIONS,
    PHASE31_PROTECTED_LAST_SIGNAL,
    PHASE31_PROTECTED_OUTCOME_END,
    PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE31_RESEARCH_SIGNAL_START,
    PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE31_SOURCE_HISTORY_START,
    phase31_candidate_ids,
    phase31_policy_fingerprint,
)


def test_phase31_scientific_policy_fingerprint_is_frozen() -> None:
    assert phase31_policy_fingerprint() == (
        "e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67"
    )


def test_phase31_has_exactly_four_frozen_candidates() -> None:
    assert phase31_candidate_ids() == (
        "open_market_purchase_long",
        "clustered_open_market_purchase_long",
        "open_market_sale_short",
        "clustered_open_market_sale_short",
    )
    assert len(PHASE31_CANDIDATES) == 4
    assert {candidate.direction for candidate in PHASE31_CANDIDATES} == {"LONG", "SHORT"}
    assert PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED is False
    assert PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False


def test_phase31_twenty_session_boundary_is_explicit() -> None:
    assert PHASE31_OUTCOME_HORIZON_SESSIONS == 20
    assert PHASE31_RESEARCH_SIGNAL_START == "2021-08-16"
    assert PHASE31_DEVELOPMENT_LAST_SIGNAL == "2026-04-13"
    assert PHASE31_PROTECTED_LAST_SIGNAL == "2026-07-14"
    assert PHASE31_PROTECTED_OUTCOME_END == "2026-08-11"


def test_phase31_month_shards_cover_frozen_source_scope() -> None:
    shards = phase31_month_shards()
    assert len(shards) == PHASE31_EXPECTED_MONTH_SHARDS == 62
    assert shards[0].label == "2021-07"
    assert shards[0].start_date == PHASE31_SOURCE_HISTORY_START == "2021-07-16"
    assert shards[0].end_date == "2021-07-31"
    assert shards[-1].label == "2026-08"
    assert shards[-1].start_date == "2026-08-01"
    assert shards[-1].end_date == PHASE31_PROTECTED_OUTCOME_END == "2026-08-11"
    assert len({shard.label for shard in shards}) == len(shards)


def test_phase31_acquisition_is_memory_bounded_and_global_accession_quarantine() -> None:
    assert "memory-bounded-global-accession-quarantine" in PHASE31_ACQUISITION_CONTRACT_VERSION
    rows = (
        {"accession_number": "A", "filing_date": "2023-08-17"},
        {"accession_number": "B", "filing_date": "2023-08-17"},
        {"accession_number": "A", "filing_date": "2023-09-19"},
    )
    authoritative, quarantined = _partition_global_quarantine(rows, {"A"})
    assert [row["accession_number"] for row in authoritative] == ["B"]
    assert [row["accession_number"] for row in quarantined] == ["A", "A"]
