from __future__ import annotations

import inspect

from packages.backtesting.phase25_gate6_recovery import (
    Phase25Gate6RecoveredIndependentValidator,
    Phase25Gate6RecoveredPrerequisiteReconstruction,
)
from packages.backtesting.phase25_gate6_reference_rebind import (
    PHASE25_GATE6_REFERENCE_REBIND_CONTRACT_VERSION,
    Phase25Gate6ReferenceRebindIndependentValidator,
    Phase25Gate6ReferenceRebindReconstruction,
)


def test_reference_rebind_is_recovery_only_and_versioned() -> None:
    assert PHASE25_GATE6_REFERENCE_REBIND_CONTRACT_VERSION.startswith(
        "phase25-gate6-reference-rebind-v1-"
    )
    assert issubclass(
        Phase25Gate6ReferenceRebindReconstruction,
        Phase25Gate6RecoveredPrerequisiteReconstruction,
    )
    assert issubclass(
        Phase25Gate6ReferenceRebindIndependentValidator,
        Phase25Gate6RecoveredIndependentValidator,
    )


def test_reference_rebind_backs_up_before_force_rebuild() -> None:
    source = inspect.getsource(Phase25Gate6ReferenceRebindReconstruction._reconcile_one)
    backup_snapshot = source.index("self._backup_file(snapshot, backup_snapshot)")
    backup_exclusion = source.index("self._backup_file(exclusion, backup_exclusion)")
    backup_manifest = source.index("self._backup_file(manifest_path, backup_manifest)")
    force_rebuild = source.index("UniverseManager(self.settings).build(session, force=True)")
    assert backup_snapshot < force_rebuild
    assert backup_exclusion < force_rebuild
    assert backup_manifest < force_rebuild


def test_reference_rebind_requires_exact_derived_output_preservation() -> None:
    source = inspect.getsource(Phase25Gate6ReferenceRebindReconstruction._reconcile_one)
    assert "rebuilt_snapshot_sha == prior_snapshot_sha" in source
    assert "rebuilt_exclusion_sha == prior_exclusion_sha" in source
    assert "rebuilt.fingerprint == prior_fingerprint" in source
    assert "authoritative reference recovery changes Phase7 derived output" in source


def test_reference_rebind_restores_originals_on_any_rebuild_failure() -> None:
    source = inspect.getsource(Phase25Gate6ReferenceRebindReconstruction._reconcile_one)
    assert "except Exception:" in source
    assert "self._restore_file(backup_snapshot, snapshot)" in source
    assert "self._restore_file(backup_exclusion, exclusion)" in source
    assert "self._restore_file(backup_manifest, manifest_path)" in source


def test_reference_rebind_only_accepts_reference_sha_only_staleness() -> None:
    source = inspect.getsource(
        Phase25Gate6ReferenceRebindReconstruction._assert_only_reference_sha_is_stale
    )
    for check in (
        "manifest_version",
        "contract_version",
        "policy_version",
        "policy_fingerprint",
        "as_of_date",
        "reference_date",
        "routing_input",
        "snapshot_sha",
        "exclusion_sha",
        "reference_sha_stale",
    ):
        assert f'"{check}"' in source


def test_reference_rebind_validator_reopens_live_bindings() -> None:
    source = inspect.getsource(Phase25Gate6ReferenceRebindIndependentValidator.run)
    assert 'manifest.get("source_reference_sha256") == sha256_file(reference)' in source
    assert 'manifest.get("snapshot_sha256") == sha256_file(universe)' in source
    assert 'manifest.get("exclusion_sha256") == sha256_file(exclusion)' in source
    assert '"reference_rebind_semantic_drift_zero"' in source
