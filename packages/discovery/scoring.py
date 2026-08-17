from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import FeaturePartitionStore, sha256_file
from packages.schemas.candidate import DiscoveryActivityTier
from packages.schemas.discovery_score import (
    DISCOVERY_SCORE_CONTRACT_VERSION,
    DiscoveryDirection,
    DiscoveryScoreRecord,
)
from packages.schemas.universe import UniverseRoute

from .directional_score import (
    DIRECTIONAL_SCORE_POLICY_VERSION,
    aggregate_multitimeframe,
)
from .scanner import DISCOVERY_FOUNDATION_MANIFEST_VERSION
from .setup_scores import REQUIRED_SCORE_COLUMNS, SETUP_SCORE_POLICY_VERSION, score_timeframe
from .state_machine import (
    ACTIVE_DISCOVERY_STATE_POLICY,
    DISCOVERY_STATE_POLICY_VERSION,
    DiscoveryStatePolicy,
)


DISCOVERY_SCORE_MANIFEST_VERSION = "discovery-score-manifest-v1-foundation-feature-lineage"


@dataclass(frozen=True, slots=True)
class DiscoveryScoreBuildResult:
    as_of_date: date
    scored_count: int
    state_counts: dict[str, int]
    direction_counts: dict[str, int]
    top_setup_counts: dict[str, int]
    timeframe_coverage_counts: dict[str, int]
    priority_quantiles: dict[str, float]
    dependency_fingerprint: str
    snapshot_sha256: str
    snapshot_path: Path
    manifest_path: Path
    wall_seconds: float
    skipped: bool


