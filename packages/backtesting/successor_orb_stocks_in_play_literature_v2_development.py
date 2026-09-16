from __future__ import annotations

import hashlib
import json
import math
import os
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Iterable, Sequence

import duckdb
import numpy as np
import pandas as pd

from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentUnitBinding,
)
from packages.backtesting.reference_v2_lake_adapter import ReferenceV2DailyLakeAdapter
from packages.backtesting.successor_development_outcomes import (
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    validate_accepted_successor_preflight,
)
from packages.backtesting.successor_runner_contract import minute_symbol_groups
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import load_settings
from packages.core.successor_execution_profile import resolve_successor_research_execution_profile
from packages.features.volatility import atr_wilder
from packages.strategies.successor_orb_stocks_in_play_literature_v2_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
)
from packages.strategies.successor_orb_stocks_in_play_literature_v2_development_contract import (
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT_ID,
    ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
    contract_payload as development_contract_payload,
)


ANALYSIS_CONTRACT = "atlas-orb-stocks-in-play-5m-literature-v2-development-runner-v1"
OPENING_PHASE = "OPENING_SNAPSHOT"
PATH_PHASE = "SELECTED_FULL_PATH"
MOVE_THRESHOLDS = (0.01, 0.02, 0.03, 0.05)
COST_GRID_BPS = (0, 10, 25, 50, 100)
PRIMARY_COST_BPS = 50
STRESS_COST_BPS = 100


class OrbLiteratureV2DevelopmentError(RuntimeError):
    pass


def _stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        path,
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        fsync=True,
    )


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise OrbLiteratureV2DevelopmentError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise OrbLiteratureV2DevelopmentError(f"JSON artifact is not an object: {path}")
    return value


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _sql_paths(paths: Sequence[Path]) -> str:
    return "[" + ",".join(f"'{_sql_path(path)}'" for path in paths) + "]"


def _write_frame_atomic(
    conn: duckdb.DuckDBPyConnection,
    frame: pd.DataFrame,
    target: Path,
    *,
    order_by: str,
) -> int:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(target)
    conn.register("orb_v2_output_frame", frame)
    try:
        conn.execute(
            f"COPY (SELECT * FROM orb_v2_output_frame ORDER BY {order_by}) "
            f"TO '{_sql_path(temp)}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        with temp.open("rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(temp, target)
    finally:
        conn.unregister("orb_v2_output_frame")
        temp.unlink(missing_ok=True)
    return int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(target)}')").fetchone()[0])


def analysis_root(project_root: Path) -> Path:
    return (
        Path(project_root).resolve()
        / "data"
        / "v2_build"
        / "alpaca_sip_v2"
        / "derived"
        / "strategy_lab"
        / ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID
        / ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT[:16]
    )


def _unit_binding_payload(unit: B35DevelopmentUnitBinding) -> dict[str, object]:
    return {
        "unit_id": unit.unit_id,
        "year": unit.year,
        "month": unit.month,
        "batch_index": unit.batch_index,
        "window_start": unit.window_start.isoformat(),
        "window_end_exclusive": unit.window_end_exclusive.isoformat(),
        "symbols": list(unit.symbols),
        "policy_sha256": unit.policy_sha256,
        "universe_sha256": unit.universe_sha256,
        "canonical_sha256": unit.canonical_sha256,
    }


def _group_binding_fingerprint(units: Sequence[B35DevelopmentUnitBinding]) -> str:
    return _stable_hash([_unit_binding_payload(unit) for unit in units])


def _group_token(symbols: Sequence[str]) -> str:
    return "minute_" + _stable_hash({"symbols": list(symbols)})[:20]


def _receipt_path(artifact: Path) -> Path:
    return artifact.with_suffix(artifact.suffix + ".receipt.json")


def _publish_group_receipt(
    artifact: Path,
    *,
    phase: str,
    group_token: str,
    group_binding_fingerprint: str,
    row_count: int,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract": ANALYSIS_CONTRACT,
        "development_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
        "strategy_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
        "phase": phase,
        "group_token": group_token,
        "group_binding_fingerprint": group_binding_fingerprint,
        "artifact_sha256": _sha256_file(artifact),
        "row_count": int(row_count),
    }
    payload["receipt_id"] = _stable_hash(payload)
    _write_json(_receipt_path(artifact), payload)
    return payload


def _reusable_group_artifact(
    artifact: Path,
    *,
    phase: str,
    group_token: str,
    group_binding_fingerprint: str,
) -> dict[str, object] | None:
    receipt_path = _receipt_path(artifact)
    if not artifact.is_file() or not receipt_path.is_file():
        return None
    try:
        receipt = _read_json(receipt_path)
    except OrbLiteratureV2DevelopmentError:
        return None
    expected = _stable_hash({key: value for key, value in receipt.items() if key != "receipt_id"})
    if receipt.get("receipt_id") != expected:
        return None
    required = {
        "contract": ANALYSIS_CONTRACT,
        "development_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
        "strategy_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
        "phase": phase,
        "group_token": group_token,
        "group_binding_fingerprint": group_binding_fingerprint,
    }
    if any(receipt.get(key) != value for key, value in required.items()):
        return None
    if receipt.get("artifact_sha256") != _sha256_file(artifact):
        return None
    return receipt


def _daily_feature_receipt_path(path: Path) -> Path:
    return path.with_suffix(path.suffix + ".receipt.json")


