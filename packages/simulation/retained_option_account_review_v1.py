from __future__ import annotations

"""Read two named retained V2 reports; audit their ledger without replaying it.

No strategy resolution, raw quote/bar scan, provider request or settlement is
performed. Legacy filenames retain 16-character run identities; their complete
self-signatures and mutual linkage are checked, not treated as source acceptance.
"""

import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.core.market_calendar import get_market_calendar
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.multiyear_offline_account_replay_v1 import ReplayPolicy

CONTRACT = "atlas-retained-option-account-ledger-review-v1"
SCENARIO_CONTRACT = "atlas-multiyear-continuous-dynamic-exit-v2-option-scenario"
REPLAY_CONTRACT = "atlas-multiyear-continuous-dynamic-exit-v2-option-replay"
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_CASES = 20000
MAX_LEDGER_EVENTS = 60000
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
ENTRY = "MODELED_STRATEGY_ALIGNED_EOD_ENTRY"
EXIT = "MODELED_STRATEGY_ALIGNED_EOD_EXIT"
FAILED_EXIT = "MODELED_STRATEGY_EXIT_ATTEMPT_UNRESOLVED"
CLOSED = "MODELED_STRATEGY_ALIGNED_EOD_ROUND_TRIP"
OPEN = "OPEN_UNRESOLVED_EXACT_STRATEGY_EXIT_SOURCE_GAP"
REJECTIONS = {"MAX_CONCURRENT_POSITIONS_REACHED", "MAX_POSITIONS_PER_FAMILY_REACHED",
              "ACTIVE_TICKER_ALREADY_PRESENT", "INSUFFICIENT_CASH_FOR_ONE_CONTRACT"}
GAPS = {"STRATEGY_EXIT_SESSION_OPTION_SOURCE_MISSING", "STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP",
        "STRATEGY_EXIT_OUTSIDE_SELECTED_OPTION_WINDOW"}


class RetainedOptionAccountReviewError(ValueError):
    pass


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise RetainedOptionAccountReviewError(detail)


def _number(value: Any, label: str) -> Decimal:
    _require(isinstance(value, str) and 0 < len(value) <= 128 and value.strip() == value,
             f"{label} requires exact decimal text")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise RetainedOptionAccountReviewError(f"invalid {label}") from exc
    _require(result.is_finite() and abs(result) <= Decimal("1e12"), f"invalid {label}")
    return result


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _stamp(value: Any) -> datetime:
    _require(isinstance(value, str), "recorded clock requires ISO text")
    stamp = datetime.fromisoformat(value)
    _require(stamp.tzinfo is not None and stamp.utcoffset() is not None, "recorded clock must be aware")
    stamp = stamp.astimezone(UTC)
    _require(stamp.astimezone(EASTERN).year in range(2021, 2026), "ledger clock crosses permitted 2021-2025 scope")
    return stamp


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise RetainedOptionAccountReviewError(f"nonfinite JSON value: {value}")


@dataclass(frozen=True)
class RetainedOptionAccountBindingV1:
    replay_identity: str = "b525b49fabd0aead"
    scenario_identity: str = "03406fdf1def8233"
    original_cases: int = 14902
    source_ready_pairs: int = 2055
    admitted: int = 84
    completed: int = 74
    unresolved: int = 10
    ending_cash: str = "24997.70"
    realized_pnl: str = "-33365.40"
    policy: ReplayPolicy = ReplayPolicy(max_open_positions=10)

    @property
    def replay_relative_path(self) -> str:
        return f"data/options/derived/multiyear_continuous_dynamic_exit_v2_option_replay_{self.replay_identity}.json"

    @property
    def scenario_relative_path(self) -> str:
        return f"data/options/derived/multiyear_continuous_dynamic_exit_v2_option_scenario_{self.scenario_identity}.json"


DEFAULT_BINDING = RetainedOptionAccountBindingV1()


