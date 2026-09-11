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

s = register.read_text(encoding="utf-8")
old_remaining = """- Remaining preregistered robustness/promotion gates are not complete: BH FDR, Deflated Sharpe, PBO/CSCV where evaluable, 10,000-draw session bootstrap tail/drawdown work, losing-streak/P&L-concentration diagnostics, perturbation diagnostics, and portfolio/reference comparison."""
new_remaining = """- Retained-artifact robustness is now complete under fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`: 13 selected fold/cell hypotheses produced 0 BH-FDR q=.05 rejections; all five declared 50-bps profiles have negative mean session return and Deflated-Sharpe probability 0.0. Exact minute-path perturbations remain the final preregistered B35 robustness component and are implemented in PR #79 without selector refit or v1 rewrite."""
assert old_remaining in s
s = s.replace(old_remaining, new_remaining, 1)

marker = "## 4. Current B35 strategy dispositions"
robustness_section = """### 3.3 Retained-artifact robustness result

- Robustness fingerprint: `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`.
- Scope: the same 2,079 complete XNYS walk-forward test sessions; session is the primary dependence cluster.
- Selected-cell multiplicity: 13 declared fold x strategy x fallback-level x condition-cell hypotheses; **0 BH-FDR q=.05 rejections**. The smallest raw one-sided p-values were not sufficient after multiplicity correction.
- Profile multiplicity: all five declared 50-bps profiles have negative mean session return; profile one-sided bootstrap p-values and BH-adjusted p-values are 1.0.
- Deflated Sharpe: probability `0.0` for all five declared profiles. Annualized 50-bps Sharpes are approximately gap `-25.08`, ORB `-27.25`, premarket-relvol `-16.84`, HVD `-0.57`, selector `-0.24`.
- Frozen selector cost curve: annualized Sharpe `+0.652` / `+0.475` / `+0.208` / `-0.238` / `-1.120` and mean session return `+0.0834%` / `+0.0607%` / `+0.0265%` / `-0.0303%` / `-0.1441%` at 0/10/25/50/100 bps. The low-cost structure is research evidence only; the frozen 50-bps hurdle remains binding.
- Selector 10,000-draw bootstrap at 50 bps: probability mean session return >0 = `24.21%`; median bootstrapped mean session return about `-0.0310%`; median terminal research-profile compound return about `-65.56%`; median max drawdown about `-79.75%`. The 95th-percentile bootstrap can be positive, which confirms uncertainty but not a qualifying edge.
- HVD remains extremely sparse: 46 active 50-bps sessions in the aligned profile; bootstrap probability of positive mean session return is only `4.75%`, and positive P&L is highly concentrated (top 10 positive sessions account for about 99.63% of positive-session contribution).
- PBO/CSCV: `7.77e-05` (~0.01%) across the five declared profiles. This indicates little evidence that the in-sample winner ranking is a classic overfit selection artifact, but it does **not** establish profitability; consistently weak candidates can also have low PBO.
- A34 stable long-only account replay remains context only, not same-unit statistical comparison.
- Authority unchanged: consumed-master/future-blind reads 0; provider/broker calls/writes 0; PAPER/LIVE false; strategy/selector promotion false.

**Interpretation:** B35 has not established promotable alpha. The selector materially improves the unrestricted strategies and retains a low-cost positive signal, but the 50-bps economics, FDR and Deflated-Sharpe gates remain negative. That supports continued bounded specialist/condition research, not promotion or retroactive weakening of costs.

**Final robustness component:** PR #79 implements the five frozen minute-path perturbation families in one DEVELOPMENT-only pass. There are 27 strategy/variant profiles because entry delay is applied to all four strategies and consolidation-range perturbation applies independently to premarket-relvol and HVD. Each axis changes alone. All baseline values must reproduce the canonical v1 fired/comparable/noncomparable counts in every group before a perturbed group can complete. Better variants are diagnostic successor hypotheses only; selector refit and canonical-v1 rewrite are forbidden.

"""
assert marker in s
s = s.replace(marker, robustness_section + marker, 1)

old_status = """**Implementation status (2026-09-11): retained-artifact robustness analyzer implemented in PR #78; repository acceptance and workstation result pending.** The analyzer validates the accepted analysis receipts and computes, on the same 2,079 complete XNYS test sessions, exact cost-grid profiles, deterministic 10,000-draw session bootstrap tail/drawdown uncertainty, loss-streak/concentration diagnostics, selected-cell/profile BH-FDR q=.05, Deflated Sharpe, and frozen 16-partition CSCV/PBO for the four standalone strategies plus frozen selector. The one-sided bootstrap p-value construction used for the post-result FDR diagnostic is itself descriptive and does not create promotion authority. Cash is the same-unit benchmark; the accepted A34 account replay is contextual only because it is not the same statistical/account unit.

The compact fired-opportunity artifacts cannot exactly reconstruct counterfactual entry delays or changed setup definitions. PR #78 therefore marks entry delay, gap threshold, opening-range duration, premarket rel-volume threshold, and premarket consolidation-range perturbations as `REQUIRES_TARGETED_MINUTE_REPLAY` and uses no approximation. After PR #78 merges, run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_robustness_analysis.py`; then implement the remaining perturbations together in one bounded exact minute pass rather than repeating the canonical replay separately per variant."""
new_status = """**Implementation status (2026-09-11): retained-artifact robustness COMPLETE; exact targeted perturbation implementation ACTIVE in PR #79.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; the workstation run completed under robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107`. Its 50-bps multiplicity/Deflated-Sharpe result is negative and grants no promotion. The exact minute-path perturbations could not be reconstructed from compact outputs, so PR #79 implements them together in one bounded pass rather than approximating them or rerunning the canonical evidence separately per variant.

PR #79 binds the same 59,768-unit DEVELOPMENT source, split evidence and immutable DEVELOPMENT authorization plus the accepted robustness fingerprint. It requires a new explicit hash-bound targeted authorization, validates every canonical B35 group output/receipt before use, publishes only restartable diagnostic group summaries/receipts, and fails each group closed unless all baseline perturbation values reproduce canonical fired/comparable/noncomparable counts. The pass changes one axis at a time, does not refit the selector, does not rewrite canonical B35 v1, and grants no strategy/selector/PAPER/LIVE authority."""
assert old_status in s
s = s.replace(old_status, new_status, 1)
register.write_text(s, encoding="utf-8")
