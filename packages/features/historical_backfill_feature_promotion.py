from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_TARGET_SESSION
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.data.paths import MarketDataPaths
from packages.features.historical_backfill_replay_build import (
    GATE9_DAILY_REPLAY_CONTRACT_VERSION,
    HistoricalBackfillDailyFeatureReplay,
)
from packages.features.historical_backfill_replay_validation_v2 import (
    GATE9_DAILY_REPLAY_VALIDATION_V2_CONTRACT_VERSION,
    HistoricalBackfillDailyFeatureReplayValidatorV2,
)


GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION = (
    "historical-backfill-feature-promotion-preflight-v1-full-daily-replay-protected-rollback"
)
GATE9_FEATURE_PROMOTION_ROLE = "PRODUCTION_DAILY_FEATURE_REPLAY_PROMOTION_PENDING"

COPY_NEW = "COPY_NEW"
REUSE_EXACT = "REUSE_EXACT"
REPLACE_PROTECTED_BASELINE = "REPLACE_PROTECTED_BASELINE"
FAIL_UNMANAGED_TARGET = "FAIL_UNMANAGED_TARGET"


def feature_promotion_action(
    *,
    target_exists: bool,
    target_in_locked_baseline: bool,
    target_sha256: str | None,
    candidate_sha256: str,
) -> str:
    """Classify a Gate 9-C feature target without allowing untracked replacement."""

    if not target_exists:
        return COPY_NEW
    if target_sha256 == candidate_sha256:
        return REUSE_EXACT
    if target_in_locked_baseline:
        return REPLACE_PROTECTED_BASELINE
    return FAIL_UNMANAGED_TARGET


def feature_inventory_fingerprint(rows: list[dict[str, object]]) -> str:
    stable_rows = [
        {
            "session_date": str(row["session_date"]),
            "feature_sha256": str(row["feature_sha256"]),
            "source_sha256": str(row["source_sha256"]),
            "manifest_sha256": str(row["manifest_sha256"]),
            "row_count": int(row["row_count"]),
            "symbol_count": int(row["symbol_count"]),
        }
        for row in rows
    ]
    stable_rows.sort(key=lambda item: item["session_date"])
    return stable_source_fingerprint({"feature_sessions": stable_rows})


def feature_promotion_source_fingerprint(
    *,
    replay_source_fingerprint: str,
    candidate_inventory_fingerprint: str,
    production_baseline_fingerprint: str,
    candidate_current_state_sha256: str,
    candidate_current_state_fingerprint: str,
    candidate_year_checkpoint_fingerprint: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "role": GATE9_FEATURE_PROMOTION_ROLE,
            "gate9_replay_contract": GATE9_DAILY_REPLAY_CONTRACT_VERSION,
            "gate9_validation_contract": GATE9_DAILY_REPLAY_VALIDATION_V2_CONTRACT_VERSION,
            "replay_source_fingerprint": replay_source_fingerprint,
            "candidate_inventory_fingerprint": candidate_inventory_fingerprint,
            "production_baseline_fingerprint": production_baseline_fingerprint,
            "candidate_current_state_sha256": candidate_current_state_sha256,
            "candidate_current_state_fingerprint": candidate_current_state_fingerprint,
            "candidate_year_checkpoint_fingerprint": candidate_year_checkpoint_fingerprint,
            "timeframe": Timeframe.DAY_1.value,
        }
    )


