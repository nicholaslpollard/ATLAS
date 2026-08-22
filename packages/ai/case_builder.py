from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from packages.schemas.case_file import Phase13CaseFile
from packages.schemas.deep_research import DeepResearchCase


AI_REVIEW_PROMPT_CONTRACT_VERSION = (
    "ai-review-prompt-v1-sanitized-phase13-plus-phase12-whitelisted-grounding"
)

_PATH_KEYS = {
    "provider_snapshot_path",
    "option_chain_snapshot_path",
    "analogue_artifact_path",
    "path_artifact_path",
}
_HASH_KEYS = {
    "provider_snapshot_sha256",
    "option_chain_snapshot_sha256",
    "analogue_artifact_sha256",
    "path_artifact_sha256",
    "research_source_fingerprint",
}


@dataclass(frozen=True, slots=True)
class ReviewPromptPacket:
    contract_version: str
    fingerprint: str
    instructions: str
    input_text: str
    case_packet: dict[str, object]
    evidence_paths: tuple[str, ...]


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _sanitize(item)
            for key, item in value.items()
            if str(key) not in _PATH_KEYS and str(key) not in _HASH_KEYS
        }
    if isinstance(value, (list, tuple)):
        return [_sanitize(item) for item in value]
    return value


def _collect_paths(value: Any, prefix: str = "") -> set[str]:
    paths: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            paths.update(_collect_paths(item, child))
        return paths
    if isinstance(value, list):
        if prefix:
            paths.add(prefix)
        return paths
    if prefix:
        paths.add(prefix)
    return paths


def build_review_case_packet(
    case: Phase13CaseFile,
    research: DeepResearchCase,
) -> ReviewPromptPacket:
    if not case.phase14_review_ready:
        raise ValueError("AI review packet requires a Phase 14 review-ready Phase 13 case")
    if case.instrument_id != research.instrument_id or case.ticker != research.ticker:
        raise ValueError("Phase 13 case and Phase 12 research identity differ")
    if case.as_of_date != research.as_of_date or case.direction != research.direction:
        raise ValueError("Phase 13 case and Phase 12 research context differ")

    phase13 = _sanitize(case.model_dump(mode="json"))
    phase12 = _sanitize(research.model_dump(mode="json"))
    packet: dict[str, object] = {
        "phase13": phase13,
        "phase12": phase12,
        "authority": {
            "deterministic_case_is_immutable": True,
            "review_disposition_is_not_trade_signal": True,
            "ai_may_not_change_direction_instrument_geometry_or_size": True,
            "ai_may_not_create_orders": True,
        },
    }
    evidence_paths = tuple(
        sorted(
            path
            for path in _collect_paths({"phase13": phase13, "phase12": phase12})
            if path.startswith("phase13.") or path.startswith("phase12.")
        )
    )
    if not evidence_paths:
        raise ValueError("AI review packet produced no groundable evidence paths")

    instructions = (
        "You are the independent ATLAS risk-and-thesis auditor. Audit only the supplied "
        "immutable evidence. Choose exactly APPROVE, CAUTIOUS, or REJECT. These labels are "
        "review dispositions for alert presentation and are never trade signals. Do not "
        "invent facts, browse, request tools, alter direction/instrument/entry/stop/target/"
        "horizon/quantity, or create an order. Every reason, risk flag, and disagreement must "
        "cite one or more exact evidence paths from the supplied whitelist. Cite leaf facts or "
        "explicit list fields; broad object-level citations are not accepted. APPROVE means the "
        "deterministic case is internally coherent with no material disagreement. CAUTIOUS "
        "means the case remains coherent but material uncertainty or weakness should be shown. "
        "REJECT means the auditor finds a material evidence-based conflict or weakness; it does "
        "not mutate or veto deterministic state. Return only schema-conforming structured data."
    )
    input_payload = {
        "case_packet": packet,
        "allowed_evidence_paths": list(evidence_paths),
    }
    input_text = json.dumps(input_payload, sort_keys=True, separators=(",", ":"), default=str)
    fp_payload = {
        "contract_version": AI_REVIEW_PROMPT_CONTRACT_VERSION,
        "instructions": instructions,
        "input": input_payload,
    }
    raw = json.dumps(fp_payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return ReviewPromptPacket(
        contract_version=AI_REVIEW_PROMPT_CONTRACT_VERSION,
        fingerprint=hashlib.sha256(raw).hexdigest(),
        instructions=instructions,
        input_text=input_text,
        case_packet=packet,
        evidence_paths=evidence_paths,
    )
