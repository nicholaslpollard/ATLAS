from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from packages.backtesting.b35_development_authorization import (
    validate_development_authorization,
)
from packages.backtesting.b35_development_context import (
    DailySessionSummary,
    build_condition_snapshot,
    summarize_regular_session,
)
from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentSourcePlan,
    B35DevelopmentUnitBinding,
    validate_source_plan,
)
from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.backtesting.b35_replay_guard import ensure_read_start_marker, serialized_replay
from packages.backtesting.b35_setup_scan import (
    first_fired_hvd,
    first_fired_opening_range,
    first_fired_premarket_relvol,
)
from packages.backtesting.b35_split_evidence import load_b35_split_evidence
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.enums import SessionSegment
from packages.schemas.market import CanonicalBar
from packages.strategies.b35_conditional_evidence_contract import (
    B34_STRATEGY_IDS,
    B35_PREOUTCOME_FINGERPRINT,
)
from packages.strategies.intraday_opening_pack import (
    IntradaySetupResult,
    evaluate_gap_continuation,
    evaluate_highest_volume_day_style,
    evaluate_opening_range_breakout,
    evaluate_premarket_relvol_consolidation,
)


B35_DEVELOPMENT_REPLAY_CONTRACT = (
    "atlas-b35-development-replay-v2-self-hash-restartable-compact-evidence"
)
MARKET_TZ = ZoneInfo("America/New_York")


class B35DevelopmentReplayError(RuntimeError):
    pass


@dataclass(slots=True)
class _SymbolHistory:
    daily: list[DailySessionSummary]
    premarket: list[tuple[date, float]]

    @classmethod
    def empty(cls) -> "_SymbolHistory":
        return cls(daily=[], premarket=[])

    def append_daily(self, item: DailySessionSummary) -> None:
        self.daily.append(item)
        if len(self.daily) > 260:
            del self.daily[: len(self.daily) - 260]

    def append_premarket(self, session_date: date, volume: float) -> None:
        self.premarket.append((session_date, volume))
        if len(self.premarket) > 25:
            del self.premarket[: len(self.premarket) - 25]


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _receipt_id(receipt: dict[str, object]) -> str:
    return _stable_hash({key: value for key, value in receipt.items() if key != "receipt_id"})


def _canonical_bars(frame: pd.DataFrame) -> tuple[CanonicalBar, ...]:
    bars: list[CanonicalBar] = []
    fields = (
        "symbol",
        "timestamp_utc",
        "session_date",
        "timeframe",
        "session_segment",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "vwap",
        "transaction_count",
        "provider",
        "dataset",
        "source_id",
        "is_adjusted",
        "provider_timestamp_utc",
    )
    for record in frame.to_dict(orient="records"):
        payload: dict[str, object] = {}
        for field in fields:
            value = record.get(field)
            if field in {"vwap", "transaction_count"} and pd.isna(value):
                value = None
            payload[field] = value
        bars.append(CanonicalBar.model_validate(payload))
    return tuple(bars)


def _premarket_volume(
    bars: Sequence[CanonicalBar], session_date: date
) -> float | None:
    selected = [
        bar
        for bar in bars
        if bar.session_date == session_date
        and bar.session_segment == SessionSegment.PREMARKET
        and time(4, 0)
        <= bar.timestamp_utc.astimezone(MARKET_TZ).time()
        < time(9, 30)
    ]
    if not selected:
        return None
    return float(sum(float(bar.volume) for bar in selected))


def _first_regular_bar(
    bars: Sequence[CanonicalBar], session_date: date
) -> CanonicalBar | None:
    regular = sorted(
        (
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment == SessionSegment.REGULAR
        ),
        key=lambda bar: bar.timestamp_utc,
    )
    return regular[0] if regular else None


def _current_regular_open(
    bars: Sequence[CanonicalBar], session_date: date
) -> float | None:
    first = _first_regular_bar(bars, session_date)
    return float(first.open) if first is not None else None


