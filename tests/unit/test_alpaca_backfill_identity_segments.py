import pytest

from packages.data.alpaca_backfill_identity_segments import build_identity_segments


def _observed(symbol: str, first_date: str, last_date: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "observed": True,
        "first_timestamp": f"{first_date}T05:00:00Z",
        "last_timestamp": f"{last_date}T05:00:00Z",
    }


def _safe(
    old_symbol: str,
    new_symbol: str,
    cusip: str,
    *,
    event_key: str,
    provider_event_id: str,
) -> dict[str, object]:
    return {
        "event_key": event_key,
        "provider_event_id": provider_event_id,
        "old_symbol": old_symbol,
        "new_symbol": new_symbol,
        "old_cusip": cusip,
        "new_cusip": cusip,
        "status": "SAFE_STITCH_CANDIDATE",
        "safe_to_stitch": True,
    }


def test_gate4c_builds_linear_multi_symbol_chain() -> None:
    observed = [
        _observed("AAA", "2020-01-02", "2020-06-12"),
        _observed("BBB", "2020-06-15", "2021-01-08"),
        _observed("CCC", "2021-01-11", "2021-08-13"),
    ]
    renames = [
        _safe("AAA", "BBB", "123456789", event_key="e1", provider_event_id="p1"),
        _safe("BBB", "CCC", "123456789", event_key="e2", provider_event_id="p2"),
    ]

    result = build_identity_segments(observed, renames)

    assert len(result.edge_rows) == 2
    assert len(result.chain_rows) == 1
    assert len(result.segment_rows) == 3
    chain = result.chain_rows[0]
    assert chain["chain_length"] == 3
    assert chain["member_symbols_json"] == '["AAA", "BBB", "CCC"]'
    assert chain["cusip"] == "123456789"
    positions = {row["symbol"]: row["chain_position"] for row in result.segment_rows}
    assert positions == {"AAA": 0, "BBB": 1, "CCC": 2}


def test_gate4c_keeps_unrelated_observed_symbol_as_singleton() -> None:
    observed = [
        _observed("AAA", "2020-01-02", "2020-06-12"),
        _observed("BBB", "2020-06-15", "2021-08-13"),
        _observed("ZZZ", "2019-01-02", "2021-08-13"),
    ]
    renames = [
        _safe("AAA", "BBB", "123456789", event_key="e1", provider_event_id="p1"),
    ]

    result = build_identity_segments(observed, renames)

    assert len(result.chain_rows) == 2
    singleton = next(row for row in result.chain_rows if row["first_symbol"] == "ZZZ")
    assert singleton["chain_length"] == 1
    assert singleton["continuity_basis"] == "OBSERVED_LITERAL_SINGLETON"


def test_gate4c_preserves_literal_nan_ticker_as_exact_symbol() -> None:
    observed = [_observed("NAN", "2019-01-02", "2021-08-13")]

    result = build_identity_segments(observed, [])

    assert len(result.chain_rows) == 1
    assert len(result.segment_rows) == 1
    assert result.chain_rows[0]["first_symbol"] == "NAN"
    assert result.segment_rows[0]["symbol"] == "NAN"


def test_gate4c_consolidates_duplicate_safe_evidence_for_same_pair() -> None:
    observed = [
        _observed("AAA", "2020-01-02", "2020-06-12"),
        _observed("BBB", "2020-06-15", "2021-08-13"),
    ]
    renames = [
        _safe("AAA", "BBB", "123456789", event_key="e1", provider_event_id="p1"),
        _safe("AAA", "BBB", "123456789", event_key="e2", provider_event_id="p2"),
    ]

    result = build_identity_segments(observed, renames)

    assert result.safe_candidate_rows == 2
    assert result.duplicate_safe_candidate_rows == 1
    assert len(result.edge_rows) == 1
    assert result.edge_rows[0]["evidence_event_count"] == 2
    assert result.edge_rows[0]["provider_event_ids_json"] == '["p1", "p2"]'


def test_gate4c_refuses_mixed_status_for_same_pair() -> None:
    observed = [
        _observed("AAA", "2020-01-02", "2020-06-12"),
        _observed("BBB", "2020-06-15", "2021-08-13"),
    ]
    renames = [
        _safe("AAA", "BBB", "123456789", event_key="e1", provider_event_id="p1"),
        {
            "old_symbol": "AAA",
            "new_symbol": "BBB",
            "status": "REVIEW_REQUIRED",
            "safe_to_stitch": False,
        },
    ]

    with pytest.raises(RuntimeError, match="mixed-status rename pair"):
        build_identity_segments(observed, renames)


def test_gate4c_refuses_safe_edge_that_violates_handoff_policy() -> None:
    observed = [
        _observed("AAA", "2020-01-02", "2020-06-01"),
        _observed("BBB", "2020-06-15", "2021-08-13"),
    ]
    renames = [
        _safe("AAA", "BBB", "123456789", event_key="e1", provider_event_id="p1"),
    ]

    with pytest.raises(RuntimeError, match="violates handoff policy"):
        build_identity_segments(observed, renames)


def test_gate4c_refuses_cross_edge_cusip_change_inside_chain() -> None:
    observed = [
        _observed("AAA", "2020-01-02", "2020-06-12"),
        _observed("BBB", "2020-06-15", "2021-01-08"),
        _observed("CCC", "2021-01-11", "2021-08-13"),
    ]
    renames = [
        _safe("AAA", "BBB", "111111111", event_key="e1", provider_event_id="p1"),
        _safe("BBB", "CCC", "222222222", event_key="e2", provider_event_id="p2"),
    ]

    with pytest.raises(RuntimeError, match="changes CUSIP across safe renames"):
        build_identity_segments(observed, renames)
