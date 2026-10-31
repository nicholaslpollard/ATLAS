from __future__ import annotations

"""V71: offline SPY original-exit quote continuity and available native months.

Source-only research diagnostic: independently verify original signed V69
source/replay receipts, inspect the actual archived option quote observations
around each unresolved exit, and discover local native SPY monthly units for
the next source-first V69 expansion. No provider/broker requests, hypothetical
fills, same-query retries, or source mutation.
"""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.alpaca_v2_rebuild import V2Layout
from packages.data.intraday_semantics_audit import (
    B34_MAX_SAMPLE_DATE, discover_minute_units,
)
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.spy_v55_closed_bar_option_replay import (
    _quote, _read_timestamp,
)
from scripts.run_spy_v59_offline_quote_forensics import _local_cache_only

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v71-original-exit-quote-clock-and-spy-month-catalog-v1"
V69 = "atlas-v69-spy-source-first-multiwindow-exact-options-census-v1"
V65 = "atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
EXPECTED_V69 = "0b8379ee99238bfde3c4230e74f7d8c9412c3fece899f3f0e1e3b3c75a18d7dd"
EXPECTED_REJECTS = ("2025-06-04", "2025-06-13")


class V71Error(ValueError):
    pass


def log(msg):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}",
          flush=True)


def signed(doc):
    return {**doc, "fingerprint": _fingerprint(doc)}


def source_report(path, contract, expected=None):
    if path.is_symlink() or not path.is_file():
        raise V71Error("V71_MISSING_OR_UNSAFE_IMMUTABLE_PARENT")
    doc = json.loads(path.read_text(encoding="utf8"))
    if (not isinstance(doc, dict) or doc.get("contract") != contract
            or doc.get("fingerprint") != _fingerprint({
                k: v for k, v in doc.items() if k != "fingerprint"
            }) or expected is not None and doc["fingerprint"] != expected):
        raise V71Error("V71_PARENT_REPORT_FINGERPRINT_OR_CONTRACT_CHANGED")
    return doc


def validate_full_june(folder, *, expected_sha=EXPECTED_V69):
    summary = source_report(folder / "summary.json", V69, expected_sha)
    if (summary.get("start") != "2025-06-02"
            or summary.get("end") != "2025-06-30"
            or summary.get("weekdays") != 21
            or summary.get("unresolved_option_positions") != 2
            or summary.get("unresolved_source_or_underlying_chunks") != 0
            or summary.get("chunks") != 1
            or summary.get("broker_orders") != 0):
        raise V71Error("V71_FROZEN_JUNE_SOURCE_CENSUS_CHANGED")
    chunk = source_report(folder / "chunk_0001.summary.json", V69)
    replay = source_report(folder / "chunk_0001.replay.json", V65)
    preflight = source_report(folder / "chunk_0001.preflight.json", V65)
    sources = source_report(folder / "chunk_0001.sources.json", V69)
    if (chunk["fingerprint"] != summary["chunk_summaries"][0]["fingerprint"]
            or chunk["original_v65_preflight_sha"] != preflight["fingerprint"]
            or chunk["original_v65_post_source_sha"] != replay["fingerprint"]
            or sources["original_preflight_sha"] != preflight["fingerprint"]
            or chunk.get("source_state_counts") != {"ARCHIVED": 13}
            or replay.get("option_source_state_counts") != {"ARCHIVED": 13}
            or chunk.get("unresolved_positions") != 2
            or chunk.get("unresolved_source_requirements")
            or sources["runtime_source_receipt"].get("source_uses_requested") != 13
            or sources["runtime_source_receipt"].get("source_uses_resolved") != 13):
        raise V71Error("V71_JUNE_SOURCE_REPLAY_RECEIPT_CHAIN_INVALID")
    original = {r["session"]: r for r in preflight["session_reports"]}
    after = replay["session_reports"]
    if len(original) != 21 or len(after) != 21:
        raise V71Error("V71_JUNE_SESSIONS_INCOMPLETE")
    for row in after:
        if (row["fingerprint"] != _fingerprint({
                k: v for k, v in row.items() if k != "fingerprint"
            }) or row["session"] not in original):
            raise V71Error("V71_ORIGINAL_SESSION_SHA_INVALID")
        prior = original[row["session"]]
        if (row["signal_fingerprint"] != prior["signal_fingerprint"]
                or row["selected_contract"] != prior["selected_contract"]
                or row["native_minute_source_sha256"] !=
                    prior["native_minute_source_sha256"]):
            raise V71Error("V71_ORIGINAL_NATIVE_SIGNAL_CHANGED")
        trade = row["standalone_replay_report"]
        if (trade["fingerprint"] != _fingerprint({
                k: v for k, v in trade.items() if k != "fingerprint"
            }) or trade["actual_fills"] != 0
                or not trade["quote_reference_not_broker_execution"]):
            raise V71Error("V71_ORIGINAL_TRADE_REPORT_SHA_INVALID")
    rejected = {
        row["session"]: row for row in after
        if row["standalone_replay_report"]["status"] == "UNRESOLVED_POSITION"
    }
    if tuple(sorted(rejected)) != EXPECTED_REJECTS:
        raise V71Error("V71_REJECTED_EXIT_COHORT_CHANGED")
    return summary, rejected


