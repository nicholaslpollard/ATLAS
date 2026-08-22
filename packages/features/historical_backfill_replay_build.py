from __future__ import annotations

import json
import shutil
import time
from collections import Counter, defaultdict
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.data.paths import MarketDataPaths
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.historical_backfill_replay import (
    DROP_AT_PROVIDER_SEAM,
    GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION,
    HistoricalBackfillFeatureReplayPreflight,
    TRANSFER_IDENTITY_STATE,
)
from packages.features.historical_materializer import HistoricalFeatureMaterializer
from packages.features.incremental import IncrementalFeatureEngine
from packages.features.state_checkpoint import (
    FEATURE_STATE_SCHEMA_VERSION,
    FeatureStateCheckpointStore,
    feature_state_fingerprint,
)
from packages.schemas.feature import (
    CORE_FEATURE_STORAGE_COLUMNS,
    CORE_FEATURE_STORAGE_SCHEMA_VERSION,
    core_feature_select_sql,
)


GATE9_DAILY_REPLAY_CONTRACT_VERSION = (
    "historical-backfill-feature-replay-v1-year-resumable-lifecycle-bound"
)
GATE9_DAILY_REPLAY_PARTITION_CONTRACT_VERSION = (
    "historical-backfill-feature-replay-partition-v1-core-33"
)
GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION = (
    "historical-backfill-feature-replay-year-v1-state-checkpoint-chain"
)
GATE9_DAILY_REPLAY_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-feature-replay-validation-v1-independent-candidate-proof"
)
GATE9_DAILY_REPLAY_ROLE = "ISOLATED_DAILY_FEATURE_REPLAY_NOT_PRODUCTION"


ReplayProgressCallback = Callable[[date, int, int, int], None]


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _sql_path_list(paths: list[Path]) -> str:
    return "[" + ",".join(_sql_string(path) for path in paths) + "]"


def _stable_event_payload(row: dict[str, object]) -> dict[str, object]:
    return {
        "event_date": str(row.get("event_date")),
        "event_type": str(row.get("event_type")),
        "source_symbol": str(row.get("source_symbol") or ""),
        "target_symbol": str(row.get("target_symbol") or ""),
        "reason": str(row.get("reason") or ""),
        "identity_chain_id": str(row.get("identity_chain_id") or ""),
        "segment_id": str(row.get("segment_id") or ""),
        "handoff_gap_calendar_days": (
            None
            if row.get("handoff_gap_calendar_days") is None
            else int(row["handoff_gap_calendar_days"])
        ),
        "seam_decision": str(row.get("seam_decision") or ""),
    }


def lifecycle_content_fingerprint(events: list[dict[str, object]]) -> str:
    payload = [_stable_event_payload(row) for row in events]
    payload.sort(
        key=lambda row: (
            row["event_date"],
            row["event_type"],
            row["source_symbol"],
            row["target_symbol"],
        )
    )
    return stable_source_fingerprint({"events": payload})


def replay_source_fingerprint(
    *,
    preflight_source_fingerprint: str,
    canonical_inventory_fingerprint: str,
    production_feature_baseline_fingerprint: str,
    lifecycle_fingerprint: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": GATE9_DAILY_REPLAY_CONTRACT_VERSION,
            "partition_contract_version": GATE9_DAILY_REPLAY_PARTITION_CONTRACT_VERSION,
            "year_contract_version": GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION,
            "role": GATE9_DAILY_REPLAY_ROLE,
            "preflight_contract_version": GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION,
            "preflight_source_fingerprint": preflight_source_fingerprint,
            "canonical_inventory_fingerprint": canonical_inventory_fingerprint,
            "production_feature_baseline_fingerprint": production_feature_baseline_fingerprint,
            "lifecycle_fingerprint": lifecycle_fingerprint,
            "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "feature_storage_schema_version": CORE_FEATURE_STORAGE_SCHEMA_VERSION,
            "feature_state_schema_version": FEATURE_STATE_SCHEMA_VERSION,
            "timeframe": Timeframe.DAY_1.value,
            "history_start": ALPACA_BACKFILL_START.isoformat(),
        }
    )


