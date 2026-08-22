from __future__ import annotations

import pandas as pd

from packages.analogues.policy import PHASE12_BOOTSTRAP_DRAWS
from packages.analogues.scenarios import build_empirical_path_scenarios, deterministic_seed


def _paths(rows: int) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "direction_return_1": [((x % 7) - 3) / 100.0 for x in range(rows)],
            "direction_return_2": [((x % 9) - 4) / 90.0 for x in range(rows)],
            "direction_return_3": [((x % 11) - 5) / 80.0 for x in range(rows)],
        }
    )


def test_scenario_seed_is_stable_and_identity_bound() -> None:
    first = deterministic_seed(instrument_id="FIGI-1", as_of_date="2026-08-14", direction="bullish")
    second = deterministic_seed(instrument_id="FIGI-1", as_of_date="2026-08-14", direction="bullish")
    changed = deterministic_seed(instrument_id="FIGI-2", as_of_date="2026-08-14", direction="bullish")
    assert first == second
    assert first != changed


def test_empirical_path_bootstrap_is_exactly_reproducible() -> None:
    paths = _paths(60)
    first = build_empirical_path_scenarios(
        paths,
        instrument_id="FIGI-1",
        as_of_date="2026-08-14",
        direction="bullish",
    )
    second = build_empirical_path_scenarios(
        paths,
        instrument_id="FIGI-1",
        as_of_date="2026-08-14",
        direction="bullish",
    )
    assert first == second
    assert first.available is True
    assert first.draw_count == PHASE12_BOOTSTRAP_DRAWS
    assert first.session_3 is not None
    assert first.max_adverse_excursion is not None
    assert first.max_favorable_excursion is not None


def test_scenarios_fail_closed_when_path_support_is_too_small() -> None:
    result = build_empirical_path_scenarios(
        _paths(49),
        instrument_id="FIGI-1",
        as_of_date="2026-08-14",
        direction="bearish",
    )
    assert result.available is False
    assert result.draw_count == 0
    assert result.source_path_rows == 49
    assert result.session_1 is None
    assert result.reason_codes == ("PATH_ROWS_BELOW_PREREGISTERED_MINIMUM",)