def analyze_rejected_exit(row, *, setting, cache_reader=_local_cache_only):
    contract = row["selected_contract"]
    receipt = row["exact_option_receipt"]
    requirement = row["exact_option_requirement"]
    trade = row["standalone_replay_report"]
    if (receipt["state"] != "ARCHIVED"
            or receipt["query_id"] != _fingerprint(requirement)
            or receipt["query_id"] != trade["source_query_id"]
            or receipt["archive_sha256"] != trade["source_sha256"]):
        raise V71Error("V71_EXIT_SOURCE_IDENTITY_INVALID")
    source_entry = cache_reader(setting, receipt["query_id"])
    source = source_entry.get("source")
    if (source_entry.get("cache_evidence") != "CACHE_HIT"
            or not isinstance(source, dict)
            or source["source_sha256"] != receipt["archive_sha256"]
            or source["query_id"] != receipt["query_id"]
            or source["exact_requirement"] != requirement):
        raise V71Error("V71_EXIT_SOURCE_NOT_SHA_VERIFIED_ACQUIRE_REQUIRED")
    day = date.fromisoformat(row["session"])
    events = trade["events"]
    rejects = [e for e in events if e["type"] == "EXIT_SOURCE_REJECTION"]
    entries = [e for e in events if e["type"] == "MODELED_ENTRY_QUOTE_REFERENCE"]
    if (len(rejects) != 1 or len(entries) != 1
            or trade["censor_reason"] != "UNQUALIFIED_EXIT_QUOTE_PATH"
            or rejects[0]["reason"] != "QUOTE_SPREAD_ABOVE_15_PERCENT"
            or rejects[0]["at_et"] != f"{day.isoformat()}T10:00:01-04:00"):
        raise V71Error("V71_UNEXPECTED_ORIGINAL_EXIT_REJECTION")
    idx = rejects[0]["row"]
    rows = source["source_rows"]
    if not 0 <= idx < len(rows):
        raise V71Error("V71_REJECTED_ROW_OUTSIDE_SOURCE")
    stamp = _read_timestamp(rows[idx], day)
    if stamp.isoformat() != rejects[0]["at_et"]:
        raise V71Error("V71_ORIGINAL_REJECTION_CLOCK_CHANGED")
    ask_at_entry = Decimal(str(entries[0]["ask"]))
    qty = entries[0]["qty"]
    observed = []
    after_valid = []
    invalid_counts = Counter()
    first_valid_prior = None
    for j in range(max(0, idx - 5), len(rows)):
        t = _read_timestamp(rows[j], day)
        offset = (t - stamp).total_seconds()
        if offset > 60:
            break
        if offset < -5:
            continue
        raw = rows[j]
        value = {
            "quote_index": j, "timestamp_et": t.isoformat(),
            "seconds_from_rejected_quote": offset,
            "raw_bid": raw.get("bid"), "raw_ask": raw.get("ask"),
            "raw_bid_size": raw.get("bid_size"),
            "raw_ask_size": raw.get("ask_size"),
            "status": "UNVERIFIED",
        }
        try:
            quote = _quote(raw, day=day, contract=contract)
            bid = Decimal(quote["bid"])
            decision = (
                "TAKE_PROFIT_100" if bid >= ask_at_entry * 2 else
                "STOP_LOSS_50" if bid <= ask_at_entry / 2 else "HOLD"
            )
            value["status"] = "QUALIFIED_ORIGINAL_QUOTE"
            value["hypothetical_threshold_comparison_only"] = decision
            value["bid_size_covers_original_qty"] = quote["bid_size"] >= qty
            if offset < 0:
                first_valid_prior = value
            elif offset > 0:
                after_valid.append(value)
        except Exception as exc:
            value["status"] = "REJECTED_ORIGINAL_QUOTE"
            value["rejection_type"] = type(exc).__name__
            value["rejection_reason"] = str(exc)
            invalid_counts[str(exc)] += 1
        observed.append(value)
    return signed({
        "contract": CONTRACT, "session": row["session"],
        "original_v65_replay_sha": trade["fingerprint"],
        "original_source_query_id": receipt["query_id"],
        "original_option_archive_sha256": receipt["archive_sha256"],
        "selected_contract": contract,
        "original_entry_at_et": entries[0]["at_et"],
        "original_entry_ask": str(ask_at_entry),
        "original_qty": qty,
        "original_exit_row_index": idx,
        "original_rejection_at_et": stamp.isoformat(),
        "original_exit_rejection_reason": rejects[0]["reason"],
        "examined_clock_interval": "5s before to 60s after rejected quote",
        "original_quote_observations": observed,
        "rejected_quote_counts": dict(sorted(invalid_counts.items())),
        "last_valid_quote_before_rejection": first_valid_prior,
        "first_valid_quote_after_rejection": (
            after_valid[0] if after_valid else None
        ),
        "qualified_quote_count_after_rejection_within_60s": len(after_valid),
        "same_moment_eligible_liquidation_proven": False,
        "skip_invalid_observation_authorized": False,
        "future_data_used_for_original_decision": False,
        "price_interpolation_performed": False,
        "quote_reference_pnl_revised": False,
        "broker_orders": 0, "provider_requests": 0,
    })


