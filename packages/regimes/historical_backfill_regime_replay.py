from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.alpaca_backfill_policy import ALPACA_BACKFILL_START
from packages.data.alpaca_backfill_validated_evidence import stable_source_fingerprint
from packages.data.paths import MarketDataPaths
from packages.features.historical_backfill_feature_handoff_runtime import (
    HistoricalBackfillDailyFeatureHandoffRuntimeValidator,
)
from packages.features.partition_store import FeaturePartitionManifest

from .calibration import RegimeCalibration
from .input_inventory import MARKET_PROXY_TICKERS, SECTOR_PROXY_TICKERS
from .state_engine import (
    REGIME_STATE_POLICY_CONTRACT_VERSION,
    RegimeStateEngine,
    compute_regime_state_history,
)
from .threshold_policy import (
    REGIME_HISTORY_ORIGIN_DATE,
    REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
)
from .ticker_state_engine import (
    TICKER_STATE_POLICY_CONTRACT_VERSION,
    TickerStateEngine,
)


GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION = (
    "historical-backfill-regime-replay-preflight-v1-split-market-sector-daily-origin-ticker-intraday-origin"
)
GATE10_REGIME_REPLAY_ROLE = "READ_ONLY_REGIME_REPLAY_FEASIBILITY_NO_PRODUCTION_WRITES"
GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN = ALPACA_BACKFILL_START
GATE10_TICKER_ORIGIN = REGIME_HISTORY_ORIGIN_DATE
GATE10_INTRADAY_POLICY = "NO_SYNTHETIC_PRE2021_4H_OR_1H_FROM_DAILY_BACKFILL"

