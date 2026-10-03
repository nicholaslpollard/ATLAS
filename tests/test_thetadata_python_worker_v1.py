from __future__ import annotations

from datetime import date

import pandas as pd

import scripts.thetadata_python_worker_v1 as worker


def test_worker_preflight_is_zero_provider_request_contract():
    result = worker.preflight()

    assert result["ok"] is True
    assert result["provider_requests"] == 0
    assert result["thetadata_tested_version"] == "1.0.12"


def test_worker_converts_date_arguments_for_library():
    converted = worker._convert_kwargs(
        "option_at_time_quote",
        {
            "start_date": "2025-01-06",
            "end_date": "20250106",
            "expiration": "2025-02-21",
            "symbol": "AAPL",
        },
    )

    assert converted["start_date"] == date(2025, 1, 6)
    assert converted["end_date"] == date(2025, 1, 6)
    assert converted["expiration"] == date(2025, 2, 21)


def test_worker_preserves_expiration_wildcard():
    converted = worker._convert_kwargs(
        "option_history_open_interest",
        {
            "date": "2025-01-06",
            "expiration": "*",
        },
    )

    assert converted["date"] == date(2025, 1, 6)
    assert converted["expiration"] == "*"


def test_worker_dataframe_serialization_is_json_safe():
    frame = pd.DataFrame(
        [
            {
                "expiration": date(2025, 2, 21),
                "strike": 100.0,
                "right": "call",
            }
        ]
    )
    assert worker._records(frame) == [
        {
            "expiration": "2025-02-21",
            "strike": 100.0,
            "right": "call",
        }
    ]


def test_worker_maps_no_data_exception_to_explicit_empty_surface():
    class NoDataFoundError(Exception):
        pass

    class FakeClient:
        def option_at_time_quote(self, **kwargs):
            raise NoDataFoundError("no historical rows")

    runtime = worker.Runtime()
    runtime.version = "1.0.12"
    runtime.ensure = lambda: FakeClient()

    result = runtime.request(
        "option_at_time_quote",
        {
            "symbol": "AAPL",
            "start_date": "2025-01-06",
            "end_date": "2025-01-06",
            "time_of_day": "09:35:00.000",
            "expiration": "*",
            "strike": "*",
            "right": "call",
            "max_dte": 75,
        },
    )

    assert result["ok"] is True
    assert result["rows"] == []
    assert result["explicit_no_data"] is True
    assert result["library_version"] == "1.0.12"
