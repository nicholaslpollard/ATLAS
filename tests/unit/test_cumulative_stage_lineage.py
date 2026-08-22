from __future__ import annotations

from datetime import date

from packages.validation.cumulative_lifecycle_integrity import (
    CumulativeFoundationLifecycleAwareAuditor,
)
from packages.validation.cumulative_stage_lineage import (
    CumulativeFoundationRetainedStageAuditor,
    transition_dates,
    transitions_are_lifecycle_backed,
)


def _row(input_state: str, output_state: str) -> dict[str, object]:
    return {
        "input_state_fingerprint": input_state,
        "output_state_fingerprint": output_state,
    }


def test_retained_stage_auditor_preserves_lifecycle_and_identity_checks() -> None:
    assert issubclass(
        CumulativeFoundationRetainedStageAuditor,
        CumulativeFoundationLifecycleAwareAuditor,
    )


def test_transition_dates_detect_only_nonadjacent_state_changes() -> None:
    d1 = date(2016, 10, 31)
    d2 = date(2016, 11, 1)
    d3 = date(2016, 11, 2)
    rows = {
        d1: _row("genesis", "state-a"),
        d2: _row("state-after-lifecycle", "state-b"),
        d3: _row("state-b", "state-c"),
    }
    assert transition_dates(rows) == {d2}


def test_lifecycle_backing_accepts_only_transition_on_event_date() -> None:
    d1 = date(2016, 10, 31)
    d2 = date(2016, 11, 1)
    d3 = date(2016, 11, 2)
    rows = {
        d1: _row("genesis", "state-a"),
        d2: _row("state-after-lifecycle", "state-b"),
        d3: _row("state-b", "state-c"),
    }
    passed, unbacked = transitions_are_lifecycle_backed(rows, {d2})
    assert passed is True
    assert unbacked == []


def test_lifecycle_backing_rejects_unexplained_state_transition() -> None:
    d1 = date(2016, 10, 31)
    d2 = date(2016, 11, 1)
    rows = {
        d1: _row("genesis", "state-a"),
        d2: _row("unexpected-state", "state-b"),
    }
    passed, unbacked = transitions_are_lifecycle_backed(rows, set())
    assert passed is False
    assert unbacked == [d2]
