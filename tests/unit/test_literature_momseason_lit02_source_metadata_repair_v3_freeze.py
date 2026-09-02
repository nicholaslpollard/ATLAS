from __future__ import annotations

from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3 import (
    LIT02_REPAIR_V3_SEC_ALLOWED_FORMS,
    lit02_repair_v3_source_expansion_fingerprint,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3_certified import (
    LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION,
)
from packages.backtesting.literature_momseason_lit02_source_metadata_repair_v3_freeze import (
    LIT02_REPAIR_V3_DEFINED_CASH_TERMS,
    LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT,
    _contains_contingent_consideration,
    lit02_repair_v3_freeze_fingerprint,
    lit02_repair_v3_freeze_payload,
)


EXPECTED_REPAIR_V3_SOURCE_EXPANSION_FINGERPRINT = (
    "c5da7d155c50d7c19ae9c23bb604b1205e21b3359d51157f7367a1c88fed82bb"
)
EXPECTED_REPAIR_V3_FREEZE_FINGERPRINT = (
    "6b7af7b2637ac374d5d6d3cfcb2c12ee8825f6ec86716118306130c7ad8e5f0f"
)


def test_repair_v3_freeze_binds_source_expansion_and_parser_semantics() -> None:
    payload = lit02_repair_v3_freeze_payload()
    assert payload["freeze_contract"] == LIT02_SOURCE_METADATA_REPAIR_V3_FREEZE_CONTRACT
    assert payload["source_expansion_fingerprint"] == lit02_repair_v3_source_expansion_fingerprint()
    assert payload["repair_v3_parser_certification"] == LIT02_SOURCE_METADATA_REPAIR_V3_PARSER_CERTIFICATION
    assert payload["defined_cash_terms"] == list(LIT02_REPAIR_V3_DEFINED_CASH_TERMS)
    assert payload["source_expansion"]["sec_allowed_forms"] == sorted(LIT02_REPAIR_V3_SEC_ALLOWED_FORMS)


def test_repair_v3_freeze_preserves_scientific_safety() -> None:
    payload = lit02_repair_v3_freeze_payload()
    assert payload["economic_paths_changed"] is False
    assert payload["required_source_coverage"] == 1.0
    assert payload["ticker_specific_exceptions_allowed"] is False
    assert payload["economic_outcome_values_allowed"] is False
    assert payload["new_price_or_return_reads_allowed"] is False
    assert payload["protected_reads_allowed"] is False
    assert payload["broker_or_order_authority"] is False
    assert payload["phase33_authority"] is False


def test_repair_v3_freeze_explicitly_fails_closed_on_contingent_consideration() -> None:
    payload = lit02_repair_v3_freeze_payload()
    text = str(payload["contingent_rule"])
    assert "CVR" in text
    assert "not admitted" in text
    assert _contains_contingent_consideration("$1.00 cash plus one CVR per share") is True
    assert _contains_contingent_consideration("one contingent value right plus cash") is True
    assert _contains_contingent_consideration("$27.00 cash per share, without interest") is False


def test_repair_v3_freeze_fingerprint_is_exact_and_deterministic() -> None:
    assert (
        lit02_repair_v3_source_expansion_fingerprint()
        == EXPECTED_REPAIR_V3_SOURCE_EXPANSION_FINGERPRINT
    )
    assert lit02_repair_v3_freeze_fingerprint() == EXPECTED_REPAIR_V3_FREEZE_FINGERPRINT
    assert lit02_repair_v3_freeze_fingerprint() == lit02_repair_v3_freeze_fingerprint()
