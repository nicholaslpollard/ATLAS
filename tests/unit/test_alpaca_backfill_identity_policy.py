from packages.data.alpaca_backfill_identity_policy import (
    MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS,
    classify_observed_handoff,
)


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "event_key": "event-1",
        "provider_event_id": "provider-1",
        "event_date": "2020-10-23",
        "old_symbol": "FMCI",
        "new_symbol": "TTCF",
        "old_cusip": "87663X102",
        "new_cusip": "87663X102",
        "old_observed": True,
        "new_observed": True,
        "old_first_date": "2017-05-02",
        "old_last_date": "2020-10-15",
        "new_first_date": "2020-10-16",
        "new_last_date": "2021-08-13",
        "status": "REVIEW_REQUIRED",
        "safe_to_stitch": False,
        "review_reasons": "NEW_OBSERVED_BEFORE_CHANGE",
    }
    row.update(overrides)
    return row


def test_gate4_process_date_lag_does_not_block_clean_observed_handoff() -> None:
    result = classify_observed_handoff(_row())
    assert result["status"] == "SAFE_STITCH_CANDIDATE"
    assert result["safe_to_stitch"] is True
    assert result["review_reasons"] == ""
    assert result["handoff_gap_calendar_days"] == 1
    assert result["process_date_lag_from_new_start_days"] == 7


def test_gate4_weekend_or_holiday_sized_gap_is_within_safe_policy() -> None:
    result = classify_observed_handoff(
        _row(
            old_last_date="2021-07-02",
            new_first_date="2021-07-06",
            event_date="2021-07-08",
        )
    )
    assert MAX_SAFE_RENAME_HANDOFF_CALENDAR_DAYS == 7
    assert result["status"] == "SAFE_STITCH_CANDIDATE"
    assert result["handoff_gap_calendar_days"] == 4


def test_gate4_long_nonoverlapping_gap_remains_review_required() -> None:
    result = classify_observed_handoff(
        _row(
            old_last_date="2020-06-18",
            new_first_date="2020-07-30",
            event_date="2020-07-20",
            status="SAFE_STITCH_CANDIDATE",
            review_reasons="",
        )
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["safe_to_stitch"] is False
    assert result["handoff_gap_calendar_days"] == 42
    assert result["review_reasons"] == "OBSERVED_HANDOFF_GAP_EXCEEDS_7_DAYS"


def test_gate4_actual_observation_overlap_remains_review_required() -> None:
    result = classify_observed_handoff(
        _row(
            old_last_date="2021-08-13",
            new_first_date="2021-04-06",
            event_date="2021-04-06",
            review_reasons="OBSERVATION_OVERLAP,OLD_OBSERVED_AFTER_CHANGE",
        )
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["safe_to_stitch"] is False
    assert result["review_reasons"] == "OBSERVATION_OVERLAP"


def test_gate4_unobserved_side_remains_continuity_evidence_only_without_hard_blocker() -> None:
    result = classify_observed_handoff(
        _row(
            old_observed=False,
            old_first_date=None,
            old_last_date=None,
            status="CONTINUITY_EVIDENCE_ONLY",
            review_reasons="",
        )
    )
    assert result["status"] == "CONTINUITY_EVIDENCE_ONLY"
    assert result["safe_to_stitch"] is False
    assert result["review_reasons"] == ""
