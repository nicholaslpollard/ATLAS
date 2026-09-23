from __future__ import annotations

import argparse
import sys
import time
from datetime import UTC, datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.providers.czar28 import Czar28Error, get_health, health_is_ready


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Poll the public Czar28 health endpoint without API-key quota and "
            "exit when status=ok and upstream.mdds_status=CONNECTED."
        )
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="Seconds between public health checks (minimum 30, default 60).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval_seconds < 30:
        print("BLOCKED: --interval-seconds must be at least 30.")
        return 2

    print("ATLAS Czar28 Public Health Watch V1")
    print("  endpoint: https://czar28.com/v1/options/health")
    print("  authentication: none")
    print("  API-key quota consumption: none")
    print(f"  interval: {args.interval_seconds}s")
    print("  success condition: status=ok AND mdds_status=CONNECTED")
    print("  stop manually with Ctrl+C")

    check = 0
    last_rendered: str | None = None
    try:
        while True:
            check += 1
            timestamp = datetime.now(UTC).isoformat()
            try:
                response = get_health()
                upstream = response.payload.get("upstream")
                upstream_status = None
                upstream_message = None
                upstream_ms = None
                if isinstance(upstream, dict):
                    upstream_status = upstream.get("mdds_status")
                    upstream_message = upstream.get("message")
                    upstream_ms = upstream.get("upstream_ms")
                rendered = (
                    f"status={response.payload.get('status')} "
                    f"upstream={upstream_status} "
                    f"upstream_ms={upstream_ms} "
                    f"message={upstream_message}"
                )
                if rendered != last_rendered or check == 1 or check % 5 == 0:
                    print(
                        f"  [{timestamp}] check={check}: {rendered}",
                        flush=True,
                    )
                last_rendered = rendered

                if health_is_ready(response.payload):
                    print(
                        "CZAR28 HEALTHY: public health is ok/CONNECTED. "
                        "Stop here and run the five-probe ATLAS preflight next.",
                        flush=True,
                    )
                    return 0
            except Czar28Error as exc:
                rendered = f"{type(exc).__name__}: {exc}"
                if rendered != last_rendered or check == 1 or check % 5 == 0:
                    print(
                        f"  [{timestamp}] check={check}: {rendered}",
                        flush=True,
                    )
                last_rendered = rendered

            time.sleep(args.interval_seconds)
    except KeyboardInterrupt:
        print("\nSTOPPED: Czar28 health watch interrupted by user.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
