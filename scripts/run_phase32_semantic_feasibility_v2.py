from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase32_semantic_feasibility_v2 import (
    PHASE32_SEMANTIC_V2_IDENTITY_RULE,
    PHASE32_SEMANTIC_V2_RESEARCH_START,
    PHASE32_SEMANTIC_V2_SUPPORT_RULE,
    PHASE32_SEMANTIC_V2_TICKER_RULE,
    Phase32SemanticSourceFeasibilityV2,
    Phase32SemanticV2FeasibilityError,
    phase32_semantic_v2_fingerprint,
)
from packages.core.exceptions import ProviderError
from packages.core.settings import load_settings
from packages.providers.massive.phase32 import MassivePhase32SECIndexClient
from packages.providers.massive.phase32_semantic import MassivePhase32SemanticClient
from packages.providers.massive.rest import MassiveRESTClient
from packages.providers.sec_edgar import SECEDGARClient


def main() -> int:
    print("ATLAS Phase 32 — 8-K Semantic Source Qualification V2")
    print(f"Frozen semantic V2 fingerprint: {phase32_semantic_v2_fingerprint()}")
    print(f"Empirical Phase32 research start: {PHASE32_SEMANTIC_V2_RESEARCH_START}")
    print(f"Identity rule: {PHASE32_SEMANTIC_V2_IDENTITY_RULE}")
    print(f"Ticker rule: {PHASE32_SEMANTIC_V2_TICKER_RULE}")
    print(f"Supporting-text rule: {PHASE32_SEMANTIC_V2_SUPPORT_RULE}")
    print("Scope: semantic source/provenance qualification only")
    print("Alpha hypotheses: NOT YET FROZEN")
    print("Target/protected market outcomes: FORBIDDEN / UNREAD")
    print("Broker/order/PAPER/LIVE activity: DISABLED")
    print()

    try:
        settings = load_settings()
        rest = MassiveRESTClient(settings)
        report = Phase32SemanticSourceFeasibilityV2(
            settings,
            MassivePhase32SECIndexClient(rest),
            MassivePhase32SemanticClient(rest),
            SECEDGARClient(),
        ).run()
    except (Phase32SemanticV2FeasibilityError, ProviderError, OSError, ValueError) as exc:
        print("Phase 32 semantic V2 source qualification: NOT ACCEPTED")
        print(f"Reason: {exc}")
        print(
            "Stop here. Diagnose and repair the V2 source/provenance defect before "
            "any hypothesis freeze or market-outcome read."
        )
        return 2

    print("Phase 32 semantic V2 source qualification: PASS")
    print(
        f"Taxonomy: rows={report['taxonomy_rows']} versions={report['taxonomy_versions']} "
        f"sha256={report['taxonomy_sha256']}"
    )
    for window in report["windows"]:
        print(
            f"  {window['label']}: index_rows={window['index_rows']} "
            f"disclosures={window['disclosure_rows']} "
            f"overlap={window['original_8k_overlap_rows']} "
            f"samples={len(window['sampled_accessions'])}"
        )
    print(f"Ticker relations: {report['ticker_relation_counts']}")
    diagnostics = report["items_text_scope_diagnostics"]
    print(
        "Items-text diagnostics (not an acceptance gate): "
        f"rows={diagnostics['disclosure_rows_checked']} "
        f"exact_substrings={diagnostics['exact_normalized_substring_rows']} "
        f"min_ordered={diagnostics['minimum_ordered_token_coverage']} "
        f"mean_ordered={diagnostics['mean_ordered_token_coverage']}"
    )
    print(f"Total disclosure rows: {report['total_disclosure_rows']}")
    print(f"Total sampled accessions: {report['total_sampled_accessions']}")
    print(f"Total text records fetched: {report['total_text_records_fetched']}")
    print(f"Total SEC records fetched: {report['total_sec_records_fetched']}")
    print(f"Target outcome rows read: {report['target_outcome_rows_read']}")
    print(f"Protected candidate rows read: {report['protected_candidate_rows_read']}")
    print(f"Protected return rows read: {report['protected_return_rows_read']}")
    print("Provider writes / broker reads / broker writes / orders / PAPER / LIVE: 0 / 0 / 0 / 0 / 0 / 0")
    print(f"Semantic V2 report: {report['report_path']}")
    print(
        "Next scientific action only after PASS: freeze the finite Phase32 hypothesis "
        "family and complete the full scientific contract before any return read."
    )
    print(f"Pass: {report['pass']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
