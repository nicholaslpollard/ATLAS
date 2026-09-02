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
    lit02_repair_v3_freeze_fingerprint,
    lit02_repair_v3_freeze_payload,
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


def test_repair_v3_freeze_fingerprint_is_deterministic() -> None:
    first = lit02_repair_v3_freeze_fingerprint()
    second = lit02_repair_v3_freeze_fingerprint()
    assert first == second
    assert len(first) == 64
