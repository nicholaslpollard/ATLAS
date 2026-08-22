from packages.data.alpaca_backfill_seam_lifecycle import (
    ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION,
    classify_boundary_presence,
    evaluate_cross_seam_rename,
    provider_bridge_compatible,
)


def _boundary(friday: bool, massive: bool, alpaca: bool) -> dict[str, object]:
    return {
        "candidate_friday_present": friday,
        "massive_monday_present": massive,
        "alpaca_monday_present": alpaca,
    }


def _segment(*, ambiguous: bool = False) -> dict[str, object]:
    return {
        "identity_chain_id": "chain",
        "segment_id": "segment",
        "identity_ambiguous": ambiguous,
        "last_candidate_session": "2021-08-13",
    }


def _rename_event(**updates: object) -> dict[str, object]:
    event = {
        "event_type": "name_changes",
        "source_symbol": "OLD",
        "target_symbol": "NEW",
        "source_cusip": "123456789",
        "target_cusip": "123456789",
    }
    event.update(updates)
    return event


def test_presence_classifier_covers_exact_continuation() -> None:
    assert classify_boundary_presence(True, True, True) == "FRIDAY_MONDAY_BOTH_PROVIDERS"


def test_presence_classifier_distinguishes_massive_coverage_gap() -> None:
    assert classify_boundary_presence(True, False, True) == "FRIDAY_ALPACA_ONLY_MONDAY"


def test_provider_bridge_requires_structural_parent_pass() -> None:
    assert not provider_bridge_compatible(
        {
            "structural_pass": False,
            "alpaca_safe_target_symbols": 100,
            "massive_target_symbols": 100,
            "matched_exact_symbols": 100,
            "close_within_1bp_fraction": 1.0,
            "ohlc_relative_diff_p95": 0.0,
        }
    )


def test_provider_bridge_accepts_gate7a_observed_quality_band() -> None:
    assert provider_bridge_compatible(
        {
            "structural_pass": True,
            "alpaca_safe_target_symbols": 10815,
            "massive_target_symbols": 10619,
            "matched_exact_symbols": 10169,
            "close_within_1bp_fraction": 0.99468974,
            "ohlc_relative_diff_p95": 0.0,
        }
    )


def test_clean_matching_cusip_adjacent_rename_is_safe() -> None:
    safe, reasons = evaluate_cross_seam_rename(
        _rename_event(),
        boundary_by_symbol={
            "OLD": _boundary(True, False, False),
            "NEW": _boundary(False, True, True),
        },
        anomaly_casefold=set(),
        segment_by_symbol={"OLD": _segment()},
    )
    assert safe
    assert reasons == ()


def test_cross_seam_rename_rejects_cusip_change() -> None:
    safe, reasons = evaluate_cross_seam_rename(
        _rename_event(target_cusip="987654321"),
        boundary_by_symbol={
            "OLD": _boundary(True, False, False),
            "NEW": _boundary(False, True, True),
        },
        anomaly_casefold=set(),
        segment_by_symbol={"OLD": _segment()},
    )
    assert not safe
    assert "CUSIP_CHANGED" in reasons


def test_cross_seam_rename_rejects_old_literal_still_trading_monday() -> None:
    safe, reasons = evaluate_cross_seam_rename(
        _rename_event(),
        boundary_by_symbol={
            "OLD": _boundary(True, False, True),
            "NEW": _boundary(False, True, True),
        },
        anomaly_casefold=set(),
        segment_by_symbol={"OLD": _segment()},
    )
    assert not safe
    assert "OLD_STILL_OBSERVED_MONDAY" in reasons


def test_cross_seam_rename_rejects_casefold_anomaly_or_identity_ambiguity() -> None:
    safe, reasons = evaluate_cross_seam_rename(
        _rename_event(),
        boundary_by_symbol={
            "OLD": _boundary(True, False, False),
            "NEW": _boundary(False, True, True),
        },
        anomaly_casefold={"old"},
        segment_by_symbol={"OLD": _segment(ambiguous=True)},
    )
    assert not safe
    assert "GATE7A_CASEFOLD_ANOMALY" in reasons
    assert "OLD_IDENTITY_AMBIGUOUS" in reasons


def test_gate7b_contract_is_lifecycle_specific() -> None:
    assert ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION.startswith("historical-backfill-seam-v2")
    assert "lifecycle" in ALPACA_BACKFILL_SEAM_LIFECYCLE_CONTRACT_VERSION
