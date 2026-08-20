from packages.data.alpaca_backfill_seam import (
    ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION,
    ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION,
    ALPACA_BACKFILL_SEAM_TARGET_SESSION,
    _chunks,
    _relative_difference,
    classify_seam_response_symbol,
    seam_source_fingerprint,
)


def test_gate7a_boundary_is_adjacent_friday_to_monday() -> None:
    assert ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION.isoformat() == "2021-08-13"
    assert ALPACA_BACKFILL_SEAM_TARGET_SESSION.isoformat() == "2021-08-16"
    assert (ALPACA_BACKFILL_SEAM_TARGET_SESSION - ALPACA_BACKFILL_CANDIDATE_BOUNDARY_SESSION).days == 3


def test_gate7a_exact_unique_response_symbol_is_safe() -> None:
    result = classify_seam_response_symbol("BCpC", ("ABC", "BCpC"), {"ABC", "BCpC"})
    assert result == (None, "BCpC", 1)


def test_gate7a_casefold_response_is_quarantined() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "BCPC", ("ABC", "BCpC"), {"ABC", "BCpC"}
    )
    assert classification == "CASE_FOLD_RESPONSE"
    assert requested == "BCpC"
    assert count == 1


def test_gate7a_casefold_collision_is_quarantined_more_strictly() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "BCPC", ("ABC", "BCpC"), {"ABC", "BCpC", "BCPC"}
    )
    assert classification == "CASE_FOLD_IDENTITY_COLLISION"
    assert requested == "BCpC"
    assert count == 1


def test_gate7a_same_batch_casefold_pair_is_ambiguous_even_for_exact_return() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "BCPC", ("BCpC", "BCPC"), {"BCpC", "BCPC"}
    )
    assert classification == "AMBIGUOUS_CASE_FOLD_RESPONSE"
    assert requested is None
    assert count == 2


def test_gate7a_unrequested_response_symbol_is_quarantined() -> None:
    classification, requested, count = classify_seam_response_symbol(
        "XYZ", ("ABC", "DEF"), {"ABC", "DEF"}
    )
    assert classification == "UNREQUESTED_RESPONSE_SYMBOL"
    assert requested is None
    assert count == 0


def test_gate7a_source_fingerprint_is_deterministic_case_and_parent_sensitive() -> None:
    kwargs = {
        "candidate_fingerprint": "candidate",
        "candidate_boundary_sha256": "friday",
        "massive_boundary_sha256": "monday",
        "symbols": ["ABC", "BCpC"],
        "symbol_batch_size": 100,
        "feed": "sip",
        "adjustment": "raw",
        "asof": "-",
        "timeframe": "1Day",
    }
    first = seam_source_fingerprint(**kwargs)
    assert first == seam_source_fingerprint(**kwargs)
    assert len(first) == 64
    assert first != seam_source_fingerprint(**{**kwargs, "symbols": ["ABC", "BCPC"]})
    assert first != seam_source_fingerprint(**{**kwargs, "massive_boundary_sha256": "changed"})


def test_gate7a_chunks_are_stable_and_complete() -> None:
    assert list(_chunks(["A", "B", "C", "D", "E"], 2)) == [
        ("A", "B"),
        ("C", "D"),
        ("E",),
    ]


def test_gate7a_relative_difference_is_symmetric() -> None:
    assert _relative_difference(100.0, 101.0) == _relative_difference(101.0, 100.0)
    assert _relative_difference(5.0, 5.0) == 0.0


def test_gate7a_contract_is_explicitly_same_session_provider_probe() -> None:
    assert ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION.startswith(
        "historical-backfill-seam-v1"
    )
    assert "same-session-provider-probe" in ALPACA_BACKFILL_SEAM_PROBE_CONTRACT_VERSION
