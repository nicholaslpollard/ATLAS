from __future__ import annotations

"""Offline proof probe for MarketData historical EOD option snapshot semantics.

This module reopens only already accepted, SHA-verified option quote bodies.  It
does not contact a provider and does not create historical trades or P&L.

MarketData's 2026-09 option quote documentation states that historical bid, ask,
volume and underlyingPrice are as of the row's `updated` quote-snapshot
timestamp, and that underlyingPrice is the last underlying-security price at the
time of that quote.  We freeze that documented semantic interpretation here so
ATLAS can measure how much of the historical execution-proof demand already has
same-row stock/option clock and conservative quote-side liquidity evidence.

Deliverable/multiplier proof remains explicitly absent.
"""

from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_demand_quote_cache_v1 import (
    CONTRACT as QUOTE_CONTRACT, _write_new,
)
from packages.data.multiyear_option_quote_reuse_handoff_v1 import (
    CONTRACT as HANDOFF_CONTRACT, _check_signature,
)
from packages.data.multiyear_verified_stock_option_source_casebook_v1 import (
    CONTRACT as CASEBOOK_CONTRACT,
)
from packages.providers.marketdata_app.client import array_rows
from packages.simulation.multiyear_historical_execution_requirements_v1 import (
    CONTRACT as PROOF_DEMAND_CONTRACT,
)

CONTRACT = "atlas-multiyear-marketdata-eod-clock-liquidity-probe-v1"
OUTPUT_REL = "data/options/derived/multiyear_marketdata_eod_clock_liquidity_probe_v1"
EASTERN = ZoneInfo("America/New_York")
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
ROUND_TRIP_FEE_PER_CONTRACT = "1.30"

PROVIDER_SEMANTICS = {
    "provider": "MarketData.app",
    "retrieved_on": "2026-10-01",
    "option_quotes_docs": "https://www.marketdata.app/docs/api/options/quotes/",
    "dates_times_docs": "https://www.marketdata.app/docs/api/dates-and-times/",
    "option_chain_docs": "https://www.marketdata.app/docs/api/options/chain/",
    "documented_claims": {
        "updated_is_quote_snapshot_time": True,
        "historical_bid_ask_volume_underlying_price_are_asof_updated": True,
        "underlying_price_is_last_underlying_price_at_quote_time": True,
        "historical_option_data_is_end_of_day": True,
        "historical_greeks_are_not_stored": True,
    },
}
PROVIDER_SEMANTICS_FINGERPRINT = _fingerprint(PROVIDER_SEMANTICS)


class MarketDataEodClockProbeError(ValueError):
    pass


def _number(value: Any, label: str, *, allow_zero: bool = True) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise MarketDataEodClockProbeError(f"{label} boolean")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MarketDataEodClockProbeError(f"{label} malformed") from exc
    if not number.is_finite() or number < 0 or (not allow_zero and number == 0):
        raise MarketDataEodClockProbeError(f"{label} invalid")
    return number


def _expiry(option_symbol: str) -> date:
    match = OCC.fullmatch(option_symbol)
    if match is None:
        raise MarketDataEodClockProbeError("invalid OCC option symbol")
    raw = match.group(2)
    try:
        return date(2000 + int(raw[:2]), int(raw[2:4]), int(raw[4:6]))
    except ValueError as exc:
        raise MarketDataEodClockProbeError("invalid OCC expiration") from exc


