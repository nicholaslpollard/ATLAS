from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Sequence

from packages.backtesting.successor_development_runner import (
    build_successor_development_run_identity,
    development_outcome_authority,
    prepare_successor_development_inputs,
    run_successor_development_standalone,
)
from packages.backtesting.successor_parallel import ResearchWorkUnit, validate_completed_group
from packages.backtesting.successor_worker_scaling import (
    SUCCESSOR_WORKER_SCALING_BENCHMARK_CONTRACT,
    candidate_profile,
    decide_worker_scaling,
    load_baseline_progress,
)
from packages.core.atomic_io import atomic_write_text
from packages.core.settings import load_settings
from packages.core.successor_execution_profile import resolve_successor_research_execution_profile


DEFAULT_CANDIDATE_WORKERS = 9
DEFAULT_BENCHMARK_GROUPS = 18
DEFAULT_MINIMUM_SPEEDUP_PERCENT = 3.0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark a denser successor Nx1 worker profile on still-pending DEVELOPMENT "
            "minute groups, promote the validated benchmark work into the canonical run, "
            "and automatically continue with the profile that wins the conservative "
            "break-even test. Never opens the consumed master or future blind."
        )
    )
    parser.add_argument(
        "--authorize-development-outcomes",
        action="store_true",
        help="Explicitly authorize frozen DEVELOPMENT outcomes only.",
    )
    parser.add_argument(
        "--authorize-full-standalone",
        action="store_true",
        help="Explicitly authorize continuation of the full DEVELOPMENT standalone run.",
    )
    parser.add_argument(
        "--candidate-workers",
        type=int,
        default=DEFAULT_CANDIDATE_WORKERS,
        help="Candidate single-threaded worker count (default: 9).",
    )
    parser.add_argument(
        "--benchmark-groups",
        type=int,
        default=DEFAULT_BENCHMARK_GROUPS,
        help="Pending minute groups used for the candidate benchmark (default: 18).",
    )
    parser.add_argument(
        "--minimum-speedup-percent",
        type=float,
        default=DEFAULT_MINIMUM_SPEEDUP_PERCENT,
        help="Minimum measured speedup required before break-even can select the candidate (default: 3%%).",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="ATLAS project root (default: current directory).",
    )
    return parser


def _canonical_root(project_root: Path, run_fingerprint: str) -> Path:
    return (
        project_root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development"
        / run_fingerprint[:16]
    ).resolve()


def _benchmark_root(project_root: Path, run_fingerprint: str, workers: int) -> Path:
    return (
        project_root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_worker_scaling_benchmark"
        / run_fingerprint[:16]
        / f"candidate_{workers}x1"
    ).resolve()


