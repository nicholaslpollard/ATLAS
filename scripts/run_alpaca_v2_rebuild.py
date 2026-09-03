from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.data.alpaca_v2_rebuild import (
    V2Layout,
    build_decommission_plan,
    disk_guard,
    execute_decommission,
    execute_decommission_with_journal,
    write_decommission_plan,
    write_run_state,
)

NATIVE_BASE_ESTIMATE_BYTES = int(127.8 * 1024**3)
# This must become true only in the same accepted package that implements and
# validates resumable native 1Day + 1Min acquisition/canonicalization. Until
# then the coordinator is intentionally incapable of deleting V1.
REBUILD_ACQUISITION_READY = False


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Resumable top-level Alpaca SIP V2 rebuild coordinator."
    )
    result.add_argument("--execute-v1-decommission", action="store_true")
    result.add_argument(
        "--decommission-v1-only",
        action="store_true",
        help=(
            "Delete only the exact inventoried V1 historical database namespaces, "
            "then stop. This does not build V2."
        ),
    )
    result.add_argument("--confirmation-token", default=None)
    result.add_argument(
        "--required-base-bytes",
        type=int,
        default=NATIVE_BASE_ESTIMATE_BYTES,
        help="Preflight capacity required for source + native 1d/1m base.",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.execute_v1_decommission and args.decommission_v1_only:
        raise ValueError("choose only one V1 decommission mode")
    data_root = (PROJECT_ROOT / "data").resolve()
    data_root.mkdir(parents=True, exist_ok=True)
    layout = V2Layout.beneath(data_root)
    plan = build_decommission_plan(data_root)
    plan_path = data_root / "checkpoints" / "alpaca_v2_migration" / "v1_decommission_plan.json"
    write_decommission_plan(plan, plan_path)

    projected_free = disk_guard(
        data_root,
        required_bytes=args.required_base_bytes,
    )
    projected_free["reclaimable_v1_bytes"] = plan.total_bytes
    projected_free["projected_free_after_decommission_bytes"] = (
        projected_free["free_bytes"] + plan.total_bytes
    )
    projected_free["accepted_after_decommission"] = (
        projected_free["projected_free_after_decommission_bytes"]
        >= projected_free["required_bytes"] + projected_free["reserve_bytes"]
    )

    print("ATLAS Alpaca SIP V2 rebuild preflight")
    print(f"  decommission plan: {plan_path}")
    print(f"  historical targets: {len(plan.entries)}")
    print(f"  historical files: {plan.total_files:,}")
    print(f"  reclaimable bytes: {plan.total_bytes:,}")
    print(f"  confirmation token: {plan.confirmation_token}")
    print(f"  base storage accepted after decommission: {projected_free['accepted_after_decommission']}")

    if not args.execute_v1_decommission and not args.decommission_v1_only:
        print("Result: PREFLIGHT_ONLY — no files deleted and no provider requests made")
        return 0
    if args.decommission_v1_only:
        supplied_token = args.confirmation_token
        if supplied_token is None:
            print()
            print("This permanently deletes only the historical targets listed above.")
            print("It preserves source code, Git history, data/live, data/models, and unrelated research state.")
            supplied_token = input(f"Type {plan.confirmation_token} to continue: ").strip()
        journal_path = (
            data_root
            / "checkpoints"
            / "alpaca_v2_migration"
            / "v1_decommission_receipt.json"
        )
        removed = execute_decommission_with_journal(
            plan,
            confirmation_token=supplied_token,
            journal_path=journal_path,
            progress=lambda target: print(f"  removed: {target}"),
        )
        print(f"  removed historical targets: {removed}")
        print(f"  retained deletion receipt: {journal_path}")
        print("Result: V1 HISTORICAL DATABASE DECOMMISSIONED / V2 NOT YET BUILT")
        return 0
    if not REBUILD_ACQUISITION_READY:
        raise RuntimeError(
            "V1 decommission is code-locked until resumable V2 acquisition is implemented"
        )
    if not projected_free["accepted_after_decommission"]:
        raise RuntimeError("native base disk preflight failed; V1 was not deleted")
    if not args.confirmation_token:
        raise RuntimeError("--confirmation-token is required; V1 was not deleted")

    removed = execute_decommission(plan, confirmation_token=args.confirmation_token)
    layout.create()
    state = write_run_state(
        layout,
        stage="V1_DECOMMISSIONED",
        status="READY_FOR_ACQUISITION",
        details={
            "removed_targets": removed,
            "decommission_plan_sha256": plan.plan_sha256,
            "disk_preflight": projected_free,
        },
    )
    print(f"  removed historical targets: {removed}")
    print(f"  V2 run state: {state}")
    print("Result: V1_DECOMMISSIONED / V2 ACQUISITION NOT YET IMPLEMENTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
