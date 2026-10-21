from __future__ import annotations

"""Descriptive 20-session same-clock premarket volume context (NOT a signal).

Uses the already accepted B34 left-edge+1m canonical stock bars. Missing
historical premarket observations never become synthetic zero volume.
Raw volume comparisons remain non-admissible for signals until split/PIT
corporate-action comparability is independently established.
"""

from datetime import date, time
import math
from statistics import median
from typing import Iterable, Mapping, Sequence

from packages.data.b34_premarket_decision_context_v1 import (
    ALLOWED_DECISIONS_ET, B34_LAST_SAFE_SESSION, PremarketContextError,
    build_context, build_three_cutoffs,
)
from packages.schemas.market import CanonicalBar

CONTRACT = "atlas-b34-premarket-prior20-volume-observation-v1-no-signal"
PRIOR_SESSIONS = 20


def review_prior20(
    *,
    symbol: str,
    current_session: date,
    current_bars: Iterable[CanonicalBar],
    prior_sessions: Sequence[date],
    prior_bars_by_session: Mapping[date, Iterable[CanonicalBar]],
) -> dict[str, object]:
    """Compare like-for-like premarket volumes at three causally safe clocks.

    The calling source review must verify each canonical unit fingerprint.
    This pure function explicitly DOES NOT certify split-free comparisons.
    """
    if (current_session > B34_LAST_SAFE_SESSION or not symbol
            or current_session.month != 4 or current_session.year != 2026):
        # Initial operator review is restricted to the accepted April ZSL unit.
        raise PremarketContextError("PRIOR20_SCOPE_NOT_APPROVED")
    if (len(prior_sessions) != PRIOR_SESSIONS
            or len(set(prior_sessions)) != PRIOR_SESSIONS
            or list(prior_sessions) != sorted(prior_sessions)
            or any(d >= current_session or d.month != current_session.month
                   or d.year != current_session.year for d in prior_sessions)
            or set(prior_bars_by_session) != set(prior_sessions)):
        raise PremarketContextError("PRIOR20_SESSION_CALENDAR_MISMATCH")

    current = build_three_cutoffs(
        current_bars, symbol=symbol, session_date=current_session
    )
    historic = {}
    for day in prior_sessions:
        observations = build_three_cutoffs(
            tuple(prior_bars_by_session[day]), symbol=symbol, session_date=day
        )
        historic[day] = observations

    rows = []
    for clock_idx, clock in enumerate(ALLOWED_DECISIONS_ET):
        today = current[clock_idx]
        today_volume = today["features"]["premarket_cumulative_volume"]
        past = [(day, int(historic[day][clock_idx]["features"][
            "premarket_observed_minutes"]), float(historic[day][clock_idx][
                "features"]["premarket_cumulative_volume"]))
            for day in prior_sessions]
        # Zero observed bars is absent evidence, never imputed zero volume.
        missing = [day.isoformat() for day, count, _ in past if not count]
        eligible = [value for _, count, value in past if count]
        reference = float(median(eligible)) if not missing else None
        diagnostic_ratio = (
            float(today_volume) / reference
            if reference is not None and reference > 0
               and today["features"]["premarket_observed_minutes"] > 0
            else None
        )
        if diagnostic_ratio is not None and not math.isfinite(diagnostic_ratio):
            raise PremarketContextError("PRIOR20_RATIO_NONFINITE")
        rows.append({
            "decision_clock_et": clock.isoformat(),
            "current_session": current_session.isoformat(),
            "current_observed_premarket_minutes": today["features"][
                "premarket_observed_minutes"
            ],
            "current_observed_premarket_volume": today_volume,
            "prior_session_count": PRIOR_SESSIONS,
            "prior_sessions_with_observed_premarket": len(eligible),
            "prior_sessions_missing_premarket": missing,
            "prior_20_median_observed_premarket_volume": reference,
            "raw_volume_ratio_diagnostic_only": diagnostic_ratio,
            "volume_ratio_admissible_as_strategy_input": False,
            "reason_not_admissible": (
                "PIT_SPLIT_AND_CORPORATE_ACTION_COMPARABILITY_UNQUALIFIED"
                if not missing else "MISSING_PRIOR_PREMARKET_OBSERVATIONS"
            ),
            "source_context_fingerprint": today["eligible_source_bars_sha256"],
            "prior_context_fingerprints": {
                day.isoformat(): historic[day][clock_idx][
                    "eligible_source_bars_sha256"
                ] for day in prior_sessions
            },
        })

    return {
        "contract": CONTRACT,
        "symbol": symbol,
        "session_date": current_session.isoformat(),
        "prior_session_dates": [day.isoformat() for day in prior_sessions],
        "snapshots": rows,
        "split_or_corporate_action_history_checked": False,
        "protected_outcomes_opened": 0,
        "provider_requests": 0,
        "broker_requests": 0,
        "signal_authority": False,
        "note": (
            "Descriptive, same-clock observed premarket volumes only. Historical "
            "raw volume spans unqualified split boundaries; no signal, backtest "
            "or order admission. No data after each clock enters its features."
        ),
    }
