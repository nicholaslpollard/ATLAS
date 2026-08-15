from __future__ import annotations

import hashlib
from pathlib import Path

from packages.core.enums import IngestionStatus, ValidationStatus
from packages.schemas.ingestion import IngestionManifestRecord, ProviderFileDescriptor


def sha256_file(path: Path, *, chunk_size: int = 4 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def existing_file_is_complete(
    descriptor: ProviderFileDescriptor,
    local_path: Path,
    record: IngestionManifestRecord | None,
    *,
    verify_hash: bool = False,
) -> bool:
    local_path = Path(local_path)
    if record is None or not local_path.is_file():
        return False
    if record.status not in {IngestionStatus.VALIDATED, IngestionStatus.COMPLETE}:
        return False
    if record.validation_status not in {ValidationStatus.VALID, ValidationStatus.WARNING}:
        return False

    stat_size = local_path.stat().st_size
    expected = descriptor.expected_size_bytes
    if expected is not None and stat_size != expected:
        return False
    if record.size_bytes is not None and stat_size != record.size_bytes:
        return False
    if descriptor.etag and record.etag and descriptor.etag != record.etag:
        return False
    if verify_hash and record.sha256 and sha256_file(local_path) != record.sha256:
        return False
    return True
