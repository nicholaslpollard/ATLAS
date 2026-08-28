from __future__ import annotations

import ast
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

EXPECTED_POLICY_FINGERPRINT = "e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67"
EXPECTED_SOURCE_QUALITY_FINGERPRINT = "2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83"
EXPECTED_QUARANTINE_SHA = "586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb"
EXPECTED_RAW_ACQUISITION_CONTRACT = (
    "phase31-form4-acquisition-v2-monthly-memory-bounded-global-accession-quarantine"
)
EXPECTED_ACQUISITION_V3_CONTRACT = (
    "phase31-form4-acquisition-v3-v2-raw-resume-global-historical-admissibility-quarantine"
)
EXPECTED_HISTORICAL_SOURCE_QUALITY_CONTRACT = (
    "phase31-form4-historical-source-quality-v1-chronology-required-code-global-accession-quarantine"
)
EXPECTED_CANDIDATES = (
    "open_market_purchase_long",
    "clustered_open_market_purchase_long",
    "open_market_sale_short",
    "clustered_open_market_sale_short",
)
EXPECTED_WINDOW_SHAS = (
    "0378adc4364b0b49812f95f700ff47eb52d55b2cf2c17bbecad77a48d6f8a4d5",
    "d8acaf8834ce166901388b437d5df1adf097d798fefb2e86449d92683acd7afd",
    "76c250af73a5694751eeb5974dbc55410c3ec63335d57632ab39d4a80d4edd8c",
    "a3b1b23c00ffbc7372f779d48171fa0a7aac04a5b3bf028c7b2e9bf74d0bb6e0",
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
    python_files = (
        "packages/backtesting/phase31_policy.py",
        "packages/backtesting/phase31_acquisition.py",
        "packages/backtesting/phase31_acquisition_v3.py",
        "packages/backtesting/phase31_historical_source_quality.py",
        "packages/providers/massive/phase31.py",
        "scripts/run_phase31_form4_acquisition.py",
    )
    for path in python_files:
        ast.parse(_read(path), filename=path)

    policy = _read("packages/backtesting/phase31_policy.py")
    acquisition = _read("packages/backtesting/phase31_acquisition.py")
    acquisition_v3 = _read("packages/backtesting/phase31_acquisition_v3.py")
    historical_source_quality = _read("packages/backtesting/phase31_historical_source_quality.py")
    provider = _read("packages/providers/massive/phase31.py")
    runner = _read("scripts/run_phase31_form4_acquisition.py")
    scientific = _read("docs/phase31_scientific_contract.md")
    phase_doc = _read("docs/phase31_sec_insider_transaction_alpha.md")
    status = _read("docs/current_status.md")
    workflow = _read(".github/workflows/atlas-tests.yml")

    from packages.backtesting.phase31_policy import PHASE31_CANDIDATES, phase31_policy_fingerprint
    from packages.backtesting.phase31_acquisition import (
        PHASE31_ACQUISITION_CONTRACT_VERSION,
        phase31_month_shards,
    )
    from packages.backtesting.phase31_acquisition_v3 import PHASE31_ACQUISITION_V3_CONTRACT_VERSION
    from packages.backtesting.phase31_historical_source_quality import (
        PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION,
    )

    if phase31_policy_fingerprint() != EXPECTED_POLICY_FINGERPRINT:
        raise AssertionError("Phase31 scientific policy fingerprint drifted")
    if PHASE31_ACQUISITION_CONTRACT_VERSION != EXPECTED_RAW_ACQUISITION_CONTRACT:
        raise AssertionError("Phase31 v2 raw-shard acquisition contract drifted")
    if PHASE31_ACQUISITION_V3_CONTRACT_VERSION != EXPECTED_ACQUISITION_V3_CONTRACT:
        raise AssertionError("Phase31 v3 historical acquisition contract drifted")
    if PHASE31_HISTORICAL_SOURCE_QUALITY_CONTRACT_VERSION != EXPECTED_HISTORICAL_SOURCE_QUALITY_CONTRACT:
        raise AssertionError("Phase31 historical source-quality contract drifted")
    if tuple(candidate.candidate_id for candidate in PHASE31_CANDIDATES) != EXPECTED_CANDIDATES:
        raise AssertionError("Phase31 candidate family drifted")
    if len(phase31_month_shards()) != 62:
        raise AssertionError("Phase31 acquisition monthly shard count drifted")

    _require(policy, EXPECTED_SOURCE_QUALITY_FINGERPRINT, "source-quality lineage")
    _require(policy, EXPECTED_QUARANTINE_SHA, "target quarantine lineage")
    for sha in EXPECTED_WINDOW_SHAS:
        _require(policy, sha, "accepted probe-window SHA")
    for candidate in EXPECTED_CANDIDATES:
        _require(policy, candidate, "frozen candidate")
    _require(policy, 'PHASE31_OUTCOME_HORIZON_SESSIONS = 20', "20-session outcome horizon")
    _require(policy, 'PHASE31_ENTRY_RULE = "DECISION_SESSION_OPEN"', "decision-open entry")
    _require(policy, 'PHASE31_BENCHMARK_TICKER = "SPY"', "SPY benchmark")
    _require(policy, 'PHASE31_INTERNAL_PURGE_SESSIONS = 20', "internal 20-session purge")
    _require(policy, 'PHASE31_MULTIPLE_TESTING_METHOD = "HOLM_BONFERRONI_GLOBAL_4"', "global Holm")
    _require(policy, 'PHASE31_RUNNER_UP_SUBSTITUTION_ALLOWED = False', "no runner-up substitution")
    _require(policy, 'PHASE31_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED = False', "protected blindness")
    _require(policy, 'PHASE31_PROVIDER_TEXT_ALPHA_AUTHORITY = False', "no provider text authority")
    _require(policy, 'PHASE31_TRANSACTION_VALUE_THRESHOLD_USED = False', "no trade-size threshold search")

    # The accepted v2 raw-shard contract remains frozen specifically so already
    # acquired SHA-bound shards can be reused without a scientific/source rewrite.
    _require(acquisition, EXPECTED_RAW_ACQUISITION_CONTRACT, "v2 raw acquisition contract")
    _require(acquisition, "raw_metadata_path", "raw shard sidecar metadata")
    _require(acquisition, "immutable Phase31 acquisition artifact drifted", "immutable shard protection")
    _forbid(acquisition, "all_raw.extend", "full-history in-memory accumulation")
    _forbid(acquisition, "all_raw_rows", "full-history in-memory tuple")

    _require(acquisition_v3, EXPECTED_ACQUISITION_V3_CONTRACT, "v3 acquisition contract")
    _require(
        acquisition_v3,
        "classify_form4_historical_source_quality",
        "historical source-admissibility classifier",
    )
    _require(
        acquisition_v3,
        "required_transaction_code_violation_count",
        "authoritative required-code recheck",
    )
    _require(acquisition_v3, "raw_shard_contract_retained_v2", "v2 raw resumability guard")
    _require(acquisition_v3, "probe_raw_reconciliation_exact", "raw overlap reconciliation")
    _require(
        acquisition_v3,
        "probe_authoritative_reconciliation_exact",
        "authoritative overlap reconciliation",
    )
    _require(acquisition_v3, '"target_outcome_rows_read": 0', "zero target outcome reads")
    _require(acquisition_v3, '"protected_return_rows_read": 0', "zero protected return reads")

    _require(
        historical_source_quality,
        EXPECTED_HISTORICAL_SOURCE_QUALITY_CONTRACT,
        "historical source-quality contract",
    )
    _require(
        historical_source_quality,
        "SOURCE_TRANSACTION_ROW_MISSING_TRANSACTION_CODE",
        "missing-code quarantine reason",
    )
    _require(
        historical_source_quality,
        "classify_form4_source_quality(materialized)",
        "accepted chronology classifier reuse",
    )
    _require(
        historical_source_quality,
        "entire accession",
        "whole-accession quarantine semantics",
    )
    _forbid(historical_source_quality, "0000752642-25-000004", "accession-specific workaround")

    _require(provider, "Preserve provider-native missing/blank transaction_code evidence unchanged", "raw malformed-row preservation")
    _forbid(provider, "is missing transaction_code", "transport-level missing-code abort")

    for source_name, source in (
        ("v2 acquisition", acquisition),
        ("v3 acquisition", acquisition_v3),
        ("historical source quality", historical_source_quality),
    ):
        for forbidden in (
            "forward_return",
            "directional_return",
            "future_close",
            "read_parquet",
            "packages.execution",
            "packages.brokers",
            "Webull",
            "AlpacaTrading",
        ):
            _forbid(source, forbidden, f"market outcome/trading dependency in {source_name}")

    _require(runner, "MassiveRESTClient(settings)", "accepted Massive client")
    _require(runner, "Phase31Form4HistoricalAcquisitionV3", "v3 acquisition runner")
    _require(runner, "existing v2 SHA-bound sidecars remain authoritative", "resume boundary")
    _require(runner, "Market outcomes/protected returns: FORBIDDEN / UNREAD", "runner blindness boundary")
    _require(runner, "Broker/order/PAPER/LIVE: DISABLED", "runner trading boundary")

    _require(scientific, EXPECTED_POLICY_FINGERPRINT, "scientific contract fingerprint")
    _require(scientific, "Exactly four hypotheses", "finite family")
    _require(scientific, "DECISION_SESSION_OPEN", "scientific entry")
    _require(scientific, "CLOSE_20_XNYS_SESSIONS_AFTER_DECISION", "scientific horizon")
    _require(scientific, "HOLM_BONFERRONI_GLOBAL_4", "scientific multiplicity")
    _require(scientific, "no runner-up substitution", "scientific winner freeze")
    _require(scientific, "2026-04-13", "development label boundary")
    _require(scientific, "2026-07-14", "protected signal boundary")
    _require(scientific, "zero market outcomes", "pre-performance freeze")

    _require(phase_doc, EXPECTED_POLICY_FINGERPRINT, "phase spec policy fingerprint")
    _require(phase_doc, "SOURCE_QUALITY_REPAIR_PASS", "phase spec repair pass")
    _require(phase_doc, "full historical Form-4 acquisition", "phase spec next acquisition")
    _require(status, EXPECTED_POLICY_FINGERPRINT, "status policy fingerprint")
    _require(status, "45,915", "status authoritative target count")
    _require(status, "scripts/run_phase31_form4_acquisition.py", "status exact next target")

    _require(workflow, "Validate Phase 31 frozen scientific policy and acquisition contracts", "CI policy step")
    _require(workflow, "python scripts/validate_phase31_policy.py", "CI policy validator command")

    print("ATLAS Phase 31 frozen scientific policy/acquisition contracts: PASS")
    print("- exact source-quality target evidence remains bound before performance")
    print("- exactly four Form-4 hypotheses remain frozen")
    print("- 20-session decision-open outcome, SPY-relative primary, costs, sample gates, Holm and robustness remain frozen")
    print("- existing v2 raw shards remain SHA-bound and resumable")
    print("- v3 historical admission globally quarantines chronology defects and missing transaction classification")
    print("- accepted probe windows must still reconcile exactly")
    print("- acquisition has no market-outcome or broker/order/PAPER/LIVE authority")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
