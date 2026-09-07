"""Durable, history-preserving records of one frozen holdout consumption.

The current receipt is an atomic projection. Every superseded state is retained
as a content-addressed snapshot before that projection changes. A retry is another
attempt at the same frozen evaluation, never a new unused holdout.
"""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text


MASTER_HOLDOUT_CONSUMPTION_CONTRACT = "atlas-master-holdout-consumption-v2-preserved-history"
_STARTED = "CONSUMED_MATERIALIZATION_STARTED"
_REPLAY = "CONSUMED_REPLAY_STARTED"
_COMPLETE = "CONSUMED_WALK_FORWARD_COMPLETE"
_MATERIALIZATION_FAILURES = {
    "CONSUMED_MATERIALIZATION_FAILED",
    "CONSUMED_MATERIALIZATION_SCOPE_MISMATCH",
}
_STATES = {_STARTED, _REPLAY, _COMPLETE, "CONSUMED_REPLAY_FAILED"} | _MATERIALIZATION_FAILURES
_IMMUTABLE_FIELDS = (
    "contract", "authorization_id", "master_protected_start", "master_protected_end",
    "walk_forward_end", "walk_forward_daily_manifest",
    "historical_replay_not_prospective_paper", "strategy_authority_promoted",
    "paper_authority", "live_authority", "first_consumption_started_at_utc",
)
_MAX_RECEIPT_BYTES = 2 * 1024 * 1024


