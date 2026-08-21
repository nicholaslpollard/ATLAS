from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_validated_evidence import sha256_file, stable_source_fingerprint
from packages.features.historical_backfill_feature_promotion import (
    GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
    HistoricalBackfillDailyFeaturePromotionPreflight,
)
from packages.features.historical_backfill_replay_build import apply_lifecycle_events
from packages.features.incremental import IncrementalFeatureEngine, feature_stream_key
from packages.features.state_checkpoint import feature_state_fingerprint


GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION = (
    "historical-backfill-feature-state-chain-v1-session-manifest-dependency-proof"
)
GATE9_FEATURE_STATE_CHAIN_ROLE = "CANDIDATE_SESSION_STATE_CHAIN_NOT_PRODUCTION"


def _sql_string(value: str | Path) -> str:
    return "'" + str(value).replace("\\", "/").replace("'", "''") + "'"


def state_chain_year_source_fingerprint(
    *,
    gate9c_preflight_source_fingerprint: str,
    replay_source_fingerprint: str,
    year: int,
    input_state_fingerprint: str,
    expected_output_state_fingerprint: str,
    canonical_rows: list[dict[str, object]],
    lifecycle_events: list[dict[str, object]],
) -> str:
    canonical = [
        {
            "session_date": str(row["session_date"]),
            "relative_path": str(row["relative_path"]).replace("\\", "/"),
            "sha256": str(row["sha256"]),
        }
        for row in canonical_rows
    ]
    canonical.sort(key=lambda row: row["session_date"])
    events = [
        {
            "event_date": str(row["event_date"]),
            "event_type": str(row["event_type"]),
            "source_symbol": str(row["source_symbol"]),
            "target_symbol": str(row.get("target_symbol") or ""),
            "reason": str(row.get("reason") or ""),
            "seam_decision": str(row.get("seam_decision") or ""),
        }
        for row in lifecycle_events
    ]
    events.sort(
        key=lambda row: (
            row["event_date"],
            row["event_type"],
            row["source_symbol"],
            row["target_symbol"],
        )
    )
    return stable_source_fingerprint(
        {
            "contract_version": GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION,
            "role": GATE9_FEATURE_STATE_CHAIN_ROLE,
            "gate9c_preflight_contract": GATE9_FEATURE_PROMOTION_PREFLIGHT_CONTRACT_VERSION,
            "gate9c_preflight_source_fingerprint": gate9c_preflight_source_fingerprint,
            "replay_source_fingerprint": replay_source_fingerprint,
            "year": int(year),
            "input_state_fingerprint": input_state_fingerprint,
            "expected_output_state_fingerprint": expected_output_state_fingerprint,
            "canonical": canonical,
            "lifecycle_events": events,
            "timeframe": Timeframe.DAY_1.value,
        }
    )


