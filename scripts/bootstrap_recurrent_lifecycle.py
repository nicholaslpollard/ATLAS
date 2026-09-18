from __future__ import annotations

import argparse
from datetime import UTC, datetime

from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.simulation.recurrent_genesis import (
    RecurrentGenesisBootstrapError,
    bootstrap_recurrent_genesis_v1,
)


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "timestamp must be ISO-8601, for example 2026-09-18T20:00:00Z"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError(
            "timestamp must include an explicit timezone offset"
        )
    return parsed.astimezone(UTC)


def _positive_equity(value: str) -> float:
    try:
        equity = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "initial equity must be numeric"
        ) from exc
    if equity <= 0.0:
        raise argparse.ArgumentTypeError(
            "initial equity must be greater than zero"
        )
    return equity


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create the one-time authoritative empty recurrent simulation "
            "checkpoint. This command performs no provider or broker reads."
        )
    )
    parser.add_argument(
        "--initial-equity",
        required=True,
        type=_positive_equity,
        help="Explicit starting simulation equity in dollars.",
    )
    parser.add_argument(
        "--as-of-utc",
        type=_parse_utc,
        default=None,
        help=(
            "Optional explicit ISO-8601 UTC bootstrap timestamp. "
            "Defaults to the current UTC time."
        ),
    )
    args = parser.parse_args()

    settings = load_settings()
    checkpoint_path = MarketDataPaths(
        settings
    ).recurrent_lifecycle_checkpoint_file()
    as_of_utc = args.as_of_utc or datetime.now(UTC)

    try:
        runtime, result = bootstrap_recurrent_genesis_v1(
            checkpoint_path=checkpoint_path,
            initial_equity=args.initial_equity,
            as_of_utc=as_of_utc,
        )
    except RecurrentGenesisBootstrapError as exc:
        raise SystemExit(
            f"Recurrent genesis bootstrap refused: {exc}"
        ) from exc

    status = runtime.status()
    print("ATLAS recurrent lifecycle genesis bootstrap: COMPLETE")
    print(f"  checkpoint: {result.checkpoint_path}")
    print(f"  checkpoint SHA-256: {result.checkpoint_sha256}")
    print(f"  bootstrap UTC: {result.as_of_utc.isoformat()}")
    print(f"  initial simulation equity: ${result.initial_equity:,.2f}")
    print(f"  recurrent state: {result.recurrent_state_fingerprint}")
    print(f"  recurrent ledger: {result.recurrent_ledger_fingerprint}")
    print(f"  runtime revision: {status.revision}")
    print("  provider reads/writes: 0 / 0")
    print("  broker reads/writes: 0 / 0")
    print("  order creation: disabled")
    print("  PAPER authority: disabled")
    print("  LIVE authority: disabled")


if __name__ == "__main__":
    main()
