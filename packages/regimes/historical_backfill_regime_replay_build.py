from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.discovery.filter_policy import ACTIVE_DISCOVERY_FILTER_POLICY
from packages.features.partition_store import FeaturePartitionManifest, sha256_file

from .calibration import RegimeCalibration, basket_daily
from .historical_backfill_regime_replay import (
    GATE10_INTRADAY_POLICY,
    GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN,
    GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION,
    GATE10_TICKER_ORIGIN,
    HistoricalBackfillRegimeReplayPreflight,
    sector_first_dates,
)
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS
from .persistence_policy import (
    REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
    REGIME_SELECTED_CONFIRMATION_SESSIONS,
)
from .state_engine import (
    _market_evidence,
    _market_thresholds,
    _score_fields,
    _sector_evidence,
    _sector_thresholds,
    _state_fields,
    compute_regime_state_history,
)
from .threshold_policy import (
    POINT_IN_TIME_THRESHOLD_RULE,
    REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
    REGIME_THRESHOLD_POLICY_NAME,
    REGIME_THRESHOLD_TRAINING_SESSIONS,
)
from .ticker_persistence_policy import TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION
from .ticker_risk_policy import TICKER_RISK_POLICY_CONTRACT_VERSION
from .ticker_state_engine import (
    TICKER_STATE_MANIFEST_VERSION,
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
    TickerStateBuildResult,
    TickerStateEngine,
)


GATE10_SPLIT_ORIGIN_POLICY_VERSION = (
    "historical-backfill-regime-split-policy-v1-market-sector-daily-2016-ticker-intraday-2021"
)
GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION = (
    "regime-state-policy-v2-expanding252-confirm2-dimensional-daily-origin-2016"
)
GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION = (
    "regime-state-snapshot-v2-market-sector-proxies-daily-origin-2016"
)
GATE10_MARKET_SECTOR_MANIFEST_VERSION = (
    "regime-state-manifest-v2-split-origin-source-lineage"
)
GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION = (
    "historical-backfill-regime-replay-v1-isolated-split-origin"
)
GATE10_REGIME_REPLAY_BUILD_ROLE = "ISOLATED_REGIME_REPLAY_NO_PRODUCTION_WRITES"


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _hash_or_missing(path: Path) -> str | None:
    return sha256_file(path) if path.is_file() else None


