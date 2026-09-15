from __future__ import annotations

import bisect
import hashlib
import json
import math
import os
import time
from collections import defaultdict
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable, Sequence

import duckdb
import exchange_calendars as xcals
import numpy as np
import pandas as pd

from packages.backtesting.successor_runner_contract import canonical_sha256, successor_policy_routes
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.successor_execution_profile import (
    SuccessorResearchExecutionProfile,
    resolve_successor_research_execution_profile,
)
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_GROUP_COUNT,
    ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
    ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
    ACCEPTED_STANDALONE_RECORD_COUNT,
    ACCEPTED_STANDALONE_RUN_FINGERPRINT,
    AUTHORITY,
    CONDITION_DIMENSIONS,
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    MIN_CELL_OPPORTUNITIES,
    MIN_CELL_UNIQUE_INSTRUMENTS,
    MIN_CELL_UNIQUE_SESSIONS,
    PRIMARY_CONDITION_INTERACTIONS,
    SELECTOR_FALLBACK_HIERARCHY,
    SELECTOR_LCB_QUANTILE,
    SESSION_CLUSTER_BOOTSTRAP_DRAWS,
    SUCCESSOR_CONDITIONING_CONTRACT,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
    WALK_FORWARD_EMBARGO_SESSIONS,
    WALK_FORWARD_STEP_SESSIONS,
    WALK_FORWARD_TEST_SESSIONS,
    ROLLING_TRAIN_SESSIONS,
    successor_conditioning_manifest,
)


SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT = (
    "atlas-successor-conditioning-analysis-v1-immutable-standalone-postprocess"
)
CONSOLE_HEARTBEAT_SECONDS = 300.0
MACHINE_HEARTBEAT_SECONDS = 30.0


class SuccessorConditioningError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StandaloneArtifact:
    token: str
    kind: str
    sha256: str
    record_count: int
    source_path: Path


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_id: int
    train_start: date
    train_end: date
    embargo_session: date
    test_start: date
    test_end: date


NORMALIZED_SCHEMA: tuple[tuple[str, str], ...] = (
    ("policy_id", "VARCHAR"),
    ("economic_family_id", "VARCHAR"),
    ("native_timeframe", "VARCHAR"),
    ("instrument_key", "VARCHAR"),
    ("ticker", "VARCHAR"),
    ("session_date", "DATE"),
    ("calendar_year", "INTEGER"),
    ("direction", "VARCHAR"),
    ("eligible_opportunity", "BOOLEAN"),
    ("status", "VARCHAR"),
    ("comparable", "BOOLEAN"),
    ("gross_return", "DOUBLE"),
    ("net_return_0", "DOUBLE"),
    ("net_return_10", "DOUBLE"),
    ("net_return_25", "DOUBLE"),
    ("net_return_50", "DOUBLE"),
    ("net_return_100", "DOUBLE"),
    ("primary_net_return", "DOUBLE"),
    ("stress_net_return", "DOUBLE"),
    ("daily_h1_primary", "DOUBLE"),
    ("daily_h20_primary", "DOUBLE"),
    ("net_r_primary", "DOUBLE"),
    ("mfe", "DOUBLE"),
    ("mae", "DOUBLE"),
    ("entry_time_utc", "TIMESTAMPTZ"),
    ("exit_time_utc", "TIMESTAMPTZ"),
    ("holding_minutes", "INTEGER"),
    ("market_direction_alignment", "VARCHAR"),
    ("market_volatility_state", "VARCHAR"),
    ("relative_strength_20_raw", "DOUBLE"),
    ("relative_strength_63_raw", "DOUBLE"),
    ("higher_timeframe_ticker_trend", "VARCHAR"),
    ("trend_extension_raw", "DOUBLE"),
    ("opening_participation_raw", "DOUBLE"),
    ("premarket_participation_raw", "DOUBLE"),
    ("prior_dollar_volume_raw", "DOUBLE"),
    ("overnight_gap_raw", "DOUBLE"),
    ("price_band", "VARCHAR"),
    ("signal_time_raw", "VARCHAR"),
    ("realized_volatility_raw", "DOUBLE"),
    ("execution_liquidity_quality", "VARCHAR"),
    ("context_provenance", "VARCHAR"),
    ("legacy_prior_close_bucket", "VARCHAR"),
    ("relative_strength_20_bucket", "VARCHAR"),
    ("relative_strength_63_bucket", "VARCHAR"),
    ("trend_extension_bucket", "VARCHAR"),
    ("opening_participation_bucket", "VARCHAR"),
    ("premarket_participation_bucket", "VARCHAR"),
    ("liquidity_bucket", "VARCHAR"),
    ("overnight_gap_magnitude_bucket", "VARCHAR"),
    ("signal_time_bucket", "VARCHAR"),
    ("realized_volatility_bucket", "VARCHAR"),
    ("selector_key_1", "VARCHAR"),
    ("selector_key_2", "VARCHAR"),
    ("selector_key_3", "VARCHAR"),
    ("selector_key_4", "VARCHAR"),
    ("selector_key_5", "VARCHAR"),
)


def _stable_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
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
    row_group_size: int = 250_000,
) -> None:
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


def _artifact_receipt_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".receipt.json")


def _publish_artifact_receipt(
    path: Path,
    *,
    phase: str,
    row_count: int,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
        "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
        "phase": phase,
        "artifact_path": str(path.resolve()),
        "artifact_sha256": _sha256_file(path),
        "row_count": int(row_count),
        "created_at_utc": datetime.now(UTC).isoformat(),
    }
    if extra:
        payload.update(extra)
    payload["receipt_id"] = _stable_hash(payload)
    _write_json(_artifact_receipt_path(path), payload)
    return payload


def _reusable_artifact(
    path: Path,
    *,
    phase: str,
    expected_row_count: int | None = None,
    extra_required: dict[str, object] | None = None,
) -> dict[str, object] | None:
    receipt_path = _artifact_receipt_path(path)
    if not path.is_file() or not receipt_path.is_file():
        return None
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    expected_id = _stable_hash({key: value for key, value in receipt.items() if key != "receipt_id"})
    if receipt.get("receipt_id") != expected_id:
        return None
    if receipt.get("contract") != SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT:
        return None
    if receipt.get("conditioning_fingerprint") != SUCCESSOR_CONDITIONING_FINGERPRINT:
        return None
    if receipt.get("phase") != phase:
        return None
    if receipt.get("artifact_path") != str(path.resolve()):
        return None
    if expected_row_count is not None and int(receipt.get("row_count", -1)) != int(expected_row_count):
        return None
    if extra_required and any(receipt.get(key) != value for key, value in extra_required.items()):
        return None
    if receipt.get("artifact_sha256") != _sha256_file(path):
        return None
    return receipt


def _accepted_standalone_root(project_root: Path) -> Path:
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


