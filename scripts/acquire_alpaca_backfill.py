from __future__ import annotations

import argparse

from packages.core.settings import load_settings
from packages.data.alpaca_backfill_acquisition import AlpacaBackfillAcquirer


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Acquire the locked 2016-2021 Alpaca raw-SIP daily historical backfill."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=None,
        help="Optional single year to acquire. Omit for the complete locked range.",
    )
    parser.add_argument(
        "--max-units",
        type=int,
        default=None,
        help="Optional diagnostic cap on newly executed units. A capped run cannot complete Gate 3.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.max_units is not None and args.max_units < 1:
        raise SystemExit("--max-units must be at least 1")

    settings = load_settings()
    acquirer = AlpacaBackfillAcquirer(settings)
    symbols, fingerprint, units = acquirer.build_plan()
    years = sorted({unit.year for unit in units})

    print("ATLAS Alpaca Raw Historical Backfill Acquisition")
    print("  safety: production canonical history will not be modified")
    print(f"  candidates:                  {len(symbols):,}")
    print(f"  inventory fingerprint:       {fingerprint}")
    print(f"  year partitions:             {years}")
    print(f"  planned restartable units:   {len(units):,}")
    print(f"  symbol batch size:           {settings.alpaca.market_data.symbol_batch_size}")
    print(f"  page limit:                  {settings.alpaca.market_data.page_limit:,}")
    print(f"  request safety cap:          {settings.alpaca.market_data.requests_per_minute}/min")
    if args.year is not None:
        print(f"  execution scope:             year={args.year}")
    elif args.max_units is not None:
        print(f"  execution scope:             full plan, at most {args.max_units} new units")
    else:
        print("  execution scope:             complete locked range")
    print("  resume behavior:             completed compatible unit manifests are skipped")

    def progress(done, total, unit, payload, skipped):
        if skipped and (done % 25 != 0 and done != total):
            return
        if not skipped and (done % 10 != 0 and done != total and done != 1):
            return
        marker = "SKIP" if skipped else "DONE"
        print(
            f"    [{done:04d}/{total:04d}] {marker} year={unit.year} "
            f"batch={unit.batch_index:04d} symbols={len(unit.symbols):3d} "
            f"pages={int(payload.get('page_count', 0)):2d} "
            f"bars={int(payload.get('bar_rows', 0)):6d} "
            f"observed={int(payload.get('observed_symbol_count', 0)):3d}"
        )

    report = acquirer.run(
        year=args.year,
        max_units=args.max_units,
        progress=progress,
    )

    print("  acquisition state:")
    print(f"    completed units:           {report.completed_units:,}/{report.planned_units:,}")
    print(f"    missing units:             {report.missing_units:,}")
    print(f"    raw payload pages:         {report.raw_payload_pages:,}")
    print(f"    observed symbols:          {report.observed_symbols:,}/{report.candidate_symbols:,}")
    print(f"    zero-bar symbols:          {report.zero_bar_symbols:,}")
    print(f"    bar rows:                  {report.bar_rows:,}")
    print(f"    executed this run:         {report.executed_units_this_run:,}")
    print(f"    skipped this run:          {report.skipped_completed_units_this_run:,}")
    print(f"    complete:                  {report.complete}")
    print(f"  observed summary:            {report.observed_summary_path}")
    print(f"  unit manifests:              {report.unit_manifest_root}")
    print(f"  report:                      {report.report_path}")
    print("  canonical data modified:     False")
    print("  result:                      ACQUISITION COMPLETE" if report.complete else "  result:                      PARTIAL / RESUMABLE")


if __name__ == "__main__":
    main()
