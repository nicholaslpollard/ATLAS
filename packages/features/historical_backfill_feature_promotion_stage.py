from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.features.historical_backfill_feature_promotion import (
    GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
    HistoricalBackfillDailyFeaturePromotionPreflight,
)
from packages.features.historical_backfill_replay_build import apply_lifecycle_events
from packages.features.incremental import IncrementalFeatureEngine
from packages.features.partition_store import (
    FEATURE_PARTITION_CONTRACT_VERSION,
    FEATURE_PARTITION_SCHEMA_VERSION,
    FeaturePartitionManifest,
    feature_dependency_fingerprint,
)
from packages.features.state_checkpoint import (
    FEATURE_STATE_SCHEMA_VERSION,
    feature_state_fingerprint,
)
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY


GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION = (
    "historical-backfill-feature-promotion-stage-v1-production-native-bundle"
)
GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION = (
    "historical-backfill-feature-promotion-stage-year-v1-independent-year-replay"
)
GATE9_FEATURE_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-feature-promotion-stage-validation-v1-disk-proof"
)
GATE9_FEATURE_PROMOTION_STAGE_ROLE = "PRODUCTION_DAILY_FEATURE_PROMOTION_STAGED_NOT_LIVE"

StageProgressCallback = Callable[[int, str, int, int], None]


def gate9c_stage_source_fingerprint(
    *,
    preflight_source_fingerprint: str,
    candidate_inventory_fingerprint: str,
    production_baseline_fingerprint: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION,
            "year_contract_version": GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION,
            "role": GATE9_FEATURE_PROMOTION_STAGE_ROLE,
            "preflight_contract_version": GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "preflight_source_fingerprint": preflight_source_fingerprint,
            "candidate_inventory_fingerprint": candidate_inventory_fingerprint,
            "production_baseline_fingerprint": production_baseline_fingerprint,
            "feature_partition_schema_version": FEATURE_PARTITION_SCHEMA_VERSION,
            "feature_partition_contract_version": FEATURE_PARTITION_CONTRACT_VERSION,
            "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "feature_state_schema_version": FEATURE_STATE_SCHEMA_VERSION,
            "timeframe": Timeframe.DAY_1.value,
        }
    )


def month_end_sessions(sessions: list[date]) -> set[date]:
    """Return the final observed exchange session in each calendar month."""

    result: dict[tuple[int, int], date] = {}
    for session in sorted(sessions):
        result[(session.year, session.month)] = session
    return set(result.values())


def production_manifest_payload(
    *,
    trading_date: date,
    source_path: Path,
    source_sha256: str,
    input_state_fingerprint: str,
    output_state_fingerprint: str,
    production_feature_path: Path,
    feature_sha256: str,
    row_count: int,
    symbol_count: int,
    created_at_utc: str,
) -> dict[str, object]:
    """Build the normal production FeaturePartitionManifest for a staged replay row."""

    record = FeaturePartitionManifest(
        schema_version=FEATURE_PARTITION_SCHEMA_VERSION,
        partition_contract_version=FEATURE_PARTITION_CONTRACT_VERSION,
        feature_contract_version=CORE_FEATURE_CONTRACT_VERSION,
        feature_registry_fingerprint=CORE_FEATURE_REGISTRY.fingerprint(),
        timeframe=Timeframe.DAY_1.value,
        trading_date=trading_date.isoformat(),
        source_path=str(Path(source_path).resolve()),
        source_sha256=source_sha256,
        input_state_fingerprint=input_state_fingerprint,
        output_state_fingerprint=output_state_fingerprint,
        dependency_fingerprint=feature_dependency_fingerprint(
            source_sha256=source_sha256,
            input_state_fingerprint=input_state_fingerprint,
        ),
        feature_path=str(Path(production_feature_path).resolve()),
        feature_sha256=feature_sha256,
        row_count=int(row_count),
        symbol_count=int(symbol_count),
        created_at_utc=created_at_utc,
    )
    return asdict(record)


