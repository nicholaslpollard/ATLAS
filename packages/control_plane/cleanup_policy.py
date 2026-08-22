from __future__ import annotations

import hashlib
import json


CONTROL_PLANE_CLEANUP_POLICY_VERSION = (
    "control-plane-cleanup-policy-v1-exact-plan-confirmation-rereconcile-no-writes"
)

# Cleanup is deliberately staged behind the browser/routing work. These switches stay
# false until provider-specific cancellation/close uncertainty semantics are independently
# implemented and accepted. The schemas/plans may be built and reviewed while writes are off.
PHASE16_CANCEL_PROVIDER_WRITES_ENABLED = False
PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED = False
PHASE16_CLEANUP_LIVE_ENABLED = False

# A generic broker-level confirmation is insufficient. The local user must confirm the
# exact reconciliation-derived resource plan that will be affected.
PHASE16_CLEANUP_REQUIRES_ACTION_CONFIRMATION = True
PHASE16_CLEANUP_REQUIRES_EXACT_PLAN_CONFIRMATION = True
PHASE16_CLEANUP_PLAN_CONFIRMATION_ONE_TIME = True
PHASE16_CLEANUP_PLAN_MAX_AGE_SECONDS = 120

# Provider state must be freshly reconciled immediately before any future write and must
# still match the exact plan. Drift invalidates the plan; ATLAS never expands scope.
PHASE16_CLEANUP_REQUIRES_PREFLIGHT_RECONCILIATION = True
PHASE16_CLEANUP_REQUIRES_EXACT_RESOURCE_SET_RECHECK = True
PHASE16_CLEANUP_SCOPE_EXPANSION_ALLOWED = False
PHASE16_CLEANUP_BLIND_RETRY_ALLOWED = False
PHASE16_CLEANUP_STOP_ON_FIRST_UNCERTAIN_WRITE = True
PHASE16_CLEANUP_UNKNOWN_WRITE_FAILS_CLOSED = True

# Flattening is intentionally downstream of cancellation. Existing open orders, including
# protective/bracket legs, must be resolved first so a close cannot race an outstanding leg.
PHASE16_FLATTEN_REQUIRES_ZERO_OPEN_ORDERS = True
PHASE16_AUTOMATIC_CANCEL_BEFORE_FLATTEN = False
PHASE16_AUTOMATIC_FLATTEN_FOR_BROKER_SWITCH = False
PHASE16_CROSS_BROKER_CLEANUP_ALLOWED = False

# No provider-neutral close-order execution method has been accepted yet. A read-only
# position inventory may be planned, but it cannot become executable authority in v1.
PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED = False
PHASE16_MARKET_CLOSE_ORDERS_ALLOWED = False


def cleanup_policy_payload() -> dict[str, object]:
    return {
        "contract_version": CONTROL_PLANE_CLEANUP_POLICY_VERSION,
        "provider_writes": {
            "cancel_enabled": PHASE16_CANCEL_PROVIDER_WRITES_ENABLED,
            "flatten_enabled": PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED,
            "live_enabled": PHASE16_CLEANUP_LIVE_ENABLED,
        },
        "confirmation": {
            "action_confirmation_required": PHASE16_CLEANUP_REQUIRES_ACTION_CONFIRMATION,
            "exact_plan_confirmation_required": PHASE16_CLEANUP_REQUIRES_EXACT_PLAN_CONFIRMATION,
            "plan_confirmation_one_time": PHASE16_CLEANUP_PLAN_CONFIRMATION_ONE_TIME,
            "plan_max_age_seconds": PHASE16_CLEANUP_PLAN_MAX_AGE_SECONDS,
        },
        "reconciliation": {
            "preflight_required": PHASE16_CLEANUP_REQUIRES_PREFLIGHT_RECONCILIATION,
            "exact_resource_set_recheck": PHASE16_CLEANUP_REQUIRES_EXACT_RESOURCE_SET_RECHECK,
            "scope_expansion_allowed": PHASE16_CLEANUP_SCOPE_EXPANSION_ALLOWED,
        },
        "uncertainty": {
            "blind_retry_allowed": PHASE16_CLEANUP_BLIND_RETRY_ALLOWED,
            "stop_on_first_uncertain_write": PHASE16_CLEANUP_STOP_ON_FIRST_UNCERTAIN_WRITE,
            "unknown_write_fails_closed": PHASE16_CLEANUP_UNKNOWN_WRITE_FAILS_CLOSED,
        },
        "flatten": {
            "requires_zero_open_orders": PHASE16_FLATTEN_REQUIRES_ZERO_OPEN_ORDERS,
            "automatic_cancel_before_flatten": PHASE16_AUTOMATIC_CANCEL_BEFORE_FLATTEN,
            "automatic_flatten_for_broker_switch": PHASE16_AUTOMATIC_FLATTEN_FOR_BROKER_SWITCH,
            "cross_broker_cleanup_allowed": PHASE16_CROSS_BROKER_CLEANUP_ALLOWED,
            "close_order_method_accepted": PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED,
            "market_close_orders_allowed": PHASE16_MARKET_CLOSE_ORDERS_ALLOWED,
        },
    }


def cleanup_policy_fingerprint() -> str:
    raw = json.dumps(cleanup_policy_payload(), sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def validate_cleanup_policy() -> None:
    assert PHASE16_CANCEL_PROVIDER_WRITES_ENABLED is False
    assert PHASE16_FLATTEN_PROVIDER_WRITES_ENABLED is False
    assert PHASE16_CLEANUP_LIVE_ENABLED is False
    assert PHASE16_CLEANUP_REQUIRES_ACTION_CONFIRMATION is True
    assert PHASE16_CLEANUP_REQUIRES_EXACT_PLAN_CONFIRMATION is True
    assert PHASE16_CLEANUP_PLAN_CONFIRMATION_ONE_TIME is True
    assert PHASE16_CLEANUP_PLAN_MAX_AGE_SECONDS == 120
    assert PHASE16_CLEANUP_REQUIRES_PREFLIGHT_RECONCILIATION is True
    assert PHASE16_CLEANUP_REQUIRES_EXACT_RESOURCE_SET_RECHECK is True
    assert PHASE16_CLEANUP_SCOPE_EXPANSION_ALLOWED is False
    assert PHASE16_CLEANUP_BLIND_RETRY_ALLOWED is False
    assert PHASE16_CLEANUP_STOP_ON_FIRST_UNCERTAIN_WRITE is True
    assert PHASE16_CLEANUP_UNKNOWN_WRITE_FAILS_CLOSED is True
    assert PHASE16_FLATTEN_REQUIRES_ZERO_OPEN_ORDERS is True
    assert PHASE16_AUTOMATIC_CANCEL_BEFORE_FLATTEN is False
    assert PHASE16_AUTOMATIC_FLATTEN_FOR_BROKER_SWITCH is False
    assert PHASE16_CROSS_BROKER_CLEANUP_ALLOWED is False
    assert PHASE16_FLATTEN_CLOSE_ORDER_METHOD_ACCEPTED is False
    assert PHASE16_MARKET_CLOSE_ORDERS_ALLOWED is False
