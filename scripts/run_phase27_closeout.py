from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase27_closeout import Phase27Closeout, Phase27CloseoutError
from packages.backtesting.phase27_policy import phase27_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 27 — Full Phase-End Acceptance Gate")
    print(f"Frozen alpha policy: {phase27_policy_fingerprint()}")
    print("Scope: target evidence + independent validation + end-to-end anti-workaround audit")
    print("This command does not rerun model search or read new protected performance.")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase27Closeout(settings).run()
    except (Phase27CloseoutError, FileNotFoundError, ValueError) as exc:
        print("Phase 27 closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No provider/broker/order/PAPER/LIVE authority was granted.")
        return 2

    print("Phase 27 closeout: PASS")
    print(f"Disposition: {report['phase27_disposition']}")
    print(f"Selection survivors: {report['selection_survivor_ids']}")
    print(f"Selection winners: {report['selection_winner_ids']}")
    print(f"Internal-validation finalists: {report['finalist_ids']}")
    print(f"Supported candidates: {report['supported_candidate_ids']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_returns_read']}")
    print(f"Protected holdout consumed: {report['protected_holdout_consumed']}")
    print(f"End-to-end anti-workaround audit: {report['architecture_audit_pass']}")
    print(f"Phase 28 entry satisfied: {report['phase28_entry_satisfied']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Closeout report: {report['report_path']}")
    if report["phase27_disposition"] == "ACCEPTED_NEGATIVE":
        print("Plain-English result: Phase 27 was executed correctly, but none of the frozen cross-sectional alpha architectures earned support.")
        print("The negative result is accepted; the untouched holdout remains unconsumed and trade construction stays blocked on alpha.")
    else:
        print("Plain-English result: Phase 27 earned historical analytical alpha support, but no PAPER or LIVE authority is granted by this closeout.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
