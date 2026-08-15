from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from packages.core.enums import DataQualityCode, DataQualitySeverity
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.schemas.data_quality import DataQualityIssue

try:
    import duckdb
except ImportError:  # pragma: no cover
    duckdb = None


@dataclass(frozen=True, slots=True)
class SymbolQuarantineResult:
    symbols: tuple[str, ...] = ()
    exact_duplicate_rows_removed: int = 0
    conflicting_rows_quarantined: int = 0
    quarantine_path: Path | None = None

    def quality_issues(self) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        if self.exact_duplicate_rows_removed:
            issues.append(
                DataQualityIssue(
                    code=DataQualityCode.DUPLICATE_BAR,
                    severity=DataQualitySeverity.WARNING,
                    message="Exact duplicate provider rows were removed deterministically",
                    details={"count": self.exact_duplicate_rows_removed},
                )
            )
        if self.symbols:
            issues.append(
                DataQualityIssue(
                    code=DataQualityCode.SYMBOL_CONFLICT,
                    severity=DataQualitySeverity.WARNING,
                    message="Conflicting provider rows were quarantined for the affected symbols",
                    details={
                        "count": self.conflicting_rows_quarantined,
                        "symbol_count": len(self.symbols),
                        "symbols": list(self.symbols),
                    },
                )
            )
        return issues