def _decode_snapshot_rows(
    raw: bytes, ticket: dict[str, Any], expected_rows: int,
) -> list[dict[str, Any]]:
    try:
        items = array_rows(json.loads(raw.decode("utf-8")))
    except (UnicodeDecodeError, ValueError, TypeError, KeyError) as exc:
        raise MarketDataEodClockProbeError(
            "accepted quote body cannot be decoded"
        ) from exc
    if len(items) != expected_rows:
        raise MarketDataEodClockProbeError("accepted quote body row count differs")
    start = date.fromisoformat(ticket["from_inclusive"])
    end = date.fromisoformat(ticket["to_exclusive"])
    rows: list[dict[str, Any]] = []
    seen: set[date] = set()
    for item in items:
        if item.get("optionSymbol") != ticket["option_symbol"]:
            raise MarketDataEodClockProbeError("accepted OCC symbol changed")
        updated = _number(item.get("updated"), "updated", allow_zero=False)
        if updated is None or updated != updated.to_integral_value():
            raise MarketDataEodClockProbeError("accepted updated timestamp malformed")
        stamp = datetime.fromtimestamp(int(updated), UTC)
        day = stamp.astimezone(EASTERN).date()
        if not start <= day < end or day in seen:
            raise MarketDataEodClockProbeError(
                "accepted quote session outside exact physical request"
            )
        seen.add(day)
        bid = _number(item.get("bid"), "bid")
        ask = _number(item.get("ask"), "ask")
        bid_size = _number(item.get("bidSize"), "bidSize")
        ask_size = _number(item.get("askSize"), "askSize")
        volume = _number(item.get("volume"), "volume")
        underlying = _number(
            item.get("underlyingPrice"), "underlyingPrice"
        )
        if underlying is not None and underlying == 0:
            # Existing source validation permits nonnegative provider fields.
            # A zero underlying mark is retained as an explicit missing-clock
            # condition rather than aborting unrelated valid rows.
            underlying = None
        two_sided = (
            bid is not None and ask is not None
            and bid > 0 and ask >= bid
        )
        if bid_size is not None and bid_size != bid_size.to_integral_value():
            raise MarketDataEodClockProbeError("bidSize is not an integer contract count")
        if ask_size is not None and ask_size != ask_size.to_integral_value():
            raise MarketDataEodClockProbeError("askSize is not an integer contract count")
        rows.append({
            "session_et": day.isoformat(),
            "updated_at_utc": stamp.isoformat(),
            "updated_at_et": stamp.astimezone(EASTERN).isoformat(),
            "option_symbol": ticket["option_symbol"],
            "bid": str(bid) if bid is not None else None,
            "ask": str(ask) if ask is not None else None,
            "bid_size_contracts": int(bid_size) if bid_size is not None else None,
            "ask_size_contracts": int(ask_size) if ask_size is not None else None,
            "reported_volume_contracts": str(volume) if volume is not None else None,
            "underlying_price_same_snapshot": (
                str(underlying) if underlying is not None else None
            ),
            "two_sided": two_sided,
            "positive_reported_volume": volume is not None and volume > 0,
            "positive_bid_size": bid_size is not None and bid_size >= 1,
            "positive_ask_size": ask_size is not None and ask_size >= 1,
            "updated_is_1600_et": (
                stamp.astimezone(EASTERN).hour == 16
                and stamp.astimezone(EASTERN).minute == 0
                and stamp.astimezone(EASTERN).second == 0
            ),
        })
    rows.sort(key=lambda row: (row["session_et"], row["updated_at_utc"]))
    return rows


def _mark_key(mark: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        mark["session_et"],
        mark["provider_updated_at_utc_not_publication_proof"],
        mark["source_bid_per_share_not_fill"],
        mark["source_ask_per_share_not_fill"],
    )


def _decoded_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        row["session_et"], row["updated_at_utc"], row["bid"], row["ask"],
    )


def _project_mark(row: dict[str, Any], *, side: str) -> dict[str, Any]:
    if side not in {"entry", "exit"}:
        raise MarketDataEodClockProbeError("unknown quote side")
    size_ok = (
        row["positive_ask_size"] if side == "entry"
        else row["positive_bid_size"]
    )
    price = row["ask"] if side == "entry" else row["bid"]
    return {
        "session_et": row["session_et"],
        "snapshot_updated_at_utc": row["updated_at_utc"],
        "snapshot_updated_at_et": row["updated_at_et"],
        "option_price_per_share": price,
        "option_price_side": "ASK" if side == "entry" else "BID",
        "displayed_size_contracts": (
            row["ask_size_contracts"] if side == "entry"
            else row["bid_size_contracts"]
        ),
        "reported_volume_contracts": row["reported_volume_contracts"],
        "underlying_price_same_snapshot": row["underlying_price_same_snapshot"],
        "two_sided": row["two_sided"],
        "positive_displayed_size": size_ok,
        "positive_reported_volume": row["positive_reported_volume"],
        "updated_is_1600_et": row["updated_is_1600_et"],
        "documented_same_row_stock_option_snapshot": (
            row["two_sided"]
            and row["underlying_price_same_snapshot"] is not None
        ),
    }


