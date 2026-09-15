from __future__ import annotations

import hashlib
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import duckdb

from packages.backtesting.successor_conditioning_analysis import (
    SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
)
from packages.backtesting.successor_runner_contract import canonical_sha256, successor_policy_routes
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_GROUP_COUNT,
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
    ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
    ACCEPTED_STANDALONE_RECORD_COUNT,
    ACCEPTED_STANDALONE_RUN_FINGERPRINT,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)
from packages.strategies.successor_optionworthiness_contract import (
    ANALYSIS_SUBSETS,
    AUTHORITY,
    MOVE_THRESHOLDS,
    SUCCESSOR_OPTIONWORTHINESS_CONTRACT,
    SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
    successor_optionworthiness_manifest,
)


SUCCESSOR_OPTIONWORTHINESS_ANALYSIS_CONTRACT = (
    "atlas-successor-optionworthiness-analysis-v1-retained-conditioning-artifacts"
)
SHA_WORKERS_MAX = 8
MACHINE_HEARTBEAT_SECONDS = 30.0
CONSOLE_HEARTBEAT_SECONDS = 300.0


class SuccessorOptionworthinessError(RuntimeError):
    pass


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _copy_query_atomic(
    conn: duckdb.DuckDBPyConnection,
    query: str,
    target: Path,
    *,
    row_group_size: int = 100_000,
) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(target)
    try:
        conn.execute(
            f"COPY ({query}) TO '{_sql_path(temp)}' "
            f"(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE {int(row_group_size)})"
        )
        with temp.open("rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(target)}')").fetchone()[0])


def _standalone_root(project_root: Path) -> Path:
    return (
        project_root.resolve()
        / "data"
        / "v2_build"
        / "alpaca_sip_v2"
        / "derived"
        / "strategy_lab"
        / "successor_development"
        / ACCEPTED_RUN_CONTRACT_FINGERPRINT[:16]
    ).resolve()


def conditioning_root(project_root: Path) -> Path:
    return (
        _standalone_root(project_root)
        / "conditioning_v1"
        / SUCCESSOR_CONDITIONING_FINGERPRINT[:16]
    ).resolve()


def optionworthiness_root(project_root: Path) -> Path:
    return (
        conditioning_root(project_root)
        / "optionworthiness_v1"
        / SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT[:16]
    ).resolve()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorOptionworthinessError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise SuccessorOptionworthinessError(f"JSON artifact is not an object: {path}")
    return payload


def _validate_receipt(path: Path, *, phase: str) -> dict[str, object]:
    receipt_path = path.with_suffix(path.suffix + ".receipt.json")
    if not path.is_file() or not receipt_path.is_file():
        raise SuccessorOptionworthinessError(f"conditioning artifact or receipt is missing: {path}")
    receipt = _read_json(receipt_path)
    expected_receipt_id = _stable_hash(
        {key: value for key, value in receipt.items() if key != "receipt_id"}
    )
    if receipt.get("receipt_id") != expected_receipt_id:
        raise SuccessorOptionworthinessError(f"conditioning receipt self-hash drifted: {receipt_path}")
    if receipt.get("contract") != SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT:
        raise SuccessorOptionworthinessError(f"conditioning receipt contract drifted: {receipt_path}")
    if receipt.get("conditioning_fingerprint") != SUCCESSOR_CONDITIONING_FINGERPRINT:
        raise SuccessorOptionworthinessError(f"conditioning receipt fingerprint drifted: {receipt_path}")
    if receipt.get("phase") != phase:
        raise SuccessorOptionworthinessError(f"conditioning receipt phase drifted: {receipt_path}")
    if receipt.get("artifact_path") != str(path.resolve()):
        raise SuccessorOptionworthinessError(f"conditioning receipt path drifted: {receipt_path}")
    observed_sha = _sha256_file(path)
    if receipt.get("artifact_sha256") != observed_sha:
        raise SuccessorOptionworthinessError(f"conditioning artifact SHA drifted: {path}")
    return receipt


