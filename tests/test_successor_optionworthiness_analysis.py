from __future__ import annotations

import duckdb

from packages.backtesting.successor_optionworthiness_analysis import (
    _install_assigned_view,
    route_stability_sql,
    selected_route_diagnostics,
    route_summary_sql,
    selected_fold_summary_sql,
    threshold_curve_sql,
)
from packages.strategies.successor_optionworthiness_contract import (
    AUTHORITY,
    MOVE_THRESHOLDS,
    SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT,
    successor_optionworthiness_manifest,
)


def _install_synthetic_tables(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(
        """
        CREATE TABLE opportunities(
            policy_id VARCHAR,
            economic_family_id VARCHAR,
            native_timeframe VARCHAR,
            instrument_key VARCHAR,
            session_date DATE,
            direction VARCHAR,
            comparable BOOLEAN,
            gross_return DOUBLE,
            primary_net_return DOUBLE,
            stress_net_return DOUBLE,
            mfe DOUBLE,
            mae DOUBLE,
            holding_minutes INTEGER,
            daily_h1_primary DOUBLE,
            daily_h20_primary DOUBLE
        )
        """
    )
    conn.execute(
        """
        INSERT INTO opportunities VALUES
          ('daily_policy','daily_family','1d','iid-1',DATE '2020-01-02','LONG',true,0.030,0.029,0.0275,0.060,-0.020,NULL,0.009,0.039),
          ('daily_policy','daily_family','1d','iid-2',DATE '2020-01-03','LONG',true,-0.010,-0.011,-0.0125,0.015,-0.040,NULL,-0.011,-0.021),
          ('minute_policy','minute_family','1m','AAA',DATE '2020-01-02','LONG',true,0.020,0.015,0.0100,0.040,-0.010,30,NULL,NULL),
          ('minute_policy','minute_family','1m','BBB',DATE '2020-01-03','LONG',true,-0.010,-0.015,-0.0200,0.005,-0.030,45,NULL,NULL)
        """
    )
    conn.execute(
        """
        CREATE TABLE eligibility_assignments(
            fold_id INTEGER,
            policy_id VARCHAR,
            native_timeframe VARCHAR,
            instrument_key VARCHAR,
            session_date DATE,
            direction VARCHAR,
            comparable BOOLEAN,
            fallback_level INTEGER,
            selector_score DOUBLE,
            research_eligible BOOLEAN
        )
        """
    )
    conn.execute(
        """
        INSERT INTO eligibility_assignments VALUES
          (1,'daily_policy','1d','iid-1',DATE '2020-01-02','LONG',true,1,0.001,true),
          (1,'daily_policy','1d','iid-2',DATE '2020-01-03','LONG',true,1,-0.001,false),
          (1,'minute_policy','1m','AAA',DATE '2020-01-02','LONG',true,1,0.001,true),
          (1,'minute_policy','1m','BBB',DATE '2020-01-03','LONG',true,1,-0.001,false)
        """
    )
    _install_assigned_view(conn)


def test_optionworthiness_contract_is_descriptive_and_no_authority() -> None:
    manifest = successor_optionworthiness_manifest()
    assert len(SUCCESSOR_OPTIONWORTHINESS_FINGERPRINT) == 64
    assert tuple(manifest["move_thresholds_fraction"]) == MOVE_THRESHOLDS
    assert manifest["interpretation"]["descriptive_only"] is True
    assert manifest["interpretation"]["no_composite_optionworthiness_score"] is True
    unavailable = manifest["explicitly_unavailable_from_retained_artifacts"]
    assert "exact_time_to_1_2_3_5_percent_favorable_move" in unavailable
    assert "atr_normalized_1atr_2atr_favorable_move_frequency" in unavailable
    assert "historical_option_pnl" in unavailable
    assert AUTHORITY["consumed_master_rows_permitted"] == 0
    assert AUTHORITY["future_blind_rows_permitted"] == 0
    assert AUTHORITY["paper_authority"] is False
    assert AUTHORITY["live_authority"] is False
    assert AUTHORITY["option_trading_authority"] is False
    assert AUTHORITY["confluence_opened"] is False


def test_route_summary_separates_all_test_and_selected() -> None:
    conn = duckdb.connect()
    try:
        _install_synthetic_tables(conn)
        rows = conn.execute(route_summary_sql()).fetchdf()
    finally:
        conn.close()
    daily = rows[(rows.policy_id == "daily_policy") & (rows.direction == "LONG")]
    all_row = daily[daily.subset == "DEVELOPMENT_ALL_COMPARABLE"].iloc[0]
    test_row = daily[daily.subset == "WALK_FORWARD_TEST_COMPARABLE"].iloc[0]
    selected = daily[daily.subset == "WALK_FORWARD_SELECTED_COMPARABLE"].iloc[0]
    assert int(all_row.comparable_opportunities) == 2
    assert int(test_row.comparable_opportunities) == 2
    assert int(selected.comparable_opportunities) == 1
    assert selected.excursion_window == "THROUGH_20_SESSIONS"
    assert abs(float(selected.mean_mfe) - 0.06) < 1e-12
    assert abs(float(selected.mean_primary_net_return) - 0.029) < 1e-12
    assert abs(float(selected.mean_daily_h1_primary) - 0.009) < 1e-12
    assert abs(float(selected.mean_daily_h20_primary) - 0.039) < 1e-12


def test_move_threshold_curve_reports_favorable_and_adverse_frequencies() -> None:
    conn = duckdb.connect()
    try:
        _install_synthetic_tables(conn)
        curve = conn.execute(threshold_curve_sql()).fetchdf()
    finally:
        conn.close()
    selected_daily = curve[
        (curve.policy_id == "daily_policy")
        & (curve.subset == "WALK_FORWARD_SELECTED_COMPARABLE")
    ]
    assert len(selected_daily) == 4
    assert set(round(float(value), 2) for value in selected_daily.move_threshold) == {0.01, 0.02, 0.03, 0.05}
    assert all(abs(float(value) - 1.0) < 1e-12 for value in selected_daily.favorable_excursion_hit_rate)
    at_two = selected_daily[abs(selected_daily.move_threshold - 0.02) < 1e-12].iloc[0]
    at_three = selected_daily[abs(selected_daily.move_threshold - 0.03) < 1e-12].iloc[0]
    assert abs(float(at_two.adverse_excursion_breach_rate) - 1.0) < 1e-12
    assert abs(float(at_three.adverse_excursion_breach_rate) - 0.0) < 1e-12


def test_selected_fold_stability_is_descriptive_not_a_new_selector() -> None:
    conn = duckdb.connect()
    try:
        _install_synthetic_tables(conn)
        conn.execute(
            "CREATE TEMP TABLE selected_fold_summary AS " + selected_fold_summary_sql()
        )
        stability = conn.execute(route_stability_sql()).fetchdf()
    finally:
        conn.close()
    daily = stability[stability.policy_id == "daily_policy"].iloc[0]
    minute = stability[stability.policy_id == "minute_policy"].iloc[0]
    assert int(daily.active_folds) == 1
    assert int(daily.positive_primary_folds) == 1
    assert int(daily.selected_comparable) == 1
    assert abs(float(daily.largest_fold_share) - 1.0) < 1e-12
    assert int(minute.active_folds) == 1
    assert int(minute.positive_primary_folds) == 1
    assert int(minute.selected_comparable) == 1


def test_selected_route_diagnostics_exposes_move_profile_without_ranking() -> None:
    conn = duckdb.connect()
    try:
        _install_synthetic_tables(conn)
        conn.execute("CREATE TEMP TABLE option_route_summary AS " + route_summary_sql())
        conn.execute("CREATE TEMP TABLE option_move_threshold_curve AS " + threshold_curve_sql())
        conn.execute("CREATE TEMP TABLE selected_fold_summary AS " + selected_fold_summary_sql())
        conn.execute("CREATE TEMP TABLE option_route_stability AS " + route_stability_sql())
        rows = selected_route_diagnostics(conn)
    finally:
        conn.close()
    assert [row["policy_id"] for row in rows] == ["daily_policy", "minute_policy"]
    daily = rows[0]
    assert daily["selected_comparable"] == 1
    assert daily["excursion_window"] == "THROUGH_20_SESSIONS"
    assert rows[1]["excursion_window"] == "ENTRY_TO_ACTUAL_EXIT"
    assert abs(float(daily["p_mfe_ge_5pct"]) - 1.0) < 1e-12
    assert abs(float(daily["p_mae_le_m3pct"]) - 0.0) < 1e-12
    assert daily["active_folds"] == 1
