from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate4 import (
    Phase25Gate4AuthorizationError,
    Phase25Gate4EntitlementProbe,
    Phase25Gate4Error,
    authorize_phase25_gate4_probe,
)
from packages.backtesting.phase25_gate4_validation import (
    Phase25Gate4IndependentValidationError,
    Phase25Gate4IndependentValidator,
)
from packages.backtesting.phase25_policy import phase25_gate4_policy_fingerprint
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings


def _print_preparation(preparation) -> None:
    print(f"Phase 25 Gate4 policy: {phase25_gate4_policy_fingerprint()}")
    print(f"Through session: {preparation.through_date}")
    print(f"Frozen acquisition sessions: {preparation.acquisition_session_count}")
    print(f"Earliest entitlement probe session: {preparation.entitlement_probe_session}")
    print("Scope: ONE-SESSION MASSIVE ACTIVE-ONLY HISTORICAL REFERENCE ENTITLEMENT PROBE")
    print("Bulk acquisition: DISABLED")
    print("Strategy returns/protected evidence: DISABLED / UNREAD")
    print("Broker/order/PAPER/LIVE/support authority: NONE")
    print(f"Execution scope: {preparation.challenge.execution_scope_id}")
    print("Required exact confirmation:")
    print(preparation.challenge.required_confirmation)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "ATLAS Phase25 Gate4 one-session Massive entitlement probe. prepare is provider-free; "
            "probe requires exact interactive run-scoped authorization and cannot bulk-acquire history."
        )
    )
    parser.add_argument("command", choices=("prepare", "probe"))
    parser.add_argument("--through", required=True, type=date.fromisoformat)
    args = parser.parse_args()

    settings = load_settings()
    gate = Phase25Gate4EntitlementProbe(settings)
    try:
        preparation = gate.prepare(through_date=args.through)
    except (Phase25Gate4Error, ValueError) as exc:
        print("Preparation status: BLOCKED")
        print(f"Reason: {exc}")
        print("External provider calls attempted: NO")
        return 2

    print("ATLAS Phase 25 Historical Production-Path Replay — Gate 4")
    _print_preparation(preparation)
    if args.command == "prepare":
        print("Disposition: PREPARED_ZERO_EXTERNAL_CALLS")
        return 0

    print("Provider reads are default-deny until the exact run-scoped text above is typed.")
    confirmation = input("Type exact confirmation: ").strip()
    try:
        authority = authorize_phase25_gate4_probe(
            preparation.challenge,
            confirmation=confirmation,
            explicitly_authorized=True,
        )
        report = gate.execute_probe(preparation, read_authority=authority)
        validation = Phase25Gate4IndependentValidator(settings).run(through_date=args.through)
    except (
        Phase25Gate4AuthorizationError,
        Phase25Gate4Error,
        Phase25Gate4IndependentValidationError,
        ProviderError,
        ValueError,
    ) as exc:
        print("Probe status: BLOCKED")
        print(f"Reason: {exc}")
        print("Bulk acquisition attempted: NO")
        print("Do not blindly retry an unreconciled partial local session.")
        return 2

    print("Probe status: COMPLETE")
    print(f"Probe report: {report['report_path']}")
    print(f"Independent validation: {validation['report_path']}")
    print(f"Probe session: {report['entitlement_probe_session']}")
    print(f"Provider probe sessions: {report['provider_probe_sessions']}")
    print(f"Provider page reads: {report['provider_page_reads']}")
    print(f"Persisted rows: {report['persisted_row_count']}")
    print(f"Persisted instruments: {report['persisted_instrument_count']}")
    print(f"Bulk acquisition sessions: {report['bulk_acquisition_sessions']}")
    print(f"Remaining frozen acquisition sessions: {report['remaining_frozen_acquisition_sessions']}")
    print(f"Broker reads/writes: {report['broker_reads']} / {report['broker_writes']}")
    print(f"Order/PAPER/LIVE writes: {report['order_writes']} / {report['paper_submits']} / {report['live_writes']}")
    print(f"Phase 11 support writes: {report['phase11_support_writes']}")
    print(f"Independent validation pass: {validation['pass']}")
    print(f"Pass: {report['pass'] and validation['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
