from __future__ import annotations

"""No-lookahead long-only stock/CALL/PUT account mechanics for synthetic fixtures.

This engine is deliberately separate from historical source admission. Current
dated source casebooks do not certify synchronized observations, contract
deliverables or fills, so they MUST NOT be transformed into ReplaySignal here.
"""

from collections import Counter
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Literal, Mapping
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.offline_option_exit_retry_v1 import (
    OptionExitRetryCursorV1, OptionExitRetryPlanV1, SyntheticExitQuoteV1,
    advance_option_exit_retry,
)

CONTRACT = "atlas-multiyear-synthetic-account-replay-engine-v1"
EXIT_FILL_CONTRACT = "atlas-synthetic-option-exit-fill-v1"
ORIGIN = "SYNTHETIC_FIXTURE_ONLY"
MODES = ("STOCK", "CALL", "PUT", "ABSTAIN")
CENTS = Decimal("0.01")
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^O:([A-Z0-9.]{1,6})(\d{6})([CP])(\d{8})$")
Mode = Literal["STOCK", "CALL", "PUT", "ABSTAIN"]


class OfflineAccountReplayError(ValueError):
    pass


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


def _decimal(value: object, label: str, *, allow_zero: bool = False) -> Decimal:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise OfflineAccountReplayError(f"{label} requires an exact decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise OfflineAccountReplayError(f"{label} is not decimal") from exc
    if not number.is_finite() or (number < 0 if allow_zero else number <= 0):
        raise OfflineAccountReplayError(f"{label} out of range")
    return number


def _stamp(value: datetime, label: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise OfflineAccountReplayError(f"{label} requires timezone-aware datetime")
    return value.astimezone(UTC)


@dataclass(frozen=True, slots=True)
class ReplayPolicy:
    initial_cash: str = "100000.00"
    fraction_of_available_cash: str = "0.10"
    max_open_positions: int = 5
    stock_slippage_bps: str = "5"
    option_slippage_per_share: str = "0.00"
    stock_entry_fee: str = "0.00"
    stock_exit_fee: str = "0.00"
    option_entry_fee_per_contract: str = "0.65"
    option_exit_fee_per_contract: str = "0.65"
    maximum_units_per_position: int = 10000

    def validate(self) -> None:
        cash = _decimal(self.initial_cash, "initial cash")
        if cash != _money(cash):
            raise OfflineAccountReplayError("initial cash requires cent precision")
        frac = _decimal(self.fraction_of_available_cash, "allocation fraction")
        if frac > 1:
            raise OfflineAccountReplayError("allocation fraction exceeds available cash")
        for name in (
            "stock_slippage_bps", "option_slippage_per_share", "stock_entry_fee",
            "stock_exit_fee", "option_entry_fee_per_contract", "option_exit_fee_per_contract",
        ):
            _decimal(getattr(self, name), name, allow_zero=True)
        if _decimal(self.stock_slippage_bps, "slippage", allow_zero=True) >= 10000:
            raise OfflineAccountReplayError("stock slippage invalid")
        for name in ("max_open_positions", "maximum_units_per_position"):
            value = getattr(self, name)
            if type(value) is not int or not 1 <= value <= 100000:
                raise OfflineAccountReplayError(f"{name} out of range")


@dataclass(frozen=True, slots=True)
class SyntheticOptionExitFillV1:
    """Explicit invented execution, never inferred from a quote or bid size.

    Cash becomes usable at available_at_utc, without backdating earlier account
    decisions. execution_per_share is the final execution price; account option
    slippage is not charged again. Policy exit fees still apply per closed unit.
    Qualification flags describe the fixture's assumptions, not historical proof.
    """
    fill_id: str
    option_symbol: str
    executed_at_utc: datetime
    available_at_utc: datetime
    contracts: int
    execution_per_share: str
    source_integrity_qualified: bool
    execution_clock_qualified: bool
    origin: str = ORIGIN

    def validate(self, symbol: str, opened_at: datetime, expiration: date) -> None:
        if (self.origin != ORIGIN or not isinstance(self.fill_id, str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", self.fill_id) is None
                or self.option_symbol != symbol):
            raise OfflineAccountReplayError("exit fill requires fixture identity and exact option")
        executed = _stamp(self.executed_at_utc, "fill execution")
        available = _stamp(self.available_at_utc, "fill availability")
        if (executed <= opened_at or available < executed
                or executed.astimezone(EASTERN).date() > expiration):
            raise OfflineAccountReplayError("exit fill has invalid execution/availability chronology")
        if type(self.contracts) is not int or not 1 <= self.contracts <= 100000:
            raise OfflineAccountReplayError("exit fill requires a positive bounded contract quantity")
        _decimal(self.execution_per_share, "fill execution price", allow_zero=True)
        if (type(self.source_integrity_qualified) is not bool
                or type(self.execution_clock_qualified) is not bool):
            raise OfflineAccountReplayError("exit fill qualification must be boolean")


@dataclass(frozen=True, slots=True)
class ReplayLeg:
    """One *synthetic* time-qualified priced long instrument path.

    Entry side is ask for option, stock raw price plus adverse slippage.
    Exit side is bid for option, stock raw price less adverse slippage.
    """
    symbol: str
    kind: Literal["STOCK", "CALL", "PUT"]
    entry_at_utc: datetime
    exit_at_utc: datetime | None
    entry_per_share: str
    exit_per_share: str | None
    multiplier: int
    expiration: date | None
    source_integrity_qualified: bool
    observation_clock_qualified: bool
    standard_deliverable_verified: bool
    exit_source_integrity_qualified: bool | None = None
    exit_observation_clock_qualified: bool | None = None
    exit_retry_plan: OptionExitRetryPlanV1 | None = None
    exit_fill_fixtures: tuple[SyntheticOptionExitFillV1, ...] = ()

    def validate(self, signal_at_utc: datetime, ticker: str) -> None:
        start = _stamp(self.entry_at_utc, "leg entry")
        end = _stamp(self.exit_at_utc, "leg exit") if self.exit_at_utc is not None else None
        if start <= signal_at_utc or (end is not None and end <= start):
            raise OfflineAccountReplayError("nonchronological synthetic decision/entry/exit")
        if self.kind not in ("STOCK", "CALL", "PUT") or not self.symbol:
            raise OfflineAccountReplayError("instrument identity invalid")
        _decimal(self.entry_per_share, "entry side")
        if (end is None) != (self.exit_per_share is None):
            raise OfflineAccountReplayError("exit source price and clock must be paired")
        if self.exit_per_share is not None:
            _decimal(self.exit_per_share, "exit side", allow_zero=self.kind != "STOCK")
        if self.kind == "STOCK":
            if self.symbol != ticker or self.multiplier != 1 or self.expiration is not None:
                raise OfflineAccountReplayError("stock contract identity changed")
        elif (
            type(self.multiplier) is not int or not 1 <= self.multiplier <= 100000
            or not isinstance(self.expiration, date)
            or isinstance(self.expiration, datetime)
        ):
            raise OfflineAccountReplayError("option multiplier or expiration invalid")
        if self.kind != "STOCK":
            match = OCC.fullmatch(self.symbol)
            if not match or match.group(3) != ("C" if self.kind == "CALL" else "P"):
                raise OfflineAccountReplayError("option OCC identity or right invalid")
            try:
                occ_expiry = datetime.strptime(match.group(2), "%y%m%d").date()
            except ValueError as exc:
                raise OfflineAccountReplayError("option OCC expiration invalid") from exc
            if occ_expiry != self.expiration or int(match.group(4)) <= 0:
                raise OfflineAccountReplayError("option OCC expiry or strike mismatch")
        for flag in (self.source_integrity_qualified, self.observation_clock_qualified,
                     self.standard_deliverable_verified):
            if type(flag) is not bool:
                raise OfflineAccountReplayError("entry admission gate must be boolean")
        for flag in (self.exit_source_integrity_qualified,
                     self.exit_observation_clock_qualified):
            if flag is not None and type(flag) is not bool:
                raise OfflineAccountReplayError("exit source gate must be boolean or absent")
        if self.exit_retry_plan is not None:
            plan = self.exit_retry_plan
            if (not isinstance(plan, OptionExitRetryPlanV1) or self.kind == "STOCK"
                    or plan.option_symbol != self.symbol or plan.expiration != self.expiration
                    or plan.opened_at_utc != start or end is not None
                    or self.exit_source_integrity_qualified is not None
                    or self.exit_observation_clock_qualified is not None):
                raise OfflineAccountReplayError("retry plan must bind the exact option/open and replace the fixed exit")
        if not isinstance(self.exit_fill_fixtures, tuple) or len(self.exit_fill_fixtures) > 64:
            raise OfflineAccountReplayError("exit fill fixtures require a tuple of at most 64 fills")
        if self.exit_fill_fixtures:
            if (self.kind == "STOCK" or end is not None or self.exit_retry_plan is not None
                    or self.exit_source_integrity_qualified is not None
                    or self.exit_observation_clock_qualified is not None):
                raise OfflineAccountReplayError("exit fill fixtures must replace the fixed option exit/retry")
            for fill in self.exit_fill_fixtures:
                if not isinstance(fill, SyntheticOptionExitFillV1):
                    raise OfflineAccountReplayError("typed synthetic exit fill fixture required")
                fill.validate(self.symbol, start, self.expiration)
            if len({fill.fill_id for fill in self.exit_fill_fixtures}) != len(self.exit_fill_fixtures):
                raise OfflineAccountReplayError("duplicate exit fill identity")


@dataclass(frozen=True, slots=True)
class ReplaySignal:
    case_id: str
    year: int
    ticker: str
    decision_at_utc: datetime
    stock: ReplayLeg | None = None
    call: ReplayLeg | None = None
    put: ReplayLeg | None = None
    origin: str = ORIGIN

    def validate(self) -> None:
        at = _stamp(self.decision_at_utc, "signal decision")
        if (
            self.origin != ORIGIN or not self.case_id or not self.ticker
            or type(self.year) is not int or self.year not in range(2021, 2027)
            or at.astimezone(EASTERN).year != self.year
        ):
            raise OfflineAccountReplayError("nonfixture or noncanonical signal identity")
        for kind, leg in (("STOCK", self.stock), ("CALL", self.call), ("PUT", self.put)):
            if leg is not None:
                if not isinstance(leg, ReplayLeg) or leg.kind != kind:
                    raise OfflineAccountReplayError("candidate leg assigned to wrong instrument")
                leg.validate(at, self.ticker)


def _admission(leg: ReplayLeg | None, mode: Mode) -> str:
    if leg is None:
        return "NO_SYNTHETIC_" + mode + "_LEG"
    if not leg.source_integrity_qualified:
        return "UNQUALIFIED_SOURCE_INTEGRITY"
    if not leg.observation_clock_qualified:
        return "UNQUALIFIED_OBSERVATION_CLOCK"
    if not leg.standard_deliverable_verified or (leg.kind != "STOCK" and leg.multiplier != 100):
        return "UNVERIFIED_CONTRACT_DELIVERABLE"
    if leg.kind != "STOCK" and leg.entry_at_utc.astimezone(EASTERN).date() > leg.expiration:
        return "EXPIRED_BEFORE_ENTRY"
    return "ELIGIBLE_SYNTHETIC_ENTRY"


def _entry_unit_terms(
    leg: ReplayLeg, policy: ReplayPolicy,
) -> tuple[Decimal, Decimal, Decimal]:
    """Only entry-observed price and known entry/exit fees are read at admission."""
    entry = _decimal(leg.entry_per_share, "entry")
    if leg.kind == "STOCK":
        bps = _decimal(policy.stock_slippage_bps, "stock slippage", allow_zero=True)
        debit = _money(entry * (Decimal(1) + bps / Decimal(10000)))
        fee_in = _money(_decimal(policy.stock_entry_fee, "entry fee", allow_zero=True))
        fee_out = _money(_decimal(policy.stock_exit_fee, "exit fee", allow_zero=True))
    else:
        slip = _decimal(policy.option_slippage_per_share, "option slippage", allow_zero=True)
        debit = _money((entry + slip) * leg.multiplier)
        fee_in = _money(_decimal(policy.option_entry_fee_per_contract, "entry fee", allow_zero=True))
        fee_out = _money(_decimal(policy.option_exit_fee_per_contract, "exit fee", allow_zero=True))
    if debit <= 0 or fee_in < 0 or fee_out < 0:
        raise OfflineAccountReplayError("invalid modeled entry economics")
    return debit, fee_in, fee_out


def _observed_exit_credit(leg: ReplayLeg, policy: ReplayPolicy) -> Decimal:
    """Access the future exit price only when a qualified exit event is reached."""
    if leg.exit_at_utc is None or leg.exit_per_share is None:
        raise OfflineAccountReplayError("unqualified or absent future exit cannot settle position")
    exit_ = _decimal(leg.exit_per_share, "exit", allow_zero=leg.kind != "STOCK")
    if leg.kind == "STOCK":
        bps = _decimal(policy.stock_slippage_bps, "stock slippage", allow_zero=True)
        credit = _money(exit_ * (Decimal(1) - bps / Decimal(10000)))
    else:
        slip = _decimal(policy.option_slippage_per_share, "option slippage", allow_zero=True)
        credit = _money(max(Decimal(0), exit_ - slip) * leg.multiplier)
    if credit < 0:
        raise OfflineAccountReplayError("invalid modeled exit economics")
    return credit

def replay_synthetic_account(
    signals: list[ReplaySignal], *, mode: Mode,
    policy: ReplayPolicy | None = None,
    as_of_utc: datetime | None = None,
    exit_quotes: Mapping[tuple[str, datetime], SyntheticExitQuoteV1 | None] | None = None,
) -> dict[str, Any]:
    """Chronological entry-first cash ledger with optional as-of knowledge boundary.

    Synthetic fixtures can open positions without an observed exit. No next-session
    quote may decide whether an earlier entry was admitted. Open contracts have
    NULL equity when an independently qualified terminal mark is unavailable.
    """
    policy = policy or ReplayPolicy()
    policy.validate()
    cutoff = _stamp(as_of_utc, "as-of") if as_of_utc is not None else None
    if mode not in MODES or not isinstance(signals, list) or not signals:
        raise OfflineAccountReplayError("nonempty fixture cohort and explicit mode required")
    if len(signals) > 100000:
        raise OfflineAccountReplayError("fixture cohort exceeds safe bound")
    if any(not isinstance(s, ReplaySignal) for s in signals):
        raise OfflineAccountReplayError("fixture signal object required")
    for signal in signals:
        signal.validate()
    if len({s.case_id for s in signals}) != len(signals):
        raise OfflineAccountReplayError("duplicate original case identity")
    if exit_quotes is not None and (not isinstance(exit_quotes, Mapping) or len(exit_quotes) > 100000):
        raise OfflineAccountReplayError("bounded in-memory synthetic exit quote map required")
    quotes = exit_quotes if exit_quotes is not None else {}
    if mode != "ABSTAIN" and sum(
        len(leg.exit_retry_plan.attempt_times_utc)
        for signal in signals if (leg := getattr(signal, mode.lower())) is not None
        and leg.exit_retry_plan is not None
    ) > 100000:
        raise OfflineAccountReplayError("aggregate retry attempts exceed safe bound")
    chosen_fills = [
        fill for signal in signals
        if mode != "ABSTAIN" and (leg := getattr(signal, mode.lower())) is not None
        for fill in leg.exit_fill_fixtures
    ]
    if len(chosen_fills) > 100000:
        raise OfflineAccountReplayError("aggregate exit fill fixtures exceed safe bound")
    if len({fill.fill_id for fill in chosen_fills}) != len(chosen_fills):
        raise OfflineAccountReplayError("duplicate exit fill identity across cases")
    # Without an explicit cutoff, consume the complete chosen-mode fixture clock.
    # Include failed exit attempts: their source gate cannot erase when an attempt
    # was reached. Other modes' paths must not advance this account's horizon.
    horizon = cutoff
    if horizon is None:
        clocks = [_stamp(s.decision_at_utc, "decision") for s in signals]
        if mode != "ABSTAIN":
            for signal in signals:
                leg = getattr(signal, mode.lower())
                if leg is not None:
                    clocks.append(_stamp(leg.entry_at_utc, "entry"))
                    if leg.exit_at_utc is not None:
                        clocks.append(_stamp(leg.exit_at_utc, "exit"))
                    if leg.exit_retry_plan is not None:
                        clocks.append(leg.exit_retry_plan.deadline_at_utc)
                    clocks.extend(_stamp(fill.available_at_utc, "fill availability")
                                  for fill in leg.exit_fill_fixtures)
        horizon = max(clocks)
    cash = _decimal(policy.initial_cash, "initial cash")
    initial_cash = cash
    realized_pnl = Decimal("0.00")
    fill_path_reached = False
    reserved_exit_fees = Decimal("0.00")
    positions: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    by_year: dict[str, Counter[str]] = {str(y): Counter() for y in range(2021, 2027)}
    events: list[tuple[datetime, int, str, ReplayLeg, bool, SyntheticOptionExitFillV1 | None]] = []
    selected: dict[str, ReplayLeg] = {}
    retry_cursors: dict[str, OptionExitRetryCursorV1] = {}
    for signal in signals:
        leg = getattr(signal, mode.lower()) if mode != "ABSTAIN" else None
        if cutoff is not None and _stamp(signal.decision_at_utc, "decision") > cutoff:
            status = "FUTURE_SIGNAL_NOT_REACHED"
        else:
            status = "ABSTAIN_BY_POLICY" if mode == "ABSTAIN" else _admission(leg, mode)
            if (status == "ELIGIBLE_SYNTHETIC_ENTRY" and cutoff is not None
                    and _stamp(leg.entry_at_utc, "entry") > cutoff):
                status = "FUTURE_ENTRY_NOT_REACHED"
        decisions[signal.case_id] = {
            "case_id": signal.case_id, "year": signal.year,
            "ticker": signal.ticker, "mode": mode, "status": status,
            "units": 0, "modeled_net_pnl": None,
        }
        if status == "ELIGIBLE_SYNTHETIC_ENTRY":
            selected[signal.case_id] = leg
            events.append((_stamp(leg.entry_at_utc, "entry"), 1, signal.case_id, leg, False, None))
            if leg.exit_retry_plan is not None:
                events.extend((at, 0, signal.case_id, leg, True, None)
                              for at in leg.exit_retry_plan.attempt_times_utc
                              if cutoff is None or at <= cutoff)
            events.extend((_stamp(fill.available_at_utc, "fill availability"), 0,
                           signal.case_id, leg, False, fill)
                          for fill in leg.exit_fill_fixtures
                          if cutoff is None or _stamp(fill.available_at_utc, "fill availability") <= cutoff)
            if (leg.exit_at_utc is not None and leg.exit_per_share is not None
                    and (cutoff is None or _stamp(leg.exit_at_utc, "exit") <= cutoff)
                    and leg.exit_source_integrity_qualified is not False
                    and leg.exit_observation_clock_qualified is not False
                    and (leg.kind == "STOCK" or
                         leg.exit_at_utc.astimezone(EASTERN).date() <= leg.expiration)):
                events.append((_stamp(leg.exit_at_utc, "exit"), 0, signal.case_id, leg, False, None))
    # Release existing positions before admitting new ones at an identical stamp.
    for at, priority, cid, leg, is_retry, fill in sorted(
        events, key=lambda e: (e[0], e[1], e[2], e[5].fill_id if e[5] is not None else ""),
    ):
        row = decisions[cid]
        debit, fee_in, fee_out = _entry_unit_terms(leg, policy)
        if priority == 1:
            if len(positions) >= policy.max_open_positions:
                row["status"] = "MAX_CONCURRENT_POSITIONS_REACHED"
                continue
            available = _money(cash - reserved_exit_fees)
            budget = _money(available * _decimal(policy.fraction_of_available_cash, "fraction"))
            # Reserve the exit fee before allocating another cash-only position.
            per_unit_liquidity = debit + fee_in + fee_out
            units = min(
                policy.maximum_units_per_position,
                int(min(available, budget) // per_unit_liquidity),
            )
            if units < 1:
                row["status"] = "INSUFFICIENT_CASH_FOR_ONE_UNIT"
                continue
            cost = (debit + fee_in) * units
            reserve = fee_out * units
            cash = _money(cash - cost)
            reserved_exit_fees = _money(reserved_exit_fees + reserve)
            if cash < reserved_exit_fees:
                raise OfflineAccountReplayError("cash-only account overdraft or unfunded exit fees")
            positions[cid] = {
                "units": units, "debit": cost, "reserved_exit_fee": reserve, "entry_at": at,
                "kind": leg.kind, "symbol": leg.symbol,
            }
            row["status"] = "OPEN_UNMARKED_NO_QUALIFIED_EXIT"
            row["units"] = units
            if leg.exit_retry_plan is not None:
                retry_cursors[cid] = OptionExitRetryCursorV1(
                    leg.exit_retry_plan, units, policy.option_slippage_per_share, at,
                )
            ledger.append({
                "kind": "MODELED_ENTRY", "case_id": cid,
                "at_utc": at.isoformat(), "instrument": leg.symbol,
                "units": units, "cash_delta": str(-cost),
                "cash_after": str(cash), "exit_fees_reserved": str(reserved_exit_fees),
            })
        elif cid in positions:
            if fill is not None:
                fill_path_reached = True
                position = positions[cid]
                if position["kind"] != leg.kind or position["symbol"] != fill.option_symbol:
                    raise OfflineAccountReplayError("modeled exit fill position identity changed")
                common = {
                    "case_id": cid, "at_utc": at.isoformat(), "instrument": fill.option_symbol,
                    "fill_id": fill.fill_id, "fixture_origin": fill.origin,
                    "executed_at_utc": _stamp(fill.executed_at_utc, "fill execution").isoformat(),
                    "available_at_utc": at.isoformat(),
                }
                if not fill.source_integrity_qualified or not fill.execution_clock_qualified:
                    ledger.append(common | {
                        "kind": "MODELED_EXIT_FILL_REJECTED",
                        "reason": ("UNQUALIFIED_SOURCE_INTEGRITY" if not fill.source_integrity_qualified
                                   else "UNQUALIFIED_EXECUTION_CLOCK"),
                        "cash_delta": "0.00", "cash_after": str(cash),
                        "exit_fees_reserved": str(reserved_exit_fees),
                    })
                    if "closed_units" not in row:
                        row["status"] = "OPEN_UNQUALIFIED_EXIT_SOURCE"
                    continue
                units = fill.contracts
                if units > position["units"]:
                    raise OfflineAccountReplayError("exit fill exceeds remaining position quantity")
                # Entry debit and escrow are exact cent amounts per contract.
                allocated_debit = (debit + fee_in) * units
                released_reserve = fee_out * units
                credit = _money(_decimal(fill.execution_per_share, "fill execution price", allow_zero=True)
                                * leg.multiplier)
                proceeds = (credit - fee_out) * units
                pnl = _money(proceeds - allocated_debit)
                cash = _money(cash + proceeds)
                reserved_exit_fees = _money(reserved_exit_fees - released_reserve)
                position["units"] -= units
                position["debit"] -= allocated_debit
                position["reserved_exit_fee"] -= released_reserve
                realized_pnl += pnl
                row["closed_units"] = row.get("closed_units", 0) + units
                row["remaining_units"] = position["units"]
                row["modeled_realized_pnl"] = str(_money(
                    Decimal(row.get("modeled_realized_pnl", "0.00")) + pnl))
                complete = position["units"] == 0
                if complete:
                    positions.pop(cid)
                    row["modeled_net_pnl"] = row["modeled_realized_pnl"]
                    row["status"] = "SYNTHETIC_ROUND_TRIP_MODELED"
                else:
                    row["status"] = "OPEN_PARTIALLY_EXITED_UNMARKED"
                if cash < reserved_exit_fees or reserved_exit_fees < 0:
                    raise OfflineAccountReplayError("modeled partial exit violates cash or fee escrow")
                ledger.append(common | {
                    "kind": "MODELED_EXIT" if complete else "MODELED_PARTIAL_EXIT",
                    "units": units, "remaining_units": position["units"],
                    "allocated_entry_debit": str(allocated_debit), "exit_fee": str(released_reserve),
                    "execution_per_share": fill.execution_per_share,
                    "cash_delta": str(proceeds), "cash_after": str(cash),
                    "exit_fees_reserved": str(reserved_exit_fees), "modeled_net_pnl": str(pnl),
                })
                continue
            if is_retry:
                cursor = advance_option_exit_retry(
                    retry_cursors[cid], as_of_utc=at,
                    read_quote=lambda symbol, clock: quotes.get((cid, clock)),
                )
                retry_cursors[cid] = cursor
                attempt = cursor.attempts[-1]
                if cursor.ready_quote is None:
                    row["status"] = cursor.status
                    ledger.append({
                        "kind": "MODELED_EXIT_ATTEMPT_UNRESOLVED", "case_id": cid,
                        "at_utc": at.isoformat(), "instrument": leg.symbol,
                        "attempt_number": len(cursor.attempts), "reason": attempt.result,
                        "cash_delta": "0.00", "cash_after": str(cash),
                        "exit_fees_reserved": str(reserved_exit_fees),
                    })
                    continue
                leg = replace(leg, exit_retry_plan=None, exit_at_utc=at,
                              exit_per_share=cursor.ready_quote.bid_per_share)
            position = positions.pop(cid)
            if position["kind"] != leg.kind or position["symbol"] != leg.symbol:
                raise OfflineAccountReplayError("modeled position identity changed")
            credit = _observed_exit_credit(leg, policy)
            proceeds = (credit - fee_out) * position["units"]
            cash = _money(cash + proceeds)
            reserved_exit_fees = _money(reserved_exit_fees - position["reserved_exit_fee"])
            if cash < reserved_exit_fees or reserved_exit_fees < 0:
                raise OfflineAccountReplayError("modeled exit violates cash or fee escrow")
            pnl = _money(proceeds - position["debit"])
            realized_pnl += pnl
            row["modeled_net_pnl"] = str(pnl)
            row["status"] = "SYNTHETIC_ROUND_TRIP_MODELED"
            ledger.append({
                "kind": "MODELED_EXIT", "case_id": cid,
                "at_utc": at.isoformat(), "instrument": leg.symbol,
                "units": position["units"], "cash_delta": str(proceeds),
                "cash_after": str(cash), "exit_fees_reserved": str(reserved_exit_fees),
                "modeled_net_pnl": str(pnl),
            })
        elif fill is not None and row["units"] > 0:
            raise OfflineAccountReplayError("exit fill supplied after the position was fully closed")
    if reserved_exit_fees != sum(
        (p["reserved_exit_fee"] for p in positions.values()), Decimal(0)
    ):
        raise OfflineAccountReplayError("modeled open-position fee escrow does not reconcile")
    if cash != initial_cash + realized_pnl - sum((p["debit"] for p in positions.values()), Decimal(0)):
        raise OfflineAccountReplayError("modeled cash, realized P&L and remaining entry debit do not reconcile")
    retry_cursors = {cid: replace(cursor, as_of_utc=horizon)
                     for cid, cursor in retry_cursors.items()}
    for cid in positions:
        leg = selected[cid]
        # An expiration DATE does not establish an intraday trading/exercise
        # deadline. Only classify it as past once the local date has ended, and
        # never infer a settlement, mark, cash release, or assignment from it.
        if leg.kind != "STOCK" and horizon.astimezone(EASTERN).date() > leg.expiration:
            decisions[cid]["status"] = "OPEN_UNRESOLVED_EXPIRY_OR_ASSIGNMENT"
        elif cid in retry_cursors:
            decisions[cid]["status"] = retry_cursors[cid].status
        elif (leg.exit_at_utc is not None
              and _stamp(leg.exit_at_utc, "exit") <= horizon
              and (leg.exit_source_integrity_qualified is False
                   or leg.exit_observation_clock_qualified is False)):
            decisions[cid]["status"] = "OPEN_UNQUALIFIED_EXIT_SOURCE"
    for signal in signals:
        by_year[str(signal.year)][decisions[signal.case_id]["status"]] += 1
    rows = [decisions[s.case_id] for s in sorted(signals, key=lambda s: (s.decision_at_utc, s.case_id))]
    round_trips = sum(x["status"] == "SYNTHETIC_ROUND_TRIP_MODELED" for x in rows)
    result = {
        "contract": CONTRACT,
        "status": "SYNTHETIC_ACCOUNT_MECHANICS_ONLY_NOT_HISTORICAL",
        "mode": mode,
        "policy": {
            name: getattr(policy, name) for name in policy.__dataclass_fields__
        },
        "original_case_denominator": len(signals),
        "synthetic_round_trips": round_trips,
        "as_of_utc": cutoff.isoformat() if cutoff is not None else None,
        "replay_horizon_utc": horizon.isoformat(),
        "initial_cash": str(initial_cash),
        "ending_cash": str(cash),
        "modeled_cash_flow_change": str(_money(cash - initial_cash)),
        "modeled_realized_pnl": str(_money(realized_pnl)),
        "modeled_realized_cash_change": (
            str(_money(cash - initial_cash)) if not positions else None
        ),
        "ending_equity": str(cash) if not positions else None,
        "end_open_positions": len(positions),
        "ending_reserved_exit_fees": str(reserved_exit_fees),
        "open_positions": [
            {
                "case_id": cid, "symbol": p["symbol"], "kind": p["kind"],
                "units": p["units"], "entry_debit": str(p["debit"]),
                "reserved_exit_fee": str(p["reserved_exit_fee"]),
                "terminal_market_mark": None, "unrealized_pnl": None,
            }
            for cid, p in sorted(positions.items())
        ],
        "by_year": {
            y: {"original_cases": sum(counts.values()),
                "statuses": dict(sorted(counts.items()))}
            for y, counts in by_year.items()
        },
        "decisions": rows, "ledger": ledger,
        "provider_requests": 0, "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "observed_intraday_drawdown": None,
        "protected_holdout_is_fresh": False,
        "paper": False, "live": False,
    }
    if retry_cursors:
        result["option_exit_retries"] = [
            {"case_id": cid, "cursor_fingerprint": cursor.fingerprint,
             "cursor": cursor.payload()}
            for cid, cursor in sorted(retry_cursors.items())
        ]
    if fill_path_reached:
        result["option_exit_fill_contract"] = EXIT_FILL_CONTRACT
    result["replay_fingerprint"] = _fingerprint(result)
    return result


def compare_synthetic_modes(
    signals: list[ReplaySignal], *, policy: ReplayPolicy | None = None,
) -> dict[str, dict[str, Any]]:
    """All four alternatives use the exact same original signal cohort."""
    return {
        mode: replay_synthetic_account(signals, mode=mode, policy=policy)
        for mode in MODES
    }
