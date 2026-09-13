from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

import pandas as pd

from packages.backtesting.successor_runner_contract import (
    COST_GRID_BPS,
    SUCCESSOR_RUNNER_CONTRACT,
    canonical_sha256,
    frozen_authority_contract,
)
from packages.core.enums import SessionSegment, Timeframe
from packages.schemas.market import CanonicalBar
from packages.strategies.successor_intraday_rules import SuccessorIntradaySignal


SUCCESSOR_DEVELOPMENT_OUTCOME_CONTRACT = (
    "atlas-successor-development-outcomes-v1-common-diagnostic-adverse-first"
)
ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT = (
    "d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c"
)
ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT = (
    "a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3"
)
ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT = 493
ACCEPTED_SUCCESSOR_MINUTE_SOURCE_UNITS = 59_768
DEVELOPMENT_START = date(2016, 1, 4)
DEVELOPMENT_END = date(2026, 4, 30)
MARKET_TZ = ZoneInfo("America/New_York")
MAX_ENTRY_DELAY_MINUTES = 5
TIME_EXIT_START_ET = datetime.strptime("15:55", "%H:%M").time()
TIME_EXIT_END_ET = datetime.strptime("15:59", "%H:%M").time()
TARGET_R_MULTIPLE = 2.0


class SuccessorDevelopmentOutcomeError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class AcceptedSuccessorPreflight:
    runner_contract_fingerprint: str
    source_verification_run_fingerprint: str
    source_manifest_fingerprint: str
    source_group_count: int
    minute_source_units: int
    summary_path: str

    def scientific_payload(self) -> dict[str, object]:
        return {
            "runner_contract_fingerprint": self.runner_contract_fingerprint,
            "source_verification_run_fingerprint": self.source_verification_run_fingerprint,
            "source_manifest_fingerprint": self.source_manifest_fingerprint,
            "source_group_count": self.source_group_count,
            "minute_source_units": self.minute_source_units,
        }


@dataclass(frozen=True, slots=True)
class SuccessorDailyDiagnosticOutcome:
    contract: str
    policy_id: str
    economic_family_id: str
    instrument_id: str
    ticker: str
    signal_session: str
    signal_available_at_utc: str
    direction: str
    universe_eligible: bool
    status: str
    reason_codes: tuple[str, ...]
    entry_session: str | None
    entry_price: float | None
    horizon_exit_sessions: dict[str, str | None]
    horizon_exit_prices: dict[str, float | None]
    gross_directional_returns: dict[str, float | None]
    net_directional_returns_by_cost_bps: dict[str, dict[str, float | None]]
    maximum_favorable_excursion_20: float | None
    maximum_adverse_excursion_20: float | None
    common_context: dict[str, object]
    outcome_fingerprint: str


