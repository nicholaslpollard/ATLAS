from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import packages.control_plane.phase19_preview_server as preview_server
from packages.control_plane.phase19_preview_server import (
    DEFAULT_PHASE19_PREVIEW_HOST,
    DEFAULT_PHASE19_PREVIEW_PORT,
    PHASE19_PREVIEW_CONTRACT_VERSION,
    create_phase19_preview_server,
)

# Preview-only asset extension. Production Phase19 keeps its own strict loopback server.
preview_server._STATIC_ASSETS["/assets/atlas_console.css"] = (
    "atlas_console.css",
    "text/css; charset=utf-8",
)
preview_server._STATIC_ASSETS["/assets/atlas_overview.css"] = (
    "atlas_overview.css",
    "text/css; charset=utf-8",
)
preview_server._STATIC_ASSETS["/assets/atlas_tabs.css"] = (
    "atlas_tabs.css",
    "text/css; charset=utf-8",
)
preview_server._STATIC_ASSETS["/assets/atlas_status.css"] = (
    "atlas_status.css",
    "text/css; charset=utf-8",
)
for console_asset in (
    "atlas_console.js",
    "atlas_overview_style.js",
    "atlas_overview.js",
    "atlas_tabs.js",
    "atlas_console_runtime.js",
):
    if console_asset not in preview_server._PREVIEW_JS_BUNDLE:
        bundle = list(preview_server._PREVIEW_JS_BUNDLE)
        insert_at = max(0, len(bundle) - 1)
        bundle.insert(insert_at, console_asset)
        preview_server._PREVIEW_JS_BUNDLE = tuple(bundle)


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
    print("  multi-page console shell: enabled")
    print("  overview summary console: enabled")
    print("  domain detail tabs: enabled")
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
