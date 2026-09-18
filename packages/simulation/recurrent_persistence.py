from __future__ import annotations

import hashlib
import json
import types
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from packages.core.atomic_io import atomic_write_text
from packages.simulation.recurrent_coordinator_contract import (
    RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_engine import (
    RecurrentLifecycleCoordinatorSnapshotV1,
    RecurrentLifecycleCoordinatorV1,
    recurrent_lifecycle_coordinator_snapshot_fingerprint,
)
from packages.simulation.recurrent_lifecycle_state import (
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)
from packages.simulation.recurrent_marked_state import (
    recurrent_marked_account_state_fingerprint,
)
from packages.simulation.recurrent_persistence_contract import (
    RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT,
    RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_FINGERPRINT,
)


RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_VERSION = str(
    RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT["contract_id"]
)
_MAX_CHECKPOINT_BYTES = 128 * 1024 * 1024


class RecurrentLifecyclePersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RecurrentLifecycleCheckpointV1:
    checkpoint_sha256: str
    persisted_at_utc: datetime
    checkpoint_history: tuple[str, ...]
    snapshot: RecurrentLifecycleCoordinatorSnapshotV1

    @property
    def snapshot_fingerprint(self) -> str:
        return self.snapshot.snapshot_fingerprint


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in value.items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _hash_payload(value: dict[str, Any]) -> str:
    body = {
        key: item
        for key, item in value.items()
        if key != "checkpoint_sha256"
    }
    raw = json.dumps(
        body,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _parse_datetime(value: object, *, label: str) -> datetime:
    if not isinstance(value, str):
        raise RecurrentLifecyclePersistenceError(
            f"{label} must be an ISO timestamp"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RecurrentLifecyclePersistenceError(
            f"{label} must be an ISO timestamp"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RecurrentLifecyclePersistenceError(
            f"{label} must be timezone-aware"
        )
    return parsed


def _decode_value(expected_type: Any, value: Any) -> Any:
    if expected_type is Any:
        return value

    if expected_type is datetime:
        return _parse_datetime(value, label="snapshot datetime")

    if expected_type is type(None):
        if value is not None:
            raise RecurrentLifecyclePersistenceError(
                "snapshot null field is not null"
            )
        return None

    origin = get_origin(expected_type)
    args = get_args(expected_type)

    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        errors: list[Exception] = []
        for candidate in args:
            if candidate is type(None):
                continue
            try:
                return _decode_value(candidate, value)
            except (TypeError, ValueError, RecurrentLifecyclePersistenceError) as exc:
                errors.append(exc)
        raise RecurrentLifecyclePersistenceError(
            "snapshot union field could not be decoded"
        ) from (errors[-1] if errors else None)

    if origin is tuple:
        if not isinstance(value, list):
            raise RecurrentLifecyclePersistenceError(
                "snapshot tuple field must be a JSON array"
            )
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_value(args[0], item) for item in value)
        if len(args) != len(value):
            raise RecurrentLifecyclePersistenceError(
                "snapshot fixed tuple length mismatch"
            )
        return tuple(
            _decode_value(item_type, item)
            for item_type, item in zip(args, value, strict=True)
        )

    if origin is list:
        if not isinstance(value, list):
            raise RecurrentLifecyclePersistenceError(
                "snapshot list field must be a JSON array"
            )
        item_type = args[0] if args else Any
        return [
            _decode_value(item_type, item)
            for item in value
        ]

    if origin is dict:
        if not isinstance(value, dict):
            raise RecurrentLifecyclePersistenceError(
                "snapshot dict field must be a JSON object"
            )
        key_type = args[0] if args else Any
        item_type = args[1] if len(args) > 1 else Any
        return {
            _decode_value(key_type, key): _decode_value(item_type, item)
            for key, item in value.items()
        }

    if isinstance(expected_type, type) and issubclass(expected_type, Enum):
        try:
            return expected_type(value)
        except (TypeError, ValueError) as exc:
            raise RecurrentLifecyclePersistenceError(
                f"snapshot enum value is invalid for {expected_type.__name__}"
            ) from exc

    if isinstance(expected_type, type) and is_dataclass(expected_type):
        if not isinstance(value, dict):
            raise RecurrentLifecyclePersistenceError(
                f"snapshot {expected_type.__name__} must be a JSON object"
            )
        hints = get_type_hints(expected_type)
        field_names = {field.name for field in fields(expected_type)}
        extra = set(value) - field_names
        if extra:
            raise RecurrentLifecyclePersistenceError(
                f"snapshot {expected_type.__name__} has unexpected fields: "
                f"{sorted(extra)}"
            )
        kwargs: dict[str, Any] = {}
        for field in fields(expected_type):
            if field.name not in value:
                continue
            kwargs[field.name] = _decode_value(
                hints.get(field.name, Any),
                value[field.name],
            )
        try:
            return expected_type(**kwargs)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise RecurrentLifecyclePersistenceError(
                f"snapshot {expected_type.__name__} validation failed"
            ) from exc

    if expected_type is bool:
        if type(value) is not bool:
            raise RecurrentLifecyclePersistenceError(
                "snapshot boolean field type mismatch"
            )
        return value
    if expected_type is int:
        if type(value) is not int:
            raise RecurrentLifecyclePersistenceError(
                "snapshot integer field type mismatch"
            )
        return value
    if expected_type is float:
        if type(value) not in (int, float):
            raise RecurrentLifecyclePersistenceError(
                "snapshot float field type mismatch"
            )
        # Preserve the exact JSON numeric representation. Some accepted
        # fingerprinted states contain integer-valued numbers in fields that are
        # annotated as float. Coercing 0 -> 0.0 changes canonical JSON and therefore
        # the deterministic state fingerprint during checkpoint readback.
        return value
    if expected_type is str:
        if not isinstance(value, str):
            raise RecurrentLifecyclePersistenceError(
                "snapshot string field type mismatch"
            )
        return value

    return value


def _decode_snapshot(value: object) -> RecurrentLifecycleCoordinatorSnapshotV1:
    try:
        snapshot = _decode_value(
            RecurrentLifecycleCoordinatorSnapshotV1,
            value,
        )
    except RecurrentLifecyclePersistenceError:
        raise
    except Exception as exc:
        raise RecurrentLifecyclePersistenceError(
            "recurrent coordinator snapshot decode failed"
        ) from exc
    if not isinstance(snapshot, RecurrentLifecycleCoordinatorSnapshotV1):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint payload is not a recurrent coordinator snapshot"
        )
    return snapshot


def _checkpoint_payload(
    *,
    snapshot: RecurrentLifecycleCoordinatorSnapshotV1,
    persisted_at_utc: datetime,
    history: tuple[str, ...],
) -> dict[str, Any]:
    marked = snapshot.marked_state
    payload: dict[str, Any] = {
        "contract_version": RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_VERSION,
        "contract_fingerprint": (
            RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_FINGERPRINT
        ),
        "snapshot_contract_fingerprint": snapshot.contract_fingerprint,
        "snapshot_fingerprint": snapshot.snapshot_fingerprint,
        "account_state_fingerprint": snapshot.account.state.state_fingerprint,
        "account_ledger_fingerprint": snapshot.account.ledger.ledger_fingerprint,
        "marked_state_fingerprint": (
            None if marked is None else marked.state_fingerprint
        ),
        "revision": snapshot.revision,
        "persisted_at_utc": persisted_at_utc.isoformat(),
        "checkpoint_history": list(history),
        "snapshot": _canonicalize(snapshot),
    }
    payload["checkpoint_sha256"] = _hash_payload(payload)
    return payload


def _history_dir(path: Path) -> Path:
    return path.parent / "history"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise RecurrentLifecyclePersistenceError(
            f"could not stat recurrent checkpoint: {path}"
        ) from exc
    if size <= 0 or size > _MAX_CHECKPOINT_BYTES:
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint size is invalid"
        )
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecurrentLifecyclePersistenceError(
            f"could not read recurrent checkpoint: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint must be a JSON object"
        )
    return value


def _validate_payload(
    value: dict[str, Any],
) -> RecurrentLifecycleCheckpointV1:
    if (
        value.get("contract_version")
        != RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_VERSION
        or value.get("contract_fingerprint")
        != RECURRENT_LIFECYCLE_CHECKPOINT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint contract mismatch"
        )
    if (
        value.get("snapshot_contract_fingerprint")
        != RECURRENT_LIFECYCLE_COORDINATOR_CONTRACT_FINGERPRINT
    ):
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint coordinator contract mismatch"
        )

    checkpoint_sha = value.get("checkpoint_sha256")
    if (
        not _is_sha256(checkpoint_sha)
        or checkpoint_sha != _hash_payload(value)
    ):
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint self-hash mismatch"
        )

    history_raw = value.get("checkpoint_history")
    if (
        not isinstance(history_raw, list)
        or any(not _is_sha256(item) for item in history_raw)
        or len(history_raw) != len(set(history_raw))
    ):
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint history is invalid"
        )
    history = tuple(str(item) for item in history_raw)

    persisted_at = _parse_datetime(
        value.get("persisted_at_utc"),
        label="checkpoint persisted timestamp",
    )
    revision = value.get("revision")
    if type(revision) is not int or revision < 0:
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint revision is invalid"
        )

    snapshot = _decode_snapshot(value.get("snapshot"))
    if snapshot.revision != revision:
        raise RecurrentLifecyclePersistenceError(
            "checkpoint revision does not match snapshot revision"
        )
    if snapshot.contract_fingerprint != value.get(
        "snapshot_contract_fingerprint"
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint snapshot contract field mismatch"
        )
    if (
        snapshot.snapshot_fingerprint
        != value.get("snapshot_fingerprint")
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint snapshot fingerprint mismatch"
        )
    if (
        snapshot.account.state.state_fingerprint
        != value.get("account_state_fingerprint")
        or snapshot.account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(
            snapshot.account.state
        )
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint account-state fingerprint mismatch"
        )
    if (
        snapshot.account.ledger.ledger_fingerprint
        != value.get("account_ledger_fingerprint")
        or snapshot.account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(
            snapshot.account.ledger
        )
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint account-ledger fingerprint mismatch"
        )
    marked = snapshot.marked_state
    marked_fp = None if marked is None else marked.state_fingerprint
    if marked_fp != value.get("marked_state_fingerprint"):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint marked-state fingerprint field mismatch"
        )
    if (
        marked is not None
        and marked.state_fingerprint
        != recurrent_marked_account_state_fingerprint(marked)
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint marked-state fingerprint mismatch"
        )
    if snapshot.revision < len(snapshot.account.ledger.events):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint revision cannot trail recurrent ledger length"
        )

    return RecurrentLifecycleCheckpointV1(
        checkpoint_sha256=str(checkpoint_sha),
        persisted_at_utc=persisted_at,
        checkpoint_history=history,
        snapshot=snapshot,
    )


