from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase28_blindness import PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION
from packages.backtesting.phase28_closeout import (
    PHASE28_ARCHITECTURE_AUDIT_CONTRACT_VERSION,
    PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION,
    phase28_architecture_audit_checks,
    phase28_disposition,
)
from packages.backtesting.phase28_confirmation import (
    PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE28_PROTECTED_READ_PLAN_CONTRACT_VERSION,
    PHASE28_SUPPORT_OVERLAY_CONTRACT_VERSION,
)
from packages.backtesting.phase28_network import lead_lag_edge
from packages.backtesting.phase28_policy import (
    PHASE28_AUTOMATION_WRITES,
    PHASE28_AUTOMATIC_BROKER_FAILOVER,
    PHASE28_BROKER_READS,
    PHASE28_BROKER_WRITES,
    PHASE28_CANDIDATES,
    PHASE28_COMMON_RETURN_MIN_PEERS,
    PHASE28_LEAD_LAG_PAIRS,
    PHASE28_LIVE_WRITES,
    PHASE28_MAX_LEADERS,
    PHASE28_MIN_LEADERS,
    PHASE28_MIN_VALID_LAG_PAIRS,
    PHASE28_ORDER_WRITES,
    PHASE28_PAPER_SUBMITS,
    PHASE28_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE28_PROVIDER_READS,
    PHASE28_PROVIDER_WRITES,
    PHASE28_RAW_SIGNAL_FIELDS,
    PHASE28_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE28_SIGNAL_TAIL_FRACTION,
    PHASE28_SOURCE_PHASE27_MERGE,
    phase28_policy_fingerprint,
)
from packages.backtesting.phase28_population import (
    PHASE28_POPULATION_REPORT_CONTRACT_VERSION,
    PHASE28_REQUIRED_CLOSES,
    PHASE28_REQUIRED_RESIDUAL_RETURNS,
)
from packages.backtesting.phase28_research import (
    PHASE28_RESEARCH_REPORT_CONTRACT_VERSION,
    select_fixed_tail,
)
from packages.backtesting.phase28_runner import PHASE28_CUMULATIVE_REPORT_CONTRACT_VERSION
from packages.backtesting.phase28_validation import PHASE28_VALIDATION_CONTRACT_VERSION


def _tail_contract() -> bool:
    rows = [
        {
            "as_of_date": date(2026, 1, 2),
            "instrument_id": f"i-{index:02d}",
            "phase28_score": 1.0,
        }
        for index in range(10)
    ]
    selected = select_fixed_tail(pd.DataFrame(rows))
    return len(selected) == 2 and list(selected["instrument_id"].astype(str)) == ["i-00", "i-01"]


def _asymmetric_lead_contract() -> bool:
    rng = np.random.default_rng(280228)
    count = 90
    start = date(2025, 1, 2)
    dates = [start + timedelta(days=index) for index in range(count)]
    peer = rng.normal(0.0, 1.0, size=count)
    focal = np.empty(count)
    focal[0] = 0.0
    focal[1:] = peer[:-1] + rng.normal(0.0, 0.03, size=count - 1)
    residuals = pd.DataFrame({"focal": focal, "peer": peer}, index=dates)
    edge = lead_lag_edge(
        residuals,
        focal_id="focal",
        peer_id="peer",
        estimation_end=dates[-1],
    )
    return bool(
        edge is not None
        and edge.valid_pairs == PHASE28_LEAD_LAG_PAIRS
        and edge.forward_corr > 0.0
        and edge.asymmetry > 0.0
    )


