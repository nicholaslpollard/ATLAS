from __future__ import annotations

import hashlib
import json
from collections import deque
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

from packages.backtesting.reference_portfolio_policy import (
    REFERENCE_PORTFOLIO_BROKER_WRITES,
    REFERENCE_PORTFOLIO_LIVE_WRITES,
    REFERENCE_PORTFOLIO_PAPER_SUBMITS,
    REFERENCE_PORTFOLIO_PROVIDER_WRITES,
    reference_portfolio_policy_fingerprint,
)
from packages.core.settings import AtlasSettings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.schemas.reference_portfolio import (
    REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION,
    ReferencePortfolioDecision,
    ReferencePortfolioEquityPoint,
    ReferencePortfolioPositionOutcome,
    ReferenceSimulatedOrderEvent,
)


REFERENCE_REPLAY_READ_MODEL_CONTRACT_VERSION = (
    "reference-replay-read-model-v2-hash-bound-operator-drilldown-read-only"
)
_MAX_SUMMARY_BYTES = 2 * 1024 * 1024
_MAX_JSONL_BYTES = 32 * 1024 * 1024
_RECENT_DECISION_LIMIT = 50
_RECENT_ORDER_LIMIT = 50
_RECENT_OUTCOME_LIMIT = 25
_EQUITY_TAIL_LIMIT = 120
_EXPECTED_ARTIFACTS = 4
_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _base_payload(status: str) -> dict[str, object]:
    return {
        "contract_version": REFERENCE_REPLAY_READ_MODEL_CONTRACT_VERSION,
        "status": status,
        "portfolio_policy_fingerprint": reference_portfolio_policy_fingerprint(),
        "replay_scope": "RESEARCH_ACCOUNT_REPLAY_NOT_QUALIFYING_HISTORICAL_OR_PAPER",
        "authority": {
            "authority_promotion": False,
            "qualifying_historical": False,
            "operational_paper": False,
            "qualifying_paper": False,
            "live": False,
            "provider_writes": REFERENCE_PORTFOLIO_PROVIDER_WRITES,
            "broker_writes": REFERENCE_PORTFOLIO_BROKER_WRITES,
            "paper_submits": REFERENCE_PORTFOLIO_PAPER_SUBMITS,
            "live_writes": REFERENCE_PORTFOLIO_LIVE_WRITES,
        },
        "artifact_integrity": {
            "expected_artifacts": _EXPECTED_ARTIFACTS,
            "verified_artifacts": 0,
            "all_sha256_verified": False,
        },
    }


def _read_json(path: Path, maximum_bytes: int) -> dict[str, Any]:
    size = path.stat().st_size
    if size <= 0 or size > maximum_bytes:
        raise ValueError("artifact size is outside the read-model boundary")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact root must be an object")
    return payload


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bound_artifact(
    summary_path: Path,
    summary: dict[str, Any],
    metadata_field: str,
    filename: str,
) -> Path:
    candidate = summary_path.with_name(filename).resolve()
    metadata = summary.get(metadata_field)
    if not isinstance(metadata, dict):
        raise ValueError(f"missing artifact binding: {metadata_field}")
    recorded_path = metadata.get("path")
    recorded_sha = metadata.get("sha256")
    if not isinstance(recorded_path, str) or Path(recorded_path).resolve() != candidate:
        raise ValueError(f"artifact path binding failed: {metadata_field}")
    if (
        not isinstance(recorded_sha, str)
        or len(recorded_sha) != 64
        or any(character not in "0123456789abcdef" for character in recorded_sha)
    ):
        raise ValueError(f"artifact SHA-256 binding is invalid: {metadata_field}")
    if not candidate.is_file() or _sha256_file(candidate) != recorded_sha:
        raise ValueError(f"artifact SHA-256 mismatch: {metadata_field}")
    return candidate


def _read_jsonl_tail(
    path: Path,
    limit: int,
    model: type[_ModelT],
) -> list[dict[str, Any]]:
    size = path.stat().st_size
    if size < 0 or size > _MAX_JSONL_BYTES:
        raise ValueError("JSONL artifact exceeds the read-model boundary")
    rows: deque[dict[str, Any]] = deque(maxlen=limit)
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict):
                raise ValueError("JSONL row must be an object")
            rows.append(model.model_validate(item).model_dump(mode="json"))
    return list(rows)


