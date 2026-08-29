from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY_FINGERPRINT = "4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7"
EXPECTED_CONTRACT = "phase32-predictor-source-acquisition-v1-resumable-no-market-outcomes"
EXPECTED_IDENTITY = "instrument-identity-v4-no-issuer-level-medium-collapse"
EXPECTED_TAXONOMY_SHA = "b1bcb0037d2d17a36f1b72b8e260b32a611a81b36b831af5c5a6423e660d28a6"
EXPECTED_FILING_ENTITY_RULE = (
    "EXACT_ACCESSION_PLUS_ZERO_PADDED_ISSUER_CIK_PLUS_ACCESSION_WIDE_FILING_DATE"
)


def _read(path: str) -> str:
    return (PROJECT_ROOT / path).read_text(encoding="utf-8")


def _require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def _forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> int:
    module_path = "packages/backtesting/phase32_predictor_acquisition.py"
    runner_path = "scripts/run_phase32_predictor_acquisition.py"
    test_path = "tests/unit/test_phase32_predictor_acquisition.py"
    workflow_path = ".github/workflows/phase32-tests.yml"

    module = _read(module_path)
    runner = _read(runner_path)
    tests = _read(test_path)
    workflow = _read(workflow_path)
    ast.parse(module, filename=module_path)
    ast.parse(runner, filename=runner_path)
    ast.parse(tests, filename=test_path)

    from packages.backtesting.phase32_policy import phase32_policy_fingerprint
    from packages.backtesting.phase32_predictor_acquisition import (
        PHASE32_ACCEPTED_TAXONOMY_SHA256,
        PHASE32_ACQUISITION_END,
        PHASE32_ACQUISITION_START,
        PHASE32_FILING_ENTITY_KEY_RULE,
        PHASE32_FROZEN_POLICY_FINGERPRINT,
        PHASE32_PREDICTOR_ACQUISITION_CONTRACT,
    )
    from packages.instruments.identity import IDENTITY_CONTRACT_VERSION
    from packages.providers.massive.phase32_semantic import MassivePhase32SemanticClient

    if phase32_policy_fingerprint() != EXPECTED_POLICY_FINGERPRINT:
        raise AssertionError("frozen Phase32 policy drifted before predictor acquisition")
    if PHASE32_FROZEN_POLICY_FINGERPRINT != EXPECTED_POLICY_FINGERPRINT:
        raise AssertionError("predictor acquisition does not pin frozen policy fingerprint")
    if PHASE32_PREDICTOR_ACQUISITION_CONTRACT != EXPECTED_CONTRACT:
        raise AssertionError("predictor acquisition contract drifted")
    if PHASE32_FILING_ENTITY_KEY_RULE != EXPECTED_FILING_ENTITY_RULE:
        raise AssertionError("Phase32 filing-entity source key rule drifted")
    if IDENTITY_CONTRACT_VERSION != EXPECTED_IDENTITY:
        raise AssertionError("accepted identity-v4 contract drifted")
    if PHASE32_ACCEPTED_TAXONOMY_SHA256 != EXPECTED_TAXONOMY_SHA:
        raise AssertionError("accepted semantic taxonomy hash drifted")
    if PHASE32_ACQUISITION_START.isoformat() != "2021-08-16":
        raise AssertionError("Phase32 full-history acquisition start drifted")
    if PHASE32_ACQUISITION_END.isoformat() != "2026-08-11":
        raise AssertionError("Phase32 full-history acquisition end drifted")
    if not hasattr(MassivePhase32SemanticClient, "disclosures_window"):
        raise AssertionError("accepted Massive Phase32 semantic disclosure-window interface drifted")

    # Core acquisition is intentionally dependency-injected. Validate the source-only
    # acquisition invariants in the core module and validate concrete production
    # provider wiring separately in the runner rather than forcing provider imports
    # into the reusable acquisition engine. Exact version/contract values are checked
    # above against the live imported constants rather than duplicated in consumers.
    for token in (
        "Phase32PredictorSourceAcquisition",
        "InstrumentIdentityResolver",
        "massive_index",
        "massive_disclosures",
        "massive_text",
        "sec_submissions",
        "massive_reference",
        "candidate_filing_entity_records.jsonl",
        "phase32_predictor_rows.jsonl",
        "filing_entity_key",
        "filing_entity_key_rule",
        "assignments_by_cik",
        "disclosure_filer_ciks",
        "co_filer_disclosure_ciks",
        "accession_disclosure_row_count",
        "issuer_index_row_count",
        "co_filer_index_row_count",
        "index_filer_ciks",
        "co_filer_index_ciks",
        "for row in issuer_index_rows:",
        "multi_filer_candidate_accessions",
        "candidate_filing_entity_records",
        "source_stage_filing_entity_counts",
        "target_outcome_rows_read\": 0",
        "protected_return_rows_read\": 0",
        "stock_price_rows_read\": 0",
        "spy_price_rows_read\": 0",
        "options_rows_read\": 0",
        "provider_writes\": 0",
        "broker_reads\": 0",
        "order_writes\": 0",
        "paper_submits\": 0",
        "live_writes\": 0",
    ):
        _require(module, token, "predictor-acquisition invariant")

    for token in (
        "candidate disclosure accession has inconsistent filing dates",
        "candidate filing entity requires exactly one Massive Text row",
        "candidate disclosure accession is absent from original-8-K index",
        "candidate accession has no original-8-K index row for disclosure CIK",
        "SEC CIK mismatch",
        "SEC filing-date mismatch",
        "SEC original-form mismatch",
        "AMBIGUOUS_MULTIPLE_PIT_INSTRUMENTS",
        "NO_ELIGIBLE_PIT_INSTRUMENT",
        "CONTRADICTORY_LONG_SHORT_INSTRUMENT_SESSION",
        "reference_cik_missing",
        "filing_cik_mismatch",
        "fallback_identity",
        "identity_interval_changed",
    ):
        _require(module, token, "fail-closed source/identity rule")

    for forbidden in (
        "packages.data.market",
        "packages.features",
        "packages.execution",
        "packages.brokers",
        "packages.portfolio",
        "read_parquet",
        "forward_return",
        "future_close",
        "adjusted_close",
        "stock_return =",
        "spy_return =",
    ):
        _forbid(module, forbidden, "market outcome/execution dependency")

    for token in (
        "MassivePhase32SECIndexClient",
        "MassivePhase32SemanticClient",
        "SECEDGARClient",
        "MassiveReferenceProvider",
        "MassiveRESTClient",
        "PHASE32_PREDICTOR_ACQUISITION_CONTRACT",
        "Phase32PredictorSourceAcquisition(",
        "_Phase32SemanticAcquisitionAdapter",
        "self.client.disclosures_window(start_date=start_date, end_date=end_date)",
        "_Phase32SemanticAcquisitionAdapter(semantic_client)",
    ):
        _require(runner, token, "production source dependency wiring")

    _require(runner, "Stock/SPY/options outcomes: FORBIDDEN / UNREAD", "runner blindness declaration")
    _require(runner, "rerun will reuse completed atomic source caches", "runner resumability declaration")
    _require(tests, "test_source_acquisition_is_resumable_from_atomic_local_evidence", "resumability test")
    _require(tests, "test_multiple_pit_instruments_are_excluded_not_guessed", "ambiguity test")
    _require(tests, "test_acceptance_time_uses_first_regular_open_strictly_after_acceptance", "acceptance timing test")
    _require(
        tests,
        "test_production_semantic_adapter_binds_accepted_provider_interface",
        "production semantic adapter regression test",
    )
    _require(
        tests,
        "test_joint_filer_index_rows_are_preserved_but_do_not_contaminate_issuer_tickers",
        "joint-filer index provenance/ticker-isolation regression test",
    )
    _require(
        tests,
        "test_multi_filer_disclosure_rows_partition_by_exact_issuer_cik",
        "multi-filer disclosure filing-entity partition regression test",
    )
    _require(
        tests,
        "test_multi_filer_disclosure_still_fails_closed_on_accession_date_conflict",
        "multi-filer accession-date fail-closed regression test",
    )
    _require(
        tests,
        "test_joint_filer_reconciliation_fails_closed_when_disclosure_cik_is_absent",
        "joint-filer missing-issuer fail-closed regression test",
    )
    _require(tests, "def disclosures_window", "accepted semantic provider-interface fixture")

    _require(workflow, "Validate Phase 32 full-history predictor acquisition contracts", "CI acquisition validator step")
    _require(workflow, "python scripts/validate_phase32_predictor_acquisition.py", "CI acquisition validator command")
    _require(workflow, "tests/unit/test_phase32_predictor_acquisition.py", "CI acquisition unit test")

    print("ATLAS Phase 32 full-history predictor/source acquisition contracts: PASS")
    print(f"- frozen policy fingerprint pinned: {EXPECTED_POLICY_FINGERPRINT}")
    print(f"- acquisition contract pinned: {EXPECTED_CONTRACT}")
    print(f"- accepted identity contract pinned: {EXPECTED_IDENTITY}")
    print(f"- filing-entity source key pinned: {EXPECTED_FILING_ENTITY_RULE}")
    print("- full source range pinned: 2021-08-16..2026-08-11")
    print("- dependency-injected acquisition engine and concrete production source wiring are validated separately")
    print("- production semantic adapter explicitly binds disclosures_window to the acquisition disclosure port")
    print("- joint/multi-filer disclosure rows are partitioned by exact issuer CIK while filing date remains accession-wide")
    print("- co-filer disclosure/index provenance is preserved but cannot contaminate issuer ticker mapping")
    print("- monthly/index/disclosure plus filing-entity SEC/Text and ticker/date reference caches are resumable")
    print("- stock/SPY/options outcomes and broker/order/PAPER/LIVE authority remain absent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
