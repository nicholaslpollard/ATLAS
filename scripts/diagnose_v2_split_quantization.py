from __future__ import annotations

import json
from pathlib import Path

import duckdb


def main() -> int:
    root = Path("data/v2_build/alpaca_sip_v2").resolve()
    validation = root / "validation"
    identity_path = root / "canonical" / "identity" / "v2_symbol_identity_map.parquet"
    native_inventory_path = validation / "native_unit_inventory.parquet"
    split_inventory_path = validation / "split_adjusted_daily_inventory.parquet"
    split_manifest_path = root / "manifests" / "split_adjusted_daily.json"
    price_out = validation / "split_quantization_worst_price.csv"
    volume_out = validation / "split_quantization_worst_volume.csv"

    for path in (
        identity_path,
        native_inventory_path,
        split_inventory_path,
        split_manifest_path,
    ):
        if not path.is_file():
            raise SystemExit(f"MISSING: {path}")

    con = duckdb.connect(":memory:")
    con.execute("PRAGMA threads=4")

    raw_inventory = con.execute(
        "SELECT unit_id, canonical_path FROM read_parquet(?) "
        "WHERE canonical_timeframe = '1d' ORDER BY unit_id",
        [str(native_inventory_path)],
    ).fetchdf()
    split_inventory = con.execute(
        "SELECT unit_id, canonical_path FROM read_parquet(?) ORDER BY unit_id",
        [str(split_inventory_path)],
    ).fetchdf()
    identity = con.execute(
        "SELECT symbol, identity_clear, security_type, missing_sessions_between_bounds "
        "FROM read_parquet(?) ORDER BY symbol",
        [str(identity_path)],
    ).fetchdf()

    manifest = json.loads(split_manifest_path.read_text(encoding="utf-8"))
    excluded = {str(value) for value in manifest.get("excluded_symbols") or []}
    eligible = identity.loc[
        identity["identity_clear"].astype(bool)
        & identity["security_type"].eq("COMMON_STOCK")
        & identity["missing_sessions_between_bounds"].eq(0)
        & ~identity["symbol"].astype(str).isin(excluded),
        ["symbol"],
    ].copy()

    raw_paths = [str(Path(value)) for value in raw_inventory["canonical_path"]]
    split_paths = [str(Path(value)) for value in split_inventory["canonical_path"]]
    if not raw_paths or not split_paths or eligible.empty:
        raise SystemExit("Required reconciliation inputs are empty.")

    con.read_parquet(raw_paths).create_view("raw_daily")
    con.read_parquet(split_paths).create_view("adjusted_daily")
    con.register("eligible_reconcile", eligible)

    con.execute(
        """
        CREATE TEMP VIEW split_quantization AS
        WITH paired AS (
            SELECT
                r.symbol,
                r.session_date,
                r.open AS raw_open,
                r.high AS raw_high,
                r.low AS raw_low,
                r.close AS raw_close,
                r.volume AS raw_volume,
                a.open AS adjusted_open,
                a.high AS adjusted_high,
                a.low AS adjusted_low,
                a.close AS adjusted_close,
                a.volume AS adjusted_volume,
                a.close / r.close AS factor_close,
                a.open / r.open AS factor_open,
                a.high / r.high AS factor_high,
                a.low / r.low AS factor_low
            FROM raw_daily r
            JOIN adjusted_daily a USING (symbol, session_date)
            JOIN eligible_reconcile e ON e.symbol = r.symbol
            WHERE r.close > 0 AND a.close > 0
        )
        SELECT
            *,
            abs(adjusted_open - raw_open * factor_close) AS open_adjusted_price_error,
            abs(adjusted_high - raw_high * factor_close) AS high_adjusted_price_error,
            abs(adjusted_low - raw_low * factor_close) AS low_adjusted_price_error,
            greatest(
                abs(adjusted_open - raw_open * factor_close),
                abs(adjusted_high - raw_high * factor_close),
                abs(adjusted_low - raw_low * factor_close)
            ) AS max_adjusted_price_error,
            abs(factor_open - factor_close) / abs(factor_close) AS open_factor_relative_error,
            abs(factor_high - factor_close) / abs(factor_close) AS high_factor_relative_error,
            abs(factor_low - factor_close) / abs(factor_close) AS low_factor_relative_error,
            greatest(
                abs(factor_open - factor_close) / abs(factor_close),
                abs(factor_high - factor_close) / abs(factor_close),
                abs(factor_low - factor_close) / abs(factor_close)
            ) AS max_factor_relative_error,
            raw_volume / factor_close AS expected_adjusted_volume,
            abs(adjusted_volume - raw_volume / factor_close) AS adjusted_volume_share_error
        FROM paired
        """
    )

    summary = con.execute(
        """
        SELECT
            count(*) AS paired_rows,
            count(DISTINCT symbol) AS symbols,
            count(*) FILTER (WHERE abs(factor_close - 1.0) > 1e-12) AS adjusted_rows,
            count(DISTINCT symbol) FILTER (WHERE abs(factor_close - 1.0) > 1e-12)
                AS adjusted_symbols,
            quantile_cont(max_adjusted_price_error, 0.50) AS price_p50,
            quantile_cont(max_adjusted_price_error, 0.90) AS price_p90,
            quantile_cont(max_adjusted_price_error, 0.99) AS price_p99,
            quantile_cont(max_adjusted_price_error, 0.999) AS price_p999,
            quantile_cont(max_adjusted_price_error, 0.9999) AS price_p9999,
            max(max_adjusted_price_error) AS price_max,
            quantile_cont(adjusted_volume_share_error, 0.50) AS volume_p50,
            quantile_cont(adjusted_volume_share_error, 0.90) AS volume_p90,
            quantile_cont(adjusted_volume_share_error, 0.99) AS volume_p99,
            quantile_cont(adjusted_volume_share_error, 0.999) AS volume_p999,
            quantile_cont(adjusted_volume_share_error, 0.9999) AS volume_p9999,
            max(adjusted_volume_share_error) AS volume_max,
            quantile_cont(max_factor_relative_error, 0.99) AS factor_rel_p99,
            quantile_cont(max_factor_relative_error, 0.999) AS factor_rel_p999,
            quantile_cont(max_factor_relative_error, 0.9999) AS factor_rel_p9999,
            max(max_factor_relative_error) AS factor_rel_max
        FROM split_quantization
        """
    ).fetchone()
    assert summary is not None

    price_thresholds = (0.005, 0.01, 0.02, 0.05, 0.10, 0.50, 1.00)
    price_counts = []
    for threshold in price_thresholds:
        value = con.execute(
            "SELECT count(*) FROM split_quantization WHERE max_adjusted_price_error > ?",
            [threshold],
        ).fetchone()
        price_counts.append((threshold, int(value[0])))

    volume_thresholds = (0.5, 1.0, 2.0, 5.0, 10.0)
    volume_counts = []
    for threshold in volume_thresholds:
        value = con.execute(
            "SELECT count(*) FROM split_quantization WHERE adjusted_volume_share_error > ?",
            [threshold],
        ).fetchone()
        volume_counts.append((threshold, int(value[0])))

    relative_thresholds = (1e-6, 1e-5, 1e-4, 1e-3)
    relative_counts = []
    for threshold in relative_thresholds:
        value = con.execute(
            "SELECT count(*) FROM split_quantization WHERE max_factor_relative_error > ?",
            [threshold],
        ).fetchone()
        relative_counts.append((threshold, int(value[0])))

    price_worst = con.execute(
        """
        SELECT
            symbol, session_date,
            raw_open, adjusted_open, raw_high, adjusted_high,
            raw_low, adjusted_low, raw_close, adjusted_close,
            factor_close,
            open_adjusted_price_error, high_adjusted_price_error,
            low_adjusted_price_error, max_adjusted_price_error,
            max_factor_relative_error
        FROM split_quantization
        ORDER BY max_adjusted_price_error DESC, symbol, session_date
        LIMIT 500
        """
    ).fetchdf()
    volume_worst = con.execute(
        """
        SELECT
            symbol, session_date,
            raw_volume, adjusted_volume, factor_close,
            expected_adjusted_volume, adjusted_volume_share_error,
            max_adjusted_price_error, max_factor_relative_error
        FROM split_quantization
        ORDER BY adjusted_volume_share_error DESC, symbol, session_date
        LIMIT 500
        """
    ).fetchdf()
    price_worst.to_csv(price_out, index=False)
    volume_worst.to_csv(volume_out, index=False)
    con.close()

    print()
    print("V2 SPLIT QUANTIZATION DIAGNOSTIC")
    print(f"Eligible symbols: {len(eligible):,}")
    print(f"Previously excluded split symbols: {len(excluded):,}")
    print(f"Paired rows: {int(summary[0]):,}")
    print(f"Paired symbols: {int(summary[1]):,}")
    print(f"Rows with non-unit close factor: {int(summary[2]):,}")
    print(f"Symbols with non-unit close factor: {int(summary[3]):,}")
    print()
    print("ADJUSTED-PRICE ERROR DISTRIBUTION ($, close-derived factor anchor)")
    print(f"p50:    {summary[4]}")
    print(f"p90:    {summary[5]}")
    print(f"p99:    {summary[6]}")
    print(f"p99.9:  {summary[7]}")
    print(f"p99.99: {summary[8]}")
    print(f"max:    {summary[9]}")
    for threshold, count in price_counts:
        print(f"rows > ${threshold:g}: {count:,}")
    print()
    print("ADJUSTED-VOLUME ERROR DISTRIBUTION (shares)")
    print(f"p50:    {summary[10]}")
    print(f"p90:    {summary[11]}")
    print(f"p99:    {summary[12]}")
    print(f"p99.9:  {summary[13]}")
    print(f"p99.99: {summary[14]}")
    print(f"max:    {summary[15]}")
    for threshold, count in volume_counts:
        print(f"rows > {threshold:g} share(s): {count:,}")
    print()
    print("MAX RELATIVE FACTOR ERROR DISTRIBUTION")
    print(f"p99:    {summary[16]}")
    print(f"p99.9:  {summary[17]}")
    print(f"p99.99: {summary[18]}")
    print(f"max:    {summary[19]}")
    for threshold, count in relative_counts:
        print(f"rows > {threshold:g}: {count:,}")
    print()
    print("WORST 25 ADJUSTED-PRICE ROWS")
    print(price_worst.head(25).to_string(index=False))
    print()
    print("WORST 25 ADJUSTED-VOLUME ROWS")
    print(volume_worst.head(25).to_string(index=False))
    print()
    print(f"Worst 500 price rows written to: {price_out}")
    print(f"Worst 500 volume rows written to: {volume_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
