from __future__ import annotations

from packages.control_plane.phase19_http_server import PHASE19_HTTP_CONTRACT_VERSION
from packages.control_plane.phase19_observability import (
    PHASE19_CANDIDATE_LIMIT,
    PHASE19_LIVE_QUOTE_LIMIT,
    PHASE19_OBSERVABILITY_CONTRACT_VERSION,
    PHASE19_OUTCOME_LIMIT,
    PHASE19_RECENT_ARTIFACT_HOURS,
)
from packages.control_plane.phase19_policy import (
    PHASE19_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED,
    PHASE19_BROWSER_EXECUTION_AUTHORITY_ALLOWED,
    PHASE19_CREDENTIAL_VALUES_EXPOSED,
    PHASE19_LIVE_EXECUTION_PROMOTION_ALLOWED,
    PHASE19_LOCAL_ARTIFACT_READS_ALLOWED,
    PHASE19_MISSING_ARTIFACTS_FAIL_DISPLAY_ONLY,
    PHASE19_PROVIDER_READS_ALLOWED,
    PHASE19_PROVIDER_WRITES_ALLOWED,
    PHASE19_RAW_ACCOUNT_IDS_EXPOSED,
    PHASE19_STACKED_MERGE_BLOCKED_UNTIL_PHASE18_MERGED,
    phase19_policy_fingerprint,
    validate_phase19_policy,
)


def main() -> None:
    validate_phase19_policy()
    assert PHASE19_PROVIDER_READS_ALLOWED is False
    assert PHASE19_PROVIDER_WRITES_ALLOWED is False
    assert PHASE19_LOCAL_ARTIFACT_READS_ALLOWED is True
    assert PHASE19_MISSING_ARTIFACTS_FAIL_DISPLAY_ONLY is True
    assert PHASE19_LIVE_EXECUTION_PROMOTION_ALLOWED is False
    assert PHASE19_AUTOMATIC_CROSS_BROKER_FAILOVER_ALLOWED is False
    assert PHASE19_BROWSER_EXECUTION_AUTHORITY_ALLOWED is False
    assert PHASE19_CREDENTIAL_VALUES_EXPOSED is False
    assert PHASE19_RAW_ACCOUNT_IDS_EXPOSED is False
    assert PHASE19_STACKED_MERGE_BLOCKED_UNTIL_PHASE18_MERGED is True
    assert PHASE19_CANDIDATE_LIMIT == 50
    assert PHASE19_OUTCOME_LIMIT == 20
    assert PHASE19_LIVE_QUOTE_LIMIT == 20
    assert PHASE19_RECENT_ARTIFACT_HOURS == 96.0
    assert PHASE19_OBSERVABILITY_CONTRACT_VERSION == (
        "phase19-observability-v3-local-artifacts-live-market-candidates-ai-outcomes"
    )
    assert PHASE19_HTTP_CONTRACT_VERSION == (
        "phase19-http-v1-phase16-preserving-readonly-observability-extension"
    )
    fingerprint = phase19_policy_fingerprint()
    assert len(fingerprint) == 64
    print("Phase 19 validation: PASS")
    print(f"  policy fingerprint: {fingerprint}")
    print("  observability contract: v3 local live-market/candidate/AI/outcome diagnostics")
    print(f"  artifact recency threshold: {PHASE19_RECENT_ARTIFACT_HOURS:.0f}h diagnostic-only")
    print(f"  live quote display limit: {PHASE19_LIVE_QUOTE_LIMIT}")
    print("  live market snapshot source: local persisted Phase 5 state only")
    print("  local artifact reads: enabled")
    print("  Phase 19 provider reads: disabled")
    print("  Phase 19 provider writes: disabled")
    print("  browser execution authority: disabled")
    print("  live execution promotion: disabled")
    print("  automatic cross-broker failover: disabled")
    print("  stacked merge before Phase 18 closeout: blocked")


if __name__ == "__main__":
    main()