def year_source_fingerprint(
    *,
    replay_source_fingerprint_value: str,
    year: int,
    input_state_fingerprint: str,
    canonical_rows: list[dict[str, object]],
    lifecycle_events: list[dict[str, object]],
) -> str:
    canonical_payload = [
        {
            "session_date": str(row["session_date"]),
            "relative_path": str(row["relative_path"]).replace("\\", "/"),
            "sha256": str(row["sha256"]),
        }
        for row in canonical_rows
    ]
    canonical_payload.sort(key=lambda row: row["session_date"])
    event_payload = [_stable_event_payload(row) for row in lifecycle_events]
    event_payload.sort(
        key=lambda row: (
            row["event_date"],
            row["event_type"],
            row["source_symbol"],
            row["target_symbol"],
        )
    )
    return stable_source_fingerprint(
        {
            "year_contract_version": GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION,
            "replay_source_fingerprint": replay_source_fingerprint_value,
            "year": int(year),
            "input_state_fingerprint": input_state_fingerprint,
            "canonical": canonical_payload,
            "lifecycle_events": event_payload,
        }
    )


def apply_lifecycle_events(
    engine: IncrementalFeatureEngine,
    events: list[dict[str, object]],
) -> dict[str, int]:
    counts = {
        "events": 0,
        "identity_transfers": 0,
        "seam_drop_events": 0,
        "seam_drop_hits": 0,
        "seam_drop_misses": 0,
    }
    for row in events:
        event_type = str(row["event_type"])
        source_symbol = str(row["source_symbol"])
        if event_type == TRANSFER_IDENTITY_STATE:
            target_symbol = str(row.get("target_symbol") or "")
            if not target_symbol:
                raise RuntimeError("Gate 9-B transfer event lacks target symbol")
            engine.transfer_state(source_symbol, target_symbol)
            counts["identity_transfers"] += 1
        elif event_type == DROP_AT_PROVIDER_SEAM:
            removed = engine.drop_state(source_symbol)
            counts["seam_drop_events"] += 1
            if removed:
                counts["seam_drop_hits"] += 1
            else:
                counts["seam_drop_misses"] += 1
        else:
            raise RuntimeError(f"Gate 9-B unsupported lifecycle event type: {event_type}")
        counts["events"] += 1
    return counts


def _merge_counts(target: Counter[str], values: dict[str, int]) -> None:
    for key, value in values.items():
        target[key] += int(value)


def _remove_tree_with_retry(path: Path) -> None:
    path = Path(path)
    if not path.exists():
        return
    delay = 0.05
    for attempt in range(1, 9):
        try:
            shutil.rmtree(path)
            return
        except OSError as exc:
            transient = isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in {
                5,
                32,
                33,
            }
            if not transient or attempt >= 8:
                raise
            time.sleep(delay)
            delay = min(0.5, delay * 2.0)


