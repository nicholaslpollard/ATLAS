from __future__ import annotations

import argparse

from packages.control_plane.http_server import DEFAULT_CONTROL_PLANE_PORT
from packages.control_plane.phase16_policy import PHASE16_DEFAULT_BIND_HOST
from packages.control_plane.phase19_http_server import create_phase19_status_server
from packages.control_plane.phase19_observability import Phase19ObservabilityService
from packages.control_plane.phase19_policy import phase19_policy_fingerprint
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ATLAS Phase 19 stacked read-only operations dashboard"
    )
    parser.add_argument("--host", default=PHASE16_DEFAULT_BIND_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_CONTROL_PLANE_PORT)
    args = parser.parse_args()

    settings = load_settings()
    status_service = Phase16StatusService(settings)
    observability = Phase19ObservabilityService(settings, status_service=status_service)
    server = create_phase19_status_server(
        service=status_service,
        observability_service=observability,
        host=args.host,
        port=args.port,
    )
    host, port = server.server_address[:2]
    print(f"ATLAS Phase 19 stacked operations dashboard: http://{host}:{port}")
    print(f"  phase19 policy: {phase19_policy_fingerprint()}")
    print("  local artifact observability: enabled")
    print("  candidate/regime/ML/strategy evidence: read-only")
    print("  AI audit evidence: read-only")
    print("  execution outcome evidence: read-only")
    print("  provider reads from Phase 19 observability: 0")
    print("  provider writes from Phase 19 observability: 0")
    print("  existing Phase 16 broker refresh remains explicit/read-only")
    print("  live execution promotion: disabled")
    print("  automatic cross-broker failover: disabled")
    print("  stacked PR merge: blocked until Phase 18 is accepted/merged")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
