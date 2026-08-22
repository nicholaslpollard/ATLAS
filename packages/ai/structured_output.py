from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from packages.ai.phase14_policy import PHASE14_REVIEW_DISPOSITIONS
from packages.schemas.ai_review import (
    AI_REVIEW_PAYLOAD_CONTRACT_VERSION,
    AIReviewPayload,
)


class AIReviewOutputError(ValueError):
    pass


def review_json_schema(allowed_evidence_paths: Iterable[str]) -> dict[str, Any]:
    """Return a conservative strict schema for provider-side structured output.

    Length/count constraints remain in the Pydantic contract and are revalidated after
    the response. The provider schema intentionally sticks to the core JSON-Schema
    subset most broadly supported by strict Structured Outputs.
    """
    paths = sorted({str(item).strip() for item in allowed_evidence_paths if str(item).strip()})
    if not paths:
        raise AIReviewOutputError("structured review schema requires evidence paths")

    statement = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "text": {"type": "string"},
            "evidence_paths": {
                "type": "array",
                "items": {"type": "string", "enum": paths},
            },
        },
        "required": ["text", "evidence_paths"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "contract_version": {
                "type": "string",
                "enum": [AI_REVIEW_PAYLOAD_CONTRACT_VERSION],
            },
            "disposition": {
                "type": "string",
                "enum": list(PHASE14_REVIEW_DISPOSITIONS),
            },
            "summary": {"type": "string"},
            "reasons": {"type": "array", "items": statement},
            "risk_flags": {"type": "array", "items": statement},
            "disagreements": {"type": "array", "items": statement},
        },
        "required": [
            "contract_version",
            "disposition",
            "summary",
            "reasons",
            "risk_flags",
            "disagreements",
        ],
    }


def validate_review_payload(
    payload: dict[str, Any],
    *,
    allowed_evidence_paths: Iterable[str],
) -> AIReviewPayload:
    allowed = {str(item) for item in allowed_evidence_paths}
    try:
        review = AIReviewPayload.model_validate(payload)
    except ValueError as exc:
        raise AIReviewOutputError("model output violates AIReviewPayload contract") from exc
    for statement in (*review.reasons, *review.risk_flags, *review.disagreements):
        unknown = sorted(set(statement.evidence_paths) - allowed)
        if unknown:
            raise AIReviewOutputError(
                "model output cites evidence outside the immutable packet: " + ", ".join(unknown)
            )
    return review
