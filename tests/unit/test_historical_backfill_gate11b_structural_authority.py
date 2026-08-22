from __future__ import annotations

from packages.ml.historical_backfill_structural_authority import (
    AUTH_CONFLICT,
    AUTH_ELIGIBLE,
    AUTH_IDENTITY_AMBIGUOUS,
    AUTH_INELIGIBLE,
    AUTH_NO_METADATA,
    classify_chain_structural_authority,
    normalize_structural_metadata,
    structural_metadata_reasons,
)


def test_normalize_structural_metadata_requires_all_fields() -> None:
    assert (
        normalize_structural_metadata(
            market="stocks",
            locale="us",
            primary_exchange="XNAS",
            security_type=None,
        )
        is None
    )


def test_structural_metadata_policy_accepts_supported_us_security() -> None:
    metadata = normalize_structural_metadata(
        market=" Stocks ",
        locale="US",
        primary_exchange="xnas",
        security_type="cs",
    )
    assert metadata == ("stocks", "us", "XNAS", "CS")
    assert structural_metadata_reasons(metadata) == ()


def test_structural_metadata_policy_rejects_unsupported_security_type() -> None:
    metadata = normalize_structural_metadata(
        market="stocks",
        locale="us",
        primary_exchange="XNYS",
        security_type="WARRANT",
    )
    assert structural_metadata_reasons(metadata) == ("UNSUPPORTED_SECURITY_TYPE",)


def test_chain_authority_quarantines_gate4_ambiguity_first() -> None:
    status, eligible, metadata, reasons = classify_chain_structural_authority(
        identity_ambiguous=True,
        metadata_candidates=[("stocks", "us", "XNYS", "CS")],
    )
    assert status == AUTH_IDENTITY_AMBIGUOUS
    assert eligible is False
    assert metadata is None
    assert reasons == ("GATE4_IDENTITY_AMBIGUOUS",)


def test_chain_authority_quarantines_missing_metadata() -> None:
    status, eligible, metadata, reasons = classify_chain_structural_authority(
        identity_ambiguous=False,
        metadata_candidates=[],
    )
    assert status == AUTH_NO_METADATA
    assert eligible is False
    assert metadata is None
    assert reasons == ("NO_STABLE_STRUCTURAL_METADATA",)


def test_chain_authority_quarantines_conflicting_metadata() -> None:
    status, eligible, metadata, reasons = classify_chain_structural_authority(
        identity_ambiguous=False,
        metadata_candidates=[
            ("stocks", "us", "XNYS", "CS"),
            ("stocks", "us", "XNAS", "CS"),
        ],
    )
    assert status == AUTH_CONFLICT
    assert eligible is False
    assert metadata is None
    assert reasons == ("CONFLICTING_STRUCTURAL_METADATA",)


def test_chain_authority_distinguishes_eligible_and_policy_ineligible() -> None:
    eligible_result = classify_chain_structural_authority(
        identity_ambiguous=False,
        metadata_candidates=[("stocks", "us", "ARCX", "ETF")],
    )
    assert eligible_result == (
        AUTH_ELIGIBLE,
        True,
        ("stocks", "us", "ARCX", "ETF"),
        (),
    )

    ineligible_result = classify_chain_structural_authority(
        identity_ambiguous=False,
        metadata_candidates=[("stocks", "us", "XNYS", "WARRANT")],
    )
    assert ineligible_result[0] == AUTH_INELIGIBLE
    assert ineligible_result[1] is False
    assert ineligible_result[2] == ("stocks", "us", "XNYS", "WARRANT")
    assert ineligible_result[3] == ("UNSUPPORTED_SECURITY_TYPE",)
