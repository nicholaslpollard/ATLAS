from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_beneficial_ownership_closeout_probe import (
    BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD,
    BENEFICIAL_OWNERSHIP_CLOSEOUT_PROBE_CONTRACT,
    BeneficialOwnershipCloseoutProbeError,
    collect_beneficial_ownership_closeout_evidence,
)
from packages.core.settings import load_settings


def main() -> int:
    print("ATLAS SEC Schedule 13D/13G Beneficial Ownership — Closeout Evidence Probe")
    print(f"Probe contract: {BENEFICIAL_OWNERSHIP_CLOSEOUT_PROBE_CONTRACT}")
    print(
        "Accepted development target head: "
        f"{BENEFICIAL_OWNERSHIP_ACCEPTED_DEVELOPMENT_TARGET_HEAD}"
    )
    print("Evidence source: PERSISTED LOCAL ARTIFACTS ONLY")
    print("Provider/network calls: DISABLED / ZERO")
    print("Development/protected outcome recomputation: DISABLED")
    print("Protected returns: FORBIDDEN / UNREAD")
    print("Broker / orders / PAPER / LIVE / automation: DISABLED")
    print()
    try:
        report = collect_beneficial_ownership_closeout_evidence(load_settings())
    except (BeneficialOwnershipCloseoutProbeError, OSError, ValueError, TypeError) as exc:
        print("Beneficial-ownership closeout evidence probe: NOT ACCEPTED")
        print(f"Reason: {exc}")
        return 2

    print("Beneficial-ownership closeout evidence probe: PASS")
    print(f"Disposition candidate: {report['disposition']}")
    print(f"Evidence fingerprint: {report['evidence_fingerprint']}")
    print("Exact evidence package:")
    print(json.dumps(report["evidence"], indent=2, sort_keys=True))
    print("Provider reads performed by probe: 0")
    print("Protected return rows read by probe: 0")
    print("Ready to pin: True")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
