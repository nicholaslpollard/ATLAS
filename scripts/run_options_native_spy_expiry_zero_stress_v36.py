from __future__ import annotations

"""V36 SPY original-quote lifecycle stress: no actual fills or expiry receipts."""

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.options_native_original_pair_diagnostic_v26 import TRIAL_LEDGER_REL
from packages.performance.ledger import StrategyTrialLedger
from packages.schemas.strategy_lab import (
    StrategyTrialDraft, StrategyTrialStage, StrategyTrialDisposition,
)
from packages.simulation.options_native_spy_expiry_zero_stress_v36 import (
    CONTRACT, run_expiry_zero_stress,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)

MAX_TAPE_BYTES = 16 * 1024 * 1024
TRIAL_ID = "options-native.spy-v36-expiry-zero-quote-cash-retrospective"


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
            "Retrospective V34 follow-up: test remaining cash allocation and quote"
            " coverage with unpriced options held until original expiration and"
            " zero proceeds assumed at expiry, without using historical outcomes"
            " to choose entry or exit dates",
        ),
        notes=(
            "Source V32 quote outcomes already opened; no novel qualification or alpha promotion",
            "Two fixed capacity policies: V34 two-slot/10% and pilot one-slot/5% one-pair geometry",
            "5 fixed hold sessions x fees 0.65/1.30 x adverse per-leg slippage 0/0.05",
            "Observed qualified original review quotes define illustrative sale prices, not fills",
            "Missing review quotes held to contractual expiration, zero final proceeds is pessimistic scenario, not verified settlement",
            "All selected provisional entries in denominator, no 2026 market price or protected outcome read",
        ),
    )
    prior_draft = prior.get(TRIAL_ID)
    if prior_draft is not None:
        if (prior_draft.stage != draft.stage
                or prior_draft.disposition != draft.disposition
                or prior_draft.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
                or prior_draft.feature_fingerprint != draft.feature_fingerprint
                or prior_draft.performance_outcomes_opened
                or prior_draft.master_protected_return_rows_read):
            raise ValueError("V36_TRIAL_FROZEN_SCOPE_DRIFT")
    else:
        ledger.append(draft)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tape", type=Path, required=True)
    parser.add_argument("--expect-fingerprint", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print("ATLAS V36 SPY FULL-HISTORY EXPIRY-ZERO QUOTE CASH STRESS")
    print("  source=ORIGINAL_HISTORICAL_QUOTES outcome=HYPOTHETICAL_EXPIRY_ZERO"
          " provider_requests=0 broker_requests=0", flush=True)
    try:
        if (re.fullmatch(r"[0-9a-f]{64}", args.expect_fingerprint) is None
                or args.tape.is_symlink() or not args.tape.is_file()
                or not 0 < args.tape.stat().st_size <= MAX_TAPE_BYTES
                or args.output.exists() or args.output.is_symlink()):
            raise ValueError("V36_INPUT_OUTPUT_PREFLIGHT_REJECTED")
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("options")
        _register_trial(settings)
        tape = json.loads(args.tape.read_text(encoding="utf-8"))
        report = run_expiry_zero_stress(tape, args.expect_fingerprint)
        if report["contract"] != CONTRACT or report["scenario_count"] != 40:
            raise ValueError("V36_FROZEN_SCENARIO_SET_DRIFT")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
        for row in report["scenarios"]:
            account = row["hypothetical_expiry_zero_account"]
            cnt = account["counts"]
            print(
                f"  policy={row['capacity_policy']} hold={row['hold_xnys_sessions']}"
                f" fee={row['fee_per_contract_per_side']}"
                f" slip={row['adverse_slippage_per_share_per_leg']}"
                f" entered={cnt.get('hypothetical_entries', 0)}"
                f" review_closed={cnt.get('hypothetical_quote_closures', 0)}"
                f" zero_expiry_assumed={cnt.get('unobserved_expiry_assumed_zero_credit', 0)}"
                f" modeled_terminal_cash={account['terminal_hypothetical_cash_after_zero_expiry_assumptions']}"
                f" modeled_return_pct={account['assumption_dependent_net_return_pct']}",
                flush=True,
            )
        print("  scenario_count=40 report_fingerprint=" + report["fingerprint"])
        print("  COMPLETE: QUOTE_REFERENCE_AND_EXPLICIT_EXPIRY_ZERO_STRESS_ONLY"
              " true_order_fills=NONE true_strategy_pnl=NONE", flush=True)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"  BLOCKED: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
