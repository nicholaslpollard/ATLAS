from __future__ import annotations

"""Additive 2022 PIT historical option-chain sharding, outside the 3/month pilot.

Deliberately source-only. Historical chain keys already covered by the original
2022 acquisition are excluded in full, not merely matching exact HTTP URLs.
Every shard is composed from intact native-raw DEVELOPMENT stock opportunities.
"""

import json
import math
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from packages.backtesting.recurrent_successor_outcome_replay import load_selected_replay_opportunities
from packages.core.settings import AtlasSettings
from packages.data import marketdata_accepted_stock_candidate_export_v1 as exporter
from packages.data.marketdata_candidate_batch_plan_v1 import TICKER_PATTERN, plan_candidate_chain_batches
from packages.data.marketdata_candidate_chain_cache_v1 import (
    CandidateChainCacheError, _fingerprint, verify_candidate_plan,
    run_candidate_chain_cache,
)
from packages.data.marketdata_candidate_expansion_v1 import (
    _bound_path, _exclusive, _read_object, _require_external, _sha,
    prepare_cohort, run_expansion,
)

CONTRACT = "atlas-marketdata-additive-development-2022-shard-v1"
FROZEN_PRIOR_PLAN = "7ee19d3d396ff90ce1c81b488cb70f21e59341f08d264531565ec586e7182faf"
FROZEN_PRIOR_COHORT = "c257f2d0505becff"
YEAR = 2022
KEYS_PER_SHARD = 40
MAX_SHARD_INDEX = 999
EASTERN = ZoneInfo("America/New_York")
SALT = "ATLAS_2022_ADDITIVE_KEYS_V1"
BIND_REL = "data/options/manifests/marketdata_additive_2022"


def _key(item: Any) -> tuple[str, str, str]:
    return (
        item.ticker,
        item.signal_session.isoformat(),
        exporter._monthly_expiration(item.signal_session).isoformat(),
    )


def _prior(settings: AtlasSettings, *, runner: Callable[..., dict[str, Any]] = run_candidate_chain_cache,
           preparer: Callable[..., Any] = prepare_cohort) -> tuple[dict[str, Any], set[str], set[tuple[str, str, str]]]:
    if not _bound_path(settings, YEAR, 3).is_file():
        raise CandidateChainCacheError("original 2022 three/month source has not been exported")
    plan, source_path, binding, action = preparer(
        settings, year=YEAR, per_month=3, duckdb_threads=4,
    )
    if (plan["plan_fingerprint"] != FROZEN_PRIOR_PLAN
            or binding["cohort_id"] != FROZEN_PRIOR_COHORT
            or plan["opportunities"] != 36 or plan["shared_chain_requests"] != 36):
        raise CandidateChainCacheError("original 2022 source/plan no longer matches operator result")
    state = runner(settings, plan)
    if (state["pending"] != 0 or state["reused"] + state["no_data_verified"] != 36
            or state["no_data_verified"] < 3):
        raise CandidateChainCacheError("finish and verify all original 2022 chains/gaps first")
    bundle = _read_object(source_path)
    if (_sha(source_path) != binding["source_sha256"]
            or bundle["contract"] != exporter.CONTRACT or bundle["year"] != YEAR
            or len(bundle["rows"]) != 36):
        raise CandidateChainCacheError("original 2022 immutable native stock source changed")
    keys = {(req["ticker"], req["params"]["date"], req["params"]["expiration"])
            for req in plan["requests"]}
    ids = {row["opportunity_id"] for row in bundle["rows"]}
    if not 1 <= len(keys) <= 36 or len(ids) != 36:
        raise CandidateChainCacheError("original 2022 source/group identities changed")
    return plan, ids, keys


def _binding_path(settings: AtlasSettings, shard_index: int) -> Path:
    return settings.resolved_path(f"{BIND_REL}/shard_{shard_index:03d}.json")


