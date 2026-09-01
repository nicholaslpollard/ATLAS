from __future__ import annotations

from packages.backtesting.research_population_coverage import (
    PopulationCoverageStage,
    PopulationScope,
    assess_population_coverage,
)


def test_full_universe_funnel_proves_scope_and_surfaces_severe_attrition() -> None:
    result = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="eligible_universe",
                rows=1_000_000,
                sessions=250,
                instruments=5_000,
                scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
            ),
            PopulationCoverageStage(
                name="discovery_population",
                rows=20_000,
                sessions=250,
                instruments=1_200,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
            PopulationCoverageStage(
                name="route_eligible",
                rows=12_000,
                sessions=240,
                instruments=900,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
        )
    )

    assert result.valid_contract is True
    assert result.source_scope_proven is True
    assert result.requires_bottleneck_explanation is True
    assert result.bottleneck_stages == ("discovery_population",)
    assert result.transitions[0].row_retention == 0.02


def test_complete_natural_event_source_is_valid_without_every_stock() -> None:
    result = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="all_form4_events",
                rows=2_000_000,
                sessions=1_200,
                instruments=8_000,
                scope=PopulationScope.NATURAL_EVENT_SOURCE,
                grain="event_key",
            ),
            PopulationCoverageStage(
                name="frozen_predictor_events",
                rows=6_000,
                sessions=900,
                instruments=2_000,
                scope=PopulationScope.FILTERED_POPULATION,
                grain="event_key",
            ),
        )
    )

    assert result.valid_contract is True
    assert result.source_scope_proven is True
    assert result.requires_bottleneck_explanation is True


def test_probe_only_source_cannot_claim_complete_research_coverage() -> None:
    result = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="source_probe",
                rows=500,
                sessions=5,
                instruments=300,
                scope=PopulationScope.PROBE_ONLY,
                complete_scope=False,
            ),
            PopulationCoverageStage(
                name="probe_signals",
                rows=100,
                sessions=5,
                instruments=80,
                scope=PopulationScope.FILTERED_POPULATION,
                complete_scope=False,
            ),
        )
    )

    assert result.valid_contract is True
    assert result.source_scope_proven is False


def test_same_grain_filtered_population_cannot_expand() -> None:
    result = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="eligible",
                rows=100,
                scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
            ),
            PopulationCoverageStage(
                name="filtered",
                rows=120,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
        )
    )

    assert result.valid_contract is False


def test_noncomparable_derived_rows_may_exceed_candidate_count() -> None:
    result = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="route_candidates",
                rows=100,
                scope=PopulationScope.FULL_ELIGIBLE_UNIVERSE,
                grain="candidate_key",
            ),
            PopulationCoverageStage(
                name="strategy_signal_rows",
                rows=240,
                scope=PopulationScope.DERIVED_NONCOMPARABLE,
                comparable_to_previous=False,
                grain="candidate_strategy_key",
            ),
        )
    )

    assert result.valid_contract is True
    assert result.transitions[0].row_retention is None


def test_filtered_first_stage_is_not_a_valid_coverage_contract() -> None:
    result = assess_population_coverage(
        (
            PopulationCoverageStage(
                name="already_filtered",
                rows=100,
                scope=PopulationScope.FILTERED_POPULATION,
            ),
        )
    )

    assert result.valid_contract is False
    assert result.source_scope_proven is False
