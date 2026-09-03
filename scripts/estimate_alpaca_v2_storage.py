from __future__ import annotations

import argparse
import gzip
import hashlib
import shutil
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import sys
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.providers.alpaca import AlpacaInvalidSymbolError, AlpacaMarketDataClient

CONTRACT = "atlas-alpaca-v2-storage-preflight-v1"
BUCKETS = (
    ("LT_250K", 0.0, 250_000.0),
    ("250K_TO_1M", 250_000.0, 1_000_000.0),
    ("1M_TO_5M", 1_000_000.0, 5_000_000.0),
    ("5M_TO_25M", 5_000_000.0, 25_000_000.0),
    ("25M_PLUS", 25_000_000.0, None),
)
WINDOWS = ((2, 1, 9), (6, 1, 9), (10, 1, 9))
GIB = 1024 ** 3


def human_bytes(value: float | int) -> str:
    value = float(value)
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            return f"{value:,.2f} {unit}"
        value /= 1024.0
    return f"{value:,.2f} B"


def dir_size(root: Path) -> int:
    if not root.exists():
        return 0
    total = 0
    for path in root.rglob("*"):
        try:
            if path.is_file() and not path.is_symlink():
                total += path.stat().st_size
        except OSError:
            pass
    return total


def bucket_name(median_dollar_volume: float) -> str:
    for name, lower, upper in BUCKETS:
        if median_dollar_volume >= lower and (upper is None or median_dollar_volume < upper):
            return name
    return "LT_250K"


def sample_key(year: int, bucket: str, symbol: str) -> str:
    return hashlib.sha256(f"{year}|{bucket}|{symbol}".encode("utf-8")).hexdigest()


def iter_payload_bars(payload: Any):
    if not isinstance(payload, dict):
        return
    bars = payload.get("bars")
    if not isinstance(bars, dict):
        return
    for raw_symbol, values in bars.items():
        if not isinstance(raw_symbol, str) or not isinstance(values, list):
            continue
        symbol = raw_symbol.strip()
        if not symbol:
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            timestamp = item.get("t")
            if timestamp is None:
                continue
            yield {
                "symbol": symbol,
                "timestamp_utc": str(timestamp),
                "open": item.get("o"),
                "high": item.get("h"),
                "low": item.get("l"),
                "close": item.get("c"),
                "volume": item.get("v"),
                "vwap": item.get("vw"),
                "transaction_count": item.get("n"),
            }


