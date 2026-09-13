from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _write(path: str, text: str) -> None:
    (ROOT / path).write_text(text, encoding="utf-8")


def _replace_once(text: str, old: str, new: str, *, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def _replace_function(text: str, name: str, next_name: str, replacement: str) -> str:
    start_token = f"def {name}("
    next_token = f"\ndef {next_name}("
    start = text.find(start_token)
    if start < 0:
        raise RuntimeError(f"missing function {name}")
    end = text.find(next_token, start)
    if end < 0:
        raise RuntimeError(f"missing next function {next_name} after {name}")
    return text[:start] + replacement.rstrip() + "\n\n" + text[end + 1 :]


# 1. Daily pivot breakout must cross the same already-known pivot on both sides
#    of the signal transition. Also bump the feature contract so the scientific
#    identity changes with this semantic correction.
feature_path = "packages/features/successor_practitioner.py"
feature = _read(feature_path)
feature = _replace_once(
    feature,
    '    "successor-practitioner-features-v1-pit-confirmed-patterns-shared-compute"\n',
    '    "successor-practitioner-features-v2-pit-confirmed-patterns-exact-pivot-cross-shared-compute"\n',
    label="feature contract bump",
)
feature = _replace_once(
    feature,
    '                "confirmed_pivot": "radius-2 center becomes usable only after both right-side bars have closed",\n',
    '                "confirmed_pivot": "radius-2 center becomes usable only after both right-side bars have closed",\n'
    '                "pivot_breakout_cross": "prior and current close are evaluated against the same previously-known confirmed pivot level",\n',
    label="feature fingerprint pivot semantics",
)
old_pivot = '''    known_high = result["confirmed_pivot_high"].shift(1)
    known_low = result["confirmed_pivot_low"].shift(1)
    prior_known_high = result["confirmed_pivot_high"].shift(2)
    prior_known_low = result["confirmed_pivot_low"].shift(2)
    pivot_valid = group["relative_volume_20"].notna()
    result["pivot_sr_breakout_long"] = _binary(
        known_high.notna()
        & prior_known_high.notna()
        & (previous_close <= prior_known_high)
        & (close > known_high)
        & (group["relative_volume_20"] >= PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN),
        pivot_valid & known_high.notna() & previous_close.notna(),
    )
    result["pivot_sr_breakout_short"] = _binary(
        known_low.notna()
        & prior_known_low.notna()
        & (previous_close >= prior_known_low)
        & (close < known_low)
        & (group["relative_volume_20"] >= PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN),
        pivot_valid & known_low.notna() & previous_close.notna(),
    )
'''
new_pivot = '''    # The level itself must have been known before the signal session. Compare
    # both sides of the crossover with that exact same frozen level; never mix
    # the previously-known level with an older pivot snapshot.
    known_high = result["confirmed_pivot_high"].shift(1)
    known_low = result["confirmed_pivot_low"].shift(1)
    pivot_valid = group["relative_volume_20"].notna()
    result["pivot_sr_breakout_long"] = _binary(
        known_high.notna()
        & (previous_close <= known_high)
        & (close > known_high)
        & (group["relative_volume_20"] >= PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN),
        pivot_valid & known_high.notna() & previous_close.notna(),
    )
    result["pivot_sr_breakout_short"] = _binary(
        known_low.notna()
        & (previous_close >= known_low)
        & (close < known_low)
        & (group["relative_volume_20"] >= PIVOT_BREAKOUT_RELATIVE_VOLUME_MIN),
        pivot_valid & known_low.notna() & previous_close.notna(),
    )
'''
feature = _replace_once(feature, old_pivot, new_pivot, label="pivot crossover implementation")
_write(feature_path, feature)


# 2. Intraday quality values that belong to an earlier clock are derived from
#    the closed bars at that clock. Breakout relative volume is keyed to the
#    exact breakout bar instead of being a free scalar that could come from a
#    later decision time.
intraday_path = "packages/strategies/successor_intraday_rules.py"
intraday = _read(intraday_path)
intraday = _replace_once(
    intraday,
    '    "successor-intraday-rules-v1-closed-bar-pit-objective-quality-and-retest"\n',
    '    "successor-intraday-rules-v2-frozen-quality-clocks-keyed-breakout-relvol"\n',
    label="intraday contract bump",
)
intraday = _replace_once(
    intraday,
    '            "gap_quality": {"gap_min": 0.02, "price_min": 5.0, "prior_median_dollar_volume_20_min": 20_000_000.0, "natr_14_min": 0.01, "natr_14_max": 0.08, "premarket_relvol_20_min": 1.5},\n',
    '            "gap_quality": {"gap_min": 0.02, "price_min": 5.0, "price_clock": "09:30 bar close available 09:31", "prior_median_dollar_volume_20_min": 20_000_000.0, "natr_14_min": 0.01, "natr_14_max": 0.08, "premarket_relvol_20_min": 1.5},\n',
    label="gap fingerprint clock",
)
intraday = _replace_once(
    intraday,
    '            "orb_5m": {"required_bars": 5, "same_time_relvol_min": 2.0, "prior_median_dollar_volume_20_min": 20_000_000.0, "price_min": 5.0, "cutoff": "11:30"},\n',
    '            "orb_5m": {"required_bars": 5, "same_time_relvol_min": 2.0, "prior_median_dollar_volume_20_min": 20_000_000.0, "price_min": 5.0, "price_clock": "09:34 close frozen when range becomes available 09:35", "cutoff": "11:30"},\n',
    label="orb fingerprint clock",
)
intraday = _replace_once(
    intraday,
    '            "premarket_quality": {"premarket_relvol_min": 2.0, "consolidation_max_fraction": 0.03, "consolidation_min_bars": 5, "prior_median_dollar_volume_20_min": 20_000_000.0, "price_min": 5.0, "premarket_dollar_volume_min": 2_000_000.0, "breakout_same_time_relvol_min": 1.5, "cutoff": "11:30"},\n',
    '            "premarket_quality": {"premarket_relvol_min": 2.0, "consolidation_max_fraction": 0.03, "consolidation_min_bars": 5, "prior_median_dollar_volume_20_min": 20_000_000.0, "price_min": 5.0, "price_clock": "last observed 09:00..09:29 consolidation close", "premarket_dollar_volume_min": 2_000_000.0, "breakout_same_time_relvol_min": 1.5, "breakout_relvol_binding": "exact first closed breakout timestamp", "cutoff": "11:30"},\n',
    label="premarket fingerprint clocks",
)

gap_function = r'''def evaluate_gap_quality_condition_long(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    prior_regular_close: float,
    prior_median_dollar_volume_20: float,
    natr_14: float,
    premarket_relvol_20: float,
    split_crossed: bool,
) -> SuccessorIntradaySignal:
    decision = _aware_utc(decision_time_utc).astimezone(MARKET_TZ)
    earliest = datetime.combine(session_date, time(9, 31), tzinfo=MARKET_TZ)
    if decision < earliest:
        return _signal(
            policy_id="gap_quality_condition_long_v2",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("INFORMATION_CLOCK_NOT_READY",),
            evidence={"earliest_decision_et": earliest.isoformat()},
        )
    if split_crossed:
        return _signal(
            policy_id="gap_quality_condition_long_v2",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("SPLIT_CROSSES_PRICE_COMPARISON",),
            evidence={},
        )
    closed = _closed_session_bars(
        bars,
        session_date=session_date,
        decision_time_utc=decision_time_utc,
        segment=SessionSegment.REGULAR,
    )
    first_regular = [bar for bar in closed if _local_time(bar) == time(9, 30)]
    if not first_regular:
        return _signal(
            policy_id="gap_quality_condition_long_v2",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("FIRST_REGULAR_BAR_NOT_CLOSED",),
            evidence={},
        )
    opening_bar = first_regular[0]
    current_regular_open = float(opening_bar.open)
    quality_price = float(opening_bar.close)
    values = (
        prior_regular_close,
        current_regular_open,
        quality_price,
        prior_median_dollar_volume_20,
        natr_14,
        premarket_relvol_20,
    )
    if not all(math.isfinite(value) for value in values):
        raise ValueError("gap quality inputs must be finite")
    if prior_regular_close <= 0.0 or current_regular_open <= 0.0 or quality_price <= 0.0:
        raise ValueError("gap quality prices must be positive")
    gap = current_regular_open / prior_regular_close - 1.0
    checks = {
        "gap_ge_2pct": gap >= 0.02,
        "price_ge_5": quality_price >= 5.0,
        "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20 >= 20_000_000.0,
        "natr_14_ge_1pct": natr_14 >= 0.01,
        "natr_14_le_8pct": natr_14 <= 0.08,
        "premarket_relvol_20_ge_1_5": premarket_relvol_20 >= 1.5,
    }
    fired = all(checks.values())
    return _signal(
        policy_id="gap_quality_condition_long_v2",
        session_date=session_date,
        ready=True,
        fired=fired,
        direction="LONG" if fired else None,
        signal_bar=opening_bar,
        reasons=(("QUALITY_GATE_PASS",) if fired else ("QUALITY_GATE_FAIL",)),
        evidence={
            "gap_fraction": gap,
            "quality_price_0930_close": quality_price,
            "checks": checks,
        },
    )'''
intraday = _replace_function(
    intraday,
    "evaluate_gap_quality_condition_long",
    "evaluate_orb_stocks_in_play_5m",
    gap_function,
)

orb_function = r'''def evaluate_orb_stocks_in_play_5m(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    same_time_opening_relvol: float,
    prior_median_dollar_volume_20: float,
) -> SuccessorIntradaySignal:
    if not all(
        math.isfinite(value)
        for value in (same_time_opening_relvol, prior_median_dollar_volume_20)
    ):
        raise ValueError("ORB stocks-in-play scalar inputs must be finite")
    closed = _closed_session_bars(
        bars,
        session_date=session_date,
        decision_time_utc=decision_time_utc,
        segment=SessionSegment.REGULAR,
    )
    opening = [bar for bar in closed if time(9, 30) <= _local_time(bar) < time(9, 35)]
    if len(opening) < 5:
        return _signal(
            policy_id="orb_stocks_in_play_5m_v1",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("INCOMPLETE_FIVE_MINUTE_OPENING_RANGE",),
            evidence={"observed_range_bars": len(opening)},
        )
    range_high = max(bar.high for bar in opening)
    range_low = min(bar.low for bar in opening)
    opening_quality_price = float(opening[-1].close)
    quality = {
        "same_time_opening_relvol_ge_2": same_time_opening_relvol >= 2.0,
        "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20 >= 20_000_000.0,
        "price_ge_5": opening_quality_price >= 5.0,
    }
    evidence = {
        "checks": quality,
        "range_high": range_high,
        "range_low": range_low,
        "opening_quality_price_0934_close": opening_quality_price,
    }
    if not all(quality.values()):
        return _signal(
            policy_id="orb_stocks_in_play_5m_v1",
            session_date=session_date,
            ready=True,
            fired=False,
            direction=None,
            signal_bar=opening[-1],
            reasons=("STOCKS_IN_PLAY_GATE_FAIL",),
            evidence=evidence,
        )
    breakout_bars = _regular_through(
        closed, start=time(9, 35), cutoff=ORB_ENTRY_CUTOFF
    )
    for bar in breakout_bars:
        if bar.close > range_high:
            return _signal(
                policy_id="orb_stocks_in_play_5m_v1",
                session_date=session_date,
                ready=True,
                fired=True,
                direction="LONG",
                signal_bar=bar,
                reasons=("FIVE_MINUTE_ORB_BREAKOUT", "STOCKS_IN_PLAY_GATE_PASS"),
                evidence=evidence,
            )
        if bar.close < range_low:
            return _signal(
                policy_id="orb_stocks_in_play_5m_v1",
                session_date=session_date,
                ready=True,
                fired=True,
                direction="SHORT",
                signal_bar=bar,
                reasons=("FIVE_MINUTE_ORB_BREAKDOWN", "STOCKS_IN_PLAY_GATE_PASS"),
                evidence=evidence,
            )
    return _signal(
        policy_id="orb_stocks_in_play_5m_v1",
        session_date=session_date,
        ready=True,
        fired=False,
        direction=None,
        signal_bar=breakout_bars[-1] if breakout_bars else opening[-1],
        reasons=("NO_FIVE_MINUTE_RANGE_BREAK",),
        evidence=evidence,
    )'''
intraday = _replace_function(
    intraday,
    "evaluate_orb_stocks_in_play_5m",
    "evaluate_orb_15m_close_retest",
    orb_function,
)

premarket_function = r'''def evaluate_premarket_relvol_quality(
    bars: Iterable[CanonicalBar],
    *,
    session_date: date,
    decision_time_utc: datetime,
    prior_premarket_median_volume_20: float,
    prior_median_dollar_volume_20: float,
    breakout_same_time_relvol_by_timestamp: dict[datetime, float],
) -> SuccessorIntradaySignal:
    scalar_values = (prior_premarket_median_volume_20, prior_median_dollar_volume_20)
    if not all(math.isfinite(value) for value in scalar_values):
        raise ValueError("premarket quality scalar inputs must be finite")
    if prior_premarket_median_volume_20 <= 0.0:
        return _signal(
            policy_id="premarket_relvol_quality_v2",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("PRIOR_PREMARKET_MEDIAN_VOLUME_UNAVAILABLE",),
            evidence={},
        )
    closed = _closed_session_bars(
        bars, session_date=session_date, decision_time_utc=decision_time_utc
    )
    premarket = [
        bar
        for bar in closed
        if bar.session_segment == SessionSegment.PREMARKET
        and PREMARKET_START <= _local_time(bar) < PREMARKET_END
    ]
    consolidation = [
        bar
        for bar in premarket
        if PREMARKET_CONSOLIDATION_START
        <= _local_time(bar)
        < PREMARKET_CONSOLIDATION_END
    ]
    if len(consolidation) < 5:
        return _signal(
            policy_id="premarket_relvol_quality_v2",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("INSUFFICIENT_PREMARKET_CONSOLIDATION_BARS",),
            evidence={"consolidation_bars": len(consolidation)},
        )
    pm_volume = sum(bar.volume for bar in premarket)
    pm_dollar_volume = sum(
        ((bar.high + bar.low + bar.close) / 3.0) * bar.volume for bar in premarket
    )
    relvol = pm_volume / prior_premarket_median_volume_20
    consolidation_high = max(bar.high for bar in consolidation)
    consolidation_low = min(bar.low for bar in consolidation)
    quality_price = float(consolidation[-1].close)
    consolidation_range = (
        (consolidation_high - consolidation_low) / quality_price
        if quality_price > 0.0
        else math.inf
    )
    static_quality = {
        "premarket_relvol_ge_2": relvol >= 2.0,
        "consolidation_range_le_3pct": consolidation_range <= 0.03,
        "prior_median_dollar_volume_20_ge_20m": prior_median_dollar_volume_20 >= 20_000_000.0,
        "price_ge_5": quality_price >= 5.0,
        "premarket_dollar_volume_ge_2m": pm_dollar_volume >= 2_000_000.0,
    }
    base_evidence = {
        "premarket_relvol": relvol,
        "premarket_dollar_volume": pm_dollar_volume,
        "consolidation_high": consolidation_high,
        "consolidation_low": consolidation_low,
        "consolidation_range_fraction": consolidation_range,
        "quality_price_last_consolidation_close": quality_price,
        "checks": static_quality,
    }
    if not all(static_quality.values()):
        return _signal(
            policy_id="premarket_relvol_quality_v2",
            session_date=session_date,
            ready=True,
            fired=False,
            direction=None,
            signal_bar=None,
            reasons=("PREMARKET_QUALITY_GATE_FAIL",),
            evidence=base_evidence,
        )
    regular = [
        bar
        for bar in closed
        if bar.session_segment == SessionSegment.REGULAR
        and REGULAR_START <= _local_time(bar) <= ORB_ENTRY_CUTOFF
    ]
    first_breakout = next(
        (bar for bar in regular if bar.close > consolidation_high), None
    )
    if first_breakout is None:
        return _signal(
            policy_id="premarket_relvol_quality_v2",
            session_date=session_date,
            ready=True,
            fired=False,
            direction=None,
            signal_bar=regular[-1] if regular else None,
            reasons=("NO_PREMARKET_QUALITY_BREAKOUT",),
            evidence=base_evidence,
        )
    breakout_relvol = breakout_same_time_relvol_by_timestamp.get(
        first_breakout.timestamp_utc
    )
    if breakout_relvol is None or not math.isfinite(float(breakout_relvol)):
        return _signal(
            policy_id="premarket_relvol_quality_v2",
            session_date=session_date,
            ready=False,
            fired=False,
            direction=None,
            signal_bar=first_breakout,
            reasons=("BREAKOUT_SAME_TIME_RELVOL_UNAVAILABLE",),
            evidence={
                **base_evidence,
                "first_breakout_stamp_utc": first_breakout.timestamp_utc.isoformat(),
            },
        )
    breakout_relvol = float(breakout_relvol)
    breakout_pass = breakout_relvol >= 1.5
    evidence = {
        **base_evidence,
        "first_breakout_stamp_utc": first_breakout.timestamp_utc.isoformat(),
        "first_breakout_same_time_relvol": breakout_relvol,
        "breakout_same_time_relvol_ge_1_5": breakout_pass,
    }
    if not breakout_pass:
        return _signal(
            policy_id="premarket_relvol_quality_v2",
            session_date=session_date,
            ready=True,
            fired=False,
            direction=None,
            signal_bar=first_breakout,
            reasons=("FIRST_BREAKOUT_RELVOL_GATE_FAIL",),
            evidence=evidence,
        )
    return _signal(
        policy_id="premarket_relvol_quality_v2",
        session_date=session_date,
        ready=True,
        fired=True,
        direction="LONG",
        signal_bar=first_breakout,
        reasons=("PREMARKET_QUALITY_PASS", "CONSOLIDATION_BREAKOUT"),
        evidence=evidence,
    )'''
# This is the final function in the module, so replace through the fingerprint constant.
start = intraday.find("def evaluate_premarket_relvol_quality(")
end = intraday.find("\n\nSUCCESSOR_INTRADAY_RULE_FINGERPRINT", start)
if start < 0 or end < 0:
    raise RuntimeError("could not locate premarket evaluator bounds")
intraday = intraday[:start] + premarket_function.rstrip() + intraday[end:]
_write(intraday_path, intraday)


# 3. Update synthetic tests to make the clocks executable, then add explicit
#    regression cases proving later values cannot be back-applied.
test_path = "tests/unit/test_successor_strategy_implementation.py"
tests = _read(test_path)
old_gap_test = '''def test_gap_quality_challenger_is_not_a_neighbor_threshold_search() -> None:
    session = date(2026, 9, 10)
    result = evaluate_gap_quality_condition_long(
        session_date=session, decision_time_utc=_decision(session, 9, 31), prior_regular_close=10.0,
        current_regular_open=10.25, current_price=10.3, prior_median_dollar_volume_20=25_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert result.fired is True
    assert result.direction == "LONG"
    failed = evaluate_gap_quality_condition_long(
        session_date=session, decision_time_utc=_decision(session, 9, 31), prior_regular_close=10.0,
        current_regular_open=10.25, current_price=10.3, prior_median_dollar_volume_20=5_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert failed.fired is False
'''
new_gap_test = '''def test_gap_quality_challenger_is_not_a_neighbor_threshold_search() -> None:
    session = date(2026, 9, 10)
    first_bar = _bar(session, 9, 30, open_=10.25, high=10.4, low=10.2, close=10.3)
    result = evaluate_gap_quality_condition_long(
        [first_bar], session_date=session, decision_time_utc=_decision(session, 9, 31),
        prior_regular_close=10.0, prior_median_dollar_volume_20=25_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert result.fired is True
    assert result.direction == "LONG"
    failed = evaluate_gap_quality_condition_long(
        [first_bar], session_date=session, decision_time_utc=_decision(session, 9, 31),
        prior_regular_close=10.0, prior_median_dollar_volume_20=5_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert failed.fired is False


def test_gap_quality_price_gate_is_frozen_to_first_closed_regular_bar() -> None:
    session = date(2026, 9, 10)
    bars = [
        _bar(session, 9, 30, open_=10.25, high=10.3, low=4.8, close=4.9),
        _bar(session, 9, 31, open_=4.9, high=10.5, low=4.9, close=10.4),
    ]
    result = evaluate_gap_quality_condition_long(
        bars, session_date=session, decision_time_utc=_decision(session, 9, 32),
        prior_regular_close=10.0, prior_median_dollar_volume_20=25_000_000.0,
        natr_14=0.03, premarket_relvol_20=1.8, split_crossed=False,
    )
    assert result.fired is False
    assert result.evidence["quality_price_0930_close"] == 4.9
    assert result.evidence["checks"]["price_ge_5"] is False
'''
tests = _replace_once(tests, old_gap_test, new_gap_test, label="gap tests")
tests = _replace_once(
    tests,
    '        same_time_opening_relvol=2.2, prior_median_dollar_volume_20=30_000_000.0, current_price=10.7,\n',
    '        same_time_opening_relvol=2.2, prior_median_dollar_volume_20=30_000_000.0,\n',
    label="orb call signature",
)
old_premarket_call = '''    result = evaluate_premarket_relvol_quality(
        premarket + regular, session_date=session, decision_time_utc=_decision(session, 9, 31),
        prior_premarket_median_volume_20=200_000.0, prior_median_dollar_volume_20=30_000_000.0,
        current_price=10.2, breakout_same_time_relvol=1.8,
    )
    assert result.fired is True
    assert result.direction == "LONG"
'''
new_premarket_call = '''    result = evaluate_premarket_relvol_quality(
        premarket + regular, session_date=session, decision_time_utc=_decision(session, 9, 31),
        prior_premarket_median_volume_20=200_000.0, prior_median_dollar_volume_20=30_000_000.0,
        breakout_same_time_relvol_by_timestamp={regular[0].timestamp_utc: 1.8},
    )
    assert result.fired is True
    assert result.direction == "LONG"


def test_premarket_quality_binds_relvol_to_first_breakout_bar() -> None:
    session = date(2026, 9, 10)
    premarket = [
        _bar(session, 9, minute, open_=10.0, high=10.10, low=9.95, close=10.02, volume=100_000.0, segment=SessionSegment.PREMARKET)
        for minute in range(5)
    ]
    first = _bar(session, 9, 30, open_=10.02, high=10.25, low=10.0, close=10.20, volume=200_000.0)
    later = _bar(session, 9, 31, open_=10.20, high=10.35, low=10.15, close=10.30, volume=300_000.0)
    result = evaluate_premarket_relvol_quality(
        premarket + [first, later], session_date=session, decision_time_utc=_decision(session, 9, 32),
        prior_premarket_median_volume_20=200_000.0, prior_median_dollar_volume_20=30_000_000.0,
        breakout_same_time_relvol_by_timestamp={first.timestamp_utc: 1.2, later.timestamp_utc: 3.0},
    )
    assert result.fired is False
    assert "FIRST_BREAKOUT_RELVOL_GATE_FAIL" in result.reason_codes
    assert result.evidence["first_breakout_stamp_utc"] == first.timestamp_utc.isoformat()
    assert result.evidence["first_breakout_same_time_relvol"] == 1.2


def test_five_minute_orb_price_gate_uses_frozen_opening_range_close() -> None:
    session = date(2026, 9, 10)
    opening = [
        _bar(session, 9, 30 + minute, open_=4.8, high=4.95, low=4.7, close=4.9)
        for minute in range(5)
    ]
    later_breakout = _bar(session, 9, 35, open_=4.9, high=6.2, low=4.9, close=6.0)
    result = evaluate_orb_stocks_in_play_5m(
        opening + [later_breakout], session_date=session, decision_time_utc=_decision(session, 9, 36),
        same_time_opening_relvol=2.5, prior_median_dollar_volume_20=30_000_000.0,
    )
    assert result.fired is False
    assert result.evidence["opening_quality_price_0934_close"] == 4.9
    assert result.evidence["checks"]["price_ge_5"] is False
'''
tests = _replace_once(tests, old_premarket_call, new_premarket_call, label="premarket tests")
_write(test_path, tests)

print("PR82 pre-outcome semantic repair applied successfully")
