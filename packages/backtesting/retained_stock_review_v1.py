from __future__ import annotations

"""Reconcile small accepted DEVELOPMENT aggregates without replaying their sources."""

import hashlib
import json
import math
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import duckdb

from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.settings import AtlasSettings
from packages.strategies.successor_conditioning_contract import (
    ACCEPTED_RUN_CONTRACT_FINGERPRINT,
    ACCEPTED_STANDALONE_RECORD_COUNT,
    DAILY_PRIMARY_COST_BPS,
    DAILY_STRESS_COST_BPS,
    INTRADAY_PRIMARY_COST_BPS,
    INTRADAY_STRESS_COST_BPS,
    SUCCESSOR_CONDITIONING_FINGERPRINT,
)
from packages.strategies.successor_optionworthiness_contract import (
    ANALYSIS_SUBSETS,
    SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
)
from packages.strategies.successor_selected_daily_path_contract import (
    ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
    MOVE_THRESHOLDS,
    SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT,
)


CONTRACT = "atlas-retained-stock-review-v1-accepted-aggregate-reconciliation"
ACCEPTED_PATH_ANALYSIS = "e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_AGGREGATE_ROWS = 10_000
CONDITIONING_ROOT = (
    "data/v2_build/alpaca_sip_v2/derived/strategy_lab/successor_development/"
    f"{ACCEPTED_RUN_CONTRACT_FINGERPRINT[:16]}/conditioning_v1/"
    f"{SUCCESSOR_CONDITIONING_FINGERPRINT[:16]}"
)
OPTIONWORTHINESS_ROOT = f"{CONDITIONING_ROOT}/optionworthiness_v1/{SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT[:16]}"
PATH_ROOT = f"{CONDITIONING_ROOT}/selected_daily_path_v1/{SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT[:16]}"
SELECTED = "WALK_FORWARD_SELECTED_COMPARABLE"
TEST = "WALK_FORWARD_TEST_COMPARABLE"
ALL = "DEVELOPMENT_ALL_COMPARABLE"


class RetainedStockReviewError(ValueError):
    pass


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise RetainedStockReviewError(detail)


def _read_bounded(path: Path) -> bytes:
    # Fixed, locally constructed filenames only. Do not follow filenames/paths in
    # reports, or scan normalized outcomes, assignments, bars, or option caches.
    _require(path.resolve().is_relative_to(path.parent.resolve()), f"linked artifact escapes its directory: {path}")
    _require(path.stat().st_size <= MAX_FILE_BYTES, f"artifact exceeds bounded read limit: {path}")
    with path.open("rb") as handle:
        raw = handle.read(MAX_FILE_BYTES + 1)
    _require(len(raw) <= MAX_FILE_BYTES, f"artifact grew beyond bounded read limit: {path}")
    return raw


def _reject_nonfinite(value: str) -> None:
    raise RetainedStockReviewError(f"nonfinite JSON value: {value}")


