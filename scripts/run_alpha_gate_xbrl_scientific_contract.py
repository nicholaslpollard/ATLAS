from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.alpha_gate_xbrl_scientific_policy import (
    XBRL_HYPOTHESES,
    XBRL_SCIENTIFIC_CONTRACT,
    XBRL_SCIENTIFIC_FINGERPRINT,
    scientific_contract_snapshot,
    xbrl_scientific_fingerprint,
)


def main() -> int:
    actual = xbrl_scientific_fingerprint()
    if actual != XBRL_SCIENTIFIC_FINGERPRINT:
        print(f"XBRL scientific contract: FAIL fingerprint={actual}")
        return 1
    snapshot = scientific_contract_snapshot()
    print("ATLAS XBRL Fundamental Alpha — Frozen Scientific Contract")
    print(f"Contract: {XBRL_SCIENTIFIC_CONTRACT}")
    print(f"Fingerprint: {actual}")
    print(f"Hypotheses: {len(XBRL_HYPOTHESES)}")
    for spec in XBRL_HYPOTHESES:
        print(f"- {spec.candidate_id}: {spec.direction} {spec.feature} {spec.delta_rule}")
    print(f"Primary horizon: {snapshot['primary_horizon_sessions']} XNYS sessions")
    print(f"Development last signal: {snapshot['development_last_signal']}")
    print(f"Protected first/last signal: {snapshot['protected_start']} / {snapshot['protected_last_signal']}")
    print(f"Multiplicity: {snapshot['multiple_testing_method']} alpha={snapshot['multiple_testing_alpha']}")
    print(f"Winner rule: {snapshot['selection_winner_rule']}")
    print(f"Runner-up substitution allowed: {snapshot['runner_up_substitution_allowed']}")
    print("Market prices/returns and protected returns read by this preflight: 0")
    print("Provider writes / broker / orders / PAPER / LIVE / automation: 0")
    print("Phase33 authority: False")
    print("XBRL scientific contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
