from __future__ import annotations

"""V40 actual source acquisition for V37 SPY pre-trade candidate decisions.

This is a source discovery/acquisition stage, NOT trade eligibility. It uses
the V39 dynamic, persistent read-through provider cache: previous immutable
source data is reused, missing data is requested and saved automatically.
No fixed request count or provider-call prohibition applies to the runtime.
"""

from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.options_native_spy_pretrade_feature_bridge_v37 import (
    CONTRACT as V37_CONTRACT,
    PINNED_TAPE_FINGERPRINT,
)
from packages.strategies.options_native_pilot_v1_contract import SPECIFICATION_FINGERPRINT

CONTRACT = "atlas-spy-v40-dynamic-pretrade-source-acquisition-v1"
V37_STATUS = "SOURCE_BOUND_HISTORICAL_PRETRADE_FEATURE_GAP_PACKET_NOT_SIGNAL"
USE_CLOCK = "10:01:00.000"
FOCUSED_OI_DTE = 75  # Existing 30..45 selected expiry + prior-session day offset.
SOURCE_LABELS = ("decision_date_prior_state_oi_surface", "call_1001_quote", "put_1001_quote")


class PretradeSourceDemandError(ValueError):
    pass


def validate_v37_source_packet(report: Any) -> list[dict[str, Any]]:
    if not isinstance(report, dict):
        raise PretradeSourceDemandError("V37_PACKET_NOT_OBJECT")
    required = {
        "contract": V37_CONTRACT,
        "status": V37_STATUS,
        "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "source_v32_quote_tape_fingerprint": PINNED_TAPE_FINGERPRINT,
        "original_weekly_decision_clocks": 411,
        "source_selected_pairs": 361,
        "original_abstentions": 50,
        "selected_retrospective_window_present": 358,
        "selected_retrospective_window_missing": 3,
        "qualified_real_historical_volatility_signals": 0,
        "historical_publication_clocks_qualified": False,
        "trading_pnl_computed": False,
        "protected_2026_outcomes_read": 0,
    }
    if any(report.get(name) != value for name, value in required.items()):
        raise PretradeSourceDemandError("V37_FROZEN_SOURCE_PACKET_AUTHORITY_DRIFT")
    entries = report.get("entries")
    if (not isinstance(entries, list) or len(entries) != 361
            or not isinstance(report.get("fingerprint"), str)
            or _fingerprint({k: v for k, v in report.items() if k != "fingerprint"})
                != report["fingerprint"]):
        raise PretradeSourceDemandError("V37_PACKET_SHA_OR_ENTRIES_DRIFT")
    days = [x.get("original_entry_date_et") for x in entries if isinstance(x, dict)]
    if len(days) != 361 or len(set(days)) != 361 or days != sorted(days):
        raise PretradeSourceDemandError("V37_UNIQUE_ORDERED_ENTRIES_DRIFT")
    for item in entries:
        if (item.get("historical_source_qualified_1001_order_fill") is not False
                or item.get("forecast_source_historical_pit_qualified") is not False
                or item.get("american_call_iv") is not None
                or item.get("american_put_iv") is not None
                or item.get("frozen_pilot_entry_signal") is not None
                or item.get("implied_pair_variance") is not None):
            raise PretradeSourceDemandError("V37_INPUTS_PROMOTED_TO_UNPROVEN_SIGNAL")
    return entries


