from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Iterable


RESEARCH_POPULATION_COVERAGE_CONTRACT_VERSION = (
    "research-population-coverage-v1-explicit-source-to-signal-funnel"
)


class PopulationScope(StrEnum):
    """Scientific meaning of a population stage.

    FULL_ELIGIBLE_UNIVERSE is appropriate for broad technical/cross-sectional studies.
    NATURAL_EVENT_SOURCE is appropriate when the scientific population is the complete
    event census (for example filings/news/short-interest observations) rather than every
    listed security. PROBE_ONLY may establish source feasibility but cannot prove full
    research coverage. FILTERED_POPULATION and DERIVED_NONCOMPARABLE are downstream stages.
    """

    FULL_ELIGIBLE_UNIVERSE = "FULL_ELIGIBLE_UNIVERSE"
    NATURAL_EVENT_SOURCE = "NATURAL_EVENT_SOURCE"
    FILTERED_POPULATION = "FILTERED_POPULATION"
    PROBE_ONLY = "PROBE_ONLY"
    DERIVED_NONCOMPARABLE = "DERIVED_NONCOMPARABLE"


@dataclass(frozen=True, slots=True)
class PopulationCoverageStage:
    name: str
    rows: int
    sessions: int | None = None
    instruments: int | None = None
    scope: PopulationScope = PopulationScope.FILTERED_POPULATION
    complete_scope: bool = True
    comparable_to_previous: bool = True
    grain: str = "candidate_key"
    source: str = "UNSPECIFIED"


@dataclass(frozen=True, slots=True)
class PopulationCoverageTransition:
    from_stage: str
    to_stage: str
    row_retention: float | None
    comparable: bool
    severe_attrition: bool
    note: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class PopulationCoverageAssessment:
    valid_contract: bool
    source_scope_proven: bool
    requires_bottleneck_explanation: bool
    bottleneck_stages: tuple[str, ...]
    reasons: tuple[str, ...]
    stages: tuple[PopulationCoverageStage, ...]
    transitions: tuple[PopulationCoverageTransition, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "valid_contract": self.valid_contract,
            "source_scope_proven": self.source_scope_proven,
            "requires_bottleneck_explanation": self.requires_bottleneck_explanation,
            "bottleneck_stages": list(self.bottleneck_stages),
            "reasons": list(self.reasons),
            "stages": [
                {
                    **asdict(stage),
                    "scope": stage.scope.value,
                }
                for stage in self.stages
            ],
            "transitions": [transition.to_dict() for transition in self.transitions],
        }


def assess_population_coverage(
    stages: Iterable[PopulationCoverageStage],
    *,
    bottleneck_ratio: float = 0.05,
) -> PopulationCoverageAssessment:
    """Audit an explicit source-to-signal research funnel.

    A severe narrowing is diagnostic, not automatically a scientific failure. The purpose
    is to force the narrowing to be visible and explained rather than allowing a hidden
    sample bottleneck to be mistaken for evidence of absent alpha.
    """

    ordered = tuple(stages)
    if not ordered:
        raise ValueError("at least one population stage is required")
    if not 0.0 < bottleneck_ratio < 1.0:
        raise ValueError("bottleneck_ratio must be between zero and one")

    reasons: list[str] = []
    valid = True
    seen_names: set[str] = set()
    for stage in ordered:
        if not stage.name.strip():
            raise ValueError("population stage names must be nonempty")
        if stage.name in seen_names:
            raise ValueError(f"duplicate population stage name: {stage.name}")
        seen_names.add(stage.name)
        if stage.rows < 0:
            raise ValueError(f"negative row count for stage {stage.name}")
        if stage.sessions is not None and stage.sessions < 0:
            raise ValueError(f"negative session count for stage {stage.name}")
        if stage.instruments is not None and stage.instruments < 0:
            raise ValueError(f"negative instrument count for stage {stage.name}")
        if not stage.grain.strip():
            raise ValueError(f"empty grain for stage {stage.name}")

    first = ordered[0]
    source_scope_proven = bool(
        first.scope
        in {
            PopulationScope.FULL_ELIGIBLE_UNIVERSE,
            PopulationScope.NATURAL_EVENT_SOURCE,
        }
        and first.complete_scope
        and all(stage.complete_scope for stage in ordered)
        and all(stage.scope is not PopulationScope.PROBE_ONLY for stage in ordered)
    )
    if first.scope is PopulationScope.FILTERED_POPULATION:
        valid = False
        reasons.append(
            "first population stage is already filtered; the eligible universe/event source is not explicit"
        )
    elif first.scope is PopulationScope.DERIVED_NONCOMPARABLE:
        valid = False
        reasons.append("first population stage cannot be a derived noncomparable output")
    elif first.scope is PopulationScope.PROBE_ONLY:
        reasons.append("source begins from a feasibility probe; full research coverage is not proven")

    if not first.complete_scope:
        reasons.append("source stage is explicitly incomplete")
    if any(not stage.complete_scope for stage in ordered[1:]):
        reasons.append("one or more downstream stages are incomplete")
    if any(stage.scope is PopulationScope.PROBE_ONLY for stage in ordered[1:]):
        reasons.append("a downstream stage is probe-only; full funnel coverage is not proven")

    transitions: list[PopulationCoverageTransition] = []
    bottlenecks: list[str] = []
    for previous, current in zip(ordered[:-1], ordered[1:], strict=True):
        if not current.comparable_to_previous:
            transitions.append(
                PopulationCoverageTransition(
                    from_stage=previous.name,
                    to_stage=current.name,
                    row_retention=None,
                    comparable=False,
                    severe_attrition=False,
                    note="noncomparable grain; retention ratio intentionally not computed",
                )
            )
            continue

        if current.grain != previous.grain:
            valid = False
            reasons.append(
                f"{previous.name}->{current.name} is marked comparable but grain changes "
                f"from {previous.grain!r} to {current.grain!r}"
            )
            transitions.append(
                PopulationCoverageTransition(
                    from_stage=previous.name,
                    to_stage=current.name,
                    row_retention=None,
                    comparable=True,
                    severe_attrition=False,
                    note="invalid comparable transition because grain changed",
                )
            )
            continue

        if previous.rows == 0:
            if current.rows > 0:
                valid = False
                reasons.append(
                    f"{previous.name}->{current.name} expands from zero rows on the same grain"
                )
            retention = 1.0 if current.rows == 0 else None
        else:
            retention = current.rows / previous.rows
            if retention > 1.0:
                valid = False
                reasons.append(
                    f"{previous.name}->{current.name} expands a supposedly filtered same-grain population "
                    f"({current.rows}>{previous.rows})"
                )

        severe = bool(retention is not None and retention < bottleneck_ratio)
        if severe:
            bottlenecks.append(current.name)
        transitions.append(
            PopulationCoverageTransition(
                from_stage=previous.name,
                to_stage=current.name,
                row_retention=retention,
                comparable=True,
                severe_attrition=severe,
            )
        )

    if source_scope_proven:
        reasons.append("complete source scope is explicit and no probe-only stage is present")
    else:
        reasons.append("complete source-to-signal coverage is not yet proven")
    if bottlenecks:
        reasons.append(
            "severe population narrowing requires an explicit causal explanation before interpreting a negative result"
        )

    return PopulationCoverageAssessment(
        valid_contract=valid,
        source_scope_proven=source_scope_proven,
        requires_bottleneck_explanation=bool(bottlenecks),
        bottleneck_stages=tuple(bottlenecks),
        reasons=tuple(reasons),
        stages=ordered,
        transitions=tuple(transitions),
    )
