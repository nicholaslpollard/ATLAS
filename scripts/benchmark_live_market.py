from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from apps.market_ingestion.live_service import LiveMarketService
from packages.core.atomic_io import atomic_write_text
from packages.core.enums import LiveFeedMode
from packages.core.settings import load_settings
from packages.data.paths import MarketDataPaths
from packages.live.benchmark import (
    build_benchmark_summary,
    process_peak_rss_bytes,
    tree_size_bytes,
)


def _symbols(value: str) -> tuple[str, ...]:
    return tuple(symbol.strip() for symbol in value.split(",") if symbol.strip())


def _mib(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"{value / (1024 * 1024):,.1f} MiB"


def _seconds(value: float | None) -> str:
    return "n/a" if value is None else f"{value:,.2f}s"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Benchmark ATLAS live stock minute ingestion on the target machine."
    )
    parser.add_argument(
        "--feed",
        choices=[mode.value for mode in LiveFeedMode],
        default=LiveFeedMode.DELAYED.value,
    )
    parser.add_argument(
        "--minute-symbols",
        default="*",
        help="Comma-separated provider-native symbols or * for broad minute aggregates.",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=300.0,
        help="Benchmark wall-clock duration. Default: 300 seconds.",
    )
    parser.add_argument(
        "--require-events",
        action="store_true",
        help="Return nonzero if the run receives no accepted market events.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Return nonzero for parse errors, reconnects/open gaps, or >=80%% peak ingress queue use.",
    )
    parser.add_argument("--no-journal", action="store_true")
    return parser


async def _run(args: argparse.Namespace) -> int:
    if args.seconds <= 0:
        raise ValueError("--seconds must be greater than zero")

    settings = load_settings(PROJECT_ROOT)
    paths = MarketDataPaths(settings)
    minute_symbols = _symbols(args.minute_symbols)
    service = LiveMarketService(
        settings,
        feed_mode=LiveFeedMode(args.feed),
        minute_symbols=minute_symbols,
        quote_symbols=(),
        journal_enabled=not args.no_journal,
    )

    journal_root = settings.resolved_path(settings.data.paths.live) / "journal" / "massive" / "stocks"
    journal_before = tree_size_bytes(journal_root)
    wall_start = time.perf_counter()
    cpu_start = time.process_time()

    print("ATLAS Live Market Benchmark")
    print(f"  feed:              {service.client.feed_mode.value}")
    print(f"  expected delay:    {service.client.expected_delay_seconds}s")
    print(f"  subscriptions:     {', '.join(service.subscriptions)}")
    print(f"  requested seconds: {args.seconds:,.0f}")
    print(f"  journal:           {'disabled' if args.no_journal else 'enabled'}")
    print(f"  restored symbols:  {service.state.restored_symbol_count:,}")
    if service.state.restore_warning:
        print(f"  restore warning:   {service.state.restore_warning}")

    snapshot = await service.run(max_seconds=args.seconds)

    wall_seconds = time.perf_counter() - wall_start
    process_cpu_seconds = time.process_time() - cpu_start
    journal_after = tree_size_bytes(journal_root)
    summary = build_benchmark_summary(
        snapshot,
        service.client.runtime_stats,
        wall_seconds=wall_seconds,
        process_cpu_seconds=process_cpu_seconds,
        peak_rss_bytes=process_peak_rss_bytes(),
        journal_growth_bytes=journal_after - journal_before,
    )

    report_path = paths.live_benchmark_report(datetime.now(UTC))
    atomic_write_text(report_path, json.dumps(summary, indent=2, sort_keys=True) + "\n")

    lag = summary["latest_minute_excess_lag_seconds"]
    freshness = summary["minute_freshness_counts"]
    queue_pct = float(summary["peak_queue_utilization"]) * 100.0

    print("ATLAS Live Market Benchmark result")
    print(f"  wall seconds:       {summary['wall_seconds']:,.2f}")
    print(f"  process CPU:        {summary['process_cpu_seconds']:,.2f}s")
    print(f"  CPU one-core equiv: {summary['cpu_one_core_percent']:,.1f}%")
    print(f"  peak process RSS:   {_mib(summary['peak_rss_bytes'])}")
    print(f"  frames received:    {summary['frames_received']:,}")
    print(f"  received events:    {summary['received_events']:,} ({summary['received_events_per_second']:,.1f}/s)")
    print(f"  accepted events:    {summary['accepted_events']:,} ({summary['accepted_events_per_second']:,.1f}/s)")
    print(f"  observed this run:  {summary['observed_symbol_count']:,}")
    print(f"  restored at start:  {summary['restored_symbol_count']:,}")
    print(f"  symbols in state:   {summary['symbol_count']:,}")
    print(
        "  peak ingress queue: "
        f"{summary['peak_ingress_queue_depth']:,}/{summary['ingress_queue_capacity']:,} "
        f"({queue_pct:,.2f}%)"
    )
    print(
        "  minute freshness:   "
        f"fresh={freshness.get('fresh', 0):,} "
        f"aging={freshness.get('aging', 0):,} "
        f"stale={freshness.get('stale', 0):,} "
        f"unknown={freshness.get('unknown', 0):,}"
    )
    print(
        "  excess feed lag:     "
        f"p50={_seconds(lag['p50'])} p95={_seconds(lag['p95'])} max={_seconds(lag['max'])}"
    )
    print(f"  journal growth:      {_mib(summary['journal_growth_bytes'])}")
    print(f"  ignored old:         {summary['ignored_out_of_order_events']:,}")
    print(f"  parse errors:        {summary['parse_errors']:,}")
    print(f"  reconnects:          {summary['reconnects']:,}")
    print(
        "  transport gaps:      "
        f"{summary['transport_gap_count']:,} closed / "
        f"{summary['transport_gap_total_seconds']:,.2f}s total"
    )
    if summary["open_transport_gap_started_at_utc"] is not None:
        print(f"  open transport gap:  {summary['open_transport_gap_started_at_utc']}")
    print(f"  baseline health:     {'PASS' if summary['baseline_healthy'] else 'REVIEW'}")
    print(f"  report:              {report_path.resolve()}")

    if args.require_events and snapshot.accepted_events == 0:
        print("ATLAS benchmark requirement failed: no accepted market events were observed.")
        return 3
    if args.strict and not bool(summary["baseline_healthy"]):
        print("ATLAS benchmark strict health gate failed; review the metrics above.")
        return 4
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(_run(args))


if __name__ == "__main__":
    raise SystemExit(main())
