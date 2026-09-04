from __future__ import annotations

import argparse

from packages.control_plane.phase19_preview_server import (
    DEFAULT_PHASE19_PREVIEW_HOST,
    DEFAULT_PHASE19_PREVIEW_PORT,
    PHASE19_PREVIEW_CONTRACT_VERSION,
    create_phase19_preview_server,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ATLAS Phase19 synthetic read-only preview for Codespaces/frontend review"
    )
    parser.add_argument("--host", default=DEFAULT_PHASE19_PREVIEW_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PHASE19_PREVIEW_PORT)
    args = parser.parse_args()

    server = create_phase19_preview_server(host=args.host, port=args.port)
    host, port = server.server_address[:2]
    print(f"ATLAS Phase19 synthetic preview: http://{host}:{port}")
    print(f"  contract: {PHASE19_PREVIEW_CONTRACT_VERSION}")
    print("  synthetic demo data only: yes")
    print("  market-data/provider connections: 0")
    print("  broker connections: 0")
    print("  provider writes: 0")
    print("  broker writes: 0")
    print("  POST requests: disabled")
    print("  production loopback guard: unchanged")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
