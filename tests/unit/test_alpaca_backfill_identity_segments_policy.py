from packages.data.alpaca_backfill_identity_segments_policy import (
    CUSIP_AMBIGUITY_REASON,
    partition_safe_edges_by_cusip_node,
    quarantine_ambiguous_safe_rename_rows,
)


def _edge(old_symbol: str, new_symbol: str, cusip: str, edge_id: str) -> dict[str, object]:
    return {
        "old_symbol": old_symbol,
        "new_symbol": new_symbol,
        "cusip": cusip,
        "safe_edge_id": edge_id,
        "evidence_event_count": 1,
    }


def _rename(old_symbol: str, new_symbol: str, cusip: str) -> dict[str, object]:
    return {
        "old_symbol": old_symbol,
        "new_symbol": new_symbol,
        "old_cusip": cusip,
        "new_cusip": cusip,
        "status": "SAFE_STITCH_CANDIDATE",
        "safe_to_stitch": True,
    }


def test_gate4c_v2_quarantines_all_edges_touching_multi_cusip_shared_node() -> None:
    partition = partition_safe_edges_by_cusip_node(
        [
            _edge("TXAC", "RACA", "88339T103", "e1"),
            _edge("RACA", "PNT", "730541109", "e2"),
        ]
    )

    assert partition.eligible_edges == []
    assert len(partition.quarantined_edges) == 2
    assert partition.ambiguous_symbols == {
        "RACA": ("730541109", "88339T103"),
    }
    assert all(
        row["quarantine_reason"] == CUSIP_AMBIGUITY_REASON
        for row in partition.quarantined_edges
    )


def test_gate4c_v2_preserves_same_cusip_linear_chain_edges() -> None:
    partition = partition_safe_edges_by_cusip_node(
        [
            _edge("AAA", "BBB", "123456789", "e1"),
            _edge("BBB", "CCC", "123456789", "e2"),
        ]
    )

    assert len(partition.eligible_edges) == 2
    assert partition.quarantined_edges == []
    assert partition.ambiguous_symbols == {}


def test_gate4c_v2_marks_ambiguous_node_rename_rows_nonautomatic() -> None:
    rows = [
        _rename("TXAC", "RACA", "88339T103"),
        _rename("RACA", "PNT", "730541109"),
        _rename("AAA", "BBB", "123456789"),
    ]

    revised = quarantine_ambiguous_safe_rename_rows(rows, {"RACA"})

    assert revised[0]["status"] == "GRAPH_QUARANTINED"
    assert revised[0]["safe_to_stitch"] is False
    assert revised[1]["status"] == "GRAPH_QUARANTINED"
    assert revised[1]["safe_to_stitch"] is False
    assert revised[2]["status"] == "SAFE_STITCH_CANDIDATE"
    assert revised[2]["safe_to_stitch"] is True
