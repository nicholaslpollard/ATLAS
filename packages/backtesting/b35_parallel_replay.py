from __future__ import annotations

import json
import os
import socket
import time as monotonic_time
from collections import deque
from concurrent.futures import FIRST_COMPLETED, Future, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from packages.backtesting.b35_development_authorization import (
    validate_development_authorization,
)
from packages.backtesting.b35_development_context import (
    build_condition_snapshot,
    summarize_regular_session,
)
from packages.backtesting.b35_development_replay import (
    B35_DEVELOPMENT_REPLAY_CONTRACT,
    B35DevelopmentReplayError,
    _SymbolHistory,
    _canonical_bars,
    _completed_group,
    _current_regular_open,
    _evaluate_setups,
    _group_units,
    _premarket_volume,
    _receipt_id,
    _sha256_file,
    _signal_time_override,
    _split_epoch,
    _stable_hash,
    _validate_group_receipt,
    _validate_strategy_counts,
)
from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentSourcePlan,
    B35DevelopmentUnitBinding,
    validate_source_plan,
)
from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.backtesting.b35_replay_guard import ensure_read_start_marker, serialized_replay
from packages.backtesting.b35_split_evidence import load_b35_split_evidence
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.execution_profile import ParallelResearchExecutionProfile
from packages.core.settings import load_settings
from packages.strategies.b35_conditional_evidence_contract import (
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
)


B35_PROGRESS_CONTRACT = "atlas-b35-runtime-progress-v1-non-authoritative"


@dataclass(frozen=True, slots=True)
class B35GroupTask:
    group_fingerprint: str
    units: tuple[B35DevelopmentUnitBinding, ...]
    start_session: date
    end_session: date
    source_fingerprint: str
    split_evidence_fingerprint: str
    authorization_id: str
    output_path: str
    receipt_path: str

    @property
    def token(self) -> str:
        return self.group_fingerprint[:20]


_WORKER_SOURCE: B35DevelopmentMinuteSource | None = None
_WORKER_SPLIT_EVIDENCE: Any = None


def _init_b35_worker(project_root: str, duckdb_threads: int) -> None:
    """Initialize one spawned replay worker with its own DuckDB/source reader."""

    global _WORKER_SOURCE, _WORKER_SPLIT_EVIDENCE
    settings = load_settings(Path(project_root).resolve())
    _WORKER_SOURCE = B35DevelopmentMinuteSource(
        settings,
        duckdb_threads=duckdb_threads,
    )
    _WORKER_SPLIT_EVIDENCE = load_b35_split_evidence(_WORKER_SOURCE.layout)


