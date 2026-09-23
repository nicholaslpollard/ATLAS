from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.provider_source_qualification import stable_fingerprint
from packages.providers.czar28.client import (
    Czar28Error,
    Czar28QuotaExhausted,
    Czar28Response,
    get_json,
)


CZAR28_CONNECTIVITY_PREFLIGHT_V1 = {
    "contract_id": "atlas-czar28-connectivity-preflight-v1",
    "purpose": (
        "bounded operational diagnostic before the frozen Czar28 historical-option "
        "source qualification; does not alter or consume scientific authority"
    ),
    "probes": [
        {"name": "health", "path": "options/health", "params": {}},
        {
            "name": "current_chain",
            "path": "options/chain",
            "params": {"root": "SPY", "exp": "20261016"},
        },
        {
            "name": "recent_expired_chain",
            "path": "options/chain",
            "params": {"root": "SPY", "exp": "20250620"},
        },
        {
            "name": "deep_expired_chain",
            "path": "options/chain",
            "params": {"root": "SPY", "exp": "20160617"},
        },
        {
            "name": "deep_expired_eod",
            "path": "options/quote/eod",
            "params": {
                "root": "SPY",
                "exp": "20160617",
                "strike": "200",
                "right": "C",
                "start_date": "20160601",
                "end_date": "20160617",
            },
        },
    ],
    "max_transport_attempts_per_probe": 3,
    "authority": {
        "historical_data_authority": False,
        "strategy_evidence": False,
        "paper": False,
        "live": False,
        "provider_writes": False,
        "broker_writes": False,
    },
}

CZAR28_CONNECTIVITY_PREFLIGHT_V1_FINGERPRINT = stable_fingerprint(
    CZAR28_CONNECTIVITY_PREFLIGHT_V1
)


@dataclass(frozen=True, slots=True)
class PreflightProbeResult:
    name: str
    path: str
    params: dict[str, str]
    status: str
    http_status: int | None
    row_count: int | None
    transport_attempts: int
    provider_limit: str | None
    provider_remaining: str | None
    provider_reset: str | None
    health_status: str | None
    upstream_status: str | None
    error: str | None


def _header(headers: dict[str, str], name: str) -> str | None:
    lowered = {str(k).lower(): str(v) for k, v in headers.items()}
    return lowered.get(name.lower())


def _row_count(payload: dict[str, Any]) -> int | None:
    response = payload.get("response")
    if isinstance(response, list):
        return len(response)
    return None