class HistoricalBackfillDailyFeaturePromotionPreflight:
    """Read-only Gate 9-C promotion planning over the accepted Gate 9-B replay.

    Gate 9-C is intentionally split before any production feature write. This preflight
    revalidates Gate 9-B, freezes the current production 1d feature/state namespace as
    the rollback baseline, and classifies every candidate session as new, exact reuse,
    protected replacement, or an unmanaged collision. The production daily feature
    tree, manifests, state checkpoints, canonical bars, and all sub-daily feature trees
    remain untouched.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.validator = HistoricalBackfillDailyFeatureReplayValidatorV2(settings)
        self.replay: HistoricalBackfillDailyFeatureReplay = self.validator.replay
        self.root = self.replay.preflight.root / "promotion" / "v1"
        self.report_path = self.root / "gate9c_preflight_report.json"

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 9-C requires {label}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _candidate_inventory(
        self,
        replay_report: dict[str, Any],
    ) -> tuple[list[dict[str, object]], dict[str, object]]:
        rows: list[dict[str, object]] = []
        feature_hash_failures = 0
        manifest_hash_failures = 0
        total_feature_bytes = 0
        total_manifest_bytes = 0

        for year_record in list(replay_report.get("year_manifests") or []):
            year = int(year_record["year"])
            year_path = self.replay.year_manifest_path(year)
            year_payload = self._load_json(year_path, f"Gate 9-B year manifest {year}")
            for record in list(year_payload.get("sessions") or []):
                feature_path = Path(str(record["feature_path"]))
                manifest_path = Path(str(record["manifest_path"]))
                feature_sha = str(record["feature_sha256"])
                manifest_sha = str(record["manifest_sha256"])
                if not feature_path.is_file() or sha256_file(feature_path) != feature_sha:
                    feature_hash_failures += 1
                else:
                    total_feature_bytes += feature_path.stat().st_size
                if not manifest_path.is_file() or sha256_file(manifest_path) != manifest_sha:
                    manifest_hash_failures += 1
                else:
                    total_manifest_bytes += manifest_path.stat().st_size
                rows.append(
                    {
                        "session_date": str(record["session_date"]),
                        "feature_path": str(feature_path),
                        "feature_sha256": feature_sha,
                        "manifest_path": str(manifest_path),
                        "manifest_sha256": manifest_sha,
                        "source_sha256": str(record["source_sha256"]),
                        "row_count": int(record["row_count"]),
                        "symbol_count": int(record["symbol_count"]),
                    }
                )

        rows.sort(key=lambda item: item["session_date"])
        unique_sessions = len({str(row["session_date"]) for row in rows})
        return rows, {
            "feature_hash_failures": feature_hash_failures,
            "manifest_hash_failures": manifest_hash_failures,
            "feature_bytes": total_feature_bytes,
            "manifest_bytes": total_manifest_bytes,
            "sessions": len(rows),
            "unique_sessions": unique_sessions,
            "rows": sum(int(row["row_count"]) for row in rows),
            "first_session": rows[0]["session_date"] if rows else None,
            "last_session": rows[-1]["session_date"] if rows else None,
        }

    def _year_checkpoint_inventory(
        self,
        replay_report: dict[str, Any],
    ) -> tuple[list[dict[str, object]], int, str]:
        rows: list[dict[str, object]] = []
        total_bytes = 0
        for year_record in list(replay_report.get("year_manifests") or []):
            year = int(year_record["year"])
            year_payload = self._load_json(
                self.replay.year_manifest_path(year),
                f"Gate 9-B year manifest {year}",
            )
            path = Path(str(year_payload["checkpoint_path"]))
            expected_sha = str(year_payload["checkpoint_sha256"])
            actual_sha = sha256_file(path) if path.is_file() else ""
            rows.append(
                {
                    "year": year,
                    "last_session": str(year_payload["last_session"]),
                    "path": str(path),
                    "sha256": actual_sha,
                    "expected_sha256": expected_sha,
                    "output_state_fingerprint": str(year_payload["output_state_fingerprint"]),
                }
            )
            if path.is_file():
                total_bytes += path.stat().st_size
        fingerprint = stable_source_fingerprint(
            {
                "year_checkpoints": [
                    {
                        "year": row["year"],
                        "last_session": row["last_session"],
                        "sha256": row["sha256"],
                        "output_state_fingerprint": row["output_state_fingerprint"],
                    }
                    for row in rows
                ]
            }
        )
        return rows, total_bytes, fingerprint

    def _production_state_inventory(self) -> tuple[list[dict[str, object]], int]:
        state_root = self.paths.feature_current_state_file(Timeframe.DAY_1).parent
        paths = sorted(state_root.glob("**/*.json.gz")) if state_root.exists() else []
        derived_root = self.settings.resolved_path(self.settings.data.paths.derived)
        rows: list[dict[str, object]] = []
        total_bytes = 0
        for path in paths:
            rows.append(
                {
                    "relative_path": path.relative_to(derived_root).as_posix(),
                    "path": str(path),
                    "sha256": sha256_file(path),
                    "bytes": path.stat().st_size,
                }
            )
            total_bytes += path.stat().st_size
        return rows, total_bytes

    def run(self) -> dict[str, object]:
        validation = self.validator.run()
        if validation.get("pass") is not True:
            raise RuntimeError("Gate 9-C requires accepted Gate 9-B independent validation")
        if (
            validation.get("validation_contract_version")
            != GATE9_DAILY_REPLAY_VALIDATION_V2_CONTRACT_VERSION
        ):
            raise RuntimeError("Gate 9-C requires Gate 9-B validation v2")

        replay_report = self._load_json(self.replay.report_path, "Gate 9-B replay report")
        candidate_rows, candidate_stats = self._candidate_inventory(replay_report)
        candidate_fp = feature_inventory_fingerprint(candidate_rows)

        year_checkpoints, year_checkpoint_bytes, year_checkpoint_fp = (
            self._year_checkpoint_inventory(replay_report)
        )
        year_checkpoint_hash_failures = sum(
            1
            for row in year_checkpoints
            if row["sha256"] != row["expected_sha256"]
        )

        candidate_state_path = self.replay.current_state_path
        if not candidate_state_path.is_file():
            raise RuntimeError("Gate 9-C candidate current-state checkpoint is missing")
        candidate_state_sha = sha256_file(candidate_state_path)
        _candidate_engine, candidate_state_payload = self.replay.checkpoints.read(
            candidate_state_path,
            expected_timeframe=Timeframe.DAY_1,
        )
        candidate_state_fp = str(candidate_state_payload["checkpoint_fingerprint"])
        candidate_state_as_of = str(candidate_state_payload["as_of_date"])
        candidate_state_bytes = candidate_state_path.stat().st_size

        baseline_rows, baseline_stats = self.replay.preflight._production_feature_baseline()
        baseline_by_session = {
            date.fromisoformat(str(row["session_date"])): row for row in baseline_rows
        }
        production_state_rows, production_state_bytes = self._production_state_inventory()
        baseline_feature_bytes = sum(
            Path(str(row["path"])).stat().st_size
            for row in baseline_rows
            if Path(str(row["path"])).is_file()
        )
        baseline_manifest_bytes = sum(
            Path(str(row["manifest_path"])).stat().st_size
            for row in baseline_rows
            if Path(str(row["manifest_path"])).is_file()
        )

        action_counts: Counter[str] = Counter()
        plan: list[dict[str, object]] = []
        candidate_sessions: set[date] = set()
        overlap_sessions = 0
        prehistory_new_sessions = 0
        replacement_sessions: list[str] = []
        exact_reuse_sessions: list[str] = []
        unmanaged_sessions: list[str] = []

        for row in candidate_rows:
            session = date.fromisoformat(str(row["session_date"]))
            if session in candidate_sessions:
                raise RuntimeError(f"Gate 9-C duplicate candidate session: {session}")
            candidate_sessions.add(session)
            target_path = self.paths.feature_file(Timeframe.DAY_1, session)
            target_exists = target_path.is_file()
            target_sha = sha256_file(target_path) if target_exists else None
            baseline_row = baseline_by_session.get(session)
            action = feature_promotion_action(
                target_exists=target_exists,
                target_in_locked_baseline=baseline_row is not None,
                target_sha256=target_sha,
                candidate_sha256=str(row["feature_sha256"]),
            )
            action_counts[action] += 1
            if baseline_row is not None:
                overlap_sessions += 1
            if action == COPY_NEW and session < ALPACA_BACKFILL_SEAM_TARGET_SESSION:
                prehistory_new_sessions += 1
            elif action == REPLACE_PROTECTED_BASELINE:
                replacement_sessions.append(session.isoformat())
            elif action == REUSE_EXACT:
                exact_reuse_sessions.append(session.isoformat())
            elif action == FAIL_UNMANAGED_TARGET:
                unmanaged_sessions.append(session.isoformat())
            plan.append(
                {
                    "session_date": session.isoformat(),
                    "action": action,
                    "candidate_feature_path": row["feature_path"],
                    "candidate_feature_sha256": row["feature_sha256"],
                    "production_feature_path": str(target_path),
                    "production_feature_sha256": target_sha,
                    "locked_baseline": baseline_row is not None,
                }
            )

        unexpected_production_sessions = sorted(
            session.isoformat()
            for session in baseline_by_session
            if session not in candidate_sessions
        )

        baseline_fp = str(baseline_stats["fingerprint"])
        source_fp = feature_promotion_source_fingerprint(
            replay_source_fingerprint=str(validation["source_fingerprint"]),
            candidate_inventory_fingerprint=candidate_fp,
            production_baseline_fingerprint=baseline_fp,
            candidate_current_state_sha256=candidate_state_sha,
            candidate_current_state_fingerprint=candidate_state_fp,
            candidate_year_checkpoint_fingerprint=year_checkpoint_fp,
        )

        expected_candidate = dict(validation["candidate"])
        stored_baseline_fp = str(replay_report["production_feature_baseline_fingerprint"])
        production_current_state = self.paths.feature_current_state_file(Timeframe.DAY_1)
        production_current_state_sha = (
            sha256_file(production_current_state)
            if production_current_state.is_file()
            else None
        )

        checks = {
            "preflight_contract": True,
            "gate9b_validation_pass": validation.get("pass") is True,
            "gate9b_validation_v2": validation.get("validation_contract_version")
            == GATE9_DAILY_REPLAY_VALIDATION_V2_CONTRACT_VERSION,
            "replay_contract_current": replay_report.get("contract_version")
            == GATE9_DAILY_REPLAY_CONTRACT_VERSION,
            "replay_source_fingerprint_current": replay_report.get("source_fingerprint")
            == validation.get("source_fingerprint"),
            "production_baseline_unchanged_from_gate9b": baseline_fp == stored_baseline_fp,
            "candidate_feature_hashes_exact": int(candidate_stats["feature_hash_failures"]) == 0,
            "candidate_manifest_hashes_exact": int(candidate_stats["manifest_hash_failures"])
            == 0,
            "candidate_year_checkpoint_hashes_exact": year_checkpoint_hash_failures == 0,
            "candidate_session_accounting_exact": int(candidate_stats["sessions"])
            == int(expected_candidate["sessions"]),
            "candidate_sessions_unique": int(candidate_stats["unique_sessions"])
            == int(candidate_stats["sessions"]),
            "candidate_row_accounting_exact": int(candidate_stats["rows"])
            == int(expected_candidate["rows"]),
            "candidate_range_exact": candidate_stats["first_session"]
            == expected_candidate["first_session"]
            and candidate_stats["last_session"] == expected_candidate["last_session"],
            "production_sessions_subset_candidate": not unexpected_production_sessions,
            "locked_overlap_accounting_exact": overlap_sessions
            == int(baseline_stats["sessions"]),
            "promotion_plan_accounting_exact": sum(action_counts.values())
            == int(candidate_stats["sessions"]),
            "unmanaged_targets_zero": int(action_counts[FAIL_UNMANAGED_TARGET]) == 0,
            "new_sessions_are_preseam": int(action_counts[COPY_NEW])
            == prehistory_new_sessions,
            "candidate_current_state_hash_exact": candidate_state_sha
            == replay_report.get("current_state_sha256"),
            "candidate_current_state_fingerprint_exact": candidate_state_fp
            == replay_report.get("current_state_fingerprint"),
            "candidate_current_state_range_exact": candidate_state_as_of
            == candidate_stats["last_session"],
            "production_current_state_present": production_current_state.is_file(),
            "candidate_namespace_isolated": self.replay.feature_root.resolve()
            != (
                self.settings.resolved_path(self.settings.data.paths.derived)
                / "features"
                / "1d"
            ).resolve(),
            "production_feature_writes_zero": True,
        }

        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_FEATURE_PROMOTION_ROLE,
            "source_fingerprint": source_fp,
            "gate9b_replay_source_fingerprint": validation["source_fingerprint"],
            "gate9b_validation_contract": validation["validation_contract_version"],
            "candidate_inventory_fingerprint": candidate_fp,
            "candidate": {
                **candidate_stats,
                "current_state_path": str(candidate_state_path),
                "current_state_sha256": candidate_state_sha,
                "current_state_fingerprint": candidate_state_fp,
                "current_state_as_of": candidate_state_as_of,
                "current_state_bytes": candidate_state_bytes,
                "year_checkpoints": len(year_checkpoints),
                "year_checkpoint_bytes": year_checkpoint_bytes,
                "year_checkpoint_fingerprint": year_checkpoint_fp,
                "year_checkpoint_hash_failures": year_checkpoint_hash_failures,
            },
            "production_rollback_baseline": {
                **baseline_stats,
                "feature_bytes": baseline_feature_bytes,
                "manifest_bytes": baseline_manifest_bytes,
                "state_files": len(production_state_rows),
                "state_bytes": production_state_bytes,
                "current_state_path": str(production_current_state),
                "current_state_sha256": production_current_state_sha,
                "total_bytes": baseline_feature_bytes
                + baseline_manifest_bytes
                + production_state_bytes,
            },
            "promotion_plan": {
                "candidate_sessions": len(candidate_rows),
                "locked_overlap_sessions": overlap_sessions,
                "copy_new_sessions": int(action_counts[COPY_NEW]),
                "reuse_exact_sessions": int(action_counts[REUSE_EXACT]),
                "replace_protected_baseline_sessions": int(
                    action_counts[REPLACE_PROTECTED_BASELINE]
                ),
                "unmanaged_target_sessions": int(action_counts[FAIL_UNMANAGED_TARGET]),
                "prehistory_new_sessions": prehistory_new_sessions,
                "replacement_session_examples": replacement_sessions[:20],
                "exact_reuse_session_examples": exact_reuse_sessions[:20],
                "unmanaged_sessions": unmanaged_sessions,
                "unexpected_production_sessions": unexpected_production_sessions,
                "candidate_feature_bytes": int(candidate_stats["feature_bytes"]),
                "candidate_manifest_bytes": int(candidate_stats["manifest_bytes"]),
                "candidate_state_and_year_checkpoint_bytes": candidate_state_bytes
                + year_checkpoint_bytes,
                "candidate_total_bytes": int(candidate_stats["feature_bytes"])
                + int(candidate_stats["manifest_bytes"])
                + candidate_state_bytes
                + year_checkpoint_bytes,
            },
            "production_state_inventory": production_state_rows,
            "candidate_year_checkpoints": year_checkpoints,
            "plan": plan,
            "production_feature_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
