# Phase 24 — Strategy Evidence Challenger & Support Replacement

**Status: ACCEPTED / MERGED — NO SUPPORT REPLACEMENT**

Authoritative merge: `15b77321d4815f9f52fe74d47ba32fee8127526a` through PR #26.

Upstream authority: Phase23 merge `2004338624766c42b5f4db2bb0976b2047a5c6b0`.

## Purpose

Phase24 addressed the analytical bottleneck exposed by the accepted 2026-08-21 Phase23 cycle: 23 WARM/HOT directional cases were current enough to be considered, but Phase11 contained zero SUPPORTED strategies, so no candidate could promote.

Phase24 did not weaken Phase11. It built a separate preregistered challenger process and accepted the possibility that no replacement would earn support.

That is the accepted result: **no Phase24 challenger earned support-replacement authority, no protected Gate3 evaluation occurred, and Phase11 remains authoritative unchanged.**

## Authority boundary

Phase24 remained local analytical research only.

Across accepted evidence:

- provider reads/writes: 0 / 0;
- broker reads/writes: 0 / 0;
- order/PAPER/LIVE writes: 0 / 0 / 0;
- production ML writes: 0;
- Phase11 support writes: 0;
- scheduler/PostgreSQL/browser/LIVE authority: none;
- automatic broker failover: false.

Accepted Phase11 support therefore remains:

- SUPPORTED: 0;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

## Gate0 — current-case forensic diagnostic

Gate0 bound the exact accepted Phase11 study/support/registry lineage to the accepted Phase23 2026-08-21 current candidate population and counterfactually evaluated incumbent rules without changing authority.

Target result:

- current WARM/HOT directional cases: 23;
- authoritative promotions: 0;
- eligible incumbent route evaluations: 92;
- counterfactual incumbent rule fires: 48;
- cases with at least one incumbent fire: 21 / 23;
- support status: 3 MIXED / 5 UNSUPPORTED / 0 SUPPORTED;
- protected evidence use: none;
- all external/execution/support writes: 0;
- PASS.

This proved the current zero-promotion condition was not caused by dormant setup rules.

## Gate1 — preregistered v2 methodology

Gate1 froze the replacement methodology before challenger performance was observed.

Policy fingerprint:

`9550dd572edb056be7ee06c7a4319f9c2057ac304c630fcd3a1382ebcf83007a`

Locked design:

- exactly 28 bounded v2 variants, 14 LONG / 14 SHORT;
- development-only 75% selection tranche;
- three-session purge before internal validation;
- six chronological selection folds;
- three internal-validation folds;
- session-level cross-sectional aggregation so same-day ticker signals are not treated as independent support observations;
- six-session block bootstrap for overlapping three-session outcomes;
- explicit minimum row/signal-session requirements;
- 10 bps primary cost;
- 25 bps stress cost;
- positive mean, median, >=50% positive-rate, and positive lower-confidence-bound requirements;
- yearly and market-regime robustness gates;
- Holm-Bonferroni control within family/direction;
- maximum one frozen selection per family/direction;
- current Gate0 evidence excluded from selection;
- incumbent protected evidence treated as already observed/non-fresh;
- zero protected-read and support-replacement authority during Gates1-2.

## Gate2 — development-only challenger evaluation

Exact target head:

`f591942413973107d7abc9d21325623e2e7000f1`

Target result:

- preregistered challengers: 28;
- selection basic-pass variants: 0;
- multiplicity-pass variants: 0;
- frozen family/direction selections: 0;
- fresh finalists after internal validation: 0;
- fresh finalist IDs: `[]`;
- protected evidence reads: 0;
- provider reads: 0;
- broker reads: 0;
- order/PAPER/LIVE writes: 0 / 0 / 0;
- Phase11 support writes: 0;
- independent persisted validation: PASS;
- overall Gate2: PASS.

Because no variant passed the preregistered basic gate, no Gate3 protected-confirmation run was authorized.

## Post-Gate2 forensic analysis

A read-only analysis of the persisted selection report was performed after Gate2. It did not rerun the study, alter thresholds, or read protected evidence.

Across all 28 challengers:

