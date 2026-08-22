from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from packages.core.settings import load_settings
from packages.regimes.historical_backfill_regime_handoff import (
    CURRENT_KEYS,
    HISTORY_KEYS,
    GATE10_REGIME_HANDOFF_CONTRACT_VERSION,
    Gate10RegimeHandoffError,
    HistoricalBackfillRegimeHandoff,
    classify_current_file_state,
    classify_history_file_state,
    gate10c_handoff_source_fingerprint,
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_gate10c_handoff_contract_and_artifact_sets_are_locked() -> None:
    assert GATE10_REGIME_HANDOFF_CONTRACT_VERSION == (
        "historical-backfill-regime-handoff-v1-journaled-atomic-files-rollback"
    )
    assert CURRENT_KEYS == (
        "market_sector_snapshot",
        "market_sector_manifest",
        "ticker_snapshot",
        "ticker_manifest",
    )
    assert HISTORY_KEYS == ("market_raw", "market_effective", "sector_raw", "sector_effective")


def test_gate10c_current_file_state_machine_is_fail_closed() -> None:
    old = "old"
    new = "new"
    assert classify_current_file_state(
        live_sha256=old, old_sha256=old, new_sha256=new, rollback_sha256=None
    ) == "OLD_LIVE_NO_ROLLBACK"
    assert classify_current_file_state(
        live_sha256=old, old_sha256=old, new_sha256=new, rollback_sha256=old
    ) == "OLD_LIVE_ROLLBACK_READY"
    assert classify_current_file_state(
        live_sha256=new, old_sha256=old, new_sha256=new, rollback_sha256=old
    ) == "NEW_LIVE_ROLLBACK_READY"
    assert classify_current_file_state(
        live_sha256="other", old_sha256=old, new_sha256=new, rollback_sha256=old
    ) == "INVALID"
    assert classify_current_file_state(
        live_sha256=new, old_sha256=old, new_sha256=new, rollback_sha256=None
    ) == "INVALID"


def test_gate10c_history_file_state_machine_is_fail_closed() -> None:
    assert classify_history_file_state(live_sha256=None, expected_sha256="expected") == "ABSENT"
    assert (
        classify_history_file_state(live_sha256="expected", expected_sha256="expected")
        == "PUBLISHED_EXACT"
    )
    assert classify_history_file_state(live_sha256="other", expected_sha256="expected") == "INVALID"


def test_gate10c_handoff_fingerprint_binds_parent_and_artifact_evidence() -> None:
    values = {
        "stage_source_fingerprint": "stage",
        "stage_report_sha256": "stage-report",
        "stage_validation_sha256": "stage-validation",
        "preflight_source_fingerprint": "preflight",
        "rollback_baseline": {"a": {"sha256": "old"}},
        "staged_artifacts": {"a": {"sha256": "new"}},
    }
    baseline = gate10c_handoff_source_fingerprint(**values)
    assert len(baseline) == 64
    for key in (
        "stage_source_fingerprint",
        "stage_report_sha256",
        "stage_validation_sha256",
        "preflight_source_fingerprint",
    ):
        changed = dict(values)
        changed[key] = f"changed-{key}"
        assert gate10c_handoff_source_fingerprint(**changed) != baseline
    changed = dict(values)
    changed["rollback_baseline"] = {"a": {"sha256": "different"}}
    assert gate10c_handoff_source_fingerprint(**changed) != baseline
    changed = dict(values)
    changed["staged_artifacts"] = {"a": {"sha256": "different"}}
    assert gate10c_handoff_source_fingerprint(**changed) != baseline


def test_gate10c_atomic_copy_is_idempotent_and_hash_bound(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    target = tmp_path / "nested" / "target.bin"
    source.write_bytes(b"accepted")
    expected = _sha(b"accepted")
    HistoricalBackfillRegimeHandoff._copy_atomic_exact(source, target, expected)
    assert target.read_bytes() == b"accepted"
    HistoricalBackfillRegimeHandoff._copy_atomic_exact(source, target, expected)
    target.write_bytes(b"tampered")
    with pytest.raises(Gate10RegimeHandoffError):
        HistoricalBackfillRegimeHandoff._copy_atomic_exact(source, target, expected)


def test_gate10c_atomic_replace_keeps_target_present_and_exact(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    target = tmp_path / "target.bin"
    source.write_bytes(b"new")
    target.write_bytes(b"old")
    expected = _sha(b"new")
    HistoricalBackfillRegimeHandoff._replace_atomic_exact(source, target, expected)
    assert target.read_bytes() == b"new"
    assert _sha(target.read_bytes()) == expected


def test_gate10c_rollback_paths_are_outside_live_current_paths() -> None:
    handoff = HistoricalBackfillRegimeHandoff(load_settings())
    as_of = __import__("datetime").date(2026, 8, 14)
    live = handoff._live_paths(as_of)
    rollback = handoff._rollback_paths("0123456789abcdef")
    assert set(live) == set(rollback) == set(CURRENT_KEYS)
    for key in CURRENT_KEYS:
        assert live[key].resolve() != rollback[key].resolve()
        assert "_rollback" in rollback[key].parts
