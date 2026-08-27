from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase26_confirmation import Phase26ConfirmationError
from packages.backtesting.phase26_observations import Phase26ObservationError
from packages.backtesting.phase26_policy import phase26_policy_fingerprint
from packages.backtesting.phase26_research import Phase26ResearchError
from packages.backtesting.phase26_runner import Phase26CumulativeRunner, Phase26RunnerError
from packages.backtesting.phase26_validation import Phase26IndependentValidationError
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 26 — Production-Path-Native Alpha Discovery & Validation")
    print(f"Frozen policy: {phase26_policy_fingerprint()}")
    print("Purpose: test 24 materially different production-path-native strategy candidates")
    print("Research population: accepted Phase25 production candidates + exact PIT context")
    print("Economics: 10 bps primary / 25 bps stress")
    print("Selection: chronological + purge + session-dependence + global multiplicity control")
    print("Protected returns: finalist-only; remain unread when there are zero finalists")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase26CumulativeRunner(settings).run()
    except (
        Phase26ObservationError,
        Phase26ResearchError,
        Phase26ConfirmationError,
        Phase26IndependentValidationError,
        Phase26RunnerError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        print("Phase 26 target evidence: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    supported = report["confirmed_supported_candidate_ids"]
    print("Phase 26 target evidence: COMPLETE")
    print(f"Development usable observations: {report['development_usable_rows']}")
    print(f"Protected predictor observations: {report['protected_predictor_rows']}")
    print(f"Selection survivors: {report['selected_candidate_ids']}")
    print(f"Internal-validation finalists: {report['finalist_candidate_ids']}")
    print(f"Protected-confirmed supported candidates: {supported}")
    print(f"Protected return rows read: {report['protected_returns_read']}")
    print(f"Independent validation pass: {report['independent_validation_pass']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Cumulative report: {report['report_path']}")
    if supported:
        print("Practical result: at least one strategy earned historical analytical support.")
        print("This does NOT authorize PAPER or LIVE trading; Phase27 trade construction is still required.")
    else:
        print("Practical result: no strategy earned historical analytical support under the frozen Phase26 standard.")
        print("This is valid negative evidence; downstream trading phases remain blocked on alpha.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
