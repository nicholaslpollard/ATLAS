from __future__ import annotations

from packages.ai.case_builder import AI_REVIEW_PROMPT_CONTRACT_VERSION
from packages.ai.phase14_engine import PHASE14_MANIFEST_CONTRACT_VERSION
from packages.ai.phase14_policy import (
    PHASE14_AI_CAN_CHANGE_DIRECTION,
    PHASE14_AI_CAN_CHANGE_GEOMETRY,
    PHASE14_AI_CAN_CHANGE_INSTRUMENT,
    PHASE14_AI_CAN_CHANGE_POSITION_SIZE,
    PHASE14_AI_CAN_CREATE_ORDER,
    PHASE14_AI_CAN_OVERRIDE_DETERMINISTIC_REJECTION,
    PHASE14_BROKER_WRITES,
    PHASE14_DEFAULT_MODEL,
    PHASE14_EXTERNAL_DELIVERY_ENABLED,
    PHASE14_EXTERNAL_WEB_ENABLED,
    PHASE14_MODEL_TOOLS_ENABLED,
    PHASE14_OPENAI_ENDPOINT,
    PHASE14_ORDER_WRITES,
    PHASE14_POSITION_WRITES,
    PHASE14_PRODUCTION_ML_WRITES,
    PHASE14_REVIEW_DISPOSITIONS,
    phase14_policy_fingerprint,
)
from packages.ai.phase14_source import PHASE14_INPUT_CONTRACT_VERSION
from packages.ai.phase14_validation import PHASE14_VALIDATION_CONTRACT_VERSION
from packages.schemas.ai_review import (
    AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
    AI_REVIEW_RECORD_CONTRACT_VERSION,
    ALERT_RECORD_CONTRACT_VERSION,
    AIReviewPayload,
    AlertArtifactRecord,
)


_FORBIDDEN_REVIEW_FIELDS = {
    "entry",
    "entry_price",
    "reference_entry",
    "stop",
    "stop_loss",
    "target",
    "take_profit",
    "quantity",
    "proposed_quantity",
    "position_size",
    "broker",
    "order",
    "order_id",
}


def main() -> None:
    review_fields = set(AIReviewPayload.model_fields)
    alert_fields = set(AlertArtifactRecord.model_fields)
    checks = {
        "three_review_dispositions_only": PHASE14_REVIEW_DISPOSITIONS
        == ("APPROVE", "CAUTIOUS", "REJECT"),
        "ai_cannot_change_direction": PHASE14_AI_CAN_CHANGE_DIRECTION is False,
        "ai_cannot_change_instrument": PHASE14_AI_CAN_CHANGE_INSTRUMENT is False,
        "ai_cannot_change_geometry": PHASE14_AI_CAN_CHANGE_GEOMETRY is False,
        "ai_cannot_change_position_size": PHASE14_AI_CAN_CHANGE_POSITION_SIZE is False,
        "ai_cannot_create_order": PHASE14_AI_CAN_CREATE_ORDER is False,
        "ai_cannot_override_rejection": PHASE14_AI_CAN_OVERRIDE_DETERMINISTIC_REJECTION is False,
        "model_tools_disabled": PHASE14_MODEL_TOOLS_ENABLED is False,
        "external_web_disabled": PHASE14_EXTERNAL_WEB_ENABLED is False,
        "review_schema_has_no_trade_mutation_fields": not bool(review_fields & _FORBIDDEN_REVIEW_FIELDS),
        "alert_schema_has_no_order_fields": "order" not in alert_fields and "order_id" not in alert_fields,
        "external_delivery_disabled": PHASE14_EXTERNAL_DELIVERY_ENABLED is False,
        "production_ml_writes_zero": PHASE14_PRODUCTION_ML_WRITES == 0,
        "broker_writes_zero": PHASE14_BROKER_WRITES == 0,
        "order_writes_zero": PHASE14_ORDER_WRITES == 0,
        "position_writes_zero": PHASE14_POSITION_WRITES == 0,
        "responses_endpoint_exact": PHASE14_OPENAI_ENDPOINT == "https://api.openai.com/v1/responses",
        "default_model_is_gpt56_terra": PHASE14_DEFAULT_MODEL == "gpt-5.6-terra",
        "policy_fingerprint_present": len(phase14_policy_fingerprint()) == 64,
    }
    print(f"Phase 14 input contract: {PHASE14_INPUT_CONTRACT_VERSION}")
    print(f"Phase 14 prompt contract: {AI_REVIEW_PROMPT_CONTRACT_VERSION}")
    print(f"Phase 14 payload contract: {AI_REVIEW_PAYLOAD_CONTRACT_VERSION}")
    print(f"Phase 14 review record contract: {AI_REVIEW_RECORD_CONTRACT_VERSION}")
    print(f"Phase 14 alert record contract: {ALERT_RECORD_CONTRACT_VERSION}")
    print(f"Phase 14 manifest contract: {PHASE14_MANIFEST_CONTRACT_VERSION}")
    print(f"Phase 14 validation contract: {PHASE14_VALIDATION_CONTRACT_VERSION}")
    print(f"Phase 14 policy fingerprint: {phase14_policy_fingerprint()}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, value in checks.items() if not value)
        raise SystemExit("Phase 14 static validation failed: " + ", ".join(failed))
    print("Phase 14 Independent AI Audit and Alerting contracts: PASS")


if __name__ == "__main__":
    main()
