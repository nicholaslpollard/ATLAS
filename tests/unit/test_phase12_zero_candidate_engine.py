from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.analogues.engine import (
    PHASE12_NO_CANDIDATE_DISPOSITION,
    DeepCandidateResearchEngine,
)
from packages.analogues.source import Phase12ResearchInput


class _InputResolver:
    def __init__(self, value: Phase12ResearchInput) -> None:
        self.value = value

    def resolve(self, as_of_date: date | None = None) -> Phase12ResearchInput:
        assert as_of_date in {None, self.value.as_of_date}
        return self.value


class _ForbiddenHistoryResolver:
    def resolve(self) -> object:
        raise AssertionError("zero-candidate Phase 12 run must not open Gate 11-C history")


def test_zero_candidate_engine_never_resolves_expensive_history(tmp_path: Path) -> None:
    day = date(2026, 8, 14)
    research_input = Phase12ResearchInput(
        contract_version="phase12-input-v1-accepted-phase11-promoted-only",
        source_fingerprint="a" * 64,
        as_of_date=day,
        phase11_acceptance_path=tmp_path / "phase11.json",
        phase11_acceptance_sha256="b" * 64,
        current_manifest_path=tmp_path / "current.json",
        current_manifest_sha256="c" * 64,
        promoted_path=tmp_path / "promoted.jsonl",
        promoted_sha256="d" * 64,
        feature_path=tmp_path / "features.parquet",
        feature_sha256="e" * 64,
        canonical_path=tmp_path / "canonical.parquet",
        canonical_sha256="f" * 64,
        promoted_candidates=(),
    )
    engine = DeepCandidateResearchEngine.__new__(DeepCandidateResearchEngine)
    engine.input_resolver = _InputResolver(research_input)
    engine.history_resolver = _ForbiddenHistoryResolver()
    engine.root = tmp_path / "deep_research"

    result = engine.run(as_of_date=day)
    assert result["pass"] is True
    assert result["promoted_input_count"] == 0
    assert result["research_case_count"] == 0
    assert result["historical_source_accessed"] is False
    assert result["no_candidate_disposition"] == PHASE12_NO_CANDIDATE_DISPOSITION
    assert Path(str(result["manifest_path"])).is_file()