class HistoricalBackfillDailyFeatureStateChain:
    """Derive exact per-session feature-state dependencies without production writes.

    Gate 9-B intentionally stored year checkpoints rather than a checkpoint per session.
    Production FeaturePartitionManifest requires exact input/output state fingerprints,
    so Gate 9-C derives that missing dependency chain by replaying state only. Feature
    Parquet is never rewritten here. Every year must terminate at the already-accepted
    Gate 9-B checkpoint fingerprint, which independently anchors the derived session
    chain to the validated candidate replay.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.preflight = HistoricalBackfillDailyFeaturePromotionPreflight(settings)
        self.replay = self.preflight.replay
        self.root = self.preflight.root / "state_chain"
        self.year_root = self.root / "years"
        self.report_path = self.root / "gate9c_state_chain_report.json"
        self.chain_path = self.root / "feature_session_state_chain.parquet"

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        if not path.is_file():
            raise RuntimeError(f"Gate 9-C state chain requires {label}: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def year_chain_path(self, year: int) -> Path:
        return self.year_root / f"{year:04d}.parquet"

    def year_report_path(self, year: int) -> Path:
        return self.year_root / f"{year:04d}.json"

    @staticmethod
    def _update_state(engine: IncrementalFeatureEngine, bars: pd.DataFrame) -> None:
        for row in bars.itertuples(index=False):
            symbol = str(row.symbol)
            state_key = feature_stream_key(symbol, None)
            engine.update(
                symbol=symbol,
                state_key=state_key,
                timestamp_utc=row.timestamp_utc,
                high=float(row.high),
                low=float(row.low),
                close=float(row.close),
                volume=float(row.volume),
            )

    @staticmethod
    def _write_parquet(frame: pd.DataFrame, path: Path) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = unique_temp_path(path)
        con = duckdb.connect(":memory:")
        try:
            con.register("state_chain", frame)
            con.execute(
                f"""
                COPY (
                    SELECT *
                    FROM state_chain
                    ORDER BY session_date
                ) TO {_sql_string(temp)} (FORMAT PARQUET, COMPRESSION ZSTD)
                """
            )
        finally:
            con.close()
        replace_with_retry(temp, path)
        return sha256_file(path)

    def _read_year_rows(self, path: Path) -> list[dict[str, object]]:
        con = duckdb.connect(":memory:")
        try:
            cursor = con.execute(
                f"SELECT * FROM read_parquet({_sql_string(path)}, hive_partitioning=false) "
                "ORDER BY session_date"
            )
            columns = [item[0] for item in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
        finally:
            con.close()

    def _accepted_year_payload(self, year: int) -> dict[str, Any]:
        return self._load_json(
            self.replay.year_manifest_path(year),
            f"accepted Gate 9-B year manifest {year}",
        )

    def _starting_engine_and_fingerprint(
        self,
        year: int,
        previous_year: int | None,
    ) -> tuple[IncrementalFeatureEngine, str, str]:
        if previous_year is None:
            engine = IncrementalFeatureEngine()
            as_of = "genesis"
            return (
                engine,
                feature_state_fingerprint(engine, timeframe=Timeframe.DAY_1, as_of_date=as_of),
                as_of,
            )
        previous = self._accepted_year_payload(previous_year)
        checkpoint_path = Path(str(previous["checkpoint_path"]))
        engine, checkpoint = self.replay.checkpoints.read(
            checkpoint_path,
            expected_timeframe=Timeframe.DAY_1,
        )
        expected = str(previous["output_state_fingerprint"])
        if checkpoint.get("checkpoint_fingerprint") != expected:
            raise RuntimeError(f"Gate 9-C prior-year checkpoint mismatch: {previous_year}")
        as_of = str(previous["last_session"])
        actual = feature_state_fingerprint(engine, timeframe=Timeframe.DAY_1, as_of_date=as_of)
        if actual != expected:
            raise RuntimeError(f"Gate 9-C prior-year state fingerprint mismatch: {previous_year}")
        return engine, actual, as_of

    def _validate_reusable_year(
        self,
        *,
        year: int,
        source_fingerprint: str,
        expected_sessions: int,
        expected_output_state_fingerprint: str,
    ) -> tuple[bool, list[dict[str, object]]]:
        chain_path = self.year_chain_path(year)
        report_path = self.year_report_path(year)
        if not chain_path.is_file() or not report_path.is_file():
            return False, []
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("contract_version") != GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION:
                return False, []
            if report.get("source_fingerprint") != source_fingerprint:
                return False, []
            if report.get("chain_sha256") != sha256_file(chain_path):
                return False, []
            if int(report.get("sessions", -1)) != expected_sessions:
                return False, []
            if report.get("output_state_fingerprint") != expected_output_state_fingerprint:
                return False, []
            rows = self._read_year_rows(chain_path)
            if len(rows) != expected_sessions:
                return False, []
            if not rows or str(rows[-1]["output_state_fingerprint"]) != expected_output_state_fingerprint:
                return False, []
            return True, rows
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return False, []

    def run(self, *, force: bool = False) -> dict[str, object]:
        gate9c = self.preflight.run()
        if gate9c.get("pass") is not True:
            raise RuntimeError("Gate 9-C state chain requires accepted promotion preflight")

        replay_report = self._load_json(self.replay.report_path, "Gate 9-B replay report")
        canonical_inventory = self.replay.preflight._canonical_inventory()
        grouped = self.replay._group_inventory(canonical_inventory)
        events = self.replay._load_lifecycle_events()
        events_by_date = self.replay._events_by_date(events)

        candidate_session_records: dict[str, dict[str, object]] = {}
        for year_record in list(replay_report.get("year_manifests") or []):
            year_payload = self._accepted_year_payload(int(year_record["year"]))
            for record in list(year_payload.get("sessions") or []):
                candidate_session_records[str(record["session_date"])] = record

        all_rows: list[dict[str, object]] = []
        rebuilt_years: list[int] = []
        reused_years: list[int] = []
        year_reconciliations: list[dict[str, object]] = []
        previous_year: int | None = None

        for year, canonical_rows in grouped.items():
            accepted_year = self._accepted_year_payload(year)
            expected_output = str(accepted_year["output_state_fingerprint"])
            engine, input_state_fp, input_as_of = self._starting_engine_and_fingerprint(
                year,
                previous_year,
            )
            year_events = [
                row
                for row in events
                if isinstance(row["event_date"], date) and row["event_date"].year == year
            ]
            year_fp = state_chain_year_source_fingerprint(
                gate9c_preflight_source_fingerprint=str(gate9c["source_fingerprint"]),
                replay_source_fingerprint=str(replay_report["source_fingerprint"]),
                year=year,
                input_state_fingerprint=input_state_fp,
                expected_output_state_fingerprint=expected_output,
                canonical_rows=canonical_rows,
                lifecycle_events=year_events,
            )

            reusable, rows = (False, [])
            if not force:
                reusable, rows = self._validate_reusable_year(
                    year=year,
                    source_fingerprint=year_fp,
                    expected_sessions=len(canonical_rows),
                    expected_output_state_fingerprint=expected_output,
                )
            if reusable:
                reused_years.append(year)
                all_rows.extend(rows)
                year_reconciliations.append(
                    {
                        "year": year,
                        "sessions": len(rows),
                        "expected_output_state_fingerprint": expected_output,
                        "actual_output_state_fingerprint": str(rows[-1]["output_state_fingerprint"]),
                        "match": True,
                        "reused": True,
                    }
                )
                previous_year = year
                continue

            rows = []
            current_input_as_of = input_as_of
            for source_row in canonical_rows:
                session = date.fromisoformat(str(source_row["session_date"]))
                session_events = events_by_date.get(session, [])
                apply_lifecycle_events(engine, session_events)
                session_input_fp = feature_state_fingerprint(
                    engine,
                    timeframe=Timeframe.DAY_1,
                    as_of_date=current_input_as_of,
                )
                source_path = Path(str(source_row["path"]))
                if not source_path.is_file() or sha256_file(source_path) != str(source_row["sha256"]):
                    raise RuntimeError(f"Gate 9-C canonical source changed: {source_path}")
                bars = self.replay._load_source(source_path)
                self._update_state(engine, bars)
                session_output_fp = feature_state_fingerprint(
                    engine,
                    timeframe=Timeframe.DAY_1,
                    as_of_date=session.isoformat(),
                )
                candidate = candidate_session_records.get(session.isoformat())
                if candidate is None:
                    raise RuntimeError(f"Gate 9-C candidate session record missing: {session}")
                rows.append(
                    {
                        "session_date": session.isoformat(),
                        "input_as_of": current_input_as_of,
                        "input_state_fingerprint": session_input_fp,
                        "output_state_fingerprint": session_output_fp,
                        "lifecycle_event_count": len(session_events),
                        "source_sha256": str(source_row["sha256"]),
                        "candidate_feature_sha256": str(candidate["feature_sha256"]),
                        "candidate_manifest_sha256": str(candidate["manifest_sha256"]),
                        "row_count": int(candidate["row_count"]),
                        "symbol_count": int(candidate["symbol_count"]),
                    }
                )
                current_input_as_of = session.isoformat()

            actual_output = str(rows[-1]["output_state_fingerprint"]) if rows else ""
            if actual_output != expected_output:
                raise RuntimeError(
                    f"Gate 9-C state chain year {year} does not reconcile to accepted checkpoint"
                )
            frame = pd.DataFrame(rows)
            chain_sha = self._write_parquet(frame, self.year_chain_path(year))
            year_report = {
                "contract_version": GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION,
                "generated_at_utc": datetime.now(UTC).isoformat(),
                "role": GATE9_FEATURE_STATE_CHAIN_ROLE,
                "source_fingerprint": year_fp,
                "year": year,
                "sessions": len(rows),
                "input_state_fingerprint": input_state_fp,
                "output_state_fingerprint": actual_output,
                "expected_output_state_fingerprint": expected_output,
                "chain_path": str(self.year_chain_path(year)),
                "chain_sha256": chain_sha,
                "pass": actual_output == expected_output,
            }
            atomic_write_text(
                self.year_report_path(year),
                json.dumps(year_report, indent=2, sort_keys=True) + "\n",
            )
            rebuilt_years.append(year)
            all_rows.extend(rows)
            year_reconciliations.append(
                {
                    "year": year,
                    "sessions": len(rows),
                    "expected_output_state_fingerprint": expected_output,
                    "actual_output_state_fingerprint": actual_output,
                    "match": actual_output == expected_output,
                    "reused": False,
                }
            )
            previous_year = year

        if not all_rows:
            raise RuntimeError("Gate 9-C state chain produced no session rows")
        combined = pd.DataFrame(all_rows)
        if combined["session_date"].duplicated().any():
            raise RuntimeError("Gate 9-C state chain contains duplicate sessions")
        chain_sha = self._write_parquet(combined, self.chain_path)
        expected_sessions = int(gate9c["candidate"]["sessions"])
        final_expected = str(replay_report["current_state_fingerprint"])
        final_actual = str(all_rows[-1]["output_state_fingerprint"])
        checks = {
            "gate9c_preflight_pass": gate9c.get("pass") is True,
            "replay_source_fingerprint_current": replay_report.get("source_fingerprint")
            == gate9c.get("gate9b_replay_source_fingerprint"),
            "session_accounting_exact": len(all_rows) == expected_sessions,
            "session_keys_unique": len({str(row["session_date"]) for row in all_rows})
            == len(all_rows),
            "all_year_checkpoints_reconciled": all(
                row["match"] is True for row in year_reconciliations
            ),
            "final_state_matches_candidate_current": final_actual == final_expected,
            "candidate_feature_hashes_bound": all(bool(row["candidate_feature_sha256"]) for row in all_rows),
            "production_feature_writes_zero": True,
        }
        report = {
            "contract_version": GATE9_FEATURE_STATE_CHAIN_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE9_FEATURE_STATE_CHAIN_ROLE,
            "gate9c_preflight_source_fingerprint": gate9c["source_fingerprint"],
            "replay_source_fingerprint": replay_report["source_fingerprint"],
            "sessions": len(all_rows),
            "first_session": str(all_rows[0]["session_date"]),
            "last_session": str(all_rows[-1]["session_date"]),
            "rebuilt_years": rebuilt_years,
            "reused_years": reused_years,
            "year_reconciliations": year_reconciliations,
            "final_output_state_fingerprint": final_actual,
            "candidate_current_state_fingerprint": final_expected,
            "chain_path": str(self.chain_path),
            "chain_sha256": chain_sha,
            "checks": checks,
            "production_feature_writes": 0,
            "pass": all(checks.values()),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