def validate_accepted_standalone(project_root: Path) -> tuple[Path, dict[str, object], tuple[StandaloneArtifact, ...]]:
    root = _accepted_standalone_root(project_root)
    summary_path = root / "standalone_summary.json"
    if not summary_path.is_file():
        raise SuccessorConditioningError(f"accepted standalone summary is missing: {summary_path}")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if not isinstance(summary, dict):
        raise SuccessorConditioningError("standalone summary is not a JSON object")
    required = {
        "status": "COMPLETE_STANDALONE_ONLY",
        "run_contract_fingerprint": ACCEPTED_RUN_CONTRACT_FINGERPRINT,
        "input_manifest_fingerprint": ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
        "conditioning_opened": False,
        "confluence_opened": False,
        "corrupt_reuse_invalidated": 0,
    }
    for key, expected in required.items():
        if summary.get(key) != expected:
            raise SuccessorConditioningError(f"accepted standalone summary {key} drifted")
    parallel = summary.get("parallel_run")
    standalone = summary.get("standalone")
    authority = summary.get("authority")
    if not isinstance(parallel, dict) or not isinstance(standalone, dict) or not isinstance(authority, dict):
        raise SuccessorConditioningError("standalone summary structure drifted")
    if parallel.get("status") != "COMPLETE":
        raise SuccessorConditioningError("standalone parallel run is not COMPLETE")
    if parallel.get("scientific_contract_fingerprint") != ACCEPTED_RUN_CONTRACT_FINGERPRINT:
        raise SuccessorConditioningError("standalone scientific contract fingerprint drifted")
    if parallel.get("run_fingerprint") != ACCEPTED_STANDALONE_RUN_FINGERPRINT:
        raise SuccessorConditioningError("standalone run fingerprint drifted")
    if int(parallel.get("group_count", -1)) != ACCEPTED_GROUP_COUNT:
        raise SuccessorConditioningError("standalone group count drifted")
    if standalone.get("status") != "VALIDATED_STANDALONE_COMPLETE":
        raise SuccessorConditioningError("standalone artifact validation state drifted")
    if int(standalone.get("group_count", -1)) != ACCEPTED_GROUP_COUNT:
        raise SuccessorConditioningError("standalone artifact group count drifted")
    if int(standalone.get("record_count", -1)) != ACCEPTED_STANDALONE_RECORD_COUNT:
        raise SuccessorConditioningError("standalone record count drifted")
    if standalone.get("artifact_set_fingerprint") != ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT:
        raise SuccessorConditioningError("standalone artifact-set fingerprint drifted")
    for key, expected in AUTHORITY.items():
        if key in authority and authority.get(key) != expected:
            raise SuccessorConditioningError(f"standalone authority {key} is incompatible with conditioning")
    for key in (
        "consumed_master_rows_permitted",
        "future_blind_rows_permitted",
        "provider_calls_permitted",
        "broker_reads_permitted",
        "broker_writes_permitted",
    ):
        if int(authority.get(key, -1)) != 0:
            raise SuccessorConditioningError(f"standalone authority {key} is nonzero")
    for key in ("paper_authority", "live_authority", "promotion_authority"):
        if authority.get(key) is not False:
            raise SuccessorConditioningError(f"standalone authority {key} is not false")

    raw_artifacts = standalone.get("artifacts")
    if not isinstance(raw_artifacts, list) or len(raw_artifacts) != ACCEPTED_GROUP_COUNT:
        raise SuccessorConditioningError("standalone artifact inventory drifted")
    artifacts: list[StandaloneArtifact] = []
    total = 0
    seen: set[str] = set()
    for item in raw_artifacts:
        if not isinstance(item, dict):
            raise SuccessorConditioningError("standalone artifact inventory contains a non-object")
        token = str(item.get("token") or "")
        kind = str(item.get("kind") or "")
        sha = str(item.get("sha256") or "")
        count = int(item.get("record_count", -1))
        if not token or token in seen or kind not in {"daily", "minute"} or len(sha) != 64 or count < 0:
            raise SuccessorConditioningError(f"invalid standalone artifact inventory row: {token!r}")
        source = (root / "standalone" / f"{token}.jsonl").resolve()
        if source.parent != (root / "standalone").resolve() or not source.is_file():
            raise SuccessorConditioningError(f"standalone artifact is missing: {token}")
        artifacts.append(StandaloneArtifact(token, kind, sha, count, source))
        seen.add(token)
        total += count
    if total != ACCEPTED_STANDALONE_RECORD_COUNT:
        raise SuccessorConditioningError("standalone artifact row counts do not reconcile")
    return root, summary, tuple(sorted(artifacts, key=lambda item: item.token))


def _json(path: str) -> str:
    return f"json_extract_string(j, '{path}')"


def _try_double(path: str) -> str:
    return f"TRY_CAST({_json(path)} AS DOUBLE)"


def _try_bool(path: str) -> str:
    return f"TRY_CAST({_json(path)} AS BOOLEAN)"


def _rs_bucket(expr: str) -> str:
    return (
        f"CASE WHEN {expr} IS NULL THEN 'UNAVAILABLE' "
        f"WHEN {expr} <= -0.10 THEN 'LE_M10PCT' "
        f"WHEN {expr} < -0.03 THEN 'M10_TO_M3PCT' "
        f"WHEN {expr} < 0.03 THEN 'M3_TO_P3PCT' "
        f"WHEN {expr} < 0.10 THEN 'P3_TO_P10PCT' ELSE 'GE_P10PCT' END"
    )


def _extension_bucket(expr: str) -> str:
    return (
        f"CASE WHEN {expr} IS NULL THEN 'UNAVAILABLE' "
        f"WHEN {expr} <= -2.0 THEN 'LE_M2ATR' WHEN {expr} < -1.0 THEN 'M2_TO_M1ATR' "
        f"WHEN {expr} < 1.0 THEN 'M1_TO_P1ATR' WHEN {expr} < 2.0 THEN 'P1_TO_P2ATR' "
        "ELSE 'GE_P2ATR' END"
    )


def _participation_bucket(expr: str) -> str:
    return (
        f"CASE WHEN {expr} IS NULL THEN 'UNAVAILABLE' "
        f"WHEN {expr} < 1.0 THEN 'LT_1' WHEN {expr} < 1.5 THEN '1_TO_1_5' "
        f"WHEN {expr} < 2.0 THEN '1_5_TO_2' WHEN {expr} < 4.0 THEN '2_TO_4' "
        "ELSE 'GE_4' END"
    )


def _liquidity_bucket(expr: str) -> str:
    return (
        f"CASE WHEN {expr} IS NULL THEN 'UNAVAILABLE' "
        f"WHEN {expr} < 1000000 THEN 'LT_1M' WHEN {expr} < 10000000 THEN '1M_TO_10M' "
        f"WHEN {expr} < 50000000 THEN '10M_TO_50M' WHEN {expr} < 250000000 THEN '50M_TO_250M' "
        "ELSE 'GE_250M' END"
    )


def _gap_bucket(expr: str) -> str:
    return (
        f"CASE WHEN {expr} IS NULL THEN 'UNAVAILABLE' WHEN abs({expr}) < 0.02 THEN 'LT_2PCT' "
        f"WHEN abs({expr}) < 0.05 THEN '2_TO_5PCT' WHEN abs({expr}) < 0.10 THEN '5_TO_10PCT' "
        "ELSE 'GE_10PCT' END"
    )


def _rv_bucket(expr: str) -> str:
    return (
        f"CASE WHEN {expr} IS NULL THEN 'UNAVAILABLE' WHEN {expr} < 0.25 THEN 'LT_25PCT' "
        f"WHEN {expr} < 0.50 THEN '25_TO_50PCT' WHEN {expr} < 1.00 THEN '50_TO_100PCT' "
        "ELSE 'GE_100PCT' END"
    )


def _signal_time_bucket(expr: str, *, daily: bool) -> str:
    if daily:
        return "'DAILY_CLOSE'"
    return (
        f"CASE WHEN {expr} IS NULL OR {expr} IN ('', 'UNAVAILABLE') THEN 'UNAVAILABLE' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '09:31:00' AND TIME '09:44:59' THEN '0931_TO_0944' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '09:45:00' AND TIME '10:00:59' THEN '0945_TO_1000' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '10:01:00' AND TIME '10:30:59' THEN '1001_TO_1030' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '10:31:00' AND TIME '11:31:59' THEN '1031_TO_1131' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '11:32:00' AND TIME '13:00:59' THEN '1132_TO_1300' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '13:01:00' AND TIME '15:00:59' THEN '1301_TO_1500' "
        f"WHEN TRY_CAST({expr} AS TIME) BETWEEN TIME '15:01:00' AND TIME '16:00:00' THEN '1501_TO_CLOSE' "
        "ELSE 'UNAVAILABLE' END"
    )


def _selector_key_expr(columns: Sequence[str]) -> str:
    args = ", ".join(f"coalesce(CAST({column} AS VARCHAR), 'UNAVAILABLE')" for column in columns)
    return f"concat_ws('|', {args})"


def _empty_normalized_query() -> str:
    columns = ", ".join(f"CAST(NULL AS {kind}) AS {name}" for name, kind in NORMALIZED_SCHEMA)
    return f"SELECT {columns} WHERE FALSE"


