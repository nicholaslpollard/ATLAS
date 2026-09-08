from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, found {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")


replace_once(
    "README.md",
    "**B35/A36 v2 preregistration is FROZEN PRE-OUTCOME and the finite DEVELOPMENT replay implementation is on PR #69 for exact-head acceptance.**",
    "**B35/A36 v2 preregistration and the finite DEVELOPMENT replay implementation are FROZEN PRE-OUTCOME.** Repository acceptance is exact-head gated; acceptance itself does not open B35 outcomes.",
)
replace_once(
    "README.md",
    "**PR #69 implementation acceptance itself has opened no B35 historical outcomes.**",
    "**The B35 finite-replay implementation package has opened no B35 historical outcomes.**",
)
replace_once(
    "docs/roadmap.md",
    "**Active pre-outcome contract (2026-09-08): v2 FROZEN; finite DEVELOPMENT replay implementation is on PR #69 for exact-head acceptance.**",
    "**Active pre-outcome contract (2026-09-08): v2 FROZEN; finite DEVELOPMENT replay implementation FROZEN PRE-OUTCOME.** Repository acceptance is exact-head gated and does not itself open B35 outcomes.",
)
replace_once(
    "docs/roadmap.md",
    "7. **NEXT Track-B authority transition — finite B35 DEVELOPMENT replay authorization.** The pre-outcome contract is frozen in this package. Only after exact-head acceptance may a separate hash-bound authorization permit finite DEVELOPMENT outcome replay through `2026-04-30`; it must exclude the consumed master and the new future blind, preserve all trials/counterfactuals, and still grant no PAPER/LIVE authority.",
    "7. **NEXT Track-B post-merge gate — B35 source-only workstation preflight.** After exact-head repository acceptance, run `python scripts/run_b35_development_replay.py --source-only`. This validates and records the exact frozen minute source plan plus split evidence and then stops before creating outcome authorization or opening any outcome. Review that source-only evidence in the control chat first. Only after that separate review may `--authorize-development-outcomes` explicitly open the finite frozen DEVELOPMENT replay through `2026-04-30`; the consumed master and future blind remain structurally forbidden, and no PAPER/LIVE/provider/broker authority is granted.",
)
replace_once(
    "docs/b35_a36_preoutcome_conditional_evidence.md",
    "Status: **V2 FROZEN PRE-OUTCOME; FINITE DEVELOPMENT REPLAY IMPLEMENTATION UNDER EXACT-HEAD ACCEPTANCE — NO B35 HISTORICAL OUTCOMES OPENED**",
    "Status: **V2 FROZEN PRE-OUTCOME; FINITE DEVELOPMENT REPLAY IMPLEMENTATION FROZEN — NO B35 HISTORICAL OUTCOMES OPENED**",
)
