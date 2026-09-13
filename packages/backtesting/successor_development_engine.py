from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from statistics import median
from typing import Iterable, Mapping, Sequence

import pandas as pd

from packages.backtesting.b35_development_context import build_condition_snapshot
from packages.backtesting.b35_development_replay import (
    _SymbolHistory,
    _current_regular_open,
    _evaluate_setups,
    _premarket_volume,
    _signal_time_override,
    _split_epoch,
)
from packages.backtesting.b35_intraday_outcomes import simulate_intraday_outcome
from packages.backtesting.reference_strategy_runner import _universe_decision
from packages.backtesting.successor_development_outcomes import (
    SuccessorDevelopmentOutcomeError,
    evaluate_daily_diagnostic_outcome,
    simulate_successor_intraday_outcome,
)
from packages.backtesting.successor_runner_contract import successor_policy_routes
from packages.features.successor_practitioner import (
    compute_successor_daily_features,
    successor_common_context_from_row,
)
from packages.features.volatility import normalized_atr
from packages.schemas.market import CanonicalBar
from packages.strategies.reference_library import REFERENCE_STRATEGY_CATALOG
from packages.strategies.successor_intraday_rules import (
    SuccessorIntradaySignal,
    evaluate_gap_quality_condition_long,
    evaluate_orb_15m_close_retest,
    evaluate_orb_stocks_in_play_5m,
    evaluate_premarket_relvol_quality,
    evaluate_session_failed_break_reclaim,
    evaluate_vwap_reclaim_reject,
)
from packages.strategies.successor_practitioner_rules import (
    ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS,
)


SUCCESSOR_STANDALONE_ENGINE_CONTRACT = (
    "atlas-successor-standalone-engine-v1-shared-daily-single-minute-scan"
)
MARKET_TZ = __import__("zoneinfo").ZoneInfo("America/New_York")


@dataclass(frozen=True, slots=True)
class RawMinuteDailySummary:
    session_date: date
    high: float
    low: float
    close: float
    dollar_volume: float
    split_epoch: float


