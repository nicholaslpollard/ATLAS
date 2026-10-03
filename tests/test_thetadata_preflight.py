from __future__ import annotations

from pathlib import Path

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


def test_auth_source_detects_env():
    source, present = module.inspect_auth_source(
        environ={"THETADATA_API_KEY": "secret"},
    )
    assert present is True
    assert source == "THETADATA_API_KEY_ENV"


def test_auth_source_detects_dotenv_without_exposing_secret(tmp_path):
    path = tmp_path / ".env"
    path.write_text('THETADATA_API_KEY="abc123"\n', encoding="utf-8")

    source, present = module.inspect_auth_source(
        dotenv_path=path,
        environ={},
    )

    assert present is True
    assert source == "THETADATA_DOTENV_API_KEY"
    assert "abc123" not in source


def test_plan_linkage_passes_for_matching_signed_plans():
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    assert module.validate_plans(source, enrichment) == (True, True, True)


def test_preflight_ready_on_python_library_path():
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        python_version=(3, 14),
        library_version="1.0.12",
        environ={"THETADATA_API_KEY": "x"},
    )

    assert result.python_meets_minimum is True
    assert result.library_installed is True
    assert result.library_meets_minimum is True
    assert result.auth_material_present is True
    assert result.plans_linked is True
    assert result.provider_requests == 0
    assert result.ready_for_bounded_source_qualification is True
    assert result.next_action == "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"
    assert any("Terminal and Java are not required" in x for x in result.detail)


def test_preflight_blocks_python_311():
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        python_version=(3, 11),
        library_version="1.0.12",
        environ={"THETADATA_API_KEY": "x"},
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "USE_PYTHON_3_12_PLUS"


def test_preflight_blocks_missing_library():
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        python_version=(3, 14),
        library_version=None,
        environ={"THETADATA_API_KEY": "x"},
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "INSTALL_THETADATA_PYTHON_LIBRARY"


def test_preflight_blocks_missing_auth():
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        python_version=(3, 14),
        library_version="1.0.12",
        environ={},
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "CONFIGURE_THETADATA_AUTH"
