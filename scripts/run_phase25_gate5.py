from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate5 import (  # noqa: E402
    Phase25Gate5AuthorizationError,
    Phase25Gate5BulkAcquisition,
    Phase25Gate5Error,
)
from packages.backtesting.phase25_gate5_policy import (  # noqa: E402
    PHASE25_GATE5_AUTHORIZATION_MODE,
    phase25_gate5_policy_fingerprint,
)
from packages.backtesting.phase25_gate5_validation import (  # noqa: E402
    Phase25Gate5IndependentValidationError,
    Phase25Gate5IndependentValidator,
)
from packages.core.exceptions import ProviderError  # noqa: E402
from packages.core.settings import load_settings  # noqa: E402


def _print_preparation(preparation) -> None:
    print(f"Phase 25 Gate5 policy: {phase25_gate5_policy_fingerprint()}")
    print(f"Through session: {preparation.through_date}")
    print(f"Execution scope: {preparation.execution_scope_id}")
    print(f"Authorization mode: {PHASE25_GATE5_AUTHORIZATION_MODE}")
    print("Interactive confirmation: NOT REQUIRED FOR READ-ONLY ACQUISITION")
    print(f"Frozen acquisition sessions including accepted probe: {len(preparation.frozen_acquisition_sessions)}")
    print(f"Frozen bulk sessions after probe: {len(preparation.frozen_bulk_sessions)}")
    print(f"Validated bulk sessions already present: {len(preparation.validated_existing_bulk_sessions)}")
    print(f"Missing bulk sessions to acquire: {len(preparation.missing_bulk_sessions)}")
    if preparation.missing_bulk_sessions:
        print(f"Next missing session: {preparation.missing_bulk_sessions[0]}")
        print(f"Last frozen bulk session: {preparation.frozen_bulk_sessions[-1]}")
    print("Accepted 2021-08-17 entitlement probe will NOT be re-fetched")
    print("Provider writes/broker/order/PAPER/LIVE/support authority: NONE")
    print("Strategy returns/protected evidence: DISABLED / UNREAD")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase25 Gate5 resumable frozen active-only Massive reference acquisition. "
            "The explicit acquire subcommand is the read-only authorization; no pasted confirmation is required."
        )
    )
    parser.add_argument("command", choices=("status", "acquire"))
    parser.add_argument("--through", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings()
    gate = Phase25Gate5BulkAcquisition(settings)
    try:
        preparation = gate.prepare(through_date=args.through)
    except (Phase25Gate5Error, ValueError) as exc:
        print("Preparation status: BLOCKED")
        print(f"Reason: {exc}")
        print("External provider calls attempted by this command: NO")
        return 2

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 5")
    _print_preparation(preparation)
    if args.command == "status":
        print("Disposition: STATUS_ONLY_ZERO_EXTERNAL_CALLS")
        return 0

    print("Disposition: ACQUIRE_FROZEN_READ_ONLY_SCOPE")
    print("The acquire command itself is the explicit provider-read authorization.")

    def progress(*, index: int, total: int, session: date, rows: int, pages: int) -> None:
        if index == 1 or index % 25 == 0 or index == total:
            print(
                f"Progress: {index}/{total} newly acquired this run | "
                f"session={session} rows={rows} pages={pages}"
            )

    try:
        authority = gate.authorize_cli_acquire(preparation)
        report = gate.execute(
            preparation,
            read_authority=authority,
            progress_callback=progress,
        )
        validation = Phase25Gate5IndependentValidator(settings).run(through_date=args.through)
    except (
        Phase25Gate5AuthorizationError,
        Phase25Gate5Error,
        Phase25Gate5IndependentValidationError,
        ProviderError,
        OSError,
        ValueError,
    ) as exc:
        print("Acquisition status: BLOCKED")
        print(f"Reason: {exc}")
        print("The same acquire command is resumable only from complete validated session pairs.")
        print("If the reason reports an unreconciled partial pair, do not blindly rerun it.")
        return 2

    print("Acquisition status: COMPLETE")
    print(f"Bulk acquisition report: {report['report_path']}")
    print(f"Independent validation: {validation['report_path']}")
    print(f"Frozen acquisition sessions: {report['frozen_acquisition_session_count']}")
    print(f"Frozen bulk sessions: {report['frozen_bulk_session_count']}")
    print(f"Validated before this run: {report['validated_bulk_sessions_before_run']}")
    print(f"Newly acquired this run: {report['newly_acquired_bulk_sessions_this_run']}")
    print(f"Validated bulk sessions after run: {report['validated_bulk_sessions_after_run']}")
    print(f"Remaining frozen bulk sessions: {report['remaining_frozen_bulk_sessions']}")
    print(f"Successful provider page reads this run: {report['successful_provider_page_reads_this_run']}")
    print(f"Probe re-fetch sessions: {report['probe_refetch_sessions']}")
    print(f"Provider writes: {report['provider_writes']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(f"Order/PAPER/LIVE writes: {report['order_writes']} / {report['paper_submits']} / {report['live_writes']}")
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Independent validation pass: {validation['pass']}")
    print(f"Pass: {report['pass'] and validation['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