def _daily_normalization_query(source: Path) -> str:
    source_sql = _sql_path(source)
    raw = "SELECT json AS j FROM read_json_objects('" + source_sql + "', format='newline_delimited')"
    rs20 = _try_double("/outcome/common_context/ticker_relative_strength_vs_spy_short_horizon")
    rs63 = _try_double("/outcome/common_context/ticker_relative_strength_vs_spy_medium_horizon")
    extension = _try_double("/outcome/common_context/atr_normalized_trend_maturity_extension")
    opening = _try_double("/outcome/common_context/opening_same_time_volume_participation")
    premarket = _try_double("/outcome/common_context/premarket_volume_participation")
    liquidity = _try_double("/outcome/common_context/prior_dollar_volume_liquidity")
    gap = _try_double("/outcome/common_context/overnight_gap")
    rv = _try_double("/outcome/common_context/realized_volatility")
    session = _json("/outcome/signal_session")
    eligible = f"coalesce({_try_bool('/signal/universe_eligible')}, false)"
    n0 = _try_double("/outcome/net_directional_returns_by_cost_bps/0/5")
    n10 = _try_double("/outcome/net_directional_returns_by_cost_bps/10/5")
    n25 = _try_double("/outcome/net_directional_returns_by_cost_bps/25/5")
    n50 = _try_double("/outcome/net_directional_returns_by_cost_bps/50/5")
    n100 = _try_double("/outcome/net_directional_returns_by_cost_bps/100/5")
    base = f"""
        SELECT
            {_json('/route/policy_id')} AS policy_id,
            {_json('/route/economic_family_id')} AS economic_family_id,
            coalesce({_json('/route/native_timeframe')}, '1d') AS native_timeframe,
            coalesce({_json('/outcome/instrument_id')}, {_json('/signal/instrument_id')}) AS instrument_key,
            coalesce({_json('/outcome/ticker')}, {_json('/signal/ticker')}) AS ticker,
            TRY_CAST({session} AS DATE) AS session_date,
            year(TRY_CAST({session} AS DATE)) AS calendar_year,
            coalesce({_json('/outcome/direction')}, {_json('/signal/direction')}) AS direction,
            {eligible} AS eligible_opportunity,
            {_json('/outcome/status')} AS status,
            ({eligible} AND {n10} IS NOT NULL) AS comparable,
            {_try_double('/outcome/gross_directional_returns/5')} AS gross_return,
            {n0} AS net_return_0,
            {n10} AS net_return_10,
            {n25} AS net_return_25,
            {n50} AS net_return_50,
            {n100} AS net_return_100,
            {n10} AS primary_net_return,
            {n25} AS stress_net_return,
            {_try_double('/outcome/net_directional_returns_by_cost_bps/10/1')} AS daily_h1_primary,
            {_try_double('/outcome/net_directional_returns_by_cost_bps/10/20')} AS daily_h20_primary,
            CAST(NULL AS DOUBLE) AS net_r_primary,
            {_try_double('/outcome/maximum_favorable_excursion_20')} AS mfe,
            {_try_double('/outcome/maximum_adverse_excursion_20')} AS mae,
            CAST(NULL AS TIMESTAMPTZ) AS entry_time_utc,
            CAST(NULL AS TIMESTAMPTZ) AS exit_time_utc,
            CAST(NULL AS INTEGER) AS holding_minutes,
            coalesce({_json('/outcome/common_context/market_direction_alignment')}, 'UNAVAILABLE') AS market_direction_alignment,
            coalesce({_json('/outcome/common_context/market_volatility_state')}, 'UNAVAILABLE') AS market_volatility_state,
            {rs20} AS relative_strength_20_raw,
            {rs63} AS relative_strength_63_raw,
            coalesce({_json('/outcome/common_context/higher_timeframe_ticker_trend')}, 'UNAVAILABLE') AS higher_timeframe_ticker_trend,
            {extension} AS trend_extension_raw,
            {opening} AS opening_participation_raw,
            {premarket} AS premarket_participation_raw,
            {liquidity} AS prior_dollar_volume_raw,
            {gap} AS overnight_gap_raw,
            coalesce({_json('/outcome/common_context/price_band')}, 'UNAVAILABLE') AS price_band,
            coalesce({_json('/outcome/common_context/signal_time')}, 'DAILY_CLOSE') AS signal_time_raw,
            {rv} AS realized_volatility_raw,
            coalesce({_json('/outcome/common_context/execution_liquidity_quality')}, 'UNAVAILABLE') AS execution_liquidity_quality,
            'SUCCESSOR_SHARED' AS context_provenance,
            CAST(NULL AS VARCHAR) AS legacy_prior_close_bucket,
            {_rs_bucket(rs20)} AS relative_strength_20_bucket,
            {_rs_bucket(rs63)} AS relative_strength_63_bucket,
            {_extension_bucket(extension)} AS trend_extension_bucket,
            {_participation_bucket(opening)} AS opening_participation_bucket,
            {_participation_bucket(premarket)} AS premarket_participation_bucket,
            {_liquidity_bucket(liquidity)} AS liquidity_bucket,
            {_gap_bucket(gap)} AS overnight_gap_magnitude_bucket,
            {_signal_time_bucket(_json('/outcome/common_context/signal_time'), daily=True)} AS signal_time_bucket,
            {_rv_bucket(rv)} AS realized_volatility_bucket
        FROM ({raw})
    """
    selector_columns = [
        _selector_key_expr(level) + f" AS selector_key_{index}"
        for index, level in enumerate(SELECTOR_FALLBACK_HIERARCHY, start=1)
    ]
    return f"SELECT base.*, {', '.join(selector_columns)} FROM ({base}) base"


