from __future__ import annotations

from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from .action_ledger import ControlPlaneActionLedger
from .broker_switch_processor import Phase16BrokerSwitchProcessor
from .cleanup_plan_ledger import ControlPlaneCleanupPlanLedger
from .cleanup_planner import Phase16CleanupPlanner
from .cleanup_processor import Phase16CleanupProcessor
from .http_server import (
    DEFAULT_CONTROL_PLANE_PORT,
    MAX_STATIC_ASSET_BYTES,
    AtlasControlPlaneHTTPServer,
    AtlasControlPlaneRequestHandler,
    _BROWSER_CSP,
    create_status_server,
)
from .paper_dashboard import PaperDashboardService
from .phase16_policy import PHASE16_DEFAULT_BIND_HOST
from .phase19_observability import Phase19ObservabilityService
from .session import ControlPlaneSessionGuard
from .status import Phase16StatusService


PHASE19_HTTP_CONTRACT_VERSION = (
    "phase19-http-v1-phase16-preserving-readonly-observability-extension"
)
_PHASE19_STATIC_ASSETS = {
    "/": ("phase19.html", "text/html; charset=utf-8"),
    "/index.html": ("phase19.html", "text/html; charset=utf-8"),
    "/assets/observability_controls.js": (
        "observability_controls.js",
        "text/javascript; charset=utf-8",
    ),
    "/assets/observability.css": ("observability.css", "text/css; charset=utf-8"),
    "/assets/atlas_console.css": ("atlas_console.css", "text/css; charset=utf-8"),
}
_PHASE19_OBSERVABILITY_BUNDLE = (
    "observability.js",
    "observability_controls.js",
    "paper_dashboard.js",
    "atlas_console.js",
    "atlas_overview.js",
    "atlas_console_runtime.js",
)


def _read_static_part(web_root: Path, filename: str) -> bytes:
    candidate = (web_root / filename).resolve()
    if candidate.parent != web_root:
        raise PermissionError(filename)
    if not candidate.is_file():
        raise FileNotFoundError(candidate.name)
    size = candidate.stat().st_size
    if size < 0 or size > MAX_STATIC_ASSET_BYTES:
        raise ValueError("static asset exceeds size cap")
    raw = candidate.read_bytes()
    if len(raw) != size:
        raise OSError("static asset changed while reading")
    return raw


class Phase19ControlPlaneRequestHandler(AtlasControlPlaneRequestHandler):
    def _send_static(self, path: str) -> bool:
        if path == "/assets/observability.js":
            try:
                parts = [
                    _read_static_part(self.atlas_server.web_root, filename)
                    for filename in _PHASE19_OBSERVABILITY_BUNDLE
                ]
                raw = b"\n".join(parts)
                if len(raw) > MAX_STATIC_ASSET_BYTES:
                    raise ValueError("bundled static asset exceeds size cap")
            except PermissionError:
                self._send_json(HTTPStatus.FORBIDDEN, {"error": "STATIC_PATH_REJECTED"})
                return True
            except (OSError, ValueError):
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "UI_ASSET_UNAVAILABLE"})
                return True
            self._send_bytes(
                HTTPStatus.OK,
                raw,
                content_type="text/javascript; charset=utf-8",
                csp=_BROWSER_CSP,
            )
            return True

        asset = _PHASE19_STATIC_ASSETS.get(path)
        if asset is None:
            return super()._send_static(path)
        filename, content_type = asset
        try:
            raw = _read_static_part(self.atlas_server.web_root, filename)
        except PermissionError:
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "STATIC_PATH_REJECTED"})
            return True
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

    def _dispatch_get(self) -> None:
        if not self._authorized_local_request():
            self._send_json(HTTPStatus.FORBIDDEN, {"error": "LOCAL_HOST_REQUIRED"})
            return
        path = urlsplit(self.path).path.rstrip("/") or "/"
        if path == "/api/v1/observability":
            try:
                payload = self.atlas_server.observability_service.snapshot()  # type: ignore[attr-defined]
            except Exception:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "OBSERVABILITY_READ_FAILED",
                        "provider_reads": 0,
                        "provider_writes": 0,
                    },
                )
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        if path == "/api/v1/ops/paper-dashboard":
            try:
                payload = self.atlas_server.paper_dashboard_service.snapshot()  # type: ignore[attr-defined]
            except Exception:
                self._send_json(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {
                        "error": "PAPER_DASHBOARD_READ_FAILED",
                        "read_only": True,
                        "provider_reads": 0,
                        "provider_writes": 0,
                        "broker_writes": 0,
                    },
                )
                return
            self._send_json(HTTPStatus.OK, payload)
            return
        super()._dispatch_get()


def create_phase19_status_server(
    *,
    service: Phase16StatusService,
    observability_service: Phase19ObservabilityService | None = None,
    paper_dashboard_service: PaperDashboardService | None = None,
    host: str = PHASE16_DEFAULT_BIND_HOST,
    port: int = DEFAULT_CONTROL_PLANE_PORT,
    session_guard: ControlPlaneSessionGuard | None = None,
    action_ledger: ControlPlaneActionLedger | None = None,
    broker_switch_processor: Phase16BrokerSwitchProcessor | None = None,
    cleanup_planner: Phase16CleanupPlanner | None = None,
    cleanup_plan_ledger: ControlPlaneCleanupPlanLedger | None = None,
    cleanup_review_processor: Phase16CleanupProcessor | None = None,
    web_root: Path | None = None,
) -> AtlasControlPlaneHTTPServer:
    server = create_status_server(
        service=service,
        host=host,
        port=port,
        session_guard=session_guard,
        action_ledger=action_ledger,
        broker_switch_processor=broker_switch_processor,
        cleanup_planner=cleanup_planner,
        cleanup_plan_ledger=cleanup_plan_ledger,
        cleanup_review_processor=cleanup_review_processor,
        web_root=web_root,
    )
    server.RequestHandlerClass = Phase19ControlPlaneRequestHandler
    server.observability_service = observability_service or Phase19ObservabilityService(  # type: ignore[attr-defined]
        service.settings,
        status_service=service,
    )
    server.paper_dashboard_service = paper_dashboard_service or PaperDashboardService(  # type: ignore[attr-defined]
        service.settings,
    )
    return server
