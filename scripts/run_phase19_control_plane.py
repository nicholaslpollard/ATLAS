from __future__ import annotations

import argparse

from packages.control_plane.http_server import DEFAULT_CONTROL_PLANE_PORT
from packages.control_plane.phase16_policy import PHASE16_DEFAULT_BIND_HOST
from packages.control_plane.phase19_http_server import create_phase19_status_server
from packages.control_plane.phase19_observability import Phase19ObservabilityService
from packages.control_plane.phase19_policy import phase19_policy_fingerprint
from packages.control_plane.status import Phase16StatusService
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.simulation.recurrent_persistence import (
    RecurrentLifecyclePersistenceError,
)
from packages.simulation.recurrent_runtime import (
    RecurrentDurableRuntimeError,
    restore_durable_recurrent_lifecycle_runtime,
)


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

    checkpoint_path = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    recurrent_coordinator = None
    if checkpoint_path.exists():
        try:
            recurrent_coordinator = restore_durable_recurrent_lifecycle_runtime(
                checkpoint_path
            )
        except (
            RecurrentLifecyclePersistenceError,
            RecurrentDurableRuntimeError,
        ) as exc:
            raise SystemExit(
                "Refusing to start with an invalid recurrent lifecycle "
                f"checkpoint at {checkpoint_path}: {exc}"
            ) from exc

    server = create_phase19_status_server(
        service=status_service,
        observability_service=observability,
        recurrent_lifecycle_coordinator=recurrent_coordinator,
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
    if recurrent_coordinator is None:
        print("  recurrent lifecycle checkpoint: not present")
        print("  recurrent lifecycle dashboard: NOT_CONNECTED")
    else:
        restored = recurrent_coordinator.snapshot()
        runtime_status = recurrent_coordinator.status()
        print(f"  recurrent lifecycle checkpoint: restored from {checkpoint_path}")
        print(f"  recurrent checkpoint SHA-256: {runtime_status.checkpoint_sha256}")
        print(f"  recurrent lifecycle revision: {restored.revision}")
        print(
            "  recurrent account state: "
            f"{restored.account.state.state_fingerprint}"
        )
        print(
            "  recurrent marked state: "
            + (
                "not current"
                if restored.marked_state is None
                else restored.marked_state.state_fingerprint
            )
        )
    print("  live execution promotion: disabled")
    print("  automatic cross-broker failover: disabled")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