- `positive_folds`: 28/28 failed;
- `primary_lcb_positive`: 28/28 failed;
- `stress_mean_positive`: 28/28 failed;
- `year_robustness`: 24/28 failed;
- `positive_rate_half`: 20/28 failed;
- `primary_mean_positive`: 20/28 failed;
- `primary_median_positive`: 20/28 failed;
- `regime_robustness`: 20/28 failed;
- `min_raw_rows`: only 3/28 failed;
- `min_signal_sessions`: only 2/28 failed;
- `session_concentration`: only 2/28 failed.

The dominant failure was therefore weak temporal/uncertainty/cost robustness, not generic sample scarcity.

### Closest long-side evidence

`trend_following_long_v2_rsi55_rvol1`:

- signal sessions: 1,188;
- raw rows: 725,668;
- mean after 10 bps: +0.000737 (~+7.37 bps);
- median after 10 bps: +0.001210;
- positive session rate: 54.29%;
- block-bootstrap LCB: -0.000452;
- mean after 25 bps: -0.000763;
- failed chronological folds, LCB, and stress mean.

The incumbent `trend_following_long_v1` benchmark was similar: mean10 +0.000684, LCB -0.000536, mean25 -0.000816. Tightening the old trend rule produced only a modest improvement, not a robust new edge.

Long momentum retained a smaller positive primary-cost mean but negative uncertainty/stress evidence. Breakout LONG variants were negative even at 10 bps.

### Short-side evidence

Short-side trend/momentum/breakdown rules were materially negative at the primary 10 bps cost. Incumbent examples:

- `trend_following_short_v1`: -0.002774;
- `momentum_short_v1`: -0.002881;
- `breakdown_short_v1`: -0.004725.

The v2 short variants remained materially negative. Phase24 therefore rejects the assumption that short strategies should simply mirror long rules with reversed signs.

Two combined pullback variants produced zero qualifying sessions; they are descriptive failures, not candidates for post-hoc threshold relaxation.

## Acceptance decision

Phase24 is accepted with disposition:

**NO SUPPORT REPLACEMENT.**

Consequences:

- do not weaken Gate1 thresholds after observing failures;
- do not open protected evidence for a zero-finalist set;
- do not promote any v2 challenger;
- do not replace Phase11 support;
- do not assume symmetric LONG/SHORT architecture;
- stop blind threshold tightening of the same daily-rule families.

Final pre-merge living-doc head: `5ed3311d4ec1ac97cf841e160cf9c0987f731fe5`.

Final pre-merge exact-head CI `32806726958`: Ubuntu/Windows SUCCESS; every validator through Phase24 Gate2 and full regression passed.

Authoritative merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.

## Post-evidence methodological finding

Phase24 exposed a population-fidelity gap more important than another threshold sweep.

Historical Phase11/24 support evaluates rules over broad historical daily rows with broad market-regime direction routing.

Production promotion is narrower:

1. PIT universe eligibility;
2. broad discovery foundation;
3. 1d/4h/1h discovery scoring;
4. discovery-state hysteresis;
5. WARM/HOT directional qualification;
6. market/sector/ticker strategy routing;
7. historical support authority;
8. current rule firing.

Current sector context is intentionally `UNAVAILABLE` because no authoritative ticker-to-sector mapping is accepted. Market and ticker routing still participate.

Therefore historical support is not yet measured on the same population ATLAS actually tries to trade. This does not invalidate the conservative Phase11/24 rejection; it identifies the next research question.

## Next phase boundary

Define next:

**Phase25 — Historical Production-Path Replay & Route-Fidelity Strategy Evidence**.

Initial Phase25 should:

- remain provider/broker/order/PAPER/LIVE/support-authority free;
- begin no earlier than legitimate ticker/intraday origin **2021-08-16**;
- never fabricate pre-2021 1h/4h/ticker context;
- reconstruct PIT universe, discovery, hysteresis, WARM/HOT direction, and market/ticker routing;
- keep sector `UNAVAILABLE` absent authoritative historical sector mapping;
- initially hold incumbent rules and the three-session outcome fixed;
- compare broad vs production-path-conditioned evidence via a transparent attribution ladder;
- independently validate the replay population before any support replacement.

If route-fidelity conditioning still yields no robust edge, a later separately preregistered challenger process should move to materially different families such as relative strength, mean reversion, gap/event, volatility-normalized, multi-timeframe, or composite strategies rather than further v1 threshold tweaks.
