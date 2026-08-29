from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_semantic_feasibility import (
    PHASE32_PROVIDER_PUBLISHED_DISCLOSURE_HISTORY,
    PHASE32_SEMANTIC_DECLARED_MASSIVE_PLAN,
    PHASE32_SEMANTIC_SAFE_HISTORY_START,
    Phase32SemanticFeasibilityError,
    Phase32SemanticSourceFeasibility,
    phase32_semantic_feasibility_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase32 import MassivePhase32SECIndexClient
from packages.providers.massive.phase32_semantic import MassivePhase32SemanticClient
from packages.providers.massive.rest import MassiveRESTClient
from packages.providers.sec_edgar import SECEDGARClient


def main() -> int:
    print("ATLAS Phase 32 — 8-K Semantic Source Qualification")
    print(f"Frozen semantic-source fingerprint: {phase32_semantic_feasibility_fingerprint()}")
    print(f"Declared Massive plan: {PHASE32_SEMANTIC_DECLARED_MASSIVE_PLAN}")
    print(
        "Sources: Massive 8-K index + disclosures + text + disclosure taxonomy, "
        "with official SEC submissions reconciliation"
    )
    print(
        "Provider-published disclosure history expectation: "
        f"{PHASE32_PROVIDER_PUBLISHED_DISCLOSURE_HISTORY}"
    )
    print(f"Frozen safe semantic history start: {PHASE32_SEMANTIC_SAFE_HISTORY_START}")
    print("Scope: source coverage, taxonomy, text grounding, ticker/accession/SEC provenance only")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    try:
        settings = load_settings()
        rest = MassiveRESTClient(settings)
        report = Phase32SemanticSourceFeasibility(
            settings,
            MassivePhase32SECIndexClient(rest),
            MassivePhase32SemanticClient(rest),
            SECEDGARClient(),
        ).run()
    except (Phase32SemanticFeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("Phase 32 semantic source qualification: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "Stop here. Diagnose and repair the source/provenance defect before any "
            "hypothesis freeze or market-outcome read."
        )
        return 2

    print("Phase 32 semantic source qualification: PASS")
    print(
        f"Taxonomy: rows={report['taxonomy_rows']} versions={report['taxonomy_versions']} "
        f"sha256={report['taxonomy_sha256']}"
    )
    for window in report["windows"]:
        print(
            f"  {window['label']}: index_rows={window['index_rows']} "
            f"disclosures={window['disclosure_rows']} "
            f"overlap={window['original_8k_overlap_rows']} "
            f"samples={len(window['sampled_accessions'])} "
            f"covered={window['covered_by_safe_history']}"
        )
    print(f"Total disclosure rows: {report['total_disclosure_rows']}")
    print(f"Total sampled accessions: {report['total_sampled_accessions']}")
    print(f"Total text records fetched: {report['total_text_records_fetched']}")
    print(f"Total SEC records fetched: {report['total_sec_records_fetched']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Semantic feasibility report: {report['report_path']}")
    print(
        "Next scientific action: use only accepted source/taxonomy evidence to freeze "
        "the finite Phase32 hypothesis family and complete scientific contract before returns."
    )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
