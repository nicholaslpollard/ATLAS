from __future__ import annotations

import hashlib
import json
import math
import os
import types
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, TYPE_CHECKING, Union, get_args, get_origin, get_type_hints

from packages.core.atomic_io import atomic_write_text
from packages.simulation.recurrent_lifecycle_contract import (
    RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT,
)
from packages.simulation.recurrent_lifecycle_state import (
    RecurrentLifecycleAccountV1,
    recurrent_lifecycle_account_state_fingerprint,
    recurrent_lifecycle_ledger_fingerprint,
)
from packages.simulation.recurrent_runtime_store_contract import (
    RECURRENT_RUNTIME_STORE_CONTRACT,
    RECURRENT_RUNTIME_STORE_CONTRACT_FINGERPRINT,
)

if TYPE_CHECKING:
    from packages.core.settings import AtlasSettings


RECURRENT_RUNTIME_STORE_CONTRACT_VERSION = str(
    RECURRENT_RUNTIME_STORE_CONTRACT["contract_id"]
)
_TOLERANCE = 1e-9


class RecurrentRuntimeStoreError(RuntimeError):
    pass


class RecurrentRuntimeStoreConflict(RecurrentRuntimeStoreError):
    pass


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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        _canonicalize(value),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _fingerprint_payload(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _require_fingerprint(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise RecurrentRuntimeStoreError(
            f"{label} must be a SHA-256 fingerprint"
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise RecurrentRuntimeStoreError(
            f"{label} must be a SHA-256 fingerprint"
        ) from exc


def _require_aware(value: datetime, *, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise RecurrentRuntimeStoreError(
            f"{label} must be timezone-aware"
        )


def _decode_value(annotation: Any, value: Any) -> Any:
    if annotation is Any:
        return value

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in (Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        failures: list[Exception] = []
        for item_type in args:
            if item_type is type(None):
                continue
            try:
                return _decode_value(item_type, value)
            except (TypeError, ValueError, RecurrentRuntimeStoreError) as exc:
                failures.append(exc)
        raise RecurrentRuntimeStoreError(
            f"cannot decode union value for {annotation!r}"
        ) from (failures[-1] if failures else None)

    if origin is tuple:
        if not isinstance(value, list):
            raise RecurrentRuntimeStoreError(
                f"expected JSON array for {annotation!r}"
            )
        if len(args) == 2 and args[1] is Ellipsis:
            return tuple(_decode_value(args[0], item) for item in value)
        if len(args) != len(value):
            raise RecurrentRuntimeStoreError(
                f"tuple length mismatch for {annotation!r}"
            )
        return tuple(
            _decode_value(item_type, item)
            for item_type, item in zip(args, value, strict=True)
        )

    if origin is list:
        if not isinstance(value, list):
            raise RecurrentRuntimeStoreError(
                f"expected JSON array for {annotation!r}"
            )
        item_type = args[0] if args else Any
        return [_decode_value(item_type, item) for item in value]

    if origin is dict:
        if not isinstance(value, dict):
            raise RecurrentRuntimeStoreError(
                f"expected JSON object for {annotation!r}"
            )
        key_type = args[0] if args else Any
        item_type = args[1] if len(args) > 1 else Any
        return {
            _decode_value(key_type, key): _decode_value(item_type, item)
            for key, item in value.items()
        }

    if annotation is datetime:
        if not isinstance(value, str):
            raise RecurrentRuntimeStoreError(
                "datetime payload must be an ISO-8601 string"
            )
        try:
            decoded = datetime.fromisoformat(value)
        except ValueError as exc:
            raise RecurrentRuntimeStoreError(
                "invalid ISO-8601 datetime payload"
            ) from exc
        _require_aware(decoded, label="decoded runtime datetime")
        return decoded

    if (
        isinstance(annotation, type)
        and issubclass(annotation, Enum)
    ):
        try:
            return annotation(value)
        except (TypeError, ValueError) as exc:
            raise RecurrentRuntimeStoreError(
                f"invalid enum value for {annotation.__name__}"
            ) from exc

    if isinstance(annotation, type) and is_dataclass(annotation):
        if not isinstance(value, dict):
            raise RecurrentRuntimeStoreError(
                f"expected JSON object for {annotation.__name__}"
            )
        hints = get_type_hints(annotation)
        expected = {field.name for field in fields(annotation)}
        supplied = set(value)
        if supplied != expected:
            missing = sorted(expected - supplied)
            extra = sorted(supplied - expected)
            raise RecurrentRuntimeStoreError(
                f"{annotation.__name__} field mismatch; "
                f"missing={missing}, extra={extra}"
            )
        kwargs = {
            field.name: _decode_value(
                hints.get(field.name, Any),
                value[field.name],
            )
            for field in fields(annotation)
        }
        try:
            return annotation(**kwargs)
        except Exception as exc:
            raise RecurrentRuntimeStoreError(
                f"{annotation.__name__} validation failed during restore"
            ) from exc

    if annotation is bool:
        if not isinstance(value, bool):
            raise RecurrentRuntimeStoreError("expected boolean payload")
        return value
    if annotation is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise RecurrentRuntimeStoreError("expected integer payload")
        return value
    if annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RecurrentRuntimeStoreError("expected numeric payload")
        converted = float(value)
        if not math.isfinite(converted):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot numeric payload must be finite"
            )
        return converted
    if annotation is str:
        if not isinstance(value, str):
            raise RecurrentRuntimeStoreError("expected string payload")
        return value
    if annotation is type(None):
        if value is not None:
            raise RecurrentRuntimeStoreError("expected null payload")
        return None

    return value


def _validate_account(account: RecurrentLifecycleAccountV1) -> None:
    if (
        account.state.contract_fingerprint
        != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
    ):
        raise RecurrentRuntimeStoreError(
            "runtime store account contract fingerprint mismatch"
        )
    if (
        account.state.state_fingerprint
        != recurrent_lifecycle_account_state_fingerprint(account.state)
    ):
        raise RecurrentRuntimeStoreError(
            "runtime store account-state fingerprint mismatch"
        )
    if (
        account.ledger.ledger_fingerprint
        != recurrent_lifecycle_ledger_fingerprint(account.ledger)
    ):
        raise RecurrentRuntimeStoreError(
            "runtime store ledger fingerprint mismatch"
        )
    expected = (
        account.ledger.events[-1].after_state_fingerprint
        if account.ledger.events
        else account.ledger.initial_state_fingerprint
    )
    if expected != account.state.state_fingerprint:
        raise RecurrentRuntimeStoreError(
            "runtime store ledger does not terminate at current account state"
        )


@dataclass(frozen=True)
class RecurrentRuntimeSnapshotV1:
    contract_version: str
    contract_fingerprint: str
    account_contract_fingerprint: str
    written_at_utc: datetime
    state_fingerprint: str
    ledger_fingerprint: str
    ledger_event_count: int
    account: RecurrentLifecycleAccountV1

    provider_read_authority: bool = False
    provider_write_authority: bool = False
    broker_read_authority: bool = False
    broker_write_authority: bool = False
    order_creation_authority: bool = False
    paper_authority: bool = False
    live_authority: bool = False
    promotion_authority: bool = False
    confluence_authority: bool = False

    def __post_init__(self) -> None:
        if self.contract_version != RECURRENT_RUNTIME_STORE_CONTRACT_VERSION:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != RECURRENT_RUNTIME_STORE_CONTRACT_FINGERPRINT
        ):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot contract fingerprint mismatch"
            )
        if (
            self.account_contract_fingerprint
            != RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
        ):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot account contract fingerprint mismatch"
            )
        _require_aware(self.written_at_utc, label="runtime snapshot write timestamp")
        _require_fingerprint(self.state_fingerprint, label="runtime state fingerprint")
        _require_fingerprint(self.ledger_fingerprint, label="runtime ledger fingerprint")
        if self.ledger_event_count < 0:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot ledger-event count cannot be negative"
            )

        _validate_account(self.account)
        if self.state_fingerprint != self.account.state.state_fingerprint:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot state fingerprint does not match account"
            )
        if self.ledger_fingerprint != self.account.ledger.ledger_fingerprint:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot ledger fingerprint does not match account"
            )
        if self.ledger_event_count != len(self.account.ledger.events):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot ledger-event count does not match account"
            )
        if self.written_at_utc < self.account.state.as_of_utc:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot write timestamp cannot predate account state"
            )

        forbidden = (
            self.provider_read_authority,
            self.provider_write_authority,
            self.broker_read_authority,
            self.broker_write_authority,
            self.order_creation_authority,
            self.paper_authority,
            self.live_authority,
            self.promotion_authority,
            self.confluence_authority,
        )
        if any(forbidden):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot cannot grant external/trading authority"
            )

    @property
    def snapshot_fingerprint(self) -> str:
        return _fingerprint_payload(self)


