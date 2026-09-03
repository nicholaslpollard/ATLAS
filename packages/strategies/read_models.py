from __future__ import annotations

from packages.strategies.reference_library import (
    REFERENCE_STRATEGY_AUTHORITIES,
    REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT,
    REFERENCE_STRATEGY_CATALOG,
    REFERENCE_STRATEGY_POLICY_FINGERPRINT,
)


REFERENCE_STRATEGY_READ_MODEL_CONTRACT_VERSION = (
    "reference-strategy-read-model-v1-policy-authority-separated-read-only"
)


def reference_strategy_catalog_read_model() -> dict[str, object]:
    authority_by_id = {item.strategy_id: item for item in REFERENCE_STRATEGY_AUTHORITIES}
    strategies = []
    for specification in REFERENCE_STRATEGY_CATALOG.all():
        authority = authority_by_id[specification.strategy_id]
        strategies.append(
            {
                "specification": specification.model_dump(mode="json"),
                "policy_fingerprint": specification.fingerprint(),
                "authority": authority.model_dump(mode="json"),
            }
        )
    return {
        "contract_version": REFERENCE_STRATEGY_READ_MODEL_CONTRACT_VERSION,
        "catalog_fingerprint": REFERENCE_STRATEGY_POLICY_FINGERPRINT,
        "authority_fingerprint": REFERENCE_STRATEGY_AUTHORITY_FINGERPRINT,
        "family_count": len(REFERENCE_STRATEGY_CATALOG.family_ids()),
        "strategy_count": len(strategies),
        "family_ids": list(REFERENCE_STRATEGY_CATALOG.family_ids()),
        "strategies": strategies,
        "execution_boundaries": {
            "research_replay_allowed": True,
            "operational_paper_allowed": False,
            "qualifying_paper_allowed": False,
            "live_allowed": False,
            "broker_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
        },
    }