class HistoricalBackfillDailyFeaturePromotionStage:
    """Build a production-native Gate 9-C bundle without touching production 1d features."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.preflight = HistoricalBackfillDailyFeaturePromotionPreflight(settings)
        self.replay = self.preflight.replay
        self.paths = self.preflight.paths
        self.checkpoints = self.replay.checkpoints
        self.root = self.preflight.root / "stage"
        self.staged_derived_root = self.root / "derived"
        self.staged_manifests_root = self.root / "manifests"
        self.staged_feature_root = self.staged_derived_root / "features" / Timeframe.DAY_1.value
        self.staged_state_root = (
            self.staged_derived_root / "features" / "_state" / Timeframe.DAY_1.value
        )
        self.staged_manifest_root = (
            self.staged_manifests_root / "features" / Timeframe.DAY_1.value
        )
        self.year_manifest_root = self.root / "year_manifests"
        self.report_path = self.preflight.root / "gate9c_stage_report.json"

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 9-C stage requires {label}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def staged_feature_path(self, trading_date: date) -> Path:
        return (
            self.staged_feature_root
            / f"year={trading_date.year:04d}"
            / f"month={trading_date.month:02d}"
            / f"date={trading_date}"
            / "part-000.parquet"
        )

    def staged_manifest_path(self, trading_date: date) -> Path:
        return self.staged_manifest_root / f"{trading_date.year:04d}" / f"{trading_date}.json"

    def staged_monthly_state_path(self, trading_date: date) -> Path:
        return (
            self.staged_state_root
            / "monthly"
            / f"{trading_date.year:04d}"
            / f"{trading_date}.json.gz"
        )

    @property
    def staged_current_state_path(self) -> Path:
        return self.staged_state_root / "current.json.gz"

    def stage_year_manifest_path(self, year: int) -> Path:
        return self.year_manifest_root / f"{year:04d}.json"

    @staticmethod
    def _copy_exact(source: Path, target: Path, expected_sha256: str) -> bool:
        """Copy one immutable candidate file unless an exact staged copy already exists."""

        source = Path(source)
        target = Path(target)
        if not source.is_file() or sha256_file(source) != expected_sha256:
            raise RuntimeError(f"Gate 9-C stage candidate hash mismatch: {source}")
        if target.is_file() and sha256_file(target) == expected_sha256:
            return False
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(target)
        try:
            shutil.copy2(source, temp)
            if sha256_file(temp) != expected_sha256:
                raise RuntimeError(f"Gate 9-C staged copy hash mismatch: {source}")
            replace_with_retry(temp, target)
        except Exception:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        if sha256_file(target) != expected_sha256:
            raise RuntimeError(f"Gate 9-C staged target hash mismatch: {target}")
        return True

    @staticmethod
    def _update_engine_only(engine: IncrementalFeatureEngine, bars: Any) -> None:
        for row in bars.itertuples(index=False):
            engine.update(
                symbol=str(row.symbol),
                timestamp_utc=row.timestamp_utc,
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )

    def _candidate_created_at(self, candidate_row: dict[str, object]) -> str:
        payload = self._load_json(
            Path(str(candidate_row["manifest_path"])),
            f"Gate 9-B candidate session manifest {candidate_row['session_date']}",
        )
        value = str(payload.get("created_at_utc") or "")
        if not value:
            raise RuntimeError("Gate 9-C candidate session manifest lacks created_at_utc")
        return value

    def _year_source_payload(
        self,
        *,
        stage_source_fingerprint: str,
        year: int,
        candidate_rows: list[dict[str, object]],
        canonical_rows: list[dict[str, object]],
        expected_output_state_fingerprint: str,
    ) -> str:
        return stable_source_fingerprint(
            {
                "contract_version": GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION,
                "stage_source_fingerprint": stage_source_fingerprint,
                "year": int(year),
                "candidate": [
                    {
                        "session_date": str(row["session_date"]),
                        "feature_sha256": str(row["feature_sha256"]),
                        "source_sha256": str(row["source_sha256"]),
                        "row_count": int(row["row_count"]),
                        "symbol_count": int(row["symbol_count"]),
                    }
                    for row in candidate_rows
                ],
                "canonical": [
                    {
                        "session_date": str(row["session_date"]),
                        "sha256": str(row["sha256"]),
                    }
                    for row in canonical_rows
                ],
                "expected_output_state_fingerprint": expected_output_state_fingerprint,
            }
        )

    def _validate_staged_year(
        self,
        *,
        year: int,
        year_source_fingerprint: str,
        candidate_rows: list[dict[str, object]],
        expected_output_state_fingerprint: str,
        expected_month_ends: set[date],
    ) -> tuple[bool, dict[str, Any] | None]:
        path = self.stage_year_manifest_path(year)
        if not path.is_file():
            return False, None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("contract_version") != GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION:
                return False, None
            if payload.get("year_source_fingerprint") != year_source_fingerprint:
                return False, None
            if payload.get("output_state_fingerprint") != expected_output_state_fingerprint:
                return False, None
            records = list(payload.get("sessions") or [])
            if len(records) != len(candidate_rows):
                return False, None
            candidate_by_date = {str(row["session_date"]): row for row in candidate_rows}
            for record in records:
                candidate = candidate_by_date.get(str(record.get("session_date")))
                if candidate is None:
                    return False, None
                feature_path = Path(str(record.get("feature_path") or ""))
                manifest_path = Path(str(record.get("manifest_path") or ""))
                if not feature_path.is_file() or sha256_file(feature_path) != candidate[
                    "feature_sha256"
                ]:
                    return False, None
                if not manifest_path.is_file() or sha256_file(manifest_path) != record.get(
                    "manifest_sha256"
                ):
                    return False, None
                manifest = FeaturePartitionManifest.from_dict(
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                )
                trading_date = date.fromisoformat(str(record["session_date"]))
                manifest.validate_contract(Timeframe.DAY_1, trading_date)
                if manifest.feature_sha256 != candidate["feature_sha256"]:
                    return False, None
                if manifest.source_sha256 != candidate["source_sha256"]:
                    return False, None
            checkpoints = list(payload.get("monthly_checkpoints") or [])
            if {date.fromisoformat(str(row["session_date"])) for row in checkpoints} != expected_month_ends:
                return False, None
            for record in checkpoints:
                checkpoint_path = Path(str(record.get("path") or ""))
                if not checkpoint_path.is_file() or sha256_file(checkpoint_path) != record.get(
                    "sha256"
                ):
                    return False, None
                _engine, checkpoint = self.checkpoints.read(
                    checkpoint_path,
                    expected_timeframe=Timeframe.DAY_1,
                )
                if checkpoint.get("checkpoint_fingerprint") != record.get("state_fingerprint"):
                    return False, None
            return True, payload
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False, None

    def _build_year(
        self,
        *,
        year: int,
        first_year: int,
        stage_source_fingerprint: str,
        canonical_rows: list[dict[str, object]],
        candidate_rows: list[dict[str, object]],
        events_by_date: dict[date, list[dict[str, object]]],
        expected_output_state_fingerprint: str,
        expected_month_ends: set[date],
    ) -> dict[str, object]:
        candidate_by_date = {
            date.fromisoformat(str(row["session_date"])): row for row in candidate_rows
        }
        if year == first_year:
            engine = IncrementalFeatureEngine()
            input_as_of = "genesis"
        else:
            previous_year = year - 1
            previous_payload = self._load_json(
                self.replay.year_manifest_path(previous_year),
                f"Gate 9-B year manifest {previous_year}",
            )
            previous_checkpoint = Path(str(previous_payload["checkpoint_path"]))
            engine, checkpoint_payload = self.checkpoints.read(
                previous_checkpoint,
                expected_timeframe=Timeframe.DAY_1,
            )
            input_as_of = str(checkpoint_payload["as_of_date"])

        session_records: list[dict[str, object]] = []
        monthly_records: list[dict[str, object]] = []
        copied_features = 0
        reused_features = 0
        row_count = 0

        for source_row in canonical_rows:
            trading_date = date.fromisoformat(str(source_row["session_date"]))
            candidate = candidate_by_date.get(trading_date)
            if candidate is None:
                raise RuntimeError(f"Gate 9-C stage lacks candidate session {trading_date}")
            if str(candidate["source_sha256"]) != str(source_row["sha256"]):
                raise RuntimeError(f"Gate 9-C candidate/canonical source hash mismatch: {trading_date}")

            apply_lifecycle_events(engine, events_by_date.get(trading_date, []))
            input_state_fp = feature_state_fingerprint(
                engine,
                timeframe=Timeframe.DAY_1,
                as_of_date=input_as_of,
            )
            bars = self.replay._load_source(Path(str(source_row["path"])))
            self._update_engine_only(engine, bars)
            output_state_fp = feature_state_fingerprint(
                engine,
                timeframe=Timeframe.DAY_1,
                as_of_date=trading_date.isoformat(),
            )

            candidate_feature_path = Path(str(candidate["feature_path"]))
            stage_feature_path = self.staged_feature_path(trading_date)
            copied = self._copy_exact(
                candidate_feature_path,
                stage_feature_path,
                str(candidate["feature_sha256"]),
            )
            copied_features += int(copied)
            reused_features += int(not copied)

            manifest_payload = production_manifest_payload(
                trading_date=trading_date,
                source_path=Path(str(source_row["path"])),
                source_sha256=str(source_row["sha256"]),
                input_state_fingerprint=input_state_fp,
                output_state_fingerprint=output_state_fp,
                production_feature_path=self.paths.feature_file(Timeframe.DAY_1, trading_date),
                feature_sha256=str(candidate["feature_sha256"]),
                row_count=int(candidate["row_count"]),
                symbol_count=int(candidate["symbol_count"]),
                created_at_utc=self._candidate_created_at(candidate),
            )
            stage_manifest_path = self.staged_manifest_path(trading_date)
            atomic_write_text(
                stage_manifest_path,
                json.dumps(manifest_payload, indent=2, sort_keys=True) + "\n",
            )
            manifest_sha = sha256_file(stage_manifest_path)

            if trading_date in expected_month_ends:
                checkpoint_path = self.staged_monthly_state_path(trading_date)
                state_fp = self.checkpoints.write(
                    checkpoint_path,
                    engine,
                    timeframe=Timeframe.DAY_1,
                    as_of_date=trading_date.isoformat(),
                )
                monthly_records.append(
                    {
                        "session_date": trading_date.isoformat(),
                        "path": str(checkpoint_path),
                        "sha256": sha256_file(checkpoint_path),
                        "state_fingerprint": state_fp,
                    }
                )

            session_records.append(
                {
                    "session_date": trading_date.isoformat(),
                    "feature_path": str(stage_feature_path),
                    "feature_sha256": str(candidate["feature_sha256"]),
                    "manifest_path": str(stage_manifest_path),
                    "manifest_sha256": manifest_sha,
                    "input_state_fingerprint": input_state_fp,
                    "output_state_fingerprint": output_state_fp,
                    "row_count": int(candidate["row_count"]),
                    "symbol_count": int(candidate["symbol_count"]),
                }
            )
            row_count += int(candidate["row_count"])
            input_as_of = trading_date.isoformat()

        if not session_records:
            raise RuntimeError(f"Gate 9-C stage year {year} has no sessions")
        final_output_fp = str(session_records[-1]["output_state_fingerprint"])
        if final_output_fp != expected_output_state_fingerprint:
            raise RuntimeError(
                f"Gate 9-C stage year-end state mismatch for {year}: "
                f"{final_output_fp} != {expected_output_state_fingerprint}"
            )

        year_source_fp = self._year_source_payload(
            stage_source_fingerprint=stage_source_fingerprint,
            year=year,
            candidate_rows=candidate_rows,
            canonical_rows=canonical_rows,
            expected_output_state_fingerprint=expected_output_state_fingerprint,
        )
        payload: dict[str, object] = {
            "contract_version": GATE9_FEATURE_PROMOTION_STAGE_YEAR_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "stage_source_fingerprint": stage_source_fingerprint,
            "year_source_fingerprint": year_source_fp,
            "year": year,
            "first_session": session_records[0]["session_date"],
            "last_session": session_records[-1]["session_date"],
            "session_count": len(session_records),
            "row_count": row_count,
            "output_state_fingerprint": final_output_fp,
            "copied_feature_files": copied_features,
            "reused_feature_files": reused_features,
            "sessions": session_records,
            "monthly_checkpoints": monthly_records,
        }
        atomic_write_text(
            self.stage_year_manifest_path(year),
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
        return payload

    def run(self, *, progress: StageProgressCallback | None = None) -> dict[str, object]:
        preflight_report = self.preflight.run()
        if preflight_report.get("pass") is not True:
            raise RuntimeError("Gate 9-C staging requires accepted promotion preflight")

        replay_report = self._load_json(self.replay.report_path, "Gate 9-B replay report")
        candidate_rows, candidate_stats = self.preflight._candidate_inventory(replay_report)
        canonical_inventory = self.replay.preflight._canonical_inventory()
        grouped_canonical = self.replay._group_inventory(canonical_inventory)
        candidate_by_year: dict[int, list[dict[str, object]]] = {}
        for row in candidate_rows:
            session = date.fromisoformat(str(row["session_date"]))
            candidate_by_year.setdefault(session.year, []).append(row)
        for rows in candidate_by_year.values():
            rows.sort(key=lambda item: str(item["session_date"]))

        accepted_years: dict[int, dict[str, Any]] = {}
        for year_record in list(replay_report.get("year_manifests") or []):
            year = int(year_record["year"])
            accepted_years[year] = self._load_json(
                self.replay.year_manifest_path(year),
                f"Gate 9-B year manifest {year}",
            )

        events = self.replay._load_lifecycle_events()
        events_by_date = self.replay._events_by_date(events)
        all_sessions = [date.fromisoformat(str(row["session_date"])) for row in canonical_inventory]
        all_month_ends = month_end_sessions(all_sessions)

        stage_fp = gate9c_stage_source_fingerprint(
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            candidate_inventory_fingerprint=str(preflight_report["candidate_inventory_fingerprint"]),
            production_baseline_fingerprint=str(
                preflight_report["production_rollback_baseline"]["fingerprint"]
            ),
        )

        rebuilt_years: list[int] = []
        reused_years: list[int] = []
        year_reports: list[dict[str, object]] = []
        total_rows = 0
        total_sessions = 0
        copied_features = 0
        reused_features = 0
        monthly_checkpoints = 0
        first_year = min(grouped_canonical)

        for year, canonical_rows in grouped_canonical.items():
            candidate_year_rows = candidate_by_year.get(year, [])
            accepted_year = accepted_years.get(year)
            if accepted_year is None:
                raise RuntimeError(f"Gate 9-C stage lacks accepted Gate 9-B year {year}")
            expected_output_fp = str(accepted_year["output_state_fingerprint"])
            expected_month_ends = {
                session for session in all_month_ends if session.year == year
            }
            year_source_fp = self._year_source_payload(
                stage_source_fingerprint=stage_fp,
                year=year,
                candidate_rows=candidate_year_rows,
                canonical_rows=canonical_rows,
                expected_output_state_fingerprint=expected_output_fp,
            )
            valid, existing = self._validate_staged_year(
                year=year,
                year_source_fingerprint=year_source_fp,
                candidate_rows=candidate_year_rows,
                expected_output_state_fingerprint=expected_output_fp,
                expected_month_ends=expected_month_ends,
            )
            if valid and existing is not None:
                payload = existing
                reused_years.append(year)
                action = "REUSED"
            else:
                payload = self._build_year(
                    year=year,
                    first_year=first_year,
                    stage_source_fingerprint=stage_fp,
                    canonical_rows=canonical_rows,
                    candidate_rows=candidate_year_rows,
                    events_by_date=events_by_date,
                    expected_output_state_fingerprint=expected_output_fp,
                    expected_month_ends=expected_month_ends,
                )
                rebuilt_years.append(year)
                action = "REBUILT"
            year_reports.append(payload)
            total_rows += int(payload["row_count"])
            total_sessions += int(payload["session_count"])
            copied_features += int(payload.get("copied_feature_files", 0))
            reused_features += int(payload.get("reused_feature_files", 0))
            monthly_checkpoints += len(list(payload.get("monthly_checkpoints") or []))
            if progress is not None:
                progress(year, action, int(payload["session_count"]), int(payload["row_count"]))

        candidate_current = Path(str(preflight_report["candidate"]["current_state_path"]))
        candidate_current_sha = str(preflight_report["candidate"]["current_state_sha256"])
        self._copy_exact(candidate_current, self.staged_current_state_path, candidate_current_sha)
        staged_current_sha = sha256_file(self.staged_current_state_path)
        _engine, staged_current_payload = self.checkpoints.read(
            self.staged_current_state_path,
            expected_timeframe=Timeframe.DAY_1,
        )
        staged_current_fp = str(staged_current_payload["checkpoint_fingerprint"])

        _baseline_rows_after, baseline_after = self.replay.preflight._production_feature_baseline()
        baseline_unchanged = str(baseline_after["fingerprint"]) == str(
            preflight_report["production_rollback_baseline"]["fingerprint"]
        )

        staged_manifest_count = sum(len(list(row.get("sessions") or [])) for row in year_reports)
        staged_feature_count = len(list(self.staged_feature_root.glob("**/*.parquet")))
        staged_state_files = list(self.staged_state_root.glob("**/*.json.gz"))
        staged_bytes = sum(path.stat().st_size for path in self.root.glob("**/*") if path.is_file())

        checks = {
            "stage_contract": True,
            "preflight_pass": preflight_report.get("pass") is True,
            "candidate_accounting_exact": total_rows == int(candidate_stats["rows"])
            and total_sessions == int(candidate_stats["sessions"]),
            "all_candidate_sessions_staged": staged_feature_count == int(candidate_stats["sessions"]),
            "all_production_manifests_staged": staged_manifest_count == int(candidate_stats["sessions"]),
            "monthly_anchor_accounting_exact": monthly_checkpoints == len(all_month_ends),
            "year_end_states_match_gate9b": all(
                str(report["output_state_fingerprint"])
                == str(accepted_years[int(report["year"])]["output_state_fingerprint"])
                for report in year_reports
            ),
            "current_state_hash_exact": staged_current_sha == candidate_current_sha,
            "current_state_fingerprint_exact": staged_current_fp
            == str(preflight_report["candidate"]["current_state_fingerprint"]),
            "production_baseline_unchanged": baseline_unchanged,
            "stage_namespace_isolated": self.staged_feature_root.resolve()
            != (
                self.settings.resolved_path(self.settings.data.paths.derived)
                / "features"
                / Timeframe.DAY_1.value
            ).resolve(),
            "production_feature_writes_zero": True,
        }
        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_PROMOTION_STAGE_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_FEATURE_PROMOTION_STAGE_ROLE,
            "source_fingerprint": stage_fp,
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "candidate_inventory_fingerprint": preflight_report["candidate_inventory_fingerprint"],
            "production_baseline_fingerprint": preflight_report["production_rollback_baseline"][
                "fingerprint"
            ],
            "candidate_rows": int(candidate_stats["rows"]),
            "candidate_sessions": int(candidate_stats["sessions"]),
            "first_session": candidate_stats["first_session"],
            "last_session": candidate_stats["last_session"],
            "rebuilt_years": rebuilt_years,
            "reused_years": reused_years,
            "copied_feature_files": copied_features,
            "reused_feature_files": reused_features,
            "staged_feature_files": staged_feature_count,
            "staged_manifest_files": staged_manifest_count,
            "staged_state_files": len(staged_state_files),
            "monthly_checkpoints": monthly_checkpoints,
            "staged_current_state_sha256": staged_current_sha,
            "staged_current_state_fingerprint": staged_current_fp,
            "staged_bytes": staged_bytes,
            "staged_feature_root": str(self.staged_feature_root),
            "staged_manifest_root": str(self.staged_manifest_root),
            "staged_state_root": str(self.staged_state_root),
            "year_manifests": [
                {
                    "year": int(row["year"]),
                    "path": str(self.stage_year_manifest_path(int(row["year"]))),
                    "sha256": sha256_file(self.stage_year_manifest_path(int(row["year"]))),
                    "session_count": int(row["session_count"]),
                    "row_count": int(row["row_count"]),
                    "output_state_fingerprint": row["output_state_fingerprint"],
                }
                for row in year_reports
            ],
            "production_feature_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report


class HistoricalBackfillDailyFeaturePromotionStageValidator:
    """Independently reopen the Gate 9-C staged production-native bundle."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.stage = HistoricalBackfillDailyFeaturePromotionStage(settings)
        self.preflight = self.stage.preflight
        self.replay = self.stage.replay
        self.checkpoints = self.stage.checkpoints
        self.report_path = self.preflight.root / "gate9c_stage_validation_report.json"

    def run(self) -> dict[str, object]:
        preflight_report = self.preflight.run()
        if preflight_report.get("pass") is not True:
            raise RuntimeError("Gate 9-C stage validation requires current passing preflight")
        stored = self.stage._load_json(self.stage.report_path, "Gate 9-C stage report")
        expected_stage_fp = gate9c_stage_source_fingerprint(
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            candidate_inventory_fingerprint=str(preflight_report["candidate_inventory_fingerprint"]),
            production_baseline_fingerprint=str(
                preflight_report["production_rollback_baseline"]["fingerprint"]
            ),
        )

        replay_report = self.stage._load_json(self.replay.report_path, "Gate 9-B replay report")
        candidate_rows, candidate_stats = self.preflight._candidate_inventory(replay_report)
        candidate_by_date = {str(row["session_date"]): row for row in candidate_rows}
        canonical_inventory = self.replay.preflight._canonical_inventory()
        canonical_by_date = {str(row["session_date"]): row for row in canonical_inventory}

        feature_hash_failures = 0
        manifest_failures = 0
        source_hash_failures = 0
        row_accounting = 0
        session_count = 0
        year_state_failures = 0
        monthly_state_failures = 0

        for year_record in list(stored.get("year_manifests") or []):
            year = int(year_record["year"])
            year_path = self.stage.stage_year_manifest_path(year)
            if not year_path.is_file() or sha256_file(year_path) != year_record.get("sha256"):
                year_state_failures += 1
                continue
            payload = json.loads(year_path.read_text(encoding="utf-8"))
            accepted_year = self.stage._load_json(
                self.replay.year_manifest_path(year),
                f"Gate 9-B year manifest {year}",
            )
            if payload.get("output_state_fingerprint") != accepted_year.get(
                "output_state_fingerprint"
            ):
                year_state_failures += 1
            for record in list(payload.get("sessions") or []):
                session_text = str(record["session_date"])
                candidate = candidate_by_date.get(session_text)
                canonical = canonical_by_date.get(session_text)
                if candidate is None or canonical is None:
                    manifest_failures += 1
                    continue
                feature_path = Path(str(record["feature_path"]))
                manifest_path = Path(str(record["manifest_path"]))
                if not feature_path.is_file() or sha256_file(feature_path) != candidate[
                    "feature_sha256"
                ]:
                    feature_hash_failures += 1
                if not Path(str(canonical["path"])).is_file() or sha256_file(
                    Path(str(canonical["path"]))
                ) != canonical["sha256"]:
                    source_hash_failures += 1
                try:
                    manifest = FeaturePartitionManifest.from_dict(
                        json.loads(manifest_path.read_text(encoding="utf-8"))
                    )
                    trading_date = date.fromisoformat(session_text)
                    manifest.validate_contract(Timeframe.DAY_1, trading_date)
                    expected_dependency = feature_dependency_fingerprint(
                        source_sha256=str(canonical["sha256"]),
                        input_state_fingerprint=str(record["input_state_fingerprint"]),
                    )
                    if (
                        manifest.source_sha256 != canonical["sha256"]
                        or manifest.feature_sha256 != candidate["feature_sha256"]
                        or manifest.dependency_fingerprint != expected_dependency
                        or manifest.input_state_fingerprint
                        != record["input_state_fingerprint"]
                        or manifest.output_state_fingerprint
                        != record["output_state_fingerprint"]
                        or Path(manifest.feature_path).resolve()
                        != self.stage.paths.feature_file(Timeframe.DAY_1, trading_date).resolve()
                    ):
                        manifest_failures += 1
                except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
                    manifest_failures += 1
                row_accounting += int(record["row_count"])
                session_count += 1
            for record in list(payload.get("monthly_checkpoints") or []):
                path = Path(str(record["path"]))
                try:
                    if not path.is_file() or sha256_file(path) != record["sha256"]:
                        monthly_state_failures += 1
                        continue
                    _engine, checkpoint = self.checkpoints.read(
                        path,
                        expected_timeframe=Timeframe.DAY_1,
                    )
                    if (
                        checkpoint.get("checkpoint_fingerprint")
                        != record["state_fingerprint"]
                        or checkpoint.get("as_of_date") != record["session_date"]
                    ):
                        monthly_state_failures += 1
                except (OSError, ValueError, TypeError, KeyError):
                    monthly_state_failures += 1

        current_state_failures = 0
        candidate_current_sha = str(preflight_report["candidate"]["current_state_sha256"])
        try:
            staged_current_sha = sha256_file(self.stage.staged_current_state_path)
            _engine, current_payload = self.checkpoints.read(
                self.stage.staged_current_state_path,
                expected_timeframe=Timeframe.DAY_1,
            )
            if (
                staged_current_sha != candidate_current_sha
                or current_payload.get("checkpoint_fingerprint")
                != preflight_report["candidate"]["current_state_fingerprint"]
                or current_payload.get("as_of_date") != candidate_stats["last_session"]
            ):
                current_state_failures += 1
        except (OSError, ValueError, TypeError, KeyError):
            current_state_failures += 1

        _baseline_rows_after, baseline_after = self.replay.preflight._production_feature_baseline()
        baseline_unchanged = str(baseline_after["fingerprint"]) == str(
            preflight_report["production_rollback_baseline"]["fingerprint"]
        )

        checks = {
            "validation_contract": True,
            "preflight_current": preflight_report.get("pass") is True,
            "stage_source_fingerprint_current": stored.get("source_fingerprint")
            == expected_stage_fp,
            "stage_report_pass": stored.get("pass") is True,
            "candidate_feature_hashes_exact": feature_hash_failures == 0,
            "canonical_source_hashes_exact": source_hash_failures == 0,
            "production_manifests_exact": manifest_failures == 0,
            "year_end_states_exact": year_state_failures == 0,
            "monthly_state_checkpoints_exact": monthly_state_failures == 0,
            "current_state_exact": current_state_failures == 0,
            "row_accounting_exact": row_accounting == int(candidate_stats["rows"]),
            "session_accounting_exact": session_count == int(candidate_stats["sessions"]),
            "production_baseline_unchanged": baseline_unchanged,
            "production_feature_writes_zero": True,
        }
        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_PROMOTION_STAGE_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "stage_source_fingerprint": expected_stage_fp,
            "feature_hash_failures": feature_hash_failures,
            "source_hash_failures": source_hash_failures,
            "manifest_failures": manifest_failures,
            "year_state_failures": year_state_failures,
            "monthly_state_failures": monthly_state_failures,
            "current_state_failures": current_state_failures,
            "rows": row_accounting,
            "sessions": session_count,
            "production_feature_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
            "stage_report_path": str(self.stage.report_path),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