@dataclass
class YearBucket:
    year: int
    bucket: str
    full_daily_rows: int
    eligible_symbols: int
    selected_symbols: list[str]
    sampled_daily_rows: int = 0
    sampled_minute_rows: int = 0

    @property
    def minute_rows_per_daily_row(self) -> float | None:
        if self.sampled_daily_rows <= 0:
            return None
        return self.sampled_minute_rows / self.sampled_daily_rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Empirical read-only Alpaca SIP 1Min storage preflight. Reads V1 daily canonical "
            "history for stratified weighting, calls Alpaca for small samples, writes only "
            "temporary Parquet samples outside data/, and deletes them by default."
        )
    )
    parser.add_argument("--sample-per-bucket", type=int, default=6)
    parser.add_argument("--start-year", type=int, default=2016)
    parser.add_argument("--end-year", type=int, default=None)
    parser.add_argument(
        "--keep-samples",
        action="store_true",
        help="Keep temporary Parquet sample files and print their directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_per_bucket < 1:
        raise ValueError("--sample-per-bucket must be >= 1")

    settings = load_settings(PROJECT_ROOT)
    canonical_root = settings.resolved_path(settings.data.paths.canonical)
    daily_root = canonical_root / "stocks" / "1d"
    minute_root = canonical_root / "stocks" / "1m"
    daily_glob = (daily_root / "**" / "*.parquet").as_posix()
    if not daily_root.exists():
        raise RuntimeError(f"canonical daily history not found: {daily_root}")

    con = connect_utc(":memory:")
    try:
        min_day, max_day, daily_rows = con.execute(
            f"""
            SELECT
                MIN(CAST(timestamp_utc AS DATE)),
                MAX(CAST(timestamp_utc AS DATE)),
                COUNT(*)
            FROM read_parquet({sql_string(daily_glob)}, hive_partitioning=true)
            """
        ).fetchone()
        if min_day is None or max_day is None:
            raise RuntimeError("canonical daily history is empty")
        max_year = min(int(max_day.year), args.end_year or int(max_day.year))
        start_year = max(int(min_day.year), args.start_year)
        if start_year > max_year:
            raise RuntimeError("requested year range does not overlap canonical daily history")

        stats = con.execute(
            f"""
            SELECT
                EXTRACT(year FROM CAST(timestamp_utc AS DATE))::INTEGER AS year,
                symbol,
                COUNT(*)::BIGINT AS sessions,
                MEDIAN(CAST(close AS DOUBLE) * CAST(volume AS DOUBLE)) AS median_dollar_volume,
                MIN(CAST(timestamp_utc AS DATE)) AS first_day,
                MAX(CAST(timestamp_utc AS DATE)) AS last_day
            FROM read_parquet({sql_string(daily_glob)}, hive_partitioning=true)
            WHERE EXTRACT(year FROM CAST(timestamp_utc AS DATE)) BETWEEN {start_year} AND {max_year}
              AND CAST(close AS DOUBLE) > 0
              AND CAST(volume AS DOUBLE) >= 0
            GROUP BY 1, 2
            ORDER BY 1, 2
            """
        ).fetchall()

        by_year_bucket: dict[
            tuple[int, str], list[tuple[str, int, float, date, date]]
        ] = defaultdict(list)
        for year, symbol, sessions, mdv, first_day, last_day in stats:
            if mdv is None or first_day is None or last_day is None:
                continue
            bucket = bucket_name(float(mdv))
            by_year_bucket[(int(year), bucket)].append(
                (str(symbol), int(sessions), float(mdv), first_day, last_day)
            )

        weighted: dict[tuple[int, str], YearBucket] = {}
        for year in range(start_year, max_year + 1):
            for bucket, _, _ in BUCKETS:
                rows = by_year_bucket.get((year, bucket), [])
                # The sizing sample uses February/June/October windows. Require the
                # selected symbol to span the first and last window available in that
                # year so deterministic sampling does not accidentally choose only a
                # short-lived listing with zero observations in every sample window.
                available_windows = []
                for month, start_day, end_day in WINDOWS:
                    w_start = date(year, month, start_day)
                    w_end = min(date(year, month, end_day), max_day)
                    if w_start <= max_day and w_start <= w_end:
                        available_windows.append((w_start, w_end))
                coverage_start = available_windows[0][0] if available_windows else date(year, 1, 1)
                coverage_end = available_windows[-1][1] if available_windows else min(date(year, 12, 31), max_day)
                eligible = [
                    row
                    for row in rows
                    if row[1] >= 40 and row[3] <= coverage_start and row[4] >= coverage_end
                ]
                selected = sorted(
                    eligible,
                    key=lambda row: sample_key(year, bucket, row[0]),
                )[: args.sample_per_bucket]
                weighted[(year, bucket)] = YearBucket(
                    year=year,
                    bucket=bucket,
                    full_daily_rows=sum(row[1] for row in rows),
                    eligible_symbols=len(eligible),
                    selected_symbols=[row[0] for row in selected],
                )

        # Capture existing layer sizes. No V1 file contents are changed.
        v1_daily_bytes = dir_size(daily_root)
        v1_minute_bytes = dir_size(minute_root)
        derived_root = settings.resolved_path(settings.data.paths.derived)
        v1_derived_bars_bytes = dir_size(derived_root / "bars")
        v1_features_bytes = dir_size(derived_root / "features")
        v1_data_bytes = dir_size(PROJECT_ROOT / "data")
        disk = shutil.disk_usage(PROJECT_ROOT)

        # Switch only the in-memory settings object. No config file is modified.
        settings.alpaca.market_data.timeframe = "1Min"
        client = AlpacaMarketDataClient(settings)

        temp_root = Path(tempfile.mkdtemp(prefix="atlas_v2_storage_preflight_"))
        total_pages = 0
        total_raw_bytes = 0
        total_gzip_bytes = 0
        total_minute_rows = 0
        total_parquet_bytes = 0
        sample_windows = 0

        try:
            for year in range(start_year, max_year + 1):
                bucket_for_symbol: dict[str, str] = {}
                for bucket, _, _ in BUCKETS:
                    for symbol in weighted[(year, bucket)].selected_symbols:
                        bucket_for_symbol[symbol] = bucket
                symbols = sorted(bucket_for_symbol)
                if not symbols:
                    continue

                year_rows: list[dict[str, Any]] = []
                for month, start_day, end_day in WINDOWS:
                    window_start = date(year, month, start_day)
                    window_end = date(year, month, end_day)
                    if window_start > max_day:
                        continue
                    if window_end > max_day:
                        window_end = max_day
                    if window_start > window_end:
                        continue

                    start_text = f"{window_start.isoformat()}T00:00:00Z"
                    end_text = f"{window_end.isoformat()}T23:59:59Z"

                    # Provider-rejected historical literals are removed only from this sizing
                    # sample; no identity remapping is attempted.
                    request_symbols = list(symbols)
                    pages = []
                    while request_symbols:
                        try:
                            pages = list(
                                client.historical_bar_pages(
                                    symbols=request_symbols,
                                    start=start_text,
                                    end=end_text,
                                )
                            )
                            break
                        except AlpacaInvalidSymbolError as exc:
                            if exc.symbol not in request_symbols:
                                raise
                            request_symbols = [s for s in request_symbols if s != exc.symbol]

                    if not request_symbols:
                        continue

                    selected_sql = ",".join(sql_string(symbol) for symbol in request_symbols)
                    daily_counts = con.execute(
                        f"""
                        SELECT symbol, COUNT(*)::BIGINT
                        FROM read_parquet({sql_string(daily_glob)}, hive_partitioning=true)
                        WHERE CAST(timestamp_utc AS DATE)
                              BETWEEN DATE {sql_string(window_start.isoformat())}
                                  AND DATE {sql_string(window_end.isoformat())}
                          AND symbol IN ({selected_sql})
                        GROUP BY symbol
                        """
                    ).fetchall()
                    for symbol, count in daily_counts:
                        bucket = bucket_for_symbol.get(str(symbol))
                        if bucket is not None:
                            weighted[(year, bucket)].sampled_daily_rows += int(count)

                    sample_windows += 1
                    for page in pages:
                        total_pages += 1
                        total_raw_bytes += len(page.raw_body)
                        total_gzip_bytes += len(gzip.compress(page.raw_body, compresslevel=6, mtime=0))
                        for row in iter_payload_bars(page.payload):
                            bucket = bucket_for_symbol.get(row["symbol"])
                            if bucket is None:
                                continue
                            weighted[(year, bucket)].sampled_minute_rows += 1
                            total_minute_rows += 1
                            year_rows.append(row)

                if year_rows:
                    df = pd.DataFrame.from_records(year_rows)
                    out = temp_root / f"year={year}" / "part-000.parquet"
                    out.parent.mkdir(parents=True, exist_ok=True)
                    local = duckdb.connect(":memory:")
                    try:
                        local.register("sample_rows", df)
                        compression = settings.data.parquet.compression.upper()
                        row_group = int(settings.data.parquet.row_group_size)
                        local.execute(
                            f"""
                            COPY (
                                SELECT
                                    CAST(symbol AS VARCHAR) AS symbol,
                                    CAST(timestamp_utc AS TIMESTAMPTZ) AS timestamp_utc,
                                    CAST(open AS DOUBLE) AS open,
                                    CAST(high AS DOUBLE) AS high,
                                    CAST(low AS DOUBLE) AS low,
                                    CAST(close AS DOUBLE) AS close,
                                    CAST(volume AS BIGINT) AS volume,
                                    CAST(vwap AS DOUBLE) AS vwap,
                                    CAST(transaction_count AS BIGINT) AS transaction_count
                                FROM sample_rows
                                ORDER BY symbol, timestamp_utc
                            )
                            TO {sql_string(out.as_posix())}
                            (FORMAT PARQUET, COMPRESSION {compression}, ROW_GROUP_SIZE {row_group})
                            """
                        )
                    finally:
                        local.close()
                    total_parquet_bytes += out.stat().st_size

            if total_minute_rows <= 0:
                raise RuntimeError("Alpaca sizing sample returned zero minute rows")
            if total_parquet_bytes <= 0 or total_gzip_bytes <= 0:
                raise RuntimeError("sizing sample did not produce measurable storage evidence")

            parquet_bytes_per_row = total_parquet_bytes / total_minute_rows
            gzip_bytes_per_row = total_gzip_bytes / total_minute_rows
            raw_bytes_per_row = total_raw_bytes / total_minute_rows

            annual_estimates: dict[int, int] = {}
            missing_cells: list[str] = []
            for year in range(start_year, max_year + 1):
                estimate = 0.0
                for bucket, _, _ in BUCKETS:
                    cell = weighted[(year, bucket)]
                    ratio = cell.minute_rows_per_daily_row
                    if cell.full_daily_rows <= 0:
                        continue
                    if ratio is None:
                        missing_cells.append(f"{year}:{bucket}")
                        continue
                    estimate += cell.full_daily_rows * ratio
                annual_estimates[year] = int(round(estimate))

            # Missing liquidity strata are a sizing risk. Fail closed instead of treating
            # an unsampled stratum as zero storage.
            if missing_cells:
                raise RuntimeError(
                    "insufficient sample coverage for weighted estimate: " + ", ".join(missing_cells)
                )

            estimated_minute_rows = sum(annual_estimates.values())
            estimated_minute_parquet = estimated_minute_rows * parquet_bytes_per_row
            estimated_raw_gzip = estimated_minute_rows * gzip_bytes_per_row

            # Full-package planning intentionally does not optimize away normal ATLAS layers.
            daily_planning = v1_daily_bytes * 1.15
            minute_scale = estimated_minute_parquet / v1_minute_bytes if v1_minute_bytes > 0 else 1.0
            derived_planning = v1_derived_bars_bytes * max(1.0, minute_scale) * 1.15
            feature_planning = v1_features_bytes * max(1.0, minute_scale) * 1.15

            persistent_planning = (
                estimated_raw_gzip
                + estimated_minute_parquet
                + daily_planning
                + derived_planning
                + feature_planning
            )
            # Allow for identities/corporate actions/manifests/research state plus transient
            # migration/validation artifacts. Keep a separate post-build free-space reserve.
            ancillary_planning = persistent_planning * 0.15
            working_reserve = 35 * GIB
            peak_planning = persistent_planning + ancillary_planning + working_reserve

            free_v1_local = disk.free
            free_v1_external = disk.free + v1_data_bytes
            operational_reserve = 30 * GIB

            def verdict(free_bytes: int) -> str:
                return "GO" if peak_planning + operational_reserve <= free_bytes else "NO-GO"

            print("ATLAS Alpaca V2 Storage Preflight")
            print(f"  contract:                     {CONTRACT}")
            print("  V1 market data modified:       False")
            print("  config files modified:         False")
            print(f"  Alpaca profile:                {client.credential_profile_name}")
            print(
                "  Alpaca semantics:              "
                f"feed={settings.alpaca.market_data.feed} "
                f"adjustment={settings.alpaca.market_data.adjustment} "
                f"asof={settings.alpaca.market_data.asof} timeframe=1Min"
            )
            print(f"  canonical daily range:         {min_day} -> {max_day}")
            print(f"  canonical daily rows:          {int(daily_rows):,}")
            print(f"  sample years:                  {start_year}-{max_year}")
            print(f"  sample/bucket/year:            {args.sample_per_bucket}")
            print(f"  sample windows executed:       {sample_windows}")
            print(f"  Alpaca response pages:         {total_pages:,}")
            print(f"  sampled minute rows:           {total_minute_rows:,}")
            print()
            print("Sample storage")
            print(f"  raw JSON:                      {human_bytes(total_raw_bytes)}")
            print(f"  gzip raw evidence:             {human_bytes(total_gzip_bytes)}")
            print(f"  canonical-shape Parquet:       {human_bytes(total_parquet_bytes)}")
            print(f"  raw JSON bytes/minute row:     {raw_bytes_per_row:,.2f}")
            print(f"  gzip bytes/minute row:         {gzip_bytes_per_row:,.2f}")
            print(f"  Parquet bytes/minute row:      {parquet_bytes_per_row:,.2f}")
            print()
            print("Weighted minute-density estimate")
            for year in range(start_year, max_year + 1):
                print(f"  {year}: estimated minute rows={annual_estimates[year]:,}")
                for bucket, _, _ in BUCKETS:
                    cell = weighted[(year, bucket)]
                    ratio = cell.minute_rows_per_daily_row
                    ratio_text = "n/a" if ratio is None else f"{ratio:,.2f}"
                    print(
                        f"    {bucket:12s} full_daily={cell.full_daily_rows:>10,} "
                        f"eligible={cell.eligible_symbols:>5,} selected={len(cell.selected_symbols):>2} "
                        f"sample_daily={cell.sampled_daily_rows:>4,} "
                        f"sample_1m={cell.sampled_minute_rows:>7,} "
                        f"1m/dayrow={ratio_text}"
                    )
            print()
            print("Estimated V2 native bases")
            print(f"  native 1m rows:                {estimated_minute_rows:,}")
            print(f"  native 1m canonical Parquet:   {human_bytes(estimated_minute_parquet)}")
            print(f"  Alpaca raw 1m gzip evidence:   {human_bytes(estimated_raw_gzip)}")
            print(f"  native 1d planning allowance:  {human_bytes(daily_planning)}")
            print()
            print("Current V1 comparison")
            print(f"  V1 canonical 1m:               {human_bytes(v1_minute_bytes)}")
            print(f"  V1 canonical 1d:               {human_bytes(v1_daily_bytes)}")
            print(f"  V1 derived bars:               {human_bytes(v1_derived_bars_bytes)}")
            print(f"  V1 derived features:           {human_bytes(v1_features_bytes)}")
            print(f"  V1 total data/:                {human_bytes(v1_data_bytes)}")
            print(f"  inferred V2/V1 1m scale:       {minute_scale:,.3f}x")
            print()
            print("Conservative V2 full-package planning")
            print(f"  native/raw/daily/derived/features: {human_bytes(persistent_planning)}")
            print(f"  ancillary 15% allowance:           {human_bytes(ancillary_planning)}")
            print(f"  transient build reserve:           {human_bytes(working_reserve)}")
            print(f"  estimated V2 peak:                 {human_bytes(peak_planning)}")
            print(f"  separate post-build free reserve:  {human_bytes(operational_reserve)}")
            print()
            print("Disk decision")
            print(
                f"  current free with V1 local:        {human_bytes(free_v1_local)} "
                f"-> {verdict(free_v1_local)}"
            )
            print(
                f"  projected free with V1 external:   {human_bytes(free_v1_external)} "
                f"-> {verdict(free_v1_external)}"
            )
            print()
            print("Result: STORAGE PREFLIGHT ESTIMATE CAPTURED")
            if args.keep_samples:
                print(f"Temporary sample directory retained: {temp_root}")
            return 0
        finally:
            if not args.keep_samples:
                shutil.rmtree(temp_root, ignore_errors=True)
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
