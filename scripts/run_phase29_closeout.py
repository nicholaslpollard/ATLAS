from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase29_closeout import Phase29Closeout, Phase29CloseoutError
from packages.backtesting.phase29_policy import phase29_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 29 — Full Phase-End Acceptance Gate")
    print(f"Frozen alpha policy: {phase29_policy_fingerprint()}")
    print("Scope: persisted target evidence + independent validation + end-to-end anti-workaround audit")
    print("This command does not rerun alpha search or read new protected performance.")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase29Closeout(settings).run()
    except (Phase29CloseoutError, FileNotFoundError, ValueError) as exc:
        print("Phase 29 closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    print("Phase 29 closeout: PASS")
    print(f"Disposition: {report['phase29_disposition']}")
    print(f"Development relative-value rows: {report['development_relative_value_rows']}")
    print(f"Protected relative-value predictor rows: {report['protected_relative_value_rows']}")
    print(f"Selection survivors: {report['selection_survivor_ids']}")
    print(f"Selection winners: {report['selection_winner_ids']}")
    print(f"Internal-validation finalists: {report['finalist_ids']}")
    print(f"Supported candidates: {report['supported_candidate_ids']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_returns_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"End-to-end anti-workaround audit: {report['architecture_audit_pass']}")
    print(f"Phase 30 signal-to-trade entry satisfied: {report['phase30_entry_satisfied']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Closeout report: {report['report_path']}")
    if report["phase29_disposition"] == "ACCEPTED_NEGATIVE":
        print("Plain-English result: Phase 29 was executed correctly, but none of the frozen relative-value hypotheses earned support.")
        print("The negative result is accepted; the protected holdout remains unconsumed and Phase 30 stays blocked on validated alpha.")
    else:
        print("Plain-English result: Phase 29 earned historical analytical alpha support, but no pair-portfolio, PAPER, or LIVE authority is granted by this closeout.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
