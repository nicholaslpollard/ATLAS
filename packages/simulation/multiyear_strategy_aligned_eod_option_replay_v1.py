from __future__ import annotations

"""Strategy-aligned modeled historical EOD CALL replay.

This adapter keeps the first historical option replay's causal EOD entry, but replaces
its diagnostic "first later liquid bid" exit with the already frozen stock
STOP/TARGET/TIME exit session.

Important timing rule: the option entry is the first *later-session* qualified EOD ask
after the original 09:35 option decision.  If the stock strategy has already exited
by that EOD entry session, no option trade is admitted.  If the strategy exit occurs
later, the option is held to that exact stock exit session.  Missing/illiquid option
evidence on that exact session is an unresolved execution gap; the replay never slides
forward to a more convenient quote.

No provider calls, 2026 outcome reads, verified historical fills, strategy promotion,
PAPER or LIVE authority are created.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Sequence

from packages.core.market_calendar import get_market_calendar
from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.multiyear_demand_quote_cache_v1 import CONTRACT as QUOTE_CONTRACT
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    _decode_snapshot_rows,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT,
    _check_signature,
)
from packages.backtesting.recurrent_successor_daily_exit_sweep import (
    DailyPathCase,
    resolve_daily_exit,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_CONTRACT as BASE_SCENARIO_CONTRACT,
    _aware,
)
from packages.simulation.multiyear_offline_account_replay_v1 import (
    ReplayPolicy,
    _decimal,
    _money,
)

CONTRACT = "atlas-multiyear-strategy-aligned-eod-option-replay-v1"
SCENARIO_CONTRACT = "atlas-multiyear-strategy-aligned-eod-option-scenario-v1"
OUTPUT_REL = "data/options/derived/multiyear_strategy_aligned_eod_option_replay_v1"
SCENARIO_REL = "data/options/derived/multiyear_strategy_aligned_eod_option_scenario_v1"
PROTECTED_2026_START = date(2026, 1, 1)


class StrategyAlignedEodReplayError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class StrategyExitPolicy:
    stop_fraction: float
    target_fraction: float

    @property
    def policy_id(self) -> str:
        return (
            f"STOP_{int(round(self.stop_fraction * 100)):02d}PCT_"
            f"TARGET_{int(round(self.target_fraction * 100)):02d}PCT"
        )


def _policy_payload(policy: StrategyExitPolicy) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "stop_fraction": policy.stop_fraction,
        "target_fraction": policy.target_fraction,
        "same_session_collision": "STOP_WORST_CASE",
        "gap_through_stop": "SESSION_OPEN_IF_WORSE_THAN_STOP",
        "gap_through_target": "TARGET_PRICE_NO_POSITIVE_SLIPPAGE",
        "time_exit": "FIFTH_ENTRY_SESSION_REGULAR_CLOSE",
    }


def _exit_row_qualified(row: dict[str, Any]) -> bool:
    bid = row.get("bid")
    return bool(
        row.get("updated_is_1600_et")
        and row.get("two_sided")
        and row.get("positive_bid_size")
        and row.get("positive_reported_volume")
        and row.get("underlying_price_same_snapshot") is not None
        and bid is not None
        and Decimal(str(bid)) > 0
    )


def build_strategy_aligned_eod_option_scenario(
    base_scenario: dict[str, Any],
    plan: dict[str, Any],
    handoff: dict[str, Any],
    daily_cases: Sequence[DailyPathCase],
    *,
    policy: StrategyExitPolicy,
    safe_last_signal_session: date,
    read_verified_body: Callable[
        [dict[str, Any], dict[str, Any]],
        tuple[dict[str, Any], bytes, dict[str, Any]],
    ],
    expected_original_cases: int = 14902,
    decoded_cache: dict[str, list[dict[str, Any]]] | None = None,
    decoded_sha_cache: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Bind CALL entries to exact frozen stock exit sessions without exit lookahead."""
    for doc, field in (
        (base_scenario, "scenario_fingerprint"),
        (plan, "plan_fingerprint"),
        (handoff, "handoff_fingerprint"),
    ):
        _check_signature(doc, field)

    if (
        base_scenario.get("contract") != BASE_SCENARIO_CONTRACT
        or base_scenario.get("original_case_denominator") != expected_original_cases
        or len(base_scenario.get("cases", [])) != expected_original_cases
        or base_scenario.get("future_exit_used_for_entry_admission") is not False
        or base_scenario.get("provider_requests") != 0
        or base_scenario.get("protected_2026_outcomes_read") != 0
        or base_scenario.get("historical_fills_verified") != 0
        or base_scenario.get("historical_account_pnl_authority") is not False
        or plan.get("contract") != QUOTE_CONTRACT
        or handoff.get("contract") != HANDOFF_CONTRACT
        or base_scenario.get("quote_plan_fingerprint") != plan.get("plan_fingerprint")
        or base_scenario.get("handoff_fingerprint") != handoff.get("handoff_fingerprint")
        or handoff.get("quote_plan_fingerprint") != plan.get("plan_fingerprint")
        or handoff.get("provider_requests") != 0
        or handoff.get("protected_2026_outcomes_read") != 0
    ):
        raise StrategyAlignedEodReplayError(
            "strategy-aligned source lineage or authority changed"
        )

    case_by_id = {case["case_id"]: case for case in base_scenario["cases"]}
    handoff_by_id = {row["case_right_id"]: row for row in handoff["rows"]}
    request_by_id = {row["request_identity"]: row for row in plan["requests"]}
    daily_by_id = {case.opportunity.opportunity_id: case for case in daily_cases}
    if (
        len(case_by_id) != expected_original_cases
        or len(handoff_by_id) != handoff.get("original_right_memberships")
        or len(request_by_id) != plan.get("unique_physical_quote_queries")
        or len(daily_by_id) != len(daily_cases)
        or not set(daily_by_id).issubset(case_by_id)
    ):
        raise StrategyAlignedEodReplayError("strategy-aligned denominator changed")

    decoded = decoded_cache if decoded_cache is not None else {}
    decoded_sha = decoded_sha_cache if decoded_sha_cache is not None else {}
    counts: Counter[str] = Counter()
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    output_cases: list[dict[str, Any]] = []

    for case in sorted(
        base_scenario["cases"],
        key=lambda item: (item["decision_at_utc"], item["case_id"]),
    ):
        cid = case["case_id"]
        year = case["year"]
        signal_day = date.fromisoformat(case["signal_session"])
        result: dict[str, Any] = {
            "case_id": cid,
            "year": year,
            "ticker": case["ticker"],
            "policy_id": case["policy_id"],
            "signal_session": case["signal_session"],
            "decision_at_utc": case["decision_at_utc"],
            "strategy_exit_policy": _policy_payload(policy),
            "economic_family_id": None,
            "selector_score": None,
            "stock_exit": None,
            "call": case.get("call"),
            "strategy_aligned_status": None,
            "strategy_exit_option_mark": None,
            "future_option_exit_used_for_entry_admission": False,
            "protected_2026_outcomes_read": 0,
        }

        if signal_day > safe_last_signal_session:
            status = "PROTECTED_2026_STOCK_HORIZON_WITHHELD"
        else:
            stock_case = daily_by_id.get(cid)
            if stock_case is None:
                status = "STOCK_EXIT_POLICY_INELIGIBLE_NO_PRIOR_PATH_EVIDENCE"
            else:
                item = stock_case.opportunity
                result["economic_family_id"] = item.economic_family_id
                result["selector_score"] = item.selector_score
                resolved = resolve_daily_exit(
                    stock_case,
                    stop_fraction=policy.stop_fraction,
                    target_fraction=policy.target_fraction,
                )
                if resolved.exit_session_date >= PROTECTED_2026_START:
                    raise StrategyAlignedEodReplayError(
                        "stock exit resolution crossed protected 2026 boundary"
                    )
                result["stock_exit"] = {
                    "disposition": resolved.disposition,
                    "session_offset": resolved.exit_session_offset,
                    "session_et": resolved.exit_session_date.isoformat(),
                    "stock_exit_price_per_unit": str(resolved.exit_price_per_unit),
                    "same_session_collision": resolved.same_session_collision,
                    "gap_through_stop": resolved.gap_through_stop,
                    "gap_through_target": resolved.gap_through_target,
                }

                call = case.get("call")
                if call is None:
                    status = "NO_DATED_CALL_RIGHT"
                elif call.get("status") != "ENTRY_READY_MODELED_STANDARD_EOD":
                    status = "CALL_ENTRY_SOURCE_NOT_CAUSALLY_READY"
                else:
                    entry = call.get("entry")
                    if not isinstance(entry, dict):
                        raise StrategyAlignedEodReplayError(
                            "entry-ready CALL lost EOD entry"
                        )
                    entry_day = date.fromisoformat(entry["session_et"])
                    if resolved.exit_session_date <= entry_day:
                        status = "STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY"
                    else:
                        slot = handoff_by_id.get(call["case_right_id"])
                        if slot is None:
                            raise StrategyAlignedEodReplayError(
                                "strategy-aligned CALL lost handoff slot"
                            )
                        request = request_by_id.get(slot.get("quote_request_identity"))
                        if request is None:
                            raise StrategyAlignedEodReplayError(
                                "strategy-aligned CALL lost selected quote request"
                            )
                        source_id = slot.get("quote_source_request_identity")
                        body_sha = slot.get("quote_body_sha256")
                        if (
                            source_id != entry.get("physical_quote_request_identity")
                            or body_sha != entry.get("physical_quote_body_sha256")
                        ):
                            raise StrategyAlignedEodReplayError(
                                "strategy-aligned CALL physical source changed"
                            )
                        if source_id not in decoded:
                            source_ticket, raw, receipt = read_verified_body(
                                request, slot
                            )
                            if (
                                source_ticket.get("request_identity") != source_id
                                or receipt.get("body_sha256") != body_sha
                                or receipt.get("safe_summary", {}).get("observed_rows")
                                    != slot.get("observed_quote_rows")
                            ):
                                raise StrategyAlignedEodReplayError(
                                    "strategy-aligned physical receipt changed"
                                )
                            decoded[source_id] = _decode_snapshot_rows(
                                raw,
                                source_ticket,
                                slot["observed_quote_rows"],
                            )
                            decoded_sha[source_id] = body_sha
                        elif decoded_sha[source_id] != body_sha:
                            raise StrategyAlignedEodReplayError(
                                "shared strategy-aligned source SHA changed"
                            )

                        selected_from = date.fromisoformat(request["from_inclusive"])
                        selected_to = date.fromisoformat(request["to_exclusive"])
                        exit_day = resolved.exit_session_date
                        if not selected_from <= exit_day < selected_to:
                            status = "STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW"
                        else:
                            exact = [
                                row
                                for row in decoded[source_id]
                                if row["session_et"] == exit_day.isoformat()
                            ]
                            if len(exact) > 1:
                                raise StrategyAlignedEodReplayError(
                                    "duplicate option rows on exact strategy exit session"
                                )
                            if not exact:
                                status = "STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING"
                            elif not _exit_row_qualified(exact[0]):
                                status = "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP"
                                result["strategy_exit_option_mark"] = {
                                    "session_et": exact[0]["session_et"],
                                    "updated_at_utc": exact[0]["updated_at_utc"],
                                    "bid_per_share": exact[0]["bid"],
                                    "two_sided": exact[0]["two_sided"],
                                    "positive_bid_size": exact[0]["positive_bid_size"],
                                    "positive_reported_volume":
                                        exact[0]["positive_reported_volume"],
                                }
                            else:
                                status = "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"
                                result["strategy_exit_option_mark"] = {
                                    "session_et": exact[0]["session_et"],
                                    "updated_at_utc": exact[0]["updated_at_utc"],
                                    "bid_per_share": exact[0]["bid"],
                                    "displayed_bid_size_contracts":
                                        exact[0]["bid_size_contracts"],
                                    "reported_volume_contracts":
                                        exact[0]["reported_volume_contracts"],
                                    "underlying_price_same_snapshot":
                                        exact[0]["underlying_price_same_snapshot"],
                                    "two_sided": True,
                                    "positive_bid_size": True,
                                    "positive_reported_volume": True,
                                }

        result["strategy_aligned_status"] = status
        counts[status] += 1
        by_year[year][status] += 1
        output_cases.append(result)

    if len(output_cases) != expected_original_cases:
        raise StrategyAlignedEodReplayError(
            "strategy-aligned full denominator changed"
        )

    report = {
        "contract": SCENARIO_CONTRACT,
        "status": "MODELED_STRATEGY_ALIGNED_EOD_CALL_SCENARIO_NO_FILL_AUTHORITY",
        "base_scenario_fingerprint": base_scenario["scenario_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "safe_last_signal_session": safe_last_signal_session.isoformat(),
        "strategy_exit_policy": _policy_payload(policy),
        "usable_stock_exit_policy_cases": len(daily_cases),
        "source_ready_strategy_aligned_round_trips":
            counts["STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY"],
        "entry_ready_but_exact_strategy_exit_source_gap": (
            counts["STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING"]
            + counts["STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP"]
            + counts["STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW"]
        ),
        "stock_exit_not_after_option_eod_entry":
            counts["STOCK_EXIT_NOT_AFTER_OPTION_EOD_ENTRY"],
        "protected_2026_stock_horizon_withheld":
            counts["PROTECTED_2026_STOCK_HORIZON_WITHHELD"],
        "unique_physical_quote_histories_decoded": len(decoded),
        "future_option_exit_used_for_entry_admission": False,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "by_status": dict(sorted(counts.items())),
        "by_year": {
            year: dict(sorted(counter.items()))
            for year, counter in by_year.items()
        },
        "cases": output_cases,
    }
    report["scenario_fingerprint"] = _fingerprint(report)
    return report


def replay_strategy_aligned_eod_call_account(
    scenario: dict[str, Any],
    *,
    policy: ReplayPolicy | None = None,
    max_positions_per_family: int = 3,
    one_active_position_per_ticker: bool = True,
    expected_scenario_contract: str = SCENARIO_CONTRACT,
    replay_contract: str = CONTRACT,
) -> dict[str, Any]:
    """Replay CALL entries with exact frozen strategy-exit attempts."""
    _check_signature(scenario, "scenario_fingerprint")
    if (
        scenario.get("contract") != expected_scenario_contract
        or scenario.get("future_option_exit_used_for_entry_admission") is not False
        or scenario.get("provider_requests") != 0
        or scenario.get("protected_2026_outcomes_read") != 0
        or scenario.get("historical_fills_verified") != 0
        or scenario.get("historical_account_pnl_authority") is not False
        or scenario.get("strategy_evidence_authority") is not False
    ):
        raise StrategyAlignedEodReplayError("strategy-aligned scenario authority changed")
    if type(max_positions_per_family) is not int or max_positions_per_family < 1:
        raise StrategyAlignedEodReplayError("max_positions_per_family invalid")
    if type(one_active_position_per_ticker) is not bool:
        raise StrategyAlignedEodReplayError("ticker constraint invalid")

    policy = policy or ReplayPolicy(max_open_positions=10)
    policy.validate()
    cash = _decimal(policy.initial_cash, "initial cash")
    initial_cash = cash
    reserved_exit_fees = Decimal("0.00")
    fee_in = _money(
        _decimal(
            policy.option_entry_fee_per_contract,
            "option entry fee",
            allow_zero=True,
        )
    )
    fee_out = _money(
        _decimal(
            policy.option_exit_fee_per_contract,
            "option exit fee",
            allow_zero=True,
        )
    )
    slip = _decimal(
        policy.option_slippage_per_share,
        "option slippage",
        allow_zero=True,
    )

    case_by_id = {case["case_id"]: case for case in scenario["cases"]}
    if len(case_by_id) != scenario["original_case_denominator"]:
        raise StrategyAlignedEodReplayError("strategy account case identities changed")

    decisions: dict[str, dict[str, Any]] = {}
    positions: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    events: list[tuple[datetime, int, float, str, str]] = []
    rejections: Counter[str] = Counter()
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    peak_positions = 0

    calendar = get_market_calendar()
    for case in scenario["cases"]:
        cid = case["case_id"]
        status = case["strategy_aligned_status"]
        row = {
            "case_id": cid,
            "year": case["year"],
            "ticker": case["ticker"],
            "economic_family_id": case.get("economic_family_id"),
            "strategy_aligned_status": status,
            "account_status": status,
            "contracts": 0,
            "modeled_net_pnl": None,
            "entry_at_utc": None,
            "exit_at_utc": None,
        }
        decisions[cid] = row
        if status not in {
            "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY",
            "STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING",
            "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP",
            "STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW",
        }:
            continue
        call = case.get("call")
        stock_exit = case.get("stock_exit")
        if (
            not isinstance(call, dict)
            or call.get("status") != "ENTRY_READY_MODELED_STANDARD_EOD"
            or not isinstance(call.get("entry"), dict)
            or not isinstance(stock_exit, dict)
        ):
            raise StrategyAlignedEodReplayError(
                "account-ready strategy case lost CALL/stock exit"
            )
        entry_at = _aware(call["entry"]["at_utc"], "strategy CALL entry")
        exit_day = date.fromisoformat(stock_exit["session_et"])
        _, strategy_close = calendar.regular_open_close(exit_day)
        if strategy_close <= entry_at:
            raise StrategyAlignedEodReplayError(
                "strategy exit attempt is not after option entry"
            )
        score = float(case.get("selector_score") or 0.0)
        events.append((entry_at, 1, -score, cid, "ENTRY"))
        events.append((strategy_close.astimezone(UTC), 0, -score, cid, "EXIT_ATTEMPT"))

    for at, priority, _tie, cid, kind in sorted(events):
        case = case_by_id[cid]
        row = decisions[cid]
        call = case["call"]

        if kind == "ENTRY":
            active_family = sum(
                position["economic_family_id"] == case["economic_family_id"]
                for position in positions.values()
            )
            if len(positions) >= policy.max_open_positions:
                row["account_status"] = "MAX_CONCURRENT_POSITIONS_REACHED"
                rejections["MAX_CONCURRENT_POSITIONS_REACHED"] += 1
                continue
            if active_family >= max_positions_per_family:
                row["account_status"] = "MAX_POSITIONS_PER_FAMILY_REACHED"
                rejections["MAX_POSITIONS_PER_FAMILY_REACHED"] += 1
                continue
            if one_active_position_per_ticker and any(
                position["ticker"] == case["ticker"]
                for position in positions.values()
            ):
                row["account_status"] = "ACTIVE_TICKER_ALREADY_PRESENT"
                rejections["ACTIVE_TICKER_ALREADY_PRESENT"] += 1
                continue

            ask = _decimal(call["entry"]["ask_per_share"], "strategy CALL ask")
            unit_debit = _money((ask + slip) * Decimal(100))
            available = _money(cash - reserved_exit_fees)
            budget = _money(
                available
                * _decimal(
                    policy.fraction_of_available_cash,
                    "allocation fraction",
                )
            )
            per_unit_liquidity = unit_debit + fee_in + fee_out
            units = min(
                policy.maximum_units_per_position,
                int(min(available, budget) // per_unit_liquidity),
            )
            if units < 1:
                row["account_status"] = "INSUFFICIENT_CASH_FOR_ONE_CONTRACT"
                rejections["INSUFFICIENT_CASH_FOR_ONE_CONTRACT"] += 1
                continue

            cost = (unit_debit + fee_in) * units
            reserve = fee_out * units
            cash = _money(cash - cost)
            reserved_exit_fees = _money(reserved_exit_fees + reserve)
            if cash < reserved_exit_fees:
                raise StrategyAlignedEodReplayError("strategy account overdraft")
            positions[cid] = {
                "ticker": case["ticker"],
                "economic_family_id": case["economic_family_id"],
                "symbol": call["option_symbol"],
                "contracts": units,
                "entry_debit": cost,
                "reserved_exit_fee": reserve,
                "entry_at": at,
            }
            row["account_status"] = "OPEN_AWAITING_STRATEGY_EXIT_ATTEMPT"
            row["contracts"] = units
            row["entry_at_utc"] = at.isoformat()
            peak_positions = max(peak_positions, len(positions))
            ledger.append({
                "kind": "MODELED_STRATEGY_ALIGNED_EOD_ENTRY",
                "case_id": cid,
                "at_utc": at.isoformat(),
                "instrument": call["option_symbol"],
                "contracts": units,
                "ask_per_share": str(ask),
                "cash_delta": str(-cost),
                "cash_after": str(cash),
                "exit_fees_reserved": str(reserved_exit_fees),
            })
            continue

        position = positions.get(cid)
        if position is None:
            continue
        mark = case.get("strategy_exit_option_mark")
        if case["strategy_aligned_status"] != "STRATEGY_ALIGNED_EOD_ROUND_TRIP_SOURCE_READY":
            row["account_status"] = "OPEN_UNRESOLVED_EXACT_STRATEGY_EXIT_SOURCE_GAP"
            ledger.append({
                "kind": "MODELED_STRATEGY_EXIT_ATTEMPT_UNRESOLVED",
                "case_id": cid,
                "at_utc": at.isoformat(),
                "instrument": position["symbol"],
                "reason": case["strategy_aligned_status"],
                "cash_after": str(cash),
                "exit_fees_reserved": str(reserved_exit_fees),
            })
            continue
        if not isinstance(mark, dict):
            raise StrategyAlignedEodReplayError(
                "source-ready strategy exit lost option mark"
            )
        bid = _decimal(mark["bid_per_share"], "strategy CALL bid")
        unit_credit = _money(max(Decimal("0"), bid - slip) * Decimal(100))
        proceeds = (unit_credit - fee_out) * position["contracts"]
        cash = _money(cash + proceeds)
        reserved_exit_fees = _money(
            reserved_exit_fees - position["reserved_exit_fee"]
        )
        pnl = _money(proceeds - position["entry_debit"])
        del positions[cid]
        row["account_status"] = "MODELED_STRATEGY_ALIGNED_EOD_ROUND_TRIP"
        row["modeled_net_pnl"] = str(pnl)
        row["exit_at_utc"] = at.isoformat()
        ledger.append({
            "kind": "MODELED_STRATEGY_ALIGNED_EOD_EXIT",
            "case_id": cid,
            "at_utc": at.isoformat(),
            "instrument": position["symbol"],
            "contracts": position["contracts"],
            "bid_per_share": str(bid),
            "cash_delta": str(proceeds),
            "cash_after": str(cash),
            "exit_fees_reserved": str(reserved_exit_fees),
            "modeled_net_pnl": str(pnl),
        })

    if reserved_exit_fees != sum(
        (position["reserved_exit_fee"] for position in positions.values()),
        Decimal("0"),
    ):
        raise StrategyAlignedEodReplayError(
            "strategy account ending fee reserve does not reconcile"
        )

    ordered = [
        decisions[case["case_id"]]
        for case in scenario["cases"]
    ]
    for row in ordered:
        by_year[row["year"]][row["account_status"]] += 1
    completed = [
        row
        for row in ordered
        if row["account_status"] == "MODELED_STRATEGY_ALIGNED_EOD_ROUND_TRIP"
    ]
    realized = sum(
        (Decimal(row["modeled_net_pnl"]) for row in completed),
        Decimal("0"),
    )
    ending_equity = str(cash) if not positions else None

    report = {
        "contract": replay_contract,
        "status": "MODELED_STRATEGY_ALIGNED_EOD_CALL_ACCOUNT_NO_FILL_AUTHORITY",
        "scenario_fingerprint": scenario["scenario_fingerprint"],
        "strategy_exit_policy": scenario["strategy_exit_policy"],
        "option_exit_timing_interpretation": (
            "EOD_BID_ON_STOCK_STRATEGY_EXIT_SESSION; "
            "NOT_INTRADAY_STOP_OR_TARGET_TOUCH_TIME"
        ),
        "original_case_denominator": scenario["original_case_denominator"],
        "safe_last_signal_session": scenario["safe_last_signal_session"],
        "policy": {
            name: getattr(policy, name)
            for name in policy.__dataclass_fields__
        },
        "max_positions_per_family": max_positions_per_family,
        "one_active_position_per_ticker": one_active_position_per_ticker,
        "source_ready_strategy_aligned_round_trips":
            scenario["source_ready_strategy_aligned_round_trips"],
        "admitted_positions": sum(row["contracts"] > 0 for row in ordered),
        "completed_round_trips": len(completed),
        "end_open_positions": len(positions),
        "peak_open_positions": peak_positions,
        "initial_cash": str(initial_cash),
        "ending_cash": str(cash),
        "ending_equity": ending_equity,
        "modeled_realized_pnl": str(_money(realized)),
        "modeled_cash_change": str(_money(cash - initial_cash)),
        "modeled_total_return_if_fully_closed": (
            str(
                ((cash - initial_cash) / initial_cash).quantize(
                    Decimal("0.00000001")
                )
            )
            if not positions else None
        ),
        "ending_reserved_exit_fees": str(reserved_exit_fees),
        "rejections": dict(sorted(rejections.items())),
        "open_positions": [
            {
                "case_id": cid,
                "ticker": position["ticker"],
                "economic_family_id": position["economic_family_id"],
                "symbol": position["symbol"],
                "contracts": position["contracts"],
                "entry_debit": str(position["entry_debit"]),
                "entry_at_utc": position["entry_at"].isoformat(),
                "reserved_exit_fee": str(position["reserved_exit_fee"]),
                "terminal_market_mark": None,
                "unrealized_pnl": None,
            }
            for cid, position in sorted(positions.items())
        ],
        "by_year": {
            year: {
                "original_cases": sum(counter.values()),
                "statuses": dict(sorted(counter.items())),
            }
            for year, counter in by_year.items()
        },
        "decisions": ordered,
        "ledger": ledger,
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "future_option_exit_used_for_entry_admission": False,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "strategy_evidence_authority": False,
        "paper": False,
        "live": False,
    }
    report["replay_fingerprint"] = _fingerprint(report)
    return report


def persist_strategy_aligned_scenario(
    settings: AtlasSettings,
    report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "scenario_fingerprint")
    policy = report["strategy_exit_policy"]["policy_id"].lower()
    path = settings.resolved_path(
        f"{SCENARIO_REL}_{policy}_{report['scenario_fingerprint'][:16]}.json"
    )
    return _persist(path, report, "STRATEGY_ALIGNED_EOD_OPTION_SCENARIO")


def persist_strategy_aligned_replay(
    settings: AtlasSettings,
    report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "replay_fingerprint")
    policy = report["strategy_exit_policy"]["policy_id"].lower()
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{policy}_{report['replay_fingerprint'][:16]}.json"
    )
    return _persist(path, report, "STRATEGY_ALIGNED_EOD_OPTION_REPLAY")


def _persist(
    path: Path,
    value: dict[str, Any],
    label: str,
) -> tuple[Path, str]:
    import json

    raw = json.dumps(value, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise StrategyAlignedEodReplayError(f"existing {label} path invalid")
        if path.read_text(encoding="utf-8") != raw:
            raise StrategyAlignedEodReplayError(f"immutable {label} differs")
        return path, "REUSED_IMMUTABLE_" + label
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(raw)
        handle.flush()
    return path, "WRITTEN_IMMUTABLE_" + label