def _empty_operator_rows(payload: dict[str, object]) -> None:
    payload["recent_portfolio_decisions"] = []
    payload["recent_simulated_orders"] = []
    payload["recent_position_outcomes"] = []
    payload["equity_curve_tail"] = []


def reference_replay_read_model(settings: AtlasSettings) -> dict[str, object]:
    legacy_derived = settings.resolved_path(settings.data.paths.derived).resolve()
    v2_derived = V2Layout.beneath(
        (settings.project_root / "data").resolve()
    ).derived.resolve()
    v2_root = v2_derived / "strategy_lab" / "a33_b33_reference" / "development"
    legacy_root = (
        legacy_derived / "strategy_lab" / "a33_b33_reference" / "development"
    )
    v2_summaries = (
        sorted(v2_root.glob("*/portfolio_run_summary.json"))
        if v2_root.is_dir()
        else []
    )
    legacy_summaries = (
        sorted(legacy_root.glob("*/portfolio_run_summary.json"))
        if legacy_root.is_dir()
        else []
    )
    if v2_summaries:
        summaries = v2_summaries
        derived = v2_derived
        data_source = "v2"
    else:
        summaries = legacy_summaries
        derived = legacy_derived
        data_source = "legacy"
    if not summaries:
        payload = _base_payload("NOT_RUN")
        payload["message"] = (
            "No hash-verified V2 or retained legacy account replay exists yet. Run "
            "source validation, then the frozen DEVELOPMENT command on the data machine."
        )
        payload["data_source"] = None
        payload["summary"] = None
        _empty_operator_rows(payload)
        return payload

    summary_path = summaries[-1].resolve()
    try:
        if not summary_path.is_relative_to(derived):
            raise ValueError("summary escaped the derived-data root")
        summary = _read_json(summary_path, _MAX_SUMMARY_BYTES)
        if summary.get("contract_version") != REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION:
            raise ValueError("portfolio replay contract version mismatch")
        if summary.get("portfolio_policy_fingerprint") != reference_portfolio_policy_fingerprint():
            raise ValueError("portfolio policy fingerprint mismatch")
        for field in (
            "protected_master_return_rows_read",
            "provider_writes",
            "broker_writes",
            "paper_submits",
            "live_writes",
        ):
            if summary.get(field) != 0:
                raise ValueError(f"portfolio replay authority boundary failed: {field}")
        decisions_path = _bound_artifact(
            summary_path,
            summary,
            "decision_records",
            "portfolio_decisions.jsonl",
        )
        orders_path = _bound_artifact(
            summary_path,
            summary,
            "simulated_order_records",
            "portfolio_simulated_orders.jsonl",
        )
        outcomes_path = _bound_artifact(
            summary_path,
            summary,
            "position_outcome_records",
            "portfolio_position_outcomes.jsonl",
        )
        equity_path = _bound_artifact(
            summary_path,
            summary,
            "equity_curve_records",
            "portfolio_equity_curve.jsonl",
        )
        decisions = _read_jsonl_tail(
            decisions_path,
            _RECENT_DECISION_LIMIT,
            ReferencePortfolioDecision,
        )
        orders = _read_jsonl_tail(
            orders_path,
            _RECENT_ORDER_LIMIT,
            ReferenceSimulatedOrderEvent,
        )
        recent = _read_jsonl_tail(
            outcomes_path,
            _RECENT_OUTCOME_LIMIT,
            ReferencePortfolioPositionOutcome,
        )
        equity_tail = _read_jsonl_tail(
            equity_path,
            _EQUITY_TAIL_LIMIT,
            ReferencePortfolioEquityPoint,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        payload = _base_payload("INVALID")
        payload["message"] = (
            f"Latest {data_source} portfolio replay artifacts failed closed validation."
        )
        payload["data_source"] = data_source
        payload["summary"] = None
        _empty_operator_rows(payload)
        return payload

    payload = _base_payload("AVAILABLE")
    payload["message"] = "Latest frozen DEVELOPMENT account replay is available read-only."
    payload["data_source"] = data_source
    payload["summary"] = summary
    payload["artifact_integrity"] = {
        "expected_artifacts": _EXPECTED_ARTIFACTS,
        "verified_artifacts": _EXPECTED_ARTIFACTS,
        "all_sha256_verified": True,
    }
    payload["recent_portfolio_decisions"] = decisions
    payload["recent_simulated_orders"] = orders
    payload["recent_position_outcomes"] = recent
    payload["equity_curve_tail"] = equity_tail
    return payload