def _minute_normalization_query(source: Path) -> str:
    source_sql = _sql_path(source)
    raw = "SELECT json AS j FROM read_json_objects('" + source_sql + "', format='newline_delimited')"
    status = _json("/outcome/status")
    explicit_comparable = _try_bool("/outcome/comparable")
    entry = _try_double("/outcome/entry_price")
    stop = _try_double("/outcome/stop_price")
    risk_pct = f"CASE WHEN {entry} > 0 AND {stop} > 0 THEN abs({entry} - {stop}) / {entry} ELSE NULL END"
    n0 = _try_double("/outcome/net_directional_returns_by_cost_bps/0")
    n10 = _try_double("/outcome/net_directional_returns_by_cost_bps/10")
    n25 = _try_double("/outcome/net_directional_returns_by_cost_bps/25")
    n50 = _try_double("/outcome/net_directional_returns_by_cost_bps/50")
    n100 = _try_double("/outcome/net_directional_returns_by_cost_bps/100")
    new_rs20 = _try_double("/context/ticker_relative_strength_vs_spy_short_horizon")
    new_rs63 = _try_double("/context/ticker_relative_strength_vs_spy_medium_horizon")
    extension = _try_double("/context/atr_normalized_trend_maturity_extension")
    opening = _try_double("/context/opening_same_time_volume_participation")
    premarket = _try_double("/context/premarket_volume_participation")
    liquidity = _try_double("/context/prior_dollar_volume_liquidity")
    gap = _try_double("/context/overnight_gap")
    rv = _try_double("/context/realized_volatility")
    legacy = f"coalesce({_json('/context/contract')} LIKE 'atlas-b35-%', false)"
    legacy_trend = _json("/context/prior_trend_20_50")
    normalized_trend = (
        f"CASE WHEN {legacy} THEN CASE {legacy_trend} WHEN 'UP' THEN 'BULL' WHEN 'DOWN' THEN 'BEAR' "
        f"WHEN 'MIXED' THEN 'MIXED' ELSE 'UNAVAILABLE' END "
        f"ELSE coalesce({_json('/context/higher_timeframe_ticker_trend')}, 'UNAVAILABLE') END"
    )
    legacy_liquidity = _json("/context/median_dollar_volume_20")
    legacy_gap = _json("/context/absolute_gap_pct")
    legacy_rv = _json("/context/realized_volatility_20")
    legacy_pm = _json("/context/premarket_relvol_20")
    legacy_signal_time = _json("/context/signal_time_et")
    signal_time = _json("/context/signal_time")
    comparable = f"coalesce({explicit_comparable}, {status} = 'EXITED', false)"
    session = f"coalesce({_json('/outcome/session_date')}, {_json('/signal/session_date')})"
    entry_time = f"TRY_CAST({_json('/outcome/entry_bar_timestamp_utc')} AS TIMESTAMPTZ)"
    exit_time = f"TRY_CAST({_json('/outcome/exit_bar_timestamp_utc')} AS TIMESTAMPTZ)"
    base = f"""
        SELECT
            {_json('/route/policy_id')} AS policy_id,
            {_json('/route/economic_family_id')} AS economic_family_id,
            coalesce({_json('/route/native_timeframe')}, '1m') AS native_timeframe,
            coalesce({_json('/outcome/symbol')}, {_json('/signal/symbol')}) AS instrument_key,
            coalesce({_json('/outcome/symbol')}, {_json('/signal/symbol')}) AS ticker,
            TRY_CAST({session} AS DATE) AS session_date,
            year(TRY_CAST({session} AS DATE)) AS calendar_year,
            coalesce({_json('/outcome/direction')}, {_json('/signal/direction')}) AS direction,
            true AS eligible_opportunity,
            {status} AS status,
            {comparable} AS comparable,
            {_try_double('/outcome/gross_directional_return')} AS gross_return,
            {n0} AS net_return_0,
            {n10} AS net_return_10,
            {n25} AS net_return_25,
            {n50} AS net_return_50,
            {n100} AS net_return_100,
            {n50} AS primary_net_return,
            {n100} AS stress_net_return,
            CAST(NULL AS DOUBLE) AS daily_h1_primary,
            CAST(NULL AS DOUBLE) AS daily_h20_primary,
            CASE WHEN {comparable} AND {risk_pct} > 0 THEN {n50} / {risk_pct} ELSE NULL END AS net_r_primary,
            {_try_double('/outcome/maximum_favorable_excursion')} AS mfe,
            {_try_double('/outcome/maximum_adverse_excursion')} AS mae,
            {entry_time} AS entry_time_utc,
            {exit_time} AS exit_time_utc,
            CASE WHEN {entry_time} IS NOT NULL AND {exit_time} IS NOT NULL
                 THEN date_diff('minute', {entry_time}, {exit_time}) ELSE NULL END AS holding_minutes,
            CASE WHEN {legacy} THEN coalesce({_json('/context/prior_market_regime')}, 'UNAVAILABLE')
                 ELSE coalesce({_json('/context/market_direction_alignment')}, 'UNAVAILABLE') END AS market_direction_alignment,
            CASE WHEN {legacy} THEN 'UNAVAILABLE'
                 ELSE coalesce({_json('/context/market_volatility_state')}, 'UNAVAILABLE') END AS market_volatility_state,
            CASE WHEN {legacy} THEN NULL ELSE {new_rs20} END AS relative_strength_20_raw,
            CASE WHEN {legacy} THEN NULL ELSE {new_rs63} END AS relative_strength_63_raw,
            {normalized_trend} AS higher_timeframe_ticker_trend,
            CASE WHEN {legacy} THEN NULL ELSE {extension} END AS trend_extension_raw,
            CASE WHEN {legacy} THEN NULL ELSE {opening} END AS opening_participation_raw,
            CASE WHEN {legacy} THEN NULL ELSE {premarket} END AS premarket_participation_raw,
            CASE WHEN {legacy} THEN NULL ELSE {liquidity} END AS prior_dollar_volume_raw,
            CASE WHEN {legacy} THEN NULL ELSE {gap} END AS overnight_gap_raw,
            CASE WHEN {legacy} THEN 'UNAVAILABLE' ELSE coalesce({_json('/context/price_band')}, 'UNAVAILABLE') END AS price_band,
            CASE WHEN {legacy} THEN coalesce({legacy_signal_time}, 'UNAVAILABLE') ELSE coalesce({signal_time}, 'UNAVAILABLE') END AS signal_time_raw,
            CASE WHEN {legacy} THEN NULL ELSE {rv} END AS realized_volatility_raw,
            CASE WHEN {legacy} THEN 'UNAVAILABLE' ELSE coalesce({_json('/context/execution_liquidity_quality')}, 'UNAVAILABLE') END AS execution_liquidity_quality,
            CASE WHEN {legacy} THEN 'B35_LEGACY_BUCKETED' ELSE 'SUCCESSOR_SHARED' END AS context_provenance,
            CASE WHEN {legacy} THEN coalesce({_json('/context/prior_close_price')}, 'UNAVAILABLE') ELSE NULL END AS legacy_prior_close_bucket,
            CASE WHEN {legacy} THEN 'UNAVAILABLE' ELSE {_rs_bucket(new_rs20)} END AS relative_strength_20_bucket,
            CASE WHEN {legacy} THEN 'UNAVAILABLE' ELSE {_rs_bucket(new_rs63)} END AS relative_strength_63_bucket,
            CASE WHEN {legacy} THEN 'UNAVAILABLE' ELSE {_extension_bucket(extension)} END AS trend_extension_bucket,
            CASE WHEN {legacy} THEN 'UNAVAILABLE' ELSE {_participation_bucket(opening)} END AS opening_participation_bucket,
            CASE WHEN {legacy} THEN coalesce({legacy_pm}, 'UNAVAILABLE') ELSE {_participation_bucket(premarket)} END AS premarket_participation_bucket,
            CASE WHEN {legacy} THEN coalesce({legacy_liquidity}, 'UNAVAILABLE') ELSE {_liquidity_bucket(liquidity)} END AS liquidity_bucket,
            CASE WHEN {legacy} THEN coalesce({legacy_gap}, 'UNAVAILABLE') ELSE {_gap_bucket(gap)} END AS overnight_gap_magnitude_bucket,
            CASE WHEN {legacy} THEN coalesce({legacy_signal_time}, 'UNAVAILABLE') ELSE {_signal_time_bucket(signal_time, daily=False)} END AS signal_time_bucket,
            CASE WHEN {legacy} THEN coalesce({legacy_rv}, 'UNAVAILABLE') ELSE {_rv_bucket(rv)} END AS realized_volatility_bucket
        FROM ({raw})
    """
    selector_columns = [
        _selector_key_expr(level) + f" AS selector_key_{index}"
        for index, level in enumerate(SELECTOR_FALLBACK_HIERARCHY, start=1)
    ]
    return f"SELECT base.*, {', '.join(selector_columns)} FROM ({base}) base"


def normalization_query(source: Path, kind: str, expected_count: int) -> str:
    if expected_count == 0:
        return _empty_normalized_query()
    if kind == "daily":
        return _daily_normalization_query(source)
    if kind == "minute":
        return _minute_normalization_query(source)
    raise SuccessorConditioningError(f"unsupported standalone artifact kind: {kind}")


def _normalized_target(analysis_root: Path, token: str) -> Path:
    return analysis_root / "normalized" / f"{token}.parquet"


def _normalize_artifact_worker(payload: dict[str, object]) -> dict[str, object]:
    source = Path(str(payload["source_path"])).resolve()
    target = Path(str(payload["target_path"])).resolve()
    token = str(payload["token"])
    kind = str(payload["kind"])
    expected_sha = str(payload["source_sha256"])
    expected_count = int(payload["record_count"])
    threads = int(payload["duckdb_threads"])
    if not source.is_file() or _sha256_file(source) != expected_sha:
        raise SuccessorConditioningError(f"standalone source hash drifted before conditioning: {token}")
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect()
    try:
        conn.execute(f"PRAGMA threads={max(1, threads)}")
        conn.execute("PRAGMA preserve_insertion_order=false")
        query = normalization_query(source, kind, expected_count)
        _copy_query_atomic(conn, query, target)
        row_count = int(
            conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(target)}')").fetchone()[0]
        )
    finally:
        conn.close()
    if row_count != expected_count:
        target.unlink(missing_ok=True)
        raise SuccessorConditioningError(
            f"normalized row count drifted for {token}: {row_count} != {expected_count}"
        )
    receipt = _publish_artifact_receipt(
        target,
        phase="NORMALIZE_PART",
        row_count=row_count,
        extra={
            "token": token,
            "kind": kind,
            "source_path": str(source),
            "source_sha256": expected_sha,
        },
    )
    return {
        "token": token,
        "kind": kind,
        "row_count": row_count,
        "artifact_sha256": receipt["artifact_sha256"],
    }


def _normalized_reusable(analysis_root: Path, artifact: StandaloneArtifact) -> dict[str, object] | None:
    target = _normalized_target(analysis_root, artifact.token)
    if not artifact.source_path.is_file() or _sha256_file(artifact.source_path) != artifact.sha256:
        return None
    return _reusable_artifact(
        target,
        phase="NORMALIZE_PART",
        expected_row_count=artifact.record_count,
        extra_required={
            "token": artifact.token,
            "kind": artifact.kind,
            "source_path": str(artifact.source_path.resolve()),
            "source_sha256": artifact.sha256,
        },
    )


def _format_duration(seconds: float | None) -> str:
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return "n/a"
    value = int(round(seconds))
    hours, rem = divmod(value, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours}h{minutes:02d}m{secs:02d}s" if hours else f"{minutes}m{secs:02d}s"


def _write_progress(
    path: Path,
    *,
    phase: str,
    completed: int,
    total: int,
    rows_completed: int,
    total_rows: int,
    started: float,
    reused: int = 0,
    active: int = 0,
    state: str = "RUNNING",
) -> dict[str, object]:
    elapsed = max(0.0, time.monotonic() - started)
    fresh = max(0, completed - reused)
    fresh_rate = None if fresh <= 0 or elapsed <= 0 else fresh * 3600.0 / elapsed
    remaining = max(0, total - completed)
    eta = None if fresh_rate in (None, 0) else remaining / fresh_rate * 3600.0
    payload = {
        "contract": SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
        "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
        "state": state,
        "phase": phase,
        "completed_parts": completed,
        "total_parts": total,
        "reused_parts": reused,
        "fresh_parts": fresh,
        "active": active,
        "rows_completed": rows_completed,
        "total_rows": total_rows,
        "elapsed_seconds": round(elapsed, 3),
        "fresh_parts_per_hour": fresh_rate,
        "eta_seconds": eta,
        "updated_at_utc": datetime.now(UTC).isoformat(),
        "authority": "NON_AUTHORITATIVE_OPERATIONAL",
    }
    _write_json(path, payload)
    return payload


