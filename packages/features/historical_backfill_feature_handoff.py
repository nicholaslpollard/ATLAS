from __future__ import annotations

import json
import os
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.features.historical_backfill_feature_promotion_stage import (
    GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION,
    GATE9_FEATURE_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION,
    HistoricalBackfillDailyFeaturePromotionStage,
    HistoricalBackfillDailyFeaturePromotionStageValidator,
)
from packages.features.partition_store import (
    FeaturePartitionManifest,
    feature_dependency_fingerprint,
)


GATE9_FEATURE_HANDOFF_CONTRACT_VERSION = (
    "historical-backfill-feature-handoff-v1-journaled-directory-rollback"
)
GATE9_FEATURE_HANDOFF_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-feature-handoff-validation-v1-independent-production-disk-proof"
)
GATE9_FEATURE_HANDOFF_ROLE = "PRODUCTION_DAILY_FEATURE_HANDOFF"

COMPONENT_FEATURES = "features"
COMPONENT_MANIFESTS = "manifests"
COMPONENT_STATE = "state"
COMPONENT_ORDER = (COMPONENT_FEATURES, COMPONENT_MANIFESTS, COMPONENT_STATE)

STATE_INITIAL = "OLD_LIVE_NEW_STAGED"
STATE_OLD_MOVED = "OLD_ROLLBACK_NEW_STAGED"
STATE_PROMOTED = "NEW_LIVE_OLD_ROLLBACK"
STATE_INVALID = "INVALID"


class Gate9FeatureHandoffError(RuntimeError):
    pass


def _inventory(root: Path, pattern: str) -> list[dict[str, object]]:
    root = Path(root)
    if not root.exists():
        return []
    rows: list[dict[str, object]] = []
    for path in sorted(root.glob(pattern)):
        if not path.is_file():
            continue
        rows.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": int(path.stat().st_size),
            }
        )
    return rows


def inventory_fingerprint(rows: list[dict[str, object]]) -> str:
    normalized = [
        {
            "relative_path": str(row["relative_path"]).replace("\\", "/"),
            "sha256": str(row["sha256"]),
            "bytes": int(row.get("bytes", 0)),
        }
        for row in rows
    ]
    normalized.sort(key=lambda item: item["relative_path"])
    return stable_source_fingerprint({"files": normalized})


def handoff_source_fingerprint(
    *,
    stage_source_fingerprint: str,
    stage_report_sha256: str,
    stage_validation_sha256: str,
    preflight_source_fingerprint: str,
    production_baseline_fingerprint: str,
    rollback_inventory_fingerprint: str,
    promotion_inventory_fingerprint: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
            "role": GATE9_FEATURE_HANDOFF_ROLE,
            "stage_contract_version": GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION,
            "stage_validation_contract_version": GATE9_FEATURE_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION,
            "stage_source_fingerprint": stage_source_fingerprint,
            "stage_report_sha256": stage_report_sha256,
            "stage_validation_sha256": stage_validation_sha256,
            "preflight_source_fingerprint": preflight_source_fingerprint,
            "production_baseline_fingerprint": production_baseline_fingerprint,
            "rollback_inventory_fingerprint": rollback_inventory_fingerprint,
            "promotion_inventory_fingerprint": promotion_inventory_fingerprint,
            "timeframe": Timeframe.DAY_1.value,
        }
    )


def _inventory_matches(root: Path, pattern: str, expected: list[dict[str, object]]) -> bool:
    if not Path(root).exists():
        return False
    return _inventory(Path(root), pattern) == expected


def component_disk_state(
    *,
    live_matches_old: bool,
    live_matches_new: bool,
    live_missing: bool,
    rollback_matches_old: bool,
    rollback_missing: bool,
    source_matches_new: bool,
    source_missing: bool,
) -> str:
    """Classify one restartable handoff component from exact filesystem evidence."""

    if live_matches_old and rollback_missing and source_matches_new:
        return STATE_INITIAL
    if live_missing and rollback_matches_old and source_matches_new:
        return STATE_OLD_MOVED
    if live_matches_new and rollback_matches_old and source_missing:
        return STATE_PROMOTED
    return STATE_INVALID


def _same_device_move(source: Path, target: Path) -> None:
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
    os.replace(source, target)


