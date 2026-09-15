from __future__ import annotations

import hashlib
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from packages.backtesting.b35_development_source import (
    B35DevelopmentMinuteSource,
    B35DevelopmentUnitBinding,
)
from packages.backtesting.successor_development_outcomes import (
    DEVELOPMENT_END,
    DEVELOPMENT_START,
    validate_accepted_successor_preflight,
)
from packages.backtesting.successor_optionworthiness_analysis import (
    conditioning_root,
    optionworthiness_root,
    validate_conditioning_inputs,
)
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.atomic_io import atomic_write_text, replace_with_retry, unique_temp_path
from packages.core.settings import load_settings
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
)
from packages.strategies.successor_selected_daily_path_contract import (
    ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
    MOVE_THRESHOLDS,
)
from packages.strategies.successor_selected_minute_path_contract import (
    AUTHORITY,
    EXPECTED_POLICY_ID,
    EXPECTED_SELECTED_MINUTE_COMPARABLE,
    SUCCESSOR_SELECTED_MINUTE_PATH_CONTRACT,
    SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT,
    successor_selected_minute_path_manifest,
)


SUCCESSOR_SELECTED_MINUTE_PATH_ANALYSIS_CONTRACT = (
    "atlas-successor-selected-minute-path-analysis-v1-source-bound-exact-minute"
)
VERIFY_WORKERS_MAX = 8


class SuccessorSelectedMinutePathError(RuntimeError):
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


