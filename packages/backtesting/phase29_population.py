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
from .phase28_closeout import PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION, Phase28Closeout
from .phase29_policy import (
    PHASE29_DEVELOPMENT_END,
    PHASE29_FORBIDDEN_PROTECTED_OUTCOME_FIELDS,
    PHASE29_MIN_DIRECTION_ROWS_PER_SESSION,
    PHASE29_PCA_MIN_PEERS,
    PHASE29_PROTECTED_END,
    PHASE29_PROTECTED_START,
    PHASE29_RAW_SIGNAL_FIELDS,
    PHASE29_REQUIRED_CLOSES,
    PHASE29_SOURCE_PHASE26_POLICY_FINGERPRINT,
    PHASE29_SOURCE_PHASE27_POLICY_FINGERPRINT,
    PHASE29_SOURCE_PHASE28_MERGE,
    PHASE29_SOURCE_PHASE28_POLICY_FINGERPRINT,
    phase29_policy_fingerprint,
)
from .phase29_relative_value import nearest_pair_dislocations, pca_residual_dislocations


PHASE29_POPULATION_REPORT_CONTRACT_VERSION = (
    "phase29-population-report-v1-pit-split-safe-pca-distance-relative-value"
)
PHASE29_DEVELOPMENT_FRAME_CONTRACT_VERSION = (
    "phase29-development-frame-v1-relative-value-signals-three-session-outcomes"
)
PHASE29_PROTECTED_FRAME_CONTRACT_VERSION = (
    "phase29-protected-frame-v1-relative-value-signals-no-outcomes"
)


class Phase29PopulationError(RuntimeError):
    pass