def _summary(root: Path, *, daily_path: bool) -> tuple[dict, list[dict], dict]:
    path = root / "analysis_summary.json"
    raw = _read_bounded(path)
    report = json.loads(raw, parse_constant=_reject_nonfinite)
    _require(isinstance(report, dict), f"summary is not an object: {path}")
    status = "COMPLETE_SELECTED_DAILY_PATH_DIAGNOSTICS_ONLY" if daily_path else "COMPLETE_OPTIONWORTHINESS_DIAGNOSTICS_ONLY"
    fingerprint_key = "selected_daily_path_fingerprint" if daily_path else "optionworthiness_fingerprint"
    expected_contract = SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT if daily_path else SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT
    expected_analysis = ACCEPTED_PATH_ANALYSIS if daily_path else ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT
    _require(report.get("status") == status and report.get(fingerprint_key) == expected_contract, f"accepted summary contract/status drifted: {path}")
    for key in ("consumed_master_rows_read", "future_blind_rows_read", "provider_calls", "broker_reads", "broker_writes"):
        _require(type(report.get(key)) is int and report[key] == 0, f"summary scope drifted: {key}")
    for key in ("confluence_opened", "paper_authority", "live_authority", "strategy_promotion", "selector_promotion", "option_trading_authority", "historical_option_pnl_claimed"):
        _require(report.get(key) is False, f"summary authority drifted: {key}")
    if not daily_path:
        for key in ("raw_market_data_reread", "historical_option_data_read"):
            _require(report.get(key) is False, f"summary authority drifted: {key}")
    outputs = report.get("outputs")
    _require(isinstance(outputs, list) and all(isinstance(row, dict) for row in outputs), "summary output inventory is malformed")
    names = [row.get("name") for row in outputs]
    _require(all(isinstance(name, str) for name in names) and len(set(names)) == len(names), "summary output names are missing/duplicated")
    output_fingerprint = canonical_sha256(outputs)
    _require(report.get("output_artifact_set_fingerprint") == output_fingerprint, "summary output inventory fingerprint drifted")
    if daily_path:
        accepted = report["accepted_optionworthiness"]
        _require(accepted["analysis_fingerprint"] == ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT, "path/option-worthiness analysis binding drifted")
        _require(report.get("path_horizon_sessions") == 5 and report.get("move_thresholds_fraction") == list(MOVE_THRESHOLDS), "daily path horizon/threshold semantics drifted")
        identity = {
            "selected_daily_path_fingerprint": expected_contract,
            "accepted_optionworthiness_analysis_fingerprint": ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT,
            "conditioning_analysis_fingerprint": report["conditioning_analysis_fingerprint"],
            "daily_source_report_fingerprint": report["daily_source_report_fingerprint"],
            "output_artifact_set_fingerprint": output_fingerprint,
        }
    else:
        binding = report["input_binding"]
        identity = {
            "optionworthiness_fingerprint": expected_contract,
            "conditioning_analysis_fingerprint": binding["conditioning_analysis_fingerprint"],
            "normalized_input_identity": binding["normalized_input_identity"],
            "eligibility_assignments_sha256": binding["eligibility_assignments_sha256"],
            "output_artifact_set_fingerprint": output_fingerprint,
        }
    _require(report.get("analysis_fingerprint") == expected_analysis == canonical_sha256(identity), f"frozen accepted analysis fingerprint drifted: {path}")
    return report, outputs, {"summary_path": str(path), "summary_sha256": hashlib.sha256(raw).hexdigest(), "analysis_fingerprint": expected_analysis}


def _aggregate(root: Path, outputs: list[dict], name: str, columns: set[str]) -> tuple[list[dict], dict]:
    matches = [row for row in outputs if row["name"] == name]
    _require(len(matches) == 1, f"accepted aggregate identity is missing: {name}")
    path = root / f"{name}.parquet"
    raw = _read_bounded(path)
    digest = hashlib.sha256(raw).hexdigest()
    _require(matches[0].get("sha256") == digest, f"accepted aggregate hash drifted: {name}")
    # Parse a disposable copy of precisely the bytes hashed above. Close its file
    # before DuckDB opens it on Windows; neither the original nor paths recorded
    # in the summary are passed to the Parquet reader. No new dependency needed.
    with tempfile.TemporaryDirectory(prefix="atlas-stock-review-") as temporary:
        snapshot = Path(temporary) / "aggregate.parquet"
        snapshot.write_bytes(raw)
        conn = duckdb.connect()
        try:
            relation = "read_parquet(?, hive_partitioning=false)"
            params = [str(snapshot)]
            schema = {row[0] for row in conn.execute(f"DESCRIBE SELECT * FROM {relation}", params).fetchall()}
            count = conn.execute(f"SELECT count(*) FROM {relation}", params).fetchone()[0]
            _require(count <= MAX_AGGREGATE_ROWS, f"not a bounded aggregate: {name}")
            _require(columns.issubset(schema), f"aggregate columns are missing: {name}")
            ordered = sorted(columns)
            projection = ", ".join(f'"{column}"' for column in ordered)
            values = conn.execute(f"SELECT {projection} FROM {relation}", params).fetchall()
            rows = [
                {column: None if isinstance(value, float) and not math.isfinite(value) else value
                 for column, value in zip(ordered, row, strict=True)}
                for row in values
            ]
        except duckdb.Error as exc:
            raise RetainedStockReviewError(f"cannot read accepted aggregate: {name}") from exc
        finally:
            conn.close()
    if "row_count" in matches[0]:
        _require(matches[0]["row_count"] == len(rows), f"accepted aggregate row count drifted: {name}")
    return rows, {"name": name, "path": str(path), "sha256": digest, "rows": len(rows), "size_bytes": len(raw)}


