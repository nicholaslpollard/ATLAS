from __future__ import annotations

"""Run the zero-provider intraday stock-exit clock resolver.

This runner opens only accepted local Alpaca SIP raw 1-minute Parquet units needed
for STOP/TARGET exit sessions in the frozen pre-2026 CALL cohort. TIME exits use
the official exchange close and therefore do not require minute materialization.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
import json
import os
import sys
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import duckdb

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    _binding_from_plan,
    _load_frozen_minute_plan,
)
from packages.core.enums import SessionSegment
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import load_settings
from packages.data.intraday_semantics_audit import (
    ALPACA_V2_SOURCE_PREFIX,
    MINUTE_DATASET,
    MINUTE_TIMEFRAME,
)
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_native_stock_open_v1 import OUTPUT_REL as NATIVE_REL
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    SCENARIO_REL as CONTINUOUS_REL,
)
from packages.simulation.multiyear_historical_eod_option_account_replay_v1 import (
    SCENARIO_REL as BASE_REL,
)
from packages.simulation.multiyear_intraday_stock_exit_clock_v1 import (
    OUTPUT_REL,
    build_intraday_exit_clock_report,
    minute_source_requirements,
    resolve_intraday_exit_case,
    select_intraday_exit_clock_cases,
)


class IntradayStockExitClockRunnerError(ValueError):
    pass


def _resolve_signed_artifact(
    settings,
    stem: str,
    fingerprint: str,
    field: str,
) -> tuple[Path, dict[str, Any]]:
    path = settings.resolved_path(f"{stem}_{fingerprint[:16]}.json")
    if path.is_symlink() or not path.is_file():
        raise IntradayStockExitClockRunnerError(f"required artifact unavailable: {path}")
    value = _read_object(path)
    _check_signature(value, field)
    if value.get(field) != fingerprint:
        raise IntradayStockExitClockRunnerError(
            f"required artifact fingerprint changed: {path}"
        )
    return path, value


def _resolve_native(settings, fingerprint: str) -> tuple[Path, dict[str, Any]]:
    prefix = settings.resolved_path(NATIVE_REL)
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(prefix.parent.glob(prefix.name + "_*.json")):
        if path.is_symlink() or not path.is_file():
            continue
        value = _read_object(path)
        if value.get("source_fingerprint") == fingerprint:
            _check_signature(value, "source_fingerprint")
            matches.append((path, value))
    if len(matches) != 1:
        raise IntradayStockExitClockRunnerError(
            f"expected exactly one native source for {fingerprint}, found {len(matches)}"
        )
    return matches[0]


def _case_month(case: dict[str, Any]) -> tuple[int, int]:
    session = date.fromisoformat(case["daily_exit_session"])
    return session.year, session.month


def _targeted_bindings(
    source: B35DevelopmentMinuteSource,
    cases: list[dict[str, Any]],
) -> tuple[list[Any], dict[tuple[str, str], Any], str, str]:
    requirements = minute_source_requirements(cases)
    if not requirements:
        raise IntradayStockExitClockRunnerError("no STOP/TARGET minute requirements")
    all_days = [
        date.fromisoformat(day)
        for symbols in requirements.values()
        for days in symbols.values()
        for day in days
    ]
    records, raw_sha, compressed_sha = _load_frozen_minute_plan(
        source.layout,
        start_session=min(all_days),
        end_session=max(all_days),
    )
    selected_records = []
    for record in records:
        key = (int(record["year"]), int(record["month"]))
        needed = requirements.get(key)
        if not needed:
            continue
        window_start = date.fromisoformat(str(record["window_start"]))
        window_end = date.fromisoformat(str(record["window_end_exclusive"]))
        symbols = set(str(value) for value in record["symbols"])
        include = any(
            any(
                window_start <= date.fromisoformat(day) < window_end
                for day in needed.get(symbol, set())
            )
            for symbol in symbols.intersection(needed)
        )
        if include:
            selected_records.append(record)
    bindings = [_binding_from_plan(source.layout, record) for record in selected_records]
    if not bindings:
        raise IntradayStockExitClockRunnerError("no targeted minute bindings selected")

    by_symbol_day: dict[tuple[str, str], list[Any]] = {}
    for binding in bindings:
        needed = requirements.get((binding.year, binding.month), {})
        for symbol in binding.symbols:
            for day in needed.get(symbol, set()):
                parsed = date.fromisoformat(day)
                if binding.window_start <= parsed < binding.window_end_exclusive:
                    by_symbol_day.setdefault((symbol, day), []).append(binding)

    exact: dict[tuple[str, str], Any] = {}
    missing: list[tuple[str, str]] = []
    ambiguous: list[tuple[str, str]] = []
    for symbols in requirements.values():
        for symbol, days in symbols.items():
            for day in days:
                candidates = by_symbol_day.get((symbol, day), [])
                if len(candidates) == 1:
                    exact[(symbol, day)] = candidates[0]
                elif not candidates:
                    missing.append((symbol, day))
                else:
                    ambiguous.append((symbol, day))
    if missing or ambiguous:
        raise IntradayStockExitClockRunnerError(
            "targeted minute binding coverage is not exact: "
            f"missing={len(missing)} ambiguous={len(ambiguous)}"
        )
    return bindings, exact, raw_sha, compressed_sha


def _read_binding_rows(
    *,
    settings,
    binding,
    requested: dict[str, set[str]],
    duckdb_threads: int,
) -> tuple[str, dict[tuple[str, str], list[dict[str, Any]]], int]:
    verifier = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
    try:
        verifier.verify_unit(binding)
    finally:
        verifier.close()

    symbols = sorted(requested)
    days = sorted({day for values in requested.values() for day in values})
    if not symbols or not days:
        raise IntradayStockExitClockRunnerError("binding read has no requested keys")

    symbol_marks = ",".join("?" for _ in symbols)
    day_marks = ",".join("?" for _ in days)
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"PRAGMA threads={max(1, int(duckdb_threads))}")
        rows = con.execute(
            f"""
            SELECT
                symbol,
                timestamp_utc,
                CAST(session_date AS VARCHAR) AS session_date,
                session_segment,
                open,
                high,
                low,
                close,
                timeframe,
                dataset,
                provider,
                source_id,
                is_adjusted
            FROM read_parquet(?, hive_partitioning=false)
            WHERE symbol IN ({symbol_marks})
              AND CAST(session_date AS VARCHAR) IN ({day_marks})
              AND session_segment = ?
            ORDER BY symbol, session_date, timestamp_utc
            """,
            [
                str(binding.canonical_path),
                *symbols,
                *days,
                SessionSegment.REGULAR.value,
            ],
        ).fetchall()
    finally:
        con.close()

    expected_source = ALPACA_V2_SOURCE_PREFIX + binding.unit_id
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for (
        symbol,
        timestamp,
        session_day,
        segment,
        open_,
        high,
        low,
        close,
        timeframe,
        dataset,
        provider,
        source_id,
        is_adjusted,
    ) in rows:
        symbol = str(symbol)
        session_day = str(session_day)
        if session_day not in requested.get(symbol, set()):
            continue
        if (
            str(segment) != SessionSegment.REGULAR.value
            or str(timeframe) != MINUTE_TIMEFRAME
            or str(dataset) != MINUTE_DATASET
            or str(provider) != "alpaca"
            or str(source_id) != expected_source
            or is_adjusted is not False
        ):
            raise IntradayStockExitClockRunnerError(
                f"minute semantic identity changed in {binding.unit_id}"
            )
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise IntradayStockExitClockRunnerError("minute timestamp lost timezone")
        identity = (symbol, session_day, timestamp.isoformat())
        if identity in seen:
            raise IntradayStockExitClockRunnerError("duplicate requested minute key")
        seen.add(identity)
        grouped.setdefault((symbol, session_day), []).append(
            {
                "timestamp_utc": timestamp,
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
            }
        )
    return binding.unit_id, grouped, len(rows)


def _persist(settings, report: dict[str, Any]) -> tuple[Path, str]:
    fingerprint = report["intraday_clock_fingerprint"]
    path = settings.resolved_path(f"{OUTPUT_REL}_{fingerprint[:16]}.json")
    encoded = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != encoded:
            raise IntradayStockExitClockRunnerError(
                "existing immutable intraday clock report differs"
            )
        return path, "REUSED_IDENTICAL_INTRADAY_STOCK_EXIT_CLOCK"
    with path.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != encoded:
        raise IntradayStockExitClockRunnerError(
            "intraday clock report write/readback failed"
        )
    return path, "WRITTEN_IMMUTABLE_INTRADAY_STOCK_EXIT_CLOCK"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve pre-2026 CALL-cohort stock STOP/TARGET/TIME exits to accepted "
            "Alpaca SIP raw 1-minute clocks and produce generic at-time option NBBO "
            "quote demands. Zero provider requests."
        )
    )
    parser.add_argument(
        "--continuous-scenario",
        type=Path,
        required=True,
        help="Exact immutable Continuous Dynamic Exit V2 scenario artifact.",
    )
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--duckdb-threads-per-worker", type=int, default=1)
    args = parser.parse_args(argv)
    if args.workers < 1 or args.workers > 8:
        raise SystemExit("--workers must be between 1 and 8")
    if args.duckdb_threads_per_worker < 1 or args.duckdb_threads_per_worker > 4:
        raise SystemExit("--duckdb-threads-per-worker must be between 1 and 4")

    print("ATLAS INTRADAY STOCK EXIT CLOCK V1", flush=True)
    print(
        "  ZERO provider GETs. Reuses accepted Alpaca SIP raw 1-minute source. "
        "No option prices are read; output is an exact future at-time NBBO demand plan.",
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
            raise IntradayStockExitClockRunnerError("continuous scenario unavailable")
        continuous = _read_object(continuous_path)
        _check_signature(continuous, "scenario_fingerprint")
        base_path, base = _resolve_signed_artifact(
            settings,
            BASE_REL,
            continuous["base_scenario_fingerprint"],
            "scenario_fingerprint",
        )
        native_path, native = _resolve_native(settings, base["native_source_fingerprint"])
        cases = select_intraday_exit_clock_cases(native, base, continuous)
        print(
            f"  selected pre-2026 CALL/policy/stock-exit cases={len(cases)}",
            flush=True,
        )
        disposition_counts: dict[str, int] = {}
        for case in cases:
            key = str(case["daily_exit_disposition"])
            disposition_counts[key] = disposition_counts.get(key, 0) + 1
        print(f"  daily_exit_dispositions={dict(sorted(disposition_counts.items()))}", flush=True)

        source = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
        bindings, binding_by_key, raw_plan_sha, compressed_plan_sha = _targeted_bindings(
            source, cases
        )
        source.close()
        stop_target_cases = [
            case for case in cases if case["daily_exit_disposition"] != "TIME"
        ]
        assigned: dict[str, list[dict[str, Any]]] = {}
        binding_by_id = {binding.unit_id: binding for binding in bindings}
        requested_by_unit: dict[str, dict[str, set[str]]] = {}
        for case in stop_target_cases:
            key = (case["ticker"], case["daily_exit_session"])
            binding = binding_by_key[key]
            assigned.setdefault(binding.unit_id, []).append(case)
            requested_by_unit.setdefault(binding.unit_id, {}).setdefault(
                case["ticker"], set()
            ).add(case["daily_exit_session"])

        print(
            "  targeted minute source "
            f"bindings={len(assigned)} "
            f"stop_target_cases={len(stop_target_cases)} "
            f"unique_symbol_exit_sessions={len(binding_by_key)} "
            f"workers={args.workers}",
            flush=True,
        )

        resolved: list[dict[str, Any]] = []
        calendar = MarketCalendar(
            exchange=settings.data.calendar.exchange,
            market_tz=ZoneInfo(settings.data.calendar.market_timezone),
        )
        for case in cases:
            if case["daily_exit_disposition"] == "TIME":
                resolved.append(
                    resolve_intraday_exit_case(case, (), calendar=calendar)
                )

        total_rows_read = 0
        completed = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    _read_binding_rows,
                    settings=settings,
                    binding=binding_by_id[unit_id],
                    requested=requested_by_unit[unit_id],
                    duckdb_threads=args.duckdb_threads_per_worker,
                ): unit_id
                for unit_id in sorted(assigned)
            }
            for future in as_completed(futures):
                unit_id, grouped, rows_read = future.result()
                total_rows_read += rows_read
                for case in assigned[unit_id]:
                    bars = grouped.get(
                        (case["ticker"], case["daily_exit_session"]), []
                    )
                    resolved.append(
                        resolve_intraday_exit_case(case, bars, calendar=calendar)
                    )
                completed += 1
                if completed % 25 == 0 or completed == len(futures):
                    print(
                        "  minute_source_progress "
                        f"{completed}/{len(futures)} bindings verified/read "
                        f"rows_read={total_rows_read}",
                        flush=True,
                    )

        if len(resolved) != len(cases):
            raise IntradayStockExitClockRunnerError(
                f"resolved case count {len(resolved)} != selected {len(cases)}"
            )

        source_metadata = {
            "contract": "atlas-b35-development-minute-source-v2-native-plan-exact-path-physical",
            "provider": "alpaca",
            "feed": "sip",
            "provider_timeframe": "1Min",
            "canonical_timeframe": "1m",
            "adjustment": "raw",
            "interval_timestamp": "left_edge_start",
            "minute_action_clock": "bar_timestamp_plus_one_minute",
            "missing_minutes": "preserve_absence_no_synthesis",
            "native_plan_sha256": raw_plan_sha,
            "native_plan_file_sha256": compressed_plan_sha,
            "targeted_binding_count": len(assigned),
            "targeted_bindings_sha_verified": len(assigned),
            "unique_symbol_exit_session_keys": len(binding_by_key),
            "physical_rows_read": total_rows_read,
            "provider_calls": 0,
            "protected_2026_rows_read": 0,
        }
        report = build_intraday_exit_clock_report(
            native=native,
            base=base,
            continuous=continuous,
            source_metadata=source_metadata,
            resolved_rows=resolved,
        )
        output_path, action = _persist(settings, report)

        print(f"  continuous_scenario={continuous_path}", flush=True)
        print(f"  base_scenario={base_path}", flush=True)
        print(f"  native_source={native_path}", flush=True)
        print(
            "  intraday_clock "
            f"cases={report['pre2026_call_policy_stock_exit_cases']} "
            f"clock_ready={report['clock_ready_cases']} "
            f"fraction={report['clock_ready_fraction']:.6f} "
            f"exit_at_or_before_0935={report['stock_exit_at_or_before_option_decision']} "
            f"fraction={report['stock_exit_at_or_before_option_decision_fraction']:.6f}",
            flush=True,
        )
        print(
            "  daily_vs_minute "
            f"changed={report['daily_vs_minute_disposition_changed']} "
            f"fraction={report['daily_vs_minute_disposition_changed_fraction']:.6f} "
            f"daily={report['daily_dispositions']} "
            f"minute={report['minute_dispositions']}",
            flush=True,
        )
        print(f"  statuses={report['statuses']}", flush=True)
        print(
            f"  minutes_after_option_decision={report['minutes_after_option_decision']}",
            flush=True,
        )
        demand = report["option_quote_demand"]
        print(
            "  future_option_quote_demand "
            f"entry_members={demand['entry_case_members']} "
            f"exit_members={demand['exit_case_members']} "
            f"unique_at_time_nbbo_queries={demand['unique_at_time_nbbo_queries']} "
            "provider_requests_performed=0",
            flush=True,
        )
        for year, values in report["by_year"].items():
            print(f"  year={year} {values}", flush=True)
        print(f"  intraday_clock={action} / {output_path}", flush=True)
        print(
            "  COMPLETE provider_requests=0 protected_2026_outcomes_read=0 "
            "historical_fills_verified=0 historical_account_pnl_authority=False "
            "strategy_evidence_authority=False paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"INTRADAY STOCK EXIT CLOCK STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No provider fallback or paid request is authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
