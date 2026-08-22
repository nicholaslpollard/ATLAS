from datetime import date

from packages.data.alpaca_backfill_identity import (
    ObservedBounds,
    _classify_name_change,
    _cycle_nodes,
    _normalize_event,
    _relationship_rows,
)


def test_gate4_name_change_normalizes_explicit_old_new_identity_evidence() -> None:
    event = _normalize_event(
        "name_changes",
        {
            "id": "event-1",
            "old_symbol": "AACQ",
            "new_symbol": "ORGN",
            "old_cusip": "68622D106",
            "new_cusip": "68622D106",
            "process_date": "2021-06-25",
        },
        partition="corporate_actions_2016_2021_page_0000",
        raw_sha256="a" * 64,
        event_index=0,
    )
    assert event["identity_semantics"] == "RENAME_CONTINUITY_CANDIDATE"
    assert event["source_symbol"] == "AACQ"
    assert event["target_symbol"] == "ORGN"
    assert event["source_cusip"] == event["target_cusip"] == "68622D106"
    relationships = _relationship_rows(event)
    assert len(relationships) == 1
    assert relationships[0]["relation_type"] == "RENAME"
    assert relationships[0]["continuity_candidate"] is True
    assert relationships[0]["continuity_forbidden"] is False


def test_gate4_merger_is_relationship_not_identity_continuity() -> None:
    event = _normalize_event(
        "stock_and_cash_mergers",
        {
            "id": "event-2",
            "acquiree_symbol": "AGN",
            "acquiree_cusip": "G0177J108",
            "acquirer_symbol": "ABBV",
            "acquirer_cusip": "00287Y109",
            "effective_date": "2020-05-08",
            "process_date": "2020-05-08",
        },
        partition="corporate_actions_2016_2021_page_0001",
        raw_sha256="b" * 64,
        event_index=0,
    )
    assert event["identity_semantics"] == "TERMINATION_CONVERSION"
    relationship = _relationship_rows(event)[0]
    assert relationship["relation_type"] == "TERMINATION_CONVERSION"
    assert relationship["continuity_candidate"] is False
    assert relationship["continuity_forbidden"] is True


def test_gate4_unit_split_creates_two_noncontinuity_component_edges() -> None:
    event = _normalize_event(
        "unit_splits",
        {
            "id": "event-3",
            "old_symbol": "ADOCU",
            "old_cusip": "G4000A128",
            "new_symbol": "ADOC",
            "new_cusip": "G4000A102",
            "alternate_symbol": "ADOCW",
            "alternate_cusip": "G4000A110",
            "effective_date": "2020-12-10",
        },
        partition="corporate_actions_2016_2021_page_0002",
        raw_sha256="c" * 64,
        event_index=0,
    )
    relationships = _relationship_rows(event)
    assert {row["relation_type"] for row in relationships} == {
        "UNIT_COMMON_COMPONENT",
        "UNIT_ALTERNATE_COMPONENT",
    }
    assert all(row["continuity_forbidden"] is True for row in relationships)


def test_gate4_same_cusip_temporally_clean_rename_is_safe_stitch_candidate() -> None:
    event = _normalize_event(
        "name_changes",
        {
            "id": "event-4",
            "old_symbol": "OLD",
            "new_symbol": "NEW",
            "old_cusip": "123456789",
            "new_cusip": "123456789",
            "process_date": "2020-06-15",
        },
        partition="corporate_actions_2016_2021_page_0003",
        raw_sha256="d" * 64,
        event_index=0,
    )
    result = _classify_name_change(
        event,
        observed={
            "OLD": ObservedBounds(date(2019, 1, 2), date(2020, 6, 12), True),
            "NEW": ObservedBounds(date(2020, 6, 15), date(2021, 8, 13), True),
        },
        source_target_count={"OLD": 1},
        target_source_count={"NEW": 1},
        cycle_nodes=set(),
        anomaly_casefold_keys=set(),
    )
    assert result["status"] == "SAFE_STITCH_CANDIDATE"
    assert result["safe_to_stitch"] is True
    assert result["review_reasons"] == ""


def test_gate4_casefold_sensitive_or_cyclic_rename_never_auto_stitches() -> None:
    event = _normalize_event(
        "name_changes",
        {
            "id": "event-5",
            "old_symbol": "AbC",
            "new_symbol": "ABC",
            "old_cusip": "123456789",
            "new_cusip": "123456789",
            "process_date": "2020-06-15",
        },
        partition="corporate_actions_2016_2021_page_0004",
        raw_sha256="e" * 64,
        event_index=0,
    )
    assert _cycle_nodes([("A", "B"), ("B", "A")]) == {"A", "B"}
    result = _classify_name_change(
        event,
        observed={},
        source_target_count={"AbC": 1},
        target_source_count={"ABC": 1},
        cycle_nodes=set(),
        anomaly_casefold_keys={"abc"},
    )
    assert result["status"] == "REVIEW_REQUIRED"
    assert result["safe_to_stitch"] is False
    reasons = set(str(result["review_reasons"]).split(","))
    assert "CASE_ONLY_LITERAL_CHANGE" in reasons
    assert "GATE3_CASEFOLD_ANOMALY" in reasons
