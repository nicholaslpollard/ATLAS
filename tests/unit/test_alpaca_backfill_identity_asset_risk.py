import pytest

from packages.data.alpaca_backfill_identity_asset_risk import (
    ASSET_ID_HISTORICAL_EFFECT,
    ASSET_ID_MULTIPLICITY_REFERENCE,
    ASSET_ID_REFERENCE_POLICY,
    analyze_asset_id_reference_risk,
    annotate_asset_id_reference,
    asset_records_from_payload,
)


def _asset(symbol: str, asset_id: str, partition: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "asset_id": asset_id,
        "partition": partition,
        "status": "active" if partition == "assets_active" else "inactive",
        "exchange": "NYSE",
        "asset_class": "us_equity",
        "name": f"{symbol} Corp",
        "tradable": partition == "assets_active",
    }


def _segment(symbol: str, chain_length: int = 1) -> dict[str, object]:
    return {
        "symbol": symbol,
        "chain_length": chain_length,
        "identity_ambiguous": False,
        "identity_ambiguity_reason": None,
    }


def test_gate4d_extracts_exact_asset_literals() -> None:
    payload = [
        {"symbol": "NAN", "id": "id-1", "status": "active", "exchange": "NYSE", "class": "us_equity", "name": "NAN Corp", "tradable": True},
        {"symbol": "", "id": "id-2"},
    ]

    rows = asset_records_from_payload(payload, "assets_active")

    assert len(rows) == 1
    assert rows[0]["symbol"] == "NAN"
    assert rows[0]["asset_id"] == "id-1"


def test_gate4d_current_uuid_multiplicity_is_reference_only() -> None:
    assets = [
        _asset("AAA", "id-active", "assets_active"),
        _asset("AAA", "id-inactive", "assets_inactive"),
        _asset("BBB", "id-b", "assets_active"),
    ]

    result = analyze_asset_id_reference_risk(
        assets,
        {"AAA", "BBB"},
        [],
        [],
        [_segment("AAA"), _segment("BBB")],
    )

    assert result.observed_symbols_with_multiple_asset_ids == 1
    assert len(result.reference_rows) == 1
    row = result.reference_rows[0]
    assert row["symbol"] == "AAA"
    assert row["risk_classification"] == ASSET_ID_MULTIPLICITY_REFERENCE
    assert row["asset_state_role"] == ASSET_ID_REFERENCE_POLICY
    assert row["historical_identity_effect"] == ASSET_ID_HISTORICAL_EFFECT
    assert row["automatic_continuity_forbidden"] is False
    assert row["historical_identity_ambiguous_from_uuid_alone"] is False


def test_gate4d_refuses_uuid_multiplicity_touching_eligible_edge() -> None:
    assets = [
        _asset("AAA", "id-1", "assets_active"),
        _asset("AAA", "id-2", "assets_inactive"),
        _asset("BBB", "id-3", "assets_active"),
    ]

    with pytest.raises(RuntimeError, match="touches identity-eligible rename continuity"):
        analyze_asset_id_reference_risk(
            assets,
            {"AAA", "BBB"},
            [{"old_symbol": "AAA", "new_symbol": "BBB"}],
            [],
            [_segment("AAA"), _segment("BBB", 2)],
        )


def test_gate4d_refuses_uuid_multiplicity_inside_multi_symbol_chain() -> None:
    assets = [
        _asset("AAA", "id-1", "assets_active"),
        _asset("AAA", "id-2", "assets_inactive"),
    ]

    with pytest.raises(RuntimeError, match="inside multi-symbol chain"):
        analyze_asset_id_reference_risk(
            assets,
            {"AAA"},
            [],
            [],
            [_segment("AAA", 2)],
        )


def test_gate4d_annotation_does_not_change_historical_ambiguity() -> None:
    rows = [
        {
            "symbol": "AAA",
            "identity_ambiguous": False,
            "identity_ambiguity_reason": None,
        },
        {
            "symbol": "RACA",
            "identity_ambiguous": True,
            "identity_ambiguity_reason": "SHARED_RENAME_NODE_HAS_MULTIPLE_CUSIPS",
        },
    ]
    reference = {
        "AAA": {
            "asset_id_count": 2,
            "asset_ids_json": '["id-1", "id-2"]',
        }
    }

    annotated, count = annotate_asset_id_reference(rows, reference, symbol_field="symbol")

    assert count == 1
    assert annotated[0]["asset_id_multiplicity_reference"] is True
    assert annotated[0]["identity_ambiguous"] is False
    assert annotated[1]["asset_id_multiplicity_reference"] is False
    assert annotated[1]["identity_ambiguous"] is True
