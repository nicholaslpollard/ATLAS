from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from packages.aggregation.bar_builder import SessionBarBuilder
from packages.aggregation.sessionizer import session_boundaries
from packages.core.enums import (
    DataProvider,
    DatasetType,
    MaterializationStatus,
    Timeframe,
    ValidationStatus,
)
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.materialization_manifest import MaterializationManifestStore
from packages.data.normalizer import MassiveStockNormalizer
from packages.data.paths import MarketDataPaths
from packages.data_quality.bar_validator import ParquetBarValidator
from packages.data_quality.symbol_quarantine import SessionSymbolQuarantine
from packages.ingestion.manifest import DirectoryManifestStore
from packages.schemas.ingestion import ProviderFileDescriptor
from packages.schemas.materialization import MaterializationRecord

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


# Bump this whenever canonical/derived transformation semantics change in a way
# that requires existing materializations to be regenerated from the same raw
# provider file. Phase 4 v2 preserves Massive's provider-significant ticker case.
MATERIALIZATION_CONTRACT_VERSION = "market-v2-provider-symbol-case"


@dataclass(frozen=True, slots=True)
class MaterializationResult:
    dataset: DatasetType
    trading_date: date
    source_rows: int
    canonical_rows: int
    canonical_path: Path
    derived_rows: dict[Timeframe, int]
    skipped: bool
    quality_status: ValidationStatus
    quarantined_symbols: tuple[str, ...] = ()


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class MarketDataMaterializer:
    """Transform validated Massive flat files into trusted ATLAS Parquet data.

    A provider session is the atomic unit. Reprocessing a corrected source file
    replaces only that session's staging/canonical/derived outputs.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(
            exchange=settings.data.calendar.exchange,
            premarket_start=self._clock(settings.data.calendar.premarket_start_local),
            after_hours_end=self._clock(settings.data.calendar.after_hours_end_local),
        )
        self.normalizer = MassiveStockNormalizer(
            compression=settings.data.parquet.compression,
            row_group_size=settings.data.parquet.row_group_size,
        )
        self.builder = SessionBarBuilder(
            compression=settings.data.parquet.compression,
            row_group_size=settings.data.parquet.row_group_size,
        )
        self.quarantine = SessionSymbolQuarantine(
            compression=settings.data.parquet.compression,
            row_group_size=settings.data.parquet.row_group_size,
        )
        self.manifest = MaterializationManifestStore(self.paths.materialization_manifest_dir())
        ingestion_root = settings.resolved_path(settings.data.paths.manifests) / "ingestion"
        self.ingestion_manifest = DirectoryManifestStore(ingestion_root)

    @staticmethod
    def _clock(value: str):
        from datetime import time
        h, m = (int(x) for x in value.split(":", 1))
        return time(h, m)

    def _descriptor(self, dataset: DatasetType, trading_date: date) -> ProviderFileDescriptor:
        cfg = self.settings.massive.flat_files.datasets[dataset.value]
        remote_key = f"{cfg.prefix}/{trading_date.year:04d}/{trading_date.month:02d}/{trading_date}.csv.gz"
        return ProviderFileDescriptor(
            provider=DataProvider.MASSIVE,
            dataset=dataset,
            trading_date=trading_date,
            remote_key=remote_key,
        )

    def _source_fingerprint(self, descriptor: ProviderFileDescriptor, source_path: Path) -> str:
        record = self.ingestion_manifest.get(descriptor.source_id)
        if record and record.sha256 and Path(record.local_path).resolve() == source_path.resolve():
            return record.sha256
        return _sha256(source_path)

    @staticmethod
    def _copy_atomic(source: Path, target: Path) -> None:
        temp = atomic_target(target)
        temp.unlink(missing_ok=True)
        shutil.copy2(source, temp)
        promote(temp, target)

    def materialize(self, dataset: DatasetType, trading_date: date, *, force: bool = False) -> MaterializationResult:
        if dataset not in {DatasetType.STOCK_MINUTE_AGGREGATES, DatasetType.STOCK_DAILY_AGGREGATES}:
            raise ValueError(f"Unsupported materialization dataset: {dataset}")
        if not self.calendar.is_session(trading_date):
            raise ValueError(f"{trading_date} is not an exchange session")

        source_path = self.paths.provider_file(dataset, trading_date)
        if not source_path.exists():
            raise FileNotFoundError(f"Provider file is missing: {source_path}")
        descriptor = self._descriptor(dataset, trading_date)
        source_sha = self._source_fingerprint(descriptor, source_path)
        existing = self.manifest.get(descriptor.source_id)

        registry_path = self.paths.symbol_quarantine_registry(trading_date)
        registry_fingerprint = (
            _sha256(registry_path)
            if dataset == DatasetType.STOCK_MINUTE_AGGREGATES and registry_path.exists()
            else None
        )
        if dataset == DatasetType.STOCK_MINUTE_AGGREGATES:
            dependency_fingerprint = (
                f"{MATERIALIZATION_CONTRACT_VERSION}:quarantine:{registry_fingerprint or 'none'}"
            )
        else:
            dependency_fingerprint = MATERIALIZATION_CONTRACT_VERSION

        timeframe = Timeframe.MINUTE_1 if dataset == DatasetType.STOCK_MINUTE_AGGREGATES else Timeframe.DAY_1
        canonical = self.paths.canonical_file(timeframe, trading_date)
        expected_derived = (
            {tf: self.paths.derived_file(tf, trading_date) for tf in (Timeframe.MINUTE_15, Timeframe.HOUR_1, Timeframe.HOUR_4)}
            if dataset == DatasetType.STOCK_MINUTE_AGGREGATES else {}
        )
        if (
            not force
            and existing
            and existing.status == MaterializationStatus.COMPLETE
            and existing.source_sha256 == source_sha
            and existing.dependency_fingerprint == dependency_fingerprint
            and canonical.exists()
            and all(path.exists() for path in expected_derived.values())
        ):
            return MaterializationResult(
                dataset=dataset,
                trading_date=trading_date,
                source_rows=existing.source_rows,
                canonical_rows=existing.canonical_rows,
                canonical_path=canonical,
                derived_rows={tf: self._count(path) for tf, path in expected_derived.items()},
                skipped=True,
                quality_status=existing.validation_status,
                quarantined_symbols=tuple(existing.quarantined_symbols),
            )

        staging = self.paths.staging_file(timeframe, trading_date)
        quality_path = self.paths.quality_report(timeframe, trading_date)
        record = MaterializationRecord(
            source_id=descriptor.source_id,
            dataset=dataset,
            trading_date=trading_date,
            source_path=source_path,
            source_sha256=source_sha,
            dependency_fingerprint=dependency_fingerprint,
            status=MaterializationStatus.NORMALIZING,
            staging_path=staging,
            canonical_path=canonical,
            derived_paths={tf.value: path for tf, path in expected_derived.items()},
            quality_report_path=quality_path,
            quarantine_path=self.paths.quarantine_file(timeframe, trading_date),
            started_at_utc=datetime.now(UTC),
        )
        self.manifest.put(record)

        try:
            boundaries = session_boundaries(
                trading_date,
                self.calendar,
                market_timezone=self.settings.data.calendar.market_timezone,
                premarket_start_local=self.settings.data.calendar.premarket_start_local,
                after_hours_end_local=self.settings.data.calendar.after_hours_end_local,
            )
            rows = self.normalizer.normalize(source_path, staging, dataset, trading_date, descriptor.source_id, boundaries)
            quarantine_path = self.paths.quarantine_file(timeframe, trading_date)
            if dataset == DatasetType.STOCK_DAILY_AGGREGATES:
                quarantine_result = self.quarantine.sanitize_daily(
                    staging,
                    trading_date=trading_date,
                    quarantine_path=quarantine_path,
                    registry_path=registry_path,
                )
            else:
                quarantine_result = self.quarantine.apply_registry(
                    staging,
                    registry_path=registry_path,
                    quarantine_path=quarantine_path,
                )

            record = record.model_copy(update={
                "source_rows": rows,
                "status": MaterializationStatus.VALIDATING,
                "quarantine_path": quarantine_result.quarantine_path,
                "quarantined_symbols": list(quarantine_result.symbols),
            })
            self.manifest.put(record)

            validator = ParquetBarValidator(dataset=dataset, trading_date=trading_date)
            report = validator.validate(staging)
            extra_issues = quarantine_result.quality_issues()
            if extra_issues:
                report = report.model_copy(update={"issues": [*report.issues, *extra_issues]})
            validator.persist(report, quality_path)
            validator.enforce(report)

            record = record.model_copy(update={
                "status": MaterializationStatus.WRITING_CANONICAL,
                "validation_status": report.status,
            })
            self.manifest.put(record)
            self._copy_atomic(staging, canonical)
            # Canonical is an atomic byte-for-byte copy of the just-validated
            # staging Parquet. Re-reading canonical only for count(*) duplicated a
            # full file scan; the validator's checked_rows is the exact row count.
            canonical_rows = int(report.checked_rows)

            derived_rows: dict[Timeframe, int] = {}
            if dataset == DatasetType.STOCK_MINUTE_AGGREGATES:
                record = record.model_copy(update={"status": MaterializationStatus.BUILDING_DERIVED})
                self.manifest.put(record)
                for tf, path in expected_derived.items():
                    derived_rows[tf] = self.builder.build(canonical, path, tf, trading_date, boundaries)
                    derived_validator = ParquetBarValidator(
                        dataset=DatasetType.DERIVED_STOCK_BARS, trading_date=trading_date
                    )
                    derived_report = derived_validator.validate(path)
                    derived_validator.persist(derived_report, self.paths.quality_report(tf, trading_date))
                    derived_validator.enforce(derived_report)

            if not self.settings.data.staging.retain_normalized_after_success:
                staging.unlink(missing_ok=True)

            record = record.model_copy(update={
                "status": MaterializationStatus.COMPLETE,
                "canonical_rows": canonical_rows,
                "completed_at_utc": datetime.now(UTC),
                "last_error": None,
            })
            self.manifest.put(record)
            return MaterializationResult(
                dataset=dataset,
                trading_date=trading_date,
                source_rows=rows,
                canonical_rows=canonical_rows,
                canonical_path=canonical,
                derived_rows=derived_rows,
                skipped=False,
                quality_status=report.status,
                quarantined_symbols=quarantine_result.symbols,
            )
        except Exception as exc:
            failed = record.model_copy(update={
                "status": MaterializationStatus.FAILED,
                "last_error": f"{type(exc).__name__}: {exc}",
            })
            self.manifest.put(failed)
            raise

    @staticmethod
    def _count(path: Path) -> int:
        con = connect_utc(":memory:")
        try:
            safe = str(path).replace("\\", "/").replace("'", "''")
            return int(con.execute(f"SELECT count(*) FROM read_parquet('{safe}')").fetchone()[0])
        finally:
            con.close()