def build_prior_daily_features(bars: pd.DataFrame) -> pd.DataFrame:
    required = {
        "instrument_id",
        "ticker",
        "session_date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "unadjusted_close",
    }
    missing = sorted(required.difference(bars.columns))
    if missing:
        raise OrbLiteratureV2DevelopmentError(
            "daily feature source is missing columns: " + ", ".join(missing)
        )
    if bars.empty:
        raise OrbLiteratureV2DevelopmentError("daily feature source is empty")

    source = bars.sort_values(["instrument_id", "session_date"], kind="stable").copy()
    numeric = source[["open", "high", "low", "close", "volume", "unadjusted_close"]].to_numpy(
        dtype="float64"
    )
    if not np.isfinite(numeric).all():
        raise OrbLiteratureV2DevelopmentError("daily feature source contains non-finite values")
    factor = source["unadjusted_close"].astype("float64") / source["close"].astype("float64")
    if (~np.isfinite(factor.to_numpy(dtype="float64"))).any() or (factor <= 0.0).any():
        raise OrbLiteratureV2DevelopmentError("daily raw reconstruction factor is invalid")
    source["raw_open"] = source["open"].astype("float64") * factor
    source["raw_high"] = source["high"].astype("float64") * factor
    source["raw_low"] = source["low"].astype("float64") * factor
    source["raw_close"] = source["close"].astype("float64") * factor
    # V2 deliberately preserves provider-native split-adjusted volume as supplied.
    # The accepted source contract explicitly treats inverse-price-factor volume
    # equivalence as audit-only, so do not manufacture a raw-volume estimate.
    source["provider_native_share_volume"] = source["volume"].astype("float64")

    pieces: list[pd.DataFrame] = []
    for _, frame in source.groupby("instrument_id", sort=True, observed=True):
        frame = frame.sort_values("session_date", kind="stable").copy()
        prior_volume = (
            frame["provider_native_share_volume"]
            .rolling(window=14, min_periods=14)
            .mean()
            .shift(1)
        )
        prior_atr = atr_wilder(
            frame["raw_high"], frame["raw_low"], frame["raw_close"], 14
        ).shift(1)
        pieces.append(
            pd.DataFrame(
                {
                    "instrument_id": frame["instrument_id"].astype(str).to_numpy(),
                    "ticker": frame["ticker"].astype(str).to_numpy(),
                    "session_date": pd.to_datetime(frame["session_date"], errors="raise").dt.date.to_numpy(),
                    "prior_average_daily_share_volume_14": prior_volume.to_numpy(dtype="float64"),
                    "prior_atr_14_dollars": prior_atr.to_numpy(dtype="float64"),
                }
            )
        )
    result = pd.concat(pieces, ignore_index=True)
    duplicates = result.duplicated(["ticker", "session_date"], keep=False)
    if duplicates.any():
        sample = result.loc[duplicates, ["ticker", "session_date", "instrument_id"]].head(10)
        raise OrbLiteratureV2DevelopmentError(
            "daily PIT identity produces duplicate ticker/session rows: " + sample.to_json(orient="records")
        )
    return result


def _prepare_daily_feature_artifact(project_root: Path, output_root: Path) -> tuple[Path, dict[str, object], bool]:
    path = output_root / "prior_daily_features.parquet"
    receipt_path = _daily_feature_receipt_path(path)
    if path.is_file() and receipt_path.is_file():
        receipt = _read_json(receipt_path)
        expected = _stable_hash({key: value for key, value in receipt.items() if key != "receipt_id"})
        if (
            receipt.get("receipt_id") == expected
            and receipt.get("contract") == ANALYSIS_CONTRACT
            and receipt.get("development_contract_fingerprint")
            == ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT
            and receipt.get("artifact_sha256") == _sha256_file(path)
        ):
            return path, receipt, True

    settings = load_settings(project_root)
    adapter = ReferenceV2DailyLakeAdapter(settings)
    loaded = adapter.load(DEVELOPMENT_START, DEVELOPMENT_END)
    features = build_prior_daily_features(loaded.bars)
    conn = duckdb.connect(":memory:")
    try:
        row_count = _write_frame_atomic(
            conn,
            features,
            path,
            order_by="ticker, session_date, instrument_id",
        )
    finally:
        conn.close()
    payload: dict[str, object] = {
        "contract": ANALYSIS_CONTRACT,
        "development_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
        "strategy_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
        "phase": "PRIOR_DAILY_FEATURES",
        "artifact_sha256": _sha256_file(path),
        "row_count": row_count,
        "daily_source_fingerprint": loaded.report["source_fingerprint"],
        "research_daily_fingerprint": loaded.report["research_daily_fingerprint"],
        "manifest_sha256": loaded.report["manifest_sha256"],
        "protected_master_return_rows_read": loaded.report["protected_master_return_rows_read"],
    }
    payload["receipt_id"] = _stable_hash(payload)
    _write_json(receipt_path, payload)
    return path, payload, False


def _opening_group_worker(
    project_root_text: str,
    output_root_text: str,
    group_token: str,
    units: tuple[B35DevelopmentUnitBinding, ...],
) -> dict[str, object]:
    project_root = Path(project_root_text).resolve()
    output_root = Path(output_root_text).resolve()
    artifact = output_root / "opening_groups" / f"{group_token}.parquet"
    binding_fp = _group_binding_fingerprint(units)
    settings = load_settings(project_root)
    source = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
    try:
        reusable = _reusable_group_artifact(
            artifact,
            phase=OPENING_PHASE,
            group_token=group_token,
            group_binding_fingerprint=binding_fp,
        )
        if reusable is not None:
            for unit in units:
                source.verify_unit(unit)
            return {
                "group_token": group_token,
                "artifact": str(artifact),
                "row_count": int(reusable["row_count"]),
                "reused": True,
            }

        conn = duckdb.connect(":memory:")
        conn.execute("SET TimeZone='UTC'")
        conn.execute("PRAGMA threads=1")
        pieces: list[pd.DataFrame] = []
        session_ordinals = {
            session: ordinal
            for ordinal, session in enumerate(
                source.calendar.sessions_in_range(DEVELOPMENT_START, DEVELOPMENT_END)
            )
        }
        try:
            for unit in units:
                source.verify_unit(unit)
                calendar = source._calendar_frame(unit)  # operational reuse of accepted source calendar
                if calendar.empty:
                    continue
                conn.register("orb_calendar", calendar[["session_date", "regular_open_utc"]])
                try:
                    query = conn.execute(
                        """
                        SELECT
                            ? AS group_token,
                            ? AS unit_id,
                            p.symbol AS ticker,
                            p.session_date,
                            arg_min(CAST(p.open AS DOUBLE), p.timestamp_utc) AS opening_price,
                            arg_max(CAST(p.close AS DOUBLE), p.timestamp_utc) AS opening_close,
                            max(CAST(p.high AS DOUBLE)) AS opening_range_high,
                            min(CAST(p.low AS DOUBLE)) AS opening_range_low,
                            sum(CAST(p.volume AS DOUBLE)) AS opening_five_minute_volume,
                            min(p.timestamp_utc) AS opening_first_timestamp_utc,
                            max(p.timestamp_utc) AS opening_last_timestamp_utc,
                            count(*)::INTEGER AS opening_bar_count
                        FROM read_parquet(?, hive_partitioning=false) p
                        JOIN orb_calendar c USING (session_date)
                        WHERE p.session_segment = 'regular'
                          AND p.session_date BETWEEN ? AND ?
                          AND p.timestamp_utc >= c.regular_open_utc
                          AND p.timestamp_utc < c.regular_open_utc + INTERVAL '5 minutes'
                        GROUP BY p.symbol, p.session_date
                        HAVING count(*) = 5
                        ORDER BY p.symbol, p.session_date
                        """,
                        [
                            group_token,
                            unit.unit_id,
                            str(unit.canonical_path),
                            DEVELOPMENT_START,
                            DEVELOPMENT_END,
                        ],
                    ).fetchdf()
                finally:
                    conn.unregister("orb_calendar")
                if not query.empty:
                    query["session_ordinal"] = query["session_date"].map(session_ordinals)
                    if query["session_ordinal"].isna().any():
                        raise OrbLiteratureV2DevelopmentError(
                            "opening snapshot session is outside frozen XNYS DEVELOPMENT"
                        )
                    query["session_ordinal"] = query["session_ordinal"].astype("int64")
                    pieces.append(query)
            columns = [
                "group_token",
                "unit_id",
                "ticker",
                "session_date",
                "session_ordinal",
                "opening_price",
                "opening_close",
                "opening_range_high",
                "opening_range_low",
                "opening_five_minute_volume",
                "opening_first_timestamp_utc",
                "opening_last_timestamp_utc",
                "opening_bar_count",
            ]
            frame = pd.concat(pieces, ignore_index=True) if pieces else pd.DataFrame(columns=columns)
            row_count = _write_frame_atomic(
                conn,
                frame,
                artifact,
                order_by="ticker, session_date, unit_id",
            )
        finally:
            conn.close()
    finally:
        source.close()
    _publish_group_receipt(
        artifact,
        phase=OPENING_PHASE,
        group_token=group_token,
        group_binding_fingerprint=binding_fp,
        row_count=row_count,
    )
    return {
        "group_token": group_token,
        "artifact": str(artifact),
        "row_count": row_count,
        "reused": False,
    }