class HistoricalBackfillDailyFeatureReplay:
    """Build Gate 9-B in an isolated candidate namespace with year checkpoints."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.preflight = HistoricalBackfillFeatureReplayPreflight(settings)
        self.checkpoints = FeatureStateCheckpointStore()
        self.feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
        self.root = self.preflight.root / "candidate"
        self.feature_root = self.preflight.candidate_feature_root
        self.manifest_root = self.preflight.candidate_manifest_root
        self.state_root = self.preflight.candidate_state_root
        self.year_manifest_root = self.root / "year_manifests"
        self.report_path = self.root / "gate9_replay_report.json"
        self.current_state_path = self.state_root / "current.json.gz"

    def feature_path(self, trading_date: date) -> Path:
        return (
            self.feature_root
            / f"year={trading_date.year:04d}"
            / f"month={trading_date.month:02d}"
            / f"date={trading_date}"
            / "part-000.parquet"
        )

    def session_manifest_path(self, trading_date: date) -> Path:
        return self.manifest_root / f"year={trading_date.year:04d}" / f"{trading_date}.json"

    def year_manifest_path(self, year: int) -> Path:
        return self.year_manifest_root / f"{year:04d}.json"

    def year_checkpoint_path(self, year: int, last_session: date) -> Path:
        return self.state_root / "yearly" / f"year={year:04d}" / f"{last_session}.json.gz"

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 9-B requires {label}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _load_lifecycle_events(self) -> list[dict[str, object]]:
        path = self.preflight.lifecycle_path
        if not path.is_file():
            raise RuntimeError(f"Gate 9-B lifecycle artifact is missing: {path}")
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(
                f"""
                SELECT *
                FROM read_parquet({_sql_string(path)}, hive_partitioning=false)
                ORDER BY event_date, event_type, source_symbol, target_symbol NULLS LAST
                """
            )
            columns = [item[0] for item in cursor.description]
            rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            con.close()
        for row in rows:
            event_date = row.get("event_date")
            if isinstance(event_date, datetime):
                row["event_date"] = event_date.date()
            elif not isinstance(event_date, date):
                row["event_date"] = date.fromisoformat(str(event_date))
        return rows

    @staticmethod
    def _group_inventory(
        inventory: list[dict[str, object]],
    ) -> dict[int, list[dict[str, object]]]:
        grouped: dict[int, list[dict[str, object]]] = defaultdict(list)
        for row in inventory:
            session = date.fromisoformat(str(row["session_date"]))
            grouped[session.year].append(row)
        for year in grouped:
            grouped[year].sort(key=lambda row: str(row["session_date"]))
        return dict(sorted(grouped.items()))

    @staticmethod
    def _events_by_date(
        events: list[dict[str, object]],
    ) -> dict[date, list[dict[str, object]]]:
        grouped: dict[date, list[dict[str, object]]] = defaultdict(list)
        for row in events:
            event_date = row["event_date"]
            if not isinstance(event_date, date):
                raise RuntimeError("Gate 9-B lifecycle event date was not normalized")
            grouped[event_date].append(row)
        for event_date in grouped:
            grouped[event_date].sort(
                key=lambda row: (
                    str(row["event_type"]),
                    str(row["source_symbol"]),
                    str(row.get("target_symbol") or ""),
                )
            )
        return grouped

    def _load_source(self, source_path: Path) -> pd.DataFrame:
        con = duckdb.connect(":memory:")
        try:
            return con.execute(
                f"""
                SELECT symbol, timestamp_utc, high, low, close, volume
                FROM read_parquet({_sql_string(source_path)}, hive_partitioning=false)
                ORDER BY symbol, timestamp_utc
                """
            ).fetch_df()
        finally:
            con.close()

    def _write_feature_file(self, frame: pd.DataFrame, final_path: Path) -> str:
        if tuple(frame.columns) != CORE_FEATURE_STORAGE_COLUMNS:
            raise RuntimeError(
                "Gate 9-B feature frame schema/order drifted from frozen core feature storage"
            )
        if frame.duplicated(["symbol", "timestamp_utc"]).any():
            raise RuntimeError("Gate 9-B feature frame contains duplicate market keys")
        numeric = frame[self.feature_names].to_numpy(dtype="float64", na_value=np.nan)
        if int(np.isinf(numeric).sum()) != 0:
            raise RuntimeError("Gate 9-B feature frame contains infinite feature values")

        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(final_path)
        con = duckdb.connect(":memory:")
        try:
            con.register("feature_df", frame)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            select_sql = core_feature_select_sql(table_alias="feature_df")
            con.execute(
                f"""
                COPY (
                    SELECT
                    {select_sql}
                    FROM feature_df
                    ORDER BY symbol, timestamp_utc
                )
                TO {_sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
        finally:
            con.close()
        replace_with_retry(temp, final_path)
        return sha256_file(final_path)

    def _session_manifest(
        self,
        *,
        trading_date: date,
        source_row: dict[str, object],
        feature_path: Path,
        feature_sha256: str,
        row_count: int,
        symbol_count: int,
        events: list[dict[str, object]],
        replay_fp: str,
    ) -> dict[str, object]:
        return {
            "contract_version": GATE9_DAILY_REPLAY_PARTITION_CONTRACT_VERSION,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "replay_source_fingerprint": replay_fp,
            "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "feature_storage_schema_version": CORE_FEATURE_STORAGE_SCHEMA_VERSION,
            "timeframe": Timeframe.DAY_1.value,
            "session_date": trading_date.isoformat(),
            "source_path": str(source_row["path"]),
            "source_relative_path": str(source_row["relative_path"]).replace("\\", "/"),
            "source_sha256": str(source_row["sha256"]),
            "lifecycle_event_count": len(events),
            "lifecycle_event_fingerprint": lifecycle_content_fingerprint(events),
            "feature_path": str(feature_path),
            "feature_sha256": feature_sha256,
            "row_count": int(row_count),
            "symbol_count": int(symbol_count),
            "duplicate_keys": 0,
            "infinite_feature_values": 0,
        }

    def _write_session_manifest(
        self,
        trading_date: date,
        payload: dict[str, object],
    ) -> str:
        path = self.session_manifest_path(trading_date)
        atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return sha256_file(path)

    def _clean_year(self, year: int) -> None:
        _remove_tree_with_retry(self.feature_root / f"year={year:04d}")
        _remove_tree_with_retry(self.manifest_root / f"year={year:04d}")
        _remove_tree_with_retry(self.state_root / "yearly" / f"year={year:04d}")
        self.year_manifest_path(year).unlink(missing_ok=True)

    def _validate_year_manifest(
        self,
        *,
        year: int,
        canonical_rows: list[dict[str, object]],
        year_events: list[dict[str, object]],
        replay_fp: str,
        input_state_fingerprint: str,
    ) -> tuple[bool, dict[str, Any] | None, IncrementalFeatureEngine | None]:
        path = self.year_manifest_path(year)
        if not path.is_file():
            return False, None, None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            expected_year_fp = year_source_fingerprint(
                replay_source_fingerprint_value=replay_fp,
                year=year,
                input_state_fingerprint=input_state_fingerprint,
                canonical_rows=canonical_rows,
                lifecycle_events=year_events,
            )
            if payload.get("contract_version") != GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION:
                return False, None, None
            if payload.get("replay_source_fingerprint") != replay_fp:
                return False, None, None
            if payload.get("year_source_fingerprint") != expected_year_fp:
                return False, None, None
            if payload.get("input_state_fingerprint") != input_state_fingerprint:
                return False, None, None
            session_records = list(payload.get("sessions") or [])
            if len(session_records) != len(canonical_rows):
                return False, None, None
            by_date = {str(row["session_date"]): row for row in canonical_rows}
            if len(by_date) != len(canonical_rows):
                return False, None, None
            for record in session_records:
                session_text = str(record.get("session_date"))
                source = by_date.get(session_text)
                if source is None:
                    return False, None, None
                if record.get("source_sha256") != source["sha256"]:
                    return False, None, None
                feature_path = Path(str(record.get("feature_path") or ""))
                manifest_path = Path(str(record.get("manifest_path") or ""))
                if not feature_path.is_file() or not manifest_path.is_file():
                    return False, None, None
                if sha256_file(feature_path) != record.get("feature_sha256"):
                    return False, None, None
                if sha256_file(manifest_path) != record.get("manifest_sha256"):
                    return False, None, None
                session_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                if session_manifest.get("source_sha256") != source["sha256"]:
                    return False, None, None
                if session_manifest.get("feature_sha256") != record.get("feature_sha256"):
                    return False, None, None
                if session_manifest.get("replay_source_fingerprint") != replay_fp:
                    return False, None, None
            checkpoint_path = Path(str(payload.get("checkpoint_path") or ""))
            if not checkpoint_path.is_file():
                return False, None, None
            if sha256_file(checkpoint_path) != payload.get("checkpoint_sha256"):
                return False, None, None
            engine, checkpoint = self.checkpoints.read(
                checkpoint_path,
                expected_timeframe=Timeframe.DAY_1,
            )
            if checkpoint.get("checkpoint_fingerprint") != payload.get(
                "output_state_fingerprint"
            ):
                return False, None, None
            if checkpoint.get("as_of_date") != payload.get("last_session"):
                return False, None, None
            return True, payload, engine
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False, None, None

    def _build_year(
        self,
        *,
        year: int,
        canonical_rows: list[dict[str, object]],
        events_by_date: dict[date, list[dict[str, object]]],
        year_events: list[dict[str, object]],
        engine: IncrementalFeatureEngine,
        replay_fp: str,
        input_state_fingerprint: str,
        progress: ReplayProgressCallback | None,
    ) -> tuple[dict[str, object], Counter[str], IncrementalFeatureEngine]:
        self._clean_year(year)
        session_records: list[dict[str, object]] = []
        lifecycle_counts: Counter[str] = Counter()
        total = len(canonical_rows)
        year_rows = 0

        for index, source_row in enumerate(canonical_rows, start=1):
            trading_date = date.fromisoformat(str(source_row["session_date"]))
            session_events = events_by_date.get(trading_date, [])
            _merge_counts(lifecycle_counts, apply_lifecycle_events(engine, session_events))
            source_path = Path(str(source_row["path"]))
            if not source_path.is_file():
                raise RuntimeError(f"Gate 9-B canonical source vanished: {source_path}")
            if sha256_file(source_path) != str(source_row["sha256"]):
                raise RuntimeError(f"Gate 9-B canonical source hash changed: {source_path}")

            bars = self._load_source(source_path)
            features = HistoricalFeatureMaterializer._update_engine(
                engine,
                bars,
                self.feature_names,
            )
            if len(features) != len(bars):
                raise RuntimeError("Gate 9-B feature row count differs from canonical source")
            if not features["symbol"].equals(bars["symbol"].astype(str)):
                raise RuntimeError("Gate 9-B feature symbols differ from canonical source order")
            if not features["timestamp_utc"].equals(bars["timestamp_utc"]):
                raise RuntimeError("Gate 9-B feature timestamps differ from canonical source order")

            feature_path = self.feature_path(trading_date)
            feature_sha = self._write_feature_file(features, feature_path)
            session_manifest = self._session_manifest(
                trading_date=trading_date,
                source_row=source_row,
                feature_path=feature_path,
                feature_sha256=feature_sha,
                row_count=len(features),
                symbol_count=int(features["symbol"].nunique()),
                events=session_events,
                replay_fp=replay_fp,
            )
            manifest_sha = self._write_session_manifest(trading_date, session_manifest)
            session_records.append(
                {
                    "session_date": trading_date.isoformat(),
                    "source_sha256": str(source_row["sha256"]),
                    "feature_path": str(feature_path),
                    "feature_sha256": feature_sha,
                    "manifest_path": str(self.session_manifest_path(trading_date)),
                    "manifest_sha256": manifest_sha,
                    "row_count": int(len(features)),
                    "symbol_count": int(features["symbol"].nunique()),
                    "lifecycle_event_count": len(session_events),
                }
            )
            year_rows += len(features)
            if progress is not None:
                progress(trading_date, index, total, year_rows)

        if not canonical_rows:
            raise RuntimeError(f"Gate 9-B year {year} has no canonical sessions")
        last_session = date.fromisoformat(str(canonical_rows[-1]["session_date"]))
        output_state_fp = self.checkpoints.write(
            self.year_checkpoint_path(year, last_session),
            engine,
            timeframe=Timeframe.DAY_1,
            as_of_date=last_session.isoformat(),
        )
        checkpoint_path = self.year_checkpoint_path(year, last_session)
        year_fp = year_source_fingerprint(
            replay_source_fingerprint_value=replay_fp,
            year=year,
            input_state_fingerprint=input_state_fingerprint,
            canonical_rows=canonical_rows,
            lifecycle_events=year_events,
        )
        payload: dict[str, object] = {
            "contract_version": GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION,
            "created_at_utc": datetime.now(UTC).isoformat(),
            "replay_source_fingerprint": replay_fp,
            "year_source_fingerprint": year_fp,
            "year": int(year),
            "input_state_fingerprint": input_state_fingerprint,
            "output_state_fingerprint": output_state_fp,
            "first_session": str(canonical_rows[0]["session_date"]),
            "last_session": last_session.isoformat(),
            "session_count": len(session_records),
            "row_count": int(year_rows),
            "lifecycle": dict(sorted(lifecycle_counts.items())),
            "checkpoint_path": str(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
            "sessions": session_records,
        }
        manifest_path = self.year_manifest_path(year)
        atomic_write_text(
            manifest_path,
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
        )
        return payload, lifecycle_counts, engine

    def run(
        self,
        *,
        force: bool = False,
        progress: ReplayProgressCallback | None = None,
    ) -> dict[str, object]:
        preflight_report = self.preflight.run()
        if preflight_report.get("pass") is not True:
            raise RuntimeError("Gate 9-B requires accepted Gate 9-A preflight")

        canonical_inventory = self.preflight._canonical_inventory()
        grouped_inventory = self._group_inventory(canonical_inventory)
        events = self._load_lifecycle_events()
        events_by_date = self._events_by_date(events)
        lifecycle_fp = lifecycle_content_fingerprint(events)
        replay_fp = replay_source_fingerprint(
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            canonical_inventory_fingerprint=str(
                preflight_report["canonical_inventory_fingerprint"]
            ),
            production_feature_baseline_fingerprint=str(
                preflight_report["production_feature_baseline_fingerprint"]
            ),
            lifecycle_fingerprint=lifecycle_fp,
        )

        engine = IncrementalFeatureEngine()
        input_state_fp = feature_state_fingerprint(
            engine,
            timeframe=Timeframe.DAY_1,
            as_of_date="genesis",
        )
        year_manifests: list[dict[str, object]] = []
        lifecycle_totals: Counter[str] = Counter()
        rebuilt_years: list[int] = []
        reused_years: list[int] = []
        must_rebuild = bool(force)

        for year, canonical_rows in grouped_inventory.items():
            year_events = [
                row
                for row in events
                if isinstance(row["event_date"], date) and row["event_date"].year == year
            ]
            valid = False
            existing: dict[str, Any] | None = None
            restored: IncrementalFeatureEngine | None = None
            if not must_rebuild:
                valid, existing, restored = self._validate_year_manifest(
                    year=year,
                    canonical_rows=canonical_rows,
                    year_events=year_events,
                    replay_fp=replay_fp,
                    input_state_fingerprint=input_state_fp,
                )
            if valid and existing is not None and restored is not None:
                engine = restored
                year_manifests.append(existing)
                _merge_counts(
                    lifecycle_totals,
                    {
                        key: int(value)
                        for key, value in dict(existing.get("lifecycle") or {}).items()
                    },
                )
                input_state_fp = str(existing["output_state_fingerprint"])
                reused_years.append(year)
                continue

            must_rebuild = True
            built, year_counts, engine = self._build_year(
                year=year,
                canonical_rows=canonical_rows,
                events_by_date=events_by_date,
                year_events=year_events,
                engine=engine,
                replay_fp=replay_fp,
                input_state_fingerprint=input_state_fp,
                progress=progress,
            )
            year_manifests.append(built)
            lifecycle_totals.update(year_counts)
            input_state_fp = str(built["output_state_fingerprint"])
            rebuilt_years.append(year)

        if not year_manifests:
            raise RuntimeError("Gate 9-B produced no year manifests")
        final_session = date.fromisoformat(str(year_manifests[-1]["last_session"]))
        current_state_fp = self.checkpoints.write(
            self.current_state_path,
            engine,
            timeframe=Timeframe.DAY_1,
            as_of_date=final_session.isoformat(),
        )
        if current_state_fp != str(year_manifests[-1]["output_state_fingerprint"]):
            raise RuntimeError("Gate 9-B current state differs from final year checkpoint")

        _inventory_after, production_baseline_after = self.preflight._production_feature_baseline()
        production_baseline_unchanged = (
            str(production_baseline_after["fingerprint"])
            == str(preflight_report["production_feature_baseline_fingerprint"])
        )

        total_rows = sum(int(row["row_count"]) for row in year_manifests)
        total_sessions = sum(int(row["session_count"]) for row in year_manifests)
        expected_lifecycle = dict(preflight_report["lifecycle"])
        checks = {
            "preflight_pass": preflight_report.get("pass") is True,
            "year_accounting_exact": len(year_manifests) == len(grouped_inventory),
            "row_accounting_exact": total_rows == int(preflight_report["canonical"]["rows"]),
            "session_accounting_exact": total_sessions
            == int(preflight_report["canonical"]["sessions"]),
            "identity_transfers_applied_exact": int(lifecycle_totals["identity_transfers"])
            == int(expected_lifecycle["identity_transfers"]),
            "seam_drop_events_applied_exact": int(lifecycle_totals["seam_drop_events"])
            == int(expected_lifecycle["seam_drop_events"]),
            "all_lifecycle_events_consumed": int(lifecycle_totals["events"])
            == int(preflight_report["lifecycle_events"]),
            "current_state_matches_final_year": current_state_fp
            == str(year_manifests[-1]["output_state_fingerprint"]),
            "production_feature_baseline_unchanged": production_baseline_unchanged,
            "candidate_namespace_isolated": self.feature_root.resolve()
            != (
                self.settings.resolved_path(self.settings.data.paths.derived)
                / "features"
                / "1d"
            ).resolve(),
            "production_feature_writes_zero": True,
        }
        report: dict[str, object] = {
            "contract_version": GATE9_DAILY_REPLAY_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_DAILY_REPLAY_ROLE,
            "source_fingerprint": replay_fp,
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "canonical_inventory_fingerprint": preflight_report[
                "canonical_inventory_fingerprint"
            ],
            "production_feature_baseline_fingerprint": preflight_report[
                "production_feature_baseline_fingerprint"
            ],
            "lifecycle_fingerprint": lifecycle_fp,
            "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "feature_storage_schema_version": CORE_FEATURE_STORAGE_SCHEMA_VERSION,
            "feature_state_schema_version": FEATURE_STATE_SCHEMA_VERSION,
            "timeframe": Timeframe.DAY_1.value,
            "feature_count": len(self.feature_names),
            "candidate_rows": total_rows,
            "candidate_sessions": total_sessions,
            "candidate_symbols_expected": int(preflight_report["canonical"]["symbols"]),
            "first_session": str(year_manifests[0]["first_session"]),
            "last_session": str(year_manifests[-1]["last_session"]),
            "rebuilt_years": rebuilt_years,
            "reused_years": reused_years,
            "lifecycle": dict(sorted(lifecycle_totals.items())),
            "year_manifests": [
                {
                    "year": int(row["year"]),
                    "path": str(self.year_manifest_path(int(row["year"]))),
                    "sha256": sha256_file(self.year_manifest_path(int(row["year"]))),
                    "row_count": int(row["row_count"]),
                    "session_count": int(row["session_count"]),
                    "output_state_fingerprint": str(row["output_state_fingerprint"]),
                }
                for row in year_manifests
            ],
            "current_state_path": str(self.current_state_path),
            "current_state_sha256": sha256_file(self.current_state_path),
            "current_state_fingerprint": current_state_fp,
            "production_feature_baseline_after": production_baseline_after,
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
