from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path
from typing import Sequence

from packages.backtesting.successor_development_runner import (
    build_successor_development_run_identity,
    prepare_successor_development_inputs,
    run_successor_development_standalone,
)
from packages.backtesting.successor_parallel import validate_completed_group
from packages.core.settings import load_settings
from packages.core.successor_execution_profile import SuccessorResearchExecutionProfile


PROBE_CONTRACT = "successor-minute-real-data-equivalence-performance-probe-v1"
DEFAULT_GROUPS = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute a small spread of already-completed successor minute groups in "
            "an isolated output root, prove exact artifact equivalence, and report runtime. "
            "The probe opens DEVELOPMENT outcomes only and grants no PAPER/LIVE/promotion authority."
        )
    )
    parser.add_argument(
        "--authorize-development-outcomes",
        action="store_true",
        help="Explicitly authorize the frozen DEVELOPMENT interval only.",
    )
    parser.add_argument(
        "--groups",
        type=int,
        default=DEFAULT_GROUPS,
        help="Number of completed minute groups to probe (default: 3; maximum: 8).",
    )
    parser.add_argument(
        "--project-root", type=Path, default=Path.cwd(), help="ATLAS project root."
    )
    return parser


def _profile(base: SuccessorResearchExecutionProfile, workers: int) -> SuccessorResearchExecutionProfile:
    usable = max(1, base.logical_cpus - base.reserved_logical_cpus)
    workers = max(1, min(workers, usable))
    return SuccessorResearchExecutionProfile(
        logical_cpus=base.logical_cpus,
        total_memory_bytes=base.total_memory_bytes,
        reserved_logical_cpus=base.reserved_logical_cpus,
        workers=workers,
        duckdb_threads_per_worker=1,
        aggregate_worker_threads=workers,
        profile_source="successor_real_data_probe",
        thermal_headroom_policy=base.thermal_headroom_policy,
    )


def _spread(values: Sequence[object], count: int) -> tuple[object, ...]:
    if count >= len(values):
        return tuple(values)
    if count == 1:
        return (values[len(values) // 2],)
    positions = [round(index * (len(values) - 1) / (count - 1)) for index in range(count)]
    return tuple(values[position] for position in positions)


def _group_output(root: Path, token: str) -> dict[str, object]:
    path = root / "groups" / token / "output.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"group output is not a JSON object: {token}")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_development_outcomes:
        raise SystemExit("--authorize-development-outcomes is required; no outcomes were opened")
    if args.groups < 1 or args.groups > 8:
        raise SystemExit("--groups must be between 1 and 8")

    project_root = args.project_root.resolve()
    settings = load_settings(project_root)
    identity = build_successor_development_run_identity(project_root)
    inputs = prepare_successor_development_inputs(settings, identity=identity)
    canonical_root = (
        project_root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development"
        / identity.fingerprint[:16]
    ).resolve()

    completed = []
    for unit in inputs.work_units:
        if not unit.token.startswith("minute_"):
            continue
        prior = validate_completed_group(
            canonical_root,
            unit,
            scientific_contract_fingerprint=identity.fingerprint,
        )
        if prior is not None:
            completed.append(unit)
    if not completed:
        raise SystemExit(
            "no completed minute groups are available for an exact real-data equivalence probe"
        )

    selected = tuple(_spread(completed, min(args.groups, len(completed))))
    baseline = {unit.token: _group_output(canonical_root, unit.token) for unit in selected}
    probe_root = (
        project_root
        / "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development_probe"
        / identity.fingerprint[:16]
    ).resolve()
    if probe_root.exists():
        shutil.rmtree(probe_root)

    base_profile = __import__(
        "packages.core.successor_execution_profile", fromlist=["resolve_successor_research_execution_profile"]
    ).resolve_successor_research_execution_profile()
    profile = _profile(base_profile, len(selected))
    tokens = [unit.token for unit in selected]
    print(
        f"successor minute probe contract={PROBE_CONTRACT} tokens={','.join(tokens)} "
        f"workers={profile.workers} run_contract={identity.fingerprint}",
        flush=True,
    )
    print(
        "authority: protected=0 future=0 provider=0 broker=0 PAPER=false LIVE=false promotion=false",
        flush=True,
    )

    started = time.monotonic()
    result = run_successor_development_standalone(
        settings,
        identity=identity,
        inputs=inputs,
        execution_profile=profile,
        units=selected,
        output_root=probe_root,
    )
    elapsed = time.monotonic() - started

    comparisons = []
    for unit in selected:
        before = baseline[unit.token]
        after = _group_output(probe_root, unit.token)
        equivalent = (
            before.get("standalone_artifact_sha256") == after.get("standalone_artifact_sha256")
            and before.get("standalone_record_count") == after.get("standalone_record_count")
            and before.get("policy_record_counts") == after.get("policy_record_counts")
            and before.get("source_units") == after.get("source_units")
        )
        comparisons.append(
            {
                "token": unit.token,
                "equivalent": equivalent,
                "baseline_artifact_sha256": before.get("standalone_artifact_sha256"),
                "probe_artifact_sha256": after.get("standalone_artifact_sha256"),
                "record_count": after.get("standalone_record_count"),
                "source_units": after.get("source_units"),
            }
        )
    if not all(item["equivalent"] for item in comparisons):
        print(
            "PROBE_FAILED_EQUIVALENCE "
            + json.dumps(comparisons, sort_keys=True, separators=(",", ":")),
            flush=True,
        )
        return 2

    summary = {
        "contract": PROBE_CONTRACT,
        "status": "PASS_EXACT_REAL_DATA_EQUIVALENCE",
        "run_contract_fingerprint": identity.fingerprint,
        "group_count": len(selected),
        "tokens": tokens,
        "elapsed_seconds": elapsed,
        "groups_per_hour": (len(selected) * 3600.0 / elapsed) if elapsed > 0 else None,
        "comparisons": comparisons,
        "canonical_run_untouched": True,
        "conditioning_opened": False,
        "confluence_opened": False,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "probe_parallel_run": result.get("parallel_run"),
    }
    print("PROBE " + json.dumps(summary, sort_keys=True, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
