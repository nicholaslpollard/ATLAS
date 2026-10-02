from __future__ import annotations

"""Receipt-bound modeled historical EOD long-option account replay.

This is a separate historical adapter and replay path. It does not weaken or
reuse the synthetic fixture origin gate in multiyear_offline_account_replay_v1.

The replay is deliberately labeled MODELED:
- entries use the first causal-entry-ready MarketData 16:00 ET ask;
- the contract multiplier is the provider-standard 100-share model assumption
  established by the signed admission audit, not independent OCC deliverable proof;
- after entry, the exit policy attempts to sell at the first subsequent SHA-verified
  MarketData 16:00 ET bid with two-sided quote, displayed bid size >= 1 and positive
  reported volume, strictly before expiration and no later than 2025-12-31;
- future exit availability never decides whether an earlier entry is admitted;
- unresolved exits remain open/unmarked and consume cash/position capacity.

No provider requests, PAPER/LIVE authority, protected-2026 outcome reads or claim of
historically executable fills is created.
"""

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
import re
from typing import Any, Callable, Literal
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_marketdata_eod_clock_liquidity_probe_v1 import (
    _decode_snapshot_rows,
)
from packages.data.multiyear_marketdata_eod_standard_contract_admission_v1 import (
    CONTRACT as ADMISSION_CONTRACT,
)
from packages.data.multiyear_native_stock_open_v1 import (
    CONTRACT as NATIVE_CONTRACT,
    NATIVE_FP,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_offline_account_replay_v1 import (
    ReplayPolicy,
    _decimal,
    _money,
)

CONTRACT = "atlas-multiyear-historical-eod-option-account-replay-v1"
SCENARIO_CONTRACT = "atlas-multiyear-historical-eod-option-scenario-v1"
OUTPUT_REL = "data/options/derived/multiyear_historical_eod_option_account_replay_v1"
SCENARIO_REL = "data/options/derived/multiyear_historical_eod_option_scenario_v1"
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
MODES = ("CALL", "PUT")
Mode = Literal["CALL", "PUT"]
PROTECTED_2026_START = date(2026, 1, 1)


class HistoricalEodReplayError(ValueError):
    pass


def _aware(value: str, label: str) -> datetime:
    if not isinstance(value, str):
        raise HistoricalEodReplayError(f"{label} must be ISO text")
    stamp = datetime.fromisoformat(value)
    if stamp.tzinfo is None:
        raise HistoricalEodReplayError(f"{label} must be timezone-aware")
    return stamp.astimezone(UTC)


def _expiry(symbol: str, expected: str) -> date:
    match = OCC.fullmatch(symbol)
    if match is None:
        raise HistoricalEodReplayError("invalid selected OCC symbol")
    compact = match.group(2)
    parsed = date(2000 + int(compact[:2]), int(compact[2:4]), int(compact[4:6]))
    if parsed.isoformat() != expected:
        raise HistoricalEodReplayError("selected OCC expiration changed")
    return parsed


def _right_letter(right: str) -> str:
    if right == "call":
        return "C"
    if right == "put":
        return "P"
    raise HistoricalEodReplayError("unexpected option right")


def build_historical_eod_option_scenario(
    native: dict[str, Any],
    plan: dict[str, Any],
    handoff: dict[str, Any],
    admission: dict[str, Any],
    *,
    read_verified_body: Callable[
        [dict[str, Any], dict[str, Any]],
        tuple[dict[str, Any], bytes, dict[str, Any]],
    ],
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Build causal entry legs and resolve exits only after their entry timestamp."""
    for doc, field in (
        (native, "source_fingerprint"),
        (plan, "plan_fingerprint"),
        (handoff, "handoff_fingerprint"),
        (admission, "audit_fingerprint"),
    ):
        _check_signature(doc, field)

    if (
        native.get("contract") != NATIVE_CONTRACT
        or native.get("source_fingerprint") != NATIVE_FP
        or native.get("case_denominator") != expected_original_cases
        or len(native.get("rows", [])) != expected_original_cases
        or native.get("protected_outcomes_read") != 0
        or admission.get("contract") != ADMISSION_CONTRACT
        or admission.get("original_case_denominator") != expected_original_cases
        or admission.get("original_right_memberships") != expected_original_cases * 2
        or admission.get("future_exit_used_for_entry_admission") is not False
        or admission.get("provider_requests") != 0
        or admission.get("historical_option_trades_admitted") != 0
        or admission.get("historical_account_pnl_authority") is not False
        or admission.get("provider_standard_100_share_multiplier_is_model_assumption")
            is not True
        or handoff.get("original_case_denominator") != expected_original_cases
        or handoff.get("original_right_memberships") != expected_original_cases * 2
        or handoff.get("quote_plan_fingerprint") != plan.get("plan_fingerprint")
        or handoff.get("provider_requests") != 0
    ):
        raise HistoricalEodReplayError("historical EOD source lineage or authority changed")

    native_by_id = {row["case_id"]: row for row in native["rows"]}
    handoff_by_id = {row["case_right_id"]: row for row in handoff["rows"]}
    admission_by_id = {row["case_right_id"]: row for row in admission["rows"]}
    requests = {row["request_identity"]: row for row in plan["requests"]}
    if (
        len(native_by_id) != expected_original_cases
        or len(handoff_by_id) != expected_original_cases * 2
        or len(admission_by_id) != admission["dated_pair_work_items"]
        or len(requests) != plan["unique_physical_quote_queries"]
    ):
        raise HistoricalEodReplayError("historical EOD source denominator changed")

    decoded: dict[str, list[dict[str, Any]]] = {}
    decoded_sha: dict[str, str] = {}
    leg_rows: dict[str, dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    years: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }

    for case_right_id, row in sorted(admission_by_id.items()):
        if row.get("provider_standard_chain_classification") is not True:
            raise HistoricalEodReplayError("admission lost provider-standard classification")
        status = (
            "ENTRY_READY_MODELED_STANDARD_EOD"
            if row.get("causal_entry_ready_model_source_shape") is True
            else "ENTRY_SOURCE_NOT_CAUSALLY_READY"
        )
        result: dict[str, Any] = {
            "case_right_id": case_right_id,
            "original_case_id": row["original_case_id"],
            "year": row["year"],
            "right": row["right"],
            "ticker": row["ticker"],
            "option_symbol": row["option_symbol"],
            "status": status,
            "entry": None,
            "resolved_exit": None,
            "exit_resolution": (
                "NOT_ATTEMPTED_ENTRY_NOT_READY"
                if status != "ENTRY_READY_MODELED_STANDARD_EOD"
                else "PENDING"
            ),
            "modeled_multiplier": 100,
            "independent_occ_deliverable_multiplier_verified": False,
            "provider_standard_multiplier_model_only": True,
            "protected_2026_outcomes_read": 0,
        }
        counts[status] += 1
        years[row["year"]][status] += 1

        if status == "ENTRY_READY_MODELED_STANDARD_EOD":
            slot = handoff_by_id.get(case_right_id)
            if slot is None:
                raise HistoricalEodReplayError("entry-ready right lost quote handoff")
            request_id = slot.get("quote_request_identity")
            request = requests.get(request_id)
            if request is None:
                raise HistoricalEodReplayError("entry-ready right lost quote request")
            source_id = slot.get("quote_source_request_identity")
            body_sha = slot.get("quote_body_sha256")
            if not isinstance(source_id, str) or not isinstance(body_sha, str):
                raise HistoricalEodReplayError("entry-ready right lost physical quote source")
            if source_id not in decoded:
                source_ticket, raw, receipt = read_verified_body(request, slot)
                if (
                    source_ticket.get("request_identity") != source_id
                    or receipt.get("body_sha256") != body_sha
                    or receipt.get("safe_summary", {}).get("observed_rows")
                        != slot.get("observed_quote_rows")
                ):
                    raise HistoricalEodReplayError("physical quote receipt/body changed")
                decoded[source_id] = _decode_snapshot_rows(
                    raw, source_ticket, slot["observed_quote_rows"]
                )
                decoded_sha[source_id] = body_sha
            elif decoded_sha[source_id] != body_sha:
                raise HistoricalEodReplayError("shared physical quote source SHA changed")

            entry = row.get("entry")
            if not isinstance(entry, dict):
                raise HistoricalEodReplayError("entry-ready right lost entry snapshot")
            entry_at = _aware(entry["snapshot_updated_at_utc"], "entry snapshot")
            entry_day = date.fromisoformat(entry["session_et"])
            expiration = _expiry(row["option_symbol"], row["expiration"])
            match = OCC.fullmatch(row["option_symbol"])
            if (
                match is None
                or match.group(1) != row["ticker"]
                or match.group(3) != _right_letter(row["right"])
                or entry_day >= expiration
                or entry_day >= PROTECTED_2026_START
                or entry.get("option_price_side") != "ASK"
                or entry.get("documented_same_row_stock_option_snapshot") is not True
                or entry.get("positive_displayed_size") is not True
                or entry.get("positive_reported_volume") is not True
                or entry.get("updated_is_1600_et") is not True
            ):
                raise HistoricalEodReplayError("causal entry source shape changed")
            entry_ask = _decimal(entry["option_price_per_share"], "entry ask")
            if entry_at.astimezone(EASTERN).date() != entry_day:
                raise HistoricalEodReplayError("entry timestamp/session mismatch")

            matches = [
                source_row
                for source_row in decoded[source_id]
                if source_row["session_et"] == entry_day.isoformat()
                and source_row["updated_at_utc"] == entry_at.isoformat()
                and source_row["ask"] is not None
                and Decimal(source_row["ask"]) == entry_ask
            ]
            if len(matches) != 1:
                raise HistoricalEodReplayError("entry snapshot no longer matches raw body")

            exits = []
            for source_row in decoded[source_id]:
                session = date.fromisoformat(source_row["session_et"])
                if not (entry_day < session < expiration):
                    continue
                if session >= PROTECTED_2026_START:
                    continue
                if (
                    source_row["updated_is_1600_et"]
                    and source_row["two_sided"]
                    and source_row["positive_bid_size"]
                    and source_row["positive_reported_volume"]
                    and source_row["underlying_price_same_snapshot"] is not None
                    and source_row["bid"] is not None
                    and Decimal(source_row["bid"]) > 0
                ):
                    exits.append(source_row)
            exits.sort(key=lambda item: (item["session_et"], item["updated_at_utc"]))
            resolved = exits[0] if exits else None

            result["entry"] = {
                "at_utc": entry_at.isoformat(),
                "session_et": entry_day.isoformat(),
                "ask_per_share": str(entry_ask),
                "displayed_ask_size_contracts": entry["displayed_size_contracts"],
                "reported_volume_contracts": entry["reported_volume_contracts"],
                "underlying_price_same_snapshot":
                    entry["underlying_price_same_snapshot"],
                "physical_quote_request_identity": source_id,
                "physical_quote_body_sha256": body_sha,
            }
            if resolved is None:
                result["exit_resolution"] = (
                    "NO_LATER_QUALIFIED_LIQUID_EOD_BID_BEFORE_EXPIRY_OR_2026"
                )
                counts["ENTRY_READY_NO_RESOLVED_EXIT"] += 1
                years[row["year"]]["ENTRY_READY_NO_RESOLVED_EXIT"] += 1
            else:
                exit_at = _aware(resolved["updated_at_utc"], "resolved exit")
                result["resolved_exit"] = {
                    "at_utc": exit_at.isoformat(),
                    "session_et": resolved["session_et"],
                    "bid_per_share": resolved["bid"],
                    "displayed_bid_size_contracts": resolved["bid_size_contracts"],
                    "reported_volume_contracts": resolved["reported_volume_contracts"],
                    "underlying_price_same_snapshot":
                        resolved["underlying_price_same_snapshot"],
                    "exit_policy":
                        "FIRST_SUBSEQUENT_QUALIFIED_LIQUID_EOD_BID_BEFORE_EXPIRY",
                }
                result["exit_resolution"] = "RESOLVED_FIRST_LATER_LIQUID_EOD_BID"
                counts["ENTRY_READY_RESOLVED_EXIT"] += 1
                years[row["year"]]["ENTRY_READY_RESOLVED_EXIT"] += 1
        leg_rows[case_right_id] = result

    cases: list[dict[str, Any]] = []
    for case_id, native_row in sorted(
        native_by_id.items(),
        key=lambda item: (
            item[1]["planned_option_decision_at_utc"],
            item[0],
        ),
    ):
        decision = _aware(
            native_row["planned_option_decision_at_utc"], "native decision"
        )
        if decision.astimezone(EASTERN).year not in range(2021, 2027):
            raise HistoricalEodReplayError("native decision year outside cohort")
        case = {
            "case_id": case_id,
            "year": native_row["signal_session"][:4],
            "ticker": native_row["ticker"],
            "policy_id": native_row["policy_id"],
            "signal_session": native_row["signal_session"],
            "decision_at_utc": decision.isoformat(),
            "call": leg_rows.get(f"{case_id}:C"),
            "put": leg_rows.get(f"{case_id}:P"),
        }
        cases.append(case)

    result = {
        "contract": SCENARIO_CONTRACT,
        "status": "MODELED_HISTORICAL_EOD_OPTION_SCENARIO_NO_FILL_AUTHORITY",
        "native_source_fingerprint": native["source_fingerprint"],
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "handoff_fingerprint": handoff["handoff_fingerprint"],
        "admission_audit_fingerprint": admission["audit_fingerprint"],
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": expected_original_cases * 2,
        "dated_rights": len(admission_by_id),
        "causal_entry_ready_rights":
            admission["causal_entry_ready_model_source_shape"],
        "entry_ready_resolved_exit_rights": counts["ENTRY_READY_RESOLVED_EXIT"],
        "entry_ready_unresolved_exit_rights":
            counts["ENTRY_READY_NO_RESOLVED_EXIT"],
        "unique_physical_quote_histories_decoded": len(decoded),
        "exit_policy":
            "FIRST_SUBSEQUENT_QUALIFIED_LIQUID_EOD_BID_BEFORE_EXPIRY",
        "provider_standard_100_share_multiplier_is_model_assumption": True,
        "independent_occ_deliverable_multiplier_verified": 0,
        "future_exit_used_for_entry_admission": False,
        "protected_2026_outcomes_read": 0,
        "provider_requests": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "by_year": {
            year: dict(sorted(counter.items()))
            for year, counter in years.items()
        },
        "cases": cases,
    }
    if (
        len(cases) != expected_original_cases
        or result["causal_entry_ready_rights"]
            != counts["ENTRY_READY_MODELED_STANDARD_EOD"]
        or result["entry_ready_resolved_exit_rights"]
            + result["entry_ready_unresolved_exit_rights"]
            != result["causal_entry_ready_rights"]
    ):
        raise HistoricalEodReplayError("scenario accounting changed")
    result["scenario_fingerprint"] = _fingerprint(result)
    return result


def _mode_leg(case: dict[str, Any], mode: Mode) -> dict[str, Any] | None:
    return case["call" if mode == "CALL" else "put"]


def replay_historical_eod_option_account(
    scenario: dict[str, Any],
    *,
    mode: Mode,
    policy: ReplayPolicy | None = None,
) -> dict[str, Any]:
    """Replay a modeled historical EOD CALL or PUT account without exit lookahead."""
    _check_signature(scenario, "scenario_fingerprint")
    if (
        scenario.get("contract") != SCENARIO_CONTRACT
        or scenario.get("future_exit_used_for_entry_admission") is not False
        or scenario.get("provider_standard_100_share_multiplier_is_model_assumption")
            is not True
        or scenario.get("independent_occ_deliverable_multiplier_verified") != 0
        or scenario.get("provider_requests") != 0
        or scenario.get("historical_fills_verified") != 0
        or scenario.get("historical_account_pnl_authority") is not False
        or scenario.get("protected_2026_outcomes_read") != 0
        or mode not in MODES
    ):
        raise HistoricalEodReplayError("scenario authority or mode changed")
    cases = scenario.get("cases")
    if (
        not isinstance(cases, list)
        or len(cases) != scenario.get("original_case_denominator")
        or len({row["case_id"] for row in cases}) != len(cases)
    ):
        raise HistoricalEodReplayError("scenario case denominator changed")

    policy = policy or ReplayPolicy()
    policy.validate()
    cash = _decimal(policy.initial_cash, "initial cash")
    initial_cash = cash
    reserved_exit_fees = Decimal("0.00")
    positions: dict[str, dict[str, Any]] = {}
    decisions: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    events: list[tuple[datetime, int, str, dict[str, Any]]] = []

    fee_in = _money(
        _decimal(policy.option_entry_fee_per_contract, "option entry fee", allow_zero=True)
    )
    fee_out = _money(
        _decimal(policy.option_exit_fee_per_contract, "option exit fee", allow_zero=True)
    )
    slip = _decimal(
        policy.option_slippage_per_share, "option slippage", allow_zero=True
    )

    for case in cases:
        cid = case["case_id"]
        leg = _mode_leg(case, mode)
        status = "NO_DATED_" + mode + "_RIGHT"
        if leg is not None:
            status = leg["status"]
            if status == "ENTRY_READY_MODELED_STANDARD_EOD":
                entry = leg["entry"]
                if not isinstance(entry, dict):
                    raise HistoricalEodReplayError("entry-ready leg lost entry")
                entry_at = _aware(entry["at_utc"], "account entry")
                decision = _aware(case["decision_at_utc"], "account decision")
                if entry_at <= decision:
                    raise HistoricalEodReplayError("modeled EOD entry not after decision")
                events.append((entry_at, 1, cid, leg))
                if leg["resolved_exit"] is not None:
                    exit_at = _aware(leg["resolved_exit"]["at_utc"], "account exit")
                    if exit_at <= entry_at:
                        raise HistoricalEodReplayError("modeled exit not after entry")
                    events.append((exit_at, 0, cid, leg))
                status = "ELIGIBLE_MODELED_EOD_ENTRY"
        decisions[cid] = {
            "case_id": cid,
            "year": case["year"],
            "ticker": case["ticker"],
            "policy_id": case["policy_id"],
            "mode": mode,
            "status": status,
            "units": 0,
            "modeled_net_pnl": None,
            "entry_at_utc": None,
            "exit_at_utc": None,
        }

    peak_positions = 0
    for at, priority, cid, leg in sorted(events, key=lambda e: (e[0], e[1], e[2])):
        row = decisions[cid]
        if priority == 1:
            if len(positions) >= policy.max_open_positions:
                row["status"] = "MAX_CONCURRENT_POSITIONS_REACHED"
                continue
            ask = _decimal(leg["entry"]["ask_per_share"], "historical EOD ask")
            unit_debit = _money((ask + slip) * Decimal(100))
            available = _money(cash - reserved_exit_fees)
            budget = _money(
                available
                * _decimal(policy.fraction_of_available_cash, "allocation fraction")
            )
            per_unit_liquidity = unit_debit + fee_in + fee_out
            units = min(
                policy.maximum_units_per_position,
                int(min(available, budget) // per_unit_liquidity),
            )
            if units < 1:
                row["status"] = "INSUFFICIENT_CASH_FOR_ONE_CONTRACT"
                continue
            cost = (unit_debit + fee_in) * units
            reserve = fee_out * units
            cash = _money(cash - cost)
            reserved_exit_fees = _money(reserved_exit_fees + reserve)
            if cash < reserved_exit_fees:
                raise HistoricalEodReplayError("modeled account overdraft")
            positions[cid] = {
                "units": units,
                "debit": cost,
                "reserved_exit_fee": reserve,
                "symbol": leg["option_symbol"],
                "entry_at": at,
            }
            peak_positions = max(peak_positions, len(positions))
            row["status"] = (
                "OPEN_AWAITING_RESOLVED_EOD_EXIT"
                if leg["resolved_exit"] is not None
                else "OPEN_UNRESOLVED_NO_QUALIFIED_PREEXPIRY_EXIT"
            )
            row["units"] = units
            row["entry_at_utc"] = at.isoformat()
            ledger.append({
                "kind": "MODELED_HISTORICAL_EOD_ENTRY",
                "case_id": cid,
                "at_utc": at.isoformat(),
                "instrument": leg["option_symbol"],
                "contracts": units,
                "ask_per_share": str(ask),
                "multiplier_model": 100,
                "cash_delta": str(-cost),
                "cash_after": str(cash),
                "exit_fees_reserved": str(reserved_exit_fees),
            })
        elif cid in positions:
            position = positions.pop(cid)
            resolved = leg["resolved_exit"]
            if resolved is None:
                raise HistoricalEodReplayError("exit event lost resolved source")
            bid = _decimal(resolved["bid_per_share"], "historical EOD bid")
            unit_credit = _money(max(Decimal("0"), bid - slip) * Decimal(100))
            proceeds = (unit_credit - fee_out) * position["units"]
            cash = _money(cash + proceeds)
            reserved_exit_fees = _money(
                reserved_exit_fees - position["reserved_exit_fee"]
            )
            if reserved_exit_fees < 0 or cash < reserved_exit_fees:
                raise HistoricalEodReplayError("modeled exit cash/fee reconciliation failed")
            pnl = _money(proceeds - position["debit"])
            row["status"] = "MODELED_HISTORICAL_EOD_ROUND_TRIP"
            row["modeled_net_pnl"] = str(pnl)
            row["exit_at_utc"] = at.isoformat()
            ledger.append({
                "kind": "MODELED_HISTORICAL_EOD_EXIT",
                "case_id": cid,
                "at_utc": at.isoformat(),
                "instrument": leg["option_symbol"],
                "contracts": position["units"],
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
        raise HistoricalEodReplayError("ending exit-fee reserve does not reconcile")

    for case in cases:
        row = decisions[case["case_id"]]
        by_year[case["year"]][row["status"]] += 1

    ordered = [
        decisions[case["case_id"]]
        for case in sorted(
            cases,
            key=lambda item: (item["decision_at_utc"], item["case_id"]),
        )
    ]
    completed = [
        row for row in ordered
        if row["status"] == "MODELED_HISTORICAL_EOD_ROUND_TRIP"
    ]
    realized_pnl = sum(
        (Decimal(row["modeled_net_pnl"]) for row in completed),
        Decimal("0"),
    )
    ending_equity = str(cash) if not positions else None

    report = {
        "contract": CONTRACT,
        "status": "MODELED_HISTORICAL_EOD_ACCOUNT_REPLAY_NO_FILL_AUTHORITY",
        "scenario_fingerprint": scenario["scenario_fingerprint"],
        "mode": mode,
        "signal_direction_context": "ORIGINAL_ACCEPTED_DAILY_LONG_COHORT",
        "mode_interpretation": (
            "DIRECTION_ALIGNED_PRIMARY" if mode == "CALL"
            else "COUNTERFACTUAL_DIAGNOSTIC"
        ),
        "policy": {
            name: getattr(policy, name) for name in policy.__dataclass_fields__
        },
        "exit_policy": scenario["exit_policy"],
        "original_case_denominator": len(cases),
        "causal_entry_source_rights":
            sum(
                1 for case in cases
                if (_mode_leg(case, mode) or {}).get("status")
                    == "ENTRY_READY_MODELED_STANDARD_EOD"
            ),
        "admitted_positions":
            sum(row["units"] > 0 for row in ordered),
        "completed_round_trips": len(completed),
        "end_open_positions": len(positions),
        "peak_open_positions": peak_positions,
        "initial_cash": str(initial_cash),
        "ending_cash": str(cash),
        "ending_equity": ending_equity,
        "modeled_realized_pnl": str(_money(realized_pnl)),
        "modeled_cash_change": str(_money(cash - initial_cash)),
        "modeled_total_return_on_initial_cash_if_fully_closed": (
            str(_money((cash - initial_cash) / initial_cash))
            if not positions else None
        ),
        "ending_reserved_exit_fees": str(reserved_exit_fees),
        "open_positions": [
            {
                "case_id": cid,
                "symbol": position["symbol"],
                "contracts": position["units"],
                "entry_debit": str(position["debit"]),
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
        "future_exit_used_for_entry_admission": False,
        "provider_requests": 0,
        "historical_fills_verified": 0,
        "historical_account_pnl_authority": False,
        "protected_2026_outcomes_read": 0,
        "strategy_evidence_authority": False,
        "paper": False,
        "live": False,
    }
    report["replay_fingerprint"] = _fingerprint(report)
    return report


def persist_historical_eod_option_scenario(
    settings: AtlasSettings,
    scenario: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(scenario, "scenario_fingerprint")
    path = settings.resolved_path(
        f"{SCENARIO_REL}_{scenario['scenario_fingerprint'][:16]}.json"
    )
    return _persist(path, scenario, "HISTORICAL_EOD_OPTION_SCENARIO")


def persist_historical_eod_option_account_replay(
    settings: AtlasSettings,
    report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "replay_fingerprint")
    if (
        report.get("historical_account_pnl_authority") is not False
        or report.get("provider_requests") != 0
        or report.get("protected_2026_outcomes_read") != 0
        or report.get("strategy_evidence_authority") is not False
    ):
        raise HistoricalEodReplayError("replay authority changed")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['mode'].lower()}_{report['replay_fingerprint'][:16]}.json"
    )
    return _persist(path, report, "HISTORICAL_EOD_OPTION_ACCOUNT_REPLAY")


def _persist(
    path: Path, value: dict[str, Any], label: str,
) -> tuple[Path, str]:
    raw = (
        __import__("json").dumps(value, sort_keys=True, indent=2)
        + "\n"
    )
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise HistoricalEodReplayError(f"existing {label} path invalid")
        if path.read_text(encoding="utf-8") != raw:
            raise HistoricalEodReplayError(f"immutable {label} differs")
        return path, "REUSED_IMMUTABLE_" + label
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        handle.write(raw)
        handle.flush()
    return path, "WRITTEN_IMMUTABLE_" + label