def _key(row: dict) -> tuple[str, str]:
    return row["policy_id"], row["direction"]


def _index(rows: list[dict], key: Callable) -> dict:
    result = {key(row): row for row in rows}
    _require(len(result) == len(rows), "duplicate aggregate keys")
    return result


def _close(left: float, right: float, detail: str) -> None:
    _require(math.isfinite(left) and math.isfinite(right) and math.isclose(left, right, abs_tol=1e-10, rel_tol=1e-8), detail)


def _weighted(rows: list[dict], count: str, metric: str) -> float | None:
    total = sum(row[count] for row in rows)
    return sum(row[count] * row[metric] for row in rows) / total if total else None


def reconcile_aggregates(inventory: list[dict], returns: list[dict], folds: list[dict], paths: list[dict], thresholds: list[dict]) -> dict:
    """All observed directions are retained, including losses and zero selections."""
    policies = _index(inventory, lambda row: row["policy_id"])
    _require(all(row["subset"] in ANALYSIS_SUBSETS and row["policy_id"] in policies for row in returns), "unexpected return subset/policy")
    returns_by_key = _index(returns, lambda row: (row["subset"], *_key(row)))
    _index(folds, lambda row: (row["fold_id"], *_key(row)))
    paths_by_key = _index(paths, _key)
    thresholds_by_key = _index(thresholds, lambda row: (*_key(row), row["move_threshold"]))
    selected = [row for row in returns if row["subset"] == SELECTED]
    selected_keys = {_key(row) for row in selected}
    _require({_key(row) for row in folds} == selected_keys, "selected return/fold population differs")
    daily_keys = {_key(row) for row in selected if row["native_timeframe"] == "1d"}
    _require(set(paths_by_key) == daily_keys, "five-session path population differs from selected daily returns")
    _require(set(thresholds_by_key) == {(*key, value) for key in daily_keys for value in MOVE_THRESHOLDS}, "five-session threshold population differs")
    routes = []
    for key in sorted({_key(row) for row in returns}):
        policy, direction = key
        meta = policies[policy]
        _require(direction in ("LONG", "SHORT") and meta["native_timeframe"] in ("1d", "1m"), "unsupported route direction/timeframe")
        subsets = {subset: returns_by_key.get((subset, *key)) for subset in ANALYSIS_SUBSETS}
        for subset, row in subsets.items():
            if row is None:
                continue
            _require(row["economic_family_id"] == meta["economic_family_id"] and row["native_timeframe"] == meta["native_timeframe"], "route identity differs across aggregates")
            excursion = "THROUGH_20_SESSIONS" if meta["native_timeframe"] == "1d" else "ENTRY_TO_ACTUAL_EXIT"
            _require(row["excursion_window"] == excursion, "baseline excursion horizon drifted")
            _require(type(row["comparable_opportunities"]) is int and row["comparable_opportunities"] > 0, "invalid comparable count")
            _require(all(isinstance(row[metric], (int, float)) and math.isfinite(row[metric]) for metric in ("mean_gross_return", "mean_primary_net_return", "mean_stress_net_return")), "invalid return mean")
        selection = subsets[SELECTED]
        test = subsets[TEST]
        _require(subsets[ALL] is not None and (selection is None or test is not None), "selected/test route is absent from its parent population")
        _require(subsets[ALL]["comparable_opportunities"] >= (test["comparable_opportunities"] if test else 0) >= (selection["comparable_opportunities"] if selection else 0), "route subset count ordering drifted")
        route_folds = [row for row in folds if _key(row) == key]
        for fold in route_folds:
            _require(fold["economic_family_id"] == meta["economic_family_id"] and fold["native_timeframe"] == meta["native_timeframe"], "fold route identity differs")
            _require(type(fold["selected_comparable"]) is int and fold["selected_comparable"] > 0, "invalid fold count")
        count = selection["comparable_opportunities"] if selection else 0
        _require(sum(row["selected_comparable"] for row in route_folds) == count, "selected route/fold counts do not reconcile")
        if selection:
            for metric in ("mean_primary_net_return", "mean_stress_net_return"):
                _close(_weighted(route_folds, "selected_comparable", metric), selection[metric], f"selected route/fold {metric} does not reconcile")
        primary_cost, stress_cost = (DAILY_PRIMARY_COST_BPS, DAILY_STRESS_COST_BPS) if meta["native_timeframe"] == "1d" else (INTRADAY_PRIMARY_COST_BPS, INTRADAY_STRESS_COST_BPS)
        path = paths_by_key.get(key)
        first_touch = []
        if path:
            _require(path["economic_family_id"] == meta["economic_family_id"] and path["selected_comparable"] == count and path["active_folds"] == len(route_folds), "daily path route/count/folds do not reconcile")
            for metric in ("primary", "stress"):
                _close(path[f"retained_mean_{metric}_net_return"], selection[f"mean_{metric}_net_return"], "daily path retained return does not reconcile")
            for value in MOVE_THRESHOLDS:
                touch = thresholds_by_key[(*key, value)]
                _require(touch["selected_comparable"] == count, "threshold/path count does not reconcile")
                rate_keys = ("favorable_hit_rate_5", "adverse_hit_rate_5", "favorable_before_adverse_rate", "adverse_before_favorable_rate", "same_session_collision_rate")
                _require(all(isinstance(touch[name], (int, float)) and math.isfinite(touch[name]) and 0 <= touch[name] <= 1 for name in rate_keys), "invalid first-touch rate")
                classified = sum(touch[name] for name in rate_keys[2:])
                _require(classified <= 1 + 1e-10, "first-touch classes overlap")
                first_touch.append({"move_threshold": value, **{name: touch[name] for name in rate_keys}, "neither_rate": max(0.0, 1.0 - classified)})
        routes.append({
            "policy_id": policy, "economic_family_id": meta["economic_family_id"], "native_timeframe": meta["native_timeframe"], "direction": direction,
            "return_subsets": subsets,
            "selected_comparable": count,
            "selection_rate_of_test_comparable": count / test["comparable_opportunities"] if test else None,
            "cost_assumptions_bps": {"primary": primary_cost, "stress": stress_cost},
            "selected_observed_primary_cost_drag_bps": (selection["mean_gross_return"] - selection["mean_primary_net_return"]) * 10_000 if selection else None,
            "selected_gross_positive_primary_nonpositive": selection["mean_gross_return"] > 0 >= selection["mean_primary_net_return"] if selection else None,
            "fold_consistency": {
                "active_folds": len(route_folds),
                "positive_primary_folds": sum(row["mean_primary_net_return"] > 0 for row in route_folds),
                "negative_primary_folds": sum(row["mean_primary_net_return"] < 0 for row in route_folds),
                "flat_primary_folds": sum(row["mean_primary_net_return"] == 0 for row in route_folds),
                "largest_fold_share": max((row["selected_comparable"] for row in route_folds), default=0) / count if count else None,
            },
            "selected_folds": sorted(route_folds, key=lambda row: row["fold_id"]),
            "five_session_path": path,
            "five_session_first_touch": first_touch,
        })
    for policy, meta in policies.items():
        policy_rows = [row for row in returns if row["policy_id"] == policy]
        for subset, field in ((ALL, "standalone_comparable"), (TEST, "walk_forward_test_comparable"), (SELECTED, "selected_comparable")):
            _require(sum(row["comparable_opportunities"] for row in policy_rows if row["subset"] == subset) == meta[field], f"inventory/subset counts do not reconcile: {policy}/{subset}")
        _require(0 <= meta["selected_comparable"] <= meta["selected_records"] <= meta["walk_forward_test_records"] <= meta["standalone_records"], "inventory count ordering drifted")
    fold_totals = []
    for fold_id in sorted({row["fold_id"] for row in folds}):
        rows = [row for row in folds if row["fold_id"] == fold_id]
        fold_totals.append({"fold_id": fold_id, "selected_comparable": sum(row["selected_comparable"] for row in rows), "mean_primary_net_return": _weighted(rows, "selected_comparable", "mean_primary_net_return"), "mean_stress_net_return": _weighted(rows, "selected_comparable", "mean_stress_net_return")})
    return {
        "strategy_inventory": sorted(inventory, key=lambda row: row["policy_id"]), "route_directions": routes,
        "selected_fold_totals": fold_totals,
        "totals": {
            "policy_routes": len(policies), "economic_families": len({row["economic_family_id"] for row in inventory}),
            "standalone_records": sum(row["standalone_records"] for row in inventory),
            "test_records": sum(row["walk_forward_test_records"] for row in inventory),
            "selected_records": sum(row["selected_records"] for row in inventory),
            "selected_comparable": sum(row["comparable_opportunities"] for row in selected),
            "selected_daily_comparable": sum(row["selected_comparable"] for row in paths),
            "selected_mean_primary_net_return": _weighted(selected, "comparable_opportunities", "mean_primary_net_return"),
            "selected_mean_stress_net_return": _weighted(selected, "comparable_opportunities", "mean_stress_net_return"),
            "active_folds": len(fold_totals),
            "positive_primary_folds": sum(row["mean_primary_net_return"] > 0 for row in fold_totals),
            "negative_primary_folds": sum(row["mean_primary_net_return"] < 0 for row in fold_totals),
        },
    }


