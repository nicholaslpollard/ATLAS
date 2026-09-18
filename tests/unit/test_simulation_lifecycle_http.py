from __future__ import annotations

import json
import threading
from urllib.request import urlopen

from packages.control_plane.phase19_http_server import (
    create_phase19_status_server,
)
from packages.control_plane.phase19_preview_server import preview_payload
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(
        update={"derived": tmp_path, "live": tmp_path / "live"}
    )
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


class _FakeObservabilityService:
    def snapshot(self):
        return {
            "generated_at_utc": "2026-09-17T16:00:00+00:00",
            "provider_reads": 0,
            "provider_writes": 0,
        }


class _FakePaperDashboardService:
    def snapshot(self):
        return {
            "status": "NOT_RUN",
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_writes": 0,
        }


class _FakeLifecycleService:
    def __init__(self) -> None:
        self.calls = 0

    def snapshot(self):
        self.calls += 1
        return {
            "contract_version": (
                "track-a-simulation-lifecycle-dashboard-v1-engine-owned-readonly"
            ),
            "generated_at_utc": "2026-09-17T16:00:00+00:00",
            "status": "NOT_CONNECTED",
            "read_only": True,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "account": None,
            "open_positions": [],
            "closed_trades": [],
        }


def test_phase19_simulation_lifecycle_endpoint_is_local_read_only(
    tmp_path,
) -> None:
    settings = _settings_with_derived(tmp_path)

    def forbidden_broker_factory(_broker):
        raise AssertionError(
            "simulation-lifecycle GET must not initialize a broker"
        )

    status_service = Phase16StatusService(
        settings,
        env={},
        broker_factory=forbidden_broker_factory,
    )
    lifecycle_service = _FakeLifecycleService()
    server = create_phase19_status_server(
        service=status_service,
        observability_service=_FakeObservabilityService(),
        paper_dashboard_service=_FakePaperDashboardService(),
        simulation_lifecycle_dashboard_service=lifecycle_service,
        host="127.0.0.1",
        port=0,
        web_root=settings.project_root / "apps" / "web",
    )
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        host, port = server.server_address[:2]
        with urlopen(
            f"http://{host}:{port}/api/v1/ops/simulation-lifecycle",
            timeout=2,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "NOT_CONNECTED"
        assert payload["read_only"] is True
        assert payload["provider_reads"] == 0
        assert payload["broker_reads"] == 0
        assert payload["provider_writes"] == 0
        assert payload["broker_writes"] == 0
        assert payload["order_writes"] == 0
        assert lifecycle_service.calls == 1

        with urlopen(
            f"http://{host}:{port}/assets/observability.js",
            timeout=2,
        ) as response:
            bundle = response.read().decode("utf-8")
        assert "/api/v1/ops/simulation-lifecycle" in bundle
        assert "atlas:observability-refreshed" in bundle
        assert "window.refreshSimulationLifecycleDashboard" in bundle
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_simulation_lifecycle_browser_uses_existing_refresh_timer_only() -> None:
    settings = load_settings()
    web_root = settings.project_root / "apps" / "web"
    lifecycle_js = (
        web_root / "simulation_lifecycle_dashboard.js"
    ).read_text(encoding="utf-8")
    controls_js = (
        web_root / "observability_controls.js"
    ).read_text(encoding="utf-8")

    assert "/api/v1/ops/simulation-lifecycle" in lifecycle_js
    assert 'method: "GET"' in lifecycle_js
    assert "setInterval" not in lifecycle_js
    assert 'method: "POST"' not in lifecycle_js
    assert "/api/v1/operations/" not in lifecycle_js
    assert "refresh=1" not in lifecycle_js
    assert "atlas:observability-refreshed" in lifecycle_js
    assert "account_state_fingerprint" in lifecycle_js
    assert "account_ledger_fingerprint" in lifecycle_js
    assert controls_js.count("window.setInterval") == 1
    assert "atlas:observability-refreshed" in controls_js


def test_preview_exposes_synthetic_lifecycle_without_authority() -> None:
    payload = preview_payload("/api/v1/ops/simulation-lifecycle")
    assert payload is not None
    assert payload["preview_synthetic"] is True
    assert payload["status"] == "AVAILABLE"
    assert payload["read_only"] is True
    assert payload["provider_reads"] == 0
    assert payload["broker_reads"] == 0
    assert payload["provider_writes"] == 0
    assert payload["broker_writes"] == 0
    assert payload["order_writes"] == 0
    assert payload["authority"]["browser_mutation_authority"] is False
    assert payload["authority"]["paper_authority"] is False
    assert payload["authority"]["live_authority"] is False
    assert len(payload["open_positions"]) == 1
    assert len(payload["closed_trades"]) == 1
    assert payload["source"]["source_kind"] == "RECURRENT_LIFECYCLE_ACCOUNT"
    assert "account_state_fingerprint" in payload["source"]
    assert "account_ledger_fingerprint" in payload["source"]
    assert payload["closed_trades"][0]["origin"] == "RECURRENT_ACCOUNT_V1"


class _FakeLifecycleCoordinator:
    def __init__(self) -> None:
        self.calls = 0

    def current_dashboard_pair(self):
        self.calls += 1
        return None


def test_phase19_can_inject_lifecycle_coordinator_without_external_reads(
    tmp_path,
) -> None:
    settings = _settings_with_derived(tmp_path)

    def forbidden_broker_factory(_broker):
        raise AssertionError(
            "coordinator-backed lifecycle GET must not initialize a broker"
        )

    status_service = Phase16StatusService(
        settings,
        env={},
        broker_factory=forbidden_broker_factory,
    )
    coordinator = _FakeLifecycleCoordinator()
    server = create_phase19_status_server(
        service=status_service,
        observability_service=_FakeObservabilityService(),
        paper_dashboard_service=_FakePaperDashboardService(),
        simulation_lifecycle_coordinator=coordinator,
        host="127.0.0.1",
        port=0,
        web_root=settings.project_root / "apps" / "web",
    )
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        host, port = server.server_address[:2]
        with urlopen(
            f"http://{host}:{port}/api/v1/ops/simulation-lifecycle",
            timeout=2,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "NOT_CONNECTED"
        assert payload["provider_reads"] == 0
        assert payload["broker_reads"] == 0
        assert payload["provider_writes"] == 0
        assert payload["broker_writes"] == 0
        assert payload["order_writes"] == 0
        assert coordinator.calls == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_phase19_rejects_ambiguous_lifecycle_service_and_coordinator(
    tmp_path,
) -> None:
    settings = _settings_with_derived(tmp_path)
    status_service = Phase16StatusService(settings, env={})
    try:
        create_phase19_status_server(
            service=status_service,
            observability_service=_FakeObservabilityService(),
            paper_dashboard_service=_FakePaperDashboardService(),
            simulation_lifecycle_dashboard_service=_FakeLifecycleService(),
            simulation_lifecycle_coordinator=_FakeLifecycleCoordinator(),
            host="127.0.0.1",
            port=0,
            web_root=settings.project_root / "apps" / "web",
        )
    except ValueError as exc:
        assert "exactly one lifecycle dashboard service or coordinator source" in str(exc)
    else:
        raise AssertionError("ambiguous lifecycle injection must fail closed")


class _FakeRecurrentLifecycleCoordinator:
    def __init__(self) -> None:
        self.calls = 0

    def current_dashboard_pair(self):
        self.calls += 1
        return None


def test_phase19_can_inject_recurrent_coordinator_without_external_reads(
    tmp_path,
) -> None:
    settings = _settings_with_derived(tmp_path)

    def forbidden_broker_factory(_broker):
        raise AssertionError(
            "recurrent coordinator lifecycle GET must not initialize a broker"
        )

    status_service = Phase16StatusService(
        settings,
        env={},
        broker_factory=forbidden_broker_factory,
    )
    coordinator = _FakeRecurrentLifecycleCoordinator()
    server = create_phase19_status_server(
        service=status_service,
        observability_service=_FakeObservabilityService(),
        paper_dashboard_service=_FakePaperDashboardService(),
        recurrent_lifecycle_coordinator=coordinator,
        host="127.0.0.1",
        port=0,
        web_root=settings.project_root / "apps" / "web",
    )
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.01},
        daemon=True,
    )
    thread.start()
    try:
        host, port = server.server_address[:2]
        with urlopen(
            f"http://{host}:{port}/api/v1/ops/simulation-lifecycle",
            timeout=2,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["status"] == "NOT_CONNECTED"
        assert payload["read_only"] is True
        assert payload["provider_reads"] == 0
        assert payload["broker_reads"] == 0
        assert payload["provider_writes"] == 0
        assert payload["broker_writes"] == 0
        assert payload["order_writes"] == 0
        assert payload["health"]["reason"] == (
            "RECURRENT_LIFECYCLE_SOURCE_NOT_AVAILABLE"
        )
        assert coordinator.calls == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_phase19_rejects_old_and_recurrent_coordinator_together(
    tmp_path,
) -> None:
    settings = _settings_with_derived(tmp_path)
    status_service = Phase16StatusService(settings, env={})
    try:
        create_phase19_status_server(
            service=status_service,
            observability_service=_FakeObservabilityService(),
            paper_dashboard_service=_FakePaperDashboardService(),
            simulation_lifecycle_coordinator=_FakeLifecycleCoordinator(),
            recurrent_lifecycle_coordinator=_FakeRecurrentLifecycleCoordinator(),
            host="127.0.0.1",
            port=0,
            web_root=settings.project_root / "apps" / "web",
        )
    except ValueError as exc:
        assert "exactly one lifecycle dashboard service or coordinator source" in str(exc)
    else:
        raise AssertionError("dual lifecycle coordinators must fail closed")
