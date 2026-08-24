from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request

from packages.control_plane.action_ledger import ControlPlaneActionLedger
from packages.control_plane.phase19_http_server import create_phase19_status_server
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.execution.phase15_closeout import PHASE15_CLOSEOUT_CONTRACT_VERSION
from packages.execution.phase15_foundation import PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT
from packages.execution.phase15_policy import phase15_policy_fingerprint


def _settings_with_derived(tmp_path):
    settings = load_settings()
    paths = settings.data.paths.model_copy(update={"derived": tmp_path})
    data = settings.data.model_copy(update={"paths": paths})
    return settings.model_copy(update={"data": data})


def _write_phase15_acceptance(tmp_path) -> None:
    root = tmp_path / "execution" / "phase15" / "v1"
    root.mkdir(parents=True, exist_ok=True)
    payload = {
        "contract_version": PHASE15_CLOSEOUT_CONTRACT_VERSION,
        "pass": True,
        "as_of_date": "2026-08-14",
        "phase15_policy_fingerprint": phase15_policy_fingerprint(),
        "cumulative_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        "execution_case_count": 0,
        "final_disposition": {
            "phase15_accepted": True,
            "actual_broker_execution_exercised_in_acceptance": False,
            "live_execution_promoted": False,
            "automatic_cross_broker_failover_allowed": False,
        },
    }
    (root / "phase15_final_acceptance.json").write_text(json.dumps(payload), encoding="utf-8")


class _ObservabilityStub:
    def __init__(self) -> None:
        self.calls = 0

    def snapshot(self):
        self.calls += 1
        return {
            "contract_version": "phase19-test",
            "authority": {
                "provider_reads": 0,
                "provider_writes": 0,
                "live_execution_promoted": False,
            },
        }


def test_phase19_observability_endpoint_is_get_only_provider_inert(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    status = Phase16StatusService(settings, env={})
    ledger = ControlPlaneActionLedger(settings)
    observability = _ObservabilityStub()
    server = create_phase19_status_server(
        service=status,
        observability_service=observability,
        action_ledger=ledger,
        host="127.0.0.1",
        port=0,
    )
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    base = f"http://127.0.0.1:{int(server.server_address[1])}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base}/api/v1/observability", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        assert payload["authority"]["provider_reads"] == 0
        assert payload["authority"]["provider_writes"] == 0
        assert payload["authority"]["live_execution_promoted"] is False
        assert observability.calls == 1
        assert ledger.verify()["event_count"] == 0

        request = urllib.request.Request(
            f"{base}/api/v1/observability",
            data=b"{}",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        try:
            opener.open(request, timeout=5)
        except urllib.error.HTTPError as exc:
            assert exc.code == 405
        else:
            raise AssertionError("observability POST must be rejected")
        assert observability.calls == 1
        assert ledger.verify()["event_count"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_phase19_server_serves_dedicated_shell_and_local_only_observability_assets(tmp_path) -> None:
    _write_phase15_acceptance(tmp_path)
    settings = _settings_with_derived(tmp_path)
    status = Phase16StatusService(settings, env={})
    server = create_phase19_status_server(service=status, host="127.0.0.1", port=0)
    thread = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    thread.start()
    base = f"http://127.0.0.1:{int(server.server_address[1])}"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(f"{base}/", timeout=5) as response:
            html = response.read().decode("utf-8")
            assert "ATLAS Control Plane · Operations Dashboard" in html
            assert 'id="candidate-search"' in html
            assert 'id="candidate-state-filter"' in html
            assert 'id="candidate-promoted-only"' in html
            assert 'id="candidate-dialog"' in html
            assert 'id="artifact-recency"' in html
            assert 'id="outcome-win-rate"' in html
            assert "/assets/observability.js" in html
            assert response.headers["Content-Security-Policy"].find("script-src 'self'") >= 0

        with opener.open(f"{base}/assets/observability.js", timeout=5) as response:
            js = response.read().decode("utf-8")
            assert "loadObservability" in js
            assert "renderCandidateRows" in js
            assert "showCandidateDetail" in js
            assert "setPhase19LocalRefreshInterval" in js
            assert "phase18-input-checklist" in js
            assert "Every 5 seconds" in js
            assert "Every 15 seconds" in js
            assert "Every 30 seconds" in js
            assert 'fetch("/api/v1/observability"' in js
            assert "/api/v1/brokers/refresh" not in js
            assert "No automatic broker refresh" in js
            assert "Explicit Phase 18 paper-mutation authorization remains separately required." in js

        with opener.open(f"{base}/assets/observability_controls.js", timeout=5) as response:
            controls = response.read().decode("utf-8")
            assert "intervalSeconds: 0" in controls
            assert "document.hidden" in controls
            assert "/api/v1/brokers/refresh" not in controls

        with opener.open(f"{base}/assets/observability.css", timeout=5) as response:
            css = response.read().decode("utf-8")
            assert ".pipeline-grid" in css
            assert ".candidate-tools" in css
            assert ".candidate-dialog-shell" in css
            assert ".readiness-checklist" in css
            assert ".local-refresh-control" in css
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
