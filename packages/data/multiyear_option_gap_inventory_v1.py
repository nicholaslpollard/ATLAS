from __future__ import annotations

"""Offline full-denominator multi-year options source-gap inventory.

Read original accepted native stock source and already frozen 2022 CALL quote
plan once. A quote-plan member is a lineage POINTER, not a newly verified fill
or proof that a different same-key stock decision selected the same contract.
Never create a paid GET while exact prior-chain/2025-pilot reconciliation is due.
"""

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
import re
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.core.settings import AtlasSettings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _exclusive, _read_object
from packages.data.marketdata_2022_selected_quote_campaign_v1 import CONTRACT as OLD_QUOTE_CONTRACT
from packages.data.marketdata_2022_broad_quote_campaign_v2 import PLAN_REL, WIDE_POLICY, POLICY_VERSION
from packages.data.multiyear_native_stock_open_v1 import (
    AUTHORITY as NATIVE_AUTHORITY,
    CONTRACT as NATIVE_CONTRACT,
    build_multiyear_native_raw_open_source,
)

CONTRACT = "atlas-multiyear-original-option-source-gap-inventory-v1"
OUTPUT_REL = "data/options/manifests/multiyear_original_option_gap_inventory_v1"
ACCEPTED_2022_QUOTE_PLAN = "017805741349c5bd93eead00123282cee8a3980fcf9d3c368147b0ed4bbe6786"
EASTERN = ZoneInfo("America/New_York")
STRIKE_FRACTION = Decimal("0.08")
MAX_UNION_FRACTION = Decimal("0.25")
CENT = Decimal("0.01")
OCC = re.compile(r"^([A-Z0-9.]+)(\d{6})([CP])(\d{8})$")
AUTHORITY = {
    "provider_requests": 0,
    "new_paid_request_authority": False,
    "original_quote_receipts_reopened": False,
    "2022_original_chain_coverage_inferred_from_quote_plan": False,
    "2025_original_pilot_reconciliation_required": True,
    "2026_protected_data_read": False,
    "option_contract_selected_for_uncovered_cases": False,
    "fill_or_option_pnl": False,
    "paper": False, "live": False,
}


class MultiYearOptionInventoryError(ValueError):
    pass


def _valid_native(doc: dict[str, Any]) -> dict[str, Any]:
    unsigned = dict(doc)
    fp = unsigned.pop("source_fingerprint", None)
    rows = doc.get("rows")
    if (
        fp != _fingerprint(unsigned)
        or doc.get("contract") != NATIVE_CONTRACT
        or doc.get("status") != "MULTIYEAR_NATIVE_RAW_OPEN_VERIFIED_SOURCE_ONLY"
        or doc.get("authority") != NATIVE_AUTHORITY
        or doc.get("provider_requests") != 0
        or doc.get("protected_outcomes_read") != 0
        or not isinstance(rows, list)
        or len(rows) != doc.get("case_denominator")
        or len({r["case_id"] for r in rows}) != len(rows)
        or len(rows) != doc["verified_native_raw_open_cases"] + doc["deferred_2026_entry_cases"]
    ):
        raise MultiYearOptionInventoryError("accepted native stock input changed")
    return doc


def original_2022_quote_index(
    plan: dict[str, Any], *, expected: str = ACCEPTED_2022_QUOTE_PLAN,
) -> dict[str, Any]:
    """Source pointers only. Do not claim that the original bodies were reopened."""
    unsigned = dict(plan)
    fp = unsigned.pop("plan_fingerprint", None)
    envelope = plan.get("broad_acquisition_envelope_v2")
    requests = plan.get("requests")
    if (
        fp != _fingerprint(unsigned) or fp != expected
        or plan.get("contract") != OLD_QUOTE_CONTRACT
        or plan.get("selection_policy") != WIDE_POLICY
        or plan.get("year") != 2022
        or plan.get("last_shard_inclusive") != 70
        or plan.get("provider_reads_in_planning") != 0
        or not isinstance(envelope, dict)
        or envelope.get("policy_version") != POLICY_VERSION
        or envelope.get("alternate_expiration_sources_acquired") is not False
        or not isinstance(plan.get("source_plans"), list)
        or len(plan["source_plans"]) != 71
        or [r["shard_index"] for r in plan["source_plans"]] != list(range(71))
        or not isinstance(requests, list)
        or len(requests) != 6398
        or plan.get("unique_exact_quote_series") != 6398
    ):
        raise MultiYearOptionInventoryError("existing accepted 2022 quote plan changed")
    rank_zero: dict[str, dict[str, str]] = {}
    same_key: set[str] = set()
    for ticket in requests:
        symbol = ticket.get("option_symbol")
        if not isinstance(symbol, str) or not symbol:
            raise MultiYearOptionInventoryError("original OCC symbol is missing")
        for m in ticket.get("source_shard_memberships", []):
            case = m.get("opportunity_id")
            all_ids = m.get("all_accepted_same_key_opportunity_ids")
            if not isinstance(case, str) or not case or not isinstance(all_ids, list):
                raise MultiYearOptionInventoryError("original 2022 same-key ledger missing")
            if case not in all_ids or not all(isinstance(x, str) and x for x in all_ids):
                raise MultiYearOptionInventoryError("original 2022 same-key membership inconsistent")
            same_key.update(all_ids)
            if m.get("rank") == 0:
                if case in rank_zero:
                    raise MultiYearOptionInventoryError("duplicate original 2022 representative")
                rank_zero[case] = {
                    "option_symbol": symbol,
                    "original_chain_request_identity": m["chain_request_identity"],
                    "original_chain_body_sha256": m["chain_body_sha256"],
                    "original_raw_open": m["raw_underlying_open"],
                    "original_expiration": ticket["to_exclusive"],
                }
    if len(rank_zero) != 2643:
        raise MultiYearOptionInventoryError("original preferred 2022 CALL denominator changed")
    if not set(rank_zero).issubset(same_key):
        raise MultiYearOptionInventoryError("original rank-zero case lacks same-key ledger")
    return {
        "quote_plan_fingerprint": fp,
        "rank_zero": rank_zero,
        "same_key_case_ids": same_key,
        "unique_original_quote_histories": len(requests),
        "original_rank_zero_representatives": len(rank_zero),
    }


