from __future__ import annotations

"""V37 offline 411-clock SPY feature staging: no IV guesses or strategy P&L."""

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_original_pair_diagnostic_v26 import TRIAL_LEDGER_REL
from packages.data.options_native_spy_full_period_retrospective_dividend_variance_v1 import (
    build_full_period_retrospective_grid,
)
from packages.data.options_native_spy_pretrade_feature_bridge_v37 import (
    CONTRACT, PINNED_TAPE_FINGERPRINT, bridge_pretrade_inputs,
)
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDraft, StrategyTrialStage, StrategyTrialDisposition,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)

MAX_INPUT_BYTES = 32 * 1024 * 1024
TRIAL_ID = "options-native.spy-v37-retrospective-feature-source-stage"


def _register_trial(settings) -> None:
    ledger = StrategyTrialLedger(settings.resolved_path(TRIAL_LEDGER_REL))
    prior = {item.trial_id: item for item in ledger.read()}
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
            "Reconcile the frozen V29 original SPY 361 pair entry cohort with"
            " 411 retrospective 20-return volatility windows before qualifying"
            " historical IV, PIT source publication, executable entry or outcomes",
        ),
        notes=(
            "No strategy profitability, retrospective performance optimization or historical fill",
            "Original SPY V32 quote outcomes were previously opened; inputs reused",
            "Four pinned original reports produce retrospective volatility, not PIT",
            "Never substitute ask premium for American model IV, or zero SOFR and dividends",
            "Retain 50 original abstentions and 4 known raw prior-close gaps",
            "No new provider, broker or 2026 protected outcome calls",
        ),
    )
    existing = prior.get(TRIAL_ID)
    if existing is None:
        ledger.append(draft)
    elif (existing.stage != draft.stage
          or existing.disposition != draft.disposition
          or existing.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
          or existing.feature_fingerprint != draft.feature_fingerprint
          or existing.performance_outcomes_opened
          or existing.master_protected_return_rows_read):
        raise ValueError("V37_TRIAL_REGISTRATION_SCOPE_DRIFT")


def _read_bounded(path: Path) -> dict:
    if (path.is_symlink() or not path.is_file()
            or not 0 < path.stat().st_size < MAX_INPUT_BYTES):
        raise ValueError("V37_SOURCE_INPUT_NOT_BOUND_OR_MISSING")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tape", type=Path, required=True)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--expect-fingerprint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V37 SPY ORIGINAL SOURCE-BOUND PRETRADE FEATURE BRIDGE")
    print("  mode=PRETRADE_RESEARCH_EVIDENCE_ONLY provider_requests=0"
          " broker_requests=0 historical_simulations=0", flush=True)
    try:
        if (args.expect_fingerprint != PINNED_TAPE_FINGERPRINT
                or args.output.exists() or args.output.is_symlink()):
            raise ValueError("V37_PINNED_SOURCE_OR_OUTPUT_PREFLIGHT_FAILED")
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("research_evidence")
        _register_trial(settings)
        tape = _read_bounded(args.tape)
        plan = _read_bounded(args.plan)
        grid = build_full_period_retrospective_grid(settings)
        report = bridge_pretrade_inputs(tape, plan, grid)
        if report["contract"] != CONTRACT:
            raise ValueError("V37_FEATURE_PACKET_CONTRACT_DRIFT")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        print(
            f"  original_weekly_clocks={report['original_weekly_decision_clocks']}"
            f" original_selected_pairs={report['source_selected_pairs']}"
            f" original_abstentions={report['original_abstentions']}"
        )
        print(
            f"  retrospective_20return_windows="
            f"{report['selected_retrospective_window_present']}/361"
            f" missing={report['selected_retrospective_window_missing']}"
        )
        print("  REAL_PIT_FORECAST=NOT_READY"
              " AMERICAN_101STEP_IV=NOT_READY"
              " PRIOR_OI=NOT_READY"
              " 1001_EXECUTABLE_FILLED_PAIRS=NOT_READY")
        print("  fingerprint=" + report["fingerprint"])
        print("  COMPLETE: IMMUTABLE_SOURCE_BRIDGE_ONLY actual_signal=NONE"
              " actual_simulation=NONE")
        print(f"  saved={args.output}")
        return 0
    except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
        print(f"  BLOCKED: {type(exc).__name__}: {str(exc)[:320]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
