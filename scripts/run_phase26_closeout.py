from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase26_closeout import Phase26Closeout, Phase26CloseoutError
from packages.backtesting.phase26_policy import phase26_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 26 — Full Phase-End Acceptance Gate")
    print(f"Frozen alpha policy: {phase26_policy_fingerprint()}")
    print("Scope: target evidence + independent validation + end-to-end anti-workaround audit")
    print("This command does not rerun strategy search or read new protected performance.")
    print("Provider/broker/order/PAPER/LIVE activity: DISABLED")
    print()

    settings = load_settings()
    try:
        report = Phase26Closeout(settings).run()
    except (Phase26CloseoutError, FileNotFoundError, ValueError) as exc:
        print("Phase 26 closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("Phase 27 remains blocked. No trading authority was granted.")
        return 2

    print("Phase 26 closeout: PASS")
    print(f"Disposition: {report['phase26_disposition']}")
    print(f"Selection survivors: {report['selected_candidate_ids']}")
    print(f"Internal-validation finalists: {report['finalist_candidate_ids']}")
    print(f"Supported candidates: {report['supported_candidate_ids']}")
    print(f"Protected return rows read: {report['protected_returns_read']}")
    print(f"End-to-end anti-workaround audit: {report['architecture_audit_pass']}")
    print(f"Phase 27 entry satisfied: {report['phase27_entry_satisfied']}")
    print("Provider/broker/order/PAPER/LIVE activity: 0 / 0 / 0 / 0 / 0")
    print(f"Closeout report: {report['report_path']}")
    if report["phase26_disposition"] == "ACCEPTED_NEGATIVE":
        print("Plain-English result: Phase 26 was executed correctly, but none of the frozen alpha candidates earned support.")
        print("The negative result is accepted; Phase 27 stays blocked until a separately preregistered alpha phase succeeds.")
    else:
        print("Plain-English result: Phase 26 produced supported historical alpha evidence.")
        print("That support is analytical only; downstream trade construction still requires its own accepted phase.")
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
