from __future__ import annotations

from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from packages.backtesting import literature_momseason_development_target_transport as transport


def _runner(rows: list[dict[str, object]], *, allowed: set[date] | None = None):
    runner = object.__new__(transport.MomSeasonDevelopmentResearchTargetTransportSafe)
    runner.allowed_target_sessions = frozenset(allowed or {date(2023, 3, 31)})
    runner.alpaca = SimpleNamespace(cfg=SimpleNamespace(symbol_batch_size=100))
    runner._load_target_plan = lambda: (
        rows,
        {"target_plan_fingerprint": "frozen-plan-fingerprint"},
    )
    runner._target_transport_shared_groups = []
    runner._target_transport_extra_instrument_rows = 0
    runner._target_transport_reported = False
    return runner


def test_same_endpoint_ticker_can_serve_multiple_frozen_instrument_rows() -> None:
    rows = [
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_old_safe",
            "historical_ticker": "SAFE",
        },
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_new_safe",
            "historical_ticker": "SAFE",
        },
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_other",
            "historical_ticker": "AAA",
        },
    ]
    original = deepcopy(rows)
    runner = _runner(rows)

    units = runner.build_units()

    assert rows == original
    assert len(units) == 1
    assert units[0].endpoint_session == date(2023, 3, 31)
    assert units[0].symbols == ("AAA", "SAFE")
    assert runner._target_transport_extra_instrument_rows == 1
    assert runner._target_transport_shared_groups == [
        {
            "endpoint_session": "2023-03-31",
            "historical_ticker": "SAFE",
            "instrument_ids": ["ins_new_safe", "ins_old_safe"],
            "instrument_count": 2,
        }
    ]


def test_source_key_sharing_does_not_merge_distinct_endpoint_rows() -> None:
    rows = [
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_a",
            "historical_ticker": "SAFE",
        },
        {
            "endpoint_session": "2023-04-28",
            "instrument_id": "ins_b",
            "historical_ticker": "SAFE",
        },
    ]
    runner = _runner(rows, allowed={date(2023, 3, 31), date(2023, 4, 28)})

    units = runner.build_units()

    assert [(unit.endpoint_session, unit.symbols) for unit in units] == [
        (date(2023, 3, 31), ("SAFE",)),
        (date(2023, 4, 28), ("SAFE",)),
    ]
    assert runner._target_transport_shared_groups == []


def test_target_transport_still_enforces_frozen_endpoint_whitelist() -> None:
    rows = [
        {
            "endpoint_session": "2023-04-28",
            "instrument_id": "ins_a",
            "historical_ticker": "SAFE",
        }
    ]
    runner = _runner(rows, allowed={date(2023, 3, 31)})

    with pytest.raises(RuntimeError, match="escaped target whitelist"):
        runner.build_units()


def test_target_transport_rejects_empty_ticker() -> None:
    rows = [
        {
            "endpoint_session": "2023-03-31",
            "instrument_id": "ins_a",
            "historical_ticker": "",
        }
    ]
    runner = _runner(rows)

    with pytest.raises(RuntimeError, match="empty historical ticker"):
        runner.build_units()