class RecurrentRuntimeAccountStoreV1:
    """Durable single-snapshot store for the authoritative recurrent account.

    The recurrent account already contains its complete append-only event ledger and
    canonical closed-trade history. The store therefore persists one exact current
    snapshot rather than duplicating the full account for every mutation.
    """

    def __init__(
        self,
        root: Path,
        *,
        clock: Any | None = None,
    ) -> None:
        self.root = Path(root)
        self.snapshot_path = self.root / "current_account.json"
        self.lock_path = self.root / "current_account.lock"
        self._clock = clock or (lambda: datetime.now(UTC))
        self._process_lock = RLock()

    @classmethod
    def from_settings(
        cls,
        settings: AtlasSettings,
        *,
        clock: Any | None = None,
    ) -> "RecurrentRuntimeAccountStoreV1":
        derived = settings.resolved_path(settings.data.paths.derived)
        return cls(
            derived / "simulation" / "recurrent_runtime" / "v1",
            clock=clock,
        )

    @contextmanager
    def _exclusive_writer(self):
        self.root.mkdir(parents=True, exist_ok=True)
        descriptor: int | None = None
        try:
            try:
                descriptor = os.open(
                    self.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError as exc:
                raise RecurrentRuntimeStoreConflict(
                    "recurrent runtime store already has an active/stale writer lock"
                ) from exc
            payload = (
                f"pid={os.getpid()}\n"
                f"created_at_utc={datetime.now(UTC).isoformat()}\n"
            ).encode("utf-8")
            os.write(descriptor, payload)
            os.fsync(descriptor)
            yield
        finally:
            if descriptor is not None:
                os.close(descriptor)
                try:
                    self.lock_path.unlink()
                except FileNotFoundError:
                    pass

    def _decode_document(self, raw: Any) -> RecurrentRuntimeSnapshotV1:
        if not isinstance(raw, dict):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot root must be a JSON object"
            )
        expected = {"snapshot", "snapshot_fingerprint"}
        if set(raw) != expected:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot envelope fields changed"
            )
        supplied_fp = raw["snapshot_fingerprint"]
        if not isinstance(supplied_fp, str):
            raise RecurrentRuntimeStoreError(
                "runtime snapshot fingerprint must be a string"
            )
        _require_fingerprint(supplied_fp, label="runtime snapshot")
        body = raw["snapshot"]
        actual_fp = _fingerprint_payload(body)
        if supplied_fp != actual_fp:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot envelope fingerprint mismatch"
            )
        snapshot = _decode_value(RecurrentRuntimeSnapshotV1, body)
        if snapshot.snapshot_fingerprint != supplied_fp:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot decoded fingerprint mismatch"
            )
        return snapshot

    def _load_unlocked(self) -> RecurrentRuntimeSnapshotV1 | None:
        if not self.snapshot_path.exists():
            return None
        if not self.snapshot_path.is_file():
            raise RecurrentRuntimeStoreError(
                f"runtime snapshot path is not a file: {self.snapshot_path}"
            )
        try:
            raw = json.loads(self.snapshot_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecurrentRuntimeStoreError(
                "runtime snapshot is unreadable or invalid JSON"
            ) from exc
        return self._decode_document(raw)

    def load(self) -> RecurrentRuntimeSnapshotV1 | None:
        with self._process_lock:
            return self._load_unlocked()

    def persist(
        self,
        account: RecurrentLifecycleAccountV1,
        *,
        expected_prior_state_fingerprint: str | None,
    ) -> RecurrentRuntimeSnapshotV1:
        _validate_account(account)
        if expected_prior_state_fingerprint is not None:
            _require_fingerprint(
                expected_prior_state_fingerprint,
                label="expected prior recurrent state",
            )

        with self._process_lock:
            with self._exclusive_writer():
                current = self._load_unlocked()
                if current is None:
                    if expected_prior_state_fingerprint is not None:
                        raise RecurrentRuntimeStoreConflict(
                            "runtime snapshot is uninitialized but caller expected prior state"
                        )
                else:
                    if expected_prior_state_fingerprint is None:
                        raise RecurrentRuntimeStoreConflict(
                            "runtime snapshot already exists; expected prior state is required"
                        )
                    if (
                        current.state_fingerprint
                        != expected_prior_state_fingerprint
                    ):
                        raise RecurrentRuntimeStoreConflict(
                            "runtime snapshot prior-state fingerprint changed"
                        )
                    if (
                        len(account.ledger.events)
                        < current.ledger_event_count
                    ):
                        raise RecurrentRuntimeStoreError(
                            "runtime account ledger-event count cannot regress"
                        )
                    if account.state.as_of_utc < current.account.state.as_of_utc:
                        raise RecurrentRuntimeStoreError(
                            "runtime account timestamp cannot regress"
                        )
                    if (
                        len(account.ledger.events)
                        == current.ledger_event_count
                        and account.state.state_fingerprint
                        != current.state_fingerprint
                    ):
                        raise RecurrentRuntimeStoreError(
                            "same-event-count runtime write changed account state"
                        )
                    if account == current.account:
                        return current

                written_at = self._clock()
                if not isinstance(written_at, datetime):
                    raise RecurrentRuntimeStoreError(
                        "runtime store clock must return datetime"
                    )
                _require_aware(written_at, label="runtime store clock")
                written_at = written_at.astimezone(UTC)
                if written_at < account.state.as_of_utc:
                    written_at = account.state.as_of_utc

                snapshot = RecurrentRuntimeSnapshotV1(
                    contract_version=RECURRENT_RUNTIME_STORE_CONTRACT_VERSION,
                    contract_fingerprint=RECURRENT_RUNTIME_STORE_CONTRACT_FINGERPRINT,
                    account_contract_fingerprint=(
                        RECURRENT_LIFECYCLE_ACCOUNT_CONTRACT_FINGERPRINT
                    ),
                    written_at_utc=written_at,
                    state_fingerprint=account.state.state_fingerprint,
                    ledger_fingerprint=account.ledger.ledger_fingerprint,
                    ledger_event_count=len(account.ledger.events),
                    account=account,
                )
                document = {
                    "snapshot": _canonicalize(snapshot),
                    "snapshot_fingerprint": snapshot.snapshot_fingerprint,
                }
                text = (
                    json.dumps(
                        document,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    )
                    + "\n"
                )
                atomic_write_text(
                    self.snapshot_path,
                    text,
                    fsync=True,
                )
                reloaded = self._load_unlocked()
                if reloaded is None:
                    raise RecurrentRuntimeStoreError(
                        "runtime snapshot disappeared after atomic write"
                    )
                if reloaded != snapshot:
                    raise RecurrentRuntimeStoreError(
                        "runtime snapshot re-read differs after atomic write"
                    )
                return reloaded


__all__ = [
    "RECURRENT_RUNTIME_STORE_CONTRACT_FINGERPRINT",
    "RecurrentRuntimeAccountStoreV1",
    "RecurrentRuntimeSnapshotV1",
    "RecurrentRuntimeStoreConflict",
    "RecurrentRuntimeStoreError",
]
