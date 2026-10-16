from __future__ import annotations

"""Causal feature arithmetic for invented pilot inputs, without historical replay.

The variance comparison is an input filter. It is not a straddle price, profit
forecast, selected contract, execution or account admission.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
import re
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.strategies.options_native_pilot_v1_contract import (
    AUTHORITY, END_DATE, IMPLIED_INPUT_FINGERPRINT, LOOKBACK_RETURNS, MAX_DTE,
    SPECIFICATION_FINGERPRINT, START_DATE,
)

ORIGIN = "SYNTHETIC_FIXTURE_ONLY"
YEAR_SECONDS = Decimal(365 * 86400)


class OptionsNativePilotError(ValueError):
    pass


def _utc(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise OptionsNativePilotError("pilot clocks require aware datetimes")
    return value.astimezone(UTC)


def _decimal(value: str, *, signed: bool = False) -> Decimal:
    if not isinstance(value, str) or not value or len(value) > 64 or value.strip() != value:
        raise OptionsNativePilotError("bounded exact decimal strings required")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise OptionsNativePilotError("invalid decimal") from exc
    if (not number.is_finite() or abs(number) > 10 or (not signed and number <= 0)
            or not -24 <= number.as_tuple().exponent <= 6):
        raise OptionsNativePilotError("variance input outside finite bounds")
    return number


@dataclass(frozen=True, slots=True)
class PriorEconomicLogReturnV1:
    interval_start_utc: datetime
    interval_end_utc: datetime
    available_at_utc: datetime
    log_return: str
    source_fingerprint: str


@dataclass(frozen=True, slots=True)
class SyntheticPilotVarianceInputV1:
    feature_cutoff_utc: datetime
    model_maturity_utc: datetime
    prior_returns: tuple[PriorEconomicLogReturnV1, ...]
    call_iv: str
    put_iv: str
    implied_observed_at_utc: datetime
    implied_available_at_utc: datetime
    implied_model_fingerprint: str
    source_integrity_qualified: bool
    availability_clocks_qualified: bool
    corporate_actions_qualified: bool
    rate_dividend_inputs_qualified: bool
    symbol: str = "SPY"
    origin: str = ORIGIN


def _payload(value: Any) -> Any:
    if isinstance(value, datetime):
        return _utc(value).isoformat()
    if isinstance(value, dict):
        return {key: _payload(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_payload(item) for item in value]
    return value


def screen_synthetic_pilot_variance(inputs: SyntheticPilotVarianceInputV1) -> dict[str, Any]:
    if not isinstance(inputs, SyntheticPilotVarianceInputV1) or inputs.origin != ORIGIN or inputs.symbol != "SPY":
        raise OptionsNativePilotError("explicit SPY synthetic fixture required; no historical adapter")
    decision, maturity = _utc(inputs.feature_cutoff_utc), _utc(inputs.model_maturity_utc)
    ready = decision + timedelta(minutes=1)
    local = decision.astimezone(ZoneInfo("America/New_York"))
    calendar = get_market_calendar("XNYS")
    if (not START_DATE <= local.date().isoformat() <= END_DATE
            or (local.hour, local.minute, local.second, local.microsecond) != (10, 0, 0, 0)
            or not calendar.is_session(local.date())):
        raise OptionsNativePilotError("pilot requires a pre-2026 session feature cutoff at 10:00 ET")
    observed, available = _utc(inputs.implied_observed_at_utc), _utc(inputs.implied_available_at_utc)
    if (not ready < maturity <= decision + timedelta(days=MAX_DTE + 1)
            or maturity.astimezone(ZoneInfo("America/New_York")).date().isoformat() > END_DATE):
        raise OptionsNativePilotError("same explicit future model maturity within pilot bound required")
    if not isinstance(inputs.prior_returns, tuple) or len(inputs.prior_returns) != LOOKBACK_RETURNS:
        raise OptionsNativePilotError("exactly 20 prior return intervals required")
    for item in inputs.prior_returns:
        if not isinstance(item, PriorEconomicLogReturnV1):
            raise OptionsNativePilotError("typed prior return interval required")
        start, end, known = _utc(item.interval_start_utc), _utc(item.interval_end_utc), _utc(item.available_at_utc)
        if (not start < end <= known or not isinstance(item.source_fingerprint, str)
                or not re.fullmatch(r"[0-9a-f]{64}", item.source_fingerprint)):
            raise OptionsNativePilotError("return interval chronology or source identity malformed")
        _decimal(item.log_return, signed=True)
    _decimal(inputs.call_iv)
    _decimal(inputs.put_iv)
    gates = (
        ("source_integrity_qualified", "UNQUALIFIED_SOURCE"),
        ("availability_clocks_qualified", "UNQUALIFIED_AVAILABILITY_CLOCKS"),
        ("corporate_actions_qualified", "UNQUALIFIED_ECONOMIC_RETURN_ADJUSTMENTS"),
        ("rate_dividend_inputs_qualified", "UNQUALIFIED_RATE_DIVIDEND_INPUTS"),
    )
    if any(type(getattr(inputs, name)) is not bool for name, _ in gates):
        raise OptionsNativePilotError("qualification flags must be boolean")
    reasons = [reason for name, reason in gates if not getattr(inputs, name)]
    if inputs.implied_model_fingerprint != IMPLIED_INPUT_FINGERPRINT:
        reasons.append("IMPLIED_MODEL_CONTRACT_MISMATCH")
    if (not observed <= decision or not observed <= available <= ready
            or observed < decision - timedelta(seconds=30)):
        reasons.append("FUTURE_LATE_OR_STALE_IMPLIED_INPUT")
    history = sorted(inputs.prior_returns, key=lambda item: _utc(item.interval_end_utc))
    if any(_utc(item.available_at_utc) > ready for item in history):
        reasons.append("FUTURE_OR_LATE_RETURN_INPUT")
    # Session-close labels, not option trading/expiry hours. Require the exact
    # previous 21 completed closes so missing history cannot silently shrink or
    # move the lookback window.
    days = calendar.sessions_in_range((decision - timedelta(days=75)).date(), decision.date())
    closes = [calendar.regular_open_close(day)[1] for day in days]
    closes = [at for at in closes if at < decision][-LOOKBACK_RETURNS - 1:]
    expected_intervals = list(zip(closes, closes[1:]))
    actual_intervals = [(_utc(item.interval_start_utc), _utc(item.interval_end_utc)) for item in history]
    if len(expected_intervals) != LOOKBACK_RETURNS or actual_intervals != expected_intervals:
        reasons.append("MISSING_DUPLICATE_OR_NONPRIOR_RETURN_WINDOW")
    total_forecast = total_implied = variance_rate = None
    if not reasons:
        elapsed = Decimal(sum(int((_utc(item.interval_end_utc) - _utc(item.interval_start_utc)).total_seconds())
                              for item in history))
        remaining = Decimal(str((maturity - ready).total_seconds()))
        variance_rate = sum((_decimal(item.log_return, signed=True) ** 2 for item in history), Decimal(0)) / elapsed
        total_forecast = variance_rate * remaining
        pair_iv_variance = (_decimal(inputs.call_iv) ** 2 + _decimal(inputs.put_iv) ** 2) / 2
        total_implied = pair_iv_variance * remaining / YEAR_SECONDS
        if total_forecast <= total_implied:
            reasons.append("NO_POSITIVE_FORECAST_VARIANCE_GAP")
    result = {
        "contract": "atlas-options-native-synthetic-variance-screen-v1",
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "input_fingerprint": _fingerprint(_payload(asdict(inputs))),
        "status": "FIXTURE_VARIANCE_FILTER_PASS" if not reasons else "FIXTURE_ABSTAIN",
        "reasons": reasons, "feature_cutoff_utc": decision.isoformat(),
        "decision_ready_utc": ready.isoformat(),
        "model_maturity_utc": maturity.isoformat(),
        "forecast_total_variance": str(total_forecast) if total_forecast is not None else None,
        "implied_total_variance": str(total_implied) if total_implied is not None else None,
        "forecast_variance_per_calendar_second": str(variance_rate) if variance_rate is not None else None,
        "expected_dollar_profit": None, "contracts_selected": 0,
        "historical_performance_evidence": False, "authority": dict(AUTHORITY),
    }
    result["screen_fingerprint"] = _fingerprint(result)
    return result
