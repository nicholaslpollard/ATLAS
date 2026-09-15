from __future__ import annotations

import hashlib
import json
import math
import os
import time
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from packages.backtesting.reference_v2_lake_adapter import ReferenceV2DailyLakeAdapter
from packages.backtesting.successor_optionworthiness_analysis import (
    conditioning_root,
    optionworthiness_root,
    validate_conditioning_inputs,
)
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import load_settings
from packages.strategies.successor_conditioning_contract import DEVELOPMENT_END, DEVELOPMENT_START
from packages.strategies.successor_path_kinetics_contract import (
    ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
    ACCEPTED_SELECTED_COMPARABLE_TOTAL,
    ACCEPTED_SELECTED_DAILY_COMPARABLE,
    ACCEPTED_SELECTED_INTRADAY_COMPARABLE,
    AUTHORITY,
    MOVE_THRESHOLDS,
    SESSION_HORIZONS,
    SUCCESSOR_PATH_KINETICS_CONTRACT,
    SUCCESSOR_PATH_KINETICS_FINGERPRINT,
    successor_path_kinetics_manifest,
)


SUCCESSOR_PATH_KINETICS_ANALYSIS_CONTRACT = (
    "atlas-successor-path-kinetics-analysis-v1-selected-daily-development-day-resolution"
)


class SuccessorPathKineticsError(RuntimeError):
    pass


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


