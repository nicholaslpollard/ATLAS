from __future__ import annotations

from scripts.run_multiyear_option_decision_spot_v1 import _decision_cutoff_utc


def test_decision_cutoff_utc_tracks_eastern_dst():
    assert _decision_cutoff_utc("2025-01-06").isoformat() == "2025-01-06T14:34:00+00:00"
    assert _decision_cutoff_utc("2025-07-07").isoformat() == "2025-07-07T13:34:00+00:00"
