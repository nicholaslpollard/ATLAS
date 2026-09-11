from pathlib import Path
import re

readme = Path("README.md")
roadmap = Path("docs/roadmap.md")
register = Path("docs/strategy_evidence_register.md")

r = readme.read_text(encoding="utf-8")
old = "- **B35 remaining gate is robustness and final research disposition, not replay.** Complete BH FDR, Deflated Sharpe, PBO/CSCV where evaluable, deterministic 10,000-draw session-bootstrap tail/drawdown analysis, losing-streak/P&L-concentration diagnostics, perturbation diagnostics, and selector comparison versus same-fold standalone/reference/cash before freezing any condition-gated v2. The future blind remains untouched."
new = "- **B35 retained-artifact robustness analyzer is IMPLEMENTED / ACCEPTANCE ACTIVE in PR #78.** It consumes only the accepted `analysis_v1` Parquet artifacts, aligns the four standalone B34 strategies plus the frozen selector on the same 2,079 complete XNYS test sessions, evaluates the exact 0/10/25/50/100-bps cost grid, deterministic 10,000-draw session bootstrap, loss streaks/concentration, selected-cell and profile BH-FDR q=.05, Deflated Sharpe, and frozen 16-partition CSCV/PBO. Cash is the same-unit abstention benchmark; the accepted A34 account replay is retained only as contextual evidence because its strategy set/account construction/date scope are not directly comparable. Entry-delay/setup-threshold/opening-range/premarket perturbations are explicitly `REQUIRES_TARGETED_MINUTE_REPLAY`; compact outputs are not used to approximate them. After accepted merge, run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_robustness_analysis.py`. No strategy/selector promotion or PAPER/LIVE authority is granted; the future blind remains untouched."
assert old in r
r = r.replace(old, new, 1)
readme.write_text(r, encoding="utf-8")

d = roadmap.read_text(encoding="utf-8")
pattern = re.compile(
    r"\*\*B35 condition/selector analyzer status \(2026-09-11\): IMPLEMENTED / ACCEPTANCE PENDING in PR #76\.\*\*.*?Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence\.md`\.",
    re.S,
)
replacement = """**B35 condition/selector analyzer status (2026-09-11): COMPLETE / PROFILE-ONLY.** PR #76 merged as `cceccdc23569f6d48395a52322a83f59ba555b23`; the workstation analysis completed with fingerprint `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f`. It normalized all 20,171,286 accepted compact opportunities and constructed 33 complete-XNYS 504/63/63/1 walk-forward folds. The frozen selector evaluated 17,030,985 test opportunities, selected 3,747 (3,188 comparable), and abstained on 99.978%. Selected mean return across the exact cost grid was +0.2984% / +0.1984% / +0.0485% / -0.2015% / -0.7014% at 0/10/25/50/100 bps. Strategy-level interpretation and current dispositions live in `docs/strategy_evidence_register.md`; no strategy or selector was promoted.

**B35 retained-artifact robustness package is IMPLEMENTED / ACCEPTANCE ACTIVE in PR #78.** It validates the complete accepted analysis/receipt chain, creates aligned complete-session research profiles for the four B34 strategies and frozen selector, and computes the exact retained-artifact gates: cost robustness, deterministic 10,000-draw session-bootstrap downside/drawdown uncertainty, loss streaks, session contribution concentration, selected-cell/profile BH-FDR q=.05, Deflated Sharpe, and 16-partition CSCV/PBO. Cash is a same-unit benchmark. The accepted A34 account replay is contextual only because its daily strategy set, portfolio construction, date scope and costs are not statistically identical to B35. The frozen minute-path perturbations for entry delay, gap threshold, opening-range duration, premarket rel-volume threshold, and consolidation range cannot be reconstructed exactly from fired-opportunity compact artifacts and therefore fail closed as `REQUIRES_TARGETED_MINUTE_REPLAY`; no approximation is allowed. After accepted merge run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_robustness_analysis.py`. This package opens no new minute outcomes, consumed master or future blind and grants no promotion/PAPER/LIVE/provider/broker authority.

Next Track-B sequence: (1) accept/merge PR #78 only after exact-head Windows+Ubuntu regression is green; (2) run the retained-artifact robustness command once; (3) review its BH-FDR, Deflated-Sharpe, PBO/CSCV, bootstrap-tail, loss-streak/concentration and cost results; (4) implement one exact targeted minute-path perturbation replay that evaluates the remaining preregistered perturbations together in one pass, without changing the canonical B35 v1 result; (5) record the final B35 research disposition without promotion; (6) freeze any justified condition-gated/calibrated successors plus the eight-new-family/confluence contract under new fingerprints; (7) later evaluate the genuinely new future blind only after required accrual and without refitting on it; and (8) never reuse the consumed master interval. Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`."""
d, count = pattern.subn(lambda _m: replacement, d, count=1)
assert count == 1

