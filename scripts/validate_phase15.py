from __future__ import annotations

from packages.execution.phase15_policy import (
    PHASE15_AI_DISPOSITION_IS_EXECUTION_AUTHORITY,
    PHASE15_ALLOWED_BROKERS,
    PHASE15_ALLOWED_EXECUTION_ENVIRONMENTS,
    PHASE15_AUTOMATIC_BROKER_FAILOVER,
    PHASE15_EXISTING_SAME_TICKER_ENTRY_ALLOWED,
    PHASE15_LIVE_EXECUTION_ENABLED,
    PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R,
    PHASE15_MAX_QUOTE_AGE_SECONDS,
    PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK,
    PHASE15_PRIMARY_BROKER,
    PHASE15_REQUIRE_BROKER_PREFLIGHT,
    PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT,
    PHASE15_REQUIRE_CURRENT_BROKER_RISK_REVALIDATION,
    PHASE15_REQUIRE_CURRENT_CORRELATION_WITH_EXISTING_POSITIONS,
    PHASE15_REQUIRE_PROFIT_TARGET,
    PHASE15_REQUIRE_PROTECTIVE_STOP,
    PHASE15_SECONDARY_BROKER,
    PHASE15_SHADOW_EXECUTION_ENABLED,
    PHASE15_PAPER_EXECUTION_ENABLED,
    PHASE15_OUTCOME_LEARNING_CAN_CHANGE_STRATEGY_SUPPORT,
    PHASE15_OUTCOME_LEARNING_CAN_CHANGE_THRESHOLDS,
    PHASE15_OUTCOME_LEARNING_CAN_PROMOTE_MODEL,
    phase15_policy_fingerprint,
)
from packages.execution.phase15_run import PHASE15_RUN_MANIFEST_CONTRACT_VERSION
from packages.execution.phase15_source import PHASE15_INPUT_CONTRACT_VERSION
from packages.schemas.broker_switch import BROKER_SWITCH_AUTHORIZATION_CONTRACT_VERSION
from packages.schemas.execution import (
    BROKER_ACCOUNT_CONTRACT_VERSION,
    BROKER_ORDER_PLAN_CONTRACT_VERSION,
    BROKER_ORDER_SNAPSHOT_CONTRACT_VERSION,
    BROKER_POSITION_SNAPSHOT_CONTRACT_VERSION,
    BROKER_PREFLIGHT_CONTRACT_VERSION,
    BROKER_RECONCILIATION_CONTRACT_VERSION,
    EXECUTION_INTENT_CONTRACT_VERSION,
    EXECUTION_OUTCOME_CONTRACT_VERSION,
    BrokerOrderPlan,
    ExecutionIntent,
    ExecutionOutcome,
)
from packages.schemas.execution_attempt import (
    EXECUTION_ATTEMPT_CONTRACT_VERSION,
    EXECUTION_RISK_REVALIDATION_CONTRACT_VERSION,
)
from packages.schemas.execution_run import EXECUTION_CASE_DISPOSITION_CONTRACT_VERSION


_FORBIDDEN_LIVE_AUTHORITY_FIELDS = {
    "live_authorized",
    "live_enabled",
    "production_enabled",
    "automatic_failover",
}


