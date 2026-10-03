from __future__ import annotations

import json
from pathlib import Path
import subprocess

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
)
import packages.providers.thetadata.preflight as module


def _source_plan() -> dict:
    body = {
        "contract": SOURCE_PLAN_CONTRACT,
        "decision_spot_fingerprint": "1" * 64,
    }
    body["plan_fingerprint"] = _fingerprint(body)
    return body


def _enrichment_plan(source: dict) -> dict:
    body = {
        "contract": ENRICHMENT_PLAN_CONTRACT,
        "source_plan_fingerprint": source["plan_fingerprint"],
        "decision_spot_fingerprint": source["decision_spot_fingerprint"],
    }
    body["enrichment_plan_fingerprint"] = _fingerprint(body)
    return body


def _runner(payload: dict, *, returncode: int = 0):
    def run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [],
            returncode=returncode,
            stdout=json.dumps(payload),
            stderr="",
        )
    return run


def test_plan_linkage_passes_for_matching_signed_plans():
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    assert module.validate_plans(source, enrichment) == (True, True, True)


def test_missing_provider_python_is_not_ready(tmp_path):
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        provider_python=tmp_path / "missing-python.exe",
    )

    assert result.provider_python_present is False
    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "SETUP_ISOLATED_THETADATA_PROVIDER_ENVIRONMENT"
    assert result.provider_requests == 0


def test_ready_provider_environment(tmp_path):
    provider_python = tmp_path / "python.exe"
    provider_python.write_bytes(b"placeholder")
    payload = {
        "ok": True,
        "python_version": "3.14.0",
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": "1.0.12",
        "thetadata_tested_version": "1.0.12",
        "thetadata_version_supported": True,
        "auth_source": "THETADATA_API_KEY_ENV",
        "auth_material_present": True,
        "provider_requests": 0,
    }
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        provider_python=provider_python,
        runner=_runner(payload),
    )

    assert result.provider_python_present is True
    assert result.provider_python_meets_3_12 is True
    assert result.library_installed is True
    assert result.library_version == "1.0.12"
    assert result.library_version_matches_tested is True
    assert result.auth_material_present is True
    assert result.plans_linked is True
    assert result.provider_requests == 0
    assert result.ready_for_bounded_source_qualification is True
    assert result.next_action == "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"
    assert any("protobuf>=6" in item for item in result.detail)
    assert any("Terminal and Java are not required" in item for item in result.detail)


def test_wrong_library_version_blocks(tmp_path):
    provider_python = tmp_path / "python.exe"
    provider_python.write_bytes(b"placeholder")
    payload = {
        "ok": True,
        "python_version": "3.14.0",
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": "1.0.11",
        "thetadata_version_supported": True,
        "auth_source": "THETADATA_API_KEY_ENV",
        "auth_material_present": True,
        "provider_requests": 0,
    }
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        provider_python=provider_python,
        runner=_runner(payload),
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "INSTALL_PINNED_THETADATA_PROVIDER_DEPENDENCIES"


def test_missing_auth_blocks(tmp_path):
    provider_python = tmp_path / "python.exe"
    provider_python.write_bytes(b"placeholder")
    payload = {
        "ok": True,
        "python_version": "3.14.0",
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": "1.0.12",
        "thetadata_version_supported": True,
        "auth_source": "NOT_OBSERVED_LOCALLY",
        "auth_material_present": False,
        "provider_requests": 0,
    }
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        provider_python=provider_python,
        runner=_runner(payload),
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "CONFIGURE_THETADATA_AUTH"


def test_invalid_worker_protocol_blocks(tmp_path):
    provider_python = tmp_path / "python.exe"
    provider_python.write_bytes(b"placeholder")
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        provider_python=provider_python,
        runner=_runner({"ok": False}),
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.provider_requests == 0
