from __future__ import annotations

"""V32 offline original+V30 exact SPY quote event tape (no historical fills).

Loads the EXISTING immutable V29 report and V24/V30 sources, not the 97-month
SPY-minute scan. All quote prices, source IDs, and missing outcomes remain
explicitly observational. This is an input tape for future admitted execution
modeling, NOT historical strategy/account performance.
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
from packages.data.options_native_spy_exact_exit_source_campaign_v30 import load_exact_exit_plan
from packages.data.options_native_spy_recovered_quote_tape_v32 import (
    CONTRACT, evaluate_original_plus_exact_option_quote_tape,
)
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDraft, StrategyTrialStage, StrategyTrialDisposition,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)
from scripts.run_options_native_spy_physical_spot_exact_demand_v29 import (
    register_v29_trial, DEFAULT_MANIFEST, DEFAULT_CANDIDATE,
)

DEFAULT_PLAN = Path("data/research/spy_one_pair_exact_exit_demand_v29.json")
TRIAL_ID = "options-native.spy-v32-original-exact-quote-observation-tape"


def _register_trial(settings) -> None:
    register_v29_trial(settings)
    ledger = StrategyTrialLedger(settings.resolved_path(TRIAL_LEDGER_REL))
    existing = {r.trial_id: r for r in ledger.read()}
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
            "Join previously archived original and verified V30 exact"
            " contract 10:00 quotes for each V29 first-selected original"
            " SPY CALL/PUT pair at five predeclared review sessions",
        ),
        notes=(
            "No future prices or source availability ever affect V29 entry selection",
            "Every initial selected entry pair stays in all five review denominators",
            "Uncertain started-only or missing sources remain unobserved",
            "10:00 premium evidence never establishes 10:01 fills or portfolio P&L",
            "No new provider calls, no previously consumed 2026 master holdout",
        ),
    )
    previous = existing.get(TRIAL_ID)
    if previous is not None:
        if (previous.stage != draft.stage
                or previous.disposition != draft.disposition
                or previous.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
                or previous.feature_fingerprint != draft.feature_fingerprint
                or previous.performance_outcomes_opened
                or previous.master_protected_return_rows_read):
            raise ValueError("V32_TRIAL_LEDGER_FROZEN_SCOPE_DRIFT")
    else:
        ledger.append(draft)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, default=DEFAULT_PLAN)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=None,
                        help="New derived JSON output; never overwrite")
    args = parser.parse_args(argv)
    print("ATLAS V32 SOURCE-LINKED SPY ORIGINAL + EXACT QUOTE OBSERVATION TAPE")
    print("  mode=OFFLINE_SOURCE_ONLY provider_requests=0 broker_requests=0", flush=True)
    try:
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError("V32_OUTPUT_ALREADY_EXISTS")
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        plan = load_exact_exit_plan(args.plan)
        _register_trial(settings)
        source = audit_original_spy_pair_observations(
            settings, args.manifest, args.candidate_plan,
            evaluator=lambda entries, fetch:
                evaluate_original_plus_exact_option_quote_tape(
                    entries, fetch, settings=settings, plan=plan,
                ),
        )
        if source["contract"] != CONTRACT:
            raise ValueError("V32_OBSERVATION_CONTRACT_DRIFT")
        if source["provisionally_selected_original_weekly_pairs"] != plan["provisional_entry_pairs"]:
            raise ValueError("V32_SELECTED_PAIR_CENSUS_DRIFT")
        raw = json.dumps(source, sort_keys=True, indent=2, allow_nan=False) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(raw)
        print(
            f"  original_clocks={source['original_frozen_weekly_entries']}"
            f" provisional_pairs={source['provisionally_selected_original_weekly_pairs']}"
            f" original_abstentions={source['original_weekly_abstentions']}",
            flush=True,
        )
        for hold, item in source["by_exit_horizon"].items():
            print(
                f"  review_session={hold}"
                f" original_matched={item['original_qualified_pair_matches']}"
                f" new_exact_matched={item['newly_matched_using_exact_source']}"
                f" total_matched={item['total_qualified_quote_matches']}"
                f" unresolved={item['missing_or_unqualified_after_recovery']}"
                f" denominator={item['selected_entry_pair_denominator']}",
                flush=True,
            )
        print("  requested_right_terminal_states_encountered="
              + str(source["exact_requested_right_terminal_states_encountered"]), flush=True)
        print("  report_fingerprint=" + source["fingerprint"], flush=True)
        print("  COMPLETE: QUOTE_EVENT_TAPE_ONLY historical_fills=NONE account_pnl=NONE", flush=True)
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__ + ": " + str(exc)[:300]
            + " original_source_files_unmodified=True",
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
