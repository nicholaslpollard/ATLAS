from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase28_blindness import Phase28BlindnessError
from packages.backtesting.phase28_confirmation import Phase28ConfirmationError
from packages.backtesting.phase28_policy import phase28_policy_fingerprint
from packages.backtesting.phase28_population import Phase28PopulationError
from packages.backtesting.phase28_research import Phase28ResearchError
from packages.backtesting.phase28_runner import Phase28CumulativeRunner, Phase28RunnerError
from packages.backtesting.phase28_validation import Phase28IndependentValidationError
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 28 — Cross-Stock Lead-Lag & Residual Network Alpha")
    print(f"Frozen policy: {phase28_policy_fingerprint()}")
    print("Hypotheses: residual momentum + peer 1d/5d lead + diffusion gap, LONG/SHORT independently")
    print("Network: 60 lag pairs ending t-1; top 3 positive asymmetric leaders; minimum 2")
    print("Outcome: exact 3-session directional return; fixed top 20% score tail")
    print("Economics: 10 bps primary / 25 bps stress")
    print("Selection: chronological 75% + 3-session purge + internal validation + global Holm across 8")
    print("Protected evidence: inherited unopened holdout; finalist-tail keys only")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase28CumulativeRunner(settings).run()
    except (
        Phase28PopulationError,
        Phase28ResearchError,
        Phase28BlindnessError,
        Phase28ConfirmationError,
        Phase28IndependentValidationError,
        Phase28RunnerError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        print("Phase 28 target evidence: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    supported = report["confirmed_supported_candidate_ids"]
    print("Phase 28 target evidence: COMPLETE")
    print(f"Development network rows: {report['development_network_rows']}")
    print(f"Protected network predictor rows: {report['protected_network_rows']}")
    print(f"Selection survivors: {report['selection_survivor_ids']}")
    print(f"Selection winners: {report['selection_winner_ids']}")
    print(f"Internal-validation finalists: {report['finalist_ids']}")
    print(f"Protected-confirmed supported candidates: {supported}")
    print(f"Protected candidate rows queried: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_returns_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"Independent validation pass: {report['independent_validation_pass']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Cumulative report: {report['report_path']}")
    if supported:
        print("Practical result: at least one cross-stock network alpha hypothesis earned historical analytical support.")
        print("This does NOT authorize PAPER or LIVE trading; Phase 29 signal-to-trade construction is a separate gate.")
    else:
        print("Practical result: no Phase 28 network alpha hypothesis earned historical analytical support under the frozen standard.")
        print("This is valid negative evidence; Phase 29 remains blocked on validated alpha.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