@dataclass(slots=True)
class SuccessorMinuteHistory:
    daily: list[RawMinuteDailySummary] = field(default_factory=list)
    premarket_volumes: list[tuple[date, float]] = field(default_factory=list)
    opening_five_minute_volumes: list[tuple[date, float]] = field(default_factory=list)
    same_time_regular_volumes: dict[time, list[tuple[date, float]]] = field(default_factory=dict)

    def append_session(
        self,
        bars: Sequence[CanonicalBar],
        *,
        session_date: date,
        split_epoch: float,
    ) -> None:
        regular = sorted(
            (
                bar
                for bar in bars
                if bar.session_date == session_date
                and bar.session_segment.value == "regular"
            ),
            key=lambda item: item.timestamp_utc,
        )
        premarket = [
            bar
            for bar in bars
            if bar.session_date == session_date
            and bar.session_segment.value == "premarket"
            and time(4, 0) <= bar.timestamp_utc.astimezone(MARKET_TZ).time() < time(9, 30)
        ]
        if premarket:
            self.premarket_volumes.append(
                (session_date, float(sum(float(item.volume) for item in premarket)))
            )
            del self.premarket_volumes[:-25]
        if not regular:
            return
        high = max(float(item.high) for item in regular)
        low = min(float(item.low) for item in regular)
        close = float(regular[-1].close)
        dollar_volume = float(
            sum(
                float(item.volume)
                * float(item.vwap if item.vwap is not None else item.close)
                for item in regular
            )
        )
        self.daily.append(
            RawMinuteDailySummary(
                session_date=session_date,
                high=high,
                low=low,
                close=close,
                dollar_volume=dollar_volume,
                split_epoch=split_epoch,
            )
        )
        del self.daily[:-260]

        opening = [
            item
            for item in regular
            if time(9, 30) <= item.timestamp_utc.astimezone(MARKET_TZ).time() < time(9, 35)
        ]
        if len(opening) == 5:
            self.opening_five_minute_volumes.append(
                (session_date, float(sum(float(item.volume) for item in opening)))
            )
            del self.opening_five_minute_volumes[:-25]
        for item in regular:
            local_time = item.timestamp_utc.astimezone(MARKET_TZ).time().replace(tzinfo=None)
            history = self.same_time_regular_volumes.setdefault(local_time, [])
            history.append((session_date, float(item.volume)))
            del history[:-25]

    def prior_median_dollar_volume_20(self) -> float | None:
        if len(self.daily) < 20:
            return None
        return float(median(item.dollar_volume for item in self.daily[-20:]))

    def prior_premarket_median_volume_20(self) -> float | None:
        if len(self.premarket_volumes) < 20:
            return None
        return float(median(value for _, value in self.premarket_volumes[-20:]))

    def opening_five_minute_relvol(self, bars: Sequence[CanonicalBar], session_date: date) -> float | None:
        if len(self.opening_five_minute_volumes) < 20:
            return None
        opening = [
            item
            for item in bars
            if item.session_date == session_date
            and item.session_segment.value == "regular"
            and time(9, 30) <= item.timestamp_utc.astimezone(MARKET_TZ).time() < time(9, 35)
        ]
        if len(opening) != 5:
            return None
        denominator = float(median(value for _, value in self.opening_five_minute_volumes[-20:]))
        if denominator <= 0.0:
            return None
        return float(sum(float(item.volume) for item in opening)) / denominator

    def same_time_relvol_map(
        self, bars: Sequence[CanonicalBar], session_date: date
    ) -> dict[datetime, float]:
        result: dict[datetime, float] = {}
        for item in bars:
            if item.session_date != session_date or item.session_segment.value != "regular":
                continue
            local_time = item.timestamp_utc.astimezone(MARKET_TZ).time().replace(tzinfo=None)
            prior = self.same_time_regular_volumes.get(local_time, [])
            if len(prior) < 20:
                continue
            denominator = float(median(value for _, value in prior[-20:]))
            if denominator > 0.0:
                result[item.timestamp_utc] = float(item.volume) / denominator
        return result

    def split_crossed_prior_close(self, current_epoch: float) -> bool:
        return not self.daily or not math.isclose(
            self.daily[-1].split_epoch,
            current_epoch,
            rel_tol=1e-10,
            abs_tol=1e-12,
        )

    def prior_natr_14(self, current_epoch: float) -> float | None:
        same_epoch: list[RawMinuteDailySummary] = []
        for item in reversed(self.daily):
            if not math.isclose(
                item.split_epoch, current_epoch, rel_tol=1e-10, abs_tol=1e-12
            ):
                break
            same_epoch.append(item)
        same_epoch.reverse()
        if len(same_epoch) < 14:
            return None
        frame = pd.DataFrame(
            {
                "high": [item.high for item in same_epoch],
                "low": [item.low for item in same_epoch],
                "close": [item.close for item in same_epoch],
            }
        )
        series = normalized_atr(frame["high"], frame["low"], frame["close"], 14)
        value = series.iloc[-1]
        if pd.isna(value) or not math.isfinite(float(value)):
            return None
        return float(value)

    def prior_trend_20_50(self, current_epoch: float) -> str:
        same_epoch: list[RawMinuteDailySummary] = []
        for item in reversed(self.daily):
            if not math.isclose(item.split_epoch, current_epoch, rel_tol=1e-10, abs_tol=1e-12):
                break
            same_epoch.append(item)
        same_epoch.reverse()
        if len(same_epoch) < 50:
            return "UNAVAILABLE"
        closes = [item.close for item in same_epoch[-50:]]
        sma20 = sum(closes[-20:]) / 20.0
        sma50 = sum(closes) / 50.0
        latest = closes[-1]
        if latest > sma20 > sma50:
            return "BULL"
        if latest < sma20 < sma50:
            return "BEAR"
        return "MIXED"

    def prior_realized_volatility_20(self, current_epoch: float) -> float | None:
        same_epoch: list[RawMinuteDailySummary] = []
        for item in reversed(self.daily):
            if not math.isclose(item.split_epoch, current_epoch, rel_tol=1e-10, abs_tol=1e-12):
                break
            same_epoch.append(item)
        same_epoch.reverse()
        if len(same_epoch) < 21:
            return None
        closes = [item.close for item in same_epoch[-21:]]
        returns = [math.log(closes[index] / closes[index - 1]) for index in range(1, 21)]
        mean = sum(returns) / len(returns)
        variance = sum((value - mean) ** 2 for value in returns) / len(returns)
        return math.sqrt(variance) * math.sqrt(252.0)


