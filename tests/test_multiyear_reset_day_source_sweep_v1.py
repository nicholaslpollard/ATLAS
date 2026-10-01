from scripts.run_multiyear_reset_day_source_sweep_v1 import _available_assertion


def test_available_assertion_tracks_cumulative_spend_without_header():
    assert _available_assertion(10000, 3897, None) == 6103


def test_available_assertion_uses_lower_provider_header():
    assert _available_assertion(10000, 1000, 7200) == 7200


def test_available_assertion_never_goes_negative():
    assert _available_assertion(1000, 1500, 900) == 0
