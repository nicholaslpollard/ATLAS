from __future__ import annotations

from datetime import date
import hashlib
from pathlib import Path
import subprocess
import sys

import pytest

from packages.data.b34_premarket_zsl_action_candidates_v1 import (
    EXPECTED_RECORDS, EXPECTED_PAGES, ZslActionCandidateError,
    project_archived_candidates,
)
from scripts.review_b34_premarket_zsl_action_candidates_v1 import (
    _validate_prior20_receipt,
)


def page_hashes():
    return [hashlib.sha256(str(i).encode()).hexdigest()
            for i in range(EXPECTED_PAGES)]


def row(symbol: str, index: int, *, action="reverse_splits", dates=None):
    return {
        "source_page_index": 0,
        "source_record_index": index,
        "action_type": action,
        "payload": {"symbol": symbol, **(dates or {})},
    }


def test_source_candidates_only_matching_zsl_and_april_dates():
    rows = [
        row("ZSL", 0, dates={"effective_date": "2026-04-15"}),
        row("ZSL", 1, dates={"effective_date": "2026-05-01"}),
        row("ZSL", 2),
        row("SPY", 3, dates={"effective_date": "2026-04-20"}),
    ]
    # Fixed-size corpus simulated without allocating 378k dictionaries.
    def records():
        yield from rows
        for i in range(len(rows), EXPECTED_RECORDS):
            yield row("OTHER", i)

    report = project_archived_candidates(records(), page_hashes())
    assert report["archive_records_checked"] == EXPECTED_RECORDS
    assert report["zsl_candidate_count"] == 2
    assert report["zsl_split_type_candidates"] == 2
    assert report["zsl_undated_candidates"] == 1
    assert report["archival_zero_action_coverage_proved"] is False
    assert report["historical_publication_revisions_qualified"] is False
    assert report["signal_authority"] is False
    assert all(c["historically_available_at"] is None for c in report["zsl_action_candidates"])


def test_known_february_zsl_split_is_outside_april_and_zero_candidates_fail_closed():
    # A separately published ProShares / SEC 8-K described a 1-for-10
    # ZSL reverse split effective 2026-02-26 with new CUSIP 74347Y672.
    # This synthetic projection is NOT a proof that April has complete coverage.
    february = row("ZSL", 0, dates={"effective_date": "2026-02-26"})

    def all_archived_records():
        yield february
        for i in range(1, EXPECTED_RECORDS):
            yield row("OTHER", i)

    report = project_archived_candidates(all_archived_records(), page_hashes())
    assert report["archive_records_checked"] == EXPECTED_RECORDS
    assert report["zsl_candidate_count"] == 0
    assert report["zsl_action_candidates"] == []
    assert report["zsl_split_type_candidates"] == 0
    assert report["archival_zero_action_coverage_proved"] is False
    assert report["corporate_action_completeness_qualified"] is False
    assert report["historical_publication_revisions_qualified"] is False
    assert report["split_comparable_premarket_volume_qualified"] is False
    assert report["signal_authority"] is False
    assert report["provider_requests"] == 0
    assert report["protected_outcomes_opened"] == 0


def test_duplicates_malformed_actions_and_wrong_corpus_fail_closed():
    hashes = page_hashes()
    with pytest.raises(ZslActionCandidateError, match="LEDGER_COUNT_CHANGED"):
        project_archived_candidates([row("ZSL", 0)], hashes)
    with pytest.raises(ZslActionCandidateError, match="DUPLICATE"):
        project_archived_candidates([row("ZSL", 0), row("ZSL", 0)], hashes)
    with pytest.raises(ZslActionCandidateError, match="MALFORMED_ZSL_EVENT_DATE"):
        project_archived_candidates(
            [row("ZSL", 0, dates={"ex_date": "not-a-date"})], hashes
        )
    with pytest.raises(ZslActionCandidateError, match="SOURCE_RECEIPTS"):
        project_archived_candidates([], hashes[:-1])


def test_exact_retained_prior20_receipt_and_non_admission():
    original = {
        "contract": "atlas-b34-premarket-prior20-source-review-v1",
        "source_contract": "atlas-b34-premarket-prior20-volume-observation-v1-no-signal",
        "status": "PRIOR20_SOURCE_DIAGNOSTIC_NO_SIGNAL",
        "symbol": "ZSL", "session_date": "2026-04-30",
        "selected_symbol": "ZSL", "selected_session": "2026-04-30",
        "prior_session_count": 20, "prior_rows_read": 5150,
        "signal_authority": False, "provider_requests": 0,
        "broker_requests": 0, "protected_outcomes_opened": 0,
        "split_or_corporate_action_history_checked": False,
        "prior_session_dates": [], "snapshots": [],
    }
    from packages.core.market_calendar import MarketCalendar
    days = MarketCalendar().sessions_in_range(date(2026,4,1),date(2026,4,29))
    original["prior_session_dates"] = [x.isoformat() for x in days]
    for clock, volume, med in [
        ("09:20:00", 708692, 1058953.5),
        ("09:30:00", 724192, 1092517.0),
        ("09:35:00", 724192, 1092517.0),
    ]:
        original["snapshots"].append({
            "decision_clock_et":clock,
            "current_observed_premarket_volume":volume,
            "prior_20_median_observed_premarket_volume":med,
            "raw_volume_ratio_diagnostic_only":volume/med,
            "prior_session_count":20,
            "prior_sessions_with_observed_premarket":20,
            "prior_sessions_missing_premarket":[],
            "volume_ratio_admissible_as_strategy_input":False,
        })
    assert _validate_prior20_receipt(original) == len(days)
    original["snapshots"][0]["volume_ratio_admissible_as_strategy_input"] = True
    with pytest.raises(ValueError, match="STRATEGY"):
        _validate_prior20_receipt(original)


@pytest.mark.parametrize("form", ["direct", "module"])
def test_cli_invocation_no_provider_calls(form):
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "review_b34_premarket_zsl_action_candidates_v1.py"
    cmd = ([sys.executable, str(script)] if form == "direct" else [
        sys.executable, "-m",
        "scripts.review_b34_premarket_zsl_action_candidates_v1",
    ])
    done = subprocess.run([*cmd, "--help"], cwd=root, text=True,
                          capture_output=True, timeout=30, check=False)
    assert done.returncode == 0, done.stderr
    assert "--no-write" in done.stdout
