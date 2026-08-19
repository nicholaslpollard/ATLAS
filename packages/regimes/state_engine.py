from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.paths import MarketDataPaths
from packages.discovery.filter_policy import ACTIVE_DISCOVERY_FILTER_POLICY
from packages.features.partition_store import FeaturePartitionManifest, sha256_file

from .calibration import BASKET_METRICS, BREADTH_METRICS, RegimeCalibration, basket_daily
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS
from .persistence_policy import (
    REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
    REGIME_SELECTED_CONFIRMATION_SESSIONS,
)
from .persistence_probe import persist_market_states, persist_sector_states
from .threshold_policy import (
    POINT_IN_TIME_THRESHOLD_RULE,
    REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
    REGIME_HISTORY_ORIGIN_DATE,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
    REGIME_THRESHOLD_POLICY_NAME,
    REGIME_THRESHOLD_TRAINING_SESSIONS,
)
from .threshold_probe import (
    MARKET_THRESHOLD_METRICS,
    SECTOR_THRESHOLD_METRICS,
    _attach_thresholds,
    _market_point_in_time_states,
    _sector_point_in_time_states,
)


REGIME_STATE_POLICY_CONTRACT_VERSION = (
    "regime-state-policy-v1-expanding252-confirm2-dimensional"
)
REGIME_STATE_SNAPSHOT_CONTRACT_VERSION = (
    "regime-state-snapshot-v1-market-sector-proxies"
)
REGIME_STATE_MANIFEST_VERSION = "regime-state-manifest-v1-policy-source-lineage"


