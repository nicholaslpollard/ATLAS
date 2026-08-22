from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from packages.analogues.phase12_closeout import (
    PHASE12_NEXT_PHASE,
    phase12_acceptance_checks,
)
from packages.analogues.policy import PHASE12_SIMILARITY_FEATURES
from packages.schemas.deep_research import (
    AnalogueDistribution,
    AnalogueQuality,
    DeepResearchCase,
    EmpiricalPathScenarios,
)
from packages.schemas.discovery_score import DiscoveryDirection


def test_zero_candidate_noop_is_a_valid_phase12_acceptance() -> None:
    research = {
        "pass": True,
        "promoted_input_count": 0,
        "research_case_count": 0,
        "historical_source_accessed": False,
        "no_candidate_disposition": "NO_PHASE11_PROMOTED_CANDIDATES",
        "research_only_not_trade_signal": True,
        "trade_geometry_present": False,
        "production_ml_writes": 0,
        "broker_writes": 0,
    }
    validation = {
        "pass": True,
        "production_ml_writes": 0,
        "broker_writes": 0,
        "checks": {
            "accepted_phase11_input_reverified": True,
            "preregistered_policy_exact": True,
            "case_evidence_independently_recomputed": True,
        },
    }
    checks = phase12_acceptance_checks(research=research, validation=validation)
    assert all(checks.values())
    assert PHASE12_NEXT_PHASE == "PHASE_13_CONTEXT_INSTRUMENT_GEOMETRY_PORTFOLIO_RISK"


def test_deep_research_schema_refuses_complete_status_with_insufficient_analogues() -> None:
    values = {name: 0.0 for name in PHASE12_SIMILARITY_FEATURES}
    with pytest.raises(ValidationError):
        DeepResearchCase(
            instrument_id="FIGI-1",
            ticker="XYZ",
            as_of_date=date(2026, 8, 14),
            direction=DiscoveryDirection.BULLISH,
            phase11_candidate_sha256="a" * 64,
            research_source_fingerprint="b" * 64,
            similarity_feature_names=PHASE12_SIMILARITY_FEATURES,
            current_feature_values=values,
            eligible_pool_rows=10,
            analogue_distribution=AnalogueDistribution(rows=10, unique_instruments=5),
            analogue_quality=AnalogueQuality(
                status="INSUFFICIENT",
                analogue_count=10,
                unique_instruments=5,
                path_rows=10,
                path_coverage=1.0,
                reason_codes=("ANALOGUE_COUNT_BELOW_PREREGISTERED_MINIMUM",),
            ),
            scenarios=EmpiricalPathScenarios(
                available=False,
                draw_count=0,
                seed=1,
                source_path_rows=10,
                reason_codes=("PATH_ROWS_BELOW_PREREGISTERED_MINIMUM",),
            ),
            analogue_artifact_path="analogues.parquet",
            analogue_artifact_sha256="c" * 64,
            path_artifact_path="paths.parquet",
            path_artifact_sha256="d" * 64,
            research_complete=True,
            reason_codes=("DEEP_RESEARCH_EVIDENCE_LIMITED",),
        )
