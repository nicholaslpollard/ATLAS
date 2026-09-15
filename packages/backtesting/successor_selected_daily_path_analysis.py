from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pandas as pd

from packages.backtesting.reference_v2_lake_adapter import (
    REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION,
    ReferenceV2DailyLakeAdapter,
)
from packages.backtesting.successor_development_outcomes import DEVELOPMENT_END, DEVELOPMENT_START
from packages.backtesting.successor_optionworthiness_analysis import (
    conditioning_root,
    optionworthiness_root,
    validate_conditioning_inputs,
)
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import load_settings
from packages.strategies.successor_selected_daily_path_contract import (
    ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
    AUTHORITY,
    MOVE_THRESHOLDS,
    PATH_HORIZON_SESSIONS,
    SUCCESSOR_SELECTED_DAILY_PATH_CONTRACT,
    SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
    successor_selected_daily_path_manifest,
)


SUCCESSOR_SELECTED_DAILY_PATH_ANALYSIS_CONTRACT = (
    "atlas-successor-selected-daily-path-analysis-v1-source-bound-five-session"
)
EXPECTED_SELECTED_DAILY_COMPARABLE = 35_995


class SuccessorSelectedDailyPathError(RuntimeError):
    pass


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _stable_hash(value: object) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, payload: object) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _sql_paths(paths: tuple[Path, ...]) -> str:
    return "[" + ",".join(f"'{_sql_path(path)}'" for path in paths) + "]"


def _copy_query_atomic(conn: duckdb.DuckDBPyConnection, query: str, target: Path) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(target)
    try:
        conn.execute(
            f"COPY ({query}) TO '{_sql_path(temp)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        with temp.open("rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(target)}')").fetchone()[0])


def selected_daily_path_root(project_root: Path) -> Path:
    # Keep derived path artifacts beside, rather than beneath, option-worthiness.
    # The scientific binding to the accepted option-worthiness run is validated
    # separately in _validate_optionworthiness(); nesting it here needlessly pushed
    # Windows atomic destinations beyond legacy-safe path lengths.
    return (
        conditioning_root(project_root)
        / "selected_daily_path_v1"
        / SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT[:16]
    ).resolve()


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorSelectedDailyPathError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise SuccessorSelectedDailyPathError(f"JSON artifact is not an object: {path}")
    return value


def _validate_optionworthiness(project_root: Path) -> dict[str, object]:
    summary_path = optionworthiness_root(project_root) / "analysis_summary.json"
    if not summary_path.is_file():
        raise SuccessorSelectedDailyPathError(
            "accepted option-worthiness analysis is missing; run that package first"
        )
    summary = _read_json(summary_path)
    if summary.get("status") != "COMPLETE_OPTIONWORTHINESS_DIAGNOSTICS_ONLY":
        raise SuccessorSelectedDailyPathError("option-worthiness analysis is not complete")
    if summary.get("analysis_fingerprint") != ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT:
        raise SuccessorSelectedDailyPathError("option-worthiness analysis fingerprint drifted")
    for key in (
        "raw_market_data_reread",
        "historical_option_data_read",
        "confluence_opened",
        "paper_authority",
        "live_authority",
        "strategy_promotion",
        "selector_promotion",
        "option_trading_authority",
    ):
        if summary.get(key) is not False:
            raise SuccessorSelectedDailyPathError(f"option-worthiness authority drifted: {key}")
    counts = summary.get("scope_counts")
    if not isinstance(counts, dict) or int(counts.get("walk_forward_selected_comparable", -1)) != 36_254:
        raise SuccessorSelectedDailyPathError("option-worthiness selected population drifted")
    return {
        "analysis_fingerprint": str(summary["analysis_fingerprint"]),
        "output_artifact_set_fingerprint": str(summary["output_artifact_set_fingerprint"]),
        "summary_sha256": _sha256_file(summary_path),
    }