def _source_day(row: dict[str, Any]) -> date:
    snap = date.fromisoformat(row["signal_session"])
    entry = date.fromisoformat(row["entry_session"])
    decision = datetime.fromisoformat(row["planned_option_decision_at_utc"])
    if decision.tzinfo is None or decision.astimezone(EASTERN).date() != entry:
        raise MultiYearOptionInventoryError("source decision clock/session changed")
    if not 2021 <= snap.year <= 2025 or not snap < entry:
        raise MultiYearOptionInventoryError("source year and session changed")
    return snap


def _bounds(value: str) -> tuple[Decimal, Decimal]:
    try:
        price = Decimal(value)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise MultiYearOptionInventoryError("raw native price malformed") from exc
    if not price.is_finite() or not Decimal("0.01") <= price <= Decimal("1000000"):
        raise MultiYearOptionInventoryError("raw native price outside accepted query policy")
    lo = max(CENT, (price * (1 - STRIKE_FRACTION)).quantize(
        CENT, rounding=ROUND_FLOOR
    ))
    hi = (price * (1 + STRIKE_FRACTION)).quantize(
        CENT, rounding=ROUND_CEILING
    )
    return lo, hi


def freeze_option_source_gap_inventory(
    native: dict[str, Any],
    index: dict[str, Any],
    *, rolling_floor: date, progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    native = _valid_native(native)
    if (
        not isinstance(rolling_floor, date) or rolling_floor.year != 2021
        or index.get("quote_plan_fingerprint") != ACCEPTED_2022_QUOTE_PLAN
        or not isinstance(index.get("rank_zero"), dict)
        or not isinstance(index.get("same_key_case_ids"), set)
    ):
        raise MultiYearOptionInventoryError("accepted quote index or rolling floor absent")
    by_year: dict[str, Counter[str]] = {
        str(year): Counter() for year in range(2021, 2027)
    }
    members: list[dict[str, Any]] = []
    provisional_groups: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    original_ids: set[str] = set()
    for n, row in enumerate(native["rows"], 1):
        oid = row["case_id"]
        snap = _source_day(row)
        year = str(snap.year)
        if oid in original_ids:
            raise MultiYearOptionInventoryError("duplicate original signal")
        original_ids.add(oid)
        if (
            row["original_stock_source_status"] == "NEEDS_SEPARATE_2026_NATIVE_SOURCE"
            or row["raw_underlying_price"] is None
        ):
            if row["raw_underlying_price"] is not None or row["native_source_status"] != "DEFERRED_ENTRY_2026_NATIVE_SOURCE_NOT_READ":
                raise MultiYearOptionInventoryError("deferred 2026 entry has invented raw opening")
            status = "DEFERRED_2026_NATIVE_ENTRY"
        elif row["expiration"] is None:
            if row["native_source_status"] != "VERIFIED_NATIVE_RAW_OPEN_NO_MONTHLY_EXPIRY":
                raise MultiYearOptionInventoryError("absent monthly expiration status changed")
            status = "NO_BOUNDED_MONTHLY_EXPIRATION"
        else:
            expiry = date.fromisoformat(row["expiration"])
            if not 28 <= (expiry - snap).days <= 60:
                raise MultiYearOptionInventoryError("frozen monthly expiry range changed")
            _bounds(row["raw_underlying_price"])
            if snap < rolling_floor:
                status = "DECISION_OUTSIDE_ROLLING_PROVIDER_WINDOW"
            elif year == "2022":
                rank = index["rank_zero"].get(oid)
                if rank is not None:
                    occ = OCC.fullmatch(rank["option_symbol"])
                    if (
                        Decimal(rank["original_raw_open"]) != Decimal(row["raw_underlying_price"])
                        or rank["original_expiration"] != (expiry + timedelta(days=1)).isoformat()
                        or occ is None or occ.group(1) != row["ticker"]
                        or occ.group(3) != "C"
                        or "20" + occ.group(2)[:2] + "-" + occ.group(2)[2:4]
                           + "-" + occ.group(2)[4:6] != expiry.isoformat()
                    ):
                        raise MultiYearOptionInventoryError(
                            "rank-zero prior source original price/expiry identity differs"
                        )
                    status = "ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH"
                elif oid in index["same_key_case_ids"]:
                    status = "ORIGINAL_2022_SAME_KEY_RECONCILIATION_REQUIRED"
                else:
                    status = "ORIGINAL_2022_CHAIN_RECONCILIATION_REQUIRED"
            elif year == "2025":
                status = "ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED"
            else:
                status = "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE"
            if status in {
                "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE",
                "ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED",
            }:
                provisional_groups[(year,row["ticker"],row["signal_session"],row["expiration"])].append({
                    "case_id": oid,
                    "raw_underlying_price": row["raw_underlying_price"],
                    "decision_at_utc": row["planned_option_decision_at_utc"],
                })
        by_year[year][status] += 1
        pointer = index["rank_zero"].get(oid) if status == "ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH" else None
        members.append({
            "case_id": oid, "year": year, "ticker": row["ticker"],
            "signal_session": row["signal_session"], "entry_session": row["entry_session"],
            "expiration": row["expiration"],
            "decision_at_utc": row["planned_option_decision_at_utc"],
            "news_prior_24h": row["prior_24h_news_articles"],
            "news_prior_7d": row["prior_7d_news_articles"],
            "source_disposition": status,
            "original_2022_option_symbol_pointer": pointer["option_symbol"] if pointer else None,
            "original_2022_chain_body_sha256_pointer": pointer["original_chain_body_sha256"] if pointer else None,
            "selected_for_new_paid_get": False,
        })
        if progress and (n % 2500 == 0 or n == len(native["rows"])):
            progress({"stage":"OPTION_SOURCE_GAP_CENSUS","processed":n,
                      "total":len(native["rows"]),"provider_requests":0})
    if len(members) != native["case_denominator"]:
        raise MultiYearOptionInventoryError("original source denominator changed")
    for year in by_year:
        if sum(by_year[year].values()) != sum(1 for x in members if x["year"] == year):
            raise MultiYearOptionInventoryError("year denominator changed")
    # These are only a physical-query-size preview. A separately approved
    # original chain plan must reconcile exact historical 2022/2025 receipts.
    groups: list[dict[str, Any]] = []
    for key, cases in sorted(provisional_groups.items()):
        bins: list[dict[str, Any]] = []
        for case in sorted(cases, key=lambda x:(Decimal(x["raw_underlying_price"]),x["case_id"])):
            lo,hi = _bounds(case["raw_underlying_price"])
            price = Decimal(case["raw_underlying_price"])
            placed = False
            for b in bins:
                union_lo,union_hi = min(lo,b["lo"]),max(hi,b["hi"])
                min_price = min(price,b["minimum_price"])
                if (lo <= b["hi"] and hi >= b["lo"]
                    and (union_hi-union_lo)/min_price <= MAX_UNION_FRACTION):
                    b["lo"],b["hi"],b["minimum_price"] = union_lo,union_hi,min_price
                    b["member_case_ids"].append(case["case_id"])
                    placed = True
                    break
            if not placed:
                bins.append({"lo":lo,"hi":hi,"minimum_price":price,
                             "member_case_ids":[case["case_id"]]})
        for b in bins:
            group = {
                "year": key[0],"ticker":key[1],"snapshot_date":key[2],
                "expiration":key[3], "side":"call",
                "strike_window":f"{b['lo']:.2f},{b['hi']:.2f}",
                "member_case_ids":sorted(b["member_case_ids"]),
                "original_case_count":len(b["member_case_ids"]),
                "source_status":"PROVISIONAL_UNPAID_CHAIN_QUERY_NEEDS_RECEIPT_RECONCILIATION",
            }
            group["preview_identity"] = _fingerprint({"contract":CONTRACT,"preview":group})
            groups.append(group)
    if sum(g["original_case_count"] for g in groups) != sum(
        1 for m in members if m["source_disposition"] in {
            "PIT_CHAIN_SOURCE_REQUEST_CANDIDATE",
            "ORIGINAL_2025_PILOT_RECONCILIATION_REQUIRED",
        }
    ):
        raise MultiYearOptionInventoryError("provisional physical grouping lost cases")
    result = {
        "contract":CONTRACT,
        "status":"FULL_DENOMINATOR_OPTIONS_SOURCE_GAP_INVENTORY_NO_PAID_GET",
        "original_native_stock_source_fingerprint":native["source_fingerprint"],
        "accepted_original_2022_quote_plan_fingerprint":index["quote_plan_fingerprint"],
        "rolling_five_year_floor":rolling_floor.isoformat(),
        "case_denominator":len(members),
        "original_2022_preferred_representatives_in_plan":index["original_rank_zero_representatives"],
        "original_2022_physical_quote_histories_in_plan":index["unique_original_quote_histories"],
        "2022_case_overlaps_not_new_contract_selections":sum(
            1 for x in members if x["source_disposition"]=="ORIGINAL_2022_PREFERRED_CALL_PLAN_MATCH"
        ),
        "provisional_group_count":len(groups),
        "by_year":{y:dict(sorted(c.items())) for y,c in by_year.items()},
        "provider_requests":0,"new_paid_requests":0,"authority":AUTHORITY,
        "cases":members,"provisional_chain_groups":groups,
    }
    result["inventory_fingerprint"] = _fingerprint(result)
    return result


def _target(settings: AtlasSettings, native: dict[str, Any]) -> Path:
    return settings.resolved_path(
        f"{OUTPUT_REL}_{native['source_fingerprint'][:16]}.json"
    )


def _verified_existing(path: Path, native: dict[str, Any], *, rolling_floor: date) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise MultiYearOptionInventoryError("existing options inventory is not a regular file")
    doc = _read_object(path)
    unsigned = dict(doc)
    fp = unsigned.pop("inventory_fingerprint", None)
    if (
        fp != _fingerprint(unsigned) or doc.get("contract") != CONTRACT
        or doc.get("status") != "FULL_DENOMINATOR_OPTIONS_SOURCE_GAP_INVENTORY_NO_PAID_GET"
        or doc.get("authority") != AUTHORITY or doc.get("provider_requests") != 0
        or doc.get("new_paid_requests") != 0
        or doc.get("original_native_stock_source_fingerprint") != native["source_fingerprint"]
        or doc.get("accepted_original_2022_quote_plan_fingerprint") != ACCEPTED_2022_QUOTE_PLAN
        or doc.get("rolling_five_year_floor") != rolling_floor.isoformat()
        or doc.get("case_denominator") != len(native["rows"])
        or len(doc.get("cases",[])) != len(native["rows"])
        or len(doc.get("provisional_chain_groups",[])) != doc.get("provisional_group_count")
    ):
        raise MultiYearOptionInventoryError("existing options gap inventory drifted")
    return doc


def build_option_source_gap_inventory(
    settings: AtlasSettings, *, rolling_floor: date = date(2021,9,27),
    progress: Callable[[dict[str, Any]], None] | None = None,
    native_builder: Callable[..., Any] = build_multiyear_native_raw_open_source,
) -> tuple[dict[str, Any], Path, str]:
    settings.assert_external_storage_binding("options")
    settings.assert_external_storage_binding("research_evidence")
    native, _, action = native_builder(settings, progress=progress)
    native = _valid_native(native)
    if progress:
        progress({"stage":"REUSE_VERIFIED_ORIGINAL_NATIVE_STOCK",
                  "source_action":action,"cases":len(native["rows"]),"provider_requests":0})
    path = _target(settings,native)
    existing = _verified_existing(path,native,rolling_floor=rolling_floor)
    if existing is not None:
        return existing,path,"REUSED_VERIFIED_OPTION_INVENTORY_NO_SOURCE_RESCAN"
    frozen_path = settings.resolved_path(f"{PLAN_REL}/through_shard_070.json")
    if frozen_path.is_symlink() or not frozen_path.is_file():
        raise MultiYearOptionInventoryError("original accepted 2022 plan unavailable")
    index = original_2022_quote_index(_read_object(frozen_path))
    result = freeze_option_source_gap_inventory(
        native,index,rolling_floor=rolling_floor,progress=progress
    )
    if path.exists() or path.is_symlink():
        if _verified_existing(path,native,rolling_floor=rolling_floor) != result:
            raise MultiYearOptionInventoryError("existing immutable option inventory differs")
        return result,path,"REUSED_IDENTICAL_OPTION_INVENTORY"
    _exclusive(path,result)
    if _verified_existing(path,native) != result:
        raise MultiYearOptionInventoryError("new options source gap inventory readback differs")
    return result,path,"WRITTEN_NEW_OPTIONS_SOURCE_GAP_INVENTORY"
