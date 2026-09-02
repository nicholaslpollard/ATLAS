from __future__ import annotations

import math
from datetime import date

import pytest

from packages.backtesting.literature_momseason_development import (
    MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT,
    MOMSEASON_DEVELOPMENT_CONTRACT,
    _target_unit_id,
    one_way_turnover,
    select_equal_weight_deciles,
)
from packages.backtesting.literature_momseason_research_freeze import (
    MOMSEASON_LONG_SHORT_QUANTILE,
)


def _rows(count: int) -> list[dict[str, object]]:
    return [
        {
            "instrument_id": f"id-{index:03d}",
            "predictor_value": float(index),
        }
        for index in range(count)
    ]


def test_development_contract_is_bound_to_accepted_freeze() -> None:
    assert MOMSEASON_DEVELOPMENT_CONTRACT.endswith("no-protected")
    assert MOMSEASON_ACCEPTED_FREEZE_FINGERPRINT == (
        "745ff247ecf9404f19aaf67450fdaf08fcec525e3a62c781f30a91662a901cfb"
    )
    assert MOMSEASON_LONG_SHORT_QUANTILE == 0.10


def test_decile_selection_is_equal_count_and_disjoint() -> None:
    long_leg, short_leg = select_equal_weight_deciles(_rows(100))
    assert len(long_leg) == 10
    assert len(short_leg) == 10
    assert [row["instrument_id"] for row in short_leg] == [
        f"id-{index:03d}" for index in range(10)
    ]
    assert [row["instrument_id"] for row in long_leg] == [
        f"id-{index:03d}" for index in range(90, 100)
    ]
    assert not (
        {row["instrument_id"] for row in long_leg}
        & {row["instrument_id"] for row in short_leg}
    )


def test_decile_ties_use_stable_instrument_id() -> None:
    rows = [
        {"instrument_id": f"id-{index:03d}", "predictor_value": 0.0}
        for index in reversed(range(20))
    ]
    long_leg, short_leg = select_equal_weight_deciles(rows)
    assert [row["instrument_id"] for row in short_leg] == ["id-000", "id-001"]
    assert [row["instrument_id"] for row in long_leg] == ["id-018", "id-019"]


def test_decile_selection_rejects_too_small_population() -> None:
    with pytest.raises(ValueError):
        select_equal_weight_deciles(_rows(9))


def test_one_way_turnover_initial_portfolio_is_one() -> None:
    assert one_way_turnover(None, {"A": 0.5, "B": 0.5}) == 1.0


def test_one_way_turnover_full_replacement_is_one() -> None:
    assert math.isclose(
        one_way_turnover(
            {"A": 0.5, "B": 0.5},
            {"C": 0.5, "D": 0.5},
        ),
        1.0,
    )


def test_one_way_turnover_partial_overlap() -> None:
    assert math.isclose(
        one_way_turnover(
            {"A": 0.5, "B": 0.5},
            {"A": 0.5, "C": 0.5},
        ),
        0.5,
    )


def test_one_way_turnover_requires_fully_invested_weights() -> None:
    with pytest.raises(ValueError):
        one_way_turnover(None, {"A": 0.75})


def test_target_unit_id_binds_endpoint_and_plan() -> None:
    first = _target_unit_id(
        endpoint_session=date(2024, 1, 31),
        batch_index=0,
        symbols=("AAPL", "MSFT"),
        plan_fingerprint="abc",
    )
    second = _target_unit_id(
        endpoint_session=date(2024, 2, 29),
        batch_index=0,
        symbols=("AAPL", "MSFT"),
        plan_fingerprint="abc",
    )
    third = _target_unit_id(
        endpoint_session=date(2024, 1, 31),
        batch_index=0,
        symbols=("AAPL", "MSFT"),
        plan_fingerprint="def",
    )
    assert first != second
    assert first != third
