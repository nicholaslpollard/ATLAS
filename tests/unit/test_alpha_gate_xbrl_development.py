from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from packages.backtesting.alpha_gate_xbrl_development import (
    XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
    chronological_boundaries,
    development_implementation_fingerprint,
    holm_bonferroni,
    protected_source_precheck,
)
from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_INTERNAL_PURGE_SESSIONS,
)


def test_development_implementation_fingerprint_is_exact() -> None:
    assert development_implementation_fingerprint() == XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT
    assert XBRL_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT == (
        "3b5a02113ceab0065ea9a03020cc5266222e67ba39abe36311a6959e7e2d488f"
    )


def test_chronological_split_has_exact_63_session_internal_purge() -> None:
    sessions = tuple(date(2021, 1, 1) + timedelta(days=index) for index in range(600))
    boundaries = chronological_boundaries(sessions)
    assert len(boundaries.purge_sessions) == XBRL_INTERNAL_PURGE_SESSIONS == 63
    assert boundaries.selection_end < boundaries.purge_sessions[0]
    assert boundaries.purge_sessions[-1] < boundaries.internal_start


def test_holm_bonferroni_is_global_and_step_down() -> None:
    result = holm_bonferroni(
        {
            "a": 0.001,
            "b": 0.009,
            "c": 0.02,
            "d": 0.20,
            "e": 0.30,
            "f": 0.40,
        },
        alpha=0.05,
    )
    assert result["a"]["rejected_null"] is True
    assert result["b"]["rejected_null"] is True
    assert result["c"]["rejected_null"] is False
    assert result["d"]["rejected_null"] is False
    assert result["e"]["rejected_null"] is False
    assert result["f"]["rejected_null"] is False


def test_protected_source_precheck_can_pass_without_return_columns() -> None:
    rows = []
    for index in range(75):
        rows.append(
            {
                "candidate_id": "gross_profitability_improvement_long",
                "decision_session": date(2025, 4, 4) + timedelta(days=index % 30),
                "instrument_id": f"instrument-{index % 25:02d}",
            }
        )
    frame = pd.DataFrame.from_records(rows)
    assert not {"stock_return", "spy_return", "primary_gross_return"}.intersection(frame.columns)
    result = protected_source_precheck(frame, "gross_profitability_improvement_long")
    assert result["raw_rows"] == 75
    assert result["signal_sessions"] == 30
    assert result["unique_instruments"] == 25
    assert result["pass"] is True
    assert result["protected_return_rows_read"] == 0