_DAILY_ROUTES = tuple(route for route in successor_policy_routes() if route.native_timeframe == "1d")
_MINUTE_ROUTES = tuple(route for route in successor_policy_routes() if route.native_timeframe == "1m")
_IMPLEMENTATIONS = {item.policy_id: item for item in ALL_SUCCESSOR_POLICY_IMPLEMENTATIONS}


def evaluate_successor_daily_standalone(
    frame: pd.DataFrame,
    *,
    benchmark_frame: pd.DataFrame,
) -> list[dict[str, object]]:
    """Evaluate all 18 frozen daily routes while computing shared PIT features once."""

    if frame.empty:
        return []
    features = compute_successor_daily_features(frame, benchmark_frame=benchmark_frame)
    records: list[dict[str, object]] = []
    for instrument_id, instrument_frame in features.groupby(
        "instrument_id", sort=True, observed=True
    ):
        instrument = instrument_frame.sort_values("session_date", kind="stable").reset_index(drop=True)
        for route in _DAILY_ROUTES:
            if route.evaluator_contract_id == "accepted_reference_daily_v1":
                specification = REFERENCE_STRATEGY_CATALOG.get(route.policy_id)
                pairs = ((specification.direction.value, specification.signal.trigger_feature, True),)
            elif route.evaluator_contract_id == "successor_practitioner_daily_v1":
                implementation = _IMPLEMENTATIONS[route.policy_id]
                pairs = tuple(
                    (direction, trigger, False)
                    for direction, trigger in zip(
                        implementation.directions,
                        implementation.trigger_features,
                        strict=True,
                    )
                )
            else:
                raise SuccessorDevelopmentOutcomeError(
                    f"unsupported daily evaluator contract: {route.evaluator_contract_id}"
                )
            for direction, trigger_feature, retain_reference_universe in pairs:
                if trigger_feature not in instrument.columns:
                    raise SuccessorDevelopmentOutcomeError(
                        f"daily trigger feature missing: {route.policy_id}:{trigger_feature}"
                    )
                fired_positions = [
                    position
                    for position, value in enumerate(instrument[trigger_feature].tolist())
                    if not pd.isna(value) and float(value) == 1.0
                ]
                for position in fired_positions:
                    row = instrument.iloc[position]
                    universe_eligible = True
                    universe_reasons: tuple[str, ...] = ("SOURCE_COMMON_STOCK_PIT_IDENTITY_ACCEPTED",)
                    if retain_reference_universe:
                        universe_eligible, universe_reasons = _universe_decision(row)
                    outcome = evaluate_daily_diagnostic_outcome(
                        policy_id=route.policy_id,
                        economic_family_id=route.economic_family_id,
                        instrument=instrument,
                        signal_position=position,
                        direction=direction,
                        universe_eligible=universe_eligible,
                        common_context=successor_common_context_from_row(row),
                    )
                    records.append(
                        {
                            "engine_contract": SUCCESSOR_STANDALONE_ENGINE_CONTRACT,
                            "route": route.as_dict(),
                            "signal": {
                                "instrument_id": str(instrument_id),
                                "ticker": str(row["ticker"]),
                                "session_date": str(row["session_date"]),
                                "direction": direction,
                                "trigger_feature": trigger_feature,
                                "universe_eligible": universe_eligible,
                                "universe_reason_codes": list(universe_reasons),
                            },
                            "outcome": asdict(outcome),
                        }
                    )
    records.sort(
        key=lambda item: (
            str(item["route"]["policy_id"]),
            str(item["signal"]["instrument_id"]),
            str(item["signal"]["session_date"]),
            str(item["signal"]["direction"]),
        )
    )
    return records


def _first_fired_successor(
    evaluator,
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    earliest: time,
    latest: time,
    kwargs: Mapping[str, object] | None = None,
) -> SuccessorIntradaySignal | None:
    kwargs = dict(kwargs or {})
    regular = [
        bar
        for bar in bars
        if bar.session_date == session_date
        and bar.session_segment.value == "regular"
        and earliest <= bar.timestamp_utc.astimezone(MARKET_TZ).time() <= latest
    ]
    for bar in regular:
        result = evaluator(
            bars,
            session_date=session_date,
            decision_time_utc=bar.timestamp_utc + timedelta(minutes=1),
            **kwargs,
        )
        if result.ready and result.fired:
            return result
    return None


