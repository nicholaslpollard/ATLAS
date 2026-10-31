from __future__ import annotations

"""V84: offline, source-linked historical 0DTE option quote-reference economics.

Independent family/exit-policy/latency what-if scenarios ONLY. A displayed
bid/ask and size are not proof of either a market order fill or a limit fill.
Never query a provider or broker; the caller supplies SHA-verified cached rows.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import _quote, _read_timestamp

ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v84-offline-three-family-option-quote-shadow-v1"
POLICIES = {
    "control_50_100": {"stop": "-50", "target": "100", "arm": "20", "trail": "15", "hold_minutes": 180},
    "balanced_35_100": {"stop": "-35", "target": "100", "arm": "20", "trail": "15", "hold_minutes": 120},
    "runner_35_150": {"stop": "-35", "target": "150", "arm": "30", "trail": "20", "hold_minutes": 180},
}
LAGS = (1, 3)
FEE_PER_CONTRACT_SIDE = Decimal(".65")
MAX_ENTRY_PREMIUM_USD = Decimal("500")
MAX_QTY = 4
MAX_ENTRY_DISCOVERY_DELAY_SECONDS = 10
MAX_ENTRY_ACTION_EXTRA_SECONDS = 3
MAX_BAD_QUOTE_SECONDS = 30
MAX_OBSERVATION_GAP_SECONDS = 60
MAX_REVIEW_EVENTS = 900


class V84Error(ValueError):
    pass


def signed(doc):
    return {**doc, "fingerprint": _fingerprint(doc)}


def verified(doc):
    return isinstance(doc, dict) and doc.get("fingerprint") == _fingerprint({
        k: v for k, v in doc.items() if k != "fingerprint"
    })


def usd(value):
    return Decimal(str(value)).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def prepare_original_tape(source, selected_contract, session):
    """Validate clocks and each original quote ONCE for all six variants.

    Only timestamp ordering is examined before the causal event replay.
    Invalid quotes are retained with their rejection reason; neither invalid
    nor future quotes are silently promoted to entry or execution evidence.
    """
    if source.get("status") != "CACHE_HIT" or not source.get("source_sha256"):
        raise V84Error("V84_NOT_VERIFIED_CACHED_ORIGINAL_SOURCE")
    rows = source.get("source_rows")
    if not isinstance(rows, (list, tuple)) or not rows:
        raise V84Error("V84_ORIGINAL_TAPE_EMPTY")
    day = date.fromisoformat(session)
    prepared = []
    last = None
    for idx, row in enumerate(rows):
        try:
            at = _read_timestamp(row, day)
        except Exception as exc:
            raise V84Error("V84_OPTION_SOURCE_CLOCK_INVALID") from exc
        if at.date() != day or (last is not None and at <= last):
            raise V84Error("V84_OPTION_SOURCE_CLOCK_OUT_OF_ORDER_OR_DUPLICATE")
        last = at
        try:
            q = _quote(row, day=day, contract=selected_contract)
            error = None
        except (ValueError, TypeError, KeyError) as exc:
            q = None
            error = str(exc)[:120]
        prepared.append((at, q, error, idx))
    return prepared


def replay(decision, demand, source, prepared, *, policy, lag_seconds, market_close_et):
    if policy not in POLICIES or lag_seconds not in LAGS:
        raise V84Error("V84_UNREGISTERED_VARIANT")
    if not verified(decision) or not verified(demand):
        raise V84Error("V84_DECISION_OR_REQUEST_SIGNATURE_INVALID")
    if demand.get("strategy_decision_sha") != decision["fingerprint"]:
        raise V84Error("V84_SOURCE_DOES_NOT_BELONG_TO_DECISION")
    if source.get("query_id") != demand["query_id"] or source.get("source_sha256") is None:
        raise V84Error("V84_EXACT_SOURCE_MISMATCH")
    if source.get("exact_requirement") != {"provider": "thetadata", "method": demand["method"], "kwargs": demand["kwargs"]}:
        raise V84Error("V84_EXACT_OPTION_SOURCE_SCOPE_MISMATCH")
    day = date.fromisoformat(decision["session"])
    if (not isinstance(market_close_et, datetime) or market_close_et.utcoffset() is None
            or market_close_et.astimezone(ET).date() != day):
        raise V84Error("V84_UNVERIFIED_EXCHANGE_CLOSE")
    close = market_close_et.astimezone(ET)
    # Freeze exchange-aware research clocks; NOT guaranteed broker cutoffs.
    if close.hour < 16:
        planned = close - timedelta(minutes=60)
        hard = close - timedelta(minutes=55)
    else:
        planned = close.replace(hour=15, minute=0, second=0)
        hard = close.replace(hour=15, minute=5, second=0)
    if hard.strftime("%H:%M:%S") + ".000" > demand["kwargs"]["end_time_et"]:
        raise V84Error("V84_HARD_EXIT_OUTSIDE_ARCHIVED_SOURCE")
    cutoff = datetime.fromisoformat(decision["decision_at_et"])
    if cutoff.tzinfo is None or cutoff.astimezone(ET).date() != day:
        raise V84Error("V84_DECISION_TIME_INVALID")
    contract = {k: demand["kwargs"][k] for k in ("symbol", "date_et", "expiration", "strike", "right")}
    if contract["date_et"] != day.isoformat() or contract["expiration"] != day.isoformat():
        raise V84Error("V84_NON_0DTE_CONTRACT")
    if contract["right"] != decision["direction"].lower():
        raise V84Error("V84_OPTION_DIRECTION_DRIFT")

    events = []
    counts = {"observations_reviewed": 0, "invalid_quotes": 0,
              "insufficient_bid_size": 0, "review_events_suppressed": 0}
    def note(event, **fields):
        if len(events) < MAX_REVIEW_EVENTS or event != "QUOTE_HOLD_REVIEW":
            events.append({"event": event, **fields})
        else:
            counts["review_events_suppressed"] += 1

    params = POLICIES[policy]
    entry_ask = None
    entry_at = None
    trigger = None
    qty = 0
    paid = None
    exit_data = None
    reference = None
    reference_at = None
    first_good = None
    last_good = None
    bad_start = None
    high = Decimal("0")
    trail = None

    def finish(status, reason):
        pnl = exit_data["reference_pnl"] if exit_data is not None else None
        return signed({
            "contract": CONTRACT,
            "session": day.isoformat(), "strategy": decision["strategy_id"],
            "policy": policy, "lag_seconds": lag_seconds, "status": status,
            "reason": reason, "decision_sha": decision["fingerprint"],
            "demand_sha": demand["fingerprint"], "source_query_id": demand["query_id"],
            "source_sha256": source["source_sha256"],
            "selected_contract": contract, "market_close_et": close.isoformat(),
            "planned_exit_at_et": planned.isoformat(), "hard_exit_at_et": hard.isoformat(),
            "decision_at_et": cutoff.isoformat(),
            "discovery_at_et": reference_at.isoformat() if reference_at else None,
            "discovery_ask": str(reference) if reference is not None else None,
            "entry_action_at_et": entry_at.isoformat() if entry_at else None,
            "entry_action_ask": str(entry_ask) if entry_ask is not None else None,
            "entry_qty": qty, "entry_debit_usd": str(paid) if paid is not None else None,
            "exit": exit_data,
            "quote_reference_pnl_usd": str(pnl) if pnl is not None else None,
            "quote_reference_pnl_2pct_exit_haircut_usd": (
                exit_data["pnl_with_2pct_exit_bid_haircut"] if exit_data else None),
            "counts": counts, "events": events,
            "observed_ask_bid_not_broker_fills": True,
            "market_order_execution_not_proven": True,
            "original_limit_fill_not_guaranteed": True,
            "historical_listing_independently_verified": False,
            "portfolio_cash_or_position_conflicts_not_simulated": True,
            "actual_broker_fills": 0, "provider_requests": 0,
            "in_sample_development_only": True,
        })

    # 1. First available original quote after the completed-bar decision clock.
    ref_index = None
    for i, (at, q, err, idx) in enumerate(prepared):
        if at < cutoff:
            continue
        if at > cutoff + timedelta(seconds=MAX_ENTRY_DISCOVERY_DELAY_SECONDS):
            break
        counts["observations_reviewed"] += 1
        if q is None:
            counts["invalid_quotes"] += 1
            note("ENTRY_DISCOVERY_QUOTE_REJECTED", at=at.isoformat(), reason=err)
            continue
        reference = Decimal(q["ask"])
        reference_at = at
        ref_index = i
        note("ENTRY_DISCOVERY", at=at.isoformat(), ask=q["ask"],
             bid=q["bid"], spread=str(Decimal(q["ask"])-Decimal(q["bid"])),
             ask_size=q["ask_size"], original_row=idx)
        break
    if ref_index is None:
        return finish("NO_ENTRY", "NO_QUALIFIED_QUOTE_WITHIN_10_SECONDS")

    # 2. Action requires fresh quote after registered 1s/3s latency, at
    # most 3 extra seconds; reject adverse ask drift instead of waiting for
    # hindsight improvement in the offered price.
    action_start = reference_at + timedelta(seconds=lag_seconds)
    action_index = None
    for i in range(ref_index + 1, len(prepared)):
        at, q, err, idx = prepared[i]
        if at < action_start:
            continue
        if at > action_start + timedelta(seconds=MAX_ENTRY_ACTION_EXTRA_SECONDS):
            break
        counts["observations_reviewed"] += 1
        if q is None:
            counts["invalid_quotes"] += 1
            note("ENTRY_ACTION_QUOTE_REJECTED", at=at.isoformat(), reason=err)
            continue
        action_index = i
        action_ask = Decimal(q["ask"])
        adverse_pct = (action_ask / reference - 1) * 100
        note("ENTRY_ACTION_PRICE_CHECK", at=at.isoformat(), ask=q["ask"],
             bid=q["bid"], ask_size=q["ask_size"],
             ask_drift_pct=str(adverse_pct), original_row=idx)
        if adverse_pct > Decimal("1"):
            return finish("NO_ENTRY", "ENTRY_ASK_ADVERSE_DRIFT_GT_1PCT")
        affordable = int((MAX_ENTRY_PREMIUM_USD /
                          (action_ask*100 + FEE_PER_CONTRACT_SIDE)).to_integral_value(
                              rounding=ROUND_DOWN))
        qty = min(MAX_QTY, affordable, q["ask_size"])
        if qty < 1:
            return finish("NO_ENTRY", "ENTRY_PREMIUM_BUDGET_OR_DISPLAYED_SIZE")
        entry_at = at
        entry_ask = action_ask
        paid = usd(qty * (action_ask*100 + FEE_PER_CONTRACT_SIDE))
        note("MODELED_BUY_TO_OPEN_ASK_REFERENCE", at=at.isoformat(), qty=qty,
             debit_usd=str(paid), guaranteed_fill=False)
        last_good = at
        break
    if entry_at is None:
        return finish("NO_ENTRY", "NO_FRESH_ACTION_QUOTE_WITHIN_LATENCY_WINDOW")

    stop = entry_ask * (1 + Decimal(params["stop"])/100)
    target = entry_ask * (1 + Decimal(params["target"])/100)
    arm = entry_ask * (1 + Decimal(params["arm"])/100)
    max_hold = entry_at + timedelta(minutes=params["hold_minutes"])

    for at, q, err, idx in prepared[action_index + 1:]:
        if at > hard:
            break
        counts["observations_reviewed"] += 1
        if last_good is not None and (at-last_good).total_seconds() > MAX_OBSERVATION_GAP_SECONDS:
            note("SOURCE_GAP", at=at.isoformat(), last_at=last_good.isoformat())
            return finish("UNRESOLVED_POSITION", "OPTION_QUOTE_PATH_GAP_GT_60_SECONDS")
        if q is None:
            counts["invalid_quotes"] += 1
            if bad_start is None:
                bad_start = at
            note("QUOTE_REJECTED", at=at.isoformat(), reason=err, original_row=idx)
            if (at-bad_start).total_seconds() > MAX_BAD_QUOTE_SECONDS:
                return finish("UNRESOLVED_POSITION", "INVALID_OPTION_QUOTE_BLACKOUT_GT_30_SECONDS")
            continue
        bad_start = None
        last_good = at
        bid = Decimal(q["bid"])
        high = max(high, bid)
        if high >= arm:
            trail = max(trail or Decimal("0"), high*(1-Decimal(params["trail"])/100))
        if trigger is None:
            reason = ("PROFIT_TARGET" if bid >= target else
                      "STOP_LOSS" if bid <= stop else
                      "CAUSAL_TRAIL" if trail is not None and bid <= trail else
                      "MAX_HOLD" if at >= max_hold else
                      "PLANNED_PRE_EXPIRY_EXIT" if at >= planned else None)
            if reason is not None:
                trigger = {"reason": reason, "trigger_at_et": at.isoformat(),
                           "trigger_bid": str(bid), "action_earliest": at+timedelta(seconds=lag_seconds)}
                note("SELL_TO_CLOSE_EXIT_INTENT", at=at.isoformat(), reason=reason,
                     bid=str(bid), original_row=idx, original_limit_marketability_unproven=True)
        if trigger is not None and at >= trigger["action_earliest"]:
            if q["bid_size"] < qty:
                counts["insufficient_bid_size"] += 1
                note("INSUFFICIENT_DISPLAYED_EXIT_SIZE", at=at.isoformat(),
                     bid_size=q["bid_size"], qty=qty)
                continue
            if (at-trigger["action_earliest"]).total_seconds() > MAX_OBSERVATION_GAP_SECONDS:
                return finish("UNRESOLVED_POSITION", "EXIT_ACTION_QUOTE_TOO_LATE")
            fixed_limit_marketable = bid >= Decimal(trigger["trigger_bid"])
            credit = usd(qty * (bid*100 - FEE_PER_CONTRACT_SIDE))
            haircut_bid = bid * Decimal(".98")
            conservative_credit = usd(qty * (haircut_bid*100 - FEE_PER_CONTRACT_SIDE))
            exit_data = {
                "reason": trigger["reason"], "trigger_at_et": trigger["trigger_at_et"],
                "trigger_bid": trigger["trigger_bid"],
                "action_at_et": at.isoformat(), "action_bid": str(bid),
                "bid_size": q["bid_size"],
                "original_trigger_limit_marketable_at_action": fixed_limit_marketable,
                "requires_new_lower_limit_if_false": not fixed_limit_marketable,
                "quote_reference_credit_usd": str(credit),
                "reference_pnl": usd(credit-paid),
                "pnl_with_2pct_exit_bid_haircut": str(usd(conservative_credit-paid)),
                "adverse_bid_change_from_trigger_pct": str(
                    (bid/Decimal(trigger["trigger_bid"])-1)*100),
                "broker_fill_guaranteed": False,
            }
            # Convert Decimal for deterministic signed JSON serialization.
            exit_data["reference_pnl"] = str(exit_data["reference_pnl"])
            note("MODELED_SELL_TO_CLOSE_BID_REFERENCE", at=at.isoformat(),
                 observed_bid=str(bid), qty=qty,
                 trigger_limit_marketable=fixed_limit_marketable,
                 repricing_required=not fixed_limit_marketable, actual_fill=False)
            return finish("CLOSED_QUOTE_REFERENCE", trigger["reason"])
        if idx % 60 == 0:
            note("QUOTE_HOLD_REVIEW", at=at.isoformat(), bid=str(bid),
                 ask=q["ask"], bid_size=q["bid_size"], high_bid=str(high),
                 trail_floor=str(trail) if trail is not None else None)
    note("UNRESOLVED_AT_HARD_EXIT", hard_at_et=hard.isoformat(),
         pending_trigger=trigger["reason"] if trigger else None)
    return finish("UNRESOLVED_POSITION", "NO_QUALIFIED_SELL_TO_CLOSE_ACTION_BEFORE_HARD_CUTOFF")