def _run_opening_groups(
    project_root: Path,
    output_root: Path,
    groups: Sequence[tuple[str, tuple[B35DevelopmentUnitBinding, ...]]],
    *,
    workers: int,
) -> list[dict[str, object]]:
    pending = {}
    results: list[dict[str, object]] = []
    started = time.monotonic()
    last_print = started
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for token, units in groups:
            future = executor.submit(
                _opening_group_worker,
                str(project_root),
                str(output_root),
                token,
                units,
            )
            pending[future] = token
        while pending:
            done, _ = wait(tuple(pending), timeout=5.0, return_when=FIRST_COMPLETED)
            for future in done:
                token = pending.pop(future)
                try:
                    results.append(future.result())
                except Exception as exc:
                    raise OrbLiteratureV2DevelopmentError(
                        f"opening snapshot group failed: {token}: {type(exc).__name__}: {exc}"
                    ) from exc
            now = time.monotonic()
            if done or now - last_print >= 30.0:
                reused = sum(bool(item["reused"]) for item in results)
                fresh = len(results) - reused
                rate = fresh / max((now - started) / 3600.0, 1e-9)
                print(
                    f"ORB v2 opening groups {len(results)}/{len(groups)}; reused={reused} fresh={fresh} "
                    f"active/queued={min(workers, len(pending))}/{max(0, len(pending)-workers)} "
                    f"new_rate={rate:.1f} groups/hour",
                    flush=True,
                )
                last_print = now
    return sorted(results, key=lambda item: str(item["group_token"]))


def _rank_selected_candidates(
    opening_artifacts: Sequence[Path],
    daily_features: Path,
    output_root: Path,
) -> tuple[Path, dict[str, int]]:
    if not opening_artifacts:
        raise OrbLiteratureV2DevelopmentError("no opening group artifacts exist")
    conn = duckdb.connect(":memory:")
    conn.execute(f"PRAGMA threads={max(1, min(8, os.cpu_count() or 1))}")
    opening_sql = f"read_parquet({_sql_paths(opening_artifacts)}, hive_partitioning=false)"
    daily_sql = f"read_parquet('{_sql_path(daily_features)}', hive_partitioning=false)"
    try:
        dup_opening = int(
            conn.execute(
                f"""
                SELECT count(*) FROM (
                    SELECT ticker, session_date, count(*) AS n
                    FROM {opening_sql}
                    GROUP BY ticker, session_date
                    HAVING count(*) <> 1
                )
                """
            ).fetchone()[0]
        )
        if dup_opening:
            raise OrbLiteratureV2DevelopmentError("opening snapshots contain duplicate ticker/session rows")
        dup_daily = int(
            conn.execute(
                f"""
                SELECT count(*) FROM (
                    SELECT ticker, session_date, count(*) AS n
                    FROM {daily_sql}
                    GROUP BY ticker, session_date
                    HAVING count(*) <> 1
                )
                """
            ).fetchone()[0]
        )
        if dup_daily:
            raise OrbLiteratureV2DevelopmentError("prior daily features contain duplicate ticker/session rows")

        selected_query = f"""
            WITH opening_history AS (
                SELECT o.*,
                       count(opening_five_minute_volume) OVER (
                           PARTITION BY ticker ORDER BY session_date
                           ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
                       ) AS prior_opening_count_14,
                       avg(opening_five_minute_volume) OVER (
                           PARTITION BY ticker ORDER BY session_date
                           ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
                       ) AS prior_average_opening_volume_14,
                       lag(session_ordinal, 14) OVER (
                           PARTITION BY ticker ORDER BY session_date
                       ) AS prior_14th_session_ordinal
                FROM {opening_sql} o
            ), joined AS (
                SELECT h.*, d.instrument_id,
                       d.prior_average_daily_share_volume_14,
                       d.prior_atr_14_dollars,
                       h.opening_five_minute_volume / NULLIF(h.prior_average_opening_volume_14, 0.0)
                           AS opening_relvol_14
                FROM opening_history h
                JOIN {daily_sql} d USING (ticker, session_date)
            ), eligible AS (
                SELECT *
                FROM joined
                WHERE prior_opening_count_14 = 14
                  AND session_ordinal - prior_14th_session_ordinal = 14
                  AND isfinite(opening_price) AND opening_price > 5.0
                  AND isfinite(prior_average_daily_share_volume_14)
                  AND prior_average_daily_share_volume_14 >= 1000000.0
                  AND isfinite(prior_atr_14_dollars) AND prior_atr_14_dollars > 0.50
                  AND isfinite(opening_relvol_14) AND opening_relvol_14 >= 1.0
            ), ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY session_date
                    ORDER BY opening_relvol_14 DESC, ticker ASC, instrument_id ASC
                )::INTEGER AS daily_relvol_rank
                FROM eligible
            )
            SELECT
                '{ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID}' AS policy_id,
                instrument_id, ticker, session_date, group_token, unit_id,
                opening_price, opening_close, opening_range_high, opening_range_low,
                opening_five_minute_volume, prior_average_opening_volume_14,
                opening_relvol_14, prior_average_daily_share_volume_14,
                prior_atr_14_dollars, daily_relvol_rank,
                opening_first_timestamp_utc, opening_last_timestamp_utc,
                CASE
                    WHEN abs(opening_close - opening_price) <= 1e-12 THEN 'DOJI_ABSTAIN'
                    WHEN opening_close > opening_price THEN 'LONG'
                    ELSE 'SHORT'
                END AS direction
            FROM ranked
            WHERE daily_relvol_rank <= 20
            ORDER BY session_date, daily_relvol_rank, ticker, instrument_id
        """
        target = output_root / "selected_candidates.parquet"
        temp = unique_temp_path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            conn.execute(
                f"COPY ({selected_query}) TO '{_sql_path(temp)}' "
                "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
            )
            with temp.open("rb+") as handle:
                os.fsync(handle.fileno())
            replace_with_retry(temp, target)
        finally:
            temp.unlink(missing_ok=True)
        counts = conn.execute(
            f"""
            SELECT count(*) AS selected,
                   count(DISTINCT session_date) AS sessions,
                   count(*) FILTER (WHERE direction='DOJI_ABSTAIN') AS doji,
                   count(*) FILTER (WHERE direction='LONG') AS long_count,
                   count(*) FILTER (WHERE direction='SHORT') AS short_count
            FROM read_parquet('{_sql_path(target)}')
            """
        ).fetchone()
        opening_count = int(conn.execute(f"SELECT count(*) FROM {opening_sql}").fetchone()[0])
        eligible_count = int(
            conn.execute(
                f"""
                WITH opening_history AS (
                    SELECT o.*,
                           count(opening_five_minute_volume) OVER (
                               PARTITION BY ticker ORDER BY session_date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
                           ) AS prior_count,
                           avg(opening_five_minute_volume) OVER (
                               PARTITION BY ticker ORDER BY session_date ROWS BETWEEN 14 PRECEDING AND 1 PRECEDING
                           ) AS prior_avg,
                           lag(session_ordinal, 14) OVER (
                               PARTITION BY ticker ORDER BY session_date
                           ) AS prior_14th_session_ordinal
                    FROM {opening_sql} o
                )
                SELECT count(*)
                FROM opening_history h JOIN {daily_sql} d USING(ticker, session_date)
                WHERE prior_count=14
                  AND session_ordinal - prior_14th_session_ordinal = 14
                  AND opening_price>5.0
                  AND d.prior_average_daily_share_volume_14>=1000000.0
                  AND d.prior_atr_14_dollars>0.50
                  AND h.opening_five_minute_volume / NULLIF(prior_avg,0.0) >= 1.0
                """
            ).fetchone()[0]
        )
    finally:
        conn.close()
    assert counts is not None
    return target, {
        "opening_snapshot_rows": opening_count,
        "eligible_rank_pool_rows": eligible_count,
        "selected_top20_rows": int(counts[0]),
        "selected_sessions": int(counts[1]),
        "doji_abstentions": int(counts[2]),
        "long_candidates": int(counts[3]),
        "short_candidates": int(counts[4]),
    }


