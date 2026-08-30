from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_beneficial_ownership_closeout import (
    BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
    BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT,
    BENEFICIAL_OWNERSHIP_CLOSEOUT_CONTRACT,
    BeneficialOwnershipCloseoutError,
    validate_beneficial_ownership_negative_closeout,
)
from packages.backtesting.alpha_gate_beneficial_ownership_development import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT,
)
from packages.backtesting.alpha_gate_beneficial_ownership_scientific_policy import (
    BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT,
)
from packages.backtesting.alpha_gate_beneficial_ownership_transport_repair import (
    BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS SEC Schedule 13D/13G Beneficial Ownership — Negative Closeout")
    print(f"Closeout contract: {BENEFICIAL_OWNERSHIP_CLOSEOUT_CONTRACT}")
    print(
        "Accepted development target head: "
        f"{BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD}"
    )
    print(f"Scientific fingerprint: {BENEFICIAL_OWNERSHIP_SCIENTIFIC_FINGERPRINT}")
    print(
        "Development implementation fingerprint: "
        f"{BENEFICIAL_OWNERSHIP_DEVELOPMENT_IMPLEMENTATION_FINGERPRINT}"
    )
    print(
        "Development transport repair fingerprint: "
        f"{BENEFICIAL_OWNERSHIP_DEVELOPMENT_TRANSPORT_REPAIR_FINGERPRINT}"
    )
    print(
        "Accepted closeout evidence fingerprint: "
        f"{BENEFICIAL_OWNERSHIP_ACCEPTED_EVIDENCE_FINGERPRINT}"
    )
    print("Protected returns: FORBIDDEN / UNREAD")
    print("Provider calls: DISABLED / ZERO")
    print("Provider writes / broker / orders / PAPER / LIVE / automation: DISABLED")
    print()

    try:
        result = validate_beneficial_ownership_negative_closeout(load_settings())
    except (BeneficialOwnershipCloseoutError, OSError, ValueError, TypeError) as exc:
        print("Beneficial-ownership negative closeout: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "No protected return, historical support, Phase33 entry, or trading authority was granted."
        )
        return 2

    evidence = result["evidence"]
    print("Beneficial-ownership negative closeout: PASS")
    print(f"Disposition: {result['disposition']}")
    print(f"Evidence fingerprint: {result['evidence_fingerprint']}")
    print(f"Development report SHA-256: {evidence['development_report_sha256']}")
    print(f"Predictor report SHA-256: {evidence['predictor_report_sha256']}")
    print(f"Predictor rows SHA-256: {evidence['predictor_rows_sha256']}")
    print(f"Development outcomes SHA-256: {evidence['development_outcomes_sha256']}")
    print(f"Finalists SHA-256: {evidence['finalists_sha256']}")
    print(f"Development status: {evidence['development_status']}")
    print(f"Predictor rows: {evidence['predictor_rows']}")
    print(f"Development predictor rows: {evidence['development_predictor_rows']}")
    print(f"Development outcome rows: {evidence['development_outcome_rows']}")
    print(f"Protected predictor rows: {evidence['protected_predictor_rows']}")
    print(f"Selection passers: {evidence['selection_passers']}")
    print(f"Selection winners: {evidence['selection_winners']}")
    print(f"Internal finalists: {evidence['internal_finalists']}")
    print(
        "Protected-return eligible finalists: "
        f"{evidence['protected_return_eligible_finalists']}"
    )
    print(f"Protected return rows read: {result['protected_return_rows_read']}")
    print(f"Protected holdout consumed: {result['protected_holdout_consumed']}")
    print(f"Historical supported alpha: {result['historical_supported_alpha']}")
    print(f"Phase33 authority: {result['phase33_signal_to_trade_authority']}")
    print(
        "Provider reads / provider writes / broker reads / broker writes / orders / PAPER / LIVE / automation: "
        f"{result['provider_reads_performed']} / {result['provider_writes_performed']} / "
        f"{result['broker_reads_performed']} / {result['broker_writes_performed']} / "
        f"{result['order_writes_performed']} / {result['paper_submits_performed']} / "
        f"{result['live_writes_performed']} / {result['automation_writes_performed']}"
    )
    print(
        "Next scientific action: close this beneficial-ownership family without support and select a materially different alpha mechanism; do not retune this family after results."
    )
    print(f"Pass: {result['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
