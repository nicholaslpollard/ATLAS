from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_canonical_promotion import inventory_fingerprint
from packages.data.alpaca_backfill_canonical_promotion_validation import (
    AlpacaBackfillCanonicalPromotionValidator,
)
from packages.data.alpaca_backfill_identity_segments_policy import (
    ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
)
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_seam import ALPACA_BACKFILL_SEAM_TARGET_SESSION
from packages.data.alpaca_backfill_seam_final import (
    ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION,
    BRIDGE_EXACT_LITERAL,
    POSTSEAM_ONLY,
    QUARANTINE_SEAM_CONTINUITY,
    RESET_AT_PROVIDER_SEAM,
    TERMINATE_PRESEAM_CONTINUITY,
)
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.data.paths import MarketDataPaths
from packages.features.feature_registry import (
    CORE_FEATURE_CONTRACT_VERSION,
    CORE_FEATURE_REGISTRY,
)
from packages.features.partition_store import FeaturePartitionManifest
from packages.schemas.canonical_market import canonical_stock_daily_schema_matches


GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION = (
    "historical-backfill-feature-replay-preflight-v2-daily-identity-lifecycle-fresh-postseam"
)
GATE9_FEATURE_REPLAY_ROLE = "ISOLATED_DAILY_FEATURE_REPLAY_NOT_PRODUCTION"
TRANSFER_IDENTITY_STATE = "TRANSFER_IDENTITY_STATE"
DROP_AT_PROVIDER_SEAM = "DROP_AT_PROVIDER_SEAM"
SAFE_NAME_CHANGE_CHAIN = "SAFE_NAME_CHANGE_CHAIN"


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def _sql_path_list(paths: list[Path]) -> str:
    return "[" + ",".join(_sql_string(path) for path in paths) + "]"


def seam_requires_state_drop(decision: str) -> bool:
    return decision in {
        RESET_AT_PROVIDER_SEAM,
        TERMINATE_PRESEAM_CONTINUITY,
        QUARANTINE_SEAM_CONTINUITY,
        POSTSEAM_ONLY,
    }


def lifecycle_source_fingerprint(
    *,
    gate8_fingerprint: str,
    gate7_fingerprint: str,
    gate7_decision_sha256: str,
    identity_segments_sha256: str,
    canonical_inventory_fingerprint: str,
    production_feature_baseline_fingerprint: str,
) -> str:
    return stable_source_fingerprint(
        {
            "contract_version": GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION,
            "role": GATE9_FEATURE_REPLAY_ROLE,
            "gate8_fingerprint": gate8_fingerprint,
            "gate7_fingerprint": gate7_fingerprint,
            "gate7_decision_sha256": gate7_decision_sha256,
            "identity_segments_sha256": identity_segments_sha256,
            "canonical_inventory_fingerprint": canonical_inventory_fingerprint,
            "production_feature_baseline_fingerprint": production_feature_baseline_fingerprint,
            "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "timeframe": Timeframe.DAY_1.value,
            "history_start": ALPACA_BACKFILL_START.isoformat(),
            "provider_seam": ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat(),
        }
    )


def _artifact_inventory_fingerprint(rows: list[dict[str, object]]) -> str:
    normalized = [
        {
            "relative_path": str(item["relative_path"]).replace("\\", "/"),
            "sha256": str(item["sha256"]),
        }
        for item in rows
    ]
    normalized.sort(key=lambda item: item["relative_path"])
    return stable_source_fingerprint({"files": normalized})


