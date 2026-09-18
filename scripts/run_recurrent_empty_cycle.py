from __future__ import annotations

import argparse
from datetime import UTC, datetime

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.simulation.recurrent_cycle import (
    RecurrentCycleOrchestrationError,
    apply_recurrent_cycle_close_stage,
    apply_recurrent_cycle_entry_stage,
    apply_recurrent_cycle_mark_stage,
    apply_recurrent_cycle_reserve_stage,
    begin_recurrent_cycle,
    complete_recurrent_cycle,
)
from packages.simulation.recurrent_persistence import (
    RecurrentLifecyclePersistenceError,
)
from packages.simulation.recurrent_runtime import (
    RecurrentDurableRuntimeError,
    restore_durable_recurrent_lifecycle_runtime,
)


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "timestamp must be ISO-8601, for example 2026-09-18T21:30:00Z"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "timestamp must include an explicit timezone offset"
        )
    return parsed.astimezone(UTC)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run one zero-evidence recurrent lifecycle smoke cycle against the "
            "authoritative durable checkpoint. This performs no provider/broker reads."
        )
    )
    parser.add_argument(
        "--cycle-id",
        required=True,
        help="Explicit unique cycle id for the smoke receipt.",
    )
    parser.add_argument(
        "--valuation-utc",
        type=_parse_utc,
        default=None,
        help=(
            "Optional explicit valuation timestamp. Defaults to current UTC time."
        ),
    )
    args = parser.parse_args()

    settings = load_settings()
    checkpoint_path = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    if not checkpoint_path.is_file():
        raise SystemExit(
            "Recurrent smoke cycle refused: authoritative checkpoint does not exist. "
            "Run the one-time genesis bootstrap first."
        )

    try:
        runtime = restore_durable_recurrent_lifecycle_runtime(
            checkpoint_path
        )
    except (
        RecurrentLifecyclePersistenceError,
        RecurrentDurableRuntimeError,
    ) as exc:
        raise SystemExit(
            f"Recurrent smoke cycle refused: checkpoint restore failed: {exc}"
        ) from exc

    account = runtime.current_account().state
    if (
        account.stock_reservations
        or account.option_reservations
        or account.open_positions
    ):
        raise SystemExit(
            "Recurrent smoke cycle refused: account is not empty. "
            "This command is only for the post-genesis zero-evidence validation."
        )

    valuation_utc = args.valuation_utc or datetime.now(UTC)
    try:
        path, _receipt = begin_recurrent_cycle(
            checkpoint_path=checkpoint_path,
            runtime=runtime,
            cycle_id=args.cycle_id,
        )
        apply_recurrent_cycle_close_stage(
            path=path,
            runtime=runtime,
            fills=(),
        )
        apply_recurrent_cycle_reserve_stage(
            path=path,
            runtime=runtime,
            decisions=(),
        )
        apply_recurrent_cycle_entry_stage(
            path=path,
            runtime=runtime,
            entries=(),
        )
        apply_recurrent_cycle_mark_stage(
            path=path,
            runtime=runtime,
            marks=(),
            valuation_utc=valuation_utc,
        )
        receipt = complete_recurrent_cycle(
            path=path,
            runtime=runtime,
        )
    except (
        RecurrentCycleOrchestrationError,
        RecurrentDurableRuntimeError,
        RecurrentLifecyclePersistenceError,
    ) as exc:
        raise SystemExit(
            f"Recurrent smoke cycle refused/failed: {exc}"
        ) from exc

    status = runtime.status()
    print("ATLAS recurrent lifecycle empty smoke cycle: COMPLETE")
    print(f"  cycle id: {receipt.cycle_id}")
    print(f"  cycle receipt: {path}")
    print(f"  cycle receipt SHA-256: {receipt.receipt_sha256}")
    print(f"  checkpoint SHA-256: {status.checkpoint_sha256}")
    print(f"  runtime snapshot: {status.snapshot_fingerprint}")
    print(f"  runtime revision: {status.revision}")
    print(f"  account state: {runtime.current_account().state.state_fingerprint}")
    marked = runtime.current_marked_state()
    print(
        "  marked state: "
        + ("not current" if marked is None else marked.state_fingerprint)
    )
    print("  provider reads/writes: 0 / 0")
    print("  broker reads/writes: 0 / 0")
    print("  order creation: disabled")
    print("  PAPER authority: disabled")
    print("  LIVE authority: disabled")


if __name__ == "__main__":
    main()
