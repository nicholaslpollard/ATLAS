from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentScopeError,
    B35DevelopmentSourceError,
    B35DevelopmentUnitBinding,
)


def _binding(path: Path, *, year: int = 2026, month: int = 4, sha: str | None = None) -> B35DevelopmentUnitBinding:
    return B35DevelopmentUnitBinding(
        unit_id=f"unit-{year}-{month}",
        year=year,
        month=month,
        symbols=("TEST",),
        canonical_path=path,
        canonical_sha256=sha or "0" * 64,
        checkpoint_path=path.with_suffix(".json"),
    )


def test_scope_rejects_consumed_master_and_future_blind() -> None:
    with pytest.raises(B35DevelopmentScopeError, match="cannot pass 2026-04-30"):
        B35DevelopmentMinuteSource.validate_scope(date(2026, 4, 1), date(2026, 5, 12))
    with pytest.raises(B35DevelopmentScopeError, match="cannot pass 2026-04-30"):
        B35DevelopmentMinuteSource.validate_scope(date(2026, 9, 8), date(2026, 9, 8))


def test_verify_unit_refuses_may_before_touching_file(tmp_path: Path) -> None:
    missing = tmp_path / "must-not-open.parquet"
    with pytest.raises(B35DevelopmentSourceError, match="in or after May 2026"):
        B35DevelopmentMinuteSource.verify_unit(
            _binding(missing, year=2026, month=5)
        )
    assert not missing.exists()


def test_verify_unit_accepts_exact_hash(tmp_path: Path) -> None:
    path = tmp_path / "unit.parquet"
    path.write_bytes(b"immutable canonical evidence")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    assert B35DevelopmentMinuteSource.verify_unit(_binding(path, sha=sha)) == sha


def test_verify_unit_rejects_hash_drift(tmp_path: Path) -> None:
    path = tmp_path / "unit.parquet"
    path.write_bytes(b"drifted")
    with pytest.raises(B35DevelopmentSourceError, match="SHA-256 drifted"):
        B35DevelopmentMinuteSource.verify_unit(_binding(path, sha="a" * 64))