def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> dict[str, object]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = unique_temp_path(path)
    con = duckdb.connect()
    try:
        con.register("artifact_frame", frame)
        con.execute(
            f"COPY artifact_frame TO '{_sql_path(temp)}' "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        con.unregister("artifact_frame")
        with temp.open("rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(temp, path)
    finally:
        try:
            con.unregister("artifact_frame")
        except duckdb.Error:
            pass
        con.close()
        temp.unlink(missing_ok=True)
    return {
        "path": str(path.resolve()),
        "sha256": _sha256_file(path),
        "row_count": int(len(frame)),
    }


def path_kinetics_root(project_root: Path) -> Path:
    return (
        optionworthiness_root(project_root)
        / "path_kinetics_v1"
        / SUCCESSOR_PATH_KINETICS_FINGERPRINT[:16]
    ).resolve()


def _read_json(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorPathKineticsError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(payload, dict):
        raise SuccessorPathKineticsError(f"JSON artifact is not an object: {path}")
    return payload


def _validate_optionworthiness_summary(project_root: Path) -> dict[str, object]:
    root = optionworthiness_root(project_root)
    summary_path = root / "analysis_summary.json"
    if not summary_path.is_file():
        raise SuccessorPathKineticsError(
            "accepted option-worthiness summary is missing; run the accepted option-worthiness package first"
        )
    summary = _read_json(summary_path)
    if summary.get("status") != "COMPLETE_OPTIONWORTHINESS_DIAGNOSTICS_ONLY":
        raise SuccessorPathKineticsError("option-worthiness diagnostics are not complete")
    if summary.get("analysis_fingerprint") != ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT:
        raise SuccessorPathKineticsError("option-worthiness analysis fingerprint is not the accepted result")
    if summary.get("raw_market_data_reread") is not False:
        raise SuccessorPathKineticsError("accepted option-worthiness summary unexpectedly reread raw market data")
    if summary.get("historical_option_data_read") is not False:
        raise SuccessorPathKineticsError("accepted option-worthiness summary unexpectedly read option history")
    if summary.get("confluence_opened") is not False:
        raise SuccessorPathKineticsError("accepted option-worthiness summary unexpectedly opened confluence")
    for key in (
        "consumed_master_rows_read",
        "future_blind_rows_read",
        "provider_calls",
        "broker_reads",
        "broker_writes",
    ):
        if int(summary.get(key, -1)) != 0:
            raise SuccessorPathKineticsError(f"accepted option-worthiness authority drifted: {key}")
    counts = summary.get("scope_counts")
    if not isinstance(counts, dict):
        raise SuccessorPathKineticsError("option-worthiness scope counts are missing")
    if int(counts.get("walk_forward_selected_comparable", -1)) != ACCEPTED_SELECTED_COMPARABLE_TOTAL:
        raise SuccessorPathKineticsError("option-worthiness selected-comparable count drifted")
    return {
        "summary_path": str(summary_path.resolve()),
        "summary_sha256": _sha256_file(summary_path),
        "analysis_fingerprint": str(summary["analysis_fingerprint"]),
        "output_artifact_set_fingerprint": str(summary.get("output_artifact_set_fingerprint") or ""),
    }


def _selected_daily_frame(project_root: Path) -> tuple[pd.DataFrame, dict[str, object]]:
    root = conditioning_root(project_root)
    path = root / "eligibility_assignments.parquet"
    if not path.is_file():
        raise SuccessorPathKineticsError(f"conditioning eligibility assignments are missing: {path}")
    con = duckdb.connect()
    try:
        total, daily, intraday = con.execute(
            f"""
            SELECT
                count(*) FILTER (WHERE research_eligible AND comparable),
                count(*) FILTER (WHERE research_eligible AND comparable AND native_timeframe='1d'),
                count(*) FILTER (WHERE research_eligible AND comparable AND native_timeframe='1m')
            FROM read_parquet('{_sql_path(path)}')
            """
        ).fetchone()
        if int(total) != ACCEPTED_SELECTED_COMPARABLE_TOTAL:
            raise SuccessorPathKineticsError(
                f"selected comparable count drifted: {int(total)} != {ACCEPTED_SELECTED_COMPARABLE_TOTAL}"
            )
        if int(daily) != ACCEPTED_SELECTED_DAILY_COMPARABLE:
            raise SuccessorPathKineticsError(
                f"selected daily comparable count drifted: {int(daily)} != {ACCEPTED_SELECTED_DAILY_COMPARABLE}"
            )
        if int(intraday) != ACCEPTED_SELECTED_INTRADAY_COMPARABLE:
            raise SuccessorPathKineticsError(
                f"selected intraday comparable count drifted: {int(intraday)} != {ACCEPTED_SELECTED_INTRADAY_COMPARABLE}"
            )
        frame = con.execute(
            f"""
            SELECT fold_id, policy_id, economic_family_id, native_timeframe,
                   instrument_key, ticker, session_date, direction,
                   primary_net_return, stress_net_return, selector_score, fallback_level
            FROM read_parquet('{_sql_path(path)}')
            WHERE research_eligible AND comparable AND native_timeframe='1d'
            ORDER BY instrument_key, session_date, policy_id, direction
            """
        ).fetchdf()
        duplicate_count = int(
            con.execute(
                f"""
                SELECT count(*) FROM (
                    SELECT policy_id, instrument_key, session_date, direction, count(*) c
                    FROM read_parquet('{_sql_path(path)}')
                    WHERE research_eligible AND comparable AND native_timeframe='1d'
                    GROUP BY policy_id, instrument_key, session_date, direction
                    HAVING c > 1
                )
                """
            ).fetchone()[0]
        )
        if duplicate_count:
            raise SuccessorPathKineticsError("selected daily opportunities are not unique on the frozen route key")
    finally:
        con.close()
    frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise").dt.date
    return frame, {
        "eligibility_assignments_path": str(path.resolve()),
        "eligibility_assignments_sha256": _sha256_file(path),
        "selected_comparable_total": int(total),
        "selected_daily_comparable": int(daily),
        "selected_intraday_comparable": int(intraday),
    }


def _directional_return(direction: str, entry: float, exit_price: float) -> float:
    if direction == "LONG":
        return exit_price / entry - 1.0
    if direction == "SHORT":
        return 1.0 - exit_price / entry
    raise SuccessorPathKineticsError(f"unsupported direction: {direction}")


def _net_return_with_cost(direction: str, entry: float, exit_price: float, bps: float) -> float:
    half = bps / 20_000.0
    if direction == "LONG":
        return (exit_price * (1.0 - half) - entry * (1.0 + half)) / entry
    if direction == "SHORT":
        return (entry * (1.0 - half) - exit_price * (1.0 + half)) / entry
    raise SuccessorPathKineticsError(f"unsupported direction: {direction}")


def _threshold_label(threshold: float) -> str:
    return f"{int(round(threshold * 100))}pct"


def _first_true_offset(mask: np.ndarray) -> int | None:
    hits = np.flatnonzero(mask)
    return None if hits.size == 0 else int(hits[0]) + 1


def _first_hit_class(first_favorable: int | None, first_adverse: int | None) -> str:
    if first_favorable is None and first_adverse is None:
        return "NEITHER"
    if first_favorable is not None and first_adverse is None:
        return "FAVORABLE_ONLY"
    if first_favorable is None and first_adverse is not None:
        return "ADVERSE_ONLY"
    assert first_favorable is not None and first_adverse is not None
    if first_favorable < first_adverse:
        return "FAVORABLE_BEFORE_ADVERSE"
    if first_adverse < first_favorable:
        return "ADVERSE_BEFORE_FAVORABLE"
    return "SAME_SESSION_AMBIGUOUS"


def _path_record(
    selected: object,
    instrument: pd.DataFrame,
    signal_index: int,
) -> dict[str, object]:
    direction = str(getattr(selected, "direction"))
    if direction not in {"LONG", "SHORT"}:
        raise SuccessorPathKineticsError(f"unsupported selected direction: {direction}")
    entry_index = signal_index + 1
    if entry_index >= len(instrument):
        raise SuccessorPathKineticsError("selected comparable daily opportunity has no next-session entry")
    entry_row = instrument.iloc[entry_index]
    entry = float(entry_row["open"])
    if not math.isfinite(entry) or entry <= 0.0:
        raise SuccessorPathKineticsError("selected daily entry price is invalid")
    available = min(max(0, len(instrument) - entry_index), max(SESSION_HORIZONS))
    if available < 5:
        raise SuccessorPathKineticsError(
            "selected comparable daily opportunity has fewer than five DEVELOPMENT sessions after signal"
        )
    window = instrument.iloc[entry_index : entry_index + available]
    highs = window["high"].to_numpy(dtype=float)
    lows = window["low"].to_numpy(dtype=float)
    closes = window["close"].to_numpy(dtype=float)
    if not np.isfinite(np.concatenate((highs, lows, closes))).all():
        raise SuccessorPathKineticsError("selected daily path contains non-finite prices")

    record: dict[str, object] = {
        "fold_id": int(getattr(selected, "fold_id")),
        "policy_id": str(getattr(selected, "policy_id")),
        "economic_family_id": str(getattr(selected, "economic_family_id")),
        "direction": direction,
        "instrument_id": str(getattr(selected, "instrument_key")),
        "ticker": str(getattr(selected, "ticker")),
        "signal_session": getattr(selected, "session_date"),
        "entry_session": entry_row["session_date"],
        "entry_price": entry,
        "available_sessions": int(available),
        "conditioning_primary_net_return": float(getattr(selected, "primary_net_return")),
        "conditioning_stress_net_return": float(getattr(selected, "stress_net_return")),
        "selector_score": float(getattr(selected, "selector_score")),
        "fallback_level": int(getattr(selected, "fallback_level")),
    }

    for horizon in SESSION_HORIZONS:
        key = f"h{horizon}"
        if available < horizon:
            record[f"close_return_{key}"] = None
            record[f"mfe_{key}"] = None
            record[f"mae_{key}"] = None
            continue
        local_highs = highs[:horizon]
        local_lows = lows[:horizon]
        close = float(closes[horizon - 1])
        record[f"close_return_{key}"] = _directional_return(direction, entry, close)
        if direction == "LONG":
            record[f"mfe_{key}"] = float(local_highs.max() / entry - 1.0)
            record[f"mae_{key}"] = float(local_lows.min() / entry - 1.0)
        else:
            record[f"mfe_{key}"] = float(1.0 - local_lows.min() / entry)
            record[f"mae_{key}"] = float(1.0 - local_highs.max() / entry)

    expected_primary = _net_return_with_cost(direction, entry, float(closes[4]), 10.0)
    expected_stress = _net_return_with_cost(direction, entry, float(closes[4]), 25.0)
    if not math.isclose(
        expected_primary,
        float(getattr(selected, "primary_net_return")),
        rel_tol=1e-9,
        abs_tol=1e-10,
    ):
        raise SuccessorPathKineticsError(
            "daily source path does not reproduce the frozen 5-session primary return"
        )
    if not math.isclose(
        expected_stress,
        float(getattr(selected, "stress_net_return")),
        rel_tol=1e-9,
        abs_tol=1e-10,
    ):
        raise SuccessorPathKineticsError(
            "daily source path does not reproduce the frozen 5-session stress return"
        )

    for threshold in MOVE_THRESHOLDS:
        label = _threshold_label(threshold)
        if direction == "LONG":
            favorable_mask = highs >= entry * (1.0 + threshold)
            adverse_mask = lows <= entry * (1.0 - threshold)
        else:
            favorable_mask = lows <= entry * (1.0 - threshold)
            adverse_mask = highs >= entry * (1.0 + threshold)
        first_favorable = _first_true_offset(favorable_mask)
        first_adverse = _first_true_offset(adverse_mask)
        record[f"first_favorable_{label}_session"] = first_favorable
        record[f"first_adverse_{label}_session"] = first_adverse
        record[f"first_hit_{label}_classification"] = _first_hit_class(
            first_favorable, first_adverse
        )
    return record


def _materialize_path_records(selected: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    selected_groups = {
        str(instrument_id): group.copy()
        for instrument_id, group in selected.groupby("instrument_key", sort=False, observed=True)
    }
    seen: set[str] = set()
    records: list[dict[str, object]] = []
    started = time.monotonic()
    last_console = started
    completed = 0
    total = len(selected)
    for instrument_id, instrument in bars.groupby("instrument_id", sort=False, observed=True):
        key = str(instrument_id)
        selected_group = selected_groups.get(key)
        if selected_group is None:
            continue
        seen.add(key)
        instrument = instrument.sort_values("session_date", kind="stable").reset_index(drop=True)
        dates = list(instrument["session_date"])
        if len(dates) != len(set(dates)):
            raise SuccessorPathKineticsError(f"daily source has duplicate sessions for {key}")
        index_by_session = {session: index for index, session in enumerate(dates)}
        source_tickers = set(str(value) for value in instrument["ticker"].unique())
        if len(source_tickers) != 1:
            raise SuccessorPathKineticsError(f"daily source ticker identity drifted for {key}")
        source_ticker = next(iter(source_tickers))
        for item in selected_group.itertuples(index=False):
            signal_session = getattr(item, "session_date")
            signal_index = index_by_session.get(signal_session)
            if signal_index is None:
                raise SuccessorPathKineticsError(
                    f"selected signal session is missing from DEVELOPMENT daily source: {key} {signal_session}"
                )
            if str(getattr(item, "ticker")) != source_ticker:
                raise SuccessorPathKineticsError(
                    f"selected ticker does not match DEVELOPMENT source identity: {key}"
                )
            records.append(_path_record(item, instrument, signal_index))
            completed += 1
        now = time.monotonic()
        if completed == total or now - last_console >= 300.0:
            elapsed = max(now - started, 1e-9)
            print(
                "successor path kinetics "
                f"{completed:,}/{total:,} ({completed/total:.1%}) "
                f"rate={completed * 3600.0 / elapsed:,.1f} opportunities/hour",
                flush=True,
            )
            last_console = now
    missing = sorted(set(selected_groups) - seen)
    if missing:
        raise SuccessorPathKineticsError(
            f"selected DEVELOPMENT instruments are missing from the daily view: {missing[:10]}"
        )
    frame = pd.DataFrame.from_records(records)
    if len(frame) != ACCEPTED_SELECTED_DAILY_COMPARABLE:
        raise SuccessorPathKineticsError(
            f"path record count drifted: {len(frame)} != {ACCEPTED_SELECTED_DAILY_COMPARABLE}"
        )
    return frame.sort_values(
        ["policy_id", "direction", "signal_session", "instrument_id"], kind="stable"
    ).reset_index(drop=True)


def _horizon_summary(paths: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_cols = ["policy_id", "economic_family_id", "direction"]
    for keys, group in paths.groupby(group_cols, sort=True, observed=True):
        policy_id, family_id, direction = keys
        primary_mean = float(group["conditioning_primary_net_return"].mean())
        stress_mean = float(group["conditioning_stress_net_return"].mean())
        for horizon in SESSION_HORIZONS:
            available = group[group["available_sessions"] >= horizon]
            close = available[f"close_return_h{horizon}"]
            mfe = available[f"mfe_h{horizon}"]
            mae = available[f"mae_h{horizon}"]
            rows.append(
                {
                    "policy_id": policy_id,
                    "economic_family_id": family_id,
                    "direction": direction,
                    "horizon_sessions": horizon,
                    "selected_comparable": int(len(group)),
                    "observations": int(len(available)),
                    "mean_conditioning_primary_net_return": primary_mean,
                    "mean_conditioning_stress_net_return": stress_mean,
                    "mean_close_directional_return": float(close.mean()) if len(close) else None,
                    "median_close_directional_return": float(close.median()) if len(close) else None,
                    "positive_close_rate": float((close > 0).mean()) if len(close) else None,
                    "mean_mfe": float(mfe.mean()) if len(mfe) else None,
                    "median_mfe": float(mfe.median()) if len(mfe) else None,
                    "p90_mfe": float(mfe.quantile(0.90)) if len(mfe) else None,
                    "mean_mae": float(mae.mean()) if len(mae) else None,
                    "median_mae": float(mae.median()) if len(mae) else None,
                    "p10_mae": float(mae.quantile(0.10)) if len(mae) else None,
                }
            )
    return pd.DataFrame.from_records(rows)


def _threshold_timing_curve(paths: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_cols = ["policy_id", "economic_family_id", "direction"]
    for keys, group in paths.groupby(group_cols, sort=True, observed=True):
        policy_id, family_id, direction = keys
        for threshold in MOVE_THRESHOLDS:
            label = _threshold_label(threshold)
            first_fav = group[f"first_favorable_{label}_session"]
            first_adv = group[f"first_adverse_{label}_session"]
            for horizon in SESSION_HORIZONS:
                available = group["available_sessions"] >= horizon
                ff = first_fav[available]
                fa = first_adv[available]
                n = int(available.sum())
                if n == 0:
                    continue
                fav_hit = ff.notna() & (ff <= horizon)
                adv_hit = fa.notna() & (fa <= horizon)
                same = fav_hit & adv_hit & (ff == fa)
                fav_before = fav_hit & adv_hit & (ff < fa)
                adv_before = fav_hit & adv_hit & (fa < ff)
                fav_only = fav_hit & ~adv_hit
                adv_only = adv_hit & ~fav_hit
                neither = ~fav_hit & ~adv_hit
                fav_offsets = ff[fav_hit]
                adv_offsets = fa[adv_hit]
                rows.append(
                    {
                        "policy_id": policy_id,
                        "economic_family_id": family_id,
                        "direction": direction,
                        "move_threshold": threshold,
                        "horizon_sessions": horizon,
                        "observations": n,
                        "favorable_hit_rate": float(fav_hit.mean()),
                        "adverse_hit_rate": float(adv_hit.mean()),
                        "favorable_before_adverse_rate": float(fav_before.mean()),
                        "adverse_before_favorable_rate": float(adv_before.mean()),
                        "same_session_ambiguous_rate": float(same.mean()),
                        "favorable_only_rate": float(fav_only.mean()),
                        "adverse_only_rate": float(adv_only.mean()),
                        "neither_rate": float(neither.mean()),
                        "median_first_favorable_session": (
                            float(fav_offsets.median()) if len(fav_offsets) else None
                        ),
                        "mean_first_favorable_session": (
                            float(fav_offsets.mean()) if len(fav_offsets) else None
                        ),
                        "median_first_adverse_session": (
                            float(adv_offsets.median()) if len(adv_offsets) else None
                        ),
                    }
                )
    return pd.DataFrame.from_records(rows)


def _console_diagnostics(
    paths: pd.DataFrame,
    timing: pd.DataFrame,
) -> list[dict[str, object]]:
    primary = (
        paths.groupby(["policy_id", "direction"], sort=True, observed=True)
        .agg(
            selected_comparable=("policy_id", "size"),
            mean_primary=("conditioning_primary_net_return", "mean"),
            mean_stress=("conditioning_stress_net_return", "mean"),
        )
        .reset_index()
    )
    result: list[dict[str, object]] = []
    for row in primary.itertuples(index=False):
        item: dict[str, object] = {
            "policy_id": row.policy_id,
            "direction": row.direction,
            "selected_comparable": int(row.selected_comparable),
            "mean_primary_net_return": float(row.mean_primary),
            "mean_stress_net_return": float(row.mean_stress),
        }
        for threshold in (0.02, 0.03, 0.05):
            match = timing[
                (timing["policy_id"] == row.policy_id)
                & (timing["direction"] == row.direction)
                & np.isclose(timing["move_threshold"], threshold)
                & (timing["horizon_sessions"] == 5)
            ]
            if len(match) != 1:
                raise SuccessorPathKineticsError(
                    f"missing frozen five-session timing row for {row.policy_id} {row.direction} {threshold}"
                )
            metric = match.iloc[0]
            label = _threshold_label(threshold)
            item[f"p_favorable_{label}_by_5"] = float(metric["favorable_hit_rate"])
            item[f"p_adverse_{label}_by_5"] = float(metric["adverse_hit_rate"])
            item[f"p_same_session_ambiguous_{label}_by_5"] = float(
                metric["same_session_ambiguous_rate"]
            )
            value = metric["median_first_favorable_session"]
            item[f"median_first_favorable_{label}_session"] = (
                None if pd.isna(value) else float(value)
            )
        result.append(item)
    return result


def run_successor_path_kinetics_analysis(project_root: Path) -> dict[str, object]:
    project = Path(project_root).resolve()
    output_root = path_kinetics_root(project)
    output_root.mkdir(parents=True, exist_ok=True)
    _write_json(output_root / "path_kinetics_contract.json", successor_path_kinetics_manifest())

    print(
        "successor path-kinetics authority: selected comparable DAILY DEVELOPMENT opportunities only; "
        "hash-bound daily source reread; no master/future/provider/broker/PAPER/LIVE/promotion/confluence/option authority",
        flush=True,
    )
    conditioning_binding = validate_conditioning_inputs(project)
    option_binding = _validate_optionworthiness_summary(project)
    selected, selection_binding = _selected_daily_frame(project)

    settings = load_settings(project)
    loaded = ReferenceV2DailyLakeAdapter(settings).load(DEVELOPMENT_START, DEVELOPMENT_END)
    source_report = loaded.report
    if source_report.get("status") != "PASS":
        raise SuccessorPathKineticsError("V2 DEVELOPMENT daily source did not pass validation")
    if source_report.get("scope") != "ALPACA_SIP_V2_DEVELOPMENT_ONLY":
        raise SuccessorPathKineticsError("V2 daily source scope is not DEVELOPMENT-only")
    if int(source_report.get("protected_master_return_rows_read", -1)) != 0:
        raise SuccessorPathKineticsError("path kinetics attempted to read protected master rows")
    if int(source_report.get("v1_rows_read", -1)) != 0:
        raise SuccessorPathKineticsError("path kinetics attempted a V1 source fallback")

    paths = _materialize_path_records(selected, loaded.bars)
    del loaded
    horizon = _horizon_summary(paths)
    timing = _threshold_timing_curve(paths)
    diagnostics = _console_diagnostics(paths, timing)

    outputs = {
        "per_opportunity": _write_parquet_atomic(output_root / "per_opportunity.parquet", paths),
        "horizon_summary": _write_parquet_atomic(output_root / "horizon_summary.parquet", horizon),
        "threshold_timing_curve": _write_parquet_atomic(
            output_root / "threshold_timing_curve.parquet", timing
        ),
    }
    output_identity = [
        {"name": name, **value} for name, value in sorted(outputs.items())
    ]
    output_artifact_set_fingerprint = canonical_sha256(output_identity)
    scientific_identity = {
        "analysis_contract": SUCCESSOR_PATH_KINETICS_ANALYSIS_CONTRACT,
        "path_kinetics_fingerprint": SUCCESSOR_PATH_KINETICS_FINGERPRINT,
        "conditioning_analysis_fingerprint": conditioning_binding["conditioning_analysis_fingerprint"],
        "optionworthiness_analysis_fingerprint": option_binding["analysis_fingerprint"],
        "eligibility_assignments_sha256": selection_binding["eligibility_assignments_sha256"],
        "v2_daily_source_fingerprint": source_report["source_fingerprint"],
        "output_artifact_set_fingerprint": output_artifact_set_fingerprint,
    }
    analysis_fingerprint = canonical_sha256(scientific_identity)
    report: dict[str, object] = {
        "status": "COMPLETE_SELECTED_DAILY_PATH_KINETICS_ONLY",
        "analysis_contract": SUCCESSOR_PATH_KINETICS_ANALYSIS_CONTRACT,
        "path_kinetics_contract": SUCCESSOR_PATH_KINETICS_CONTRACT,
        "path_kinetics_fingerprint": SUCCESSOR_PATH_KINETICS_FINGERPRINT,
        "analysis_fingerprint": analysis_fingerprint,
        "scientific_identity": scientific_identity,
        "conditioning_binding": conditioning_binding,
        "optionworthiness_binding": option_binding,
        "selection_binding": selection_binding,
        "daily_source_report": source_report,
        "scope_counts": {
            "selected_comparable_total": ACCEPTED_SELECTED_COMPARABLE_TOTAL,
            "selected_daily_comparable_analyzed": int(len(paths)),
            "selected_intraday_comparable_not_reopened": ACCEPTED_SELECTED_INTRADAY_COMPARABLE,
        },
        "move_thresholds_fraction": list(MOVE_THRESHOLDS),
        "session_horizons": list(SESSION_HORIZONS),
        "outputs": output_identity,
        "output_artifact_set_fingerprint": output_artifact_set_fingerprint,
        "five_session_route_diagnostics": diagnostics,
        "daily_bar_sequence_limit": "SAME_SESSION_FAVORABLE_AND_ADVERSE_ORDER_IS_AMBIGUOUS",
        "historical_option_pnl_claimed": False,
        "intraday_path_reopened": False,
        "consumed_master_rows_read": 0,
        "future_blind_rows_read": 0,
        "provider_calls": 0,
        "broker_reads": 0,
        "broker_writes": 0,
        "confluence_opened": False,
        "paper_authority": False,
        "live_authority": False,
        "strategy_promotion": False,
        "selector_promotion": False,
        "option_trading_authority": False,
        "authority": AUTHORITY,
        "completed_at_utc": datetime.now(UTC).isoformat(),
    }
    _write_json(output_root / "analysis_summary.json", report)
    return report