def _decision_stamp(session_date: date, value: time) -> datetime:
    return datetime.combine(session_date, value, tzinfo=MARKET_TZ).astimezone(UTC)


def _signal_bar(bars: Sequence[CanonicalBar], signal: SuccessorIntradaySignal) -> CanonicalBar | None:
    if not signal.signal_available_at_utc:
        return None
    available = datetime.fromisoformat(signal.signal_available_at_utc.replace("Z", "+00:00")).astimezone(UTC)
    stamp = available - timedelta(minutes=1)
    return next((item for item in bars if item.timestamp_utc == stamp), None)


def _stop_for_successor_signal(
    signal: SuccessorIntradaySignal,
    bars: Sequence[CanonicalBar],
    *,
    prior_regular_close: float | None,
) -> float | None:
    if signal.policy_id in {
        "pract_vwap_reclaim_reject_v1",
        "pract_session_failed_break_reclaim_v1",
    }:
        signal_bar = _signal_bar(bars, signal)
        if signal_bar is None:
            return None
        return float(signal_bar.low if signal.direction == "LONG" else signal_bar.high)
    if signal.policy_id == "gap_quality_condition_long_v2":
        return prior_regular_close
    if signal.policy_id in {"orb_stocks_in_play_5m_v1", "orb_15m_close_retest_v2"}:
        key = "range_low" if signal.direction == "LONG" else "range_high"
        value = signal.evidence.get(key)
        return None if value is None else float(value)
    if signal.policy_id == "premarket_relvol_quality_v2":
        value = signal.evidence.get("consolidation_low")
        return None if value is None else float(value)
    raise SuccessorDevelopmentOutcomeError(f"unsupported successor minute policy: {signal.policy_id}")


def _liquidity_quality(value: float | None) -> str:
    if value is None:
        return "UNAVAILABLE"
    if value >= 50_000_000.0:
        return "HIGH"
    if value >= 20_000_000.0:
        return "MEDIUM"
    if value >= 5_000_000.0:
        return "BASE"
    return "INELIGIBLE"


def successor_minute_common_context(
    signal: SuccessorIntradaySignal,
    bars: Sequence[CanonicalBar],
    *,
    history: SuccessorMinuteHistory,
    current_epoch: float,
    opening_same_time_relvol: float | None,
    premarket_relvol: float | None,
) -> dict[str, object]:
    prior = history.daily[-1] if history.daily else None
    regular_open = _current_regular_open(bars, date.fromisoformat(signal.session_date))
    gap = None
    if (
        prior is not None
        and regular_open is not None
        and not history.split_crossed_prior_close(current_epoch)
        and prior.close > 0.0
    ):
        gap = regular_open / prior.close - 1.0
    signal_bar = _signal_bar(bars, signal)
    price = None if signal_bar is None else float(signal_bar.close)
    if price is None:
        price_band = "UNAVAILABLE"
    elif price < 5.0:
        price_band = "LT_5"
    elif price < 10.0:
        price_band = "5_10"
    elif price < 25.0:
        price_band = "10_25"
    elif price < 50.0:
        price_band = "25_50"
    elif price < 100.0:
        price_band = "50_100"
    else:
        price_band = "GE_100"
    available = None
    if signal.signal_available_at_utc:
        available = datetime.fromisoformat(signal.signal_available_at_utc.replace("Z", "+00:00"))
    dollar_volume = history.prior_median_dollar_volume_20()
    return {
        "market_direction_alignment": "UNAVAILABLE",
        "market_volatility_state": "UNAVAILABLE",
        "ticker_relative_strength_vs_spy_short_horizon": None,
        "ticker_relative_strength_vs_spy_medium_horizon": None,
        "higher_timeframe_ticker_trend": history.prior_trend_20_50(current_epoch),
        "atr_normalized_trend_maturity_extension": None,
        "opening_same_time_volume_participation": opening_same_time_relvol,
        "premarket_volume_participation": premarket_relvol,
        "prior_dollar_volume_liquidity": dollar_volume,
        "overnight_gap": gap,
        "price_band": price_band,
        "signal_time": (
            "UNAVAILABLE"
            if available is None
            else available.astimezone(MARKET_TZ).time().isoformat()
        ),
        "realized_volatility": history.prior_realized_volatility_20(current_epoch),
        "execution_liquidity_quality": _liquidity_quality(dollar_volume),
    }


