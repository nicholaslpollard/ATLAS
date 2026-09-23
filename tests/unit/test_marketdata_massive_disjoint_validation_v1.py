from __future__ import annotations

from packages.data.marketdata_massive_disjoint_validation_v1 import (
    CONTRACT,
    _aggregate_checks,
    _anchor_checks,
)


def test_validation_anchors_are_disjoint_from_calibration_roots_and_dates() -> None:
    validation_roots = {item["root"] for item in CONTRACT["validation_anchors"]}
    validation_dates = {item["date"] for item in CONTRACT["validation_anchors"]}
    calibration_roots = {"SPY", "MSFT", "NVDA", "QQQ"}
    calibration_dates = {
        "2026-03-02",
        "2026-05-01",
        "2026-07-01",
        "2026-09-01",
    }
    assert validation_roots.isdisjoint(calibration_roots)
    assert validation_dates.isdisjoint(calibration_dates)
    assert validation_roots == {"IWM", "AMZN", "META", "DIA"}
    assert validation_dates == {
        "2026-02-02",
        "2026-04-01",
        "2026-06-01",
        "2026-08-03",
    }


def test_thresholds_are_frozen_and_exact_match_is_descriptive_only() -> None:
    thresholds = CONTRACT["preregistered_thresholds"]
    assert thresholds["required_anchor_count"] == 4
    assert thresholds["minimum_overlap_coverage_rate_per_anchor"] == 1.0
    assert thresholds["minimum_last_inside_massive_range_rate_per_anchor"] == 1.0
    assert thresholds["maximum_median_price_relative_diff_per_anchor"] == 0.05
    assert thresholds["maximum_aggregate_median_price_relative_diff"] == 0.02
    assert thresholds["maximum_median_volume_relative_diff_per_anchor"] == 0.15
    assert thresholds["maximum_aggregate_median_volume_relative_diff"] == 0.10
    assert thresholds["exact_last_close_match_rate"] == "DESCRIPTIVE_ONLY"


def test_anchor_checks_pass_calibration_like_semantics() -> None:
    summary = {
        "overlap_sessions": 7,
        "marketdata_last_inside_massive_range_rate": 1.0,
        "median_price_rel_diff": 0.01,
        "median_volume_rel_diff": 0.05,
    }
    checks = _anchor_checks(marketdata_rows=7, summary=summary)
    assert all(checks.values())


def test_anchor_checks_fail_range_or_coverage_violation() -> None:
    range_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 7,
            "marketdata_last_inside_massive_range_rate": 0.99,
            "median_price_rel_diff": 0.01,
            "median_volume_rel_diff": 0.05,
        },
    )
    assert range_failure["last_inside_massive_range_rate"] is False

    coverage_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 6,
            "marketdata_last_inside_massive_range_rate": 1.0,
            "median_price_rel_diff": 0.01,
            "median_volume_rel_diff": 0.05,
        },
    )
    assert coverage_failure["overlap_coverage_rate"] is False


def test_anchor_checks_fail_preregistered_price_or_volume_median() -> None:
    price_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 7,
            "marketdata_last_inside_massive_range_rate": 1.0,
            "median_price_rel_diff": 0.051,
            "median_volume_rel_diff": 0.05,
        },
    )
    assert price_failure["median_price_relative_diff"] is False

    volume_failure = _anchor_checks(
        marketdata_rows=7,
        summary={
            "overlap_sessions": 7,
            "marketdata_last_inside_massive_range_rate": 1.0,
            "median_price_rel_diff": 0.01,
            "median_volume_rel_diff": 0.151,
        },
    )
    assert volume_failure["median_volume_relative_diff"] is False


def test_aggregate_checks_require_all_four_and_tighter_medians() -> None:
    checks = _aggregate_checks(
        anchor_count=4,
        anchor_pass_count=4,
        aggregate={
            "median_price_rel_diff": 0.019,
            "median_volume_rel_diff": 0.099,
        },
    )
    assert all(checks.values())

    failed = _aggregate_checks(
        anchor_count=4,
        anchor_pass_count=4,
        aggregate={
            "median_price_rel_diff": 0.021,
            "median_volume_rel_diff": 0.101,
        },
    )
    assert failed["aggregate_median_price_relative_diff"] is False
    assert failed["aggregate_median_volume_relative_diff"] is False


def test_passed_authority_remains_narrow() -> None:
    authority = CONTRACT["authority_if_passed"]
    assert authority["marketdata_eod_last_volume_semantics_validated"] is True
    assert authority["historical_bid_ask_validated"] is False
    assert authority["historical_intraday_validated"] is False
    assert authority["execution_price_authority"] is False
    assert authority["simulator_authority"] is False
    assert authority["paper"] is False
    assert authority["live"] is False
