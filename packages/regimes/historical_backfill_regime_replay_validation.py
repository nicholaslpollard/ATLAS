from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.settings import AtlasSettings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .calibration import RegimeCalibration
from .historical_backfill_regime_replay import (
    GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN,
    GATE10_TICKER_ORIGIN,
    HistoricalBackfillRegimeReplayPreflight,
    sector_first_dates,
)
from .historical_backfill_regime_replay_build import (
    GATE10_MARKET_SECTOR_MANIFEST_VERSION,
    GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
    GATE10_SPLIT_ORIGIN_POLICY_VERSION,
    HistoricalBackfillRegimeReplayBuilder,
    _IsolatedTickerStateEngine,
)
from .input_inventory import SECTOR_PROXY_TICKERS
from .state_engine import compute_regime_state_history
from .ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    TickerStateEngine,
    classify_current_ticker_dimensions,
)


GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION = (
    "historical-backfill-regime-replay-validation-v1-independent-disk-recompute-and-ticker-rebuild"
)
GATE10_REGIME_REPLAY_VALIDATION_ROLE = "READ_ONLY_PRODUCTION_INDEPENDENT_CANDIDATE_PROOF"


def _read_parquet(path: Path, order_by: str) -> pd.DataFrame:
    con = connect_utc(":memory:")
    try:
        return con.execute(
            f"SELECT * FROM read_parquet({sql_string(str(path.resolve()))}) ORDER BY {order_by}"
        ).fetchdf()
    finally:
        con.close()


def _normalize_dates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for column in ("trading_date", "as_of_date"):
        if column in result.columns:
            result[column] = pd.to_datetime(result[column], utc=True).dt.date
    return result


def _frames_equal(
    expected: pd.DataFrame,
    observed: pd.DataFrame,
    *,
    order_by: list[str],
    atol: float = 1e-12,
) -> bool:
    left = _normalize_dates(expected).sort_values(order_by).reset_index(drop=True)
    right = _normalize_dates(observed).sort_values(order_by).reset_index(drop=True)
    if list(left.columns) != list(right.columns):
        return False
    try:
        pd.testing.assert_frame_equal(
            left,
            right,
            check_dtype=False,
            check_exact=False,
            rtol=1e-12,
            atol=atol,
        )
    except AssertionError:
        return False
    return True