def _validate_transition(
    previous: RecurrentLifecycleCheckpointV1,
    current: RecurrentLifecycleCheckpointV1,
) -> None:
    if (
        previous.snapshot.account.state.bootstrap_state_fingerprint
        != current.snapshot.account.state.bootstrap_state_fingerprint
        or previous.snapshot.account.state.bootstrap_ledger_fingerprint
        != current.snapshot.account.state.bootstrap_ledger_fingerprint
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint cannot change recurrent bootstrap lineage"
        )

    if current.snapshot.revision < previous.snapshot.revision:
        raise RecurrentLifecyclePersistenceError(
            "checkpoint revision cannot move backward"
        )
    if current.snapshot.revision == previous.snapshot.revision:
        if (
            current.snapshot.snapshot_fingerprint
            != previous.snapshot.snapshot_fingerprint
        ):
            raise RecurrentLifecyclePersistenceError(
                "same recurrent revision cannot contain a different snapshot"
            )
        return

    previous_events = previous.snapshot.account.ledger.events
    current_events = current.snapshot.account.ledger.events
    if len(current_events) < len(previous_events):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint recurrent ledger cannot shrink"
        )
    if current_events[: len(previous_events)] != previous_events:
        raise RecurrentLifecyclePersistenceError(
            "checkpoint recurrent ledger history changed"
        )
    if (
        len(current_events) == len(previous_events)
        and current.snapshot.account != previous.snapshot.account
    ):
        raise RecurrentLifecyclePersistenceError(
            "checkpoint changed account state without a recurrent ledger event"
        )