def _health_fields(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    status = payload.get("status")
    upstream = payload.get("upstream")
    upstream_status: str | None = None
    if isinstance(upstream, dict) and upstream.get("mdds_status") is not None:
        upstream_status = str(upstream.get("mdds_status"))
    return (
        None if status is None else str(status),
        upstream_status,
    )


def _report_root(settings: AtlasSettings) -> Path:
    return (
        settings.project_root
        / "data"
        / "research"
        / "provider_qualification"
        / "czar28"
        / "connectivity_preflight_v1"
        / "reports"
    )


def classify_preflight(
    results: list[PreflightProbeResult],
) -> str:
    by_name = {result.name: result for result in results}
    health = by_name.get("health")
    current = by_name.get("current_chain")
    recent = by_name.get("recent_expired_chain")
    deep = by_name.get("deep_expired_chain")
    deep_eod = by_name.get("deep_expired_eod")

    if health is None or health.status != "PASS":
        return "PROVIDER_HEALTH_UNAVAILABLE"
    if health.health_status not in (None, "ok"):
        return "PROVIDER_HEALTH_DEGRADED"
    if current is None or current.status != "PASS":
        return "CURRENT_CHAIN_UNAVAILABLE"
    if recent is None or recent.status != "PASS":
        return "RECENT_HISTORY_UNAVAILABLE"
    if deep_eod is None or deep_eod.status != "PASS":
        return "DEEP_HISTORY_UNAVAILABLE"
    if deep is None or deep.status != "PASS":
        return "DEEP_EOD_AVAILABLE_CHAIN_LIMITATION"
    return "PREFLIGHT_PASS"


def run_czar28_connectivity_preflight_v1(
    settings: AtlasSettings,
    *,
    request_json: Callable[..., Czar28Response] = get_json,
) -> dict[str, object]:
    results: list[PreflightProbeResult] = []
    probes = list(CZAR28_CONNECTIVITY_PREFLIGHT_V1["probes"])
    total = len(probes)

    for index, raw_probe in enumerate(probes, start=1):
        probe = dict(raw_probe)
        name = str(probe["name"])
        path = str(probe["path"])
        params = {str(k): str(v) for k, v in dict(probe["params"]).items()}
        rendered = (
            f"{name}: {path}"
            + (f" {params}" if params else "")
        )
        print(f"  [{index}/{total}] {rendered}", flush=True)
        try:
            response = request_json(
                path,
                params=params,
                authenticate=(name != "health"),
                idempotency_key=stable_fingerprint(
                    {
                        "contract": CZAR28_CONNECTIVITY_PREFLIGHT_V1_FINGERPRINT,
                        "name": name,
                        "path": path,
                        "params": params,
                    }
                ),
                max_attempts=int(
                    CZAR28_CONNECTIVITY_PREFLIGHT_V1[
                        "max_transport_attempts_per_probe"
                    ]
                ),
            )
            health_status, upstream_status = _health_fields(response.payload)
            row_count = _row_count(response.payload)
            status = (
                "PASS"
                if response.http_status == 200
                and (
                    name == "health"
                    or (row_count is not None and row_count > 0)
                )
                else "NO_DATA"
            )
            result = PreflightProbeResult(
                name=name,
                path=path,
                params=params,
                status=status,
                http_status=response.http_status,
                row_count=row_count,
                transport_attempts=response.transport_attempts,
                provider_limit=_header(response.headers, "X-RateLimit-Limit"),
                provider_remaining=_header(
                    response.headers, "X-RateLimit-Remaining"
                ),
                provider_reset=_header(response.headers, "X-RateLimit-Reset"),
                health_status=health_status,
                upstream_status=upstream_status,
                error=None,
            )
            print(
                f"      {status}: http={response.http_status} "
                f"rows={row_count} attempts={response.transport_attempts} "
                f"health={health_status} upstream={upstream_status} "
                f"remaining={result.provider_remaining}",
                flush=True,
            )
        except (Czar28QuotaExhausted, Czar28Error) as exc:
            result = PreflightProbeResult(
                name=name,
                path=path,
                params=params,
                status="ERROR",
                http_status=exc.http_status,
                row_count=None,
                transport_attempts=int(exc.transport_attempts or 0),
                provider_limit=None,
                provider_remaining=None,
                provider_reset=None,
                health_status=None,
                upstream_status=None,
                error=f"{type(exc).__name__}: {exc}",
            )
            print(
                f"      ERROR: http={exc.http_status} "
                f"attempts={exc.transport_attempts} "
                f"error={exc.error_code or str(exc)}",
                flush=True,
            )
        results.append(result)

        # Fail early when the provider cannot answer the health/current path.
        # Continue after recent/deep-chain failures so the direct deep EOD
        # endpoint can distinguish chain-discovery failure from price-data failure.
        if name in {"health", "current_chain"} and result.status != "PASS":
            break

    classification = classify_preflight(results)
    report = {
        "contract_id": CZAR28_CONNECTIVITY_PREFLIGHT_V1["contract_id"],
        "contract_fingerprint": CZAR28_CONNECTIVITY_PREFLIGHT_V1_FINGERPRINT,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "classification": classification,
        "results": [
            {
                "name": result.name,
                "path": result.path,
                "params": result.params,
                "status": result.status,
                "http_status": result.http_status,
                "row_count": result.row_count,
                "transport_attempts": result.transport_attempts,
                "provider_limit": result.provider_limit,
                "provider_remaining": result.provider_remaining,
                "provider_reset": result.provider_reset,
                "health_status": result.health_status,
                "upstream_status": result.upstream_status,
                "error": result.error,
            }
            for result in results
        ],
        "total_physical_http_attempts": sum(
            result.transport_attempts for result in results
        ),
        "authority": CZAR28_CONNECTIVITY_PREFLIGHT_V1["authority"],
    }
    report["evidence_fingerprint"] = stable_fingerprint(report)

    report_root = _report_root(settings)
    report_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    report_path = report_root / f"{stamp}.json"
    atomic_write_text(
        report_path,
        json.dumps(report, indent=2, sort_keys=True) + "\n",
    )
    report["report_path"] = str(report_path.resolve())
    return report
