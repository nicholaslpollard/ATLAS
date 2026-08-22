from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.features.partition_store import sha256_file

from .historical_backfill_regime_replay_build import HistoricalBackfillRegimeReplayBuilder
from .historical_backfill_regime_replay_validation import (
    GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION,
)
from .split_origin_policy import (
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    REGIME_HISTORY_DATASET_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)
from .split_origin_state_engine import SplitOriginRegimeStateEngine
from .ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    TickerStateEngine,
)


GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION = (
    "historical-backfill-regime-promotion-preflight-v1-v2-writer-rollback-history-publication"
)
GATE10_REGIME_PROMOTION_ROLE = "READ_ONLY_PRODUCTION_REGIME_PROMOTION_PREFLIGHT"


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {path}") from exc


def _path_evidence(path: Path) -> dict[str, object]:
    return {
        "path": str(path.resolve()),
        "present": path.is_file(),
        "sha256": sha256_file(path) if path.is_file() else None,
        "bytes": path.stat().st_size if path.is_file() else 0,
    }


def _classify_new_target(path: Path, expected_sha256: str) -> str:
    if not path.exists():
        return "COPY_NEW"
    if path.is_file() and sha256_file(path) == expected_sha256:
        return "REUSE_EXACT"
    return "FAIL_UNMANAGED_TARGET"


def _manifest_rewrite_is_path_only(
    candidate: dict[str, Any],
    planned: dict[str, Any],
    *,
    market_sector: bool,
) -> bool:
    left = json.loads(json.dumps(candidate))
    right = json.loads(json.dumps(planned))
    left.pop("generated_at_utc", None)
    right.pop("generated_at_utc", None)
    left.pop("snapshot_path", None)
    right.pop("snapshot_path", None)
    if market_sector:
        left_history = left.pop("history_files", {})
        right_history = right.pop("history_files", {})
        if set(left_history) != set(right_history):
            return False
        for key in left_history:
            if left_history[key].get("sha256") != right_history[key].get("sha256"):
                return False
    return left == right


