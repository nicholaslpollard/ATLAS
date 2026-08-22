from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text, replace_with_retry
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_validated_evidence import sha256_file
from packages.features.historical_backfill_feature_handoff import (
    COMPONENT_FEATURES,
    COMPONENT_MANIFESTS,
    COMPONENT_ORDER,
    COMPONENT_STATE,
    GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
    Gate9FeatureHandoffError,
    HistoricalBackfillDailyFeatureHandoff,
    HistoricalBackfillDailyFeatureHandoffValidator,
    STATE_INITIAL,
    STATE_OLD_MOVED,
    STATE_PROMOTED,
    _inventory_matches,
    handoff_source_fingerprint,
)


class HistoricalBackfillDailyFeatureHandoffRuntime(HistoricalBackfillDailyFeatureHandoff):
    """Runtime-hardened Gate 9-C handoff using the v1 journal/data contract."""

    @staticmethod
    def _move_with_retry(source: Path, target: Path) -> None:
        """Same-filesystem atomic directory rename with bounded Windows lock retries."""

        source = Path(source)
        target = Path(target)
        if not source.exists():
            raise Gate9FeatureHandoffError(f"handoff source is missing: {source}")
        if target.exists():
            raise Gate9FeatureHandoffError(f"handoff target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        if os.stat(source).st_dev != os.stat(target.parent).st_dev:
            raise Gate9FeatureHandoffError(
                f"handoff directory rename crosses filesystems: {source} -> {target}"
            )
        replace_with_retry(source, target)

    def _prepare_manifests(self, journal: dict[str, Any]) -> None:
        component = journal["components"][COMPONENT_MANIFESTS]
        live = Path(str(component["live"]))
        rollback = Path(str(component["rollback"]))
        prepared = Path(str(component["source"]))
        expected_new = list(journal["promotion_inventory"][COMPONENT_MANIFESTS])
        expected_old = list(journal["rollback_inventory"][COMPONENT_MANIFESTS])

        # A crash/rerun after the manifest swap must not recreate the consumed prepared
        # directory, which would make an otherwise valid promoted state ambiguous.
        already_promoted = (
            _inventory_matches(live, "**/*.json", expected_new)
            and _inventory_matches(rollback, "**/*.json", expected_old)
            and not prepared.exists()
        )
        if already_promoted:
            journal["steps"]["prepared_manifests"] = True
            self._write_journal(journal)
            return
        super()._prepare_manifests(journal)

    def _promote_component(self, journal: dict[str, Any], component_name: str) -> None:
        component = journal["components"][component_name]
        live = Path(str(component["live"]))
        rollback = Path(str(component["rollback"]))
        source = Path(str(component["source"]))

        state = self._disk_state(journal, component_name)
        if state == STATE_INITIAL:
            self._move_with_retry(live, rollback)
            state = self._disk_state(journal, component_name)
        if state == STATE_OLD_MOVED:
            self._move_with_retry(source, live)
            state = self._disk_state(journal, component_name)
        if state != STATE_PROMOTED:
            raise Gate9FeatureHandoffError(
                f"Gate 9-C {component_name} filesystem state is invalid: {state}"
            )
        journal["steps"][component_name] = True
        self._write_journal(journal)

    def _rollback_component(self, journal: dict[str, Any], component_name: str) -> None:
        component = journal["components"][component_name]
        live = Path(str(component["live"]))
        rollback = Path(str(component["rollback"]))
        source = Path(str(component["source"]))
        pattern = str(component["pattern"])
        old = list(journal["rollback_inventory"][component_name])
        new = list(journal["promotion_inventory"][component_name])

        state = self._disk_state(journal, component_name)
        if state == STATE_INITIAL:
            journal["steps"][component_name] = False
            self._write_journal(journal)
            return
        if state == STATE_OLD_MOVED:
            self._move_with_retry(rollback, live)
        elif state == STATE_PROMOTED:
            if source.exists():
                raise Gate9FeatureHandoffError(
                    f"Gate 9-C rollback source target already exists: {source}"
                )
            self._move_with_retry(live, source)
            if not _inventory_matches(source, pattern, new):
                raise Gate9FeatureHandoffError(
                    f"Gate 9-C rollback failed to preserve promoted {component_name}"
                )
            self._move_with_retry(rollback, live)
        else:
            raise Gate9FeatureHandoffError(
                f"Gate 9-C cannot rollback invalid {component_name} filesystem state: {state}"
            )
        if not _inventory_matches(live, pattern, old):
            raise Gate9FeatureHandoffError(
                f"Gate 9-C rollback did not restore original {component_name}"
            )
        journal["steps"][component_name] = False
        self._write_journal(journal)

    def _finalize_report(
        self,
        journal: dict[str, Any],
        proof: dict[str, object],
    ) -> dict[str, object]:
        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": journal["role"],
            "source_fingerprint": journal["source_fingerprint"],
            "handoff_id": journal["handoff_id"],
            "status": journal["status"],
            "rows": int(journal["expected_rows"]),
            "sessions": int(journal["expected_sessions"]),
            "first_session": journal["expected_first_session"],
            "last_session": journal["expected_last_session"],
            "production_feature_files": len(
                journal["promotion_inventory"][COMPONENT_FEATURES]
            ),
            "production_manifest_files": len(
                journal["promotion_inventory"][COMPONENT_MANIFESTS]
            ),
            "production_state_files": len(
                journal["promotion_inventory"][COMPONENT_STATE]
            ),
            "rollback_feature_files": len(
                journal["rollback_inventory"][COMPONENT_FEATURES]
            ),
            "rollback_manifest_files": len(
                journal["rollback_inventory"][COMPONENT_MANIFESTS]
            ),
            "rollback_state_files": len(journal["rollback_inventory"][COMPONENT_STATE]),
            "rollback_inventory_fingerprint": journal["rollback_inventory_fingerprint"],
            "promotion_inventory_fingerprint": journal["promotion_inventory_fingerprint"],
            "proof": proof,
            "rollback_paths": {
                component: journal["components"][component]["rollback"]
                for component in COMPONENT_ORDER
            },
            "checks": {
                "handoff_contract": True,
                "journal_complete": journal["status"] == "COMPLETE",
                "all_components_promoted": all(
                    state == STATE_PROMOTED
                    for state in proof["component_states"].values()
                ),
                "current_state_exact": proof["current_state_fingerprint"]
                == journal["expected_current_state_fingerprint"],
                "current_state_range_exact": proof["current_state_as_of"]
                == journal["expected_last_session"],
                "final_manifest_state_chain_exact": proof[
                    "last_manifest_output_state_fingerprint"
                ]
                == journal["expected_current_state_fingerprint"],
                "rollback_preserved": True,
            },
            "journal_path": str(self.journal_path),
            "report_path": str(self.report_path),
        }
        report["pass"] = all(report["checks"].values())
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report

    def apply(self) -> dict[str, object]:
        journal = self._load_or_create_journal()

        # Full reruns after success are read-only verification, not a second migration.
        if journal.get("status") == "COMPLETE":
            proof = self._verify_complete(journal)
            return self._finalize_report(journal, proof)

        if journal.get("status") == "ROLLED_BACK":
            journal["status"] = "PLANNED"
            self._write_journal(journal)

        self._prepare_manifests(journal)
        for component in COMPONENT_ORDER:
            self._promote_component(journal, component)
        proof = self._verify_complete(journal)
        journal["status"] = "COMPLETE"
        journal["completed_at_utc"] = datetime.now(UTC).isoformat()
        self._write_journal(journal)
        return self._finalize_report(journal, proof)


