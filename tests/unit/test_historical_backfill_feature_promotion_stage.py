from __future__ import annotations

from datetime import date
from pathlib import Path

from packages.core.enums import Timeframe
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.historical_backfill_feature_promotion_stage import (
    gate9c_stage_source_fingerprint,
    month_end_sessions,
    production_manifest_payload,
)
from packages.features.partition_store import (
    FEATURE_PARTITION_CONTRACT_VERSION,
    FEATURE_PARTITION_SCHEMA_VERSION,
    FeaturePartitionManifest,
    feature_dependency_fingerprint,
)


def test_gate9c_stage_source_fingerprint_binds_all_parent_evidence() -> None:
    values = {
        "preflight_source_fingerprint": "preflight",
        "candidate_inventory_fingerprint": "candidate",
        "production_baseline_fingerprint": "baseline",
    }
    baseline = gate9c_stage_source_fingerprint(**values)
    assert len(baseline) == 64
    for field in values:
        changed = dict(values)
        changed[field] = f"changed-{field}"
        assert gate9c_stage_source_fingerprint(**changed) != baseline


def test_gate9c_month_end_sessions_uses_last_observed_exchange_session() -> None:
    sessions = [
        date(2021, 8, 16),
        date(2021, 8, 30),
        date(2021, 8, 31),
        date(2021, 9, 1),
        date(2021, 9, 30),
        date(2021, 10, 1),
    ]
    assert month_end_sessions(sessions) == {
        date(2021, 8, 31),
        date(2021, 9, 30),
        date(2021, 10, 1),
    }


def test_gate9c_production_manifest_uses_normal_feature_partition_contract(tmp_path: Path) -> None:
    source = tmp_path / "canonical.parquet"
    target = tmp_path / "features" / "part-000.parquet"
    payload = production_manifest_payload(
        trading_date=date(2021, 8, 16),
        source_path=source,
        source_sha256="source-sha",
        input_state_fingerprint="input-state",
        output_state_fingerprint="output-state",
        production_feature_path=target,
        feature_sha256="feature-sha",
        row_count=10,
        symbol_count=5,
        created_at_utc="2026-08-21T00:00:00+00:00",
    )
    manifest = FeaturePartitionManifest.from_dict(payload)
    manifest.validate_contract(Timeframe.DAY_1, date(2021, 8, 16))
    assert manifest.schema_version == FEATURE_PARTITION_SCHEMA_VERSION
    assert manifest.partition_contract_version == FEATURE_PARTITION_CONTRACT_VERSION
    assert manifest.feature_contract_version == CORE_FEATURE_CONTRACT_VERSION
    assert manifest.feature_registry_fingerprint == CORE_FEATURE_REGISTRY.fingerprint()
    assert manifest.feature_path == str(target.resolve())
    assert manifest.source_path == str(source.resolve())


def test_gate9c_production_manifest_dependency_is_state_bound(tmp_path: Path) -> None:
    payload = production_manifest_payload(
        trading_date=date(2021, 8, 16),
        source_path=tmp_path / "source.parquet",
        source_sha256="source-sha",
        input_state_fingerprint="input-state",
        output_state_fingerprint="output-state",
        production_feature_path=tmp_path / "target.parquet",
        feature_sha256="feature-sha",
        row_count=10,
        symbol_count=5,
        created_at_utc="2026-08-21T00:00:00+00:00",
    )
    assert payload["dependency_fingerprint"] == feature_dependency_fingerprint(
        source_sha256="source-sha",
        input_state_fingerprint="input-state",
    )
    changed = production_manifest_payload(
        trading_date=date(2021, 8, 16),
        source_path=tmp_path / "source.parquet",
        source_sha256="source-sha",
        input_state_fingerprint="different-input-state",
        output_state_fingerprint="output-state",
        production_feature_path=tmp_path / "target.parquet",
        feature_sha256="feature-sha",
        row_count=10,
        symbol_count=5,
        created_at_utc="2026-08-21T00:00:00+00:00",
    )
    assert changed["dependency_fingerprint"] != payload["dependency_fingerprint"]
