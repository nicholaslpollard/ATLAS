# Phase 24 Gate 1 — Preregistered Challenger Methodology

**Status: LOCKED / NO CHALLENGER RESULTS READ / NO PROTECTED READ AUTHORITY**

Gate 1 is defined after the accepted Gate 0 forensic result and before any challenger variant is evaluated against protected evidence.

## Accepted Gate 0 evidence

Target-machine Gate 0 on finalized session `2026-08-21` passed with:

- accepted WARM/HOT directional candidates: **23**;
- authoritative promotions: **0**;
- route-eligible incumbent evaluations: **92**;
- incumbent rule fires ignoring support authority: **48**;
- candidates with at least one counterfactual incumbent fire: **21 / 23**;
- Phase11 support map: **3 MIXED / 5 UNSUPPORTED / 0 SUPPORTED**;
- provider reads/writes: **0 / 0**;
- broker reads/writes: **0 / 0**;
- order/PAPER/LIVE writes: **0 / 0 / 0**;
- Phase11 support writes: **0**;
- Gate 0 pass: **true**.

These current results are forensic only. They are explicitly excluded from challenger selection and threshold tuning.

## Why v2 is different from Phase11 v1

Phase11 v1 uses individual ticker-signal rows and a two-half mean-sign rule. Gate 1 treats dependence as a first-class issue because many observations occur on the same market session and every outcome spans three sessions.

The v2 framework therefore uses:

- chronological selection and internal-validation tranches;
- a three-session purge at the selection/validation boundary;
- session-clustered evidence;
- six-session moving/block bootstrap uncertainty, longer than the three-session outcome horizon;
- minimum unique signal-session requirements in addition to raw row counts;
- multi-fold chronological stability;
- yearly and market-regime robustness gates;
- 10 bps primary and 25 bps stress costs;
- median/positive-rate evidence in addition to mean return;
- within-family/direction Holm-Bonferroni control;
- at most one selected finalist per family/direction before internal validation;
- one-shot protected confirmation only for newly defined finalists after the finalist set is frozen.

## Development partition

The accepted historical research source remains the authority.

Only sessions strictly before the existing protected holdout may participate in Gate 1 selection or internal validation.

The pre-protected development sessions are split chronologically:

1. first **75%**: challenger selection;
2. **3 exchange sessions purged** at the boundary;
3. remaining development sessions: internal chronological validation.

The protected interval is not read during Gate 1.

## Dependence and uncertainty controls

Locked values:

- outcome horizon: **3 sessions**;
- bootstrap block: **6 sessions**;
- bootstrap replicates: **2,000**;
- deterministic bootstrap seed: `240124`;
- selection confidence: **95%**;
- internal-validation confidence: **90%**;
- future protected-confirmation confidence: **80%**;
- maximum fraction of a strategy's raw evidence contributed by one session: **10%**.

The block-bootstrap unit is the chronological session-level return series after cross-sectional signals for the same session are aggregated. This prevents the system from treating hundreds of same-day ticker rows as hundreds of fully independent observations.

## Selection gates

A challenger cannot be selected unless all locked gates pass on the selection tranche:

- at least **1,000** routed signal rows;
- signals on at least **250 unique sessions**;
- **6** chronological folds with at least **5 positive** mean-return folds at 10 bps;
- 10 bps mean return positive;
- 10 bps median return positive;
- 10 bps positive-return rate at least 50%;
- 95% session-block-bootstrap lower confidence bound on the 10 bps mean is positive;
- 25 bps stress mean is positive;
- at least 60% of sufficiently populated calendar-year slices are positive at 10 bps;
- at least 50% of sufficiently populated compatible market-regime slices are positive at 10 bps;
- no single session exceeds the locked 10% raw-row concentration ceiling.

Calendar-year and regime slices are considered sufficiently populated at **20 unique signal sessions**.

Within each family/direction group, multiplicity is controlled by **Holm-Bonferroni at alpha 0.05**. At most one variant per family/direction may advance to internal validation. Passing variants are ranked by the preregistered uncertainty-first score: highest primary-cost block-bootstrap lower bound, then highest 25 bps stress mean, then deterministic variant ID.

## Internal-validation gates

The selected family/direction finalist is frozen before the internal-validation tranche is read.

It must then pass:

- at least **300** routed signal rows;
- signals on at least **80 unique sessions**;
- **3** chronological folds with at least **2 positive** 10 bps mean-return folds;
- positive 10 bps mean and median;
- positive-return rate at least 50%;
- positive 90% session-block-bootstrap lower confidence bound;
- positive 25 bps stress mean;
- the same 10% single-session concentration ceiling.

An internal-validation failure cannot be rescued by another member of the same family/direction after the validation results are seen. That family/direction produces no fresh finalist for protected confirmation in this Phase24 study.

## Preregistered challenger space

Gate 1 contains exactly **28 new v2 variants**, split symmetrically **14 LONG / 14 SHORT**:

- trend-following: 3 per direction;
- momentum: 4 per direction;
- breakout/breakdown: 4 per direction;
- pullback: 3 per direction.

The variants only tighten existing v1 rules or add confirmation using accepted features already present in the historical source:

- `rsi_14`;
- `relative_volume_20`;
- `macd_hist_12_26_9`.

No new feature discovery, arbitrary continuous optimization, ML retraining, genetic search, Bayesian optimization, or post-result threshold editing is allowed.

The exact variant IDs/mutations are code-locked in `packages/backtesting/phase24_gate1_policy.py` and fingerprinted.

## Incumbent benchmark handling

The eight Phase11 incumbents must be evaluated under the same v2 **selection and internal-validation** framework for comparison.

Their already-seen Phase11 protected results are contaminated for fresh-confirmation purposes. They cannot become a newly supported strategy merely by reusing that observed protected evidence.

## Future protected confirmation

Gate 1 grants **zero protected read authority**. This section preregisters the later one-shot confirmation rule only.

A newly frozen challenger finalist may later be evaluated once on the untouched protected interval. Final confirmation will require:

- at least **75** routed rows;
- signals on at least **24 unique sessions**;
- 3 chronological folds with at least 2 positive 10 bps folds;
- positive 10 bps mean and median;
- positive 80% session-block-bootstrap lower confidence bound;
- positive 25 bps stress mean.

No protected result may be used to alter the variant, threshold, family ranking, or validation rule. A failure is a failure.

## Authority boundary

Gate 1 is local research only. It grants no authority for:

- provider reads/writes;
- broker reads/writes;
- order mutation;
- PAPER submission;
- LIVE;
- AI-provider calls;
- production ML changes;
- Phase11 support replacement;
- Phase23 promotion changes.

The Phase11 support map remains authoritative throughout Gate 1.

## Next gate

Gate 2 may implement and run the development-only selection/internal-validation engine exactly against this locked policy. Gate 2 still may not read protected evidence until the fresh finalist set is frozen and independently validated.
