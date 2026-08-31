from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from packages.backtesting.alpha_gate_sec_13f_feasibility import (
    SEC_13F_ALPHA_HYPOTHESES_FROZEN,
    SEC_13F_ANCHORS,
    SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY,
    SEC_13F_FEASIBILITY_CONTRACT,
    SEC_13F_FEASIBILITY_FINGERPRINT,
    SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED,
    SEC_13F_MECHANISM_CANDIDATE,
    SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED,
    SEC_13F_PROTECTED_SOURCE_CUTOFF,
    SEC_13F_SOURCE_MAIN_MERGE,
    SEC_13F_TARGET_OUTCOME_READS_ALLOWED,
    sec_13f_feasibility_fingerprint,
)
from packages.providers.sec_13f_datasets import (
    SEC_13F_DATASET_HOST,
    SEC_13F_DATASET_MAX_RESPONSE_BYTES,
    SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES,
    SEC_13F_REQUIRED_TABLES,
)


def main() -> int:
    provider_path = PROJECT_ROOT / "packages/providers/sec_13f_datasets.py"
    engine_path = PROJECT_ROOT / "packages/backtesting/alpha_gate_sec_13f_feasibility.py"
    runner_path = PROJECT_ROOT / "scripts/run_alpha_gate_sec_13f_feasibility.py"
    workflow_path = PROJECT_ROOT / ".github/workflows/sec-13f-alpha-gate-tests.yml"
    full_workflow_path = PROJECT_ROOT / ".github/workflows/atlas-tests.yml"
    doc_path = PROJECT_ROOT / "docs/alpha_gate_sec_13f_feasibility.md"

    provider = provider_path.read_text(encoding="utf-8")
    engine = engine_path.read_text(encoding="utf-8")
    runner = runner_path.read_text(encoding="utf-8")
    workflow = workflow_path.read_text(encoding="utf-8")
    full_workflow = full_workflow_path.read_text(encoding="utf-8")
    doc = doc_path.read_text(encoding="utf-8")

    checks = {
        "fingerprint_exact": sec_13f_feasibility_fingerprint() == SEC_13F_FEASIBILITY_FINGERPRINT and bool(re.fullmatch(r"[0-9a-f]{64}", SEC_13F_FEASIBILITY_FINGERPRINT)),
        "source_main_merge_exact": SEC_13F_SOURCE_MAIN_MERGE == "579e94d0dfe861e37c25d2d67099f44c4f1c2351",
        "mechanism_materially_distinct": SEC_13F_MECHANISM_CANDIDATE == "PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION",
        "four_anchors_exact": len(SEC_13F_ANCHORS) == 4,
        "anchors_preprotected": all("2026" not in url for _, url in SEC_13F_ANCHORS) and SEC_13F_PROTECTED_SOURCE_CUTOFF.isoformat() == "2025-05-31",
        "official_sec_host_exact": SEC_13F_DATASET_HOST == "www.sec.gov",
        "required_tables_exact": SEC_13F_REQUIRED_TABLES == ("SUBMISSION.tsv", "COVERPAGE.tsv", "INFOTABLE.tsv"),
        "compressed_cap_bounded": SEC_13F_DATASET_MAX_RESPONSE_BYTES == 128_000_000,
        "uncompressed_cap_bounded": SEC_13F_DATASET_MAX_UNCOMPRESSED_BYTES == 1_500_000_000,
        "hypotheses_unfrozen": SEC_13F_ALPHA_HYPOTHESES_FROZEN is False,
        "cusip_identity_not_granted": SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY is False,
        "full_history_disabled": SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED is False,
        "target_outcomes_forbidden": SEC_13F_TARGET_OUTCOME_READS_ALLOWED is False,
        "protected_outcomes_forbidden": SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED is False,
        "provider_has_strict_url": "validate_url" in provider and "SEC_13F_DATASET_PREFIX" in provider,
        "zip_traversal_guard": "_safe_member_name" in provider and '".."' in provider,
        "immutable_raw_source_write": "_atomic_write_bytes" in engine and "LOCAL_IMMUTABLE_SOURCE" in engine,
        "existing_report_hash_checks_raw": "_existing_report" in engine and "source_sha256" in engine,
        "no_ticker_mapping": "ticker" not in engine.lower(),
        "runner_no_arbitrary_scope_args": "argparse" not in runner and "sys.argv" not in runner,
        "runner_declares_outcomes_unread": "FORBIDDEN / UNREAD" in runner,
        "focused_workflow_present": "sec-13f" in workflow.lower(),
        "full_workflow_retains_pytest": "python -m pytest -q" in full_workflow,
        "documentation_present": SEC_13F_FEASIBILITY_CONTRACT in doc and SEC_13F_FEASIBILITY_FINGERPRINT in doc,
    }
    for name, passed in checks.items():
        print(f"{name}: {passed}")
    if not all(checks.values()):
        return 2

    forbidden_import_fragments = ("packages.execution", "packages.brokers", "packages.backtesting.phase26")
    tree = ast.parse(engine)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for fragment in forbidden_import_fragments:
        if any(fragment in name for name in imported):
            raise AssertionError(f"forbidden SEC 13F feasibility import: {fragment}")

    print("ATLAS SEC Form 13F source-only feasibility contracts: PASS")
    print(f"Feasibility contract: {SEC_13F_FEASIBILITY_CONTRACT}")
    print(f"Feasibility fingerprint: {SEC_13F_FEASIBILITY_FINGERPRINT}")
    print("Market outcomes/protected returns: UNREAD")
    print("CUSIP -> ATLAS identity authority: NOT GRANTED")
    print("Phase33 authority: BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
