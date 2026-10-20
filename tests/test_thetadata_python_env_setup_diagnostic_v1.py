from __future__ import annotations

"""Offline, synthetic diagnostics for isolated ThetaData package setup.

No ThetaData credentials, provider environment, or market-data calls.
"""

import json

from scripts import setup_thetadata_python_env_v1 as setup


def test_missing_sdk_interface_returns_actionable_failure_codes():
    sample = {
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": setup.TARGET_LIBRARY_VERSION,
        "environment_packages": {"python-dotenv": setup.TARGET_DOTENV_DISTRIBUTION_VERSION},
        "sdk_contract_compatible": False,
        "sdk_contract_status": "SDK_METHOD_CONTRACT_UNQUALIFIED",
        "sdk_method_statuses": {
            "option_at_time_quote": "EXPLICIT_KEYWORDS_PRESENT",
            "option_history_open_interest": "KEYWORDS_NOT_ACCEPTED",
            "option_history_binomial_greeks_first_order": "MISSING_METHOD",
        },
        "environment_fingerprint": "a" * 64,
        "auth_material_present": False,
        "secret_canary": "should-not-ever-appear",
    }
    report = setup._safe_provider_diagnostic(sample)
    assert report["failed_checks"] == ["SDK_METHOD_INTERFACE_MISMATCH"]
    assert report["sdk_method_statuses"]["option_history_open_interest"] == "KEYWORDS_NOT_ACCEPTED"
    assert report["provider_requests"] == 0
    assert "secret_canary" not in json.dumps(report)
    assert "should-not-ever-appear" not in json.dumps(report)
    assert "auth_material_present" not in json.dumps(report)


def test_missing_auth_does_not_block_package_only_environment_setup():
    package_valid = {
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": setup.TARGET_LIBRARY_VERSION,
        "environment_packages": {"python-dotenv": setup.TARGET_DOTENV_DISTRIBUTION_VERSION},
        "sdk_contract_compatible": True,
        "environment_fingerprint": "a" * 64,
        "auth_material_present": False,
    }
    assert setup._failed_pinned_contract_checks(package_valid) == ()


def test_all_failed_checks_are_reported_without_secrets():
    sample = {
        "python_meets_3_12": False,
        "thetadata_installed": True,
        "thetadata_version": "0.1",
        "environment_packages": {"python-dotenv": setup.TARGET_DOTENV_DISTRIBUTION_VERSION},
        "sdk_contract_compatible": False,
        "environment_fingerprint": "invalid",
        "auth_material_present": True,
        "auth_source": "THETADATA_API_KEY_ENV",
    }
    assert setup._failed_pinned_contract_checks(sample) == (
        "PYTHON_BELOW_3_12",
        "SDK_PIN_MISMATCH",
        "SDK_METHOD_INTERFACE_MISMATCH",
        "INVALID_ENVIRONMENT_FINGERPRINT",
    )

def test_import_failure_propagates_only_safe_module_identifier():
    sample = {
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": setup.TARGET_LIBRARY_VERSION,
        "environment_packages": {"python-dotenv": setup.TARGET_DOTENV_DISTRIBUTION_VERSION},
        "sdk_contract_compatible": False,
        "sdk_contract_status": "SDK_IMPORT_FAILED_ModuleNotFoundError",
        "sdk_missing_module": "grpc._cython.cygrpc",
        "environment_fingerprint": "a" * 64,
        "api_key": "test-canary-should-never-appear",
    }
    result = setup._safe_provider_diagnostic(sample)
    assert result["sdk_missing_module"] == "grpc._cython.cygrpc"
    assert result["failed_checks"] == ["SDK_METHOD_INTERFACE_MISMATCH"]
    assert "test-canary" not in json.dumps(result)

    sample["sdk_missing_module"] = "../.env?THETADATA_API_KEY=test-canary"
    result = setup._safe_provider_diagnostic(sample)
    assert result["sdk_missing_module"] is None
    assert "test-canary" not in json.dumps(result)

def test_companion_dotenv_missing_triggers_pinned_install_even_if_sdk_is_present():
    before = {
        "thetadata_installed": True,
        "thetadata_version": setup.TARGET_LIBRARY_VERSION,
        "environment_packages": {"python-dotenv": None},
        "python_meets_3_12": True,
        "sdk_contract_compatible": False,
        "environment_fingerprint": "a" * 64,
    }
    assert setup._provider_dependency_install_needed(before) is True
    assert "PYTHON_DOTENV_DISTRIBUTION_NOT_PINNED" in setup._failed_pinned_contract_checks(before)
    diag = setup._safe_provider_diagnostic(before)
    assert diag["python_dotenv_version"] == "NONE"
    assert diag["provider_requests"] == 0

    after = {
        **before,
        "environment_packages": {"python-dotenv": setup.TARGET_DOTENV_DISTRIBUTION_VERSION},
        "sdk_contract_compatible": True,
    }
    assert setup._provider_dependency_install_needed(after) is False
    assert setup._failed_pinned_contract_checks(after) == ()


def test_setup_requirements_pin_companion_distribution_exactly():
    lines = [
        row.strip()
        for row in setup.REQUIREMENTS.read_text(encoding="utf-8").splitlines()
        if row.strip() and not row.lstrip().startswith("#")
    ]
    assert "thetadata==" + setup.TARGET_LIBRARY_VERSION in lines
    assert "python-dotenv==" + setup.TARGET_DOTENV_DISTRIBUTION_VERSION in lines