_MARKET_STATE_COLUMNS = (
    "composite",
    "structure",
    "momentum",
    "volatility",
    "efficiency",
    "participation",
)
_SECTOR_STATE_COLUMNS = (
    "composite",
    "structure",
    "momentum",
    "volatility",
    "efficiency",
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _date_value(value: object) -> date:
    return pd.Timestamp(value).date()


def _frame_date_range(frame: pd.DataFrame) -> tuple[str | None, str | None]:
    if frame.empty:
        return None, None
    values = pd.to_datetime(frame["trading_date"]).dt.date
    return min(values).isoformat(), max(values).isoformat()


def state_overlap_diagnostics(
    candidate: pd.DataFrame,
    baseline: pd.DataFrame,
    *,
    key_columns: tuple[str, ...],
    state_columns: tuple[str, ...],
) -> dict[str, object]:
    """Compare state histories on exact shared keys without assuming equality."""

    columns = list(key_columns + state_columns)
    left = candidate.loc[:, columns].copy()
    right = baseline.loc[:, columns].copy()
    if "trading_date" in key_columns:
        left["trading_date"] = pd.to_datetime(left["trading_date"]).dt.date
        right["trading_date"] = pd.to_datetime(right["trading_date"]).dt.date
    joined = left.merge(right, on=list(key_columns), how="inner", suffixes=("_candidate", "_baseline"))
    if joined.empty:
        return {
            "overlap_rows": 0,
            "changed_rows": 0,
            "unchanged_rows": 0,
            "change_rate": None,
            "dimension_change_counts": {column: 0 for column in state_columns},
        }
    dimension_counts: dict[str, int] = {}
    changed = pd.Series(False, index=joined.index)
    for column in state_columns:
        mask = joined[f"{column}_candidate"].astype(str) != joined[f"{column}_baseline"].astype(str)
        dimension_counts[column] = int(mask.sum())
        changed |= mask
    changed_rows = int(changed.sum())
    overlap_rows = len(joined)
    return {
        "overlap_rows": overlap_rows,
        "changed_rows": changed_rows,
        "unchanged_rows": overlap_rows - changed_rows,
        "change_rate": changed_rows / overlap_rows,
        "dimension_change_counts": dimension_counts,
    }


def sector_first_dates(frame: pd.DataFrame) -> dict[str, str | None]:
    """Return the first evaluable state date for every accepted sector proxy."""

    result: dict[str, str | None] = {symbol: None for symbol in SECTOR_PROXY_TICKERS}
    if frame.empty:
        return result
    data = frame.copy()
    data["trading_date"] = pd.to_datetime(data["trading_date"]).dt.date
    for symbol, subset in data.groupby("symbol", observed=True, sort=True):
        text = str(symbol)
        if text in result and not subset.empty:
            result[text] = min(subset["trading_date"]).isoformat()
    return result


def feature_manifest_inventory(
    settings: AtlasSettings,
    timeframe: Timeframe,
) -> dict[str, object]:
    """Inventory the live production manifest chain for one permanent timeframe."""

    root = settings.resolved_path(settings.data.paths.manifests) / "features" / timeframe.value
    rows: list[dict[str, str]] = []
    invalid = 0
    for path in sorted(root.glob("*/*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            manifest = FeaturePartitionManifest.from_dict(payload)
            session = date.fromisoformat(str(manifest.trading_date))
            manifest.validate_contract(timeframe, session)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            invalid += 1
            continue
        rows.append(
            {
                "session_date": session.isoformat(),
                "feature_sha256": str(manifest.feature_sha256),
                "dependency_fingerprint": str(manifest.dependency_fingerprint),
            }
        )
    dates = [date.fromisoformat(row["session_date"]) for row in rows]
    lineage = "\n".join(
        f"{row['session_date']}:{row['feature_sha256']}:{row['dependency_fingerprint']}"
        for row in rows
    )
    return {
        "timeframe": timeframe.value,
        "manifest_count": len(rows),
        "invalid_manifests": invalid,
        "first_session": min(dates).isoformat() if dates else None,
        "last_session": max(dates).isoformat() if dates else None,
        "sessions": [value.isoformat() for value in dates],
        "lineage_fingerprint": _sha256_text(lineage),
    }


def _coverage_complete(
    calendar: Any,
    inventory: dict[str, object],
    start_date: date,
    end_date: date,
) -> bool:
    expected = {value.isoformat() for value in calendar.sessions_in_range(start_date, end_date)}
    actual = set(str(value) for value in inventory["sessions"])
    return actual == expected and int(inventory["invalid_manifests"]) == 0


def _latest_manifest_status(
    *,
    manifest_path: Path,
    expected_dependency: str,
) -> dict[str, object]:
    if not manifest_path.is_file():
        return {
            "present": False,
            "stored_dependency_fingerprint": None,
            "expected_dependency_fingerprint": expected_dependency,
            "current": False,
        }
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "present": True,
            "stored_dependency_fingerprint": None,
            "expected_dependency_fingerprint": expected_dependency,
            "current": False,
        }
    stored = payload.get("dependency_fingerprint")
    return {
        "present": True,
        "stored_dependency_fingerprint": stored,
        "expected_dependency_fingerprint": expected_dependency,
        "current": stored == expected_dependency,
    }


def _state_tail(frame: pd.DataFrame, *, sector: bool) -> object:
    if frame.empty:
        return None
    data = frame.copy()
    data["trading_date"] = pd.to_datetime(data["trading_date"]).dt.date
    if not sector:
        row = data.sort_values("trading_date").iloc[-1]
        return {
            "trading_date": row["trading_date"].isoformat(),
            **{column: str(row[column]) for column in _MARKET_STATE_COLUMNS},
        }
    result: dict[str, object] = {}
    for symbol, subset in data.groupby("symbol", observed=True, sort=True):
        row = subset.sort_values("trading_date").iloc[-1]
        result[str(symbol)] = {
            "trading_date": row["trading_date"].isoformat(),
            **{column: str(row[column]) for column in _SECTOR_STATE_COLUMNS},
        }
    return result


class HistoricalBackfillRegimeReplayPreflight:
    """Gate 10-A evidence for versioning regime replay after the daily backfill.

    Market/sector evidence is replayed in memory from the new daily-history origin.
    Ticker regimes remain anchored to the existing Massive-era intraday boundary because
    the accepted ticker classifier requires 1d + 4h + 1h evidence and no pre-2021
    intraday bars were fabricated by the historical daily backfill.
    """

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        self.calibration = RegimeCalibration(settings)
        self.regime_engine = RegimeStateEngine(settings)
        self.ticker_engine = TickerStateEngine(settings)
        self.gate9c_validator = HistoricalBackfillDailyFeatureHandoffRuntimeValidator(settings)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "historical_backfill" / "alpaca" / "regime_replay" / "v1"
        self.report_path = self.root / "gate10_preflight_report.json"

    def _artifact_inventory(self) -> dict[str, int]:
        derived = self.settings.resolved_path(self.settings.data.paths.derived)
        manifests = self.settings.resolved_path(self.settings.data.paths.manifests)
        return {
            "market_sector_snapshots": len(list((derived / "regimes" / "states").glob("*/*.json"))),
            "market_sector_manifests": len(list((manifests / "regimes").glob("[0-9][0-9][0-9][0-9]/*.json"))),
            "ticker_snapshots": len(list((derived / "regimes" / "ticker_states").glob("year=*/date=*/part-000.parquet"))),
            "ticker_manifests": len(list((manifests / "regimes" / "ticker_states").glob("*/*.json"))),
        }

    @staticmethod
    def _gate9c_fingerprint(report: dict[str, object]) -> str:
        value = report.get("handoff_source_fingerprint") or report.get("source_fingerprint")
        if value:
            return str(value)
        raise RuntimeError("Gate 10-A cannot resolve the accepted Gate 9-C handoff fingerprint")

    def _accepted_gate9c_writer(self, gate9c_fingerprint: str) -> dict[str, Any]:
        writer_path = self.gate9c_validator.handoff.report_path
        if not writer_path.is_file():
            raise RuntimeError(f"Gate 10-A requires Gate 9-C writer report: {writer_path}")
        try:
            report = json.loads(writer_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Gate 10-A cannot read Gate 9-C writer report: {writer_path}") from exc
        writer_fingerprint = str(report.get("source_fingerprint") or "")
        if not writer_fingerprint or writer_fingerprint != gate9c_fingerprint:
            raise RuntimeError(
                "Gate 10-A Gate 9-C writer/validator handoff fingerprints do not match"
            )
        last_session = report.get("last_session")
        if not last_session:
            raise RuntimeError("Gate 10-A Gate 9-C writer report lacks last_session")
        date.fromisoformat(str(last_session))
        return report

    def run(self) -> dict[str, object]:
        gate9c = self.gate9c_validator.run()
        if gate9c.get("pass") is not True:
            raise RuntimeError("Gate 10-A requires current passing Gate 9-C production validation")
        gate9c_fp = self._gate9c_fingerprint(gate9c)
        gate9c_writer = self._accepted_gate9c_writer(gate9c_fp)

        as_of_date = date.fromisoformat(str(gate9c_writer["last_session"]))
        daily = feature_manifest_inventory(self.settings, Timeframe.DAY_1)
        hour4 = feature_manifest_inventory(self.settings, Timeframe.HOUR_4)
        hour1 = feature_manifest_inventory(self.settings, Timeframe.HOUR_1)

        breadth = self.calibration._breadth_daily(GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date)
        proxies = self.calibration._proxy_frame(GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date)
        candidate_raw_market, candidate_effective_market, candidate_raw_sector, candidate_effective_sector = (
            compute_regime_state_history(breadth, proxies)
        )

        old_dates = pd.to_datetime(breadth["trading_date"]).dt.date >= GATE10_TICKER_ORIGIN
        old_breadth = breadth.loc[old_dates].copy()
        old_proxy_dates = pd.to_datetime(proxies["trading_date"]).dt.date >= GATE10_TICKER_ORIGIN
        old_proxies = proxies.loc[old_proxy_dates].copy()
        old_raw_market, old_effective_market, old_raw_sector, old_effective_sector = (
            compute_regime_state_history(old_breadth, old_proxies)
        )

        market_overlap = state_overlap_diagnostics(
            candidate_effective_market,
            old_effective_market,
            key_columns=("trading_date",),
            state_columns=_MARKET_STATE_COLUMNS,
        )
        sector_overlap = state_overlap_diagnostics(
            candidate_effective_sector,
            old_effective_sector,
            key_columns=("symbol", "trading_date"),
            state_columns=_SECTOR_STATE_COLUMNS,
        )

        market_candidate_range = _frame_date_range(candidate_effective_market)
        market_old_range = _frame_date_range(old_effective_market)
        sector_candidate_range = _frame_date_range(candidate_effective_sector)
        sector_old_range = _frame_date_range(old_effective_sector)
        breadth_range = _frame_date_range(breadth)
        proxy_range = _frame_date_range(proxies)

        source_count, source_lineage = self.regime_engine._source_lineage(as_of_date)
        regime_dependency = self.regime_engine._dependency(
            as_of_date=as_of_date,
            source_lineage=source_lineage,
        )
        market_manifest_status = _latest_manifest_status(
            manifest_path=self.paths.regime_state_manifest(as_of_date),
            expected_dependency=regime_dependency,
        )
        ticker_dependency, ticker_lineage = self.ticker_engine._dependency(as_of_date)
        ticker_manifest_status = _latest_manifest_status(
            manifest_path=self.ticker_engine.manifest_path(as_of_date),
            expected_dependency=ticker_dependency,
        )

        artifacts = self._artifact_inventory()
        source_fp = stable_source_fingerprint(
            {
                "contract_version": GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION,
                "role": GATE10_REGIME_REPLAY_ROLE,
                "gate9c_handoff_source_fingerprint": gate9c_fp,
                "candidate_market_sector_origin": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
                "ticker_origin": GATE10_TICKER_ORIGIN.isoformat(),
                "intraday_policy": GATE10_INTRADAY_POLICY,
                "regime_threshold_policy": REGIME_THRESHOLD_POLICY_CONTRACT_VERSION,
                "regime_state_policy": REGIME_STATE_POLICY_CONTRACT_VERSION,
                "ticker_state_policy": TICKER_STATE_POLICY_CONTRACT_VERSION,
                "daily_lineage": daily["lineage_fingerprint"],
                "hour4_lineage": hour4["lineage_fingerprint"],
                "hour1_lineage": hour1["lineage_fingerprint"],
                "market_proxies": MARKET_PROXY_TICKERS,
                "sector_proxies": SECTOR_PROXY_TICKERS,
                "as_of_date": as_of_date.isoformat(),
            }
        )

        proxy_latest: dict[str, str | None] = {}
        if not proxies.empty:
            proxy_data = proxies.copy()
            proxy_data["trading_date"] = pd.to_datetime(proxy_data["trading_date"]).dt.date
            for symbol in MARKET_PROXY_TICKERS + SECTOR_PROXY_TICKERS:
                subset = proxy_data.loc[proxy_data["symbol"] == symbol]
                proxy_latest[symbol] = (
                    max(subset["trading_date"]).isoformat() if not subset.empty else None
                )

        checks = {
            "preflight_contract": True,
            "gate9c_production_validation_pass": gate9c.get("pass") is True,
            "gate9c_writer_handoff_fingerprint_exact": str(
                gate9c_writer["source_fingerprint"]
            )
            == gate9c_fp,
            "candidate_market_sector_origin_is_daily_backfill_origin": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN == ALPACA_BACKFILL_START,
            "ticker_origin_remains_massive_intraday_origin": GATE10_TICKER_ORIGIN == date(2021, 8, 16),
            "daily_manifest_coverage_complete": _coverage_complete(
                self.calendar, daily, GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN, as_of_date
            ),
            "hour4_manifest_coverage_complete_from_ticker_origin": _coverage_complete(
                self.calendar, hour4, GATE10_TICKER_ORIGIN, as_of_date
            ),
            "hour1_manifest_coverage_complete_from_ticker_origin": _coverage_complete(
                self.calendar, hour1, GATE10_TICKER_ORIGIN, as_of_date
            ),
            "no_preorigin_hour4_manifests": hour4["first_session"] == GATE10_TICKER_ORIGIN.isoformat(),
            "no_preorigin_hour1_manifests": hour1["first_session"] == GATE10_TICKER_ORIGIN.isoformat(),
            "candidate_market_history_nonempty": not candidate_effective_market.empty,
            "candidate_sector_history_nonempty": not candidate_effective_sector.empty,
            "all_sector_proxies_evaluable": all(
                value is not None for value in sector_first_dates(candidate_effective_sector).values()
            ),
            "all_proxies_current_at_asof": all(
                proxy_latest.get(symbol) == as_of_date.isoformat()
                for symbol in MARKET_PROXY_TICKERS + SECTOR_PROXY_TICKERS
            ),
            "old_origin_comparison_nonempty": not old_effective_market.empty
            and not old_effective_sector.empty,
            "ticker_pre2021_extension_blocked_by_intraday_boundary": hour4["first_session"] == GATE10_TICKER_ORIGIN.isoformat()
            and hour1["first_session"] == GATE10_TICKER_ORIGIN.isoformat(),
            "latest_market_sector_dependency_recomputed": source_count > 0
            and market_manifest_status["present"] is True,
            "latest_ticker_dependency_recomputed": int(ticker_lineage["feature_manifest_count"]) > 0
            and ticker_manifest_status["present"] is True,
            "production_regime_writes_zero": True,
        }

        report: dict[str, object] = {
            "contract_version": GATE10_REGIME_REPLAY_PREFLIGHT_CONTRACT_VERSION,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "role": GATE10_REGIME_REPLAY_ROLE,
            "source_fingerprint": source_fp,
            "gate9c_handoff_source_fingerprint": gate9c_fp,
            "gate9c_writer_report_path": str(self.gate9c_validator.handoff.report_path),
            "as_of_date": as_of_date.isoformat(),
            "current_phase9_origin": REGIME_HISTORY_ORIGIN_DATE.isoformat(),
            "candidate_market_sector_origin": GATE10_MARKET_SECTOR_CANDIDATE_ORIGIN.isoformat(),
            "ticker_origin": GATE10_TICKER_ORIGIN.isoformat(),
            "intraday_policy": GATE10_INTRADAY_POLICY,
            "feature_manifest_coverage": {
                "1d": {key: value for key, value in daily.items() if key != "sessions"},
                "4h": {key: value for key, value in hour4.items() if key != "sessions"},
                "1h": {key: value for key, value in hour1.items() if key != "sessions"},
            },
            "candidate_market_sector_replay": {
                "usable_breadth_sessions": len(breadth),
                "breadth_first_session": breadth_range[0],
                "breadth_last_session": breadth_range[1],
                "proxy_observations": len(proxies),
                "proxy_first_session": proxy_range[0],
                "proxy_last_session": proxy_range[1],
                "market_raw_rows": len(candidate_raw_market),
                "market_effective_rows": len(candidate_effective_market),
                "market_first_evaluation": market_candidate_range[0],
                "market_last_evaluation": market_candidate_range[1],
                "sector_raw_rows": len(candidate_raw_sector),
                "sector_effective_rows": len(candidate_effective_sector),
                "sector_first_evaluation": sector_candidate_range[0],
                "sector_last_evaluation": sector_candidate_range[1],
                "sector_first_dates": sector_first_dates(candidate_effective_sector),
                "proxy_latest_dates": proxy_latest,
                "market_end_state": _state_tail(candidate_effective_market, sector=False),
                "sector_end_states": _state_tail(candidate_effective_sector, sector=True),
            },
            "current_origin_replay_with_new_features": {
                "market_raw_rows": len(old_raw_market),
                "market_effective_rows": len(old_effective_market),
                "market_first_evaluation": market_old_range[0],
                "market_last_evaluation": market_old_range[1],
                "sector_raw_rows": len(old_raw_sector),
                "sector_effective_rows": len(old_effective_sector),
                "sector_first_evaluation": sector_old_range[0],
                "sector_last_evaluation": sector_old_range[1],
                "market_end_state": _state_tail(old_effective_market, sector=False),
                "sector_end_states": _state_tail(old_effective_sector, sector=True),
            },
            "overlap_change_diagnostics": {
                "market": market_overlap,
                "sector": sector_overlap,
            },
            "existing_artifacts": {
                **artifacts,
                "latest_market_sector_manifest": market_manifest_status,
                "latest_ticker_manifest": ticker_manifest_status,
            },
            "production_regime_writes": 0,
            "checks": checks,
            "pass": all(checks.values()),
            "report_path": str(self.report_path),
        }
        atomic_write_text(
            self.report_path,
            json.dumps(report, indent=2, sort_keys=True) + "\n",
        )
        return report