def _run_group_task(task: B35GroupTask) -> dict[str, object]:
    """Compute exactly one frozen group using the legacy scientific mechanics.

    This function intentionally mirrors the accepted serial inner loop. Parallelism
    changes scheduling only: setup truth, context, outcome simulation, JSON record
    bytes, receipt schema, hashes, and scientific authority remain unchanged.
    """

    source = _WORKER_SOURCE
    split_evidence = _WORKER_SPLIT_EVIDENCE
    if source is None or split_evidence is None:
        raise B35DevelopmentReplayError("B35 parallel worker was not initialized")
    if split_evidence.fingerprint != task.split_evidence_fingerprint:
        raise B35DevelopmentReplayError("B35 worker split evidence fingerprint drifted")

    output_path = Path(task.output_path)
    receipt_path = Path(task.receipt_path)
    units = task.units
    histories = {symbol: _SymbolHistory.empty() for symbol in units[0].symbols}
    counters = {
        strategy_id: {
            "evaluated_fired": 0,
            "comparable": 0,
            "noncomparable": 0,
        }
        for strategy_id in B34_STRATEGY_IDS
    }
    record_count = 0
    temp = unique_temp_path(output_path)
    try:
        with temp.open("w", encoding="utf-8", newline="") as handle:
            for unit in units:
                frame = source.load_unit(
                    unit,
                    start_session=task.start_session,
                    end_session=task.end_session,
                )
                if frame.empty:
                    continue
                frame["session_date"] = pd.to_datetime(
                    frame["session_date"], errors="raise"
                ).dt.date
                for (symbol, session_date), session_frame in frame.groupby(
                    ["symbol", "session_date"], sort=True, observed=True
                ):
                    symbol = str(symbol)
                    if symbol not in histories:
                        raise B35DevelopmentReplayError(
                            f"unit emitted symbol outside its frozen batch: {symbol}"
                        )
                    if not isinstance(session_date, date):
                        raise B35DevelopmentReplayError("session date is not a date")
                    bars = _canonical_bars(session_frame)
                    current_open = _current_regular_open(bars, session_date)
                    if current_open is None:
                        pm_volume = _premarket_volume(bars, session_date)
                        if pm_volume is not None:
                            histories[symbol].append_premarket(session_date, pm_volume)
                        continue
                    symbol_splits = split_evidence.split_dates_by_symbol.get(symbol, ())
                    current_epoch = _split_epoch(symbol_splits, session_date)
                    setups = _evaluate_setups(
                        bars,
                        session_date=session_date,
                        history=histories[symbol],
                        symbol_split_dates=symbol_splits,
                    )
                    for setup in setups:
                        counters[setup.strategy_id]["evaluated_fired"] += 1
                        context = build_condition_snapshot(
                            setup,
                            bars,
                            symbol=symbol,
                            session_date=session_date,
                            prior_daily=histories[symbol].daily,
                            current_regular_open=current_open,
                            current_split_factor=current_epoch,
                            prior_market_regime="UNAVAILABLE",
                            signal_time_et_override=_signal_time_override(
                                setup, bars, session_date
                            ),
                        )
                        outcome = simulate_intraday_outcome(
                            setup,
                            bars,
                            symbol=symbol,
                            session_date=session_date,
                        )
                        if outcome.comparable:
                            counters[setup.strategy_id]["comparable"] += 1
                        else:
                            counters[setup.strategy_id]["noncomparable"] += 1
                        record = {
                            "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
                            "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
                            "source_fingerprint": task.source_fingerprint,
                            "split_evidence_fingerprint": task.split_evidence_fingerprint,
                            "authorization_id": task.authorization_id,
                            "group_fingerprint": task.group_fingerprint,
                            "setup": asdict(setup),
                            "context": asdict(context),
                            "outcome": asdict(outcome),
                        }
                        handle.write(
                            json.dumps(
                                record,
                                sort_keys=True,
                                separators=(",", ":"),
                                default=str,
                            )
                            + "\n"
                        )
                        record_count += 1

                    pm_volume = _premarket_volume(bars, session_date)
                    if pm_volume is not None:
                        histories[symbol].append_premarket(session_date, pm_volume)
                    summary = summarize_regular_session(
                        bars,
                        session_date=session_date,
                        split_factor=current_epoch,
                    )
                    if summary is not None:
                        histories[symbol].append_daily(summary)
            handle.flush()
            os.fsync(handle.fileno())
        replace_with_retry(temp, output_path)
    except Exception:
        temp.unlink(missing_ok=True)
        raise

    receipt: dict[str, object] = {
        "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
        "status": "COMPLETE",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "source_fingerprint": task.source_fingerprint,
        "split_evidence_fingerprint": task.split_evidence_fingerprint,
        "authorization_id": task.authorization_id,
        "group_fingerprint": task.group_fingerprint,
        "symbols": list(units[0].symbols),
        "unit_count": len(units),
        "unit_bindings": [
            {
                "unit_id": unit.unit_id,
                "canonical_sha256": unit.canonical_sha256,
                "year": unit.year,
                "month": unit.month,
                "batch_index": unit.batch_index,
            }
            for unit in units
        ],
        "record_count": record_count,
        "strategy_counts": counters,
        "output_path": str(output_path),
        "output_sha256": _sha256_file(output_path),
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
    receipt["receipt_id"] = _receipt_id(receipt)
    _validate_group_receipt(
        receipt,
        output_path,
        units=units,
        group_fingerprint=task.group_fingerprint,
        source_fingerprint=task.source_fingerprint,
        split_evidence_fingerprint=task.split_evidence_fingerprint,
        authorization_id=task.authorization_id,
    )
    atomic_write_text(
        receipt_path,
        json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )
    return receipt


def _duration_text(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _build_progress_payload(
    *,
    state: str,
    started_at_utc: str,
    started_monotonic: float,
    profile: ParallelResearchExecutionProfile,
    groups_total: int,
    groups_completed: int,
    groups_reused_at_start: int,
    groups_computed_this_run: int,
    units_total: int,
    units_completed: int,
    units_reused_at_start: int,
    units_computed_this_run: int,
    active_group_tokens: list[str],
    last_error: str | None = None,
) -> dict[str, object]:
    elapsed = max(0.0, monotonic_time.monotonic() - started_monotonic)
    rate = None
    eta_seconds = None
    if elapsed > 0 and units_computed_this_run > 0:
        rate = units_computed_this_run / (elapsed / 3600.0)
        if groups_computed_this_run >= 2 and rate > 0:
            eta_seconds = max(0.0, units_total - units_completed) / rate * 3600.0
    percent = 100.0 if units_total == 0 else units_completed / units_total * 100.0
    return {
        "contract": B35_PROGRESS_CONTRACT,
        "state": state,
        "status_authority": "NON_AUTHORITATIVE_OPERATIONAL",
        "scientific_completion_authority": "GROUP_RECEIPTS_AND_FINAL_SUMMARY_ONLY",
        "host": socket.gethostname(),
        "pid": os.getpid(),
        "started_at_utc": started_at_utc,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": round(elapsed, 3),
        "workers": profile.replay_workers,
        "duckdb_threads_per_worker": profile.duckdb_threads_per_worker,
        "aggregate_worker_threads": profile.aggregate_worker_threads,
        "groups_total": groups_total,
        "groups_completed": groups_completed,
        "groups_reused_at_start": groups_reused_at_start,
        "groups_computed_this_run": groups_computed_this_run,
        "units_total": units_total,
        "units_completed": units_completed,
        "units_reused_at_start": units_reused_at_start,
        "units_computed_this_run": units_computed_this_run,
        "percent_complete": round(percent, 2),
        "units_per_hour_this_run": None if rate is None else round(rate, 1),
        "eta_seconds": None if eta_seconds is None else round(eta_seconds, 1),
        "active_group_tokens": active_group_tokens,
        "last_error": last_error,
    }


def _write_and_print_progress(output_root: Path, payload: dict[str, object]) -> None:
    atomic_write_text(
        output_root / "progress.json",
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )
    rate = payload["units_per_hour_this_run"]
    eta = payload["eta_seconds"]
    eta_text = "ETA unavailable" if eta is None else f"ETA {_duration_text(float(eta))}"
    rate_text = "rate unavailable" if rate is None else f"{float(rate):,.1f} units/hr"
    stamp = str(payload["updated_at_utc"])
    print(
        f"[{stamp}] B35 {payload['groups_completed']}/{payload['groups_total']} groups "
        f"({float(payload['percent_complete']):.2f}%) | "
        f"units {int(payload['units_completed']):,}/{int(payload['units_total']):,} | "
        f"reused {payload['groups_reused_at_start']} groups | "
        f"new {payload['groups_computed_this_run']} groups | "
        f"elapsed {_duration_text(float(payload['elapsed_seconds']))} | "
        f"{rate_text} | {eta_text} | state={payload['state']}",
        flush=True,
    )


def _build_summary(
    *,
    plan: B35DevelopmentSourcePlan,
    split_evidence: Any,
    authorization_id: str,
    read_start_marker_id: str,
    group_receipts: list[dict[str, object]],
) -> dict[str, object]:
    """Build the exact legacy scientific summary; execution metadata is excluded."""

    total_records = sum(int(item["record_count"]) for item in group_receipts)
    aggregate: dict[str, dict[str, int]] = {
        strategy_id: {
            "evaluated_fired": 0,
            "comparable": 0,
            "noncomparable": 0,
        }
        for strategy_id in B34_STRATEGY_IDS
    }
    receipt_ids: list[str] = []
    for receipt in group_receipts:
        receipt_id = str(receipt.get("receipt_id") or "")
        if len(receipt_id) != 64 or receipt_id != _receipt_id(receipt):
            raise B35DevelopmentReplayError("aggregate received an invalid group receipt id")
        receipt_ids.append(receipt_id)
        counts = _validate_strategy_counts(
            receipt.get("strategy_counts"), record_count=int(receipt["record_count"])
        )
        for strategy_id in B34_STRATEGY_IDS:
            for field in ("evaluated_fired", "comparable", "noncomparable"):
                aggregate[strategy_id][field] += counts[strategy_id][field]

    summary: dict[str, object] = {
        "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
        "status": "COMPLETE",
        "completed_at_utc": datetime.now(UTC).isoformat(),
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "source_contract": plan.contract,
        "source_fingerprint": plan.source_fingerprint,
        "split_evidence_contract": split_evidence.contract,
        "split_evidence_fingerprint": split_evidence.fingerprint,
        "corporate_action_split_evidence_sha256": split_evidence.corporate_actions_sha256,
        "authorization_id": authorization_id,
        "read_start_marker_id": read_start_marker_id,
        "start_session": plan.start_session.isoformat(),
        "end_session": plan.end_session.isoformat(),
        "group_count": len(group_receipts),
        "group_receipt_ids": sorted(receipt_ids),
        "source_unit_count": len(plan.units),
        "fired_opportunity_records": total_records,
        "strategy_counts": aggregate,
        "compact_group_outputs_only": True,
        "permanent_minute_feature_lake_created": False,
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
    summary["run_fingerprint"] = _stable_hash(
        {key: value for key, value in summary.items() if key != "completed_at_utc"}
    )
    return summary


class B35ParallelDevelopmentReplayEngine:
    """Parallel coordinator for the frozen B35 group contract.

    Independent group scheduling is the only scientific-path change. Existing
    completion receipts are validated and reused before any new worker is launched.
    """

    def __init__(
        self,
        source: B35DevelopmentMinuteSource,
        *,
        execution_profile: ParallelResearchExecutionProfile,
        progress_interval_seconds: float = 60.0,
    ) -> None:
        self.source = source
        self.layout = source.layout
        self.execution_profile = execution_profile
        self.progress_interval_seconds = max(0.05, float(progress_interval_seconds))

    @serialized_replay
    def run(
        self,
        plan: B35DevelopmentSourcePlan,
        *,
        output_root: Path,
        authorization: dict[str, object],
    ) -> dict[str, object]:
        validate_source_plan(plan)
        output_root = output_root.resolve()
        groups_root = output_root / "groups"
        groups_root.mkdir(parents=True, exist_ok=True)
        split_evidence = load_b35_split_evidence(self.layout)
        authorization_id = validate_development_authorization(
            authorization,
            plan=plan,
            split_evidence=split_evidence,
        )
        read_start_marker = ensure_read_start_marker(
            output_root,
            source_fingerprint=plan.source_fingerprint,
            split_evidence_fingerprint=split_evidence.fingerprint,
            authorization_id=authorization_id,
        )
        read_start_marker_id = str(read_start_marker["marker_id"])

        groups = _group_units(
            plan,
            split_evidence_fingerprint=split_evidence.fingerprint,
            authorization_id=authorization_id,
        )
        receipts_by_group: dict[str, dict[str, object]] = {}
        pending_tasks: deque[B35GroupTask] = deque()
        units_reused = 0
        for group_fingerprint, units in groups:
            token = group_fingerprint[:20]
            output_path = groups_root / f"{token}.jsonl"
            receipt_path = groups_root / f"{token}.receipt.json"
            existing = _completed_group(
                receipt_path,
                output_path,
                units=units,
                group_fingerprint=group_fingerprint,
                source_fingerprint=plan.source_fingerprint,
                split_evidence_fingerprint=split_evidence.fingerprint,
                authorization_id=authorization_id,
            )
            if existing is not None:
                receipts_by_group[group_fingerprint] = existing
                units_reused += int(existing["unit_count"])
                continue
            pending_tasks.append(
                B35GroupTask(
                    group_fingerprint=group_fingerprint,
                    units=units,
                    start_session=plan.start_session,
                    end_session=plan.end_session,
                    source_fingerprint=plan.source_fingerprint,
                    split_evidence_fingerprint=split_evidence.fingerprint,
                    authorization_id=authorization_id,
                    output_path=str(output_path),
                    receipt_path=str(receipt_path),
                )
            )

        started_at_utc = datetime.now(UTC).isoformat()
        started_monotonic = monotonic_time.monotonic()
        reused_groups = len(receipts_by_group)
        computed_groups = 0
        computed_units = 0
        total_groups = len(groups)
        total_units = len(plan.units)

        def emit(state: str, active: list[str], error: str | None = None) -> None:
            payload = _build_progress_payload(
                state=state,
                started_at_utc=started_at_utc,
                started_monotonic=started_monotonic,
                profile=self.execution_profile,
                groups_total=total_groups,
                groups_completed=len(receipts_by_group),
                groups_reused_at_start=reused_groups,
                groups_computed_this_run=computed_groups,
                units_total=total_units,
                units_completed=units_reused + computed_units,
                units_reused_at_start=units_reused,
                units_computed_this_run=computed_units,
                active_group_tokens=active,
                last_error=error,
            )
            _write_and_print_progress(output_root, payload)

        emit("RUNNING", [])

        executor: ProcessPoolExecutor | None = None
        inflight: dict[Future[dict[str, object]], B35GroupTask] = {}
        try:
            if pending_tasks:
                executor = ProcessPoolExecutor(
                    max_workers=self.execution_profile.replay_workers,
                    initializer=_init_b35_worker,
                    initargs=(
                        str(self.source.settings.project_root),
                        self.execution_profile.duckdb_threads_per_worker,
                    ),
                )

                def fill_workers() -> None:
                    while pending_tasks and len(inflight) < self.execution_profile.replay_workers:
                        task = pending_tasks.popleft()
                        inflight[executor.submit(_run_group_task, task)] = task

                fill_workers()
                while inflight:
                    done, _ = wait(
                        tuple(inflight),
                        timeout=self.progress_interval_seconds,
                        return_when=FIRST_COMPLETED,
                    )
                    if not done:
                        emit("RUNNING", [task.token for task in inflight.values()])
                        continue
                    for future in done:
                        task = inflight.pop(future)
                        receipt = future.result()
                        _validate_group_receipt(
                            receipt,
                            Path(task.output_path),
                            units=task.units,
                            group_fingerprint=task.group_fingerprint,
                            source_fingerprint=task.source_fingerprint,
                            split_evidence_fingerprint=task.split_evidence_fingerprint,
                            authorization_id=task.authorization_id,
                        )
                        receipts_by_group[task.group_fingerprint] = receipt
                        computed_groups += 1
                        computed_units += int(receipt["unit_count"])
                    fill_workers()
                    emit("RUNNING", [task.token for task in inflight.values()])
        except KeyboardInterrupt:
            emit("INTERRUPTING", [task.token for task in inflight.values()])
            for future in inflight:
                future.cancel()
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)
                executor = None
            emit("INTERRUPTED", [])
            raise
        except BaseException as exc:
            for future in inflight:
                future.cancel()
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)
                executor = None
            emit("FAILED", [], f"{type(exc).__name__}: {exc}")
            raise
        finally:
            if executor is not None:
                executor.shutdown(wait=True, cancel_futures=True)

        if len(receipts_by_group) != total_groups:
            emit("FAILED", [], "validated group receipt count did not reach the frozen total")
            raise B35DevelopmentReplayError(
                "parallel B35 replay did not produce every frozen group receipt"
            )

        ordered_receipts = [receipts_by_group[group_fingerprint] for group_fingerprint, _ in groups]
        summary = _build_summary(
            plan=plan,
            split_evidence=split_evidence,
            authorization_id=authorization_id,
            read_start_marker_id=read_start_marker_id,
            group_receipts=ordered_receipts,
        )
        atomic_write_text(
            output_root / "summary.json",
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
            fsync=True,
        )
        emit("COMPLETE", [])
        return summary