def normalize_standalone_artifacts(
    artifacts: Sequence[StandaloneArtifact],
    *,
    analysis_root: Path,
    execution_profile: SuccessorResearchExecutionProfile,
) -> tuple[dict[str, object], ...]:
    analysis_root.mkdir(parents=True, exist_ok=True)
    progress_path = analysis_root / "progress.json"
    started = time.monotonic()
    completed: dict[str, dict[str, object]] = {}
    reused = 0
    rows_completed = 0
    pending: list[StandaloneArtifact] = []
    for artifact in artifacts:
        receipt = _normalized_reusable(analysis_root, artifact)
        if receipt is None:
            pending.append(artifact)
            continue
        completed[artifact.token] = {
            "token": artifact.token,
            "kind": artifact.kind,
            "row_count": artifact.record_count,
            "artifact_sha256": receipt["artifact_sha256"],
        }
        reused += 1
        rows_completed += artifact.record_count
    total_rows = sum(item.record_count for item in artifacts)
    initial = _write_progress(
        progress_path,
        phase="NORMALIZE",
        completed=len(completed),
        total=len(artifacts),
        rows_completed=rows_completed,
        total_rows=total_rows,
        started=started,
        reused=reused,
        active=0,
    )
    print(
        "successor conditioning normalization "
        f"completed={initial['completed_parts']}/{initial['total_parts']} reused={reused} "
        f"pending={len(pending)} workers={execution_profile.workers}x"
        f"{execution_profile.duckdb_threads_per_worker}",
        flush=True,
    )
    if not pending:
        _write_progress(
            progress_path,
            phase="NORMALIZE",
            completed=len(artifacts),
            total=len(artifacts),
            rows_completed=total_rows,
            total_rows=total_rows,
            started=started,
            reused=reused,
            active=0,
            state="COMPLETE",
        )
        return tuple(completed[token] for token in sorted(completed))

    workers = min(execution_profile.workers, len(pending))
    payloads = [
        {
            "source_path": str(item.source_path),
            "target_path": str(_normalized_target(analysis_root, item.token)),
            "token": item.token,
            "kind": item.kind,
            "source_sha256": item.sha256,
            "record_count": item.record_count,
            "duckdb_threads": execution_profile.duckdb_threads_per_worker,
        }
        for item in pending
    ]
    last_machine = 0.0
    last_console = 0.0
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_normalize_artifact_worker, payload): payload for payload in payloads}
        while futures:
            done, _ = wait(tuple(futures), timeout=MACHINE_HEARTBEAT_SECONDS, return_when=FIRST_COMPLETED)
            for future in done:
                payload = futures.pop(future)
                result = future.result()
                completed[str(result["token"])] = result
                rows_completed += int(result["row_count"])
                print(
                    f"successor conditioning normalized token={result['token']} "
                    f"completed={len(completed)}/{len(artifacts)}",
                    flush=True,
                )
            now = time.monotonic()
            if done or now - last_machine >= MACHINE_HEARTBEAT_SECONDS:
                status = _write_progress(
                    progress_path,
                    phase="NORMALIZE",
                    completed=len(completed),
                    total=len(artifacts),
                    rows_completed=rows_completed,
                    total_rows=total_rows,
                    started=started,
                    reused=reused,
                    active=len(futures),
                )
                last_machine = now
                if now - last_console >= CONSOLE_HEARTBEAT_SECONDS:
                    rate = status["fresh_parts_per_hour"]
                    rate_text = "n/a" if rate is None else f"{float(rate):.2f}/h"
                    print(
                        "successor conditioning progress "
                        f"{len(completed)}/{len(artifacts)} ({len(completed)/len(artifacts):.1%}) "
                        f"rows={rows_completed:,}/{total_rows:,} fresh_rate={rate_text} "
                        f"eta={_format_duration(status['eta_seconds'])}",
                        flush=True,
                    )
                    last_console = now
    if len(completed) != len(artifacts) or rows_completed != total_rows:
        raise SuccessorConditioningError("normalization completion did not reconcile")
    _write_progress(
        progress_path,
        phase="NORMALIZE",
        completed=len(artifacts),
        total=len(artifacts),
        rows_completed=total_rows,
        total_rows=total_rows,
        started=started,
        reused=reused,
        active=0,
        state="COMPLETE",
    )
    return tuple(completed[token] for token in sorted(completed))


def build_walk_forward_folds(start_session: date, end_session: date) -> tuple[WalkForwardFold, ...]:
    calendar = xcals.get_calendar("XNYS")
    sessions = [
        stamp.date()
        for stamp in calendar.sessions_in_range(pd.Timestamp(start_session), pd.Timestamp(end_session))
    ]
    folds: list[WalkForwardFold] = []
    test_start_index = ROLLING_TRAIN_SESSIONS + WALK_FORWARD_EMBARGO_SESSIONS
    fold_id = 1
    while test_start_index + WALK_FORWARD_TEST_SESSIONS <= len(sessions):
        train_end_index = test_start_index - WALK_FORWARD_EMBARGO_SESSIONS - 1
        train_start_index = train_end_index - ROLLING_TRAIN_SESSIONS + 1
        embargo_index = train_end_index + 1
        test_end_index = test_start_index + WALK_FORWARD_TEST_SESSIONS - 1
        folds.append(
            WalkForwardFold(
                fold_id=fold_id,
                train_start=sessions[train_start_index],
                train_end=sessions[train_end_index],
                embargo_session=sessions[embargo_index],
                test_start=sessions[test_start_index],
                test_end=sessions[test_end_index],
            )
        )
        fold_id += 1
        test_start_index += WALK_FORWARD_STEP_SESSIONS
    if not folds:
        raise SuccessorConditioningError("DEVELOPMENT span cannot form a walk-forward fold")
    return tuple(folds)


def _metrics_sql(group_cols: tuple[str, ...]) -> str:
    prefix = ", ".join(group_cols)
    select_prefix = (prefix + ", ") if prefix else ""
    group = " GROUP BY " + ", ".join(str(index + 1) for index in range(len(group_cols))) if group_cols else ""
    return f"""
        SELECT {select_prefix}
            count(*) AS fired_opportunities,
            count(*) FILTER (WHERE eligible_opportunity) AS eligible_opportunities,
            count(*) FILTER (WHERE comparable) AS comparable,
            count(*) FILTER (WHERE eligible_opportunity AND NOT comparable) AS noncomparable,
            count(DISTINCT session_date) FILTER (WHERE eligible_opportunity) AS unique_sessions,
            count(DISTINCT instrument_key) FILTER (WHERE eligible_opportunity) AS unique_instruments,
            avg(CASE WHEN comparable THEN CASE WHEN primary_net_return > 0 THEN 1.0 ELSE 0.0 END END) AS win_rate_primary,
            avg(gross_return) FILTER (WHERE comparable) AS mean_gross_return,
            median(gross_return) FILTER (WHERE comparable) AS median_gross_return,
            avg(primary_net_return) FILTER (WHERE comparable) AS mean_primary_net_return,
            median(primary_net_return) FILTER (WHERE comparable) AS median_primary_net_return,
            avg(stress_net_return) FILTER (WHERE comparable) AS mean_stress_net_return,
            median(stress_net_return) FILTER (WHERE comparable) AS median_stress_net_return,
            avg(net_return_0) FILTER (WHERE comparable) AS mean_net_return_0,
            avg(net_return_10) FILTER (WHERE comparable) AS mean_net_return_10,
            avg(net_return_25) FILTER (WHERE comparable) AS mean_net_return_25,
            avg(net_return_50) FILTER (WHERE comparable) AS mean_net_return_50,
            avg(net_return_100) FILTER (WHERE comparable) AS mean_net_return_100,
            sum(CASE WHEN comparable AND primary_net_return > 0 THEN primary_net_return ELSE 0 END)
              / nullif(abs(sum(CASE WHEN comparable AND primary_net_return < 0 THEN primary_net_return ELSE 0 END)), 0)
              AS profit_factor_primary,
            avg(net_r_primary) FILTER (WHERE comparable) AS mean_net_r_primary,
            median(net_r_primary) FILTER (WHERE comparable) AS median_net_r_primary,
            avg(mfe) FILTER (WHERE comparable) AS mean_mfe,
            avg(mae) FILTER (WHERE comparable) AS mean_mae,
            avg(holding_minutes) FILTER (WHERE comparable) AS mean_holding_minutes,
            median(holding_minutes) FILTER (WHERE comparable) AS median_holding_minutes,
            avg(daily_h1_primary) FILTER (WHERE comparable AND native_timeframe='1d') AS mean_daily_h1_primary,
            avg(daily_h20_primary) FILTER (WHERE comparable AND native_timeframe='1d') AS mean_daily_h20_primary,
            avg(CASE WHEN eligible_opportunity AND NOT comparable THEN 1.0 ELSE 0.0 END) AS noncomparable_rate
        FROM opportunities
        {group}
    """


