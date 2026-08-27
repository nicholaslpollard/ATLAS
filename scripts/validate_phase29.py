from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from packages.backtesting.phase29_blindness import PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION
from packages.backtesting.phase29_confirmation import (
    PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION,
    PHASE29_PROTECTED_READ_PLAN_CONTRACT_VERSION,
    PHASE29_SUPPORT_OVERLAY_CONTRACT_VERSION,
)
from packages.backtesting.phase29_policy import (
    PHASE29_AUTOMATION_WRITES,
    PHASE29_AUTOMATIC_BROKER_FAILOVER,
    PHASE29_BROKER_READS,
    PHASE29_BROKER_WRITES,
    PHASE29_CANDIDATES,
    PHASE29_FORMATION_RETURN_SESSIONS,
    PHASE29_LIVE_WRITES,
    PHASE29_ORDER_WRITES,
    PHASE29_PAIR_FORMATION_PRICE_SESSIONS,
    PHASE29_PAPER_SUBMITS,
    PHASE29_PCA_COMPONENTS,
    PHASE29_PCA_MIN_PEERS,
    PHASE29_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED,
    PHASE29_PROVIDER_READS,
    PHASE29_PROVIDER_WRITES,
    PHASE29_RAW_SIGNAL_FIELDS,
    PHASE29_REQUIRED_CLOSES,
    PHASE29_RUNNER_UP_SUBSTITUTION_ALLOWED,
    PHASE29_SIGNAL_TAIL_FRACTION,
    PHASE29_SOURCE_PHASE28_MERGE,
    phase29_policy_fingerprint,
)
from packages.backtesting.phase29_population import PHASE29_POPULATION_REPORT_CONTRACT_VERSION
from packages.backtesting.phase29_relative_value import (
    nearest_pair_dislocations,
    pca_residual_dislocations,
)
from packages.backtesting.phase29_research import (
    PHASE29_RESEARCH_REPORT_CONTRACT_VERSION,
    holm_bonferroni,
    select_fixed_tail,
)
from packages.backtesting.phase29_runner import PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION
from packages.backtesting.phase29_validation import PHASE29_VALIDATION_CONTRACT_VERSION


def _tail_contract() -> bool:
    rows = [
        {"as_of_date": "2026-01-02", "instrument_id": f"i-{index:02d}", "phase29_score": 1.0}
        for index in range(10)
    ]
    selected = select_fixed_tail(pd.DataFrame(rows))
    return len(selected) == 2 and list(selected["instrument_id"].astype(str)) == ["i-00", "i-01"]


def _pca_leave_focal_contract() -> bool:
    rng = np.random.default_rng(290229)
    sessions = 60
    factors = rng.normal(0.0, 0.01, size=(sessions, 2))
    data = {}
    for index in range(8):
        data[f"i-{index}"] = (
            factors[:, 0] * (0.4 + 0.05 * index)
            + factors[:, 1] * (0.2 - 0.01 * index)
            + rng.normal(0.0, 0.001, sessions)
        )
    formation = pd.DataFrame(data)
    current = pd.Series({column: 0.001 * (index + 1) for index, column in enumerate(formation.columns)})
    first = pca_residual_dislocations(formation, current)
    shocked = current.copy()
    shocked["i-0"] += 0.10
    second = pca_residual_dislocations(formation, shocked)
    return bool(
        np.isclose(
            first["i-0"].factor_reconstruction,
            second["i-0"].factor_reconstruction,
            rtol=1e-12,
            atol=1e-12,
        )
        and second["i-0"].residual_dislocation > first["i-0"].residual_dislocation
    )


def _pair_freeze_contract() -> bool:
    x = np.linspace(0.0, 1.0, 60)
    formation = pd.DataFrame(
        {
            "focal": 100.0 * (1.0 + 0.04 * x + 0.002 * np.sin(5 * x)),
            "near": 50.0 * (1.0 + 0.04 * x + 0.0022 * np.sin(5 * x)),
            "far": 80.0 * (1.0 - 0.02 * x + 0.015 * np.cos(4 * x)),
        }
    )
    first = nearest_pair_dislocations(
        formation, pd.Series({"focal": 105.0, "near": 52.5, "far": 77.0})
    )
    second = nearest_pair_dislocations(
        formation, pd.Series({"focal": 130.0, "near": 40.0, "far": 120.0})
    )
    return bool(
        first["focal"].peer_instrument_id == "near"
        and second["focal"].peer_instrument_id == "near"
        and np.isclose(first["focal"].formation_distance, second["focal"].formation_distance)
    )


