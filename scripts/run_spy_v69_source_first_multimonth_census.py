from __future__ import annotations

"""V69: source-first SPY options historical run over consecutive month/day windows.

Preserve every selected option requirement, resolve through V39's safe V38
cache/provider path, then rerun the original immutable V65 quote-reference
audit. Each month/day block is independently persisted before advancing.
Never mistake source-censored NO_ENTRY as a genuine rejected trade; never
silently skip an unsupported underlying-stock source dependency.
"""

import argparse
from collections import Counter
from datetime import date, datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from packages.simulation.strategy_options_source_runtime_v39 import (
    resolve_strategy_source_demands,
)
from scripts.run_spy_v56_multi_session_quote_replay import dates_in_window
from scripts.run_spy_v65_full_june_offline_simulator_readiness import inspect as v65_inspect

ROOT = Path(__file__).resolve().parents[1]
ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v69-spy-source-first-multiwindow-exact-options-census-v1"
V65 = "atlas-v65-full-horizon-spy-closed-bar-offline-source-gate-v1"
SOURCE_CENSORS = frozenset({
    "NOT_REGISTERED", "FAILED_RETRYABLE", "IN_FLIGHT",
    "NO_DATA_EXPLICIT",
})


class V69Error(ValueError):
    pass


def info(message):
    print(f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
          flush=True)


def signed(doc):
    return {**doc, "fingerprint": _fingerprint(doc)}


