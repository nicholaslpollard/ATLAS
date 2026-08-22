from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry
from packages.core.enums import DatasetType, Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_identity_asset_risk import (
    ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_END, ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_validated_evidence import (
    ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
    AlpacaBackfillValidatedEvidenceBuilder,
    AlpacaBackfillValidatedEvidenceValidator,
    sha256_file,
    stable_source_fingerprint,
)
from packages.data.materializer import MATERIALIZATION_CONTRACT_VERSION
from packages.schemas.canonical_market import (
    CANONICAL_STOCK_DAILY_COLUMNS as CANONICAL_DAILY_COLUMNS,
    CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
    CANONICAL_STOCK_DAILY_TYPES as CANONICAL_DAILY_TYPES,
)


ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION = (
    "historical-backfill-candidate-canonical-v1-production-1d-schema-identity-sidecar"
)
CANDIDATE_VERSION_DIR = "v1"
CANDIDATE_ROLE = "ISOLATED_CANDIDATE_CANONICAL_NOT_PRODUCTION"
CANDIDATE_PROVIDER = "alpaca"
CANDIDATE_DATASET = DatasetType.STOCK_DAILY_AGGREGATES.value
CANDIDATE_TIMEFRAME = Timeframe.DAY_1.value
CANDIDATE_SESSION_SEGMENT = "regular"
CANDIDATE_ADJUSTMENT = "raw"
CANDIDATE_ASOF = "-"
TRADE_BACKED_CLASS = "TRADE_BACKED"


def candidate_daily_relative_path(trading_date: date) -> Path:
    return (
        Path("stocks")
        / CANDIDATE_TIMEFRAME
        / f"year={trading_date.year:04d}"
        / f"date={trading_date}"
        / "part-000.parquet"
    )


def candidate_source_id(candidate_fingerprint: str) -> str:
    return f"alpaca:sip:1Day:raw:asof=-:validated:{candidate_fingerprint}"


def candidate_source_fingerprint(
    *,
    validated_evidence_fingerprint: str,
    identity_segments_sha256: str,
    identity_chains_sha256: str,
    identity_report_sha256: str,
    exchange: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
            "production_materialization_contract_version": MATERIALIZATION_CONTRACT_VERSION,
            "canonical_daily_schema_contract_version": CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
            "validated_evidence_contract_version": ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
            "identity_contract_version": ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
            "validated_evidence_fingerprint": validated_evidence_fingerprint,
            "identity_segments_sha256": identity_segments_sha256,
            "identity_chains_sha256": identity_chains_sha256,
            "identity_report_sha256": identity_report_sha256,
            "exchange": exchange,
            "timeframe": CANDIDATE_TIMEFRAME,
            "provider": CANDIDATE_PROVIDER,
            "dataset": CANDIDATE_DATASET,
            "adjustment": CANDIDATE_ADJUSTMENT,
            "asof": CANDIDATE_ASOF,
            "start_date": ALPACA_BACKFILL_START.isoformat(),
            "end_date": ALPACA_BACKFILL_END.isoformat(),
            "canonical_daily_columns": list(CANONICAL_DAILY_COLUMNS),
            "canonical_daily_types": list(CANONICAL_DAILY_TYPES),
        }
    )


def path_is_isolated(candidate_root: Path, canonical_root: Path) -> bool:
    candidate = candidate_root.resolve()
    canonical = canonical_root.resolve()
    try:
        candidate.relative_to(canonical)
        return False
    except ValueError:
        pass
    try:
        canonical.relative_to(candidate)
        return False
    except ValueError:
        return candidate != canonical