def main() -> None:
    research_source = (PROJECT_ROOT / "packages" / "backtesting" / "phase29_research.py").read_text(
        encoding="utf-8"
    )
    confirmation_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase29_confirmation.py"
    ).read_text(encoding="utf-8")
    validation_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase29_validation.py"
    ).read_text(encoding="utf-8")
    population_source = (
        PROJECT_ROOT / "packages" / "backtesting" / "phase29_population.py"
    ).read_text(encoding="utf-8")

    external_values = (
        PHASE29_PROVIDER_READS,
        PHASE29_PROVIDER_WRITES,
        PHASE29_BROKER_READS,
        PHASE29_BROKER_WRITES,
        PHASE29_ORDER_WRITES,
        PHASE29_PAPER_SUBMITS,
        PHASE29_LIVE_WRITES,
        PHASE29_AUTOMATION_WRITES,
    )
    holm = holm_bonferroni({candidate.candidate_id: 1.0 for candidate in PHASE29_CANDIDATES})
    checks = {
        "policy_fingerprint_present": len(phase29_policy_fingerprint()) == 64,
        "source_phase28_merge_frozen": PHASE29_SOURCE_PHASE28_MERGE
        == "285f112d51463dd1e06ea4e874a882ad98f71dc5",
        "candidate_count_4": len(PHASE29_CANDIDATES) == 4,
        "signal_family_count_2": len(PHASE29_RAW_SIGNAL_FIELDS) == 2,
        "required_closes_62": PHASE29_REQUIRED_CLOSES == 62,
        "formation_returns_60": PHASE29_FORMATION_RETURN_SESSIONS == 60,
        "pair_formation_60": PHASE29_PAIR_FORMATION_PRICE_SESSIONS == 60,
        "pca_three_components_min_eight_peers": PHASE29_PCA_COMPONENTS == 3
        and PHASE29_PCA_MIN_PEERS == 8,
        "fixed_tail_20pct": PHASE29_SIGNAL_TAIL_FRACTION == 0.20 and _tail_contract(),
        "pca_current_leave_focal_out": _pca_leave_focal_contract(),
        "pair_identity_frozen_before_current": _pair_freeze_contract(),
        "holm_global_four": len(holm) == 4 and "len(holm) != len(PHASE29_CANDIDATES)" in research_source,
        "no_outcome_model_training": "fit(" not in research_source and "predict(" not in research_source,
        "runner_up_substitution_disabled": PHASE29_RUNNER_UP_SUBSTITUTION_ALLOWED is False,
        "protected_before_finalists_disabled": PHASE29_PROTECTED_RETURNS_BEFORE_FINALISTS_ALLOWED is False,
        "automatic_broker_failover_disabled": PHASE29_AUTOMATIC_BROKER_FAILOVER is False,
        "external_authority_zero": all(value == 0 for value in external_values),
        "population_contract_present": bool(PHASE29_POPULATION_REPORT_CONTRACT_VERSION),
        "research_contract_present": bool(PHASE29_RESEARCH_REPORT_CONTRACT_VERSION),
        "blindness_contract_present": bool(PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION),
        "confirmation_contract_present": bool(PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION),
        "read_plan_is_immutable_exact_keys": "immutable-resumable-exact-signal-keys"
        in PHASE29_PROTECTED_READ_PLAN_CONTRACT_VERSION,
        "support_is_historical_only_contract": bool(PHASE29_SUPPORT_OVERLAY_CONTRACT_VERSION),
        "validation_contract_present": bool(PHASE29_VALIDATION_CONTRACT_VERSION),
        "cumulative_contract_present": bool(PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION),
        "population_uses_exact_expected_sessions": ".reindex(expected)" in population_source,
        "population_formation_ends_before_current": "formation_61 = numeric.iloc[:-1]" in population_source,
        "confirmation_zero_finalists_before_scoring": "if not finalist_entries:" in confirmation_source
        and confirmation_source.index("if not finalist_entries:")
        < confirmation_source.index("self._score_finalists("),
        "read_plan_written_before_outcomes": confirmation_source.index("self._ensure_read_plan(")
        < confirmation_source.index("self._join_outcomes(query_keys)"),
        "confirmation_queries_exact_signal_keys": "phase29_query_keys" in confirmation_source,
        "support_rejects_market_neutral_authority": '"market_neutral_pair_execution_authority": False'
        in confirmation_source,
        "validator_does_not_import_phase29_relative_value": "from .phase29_relative_value" not in validation_source,
        "validator_rebuilds_raw_sample": "_network_sample_reconciliation(" in validation_source,
    }

    print(f"Phase 29 policy fingerprint: {phase29_policy_fingerprint()}")
    print(f"Phase 29 population contract: {PHASE29_POPULATION_REPORT_CONTRACT_VERSION}")
    print(f"Phase 29 research contract: {PHASE29_RESEARCH_REPORT_CONTRACT_VERSION}")
    print(f"Phase 29 blindness contract: {PHASE29_BLINDNESS_AUDIT_CONTRACT_VERSION}")
    print(f"Phase 29 confirmation contract: {PHASE29_CONFIRMATION_REPORT_CONTRACT_VERSION}")
    print(f"Phase 29 validation contract: {PHASE29_VALIDATION_CONTRACT_VERSION}")
    print(f"Phase 29 cumulative contract: {PHASE29_CUMULATIVE_REPORT_CONTRACT_VERSION}")
    for name, value in checks.items():
        print(f"  {name}: {value}")
    if not all(checks.values()):
        failed = sorted(name for name, passed in checks.items() if not passed)
        raise SystemExit("Phase 29 contract validation failed: " + ", ".join(failed))
    print("Phase 29 relative-value statistical-arbitrage contracts: PASS")


if __name__ == "__main__":
    main()
