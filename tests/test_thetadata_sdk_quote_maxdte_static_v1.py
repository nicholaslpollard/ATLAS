from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from scripts import audit_thetadata_sdk_quote_maxdte_static_v1 as sdk


def fake_direct(*, max_dte: int, symbol: str):
    return other_client(symbol=symbol, max_dte=max_dte)


def fake_dict(*, max_dte: int, symbol: str):
    settings = {"symbol": symbol, "max_dte": max_dte}
    return settings


def fake_declared_only(*, max_dte: int, symbol: str):
    return symbol


def fake_dynamic(**kwargs):
    return other_client(**kwargs)


def other_client(**kwargs):
    raise AssertionError("Inspection must NEVER invoke the SDK or a fake client")


def test_direct_method_source_has_candidate_only_never_claims_wire_proof():
    report = sdk.classify_method_source(fake_direct)
    assert report["explicit_max_dte_parameter"] is True
    assert report["source_available"] is True
    assert report["max_dte_keyword_forward_calls"] == 1
    assert report["static_forwarding_classification"] == (
        "DIRECT_STATIC_FORWARDING_CANDIDATE_NOT_WIRE_PROOF"
    )
    assert len(report["source_sha256"]) == 64


def test_dict_forwarding_detected_without_calling_fake():
    report = sdk.classify_method_source(fake_dict)
    assert report["max_dte_dict_value_forwards"] == 1
    assert report["static_forwarding_classification"] == (
        "DIRECT_STATIC_FORWARDING_CANDIDATE_NOT_WIRE_PROOF"
    )


def test_signature_without_body_usage_does_not_prove_forwarding():
    report = sdk.classify_method_source(fake_declared_only)
    assert report["explicit_max_dte_parameter"] is True
    assert report["max_dte_keyword_forward_calls"] == 0
    assert report["max_dte_dict_value_forwards"] == 0
    assert report["static_forwarding_classification"] == (
        "PARAMETER_BODY_FORWARDING_NOT_OBSERVED"
    )


def test_kwargs_only_is_not_maxdte_semantics_proof():
    report = sdk.classify_method_source(fake_dynamic)
    assert report["explicit_max_dte_parameter"] is False
    assert report["var_keyword_parameter"] is True
    assert report["dynamic_kwargs_call_sites"] >= 1
    assert report["static_forwarding_classification"] == (
        "PARAMETER_BODY_FORWARDING_NOT_OBSERVED"
    )


def _sample_child_report():
    return {
        "contract": sdk.CONTRACT,
        "status": "OFFLINE_INSTALLED_SDK_STATIC_INSPECTION",
        "library_version": sdk.TARGET,
        "method": sdk.EXPECTED_METHOD,
        "method_callable": True,
        "explicit_max_dte_parameter": True,
        "var_keyword_parameter": False,
        "source_available": True,
        "source_sha256": "a" * 64,
        "source_line_count": 25,
        "max_dte_name_references": 3,
        "max_dte_keyword_forward_calls": 1,
        "max_dte_dict_value_forwards": 0,
        "dynamic_kwargs_call_sites": 0,
        "static_forwarding_classification": (
            "DIRECT_STATIC_FORWARDING_CANDIDATE_NOT_WIRE_PROOF"
        ),
        "provider_requests": 0,
        "client_instances": 0,
    }


def test_parent_reads_only_sanitized_one_shot_report_no_sdk_client(tmp_path, monkeypatch):
    fake_python = tmp_path / "provider-python.exe"
    fake_python.write_bytes(b"fake interpreter path, never executed")
    monkeypatch.setenv("THETADATA_API_KEY", "must_never_reach_child")
    monkeypatch.setenv("ATLAS_THETADATA_PYTHON", "hidden-provider-config")
    monkeypatch.setenv("SOME_OTHER_TOKEN", "no-token-leak")
    captured = []

    def runner(argv, **kwargs):
        captured.append((argv, kwargs))
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(_sample_child_report()),
            stderr="ignored and never displayed",
        )

    report = sdk.inspect_provider_sdk_offline(
        python_path=fake_python, runner=runner
    )
    assert report["provider_requests"] == report["client_instances"] == 0
    assert report["source_available"] is True
    assert len(captured) == 1
    argv, opts = captured[0]
    assert argv[0] == str(fake_python) and argv[-1] == "--isolated-child"
    assert opts["timeout"] == 25
    assert opts["stdin"] == subprocess.DEVNULL
    assert opts["stderr"] == subprocess.DEVNULL
    assert "THETADATA_API_KEY" not in opts["env"]
    assert "ATLAS_THETADATA_PYTHON" not in opts["env"]
    assert "SOME_OTHER_TOKEN" not in opts["env"]
    assert "must_never_reach_child" not in str(captured)


@pytest.mark.parametrize("tamper", [
    {"provider_requests": 1},
    {"client_instances": 1},
    {"library_version": "1.0.13"},
    {"source_sha256": "not-a-hash"},
    {"status": "BLOCKED"},
    {"max_dte_name_references": -1},
    {"extra_source_text": "sensitive arbitrary SDK code"},
])
def test_untrusted_child_report_fails_closed_without_retry(tmp_path, tamper):
    path = tmp_path / "python.exe"
    path.touch()
    report = {**_sample_child_report(), **tamper}
    calls = []

    def runner(argv, **kwargs):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, json.dumps(report))

    with pytest.raises(sdk.StaticSdkAuditError):
        sdk.inspect_provider_sdk_offline(python_path=path, runner=runner)
    assert len(calls) == 1


def test_missing_provider_python_prevents_any_subprocess(tmp_path):
    called = []
    with pytest.raises(sdk.StaticSdkAuditError, match="UNAVAILABLE"):
        sdk.inspect_provider_sdk_offline(
            python_path=tmp_path / "absent", runner=lambda *a, **k: called.append(1)
        )
    assert called == []


def test_nonzero_child_stops_without_outputting_potential_secrets(tmp_path):
    path = tmp_path / "python.exe"
    path.touch()
    called = []
    def runner(argv, **kwargs):
        called.append(argv)
        return subprocess.CompletedProcess(argv, 3, stdout=json.dumps({
            "contract": sdk.CONTRACT, "status": "BLOCKED",
            "provider_requests": 0, "client_instances": 0,
            "error_code": "SDK_CLASS_IMPORT_FAILED_RuntimeError",
        }))
    with pytest.raises(sdk.StaticSdkAuditError, match="BLOCKED"):
        sdk.inspect_provider_sdk_offline(python_path=path, runner=runner)
    assert len(called) == 1