def _validate_normalized_one(path: Path) -> dict[str, object]:
    receipt = _validate_receipt(path, phase="NORMALIZE_PART")
    count = int(receipt.get("row_count", -1))
    if count < 0:
        raise SuccessorOptionworthinessError(f"normalized row count is invalid: {path}")
    return {
        "token": path.stem,
        "row_count": count,
        "sha256": str(receipt["artifact_sha256"]),
    }


def _assert_zero_authority(summary: dict[str, object]) -> None:
    if summary.get("confluence_opened") is not False:
        raise SuccessorOptionworthinessError("conditioning summary unexpectedly opened confluence")
    for key in (
        "consumed_master_rows_read",
        "future_blind_rows_read",
        "provider_calls",
        "broker_reads",
        "broker_writes",
    ):
        if int(summary.get(key, -1)) != 0:
            raise SuccessorOptionworthinessError(f"conditioning summary authority drifted: {key}")
    for key in (
        "paper_authority",
        "live_authority",
        "strategy_promotion",
        "selector_promotion",
    ):
        if summary.get(key) is not False:
            raise SuccessorOptionworthinessError(f"conditioning summary authority drifted: {key}")


def validate_conditioning_inputs(
    project_root: Path,
    *,
    progress_callback: callable | None = None,
) -> dict[str, object]:
    root = conditioning_root(project_root)
    summary_path = root / "analysis_summary.json"
    if not summary_path.is_file():
        raise SuccessorOptionworthinessError(
            "accepted successor conditioning summary is missing; run the accepted conditioning package first"
        )
    summary = _read_json(summary_path)
    if summary.get("status") != "COMPLETE_CONDITIONING_ONLY":
        raise SuccessorOptionworthinessError("successor conditioning is not complete")
    if summary.get("contract") != SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT:
        raise SuccessorOptionworthinessError("successor conditioning analysis contract drifted")
    if summary.get("conditioning_fingerprint") != SUCCESSOR_CONDITIONING_FINGERPRINT:
        raise SuccessorOptionworthinessError("successor conditioning fingerprint drifted")
    if summary.get("conditioning_opened") is not True:
        raise SuccessorOptionworthinessError("conditioning summary does not record conditioning as opened")
    _assert_zero_authority(summary)

    accepted = summary.get("accepted_standalone")
    normalized = summary.get("normalized")
    if not isinstance(accepted, dict) or not isinstance(normalized, dict):
        raise SuccessorOptionworthinessError("conditioning accepted-input binding is malformed")
    required_accepted = {
        "run_contract_fingerprint": ACCEPTED_RUN_CONTRACT_FINGERPRINT,
        "standalone_run_fingerprint": ACCEPTED_STANDALONE_RUN_FINGERPRINT,
        "artifact_set_fingerprint": ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
        "group_count": ACCEPTED_GROUP_COUNT,
        "record_count": ACCEPTED_STANDALONE_RECORD_COUNT,
    }
    for key, expected in required_accepted.items():
        if accepted.get(key) != expected:
            raise SuccessorOptionworthinessError(f"conditioning standalone binding drifted: {key}")
    if int(normalized.get("part_count", -1)) != ACCEPTED_GROUP_COUNT:
        raise SuccessorOptionworthinessError("conditioning normalized part count drifted")
    if int(normalized.get("record_count", -1)) != ACCEPTED_STANDALONE_RECORD_COUNT:
        raise SuccessorOptionworthinessError("conditioning normalized record count drifted")

    assignment_path = root / "eligibility_assignments.parquet"
    assignment_receipt = _validate_receipt(assignment_path, phase="ELIGIBILITY_ASSIGNMENTS")
    output_rows = summary.get("outputs")
    if not isinstance(output_rows, list):
        raise SuccessorOptionworthinessError("conditioning output inventory is missing")
    assignment_identity = next(
        (item for item in output_rows if isinstance(item, dict) and item.get("name") == "eligibility_assignments"),
        None,
    )
    if not isinstance(assignment_identity, dict):
        raise SuccessorOptionworthinessError("conditioning eligibility output identity is missing")
    if assignment_identity.get("sha256") != assignment_receipt.get("artifact_sha256"):
        raise SuccessorOptionworthinessError("conditioning eligibility assignment SHA does not match summary")
    if int(assignment_identity.get("row_count", -1)) != int(assignment_receipt.get("row_count", -2)):
        raise SuccessorOptionworthinessError("conditioning eligibility assignment row count drifted")

    normalized_dir = root / "normalized"
    paths = tuple(sorted(normalized_dir.glob("*.parquet")))
    if len(paths) != ACCEPTED_GROUP_COUNT:
        raise SuccessorOptionworthinessError(
            f"conditioning normalized artifact count drifted: {len(paths)} != {ACCEPTED_GROUP_COUNT}"
        )
    workers = min(SHA_WORKERS_MAX, max(1, os.cpu_count() or 1), len(paths))
    validated: list[dict[str, object]] = []
    started = time.monotonic()
    last_console = started
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_validate_normalized_one, path): path for path in paths}
        for future in as_completed(futures):
            validated.append(future.result())
            completed = len(validated)
            now = time.monotonic()
            if progress_callback is not None:
                progress_callback(completed, len(paths))
            if completed == len(paths) or now - last_console >= CONSOLE_HEARTBEAT_SECONDS:
                elapsed = max(now - started, 1e-9)
                print(
                    "successor option-worthiness input validation "
                    f"{completed}/{len(paths)} ({completed/len(paths):.1%}) "
                    f"rate={completed * 3600.0 / elapsed:.1f} artifacts/hour",
                    flush=True,
                )
                last_console = now
    validated.sort(key=lambda item: str(item["token"]))
    if sum(int(item["row_count"]) for item in validated) != ACCEPTED_STANDALONE_RECORD_COUNT:
        raise SuccessorOptionworthinessError("conditioning normalized receipt rows do not reconcile")
    normalized_identity = canonical_sha256(validated)
    if normalized_identity != canonical_sha256(validated):  # explicit deterministic guard
        raise SuccessorOptionworthinessError("normalized input identity is unstable")
    return {
        "conditioning_root": str(root),
        "conditioning_summary_sha256": _sha256_file(summary_path),
        "conditioning_analysis_fingerprint": str(summary.get("analysis_fingerprint") or ""),
        "conditioning_output_artifact_set_fingerprint": str(
            summary.get("output_artifact_set_fingerprint") or ""
        ),
        "normalized_part_count": len(validated),
        "normalized_record_count": ACCEPTED_STANDALONE_RECORD_COUNT,
        "normalized_input_identity": normalized_identity,
        "normalized": validated,
        "eligibility_assignments_sha256": str(assignment_receipt["artifact_sha256"]),
        "eligibility_assignments_rows": int(assignment_receipt["row_count"]),
    }


