# Phase 24 — Strategy Evidence Challenger & Support Replacement

**Status: ACCEPTANCE EVIDENCE COMPLETE / NO SUPPORT REPLACEMENT / MERGE PENDING**

Upstream authority: Phase23 accepted merge `2004338624766c42b5f4db2bb0976b2047a5c6b0`; synchronized `main` handoff `8fa832decc2f1be7762373f8ba4cc05a38b8404a`.

## Purpose

Phase24 addressed the analytical bottleneck exposed by the accepted 2026-08-21 Phase23 cycle: 23 WARM/HOT directional cases were current enough to be considered, but the frozen Phase11 support map contained zero SUPPORTED strategies, so no candidate could promote.

Phase24 did **not** weaken or edit the accepted Phase11 map in place. It built a separate preregistered challenger-evidence process, tested a bounded challenger set, and accepted the possibility that the correct result would be no support replacement.

That is the result: **no Phase24 challenger earned the right to replace Phase11 support, and the protected confirmation interval remained unread.**

## Authority boundary

Phase24 remained local analytical research only.

Across accepted target evidence:

- provider reads/writes: **0 / 0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- production ML writes: **0**;
- Phase11 support writes: **0**;
- automatic broker failover: **false**;
- scheduler/PostgreSQL/browser/LIVE authority: **none**.

Phase11 support therefore remains the production authority:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

## Gate 0 — forensic current-case diagnostic — COMPLETE

Gate 0 bound the exact accepted Phase11 study/support/registry lineage to the accepted Phase23 2026-08-21 current candidate population and then evaluated incumbent rules counterfactually without changing authority.

Accepted target-machine result:

- current WARM/HOT directional cases: **23**;
- authoritative promotions: **0**;
- eligible incumbent route evaluations: **92**;
- counterfactual incumbent rule fires: **48**;
- candidates with at least one counterfactual incumbent fire: **21 / 23**;
- support map: **3 MIXED / 5 UNSUPPORTED / 0 SUPPORTED**;
- protected evidence use: **none**;
- independent/pass result: **true**.

This proved that the current zero-promotion condition was not caused by dormant setup rules. Existing rules frequently fire on current routed cases, but none had earned accepted historical support.

The Gate 0 current result was descriptive only and was explicitly excluded from challenger selection.

## Gate 1 — preregistered v2 evidence methodology — COMPLETE

Gate 1 froze the replacement methodology **before** challenger performance was evaluated.

Canonical methodology:

- `docs/phase24_gate1_preregistered_methodology.md`
- `packages/backtesting/phase24_gate1_policy.py`

Locked design:

- exactly **28** bounded new v2 rule variants;
- symmetric **14 LONG / 14 SHORT** challenger population;
- development-only 75% selection tranche;
- three-session purge before internal validation;
- six chronological selection folds;
- three internal-validation folds;
- session-level cross-sectional aggregation so same-day ticker signals are not treated as independent support observations;
- six-session block bootstrap for overlapping three-session outcomes;
- explicit minimum raw-row and signal-session requirements;
- **10 bps** primary cost;
- **25 bps** stress cost;
- positive primary mean, median and >=50% positive-rate requirements;
- positive block-bootstrap lower confidence bound;
- yearly and market-regime robustness gates;
- Holm-Bonferroni control within family/direction;
- maximum one frozen selection per family/direction;
- selection lock written before internal validation;
- fresh finalist lock required before any protected evaluation;
- current Gate 0 evidence excluded from selection;
- incumbent protected evidence treated as already observed/non-fresh;
- zero protected-read authority during Gates 1-2.

Gate 1 fingerprint used by Gate 2:

`9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`

## Gate 2 — development-only challenger evaluation — COMPLETE

Exact target-machine Gate 2 head:

`f591942413973107d7abc9d21325623e2e7000f1`

Accepted result:

- preregistered challengers: **28**;
- selection basic-pass variants: **0**;
- multiplicity-pass variants: **0**;
- frozen family/direction selections: **0**;
- fresh finalists after internal validation: **0**;
- fresh finalist IDs: `[]`;
- protected evidence reads: **0**;
- provider reads: **0**;
- broker reads: **0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- Phase11 support writes: **0**;
- independent persisted validation: **PASS**;
- overall Gate 2: **PASS**.

Because no variant passed the preregistered basic selection gate, multiplicity selection and internal finalist evaluation had no strategy to advance. No Gate 3 protected-confirmation run is authorized or necessary for this challenger set.

## Forensic failure analysis

A read-only analysis of the already-written Gate 2 selection report was performed after Gate 2 was complete. It did not rerun the study, change any threshold, or read protected evidence.

### Challenger failure counts

Across all 28 challengers:

- `positive_folds`: **28 / 28 failed**;
- `primary_lcb_positive`: **28 / 28 failed**;
- `stress_mean_positive`: **28 / 28 failed**;
- `year_robustness`: **24 / 28 failed**;
- `positive_rate_half`: **20 / 28 failed**;
- `primary_mean_positive`: **20 / 28 failed**;
- `primary_median_positive`: **20 / 28 failed**;
- `regime_robustness`: **20 / 28 failed**;
- `min_raw_rows`: **3 / 28 failed**;
- `min_signal_sessions`: **2 / 28 failed**;
- `session_concentration`: **2 / 28 failed**.

