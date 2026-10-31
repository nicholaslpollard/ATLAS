from __future__ import annotations

"""V67: one guarded workstation execution for V66 acquisition + V65 re-audit.

Acquire all new exact June source needs first, independently, with V66's
no-ambiguous-retry semantics. Then re-evaluate the same ten dates using the
unchanged original V55/V65 strategy. Never chain standalone cash or invent a
price for missing, bad, or unresolved original quotes.
"""

import argparse
from datetime import date, datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from packages.data.marketdata_candidate_chain_cache_v1 import _fingerprint
from scripts.run_spy_v65_full_june_offline_simulator_readiness import (
    CONTRACT as V65_CONTRACT, inspect,
)
from scripts.run_spy_v66_three_missing_exact_tape_acquisition import (
    CONTRACT as V66_CONTRACT, V65_SHA, dispatch, input_sessions,
    write_once,
)

ET = ZoneInfo("America/New_York")
CONTRACT = "atlas-v67-source-acquire-and-independent-replay-joint-acceptance-v1"


class V67Error(ValueError):
    pass


def announce(message: str) -> None:
    print(
        f"[{datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}] {message}",
        flush=True,
    )


def signed(report: dict) -> dict:
    return {**report, "fingerprint": _fingerprint(report)}


def valid_saved(path: Path, returned: dict) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        persisted = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return False
    return (
        persisted == returned
        and persisted.get("fingerprint")
        == _fingerprint({k: v for k, v in persisted.items() if k != "fingerprint"})
    )


def run(
    original_v65: Path, output_dir: Path, *,
    verify_parent=input_sessions, acquire=dispatch, replay=inspect,
    emit=announce,
) -> dict:
    # All preconditions, including original parent report SHA and exact contract
    # identities, are checked BEFORE creating output or invoking any provider.
    parent, scopes = verify_parent(original_v65)
    if parent != V65_SHA or len(scopes) != 3:
        raise V67Error("V67_ORIGINAL_V65_ACCEPTANCE_REQUIRED")
    if output_dir.is_symlink() or output_dir.exists():
        raise V67Error("V67_OUTPUT_ALREADY_EXISTS")
    output_dir.mkdir(parents=True, exist_ok=False)
    report = {
        "contract": CONTRACT,
        "original_v65_fingerprint": parent,
        "original_source_requirements": len(scopes),
        "provider_attempts_are_only_for_verified_missing_exact_source": True,
        "all_independent_demands_attempted_without_fixed_lifetime_limit": True,
        "broker_orders": 0,
        "cumulative_cash_reconstructed": False,
        "historical_fills_proven": False,
        "historical_profitability_proven": False,
        "v66_status": None,
        "v66_fingerprint": None,
        "v65_refreshed_fingerprint": None,
        "v65_refreshed_counts": None,
        "v65_refreshed_source_counts": None,
        "status": "SOURCE_ACQUISITION_NOT_STARTED",
    }
    emit("START V67 combined_source_and_replay stage=V66 "
         "sources=3 source_calls=cache_first_bounded broker_orders=0")
    try:
        acquired = acquire(original_v65, output_dir / "sources")
        if (acquired.get("contract") != V66_CONTRACT
                or acquired.get("frozen_v65_report_fingerprint") != parent
                or not valid_saved(output_dir / "sources" / "summary.json", acquired)):
            raise V67Error("V67_SOURCE_ACCEPTANCE_OR_FINGERPRINT_INVALID")
        report["v66_status"] = acquired["status"]
        report["v66_fingerprint"] = acquired["fingerprint"]
        report["v66_result_counts"] = acquired["result_counts"]
        report["new_provider_request_count_upper_bound"] = (
            acquired["new_provider_request_count_upper_bound"]
        )
        emit("STAGE_PASS V66 source requests completed="
             f"{acquired['completed_scopes']}/3 "
             f"outcomes={acquired['result_counts']} "
             f"provider_attempt_bound={acquired['new_provider_request_count_upper_bound']}")
    except Exception as exc:
        report["status"] = "SOURCE_ACQUISITION_UNVERIFIED"
        report["failure_class"] = type(exc).__name__
        emit(f"STAGE_BLOCKED V66 exception_class={type(exc).__name__} "
             "original_source_receipts_preserved=True")
        output = signed(report)
        write_once(output_dir / "summary.json", output)
        return output

    # Do this even if an independent provider call was censored: other
    # successfully archived dates still deserve offline replay and audit.
    emit("STAGE_START V65 unchanged_10_day_offline_replay "
         "reuse_verified_sources=True new_provider_calls=0")
    try:
        refreshed_path = output_dir / "refreshed_v65.json"
        refreshed = replay(
            date(2025, 6, 9), date(2025, 6, 20), refreshed_path,
        )
        if (refreshed.get("contract") != V65_CONTRACT
                or refreshed.get("start") != "2025-06-09"
                or refreshed.get("end") != "2025-06-20"
                or refreshed.get("provider_requests") != 0
                or refreshed.get("broker_orders") != 0
                or not valid_saved(refreshed_path, refreshed)):
            raise V67Error("V67_REFRESHED_V65_INTEGRITY_UNQUALIFIED")
        report["v65_refreshed_fingerprint"] = refreshed["fingerprint"]
        report["v65_refreshed_counts"] = refreshed["status_counts"]
        report["v65_refreshed_source_counts"] = (
            refreshed["option_source_state_counts"]
        )
        report["status"] = (
            "COMPLETE_SOURCE_AND_OFFLINE_CENSUS"
            if acquired["status"] == "COMPLETE_SOURCE_CENSUS"
            else "OFFLINE_CENSUS_COMPLETE_WITH_UNRESOLVED_SOURCE_DEMANDS"
        )
        emit("STAGE_PASS V65 original_replay="
             f"{refreshed['status_counts']} "
             f"sources={refreshed['option_source_state_counts']} "
             "cumulative_cash_not_reconstructed=True")
    except Exception as exc:
        report["status"] = "SOURCE_COMPLETED_OFFLINE_REPLAY_UNVERIFIED"
        report["failure_class"] = type(exc).__name__
        emit(f"STAGE_BLOCKED V65 exception_class={type(exc).__name__} "
             "source_receipts_preserved=True")
    final = signed(report)
    write_once(output_dir / "summary.json", final)
    emit(f"COMPLETE V67 status={final['status']} "
         f"summary={output_dir / 'summary.json'} "
         "broker_orders=0 historical_alpha_proven=False")
    return final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--v65-report", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        doc = run(args.v65_report, args.output_dir)
        return 0 if doc["status"] == "COMPLETE_SOURCE_AND_OFFLINE_CENSUS" else 2
    except Exception as exc:
        announce(f"STOPPED V67 error_class={type(exc).__name__} "
                 "no_broker_orders=True no_automatic_ambiguous_retry=True")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
