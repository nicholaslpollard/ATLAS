from pathlib import Path
import re

source_path = Path("packages/backtesting/b35_development_source.py")
test_path = Path("tests/unit/test_b35_development_source.py")
readme_path = Path("README.md")
roadmap_path = Path("docs/roadmap.md")

source = source_path.read_text(encoding="utf-8")
tests = test_path.read_text(encoding="utf-8")
readme = readme_path.read_text(encoding="utf-8")
roadmap = roadmap_path.read_text(encoding="utf-8")

pattern = re.compile(
    r'        try:\n            validation_sql = f""".*?            \)\.fetchdf\(\)\n',
    re.DOTALL,
)
matches = list(pattern.finditer(source))
if len(matches) != 1:
    raise SystemExit(f"load_unit query block: expected one match, found {len(matches)}")

replacement = '''        try:
            # One DuckDB read of the frozen Parquet unit performs both full-file
            # physical/session validation and premarket/regular materialization.
            # The separate SHA-256 verification above remains unchanged. Window
            # validation metrics are computed before the outer materialization
            # filter, so malformed closed/after-hours rows still fail closed.
            combined_sql = f"""
                WITH source_rows AS (
                    SELECT
                        p.*,
                        c.session_date AS __b35_calendar_session_date,
                        c.premarket_start_utc AS __b35_premarket_start_utc,
                        c.regular_open_utc AS __b35_regular_open_utc,
                        c.regular_close_utc AS __b35_regular_close_utc,
                        c.after_hours_end_utc AS __b35_after_hours_end_utc,
                        count(*) OVER (
                            PARTITION BY p.symbol, p.timestamp_utc, p.timeframe, p.session_segment
                        ) AS __b35_duplicate_count
                    FROM read_parquet(?, hive_partitioning=false) p
                    LEFT JOIN b35_calendar c
                      ON p.session_date = c.session_date
                ), checked AS (
                    SELECT
                        *,
                        CASE
                            WHEN __b35_calendar_session_date IS NULL
                                THEN session_segment = 'closed'
                            WHEN timestamp_utc >= __b35_premarket_start_utc
                             AND timestamp_utc < __b35_regular_open_utc
                                THEN session_segment = 'premarket'
                            WHEN timestamp_utc >= __b35_regular_open_utc
                             AND timestamp_utc < __b35_regular_close_utc
                                THEN session_segment = 'regular'
                            WHEN timestamp_utc >= __b35_regular_close_utc
                             AND timestamp_utc < __b35_after_hours_end_utc
                                THEN session_segment = 'after_hours'
                            ELSE session_segment = 'closed'
                        END AS __b35_segment_ok,
                        (
                               session_date IS NULL
                            OR session_date < ? OR session_date >= ?
                            OR symbol IS NULL OR symbol NOT IN ({symbol_placeholders})
                            OR provider IS DISTINCT FROM 'alpaca'
                            OR dataset IS DISTINCT FROM ?
                            OR timeframe IS DISTINCT FROM ?
                            OR is_adjusted IS DISTINCT FROM FALSE
                            OR source_id IS DISTINCT FROM ?
                            OR timestamp_utc IS NULL OR provider_timestamp_utc IS NULL
                            OR timestamp_utc IS DISTINCT FROM provider_timestamp_utc
                            OR date_trunc('minute', timestamp_utc) IS DISTINCT FROM timestamp_utc
                            OR open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL
                            OR volume IS NULL
                            OR NOT isfinite(CAST(open AS DOUBLE))
                            OR NOT isfinite(CAST(high AS DOUBLE))
                            OR NOT isfinite(CAST(low AS DOUBLE))
                            OR NOT isfinite(CAST(close AS DOUBLE))
                            OR NOT isfinite(CAST(volume AS DOUBLE))
                            OR open <= 0 OR high <= 0 OR low <= 0 OR close <= 0
                            OR volume < 0
                            OR high < greatest(open, close)
                            OR low > least(open, close)
                            OR high < low
                            OR (vwap IS NOT NULL AND (
                                   NOT isfinite(CAST(vwap AS DOUBLE)) OR vwap <= 0
                               ))
                            OR (transaction_count IS NOT NULL AND transaction_count < 0)
                        ) AS __b35_invalid_physical
                    FROM source_rows
                ), annotated AS (
                    SELECT
                        *,
                        CAST(count(*) OVER () AS BIGINT) AS __b35_rows,
                        CAST(count(*) FILTER (
                            WHERE __b35_invalid_physical
                        ) OVER () AS BIGINT) AS __b35_invalid_physical_rows,
                        CAST(count(*) FILTER (
                            WHERE __b35_duplicate_count > 1
                        ) OVER () AS BIGINT) AS __b35_duplicate_member_rows,
                        CAST(count(*) FILTER (
                            WHERE __b35_segment_ok IS DISTINCT FROM TRUE
                        ) OVER () AS BIGINT) AS __b35_incorrect_session_rows,
                        row_number() OVER () AS __b35_probe_row
                    FROM checked
                ), selected AS (
                    SELECT
                        *,
                        (
                            session_date BETWEEN ? AND ?
                            AND session_segment IN ('premarket', 'regular')
                        ) AS __b35_materialize
                    FROM annotated
                )
                SELECT * EXCLUDE (
                    __b35_calendar_session_date,
                    __b35_premarket_start_utc,
                    __b35_regular_open_utc,
                    __b35_regular_close_utc,
                    __b35_after_hours_end_utc,
                    __b35_duplicate_count,
                    __b35_segment_ok,
                    __b35_invalid_physical,
                    __b35_probe_row
                )
                FROM selected
                WHERE __b35_materialize OR __b35_probe_row = 1
                ORDER BY __b35_materialize DESC, symbol, session_date, timestamp_utc, session_segment
            """
            params: list[object] = [
                str(binding.canonical_path),
                binding.window_start,
                binding.window_end_exclusive,
                *binding.symbols,
                MINUTE_DATASET,
                MINUTE_TIMEFRAME,
                exact_source_id,
                start_session,
                end_session,
            ]
            frame = con.execute(combined_sql, params).fetchdf()
'''
source = pattern.sub(replacement, source, count=1)

