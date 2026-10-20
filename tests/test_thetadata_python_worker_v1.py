from __future__ import annotations

import builtins
from datetime import date
import sys
from types import ModuleType

import pytest

import pandas as pd

import scripts.thetadata_python_worker_v1 as worker


def test_worker_preflight_is_zero_provider_request_contract():
    result = worker.preflight()

    assert result["ok"] is True
    assert result["provider_requests"] == 0
    assert result["thetadata_tested_version"] == "1.0.12"
    assert isinstance(result["environment_fingerprint"], str)
    assert len(result["environment_fingerprint"]) == 64
    assert "protobuf" in result["environment_packages"]


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
    runtime.environment_fingerprint = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
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
    assert result["environment_fingerprint"] == "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

def test_sdk_inspection_does_not_construct_a_client_or_request_data(monkeypatch):
    module = ModuleType("thetadata")
    class FakeThetaClient:
        def __init__(self, **kwargs):
            pytest.fail("SDK compatibility preflight must not instantiate the client")

        def option_at_time_quote(self, **kwargs):
            pytest.fail("SDK compatibility preflight must not request quote data")

        def option_history_open_interest(self, **kwargs):
            pytest.fail("SDK compatibility preflight must not request OI data")

        def option_history_binomial_greeks_first_order(self, **kwargs):
            pytest.fail("SDK compatibility preflight must not request Greeks data")

    module.ThetaClient = FakeThetaClient
    monkeypatch.setitem(sys.modules, "thetadata", module)
    monkeypatch.setattr(worker, "_library_version", lambda: "1.0.12")
    report = worker.inspect_sdk_method_contract()
    assert report["compatible"] is True
    assert report["provider_requests"] == 0
    assert set(report["method_statuses"]) == set(worker.ALLOWED_METHOD_ARGUMENTS)
    assert set(report["method_statuses"].values()) == {
        "DYNAMIC_KEYWORDS_ACCEPTED_UNVERIFIED"
    }


def test_sdk_inspection_rejects_missing_method_without_client_construction(monkeypatch):
    module = ModuleType("thetadata")
    class IncompleteThetaClient:
        def option_at_time_quote(self, *, symbol):
            raise AssertionError("method invoked")
        def option_history_open_interest(self, **kwargs):
            raise AssertionError("method invoked")

    module.ThetaClient = IncompleteThetaClient
    monkeypatch.setitem(sys.modules, "thetadata", module)
    monkeypatch.setattr(worker, "_library_version", lambda: "1.0.12")
    report = worker.inspect_sdk_method_contract()
    assert report["compatible"] is False
    assert report["method_statuses"]["option_at_time_quote"] == "KEYWORDS_NOT_ACCEPTED"
    assert report["method_statuses"]["option_history_binomial_greeks_first_order"] == "MISSING_METHOD"
    assert report["provider_requests"] == 0


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("option_history_eod", {"symbol": "SPY"}),
        ("option_at_time_quote", {"symbol": "SPY", "api_key": "should-not-pass"}),
        ("option_history_open_interest", {"symbol": "SPY", "status": "unknown"}),
    ],
)
def test_worker_rejects_unapproved_methods_or_keywords_before_sdk_auth(name, kwargs):
    runtime = worker.Runtime()
    runtime.ensure = lambda: pytest.fail("invalid operation cannot construct/authenticate SDK")
    with pytest.raises(RuntimeError, match="THETADATA_"):
        runtime.request(name, kwargs)


def test_root_dotenv_key_detected_without_exposing_value(tmp_path, monkeypatch):
    # The user's actual secret is never used or printed in this fixture.
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(worker.API_KEY_ENV, raising=False)
    monkeypatch.delenv(worker.CREDENTIALS_FILE_ENV, raising=False)
    fake_secret = "unit-test-secret-not-a-real-key"
    file = tmp_path / ".env"
    file.write_text("THETADATA_API_KEY=" + fake_secret + "\n", encoding="utf-8")

    source, present = worker._auth_source()
    assert (source, present) == ("THETADATA_DOTENV_API_KEY", True)
    status = worker.preflight()
    assert status["auth_source"] == "THETADATA_DOTENV_API_KEY"
    assert status["auth_material_present"] is True
    assert status["provider_requests"] == 0
    assert fake_secret not in str(status)

    # A literal empty assignment does not establish any credentials.
    file.write_text("THETADATA_API_KEY=\n", encoding="utf-8")
    assert worker._auth_source() == ("NOT_OBSERVED_LOCALLY", False)

def test_sdk_import_reports_bounded_missing_dependency_without_sdk_creation(monkeypatch):
    monkeypatch.setattr(worker, "_library_version", lambda: "1.0.12")
    original = builtins.__import__

    def import_failing(name, *args, **kwargs):
        if name == "thetadata":
            raise ModuleNotFoundError(
                "Sensitive import traceback context must not be repeated",
                name="grpc._cython.cygrpc",
            )
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_failing)
    result = worker.inspect_sdk_method_contract()
    assert result["status"] == "SDK_IMPORT_FAILED_ModuleNotFoundError"
    assert result["missing_module"] == "grpc._cython.cygrpc"
    assert result["compatible"] is False
    assert result["provider_requests"] == 0
    assert "Sensitive" not in str(result)


def test_sdk_import_rejects_untrusted_module_name_in_diagnostics():
    bad = ModuleNotFoundError(
        "API key may be in an exception message",
        name="../.env?THETADATA_API_KEY=do-not-share",
    )
    assert worker._safe_missing_module_name(bad) is None
    assert worker._safe_missing_module_name(
        ModuleNotFoundError("missing", name="zstandard.backend_c")
    ) == "zstandard.backend_c"
    assert worker._safe_missing_module_name(
        ModuleNotFoundError("missing", name="x" * 101)
    ) is None