class SessionSymbolQuarantine:
    """Safely isolate ambiguous provider-symbol data without guessing a winner.

    Massive aggregate flat files identify observations by ticker text only. If a
    daily source contains materially different rows for the same exact provider
    ticker/date, ATLAS cannot prove which row belongs to the point-in-time
    instrument from the flat file alone. The deterministic response is therefore
    to quarantine that symbol for the whole session, not keep-first/keep-last.

    Provider symbol case is significant. In particular, Massive uses lowercase
    'p' in preferred-share symbols, so BCPC and BCpC are distinct tickers.
    """

    def __init__(self, *, compression: str = "zstd", row_group_size: int = 122_880) -> None:
        if duckdb is None:
            raise RuntimeError("duckdb is required for Phase 3. Run: pip install -r requirements.lock")
        self.compression = compression.upper()
        self.row_group_size = row_group_size

    @staticmethod
    def _symbol_list_sql(symbols: tuple[str, ...] | list[str]) -> str:
        return ", ".join("'" + symbol.replace("'", "''") + "'" for symbol in symbols)

    @staticmethod
    def _write_registry(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
        temp.replace(path)

    @staticmethod
    def load_registry(path: Path) -> tuple[str, ...]:
        path = Path(path)
        if not path.exists():
            return ()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return tuple(sorted({str(x).strip() for x in payload.get("symbols", []) if str(x).strip()}))

    def _rewrite(self, source_path: Path, select_sql: str) -> None:
        temp = atomic_target(source_path)
        temp.unlink(missing_ok=True)
        out = sql_string(temp)
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"COPY ({select_sql}) TO {out} "
                f"(FORMAT PARQUET, COMPRESSION {self.compression}, ROW_GROUP_SIZE {self.row_group_size})"
            )
        finally:
            con.close()
        promote(temp, source_path)

    def sanitize_daily(
        self,
        staging_path: Path,
        *,
        trading_date: date,
        quarantine_path: Path,
        registry_path: Path,
    ) -> SymbolQuarantineResult:
        staging_path = Path(staging_path)
        source = f"read_parquet({sql_string(staging_path)})"
        con = connect_utc(":memory:")
        try:
            before = int(con.execute(f"SELECT count(*) FROM {source}").fetchone()[0])
            distinct_count = int(con.execute(f"SELECT count(*) FROM (SELECT DISTINCT * FROM {source})").fetchone()[0])
        finally:
            con.close()

        exact_removed = before - distinct_count
        if exact_removed:
            self._rewrite(staging_path, f"SELECT DISTINCT * FROM {source}")
            source = f"read_parquet({sql_string(staging_path)})"

        con = connect_utc(":memory:")
        try:
            conflict_rows = con.execute(
                f"""
                WITH duplicate_keys AS (
                    SELECT symbol, timestamp_utc, timeframe, session_segment
                    FROM {source}
                    GROUP BY ALL
                    HAVING count(*) > 1
                )
                SELECT p.symbol, p.timestamp_utc, p.open, p.high, p.low, p.close,
                       p.volume, p.transaction_count, p.provider_timestamp_utc
                FROM {source} p
                INNER JOIN duplicate_keys d
                  USING (symbol, timestamp_utc, timeframe, session_segment)
                ORDER BY p.symbol, p.open, p.close, p.volume
                """
            ).fetchall()
        finally:
            con.close()

        symbols = tuple(sorted({str(row[0]) for row in conflict_rows}))
        if symbols:
            sym_sql = self._symbol_list_sql(symbols)
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            qtemp = atomic_target(quarantine_path)
            qtemp.unlink(missing_ok=True)
            con = connect_utc(":memory:")
            try:
                con.execute(
                    f"COPY (SELECT *, 'conflicting_daily_symbol_rows' AS quarantine_reason "
                    f"FROM {source} WHERE symbol IN ({sym_sql})) TO {sql_string(qtemp)} "
                    f"(FORMAT PARQUET, COMPRESSION {self.compression}, ROW_GROUP_SIZE {self.row_group_size})"
                )
            finally:
                con.close()
            promote(qtemp, quarantine_path)
            self._rewrite(staging_path, f"SELECT * FROM {source} WHERE symbol NOT IN ({sym_sql})")
        else:
            quarantine_path.unlink(missing_ok=True)

        samples = [
            {
                "symbol": row[0],
                "timestamp_utc": row[1].isoformat() if row[1] else None,
                "open": row[2],
                "high": row[3],
                "low": row[4],
                "close": row[5],
                "volume": row[6],
                "transaction_count": row[7],
                "provider_timestamp_utc": row[8].isoformat() if row[8] else None,
            }
            for row in conflict_rows[:40]
        ]
        self._write_registry(
            registry_path,
            {
                "trading_date": trading_date.isoformat(),
                "reason": "conflicting_daily_symbol_rows",
                "policy": "quarantine_entire_exact_provider_symbol_session_no_guess",
                "symbols": list(symbols),
                "exact_duplicate_rows_removed": exact_removed,
                "conflicting_rows_quarantined": len(conflict_rows),
                "samples": samples,
            },
        )
        return SymbolQuarantineResult(
            symbols=symbols,
            exact_duplicate_rows_removed=exact_removed,
            conflicting_rows_quarantined=len(conflict_rows),
            quarantine_path=quarantine_path if symbols else None,
        )

    def apply_registry(
        self,
        staging_path: Path,
        *,
        registry_path: Path,
        quarantine_path: Path,
    ) -> SymbolQuarantineResult:
        symbols = self.load_registry(registry_path)
        if not symbols:
            quarantine_path.unlink(missing_ok=True)
            return SymbolQuarantineResult()

        source = f"read_parquet({sql_string(staging_path)})"
        sym_sql = self._symbol_list_sql(symbols)
        con = connect_utc(":memory:")
        try:
            count = int(con.execute(f"SELECT count(*) FROM {source} WHERE symbol IN ({sym_sql})").fetchone()[0])
        finally:
            con.close()

        if count:
            quarantine_path.parent.mkdir(parents=True, exist_ok=True)
            qtemp = atomic_target(quarantine_path)
            qtemp.unlink(missing_ok=True)
            con = connect_utc(":memory:")
            try:
                con.execute(
                    f"COPY (SELECT *, 'session_symbol_quarantine' AS quarantine_reason "
                    f"FROM {source} WHERE symbol IN ({sym_sql})) TO {sql_string(qtemp)} "
                    f"(FORMAT PARQUET, COMPRESSION {self.compression}, ROW_GROUP_SIZE {self.row_group_size})"
                )
            finally:
                con.close()
            promote(qtemp, quarantine_path)
            self._rewrite(staging_path, f"SELECT * FROM {source} WHERE symbol NOT IN ({sym_sql})")
        else:
            quarantine_path.unlink(missing_ok=True)

        return SymbolQuarantineResult(
            symbols=symbols,
            conflicting_rows_quarantined=count,
            quarantine_path=quarantine_path if count else None,
        )