def _materialize_condition_cells(conn: duckdb.DuckDBPyConnection, target: Path) -> None:
    queries: list[str] = []
    metric_names = (
        "fired_opportunities, eligible_opportunities, comparable, noncomparable, unique_sessions, "
        "unique_instruments, win_rate_primary, mean_gross_return, median_gross_return, "
        "mean_primary_net_return, median_primary_net_return, mean_stress_net_return, "
        "median_stress_net_return, mean_net_return_0, mean_net_return_10, mean_net_return_25, "
        "mean_net_return_50, mean_net_return_100, profit_factor_primary, mean_net_r_primary, "
        "median_net_r_primary, mean_mfe, mean_mae, mean_holding_minutes, median_holding_minutes, "
        "mean_daily_h1_primary, mean_daily_h20_primary, noncomparable_rate"
    )
    for name in CONDITION_DIMENSIONS:
        metrics = _metrics_sql(("policy_id", "direction", name))
        queries.append(
            "SELECT policy_id, direction, "
            f"'{name}' AS condition_name, CAST({name} AS VARCHAR) AS condition_value, {metric_names} "
            f"FROM ({metrics})"
        )
    for interaction in PRIMARY_CONDITION_INTERACTIONS:
        label = "__x__".join(interaction)
        expression = "concat_ws('|', " + ", ".join(interaction) + ")"
        metrics = _metrics_sql(("policy_id", "direction") + tuple(interaction))
        queries.append(
            "SELECT policy_id, direction, "
            f"'{label}' AS condition_name, {expression} AS condition_value, {metric_names} "
            f"FROM ({metrics})"
        )
    union = " UNION ALL ".join(queries)
    query = f"""
        SELECT *,
            eligible_opportunities >= {MIN_CELL_OPPORTUNITIES}
            AND unique_sessions >= {MIN_CELL_UNIQUE_SESSIONS}
            AND unique_instruments >= {MIN_CELL_UNIQUE_INSTRUMENTS}
            AS minimum_support
        FROM ({union})
        ORDER BY policy_id, direction, condition_name, condition_value
    """
    _copy_query_atomic(conn, query, target)


def _rows_to_cell_maps(
    session_rows: list[tuple],
    symbol_rows: list[tuple],
    key_count: int,
) -> tuple[dict[tuple[str, ...], list[tuple]], dict[tuple[str, ...], list[tuple[str, tuple[date, ...]]]]]:
    session_map: dict[tuple[str, ...], list[tuple]] = defaultdict(list)
    for row in session_rows:
        key = tuple(str(item) for item in row[:key_count])
        day = row[key_count]
        if isinstance(day, datetime):
            day = day.date()
        session_map[key].append((day, int(row[key_count + 1]), int(row[key_count + 2]), float(row[key_count + 3] or 0.0)))
    for values in session_map.values():
        values.sort(key=lambda item: item[0])
    symbol_map: dict[tuple[str, ...], list[tuple[str, tuple[date, ...]]]] = defaultdict(list)
    for row in symbol_rows:
        key = tuple(str(item) for item in row[:key_count])
        symbol = str(row[key_count])
        raw_sessions = row[key_count + 1] or []
        sessions = tuple(item.date() if isinstance(item, datetime) else item for item in raw_sessions)
        symbol_map[key].append((symbol, sessions))
    return dict(session_map), dict(symbol_map)


def _slice_session_rows(rows: list[tuple], start: date, end: date) -> list[tuple]:
    dates = [item[0] for item in rows]
    return rows[bisect.bisect_left(dates, start) : bisect.bisect_right(dates, end)]


def _symbol_present(sessions: tuple[date, ...], start: date, end: date) -> bool:
    index = bisect.bisect_left(sessions, start)
    return index < len(sessions) and sessions[index] <= end


def _empirical_lower_quantile(values: np.ndarray, q: float) -> float:
    ordered = np.sort(values.astype(float, copy=False))
    rank = max(1, math.ceil(q * ordered.size))
    return float(ordered[rank - 1])


def _bootstrap_lcb(
    session_sums: np.ndarray,
    session_counts: np.ndarray,
    *,
    seed_material: str,
) -> float | None:
    if session_sums.size == 0 or session_counts.size == 0:
        return None
    if session_sums.size != session_counts.size or np.any(session_counts <= 0):
        raise SuccessorConditioningError("invalid session-cluster bootstrap inputs")
    seed = int.from_bytes(hashlib.sha256(seed_material.encode("utf-8")).digest()[:8], "big")
    rng = np.random.default_rng(seed)
    n = session_sums.size
    indices = rng.integers(0, n, size=(SESSION_CLUSTER_BOOTSTRAP_DRAWS, n))
    means = session_sums[indices].sum(axis=1) / session_counts[indices].sum(axis=1)
    return _empirical_lower_quantile(means, SELECTOR_LCB_QUANTILE)


