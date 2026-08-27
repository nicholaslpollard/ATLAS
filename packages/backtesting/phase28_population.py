from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from packages.core.atomic_io import atomic_write_text
from packages.core.enums import Timeframe
from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.atomic import atomic_target, promote
from packages.data.duckdb_connection import connect_utc
from packages.data.paths import MarketDataPaths
from packages.data.sql import sql_string
from packages.features.partition_store import sha256_file

from .phase26_closeout import PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase26Closeout
from .phase26_observations import (
    PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION,
    PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION,
    PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION,
    Phase26ObservationBuilder,
)
from .phase27_closeout import PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase27Closeout
from .phase28_network import compute_signal_values, cross_sectional_residuals, select_leaders
from .phase28_policy import (
    PHASE28_DEVELOPMENT_END,
    PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS,
    PHASE28_LEAD_LAG_PAIRS,
    PHASE28_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE28_PROTECTED_END,
    PHASE28_PROTECTED_START,
    PHASE28_RAW_SIGNAL_FIELDS,
    PHASE28_RESEARCH_START,
    PHASE28_SOURCE_PHASE26_POLICY_FINGERPRINT,
    PHASE28_SOURCE_PHASE27_POLICY_FINGERPRINT,
    phase28_policy_fingerprint,
)


PHASE28_POPULATION_REPORT_CONTRACT_VERSION = (
    "phase28-population-report-v1-pit-split-safe-residual-lead-lag-network"
)
PHASE28_DEVELOPMENT_FRAME_CONTRACT_VERSION = (
    "phase28-development-frame-v1-network-signals-three-session-outcomes"
)
PHASE28_PROTECTED_FRAME_CONTRACT_VERSION = (
    "phase28-protected-frame-v1-network-signals-no-outcomes"
)
PHASE28_REQUIRED_CLOSES = PHASE28_LEAD_LAG_PAIRS + 3
PHASE28_REQUIRED_RESIDUAL_RETURNS = PHASE28_REQUIRED_CLOSES - 1


class Phase28PopulationError(RuntimeError):
    pass


def _json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase28PopulationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase28PopulationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase28PopulationError(f"{label} must be a JSON object")
    return payload


def _read_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase28PopulationError(f"missing parquet evidence: {path}")
    con = connect_utc(":memory:")
    try:
        frame = con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()
    return frame


def _write_parquet(
    settings: AtlasSettings,
    frame: pd.DataFrame,
    target: Path,
    *,
    order_by: str,
) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase28_population_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM phase28_population_write ORDER BY {order_by}) "
            f"TO {sql_string(temp)} (FORMAT PARQUET, COMPRESSION {compression}, "
            f"ROW_GROUP_SIZE {row_group_size})"
        )
        promote(temp, target)
    finally:
        con.close()


