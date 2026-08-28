from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase31_predictors import (
    Phase31Form4PredictorBuilder,
    Phase31PredictorError,
)
from packages.backtesting.phase31_policy import phase31_policy_fingerprint
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS Phase 31 — Predictor-Only Form-4 Event Construction")
    print(f"Frozen scientific policy fingerprint: {phase31_policy_fingerprint()}")
    print("Source: accepted 62-shard authoritative Form-4 history")
    print("Identity: Composite-FIGI-authoritative PIT ticker intervals only")
    print("Signals: exact frozen P/S eligibility, aggregation, contradiction, 20-session cluster")
    print("Market prices/outcomes/protected returns: FORBIDDEN / UNREAD")
    print("Provider/broker/order/PAPER/LIVE/automation: DISABLED")
    print()

    try:
        report = Phase31Form4PredictorBuilder(load_settings()).run()
    except (Phase31PredictorError, OSError, ValueError) as exc:
        print("Phase 31 predictor-only construction: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print("No market-outcome or trading authority is granted.")
        return 2

    print("Phase 31 predictor-only construction: PASS")
    print(f"Authoritative rows scanned: {report['authoritative_rows_scanned']}")
    print(f"Qualified accessions before session/identity: {report['qualified_accessions_before_session_identity']}")
    print(f"Resolved noncontradictory events: {report['resolved_noncontradictory_events_all_signal_history']}")
    print(f"Development predictor rows: {report['development_predictor_rows']}")
    print(f"Protected predictor rows: {report['protected_predictor_rows']}")
    print(f"Candidate membership rows: {report['candidate_membership_rows']}")
    print(f"Exclusions: {report['exclusion_counts']}")
    print(f"Authoritative lineage SHA256: {report['authoritative_lineage_sha256']}")
    print(f"Identity interval SHA256: {report['identity_interval_sha256']}")
    print(f"Development SHA256: {report['development_sha256']}")
    print(f"Protected SHA256: {report['protected_sha256']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider/broker/order/PAPER/LIVE/automation writes: 0")
    print(f"Report: {report['report_path']}")
    print(f"Pass: {report['pass']}")
    print()
    print("A PASS freezes predictor evidence before any development-performance read.")
    print("It does not accept Phase31 or authorize protected-return access.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