def _relation_metrics_sql(relation: str, *, subset: str, where: str) -> str:
    if subset not in ANALYSIS_SUBSETS:
        raise SuccessorOptionworthinessError(f"unsupported option-worthiness subset: {subset}")
    return f"""
        SELECT
            '{subset}' AS subset,
            policy_id,
            economic_family_id,
            native_timeframe,
            direction,
            count(*) AS comparable_opportunities,
            count(DISTINCT session_date) AS unique_sessions,
            count(DISTINCT instrument_key) AS unique_instruments,
            avg(CASE WHEN primary_net_return > 0 THEN 1.0 ELSE 0.0 END) AS primary_win_rate,
            avg(gross_return) AS mean_gross_return,
            median(gross_return) AS median_gross_return,
            quantile_cont(gross_return, 0.10) AS p10_gross_return,
            quantile_cont(gross_return, 0.90) AS p90_gross_return,
            avg(primary_net_return) AS mean_primary_net_return,
            median(primary_net_return) AS median_primary_net_return,
            avg(stress_net_return) AS mean_stress_net_return,
            median(stress_net_return) AS median_stress_net_return,
            count(mfe) AS mfe_observations,
            avg(mfe) AS mean_mfe,
            median(mfe) AS median_mfe,
            quantile_cont(mfe, 0.75) AS p75_mfe,
            quantile_cont(mfe, 0.90) AS p90_mfe,
            quantile_cont(mfe, 0.95) AS p95_mfe,
            count(mae) AS mae_observations,
            avg(mae) AS mean_mae,
            median(mae) AS median_mae,
            quantile_cont(mae, 0.10) AS p10_mae,
            quantile_cont(mae, 0.05) AS p05_mae,
            count(holding_minutes) AS holding_time_observations,
            avg(holding_minutes) AS mean_holding_minutes,
            median(holding_minutes) AS median_holding_minutes,
            quantile_cont(holding_minutes, 0.75) AS p75_holding_minutes,
            quantile_cont(holding_minutes, 0.90) AS p90_holding_minutes,
            avg(daily_h1_primary) AS mean_daily_h1_primary,
            median(daily_h1_primary) AS median_daily_h1_primary,
            avg(CASE WHEN daily_h1_primary IS NOT NULL THEN CASE WHEN daily_h1_primary > 0 THEN 1.0 ELSE 0.0 END END)
                AS daily_h1_positive_rate,
            avg(daily_h20_primary) AS mean_daily_h20_primary,
            median(daily_h20_primary) AS median_daily_h20_primary,
            avg(CASE WHEN daily_h20_primary IS NOT NULL THEN CASE WHEN daily_h20_primary > 0 THEN 1.0 ELSE 0.0 END END)
                AS daily_h20_positive_rate
        FROM {relation}
        WHERE {where}
        GROUP BY policy_id, economic_family_id, native_timeframe, direction
    """