marker = '''        if "is_adjusted" not in frame.columns or str(frame["is_adjusted"].dtype).lower() not in {
'''
if source.count(marker) != 1:
    raise SystemExit("post-query validation marker drifted")
extraction = '''        metric_columns = [
            "__b35_rows",
            "__b35_invalid_physical_rows",
            "__b35_duplicate_member_rows",
            "__b35_incorrect_session_rows",
        ]
        if frame.empty:
            validation = (0, 0, 0, 0)
        else:
            first = frame.iloc[0]
            validation = tuple(int(first[column]) for column in metric_columns)
        if "__b35_materialize" not in frame.columns:
            raise B35DevelopmentSourceError("B35 combined source scan lost materialization marker")
        frame = frame.loc[frame["__b35_materialize"].fillna(False).astype(bool)].copy()
        frame.drop(columns=["__b35_materialize", *metric_columns], inplace=True)

'''
source = source.replace(marker, extraction + marker, 1)

test_marker = '''    assert len(frame) == 1
    assert frame.iloc[0]["symbol"] == "TEST"
'''
if tests.count(test_marker) != 1:
    raise SystemExit("valid-frame test marker drifted")
tests = tests.replace(
    test_marker,
    test_marker + '    assert not any(str(column).startswith("__b35_") for column in frame.columns)\n',
    1,
)

if "**Current as of 2026-09-09 (UTC)." in readme:
    readme = readme.replace(
        "**Current as of 2026-09-09 (UTC).",
        "**Current as of 2026-09-10 (UTC).",
        1,
    )
benchmark_anchor = "**no runtime target may weaken scientific validation, data coverage, outcome quality, or authority controls.**"
if readme.count(benchmark_anchor) != 1:
    raise SystemExit("README B35 performance anchor drifted")
readme = readme.replace(
    benchmark_anchor,
    benchmark_anchor
    + " Workstation equivalence benchmarks now show 5 workers x 2 DuckDB threads at **1,744.4 units/hour / 34.3 hours full**, "
      "8 x 1 at **2,560.9 units/hour / 23.3 hours full**, and 10 x 1 at **2,676.8 units/hour / 22.3 hours full**, with exact "
      "JSONL SHA-256 equivalence at 5/5, 8/8, and 10/10 sampled groups. The small 8-to-10-worker gain identifies a shared "
      "data/processing bottleneck rather than a concurrency shortage. A single-Parquet-scan source-load optimization is now staged: "
      "the separate canonical SHA-256 read remains mandatory, while DuckDB computes full physical/session/duplicate validation and "
      "premarket/regular materialization from one Parquet scan before filtering.",
    1,
)

roadmap_anchor = "The hard performance objective is <24 hours for a full canonical replay where achievable without weakening safeguards; 8-12 hours is a stretch objective, not authority to reduce quality."
if roadmap.count(roadmap_anchor) != 1:
    raise SystemExit("roadmap B35 performance anchor drifted")
roadmap = roadmap.replace(
    roadmap_anchor,
    roadmap_anchor
    + " Workstation probes preserve exact scientific output at **5/5, 8/8, and 10/10** sampled groups and measure respectively "
      "**1,744.4**, **2,560.9**, and **2,676.8 source units/hour** (34.3, 23.3, and 22.3 projected full-replay hours). Because "
      "10 x 1 adds little over 8 x 1, the next staged execution-only optimization collapses the duplicate DuckDB Parquet "
      "validation/materialization scans into one scan while preserving the independent canonical file SHA-256 verification and all fail-closed validators.",
    1,
)

source_path.write_text(source, encoding="utf-8")
test_path.write_text(tests, encoding="utf-8")
readme_path.write_text(readme, encoding="utf-8")
roadmap_path.write_text(roadmap, encoding="utf-8")
