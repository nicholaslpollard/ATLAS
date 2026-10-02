from __future__ import annotations

"""Run the zero-provider causal 09:35 stock-spot / option-candidate gate."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, time
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
from packages.core.settings import load_settings
from packages.data.intraday_semantics_audit import (
    ALPACA_V2_SOURCE_PREFIX,
    MINUTE_DATASET,
    MINUTE_TIMEFRAME,
)
from packages.data.marketdata_candidate_expansion_v1 import _read_object
from packages.data.multiyear_option_quote_reuse_handoff_v1 import _check_signature
from packages.simulation.multiyear_option_decision_spot_v1 import (
    OUTPUT_REL,
    build_decision_spot_report,
    minute_source_requirements,
    resolve_decision_spot,
    select_decision_spot_cases,
)


class OptionDecisionSpotRunnerError(ValueError):
    pass


def _targeted_bindings(
    source: B35DevelopmentMinuteSource,
    cases: list[dict[str, Any]],
) -> tuple[list[Any], dict[tuple[str, str], Any], str, str]:
    requirements = minute_source_requirements(cases)
    all_days = [
        date.fromisoformat(day)
        for symbols in requirements.values()
        for days in symbols.values()
        for day in days
    ]
    if not all_days:
        raise OptionDecisionSpotRunnerError("no entry-session minute requirements")
    records, raw_sha, compressed_sha = _load_frozen_minute_plan(
        source.layout,
        start_session=min(all_days),
        end_session=max(all_days),
    )
    selected_records = []
    for record in records:
        needed = requirements.get((int(record["year"]), int(record["month"])))
        if not needed:
            continue
        window_start = date.fromisoformat(str(record["window_start"]))
        window_end = date.fromisoformat(str(record["window_end_exclusive"]))
        symbols = set(str(value) for value in record["symbols"])
        if any(
            any(
                window_start <= date.fromisoformat(day) < window_end
                for day in needed.get(symbol, set())
            )
            for symbol in symbols.intersection(needed)
        ):
            selected_records.append(record)

    bindings = [_binding_from_plan(source.layout, record) for record in selected_records]
    if not bindings:
        raise OptionDecisionSpotRunnerError("no targeted entry-session minute bindings")

    by_key: dict[tuple[str, str], list[Any]] = {}
    for binding in bindings:
        needed = requirements.get((binding.year, binding.month), {})
        for symbol in binding.symbols:
            for day in needed.get(symbol, set()):
                parsed = date.fromisoformat(day)
                if binding.window_start <= parsed < binding.window_end_exclusive:
                    by_key.setdefault((symbol, day), []).append(binding)

    exact: dict[tuple[str, str], Any] = {}
    missing = ambiguous = 0
    for symbols in requirements.values():
        for symbol, days in symbols.items():
            for day in days:
                found = by_key.get((symbol, day), [])
                if len(found) == 1:
                    exact[(symbol, day)] = found[0]
                elif not found:
                    missing += 1
                else:
                    ambiguous += 1
    if missing or ambiguous:
        raise OptionDecisionSpotRunnerError(
            f"entry-minute binding coverage is not exact: missing={missing} ambiguous={ambiguous}"
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

    request_rows = [
        (
            symbol,
            day,
            datetime.combine(
                date.fromisoformat(day),
                time(9, 34),
                tzinfo=EASTERN,
            ).astimezone(ZoneInfo("UTC")),
        )
        for symbol in sorted(requested)
        for day in sorted(requested[symbol])
    ]
    if not request_rows:
        raise OptionDecisionSpotRunnerError("binding read has no requested keys")

    con = duckdb.connect(":memory:")
    try:
        con.execute(f"PRAGMA threads={max(1, int(duckdb_threads))}")
        con.execute(
            """
            CREATE TEMP TABLE requested_decision_spots(
                symbol VARCHAR,
                session_date DATE,
                cutoff_utc TIMESTAMPTZ
            )
            """
        )
        con.executemany(
            "INSERT INTO requested_decision_spots VALUES (?, CAST(? AS DATE), ?)",
            request_rows,
        )
        physical = con.execute(
            """
            SELECT
                p.symbol,
                p.timestamp_utc,
                CAST(p.session_date AS VARCHAR) AS session_date,
                p.session_segment,
                p.close,
                p.timeframe,
                p.dataset,
                p.provider,
                p.source_id,
                p.is_adjusted
            FROM read_parquet(?, hive_partitioning=false) p
            JOIN requested_decision_spots r
              ON p.symbol = r.symbol
             AND p.session_date = r.session_date
            WHERE p.session_segment = ?
              AND p.timestamp_utc <= r.cutoff_utc
            QUALIFY row_number() OVER (
                PARTITION BY p.symbol, p.session_date
                ORDER BY p.timestamp_utc DESC
            ) = 1
            ORDER BY p.symbol, p.session_date
            """,
            [
                str(binding.canonical_path),
                SessionSegment.REGULAR.value,
            ],
        ).fetchall()
    finally:
        con.close()

    expected_source = ALPACA_V2_SOURCE_PREFIX + binding.unit_id
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for (
        symbol, stamp, session_day, segment, close,
        timeframe, dataset, provider, source_id, is_adjusted,
    ) in physical:
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
            raise OptionDecisionSpotRunnerError(
                f"entry-minute semantic identity changed in {binding.unit_id}"
            )
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            raise OptionDecisionSpotRunnerError("entry-minute timestamp lost timezone")
        identity = (symbol, session_day, stamp.isoformat())
        if identity in seen:
            raise OptionDecisionSpotRunnerError("duplicate entry-minute key")
        seen.add(identity)
        grouped.setdefault((symbol, session_day), []).append(
            {"timestamp_utc": stamp, "close": close}
        )
    return binding.unit_id, grouped, len(physical)


def _persist(settings, report: dict[str, Any]) -> tuple[Path, str]:
    fp = report["decision_spot_fingerprint"]
    path = settings.resolved_path(f"{OUTPUT_REL}_{fp[:16]}.json")
    raw = (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file() or path.read_bytes() != raw:
            raise OptionDecisionSpotRunnerError(
                "existing immutable option-decision spot artifact differs"
            )
        return path, "REUSED_IDENTICAL_OPTION_DECISION_SPOT"
    with path.open("xb") as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
    if path.read_bytes() != raw:
        raise OptionDecisionSpotRunnerError("option-decision spot write/readback failed")
    return path, "WRITTEN_IMMUTABLE_OPTION_DECISION_SPOT"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Bind the causal stock spot available at 09:35 for every option-expressible "
            "case and replace single-strike demand with provider-agnostic CALL candidate "
            "surface demand. Zero provider requests."
        )
    )
    parser.add_argument("--intraday-clock", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--duckdb-threads-per-worker", type=int, default=1)
    args = parser.parse_args(argv)
    if not 1 <= args.workers <= 8:
        raise SystemExit("--workers must be between 1 and 8")
    if not 1 <= args.duckdb_threads_per_worker <= 4:
        raise SystemExit("--duckdb-threads-per-worker must be between 1 and 4")

    print("ATLAS OPTION DECISION SPOT V1", flush=True)
    print(
        "  ZERO provider GETs. Resolves causal 09:35 stock spot from accepted Alpaca "
        "SIP raw 1-minute source. No option prices or outcomes are read.",
        flush=True,
    )
    try:
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        settings.assert_external_storage_binding("research_evidence")
        source_path = (
            args.intraday_clock
            if args.intraday_clock.is_absolute()
            else settings.resolved_path(args.intraday_clock)
        )
        if source_path.is_symlink() or not source_path.is_file():
            raise OptionDecisionSpotRunnerError(
                f"intraday stock clock artifact unavailable: {source_path}"
            )
        intraday_clock = _read_object(source_path)
        _check_signature(intraday_clock, "intraday_clock_fingerprint")
        cases = select_decision_spot_cases(intraday_clock)

        source = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
        bindings, binding_by_key, raw_plan_sha, compressed_plan_sha = _targeted_bindings(
            source, cases
        )
        source.close()

        binding_by_id = {item.unit_id: item for item in bindings}
        assigned: dict[str, list[dict[str, Any]]] = {}
        requested: dict[str, dict[str, set[str]]] = {}
        for case in cases:
            key = (case["ticker"], case["entry_session"])
            binding = binding_by_key[key]
            assigned.setdefault(binding.unit_id, []).append(case)
            requested.setdefault(binding.unit_id, {}).setdefault(
                case["ticker"], set()
            ).add(case["entry_session"])

        print(
            "  target "
            f"clock_ready_cases={len(cases)} "
            f"unique_symbol_entry_sessions={len(binding_by_key)} "
            f"minute_bindings={len(assigned)} workers={args.workers}",
            flush=True,
        )

        resolved: list[dict[str, Any]] = []
        total_rows = 0
        completed = 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    _read_binding_rows,
                    settings=settings,
                    binding=binding_by_id[unit_id],
                    requested=requested[unit_id],
                    duckdb_threads=args.duckdb_threads_per_worker,
                ): unit_id
                for unit_id in sorted(assigned)
            }
            for future in as_completed(futures):
                unit_id, grouped, rows_read = future.result()
                total_rows += rows_read
                for case in assigned[unit_id]:
                    bars = grouped.get((case["ticker"], case["entry_session"]), [])
                    resolved.append(resolve_decision_spot(case, bars))
                completed += 1
                if completed % 25 == 0 or completed == len(futures):
                    print(
                        "  minute_source_progress "
                        f"{completed}/{len(futures)} bindings verified/read "
                        f"rows_read={total_rows}",
                        flush=True,
                    )

        metadata = {
            "contract": "atlas-b35-development-minute-source-v2-native-plan-exact-path-physical",
            "provider": "alpaca",
            "feed": "sip",
            "provider_timeframe": "1Min",
            "canonical_timeframe": "1m",
            "adjustment": "raw",
            "interval_timestamp": "left_edge_start",
            "decision_spot_rule":
                "latest completed regular minute close with bar_timestamp+1m <= 09:35 decision",
            "native_plan_sha256": raw_plan_sha,
            "native_plan_file_sha256": compressed_plan_sha,
            "targeted_binding_count": len(assigned),
            "unique_symbol_entry_session_keys": len(binding_by_key),
            "physical_rows_read": total_rows,
            "provider_calls": 0,
            "protected_2026_rows_read": 0,
        }
        report = build_decision_spot_report(
            intraday_clock=intraday_clock,
            source_metadata=metadata,
            resolved_rows=resolved,
        )
        output_path, action = _persist(settings, report)

        print(f"  intraday_clock={source_path}", flush=True)
        print(
            "  decision_spot "
            f"ready={report['decision_spot_ready_cases']} "
            f"missing={report['decision_spot_missing_cases']} "
            f"fraction={report['decision_spot_ready_fraction']:.6f}",
            flush=True,
        )
        print(
            f"  raw_open_to_0935_move={report['raw_open_to_0935_move']}",
            flush=True,
        )
        print(
            "  absolute_raw_open_to_0935_move="
            f"{report['absolute_raw_open_to_0935_move']}",
            flush=True,
        )
        print(
            f"  absolute_move_thresholds={report['absolute_move_thresholds']}",
            flush=True,
        )
        print(
            f"  source_staleness_seconds={report['source_staleness_seconds']}",
            flush=True,
        )
        baseline = report["baseline_structural_call_at_0935"]
        print(
            "  baseline_structural_call_at_0935 "
            f"moneyness={baseline['moneyness']} "
            f"strike_distance_fraction={baseline['strike_distance_fraction']} "
            "final_contract_selection=False",
            flush=True,
        )
        demand = report["candidate_entry_surface_demand"]
        print(
            "  candidate_entry_surface "
            f"case_members={demand['case_members']} "
            f"unique_underlying_date_clock_queries="
            f"{demand['unique_underlying_date_clock_queries']} "
            f"max_dte={demand['max_dte_calendar_days']} "
            "single_strike_preselection=False provider_specific_shape=False",
            flush=True,
        )
        for year, values in report["by_year"].items():
            print(f"  year={year} {values}", flush=True)
        print(f"  decision_spot={action} / {output_path}", flush=True)
        print(
            "  COMPLETE provider_requests=0 option_prices_read=0 option_outcomes_read=0 "
            "historical_fill_authority=False strategy_evidence_authority=False "
            "paper_authority=False live_authority=False",
            flush=True,
        )
        return 0
    except Exception as exc:
        print(
            f"OPTION DECISION SPOT STOPPED: {type(exc).__name__}: {exc}",
            flush=True,
        )
        print("  No provider fallback or paid request is authorized.", flush=True)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