This rules out sample scarcity as the general explanation. Most variants had abundant observations. The dominant failure was insufficient edge stability and cost robustness.

### Best long-side evidence

The three closest challengers were all trend-following LONG variants:

1. `trend_following_long_v2_rsi55_rvol1`
   - signal sessions: **1,188**;
   - raw rows: **725,668**;
   - 10 bps mean: **+0.000737** (~+7.37 bps);
   - 10 bps median: **+0.001210**;
   - positive session rate: **54.29%**;
   - 95% block-bootstrap LCB: **-0.000452**;
   - 25 bps stress mean: **-0.000763**;
   - failed only chronological folds, LCB, and 25 bps stress.

2. `trend_following_long_v2_rsi55`
   - 10 bps mean: **+0.000731**;
   - LCB: **-0.000454**;
   - 25 bps stress mean: **-0.000769**.

3. `trend_following_long_v2_rvol1`
   - 10 bps mean: **+0.000700**;
   - LCB: **-0.000502**;
   - 25 bps stress mean: **-0.000800**.

The incumbent `trend_following_long_v1` benchmark was similar:

- 10 bps mean: **+0.000684**;
- 10 bps median: **+0.001245**;
- positive session rate: **53.87%**;
- LCB: **-0.000536**;
- 25 bps stress mean: **-0.000816**.

Tightening the old trend rule therefore produced only a modest improvement, not a robust new edge.

The long momentum family also retained a small positive primary-cost mean, but its uncertainty and 25 bps stress evidence remained negative. Breakout LONG variants were negative even at the 10 bps primary cost.

### Short-side evidence

The short-side families were not merely failing conservative uncertainty gates. Their primary-cost means were generally negative.

Incumbent examples:

- `trend_following_short_v1`: 10 bps mean **-0.002774**;
- `momentum_short_v1`: 10 bps mean **-0.002881**;
- `breakdown_short_v1`: 10 bps mean **-0.004725**.

The corresponding v2 short variants remained materially negative. Phase24 therefore rejects the assumption that short strategies should simply mirror the existing long architecture with reversed signs.

### Sparse/contradictory pullback variants

Two combined pullback variants produced zero qualifying sessions:

- `pullback_long_v2_rsi55_macdpos`;
- `pullback_short_v2_rsi45_macdneg`.

This is descriptive evidence that those combined conditions were effectively contradictory or too restrictive in the accepted research population. They are not candidates for threshold relaxation after the fact.

## Methodological finding from the post-evidence code audit

Phase24 also exposed an upstream population-fidelity gap that is more important than simply generating more indicator thresholds.

The historical strategy evaluator used for Phase11/Phase24 studies evaluates strategy rules over the accepted long-history daily research rows with a broad **market-regime** direction route.

Production candidate promotion is narrower. A strategy is reached only after:

1. broad discovery;
2. WARM/HOT discovery-state filtering;
3. non-neutral discovery direction;
4. external strategy routing using discovery direction plus market/sector/ticker regime context;
5. historical support authority;
6. current rule firing.

Current production sector state is explicitly unavailable because no authoritative ticker-to-sector mapping is accepted, so sector context does not silently block. Market and ticker regime context still participate in the production route.

Therefore Phase11/24 historical support evidence is **not yet conditioned on the same population that production promotion actually sees**. In particular, the historical support study does not currently require historical WARM/HOT discovery qualification or historical ticker-route compatibility.

This does **not** invalidate the conservative Phase11/24 rejection result and does not authorize a support change. It identifies the next evidence question: whether strategy edge changes materially when the production candidate path is reconstructed point-in-time and strategy support is measured on the same routed population.

## Acceptance decision

Phase24 is accepted as a successful research phase with the disposition:

**NO SUPPORT REPLACEMENT.**

The accepted conclusions are:

- do not weaken Gate 1 thresholds after observing the failures;
- do not open the protected holdout for a zero-finalist challenger set;
- do not promote any v2 challenger;
- do not replace Phase11 support;
- do not assume symmetric short-side rules are appropriate;
- do not continue blind threshold tightening of the same daily-rule families;
- investigate production-path / route-fidelity evidence before designing a materially larger challenger family.

## Next analytical direction

The next numbered phase should first establish a point-in-time historical **production-path strategy research population**, preferably over the interval where the required 1d/4h/1h features and ticker-regime evidence are legitimately available.

That phase should determine whether ATLAS can reconstruct, without fabrication:

- historical broad-discovery eligibility;
- multi-timeframe discovery scoring;
- discovery-state hysteresis;
- WARM/HOT directional qualification;
- market and ticker regime routing consistent with production semantics;
- the exact strategy-rule population reaching candidate promotion.

Only after that route-fidelity population is independently validated should incumbent or new strategy families be re-evaluated. If production-path conditioning still produces no robust edge, the next challenger generation should move to materially different signal families such as relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite strategies rather than further threshold tweaks to the v1 rules.

## Non-goals preserved

Phase24 did not become a model-replacement, provider, broker, execution, GUI, scheduler, PostgreSQL, or LIVE phase. It did not manufacture a supported strategy merely because downstream activity was zero.
