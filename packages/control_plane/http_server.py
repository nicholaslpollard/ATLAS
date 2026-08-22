from __future__ import annotations

import argparse
import ipaddress
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from packages.core.settings import load_settings
from packages.schemas.control_plane import (
    ControlPlaneActionKind,
    ControlPlaneActionRequest,
    ControlPlaneConfirmationGrant,
)
from packages.schemas.execution import BrokerName

from .action_ledger import (
    ControlPlaneActionConflict,
    ControlPlaneActionLedger,
    ControlPlaneActionLedgerError,
    ControlPlaneActionNotFound,
)
from .broker_switch_processor import (
    ControlPlaneBrokerSwitchError,
    Phase16BrokerSwitchProcessor,
)
from .phase16_policy import PHASE16_DEFAULT_BIND_HOST
from .session import ControlPlaneSessionGuard
from .status import ControlPlaneStatusError, Phase16StatusService


CONTROL_PLANE_HTTP_CONTRACT_VERSION = (
    "control-plane-http-v4-loopback-browser-switch-local-routing-no-provider-writes"
)
DEFAULT_CONTROL_PLANE_PORT = 8765
MAX_JSON_BODY_BYTES = 64 * 1024
MAX_STATIC_ASSET_BYTES = 1024 * 1024

_BROWSER_CSP = (
    "default-src 'none'; style-src 'self'; script-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
_JSON_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
_STATIC_ASSETS = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/assets/app.css": ("app.css", "text/css; charset=utf-8"),
    "/assets/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


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
        action_ledger: ControlPlaneActionLedger | None = None,
        broker_switch_processor: Phase16BrokerSwitchProcessor | None = None,
        web_root: Path | None = None,
    ) -> None:
        self.service = service
        self.session_guard = session_guard or ControlPlaneSessionGuard()
        self.action_ledger = action_ledger or service.action_ledger
        self.broker_switch_processor = broker_switch_processor or Phase16BrokerSwitchProcessor(
            service.settings,
            status_service=service,
            ledger=self.action_ledger,
            runtime_store=service.runtime_store,
        )
        self.web_root = (
            web_root.resolve()
            if web_root is not None
            else (service.settings.project_root / "apps" / "web").resolve()
        )
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

    def _send_bytes(
        self,
        status: HTTPStatus,
        raw: bytes,
        *,
        content_type: str,
        csp: str,
        allow: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.send_response(status.value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", csp)
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if allow is not None:
            self.send_header("Allow", allow)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _send_json(
        self,
        status: HTTPStatus,
        payload: Any,
        *,
        allow: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
            "utf-8"
        )
        self._send_bytes(
            status,
            raw,
            content_type="application/json; charset=utf-8",
            csp=_JSON_CSP,
            allow=allow,
            extra_headers=extra_headers,
        )

    def _send_static(self, path: str) -> bool:
        asset = _STATIC_ASSETS.get(path)
        if asset is None:
            return False
        filename, content_type = asset
        candidate = (self.atlas_server.web_root / filename).resolve()
        if candidate.parent != self.atlas_server.web_root:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "STATIC_PATH_REJECTED"})
            return True
        try:
            if not candidate.is_file():
                raise FileNotFoundError(filename)
            size = candidate.stat().st_size
            if size < 0 or size > MAX_STATIC_ASSET_BYTES:
                raise ValueError("static asset exceeds size cap")
            raw = candidate.read_bytes()
            if len(raw) != size:
                raise OSError("static asset changed while reading")
        except (OSError, ValueError):
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "UI_ASSET_UNAVAILABLE"})
            return True
        self._send_bytes(
            HTTPStatus.OK,
            raw,
            content_type=content_type,
            csp=_BROWSER_CSP,
        )
        return True

    def _authorized_local_request(self) -> bool:
        return host_header_is_loopback(self.headers.get("Host"))

    def _expected_origin(self) -> str:
        return f"http://{str(self.headers.get('Host', '')).strip()}"

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length")
        if raw_length is None:
            raise ValueError("CONTENT_LENGTH_REQUIRED")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise ValueError("CONTENT_LENGTH_INVALID") from exc
        if length <= 0 or length > MAX_JSON_BODY_BYTES:
            raise ValueError("JSON_BODY_SIZE_INVALID")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise ValueError("JSON_BODY_TRUNCATED")
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("JSON_OBJECT_REQUIRED")
        return payload

    def _write_preconditions(self) -> bool:
        system = self.atlas_server.service.system_status()
        if not system.phase15.accepted:
            self._send_json(HTTPStatus.CONFLICT, {"error": "PHASE15_ACCEPTANCE_REQUIRED"})
            return False
        if not system.runtime_state_valid:
            self._send_json(HTTPStatus.CONFLICT, {"error": "RUNTIME_STATE_INVALID"})
            return False
        if not system.action_ledger_valid:
            self._send_json(HTTPStatus.CONFLICT, {"error": "ACTION_LEDGER_INVALID"})
            return False
        if system.provider_write_uncertain:
            self._send_json(HTTPStatus.CONFLICT, {"error": "PROVIDER_WRITE_UNCERTAIN"})
            return False
        return True

    def _dispatch_get(self) -> None:
        if not self._authorized_local_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOCAL_HOST_REQUIRED"})
            return
        split = urlsplit(self.path)
        path = split.path.rstrip("/") or "/"
        if self._send_static(path):
            return
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
                        "action_ledger_valid": status.action_ledger_valid,
                        "provider_write_uncertain": status.provider_write_uncertain,
                        "provider_write_endpoints_present": False,
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
            if path == "/api/v1/actions":
                records = self.atlas_server.action_ledger.records()
                self._send_json(
                    HTTPStatus.OK,
                    {
                        "actions": [
                            records[key].model_dump(mode="json")
                            for key in sorted(records)
                        ]
                    },
                )
                return
            if path.startswith("/api/v1/actions/"):
                action_id = path.rsplit("/", 1)[-1]
                if action_id and action_id not in {"request", "confirm", "process"}:
                    try:
                        record = self.atlas_server.action_ledger.get(action_id)
                    except ControlPlaneActionNotFound:
                        self._send_json(
                            HTTPStatus.NOT_FOUND, {"error": "ACTION_NOT_FOUND"}
                        )
                        return
                    self._send_json(
                        HTTPStatus.OK, record.model_dump(mode="json")
                    )
                    return
            if path in {"/api/v1/status", "/api/v1/status/full"}:
                self._send_json(
                    HTTPStatus.OK,
                    service.full_status(refresh_brokers=refresh),
                )
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
                self._send_json(
                    HTTPStatus.OK,
                    runtime.model_dump(mode="json"),
                )
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
                    self._send_json(
                        HTTPStatus.NOT_FOUND, {"error": "BROKER_NOT_FOUND"}
                    )
                    return
                row = service.broker_status(BrokerName(name), refresh=refresh)
                self._send_json(
                    HTTPStatus.OK,
                    row.model_dump(mode="json"),
                )
                return
        except ControlPlaneActionLedgerError:
            self._send_json(
                HTTPStatus.CONFLICT, {"error": "ACTION_LEDGER_INVALID"}
            )
            return
        except ControlPlaneStatusError:
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"error": "STATUS_REQUEST_INVALID"}
            )
            return
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "STATUS_READ_FAILED"}
            )
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch_get()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch_get()

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized_local_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOCAL_HOST_REQUIRED"})
            return
        path = urlsplit(self.path).path.rstrip("/") or "/"
        action_request = path == "/api/v1/actions/request"
        action_confirm = path.startswith("/api/v1/actions/") and path.endswith(
            "/confirm"
        )
        action_process = path.startswith("/api/v1/actions/") and path.endswith(
            "/process"
        )
        if not action_request and not action_confirm and not action_process:
            self._method_not_allowed()
            return
        authorization = self.atlas_server.session_guard.authorize_write(
            self.headers,
            expected_origin=self._expected_origin(),
        )
        if not authorization.allowed:
            self._send_json(
                HTTPStatus.FORBIDDEN,
                {
                    "error": authorization.error_code
                    or "WRITE_AUTHORIZATION_FAILED"
                },
            )
            return
        if not self._write_preconditions():
            return
        try:
            payload = self._read_json_body()
            if action_request:
                request = ControlPlaneActionRequest.model_validate(payload)
                record = self.atlas_server.action_ledger.create_request(request)
            else:
                parts = path.split("/")
                if len(parts) != 6 or parts[:4] != ["", "api", "v1", "actions"]:
                    self._send_json(
                        HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"}
                    )
                    return
                action_id = parts[4]
                if action_confirm:
                    grant = ControlPlaneConfirmationGrant.model_validate(payload)
                    record = self.atlas_server.action_ledger.confirm(action_id, grant)
                else:
                    if payload != {"process": True}:
                        raise ValueError("PROCESS_TRUE_REQUIRED")
                    existing = self.atlas_server.action_ledger.get(action_id)
                    if existing.request.action_kind != ControlPlaneActionKind.BROKER_SWITCH:
                        self._send_json(
                            HTTPStatus.CONFLICT,
                            {"error": "PROCESSOR_NOT_AVAILABLE_FOR_ACTION"},
                        )
                        return
                    record = self.atlas_server.broker_switch_processor.process(action_id)
            runtime = self.atlas_server.service.runtime_state()
            self._send_json(
                HTTPStatus.OK,
                {
                    "record": record.model_dump(mode="json"),
                    "runtime": runtime.model_dump(mode="json"),
                    "provider_write_attempted": record.provider_write_attempted,
                    "provider_write_endpoint_invoked": False,
                    "provider_write_endpoints_present": False,
                    "live_execution_promoted": False,
                },
            )
        except ControlPlaneActionNotFound:
            self._send_json(
                HTTPStatus.NOT_FOUND, {"error": "ACTION_NOT_FOUND"}
            )
        except (ControlPlaneActionConflict, ControlPlaneBrokerSwitchError) as exc:
            self._send_json(
                HTTPStatus.CONFLICT,
                {"error": "ACTION_CONFLICT", "detail": str(exc)},
            )
        except (ControlPlaneActionLedgerError, ValueError, json.JSONDecodeError):
            self._send_json(
                HTTPStatus.BAD_REQUEST, {"error": "ACTION_REQUEST_INVALID"}
            )
        except Exception:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "ACTION_REQUEST_FAILED"}
            )

    def _method_not_allowed(self) -> None:
        if not self._authorized_local_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOCAL_HOST_REQUIRED"})
            return
        self._send_json(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {
                "error": "METHOD_NOT_ALLOWED",
                "action_request_endpoints_present": True,
                "broker_switch_local_routing_processor_present": True,
                "provider_write_endpoints_present": False,
            },
            allow="GET, HEAD, POST",
        )

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
    action_ledger: ControlPlaneActionLedger | None = None,
    broker_switch_processor: Phase16BrokerSwitchProcessor | None = None,
    web_root: Path | None = None,
) -> AtlasControlPlaneHTTPServer:
    if not is_loopback_host(host):
        raise ValueError("Phase 16 control plane may bind only to loopback")
    if not 0 <= int(port) <= 65535:
        raise ValueError("port must be between 0 and 65535")
    return AtlasControlPlaneHTTPServer(
        (host, int(port)),
        service,
        session_guard=session_guard,
        action_ledger=action_ledger,
        broker_switch_processor=broker_switch_processor,
        web_root=web_root,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="ATLAS Phase 16 local control plane")
    parser.add_argument("--host", default=PHASE16_DEFAULT_BIND_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_CONTROL_PLANE_PORT)
    args = parser.parse_args()
    settings = load_settings()
    service = Phase16StatusService(settings)
    server = create_status_server(
        service=service,
        host=args.host,
        port=args.port,
    )
    host, port = server.server_address[:2]
    print(f"ATLAS Phase 16 control plane: http://{host}:{port}")
    print("  browser dashboard: enabled")
    print("  audited request/confirmation endpoints: enabled")
    print("  broker-switch local routing processor: enabled")
    print("  provider write endpoints: disabled")
    print("  live execution promotion: disabled")
    print("  broker polling: lazy; dashboard refresh is explicit")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
