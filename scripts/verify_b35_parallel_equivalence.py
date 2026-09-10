from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import TypeVar


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.b35_development_authorization import (
    validate_development_authorization,
)
from packages.backtesting.b35_development_replay import (
    _group_units,
    _validate_group_receipt,
)
from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentUnitBinding,
)
from packages.backtesting.b35_parallel_replay import (
    B35GroupTask,
    _init_b35_worker,
    _run_group_task,
)
from packages.backtesting.b35_replay_guard import ensure_read_start_marker
from packages.backtesting.b35_split_evidence import load_b35_split_evidence
from packages.core.execution_profile import resolve_parallel_research_execution_profile
from packages.core.settings import AtlasSettings, load_settings
from packages.data.alpaca_v2_acquisition import V2_DEFAULT_START
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    DEVELOPMENT_LAST_SCORING_SESSION,
)


T = TypeVar("T")


def _output_root(settings: AtlasSettings) -> Path:
    layout = V2Layout.beneath((settings.project_root / "data").resolve())
    return (
        layout.derived
        / "strategy_lab"
        / "b35_development"
        / B35_PREOUTCOME_FINGERPRINT[:16]
        / f"{V2_DEFAULT_START}_{DEVELOPMENT_LAST_SCORING_SESSION}"
    )


def _select_evenly(items: list[T], count: int) -> list[T]:
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[len(items) // 2]]
    indexes = {
        round(index * (len(items) - 1) / (count - 1))
        for index in range(count)
    }
    return [items[index] for index in sorted(indexes)]


def _timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def _run_probe_task(task: B35GroupTask, ordinal: int, total: int) -> dict[str, object]:
    print(f"[{_timestamp()}] STARTED {ordinal}/{total}: {task.token}", flush=True)
    return _run_group_task(task)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Recompute a small deterministic sample of already-completed B35 DEVELOPMENT "
            "groups in an isolated temporary directory and require byte-identical JSONL "
            "SHA-256 output before the parallel replay is trusted."
        )
    )
    parser.add_argument(
        "--authorize-development-outcomes",
        action="store_true",
        help=(
            "Acknowledge that this verifier reopens only the already-authorized frozen "
            "B35 DEVELOPMENT interval. It never reads master-protected or future-blind data."
        ),
    )
    parser.add_argument(
        "--groups",
        type=int,
        default=5,
        help="Number of already-completed groups to recompute; default 5.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not args.authorize_development_outcomes:
        raise ValueError("equivalence verification requires --authorize-development-outcomes")
    if args.groups < 1:
        raise ValueError("--groups must be at least 1")

    settings = load_settings(PROJECT_ROOT)
    profile = resolve_parallel_research_execution_profile()
    source = B35DevelopmentMinuteSource(
        settings,
        duckdb_threads=profile.duckdb_threads_per_worker,
    )
    plan = source.plan(V2_DEFAULT_START, DEVELOPMENT_LAST_SCORING_SESSION)
    split_evidence = load_b35_split_evidence(source.layout)
    output_root = _output_root(settings).resolve()
    replay_lock = output_root / ".b35_replay.lock"
    if replay_lock.exists():
        raise RuntimeError(
            "canonical B35 replay lock exists; stop/verify the active replay before "
            "running the isolated equivalence/performance probe"
        )
    authorization_path = output_root / "development_outcome_authorization.json"
    if not authorization_path.is_file():
        raise RuntimeError("canonical B35 DEVELOPMENT authorization is missing")
    authorization = json.loads(authorization_path.read_text(encoding="utf-8"))
    if not isinstance(authorization, dict):
        raise RuntimeError("canonical B35 DEVELOPMENT authorization is malformed")
    authorization_id = validate_development_authorization(
        authorization,
        plan=plan,
        split_evidence=split_evidence,
    )
    ensure_read_start_marker(
        output_root,
        source_fingerprint=plan.source_fingerprint,
        split_evidence_fingerprint=split_evidence.fingerprint,
        authorization_id=authorization_id,
    )

    completed: list[
        tuple[str, tuple[B35DevelopmentUnitBinding, ...], dict[str, object]]
    ] = []
    for group_fingerprint, units in _group_units(
        plan,
        split_evidence_fingerprint=split_evidence.fingerprint,
        authorization_id=authorization_id,
    ):
        token = group_fingerprint[:20]
        output_path = output_root / "groups" / f"{token}.jsonl"
        receipt_path = output_root / "groups" / f"{token}.receipt.json"
        if not receipt_path.is_file():
            continue
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise RuntimeError(f"completed receipt is malformed: {receipt_path}")
        _validate_group_receipt(
            receipt,
            output_path,
            units=units,
            group_fingerprint=group_fingerprint,
            source_fingerprint=plan.source_fingerprint,
            split_evidence_fingerprint=split_evidence.fingerprint,
            authorization_id=authorization_id,
        )
        completed.append((group_fingerprint, units, receipt))

    if not completed:
        raise RuntimeError("no completed canonical B35 groups are available for equivalence verification")

    sample = _select_evenly(completed, min(args.groups, len(completed)))
    print("ATLAS B35 Parallel Equivalence / Performance Probe", flush=True)
    print(f"  completed canonical groups available: {len(completed):,}", flush=True)
    print(f"  groups selected for exact recompute: {len(sample):,}", flush=True)
    print(
        "  execution profile: "
        f"workers={profile.replay_workers}, "
        f"DuckDB threads/worker={profile.duckdb_threads_per_worker}, "
        f"aggregate worker threads={profile.aggregate_worker_threads}",
        flush=True,
    )
    print("  canonical outputs are read-only; recompute target is temporary", flush=True)
    print("  consumed master / future blind permitted: 0 / 0", flush=True)

    start = time.monotonic()
    total_units = 0
    with tempfile.TemporaryDirectory(prefix="b35_parallel_probe_", dir=output_root) as temp_dir:
        probe_root = Path(temp_dir)
        tasks: list[tuple[B35GroupTask, dict[str, object]]] = []
        for group_fingerprint, units, baseline in sample:
            token = group_fingerprint[:20]
            task = B35GroupTask(
                group_fingerprint=group_fingerprint,
                units=units,
                start_session=plan.start_session,
                end_session=plan.end_session,
                source_fingerprint=plan.source_fingerprint,
                split_evidence_fingerprint=split_evidence.fingerprint,
                authorization_id=authorization_id,
                output_path=str(probe_root / f"{token}.jsonl"),
                receipt_path=str(probe_root / f"{token}.receipt.json"),
            )
            tasks.append((task, baseline))
            total_units += len(units)

        results: dict[str, dict[str, object]] = {}
        total_tasks = len(tasks)
        completed_tasks = 0
        with ProcessPoolExecutor(
            max_workers=min(profile.replay_workers, total_tasks),
            initializer=_init_b35_worker,
            initargs=(str(settings.project_root), profile.duckdb_threads_per_worker),
        ) as executor:
            future_map = {}
            for ordinal, (task, baseline) in enumerate(tasks, start=1):
                future = executor.submit(_run_probe_task, task, ordinal, total_tasks)
                future_map[future] = (task, baseline)

            for future in as_completed(future_map):
                task, baseline = future_map[future]
                recomputed = future.result()
                if recomputed["output_sha256"] != baseline["output_sha256"]:
                    raise RuntimeError(
                        f"SCIENTIFIC EQUIVALENCE FAILURE for group {task.token}: JSONL SHA-256 differs"
                    )
                for field in (
                    "group_fingerprint",
                    "symbols",
                    "unit_count",
                    "unit_bindings",
                    "record_count",
                    "strategy_counts",
                    "source_fingerprint",
                    "split_evidence_fingerprint",
                    "authorization_id",
                    "consumed_master_rows_read",
                    "future_blind_rows_read",
                    "provider_calls",
                    "broker_reads",
                    "broker_writes",
                    "paper_authority",
                    "live_authority",
                    "strategy_promotion",
                    "selector_promotion",
                ):
                    if recomputed[field] != baseline[field]:
                        raise RuntimeError(
                            f"SCIENTIFIC EQUIVALENCE FAILURE for group {task.token}: {field} differs"
                        )
                results[task.group_fingerprint] = recomputed
                completed_tasks += 1
                print(
                    f"[{_timestamp()}] COMPLETED {completed_tasks}/{total_tasks}: {task.token} "
                    f"| PASS | records={int(recomputed['record_count']):,}",
                    flush=True,
                )

        if len(results) != len(tasks):
            raise RuntimeError("equivalence probe did not return every selected group")

    elapsed = time.monotonic() - start
    units_per_hour = total_units / (elapsed / 3600.0) if elapsed > 0 else 0.0
    full_hours = len(plan.units) / units_per_hour if units_per_hour > 0 else float("inf")
    completed_units = sum(int(item[2]["unit_count"]) for item in completed)
    remaining_units = max(0, len(plan.units) - completed_units)
    remaining_hours = remaining_units / units_per_hour if units_per_hour > 0 else float("inf")

    print("", flush=True)
    print("B35 PARALLEL EQUIVALENCE: PASS", flush=True)
    print(f"  exact JSONL SHA-256 matches: {len(sample)}/{len(sample)}", flush=True)
    print(f"  benchmark source units: {total_units:,}", flush=True)
    print(f"  benchmark elapsed seconds: {elapsed:,.1f}", flush=True)
    print(f"  observed probe throughput: {units_per_hour:,.1f} units/hour", flush=True)
    print(f"  projected full replay at probe rate: {full_hours:,.1f} hours", flush=True)
    print(f"  projected remaining replay at probe rate: {remaining_hours:,.1f} hours", flush=True)
    print("  projections are operational estimates, not scientific evidence", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
