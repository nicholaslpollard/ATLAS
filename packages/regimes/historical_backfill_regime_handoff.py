from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .historical_backfill_regime_promotion import _path_evidence, _read_json, _stable_hash
from .historical_backfill_regime_promotion_stage import (
    GATE10_REGIME_PROMOTION_STAGE_CONTRACT_VERSION,
    GATE10_REGIME_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION,
    HistoricalBackfillRegimePromotionStage,
    HistoricalBackfillRegimePromotionStageValidator,
    staged_manifests_are_production_native,
)
from .split_origin_policy import REGIME_HISTORY_DATASET_VERSION


GATE10_REGIME_HANDOFF_CONTRACT_VERSION = (
    "historical-backfill-regime-handoff-v1-journaled-atomic-files-rollback"
)
GATE10_REGIME_HANDOFF_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-regime-handoff-validation-v1-independent-production-disk-proof"
)
GATE10_REGIME_HANDOFF_ROLE = "PRODUCTION_REGIME_SPLIT_ORIGIN_HANDOFF"

CURRENT_KEYS = (
    "market_sector_snapshot",
    "market_sector_manifest",
    "ticker_snapshot",
    "ticker_manifest",
)
HISTORY_KEYS = ("market_raw", "market_effective", "sector_raw", "sector_effective")


class Gate10RegimeHandoffError(RuntimeError):
    pass


def gate10c_handoff_source_fingerprint(
    *,
    stage_source_fingerprint: str,
    stage_report_sha256: str,
    stage_validation_sha256: str,
    preflight_source_fingerprint: str,
    rollback_baseline: dict[str, Any],
    staged_artifacts: dict[str, Any],
) -> str:
    return _stable_hash(
        {
            "contract_version": GATE10_REGIME_HANDOFF_CONTRACT_VERSION,
            "role": GATE10_REGIME_HANDOFF_ROLE,
            "stage_contract_version": GATE10_REGIME_PROMOTION_STAGE_CONTRACT_VERSION,
            "stage_validation_contract_version": GATE10_REGIME_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION,
            "stage_source_fingerprint": stage_source_fingerprint,
            "stage_report_sha256": stage_report_sha256,
            "stage_validation_sha256": stage_validation_sha256,
            "preflight_source_fingerprint": preflight_source_fingerprint,
            "rollback_baseline": rollback_baseline,
            "staged_artifacts": staged_artifacts,
            "history_dataset_version": REGIME_HISTORY_DATASET_VERSION,
        }
    )


def classify_current_file_state(
    *,
    live_sha256: str | None,
    old_sha256: str,
    new_sha256: str,
    rollback_sha256: str | None,
) -> str:
    if live_sha256 == old_sha256 and rollback_sha256 is None:
        return "OLD_LIVE_NO_ROLLBACK"
    if live_sha256 == old_sha256 and rollback_sha256 == old_sha256:
        return "OLD_LIVE_ROLLBACK_READY"
    if live_sha256 == new_sha256 and rollback_sha256 == old_sha256:
        return "NEW_LIVE_ROLLBACK_READY"
    return "INVALID"


def classify_history_file_state(*, live_sha256: str | None, expected_sha256: str) -> str:
    if live_sha256 is None:
        return "ABSENT"
    if live_sha256 == expected_sha256:
        return "PUBLISHED_EXACT"
    return "INVALID"


