from __future__ import annotations

"""2022 opportunity-level EOD scenario readiness, NOT an executable backtest.

One deterministic structural rank-0 CALL per accepted representative. Original
decision date is sourced from SHA-bound stock evidence. Future EOD observations
are described only AFTER selection; never used to choose a contract.
"""

import json
from collections import Counter
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable

from packages.core.settings import AtlasSettings
from packages.data import marketdata_additive_2022_shards_v1 as shards
from packages.data.marketdata_2022_broad_quote_campaign_v2 import (
    PLAN_REL, POLICY_VERSION, WIDE_POLICY,
)
from packages.data.marketdata_2022_selected_quote_campaign_v1 import (
    CONTRACT as QUOTE_CONTRACT, _cache_paths, _read_intact_quote,
)
from packages.data.marketdata_candidate_2025_selected_quote_source_v1 import EASTERN, _decimal
from packages.data.marketdata_candidate_chain_cache_v1 import CandidateChainCacheError, _fingerprint
from packages.data.marketdata_candidate_expansion_v1 import _read_object, _exclusive
from packages.providers.marketdata_app.client import array_rows

CONTRACT = "atlas-marketdata-2022-ranked-eod-readiness-v1"
EXPECTED_PLAN = "017805741349c5bd93eead00123282cee8a3980fcf9d3c368147b0ed4bbe6786"
SOURCE_RANGE_END = 70
OUTPUT_REL = "data/options/manifests/marketdata_2022_ranked_eod_readiness_v1"
AUTHORITY = {
    "provider_reads": False, "intraday_0935_fill": False,
    "historical_deliverable_verified": False, "executable_option_pnl": False,
    "paper": False, "live": False, "broker": False,
}


def _number(value: Any) -> Decimal | None:
    try:
        return _decimal(value)
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise CandidateChainCacheError("malformed original EOD quote price") from exc


def _source_map(settings: AtlasSettings, plan: dict[str, Any],
                *, prior_reader: Callable[..., Any] = shards._prior,
                bound_reader: Callable[..., Any] = shards._read_bound,
                ) -> dict[tuple[int, str], dict[str, Any]]:
    prior, _, _ = prior_reader(settings)
    original_fp = prior["plan_fingerprint"]
    source_plans = plan["source_plans"]
    if (not isinstance(source_plans, list) or len(source_plans) != 71
            or [x.get("shard_index") for x in source_plans] != list(range(71))):
        raise CandidateChainCacheError("full 2022 source shard census missing")
    source_map: dict[tuple[int, str], dict[str, Any]] = {}
    for info in source_plans:
        i = info["shard_index"]
        bound_plan, path, binding = bound_reader(settings, i, original_fp)
        if (binding["source_sha256"] != info["source_sha256"]
                or bound_plan["plan_fingerprint"] != info["chain_plan_fingerprint"]):
            raise CandidateChainCacheError("original source/plan binding changed")
        source = _read_object(path)
        if source.get("year") != 2022 or source.get("shard_index") != i:
            raise CandidateChainCacheError("original source year/shard changed")
        for row in source["rows"]:
            oid = row["opportunity_id"]
            key = (i, oid)
            if key in source_map or not oid:
                raise CandidateChainCacheError("duplicate original opportunity membership")
            source_map[key] = row
    return source_map


