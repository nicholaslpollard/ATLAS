from datetime import date, timedelta

import pandas as pd

from packages.backtesting.alpha_gate_finra_short_interest_development import (
    FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    chronological_boundaries,
    development_implementation_fingerprint,
    holm_bonferroni,
    protected_source_precheck,
)


def test_finra_development_implementation_fingerprint_is_frozen() -> None:
    assert development_implementation_fingerprint() == (
        FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
    )
    assert FINRA_SHORT_INTEREST_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT == (
        "f5b99a52bf0e9d101b53493e0012a7a60d24b301f904d4b9958dc03638432a5f"
    )


def test_chronological_boundaries_have_exact_63_session_purge() -> None:
    start = date(2021, 1, 1)
    sessions = tuple(start + timedelta(days=index) for index in range(400))
    boundary = chronological_boundaries(sessions)
    assert boundary.selection_session_count == 280
    assert len(boundary.purge_sessions) == 63
    assert boundary.internal_session_count == 57
    assert boundary.selection_end < boundary.purge_sessions[0]
    assert boundary.purge_sessions[-1] < boundary.internal_start


def test_holm_bonferroni_is_global_and_stops_after_first_failure() -> None:
    result = holm_bonferroni(
        {"a": 0.001, "b": 0.02, "c": 0.03, "d": 0.04}, alpha=0.05
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is False
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False
    assert result["a"]["threshold"] == 0.0125


def test_protected_source_precheck_reads_no_returns() -> None:
    rows = []
    start = date(2025, 4, 4)
    for session_index in range(16):
        session = start + timedelta(days=session_index)
        for row_index in range(20):
            rows.append(
                {
                    "candidate_id": "candidate",
                    "decision_session": session.isoformat(),
                    "instrument_id": f"id-{session_index}-{row_index}",
                }
            )
    result = protected_source_precheck(pd.DataFrame(rows), "candidate")
    assert result["raw_rows"] == 320
    assert result["signal_sessions"] == 16
    assert result["unique_instruments"] == 320
    assert result["protected_return_rows_read"] == 0
    assert result["pass"] is True
