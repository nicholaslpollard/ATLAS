from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Sequence

import duckdb
import pandas as pd

from packages.backtesting.recurrent_successor_outcome_replay_contract import (
    AUTHORITY,
    INITIAL_POSITION_FRACTION,
    MAX_OPEN_POSITIONS,
    MAX_POSITIONS_PER_FAMILY,
    NORMALIZED_ENTRY_PRICE,
    RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT,
    RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT,
)
from packages.backtesting.successor_conditioning_analysis import (
    SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
    build_walk_forward_folds,
    validate_accepted_standalone,
)
from packages.core.market_calendar import get_market_calendar
from packages.execution.stock_economics import StockEconomicsInputs
from packages.execution.trade_expression import ActionabilityPolicy, TradeExpressionMode
from packages.schemas.discovery_score import DiscoveryDirection
from packages.schemas.move_time_forecast import (
    ForecastAvailability,
    ForecastHorizonUnit,
    MoveThresholdProbability,
    UnderlyingMoveTimeForecast,
)
from packages.simulation.decision_record import (
    SimulationDecisionRecord,
    build_simulation_decision_record,
)
from packages.simulation.recurrent_engine import RecurrentLifecycleCoordinatorV1
from packages.simulation.recurrent_entry_evidence import (
    build_recurrent_entry_fill_evidence,
    build_recurrent_funding_terms,
)
from packages.simulation.recurrent_exit_fill import (
    RecurrentExitFillInputsV1,
    build_recurrent_exit_fill_evidence,
)
from packages.simulation.recurrent_genesis import build_empty_recurrent_genesis_account_v1
from packages.simulation.recurrent_lifecycle_state import RecurrentLifecycleEventKind
from packages.simulation.simulated_fill import SimulatedEntryFillInputs
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
    DAILY_PRIMARY_COST_BPS,
    DAILY_PRIMARY_HORIZON_SESSIONS,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    INTRADAY_PRIMARY_COST_BPS,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)


class RecurrentSuccessorOutcomeReplayError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SelectedReplayOpportunity:
    opportunity_id: str
    fold_id: int
    policy_id: str
    economic_family_id: str
    native_timeframe: str
    instrument_id: str
    ticker: str
    signal_session: date
    direction: str
    fallback_level: int
    selector_score: float
    primary_net_return: float
    gross_return: float
    liquidity_bucket: str
    decision_utc: datetime
    entry_utc: datetime
    exit_utc: datetime
    round_trip_cost_bps: float
    training_start: date
    training_end: date
    training_sample_size: int
    training_mean_gross_return: float
    training_p10_gross_return: float
    training_p25_gross_return: float
    training_median_gross_return: float
    training_p75_gross_return: float
    training_p90_gross_return: float
    training_probability_positive_gross: float
    training_probability_positive_net: float
    training_mean_mfe: float
    training_mean_mae: float
    training_max_abs_excursion: float
    training_median_holding_minutes: float | None
    source_analysis_fingerprint: str


@dataclass(slots=True)
class _Slot:
    opportunity: SelectedReplayOpportunity
    decision: SimulationDecisionRecord
    position_fingerprint: str | None = None
    state: str = "RESERVED"