def main() -> None:
    confirmation_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase28_confirmation.py"
    ).read_text(encoding="utf-8")
    research_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase28_research.py"
    ).read_text(encoding="utf-8")
    validation_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase28_validation.py"
    ).read_text(encoding="utf-8")

    external_values = (
        PHASE28_PROVIDER_READS,
        PHASE28_PROVIDER_WRITES,
        PHASE28_BROKER_READS,
        PHASE28_BROKER_WRITES,
        PHASE28_ORDER_WRITES,
        PHASE28_PAPER_SUBMITS,
        PHASE28_LIVE_WRITES,
        PHASE28_AUTOMATION_WRITES,
    )
    architecture = phase28_architecture_audit_checks(PROJECT_ROOT)
    negative_disposition, negative_next = phase28_disposition(())
    positive_disposition, positive_next = phase28_disposition(("supported-alpha",))
    checks = {
        "phase28_policy_fingerprint_present": len(phase28_policy_fingerprint()) == 64,
        "source_phase27_merge_frozen": PHASE28_SOURCE_PHASE27_MERGE
        == "dc015f51232dc66ba94b6175c276a0227d5a3761",
        "frozen_global_candidate_count_8": len(PHASE28_CANDIDATES) == 8,
        "frozen_signal_family_count_4": len(PHASE28_RAW_SIGNAL_FIELDS) == 4,
        "network_common_peer_min_5": PHASE28_COMMON_RETURN_MIN_PEERS == 5,
        "network_lag_pairs_60": PHASE28_LEAD_LAG_PAIRS == 60,
        "network_min_valid_pairs_50": PHASE28_MIN_VALID_LAG_PAIRS == 50,
        "network_leader_bounds_2_to_3": PHASE28_MIN_LEADERS == 2 and PHASE28_MAX_LEADERS == 3,
        "history_geometry_63_closes_62_returns": PHASE28_REQUIRED_CLOSES == 63
        and PHASE28_REQUIRED_RESIDUAL_RETURNS == 62,
        "fixed_tail_fraction_20pct": PHASE28_SIGNAL_TAIL_FRACTION == 0.20
        and _tail_contract(),
        "asymmetric_lead_contract": _asymmetric_lead_contract(),
        "runner_up_substitution_disabled": PHASE28_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_returns_before_finalists_disabled": PHASE28_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED
        is False,
        "automatic_broker_failover_disabled": PHASE28_AUTOMATIC_BROKER_FAILOVER is False,
        "external_authority_zero": all(value == 0 for value in external_values),
        "population_contract_present": bool(PHASE28_POPULATION_REPORT_CONTRACT_VERSION),
        "research_contract_present": bool(PHASE28_RESEARCH_REPORT_CONTRACT_VERSION),
        "blindness_contract_present": bool(PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION),
        "confirmation_contract_present": bool(PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION),
        "read_plan_contract_is_immutable_exact_keys": "immutable-resumable-exact-signal-keys"
        in PHASE28_PROTECTED_READ_PLAN_CONTRACT_VERSION,
        "support_overlay_historical_only_contract_present": bool(
            PHASE28_SUPPORT_OVERLAY_CONTRACT_VERSION
        ),
        "validation_contract_present": bool(PHASE28_VALIDATION_CONTRACT_VERSION),
        "cumulative_contract_present": bool(PHASE28_CUMULATIVE_REPORT_CONTRACT_VERSION),
        "architecture_audit_contract_present": bool(PHASE28_ARCHITECTURE_AUDIT_CONTRACT_VERSION),
        "closeout_contract_present": bool(PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION),
        "architecture_audit_checks_pass": all(architecture.values()),
        "negative_result_is_accepted_negative": negative_disposition == "ACCEPTED_NEGATIVE",
        "negative_result_blocks_phase29_signal_to_trade_entry": negative_next is False,
        "supported_result_is_accepted_positive": positive_disposition == "ACCEPTED_POSITIVE",
        "supported_result_can_satisfy_phase29_entry": positive_next is True,
        "research_has_global_holm": "holm_bonferroni(" in research_source
        and "len(holm) == 8" in research_source,
        "research_has_no_model_tuning_loop": "tune_hyperparameters" not in research_source,
        "confirmation_zero_finalists_skips_read_plan": "if not finalist_entries:" in confirmation_source
        and "SKIPPED_ZERO_FINALISTS" in confirmation_source,
        "confirmation_writes_read_plan_before_outcome_join": confirmation_source.index(
            "self._ensure_read_plan("
        )
        < confirmation_source.index("self._join_outcomes(query_keys)"),
        "confirmation_reads_only_query_keys": "phase28_query_keys" in confirmation_source
        and "ON b.symbol = q.ticker" in confirmation_source,
        "validator_independent_of_phase28_network_helpers": "from .phase28_network" not in validation_source,
        "validator_rebuilds_network_sample": "_network_sample_reconciliation(" in validation_source,
    }

    print(f"Phase 28 policy fingerprint: {phase28_policy_fingerprint()}")
    print(f"Phase 28 population contract: {PHASE28_POPULATION_REPORT_CONTRACT_VERSION}")
    print(f"Phase 28 research contract: {PHASE28_RESEARCH_REPORT_CONTRACT_VERSION}")
    print(f"Phase 28 blindness contract: {PHASE28_BLINDNESS_AUDIT_CONTRACT_VERSION}")
    print(f"Phase 28 confirmation contract: {PHASE28_CONFIRMATION_REPORT_CONTRACT_VERSION}")
    print(f"Phase 28 validation contract: {PHASE28_VALIDATION_CONTRACT_VERSION}")
    print(f"Phase 28 cumulative contract: {PHASE28_CUMULATIVE_REPORT_CONTRACT_VERSION}")
    print(f"Phase 28 architecture audit contract: {PHASE28_ARCHITECTURE_AUDIT_CONTRACT_VERSION}")
    print(f"Phase 28 closeout contract: {PHASE28_CLOSEOUT_REPORT_CONTRACT_VERSION}")
    for name, value in architecture.items():
        print(f"  audit.{name}: {value}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 28 contract validation failed: " + ", ".join(failed))
    print("Phase 28 cross-stock lead-lag alpha and closeout contracts: PASS")


if __name__ == "__main__":
    main()
