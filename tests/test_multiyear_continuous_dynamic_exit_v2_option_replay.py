from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from packages.simulation.multiyear_continuous_dynamic_exit_v2_option_replay import (
    MIN_TARGET_TO_STOP,
    STOP_MAX,
    STOP_MIN,
    TARGET_MAX,
    TARGET_MIN,
    derive_continuous_exit_choice,
)
from scripts.run_multiyear_continuous_dynamic_exit_v2_option_replay import (
    main as continuous_v2_runner_main,
)


def fake_case(
    *,
    mean_mae: float,
    mean_mfe: float,
    p25: float,
    p75: float,
    gross_return: float = -999.0,
    primary_net_return: float = -999.0,
):
    opportunity = SimpleNamespace(
        training_mean_mae=mean_mae,
        training_mean_mfe=mean_mfe,
        training_p25_gross_return=p25,
        training_p75_gross_return=p75,
        training_sample_size=100,
        training_start=date(2020, 1, 1),
        training_end=date(2020, 12, 31),
        signal_session=date(2021, 1, 5),
        # Current-case outcome fields are intentionally present but V2 must
        # never consult them while deriving its exit levels.
        gross_return=gross_return,
        primary_net_return=primary_net_return,
    )
    return SimpleNamespace(opportunity=opportunity)


def test_continuous_v2_derives_levels_from_prior_distribution():
    choice = derive_continuous_exit_choice(
        fake_case(
            mean_mae=0.018,
            mean_mfe=0.041,
            p25=-0.022,
            p75=0.035,
        )
    )
    assert abs(choice.downside_anchor - 0.020) < 1e-12
    assert abs(choice.upside_anchor - 0.038) < 1e-12
    assert abs(choice.stop_fraction - 0.020) < 1e-12
    assert abs(choice.target_fraction - 0.038) < 1e-12


def test_continuous_v2_respects_envelope_and_minimum_reward_to_risk():
    choice = derive_continuous_exit_choice(
        fake_case(
            mean_mae=0.080,
            mean_mfe=0.010,
            p25=-0.070,
            p75=0.010,
        )
    )
    assert choice.stop_fraction == STOP_MAX
    assert abs(choice.target_fraction - 0.045) < 1e-12
    assert STOP_MIN <= choice.stop_fraction <= STOP_MAX
    assert TARGET_MIN <= choice.target_fraction <= TARGET_MAX
    assert (
        choice.target_fraction + 1e-12
        >= MIN_TARGET_TO_STOP * choice.stop_fraction
    )


def test_continuous_v2_current_outcome_cannot_change_levels():
    first = derive_continuous_exit_choice(
        fake_case(
            mean_mae=0.012,
            mean_mfe=0.044,
            p25=-0.018,
            p75=0.032,
            gross_return=-0.99,
            primary_net_return=-0.99,
        )
    )
    second = derive_continuous_exit_choice(
        fake_case(
            mean_mae=0.012,
            mean_mfe=0.044,
            p25=-0.018,
            p75=0.032,
            gross_return=9.99,
            primary_net_return=9.99,
        )
    )
    assert first == second


def test_continuous_v2_floor_is_inside_frozen_research_envelope():
    choice = derive_continuous_exit_choice(
        fake_case(
            mean_mae=0.0,
            mean_mfe=0.0,
            p25=0.01,
            p75=-0.01,
        )
    )
    assert choice.stop_fraction == STOP_MIN
    assert choice.target_fraction == TARGET_MIN


def test_continuous_v2_runner_imports_end_to_end():
    assert callable(continuous_v2_runner_main)