class HistoricalBackfillDailyFeatureHandoff:
    """Promote the accepted Gate 9-C stage by restartable directory renames.

    The operation is intentionally limited to the production 1d feature partitions,
    their normal production manifests, and their 1d state directory. The previous
    production trees are moved intact into same-filesystem rollback roots before the
    staged replacements become live. Filesystem state, not journal timing, is the
    authority after interruption.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.stage_validator = HistoricalBackfillDailyFeaturePromotionStageValidator(settings)
        self.stage: HistoricalBackfillDailyFeaturePromotionStage = self.stage_validator.stage
        self.preflight = self.stage.preflight
        self.paths = self.preflight.paths
        self.promotion_root = self.preflight.root
        self.journal_path = self.promotion_root / "gate9c_handoff_journal.json"
        self.report_path = self.promotion_root / "gate9c_handoff_report.json"

        derived_root = settings.resolved_path(settings.data.paths.derived)
        manifests_root = settings.resolved_path(settings.data.paths.manifests)
        self.live_feature_root = derived_root / "features" / Timeframe.DAY_1.value
        self.live_state_root = derived_root / "features" / "_state" / Timeframe.DAY_1.value
        self.live_manifest_root = manifests_root / "features" / Timeframe.DAY_1.value

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not Path(path).is_file():
            raise Gate9FeatureHandoffError(f"Gate 9-C handoff requires {label}: {path}")
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def _write_journal(self, journal: dict[str, Any]) -> None:
        journal["updated_at_utc"] = datetime.now(UTC).isoformat()
        atomic_write_text(
            self.journal_path,
            json.dumps(journal, indent=2, sort_keys=True) + "\n",
        )

    @staticmethod
    def _component_inventory_fingerprint(
        inventories: dict[str, list[dict[str, object]]],
    ) -> str:
        return stable_source_fingerprint(
            {
                component: [
                    {
                        "relative_path": str(row["relative_path"]),
                        "sha256": str(row["sha256"]),
                        "bytes": int(row["bytes"]),
                    }
                    for row in inventories[component]
                ]
                for component in COMPONENT_ORDER
            }
        )

    def _component_paths(self, handoff_id: str) -> dict[str, dict[str, str]]:
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        manifests_root = self.settings.resolved_path(self.settings.data.paths.manifests)
        rollback_derived = derived_root / "features" / "_rollback" / handoff_id
        rollback_manifests = manifests_root / "features" / "_rollback" / handoff_id
        prepared_manifests = (
            self.live_manifest_root.parent / f"_gate9c_prepared_{handoff_id}"
        )
        return {
            COMPONENT_FEATURES: {
                "live": str(self.live_feature_root),
                "rollback": str(rollback_derived / Timeframe.DAY_1.value),
                "source": str(self.stage.staged_feature_root),
                "pattern": "**/*.parquet",
            },
            COMPONENT_MANIFESTS: {
                "live": str(self.live_manifest_root),
                "rollback": str(rollback_manifests / Timeframe.DAY_1.value),
                "source": str(prepared_manifests),
                "stage_source": str(self.stage.staged_manifest_root),
                "pattern": "**/*.json",
            },
            COMPONENT_STATE: {
                "live": str(self.live_state_root),
                "rollback": str(rollback_derived / "_state" / Timeframe.DAY_1.value),
                "source": str(self.stage.staged_state_root),
                "pattern": "**/*.json.gz",
            },
        }

    def _new_plan(self) -> dict[str, Any]:
        validation = self.stage_validator.run()
        if validation.get("pass") is not True:
            raise Gate9FeatureHandoffError(
                "Gate 9-C production handoff requires accepted staged-bundle validation"
            )
        stage_report = self._load_json(self.stage.report_path, "Gate 9-C stage report")
        preflight_report = self._load_json(
            self.preflight.report_path,
            "Gate 9-C promotion preflight report",
        )
        if stage_report.get("pass") is not True or preflight_report.get("pass") is not True:
            raise Gate9FeatureHandoffError("Gate 9-C parent evidence is not passing")

        baseline_rows, baseline_stats = self.preflight.replay.preflight._production_feature_baseline()
        if str(baseline_stats["fingerprint"]) != str(
            preflight_report["production_rollback_baseline"]["fingerprint"]
        ):
            raise Gate9FeatureHandoffError("Gate 9-C live rollback baseline changed")

        promotion_inventories = {
            COMPONENT_FEATURES: _inventory(self.stage.staged_feature_root, "**/*.parquet"),
            COMPONENT_MANIFESTS: _inventory(self.stage.staged_manifest_root, "**/*.json"),
            COMPONENT_STATE: _inventory(self.stage.staged_state_root, "**/*.json.gz"),
        }
        rollback_inventories = {
            COMPONENT_FEATURES: _inventory(self.live_feature_root, "**/*.parquet"),
            COMPONENT_MANIFESTS: _inventory(self.live_manifest_root, "**/*.json"),
            COMPONENT_STATE: _inventory(self.live_state_root, "**/*.json.gz"),
        }

        expected_stage_sessions = int(stage_report["candidate_sessions"])
        if len(promotion_inventories[COMPONENT_FEATURES]) != expected_stage_sessions:
            raise Gate9FeatureHandoffError("Gate 9-C staged feature inventory is incomplete")
        if len(promotion_inventories[COMPONENT_MANIFESTS]) != expected_stage_sessions:
            raise Gate9FeatureHandoffError("Gate 9-C staged manifest inventory is incomplete")
        if len(promotion_inventories[COMPONENT_STATE]) != int(stage_report["staged_state_files"]):
            raise Gate9FeatureHandoffError("Gate 9-C staged state inventory is incomplete")
        if len(rollback_inventories[COMPONENT_FEATURES]) != int(baseline_stats["sessions"]):
            raise Gate9FeatureHandoffError("Gate 9-C rollback feature inventory is incomplete")
        if len(rollback_inventories[COMPONENT_MANIFESTS]) != int(baseline_stats["sessions"]):
            raise Gate9FeatureHandoffError("Gate 9-C rollback manifest inventory is incomplete")
        if len(rollback_inventories[COMPONENT_STATE]) != int(baseline_stats["state_files"]):
            raise Gate9FeatureHandoffError("Gate 9-C rollback state inventory is incomplete")

        rollback_fp = self._component_inventory_fingerprint(rollback_inventories)
        promotion_fp = self._component_inventory_fingerprint(promotion_inventories)
        stage_report_sha = sha256_file(self.stage.report_path)
        stage_validation_sha = sha256_file(self.stage_validator.report_path)
        source_fp = handoff_source_fingerprint(
            stage_source_fingerprint=str(stage_report["source_fingerprint"]),
            stage_report_sha256=stage_report_sha,
            stage_validation_sha256=stage_validation_sha,
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            production_baseline_fingerprint=str(baseline_stats["fingerprint"]),
            rollback_inventory_fingerprint=rollback_fp,
            promotion_inventory_fingerprint=promotion_fp,
        )
        handoff_id = source_fp[:16]
        components = self._component_paths(handoff_id)
        for component in COMPONENT_ORDER:
            rollback = Path(components[component]["rollback"])
            if rollback.exists():
                raise Gate9FeatureHandoffError(
                    f"Gate 9-C rollback target exists before journal creation: {rollback}"
                )
        prepared_manifest_root = Path(components[COMPONENT_MANIFESTS]["source"])
        if prepared_manifest_root.exists():
            raise Gate9FeatureHandoffError(
                f"Gate 9-C prepared manifest root exists before journal creation: {prepared_manifest_root}"
            )

        return {
            "contract_version": GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "updated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_FEATURE_HANDOFF_ROLE,
            "status": "PLANNED",
            "source_fingerprint": source_fp,
            "handoff_id": handoff_id,
            "stage_source_fingerprint": stage_report["source_fingerprint"],
            "stage_report_path": str(self.stage.report_path),
            "stage_report_sha256": stage_report_sha,
            "stage_validation_path": str(self.stage_validator.report_path),
            "stage_validation_sha256": stage_validation_sha,
            "preflight_report_path": str(self.preflight.report_path),
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "production_baseline_fingerprint": baseline_stats["fingerprint"],
            "rollback_inventory_fingerprint": rollback_fp,
            "promotion_inventory_fingerprint": promotion_fp,
            "expected_rows": int(stage_report["candidate_rows"]),
            "expected_sessions": expected_stage_sessions,
            "expected_first_session": stage_report["first_session"],
            "expected_last_session": stage_report["last_session"],
            "expected_current_state_fingerprint": stage_report[
                "staged_current_state_fingerprint"
            ],
            "expected_current_state_sha256": stage_report["staged_current_state_sha256"],
            "components": components,
            "rollback_inventory": rollback_inventories,
            "promotion_inventory": promotion_inventories,
            "steps": {
                "prepared_manifests": False,
                COMPONENT_FEATURES: False,
                COMPONENT_MANIFESTS: False,
                COMPONENT_STATE: False,
            },
        }

    def _load_or_create_journal(self) -> dict[str, Any]:
        if self.journal_path.is_file():
            journal = self._load_json(self.journal_path, "Gate 9-C handoff journal")
            if journal.get("contract_version") != GATE9_FEATURE_HANDOFF_CONTRACT_VERSION:
                raise Gate9FeatureHandoffError("Gate 9-C handoff journal contract is stale")
            return journal
        journal = self._new_plan()
        self._write_journal(journal)
        return journal

    def _prepare_manifests(self, journal: dict[str, Any]) -> None:
        component = journal["components"][COMPONENT_MANIFESTS]
        stage_source = Path(str(component["stage_source"]))
        prepared = Path(str(component["source"]))
        expected = list(journal["promotion_inventory"][COMPONENT_MANIFESTS])
        if _inventory_matches(prepared, "**/*.json", expected):
            journal["steps"]["prepared_manifests"] = True
            self._write_journal(journal)
            return
        if prepared.exists():
            raise Gate9FeatureHandoffError(
                "Gate 9-C prepared manifest directory exists but does not match staged evidence"
            )
        if not _inventory_matches(stage_source, "**/*.json", expected):
            raise Gate9FeatureHandoffError("Gate 9-C staged production manifests changed")
        prepared.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage_source, prepared, copy_function=shutil.copy2)
        if not _inventory_matches(prepared, "**/*.json", expected):
            raise Gate9FeatureHandoffError("Gate 9-C prepared manifest copy failed hash proof")
        journal["steps"]["prepared_manifests"] = True
        self._write_journal(journal)

    def _disk_state(self, journal: dict[str, Any], component_name: str) -> str:
        component = journal["components"][component_name]
        pattern = str(component["pattern"])
        live = Path(str(component["live"]))
        rollback = Path(str(component["rollback"]))
        source = Path(str(component["source"]))
        old = list(journal["rollback_inventory"][component_name])
        new = list(journal["promotion_inventory"][component_name])
        return component_disk_state(
            live_matches_old=_inventory_matches(live, pattern, old),
            live_matches_new=_inventory_matches(live, pattern, new),
            live_missing=not live.exists(),
            rollback_matches_old=_inventory_matches(rollback, pattern, old),
            rollback_missing=not rollback.exists(),
            source_matches_new=_inventory_matches(source, pattern, new),
            source_missing=not source.exists(),
        )

    def _promote_component(self, journal: dict[str, Any], component_name: str) -> None:
        component = journal["components"][component_name]
        live = Path(str(component["live"]))
        rollback = Path(str(component["rollback"]))
        source = Path(str(component["source"]))

        state = self._disk_state(journal, component_name)
        if state == STATE_INITIAL:
            _same_device_move(live, rollback)
            state = self._disk_state(journal, component_name)
        if state == STATE_OLD_MOVED:
            _same_device_move(source, live)
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
            _same_device_move(rollback, live)
        elif state == STATE_PROMOTED:
            if source.exists():
                raise Gate9FeatureHandoffError(
                    f"Gate 9-C rollback source target already exists: {source}"
                )
            _same_device_move(live, source)
            if not _inventory_matches(source, pattern, new):
                raise Gate9FeatureHandoffError(
                    f"Gate 9-C rollback failed to preserve promoted {component_name}"
                )
            _same_device_move(rollback, live)
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

    def _verify_complete(self, journal: dict[str, Any]) -> dict[str, object]:
        component_states = {
            component: self._disk_state(journal, component) for component in COMPONENT_ORDER
        }
        if any(state != STATE_PROMOTED for state in component_states.values()):
            raise Gate9FeatureHandoffError(
                f"Gate 9-C production handoff is incomplete: {component_states}"
            )

        current_state = self.paths.feature_current_state_file(Timeframe.DAY_1)
        if sha256_file(current_state) != str(journal["expected_current_state_sha256"]):
            raise Gate9FeatureHandoffError("Gate 9-C live current-state hash mismatch")
        _engine, current_payload = self.stage.checkpoints.read(
            current_state,
            expected_timeframe=Timeframe.DAY_1,
        )
        if current_payload.get("checkpoint_fingerprint") != journal[
            "expected_current_state_fingerprint"
        ]:
            raise Gate9FeatureHandoffError("Gate 9-C live current-state fingerprint mismatch")
        if current_payload.get("as_of_date") != journal["expected_last_session"]:
            raise Gate9FeatureHandoffError("Gate 9-C live current-state as-of mismatch")

        last_session = date.fromisoformat(str(journal["expected_last_session"]))
        last_manifest_path = self.paths.feature_manifest_file(Timeframe.DAY_1, last_session)
        last_manifest = FeaturePartitionManifest.from_dict(
            json.loads(last_manifest_path.read_text(encoding="utf-8"))
        )
        last_manifest.validate_contract(Timeframe.DAY_1, last_session)
        if last_manifest.output_state_fingerprint != current_payload.get(
            "checkpoint_fingerprint"
        ):
            raise Gate9FeatureHandoffError(
                "Gate 9-C final production manifest does not terminate at current state"
            )

        return {
            "component_states": component_states,
            "current_state_fingerprint": current_payload["checkpoint_fingerprint"],
            "current_state_as_of": current_payload["as_of_date"],
            "last_manifest_output_state_fingerprint": last_manifest.output_state_fingerprint,
        }

    def apply(self) -> dict[str, object]:
        journal = self._load_or_create_journal()
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

        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_FEATURE_HANDOFF_ROLE,
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
            "production_state_files": len(journal["promotion_inventory"][COMPONENT_STATE]),
            "rollback_feature_files": len(journal["rollback_inventory"][COMPONENT_FEATURES]),
            "rollback_manifest_files": len(journal["rollback_inventory"][COMPONENT_MANIFESTS]),
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

    def rollback(self) -> dict[str, object]:
        if not self.journal_path.is_file():
            raise Gate9FeatureHandoffError("Gate 9-C has no handoff journal to rollback")
        journal = self._load_json(self.journal_path, "Gate 9-C handoff journal")
        if journal.get("contract_version") != GATE9_FEATURE_HANDOFF_CONTRACT_VERSION:
            raise Gate9FeatureHandoffError("Gate 9-C handoff journal contract is stale")
        # Restore feature files and manifests before exposing the old current-state checkpoint.
        for component in COMPONENT_ORDER:
            self._rollback_component(journal, component)
        journal["status"] = "ROLLED_BACK"
        journal["rolled_back_at_utc"] = datetime.now(UTC).isoformat()
        self._write_journal(journal)
        return {
            "contract_version": GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
            "status": journal["status"],
            "source_fingerprint": journal["source_fingerprint"],
            "handoff_id": journal["handoff_id"],
            "rollback_restored": all(
                self._disk_state(journal, component) == STATE_INITIAL
                for component in COMPONENT_ORDER
            ),
            "journal_path": str(self.journal_path),
        }


class HistoricalBackfillDailyFeatureHandoffValidator:
    """Independently prove live production and rollback trees after Gate 9-C handoff."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.handoff = HistoricalBackfillDailyFeatureHandoff(settings)
        self.paths = self.handoff.paths
        self.report_path = self.handoff.promotion_root / "gate9c_handoff_validation_report.json"

    def _validate_inventory_root(
        self,
        root: Path,
        pattern: str,
        expected: list[dict[str, object]],
    ) -> int:
        return 0 if _inventory(root, pattern) == expected else 1

    def run(self) -> dict[str, object]:
        journal = self.handoff._load_json(
            self.handoff.journal_path,
            "Gate 9-C handoff journal",
        )
        writer_report = self.handoff._load_json(
            self.handoff.report_path,
            "Gate 9-C handoff report",
        )
        if journal.get("contract_version") != GATE9_FEATURE_HANDOFF_CONTRACT_VERSION:
            raise Gate9FeatureHandoffError("Gate 9-C handoff journal contract is stale")

        live_inventory_failures = 0
        rollback_inventory_failures = 0
        for component in COMPONENT_ORDER:
            cfg = journal["components"][component]
            live_inventory_failures += self._validate_inventory_root(
                Path(str(cfg["live"])),
                str(cfg["pattern"]),
                list(journal["promotion_inventory"][component]),
            )
            rollback_inventory_failures += self._validate_inventory_root(
                Path(str(cfg["rollback"])),
                str(cfg["pattern"]),
                list(journal["rollback_inventory"][component]),
            )

        manifest_failures = 0
        source_hash_failures = 0
        dependency_failures = 0
        row_count = 0
        session_count = 0
        feature_rows = list(journal["promotion_inventory"][COMPONENT_FEATURES])
        feature_sha_by_relative = {
            str(row["relative_path"]): str(row["sha256"]) for row in feature_rows
        }
        for row in list(journal["promotion_inventory"][COMPONENT_MANIFESTS]):
            manifest_path = self.handoff.live_manifest_root / str(row["relative_path"])
            try:
                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest = FeaturePartitionManifest.from_dict(payload)
                trading_date = date.fromisoformat(str(manifest.trading_date))
                manifest.validate_contract(Timeframe.DAY_1, trading_date)
                expected_feature_path = self.paths.feature_file(Timeframe.DAY_1, trading_date)
                feature_relative = expected_feature_path.relative_to(
                    self.handoff.live_feature_root
                ).as_posix()
                expected_feature_sha = feature_sha_by_relative.get(feature_relative)
                if expected_feature_sha is None:
                    manifest_failures += 1
                    continue
                if (
                    Path(manifest.feature_path).resolve() != expected_feature_path.resolve()
                    or manifest.feature_sha256 != expected_feature_sha
                    or sha256_file(expected_feature_path) != expected_feature_sha
                ):
                    manifest_failures += 1
                source_path = Path(manifest.source_path)
                if not source_path.is_file() or sha256_file(source_path) != manifest.source_sha256:
                    source_hash_failures += 1
                expected_dependency = feature_dependency_fingerprint(
                    source_sha256=manifest.source_sha256,
                    input_state_fingerprint=manifest.input_state_fingerprint,
                )
                if manifest.dependency_fingerprint != expected_dependency:
                    dependency_failures += 1
                row_count += int(manifest.row_count)
                session_count += 1
            except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                manifest_failures += 1

        state_failures = 0
        current_state = self.paths.feature_current_state_file(Timeframe.DAY_1)
        current_state_fp: str | None = None
        current_state_as_of: str | None = None
        try:
            if sha256_file(current_state) != journal["expected_current_state_sha256"]:
                state_failures += 1
            _engine, current_payload = self.handoff.stage.checkpoints.read(
                current_state,
                expected_timeframe=Timeframe.DAY_1,
            )
            current_state_fp = str(current_payload["checkpoint_fingerprint"])
            current_state_as_of = str(current_payload["as_of_date"])
            if (
                current_state_fp != journal["expected_current_state_fingerprint"]
                or current_state_as_of != journal["expected_last_session"]
            ):
                state_failures += 1
        except (OSError, ValueError, TypeError, KeyError):
            state_failures += 1

        final_manifest_failures = 0
        try:
            last_session = date.fromisoformat(str(journal["expected_last_session"]))
            final_payload = json.loads(
                self.paths.feature_manifest_file(Timeframe.DAY_1, last_session).read_text(
                    encoding="utf-8"
                )
            )
            final_manifest = FeaturePartitionManifest.from_dict(final_payload)
            final_manifest.validate_contract(Timeframe.DAY_1, last_session)
            if final_manifest.output_state_fingerprint != current_state_fp:
                final_manifest_failures += 1
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            final_manifest_failures += 1

        checks = {
            "validation_contract": True,
            "writer_contract": writer_report.get("contract_version")
            == GATE9_FEATURE_HANDOFF_CONTRACT_VERSION,
            "writer_report_pass": writer_report.get("pass") is True,
            "journal_complete": journal.get("status") == "COMPLETE",
            "source_fingerprint_exact": writer_report.get("source_fingerprint")
            == journal.get("source_fingerprint"),
            "live_inventory_exact": live_inventory_failures == 0,
            "rollback_inventory_exact": rollback_inventory_failures == 0,
            "production_manifests_exact": manifest_failures == 0,
            "canonical_source_hashes_exact": source_hash_failures == 0,
            "dependency_fingerprints_exact": dependency_failures == 0,
            "row_accounting_exact": row_count == int(journal["expected_rows"]),
            "session_accounting_exact": session_count == int(journal["expected_sessions"]),
            "current_state_exact": state_failures == 0,
            "final_manifest_state_chain_exact": final_manifest_failures == 0,
            "rollback_available": rollback_inventory_failures == 0,
        }
        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_HANDOFF_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "handoff_source_fingerprint": journal["source_fingerprint"],
            "handoff_id": journal["handoff_id"],
            "rows": row_count,
            "sessions": session_count,
            "first_session": journal["expected_first_session"],
            "last_session": journal["expected_last_session"],
            "live_inventory_failures": live_inventory_failures,
            "rollback_inventory_failures": rollback_inventory_failures,
            "manifest_failures": manifest_failures,
            "source_hash_failures": source_hash_failures,
            "dependency_failures": dependency_failures,
            "state_failures": state_failures,
            "final_manifest_failures": final_manifest_failures,
            "current_state_fingerprint": current_state_fp,
            "current_state_as_of": current_state_as_of,
            "checks": checks,
            "pass": all(checks.values()),
            "writer_report_path": str(self.handoff.report_path),
            "journal_path": str(self.handoff.journal_path),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