def _new_successor_minute_signals(
    bars: Sequence[CanonicalBar],
    *,
    session_date: date,
    history: SuccessorMinuteHistory,
    current_epoch: float,
) -> list[tuple[SuccessorIntradaySignal, float | None, float | None]]:
    signals: list[tuple[SuccessorIntradaySignal, float | None, float | None]] = []
    prior = history.daily[-1] if history.daily else None
    prior_close = None if prior is None else prior.close
    prior_dv = history.prior_median_dollar_volume_20()
    prior_pm_median = history.prior_premarket_median_volume_20()
    natr14 = history.prior_natr_14(current_epoch)
    opening_relvol = history.opening_five_minute_relvol(bars, session_date)
    pm_volume = _premarket_volume(bars, session_date)
    pm_relvol = (
        None
        if pm_volume is None or prior_pm_median is None or prior_pm_median <= 0.0
        else pm_volume / prior_pm_median
    )

    vwap = _first_fired_successor(
        evaluate_vwap_reclaim_reject,
        bars,
        session_date=session_date,
        earliest=time(9, 31),
        latest=time(15, 30),
    )
    if vwap is not None:
        signals.append((vwap, opening_relvol, pm_relvol))

    if prior is not None and not history.split_crossed_prior_close(current_epoch):
        premarket = [
            item
            for item in bars
            if item.session_date == session_date and item.session_segment.value == "premarket"
        ]
        pm_high = max((float(item.high) for item in premarket), default=None)
        pm_low = min((float(item.low) for item in premarket), default=None)
        failed_break = _first_fired_successor(
            evaluate_session_failed_break_reclaim,
            bars,
            session_date=session_date,
            earliest=time(9, 30),
            latest=time(15, 30),
            kwargs={
                "prior_regular_high": prior.high,
                "prior_regular_low": prior.low,
                "premarket_high": pm_high,
                "premarket_low": pm_low,
            },
        )
        if failed_break is not None:
            signals.append((failed_break, opening_relvol, pm_relvol))

    if (
        prior_close is not None
        and prior_dv is not None
        and natr14 is not None
        and pm_relvol is not None
    ):
        gap = evaluate_gap_quality_condition_long(
            bars,
            session_date=session_date,
            decision_time_utc=_decision_stamp(session_date, time(9, 31)),
            prior_regular_close=prior_close,
            prior_median_dollar_volume_20=prior_dv,
            natr_14=natr14,
            premarket_relvol_20=pm_relvol,
            split_crossed=history.split_crossed_prior_close(current_epoch),
        )
        if gap.ready and gap.fired:
            signals.append((gap, opening_relvol, pm_relvol))

    if prior_dv is not None and opening_relvol is not None:
        orb5 = evaluate_orb_stocks_in_play_5m(
            bars,
            session_date=session_date,
            decision_time_utc=_decision_stamp(session_date, time(11, 31)),
            same_time_opening_relvol=opening_relvol,
            prior_median_dollar_volume_20=prior_dv,
        )
        if orb5.ready and orb5.fired:
            signals.append((orb5, opening_relvol, pm_relvol))

    if natr14 is not None and prior_close is not None:
        atr_reference = natr14 * prior_close
        if atr_reference > 0.0:
            orb15 = evaluate_orb_15m_close_retest(
                bars,
                session_date=session_date,
                decision_time_utc=_decision_stamp(session_date, time(15, 31)),
                atr_reference=atr_reference,
            )
            if orb15.ready and orb15.fired:
                signals.append((orb15, opening_relvol, pm_relvol))

    if prior_pm_median is not None and prior_dv is not None:
        pm_quality = evaluate_premarket_relvol_quality(
            bars,
            session_date=session_date,
            decision_time_utc=_decision_stamp(session_date, time(11, 31)),
            prior_premarket_median_volume_20=prior_pm_median,
            prior_median_dollar_volume_20=prior_dv,
            breakout_same_time_relvol_by_timestamp=history.same_time_relvol_map(
                bars, session_date
            ),
        )
        if pm_quality.ready and pm_quality.fired:
            signals.append((pm_quality, opening_relvol, pm_relvol))
    return signals