class HistoricalBackfillFeatureReplayPreflight:
    """Gate 9-A read-only preflight for an isolated canonical 1d feature replay."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
        self.gate8_validator = AlpacaBackfillCanonicalPromotionValidator(settings)
        self.promotion = self.gate8_validator.promotion

        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "historical_backfill" / "alpaca" / "feature_replay" / "v1"
        self.lifecycle_path = self.root / "preflight" / "feature_lifecycle_events.parquet"
        self.report_path = self.root / "preflight" / "gate9_preflight_report.json"
        self.candidate_feature_root = self.root / "candidate" / "features" / "1d"
        self.candidate_manifest_root = self.root / "candidate" / "manifests" / "1d"
        self.candidate_state_root = self.root / "candidate" / "state" / "1d"

        self.identity_segments_path = self.promotion.candidate_builder.identity_segment_output_path
        self.identity_segment_report_path = (
            self.promotion.candidate_builder.identity_source_root / "identity_segment_report.json"
        )
        self.gate7_report_path = self.promotion.gate7_report_path
        self.gate7_decision_path = self.promotion.gate7_decision_path
        self.gate8_preflight_path = self.promotion.preflight_report_path

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 9-A requires {label}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _canonical_inventory(self) -> list[dict[str, object]]:
        root = self.settings.resolved_path(self.settings.data.paths.canonical)
        paths = sorted((root / "stocks" / "1d").glob("year=*/date=*/part-000.parquet"))
        rows: list[dict[str, object]] = []
        for path in paths:
            date_dir = path.parent.name
            if not date_dir.startswith("date="):
                raise RuntimeError(f"Gate 9-A canonical path lacks date partition: {path}")
            session = date.fromisoformat(date_dir.split("=", 1)[1])
            rows.append(
                {
                    "session_date": session.isoformat(),
                    "relative_path": path.relative_to(root).as_posix(),
                    "path": str(path),
                    "sha256": sha256_file(path),
                }
            )
        return rows

    @staticmethod
    def _canonical_stats(paths: list[Path]) -> dict[str, object]:
        if not paths:
            raise RuntimeError("Gate 9-A canonical daily inventory is empty")
        con = duckdb.connect(":memory:")
        try:
            description = con.execute(
                f"DESCRIBE SELECT * FROM read_parquet({_sql_path_list(paths)}, "
                "hive_partitioning=false)"
            ).fetchall()
            row = con.execute(
                f"""
                SELECT count(*) AS rows,
                       count(DISTINCT session_date) AS sessions,
                       count(DISTINCT symbol) AS symbols,
                       count(*) FILTER (WHERE provider = 'alpaca') AS alpaca_rows,
                       count(*) FILTER (WHERE provider = 'massive') AS massive_rows,
                       count(*) FILTER (WHERE provider NOT IN ('alpaca', 'massive')) AS other_rows,
                       min(session_date) AS first_session,
                       max(session_date) AS last_session
                FROM read_parquet({_sql_path_list(paths)}, hive_partitioning=false)
                """
            ).fetchone()
        finally:
            con.close()
        assert row is not None
        return {
            "rows": int(row[0]),
            "sessions": int(row[1]),
            "symbols": int(row[2]),
            "alpaca_rows": int(row[3]),
            "massive_rows": int(row[4]),
            "other_rows": int(row[5]),
            "first_session": str(row[6]),
            "last_session": str(row[7]),
            "schema_exact": canonical_stock_daily_schema_matches(description),
        }

    def _production_feature_baseline(self) -> tuple[list[dict[str, object]], dict[str, object]]:
        feature_root = self.settings.resolved_path(self.settings.data.paths.derived) / "features" / "1d"
        paths = sorted(feature_root.glob("year=*/month=*/date=*/part-000.parquet"))
        rows: list[dict[str, object]] = []
        manifest_failures = 0
        hash_failures = 0
        source_hash_failures = 0
        total_rows = 0
        sessions: list[date] = []

        for path in paths:
            date_dir = path.parent.name
            if not date_dir.startswith("date="):
                manifest_failures += 1
                continue
            session = date.fromisoformat(date_dir.split("=", 1)[1])
            sessions.append(session)
            manifest_path = self.paths.feature_manifest_file(Timeframe.DAY_1, session)
            if not manifest_path.is_file():
                manifest_failures += 1
                continue
            try:
                manifest = FeaturePartitionManifest.from_dict(
                    json.loads(manifest_path.read_text(encoding="utf-8"))
                )
                manifest.validate_contract(Timeframe.DAY_1, session)
            except Exception:
                manifest_failures += 1
                continue
            feature_sha = sha256_file(path)
            if feature_sha != manifest.feature_sha256:
                hash_failures += 1
            source_path = self.paths.canonical_file(Timeframe.DAY_1, session)
            if not source_path.is_file() or sha256_file(source_path) != manifest.source_sha256:
                source_hash_failures += 1
            total_rows += int(manifest.row_count)
            rows.append(
                {
                    "relative_path": path.relative_to(
                        self.settings.resolved_path(self.settings.data.paths.derived)
                    ).as_posix(),
                    "sha256": feature_sha,
                    "session_date": session.isoformat(),
                    "manifest_path": str(manifest_path),
                    "manifest_sha256": sha256_file(manifest_path),
                    "row_count": int(manifest.row_count),
                }
            )

        current_state = self.paths.feature_current_state_file(Timeframe.DAY_1)
        monthly_root = current_state.parent / "monthly"
        state_paths = ([current_state] if current_state.is_file() else []) + sorted(
            monthly_root.glob("*/*.json.gz") if monthly_root.exists() else []
        )
        state_inventory = [
            {
                "relative_path": path.relative_to(
                    self.settings.resolved_path(self.settings.data.paths.derived)
                ).as_posix(),
                "sha256": sha256_file(path),
            }
            for path in state_paths
        ]
        baseline_fp = stable_source_fingerprint(
            {
                "features": [
                    {
                        "relative_path": row["relative_path"],
                        "sha256": row["sha256"],
                        "manifest_sha256": row["manifest_sha256"],
                        "row_count": row["row_count"],
                    }
                    for row in rows
                ],
                "states": state_inventory,
            }
        )
        stats = {
            "sessions": len(rows),
            "rows": total_rows,
            "first_session": min(sessions).isoformat() if sessions else None,
            "last_session": max(sessions).isoformat() if sessions else None,
            "manifest_failures": manifest_failures,
            "feature_hash_failures": hash_failures,
            "source_hash_failures": source_hash_failures,
            "state_files": len(state_inventory),
            "current_state_present": current_state.is_file(),
            "fingerprint": baseline_fp,
        }
        return rows, stats

    def _lifecycle_events(self) -> tuple[list[dict[str, object]], dict[str, int]]:
        if not self.identity_segments_path.is_file():
            raise RuntimeError("Gate 9-A requires Gate 6 identity segment sidecar")
        if not self.gate7_decision_path.is_file():
            raise RuntimeError("Gate 9-A requires Gate 7 seam decision map")

        con = duckdb.connect(":memory:")
        try:
            transfer_cursor = con.execute(
                f"""
                SELECT CAST(first_candidate_session AS DATE) AS event_date,
                       predecessor_symbol AS source_symbol,
                       symbol AS target_symbol,
                       identity_chain_id,
                       segment_id,
                       incoming_handoff_gap_calendar_days
                FROM read_parquet({_sql_string(self.identity_segments_path)}, hive_partitioning=false)
                WHERE predecessor_symbol IS NOT NULL
                  AND continuity_basis = ?
                ORDER BY event_date, source_symbol, target_symbol
                """,
                [SAFE_NAME_CHANGE_CHAIN],
            )
            transfer_columns = [item[0] for item in transfer_cursor.description]
            transfers = [dict(zip(transfer_columns, row)) for row in transfer_cursor.fetchall()]

            decision_cursor = con.execute(
                f"""
                SELECT symbol, promotion_decision
                FROM read_parquet({_sql_string(self.gate7_decision_path)}, hive_partitioning=false)
                ORDER BY symbol
                """
            )
            decisions = decision_cursor.fetchall()
        finally:
            con.close()

        events: list[dict[str, object]] = []
        for row in transfers:
            events.append(
                {
                    "event_date": row["event_date"],
                    "event_type": TRANSFER_IDENTITY_STATE,
                    "source_symbol": row["source_symbol"],
                    "target_symbol": row["target_symbol"],
                    "reason": SAFE_NAME_CHANGE_CHAIN,
                    "identity_chain_id": row["identity_chain_id"],
                    "segment_id": row["segment_id"],
                    "handoff_gap_calendar_days": row["incoming_handoff_gap_calendar_days"],
                    "seam_decision": None,
                }
            )

        decision_counts: Counter[str] = Counter()
        seam_drops = 0
        for symbol, decision in decisions:
            decision_text = str(decision)
            decision_counts[decision_text] += 1
            if not seam_requires_state_drop(decision_text):
                continue
            seam_drops += 1
            events.append(
                {
                    "event_date": ALPACA_BACKFILL_SEAM_TARGET_SESSION,
                    "event_type": DROP_AT_PROVIDER_SEAM,
                    "source_symbol": str(symbol),
                    "target_symbol": None,
                    "reason": decision_text,
                    "identity_chain_id": None,
                    "segment_id": None,
                    "handoff_gap_calendar_days": None,
                    "seam_decision": decision_text,
                }
            )

        events.sort(
            key=lambda row: (
                str(row["event_date"]),
                str(row["event_type"]),
                str(row["source_symbol"]),
                str(row.get("target_symbol") or ""),
            )
        )
        counts = {
            "identity_transfers": len(transfers),
            "seam_drop_events": seam_drops,
            "bridge_exact_literal": int(decision_counts[BRIDGE_EXACT_LITERAL]),
            "reset_at_provider_seam": int(decision_counts[RESET_AT_PROVIDER_SEAM]),
            "terminate_preseam_continuity": int(
                decision_counts[TERMINATE_PRESEAM_CONTINUITY]
            ),
            "quarantine_seam_continuity": int(
                decision_counts[QUARANTINE_SEAM_CONTINUITY]
            ),
            "postseam_only": int(decision_counts[POSTSEAM_ONLY]),
        }
        return events, counts

    def _write_lifecycle(self, events: list[dict[str, object]]) -> None:
        self.lifecycle_path.parent.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(events)
        temp = unique_temp_path(self.lifecycle_path)
        con = duckdb.connect(":memory:")
        try:
            con.register("lifecycle_df", frame)
            con.execute(
                f"""
                COPY (
                    SELECT * FROM lifecycle_df
                    ORDER BY event_date, event_type, source_symbol, target_symbol NULLS LAST
                ) TO {_sql_string(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        finally:
            con.close()
        replace_with_retry(temp, self.lifecycle_path)

    def run(self) -> dict[str, object]:
        gate8 = self.gate8_validator.run()
        if gate8.get("pass") is not True:
            raise RuntimeError("Gate 9-A requires accepted Gate 8 independent revalidation")
        gate7 = self._load_json(self.gate7_report_path, "Gate 7 final report")
        gate7_decision_sha = sha256_file(self.gate7_decision_path)
        identity_report = self._load_json(
            self.identity_segment_report_path,
            "Gate 4-C identity segment report",
        )
        gate8_preflight = self._load_json(self.gate8_preflight_path, "Gate 8 preflight report")

        canonical_inventory = self._canonical_inventory()
        canonical_paths = [Path(str(item["path"])) for item in canonical_inventory]
        canonical_stats = self._canonical_stats(canonical_paths)
        canonical_fp = inventory_fingerprint(canonical_inventory)
        production_feature_inventory, feature_baseline = self._production_feature_baseline()
        events, lifecycle_counts = self._lifecycle_events()
        self._write_lifecycle(events)

        identity_segments_sha = sha256_file(self.identity_segments_path)
        source_fp = lifecycle_source_fingerprint(
            gate8_fingerprint=str(gate8["source_fingerprint"]),
            gate7_fingerprint=str(gate7["source_fingerprint"]),
            gate7_decision_sha256=gate7_decision_sha,
            identity_segments_sha256=identity_segments_sha,
            canonical_inventory_fingerprint=canonical_fp,
            production_feature_baseline_fingerprint=str(feature_baseline["fingerprint"]),
        )

        expected_rows = int(gate8["promoted_rows"]) + int(gate8_preflight["massive_baseline_rows"])
        expected_sessions = int(gate8["promoted_sessions"]) + int(
            gate8_preflight["massive_baseline_sessions"]
        )
        last_session = date.fromisoformat(str(canonical_stats["last_session"]))
        expected_exchange_sessions = self.calendar.sessions_in_range(ALPACA_BACKFILL_START, last_session)
        expected_transfers = int(identity_report.get("identity_eligible_safe_edges", -1))
        expected_seam_drops = (
            int(gate7["coverage_reset_symbols"])
            + int(gate7["terminal_preseam_symbols"])
            + int(gate7["quarantined_seam_symbols"])
            + int(gate7["postseam_only_symbols"])
        )

        checks = {
            "gate8_independent_revalidation_pass": gate8.get("pass") is True,
            "gate7_contract_and_pass": gate7.get("contract_version")
            == ALPACA_BACKFILL_SEAM_FINAL_CONTRACT_VERSION
            and gate7.get("gate7_pass") is True,
            "gate7_decision_map_current": gate7_decision_sha
            == str(gate8["gate7_decision_sha256"]),
            "identity_contract_current": identity_report.get("contract_version")
            == ALPACA_BACKFILL_IDENTITY_SEGMENT_POLICY_CONTRACT_VERSION,
            "canonical_schema_exact": canonical_stats["schema_exact"] is True,
            "canonical_row_accounting_exact": canonical_stats["rows"] == expected_rows,
            "canonical_session_accounting_exact": canonical_stats["sessions"]
            == expected_sessions
            == len(canonical_inventory)
            == len(expected_exchange_sessions),
            "canonical_provider_accounting_exact": canonical_stats["alpaca_rows"]
            == int(gate8["promoted_rows"])
            and canonical_stats["massive_rows"]
            == int(gate8_preflight["massive_baseline_rows"])
            and canonical_stats["other_rows"] == 0,
            "canonical_range_exact": canonical_stats["first_session"]
            == ALPACA_BACKFILL_START.isoformat()
            and canonical_stats["last_session"]
            == str(gate8_preflight["massive_baseline_last_session"]),
            "identity_transfer_count_exact": lifecycle_counts["identity_transfers"]
            == expected_transfers,
            "identity_transfers_preseam": all(
                row["event_date"] < ALPACA_BACKFILL_SEAM_TARGET_SESSION
                for row in events
                if row["event_type"] == TRANSFER_IDENTITY_STATE
            ),
            "seam_drop_count_exact": lifecycle_counts["seam_drop_events"]
            == expected_seam_drops,
            "seam_decision_accounting_exact": lifecycle_counts["bridge_exact_literal"]
            == int(gate7["safe_exact_literal_bridges"])
            and lifecycle_counts["reset_at_provider_seam"]
            == int(gate7["coverage_reset_symbols"])
            and lifecycle_counts["terminate_preseam_continuity"]
            == int(gate7["terminal_preseam_symbols"])
            and lifecycle_counts["quarantine_seam_continuity"]
            == int(gate7["quarantined_seam_symbols"])
            and lifecycle_counts["postseam_only"]
            == int(gate7["postseam_only_symbols"]),
            "production_feature_baseline_present": bool(production_feature_inventory),
            "production_feature_manifests_clean": int(feature_baseline["manifest_failures"])
            == 0,
            "production_feature_hashes_clean": int(feature_baseline["feature_hash_failures"])
            == 0,
            "production_feature_sources_current": int(feature_baseline["source_hash_failures"])
            == 0,
            "production_feature_current_state_present": bool(
                feature_baseline["current_state_present"]
            ),
            "candidate_namespace_isolated": self.candidate_feature_root.resolve()
            != (
                self.settings.resolved_path(self.settings.data.paths.derived)
                / "features"
                / "1d"
            ).resolve(),
            "production_feature_writes_zero": True,
        }

        report: dict[str, object] = {
            "contract_version": GATE9_FEATURE_REPLAY_PREFLIGHT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_FEATURE_REPLAY_ROLE,
            "source_fingerprint": source_fp,
            "gate8_source_fingerprint": gate8["source_fingerprint"],
            "gate7_source_fingerprint": gate7["source_fingerprint"],
            "gate7_decision_sha256": gate7_decision_sha,
            "identity_segments_sha256": identity_segments_sha,
            "canonical_inventory_fingerprint": canonical_fp,
            "production_feature_baseline_fingerprint": feature_baseline["fingerprint"],
            "feature_contract_version": CORE_FEATURE_CONTRACT_VERSION,
            "feature_registry_fingerprint": CORE_FEATURE_REGISTRY.fingerprint(),
            "feature_count": len(CORE_FEATURE_REGISTRY.all()),
            "timeframe": Timeframe.DAY_1.value,
            "canonical": canonical_stats,
            "lifecycle": lifecycle_counts,
            "lifecycle_events": len(events),
            "production_feature_baseline": feature_baseline,
            "candidate_feature_root": str(self.candidate_feature_root),
            "candidate_manifest_root": str(self.candidate_manifest_root),
            "candidate_state_root": str(self.candidate_state_root),
            "lifecycle_path": str(self.lifecycle_path),
            "report_path": str(self.report_path),
            "production_feature_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True, default=str) + "\n",
        )
        return report