class HistoricalBackfillRegimePromotionPreflight:
    """Gate 10-C read-only freeze of the live regime promotion boundary."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.builder = HistoricalBackfillRegimeReplayBuilder(settings)
        self.market_engine = SplitOriginRegimeStateEngine(settings)
        self.ticker_engine = TickerStateEngine(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = self.builder.root / "promotion" / "v1"
        self.report_path = self.root / "gate10c_preflight_report.json"
        self.production_write_count = 0
        self.derived_root = derived

    def _load_parent_reports(self) -> tuple[dict[str, Any], dict[str, Any]]:
        validation_path = self.builder.candidate_root / "gate10_validation_report.json"
        if not self.builder.report_path.is_file() or not validation_path.is_file():
            raise FileNotFoundError("Gate 10-C requires accepted Gate 10-B builder and validation reports")
        return _read_json(self.builder.report_path), _read_json(validation_path)

    @staticmethod
    def _planned_market_manifest(
        candidate: dict[str, Any],
        *,
        snapshot_path: Path,
        history_paths: dict[str, Path],
    ) -> dict[str, Any]:
        planned = json.loads(json.dumps(candidate))
        planned["snapshot_path"] = str(snapshot_path.resolve())
        for name, path in history_paths.items():
            planned["history_files"][name]["path"] = str(path.resolve())
        return planned

    @staticmethod
    def _planned_ticker_manifest(candidate: dict[str, Any], *, snapshot_path: Path) -> dict[str, Any]:
        planned = json.loads(json.dumps(candidate))
        planned["snapshot_path"] = str(snapshot_path.resolve())
        return planned

    def run(self) -> dict[str, Any]:
        builder_report, validation_report = self._load_parent_reports()
        if builder_report.get("pass") is not True or validation_report.get("pass") is not True:
            raise ValueError("Gate 10-C requires Gate 10-B builder and independent validation PASS")
        as_of_text = str(builder_report["as_of_date"])
        from datetime import date

        as_of_date = date.fromisoformat(as_of_text)
        if validation_report.get("builder_source_fingerprint") != builder_report.get("source_fingerprint"):
            raise ValueError("Gate 10-B builder/validator fingerprint disagreement")
        if validation_report.get("contract_version") != GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION:
            raise ValueError("Gate 10-B validation contract is not current")

        candidate_market_snapshot = self.builder.market_sector_snapshot_path
        candidate_market_manifest_path = self.builder.market_sector_manifest_path
        candidate_ticker_snapshot = self.builder.ticker_snapshot_path
        candidate_ticker_manifest_path = self.builder.ticker_manifest_path
        candidate_market_manifest = _read_json(candidate_market_manifest_path)
        candidate_ticker_manifest = _read_json(candidate_ticker_manifest_path)

        live_market_snapshot = self.market_engine.snapshot_path(as_of_date)
        live_market_manifest = self.market_engine.manifest_path(as_of_date)
        live_ticker_snapshot = self.ticker_engine.snapshot_path(as_of_date)
        live_ticker_manifest = self.ticker_engine.manifest_path(as_of_date)
        live_paths = {
            "market_sector_snapshot": live_market_snapshot,
            "market_sector_manifest": live_market_manifest,
            "ticker_snapshot": live_ticker_snapshot,
            "ticker_manifest": live_ticker_manifest,
        }
        live_baseline = {key: _path_evidence(path) for key, path in live_paths.items()}

        frozen = builder_report["production_baseline_before"]
        baseline_matches_builder = all(
            bool(live_baseline[key]["present"]) == bool(frozen[key]["present"])
            and live_baseline[key]["sha256"] == frozen[key]["sha256"]
            for key in live_paths
        )

        history_targets = self.market_engine.history_paths(as_of_date)
        candidate_history = builder_report["market_sector"]["history_files"]
        history_plan: dict[str, dict[str, object]] = {}
        for name, target in history_targets.items():
            expected_sha = str(candidate_history[name]["sha256"])
            history_plan[name] = {
                "source_path": str(Path(str(candidate_history[name]["path"])).resolve()),
                "source_sha256": expected_sha,
                "target_path": str(target.resolve()),
                "action": _classify_new_target(target, expected_sha),
            }

        planned_market_manifest = self._planned_market_manifest(
            candidate_market_manifest,
            snapshot_path=live_market_snapshot,
            history_paths=history_targets,
        )
        planned_ticker_manifest = self._planned_ticker_manifest(
            candidate_ticker_manifest,
            snapshot_path=live_ticker_snapshot,
        )

        source_count, source_lineage = self.market_engine._source_lineage(as_of_date)
        market_dependency, market_dependency_payload = self.market_engine._dependency(
            as_of_date=as_of_date,
            source_manifest_count=source_count,
            source_lineage=source_lineage,
        )
        ticker_dependency, _ticker_dependency_payload = self.ticker_engine._dependency(as_of_date)

        candidate_hash_checks = {
            "market_snapshot": sha256_file(candidate_market_snapshot)
            == str(candidate_market_manifest["snapshot_sha256"]),
            "ticker_snapshot": sha256_file(candidate_ticker_snapshot)
            == str(candidate_ticker_manifest["snapshot_sha256"]),
            "market_manifest": sha256_file(candidate_market_manifest_path)
            == str(builder_report["market_sector"]["manifest_sha256"]),
            "ticker_manifest": sha256_file(candidate_ticker_manifest_path)
            == str(builder_report["ticker"]["manifest_sha256"]),
        }
        for name, entry in candidate_history.items():
            candidate_hash_checks[f"history_{name}"] = (
                sha256_file(Path(str(entry["path"]))) == str(entry["sha256"])
            )

        current_replacements = {
            "market_sector_snapshot": {
                "action": "REPLACE_PROTECTED_BASELINE",
                "source_sha256": sha256_file(candidate_market_snapshot),
                "target_sha256": live_baseline["market_sector_snapshot"]["sha256"],
            },
            "market_sector_manifest": {
                "action": "REPLACE_PROTECTED_BASELINE",
                "planned_payload_sha256": _stable_hash(planned_market_manifest),
                "target_sha256": live_baseline["market_sector_manifest"]["sha256"],
            },
            "ticker_snapshot": {
                "action": "REPLACE_PROTECTED_BASELINE",
                "source_sha256": sha256_file(candidate_ticker_snapshot),
                "target_sha256": live_baseline["ticker_snapshot"]["sha256"],
            },
            "ticker_manifest": {
                "action": "REPLACE_PROTECTED_BASELINE",
                "planned_payload_sha256": _stable_hash(planned_ticker_manifest),
                "target_sha256": live_baseline["ticker_manifest"]["sha256"],
            },
        }

        rollback_bytes = sum(int(entry["bytes"]) for entry in live_baseline.values())
        candidate_bytes = sum(
            path.stat().st_size
            for path in (
                candidate_market_snapshot,
                candidate_ticker_snapshot,
                *(Path(str(entry["path"])) for entry in candidate_history.values()),
            )
        )
        candidate_bytes += len(json.dumps(planned_market_manifest, sort_keys=True).encode("utf-8"))
        candidate_bytes += len(json.dumps(planned_ticker_manifest, sort_keys=True).encode("utf-8"))

        checks = {
            "preflight_contract": True,
            "gate10b_builder_pass": builder_report.get("pass") is True,
            "gate10b_validation_pass": validation_report.get("pass") is True,
            "gate10b_builder_fingerprint_exact": validation_report.get("builder_source_fingerprint")
            == builder_report.get("source_fingerprint"),
            "split_origin_policy_exact": candidate_market_manifest.get("split_origin_policy_version")
            == SPLIT_ORIGIN_POLICY_VERSION,
            "market_sector_origin_exact": candidate_market_manifest.get("history_origin_date")
            == MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_origin_exact": candidate_market_manifest.get("ticker_history_origin_date")
            == TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "production_market_writer_v2": (
                candidate_market_manifest.get("manifest_version") == MARKET_SECTOR_MANIFEST_VERSION
                and candidate_market_manifest.get("state_policy_contract_version")
                == MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION
                and candidate_market_manifest.get("snapshot_contract_version")
                == MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION
            ),
            "production_market_dependency_matches_candidate": market_dependency
            == candidate_market_manifest.get("dependency_fingerprint"),
            "production_market_source_count_matches_candidate": source_count
            == int(candidate_market_manifest.get("source_manifest_count", -1)),
            "production_ticker_dependency_matches_candidate": ticker_dependency
            == candidate_ticker_manifest.get("dependency_fingerprint"),
            "ticker_manifest_contract_retained": candidate_ticker_manifest.get("manifest_version")
            == TICKER_STATE_MANIFEST_VERSION,
            "ticker_state_policy_retained": candidate_ticker_manifest.get("state_policy_contract_version")
            == TICKER_STATE_POLICY_CONTRACT_VERSION,
            "ticker_snapshot_contract_retained": candidate_ticker_manifest.get("snapshot_contract_version")
            == TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
            "candidate_hashes_exact": all(candidate_hash_checks.values()),
            "production_baseline_unchanged_from_gate10b": baseline_matches_builder,
            "market_manifest_rewrite_path_only": _manifest_rewrite_is_path_only(
                candidate_market_manifest, planned_market_manifest, market_sector=True
            ),
            "ticker_manifest_rewrite_path_only": _manifest_rewrite_is_path_only(
                candidate_ticker_manifest, planned_ticker_manifest, market_sector=False
            ),
            "history_targets_managed": all(
                entry["action"] in {"COPY_NEW", "REUSE_EXACT"} for entry in history_plan.values()
            ),
            "history_dataset_version_exact": REGIME_HISTORY_DATASET_VERSION == "split_origin_v1",
            "production_regime_writes_zero": self.production_write_count == 0,
        }

        fingerprint_payload = {
            "contract_version": GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "builder_source_fingerprint": builder_report["source_fingerprint"],
            "validation_report_sha256": sha256_file(
                self.builder.candidate_root / "gate10_validation_report.json"
            ),
            "as_of_date": as_of_text,
            "live_baseline": live_baseline,
            "history_plan": history_plan,
            "planned_market_manifest": planned_market_manifest,
            "planned_ticker_manifest": planned_ticker_manifest,
            "market_dependency": market_dependency,
            "ticker_dependency": ticker_dependency,
        }
        source_fingerprint = _stable_hash(fingerprint_payload)
        report = {
            "contract_version": GATE10_REGIME_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "role": GATE10_REGIME_PROMOTION_ROLE,
            "source_fingerprint": source_fingerprint,
            "builder_source_fingerprint": builder_report["source_fingerprint"],
            "validation_contract_version": validation_report["contract_version"],
            "as_of_date": as_of_text,
            "split_origin_policy": SPLIT_ORIGIN_POLICY_VERSION,
            "market_sector_history_origin": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_history_origin": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "production_market_dependency": market_dependency,
            "production_market_dependency_payload": market_dependency_payload,
            "production_ticker_dependency": ticker_dependency,
            "live_rollback_baseline": live_baseline,
            "rollback_footprint_bytes": rollback_bytes,
            "candidate_promotion_footprint_bytes": candidate_bytes,
            "current_replacement_plan": current_replacements,
            "history_publication_plan": history_plan,
            "planned_market_manifest": planned_market_manifest,
            "planned_ticker_manifest": planned_ticker_manifest,
            "candidate_hash_checks": candidate_hash_checks,
            "checks": checks,
            "production_regime_writes": self.production_write_count,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "pass": all(checks.values()),
        }
        self.root.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        report["report_path"] = str(self.report_path.resolve())
        return report
