from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

from packages.core.exceptions import DownloadError, ProviderAccessDeniedError, ProviderError
from packages.schemas.ingestion import DownloadResult, IngestionPlanItem


class AtomicDownloader:
    def __init__(
        self,
        provider,
        *,
        chunk_size: int = 4 * 1024 * 1024,
        max_attempts: int = 4,
        initial_retry_seconds: float = 1.0,
        max_retry_seconds: float = 20.0,
        sleeper=time.sleep,
    ) -> None:
        self.provider = provider
        self.chunk_size = chunk_size
        self.max_attempts = max_attempts
        self.initial_retry_seconds = initial_retry_seconds
        self.max_retry_seconds = max_retry_seconds
        self.sleeper = sleeper

    def download(self, item: IngestionPlanItem) -> DownloadResult:
        destination = Path(item.local_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor = item.descriptor
        started = time.perf_counter()
        last_error: Exception | None = None

        for attempt in range(1, self.max_attempts + 1):
            temp = destination.with_suffix(destination.suffix + f".{os.getpid()}.part")
            temp.unlink(missing_ok=True)
            digest = hashlib.sha256()
            size = 0
            try:
                with temp.open("wb") as handle:
                    for chunk in self.provider.iter_object_chunks(descriptor.remote_key, self.chunk_size):
                        if not chunk:
                            continue
                        handle.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
                    handle.flush()
                    os.fsync(handle.fileno())

                if descriptor.expected_size_bytes is not None and size != descriptor.expected_size_bytes:
                    raise DownloadError(
                        f"Size mismatch for {descriptor.remote_key}: expected {descriptor.expected_size_bytes}, got {size}"
                    )
                os.replace(temp, destination)
                return DownloadResult(
                    source_id=descriptor.source_id,
                    local_path=destination,
                    size_bytes=size,
                    sha256=digest.hexdigest(),
                    attempts=attempt,
                    elapsed_seconds=time.perf_counter() - started,
                )
            except ProviderAccessDeniedError as exc:
                temp.unlink(missing_ok=True)
                raise DownloadError(
                    f"Provider denied access to {descriptor.remote_key}; check the Massive flat-file historical entitlement for this date"
                ) from exc
            except (ProviderError, DownloadError, OSError) as exc:
                last_error = exc
                temp.unlink(missing_ok=True)
                if attempt < self.max_attempts:
                    delay = min(self.initial_retry_seconds * (2 ** (attempt - 1)), self.max_retry_seconds)
                    self.sleeper(delay)

        raise DownloadError(
            f"Download failed after {self.max_attempts} attempts for {descriptor.remote_key}: "
            f"{type(last_error).__name__ if last_error else 'unknown error'}"
        ) from last_error