def _read_report(path: Path, *, field: str, identity: str) -> tuple[dict[str, Any], str]:
    _require(re.fullmatch(r"[0-9a-f]{16}|[0-9a-f]{64}", identity) is not None, "invalid retained run identity")
    _require(not path.is_symlink() and path.resolve().is_relative_to(path.parent.resolve()),
             f"retained artifact link is unsafe: {path}")
    _require(path.stat().st_size <= MAX_FILE_BYTES, f"retained artifact exceeds 64 MiB bound: {path}")
    with path.open("rb") as handle:
        raw = handle.read(MAX_FILE_BYTES + 1)
    _require(len(raw) <= MAX_FILE_BYTES, f"retained artifact grew beyond read bound: {path}")
    report = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    _require(isinstance(report, dict), f"retained report is not an object: {path}")
    unsigned = dict(report)
    fingerprint = unsigned.pop(field, None)
    _require(isinstance(fingerprint, str) and re.fullmatch(r"[0-9a-f]{64}", fingerprint) is not None,
             f"retained report signature absent: {path}")
    _require(fingerprint == _fingerprint(unsigned) and fingerprint.startswith(identity),
             f"retained report identity/signature drifted: {path}")
    return report, hashlib.sha256(raw).hexdigest()


def _scope(report: dict[str, Any], *, scenario: bool) -> None:
    expected_status = ("MODELED_CONTINUOUS_DYNAMIC_EXIT_V2_EOD_CALL_SCENARIO" if scenario
                       else "MODELED_STRATEGY_ALIGNED_EOD_CALL_ACCOUNT_NO_FILL_AUTHORITY")
    _require(report.get("contract") == (SCENARIO_CONTRACT if scenario else REPLAY_CONTRACT)
             and report.get("status") == expected_status, "retained report contract/status changed")
    for field in ("provider_requests", "protected_2026_outcomes_read", "historical_fills_verified",
                  "independent_occ_deliverable_multiplier_verified"):
        _require(type(report.get(field)) is int and report[field] == 0, f"retained scope drifted: {field}")
    for field in ("historical_account_pnl_authority", "strategy_evidence_authority",
                  "future_option_exit_used_for_entry_admission"):
        _require(report.get(field) is False, f"retained authority drifted: {field}")
    if not scenario:
        _require(report.get("paper") is False and report.get("live") is False, "retained trading authority changed")
    _require(report.get("provider_standard_100_share_multiplier_is_model_assumption") is True,
             "retained modeled deliverable assumption changed")


