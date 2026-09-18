from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import replace_with_retry, unique_temp_path
from packages.schemas.live_market import LiveStateSnapshot
from packages.simulation.current_market_snapshot_source_contract import (
    CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT,
    CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT,
)


CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_VERSION = str(
    CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT["contract_id"]
)
_MAX_SNAPSHOT_BYTES = 128 * 1024 * 1024


class CurrentMarketSnapshotSourceError(RuntimeError):
    pass


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _semantic_fingerprint(snapshot: LiveStateSnapshot) -> str:
    raw = json.dumps(
        snapshot.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_source_bytes(path: Path) -> bytes:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CurrentMarketSnapshotSourceError(
            f"could not stat current live market snapshot: {path}"
        ) from exc
    if size <= 0 or size > _MAX_SNAPSHOT_BYTES:
        raise CurrentMarketSnapshotSourceError(
            "current live market snapshot size is invalid"
        )
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CurrentMarketSnapshotSourceError(
            f"could not read current live market snapshot: {path}"
        ) from exc
    if len(raw) != size:
        raise CurrentMarketSnapshotSourceError(
            "current live market snapshot changed while reading"
        )
    return raw


def _decode_snapshot(raw: bytes) -> LiveStateSnapshot:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CurrentMarketSnapshotSourceError(
            "current live market snapshot is not UTF-8"
        ) from exc
    try:
        return LiveStateSnapshot.model_validate_json(text)
    except ValueError as exc:
        raise CurrentMarketSnapshotSourceError(
            "current live market snapshot failed LiveStateSnapshot validation"
        ) from exc


def _atomic_write_exact_bytes(path: Path, raw: bytes) -> None:
    path = Path(path)
    temp = unique_temp_path(path)
    try:
        with temp.open("wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    except Exception:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


@dataclass(frozen=True)
class CurrentMarketSnapshotSourceV1:
    contract_version: str
    contract_fingerprint: str
    source_id: str
    raw_sha256: str
    semantic_fingerprint: str
    generated_at_utc: datetime
    feed_mode: str
    connection_state: str
    session_segment: str
    symbol_count: int
    archive_path: Path
    snapshot: LiveStateSnapshot

    def __post_init__(self) -> None:
        if self.contract_version != CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_VERSION:
            raise CurrentMarketSnapshotSourceError(
                "current market snapshot source contract version mismatch"
            )
        if (
            self.contract_fingerprint
            != CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT
        ):
            raise CurrentMarketSnapshotSourceError(
                "current market snapshot source contract fingerprint mismatch"
            )
        for label, value in (
            ("raw", self.raw_sha256),
            ("semantic", self.semantic_fingerprint),
        ):
            if (
                len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise CurrentMarketSnapshotSourceError(
                    f"{label} fingerprint must be SHA-256"
                )
        expected_id = f"live-market-state:{self.raw_sha256}"
        if self.source_id != expected_id:
            raise CurrentMarketSnapshotSourceError(
                "current market snapshot source id mismatch"
            )
        if self.semantic_fingerprint != _semantic_fingerprint(self.snapshot):
            raise CurrentMarketSnapshotSourceError(
                "current market snapshot semantic fingerprint mismatch"
            )
        if self.generated_at_utc != self.snapshot.generated_at_utc:
            raise CurrentMarketSnapshotSourceError(
                "snapshot generated timestamp metadata mismatch"
            )
        if self.feed_mode != self.snapshot.feed_mode.value:
            raise CurrentMarketSnapshotSourceError(
                "snapshot feed-mode metadata mismatch"
            )
        if self.connection_state != self.snapshot.connection_state.value:
            raise CurrentMarketSnapshotSourceError(
                "snapshot connection-state metadata mismatch"
            )
        if self.session_segment != self.snapshot.session.session_segment.value:
            raise CurrentMarketSnapshotSourceError(
                "snapshot session metadata mismatch"
            )
        if self.symbol_count != self.snapshot.symbol_count:
            raise CurrentMarketSnapshotSourceError(
                "snapshot symbol-count metadata mismatch"
            )

    @property
    def evidence_source_id(self) -> str:
        return self.source_id

    @property
    def evidence_source_fingerprint(self) -> str:
        return self.raw_sha256


def current_market_snapshot_archive_root(
    recurrent_checkpoint_path: Path,
) -> Path:
    return (
        Path(recurrent_checkpoint_path).parent
        / "evidence"
        / "market_state"
    )


def current_market_snapshot_archive_path(
    recurrent_checkpoint_path: Path,
    raw_sha256: str,
) -> Path:
    if (
        len(raw_sha256) != 64
        or any(character not in "0123456789abcdef" for character in raw_sha256)
    ):
        raise CurrentMarketSnapshotSourceError(
            "archive raw fingerprint must be SHA-256"
        )
    return (
        current_market_snapshot_archive_root(recurrent_checkpoint_path)
        / f"{raw_sha256}.json"
    )


def _build_source(
    *,
    raw: bytes,
    archive_path: Path,
) -> CurrentMarketSnapshotSourceV1:
    snapshot = _decode_snapshot(raw)
    raw_sha = _sha256_bytes(raw)
    if Path(archive_path).name != f"{raw_sha}.json":
        raise CurrentMarketSnapshotSourceError(
            "archive path does not match raw snapshot SHA-256"
        )
    return CurrentMarketSnapshotSourceV1(
        contract_version=CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_VERSION,
        contract_fingerprint=CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT,
        source_id=f"live-market-state:{raw_sha}",
        raw_sha256=raw_sha,
        semantic_fingerprint=_semantic_fingerprint(snapshot),
        generated_at_utc=snapshot.generated_at_utc,
        feed_mode=snapshot.feed_mode.value,
        connection_state=snapshot.connection_state.value,
        session_segment=snapshot.session.session_segment.value,
        symbol_count=snapshot.symbol_count,
        archive_path=Path(archive_path),
        snapshot=snapshot,
    )


def capture_current_market_snapshot_source_v1(
    *,
    current_snapshot_path: Path,
    recurrent_checkpoint_path: Path,
) -> CurrentMarketSnapshotSourceV1:
    raw = _read_source_bytes(current_snapshot_path)
    raw_sha = _sha256_bytes(raw)
    archive_path = current_market_snapshot_archive_path(
        recurrent_checkpoint_path,
        raw_sha,
    )

    if archive_path.exists():
        archived = _read_source_bytes(archive_path)
        if archived != raw:
            raise CurrentMarketSnapshotSourceError(
                "content-addressed market snapshot archive changed or collided"
            )
    else:
        try:
            _atomic_write_exact_bytes(archive_path, raw)
        except OSError as exc:
            raise CurrentMarketSnapshotSourceError(
                "could not persist immutable market snapshot archive"
            ) from exc

    verified = _read_source_bytes(archive_path)
    if verified != raw or _sha256_bytes(verified) != raw_sha:
        raise CurrentMarketSnapshotSourceError(
            "market snapshot archive readback verification failed"
        )
    return _build_source(raw=verified, archive_path=archive_path)


def load_current_market_snapshot_source_v1(
    *,
    recurrent_checkpoint_path: Path,
    raw_sha256: str,
) -> CurrentMarketSnapshotSourceV1:
    archive_path = current_market_snapshot_archive_path(
        recurrent_checkpoint_path,
        raw_sha256,
    )
    raw = _read_source_bytes(archive_path)
    if _sha256_bytes(raw) != raw_sha256:
        raise CurrentMarketSnapshotSourceError(
            "archived market snapshot raw SHA-256 mismatch"
        )
    return _build_source(raw=raw, archive_path=archive_path)


__all__ = [
    "CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_FINGERPRINT",
    "CURRENT_MARKET_SNAPSHOT_SOURCE_CONTRACT_VERSION",
    "CurrentMarketSnapshotSourceError",
    "CurrentMarketSnapshotSourceV1",
    "capture_current_market_snapshot_source_v1",
    "current_market_snapshot_archive_path",
    "current_market_snapshot_archive_root",
    "load_current_market_snapshot_source_v1",
]
