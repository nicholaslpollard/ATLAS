from __future__ import annotations

import hashlib
from pathlib import Path

from packages.regimes.historical_backfill_regime_promotion_stage import (
    HistoricalBackfillRegimePromotionStage,
    gate10c_stage_source_fingerprint,
    production_history_target_unchanged,
    staged_manifests_are_production_native,
)


def test_gate10c_stage_source_fingerprint_binds_parent_evidence() -> None:
    values = {
        "preflight_source_fingerprint": "preflight",
        "builder_source_fingerprint": "builder",
        "market_dependency": "market",
        "ticker_dependency": "ticker",
    }
    baseline = gate10c_stage_source_fingerprint(**values)
    assert len(baseline) == 64
    for field in values:
        changed = dict(values)
        changed[field] = f"changed-{field}"
        assert gate10c_stage_source_fingerprint(**changed) != baseline


def test_gate10c_stage_copy_exact_is_resumable_and_hash_guarded(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    target = tmp_path / "stage" / "target.bin"
    source.write_bytes(b"accepted")
    expected = hashlib.sha256(b"accepted").hexdigest()
    assert HistoricalBackfillRegimePromotionStage._copy_exact(source, target, expected)
    assert not HistoricalBackfillRegimePromotionStage._copy_exact(source, target, expected)
    source.write_bytes(b"changed")
    try:
        HistoricalBackfillRegimePromotionStage._copy_exact(source, target, expected)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Gate 10-C staging must reject a changed candidate source")


def test_gate10c_production_history_target_state_is_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "market_raw.parquet"
    expected = hashlib.sha256(b"accepted").hexdigest()
    assert production_history_target_unchanged(
        action="COPY_NEW", target=target, expected_sha256=expected
    )
    target.write_bytes(b"accepted")
    assert production_history_target_unchanged(
        action="REUSE_EXACT", target=target, expected_sha256=expected
    )
    assert not production_history_target_unchanged(
        action="COPY_NEW", target=target, expected_sha256=expected
    )
    assert not production_history_target_unchanged(
        action="FAIL_UNMANAGED_TARGET", target=target, expected_sha256=expected
    )


def test_gate10c_staged_manifests_reference_production_not_stage_paths(tmp_path: Path) -> None:
    live_market = tmp_path / "production" / "market" / "snapshot.json"
    live_ticker = tmp_path / "production" / "ticker" / "part-000.parquet"
    history = {
        "market_raw": tmp_path / "production" / "history" / "market_raw.parquet",
        "market_effective": tmp_path / "production" / "history" / "market_effective.parquet",
        "sector_raw": tmp_path / "production" / "history" / "sector_raw.parquet",
        "sector_effective": tmp_path / "production" / "history" / "sector_effective.parquet",
    }
    market_manifest = {
        "snapshot_path": str(live_market.resolve()),
        "history_files": {
            name: {"path": str(path.resolve()), "sha256": name}
            for name, path in history.items()
        },
    }
    ticker_manifest = {"snapshot_path": str(live_ticker.resolve())}
    assert staged_manifests_are_production_native(
        market_manifest=market_manifest,
        ticker_manifest=ticker_manifest,
        live_market_snapshot=live_market,
        live_ticker_snapshot=live_ticker,
        production_history_paths=history,
    )
    market_manifest["history_files"]["market_raw"]["path"] = str(
        (tmp_path / "stage" / "market_raw.parquet").resolve()
    )
    assert not staged_manifests_are_production_native(
        market_manifest=market_manifest,
        ticker_manifest=ticker_manifest,
        live_market_snapshot=live_market,
        live_ticker_snapshot=live_ticker,
        production_history_paths=history,
    )
