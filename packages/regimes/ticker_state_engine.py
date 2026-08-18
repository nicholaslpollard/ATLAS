from __future__ import annotations

import hashlib
import json
import math
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
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.partition_store import FeaturePartitionManifest, sha256_file

from .persistence_probe import confirm_states
from .threshold_policy import REGIME_HISTORY_ORIGIN_DATE
from .ticker_history_probe import (
    AUTHORITATIVE_CURRENT_INTERVAL,
    CURRENT_ALIAS_NO_CONFLICT,
    TickerHistoryProbe,
    history_status,
    operational_history_depth,
)
from .ticker_persistence_policy import (
    TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION,
    TICKER_SELECTED_CONFIRMATION_SESSIONS,
)
from .ticker_persistence_probe import TickerPersistenceProbe
from .ticker_probe import (
    TickerRegimeProbe,
    candidate_ticker_state,
    daily_structure_state,
    intraday_direction_state,
    short_alignment_state,
    ticker_momentum_state,
)
from .ticker_risk_policy import (
    TICKER_RISK_MODE_FULL,
    TICKER_RISK_MODE_IDENTITY_BLOCKED,
    TICKER_RISK_MODE_INSUFFICIENT,
    TICKER_RISK_MODE_NO_CURRENT_METRICS,
    TICKER_RISK_MODE_PROVISIONAL,
    TICKER_RISK_POLICY_CONTRACT_VERSION,
    ticker_risk_history_mode,
    ticker_risk_selected_window,
)
from .ticker_risk_probe import (
    TickerRiskProbe,
    self_relative_efficiency_state,
    self_relative_volatility_state,
)


TICKER_STATE_POLICY_CONTRACT_VERSION = (
    "ticker-state-policy-v1-confirm2-dimensional-risk126-60"
)
TICKER_STATE_SNAPSHOT_CONTRACT_VERSION = (
    "ticker-state-snapshot-v1-routed-identity-persistence-risk"
)
TICKER_STATE_MANIFEST_VERSION = "ticker-state-manifest-v1-policy-lineage"

PERSISTENCE_CONFIRMED = "CONFIRMED_2_SESSION"
PERSISTENCE_CURRENT_ONLY_BLOCKED = "CURRENT_ONLY_IDENTITY_BLOCKED"
PERSISTENCE_CURRENT_ONLY_SHALLOW = "CURRENT_ONLY_SHALLOW_HISTORY"
PERSISTENCE_NO_CURRENT_STATE = "NO_CURRENT_STATE"

_CURRENT_DAILY_COLUMNS = (
    "close_1d",
    "ema20_1d",
    "ema50_1d",
    "ema200_1d",
    "return1_1d",
    "rsi_1d",
    "macd_hist_1d",
    "ema20_slope_1d",
)
_CURRENT_H4_COLUMNS = (
    "close_4h",
    "ema20_4h",
    "ema50_4h",
    "rsi_4h",
    "macd_hist_4h",
    "ema20_slope_4h",
)
_CURRENT_H1_COLUMNS = (
    "close_1h",
    "ema20_1h",
    "ema50_1h",
    "rsi_1h",
    "macd_hist_1h",
    "ema20_slope_1h",
)


@dataclass(frozen=True, slots=True)
class TickerStateBuildResult:
    as_of_date: date
    record_count: int
    raw_state_available_count: int
    confirmed_persistence_count: int
    risk_mode_counts: dict[str, int]
    persistence_status_counts: dict[str, int]
    history_status_counts: dict[str, int]
    effective_state_counts: dict[str, int]
    dependency_fingerprint: str
    snapshot_sha256: str
    snapshot_path: Path
    manifest_path: Path
    wall_seconds: float
    skipped: bool


