from __future__ import annotations

import http.client
import json
import threading
from datetime import UTC, datetime

from packages.control_plane.phase19_preview_server import (
    PHASE19_PREVIEW_CONTRACT_VERSION,
    create_phase19_preview_server,
    preview_payload,
)


def test_preview_payloads_are_synthetic_and_read_only() -> None:
    now = datetime(2026, 9, 4, 20, 0, tzinfo=UTC)
    health = preview_payload("/healthz", now_utc=now)
    paper = preview_payload("/api/v1/ops/paper-dashboard", now_utc=now)
    observability = preview_payload("/api/v1/observability", now_utc=now)

    assert health is not None
    assert health["contract_version"] == PHASE19_PREVIEW_CONTRACT_VERSION
    assert health["preview_synthetic"] is True
    assert health["provider_writes"] == 0
    assert health["broker_writes"] == 0

    assert paper is not None
    assert paper["preview_synthetic"] is True
    assert paper["read_only"] is True
    assert paper["provider_reads"] == 0
    assert paper["provider_writes"] == 0
    assert paper["broker_writes"] == 0
    assert paper["health"]["browser_mutation_authority"] is False
    assert paper["health"]["live_execution_promoted"] is False
    assert paper["open_positions"][0]["ticker"] == "AAPL"

    assert observability is not None
    assert observability["preview_synthetic"] is True
    assert observability["authority"]["provider_reads"] == 0
    assert observability["authority"]["provider_writes"] == 0
    assert observability["authority"]["live_execution_promoted"] is False


def test_preview_server_serves_ui_and_rejects_posts() -> None:
    server = create_phase19_preview_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/")
        response = connection.getresponse()
        body = response.read().decode("utf-8")
        connection.close()
        assert response.status == 200
        assert "ATLAS Control Plane" in body

        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request("GET", "/api/v1/ops/paper-dashboard")
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        assert response.status == 200
        assert payload["preview_synthetic"] is True
        assert payload["provider_writes"] == 0
        assert payload["broker_writes"] == 0

        connection = http.client.HTTPConnection(host, port, timeout=5)
        connection.request(
            "POST",
            "/api/v1/actions/request",
            body=b"{}",
            headers={"Content-Type": "application/json", "Content-Length": "2"},
        )
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        connection.close()
        assert response.status == 405
        assert payload["error"] == "PREVIEW_READ_ONLY"
        assert payload["provider_writes"] == 0
        assert payload["broker_writes"] == 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
