from pathlib import Path

readme = Path("README.md")
roadmap = Path("docs/roadmap.md")
register = Path("docs/strategy_evidence_register.md")

r = readme.read_text(encoding="utf-8")
old = """- **B35 retained-artifact robustness analyzer is IMPLEMENTED / ACCEPTANCE ACTIVE in PR #78.** It consumes only the accepted `analysis_v1` Parquet artifacts, aligns the four standalone B34 strategies plus the frozen selector on the same 2,079 complete XNYS test sessions, evaluates the exact 0/10/25/50/100-bps cost grid, deterministic 10,000-draw session bootstrap, loss streaks/concentration, selected-cell and profile BH-FDR q=.05, Deflated Sharpe, and frozen 16-partition CSCV/PBO. Cash is the same-unit abstention benchmark; the accepted A34 account replay is retained only as contextual evidence because its strategy set/account construction/date scope are not directly comparable. Entry-delay/setup-threshold/opening-range/premarket perturbations are explicitly `REQUIRES_TARGETED_MINUTE_REPLAY`; compact outputs are not used to approximate them. After accepted merge, run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_robustness_analysis.py`. No strategy/selector promotion or PAPER/LIVE authority is granted; the future blind remains untouched."""
new = """- **B35 retained-artifact robustness is COMPLETE / NO PROMOTION.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; workstation robustness fingerprint = `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` across 2,079 complete XNYS test sessions. At 50 bps every declared standalone/selector profile has negative mean session return and Deflated-Sharpe probability `0.0`; 13 selected fold/cell hypotheses produced **0 BH-FDR q=.05 rejections**. The frozen selector remains positive at 0/10/25 bps but is negative at 50/100 bps; its 10,000-draw bootstrap assigns 24.21% probability to positive mean 50-bps session return. PBO/CSCV is 0.01%, retained only as a narrow ranking-stability diagnostic and not profitability evidence. No strategy/selector promotion occurred; consumed-master/future/provider/broker reads remain zero and PAPER/LIVE authority remains false.
- **B35 exact targeted minute perturbations are IMPLEMENTED / ACCEPTANCE ACTIVE in PR #79.** One DEVELOPMENT-only pass freezes 27 one-axis-at-a-time strategy/variant profiles covering entry delay 0/1/2, gap threshold x0.9/1.0/1.1, ORB 14/15/16 minutes, premarket rel-vol threshold x0.9/1.0/1.1, and premarket consolidation-range x0.9/1.0/1.1 for premarket-relvol/HVD. Every group must reproduce canonical v1 fired/comparable/noncomparable counts for all baseline variants before perturbed evidence can publish. Outputs are diagnostic, hash-receipted and restartable; canonical B35 v1 is immutable, selector refit is forbidden, and no promotion/PAPER/LIVE/master/future/provider/broker authority is granted."""
assert old in r
readme.write_text(r.replace(old, new, 1), encoding="utf-8")

d = roadmap.read_text(encoding="utf-8")
d = d.replace(
    "**B35 DEVELOPMENT replay status (2026-09-11): CLOSED / ACCEPTED; strategy x condition / selector analysis NEXT.**",
    "**B35 DEVELOPMENT replay status (2026-09-11): CLOSED / ACCEPTED; condition/selector and retained-artifact robustness COMPLETE / NO PROMOTION; exact targeted perturbations CURRENT in PR #79.**",
    1,
)
d = d.replace(
    "**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY CLOSED / ACCEPTED; B35 CONDITION/SELECTOR ANALYZER ACCEPTANCE ACTIVE.**",
    "**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY, CONDITION/SELECTOR, AND RETAINED-ARTIFACT ROBUSTNESS COMPLETE; EXACT TARGETED PERTURBATION PR #79 ACCEPTANCE ACTIVE.**",
    1,
)
old_step = """3. **CURRENT:** complete B35 robustness. Run the retained-artifact PR #78 analyzer first, then one exact targeted minute-path perturbation package for the preregistered perturbations that cannot be reconstructed from compact outcomes. Record final B35 research disposition without promotion."""
new_step = """3. **CURRENT:** retained-artifact robustness is complete with fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`, 0/13 selected-cell BH-FDR rejections, Deflated-Sharpe probability 0 for all five profiles, and no promotion. Accept PR #79, then run its one-pass exact DEVELOPMENT minute perturbations; review the 27 diagnostic variant profiles and record final B35 research disposition without rewriting v1 or refitting the selector."""
assert old_step in d
d = d.replace(old_step, new_step, 1)
insert_marker = """PIT market regime remains `UNAVAILABLE` wherever this minute replay does not have an exact accepted prior-session regime join; it is never guessed."""
insert = """**Retained-artifact robustness result (2026-09-11): COMPLETE / NO PROMOTION.** Robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` covers the same 2,079 complete XNYS walk-forward test sessions. Every declared 50-bps profile has negative mean session return; all five Deflated-Sharpe probabilities are `0.0`; 13 selected fold/cell hypotheses yield 0 BH-FDR q=.05 rejections. The frozen selector remains positive at 0/10/25 bps but turns negative at 50/100 bps and its bootstrap probability of positive mean 50-bps session return is 24.21%. PBO/CSCV = 0.01% is interpreted only as low rank-overfit tendency among the five declared profiles, not evidence of positive alpha. Exact entry/setup perturbations remained pending because compact outputs cannot reconstruct counterfactual minute paths; PR #79 implements those five families together in one hash-receipted, restartable DEVELOPMENT-only pass with per-group canonical baseline-equivalence gates and no selector refit.\n\n""" + insert_marker
assert insert_marker in d
d = d.replace(insert_marker, insert, 1)
roadmap.write_text(d, encoding="utf-8")

s = register.read_text(encoding="utf-8")n
