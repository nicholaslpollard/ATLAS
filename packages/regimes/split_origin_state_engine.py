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
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.discovery.filter_policy import ACTIVE_DISCOVERY_FILTER_POLICY
from packages.features.partition_store import FeaturePartitionManifest, sha256_file

from .calibration import RegimeCalibration, basket_daily
from .historical_backfill_regime_replay_build import GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS
from .persistence_policy import (
    REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
    REGIME_SELECTED_CONFIRMATION_SESSIONS,
)
from .split_origin_policy import (
    INTRADAY_POLICY,
    MARKET_SECTOR_HISTORY_ORIGIN_DATE,
    MARKET_SECTOR_MANIFEST_VERSION,
    MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
    MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
    MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
    REGIME_HISTORY_DATASET_VERSION,
    SPLIT_ORIGIN_POLICY_VERSION,
    TICKER_HISTORY_ORIGIN_DATE,
)
from .state_engine import (
    RegimeStateBuildResult,
    _market_evidence,
    _market_thresholds,
    _score_fields,
    _sector_evidence,
    _sector_thresholds,
    _stable_hash,
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


class SplitOriginRegimeStateEngine:
    """Production market/sector writer for the accepted Gate 10 split-origin policy.

    The legacy Phase 9 ``RegimeStateEngine`` remains unchanged and reproducible.  This
    engine is the production v2 writer: market/sector thresholds are conditioned on the
    promoted daily history from 2016, while ticker/intraday policy remains explicitly
    anchored to 2021 and is materialized by ``TickerStateEngine`` separately.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calibration = RegimeCalibration(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid regime manifest: {path}") from exc

    def snapshot_path(self, as_of_date: date) -> Path:
        return self.paths.regime_state_snapshot(as_of_date)

    def manifest_path(self, as_of_date: date) -> Path:
        return self.paths.regime_state_manifest(as_of_date)

    def history_root(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return (
            root
            / "regimes"
            / "history"
            / REGIME_HISTORY_DATASET_VERSION
            / f"as_of={as_of_date}"
        )

    def history_paths(self, as_of_date: date) -> dict[str, Path]:
        root = self.history_root(as_of_date)
        return {
            "market_raw": root / "market_raw.parquet",
            "market_effective": root / "market_effective.parquet",
            "sector_raw": root / "sector_raw.parquet",
            "sector_effective": root / "sector_effective.parquet",
        }

    def _source_lineage(self, as_of_date: date) -> tuple[int, str]:
        sessions = self.calendar.sessions_in_range(MARKET_SECTOR_HISTORY_ORIGIN_DATE, as_of_date)
        if not sessions:
            raise ValueError("split-origin market/sector history produced no XNYS sessions")
        entries: list[str] = []
        missing: list[Path] = []
        for session in sessions:
            path = self.paths.feature_manifest_file(Timeframe.DAY_1, session)
            if not path.is_file():
                missing.append(path)
                continue
            manifest = FeaturePartitionManifest.from_dict(self._read_json(path))
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
        if missing:
            preview = "\n  ".join(str(path) for path in missing[:20])
            suffix = "" if len(missing) <= 20 else f"\n  ... and {len(missing) - 20} more"
            raise FileNotFoundError(
                "Split-origin regime state requires complete 1d feature manifests:\n  "
                + preview
                + suffix
            )
        return len(entries), hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()

    def _dependency(
        self,
        *,
        as_of_date: date,
        source_manifest_count: int | None = None,
        source_lineage: str | None = None,
    ) -> tuple[str, dict[str, object]]:
        if source_manifest_count is None or source_lineage is None:
            source_manifest_count, source_lineage = self._source_lineage(as_of_date)
        lineage: dict[str, object] = {
            "build_contract": GATE10_REGIME_REPLAY_BUILD_CONTRACT_VERSION,
            "split_origin_policy": SPLIT_ORIGIN_POLICY_VERSION,
            "market_sector_state_policy": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "market_sector_snapshot_contract": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "threshold_policy": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "history_origin": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_origin": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "intraday_policy": INTRADAY_POLICY,
            "threshold_training_sessions": REGIME_THRESHOLD_TRAINING_SESSIONS,
            "confirmation_sessions": REGIME_SELECTED_CONFIRMATION_SESSIONS,
            "minimum_dollar_volume": float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume),
            "market_proxies": MARKET_PROXY_TICKERS,
            "sector_proxies": SECTOR_PROXY_TICKERS,
            "as_of_date": as_of_date.isoformat(),
            "source_manifest_count": int(source_manifest_count),
            "source_lineage": str(source_lineage),
            "gate10a_source_fingerprint": MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
        }
        return _stable_hash(lineage), lineage

    def _existing(
        self,
        *,
        as_of_date: date,
        dependency: str,
        snapshot_path: Path,
        manifest_path: Path,
    ) -> dict[str, Any] | None:
        if not snapshot_path.is_file() or not manifest_path.is_file():
            return None
        try:
            manifest = self._read_json(manifest_path)
        except ValueError:
            return None
        if manifest.get("manifest_version") != MARKET_SECTOR_MANIFEST_VERSION:
            return None
        if manifest.get("snapshot_contract_version") != MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION:
            return None
        if manifest.get("state_policy_contract_version") != MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION:
            return None
        if manifest.get("dependency_fingerprint") != dependency:
            return None
        if manifest.get("snapshot_sha256") != sha256_file(snapshot_path):
            return None
        expected_history = self.history_paths(as_of_date)
        stored_history = manifest.get("history_files", {})
        if set(stored_history) != set(expected_history):
            return None
        for name, path in expected_history.items():
            entry = stored_history.get(name, {})
            if str(entry.get("path")) != str(path.resolve()):
                return None
            if not path.is_file() or entry.get("sha256") != sha256_file(path):
                return None
        return manifest

    @staticmethod
    def _write_frame(settings: AtlasSettings, frame: pd.DataFrame, path: Path, order_by: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(path)
        con = connect_utc(":memory:")
        try:
            con.register("atlas_regime_history", frame)
            compression = settings.data.parquet.compression.upper()
            row_group_size = int(settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (SELECT * FROM atlas_regime_history ORDER BY {order_by})
                TO {sql_string(str(temp))}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, path)
        finally:
            con.close()

    @staticmethod
    def _result(
        *,
        manifest: dict[str, Any],
        snapshot_path: Path,
        manifest_path: Path,
        wall_seconds: float,
        skipped: bool,
    ) -> RegimeStateBuildResult:
        return RegimeStateBuildResult(
            as_of_date=date.fromisoformat(str(manifest["as_of_date"])),
            source_manifest_count=int(manifest["source_manifest_count"]),
            usable_breadth_session_count=int(manifest["usable_breadth_session_count"]),
            evaluation_session_count=int(manifest["evaluation_session_count"]),
            sector_observation_count=int(manifest["sector_observation_count"]),
            first_evaluation_date=date.fromisoformat(str(manifest["first_evaluation_date"])),
            market_state=str(manifest["market_state"]),
            sector_state_counts={str(k): int(v) for k, v in manifest["sector_state_counts"].items()},
            dependency_fingerprint=str(manifest["dependency_fingerprint"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=wall_seconds,
            skipped=skipped,
        )

    def build(self, as_of_date: date) -> RegimeStateBuildResult:
        started = perf_counter()
        if as_of_date < MARKET_SECTOR_HISTORY_ORIGIN_DATE:
            raise ValueError("as_of_date predates the split-origin market/sector history origin")
        if not self.calendar.is_session(as_of_date):
            raise ValueError(f"{as_of_date} is not an XNYS trading session")

        source_count, source_lineage = self._source_lineage(as_of_date)
        dependency, _ = self._dependency(
            as_of_date=as_of_date,
            source_manifest_count=source_count,
            source_lineage=source_lineage,
        )
        snapshot_path = self.snapshot_path(as_of_date)
        manifest_path = self.manifest_path(as_of_date)
        existing = self._existing(
            as_of_date=as_of_date,
            dependency=dependency,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
        )
        if existing is not None:
            return self._result(
                manifest=existing,
                snapshot_path=snapshot_path,
                manifest_path=manifest_path,
                wall_seconds=perf_counter() - started,
                skipped=True,
            )

        breadth = self.calibration._breadth_daily(MARKET_SECTOR_HISTORY_ORIGIN_DATE, as_of_date)
        proxies = self.calibration._proxy_frame(MARKET_SECTOR_HISTORY_ORIGIN_DATE, as_of_date)
        raw_market, effective_market, raw_sector, effective_sector = compute_regime_state_history(
            breadth,
            proxies,
        )
        if any(frame.empty for frame in (raw_market, effective_market, raw_sector, effective_sector)):
            raise ValueError("split-origin regime policy produced no evaluable state history")

        history_paths = self.history_paths(as_of_date)
        self._write_frame(self.settings, raw_market, history_paths["market_raw"], "trading_date")
        self._write_frame(self.settings, effective_market, history_paths["market_effective"], "trading_date")
        self._write_frame(self.settings, raw_sector, history_paths["sector_raw"], "symbol, trading_date")
        self._write_frame(self.settings, effective_sector, history_paths["sector_effective"], "symbol, trading_date")

        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        market_basket = basket_daily(market_frame)
        raw_market_row = raw_market.sort_values("trading_date").iloc[-1]
        effective_market_row = effective_market.sort_values("trading_date").iloc[-1]
        if pd.Timestamp(effective_market_row["trading_date"]).date() != as_of_date:
            raise ValueError("latest split-origin market state does not match requested as-of date")

        raw_sector_sorted = raw_sector.sort_values(["symbol", "trading_date"])
        effective_sector_sorted = effective_sector.sort_values(["symbol", "trading_date"])
        sectors: dict[str, object] = {}
        sector_counts: Counter[str] = Counter()
        for ticker in SECTOR_PROXY_TICKERS:
            raw_subset = raw_sector_sorted.loc[raw_sector_sorted["symbol"] == ticker]
            effective_subset = effective_sector_sorted.loc[effective_sector_sorted["symbol"] == ticker]
            evidence_subset = sector_frame.loc[sector_frame["symbol"] == ticker].sort_values("trading_date")
            if raw_subset.empty or effective_subset.empty or evidence_subset.empty:
                raise ValueError(f"missing split-origin sector regime state for {ticker}")
            raw_row = raw_subset.iloc[-1]
            effective_row = effective_subset.iloc[-1]
            evidence_row = evidence_subset.iloc[-1]
            if pd.Timestamp(effective_row["trading_date"]).date() != as_of_date:
                raise ValueError(f"latest {ticker} split-origin state does not match {as_of_date}")
            if pd.Timestamp(evidence_row["trading_date"]).date() != as_of_date:
                raise ValueError(f"latest {ticker} evidence does not match {as_of_date}")
            effective_fields = _state_fields(effective_row, market=False)
            sector_counts.update([str(effective_fields["composite"])])
            sectors[ticker] = {
                "raw": {**_state_fields(raw_row, market=False), **_score_fields(raw_row)},
                "effective": effective_fields,
                "evidence": _sector_evidence(evidence_row),
                "thresholds": _sector_thresholds(sector_frame, ticker),
            }

        snapshot = {
            "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
            "threshold_policy_contract_version": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population_contract_version": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_history_origin_date": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "intraday_policy": INTRADAY_POLICY,
            "point_in_time_rule": POINT_IN_TIME_THRESHOLD_RULE,
            "threshold_policy": REGIME_THRESHOLD_POLICY_NAME,
            "threshold_training_sessions": REGIME_THRESHOLD_TRAINING_SESSIONS,
            "confirmation_sessions": REGIME_SELECTED_CONFIRMATION_SESSIONS,
            "minimum_dollar_volume": float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume),
            "source_manifest_count": source_count,
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
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(snapshot_path, json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
        snapshot_sha = sha256_file(snapshot_path)
        manifest = {
            "manifest_version": MARKET_SECTOR_MANIFEST_VERSION,
            "snapshot_contract_version": MARKET_SECTOR_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": MARKET_SECTOR_STATE_POLICY_CONTRACT_VERSION,
            "split_origin_policy_version": SPLIT_ORIGIN_POLICY_VERSION,
            "threshold_policy_contract_version": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population_contract_version": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "history_origin_date": MARKET_SECTOR_HISTORY_ORIGIN_DATE.isoformat(),
            "ticker_history_origin_date": TICKER_HISTORY_ORIGIN_DATE.isoformat(),
            "source_manifest_count": source_count,
            "source_lineage_fingerprint": source_lineage,
            "dependency_fingerprint": dependency,
            "gate10a_source_fingerprint": MARKET_SECTOR_POLICY_GENESIS_FINGERPRINT,
            "usable_breadth_session_count": int(len(breadth)),
            "evaluation_session_count": int(len(effective_market)),
            "sector_observation_count": int(len(effective_sector)),
            "first_evaluation_date": str(pd.Timestamp(effective_market.iloc[0]["trading_date"]).date()),
            "market_raw_rows": int(len(raw_market)),
            "market_effective_rows": int(len(effective_market)),
            "sector_raw_rows": int(len(raw_sector)),
            "sector_effective_rows": int(len(effective_sector)),
            "market_state": str(effective_market_row["composite"]),
            "sector_state_counts": dict(sorted(sector_counts.items())),
            "history_files": {
                name: {"path": str(path.resolve()), "sha256": sha256_file(path)}
                for name, path in history_paths.items()
            },
            "snapshot_path": str(snapshot_path.resolve()),
            "snapshot_sha256": snapshot_sha,
            "generated_at_utc": datetime.now(UTC).isoformat(),
        }
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(manifest_path, json.dumps(manifest, indent=2, sort_keys=True) + "\n")
        return self._result(
            manifest=manifest,
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=perf_counter() - started,
            skipped=False,
        )