def _split_epoch(split_dates: Sequence[date], session_date: date) -> float:
    # Equality-only epoch token, intentionally not an adjustment ratio.
    return float(1 + sum(1 for item in split_dates if item <= session_date))


def _split_between(
    split_dates: Sequence[date], start_exclusive: date, end_inclusive: date
) -> bool:
    return any(start_exclusive < item <= end_inclusive for item in split_dates)


def _first_fired(
    evaluator: object,
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    earliest_stamp: time,
    latest_stamp: time,
    kwargs: dict[str, object],
) -> IntradaySetupResult | None:
    regular = [
        bar
        for bar in bars
        if bar.session_date == session_date
        and bar.session_segment == SessionSegment.REGULAR
        and earliest_stamp
        <= bar.timestamp_utc.astimezone(MARKET_TZ).time()
        <= latest_stamp
    ]
    for bar in regular:
        decision = bar.timestamp_utc + timedelta(minutes=1)
        result = evaluator(  # type: ignore[operator]
            bars,
            session_date=session_date,
            decision_time_utc=decision,
            **kwargs,
        )
        if result.ready and result.fired:
            return result
    return None


def _evaluate_setups(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    history: _SymbolHistory,
    symbol_split_dates: Sequence[date],
) -> tuple[IntradaySetupResult, ...]:
    first_regular = _first_regular_bar(bars, session_date)
    if first_regular is None:
        return ()
    prior = history.daily[-1] if history.daily else None
    if prior is None:
        # Provider-literal first observation is warm-up: B35 context requires a
        # prior regular close before any scored opportunity can be materialized.
        return ()

    current_open = float(first_regular.open)
    results: list[IntradaySetupResult] = []
    gap_decision = first_regular.timestamp_utc + timedelta(minutes=1)
    if gap_decision.astimezone(MARKET_TZ).time() <= time(11, 31):
        gap = evaluate_gap_continuation(
            session_date=session_date,
            prior_regular_close=float(prior.close),
            current_regular_open=current_open,
            decision_time_utc=gap_decision,
            split_crossed=_split_between(
                symbol_split_dates, prior.session_date, session_date
            ),
        )
        if gap.ready and gap.fired:
            results.append(gap)

    # B34 remains unchanged: its cutoff is the underlying bar stamp through
    # 11:30. B35 later profiles the information-safe decision at bar+1 minute.
    opening = first_fired_opening_range(bars, session_date=session_date)
    if opening is not None:
        results.append(opening)

    if len(history.premarket) >= 20:
        prior_pm = history.premarket[-20:]
        pm_split_free = not _split_between(
            symbol_split_dates, prior_pm[0][0], session_date
        )
        relvol = first_fired_premarket_relvol(
            bars,
            session_date=session_date,
            prior_premarket_volumes=[value for _day, value in prior_pm],
            split_free_lookback=pm_split_free,
        )
        if relvol is not None:
            results.append(relvol)

    if len(history.daily) >= 252:
        prior_daily = history.daily[-252:]
        daily_split_free = not _split_between(
            symbol_split_dates, prior_daily[0].session_date, session_date
        )
        hvd = first_fired_hvd(
            bars,
            session_date=session_date,
            prior_regular_daily_volumes=[item.regular_volume for item in prior_daily],
            split_free_lookback=daily_split_free,
        )
        if hvd is not None:
            results.append(hvd)
    return tuple(results)


def _signal_time_override(
    setup: IntradaySetupResult,
    bars: Sequence[CanonicalBar],
    session_date: date,
) -> time | None:
    if setup.strategy_id != "b34_gap_continuation_v1":
        return None
    first = _first_regular_bar(bars, session_date)
    if first is None:
        raise B35DevelopmentReplayError("gap setup has no observed regular-session bar")
    return (first.timestamp_utc + timedelta(minutes=1)).astimezone(MARKET_TZ).time()


