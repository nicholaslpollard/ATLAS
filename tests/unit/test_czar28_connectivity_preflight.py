from __future__ import annotations

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
        ]
    ) == "PREFLIGHT_PASS"


def test_preflight_distinguishes_deep_history_failure() -> None:
    assert classify_preflight(
        [
            _result("health", health_status="ok"),
            _result("current_chain"),
            _result("recent_expired_chain"),
            _result("deep_expired_chain", status="ERROR"),
        ]
    ) == "DEEP_HISTORY_UNAVAILABLE"


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
