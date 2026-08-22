from __future__ import annotations

import hashlib
import json

from packages.execution.phase15_foundation import (
    PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
    PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
)


PHASE15_POLICY_CONTRACT_VERSION = (
    "phase15-policy-v1-shadow-paper-broker-neutral-no-live-promotion"
)
PHASE15_PRIMARY_BROKER = "webull"
PHASE15_SECONDARY_BROKER = "alpaca"
PHASE15_ALLOWED_BROKERS = (PHASE15_PRIMARY_BROKER, PHASE15_SECONDARY_BROKER)

# Environment authority. Production/live order submission is intentionally not
# enabled by Phase 15 acceptance. A later explicit promotion must change this
# preregistered constant and pass a separate acceptance gate.
PHASE15_ALLOWED_EXECUTION_ENVIRONMENTS = ("shadow", "paper")
PHASE15_LIVE_EXECUTION_ENABLED = False
PHASE15_PAPER_EXECUTION_ENABLED = True
PHASE15_SHADOW_EXECUTION_ENABLED = True

# Upstream authority. The cumulative historical foundation is a hard prerequisite
# alongside accepted Phase 14. Its exact target-machine acceptance fingerprint is
# locked before Phase 15 can resolve even a zero-case execution run.
PHASE15_REQUIRE_ACCEPTED_CUMULATIVE_FOUNDATION = True
PHASE15_REQUIRE_ACCEPTED_PHASE14 = True
PHASE15_REQUIRE_PHASE13_REVIEW_READY = True
PHASE15_AI_DISPOSITION_IS_EXECUTION_AUTHORITY = False
PHASE15_ALERT_IS_EXECUTION_AUTHORITY = False

# Broker switching is explicit and fail-closed. ATLAS never silently moves an
# order to the fallback broker after a reject, timeout, disconnect, or partial
# fill because that can create duplicate exposure.
PHASE15_AUTOMATIC_BROKER_FAILOVER = False
PHASE15_BROKER_SWITCH_REQUIRES_ZERO_OPEN_ORDERS = True
PHASE15_BROKER_SWITCH_REQUIRES_ZERO_POSITIONS = True
PHASE15_BROKER_SWITCH_REQUIRES_RECONCILIATION = True

# v1 executes equity only because the accepted Phase 13 primary instrument is
# equity and no option relative-value model has been accepted. It also refuses
# additive/reversal entries when the selected broker already has that ticker;
# position adjustment semantics belong in a later explicit portfolio/order phase.
PHASE15_ALLOWED_INSTRUMENT_KINDS = ("EQUITY",)
PHASE15_EXISTING_SAME_TICKER_ENTRY_ALLOWED = False
PHASE15_ENTRY_ORDER_TYPE = "LIMIT"
PHASE15_TIME_IN_FORCE = "DAY"
PHASE15_EXTENDED_HOURS_ENABLED = False

# Execution translation from a Phase 13 reference plan. The original stop and
# target remain fixed thesis levels. Entry may only move adversely by at most
# 0.25 of the original reference risk distance; favorable movement is allowed
# provided entry remains strictly between stop and target. Final quantity is
# recomputed from the accepted Phase 13 dollar risk budget and may never exceed
# the accepted proposed quantity.
PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R = 0.25
PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK = 1.0
PHASE15_MAX_QUOTE_AGE_SECONDS = 30
PHASE15_REQUIRE_REALTIME_QUOTE_FOR_BROKER_SUBMISSION = True
PHASE15_REQUIRE_BROKER_PREFLIGHT = True
PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT = True

# The Phase 13 portfolio snapshot is not permanent execution authority. Immediately
# before submission, current broker equity/exposure must still satisfy the accepted
# Phase 13 risk envelope. If any positions are open, fresh current correlation
# evidence is mandatory; stale Phase 13 correlation is never silently reused.
PHASE15_REQUIRE_CURRENT_BROKER_RISK_REVALIDATION = True
PHASE15_REQUIRE_CURRENT_CORRELATION_WITH_EXISTING_POSITIONS = True

# Protective exits must be represented in the broker-neutral order plan before
# a paper/sandbox entry can be submitted. Broker adapters may translate this to
# native bracket/OTOCO semantics but may not remove the stop or target.
PHASE15_REQUIRE_PROTECTIVE_STOP = True
PHASE15_REQUIRE_PROFIT_TARGET = True

