from __future__ import annotations

import inspect
from pathlib import Path

from packages.backtesting.phase25_gate6_recovery import (
    PHASE25_GATE6_RECOVERY_BINDING_CONTRACT_VERSION,
    Phase25Gate6RecoveredIndependentValidator,
    Phase25Gate6RecoveredPrerequisiteReconstruction,
)
from packages.backtesting.phase25_gate6_repair import (
    Phase25Gate6SafeDiscoveryReconstruction,
)
from packages.backtesting.phase25_prerequisite_recovery import (
    PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION,
    PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION,
    Phase25PrerequisiteRecovery,
    Phase25PrerequisiteRecoveryIndependentValidator,
    _stable_hash,
)


def test_phase25_recovery_contracts_are_explicit_and_versioned() -> None:
    assert PHASE25_PREREQUISITE_RECOVERY_CONTRACT_VERSION.startswith(
        "phase25-prerequisite-recovery-v1-"
    )
    assert PHASE25_PREREQUISITE_RECOVERY_VALIDATION_CONTRACT_VERSION.startswith(
        "phase25-prerequisite-recovery-validation-v1-"
    )
    assert PHASE25_GATE6_RECOVERY_BINDING_CONTRACT_VERSION.startswith(
        "phase25-gate6-recovery-binding-v2-"
    )


def test_phase25_recovery_provider_reads_are_default_deny_and_selective() -> None:
    signature = inspect.signature(Phase25PrerequisiteRecovery.run)
    assert signature.parameters["allow_provider_recovery"].default is False

    source = inspect.getsource(Phase25PrerequisiteRecovery.run)
    deny = source.index("if (missing or invalid) and not allow_provider_recovery:")
    client = source.index("client = _CountingMassiveRESTClient(self.settings)")
    quarantine = source.index("self._quarantine_source_pair(")
    fetch = source.index("provider.stock_snapshot(session, include_inactive=False)")
    assert deny < client
    assert quarantine < fetch
    assert "if state == \"valid\":" in source
    assert "REUSE_VALID" in source
    assert "REACQUIRE_AUTHORITATIVE" in source


def test_phase25_recovery_does_not_rebuild_global_registry_or_fake_old_events() -> None:
    source = inspect.getsource(Phase25PrerequisiteRecovery)
    assert ".rebuild_registry(" not in source
    assert '"global_registry_rebuilt": False' in source
    assert '"original_gate3_gate4_gate5_event_history_recreated": False' in source
    assert '"synthetic_reference_reconstruction_used": False' in source
    assert '"protected_strategy_evidence_reads": 0' in source
    assert '"phase26_strategy_returns_read": False' in source


def test_phase25_recovery_validator_reopens_source_lineage() -> None:
    source = inspect.getsource(Phase25PrerequisiteRecoveryIndependentValidator.run)
    assert "_validate_reference_pair_independently" in source
    assert "source_lineage_sha256" in source
    assert "recovery_report_sha256" in source
    assert "historical_event_log_not_fabricated" in source


def test_recovered_gate6_uses_safe_repair_and_clears_misleading_gate5_fields() -> None:
    assert issubclass(
        Phase25Gate6RecoveredPrerequisiteReconstruction,
        Phase25Gate6SafeDiscoveryReconstruction,
    )
    source = inspect.getsource(Phase25Gate6RecoveredPrerequisiteReconstruction.run)
    reconcile = source.index("self._reconcile_reacquired_sessions(through_date)")
    gate6 = source.index("super().run(")
    assert reconcile < gate6
    assert '"reference_prerequisite_mode": "authoritative_recovery"' in source
    assert '"gate5_report_path": None' in source
    assert '"gate5_validation_path": None' in source
    assert '"gate5_provider_page_reads": None' in source
    assert '"original_gate5_event_history_recreated": False' in source


def test_recovered_gate6_requires_exact_routed_universe_not_exact_exclusion_ledger() -> None:
    source = inspect.getsource(
        Phase25Gate6RecoveredPrerequisiteReconstruction._reconcile_one_reacquired_session
    )
    assert "rebuilt_snapshot_sha == prior_snapshot_sha" in source
    assert "rebuilt.fingerprint == prior_fingerprint" in source
    assert "rebuilt_exclusion_sha == prior_exclusion_sha" not in source
    assert "exclusion_diagnostic_drift" in source
    assert "DIAGNOSTIC_NOT_DISCOVERY_OR_GATE6_GATE7_INPUT" in source


def test_recovered_gate6_role_separates_same_named_backup_artifacts() -> None:
    backup_dir = Path("backup")
    snapshot = Path("universe/date=2021-08-16/part-000.parquet")
    exclusion = Path("universe_exclusions/date=2021-08-16/part-000.parquet")
    manifest = Path("universe/date=2021-08-16/manifest.json")
    snapshot_backup, exclusion_backup, manifest_backup = (
        Phase25Gate6RecoveredPrerequisiteReconstruction._artifact_backup_paths(
            backup_dir=backup_dir,
            snapshot=snapshot,
            exclusion=exclusion,
            manifest_path=manifest,
        )
    )
    assert snapshot_backup == backup_dir / "snapshot" / "part-000.parquet"
    assert exclusion_backup == backup_dir / "exclusion" / "part-000.parquet"
    assert manifest_backup == backup_dir / "manifest" / "manifest.json"
    assert snapshot_backup != exclusion_backup


def test_recovered_gate6_restores_originals_if_routed_universe_changes() -> None:
    source = inspect.getsource(
        Phase25Gate6RecoveredPrerequisiteReconstruction._reconcile_one_reacquired_session
    )
    assert "except Exception:" in source
    assert "self._restore_file(backup_snapshot, snapshot)" in source
    assert "self._restore_file(backup_exclusion, exclusion)" in source
    assert "self._restore_file(backup_manifest, manifest_path)" in source
    assert "authoritative reference recovery changes the routed Phase7 universe" in source


def test_recovered_gate6_validator_preserves_gate6_zero_authority() -> None:
    source = inspect.getsource(Phase25Gate6RecoveredIndependentValidator.run)
    assert '"gate6_provider_activity_zero"' in source
    assert '"protected_evidence_zero"' in source
    assert '"broker_order_paper_live_zero"' in source
    assert '"strategy_returns_unread"' in source
    assert '"support_authority_false"' in source
    assert '"recovered_reference_routed_universe_drift_zero"' in source
    assert '"recovered_reference_exclusion_drift_diagnostic_only"' in source


def test_recovery_lineage_hash_is_stable() -> None:
    payload = [
        {
            "session": "2026-08-11",
            "snapshot_sha256": "a" * 64,
            "manifest_sha256": "b" * 64,
            "row_count": 10,
            "instrument_count": 9,
        }
    ]
    assert _stable_hash(payload) == _stable_hash(payload)
    assert len(_stable_hash(payload)) == 64
