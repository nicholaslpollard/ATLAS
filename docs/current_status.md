# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27 after Phase28 target closeout PASS / ACCEPTED_NEGATIVE.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Read `docs/phase_plain_english_contract.md` before beginning or closing any numbered phase. Phase28 provenance is in `docs/phase28_cross_stock_lead_lag_residual_network_alpha.md`, `docs/phase28_end_to_end_anti_workaround_audit.md`, and `docs/phase28_closeout.md`.

## Repository state

- **Phases 1–27 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Phase26 merge: PR #30 / `2074808605cf85b5462e5999ed1836d68b0434c3` — `ACCEPTED_NEGATIVE`.
- Phase27 merge: PR #31 / `dc015f51232dc66ba94b6175c276a0227d5a3761` — `ACCEPTED_NEGATIVE`.
- Phase27 post-merge CI `33107544402`: Ubuntu PASS / Windows PASS.
- Active branch: `phase-28-cross-stock-lead-lag-residual-network-alpha`.
- Phase28 target research and full local closeout are **PASS / ACCEPTED_NEGATIVE**.
- Phase28 target closeout head: `945adf9b2722da3822e6dcc79467ae9620d5d439`.
- Phase28 closeout-head CI `33113281485`: Ubuntu PASS / Windows PASS, including all retained validators and full regression.
- Phase28 final provenance documentation is being certified before merge.
- Signal-to-trade construction remains blocked until at least one alpha architecture earns accepted historical analytical `SUPPORTED` authority.

## Mission lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

The system is not optimized for trade count. A PASS/no-trade decision is correct whenever evidence, instrument economics, or portfolio risk does not justify a position.

## Architecture and authority lock

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> market/sector/ticker regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options instrument selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> outcome learning -> browser/web control plane -> production deployment/operations`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox and intended primary LIVE broker only after separate acceptance; Alpaca is manual secondary only. ML is evidence, AI is independent audit, and the browser is an operator surface rather than business-logic authority.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Root-cause / no-workaround lock

A failed check must be traced to the owning component, data artifact, assumption, interface, or process and corrected there. ATLAS cannot earn acceptance by bypassing a validator, weakening an invariant, ignoring a discrepancy, adding a parallel special-case path, changing a research threshold after results, or stacking repair wrappers merely to produce PASS.

Legitimate negative research is accepted rather than repaired into a positive result.

## Accepted strategy authority

Accepted Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Phases26, 27, and 28 did not replace this support map.

## Phase26 final evidence

Frozen policy fingerprint:

`24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`

- development usable observations: **21,483**;
- protected predictor observations: **1,096**;
- selection survivors: **0**;
- internal-validation finalists: **0**;
- supported candidates: **0**;
- protected return rows read: **0**;
- independent validation / anti-workaround: **PASS**;
- disposition: **ACCEPTED_NEGATIVE**.

## Phase27 final evidence

Frozen policy fingerprint:

`63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0`

- development model rows: **18,111**;
- protected predictor rows: **920**;
- selection survivors/winners/finalists/supported: **0 / 0 / 0 / 0**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- anti-workaround audit: **PASS**;
- disposition: **ACCEPTED_NEGATIVE**.

Target closeout head `bfc1c9898a6eb67bb6a9050c8d53802a887a940d`; PR #31 merged at `dc015f51232dc66ba94b6175c276a0227d5a3761`; post-merge workflow `33107544402` passed Ubuntu and Windows.

## Phase28 final evidence

Frozen policy fingerprint:

`0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5`

Phase28 tested four relational/residual signal families independently LONG/SHORT: residual momentum 20d, peer lead 1d, peer lead 5d, and peer diffusion gap 1d. It used the frozen 60-pair asymmetric lead-lag network, top three qualifying leaders with at least two required, exact PIT/split-safe canonical daily history, fixed 20% tails, exact 3-session outcomes, 10 bps primary / 25 bps stress costs, chronological selection/internal validation, dependence-aware bootstrap statistics, robustness gates, and global Holm correction across eight hypotheses.

Valid target result:

- development network rows: **14,466**;
- protected network predictor rows: **741**;
- selection survivors: **0**;
- selection winners: **0**;
- internal-validation finalists: **0**;
- supported candidates: **0**;
- protected candidate rows queried/read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0**.

Final target closeout at `945adf9b2722da3822e6dcc79467ae9620d5d439` returned:

- `Phase 28 closeout: PASS`;
- `Disposition: ACCEPTED_NEGATIVE`;
- end-to-end anti-workaround audit: **True**;
- Phase29 signal-to-trade entry satisfied: **False**;
- protected candidate/return reads: **0 / 0**;
- holdout consumed: **False**;
- provider/broker/order/PAPER/LIVE activity: **0 / 0 / 0 / 0 / 0**;
- `Pass: True`.

Closeout-head workflow `33113281485` passed Ubuntu and Windows, including the complete retained validator stack and full pytest regression suite.

**Scientific conclusion:** Phase28 was executed correctly but the tested cross-stock residual/lead-lag network signals did not demonstrate acceptable after-cost alpha. The network/window/leader/tail/cost/chronology/statistical policy is frozen historical provenance and must not be retuned after observing this result.

## Protected-holdout state

The master protected predictor window remains `2026-05-12` through `2026-08-11`.

Phases26, 27, and 28 each read **zero protected returns**. Phase28 had zero finalists, so no protected read plan or future-return query was created. The holdout therefore remains genuinely outcome-unopened.

A later separately preregistered alpha phase may use it only while this zero-read state remains independently provable. The first future protected-outcome read permanently consumes the holdout for subsequent strategy/model selection.

## Research failure map now established

ATLAS has now rejected three materially different tested alpha classes under rigorous frozen standards:

1. **Phase26:** hand-designed deterministic/composite self-feature rules;
2. **Phase27:** same-stock cross-sectional expected-return/ranking ML architectures;
3. **Phase28:** cross-stock residual/lead-lag relational signals.

This is useful scientific information. The next alpha phase must change the hypothesis class or information source in a way that is materially distinct from all three rather than tuning the rejected families.

## Immediate handoff

1. certify the final Phase28 provenance/documentation head on Ubuntu and Windows;
2. open and merge the Phase28 PR only after exact-head green CI;
3. verify post-merge `main` on both operating systems;
4. rebaseline the roadmap so the next numbered phase remains an alpha gate rather than falsely entering signal-to-trade construction;
5. preregister the next materially different alpha architecture before any protected or target performance is inspected.

No PAPER or LIVE authority is granted by Phase28.

## Downstream roadmap before the next rebaseline

The currently numbered Phase29 signal-to-trade construction gate remains blocked because its entry condition is not satisfied. After Phase28 merge, the roadmap must insert the next alpha research phase ahead of that work and shift downstream phase numbers accordingly.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; research ideas are hypotheses rather than assumed edge; uncertain mutation state requires reconciliation; frontend/UI controls never create or bypass authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; and LIVE authority exists only after a separately accepted final activation phase.
