from __future__ import annotations

import json

from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    frozen_contract_manifest,
)


def main() -> int:
    manifest = frozen_contract_manifest()
    authority = manifest["authority"]
    forbidden_true = (
        "performance_outcomes_opened",
        "development_outcome_access_permitted",
        "future_blind_outcome_access_permitted",
        "minute_replay_read_authority",
        "paper_authority",
        "live_authority",
        "broad_minute_materialization_authority",
        "promotion_authority",
    )
    if any(authority[name] for name in forbidden_true):
        raise SystemExit("B35 pre-outcome contract unexpectedly grants outcome/execution authority")
    if authority["provider_calls"] != 0 or authority["broker_reads"] != 0 or authority["broker_writes"] != 0:
        raise SystemExit("B35 pre-outcome contract must remain provider/broker inert")
    if manifest["fingerprint"] != B35_PREOUTCOME_FINGERPRINT:
        raise SystemExit("B35 pre-outcome fingerprint mismatch")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
