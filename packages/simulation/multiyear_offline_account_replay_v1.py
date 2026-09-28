from __future__ import annotations

"""No-lookahead long-only stock/CALL/PUT account mechanics for synthetic fixtures.

This engine is deliberately separate from historical source admission. Current
dated source casebooks do not certify synchronized observations, contract
deliverables or fills, so they MUST NOT be transformed into ReplaySignal here.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint

CONTRACT = "atlas-multiyear-synthetic-account-replay-engine-v1"
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
    cash = _decimal(policy.initial_cash, "initial cash")
    initial_cash = cash
    reserved_exit_fees = Decimal("0.00")
    positions: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    by_year: dict[str, Counter[str]] = {str(y): Counter() for y in range(2021, 2027)}
    events: list[tuple[datetime, int, str, ReplayLeg]] = []
    selected: dict[str, ReplayLeg] = {}
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
            events.append((_stamp(leg.entry_at_utc, "entry"), 1, signal.case_id, leg))
            if (leg.exit_at_utc is not None and leg.exit_per_share is not None
                    and (cutoff is None or _stamp(leg.exit_at_utc, "exit") <= cutoff)
                    and leg.exit_source_integrity_qualified is not False
                    and leg.exit_observation_clock_qualified is not False
                    and (leg.kind == "STOCK" or
                         leg.exit_at_utc.astimezone(EASTERN).date() <= leg.expiration)):
                events.append((_stamp(leg.exit_at_utc, "exit"), 0, signal.case_id, leg))
    # Release existing positions before admitting new ones at an identical stamp.
    for at, priority, cid, leg in sorted(events, key=lambda e: (e[0], e[1], e[2])):
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
            ledger.append({
                "kind": "MODELED_ENTRY", "case_id": cid,
                "at_utc": at.isoformat(), "instrument": leg.symbol,
                "units": units, "cash_delta": str(-cost),
                "cash_after": str(cash), "exit_fees_reserved": str(reserved_exit_fees),
            })
        elif cid in positions:
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
            row["modeled_net_pnl"] = str(pnl)
            row["status"] = "SYNTHETIC_ROUND_TRIP_MODELED"
            ledger.append({
                "kind": "MODELED_EXIT", "case_id": cid,
                "at_utc": at.isoformat(), "instrument": leg.symbol,
                "units": position["units"], "cash_delta": str(proceeds),
                "cash_after": str(cash), "exit_fees_reserved": str(reserved_exit_fees),
                "modeled_net_pnl": str(pnl),
            })
    if reserved_exit_fees != sum(
        (p["reserved_exit_fee"] for p in positions.values()), Decimal(0)
    ):
        raise OfflineAccountReplayError("modeled open-position fee escrow does not reconcile")
    for cid, position in positions.items():
        leg = selected[cid]
        if leg.kind != "STOCK" and (
            (cutoff is not None and cutoff.astimezone(EASTERN).date() >= leg.expiration)
            or (leg.exit_at_utc is not None
                and leg.exit_at_utc.astimezone(EASTERN).date() > leg.expiration)
        ):
            decisions[cid]["status"] = "OPEN_UNRESOLVED_EXPIRY_OR_ASSIGNMENT"
        elif (leg.exit_source_integrity_qualified is False
              or leg.exit_observation_clock_qualified is False):
            decisions[cid]["status"] = "OPEN_UNQUALIFIED_EXIT_SOURCE"
    for signal in signals:
        by_year[str(signal.year)][decisions[signal.case_id]["status"]] += 1
    rows = [decisions[s.case_id] for s in sorted(signals, key=lambda s: (s.decision_at_utc, s.case_id))]
    round_trips = sum(x["status"] == "SYNTHETIC_ROUND_TRIP_MODELED" for x in rows)
    realized_pnl = sum(
        (Decimal(x["modeled_net_pnl"]) for x in rows if x["modeled_net_pnl"] is not None),
        Decimal(0),
    )
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