def _read_bound(settings: AtlasSettings, shard_index: int, prior_fp: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    binding = _read_object(_binding_path(settings, shard_index))
    unsigned = dict(binding)
    fingerprint = unsigned.pop("binding_fingerprint", None)
    if (fingerprint != _fingerprint(unsigned)
            or binding.get("contract") != CONTRACT
            or binding.get("year") != YEAR
            or binding.get("shard_index") != shard_index
            or binding.get("keys_per_shard") != KEYS_PER_SHARD
            or binding.get("prior_plan_fingerprint") != prior_fp
            or binding.get("source_role") != "ACCEPTED_NATIVE_RAW_DEVELOPMENT_ONLY"):
        raise CandidateChainCacheError("additive shard binding is not original/intact")
    cohort_id = binding["cohort_id"]
    if (not isinstance(cohort_id, str) or len(cohort_id) != 16
            or any(x not in "0123456789abcdef" for x in cohort_id)):
        raise CandidateChainCacheError("additive cohort identity malformed")
    source_path = settings.resolved_path(
        f"{exporter.BUNDLE_SUBDIR}/{cohort_id}.json"
    )
    plan_path = settings.resolved_path(
        f"{exporter.PLAN_SUBDIR}/marketdata_candidate_batch_plan_v1_{cohort_id}.json"
    )
    source = _read_object(source_path)
    plan = verify_candidate_plan(_read_object(plan_path))
    if (_sha(source_path) != binding["source_sha256"]
            or source.get("contract") != CONTRACT
            or source.get("year") != YEAR
            or source.get("shard_index") != shard_index
            or source.get("original_prior_plan_fingerprint") != prior_fp
            or source.get("protected_master_return_rows_read") != 0
            or source.get("authority", {}).get("provider_reads") is not False
            or len(source.get("rows", [])) != binding["selected_opportunities"]
            or plan["plan_fingerprint"] != binding["plan_fingerprint"]
            or plan["opportunities"] != binding["selected_opportunities"]
            or plan["shared_chain_requests"] != binding["shared_chains"]
            or {x["stock_source_sha256"] for x in plan["source_bindings"].values()}
               != {binding["source_sha256"]}):
        raise CandidateChainCacheError("additive shard source/plan physical SHA lineage changed")
    return plan, source_path, binding


def prepare_additive_shard(
    settings: AtlasSettings, *, shard_index: int = 0, duckdb_threads: int = 4,
    loader: Callable[..., Any] = load_selected_replay_opportunities,
    native_reader: Callable[..., Any] = exporter._read_entry_opens,
    runner: Callable[..., dict[str, Any]] = run_candidate_chain_cache,
    preparer: Callable[..., Any] = prepare_cohort,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any], Path, dict[str, Any], str]:
    if not 0 <= shard_index <= MAX_SHARD_INDEX or not 1 <= duckdb_threads <= 8:
        raise CandidateChainCacheError("additive shard index/threads outside registered bounds")
    _require_external(settings)
    prior, old_ids, old_keys = _prior(settings, runner=runner, preparer=preparer)
    bound = _binding_path(settings, shard_index)
    if bound.exists() or bound.is_symlink():
        result = _read_bound(settings, shard_index, prior["plan_fingerprint"])
        return (*result, "REUSED_IMMUTABLE_ADDITIVE_SHARD")

    if progress is not None:
        progress({"stage": "FULL_ACCEPTED_2022_SOURCE_LOADING", "shard_index": shard_index})
    opportunities, source = loader(
        settings.project_root, start_session=date(YEAR, 1, 1),
        end_session=date(YEAR, 12, 31), duckdb_threads=duckdb_threads,
    )
    if not source.get("source_integrity_fingerprint"):
        raise CandidateChainCacheError("accepted replay/source integrity missing")
    eligible = [
        x for x in opportunities
        if (x.signal_session.year == YEAR and x.native_timeframe == "1d"
            and x.direction == "LONG"
            and x.entry_utc.astimezone(EASTERN).year == YEAR
            and isinstance(x.ticker, str) and TICKER_PATTERN.fullmatch(x.ticker))
    ]
    if not eligible or len({x.opportunity_id for x in eligible}) != len(eligible):
        raise CandidateChainCacheError("accepted 2022 daily LONG identity census empty/duplicate")
    new_by_key: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    excluded_id = excluded_prior_key = 0
    for item in eligible:
        if item.opportunity_id in old_ids:
            excluded_id += 1
            continue
        key = _key(item)
        if key in old_keys:
            excluded_prior_key += 1
            continue
        new_by_key[key].append(item)
    keys = sorted(new_by_key, key=lambda k: (
        _fingerprint({"salt": SALT, "key": k}), k
    ))
    if not keys:
        raise CandidateChainCacheError("no additive keys remain outside original 2022 coverage")
    shards = math.ceil(len(keys) / KEYS_PER_SHARD)
    if shard_index >= shards:
        raise CandidateChainCacheError(f"requested shard {shard_index} beyond {shards} accepted shards")
    chosen_keys = keys[shard_index * KEYS_PER_SHARD:(shard_index + 1) * KEYS_PER_SHARD]
    selected = [item for key in chosen_keys for item in sorted(
        new_by_key[key], key=lambda row: row.opportunity_id
    )]
    if len(selected) > 10000:
        raise CandidateChainCacheError("additive shard exceeds planner source upper bound")
    if progress is not None:
        progress({
            "stage": "ADDITIVE_KEYS_FROZEN", "accepted_eligible": len(eligible),
            "excluded_original_ids": excluded_id,
            "excluded_entire_original_query_key": excluded_prior_key,
            "new_candidate_keys": len(keys), "total_shards": shards,
            "selected_shard_keys": len(chosen_keys), "selected_shard_opportunities": len(selected),
        })
    opens, daily_source = native_reader(settings.project_root, selected)
    if set(opens) != {x.opportunity_id for x in selected}:
        raise CandidateChainCacheError("native raw stock open coverage does not match additive source")
    if daily_source.get("protected_master_return_rows_read") != 0:
        raise CandidateChainCacheError("protected return source was accessed")
    bundle_rows: list[dict[str, str]] = []
    for item in selected:
        key = _key(item)
        bundle_rows.append({
            "opportunity_id": item.opportunity_id,
            "ticker": item.ticker,
            "instrument_id": item.instrument_id,
            "policy_id": item.policy_id,
            "signal_session": key[1],
            "snapshot_date": key[1],
            "decision_at_utc": (item.entry_utc.astimezone(UTC)
                                + exporter.timedelta(minutes=5)).isoformat(),
            "raw_underlying_price": str(opens[item.opportunity_id]),
            "price_origin": "ACCEPTED_NATIVE_RAW_1DAY_ENTRY_OPEN",
            "expiration": key[2],
            "side": "call",
            "underlying_price_basis": "RAW_AS_TRADED",
        })
    bundle = {
        "contract": CONTRACT,
        "scope": "DEVELOPMENT_SOURCE_ONLY",
        "year": YEAR,
        "shard_index": shard_index,
        "keys_per_shard": KEYS_PER_SHARD,
        "selection": "ALL_ACCEPTED_DAILY_LONG_OUTSIDE_PRIOR_2022_PHYSICAL_QUERY_KEYS",
        "shard_salt": SALT,
        "all_additive_query_keys_fingerprint": _fingerprint(keys),
        "selected_query_keys": [list(k) for k in chosen_keys],
        "total_additive_shards": shards,
        "eligible_daily_long_cases": len(eligible),
        "excluded_original_opportunity_ids": excluded_id,
        "excluded_colliding_original_query_keys": excluded_prior_key,
        "original_prior_plan_fingerprint": prior["plan_fingerprint"],
        "source_selected_opportunity_integrity_fingerprint": source["source_integrity_fingerprint"],
        "source_conditioning_analysis_fingerprint": source.get("conditioning_analysis_fingerprint"),
        "accepted_research_daily_source_fingerprint": daily_source["source_fingerprint"],
        "accepted_native_raw_source": daily_source["native_raw_source"],
        "accepted_raw_daily_manifest_sha256": daily_source["manifest_sha256"],
        "protected_master_return_rows_read": 0,
        "rows": bundle_rows,
        "authority": {"provider_reads": False, "option_price_or_pnl": False,
                      "paper": False, "live": False, "broker_reads_writes": False},
    }
    raw = exporter._encoded(bundle)
    source_sha = exporter.hashlib.sha256(raw).hexdigest()
    planning = [{
        "opportunity_id": row["opportunity_id"], "ticker": row["ticker"],
        "snapshot_date": row["snapshot_date"], "decision_at_utc": row["decision_at_utc"],
        "raw_underlying_price": row["raw_underlying_price"], "side": "call",
        "expiration": row["expiration"], "underlying_price_basis": "RAW_AS_TRADED",
        "stock_source_sha256": source_sha,
    } for row in bundle_rows]
    plan = verify_candidate_plan(plan_candidate_chain_batches({
        "purpose": "SOURCE_ACQUISITION_ONLY", "opportunities": planning,
    }))
    if any((r["ticker"], r["params"]["date"], r["params"]["expiration"]) in old_keys
           for r in plan["requests"]):
        raise CandidateChainCacheError("new shard has colliding physical prior query key")
    if len({r["request_identity"] for r in plan["requests"]}) != len(plan["requests"]):
        raise CandidateChainCacheError("additive shard produced duplicate provider identities")
    cid = _fingerprint({"contract": CONTRACT, "source_sha256": source_sha,
                        "plan_fingerprint": plan["plan_fingerprint"]})[:16]
    stock_path = settings.resolved_path(f"{exporter.BUNDLE_SUBDIR}/{cid}.json")
    plan_path = settings.resolved_path(
        f"{exporter.PLAN_SUBDIR}/marketdata_candidate_batch_plan_v1_{cid}.json"
    )
    exporter._preserve_exact(stock_path, raw)
    exporter._preserve_exact(plan_path, exporter._encoded(plan))
    binding = {
        "contract": CONTRACT, "year": YEAR, "shard_index": shard_index,
        "keys_per_shard": KEYS_PER_SHARD, "cohort_id": cid,
        "prior_plan_fingerprint": prior["plan_fingerprint"],
        "source_sha256": source_sha, "plan_fingerprint": plan["plan_fingerprint"],
        "selected_opportunities": len(selected), "shared_chains": len(plan["requests"]),
        "source_role": "ACCEPTED_NATIVE_RAW_DEVELOPMENT_ONLY",
        "provider_reads": 0, "no_option_fill_or_pnl_authority": True,
    }
    binding["binding_fingerprint"] = _fingerprint(binding)
    _exclusive(bound, binding)
    verified = _read_bound(settings, shard_index, prior["plan_fingerprint"])
    if progress is not None:
        progress({"stage": "SHARD_SOURCE_WRITTEN", "source_sha256": source_sha,
                  "plan_fingerprint": plan["plan_fingerprint"], "cohort_id": cid,
                  "shared_chains": len(plan["requests"])})
    return (*verified, "WRITTEN_NEW_ADDITIVE_SHARD")