def _selected_assignments(project_root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    conditioning_binding = validate_conditioning_inputs(project_root)
    assignment_path = conditioning_root(project_root) / "eligibility_assignments.parquet"
    conn = duckdb.connect()
    try:
        frame = conn.execute(
            f"""
            SELECT fold_id, policy_id, economic_family_id, native_timeframe,
                   instrument_key, ticker, session_date, direction,
                   primary_net_return, stress_net_return
            FROM read_parquet('{_sql_path(assignment_path)}')
            WHERE research_eligible AND comparable AND native_timeframe='1d'
            ORDER BY policy_id, direction, instrument_key, session_date, fold_id
            """
        ).fetchdf()
    finally:
        conn.close()
    if len(frame) != EXPECTED_SELECTED_DAILY_COMPARABLE:
        raise SuccessorSelectedDailyPathError(
            f"selected daily population drifted: {len(frame)} != {EXPECTED_SELECTED_DAILY_COMPARABLE}"
        )
    duplicates = int(
        frame.duplicated(
            subset=["fold_id", "policy_id", "direction", "instrument_key", "session_date"]
        ).sum()
    )
    if duplicates:
        raise SuccessorSelectedDailyPathError(f"selected daily population has {duplicates} duplicate keys")
    return frame, conditioning_binding


def _validated_daily_source(
    conn: duckdb.DuckDBPyConnection,
    project_root: Path,
) -> tuple[str, dict[str, object]]:
    settings = load_settings(project_root)
    adapter = ReferenceV2DailyLakeAdapter(settings)
    manifest_path, manifest = adapter._manifest(None)
    source_start, source_end, _sessions = adapter._scope(
        DEVELOPMENT_START, DEVELOPMENT_END, manifest
    )
    paths, inventory = adapter._partitions(manifest)
    selected_paths = tuple(
        path
        for path, record in zip(paths, inventory, strict=True)
        if DEVELOPMENT_START.year <= int(record["year"]) <= DEVELOPMENT_END.year
    )
    if not selected_paths:
        raise SuccessorSelectedDailyPathError("DEVELOPMENT daily source selected no partitions")

    source_sql = f"read_parquet({_sql_paths(selected_paths)}, hive_partitioning=false)"
    description = conn.execute(f"DESCRIBE SELECT * FROM {source_sql}").fetchall()
    names = tuple(str(row[0]) for row in description)
    if names != adapter._EXPECTED_COLUMNS:
        raise SuccessorSelectedDailyPathError("DEVELOPMENT daily physical columns drifted")

    manifest_sha = _sha256_file(manifest_path)
    source_fingerprint = _stable_hash(
        {
            "contract_version": REFERENCE_V2_LAKE_ADAPTER_CONTRACT_VERSION,
            "manifest_sha256": manifest_sha,
            "research_daily_fingerprint": manifest["source_fingerprint"],
            "start_date": DEVELOPMENT_START,
            "end_date": DEVELOPMENT_END,
            "selected_partition_sha256": [
                item["sha256"]
                for item in inventory
                if DEVELOPMENT_START.year <= int(item["year"]) <= DEVELOPMENT_END.year
            ],
            "v1_fallback": "FORBIDDEN",
            "evaluation_scope": adapter._REPORT_SCOPE,
            "protected_master_return_rows_read": 0,
        }
    )
    report: dict[str, object] = {
        "status": "PASS_HASH_BOUND_TARGETED_PROJECTION",
        "scope": adapter._REPORT_SCOPE,
        "source_start_date": source_start.isoformat(),
        "source_cutoff_session": source_end.isoformat(),
        "manifest_path": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "research_daily_fingerprint": manifest["source_fingerprint"],
        "source_fingerprint": source_fingerprint,
        "verified_partitions": len(paths),
        "selected_partitions": len(selected_paths),
        "manifest_research_rows": int(manifest["research_rows"]),
        "protected_master_return_rows_read": 0,
        "v1_rows_read": 0,
        "legacy_fallback_used": False,
        "projection": "SELECTED_INSTRUMENTS_OHLC_ONLY",
    }
    return source_sql, report


def _prepare_path_relations(
    conn: duckdb.DuckDBPyConnection,
    source_relation: str,
) -> dict[str, int]:
    conn.execute(
        "CREATE TEMP TABLE selected_instruments AS "
        "SELECT DISTINCT instrument_key FROM selected"
    )
    selected_instruments = int(
        conn.execute("SELECT count(*) FROM selected_instruments").fetchone()[0]
    )

    conn.execute(
        f"""
        CREATE TEMP TABLE ordered_daily_bars AS
        SELECT b.instrument_id, b.session_date, b.open, b.high, b.low, b.close,
               row_number() OVER (
                   PARTITION BY b.instrument_id ORDER BY b.session_date
               ) AS rn
        FROM {source_relation} b
        JOIN selected_instruments i ON i.instrument_key=b.instrument_id
        WHERE b.session_date BETWEEN DATE '{DEVELOPMENT_START}' AND DATE '{DEVELOPMENT_END}'
        """
    )
    ordered_rows = int(
        conn.execute("SELECT count(*) FROM ordered_daily_bars").fetchone()[0]
    )
    if ordered_rows < EXPECTED_SELECTED_DAILY_COMPARABLE:
        raise SuccessorSelectedDailyPathError("projected daily source is unexpectedly sparse")

    conn.execute(
        """
        CREATE TEMP TABLE selected_positions AS
        SELECT s.*, b.rn AS signal_rn
        FROM selected s
        JOIN ordered_daily_bars b
          ON b.instrument_id=s.instrument_key AND b.session_date=s.session_date
        """
    )
    selected_positions = int(
        conn.execute("SELECT count(*) FROM selected_positions").fetchone()[0]
    )
    if selected_positions != EXPECTED_SELECTED_DAILY_COMPARABLE:
        raise SuccessorSelectedDailyPathError(
            f"selected signal/source join incomplete: {selected_positions} != "
            f"{EXPECTED_SELECTED_DAILY_COMPARABLE}"
        )

    conn.execute(
        f"""
        CREATE TEMP TABLE targeted_daily_bars AS
        SELECT b.*
        FROM ordered_daily_bars b
        JOIN (
            SELECT DISTINCT instrument_key AS instrument_id,
                   signal_rn + offsets.path_offset AS rn
            FROM selected_positions
            CROSS JOIN range(0, {PATH_HORIZON_SESSIONS + 1}) offsets(path_offset)
        ) targets USING (instrument_id, rn)
        """
    )
    targeted_rows = int(
        conn.execute("SELECT count(*) FROM targeted_daily_bars").fetchone()[0]
    )
    if targeted_rows < selected_positions:
        raise SuccessorSelectedDailyPathError("targeted daily path materialization is empty or incomplete")

    return {
        "selected_instruments": selected_instruments,
        "ordered_daily_rows": ordered_rows,
        "selected_positions": selected_positions,
        "targeted_daily_rows": targeted_rows,
    }


def _direction_expr(direction: str, long_expr: str, short_expr: str) -> str:
    return f"CASE WHEN {direction}='LONG' THEN {long_expr} ELSE {short_expr} END"


def _path_query() -> str:
    future_joins = "\n".join(
        f"JOIN targeted_daily_bars b{i} ON "
        f"b{i}.instrument_id=s.instrument_key AND b{i}.rn=s.signal_rn+{i}"
        for i in range(1, PATH_HORIZON_SESSIONS + 1)
    )
    fav_cols: list[str] = []
    adv_cols: list[str] = []
    for i in range(1, PATH_HORIZON_SESSIONS + 1):
        fav_cols.append(
            _direction_expr(
                "s.direction",
                f"b{i}.high / b1.open - 1.0",
                f"1.0 - b{i}.low / b1.open",
            )
            + f" AS fav_{i}"
        )
        adv_cols.append(
            _direction_expr(
                "s.direction",
                f"1.0 - b{i}.low / b1.open",
                f"b{i}.high / b1.open - 1.0",
            )
            + f" AS adv_{i}"
        )
    favorable_list = ", ".join(f"fav_{i}" for i in range(1, 6))
    adverse_list = ", ".join(f"adv_{i}" for i in range(1, 6))
    return f"""
    WITH joined AS (
        SELECT s.*,
               b1.open AS entry_price, b1.session_date AS entry_session,
               b5.close AS exit5_close, b5.session_date AS exit5_session,
               {', '.join(f'b{i}.session_date AS path_session_{i}' for i in range(1, 6))},
               {', '.join(fav_cols)},
               {', '.join(adv_cols)}
        FROM selected_positions s
        {future_joins}
    ), path AS (
        SELECT *,
               CASE WHEN direction='LONG' THEN exit5_close / entry_price - 1.0
                    ELSE 1.0 - exit5_close / entry_price END AS gross_return_5,
               greatest({favorable_list}) AS mfe_5,
               greatest({adverse_list}) AS adverse_excursion_5
        FROM joined
        WHERE entry_price IS NOT NULL AND exit5_close IS NOT NULL
          AND { ' AND '.join(f'path_session_{i} IS NOT NULL' for i in range(1, 6)) }
    )
    SELECT *,
           CASE WHEN mfe_5 > 0 THEN gross_return_5 / mfe_5 END AS exit_capture_ratio,
           mfe_5 - gross_return_5 AS peak_giveback
    FROM path
    """


def _first_touch_case(prefix: str, threshold: float) -> str:
    terms = " ".join(
        f"WHEN {prefix}_{i} >= {threshold:.8f} THEN {i}" for i in range(1, 6)
    )
    return f"CASE {terms} ELSE NULL END"


def _threshold_query(path_file: Path) -> str:
    pieces: list[str] = []
    for threshold in MOVE_THRESHOLDS:
        fav = _first_touch_case("fav", threshold)
        adv = _first_touch_case("adv", threshold)
        pieces.append(
            f"""
            SELECT *, {threshold:.8f} AS move_threshold,
                   {fav} AS first_favorable_session,
                   {adv} AS first_adverse_session,
                   CASE
                     WHEN ({fav}) IS NULL AND ({adv}) IS NULL THEN 'NEITHER'
                     WHEN ({fav}) IS NOT NULL AND ({adv}) IS NULL THEN 'FAVORABLE_ONLY'
                     WHEN ({fav}) IS NULL AND ({adv}) IS NOT NULL THEN 'ADVERSE_ONLY'
                     WHEN ({fav}) < ({adv}) THEN 'FAVORABLE_FIRST'
                     WHEN ({adv}) < ({fav}) THEN 'ADVERSE_FIRST'
                     ELSE 'SAME_SESSION_COLLISION_UNORDERED'
                   END AS first_touch_class
            FROM read_parquet('{_sql_path(path_file)}')
            """
        )
    return " UNION ALL ".join(pieces)


def _summary_query(threshold_file: Path) -> str:
    return f"""
    SELECT policy_id, direction, move_threshold,
           count(*) AS selected_comparable,
           avg(CASE WHEN first_favorable_session IS NOT NULL THEN 1.0 ELSE 0.0 END) AS favorable_hit_rate_5,
           avg(CASE WHEN first_adverse_session IS NOT NULL THEN 1.0 ELSE 0.0 END) AS adverse_hit_rate_5,
           avg(CASE WHEN first_touch_class IN ('FAVORABLE_ONLY','FAVORABLE_FIRST') THEN 1.0 ELSE 0.0 END) AS favorable_before_adverse_rate,
           avg(CASE WHEN first_touch_class IN ('ADVERSE_ONLY','ADVERSE_FIRST') THEN 1.0 ELSE 0.0 END) AS adverse_before_favorable_rate,
           avg(CASE WHEN first_touch_class='SAME_SESSION_COLLISION_UNORDERED' THEN 1.0 ELSE 0.0 END) AS same_session_collision_rate,
           avg(first_favorable_session) FILTER (WHERE first_favorable_session IS NOT NULL) AS mean_first_favorable_session,
           median(first_favorable_session) FILTER (WHERE first_favorable_session IS NOT NULL) AS median_first_favorable_session,
           avg(first_adverse_session) FILTER (WHERE first_adverse_session IS NOT NULL) AS mean_first_adverse_session
    FROM read_parquet('{_sql_path(threshold_file)}')
    GROUP BY policy_id, direction, move_threshold
    ORDER BY policy_id, direction, move_threshold
    """


def _route_query(path_file: Path) -> str:
    return f"""
    SELECT policy_id, economic_family_id, direction,
           count(*) AS selected_comparable,
           count(DISTINCT fold_id) AS active_folds,
           avg(gross_return_5) AS mean_gross_return_5,
           median(gross_return_5) AS median_gross_return_5,
           avg(mfe_5) AS mean_mfe_5,
           median(mfe_5) AS median_mfe_5,
           quantile_cont(mfe_5, 0.90) AS p90_mfe_5,
           avg(adverse_excursion_5) AS mean_adverse_excursion_5,
           median(adverse_excursion_5) AS median_adverse_excursion_5,
           avg(exit_capture_ratio) FILTER (WHERE mfe_5 > 0) AS mean_exit_capture_ratio,
           median(exit_capture_ratio) FILTER (WHERE mfe_5 > 0) AS median_exit_capture_ratio,
           avg(peak_giveback) AS mean_peak_giveback,
           median(peak_giveback) AS median_peak_giveback,
           avg(primary_net_return) AS retained_mean_primary_net_return,
           avg(stress_net_return) AS retained_mean_stress_net_return
    FROM read_parquet('{_sql_path(path_file)}')
    GROUP BY policy_id, economic_family_id, direction
    ORDER BY policy_id, direction
    """


def _clean_rows(conn: duckdb.DuckDBPyConnection, query: str) -> list[dict[str, object]]:
    result = conn.execute(query)
    columns = [item[0] for item in result.description]
    rows: list[dict[str, object]] = []
    for raw in result.fetchall():
        row: dict[str, object] = {}
        for key, value in zip(columns, raw, strict=True):
            if isinstance(value, float) and not math.isfinite(value):
                row[key] = None
            else:
                row[key] = value
        rows.append(row)
    return rows


def run_successor_selected_daily_path_analysis(project_root: Path) -> dict[str, object]:
    project = Path(project_root).resolve()
    output_root = selected_daily_path_root(project)
    output_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    _write_json(output_root / "selected_daily_path_contract.json", successor_selected_daily_path_manifest())
    print(
        "successor selected daily path authority: DEVELOPMENT selected diagnostics only; "
        "master/future/provider/broker/PAPER/LIVE/promotion/confluence/option authority forbidden",
        flush=True,
    )

    option_binding = _validate_optionworthiness(project)
    selected, conditioning_binding = _selected_assignments(project)
    print(f"selected daily assignments validated: {len(selected):,}", flush=True)

    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, min(8, os.cpu_count() or 1))}")
    conn.execute("PRAGMA preserve_insertion_order=false")
    conn.register("selected", selected)
    try:
        print("daily source lineage: verifying manifest and partition hashes...", flush=True)
        source_sql, report = _validated_daily_source(conn, project)
        print(
            f"daily source lineage verified: {int(report['verified_partitions']):,} partitions / "
            f"{int(report['manifest_research_rows']):,} manifest rows; "
            "materializing selected-instrument OHLC index...",
            flush=True,
        )
        prep_started = time.monotonic()
        prep = _prepare_path_relations(conn, source_sql)
        print(
            "selected path index prepared: "
            f"{prep['selected_instruments']:,} instruments / "
            f"{prep['ordered_daily_rows']:,} projected daily rows / "
            f"{prep['targeted_daily_rows']:,} targeted rows / "
            f"{time.monotonic() - prep_started:.1f}s; building five-session paths...",
            flush=True,
        )

        path_file = output_root / "selected_daily_paths.parquet"
        threshold_file = output_root / "selected_daily_thresholds.parquet"
        route_file = output_root / "route_path_summary.parquet"
        threshold_summary_file = output_root / "route_threshold_summary.parquet"

        path_started = time.monotonic()
        path_count = _copy_query_atomic(conn, _path_query(), path_file)
        if path_count != EXPECTED_SELECTED_DAILY_COMPARABLE:
            raise SuccessorSelectedDailyPathError(
                f"five-session path coverage incomplete: {path_count} != {EXPECTED_SELECTED_DAILY_COMPARABLE}"
            )
        print(
            f"five-session paths complete: {path_count:,} / {time.monotonic() - path_started:.1f}s; "
            "expanding first-touch thresholds...",
            flush=True,
        )
        threshold_count = _copy_query_atomic(conn, _threshold_query(path_file), threshold_file)
        if threshold_count != EXPECTED_SELECTED_DAILY_COMPARABLE * len(MOVE_THRESHOLDS):
            raise SuccessorSelectedDailyPathError("threshold expansion row count drifted")
        print(
            f"threshold expansion complete: {threshold_count:,}; summarizing routes...",
            flush=True,
        )
        _copy_query_atomic(conn, _route_query(path_file), route_file)
        _copy_query_atomic(conn, _summary_query(threshold_file), threshold_summary_file)

        route_rows = _clean_rows(
            conn,
            f"SELECT * FROM read_parquet('{_sql_path(route_file)}') ORDER BY policy_id, direction",
        )
        threshold_rows = _clean_rows(
            conn,
            f"SELECT * FROM read_parquet('{_sql_path(threshold_summary_file)}') ORDER BY policy_id, direction, move_threshold",
        )
        outputs = []
        for name, path in (
            ("selected_daily_paths", path_file),
            ("selected_daily_thresholds", threshold_file),
            ("route_path_summary", route_file),
            ("route_threshold_summary", threshold_summary_file),
        ):
            outputs.append({"name": name, "path": str(path), "sha256": _sha256_file(path)})
        output_artifact_set_fingerprint = canonical_sha256(outputs)
        result: dict[str, object] = {
            "status": "COMPLETE_SELECTED_DAILY_PATH_DIAGNOSTICS_ONLY",
            "analysis_contract": SUCCESSOR_SELECTED_DAILY_PATH_ANALYSIS_CONTRACT,
            "selected_daily_path_contract": SUCCESSOR_SELECTED_DAILY_PATH_CONTRACT,
            "selected_daily_path_fingerprint": SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
            "accepted_optionworthiness": option_binding,
            "conditioning_analysis_fingerprint": conditioning_binding["conditioning_analysis_fingerprint"],
            "daily_source_report_fingerprint": report.get("source_fingerprint"),
            "source_execution_profile": {
                "mode": "HASH_BOUND_DUCKDB_SELECTED_INSTRUMENT_PROJECTION",
                **prep,
            },
            "selected_daily_comparable": path_count,
            "path_horizon_sessions": PATH_HORIZON_SESSIONS,
            "move_thresholds_fraction": list(MOVE_THRESHOLDS),
            "route_path_summary": route_rows,
            "route_threshold_summary": threshold_rows,
            "outputs": outputs,
            "output_artifact_set_fingerprint": output_artifact_set_fingerprint,
            "daily_bar_intraday_order_claimed": False,
            "minute_level_timing_claimed": False,
            "historical_option_pnl_claimed": False,
            "composite_optionworthiness_score": False,
            "intraday_routes_analyzed": False,
            "confluence_opened": False,
            "consumed_master_rows_read": 0,
            "future_blind_rows_read": 0,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "strategy_promotion": False,
            "selector_promotion": False,
            "option_trading_authority": False,
            "authority": AUTHORITY,
        }
        result["analysis_fingerprint"] = canonical_sha256(
            {
                "selected_daily_path_fingerprint": SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
                "accepted_optionworthiness_analysis_fingerprint": ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
                "conditioning_analysis_fingerprint": conditioning_binding["conditioning_analysis_fingerprint"],
                "daily_source_report_fingerprint": report.get("source_fingerprint"),
                "output_artifact_set_fingerprint": output_artifact_set_fingerprint,
            }
        )
        _write_json(output_root / "analysis_summary.json", result)
        _write_json(
            output_root / "progress.json",
            {
                "state": "COMPLETE",
                "analysis_fingerprint": result["analysis_fingerprint"],
                "elapsed_seconds": time.monotonic() - started,
                "completed_at_utc": datetime.now(UTC).isoformat(),
            },
        )
        return result
    finally:
        conn.unregister("selected")
        conn.close()
