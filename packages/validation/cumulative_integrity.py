from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Callable

from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.data.alpaca_backfill_identity_policy import ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION
from packages.data.alpaca_backfill_identity_segments import ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_START
from packages.data.duckdb_connection import connect_utc
from packages.features.partition_store import sha256_file
from packages.ml.historical_backfill_closeout import HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION
from packages.regimes.split_origin_policy import (
    INTRADAY_POLICY,
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)

from .cumulative_foundation import (
    CumulativeFoundationAuditError,
    CumulativeFoundationAuditor,
    _json,
    _partition_date,
    _sql,
)


def _daily_integrity_sql(transaction_column: str = "transaction_count") -> str:
    """Return the exhaustive daily integrity query for the accepted canonical schema."""

    if transaction_column != "transaction_count":
        raise CumulativeFoundationAuditError(
            f"unexpected canonical transaction column: {transaction_column}"
        )
    return f"""
        SELECT
            count(*) AS row_count,
            count(DISTINCT symbol) AS symbol_count,
            count(DISTINCT CAST(timestamp_utc AS DATE)) AS session_count,
            count(*) FILTER (WHERE symbol IS NULL OR trim(symbol)='') AS blank_symbol,
            count(*) FILTER (WHERE timestamp_utc IS NULL) AS null_timestamp,
            count(*) FILTER (
                WHERE NOT isfinite(open) OR NOT isfinite(high) OR NOT isfinite(low) OR NOT isfinite(close)
                   OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                   OR high < low OR open < low OR open > high OR close < low OR close > high
            ) AS invalid_ohlc,
            count(*) FILTER (WHERE NOT isfinite(volume) OR volume < 0) AS invalid_volume,
            count(*) FILTER (
                WHERE {transaction_column} IS NOT NULL AND {transaction_column} < 0
            ) AS invalid_transactions,
            count(*) FILTER (
                WHERE CAST(timestamp_utc AS DATE)
                   <> TRY_CAST(regexp_extract(filename, 'date=([0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})', 1) AS DATE)
            ) AS partition_date_mismatch
        FROM daily
    """


def _yearly_diagnostics_sql() -> str:
    """Return the yearly population-diagnostic query using non-reserved aliases."""

    return """
        SELECT
            year(CAST(timestamp_utc AS DATE)) AS calendar_year,
            count(*) AS row_count,
            count(DISTINCT symbol) AS symbol_count,
            count(DISTINCT CAST(timestamp_utc AS DATE)) AS session_count,
            median(volume) AS median_volume,
            quantile_cont(close, 0.5) AS median_close
        FROM daily
        GROUP BY 1
        ORDER BY 1
    """


