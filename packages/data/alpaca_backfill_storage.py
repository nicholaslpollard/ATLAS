from __future__ import annotations

import gzip
import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.providers.alpaca import AlpacaApiPage


ALPACA_RAW_STORAGE_LAYOUT_VERSION = "alpaca-raw-store-v2-hashed-provenance-directory"
ALPACA_RAW_PROVENANCE_KEY_HEX_LENGTH = 20


@dataclass(frozen=True, slots=True)
class AlpacaRawPayloadRecord:
    category: str
    partition: str
    request_name: str
    request_url: str
    http_status: int
    sha256: str
    uncompressed_bytes: int
    compressed_bytes: int
    payload_path: str
    metadata_path: str
    captured_at_utc: str
    page_token_used: str | None
    next_page_token: str | None


class AlpacaRawPayloadStore:
    """Content-addressed immutable storage for exact Alpaca JSON response bytes.

    The final payload filename always retains the full response SHA-256. To preserve
    Windows path budget under long checkout/temp roots, category+partition provenance
    is represented in the directory layout by a deterministic 80-bit key; the full
    human-readable category and partition remain in the sidecar metadata record.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        provider_root = settings.resolved_path(settings.data.paths.provider)
        self.root = provider_root / "alpaca" / "historical_backfill" / "raw"

    @staticmethod
    def _clean_component(value: str) -> str:
        clean = str(value).strip().replace("\\", "_").replace("/", "_")
        if not clean or clean in {".", ".."}:
            raise ValueError("invalid Alpaca raw-store path component")
        return clean

    @staticmethod
    def _provenance_key(category: str, partition: str) -> str:
        payload = f"{category}\0{partition}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:ALPACA_RAW_PROVENANCE_KEY_HEX_LENGTH]

    def persist(
        self,
        page: AlpacaApiPage,
        *,
        category: str,
        partition: str,
    ) -> AlpacaRawPayloadRecord:
        category = self._clean_component(category)
        partition = self._clean_component(partition)
        digest = hashlib.sha256(page.raw_body).hexdigest()
        provenance_key = self._provenance_key(category, partition)
        directory = self.root / "v2" / provenance_key
        payload_path = directory / f"{digest}.json.gz"
        metadata_path = directory / f"{digest}.meta.json"
        compressed = gzip.compress(page.raw_body, compresslevel=6, mtime=0)

        if payload_path.exists():
            try:
                existing = gzip.decompress(payload_path.read_bytes())
            except (OSError, EOFError) as exc:
                raise RuntimeError(f"existing Alpaca raw payload is unreadable: {payload_path}") from exc
            if hashlib.sha256(existing).hexdigest() != digest:
                raise RuntimeError(f"immutable Alpaca payload hash mismatch: {payload_path}")
        else:
            payload_path.parent.mkdir(parents=True, exist_ok=True)
            temp = unique_temp_path(payload_path)
            try:
                with temp.open("wb") as handle:
                    handle.write(compressed)
                    handle.flush()
                    os.fsync(handle.fileno())
                replace_with_retry(temp, payload_path)
            except Exception:
                temp.unlink(missing_ok=True)
                raise

        captured = datetime.now(UTC).isoformat()
        record = AlpacaRawPayloadRecord(
            category=category,
            partition=partition,
            request_name=page.request_name,
            request_url=page.url,
            http_status=page.http_status,
            sha256=digest,
            uncompressed_bytes=len(page.raw_body),
            compressed_bytes=payload_path.stat().st_size,
            payload_path=str(payload_path),
            metadata_path=str(metadata_path),
            captured_at_utc=captured,
            page_token_used=page.page_token_used,
            next_page_token=page.next_page_token,
        )
        if not metadata_path.exists():
            atomic_write_text(
                metadata_path,
                json.dumps(asdict(record), indent=2, sort_keys=True) + "\n",
            )
        return record