def _directional_return(direction: str, entry: float, exit_price: float) -> float:
    if direction == "LONG":
        return exit_price / entry - 1.0
    if direction == "SHORT":
        return 1.0 - exit_price / entry
    raise OrbLiteratureV2DevelopmentError(f"unsupported direction: {direction}")


def _net_return(direction: str, entry: float, exit_price: float, cost_bps: float) -> float:
    half = float(cost_bps) / 20_000.0
    if direction == "LONG":
        return (exit_price * (1.0 - half) - entry * (1.0 + half)) / entry
    if direction == "SHORT":
        return (entry * (1.0 - half) - exit_price * (1.0 + half)) / entry
    raise OrbLiteratureV2DevelopmentError(f"unsupported direction: {direction}")


def _minutes_between(start: pd.Timestamp, end: pd.Timestamp) -> float:
    return float((end - start).total_seconds() / 60.0)


def _case_id(candidate: pd.Series) -> str:
    return _stable_hash(
        {
            "policy_id": ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
            "instrument_id": str(candidate["instrument_id"]),
            "ticker": str(candidate["ticker"]),
            "session_date": str(candidate["session_date"]),
            "rank": int(candidate["daily_relvol_rank"]),
        }
    )


def evaluate_selected_case(candidate: pd.Series, bars: pd.DataFrame) -> tuple[dict[str, object], list[dict[str, object]]]:
    direction = str(candidate["direction"])
    if direction not in {"LONG", "SHORT"}:
        raise OrbLiteratureV2DevelopmentError("selected full-path case must be directional")
    if bars.empty:
        raise OrbLiteratureV2DevelopmentError("selected full-path case has no regular bars")
    frame = bars.sort_values("timestamp_utc", kind="stable").copy()
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    decision_time = pd.Timestamp(candidate["opening_last_timestamp_utc"])
    if decision_time.tzinfo is None:
        decision_time = decision_time.tz_localize("UTC")
    decision_time = decision_time.tz_convert("UTC") + pd.Timedelta(minutes=1)
    post = frame.loc[frame["timestamp_utc"] >= decision_time].reset_index(drop=True)
    case_id = _case_id(candidate)
    base: dict[str, object] = {
        "case_id": case_id,
        "policy_id": ORB_STOCKS_IN_PLAY_LITERATURE_V2_POLICY_ID,
        "instrument_id": str(candidate["instrument_id"]),
        "ticker": str(candidate["ticker"]),
        "session_date": str(candidate["session_date"]),
        "direction": direction,
        "daily_relvol_rank": int(candidate["daily_relvol_rank"]),
        "opening_relvol_14": float(candidate["opening_relvol_14"]),
        "prior_average_daily_share_volume_14": float(candidate["prior_average_daily_share_volume_14"]),
        "prior_atr_14_dollars": float(candidate["prior_atr_14_dollars"]),
        "opening_price": float(candidate["opening_price"]),
        "opening_close": float(candidate["opening_close"]),
        "opening_range_high": float(candidate["opening_range_high"]),
        "opening_range_low": float(candidate["opening_range_low"]),
        "entry_stop_price": None,
        "entry_price": None,
        "entry_timestamp_utc": None,
        "entry_fill_reason": None,
        "stop_loss_price": None,
        "exit_price": None,
        "exit_timestamp_utc": None,
        "exit_reason": None,
        "holding_minutes": None,
        "gross_return": None,
        "net_return_0": None,
        "net_return_10": None,
        "net_return_25": None,
        "net_return_50": None,
        "net_return_100": None,
        "primary_net_return": None,
        "stress_net_return": None,
        "path_mfe": None,
        "path_adverse": None,
        "entry_bar_extremes_excluded": True,
        "exit_bar_extremes_excluded": True,
        "terminal_exit_return_included": True,
    }
    if post.empty:
        return {**base, "status": "NO_ENTRY", "comparable": False}, []

    entry_stop = float(candidate["opening_range_high"] if direction == "LONG" else candidate["opening_range_low"])
    entry_index: int | None = None
    entry_price: float | None = None
    entry_reason: str | None = None
    for index, row in post.iterrows():
        bar_open = float(row["open"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])
        if direction == "LONG":
            if bar_open >= entry_stop:
                entry_index, entry_price, entry_reason = index, bar_open, "GAP_THROUGH_STOP_AT_BAR_OPEN"
                break
            if bar_high >= entry_stop:
                entry_index, entry_price, entry_reason = index, entry_stop, "STOP_CROSS_AT_STOP_PRICE"
                break
        else:
            if bar_open <= entry_stop:
                entry_index, entry_price, entry_reason = index, bar_open, "GAP_THROUGH_STOP_AT_BAR_OPEN"
                break
            if bar_low <= entry_stop:
                entry_index, entry_price, entry_reason = index, entry_stop, "STOP_CROSS_AT_STOP_PRICE"
                break
    if entry_index is None or entry_price is None or entry_reason is None:
        return {**base, "status": "NO_ENTRY", "comparable": False}, []

    entry_row = post.iloc[entry_index]
    entry_time = pd.Timestamp(entry_row["timestamp_utc"])
    stop_distance = 0.10 * float(candidate["prior_atr_14_dollars"])
    stop_price = entry_price - stop_distance if direction == "LONG" else entry_price + stop_distance
    same_minute_stop = (
        float(entry_row["low"]) <= stop_price if direction == "LONG" else float(entry_row["high"]) >= stop_price
    )
    if same_minute_stop:
        return {
            **base,
            "status": "ENTRY_STOP_SAME_MINUTE_UNORDERED",
            "comparable": False,
            "entry_stop_price": entry_stop,
            "entry_price": entry_price,
            "entry_timestamp_utc": entry_time.isoformat(),
            "entry_fill_reason": entry_reason,
            "stop_loss_price": stop_price,
        }, []

    after_entry = post.iloc[entry_index + 1 :].reset_index(drop=True)
    exit_index: int | None = None
    exit_price: float | None = None
    exit_reason: str | None = None
    for index, row in after_entry.iterrows():
        bar_open = float(row["open"])
        bar_high = float(row["high"])
        bar_low = float(row["low"])
        if direction == "LONG":
            if bar_open <= stop_price:
                exit_index, exit_price, exit_reason = index, bar_open, "STOP_GAP_THROUGH_AT_BAR_OPEN"
                break
            if bar_low <= stop_price:
                exit_index, exit_price, exit_reason = index, stop_price, "STOP_CROSS_AT_STOP_PRICE"
                break
        else:
            if bar_open >= stop_price:
                exit_index, exit_price, exit_reason = index, bar_open, "STOP_GAP_THROUGH_AT_BAR_OPEN"
                break
            if bar_high >= stop_price:
                exit_index, exit_price, exit_reason = index, stop_price, "STOP_CROSS_AT_STOP_PRICE"
                break

    if exit_index is None:
        exit_row = frame.iloc[-1]
        exit_time = pd.Timestamp(exit_row["timestamp_utc"])
        if exit_time < entry_time:
            raise OrbLiteratureV2DevelopmentError("EOD exit precedes selected entry")
        exit_price = float(exit_row["close"])
        exit_reason = "EOD_LAST_REGULAR_BAR_CLOSE"
        interior = frame.loc[
            (frame["timestamp_utc"] > entry_time) & (frame["timestamp_utc"] < exit_time)
        ].copy()
    else:
        exit_row = after_entry.iloc[exit_index]
        exit_time = pd.Timestamp(exit_row["timestamp_utc"])
        interior = after_entry.iloc[:exit_index].copy()
    assert exit_price is not None and exit_reason is not None

    gross = _directional_return(direction, entry_price, exit_price)
    favorable_values = [0.0, gross]
    adverse_values = [0.0, -gross]
    for _, row in interior.iterrows():
        if direction == "LONG":
            favorable_values.append(float(row["high"]) / entry_price - 1.0)
            adverse_values.append(1.0 - float(row["low"]) / entry_price)
        else:
            favorable_values.append(1.0 - float(row["low"]) / entry_price)
            adverse_values.append(float(row["high"]) / entry_price - 1.0)
    path_mfe = max(favorable_values)
    path_adverse = max(adverse_values)

    first_fav: dict[float, float | None] = {threshold: None for threshold in MOVE_THRESHOLDS}
    first_adv: dict[float, float | None] = {threshold: None for threshold in MOVE_THRESHOLDS}
    for _, row in interior.iterrows():
        stamp = pd.Timestamp(row["timestamp_utc"])
        minutes = _minutes_between(entry_time, stamp)
        if direction == "LONG":
            fav = float(row["high"]) / entry_price - 1.0
            adv = 1.0 - float(row["low"]) / entry_price
        else:
            fav = 1.0 - float(row["low"]) / entry_price
            adv = float(row["high"]) / entry_price - 1.0
        for threshold in MOVE_THRESHOLDS:
            if first_fav[threshold] is None and fav >= threshold:
                first_fav[threshold] = minutes
            if first_adv[threshold] is None and adv >= threshold:
                first_adv[threshold] = minutes
    terminal_minutes = _minutes_between(entry_time, exit_time)
    for threshold in MOVE_THRESHOLDS:
        if gross >= threshold and first_fav[threshold] is None:
            first_fav[threshold] = terminal_minutes
        if gross <= -threshold and first_adv[threshold] is None:
            first_adv[threshold] = terminal_minutes

    nets = {str(cost): _net_return(direction, entry_price, exit_price, cost) for cost in COST_GRID_BPS}
    outcome = {
        **base,
        "status": "COMPARABLE",
        "comparable": True,
        "entry_stop_price": entry_stop,
        "entry_price": entry_price,
        "entry_timestamp_utc": entry_time.isoformat(),
        "entry_fill_reason": entry_reason,
        "stop_loss_price": stop_price,
        "exit_price": exit_price,
        "exit_timestamp_utc": exit_time.isoformat(),
        "exit_reason": exit_reason,
        "holding_minutes": terminal_minutes,
        "gross_return": gross,
        "net_return_0": nets["0"],
        "net_return_10": nets["10"],
        "net_return_25": nets["25"],
        "net_return_50": nets["50"],
        "net_return_100": nets["100"],
        "primary_net_return": nets[str(PRIMARY_COST_BPS)],
        "stress_net_return": nets[str(STRESS_COST_BPS)],
        "path_mfe": path_mfe,
        "path_adverse": path_adverse,
        "entry_bar_extremes_excluded": True,
        "exit_bar_extremes_excluded": True,
        "terminal_exit_return_included": True,
    }
    threshold_rows: list[dict[str, object]] = []
    for threshold in MOVE_THRESHOLDS:
        fav = first_fav[threshold]
        adv = first_adv[threshold]
        if fav is None and adv is None:
            touch_class = "NEITHER"
        elif fav is not None and adv is None:
            touch_class = "FAVORABLE_ONLY"
        elif fav is None and adv is not None:
            touch_class = "ADVERSE_ONLY"
        elif math.isclose(float(fav), float(adv), rel_tol=0.0, abs_tol=1e-12):
            touch_class = "SAME_MINUTE_COLLISION_UNORDERED"
        elif float(fav) < float(adv):
            touch_class = "FAVORABLE_FIRST"
        else:
            touch_class = "ADVERSE_FIRST"
        threshold_rows.append(
            {
                "case_id": case_id,
                "ticker": str(candidate["ticker"]),
                "session_date": str(candidate["session_date"]),
                "direction": direction,
                "move_threshold": threshold,
                "first_favorable_minutes": fav,
                "first_adverse_minutes": adv,
                "first_touch_class": touch_class,
            }
        )
    return outcome, threshold_rows


