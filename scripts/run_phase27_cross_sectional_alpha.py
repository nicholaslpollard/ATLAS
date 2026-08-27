from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase27_blindness import Phase27BlindnessError
from packages.backtesting.phase27_confirmation import Phase27ConfirmationError
from packages.backtesting.phase27_models import Phase27ModelError
from packages.backtesting.phase27_policy import phase27_policy_fingerprint
from packages.backtesting.phase27_population import Phase27PopulationError
from packages.backtesting.phase27_research import Phase27ResearchError
from packages.backtesting.phase27_runner import Phase27CumulativeRunner, Phase27RunnerError
from packages.backtesting.phase27_validation import Phase27IndependentValidationError
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 27 — Cross-Sectional Expected-Return Learning & Ranking")
    print(f"Frozen policy: {phase27_policy_fingerprint()}")
    print("Hypotheses: priority baseline + Ridge + HGB + pairwise ranking, LONG/SHORT independently")
    print("Outcome: exact 3-session directional return; fixed top 20% score tail")
    print("Economics: 10 bps primary / 25 bps stress")
    print("Selection: nested chronological walk-forward + 3-session purge + global Holm across 8")
    print("Protected evidence: one-time Phase26-unopened holdout, finalist-tail keys only")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase27CumulativeRunner(settings).run()
    except (
        Phase27PopulationError,
        Phase27ModelError,
        Phase27ResearchError,
        Phase27BlindnessError,
        Phase27ConfirmationError,
        Phase27IndependentValidationError,
        Phase27RunnerError,
        FileNotFoundError,
        ValueError,
    ) as exc:
        print("Phase 27 target evidence: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    supported = report["confirmed_supported_candidate_ids"]
    print("Phase 27 target evidence: COMPLETE")
    print(f"Development model rows: {report['development_model_rows']}")
    print(f"Protected predictor rows: {report['protected_model_rows']}")
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
        print("Practical result: at least one cross-sectional alpha architecture earned historical analytical support.")
        print("This does NOT authorize PAPER or LIVE trading; Phase 28 trade construction remains a separate gate.")
    else:
        print("Practical result: no Phase 27 architecture earned historical analytical support under the frozen standard.")
        print("This is valid negative evidence; Phase 28 remains blocked on validated alpha.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