class CumulativeFoundationIntegrityAuditor(CumulativeFoundationAuditor):
    """Cumulative auditor with explicit identity, coverage, and split-origin proofs."""

    def _audit_daily(self, end_date: date) -> dict[str, object]:
        """Exhaustively validate canonical daily structure using the accepted schema names."""

        files = [
            path
            for path in self._daily_files()
            if ALPACA_BACKFILL_START <= _partition_date(path) <= end_date
        ]
        actual_sessions = [_partition_date(path) for path in files]
        expected_sessions = get_market_calendar().sessions_in_range(ALPACA_BACKFILL_START, end_date)
        missing_sessions = sorted(set(expected_sessions).difference(actual_sessions))
        unexpected_sessions = sorted(set(actual_sessions).difference(expected_sessions))
        duplicate_partitions = len(actual_sessions) - len(set(actual_sessions))
        if not files:
            raise CumulativeFoundationAuditError("no canonical daily partitions in audit range")

        glob = (
            self.canonical_root
            / "stocks"
            / Timeframe.DAY_1.value
            / "year=*"
            / "date=*"
            / "part-000.parquet"
        ).as_posix()
        con = connect_utc(":memory:")
        try:
            con.execute(
                f"""
                CREATE TEMP VIEW daily AS
                SELECT *, filename
                FROM read_parquet({_sql(glob)}, union_by_name=true, filename=true)
                WHERE CAST(timestamp_utc AS DATE) BETWEEN DATE '{ALPACA_BACKFILL_START}' AND DATE '{end_date}'
                """
            )
            columns = {
                str(row[0]): str(row[1]).upper()
                for row in con.execute("DESCRIBE daily").fetchall()
            }
            if "transaction_count" not in columns:
                raise CumulativeFoundationAuditError(
                    "canonical daily schema is missing accepted transaction_count column"
                )
            row = con.execute(_daily_integrity_sql("transaction_count")).fetchone()
            duplicates = int(
                con.execute(
                    """
                    SELECT count(*) FROM (
                        SELECT symbol, timestamp_utc, count(*) AS duplicate_count
                        FROM daily
                        GROUP BY 1,2
                        HAVING count(*) > 1
                    )
                    """
                ).fetchone()[0]
            )
            yearly = con.execute(_yearly_diagnostics_sql()).fetchall()
        finally:
            con.close()

        stats = {
            "row_count": int(row[0]),
            "symbol_count": int(row[1]),
            "session_count": int(row[2]),
            "blank_symbol_rows": int(row[3]),
            "null_timestamp_rows": int(row[4]),
            "invalid_ohlc_rows": int(row[5]),
            "invalid_volume_rows": int(row[6]),
            "invalid_transaction_rows": int(row[7]),
            "partition_date_mismatch_rows": int(row[8]),
            "duplicate_market_keys": duplicates,
            "partition_count": len(files),
            "expected_session_count": len(expected_sessions),
            "missing_sessions": [item.isoformat() for item in missing_sessions],
            "unexpected_sessions": [item.isoformat() for item in unexpected_sessions],
            "duplicate_partition_dates": duplicate_partitions,
            "schema_columns": columns,
            "yearly_diagnostics": [
                {
                    "year": int(year),
                    "rows": int(rows),
                    "symbols": int(symbols),
                    "sessions": int(sessions),
                    "median_volume": None if median_volume is None else float(median_volume),
                    "median_close": None if median_close is None else float(median_close),
                }
                for year, rows, symbols, sessions, median_volume, median_close in yearly
            ],
        }
        stats["pass"] = all(
            (
                stats["blank_symbol_rows"] == 0,
                stats["null_timestamp_rows"] == 0,
                stats["invalid_ohlc_rows"] == 0,
                stats["invalid_volume_rows"] == 0,
                stats["invalid_transaction_rows"] == 0,
                stats["partition_date_mismatch_rows"] == 0,
                stats["duplicate_market_keys"] == 0,
                not missing_sessions,
                not unexpected_sessions,
                duplicate_partitions == 0,
            )
        )
        return stats

    def _audit_feature_manifests(
        self,
        end_date: date,
        progress: Callable[[str], None] | None,
    ) -> dict[str, object]:
        """Verify each source partition has exactly one current feature manifest.

        The base audit verifies every discovered manifest's contract, bound source hash,
        feature hash, and recursive state-chain fingerprint. This extension additionally
        proves date-set coverage so a silently missing indicator partition cannot pass
        merely because the remaining manifests are individually valid.
        """

        result = super()._audit_feature_manifests(end_date, progress)
        overall = bool(result.get("pass"))
        for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_1, Timeframe.HOUR_4):
            origin = ALPACA_BACKFILL_START if timeframe == Timeframe.DAY_1 else TICKER_HISTORY_ORIGIN_DATE
            if timeframe == Timeframe.DAY_1:
                source_files = self._daily_files()
            else:
                source_files = self._files_for(timeframe)
            source_dates = {
                _partition_date(path)
                for path in source_files
                if origin <= _partition_date(path) <= end_date
            }
            manifest_dir = self.manifest_root / "features" / timeframe.value
            manifest_dates = {
                date.fromisoformat(path.stem)
                for path in manifest_dir.glob("*/*.json")
                if origin <= date.fromisoformat(path.stem) <= end_date
            }
            missing_manifest_dates = sorted(source_dates - manifest_dates)
            orphan_manifest_dates = sorted(manifest_dates - source_dates)
            coverage_exact = (
                bool(source_dates)
                and source_dates == manifest_dates
                and end_date in source_dates
                and end_date in manifest_dates
            )
            item = dict(result.get(timeframe.value) or {})
            item.update(
                {
                    "source_partition_date_count": len(source_dates),
                    "manifest_partition_date_count": len(manifest_dates),
                    "source_manifest_date_coverage_exact": coverage_exact,
                    "missing_manifest_date_count": len(missing_manifest_dates),
                    "missing_manifest_dates": [d.isoformat() for d in missing_manifest_dates[:20]],
                    "orphan_manifest_date_count": len(orphan_manifest_dates),
                    "orphan_manifest_dates": [d.isoformat() for d in orphan_manifest_dates[:20]],
                    "latest_source_date": max(source_dates).isoformat() if source_dates else None,
                    "latest_manifest_date": max(manifest_dates).isoformat() if manifest_dates else None,
                }
            )
            item["pass"] = bool(item.get("pass")) and coverage_exact
            result[timeframe.value] = item
            overall = overall and bool(item["pass"])
            if progress is not None:
                progress(
                    f"feature coverage {timeframe.value}: sources {len(source_dates):,}; "
                    f"manifests {len(manifest_dates):,}; missing {len(missing_manifest_dates):,}; "
                    f"orphan {len(orphan_manifest_dates):,}"
                )
        result["pass"] = overall
        return result

    def _audit_regimes(self, end_date: date) -> dict[str, object]:
        manifest_path = self.paths.regime_state_manifest(end_date)
        manifest = _json(manifest_path, "latest split-origin regime manifest")
        snapshot_path = Path(str(manifest.get("snapshot_path", "")))
        snapshot = _json(snapshot_path, "latest split-origin regime snapshot")
        history_records = manifest.get("history_files")
        if not isinstance(history_records, dict):
            history_records = {}

        missing_history: list[str] = []
        history_hash_checks: dict[str, bool] = {}
        history_ranges: dict[str, object] = {}
        con = connect_utc(":memory:")
        try:
            for name in ("market_raw", "market_effective", "sector_raw", "sector_effective"):
                record = history_records.get(name)
                if not isinstance(record, dict):
                    missing_history.append(name)
                    continue
                path = Path(str(record.get("path", "")))
                if not path.is_file():
                    missing_history.append(name)
                    continue
                history_hash_checks[name] = sha256_file(path) == str(record.get("sha256", ""))
                columns = {
                    str(row[0])
                    for row in con.execute(f"DESCRIBE SELECT * FROM read_parquet({_sql(path)})").fetchall()
                }
                date_col = next(
                    (candidate for candidate in ("trading_date", "session_date", "as_of_date") if candidate in columns),
                    None,
                )
                if date_col is None:
                    missing_history.append(name + ":NO_DATE_COLUMN")
                    continue
                first, last, rows = con.execute(
                    f"SELECT min({date_col}), max({date_col}), count(*) FROM read_parquet({_sql(path)})"
                ).fetchone()
                history_ranges[name] = {
                    "first": str(first),
                    "last": str(last),
                    "rows": int(rows),
                }
        finally:
            con.close()

        manifest_checks = {
            "manifest_version": manifest.get("manifest_version") == MARKET_SECTOR_MANIFEST_VERSION,
            "snapshot_contract_version": manifest.get("snapshot_contract_version")
            == MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": manifest.get("state_policy_contract_version")
            == MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": manifest.get("split_origin_policy_version")
            == SPLIT_ORIGIN_POLICY_VERSION,
            "market_sector_origin": manifest.get("history_origin_date")
            == MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_origin": manifest.get("ticker_history_origin_date")
            == TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "snapshot_hash": snapshot_path.is_file()
            and sha256_file(snapshot_path) == str(manifest.get("snapshot_sha256", "")),
        }
        snapshot_checks = {
            "snapshot_contract_version": snapshot.get("snapshot_contract_version")
            == MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": snapshot.get("state_policy_contract_version")
            == MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": snapshot.get("split_origin_policy_version")
            == SPLIT_ORIGIN_POLICY_VERSION,
            "market_sector_origin": snapshot.get("history_origin_date")
            == MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_origin": snapshot.get("ticker_history_origin_date")
            == TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "intraday_policy": snapshot.get("intraday_policy") == INTRADAY_POLICY,
        }
        no_pre_origin = True
        ends_at_asof = True
        for item in history_ranges.values():
            first = date.fromisoformat(str(item["first"])[:10])
            last = date.fromisoformat(str(item["last"])[:10])
            no_pre_origin = no_pre_origin and first >= MARKET_SECTOR_HISTORY_ORIGIN_DATE
            ends_at_asof = ends_at_asof and last == end_date

        return {
            "manifest_path": str(manifest_path.resolve()),
            "manifest_sha256": sha256_file(manifest_path),
            "snapshot_path": str(snapshot_path.resolve()),
            "snapshot_sha256": sha256_file(snapshot_path) if snapshot_path.is_file() else None,
            "market_sector_origin": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_origin": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "split_origin_policy": SPLIT_ORIGIN_POLICY_VERSION,
            "intraday_policy": INTRADAY_POLICY,
            "manifest_checks": manifest_checks,
            "snapshot_checks": snapshot_checks,
            "history_hash_checks": history_hash_checks,
            "missing_history_files": missing_history,
            "history_ranges": history_ranges,
            "no_market_sector_history_before_2016_origin": no_pre_origin,
            "history_reaches_as_of": ends_at_asof,
            "manifest_contract_current": all(manifest_checks.values()),
            "snapshot_contract_current": all(snapshot_checks.values()),
            "split_origin_provenance_present": all(manifest_checks.values()) and all(snapshot_checks.values()),
            "pass": (
                not missing_history
                and all(manifest_checks.values())
                and all(snapshot_checks.values())
                and all(history_hash_checks.values())
                and no_pre_origin
                and ends_at_asof
            ),
        }

    def _audit_accepted_historical_evidence(self) -> dict[str, object]:
        base = self.derived_root / "historical_backfill" / "alpaca"
        identity_policy_path = base / "identity" / "identity_report.json"
        identity_segment_path = base / "identity" / "identity_segment_report.json"
        identity_segments_parquet = base / "identity" / "identity_segments.parquet"
        identity_policy = _json(identity_policy_path, "Gate 4 identity policy report")
        identity_segments = _json(identity_segment_path, "Gate 4 identity segment report")

        con = connect_utc(":memory:")
        try:
            duplicate_segment_ids, duplicate_symbols, rows = con.execute(
                f"""
                SELECT
                    count(*) - count(DISTINCT segment_id),
                    count(*) - count(DISTINCT symbol),
                    count(*)
                FROM read_parquet({_sql(identity_segments_parquet)})
                """
            ).fetchone()
            chain_errors = int(
                con.execute(
                    f"""
                    SELECT count(*) FROM (
                        SELECT
                            identity_chain_id,
                            count(*) AS segment_count,
                            min(chain_position) AS min_position,
                            max(chain_position) AS max_position,
                            max(chain_length) AS expected_chain_length,
                            count(DISTINCT chain_length) AS chain_length_versions
                        FROM read_parquet({_sql(identity_segments_parquet)})
                        GROUP BY identity_chain_id
                        HAVING min(chain_position) <> 0
                           OR max(chain_position) <> max(chain_length) - 1
                           OR count(*) <> max(chain_length)
                           OR count(DISTINCT chain_length) <> 1
                    )
                    """
                ).fetchone()[0]
            )
        finally:
            con.close()

        identity_checks = {
            "identity_policy_contract": identity_policy.get("contract_version")
            == ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION,
            "identity_policy_canonical_unchanged": identity_policy.get("canonical_data_modified") is False,
            "segment_contract": identity_segments.get("contract_version")
            == ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION,
            "segment_canonical_unchanged": identity_segments.get("canonical_data_modified") is False,
            "edge_component_accounting": identity_segments.get("edge_component_accounting") is True,
            "chain_coverage_exact": identity_segments.get("chain_coverage_exact") is True,
            "safe_edges_consumed_exact": identity_segments.get("safe_edges_consumed_exact") is True,
            "segment_rows_match_report": int(rows) == int(identity_segments.get("identity_segments", -1)),
            "segment_ids_unique": int(duplicate_segment_ids) == 0,
            "provider_native_symbols_unique_in_segments": int(duplicate_symbols) == 0,
            "chain_positions_structurally_exact": chain_errors == 0,
        }

        final_path = (
            base / "ml_long_history" / "v1" / "evaluation" / "v1" / "benchmark" / "v1"
            / "historical_extension_final_acceptance.json"
        )
        final = _json(final_path, "historical extension final acceptance")
        disposition = dict(final.get("final_disposition") or {})
        final_checks = dict(final.get("checks") or {})
        closeout_checks = {
            "closeout_contract": final.get("contract_version")
            == HISTORICAL_BACKFILL_CLOSEOUT_CONTRACT_VERSION,
            "closeout_pass": final.get("pass") is True,
            "phase10_model_authority_preserved": disposition.get(
                "accepted_phase10_production_model_remains_authoritative"
            )
            is True,
            "historical_challenger_not_production": disposition.get(
                "historical_C_challenger_is_production"
            )
            is False,
            "final_holdout_not_accessed": final_checks.get("final_holdout_not_accessed") is True,
            "production_registry_unchanged": final_checks.get("production_registry_unchanged") is True,
            "production_ml_writes_zero": int(final.get("production_ml_writes", -1)) == 0,
            "broker_writes_zero": int(final.get("broker_writes", -1)) == 0,
        }
        return {
            "identity_policy_path": str(identity_policy_path.resolve()),
            "identity_policy_sha256": sha256_file(identity_policy_path),
            "identity_segment_report_path": str(identity_segment_path.resolve()),
            "identity_segment_report_sha256": sha256_file(identity_segment_path),
            "identity_segments_path": str(identity_segments_parquet.resolve()),
            "identity_segments_sha256": sha256_file(identity_segments_parquet),
            "identity_rows": int(rows),
            "identity_checks": identity_checks,
            "historical_extension_acceptance_path": str(final_path.resolve()),
            "historical_extension_acceptance_sha256": sha256_file(final_path),
            "closeout_checks": closeout_checks,
            "accepted": final.get("pass") is True,
            "phase10_authority_reference_present": closeout_checks[
                "phase10_model_authority_preserved"
            ],
            "pass": all(identity_checks.values()) and all(closeout_checks.values()),
        }
