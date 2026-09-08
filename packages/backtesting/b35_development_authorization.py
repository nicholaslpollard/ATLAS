from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from packages.backtesting.b35_development_source import B35DevelopmentSourcePlan
from packages.backtesting.b35_split_evidence import B35SplitEvidence
from packages.core.atomic_io import atomic_write_text
from packages.strategies.b35_conditional_evidence_contract import (
    B34_PACK_FINGERPRINT,
    B35_PREOUTCOME_FINGERPRINT,
    CONSUMED_MASTER_END,
    CONSUMED_MASTER_START,
    FUTURE_BLIND_START_ON_OR_AFTER,
)


B35_DEVELOPMENT_AUTHORIZATION_CONTRACT = (
    "atlas-b35-development-outcome-authorization-v1-immutable-pre-read"
)
B35_DEVELOPMENT_AUTHORIZATION_PURPOSE = (
    "B35_FROZEN_INTRADAY_CONDITIONAL_DEVELOPMENT_REPLAY"
)


class B35DevelopmentAuthorizationError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _authorization_id(document: dict[str, object]) -> str:
    return _stable_hash({key: value for key, value in document.items() if key != "authorization_id"})


def _required_binding(
    plan: B35DevelopmentSourcePlan,
    split_evidence: B35SplitEvidence,
) -> dict[str, object]:
    return {
        "contract": B35_DEVELOPMENT_AUTHORIZATION_CONTRACT,
        "status": "AUTHORIZED_PENDING_DEVELOPMENT_OUTCOME_READ",
        "purpose": B35_DEVELOPMENT_AUTHORIZATION_PURPOSE,
        "authorization_mechanism": "EXPLICIT_OPERATOR_CLI_FLAG",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "b34_pack_fingerprint": B34_PACK_FINGERPRINT,
        "source_contract": plan.contract,
        "source_fingerprint": plan.source_fingerprint,
        "native_plan_sha256": plan.native_plan_sha256,
        "native_plan_file_sha256": plan.native_plan_file_sha256,
        "split_evidence_contract": split_evidence.contract,
        "split_evidence_fingerprint": split_evidence.fingerprint,
        "corporate_actions_sha256": split_evidence.corporate_actions_sha256,
        "development_start_session": plan.start_session.isoformat(),
        "development_end_session": plan.end_session.isoformat(),
        "consumed_master_start": CONSUMED_MASTER_START.isoformat(),
        "consumed_master_end": CONSUMED_MASTER_END.isoformat(),
        "consumed_master_rows_permitted": 0,
        "future_blind_start_on_or_after": FUTURE_BLIND_START_ON_OR_AFTER.isoformat(),
        "future_blind_rows_permitted": 0,
        "provider_calls_permitted": 0,
        "broker_reads_permitted": 0,
        "broker_writes_permitted": 0,
        "paper_authority": False,
        "live_authority": False,
        "broad_minute_materialization_authority": False,
        "strategy_promotion_authority": False,
        "selector_promotion_authority": False,
        "immutable_pre_read_authorization": True,
    }


def validate_development_authorization(
    document: dict[str, object],
    *,
    plan: B35DevelopmentSourcePlan,
    split_evidence: B35SplitEvidence,
) -> str:
    required = _required_binding(plan, split_evidence)
    for field, expected in required.items():
        if document.get(field) != expected:
            raise B35DevelopmentAuthorizationError(
                f"B35 DEVELOPMENT authorization {field} is not {expected!r}"
            )
    raw_time = str(document.get("authorized_at_utc") or "")
    try:
        authorized_at = datetime.fromisoformat(raw_time)
    except ValueError as exc:
        raise B35DevelopmentAuthorizationError(
            "B35 DEVELOPMENT authorization timestamp is invalid"
        ) from exc
    if authorized_at.tzinfo is None or authorized_at.utcoffset() is None:
        raise B35DevelopmentAuthorizationError(
            "B35 DEVELOPMENT authorization timestamp must be timezone-aware"
        )
    actual_id = str(document.get("authorization_id") or "")
    if len(actual_id) != 64 or actual_id != _authorization_id(document):
        raise B35DevelopmentAuthorizationError(
            "B35 DEVELOPMENT authorization is not self-hash bound"
        )
    return actual_id


def ensure_development_authorization(
    path: Path,
    *,
    plan: B35DevelopmentSourcePlan,
    split_evidence: B35SplitEvidence,
) -> dict[str, object]:
    path = path.resolve()
    if path.is_file():
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise B35DevelopmentAuthorizationError(
                f"invalid existing B35 DEVELOPMENT authorization: {path}"
            ) from exc
        if not isinstance(document, dict):
            raise B35DevelopmentAuthorizationError(
                "existing B35 DEVELOPMENT authorization is not an object"
            )
        validate_development_authorization(
            document,
            plan=plan,
            split_evidence=split_evidence,
        )
        return document

    document = {
        **_required_binding(plan, split_evidence),
        "authorized_at_utc": datetime.now(UTC).isoformat(),
    }
    document["authorization_id"] = _authorization_id(document)
    atomic_write_text(
        path,
        json.dumps(document, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )
    return document