def _hash(value: dict[str, Any]) -> str:
    body = {key: item for key, item in value.items() if key != "receipt_sha256"}
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_hash(value: object) -> bool:
    return (
        isinstance(value, str) and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _read(path: Path) -> dict[str, Any]:
    if not 0 < path.stat().st_size <= _MAX_RECEIPT_BYTES:
        raise ValueError("holdout receipt size is invalid")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("holdout receipt must be a JSON object")
    return value


def _validate(value: dict[str, Any]) -> None:
    if (
        value.get("contract") != MASTER_HOLDOUT_CONSUMPTION_CONTRACT
        or value.get("status") not in _STATES
        or not _is_hash(value.get("authorization_id"))
        or value.get("receipt_sha256") != _hash(value)
    ):
        raise ValueError("holdout receipt contract, status, or self-hash is invalid")
    if (
        value.get("master_protected_start") != "2026-05-12"
        or value.get("master_protected_end") != "2026-08-11"
        or date.fromisoformat(str(value.get("walk_forward_end"))) < date(2026, 8, 11)
        or not isinstance(value.get("walk_forward_daily_manifest"), str)
        or not value["walk_forward_daily_manifest"]
        or value.get("historical_replay_not_prospective_paper") is not True
        or any(value.get(key) is not False for key in (
            "strategy_authority_promoted", "paper_authority", "live_authority"
        ))
    ):
        raise ValueError("holdout receipt window or authority is invalid")
    for key in ("first_consumption_started_at_utc", "latest_attempt_started_at_utc"):
        stamp = datetime.fromisoformat(str(value.get(key)))
        if stamp.tzinfo is None or stamp.utcoffset() is None:
            raise ValueError("holdout receipt timestamp must be timezone-aware")
    if type(value.get("attempt_number")) is not int or value["attempt_number"] < 1:
        raise ValueError("holdout receipt attempt number is invalid")
    rows = value.get("protected_return_rows_read")
    if rows is not None and (type(rows) is not int or rows < 1):
        raise ValueError("holdout receipt known protected-row count is invalid")
    pending = value.get("protected_rows_accounting_pending")
    if value["status"] in {_REPLAY, "CONSUMED_REPLAY_FAILED", _COMPLETE}:
        if rows is None or pending is not False:
            raise ValueError("holdout replay requires complete protected-row accounting")
    elif pending is not True:
        raise ValueError("holdout materialization must retain pending accounting")
    history = value.get("receipt_history")
    if not isinstance(history, list) or any(not _is_hash(item) for item in history):
        raise ValueError("holdout receipt history is invalid")
    if len(set(history)) != len(history):
        raise ValueError("holdout receipt history contains a cycle")


def _transition(previous: dict[str, Any], current: dict[str, Any]) -> None:
    if any(previous.get(key) != current.get(key) for key in _IMMUTABLE_FIELDS):
        raise ValueError("holdout receipt cannot change its frozen binding")
    known = previous.get("protected_return_rows_read")
    if known is not None and current.get("protected_return_rows_read") != known:
        raise ValueError("holdout receipt cannot clear or change known protected-row accounting")
    before, after = previous["status"], current["status"]
    retry = after == _STARTED and before != _COMPLETE
    allowed = (
        (before == _STARTED and after in _MATERIALIZATION_FAILURES | {_REPLAY})
        or (before == _REPLAY and after in {"CONSUMED_REPLAY_FAILED", _COMPLETE})
        or retry
    )
    expected_attempt = previous["attempt_number"] + int(retry)
    if not allowed or current["attempt_number"] != expected_attempt:
        raise ValueError("invalid holdout receipt state or attempt transition")
    if not retry and (
        current["latest_attempt_started_at_utc"] != previous["latest_attempt_started_at_utc"]
    ):
        raise ValueError("holdout receipt changed its current attempt clock")


def read_holdout_receipt(path: Path) -> dict[str, Any]:
    """Verify the current state and every preserved predecessor without market reads."""
    current = _read(path)
    _validate(current)
    history = current["receipt_history"]
    previous: dict[str, Any] | None = None
    for index, digest in enumerate(history):
        snapshot = _read(path.with_name("master_holdout_consumption_history") / f"{digest}.json")
        _validate(snapshot)
        if snapshot["receipt_sha256"] != digest or snapshot["receipt_history"] != history[:index]:
            raise ValueError("holdout receipt history chain is inconsistent")
        if previous is not None:
            _transition(previous, snapshot)
        elif snapshot["status"] != _STARTED or snapshot["attempt_number"] != 1:
            raise ValueError("holdout receipt history has no first consumption start")
        previous = snapshot
    if previous is not None:
        _transition(previous, current)
    elif current["status"] != _STARTED or current["attempt_number"] != 1:
        raise ValueError("holdout receipt has no recorded first consumption start")
    return current


def write_holdout_receipt(path: Path, value: dict[str, Any]) -> dict[str, Any]:
    """Preserve the old state before atomically writing a validated successor."""
    previous = read_holdout_receipt(path) if path.exists() else None
    updated = dict(value)
    if previous is not None:
        if value.get("receipt_sha256") != previous["receipt_sha256"]:
            raise ValueError("holdout receipt changed since this attempt read it")
        _transition(previous, updated)
        updated["receipt_history"] = [*previous["receipt_history"], previous["receipt_sha256"]]
    else:
        if updated.get("receipt_sha256") or updated.get("receipt_history"):
            raise ValueError("cannot recreate a missing holdout receipt from a later state")
        if any(path.with_name("master_holdout_consumption_history").glob("*.json")):
            raise ValueError("current holdout receipt is missing but permanent history exists")
        updated["receipt_history"] = []
    updated["receipt_sha256"] = _hash(updated)
    _validate(updated)
    if previous is None and (updated["status"] != _STARTED or updated["attempt_number"] != 1):
        raise ValueError("first holdout receipt must record materialization start")
    if previous is not None:
        snapshot_path = path.with_name("master_holdout_consumption_history") / f"{previous['receipt_sha256']}.json"
        if snapshot_path.exists():
            if _read(snapshot_path) != previous:
                raise ValueError("preserved holdout receipt snapshot changed")
        else:
            atomic_write_text(snapshot_path, json.dumps(previous, indent=2, sort_keys=True) + "\n", fsync=True)
    atomic_write_text(path, json.dumps(updated, indent=2, sort_keys=True) + "\n", fsync=True)
    return updated


def begin_holdout_consumption(
    path: Path, *, authorization_id: str, walk_forward_end: date,
    walk_forward_manifest: Path,
) -> dict[str, Any]:
    binding = {
        "contract": MASTER_HOLDOUT_CONSUMPTION_CONTRACT,
        "authorization_id": authorization_id,
        "master_protected_start": "2026-05-12",
        "master_protected_end": "2026-08-11",
        "walk_forward_end": walk_forward_end.isoformat(),
        "walk_forward_daily_manifest": str(walk_forward_manifest),
        "historical_replay_not_prospective_paper": True,
        "strategy_authority_promoted": False, "paper_authority": False, "live_authority": False,
    }
    existing = read_holdout_receipt(path) if path.exists() else {}
    if any(existing.get(key) != item for key, item in binding.items()) and existing:
        raise ValueError("existing holdout consumption binds a different source, window, or authorization")
    if existing.get("status") == _COMPLETE:
        return existing
    now = datetime.now(UTC).isoformat()
    receipt = {
        **binding, "status": _STARTED,
        "first_consumption_started_at_utc": existing.get("first_consumption_started_at_utc", now),
        "latest_attempt_started_at_utc": now,
        "attempt_number": existing.get("attempt_number", 0) + 1,
        "protected_return_rows_read": existing.get("protected_return_rows_read"),
        "protected_rows_accounting_pending": True,
    }
    if existing:
        receipt["receipt_sha256"] = existing["receipt_sha256"]
    return write_holdout_receipt(path, receipt)
