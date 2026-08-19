from packages.ml.reuse_audit import (
    ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION,
    MULTI_STABLE_IDENTITIES,
    ONE_STABLE_PLUS_WEAK,
    WEAK_IDENTITIES_ONLY,
    reuse_composition_category,
)


def test_reuse_audit_contract_is_explicit() -> None:
    assert ML_TICKER_REUSE_AUDIT_CONTRACT_VERSION == (
        "ml-ticker-reuse-audit-v1-stable-vs-weak-identity-authority-enrichment"
    )


def test_multiple_stable_identities_are_real_conflict_class() -> None:
    assert reuse_composition_category(2, 2) == MULTI_STABLE_IDENTITIES
    assert reuse_composition_category(3, 5) == MULTI_STABLE_IDENTITIES


def test_one_stable_plus_date_scoped_weak_ids_is_separate_diagnostic_class() -> None:
    assert reuse_composition_category(1, 2) == ONE_STABLE_PLUS_WEAK
    assert reuse_composition_category(1, 8) == ONE_STABLE_PLUS_WEAK


def test_no_stable_identity_remains_weak_only() -> None:
    assert reuse_composition_category(0, 2) == WEAK_IDENTITIES_ONLY
    assert reuse_composition_category(0, 9) == WEAK_IDENTITIES_ONLY