def _group_units(
    plan: B35DevelopmentSourcePlan,
    *,
    split_evidence_fingerprint: str,
    authorization_id: str,
) -> tuple[tuple[str, tuple[B35DevelopmentUnitBinding, ...]], ...]:
    groups: dict[tuple[str, ...], list[B35DevelopmentUnitBinding]] = defaultdict(list)
    for unit in plan.units:
        groups[unit.symbols].append(unit)
    output: list[tuple[str, tuple[B35DevelopmentUnitBinding, ...]]] = []
    for symbols, units in groups.items():
        ordered = tuple(
            sorted(
                units,
                key=lambda item: (item.year, item.month, item.batch_index, item.unit_id),
            )
        )
        seen_months: set[tuple[int, int]] = set()
        for unit in ordered:
            month = (unit.year, unit.month)
            if month in seen_months:
                raise B35DevelopmentReplayError(
                    "multiple minute units share one symbol-batch/month; batch identity is not deterministic"
                )
            seen_months.add(month)
        group_fingerprint = _stable_hash(
            {
                "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
                "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
                "source_fingerprint": plan.source_fingerprint,
                "split_evidence_fingerprint": split_evidence_fingerprint,
                "authorization_id": authorization_id,
                "symbols": symbols,
                "units": [
                    (
                        unit.unit_id,
                        unit.canonical_sha256,
                        unit.year,
                        unit.month,
                        unit.batch_index,
                    )
                    for unit in ordered
                ],
            }
        )
        output.append((group_fingerprint, ordered))
    output.sort(key=lambda item: item[0])
    return tuple(output)


def _validate_strategy_counts(
    counts: object, *, record_count: int
) -> dict[str, dict[str, int]]:
    if not isinstance(counts, dict):
        raise B35DevelopmentReplayError("group receipt strategy counts are malformed")
    normalized: dict[str, dict[str, int]] = {}
    total_fired = 0
    for strategy_id in B34_STRATEGY_IDS:
        item = counts.get(strategy_id)
        if not isinstance(item, dict):
            raise B35DevelopmentReplayError("group receipt is missing strategy counts")
        values: dict[str, int] = {}
        for field in ("evaluated_fired", "comparable", "noncomparable"):
            value = item.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                raise B35DevelopmentReplayError("group receipt strategy count is invalid")
            values[field] = value
        if values["comparable"] + values["noncomparable"] != values["evaluated_fired"]:
            raise B35DevelopmentReplayError("group receipt strategy accounting does not reconcile")
        total_fired += values["evaluated_fired"]
        normalized[strategy_id] = values
    if set(counts) != set(B34_STRATEGY_IDS):
        raise B35DevelopmentReplayError("group receipt contains unexpected strategy ids")
    if total_fired != record_count:
        raise B35DevelopmentReplayError("group receipt record count does not reconcile")
    return normalized


