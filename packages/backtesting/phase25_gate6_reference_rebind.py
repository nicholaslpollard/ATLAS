from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path

from packages.features.partition_store import sha256_file
from packages.schemas.universe import UNIVERSE_CONTRACT_VERSION
from packages.universe.eligibility import UNIVERSE_ELIGIBILITY_POLICY_VERSION
from packages.universe.manager import (
    UNIVERSE_MANIFEST_VERSION,
    UniverseManager,
    _routing_input_fingerprint,
)

from .phase25_gate6_recovery import (
    PHASE25_GATE6_RECOVERY_BINDING_CONTRACT_VERSION,
    Phase25Gate6RecoveredIndependentValidator,
    Phase25Gate6RecoveredPrerequisiteReconstruction,
    Phase25Gate6RecoveryError,
    _read_json,
)
from .phase25_prerequisite_recovery import Phase25PrerequisiteRecovery


PHASE25_GATE6_REFERENCE_REBIND_CONTRACT_VERSION = (
    "phase25-gate6-reference-rebind-v1-exact-derived-output-preservation"
)


class Phase25Gate6ReferenceRebindReconstruction(
    Phase25Gate6RecoveredPrerequisiteReconstruction
):
    """Repair stale universe-to-reference bindings after authoritative PIT recovery.

    A recovered reference snapshot can legitimately have a new physical SHA even when
    it produces the exact same Phase7 universe. The ordinary Gate6 repair path must
    refuse that stale manifest. This recovery-only layer may force-rebuild the Phase7
    universe for sessions explicitly recorded as reacquired, but only after backing up
    the existing artifacts and only if the rebuilt universe snapshot and exclusion
    snapshot are byte-identical to the prior accepted derived outputs.

    Any semantic/derived-output drift fails closed and restores the original artifacts.
    """

    def _reacquired_sessions(self, through_date: date) -> tuple[date, ...]:
        report = _read_json(Phase25PrerequisiteRecovery(self.settings).report_path(through_date))
        raw = report.get("reacquired_sessions") or []
        if not isinstance(raw, list):
            raise Phase25Gate6RecoveryError("recovery reacquired-session list is malformed")
        sessions = tuple(date.fromisoformat(str(item)) for item in raw)
        if len(set(sessions)) != len(sessions):
            raise Phase25Gate6RecoveryError("recovery reacquired-session list contains duplicates")
        return sessions

    def _backup_root(self, through_date: date, source_lineage_sha256: str) -> Path:
        return (
            Phase25PrerequisiteRecovery(self.settings).run_root(through_date)
            / "derived_reference_rebind_backup"
            / f"lineage={source_lineage_sha256[:20]}"
        )

    @staticmethod
    def _backup_file(source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if sha256_file(destination) != sha256_file(source):
                raise Phase25Gate6RecoveryError(
                    f"existing derived-rebind backup differs from live source: {destination}"
                )
            return
        shutil.copy2(source, destination)

    @staticmethod
    def _restore_file(source: Path, destination: Path) -> None:
        if not source.is_file():
            raise Phase25Gate6RecoveryError(f"derived-rebind backup is missing: {source}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    def _universe_paths(self, session: date) -> tuple[Path, Path, Path]:
        return (
            self.paths.universe_snapshot_file(session),
            self.paths.universe_exclusion_file(session),
            self.paths.universe_snapshot_manifest(session),
        )

    def _assert_only_reference_sha_is_stale(
        self,
        *,
        session: date,
        manifest: dict[str, object],
    ) -> tuple[str, str, str]:
        manager = UniverseManager(self.settings)
        snapshot, exclusion, _ = self._universe_paths(session)
        reference = self.paths.reference_snapshot_file(session)
        expected_routing = _routing_input_fingerprint(
            override_routes={},
            override_tickers={},
            unavailable_ids=set(),
            quarantined_ids=set(),
            manual_exclude_ids=set(),
        )
        current_reference_sha = sha256_file(reference)
        prior_reference_sha = str(manifest.get("source_reference_sha256") or "")
        checks = {
            "manifest_version": manifest.get("manifest_version") == UNIVERSE_MANIFEST_VERSION,
            "contract_version": manifest.get("universe_contract_version") == UNIVERSE_CONTRACT_VERSION,
            "policy_version": manifest.get("policy_version") == UNIVERSE_ELIGIBILITY_POLICY_VERSION,
            "policy_fingerprint": manifest.get("policy_fingerprint") == manager.policy.fingerprint,
            "as_of_date": manifest.get("as_of_date") == session.isoformat(),
            "reference_date": manifest.get("reference_snapshot_date") == session.isoformat(),
            "routing_input": manifest.get("routing_input_fingerprint") == expected_routing,
            "snapshot_sha": manifest.get("snapshot_sha256") == sha256_file(snapshot),
            "exclusion_sha": manifest.get("exclusion_sha256") == sha256_file(exclusion),
            "reference_sha_stale": prior_reference_sha != current_reference_sha,
        }
        if not all(checks.values()):
            failed = [name for name, passed in checks.items() if not passed]
            raise Phase25Gate6RecoveryError(
                f"recovered-session universe is not a reference-SHA-only stale case for {session}: "
                + ", ".join(failed)
            )
        return prior_reference_sha, current_reference_sha, str(manifest.get("universe_fingerprint") or "")

    def _reconcile_one(
        self,
        *,
        through_date: date,
        session: date,
        source_lineage_sha256: str,
    ) -> dict[str, object]:
        snapshot, exclusion, manifest_path = self._universe_paths(session)
        present = (snapshot.is_file(), exclusion.is_file(), manifest_path.is_file())
        if any(present) and not all(present):
            raise Phase25Gate6RecoveryError(
                f"reacquired session has partial Phase7 universe artifacts: {session}"
            )
        if not any(present):
            return {
                "session": session.isoformat(),
                "mode": "NO_EXISTING_UNIVERSE_SUPER_REBUILDS",
                "semantic_drift": False,
            }

        manifest = _read_json(manifest_path)
        current_reference_sha = sha256_file(self.paths.reference_snapshot_file(session))
        if manifest.get("source_reference_sha256") == current_reference_sha:
            return {
                "session": session.isoformat(),
                "mode": "ALREADY_CURRENT",
                "reference_sha256": current_reference_sha,
                "universe_snapshot_sha256": sha256_file(snapshot),
                "universe_exclusion_sha256": sha256_file(exclusion),
                "semantic_drift": False,
            }

        prior_reference_sha, current_reference_sha, prior_fingerprint = (
            self._assert_only_reference_sha_is_stale(session=session, manifest=manifest)
        )
        prior_snapshot_sha = sha256_file(snapshot)
        prior_exclusion_sha = sha256_file(exclusion)

        backup_dir = self._backup_root(through_date, source_lineage_sha256) / f"date={session}"
        backup_snapshot = backup_dir / snapshot.name
        backup_exclusion = backup_dir / exclusion.name
        backup_manifest = backup_dir / manifest_path.name
        self._backup_file(snapshot, backup_snapshot)
        self._backup_file(exclusion, backup_exclusion)
        self._backup_file(manifest_path, backup_manifest)

        try:
            rebuilt = UniverseManager(self.settings).build(session, force=True)
            rebuilt_snapshot_sha = sha256_file(snapshot)
            rebuilt_exclusion_sha = sha256_file(exclusion)
            exact_derived_output = (
                rebuilt_snapshot_sha == prior_snapshot_sha
                and rebuilt_exclusion_sha == prior_exclusion_sha
                and rebuilt.fingerprint == prior_fingerprint
            )
            if not exact_derived_output:
                raise Phase25Gate6RecoveryError(
                    "authoritative reference recovery changes Phase7 derived output for "
                    f"{session}; prior/new universe={prior_snapshot_sha}/{rebuilt_snapshot_sha}, "
                    f"prior/new exclusions={prior_exclusion_sha}/{rebuilt_exclusion_sha}, "
                    f"prior/new fingerprint={prior_fingerprint}/{rebuilt.fingerprint}"
                )
        except Exception:
            self._restore_file(backup_snapshot, snapshot)
            self._restore_file(backup_exclusion, exclusion)
            self._restore_file(backup_manifest, manifest_path)
            raise

        rebuilt_manifest = _read_json(manifest_path)
        if rebuilt_manifest.get("source_reference_sha256") != current_reference_sha:
            self._restore_file(backup_snapshot, snapshot)
            self._restore_file(backup_exclusion, exclusion)
            self._restore_file(backup_manifest, manifest_path)
            raise Phase25Gate6RecoveryError(
                f"rebuilt Phase7 universe did not bind current reference SHA: {session}"
            )

        return {
            "session": session.isoformat(),
            "mode": "REBIND_AFTER_EXACT_DERIVED_OUTPUT_PROOF",
            "prior_reference_sha256": prior_reference_sha,
            "current_reference_sha256": current_reference_sha,
            "universe_snapshot_sha256": prior_snapshot_sha,
            "universe_exclusion_sha256": prior_exclusion_sha,
            "universe_fingerprint": prior_fingerprint,
            "backup_directory": str(backup_dir.resolve()),
            "semantic_drift": False,
        }

    def _reconcile_reacquired_sessions(self, through_date: date) -> list[dict[str, object]]:
        recovery_report = _read_json(
            Phase25PrerequisiteRecovery(self.settings).report_path(through_date)
        )
        source_lineage_sha256 = str(recovery_report.get("source_lineage_sha256") or "")
        if len(source_lineage_sha256) != 64:
            raise Phase25Gate6RecoveryError("recovery source-lineage SHA is unavailable")
        events = [
            self._reconcile_one(
                through_date=through_date,
                session=session,
                source_lineage_sha256=source_lineage_sha256,
            )
            for session in self._reacquired_sessions(through_date)
        ]
        if any(bool(event.get("semantic_drift")) for event in events):
            raise Phase25Gate6RecoveryError("derived reference-rebind semantic drift detected")
        return events

    def run(self, *, through_date: date, progress_callback=None):  # type: ignore[no-untyped-def]
        events = self._reconcile_reacquired_sessions(through_date)
        report = super().run(
            through_date=through_date,
            progress_callback=progress_callback,
        )
        report.update(
            {
                "reference_rebind_contract_version": (
                    PHASE25_GATE6_REFERENCE_REBIND_CONTRACT_VERSION
                ),
                "reference_rebind_session_count": len(events),
                "reference_rebind_semantic_drift_count": sum(
                    bool(event.get("semantic_drift")) for event in events
                ),
                "reference_rebind_events": events,
            }
        )
        path = self.report_path(through_date)
        from packages.core.atomic_io import atomic_write_text

        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report


class Phase25Gate6ReferenceRebindIndependentValidator(
    Phase25Gate6RecoveredIndependentValidator
):
    """Independently verify recovery-only universe reference rebinding."""

    def run(self, *, through_date: date) -> dict[str, object]:
        report = super().run(through_date=through_date)
        gate6_path = Phase25Gate6RecoveredPrerequisiteReconstruction(self.settings).report_path(
            through_date
        )
        gate6 = _read_json(gate6_path)
        recovery = _read_json(
            Phase25PrerequisiteRecovery(self.settings).report_path(through_date)
        )
        reacquired = tuple(str(item) for item in (recovery.get("reacquired_sessions") or []))
        events = gate6.get("reference_rebind_events")
        if not isinstance(events, list):
            raise Phase25Gate6RecoveryError("Gate6 reference-rebind event list is missing")
        if (
            gate6.get("reference_rebind_contract_version")
            != PHASE25_GATE6_REFERENCE_REBIND_CONTRACT_VERSION
        ):
            raise Phase25Gate6RecoveryError("Gate6 reference-rebind contract mismatch")
        if int(gate6.get("reference_rebind_session_count", -1)) != len(reacquired):
            raise Phase25Gate6RecoveryError("Gate6 reference-rebind session count mismatch")
        if int(gate6.get("reference_rebind_semantic_drift_count", -1)) != 0:
            raise Phase25Gate6RecoveryError("Gate6 reference-rebind semantic drift is nonzero")

        event_sessions = tuple(str(item.get("session")) for item in events if isinstance(item, dict))
        if event_sessions != reacquired:
            raise Phase25Gate6RecoveryError("Gate6 reference-rebind event sessions mismatch")

        for raw_session in reacquired:
            session = date.fromisoformat(raw_session)
            reference = self.paths.reference_snapshot_file(session)
            universe = self.paths.universe_snapshot_file(session)
            exclusion = self.paths.universe_exclusion_file(session)
            manifest_path = self.paths.universe_snapshot_manifest(session)
            manifest = _read_json(manifest_path)
            checks = {
                "reference_binding": manifest.get("source_reference_sha256") == sha256_file(reference),
                "universe_snapshot_binding": manifest.get("snapshot_sha256") == sha256_file(universe),
                "universe_exclusion_binding": manifest.get("exclusion_sha256") == sha256_file(exclusion),
                "session": manifest.get("as_of_date") == session.isoformat(),
            }
            if not all(checks.values()):
                failed = [name for name, passed in checks.items() if not passed]
                raise Phase25Gate6RecoveryError(
                    f"independent reference-rebind validation failed for {session}: "
                    + ", ".join(failed)
                )

        checks = report.get("checks")
        if not isinstance(checks, dict):
            raise Phase25Gate6RecoveryError("Gate6 independent-validation checks are malformed")
        checks["reference_rebind_exact"] = True
        checks["reference_rebind_semantic_drift_zero"] = True
        report["checks"] = checks
        report["reference_rebind_contract_version"] = (
            PHASE25_GATE6_REFERENCE_REBIND_CONTRACT_VERSION
        )
        report["reference_rebind_session_count"] = len(reacquired)
        report["pass"] = True

        from packages.core.atomic_io import atomic_write_text

        path = self.report_path(through_date)
        atomic_write_text(path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
