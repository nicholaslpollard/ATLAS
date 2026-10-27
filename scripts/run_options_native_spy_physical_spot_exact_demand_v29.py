from __future__ import annotations

"""V29 one-ATM-identity/week and missing exact option exit request PREVIEW.

Reads the pinned original SPY stock native 1m sources (09:59 bars), then the
V26 immutable option archive reader. Does not call ThetaData or brokers,
modify archives, or infer 10:01 fills. Records new experimental work before
opening 2018–2025 later quote outcomes. Source prices remain PIT-unqualified.
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
from packages.data.options_native_spy_development_clock_coverage_v1 import (
    review_spy_development_minute_coverage,
)
from packages.data.options_native_spy_physical_spot_exact_demand_v29 import (
    CONTRACT, evaluate_spot_selected_exact_contract_demand,
)
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDraft, StrategyTrialStage, StrategyTrialDisposition,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)
from scripts.run_options_native_exit_coverage_attribution_v28 import (
    register_v28_trial,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)
TRIAL_ID = "options-native.spy-physical-spot-atm-exact-exit-demand.v29"


def register_v29_trial(settings) -> str:
    register_v28_trial(settings)
    ledger = StrategyTrialLedger(settings.resolved_path(TRIAL_LEDGER_REL))
    prior = {record.trial_id: record for record in ledger.read()}
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
            "Preselect the earliest 30-45 DTE SPY common strike nearest"
            " the original accepted 09:59 regular-minute observed stock spot,"
            " retaining no quote-eligibility fallback, then enumerate exact"
            " missing CALL/PUT review contract quotes over five fixed sessions.",
        ),
        notes=(
            "Physical stock 09:59 raw bar is historically availability-UNKNOWN.",
            "Entry contract roster completeness and PIT option model inputs unknown.",
            "2018-2025 retrospective preview only; no provider or broker requests.",
            "Selected exit quotes and futures never influence selected strike.",
            "No option strategy signals, execution fills, account P&L or 2026 holdout.",
        ),
    )
    existing = prior.get(TRIAL_ID)
    if existing is not None:
        if (existing.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
                or existing.feature_fingerprint != draft.feature_fingerprint
                or existing.stage != draft.stage or existing.disposition != draft.disposition
                or existing.performance_outcomes_opened
                or existing.master_protected_return_rows_read):
            raise ValueError("V29_TRIAL_FROZEN_REGISTRATION_DRIFT")
    else:
        ledger.append(draft)
    return TRIAL_ID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=None,
                        help="New derived preview JSON path (never overwrite)")
    args = parser.parse_args(argv)
    print("ATLAS V29 SPY PHYSICAL-SPOT ATM IDENTITY AND TARGETED EXACT EXIT DEMAND")
    print("  provider_requests=0 broker_requests=0 model_fills=0")
    try:
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError("V29_OUTPUT_ALREADY_EXISTS")
        settings = load_settings(ROOT, "development")
        trial_id = register_v29_trial(settings)
        print("  preregistered_trial=" + trial_id, flush=True)
        stock = review_spy_development_minute_coverage(
            settings, progress=lambda msg: print("  SPY_NATIVE: " + msg, flush=True),
        )
        print(
            f"  spot_source_clocks={stock['observed_exact_clocks']}"
            f"/{stock['unique_exact_clocks_requested']}"
            f" full_raw_weekly_cases={stock['raw_complete_weekly_cases']}/411"
            " historically_available_spot=False",
            flush=True,
        )
        report = audit_original_spy_pair_observations(
            settings, args.manifest, args.candidate_plan,
            evaluator=lambda entries, read_source:
                evaluate_spot_selected_exact_contract_demand(
                    entries, read_source, stock_report=stock,
                ),
        )
        if report["contract"] != CONTRACT:
            raise ValueError("V29_REPORT_CONTRACT_DRIFT")
        content = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as file:
                file.write(content)
        print(
            f"  selected_provisional_weekly_pairs={report['provisional_entry_pairs']}"
            f" abstained_weekly_clocks={report['abstained_weekly_clocks']}"
            f" missing_exact_option_right_requests="
            f"{report['missing_exact_contract_right_request_count']}",
            flush=True,
        )
        print("  five_session_original_review_states="
              + str(report["selected_pair_review_source_states"]), flush=True)
        print("  research_fingerprint=" + report["fingerprint"], flush=True)
        print(
            "  COMPLETE: SOURCE_PREVIEW_ONLY PIT_SPOT_UNQUALIFIED"
            " historical_trades=NONE provider_requests=0", flush=True,
        )
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__ + ": " + str(exc)[:400]
            + " original_data_unmodified=True",
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
