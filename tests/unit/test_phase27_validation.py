from __future__ import annotations

from datetime import date

import pandas as pd

from packages.backtesting.phase27_validation import (
    independent_fixed_tail_keys,
    independent_holm,
)


def test_independent_tail_uses_candidate_session_and_fixed_twenty_percent() -> None:
    rows: list[dict[str, object]] = []
    for candidate_id in ("a", "b"):
        for index in range(10):
            rows.append(
                {
                    "candidate_id": candidate_id,
                    "as_of_date": date(2026, 1, 2),
                    "instrument_id": f"{candidate_id}-{index:02d}",
                    "phase27_score": float(index),
                }
            )
    keys = independent_fixed_tail_keys(pd.DataFrame(rows))
    assert keys == {
        ("a", date(2026, 1, 2), "a-08"),
        ("a", date(2026, 1, 2), "a-09"),
        ("b", date(2026, 1, 2), "b-08"),
        ("b", date(2026, 1, 2), "b-09"),
    }


def test_independent_holm_stops_after_first_nonrejection() -> None:
    result = independent_holm(
        {
            "a": 0.001,
            "b": 0.004,
            "c": 0.020,
            "d": 0.021,
            "e": 0.022,
            "f": 0.023,
            "g": 0.024,
            "h": 0.025,
        }
    )
    assert result["a"] is True
    assert result["b"] is True
    assert result["c"] is False
    assert all(result[key] is False for key in ("d", "e", "f", "g", "h"))