def build_ranked_eod_readiness(
    settings: AtlasSettings, *,
    expected_plan: str = EXPECTED_PLAN,
    prior_reader: Callable[..., Any] = shards._prior,
    bound_reader: Callable[..., Any] = shards._read_bound,
    quote_reader: Callable[..., Any] = _read_intact_quote,
    raw_reader: Callable[..., bytes] | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Transform original verified data into a NEW observational research artifact."""
    if expected_plan != EXPECTED_PLAN:
        raise CandidateChainCacheError("unaccepted 2022 quote plan fingerprint")
    path = settings.resolved_path(f"{PLAN_REL}/through_shard_070.json")
    plan = _read_object(path)
    unsigned = dict(plan)
    actual_fp = unsigned.pop("plan_fingerprint", None)
    env = plan.get("broad_acquisition_envelope_v2")
    if (actual_fp != _fingerprint(unsigned) or actual_fp != expected_plan
            or plan.get("contract") != QUOTE_CONTRACT
            or plan.get("last_shard_inclusive") != SOURCE_RANGE_END
            or plan.get("selection_policy") != WIDE_POLICY
            or plan.get("provider_reads_in_planning") != 0
            or not isinstance(env, dict) or env.get("policy_version") != POLICY_VERSION
            or env.get("alternate_expiration_sources_acquired") is not False):
        raise CandidateChainCacheError("frozen 2022 PIT quote-plan identity changed")
    tickets = plan["requests"]
    if (len(tickets) != plan["unique_exact_quote_series"] or len(tickets) != 6398
            or len({x["request_identity"] for x in tickets}) != len(tickets)):
        raise CandidateChainCacheError("accepted full quote corpus identity/count differs")
    if raw_reader is None:
        def raw_reader(s: AtlasSettings, ticket: dict[str, Any]) -> bytes:
            return _cache_paths(s, ticket)[0].read_bytes()

    sources = _source_map(settings, plan, prior_reader=prior_reader,
                          bound_reader=bound_reader)
    rank_zero: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    seen_rank_zero: set[tuple[int, str]] = set()
    for ticket in tickets:
        for member in ticket["source_shard_memberships"]:
            if member["rank"] != 0:
                continue
            key = (member["shard_index"], member["opportunity_id"])
            row = sources.get(key)
            if row is None or key in seen_rank_zero:
                raise CandidateChainCacheError("rank-zero representative missing/duplicated")
            seen_rank_zero.add(key)
            if (row["side"] != "call"
                    or row["raw_underlying_price"] != member["raw_underlying_open"]
                    or row["ticker"] != ticket["option_symbol"][:len(row["ticker"])]):
                raise CandidateChainCacheError("rank-zero source mapping differs")
            rank_zero.append((ticket, member, row))
    if not rank_zero:
        raise CandidateChainCacheError("no structural rank-zero opportunities")
    # Group selected rank-zero cases by physical exact history. An original
    # response is read once even when a contract serves several opportunities.
    by_identity: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    ticket_by_id: dict[str, dict[str, Any]] = {}
    for ticket, member, source in rank_zero:
        identity = ticket["request_identity"]
        ticket_by_id[identity] = ticket
        by_identity.setdefault(identity, []).append((member, source))
    rows_out: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    positive_after = bid_ask_after = two_context = 0
    for n, (identity, group) in enumerate(sorted(by_identity.items()), 1):
        ticket = ticket_by_id[identity]
        receipt = quote_reader(settings, ticket)
        if receipt is None or receipt["status"] != "COMPLETE_SOURCE_ONLY":
            raise CandidateChainCacheError("rank-zero exact quote source not complete")
        raw = raw_reader(settings, ticket)
        try:
            observations = array_rows(json.loads(raw.decode("utf-8")))
        except (ValueError, TypeError, KeyError) as exc:
            raise CandidateChainCacheError("rank-zero original quote body malformed") from exc
        if len(observations) != receipt["safe_summary"]["observed_rows"]:
            raise CandidateChainCacheError("rank-zero observed row count changed")
        events: list[tuple[date, bool, bool]] = []
        for item in observations:
            if item["optionSymbol"] != ticket["option_symbol"]:
                raise CandidateChainCacheError("rank-zero OCC symbol mismatch")
            ts = _number(item["updated"])
            if ts is None or ts != ts.to_integral_value():
                raise CandidateChainCacheError("rank-zero EOD timestamp malformed")
            day = datetime.fromtimestamp(int(ts), UTC).astimezone(EASTERN).date()
            bid, ask, volume = (_number(item[x]) for x in ("bid", "ask", "volume"))
            two_sided = bid is not None and ask is not None and bid > 0 and ask >= bid
            events.append((day, volume is not None and volume > 0, two_sided))
        events.sort(key=lambda x: x[0])
        for member, source in group:
            signal = date.fromisoformat(source["signal_session"])
            decision = datetime.fromisoformat(source["decision_at_utc"]).astimezone(EASTERN).date()
            expiry = date.fromisoformat(source["expiration"])
            if (not signal < decision < expiry or signal.isoformat() != source["snapshot_date"]
                    or (expiry - date.fromisoformat(ticket["to_exclusive"])).days != -1):
                raise CandidateChainCacheError("rank-zero original decision/expiry chronology changed")
            # A 09:35 decision CANNOT use a quote dated that same session for
            # entry. Later EOD is retrospective context, never contract selection.
            later = [e for e in events if decision < e[0] <= expiry]
            later_two = [e[0] for e in later if e[2]]
            later_pos = [e[0] for e in later if e[1]]
            code = ("NO_LATER_EOD_OBSERVATION" if not later
                    else "LATER_EOD_NO_TWO_SIDED_CONTEXT" if not later_two
                    else "LATER_TWO_SIDED_CONTEXT_ONLY")
            counts[code] += 1
            positive_after += bool(later_pos)
            bid_ask_after += bool(later_two)
            two_context += len(later_two) >= 2
            rows_out.append({
                "opportunity_id": source["opportunity_id"],
                "shard_index": member["shard_index"],
                "ticker": source["ticker"],
                "option_symbol": ticket["option_symbol"],
                "structural_rank": 0,
                "source_signal_session": signal.isoformat(),
                "stock_decision_session_et": decision.isoformat(),
                "expiration": expiry.isoformat(),
                "first_later_observed_eod_session": later[0][0].isoformat() if later else None,
                "first_later_positive_reported_volume_session": later_pos[0].isoformat() if later_pos else None,
                "first_later_two_sided_eod_context_session": later_two[0].isoformat() if later_two else None,
                "later_two_sided_eod_context_sessions": len(later_two),
                "classification": code,
                "future_eod_never_used_for_structural_selection": True,
                "original_exact_quote_request_identity": identity,
            })
        if progress and (n % 250 == 0 or n == len(by_identity)):
            progress({"stage": "RANKED_EOD_CONTEXT_PROGRESS", "unique_rank0_histories": n,
                      "total_unique_rank0_histories": len(by_identity),
                      "rank0_opportunity_memberships": len(rows_out),
                      "provider_requests": 0})
    rows_out.sort(key=lambda x: (x["stock_decision_session_et"], x["opportunity_id"],
                                 x["shard_index"], x["option_symbol"]))
    result = {
        "contract": CONTRACT,
        "status": "RANKED_EOD_SCENARIO_READINESS_ONLY",
        "accepted_original_quote_plan": actual_fp,
        "rank_zero_opportunity_memberships": len(rows_out),
        "unique_rank_zero_quote_histories": len(by_identity),
        "no_later_eod_observation": counts["NO_LATER_EOD_OBSERVATION"],
        "later_eod_without_two_sided_context": counts["LATER_EOD_NO_TWO_SIDED_CONTEXT"],
        "later_two_sided_eod_context_only": counts["LATER_TWO_SIDED_CONTEXT_ONLY"],
        "later_positive_reported_volume_opportunities": positive_after,
        "later_two_sided_context_opportunities": bid_ask_after,
        "opportunities_with_two_or_more_later_two_sided_context_dates": two_context,
        "entry_timing_rule": "STRICTLY_AFTER_0935_DECISION_ET_SESSION_NOT_SAME_DAY_EOD",
        "contract_choice_rule": "FROZEN_PIT_STRUCTURAL_RANK_ZERO_ONLY_NO_FUTURE_FILTER",
        "context_only_no_fills_usable_quote_timestamp_or_pnl": True,
        "original_quote_receipts_modified": 0, "provider_requests": 0,
        "authority": AUTHORITY, "rows": rows_out,
    }
    result["readiness_fingerprint"] = _fingerprint(result)
    return result


def write_ranked_readiness(settings: AtlasSettings, result: dict[str, Any]) -> tuple[Path, str]:
    if (result.get("contract") != CONTRACT
            or result.get("readiness_fingerprint") != _fingerprint({
                k: v for k, v in result.items() if k != "readiness_fingerprint"
            })
            or result.get("provider_requests") != 0
            or result.get("authority") != AUTHORITY):
        raise CandidateChainCacheError("ranked EOD readiness manifest invalid")
    path = settings.resolved_path(f"{OUTPUT_REL}_{EXPECTED_PLAN[:16]}.json")
    if path.exists() or path.is_symlink():
        if _read_object(path) != result:
            raise CandidateChainCacheError("previous readiness manifest differs; preserve original")
        return path, "REUSED_IDENTICAL_READINESS"
    _exclusive(path, result)
    if _read_object(path) != result:
        raise CandidateChainCacheError("readiness manifest readback mismatch")
    return path, "WRITTEN_NEW_READINESS"