@dataclass(frozen=True, slots=True)
class SuccessorIntradayDiagnosticOutcome:
    contract: str
    policy_id: str
    economic_family_id: str
    symbol: str
    session_date: str
    direction: str
    status: str
    reason_codes: tuple[str, ...]
    signal_available_at_utc: str
    entry_bar_timestamp_utc: str | None
    entry_price: float | None
    stop_price: float | None
    target_price: float | None
    exit_bar_timestamp_utc: str | None
    exit_price: float | None
    exit_reason: str | None
    same_bar_collision_adverse_first: bool
    gross_directional_return: float | None
    net_directional_returns_by_cost_bps: dict[str, float]
    risk_multiple: float | None
    maximum_favorable_excursion: float | None
    maximum_adverse_excursion: float | None
    bars_observed_after_entry: int
    outcome_fingerprint: str


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorDevelopmentOutcomeError(f"invalid successor preflight artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise SuccessorDevelopmentOutcomeError(f"successor preflight artifact is not an object: {path}")
    return payload


def validate_accepted_successor_preflight(
    project_root: Path,
    *,
    runner_contract_fingerprint: str = ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
) -> AcceptedSuccessorPreflight:
    """Bind outcome access to the exact accepted workstation source verification."""

    root = Path(project_root).resolve()
    if runner_contract_fingerprint != ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT:
        raise SuccessorDevelopmentOutcomeError("successor runner contract fingerprint is not the accepted workstation contract")
    output_root = (
        root
        / "data"
        / "v2_build"
        / "alpaca_sip_v2"
        / "derived"
        / "strategy_lab"
        / "successor_preflight"
        / runner_contract_fingerprint[:16]
    )
    summary_path = output_root / "summary.json"
    contract_path = output_root / "preoutcome_contract.json"
    source_manifest_path = output_root / "source_manifest.json"
    summary = _read_json(summary_path)
    contract = _read_json(contract_path)
    source_manifest = _read_json(source_manifest_path)

    if summary.get("status") != "COMPLETE_PREOUTCOME_SOURCE_VERIFICATION":
        raise SuccessorDevelopmentOutcomeError("successor source verification is not complete")
    if summary.get("contract") != SUCCESSOR_RUNNER_CONTRACT:
        raise SuccessorDevelopmentOutcomeError("successor source verification contract drifted")
    if summary.get("runner_contract_fingerprint") != runner_contract_fingerprint:
        raise SuccessorDevelopmentOutcomeError("successor source verification runner fingerprint drifted")
    if contract.get("fingerprint") != runner_contract_fingerprint:
        raise SuccessorDevelopmentOutcomeError("successor preoutcome contract artifact drifted")
    if canonical_sha256({key: value for key, value in contract.items() if key != "fingerprint"}) != runner_contract_fingerprint:
        raise SuccessorDevelopmentOutcomeError("successor preoutcome contract fingerprint is not self-consistent")

    run_summary = summary.get("source_verification")
    if not isinstance(run_summary, dict):
        raise SuccessorDevelopmentOutcomeError("successor source verification run summary is missing")
    run_fingerprint = str(run_summary.get("run_fingerprint") or "")
    if run_fingerprint != ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT:
        raise SuccessorDevelopmentOutcomeError("successor source verification run fingerprint is not accepted")
    if int(run_summary.get("group_count", -1)) != ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT:
        raise SuccessorDevelopmentOutcomeError("successor source verification group count drifted")

    binding = source_manifest.get("binding")
    minute = source_manifest.get("minute")
    if not isinstance(binding, dict) or not isinstance(minute, dict):
        raise SuccessorDevelopmentOutcomeError("successor source manifest structure drifted")
    if int(binding.get("source_binding_group_count", -1)) != ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT:
        raise SuccessorDevelopmentOutcomeError("successor source manifest group count drifted")
    if int(minute.get("unit_count", -1)) != ACCEPTED_SUCCESSOR_MINUTE_SOURCE_UNITS:
        raise SuccessorDevelopmentOutcomeError("successor minute source unit count drifted")

    expected_authority = frozen_authority_contract()
    for payload, label in ((summary, "summary"), (source_manifest, "source manifest")):
        if payload.get("authority") != expected_authority:
            raise SuccessorDevelopmentOutcomeError(f"successor {label} authority drifted")
    if summary.get("historical_outcomes_opened") is not False:
        raise SuccessorDevelopmentOutcomeError("accepted preflight must have opened zero historical outcomes")

    source_manifest_fingerprint = canonical_sha256(source_manifest)
    if summary.get("source_manifest_fingerprint") != source_manifest_fingerprint:
        raise SuccessorDevelopmentOutcomeError("successor source manifest fingerprint drifted")

    try:
        relative_summary = summary_path.resolve().relative_to(root).as_posix()
    except ValueError as exc:  # pragma: no cover - construction guard
        raise SuccessorDevelopmentOutcomeError("successor preflight summary escapes project root") from exc
    return AcceptedSuccessorPreflight(
        runner_contract_fingerprint=runner_contract_fingerprint,
        source_verification_run_fingerprint=run_fingerprint,
        source_manifest_fingerprint=source_manifest_fingerprint,
        source_group_count=ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT,
        minute_source_units=ACCEPTED_SUCCESSOR_MINUTE_SOURCE_UNITS,
        summary_path=relative_summary,
    )


def _directional_return(*, direction: str, entry: float, exit_price: float) -> float:
    if direction == "LONG":
        return exit_price / entry - 1.0
    if direction == "SHORT":
        return 1.0 - exit_price / entry
    raise SuccessorDevelopmentOutcomeError(f"unsupported direction: {direction}")


def _net_return_with_cost(
    *, direction: str, entry: float, exit_price: float, round_trip_cost_bps: float
) -> float:
    half = round_trip_cost_bps / 20_000.0
    if direction == "LONG":
        return (exit_price * (1.0 - half) - entry * (1.0 + half)) / entry
    if direction == "SHORT":
        return (entry * (1.0 - half) - exit_price * (1.0 + half)) / entry
    raise SuccessorDevelopmentOutcomeError(f"unsupported direction: {direction}")


def _finite_positive(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if math.isfinite(numeric) and numeric > 0.0 else None


def evaluate_daily_diagnostic_outcome(
    *,
    policy_id: str,
    economic_family_id: str,
    instrument: pd.DataFrame,
    signal_position: int,
    direction: str,
    universe_eligible: bool,
    common_context: Mapping[str, object],
) -> SuccessorDailyDiagnosticOutcome:
    """Frozen next-open 1/5/20-session diagnostic; no strategy-specific refit or exit."""

    if instrument.empty or signal_position < 0 or signal_position >= len(instrument):
        raise SuccessorDevelopmentOutcomeError("daily diagnostic signal position is outside instrument history")
    signal = instrument.iloc[signal_position]
    signal_session = pd.Timestamp(signal["session_date"]).date()
    if not DEVELOPMENT_START <= signal_session <= DEVELOPMENT_END:
        raise SuccessorDevelopmentOutcomeError("daily diagnostic signal lies outside DEVELOPMENT")
    signal_available = pd.Timestamp(signal["signal_available_at_utc"])
    if signal_available.tzinfo is None:
        raise SuccessorDevelopmentOutcomeError("daily signal availability must be timezone-aware")

    base = {
        "contract": SUCCESSOR_DEVELOPMENT_OUTCOME_CONTRACT,
        "policy_id": policy_id,
        "economic_family_id": economic_family_id,
        "instrument_id": str(signal["instrument_id"]),
        "ticker": str(signal["ticker"]),
        "signal_session": signal_session.isoformat(),
        "signal_available_at_utc": signal_available.isoformat(),
        "direction": direction,
        "universe_eligible": bool(universe_eligible),
        "common_context": dict(common_context),
    }
    empty_exits = {key: None for key in ("1", "5", "20")}
    empty_costs = {
        str(cost): {key: None for key in ("1", "5", "20")} for cost in COST_GRID_BPS
    }
    if not universe_eligible:
        fields = {
            **base,
            "status": "UNIVERSE_REJECTED",
            "reason_codes": ("SIGNAL_FIRED", "COMMON_UNIVERSE_REJECTED"),
            "entry_session": None,
            "entry_price": None,
            "horizon_exit_sessions": dict(empty_exits),
            "horizon_exit_prices": dict(empty_exits),
            "gross_directional_returns": dict(empty_exits),
            "net_directional_returns_by_cost_bps": empty_costs,
            "maximum_favorable_excursion_20": None,
            "maximum_adverse_excursion_20": None,
        }
        return SuccessorDailyDiagnosticOutcome(**fields, outcome_fingerprint=_stable_hash(fields))

    entry_position = signal_position + 1
    if entry_position >= len(instrument):
        fields = {
            **base,
            "status": "INSUFFICIENT_FUTURE",
            "reason_codes": ("NO_NEXT_REGULAR_SESSION_OPEN",),
            "entry_session": None,
            "entry_price": None,
            "horizon_exit_sessions": dict(empty_exits),
            "horizon_exit_prices": dict(empty_exits),
            "gross_directional_returns": dict(empty_exits),
            "net_directional_returns_by_cost_bps": empty_costs,
            "maximum_favorable_excursion_20": None,
            "maximum_adverse_excursion_20": None,
        }
        return SuccessorDailyDiagnosticOutcome(**fields, outcome_fingerprint=_stable_hash(fields))

    entry_row = instrument.iloc[entry_position]
    entry = _finite_positive(entry_row["open"])
    if entry is None:
        raise SuccessorDevelopmentOutcomeError("daily diagnostic next-session open is invalid")
    entry_session = pd.Timestamp(entry_row["session_date"]).date()
    if entry_session > DEVELOPMENT_END:
        raise SuccessorDevelopmentOutcomeError("daily diagnostic attempted to open post-DEVELOPMENT evidence")

    exit_sessions: dict[str, str | None] = {}
    exit_prices: dict[str, float | None] = {}
    gross: dict[str, float | None] = {}
    net: dict[str, dict[str, float | None]] = {str(cost): {} for cost in COST_GRID_BPS}
    for horizon in (1, 5, 20):
        position = signal_position + horizon
        key = str(horizon)
        if position >= len(instrument):
            exit_sessions[key] = None
            exit_prices[key] = None
            gross[key] = None
            for cost in COST_GRID_BPS:
                net[str(cost)][key] = None
            continue
        row = instrument.iloc[position]
        session = pd.Timestamp(row["session_date"]).date()
        if session > DEVELOPMENT_END:
            raise SuccessorDevelopmentOutcomeError("daily diagnostic attempted to read post-DEVELOPMENT evidence")
        exit_price = _finite_positive(row["close"])
        if exit_price is None:
            raise SuccessorDevelopmentOutcomeError("daily diagnostic horizon close is invalid")
        exit_sessions[key] = session.isoformat()
        exit_prices[key] = exit_price
        gross[key] = _directional_return(direction=direction, entry=entry, exit_price=exit_price)
        for cost in COST_GRID_BPS:
            net[str(cost)][key] = _net_return_with_cost(
                direction=direction,
                entry=entry,
                exit_price=exit_price,
                round_trip_cost_bps=float(cost),
            )

    mfe: float | None = None
    mae: float | None = None
    window_end = signal_position + 20
    if window_end < len(instrument):
        window = instrument.iloc[entry_position : window_end + 1]
        if any(pd.Timestamp(value).date() > DEVELOPMENT_END for value in window["session_date"]):
            raise SuccessorDevelopmentOutcomeError("daily excursion window crossed DEVELOPMENT boundary")
        highs = pd.to_numeric(window["high"], errors="raise").astype(float)
        lows = pd.to_numeric(window["low"], errors="raise").astype(float)
        if direction == "LONG":
            mfe = float(highs.max() / entry - 1.0)
            mae = float(lows.min() / entry - 1.0)
        else:
            mfe = float(1.0 - lows.min() / entry)
            mae = float(1.0 - highs.max() / entry)

    complete = all(gross[key] is not None for key in ("1", "5", "20")) and mfe is not None
    fields = {
        **base,
        "status": "COMPLETE" if complete else "INSUFFICIENT_FUTURE",
        "reason_codes": ("FROZEN_DAILY_DIAGNOSTIC_COMPLETE",) if complete else ("FROZEN_DAILY_DIAGNOSTIC_PARTIAL_FUTURE",),
        "entry_session": entry_session.isoformat(),
        "entry_price": entry,
        "horizon_exit_sessions": exit_sessions,
        "horizon_exit_prices": exit_prices,
        "gross_directional_returns": gross,
        "net_directional_returns_by_cost_bps": net,
        "maximum_favorable_excursion_20": mfe,
        "maximum_adverse_excursion_20": mae,
    }
    return SuccessorDailyDiagnosticOutcome(**fields, outcome_fingerprint=_stable_hash(fields))


def _regular_session_bars(
    bars: Iterable[CanonicalBar], *, session_date: date
) -> tuple[CanonicalBar, ...]:
    selected = tuple(
        sorted(
            (
                bar
                for bar in bars
                if bar.timeframe == Timeframe.MINUTE_1
                and bar.session_segment == SessionSegment.REGULAR
                and bar.session_date == session_date
            ),
            key=lambda item: item.timestamp_utc,
        )
    )
    stamps = [item.timestamp_utc for item in selected]
    if len(stamps) != len(set(stamps)):
        raise SuccessorDevelopmentOutcomeError("duplicate regular minute timestamps are not permitted")
    return selected


def simulate_successor_intraday_outcome(
    signal: SuccessorIntradaySignal,
    bars: Iterable[CanonicalBar],
    *,
    economic_family_id: str,
    symbol: str,
    session_date: date,
    stop_price: float,
) -> SuccessorIntradayDiagnosticOutcome:
    """Frozen next-observed-minute, structural-stop, fixed-2R, adverse-first outcome."""

    if not DEVELOPMENT_START <= session_date <= DEVELOPMENT_END:
        raise SuccessorDevelopmentOutcomeError("intraday outcome lies outside DEVELOPMENT")
    if not signal.ready or not signal.fired or signal.direction not in {"LONG", "SHORT"}:
        raise SuccessorDevelopmentOutcomeError("intraday outcome requires a ready fired successor signal")
    if signal.session_date != session_date.isoformat():
        raise SuccessorDevelopmentOutcomeError("intraday signal/session mismatch")
    if not signal.signal_available_at_utc:
        raise SuccessorDevelopmentOutcomeError("fired intraday signal has no availability timestamp")
    signal_available = datetime.fromisoformat(signal.signal_available_at_utc.replace("Z", "+00:00"))
    if signal_available.tzinfo is None or signal_available.utcoffset() is None:
        raise SuccessorDevelopmentOutcomeError("intraday signal availability must be timezone-aware")
    stop = _finite_positive(stop_price)
    if stop is None:
        raise SuccessorDevelopmentOutcomeError("intraday structural stop must be finite and positive")

    regular = _regular_session_bars(bars, session_date=session_date)
    candidates = [item for item in regular if item.timestamp_utc >= signal_available.astimezone(UTC)]
    base = {
        "contract": SUCCESSOR_DEVELOPMENT_OUTCOME_CONTRACT,
        "policy_id": signal.policy_id,
        "economic_family_id": economic_family_id,
        "symbol": symbol,
        "session_date": session_date.isoformat(),
        "direction": str(signal.direction),
        "signal_available_at_utc": signal_available.astimezone(UTC).isoformat(),
    }

    def noncomparable(status: str, reasons: tuple[str, ...]) -> SuccessorIntradayDiagnosticOutcome:
        fields = {
            **base,
            "status": status,
            "reason_codes": reasons,
            "entry_bar_timestamp_utc": None,
            "entry_price": None,
            "stop_price": stop,
            "target_price": None,
            "exit_bar_timestamp_utc": None,
            "exit_price": None,
            "exit_reason": None,
            "same_bar_collision_adverse_first": False,
            "gross_directional_return": None,
            "net_directional_returns_by_cost_bps": {},
            "risk_multiple": None,
            "maximum_favorable_excursion": None,
            "maximum_adverse_excursion": None,
            "bars_observed_after_entry": 0,
        }
        return SuccessorIntradayDiagnosticOutcome(**fields, outcome_fingerprint=_stable_hash(fields))

    if not candidates:
        return noncomparable("NONCOMPARABLE_NO_NEXT_ENTRY_BAR", ("NO_NEXT_REGULAR_MINUTE_BAR",))
    entry_bar = candidates[0]
    delay = (entry_bar.timestamp_utc - signal_available.astimezone(UTC)).total_seconds() / 60.0
    if delay > MAX_ENTRY_DELAY_MINUTES:
        return noncomparable("NONCOMPARABLE_ENTRY_DELAY", ("NEXT_ENTRY_BAR_EXCEEDS_MAX_DELAY",))
    entry = _finite_positive(entry_bar.open)
    if entry is None:
        raise SuccessorDevelopmentOutcomeError("intraday entry open is invalid")
    if signal.direction == "LONG":
        risk = entry - stop
        target = entry + TARGET_R_MULTIPLE * risk
        geometry = stop < entry
    else:
        risk = stop - entry
        target = entry - TARGET_R_MULTIPLE * risk
        geometry = stop > entry
    if not geometry or risk <= 0.0 or target <= 0.0:
        return noncomparable("NONCOMPARABLE_INVALID_STOP_GEOMETRY", ("STOP_ENTRY_TARGET_GEOMETRY_INVALID",))

    mfe = 0.0
    mae = 0.0
    exit_bar: CanonicalBar | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    collision = False
    observed = 0
    for bar in candidates:
        observed += 1
        local_time = bar.timestamp_utc.astimezone(MARKET_TZ).time()
        if TIME_EXIT_START_ET <= local_time <= TIME_EXIT_END_ET:
            exit_bar, exit_price, exit_reason = bar, float(bar.open), "TIME_EXIT"
            break
        if signal.direction == "LONG":
            stop_gap = float(bar.open) < stop
            target_gap = float(bar.open) >= target
            stop_hit = float(bar.low) <= stop
            target_hit = float(bar.high) >= target
        else:
            stop_gap = float(bar.open) > stop
            target_gap = float(bar.open) <= target
            stop_hit = float(bar.high) >= stop
            target_hit = float(bar.low) <= target
        if stop_gap:
            exit_bar, exit_price, exit_reason = bar, float(bar.open), "STOP_GAP_WORSE_OPEN"
            break
        if target_gap:
            exit_bar, exit_price, exit_reason = bar, target, "TARGET_GAP_NO_BETTER_THAN_TARGET"
            break
        if stop_hit and target_hit:
            exit_bar, exit_price, exit_reason = bar, stop, "STOP_AND_TARGET_SAME_BAR_ADVERSE_FIRST"
            collision = True
            break
        if stop_hit:
            exit_bar, exit_price, exit_reason = bar, stop, "STOP"
            break
        if target_hit:
            exit_bar, exit_price, exit_reason = bar, target, "TARGET_2R"
            break
        if signal.direction == "LONG":
            favorable = float(bar.high) / entry - 1.0
            adverse = float(bar.low) / entry - 1.0
        else:
            favorable = 1.0 - float(bar.low) / entry
            adverse = 1.0 - float(bar.high) / entry
        mfe = max(mfe, favorable)
        mae = min(mae, adverse)

    if exit_bar is None or exit_price is None or exit_reason is None:
        fields = {
            **base,
            "status": "NONCOMPARABLE_UNRESOLVED_EXIT_AFTER_ENTRY",
            "reason_codes": ("NO_STOP_TARGET_OR_OBSERVED_TIME_EXIT",),
            "entry_bar_timestamp_utc": entry_bar.timestamp_utc.isoformat(),
            "entry_price": entry,
            "stop_price": stop,
            "target_price": target,
            "exit_bar_timestamp_utc": None,
            "exit_price": None,
            "exit_reason": None,
            "same_bar_collision_adverse_first": False,
            "gross_directional_return": None,
            "net_directional_returns_by_cost_bps": {},
            "risk_multiple": None,
            "maximum_favorable_excursion": mfe,
            "maximum_adverse_excursion": mae,
            "bars_observed_after_entry": observed,
        }
        return SuccessorIntradayDiagnosticOutcome(**fields, outcome_fingerprint=_stable_hash(fields))

    gross = _directional_return(direction=str(signal.direction), entry=entry, exit_price=exit_price)
    r_multiple = (exit_price - entry) / risk if signal.direction == "LONG" else (entry - exit_price) / risk
    mfe = max(mfe, gross)
    mae = min(mae, gross)
    net = {
        str(cost): _net_return_with_cost(
            direction=str(signal.direction),
            entry=entry,
            exit_price=exit_price,
            round_trip_cost_bps=float(cost),
        )
        for cost in COST_GRID_BPS
    }
    fields = {
        **base,
        "status": "EXITED",
        "reason_codes": ("FROZEN_SUCCESSOR_INTRADAY_OUTCOME_RESOLVED",),
        "entry_bar_timestamp_utc": entry_bar.timestamp_utc.isoformat(),
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "exit_bar_timestamp_utc": exit_bar.timestamp_utc.isoformat(),
        "exit_price": exit_price,
        "exit_reason": exit_reason,
        "same_bar_collision_adverse_first": collision,
        "gross_directional_return": gross,
        "net_directional_returns_by_cost_bps": net,
        "risk_multiple": r_multiple,
        "maximum_favorable_excursion": mfe,
        "maximum_adverse_excursion": mae,
        "bars_observed_after_entry": observed,
    }
    return SuccessorIntradayDiagnosticOutcome(**fields, outcome_fingerprint=_stable_hash(fields))


def outcome_contract_manifest() -> dict[str, object]:
    payload = {
        "contract": SUCCESSOR_DEVELOPMENT_OUTCOME_CONTRACT,
        "accepted_runner_contract_fingerprint": ACCEPTED_SUCCESSOR_RUNNER_CONTRACT_FINGERPRINT,
        "accepted_source_verification_run_fingerprint": ACCEPTED_SUCCESSOR_SOURCE_VERIFICATION_RUN_FINGERPRINT,
        "accepted_source_group_count": ACCEPTED_SUCCESSOR_SOURCE_GROUP_COUNT,
        "accepted_minute_source_units": ACCEPTED_SUCCESSOR_MINUTE_SOURCE_UNITS,
        "scope": [DEVELOPMENT_START.isoformat(), DEVELOPMENT_END.isoformat()],
        "daily": {
            "entry": "NEXT_REGULAR_SESSION_OPEN_AFTER_SIGNAL_CLOSE",
            "horizons_sessions": [1, 5, 20],
            "mfe_mae_sessions": 20,
            "insufficient_future": "INSUFFICIENT_FUTURE",
        },
        "intraday": {
            "entry": "NEXT_OBSERVED_REGULAR_MINUTE_MAX_5M_DELAY",
            "target_r": TARGET_R_MULTIPLE,
            "same_bar_collision": "STOP_WINS_CONSERVATIVE",
            "time_exit": "FIRST_OBSERVED_REGULAR_BAR_1555_THROUGH_1559_ET",
        },
        "cost_grid_bps": list(COST_GRID_BPS),
        "cost_application": "HALF_ALL_IN_ROUND_TRIP_COST_ADVERSE_AT_ENTRY_AND_EXIT",
        "authority": {
            **frozen_authority_contract(),
            "historical_outcomes_opened_by_preflight": False,
            "development_outcomes_require_separate_cli_authorization": True,
        },
    }
    payload["fingerprint"] = canonical_sha256(payload)
    return payload


SUCCESSOR_DEVELOPMENT_OUTCOME_FINGERPRINT = str(outcome_contract_manifest()["fingerprint"])