def _build_selector_scores(
    conn: duckdb.DuckDBPyConnection,
    *,
    folds: tuple[WalkForwardFold, ...],
    progress_path: Path,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total_steps = len(SELECTOR_FALLBACK_HIERARCHY) * len(folds)
    completed_steps = 0
    for level_index, hierarchy in enumerate(SELECTOR_FALLBACK_HIERARCHY, start=1):
        key_column = f"selector_key_{level_index}"
        session_rows = conn.execute(
            f"""
            SELECT {key_column}, session_date,
                   count(*) AS opportunities,
                   count(*) FILTER (WHERE comparable) AS comparable,
                   coalesce(sum(primary_net_return) FILTER (WHERE comparable), 0.0) AS sum_primary
            FROM opportunities
            WHERE eligible_opportunity
            GROUP BY {key_column}, session_date
            ORDER BY {key_column}, session_date
            """
        ).fetchall()
        symbol_rows = conn.execute(
            f"""
            SELECT {key_column}, instrument_key, list(session_date ORDER BY session_date) AS sessions
            FROM (
                SELECT DISTINCT {key_column}, instrument_key, session_date
                FROM opportunities
                WHERE eligible_opportunity
            )
            GROUP BY {key_column}, instrument_key
            ORDER BY {key_column}, instrument_key
            """
        ).fetchall()
        session_map, symbol_map = _rows_to_cell_maps(session_rows, symbol_rows, 1)
        for fold in folds:
            for key, cell_rows in session_map.items():
                test_rows = _slice_session_rows(cell_rows, fold.test_start, fold.test_end)
                if not test_rows:
                    continue
                train_rows = _slice_session_rows(cell_rows, fold.train_start, fold.train_end)
                opportunities = sum(item[1] for item in train_rows)
                comparable = sum(item[2] for item in train_rows)
                unique_sessions = len(train_rows)
                unique_instruments = sum(
                    1 for _symbol, sessions in symbol_map.get(key, [])
                    if _symbol_present(sessions, fold.train_start, fold.train_end)
                )
                supported = (
                    opportunities >= MIN_CELL_OPPORTUNITIES
                    and unique_sessions >= MIN_CELL_UNIQUE_SESSIONS
                    and unique_instruments >= MIN_CELL_UNIQUE_INSTRUMENTS
                )
                score: float | None = None
                if supported and comparable > 0:
                    comparable_rows = [item for item in train_rows if item[2] > 0]
                    sums = np.asarray([item[3] for item in comparable_rows], dtype=float)
                    counts = np.asarray([item[2] for item in comparable_rows], dtype=np.int64)
                    seed_material = (
                        f"{SUCCESSOR_CONDITIONING_FINGERPRINT}|"
                        f"{ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT}|"
                        f"fold={fold.fold_id}|level={level_index}|cell={key[0]}"
                    )
                    score = _bootstrap_lcb(sums, counts, seed_material=seed_material)
                rows.append(
                    {
                        "fold_id": fold.fold_id,
                        "hierarchy_level": level_index,
                        "cell_key": key[0],
                        "training_opportunities": opportunities,
                        "training_comparable": comparable,
                        "training_unique_sessions": unique_sessions,
                        "training_unique_instruments": unique_instruments,
                        "minimum_support": supported,
                        "score_lcb_primary_net_return": score,
                        "eligible_positive": bool(supported and score is not None and score > 0.0),
                    }
                )
            completed_steps += 1
            _write_json(
                progress_path,
                {
                    "contract": SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
                    "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
                    "state": "RUNNING",
                    "phase": "SELECTOR",
                    "completed": completed_steps,
                    "total": total_steps,
                    "hierarchy_level": level_index,
                    "fold_id": fold.fold_id,
                    "updated_at_utc": datetime.now(UTC).isoformat(),
                    "authority": "NON_AUTHORITATIVE_OPERATIONAL",
                },
            )
        del session_rows, symbol_rows, session_map, symbol_map
    return pd.DataFrame.from_records(rows)


def _selector_assignments_sql() -> str:
    joins: list[str] = []
    support_cases: list[str] = []
    score_cases: list[str] = []
    for level in range(1, len(SELECTOR_FALLBACK_HIERARCHY) + 1):
        joins.append(
            f"LEFT JOIN selector_scores s{level} ON s{level}.fold_id=f.fold_id "
            f"AND s{level}.hierarchy_level={level} AND s{level}.cell_key=o.selector_key_{level}"
        )
        prior_unsupported = " AND ".join(
            f"coalesce(s{prior}.minimum_support, false)=false" for prior in range(1, level)
        )
        condition = f"coalesce(s{level}.minimum_support, false)=true"
        if prior_unsupported:
            condition = f"({prior_unsupported}) AND ({condition})"
        support_cases.append(f"WHEN {condition} THEN {level}")
        score_cases.append(f"WHEN {condition} THEN s{level}.score_lcb_primary_net_return")
    return f"""
        WITH assigned AS (
            SELECT
                f.fold_id, o.session_date, o.calendar_year, o.policy_id, o.economic_family_id,
                o.native_timeframe, o.instrument_key, o.ticker, o.direction,
                o.eligible_opportunity, o.comparable, o.primary_net_return, o.stress_net_return,
                o.market_direction_alignment, o.market_volatility_state,
                o.higher_timeframe_ticker_trend, o.signal_time_bucket, o.liquidity_bucket,
                CASE {' '.join(support_cases)} ELSE NULL END AS fallback_level,
                CASE {' '.join(score_cases)} ELSE NULL END AS selector_score
            FROM opportunities o
            JOIN folds f ON o.session_date BETWEEN f.test_start AND f.test_end
            {' '.join(joins)}
        )
        SELECT *,
               eligible_opportunity AND selector_score IS NOT NULL AND selector_score > 0.0
                   AS research_eligible
        FROM assigned
    """


def _clean_records(records: list[dict[str, object]]) -> list[dict[str, object]]:
    cleaned: list[dict[str, object]] = []
    for record in records:
        item: dict[str, object] = {}
        for key, value in record.items():
            if isinstance(value, float) and math.isnan(value):
                item[key] = None
            elif isinstance(value, (pd.Timestamp, date, datetime)):
                item[key] = value.isoformat()
            elif isinstance(value, np.generic):
                item[key] = value.item()
            else:
                item[key] = value
        cleaned.append(item)
    return cleaned


def _selector_summary(conn: duckdb.DuckDBPyConnection) -> dict[str, object]:
    overall = conn.execute(
        """
        SELECT
            count(*) AS test_fired_opportunities,
            count(*) FILTER (WHERE eligible_opportunity) AS test_eligible_opportunities,
            count(*) FILTER (WHERE research_eligible) AS selected_opportunities,
            count(*) FILTER (WHERE research_eligible AND comparable) AS selected_comparable,
            avg(CASE WHEN eligible_opportunity THEN CASE WHEN research_eligible THEN 1.0 ELSE 0.0 END END)
                AS selection_rate_among_eligible,
            avg(CASE WHEN eligible_opportunity THEN CASE WHEN research_eligible THEN 0.0 ELSE 1.0 END END)
                AS abstention_rate_among_eligible,
            avg(primary_net_return) FILTER (WHERE comparable) AS standalone_mean_primary_net_return,
            avg(primary_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_mean_primary_net_return,
            median(primary_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_median_primary_net_return,
            avg(stress_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_mean_stress_net_return,
            avg(CASE WHEN research_eligible AND comparable THEN CASE WHEN primary_net_return > 0 THEN 1.0 ELSE 0.0 END END)
                AS selected_win_rate_primary
        FROM eligibility_assignments
        """
    ).fetchdf().to_dict(orient="records")[0]
    by_policy = conn.execute(
        """
        SELECT policy_id, direction, native_timeframe,
               count(*) AS test_fired,
               count(*) FILTER (WHERE eligible_opportunity) AS test_eligible,
               count(*) FILTER (WHERE research_eligible) AS selected,
               count(*) FILTER (WHERE research_eligible AND comparable) AS selected_comparable,
               avg(primary_net_return) FILTER (WHERE comparable) AS standalone_mean_primary_net_return,
               avg(primary_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_mean_primary_net_return,
               avg(stress_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_mean_stress_net_return
        FROM eligibility_assignments
        GROUP BY policy_id, direction, native_timeframe
        ORDER BY policy_id, direction
        """
    ).fetchdf().to_dict(orient="records")
    by_fold = conn.execute(
        """
        SELECT fold_id, min(session_date) AS test_start, max(session_date) AS test_end,
               count(*) FILTER (WHERE eligible_opportunity) AS eligible,
               count(*) FILTER (WHERE research_eligible) AS selected,
               count(*) FILTER (WHERE research_eligible AND comparable) AS selected_comparable,
               avg(primary_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_mean_primary_net_return,
               avg(stress_net_return) FILTER (WHERE research_eligible AND comparable) AS selected_mean_stress_net_return
        FROM eligibility_assignments
        GROUP BY fold_id ORDER BY fold_id
        """
    ).fetchdf().to_dict(orient="records")
    fallback = conn.execute(
        """
        SELECT fallback_level, count(*) FILTER (WHERE eligible_opportunity) AS opportunities,
               count(*) FILTER (WHERE research_eligible) AS selected
        FROM eligibility_assignments
        GROUP BY fallback_level ORDER BY fallback_level NULLS LAST
        """
    ).fetchdf().to_dict(orient="records")
    return {
        "overall": _clean_records([overall])[0],
        "by_policy": _clean_records(by_policy),
        "by_fold": _clean_records(by_fold),
        "fallback_usage": _clean_records(fallback),
    }


def _aggregate_artifact(
    conn: duckdb.DuckDBPyConnection,
    *,
    path: Path,
    phase: str,
    query: str,
) -> dict[str, object]:
    reused = _reusable_artifact(path, phase=phase)
    if reused is not None:
        return reused
    _copy_query_atomic(conn, query, path)
    count = int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(path)}')").fetchone()[0])
    return _publish_artifact_receipt(path, phase=phase, row_count=count)


