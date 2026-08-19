from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.feature_registry import CORE_FEATURE_CONTRACT_VERSION, CORE_FEATURE_REGISTRY
from packages.features.partition_store import sha256_file
from packages.ml.feature_policy import (
    ML_FEATURE_POLICY_CONTRACT_VERSION,
    ML_MARKET_REGIME_CONTEXT_FIELDS,
    ML_MARKET_REGIME_EVALUATION_CONTEXT_ACCEPTED,
    ML_MARKET_REGIME_MODEL_INPUT_ACCEPTED,
    ML_PRODUCTION_CORE_FEATURE_NAMES,
)
from packages.ml.identity_policy import ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION
from packages.ml.label_policy import (
    ML_GATE4_ACCEPTED_DOWN_ROWS,
    ML_GATE4_ACCEPTED_NEUTRAL_ROWS,
    ML_GATE4_ACCEPTED_UP_ROWS,
    ML_GATE4_ACCEPTED_USABLE_ROWS,
    ML_PREDICTION_LABEL_CLASSES,
    ML_PREDICTION_LABEL_HORIZON_SESSIONS,
    ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
    ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER,
)
from packages.ml.outcome_family_audit import MLOutcomeFamilyAudit
from packages.ml.universe_probe import ML_HISTORY_ORIGIN_DATE
from packages.regimes.calibration import RegimeCalibration
from packages.regimes.persistence_policy import REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION
from packages.regimes.state_engine import compute_regime_state_history
from packages.regimes.threshold_policy import (
    REGIME_HISTORY_ORIGIN_DATE,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
)


ML_TRAINING_DATASET_SCHEMA_VERSION = 1
ML_TRAINING_DATASET_CONTRACT_VERSION = (
    "ml-training-dataset-v1-year-partitioned-core33-threeclass-context-lineage"
)
ML_TRAINING_DATASET_ORDERING = ("session_date", "symbol", "instrument_id")
ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT = "instrument_id|provider_symbol|session_date"
ML_TRAINING_DATASET_PARTITIONING = "observation_year"
ML_TRAINING_DATASET_IMMUTABLE = True
ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE = "EVALUATION_METADATA_ONLY"

ML_TRAINING_DATASET_IDENTITY_COLUMNS = (
    "observation_key",
    "session_date",
    "symbol",
    "instrument_id",
    "observation_close",
)
ML_TRAINING_DATASET_OUTCOME_COLUMNS = (
    "future_date",
    "future_close",
    "forward_return",
    "label_threshold",
    "prediction_label",
)
ML_TRAINING_DATASET_CONTEXT_COLUMNS = (
    "market_regime_available",
    "market_regime_composite",
    "market_regime_structure",
    "market_regime_momentum",
    "market_regime_volatility",
    "market_regime_efficiency",
    "market_regime_participation",
)


@dataclass(frozen=True, slots=True)
class MLTrainingDatasetPartition:
    year: int
    relative_path: str
    sha256: str
    row_count: int
    distinct_observation_keys: int
    symbol_count: int
    first_session_date: str
    last_session_date: str
    down_rows: int
    neutral_rows: int
    up_rows: int
    market_context_rows: int


