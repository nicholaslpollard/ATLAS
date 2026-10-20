from __future__ import annotations

import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
)
import packages.providers.thetadata.preflight as module
import scripts.qualify_thetadata_candidate_source_pipeline_v1 as pipeline


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
        "environment_fingerprint": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "sdk_contract_compatible": True,
        "sdk_contract_status": "EXPECTED_METHOD_SIGNATURES_PRESENT",
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
    assert result.sdk_contract_compatible is True
    assert result.sdk_contract_status == "EXPECTED_METHOD_SIGNATURES_PRESENT"
    assert result.provider_environment_fingerprint == "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
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
        "environment_fingerprint": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "sdk_contract_compatible": True,
        "sdk_contract_status": "EXPECTED_METHOD_SIGNATURES_PRESENT",
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
        "environment_fingerprint": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
        "sdk_contract_compatible": True,
        "sdk_contract_status": "EXPECTED_METHOD_SIGNATURES_PRESENT",
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

def test_sdk_method_contract_is_a_hard_readiness_gate(tmp_path):
    provider_python = tmp_path / "python.exe"
    provider_python.write_bytes(b"placeholder")
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    payload = {
        "ok": True,
        "python_version": "3.12.5",
        "python_meets_3_12": True,
        "thetadata_installed": True,
        "thetadata_version": "1.0.12",
        "environment_fingerprint": "a" * 64,
        "sdk_contract_compatible": False,
        "sdk_contract_status": "SDK_METHOD_CONTRACT_UNQUALIFIED",
        "auth_source": "THETADATA_API_KEY_ENV",
        "auth_material_present": True,
        "provider_requests": 0,
    }
    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        provider_python=provider_python,
        runner=_runner(payload),
    )
    assert result.source_plan_valid
    assert result.enrichment_plan_valid
    assert result.plans_linked
    assert not result.sdk_contract_compatible
    assert not result.ready_for_bounded_source_qualification
    assert result.next_action == "INSPECT_PINNED_THETADATA_SDK_METHOD_SIGNATURES"
    assert result.provider_requests == 0


@pytest.mark.parametrize(
    "allowed,provider_requests,next_action",
    [
        (False, 0, "CONFIGURE_THETADATA_AUTH"),
        (False, 0, "INSTALL_PINNED_THETADATA_PROVIDER_DEPENDENCIES"),
        (False, 0, "REPAIR_ATLAS_PLAN_LINKAGE"),
        (True, 1, "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"),
    ],
)
def test_qualification_internal_preflight_stops_before_provider_reads(
    tmp_path, monkeypatch, allowed, provider_requests, next_action
):
    """Authorization flags cannot bypass a failed or nonzero-read preflight."""
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    source_path = tmp_path / "source.json"
    enrichment_path = tmp_path / "enrichment.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")
    enrichment_path.write_text(json.dumps(enrichment), encoding="utf-8")

    fake_settings = SimpleNamespace(
        assert_external_storage_binding=lambda family: None,
    )
    monkeypatch.setattr(pipeline, "load_settings", lambda *args: fake_settings)
    monkeypatch.setattr(pipeline, "close_all_workers", lambda: None)
    monkeypatch.setattr(
        pipeline,
        "run_thetadata_preflight_v1",
        lambda **kwargs: SimpleNamespace(
            ready_for_bounded_source_qualification=allowed,
            provider_requests=provider_requests,
            next_action=next_action,
        ),
    )
    monkeypatch.setattr(
        pipeline,
        "run_thetadata_candidate_surface_qualification_v1",
        lambda *args, **kwargs: pytest.fail("Quote provider read is forbidden"),
    )
    monkeypatch.setattr(
        pipeline,
        "run_thetadata_open_interest_qualification_v1",
        lambda *args, **kwargs: pytest.fail("OI provider read is forbidden"),
    )

    result = pipeline.main(
        [
            "--source-plan", str(source_path),
            "--enrichment-plan", str(enrichment_path),
            "--authorize-provider-reads",
            "--confirm-thetadata-standard",
        ]
    )
    assert result == 3


def test_qualification_internal_preflight_passes_only_readiness_contract(monkeypatch, capsys):
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    observed = []

    def fake_preflight(*, source_plan, enrichment_plan):
        observed.append((source_plan, enrichment_plan))
        return SimpleNamespace(
            ready_for_bounded_source_qualification=True,
            provider_requests=0,
            next_action="READY_FOR_BOUNDED_SOURCE_QUALIFICATION",
        )

    monkeypatch.setattr(pipeline, "run_thetadata_preflight_v1", fake_preflight)
    pipeline.require_offline_source_readiness(source, enrichment)
    assert observed == [(source, enrichment)]
    assert "offline_preflight=PASSED" in capsys.readouterr().out
