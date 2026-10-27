from __future__ import annotations

"""V27 offline fixed 1..5-session SPY quote sensitivity from original archives.

Historical observed bid/ask source diagnosis, NOT fills, strategy performance,
or portfolio simulation. Registers the trial before any later quote outcomes.
No provider/broker access. Retains all missing source/contract observations.
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
    audit_original_spy_pair_observations,
    register_outcome_inspection_trial,
    TRIAL_LEDGER_REL,
)
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDraft, StrategyTrialStage, StrategyTrialDisposition,
)
from packages.simulation.options_native_fixed_hold_quote_sweep_v27 import (
    evaluate_fixed_hold_quote_scenarios,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)
TRIAL_ID = "options-native.spy-fixed-hold-1to5-original-quote-sweep.v27"


def _register_trial(settings) -> str:
    register_outcome_inspection_trial(settings)
    path = settings.resolved_path(TRIAL_LEDGER_REL)
    ledger = StrategyTrialLedger(path)
    previous = {record.trial_id: record for record in ledger.read()}
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
            "Observe same original CALL/PUT pairs with fixed 1-5 XNYS"
            " session holding periods and explicit 10:00 bid/ask fee stress.",
        ),
        notes=(
            "EXPLORATORY retrospective quote sensitivity only, not strategy selection.",
            "Frozen pair eligibility 30-45 DTE 30s age <=15% spread <=1s skew.",
            "Five exit sessions fixed before any exit observations are inspected.",
            "All initial entry pairs remain in denominator even without exit quotes.",
            "Every missing contract/source is unresolved, not a losing or winning fill.",
            "Trial does not reuse the consumed 2026 master holdout.",
        ),
    )
    existing = previous.get(TRIAL_ID)
    if existing is not None:
        if (existing.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
                or existing.feature_fingerprint != draft.feature_fingerprint
                or existing.stage != draft.stage
                or existing.disposition != draft.disposition
                or existing.performance_outcomes_opened
                or existing.master_protected_return_rows_read):
            raise ValueError("V27_FROZEN_RESEARCH_TRIAL_DRIFT")
    else:
        ledger.append(draft)
    return TRIAL_ID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=None,
                        help="New diagnostic report path; never overwrites")
    args = parser.parse_args(argv)
    print("ATLAS V27 SPY ORIGINAL QUOTE FIXED-HOLD SCENARIOS", flush=True)
    print("  provider_requests=0 broker_requests=0 historical_fills=0", flush=True)
    try:
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError("V27_OUTPUT_EXISTS_NO_OVERWRITE")
        settings = load_settings(ROOT, "development")
        tid = _register_trial(settings)
        print("  preregistered_outcome_trial=" + tid, flush=True)
        report = audit_original_spy_pair_observations(
            settings, args.manifest, args.candidate_plan,
            evaluator=evaluate_fixed_hold_quote_scenarios,
        )
        if report["contract"] != "atlas-spy-fixed-hold-original-quote-sweep-v27-research-only":
            raise ValueError("V27_RESEARCH_CONTRACT_CHANGED")
        content = json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as file:
                file.write(content)
        for hold, scenario in report["scenarios"].items():
            summary = scenario["hypothetical_10am_entry_ask_exit_bid_return_by_fee_per_contract_per_side"]["0.65"]
            print(
                f"  fixed_exit_session={hold}"
                f" eligible_pairs={scenario['eligible_entry_pair_count']}"
                f" quotes_matched={scenario['source_observed_same_contract_pair']}"
                f" missing_source={scenario['unobserved_due_to_missing_review_source']}"
                f" missing_contract_quality={scenario['unobserved_due_to_contract_absence_or_quality']}"
                f" mean_observed_pct_with_0.65_fee={summary['mean_pct']}"
                f" conditional_observations={summary['observations']}",
                flush=True,
            )
        print("  report_fingerprint=" + report["fingerprint"], flush=True)
        print("  COMPLETE: ORIGINAL_QUOTE_SENSITIVITY_ONLY actual_portfolio_pnl=NOT_EVALUATED", flush=True)
        if args.output is None:
            print("  Use --output NEW_FILENAME.json to persist the derived report.")
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " original_archives_unmodified=True", flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