def write_signed(path, doc):
    if path.is_symlink() or path.exists():
        raise V69Error("V69_OUTPUT_ALREADY_EXISTS")
    value = signed(doc)
    with path.open("x", encoding="utf8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return value


def inspect_input(report, first, last):
    if (not isinstance(report, dict) or report.get("contract") != V65
            or report.get("start") != first.isoformat()
            or report.get("end") != last.isoformat()
            or report.get("provider_requests") != 0
            or report.get("broker_orders") != 0
            or report.get("fingerprint") != _fingerprint({
                k: v for k, v in report.items() if k != "fingerprint"
            })):
        raise V69Error("V69_ORIGINAL_OFFLINE_REPORT_INVALID")
    rows = report.get("session_reports")
    if (not isinstance(rows, list) or len(rows) == 0
            or len({row["session"] for row in rows}) != len(rows)):
        raise V69Error("V69_ORIGINAL_SESSION_COVERAGE_INVALID")
    for row in rows:
        # A source-incomplete eligible day must generate an underlying-data
        # requirement, not masquerade as a day with no breakout signal.
        # Tue/Thu weekday exclusions do not require option/spot acquisition.
        if row.get("weekday") in ("Monday", "Wednesday", "Friday"):
            if (row.get("original_minute_rows", 0) < 5
                    or row.get("signal_status") in (
                        "MISSING_OPENING_MINUTE",
                        "MISSING_MINUTE_BEFORE_SIGNAL",
                    )
                    or "NO_SOURCE_BARS_FOR_ELIGIBLE_DAY" in
                        row.get("native_source_warnings", [])):
                raise V69Error("V69_REQUIRED_SPY_MINUTE_SESSION_SOURCE_INCOMPLETE")
        if (row["fingerprint"] != _fingerprint({
                k: v for k, v in row.items() if k != "fingerprint"
            })):
            raise V69Error("V69_SESSION_FINGERPRINT_INVALID")
        replay = row["standalone_replay_report"]
        if (replay["fingerprint"] != _fingerprint({
                k: v for k, v in replay.items() if k != "fingerprint"
            }) or replay.get("actual_fills") != 0):
            raise V69Error("V69_ORIGINAL_REPLAY_INVALID")
        requirement = row["exact_option_requirement"]
        receipt = row["exact_option_receipt"]
        if (requirement is None) != (receipt is None):
            raise V69Error("V69_MISSING_REQUIREMENT_RECEIPT")
        if requirement is not None:
            if (not isinstance(receipt, dict)
                    or receipt.get("query_id") != _fingerprint(requirement)
                    or requirement.get("method") !=
                        "option_history_exact_quote_tape"
                    or requirement.get("kwargs", {}).get("symbol") != "SPY"
                    or requirement["kwargs"].get("date_et") != row["session"]):
                raise V69Error("V69_REQUIREMENT_IDENTITY_INVALID")
    return rows


def demands(rows):
    """Every selected contract, even an already archived one, is registered.

    V39 verifies the cached original or auto-acquires any missing exact query.
    Unknown prior provider dispatch stays blocked; different queries continue.
    """
    for row in rows:
        req = row["exact_option_requirement"]
        if req is None:
            continue
        contract = row["selected_contract"]
        if not contract:
            raise V69Error("V69_SELECTED_CONTRACT_MISSING")
        yield {
            "candidate_id": "SPY_" + row["session"] + "_" +
                contract["right"] + "_" + str(contract["strike"]),
            "purpose": "required_exact_entry_and_exit_tape",
            "method": req["method"],
            "kwargs": dict(req["kwargs"]),
        }


def summarize_chunk(before, after, source_resolution, first, last, index):
    before_rows = inspect_input(before, first, last)
    after_rows = inspect_input(after, first, last)
    prev = {r["session"]: r for r in before_rows}
    statuses = Counter()
    source_states = Counter()
    outstanding = []
    pnl_only_closed = "NOT_A_CUMULATIVE_ACCOUNT"
    for row in after_rows:
        original = prev.get(row["session"])
        if (not original
                or original["signal_fingerprint"] != row["signal_fingerprint"]
                or original["selected_contract"] != row["selected_contract"]
                or original["exact_option_requirement"] !=
                    row["exact_option_requirement"]
                or original["native_minute_source_sha256"] !=
                    row["native_minute_source_sha256"]):
            raise V69Error("V69_POST_SOURCE_SIGNAL_OR_UNDERLYING_DRIFT")
        req = row["exact_option_requirement"]
        if req is not None:
            receipt = row["exact_option_receipt"]
            state = receipt["state"]
            source_states[state] += 1
            if state != "ARCHIVED":
                outstanding.append({
                    "session": row["session"],
                    "query_id": receipt["query_id"],
                    "state": state,
                    "status": "SOURCE_REQUIREMENT_UNRESOLVED",
                    "not_a_trade_rejection": True,
                })
                # V65's original missing-source NO_ENTRY is an inventory
                # placeholder only, not a genuine simulation no-trade.
                if row["standalone_replay_disposition"] != "NO_ENTRY":
                    raise V69Error("V69_MISSING_SOURCE_CONTRADICTS_REPLAY")
                continue
        statuses[row["standalone_replay_disposition"]] += 1
    if source_resolution["source_uses_requested"] != sum(source_states.values()):
        raise V69Error("V69_SOURCE_REQUIREMENT_COUNT_DISAGREEMENT")
    return signed({
        "contract": CONTRACT,
        "chunk_index": index,
        "start": first.isoformat(), "end": last.isoformat(),
        "weekdays": len(after_rows),
        "selected_option_contracts": sum(source_states.values()),
        "original_v65_preflight_sha": before["fingerprint"],
        "original_v65_post_source_sha": after["fingerprint"],
        "source_resolution": source_resolution,
        "qualified_replay_status_counts": dict(sorted(statuses.items())),
        "source_state_counts": dict(sorted(source_states.items())),
        "unresolved_source_requirements": outstanding,
        "unresolved_positions": sum(
            1 for r in after_rows if
            r["standalone_replay_disposition"] == "UNRESOLVED_POSITION"
        ),
        "strategy_universe_demand_count_is_not_capped": True,
        "full_original_event_logs_saved_in_v65_report": True,
        "source_censor_not_counted_as_no_entry": True,
        "account_profit": pnl_only_closed,
        "historical_execution_or_alpha_proven": False,
        "broker_orders": 0,
    })


def run(start, end, output_dir, *, audit=v65_inspect,
        resolve=resolve_strategy_source_demands, emit=info,
        session_calendar=None):
    # Validate the desired date interval before creating output or making
    # requests; contiguous chunks retain the full date scope without a
    # fixed lifetime roster or source-count cap.
    days = list(dates_in_window(start, end))
    if not days:
        raise V69Error("V69_NO_WEEKDAY_SESSIONS")
    if output_dir.is_symlink() or output_dir.exists():
        raise V69Error("V69_OUTPUT_ALREADY_EXISTS")
    output_dir.mkdir(parents=True, exist_ok=False)
    groups = [days[i:i+30] for i in range(0, len(days), 30)]
    emit(f"START V69 days={len(days)} groups={len(groups)} "
         "source_mode=V39_CACHE_FIRST_AUTOMATIC_PROVIDER_ON_MISS "
         "unknown_prior_dispatch_not_retried=True broker_orders=0")
    chunk_summaries = []
    for index, group in enumerate(groups, 1):
        first, last = group[0], group[-1]
        prefix = f"chunk_{index:04d}"
        pre_path = output_dir / f"{prefix}.preflight.json"
        post_path = output_dir / f"{prefix}.replay.json"
        receipt_path = output_dir / f"{prefix}.sources.json"
        out_path = output_dir / f"{prefix}.summary.json"
        emit(f"STAGE_START V69 group={index}/{len(groups)} "
             f"dates={first}/{last} source_preflight_provider_calls=0")
        # Missing underlying minute unit is a distinct *blocking dependency*.
        # It must be acquired through a supported stock adapter; never fake
        # no-signal and never dispatch option requests without valid spot bars.
        try:
            preflight = audit(first, last, pre_path)
            original = inspect_input(preflight, first, last)
        except Exception as exc:
            error = write_signed(output_dir / f"{prefix}.blocked.json", {
                "contract": CONTRACT,
                "status": "UNDERLYING_OR_ORIGINAL_PREFLIGHT_BLOCKED",
                "start": first.isoformat(), "end": last.isoformat(),
                "error_class": type(exc).__name__,
                "stock_source_acquisition_or_geometry_review_required": True,
                "option_source_queries_dispatched": 0,
                "broker_orders": 0,
            })
            emit(f"STAGE_BLOCKED V69 original_stock_source group={index} "
                 f"error_type={type(exc).__name__} no_option_calls=True")
            chunk_summaries.append(error)
            continue

        source_events = Counter()
        needed = sum(r["exact_option_requirement"] is not None for r in original)
        complete = 0
        progress_mark = 10
        def progress(event, details):
            nonlocal complete, progress_mark
            source_events[event] += 1
            if event == "provider_dispatch":
                emit(f"PROVIDER_DISPATCH V69 group={index} "
                     f"query={details['query_id']} date={details['date_et']} "
                     "completion_fraction=UNKNOWN")
            if event in ("source_done", "source_blocked", "source_failed"):
                complete += 1
                while (needed > 0 and progress_mark <= 100
                       and 100*complete >= progress_mark*needed):
                    emit(f"PROGRESS_{progress_mark}PCT V69 group={index} "
                         f"source_requirements_completed={complete}/{needed} "
                         f"last_query={details['query_id']} status={details['status']}")
                    progress_mark += 10

        try:
            # V39 handles *any* new exact option contract generated by the
            # original strategy and auto-issues valid connected source calls.
            resolution = resolve(
                load_settings(ROOT, "development"),
                "spy_v55_v69_source_first_dev",
                demands(original),
                continue_on_error=True,
                on_progress=progress,
            )
            if (resolution.get("source_uses_requested") != needed
                    or resolution.get("provider_dispatch_attempts", -1) < 0):
                raise V69Error("V69_SOURCE_RESOLVER_INCOMPLETE")
            write_signed(receipt_path, {
                "contract": CONTRACT,
                "original_preflight_sha": preflight["fingerprint"],
                "runtime_source_receipt": resolution,
                "source_events": dict(source_events),
                "broker_orders": 0,
            })
        except Exception as exc:
            blocker = write_signed(output_dir / f"{prefix}.blocked.json", {
                "contract": CONTRACT,
                "status": "SOURCE_COORDINATION_BLOCKED",
                "start": first.isoformat(), "end": last.isoformat(),
                "error_class": type(exc).__name__,
                "source_requirements": needed,
                "completed_source_events": complete,
                "provider_dispatch_count_may_be_unknown": True,
                "broker_orders": 0,
            })
            chunk_summaries.append(blocker)
            emit(f"STAGE_BLOCKED V69 source_coordination group={index} "
                 f"error_type={type(exc).__name__}")
            continue
        try:
            after = audit(first, last, post_path)
            chunk = summarize_chunk(preflight, after, resolution, first, last, index)
            # summarize_chunk already signed; do not apply a second fingerprint.
            if chunk["fingerprint"] != _fingerprint({
                    k: v for k, v in chunk.items() if k != "fingerprint"
            }):
                raise V69Error("V69_CHUNK_SUMMARY_FINGERPRINT_INVALID")
            with out_path.open("x", encoding="utf8") as stream:
                json.dump(chunk, stream, sort_keys=True, indent=2, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            chunk_summaries.append(chunk)
            emit(f"STAGE_PASS V69 group={index}/{len(groups)} "
                 f"source_states={chunk['source_state_counts']} "
                 f"replays={chunk['qualified_replay_status_counts']} "
                 f"unresolved_sources={len(chunk['unresolved_source_requirements'])} "
                 f"unresolved_exits={chunk['unresolved_positions']}")
        except Exception as exc:
            blocked = write_signed(output_dir / f"{prefix}.blocked.json", {
                "contract": CONTRACT,
                "status": "POST_ACQUISITION_REPLAY_UNVERIFIED",
                "start": first.isoformat(), "end": last.isoformat(),
                "error_class": type(exc).__name__,
                "original_preflight_sha": preflight["fingerprint"],
                "source_receipt_path": str(receipt_path),
                "provider_requests_may_have_completed": True,
                "broker_orders": 0,
            })
            chunk_summaries.append(blocked)
            emit(f"STAGE_BLOCKED V69 post_source_replay group={index} "
                 f"error_type={type(exc).__name__}")
    blocked = [
        row for row in chunk_summaries
        if ("status" in row and row["status"].endswith("BLOCKED"))
        or row.get("status") == "SOURCE_COORDINATION_BLOCKED"
        or row.get("unresolved_source_requirements")
    ]
    unresolved_positions = sum(
        row.get("unresolved_positions", 0) for row in chunk_summaries
    )
    summary = write_signed(output_dir / "summary.json", {
        "contract": CONTRACT, "start": start.isoformat(), "end": end.isoformat(),
        "weekdays": len(days), "chunks": len(groups),
        "completed_chunk_reports": len(chunk_summaries),
        "chunk_summaries": [
            {
                "index": i + 1, "start": x["start"], "end": x["end"],
                "status": x.get("status", "SOURCE_CHECKED_AND_REPLAYED"),
                "fingerprint": x["fingerprint"],
                "source_states": x.get("source_state_counts"),
                "replay_statuses": x.get("qualified_replay_status_counts"),
                "unresolved_sources": len(x.get("unresolved_source_requirements", [])),
                "unresolved_positions": x.get("unresolved_positions"),
                "blocked": bool(x in blocked),
            } for i, x in enumerate(chunk_summaries)
        ],
        "status": "COMPLETE_WITH_SOURCE_OR_STOCK_BLOCKERS"
                  if blocked else "COMPLETE_SOURCE_CENSUS_WITH_OPEN_POSITIONS"
                  if unresolved_positions else "COMPLETE_SOURCE_CENSUS_QUOTE_REFERENCE_ONLY",
        "unresolved_source_or_underlying_chunks": len(blocked),
        "unresolved_option_positions": unresolved_positions,
        "provider_calls": "ACTUAL_COUNTS_IN_EACH_CHUNK_SOURCE_RECEIPT",
        "all_strategy_source_demands_persisted_or_blocker_reported": True,
        "closed_day_cash_not_chained_over_unresolved_position": True,
        "historical_profitability_proven": False,
        "broker_orders": 0,
    })
    emit(f"COMPLETE V69 status={summary['status']} "
         f"chunks={len(chunk_summaries)}/{len(groups)} "
         f"unresolved_chunks={len(blocked)} "
         f"unresolved_positions={unresolved_positions} "
         f"output={output_dir / 'summary.json'} broker_orders=0")
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=date.fromisoformat, required=True)
    p.add_argument("--end", type=date.fromisoformat, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        result = run(a.start, a.end, a.output_dir)
        return 0 if result["status"].startswith("COMPLETE_SOURCE_CENSUS") else 2
    except Exception as exc:
        info(f"STOPPED V69 error_class={type(exc).__name__} "
             "original_receipts_preserved=True no_broker_orders=True")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
