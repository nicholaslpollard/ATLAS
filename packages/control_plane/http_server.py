from __future__ import annotations

import argparse
import ipaddress
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlsplit

from packages.core.settings import load_settings
from packages.schemas.execution import BrokerName

from .phase16_policy import PHASE16_DEFAULT_BIND_HOST
from .session import ControlPlaneSessionGuard
from .status import ControlPlaneStatusError, Phase16StatusService


CONTROL_PLANE_HTTP_CONTRACT_VERSION = (
    "control-plane-http-v1-loopback-get-only-no-cors-host-validated"
)
DEFAULT_CONTROL_PLANE_PORT = 8765


def is_loopback_host(host: str) -> bool:
    text = host.strip().lower()
    if text == "localhost":
        return True
    try:
        return ipaddress.ip_address(text).is_loopback
    except ValueError:
        return False


def host_header_is_loopback(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    if text.startswith("["):
        end = text.find("]")
        if end < 0:
            return False
        host = text[1:end]
    else:
        host = text.rsplit(":", 1)[0] if text.count(":") == 1 else text
    return is_loopback_host(host)


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


class AtlasControlPlaneHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        service: Phase16StatusService,
        *,
        session_guard: ControlPlaneSessionGuard | None = None,
    ) -> None:
        self.service = service
        self.session_guard = session_guard or ControlPlaneSessionGuard()
        super().__init__(server_address, AtlasControlPlaneRequestHandler)


class AtlasControlPlaneRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "ATLAS-ControlPlane"
    sys_version = ""

    @property
    def atlas_server(self) -> AtlasControlPlaneHTTPServer:
        return self.server  # type: ignore[return-value]

    def log_message(self, format: str, *args: object) -> None:
        return

    def _send_json(
        self,
        status: HTTPStatus,
        payload: Any,
        *,
        allow: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
        self.send_header("Referrer-Policy", "no-referrer")
        if allow is not None:
            self.send_header("Allow", allow)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _authorized_local_request(self) -> bool:
        return host_header_is_loopback(self.headers.get("Host"))

    def _dispatch_get(self) -> None:
        if not self._authorized_local_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOCAL_HOST_REQUIRED"})
            return

        split = urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        query = parse_qs(split.query, keep_blank_values=False)
        refresh = _truthy(query.get("refresh", [None])[0])
        service = self.atlas_server.service

        try:
            if path == "/healthz":
                status = service.system_status()
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "contract_version": CONTROL_PLANE_HTTP_CONTRACT_VERSION,
                        "health": status.health.value,
                        "phase15_accepted": status.phase15.accepted,
                        "runtime_state_valid": status.runtime_state_valid,
                        "provider_write_uncertain": status.provider_write_uncertain,
                        "live_execution_promoted": False,
                    },
                )
                return
            if path == "/api/v1/session":
                self._send_json(
                    HTTPStatus.OK,
                    self.atlas_server.session_guard.public_payload(),
                    extra_headers={
                        "Set-Cookie": self.atlas_server.session_guard.cookie_header()
                    },
                )
                return
            if path in {"/api/v1/status", "/api/v1/status/full"}:
                self._send_json(HTTPStatus.OK, service.full_status(refresh_brokers=refresh))
                return
            if path in {"/api/v1/status/system", "/api/v1/status/lineage"}:
                self._send_json(
                    HTTPStatus.OK,
                    service.system_status().model_dump(mode="json"),
                )
                return
            if path == "/api/v1/status/runtime":
                try:
                    runtime = service.runtime_state()
                except Exception:
                    self._send_json(
                        HTTPStatus.CONFLICT,
                        {"valid": False, "source": "invalid", "fail_closed": True},
                    )
                    return
                self._send_json(HTTPStatus.OK, runtime.model_dump(mode="json"))
                return
            if path == "/api/v1/status/execution":
                self._send_json(
                    HTTPStatus.OK,
                    service.execution_status().model_dump(mode="json"),
                )
                return
            if path == "/api/v1/status/brokers":
                rows = service.brokers_status(refresh=refresh)
                self._send_json(
                    HTTPStatus.OK,
                    {"brokers": [row.model_dump(mode="json") for row in rows]},
                )
                return
            if path.startswith("/api/v1/status/brokers/"):
                name = path.rsplit("/", 1)[-1]
                if name not in {BrokerName.WEBULL.value, BrokerName.ALPACA.value}:
                    self._send_json(HTTPStatus.NOT_FOUND, {"error": "BROKER_NOT_FOUND"})
                    return
                row = service.broker_status(BrokerName(name), refresh=refresh)
                self._send_json(HTTPStatus.OK, row.model_dump(mode="json"))
                return
        except ControlPlaneStatusError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "STATUS_REQUEST_INVALID"})
            return
        except Exception:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "STATUS_READ_FAILED"})
            return

        self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch_get()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch_get()

    def _method_not_allowed(self) -> None:
        if not self._authorized_local_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOCAL_HOST_REQUIRED"})
            return
        self._send_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"error": "READ_ONLY_CONTROL_PLANE", "write_endpoints_present": False},
            allow="GET, HEAD",
        )

    do_POST = _method_not_allowed  # type: ignore[assignment]
    do_PUT = _method_not_allowed  # type: ignore[assignment]
    do_PATCH = _method_not_allowed  # type: ignore[assignment]
    do_DELETE = _method_not_allowed  # type: ignore[assignment]
    do_OPTIONS = _method_not_allowed  # type: ignore[assignment]


def create_status_server(
    *,
    service: Phase16StatusService,
    host: str = PHASE16_DEFAULT_BIND_HOST,
    port: int = DEFAULT_CONTROL_PLANE_PORT,
    session_guard: ControlPlaneSessionGuard | None = None,
) -> AtlasControlPlaneHTTPServer:
    if not is_loopback_host(host):
        raise ValueError("Phase 16 read-only control plane may bind only to loopback")
    if not 0 <= int(port) <= 65535:
        raise ValueError("port must be between 0 and 65535")
    return AtlasControlPlaneHTTPServer(
        (host, int(port)), service, session_guard=session_guard
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ATLAS Phase 16 read-only local control plane")
    parser.add_argument("--host", default=PHASE16_DEFAULT_BIND_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_CONTROL_PLANE_PORT)
    args = parser.parse_args()

    settings = load_settings()
    service = Phase16StatusService(settings)
    server = create_status_server(service=service, host=args.host, port=args.port)
    host, port = server.server_address[:2]
    print(f"ATLAS Phase 16 read-only control plane: http://{host}:{port}")
    print("  write endpoints: disabled")
    print("  live execution promotion: disabled")
    print("  broker polling: lazy; add ?refresh=1 to an explicit broker status GET")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
