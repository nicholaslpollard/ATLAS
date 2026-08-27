from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase29_blindness import Phase29BlindnessError
from packages.backtesting.phase29_confirmation import Phase29ConfirmationError
from packages.backtesting.phase29_policy import phase29_policy_fingerprint
from packages.backtesting.phase29_population import Phase29PopulationError
from packages.backtesting.phase29_research import Phase29ResearchError
from packages.backtesting.phase29_runner import Phase29CumulativeRunner, Phase29RunnerError
from packages.backtesting.phase29_validation import Phase29IndependentValidationError
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 29 — Relative-Value Statistical-Arbitrage Confirmation Alpha")
    print(f"Frozen policy: {phase29_policy_fingerprint()}")
    print("Hypotheses: PCA residual reversion + nearest-distance-pair reversion, LONG/SHORT")
    print("Formation: 60 returns / 60 normalized-price closes ending t-1")
    print("PCA: 3 components; current factor score solved leave-focal-out")
    print("Pair: one minimum-distance peer; identity/statistics frozen before current dislocation")
    print("Outcome: exact focal-stock 3-session directional return; fixed top 20% score tail")
    print("Economics: 10 bps primary / 25 bps stress")
    print("Selection: chronological 75% + 3-session purge + internal + global Holm across 4")
    print("Protected evidence: inherited unopened holdout; finalist-tail keys only")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase29CumulativeRunner(settings).run()
    except (
        Phase29PopulationError,
        Phase29ResearchError,
        Phase29BlindnessError,
        Phase29ConfirmationError,
        Phase29IndependentValidationError,
        Phase29RunnerError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        print("Phase 29 target evidence: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    supported = report["confirmed_supported_candidate_ids"]
    print("Phase 29 target evidence: COMPLETE")
    print(f"Development relative-value rows: {report['development_relative_value_rows']}")
    print(f"Protected relative-value predictor rows: {report['protected_relative_value_rows']}")
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
        print("Practical result: at least one relative-value confirmation hypothesis earned historical analytical support.")
        print("This does NOT create pair-portfolio, PAPER, or LIVE authority; signal-to-trade construction is a separate phase.")
    else:
        print("Practical result: no Phase 29 relative-value hypothesis earned historical analytical support under the frozen standard.")
        print("This is valid negative evidence; downstream signal-to-trade construction remains blocked on validated alpha.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
