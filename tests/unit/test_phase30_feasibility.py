from __future__ import annotations

from pathlib import Path

import pytest

from packages.backtesting.phase30_feasibility import (
    PHASE30_ALPHA_HYPOTHESES_FROZEN,
    PHASE30_PROBE_WINDOWS,
    PHASE30_SOURCE_PHASE29_MERGE,
    Phase30FeasibilityError,
    _immutable_write,
    _jsonl_text,
    phase30_feasibility_fingerprint,
)


def test_phase30_feasibility_contract_is_preperformance_and_bound_to_phase29_merge() -> None:
    assert PHASE30_SOURCE_PHASE29_MERGE == "87c9450e1b21606b83489f16ff326235ae92eb2b"
    assert PHASE30_ALPHA_HYPOTHESES_FROZEN is False
    assert len(phase30_feasibility_fingerprint()) == 64
    assert [window.label for window in PHASE30_PROBE_WINDOWS] == [
        "research_start",
        "development_end",
        "protected_start",
        "protected_end",
    ]
    assert PHASE30_PROBE_WINDOWS[0].start_utc == "2021-08-16T00:00:00Z"
    assert PHASE30_PROBE_WINDOWS[-1].end_utc == "2026-08-11T23:59:59Z"


def test_phase30_jsonl_is_deterministic_for_equivalent_key_order() -> None:
    first = ({"id": "a", "published_utc": "2021-08-16T10:00:00Z", "tickers": ["A"]},)
    second = ({"tickers": ["A"], "published_utc": "2021-08-16T10:00:00Z", "id": "a"},)
    assert _jsonl_text(first) == _jsonl_text(second)


def test_phase30_immutable_evidence_accepts_identical_replay_and_rejects_drift(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.jsonl"
    first_sha = _immutable_write(path, "{\"id\":\"a\"}\n")
    second_sha = _immutable_write(path, "{\"id\":\"a\"}\n")
    assert first_sha == second_sha

    with pytest.raises(Phase30FeasibilityError, match="evidence drifted"):
        _immutable_write(path, "{\"id\":\"b\"}\n")
