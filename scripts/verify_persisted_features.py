from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np

from packages.core.enums import Timeframe
from packages.core.market_calendar import MarketCalendar
from packages.core.settings import load_settings
from packages.data.duckdb_connection import connect_utc
from packages.data.sql import sql_string
from packages.features.engine import compute_core_features
from packages.features.feature_registry import CORE_FEATURE_REGISTRY
from packages.features.partition_store import FeaturePartitionStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Independently recompute one real symbol and verify a persisted ATLAS feature partition."
    )
    parser.add_argument("--timeframe", choices=["1d", "4h", "1h"], required=True)
    parser.add_argument("--history-start", type=date.fromisoformat, required=True)
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--atol", type=float, default=1e-10)
    parser.add_argument("--rtol", type=float, default=1e-10)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    timeframe = Timeframe(args.timeframe)
    symbol = args.symbol.strip()
    if not symbol:
        raise SystemExit("--symbol cannot be blank")
    if args.date < args.history_start:
        raise SystemExit("--date precedes --history-start")

    settings = load_settings(PROJECT_ROOT)
    store = FeaturePartitionStore(settings)
    calendar = MarketCalendar(exchange=settings.data.calendar.exchange)
    sessions = calendar.sessions_in_range(args.history_start, args.date)
    source_paths = [store.source_path(timeframe, session) for session in sessions]
    missing = [path for path in source_paths if not path.is_file()]
    if missing:
        print("ATLAS persisted feature verification cannot run; source partitions are missing:")
        for path in missing[:10]:
            print(f"  {path}")
        return 2

    target_feature = store.paths.feature_file(timeframe, args.date)
    target_source = store.source_path(timeframe, args.date)
    if not target_feature.is_file():
        print(f"ATLAS persisted feature verification cannot run; feature partition is missing: {target_feature}")
        return 2

    source_sql = "[" + ",".join(sql_string(path) for path in source_paths) + "]"
    con = connect_utc(":memory:")
    try:
        if timeframe == Timeframe.DAY_1:
            select_columns = "symbol, timestamp_utc, high, low, close, volume"
            key_columns = ["symbol", "timestamp_utc"]
            order_columns = "symbol, timestamp_utc"
        else:
            select_columns = "symbol, timestamp_utc, session_segment, high, low, close, volume"
            key_columns = ["symbol", "timestamp_utc", "session_segment"]
            order_columns = "symbol, session_segment, timestamp_utc"

        bars = con.execute(
            f"""
            SELECT {select_columns}
            FROM read_parquet({source_sql}, union_by_name=true, hive_partitioning=true)
            WHERE symbol = ?
            ORDER BY {order_columns}
            """,
            [symbol],
        ).fetch_df()
        if bars.empty:
            print(f"No source bars found for exact provider symbol {symbol!r}")
            return 3

        target_keys = con.execute(
            f"""
            SELECT {', '.join(key_columns)}
            FROM read_parquet({sql_string(target_source)})
            WHERE symbol = ?
            ORDER BY {order_columns}
            """,
            [symbol],
        ).fetch_df()
        persisted = con.execute(
            f"""
            SELECT *
            FROM read_parquet({sql_string(target_feature)})
            WHERE symbol = ?
            ORDER BY {order_columns}
            """,
            [symbol],
        ).fetch_df()
    finally:
        con.close()

    if target_keys.empty:
        print(f"No target-date source rows found for exact provider symbol {symbol!r}")
        return 3
    if persisted.empty:
        print(f"No persisted target-date feature rows found for exact provider symbol {symbol!r}")
        return 4

    expected_all = compute_core_features(bars)
    expected = expected_all.merge(target_keys, on=key_columns, how="inner", validate="one_to_one")
    expected = expected.sort_values(key_columns, kind="stable").reset_index(drop=True)
    persisted = persisted.sort_values(key_columns, kind="stable").reset_index(drop=True)

    if len(expected) != len(target_keys) or len(persisted) != len(target_keys):
        print("Persisted feature verification failed: target row-count/key mismatch")
        print(f"  target source rows: {len(target_keys)}")
        print(f"  expected rows:      {len(expected)}")
        print(f"  persisted rows:     {len(persisted)}")
        return 5

    for column in key_columns:
        if not expected[column].equals(persisted[column]):
            print(f"Persisted feature verification failed: key mismatch in {column}")
            return 5

    failures: list[str] = []
    max_abs_diff = 0.0
    for definition in CORE_FEATURE_REGISTRY.all():
        name = definition.name
        expected_values = expected[name].to_numpy(dtype="float64")
        actual_values = persisted[name].to_numpy(dtype="float64")
        finite = np.isfinite(expected_values) & np.isfinite(actual_values)
        if finite.any():
            max_abs_diff = max(
                max_abs_diff,
                float(np.max(np.abs(expected_values[finite] - actual_values[finite]))),
            )
        if not np.allclose(
            expected_values,
            actual_values,
            rtol=args.rtol,
            atol=args.atol,
            equal_nan=True,
        ):
            failures.append(name)

    print("ATLAS Persisted Feature Verification")
    print(f"  timeframe:          {timeframe.value}")
    print(f"  history origin:     {args.history_start}")
    print(f"  target date:        {args.date}")
    print(f"  exact symbol:       {symbol}")
    print(f"  history rows:       {len(bars):,}")
    print(f"  target rows:        {len(target_keys):,}")
    print(f"  features compared:  {len(CORE_FEATURE_REGISTRY.all())}")
    print(f"  maximum abs diff:   {max_abs_diff:.3e}")
    if failures:
        print(f"  result:              FAIL ({len(failures)} feature columns)")
        for name in failures:
            print(f"    {name}")
        return 1
    print("  result:              PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
