from __future__ import annotations

import hashlib
import json


REFERENCE_PORTFOLIO_POLICY_CONTRACT_VERSION = (
    "a34-reference-account-replay-v1-long-only-equal-risk-family-balanced-no-authority"
)

# This is a deterministic product/replay baseline, not an optimized selector and
# not qualifying historical evidence. Values are frozen before any ATLAS portfolio
# result is opened.
REFERENCE_PORTFOLIO_INITIAL_EQUITY = 100_000.0
REFERENCE_PORTFOLIO_ACCOUNT_RISK_FRACTION = 0.0025
REFERENCE_PORTFOLIO_MAX_POSITION_FRACTION = 0.10
REFERENCE_PORTFOLIO_MAX_GROSS_FRACTION = 1.00
REFERENCE_PORTFOLIO_MAX_OPEN_POSITIONS = 10
REFERENCE_PORTFOLIO_MAX_POSITIONS_PER_FAMILY = 3
REFERENCE_PORTFOLIO_PRIMARY_ROUND_TRIP_COST_BPS = 10.0
REFERENCE_PORTFOLIO_ENTRY_COST_BPS = 5.0
REFERENCE_PORTFOLIO_EXIT_COST_BPS = 5.0
REFERENCE_PORTFOLIO_SELECTOR = "LOWEST_ACTIVE_FAMILY_LOAD_THEN_STABLE_IDENTIFIERS"
REFERENCE_PORTFOLIO_LONG_ALLOWED = True
REFERENCE_PORTFOLIO_SHORT_ALLOWED = False
REFERENCE_PORTFOLIO_SHORT_BORROW_MODELED = False
REFERENCE_PORTFOLIO_ONE_POSITION_PER_INSTRUMENT = True
REFERENCE_PORTFOLIO_REQUIRES_RESOLVED_EXIT = True
REFERENCE_PORTFOLIO_CORRELATION_MODEL_AVAILABLE = False
REFERENCE_PORTFOLIO_SECTOR_MODEL_AVAILABLE = False
REFERENCE_PORTFOLIO_QUALIFYING_HISTORICAL = False
REFERENCE_PORTFOLIO_AUTHORITY_PROMOTION = False
REFERENCE_PORTFOLIO_PROVIDER_WRITES = 0
REFERENCE_PORTFOLIO_BROKER_WRITES = 0
REFERENCE_PORTFOLIO_PAPER_SUBMITS = 0
REFERENCE_PORTFOLIO_LIVE_WRITES = 0


def reference_portfolio_policy_payload() -> dict[str, object]:
    return {
        "contract_version": REFERENCE_PORTFOLIO_POLICY_CONTRACT_VERSION,
        "capital": {
            "initial_equity": REFERENCE_PORTFOLIO_INITIAL_EQUITY,
            "account_risk_fraction": REFERENCE_PORTFOLIO_ACCOUNT_RISK_FRACTION,
            "maximum_position_fraction": REFERENCE_PORTFOLIO_MAX_POSITION_FRACTION,
            "maximum_gross_fraction": REFERENCE_PORTFOLIO_MAX_GROSS_FRACTION,
            "maximum_open_positions": REFERENCE_PORTFOLIO_MAX_OPEN_POSITIONS,
            "maximum_positions_per_family": REFERENCE_PORTFOLIO_MAX_POSITIONS_PER_FAMILY,
            "one_position_per_instrument": REFERENCE_PORTFOLIO_ONE_POSITION_PER_INSTRUMENT,
        },
        "selection": {
            "selector": REFERENCE_PORTFOLIO_SELECTOR,
            "long_allowed": REFERENCE_PORTFOLIO_LONG_ALLOWED,
            "short_allowed": REFERENCE_PORTFOLIO_SHORT_ALLOWED,
            "short_borrow_modeled": REFERENCE_PORTFOLIO_SHORT_BORROW_MODELED,
            "requires_resolved_exit": REFERENCE_PORTFOLIO_REQUIRES_RESOLVED_EXIT,
            "uses_realized_outcome_to_rank_same_session_candidates": False,
        },
        "costs": {
            "primary_round_trip_cost_bps": REFERENCE_PORTFOLIO_PRIMARY_ROUND_TRIP_COST_BPS,
            "entry_cost_bps": REFERENCE_PORTFOLIO_ENTRY_COST_BPS,
            "exit_cost_bps": REFERENCE_PORTFOLIO_EXIT_COST_BPS,
        },
        "unavailable_controls": {
            "correlation_model_available": REFERENCE_PORTFOLIO_CORRELATION_MODEL_AVAILABLE,
            "sector_model_available": REFERENCE_PORTFOLIO_SECTOR_MODEL_AVAILABLE,
        },
        "authority": {
            "qualifying_historical": REFERENCE_PORTFOLIO_QUALIFYING_HISTORICAL,
            "authority_promotion": REFERENCE_PORTFOLIO_AUTHORITY_PROMOTION,
            "provider_writes": REFERENCE_PORTFOLIO_PROVIDER_WRITES,
            "broker_writes": REFERENCE_PORTFOLIO_BROKER_WRITES,
            "paper_submits": REFERENCE_PORTFOLIO_PAPER_SUBMITS,
            "live_writes": REFERENCE_PORTFOLIO_LIVE_WRITES,
        },
    }


def reference_portfolio_policy_fingerprint() -> str:
    raw = json.dumps(
        reference_portfolio_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
