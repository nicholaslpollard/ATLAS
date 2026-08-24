from __future__ import annotations

import argparse

from packages.control_plane.phase18_authorization import (
    Phase18AuthorizationError,
    Phase18MutationAuthorization,
    require_phase18_mutation_authorization,
)
from packages.control_plane.phase18_policy import PHASE18_CONFIRMATION_TEXT


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Sanitized Phase 18 authorization diagnostic. This script never initializes "
            "a broker adapter and never performs a provider mutation."
        )
    )
    parser.add_argument("--broker", choices=("webull", "alpaca"), default="webull")
    parser.add_argument(
        "--authorize-paper-provider-mutation",
        action="store_true",
        help="Exercise the local authorization gate only; this diagnostic still performs no provider calls.",
    )
    parser.add_argument(
        "--confirmation",
        default="",
        help=(
            "Exact confirmation text required by the Phase 18 gate. This diagnostic "
            "does not turn a successful gate check into a provider write."
        ),
    )
    args = parser.parse_args()

    authorization = Phase18MutationAuthorization(
        broker=args.broker,
        authorize_provider_mutation=args.authorize_paper_provider_mutation,
        confirmation_text=args.confirmation,
    )

    print("ATLAS Phase 18 paper-provider mutation gate diagnostic")
    print(f"Selected broker: {args.broker}")
    print("Provider adapter initialized: NO")
    print("Provider calls performed: 0")
    print("Provider writes performed: 0")
    print("Live execution: DISABLED")
    print("Automatic cross-broker failover: DISABLED")
    try:
        accepted = require_phase18_mutation_authorization(authorization)
    except Phase18AuthorizationError as exc:
        print("Authorization gate: DENIED")
        print(f"Reason: {exc}")
        print(f"Required confirmation text: {PHASE18_CONFIRMATION_TEXT}")
        return

    print("Authorization gate: ACCEPTED_LOCALLY")
    print(f"Authorized broker: {accepted.normalized_broker}")
    print("Important: this diagnostic still performed zero provider writes.")


if __name__ == "__main__":
    main()
