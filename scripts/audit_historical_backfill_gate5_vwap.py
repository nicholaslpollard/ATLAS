from __future__ import annotations

import gzip
import json
import math
from collections import Counter
from pathlib import Path

import duckdb

from packages.core.settings import load_settings


def _finite(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def main() -> None:
    settings = load_settings()
    root = settings.resolved_path(settings.data.paths.derived) / "historical_backfill" / "alpaca"
    acquisition_root = root / "acquisition"
    quality_root = root / "quality"
    manifest_root = acquisition_root / "units"
    anomaly_path = acquisition_root / "response_symbol_anomalies.parquet"
    baseline_report_path = quality_root / "quality_baseline_report.json"

    if not anomaly_path.is_file() or not baseline_report_path.is_file():
        raise SystemExit("Gate 5 VWAP audit requires Gate 3 anomalies and Gate 5-A baseline artifacts")

    baseline = json.loads(baseline_report_path.read_text(encoding="utf-8"))

    con = duckdb.connect(":memory:")
    try:
        rows = con.execute(
            "SELECT year, batch_index, returned_symbol "
            "FROM read_parquet(?) WHERE returned_symbol IS NOT NULL "
            "GROUP BY 1,2,3 ORDER BY 1,2,3",
            [str(anomaly_path)],
        ).fetchall()
    finally:
        con.close()
    anomaly_keys = {(int(year), int(batch), str(symbol)) for year, batch, symbol in rows}

    total = 0
    missing = 0
    nonfinite = 0
    negative = 0
    zero = 0
    positive = 0
    zero_volume_zero = 0
    zero_volume_positive = 0
    zero_trade_count_zero = 0
    zero_trade_count_positive = 0
    zero_all_ohlc_equal = 0
    zero_symbols: Counter[str] = Counter()
    zero_years: Counter[int] = Counter()
    zero_value_types: Counter[str] = Counter()
    examples: list[dict[str, object]] = []

    manifests = sorted(manifest_root.glob("*/*.json"))
    for manifest_path in manifests:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        year = int(manifest_path.parent.name)
        batch_index = int(manifest_path.stem.split("_")[-1])

        for page_record in manifest.get("raw_pages") or []:
            payload_path = Path(str(page_record.get("payload_path") or ""))
            if not payload_path.is_file():
                raise RuntimeError(f"missing retained raw page: {payload_path}")
            with gzip.open(payload_path, "rt", encoding="utf-8") as handle:
                payload = json.load(handle)
            bars = payload.get("bars") if isinstance(payload, dict) else None
            if not isinstance(bars, dict):
                raise RuntimeError(f"unexpected retained raw page shape: {payload_path}")

            for raw_symbol, values in bars.items():
                symbol = str(raw_symbol)
                if (year, batch_index, symbol) in anomaly_keys:
                    continue
                if not isinstance(values, list):
                    raise RuntimeError(f"unexpected bar list for {symbol!r}: {payload_path}")

                for record in values:
                    total += 1
                    if not isinstance(record, dict):
                        continue
                    raw_vwap = record.get("vw")
                    if raw_vwap is None:
                        missing += 1
                        continue
                    vwap = _finite(raw_vwap)
                    if vwap is None:
                        nonfinite += 1
                        continue
                    if vwap < 0:
                        negative += 1
                        continue
                    if vwap > 0:
                        positive += 1
                        continue

                    zero += 1
                    zero_years[year] += 1
                    zero_symbols[symbol] += 1
                    zero_value_types[type(raw_vwap).__name__] += 1

                    volume = _finite(record.get("v"))
                    trades = _finite(record.get("n"))
                    if volume == 0:
                        zero_volume_zero += 1
                    elif volume is not None and volume > 0:
                        zero_volume_positive += 1
                    if trades == 0:
                        zero_trade_count_zero += 1
                    elif trades is not None and trades > 0:
                        zero_trade_count_positive += 1

                    o = _finite(record.get("o"))
                    h = _finite(record.get("h"))
                    l = _finite(record.get("l"))
                    c = _finite(record.get("c"))
                    if None not in (o, h, l, c) and o == h == l == c:
                        zero_all_ohlc_equal += 1

                    if len(examples) < 40:
                        examples.append(
                            {
                                "year": year,
                                "symbol": symbol,
                                "t": record.get("t"),
                                "o": record.get("o"),
                                "h": record.get("h"),
                                "l": record.get("l"),
                                "c": record.get("c"),
                                "v": record.get("v"),
                                "n": record.get("n"),
                                "vw": raw_vwap,
                            }
                        )

    print("ATLAS Gate 5-A VWAP Sentinel Audit")
    print("  safety: retained identity-safe raw bars only; no provider fetch; no writes")
    print(f"  identity-safe rows scanned:       {total:,}")
    print(f"  Gate 5-A reported invalid VWAP:   {int(baseline.get('invalid_vwap_rows', -1)):,}")
    print("  VWAP value classes:")
    print(f"    missing:                        {missing:,}")
    print(f"    non-finite/non-numeric:         {nonfinite:,}")
    print(f"    negative:                       {negative:,}")
    print(f"    exactly zero:                   {zero:,}")
    print(f"    positive finite:                {positive:,}")
    print(f"  zero VWAP symbols:                {len(zero_symbols):,}")
    print("  zero-VWAP accompanying fields:")
    print(f"    volume == 0:                    {zero_volume_zero:,}")
    print(f"    volume > 0:                     {zero_volume_positive:,}")
    print(f"    trade count == 0:               {zero_trade_count_zero:,}")
    print(f"    trade count > 0:                {zero_trade_count_positive:,}")
    print(f"    O=H=L=C:                        {zero_all_ohlc_equal:,}")
    print("  zero VWAP by year:")
    for year in sorted(zero_years):
        print(f"    {year}: {zero_years[year]:,}")
    print("  zero VWAP raw JSON value types:")
    for name, count in zero_value_types.most_common():
        print(f"    {name}: {count:,}")
    print("  top zero-VWAP symbols:")
    for symbol, count in zero_symbols.most_common(40):
        print(f"    {symbol:16s} {count:,}")
    print("  representative zero-VWAP rows:")
    for row in examples:
        print(
            "    "
            f"{row['year']} {str(row['symbol']):16s} t={row['t']} "
            f"O={row['o']} H={row['h']} L={row['l']} C={row['c']} "
            f"V={row['v']} N={row['n']} VW={row['vw']}"
        )

    classified_nonpositive = zero + negative + nonfinite
    print("  reconciliation:")
    print(f"    nonpositive/nonfinite VWAP rows: {classified_nonpositive:,}")
    print(
        "    matches Gate 5-A invalid VWAP:  "
        f"{classified_nonpositive == int(baseline.get('invalid_vwap_rows', -1))}"
    )


if __name__ == "__main__":
    main()