def route_summary_sql() -> str:
    parts = (
        _relation_metrics_sql(
            "opportunities",
            subset="DEVELOPMENT_ALL_COMPARABLE",
            where="comparable",
        ),
        _relation_metrics_sql(
            "assigned_opportunities",
            subset="WALK_FORWARD_TEST_COMPARABLE",
            where="comparable",
        ),
        _relation_metrics_sql(
            "assigned_opportunities",
            subset="WALK_FORWARD_SELECTED_COMPARABLE",
            where="comparable AND research_eligible",
        ),
    )
    return " UNION ALL ".join(f"SELECT * FROM ({part})" for part in parts) + " ORDER BY policy_id, direction, subset"


def threshold_curve_sql() -> str:
    threshold_values = ", ".join(f"({value:.8f})" for value in MOVE_THRESHOLDS)
    relations = (
        ("DEVELOPMENT_ALL_COMPARABLE", "opportunities", "comparable"),
        ("WALK_FORWARD_TEST_COMPARABLE", "assigned_opportunities", "comparable"),
        (
            "WALK_FORWARD_SELECTED_COMPARABLE",
            "assigned_opportunities",
            "comparable AND research_eligible",
        ),
    )
    parts: list[str] = []
    for subset, relation, where in relations:
        parts.append(
            f"""
            SELECT
                '{subset}' AS subset,
                policy_id,
                economic_family_id,
                native_timeframe,
                direction,
                threshold AS move_threshold,
                count(mfe) AS mfe_observations,
                avg(CASE WHEN mfe IS NOT NULL THEN CASE WHEN mfe >= threshold THEN 1.0 ELSE 0.0 END END)
                    AS favorable_excursion_hit_rate,
                count(mae) AS mae_observations,
                avg(CASE WHEN mae IS NOT NULL THEN CASE WHEN mae <= -threshold THEN 1.0 ELSE 0.0 END END)
                    AS adverse_excursion_breach_rate
            FROM {relation}, (VALUES {threshold_values}) thresholds(threshold)
            WHERE {where}
            GROUP BY policy_id, economic_family_id, native_timeframe, direction, threshold
            """
        )
    return " UNION ALL ".join(f"SELECT * FROM ({part})" for part in parts) + " ORDER BY policy_id, direction, subset, move_threshold"


