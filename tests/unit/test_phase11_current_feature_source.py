from __future__ import annotations

from pathlib import Path

import pytest

from packages.discovery.current_candidates import (
    CurrentCandidateMaterializationError,
    _validate_feature_source_binding,
)
from packages.features.partition_store import FeaturePartitionManifest


def _manifest(*, feature_path: Path, canonical_path: Path) -> FeaturePartitionManifest:
    return FeaturePartitionManifest(
        schema_version=1,
        partition_contract_version="feature-partition-v1-state-dependent",
        feature_contract_version="features-v1-wilder-and-explicit-warmup",
        feature_registry_fingerprint=(
            "31f9e3a72962c24039aa926a36bb769d451a25035709566912681e1f039eaf6a"
        ),
        timeframe="1d",
        trading_date="2026-08-14",
        source_path=str(canonical_path.resolve()),
        source_sha256="canonical-sha",
        input_state_fingerprint="input-state",
        output_state_fingerprint="output-state",
        dependency_fingerprint="dependency",
        feature_path=str(feature_path.resolve()),
        feature_sha256="feature-sha",
        row_count=10,
        symbol_count=10,
        created_at_utc="2026-08-14T22:00:00+00:00",
    )


def test_feature_source_binding_accepts_exact_manifest_source(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.parquet"
    canonical_path = tmp_path / "canonical.parquet"
    manifest = _manifest(feature_path=feature_path, canonical_path=canonical_path)

    _validate_feature_source_binding(
        manifest,
        feature_path=feature_path,
        feature_sha256="feature-sha",
        canonical_path=canonical_path,
        canonical_sha256="canonical-sha",
    )


def test_feature_source_binding_rejects_unbound_canonical_close(tmp_path: Path) -> None:
    feature_path = tmp_path / "features.parquet"
    canonical_path = tmp_path / "canonical.parquet"
    manifest = _manifest(feature_path=feature_path, canonical_path=canonical_path)

    with pytest.raises(CurrentCandidateMaterializationError, match="canonical source hash changed"):
        _validate_feature_source_binding(
            manifest,
            feature_path=feature_path,
            feature_sha256="feature-sha",
            canonical_path=canonical_path,
            canonical_sha256="different-canonical-sha",
        )
