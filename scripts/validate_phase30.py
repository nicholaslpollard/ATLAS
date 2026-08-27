from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase30_feasibility import (
    PHASE30_ALPHA_HYPOTHESES_FROZEN,
    PHASE30_AUTOMATIC_BROKER_FAILOVER,
    PHASE30_AUTOMATION_WRITES,
    PHASE30_BROKER_READS,
    PHASE30_BROKER_WRITES,
    PHASE30_FEASIBILITY_CONTRACT_VERSION,
    PHASE30_LIVE_WRITES,
    PHASE30_ORDER_WRITES,
    PHASE30_PAPER_SUBMITS,
    PHASE30_PROBE_WINDOWS,
    PHASE30_PROTECTED_OUTCOME_READS_ALLOWED,
    PHASE30_PROVIDER_INSIGHTS_AUTHORITY,
    PHASE30_PROVIDER_READS_ALLOWED,
    PHASE30_PROVIDER_WRITES,
    PHASE30_SOURCE_PHASE29_MERGE,
    PHASE30_TARGET_OUTCOME_READS_ALLOWED,
    phase30_feasibility_fingerprint,
)
from packages.providers.massive.phase30 import (
    PHASE30_NEWS_ENDPOINT,
    PHASE30_NEWS_ORDER,
    PHASE30_NEWS_PAGE_LIMIT,
    PHASE30_NEWS_SORT_FIELD,
)


def main() -> None:
    provider_source = (
        PROJECT_ROOT / "packages" / "providers" / "massive" / "phase30.py"
    ).read_text(encoding="utf-8")
    feasibility_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase30_feasibility.py"
    ).read_text(encoding="utf-8")
    rest_source = (
        PROJECT_ROOT / "packages" / "providers" / "massive" / "rest.py"
    ).read_text(encoding="utf-8")
    runner_source = (
        PROJECT_ROOT / "scripts" / "run_phase30_news_feasibility.py"
    ).read_text(encoding="utf-8")
    spec_path = PROJECT_ROOT / "docs" / "phase30_event_driven_public_information_alpha.md"
    spec_text = spec_path.read_text(encoding="utf-8") if spec_path.is_file() else ""

    exact_windows = tuple(
        (window.label, window.start_utc, window.end_utc) for window in PHASE30_PROBE_WINDOWS
    )
    expected_windows = (
        ("research_start", "2021-08-16T00:00:00Z", "2021-08-16T23:59:59Z"),
        ("development_end", "2026-05-06T00:00:00Z", "2026-05-06T23:59:59Z"),
        ("protected_start", "2026-05-12T00:00:00Z", "2026-05-12T23:59:59Z"),
        ("protected_end", "2026-08-11T00:00:00Z", "2026-08-11T23:59:59Z"),
    )
    mutation_values = (
        PHASE30_PROVIDER_WRITES,
        PHASE30_BROKER_READS,
        PHASE30_BROKER_WRITES,
        PHASE30_ORDER_WRITES,
        PHASE30_PAPER_SUBMITS,
        PHASE30_LIVE_WRITES,
        PHASE30_AUTOMATION_WRITES,
    )
    forbidden_outcome_tokens = (
        "phase26_observations",
        "directional_return",
        "forward_return",
        "future_close",
        "outcome_evidence",
        "read_parquet",
        "duckdb_connection",
    )

    checks = {
        "feasibility_contract_present": bool(PHASE30_FEASIBILITY_CONTRACT_VERSION),
        "feasibility_fingerprint_present": len(phase30_feasibility_fingerprint()) == 64,
        "source_phase29_merge_frozen": PHASE30_SOURCE_PHASE29_MERGE
        == "87c9450e1b21606b83489f16ff326235ae92eb2b",
        "exact_boundary_probe_windows_frozen": exact_windows == expected_windows,
        "accepted_massive_news_endpoint_reused": PHASE30_NEWS_ENDPOINT == "/v2/reference/news"
        and "self.rest.iter_pages(PHASE30_NEWS_ENDPOINT, params)" in provider_source,
        "news_query_is_chronological_and_bounded": PHASE30_NEWS_ORDER == "asc"
        and PHASE30_NEWS_SORT_FIELD == "published_utc"
        and PHASE30_NEWS_PAGE_LIMIT == 1000
        and '"published_utc.gte"' in provider_source
        and '"published_utc.lte"' in provider_source,
        "phase30_does_not_create_parallel_http_authority": "urlopen" not in provider_source
        and "Request(" not in provider_source
        and "get_secret" not in provider_source,
        "accepted_rest_blocks_cross_host_pagination": "Massive pagination URL changed host"
        in rest_source,
        "provider_native_tickers_not_uppercased": ".upper()" not in provider_source,
        "conflicting_duplicate_ids_fail_closed": "conflicting payloads for article id"
        in provider_source,
        "immutable_evidence_hash_guard_present": "historical news evidence drifted"
        in feasibility_source
        and "sha256_file" in feasibility_source,
        "alpha_hypotheses_not_frozen": PHASE30_ALPHA_HYPOTHESES_FROZEN is False,
        "target_outcomes_forbidden": PHASE30_TARGET_OUTCOME_READS_ALLOWED is False,
        "protected_outcomes_forbidden": PHASE30_PROTECTED_OUTCOME_READS_ALLOWED is False,
        "provider_reads_only_authority": PHASE30_PROVIDER_READS_ALLOWED is True
        and all(value == 0 for value in mutation_values),
        "automatic_broker_failover_disabled": PHASE30_AUTOMATIC_BROKER_FAILOVER is False,
        "provider_insights_provenance_only": PHASE30_PROVIDER_INSIGHTS_AUTHORITY
        == "RAW_PROVENANCE_ONLY_NOT_AUTHORIZED_FOR_ALPHA",
        "feasibility_has_no_market_outcome_reader": not any(
            token in feasibility_source.lower() for token in forbidden_outcome_tokens
        ),
        "runner_states_no_alpha_and_no_outcomes": "Alpha hypotheses: NOT YET FROZEN"
        in runner_source
        and "Target/protected market outcomes: FORBIDDEN / UNREAD" in runner_source,
        "phase30_spec_present": spec_path.is_file(),
        "phase30_spec_separates_feasibility_from_scientific_freeze": (
            "ALPHA HYPOTHESES: NOT YET FROZEN" in spec_text
            and "Only then may target performance be read." in spec_text
            and "target outcome reads: FORBIDDEN" in spec_text
        ),
    }

    print(f"Phase 30 feasibility fingerprint: {phase30_feasibility_fingerprint()}")
    print(f"Phase 30 feasibility contract: {PHASE30_FEASIBILITY_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 30 historical-news feasibility contract validation failed: " + ", ".join(failed))
    print("Phase 30 historical-news feasibility contracts: PASS")


if __name__ == "__main__":
    main()