def _canonicalize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value):
        return {
            field.name: _canonicalize(getattr(value, field.name))
            for field in fields(value)
        }
    if isinstance(value, dict):
        return {str(key): _canonicalize(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_canonicalize(item) for item in value]
    return value


def _stable_hash(payload: object) -> str:
    raw = json.dumps(
        _canonicalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RecurrentSuccessorOutcomeReplayError(
            f"invalid JSON artifact: {path}"
        ) from exc
    if not isinstance(value, dict):
        raise RecurrentSuccessorOutcomeReplayError(
            f"JSON artifact is not an object: {path}"
        )
    return value


def _validate_receipt(path: Path, *, phase: str) -> dict[str, object]:
    receipt_path = path.with_suffix(path.suffix + ".receipt.json")
    if not path.is_file() or not receipt_path.is_file():
        raise RecurrentSuccessorOutcomeReplayError(
            f"required conditioning artifact/receipt is missing: {path}"
        )
    receipt = _load_json(receipt_path)
    receipt_body = {key: value for key, value in receipt.items() if key != "receipt_id"}
    if receipt.get("receipt_id") != _stable_hash(receipt_body):
        raise RecurrentSuccessorOutcomeReplayError(
            f"conditioning receipt self-hash drifted: {receipt_path}"
        )
    if receipt.get("contract") != SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT:
        raise RecurrentSuccessorOutcomeReplayError(
            f"conditioning receipt contract drifted: {receipt_path}"
        )
    if receipt.get("conditioning_fingerprint") != SUCCESSOR_CONDITIONING_FINGERPRINT:
        raise RecurrentSuccessorOutcomeReplayError(
            f"conditioning receipt fingerprint drifted: {receipt_path}"
        )
    if receipt.get("phase") != phase:
        raise RecurrentSuccessorOutcomeReplayError(
            f"conditioning receipt phase drifted: {receipt_path}"
        )
    if receipt.get("artifact_path") != str(path.resolve()):
        raise RecurrentSuccessorOutcomeReplayError(
            f"conditioning receipt path drifted: {receipt_path}"
        )
    if receipt.get("artifact_sha256") != _sha256_file(path):
        raise RecurrentSuccessorOutcomeReplayError(
            f"conditioning artifact SHA-256 drifted: {path}"
        )
    return receipt


def _conditioning_root(project_root: Path) -> tuple[Path, dict[str, object]]:
    standalone_root, standalone_summary, _ = validate_accepted_standalone(project_root)
    standalone = standalone_summary.get("standalone")
    if not isinstance(standalone, dict):
        raise RecurrentSuccessorOutcomeReplayError(
            "accepted standalone summary structure drifted"
        )
    if (
        standalone.get("artifact_set_fingerprint")
        != ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT
    ):
        raise RecurrentSuccessorOutcomeReplayError(
            "accepted standalone artifact-set fingerprint drifted"
        )
    root = (
        standalone_root
        / "conditioning_v1"
        / SUCCESSOR_CONDITIONING_FINGERPRINT[:16]
    ).resolve()
    summary_path = root / "analysis_summary.json"
    if not summary_path.is_file():
        raise RecurrentSuccessorOutcomeReplayError(
            f"accepted successor conditioning analysis is missing: {summary_path}"
        )
    summary = _load_json(summary_path)
    required = {
        "status": "COMPLETE_CONDITIONING_ONLY",
        "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
        "conditioning_opened": True,
        "confluence_opened": False,
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
    }
    for key, expected in required.items():
        if summary.get(key) != expected:
            raise RecurrentSuccessorOutcomeReplayError(
                f"conditioning summary {key} drifted"
            )
    accepted = summary.get("accepted_standalone")
    if (
        not isinstance(accepted, dict)
        or accepted.get("artifact_set_fingerprint")
        != ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT
    ):
        raise RecurrentSuccessorOutcomeReplayError(
            "conditioning summary standalone binding drifted"
        )
    analysis_fingerprint = str(summary.get("analysis_fingerprint") or "")
    if len(analysis_fingerprint) != 64:
        raise RecurrentSuccessorOutcomeReplayError(
            "conditioning analysis fingerprint is missing or malformed"
        )
    return root, summary


def _normalize_timestamp(value: object, *, label: str) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        raise RecurrentSuccessorOutcomeReplayError(
            f"{label} must be timezone-aware"
        )
    return stamp.to_pydatetime().astimezone(UTC)


def _future_sessions(signal_session: date, count: int) -> list[date]:
    calendar = get_market_calendar()
    cursor = signal_session + timedelta(days=1)
    sessions: list[date] = []
    while len(sessions) < count:
        end = cursor + timedelta(days=31)
        block = calendar.sessions_in_range(cursor, end)
        sessions.extend(item for item in block if item > signal_session)
        if len(sessions) >= count:
            break
        cursor = end + timedelta(days=1)
        if cursor > signal_session + timedelta(days=370):
            raise RecurrentSuccessorOutcomeReplayError(
                f"unable to resolve {count} future XNYS sessions after {signal_session}"
            )
    return sessions[:count]


def _daily_event_times(signal_session: date) -> tuple[datetime, datetime, datetime]:
    calendar = get_market_calendar()
    if not calendar.is_session(signal_session):
        raise RecurrentSuccessorOutcomeReplayError(
            f"daily signal date is not an XNYS session: {signal_session}"
        )
    _, decision_utc = calendar.regular_open_close(signal_session)
    future = _future_sessions(signal_session, DAILY_PRIMARY_HORIZON_SESSIONS)
    entry_utc, _ = calendar.regular_open_close(future[0])
    _, exit_utc = calendar.regular_open_close(
        future[DAILY_PRIMARY_HORIZON_SESSIONS - 1]
    )
    return decision_utc, entry_utc, exit_utc


def _event_times(
    *,
    native_timeframe: str,
    signal_session: date,
    entry_time_utc: object,
    exit_time_utc: object,
) -> tuple[datetime, datetime, datetime]:
    if native_timeframe == "1d":
        return _daily_event_times(signal_session)
    if native_timeframe != "1m":
        raise RecurrentSuccessorOutcomeReplayError(
            f"unsupported successor replay timeframe: {native_timeframe}"
        )
    entry = _normalize_timestamp(entry_time_utc, label="intraday entry timestamp")
    exit_time = _normalize_timestamp(exit_time_utc, label="intraday exit timestamp")
    if exit_time < entry:
        raise RecurrentSuccessorOutcomeReplayError(
            "intraday exit timestamp precedes entry"
        )
    # The retained normalized artifact does not preserve exact signal-availability
    # UTC. For this outcome replay the decision is conservatively materialized no
    # earlier than the accepted executable entry timestamp.
    return entry, entry, exit_time


def _source_integrity(
    root: Path,
) -> tuple[Path, Path, str]:
    assignments = root / "eligibility_assignments.parquet"
    assignment_receipt = _validate_receipt(
        assignments,
        phase="ELIGIBILITY_ASSIGNMENTS",
    )
    normalized_dir = root / "normalized"
    normalized_paths = sorted(normalized_dir.glob("*.parquet"))
    if not normalized_paths:
        raise RecurrentSuccessorOutcomeReplayError(
            "conditioning normalized artifact set is empty"
        )
    normalized_identity: list[dict[str, object]] = []
    print(
        f"recurrent replay source integrity: verifying {len(normalized_paths):,} normalized parts",
        flush=True,
    )
    for part_index, path in enumerate(normalized_paths, start=1):
        receipt = _validate_receipt(path, phase="NORMALIZE_PART")
        if part_index % 50 == 0 or part_index == len(normalized_paths):
            print(
                f"  source integrity: {part_index:,}/{len(normalized_paths):,} parts verified",
                flush=True,
            )
        normalized_identity.append(
            {
                "name": path.name,
                "sha256": receipt["artifact_sha256"],
                "row_count": int(receipt["row_count"]),
            }
        )
    source_fingerprint = _stable_hash(
        {
            "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
            "eligibility_assignments_sha256": assignment_receipt["artifact_sha256"],
            "normalized_artifacts": normalized_identity,
        }
    )
    return assignments, normalized_dir, source_fingerprint


def _policy_filter_sql(policy_ids: Sequence[str]) -> str:
    if not policy_ids:
        return ""
    escaped = [str(value).replace("'", "''") for value in sorted(set(policy_ids))]
    return " AND a.policy_id IN (" + ",".join(f"'{value}'" for value in escaped) + ")"


def load_selected_replay_opportunities(
    project_root: Path,
    *,
    start_session: date,
    end_session: date,
    policy_ids: Sequence[str] = (),
    duckdb_threads: int | None = None,
) -> tuple[tuple[SelectedReplayOpportunity, ...], dict[str, object]]:
    development_start = date.fromisoformat(DEVELOPMENT_START)
    development_end = date.fromisoformat(DEVELOPMENT_END)
    if not development_start <= start_session <= end_session <= development_end:
        raise RecurrentSuccessorOutcomeReplayError(
            "replay signal scope must stay inside successor DEVELOPMENT"
        )

    root, analysis_summary = _conditioning_root(project_root)
    assignments, normalized_dir, source_fingerprint = _source_integrity(root)
    analysis_fingerprint = str(analysis_summary["analysis_fingerprint"])
    print(
        "recurrent replay selection: scanning accepted conditioning assignments "
        "and training cells",
        flush=True,
    )

    threads = int(
        duckdb_threads
        if duckdb_threads is not None
        else max(1, min(8, (os.cpu_count() or 4) - 2))
    )
    if threads < 1:
        raise RecurrentSuccessorOutcomeReplayError(
            "DuckDB thread count must be positive"
        )

    folds = build_walk_forward_folds(development_start, development_end)
    folds_frame = pd.DataFrame([asdict(item) for item in folds])
    conn = duckdb.connect()
    try:
        conn.execute(f"PRAGMA threads={threads}")
        conn.execute("PRAGMA preserve_insertion_order=false")
        conn.register("replay_folds", folds_frame)
        normalized_glob = normalized_dir / "*.parquet"
        conn.execute(
            "CREATE OR REPLACE TEMP VIEW opportunities AS "
            f"SELECT * FROM read_parquet('{_sql_path(normalized_glob)}', union_by_name=true)"
        )
        conn.execute(
            "CREATE OR REPLACE TEMP VIEW assignments AS "
            f"SELECT * FROM read_parquet('{_sql_path(assignments)}')"
        )
        policy_filter = _policy_filter_sql(policy_ids)
        print(
            "  selection phase 1/3: materializing selected comparable test opportunities",
            flush=True,
        )
        selected_sql = f"""
            CREATE OR REPLACE TEMP TABLE selected_replay AS
            SELECT
                a.fold_id,
                a.policy_id,
                a.economic_family_id,
                a.native_timeframe,
                a.instrument_key,
                a.ticker,
                a.session_date,
                a.direction,
                a.fallback_level,
                a.selector_score,
                a.primary_net_return,
                a.stress_net_return,
                a.liquidity_bucket,
                o.gross_return,
                o.mfe,
                o.mae,
                o.entry_time_utc,
                o.exit_time_utc,
                o.holding_minutes,
                CASE a.fallback_level
                    WHEN 1 THEN o.selector_key_1
                    WHEN 2 THEN o.selector_key_2
                    WHEN 3 THEN o.selector_key_3
                    WHEN 4 THEN o.selector_key_4
                    WHEN 5 THEN o.selector_key_5
                    ELSE NULL
                END AS selected_cell_key
            FROM assignments a
            JOIN opportunities o
              ON o.policy_id = a.policy_id
             AND o.economic_family_id = a.economic_family_id
             AND o.native_timeframe = a.native_timeframe
             AND o.instrument_key = a.instrument_key
             AND o.ticker = a.ticker
             AND o.session_date = a.session_date
             AND o.direction = a.direction
             AND o.primary_net_return IS NOT DISTINCT FROM a.primary_net_return
             AND o.stress_net_return IS NOT DISTINCT FROM a.stress_net_return
            WHERE a.research_eligible
              AND a.comparable
              AND a.session_date BETWEEN DATE '{start_session.isoformat()}'
                                     AND DATE '{end_session.isoformat()}'
              {policy_filter}
        """
        conn.execute(selected_sql)
        selected_count = int(
            conn.execute("SELECT count(*) FROM selected_replay").fetchone()[0]
        )
        print(
            f"  selection phase 1/3 complete: {selected_count:,} opportunities",
            flush=True,
        )
        duplicate = conn.execute(
            """
            SELECT policy_id, instrument_key, session_date, direction, count(*) AS n
            FROM selected_replay
            GROUP BY 1,2,3,4
            HAVING count(*) != 1
            LIMIT 1
            """
        ).fetchone()
        if duplicate is not None:
            raise RecurrentSuccessorOutcomeReplayError(
                "selected successor opportunity identity is not unique: "
                + repr(tuple(duplicate))
            )
        invalid = conn.execute(
            """
            SELECT count(*)
            FROM selected_replay
            WHERE selector_score IS NULL
               OR selector_score <= 0
               OR fallback_level NOT BETWEEN 1 AND 5
               OR selected_cell_key IS NULL
               OR gross_return IS NULL
            """
        ).fetchone()[0]
        if int(invalid):
            raise RecurrentSuccessorOutcomeReplayError(
                "selected successor opportunity contains invalid selector/outcome evidence"
            )

        print(
            "  selection phase 2/3: resolving unique selected training cells",
            flush=True,
        )
        conn.execute(
            """
            CREATE OR REPLACE TEMP TABLE selected_cells AS
            SELECT DISTINCT
                fold_id,
                fallback_level,
                selected_cell_key AS cell_key,
                policy_id,
                direction
            FROM selected_replay
            """
        )
        selected_cell_count = int(
            conn.execute("SELECT count(*) FROM selected_cells").fetchone()[0]
        )
        print(
            f"  selection phase 2/3 complete: {selected_cell_count:,} unique cells",
            flush=True,
        )
        print(
            "  selection phase 3/3: building training-only distributions for selected cells",
            flush=True,
        )
        conn.execute(
            """
            CREATE OR REPLACE TEMP TABLE training_cell_stats AS
            SELECT
                c.fold_id,
                c.fallback_level,
                c.cell_key,
                c.policy_id,
                c.direction,
                min(f.train_start) AS training_start,
                max(f.train_end) AS training_end,
                count(*) AS sample_size,
                avg(o.gross_return) AS mean_gross_return,
                quantile_cont(o.gross_return, 0.10) AS p10_gross_return,
                quantile_cont(o.gross_return, 0.25) AS p25_gross_return,
                median(o.gross_return) AS median_gross_return,
                quantile_cont(o.gross_return, 0.75) AS p75_gross_return,
                quantile_cont(o.gross_return, 0.90) AS p90_gross_return,
                avg(CASE WHEN o.gross_return > 0 THEN 1.0 ELSE 0.0 END)
                    AS probability_positive_gross,
                avg(CASE WHEN o.primary_net_return > 0 THEN 1.0 ELSE 0.0 END)
                    AS probability_positive_net,
                avg(greatest(coalesce(o.mfe, 0.0), 0.0)) AS mean_mfe,
                avg(abs(coalesce(o.mae, 0.0))) AS mean_mae,
                max(greatest(abs(coalesce(o.mfe, 0.0)), abs(coalesce(o.mae, 0.0))))
                    AS max_abs_excursion,
                median(o.holding_minutes) FILTER (WHERE o.holding_minutes > 0)
                    AS median_holding_minutes
            FROM selected_cells c
            JOIN replay_folds f ON f.fold_id = c.fold_id
            JOIN opportunities o
              ON o.session_date BETWEEN f.train_start AND f.train_end
             AND o.policy_id = c.policy_id
             AND o.direction = c.direction
             AND o.eligible_opportunity
             AND o.comparable
             AND o.gross_return IS NOT NULL
             AND CASE c.fallback_level
                    WHEN 1 THEN o.selector_key_1
                    WHEN 2 THEN o.selector_key_2
                    WHEN 3 THEN o.selector_key_3
                    WHEN 4 THEN o.selector_key_4
                    WHEN 5 THEN o.selector_key_5
                    ELSE NULL
                 END = c.cell_key
            GROUP BY 1,2,3,4,5
            """
        )
        training_cell_count = int(
            conn.execute("SELECT count(*) FROM training_cell_stats").fetchone()[0]
        )
        print(
            f"  selection phase 3/3 complete: {training_cell_count:,} training distributions",
            flush=True,
        )
        print(
            "  selection finalization: joining selected opportunities to training evidence",
            flush=True,
        )
        rows = conn.execute(
            """
            SELECT
                s.*,
                t.training_start,
                t.training_end,
                t.sample_size,
                t.mean_gross_return,
                t.p10_gross_return,
                t.p25_gross_return,
                t.median_gross_return,
                t.p75_gross_return,
                t.p90_gross_return,
                t.probability_positive_gross,
                t.probability_positive_net,
                t.mean_mfe,
                t.mean_mae,
                t.max_abs_excursion,
                t.median_holding_minutes
            FROM selected_replay s
            JOIN training_cell_stats t
              ON t.fold_id = s.fold_id
             AND t.fallback_level = s.fallback_level
             AND t.cell_key = s.selected_cell_key
             AND t.policy_id = s.policy_id
             AND t.direction = s.direction
            ORDER BY s.session_date, s.policy_id, s.instrument_key, s.direction
            """
        ).fetchdf()
    finally:
        conn.close()

    opportunities: list[SelectedReplayOpportunity] = []
    for record in rows.to_dict("records"):
        signal_session = pd.Timestamp(record["session_date"]).date()
        decision_utc, entry_utc, exit_utc = _event_times(
            native_timeframe=str(record["native_timeframe"]),
            signal_session=signal_session,
            entry_time_utc=record["entry_time_utc"],
            exit_time_utc=record["exit_time_utc"],
        )
        training_end = pd.Timestamp(record["training_end"]).date()
        _, training_cutoff = get_market_calendar().regular_open_close(training_end)
        if training_cutoff >= decision_utc:
            raise RecurrentSuccessorOutcomeReplayError(
                "training evidence cutoff is not strictly before replay decision"
            )
        native = str(record["native_timeframe"])
        cost_bps = (
            float(DAILY_PRIMARY_COST_BPS)
            if native == "1d"
            else float(INTRADAY_PRIMARY_COST_BPS)
        )
        gross_return = float(record["gross_return"])
        direction = str(record["direction"]).upper()
        if not math.isfinite(gross_return):
            raise RecurrentSuccessorOutcomeReplayError(
                "selected replay gross return is non-finite"
            )
        half = cost_bps / 20_000.0
        if direction == "LONG":
            if gross_return <= -1.0:
                raise RecurrentSuccessorOutcomeReplayError(
                    "long replay gross return is <= -100%"
                )
            normalized_exit = NORMALIZED_ENTRY_PRICE * (1.0 + gross_return)
            expected_primary = (
                normalized_exit * (1.0 - half)
                - NORMALIZED_ENTRY_PRICE * (1.0 + half)
            ) / NORMALIZED_ENTRY_PRICE
        elif direction == "SHORT":
            if gross_return >= 1.0:
                raise RecurrentSuccessorOutcomeReplayError(
                    "short replay gross return is >= 100%"
                )
            normalized_exit = NORMALIZED_ENTRY_PRICE * (1.0 - gross_return)
            expected_primary = (
                NORMALIZED_ENTRY_PRICE * (1.0 - half)
                - normalized_exit * (1.0 + half)
            ) / NORMALIZED_ENTRY_PRICE
        else:
            raise RecurrentSuccessorOutcomeReplayError(
                f"unsupported selected replay direction: {direction}"
            )
        if not math.isclose(
            expected_primary,
            float(record["primary_net_return"]),
            rel_tol=1e-10,
            abs_tol=1e-10,
        ):
            raise RecurrentSuccessorOutcomeReplayError(
                "normalized replay cost arithmetic does not match accepted primary return"
            )
        identity = {
            "fold_id": int(record["fold_id"]),
            "policy_id": str(record["policy_id"]),
            "instrument_id": str(record["instrument_key"]),
            "session_date": signal_session.isoformat(),
            "direction": str(record["direction"]),
            "conditioning_analysis_fingerprint": analysis_fingerprint,
        }
        opportunities.append(
            SelectedReplayOpportunity(
                opportunity_id=_stable_hash(identity),
                fold_id=int(record["fold_id"]),
                policy_id=str(record["policy_id"]),
                economic_family_id=str(record["economic_family_id"]),
                native_timeframe=native,
                instrument_id=str(record["instrument_key"]),
                ticker=str(record["ticker"]),
                signal_session=signal_session,
                direction=direction,
                fallback_level=int(record["fallback_level"]),
                selector_score=float(record["selector_score"]),
                primary_net_return=float(record["primary_net_return"]),
                gross_return=gross_return,
                liquidity_bucket=str(record["liquidity_bucket"]),
                decision_utc=decision_utc,
                entry_utc=entry_utc,
                exit_utc=exit_utc,
                round_trip_cost_bps=cost_bps,
                training_start=pd.Timestamp(record["training_start"]).date(),
                training_end=training_end,
                training_sample_size=int(record["sample_size"]),
                training_mean_gross_return=float(record["mean_gross_return"]),
                training_p10_gross_return=float(record["p10_gross_return"]),
                training_p25_gross_return=float(record["p25_gross_return"]),
                training_median_gross_return=float(record["median_gross_return"]),
                training_p75_gross_return=float(record["p75_gross_return"]),
                training_p90_gross_return=float(record["p90_gross_return"]),
                training_probability_positive_gross=float(
                    record["probability_positive_gross"]
                ),
                training_probability_positive_net=float(
                    record["probability_positive_net"]
                ),
                training_mean_mfe=float(record["mean_mfe"]),
                training_mean_mae=float(record["mean_mae"]),
                training_max_abs_excursion=float(record["max_abs_excursion"]),
                training_median_holding_minutes=(
                    None
                    if pd.isna(record["median_holding_minutes"])
                    else float(record["median_holding_minutes"])
                ),
                source_analysis_fingerprint=analysis_fingerprint,
            )
        )
    print(
        f"recurrent replay selection: {len(opportunities):,} selected comparable opportunities loaded",
        flush=True,
    )
    source = {
        "conditioning_root": str(root),
        "conditioning_analysis_fingerprint": analysis_fingerprint,
        "source_integrity_fingerprint": source_fingerprint,
        "selected_opportunity_count": len(opportunities),
        "duckdb_threads": threads,
    }
    return tuple(opportunities), source


def _training_forecast(
    opportunity: SelectedReplayOpportunity,
) -> UnderlyingMoveTimeForecast:
    if opportunity.direction != "LONG":
        raise RecurrentSuccessorOutcomeReplayError(
            "recurrent outcome replay v1 forecast supports LONG only"
        )
    mean = opportunity.training_mean_gross_return
    quantiles = (
        opportunity.training_p10_gross_return,
        opportunity.training_p25_gross_return,
        opportunity.training_median_gross_return,
        opportunity.training_p75_gross_return,
        opportunity.training_p90_gross_return,
    )
    if not all(math.isfinite(value) for value in (mean, *quantiles)):
        raise RecurrentSuccessorOutcomeReplayError(
            "training forecast distribution contains non-finite values"
        )
    if not (
        quantiles[0] <= quantiles[1] <= quantiles[2] <= quantiles[3] <= quantiles[4]
    ):
        raise RecurrentSuccessorOutcomeReplayError(
            "training forecast quantiles are not monotonic"
        )
    if not 0.0 <= opportunity.training_probability_positive_gross <= 1.0:
        raise RecurrentSuccessorOutcomeReplayError(
            "training gross-profit probability is outside [0,1]"
        )
    if opportunity.native_timeframe == "1d":
        horizon_unit = ForecastHorizonUnit.SESSIONS
        horizon_value = DAILY_PRIMARY_HORIZON_SESSIONS
    else:
        horizon_unit = ForecastHorizonUnit.MINUTES
        horizon_value = max(
            1,
            int(round(opportunity.training_median_holding_minutes or 1.0)),
        )
    threshold_fraction = max(
        0.01,
        opportunity.training_max_abs_excursion + 1e-6,
    )
    source_payload = {
        "conditioning_analysis_fingerprint": opportunity.source_analysis_fingerprint,
        "fold_id": opportunity.fold_id,
        "policy_id": opportunity.policy_id,
        "fallback_level": opportunity.fallback_level,
        "training_start": opportunity.training_start,
        "training_end": opportunity.training_end,
        "sample_size": opportunity.training_sample_size,
        "mean_gross_return": mean,
        "quantiles": quantiles,
        "probability_positive_gross": opportunity.training_probability_positive_gross,
        "mean_mfe": opportunity.training_mean_mfe,
        "mean_mae": opportunity.training_mean_mae,
        "max_abs_excursion": opportunity.training_max_abs_excursion,
        "median_holding_minutes": opportunity.training_median_holding_minutes,
    }
    _, evidence_cutoff = get_market_calendar().regular_open_close(
        opportunity.training_end
    )
    return UnderlyingMoveTimeForecast(
        availability=ForecastAvailability.AVAILABLE,
        instrument_id=opportunity.instrument_id,
        ticker=opportunity.ticker,
        direction=DiscoveryDirection.BULLISH,
        forecast_created_utc=opportunity.decision_utc,
        evidence_cutoff_utc=evidence_cutoff,
        horizon_unit=horizon_unit,
        horizon_value=horizon_value,
        method_id="SUCCESSOR_WALK_FORWARD_TRAINING_CELL_DISTRIBUTION_V1",
        source_label="SUCCESSOR_CONDITIONING_TRAINING_ONLY",
        source_fingerprint=_stable_hash(source_payload),
        sample_size=opportunity.training_sample_size,
        reference_price=NORMALIZED_ENTRY_PRICE,
        mean_signed_return=mean,
        median_signed_return=quantiles[2],
        p10_signed_return=quantiles[0],
        p25_signed_return=quantiles[1],
        p75_signed_return=quantiles[3],
        p90_signed_return=quantiles[4],
        probability_positive_return=opportunity.training_probability_positive_gross,
        mean_mfe=max(0.0, opportunity.training_mean_mfe),
        mean_mae=max(0.0, opportunity.training_mean_mae),
        thresholds=(
            MoveThresholdProbability(
                threshold_fraction=threshold_fraction,
                favorable_touch_probability=0.0,
                adverse_touch_probability=0.0,
                favorable_before_adverse_probability=0.0,
                adverse_before_favorable_probability=0.0,
                same_interval_collision_probability=0.0,
                median_favorable_time=None,
            ),
        ),
        uncertainty_score=None,
        reason_codes=(
            "WALK_FORWARD_TRAINING_ONLY_CELL_DISTRIBUTION",
            "TEST_OPPORTUNITY_OUTCOME_NOT_USED_IN_DECISION_FORECAST",
            "ABOVE_OBSERVED_EXCURSION_THRESHOLD_CARRIES_ZERO_TOUCH_PROBABILITY",
            "OUTCOME_REPLAY_EXIT_IS_SEPARATE_FROM_FORECAST_HORIZON",
        ),
    )


_ACTIONABILITY_POLICY = ActionabilityPolicy(
    min_expected_net_value=0.0,
    min_expected_return_on_capital=0.0,
    min_probability_profit=0.0,
    max_expected_loss_to_gain_ratio=1_000_000.0,
    max_execution_cost_to_expected_gain_ratio=1_000_000.0,
    min_liquidity_score=0.0,
    material_superiority_ratio=1.0,
)


def _liquidity_score(bucket: str) -> float:
    token = str(bucket).upper()
    if "GE_250M" in token or token == "HIGH":
        return 1.0
    if "50M_TO_250M" in token or token == "MEDIUM":
        return 0.9
    if "10M_TO_50M" in token or token == "BASE":
        return 0.75
    if "1M_TO_10M" in token:
        return 0.6
    if "LT_1M" in token or token == "INELIGIBLE":
        return 0.25
    return 0.5


def _build_decision(
    opportunity: SelectedReplayOpportunity,
    *,
    account_book_equity: float,
) -> tuple[SimulationDecisionRecord, float]:
    if not math.isfinite(account_book_equity) or account_book_equity <= 0.0:
        raise RecurrentSuccessorOutcomeReplayError(
            "positive current recurrent book equity is required for sizing"
        )
    notional = account_book_equity * INITIAL_POSITION_FRACTION
    half_cost_bps = opportunity.round_trip_cost_bps / 2.0
    entry_fee = notional * half_cost_bps / 10_000.0
    forecast = _training_forecast(opportunity)
    net_probability = min(
        opportunity.training_probability_positive_net,
        opportunity.training_probability_positive_gross,
    )
    inputs = StockEconomicsInputs(
        position_notional_dollars=notional,
        capital_required_dollars=notional + entry_fee,
        entry_slippage_bps=half_cost_bps,
        exit_slippage_bps=half_cost_bps,
        round_trip_commission_dollars=0.0,
        round_trip_fees_dollars=0.0,
        horizon_borrow_cost_dollars=0.0,
        horizon_financing_cost_dollars=0.0,
        net_probability_profit=max(0.0, net_probability),
        liquidity_score=_liquidity_score(opportunity.liquidity_bucket),
        executable=True,
        risk_budget_ok=True,
        shortable_if_bearish=False,
    )
    record = build_simulation_decision_record(
        decision_created_utc=opportunity.decision_utc,
        forecast=forecast,
        stock_inputs=inputs,
        actionability_policy=_ACTIONABILITY_POLICY,
        trade_expression_mode=TradeExpressionMode.STOCKS_ONLY,
        option_candidates=(),
    )
    return record, entry_fee


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(
            _canonicalize(payload),
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def _write_jsonl(path: Path, rows: Iterable[object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    digest = hashlib.sha256()
    with temp.open("wb") as handle:
        for item in rows:
            line = (
                json.dumps(
                    _canonicalize(item),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            handle.write(line)
            digest.update(line)
    os.replace(temp, path)
    return digest.hexdigest()


def _opportunity_payload(opportunity: SelectedReplayOpportunity) -> dict[str, object]:
    return _canonicalize(opportunity)


def run_recurrent_successor_outcome_replay(
    project_root: Path,
    *,
    initial_equity: float,
    start_session: date,
    end_session: date,
    policy_ids: Sequence[str] = (),
    output_root: Path | None = None,
    duckdb_threads: int | None = None,
) -> dict[str, object]:
    if not math.isfinite(initial_equity) or initial_equity <= 0.0:
        raise RecurrentSuccessorOutcomeReplayError(
            "initial equity must be finite and positive"
        )
    opportunities, source = load_selected_replay_opportunities(
        project_root,
        start_session=start_session,
        end_session=end_session,
        policy_ids=policy_ids,
        duckdb_threads=duckdb_threads,
    )
    if not opportunities:
        raise RecurrentSuccessorOutcomeReplayError(
            "selected replay scope contains no walk-forward eligible comparable opportunities"
        )

    long_opportunities = tuple(
        item for item in opportunities if item.direction == "LONG"
    )
    unsupported_short_count = sum(
        item.direction == "SHORT" for item in opportunities
    )
    if not long_opportunities:
        raise RecurrentSuccessorOutcomeReplayError(
            "selected replay scope contains no LONG opportunities supported by recurrent funding v1"
        )
    print(
        "recurrent replay portfolio: "
        f"{len(long_opportunities):,} LONG supported / "
        f"{unsupported_short_count:,} SHORT reported-only",
        flush=True,
    )

    run_identity = {
        "contract_fingerprint": RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT,
        "source_integrity_fingerprint": source["source_integrity_fingerprint"],
        "conditioning_analysis_fingerprint": source[
            "conditioning_analysis_fingerprint"
        ],
        "initial_equity": float(initial_equity),
        "start_session": start_session,
        "end_session": end_session,
        "policy_ids": sorted(set(str(value) for value in policy_ids)),
    }
    run_fingerprint = _stable_hash(run_identity)
    root = (
        Path(output_root).resolve()
        if output_root is not None
        else (
            Path(source["conditioning_root"])
            / "recurrent_outcome_replay"
            / RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT[:16]
            / run_fingerprint[:16]
        ).resolve()
    )
    root.mkdir(parents=True, exist_ok=True)

    first_event = min(item.decision_utc for item in long_opportunities)
    genesis_account, genesis_lineage = build_empty_recurrent_genesis_account_v1(
        initial_equity=float(initial_equity),
        as_of_utc=first_event - timedelta(microseconds=1),
    )
    coordinator = RecurrentLifecycleCoordinatorV1(account=genesis_account)

    # Event priorities: prior-position CLOSE -> RESERVE -> ENTRY -> same-bar CLOSE.
    events: list[tuple[datetime, int, float, str, str, int, str]] = []
    for index, item in enumerate(long_opportunities):
        tie_score = -item.selector_score
        events.append(
            (
                item.decision_utc,
                1,
                tie_score,
                item.policy_id,
                item.ticker,
                index,
                "RESERVE",
            )
        )
        events.append(
            (
                item.entry_utc,
                2,
                tie_score,
                item.policy_id,
                item.ticker,
                index,
                "ENTRY",
            )
        )
        close_priority = 3 if item.exit_utc == item.entry_utc else 0
        events.append(
            (
                item.exit_utc,
                close_priority,
                tie_score,
                item.policy_id,
                item.ticker,
                index,
                "CLOSE",
            )
        )
    events.sort()
    print(
        f"recurrent replay portfolio: scheduled {len(events):,} lifecycle events",
        flush=True,
    )

    slots: dict[int, _Slot] = {}
    decision_rows: list[dict[str, object]] = []
    closed_rows: list[dict[str, object]] = []
    equity_rows: list[dict[str, object]] = []
    rejection_counts: Counter[str] = Counter()
    policy_stats: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"selected": 0, "admitted": 0, "completed": 0, "net_pnl": 0.0}
    )
    family_stats: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"selected": 0, "admitted": 0, "completed": 0, "net_pnl": 0.0}
    )
    for item in opportunities:
        policy_stats[item.policy_id]["selected"] += 1
        family_stats[item.economic_family_id]["selected"] += 1

    peak_slots = 0
    peak_book_equity = float(initial_equity)
    maximum_book_drawdown = 0.0

    for event_number, (
        event_utc,
        _,
        _,
        _,
        _,
        index,
        event_kind,
    ) in enumerate(events, start=1):
        if event_number == 1 or event_number % 500 == 0 or event_number == len(events):
            print(
                "  lifecycle progress: "
                f"{event_number:,}/{len(events):,} events "
                f"({event_number / len(events):.1%}); "
                f"closed={len(closed_rows):,}; active/reserved={len(slots)}",
                flush=True,
            )
        opportunity = long_opportunities[index]

        if event_kind == "RESERVE":
            active_slots = tuple(slots.values())
            if len(active_slots) >= MAX_OPEN_POSITIONS:
                rejection_counts["MAX_OPEN_POSITIONS"] += 1
                decision_rows.append(
                    {
                        "opportunity_id": opportunity.opportunity_id,
                        "status": "REJECTED",
                        "reason": "MAX_OPEN_POSITIONS",
                        "event_utc": event_utc,
                    }
                )
                continue
            if any(
                slot.opportunity.ticker == opportunity.ticker
                for slot in active_slots
            ):
                rejection_counts["TICKER_ALREADY_ACTIVE_OR_RESERVED"] += 1
                decision_rows.append(
                    {
                        "opportunity_id": opportunity.opportunity_id,
                        "status": "REJECTED",
                        "reason": "TICKER_ALREADY_ACTIVE_OR_RESERVED",
                        "event_utc": event_utc,
                    }
                )
                continue
            family_load = sum(
                slot.opportunity.economic_family_id
                == opportunity.economic_family_id
                for slot in active_slots
            )
            if family_load >= MAX_POSITIONS_PER_FAMILY:
                rejection_counts["MAX_POSITIONS_PER_FAMILY"] += 1
                decision_rows.append(
                    {
                        "opportunity_id": opportunity.opportunity_id,
                        "status": "REJECTED",
                        "reason": "MAX_POSITIONS_PER_FAMILY",
                        "event_utc": event_utc,
                    }
                )
                continue
            current_account = coordinator.current_account()
            if current_account.state.account_book_equity <= 0.0:
                rejection_counts["NONPOSITIVE_BOOK_EQUITY"] += 1
                continue
            decision, _ = _build_decision(
                opportunity,
                account_book_equity=current_account.state.account_book_equity,
            )
            transition, _ = coordinator.apply_reservation(record=decision)
            if (
                transition.event is None
                or transition.event.kind
                != RecurrentLifecycleEventKind.RESERVE_STOCK
            ):
                reason = (
                    transition.event.kind.value
                    if transition.event is not None
                    else "RECURRENT_RESERVATION_NOT_CREATED"
                )
                rejection_counts[reason] += 1
                decision_rows.append(
                    {
                        "opportunity_id": opportunity.opportunity_id,
                        "decision_record_fingerprint": decision.record_fingerprint,
                        "status": "REJECTED",
                        "reason": reason,
                        "event_utc": event_utc,
                    }
                )
                continue
            slots[index] = _Slot(
                opportunity=opportunity,
                decision=decision,
            )
            peak_slots = max(peak_slots, len(slots))
            policy_stats[opportunity.policy_id]["admitted"] += 1
            family_stats[opportunity.economic_family_id]["admitted"] += 1
            decision_rows.append(
                {
                    "opportunity_id": opportunity.opportunity_id,
                    "decision_record_fingerprint": decision.record_fingerprint,
                    "status": "RESERVED",
                    "reason": "WALK_FORWARD_SELECTED_AND_PORTFOLIO_ADMITTED",
                    "event_utc": event_utc,
                    "selector_score": opportunity.selector_score,
                    "fold_id": opportunity.fold_id,
                    "training_start": opportunity.training_start,
                    "training_end": opportunity.training_end,
                }
            )
            continue

        slot = slots.get(index)
        if slot is None:
            continue

        if event_kind == "ENTRY":
            account = coordinator.current_account()
            notional = float(
                slot.decision.stock_economics.position_notional_dollars
            )
            half_cost_bps = opportunity.round_trip_cost_bps / 2.0
            entry_fee = notional * half_cost_bps / 10_000.0
            entry_source = {
                "contract": RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT,
                "conditioning_analysis_fingerprint": opportunity.source_analysis_fingerprint,
                "opportunity_id": opportunity.opportunity_id,
                "entry_utc": opportunity.entry_utc,
                "normalized_entry_price": NORMALIZED_ENTRY_PRICE,
            }
            fill = build_recurrent_entry_fill_evidence(
                account=account,
                record=slot.decision,
                inputs=SimulatedEntryFillInputs(
                    fill_source_id=(
                        "ATLAS_SUCCESSOR_HISTORICAL_NORMALIZED_ENTRY:"
                        + opportunity.opportunity_id
                    ),
                    fill_source_fingerprint=_stable_hash(entry_source),
                    filled_utc=opportunity.entry_utc,
                    fill_price_per_unit=NORMALIZED_ENTRY_PRICE,
                    explicit_entry_fees_dollars=entry_fee,
                ),
            )
            funding = build_recurrent_funding_terms(
                account=account,
                fill=fill,
            )
            transition, _ = coordinator.apply_entry(
                fill=fill,
                funding=funding,
            )
            if transition.position is None:
                raise RecurrentSuccessorOutcomeReplayError(
                    "recurrent entry did not create a canonical open position"
                )
            slot.position_fingerprint = transition.position.position_fingerprint
            slot.state = "OPEN"
            current = coordinator.current_account()
            book_equity = current.state.account_book_equity
            peak_book_equity = max(peak_book_equity, book_equity)
            drawdown = (
                0.0
                if peak_book_equity <= 0.0
                else book_equity / peak_book_equity - 1.0
            )
            maximum_book_drawdown = min(maximum_book_drawdown, drawdown)
            equity_rows.append(
                {
                    "timestamp_utc": opportunity.entry_utc,
                    "event": "ENTRY",
                    "book_equity": book_equity,
                    "cash": current.state.cash,
                    "closed_trade_count": len(current.state.closed_trades),
                    "active_or_reserved_slots": len(slots),
                    "drawdown_from_peak_book_equity": drawdown,
                }
            )
            continue

        if event_kind != "CLOSE" or slot.state != "OPEN":
            continue
        if slot.position_fingerprint is None:
            raise RecurrentSuccessorOutcomeReplayError(
                "open replay slot is missing a recurrent position fingerprint"
            )
        account = coordinator.current_account()
        exit_price = NORMALIZED_ENTRY_PRICE * (1.0 + opportunity.gross_return)
        position = next(
            (
                item
                for item in account.state.open_positions
                if item.position_fingerprint == slot.position_fingerprint
            ),
            None,
        )
        if position is None:
            raise RecurrentSuccessorOutcomeReplayError(
                "replay close cannot find the exact recurrent open position"
            )
        gross_exit = position.quantity * exit_price * position.contract_multiplier
        exit_fee = (
            gross_exit
            * (opportunity.round_trip_cost_bps / 2.0)
            / 10_000.0
        )
        exit_source = {
            "contract": RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT,
            "conditioning_analysis_fingerprint": opportunity.source_analysis_fingerprint,
            "opportunity_id": opportunity.opportunity_id,
            "exit_utc": opportunity.exit_utc,
            "gross_return": opportunity.gross_return,
            "normalized_exit_price": exit_price,
        }
        exit_fill = build_recurrent_exit_fill_evidence(
            source_state=account.state,
            position_fingerprint=slot.position_fingerprint,
            inputs=RecurrentExitFillInputsV1(
                fill_source_id=(
                    "ATLAS_SUCCESSOR_ACCEPTED_OUTCOME_EXIT:"
                    + opportunity.opportunity_id
                ),
                fill_source_fingerprint=_stable_hash(exit_source),
                exited_utc=opportunity.exit_utc,
                exit_price_per_unit=exit_price,
                explicit_exit_fees_dollars=exit_fee,
            ),
        )
        transition, _ = coordinator.apply_close(fill=exit_fill)
        trade = transition.closed_trade
        realized_return = (
            trade.lifetime_trade_net_pnl_dollars
            / trade.entry_book_value_dollars
        )
        if not math.isclose(
            realized_return,
            opportunity.primary_net_return,
            rel_tol=1e-9,
            abs_tol=1e-9,
        ):
            raise RecurrentSuccessorOutcomeReplayError(
                "recurrent realized trade return does not reproduce accepted primary return"
            )
        policy_stats[opportunity.policy_id]["completed"] += 1
        policy_stats[opportunity.policy_id]["net_pnl"] += (
            trade.lifetime_trade_net_pnl_dollars
        )
        family_stats[opportunity.economic_family_id]["completed"] += 1
        family_stats[opportunity.economic_family_id]["net_pnl"] += (
            trade.lifetime_trade_net_pnl_dollars
        )
        current = coordinator.current_account()
        book_equity = current.state.account_book_equity
        peak_book_equity = max(peak_book_equity, book_equity)
        drawdown = (
            0.0
            if peak_book_equity <= 0.0
            else book_equity / peak_book_equity - 1.0
        )
        maximum_book_drawdown = min(maximum_book_drawdown, drawdown)
        closed_rows.append(
            {
                "opportunity": _opportunity_payload(opportunity),
                "decision_record_fingerprint": slot.decision.record_fingerprint,
                "position_fingerprint": slot.position_fingerprint,
                "exit_fill_fingerprint": exit_fill.exit_fill_fingerprint,
                "lifetime_trade_net_pnl_dollars": (
                    trade.lifetime_trade_net_pnl_dollars
                ),
                "realized_return_on_entry_notional": realized_return,
                "book_equity_after": book_equity,
            }
        )
        equity_rows.append(
            {
                "timestamp_utc": opportunity.exit_utc,
                "event": "CLOSE",
                "book_equity": book_equity,
                "cash": current.state.cash,
                "closed_trade_count": len(current.state.closed_trades),
                "active_or_reserved_slots": len(slots) - 1,
                "drawdown_from_peak_book_equity": drawdown,
            }
        )
        del slots[index]
        if len(closed_rows) % 100 == 0:
            print(
                "  recurrent replay progress: "
                f"{len(closed_rows):,} positions closed; "
                f"book equity={book_equity:,.2f}; active/reserved={len(slots)}",
                flush=True,
            )

    if slots:
        raise RecurrentSuccessorOutcomeReplayError(
            "replay ended with unresolved reserved/open slots"
        )
    final_account = coordinator.current_account()
    if final_account.state.open_positions or final_account.state.stock_reservations:
        raise RecurrentSuccessorOutcomeReplayError(
            "replay final recurrent account is not flat"
        )
    final_equity = final_account.state.account_book_equity
    total_return = final_equity / float(initial_equity) - 1.0

    decisions_sha = _write_jsonl(root / "portfolio_decisions.jsonl", decision_rows)
    trades_sha = _write_jsonl(root / "closed_trades.jsonl", closed_rows)
    equity_sha = _write_jsonl(root / "book_equity_curve.jsonl", equity_rows)
    report: dict[str, object] = {
        "status": "COMPLETE_RECURRENT_OUTCOME_REPLAY",
        "contract": RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT,
        "contract_fingerprint": RECURRENT_SUCCESSOR_OUTCOME_REPLAY_CONTRACT_FINGERPRINT,
        "run_fingerprint": run_fingerprint,
        "run_identity": run_identity,
        "source": source,
        "scope": {
            "start_session": start_session,
            "end_session": end_session,
            "policy_ids": sorted(set(str(value) for value in policy_ids)),
        },
        "initial_equity": float(initial_equity),
        "final_book_equity": final_equity,
        "total_return_on_initial_equity": total_return,
        "maximum_realized_book_equity_drawdown": maximum_book_drawdown,
        "selected_opportunities": len(opportunities),
        "supported_long_selected": len(long_opportunities),
        "unsupported_short_selected": unsupported_short_count,
        "admitted_positions": int(
            sum(int(value["admitted"]) for value in policy_stats.values())
        ),
        "completed_positions": len(closed_rows),
        "peak_active_or_reserved_slots": peak_slots,
        "rejections": dict(sorted(rejection_counts.items())),
        "policy_attribution": dict(sorted(policy_stats.items())),
        "family_attribution": dict(sorted(family_stats.items())),
        "genesis_lineage": genesis_lineage,
        "final_recurrent_state_fingerprint": final_account.state.state_fingerprint,
        "final_recurrent_ledger_fingerprint": final_account.ledger.ledger_fingerprint,
        "artifacts": {
            "portfolio_decisions": {
                "path": str((root / "portfolio_decisions.jsonl").resolve()),
                "sha256": decisions_sha,
            },
            "closed_trades": {
                "path": str((root / "closed_trades.jsonl").resolve()),
                "sha256": trades_sha,
            },
            "book_equity_curve": {
                "path": str((root / "book_equity_curve.jsonl").resolve()),
                "sha256": equity_sha,
            },
        },
        "interpretation": {
            "mode": "OUTCOME_REPLAY_DIAGNOSTIC",
            "walk_forward_admission": True,
            "future_outcome_used_for_admission": False,
            "accepted_outcome_used_only_when_exit_event_occurs": True,
            "normalized_price_basis": NORMALIZED_ENTRY_PRICE,
            "bar_level_stop_target_time_retest": False,
            "mark_to_market_equity_curve": False,
            "drawdown_type": "REALIZED_BOOK_EQUITY_ONLY",
            "shorts_simulated": False,
            "short_limitation": "CURRENT_RECURRENT_FUNDING_V1_IS_BULLISH_CASH_STOCK_ONLY",
            "strategy_evidence_or_promotion_change": False,
        },
        "authority": AUTHORITY,
    }
    report["report_fingerprint"] = _stable_hash(report)
    _write_json(root / "run_summary.json", report)
    return report