def selected_fold_summary_sql() -> str:
    threshold_columns = ",\n".join(
        (
            f"avg(CASE WHEN mfe IS NOT NULL THEN CASE WHEN mfe >= {threshold:.8f} THEN 1.0 ELSE 0.0 END END) "
            f"AS p_mfe_ge_{int(threshold * 100)}pct"
        )
        for threshold in MOVE_THRESHOLDS
    )
    return f"""
        SELECT
            fold_id,
            policy_id,
            economic_family_id,
            native_timeframe,
            direction,
            count(*) AS selected_comparable,
            count(DISTINCT session_date) AS unique_sessions,
            count(DISTINCT instrument_key) AS unique_instruments,
            avg(primary_net_return) AS mean_primary_net_return,
            avg(stress_net_return) AS mean_stress_net_return,
            avg(CASE WHEN primary_net_return > 0 THEN 1.0 ELSE 0.0 END) AS primary_win_rate,
            avg(mfe) AS mean_mfe,
            median(mfe) AS median_mfe,
            avg(mae) AS mean_mae,
            median(mae) AS median_mae,
            avg(holding_minutes) AS mean_holding_minutes,
            median(holding_minutes) AS median_holding_minutes,
            {threshold_columns}
        FROM assigned_opportunities
        WHERE comparable AND research_eligible
        GROUP BY fold_id, policy_id, economic_family_id, native_timeframe, direction
        ORDER BY fold_id, policy_id, direction
    """


def route_stability_sql() -> str:
    return """
        WITH per_fold AS (
            SELECT * FROM selected_fold_summary
        ), totals AS (
            SELECT policy_id, direction, sum(selected_comparable) AS total_selected
            FROM per_fold GROUP BY policy_id, direction
        )
        SELECT
            f.policy_id,
            f.economic_family_id,
            f.native_timeframe,
            f.direction,
            count(*) AS active_folds,
            count(*) FILTER (WHERE f.mean_primary_net_return > 0) AS positive_primary_folds,
            count(*) FILTER (WHERE f.mean_primary_net_return < 0) AS negative_primary_folds,
            count(*) FILTER (WHERE f.mean_primary_net_return = 0) AS flat_primary_folds,
            sum(f.selected_comparable) AS selected_comparable,
            max(f.selected_comparable) * 1.0 / nullif(t.total_selected, 0) AS largest_fold_share,
            avg(f.mean_primary_net_return) AS unweighted_mean_fold_primary_return,
            avg(f.mean_stress_net_return) AS unweighted_mean_fold_stress_return
        FROM per_fold f
        JOIN totals t USING (policy_id, direction)
        GROUP BY f.policy_id, f.economic_family_id, f.native_timeframe, f.direction, t.total_selected
        ORDER BY f.policy_id, f.direction
    """


def strategy_inventory_sql() -> str:
    return """
        WITH standalone AS (
            SELECT policy_id, economic_family_id, native_timeframe,
                   count(*) AS standalone_records,
                   count(*) FILTER (WHERE comparable) AS standalone_comparable
            FROM opportunities GROUP BY policy_id, economic_family_id, native_timeframe
        ), test AS (
            SELECT policy_id,
                   count(*) AS walk_forward_test_records,
                   count(*) FILTER (WHERE comparable) AS walk_forward_test_comparable,
                   count(*) FILTER (WHERE research_eligible) AS selected_records,
                   count(*) FILTER (WHERE research_eligible AND comparable) AS selected_comparable
            FROM assigned_opportunities GROUP BY policy_id
        )
        SELECT s.*, coalesce(t.walk_forward_test_records, 0) AS walk_forward_test_records,
               coalesce(t.walk_forward_test_comparable, 0) AS walk_forward_test_comparable,
               coalesce(t.selected_records, 0) AS selected_records,
               coalesce(t.selected_comparable, 0) AS selected_comparable,
               CASE WHEN s.standalone_records > 0 THEN 'IMPLEMENTED_AND_STANDALONE_REPLAYED'
                    ELSE 'IMPLEMENTED_ZERO_OBSERVED_RECORDS' END AS implementation_status,
               'RESEARCH_ONLY_NOT_VALIDATED' AS authority_status
        FROM standalone s LEFT JOIN test t USING (policy_id)
        ORDER BY s.policy_id
    """