def build_marketdata_eod_clock_liquidity_probe(
    plan: dict[str, Any],
    handoff: dict[str, Any],
    casebook: dict[str, Any],
    proof_demand: dict[str, Any],
    *,
    read_verified_body: Callable[
        [dict[str, Any], dict[str, Any]],
        tuple[dict[str, Any], bytes, dict[str, Any]],
    ],
    expected_original_cases: int = 14902,
) -> dict[str, Any]:
    """Measure documentation-backed EOD clock/liquidity evidence; admit no trades."""
    for doc, field in (
        (plan, "plan_fingerprint"),
        (handoff, "handoff_fingerprint"),
        (casebook, "casebook_fingerprint"),
        (proof_demand, "proof_demand_fingerprint"),
    ):
        _check_signature(doc, field)
    if (
        plan.get("contract") != QUOTE_CONTRACT
        or handoff.get("contract") != HANDOFF_CONTRACT
        or casebook.get("contract") != CASEBOOK_CONTRACT
        or proof_demand.get("contract") != PROOF_DEMAND_CONTRACT
        or handoff.get("quote_plan_fingerprint") != plan["plan_fingerprint"]
        or casebook.get("handoff_fingerprint") != handoff["handoff_fingerprint"]
        or proof_demand.get("casebook_fingerprint") != casebook["casebook_fingerprint"]
        or handoff.get("provider_requests") != 0
        or casebook.get("provider_requests") != 0
        or proof_demand.get("provider_requests") != 0
        or handoff.get("portfolio_pnl_authority") is not False
        or casebook.get("account_pnl_authority") is not False
        or proof_demand.get("historical_account_pnl_authority") is not False
        or plan.get("requested_case_denominator")
            != handoff.get("selected_case_right_memberships")
        or proof_demand.get("original_case_denominator") != expected_original_cases
        or proof_demand.get("original_right_memberships") != expected_original_cases * 2
    ):
        raise MarketDataEodClockProbeError("source lineage or authority changed")

    requests = {x["request_identity"]: x for x in plan.get("requests", [])}
    handoff_rows = {
        x["case_right_id"]: x for x in handoff.get("rows", [])
    }
    casebook_rows = {
        x["case_right_id"]: x for x in casebook.get("rows", [])
    }
    work = proof_demand.get("rows")
    if (
        not isinstance(work, list)
        or len(work) != proof_demand.get("dated_pair_work_items")
        or len(handoff_rows) != expected_original_cases * 2
        or len(casebook_rows) != expected_original_cases * 2
        or len(requests) != plan.get("unique_physical_quote_queries")
    ):
        raise MarketDataEodClockProbeError("source denominator changed")

    decoded: dict[str, dict[tuple[str, str, str, str], dict[str, Any]]] = {}
    decoded_body_sha: dict[str, str] = {}
    output_rows: list[dict[str, Any]] = []
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    counts: Counter[str] = Counter()

    for proof in sorted(work, key=lambda x: x["case_right_id"]):
        case_right_id = proof["case_right_id"]
        slot = handoff_rows.get(case_right_id)
        source_case = casebook_rows.get(case_right_id)
        if slot is None or source_case is None:
            raise MarketDataEodClockProbeError("proof work item lost source row")
        original_request_id = slot.get("quote_request_identity")
        request = requests.get(original_request_id)
        if (
            request is None
            or slot.get("quote_history_status") not in {
                "VERIFIED_ORIGINAL_2022_QUOTE_HISTORY",
                "VERIFIED_DEMAND_CACHE_QUOTE_HISTORY",
                "VERIFIED_CLIPPED_DEMAND_CACHE_QUOTE_HISTORY",
            }
            or source_case.get("source_join_status")
                != "PAIRED_DATED_SOURCE_ONLY_UNSYNCHRONIZED"
            or source_case.get("option_symbol") != proof.get("option_symbol")
            or slot.get("option_symbol") != proof.get("option_symbol")
        ):
            raise MarketDataEodClockProbeError("dated proof source mapping changed")

        source_id = slot["quote_source_request_identity"]
        body_sha = slot["quote_body_sha256"]
        if (
            source_case.get("quote_source_request_identity") != source_id
            or source_case.get("quote_source_body_sha256") != body_sha
        ):
            raise MarketDataEodClockProbeError(
                "casebook physical quote provenance changed"
            )
        for mark in (proof["entry_source"], proof["later_source"]):
            if (
                mark.get("physical_quote_body_sha256") != body_sha
                or mark.get("quote_request_identity") != source_id
                or mark.get("option_symbol") != proof["option_symbol"]
            ):
                raise MarketDataEodClockProbeError(
                    "proof-demand physical quote provenance changed"
                )
        if source_id not in decoded:
            source_ticket, raw, receipt = read_verified_body(request, slot)
            if (
                source_ticket.get("request_identity") != source_id
                or receipt.get("body_sha256") != body_sha
                or receipt.get("safe_summary", {}).get("observed_rows")
                    != slot.get("observed_quote_rows")
            ):
                raise MarketDataEodClockProbeError("verified physical source changed")
            rows = _decode_snapshot_rows(
                raw, source_ticket, slot["observed_quote_rows"]
            )
            index = {_decoded_key(row): row for row in rows}
            if len(index) != len(rows):
                raise MarketDataEodClockProbeError(
                    "duplicate documented snapshot observation"
                )
            decoded[source_id] = index
            decoded_body_sha[source_id] = body_sha
        elif (
            decoded_body_sha[source_id] != body_sha
            or len(decoded[source_id]) != slot.get("observed_quote_rows")
        ):
            raise MarketDataEodClockProbeError(
                "same physical source identity changed body SHA or row count"
            )

        entry_key = _mark_key(proof["entry_source"])
        exit_key = _mark_key(proof["later_source"])
        entry_row = decoded[source_id].get(entry_key)
        exit_row = decoded[source_id].get(exit_key)
        if entry_row is None or exit_row is None:
            raise MarketDataEodClockProbeError(
                "proof-demand option mark no longer matches accepted raw body"
            )
        entry = _project_mark(entry_row, side="entry")
        exit_mark = _project_mark(exit_row, side="exit")
        expiry = _expiry(proof["option_symbol"])

        same_row_snapshot = (
            entry["documented_same_row_stock_option_snapshot"]
            and exit_mark["documented_same_row_stock_option_snapshot"]
        )
        exact_1600 = (
            entry["updated_is_1600_et"]
            and exit_mark["updated_is_1600_et"]
        )
        historical_eod_clock_shape = same_row_snapshot and exact_1600
        quote_side_liquidity = (
            entry["positive_displayed_size"]
            and exit_mark["positive_displayed_size"]
            and entry["positive_reported_volume"]
            and exit_mark["positive_reported_volume"]
        )
        pre_expiry_exit = date.fromisoformat(exit_mark["session_et"]) < expiry
        source_shape_candidate = (
            historical_eod_clock_shape
            and quote_side_liquidity
            and pre_expiry_exit
        )

        status = (
            "EOD_SNAPSHOT_LIQUIDITY_PREEXPIRY_SOURCE_SHAPE_CANDIDATE"
            if source_shape_candidate
            else "EOD_SNAPSHOT_OR_LIQUIDITY_OR_EXIT_POLICY_GAP"
        )
        year = proof["year"]
        by_year[year][status] += 1
        counts[status] += 1
        counts["DOCUMENTED_SAME_ROW_SNAPSHOT"] += same_row_snapshot
        counts["DOCUMENTED_HISTORICAL_EOD_CLOCK_SHAPE"] += historical_eod_clock_shape
        counts["ENTRY_EXIT_POSITIVE_SIZE_AND_VOLUME"] += quote_side_liquidity
        counts["FORCED_EXIT_STRICTLY_BEFORE_EXPIRY"] += pre_expiry_exit
        counts["BOTH_UPDATED_EXACTLY_1600_ET"] += exact_1600

        output_rows.append({
            "case_right_id": case_right_id,
            "original_case_id": proof["original_case_id"],
            "year": year,
            "right": proof["right"],
            "ticker": proof["ticker"],
            "option_symbol": proof["option_symbol"],
            "physical_quote_request_identity": source_id,
            "physical_quote_body_sha256": body_sha,
            "entry": entry,
            "exit": exit_mark,
            "expiration": expiry.isoformat(),
            "provider_documented_same_row_snapshot_candidate": same_row_snapshot,
            "provider_documented_historical_eod_clock_shape_candidate":
                historical_eod_clock_shape,
            "option_quote_publication_or_retrieval_availability_verified": False,
            "matched_executable_stock_option_clock_verified": False,
            "conservative_one_contract_quote_side_liquidity_candidate":
                quote_side_liquidity,
            "forced_exit_strictly_before_expiry_candidate": pre_expiry_exit,
            "round_trip_fee_per_contract_policy": ROUND_TRIP_FEE_PER_CONTRACT,
            "entry_at_ask_exit_at_bid_cost_policy": True,
            "provider_semantics_fingerprint": PROVIDER_SEMANTICS_FINGERPRINT,
            "point_in_time_option_deliverable_and_multiplier_verified": False,
            "historical_trade_admitted": False,
            "historical_account_pnl_authority": False,
            "source_shape_clock_liquidity_preexpiry_candidate":
                source_shape_candidate,
            "status": status,
        })

    if (
        len(output_rows) != proof_demand["dated_pair_work_items"]
        or sum(by_year[y]["EOD_SNAPSHOT_LIQUIDITY_PREEXPIRY_SOURCE_SHAPE_CANDIDATE"]
               + by_year[y]["EOD_SNAPSHOT_OR_LIQUIDITY_OR_EXIT_POLICY_GAP"]
               for y in by_year) != len(output_rows)
    ):
        raise MarketDataEodClockProbeError("probe denominator changed")

    result = {
        "contract": CONTRACT,
        "status": "DOCUMENTED_EOD_REFERENCE_PROBE_NO_TRADE_AUTHORITY",
        "quote_plan_fingerprint": plan["plan_fingerprint"],
        "source_handoff_fingerprint": handoff["handoff_fingerprint"],
        "casebook_fingerprint": casebook["casebook_fingerprint"],
        "execution_proof_demand_fingerprint":
            proof_demand["proof_demand_fingerprint"],
        "provider_semantics": PROVIDER_SEMANTICS,
        "provider_semantics_fingerprint": PROVIDER_SEMANTICS_FINGERPRINT,
        "original_case_denominator": expected_original_cases,
        "original_right_memberships": expected_original_cases * 2,
        "dated_pair_work_items": len(output_rows),
        "unique_verified_physical_histories_decoded": len(decoded),
        "documented_same_row_snapshot_candidates":
            counts["DOCUMENTED_SAME_ROW_SNAPSHOT"],
        "documented_historical_eod_clock_shape_candidates":
            counts["DOCUMENTED_HISTORICAL_EOD_CLOCK_SHAPE"],
        "entry_exit_positive_size_and_volume_candidates":
            counts["ENTRY_EXIT_POSITIVE_SIZE_AND_VOLUME"],
        "forced_pre_expiry_exit_candidates":
            counts["FORCED_EXIT_STRICTLY_BEFORE_EXPIRY"],
        "exact_1600_et_entry_and_exit_snapshots":
            counts["BOTH_UPDATED_EXACTLY_1600_ET"],
        "clock_liquidity_preexpiry_source_shape_candidates":
            counts["EOD_SOURCE_SHAPE_CANDIDATE"],
        "eod_snapshot_or_liquidity_or_exit_policy_gap":
            counts["EOD_SNAPSHOT_OR_LIQUIDITY_OR_EXIT_POLICY_GAP"],
        "option_quote_publication_or_retrieval_availability_verified": 0,
        "matched_executable_stock_option_clock_verified": 0,
        "by_year": {
            year: dict(sorted(by_year[year].items())) for year in by_year
        },
        "point_in_time_option_deliverable_and_multiplier_verified": 0,
        "historical_option_trades_admitted": 0,
        "historical_account_pnl": None,
        "historical_account_pnl_authority": False,
        "provider_requests": 0,
        "protected_2026_outcomes_read": 0,
        "rows": output_rows,
    }
    result["probe_fingerprint"] = _fingerprint(result)
    return result


def persist_marketdata_eod_clock_liquidity_probe(
    settings: AtlasSettings, report: dict[str, Any],
) -> tuple[Path, str]:
    settings.assert_external_storage_binding("options")
    _check_signature(report, "probe_fingerprint")
    if (
        report.get("contract") != CONTRACT
        or report.get("provider_requests") != 0
        or report.get("historical_option_trades_admitted") != 0
        or report.get("historical_account_pnl_authority") is not False
        or report.get("point_in_time_option_deliverable_and_multiplier_verified") != 0
    ):
        raise MarketDataEodClockProbeError("probe authority changed")
    path = settings.resolved_path(
        f"{OUTPUT_REL}_{report['probe_fingerprint'][:16]}.json"
    )
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or _read_object(path) != report:
            raise MarketDataEodClockProbeError("immutable prior probe differs")
        return path, "REUSED_IDENTICAL_MARKETDATA_EOD_CLOCK_LIQUIDITY_PROBE"
    _write_new(path, report)
    return path, "WRITTEN_IMMUTABLE_MARKETDATA_EOD_CLOCK_LIQUIDITY_PROBE"