class DiscoverySetupScanner:
    """Vectorized multi-timeframe evidence scorer for consideration-required names."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        state_policy: DiscoveryStatePolicy = ACTIVE_DISCOVERY_STATE_POLICY,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.feature_store = FeaturePartitionStore(settings)
        self.state_policy = state_policy

    @staticmethod
    def _json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON manifest: {path}") from exc

    @staticmethod
    def _fingerprint(payload: dict[str, object]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    @staticmethod
    def _routes(value: object) -> tuple[UniverseRoute, ...]:
        if value is None:
            return ()
        if hasattr(value, "tolist"):
            value = value.tolist()
        if isinstance(value, str):
            text = value.strip()
            value = json.loads(text) if text.startswith("[") else [text]
        if not isinstance(value, (list, tuple, set)):
            value = [value]
        return tuple(sorted({UniverseRoute(str(item)) for item in value}, key=lambda item: item.value))

    def _upstream(self, as_of_date: date) -> tuple[dict[str, object], dict[str, Path]]:
        foundation_path = self.paths.discovery_snapshot_file(as_of_date)
        foundation_manifest_path = self.paths.discovery_snapshot_manifest(as_of_date)
        if not foundation_path.is_file() or not foundation_manifest_path.is_file():
            raise FileNotFoundError(f"Phase 8 discovery foundation is missing for {as_of_date}")
        foundation = self._json(foundation_manifest_path)
        if foundation.get("manifest_version") != DISCOVERY_FOUNDATION_MANIFEST_VERSION:
            raise ValueError("Discovery foundation manifest contract is stale")
        if foundation.get("snapshot_sha256") != sha256_file(foundation_path):
            raise ValueError("Discovery foundation snapshot hash does not match its manifest")

        expected = foundation.get("upstream_lineage")
        if not isinstance(expected, dict):
            raise ValueError("Discovery foundation is missing upstream lineage")

        feature_paths: dict[str, Path] = {}
        current_hashes: dict[str, str] = {}
        for timeframe, key in (
            (Timeframe.DAY_1, "1d"),
            (Timeframe.HOUR_4, "4h"),
            (Timeframe.HOUR_1, "1h"),
        ):
            manifest = self.feature_store.read_manifest(timeframe, as_of_date)
            if manifest is None:
                raise FileNotFoundError(f"Phase 6 {key} feature manifest is missing for {as_of_date}")
            path = self.paths.feature_file(timeframe, as_of_date)
            if not path.is_file():
                raise FileNotFoundError(f"Phase 6 {key} feature partition is missing: {path}")
            feature_paths[key] = path
            current_hashes[key] = manifest.feature_sha256

        expected_map = {
            "1d": expected.get("features_1d_sha256"),
            "4h": expected.get("features_4h_sha256"),
            "1h": expected.get("features_1h_sha256"),
        }
        if current_hashes != expected_map:
            raise ValueError(
                "Discovery foundation is stale relative to current Phase 6 features; "
                "rebuild the foundation before scoring"
            )

        lineage = {
            "foundation_snapshot_sha256": str(foundation["snapshot_sha256"]),
            "features_1d_sha256": current_hashes["1d"],
            "features_4h_sha256": current_hashes["4h"],
            "features_1h_sha256": current_hashes["1h"],
        }
        paths = {
            "foundation": foundation_path,
            "features_1d": feature_paths["1d"],
            "features_4h": feature_paths["4h"],
            "features_1h": feature_paths["1h"],
        }
        return lineage, paths

    def _dependency(self, as_of_date: date, lineage: dict[str, object]) -> str:
        return self._fingerprint(
            {
                "manifest_version": DISCOVERY_SCORE_MANIFEST_VERSION,
                "score_contract": DISCOVERY_SCORE_CONTRACT_VERSION,
                "setup_score_policy": SETUP_SCORE_POLICY_VERSION,
                "directional_score_policy": DIRECTIONAL_SCORE_POLICY_VERSION,
                "state_policy": DISCOVERY_STATE_POLICY_VERSION,
                "state_thresholds": {
                    "watch": self.state_policy.watch_priority,
                    "warm": self.state_policy.warm_priority,
                    "hot": self.state_policy.hot_priority,
                    "hot_directional": self.state_policy.hot_directional_evidence,
                },
                "as_of_date": as_of_date.isoformat(),
                "lineage": lineage,
            }
        )

    def _load_joined(self, paths: dict[str, Path]) -> pd.DataFrame:
        selected = ",\n".join(REQUIRED_SCORE_COLUMNS)
        daily_aliases = ",\n".join(f"d.{name} AS d_{name}" for name in REQUIRED_SCORE_COLUMNS)
        h4_aliases = ",\n".join(f"h4.{name} AS h4_{name}" for name in REQUIRED_SCORE_COLUMNS)
        h1_aliases = ",\n".join(f"h1.{name} AS h1_{name}" for name in REQUIRED_SCORE_COLUMNS)
        con = connect_utc(":memory:")
        try:
            foundation = sql_string(paths["foundation"])
            daily = sql_string(paths["features_1d"])
            h4 = sql_string(paths["features_4h"])
            h1 = sql_string(paths["features_1h"])
            return con.execute(
                f"""
                WITH c AS (
                    SELECT instrument_id, ticker, security_type, routes, activity_tier,
                           broad_discovery_ready, mandatory_route
                    FROM read_parquet({foundation})
                    WHERE consideration_required = TRUE
                ), d AS (
                    SELECT symbol, {selected}
                    FROM (
                        SELECT symbol, timestamp_utc, {selected},
                               row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                        FROM read_parquet({daily})
                    )
                    WHERE rn = 1
                ), h4 AS (
                    SELECT symbol, {selected}
                    FROM (
                        SELECT symbol, timestamp_utc, {selected},
                               row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                        FROM read_parquet({h4})
                        WHERE session_segment = 'regular'
                    )
                    WHERE rn = 1
                ), h1 AS (
                    SELECT symbol, {selected}
                    FROM (
                        SELECT symbol, timestamp_utc, {selected},
                               row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                        FROM read_parquet({h1})
                        WHERE session_segment = 'regular'
                    )
                    WHERE rn = 1
                )
                SELECT c.*,
                       d.symbol IS NOT NULL AS has_1d_feature_row,
                       h4.symbol IS NOT NULL AS has_regular_4h_feature_row,
                       h1.symbol IS NOT NULL AS has_regular_1h_feature_row,
                       {daily_aliases},
                       {h4_aliases},
                       {h1_aliases}
                FROM c
                LEFT JOIN d ON d.symbol = c.ticker
                LEFT JOIN h4 ON h4.symbol = c.ticker
                LEFT JOIN h1 ON h1.symbol = c.ticker
                ORDER BY c.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()

    @staticmethod
    def _tf_frame(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
        return pd.DataFrame(
            {name: frame[f"{prefix}_{name}"] for name in REQUIRED_SCORE_COLUMNS},
            index=frame.index,
        )

    def _existing(
        self,
        *,
        dependency: str,
        snapshot_path: Path,
        manifest_path: Path,
    ) -> dict[str, Any] | None:
        if not snapshot_path.is_file() or not manifest_path.is_file():
            return None
        try:
            manifest = self._json(manifest_path)
        except ValueError:
            return None
        if manifest.get("manifest_version") != DISCOVERY_SCORE_MANIFEST_VERSION:
            return None
        if manifest.get("dependency_fingerprint") != dependency:
            return None
        return manifest if manifest.get("snapshot_sha256") == sha256_file(snapshot_path) else None

    @staticmethod
    def _result(
        *,
        manifest: dict[str, Any],
        snapshot_path: Path,
        manifest_path: Path,
        wall_seconds: float,
        skipped: bool,
    ) -> DiscoveryScoreBuildResult:
        return DiscoveryScoreBuildResult(
            as_of_date=date.fromisoformat(str(manifest["as_of_date"])),
            scored_count=int(manifest["scored_count"]),
            state_counts={str(k): int(v) for k, v in manifest["state_counts"].items()},
            direction_counts={str(k): int(v) for k, v in manifest["direction_counts"].items()},
            top_setup_counts={str(k): int(v) for k, v in manifest["top_setup_counts"].items()},
            timeframe_coverage_counts={
                str(k): int(v) for k, v in manifest["timeframe_coverage_counts"].items()
            },
            priority_quantiles={str(k): float(v) for k, v in manifest["priority_quantiles"].items()},
            dependency_fingerprint=str(manifest["dependency_fingerprint"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=wall_seconds,
            skipped=skipped,
        )

    def build(self, as_of_date: date) -> DiscoveryScoreBuildResult:
        started = perf_counter()
        lineage, paths = self._upstream(as_of_date)
        dependency = self._dependency(as_of_date, lineage)
        snapshot_path = self.paths.discovery_score_file(as_of_date)
        manifest_path = self.paths.discovery_score_manifest(as_of_date)
        existing = self._existing(
            dependency=dependency,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
        )
        if existing is not None:
            return self._result(
                manifest=existing,
                snapshot_path=snapshot_path,
                manifest_path=manifest_path,
                wall_seconds=perf_counter() - started,
                skipped=True,
            )

        frame = self._load_joined(paths)
        timeframe_frames = {
            "1d": score_timeframe(self._tf_frame(frame, "d")),
            "4h": score_timeframe(self._tf_frame(frame, "h4")),
            "1h": score_timeframe(self._tf_frame(frame, "h1")),
        }
        aggregate = aggregate_multitimeframe(timeframe_frames)

        records: list[DiscoveryScoreRecord] = []
        state_counts: Counter[str] = Counter()
        direction_counts: Counter[str] = Counter()
        top_setup_counts: Counter[str] = Counter()
        coverage_counts: Counter[str] = Counter()
        for idx, row in frame.iterrows():
            one_d = bool(timeframe_frames["1d"].loc[idx, "score_input_available"])
            four_h = bool(timeframe_frames["4h"].loc[idx, "score_input_available"])
            one_h = bool(timeframe_frames["1h"].loc[idx, "score_input_available"])
            scored_timeframes = int(one_d) + int(four_h) + int(one_h)
            direction = DiscoveryDirection(str(aggregate.loc[idx, "direction"]))
            bull = float(aggregate.loc[idx, "bull_evidence"])
            bear = float(aggregate.loc[idx, "bear_evidence"])
            priority = float(aggregate.loc[idx, "priority_score"])
            raw_state = self.state_policy.classify(
                priority_score=priority,
                bull_evidence=bull,
                bear_evidence=bear,
                direction=direction,
            )
            record = DiscoveryScoreRecord(
                instrument_id=str(row["instrument_id"]),
                ticker=str(row["ticker"]),
                as_of_date=as_of_date,
                security_type=None if pd.isna(row["security_type"]) else str(row["security_type"]),
                routes=self._routes(row["routes"]),
                activity_tier=DiscoveryActivityTier(str(row["activity_tier"])),
                broad_discovery_ready=bool(row["broad_discovery_ready"]),
                mandatory_route=bool(row["mandatory_route"]),
                has_1d_score_input=one_d,
                has_regular_4h_score_input=four_h,
                has_regular_1h_score_input=one_h,
                scored_timeframes=scored_timeframes,
                trend_score=float(aggregate.loc[idx, "trend_score"]),
                momentum_score=float(aggregate.loc[idx, "momentum_score"]),
                breakout_score=float(aggregate.loc[idx, "breakout_score"]),
                pullback_score=float(aggregate.loc[idx, "pullback_score"]),
                reversal_score=float(aggregate.loc[idx, "reversal_score"]),
                mean_reversion_score=float(aggregate.loc[idx, "mean_reversion_score"]),
                relative_strength_score=float(aggregate.loc[idx, "relative_strength_score"]),
                unusual_volume_score=float(aggregate.loc[idx, "unusual_volume_score"]),
                volatility_expansion_score=float(aggregate.loc[idx, "volatility_expansion_score"]),
                breakdown_score=float(aggregate.loc[idx, "breakdown_score"]),
                bull_evidence=bull,
                bear_evidence=bear,
                priority_score=priority,
                top_setup=str(aggregate.loc[idx, "top_setup"]),
                direction=direction,
                raw_state=raw_state,
            )
            records.append(record)
            state_counts.update([record.raw_state.value])
            direction_counts.update([record.direction.value])
            top_setup_counts.update([record.top_setup])
            coverage_counts.update([str(record.scored_timeframes)])

        output_records: list[dict[str, object]] = []
        for record in records:
            item = record.model_dump(mode="python")
            item["routes"] = [route.value for route in record.routes]
            item["activity_tier"] = record.activity_tier.value
            item["direction"] = record.direction.value
            item["raw_state"] = record.raw_state.value
            output_records.append(item)
        output = pd.DataFrame.from_records(output_records)

        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(snapshot_path)
        con = connect_utc(":memory:")
        try:
            con.register("atlas_discovery_scores", output)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (SELECT * FROM atlas_discovery_scores ORDER BY instrument_id)
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, snapshot_path)
        finally:
            con.close()

        snapshot_sha = sha256_file(snapshot_path)
        priorities = output["priority_score"] if not output.empty else pd.Series(dtype="float64")
        quantiles = {
            key: float(priorities.quantile(q)) if not priorities.empty else 0.0
            for key, q in (("p50", 0.50), ("p75", 0.75), ("p90", 0.90), ("p95", 0.95), ("p99", 0.99))
        }
        manifest = {
            "manifest_version": DISCOVERY_SCORE_MANIFEST_VERSION,
            "score_contract_version": DISCOVERY_SCORE_CONTRACT_VERSION,
            "setup_score_policy_version": SETUP_SCORE_POLICY_VERSION,
            "directional_score_policy_version": DIRECTIONAL_SCORE_POLICY_VERSION,
            "state_policy_version": DISCOVERY_STATE_POLICY_VERSION,
            "state_thresholds": {
                "watch": self.state_policy.watch_priority,
                "warm": self.state_policy.warm_priority,
                "hot": self.state_policy.hot_priority,
                "hot_directional": self.state_policy.hot_directional_evidence,
            },
            "as_of_date": as_of_date.isoformat(),
            "dependency_fingerprint": dependency,
            "upstream_lineage": lineage,
            "scored_count": len(records),
            "state_counts": dict(sorted(state_counts.items())),
            "direction_counts": dict(sorted(direction_counts.items())),
            "top_setup_counts": dict(sorted(top_setup_counts.items())),
            "timeframe_coverage_counts": dict(sorted(coverage_counts.items())),
            "priority_quantiles": quantiles,
            "snapshot_path": str(snapshot_path.resolve()),
            "snapshot_sha256": snapshot_sha,
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return self._result(
            manifest=manifest,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=perf_counter() - started,
            skipped=False,
        )
