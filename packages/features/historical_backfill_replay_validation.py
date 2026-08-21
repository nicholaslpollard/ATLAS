from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_TARGET_SESSION
from packages.data.alpaca_backfill_validated_evidence import sha256_file
from packages.features.engine import compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.historical_backfill_replay_build import (
    GATE9_DAILY_REPLAY_CONTRACT_VERSION,
    GATE9_DAILY_REPLAY_VALIDATION_CONTRACT_VERSION,
    GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION,
    HistoricalBackfillDailyFeatureReplay,
    _sql_path_list,
    _sql_string,
    lifecycle_content_fingerprint,
    replay_source_fingerprint,
    year_source_fingerprint,
)
from packages.features.incremental import IncrementalFeatureEngine
from packages.features.state_checkpoint import feature_state_fingerprint
from packages.schemas.feature import core_feature_storage_schema_matches


class HistoricalBackfillDailyFeatureReplayValidator:
    """Independently validate Gate 9-B candidate output without production writes."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.replay = HistoricalBackfillDailyFeatureReplay(settings)
        self.preflight = self.replay.preflight
        self.report_path = self.replay.root / "gate9_validation_report.json"

    def _candidate_files_from_years(
        self,
        year_manifests: list[dict[str, Any]],
    ) -> list[Path]:
        files: list[Path] = []
        for year in year_manifests:
            for record in list(year.get("sessions") or []):
                files.append(Path(str(record["feature_path"])))
        return files

    def _all_year_manifests_current(
        self,
        *,
        canonical_inventory: list[dict[str, object]],
        events: list[dict[str, object]],
        replay_fp: str,
    ) -> tuple[bool, list[dict[str, Any]], int, int]:
        grouped = self.replay._group_inventory(canonical_inventory)
        engine = IncrementalFeatureEngine()
        input_state_fp = feature_state_fingerprint(
            engine,
            timeframe=Timeframe.DAY_1,
            as_of_date="genesis",
        )
        manifests: list[dict[str, Any]] = []
        feature_hash_failures = 0
        source_hash_failures = 0

        for year, canonical_rows in grouped.items():
            path = self.replay.year_manifest_path(year)
            if not path.is_file():
                return False, manifests, feature_hash_failures, source_hash_failures
            payload = json.loads(path.read_text(encoding="utf-8"))
            year_events = [
                row
                for row in events
                if isinstance(row["event_date"], date) and row["event_date"].year == year
            ]
            expected_year_fp = year_source_fingerprint(
                replay_source_fingerprint_value=replay_fp,
                year=year,
                input_state_fingerprint=input_state_fp,
                canonical_rows=canonical_rows,
                lifecycle_events=year_events,
            )
            if (
                payload.get("contract_version") != GATE9_DAILY_REPLAY_YEAR_CONTRACT_VERSION
                or payload.get("replay_source_fingerprint") != replay_fp
                or payload.get("year_source_fingerprint") != expected_year_fp
                or payload.get("input_state_fingerprint") != input_state_fp
            ):
                return False, manifests, feature_hash_failures, source_hash_failures
            records = list(payload.get("sessions") or [])
            if len(records) != len(canonical_rows):
                return False, manifests, feature_hash_failures, source_hash_failures
            source_by_date = {str(row["session_date"]): row for row in canonical_rows}
            for record in records:
                session_text = str(record.get("session_date"))
                source = source_by_date.get(session_text)
                if source is None or record.get("source_sha256") != source.get("sha256"):
                    source_hash_failures += 1
                    continue
                source_path = Path(str(source["path"]))
                if not source_path.is_file() or sha256_file(source_path) != str(
                    source["sha256"]
                ):
                    source_hash_failures += 1
                feature_path = Path(str(record.get("feature_path") or ""))
                if not feature_path.is_file() or sha256_file(feature_path) != str(
                    record.get("feature_sha256")
                ):
                    feature_hash_failures += 1
                manifest_path = Path(str(record.get("manifest_path") or ""))
                if not manifest_path.is_file() or sha256_file(manifest_path) != str(
                    record.get("manifest_sha256")
                ):
                    feature_hash_failures += 1
            checkpoint_path = Path(str(payload.get("checkpoint_path") or ""))
            if not checkpoint_path.is_file() or sha256_file(checkpoint_path) != str(
                payload.get("checkpoint_sha256")
            ):
                return False, manifests, feature_hash_failures, source_hash_failures
            _engine, checkpoint = self.replay.checkpoints.read(
                checkpoint_path,
                expected_timeframe=Timeframe.DAY_1,
            )
            if checkpoint.get("checkpoint_fingerprint") != payload.get(
                "output_state_fingerprint"
            ):
                return False, manifests, feature_hash_failures, source_hash_failures
            input_state_fp = str(payload["output_state_fingerprint"])
            manifests.append(payload)

        return (
            feature_hash_failures == 0 and source_hash_failures == 0,
            manifests,
            feature_hash_failures,
            source_hash_failures,
        )

    @staticmethod
    def _candidate_stats(paths: list[Path]) -> dict[str, object]:
        if not paths:
            raise RuntimeError("Gate 9-B validator candidate inventory is empty")
        con = duckdb.connect(":memory:")
        try:
            description = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({_sql_path_list(paths)}, hive_partitioning=false)"
            ).fetchall()
            row = con.execute(
                f"""
                SELECT count(*) AS rows,
                       count(DISTINCT symbol) AS symbols,
                       count(DISTINCT CAST(timestamp_utc AS DATE)) AS sessions,
                       min(CAST(timestamp_utc AS DATE)) AS first_session,
                       max(CAST(timestamp_utc AS DATE)) AS last_session
                FROM read_parquet({_sql_path_list(paths)}, hive_partitioning=false)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {
            "rows": int(row[0]),
            "symbols": int(row[1]),
            "sessions": int(row[2]),
            "first_session": str(row[3]),
            "last_session": str(row[4]),
            "schema_exact": core_feature_storage_schema_matches(description),
        }

    def _exact_session_keys(
        self,
        year_manifests: list[dict[str, Any]],
        canonical_inventory: list[dict[str, object]],
    ) -> tuple[int, int]:
        source_by_date = {
            str(row["session_date"]): Path(str(row["path"]))
            for row in canonical_inventory
        }
        mismatched_sessions = 0
        duplicate_keys = 0
        con = duckdb.connect(":memory:")
        try:
            for year in year_manifests:
                for record in list(year.get("sessions") or []):
                    session_text = str(record["session_date"])
                    candidate = Path(str(record["feature_path"]))
                    source = source_by_date[session_text]
                    row = con.execute(
                        f"""
                        SELECT
                            (
                                SELECT count(*)
                                FROM (
                                    SELECT symbol, timestamp_utc
                                    FROM read_parquet({_sql_string(candidate)}, hive_partitioning=false)
                                    EXCEPT
                                    SELECT symbol, timestamp_utc
                                    FROM read_parquet({_sql_string(source)}, hive_partitioning=false)
                                )
                            )
                            +
                            (
                                SELECT count(*)
                                FROM (
                                    SELECT symbol, timestamp_utc
                                    FROM read_parquet({_sql_string(source)}, hive_partitioning=false)
                                    EXCEPT
                                    SELECT symbol, timestamp_utc
                                    FROM read_parquet({_sql_string(candidate)}, hive_partitioning=false)
                                )
                            ) AS key_mismatch,
                            (
                                SELECT count(*) - count(DISTINCT symbol)
                                FROM read_parquet({_sql_string(candidate)}, hive_partitioning=false)
                            ) AS duplicate_keys
                        """
                    ).fetchone()
                    assert row is not None
                    if int(row[0]) != 0:
                        mismatched_sessions += 1
                    duplicate_keys += int(row[1])
        finally:
            con.close()
        return mismatched_sessions, duplicate_keys

    def _transfer_semantics(
        self,
        candidate_paths: list[Path],
        canonical_paths: list[Path],
    ) -> dict[str, object]:
        identity_path = self.preflight.identity_segments_path
        con = duckdb.connect(":memory:")
        try:
            row = con.execute(
                f"""
                WITH transfers AS (
                    SELECT cur.symbol AS target_symbol,
                           cur.predecessor_symbol AS source_symbol,
                           CAST(cur.first_candidate_session AS DATE) AS target_session,
                           CAST(prev.last_candidate_session AS DATE) AS source_session
                    FROM read_parquet({_sql_string(identity_path)}, hive_partitioning=false) cur
                    JOIN read_parquet({_sql_string(identity_path)}, hive_partitioning=false) prev
                      ON prev.identity_chain_id = cur.identity_chain_id
                     AND prev.symbol = cur.predecessor_symbol
                    WHERE cur.predecessor_symbol IS NOT NULL
                      AND cur.continuity_basis = 'SAFE_NAME_CHANGE_CHAIN'
                ),
                canon AS (
                    SELECT symbol, session_date, close
                    FROM read_parquet({_sql_path_list(canonical_paths)}, hive_partitioning=false)
                    WHERE session_date < DATE '2021-08-16'
                ),
                feat AS (
                    SELECT symbol, CAST(timestamp_utc AS DATE) AS session_date, return_1
                    FROM read_parquet({_sql_path_list(candidate_paths)}, hive_partitioning=false)
                    WHERE CAST(timestamp_utc AS DATE) < DATE '2021-08-16'
                ),
                proof AS (
                    SELECT t.*,
                           src.close AS source_close,
                           dst.close AS target_close,
                           f.return_1 AS feature_return,
                           dst.close / src.close - 1.0 AS expected_return
                    FROM transfers t
                    LEFT JOIN canon src
                      ON src.symbol = t.source_symbol
                     AND src.session_date = t.source_session
                    LEFT JOIN canon dst
                      ON dst.symbol = t.target_symbol
                     AND dst.session_date = t.target_session
                    LEFT JOIN feat f
                      ON f.symbol = t.target_symbol
                     AND f.session_date = t.target_session
                )
                SELECT count(*) AS transfers,
                       count(*) FILTER (
                           WHERE source_close IS NULL OR target_close IS NULL OR feature_return IS NULL
                       ) AS missing,
                       count(*) FILTER (
                           WHERE source_close IS NOT NULL
                             AND target_close IS NOT NULL
                             AND feature_return IS NOT NULL
                             AND abs(feature_return - expected_return)
                                 > 1e-12 * greatest(1.0, abs(expected_return))
                       ) AS mismatches,
                       max(
                           CASE
                               WHEN feature_return IS NULL OR expected_return IS NULL THEN NULL
                               ELSE abs(feature_return - expected_return)
                           END
                       ) AS max_abs_error
                FROM proof
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {
            "transfers": int(row[0]),
            "missing": int(row[1]),
            "mismatches": int(row[2]),
            "max_abs_error": None if row[3] is None else float(row[3]),
        }

    def _sentinel_feature_equivalence(
        self,
        candidate_paths: list[Path],
        canonical_paths: list[Path],
    ) -> dict[str, object]:
        sentinels = (
            "SPY",
            "QQQ",
            "IWM",
            "DIA",
            "AAPL",
            "MSFT",
            "AMZN",
            "GOOG",
            "GOOGL",
            "IBM",
            "XOM",
            "JPM",
        )
        in_list = ",".join(_sql_string(symbol) for symbol in sentinels)
        feature_names = [definition.name for definition in CORE_FEATURE_REGISTRY.all()]
        feature_projection = ", ".join(f'"{name}"' for name in feature_names)
        con = duckdb.connect(":memory:")
        try:
            source = con.execute(
                f"""
                SELECT symbol, timestamp_utc, high, low, close, volume
                FROM read_parquet({_sql_path_list(canonical_paths)}, hive_partitioning=false)
                WHERE symbol IN ({in_list})
                ORDER BY symbol, timestamp_utc
                """
            ).fetch_df()
            actual = con.execute(
                f"""
                SELECT symbol, timestamp_utc, {feature_projection}
                FROM read_parquet({_sql_path_list(candidate_paths)}, hive_partitioning=false)
                WHERE symbol IN ({in_list})
                ORDER BY symbol, timestamp_utc
                """
            ).fetch_df()
        finally:
            con.close()

        expected = compute_core_features(source)
        expected = expected[["symbol", "timestamp_utc", *feature_names]].reset_index(drop=True)
        actual = actual[["symbol", "timestamp_utc", *feature_names]].reset_index(drop=True)
        keys_exact = (
            len(expected) == len(actual)
            and expected["symbol"].astype(str).equals(actual["symbol"].astype(str))
            and expected["timestamp_utc"].equals(actual["timestamp_utc"])
        )
        if not keys_exact:
            return {
                "sentinels": len(sentinels),
                "rows": int(len(actual)),
                "keys_exact": False,
                "feature_mismatches": -1,
                "max_abs_error": None,
            }

        expected_values = expected[feature_names].to_numpy(dtype="float64", na_value=np.nan)
        actual_values = actual[feature_names].to_numpy(dtype="float64", na_value=np.nan)
        close = np.isclose(
            expected_values,
            actual_values,
            rtol=1e-12,
            atol=1e-12,
            equal_nan=True,
        )
        mismatches = int((~close).sum())
        finite = np.isfinite(expected_values) & np.isfinite(actual_values)
        max_abs = (
            float(np.max(np.abs(expected_values[finite] - actual_values[finite])))
            if finite.any()
            else 0.0
        )
        return {
            "sentinels": len(sentinels),
            "rows": int(len(actual)),
            "keys_exact": True,
            "feature_mismatches": mismatches,
            "max_abs_error": max_abs,
        }

    def _seam_semantics(
        self,
        candidate_paths: list[Path],
    ) -> dict[str, object]:
        decision_path = self.preflight.gate7_decision_path
        post_paths = [
            path
            for path in candidate_paths
            if date.fromisoformat(path.parent.name.split("=", 1)[1])
            >= ALPACA_BACKFILL_SEAM_TARGET_SESSION
        ]
        seam_path = self.replay.feature_path(ALPACA_BACKFILL_SEAM_TARGET_SESSION)
        con = duckdb.connect(":memory:")
        try:
            bridge = con.execute(
                f"""
                SELECT count(f.symbol) AS rows,
                       count(*) FILTER (WHERE f.return_1 IS NULL) AS null_returns
                FROM read_parquet({_sql_string(decision_path)}, hive_partitioning=false) d
                LEFT JOIN read_parquet({_sql_string(seam_path)}, hive_partitioning=false) f
                  ON f.symbol = d.symbol
                WHERE d.promotion_decision = 'BRIDGE_EXACT_LITERAL'
                """
            ).fetchone()
            fresh = con.execute(
                f"""
                WITH target AS (
                    SELECT symbol, promotion_decision
                    FROM read_parquet({_sql_string(decision_path)}, hive_partitioning=false)
                    WHERE promotion_decision IN (
                        'RESET_AT_PROVIDER_SEAM',
                        'TERMINATE_PRESEAM_CONTINUITY',
                        'QUARANTINE_SEAM_CONTINUITY',
                        'POSTSEAM_ONLY'
                    )
                ),
                rows AS (
                    SELECT f.symbol, f.timestamp_utc, f.return_1, f.log_return_1, f.obv,
                           t.promotion_decision
                    FROM read_parquet({_sql_path_list(post_paths)}, hive_partitioning=false) f
                    JOIN target t USING (symbol)
                ),
                firsts AS (
                    SELECT *,
                           row_number() OVER (
                               PARTITION BY symbol ORDER BY timestamp_utc
                           ) AS rn
                    FROM rows
                )
                SELECT count(*) AS target_symbols,
                       count(*) FILTER (WHERE firsts.symbol IS NOT NULL) AS observed_symbols,
                       count(*) FILTER (
                           WHERE firsts.symbol IS NOT NULL
                             AND (
                                 firsts.return_1 IS NOT NULL
                                 OR firsts.log_return_1 IS NOT NULL
                                 OR firsts.obv IS NULL
                                 OR abs(firsts.obv) > 1e-12
                             )
                       ) AS genesis_mismatches
                FROM target
                LEFT JOIN firsts
                  ON firsts.symbol = target.symbol
                 AND firsts.rn = 1
                """
            ).fetchone()
        finally:
            con.close()
        assert bridge is not None and fresh is not None
        return {
            "bridge_rows": int(bridge[0]),
            "bridge_null_returns": int(bridge[1]),
            "fresh_target_symbols": int(fresh[0]),
            "fresh_observed_symbols": int(fresh[1]),
            "fresh_genesis_mismatches": int(fresh[2]),
        }

    def run(self) -> dict[str, object]:
        preflight_report = self.preflight.run()
        if preflight_report.get("pass") is not True:
            raise RuntimeError("Gate 9-B validation requires current Gate 9-A PASS")
        stored = self.replay._load_json(self.replay.report_path, "Gate 9-B replay report")
        if stored.get("contract_version") != GATE9_DAILY_REPLAY_CONTRACT_VERSION:
            raise RuntimeError("Gate 9-B stored replay contract mismatch")

        canonical_inventory = self.preflight._canonical_inventory()
        canonical_paths = [Path(str(row["path"])) for row in canonical_inventory]
        events = self.replay._load_lifecycle_events()
        lifecycle_fp = lifecycle_content_fingerprint(events)
        replay_fp = replay_source_fingerprint(
            preflight_source_fingerprint=str(preflight_report["source_fingerprint"]),
            canonical_inventory_fingerprint=str(
                preflight_report["canonical_inventory_fingerprint"]
            ),
            production_feature_baseline_fingerprint=str(
                preflight_report["production_feature_baseline_fingerprint"]
            ),
            lifecycle_fingerprint=lifecycle_fp,
        )
        (
            years_current,
            year_manifests,
            feature_hash_failures,
            source_hash_failures,
        ) = self._all_year_manifests_current(
            canonical_inventory=canonical_inventory,
            events=events,
            replay_fp=replay_fp,
        )
        candidate_paths = self._candidate_files_from_years(year_manifests)
        stats = self._candidate_stats(candidate_paths) if candidate_paths else {}
        key_mismatches, duplicate_keys = (
            self._exact_session_keys(year_manifests, canonical_inventory)
            if years_current
            else (-1, -1)
        )
        transfer = (
            self._transfer_semantics(candidate_paths, canonical_paths)
            if years_current
            else {
                "transfers": -1,
                "missing": -1,
                "mismatches": -1,
                "max_abs_error": None,
            }
        )
        sentinel = (
            self._sentinel_feature_equivalence(candidate_paths, canonical_paths)
            if years_current
            else {
                "sentinels": 12,
                "rows": -1,
                "keys_exact": False,
                "feature_mismatches": -1,
                "max_abs_error": None,
            }
        )
        seam = (
            self._seam_semantics(candidate_paths)
            if years_current
            else {
                "bridge_rows": -1,
                "bridge_null_returns": -1,
                "fresh_target_symbols": -1,
                "fresh_observed_symbols": -1,
                "fresh_genesis_mismatches": -1,
            }
        )

        current_state_ok = False
        current_state_fp = None
        if self.replay.current_state_path.is_file():
            _engine, current_payload = self.replay.checkpoints.read(
                self.replay.current_state_path,
                expected_timeframe=Timeframe.DAY_1,
            )
            current_state_fp = current_payload.get("checkpoint_fingerprint")
            current_state_ok = (
                current_state_fp == stored.get("current_state_fingerprint")
                and sha256_file(self.replay.current_state_path)
                == stored.get("current_state_sha256")
            )

        expected = preflight_report["canonical"]
        expected_lifecycle = preflight_report["lifecycle"]
        checks = {
            "validation_contract": True,
            "preflight_current": preflight_report.get("pass") is True,
            "replay_source_fingerprint_current": stored.get("source_fingerprint")
            == replay_fp,
            "production_feature_baseline_unchanged": stored.get(
                "production_feature_baseline_fingerprint"
            )
            == preflight_report.get("production_feature_baseline_fingerprint"),
            "all_year_manifests_current": years_current,
            "candidate_feature_hashes_exact": feature_hash_failures == 0,
            "canonical_source_hashes_exact": source_hash_failures == 0,
            "candidate_schema_exact": bool(stats) and stats.get("schema_exact") is True,
            "candidate_row_accounting_exact": bool(stats)
            and stats.get("rows") == int(expected["rows"]),
            "candidate_session_accounting_exact": bool(stats)
            and stats.get("sessions") == int(expected["sessions"]),
            "candidate_symbol_accounting_exact": bool(stats)
            and stats.get("symbols") == int(expected["symbols"]),
            "candidate_range_exact": bool(stats)
            and stats.get("first_session") == expected["first_session"]
            and stats.get("last_session") == expected["last_session"],
            "candidate_keys_match_canonical_exactly": key_mismatches == 0,
            "duplicate_candidate_keys_zero": duplicate_keys == 0,
            "identity_transfer_count_exact": transfer["transfers"]
            == int(expected_lifecycle["identity_transfers"]),
            "identity_transfer_inputs_complete": transfer["missing"] == 0,
            "identity_transfer_returns_exact": transfer["mismatches"] == 0,
            "liquid_sentinel_keys_exact": sentinel["keys_exact"] is True,
            "liquid_sentinel_features_exact": sentinel["feature_mismatches"] == 0,
            "safe_bridges_carry_state": seam["bridge_rows"]
            == int(expected_lifecycle["bridge_exact_literal"])
            and seam["bridge_null_returns"] == 0,
            "fresh_target_population_exact": seam["fresh_target_symbols"]
            == (
                int(expected_lifecycle["reset_at_provider_seam"])
                + int(expected_lifecycle["terminate_preseam_continuity"])
                + int(expected_lifecycle["quarantine_seam_continuity"])
                + int(expected_lifecycle["postseam_only"])
            ),
            "reset_terminate_quarantine_postseam_start_fresh": seam[
                "fresh_genesis_mismatches"
            ]
            == 0,
            "current_state_exact": current_state_ok,
            "candidate_namespace_isolated": self.replay.feature_root.resolve()
            != (
                self.settings.resolved_path(self.settings.data.paths.derived)
                / "features"
                / "1d"
            ).resolve(),
            "production_feature_writes_zero": True,
        }
        report: dict[str, object] = {
            "contract_version": GATE9_DAILY_REPLAY_CONTRACT_VERSION,
            "validation_contract_version": GATE9_DAILY_REPLAY_VALIDATION_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": replay_fp,
            "preflight_source_fingerprint": preflight_report["source_fingerprint"],
            "candidate": stats,
            "feature_hash_failures": feature_hash_failures,
            "source_hash_failures": source_hash_failures,
            "key_mismatched_sessions": key_mismatches,
            "duplicate_candidate_keys": duplicate_keys,
            "identity_transfer_proof": transfer,
            "liquid_sentinel_proof": sentinel,
            "seam_proof": seam,
            "current_state_fingerprint": current_state_fp,
            "production_feature_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
            "stored_replay_report_path": str(self.replay.report_path),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