def build_retained_stock_review(settings: AtlasSettings, progress: Callable[[str], None] | None = None) -> dict:
    notify = progress or (lambda detail: None)
    stock_root = settings.resolved_path(OPTIONWORTHINESS_ROOT)
    path_root = settings.resolved_path(PATH_ROOT)
    notify("checking two frozen summaries")
    stock, stock_outputs, stock_binding = _summary(stock_root, daily_path=False)
    path, path_outputs, path_binding = _summary(path_root, daily_path=True)
    _require(path["conditioning_analysis_fingerprint"] == stock["input_binding"]["conditioning_analysis_fingerprint"], "path/stock conditioning lineage differs")
    _require(path["accepted_optionworthiness"]["summary_sha256"] == stock_binding["summary_sha256"] and path["accepted_optionworthiness"]["output_artifact_set_fingerprint"] == stock["output_artifact_set_fingerprint"], "path/stock summary lineage differs")
    route_identity = {"policy_id", "economic_family_id", "native_timeframe", "direction"}
    metrics = {"mean_gross_return", "mean_primary_net_return", "mean_stress_net_return"}
    specs = (
        (stock_root, stock_outputs, "strategy_inventory", {"policy_id", "economic_family_id", "native_timeframe", "standalone_records", "standalone_comparable", "walk_forward_test_records", "walk_forward_test_comparable", "selected_records", "selected_comparable"}),
        (stock_root, stock_outputs, "route_summary", route_identity | metrics | {"subset", "comparable_opportunities", "unique_sessions", "unique_instruments", "primary_win_rate", "median_primary_net_return", "mean_mfe", "mean_mae", "excursion_window"}),
        (stock_root, stock_outputs, "selected_fold_summary", route_identity | {"fold_id", "selected_comparable", "mean_primary_net_return", "mean_stress_net_return", "unique_sessions", "unique_instruments"}),
        (path_root, path_outputs, "route_path_summary", {"policy_id", "economic_family_id", "direction", "selected_comparable", "active_folds", "mean_gross_return_5", "median_gross_return_5", "mean_mfe_5", "mean_adverse_excursion_5", "median_exit_capture_ratio", "mean_peak_giveback", "retained_mean_primary_net_return", "retained_mean_stress_net_return"}),
        (path_root, path_outputs, "route_threshold_summary", {"policy_id", "direction", "move_threshold", "selected_comparable", "favorable_hit_rate_5", "adverse_hit_rate_5", "favorable_before_adverse_rate", "adverse_before_favorable_rate", "same_session_collision_rate"}),
    )
    tables, bindings = [], []
    for index, (root, outputs, name, columns) in enumerate(specs, 1):
        notify(f"verifying aggregate {index}/{len(specs)}: {name}")
        rows, binding = _aggregate(root, outputs, name, columns)
        tables.append(rows)
        bindings.append(binding)
    result = reconcile_aggregates(*tables)
    totals = result["totals"]
    for key, expected in {"policy_routes": 28, "economic_families": 21, "standalone_records": ACCEPTED_STANDALONE_RECORD_COUNT, "test_records": 45_516_323, "selected_records": 36_259, "selected_comparable": 36_254, "selected_daily_comparable": 35_995, "active_folds": 33}.items():
        _require(totals[key] == expected, f"accepted population drifted: {key}")
    for subset, key in ((ALL, "development_all_comparable"), (TEST, "walk_forward_test_comparable"), (SELECTED, "walk_forward_selected_comparable")):
        observed = sum(row["comparable_opportunities"] for row in tables[1] if row["subset"] == subset)
        _require(stock["scope_counts"][key] == observed, f"summary/subset counts do not reconcile: {key}")
    _require(path["selected_daily_comparable"] == totals["selected_daily_comparable"], "summary/path count differs")
    result.update({
        "contract": CONTRACT, "status": "COMPLETE_RETAINED_STOCK_AGGREGATE_REVIEW", "generated_utc": datetime.now(UTC).isoformat(),
        "input_binding": {"stock_summary": stock_binding, "path_summary": path_binding, "verified_aggregates": bindings, "verification_scope": "TWO_FROZEN_ANALYSIS_IDENTITIES_AND_FIVE_AGGREGATE_CONTENT_HASHES_ONLY"},
        "semantics": {"daily_primary_return_horizon_sessions": 5, "baseline_daily_excursion_horizon_sessions": 20, "selected_daily_path_horizon_sessions": 5, "first_touch_resolution": "SESSION_ONLY_SAME_SESSION_COLLISIONS_UNORDERED", "fold_resolution": "FROZEN_63_SESSION_TEST_FOLDS", "portfolio_return": None, "weekly_monthly_annual_account_returns": None},
        "authority": {"provider_requests": 0, "broker_requests": 0, "raw_bar_scans": 0, "raw_quote_scans": 0, "normalized_outcome_scans": 0, "simulations_run": 0, "consumed_master_rows_read": 0, "future_blind_rows_read": 0, "strategy_rule_changes": False, "source_reacceptance": False, "strategy_promotion": False, "paper_authority": False, "live_authority": False},
        "limitations": [
            "Descriptive DEVELOPMENT evidence, including all recorded losses; positive post-result slices do not validate a new filter or strategy.",
            "Aggregate content is verified against frozen accepted analyses; their large upstream sources are not revalidated or reread.",
            "Trade means and fold means are not a compounded account; overlapping opportunities, borrow, allocation and execution remain separate.",
            "Five-session path extrema do not establish intraday order, executable exits or option profit; baseline daily MFE/MAE covers 20 sessions.",
            "Week/month/year account windows and regime-specific acceptance cannot be reconstructed from these route/fold aggregates.",
        ],
    })
    result["report_fingerprint"] = canonical_sha256(result)
    notify("aggregate reconciliation complete")
    return result
