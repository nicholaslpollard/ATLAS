from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from packages.backtesting.reference_portfolio_policy import (
    REFERENCE_PORTFOLIO_BROKER_WRITES,
    REFERENCE_PORTFOLIO_LIVE_WRITES,
    REFERENCE_PORTFOLIO_PAPER_SUBMITS,
    REFERENCE_PORTFOLIO_PROVIDER_WRITES,
    reference_portfolio_policy_fingerprint,
)
from packages.core.settings import AtlasSettings
from packages.schemas.reference_portfolio import REFERENCE_PORTFOLIO_REPLAY_CONTRACT_VERSION


REFERENCE_REPLAY_READ_MODEL_CONTRACT_VERSION = (
    "reference-replay-read-model-v1-latest-summary-recent-outcomes-read-only"
)
_MAX_SUMMARY_BYTES = 2 * 1024 * 1024
_MAX_JSONL_BYTES = 32 * 1024 * 1024
_RECENT_OUTCOME_LIMIT = 25
_EQUITY_TAIL_LIMIT = 120


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
    }


def _read_json(path: Path, maximum_bytes: int) -> dict[str, Any]:
    size = path.stat().st_size
    if size <= 0 or size > maximum_bytes:
        raise ValueError("artifact size is outside the read-model boundary")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact root must be an object")
    return payload


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    size = path.stat().st_size
    if size < 0 or size > _MAX_JSONL_BYTES:
        raise ValueError("JSONL artifact exceeds the read-model boundary")
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError("JSONL row must be an object")
        rows.append(item)
    return rows[-limit:]


def reference_replay_read_model(settings: AtlasSettings) -> dict[str, object]:
    derived = settings.resolved_path(settings.data.paths.derived).resolve()
    root = derived / "strategy_lab" / "a33_b33_reference" / "development"
    summaries = sorted(root.glob("*/portfolio_run_summary.json")) if root.is_dir() else []
    if not summaries:
        payload = _base_payload("NOT_RUN")
        payload["message"] = (
            "No trusted-lake account replay exists yet. Run source validation, then the "
            "frozen DEVELOPMENT command on the machine containing the accepted lake."
        )
        payload["summary"] = None
        payload["recent_position_outcomes"] = []
        payload["equity_curve_tail"] = []
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
        recent = _read_jsonl_tail(
            summary_path.with_name("portfolio_position_outcomes.jsonl"),
            _RECENT_OUTCOME_LIMIT,
        )
        equity_tail = _read_jsonl_tail(
            summary_path.with_name("portfolio_equity_curve.jsonl"),
            _EQUITY_TAIL_LIMIT,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        payload = _base_payload("INVALID")
        payload["message"] = "Latest portfolio replay artifacts failed closed validation."
        payload["summary"] = None
        payload["recent_position_outcomes"] = []
        payload["equity_curve_tail"] = []
        return payload

    payload = _base_payload("AVAILABLE")
    payload["message"] = "Latest frozen DEVELOPMENT account replay is available read-only."
    payload["summary"] = summary
    payload["recent_position_outcomes"] = recent
    payload["equity_curve_tail"] = equity_tail
    return payload
