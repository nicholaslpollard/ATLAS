from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from packages.backtesting.successor_development_runner import (
    BENCHMARK_WORKER_SHAPES,
    build_successor_development_run_identity,
    development_outcome_authority,
    prepare_successor_development_inputs,
    run_successor_development_benchmark,
    run_successor_development_standalone,
)
from packages.core.settings import load_settings
from packages.core.successor_execution_profile import (
    SuccessorResearchExecutionProfile,
    resolve_successor_research_execution_profile,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the frozen successor DEVELOPMENT outcome package. This command never "
            "opens the consumed master or future blind and grants no PAPER/LIVE/promotion authority."
        )
    )
    parser.add_argument(
        "--authorize-development-outcomes",
        action="store_true",
        help="Explicitly authorize reading outcomes inside the frozen DEVELOPMENT interval only.",
    )
    parser.add_argument(
        "--mode",
        choices=("benchmark", "standalone"),
        required=True,
        help="benchmark runs the bounded exact-equivalence execution-shape set; standalone runs all frozen groups.",
    )
    parser.add_argument(
        "--authorize-full-standalone",
        action="store_true",
        help="Second explicit gate required only for the full 493-group standalone run.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Optional worker override for standalone mode. DuckDB remains frozen at one thread per worker.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="ATLAS project root (default: current directory).",
    )
    return parser


def _standalone_profile(workers: int | None) -> SuccessorResearchExecutionProfile:
    base = resolve_successor_research_execution_profile()
    if workers is None:
        return base
    if workers <= 0:
        raise ValueError("--workers must be positive")
    usable = max(1, base.logical_cpus - base.reserved_logical_cpus)
    if workers > usable:
        raise ValueError(
            f"--workers={workers} exceeds reserved CPU envelope of {usable} logical CPUs"
        )
    return SuccessorResearchExecutionProfile(
        logical_cpus=base.logical_cpus,
        total_memory_bytes=base.total_memory_bytes,
        reserved_logical_cpus=base.reserved_logical_cpus,
        workers=workers,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=workers,
        profile_source="successor_cli_explicit_workers",
        thermal_headroom_policy=base.thermal_headroom_policy,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.authorize_development_outcomes:
        parser.error("--authorize-development-outcomes is required; no outcomes were opened")
    if args.mode == "standalone" and not args.authorize_full_standalone:
        parser.error(
            "full standalone requires --authorize-full-standalone in addition to "
            "--authorize-development-outcomes; no broad run was opened"
        )
    if args.mode == "benchmark" and args.workers is not None:
        parser.error(
            "--workers is not accepted in benchmark mode; benchmark shapes are frozen at "
            + ", ".join(f"{value}x1" for value in BENCHMARK_WORKER_SHAPES)
        )

    project_root = args.project_root.resolve()
    settings = load_settings(project_root)
    identity = build_successor_development_run_identity(project_root)
    inputs = prepare_successor_development_inputs(settings, identity=identity)

    authority = development_outcome_authority()
    print(
        f"successor DEVELOPMENT PID={os.getpid()} mode={args.mode} "
        f"scope={authority['development_scope'][0]}..{authority['development_scope'][1]}"
    )
    print(f"run contract fingerprint={identity.fingerprint}")
    print(
        "accepted source verification fingerprint="
        f"{identity.preflight.source_verification_run_fingerprint}"
    )
    print(
        f"groups={len(inputs.work_units)} daily={inputs.daily_groups} "
        f"minute={inputs.minute_groups} minute units={inputs.minute_source_units}"
    )
    print(
        "authority: protected=0 future=0 provider=0 broker=0 "
        "PAPER=false LIVE=false promotion=false"
    )

    if args.mode == "benchmark":
        result = run_successor_development_benchmark(
            settings,
            identity=identity,
            inputs=inputs,
        )
        print("BENCHMARK " + json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0

    profile = _standalone_profile(args.workers)
    print(
        f"execution profile={profile.workers} workers x "
        f"{profile.duckdb_threads_per_worker} DuckDB thread"
    )
    result = run_successor_development_standalone(
        settings,
        identity=identity,
        inputs=inputs,
        execution_profile=profile,
    )
    print("STANDALONE " + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