def _pending_minute_units(
    units: Sequence[ResearchWorkUnit],
    *,
    canonical_root: Path,
    scientific_contract_fingerprint: str,
) -> list[ResearchWorkUnit]:
    pending: list[ResearchWorkUnit] = []
    for unit in sorted(units, key=lambda item: item.token):
        if not unit.token.startswith("minute_"):
            continue
        prior = validate_completed_group(
            canonical_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if prior is None:
            pending.append(unit)
    return pending


def _promote_benchmark_groups(
    selected: Sequence[ResearchWorkUnit],
    *,
    benchmark_root: Path,
    canonical_root: Path,
    scientific_contract_fingerprint: str,
) -> list[str]:
    promoted: list[str] = []
    for unit in selected:
        benchmark_group = validate_completed_group(
            benchmark_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if benchmark_group is None:
            raise RuntimeError(f"benchmark group did not complete: {unit.token}")

        canonical_prior = validate_completed_group(
            canonical_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if canonical_prior is not None:
            raise RuntimeError(
                f"canonical group {unit.token} appeared during the benchmark; "
                "another successor replay may be running"
            )

        source_dir = benchmark_root / "groups" / unit.token
        target_dir = canonical_root / "groups" / unit.token
        target_dir.mkdir(parents=True, exist_ok=True)
        output_text = (source_dir / "output.json").read_text(encoding="utf-8")
        receipt_text = (source_dir / "receipt.json").read_text(encoding="utf-8")
        atomic_write_text(target_dir / "output.json", output_text)
        atomic_write_text(target_dir / "receipt.json", receipt_text)

        canonical_group = validate_completed_group(
            canonical_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if canonical_group is None:
            raise RuntimeError(f"promoted group failed canonical validation: {unit.token}")
        if (
            canonical_group.output_sha256 != benchmark_group.output_sha256
            or canonical_group.receipt_id != benchmark_group.receipt_id
        ):
            raise RuntimeError(f"promoted group drifted during copy: {unit.token}")
        promoted.append(unit.token)
    return promoted


def _count_completed(
    units: Sequence[ResearchWorkUnit],
    *,
    canonical_root: Path,
    scientific_contract_fingerprint: str,
) -> int:
    count = 0
    for unit in units:
        prior = validate_completed_group(
            canonical_root,
            unit,
            scientific_contract_fingerprint=scientific_contract_fingerprint,
        )
        if prior is not None:
            count += 1
    return count


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_development_outcomes:
        raise SystemExit("--authorize-development-outcomes is required; no outcomes were opened")
    if not args.authorize_full_standalone:
        raise SystemExit("--authorize-full-standalone is required; no broad continuation was opened")
    if args.benchmark_groups < 1:
        raise SystemExit("--benchmark-groups must be positive")
    if args.minimum_speedup_percent < 0:
        raise SystemExit("--minimum-speedup-percent cannot be negative")

    project_root = args.project_root.resolve()
    settings = load_settings(project_root)
    identity = build_successor_development_run_identity(project_root)
    inputs = prepare_successor_development_inputs(settings, identity=identity)
    canonical_root = _canonical_root(project_root, identity.fingerprint)
    progress_path = canonical_root / "progress.json"
    if not progress_path.is_file():
        raise SystemExit("canonical successor progress.json is missing; establish an 8x1 baseline first")

    baseline = load_baseline_progress(progress_path)
    if baseline.state == "RUNNING":
        raise SystemExit(
            "canonical progress still says RUNNING. Stop the current successor replay cleanly with Ctrl+C "
            "before running this benchmark; concurrent canonical writers are prohibited."
        )
    if baseline.state == "COMPLETE":
        print("WORKER_BENCHMARK skipped=standalone_already_complete")
        return 0

    base_profile = resolve_successor_research_execution_profile()
    candidate = candidate_profile(base_profile, workers=args.candidate_workers)
    baseline_profile = candidate_profile(base_profile, workers=baseline.workers)
    if candidate.workers <= baseline.workers:
        raise SystemExit(
            f"candidate {candidate.workers}x1 must be denser than measured baseline {baseline.workers}x1"
        )

    pending = _pending_minute_units(
        inputs.work_units,
        canonical_root=canonical_root,
        scientific_contract_fingerprint=identity.fingerprint,
    )
    minimum_sample = candidate.workers * 2
    if len(pending) < minimum_sample:
        print(
            "WORKER_BENCHMARK skipped=insufficient_remaining_groups "
            f"pending_minute={len(pending)} required={minimum_sample}; continuing baseline={baseline.workers}x1",
            flush=True,
        )
        result = run_successor_development_standalone(
            settings,
            identity=identity,
            inputs=inputs,
            execution_profile=baseline_profile,
        )
        print("STANDALONE " + json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0

    sample_count = min(args.benchmark_groups, len(pending))
    if sample_count < minimum_sample:
        sample_count = minimum_sample
    selected = tuple(pending[:sample_count])
    benchmark_root = _benchmark_root(project_root, identity.fingerprint, candidate.workers)
    if benchmark_root.exists():
        shutil.rmtree(benchmark_root)

    authority = development_outcome_authority()
    print(
        f"successor worker benchmark contract={SUCCESSOR_WORKER_SCALING_BENCHMARK_CONTRACT} "
        f"baseline={baseline.workers}x1 baseline_rate={baseline.groups_per_hour:.2f}/h "
        f"candidate={candidate.workers}x1 groups={len(selected)}",
        flush=True,
    )
    print(
        f"run_contract={identity.fingerprint} protected=0 future=0 provider=0 broker=0 "
        "PAPER=false LIVE=false promotion=false",
        flush=True,
    )
    print("benchmark tokens=" + ",".join(unit.token for unit in selected), flush=True)

    started = time.monotonic()
    benchmark_result = run_successor_development_standalone(
        settings,
        identity=identity,
        inputs=inputs,
        execution_profile=candidate,
        units=selected,
        output_root=benchmark_root,
    )
    elapsed = time.monotonic() - started
    candidate_rate = len(selected) * 3600.0 / elapsed

    promoted = _promote_benchmark_groups(
        selected,
        benchmark_root=benchmark_root,
        canonical_root=canonical_root,
        scientific_contract_fingerprint=identity.fingerprint,
    )
    completed_after = _count_completed(
        inputs.work_units,
        canonical_root=canonical_root,
        scientific_contract_fingerprint=identity.fingerprint,
    )
    remaining_after = len(inputs.work_units) - completed_after

    decision = decide_worker_scaling(
        baseline_workers=baseline.workers,
        candidate_workers=candidate.workers,
        baseline_groups_per_hour=baseline.groups_per_hour,
        candidate_groups_per_hour=candidate_rate,
        benchmark_elapsed_seconds=elapsed,
        remaining_groups_after_benchmark=remaining_after,
        minimum_speedup_fraction=args.minimum_speedup_percent / 100.0,
    )
    chosen_profile = candidate if decision.use_candidate else baseline_profile
    report = {
        "contract": SUCCESSOR_WORKER_SCALING_BENCHMARK_CONTRACT,
        "run_contract_fingerprint": identity.fingerprint,
        "baseline": {
            "workers": baseline.workers,
            "duckdb_threads_per_worker": baseline.duckdb_threads_per_worker,
            "groups_new": baseline.groups_new,
            "elapsed_seconds": baseline.elapsed_seconds,
            "groups_per_hour": baseline.groups_per_hour,
            "state": baseline.state,
        },
        "candidate": {
            "workers": candidate.workers,
            "duckdb_threads_per_worker": candidate.duckdb_threads_per_worker,
            "benchmark_groups": len(selected),
            "elapsed_seconds": elapsed,
            "groups_per_hour": candidate_rate,
            "parallel_run": benchmark_result.get("parallel_run"),
        },
        "promoted_tokens": promoted,
        "canonical_completed_after_benchmark": completed_after,
        "canonical_remaining_after_benchmark": remaining_after,
        "decision": decision.as_dict(),
        "chosen_workers": chosen_profile.workers,
        "benchmark_work_wasted": False,
        "conditioning_opened": False,
        "confluence_opened": False,
        "authority": authority,
    }
    report_path = benchmark_root.parent / "latest_decision.json"
    atomic_write_text(
        report_path,
        json.dumps(report, sort_keys=True, separators=(",", ":"), default=str) + "\n",
    )
    print("WORKER_BENCHMARK " + json.dumps(report, sort_keys=True, separators=(",", ":"), default=str), flush=True)
    print(
        f"benchmark decision chosen={chosen_profile.workers}x1 "
        f"candidate_speedup={decision.speedup_fraction * 100.0:.2f}% "
        f"gross_savings={decision.projected_gross_savings_seconds / 60.0:.1f}m "
        f"benchmark_cost={elapsed / 60.0:.1f}m "
        f"net_after_benchmark={decision.projected_net_savings_seconds / 60.0:.1f}m "
        f"reason={decision.reason}",
        flush=True,
    )
    print(
        f"continuing canonical standalone with {chosen_profile.workers} workers x 1 DuckDB thread; "
        f"benchmark groups promoted={len(promoted)}",
        flush=True,
    )
    result = run_successor_development_standalone(
        settings,
        identity=identity,
        inputs=inputs,
        execution_profile=chosen_profile,
    )
    print("STANDALONE " + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