pattern = re.compile(
    r"2\. \*\*NEXT:\*\* produce the preregistered B35 strategy x condition evidence and selector result\..*?research family\.",
    re.S,
)
replacement = """2. **COMPLETE (2026-09-11):** produce the preregistered B35 strategy x condition evidence and selector profile; no strategy/selector promotion resulted.
3. **CURRENT:** complete B35 robustness. Run the retained-artifact PR #78 analyzer first, then one exact targeted minute-path perturbation package for the preregistered perturbations that cannot be reconstructed from compact outcomes. Record final B35 research disposition without promotion.
4. Freeze the exact **eight-new-family** successor contract, justified B35 v2 candidates, and confluence feature schema; bind the six daily plus four B34 families as retained baseline lineage.
5. Implement shared PIT indicators/pivots and the eight independent new evaluators; run source-only, semantic and exact-equivalence tests.
6. Run expanded DEVELOPMENT evidence with standalone strategies first.
7. Evaluate hard confirmation and confluence as separate hypotheses, including redundancy, conflict, costs and sample-size effects.
8. Perform one bounded diagnostic/calibration cycle; preregister up to three justified v2 candidates per family and evaluate them only on untouched evidence.
9. Promote nothing automatically. Survivors become candidates for the next prospective/PAPER evidence gate; failures stay in the ledger and guide the next research family."""
d, count = pattern.subn(lambda _m: replacement, d, count=1)
assert count == 1

d = d.replace(
    "PLAIN-ENGLISH END → UPDATE BOTH LIVING DOCS IN THE SAME COMMIT → MERGE →",
    "PLAIN-ENGLISH END → UPDATE ALL APPLICABLE LIVING DOCS IN THE SAME PACKAGE → MERGE →",
    1,
)
d = d.replace(
    "Every repository-changing package must update both living documents before merge.",
    "Every repository-changing package must update README and roadmap before merge; any package that changes or interprets strategy evidence must also update the Strategy Evidence Register.",
    1,
)
d = d.replace("If either living document is\nstale, the package is not complete.", "If any applicable living document is\nstale, the package is not complete.", 1)
roadmap.write_text(d, encoding="utf-8")

s = register.read_text(encoding="utf-8")
needle = """## 6. Next B35 scientific work

Before freezing any condition-gated v2 rule, complete the remaining preregistered robustness package over the accepted B35 analysis artifacts:
"""
replacement = """## 6. Next B35 scientific work

**Implementation status (2026-09-11): retained-artifact robustness analyzer implemented in PR #78; repository acceptance and workstation result pending.** The analyzer validates the accepted analysis receipts and computes, on the same 2,079 complete XNYS test sessions, exact cost-grid profiles, deterministic 10,000-draw session bootstrap tail/drawdown uncertainty, loss-streak/concentration diagnostics, selected-cell/profile BH-FDR q=.05, Deflated Sharpe, and frozen 16-partition CSCV/PBO for the four standalone strategies plus frozen selector. The one-sided bootstrap p-value construction used for the post-result FDR diagnostic is itself descriptive and does not create promotion authority. Cash is the same-unit benchmark; the accepted A34 account replay is contextual only because it is not the same statistical/account unit.

The compact fired-opportunity artifacts cannot exactly reconstruct counterfactual entry delays or changed setup definitions. PR #78 therefore marks entry delay, gap threshold, opening-range duration, premarket rel-volume threshold, and premarket consolidation-range perturbations as `REQUIRES_TARGETED_MINUTE_REPLAY` and uses no approximation. After PR #78 merges, run `.\\.venv\\Scripts\\python.exe scripts\\run_b35_robustness_analysis.py`; then implement the remaining perturbations together in one bounded exact minute pass rather than repeating the canonical replay separately per variant.

Before freezing any condition-gated v2 rule, complete the remaining preregistered robustness package over the accepted B35 analysis artifacts:
"""
assert needle in s
s = s.replace(needle, replacement, 1)
register.write_text(s, encoding="utf-8")
