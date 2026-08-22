from __future__ import annotations

import hashlib
import json


PHASE14_POLICY_CONTRACT_VERSION = (
    "phase14-policy-v1-independent-ai-audit-structured-nonauthoritative-alerting"
)

# Phase 14 audits only deterministic Phase 13 case files that are explicitly ready
# for review. The AI is not a predictor, strategy router, candidate promoter, geometry
# engine, position sizer, broker, or order authority.
PHASE14_INPUT_REQUIRES_PHASE13_REVIEW_READY = True
PHASE14_ZERO_CASE_NOOP = True

# Structured review vocabulary is intentionally small and semantically distinct from
# execution. A review disposition can affect alert presentation only.
PHASE14_REVIEW_DISPOSITIONS = ("APPROVE", "CAUTIOUS", "REJECT")
PHASE14_DISPOSITION_IS_TRADE_SIGNAL = False
PHASE14_AI_CAN_CHANGE_DIRECTION = False
PHASE14_AI_CAN_CHANGE_INSTRUMENT = False
PHASE14_AI_CAN_CHANGE_GEOMETRY = False
PHASE14_AI_CAN_CHANGE_POSITION_SIZE = False
PHASE14_AI_CAN_CREATE_ORDER = False
PHASE14_AI_CAN_OVERRIDE_DETERMINISTIC_REJECTION = False

# The reviewer must ground every claim in the supplied case packet. It has no browsing,
# broker, market-data, code-execution, or tool authority in v1.
PHASE14_MODEL_TOOLS_ENABLED = False
PHASE14_EXTERNAL_WEB_ENABLED = False
PHASE14_MAX_REASONS = 6
PHASE14_MAX_RISK_FLAGS = 8
PHASE14_MAX_DISAGREEMENTS = 8

# OpenAI is the first provider adapter. The model is configurable at runtime, while the
# adapter contract and structured output schema remain fixed. No key is required when
# there are zero review-ready cases.
PHASE14_DEFAULT_PROVIDER = "OPENAI_RESPONSES"
PHASE14_DEFAULT_MODEL = "gpt-5.6-terra"
PHASE14_OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
PHASE14_OPENAI_TIMEOUT_SECONDS = 90
PHASE14_OPENAI_MAX_OUTPUT_TOKENS = 1800

# Alerting is artifact-first. Phase 14 creates validated alert records/outbox entries;
# it does not transmit email/SMS/push notifications. Delivery belongs to a later
# explicitly configured control-plane boundary.
PHASE14_ALERT_ARTIFACTS_ENABLED = True
PHASE14_EXTERNAL_DELIVERY_ENABLED = False
PHASE14_ALERT_REQUIRES_VALID_REVIEW = True
PHASE14_ALERT_ENGINE_VS_AI_PRESENTATION = True

PHASE14_PRODUCTION_ML_WRITES = 0
PHASE14_BROKER_WRITES = 0
PHASE14_ORDER_WRITES = 0
PHASE14_POSITION_WRITES = 0


def phase14_policy_payload() -> dict[str, object]:
    return {
        "contract_version": PHASE14_POLICY_CONTRACT_VERSION,
        "input": {
            "requires_phase13_review_ready": PHASE14_INPUT_REQUIRES_PHASE13_REVIEW_READY,
            "zero_case_noop": PHASE14_ZERO_CASE_NOOP,
        },
        "review": {
            "dispositions": list(PHASE14_REVIEW_DISPOSITIONS),
            "disposition_is_trade_signal": PHASE14_DISPOSITION_IS_TRADE_SIGNAL,
            "ai_can_change_direction": PHASE14_AI_CAN_CHANGE_DIRECTION,
            "ai_can_change_instrument": PHASE14_AI_CAN_CHANGE_INSTRUMENT,
            "ai_can_change_geometry": PHASE14_AI_CAN_CHANGE_GEOMETRY,
            "ai_can_change_position_size": PHASE14_AI_CAN_CHANGE_POSITION_SIZE,
            "ai_can_create_order": PHASE14_AI_CAN_CREATE_ORDER,
            "ai_can_override_deterministic_rejection": PHASE14_AI_CAN_OVERRIDE_DETERMINISTIC_REJECTION,
            "model_tools_enabled": PHASE14_MODEL_TOOLS_ENABLED,
            "external_web_enabled": PHASE14_EXTERNAL_WEB_ENABLED,
            "max_reasons": PHASE14_MAX_REASONS,
            "max_risk_flags": PHASE14_MAX_RISK_FLAGS,
            "max_disagreements": PHASE14_MAX_DISAGREEMENTS,
        },
        "provider": {
            "default_provider": PHASE14_DEFAULT_PROVIDER,
            "default_model": PHASE14_DEFAULT_MODEL,
            "endpoint": PHASE14_OPENAI_ENDPOINT,
            "timeout_seconds": PHASE14_OPENAI_TIMEOUT_SECONDS,
            "max_output_tokens": PHASE14_OPENAI_MAX_OUTPUT_TOKENS,
        },
        "alerting": {
            "artifact_alerts_enabled": PHASE14_ALERT_ARTIFACTS_ENABLED,
            "external_delivery_enabled": PHASE14_EXTERNAL_DELIVERY_ENABLED,
            "requires_valid_review": PHASE14_ALERT_REQUIRES_VALID_REVIEW,
            "engine_vs_ai_presentation": PHASE14_ALERT_ENGINE_VS_AI_PRESENTATION,
        },
        "authority": {
            "production_ml_writes": PHASE14_PRODUCTION_ML_WRITES,
            "broker_writes": PHASE14_BROKER_WRITES,
            "order_writes": PHASE14_ORDER_WRITES,
            "position_writes": PHASE14_POSITION_WRITES,
        },
    }


def phase14_policy_fingerprint() -> str:
    raw = json.dumps(phase14_policy_payload(), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