class HistoricalBackfillRegimeReplayValidator:
    """Gate 10-B independent disk/recompute proof over isolated candidate artifacts."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.preflight = HistoricalBackfillRegimeReplayPreflight(settings)
        self.builder = HistoricalBackfillRegimeReplayBuilder(settings)
        self.calibration = RegimeCalibration(settings)
        self.ticker_engine = TickerStateEngine(settings)
        self.validation_root = self.builder.root / "validation_rebuild"
        self.validation_ticker_snapshot = self.validation_root / "ticker" / "part-000.parquet"
        self.validation_ticker_manifest = self.validation_root / "ticker" / "manifest.json"
        self.report_path = self.builder.candidate_root / "gate10_validation_report.json"

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid Gate 10 JSON: {path}") from exc

    def _current_production_baseline(self, as_of_date: date) -> dict[str, object]:
        return self.builder._production_baseline(as_of_date)

    def _raw_ticker_classification_proof(
        self,
        candidate: pd.DataFrame,
        as_of_date: date,
    ) -> dict[str, int]:
        current, current_population = self.ticker_engine._current_frame(as_of_date)
        candidate_map = candidate.set_index("instrument_id").to_dict(orient="index")
        missing = 0
        mismatched = 0
        classified = 0
        for _, row in current.iterrows():
            instrument_id = str(row["instrument_id"])
            stored = candidate_map.get(instrument_id)
            if stored is None:
                missing += 1
                continue
            raw = classify_current_ticker_dimensions(row)
            if raw is None:
                expected = (None, None, None, None)
            else:
                classified += 1
                expected = (
                    raw["daily_structure"],
                    raw["short_alignment"],
                    raw["momentum"],
                    raw["ticker_state"],
                )
            observed = (
                stored.get("raw_daily_structure"),
                stored.get("raw_short_alignment"),
                stored.get("raw_momentum"),
                stored.get("raw_ticker_state"),
            )
            observed = tuple(None if pd.isna(value) else str(value) for value in observed)
            if observed != expected:
                mismatched += 1
        return {
            "current_population": int(current_population),
            "candidate_rows": int(len(candidate)),
            "missing_in_candidate": missing,
            "raw_classified_rows": classified,
            "raw_classification_mismatches": mismatched,
        }

    def run(self) -> dict[str, Any]:
        started = perf_counter()
        if not self.builder.report_path.is_file():
            raise FileNotFoundError(
                "Gate 10-B candidate report is missing; run materialize_historical_backfill_gate10.py first"
            )
        builder_report = self._read_json(self.builder.report_path)
        if builder_report.get("pass") is not True:
            raise ValueError("Gate 10-B builder report is not passing")
        if builder_report.get("contract_version") != GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION:
            raise ValueError("Gate 10-B builder contract mismatch")

        preflight = self.preflight.run()
        if preflight.get("pass") is not True:
            raise ValueError("Gate 10-B validation requires a current passing Gate 10-A preflight")
        as_of_date = date.fromisoformat(str(builder_report["as_of_date"]))
        if str(preflight["as_of_date"]) != as_of_date.isoformat():
            raise ValueError("Gate 10-B candidate as-of date is stale relative to current Gate 10-A")

        market_manifest = self._read_json(self.builder.market_sector_manifest_path)
        market_snapshot = self._read_json(self.builder.market_sector_snapshot_path)
        ticker_manifest = self._read_json(self.builder.ticker_manifest_path)

        observed_market_raw = _read_parquet(self.builder.market_raw_path, "trading_date")
        observed_market_effective = _read_parquet(self.builder.market_effective_path, "trading_date")
        observed_sector_raw = _read_parquet(self.builder.sector_raw_path, "symbol, trading_date")
        observed_sector_effective = _read_parquet(self.builder.sector_effective_path, "symbol, trading_date")
        observed_ticker = _read_parquet(self.builder.ticker_snapshot_path, "instrument_id")

        breadth = self.calibration._breadth_daily(GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date)
        proxies = self.calibration._proxy_frame(GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date)
        expected_market_raw, expected_market_effective, expected_sector_raw, expected_sector_effective = (
            compute_regime_state_history(breadth, proxies)
        )

        market_raw_equal = _frames_equal(
            expected_market_raw,
            observed_market_raw,
            order_by=["trading_date"],
        )
        market_effective_equal = _frames_equal(
            expected_market_effective,
            observed_market_effective,
            order_by=["trading_date"],
        )
        sector_raw_equal = _frames_equal(
            expected_sector_raw,
            observed_sector_raw,
            order_by=["symbol", "trading_date"],
        )
        sector_effective_equal = _frames_equal(
            expected_sector_effective,
            observed_sector_effective,
            order_by=["symbol", "trading_date"],
        )

        history_hash_failures = 0
        for name, entry in market_manifest.get("history_files", {}).items():
            path = Path(str(entry["path"]))
            if not path.is_file() or sha256_file(path) != str(entry["sha256"]):
                history_hash_failures += 1
        market_snapshot_hash_exact = (
            sha256_file(self.builder.market_sector_snapshot_path)
            == str(market_manifest.get("snapshot_sha256"))
        )

        expected_market_dependency = self.builder._market_sector_dependency(
            as_of_date=as_of_date,
            source_manifest_count=int(market_manifest["source_manifest_count"]),
            source_lineage=str(market_manifest["source_lineage_fingerprint"]),
            preflight_source_fingerprint=str(preflight["source_fingerprint"]),
        )
        current_ticker_dependency, _ = self.ticker_engine._dependency(as_of_date)
        raw_ticker_proof = self._raw_ticker_classification_proof(observed_ticker, as_of_date)

        validation_ticker_engine = _IsolatedTickerStateEngine(
            self.settings,
            output_snapshot_path=self.validation_ticker_snapshot,
            output_manifest_path=self.validation_ticker_manifest,
        )
        validation_ticker_result = validation_ticker_engine.build(as_of_date)
        rebuilt_ticker = _read_parquet(self.validation_ticker_snapshot, "instrument_id")
        ticker_rebuild_equal = _frames_equal(
            observed_ticker,
            rebuilt_ticker,
            order_by=["instrument_id"],
            atol=1e-12,
        )

        production_now = self._current_production_baseline(as_of_date)
        production_baseline_exact = (
            production_now == builder_report.get("production_baseline_before")
            == builder_report.get("production_baseline_after")
        )

        expected_candidate = preflight["candidate_market_sector_replay"]
        checks = {
            "validation_contract": GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION.startswith("historical-backfill-regime-replay-validation-v1-"),
            "builder_report_pass": builder_report.get("pass") is True,
            "gate10a_pass": preflight.get("pass") is True,
            "gate10a_fingerprint_exact": builder_report.get("gate10a_source_fingerprint") == preflight.get("source_fingerprint"),
            "gate9c_fingerprint_exact": builder_report.get("gate9c_handoff_source_fingerprint") == preflight.get("gate9c_handoff_source_fingerprint"),
            "split_origin_policy_exact": builder_report.get("split_origin_policy_version") == GATE10_SPLIT_ORIGIN_POLICY_VERSION,
            "market_sector_origin_exact": builder_report.get("market_sector_origin") == GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
            "ticker_origin_exact": builder_report.get("ticker_origin") == GATE10_TICKER_ORIGIN.isoformat(),
            "market_sector_manifest_version_exact": market_manifest.get("manifest_version") == GATE10_MARKET_SECTOR_MANIFEST_VERSION,
            "market_sector_state_policy_exact": market_manifest.get("state_policy_contract_version") == GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "market_sector_snapshot_contract_exact": market_snapshot.get("snapshot_contract_version") == GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "market_sector_dependency_recomputed": market_manifest.get("dependency_fingerprint") == expected_market_dependency,
            "market_snapshot_hash_exact": market_snapshot_hash_exact,
            "history_file_hashes_exact": history_hash_failures == 0,
            "market_raw_recompute_exact": market_raw_equal,
            "market_effective_recompute_exact": market_effective_equal,
            "sector_raw_recompute_exact": sector_raw_equal,
            "sector_effective_recompute_exact": sector_effective_equal,
            "market_row_accounting_exact": len(observed_market_effective) == int(expected_candidate["market_effective_rows"]),
            "sector_row_accounting_exact": len(observed_sector_effective) == int(expected_candidate["sector_effective_rows"]),
            "sector_first_dates_exact": sector_first_dates(observed_sector_effective) == expected_candidate["sector_first_dates"],
            "all_sector_proxies_present": set(observed_sector_effective["symbol"].astype(str).unique()) == set(SECTOR_PROXY_TICKERS),
            "ticker_manifest_version_retained": ticker_manifest.get("manifest_version") == TICKER_STATE_MANIFEST_VERSION,
            "ticker_state_policy_retained": ticker_manifest.get("state_policy_contract_version") == TICKER_STATE_POLICY_CONTRACT_VERSION,
            "ticker_snapshot_contract_retained": ticker_manifest.get("snapshot_contract_version") == TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
            "ticker_dependency_recomputed": ticker_manifest.get("dependency_fingerprint") == current_ticker_dependency,
            "ticker_snapshot_hash_exact": ticker_manifest.get("snapshot_sha256") == sha256_file(self.builder.ticker_snapshot_path),
            "ticker_population_exact": raw_ticker_proof["candidate_rows"] == raw_ticker_proof["current_population"],
            "ticker_candidate_missing_zero": raw_ticker_proof["missing_in_candidate"] == 0,
            "ticker_raw_classification_mismatches_zero": raw_ticker_proof["raw_classification_mismatches"] == 0,
            "ticker_second_isolated_rebuild_exact": ticker_rebuild_equal,
            "ticker_rebuild_dependency_exact": validation_ticker_result.dependency_fingerprint == current_ticker_dependency,
            "production_regime_artifacts_unchanged": production_baseline_exact,
        }
        passed = all(checks.values())
        report = {
            "contract_version": GATE10_REGIME_REPLAY_VALIDATION_CONTRACT_VERSION,
            "role": GATE10_REGIME_REPLAY_VALIDATION_ROLE,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "builder_contract_version": builder_report["contract_version"],
            "builder_source_fingerprint": builder_report["source_fingerprint"],
            "gate10a_source_fingerprint": preflight["source_fingerprint"],
            "gate9c_handoff_source_fingerprint": preflight["gate9c_handoff_source_fingerprint"],
            "as_of_date": as_of_date.isoformat(),
            "market_sector_recompute": {
                "market_raw_rows": int(len(observed_market_raw)),
                "market_effective_rows": int(len(observed_market_effective)),
                "sector_raw_rows": int(len(observed_sector_raw)),
                "sector_effective_rows": int(len(observed_sector_effective)),
                "market_raw_equal": market_raw_equal,
                "market_effective_equal": market_effective_equal,
                "sector_raw_equal": sector_raw_equal,
                "sector_effective_equal": sector_effective_equal,
                "history_hash_failures": history_hash_failures,
            },
            "ticker_proof": {
                **raw_ticker_proof,
                "candidate_dependency_fingerprint": ticker_manifest.get("dependency_fingerprint"),
                "current_dependency_fingerprint": current_ticker_dependency,
                "second_rebuild_rows": validation_ticker_result.record_count,
                "second_rebuild_equal": ticker_rebuild_equal,
                "second_rebuild_skipped": validation_ticker_result.skipped,
            },
            "production_baseline": production_now,
            "production_regime_writes": 0 if production_baseline_exact else 1,
            "checks": checks,
            "wall_seconds": perf_counter() - started,
            "builder_report_path": str(self.builder.report_path.resolve()),
            "validation_report_path": str(self.report_path.resolve()),
            "pass": passed,
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