# Outcome learning is descriptive evidence. It cannot mutate historical labels,
# strategy support, model registry authority, or routing thresholds in Phase 15.
PHASE15_OUTCOME_LEARNING_CAN_PROMOTE_MODEL = False
PHASE15_OUTCOME_LEARNING_CAN_CHANGE_STRATEGY_SUPPORT = False
PHASE15_OUTCOME_LEARNING_CAN_CHANGE_THRESHOLDS = False


def phase15_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE15_POLICY_CONTRACT_VERSION,
        "primary_broker": PHASE15_PRIMARY_BROKER,
        "secondary_broker": PHASE15_SECONDARY_BROKER,
        "allowed_brokers": list(PHASE15_ALLOWED_BROKERS),
        "allowed_execution_environments": list(PHASE15_ALLOWED_EXECUTION_ENVIRONMENTS),
        "live_execution_enabled": PHASE15_LIVE_EXECUTION_ENABLED,
        "paper_execution_enabled": PHASE15_PAPER_EXECUTION_ENABLED,
        "shadow_execution_enabled": PHASE15_SHADOW_EXECUTION_ENABLED,
        "require_accepted_cumulative_foundation": PHASE15_REQUIRE_ACCEPTED_CUMULATIVE_FOUNDATION,
        "accepted_cumulative_foundation_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_FOUNDATION_FINGERPRINT,
        "accepted_cumulative_policy_fingerprint": PHASE15_ACCEPTED_CUMULATIVE_POLICY_FINGERPRINT,
        "require_accepted_phase14": PHASE15_REQUIRE_ACCEPTED_PHASE14,
        "require_phase13_review_ready": PHASE15_REQUIRE_PHASE13_REVIEW_READY,
        "ai_disposition_is_execution_authority": PHASE15_AI_DISPOSITION_IS_EXECUTION_AUTHORITY,
        "alert_is_execution_authority": PHASE15_ALERT_IS_EXECUTION_AUTHORITY,
        "automatic_broker_failover": PHASE15_AUTOMATIC_BROKER_FAILOVER,
        "broker_switch_requires_zero_open_orders": PHASE15_BROKER_SWITCH_REQUIRES_ZERO_OPEN_ORDERS,
        "broker_switch_requires_zero_positions": PHASE15_BROKER_SWITCH_REQUIRES_ZERO_POSITIONS,
        "broker_switch_requires_reconciliation": PHASE15_BROKER_SWITCH_REQUIRES_RECONCILIATION,
        "allowed_instrument_kinds": list(PHASE15_ALLOWED_INSTRUMENT_KINDS),
        "existing_same_ticker_entry_allowed": PHASE15_EXISTING_SAME_TICKER_ENTRY_ALLOWED,
        "entry_order_type": PHASE15_ENTRY_ORDER_TYPE,
        "time_in_force": PHASE15_TIME_IN_FORCE,
        "extended_hours_enabled": PHASE15_EXTENDED_HOURS_ENABLED,
        "max_adverse_entry_drift_r": PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R,
        "min_executable_reward_to_risk": PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK,
        "max_quote_age_seconds": PHASE15_MAX_QUOTE_AGE_SECONDS,
        "require_realtime_quote_for_broker_submission": PHASE15_REQUIRE_REALTIME_QUOTE_FOR_BROKER_SUBMISSION,
        "require_broker_preflight": PHASE15_REQUIRE_BROKER_PREFLIGHT,
        "require_broker_reconciliation_before_submit": PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT,
        "require_current_broker_risk_revalidation": PHASE15_REQUIRE_CURRENT_BROKER_RISK_REVALIDATION,
        "require_current_correlation_with_existing_positions": PHASE15_REQUIRE_CURRENT_CORRELATION_WITH_EXISTING_POSITIONS,
        "require_protective_stop": PHASE15_REQUIRE_PROTECTIVE_STOP,
        "require_profit_target": PHASE15_REQUIRE_PROFIT_TARGET,
        "outcome_learning_can_promote_model": PHASE15_OUTCOME_LEARNING_CAN_PROMOTE_MODEL,
        "outcome_learning_can_change_strategy_support": PHASE15_OUTCOME_LEARNING_CAN_CHANGE_STRATEGY_SUPPORT,
        "outcome_learning_can_change_thresholds": PHASE15_OUTCOME_LEARNING_CAN_CHANGE_THRESHOLDS,
    }


def phase15_policy_fingerprint() -> str:
    raw = json.dumps(
        phase15_policy_payload(), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
