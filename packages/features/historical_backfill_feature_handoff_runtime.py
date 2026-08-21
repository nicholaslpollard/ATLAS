from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.historical_backfill_feature_handoff import (
    COMPONENT_FEATURES,
    COMPONENT_MANIFESTS,
    COMPONENT_ORDER,
    COMPONENT_STATE,
    GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
    HistoricalBackfillDailyFeatureHandoff,
    HistoricalBackfillDailyFeatureHandoffValidator,
    STATE_PROMOTED,
    _inventory_matches,
)


class HistoricalBackfillDailyFeatureHandoffRuntime(HistoricalBackfillDailyFeatureHandoff):
    """Runtime-hardened Gate 9-C handoff using the v1 journal/data contract."""

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
    """Use the runtime-hardened handoff while retaining the independent v1 proof."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.handoff = HistoricalBackfillDailyFeatureHandoffRuntime(settings)
        self.paths = self.handoff.paths
        self.report_path = (
            self.handoff.promotion_root / "gate9c_handoff_validation_report.json"
        )