@dataclass(frozen=True, slots=True)
class RegimeStateBuildResult:
    as_of_date: date
    source_manifest_count: int
    usable_breadth_session_count: int
    evaluation_session_count: int
    sector_observation_count: int
    first_evaluation_date: date
    market_state: str
    sector_state_counts: dict[str, int]
    dependency_fingerprint: str
    snapshot_sha256: str
    snapshot_path: Path
    manifest_path: Path
    wall_seconds: float
    skipped: bool


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def compute_regime_state_history(
    breadth: pd.DataFrame,
    proxies: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build accepted raw/effective market and sector histories from in-memory evidence."""

    market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
    sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
    market_basket = basket_daily(market_frame)

    raw_market = _market_point_in_time_states(
        breadth,
        market_basket,
        REGIME_THRESHOLD_POLICY_NAME,
    )
    effective_market = persist_market_states(
        raw_market,
        REGIME_SELECTED_CONFIRMATION_SESSIONS,
    )
    raw_sector = _sector_point_in_time_states(
        sector_frame,
        REGIME_THRESHOLD_POLICY_NAME,
    )
    effective_sector = persist_sector_states(
        raw_sector,
        REGIME_SELECTED_CONFIRMATION_SESSIONS,
    )
    return raw_market, effective_market, raw_sector, effective_sector


def _state_fields(row: pd.Series, *, market: bool) -> dict[str, object]:
    fields: dict[str, object] = {
        "composite": str(row["composite"]),
        "structure": str(row["structure"]),
        "momentum": str(row["momentum"]),
        "volatility": str(row["volatility"]),
        "efficiency": str(row["efficiency"]),
    }
    if market:
        fields["participation"] = str(row["participation"])
    return fields


def _score_fields(row: pd.Series) -> dict[str, int]:
    return {
        "structure_score": int(row["structure_score"]),
        "momentum_score": int(row["momentum_score"]),
    }


def _thresholds_from_row(
    row: pd.Series,
    metrics: tuple[str, ...],
) -> dict[str, dict[str, float | None]]:
    result: dict[str, dict[str, float | None]] = {}
    for metric in metrics:
        values: dict[str, float | None] = {}
        for quantile in ("p25", "p75", "p90"):
            key = f"{metric}__{quantile}"
            if key in row.index:
                values[quantile] = None if pd.isna(row[key]) else float(row[key])
        result[metric] = values
    return result


def _market_thresholds(
    breadth: pd.DataFrame,
    market_basket: pd.DataFrame,
) -> dict[str, dict[str, float | None]]:
    left = breadth.copy()
    right = market_basket.copy()
    left["trading_date"] = pd.to_datetime(left["trading_date"]).dt.date
    right["trading_date"] = pd.to_datetime(right["trading_date"]).dt.date
    joined = left.merge(right, on="trading_date", how="inner", validate="one_to_one")
    joined = joined.sort_values("trading_date").reset_index(drop=True)
    attached = _attach_thresholds(joined, MARKET_THRESHOLD_METRICS, REGIME_THRESHOLD_POLICY_NAME)
    if attached.empty:
        return {}
    return _thresholds_from_row(attached.iloc[-1], MARKET_THRESHOLD_METRICS)


def _sector_thresholds(
    sector_frame: pd.DataFrame,
    ticker: str,
) -> dict[str, dict[str, float | None]]:
    subset = sector_frame.loc[sector_frame["symbol"] == ticker].sort_values("trading_date").reset_index(drop=True)
    if subset.empty:
        return {}
    attached = _attach_thresholds(subset, SECTOR_THRESHOLD_METRICS, REGIME_THRESHOLD_POLICY_NAME)
    return _thresholds_from_row(attached.iloc[-1], SECTOR_THRESHOLD_METRICS)


def _market_evidence(
    breadth: pd.DataFrame,
    market_basket: pd.DataFrame,
    as_of_date: date,
) -> dict[str, object]:
    breadth_dates = pd.to_datetime(breadth["trading_date"]).dt.date
    basket_dates = pd.to_datetime(market_basket["trading_date"]).dt.date
    broad = breadth.loc[breadth_dates == as_of_date]
    basket = market_basket.loc[basket_dates == as_of_date]
    if broad.empty or basket.empty:
        raise ValueError(f"missing end-date market evidence for {as_of_date}")
    broad_row = broad.iloc[-1]
    basket_row = basket.iloc[-1]
    return {
        "participant_count": int(broad_row["participant_count"]),
        "breadth": {metric: float(broad_row[metric]) for metric in BREADTH_METRICS},
        "market_basket": {metric: float(basket_row[metric]) for metric in BASKET_METRICS},
    }


def _sector_evidence(row: pd.Series) -> dict[str, float]:
    metrics = (
        "close",
        "ema_50",
        "ema_200",
        "return_1",
        "price_distance_ema_20",
        "ema_20_slope_1",
        "rsi_14",
        "macd_hist_12_26_9",
        "natr_14",
        "realized_volatility_20",
        "directional_efficiency_20",
    )
    return {metric: float(row[metric]) for metric in metrics}


class RegimeStateEngine:
    """Materialize the accepted market + sector-proxy regime state for one session.

    The engine intentionally replays from the versioned historical origin.  That keeps
    the as-of output deterministic and makes the two-session confirmation state exactly
    reproducible without depending on a mutable in-process cache.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calibration = RegimeCalibration(settings)
        self.calendar = get_market_calendar()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON manifest: {path}") from exc

    def _source_lineage(self, as_of_date: date) -> tuple[int, str]:
        sessions = self.calendar.sessions_in_range(REGIME_HISTORY_ORIGIN_DATE, as_of_date)
        if not sessions:
            raise ValueError("regime history origin produced no XNYS sessions")
        entries: list[str] = []
        missing: list[Path] = []
        for session in sessions:
            path = self.paths.feature_manifest_file(Timeframe.DAY_1, session)
            if not path.is_file():
                missing.append(path)
                continue
            payload = self._read_json(path)
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
        if missing:
            preview = "\n  ".join(str(path) for path in missing[:20])
            suffix = "" if len(missing) <= 20 else f"\n  ... and {len(missing) - 20} more"
            raise FileNotFoundError(
                "Regime state materialization requires complete 1d feature manifests:\n  "
                + preview
                + suffix
            )
        return len(entries), hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest()

    def _dependency(self, *, as_of_date: date, source_lineage: str) -> str:
        return _stable_hash(
            {
                "state_policy": REGIME_STATE_POLICY_CONTRACT_VERSION,
                "snapshot_contract": REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
                "threshold_policy": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
                "persistence_policy": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
                "breadth_population": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
                "history_origin": REGIME_HISTORY_ORIGIN_DATE.isoformat(),
                "threshold_training_sessions": REGIME_THRESHOLD_TRAINING_SESSIONS,
                "confirmation_sessions": REGIME_SELECTED_CONFIRMATION_SESSIONS,
                "minimum_dollar_volume": float(ACTIVE_DISCOVERY_FILTER_POLICY.minimum_dollar_volume),
                "market_proxies": MARKET_PROXY_TICKERS,
                "sector_proxies": SECTOR_PROXY_TICKERS,
                "as_of_date": as_of_date.isoformat(),
                "source_lineage": source_lineage,
            }
        )

    def _existing(
        self,
        *,
        snapshot_path: Path,
        manifest_path: Path,
        dependency: str,
    ) -> dict[str, Any] | None:
        if not snapshot_path.is_file() or not manifest_path.is_file():
            return None
        try:
            manifest = self._read_json(manifest_path)
        except ValueError:
            return None
        if manifest.get("manifest_version") != REGIME_STATE_MANIFEST_VERSION:
            return None
        if manifest.get("snapshot_contract_version") != REGIME_STATE_SNAPSHOT_CONTRACT_VERSION:
            return None
        if manifest.get("dependency_fingerprint") != dependency:
            return None
        return manifest if manifest.get("snapshot_sha256") == sha256_file(snapshot_path) else None

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
        if as_of_date < REGIME_HISTORY_ORIGIN_DATE:
            raise ValueError("as_of_date predates the locked regime history origin")
        if not self.calendar.is_session(as_of_date):
            raise ValueError(f"{as_of_date} is not an XNYS trading session")

        source_count, source_lineage = self._source_lineage(as_of_date)
        dependency = self._dependency(as_of_date=as_of_date, source_lineage=source_lineage)
        snapshot_path = self.paths.regime_state_snapshot(as_of_date)
        manifest_path = self.paths.regime_state_manifest(as_of_date)
        existing = self._existing(
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            dependency=dependency,
        )
        if existing is not None:
            return self._result(
                manifest=existing,
                snapshot_path=snapshot_path,
                manifest_path=manifest_path,
                wall_seconds=perf_counter() - started,
                skipped=True,
            )

        breadth = self.calibration._breadth_daily(REGIME_HISTORY_ORIGIN_DATE, as_of_date)
        proxies = self.calibration._proxy_frame(REGIME_HISTORY_ORIGIN_DATE, as_of_date)
        raw_market, effective_market, raw_sector, effective_sector = compute_regime_state_history(
            breadth,
            proxies,
        )
        if raw_market.empty or effective_market.empty or raw_sector.empty or effective_sector.empty:
            raise ValueError("accepted regime policy produced no evaluable state history")

        market_frame = proxies.loc[proxies["symbol"].isin(MARKET_PROXY_TICKERS)].copy()
        sector_frame = proxies.loc[proxies["symbol"].isin(SECTOR_PROXY_TICKERS)].copy()
        market_basket = basket_daily(market_frame)

        raw_market_row = raw_market.iloc[-1]
        effective_market_row = effective_market.iloc[-1]
        market_date = pd.Timestamp(effective_market_row["trading_date"]).date()
        if market_date != as_of_date:
            raise ValueError(
                f"latest market regime state is {market_date}, expected requested as-of {as_of_date}"
            )

        raw_sector_sorted = raw_sector.sort_values(["symbol", "trading_date"])
        effective_sector_sorted = effective_sector.sort_values(["symbol", "trading_date"])
        sectors: dict[str, object] = {}
        sector_counts: Counter[str] = Counter()
        for ticker in SECTOR_PROXY_TICKERS:
            raw_subset = raw_sector_sorted.loc[raw_sector_sorted["symbol"] == ticker]
            effective_subset = effective_sector_sorted.loc[effective_sector_sorted["symbol"] == ticker]
            evidence_subset = sector_frame.loc[sector_frame["symbol"] == ticker].sort_values("trading_date")
            if raw_subset.empty or effective_subset.empty or evidence_subset.empty:
                raise ValueError(f"missing accepted sector regime state for {ticker}")
            raw_row = raw_subset.iloc[-1]
            effective_row = effective_subset.iloc[-1]
            evidence_row = evidence_subset.iloc[-1]
            effective_date = pd.Timestamp(effective_row["trading_date"]).date()
            evidence_date = pd.Timestamp(evidence_row["trading_date"]).date()
            if effective_date != as_of_date or evidence_date != as_of_date:
                raise ValueError(f"latest {ticker} regime evidence does not match {as_of_date}")
            effective_fields = _state_fields(effective_row, market=False)
            sector_counts.update([str(effective_fields["composite"])])
            sectors[ticker] = {
                "raw": {**_state_fields(raw_row, market=False), **_score_fields(raw_row)},
                "effective": effective_fields,
                "evidence": _sector_evidence(evidence_row),
                "thresholds": _sector_thresholds(sector_frame, ticker),
            }

        snapshot = {
            "snapshot_contract_version": REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": REGIME_STATE_POLICY_CONTRACT_VERSION,
            "threshold_policy_contract_version": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population_contract_version": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "history_origin_date": REGIME_HISTORY_ORIGIN_DATE.isoformat(),
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
                "raw": {
                    **_state_fields(raw_market_row, market=True),
                    **_score_fields(raw_market_row),
                },
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
            "manifest_version": REGIME_STATE_MANIFEST_VERSION,
            "snapshot_contract_version": REGIME_STATE_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": REGIME_STATE_POLICY_CONTRACT_VERSION,
            "threshold_policy_contract_version": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": REGIME_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "breadth_population_contract_version": REGIME_BREADTH_POPULATION_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "history_origin_date": REGIME_HISTORY_ORIGIN_DATE.isoformat(),
            "source_manifest_count": source_count,
            "source_lineage_fingerprint": source_lineage,
            "usable_breadth_session_count": int(len(breadth)),
            "evaluation_session_count": int(len(effective_market)),
            "sector_observation_count": int(len(effective_sector)),
            "first_evaluation_date": str(pd.Timestamp(effective_market.iloc[0]["trading_date"]).date()),
            "market_state": str(effective_market_row["composite"]),
            "sector_state_counts": dict(sorted(sector_counts.items())),
            "dependency_fingerprint": dependency,
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