def _normalize_source_dates(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for field in ("as_of_date", "safe_start_date", "safe_end_date"):
        if field not in result.columns:
            raise Phase28PopulationError(f"Phase28 source frame missing {field}")
        result[field] = pd.to_datetime(result[field]).dt.date
    if result.duplicated(["as_of_date", "instrument_id"], keep=False).any():
        raise Phase28PopulationError("Phase28 source contains duplicate candidate keys")
    if result.duplicated(["as_of_date", "ticker"], keep=False).any():
        raise Phase28PopulationError("Phase28 peer universe contains duplicate ticker keys")
    return result


def _session_history_bounds(
    calendar_sessions: tuple[date, ...],
    observation_dates: tuple[date, ...],
) -> dict[date, date | None]:
    index = {session: position for position, session in enumerate(calendar_sessions)}
    result: dict[date, date | None] = {}
    for observation_date in observation_dates:
        position = index.get(observation_date)
        if position is None or position < PHASE28_REQUIRED_CLOSES - 1:
            result[observation_date] = None
        else:
            result[observation_date] = calendar_sessions[
                position - (PHASE28_REQUIRED_CLOSES - 1)
            ]
    return result


def _split_lookup(splits: pd.DataFrame) -> dict[str, tuple[date, ...]]:
    if splits.empty:
        return {}
    work = splits.copy()
    work["execution_date"] = pd.to_datetime(work["execution_date"]).dt.date
    return {
        str(ticker): tuple(sorted(set(group["execution_date"])))
        for ticker, group in work.groupby("ticker", sort=False, observed=True)
    }


def _crosses_history_split(
    dates: tuple[date, ...], *, history_start: date, observation_date: date
) -> bool:
    return any(history_start < split_date <= observation_date for split_date in dates)


class Phase28PopulationBuilder:
    """Reconstruct Phase28 relational signals from accepted local PIT evidence."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26 = Phase26ObservationBuilder(settings)
        self.phase26_closeout = Phase26Closeout(settings)
        self.phase27_closeout = Phase27Closeout(settings)
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase28" / "v1" / "population"

    def report_path(self) -> Path:
        return self.root / "population_report.json"

    def development_path(self) -> Path:
        return self.root / "development_network_frame.parquet"

    def protected_path(self) -> Path:
        return self.root / "protected_network_predictors.parquet"

    def _source_evidence(self) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
        observation = _json(self.phase26.report_path(), "Phase26 observation report")
        if observation.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION:
            raise Phase28PopulationError("Phase26 observation report contract mismatch")
        if observation.get("phase26_policy_fingerprint") != PHASE28_SOURCE_PHASE26_POLICY_FINGERPRINT:
            raise Phase28PopulationError("Phase26 policy fingerprint drift")
        if observation.get("pass") is not True or int(observation.get("protected_return_reads", -1)) != 0:
            raise Phase28PopulationError("Phase26 observation evidence is not passing protected-blind")
        if str(observation.get("development_boundary_label_end")) != PHASE28_DEVELOPMENT_END:
            raise Phase28PopulationError("Phase28 development end drifted from accepted source")

        phase26_closeout = _json(self.phase26_closeout.report_path(), "Phase26 closeout")
        if phase26_closeout.get("contract_version") != PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION:
            raise Phase28PopulationError("Phase26 closeout contract mismatch")
        if phase26_closeout.get("phase26_disposition") != "ACCEPTED_NEGATIVE" or phase26_closeout.get("pass") is not True:
            raise Phase28PopulationError("Phase26 is not accepted-negative passing")
        if int(phase26_closeout.get("protected_returns_read", -1)) != 0:
            raise Phase28PopulationError("Phase26 protected holdout was consumed")

        phase27_closeout = _json(self.phase27_closeout.report_path(), "Phase27 closeout")
        if phase27_closeout.get("contract_version") != PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION:
            raise Phase28PopulationError("Phase27 closeout contract mismatch")
        if phase27_closeout.get("phase27_policy_fingerprint") != PHASE28_SOURCE_PHASE27_POLICY_FINGERPRINT:
            raise Phase28PopulationError("Phase27 policy fingerprint drift")
        if phase27_closeout.get("phase27_disposition") != "ACCEPTED_NEGATIVE" or phase27_closeout.get("pass") is not True:
            raise Phase28PopulationError("Phase27 is not accepted-negative passing")
        if int(phase27_closeout.get("protected_candidate_rows_read", -1)) != 0:
            raise Phase28PopulationError("Phase27 protected candidate rows were read")
        if int(phase27_closeout.get("protected_returns_read", -1)) != 0:
            raise Phase28PopulationError("Phase27 protected returns were read")
        if phase27_closeout.get("protected_holdout_consumed") is not False:
            raise Phase28PopulationError("Phase27 does not prove an unopened master holdout")
        return observation, phase26_closeout, phase27_closeout

    def _source_frames(self, observation: dict[str, object]) -> tuple[pd.DataFrame, pd.DataFrame]:
        development_path = self.phase26.development_path()
        protected_path = self.phase26.protected_predictors_path()
        if observation.get("development_sha256") != sha256_file(development_path):
            raise Phase28PopulationError("Phase26 development source SHA mismatch")
        if observation.get("protected_predictors_sha256") != sha256_file(protected_path):
            raise Phase28PopulationError("Phase26 protected source SHA mismatch")
        development = _normalize_source_dates(
            _read_parquet(development_path, order_by="as_of_date, instrument_id")
        )
        protected = _normalize_source_dates(
            _read_parquet(protected_path, order_by="as_of_date, instrument_id")
        )
        if development.empty or protected.empty:
            raise Phase28PopulationError("Phase28 source population is empty")
        if set(development["contract_version"].astype(str)) != {
            PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION
        }:
            raise Phase28PopulationError("Phase26 development row contract mismatch")
        if set(protected["contract_version"].astype(str)) != {
            PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION
        }:
            raise Phase28PopulationError("Phase26 protected row contract mismatch")
        forbidden = sorted(
            field for field in PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS if field in protected.columns
        )
        if forbidden:
            raise Phase28PopulationError(
                "Phase28 protected source contains forbidden outcomes: " + ", ".join(forbidden)
            )
        return development, protected

    def _calendar_sessions(self) -> tuple[date, ...]:
        sessions = tuple(
            self.calendar.sessions_in_range(date(2021, 1, 4), date.fromisoformat(PHASE28_PROTECTED_END))
        )
        if not sessions:
            raise Phase28PopulationError("Phase28 exchange calendar is empty")
        return sessions

    def _history_rows(
        self,
        source: pd.DataFrame,
        *,
        splits: pd.DataFrame,
    ) -> tuple[pd.DataFrame, dict[date, int], dict[date, int]]:
        observation_dates = tuple(sorted(set(source["as_of_date"])))
        sessions = self._calendar_sessions()
        history_start_by_date = _session_history_bounds(sessions, observation_dates)
        split_dates = _split_lookup(splits)

        peer_records: list[dict[str, object]] = []
        source_peer_count: dict[date, int] = {}
        history_eligible_count: dict[date, int] = {}
        for observation_date, group in source.groupby("as_of_date", sort=True, observed=True):
            source_peer_count[observation_date] = int(len(group))
            history_start = history_start_by_date.get(observation_date)
            eligible = 0
            if history_start is not None:
                for row in group.itertuples(index=False):
                    safe_start = row.safe_start_date
                    safe_end = row.safe_end_date
                    if safe_start > history_start or safe_end < observation_date:
                        continue
                    ticker = str(row.ticker)
                    if _crosses_history_split(
                        split_dates.get(ticker, ()),
                        history_start=history_start,
                        observation_date=observation_date,
                    ):
                        continue
                    peer_records.append(
                        {
                            "observation_date": observation_date,
                            "history_start": history_start,
                            "peer_instrument_id": str(row.instrument_id),
                            "ticker": ticker,
                        }
                    )
                    eligible += 1
            history_eligible_count[observation_date] = eligible

        peers = pd.DataFrame.from_records(
            peer_records,
            columns=["observation_date", "history_start", "peer_instrument_id", "ticker"],
        )
        if peers.empty:
            raise Phase28PopulationError("Phase28 has no identity/split-safe peer histories")
        if peers.duplicated(["observation_date", "peer_instrument_id"]).any():
            raise Phase28PopulationError("Phase28 history peer plan contains duplicate instrument keys")

        con = connect_utc(":memory:")
        try:
            con.register("p28_peer_plan", peers)
            bars = self.paths.glob_for_timeframe(Timeframe.DAY_1)
            history = con.execute(
                f"""
                SELECT
                    CAST(p.observation_date AS DATE) AS observation_date,
                    p.peer_instrument_id,
                    p.ticker,
                    CAST(b.session_date AS DATE) AS history_date,
                    CAST(b.close AS DOUBLE) AS close
                FROM p28_peer_plan p
                INNER JOIN read_parquet(
                    {sql_string(bars)}, union_by_name=true, hive_partitioning=false
                ) b
                  ON b.symbol = p.ticker
                 AND CAST(b.session_date AS DATE) BETWEEN CAST(p.history_start AS DATE)
                                                       AND CAST(p.observation_date AS DATE)
                WHERE b.close IS NOT NULL
                  AND isfinite(CAST(b.close AS DOUBLE))
                  AND CAST(b.close AS DOUBLE) > 0
                ORDER BY p.observation_date, p.peer_instrument_id, b.session_date
                """
            ).fetch_df()
        finally:
            con.close()
        if history.empty:
            raise Phase28PopulationError("Phase28 canonical daily history query is empty")
        history["observation_date"] = pd.to_datetime(history["observation_date"]).dt.date
        history["history_date"] = pd.to_datetime(history["history_date"]).dt.date
        if history.duplicated(
            ["observation_date", "peer_instrument_id", "history_date"], keep=False
        ).any():
            raise Phase28PopulationError("Phase28 daily history join is non-unique")
        return history, source_peer_count, history_eligible_count

    def _network_frame(
        self,
        source: pd.DataFrame,
        *,
        splits: pd.DataFrame,
        development: bool,
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        history, source_peer_count, history_eligible_count = self._history_rows(source, splits=splits)
        source_by_date = {
            session: group.copy()
            for session, group in source.groupby("as_of_date", sort=True, observed=True)
        }
        history_by_date = {
            session: group.copy()
            for session, group in history.groupby("observation_date", sort=True, observed=True)
        }
        sessions = self._calendar_sessions()
        prior_by_date = {sessions[index]: sessions[index - 1] for index in range(1, len(sessions))}

        records: list[dict[str, object]] = []
        no_history_sessions = 0
        no_residual_sessions = 0
        focal_without_leaders = 0
        focal_without_signals = 0
        for observation_date in sorted(source_by_date):
            source_group = source_by_date[observation_date]
            history_group = history_by_date.get(observation_date)
            if history_group is None or history_group.empty:
                no_history_sessions += 1
                continue
            close_matrix = history_group.pivot(
                index="history_date",
                columns="peer_instrument_id",
                values="close",
            ).sort_index()
            raw_returns = close_matrix.pct_change(fill_method=None).iloc[1:].copy()
            if raw_returns.empty:
                no_residual_sessions += 1
                continue
            residuals = cross_sectional_residuals(raw_returns)
            estimation_end = prior_by_date.get(observation_date)
            if estimation_end is None:
                no_residual_sessions += 1
                continue
            peer_ids = tuple(str(value) for value in residuals.columns)

            for row in source_group.itertuples(index=False):
                focal_id = str(row.instrument_id)
                if focal_id not in residuals.columns:
                    focal_without_leaders += 1
                    continue
                leaders = select_leaders(
                    residuals,
                    focal_id=focal_id,
                    peer_ids=peer_ids,
                    estimation_end=estimation_end,
                )
                if not leaders:
                    focal_without_leaders += 1
                    continue
                signals = compute_signal_values(
                    residuals,
                    focal_id=focal_id,
                    leaders=leaders,
                    observation_date=observation_date,
                )
                if signals is None:
                    focal_without_signals += 1
                    continue
                base = row._asdict()
                base.update(signals.to_dict())
                base["phase28_source_peer_count"] = source_peer_count.get(observation_date, 0)
                base["phase28_history_eligible_peer_count"] = history_eligible_count.get(observation_date, 0)
                base["phase28_leader_count"] = len(leaders)
                base["phase28_leaders_json"] = json.dumps(
                    [
                        {
                            "peer_id": edge.peer_id,
                            "forward_corr": edge.forward_corr,
                            "reverse_corr": edge.reverse_corr,
                            "asymmetry": edge.asymmetry,
                            "valid_pairs": edge.valid_pairs,
                            "weight": edge.weight,
                        }
                        for edge in leaders
                    ],
                    sort_keys=True,
                    separators=(",", ":"),
                )
                records.append(base)

        frame = pd.DataFrame.from_records(records)
        if frame.empty:
            raise Phase28PopulationError("Phase28 network construction produced zero signal rows")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        for field in PHASE28_RAW_SIGNAL_FIELDS:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
        finite = np.isfinite(frame[list(PHASE28_RAW_SIGNAL_FIELDS)].to_numpy(dtype=float)).all(axis=1)
        if development:
            if "directional_return" not in frame.columns:
                raise Phase28PopulationError("Phase28 development frame lost directional return")
            directional = pd.to_numeric(frame["directional_return"], errors="coerce").to_numpy(dtype=float)
            finite &= np.isfinite(directional)
        frame = frame.loc[finite].copy()
        frame = frame.loc[frame["direction"].astype(str).isin(("bullish", "bearish"))].copy()
        counts = frame.groupby(["as_of_date", "direction"], sort=False, observed=True)[
            "instrument_id"
        ].transform("size")
        frame = frame.loc[counts >= PHASE28_MIN_DIRECTION_ROWS_PER_SESSION].copy()
        if frame.empty:
            raise Phase28PopulationError("Phase28 same-population complete-case gate removed all rows")
        if frame.duplicated(["as_of_date", "instrument_id"], keep=False).any():
            raise Phase28PopulationError("Phase28 network frame contains duplicate candidate keys")
        diagnostics = {
            "source_rows": int(len(source)),
            "complete_network_rows": int(len(frame)),
            "no_history_sessions": int(no_history_sessions),
            "no_residual_sessions": int(no_residual_sessions),
            "focal_without_leaders": int(focal_without_leaders),
            "focal_without_signals": int(focal_without_signals),
        }
        return frame.sort_values(["as_of_date", "instrument_id"], kind="stable").reset_index(drop=True), diagnostics

    def run(self) -> dict[str, object]:
        observation, phase26_closeout, phase27_closeout = self._source_evidence()
        development, protected = self._source_frames(observation)
        splits, split_path, split_sha = self.phase26._split_evidence()

        development_frame, development_diagnostics = self._network_frame(
            development,
            splits=splits,
            development=True,
        )
        protected_frame, protected_diagnostics = self._network_frame(
            protected,
            splits=splits,
            development=False,
        )
        protected_dates = pd.to_datetime(protected_frame["as_of_date"]).dt.date
        if protected_dates.min().isoformat() != PHASE28_PROTECTED_START:
            raise Phase28PopulationError("Phase28 protected network start drifted")
        if protected_dates.max().isoformat() != PHASE28_PROTECTED_END:
            raise Phase28PopulationError("Phase28 protected network end drifted")
        for field in PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS:
            if field in protected_frame.columns:
                raise Phase28PopulationError(f"Phase28 protected network leaked outcome field {field}")

        development_frame.insert(
            0,
            "phase28_contract_version",
            PHASE28_DEVELOPMENT_FRAME_CONTRACT_VERSION,
        )
        protected_frame.insert(
            0,
            "phase28_contract_version",
            PHASE28_PROTECTED_FRAME_CONTRACT_VERSION,
        )
        development_path = self.development_path()
        protected_path = self.protected_path()
        _write_parquet(
            self.settings,
            development_frame,
            development_path,
            order_by="as_of_date, instrument_id",
        )
        _write_parquet(
            self.settings,
            protected_frame,
            protected_path,
            order_by="as_of_date, instrument_id",
        )

        checks = {
            "phase26_observation_pass": observation.get("pass") is True,
            "phase26_closeout_accepted_negative": phase26_closeout.get("phase26_disposition")
            == "ACCEPTED_NEGATIVE",
            "phase27_closeout_accepted_negative": phase27_closeout.get("phase27_disposition")
            == "ACCEPTED_NEGATIVE",
            "phase27_holdout_unconsumed": phase27_closeout.get("protected_holdout_consumed") is False,
            "development_nonempty": len(development_frame) > 0,
            "protected_nonempty": len(protected_frame) > 0,
            "all_signal_fields_present": all(
                field in development_frame.columns and field in protected_frame.columns
                for field in PHASE28_RAW_SIGNAL_FIELDS
            ),
            "protected_outcomes_absent": not any(
                field in protected_frame.columns for field in PHASE28_FORBIDDEN_PROTECTED_OUTCOME_FIELDS
            ),
            "required_close_count_63": PHASE28_REQUIRED_CLOSES == 63,
            "required_residual_count_62": PHASE28_REQUIRED_RESIDUAL_RETURNS == 62,
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = sorted(name for name, value in checks.items() if not value)
            raise Phase28PopulationError("Phase28 population checks failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, Any] = {
            "contract_version": PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
            "phase28_policy_fingerprint": phase28_policy_fingerprint(),
            "source_phase26_policy_fingerprint": PHASE28_SOURCE_PHASE26_POLICY_FINGERPRINT,
            "source_phase27_policy_fingerprint": PHASE28_SOURCE_PHASE27_POLICY_FINGERPRINT,
            "phase26_observation_report_sha256": sha256_file(self.phase26.report_path()),
            "phase26_closeout_report_sha256": sha256_file(self.phase26_closeout.report_path()),
            "phase27_closeout_report_sha256": sha256_file(self.phase27_closeout.report_path()),
            "phase26_development_sha256": sha256_file(self.phase26.development_path()),
            "phase26_protected_predictors_sha256": sha256_file(self.phase26.protected_predictors_path()),
            "split_evidence_path": str(split_path.resolve()),
            "split_evidence_sha256": split_sha,
            "development_diagnostics": development_diagnostics,
            "protected_diagnostics": protected_diagnostics,
            "development_network_rows": int(len(development_frame)),
            "protected_network_rows": int(len(protected_frame)),
            "raw_signal_fields": list(PHASE28_RAW_SIGNAL_FIELDS),
            "required_close_sessions": PHASE28_REQUIRED_CLOSES,
            "required_residual_return_sessions": PHASE28_REQUIRED_RESIDUAL_RETURNS,
            "development_sha256": sha256_file(development_path),
            "protected_sha256": sha256_file(protected_path),
            "protected_return_reads": 0,
            "provider_reads": 0,
            "provider_writes": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "order_writes": 0,
            "paper_submits": 0,
            "live_writes": 0,
            "automation_writes": 0,
            "checks": checks,
            "generated_at_utc": datetime.now(UTC).isoformat(),
            "report_path": str(report_path.resolve()),
            "pass": True,
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(report_path, json.dumps(report, indent=2, sort_keys=True) + "\n")
        return report
