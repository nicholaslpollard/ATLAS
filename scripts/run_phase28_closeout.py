from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase28_closeout import Phase28Closeout, Phase28CloseoutError
from packages.backtesting.phase28_policy import phase28_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 28 — Full Phase-End Acceptance Gate")
    print(f"Frozen alpha policy: {phase28_policy_fingerprint()}")
    print("Scope: target evidence + independent validation + end-to-end anti-workaround audit")
    print("This command does not rerun alpha search or read new protected performance.")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase28Closeout(settings).run()
    except (Phase28CloseoutError, FileNotFoundError, ValueError) as exc:
        print("Phase 28 closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    print("Phase 28 closeout: PASS")
    print(f"Disposition: {report['phase28_disposition']}")
    print(f"Development network rows: {report['development_network_rows']}")
    print(f"Protected network predictor rows: {report['protected_network_rows']}")
    print(f"Selection survivors: {report['selection_survivor_ids']}")
    print(f"Selection winners: {report['selection_winner_ids']}")
    print(f"Internal-validation finalists: {report['finalist_ids']}")
    print(f"Supported candidates: {report['supported_candidate_ids']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_returns_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"End-to-end anti-workaround audit: {report['architecture_audit_pass']}")
    print(f"Phase 29 signal-to-trade entry satisfied: {report['phase29_entry_satisfied']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Closeout report: {report['report_path']}")
    if report["phase28_disposition"] == "ACCEPTED_NEGATIVE":
        print("Plain-English result: Phase 28 was executed correctly, but none of the frozen cross-stock network alpha hypotheses earned support.")
        print("The negative result is accepted; the protected holdout remains unconsumed and signal-to-trade construction stays blocked on validated alpha.")
    else:
        print("Plain-English result: Phase 28 earned historical analytical alpha support, but no PAPER or LIVE authority is granted by this closeout.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