@dataclass(frozen=True, slots=True)
class MLTrainingDatasetManifest:
    schema_version: int
    contract_version: str
    dataset_id: str
    created_at_utc: str
    history_start: str
    history_end: str
    immutable: bool
    partitioning: str
    ordering: tuple[str, ...]
    observation_key_contract: str
    row_count: int
    distinct_observation_keys: int
    symbol_count: int
    first_session_date: str
    last_session_date: str
    predictor_count: int
    predictor_columns: tuple[str, ...]
    identity_columns: tuple[str, ...]
    outcome_columns: tuple[str, ...]
    context_columns: tuple[str, ...]
    market_context_role: str
    market_context_rows: int
    market_context_fraction: float
    class_row_counts: dict[str, int]
    feature_policy_contract: str
    label_policy_contract: str
    identity_policy_contract: str
    feature_contract: str
    feature_registry_fingerprint: str
    regime_threshold_policy_contract: str
    regime_persistence_policy_contract: str
    feature_source_lineage_fingerprint: str
    identity_source_lineage_fingerprint: str
    split_evidence_sha256: str
    market_context_fingerprint: str
    dataset_lineage_fingerprint: str
    partitions: tuple[MLTrainingDatasetPartition, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "MLTrainingDatasetManifest":
        raw_partitions = payload.pop("partitions")
        partitions = tuple(
            MLTrainingDatasetPartition(**item)  # type: ignore[arg-type]
            for item in raw_partitions  # type: ignore[union-attr]
        )
        payload["partitions"] = partitions
        for key in (
            "ordering",
            "predictor_columns",
            "identity_columns",
            "outcome_columns",
            "context_columns",
        ):
            payload[key] = tuple(payload[key])  # type: ignore[arg-type]
        return cls(**payload)  # type: ignore[arg-type]


def stable_observation_key(*, instrument_id: str, symbol: str, session_date: date | str) -> str:
    instrument = str(instrument_id).strip()
    ticker = str(symbol)
    raw_date = session_date.isoformat() if isinstance(session_date, date) else str(session_date)
    if not instrument:
        raise ValueError("instrument_id is required for a stable ML observation key")
    if not ticker:
        raise ValueError("provider-native symbol is required for a stable ML observation key")
    parsed = date.fromisoformat(raw_date)
    return f"{instrument}|{ticker}|{parsed.isoformat()}"


def _stable_sha256(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def training_dataset_lineage_fingerprint(payload: dict[str, object]) -> str:
    """Return the deterministic Gate 6 lineage fingerprint for one dataset build."""

    return _stable_sha256(payload)


def training_dataset_id(*, end_date: date, lineage_fingerprint: str) -> str:
    digest = str(lineage_fingerprint).strip().lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("lineage_fingerprint must be a SHA-256 hex digest")
    return f"mltrain-{end_date.isoformat()}-{digest[:16]}"


class MLTrainingDatasetMaterializer:
    """Materialize the accepted Gate 1-5 population into an immutable ML dataset.

    The dataset is deliberately model-library agnostic. Predictor, outcome, identity,
    and evaluation-context columns have separate contracts so a future model loader
    cannot accidentally admit outcome or partial regime metadata as predictors.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.family = MLOutcomeFamilyAudit(settings)
        self.base = self.family.base
        self.paths = self.base.paths
        self.regime_calibration = RegimeCalibration(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)

    def dataset_parent(self) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return root / "ml" / "training_datasets"

    @staticmethod
    def manifest_path(dataset_root: Path) -> Path:
        return Path(dataset_root) / "manifest.json"

    def _feature_source_lineage(self, end_date: date) -> str:
        entries: list[dict[str, object]] = []
        for trading_date in self.calendar.sessions_in_range(ML_HISTORY_ORIGIN_DATE, end_date):
            manifest_path = self.paths.feature_manifest_file(Timeframe.DAY_1, trading_date)
            if not manifest_path.is_file():
                raise FileNotFoundError(
                    "Gate 6 requires complete daily feature manifests for source lineage: "
                    f"{manifest_path}"
                )
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            entries.append(
                {
                    "date": trading_date.isoformat(),
                    "feature_sha256": payload.get("feature_sha256"),
                    "source_sha256": payload.get("source_sha256"),
                    "dependency_fingerprint": payload.get("dependency_fingerprint"),
                    "feature_contract_version": payload.get("feature_contract_version"),
                    "feature_registry_fingerprint": payload.get("feature_registry_fingerprint"),
                }
            )
        return _stable_sha256(entries)

    def _identity_source_lineage(self, end_date: date) -> str:
        required = self.base.identity._required_paths(end_date)
        paths: dict[str, Path] = dict(required)
        intervals = self.paths.authoritative_ticker_intervals_file()
        if intervals.is_file():
            paths["authoritative_ticker_intervals"] = intervals
        entries = [
            {
                "name": name,
                "path_name": path.name,
                "sha256": sha256_file(path),
            }
            for name, path in sorted(paths.items())
        ]
        return _stable_sha256(entries)

    def _market_context(self, end_date: date) -> tuple[pd.DataFrame, str]:
        if not ML_MARKET_REGIME_EVALUATION_CONTEXT_ACCEPTED:
            raise RuntimeError("Gate 5 did not accept market regime as evaluation context")
        if ML_MARKET_REGIME_MODEL_INPUT_ACCEPTED:
            raise RuntimeError("Gate 6 contract expects market regime to remain non-predictor metadata")

        breadth = self.regime_calibration._breadth_daily(REGIME_HISTORY_ORIGIN_DATE, end_date)
        proxies = self.regime_calibration._proxy_frame(REGIME_HISTORY_ORIGIN_DATE, end_date)
        _, effective_market, _, _ = compute_regime_state_history(breadth, proxies)
        fields = ("trading_date",) + ML_MARKET_REGIME_CONTEXT_FIELDS
        missing = [field for field in fields if field not in effective_market.columns]
        if missing:
            raise RuntimeError("Gate 6 market-context history is missing fields: " + ", ".join(missing))
        market = effective_market.loc[:, list(fields)].copy()
        market["trading_date"] = pd.to_datetime(market["trading_date"]).dt.date
        market = market.sort_values("trading_date", kind="stable").reset_index(drop=True)
        if market["trading_date"].duplicated().any():
            raise RuntimeError("Gate 6 market-context history contains duplicate trading dates")

        records: list[dict[str, object]] = []
        for row in market.itertuples(index=False):
            record: dict[str, object] = {"trading_date": str(row.trading_date)}
            for field in ML_MARKET_REGIME_CONTEXT_FIELDS:
                value = getattr(row, field)
                record[field] = None if pd.isna(value) else str(value)
            records.append(record)
        return market, _stable_sha256(records)

    def _lineage_payload(
        self,
        *,
        end_date: date,
        feature_source_lineage: str,
        identity_source_lineage: str,
        split_evidence_sha256: str,
        market_context_fingerprint: str,
    ) -> dict[str, object]:
        return {
            "dataset_contract": ML_TRAINING_DATASET_CONTRACT_VERSION,
            "dataset_schema_version": ML_TRAINING_DATASET_SCHEMA_VERSION,
            "history_start": ML_HISTORY_ORIGIN_DATE.isoformat(),
            "history_end": end_date.isoformat(),
            "partitioning": ML_TRAINING_DATASET_PARTITIONING,
            "ordering": ML_TRAINING_DATASET_ORDERING,
            "observation_key_contract": ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
            "predictor_columns": ML_PRODUCTION_CORE_FEATURE_NAMES,
            "identity_columns": ML_TRAINING_DATASET_IDENTITY_COLUMNS,
            "outcome_columns": ML_TRAINING_DATASET_OUTCOME_COLUMNS,
            "context_columns": ML_TRAINING_DATASET_CONTEXT_COLUMNS,
            "market_context_role": ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE,
            "feature_policy_contract": ML_FEATURE_POLICY_CONTRACT_VERSION,
            "label_policy_contract": ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
            "identity_policy_contract": ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION,
            "feature_contract": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "regime_threshold_policy_contract": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "regime_persistence_policy_contract": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "feature_source_lineage_fingerprint": feature_source_lineage,
            "identity_source_lineage_fingerprint": identity_source_lineage,
            "split_evidence_sha256": split_evidence_sha256,
            "market_context_fingerprint": market_context_fingerprint,
        }

    def _prepare_labeled_candidates(self, con: Any) -> None:
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        horizon = int(ML_PREDICTION_LABEL_HORIZON_SESSIONS)
        threshold_scale = float(ML_PREDICTION_LABEL_THRESHOLD_MULTIPLIER) * math.sqrt(float(horizon))
        split_exists = (
            "EXISTS (SELECT 1 FROM ml_split_events s "
            "WHERE s.ticker = c.symbol "
            "AND s.execution_date > c.session_date "
            "AND s.execution_date <= fs.session_date)"
        )
        con.execute(
            f"""
            CREATE TEMP TABLE ml_gate6_labeled_candidates AS
            WITH volatility AS (
                SELECT
                    symbol,
                    CAST(timestamp_utc AS DATE) AS session_date,
                    CAST(natr_14 AS DOUBLE) AS natr_14
                FROM read_parquet(
                    {sql_string(feature_glob)},
                    hive_partitioning=true,
                    union_by_name=true
                )
                WHERE natr_14 IS NOT NULL
                  AND isfinite(CAST(natr_14 AS DOUBLE))
                  AND CAST(natr_14 AS DOUBLE) > 0
            )
            SELECT
                c.symbol,
                c.session_date,
                c.instrument_id,
                c.close AS observation_close,
                fs.session_date AS future_date,
                fb.close AS future_close,
                (fb.close / c.close) - 1.0 AS forward_return,
                v.natr_14 * {threshold_scale:.17g} AS label_threshold,
                CASE
                    WHEN (fb.close / c.close) - 1.0 >= v.natr_14 * {threshold_scale:.17g}
                        THEN 'UP'
                    WHEN (fb.close / c.close) - 1.0 <= -(v.natr_14 * {threshold_scale:.17g})
                        THEN 'DOWN'
                    ELSE 'NEUTRAL'
                END AS prediction_label
            FROM ml_gate3_candidates c
            INNER JOIN ml_label_sessions fs
              ON fs.session_seq = c.session_seq + {horizon}
            INNER JOIN ml_label_bars fb
              ON fb.symbol = c.symbol
             AND fb.session_date = fs.session_date
            INNER JOIN volatility v
              ON v.symbol = c.symbol
             AND v.session_date = c.session_date
            WHERE fs.session_date IS NOT NULL
              AND fb.close > 0
              AND NOT {split_exists}
            """
        )

        row = con.execute(
            """
            SELECT
                count(*) AS rows,
                count(DISTINCT (symbol, session_date)) AS keys,
                count(DISTINCT symbol) AS symbols,
                count(*) FILTER (WHERE instrument_id IS NULL OR trim(instrument_id) = '') AS bad_identity,
                count(*) FILTER (WHERE prediction_label = 'DOWN') AS down_rows,
                count(*) FILTER (WHERE prediction_label = 'NEUTRAL') AS neutral_rows,
                count(*) FILTER (WHERE prediction_label = 'UP') AS up_rows
            FROM ml_gate6_labeled_candidates
            """
        ).fetchone()
        rows = int(row[0])
        keys = int(row[1])
        bad_identity = int(row[3])
        class_counts = (int(row[4]), int(row[5]), int(row[6]))
        if rows != keys:
            raise RuntimeError(f"Gate 6 labeled population contains duplicate observation keys: {rows:,} rows / {keys:,} keys")
        if bad_identity:
            raise RuntimeError(f"Gate 6 labeled population contains {bad_identity:,} rows without a stable instrument identity")
        expected = (
            ML_GATE4_ACCEPTED_DOWN_ROWS,
            ML_GATE4_ACCEPTED_NEUTRAL_ROWS,
            ML_GATE4_ACCEPTED_UP_ROWS,
        )
        if rows == ML_GATE4_ACCEPTED_USABLE_ROWS and class_counts != expected:
            raise RuntimeError(
                "Gate 6 class counts do not reconcile to the accepted Gate 4 anchors: "
                f"actual={class_counts} expected={expected}"
            )

    def _write_partition(
        self,
        con: Any,
        *,
        temp_root: Path,
        year: int,
    ) -> MLTrainingDatasetPartition:
        target = temp_root / f"year={year:04d}" / "part-000.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        feature_glob = self.paths.feature_glob(Timeframe.DAY_1)
        predictors = ",\n                    ".join(
            f"CAST(f.{name} AS DOUBLE) AS {name}" for name in ML_PRODUCTION_CORE_FEATURE_NAMES
        )
        context = ",\n                    ".join(
            f"CAST(m.{field} AS VARCHAR) AS market_regime_{field}"
            for field in ML_MARKET_REGIME_CONTEXT_FIELDS
        )
        compression = self.settings.data.parquet.compression.upper()
        row_group_size = int(self.settings.data.parquet.row_group_size)
        con.execute(
            f"""
            COPY (
                WITH features AS (
                    SELECT symbol, CAST(timestamp_utc AS DATE) AS session_date,
                           {', '.join(ML_PRODUCTION_CORE_FEATURE_NAMES)}
                    FROM read_parquet(
                        {sql_string(feature_glob)},
                        hive_partitioning=true,
                        union_by_name=true
                    )
                    WHERE year(CAST(timestamp_utc AS DATE)) = {int(year)}
                )
                SELECT
                    concat(l.instrument_id, '|', l.symbol, '|', CAST(l.session_date AS VARCHAR))
                        AS observation_key,
                    l.session_date,
                    l.symbol,
                    l.instrument_id,
                    l.observation_close,
                    {predictors},
                    l.future_date,
                    l.future_close,
                    l.forward_return,
                    l.label_threshold,
                    l.prediction_label,
                    (m.trading_date IS NOT NULL) AS market_regime_available,
                    {context}
                FROM ml_gate6_labeled_candidates l
                INNER JOIN features f
                  ON f.symbol = l.symbol
                 AND f.session_date = l.session_date
                LEFT JOIN ml_gate6_market_context m
                  ON m.trading_date = l.session_date
                WHERE year(l.session_date) = {int(year)}
                ORDER BY l.session_date, l.symbol, l.instrument_id
            )
            TO {sql_string(target)}
            (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
            """
        )
        stats = con.execute(
            f"""
            SELECT
                count(*),
                count(DISTINCT observation_key),
                count(DISTINCT symbol),
                min(session_date),
                max(session_date),
                count(*) FILTER (WHERE prediction_label = 'DOWN'),
                count(*) FILTER (WHERE prediction_label = 'NEUTRAL'),
                count(*) FILTER (WHERE prediction_label = 'UP'),
                count(*) FILTER (WHERE market_regime_available)
            FROM read_parquet({sql_string(target)})
            """
        ).fetchone()
        rows = int(stats[0])
        keys = int(stats[1])
        if rows != keys:
            raise RuntimeError(f"Gate 6 partition {year} contains duplicate stable observation keys")
        return MLTrainingDatasetPartition(
            year=int(year),
            relative_path=f"year={year:04d}/part-000.parquet",
            sha256=sha256_file(target),
            row_count=rows,
            distinct_observation_keys=keys,
            symbol_count=int(stats[2]),
            first_session_date=str(stats[3]),
            last_session_date=str(stats[4]),
            down_rows=int(stats[5]),
            neutral_rows=int(stats[6]),
            up_rows=int(stats[7]),
            market_context_rows=int(stats[8]),
        )

    def _validate_existing(
        self,
        *,
        dataset_root: Path,
        expected_lineage: str,
    ) -> MLTrainingDatasetManifest:
        path = self.manifest_path(dataset_root)
        if not path.is_file():
            raise RuntimeError(f"Gate 6 dataset root exists without a manifest: {dataset_root}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        manifest = MLTrainingDatasetManifest.from_dict(payload)
        if manifest.schema_version != ML_TRAINING_DATASET_SCHEMA_VERSION:
            raise ValueError("unsupported Gate 6 dataset manifest schema")
        if manifest.contract_version != ML_TRAINING_DATASET_CONTRACT_VERSION:
            raise ValueError("Gate 6 dataset manifest contract is stale")
        if manifest.dataset_lineage_fingerprint != expected_lineage:
            raise ValueError("Gate 6 dataset lineage does not match current accepted source/policy lineage")
        rows = 0
        keys = 0
        for partition in manifest.partitions:
            file_path = dataset_root / partition.relative_path
            if not file_path.is_file():
                raise FileNotFoundError(f"Gate 6 dataset partition is missing: {file_path}")
            if sha256_file(file_path) != partition.sha256:
                raise ValueError(f"Gate 6 dataset partition hash mismatch: {file_path}")
            rows += partition.row_count
            keys += partition.distinct_observation_keys
        if rows != manifest.row_count or keys != manifest.distinct_observation_keys:
            raise ValueError("Gate 6 partition totals do not reconcile to the dataset manifest")
        if manifest.row_count != manifest.distinct_observation_keys:
            raise ValueError("Gate 6 dataset manifest reports duplicate stable observation keys")
        return manifest

    def materialize(self, end_date: date) -> tuple[MLTrainingDatasetManifest, bool]:
        if end_date < ML_HISTORY_ORIGIN_DATE:
            raise ValueError("end_date predates the Phase 10 ML history origin")

        splits, split_path = self.family._load_split_evidence(end_date)
        split_sha = sha256_file(split_path)
        feature_lineage = self._feature_source_lineage(end_date)
        identity_lineage = self._identity_source_lineage(end_date)
        market_context, market_context_sha = self._market_context(end_date)
        lineage_payload = self._lineage_payload(
            end_date=end_date,
            feature_source_lineage=feature_lineage,
            identity_source_lineage=identity_lineage,
            split_evidence_sha256=split_sha,
            market_context_fingerprint=market_context_sha,
        )
        lineage = training_dataset_lineage_fingerprint(lineage_payload)
        dataset_id = training_dataset_id(end_date=end_date, lineage_fingerprint=lineage)
        parent = self.dataset_parent()
        parent.mkdir(parents=True, exist_ok=True)
        dataset_root = parent / dataset_id
        if dataset_root.exists():
            return self._validate_existing(dataset_root=dataset_root, expected_lineage=lineage), True

        temp_root = Path(tempfile.mkdtemp(prefix=f".{dataset_id}.", dir=parent))
        con = connect_utc(":memory:")
        try:
            self.base._prepare_label_views(con, end_date, splits)
            self._prepare_labeled_candidates(con)
            con.register("ml_gate6_market_context_input", market_context)
            context_fields = ", ".join(ML_MARKET_REGIME_CONTEXT_FIELDS)
            con.execute(
                f"""
                CREATE TEMP TABLE ml_gate6_market_context AS
                SELECT CAST(trading_date AS DATE) AS trading_date, {context_fields}
                FROM ml_gate6_market_context_input
                """
            )
            summary = con.execute(
                """
                SELECT
                    count(*), count(DISTINCT (symbol, session_date)), count(DISTINCT symbol),
                    min(session_date), max(session_date),
                    count(*) FILTER (WHERE prediction_label = 'DOWN'),
                    count(*) FILTER (WHERE prediction_label = 'NEUTRAL'),
                    count(*) FILTER (WHERE prediction_label = 'UP')
                FROM ml_gate6_labeled_candidates
                """
            ).fetchone()
            years = [
                int(row[0])
                for row in con.execute(
                    "SELECT DISTINCT year(session_date) FROM ml_gate6_labeled_candidates ORDER BY 1"
                ).fetchall()
            ]
            partitions = tuple(
                self._write_partition(con, temp_root=temp_root, year=year)
                for year in years
            )
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise
        finally:
            con.close()

        row_count = int(summary[0])
        distinct_keys = int(summary[1])
        market_context_rows = sum(partition.market_context_rows for partition in partitions)
        class_counts = {
            "DOWN": int(summary[5]),
            "NEUTRAL": int(summary[6]),
            "UP": int(summary[7]),
        }
        if row_count != sum(partition.row_count for partition in partitions):
            shutil.rmtree(temp_root, ignore_errors=True)
            raise RuntimeError("Gate 6 written partition row counts do not reconcile to the labeled source")
        if class_counts != {
            label: sum(
                getattr(partition, f"{label.lower()}_rows") for partition in partitions
            )
            for label in ML_PREDICTION_LABEL_CLASSES
        }:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise RuntimeError("Gate 6 written partition class counts do not reconcile to the labeled source")

        manifest = MLTrainingDatasetManifest(
            schema_version=ML_TRAINING_DATASET_SCHEMA_VERSION,
            contract_version=ML_TRAINING_DATASET_CONTRACT_VERSION,
            dataset_id=dataset_id,
            created_at_utc=datetime.now(UTC).isoformat(),
            history_start=ML_HISTORY_ORIGIN_DATE.isoformat(),
            history_end=end_date.isoformat(),
            immutable=ML_TRAINING_DATASET_IMMUTABLE,
            partitioning=ML_TRAINING_DATASET_PARTITIONING,
            ordering=ML_TRAINING_DATASET_ORDERING,
            observation_key_contract=ML_TRAINING_DATASET_OBSERVATION_KEY_CONTRACT,
            row_count=row_count,
            distinct_observation_keys=distinct_keys,
            symbol_count=int(summary[2]),
            first_session_date=str(summary[3]),
            last_session_date=str(summary[4]),
            predictor_count=len(ML_PRODUCTION_CORE_FEATURE_NAMES),
            predictor_columns=ML_PRODUCTION_CORE_FEATURE_NAMES,
            identity_columns=ML_TRAINING_DATASET_IDENTITY_COLUMNS,
            outcome_columns=ML_TRAINING_DATASET_OUTCOME_COLUMNS,
            context_columns=ML_TRAINING_DATASET_CONTEXT_COLUMNS,
            market_context_role=ML_TRAINING_DATASET_MARKET_CONTEXT_ROLE,
            market_context_rows=market_context_rows,
            market_context_fraction=(0.0 if row_count == 0 else market_context_rows / row_count),
            class_row_counts=class_counts,
            feature_policy_contract=ML_FEATURE_POLICY_CONTRACT_VERSION,
            label_policy_contract=ML_PREDICTION_LABEL_POLICY_CONTRACT_VERSION,
            identity_policy_contract=ML_HISTORICAL_IDENTITY_POLICY_CONTRACT_VERSION,
            feature_contract=CORE_FEATURE_CONTRACT_VERSION,
            feature_registry_fingerprint=CORE_FEATURE_REGISTRY.fingerprint(),
            regime_threshold_policy_contract=REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            regime_persistence_policy_contract=REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            feature_source_lineage_fingerprint=feature_lineage,
            identity_source_lineage_fingerprint=identity_lineage,
            split_evidence_sha256=split_sha,
            market_context_fingerprint=market_context_sha,
            dataset_lineage_fingerprint=lineage,
            partitions=partitions,
        )
        self.manifest_path(temp_root).write_text(
            json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        try:
            os.replace(temp_root, dataset_root)
        except Exception:
            shutil.rmtree(temp_root, ignore_errors=True)
            raise
        return manifest, False

    def verify(self, end_date: date) -> MLTrainingDatasetManifest:
        splits, split_path = self.family._load_split_evidence(end_date)
        del splits
        feature_lineage = self._feature_source_lineage(end_date)
        identity_lineage = self._identity_source_lineage(end_date)
        _, market_context_sha = self._market_context(end_date)
        lineage = training_dataset_lineage_fingerprint(
            self._lineage_payload(
                end_date=end_date,
                feature_source_lineage=feature_lineage,
                identity_source_lineage=identity_lineage,
                split_evidence_sha256=sha256_file(split_path),
                market_context_fingerprint=market_context_sha,
            )
        )
        dataset_id = training_dataset_id(end_date=end_date, lineage_fingerprint=lineage)
        return self._validate_existing(
            dataset_root=self.dataset_parent() / dataset_id,
            expected_lineage=lineage,
        )