def _path_group_worker(
    project_root_text: str,
    output_root_text: str,
    group_token: str,
    units: tuple[B35DevelopmentUnitBinding, ...],
    candidate_records: list[dict[str, object]],
) -> dict[str, object]:
    project_root = Path(project_root_text).resolve()
    output_root = Path(output_root_text).resolve()
    artifact = output_root / "path_groups" / f"{group_token}.parquet"
    thresholds_artifact = output_root / "path_groups" / f"{group_token}.thresholds.parquet"
    binding_fp = _group_binding_fingerprint(units)
    settings = load_settings(project_root)
    source = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
    candidates = pd.DataFrame(candidate_records)
    selected_unit_ids = set(candidates["unit_id"].astype(str))
    unit_by_id = {unit.unit_id: unit for unit in units}
    missing_units = sorted(selected_unit_ids.difference(unit_by_id))
    if missing_units:
        source.close()
        raise OrbLiteratureV2DevelopmentError(
            f"selected candidates reference units outside group {group_token}: {missing_units[:3]}"
        )
    selected_units = tuple(unit_by_id[unit_id] for unit_id in sorted(selected_unit_ids))
    selected_binding_fp = _group_binding_fingerprint(selected_units)
    path_binding = _stable_hash(
        {
            "group_binding": binding_fp,
            "selected_binding": selected_binding_fp,
            "candidate_identity": [
                [str(row["instrument_id"]), str(row["ticker"]), str(row["session_date"]), int(row["daily_relvol_rank"])]
                for row in candidate_records
            ],
        }
    )
    try:
        reusable = _reusable_group_artifact(
            artifact,
            phase=PATH_PHASE,
            group_token=group_token,
            group_binding_fingerprint=path_binding,
        )
        threshold_receipt = _reusable_group_artifact(
            thresholds_artifact,
            phase=PATH_PHASE + "_THRESHOLDS",
            group_token=group_token,
            group_binding_fingerprint=path_binding,
        )
        if reusable is not None and threshold_receipt is not None:
            for unit in selected_units:
                source.verify_unit(unit)
            return {
                "group_token": group_token,
                "artifact": str(artifact),
                "thresholds_artifact": str(thresholds_artifact),
                "row_count": int(reusable["row_count"]),
                "threshold_row_count": int(threshold_receipt["row_count"]),
                "reused": True,
            }

        conn = duckdb.connect(":memory:")
        conn.execute("SET TimeZone='UTC'")
        conn.execute("PRAGMA threads=1")
        bar_pieces: list[pd.DataFrame] = []
        try:
            for unit in selected_units:
                source.verify_unit(unit)
                unit_candidates = candidates.loc[candidates["unit_id"].astype(str) == unit.unit_id, ["ticker", "session_date"]].copy()
                if unit_candidates.empty:
                    continue
                unit_candidates["session_date"] = pd.to_datetime(unit_candidates["session_date"], errors="raise").dt.date
                conn.register("orb_selected_keys", unit_candidates.drop_duplicates())
                try:
                    part = conn.execute(
                        """
                        SELECT p.symbol AS ticker, p.session_date, p.timestamp_utc,
                               CAST(p.open AS DOUBLE) AS open,
                               CAST(p.high AS DOUBLE) AS high,
                               CAST(p.low AS DOUBLE) AS low,
                               CAST(p.close AS DOUBLE) AS close,
                               CAST(p.volume AS DOUBLE) AS volume
                        FROM read_parquet(?, hive_partitioning=false) p
                        JOIN orb_selected_keys k
                          ON p.symbol = k.ticker AND p.session_date = k.session_date
                        WHERE p.session_segment='regular'
                        ORDER BY p.symbol, p.session_date, p.timestamp_utc
                        """,
                        [str(unit.canonical_path)],
                    ).fetchdf()
                finally:
                    conn.unregister("orb_selected_keys")
                if not part.empty:
                    bar_pieces.append(part)
            all_bars = pd.concat(bar_pieces, ignore_index=True) if bar_pieces else pd.DataFrame()
            grouped_bars = {
                (str(ticker), pd.Timestamp(session).date()): frame
                for (ticker, session), frame in all_bars.groupby(["ticker", "session_date"], sort=False)
            } if not all_bars.empty else {}
            outcome_rows: list[dict[str, object]] = []
            threshold_rows: list[dict[str, object]] = []
            for _, candidate in candidates.sort_values(["session_date", "daily_relvol_rank", "ticker"], kind="stable").iterrows():
                key = (str(candidate["ticker"]), pd.Timestamp(candidate["session_date"]).date())
                frame = grouped_bars.get(key)
                if frame is None:
                    raise OrbLiteratureV2DevelopmentError(f"selected candidate has no full-session rows: {key}")
                outcome, thresholds = evaluate_selected_case(candidate, frame)
                outcome_rows.append(outcome)
                threshold_rows.extend(thresholds)
            outcome_frame = pd.DataFrame(outcome_rows)
            threshold_frame = pd.DataFrame(
                threshold_rows,
                columns=[
                    "case_id",
                    "ticker",
                    "session_date",
                    "direction",
                    "move_threshold",
                    "first_favorable_minutes",
                    "first_adverse_minutes",
                    "first_touch_class",
                ],
            )
            row_count = _write_frame_atomic(
                conn,
                outcome_frame,
                artifact,
                order_by="session_date, ticker, instrument_id",
            )
            threshold_count = _write_frame_atomic(
                conn,
                threshold_frame,
                thresholds_artifact,
                order_by="session_date, ticker, move_threshold",
            )
        finally:
            conn.close()
    finally:
        source.close()
    _publish_group_receipt(
        artifact,
        phase=PATH_PHASE,
        group_token=group_token,
        group_binding_fingerprint=path_binding,
        row_count=row_count,
    )
    _publish_group_receipt(
        thresholds_artifact,
        phase=PATH_PHASE + "_THRESHOLDS",
        group_token=group_token,
        group_binding_fingerprint=path_binding,
        row_count=threshold_count,
    )
    return {
        "group_token": group_token,
        "artifact": str(artifact),
        "thresholds_artifact": str(thresholds_artifact),
        "row_count": row_count,
        "threshold_row_count": threshold_count,
        "reused": False,
    }