def review_retained_option_account(
    settings: AtlasSettings, *, binding: RetainedOptionAccountBindingV1 = DEFAULT_BINDING,
) -> dict[str, Any]:
    """Audit recorded cash/fees/populations; never execute the replay algorithm."""
    _require(type(binding.original_cases) is int and 1 <= binding.original_cases <= MAX_CASES,
             "retained population binding invalid")
    binding.policy.validate()
    replay, replay_sha = _read_report(settings.resolved_path(binding.replay_relative_path),
        field="replay_fingerprint", identity=binding.replay_identity)
    scenario, scenario_sha = _read_report(settings.resolved_path(binding.scenario_relative_path),
        field="scenario_fingerprint", identity=binding.scenario_identity)
    _scope(replay, scenario=False)
    _scope(scenario, scenario=True)
    _require(replay["scenario_fingerprint"] == scenario["scenario_fingerprint"], "account/scenario linkage drifted")
    _require(replay["strategy_exit_policy"] == scenario["strategy_exit_policy"], "account/scenario policy drifted")
    _require(replay["safe_last_signal_session"] == scenario["safe_last_signal_session"], "account/scenario cutoff drifted")
    _require(replay["strategy_exit_policy"].get("policy_id") == "CONTINUOUS_DYNAMIC_EXIT_V2", "retained exit version changed")
    _require(replay["policy"] == {name: getattr(binding.policy, name) for name in binding.policy.__dataclass_fields__},
             "retained cash/cost policy changed")
    _require(replay.get("one_active_position_per_ticker") is True and replay.get("max_positions_per_family") == 3,
             "retained admission constraints changed")
    for report in (replay, scenario):
        _require(report.get("original_case_denominator") == binding.original_cases, "retained denominator drifted")
        _require(report.get("source_ready_strategy_aligned_round_trips") == binding.source_ready_pairs,
                 "retained source-ready count drifted")
    cases, decisions, events, open_rows = (scenario.get("cases"), replay.get("decisions"),
                                          replay.get("ledger"), replay.get("open_positions"))
    _require(isinstance(cases, list) and len(cases) == binding.original_cases
             and isinstance(decisions, list) and len(decisions) == binding.original_cases,
             "case/decision population changed")
    _require(isinstance(events, list) and len(events) <= MAX_LEDGER_EVENTS and isinstance(open_rows, list),
             "bounded ledger/open-position arrays required")
    case_by_id = {row["case_id"]: row for row in cases}
    decision_by_id = {row["case_id"]: row for row in decisions}
    _require(len(case_by_id) == len(cases) and len(decision_by_id) == len(decisions)
             and set(case_by_id) == set(decision_by_id), "case identities missing/duplicated")
    statuses: Counter[str] = Counter()
    years: dict[str, Counter[str]] = {str(year): Counter() for year in range(2021, 2027)}
    for cid, row in decision_by_id.items():
        case = case_by_id[cid]
        _require(row["year"] in years and row["year"] == case["year"]
                 and row["ticker"] == case["ticker"]
                 and row["economic_family_id"] == case.get("economic_family_id")
                 and row["strategy_aligned_status"] == case["strategy_aligned_status"], "decision/scenario lineage drifted")
        _require(type(row["contracts"]) is int and row["contracts"] >= 0, "invalid recorded contract count")
        statuses[row["account_status"]] += 1
        years[row["year"]][row["account_status"]] += 1
    _require(replay["by_year"] == {year: {"original_cases": sum(counts.values()),
              "statuses": dict(sorted(counts.items()))} for year, counts in years.items()}, "annual account statuses do not reconcile")
    _require(replay["rejections"] == {key: statuses[key] for key in sorted(REJECTIONS) if statuses[key]},
             "rejection populations do not reconcile")
    _require(scenario["by_status"] == dict(sorted(Counter(row["strategy_aligned_status"] for row in cases).items())),
             "scenario status populations do not reconcile")
    fee_in = _money(_number(binding.policy.option_entry_fee_per_contract, "entry fee"))
    fee_out = _money(_number(binding.policy.option_exit_fee_per_contract, "exit fee"))
    slip = _number(binding.policy.option_slippage_per_share, "slippage")
    cash = _number(replay["initial_cash"], "initial cash")
    _require(cash == _number(binding.policy.initial_cash, "bound cash"), "initial cash drifted")
    fee_reserve = Decimal("0.00")
    active: dict[str, dict[str, Any]] = {}
    entered: dict[str, dict[str, Any]] = {}
    closed: dict[str, dict[str, Any]] = {}
    failed: dict[str, dict[str, Any]] = {}
    last_at: datetime | None = None
    realized = Decimal("0.00")
    peak = 0
    for event in events:
        cid, kind = event["case_id"], event["kind"]
        _require(cid in case_by_id, "ledger contains an unknown case")
        case, decision = case_by_id[cid], decision_by_id[cid]
        call = case.get("call")
        _require(isinstance(call, dict) and call.get("option_symbol") == event["instrument"],
                 "ledger lost exact CALL identity")
        at = _stamp(event["at_utc"])
        _require(last_at is None or last_at <= at, "ledger clocks are not chronological")
        last_at = at
        if kind == ENTRY:
            units = event["contracts"]
            _require(type(units) is int and 0 < units <= binding.policy.maximum_units_per_position and cid not in entered
                     and units == decision["contracts"], "duplicate/invalid recorded entry")
            _require(call.get("status") == "ENTRY_READY_MODELED_STANDARD_EOD", "ledger entry lost causal source admission")
            _require(at == _stamp(decision["entry_at_utc"]) == _stamp(call["entry"]["at_utc"]), "recorded entry clock drifted")
            ask = _number(event["ask_per_share"], "recorded ask")
            _require(ask > 0 and ask == _number(call["entry"]["ask_per_share"], "scenario ask"), "entry ask drifted")
            debit = (_money((ask + slip) * 100) + fee_in) * units
            _require(_number(event["cash_delta"], "entry delta") == -debit, "entry debit does not reconcile")
            entered[cid] = {"event": event, "debit": debit, "fee_reserve": fee_out * units}
            active[cid] = entered[cid]
            cash -= debit
            fee_reserve += fee_out * units
            peak = max(peak, len(active))
        elif kind == FAILED_EXIT:
            _require(cid in active and cid not in failed and case["strategy_aligned_status"] in GAPS,
                     "failed exit without an active source-gap position")
            _require(event["reason"] == case["strategy_aligned_status"] and decision["account_status"] == OPEN,
                     "unresolved exit reason drifted")
            _require("cash_delta" not in event or _number(event["cash_delta"], "failed exit delta") == 0,
                     "failed exit changed cash")
            failed[cid] = event
        elif kind == EXIT:
            _require(cid in active and cid not in closed and cid not in failed and decision["account_status"] == CLOSED,
                     "close without an active source-ready position")
            _require(at == _stamp(decision["exit_at_utc"]), "recorded close clock drifted")
            bid = _number(event["bid_per_share"], "recorded bid")
            _require(bid > 0 and bid == _number(case["strategy_exit_option_mark"]["bid_per_share"], "scenario bid")
                     and event["contracts"] == decision["contracts"], "recorded close price/units drifted")
            proceeds = (_money(max(Decimal(0), bid - slip) * 100) - fee_out) * event["contracts"]
            pnl = proceeds - active[cid]["debit"]
            _require(_number(event["cash_delta"], "exit delta") == proceeds
                     and _number(event["modeled_net_pnl"], "event P&L") == pnl
                     and _number(decision["modeled_net_pnl"], "decision P&L") == pnl,
                     "recorded exit cash/P&L does not reconcile")
            cash += proceeds
            fee_reserve -= active.pop(cid)["fee_reserve"]
            closed[cid] = event
            realized += pnl
        else:
            raise RetainedOptionAccountReviewError(f"unsupported retained ledger kind: {kind}")
        if kind in {FAILED_EXIT, EXIT}:
            exit_day = date.fromisoformat(case["stock_exit"]["session_et"])
            _require(exit_day.year in range(2021, 2026), "recorded stock exit crosses permitted scope")
            _, expected_close = get_market_calendar().regular_open_close(exit_day)
            _require(at == expected_close and at > _stamp(entered[cid]["event"]["at_utc"]),
                     "recorded exit attempt/close clock differs from original stock session")
        _require(_number(event["cash_after"], "cash after") == cash
                 and _number(event["exit_fees_reserved"], "fee reserve") == fee_reserve,
                 "ledger cash/fee running balances do not reconcile")
        _require(cash >= fee_reserve >= 0, "recorded cash/fee escrow invariant failed")
    _require(len(entered) == binding.admitted == replay["admitted_positions"]
             and len(closed) == binding.completed == replay["completed_round_trips"]
             and len(active) == binding.unresolved == replay["end_open_positions"] == len(open_rows),
             "admitted/completed/unresolved counts do not reconcile")
    _require(peak == replay["peak_open_positions"] <= binding.policy.max_open_positions, "peak position count drifted")
    _require(cash == _number(binding.ending_cash, "bound ending cash") == _number(replay["ending_cash"], "ending cash")
             and realized == _number(binding.realized_pnl, "bound realized P&L") == _number(replay["modeled_realized_pnl"], "realized P&L"),
             "retained terminal cash/P&L changed")
    _require(fee_reserve == _number(replay["ending_reserved_exit_fees"], "terminal fee reserve"), "ending fee reserve drifted")
    _require(_number(replay["modeled_cash_change"], "cash change") == cash - _number(replay["initial_cash"], "initial cash"),
             "reported cash change drifted")
    _require(replay["ending_equity"] is None and replay["modeled_total_return_if_fully_closed"] is None,
             "unresolved positions cannot become account equity or return")
    _require({cid for cid, row in decision_by_id.items() if row["contracts"] > 0} == set(entered)
             and {cid for cid, row in decision_by_id.items() if row["account_status"] == CLOSED} == set(closed)
             and {cid for cid, row in decision_by_id.items() if row["account_status"] == OPEN} == set(active),
             "decision/ledger membership mismatch")
    work_items = []
    seen_open = set()
    for row in open_rows:
        cid = row["case_id"]
        _require(cid in active and cid not in seen_open and cid in failed, "open position/failed attempt membership mismatch")
        seen_open.add(cid)
        case, decision, entry = case_by_id[cid], decision_by_id[cid], entered[cid]
        match = OCC.fullmatch(row["symbol"])
        _require(match is not None and match.group(3) == "C" and row["symbol"] == case["call"]["option_symbol"],
                 "unresolved OCC identity drifted")
        expiry = datetime.strptime(match.group(2), "%y%m%d").date()
        _require(row["contracts"] == decision["contracts"] and row["ticker"] == case["ticker"]
                 and row["economic_family_id"] == case["economic_family_id"]
                 and _stamp(row["entry_at_utc"]) == _stamp(entry["event"]["at_utc"])
                 and _number(row["entry_debit"], "open debit") == entry["debit"]
                 and _number(row["reserved_exit_fee"], "open exit fee") == entry["fee_reserve"],
                 "unresolved position economics drifted")
        _require(row["terminal_market_mark"] is None and row["unrealized_pnl"] is None
                 and decision["modeled_net_pnl"] is None, "unknown open economics became priced")
        work_items.append({
            "case_id": cid, "ticker": row["ticker"], "economic_family_id": row["economic_family_id"],
            "option_symbol": row["symbol"], "expiration": expiry.isoformat(),
            "contracts": row["contracts"], "entry_at_utc": row["entry_at_utc"],
            "recorded_failed_exit_at_utc": failed[cid]["at_utc"],
            "recorded_stock_exit": case["stock_exit"], "source_gap_reason": failed[cid]["reason"],
            "recorded_entry_source_binding": {key: case["call"]["entry"].get(key) for key in (
                "physical_quote_request_identity", "physical_quote_body_sha256",
            )},
            "committed_entry_cash_including_fee": row["entry_debit"],
            "reserved_exit_fee": row["reserved_exit_fee"], "terminal_market_mark": None,
            "required_evidence": ["EXACT_CONTRACT_DELIVERABLE_AND_CORPORATE_ACTION_LINEAGE",
                "QUALIFIED_ORIGINAL_EXIT_CLOCK_OBSERVATION_OR_EXPLICIT_ABSENCE",
                "EXPLICIT_TERMINAL_ACCOUNT_CLOCK", "EXERCISE_OR_EXPIRATION_OUTCOME",
                "APPLICABLE_HISTORICAL_SETTLEMENT_CYCLE_AND_CASH_SHARE_MOVEMENTS",
                "QUALIFIED_MARKS_FOR_ANY_SURVIVING_OR_DELIVERED_POSITIONS"],
            "retry_plan_created": False, "settlement_inferred": False, "capital_release_authority": False,
        })
    committed = sum((entry["debit"] for entry in active.values()), Decimal(0))
    _require(cash == _number(replay["initial_cash"], "initial cash") + realized - committed,
             "cash/realized P&L/open committed cash do not reconcile")
    report = {
        "contract": CONTRACT, "status": "COMPLETE_RETAINED_LEDGER_REVIEW_UNRESOLVED_EVIDENCE_DEMAND",
        "source_replay_fingerprint": replay["replay_fingerprint"], "source_scenario_fingerprint": scenario["scenario_fingerprint"],
        "source_replay_file_sha256": replay_sha, "source_scenario_file_sha256": scenario_sha,
        "source_identity_basis": "ORIGINAL_NAMED_RUN_PREFIX_FULL_SELF_SIGNATURE_AND_MUTUAL_LINKAGE",
        "original_cases": binding.original_cases, "admitted": len(entered), "completed": len(closed),
        "unresolved": len(active), "cash": str(_money(cash)), "modeled_realized_pnl": str(_money(realized)),
        "committed_open_entry_cash_including_fees": str(_money(committed)),
        "reserved_exit_fees": str(_money(fee_reserve)), "cash_available_after_exit_fee_reserve": str(_money(cash - fee_reserve)),
        "equity": None, "total_return": None, "terminal_valuation_clock": None,
        "account_status_counts": dict(sorted(statuses.items())), "rejections": replay["rejections"],
        "unresolved_by_reason": dict(sorted(Counter(item["source_gap_reason"] for item in work_items).items())),
        "unresolved_by_entry_year": dict(sorted(Counter(str(_stamp(item["entry_at_utc"]).astimezone(EASTERN).year) for item in work_items).items())),
        "unresolved_positions": sorted(work_items, key=lambda item: item["case_id"]),
        "provider_requests": 0, "broker_requests": 0, "raw_source_files_read": 0,
        "simulations_run": 0, "original_artifacts_modified": False, "source_reaccepted": False,
        "strategy_promotion": False, "historical_account_return_authority": False, "paper": False, "live": False,
    }
    report["report_fingerprint"] = _fingerprint(report)
    return report
