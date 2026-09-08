from __future__ import annotations

import hashlib
import json
import os
import socket
import threading
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path
from typing import Iterator

from packages.core.atomic_io import atomic_write_text
from packages.strategies.b35_conditional_evidence_contract import B35_PREOUTCOME_FINGERPRINT


B35_REPLAY_LOCK_CONTRACT = "atlas-b35-development-replay-lock-v1-exclusive-process"
B35_READ_START_CONTRACT = "atlas-b35-development-read-start-v1-immutable-audit"


class B35ReplayGuardError(RuntimeError):
    pass


_LOCAL_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[str, threading.Lock] = {}


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _local_lock(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _LOCAL_GUARD:
        return _LOCAL_LOCKS.setdefault(key, threading.Lock())


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read_lock(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


@contextmanager
def replay_execution_lock(output_root: Path, *, source_fingerprint: str) -> Iterator[None]:
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / ".b35_replay.lock"
    local = _local_lock(lock_path)
    with local:
        token = uuid.uuid4().hex
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                existing = _read_lock(lock_path)
                if (
                    existing is not None
                    and existing.get("host") == socket.gethostname()
                    and isinstance(existing.get("pid"), int)
                    and not _pid_alive(int(existing["pid"]))
                ):
                    lock_path.unlink(missing_ok=True)
                    continue
                raise B35ReplayGuardError(
                    "another B35 DEVELOPMENT replay owns the output root"
                )
            else:
                document = {
                    "contract": B35_REPLAY_LOCK_CONTRACT,
                    "status": "ACTIVE_NOT_AUTHORITY",
                    "token": token,
                    "host": socket.gethostname(),
                    "pid": os.getpid(),
                    "source_fingerprint": source_fingerprint,
                    "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
                    "started_at_utc": datetime.now(UTC).isoformat(),
                }
                payload = (json.dumps(document, sort_keys=True) + "\n").encode("utf-8")
                try:
                    os.write(fd, payload)
                    os.fsync(fd)
                finally:
                    os.close(fd)
                break
        try:
            yield
        finally:
            existing = _read_lock(lock_path)
            if existing is not None and existing.get("token") == token:
                lock_path.unlink(missing_ok=True)


def serialized_replay(method):
    @wraps(method)
    def wrapper(self, plan, *, output_root: Path, authorization: dict[str, object]):
        with replay_execution_lock(
            Path(output_root), source_fingerprint=str(plan.source_fingerprint)
        ):
            return method(
                self, plan, output_root=output_root, authorization=authorization
            )

    return wrapper


def _validate_marker(
    document: dict[str, object],
    *,
    source_fingerprint: str,
    split_evidence_fingerprint: str,
    authorization_id: str,
) -> str:
    required = {
        "contract": B35_READ_START_CONTRACT,
        "status": "DEVELOPMENT_OUTCOME_READ_STARTED",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "source_fingerprint": source_fingerprint,
        "split_evidence_fingerprint": split_evidence_fingerprint,
        "authorization_id": authorization_id,
        "consumed_master_rows_permitted": 0,
        "future_blind_rows_permitted": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
    }
    for field, expected in required.items():
        if document.get(field) != expected:
            raise B35ReplayGuardError(f"B35 read-start marker {field} drifted")
    marker_id = str(document.get("marker_id") or "")
    actual = _stable_hash({k: v for k, v in document.items() if k != "marker_id"})
    if marker_id != actual:
        raise B35ReplayGuardError("B35 read-start marker is not self-hash bound")
    return marker_id


def ensure_read_start_marker(
    output_root: Path,
    *,
    source_fingerprint: str,
    split_evidence_fingerprint: str,
    authorization_id: str,
) -> dict[str, object]:
    path = Path(output_root).resolve() / "outcome_read_start.json"
    if path.is_file():
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise B35ReplayGuardError("B35 read-start marker is not an object")
        _validate_marker(
            value,
            source_fingerprint=source_fingerprint,
            split_evidence_fingerprint=split_evidence_fingerprint,
            authorization_id=authorization_id,
        )
        return value
    document: dict[str, object] = {
        "contract": B35_READ_START_CONTRACT,
        "status": "DEVELOPMENT_OUTCOME_READ_STARTED",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "source_fingerprint": source_fingerprint,
        "split_evidence_fingerprint": split_evidence_fingerprint,
        "authorization_id": authorization_id,
        "consumed_master_rows_permitted": 0,
        "future_blind_rows_permitted": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
    }
    document["marker_id"] = _stable_hash(document)
    atomic_write_text(
        path, json.dumps(document, indent=2, sort_keys=True) + "\n", fsync=True
    )
    _validate_marker(
        document,
        source_fingerprint=source_fingerprint,
        split_evidence_fingerprint=split_evidence_fingerprint,
        authorization_id=authorization_id,
    )
    return document