def read_recurrent_lifecycle_checkpoint(
    path: Path,
) -> RecurrentLifecycleCheckpointV1:
    path = Path(path)
    current = _validate_payload(_read_json(path))
    previous: RecurrentLifecycleCheckpointV1 | None = None

    for index, digest in enumerate(current.checkpoint_history):
        history_path = _history_dir(path) / f"{digest}.json"
        historical = _validate_payload(_read_json(history_path))
        if historical.checkpoint_sha256 != digest:
            raise RecurrentLifecyclePersistenceError(
                "checkpoint history filename/hash mismatch"
            )
        if historical.checkpoint_history != current.checkpoint_history[:index]:
            raise RecurrentLifecyclePersistenceError(
                "checkpoint history chain is inconsistent"
            )
        if previous is not None:
            _validate_transition(previous, historical)
        previous = historical

    if previous is not None:
        _validate_transition(previous, current)
    return current


def write_recurrent_lifecycle_checkpoint(
    path: Path,
    snapshot: RecurrentLifecycleCoordinatorSnapshotV1,
    *,
    expected_previous_checkpoint_sha256: str | None = None,
    persisted_at_utc: datetime | None = None,
) -> RecurrentLifecycleCheckpointV1:
    path = Path(path)
    now = persisted_at_utc or datetime.now(UTC)
    if now.tzinfo is None or now.utcoffset() is None:
        raise RecurrentLifecyclePersistenceError(
            "checkpoint persisted timestamp must be timezone-aware"
        )

    previous: RecurrentLifecycleCheckpointV1 | None = None
    if path.exists():
        previous = read_recurrent_lifecycle_checkpoint(path)
    elif any(_history_dir(path).glob("*.json")):
        raise RecurrentLifecyclePersistenceError(
            "current recurrent checkpoint is missing while preserved history exists"
        )

    if expected_previous_checkpoint_sha256 is not None:
        if previous is None:
            raise RecurrentLifecyclePersistenceError(
                "expected previous checkpoint but none exists"
            )
        if (
            previous.checkpoint_sha256
            != expected_previous_checkpoint_sha256
        ):
            raise RecurrentLifecyclePersistenceError(
                "recurrent checkpoint changed since caller read it"
            )

    if (
        previous is not None
        and previous.snapshot.snapshot_fingerprint
        == snapshot.snapshot_fingerprint
        and previous.snapshot.revision == snapshot.revision
    ):
        return previous

    history = (
        ()
        if previous is None
        else (
            *previous.checkpoint_history,
            previous.checkpoint_sha256,
        )
    )
    payload = _checkpoint_payload(
        snapshot=snapshot,
        persisted_at_utc=now,
        history=history,
    )
    candidate = _validate_payload(payload)

    if previous is not None:
        _validate_transition(previous, candidate)
        history_path = (
            _history_dir(path)
            / f"{previous.checkpoint_sha256}.json"
        )
        if history_path.exists():
            existing = _validate_payload(_read_json(history_path))
            if existing != previous:
                raise RecurrentLifecyclePersistenceError(
                    "preserved recurrent checkpoint history changed"
                )
        else:
            atomic_write_text(
                history_path,
                json.dumps(
                    _checkpoint_payload(
                        snapshot=previous.snapshot,
                        persisted_at_utc=previous.persisted_at_utc,
                        history=previous.checkpoint_history,
                    ),
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                fsync=True,
            )

    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        fsync=True,
    )
    verified = read_recurrent_lifecycle_checkpoint(path)
    if verified.checkpoint_sha256 != candidate.checkpoint_sha256:
        raise RecurrentLifecyclePersistenceError(
            "recurrent checkpoint readback verification failed"
        )
    return verified


def restore_recurrent_lifecycle_coordinator(
    path: Path,
) -> RecurrentLifecycleCoordinatorV1:
    checkpoint = read_recurrent_lifecycle_checkpoint(path)
    return RecurrentLifecycleCoordinatorV1.from_snapshot(
        checkpoint.snapshot
    )