def main() -> None:
    intent_fields = set(ExecutionIntent.model_fields)
    plan_fields = set(BrokerOrderPlan.model_fields)
    outcome_fields = set(ExecutionOutcome.model_fields)
    checks = {
        "webull_primary": PHASE15_PRIMARY_BROKER == "webull",
        "alpaca_secondary": PHASE15_SECONDARY_BROKER == "alpaca",
        "allowed_brokers_exact": PHASE15_ALLOWED_BROKERS == ("webull", "alpaca"),
        "shadow_paper_only": PHASE15_ALLOWED_EXECUTION_ENVIRONMENTS == ("shadow", "paper"),
        "shadow_enabled": PHASE15_SHADOW_EXECUTION_ENABLED is True,
        "paper_enabled": PHASE15_PAPER_EXECUTION_ENABLED is True,
        "live_execution_disabled": PHASE15_LIVE_EXECUTION_ENABLED is False,
        "automatic_broker_failover_disabled": PHASE15_AUTOMATIC_BROKER_FAILOVER is False,
        "ai_not_execution_authority": PHASE15_AI_DISPOSITION_IS_EXECUTION_AUTHORITY is False,
        "same_ticker_add_flip_disabled": PHASE15_EXISTING_SAME_TICKER_ENTRY_ALLOWED is False,
        "quarter_r_entry_drift_exact": PHASE15_MAX_ADVERSE_ENTRY_DRIFT_R == 0.25,
        "minimum_executable_rr_exact": PHASE15_MIN_EXECUTABLE_REWARD_TO_RISK == 1.0,
        "quote_age_cap_exact": PHASE15_MAX_QUOTE_AGE_SECONDS == 30,
        "broker_preflight_required": PHASE15_REQUIRE_BROKER_PREFLIGHT is True,
        "broker_reconciliation_required": PHASE15_REQUIRE_BROKER_RECONCILIATION_BEFORE_SUBMIT is True,
        "current_risk_revalidation_required": PHASE15_REQUIRE_CURRENT_BROKER_RISK_REVALIDATION is True,
        "current_correlation_required_with_positions": PHASE15_REQUIRE_CURRENT_CORRELATION_WITH_EXISTING_POSITIONS is True,
        "protective_stop_required": PHASE15_REQUIRE_PROTECTIVE_STOP is True,
        "profit_target_required": PHASE15_REQUIRE_PROFIT_TARGET is True,
        "order_plan_has_protective_geometry": {"stop_price", "target_price", "bracket_required"}.issubset(plan_fields),
        "client_order_id_cross_broker_limit": BrokerOrderPlan.model_fields["client_order_id"].metadata[-1].max_length == 32,
        "intent_has_no_live_authority_field": not bool(intent_fields & _FORBIDDEN_LIVE_AUTHORITY_FIELDS),
        "outcome_descriptive_not_model_authority": PHASE15_OUTCOME_LEARNING_CAN_PROMOTE_MODEL is False
        and PHASE15_OUTCOME_LEARNING_CAN_CHANGE_STRATEGY_SUPPORT is False
        and PHASE15_OUTCOME_LEARNING_CAN_CHANGE_THRESHOLDS is False,
        "outcome_schema_carries_authority_guards": {
            "descriptive_only",
            "can_promote_model",
            "can_change_strategy_support",
            "can_change_thresholds",
        }.issubset(outcome_fields),
        "policy_fingerprint_present": len(phase15_policy_fingerprint()) == 64,
    }
    print(f"Phase 15 input contract: {PHASE15_INPUT_CONTRACT_VERSION}")
    print(f"Phase 15 intent contract: {EXECUTION_INTENT_CONTRACT_VERSION}")
    print(f"Phase 15 order-plan contract: {BROKER_ORDER_PLAN_CONTRACT_VERSION}")
    print(f"Phase 15 broker account contract: {BROKER_ACCOUNT_CONTRACT_VERSION}")
    print(f"Phase 15 broker preflight contract: {BROKER_PREFLIGHT_CONTRACT_VERSION}")
    print(f"Phase 15 broker order contract: {BROKER_ORDER_SNAPSHOT_CONTRACT_VERSION}")
    print(f"Phase 15 broker position contract: {BROKER_POSITION_SNAPSHOT_CONTRACT_VERSION}")
    print(f"Phase 15 broker reconciliation contract: {BROKER_RECONCILIATION_CONTRACT_VERSION}")
    print(f"Phase 15 execution risk contract: {EXECUTION_RISK_REVALIDATION_CONTRACT_VERSION}")
    print(f"Phase 15 execution attempt contract: {EXECUTION_ATTEMPT_CONTRACT_VERSION}")
    print(f"Phase 15 case disposition contract: {EXECUTION_CASE_DISPOSITION_CONTRACT_VERSION}")
    print(f"Phase 15 broker switch contract: {BROKER_SWITCH_AUTHORIZATION_CONTRACT_VERSION}")
    print(f"Phase 15 outcome contract: {EXECUTION_OUTCOME_CONTRACT_VERSION}")
    print(f"Phase 15 run manifest contract: {PHASE15_RUN_MANIFEST_CONTRACT_VERSION}")
    print(f"Phase 15 policy fingerprint: {phase15_policy_fingerprint()}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 15 static validation failed: " + ", ".join(failed))
    print("Phase 15 Broker Execution and Outcome Learning contracts: PASS")


if __name__ == "__main__":
    main()
