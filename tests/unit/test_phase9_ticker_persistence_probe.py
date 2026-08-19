from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from packages.regimes.ticker_persistence_probe import (
    TICKER_PERSISTENCE_CONFIRMATION_WINDOWS,
    TICKER_PERSISTENCE_POLICY_NAMES,
    TickerPersistenceProbe,
    agreement_diagnostics,
    dimensional_confirmed_states,
    sequence_diagnostics,
    split_contiguous_sequences,
    ticker_state_family,
)


def test_ticker_state_family_preserves_directional_semantics() -> None:
    assert ticker_state_family("STRONG_UPTREND") == "UP"
    assert ticker_state_family("PULLBACK_UP") == "UP"
    assert ticker_state_family("TRANSITION_UP") == "UP"
    assert ticker_state_family("STRONG_DOWNTREND") == "DOWN"
    assert ticker_state_family("BOUNCE_DOWN") == "DOWN"
    assert ticker_state_family("TRANSITION_DOWN") == "DOWN"
    assert ticker_state_family("RANGE_MIXED") == "MIXED"


def test_sequence_diagnostics_counts_one_step_flipback() -> None:
    diagnostics = sequence_diagnostics([["UPTREND", "PULLBACK_UP", "UPTREND"]])
    assert diagnostics["transition_count"] == 2
    assert diagnostics["transition_rate"] == 1.0
    assert diagnostics["aba_flipback_count"] == 1
    assert diagnostics["aba_flipback_per_transition"] == 0.5
    assert diagnostics["one_session_run_share"] == 1.0


def test_agreement_diagnostics_counts_opposite_direction_lag() -> None:
    diagnostics = agreement_diagnostics(
        [["UPTREND", "DOWNTREND"]],
        [["UPTREND", "UPTREND"]],
    )
    assert diagnostics["exact_agreement_rate"] == 0.5
    assert diagnostics["direction_family_agreement_rate"] == 0.5
    assert diagnostics["opposite_direction_mismatch_count"] == 1
    assert diagnostics["opposite_direction_mismatch_rate"] == 0.5


def test_dimensional_confirmation_recomposes_candidate_state() -> None:
    states = dimensional_confirmed_states(
        ["UP", "UP", "DOWN", "DOWN"],
        ["MIXED", "MIXED", "ALIGNED_DOWN", "ALIGNED_DOWN"],
        ["POSITIVE", "POSITIVE", "POSITIVE", "POSITIVE"],
        2,
    )
    assert states == ["UPTREND", "UPTREND", "UPTREND", "DOWNTREND"]


def test_split_contiguous_sequences_resets_across_missing_exchange_session() -> None:
    sessions = {
        date(2026, 8, 10): 0,
        date(2026, 8, 11): 1,
        date(2026, 8, 12): 2,
        date(2026, 8, 13): 3,
    }
    sequences = split_contiguous_sequences(
        [date(2026, 8, 10), date(2026, 8, 11), date(2026, 8, 13)],
        ["UPTREND", "PULLBACK_UP", "UPTREND"],
        sessions,
    )
    assert sequences == [["UPTREND", "PULLBACK_UP"], ["UPTREND"]]


def test_segments_pairs_adjacent_split_boundaries_without_strict_zip_failure() -> None:
    class _Calendar:
        @staticmethod
        def sessions_in_range(start_date: date, end_date: date) -> list[date]:
            assert start_date == date(2026, 8, 10)
            assert end_date == date(2026, 8, 13)
            return [
                date(2026, 8, 10),
                date(2026, 8, 11),
                date(2026, 8, 12),
                date(2026, 8, 13),
            ]

    probe = TickerPersistenceProbe.__new__(TickerPersistenceProbe)
    probe.calendar = _Calendar()
    frame = pd.DataFrame(
        {
            "instrument_id": ["ins_a", "ins_a", "ins_a"],
            "trading_date": [
                date(2026, 8, 10),
                date(2026, 8, 11),
                date(2026, 8, 13),
            ],
            "candidate_state": ["UPTREND", "PULLBACK_UP", "UPTREND"],
            "daily_structure": ["UP", "UP", "UP"],
            "short_alignment": ["MIXED", "ALIGNED_DOWN", "MIXED"],
            "momentum": ["POSITIVE", "POSITIVE", "POSITIVE"],
        }
    )

    segments = probe._segments(frame)

    assert [segment["candidate_state"] for segment in segments] == [
        ["UPTREND", "PULLBACK_UP"],
        ["UPTREND"],
    ]


def test_gate10_candidate_grid_is_explicit_and_bounded() -> None:
    assert TICKER_PERSISTENCE_CONFIRMATION_WINDOWS == (2, 3)
    assert TICKER_PERSISTENCE_POLICY_NAMES == (
        "composite_confirm_2",
        "composite_confirm_3",
        "dimensional_confirm_2",
        "dimensional_confirm_3",
    )
    assert len(TICKER_PERSISTENCE_POLICY_NAMES) == len(set(TICKER_PERSISTENCE_POLICY_NAMES))