def _run_path_groups(
    project_root: Path,
    output_root: Path,
    groups: dict[str, tuple[B35DevelopmentUnitBinding, ...]],
    selected_candidates: Path,
    *,
    workers: int,
) -> list[dict[str, object]]:
    candidate_conn = duckdb.connect(":memory:")
    try:
        candidates = candidate_conn.execute(
            f"SELECT * FROM read_parquet('{_sql_path(selected_candidates)}') "
            "WHERE direction IN ('LONG','SHORT')"
        ).fetchdf()
    finally:
        candidate_conn.close()
    if candidates.empty:
        return []
    candidates["session_date"] = pd.to_datetime(candidates["session_date"], errors="raise").dt.date
    pending = {}
    results: list[dict[str, object]] = []
    started = time.monotonic()
    last_print = started
    with ProcessPoolExecutor(max_workers=workers) as executor:
        for group_token, frame in candidates.groupby("group_token", sort=True):
            token = str(group_token)
            units = groups.get(token)
            if units is None:
                raise OrbLiteratureV2DevelopmentError(f"selected candidate group is unknown: {token}")
            records = frame.sort_values(["session_date", "daily_relvol_rank", "ticker"], kind="stable").to_dict(orient="records")
            future = executor.submit(
                _path_group_worker,
                str(project_root),
                str(output_root),
                token,
                units,
                records,
            )
            pending[future] = token
        total = len(pending)
        while pending:
            done, _ = wait(tuple(pending), timeout=5.0, return_when=FIRST_COMPLETED)
            for future in done:
                token = pending.pop(future)
                try:
                    results.append(future.result())
                except Exception as exc:
                    raise OrbLiteratureV2DevelopmentError(
                        f"selected path group failed: {token}: {type(exc).__name__}: {exc}"
                    ) from exc
            now = time.monotonic()
            if done or now - last_print >= 30.0:
                reused = sum(bool(item["reused"]) for item in results)
                fresh = len(results) - reused
                rate = fresh / max((now - started) / 3600.0, 1e-9)
                print(
                    f"ORB v2 selected paths {len(results)}/{total}; reused={reused} fresh={fresh} "
                    f"active/queued={min(workers, len(pending))}/{max(0, len(pending)-workers)} "
                    f"new_rate={rate:.1f} groups/hour",
                    flush=True,
                )
                last_print = now
    return sorted(results, key=lambda item: str(item["group_token"]))


