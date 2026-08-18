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
from packages.schemas.candidate import DiscoveryCandidate
from packages.schemas.universe import UNIVERSE_CONTRACT_VERSION, UniverseRoute
from packages.universe.manager import UNIVERSE_MANIFEST_VERSION

from .filter_policy import (
    ACTIVE_DISCOVERY_FILTER_POLICY,
    DISCOVERY_FILTER_POLICY_VERSION,
    DiscoveryFilterPolicy,
)


DISCOVERY_FOUNDATION_MANIFEST_VERSION = "discovery-foundation-manifest-v1-upstream-lineage-bound"


@dataclass(frozen=True, slots=True)
class DiscoveryFoundationBuildResult:
    as_of_date: date
    source_universe_count: int
    data_health_pass_count: int
    activity_pass_count: int
    broad_discovery_ready_count: int
    mandatory_route_count: int
    consideration_required_count: int
    intraday_ready_count: int
    activity_tier_counts: dict[str, int]
    reason_counts: dict[str, int]
    security_type_counts: dict[str, int]
    dependency_fingerprint: str
    snapshot_sha256: str
    snapshot_path: Path
    manifest_path: Path
    wall_seconds: float
    skipped: bool


class DiscoveryFoundationScanner:
    """Build the cheap Phase 8 health/activity foundation for the routed universe.

    Input content identity comes from authoritative Phase 6/7 manifests. The scanner
    intentionally does not deep-hash large upstream feature files on every run.
    """

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        policy: DiscoveryFilterPolicy = ACTIVE_DISCOVERY_FILTER_POLICY,
    ) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.policy = policy
        self.feature_store = FeaturePartitionStore(settings)

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
            if text.startswith("["):
                value = json.loads(text)
            else:
                value = [text]
        if not isinstance(value, (list, tuple, set)):
            value = [value]
        routes = {UniverseRoute(str(item)) for item in value}
        return tuple(sorted(routes, key=lambda item: item.value))

    @staticmethod
    def _optional(value: object) -> object | None:
        try:
            if pd.isna(value):
                return None
        except (TypeError, ValueError):
            pass
        return value

    @staticmethod
    def _optional_float(value: object) -> float | None:
        value = DiscoveryFoundationScanner._optional(value)
        return None if value is None else float(value)

    def _upstream_lineage(self, as_of_date: date) -> tuple[dict[str, object], dict[str, Path]]:
        universe_path = self.paths.universe_snapshot_file(as_of_date)
        universe_manifest_path = self.paths.universe_snapshot_manifest(as_of_date)
        if not universe_path.is_file() or not universe_manifest_path.is_file():
            raise FileNotFoundError(f"Phase 7 universe is missing for {as_of_date}")
        universe_manifest = self._json(universe_manifest_path)
        if universe_manifest.get("manifest_version") != UNIVERSE_MANIFEST_VERSION:
            raise ValueError("Phase 7 universe manifest contract is stale")
        if universe_manifest.get("universe_contract_version") != UNIVERSE_CONTRACT_VERSION:
            raise ValueError("Phase 7 universe contract is stale")

        manifests = {}
        feature_paths: dict[str, Path] = {}
        for timeframe, key in (
            (Timeframe.DAY_1, "1d"),
            (Timeframe.HOUR_4, "4h"),
            (Timeframe.HOUR_1, "1h"),
        ):
            record = self.feature_store.read_manifest(timeframe, as_of_date)
            if record is None:
                raise FileNotFoundError(f"Phase 6 {key} feature manifest is missing for {as_of_date}")
            manifests[key] = record
            path = self.paths.feature_file(timeframe, as_of_date)
            if not path.is_file():
                raise FileNotFoundError(f"Phase 6 {key} feature partition is missing: {path}")
            feature_paths[key] = path

        daily_path = self.paths.canonical_file(Timeframe.DAY_1, as_of_date)
        if not daily_path.is_file():
            raise FileNotFoundError(f"Canonical 1d partition is missing: {daily_path}")

        lineage = {
            "universe_snapshot_sha256": str(universe_manifest["snapshot_sha256"]),
            "canonical_1d_sha256": manifests["1d"].source_sha256,
            "features_1d_sha256": manifests["1d"].feature_sha256,
            "features_4h_sha256": manifests["4h"].feature_sha256,
            "features_1h_sha256": manifests["1h"].feature_sha256,
        }
        paths = {
            "universe": universe_path,
            "canonical_1d": daily_path,
            "features_1d": feature_paths["1d"],
            "features_4h": feature_paths["4h"],
            "features_1h": feature_paths["1h"],
        }
        return lineage, paths

    def _dependency_fingerprint(self, as_of_date: date, lineage: dict[str, object]) -> str:
        return self._fingerprint(
            {
                "manifest_version": DISCOVERY_FOUNDATION_MANIFEST_VERSION,
                "policy_version": DISCOVERY_FILTER_POLICY_VERSION,
                "policy_fingerprint": self.policy.fingerprint,
                "as_of_date": as_of_date.isoformat(),
                "lineage": lineage,
            }
        )

    def _result_from_manifest(
        self,
        *,
        manifest: dict[str, Any],
        snapshot_path: Path,
        manifest_path: Path,
        wall_seconds: float,
        skipped: bool,
    ) -> DiscoveryFoundationBuildResult:
        counts = manifest["counts"]
        return DiscoveryFoundationBuildResult(
            as_of_date=date.fromisoformat(str(manifest["as_of_date"])),
            source_universe_count=int(counts["source_universe"]),
            data_health_pass_count=int(counts["data_health_pass"]),
            activity_pass_count=int(counts["activity_pass"]),
            broad_discovery_ready_count=int(counts["broad_discovery_ready"]),
            mandatory_route_count=int(counts["mandatory_route"]),
            consideration_required_count=int(counts["consideration_required"]),
            intraday_ready_count=int(counts["intraday_ready"]),
            activity_tier_counts={str(k): int(v) for k, v in manifest["activity_tier_counts"].items()},
            reason_counts={str(k): int(v) for k, v in manifest["reason_counts"].items()},
            security_type_counts={str(k): int(v) for k, v in manifest["broad_security_type_counts"].items()},
            dependency_fingerprint=str(manifest["dependency_fingerprint"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=wall_seconds,
            skipped=skipped,
        )

    def _existing_current(
        self,
        *,
        as_of_date: date,
        dependency_fingerprint: str,
        snapshot_path: Path,
        manifest_path: Path,
    ) -> dict[str, Any] | None:
        if not snapshot_path.is_file() or not manifest_path.is_file():
            return None
        try:
            manifest = self._json(manifest_path)
        except ValueError:
            return None
        if manifest.get("manifest_version") != DISCOVERY_FOUNDATION_MANIFEST_VERSION:
            return None
        if manifest.get("policy_version") != DISCOVERY_FILTER_POLICY_VERSION:
            return None
        if manifest.get("policy_fingerprint") != self.policy.fingerprint:
            return None
        if manifest.get("as_of_date") != as_of_date.isoformat():
            return None
        if manifest.get("dependency_fingerprint") != dependency_fingerprint:
            return None
        return manifest if manifest.get("snapshot_sha256") == sha256_file(snapshot_path) else None

    def _load_joined(self, paths: dict[str, Path]) -> pd.DataFrame:
        con = connect_utc(":memory:")
        try:
            universe = sql_string(paths["universe"])
            daily = sql_string(paths["canonical_1d"])
            features_1d = sql_string(paths["features_1d"])
            features_4h = sql_string(paths["features_4h"])
            features_1h = sql_string(paths["features_1h"])
            return con.execute(
                f"""
                WITH u AS (
                    SELECT instrument_id, ticker, security_type, discovery_eligible, routes
                    FROM read_parquet({universe})
                ), b AS (
                    SELECT symbol, timestamp_utc, close, volume
                    FROM (
                        SELECT symbol, timestamp_utc, close, volume,
                               row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                        FROM read_parquet({daily})
                    )
                    WHERE rn = 1
                ), f AS (
                    SELECT symbol, timestamp_utc, dollar_volume, relative_volume_20,
                           relative_dollar_volume_20, natr_14, realized_volatility_20
                    FROM (
                        SELECT symbol, timestamp_utc, dollar_volume, relative_volume_20,
                               relative_dollar_volume_20, natr_14, realized_volatility_20,
                               row_number() OVER (PARTITION BY symbol ORDER BY timestamp_utc DESC) AS rn
                        FROM read_parquet({features_1d})
                    )
                    WHERE rn = 1
                ), h1 AS (
                    SELECT DISTINCT symbol
                    FROM read_parquet({features_1h})
                    WHERE session_segment = 'regular'
                ), h4 AS (
                    SELECT DISTINCT symbol
                    FROM read_parquet({features_4h})
                    WHERE session_segment = 'regular'
                )
                SELECT
                    u.*,
                    b.symbol AS bar_symbol,
                    b.timestamp_utc AS daily_bar_timestamp_utc,
                    b.close,
                    b.volume,
                    f.symbol AS feature_symbol,
                    f.timestamp_utc AS daily_feature_timestamp_utc,
                    f.dollar_volume,
                    f.relative_volume_20,
                    f.relative_dollar_volume_20,
                    f.natr_14,
                    f.realized_volatility_20,
                    h1.symbol IS NOT NULL AS has_regular_1h,
                    h4.symbol IS NOT NULL AS has_regular_4h
                FROM u
                LEFT JOIN b ON b.symbol = u.ticker
                LEFT JOIN f ON f.symbol = u.ticker
                LEFT JOIN h1 ON h1.symbol = u.ticker
                LEFT JOIN h4 ON h4.symbol = u.ticker
                ORDER BY u.instrument_id
                """
            ).fetch_df()
        finally:
            con.close()

    def build(self, as_of_date: date) -> DiscoveryFoundationBuildResult:
        started = perf_counter()
        lineage, paths = self._upstream_lineage(as_of_date)
        dependency = self._dependency_fingerprint(as_of_date, lineage)
        snapshot_path = self.paths.discovery_snapshot_file(as_of_date)
        manifest_path = self.paths.discovery_snapshot_manifest(as_of_date)
        existing = self._existing_current(
            as_of_date=as_of_date,
            dependency_fingerprint=dependency,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
        )
        if existing is not None:
            return self._result_from_manifest(
                manifest=existing,
                snapshot_path=snapshot_path,
                manifest_path=manifest_path,
                wall_seconds=perf_counter() - started,
                skipped=True,
            )

        frame = self._load_joined(paths)
        candidates: list[DiscoveryCandidate] = []
        for row in frame.itertuples(index=False):
            routes = self._routes(row.routes)
            bar_ts = self._optional(row.daily_bar_timestamp_utc)
            feature_ts = self._optional(row.daily_feature_timestamp_utc)
            decision = self.policy.evaluate(
                discovery_eligible=bool(row.discovery_eligible),
                routes=routes,
                bar_present=self._optional(row.bar_symbol) is not None,
                feature_present=self._optional(row.feature_symbol) is not None,
                bar_timestamp_utc=bar_ts,  # type: ignore[arg-type]
                feature_timestamp_utc=feature_ts,  # type: ignore[arg-type]
                close=row.close,
                volume=row.volume,
                dollar_volume=row.dollar_volume,
                has_regular_1h=bool(row.has_regular_1h),
                has_regular_4h=bool(row.has_regular_4h),
            )
            candidates.append(
                DiscoveryCandidate(
                    instrument_id=str(row.instrument_id),
                    ticker=str(row.ticker),
                    as_of_date=as_of_date,
                    security_type=None if self._optional(row.security_type) is None else str(row.security_type),
                    routes=routes,
                    discovery_eligible=bool(row.discovery_eligible),
                    daily_bar_timestamp_utc=bar_ts,  # type: ignore[arg-type]
                    daily_feature_timestamp_utc=feature_ts,  # type: ignore[arg-type]
                    close=self._optional_float(row.close),
                    volume=self._optional_float(row.volume),
                    dollar_volume=self._optional_float(row.dollar_volume),
                    relative_volume_20=self._optional_float(row.relative_volume_20),
                    relative_dollar_volume_20=self._optional_float(row.relative_dollar_volume_20),
                    natr_14=self._optional_float(row.natr_14),
                    realized_volatility_20=self._optional_float(row.realized_volatility_20),
                    has_regular_1h=bool(row.has_regular_1h),
                    has_regular_4h=bool(row.has_regular_4h),
                    intraday_ready=decision.intraday_ready,
                    data_health_pass=decision.data_health_pass,
                    activity_pass=decision.activity_pass,
                    broad_discovery_ready=decision.broad_discovery_ready,
                    mandatory_route=decision.mandatory_route,
                    consideration_required=decision.consideration_required,
                    activity_tier=decision.activity_tier,
                    reason_codes=decision.reason_codes,
                )
            )

        records: list[dict[str, object]] = []
        reason_counts: Counter[str] = Counter()
        tier_counts: Counter[str] = Counter()
        security_counts: Counter[str] = Counter()
        for item in candidates:
            record = item.model_dump(mode="python")
            record["routes"] = [route.value for route in item.routes]
            record["activity_tier"] = item.activity_tier.value
            record["reason_codes"] = [reason.value for reason in item.reason_codes]
            records.append(record)
            reason_counts.update(reason.value for reason in item.reason_codes)
            tier_counts.update([item.activity_tier.value])
            if item.broad_discovery_ready:
                security_counts.update([item.security_type or "<NULL>"])

        output = pd.DataFrame.from_records(records)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(snapshot_path)
        con = connect_utc(":memory:")
        try:
            con.register("atlas_discovery_foundation", output)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT * FROM atlas_discovery_foundation ORDER BY instrument_id
                ) TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, snapshot_path)
        finally:
            con.close()

        snapshot_sha = sha256_file(snapshot_path)
        generated_at = datetime.now(UTC)
        manifest = {
            "manifest_version": DISCOVERY_FOUNDATION_MANIFEST_VERSION,
            "policy_version": DISCOVERY_FILTER_POLICY_VERSION,
            "policy_fingerprint": self.policy.fingerprint,
            "as_of_date": as_of_date.isoformat(),
            "dependency_fingerprint": dependency,
            "upstream_lineage": lineage,
            "snapshot_path": str(snapshot_path.resolve()),
            "snapshot_sha256": snapshot_sha,
            "generated_at_utc": generated_at.isoformat(),
            "counts": {
                "source_universe": len(candidates),
                "data_health_pass": sum(item.data_health_pass for item in candidates),
                "activity_pass": sum(item.activity_pass for item in candidates),
                "broad_discovery_ready": sum(item.broad_discovery_ready for item in candidates),
                "mandatory_route": sum(item.mandatory_route for item in candidates),
                "consideration_required": sum(item.consideration_required for item in candidates),
                "intraday_ready": sum(item.intraday_ready for item in candidates),
            },
            "activity_tier_counts": dict(sorted(tier_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "broad_security_type_counts": dict(sorted(security_counts.items())),
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return self._result_from_manifest(
            manifest=manifest,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=perf_counter() - started,
            skipped=False,
        )
