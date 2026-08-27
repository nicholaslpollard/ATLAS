from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase25_gate6_reference_rebind import (
    Phase25Gate6ReferenceRebindIndependentValidator,
    Phase25Gate6ReferenceRebindReconstruction,
)
from packages.backtesting.phase25_gate7 import Phase25Gate7RouteContextReplay
from packages.backtesting.phase25_gate7_validation import (
    Phase25Gate7IndependentValidator,
)
from packages.backtesting.phase25_prerequisite_recovery import (
    Phase25PrerequisiteRecovery,
    Phase25PrerequisiteRecoveryIndependentValidator,
)
from packages.core.settings import load_settings


FROZEN_PHASE25_THROUGH = date(2026, 8, 11)


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must use YYYY-MM-DD") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Recover the exact frozen Phase25 prerequisite lineage, independently "
            "validate it, then rebuild Phase25 Gates 6-7 without running Phase26."
        )
    )
    parser.add_argument(
        "--through-date",
        type=_parse_date,
        default=FROZEN_PHASE25_THROUGH,
        help="Frozen Phase25 through-date (default: 2026-08-11).",
    )
    parser.add_argument(
        "--allow-provider-recovery",
        action="store_true",
        help=(
            "Explicitly permit Massive reference reads only for exact PIT sessions "
            "that are missing or invalid. Valid source pairs are never re-downloaded."
        ),
    )
    args = parser.parse_args()

    if args.through_date != FROZEN_PHASE25_THROUGH:
        parser.error(
            "this recovery entrypoint is frozen to 2026-08-11 for the current "
            "Phase26 prerequisite; use a separate catch-up workflow for newer data"
        )

    settings = load_settings()
    print("=== Phase 25 authoritative prerequisite recovery ===")
    print(f"Through date: {args.through_date}")
    print(
        "Massive reads: "
        + (
            "EXPLICITLY ALLOWED IF REQUIRED"
            if args.allow_provider_recovery
            else "DEFAULT-DENY"
        )
    )
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print("Phase 26 protected strategy evidence: NOT READ")
    print()

    recovery = Phase25PrerequisiteRecovery(settings)

    def recovery_progress(**event):  # type: ignore[no-untyped-def]
        if event.get("action") != "REACQUIRE_AUTHORITATIVE":
            return
        print(
            "Recovered reference "
            f"{event['session']} rows={event.get('rows')} pages={event.get('pages')}"
        )

    recovery_report = recovery.run(
        through_date=args.through_date,
        allow_provider_recovery=args.allow_provider_recovery,
        progress_callback=recovery_progress,
    )
    recovery_validation = Phase25PrerequisiteRecoveryIndependentValidator(
        settings
    ).run(through_date=args.through_date)
    print(
        "Reference prerequisite: PASS "
        f"(sessions={recovery_report['required_session_count']}, "
        f"reused={len(recovery_report['validated_reused_sessions'])}, "
        f"reacquired={len(recovery_report['reacquired_sessions'])}, "
        f"provider_pages={recovery_report['recovery_provider_page_reads']})"
    )
    print(
        "Independent reference validation: "
        + ("PASS" if recovery_validation.get("pass") is True else "FAIL")
    )
    print()

    gate6 = Phase25Gate6ReferenceRebindReconstruction(settings)

    def gate6_progress(**event):  # type: ignore[no-untyped-def]
        index = int(event["index"])
        total = int(event["total"])
        if index == 1 or index == total or index % 100 == 0:
            summary = event["summary"]
            print(
                f"Gate 6 {index}/{total} {event['session']} "
                f"directional={summary['warm_hot_directional']}"
            )

    gate6_report = gate6.run(
        through_date=args.through_date,
        progress_callback=gate6_progress,
    )
    gate6_validation = Phase25Gate6ReferenceRebindIndependentValidator(settings).run(
        through_date=args.through_date
    )
    print(
        "Recovered reference binding: PASS "
        f"(sessions={gate6_report.get('reference_rebind_session_count', 0)}, "
        f"semantic_drift={gate6_report.get('reference_rebind_semantic_drift_count', 0)})"
    )
    print(
        "Gate 6: PASS "
        f"(sessions={gate6_report['replay_session_count']}, "
        f"directional_rows={gate6_report['warm_hot_directional_population_rows']})"
    )
    print(
        "Gate 6 independent validation: "
        + ("PASS" if gate6_validation.get("pass") is True else "FAIL")
    )
    print()

    gate7_report = Phase25Gate7RouteContextReplay(settings).run(
        through_date=args.through_date
    )
    gate7_validation = Phase25Gate7IndependentValidator(settings).run(
        through_date=args.through_date
    )
    print(
        "Gate 7: PASS "
        f"(route_eligible={gate7_report.get('fully_route_eligible_candidates')}, "
        f"route_decisions={gate7_report.get('route_decision_rows')})"
    )
    print(
        "Gate 7 independent validation: "
        + ("PASS" if gate7_validation.get("pass") is True else "FAIL")
    )
    print()
    print("=== RECOVERY COMPLETE ===")
    print("Frozen Phase 25 prerequisite lineage through 2026-08-11 is restored.")
    print("Phase 26 was NOT run by this command.")
    print("Broker/order/PAPER/LIVE activity remained disabled.")
    print(
        "Current-data catch-up is intentionally deferred; it can be done later when "
        "it helps the testing/production transition."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