def _summary(
    path_artifacts: Sequence[Path],
    threshold_artifacts: Sequence[Path],
) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    if not path_artifacts:
        return (
            {"directional_candidates": 0, "entered": 0, "comparable": 0},
            [],
            [],
            [],
        )
    conn = duckdb.connect(":memory:")
    path_sql = f"read_parquet({_sql_paths(path_artifacts)}, hive_partitioning=false, union_by_name=true)"
    try:
        totals_result = conn.execute(
            f"""
            SELECT count(*) AS directional_candidates,
                   count(*) FILTER (WHERE status <> 'NO_ENTRY') AS entered,
                   count(*) FILTER (WHERE status='NO_ENTRY') AS no_entry,
                   count(*) FILTER (WHERE status='ENTRY_STOP_SAME_MINUTE_UNORDERED') AS same_minute_unordered,
                   count(*) FILTER (WHERE comparable) AS comparable,
                   avg(gross_return) FILTER (WHERE comparable) AS mean_gross_return,
                   avg(primary_net_return) FILTER (WHERE comparable) AS mean_primary_net_return,
                   avg(stress_net_return) FILTER (WHERE comparable) AS mean_stress_net_return,
                   avg(path_mfe) FILTER (WHERE comparable) AS mean_path_mfe,
                   avg(path_adverse) FILTER (WHERE comparable) AS mean_path_adverse
            FROM {path_sql}
            """
        )
        total_columns = [item[0] for item in totals_result.description]
        totals = dict(zip(total_columns, totals_result.fetchone(), strict=True))
        route_result = conn.execute(
            f"""
            SELECT direction,
                   count(*) AS directional_candidates,
                   count(*) FILTER (WHERE comparable) AS comparable,
                   avg(gross_return) FILTER (WHERE comparable) AS mean_gross_return,
                   avg(net_return_10) FILTER (WHERE comparable) AS mean_net_return_10,
                   avg(net_return_25) FILTER (WHERE comparable) AS mean_net_return_25,
                   avg(net_return_50) FILTER (WHERE comparable) AS mean_net_return_50,
                   avg(net_return_100) FILTER (WHERE comparable) AS mean_net_return_100,
                   avg(path_mfe) FILTER (WHERE comparable) AS mean_path_mfe,
                   avg(path_adverse) FILTER (WHERE comparable) AS mean_path_adverse,
                   median(holding_minutes) FILTER (WHERE comparable) AS median_holding_minutes
            FROM {path_sql}
            GROUP BY direction ORDER BY direction
            """
        )
        route_columns = [item[0] for item in route_result.description]
        routes = [dict(zip(route_columns, row, strict=True)) for row in route_result.fetchall()]
        year_result = conn.execute(
            f"""
            SELECT year(CAST(session_date AS DATE))::INTEGER AS calendar_year, direction,
                   count(*) FILTER (WHERE comparable) AS comparable,
                   avg(primary_net_return) FILTER (WHERE comparable) AS mean_primary_net_return,
                   avg(stress_net_return) FILTER (WHERE comparable) AS mean_stress_net_return
            FROM {path_sql}
            GROUP BY calendar_year, direction
            ORDER BY calendar_year, direction
            """
        )
        year_columns = [item[0] for item in year_result.description]
        years = [dict(zip(year_columns, row, strict=True)) for row in year_result.fetchall()]
        thresholds: list[dict[str, object]] = []
        if threshold_artifacts:
            threshold_sql = f"read_parquet({_sql_paths(threshold_artifacts)}, hive_partitioning=false, union_by_name=true)"
            threshold_row_count = int(conn.execute(f"SELECT count(*) FROM {threshold_sql}").fetchone()[0])
            if threshold_row_count:
                threshold_result = conn.execute(
                f"""
                SELECT direction, move_threshold, count(*) AS comparable,
                       avg(CASE WHEN first_favorable_minutes IS NOT NULL THEN 1.0 ELSE 0.0 END) AS favorable_hit_rate,
                       avg(CASE WHEN first_adverse_minutes IS NOT NULL THEN 1.0 ELSE 0.0 END) AS adverse_hit_rate,
                       avg(CASE WHEN first_touch_class IN ('FAVORABLE_ONLY','FAVORABLE_FIRST') THEN 1.0 ELSE 0.0 END)
                           AS favorable_before_adverse_rate,
                       avg(CASE WHEN first_touch_class IN ('ADVERSE_ONLY','ADVERSE_FIRST') THEN 1.0 ELSE 0.0 END)
                           AS adverse_before_favorable_rate,
                       avg(CASE WHEN first_touch_class='SAME_MINUTE_COLLISION_UNORDERED' THEN 1.0 ELSE 0.0 END)
                           AS same_minute_collision_rate,
                       median(first_favorable_minutes) FILTER (WHERE first_favorable_minutes IS NOT NULL)
                           AS median_first_favorable_minutes,
                       median(first_adverse_minutes) FILTER (WHERE first_adverse_minutes IS NOT NULL)
                           AS median_first_adverse_minutes
                FROM {threshold_sql}
                GROUP BY direction, move_threshold
                ORDER BY direction, move_threshold
                """
            )
                threshold_columns = [item[0] for item in threshold_result.description]
                thresholds = [
                    dict(zip(threshold_columns, row, strict=True))
                    for row in threshold_result.fetchall()
                ]
    finally:
        conn.close()
    return totals, routes, years, thresholds


