from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.thetadata_candidate_surface_enrichment_plan_v1 import (
    CONTRACT as ENRICHMENT_PLAN_CONTRACT,
)
from packages.data.thetadata_candidate_surface_plan_v1 import (
    CONTRACT as SOURCE_PLAN_CONTRACT,
)
import packages.providers.thetadata.preflight as module


class _Socket:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


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


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ('openjdk version "21.0.5" 2024-10-15', 21),
        ('java version "23" 2025-09-16', 23),
        ("openjdk 25 2025-09-16", 25),
        ('openjdk version "17.0.12"', 17),
        ("unparseable output", None),
    ],
)
def test_parse_java_major(text, expected):
    assert module.parse_java_major(text) == expected


def test_inspect_java_accepts_21_plus():
    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["java", "-version"],
            returncode=0,
            stdout="",
            stderr='openjdk version "21.0.5"',
        )

    found, major, detail = module.inspect_java(runner)

    assert found is True
    assert major == 21
    assert "major=21" in detail


def test_terminal_socket_loopback_only():
    with pytest.raises(module.ThetaDataPreflightError, match="loopback"):
        module.inspect_terminal_socket(host="example.com")


def test_terminal_socket_reachability_closes_socket():
    sock = _Socket()

    def connector(address, timeout):
        assert address == ("127.0.0.1", 25503)
        assert timeout == 1.0
        return sock

    reachable, detail = module.inspect_terminal_socket(connector=connector)

    assert reachable is True
    assert sock.closed is True
    assert "reachable" in detail


def test_auth_source_prefers_env_without_revealing_value(tmp_path):
    source, present = module.inspect_auth_source(
        terminal_dir=tmp_path,
        environ={"THETADATA_API_KEY": "super-secret"},
    )

    assert present is True
    assert source == "THETADATA_API_KEY_ENV"
    assert "super-secret" not in source


def test_auth_source_detects_terminal_dotenv(tmp_path):
    (tmp_path / ".env").write_text(
        'THETADATA_API_KEY="abc123"\nOTHER=1\n',
        encoding="utf-8",
    )

    source, present = module.inspect_auth_source(
        terminal_dir=tmp_path,
        environ={},
    )

    assert present is True
    assert source == "TERMINAL_DOTENV_API_KEY"


def test_auth_source_detects_creds_file(tmp_path):
    (tmp_path / "creds.txt").write_text(
        "user@example.com\npassword\n",
        encoding="utf-8",
    )

    source, present = module.inspect_auth_source(
        terminal_dir=tmp_path,
        environ={},
    )

    assert present is True
    assert source == "TERMINAL_CREDS_FILE"


def test_plan_linkage_passes_for_matching_signed_plans():
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    assert module.validate_plans(source, enrichment) == (True, True, True)


def test_plan_linkage_fails_when_enrichment_points_elsewhere():
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    enrichment["source_plan_fingerprint"] = "f" * 64
    enrichment.pop("enrichment_plan_fingerprint")
    enrichment["enrichment_plan_fingerprint"] = _fingerprint(enrichment)

    source_valid, enrichment_valid, linked = module.validate_plans(
        source,
        enrichment,
    )

    assert source_valid is True
    assert enrichment_valid is True
    assert linked is False


def test_preflight_ready_with_java_terminal_and_linked_plans():
    source = _source_plan()
    enrichment = _enrichment_plan(source)
    sock = _Socket()

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["java", "-version"],
            returncode=0,
            stdout="",
            stderr='openjdk version "21.0.5"',
        )

    def connector(address, timeout):
        return sock

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        java_runner=runner,
        socket_connector=connector,
        environ={},
    )

    assert result.java_meets_minimum is True
    assert result.terminal_reachable is True
    assert result.plans_linked is True
    assert result.provider_requests == 0
    assert result.ready_for_bounded_source_qualification is True
    assert result.next_action == "READY_FOR_BOUNDED_SOURCE_QUALIFICATION"


def test_preflight_requires_java_21():
    source = _source_plan()
    enrichment = _enrichment_plan(source)

    def runner(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=["java", "-version"],
            returncode=0,
            stdout="",
            stderr='openjdk version "17.0.12"',
        )

    def connector(address, timeout):
        return _Socket()

    result = module.run_thetadata_preflight_v1(
        source_plan=source,
        enrichment_plan=enrichment,
        java_runner=runner,
        socket_connector=connector,
        environ={"THETADATA_API_KEY": "x"},
    )

    assert result.ready_for_bounded_source_qualification is False
    assert result.next_action == "INSTALL_OR_UPGRADE_JAVA_21_PLUS"
