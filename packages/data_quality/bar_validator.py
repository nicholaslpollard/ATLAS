from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import (
    DataQualityCode,
    DataQualitySeverity,
    DatasetType,
    ValidationStatus,
)
from packages.schemas.data_quality import DataQualityIssue, DataQualityReport
from packages.data.sql import sql_string

from packages.data.duckdb_connection import connect_utc

try:
    import duckdb
except ImportError:  # pragma: no cover - dependency error explained at runtime
    duckdb = None


class QualityGateError(RuntimeError):
    pass


@dataclass(slots=True)
class ParquetBarValidator:
    dataset: DatasetType
    trading_date: date

    def validate(self, parquet_path: Path) -> DataQualityReport:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        path = Path(parquet_path)
        if not path.exists():
            raise FileNotFoundError(path)

        con = connect_utc(":memory:")
        source = f"read_parquet({sql_string(path)})"
        try:
            metrics = con.execute(
                f"""
                SELECT
                    count(*) AS rows,
                    count(*) FILTER (WHERE symbol IS NULL OR trim(symbol) = '') AS blank_symbol,
                    count(*) FILTER (WHERE timestamp_utc IS NULL) AS null_timestamp,
                    count(*) FILTER (WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL) AS null_ohlc,
                    count(*) FILTER (WHERE high < low OR high < open OR high < close OR low > open OR low > close) AS invalid_ohlc,
                    count(*) FILTER (WHERE volume IS NULL OR volume < 0) AS invalid_volume,
                    count(*) FILTER (WHERE transaction_count IS NOT NULL AND transaction_count < 0) AS invalid_transactions,
                    count(*) FILTER (WHERE session_segment = 'closed') AS closed_session_rows
                FROM {source}
                """
            ).fetchone()
            duplicate_rows = con.execute(
                f"""
                SELECT coalesce(sum(n - 1), 0)
                FROM (
                    SELECT symbol, timestamp_utc, timeframe, session_segment, count(*) n
                    FROM {source}
                    GROUP BY ALL
                    HAVING count(*) > 1
                )
                """
            ).fetchone()[0]
        finally:
            con.close()

        rows, blank_symbol, null_timestamp, null_ohlc, invalid_ohlc, invalid_volume, invalid_transactions, closed_rows = metrics
        issues: list[DataQualityIssue] = []

        def add(code: DataQualityCode, severity: DataQualitySeverity, count: int, message: str) -> None:
            if count:
                issues.append(DataQualityIssue(code=code, severity=severity, message=message, details={"count": int(count)}))

        add(DataQualityCode.INVALID_SYMBOL, DataQualitySeverity.ERROR, blank_symbol, "Blank symbols found")
        add(DataQualityCode.INVALID_TIMESTAMP, DataQualitySeverity.ERROR, null_timestamp, "Null timestamps found")
        add(DataQualityCode.NULL_VALUE, DataQualitySeverity.ERROR, null_ohlc, "Null OHLC values found")
        add(DataQualityCode.INVALID_OHLC, DataQualitySeverity.ERROR, invalid_ohlc, "Invalid OHLC geometry found")
        add(DataQualityCode.NEGATIVE_VOLUME, DataQualitySeverity.ERROR, invalid_volume, "Negative or null volume found")
        add(DataQualityCode.NEGATIVE_TRANSACTIONS, DataQualitySeverity.ERROR, invalid_transactions, "Negative transaction counts found")
        add(DataQualityCode.DUPLICATE_BAR, DataQualitySeverity.ERROR, duplicate_rows, "Duplicate canonical bar keys found")
        add(DataQualityCode.SESSION_MISMATCH, DataQualitySeverity.WARNING, closed_rows, "Rows outside configured market session envelope found")

        blocking = sum(int(issue.details.get("count", 1)) for issue in issues if issue.severity in {DataQualitySeverity.ERROR, DataQualitySeverity.CRITICAL})
        warnings = sum(int(issue.details.get("count", 1)) for issue in issues if issue.severity == DataQualitySeverity.WARNING)
        score = max(0.0, 100.0 - min(100.0, (blocking * 100.0 / max(rows, 1)) * 20.0 + (warnings * 100.0 / max(rows, 1)) * 2.0))
        return DataQualityReport(dataset=self.dataset, trading_date=self.trading_date, checked_rows=int(rows), score=score, issues=issues)

    @staticmethod
    def persist(report: DataQualityReport, path: Path) -> None:
        atomic_write_text(path, report.model_dump_json(indent=2) + "\n")

    @staticmethod
    def enforce(report: DataQualityReport) -> None:
        if report.status == ValidationStatus.INVALID:
            raise QualityGateError(
                f"Data-quality gate failed for {report.dataset.value} {report.trading_date}: "
                f"{report.blocking_issue_count} blocking issue categories"
            )