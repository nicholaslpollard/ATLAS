from __future__ import annotations

from dataclasses import replace

from packages.data.czar28_connectivity_preflight import (
    PreflightProbeResult,
    classify_preflight,
)


def _result(
    name: str,
    *,
    status: str = "PASS",
    health_status: str | None = None,
) -> PreflightProbeResult:
    return PreflightProbeResult(
        name=name,
        path="options/health" if name == "health" else "options/chain",
        params={},
        status=status,
        http_status=200 if status == "PASS" else 502,
        row_count=None if name == "health" else (1 if status == "PASS" else None),
        transport_attempts=1 if status == "PASS" else 3,
        provider_limit="1000",
        provider_remaining="999",
        provider_reset="0",
        health_status=health_status,
        upstream_status="CONNECTED" if name == "health" else None,
        error=None if status == "PASS" else "upstream_error",
    )


def test_preflight_pass_requires_all_four_stages() -> None:
    assert classify_preflight(
        [
            _result("health", health_status="ok"),
            _result("current_chain"),
            _result("recent_expired_chain"),
            _result("deep_expired_chain"),
            _result("deep_expired_eod"),
        ]
    ) == "PREFLIGHT_PASS"


def test_preflight_distinguishes_deep_history_failure() -> None:
    assert classify_preflight(
        [
            _result("health", health_status="ok"),
            _result("current_chain"),
            _result("recent_expired_chain"),
            _result("deep_expired_chain", status="ERROR"),
            _result("deep_expired_eod"),
        ]
    ) == "DEEP_EOD_AVAILABLE_CHAIN_LIMITATION"


def test_preflight_distinguishes_current_chain_failure() -> None:
    assert classify_preflight(
        [
            _result("health", health_status="ok"),
            _result("current_chain", status="ERROR"),
        ]
    ) == "CURRENT_CHAIN_UNAVAILABLE"


def test_preflight_detects_degraded_health() -> None:
    assert classify_preflight(
        [_result("health", health_status="degraded")]
    ) == "PROVIDER_HEALTH_DEGRADED"


def test_preflight_requires_connected_upstream() -> None:
    health = replace(
        _result("health", health_status="ok"),
        upstream_status="DISCONNECTED",
    )
    assert classify_preflight([health]) == "PROVIDER_HEALTH_DEGRADED"


def test_preflight_distinguishes_deep_eod_failure() -> None:
    assert classify_preflight(
        [
            _result("health", health_status="ok"),
            _result("current_chain"),
            _result("recent_expired_chain"),
            _result("deep_expired_chain", status="ERROR"),
            _result("deep_expired_eod", status="ERROR"),
        ]
    ) == "DEEP_HISTORY_UNAVAILABLE"


def test_preflight_health_uses_public_health_host(monkeypatch, tmp_path) -> None:
    from types import SimpleNamespace

    from packages.data import czar28_connectivity_preflight as preflight
    from packages.providers.czar28.client import CZAR28_HEALTH_BASE_URL, Czar28Response

    calls = []

    def fake_request(path, **kwargs):
        calls.append((path, kwargs))
        return Czar28Response(
            http_status=200,
            payload={
                "status": "ok",
                "upstream": {"mdds_status": "CONNECTED"},
            },
            headers={},
            response_bytes=10,
            elapsed_seconds=0.01,
            transport_attempts=1,
        )

    report = preflight.run_czar28_connectivity_preflight_v1(
        SimpleNamespace(project_root=tmp_path),
        request_json=fake_request,
    )

    assert calls[0][0] == "options/health"
    assert calls[0][1]["authenticate"] is False
    assert calls[0][1]["base_url"] == CZAR28_HEALTH_BASE_URL
    assert report["results"][0]["health_status"] == "ok"
    assert report["results"][0]["upstream_status"] == "CONNECTED"
