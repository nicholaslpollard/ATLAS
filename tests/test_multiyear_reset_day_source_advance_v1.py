from __future__ import annotations

import pytest

from scripts.run_multiyear_reset_day_source_advance_v1 import _remaining_after


def test_provider_remaining_header_is_hardest_bound():
    assert _remaining_after(10000, 9512, 487) == 9512
    assert _remaining_after(5000, 7000, 100) == 5000
    assert _remaining_after(5000, 0, 100) == 0


def test_missing_provider_remaining_falls_back_to_observed_debit():
    assert _remaining_after(10000, None, 487) == 9513
    assert _remaining_after(100, None, 100) == 0


def test_malformed_observation_never_invents_extra_budget():
    assert _remaining_after(1000, "900", "100") == 1000
