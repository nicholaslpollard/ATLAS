from __future__ import annotations

import copy
import hashlib
import json
import urllib.request
from decimal import Decimal
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from packages.backtesting import retained_stock_review_v1 as review
from packages.backtesting.successor_runner_contract import canonical_sha256
from packages.core.settings import load_settings
from scripts import review_retained_stock_results_v1 as command


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def accepted_aggregates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Small aggregate fixtures describe large counts without constructing source rows."""
    monkeypatch.delenv("ATLAS_EXTERNAL_DATA_ROOT", raising=False)
    settings = load_settings(ROOT, "development").model_copy(update={"project_root": tmp_path})
    stock_root = tmp_path / review.OPTIONWORTHINESS_ROOT
    path_root = tmp_path / review.PATH_ROOT
    inventory, returns, folds, paths, thresholds = [], [], [], [], []
    for index in range(28):
        policy, family = f"policy_{index:02d}", f"family_{index % 21:02d}"
        daily = index != 1
        count = 35_995 if index == 0 else (259 if index == 1 else 0)
        standalone = 54_618_427 // 28 + (index < 54_618_427 % 28)
        test = 45_907_526 // 28 + (index < 45_907_526 % 28)
        inventory.append({"policy_id": policy, "economic_family_id": family, "native_timeframe": "1d" if daily else "1m", "standalone_records": standalone, "standalone_comparable": standalone, "walk_forward_test_records": test, "walk_forward_test_comparable": test, "selected_records": count + (3 if index == 0 else 2 if index == 1 else 0), "selected_comparable": count})
        # The daily route has positive gross but negative cost-adjusted returns;
        # the minute route has negative gross already. Other routes abstain.
        gross, primary, stress = (0.0005, -0.0005, -0.002) if daily else (-0.01, -0.015, -0.02)
        row = {"policy_id": policy, "economic_family_id": family, "native_timeframe": "1d" if daily else "1m", "direction": "LONG", "unique_sessions": 100, "unique_instruments": 30, "primary_win_rate": 0.4, "mean_gross_return": gross, "mean_primary_net_return": primary, "mean_stress_net_return": stress, "median_primary_net_return": -0.01, "mean_mfe": 0.1, "mean_mae": -0.06, "excursion_window": "THROUGH_20_SESSIONS" if daily else "ENTRY_TO_ACTUAL_EXIT"}
        for subset, observations in ((review.ALL, standalone), (review.TEST, test)):
            returns.append({**row, "subset": subset, "comparable_opportunities": observations})
        if not count:
            continue
        returns.append({**row, "subset": review.SELECTED, "comparable_opportunities": count})
        for fold_id in range(33):
            observations = count // 33 + (fold_id < count % 33)
            folds.append({key: row[key] for key in ("policy_id", "economic_family_id", "native_timeframe", "direction", "mean_primary_net_return", "mean_stress_net_return", "primary_win_rate", "mean_mfe", "mean_mae", "unique_sessions", "unique_instruments")} | {"fold_id": fold_id, "selected_comparable": observations})
        if not daily:
            continue
        paths.append({"policy_id": policy, "economic_family_id": family, "direction": "LONG", "selected_comparable": count, "active_folds": 33, "mean_gross_return_5": gross, "median_gross_return_5": -0.01, "mean_mfe_5": 0.03, "mean_adverse_excursion_5": 0.025, "median_exit_capture_ratio": 0.1, "mean_peak_giveback": 0.0295, "retained_mean_primary_net_return": primary, "retained_mean_stress_net_return": stress})
        for value in review.MOVE_THRESHOLDS:
            thresholds.append({"policy_id": policy, "direction": "LONG", "move_threshold": value, "selected_comparable": count, "favorable_hit_rate_5": 0.7, "adverse_hit_rate_5": 0.6, "favorable_before_adverse_rate": 0.3, "adverse_before_favorable_rate": 0.2, "same_session_collision_rate": 0.4})

    def publish(root: Path, tables: dict[str, list[dict]]) -> list[dict]:
        root.mkdir(parents=True, exist_ok=True)
        identities = []
        for name, rows in sorted(tables.items()):
            target = root / f"{name}.parquet"
            conn = duckdb.connect()
            try:
                conn.register("records", pd.DataFrame(rows))
                locator = str(target).replace("\\", "/").replace("'", "''")
                query = "SELECT * FROM records"
                if "move_threshold" in rows[0]:
                    query = "SELECT * EXCLUDE(move_threshold), CAST(move_threshold AS DECIMAL(9,8)) AS move_threshold FROM records"
                conn.execute(f"COPY ({query}) TO '{locator}' (FORMAT PARQUET)")
            finally:
                conn.close()
            identity = {"name": name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
            if root == stock_root:
                identity["row_count"] = len(rows)
            else:
                # Recorded source locators must never become paths to open.
                identity["path"] = f"C:/original-workstation/{name}.parquet"
            identities.append(identity)
        return identities

    stability, curve, diagnostics = [], [], []
    for row in returns:
        for value in review.MOVE_THRESHOLDS:
            curve.append({key: row[key] for key in ("policy_id", "economic_family_id", "native_timeframe", "direction", "subset")} | {"move_threshold": value, "favorable_excursion_hit_rate": 0.7, "adverse_excursion_breach_rate": 0.6})
        if row["subset"] != review.SELECTED:
            continue
        route_folds = [fold for fold in folds if review._key(fold) == review._key(row)]
        stable = {key: row[key] for key in ("policy_id", "economic_family_id", "native_timeframe", "direction")} | {"active_folds": 33, "positive_primary_folds": 0, "negative_primary_folds": 33, "selected_comparable": row["comparable_opportunities"], "largest_fold_share": max(fold["selected_comparable"] for fold in route_folds) / row["comparable_opportunities"]}
        stability.append(stable)
        diagnostic = {**row, **stable}
        for value in review.MOVE_THRESHOLDS:
            diagnostic[f"p_mfe_ge_{int(value*100)}pct"] = 0.7
            diagnostic[f"p_mae_le_m{int(value*100)}pct"] = 0.6
        diagnostics.append(diagnostic)
    stock_outputs = publish(stock_root, {"strategy_inventory": inventory, "route_summary": returns, "selected_fold_summary": folds, "route_stability": stability, "move_threshold_curve": curve})
    path_outputs = publish(path_root, {"route_path_summary": paths, "route_threshold_summary": thresholds})
    authority = {**{key: 0 for key in ("consumed_master_rows_read", "future_blind_rows_read", "provider_calls", "broker_reads", "broker_writes")}, **{key: False for key in ("confluence_opened", "paper_authority", "live_authority", "strategy_promotion", "selector_promotion", "option_trading_authority", "historical_option_pnl_claimed")}}
    binding = {key: str(index) * 64 for index, key in enumerate(("conditioning_analysis_fingerprint", "normalized_input_identity", "eligibility_assignments_sha256"))}
    stock = {**authority, "status": "COMPLETE_OPTIONWORTHINESS_DIAGNOSTICS_ONLY", "optionworthiness_fingerprint": review.SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT, "input_binding": binding, "outputs": stock_outputs, "output_artifact_set_fingerprint": canonical_sha256(stock_outputs), "raw_market_data_reread": False, "historical_option_data_read": False, "scope_counts": {"development_all_comparable": 54_618_427, "walk_forward_test_comparable": 45_907_526, "walk_forward_selected_comparable": 36_254}}
    stock["analysis_fingerprint"] = canonical_sha256({"optionworthiness_fingerprint": review.SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT, **binding, "output_artifact_set_fingerprint": stock["output_artifact_set_fingerprint"]})
    binding["eligibility_assignments_rows"] = 45_907_526
    stock["selected_route_diagnostics"] = diagnostics
    monkeypatch.setattr(review, "ACCEPTED_OPTIONWORTHINESS_ANALYSIS_FINGERPRINT", stock["analysis_fingerprint"])
    stock_file = stock_root / "analysis_summary.json"
    stock_file.write_text(json.dumps(stock), encoding="utf-8")
    monkeypatch.setattr(review, "ACCEPTED_STOCK_SUMMARY_SHA256", hashlib.sha256(stock_file.read_bytes()).hexdigest())
    path = {**authority, "status": "COMPLETE_SELECTED_DAILY_PATH_DIAGNOSTICS_ONLY", "selected_daily_path_fingerprint": review.SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT, "conditioning_analysis_fingerprint": binding["conditioning_analysis_fingerprint"], "daily_source_report_fingerprint": "4" * 64, "accepted_optionworthiness": {"analysis_fingerprint": stock["analysis_fingerprint"], "output_artifact_set_fingerprint": stock["output_artifact_set_fingerprint"], "summary_sha256": hashlib.sha256(stock_file.read_bytes()).hexdigest()}, "outputs": path_outputs, "output_artifact_set_fingerprint": canonical_sha256(path_outputs), "path_horizon_sessions": 5, "selected_daily_comparable": 35_995, "move_thresholds_fraction": list(review.MOVE_THRESHOLDS)}
    path["analysis_fingerprint"] = canonical_sha256({"selected_daily_path_fingerprint": review.SUCCESSOR_SELECTED_DAILY_PATH_FINGERPRINT, "accepted_optionworthiness_analysis_fingerprint": stock["analysis_fingerprint"], "conditioning_analysis_fingerprint": path["conditioning_analysis_fingerprint"], "daily_source_report_fingerprint": path["daily_source_report_fingerprint"], "output_artifact_set_fingerprint": path["output_artifact_set_fingerprint"]})
    monkeypatch.setattr(review, "ACCEPTED_PATH_ANALYSIS", path["analysis_fingerprint"])
    path_file = path_root / "analysis_summary.json"
    path_file.write_text(json.dumps(path), encoding="utf-8")
    monkeypatch.setattr(review, "ACCEPTED_PATH_SUMMARY_SHA256", hashlib.sha256(path_file.read_bytes()).hexdigest())
    return settings, (inventory, returns, folds, paths, thresholds), stock_file, path_file


def test_review_reads_only_bound_aggregates_keeps_losses_and_abstaining_routes(accepted_aggregates, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, tables, stock_file, path_file = accepted_aggregates
    expected = {stock_file, path_file, *(stock_file.parent / f"{name}.parquet" for name in ("strategy_inventory", "route_summary", "selected_fold_summary")), *path_file.parent.glob("*.parquet")}
    before = {path: path.read_bytes() for path in expected}
    opened = []
    reader = review._read_bounded

    def checked(path):
        assert path in expected, f"unexpected source read: {path}"
        opened.append(path)
        return reader(path)

    def forbidden(*args, **kwargs):
        raise AssertionError("provider access attempted")

    monkeypatch.setattr(review, "_read_bounded", checked)
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    report = review.build_retained_stock_review(settings)
    assert set(opened) == expected and len(opened) == 7
    assert all(path.read_bytes() == raw for path, raw in before.items())
    assert len(report["route_directions"]) == 28
    assert sum(row["selected_comparable"] == 0 for row in report["route_directions"]) == 26
    assert report["totals"]["selected_comparable"] == 36_254
    assert report["totals"]["negative_primary_folds"] == 33
    daily, minute = report["route_directions"][:2]
    assert daily["selected_gross_positive_primary_nonpositive"] is True
    assert daily["selected_observed_primary_cost_drag_bps"] == pytest.approx(10)
    assert minute["selected_gross_positive_primary_nonpositive"] is False
    assert daily["five_session_path"]["mean_mfe_5"] == 0.03
    assert daily["return_subsets"][review.SELECTED]["mean_mfe"] == 0.1
    assert daily["five_session_first_touch"][0]["neither_rate"] == pytest.approx(0.1)
    assert daily["five_session_first_touch"][0]["same_session_collision_rate"] == 0.4
    assert report["semantics"]["portfolio_return"] is None
    assert report["semantics"]["weekly_monthly_annual_account_returns"] is None
    assert report["authority"]["normalized_outcome_scans"] == 0
    fingerprint = report.pop("report_fingerprint")
    assert fingerprint == canonical_sha256(report)


def test_tampered_aggregate_is_blocked_before_parquet_parse(accepted_aggregates) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    target = stock_file.parent / "route_summary.parquet"
    target.write_bytes(target.read_bytes() + b"altered")
    with pytest.raises(review.RetainedStockReviewError, match="aggregate hash drifted"):
        review.build_retained_stock_review(settings)


def test_self_consistent_new_output_identity_cannot_replace_frozen_analysis(accepted_aggregates) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    payload = json.loads(stock_file.read_text())
    payload["outputs"][0]["sha256"] = "f" * 64
    payload["output_artifact_set_fingerprint"] = canonical_sha256(payload["outputs"])
    stock_file.write_text(json.dumps(payload))
    with pytest.raises(review.RetainedStockReviewError, match="frozen accepted analysis fingerprint drifted"):
        review.build_retained_stock_review(settings)


def test_summary_change_outside_scientific_identity_breaks_original_path_binding(accepted_aggregates) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    payload = json.loads(stock_file.read_text())
    payload["unbound_note"] = "modified"
    stock_file.write_text(json.dumps(payload))
    with pytest.raises(review.RetainedStockReviewError, match="summary lineage differs"):
        review.build_retained_stock_review(settings)


@pytest.mark.parametrize("change,reason", [
    ("duplicate", "duplicate aggregate keys"),
    ("fold_count", "route/fold counts"),
    ("fold_mean", "route/fold mean_primary"),
    ("path_count", "path route/count/folds"),
    ("collision", "first-touch classes overlap"),
    ("nonfinite", "invalid return mean"),
    ("inventory", "inventory/subset counts"),
])
def test_reconciliation_rejects_population_drift_and_unresolved_semantics(accepted_aggregates, change: str, reason: str) -> None:
    _, originals, _, _ = accepted_aggregates
    tables = copy.deepcopy(originals)
    if change == "duplicate":
        tables[1].append(copy.deepcopy(tables[1][0]))
    elif change == "fold_count":
        tables[2][0]["selected_comparable"] += 1
    elif change == "fold_mean":
        tables[2][0]["mean_primary_net_return"] += 0.1
    elif change == "path_count":
        tables[3][0]["selected_comparable"] -= 1
    elif change == "collision":
        tables[4][0]["same_session_collision_rate"] = 1.0
    elif change == "nonfinite":
        tables[1][0]["mean_gross_return"] = float("nan")
    elif change == "inventory":
        tables[0][0]["standalone_comparable"] += 1
    with pytest.raises(review.RetainedStockReviewError, match=reason):
        review.reconcile_aggregates(*tables)


def test_bounded_reader_and_row_limit_fail_closed(accepted_aggregates, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    monkeypatch.setattr(review, "MAX_FILE_BYTES", 10)
    with pytest.raises(review.RetainedStockReviewError, match="bounded read limit"):
        review.build_retained_stock_review(settings)
    monkeypatch.setattr(review, "MAX_FILE_BYTES", 8 * 1024 * 1024)
    monkeypatch.setattr(review, "MAX_AGGREGATE_ROWS", 2)
    with pytest.raises(review.RetainedStockReviewError, match="not a bounded aggregate"):
        review.build_retained_stock_review(settings)


def test_command_is_read_only_and_save_creates_only_new_reviews(accepted_aggregates, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    settings, _, _, _ = accepted_aggregates
    monkeypatch.setattr(command, "load_settings", lambda *args: settings)
    before = set(settings.project_root.rglob("*"))
    assert command.main([]) == 0
    assert set(settings.project_root.rglob("*")) == before
    assert command.main(["--save-report"]) == 0
    assert command.main(["--save-report"]) == 0
    files = list((settings.project_root / "data/research/retained_stock_review_v1").glob("*.json"))
    assert len(files) == 2
    assert all(json.loads(path.read_text())["authority"]["simulations_run"] == 0 for path in files)
    assert "account and week/month/year returns: not computed" in capsys.readouterr().out


def test_command_missing_input_does_not_rebuild_or_save(accepted_aggregates, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    (stock_file.parent / "route_summary.parquet").unlink()
    monkeypatch.setattr(command, "load_settings", lambda *args: settings)
    assert command.main(["--save-report"]) == 3
    assert not (settings.project_root / "data/research/retained_stock_review_v1").exists()
    assert "BLOCKED" in capsys.readouterr().out


def test_selected_mode_uses_pinned_summary_and_never_opens_changed_route_cache(accepted_aggregates, monkeypatch: pytest.MonkeyPatch) -> None:
    settings, _, stock_file, path_file = accepted_aggregates
    bad_cache = stock_file.parent / "route_summary.parquet"
    bad_cache.write_bytes(b"DIFFERENT_BYTES_DO_NOT_USE")
    reader = review._read_bounded
    opened = []

    def checked(path):
        assert path != bad_cache, "selected review opened the rejected route cache"
        opened.append(path)
        return reader(path)

    monkeypatch.setattr(review, "_read_bounded", checked)
    report = review.build_retained_stock_review(settings, selected_only=True)
    assert len(opened) == 8  # Two full-summary snapshots and six matching aggregates.
    assert report["status"] == "COMPLETE_VERIFIED_SELECTED_STOCK_REVIEW"
    assert len(report["route_directions"]) == 28
    assert report["totals"]["selected_comparable"] == 36_254
    assert sum(row["selected_comparable"] == 0 for row in report["route_directions"]) == 26
    for row in report["route_directions"]:
        assert row["return_subsets"][review.ALL] is None
        assert row["return_subsets"][review.TEST] is None
        assert row["selection_rate_of_test_comparable"] is None
    assert report["excluded_inputs"][0]["used_for_results"] is False
    assert bad_cache.read_bytes() == b"DIFFERENT_BYTES_DO_NOT_USE"
    assert report["route_directions"][0]["five_session_first_touch"][0]["move_threshold"] == 0.01


@pytest.mark.parametrize("kind", ["stock", "path"])
def test_selected_mode_rejects_semantic_summary_edits_outside_analysis_fingerprint(accepted_aggregates, kind: str) -> None:
    settings, _, stock_file, path_file = accepted_aggregates
    target = stock_file if kind == "stock" else path_file
    payload = json.loads(target.read_text())
    payload["unsealed_extra"] = "changed"
    target.write_text(json.dumps(payload))
    if kind == "stock":
        # Preserve the old analysis/linkage fields so the new content pin is the
        # check rejecting the altered snapshot, rather than an incidental link.
        path_payload = json.loads(path_file.read_text())
        path_payload["accepted_optionworthiness"]["summary_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        path_file.write_text(json.dumps(path_payload))
    with pytest.raises(review.RetainedStockReviewError, match="content hash drifted"):
        review.build_retained_stock_review(settings, selected_only=True)


def test_selected_mode_rejects_bad_verified_input_and_default_still_rejects_route_cache(accepted_aggregates) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    target = stock_file.parent / "route_summary.parquet"
    target.write_bytes(b"bad route")
    with pytest.raises(review.RetainedStockReviewError, match="aggregate hash drifted: route_summary"):
        review.build_retained_stock_review(settings)
    folds = stock_file.parent / "selected_fold_summary.parquet"
    folds.write_bytes(folds.read_bytes() + b"changed")
    with pytest.raises(review.RetainedStockReviewError, match="aggregate hash drifted: selected_fold_summary"):
        review.build_retained_stock_review(settings, selected_only=True)


def test_exact_decimal_thresholds_are_supported_and_other_grids_are_rejected() -> None:
    rows = [{"move_threshold": Decimal("0.01000000")}, {"move_threshold": Decimal("0.05000000")}]
    assert [row["move_threshold"] for row in review._threshold_rows(rows)] == [0.01, 0.05]
    assert isinstance(rows[0]["move_threshold"], Decimal)
    for value in (Decimal("0.010000001"), Decimal("NaN"), "invalid"):
        with pytest.raises(review.RetainedStockReviewError):
            review._threshold_rows([{"move_threshold": value}])


def test_selected_command_reports_reduced_scope_and_writes_only_new_report(accepted_aggregates, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    settings, _, stock_file, _ = accepted_aggregates
    (stock_file.parent / "route_summary.parquet").unlink()
    monkeypatch.setattr(command, "load_settings", lambda *args: settings)
    assert command.main(["--selected-only", "--save-report"]) == 0
    paths = list((settings.project_root / "data/research/retained_stock_review_v1").glob("*.json"))
    assert len(paths) == 1
    report = json.loads(paths[0].read_text())
    assert report["status"] == "COMPLETE_VERIFIED_SELECTED_STOCK_REVIEW"
    assert report["semantics"]["portfolio_return"] is None
    assert "full DEVELOPMENT/test route returns: unavailable" in capsys.readouterr().out
