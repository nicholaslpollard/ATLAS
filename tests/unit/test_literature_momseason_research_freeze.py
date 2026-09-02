from __future__ import annotations

from packages.backtesting.literature_momseason_native_population import (
    MOMSEASON_NATIVE_POPULATION_CONTRACT,
)
from packages.backtesting.literature_momseason_research_freeze import (
    MOMSEASON_BOOTSTRAP_BLOCK_MONTHS,
    MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED,
    MOMSEASON_RESEARCH_FREEZE_STATUS,
    build_research_freeze_report,
)


def _native_report() -> dict[str, object]:
    return {
        "status": "NATIVE_POPULATION_SOURCE_CAPACITY_READY_FOR_REVIEW",
        "contract_version": MOMSEASON_NATIVE_POPULATION_CONTRACT,
        "native_plan": {
            "plan_fingerprint": "f6a766b338f1de32a176e34659743aad48d21c555bcb84ab8e76cadef9180792"
        },
        "endpoint_availability_counts": {"AVAILABLE": 191990, "ZERO_BAR": 73},
        "coverage": {
            "population_coverage": {
                "valid_contract": True,
                "source_scope_proven": True,
                "requires_bottleneck_explanation": False,
                "bottleneck_stages": [],
                "reasons": ["complete source scope is explicit and no probe-only stage is present"],
                "stages": [
                    {
                        "name": "literature_native_formation_population",
                        "rows": 248164,
                        "sessions": None,
                        "instruments": 2300,
                        "scope": "FULL_ELIGIBLE_UNIVERSE",
                        "complete_scope": True,
                        "comparable_to_previous": True,
                        "grain": "formation_month_hypothesis_instrument",
                        "source": "complete PIT native formation census",
                    },
                    {
                        "name": "identity_formula_defined_population",
                        "rows": 220271,
                        "sessions": None,
                        "instruments": 2200,
                        "scope": "FILTERED_POPULATION",
                        "complete_scope": True,
                        "comparable_to_previous": True,
                        "grain": "formation_month_hypothesis_instrument",
                        "source": "stable PIT identity and available annual lags",
                    },
                    {
                        "name": "adjusted_formula_defined_population",
                        "rows": 220186,
                        "sessions": None,
                        "instruments": 2195,
                        "scope": "FILTERED_POPULATION",
                        "complete_scope": True,
                        "comparable_to_previous": True,
                        "grain": "formation_month_hypothesis_instrument",
                        "source": "accepted adjustment=all endpoints",
                    },
                ],
            }
        },
        "existing_canonical_market_data_mutated": False,
        "global_alpaca_adjustment_mutated": False,
        "target_outcome_rows_read": 0,
        "protected_return_rows_read": 0,
        "protected_holdout_consumed": False,
        "broker_reads_performed": 0,
        "broker_writes_performed": 0,
        "order_writes_performed": 0,
        "paper_submits_performed": 0,
        "live_writes_performed": 0,
    }


def test_research_freeze_is_monthly_protected_blind_and_power_calibrated() -> None:
    report = build_research_freeze_report(_native_report())

    assert report["status"] == MOMSEASON_RESEARCH_FREEZE_STATUS
    assert report["gate_assessment"]["ready_to_freeze"] is True
    assert report["gate_assessment"]["disposition"] == "READY_TO_FREEZE"

    contract = report["scientific_contract"]
    development = contract["development_gate"]
    assert development["development_month_count"] == MOMSEASON_DEVELOPMENT_MONTHS_REQUIRED
    assert development["development_months"][0] == "2021-09"
    assert development["development_months"][-1] == "2026-04"
    assert development["independent_unit"] == "target_calendar_month_long_short_portfolio_return"
    assert development["stock_rows_are_not_independent_observations"] is True
    assert development["family_size"] == 2
    assert development["multiple_testing"] == "HOLM_BONFERRONI_FIXED_TWO_HYPOTHESES"
    assert development["bootstrap"]["block_months"] == MOMSEASON_BOOTSTRAP_BLOCK_MONTHS == 12

    calibration = report["positive_path_calibration"]
    assert calibration["atlas_development_outcomes_used"] is False
    assert calibration["target_met"] is True
    assert calibration["family_detection_rate"] >= calibration["target_family_detection_rate"]

    protected = contract["protected_policy"]
    assert protected["current_complete_target_months"] == 2
    assert protected["minimum_complete_target_months"] == 12
    assert protected["current_window_sufficient"] is False

    missing = contract["outcome_missingness_and_delisting"]
    assert missing["formation_cohort_fixed_before_target_outcomes"] is True
    assert missing["future_terminal_price_availability_may_not_filter_formation_cohort"] is True
    assert missing["silent_drop_of_missing_or_delisted_holding"] is False
    assert missing["zero_return_imputation"] is False

    assert report["development_outcome_rows_read"] == 0
    assert report["target_outcome_rows_read"] == 0
    assert report["protected_return_rows_read"] == 0
    assert report["protected_holdout_consumed"] is False
    assert report["provider_reads_performed"] == 0
    assert report["broker_reads_performed"] == 0
    assert report["order_writes_performed"] == 0
    assert report["paper_submits_performed"] == 0
    assert report["live_writes_performed"] == 0


def test_research_freeze_binds_native_source_fingerprint_and_cost_semantics() -> None:
    report = build_research_freeze_report(_native_report())
    contract = report["scientific_contract"]

    assert contract["source_binding"]["native_plan_fingerprint"].startswith("f6a766b3")
    assert contract["portfolio"]["weighting"] == "EQUAL_WEIGHT"
    assert contract["portfolio"]["long_short_quantile"] == 0.10
    assert contract["portfolio"]["native_signal_first"] is True
    assert contract["portfolio"]["phase25_warm_hot_filter_applied_to_primary"] is False

    costs = contract["transaction_costs"]
    assert costs["primary_bps_per_one_way_leg_turnover"] == 10.0
    assert costs["stress_bps_per_one_way_leg_turnover"] == 25.0
    assert costs["calibration_full_turnover_legs"] == 2.0

    authority = contract["authority"]
    assert authority["experimental_branch_only"] is True
    assert authority["mainline_alpha_status_changed"] is False
    assert authority["phase33_authority_changed"] is False
    assert authority["paper_authority"] is False
    assert authority["live_authority"] is False
