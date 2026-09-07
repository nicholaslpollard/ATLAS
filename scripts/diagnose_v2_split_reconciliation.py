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
    out_path = validation / "split_reconciliation_failures.csv"

    required = (
        identity_path,
        native_inventory_path,
        split_inventory_path,
        split_manifest_path,
    )
    for path in required:
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

    paired = """
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
            a.open / r.open AS factor_open,
            a.high / r.high AS factor_high,
            a.low / r.low AS factor_low,
            a.close / r.close AS factor_close,
            a.provider,
            a.dataset,
            a.timeframe,
            a.session_segment,
            a.is_adjusted,
            a.source_id
        FROM raw_daily r
        JOIN adjusted_daily a USING (symbol, session_date)
        JOIN eligible_reconcile e ON e.symbol = r.symbol
    """
    failure = """
        NOT isfinite(factor_close) OR factor_close <= 0
        OR abs(factor_open - factor_close) > 1e-5
        OR abs(factor_high - factor_close) > 1e-5
        OR abs(factor_low - factor_close) > 1e-5
        OR (
            raw_volume > 0
            AND abs(adjusted_volume * factor_close - raw_volume)
                > greatest(1.0, abs(raw_volume)) * 1e-5
        )
        OR provider <> 'alpaca'
        OR dataset <> 'stock_daily_aggregates_split_adjusted'
        OR timeframe <> '1d'
        OR session_segment <> 'regular'
        OR is_adjusted <> TRUE
        OR source_id NOT LIKE 'alpaca:sip:1Day:split:asof=-:v2:unit=%'
    """
    failures_cte = f"""
        WITH paired AS ({paired}), failures AS (
            SELECT *,
                   abs(factor_open - factor_close) AS open_factor_delta,
                   abs(factor_high - factor_close) AS high_factor_delta,
                   abs(factor_low - factor_close) AS low_factor_delta,
                   CASE WHEN raw_volume > 0
                        THEN abs(adjusted_volume * factor_close - raw_volume)
                             / greatest(1.0, abs(raw_volume))
                        ELSE 0 END AS volume_relative_delta
            FROM paired
            WHERE {failure}
        )
    """

    summary = con.execute(
        failures_cte
        + """
        SELECT
            count(*) AS failure_rows,
            count(DISTINCT symbol) AS failure_symbols,
            count(*) FILTER (WHERE open_factor_delta > 1e-5) AS open_factor_failure_rows,
            count(*) FILTER (WHERE high_factor_delta > 1e-5) AS high_factor_failure_rows,
            count(*) FILTER (WHERE low_factor_delta > 1e-5) AS low_factor_failure_rows,
            count(*) FILTER (WHERE volume_relative_delta > 1e-5) AS volume_factor_failure_rows,
            max(open_factor_delta) AS max_open_factor_delta,
            max(high_factor_delta) AS max_high_factor_delta,
            max(low_factor_delta) AS max_low_factor_delta,
            max(volume_relative_delta) AS max_volume_relative_delta
        FROM failures
        """
    ).fetchone()

    by_symbol = con.execute(
        failures_cte
        + """
        SELECT
            symbol,
            count(*) AS failure_rows,
            count(*) FILTER (WHERE open_factor_delta > 1e-5) AS open_fail,
            count(*) FILTER (WHERE high_factor_delta > 1e-5) AS high_fail,
            count(*) FILTER (WHERE low_factor_delta > 1e-5) AS low_fail,
            count(*) FILTER (WHERE volume_relative_delta > 1e-5) AS volume_fail,
            max(open_factor_delta) AS max_open_factor_delta,
            max(high_factor_delta) AS max_high_factor_delta,
            max(low_factor_delta) AS max_low_factor_delta,
            max(volume_relative_delta) AS max_volume_relative_delta
        FROM failures
        GROUP BY symbol
        ORDER BY failure_rows DESC, symbol
        LIMIT 100
        """
    ).fetchdf()

    details = con.execute(
        f"""
        WITH paired AS ({paired})
        SELECT
            *,
            abs(factor_open - factor_close) AS open_factor_delta,
            abs(factor_high - factor_close) AS high_factor_delta,
            abs(factor_low - factor_close) AS low_factor_delta,
            CASE WHEN raw_volume > 0
                 THEN abs(adjusted_volume * factor_close - raw_volume)
                      / greatest(1.0, abs(raw_volume))
                 ELSE 0 END AS volume_relative_delta,
            abs(factor_open - factor_close) > 1e-5 AS open_factor_failed,
            abs(factor_high - factor_close) > 1e-5 AS high_factor_failed,
            abs(factor_low - factor_close) > 1e-5 AS low_factor_failed,
            (
                raw_volume > 0
                AND abs(adjusted_volume * factor_close - raw_volume)
                    > greatest(1.0, abs(raw_volume)) * 1e-5
            ) AS volume_factor_failed
        FROM paired
        WHERE {failure}
        ORDER BY
            greatest(
                abs(factor_open - factor_close),
                abs(factor_high - factor_close),
                abs(factor_low - factor_close),
                CASE WHEN raw_volume > 0
                     THEN abs(adjusted_volume * factor_close - raw_volume)
                          / greatest(1.0, abs(raw_volume))
                     ELSE 0 END
            ) DESC,
            symbol,
            session_date
        LIMIT 500
        """
    ).fetchdf()
    details.to_csv(out_path, index=False)
    con.close()

    assert summary is not None
    print()
    print("V2 SPLIT RECONCILIATION DIAGNOSTIC")
    print(f"Eligible symbols: {len(eligible):,}")
    print(f"Previously excluded split symbols: {len(excluded):,}")
    print(f"Failure rows: {int(summary[0]):,}")
    print(f"Failure symbols: {int(summary[1]):,}")
    print(f"Open-factor failure rows: {int(summary[2]):,}")
    print(f"High-factor failure rows: {int(summary[3]):,}")
    print(f"Low-factor failure rows: {int(summary[4]):,}")
    print(f"Volume-factor failure rows: {int(summary[5]):,}")
    print(f"Max open-factor delta: {summary[6]}")
    print(f"Max high-factor delta: {summary[7]}")
    print(f"Max low-factor delta: {summary[8]}")
    print(f"Max volume-relative delta: {summary[9]}")
    print()
    print("FAILURES BY SYMBOL (top 100)")
    print(by_symbol.to_string(index=False))
    print()
    print(f"Detailed first 500 worst rows written to: {out_path}")
    print()
    print("WORST 25 ROWS")
    columns = [
        "symbol",
        "session_date",
        "raw_open",
        "adjusted_open",
        "raw_high",
        "adjusted_high",
        "raw_low",
        "adjusted_low",
        "raw_close",
        "adjusted_close",
        "raw_volume",
        "adjusted_volume",
        "factor_open",
        "factor_high",
        "factor_low",
        "factor_close",
        "open_factor_delta",
        "high_factor_delta",
        "low_factor_delta",
        "volume_relative_delta",
        "open_factor_failed",
        "high_factor_failed",
        "low_factor_failed",
        "volume_factor_failed",
    ]
    print(details[columns].head(25).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
