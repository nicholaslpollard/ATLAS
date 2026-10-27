from __future__ import annotations

"""Offline V26 SPY weekly candidate-pair and five-session source-only diagnostic.

Reads existing original archive/receipt files. No ThetaData client construction,
provider or broker requests, historical executions or live/paper authority.
"""

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__" and not __package__:
    sys.path.insert(0, str(ROOT))

from packages.core.settings import load_settings
from packages.data.hybrid_options_at_time_one_call_v1 import PINNED_MANIFEST_FINGERPRINT
from packages.data.options_native_original_pair_diagnostic_v26 import (
    audit_original_spy_pair_observations, register_outcome_inspection_trial,
)

DEFAULT_MANIFEST = Path(
    "data/options/manifests/hybrid_exact_at_time_research_demand_v1_"
    + PINNED_MANIFEST_FINGERPRINT[:16] + ".json"
)
DEFAULT_CANDIDATE = Path(
    "data/options/manifests/thetadata_candidate_surface_source_plan_v1_"
    "acc9525a2930fe39.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidate-plan", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--output", type=Path, default=None,
                        help="Optional new immutable diagnostic JSON report path")
    args = parser.parse_args(argv)
    print("ATLAS V26 SPY SOURCE-ORIGINAL QUOTE PAIR DIAGNOSTIC", flush=True)
    print("  provider_requests=0 broker_requests=0 fills=0 protected_outcomes=0", flush=True)
    try:
        settings = load_settings(ROOT, "development")
        if args.output is not None and (args.output.exists() or args.output.is_symlink()):
            raise FileExistsError("DIAGNOSTIC_OUTPUT_ALREADY_EXISTS")
        trial = register_outcome_inspection_trial(settings)
        print("  trial_ledger=" + trial["ledger_path"], flush=True)
        print("  preregistered_trials=" + str(trial["trial_ids"]), flush=True)
        result = audit_original_spy_pair_observations(
            settings, args.manifest, args.candidate_plan,
        )
        content = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output is not None:
            # Results are diagnostic. Never replace a retained version.
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(content)
        print(
            f"  entries={result['entries_evaluated']}"
            f" entry_candidate_pairs={result['entry_pairs_screened']}"
            f" paired_review_observations={result['matched_pair_review_observations']}",
            flush=True,
        )
        print("  exit_source_states=" + str(result["review_source_states"]), flush=True)
        print("  by_year=" + str(result["by_entry_year"]), flush=True)
        print("  fee_sensitivity=" + str(result["fee_sensitivity_per_contract_per_side"]), flush=True)
        print(
            f"  fingerprint={result['fingerprint']}"
            " account_profitability=NOT_EVALUATED historical_fills=NONE",
            flush=True,
        )
        print(
            "  COMPLETE: SOURCE_DIAGNOSTIC_ONLY original_evidence_unchanged=True",
            flush=True,
        )
        if args.output is None:
            print("  No derived report written; the trial ledger is append-only.")
        return 0
    except Exception as exc:
        print(
            "  BLOCKED: " + type(exc).__name__
            + " source_originals_unchanged=True no_retry=True",
            flush=True,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
