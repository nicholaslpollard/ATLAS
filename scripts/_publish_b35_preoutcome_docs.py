from __future__ import annotations

import json
import re
from pathlib import Path

from packages.strategies.b35_conditional_evidence_contract import (
    B35_PREOUTCOME_FINGERPRINT,
    frozen_contract_manifest,
)


def sub_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise SystemExit(f"{label}: expected one replacement, got {count}")
    return updated


def main() -> int:
    manifest = frozen_contract_manifest()
    evidence_path = Path("docs/evidence/b35_a36_preoutcome_contract.json")
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    readme_path = Path("README.md")
    readme = readme_path.read_text(encoding="utf-8")
    b35_bullet = (
        "- **B35/A36 conditional-evidence design is FROZEN PRE-OUTCOME.** Contract "
        "`atlas-b35-a36-conditional-evidence-v1-pre-outcome` is bound to the accepted B34 pack and "
        f"has fingerprint `{B35_PREOUTCOME_FINGERPRINT}`. DEVELOPMENT scoring/selector fitting stops "
        "at `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval cannot provide fitting "
        "labels or scored outcomes; a new future blind starts on the first XNYS session on/after "
        "`2026-09-08` and requires at least 63 complete sessions before one-time unblinding. The design "
        "freezes 504/63-session rolling walk-forward folds, explicit intraday exits, a 0/10/25/50/100 "
        "bps all-in cost grid with 50 bps selector scoring, PIT-safe condition buckets, session-cluster "
        "bootstrap selection, multiplicity diagnostics, robustness tests, and the existing A34 risk "
        "envelope. It opens no strategy outcomes and grants no minute-replay, promotion, PAPER, LIVE, "
        "provider-call, or broker-read/write authority."
    )
    readme = sub_once(
        readme,
        r"(?=^- \*\*B34 intraday source readiness and the opening/premarket pack are CLOSED / ACCEPTED\.\*\*)",
        b35_bullet + "\n",
        "README B35 insertion",
    )
    readme_path.write_text(readme, encoding="utf-8")

    roadmap_path = Path("docs/roadmap.md")
    roadmap = roadmap_path.read_text(encoding="utf-8")
    b35_section = f"""### B35/A36 — Conditional Evidence, Selector, Outcomes, and Performance UI

Build the walk-forward condition profiles and frozen selector challenger; compare it
to simple family baselines. Add strategy management, calibration, degradation,
regime, slippage, portfolio contribution, and trials-ledger views. Learning may
recommend but never self-promote.

**Pre-outcome design frozen (2026-09-08).** Contract
`atlas-b35-a36-conditional-evidence-v1-pre-outcome` has fingerprint
`{B35_PREOUTCOME_FINGERPRINT}` and binds exactly the accepted B34 opening/premarket
pack. It reads no outcomes and grants no minute-replay, promotion, PAPER, LIVE,
provider-call, or broker-read/write authority. Scored DEVELOPMENT and selector fit
end `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval is forbidden
as fitting/scored evidence. Rows after DEVELOPMENT may only be counted fixed-feature
warm-up for a genuinely future signal, never labels or selector fit. The new blind
begins on the first XNYS session on/after `2026-09-08`, accrues at least 63 complete
sessions before one-time unblinding, cannot refit on blind outcomes, and can never be
recycled into DEVELOPMENT after a bad result.

The frozen evaluation uses 504-session rolling training, 63-session tests, 63-session
steps and a one-session embargo; strategy thresholds never refit. It preregisters
same-session entry/stop/2R/time-exit mechanics, adverse same-bar collision handling,
a 0/10/25/50/100-bps all-in round-trip cost grid with 50 bps selector scoring and
100 bps stress, prior-close/PIT condition clocks, explicit price/liquidity/volatility/
gap/premarket/opening-range/time buckets, session-cluster bootstrap lower-confidence
selection with cash abstention, trials/multiplicity controls, Deflated-Sharpe/PBO
diagnostics, fixed robustness perturbations, and the accepted A34 long-only portfolio
risk envelope. Short signals remain research-profile only until borrow/locate/recall
economics exist. Full mechanics and literature anchors are in
`docs/b35_a36_preoutcome_conditional_evidence.md`.

The next B35 authority transition, only after exact-head acceptance of this frozen
contract, is a separate hash-bound finite DEVELOPMENT replay authorization. That
later authorization must still exclude the consumed master and future blind from
scored DEVELOPMENT outcomes and must not create a giant permanent minute-feature
lake merely to run the replay.
"""
    roadmap = sub_once(
        roadmap,
        r"### B35/A36 — Conditional Evidence, Selector, Outcomes, and Performance UI\n\nBuild the walk-forward condition profiles and frozen selector challenger; compare it\nto simple family baselines\. Add strategy management, calibration, degradation,\nregime, slippage, portfolio contribution, and trials-ledger views\. Learning may\nrecommend but never self-promote\.\n",
        b35_section,
        "roadmap B35 section",
    )
    roadmap = sub_once(
        roadmap,
        r"7\. \*\*NEXT Track B — freeze the B35/A36 pre-outcome conditional-evidence contract\.\*\*.*?(?=\n8\. Keep focused tests)",
        "7. **NEXT Track-B authority transition — finite B35 DEVELOPMENT replay authorization.** The pre-outcome contract is frozen in this package. Only after exact-head acceptance may a separate hash-bound authorization permit finite DEVELOPMENT outcome replay through `2026-04-30`; it must exclude the consumed master and the new future blind, preserve all trials/counterfactuals, and still grant no PAPER/LIVE authority.\n",
        "roadmap Track B action",
    )
    roadmap_path.write_text(roadmap, encoding="utf-8")

    Path(".github/workflows/_b35_preoutcome_publish.yml").unlink(missing_ok=True)
    Path("scripts/_publish_b35_preoutcome_docs.py").unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
