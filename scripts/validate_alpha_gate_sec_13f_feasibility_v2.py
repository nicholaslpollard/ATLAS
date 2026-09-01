from __future__ import annotations

import ast
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

from packages.backtesting.alpha_gate_sec_13f_feasibility import SEC_13F_ANCHORS, SEC_13F_MECHANISM_CANDIDATE, SEC_13F_PROTECTED_SOURCE_CUTOFF
from packages.backtesting.alpha_gate_sec_13f_feasibility_v2 import (
    SEC_13F_ALPHA_HYPOTHESES_FROZEN_V2,
    SEC_13F_CAPACITY_EVIDENCE_COMPLETE,
    SEC_13F_CAPACITY_EVIDENCE_KIND,
    SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN,
    SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY_V2,
    SEC_13F_FEASIBILITY_SCOPE,
    SEC_13F_FEASIBILITY_V1_PREAUDIT_HEAD,
    SEC_13F_FEASIBILITY_V2_CONTRACT,
    SEC_13F_FEASIBILITY_V2_FINGERPRINT,
    SEC_13F_FEASIBILITY_V2_SOURCE_MAIN_MERGE,
    SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED_V2,
    SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED_V2,
    SEC_13F_PROSPECTIVE_RESEARCH_FREEZE_REQUIRED,
    SEC_13F_SCIENTIFIC_FREEZE_ALLOWED,
    SEC_13F_TARGET_OUTCOME_READS_ALLOWED_V2,
    sec_13f_feasibility_v2_fingerprint,
)
from packages.backtesting.research_gate_freeze import RESEARCH_GATE_FREEZE_CONTRACT_VERSION
from packages.providers.sec_13f_datasets import SEC_13F_DATASET_HOST, SEC_13F_REQUIRED_TABLES


def main() -> int:
    engine_path = PROJECT_ROOT / "packages/backtesting/alpha_gate_sec_13f_feasibility_v2.py"
    runner_path = PROJECT_ROOT / "scripts/run_alpha_gate_sec_13f_feasibility_v2.py"
    workflow_path = PROJECT_ROOT / ".github/workflows/sec-13f-alpha-gate-tests.yml"
    doc_path = PROJECT_ROOT / "docs/alpha_gate_sec_13f_feasibility_v2.md"
    engine = engine_path.read_text(encoding="utf-8")
    runner = runner_path.read_text(encoding="utf-8")
    workflow = workflow_path.read_text(encoding="utf-8")
    doc = doc_path.read_text(encoding="utf-8")
    checks = {
        "fingerprint_exact": sec_13f_feasibility_v2_fingerprint() == SEC_13F_FEASIBILITY_V2_FINGERPRINT and bool(re.fullmatch(r"[0-9a-f]{64}", SEC_13F_FEASIBILITY_V2_FINGERPRINT)),
        "audited_main_lineage_exact": SEC_13F_FEASIBILITY_V2_SOURCE_MAIN_MERGE == "938747804e05357981faed79d696875cd7649f19",
        "preaudit_v1_preserved": SEC_13F_FEASIBILITY_V1_PREAUDIT_HEAD == "4f40b25d0a19d1485ef990e465ab064080c8cc06",
        "mechanism_unchanged": SEC_13F_MECHANISM_CANDIDATE == "PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION",
        "four_anchors_exact": len(SEC_13F_ANCHORS) == 4,
        "anchors_preprotected": all("2026" not in url for _, url in SEC_13F_ANCHORS) and SEC_13F_PROTECTED_SOURCE_CUTOFF.isoformat() == "2025-05-31",
        "official_sec_host_exact": SEC_13F_DATASET_HOST == "www.sec.gov",
        "required_tables_exact": SEC_13F_REQUIRED_TABLES == ("SUBMISSION.tsv", "COVERPAGE.tsv", "INFOTABLE.tsv"),
        "probe_only_scope": SEC_13F_FEASIBILITY_SCOPE == "PROBE_ONLY",
        "bounded_probe_capacity_kind": SEC_13F_CAPACITY_EVIDENCE_KIND == "BOUNDED_ANCHOR_PROBE",
        "capacity_not_claimed_complete": SEC_13F_CAPACITY_EVIDENCE_COMPLETE is False,
        "complete_source_scope_not_claimed": SEC_13F_COMPLETE_SOURCE_SCOPE_PROVEN is False,
        "science_freeze_forbidden": SEC_13F_SCIENTIFIC_FREEZE_ALLOWED is False,
        "prospective_freeze_required": SEC_13F_PROSPECTIVE_RESEARCH_FREEZE_REQUIRED is True,
        "audit_freeze_contract_retained": RESEARCH_GATE_FREEZE_CONTRACT_VERSION == "research-gate-freeze-v1-reachability-population-power-before-outcomes",
        "hypotheses_unfrozen": SEC_13F_ALPHA_HYPOTHESES_FROZEN_V2 is False,
        "cusip_identity_not_granted": SEC_13F_CUSIP_TO_ATLAS_IDENTITY_AUTHORITY_V2 is False,
        "full_history_disabled": SEC_13F_FULL_HISTORY_ACQUISITION_ALLOWED_V2 is False,
        "target_outcomes_forbidden": SEC_13F_TARGET_OUTCOME_READS_ALLOWED_V2 is False,
        "protected_outcomes_forbidden": SEC_13F_PROTECTED_OUTCOME_READS_ALLOWED_V2 is False,
        "population_contract_used": "PopulationScope.PROBE_ONLY" in engine and "assess_population_coverage" in engine,
        "v2_paths_separate_from_v1": 'Path("regulatory/sec/form13f/feasibility_v2")' in engine and 'Path("regulatory/sec/form13f/feasibility_v1")' not in engine,
        "runner_no_arbitrary_scope_args": "argparse" not in runner and "sys.argv" not in runner,
        "runner_declares_probe_boundary": "Complete source scope: NOT PROVEN BY THIS PROBE" in runner and "Scientific freeze authority: NOT GRANTED" in runner,
        "workflow_runs_v2_validator": "validate_alpha_gate_sec_13f_feasibility_v2.py" in workflow,
        "workflow_runs_research_gate_audit": "validate_research_gate_calibration.py" in workflow,
        "documentation_present": SEC_13F_FEASIBILITY_V2_CONTRACT in doc and SEC_13F_FEASIBILITY_V2_FINGERPRINT in doc and "PROBE_ONLY" in doc,
    }
    for name, passed in checks.items():
        print(f"{name}: {passed}")
    if not all(checks.values()):
        return 2
    tree = ast.parse(engine)
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    for fragment in ("packages.execution", "packages.brokers", "packages.backtesting.phase26"):
        if any(fragment in name for name in imported):
            raise AssertionError(f"forbidden SEC 13F v2 feasibility import: {fragment}")
    print("ATLAS SEC Form 13F audit-aligned bounded-probe contracts: PASS")
    print(f"Feasibility contract: {SEC_13F_FEASIBILITY_V2_CONTRACT}")
    print(f"Feasibility fingerprint: {SEC_13F_FEASIBILITY_V2_FINGERPRINT}")
    print("Population scope: PROBE_ONLY")
    print("Complete source capacity: NOT PROVEN")
    print("Market outcomes/protected returns: UNREAD")
    print("Scientific freeze authority: NOT GRANTED")
    print("Phase33 authority: BLOCKED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
