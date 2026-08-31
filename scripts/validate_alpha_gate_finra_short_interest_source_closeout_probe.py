from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from packages.backtesting import alpha_gate_finra_short_interest_source_closeout_probe as probe
from packages.backtesting.alpha_gate_finra_short_interest_scientific_policy import (
    FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS,
    FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT,
)


def main() -> int:
    failures: list[str] = []
    source = Path(probe.__file__).read_text(encoding="utf-8")

    if probe.FINRA_SHORT_INTEREST_ACCEPTED_SOURCE_TARGET_HEAD != (
        "d312ec95752ab49a6fcbec18973faacb96d4aa89"
    ):
        failures.append("accepted target head drifted")
    if FINRA_SHORT_INTEREST_SCIENTIFIC_FINGERPRINT != (
        "0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f"
    ):
        failures.append("scientific fingerprint drifted")
    if FINRA_SHORT_INTEREST_PROTECTED_MIN_EVENT_ROWS != 300:
        failures.append("protected source event-row minimum drifted")
    if probe.FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE != (
        "rapid_short_cover_crowded_long"
    ):
        failures.append("underpowered candidate drifted")
    expected_failure = probe.FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES[
        probe.FINRA_SHORT_INTEREST_UNDERPOWERED_CANDIDATE
    ][probe.FINRA_SHORT_INTEREST_UNDERPOWERED_GATE]
    if expected_failure is not False:
        failures.append("accepted source-only failure is not preserved")
    false_gates = [
        (candidate_id, gate)
        for candidate_id, gates in probe.FINRA_SHORT_INTEREST_EXPECTED_SOURCE_GATES.items()
        for gate, passed in gates.items()
        if passed is not True
    ]
    if false_gates != [("rapid_short_cover_crowded_long", "protected_min_rows")]:
        failures.append("source-only failure set drifted")

    forbidden = (
        "packages.providers",
        ".historical_file(",
        ".stock_snapshot(",
        "development_outcomes",
        "protected_returns.parquet",
        "submit_order(",
        "paper_submit(",
    )
    for token in forbidden:
        if token in source:
            failures.append(f"closeout probe contains forbidden dependency/token: {token}")

    if failures:
        print("FINRA short-interest source-only closeout probe validation: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("FINRA short-interest source-only closeout probe validation: PASS")
    print(f"Probe contract: {probe.FINRA_SHORT_INTEREST_SOURCE_CLOSEOUT_PROBE_CONTRACT}")
    print("Frozen four-hypothesis science retained; no post-result pruning or retuning allowed.")
    print("Probe is persisted-artifact-only; provider and market-outcome reads remain forbidden.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