def evaluate_successor_minute_session(
    bars: Sequence[CanonicalBar],
    *,
    symbol: str,
    session_date: date,
    retained_history: _SymbolHistory,
    successor_history: SuccessorMinuteHistory,
    symbol_split_dates: Sequence[date],
) -> list[dict[str, object]]:
    """Evaluate all retained/new minute routes from one immutable session-bar scan."""

    records: list[dict[str, object]] = []
    current_open = _current_regular_open(bars, session_date)
    if current_open is None:
        pm_volume = _premarket_volume(bars, session_date)
        if pm_volume is not None:
            retained_history.append_premarket(session_date, pm_volume)
        successor_history.append_session(
            bars, session_date=session_date, split_epoch=_split_epoch(symbol_split_dates, session_date)
        )
        return records
    current_epoch = _split_epoch(symbol_split_dates, session_date)

    retained_setups = _evaluate_setups(
        bars,
        session_date=session_date,
        history=retained_history,
        symbol_split_dates=symbol_split_dates,
    )
    retained_routes = {route.policy_id: route for route in _MINUTE_ROUTES if route.evaluator_contract_id == "accepted_b35_intraday_v1"}
    for setup in retained_setups:
        route = retained_routes.get(setup.strategy_id)
        if route is None:
            raise SuccessorDevelopmentOutcomeError(
                f"retained B35 setup is outside frozen successor routes: {setup.strategy_id}"
            )
        outcome = simulate_intraday_outcome(
            setup,
            bars,
            symbol=symbol,
            session_date=session_date,
        )
        records.append(
            {
                "engine_contract": SUCCESSOR_STANDALONE_ENGINE_CONTRACT,
                "route": route.as_dict(),
                "signal": asdict(setup),
                "context": asdict(
                    build_condition_snapshot(
                        setup,
                        bars,
                        symbol=symbol,
                        session_date=session_date,
                        prior_daily=retained_history.daily,
                        current_regular_open=current_open,
                        current_split_factor=current_epoch,
                        prior_market_regime="UNAVAILABLE",
                        signal_time_et_override=_signal_time_override(
                            setup, bars, session_date
                        ),
                    )
                ),
                "outcome": asdict(outcome),
            }
        )

    new_routes = {route.policy_id: route for route in _MINUTE_ROUTES if route.evaluator_contract_id == "successor_intraday_v1"}
    prior_close = successor_history.daily[-1].close if successor_history.daily else None
    for signal, opening_relvol, pm_relvol in _new_successor_minute_signals(
        bars,
        session_date=session_date,
        history=successor_history,
        current_epoch=current_epoch,
    ):
        route = new_routes.get(signal.policy_id)
        if route is None:
            raise SuccessorDevelopmentOutcomeError(
                f"successor minute signal is outside frozen routes: {signal.policy_id}"
            )
        stop = _stop_for_successor_signal(
            signal, bars, prior_regular_close=prior_close
        )
        if stop is None:
            raise SuccessorDevelopmentOutcomeError(
                f"fired successor signal has no frozen structural stop: {signal.policy_id}"
            )
        outcome = simulate_successor_intraday_outcome(
            signal,
            bars,
            economic_family_id=route.economic_family_id,
            symbol=symbol,
            session_date=session_date,
            stop_price=stop,
        )
        records.append(
            {
                "engine_contract": SUCCESSOR_STANDALONE_ENGINE_CONTRACT,
                "route": route.as_dict(),
                "signal": asdict(signal),
                "context": successor_minute_common_context(
                    signal,
                    bars,
                    history=successor_history,
                    current_epoch=current_epoch,
                    opening_same_time_relvol=opening_relvol,
                    premarket_relvol=pm_relvol,
                ),
                "outcome": asdict(outcome),
            }
        )

    pm_volume = _premarket_volume(bars, session_date)
    if pm_volume is not None:
        retained_history.append_premarket(session_date, pm_volume)
    from packages.backtesting.b35_development_context import summarize_regular_session

    summary = summarize_regular_session(
        bars, session_date=session_date, split_factor=current_epoch
    )
    if summary is not None:
        retained_history.append_daily(summary)
    successor_history.append_session(
        bars, session_date=session_date, split_epoch=current_epoch
    )
    records.sort(
        key=lambda item: (
            str(item["route"]["policy_id"]),
            str(item["signal"].get("signal_available_at_utc") or item["signal"].get("session_date") or ""),
        )
    )
    return records