def _validate_unique_join_keys(conn: duckdb.DuckDBPyConnection) -> None:
    key = "policy_id, native_timeframe, instrument_key, session_date, direction"
    opportunity_duplicates = int(
        conn.execute(
            f"SELECT count(*) FROM (SELECT {key}, count(*) c FROM opportunities GROUP BY {key} HAVING c > 1)"
        ).fetchone()[0]
    )
    if opportunity_duplicates:
        raise SuccessorOptionworthinessError(
            "normalized opportunities are not unique on the conditioning assignment join key; "
            "a persisted opportunity id is required before option-worthiness selection joins"
        )
    assignment_duplicates = int(
        conn.execute(
            f"SELECT count(*) FROM (SELECT {key}, count(*) c FROM eligibility_assignments GROUP BY {key} HAVING c > 1)"
        ).fetchone()[0]
    )
    if assignment_duplicates:
        raise SuccessorOptionworthinessError("eligibility assignments are not unique on the conditioning join key")


def _install_assigned_view(conn: duckdb.DuckDBPyConnection) -> None:
    _validate_unique_join_keys(conn)
    conn.execute(
        """
        CREATE OR REPLACE TEMP VIEW assigned_opportunities AS
        SELECT o.*, a.fold_id, a.fallback_level, a.selector_score, a.research_eligible
        FROM opportunities o
        JOIN eligibility_assignments a
          ON a.policy_id = o.policy_id
         AND a.native_timeframe = o.native_timeframe
         AND a.instrument_key = o.instrument_key
         AND a.session_date = o.session_date
         AND a.direction = o.direction
        """
    )
    assignment_count = int(conn.execute("SELECT count(*) FROM eligibility_assignments").fetchone()[0])
    joined_count = int(conn.execute("SELECT count(*) FROM assigned_opportunities").fetchone()[0])
    if joined_count != assignment_count:
        raise SuccessorOptionworthinessError(
            f"conditioning opportunity/assignment join did not reconcile: {joined_count} != {assignment_count}"
        )
    mismatch = int(
        conn.execute(
            """
            SELECT count(*) FROM assigned_opportunities
            WHERE comparable IS DISTINCT FROM (
                SELECT a.comparable FROM eligibility_assignments a
                WHERE a.policy_id=assigned_opportunities.policy_id
                  AND a.native_timeframe=assigned_opportunities.native_timeframe
                  AND a.instrument_key=assigned_opportunities.instrument_key
                  AND a.session_date=assigned_opportunities.session_date
                  AND a.direction=assigned_opportunities.direction
            )
            """
        ).fetchone()[0]
    )
    if mismatch:
        raise SuccessorOptionworthinessError("conditioning assignment comparability drifted from normalized opportunities")


def _write_progress(
    path: Path,
    *,
    state: str,
    phase: str,
    detail: str,
    started: float,
) -> None:
    _write_json(
        path,
        {
            "contract": SUCCESSOR_OPTIONWORTHINESS_ANALYSIS_CONTRACT,
            "optionworthiness_fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
            "state": state,
            "phase": phase,
            "detail": detail,
            "elapsed_seconds": round(max(0.0, time.monotonic() - started), 3),
            "updated_at_utc": datetime.now(UTC).isoformat(),
            "authority": "NON_AUTHORITATIVE_OPERATIONAL",
        },
    )


def _artifact_identity(conn: duckdb.DuckDBPyConnection, name: str, path: Path) -> dict[str, object]:
    return {
        "name": name,
        "sha256": _sha256_file(path),
        "row_count": int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(path)}')").fetchone()[0]),
    }


