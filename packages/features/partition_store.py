from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.feature_registry import (
    CORE_FEATURE_CONTRACT_VERSION,
    CORE_FEATURE_REGISTRY,
)


FEATURE_PARTITION_SCHEMA_VERSION = 1
FEATURE_PARTITION_CONTRACT_VERSION = "feature-partition-v1-state-dependent"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def feature_dependency_fingerprint(
    *,
    source_sha256: str,
    input_state_fingerprint: str,
) -> str:
    payload = {
        "partition_contract": FEATURE_PARTITION_CONTRACT_VERSION,
        "feature_contract": CORE_FEATURE_CONTRACT_VERSION,
        "registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
        "source_sha256": source_sha256,
        "input_state_fingerprint": input_state_fingerprint,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class FeaturePartitionManifest:
    schema_version: int
    partition_contract_version: str
    feature_contract_version: str
    feature_registry_fingerprint: str
    timeframe: str
    trading_date: str
    source_path: str
    source_sha256: str
    input_state_fingerprint: str
    output_state_fingerprint: str
    dependency_fingerprint: str
    feature_path: str
    feature_sha256: str
    row_count: int
    symbol_count: int
    created_at_utc: str

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "FeaturePartitionManifest":
        return cls(**payload)  # type: ignore[arg-type]

    def validate_contract(self, timeframe: Timeframe, trading_date: date) -> None:
        if self.schema_version != FEATURE_PARTITION_SCHEMA_VERSION:
            raise ValueError("unsupported feature partition manifest schema")
        if self.partition_contract_version != FEATURE_PARTITION_CONTRACT_VERSION:
            raise ValueError("feature partition manifest contract is stale")
        if self.feature_contract_version != CORE_FEATURE_CONTRACT_VERSION:
            raise ValueError("feature calculation contract is stale")
        if self.feature_registry_fingerprint != CORE_FEATURE_REGISTRY.fingerprint():
            raise ValueError("feature registry fingerprint is stale")
        if self.timeframe != timeframe.value:
            raise ValueError("feature partition manifest timeframe mismatch")
        if self.trading_date != trading_date.isoformat():
            raise ValueError("feature partition manifest trading-date mismatch")


class FeaturePartitionStore:
    """Atomic Parquet + JSON manifest storage for exact feature partitions."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)

    def source_path(self, timeframe: Timeframe, trading_date: date) -> Path:
        if timeframe in {Timeframe.MINUTE_1, Timeframe.DAY_1}:
            return self.paths.canonical_file(timeframe, trading_date)
        if timeframe in {Timeframe.MINUTE_15, Timeframe.HOUR_1, Timeframe.HOUR_4}:
            return self.paths.derived_file(timeframe, trading_date)
        raise ValueError(f"unsupported feature timeframe: {timeframe}")

    def read_manifest(
        self,
        timeframe: Timeframe,
        trading_date: date,
    ) -> FeaturePartitionManifest | None:
        path = self.paths.feature_manifest_file(timeframe, trading_date)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = FeaturePartitionManifest.from_dict(payload)
        record.validate_contract(timeframe, trading_date)
        return record

    def is_current(
        self,
        timeframe: Timeframe,
        trading_date: date,
        *,
        input_state_fingerprint: str,
    ) -> bool:
        source_path = self.source_path(timeframe, trading_date)
        feature_path = self.paths.feature_file(timeframe, trading_date)
        if not source_path.is_file() or not feature_path.is_file():
            return False
        try:
            record = self.read_manifest(timeframe, trading_date)
        except (ValueError, json.JSONDecodeError, TypeError):
            return False
        if record is None:
            return False
        source_sha = sha256_file(source_path)
        dependency = feature_dependency_fingerprint(
            source_sha256=source_sha,
            input_state_fingerprint=input_state_fingerprint,
        )
        if record.dependency_fingerprint != dependency:
            return False
        if record.source_sha256 != source_sha:
            return False
        if Path(record.feature_path).resolve() != feature_path.resolve():
            return False
        return record.feature_sha256 == sha256_file(feature_path)

    def write(
        self,
        frame: pd.DataFrame,
        *,
        timeframe: Timeframe,
        trading_date: date,
        input_state_fingerprint: str,
        output_state_fingerprint: str,
    ) -> FeaturePartitionManifest:
        required = {"symbol", "timestamp_utc"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise ValueError(f"feature partition frame missing columns: {', '.join(missing)}")
        duplicate_key = ["symbol", "timestamp_utc"]
        if "session_segment" in frame.columns:
            duplicate_key.append("session_segment")
        if frame.duplicated(duplicate_key).any():
            raise ValueError("feature partition contains duplicate market keys")

        source_path = self.source_path(timeframe, trading_date)
        if not source_path.is_file():
            raise FileNotFoundError(f"feature source partition is missing: {source_path}")
        source_sha = sha256_file(source_path)
        dependency = feature_dependency_fingerprint(
            source_sha256=source_sha,
            input_state_fingerprint=input_state_fingerprint,
        )

        feature_path = self.paths.feature_file(timeframe, trading_date)
        feature_path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(feature_path)
        con = connect_utc(":memory:")
        try:
            con.register("atlas_feature_partition", frame)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            order_columns = "symbol, timestamp_utc"
            if "session_segment" in frame.columns:
                order_columns = "symbol, session_segment, timestamp_utc"
            con.execute(
                f"""
                COPY (
                    SELECT *
                    FROM atlas_feature_partition
                    ORDER BY {order_columns}
                )
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, feature_path)
        finally:
            con.close()

        feature_sha = sha256_file(feature_path)
        record = FeaturePartitionManifest(
            schema_version=FEATURE_PARTITION_SCHEMA_VERSION,
            partition_contract_version=FEATURE_PARTITION_CONTRACT_VERSION,
            feature_contract_version=CORE_FEATURE_CONTRACT_VERSION,
            feature_registry_fingerprint=CORE_FEATURE_REGISTRY.fingerprint(),
            timeframe=timeframe.value,
            trading_date=trading_date.isoformat(),
            source_path=str(source_path.resolve()),
            source_sha256=source_sha,
            input_state_fingerprint=input_state_fingerprint,
            output_state_fingerprint=output_state_fingerprint,
            dependency_fingerprint=dependency,
            feature_path=str(feature_path.resolve()),
            feature_sha256=feature_sha,
            row_count=int(len(frame)),
            symbol_count=int(frame["symbol"].nunique()),
            created_at_utc=datetime.now(UTC).isoformat(),
        )
        manifest_path = self.paths.feature_manifest_file(timeframe, trading_date)
        atomic_write_text(
            manifest_path,
            json.dumps(asdict(record), indent=2, sort_keys=True) + "\n",
        )
        return record