def _fingerprint(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _relation_vote(left: float, right: float) -> int:
    if left > right:
        return 1
    if left < right:
        return -1
    return 0


def _finite_row(row: pd.Series, columns: tuple[str, ...]) -> bool:
    for column in columns:
        value = row.get(column)
        if pd.isna(value):
            return False
        try:
            if not math.isfinite(float(value)):
                return False
        except (TypeError, ValueError):
            return False
    return True


def classify_current_ticker_dimensions(row: pd.Series) -> dict[str, str] | None:
    """Classify the accepted raw ticker dimensions from one current feature row."""

    if not _finite_row(row, _CURRENT_DAILY_COLUMNS + _CURRENT_H4_COLUMNS + _CURRENT_H1_COLUMNS):
        return None

    structure_score = sum(
        (
            _relation_vote(float(row["close_1d"]), float(row["ema20_1d"])),
            _relation_vote(float(row["close_1d"]), float(row["ema50_1d"])),
            _relation_vote(float(row["close_1d"]), float(row["ema200_1d"])),
            _relation_vote(float(row["ema20_1d"]), float(row["ema50_1d"])),
            _relation_vote(float(row["ema50_1d"]), float(row["ema200_1d"])),
            _relation_vote(float(row["ema20_slope_1d"]), 0.0),
        )
    )
    structure = daily_structure_state(structure_score)

    score_4h = sum(
        (
            _relation_vote(float(row["close_4h"]), float(row["ema20_4h"])),
            _relation_vote(float(row["close_4h"]), float(row["ema50_4h"])),
            _relation_vote(float(row["rsi_4h"]), 50.0),
            _relation_vote(float(row["macd_hist_4h"]), 0.0),
            _relation_vote(float(row["ema20_slope_4h"]), 0.0),
        )
    )
    score_1h = sum(
        (
            _relation_vote(float(row["close_1h"]), float(row["ema20_1h"])),
            _relation_vote(float(row["close_1h"]), float(row["ema50_1h"])),
            _relation_vote(float(row["rsi_1h"]), 50.0),
            _relation_vote(float(row["macd_hist_1h"]), 0.0),
            _relation_vote(float(row["ema20_slope_1h"]), 0.0),
        )
    )
    direction_4h = intraday_direction_state(score_4h)
    direction_1h = intraday_direction_state(score_1h)
    alignment = short_alignment_state(direction_4h, direction_1h)
    momentum = ticker_momentum_state(
        return_1=float(row["return1_1d"]),
        rsi_14=float(row["rsi_1d"]),
        macd_hist=float(row["macd_hist_1d"]),
    )
    state = candidate_ticker_state(
        daily_structure=structure,
        short_alignment=alignment,
        momentum=momentum,
    )
    return {
        "daily_structure": structure,
        "short_alignment": alignment,
        "momentum": momentum,
        "ticker_state": state,
    }


def persisted_current_dimensions(
    frame: pd.DataFrame,
    *,
    as_of_date: date,
    session_ordinals: dict[date, int],
) -> dict[str, dict[str, str]]:
    """Replay accepted dimensional confirmation and return exact-as-of states."""

    result: dict[str, dict[str, str]] = {}
    if frame.empty:
        return result

    for instrument_id, subset in frame.groupby("instrument_id", sort=True, observed=True):
        data = subset.sort_values("trading_date").reset_index(drop=True)
        dates = pd.to_datetime(data["trading_date"]).dt.date.tolist()
        if not dates or dates[-1] != as_of_date:
            continue

        segment_start = 0
        previous_ordinal: int | None = None
        for index, trading_date in enumerate(dates):
            ordinal = session_ordinals.get(trading_date)
            if index > 0 and (
                ordinal is None
                or previous_ordinal is None
                or ordinal != previous_ordinal + 1
            ):
                segment_start = index
            previous_ordinal = ordinal

        segment = data.iloc[segment_start:].reset_index(drop=True)
        raw_structure = segment["daily_structure"].astype(str).tolist()
        raw_alignment = segment["short_alignment"].astype(str).tolist()
        raw_momentum = segment["momentum"].astype(str).tolist()
        effective_structure = confirm_states(
            raw_structure,
            TICKER_SELECTED_CONFIRMATION_SESSIONS,
        )[-1]
        effective_alignment = confirm_states(
            raw_alignment,
            TICKER_SELECTED_CONFIRMATION_SESSIONS,
        )[-1]
        effective_momentum = confirm_states(
            raw_momentum,
            TICKER_SELECTED_CONFIRMATION_SESSIONS,
        )[-1]
        effective_state = candidate_ticker_state(
            daily_structure=effective_structure,
            short_alignment=effective_alignment,
            momentum=effective_momentum,
        )
        result[str(instrument_id)] = {
            "daily_structure": effective_structure,
            "short_alignment": effective_alignment,
            "momentum": effective_momentum,
            "ticker_state": effective_state,
            "raw_daily_structure": raw_structure[-1],
            "raw_short_alignment": raw_alignment[-1],
            "raw_momentum": raw_momentum[-1],
            "raw_ticker_state": str(segment.iloc[-1]["candidate_state"]),
        }
    return result


class TickerStateEngine:
    """Materialize the accepted Phase 9 per-ticker regime context for one session."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.paths = TickerRegimeProbe(settings).paths
        self.calendar = get_market_calendar()

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON manifest: {path}") from exc

    def snapshot_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.derived)
        return (
            root
            / "regimes"
            / "ticker_states"
            / f"year={as_of_date.year:04d}"
            / f"date={as_of_date}"
            / "part-000.parquet"
        )

    def manifest_path(self, as_of_date: date) -> Path:
        root = self.settings.resolved_path(self.settings.data.paths.manifests)
        return root / "regimes" / "ticker_states" / f"{as_of_date.year:04d}" / f"{as_of_date}.json"

    def _feature_lineage(self, as_of_date: date) -> tuple[int, str]:
        sessions = self.calendar.sessions_in_range(REGIME_HISTORY_ORIGIN_DATE, as_of_date)
        entries: list[str] = []
        missing: list[Path] = []
        for session in sessions:
            for timeframe in (Timeframe.DAY_1, Timeframe.HOUR_4, Timeframe.HOUR_1):
                path = self.paths.feature_manifest_file(timeframe, session)
                if not path.is_file():
                    missing.append(path)
                    continue
                payload = self._read_json(path)
                manifest = FeaturePartitionManifest.from_dict(payload)
                manifest.validate_contract(timeframe, session)
                entries.append(
                    ":".join(
                        (
                            session.isoformat(),
                            timeframe.value,
                            manifest.feature_sha256,
                            manifest.dependency_fingerprint,
                        )
                    )
                )
        if missing:
            preview = "\n  ".join(str(path) for path in missing[:20])
            suffix = "" if len(missing) <= 20 else f"\n  ... and {len(missing) - 20} more"
            raise FileNotFoundError(
                "Ticker state materialization requires complete permanent feature manifests:\n  "
                + preview
                + suffix
            )
        raw = "\n".join(entries).encode("utf-8")
        return len(entries), hashlib.sha256(raw).hexdigest()

    def _dependency(self, as_of_date: date) -> tuple[str, dict[str, object]]:
        feature_manifest_count, feature_lineage = self._feature_lineage(as_of_date)
        universe = self.paths.universe_snapshot_file(as_of_date)
        discovery = self.paths.discovery_state_file(as_of_date)
        observations = self.paths.ticker_observations_file()
        intervals = self.paths.authoritative_ticker_intervals_file()
        required = (universe, discovery, observations, intervals)
        missing = [path for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(
                "Ticker state lineage inputs are missing:\n  "
                + "\n  ".join(str(path) for path in missing)
            )
        lineage: dict[str, object] = {
            "as_of_date": as_of_date.isoformat(),
            "feature_manifest_count": feature_manifest_count,
            "feature_lineage_sha256": feature_lineage,
            "universe_sha256": sha256_file(universe),
            "discovery_state_sha256": sha256_file(discovery),
            "ticker_observations_sha256": sha256_file(observations),
            "authoritative_intervals_sha256": sha256_file(intervals),
            "state_policy": TICKER_STATE_POLICY_CONTRACT_VERSION,
            "snapshot_contract": TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
            "persistence_policy": TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "risk_policy": TICKER_RISK_POLICY_CONTRACT_VERSION,
        }
        return _fingerprint(lineage), lineage

    def _existing(
        self,
        *,
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
        if manifest.get("manifest_version") != TICKER_STATE_MANIFEST_VERSION:
            return None
        if manifest.get("snapshot_contract_version") != TICKER_STATE_SNAPSHOT_CONTRACT_VERSION:
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
    ) -> TickerStateBuildResult:
        return TickerStateBuildResult(
            as_of_date=date.fromisoformat(str(manifest["as_of_date"])),
            record_count=int(manifest["record_count"]),
            raw_state_available_count=int(manifest["raw_state_available_count"]),
            confirmed_persistence_count=int(manifest["confirmed_persistence_count"]),
            risk_mode_counts={str(k): int(v) for k, v in manifest["risk_mode_counts"].items()},
            persistence_status_counts={
                str(k): int(v) for k, v in manifest["persistence_status_counts"].items()
            },
            history_status_counts={
                str(k): int(v) for k, v in manifest["history_status_counts"].items()
            },
            effective_state_counts={
                str(k): int(v) for k, v in manifest["effective_state_counts"].items()
            },
            dependency_fingerprint=str(manifest["dependency_fingerprint"]),
            snapshot_sha256=str(manifest["snapshot_sha256"]),
            snapshot_path=snapshot_path,
            manifest_path=manifest_path,
            wall_seconds=wall_seconds,
            skipped=skipped,
        )

    def _history_frame(self, as_of_date: date) -> tuple[pd.DataFrame, int]:
        probe = TickerHistoryProbe(self.settings)
        paths = probe._required_paths(as_of_date)
        con = connect_utc(":memory:")
        try:
            routes = probe._prepare_population(con, paths)
            probe._prepare_identity(con, paths, as_of_date)
            frame = probe._history_depth_frame(con, as_of_date)
        finally:
            con.close()

        statuses: list[str] = []
        depths: list[int] = []
        starts: list[date | None] = []
        for _, row in frame.iterrows():
            status = history_status(
                alias_count=int(row["alias_count"]),
                reuse_identity_count=int(row["reuse_identity_count"]),
                authoritative_current_interval_count=int(row["authoritative_current_interval_count"]),
            )
            depth = operational_history_depth(
                status=status,
                raw_current_alias_depth=int(row["raw_current_alias_depth"]),
                authoritative_interval_depth=int(row["authoritative_interval_depth"]),
            )
            statuses.append(status)
            depths.append(depth)
            starts.append(
                pd.Timestamp(row["current_interval_from"]).date()
                if status == AUTHORITATIVE_CURRENT_INTERVAL and pd.notna(row["current_interval_from"])
                else None
            )
        data = frame.copy()
        data["history_status"] = statuses
        data["operational_depth"] = depths
        data["safe_start_date"] = starts
        return data, int(routes["population"])

    def _current_frame(self, as_of_date: date) -> tuple[pd.DataFrame, int]:
        probe = TickerRegimeProbe(self.settings)
        paths = probe._required_paths(as_of_date)
        con = connect_utc(":memory:")
        try:
            routes = probe._prepare_population(con, paths)
            if routes["duplicate_tickers"] != 0:
                raise ValueError("ticker state materialization requires unique current routing tickers")
            probe._prepare_identity(con)
            probe._prepare_current_timeframe(
                con,
                timeframe=Timeframe.DAY_1,
                bar_path=paths["bar_1d"],
                feature_path=paths["feature_1d"],
            )
            probe._prepare_current_timeframe(
                con,
                timeframe=Timeframe.HOUR_4,
                bar_path=paths["bar_4h"],
                feature_path=paths["feature_4h"],
            )
            probe._prepare_current_timeframe(
                con,
                timeframe=Timeframe.HOUR_1,
                bar_path=paths["bar_1h"],
                feature_path=paths["feature_1h"],
            )
            probe._history_counts(con, as_of_date)
            frame = probe._candidate_frame(con)
        finally:
            con.close()
        return frame, int(routes["population"])

    @staticmethod
    def _risk_states(row: pd.Series, window: int) -> tuple[str, str]:
        return (
            self_relative_volatility_state(
                natr_value=float(row["natr_14"]),
                realized_volatility_value=float(row["realized_volatility_20"]),
                natr_p25=float(row[f"natr_p25_{window}"]),
                natr_p75=float(row[f"natr_p75_{window}"]),
                natr_p90=float(row[f"natr_p90_{window}"]),
                realized_p25=float(row[f"rv_p25_{window}"]),
                realized_p75=float(row[f"rv_p75_{window}"]),
                realized_p90=float(row[f"rv_p90_{window}"]),
            ),
            self_relative_efficiency_state(
                value=float(row["directional_efficiency_20"]),
                p25=float(row[f"eff_p25_{window}"]),
                p75=float(row[f"eff_p75_{window}"]),
            ),
        )

    def build(self, as_of_date: date) -> TickerStateBuildResult:
        started = perf_counter()
        if not self.calendar.is_session(as_of_date):
            raise ValueError(f"{as_of_date} is not an XNYS trading session")

        dependency, lineage = self._dependency(as_of_date)
        snapshot_path = self.snapshot_path(as_of_date)
        manifest_path = self.manifest_path(as_of_date)
        existing = self._existing(
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

        history, history_population = self._history_frame(as_of_date)
        current, current_population = self._current_frame(as_of_date)
        if history_population != current_population or len(history) != current_population:
            raise ValueError("ticker state population mismatch between history and current inputs")
        if len(current) != current_population:
            raise ValueError("ticker current frame does not represent the routed population exactly once")

        safe_statuses = {CURRENT_ALIAS_NO_CONFLICT, AUTHORITATIVE_CURRENT_INTERVAL}
        safe_population = history.loc[
            history["history_status"].isin(safe_statuses),
            ["instrument_id", "ticker", "history_status", "operational_depth", "safe_start_date"],
        ].copy()
        safe_population["safe_start_date"] = pd.to_datetime(
            safe_population["safe_start_date"]
        ).dt.date
        analyzable = safe_population.loc[
            pd.to_numeric(safe_population["operational_depth"], errors="coerce").fillna(0) >= 2
        ].copy()

        persistence_probe = TickerPersistenceProbe(self.settings)
        state_history = persistence_probe._state_frame(analyzable, as_of_date)
        sessions = self.calendar.sessions_in_range(REGIME_HISTORY_ORIGIN_DATE, as_of_date)
        session_ordinals = {session: index for index, session in enumerate(sessions)}
        persisted_map = persisted_current_dimensions(
            state_history,
            as_of_date=as_of_date,
            session_ordinals=session_ordinals,
        )

        risk_probe = TickerRiskProbe(self.settings)
        risk_frame = risk_probe._current_quantile_frame(safe_population, as_of_date)
        risk_map = (
            risk_frame.set_index("instrument_id").to_dict(orient="index")
            if not risk_frame.empty
            else {}
        )
        history_map = history.set_index("instrument_id").to_dict(orient="index")

        records: list[dict[str, object]] = []
        history_counts: Counter[str] = Counter()
        persistence_counts: Counter[str] = Counter()
        risk_mode_counts: Counter[str] = Counter()
        effective_counts: Counter[str] = Counter()
        raw_available = 0
        confirmed_count = 0

        for _, row in current.sort_values("instrument_id").iterrows():
            instrument_id = str(row["instrument_id"])
            history_row = history_map[instrument_id]
            status = str(history_row["history_status"])
            depth = int(history_row["operational_depth"])
            identity_safe = status in safe_statuses
            raw = classify_current_ticker_dimensions(row)
            if raw is not None:
                raw_available += 1

            persisted = persisted_map.get(instrument_id)
            if raw is None:
                persistence_status = PERSISTENCE_NO_CURRENT_STATE
                effective = None
            elif persisted is not None:
                if (
                    persisted["raw_daily_structure"] != raw["daily_structure"]
                    or persisted["raw_short_alignment"] != raw["short_alignment"]
                    or persisted["raw_momentum"] != raw["momentum"]
                    or persisted["raw_ticker_state"] != raw["ticker_state"]
                ):
                    raise ValueError(
                        f"current ticker classifier disagrees with persistence replay for {row['ticker']}"
                    )
                persistence_status = PERSISTENCE_CONFIRMED
                effective = {
                    "daily_structure": persisted["daily_structure"],
                    "short_alignment": persisted["short_alignment"],
                    "momentum": persisted["momentum"],
                    "ticker_state": persisted["ticker_state"],
                }
                confirmed_count += 1
            elif not identity_safe:
                persistence_status = PERSISTENCE_CURRENT_ONLY_BLOCKED
                effective = raw
            else:
                persistence_status = PERSISTENCE_CURRENT_ONLY_SHALLOW
                effective = raw

            risk_row = risk_map.get(instrument_id)
            has_current_metrics = risk_row is not None
            prior_sessions = (
                int(risk_row.get("prior_count_252", 0))
                if risk_row is not None
                else 0
            )
            risk_mode = ticker_risk_history_mode(
                identity_safe=identity_safe,
                has_current_metrics=has_current_metrics,
                prior_sessions=prior_sessions,
            )
            selected_window = ticker_risk_selected_window(risk_mode)
            risk_state: str | None = None
            efficiency_state: str | None = None
            natr: float | None = None
            realized_volatility: float | None = None
            directional_efficiency: float | None = None
            if risk_row is not None:
                natr = float(risk_row["natr_14"])
                realized_volatility = float(risk_row["realized_volatility_20"])
                directional_efficiency = float(risk_row["directional_efficiency_20"])
            if selected_window is not None and risk_row is not None:
                risk_state, efficiency_state = self._risk_states(
                    pd.Series(risk_row),
                    selected_window,
                )

            history_counts.update([status])
            persistence_counts.update([persistence_status])
            risk_mode_counts.update([risk_mode])
            if effective is not None:
                effective_counts.update([effective["ticker_state"]])

            records.append(
                {
                    "instrument_id": instrument_id,
                    "ticker": str(row["ticker"]),
                    "security_type": str(row["security_type"]),
                    "routes": row["routes"],
                    "as_of_date": as_of_date,
                    "in_discovery_state": bool(row["in_discovery_state"]),
                    "discovery_state": None if pd.isna(row["discovery_state"]) else str(row["discovery_state"]),
                    "discovery_direction": None if pd.isna(row["discovery_direction"]) else str(row["discovery_direction"]),
                    "top_setup": None if pd.isna(row["top_setup"]) else str(row["top_setup"]),
                    "history_status": status,
                    "history_safe": identity_safe,
                    "operational_history_depth": depth,
                    "raw_state_available": raw is not None,
                    "raw_daily_structure": None if raw is None else raw["daily_structure"],
                    "raw_short_alignment": None if raw is None else raw["short_alignment"],
                    "raw_momentum": None if raw is None else raw["momentum"],
                    "raw_ticker_state": None if raw is None else raw["ticker_state"],
                    "persistence_status": persistence_status,
                    "effective_daily_structure": None if effective is None else effective["daily_structure"],
                    "effective_short_alignment": None if effective is None else effective["short_alignment"],
                    "effective_momentum": None if effective is None else effective["momentum"],
                    "effective_ticker_state": None if effective is None else effective["ticker_state"],
                    "risk_mode": risk_mode,
                    "risk_window_sessions": selected_window,
                    "risk_state": risk_state,
                    "efficiency_state": efficiency_state,
                    "natr_14": natr,
                    "realized_volatility_20": realized_volatility,
                    "directional_efficiency_20": directional_efficiency,
                }
            )

        output = pd.DataFrame.from_records(records)
        if len(output) != current_population or output["instrument_id"].duplicated().any():
            raise ValueError("ticker state output violates one-row-per-routed-instrument contract")

        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        temp = atomic_target(snapshot_path)
        con = connect_utc(":memory:")
        try:
            con.register("atlas_ticker_states", output)
            compression = self.settings.data.parquet.compression.upper()
            row_group_size = int(self.settings.data.parquet.row_group_size)
            con.execute(
                f"""
                COPY (SELECT * FROM atlas_ticker_states ORDER BY instrument_id)
                TO {sql_string(temp)}
                (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group_size})
                """
            )
            promote(temp, snapshot_path)
        finally:
            con.close()

        snapshot_sha = sha256_file(snapshot_path)
        manifest = {
            "manifest_version": TICKER_STATE_MANIFEST_VERSION,
            "snapshot_contract_version": TICKER_STATE_SNAPSHOT_CONTRACT_VERSION,
            "state_policy_contract_version": TICKER_STATE_POLICY_CONTRACT_VERSION,
            "persistence_policy_contract_version": TICKER_PERSISTENCE_POLICY_CONTRACT_VERSION,
            "risk_policy_contract_version": TICKER_RISK_POLICY_CONTRACT_VERSION,
            "as_of_date": as_of_date.isoformat(),
            "dependency_fingerprint": dependency,
            "source_lineage": lineage,
            "record_count": len(records),
            "raw_state_available_count": raw_available,
            "confirmed_persistence_count": confirmed_count,
            "history_status_counts": dict(sorted(history_counts.items())),
            "persistence_status_counts": dict(sorted(persistence_counts.items())),
            "risk_mode_counts": dict(sorted(risk_mode_counts.items())),
            "effective_state_counts": dict(sorted(effective_counts.items())),
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