def _write_frame(settings: AtlasSettings, frame: pd.DataFrame, path: Path, order_by: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(path)
    con = connect_utc(":memory:")
    try:
        con.register("atlas_gate10_frame", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"""
            COPY (SELECT * FROM atlas_gate10_frame ORDER BY {order_by})
            TO {sql_string(temp)}
            (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
            """
        )
        promote(temp, path)
    finally:
        con.close()


def _frame_key_unique(frame: pd.DataFrame, columns: list[str]) -> bool:
    return not frame.duplicated(columns).any()


class _IsolatedTickerStateEngine(TickerStateEngine):
    """Reuse the accepted ticker algorithm while redirecting only its output paths."""

    def __init__(
        self,
        settings: AtlasSettings,
        *,
        output_snapshot_path: Path,
        output_manifest_path: Path,
    ) -> None:
        super().__init__(settings)
        self._output_snapshot_path = output_snapshot_path
        self._output_manifest_path = output_manifest_path

    def snapshot_path(self, as_of_date: date) -> Path:  # noqa: ARG002 - contract override
        return self._output_snapshot_path

    def manifest_path(self, as_of_date: date) -> Path:  # noqa: ARG002 - contract override
        return self._output_manifest_path


class HistoricalBackfillRegimeReplayBuilder:
    """Gate 10-B isolated split-origin market/sector + ticker replay."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.preflight = HistoricalBackfillRegimeReplayPreflight(settings)
        self.calibration = RegimeCalibration(settings)
        self.production_ticker_engine = TickerStateEngine(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "historical_backfill" / "alpaca" / "regime_replay" / "v1"
        self.candidate_root = self.root / "candidate"
        self.history_root = self.candidate_root / "history"
        self.market_raw_path = self.history_root / "market_raw.parquet"
        self.market_effective_path = self.history_root / "market_effective.parquet"
        self.sector_raw_path = self.history_root / "sector_raw.parquet"
        self.sector_effective_path = self.history_root / "sector_effective.parquet"
        self.market_sector_snapshot_path = self.candidate_root / "market_sector" / "snapshot.json"
        self.market_sector_manifest_path = self.candidate_root / "market_sector" / "manifest.json"
        self.ticker_snapshot_path = self.candidate_root / "ticker" / "part-000.parquet"
        self.ticker_manifest_path = self.candidate_root / "ticker" / "manifest.json"
        self.report_path = self.candidate_root / "gate10_replay_report.json"

    def _production_baseline(self, as_of_date: date) -> dict[str, object]:
        market_snapshot = self.preflight.regime_engine.paths.regime_state_snapshot(as_of_date)
        market_manifest = self.preflight.regime_engine.paths.regime_state_manifest(as_of_date)
        ticker_snapshot = self.production_ticker_engine.snapshot_path(as_of_date)
        ticker_manifest = self.production_ticker_engine.manifest_path(as_of_date)
        paths = {
            "market_sector_snapshot": market_snapshot,
            "market_sector_manifest": market_manifest,
            "ticker_snapshot": ticker_snapshot,
            "ticker_manifest": ticker_manifest,
        }
        return {
            key: {
                "path": str(path.resolve()),
                "present": path.is_file(),
                "sha256": _hash_or_missing(path),
            }
            for key, path in paths.items()
        }

    def _daily_source_lineage(self, as_of_date: date) -> tuple[int, str]:
        entries: list[str] = []
        sessions = self.preflight.calendar.sessions_in_range(
            GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN,
            as_of_date,
        )
        for session in sessions:
            path = self.preflight.paths.feature_manifest_file(Timeframe.DAY_1, session)
            if not path.is_file():
                raise FileNotFoundError(f"Gate 10-B missing production 1d feature manifest: {path}")
            payload = json.loads(path.read_text(encoding="utf-8"))
            manifest = FeaturePartitionManifest.from_dict(payload)
            manifest.validate_contract(Timeframe.DAY_1, session)
            entries.append(
                ":".join(
                    (
                        session.isoformat(),
                        manifest.source_sha256,
                        manifest.feature_sha256,
                        manifest.dependency_fingerprint,
                    )
                )
            )
        return len(entries), hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()

    def _market_sector_dependency(
        self,
        *,
        as_of_date: date,
        source_manifest_count: int,
        source_lineage: str,
        preflight_source_fingerprint: str,
    ) -> str:
        return _stable_hash(
            {
                "build_contract": GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
                "split_origin_policy": GATE10_SPLIT_ORIGIN_POLICY_VERSION,
                "market_sector_state_policy": GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
                "market_sector_snapshot_contract": GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
                "threshold_policy": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
                "persistence_policy": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
                "breadth_population": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
                "history_origin": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
                "ticker_origin": GATE10_TICKER_ORIGIN.isoformat(),
                "intraday_policy": GATE10_INTRADAY_POLICY,
                "threshold_training_sessions": REGIME_THRESHOLD_TRAINING_SESSIONS,
                "confirmation_sessions": REGIME_SELECTED_CONFIRMATION_SESSIONS,
                "minimum_dollar_volume": float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume),
                "market_proxies": MARKET_PROXY_TICKERS,
                "sector_proxies": SECTOR_PROXY_TICKERS,
                "as_of_date": as_of_date.isoformat(),
                "source_manifest_count": source_manifest_count,
                "source_lineage": source_lineage,
                "gate10a_source_fingerprint": preflight_source_fingerprint,
            }
        )

    def _market_sector_snapshot(
        self,
        *,
        as_of_date: date,
        breadth: pd.DataFrame,
        proxies: pd.DataFrame,
        raw_market: pd.DataFrame,
        effective_market: pd.DataFrame,
        raw_sector: pd.DataFrame,
        effective_sector: pd.DataFrame,
        source_manifest_count: int,
        source_lineage: str,
    ) -> tuple[dict[str, object], dict[str, int]]:
        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        market_basket = basket_daily(market_frame)

        raw_market_row = raw_market.sort_values("trading_date").iloc[-1]
        effective_market_row = effective_market.sort_values("trading_date").iloc[-1]
        if pd.Timestamp(effective_market_row["trading_date"]).date() != as_of_date:
            raise ValueError("Gate 10-B market replay is not current at the requested as-of date")

        raw_sector_sorted = raw_sector.sort_values(["symbol", "trading_date"])
        effective_sector_sorted = effective_sector.sort_values(["symbol", "trading_date"])
        sectors: dict[str, object] = {}
        sector_counts: Counter[str] = Counter()
        for ticker in SECTOR_PROXY_TICKERS:
            raw_subset = raw_sector_sorted.loc[raw_sector_sorted["symbol"] == ticker]
            effective_subset = effective_sector_sorted.loc[effective_sector_sorted["symbol"] == ticker]
            evidence_subset = sector_frame.loc[sector_frame["symbol"] == ticker].sort_values("trading_date")
            if raw_subset.empty or effective_subset.empty or evidence_subset.empty:
                raise ValueError(f"Gate 10-B missing sector replay evidence for {ticker}")
            raw_row = raw_subset.iloc[-1]
            effective_row = effective_subset.iloc[-1]
            evidence_row = evidence_subset.iloc[-1]
            if pd.Timestamp(effective_row["trading_date"]).date() != as_of_date:
                raise ValueError(f"Gate 10-B {ticker} effective state is not current")
            if pd.Timestamp(evidence_row["trading_date"]).date() != as_of_date:
                raise ValueError(f"Gate 10-B {ticker} evidence is not current")
            effective_fields = _state_fields(effective_row, market=False)
            sector_counts.update([str(effective_fields["composite"])])
            sectors[ticker] = {
                "raw": {**_state_fields(raw_row, market=False), **_score_fields(raw_row)},
                "effective": effective_fields,
                "evidence": _sector_evidence(evidence_row),
                "thresholds": _sector_thresholds(sector_frame, ticker),
            }

        snapshot = {
            "snapshot_contract_version": GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": GATE10_SPLIT_ORIGIN_POLICY_VERSION,
            "threshold_policy_contract_version": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population_contract_version": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "history_origin_date": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
            "ticker_history_origin_date": GATE10_TICKER_ORIGIN.isoformat(),
            "intraday_policy": GATE10_INTRADAY_POLICY,
            "point_in_time_rule": POINT_IN_TIME_THRESHOLD_RULE,
            "threshold_policy": REGIME_THRESHOLD_POLICY_NAME,
            "threshold_training_sessions": REGIME_THRESHOLD_TRAINING_SESSIONS,
            "confirmation_sessions": REGIME_SELECTED_CONFIRMATION_SESSIONS,
            "minimum_dollar_volume": float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume),
            "source_manifest_count": source_manifest_count,
            "source_lineage_fingerprint": source_lineage,
            "usable_breadth_session_count": int(len(breadth)),
            "evaluation_session_count": int(len(effective_market)),
            "first_evaluation_date": str(pd.Timestamp(effective_market.iloc[0]["trading_date"]).date()),
            "market": {
                "raw": {**_state_fields(raw_market_row, market=True), **_score_fields(raw_market_row)},
                "effective": _state_fields(effective_market_row, market=True),
                "evidence": _market_evidence(breadth, market_basket, as_of_date),
                "thresholds": _market_thresholds(breadth, market_basket),
            },
            "sectors": sectors,
        }
        return snapshot, dict(sorted(sector_counts.items()))

    def run(self) -> dict[str, Any]:
        started = perf_counter()
        preflight = self.preflight.run()
        if preflight.get("pass") is not True:
            raise RuntimeError("Gate 10-B requires a current passing Gate 10-A preflight")
        if preflight.get("contract_version") != GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION:
            raise ValueError("Gate 10-B encountered an unexpected Gate 10-A contract")

        as_of_date = date.fromisoformat(str(preflight["as_of_date"]))
        production_before = self._production_baseline(as_of_date)
        source_manifest_count, source_lineage = self._daily_source_lineage(as_of_date)
        dependency = self._market_sector_dependency(
            as_of_date=as_of_date,
            source_manifest_count=source_manifest_count,
            source_lineage=source_lineage,
            preflight_source_fingerprint=str(preflight["source_fingerprint"]),
        )
        source_fingerprint = _stable_hash(
            {
                "contract": GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
                "split_origin_policy": GATE10_SPLIT_ORIGIN_POLICY_VERSION,
                "gate10a_source_fingerprint": preflight["source_fingerprint"],
                "gate9c_handoff_source_fingerprint": preflight["gate9c_handoff_source_fingerprint"],
                "market_sector_dependency": dependency,
                "ticker_policy": TICKER_STATE_POLICY_CONTRACT_VERSION,
                "ticker_snapshot_contract": TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
                "ticker_manifest": TICKER_STATE_MANIFEST_VERSION,
                "ticker_persistence": TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION,
                "ticker_risk": TICKER_RISK_POLICY_CONTRACT_VERSION,
            }
        )

        breadth = self.calibration._breadth_daily(GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date)
        proxies = self.calibration._proxy_frame(GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date)
        raw_market, effective_market, raw_sector, effective_sector = compute_regime_state_history(
            breadth,
            proxies,
        )
        if any(frame.empty for frame in (raw_market, effective_market, raw_sector, effective_sector)):
            raise ValueError("Gate 10-B market/sector replay produced an empty state history")

        _write_frame(self.settings, raw_market, self.market_raw_path, "trading_date")
        _write_frame(self.settings, effective_market, self.market_effective_path, "trading_date")
        _write_frame(self.settings, raw_sector, self.sector_raw_path, "symbol, trading_date")
        _write_frame(self.settings, effective_sector, self.sector_effective_path, "symbol, trading_date")

        snapshot, sector_counts = self._market_sector_snapshot(
            as_of_date=as_of_date,
            breadth=breadth,
            proxies=proxies,
            raw_market=raw_market,
            effective_market=effective_market,
            raw_sector=raw_sector,
            effective_sector=effective_sector,
            source_manifest_count=source_manifest_count,
            source_lineage=source_lineage,
        )
        self.market_sector_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.market_sector_snapshot_path,
            json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        )
        market_sector_snapshot_sha = sha256_file(self.market_sector_snapshot_path)
        market_sector_manifest = {
            "manifest_version": GATE10_MARKET_SECTOR_MANIFEST_VERSION,
            "snapshot_contract_version": GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": GATE10_SPLIT_ORIGIN_POLICY_VERSION,
            "threshold_policy_contract_version": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population_contract_version": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "history_origin_date": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
            "ticker_history_origin_date": GATE10_TICKER_ORIGIN.isoformat(),
            "source_manifest_count": source_manifest_count,
            "source_lineage_fingerprint": source_lineage,
            "dependency_fingerprint": dependency,
            "gate10a_source_fingerprint": str(preflight["source_fingerprint"]),
            "market_raw_rows": int(len(raw_market)),
            "market_effective_rows": int(len(effective_market)),
            "sector_raw_rows": int(len(raw_sector)),
            "sector_effective_rows": int(len(effective_sector)),
            "sector_first_dates": sector_first_dates(effective_sector),
            "market_state": str(effective_market.sort_values("trading_date").iloc[-1]["composite"]),
            "sector_state_counts": sector_counts,
            "history_files": {
                "market_raw": {"path": str(self.market_raw_path.resolve()), "sha256": sha256_file(self.market_raw_path)},
                "market_effective": {"path": str(self.market_effective_path.resolve()), "sha256": sha256_file(self.market_effective_path)},
                "sector_raw": {"path": str(self.sector_raw_path.resolve()), "sha256": sha256_file(self.sector_raw_path)},
                "sector_effective": {"path": str(self.sector_effective_path.resolve()), "sha256": sha256_file(self.sector_effective_path)},
            },
            "snapshot_path": str(self.market_sector_snapshot_path.resolve()),
            "snapshot_sha256": market_sector_snapshot_sha,
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        self.market_sector_manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            self.market_sector_manifest_path,
            json.dumps(market_sector_manifest, indent=2, sort_keys=True) + "\n",
        )

        isolated_ticker_engine = _IsolatedTickerStateEngine(
            self.settings,
            output_snapshot_path=self.ticker_snapshot_path,
            output_manifest_path=self.ticker_manifest_path,
        )
        ticker_result: TickerStateBuildResult = isolated_ticker_engine.build(as_of_date)
        ticker_manifest = json.loads(self.ticker_manifest_path.read_text(encoding="utf-8"))

        production_after = self._production_baseline(as_of_date)
        expected_candidate = preflight["candidate_market_sector_replay"]
        checks = {
            "build_contract": GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION
            == "historical-backfill-regime-replay-v1-isolated-split-origin",
            "gate10a_pass": preflight.get("pass") is True,
            "split_origin_policy_explicit": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN < GATE10_TICKER_ORIGIN,
            "market_sector_state_contract_versioned": GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION.startswith("regime-state-policy-v2-"),
            "ticker_semantic_contract_retained": ticker_manifest.get("state_policy_contract_version") == TICKER_STATE_POLICY_CONTRACT_VERSION,
            "ticker_snapshot_contract_retained": ticker_manifest.get("snapshot_contract_version") == TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
            "market_history_rows_match_preflight": int(len(effective_market)) == int(expected_candidate["market_effective_rows"]),
            "sector_history_rows_match_preflight": int(len(effective_sector)) == int(expected_candidate["sector_effective_rows"]),
            "market_history_keys_unique": _frame_key_unique(effective_market, ["trading_date"]),
            "sector_history_keys_unique": _frame_key_unique(effective_sector, ["symbol", "trading_date"]),
            "all_sector_proxies_present": set(effective_sector["symbol"].astype(str).unique()) == set(SECTOR_PROXY_TICKERS),
            "market_current_at_asof": pd.Timestamp(effective_market["trading_date"].max()).date() == as_of_date,
            "sector_current_at_asof": all(
                pd.Timestamp(group["trading_date"].max()).date() == as_of_date
                for _, group in effective_sector.groupby("symbol", observed=True)
            ),
            "ticker_origin_remains_intraday_boundary": GATE10_TICKER_ORIGIN.isoformat() == str(preflight["ticker_origin"]),
            "ticker_candidate_nonempty": ticker_result.record_count > 0,
            "ticker_candidate_snapshot_hash_exact": ticker_result.snapshot_sha256 == sha256_file(self.ticker_snapshot_path),
            "ticker_candidate_dependency_current": ticker_manifest.get("dependency_fingerprint") == self.production_ticker_engine._dependency(as_of_date)[0],
            "production_regime_artifacts_unchanged": production_before == production_after,
        }
        passed = all(checks.values())
        report = {
            "contract_version": GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
            "role": GATE10_REGIME_REPLAY_BUILD_ROLE,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "source_fingerprint": source_fingerprint,
            "split_origin_policy_version": GATE10_SPLIT_ORIGIN_POLICY_VERSION,
            "gate10a_contract_version": preflight["contract_version"],
            "gate10a_source_fingerprint": preflight["source_fingerprint"],
            "gate9c_handoff_source_fingerprint": preflight["gate9c_handoff_source_fingerprint"],
            "as_of_date": as_of_date.isoformat(),
            "market_sector_origin": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
            "ticker_origin": GATE10_TICKER_ORIGIN.isoformat(),
            "intraday_policy": GATE10_INTRADAY_POLICY,
            "market_sector_contracts": {
                "state_policy": GATE10_MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
                "snapshot": GATE10_MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
                "manifest": GATE10_MARKET_SECTOR_MANIFEST_VERSION,
                "dependency_fingerprint": dependency,
                "source_manifest_count": source_manifest_count,
                "source_lineage_fingerprint": source_lineage,
            },
            "market_sector_history": {
                "market_raw_rows": int(len(raw_market)),
                "market_effective_rows": int(len(effective_market)),
                "sector_raw_rows": int(len(raw_sector)),
                "sector_effective_rows": int(len(effective_sector)),
                "market_first_evaluation": str(pd.Timestamp(effective_market["trading_date"].min()).date()),
                "market_last_evaluation": str(pd.Timestamp(effective_market["trading_date"].max()).date()),
                "sector_first_evaluation": str(pd.Timestamp(effective_sector["trading_date"].min()).date()),
                "sector_last_evaluation": str(pd.Timestamp(effective_sector["trading_date"].max()).date()),
                "sector_first_dates": sector_first_dates(effective_sector),
                "files": market_sector_manifest["history_files"],
            },
            "market_sector_snapshot": {
                "path": str(self.market_sector_snapshot_path.resolve()),
                "sha256": market_sector_snapshot_sha,
                "manifest_path": str(self.market_sector_manifest_path.resolve()),
                "manifest_sha256": sha256_file(self.market_sector_manifest_path),
                "market_state": market_sector_manifest["market_state"],
                "sector_state_counts": sector_counts,
            },
            "ticker_candidate": {
                "state_policy_contract_version": TICKER_STATE_POLICY_CONTRACT_VERSION,
                "snapshot_contract_version": TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
                "manifest_version": TICKER_STATE_MANIFEST_VERSION,
                "record_count": ticker_result.record_count,
                "raw_state_available_count": ticker_result.raw_state_available_count,
                "confirmed_persistence_count": ticker_result.confirmed_persistence_count,
                "risk_mode_counts": ticker_result.risk_mode_counts,
                "persistence_status_counts": ticker_result.persistence_status_counts,
                "history_status_counts": ticker_result.history_status_counts,
                "effective_state_counts": ticker_result.effective_state_counts,
                "dependency_fingerprint": ticker_result.dependency_fingerprint,
                "snapshot_path": str(self.ticker_snapshot_path.resolve()),
                "snapshot_sha256": ticker_result.snapshot_sha256,
                "manifest_path": str(self.ticker_manifest_path.resolve()),
                "manifest_sha256": sha256_file(self.ticker_manifest_path),
                "skipped_exact": ticker_result.skipped,
            },
            "production_baseline_before": production_before,
            "production_baseline_after": production_after,
            "production_regime_writes": 0 if production_before == production_after else 1,
            "checks": checks,
            "wall_seconds": perf_counter() - started,
            "report_path": str(self.report_path.resolve()),
            "pass": passed,
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(self.report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