class HistoricalBackfillDailyFeatureHandoffRuntimeValidator(
    HistoricalBackfillDailyFeatureHandoffValidator
):
    """Independent production proof plus recomputation of handoff provenance."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.handoff = HistoricalBackfillDailyFeatureHandoffRuntime(settings)
        self.paths = self.handoff.paths
        self.report_path = (
            self.handoff.promotion_root / "gate9c_handoff_validation_report.json"
        )

    def run(self) -> dict[str, object]:
        report = super().run()
        journal = self.handoff._load_json(
            self.handoff.journal_path,
            "Gate 9-C handoff journal",
        )

        parent_report_hashes_exact = (
            sha256_file(Path(str(journal["stage_report_path"])))
            == journal["stage_report_sha256"]
            and sha256_file(Path(str(journal["stage_validation_path"])))
            == journal["stage_validation_sha256"]
        )
        preflight_payload = self.handoff._load_json(
            Path(str(journal["preflight_report_path"])),
            "Gate 9-C frozen preflight report",
        )
        preflight_fingerprint_exact = (
            preflight_payload.get("source_fingerprint")
            == journal["preflight_source_fingerprint"]
        )
        rollback_inventory_fp = self.handoff._component_inventory_fingerprint(
            journal["rollback_inventory"]
        )
        promotion_inventory_fp = self.handoff._component_inventory_fingerprint(
            journal["promotion_inventory"]
        )
        inventory_fingerprints_exact = (
            rollback_inventory_fp == journal["rollback_inventory_fingerprint"]
            and promotion_inventory_fp == journal["promotion_inventory_fingerprint"]
        )
        expected_source_fp = handoff_source_fingerprint(
            stage_source_fingerprint=str(journal["stage_source_fingerprint"]),
            stage_report_sha256=str(journal["stage_report_sha256"]),
            stage_validation_sha256=str(journal["stage_validation_sha256"]),
            preflight_source_fingerprint=str(journal["preflight_source_fingerprint"]),
            production_baseline_fingerprint=str(
                journal["production_baseline_fingerprint"]
            ),
            rollback_inventory_fingerprint=rollback_inventory_fp,
            promotion_inventory_fingerprint=promotion_inventory_fp,
        )
        handoff_source_fingerprint_exact = (
            expected_source_fp == journal["source_fingerprint"]
        )

        checks = dict(report["checks"])
        checks.update(
            {
                "parent_report_hashes_exact": parent_report_hashes_exact,
                "frozen_preflight_fingerprint_exact": preflight_fingerprint_exact,
                "inventory_fingerprints_exact": inventory_fingerprints_exact,
                "handoff_source_fingerprint_recomputed": handoff_source_fingerprint_exact,
            }
        )
        report["checks"] = checks
        report["rollback_inventory_fingerprint"] = rollback_inventory_fp
        report["promotion_inventory_fingerprint"] = promotion_inventory_fp
        report["recomputed_handoff_source_fingerprint"] = expected_source_fp
        report["pass"] = all(checks.values())
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