def source_demands_for_entries(
    entries: Iterable[dict[str, Any]], *,
    calendar: Any = None,
) -> Iterable[dict[str, Any]]:
    """Stream all entry + previous-session OI needs, no fixed batch size.

    The generator accepts newly discovered candidate rows as well as the
    V37 frozen research cohort. Never use future price/exit information.
    """
    calendar = calendar or get_market_calendar("XNYS")
    seen = set()
    for row in entries:
        if not isinstance(row, dict):
            raise PretradeSourceDemandError("INVALID_DYNAMIC_CANDIDATE_ROW")
        d = row.get("original_entry_date_et")
        expiry = row.get("frozen_expiration_et")
        strike = row.get("frozen_strike")
        if not all(isinstance(x, str) for x in (d, expiry, strike)):
            raise PretradeSourceDemandError("CANDIDATE_CONTRACT_IDENTITY_MISSING")
        try:
            when, expiration, strike_value = (
                date.fromisoformat(d), date.fromisoformat(expiry), Decimal(strike),
            )
        except (ValueError, InvalidOperation) as exc:
            raise PretradeSourceDemandError("CANDIDATE_IDENTITY_INVALID") from exc
        if (d != when.isoformat() or expiry != expiration.isoformat()
                or not strike_value.is_finite() or strike_value <= 0
                or expiration <= when or d in seen
                or not calendar.is_session(when)):
            raise PretradeSourceDemandError("CANDIDATE_EXPIRY_OR_SESSION_INVALID")
        seen.add(d)
        prior = calendar.sessions_in_range(when - timedelta(days=10), when - timedelta(days=1))
        if not prior:
            raise PretradeSourceDemandError("PREVIOUS_XNYS_SESSION_NOT_FOUND")
        # ThetaData describes the approx. 06:30 ET *decision-date* OPRA
        # message as the OI state at the END OF THE PREVIOUS trading session.
        # Request decision-date publication, NOT previous-date publication,
        # which would normally lag an additional trading session. The prior
        # XNYS session is checked above; actual message source timestamp and
        # historical availability still require downstream qualification.
        prefix = f"SPY.{when.isoformat()}.{expiry}.{strike}"
        yield {
            "candidate_id": prefix,
            "purpose": "decision_date_prior_state_oi_surface",
            "method": "option_history_open_interest_surface",
            "kwargs": {
                "symbol": "SPY",
                "date_et": d,
                "right": "both",
                "max_dte": FOCUSED_OI_DTE,
                "strike_range": None,
            },
        }
        for right in ("call", "put"):
            yield {
                "candidate_id": prefix,
                "purpose": f"{right}_1001_quote",
                "method": "option_at_time_quote",
                "kwargs": {
                    "symbol": "SPY",
                    "expiration": expiry,
                    "strike": strike,
                    "right": right,
                    "date_et": d,
                    "time_of_day_et": USE_CLOCK,
                },
            }


def source_evidence_summary(
    report: dict[str, Any],
    acquired: dict[str, Any],
    observations: Counter,
) -> dict[str, Any]:
    """Do NOT elevate source rows to executable quotes, OI publication or IV."""
    out = {
        "contract": CONTRACT,
        "status": "COLLECTED_SOURCE_ONLY_PRETRADE_PIT_NOT_QUALIFIED",
        "source_v37_fingerprint": report["fingerprint"],
        "original_decision_clocks": report["original_weekly_decision_clocks"],
        "original_candidate_pairs": report["source_selected_pairs"],
        "original_weekly_abstentions": report["original_abstentions"],
        "available_retrospective_volatility_windows":
            report["selected_retrospective_window_present"],
        "missing_retrospective_volatility_windows":
            report["selected_retrospective_window_missing"],
        "source_demand_status": acquired["status"],
        "source_demand_counts": {
            k: v for k, v in acquired.items()
            if k in {
                "source_uses_requested", "source_uses_resolved",
                "source_uses_explicit_no_data", "source_uses_failed_or_unresolved",
                "provider_dispatch_attempts", "provider_fetch_successes",
                "persisted_cache_hits",
            }
        },
        "source_evidence_counts": dict(sorted(observations.items())),
        "source_archive_sqlite": acquired["exact_query_store"],
        "original_1000_quotes_not_replaced_by_1001_fills": True,
        "open_interest_publication_qualified": False,
        "call_put_iv_model_qualified": False,
        "retrospective_volatility_source_pit_qualified": False,
        "historical_option_fill_evidence": None,
        "actual_strategy_entries": None,
        "actual_historical_profitability": None,
        "next": "TIME_QUALIFY_AND_COMPUTE_101STEP_IV_RATE_DIVIDEND_THEN_PILOT_SIGNAL",
    }
    out["fingerprint"] = _fingerprint(out)
    return out


def count_source_observation(item: dict, source: dict, counter: Counter) -> None:
    counter["source_uses_seen"] += 1
    purpose = item["purpose"]
    if source["status"] in ("FETCHED_EXPLICIT_NO_DATA", "CACHED_EXPLICIT_NO_DATA"):
        counter["explicit_no_data_" + purpose] += 1
        return
    counter["archived_rows_" + purpose] += len(source["source_rows"])
    counter["archive_present_" + purpose] += 1
    # Do not assume the provider honored requested expiration, right or
    # strike filters; source rows may contain unrelated contracts.
    if purpose in ("call_1001_quote", "put_1001_quote"):
        expected = item["kwargs"]
        found = 0
        for r in source["source_rows"]:
            try:
                equal = (
                    str(r["symbol"]).upper() in ("SPY", "SPY.US")
                    and str(r["expiration"])[:10] == expected["expiration"]
                    and Decimal(str(r["strike"])) == Decimal(expected["strike"])
                    and str(r["right"]).lower() == expected["right"]
                )
            except (KeyError, ValueError, InvalidOperation):
                equal = False
            if equal:
                found += 1
        if found == 1:
            counter["exact_contract_present_" + purpose] += 1
        else:
            counter["exact_contract_not_unique_" + purpose] += 1
