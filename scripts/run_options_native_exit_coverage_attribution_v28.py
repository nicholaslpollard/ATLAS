from __future__ import annotations

"""Offline exact-contract exit attrition attribution on V24 acquired SPY data.

Preregisters retrospective source research before historical outcome inspection.
No provider requests, no invented trade fills and no strategy promotion.
"""

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import PINNED_MANIFEST_FINGERPRINT
from packages.data.options_native_original_pair_diagnostic_v26 import (
    audit_original_spy_pair_observations, TRIAL_LEDGER_REL,
)
from packages.data.options_native_exit_coverage_attribution_v28 import (
    CONTRACT, evaluate_exit_coverage_root_causes,
)
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDraft, StrategyTrialStage, StrategyTrialDisposition,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)
from scripts.run_options_native_fixed_hold_quote_sweep_v27 import _register_trial as register_v27_trial

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)
TRIAL_ID = "options-native.spy-exact-contract-coverage-attribution.v28"


def register_v28_trial(settings) -> str:
    register_v27_trial(settings)
    ledger = StrategyTrialLedger(settings.resolved_path(TRIAL_LEDGER_REL))
    before = {r.trial_id: r for r in ledger.read()}
    draft = StrategyTrialDraft(
        trial_id=TRIAL_ID,
        registered_at_utc=datetime.now(UTC),
        stage=StrategyTrialStage.SPECIFICATION,
        disposition=StrategyTrialDisposition.REGISTERED,
        family_ids=("options_native_underpriced_movement",),
        strategy_ids=(PILOT_ID,),
        strategy_policy_fingerprint=SPECIFICATION_FINGERPRINT,
        feature_fingerprint=DATA_FINGERPRINT,
        hypotheses=(
            "Decompose five-session retained historical CALL/PUT exit-pair"
            " attrition into no source, missing contract rights, independent"
            " quote-quality failures and synchronization failures.",
        ),
        notes=(
            "Exploratory source only, no new trading parameter selection.",
            "Reuse V27 original 30-45 DTE entry cohort and exact exit-review days.",
            "Local DTE screening only; out-of-DTE source rows remain intact.",
            "Missing rights in response do not prove options were absent from market.",
            "Already consumed 2026 master holdout remains unavailable.",
        ),
    )
    previous = before.get(TRIAL_ID)
    if previous is not None:
        if (previous.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
                or previous.feature_fingerprint != draft.feature_fingerprint
                or previous.stage != draft.stage
                or previous.disposition != draft.disposition
                or previous.performance_outcomes_opened
                or previous.master_protected_return_rows_read):
            raise ValueError("V28_REGISTERED_TRIAL_DRIFT")
    else:
        ledger.append(draft)
    return TRIAL_ID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=None,
                        help="New derived JSON report path; existing files never overwritten")
    args = parser.parse_args(argv)
    print("ATLAS V28 EXACT-CONTRACT EXIT ATTRITION", flush=True)
    print("  mode=OFFLINE_SOURCE_ONLY provider_requests=0 broker_requests=0", flush=True)
    try:
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError("V28_OUTPUT_EXISTS_NO_OVERWRITE")
        settings = load_settings(ROOT, "development")
        tid = register_v28_trial(settings)
        print("  research_trial=" + tid, flush=True)
        result = audit_original_spy_pair_observations(
            settings, args.manifest, args.candidate_plan,
            evaluator=evaluate_exit_coverage_root_causes,
        )
        if result["contract"] != CONTRACT:
            raise ValueError("V28_REPORT_CONTRACT_DRIFT")
        content = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as target:
                target.write(content)
        for hold, case in result["scenarios"].items():
            print(
                f"  hold_sessions={hold} eligible={case['eligible_entry_pairs']}"
                f" matched={case['exact_contract_pair_match']}"
                f" breakdown={case['reasons']}"
                f" quality_legs={case['quote_quality_rejection_reasons_individual_legs']}",
                flush=True,
            )
        print(
            f"  distinct_contract_rights_absent_from_retained_responses="
            f"{result['distinct_absent_original_contract_rights_across_all_exit_dates']}",
            flush=True,
        )
        print("  fingerprint=" + result["fingerprint"], flush=True)
        print("  COMPLETE: EXPLANATORY_ONLY historical_account_profit=NOT_EVALUATED", flush=True)
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " original_option_sources_unmodified=True", flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