def native_month_catalog(*, layout, discover=discover_minute_units):
    root = layout.checkpoints / "native_units" / "1m"
    if not root.is_dir() or root.is_symlink():
        return {"status": "ORIGINAL_MONTH_CHECKPOINT_TREE_MISSING",
                "months": [], "month_count": 0}
    months = []
    for yr in sorted(root.glob("year=*")):
        if yr.is_symlink() or not yr.is_dir():
            continue
        for mon in sorted(yr.glob("month=*")):
            if mon.is_symlink() or not mon.is_dir():
                continue
            try:
                year = int(yr.name.split("=")[1])
                month = int(mon.name.split("=")[1])
                target = date(year, month, 1)
            except (ValueError, IndexError):
                continue
            if target > date(B34_MAX_SAMPLE_DATE.year, B34_MAX_SAMPLE_DATE.month, 1):
                continue
            descriptor = {"month": target.strftime("%Y-%m"),
                          "status": "UNCLASSIFIED"}
            try:
                units = [
                    x for x in discover(layout, target_year=year,
                                        target_month=month, progress=None)
                    if "SPY" in x.symbols
                ]
                descriptor["spy_native_units"] = len(units)
                if len(units) != 1:
                    descriptor["status"] = (
                        "NO_NATIVE_SPY_UNIT" if not units
                        else "AMBIGUOUS_MULTIPLE_NATIVE_SPY_UNITS"
                    )
                else:
                    unit = units[0]
                    originals = (
                        (unit.canonical_path, unit.canonical_sha256),
                        (unit.raw_bundle_path, unit.raw_bundle_sha256),
                    )
                    present = all(
                        not p.is_symlink() and p.is_file()
                        and isinstance(h, str) and len(h) == 64
                        for p, h in originals
                    )
                    descriptor.update({
                        "unit_id": unit.unit_id,
                        "original_paths_exist": present,
                        "original_bytes": sum(
                            p.stat().st_size for p, _ in originals
                            if not p.is_symlink() and p.is_file()
                        ),
                        "metadata_source_sha256": unit.canonical_sha256,
                        "status": "READY_FOR_FULL_ORIGINAL_SHA_PREFLIGHT"
                                  if present else "ORIGINAL_FILES_MISSING",
                    })
            except Exception as exc:
                descriptor["status"] = "ORIGINAL_MONTH_METADATA_BLOCKED"
                descriptor["exception_type_only"] = type(exc).__name__
            months.append(descriptor)
    return {
        "status": "MONTH_CATALOG_COMPLETE",
        "month_count": len(months),
        "ready_for_full_sha_verification": sum(
            x["status"] == "READY_FOR_FULL_ORIGINAL_SHA_PREFLIGHT"
            for x in months
        ),
        "original_sha_verified_for_these_months": False,
        "full_sha_verification_required_before_option_acquisition": True,
        "months": months,
    }