class HistoricalBackfillRegimeHandoff:
    """Atomically promote the accepted Gate 10-C staged regime bundle.

    Four existing current-state files are copied into immutable rollback storage before
    being atomically replaced. Four versioned history files are atomically published.
    Filesystem hashes are authoritative on restart; the journal records progress but is
    never trusted over disk state.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.stage_validator = HistoricalBackfillRegimePromotionStageValidator(settings)
        self.stage: HistoricalBackfillRegimePromotionStage = self.stage_validator.stage
        self.preflight = self.stage.preflight
        self.root = self.preflight.root
        self.journal_path = self.root / "gate10c_handoff_journal.json"
        self.report_path = self.root / "gate10c_handoff_report.json"

    @staticmethod
    def _sha_or_none(path: Path) -> str | None:
        return sha256_file(path) if Path(path).is_file() else None

    @staticmethod
    def _copy_atomic_exact(source: Path, target: Path, expected_sha256: str) -> None:
        source = Path(source)
        target = Path(target)
        if not source.is_file() or sha256_file(source) != expected_sha256:
            raise Gate10RegimeHandoffError(f"source hash mismatch: {source}")
        if target.is_file():
            if sha256_file(target) == expected_sha256:
                return
            raise Gate10RegimeHandoffError(f"managed target exists with unexpected hash: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(target)
        try:
            shutil.copy2(source, temp)
            if sha256_file(temp) != expected_sha256:
                raise Gate10RegimeHandoffError(f"temporary copy hash mismatch: {source}")
            replace_with_retry(temp, target)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        if sha256_file(target) != expected_sha256:
            raise Gate10RegimeHandoffError(f"promoted target hash mismatch: {target}")

    @staticmethod
    def _replace_atomic_exact(source: Path, target: Path, expected_sha256: str) -> None:
        source = Path(source)
        target = Path(target)
        if not source.is_file() or sha256_file(source) != expected_sha256:
            raise Gate10RegimeHandoffError(f"replacement source hash mismatch: {source}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(target)
        try:
            shutil.copy2(source, temp)
            if sha256_file(temp) != expected_sha256:
                raise Gate10RegimeHandoffError(f"temporary replacement hash mismatch: {source}")
            replace_with_retry(temp, target)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        if sha256_file(target) != expected_sha256:
            raise Gate10RegimeHandoffError(f"live replacement hash mismatch: {target}")

    def _live_paths(self, as_of_date: date) -> dict[str, Path]:
        return {
            "market_sector_snapshot": self.preflight.market_engine.snapshot_path(as_of_date),
            "market_sector_manifest": self.preflight.market_engine.manifest_path(as_of_date),
            "ticker_snapshot": self.preflight.ticker_engine.snapshot_path(as_of_date),
            "ticker_manifest": self.preflight.ticker_engine.manifest_path(as_of_date),
        }

    def _stage_paths(self) -> dict[str, Path]:
        return {
            "market_sector_snapshot": self.stage.market_snapshot_path,
            "market_sector_manifest": self.stage.market_manifest_path,
            "ticker_snapshot": self.stage.ticker_snapshot_path,
            "ticker_manifest": self.stage.ticker_manifest_path,
        }

    def _rollback_paths(self, handoff_id: str) -> dict[str, Path]:
        derived = self.settings.resolved_path(self.settings.data.paths.derived)
        manifests = self.settings.resolved_path(self.settings.data.paths.manifests)
        return {
            "market_sector_snapshot": derived / "regimes" / "_rollback" / handoff_id / "market_sector_snapshot.json",
            "market_sector_manifest": manifests / "regimes" / "_rollback" / handoff_id / "market_sector_manifest.json",
            "ticker_snapshot": derived / "regimes" / "_rollback" / handoff_id / "ticker_snapshot.parquet",
            "ticker_manifest": manifests / "regimes" / "_rollback" / handoff_id / "ticker_manifest.json",
        }

    @staticmethod
    def _write_journal(path: Path, payload: dict[str, Any]) -> None:
        payload["updated_at_utc"] = datetime.now(UTC).isoformat()
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    def _build_plan(self) -> dict[str, Any]:
        validation = self.stage_validator.run()
        if validation.get("pass") is not True:
            raise Gate10RegimeHandoffError("Gate 10-C handoff requires passing staged validation")
        stage_report = _read_json(self.stage.report_path)
        preflight_report = _read_json(self.preflight.report_path)
        if stage_report.get("pass") is not True or preflight_report.get("pass") is not True:
            raise Gate10RegimeHandoffError("Gate 10-C parent evidence is not passing")

        as_of_date = date.fromisoformat(str(stage_report["as_of_date"]))
        live_paths = self._live_paths(as_of_date)
        stage_paths = self._stage_paths()
        live_baseline = preflight_report["live_rollback_baseline"]
        for key in CURRENT_KEYS:
            live = _path_evidence(live_paths[key])
            frozen = live_baseline[key]
            if not live["present"] or live["sha256"] != frozen["sha256"]:
                raise Gate10RegimeHandoffError(f"live rollback baseline changed before handoff: {key}")

        stage_artifacts = stage_report["artifacts"]
        new_hashes = {
            key: str(stage_artifacts[key]["sha256"])
            for key in CURRENT_KEYS
        }
        history_plan = preflight_report["history_publication_plan"]
        for key in HISTORY_KEYS:
            entry = history_plan[key]
            target = Path(str(entry["target_path"]))
            action = str(entry["action"])
            state = classify_history_file_state(
                live_sha256=self._sha_or_none(target),
                expected_sha256=str(entry["source_sha256"]),
            )
            if action == "COPY_NEW" and state != "ABSENT":
                raise Gate10RegimeHandoffError(f"history target changed before handoff: {key}")
            if action == "REUSE_EXACT" and state != "PUBLISHED_EXACT":
                raise Gate10RegimeHandoffError(f"history exact target changed before handoff: {key}")

        handoff_fp = gate10c_handoff_source_fingerprint(
            stage_source_fingerprint=str(stage_report["source_fingerprint"]),
            stage_report_sha256=sha256_file(self.stage.report_path),
            stage_validation_sha256=sha256_file(self.stage_validator.report_path),
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            rollback_baseline=live_baseline,
            staged_artifacts=stage_artifacts,
        )
        handoff_id = handoff_fp[:16]
        rollback_paths = self._rollback_paths(handoff_id)
        return {
            "contract_version": GATE10_REGIME_HANDOFF_CONTRACT_VERSION,
            "role": GATE10_REGIME_HANDOFF_ROLE,
            "source_fingerprint": handoff_fp,
            "handoff_id": handoff_id,
            "as_of_date": as_of_date.isoformat(),
            "stage_source_fingerprint": stage_report["source_fingerprint"],
            "stage_report_sha256": sha256_file(self.stage.report_path),
            "stage_validation_sha256": sha256_file(self.stage_validator.report_path),
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "live_baseline": live_baseline,
            "new_hashes": new_hashes,
            "live_paths": {key: str(path.resolve()) for key, path in live_paths.items()},
            "stage_paths": {key: str(path.resolve()) for key, path in stage_paths.items()},
            "rollback_paths": {key: str(path.resolve()) for key, path in rollback_paths.items()},
            "history_plan": history_plan,
            "status": "PLANNED",
        }

    def _load_or_create_plan(self) -> dict[str, Any]:
        if self.journal_path.is_file():
            journal = _read_json(self.journal_path)
            if journal.get("contract_version") != GATE10_REGIME_HANDOFF_CONTRACT_VERSION:
                raise Gate10RegimeHandoffError("existing Gate 10-C handoff journal has wrong contract")
            return journal
        plan = self._build_plan()
        plan["created_at_utc"] = datetime.now(UTC).isoformat()
        self._write_journal(self.journal_path, plan)
        return plan

    def _promote_current(self, journal: dict[str, Any], key: str) -> None:
        live = Path(str(journal["live_paths"][key]))
        stage = Path(str(journal["stage_paths"][key]))
        rollback = Path(str(journal["rollback_paths"][key]))
        old_sha = str(journal["live_baseline"][key]["sha256"])
        new_sha = str(journal["new_hashes"][key])
        state = classify_current_file_state(
            live_sha256=self._sha_or_none(live),
            old_sha256=old_sha,
            new_sha256=new_sha,
            rollback_sha256=self._sha_or_none(rollback),
        )
        if state == "OLD_LIVE_NO_ROLLBACK":
            self._copy_atomic_exact(live, rollback, old_sha)
            state = "OLD_LIVE_ROLLBACK_READY"
        if state == "OLD_LIVE_ROLLBACK_READY":
            self._replace_atomic_exact(stage, live, new_sha)
            state = "NEW_LIVE_ROLLBACK_READY"
        if state != "NEW_LIVE_ROLLBACK_READY":
            raise Gate10RegimeHandoffError(f"invalid current-file state for {key}: {state}")
        journal.setdefault("current", {})[key] = state
        self._write_journal(self.journal_path, journal)

    def _publish_history(self, journal: dict[str, Any], key: str) -> None:
        plan = journal["history_plan"][key]
        stage_path = self.stage.staged_history_paths()[key]
        target = Path(str(plan["target_path"]))
        expected_sha = str(plan["source_sha256"])
        action = str(plan["action"])
        state = classify_history_file_state(
            live_sha256=self._sha_or_none(target), expected_sha256=expected_sha
        )
        if state == "ABSENT":
            if action != "COPY_NEW":
                raise Gate10RegimeHandoffError(f"history target unexpectedly absent: {key}")
            self._copy_atomic_exact(stage_path, target, expected_sha)
            state = "PUBLISHED_EXACT"
        if state != "PUBLISHED_EXACT":
            raise Gate10RegimeHandoffError(f"invalid history state for {key}: {state}")
        journal.setdefault("history", {})[key] = state
        self._write_journal(self.journal_path, journal)

    def apply(self) -> dict[str, Any]:
        journal = self._load_or_create_plan()
        # If a prior run completed, revalidate the completed disk state rather than
        # trying to derive a new plan against the already-promoted live files.
        for key in CURRENT_KEYS:
            self._promote_current(journal, key)
        for key in HISTORY_KEYS:
            self._publish_history(journal, key)

        as_of_date = date.fromisoformat(str(journal["as_of_date"]))
        live_paths = {key: Path(str(value)) for key, value in journal["live_paths"].items()}
        rollback_paths = {key: Path(str(value)) for key, value in journal["rollback_paths"].items()}
        history_targets = {
            key: Path(str(journal["history_plan"][key]["target_path"])) for key in HISTORY_KEYS
        }
        market_manifest = _read_json(live_paths["market_sector_manifest"])
        ticker_manifest = _read_json(live_paths["ticker_manifest"])
        manifests_native = staged_manifests_are_production_native(
            market_manifest=market_manifest,
            ticker_manifest=ticker_manifest,
            live_market_snapshot=live_paths["market_sector_snapshot"],
            live_ticker_snapshot=live_paths["ticker_snapshot"],
            production_history_paths=history_targets,
        )
        checks = {
            "handoff_contract": journal.get("contract_version") == GATE10_REGIME_HANDOFF_CONTRACT_VERSION,
            "all_current_files_promoted": all(
                self._sha_or_none(live_paths[key]) == journal["new_hashes"][key] for key in CURRENT_KEYS
            ),
            "rollback_preserved": all(
                self._sha_or_none(rollback_paths[key]) == journal["live_baseline"][key]["sha256"]
                for key in CURRENT_KEYS
            ),
            "all_history_files_published": all(
                self._sha_or_none(history_targets[key])
                == journal["history_plan"][key]["source_sha256"]
                for key in HISTORY_KEYS
            ),
            "production_native_manifest_paths": manifests_native,
            "market_snapshot_manifest_hash_exact": market_manifest.get("snapshot_sha256")
            == self._sha_or_none(live_paths["market_sector_snapshot"]),
            "ticker_snapshot_manifest_hash_exact": ticker_manifest.get("snapshot_sha256")
            == self._sha_or_none(live_paths["ticker_snapshot"]),
            "as_of_date_exact": market_manifest.get("as_of_date") == as_of_date.isoformat()
            and ticker_manifest.get("as_of_date") == as_of_date.isoformat(),
        }
        journal["status"] = "COMPLETE" if all(checks.values()) else "INCOMPLETE"
        journal["checks"] = checks
        self._write_journal(self.journal_path, journal)
        report = {
            "contract_version": GATE10_REGIME_HANDOFF_CONTRACT_VERSION,
            "role": GATE10_REGIME_HANDOFF_ROLE,
            "source_fingerprint": journal["source_fingerprint"],
            "handoff_id": journal["handoff_id"],
            "as_of_date": journal["as_of_date"],
            "status": journal["status"],
            "live_paths": journal["live_paths"],
            "rollback_paths": journal["rollback_paths"],
            "history_plan": journal["history_plan"],
            "new_hashes": journal["new_hashes"],
            "live_baseline": journal["live_baseline"],
            "checks": checks,
            "pass": all(checks.values()),
            "journal_path": str(self.journal_path.resolve()),
            "report_path": str(self.report_path.resolve()),
        }
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report

    def rollback(self) -> dict[str, Any]:
        if not self.journal_path.is_file():
            raise Gate10RegimeHandoffError("no Gate 10-C handoff journal exists")
        journal = _read_json(self.journal_path)
        live_paths = {key: Path(str(value)) for key, value in journal["live_paths"].items()}
        rollback_paths = {key: Path(str(value)) for key, value in journal["rollback_paths"].items()}
        for key in reversed(CURRENT_KEYS):
            old_sha = str(journal["live_baseline"][key]["sha256"])
            rollback_path = rollback_paths[key]
            if self._sha_or_none(rollback_path) != old_sha:
                raise Gate10RegimeHandoffError(f"rollback source invalid for {key}")
            self._replace_atomic_exact(rollback_path, live_paths[key], old_sha)
        for key in HISTORY_KEYS:
            plan = journal["history_plan"][key]
            target = Path(str(plan["target_path"]))
            if str(plan["action"]) == "COPY_NEW" and target.exists():
                if self._sha_or_none(target) != str(plan["source_sha256"]):
                    raise Gate10RegimeHandoffError(f"refusing to remove modified history target: {key}")
                target.unlink()
        journal["status"] = "ROLLED_BACK"
        self._write_journal(self.journal_path, journal)
        return {"status": "ROLLED_BACK", "handoff_id": journal["handoff_id"]}


class HistoricalBackfillRegimeHandoffValidator:
    """Independently re-prove live production and rollback after Gate 10-C handoff."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.handoff = HistoricalBackfillRegimeHandoff(settings)
        self.stage = self.handoff.stage
        self.preflight = self.handoff.preflight
        self.report_path = self.preflight.root / "gate10c_handoff_validation_report.json"

    def run(self) -> dict[str, Any]:
        if not self.handoff.report_path.is_file() or not self.handoff.journal_path.is_file():
            raise FileNotFoundError("Gate 10-C handoff report/journal is missing")
        writer = _read_json(self.handoff.report_path)
        journal = _read_json(self.handoff.journal_path)
        stage_report = _read_json(self.stage.report_path)
        stage_validation = _read_json(self.handoff.stage_validator.report_path)
        preflight = _read_json(self.preflight.report_path)

        expected_fp = gate10c_handoff_source_fingerprint(
            stage_source_fingerprint=str(stage_report["source_fingerprint"]),
            stage_report_sha256=sha256_file(self.stage.report_path),
            stage_validation_sha256=sha256_file(self.handoff.stage_validator.report_path),
            preflight_source_fingerprint=str(preflight["source_fingerprint"]),
            rollback_baseline=preflight["live_rollback_baseline"],
            staged_artifacts=stage_report["artifacts"],
        )
        as_of_date = date.fromisoformat(str(writer["as_of_date"]))
        live_paths = self.handoff._live_paths(as_of_date)
        rollback_paths = self.handoff._rollback_paths(str(writer["handoff_id"]))
        history_paths = self.preflight.market_engine.history_paths(as_of_date)
        market_manifest = _read_json(live_paths["market_sector_manifest"])
        ticker_manifest = _read_json(live_paths["ticker_manifest"])

        live_failures = sum(
            self.handoff._sha_or_none(live_paths[key]) != writer["new_hashes"][key]
            for key in CURRENT_KEYS
        )
        rollback_failures = sum(
            self.handoff._sha_or_none(rollback_paths[key]) != writer["live_baseline"][key]["sha256"]
            for key in CURRENT_KEYS
        )
        history_failures = sum(
            self.handoff._sha_or_none(history_paths[key])
            != writer["history_plan"][key]["source_sha256"]
            for key in HISTORY_KEYS
        )
        manifests_native = staged_manifests_are_production_native(
            market_manifest=market_manifest,
            ticker_manifest=ticker_manifest,
            live_market_snapshot=live_paths["market_sector_snapshot"],
            live_ticker_snapshot=live_paths["ticker_snapshot"],
            production_history_paths=history_paths,
        )
        market_dependency, _ = self.preflight.market_engine._dependency(as_of_date=as_of_date)
        ticker_dependency, _ = self.preflight.ticker_engine._dependency(as_of_date)

        checks = {
            "validation_contract": True,
            "writer_contract": writer.get("contract_version") == GATE10_REGIME_HANDOFF_CONTRACT_VERSION,
            "writer_report_pass": writer.get("pass") is True,
            "journal_complete": journal.get("status") == "COMPLETE",
            "handoff_source_fingerprint_recomputed": writer.get("source_fingerprint") == expected_fp,
            "journal_source_fingerprint_exact": journal.get("source_fingerprint") == expected_fp,
            "parent_stage_report_pass": stage_report.get("pass") is True,
            "parent_stage_validation_pass": stage_validation.get("pass") is True,
            "live_current_hashes_exact": live_failures == 0,
            "rollback_hashes_exact": rollback_failures == 0,
            "history_hashes_exact": history_failures == 0,
            "production_native_manifest_paths": manifests_native,
            "market_dependency_current": market_manifest.get("dependency_fingerprint") == market_dependency,
            "ticker_dependency_current": ticker_manifest.get("dependency_fingerprint") == ticker_dependency,
            "market_snapshot_manifest_hash_exact": market_manifest.get("snapshot_sha256")
            == self.handoff._sha_or_none(live_paths["market_sector_snapshot"]),
            "ticker_snapshot_manifest_hash_exact": ticker_manifest.get("snapshot_sha256")
            == self.handoff._sha_or_none(live_paths["ticker_snapshot"]),
            "history_dataset_version_exact": REGIME_HISTORY_DATASET_VERSION == "split_origin_v1",
            "rollback_available": rollback_failures == 0,
        }
        report = {
            "contract_version": GATE10_REGIME_HANDOFF_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "handoff_source_fingerprint": expected_fp,
            "handoff_id": writer["handoff_id"],
            "as_of_date": writer["as_of_date"],
            "live_failures": int(live_failures),
            "rollback_failures": int(rollback_failures),
            "history_failures": int(history_failures),
            "market_dependency": market_dependency,
            "ticker_dependency": ticker_dependency,
            "checks": checks,
            "pass": all(checks.values()),
            "writer_report_path": str(self.handoff.report_path.resolve()),
            "journal_path": str(self.handoff.journal_path.resolve()),
            "report_path": str(self.report_path.resolve()),
        }
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