def identity_symbols_from_rows(rows: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    result: dict[str, dict[str, object]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip()
        chain_id = str(row.get("identity_chain_id") or "").strip()
        segment_id = str(row.get("segment_id") or "").strip()
        if not symbol or not chain_id or not segment_id:
            raise RuntimeError("Gate 6 identity segment row lacks exact symbol/chain/segment ID")
        if symbol in result:
            raise RuntimeError(f"Gate 6 duplicate exact identity symbol: {symbol!r}")
        result[symbol] = dict(row)
    return result


def _sql_string(value: str | Path) -> str:
    text = str(value).replace("\\", "/").replace("'", "''")
    return f"'{text}'"


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _replace_candidate_year(temp_year: Path, final_year: Path) -> None:
    final_year.parent.mkdir(parents=True, exist_ok=True)
    if final_year.exists():
        shutil.rmtree(final_year)
    replace_with_retry(temp_year, final_year)


class AlpacaBackfillCandidateCanonicalBuilder:
    """Gate 6 isolated candidate materializer from validated Parquet evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
        self.root = root
        self.candidate_root = root / "candidate_canonical" / CANDIDATE_VERSION_DIR
        self.bar_root = self.candidate_root / "stocks" / CANDIDATE_TIMEFRAME
        self.identity_candidate_root = self.candidate_root / "identity"
        self.report_path = self.candidate_root / "candidate_manifest.json"
        self.identity_segment_output_path = self.identity_candidate_root / "identity_segments.parquet"
        self.identity_chain_output_path = self.identity_candidate_root / "identity_chains.parquet"
        self.identity_source_root = root / "identity"
        self.identity_segment_source_path = self.identity_source_root / "identity_segments.parquet"
        self.identity_chain_source_path = self.identity_source_root / "identity_chains.parquet"
        self.identity_report_path = self.identity_source_root / "identity_asset_risk_report.json"
        self.cache_builder = AlpacaBackfillValidatedEvidenceBuilder(settings)
        self.cache_validator = AlpacaBackfillValidatedEvidenceValidator(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.canonical_root = settings.resolved_path(settings.data.paths.canonical)

    def _load_parents(
        self,
    ) -> tuple[dict[str, Any], dict[str, Any], str, dict[int, dict[str, object]]]:
        cache_validation = self.cache_validator.run()
        if cache_validation.get("pass") is not True:
            raise RuntimeError("Gate 6 requires a passing validated-evidence cache")
        cache_report = json.loads(self.cache_builder.report_path.read_text(encoding="utf-8"))
        if cache_report.get("contract_version") != ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION:
            raise RuntimeError("Gate 6 validated-evidence contract mismatch")
        if not self.identity_report_path.is_file():
            raise RuntimeError("Gate 6 requires the accepted Gate 4-D identity report")
        identity_report = json.loads(self.identity_report_path.read_text(encoding="utf-8"))
        if identity_report.get("contract_version") != ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION:
            raise RuntimeError("Gate 6 Gate 4-D identity contract mismatch")
        if identity_report.get("canonical_data_modified") is not False:
            raise RuntimeError("Gate 6 identity parent does not preserve canonical safety")
        for path in (self.identity_segment_source_path, self.identity_chain_source_path):
            if not path.is_file():
                raise RuntimeError(f"Gate 6 identity artifact is missing: {path}")

        fingerprint = candidate_source_fingerprint(
            validated_evidence_fingerprint=str(cache_report["source_fingerprint"]),
            identity_segments_sha256=sha256_file(self.identity_segment_source_path),
            identity_chains_sha256=sha256_file(self.identity_chain_source_path),
            identity_report_sha256=sha256_file(self.identity_report_path),
            exchange=self.settings.data.calendar.exchange,
        )
        partitions = {int(item["year"]): dict(item) for item in cache_report.get("partitions") or []}
        if sorted(partitions) != list(range(ALPACA_BACKFILL_START.year, ALPACA_BACKFILL_END.year + 1)):
            raise RuntimeError("Gate 6 validated-evidence year partitions are incomplete")
        return cache_report, identity_report, fingerprint, partitions

    def _session_frame(self) -> pd.DataFrame:
        rows: list[dict[str, object]] = []
        for session_date in self.calendar.sessions_in_range(ALPACA_BACKFILL_START, ALPACA_BACKFILL_END):
            regular_open, _regular_close = self.calendar.regular_open_close(session_date)
            rows.append({"session_date": session_date, "timestamp_utc": regular_open, "year": session_date.year})
        return pd.DataFrame(rows)

    def _year_manifest_path(self, year: int) -> Path:
        return self.bar_root / f"year={year:04d}" / "_candidate_year_manifest.json"

    def _year_fingerprint(
        self,
        *,
        year: int,
        candidate_fingerprint: str,
        cache_partition: dict[str, object],
    ) -> str:
        return stable_source_fingerprint(
            {
                "contract_version": ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
                "candidate_fingerprint": candidate_fingerprint,
                "year": year,
                "validated_evidence_partition_sha256": cache_partition.get("parquet_sha256"),
                "validated_evidence_partition_fingerprint": cache_partition.get("source_fingerprint"),
            }
        )

    def _valid_year(
        self,
        *,
        year: int,
        expected_fingerprint: str,
        expected_sessions: list[date],
    ) -> dict[str, object] | None:
        manifest_path = self._year_manifest_path(year)
        if not manifest_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("contract_version") != ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION:
                return None
            if manifest.get("source_fingerprint") != expected_fingerprint:
                return None
            files = manifest.get("session_files") or []
            if len(files) != len(expected_sessions):
                return None
            expected_dates = {item.isoformat() for item in expected_sessions}
            actual_dates = {str(item.get("session_date")) for item in files}
            if actual_dates != expected_dates:
                return None
            for item in files:
                path = Path(str(item.get("path") or ""))
                if not path.is_file() or sha256_file(path) != item.get("sha256"):
                    return None
            return manifest
        except Exception:
            return None

    def _build_year(
        self,
        *,
        year: int,
        cache_partition: dict[str, object],
        expected_sessions: list[date],
        year_fingerprint: str,
        source_id: str,
        session_frame: pd.DataFrame,
    ) -> dict[str, object]:
        source_path = Path(str(cache_partition["parquet_path"]))
        if not source_path.is_file():
            raise RuntimeError(f"Gate 6 missing validated-evidence partition: {source_path}")

        final_year = self.bar_root / f"year={year:04d}"
        temp_year = self.bar_root / f".year={year:04d}.{uuid.uuid4().hex}.building"
        if temp_year.exists():
            shutil.rmtree(temp_year)
        temp_year.parent.mkdir(parents=True, exist_ok=True)

        year_sessions = session_frame.loc[session_frame["year"] == year, ["session_date", "timestamp_utc"]].copy()
        con = duckdb.connect(":memory:")
        con.execute("PRAGMA threads=1")
        con.register("session_open", year_sessions)
        identity_source = _sql_string(self.identity_segment_source_path)
        evidence_source = _sql_string(source_path)
        sid = _sql_literal(source_id)
        provider = _sql_literal(CANDIDATE_PROVIDER)
        dataset = _sql_literal(CANDIDATE_DATASET)
        timeframe = _sql_literal(CANDIDATE_TIMEFRAME)
        segment = _sql_literal(CANDIDATE_SESSION_SEGMENT)
        trade_class = _sql_literal(TRADE_BACKED_CLASS)

        try:
            mapping = con.execute(
                f"""
                SELECT
                    count(*) FILTER (WHERE i.symbol IS NULL) AS missing_identity,
                    count(*) FILTER (
                        WHERE i.symbol IS NOT NULL
                          AND (e.session_date < CAST(i.first_date AS DATE)
                               OR e.session_date > CAST(i.last_date AS DATE))
                    ) AS outside_identity_interval,
                    count(*) FILTER (WHERE s.session_date IS NULL) AS missing_session_open,
                    count(*) FILTER (WHERE e.trade_count != floor(e.trade_count)) AS fractional_transactions,
                    count(*) AS trade_rows,
                    count(DISTINCT e.provider_symbol) AS symbols
                FROM read_parquet({evidence_source}) e
                LEFT JOIN read_parquet({identity_source}) i ON e.provider_symbol = i.symbol
                LEFT JOIN session_open s ON e.session_date = s.session_date
                WHERE e.bar_class = {trade_class}
                """
            ).fetchone()
            assert mapping is not None
            if any(int(mapping[index] or 0) != 0 for index in range(4)):
                raise RuntimeError(
                    "Gate 6 year mapping invariant failed: "
                    f"year={year} missing_identity={mapping[0]} "
                    f"outside_identity_interval={mapping[1]} "
                    f"missing_session_open={mapping[2]} "
                    f"fractional_transactions={mapping[3]}"
                )

            temp_sql = _sql_string(temp_year)
            compression = str(self.settings.data.parquet.compression).upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (
                    SELECT
                        e.provider_symbol AS symbol,
                        CAST(s.timestamp_utc AS TIMESTAMPTZ) AS timestamp_utc,
                        e.session_date AS session_date,
                        {timeframe} AS timeframe,
                        {segment} AS session_segment,
                        e.open::DOUBLE AS open,
                        e.high::DOUBLE AS high,
                        e.low::DOUBLE AS low,
                        e.close::DOUBLE AS close,
                        e.volume::DOUBLE AS volume,
                        e.vwap::DOUBLE AS vwap,
                        CAST(e.trade_count AS BIGINT) AS transaction_count,
                        {provider} AS provider,
                        {dataset} AS dataset,
                        {sid} AS source_id,
                        FALSE::BOOLEAN AS is_adjusted,
                        CAST(e.timestamp_utc AS TIMESTAMPTZ) AS provider_timestamp_utc,
                        CAST(e.session_date AS VARCHAR) AS date
                    FROM read_parquet({evidence_source}) e
                    JOIN session_open s ON e.session_date = s.session_date
                    JOIN read_parquet({identity_source}) i
                        ON e.provider_symbol = i.symbol
                       AND e.session_date >= CAST(i.first_date AS DATE)
                       AND e.session_date <= CAST(i.last_date AS DATE)
                    WHERE e.bar_class = {trade_class}
                    ORDER BY e.session_date, e.provider_symbol
                )
                TO {temp_sql}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size}, PARTITION_BY (date))
                """
            )
        finally:
            con.unregister("session_open")
            con.close()

        expected_dates = {item.isoformat() for item in expected_sessions}
        date_dirs = sorted(path for path in temp_year.glob("date=*") if path.is_dir())
        actual_dates = {path.name.split("=", 1)[1] for path in date_dirs}
        if actual_dates != expected_dates:
            shutil.rmtree(temp_year, ignore_errors=True)
            raise RuntimeError(
                f"Gate 6 year {year} session partition mismatch: expected={len(expected_dates)} actual={len(actual_dates)}"
            )

        session_files: list[dict[str, object]] = []
        total_rows = 0
        for directory in date_dirs:
            session_text = directory.name.split("=", 1)[1]
            files = sorted(directory.glob("*.parquet"))
            if len(files) != 1:
                shutil.rmtree(temp_year, ignore_errors=True)
                raise RuntimeError(f"Gate 6 expected one Parquet file for {session_text}, found {len(files)}")
            source_file = files[0]
            final_name = directory / "part-000.parquet"
            if source_file != final_name:
                replace_with_retry(source_file, final_name)
            con = duckdb.connect(":memory:")
            try:
                count = int(con.execute("SELECT count(*) FROM read_parquet(?)", [str(final_name)]).fetchone()[0])
            finally:
                con.close()
            if count <= 0:
                shutil.rmtree(temp_year, ignore_errors=True)
                raise RuntimeError(f"Gate 6 empty candidate session: {session_text}")
            total_rows += count
            final_path = self.bar_root / f"year={year:04d}" / f"date={session_text}" / "part-000.parquet"
            session_files.append(
                {
                    "session_date": session_text,
                    "rows": count,
                    "relative_path": str(candidate_daily_relative_path(date.fromisoformat(session_text))).replace("\\", "/"),
                    "path": str(final_path),
                    "sha256": sha256_file(final_name),
                }
            )

        partition_manifest = {
            "contract_version": ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
            "year": year,
            "source_fingerprint": year_fingerprint,
            "candidate_source_id": source_id,
            "rows": total_rows,
            "symbols": int(mapping[5]),
            "session_count": len(session_files),
            "session_files": session_files,
            "canonical_data_modified": False,
        }
        atomic_write_text(
            temp_year / "_candidate_year_manifest.json",
            json.dumps(partition_manifest, indent=2, sort_keys=True) + "\n",
        )
        _replace_candidate_year(temp_year, final_year)
        return partition_manifest

    def _build_identity_sidecars(self, *, evidence_paths: list[Path]) -> dict[str, int]:
        self.identity_candidate_root.mkdir(parents=True, exist_ok=True)
        con = duckdb.connect(":memory:")
        try:
            con.read_parquet([str(path) for path in evidence_paths]).create_view("evidence")
            con.execute(
                "CREATE TEMP VIEW candidate_counts AS "
                "SELECT provider_symbol AS symbol, count(*) AS candidate_rows, "
                "min(session_date) AS first_candidate_session, max(session_date) AS last_candidate_session "
                "FROM evidence WHERE bar_class='TRADE_BACKED' GROUP BY provider_symbol"
            )

            temp_segments = self.identity_segment_output_path.with_name(
                f".{self.identity_segment_output_path.name}.{uuid.uuid4().hex}.tmp"
            )
            con.execute(
                f"""
                COPY (
                    SELECT i.*, c.candidate_rows, c.first_candidate_session, c.last_candidate_session
                    FROM read_parquet({_sql_string(self.identity_segment_source_path)}) i
                    LEFT JOIN candidate_counts c USING (symbol)
                    ORDER BY i.identity_chain_id, i.chain_position, i.symbol
                )
                TO {_sql_string(temp_segments)} (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
            replace_with_retry(temp_segments, self.identity_segment_output_path)

            temp_chains = self.identity_chain_output_path.with_name(
                f".{self.identity_chain_output_path.name}.{uuid.uuid4().hex}.tmp"
            )
            con.execute(
                f"""
                COPY (
                    WITH segment_counts AS (
                        SELECT i.identity_chain_id,
                               sum(c.candidate_rows) AS candidate_rows,
                               min(c.first_candidate_session) AS first_candidate_session,
                               max(c.last_candidate_session) AS last_candidate_session
                        FROM read_parquet({_sql_string(self.identity_segment_source_path)}) i
                        LEFT JOIN candidate_counts c USING (symbol)
                        GROUP BY i.identity_chain_id
                    )
                    SELECT ch.*, sc.candidate_rows, sc.first_candidate_session, sc.last_candidate_session
                    FROM read_parquet({_sql_string(self.identity_chain_source_path)}) ch
                    LEFT JOIN segment_counts sc USING (identity_chain_id)
                    ORDER BY ch.first_symbol, ch.identity_chain_id
                )
                TO {_sql_string(temp_chains)} (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
            replace_with_retry(temp_chains, self.identity_chain_output_path)

            segment_stats = con.execute(
                f"""
                SELECT count(*), count(DISTINCT symbol), sum(candidate_rows),
                       count(*) FILTER (WHERE candidate_rows IS NULL OR candidate_rows <= 0),
                       count(*) FILTER (WHERE coalesce(identity_ambiguous, FALSE))
                FROM read_parquet({_sql_string(self.identity_segment_output_path)})
                """
            ).fetchone()
            chain_stats = con.execute(
                f"""
                SELECT count(*), sum(candidate_rows),
                       count(*) FILTER (WHERE candidate_rows IS NULL OR candidate_rows <= 0)
                FROM read_parquet({_sql_string(self.identity_chain_output_path)})
                """
            ).fetchone()
            assert segment_stats is not None and chain_stats is not None
        finally:
            con.close()
        return {
            "identity_segments": int(segment_stats[0]),
            "identity_symbols": int(segment_stats[1]),
            "identity_segment_candidate_rows": int(segment_stats[2] or 0),
            "identity_segments_without_candidate_rows": int(segment_stats[3] or 0),
            "identity_ambiguous_symbols": int(segment_stats[4] or 0),
            "identity_chains": int(chain_stats[0]),
            "identity_chain_candidate_rows": int(chain_stats[1] or 0),
            "identity_chains_without_candidate_rows": int(chain_stats[2] or 0),
        }

    def run(self, *, force: bool = False) -> dict[str, object]:
        cache_report, identity_report, fingerprint, cache_partitions = self._load_parents()
        if not path_is_isolated(self.candidate_root, self.canonical_root):
            raise RuntimeError("Gate 6 candidate namespace is not isolated from canonical")

        self.candidate_root.mkdir(parents=True, exist_ok=True)
        session_frame = self._session_frame()
        expected_sessions = [
            value if isinstance(value, date) else pd.Timestamp(value).date()
            for value in session_frame["session_date"].tolist()
        ]
        source_id = candidate_source_id(fingerprint)
        year_manifests: list[dict[str, object]] = []
        rebuilt_years: list[int] = []

        for year in range(ALPACA_BACKFILL_START.year, ALPACA_BACKFILL_END.year + 1):
            year_sessions = [item for item in expected_sessions if item.year == year]
            year_fp = self._year_fingerprint(
                year=year,
                candidate_fingerprint=fingerprint,
                cache_partition=cache_partitions[year],
            )
            existing = None if force else self._valid_year(
                year=year,
                expected_fingerprint=year_fp,
                expected_sessions=year_sessions,
            )
            if existing is not None:
                year_manifests.append(existing)
                continue
            built = self._build_year(
                year=year,
                cache_partition=cache_partitions[year],
                expected_sessions=year_sessions,
                year_fingerprint=year_fp,
                source_id=source_id,
                session_frame=session_frame,
            )
            year_manifests.append(built)
            rebuilt_years.append(year)

        evidence_paths = [Path(str(cache_partitions[year]["parquet_path"])) for year in sorted(cache_partitions)]
        identity_stats = self._build_identity_sidecars(evidence_paths=evidence_paths)

        candidate_rows = sum(int(item["rows"]) for item in year_manifests)
        candidate_sessions = sum(int(item["session_count"]) for item in year_manifests)
        placeholder_rows = int(cache_report["zero_activity_placeholder_rows"])
        report = {
            "contract_version": ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
            "production_materialization_contract_version": MATERIALIZATION_CONTRACT_VERSION,
            "canonical_daily_schema_contract_version": CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
            "validated_evidence_contract_version": ALPACA_BACKFILL_VALIDATED_EVIDENCE_CONTRACT_VERSION,
            "identity_contract_version": ALPACA_BACKFILL_IDENTITY_ASSET_RISK_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "canonical_data_modified": False,
            "candidate_role": CANDIDATE_ROLE,
            "source_fingerprint": fingerprint,
            "validated_evidence_source_fingerprint": cache_report["source_fingerprint"],
            "candidate_source_id": source_id,
            "provider": CANDIDATE_PROVIDER,
            "feed": "sip",
            "timeframe": CANDIDATE_TIMEFRAME,
            "dataset": CANDIDATE_DATASET,
            "adjustment": CANDIDATE_ADJUSTMENT,
            "asof": CANDIDATE_ASOF,
            "exchange_calendar": self.settings.data.calendar.exchange,
            "target_start": ALPACA_BACKFILL_START.isoformat(),
            "target_end": ALPACA_BACKFILL_END.isoformat(),
            "candidate_rows": candidate_rows,
            "expected_trade_backed_rows": int(cache_report["trade_backed_rows"]),
            "excluded_zero_activity_placeholder_rows": placeholder_rows,
            "candidate_sessions": candidate_sessions,
            "expected_exchange_sessions": len(expected_sessions),
            "observed_symbols": int(cache_report["observed_symbols"]),
            "year_manifests": year_manifests,
            "rebuilt_years": rebuilt_years,
            "identity": {
                **identity_stats,
                "expected_segments": int(identity_report["resulting_identity_segments"]),
                "expected_chains": int(identity_report["resulting_identity_chains"]),
                "source_segments_sha256": sha256_file(self.identity_segment_source_path),
                "source_chains_sha256": sha256_file(self.identity_chain_source_path),
                "candidate_segments_sha256": sha256_file(self.identity_segment_output_path),
                "candidate_chains_sha256": sha256_file(self.identity_chain_output_path),
            },
            "canonical_daily_columns": list(CANONICAL_DAILY_COLUMNS),
            "canonical_daily_types": list(CANONICAL_DAILY_TYPES),
            "candidate_root": str(self.candidate_root),
            "production_canonical_root": str(self.canonical_root),
            "report_path": str(self.report_path),
        }
        if candidate_rows != int(cache_report["trade_backed_rows"]):
            raise RuntimeError("Gate 6 candidate row count differs from trade-backed evidence")
        if candidate_sessions != len(expected_sessions):
            raise RuntimeError("Gate 6 candidate session coverage differs from exchange calendar")
        if identity_stats["identity_segment_candidate_rows"] != candidate_rows:
            raise RuntimeError("Gate 6 identity segment row accounting mismatch")
        if identity_stats["identity_chain_candidate_rows"] != candidate_rows:
            raise RuntimeError("Gate 6 identity chain row accounting mismatch")
        if identity_stats["identity_segments_without_candidate_rows"] != 0:
            raise RuntimeError("Gate 6 identity segment without trade-backed candidate rows")
        if identity_stats["identity_chains_without_candidate_rows"] != 0:
            raise RuntimeError("Gate 6 identity chain without trade-backed candidate rows")
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report


class AlpacaBackfillCandidateCanonicalValidator:
    """Fast Gate 6 validator over isolated candidate Parquet outputs."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.builder = AlpacaBackfillCandidateCanonicalBuilder(settings)

    def run(self) -> dict[str, object]:
        if not self.builder.report_path.is_file():
            raise RuntimeError("Gate 6 candidate manifest is missing")
        report = json.loads(self.builder.report_path.read_text(encoding="utf-8"))
        cache_report, identity_report, current_fingerprint, _cache_partitions = self.builder._load_parents()

        files: list[Path] = []
        hash_failures = 0
        manifest_session_rows = 0
        for year_manifest in report.get("year_manifests") or []:
            for item in year_manifest.get("session_files") or []:
                path = Path(str(item.get("path") or ""))
                files.append(path)
                manifest_session_rows += int(item.get("rows", 0))
                if not path.is_file() or sha256_file(path) != item.get("sha256"):
                    hash_failures += 1

        counts = {
            "rows": -1,
            "symbols": -1,
            "sessions": -1,
            "duplicates": -1,
            "schema_exact": False,
            "semantic_timestamp_mismatches": -1,
            "provider_timestamp_nulls": -1,
            "nonpositive_trade_fields": -1,
            "constant_semantic_mismatches": -1,
            "identity_mapping_failures": -1,
            "identity_interval_failures": -1,
            "identity_sidecar_rows": -1,
            "identity_sidecar_candidate_rows": -1,
            "chain_sidecar_rows": -1,
            "chain_sidecar_candidate_rows": -1,
        }

        expected_sessions = self.builder.calendar.sessions_in_range(ALPACA_BACKFILL_START, ALPACA_BACKFILL_END)
        session_frame = self.builder._session_frame()

        if hash_failures == 0 and len(files) == len(expected_sessions):
            con = duckdb.connect(":memory:")
            con.register("session_open", session_frame[["session_date", "timestamp_utc"]])
            con.read_parquet([str(path) for path in files]).create_view("candidate")
            try:
                description = con.execute("DESCRIBE candidate").fetchall()
                columns = tuple(str(row[0]) for row in description)
                types = tuple(str(row[1]) for row in description)
                counts["schema_exact"] = columns == CANONICAL_DAILY_COLUMNS and types == CANONICAL_DAILY_TYPES

                aggregate = con.execute(
                    """
                    SELECT count(*), count(DISTINCT symbol), count(DISTINCT session_date),
                           count(*) FILTER (WHERE provider_timestamp_utc IS NULL),
                           count(*) FILTER (WHERE volume <= 0 OR transaction_count < 0 OR vwap <= 0),
                           count(*) FILTER (
                               WHERE timeframe != ? OR session_segment != ?
                                  OR provider != ? OR dataset != ?
                                  OR source_id != ? OR is_adjusted IS DISTINCT FROM FALSE
                           )
                    FROM candidate
                    """,
                    [
                        CANDIDATE_TIMEFRAME,
                        CANDIDATE_SESSION_SEGMENT,
                        CANDIDATE_PROVIDER,
                        CANDIDATE_DATASET,
                        str(report.get("candidate_source_id")),
                    ],
                ).fetchone()
                assert aggregate is not None
                counts.update(
                    {
                        "rows": int(aggregate[0]),
                        "symbols": int(aggregate[1]),
                        "sessions": int(aggregate[2]),
                        "provider_timestamp_nulls": int(aggregate[3]),
                        "nonpositive_trade_fields": int(aggregate[4]),
                        "constant_semantic_mismatches": int(aggregate[5]),
                    }
                )

                duplicate = con.execute(
                    """
                    SELECT coalesce(sum(n - 1), 0)
                    FROM (
                        SELECT symbol, timestamp_utc, timeframe, session_segment, count(*) n
                        FROM candidate GROUP BY ALL HAVING count(*) > 1
                    )
                    """
                ).fetchone()
                counts["duplicates"] = int(duplicate[0]) if duplicate else -1

                timestamp_mismatch = con.execute(
                    """
                    SELECT count(*)
                    FROM candidate c
                    LEFT JOIN session_open s USING (session_date)
                    WHERE s.session_date IS NULL
                       OR c.timestamp_utc != CAST(s.timestamp_utc AS TIMESTAMPTZ)
                    """
                ).fetchone()
                counts["semantic_timestamp_mismatches"] = int(timestamp_mismatch[0]) if timestamp_mismatch else -1

                identity = con.execute(
                    f"""
                    SELECT count(*) FILTER (WHERE i.symbol IS NULL),
                           count(*) FILTER (
                               WHERE i.symbol IS NOT NULL
                                 AND (c.session_date < CAST(i.first_date AS DATE)
                                      OR c.session_date > CAST(i.last_date AS DATE))
                           )
                    FROM candidate c
                    LEFT JOIN read_parquet({_sql_string(self.builder.identity_segment_output_path)}) i
                        ON c.symbol = i.symbol
                    """
                ).fetchone()
                assert identity is not None
                counts["identity_mapping_failures"] = int(identity[0])
                counts["identity_interval_failures"] = int(identity[1])

                segment = con.execute(
                    f"SELECT count(*), sum(candidate_rows) FROM read_parquet({_sql_string(self.builder.identity_segment_output_path)})"
                ).fetchone()
                chain = con.execute(
                    f"SELECT count(*), sum(candidate_rows) FROM read_parquet({_sql_string(self.builder.identity_chain_output_path)})"
                ).fetchone()
                assert segment is not None and chain is not None
                counts["identity_sidecar_rows"] = int(segment[0])
                counts["identity_sidecar_candidate_rows"] = int(segment[1] or 0)
                counts["chain_sidecar_rows"] = int(chain[0])
                counts["chain_sidecar_candidate_rows"] = int(chain[1] or 0)
            finally:
                con.unregister("session_open")
                con.close()

        checks = {
            "candidate_contract": report.get("contract_version") == ALPACA_BACKFILL_CANDIDATE_CANONICAL_CONTRACT_VERSION,
            "canonical_daily_schema_contract": report.get("canonical_daily_schema_contract_version") == CANONICAL_STOCK_DAILY_SCHEMA_VERSION,
            "candidate_role_isolated": report.get("candidate_role") == CANDIDATE_ROLE,
            "candidate_source_fingerprint_exact": report.get("source_fingerprint") == current_fingerprint,
            "validated_evidence_source_fingerprint_exact": report.get("validated_evidence_source_fingerprint") == cache_report.get("source_fingerprint"),
            "production_canonical_path_isolated": path_is_isolated(self.builder.candidate_root, self.builder.canonical_root),
            "canonical_data_untouched": report.get("canonical_data_modified") is False,
            "session_file_hashes_exact": hash_failures == 0,
            "all_exchange_sessions_materialized": len(files) == len(expected_sessions) == int(report.get("candidate_sessions", -1)),
            "manifest_row_accounting_exact": manifest_session_rows == int(report.get("candidate_rows", -1)),
            "production_daily_schema_exact": counts["schema_exact"] is True,
            "candidate_rows_equal_trade_backed_evidence": counts["rows"] == int(cache_report.get("trade_backed_rows", -1)) == int(report.get("candidate_rows", -2)),
            "candidate_symbol_coverage_exact": counts["symbols"] == int(cache_report.get("observed_symbols", -1)) == int(report.get("observed_symbols", -2)),
            "candidate_session_coverage_exact": counts["sessions"] == len(expected_sessions),
            "candidate_duplicate_keys_zero": counts["duplicates"] == 0,
            "candidate_semantic_timestamps_exact": counts["semantic_timestamp_mismatches"] == 0,
            "candidate_provider_timestamps_present": counts["provider_timestamp_nulls"] == 0,
            "candidate_trade_backed_fields_valid": counts["nonpositive_trade_fields"] == 0,
            "candidate_constant_semantics_exact": counts["constant_semantic_mismatches"] == 0,
            "candidate_identity_mapping_exact": counts["identity_mapping_failures"] == 0 and counts["identity_interval_failures"] == 0,
            "identity_segment_count_exact": counts["identity_sidecar_rows"] == int(identity_report.get("resulting_identity_segments", -1)),
            "identity_chain_count_exact": counts["chain_sidecar_rows"] == int(identity_report.get("resulting_identity_chains", -1)),
            "identity_segment_row_accounting_exact": counts["identity_sidecar_candidate_rows"] == counts["rows"],
            "identity_chain_row_accounting_exact": counts["chain_sidecar_candidate_rows"] == counts["rows"],
            "zero_activity_placeholders_excluded": (
                int(report.get("excluded_zero_activity_placeholder_rows", -1)) == int(cache_report.get("zero_activity_placeholder_rows", -2))
                and counts["rows"] + int(report.get("excluded_zero_activity_placeholder_rows", -1)) == int(cache_report.get("identity_safe_rows", -3))
            ),
        }
        return {
            "contract_version": report.get("contract_version"),
            "source_fingerprint": report.get("source_fingerprint"),
            "counts": counts,
            "checks": checks,
            "pass": all(checks.values()),
        }