def run_orb_stocks_in_play_literature_v2_development(project_root: Path) -> dict[str, object]:
    project = Path(project_root).resolve()
    output_root = analysis_root(project)
    output_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()

    preflight = validate_accepted_successor_preflight(project)
    _write_json(
        output_root / "development_contract.json",
        {
            "contract": development_contract_payload(),
            "fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
        },
    )
    profile = resolve_successor_research_execution_profile()
    _write_json(output_root / "execution_profile.json", profile.as_dict())

    settings = load_settings(project)
    source = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
    try:
        plan = source.plan(DEVELOPMENT_START, DEVELOPMENT_END)
    finally:
        source.close()
    raw_groups = minute_symbol_groups(plan.units)
    groups: list[tuple[str, tuple[B35DevelopmentUnitBinding, ...]]] = []
    token_seen: set[str] = set()
    for symbols, units in raw_groups:
        token = _group_token(symbols)
        if token in token_seen:
            raise OrbLiteratureV2DevelopmentError("minute group token collision")
        token_seen.add(token)
        groups.append((token, tuple(units)))
    if len(groups) != 482:
        raise OrbLiteratureV2DevelopmentError(f"expected 482 accepted minute groups, got {len(groups)}")

    print(
        "ORB literature v2 DEVELOPMENT authority: diagnostic only; master/future/provider/broker/"
        "PAPER/LIVE/promotion/confluence/option authority forbidden",
        flush=True,
    )
    print(
        f"execution profile: workers={profile.workers} x DuckDB={profile.duckdb_threads_per_worker}; "
        f"groups={len(groups)} units={len(plan.units):,}",
        flush=True,
    )

    daily_features, daily_receipt, daily_reused = _prepare_daily_feature_artifact(project, output_root)
    print(
        f"prior daily PIT features: rows={int(daily_receipt['row_count']):,} reused={daily_reused}",
        flush=True,
    )

    opening_results = _run_opening_groups(
        project,
        output_root,
        groups,
        workers=profile.workers,
    )
    opening_artifacts = tuple(Path(str(item["artifact"])) for item in opening_results)
    selected_candidates, rank_counts = _rank_selected_candidates(
        opening_artifacts,
        daily_features,
        output_root,
    )
    print(
        f"opening snapshots={rank_counts['opening_snapshot_rows']:,}; eligible rank pool="
        f"{rank_counts['eligible_rank_pool_rows']:,}; top20={rank_counts['selected_top20_rows']:,}; "
        f"doji={rank_counts['doji_abstentions']:,}",
        flush=True,
    )

    group_map = {token: units for token, units in groups}
    path_results = _run_path_groups(
        project,
        output_root,
        group_map,
        selected_candidates,
        workers=profile.workers,
    )
    path_artifacts = tuple(Path(str(item["artifact"])) for item in path_results)
    threshold_artifacts = tuple(Path(str(item["thresholds_artifact"])) for item in path_results)
    totals, direction_summary, year_summary, threshold_summary = _summary(
        path_artifacts,
        threshold_artifacts,
    )

    scientific_payload = {
        "analysis_contract": ANALYSIS_CONTRACT,
        "development_contract_id": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_CONTRACT_ID,
        "development_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_DEVELOPMENT_FINGERPRINT,
        "strategy_contract_fingerprint": ORB_STOCKS_IN_PLAY_LITERATURE_V2_CONTRACT_FINGERPRINT,
        "accepted_successor_preflight": preflight.scientific_payload(),
        "native_plan_sha256": plan.native_plan_sha256,
        "native_plan_file_sha256": plan.native_plan_file_sha256,
        "daily_feature_sha256": _sha256_file(daily_features),
        "opening_group_artifact_sha256": [
            [str(item["group_token"]), _sha256_file(Path(str(item["artifact"])))]
            for item in opening_results
        ],
        "selected_candidates_sha256": _sha256_file(selected_candidates),
        "path_group_artifact_sha256": [
            [str(item["group_token"]), _sha256_file(Path(str(item["artifact"]))) ]
            for item in path_results
        ],
        "path_threshold_artifact_sha256": [
            [str(item["group_token"]), _sha256_file(Path(str(item["thresholds_artifact"]))) ]
            for item in path_results
        ],
        "rank_counts": rank_counts,
        "totals": totals,
        "direction_summary": direction_summary,
        "year_summary": year_summary,
        "threshold_summary": threshold_summary,
        "cost_grid_bps": list(COST_GRID_BPS),
        "primary_cost_bps": PRIMARY_COST_BPS,
        "stress_cost_bps": STRESS_COST_BPS,
        "historical_option_pnl_claimed": False,
        "consumed_master_reads": 0,
        "future_blind_reads": 0,
        "provider_reads": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "paper_authority": False,
        "live_authority": False,
        "promotion_authority": False,
        "confluence_authority": False,
        "option_trading_authority": False,
    }
    analysis_fingerprint = _stable_hash(scientific_payload)
    report: dict[str, object] = {
        **scientific_payload,
        "status": "COMPLETE_DEVELOPMENT_DIAGNOSTIC",
        "analysis_fingerprint": analysis_fingerprint,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "elapsed_seconds": time.monotonic() - started,
        "execution_profile": profile.as_dict(),
        "opening_groups_reused": sum(bool(item["reused"]) for item in opening_results),
        "opening_groups_fresh": sum(not bool(item["reused"]) for item in opening_results),
        "path_groups_reused": sum(bool(item["reused"]) for item in path_results),
        "path_groups_fresh": sum(not bool(item["reused"]) for item in path_results),
        "scientific_identity_excludes_runtime_worker_count": True,
        "development_cannot_self_validate_or_promote": True,
    }
    _write_json(output_root / "summary.json", report)
    return report
