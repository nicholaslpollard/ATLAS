from __future__ import annotations

"""Run the zero-provider Continuous V2 / EOD option-entry clock closeout."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_native_stock_open_v1 import OUTPUT_REL as NATIVE_REL
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    SCENARIO_REL as CONTINUOUS_REL,
)
from packages.simulation.multiyear_eod_option_entry_clock_closeout_v1 import (
    OUTPUT_REL,
    build_eod_option_entry_clock_closeout,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_REL as BASE_REL,
)


class EntryClockCloseoutRunnerError(ValueError):
    pass


def _resolve_signed_artifact(settings, stem: str, fingerprint: str, field: str) -> tuple[Path, dict]:
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise EntryClockCloseoutRunnerError(f"required artifact unavailable: {path}")
    value = _read_object(path)
    _check_signature(value, field)
    if value.get(field) != fingerprint:
        raise EntryClockCloseoutRunnerError(f"required artifact fingerprint changed: {path}")
    return path, value


def _resolve_native(settings, fingerprint: str) -> tuple[Path, dict]:
    prefix = settings.resolved_path(NATIVE_REL)
    matches: list[tuple[Path, dict]] = []
    for path in sorted(prefix.parent.glob(prefix.name + "_*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        value = _read_object(path)
        if value.get("source_fingerprint") == fingerprint:
            _check_signature(value, "source_fingerprint")
            matches.append((path, value))
    if len(matches) != 1:
        raise EntryClockCloseoutRunnerError(
            f"expected exactly one native source for {fingerprint}, found {len(matches)}"
        )
    return matches[0]


def _persist(settings, report: dict) -> tuple[Path, str]:
    fingerprint = report["closeout_fingerprint"]
    path = settings.resolved_path(f"{OUTPUT_REL}_{fingerprint[:16]}.json")
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != encoded:
            raise EntryClockCloseoutRunnerError("existing immutable closeout differs")
        return path, "REUSED_IDENTICAL_ENTRY_CLOCK_CLOSEOUT"
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != encoded:
        raise EntryClockCloseoutRunnerError("entry-clock closeout write/readback failed")
    return path, "WRITTEN_IMMUTABLE_ENTRY_CLOCK_CLOSEOUT"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Close Continuous Dynamic Exit V2 and quantify stock-decision to historical "
            "EOD option-entry clock translation. Zero provider requests."
        )
    )
    parser.add_argument(
        "--continuous-scenario",
        type=Path,
        required=True,
        help="Exact immutable Continuous Dynamic Exit V2 scenario artifact.",
    )
    args = parser.parse_args(argv)

    print("ATLAS CONTINUOUS V2 / EOD OPTION ENTRY CLOCK CLOSEOUT", flush=True)
    print(
        "  ZERO provider GETs. No new exit policy. No contract reselection. "
        "Measures V2 boundary saturation and stock-to-option entry-clock drift.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        settings.assert_external_storage_binding("research_evidence")

        continuous_path = (
            args.continuous_scenario
            if args.continuous_scenario.is_absolute()
            else settings.resolved_path(args.continuous_scenario)
        )
        if continuous_path.is_symlink() or not continuous_path.is_file():
            raise EntryClockCloseoutRunnerError("continuous scenario unavailable")
        continuous = _read_object(continuous_path)
        _check_signature(continuous, "scenario_fingerprint")

        base_path, base = _resolve_signed_artifact(
            settings,
            BASE_REL,
            continuous["base_scenario_fingerprint"],
            "scenario_fingerprint",
        )
        native_path, native = _resolve_native(
            settings,
            base["native_source_fingerprint"],
        )
        report = build_eod_option_entry_clock_closeout(native, base, continuous)
        output_path, action = _persist(settings, report)

        v2 = report["continuous_v2"]
        clock = report["entry_clock_translation"]
        print(f"  continuous_scenario={continuous_path}", flush=True)
        print(f"  base_scenario={base_path}", flush=True)
        print(f"  native_source={native_path}", flush=True)
        print(
            "  V2 saturation "
            f"policy_cases={v2['continuous_policy_cases']} "
            f"stop_at_3pct={v2['stop_at_3pct_count']} "
            f"({v2['stop_at_3pct_fraction']:.6f}) "
            f"target_at_5pct={v2['target_at_5pct_count']} "
            f"({v2['target_at_5pct_fraction']:.6f})",
            flush=True,
        )
        print(f"  stop_distribution={v2['stop_distribution']}", flush=True)
        print(f"  target_distribution={v2['target_distribution']}", flush=True)
        print(
            "  entry_clock "
            f"causal_eod_call_entries={clock['causal_eod_call_entries']} "
            f"stock_exit_not_after_option_entry={clock['stock_exit_not_after_option_entry']} "
            f"fraction={clock['stock_exit_not_after_option_entry_fraction']}",
            flush=True,
        )
        print(f"  session_lag={clock['session_lag']}", flush=True)
        print(f"  elapsed_hours={clock['elapsed_hours']}", flush=True)
        print(
            "  underlying_move_before_option_entry="
            f"{clock['underlying_move_before_option_entry']}",
            flush=True,
        )
        print(
            "  absolute_underlying_move_before_option_entry="
            f"{clock['absolute_underlying_move_before_option_entry']}",
            flush=True,
        )
        print(
            f"  absolute_move_threshold_counts={clock['absolute_move_threshold_counts']}",
            flush=True,
        )
        print(
            f"  moneyness_at_raw_open={clock['moneyness_at_raw_open']} "
            f"moneyness_at_option_entry={clock['moneyness_at_option_entry']} "
            f"changed={clock['moneyness_changed']} "
            f"fraction={clock['moneyness_changed_fraction']}",
            flush=True,
        )
        for year, values in report["by_year"].items():
            print(f"  year={year} {values}", flush=True)
        print(f"  closeout={action} / {output_path}", flush=True)
        print(
            "  COMPLETE provider_requests=0 protected_2026_outcomes_read=0 "
            "historical_fills_verified=0 historical_account_pnl_authority=False "
            "strategy_evidence_authority=False paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"EOD OPTION ENTRY CLOCK CLOSEOUT STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No provider fallback or paid request is authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
