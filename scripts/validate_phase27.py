from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting.phase27_blindness import PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION
from packages.backtesting.phase27_confirmation import (
    PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION,
    PHASE27_SUPPORT_OVERLAY_CONTRACT_VERSION,
)
from packages.backtesting.phase27_models import candidate_param_grid, select_fixed_tail
from packages.backtesting.phase27_policy import (
    PHASE27_AUTOMATION_WRITES,
    PHASE27_AUTOMATIC_BROKER_FAILOVER,
    PHASE27_BROKER_READS,
    PHASE27_BROKER_WRITES,
    PHASE27_CANDIDATES,
    PHASE27_HGB_MIN_SAMPLES_LEAF,
    PHASE27_LIVE_WRITES,
    PHASE27_ORDER_WRITES,
    PHASE27_PAPER_SUBMITS,
    PHASE27_PREDICTOR_FIELDS,
    PHASE27_PROVIDER_READS,
    PHASE27_PROVIDER_WRITES,
    PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE27_SIGNAL_TAIL_FRACTION,
    phase27_policy_fingerprint,
)
from packages.backtesting.phase27_population import transformed_feature_names
from packages.backtesting.phase27_research import PHASE27_RESEARCH_REPORT_CONTRACT_VERSION
from packages.backtesting.phase27_runner import PHASE27_CUMULATIVE_REPORT_CONTRACT_VERSION
from packages.backtesting.phase27_validation import PHASE27_VALIDATION_CONTRACT_VERSION


def _candidate(candidate_id: str):
    return next(item for item in PHASE27_CANDIDATES if item.candidate_id == candidate_id)


def _tail_contract() -> bool:
    rows = [
        {
            "as_of_date": date(2026, 1, 2),
            "instrument_id": f"i-{index:02d}",
            "phase27_score": float(index),
        }
        for index in range(10)
    ]
    selected = select_fixed_tail(pd.DataFrame(rows))
    return len(selected) == 2 and list(selected["instrument_id"].astype(str)) == ["i-08", "i-09"]


def main() -> None:
    confirmation_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase27_confirmation.py"
    ).read_text(encoding="utf-8")
    blindness_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase27_blindness.py"
    ).read_text(encoding="utf-8")
    research_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase27_research.py"
    ).read_text(encoding="utf-8")

    external_values = (
        PHASE27_PROVIDER_READS,
        PHASE27_PROVIDER_WRITES,
        PHASE27_BROKER_READS,
        PHASE27_BROKER_WRITES,
        PHASE27_ORDER_WRITES,
        PHASE27_PAPER_SUBMITS,
        PHASE27_LIVE_WRITES,
        PHASE27_AUTOMATION_WRITES,
    )
    checks = {
        "phase27_policy_fingerprint_present": len(phase27_policy_fingerprint()) == 64,
        "frozen_global_candidate_count_8": len(PHASE27_CANDIDATES) == 8,
        "exact_learned_predictor_count_29": len(PHASE27_PREDICTOR_FIELDS) == 29
        and len(transformed_feature_names()) == 29,
        "priority_grid_count_1": len(candidate_param_grid(_candidate("priority_tail_long"))) == 1,
        "ridge_grid_count_4": len(candidate_param_grid(_candidate("ridge_relative_long"))) == 4,
        "hgb_grid_count_16": len(candidate_param_grid(_candidate("hgb_relative_long"))) == 16,
        "pairwise_grid_count_3": len(candidate_param_grid(_candidate("pairwise_rank_long"))) == 3,
        "hgb_min_leaf_50": PHASE27_HGB_MIN_SAMPLES_LEAF == 50,
        "fixed_tail_fraction_20pct": PHASE27_SIGNAL_TAIL_FRACTION == 0.20
        and _tail_contract(),
        "runner_up_substitution_disabled": PHASE27_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "automatic_broker_failover_disabled": PHASE27_AUTOMATIC_BROKER_FAILOVER is False,
        "external_authority_zero": all(value == 0 for value in external_values),
        "research_contract_present": bool(PHASE27_RESEARCH_REPORT_CONTRACT_VERSION),
        "blindness_contract_present": bool(PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION),
        "confirmation_contract_present": bool(PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION),
        "read_plan_contract_present": "immutable-resumable-exact-signal-keys"
        in PHASE27_PROTECTED_READ_PLAN_CONTRACT_VERSION,
        "support_overlay_historical_only_contract_present": bool(
            PHASE27_SUPPORT_OVERLAY_CONTRACT_VERSION
        ),
        "validation_contract_present": bool(PHASE27_VALIDATION_CONTRACT_VERSION),
        "cumulative_contract_present": bool(PHASE27_CUMULATIVE_REPORT_CONTRACT_VERSION),
        "research_uses_nested_oos_selection": "selection_oos_signals(" in research_source
        and "outer_folds=PHASE27_SELECTION_FOLDS" in research_source,
        "blindness_checks_preexisting_confirmation_artifacts": (
            "phase27_confirmation_artifacts_absent_before_audit" in blindness_source
        ),
        "confirmation_writes_read_plan_before_outcome_join": (
            confirmation_source.index("self._ensure_read_plan(")
            < confirmation_source.index("self._join_outcomes(query_keys)")
        ),
        "confirmation_reads_only_frozen_query_keys": "phase27_query_keys" in confirmation_source
        and "ON b.symbol = q.ticker" in confirmation_source,
        "confirmation_returns_existing_immutable_result": (
            "if self.report_path().is_file():" in confirmation_source
        ),
    }

    print(f"Phase 27 policy fingerprint: {phase27_policy_fingerprint()}")
    print(f"Phase 27 research contract: {PHASE27_RESEARCH_REPORT_CONTRACT_VERSION}")
    print(f"Phase 27 blindness contract: {PHASE27_BLINDNESS_AUDIT_CONTRACT_VERSION}")
    print(f"Phase 27 confirmation contract: {PHASE27_CONFIRMATION_REPORT_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 27 contract validation failed: " + ", ".join(failed))
    print("Phase 27 cross-sectional alpha contracts: PASS")


if __name__ == "__main__":
    main()