def _read_json(path: Path, label: str) -> dict[str, object]:
    if not path.is_file():
        raise Phase29PopulationError(f"missing {label}: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise Phase29PopulationError(f"invalid JSON for {label}: {path}") from exc
    if not isinstance(payload, dict):
        raise Phase29PopulationError(f"{label} must be a JSON object")
    return payload


def _read_parquet(path: Path, *, order_by: str) -> pd.DataFrame:
    if not path.is_file():
        raise Phase29PopulationError(f"missing parquet evidence: {path}")
    con = connect_utc(":memory:")
    try:
        return con.execute(
            f"SELECT * FROM read_parquet({sql_string(path)}) ORDER BY {order_by}"
        ).fetch_df()
    finally:
        con.close()


def _write_parquet(settings: AtlasSettings, frame: pd.DataFrame, target: Path, *, order_by: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = atomic_target(target)
    temp.unlink(missing_ok=True)
    con = connect_utc(":memory:")
    try:
        con.register("phase29_write", frame)
        compression = settings.data.parquet.compression.upper()
        row_group_size = int(settings.data.parquet.row_group_size)
        con.execute(
            f"COPY (SELECT * FROM phase29_write ORDER BY {order_by}) "
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
            raise Phase29PopulationError(f"Phase29 source frame missing {field}")
        result[field] = pd.to_datetime(result[field]).dt.date
    if result.duplicated(["as_of_date", "instrument_id"], keep=False).any():
        raise Phase29PopulationError("Phase29 source contains duplicate candidate keys")
    if result.duplicated(["as_of_date", "ticker"], keep=False).any():
        raise Phase29PopulationError("Phase29 peer universe contains duplicate ticker keys")
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


def _crosses_split(dates: tuple[date, ...], *, history_start: date, observation_date: date) -> bool:
    return any(history_start < split_date <= observation_date for split_date in dates)


class Phase29PopulationBuilder:
    """Build Phase29 relative-value signals from accepted local PIT evidence only."""

    def __init__(self, settings: AtlasSettings) -> None:
        self.settings = settings
        self.phase26 = Phase26ObservationBuilder(settings)
        self.phase26_closeout = Phase26Closeout(settings)
        self.phase27_closeout = Phase27Closeout(settings)
        self.phase28_closeout = Phase28Closeout(settings)
        self.paths = MarketDataPaths(settings)
        self.calendar = get_market_calendar(settings.data.calendar.exchange)
        derived = settings.resolved_path(settings.data.paths.derived)
        self.root = derived / "strategy_evaluation" / "phase29" / "v1" / "population"

    def report_path(self) -> Path:
        return self.root / "population_report.json"

    def development_path(self) -> Path:
        return self.root / "development_relative_value_frame.parquet"

    def protected_path(self) -> Path:
        return self.root / "protected_relative_value_predictors.parquet"

    def _source_evidence(
        self,
    ) -> tuple[dict[str, object], dict[str, object], dict[str, object], dict[str, object]]:
        observation = _read_json(self.phase26.report_path(), "Phase26 observation report")
        if observation.get("contract_version") != PHASE26_OBSERVATION_REPORT_CONTRACT_VERSION:
            raise Phase29PopulationError("Phase26 observation contract mismatch")
        if observation.get("phase26_policy_fingerprint") != PHASE29_SOURCE_PHASE26_POLICY_FINGERPRINT:
            raise Phase29PopulationError("Phase26 policy fingerprint drift")
        if observation.get("pass") is not True or int(observation.get("protected_return_reads", -1)) != 0:
            raise Phase29PopulationError("Phase26 observation evidence is not protected-blind passing")
        if str(observation.get("development_boundary_label_end")) != PHASE29_DEVELOPMENT_END:
            raise Phase29PopulationError("Phase29 development end drifted from source")

        p26 = _read_json(self.phase26_closeout.report_path(), "Phase26 closeout")
        if p26.get("contract_version") != PHASE26_CLOSEOUT_REPORT_CONTRACT_VERSION:
            raise Phase29PopulationError("Phase26 closeout contract mismatch")
        if p26.get("phase26_disposition") != "ACCEPTED_NEGATIVE" or p26.get("pass") is not True:
            raise Phase29PopulationError("Phase26 is not accepted-negative passing")
        if int(p26.get("protected_returns_read", -1)) != 0:
            raise Phase29PopulationError("Phase26 protected returns were consumed")

        p27 = _read_json(self.phase27_closeout.report_path(), "Phase27 closeout")
        if p27.get("contract_version") != PHASE27_CLOSEOUT_REPORT_CONTRACT_VERSION:
            raise Phase29PopulationError("Phase27 closeout contract mismatch")
        if p27.get("phase27_policy_fingerprint") != PHASE29_SOURCE_PHASE27_POLICY_FINGERPRINT:
            raise Phase29PopulationError("Phase27 policy fingerprint drift")
        if p27.get("phase27_disposition") != "ACCEPTED_NEGATIVE" or p27.get("pass") is not True:
            raise Phase29PopulationError("Phase27 is not accepted-negative passing")
        if int(p27.get("protected_candidate_rows_read", -1)) != 0 or int(
            p27.get("protected_returns_read", -1)
        ) != 0:
            raise Phase29PopulationError("Phase27 protected evidence was consumed")
        if p27.get("protected_holdout_consumed") is not False:
            raise Phase29PopulationError("Phase27 holdout state is not unopened")

        p28 = _read_json(self.phase28_closeout.report_path(), "Phase28 closeout")
        if p28.get("contract_version") != PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION:
            raise Phase29PopulationError("Phase28 closeout contract mismatch")
        if p28.get("phase28_policy_fingerprint") != PHASE29_SOURCE_PHASE28_POLICY_FINGERPRINT:
            raise Phase29PopulationError("Phase28 policy fingerprint drift")
        if p28.get("phase28_disposition") != "ACCEPTED_NEGATIVE" or p28.get("pass") is not True:
            raise Phase29PopulationError("Phase28 is not accepted-negative passing")
        if int(p28.get("protected_candidate_rows_read", -1)) != 0 or int(
            p28.get("protected_returns_read", -1)
        ) != 0:
            raise Phase29PopulationError("Phase28 protected evidence was consumed")
        if p28.get("protected_holdout_consumed") is not False:
            raise Phase29PopulationError("Phase28 holdout state is not unopened")
        return observation, p26, p27, p28

    def _source_frames(self, observation: dict[str, object]) -> tuple[pd.DataFrame, pd.DataFrame]:
        development_path = self.phase26.development_path()
        protected_path = self.phase26.protected_predictors_path()
        if observation.get("development_sha256") != sha256_file(development_path):
            raise Phase29PopulationError("Phase26 development source SHA mismatch")
        if observation.get("protected_predictors_sha256") != sha256_file(protected_path):
            raise Phase29PopulationError("Phase26 protected source SHA mismatch")
        development = _normalize_source_dates(
            _read_parquet(development_path, order_by="as_of_date, instrument_id")
        )
        protected = _normalize_source_dates(
            _read_parquet(protected_path, order_by="as_of_date, instrument_id")
        )
        if development.empty or protected.empty:
            raise Phase29PopulationError("Phase29 source population is empty")
        if set(development["contract_version"].astype(str)) != {
            PHASE26_DEVELOPMENT_OBSERVATION_CONTRACT_VERSION
        }:
            raise Phase29PopulationError("Phase26 development row contract mismatch")
        if set(protected["contract_version"].astype(str)) != {
            PHASE26_PROTECTED_PREDICTOR_CONTRACT_VERSION
        }:
            raise Phase29PopulationError("Phase26 protected row contract mismatch")
        forbidden = [field for field in PHASE29_FORBIDDEN_PROTECTED_OUTCOME_FIELDS if field in protected]
        if forbidden:
            raise Phase29PopulationError(
                "Phase29 protected source contains outcomes: " + ", ".join(sorted(forbidden))
            )
        return development, protected

    def _calendar_sessions(self) -> tuple[date, ...]:
        sessions = tuple(
            self.calendar.sessions_in_range(date(2021, 1, 4), date.fromisoformat(PHASE29_PROTECTED_END))
        )
        if not sessions:
            raise Phase29PopulationError("Phase29 exchange calendar is empty")
        return sessions

    def _history_rows(
        self, source: pd.DataFrame, *, splits: pd.DataFrame
    ) -> tuple[pd.DataFrame, dict[date, tuple[date, ...]], dict[date, int], dict[date, int]]:
        sessions = self._calendar_sessions()
        session_index = {session: index for index, session in enumerate(sessions)}
        split_dates = _split_lookup(splits)
        peer_records: list[dict[str, object]] = []
        expected_by_date: dict[date, tuple[date, ...]] = {}
        source_counts: dict[date, int] = {}
        safe_counts: dict[date, int] = {}

        for observation_date, group in source.groupby("as_of_date", sort=True, observed=True):
            source_counts[observation_date] = int(len(group))
            position = session_index.get(observation_date)
            if position is None or position < PHASE29_REQUIRED_CLOSES - 1:
                safe_counts[observation_date] = 0
                continue
            expected = sessions[position - (PHASE29_REQUIRED_CLOSES - 1) : position + 1]
            if len(expected) != PHASE29_REQUIRED_CLOSES:
                raise Phase29PopulationError("Phase29 exact history geometry failed")
            expected_by_date[observation_date] = expected
            history_start = expected[0]
            safe = 0
            for row in group.itertuples(index=False):
                if row.safe_start_date > history_start or row.safe_end_date < observation_date:
                    continue
                ticker = str(row.ticker)
                if _crosses_split(
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
                safe += 1
            safe_counts[observation_date] = safe

        peers = pd.DataFrame.from_records(
            peer_records,
            columns=["observation_date", "history_start", "peer_instrument_id", "ticker"],
        )
        if peers.empty:
            raise Phase29PopulationError("Phase29 has no PIT/split-safe histories")
        if peers.duplicated(["observation_date", "peer_instrument_id"]).any():
            raise Phase29PopulationError("Phase29 history plan contains duplicate instrument keys")

        con = connect_utc(":memory:")
        try:
            con.register("phase29_peer_plan", peers)
            bars = self.paths.glob_for_timeframe(Timeframe.DAY_1)
            history = con.execute(
                f"""
                SELECT
                    CAST(p.observation_date AS DATE) AS observation_date,
                    p.peer_instrument_id,
                    p.ticker,
                    CAST(b.session_date AS DATE) AS history_date,
                    CAST(b.close AS DOUBLE) AS close
                FROM phase29_peer_plan p
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
            raise Phase29PopulationError("Phase29 canonical daily history query is empty")
        history["observation_date"] = pd.to_datetime(history["observation_date"]).dt.date
        history["history_date"] = pd.to_datetime(history["history_date"]).dt.date
        if history.duplicated(
            ["observation_date", "peer_instrument_id", "history_date"], keep=False
        ).any():
            raise Phase29PopulationError("Phase29 daily history join is non-unique")
        return history, expected_by_date, source_counts, safe_counts

    def _relative_value_frame(
        self, source: pd.DataFrame, *, splits: pd.DataFrame, development: bool
    ) -> tuple[pd.DataFrame, dict[str, int]]:
        history, expected_by_date, source_counts, safe_counts = self._history_rows(
            source, splits=splits
        )
        source_by_date = {
            session: group.copy()
            for session, group in source.groupby("as_of_date", sort=True, observed=True)
        }
        history_by_date = {
            session: group.copy()
            for session, group in history.groupby("observation_date", sort=True, observed=True)
        }
        records: list[dict[str, object]] = []
        insufficient_complete_peers = 0
        pca_fail_sessions = 0
        focal_missing_pair = 0
        focal_missing_pca = 0

        for observation_date in sorted(source_by_date):
            expected = expected_by_date.get(observation_date)
            history_group = history_by_date.get(observation_date)
            if expected is None or history_group is None or history_group.empty:
                insufficient_complete_peers += 1
                continue
            close_matrix = history_group.pivot(
                index="history_date", columns="peer_instrument_id", values="close"
            ).reindex(expected)
            numeric = close_matrix.apply(pd.to_numeric, errors="coerce").astype(float)
            complete = np.isfinite(numeric.to_numpy(dtype=float)).all(axis=0) & (
                numeric.to_numpy(dtype=float) > 0
            ).all(axis=0)
            numeric = numeric.loc[:, complete]
            if len(numeric.columns) < PHASE29_PCA_MIN_PEERS:
                insufficient_complete_peers += 1
                continue
            formation_61 = numeric.iloc[:-1]
            formation_returns = formation_61.pct_change(fill_method=None).iloc[1:]
            if len(formation_returns) != 60:
                raise Phase29PopulationError("Phase29 formation return count drifted")
            current_returns = numeric.iloc[-1] / numeric.iloc[-2] - 1.0
            pair_formation = formation_61.iloc[-60:]
            try:
                pca = pca_residual_dislocations(formation_returns, current_returns)
            except (ValueError, RuntimeError):
                pca_fail_sessions += 1
                continue
            pairs = nearest_pair_dislocations(pair_formation, numeric.iloc[-1])

            for row in source_by_date[observation_date].itertuples(index=False):
                focal_id = str(row.instrument_id)
                pca_item = pca.get(focal_id)
                pair_item = pairs.get(focal_id)
                if pca_item is None:
                    focal_missing_pca += 1
                    continue
                if pair_item is None:
                    focal_missing_pair += 1
                    continue
                base = row._asdict()
                base.update(
                    {
                        "pca_residual_dislocation": pca_item.residual_dislocation,
                        "phase29_pca_current_standardized_return": pca_item.current_standardized_return,
                        "phase29_pca_factor_reconstruction": pca_item.factor_reconstruction,
                        "phase29_pca_peer_count": pca_item.peer_count,
                        "distance_pair_spread_z": pair_item.spread_z,
                        "phase29_pair_peer_instrument_id": pair_item.peer_instrument_id,
                        "phase29_pair_formation_distance": pair_item.formation_distance,
                        "phase29_pair_formation_spread_mean": pair_item.formation_spread_mean,
                        "phase29_pair_formation_spread_std": pair_item.formation_spread_std,
                        "phase29_pair_current_spread": pair_item.current_spread,
                        "phase29_source_peer_count": source_counts.get(observation_date, 0),
                        "phase29_safe_history_peer_count": safe_counts.get(observation_date, 0),
                        "phase29_complete_history_peer_count": int(len(numeric.columns)),
                    }
                )
                records.append(base)

        frame = pd.DataFrame.from_records(records)
        if frame.empty:
            raise Phase29PopulationError("Phase29 relative-value construction produced zero rows")
        frame["as_of_date"] = pd.to_datetime(frame["as_of_date"]).dt.date
        for field in PHASE29_RAW_SIGNAL_FIELDS:
            frame[field] = pd.to_numeric(frame[field], errors="coerce")
        finite = np.isfinite(frame[list(PHASE29_RAW_SIGNAL_FIELDS)].to_numpy(dtype=float)).all(axis=1)
        if development:
            if "directional_return" not in frame.columns:
                raise Phase29PopulationError("Phase29 development frame lost directional return")
            directional = pd.to_numeric(frame["directional_return"], errors="coerce").to_numpy(dtype=float)
            finite &= np.isfinite(directional)
        frame = frame.loc[finite].copy()
        frame = frame.loc[frame["direction"].astype(str).isin(("bullish", "bearish"))].copy()
        counts = frame.groupby(["as_of_date", "direction"], sort=False, observed=True)[
            "instrument_id"
        ].transform("size")
        frame = frame.loc[counts >= PHASE29_MIN_DIRECTION_ROWS_PER_SESSION].copy()
        if frame.empty:
            raise Phase29PopulationError("Phase29 complete-case gate removed all rows")
        if frame.duplicated(["as_of_date", "instrument_id"], keep=False).any():
            raise Phase29PopulationError("Phase29 population contains duplicate candidate keys")
        diagnostics = {
            "source_rows": int(len(source)),
            "complete_relative_value_rows": int(len(frame)),
            "insufficient_complete_peer_sessions": int(insufficient_complete_peers),
            "pca_fail_sessions": int(pca_fail_sessions),
            "focal_missing_pca": int(focal_missing_pca),
            "focal_missing_pair": int(focal_missing_pair),
        }
        return frame.sort_values(["as_of_date", "instrument_id"], kind="stable").reset_index(
            drop=True
        ), diagnostics

    def run(self) -> dict[str, object]:
        observation, p26, p27, p28 = self._source_evidence()
        development, protected = self._source_frames(observation)
        splits, split_path, split_sha = self.phase26._split_evidence()
        development_frame, development_diagnostics = self._relative_value_frame(
            development, splits=splits, development=True
        )
        protected_frame, protected_diagnostics = self._relative_value_frame(
            protected, splits=splits, development=False
        )
        protected_dates = pd.to_datetime(protected_frame["as_of_date"]).dt.date
        if protected_dates.min().isoformat() != PHASE29_PROTECTED_START:
            raise Phase29PopulationError("Phase29 protected start drifted")
        if protected_dates.max().isoformat() != PHASE29_PROTECTED_END:
            raise Phase29PopulationError("Phase29 protected end drifted")
        forbidden = [field for field in PHASE29_FORBIDDEN_PROTECTED_OUTCOME_FIELDS if field in protected_frame]
        if forbidden:
            raise Phase29PopulationError(
                "Phase29 protected frame leaked outcomes: " + ", ".join(sorted(forbidden))
            )

        development_frame.insert(0, "phase29_contract_version", PHASE29_DEVELOPMENT_FRAME_CONTRACT_VERSION)
        protected_frame.insert(0, "phase29_contract_version", PHASE29_PROTECTED_FRAME_CONTRACT_VERSION)
        development_path = self.development_path()
        protected_path = self.protected_path()
        _write_parquet(
            self.settings, development_frame, development_path, order_by="as_of_date, instrument_id"
        )
        _write_parquet(
            self.settings, protected_frame, protected_path, order_by="as_of_date, instrument_id"
        )

        checks = {
            "phase26_observation_pass": observation.get("pass") is True,
            "phase26_accepted_negative": p26.get("phase26_disposition") == "ACCEPTED_NEGATIVE",
            "phase27_accepted_negative": p27.get("phase27_disposition") == "ACCEPTED_NEGATIVE",
            "phase28_accepted_negative": p28.get("phase28_disposition") == "ACCEPTED_NEGATIVE",
            "phase28_holdout_unconsumed": p28.get("protected_holdout_consumed") is False,
            "phase28_merge_frozen": PHASE29_SOURCE_PHASE28_MERGE
            == "285f112d51463dd1e06ea4e874a882ad98f71dc5",
            "development_nonempty": len(development_frame) > 0,
            "protected_nonempty": len(protected_frame) > 0,
            "all_signal_fields_present": all(
                field in development_frame.columns and field in protected_frame.columns
                for field in PHASE29_RAW_SIGNAL_FIELDS
            ),
            "protected_outcomes_absent": not forbidden,
            "required_close_count_62": PHASE29_REQUIRED_CLOSES == 62,
            "external_activity_zero": True,
        }
        if not all(checks.values()):
            failed = sorted(name for name, passed in checks.items() if not passed)
            raise Phase29PopulationError("Phase29 population checks failed: " + ", ".join(failed))

        report_path = self.report_path()
        report: dict[str, Any] = {
            "contract_version": PHASE29_POPULATION_REPORT_CONTRACT_VERSION,
            "phase29_policy_fingerprint": phase29_policy_fingerprint(),
            "source_phase26_policy_fingerprint": PHASE29_SOURCE_PHASE26_POLICY_FINGERPRINT,
            "source_phase27_policy_fingerprint": PHASE29_SOURCE_PHASE27_POLICY_FINGERPRINT,
            "source_phase28_policy_fingerprint": PHASE29_SOURCE_PHASE28_POLICY_FINGERPRINT,
            "source_phase28_merge": PHASE29_SOURCE_PHASE28_MERGE,
            "phase26_observation_report_sha256": sha256_file(self.phase26.report_path()),
            "phase26_closeout_report_sha256": sha256_file(self.phase26_closeout.report_path()),
            "phase27_closeout_report_sha256": sha256_file(self.phase27_closeout.report_path()),
            "phase28_closeout_report_sha256": sha256_file(self.phase28_closeout.report_path()),
            "phase26_development_sha256": sha256_file(self.phase26.development_path()),
            "phase26_protected_predictors_sha256": sha256_file(self.phase26.protected_predictors_path()),
            "split_evidence_path": str(split_path.resolve()),
            "split_evidence_sha256": split_sha,
            "development_diagnostics": development_diagnostics,
            "protected_diagnostics": protected_diagnostics,
            "development_relative_value_rows": int(len(development_frame)),
            "protected_relative_value_rows": int(len(protected_frame)),
            "raw_signal_fields": list(PHASE29_RAW_SIGNAL_FIELDS),
            "required_close_sessions": PHASE29_REQUIRED_CLOSES,
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
