from __future__ import annotations

import hashlib
import json
from typing import Final

from packages.features.successor_practitioner import (
    SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION,
    successor_practitioner_feature_fingerprint,
)
from packages.strategies.successor_intraday_rules import (
    SUCCESSOR_INTRADAY_RULE_CONTRACT,
    successor_intraday_rule_fingerprint,
)
from packages.strategies.successor_practitioner_lab import (
    B35_CHALLENGERS,
    NEW_FAMILIES,
    RETAINED_FAMILIES,
    SUCCESSOR_LAB_CONTRACT,
)
from packages.strategies.successor_practitioner_rules import (
    SUCCESSOR_POLICY_IMPLEMENTATION_CONTRACT,
    SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT,
)


SUCCESSOR_IMPLEMENTATION_BUNDLE_CONTRACT: Final[str] = (
    "successor-practitioner-implementation-bundle-v1-preoutcome-no-authority"
)


def _canonical_sha256(payload: object) -> str:
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def frozen_successor_implementation_bundle() -> dict[str, object]:
    """Bind the accepted pre-outcome lab specification to its exact rule layers.

    This bundle is intentionally performance-blind.  It records only frozen
    scientific/mechanical identities and explicit zero-authority state so the
    later historical runner can refuse to start if any implementation component
    drifts before outcomes are opened.
    """

    family_count = len(RETAINED_FAMILIES) + len(NEW_FAMILIES)
    challenger_count = len(B35_CHALLENGERS)
    if family_count != 21:
        raise RuntimeError(f"successor implementation bundle expected 21 families, got {family_count}")
    if len(NEW_FAMILIES) != 11:
        raise RuntimeError(
            f"successor implementation bundle expected 11 new families, got {len(NEW_FAMILIES)}"
        )
    if challenger_count != 4:
        raise RuntimeError(
            f"successor implementation bundle expected 4 B35 challengers, got {challenger_count}"
        )

    payload: dict[str, object] = {
        "contract": SUCCESSOR_IMPLEMENTATION_BUNDLE_CONTRACT,
        "lab_contract": SUCCESSOR_LAB_CONTRACT,
        "family_count": family_count,
        "retained_family_count": len(RETAINED_FAMILIES),
        "new_family_count": len(NEW_FAMILIES),
        "b35_challenger_count": challenger_count,
        "policy_implementation_contract": SUCCESSOR_POLICY_IMPLEMENTATION_CONTRACT,
        "policy_implementation_fingerprint": SUCCESSOR_POLICY_IMPLEMENTATION_FINGERPRINT,
        "daily_feature_contract": SUCCESSOR_PRACTITIONER_FEATURE_CONTRACT_VERSION,
        "daily_feature_fingerprint": successor_practitioner_feature_fingerprint(),
        "intraday_rule_contract": SUCCESSOR_INTRADAY_RULE_CONTRACT,
        "intraday_rule_fingerprint": successor_intraday_rule_fingerprint(),
        "authority": {
            "strategy_authority": "RESEARCH",
            "outcome_access_authorized_by_this_bundle": False,
            "consumed_master_access": False,
            "future_blind_access": False,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "promotion_authority": False,
        },
    }
    payload["fingerprint"] = _canonical_sha256(payload)
    return payload


SUCCESSOR_IMPLEMENTATION_BUNDLE_FINGERPRINT: Final[str] = str(
    frozen_successor_implementation_bundle()["fingerprint"]
)