def _validate_group_receipt(
    receipt: dict[str, object],
    output_path: Path,
    *,
    units: Sequence[B35DevelopmentUnitBinding],
    group_fingerprint: str,
    source_fingerprint: str,
    split_evidence_fingerprint: str,
    authorization_id: str,
) -> str:
    required = {
        "contract": B35_DEVELOPMENT_REPLAY_CONTRACT,
        "status": "COMPLETE",
        "b35_preoutcome_fingerprint": B35_PREOUTCOME_FINGERPRINT,
        "group_fingerprint": group_fingerprint,
        "source_fingerprint": source_fingerprint,
        "split_evidence_fingerprint": split_evidence_fingerprint,
        "authorization_id": authorization_id,
        "output_path": str(output_path),
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
    for field, expected in required.items():
        if receipt.get(field) != expected:
            raise B35DevelopmentReplayError(
                f"group receipt {field} does not match the frozen run"
            )
    expected_units = [
        {
            "unit_id": unit.unit_id,
            "canonical_sha256": unit.canonical_sha256,
            "year": unit.year,
            "month": unit.month,
            "batch_index": unit.batch_index,
        }
        for unit in units
    ]
    if receipt.get("unit_bindings") != expected_units or receipt.get("unit_count") != len(units):
        raise B35DevelopmentReplayError("group receipt unit bindings drifted")
    record_count = receipt.get("record_count")
    if not isinstance(record_count, int) or isinstance(record_count, bool) or record_count < 0:
        raise B35DevelopmentReplayError("group receipt record count is invalid")
    _validate_strategy_counts(receipt.get("strategy_counts"), record_count=record_count)
    actual_id = str(receipt.get("receipt_id") or "")
    if len(actual_id) != 64 or actual_id != _receipt_id(receipt):
        raise B35DevelopmentReplayError("group completion receipt is not self-hash bound")
    if not output_path.is_file():
        raise B35DevelopmentReplayError("completed group output is missing")
    if receipt.get("output_sha256") != _sha256_file(output_path):
        raise B35DevelopmentReplayError("completed group output SHA-256 drifted")
    return actual_id


def _completed_group(
    receipt_path: Path,
    output_path: Path,
    *,
    units: Sequence[B35DevelopmentUnitBinding],
    group_fingerprint: str,
    source_fingerprint: str,
    split_evidence_fingerprint: str,
    authorization_id: str,
) -> dict[str, object] | None:
    if not receipt_path.is_file():
        if output_path.exists():
            # Output publication happens before receipt publication. If a crash
            # occurs in that gap, the output is untrusted derived data. Remove it
            # and deterministically recompute; presence alone can never imply
            # completion.
            try:
                output_path.unlink()
            except OSError as exc:
                raise B35DevelopmentReplayError(
                    f"cannot remove orphan unreceipted group output: {output_path}"
                ) from exc
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise B35DevelopmentReplayError(f"invalid group receipt: {receipt_path}") from exc
    if not isinstance(receipt, dict):
        raise B35DevelopmentReplayError("group receipt is not an object")
    _validate_group_receipt(
        receipt,
        output_path,
        units=units,
        group_fingerprint=group_fingerprint,
        source_fingerprint=source_fingerprint,
        split_evidence_fingerprint=split_evidence_fingerprint,
        authorization_id=authorization_id,
    )
    return receipt


class B35DevelopmentReplayEngine:
    def __init__(self, source: B35DevelopmentMinuteSource) -> None:
        self.source = source
        self.layout = source.layout

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
        group_receipts: list[dict[str, object]] = []

        for group_fingerprint, units in _group_units(
            plan,
            split_evidence_fingerprint=split_evidence.fingerprint,
            authorization_id=authorization_id,
        ):
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
                group_receipts.append(existing)
                continue

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
                        frame = self.source.load_unit(
                            unit,
                            start_session=plan.start_session,
                            end_session=plan.end_session,
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
                                    "source_fingerprint": plan.source_fingerprint,
                                    "split_evidence_fingerprint": split_evidence.fingerprint,
                                    "authorization_id": authorization_id,
                                    "group_fingerprint": group_fingerprint,
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
                "source_fingerprint": plan.source_fingerprint,
                "split_evidence_fingerprint": split_evidence.fingerprint,
                "authorization_id": authorization_id,
                "group_fingerprint": group_fingerprint,
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
                group_fingerprint=group_fingerprint,
                source_fingerprint=plan.source_fingerprint,
                split_evidence_fingerprint=split_evidence.fingerprint,
                authorization_id=authorization_id,
            )
            atomic_write_text(
                receipt_path,
                json.dumps(receipt, indent=2, sort_keys=True, default=str) + "\n",
                fsync=True,
            )
            group_receipts.append(receipt)

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
        atomic_write_text(
            output_root / "summary.json",
            json.dumps(summary, indent=2, sort_keys=True, default=str) + "\n",
            fsync=True,
        )
        return summary