def run_successor_optionworthiness_analysis(project_root: Path) -> dict[str, object]:
    project = Path(project_root).resolve()
    output_root = optionworthiness_root(project)
    output_root.mkdir(parents=True, exist_ok=True)
    progress_path = output_root / "progress.json"
    started = time.monotonic()
    _write_json(output_root / "optionworthiness_contract.json", successor_optionworthiness_manifest())
    _write_progress(
        progress_path,
        state="RUNNING",
        phase="VALIDATE_INPUTS",
        detail="validating accepted conditioning artifacts and hashes",
        started=started,
    )
    print(
        "successor option-worthiness authority: retained DEVELOPMENT diagnostics only; "
        "no raw market reread, master/future/provider/broker/PAPER/LIVE/promotion/confluence/option authority",
        flush=True,
    )
    input_binding = validate_conditioning_inputs(project)
    conditioning = conditioning_root(project)
    normalized_glob = conditioning / "normalized" / "*.parquet"
    assignment_path = conditioning / "eligibility_assignments.parquet"

    _write_progress(
        progress_path,
        state="RUNNING",
        phase="AGGREGATE",
        detail="building descriptive move/excursion/holding diagnostics",
        started=started,
    )
    conn = duckdb.connect()
    try:
        conn.execute(f"PRAGMA threads={max(1, min(8, os.cpu_count() or 1))}")
        conn.execute("PRAGMA preserve_insertion_order=false")
        conn.execute(
            f"CREATE OR REPLACE TEMP VIEW opportunities AS "
            f"SELECT * FROM read_parquet('{_sql_path(normalized_glob)}', union_by_name=true)"
        )
        count = int(conn.execute("SELECT count(*) FROM opportunities").fetchone()[0])
        if count != ACCEPTED_STANDALONE_RECORD_COUNT:
            raise SuccessorOptionworthinessError(
                f"normalized opportunities drifted: {count} != {ACCEPTED_STANDALONE_RECORD_COUNT}"
            )
        conn.execute(
            f"CREATE OR REPLACE TEMP VIEW eligibility_assignments AS "
            f"SELECT * FROM read_parquet('{_sql_path(assignment_path)}')"
        )
        _install_assigned_view(conn)

        observed_policy_ids = {
            str(row[0]) for row in conn.execute("SELECT DISTINCT policy_id FROM opportunities").fetchall()
        }
        frozen_routes = successor_policy_routes()
        frozen_policy_ids = {route.policy_id for route in frozen_routes}
        if observed_policy_ids != frozen_policy_ids:
            missing = sorted(frozen_policy_ids - observed_policy_ids)
            extra = sorted(observed_policy_ids - frozen_policy_ids)
            raise SuccessorOptionworthinessError(
                f"option-worthiness route inventory drifted; missing={missing} extra={extra}"
            )

        outputs: dict[str, Path] = {
            "route_summary": output_root / "route_summary.parquet",
            "move_threshold_curve": output_root / "move_threshold_curve.parquet",
            "selected_fold_summary": output_root / "selected_fold_summary.parquet",
            "route_stability": output_root / "route_stability.parquet",
            "strategy_inventory": output_root / "strategy_inventory.parquet",
        }
        _copy_query_atomic(conn, route_summary_sql(), outputs["route_summary"])
        _copy_query_atomic(conn, threshold_curve_sql(), outputs["move_threshold_curve"])
        _copy_query_atomic(conn, selected_fold_summary_sql(), outputs["selected_fold_summary"])
        conn.execute(
            f"CREATE OR REPLACE TEMP VIEW selected_fold_summary AS "
            f"SELECT * FROM read_parquet('{_sql_path(outputs['selected_fold_summary'])}')"
        )
        _copy_query_atomic(conn, route_stability_sql(), outputs["route_stability"])
        _copy_query_atomic(conn, strategy_inventory_sql(), outputs["strategy_inventory"])

        route_count = int(conn.execute("SELECT count(*) FROM read_parquet(?)", [str(outputs["strategy_inventory"])]).fetchone()[0])
        if route_count != 28:
            raise SuccessorOptionworthinessError(f"strategy inventory expected 28 routes, got {route_count}")
        family_count = int(
            conn.execute(
                "SELECT count(DISTINCT economic_family_id) FROM read_parquet(?)",
                [str(outputs["strategy_inventory"])],
            ).fetchone()[0]
        )
        if family_count != 21:
            raise SuccessorOptionworthinessError(f"strategy inventory expected 21 economic families, got {family_count}")

        output_identity = [
            _artifact_identity(conn, name, path) for name, path in sorted(outputs.items())
        ]
        output_artifact_set_fingerprint = canonical_sha256(output_identity)

        capability = successor_optionworthiness_manifest()["explicitly_unavailable_from_retained_artifacts"]
        _write_json(
            output_root / "capability_manifest.json",
            {
                "contract": SUCCESSOR_OPTIONWORTHINESS_CONTRACT,
                "fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
                "supported_metrics": successor_optionworthiness_manifest()["supported_metrics"],
                "unavailable": capability,
                "raw_market_data_reread": False,
                "historical_option_data_read": False,
            },
        )

        all_count = int(
            conn.execute("SELECT count(*) FROM opportunities WHERE comparable").fetchone()[0]
        )
        test_count = int(
            conn.execute("SELECT count(*) FROM assigned_opportunities WHERE comparable").fetchone()[0]
        )
        selected_count = int(
            conn.execute(
                "SELECT count(*) FROM assigned_opportunities WHERE comparable AND research_eligible"
            ).fetchone()[0]
        )
        report: dict[str, object] = {
            "status": "COMPLETE_OPTIONWORTHINESS_DIAGNOSTICS_ONLY",
            "analysis_contract": SUCCESSOR_OPTIONWORTHINESS_ANALYSIS_CONTRACT,
            "optionworthiness_contract": SUCCESSOR_OPTIONWORTHINESS_CONTRACT,
            "optionworthiness_fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
            "input_binding": input_binding,
            "scope_counts": {
                "development_all_comparable": all_count,
                "walk_forward_test_comparable": test_count,
                "walk_forward_selected_comparable": selected_count,
            },
            "strategy_inventory": {
                "policy_routes": route_count,
                "economic_families": family_count,
                "implementation_status_definition": (
                    "ROUTE_REGISTERED_IN_FROZEN_SUCCESSOR_CONTRACT_AND_OBSERVED_IN_ACCEPTED_STANDALONE"
                ),
            },
            "outputs": output_identity,
            "output_artifact_set_fingerprint": output_artifact_set_fingerprint,
            "move_thresholds_fraction": list(MOVE_THRESHOLDS),
            "no_composite_optionworthiness_score": True,
            "raw_market_data_reread": False,
            "historical_option_data_read": False,
            "time_to_threshold_claimed": False,
            "atr_threshold_frequency_claimed": False,
            "historical_option_pnl_claimed": False,
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
        report["analysis_fingerprint"] = canonical_sha256(
            {
                "optionworthiness_fingerprint": SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
                "conditioning_analysis_fingerprint": input_binding[
                    "conditioning_analysis_fingerprint"
                ],
                "normalized_input_identity": input_binding["normalized_input_identity"],
                "eligibility_assignments_sha256": input_binding[
                    "eligibility_assignments_sha256"
                ],
                "output_artifact_set_fingerprint": output_artifact_set_fingerprint,
            }
        )
        _write_json(output_root / "analysis_summary.json", report)
        _write_progress(
            progress_path,
            state="COMPLETE",
            phase="COMPLETE",
            detail="retained-artifact option-worthiness diagnostics complete",
            started=started,
        )
        return report
    except Exception:
        _write_progress(
            progress_path,
            state="FAILED",
            phase="FAILED",
            detail="option-worthiness analysis failed closed; inspect exception",
            started=started,
        )
        raise
    finally:
        conn.close()
