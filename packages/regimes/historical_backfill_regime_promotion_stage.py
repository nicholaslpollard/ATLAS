from __future__ import annotations

import json
import shutil
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .historical_backfill_regime_promotion import (
    GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
    HistoricalBackfillRegimePromotionPreflight,
    _path_evidence,
    _read_json,
    _stable_hash,
)
from .split_origin_policy import (
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    REGIME_HISTORY_DATASET_VERSION,
)
from .ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
)


GATE10_REGIME_PROMOTION_STAGE_CONTRACT_VERSION = (
    "historical-backfill-regime-promotion-stage-v1-production-native-bundle"
)
GATE10_REGIME_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-regime-promotion-stage-validation-v1-independent-disk-proof"
)
GATE10_REGIME_PROMOTION_STAGE_ROLE = "PRODUCTION_REGIME_PROMOTION_STAGED_NOT_LIVE"


def gate10c_stage_source_fingerprint(
    *,
    preflight_source_fingerprint: str,
    builder_source_fingerprint: str,
    market_dependency: str,
    ticker_dependency: str,
) -> str:
    return _stable_hash(
        {
            "contract_version": GATE10_REGIME_PROMOTION_STAGE_CONTRACT_VERSION,
            "preflight_contract_version": GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "preflight_source_fingerprint": preflight_source_fingerprint,
            "builder_source_fingerprint": builder_source_fingerprint,
            "market_dependency": market_dependency,
            "ticker_dependency": ticker_dependency,
            "history_dataset_version": REGIME_HISTORY_DATASET_VERSION,
        }
    )


def production_history_target_unchanged(
    *,
    action: str,
    target: Path,
    expected_sha256: str,
) -> bool:
    target = Path(target)
    if action == "COPY_NEW":
        return not target.exists()
    if action == "REUSE_EXACT":
        return target.is_file() and sha256_file(target) == expected_sha256
    return False


def staged_manifests_are_production_native(
    *,
    market_manifest: dict[str, Any],
    ticker_manifest: dict[str, Any],
    live_market_snapshot: Path,
    live_ticker_snapshot: Path,
    production_history_paths: dict[str, Path],
) -> bool:
    if Path(str(market_manifest.get("snapshot_path", ""))).resolve() != live_market_snapshot.resolve():
        return False
    if Path(str(ticker_manifest.get("snapshot_path", ""))).resolve() != live_ticker_snapshot.resolve():
        return False
    history = market_manifest.get("history_files")
    if not isinstance(history, dict) or set(history) != set(production_history_paths):
        return False
    for name, target in production_history_paths.items():
        entry = history.get(name)
        if not isinstance(entry, dict):
            return False
        if Path(str(entry.get("path", ""))).resolve() != target.resolve():
            return False
    return True


