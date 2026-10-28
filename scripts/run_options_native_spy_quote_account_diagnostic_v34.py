from __future__ import annotations

"""Offline V34 historical SPY quote cash scenarios: indicative, NOT fills or alpha."""

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
from packages.simulation.options_native_spy_quote_account_diagnostic_v34 import (
    FEES, SLIPPAGES, HOLDS, run_quote_account_diagnostic,
)
from packages.strategies.options_native_pilot_v1_contract import (
    PILOT_ID, SPECIFICATION_FINGERPRINT, DATA_FINGERPRINT,
)

TRIAL_ID = "options-native.spy-v34-10am-original-quote-cash-diagnostic"
MAX_TAPE_SIZE = 16 * 1024 * 1024


def _register_trial(settings) -> None:
    """Register explicit fixed scenarios before opening historical quote outcomes."""
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
            "Post-observation diagnostic: selected SPY pairs all-enter hypothetical "
            "10:00 ask/bid cash outcomes at one to five frozen sessions",
        ),
        notes=(
            "V32 outcomes were already opened; V34 is RETROSPECTIVE DEVELOPMENT, NOT fresh validation",
            "Fixed fee grid 0.65 and 1.30 USD per contract per side",
            "Fixed two-leg slippage grid 0 and 0.05 USD per share per leg",
            "Initial cash 100000 USD, 10 percent available-cash per pair, two open pairs, ten-pair cap",
            "Unknown quote exits stay open with unknown equity; never discard outcome-missing cases",
            "No 10:01 fill, historical true return, actual entry volatility signal, or broker/provider calls",
        ),
    )
    previous = prior.get(TRIAL_ID)
    if previous is not None:
        if (previous.stage != draft.stage
                or previous.disposition != draft.disposition
                or previous.strategy_policy_fingerprint != draft.strategy_policy_fingerprint
                or previous.feature_fingerprint != draft.feature_fingerprint
                or previous.performance_outcomes_opened
                or previous.master_protected_return_rows_read):
            raise ValueError("V34_TRIAL_LEDGER_FROZEN_SCOPE_DRIFT")
    else:
        ledger.append(draft)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tape", required=True, type=Path,
                        help="Existing immutable V32 source-linked quote tape")
    parser.add_argument("--expect-fingerprint", required=True,
                        help="Full SHA-256 V32 report fingerprint printed by V32")
    parser.add_argument("--output", required=True, type=Path,
                        help="New exclusive-create report file")
    args = parser.parse_args(argv)
    print("ATLAS V34 HISTORICAL SPY QUOTE-CASH SCENARIO FAST LANE")
    print("  mode=HISTORICAL_SOURCE_QUOTES_HYPOTHETICAL_EXECUTION_ONLY "
          "provider_requests=0 broker_requests=0", flush=True)
    try:
        if (not re.fullmatch(r"[0-9a-f]{64}", args.expect_fingerprint)
                or not args.tape.is_file() or args.tape.is_symlink()
                or not 0 < args.tape.stat().st_size <= MAX_TAPE_SIZE
                or args.output.exists() or args.output.is_symlink()):
            raise ValueError("V34_TAPE_OR_OUTPUT_PREFLIGHT_REJECTED")
        settings = load_settings(ROOT, "development")
        settings.assert_external_storage_binding("research")
        _register_trial(settings)
        tape = json.loads(args.tape.read_text(encoding="utf-8"))
        report = run_quote_account_diagnostic(tape, args.expect_fingerprint)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
            stream.write("\n")
        for row in report["scenarios"]:
            conditional = row["conditional_quote_economics"]
            cash = row["chronological_quote_cash_scenario"]
            counts = cash["counts"]
            print(
                f"  hold={row['hold_sessions']} fee={row['fee_per_contract_per_side']}"
                f" slippage={row['slippage_per_share_per_leg']}"
                f" observed={conditional['matched_conditional_count']}/361"
                f" mean_quote_pct={conditional['conditional_mean_quote_return_pct']}"
                f" hypo_closed={counts.get('hypothetical_closed_pairs', 0)}"
                f" missing_open={cash['ending_open_pairs_without_trusted_terminal_mark']}"
                f" ending_equity={cash['ending_equity']}",
                flush=True,
            )
        print("  scenario_count=" + str(report["scenario_count"])
              + " report_fingerprint=" + report["fingerprint"], flush=True)
        print("  COMPLETE: REAL_HISTORICAL_QUOTES_HYPOTHETICAL_CASH_ONLY"
              " actual_fills=NONE strategy_pnl=NOT_VALIDATED", flush=True)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"  BLOCKED: {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
