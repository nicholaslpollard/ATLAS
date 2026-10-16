from __future__ import annotations

"""Synthetic two-long-leg coordinator using ATLAS's existing cent cash convention.

Explicit receipts drive fills, final cancellations and sale settlement. Quote
snapshots never trigger those events. No recurrent V1 or single-leg contract is
changed, and no historical/broker execution adapter is supplied here.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
import re
from typing import Any

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.multiyear_offline_account_replay_v1 import _money
from packages.strategies.options_native_pair_v1 import (
    EASTERN, ORIGIN, NativePairError, SyntheticPairSurfaceV1,
    construct_synthetic_pilot_pair, decimal, identity, pilot_entry_clock, utc,
)
from packages.strategies.options_native_pilot_v1_contract import (
    AUTHORITY, MAX_DTE, MIN_DTE, SPECIFICATION_FINGERPRINT,
)

CONTRACT = "atlas-options-native-synthetic-pair-account-v1"
KINDS = {"BUY", "SELL", "CANCEL_ENTRY", "REQUEST_EXIT", "SETTLE"}


@dataclass(frozen=True, slots=True)
class SyntheticPairIntentV1:
    case_id: str
    at_utc: datetime
    call_symbol: str
    put_symbol: str
    call_limit_per_share: str
    put_limit_per_share: str
    pair_fingerprint: str
    fixture_signal_passed: bool
    origin: str = ORIGIN


@dataclass(frozen=True, slots=True)
class SyntheticPairEventV1:
    event_id: str
    case_id: str
    kind: str
    executed_at_utc: datetime
    available_at_utc: datetime
    option_symbol: str | None = None
    price_per_share: str | None = None
    reference_fill_id: str | None = None
    terminal_unfilled_confirmed: bool = False
    qualified: bool = True
    origin: str = ORIGIN


@dataclass(frozen=True, slots=True)
class SyntheticPairMarkV1:
    case_id: str
    option_symbol: str
    observed_at_utc: datetime
    available_at_utc: datetime
    bid_per_share: str
    qualified: bool
    origin: str = ORIGIN


def synthetic_pair_intent(
    surface: SyntheticPairSurfaceV1, *, fixture_signal_passed: bool,
) -> SyntheticPairIntentV1:
    """Bind reconstructed fixture geometry to ask limits; signal is a fixture assumption."""
    pair = construct_synthetic_pilot_pair(surface)
    if pair["status"] != "FIXTURE_PAIR_CANDIDATE" or type(fixture_signal_passed) is not bool:
        raise NativePairError("qualified fixture geometry and explicit synthetic signal required")
    call, put = pair["selected_quotes"]
    return SyntheticPairIntentV1(
        case_id=surface.case_id, at_utc=pilot_entry_clock(surface.feature_cutoff_utc),
        call_symbol=call["option_symbol"], put_symbol=put["option_symbol"],
        call_limit_per_share=call["ask"], put_limit_per_share=put["ask"],
        pair_fingerprint=pair["pair_fingerprint"], fixture_signal_passed=fixture_signal_passed,
    )


def replay_synthetic_pair_account(
    intents: tuple[SyntheticPairIntentV1, ...], events: tuple[SyntheticPairEventV1, ...], *,
    as_of_utc: datetime, entry_fee_per_contract: str, exit_fee_per_contract: str,
    initial_cash: str = "100000.00", marks: tuple[SyntheticPairMarkV1, ...] = (),
) -> dict[str, Any]:
    cutoff = utc(as_of_utc)
    if (not isinstance(intents, tuple) or not 1 <= len(intents) <= 1000
            or not isinstance(events, tuple) or len(events) > 10000
            or not isinstance(marks, tuple) or len(marks) > 2000):
        raise NativePairError("bounded intent/event/mark tuples required")
    initial = decimal(initial_cash)
    if initial != _money(initial):
        raise NativePairError("initial cash must have cent precision")
    fee_in, fee_out = (decimal(value, zero=True) for value in (entry_fee_per_contract, exit_fee_per_contract))
    if any(fee != _money(fee) for fee in (fee_in, fee_out)):
        raise NativePairError("fixture fees require cent precision; no broker rounding rule supplied")
    fee_in, fee_out = _money(fee_in), _money(fee_out)
    by_id = {}
    for intent in intents:
        if (not isinstance(intent, SyntheticPairIntentV1) or intent.origin != ORIGIN
                or not isinstance(intent.case_id, str) or not intent.case_id or intent.case_id in by_id
                or type(intent.fixture_signal_passed) is not bool
                or not isinstance(intent.pair_fingerprint, str)
                or re.fullmatch(r"[0-9a-f]{64}", intent.pair_fingerprint) is None):
            raise NativePairError("unique typed synthetic intent and pair binding required")
        call, put = identity(intent.call_symbol), identity(intent.put_symbol)
        if call[1] != "C" or put[1] != "P" or (call[0], call[2]) != (put[0], put[2]):
            raise NativePairError("same-strike/expiry CALL and PUT required")
        at = utc(intent.at_utc)
        pilot_entry_clock(at - timedelta(minutes=1))
        if not MIN_DTE <= (call[0] - at.astimezone(EASTERN).date()).days <= MAX_DTE:
            raise NativePairError("intent expiration outside frozen DTE band")
        decimal(intent.call_limit_per_share)
        decimal(intent.put_limit_per_share)
        by_id[intent.case_id] = intent
    ids = set()
    for event in events:
        if (not isinstance(event, SyntheticPairEventV1) or event.origin != ORIGIN
                or not isinstance(event.event_id, str) or not event.event_id or event.event_id in ids
                or event.case_id not in by_id or event.kind not in KINDS
                or type(event.qualified) is not bool or type(event.terminal_unfilled_confirmed) is not bool):
            raise NativePairError("unique typed synthetic event required")
        ids.add(event.event_id)
        executed, available = utc(event.executed_at_utc), utc(event.available_at_utc)
        intent = by_id[event.case_id]
        if not utc(intent.at_utc) <= executed <= available:
            raise NativePairError("event execution/availability chronology invalid")
        if available > cutoff:
            continue  # future receipt economics cannot affect this account snapshot
        if event.kind != "BUY" and executed <= utc(intent.at_utc):
            raise NativePairError("non-entry event must follow order eligibility")
        if event.kind == "REQUEST_EXIT":
            if event.option_symbol is not None:
                raise NativePairError("exit request applies to the original pair")
        elif event.option_symbol not in (intent.call_symbol, intent.put_symbol):
            raise NativePairError("event changed the original contract")
        if event.kind in {"BUY", "SELL"}:
            decimal(event.price_per_share, zero=event.kind == "SELL")
            if executed.astimezone(EASTERN).date() > identity(event.option_symbol)[0]:
                raise NativePairError("fill after expiry requires separate settlement/exercise evidence")
        elif event.price_per_share is not None:
            raise NativePairError("non-fill event cannot supply an execution price")
        if (event.kind == "SETTLE") != (event.reference_fill_id is not None):
            raise NativePairError("only settlement references a prior sale fill")
        if (event.kind == "CANCEL_ENTRY") != event.terminal_unfilled_confirmed:
            raise NativePairError("cancellation requires terminal zero-fill finality; timeouts release nothing")
    settled, unsettled, realized = initial, Decimal("0.00"), Decimal("0.00")
    groups: dict[str, dict[str, Any]] = {}
    sales: dict[str, dict[str, Any]] = {}
    decisions = {i.case_id: {"case_id": i.case_id, "status": "FUTURE_INTENT_NOT_REACHED"} for i in intents}
    ledger = []

    def reserved():
        entry = sum((sum(group["pending"].values(), Decimal(0)) for group in groups.values()), Decimal(0))
        exits = sum((group["exit_reserve"] for group in groups.values()), Decimal(0))
        return entry, exits

    def record(kind, cid, at, before, **extra):
        entry, exits = reserved()
        held_basis = sum((sum((p["basis"] for p in g["positions"].values()), Decimal(0)) for g in groups.values()), Decimal(0))
        if (settled < entry + exits or min(settled, unsettled, entry, exits) < 0
                or settled + unsettled != initial + realized - held_basis):
            raise NativePairError("cash, basis, settlement or reservation invariant failed")
        ledger.append({"kind": kind, "case_id": cid, "at_utc": at.isoformat(),
                       "cash_delta": str(_money(settled + unsettled - before)),
                       "settled_cash": str(_money(settled)), "unsettled_sale_proceeds": str(_money(unsettled)),
                       "entry_cash_reserved": str(_money(entry)), "exit_fees_reserved": str(_money(exits)), **extra})

    timeline = [(utc(i.at_utc), 2, i.case_id, i) for i in intents if utc(i.at_utc) <= cutoff]
    priority = {"SELL": 0, "CANCEL_ENTRY": 0, "SETTLE": 1, "REQUEST_EXIT": 0, "BUY": 3}
    timeline += [(utc(e.available_at_utc), priority[e.kind], e.event_id, e)
                 for e in events if utc(e.available_at_utc) <= cutoff]
    # An exit request precedes sells at the same knowledge clock. Receipts for
    # old groups settle/release before a competing new intent at that clock.
    timeline.sort(key=lambda row: (row[0], row[1], 0 if isinstance(row[3], SyntheticPairEventV1) and row[3].kind == "REQUEST_EXIT" else 1, row[2]))
    for at, _, _, item in timeline:
        before = settled + unsettled
        cid = item.case_id
        if isinstance(item, SyntheticPairIntentV1):
            entry, exits = reserved()
            available = settled - entry - exits
            caps = {item.call_symbol: _money(decimal(item.call_limit_per_share) * 100) + fee_in,
                    item.put_symbol: _money(decimal(item.put_limit_per_share) * 100) + fee_in}
            total = sum(caps.values(), Decimal(0)) + fee_out * 2
            if not item.fixture_signal_passed:
                status = "FIXTURE_SIGNAL_ABSTAIN"
            elif any(g["pending"] or g["positions"] for g in groups.values()):
                status = "PAIR_SLOT_OCCUPIED"
            elif total > available * Decimal("0.05"):
                status = "PAIR_RISK_BUDGET_EXCEEDED"
            else:
                status = "PAIR_ENTRY_PENDING"
                groups[cid] = {"pending": caps, "positions": {}, "exit_reserve": fee_out * 2,
                               "entered": set(), "formed": False, "aborted": False, "exit_requested": None}
            decisions[cid]["status"] = status
            record("MODELED_PAIR_INTENT", cid, at, before, status=status, pair_fingerprint=item.pair_fingerprint,
                   leg_entry_caps_including_fees={symbol: str(cap) for symbol, cap in caps.items()},
                   total_debit_and_fee_cap=str(total))
            continue
        event = item
        if cid not in groups:
            continue  # rejected/not-reached intents cannot consume future fills
        group = groups[cid]
        symbol = event.option_symbol
        if not event.qualified:
            record("REJECTED_UNQUALIFIED_FIXTURE_EVENT", cid, at, before, event_id=event.event_id)
            continue
        if event.kind == "REQUEST_EXIT":
            if group["exit_requested"] is not None or not (group["pending"] or group["positions"]):
                raise NativePairError("duplicate pair exit request")
            group["exit_requested"] = at
            group["aborted"] = len(group["positions"]) != 2
        elif event.kind == "BUY":
            if symbol not in group["pending"] or symbol in group["entered"]:
                raise NativePairError("duplicate entry or fill contradicts final cancellation")
            cost = _money(decimal(event.price_per_share) * 100) + fee_in
            if cost > group["pending"][symbol]:
                raise NativePairError("entry fill exceeds its reserved limit")
            group["pending"].pop(symbol)
            settled -= cost
            group["positions"][symbol] = {"basis": cost, "known_at": at}
            group["entered"].add(symbol)
            group["formed"] |= len(group["positions"]) == 2
        elif event.kind == "CANCEL_ENTRY":
            if symbol not in group["pending"]:
                raise NativePairError("final cancellation does not match a pending original leg")
            group["pending"].pop(symbol)
            group["exit_reserve"] -= fee_out
            group["aborted"] = True
        elif event.kind == "SELL":
            if (symbol not in group["positions"] or group["exit_requested"] is None
                    or utc(event.executed_at_utc) < group["exit_requested"]
                    or utc(event.executed_at_utc) < group["positions"][symbol]["known_at"]):
                raise NativePairError("sale requires a reached exit request and known original position")
            basis = group["positions"].pop(symbol)["basis"]
            gross = _money(decimal(event.price_per_share, zero=True) * 100)
            settled -= fee_out
            unsettled += gross
            group["exit_reserve"] -= fee_out
            pnl = gross - fee_out - basis
            realized += pnl
            sales[event.event_id] = {"case_id": cid, "symbol": symbol, "gross": gross,
                                     "known_at": at, "settled": False}
        elif event.kind == "SETTLE":
            sale = sales.get(event.reference_fill_id)
            if (sale is None or sale["settled"] or sale["case_id"] != cid or sale["symbol"] != symbol
                    or utc(event.executed_at_utc) < sale["known_at"]):
                raise NativePairError("settlement must bind an unsettled known original sale exactly once")
            unsettled -= sale["gross"]
            settled += sale["gross"]
            sale["settled"] = True
        record("MODELED_" + event.kind, cid, at, before, event_id=event.event_id,
               option_symbol=symbol, executed_at_utc=utc(event.executed_at_utc).isoformat(),
               reference_fill_id=event.reference_fill_id, price_per_share=event.price_per_share,
               terminal_unfilled_confirmed=event.terminal_unfilled_confirmed,
               gross_sale_proceeds=str(gross) if event.kind == "SELL" else None,
               removed_entry_basis=str(basis) if event.kind == "SELL" else None,
               realized_pnl=str(pnl) if event.kind == "SELL" else None,
               fee_charged=str(fee_in if event.kind == "BUY" else fee_out if event.kind == "SELL" else Decimal("0.00")))
    held = {}
    pending_groups = 0
    for cid, group in groups.items():
        intent = by_id[cid]
        held.update({(cid, symbol): position for symbol, position in group["positions"].items()})
        pending_groups += bool(group["pending"])
        if (group["positions"] or group["pending"]) and cutoff.astimezone(EASTERN).date() > identity(intent.call_symbol)[0]:
            status = "OPEN_UNRESOLVED_EXPIRY_OR_EXERCISE"
        elif group["pending"]:
            status = "OPEN_ENTRY_LEG_EXPOSURE" if group["positions"] else "PAIR_ENTRY_PENDING"
        elif len(group["positions"]) == 2:
            status = "OPEN_COMPLETE_PAIR"
        elif group["positions"]:
            status = "OPEN_RESIDUAL_LEG_EXPOSURE"
        elif group["formed"] and not group["aborted"]:
            status = "SYNTHETIC_PAIR_ROUND_TRIP_MODELED"
        elif group["entered"]:
            status = "ABORTED_PAIR_EXPOSURE_CLOSED"
        else:
            status = "UNFILLED_PAIR_CANCELED"
        decisions[cid]["status"] = status
    mark_by_key = {}
    for mark in marks:
        if (not isinstance(mark, SyntheticPairMarkV1) or mark.origin != ORIGIN
                or type(mark.qualified) is not bool or (mark.case_id, mark.option_symbol) not in held
                or (mark.case_id, mark.option_symbol) in mark_by_key):
            raise NativePairError("exact unique current-position mark fixture required")
        decimal(mark.bid_per_share, zero=True)
        utc(mark.observed_at_utc)
        utc(mark.available_at_utc)
        mark_by_key[(mark.case_id, mark.option_symbol)] = mark
    coverage = []
    known_value = Decimal("0.00")
    for key, position in sorted(held.items()):
        mark = mark_by_key.get(key)
        expiry_unresolved = cutoff.astimezone(EASTERN).date() > identity(key[1])[0]
        known = (not expiry_unresolved and mark is not None and mark.qualified
                 and utc(mark.observed_at_utc) == cutoff and utc(mark.available_at_utc) == cutoff)
        value = _money(decimal(mark.bid_per_share, zero=True) * 100) if known else None
        if value is not None:
            known_value += value
        coverage.append({"case_id": key[0], "option_symbol": key[1], "units": 1,
                         "entry_debit": str(position["basis"]), "market_value": str(value) if value is not None else None,
                         "mark_status": "EXPIRY_EXERCISE_UNRESOLVED" if expiry_unresolved else
                                        "KNOWN_FIXTURE_MARK" if known else "MISSING_UNQUALIFIED_OR_CLOCK_MISMATCH"})
    entry, exits = reserved()
    complete_value = not pending_groups and all(row["market_value"] is not None for row in coverage)
    equity = settled + unsettled + known_value if complete_value else None
    result = {
        "contract": CONTRACT, "specification_fingerprint": SPECIFICATION_FINGERPRINT,
        "status": "SYNTHETIC_PAIR_MECHANICS_ONLY_NOT_HISTORICAL", "as_of_utc": cutoff.isoformat(),
        "intent_denominator": len(intents), "original_discovery_denominator": None,
        "reached_intents": sum(utc(i.at_utc) <= cutoff for i in intents),
        "initial_cash": str(initial), "settled_cash": str(_money(settled)),
        "unsettled_sale_proceeds": str(_money(unsettled)), "cash_and_sale_receivables": str(_money(settled + unsettled)),
        "available_settled_cash": str(_money(settled - entry - exits)),
        "entry_cash_reserved": str(_money(entry)), "exit_fees_reserved": str(_money(exits)),
        "fee_assumptions": {"entry_per_contract": str(fee_in), "exit_per_contract": str(fee_out), "broker_qualified": False},
        "modeled_realized_pnl": str(_money(realized)), "ending_equity": str(_money(equity)) if equity is not None else None,
        "modeled_liquidation_equity": str(_money(equity - fee_out * len(held))) if equity is not None else None,
        "positions": coverage, "pending_entry_groups": pending_groups,
        "unsettled_sale_count": sum(not sale["settled"] for sale in sales.values()),
        "completed_pairs": sum(row["status"] == "SYNTHETIC_PAIR_ROUND_TRIP_MODELED" for row in decisions.values()),
        "decisions": [decisions[cid] for cid in sorted(decisions)], "ledger": ledger,
        "historical_fills_verified": 0, "historical_performance_evidence": False,
        "authority": dict(AUTHORITY),
    }
    result["replay_fingerprint"] = _fingerprint(result)
    return result