class HistoricalBackfillRegimePromotionStage:
    """Build the exact Gate 10-C production-native bundle outside live regime paths."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.preflight = HistoricalBackfillRegimePromotionPreflight(settings)
        self.builder = self.preflight.builder
        self.root = self.preflight.root / "stage"
        self.current_root = self.root / "current"
        self.history_root = self.root / "history" / REGIME_HISTORY_DATASET_VERSION
        self.market_snapshot_path = self.current_root / "market_sector" / "snapshot.json"
        self.market_manifest_path = self.current_root / "market_sector" / "manifest.json"
        self.ticker_snapshot_path = self.current_root / "ticker" / "part-000.parquet"
        self.ticker_manifest_path = self.current_root / "ticker" / "manifest.json"
        self.report_path = self.preflight.root / "gate10c_stage_report.json"

    def staged_history_paths(self) -> dict[str, Path]:
        return {
            "market_raw": self.history_root / "market_raw.parquet",
            "market_effective": self.history_root / "market_effective.parquet",
            "sector_raw": self.history_root / "sector_raw.parquet",
            "sector_effective": self.history_root / "sector_effective.parquet",
        }

    @staticmethod
    def _copy_exact(source: Path, target: Path, expected_sha256: str) -> bool:
        source = Path(source)
        target = Path(target)
        if not source.is_file() or sha256_file(source) != expected_sha256:
            raise RuntimeError(f"Gate 10-C stage source hash mismatch: {source}")
        if target.is_file() and sha256_file(target) == expected_sha256:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(target)
        try:
            shutil.copy2(source, temp)
            if sha256_file(temp) != expected_sha256:
                raise RuntimeError(f"Gate 10-C stage temporary copy hash mismatch: {source}")
            replace_with_retry(temp, target)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        if sha256_file(target) != expected_sha256:
            raise RuntimeError(f"Gate 10-C staged target hash mismatch: {target}")
        return True

    @staticmethod
    def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    @staticmethod
    def _live_baseline_current(preflight_report: dict[str, Any]) -> dict[str, dict[str, object]]:
        return {
            key: _path_evidence(Path(str(entry["path"])))
            for key, entry in preflight_report["live_rollback_baseline"].items()
        }

    @staticmethod
    def _history_targets_unchanged(preflight_report: dict[str, Any]) -> bool:
        return all(
            production_history_target_unchanged(
                action=str(entry["action"]),
                target=Path(str(entry["target_path"])),
                expected_sha256=str(entry["source_sha256"]),
            )
            for entry in preflight_report["history_publication_plan"].values()
        )

    def run(self) -> dict[str, Any]:
        preflight_report = self.preflight.run()
        if preflight_report.get("pass") is not True:
            raise RuntimeError("Gate 10-C staging requires a current passing promotion preflight")

        stage_fingerprint = gate10c_stage_source_fingerprint(
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            builder_source_fingerprint=str(preflight_report["builder_source_fingerprint"]),
            market_dependency=str(preflight_report["production_market_dependency"]),
            ticker_dependency=str(preflight_report["production_ticker_dependency"]),
        )
        as_of_date = date.fromisoformat(str(preflight_report["as_of_date"]))
        production_history_paths = self.preflight.market_engine.history_paths(as_of_date)
        live_market_snapshot = self.preflight.market_engine.snapshot_path(as_of_date)
        live_ticker_snapshot = self.preflight.ticker_engine.snapshot_path(as_of_date)

        candidate_market_manifest = _read_json(self.builder.market_sector_manifest_path)
        candidate_ticker_manifest = _read_json(self.builder.ticker_manifest_path)
        planned_market_manifest = dict(preflight_report["planned_market_manifest"])
        planned_ticker_manifest = dict(preflight_report["planned_ticker_manifest"])

        copied = 0
        reused = 0
        market_snapshot_sha = str(candidate_market_manifest["snapshot_sha256"])
        ticker_snapshot_sha = str(candidate_ticker_manifest["snapshot_sha256"])
        copied_now = self._copy_exact(
            self.builder.market_sector_snapshot_path,
            self.market_snapshot_path,
            market_snapshot_sha,
        )
        copied += int(copied_now)
        reused += int(not copied_now)
        copied_now = self._copy_exact(
            self.builder.ticker_snapshot_path,
            self.ticker_snapshot_path,
            ticker_snapshot_sha,
        )
        copied += int(copied_now)
        reused += int(not copied_now)

        staged_history = self.staged_history_paths()
        history_artifacts: dict[str, dict[str, object]] = {}
        for name, plan in preflight_report["history_publication_plan"].items():
            expected_sha = str(plan["source_sha256"])
            source = Path(str(plan["source_path"]))
            target = staged_history[name]
            copied_now = self._copy_exact(source, target, expected_sha)
            copied += int(copied_now)
            reused += int(not copied_now)
            history_artifacts[name] = {
                "path": str(target.resolve()),
                "sha256": sha256_file(target),
                "production_target_path": str(Path(str(plan["target_path"])).resolve()),
                "production_action": str(plan["action"]),
            }

        self._write_manifest(self.market_manifest_path, planned_market_manifest)
        self._write_manifest(self.ticker_manifest_path, planned_ticker_manifest)

        live_baseline_after = self._live_baseline_current(preflight_report)
        baseline_unchanged = live_baseline_after == preflight_report["live_rollback_baseline"]
        history_targets_unchanged = self._history_targets_unchanged(preflight_report)
        manifests_native = staged_manifests_are_production_native(
            market_manifest=planned_market_manifest,
            ticker_manifest=planned_ticker_manifest,
            live_market_snapshot=live_market_snapshot,
            live_ticker_snapshot=live_ticker_snapshot,
            production_history_paths=production_history_paths,
        )

        staged_market_manifest = _read_json(self.market_manifest_path)
        staged_ticker_manifest = _read_json(self.ticker_manifest_path)
        derived = self.settings.resolved_path(self.settings.data.paths.derived)
        live_regime_root = (derived / "regimes").resolve()
        stage_isolated = not self.root.resolve().is_relative_to(live_regime_root)

        artifacts = {
            "market_sector_snapshot": _path_evidence(self.market_snapshot_path),
            "market_sector_manifest": _path_evidence(self.market_manifest_path),
            "ticker_snapshot": _path_evidence(self.ticker_snapshot_path),
            "ticker_manifest": _path_evidence(self.ticker_manifest_path),
            "history": history_artifacts,
        }
        staged_bytes = sum(path.stat().st_size for path in self.root.glob("**/*") if path.is_file())
        checks = {
            "stage_contract": True,
            "preflight_pass": preflight_report.get("pass") is True,
            "preflight_fingerprint_current": preflight_report.get("source_fingerprint")
            == preflight_report.get("source_fingerprint"),
            "market_snapshot_hash_exact": sha256_file(self.market_snapshot_path) == market_snapshot_sha,
            "ticker_snapshot_hash_exact": sha256_file(self.ticker_snapshot_path) == ticker_snapshot_sha,
            "market_manifest_payload_exact": staged_market_manifest == planned_market_manifest,
            "ticker_manifest_payload_exact": staged_ticker_manifest == planned_ticker_manifest,
            "market_manifest_contract_exact": staged_market_manifest.get("manifest_version")
            == MARKET_SECTOR_MANIFEST_VERSION
            and staged_market_manifest.get("snapshot_contract_version")
            == MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION
            and staged_market_manifest.get("state_policy_contract_version")
            == MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "ticker_manifest_contract_exact": staged_ticker_manifest.get("manifest_version")
            == TICKER_STATE_MANIFEST_VERSION
            and staged_ticker_manifest.get("snapshot_contract_version")
            == TICKER_STATE_SNAPSHOT_CONTRACT_VERSION
            and staged_ticker_manifest.get("state_policy_contract_version")
            == TICKER_STATE_POLICY_CONTRACT_VERSION,
            "history_hashes_exact": all(
                entry["sha256"]
                == preflight_report["history_publication_plan"][name]["source_sha256"]
                for name, entry in history_artifacts.items()
            ),
            "production_native_manifest_paths": manifests_native,
            "production_baseline_unchanged": baseline_unchanged,
            "production_history_targets_unchanged": history_targets_unchanged,
            "stage_namespace_isolated": stage_isolated,
            "production_regime_writes_zero": True,
        }
        report = {
            "contract_version": GATE10_REGIME_PROMOTION_STAGE_CONTRACT_VERSION,
            "role": GATE10_REGIME_PROMOTION_STAGE_ROLE,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": stage_fingerprint,
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "builder_source_fingerprint": preflight_report["builder_source_fingerprint"],
            "as_of_date": preflight_report["as_of_date"],
            "market_dependency": preflight_report["production_market_dependency"],
            "ticker_dependency": preflight_report["production_ticker_dependency"],
            "copied_files": copied,
            "reused_files": reused,
            "staged_artifact_count": 8,
            "staged_bytes": staged_bytes,
            "artifacts": artifacts,
            "planned_market_manifest": planned_market_manifest,
            "planned_ticker_manifest": planned_ticker_manifest,
            "live_rollback_baseline": preflight_report["live_rollback_baseline"],
            "history_publication_plan": preflight_report["history_publication_plan"],
            "checks": checks,
            "production_regime_writes": 0,
            "pass": all(checks.values()),
            "report_path": str(self.report_path.resolve()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report


class HistoricalBackfillRegimePromotionStageValidator:
    """Independently reopen the staged Gate 10-C bundle and the untouched live boundary."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.stage = HistoricalBackfillRegimePromotionStage(settings)
        self.preflight = self.stage.preflight
        self.builder = self.stage.builder
        self.report_path = self.preflight.root / "gate10c_stage_validation_report.json"

    def run(self) -> dict[str, Any]:
        preflight_report = self.preflight.run()
        if preflight_report.get("pass") is not True:
            raise RuntimeError("Gate 10-C staged validation requires a current passing preflight")
        if not self.stage.report_path.is_file():
            raise FileNotFoundError(f"Gate 10-C stage report missing: {self.stage.report_path}")
        stored = _read_json(self.stage.report_path)
        expected_stage_fingerprint = gate10c_stage_source_fingerprint(
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            builder_source_fingerprint=str(preflight_report["builder_source_fingerprint"]),
            market_dependency=str(preflight_report["production_market_dependency"]),
            ticker_dependency=str(preflight_report["production_ticker_dependency"]),
        )
        as_of_date = date.fromisoformat(str(preflight_report["as_of_date"]))
        production_history_paths = self.preflight.market_engine.history_paths(as_of_date)
        live_market_snapshot = self.preflight.market_engine.snapshot_path(as_of_date)
        live_ticker_snapshot = self.preflight.ticker_engine.snapshot_path(as_of_date)

        market_manifest = _read_json(self.stage.market_manifest_path)
        ticker_manifest = _read_json(self.stage.ticker_manifest_path)
        candidate_market_manifest = _read_json(self.builder.market_sector_manifest_path)
        candidate_ticker_manifest = _read_json(self.builder.ticker_manifest_path)

        history_failures = 0
        for name, plan in preflight_report["history_publication_plan"].items():
            staged = self.stage.staged_history_paths()[name]
            if not staged.is_file() or sha256_file(staged) != str(plan["source_sha256"]):
                history_failures += 1

        live_baseline_now = self.stage._live_baseline_current(preflight_report)
        baseline_unchanged = live_baseline_now == preflight_report["live_rollback_baseline"]
        history_targets_unchanged = self.stage._history_targets_unchanged(preflight_report)
        manifests_native = staged_manifests_are_production_native(
            market_manifest=market_manifest,
            ticker_manifest=ticker_manifest,
            live_market_snapshot=live_market_snapshot,
            live_ticker_snapshot=live_ticker_snapshot,
            production_history_paths=production_history_paths,
        )

        checks = {
            "validation_contract": True,
            "preflight_current": preflight_report.get("pass") is True,
            "stage_report_pass": stored.get("pass") is True,
            "stage_source_fingerprint_current": stored.get("source_fingerprint")
            == expected_stage_fingerprint,
            "stage_preflight_fingerprint_current": stored.get("preflight_source_fingerprint")
            == preflight_report.get("source_fingerprint"),
            "market_snapshot_candidate_hash_exact": self.stage.market_snapshot_path.is_file()
            and sha256_file(self.stage.market_snapshot_path)
            == str(candidate_market_manifest["snapshot_sha256"]),
            "ticker_snapshot_candidate_hash_exact": self.stage.ticker_snapshot_path.is_file()
            and sha256_file(self.stage.ticker_snapshot_path)
            == str(candidate_ticker_manifest["snapshot_sha256"]),
            "market_manifest_payload_exact": market_manifest
            == preflight_report["planned_market_manifest"],
            "ticker_manifest_payload_exact": ticker_manifest
            == preflight_report["planned_ticker_manifest"],
            "production_native_manifest_paths": manifests_native,
            "history_hash_failures_zero": history_failures == 0,
            "production_baseline_unchanged": baseline_unchanged,
            "production_history_targets_unchanged": history_targets_unchanged,
            "production_regime_writes_zero": True,
        }
        report = {
            "contract_version": GATE10_REGIME_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "stage_source_fingerprint": expected_stage_fingerprint,
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "as_of_date": preflight_report["as_of_date"],
            "history_hash_failures": history_failures,
            "live_rollback_baseline": live_baseline_now,
            "checks": checks,
            "production_regime_writes": 0,
            "pass": all(checks.values()),
            "stage_report_path": str(self.stage.report_path.resolve()),
            "report_path": str(self.report_path.resolve()),
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