def run_successor_conditioning_analysis(
    project_root: Path,
    *,
    execution_profile: SuccessorResearchExecutionProfile | None = None,
) -> dict[str, object]:
    project = Path(project_root).resolve()
    standalone_root, standalone_summary, artifacts = validate_accepted_standalone(project)
    profile = execution_profile or resolve_successor_research_execution_profile()
    analysis_root = standalone_root / "conditioning_v1" / SUCCESSOR_CONDITIONING_FINGERPRINT[:16]
    analysis_root.mkdir(parents=True, exist_ok=True)
    _write_json(analysis_root / "conditioning_contract.json", successor_conditioning_manifest())
    print(
        "successor conditioning authority: DEVELOPMENT-only immutable standalone artifacts; "
        "master/future/provider/broker/PAPER/LIVE/promotion forbidden",
        flush=True,
    )
    print(
        "successor conditioning execution profile="
        f"{profile.workers} workers x {profile.duckdb_threads_per_worker} DuckDB thread",
        flush=True,
    )

    normalized = normalize_standalone_artifacts(
        artifacts,
        analysis_root=analysis_root,
        execution_profile=profile,
    )
    if sum(int(item["row_count"]) for item in normalized) != ACCEPTED_STANDALONE_RECORD_COUNT:
        raise SuccessorConditioningError("normalized record count does not match accepted standalone")
    normalized_set_fingerprint = canonical_sha256(
        [
            {
                "token": item["token"],
                "kind": item["kind"],
                "row_count": int(item["row_count"]),
                "artifact_sha256": item["artifact_sha256"],
            }
            for item in normalized
        ]
    )

    conn = duckdb.connect()
    try:
        conn.execute(f"PRAGMA threads={max(1, profile.aggregate_worker_threads)}")
        conn.execute("PRAGMA preserve_insertion_order=false")
        normalized_glob = analysis_root / "normalized" / "*.parquet"
        conn.execute(
            f"CREATE OR REPLACE TEMP VIEW opportunities AS "
            f"SELECT * FROM read_parquet('{_sql_path(normalized_glob)}', union_by_name=true)"
        )
        count = int(conn.execute("SELECT count(*) FROM opportunities").fetchone()[0])
        if count != ACCEPTED_STANDALONE_RECORD_COUNT:
            raise SuccessorConditioningError("normalized opportunity view does not reconcile")
        invalid_scope = int(
            conn.execute(
                f"SELECT count(*) FROM opportunities WHERE session_date < DATE '{DEVELOPMENT_START}' "
                f"OR session_date > DATE '{DEVELOPMENT_END}' OR session_date IS NULL"
            ).fetchone()[0]
        )
        if invalid_scope:
            raise SuccessorConditioningError("normalized opportunities escaped DEVELOPMENT scope")
        frozen_policy_ids = {route.policy_id for route in successor_policy_routes()}
        observed_policy_ids = {str(row[0]) for row in conn.execute("SELECT DISTINCT policy_id FROM opportunities").fetchall()}
        if not observed_policy_ids.issubset(frozen_policy_ids) or None in observed_policy_ids:
            raise SuccessorConditioningError("normalized policy ids escaped frozen successor routes")
        expected_policy_counts = standalone_summary["standalone"].get("policy_record_counts")
        if not isinstance(expected_policy_counts, dict):
            raise SuccessorConditioningError("accepted standalone policy counts are missing")
        actual_policy_counts = {
            str(policy): int(value)
            for policy, value in conn.execute(
                "SELECT policy_id, count(*) FROM opportunities GROUP BY policy_id ORDER BY policy_id"
            ).fetchall()
        }
        if actual_policy_counts != {str(key): int(value) for key, value in expected_policy_counts.items()}:
            raise SuccessorConditioningError("normalized policy record counts drifted")

        route_path = analysis_root / "route_summary.parquet"
        route_receipt = _aggregate_artifact(
            conn,
            path=route_path,
            phase="ROUTE_SUMMARY",
            query=(
                f"{_metrics_sql(('policy_id', 'economic_family_id', 'native_timeframe', 'direction'))} "
                "ORDER BY policy_id, direction"
            ),
        )
        condition_path = analysis_root / "condition_cells.parquet"
        condition_reused = _reusable_artifact(condition_path, phase="CONDITION_CELLS")
        if condition_reused is None:
            _materialize_condition_cells(conn, condition_path)
            condition_count = int(
                conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(condition_path)}')").fetchone()[0]
            )
            condition_receipt = _publish_artifact_receipt(
                condition_path, phase="CONDITION_CELLS", row_count=condition_count
            )
        else:
            condition_receipt = condition_reused
        year_path = analysis_root / "year_summary.parquet"
        year_receipt = _aggregate_artifact(
            conn,
            path=year_path,
            phase="YEAR_SUMMARY",
            query=(
                f"{_metrics_sql(('policy_id', 'direction', 'calendar_year'))} "
                "ORDER BY policy_id, direction, calendar_year"
            ),
        )

        folds = build_walk_forward_folds(date.fromisoformat(DEVELOPMENT_START), date.fromisoformat(DEVELOPMENT_END))
        folds_df = pd.DataFrame([asdict(item) for item in folds])
        conn.register("folds", folds_df)
        score_path = analysis_root / "selector_scores.parquet"
        score_reused = _reusable_artifact(score_path, phase="SELECTOR_SCORES")
        if score_reused is None:
            scores = _build_selector_scores(conn, folds=folds, progress_path=analysis_root / "progress.json")
            if scores.empty:
                raise SuccessorConditioningError("selector score table is unexpectedly empty")
            conn.register("selector_scores_publish", scores)
            _copy_query_atomic(
                conn,
                "SELECT * FROM selector_scores_publish ORDER BY fold_id, hierarchy_level, cell_key",
                score_path,
            )
            score_receipt = _publish_artifact_receipt(
                score_path, phase="SELECTOR_SCORES", row_count=len(scores)
            )
        else:
            score_receipt = score_reused
            scores = conn.execute(f"SELECT * FROM read_parquet('{_sql_path(score_path)}')").fetchdf()
        conn.register("selector_scores", scores)

        assignment_path = analysis_root / "eligibility_assignments.parquet"
        assignment_reused = _reusable_artifact(assignment_path, phase="ELIGIBILITY_ASSIGNMENTS")
        if assignment_reused is None:
            _copy_query_atomic(conn, _selector_assignments_sql(), assignment_path)
            assignment_count = int(
                conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(assignment_path)}')").fetchone()[0]
            )
            assignment_receipt = _publish_artifact_receipt(
                assignment_path, phase="ELIGIBILITY_ASSIGNMENTS", row_count=assignment_count
            )
        else:
            assignment_receipt = assignment_reused
        conn.execute(
            f"CREATE OR REPLACE TEMP VIEW eligibility_assignments AS "
            f"SELECT * FROM read_parquet('{_sql_path(assignment_path)}')"
        )
        selector_summary = _selector_summary(conn)
        folds_payload = [_clean_records([asdict(item)])[0] for item in folds]

        output_receipts = {
            "route_summary": route_receipt,
            "condition_cells": condition_receipt,
            "year_summary": year_receipt,
            "selector_scores": score_receipt,
            "eligibility_assignments": assignment_receipt,
        }
        output_identity = [
            {
                "name": name,
                "sha256": receipt["artifact_sha256"],
                "row_count": int(receipt["row_count"]),
            }
            for name, receipt in sorted(output_receipts.items())
        ]
        report = {
            "status": "COMPLETE_CONDITIONING_ONLY",
            "contract": SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
            "conditioning_contract": SUCCESSOR_CONDITIONING_CONTRACT,
            "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
            "accepted_standalone": {
                "run_contract_fingerprint": ACCEPTED_RUN_CONTRACT_FINGERPRINT,
                "standalone_run_fingerprint": ACCEPTED_STANDALONE_RUN_FINGERPRINT,
                "artifact_set_fingerprint": ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
                "input_manifest_fingerprint": ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
                "group_count": ACCEPTED_GROUP_COUNT,
                "record_count": ACCEPTED_STANDALONE_RECORD_COUNT,
            },
            "normalized": {
                "part_count": len(normalized),
                "record_count": count,
                "artifact_set_fingerprint": normalized_set_fingerprint,
            },
            "fold_count": len(folds),
            "folds": folds_payload,
            "selector_summary": selector_summary,
            "outputs": output_identity,
            "output_artifact_set_fingerprint": canonical_sha256(output_identity),
            "execution_profile": profile.as_dict(),
            "execution_profile_in_scientific_fingerprint": False,
            "conditioning_opened": True,
            "confluence_opened": False,
            "b35_inspired_challenger_result_authority": "DIAGNOSTIC_TRAINING_ONLY_CANNOT_SELF_VALIDATE_ON_DEVELOPMENT",
            "raw_market_data_reread": False,
            "consumed_master_rows_read": 0,
            "future_blind_rows_read": 0,
            "provider_calls": 0,
            "broker_reads": 0,
            "broker_writes": 0,
            "paper_authority": False,
            "live_authority": False,
            "strategy_promotion": False,
            "selector_promotion": False,
            "authority": AUTHORITY,
        }
        report["analysis_fingerprint"] = _stable_hash(
            {
                "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
                "accepted_standalone_artifact_set": ACCEPTED_STANDALONE_ARTIFACT_SET_FINGERPRINT,
                "normalized_artifact_set": normalized_set_fingerprint,
                "output_artifact_set": report["output_artifact_set_fingerprint"],
            }
        )
        _write_json(analysis_root / "analysis_summary.json", report)
        _write_json(analysis_root / "folds.json", folds_payload)
        _write_json(
            analysis_root / "progress.json",
            {
                "contract": SUCCESSOR_CONDITIONING_ANALYSIS_CONTRACT,
                "conditioning_fingerprint": SUCCESSOR_CONDITIONING_FINGERPRINT,
                "state": "COMPLETE",
                "phase": "COMPLETE",
                "record_count": count,
                "updated_at_utc": datetime.now(UTC).isoformat(),
                "authority": "NON_AUTHORITATIVE_OPERATIONAL",
            },
        )
        return report
    finally:
        conn.close()
