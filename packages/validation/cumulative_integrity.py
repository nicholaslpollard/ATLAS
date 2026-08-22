from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from packages.data.alpaca_backfill_identity_policy import ALPACA_BACKFILL_IDENTITY_POLICY_CONTRACT_VERSION
from packages.data.alpaca_backfill_identity_segments import ALPACA_BACKFILL_IDENTITY_SEGMENT_CONTRACT_VERSION
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

from .cumulative_foundation import CumulativeFoundationAuditor, _json, _sql


class CumulativeFoundationIntegrityAuditor(CumulativeFoundationAuditor):
    """Cumulative auditor with explicit accepted identity and split-origin proofs."""

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
                        SELECT identity_chain_id,
                               count(*) n,
                               min(chain_position) min_pos,
                               max(chain_position) max_pos,
                               max(chain_length) chain_length,
                               count(DISTINCT chain_length) chain_length_versions
                        FROM read_parquet({_sql(identity_segments_parquet)})
                        GROUP BY identity_chain_id
                        HAVING min_pos <> 0 OR max_pos <> chain_length - 1
                           OR n <> chain_length OR chain_length_versions <> 1
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