def write_once(path, doc):
    value = signed(doc)
    with path.open("x", encoding="utf8") as f:
        json.dump(value, f, sort_keys=True, indent=2, allow_nan=False)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    return value


def run(v69_folder, output_dir, *, expected_v69_sha=EXPECTED_V69,
        source_reader=_local_cache_only, settings_factory=load_settings,
        catalog=native_month_catalog, emit=log):
    if output_dir.exists() or output_dir.is_symlink():
        raise V71Error("V71_IMMUTABLE_OUTPUT_ALREADY_EXISTS")
    root_summary, rejected = validate_full_june(
        v69_folder, expected_sha=expected_v69_sha
    )
    setting = settings_factory(ROOT, "development")
    analyses = [
        analyze_rejected_exit(rejected[day], setting=setting,
                              cache_reader=source_reader)
        for day in EXPECTED_REJECTS
    ]
    layout = V2Layout.beneath(ROOT / "data")
    native = catalog(layout=layout)
    output_dir.mkdir(parents=True, exist_ok=False)
    for item in analyses:
        write_once(output_dir / f"exit_{item['session']}.json", {
            k: v for k, v in item.items() if k != "fingerprint"
        })
        emit(f"STAGE_PASS V71 exit_day={item['session']} "
             f"next_qualified_quote="
             f"{item['first_valid_quote_after_rejection']['timestamp_et'] if item['first_valid_quote_after_rejection'] else 'NONE'} "
             f"provider_calls=0")
    write_once(output_dir / "month_catalog.json", native)
    summary = write_once(output_dir / "summary.json", {
        "contract": CONTRACT,
        "status": "COMPLETE_ORIGINAL_SOURCE_DIAGNOSTIC",
        "parent_v69_fingerprint": root_summary["fingerprint"],
        "rejected_exit_days": list(EXPECTED_REJECTS),
        "exit_reports": [
            {
                "session": x["session"], "fingerprint": x["fingerprint"],
                "original_rejection_at_et": x["original_rejection_at_et"],
                "first_later_qualified_quote_at_et":
                    x["first_valid_quote_after_rejection"]["timestamp_et"]
                    if x["first_valid_quote_after_rejection"] else None,
                "qualified_original_observations_after": x[
                    "qualified_quote_count_after_rejection_within_60s"
                ],
            } for x in analyses
        ],
        "month_catalog_fingerprint": _fingerprint(native),
        "month_count": native["month_count"],
        "eligible_native_months": native.get(
            "ready_for_full_sha_verification", 0
        ),
        "full_sha_not_yet_automatically_verified": True,
        "no_exit_prices_imputed_or_skip_policy_assumed": True,
        "no_cumulative_june_equity_manufactured": True,
        "provider_requests": 0, "broker_orders": 0,
    })
    emit(f"COMPLETE V71 native_months={summary['eligible_native_months']} "
         f"original_exit_anomalies=2 output={output_dir/'summary.json'} "
         "provider_calls=0 broker_orders=0")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--v69-folder", required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--expected-v69-fingerprint", default=EXPECTED_V69)
    a = p.parse_args(argv)
    try:
        run(a.v69_folder, a.output_dir,
            expected_v69_sha=a.expected_v69_fingerprint)
        return 0
    except Exception as exc:
        log(f"STOPPED V71 type={type(exc).__name__} "
            "source_not_mutated=True broker_orders=0 provider_requests=0")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
