from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from packages.backtesting.successor_development_outcomes import validate_accepted_successor_preflight
from packages.backtesting.successor_spy_benchmark_source import (
    SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT,
    SuccessorSpyBenchmarkSourceError,
    audit_successor_spy_benchmark_source,
)
from packages.core.settings import load_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit and materialize the DEVELOPMENT-only SPY benchmark source. "
            "This opens source bars only, never strategy outcomes, the consumed master, "
            "future blind, providers, brokers, PAPER, LIVE, or promotion authority."
        )
    )
    parser.add_argument(
        "--authorize-spy-source-audit",
        action="store_true",
        help="Authorize the bounded DEVELOPMENT-only SPY source integrity/coverage audit.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="ATLAS project root (default: current directory).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.authorize_spy_source_audit:
        parser.error("--authorize-spy-source-audit is required; no source bars were opened")
    project_root = args.project_root.resolve()
    settings = load_settings(project_root)
    preflight = validate_accepted_successor_preflight(project_root)
    print(
        "successor SPY source audit "
        f"contract={SPY_BENCHMARK_SOURCE_AUDIT_CONTRACT_FINGERPRINT} "
        "authority=source-only protected=0 future=0 provider=0 broker=0 "
        "PAPER=false LIVE=false promotion=false"
    )
    try:
        receipt = audit_successor_spy_benchmark_source(settings, preflight=preflight)
    except SuccessorSpyBenchmarkSourceError as exc:
        print("SPY_SOURCE_AUDIT_FAIL " + str(exc))
        return 2
    scientific = receipt["scientific"]
    resolution = scientific["resolution"]
    print(
        "SPY_SOURCE_AUDIT_ACCEPTED "
        + json.dumps(
            {
                "scientific_fingerprint": receipt["scientific_fingerprint"],
                "benchmark_sha256": scientific["benchmark_sha256"],
                "session_count": scientific["benchmark_rows"],
                "minute_primary_session_count": resolution["minute_primary_session_count"],
                "daily_fallback_session_count": resolution["daily_fallback_session_count"],
                "daily_fallback_sessions": resolution["daily_fallback_sessions"],
                "native_acceptance_fingerprint": scientific["daily_fallback"].get(
                    "native_acceptance_fingerprint"
                ),
                "authority": scientific["authority"],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
