from __future__ import annotations

import csv
import gzip
import hashlib
from pathlib import Path

from packages.core.enums import ValidationStatus
from packages.schemas.ingestion import FileValidationResult


class FlatFileValidator:
    """Validate downloaded Massive gzip CSVs without loading them into memory."""

    def __init__(self, *, validate_gzip_crc: bool = True, count_rows: bool = False) -> None:
        self.validate_gzip_crc = validate_gzip_crc
        self.count_rows = count_rows

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(4 * 1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def validate(
        self,
        path: Path,
        *,
        expected_columns: list[str],
        expected_size_bytes: int | None = None,
        expected_sha256: str | None = None,
    ) -> FileValidationResult:
        path = Path(path)
        errors: list[str] = []
        warnings: list[str] = []
        if not path.is_file():
            return FileValidationResult(path=path, status=ValidationStatus.INVALID, size_bytes=0, errors=["file does not exist"])

        size = path.stat().st_size
        if size == 0:
            errors.append("file is empty")
        if expected_size_bytes is not None and size != expected_size_bytes:
            errors.append(f"size mismatch: expected {expected_size_bytes}, got {size}")

        sha256 = self._sha256(path)
        if expected_sha256 is not None and sha256 != expected_sha256:
            errors.append("sha256 mismatch")

        header: list[str] = []
        row_count: int | None = 0 if self.count_rows else None
        try:
            with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader, [])
                if header != expected_columns:
                    errors.append(f"unexpected CSV header: {header}")
                if self.validate_gzip_crc or self.count_rows:
                    count = 0
                    for _ in reader:
                        count += 1
                    if self.count_rows:
                        row_count = count
        except (OSError, EOFError, UnicodeDecodeError, csv.Error) as exc:
            errors.append(f"gzip/csv validation failed: {type(exc).__name__}")

        status = ValidationStatus.INVALID if errors else (ValidationStatus.WARNING if warnings else ValidationStatus.VALID)
        return FileValidationResult(
            path=path,
            status=status,
            size_bytes=size,
            sha256=sha256,
            header=header,
            row_count=row_count,
            errors=errors,
            warnings=warnings,
        )
