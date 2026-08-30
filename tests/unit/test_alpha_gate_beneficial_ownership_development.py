from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from packages.backtesting.alpha_gate_beneficial_ownership_development import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    chronological_boundaries,
    development_implementation_fingerprint,
    holm_bonferroni,
    protected_source_precheck,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_INTERNAL_PURGE_SESSIONS,
    BENEFICIAL_OWNERSHIP_PROTECTED_MIN_EVENT_ROWS,
    BENEFICIAL_OWNERSHIP_PROTECTED_MIN_SIGNAL_SESSIONS,
    BENEFICIAL_OWNERSHIP_PROTECTED_MIN_UNIQUE_INSTRUMENTS,
)


def test_development_implementation_fingerprint_is_exact() -> None:
    assert development_implementation_fingerprint() == (
        BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
    )
    assert BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT == (
        "0e90a65e6e2f6a7d7206296901054de3a2c97aaa204c80927a963c298c81060d"
    )


def test_chronological_partition_has_frozen_purge() -> None:
    start = date(2021, 8, 16)
    sessions = tuple(start + timedelta(days=index) for index in range(850))
    boundary = chronological_boundaries(sessions)
    assert len(boundary.purge_sessions) == BENEFICIAL_OWNERSHIP_INTERNAL_PURGE_SESSIONS
    assert boundary.selection_end < boundary.purge_sessions[0]
    assert boundary.purge_sessions[-1] < boundary.internal_start


def test_holm_is_global_and_stops_after_first_nonrejection() -> None:
    result = holm_bonferroni(
        {
            "a": 0.001,
            "b": 0.020,
            "c": 0.030,
            "d": 0.040,
        },
        alpha=0.05,
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is False
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False


def test_protected_precheck_reads_source_counts_only() -> None:
    rows = []
    start = date(2025, 4, 4)
    candidate = "initial_13d_5_to_10_long"
    required_rows = BENEFICIAL_OWNERSHIP_PROTECTED_MIN_EVENT_ROWS
    for index in range(required_rows):
        rows.append(
            {
                "candidate_id": candidate,
                "decision_session": (start + timedelta(days=index)).isoformat(),
                "instrument_id": f"instrument-{index % max(BENEFICIAL_OWNERSHIP_PROTECTED_MIN_UNIQUE_INSTRUMENTS, 1)}",
            }
        )
    result = protected_source_precheck(pd.DataFrame.from_records(rows), candidate)
    assert result["raw_rows"] == required_rows
    assert result["signal_sessions"] >= BENEFICIAL_OWNERSHIP_PROTECTED_MIN_SIGNAL_SESSIONS
    assert result["unique_instruments"] >= BENEFICIAL_OWNERSHIP_PROTECTED_MIN_UNIQUE_INSTRUMENTS
    assert result["pass"] is True
    assert result["protected_return_rows_read"] == 0