def _read_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SuccessorSelectedMinutePathError(f"invalid JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise SuccessorSelectedMinutePathError(f"JSON artifact is not an object: {path}")
    return value


def _sql_path(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _sql_paths(paths: tuple[Path, ...]) -> str:
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
    conn.register("minute_output_frame", frame)
    try:
        conn.execute(
            f"COPY (SELECT * FROM minute_output_frame ORDER BY {order_by}) "
            f"TO '{_sql_path(temp)}' (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 100000)"
        )
        with temp.open("rb+") as handle:
            os.fsync(handle.fileno())
        replace_with_retry(temp, target)
    finally:
        conn.unregister("minute_output_frame")
        temp.unlink(missing_ok=True)
    return int(conn.execute(f"SELECT count(*) FROM read_parquet('{_sql_path(target)}')").fetchone()[0])


def selected_minute_path_root(project_root: Path) -> Path:
    return (
        conditioning_root(project_root)
        / "selected_minute_path_v1"
        / SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT[:16]
    ).resolve()


def _validate_optionworthiness(project_root: Path) -> dict[str, object]:
    summary_path = optionworthiness_root(project_root) / "analysis_summary.json"
    summary = _read_json(summary_path)
    if summary.get("status") != "COMPLETE_OPTIONWORTHINESS_DIAGNOSTICS_ONLY":
        raise SuccessorSelectedMinutePathError("option-worthiness analysis is not complete")
    if summary.get("analysis_fingerprint") != ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT:
        raise SuccessorSelectedMinutePathError("option-worthiness analysis fingerprint drifted")
    counts = summary.get("scope_counts")
    if not isinstance(counts, dict) or int(counts.get("walk_forward_selected_comparable", -1)) != 36_254:
        raise SuccessorSelectedMinutePathError("option-worthiness selected population drifted")
    for key in (
        "confluence_opened",
        "paper_authority",
        "live_authority",
        "strategy_promotion",
        "selector_promotion",
        "option_trading_authority",
    ):
        if summary.get(key) is not False:
            raise SuccessorSelectedMinutePathError(f"option-worthiness authority drifted: {key}")
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
                   gross_return, primary_net_return, stress_net_return,
                   mfe, mae, entry_time_utc, exit_time_utc, holding_minutes
            FROM read_parquet('{_sql_path(assignment_path)}')
            WHERE research_eligible AND comparable AND native_timeframe='1m'
            ORDER BY policy_id, direction, instrument_key, session_date, fold_id
            """
        ).fetchdf()
    finally:
        conn.close()
    if len(frame) != EXPECTED_SELECTED_MINUTE_COMPARABLE:
        raise SuccessorSelectedMinutePathError(
            f"selected minute population drifted: {len(frame)} != {EXPECTED_SELECTED_MINUTE_COMPARABLE}"
        )
    policies = sorted(str(value) for value in frame["policy_id"].dropna().unique())
    if policies != [EXPECTED_POLICY_ID]:
        raise SuccessorSelectedMinutePathError(f"selected minute policy drifted: {policies}")
    if frame[["entry_time_utc", "exit_time_utc", "gross_return"]].isna().any().any():
        raise SuccessorSelectedMinutePathError("selected minute population has missing retained path fields")
    frame["session_date"] = pd.to_datetime(frame["session_date"], errors="raise").dt.date
    frame["entry_time_utc"] = pd.to_datetime(frame["entry_time_utc"], utc=True, errors="raise")
    frame["exit_time_utc"] = pd.to_datetime(frame["exit_time_utc"], utc=True, errors="raise")
    if bool((frame["exit_time_utc"] < frame["entry_time_utc"]).any()):
        raise SuccessorSelectedMinutePathError("selected minute exit precedes entry")
    duplicates = int(
        frame.duplicated(
            subset=["fold_id", "policy_id", "direction", "instrument_key", "session_date"]
        ).sum()
    )
    if duplicates:
        raise SuccessorSelectedMinutePathError(f"selected minute population has {duplicates} duplicate keys")
    frame["case_id"] = [
        canonical_sha256(
            {
                "fold_id": int(row.fold_id),
                "policy_id": str(row.policy_id),
                "direction": str(row.direction),
                "instrument_key": str(row.instrument_key),
                "session_date": row.session_date.isoformat(),
                "entry_time_utc": pd.Timestamp(row.entry_time_utc).isoformat(),
                "exit_time_utc": pd.Timestamp(row.exit_time_utc).isoformat(),
            }
        )[:24]
        for row in frame.itertuples(index=False)
    ]
    if frame["case_id"].duplicated().any():
        raise SuccessorSelectedMinutePathError("selected minute case id collision")
    return frame, conditioning_binding


def _input_root(project_root: Path) -> Path:
    return (
        project_root.resolve()
        / "data"
        / "v2_build"
        / "alpaca_sip_v2"
        / "derived"
        / "strategy_lab"
        / "successor_development_inputs"
        / ACCEPTED_RUN_CONTRACT_FINGERPRINT[:16]
    ).resolve()


def _resolve_locator(project_root: Path, locator: object) -> Path:
    relative = Path(str(locator or ""))
    if not str(locator or "") or relative.is_absolute():
        raise SuccessorSelectedMinutePathError("successor input locator must be project-relative")
    resolved = (project_root.resolve() / relative).resolve()
    try:
        resolved.relative_to(project_root.resolve())
    except ValueError as exc:
        raise SuccessorSelectedMinutePathError("successor input locator escapes project root") from exc
    return resolved


def _binding_from_serialized(
    project_root: Path,
    source: B35DevelopmentMinuteSource,
    payload: dict[str, object],
) -> B35DevelopmentUnitBinding:
    try:
        unit_id = str(payload["unit_id"])
        year = int(payload["year"])
        month = int(payload["month"])
        batch = int(payload["batch_index"])
        window_start = date.fromisoformat(str(payload["window_start"]))
        window_end = date.fromisoformat(str(payload["window_end_exclusive"]))
        symbols = tuple(str(value) for value in payload["symbols"])
        canonical_sha = str(payload["canonical_sha256"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SuccessorSelectedMinutePathError("serialized successor minute unit is malformed") from exc
    if len(unit_id) != 64 or len(canonical_sha) != 64 or not symbols:
        raise SuccessorSelectedMinutePathError("serialized successor minute unit identity is incomplete")
    partition = Path(f"year={year:04d}") / f"month={month:02d}" / f"batch={batch:04d}"
    expected_canonical = (
        source.layout.canonical_minute / partition / f"{unit_id[:20]}.parquet"
    ).absolute()
    expected_checkpoint = (
        source.layout.checkpoints / "native_units" / "1m" / partition / f"{unit_id[:20]}.json"
    ).absolute()
    if _resolve_locator(project_root, payload.get("canonical_locator")) != expected_canonical:
        raise SuccessorSelectedMinutePathError("serialized successor canonical locator drifted")
    if _resolve_locator(project_root, payload.get("checkpoint_locator")) != expected_checkpoint:
        raise SuccessorSelectedMinutePathError("serialized successor checkpoint locator drifted")
    return B35DevelopmentUnitBinding(
        unit_id=unit_id,
        year=year,
        month=month,
        batch_index=batch,
        window_start=window_start,
        window_end_exclusive=window_end,
        symbols=symbols,
        policy_sha256=str(payload["policy_sha256"]),
        universe_sha256=str(payload["universe_sha256"]),
        canonical_path=expected_canonical,
        canonical_sha256=canonical_sha,
        checkpoint_path=expected_checkpoint,
    )


def _selected_source_units(
    project_root: Path,
    source: B35DevelopmentMinuteSource,
    selected: pd.DataFrame,
) -> tuple[tuple[B35DevelopmentUnitBinding, ...], dict[str, str]]:
    root = _input_root(project_root)
    summary_path = root / "input_manifest.json"
    summary = _read_json(summary_path)
    observed = canonical_sha256({key: value for key, value in summary.items() if key != "fingerprint"})
    if summary.get("fingerprint") != ACCEPTED_INPUT_MANIFEST_FINGERPRINT or observed != ACCEPTED_INPUT_MANIFEST_FINGERPRINT:
        raise SuccessorSelectedMinutePathError("accepted successor input manifest fingerprint drifted")
    work_units = summary.get("work_units")
    if not isinstance(work_units, list):
        raise SuccessorSelectedMinutePathError("successor input manifest work-unit inventory is missing")
    fingerprints = {
        str(item.get("token")): str(item.get("input_fingerprint"))
        for item in work_units
        if isinstance(item, dict)
    }
    selected_symbols = {str(value) for value in selected["instrument_key"].unique()}
    requested_months = {
        (str(row.instrument_key), int(row.session_date.year), int(row.session_date.month))
        for row in selected.itertuples(index=False)
    }
    lookup: dict[tuple[str, int, int], B35DevelopmentUnitBinding] = {}
    token_by_symbol: dict[str, str] = {}
    relevant_units: dict[str, B35DevelopmentUnitBinding] = {}

    for token, expected_fingerprint in sorted(fingerprints.items()):
        if not token.startswith("minute_"):
            continue
        group_path = root / "groups" / f"{token}.json"
        group = _read_json(group_path)
        scientific = group.get("scientific")
        operational = group.get("operational")
        if not isinstance(scientific, dict) or not isinstance(operational, dict):
            raise SuccessorSelectedMinutePathError(f"successor minute input group structure drifted: {token}")
        if canonical_sha256(scientific) != expected_fingerprint or group.get("scientific_fingerprint") != expected_fingerprint:
            raise SuccessorSelectedMinutePathError(f"successor minute input group fingerprint drifted: {token}")
        if scientific.get("kind") != "minute" or scientific.get("run_contract_fingerprint") != ACCEPTED_RUN_CONTRACT_FINGERPRINT:
            raise SuccessorSelectedMinutePathError(f"successor minute input group contract drifted: {token}")
        symbols = tuple(str(value) for value in scientific.get("symbols") or [])
        overlap = selected_symbols.intersection(symbols)
        if not overlap:
            continue
        for symbol in overlap:
            if symbol in token_by_symbol and token_by_symbol[symbol] != token:
                raise SuccessorSelectedMinutePathError(f"selected symbol appears in multiple minute groups: {symbol}")
            token_by_symbol[symbol] = token
        raw_units = operational.get("units")
        if not isinstance(raw_units, list) or not raw_units:
            raise SuccessorSelectedMinutePathError(f"successor minute input units missing: {token}")
        unit_ids = [str(item.get("unit_id")) for item in raw_units if isinstance(item, dict)]
        if unit_ids != [str(value) for value in scientific.get("unit_ids") or []]:
            raise SuccessorSelectedMinutePathError(f"successor minute input unit ids drifted: {token}")
        binding_hash = canonical_sha256(
            [
                {"unit_id": str(item["unit_id"]), "canonical_sha256": str(item["canonical_sha256"])}
                for item in raw_units
                if isinstance(item, dict)
            ]
        )
        if binding_hash != scientific.get("unit_bindings_sha256"):
            raise SuccessorSelectedMinutePathError(f"successor minute input unit binding hash drifted: {token}")
        for raw in raw_units:
            if not isinstance(raw, dict):
                raise SuccessorSelectedMinutePathError(f"successor minute input unit is not an object: {token}")
            year = int(raw["year"])
            month = int(raw["month"])
            needed = [symbol for symbol in overlap if (symbol, year, month) in requested_months]
            if not needed:
                continue
            binding = _binding_from_serialized(project_root, source, raw)
            for symbol in needed:
                key = (symbol, year, month)
                if key in lookup:
                    raise SuccessorSelectedMinutePathError(f"multiple source units match selected minute case: {key}")
                lookup[key] = binding
            relevant_units[binding.unit_id] = binding

    missing_symbols = sorted(selected_symbols.difference(token_by_symbol))
    if missing_symbols:
        raise SuccessorSelectedMinutePathError(f"selected minute symbols missing from accepted input groups: {missing_symbols[:5]}")
    missing_months = sorted(requested_months.difference(lookup))
    if missing_months:
        raise SuccessorSelectedMinutePathError(f"selected minute symbol/month source binding missing: {missing_months[:5]}")
    case_unit = {
        str(row.case_id): lookup[(str(row.instrument_key), row.session_date.year, row.session_date.month)].unit_id
        for row in selected.itertuples(index=False)
    }
    return tuple(sorted(relevant_units.values(), key=lambda item: item.unit_id)), case_unit


def _verify_units(
    source: B35DevelopmentMinuteSource,
    units: tuple[B35DevelopmentUnitBinding, ...],
) -> None:
    if not units:
        raise SuccessorSelectedMinutePathError("selected minute source binding produced no units")
    workers = min(VERIFY_WORKERS_MAX, max(1, len(units)))
    completed = 0
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(source.verify_unit, unit): unit for unit in units}
        for future in as_completed(futures):
            unit = futures[future]
            try:
                future.result()
            except Exception as exc:
                raise SuccessorSelectedMinutePathError(
                    f"selected minute canonical source verification failed: {unit.unit_id}"
                ) from exc
            completed += 1
            if completed == len(units) or completed % 25 == 0:
                elapsed = max(time.monotonic() - started, 1e-9)
                print(
                    f"selected minute source verification {completed}/{len(units)} "
                    f"({completed / len(units):.1%}) rate={completed / elapsed:.1f} units/s",
                    flush=True,
                )


def _read_selected_bars(
    selected: pd.DataFrame,
    units: tuple[B35DevelopmentUnitBinding, ...],
    case_unit: dict[str, str],
) -> pd.DataFrame:
    requests = selected[
        ["case_id", "instrument_key", "session_date", "entry_time_utc", "exit_time_utc"]
    ].copy()
    requests["unit_id"] = requests["case_id"].map(case_unit)
    paths = tuple(unit.canonical_path for unit in units)
    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, min(8, os.cpu_count() or 1))}")
    conn.execute("PRAGMA preserve_insertion_order=false")
    conn.register("selected_minute_requests", requests)
    try:
        frame = conn.execute(
            f"""
            SELECT r.case_id, p.symbol, p.session_date, p.timestamp_utc,
                   p.open, p.high, p.low, p.close
            FROM read_parquet({_sql_paths(paths)}, hive_partitioning=false) p
            JOIN selected_minute_requests r
              ON p.symbol = r.instrument_key
             AND p.session_date = r.session_date
             AND p.timestamp_utc >= r.entry_time_utc
             AND p.timestamp_utc <= r.exit_time_utc
            WHERE p.session_segment = 'regular'
            ORDER BY r.case_id, p.timestamp_utc
            """
        ).fetchdf()
    finally:
        conn.unregister("selected_minute_requests")
        conn.close()
    if frame.empty:
        raise SuccessorSelectedMinutePathError("selected minute raw path query returned no bars")
    frame["timestamp_utc"] = pd.to_datetime(frame["timestamp_utc"], utc=True, errors="raise")
    return frame


def _touch_class(fav: int | None, adv: int | None) -> str:
    if fav is None and adv is None:
        return "NEITHER"
    if fav is not None and adv is None:
        return "FAVORABLE_ONLY"
    if fav is None and adv is not None:
        return "ADVERSE_ONLY"
    if int(fav) < int(adv):
        return "FAVORABLE_FIRST"
    if int(adv) < int(fav):
        return "ADVERSE_FIRST"
    return "SAME_MINUTE_COLLISION_UNORDERED"


def _analyze_case_bars(case: pd.Series, bars: pd.DataFrame) -> tuple[dict[str, object], list[dict[str, object]]]:
    bars = bars.sort_values("timestamp_utc", kind="stable").reset_index(drop=True)
    entry_time = pd.Timestamp(case["entry_time_utc"])
    exit_time = pd.Timestamp(case["exit_time_utc"])
    if bars.empty or pd.Timestamp(bars.iloc[0]["timestamp_utc"]) != entry_time:
        raise SuccessorSelectedMinutePathError(f"selected minute entry bar missing: {case['case_id']}")
    if pd.Timestamp(bars.iloc[-1]["timestamp_utc"]) != exit_time:
        raise SuccessorSelectedMinutePathError(f"selected minute exit bar missing: {case['case_id']}")
    if bars["timestamp_utc"].duplicated().any():
        raise SuccessorSelectedMinutePathError(f"duplicate selected minute timestamps: {case['case_id']}")
    entry = float(bars.iloc[0]["open"])
    if not math.isfinite(entry) or entry <= 0:
        raise SuccessorSelectedMinutePathError(f"invalid selected minute entry price: {case['case_id']}")
    direction = str(case["direction"])
    if direction not in {"LONG", "SHORT"}:
        raise SuccessorSelectedMinutePathError(f"invalid selected minute direction: {direction}")
    gross = float(case["gross_return"])
    if not math.isfinite(gross):
        raise SuccessorSelectedMinutePathError(f"invalid retained gross return: {case['case_id']}")

    first_fav: dict[float, int | None] = {float(value): None for value in MOVE_THRESHOLDS}
    first_adv: dict[float, int | None] = {float(value): None for value in MOVE_THRESHOLDS}
    path_mfe = 0.0
    path_adv = 0.0
    pre_exit_bars = 0
    for row in bars.itertuples(index=False):
        timestamp = pd.Timestamp(row.timestamp_utc)
        minutes = int(round((timestamp - entry_time).total_seconds() / 60.0))
        if timestamp == exit_time:
            favorable = max(gross, 0.0)
            adverse = max(-gross, 0.0)
        else:
            pre_exit_bars += 1
            high = float(row.high)
            low = float(row.low)
            if direction == "LONG":
                favorable = high / entry - 1.0
                adverse = 1.0 - low / entry
            else:
                favorable = 1.0 - low / entry
                adverse = high / entry - 1.0
            favorable = max(float(favorable), 0.0)
            adverse = max(float(adverse), 0.0)
        path_mfe = max(path_mfe, favorable)
        path_adv = max(path_adv, adverse)
        for threshold in MOVE_THRESHOLDS:
            key = float(threshold)
            if first_fav[key] is None and favorable >= key:
                first_fav[key] = minutes
            if first_adv[key] is None and adverse >= key:
                first_adv[key] = minutes

    holding = int(case["holding_minutes"])
    actual_holding = int(round((exit_time - entry_time).total_seconds() / 60.0))
    if holding != actual_holding:
        raise SuccessorSelectedMinutePathError(
            f"retained holding minutes drifted for {case['case_id']}: {holding} != {actual_holding}"
        )
    path_row = {
        "case_id": str(case["case_id"]),
        "fold_id": int(case["fold_id"]),
        "policy_id": str(case["policy_id"]),
        "economic_family_id": str(case["economic_family_id"]),
        "instrument_key": str(case["instrument_key"]),
        "session_date": case["session_date"],
        "direction": direction,
        "entry_time_utc": entry_time,
        "exit_time_utc": exit_time,
        "entry_price": entry,
        "holding_minutes": holding,
        "bars_observed_including_exit": len(bars),
        "pre_exit_bars_with_ohlc_extremes": pre_exit_bars,
        "retained_gross_return": gross,
        "retained_primary_net_return": float(case["primary_net_return"]),
        "retained_stress_net_return": float(case["stress_net_return"]),
        "retained_mfe": None if pd.isna(case["mfe"]) else float(case["mfe"]),
        "retained_mae": None if pd.isna(case["mae"]) else float(case["mae"]),
        "path_mfe_before_exit_plus_terminal": path_mfe,
        "path_adverse_before_exit_plus_terminal": path_adv,
        "exit_bar_extremes_excluded": True,
    }
    threshold_rows = [
        {
            **{key: path_row[key] for key in (
                "case_id", "fold_id", "policy_id", "economic_family_id",
                "instrument_key", "session_date", "direction", "holding_minutes"
            )},
            "move_threshold": float(threshold),
            "first_favorable_minutes": first_fav[float(threshold)],
            "first_adverse_minutes": first_adv[float(threshold)],
            "first_touch_class": _touch_class(
                first_fav[float(threshold)], first_adv[float(threshold)]
            ),
        }
        for threshold in MOVE_THRESHOLDS
    ]
    return path_row, threshold_rows


def _summary_rows(conn: duckdb.DuckDBPyConnection, path_file: Path, threshold_file: Path) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    path_result = conn.execute(
        f"""
        SELECT policy_id, economic_family_id, direction,
               count(*) AS selected_comparable,
               count(DISTINCT fold_id) AS active_folds,
               avg(retained_gross_return) AS mean_gross_return,
               median(retained_gross_return) AS median_gross_return,
               avg(retained_primary_net_return) AS mean_primary_net_return,
               avg(retained_stress_net_return) AS mean_stress_net_return,
               avg(holding_minutes) AS mean_holding_minutes,
               median(holding_minutes) AS median_holding_minutes,
               avg(path_mfe_before_exit_plus_terminal) AS mean_path_mfe,
               median(path_mfe_before_exit_plus_terminal) AS median_path_mfe,
               avg(path_adverse_before_exit_plus_terminal) AS mean_path_adverse,
               median(path_adverse_before_exit_plus_terminal) AS median_path_adverse
        FROM read_parquet('{_sql_path(path_file)}')
        GROUP BY policy_id, economic_family_id, direction
        ORDER BY policy_id, direction
        """
    )
    path_columns = [item[0] for item in path_result.description]
    route_rows = [dict(zip(path_columns, raw, strict=True)) for raw in path_result.fetchall()]

    threshold_result = conn.execute(
        f"""
        SELECT policy_id, direction, move_threshold,
               count(*) AS selected_comparable,
               avg(CASE WHEN first_favorable_minutes IS NOT NULL THEN 1.0 ELSE 0.0 END) AS favorable_hit_rate,
               avg(CASE WHEN first_adverse_minutes IS NOT NULL THEN 1.0 ELSE 0.0 END) AS adverse_hit_rate,
               avg(CASE WHEN first_touch_class IN ('FAVORABLE_ONLY','FAVORABLE_FIRST') THEN 1.0 ELSE 0.0 END) AS favorable_before_adverse_rate,
               avg(CASE WHEN first_touch_class IN ('ADVERSE_ONLY','ADVERSE_FIRST') THEN 1.0 ELSE 0.0 END) AS adverse_before_favorable_rate,
               avg(CASE WHEN first_touch_class='SAME_MINUTE_COLLISION_UNORDERED' THEN 1.0 ELSE 0.0 END) AS same_minute_collision_rate,
               avg(first_favorable_minutes) FILTER (WHERE first_favorable_minutes IS NOT NULL) AS mean_first_favorable_minutes,
               median(first_favorable_minutes) FILTER (WHERE first_favorable_minutes IS NOT NULL) AS median_first_favorable_minutes,
               avg(first_adverse_minutes) FILTER (WHERE first_adverse_minutes IS NOT NULL) AS mean_first_adverse_minutes,
               median(first_adverse_minutes) FILTER (WHERE first_adverse_minutes IS NOT NULL) AS median_first_adverse_minutes
        FROM read_parquet('{_sql_path(threshold_file)}')
        GROUP BY policy_id, direction, move_threshold
        ORDER BY policy_id, direction, move_threshold
        """
    )
    threshold_columns = [item[0] for item in threshold_result.description]
    threshold_rows = [
        dict(zip(threshold_columns, raw, strict=True)) for raw in threshold_result.fetchall()
    ]
    return route_rows, threshold_rows


def run_successor_selected_minute_path_analysis(project_root: Path) -> dict[str, object]:
    project = Path(project_root).resolve()
    output_root = selected_minute_path_root(project)
    output_root.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    _write_json(output_root / "selected_minute_path_contract.json", successor_selected_minute_path_manifest())
    print(
        "successor selected minute path authority: selected DEVELOPMENT minute diagnostics only; "
        "master/future/provider/broker/PAPER/LIVE/promotion/confluence/option authority forbidden",
        flush=True,
    )

    option_binding = _validate_optionworthiness(project)
    selected, conditioning_binding = _selected_assignments(project)
    preflight = validate_accepted_successor_preflight(project)
    print(
        f"selected minute assignments validated: {len(selected):,} "
        f"({selected['instrument_key'].nunique():,} symbols)",
        flush=True,
    )

    settings = load_settings(project)
    source = B35DevelopmentMinuteSource(settings, duckdb_threads=1)
    try:
        units, case_unit = _selected_source_units(project, source, selected)
        print(
            f"selected minute source bindings: {len(units):,} unique native units; verifying exact paths and SHA-256...",
            flush=True,
        )
        _verify_units(source, units)
        print("selected minute source verified; reading only selected symbol/session entry-to-exit paths...", flush=True)
        bars = _read_selected_bars(selected, units, case_unit)
    finally:
        source.close()
    print(
        f"selected minute path rows loaded: {len(bars):,} bars across {bars['case_id'].nunique():,} cases",
        flush=True,
    )

    selected_by_case = selected.set_index("case_id", drop=False)
    grouped = {str(case_id): frame for case_id, frame in bars.groupby("case_id", sort=False)}
    path_rows: list[dict[str, object]] = []
    threshold_rows: list[dict[str, object]] = []
    for case_id, case in selected_by_case.iterrows():
        if str(case_id) not in grouped:
            raise SuccessorSelectedMinutePathError(f"no raw path rows for selected minute case: {case_id}")
        path_row, case_thresholds = _analyze_case_bars(case, grouped[str(case_id)])
        path_rows.append(path_row)
        threshold_rows.extend(case_thresholds)
    if len(path_rows) != EXPECTED_SELECTED_MINUTE_COMPARABLE:
        raise SuccessorSelectedMinutePathError("selected minute path coverage drifted")
    if len(threshold_rows) != EXPECTED_SELECTED_MINUTE_COMPARABLE * len(MOVE_THRESHOLDS):
        raise SuccessorSelectedMinutePathError("selected minute threshold expansion drifted")

    path_frame = pd.DataFrame(path_rows)
    threshold_frame = pd.DataFrame(threshold_rows)
    conn = duckdb.connect()
    conn.execute(f"PRAGMA threads={max(1, min(8, os.cpu_count() or 1))}")
    try:
        path_file = output_root / "selected_minute_paths.parquet"
        threshold_file = output_root / "selected_minute_thresholds.parquet"
        _write_frame_atomic(
            conn,
            path_frame,
            path_file,
            order_by="policy_id, direction, instrument_key, session_date, fold_id",
        )
        _write_frame_atomic(
            conn,
            threshold_frame,
            threshold_file,
            order_by="policy_id, direction, instrument_key, session_date, fold_id, move_threshold",
        )
        route_rows, route_threshold_rows = _summary_rows(conn, path_file, threshold_file)
    finally:
        conn.close()

    outputs = [
        {"name": "selected_minute_paths", "path": str(path_file), "sha256": _sha256_file(path_file)},
        {"name": "selected_minute_thresholds", "path": str(threshold_file), "sha256": _sha256_file(threshold_file)},
    ]
    result: dict[str, object] = {
        "status": "COMPLETE_SELECTED_MINUTE_PATH_DIAGNOSTICS_ONLY",
        "analysis_contract": SUCCESSOR_SELECTED_MINUTE_PATH_ANALYSIS_CONTRACT,
        "selected_minute_path_contract": SUCCESSOR_SELECTED_MINUTE_PATH_CONTRACT,
        "selected_minute_path_fingerprint": SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT,
        "accepted_optionworthiness": option_binding,
        "conditioning_analysis_fingerprint": conditioning_binding["conditioning_analysis_fingerprint"],
        "accepted_source_verification_run_fingerprint": preflight.source_verification_run_fingerprint,
        "accepted_source_manifest_fingerprint": preflight.source_manifest_fingerprint,
        "accepted_input_manifest_fingerprint": ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
        "selected_minute_comparable": len(path_rows),
        "selected_policy_id": EXPECTED_POLICY_ID,
        "selected_symbol_count": int(selected["instrument_key"].nunique()),
        "verified_native_unit_count": len(units),
        "raw_path_bar_count": len(bars),
        "move_thresholds_fraction": list(MOVE_THRESHOLDS),
        "route_path_summary": route_rows,
        "route_threshold_summary": route_threshold_rows,
        "exit_bar_extremes_excluded": True,
        "same_minute_collision_unordered": True,
        "tick_order_claimed": False,
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
        "outputs": outputs,
        "output_artifact_set_fingerprint": canonical_sha256(outputs),
    }
    result["analysis_fingerprint"] = canonical_sha256(
        {
            "selected_minute_path_fingerprint": SUCCESSOR_SELECTED_MINUTE_PATH_FINGERPRINT,
            "conditioning_analysis_fingerprint": conditioning_binding["conditioning_analysis_fingerprint"],
            "accepted_optionworthiness_analysis_fingerprint": ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
            "accepted_source_verification_run_fingerprint": preflight.source_verification_run_fingerprint,
            "accepted_source_manifest_fingerprint": preflight.source_manifest_fingerprint,
            "accepted_input_manifest_fingerprint": ACCEPTED_INPUT_MANIFEST_FINGERPRINT,
            "output_artifact_set_fingerprint": result["output_artifact_set_fingerprint"],
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
