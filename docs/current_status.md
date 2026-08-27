# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27 after Phase27 acceptance and merge.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Read `docs/phase_plain_english_contract.md` before beginning or closing any numbered phase. The active Phase28 specification is `docs/phase28_cross_stock_lead_lag_residual_network_alpha.md`.

## Repository state

- **Phases 1–27 ACCEPTED / MERGED.**
- Phase23 merge: `2004338624766c42b5f4db2bb0976b2047a5c6b0`.
- Phase24 merge: `15b77321d4815f9f52fe74d47ba32fee8127526a`.
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950` through PR #27.
- Phase26 merge: PR #30 / `2074808605cf85b5462e5999ed1836d68b0434c3` — `ACCEPTED_NEGATIVE`.
- Phase27 merge: PR #31 / `dc015f51232dc66ba94b6175c276a0227d5a3761` — `ACCEPTED_NEGATIVE`.
- Phase27 post-merge CI `33107544402`: Ubuntu PASS / Windows PASS, including all retained validators and full regression.
- Active branch: `phase-28-cross-stock-lead-lag-residual-network-alpha`.
- **Current phase/gate: Phase28 — Cross-Stock Lead-Lag & Residual Network Alpha.**
- Signal-to-trade construction is now Phase29 and remains blocked until at least one alpha architecture earns accepted historical analytical `SUPPORTED` authority.

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

Neither Phase26 nor Phase27 replaced this support map.

## Phase26 final evidence

Frozen Phase26 policy fingerprint:

`24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`

Valid target result:

- development usable observations: **21,483**;
- protected predictor observations: **1,096**;
- selection survivors: **0**;
- internal-validation finalists: **0**;
- supported candidates: **0**;
- protected return rows read: **0**;
- independent validation / anti-workaround: **PASS**.

## Phase27 final evidence

Frozen Phase27 policy fingerprint:

`63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0`

Valid target result:

- development model rows: **18,111**;
- protected predictor rows: **920**;
- selection survivors: **0**;
- selection winners: **0**;
- internal-validation finalists: **0**;
- supported candidates: **0**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- end-to-end anti-workaround audit: **PASS**;
- provider/broker/order/PAPER/LIVE activity: **0**.

Target closeout at branch head `bfc1c9898a6eb67bb6a9050c8d53802a887a940d` returned `PASS / ACCEPTED_NEGATIVE`. PR #31 merged at `dc015f51232dc66ba94b6175c276a0227d5a3761`; post-merge workflow `33107544402` passed Ubuntu and Windows.

**Practical conclusion:** both the tested hand-designed self-feature rules and the tested same-stock cross-sectional ML/ranking architectures failed to demonstrate acceptable after-cost alpha. The next phase therefore changes the information source.

## Protected-holdout state

The master protected predictor window remains `2026-05-12` through `2026-08-11`.

Phases26 and 27 each read **zero protected returns**. Phase27's independent blindness/closeout evidence confirmed that the holdout is still outcome-unopened. Phase28 may use it only after its own policy/specification is frozen and an independent pre-read blindness audit proves the prior zero-read state and absence of Phase28 protected outcome artifacts.

The first future protected-return read permanently consumes this holdout for later strategy/model selection.

## Phase28 rationale

Phase28 asks a materially different question: **does the recent behavior of other production-relevant stocks contain information about a focal candidate's next move after common cross-sectional movement is removed?**

The phase does not add another generic classifier over the same 29 Phase27 self-features. It builds observation-time relational information from the canonical daily lake and exact PIT candidate identities, using a frozen asymmetric lead-lag network and residual-return baselines.

## Phase28 frozen high-level design

Active specification:

`docs/phase28_cross_stock_lead_lag_residual_network_alpha.md`

Frozen design:

- source focal population: accepted Phase26 production-path-native development/protected predictor rows;
- peer universe at each observation session: all eligible same-session Phase26 WARM/HOT directional candidates, irrespective of focal direction;
- daily history: canonical finalized 1d bars only, restricted to exact safe identity intervals;
- split crossing in network lookback: fail/censor that ticker for the observation;
- common-move residual: each peer's daily return minus the contemporaneous cross-sectional median peer return;
- lead-lag estimation: fixed 60 lag pairs ending at `t-1`, at least 50 valid aligned observations;
- edge strength: `corr(peer[s-1], focal[s]) - corr(focal[s-1], peer[s])`, requiring positive forward correlation and positive asymmetry;
- fixed top 3 leaders, deterministic tie break, at least 2 leaders;
- leader weights: normalized positive asymmetry;
- four frozen raw signals: 20-session focal residual momentum, weighted leader 1-session residual return, weighted leader 5-session residual return, and 1-session leader-minus-focal diffusion gap;
- LONG score = raw signal; SHORT score = negative raw signal;
- every row must have all four signals finite; all eight hypotheses use the same complete-case population;
- minimum 5 complete rows per session/direction;
- fixed top 20% score tail with deterministic tie break;
- eight hypotheses = four signal families × LONG/SHORT;
- fixed 3-session outcome horizon;
- 75% chronological selection, exact 3-session purge, internal remainder;
- 10 bps primary / 25 bps stress economics;
- global Holm-Bonferroni across all eight hypotheses;
- session/block dependence handling, sample/concentration/year/regime robustness;
- at most one winner/finalist per direction; no runner-up substitution after internal failure;
- finalist-only protected confirmation after independent blindness audit;
- provider/broker/order/PAPER/LIVE/automation activity zero.

No network window, leader count, signal formula, tail fraction, outcome horizon, costs, or acceptance threshold may change after Phase28 performance is observed.

## Phase28 implementation path

1. frozen spec + machine-readable policy/fingerprint;
2. deterministic residual/lead-lag network primitives with unit tests;
3. source-lineage and network-population reconstruction from accepted local artifacts;
4. development selection + global multiplicity;
5. internal validation and finalist freeze;
6. independent pre-read protected blindness audit;
7. zero-finalist skip or immutable finalist-only protected read plan/confirmation;
8. independent persisted-artifact reconciliation;
9. cumulative target runner;
10. full phase-end closeout, anti-workaround audit, retained validators, pytest, Ubuntu/Windows CI, plain-English end, docs, accept/repair, merge.

No user-local command is required until repository implementation and exact-head CI reach the genuine target-evidence boundary.

## Rebaselined downstream roadmap

- **Phase28:** Cross-Stock Lead-Lag & Residual Network Alpha — active alpha gate.
- **Phase29:** Signal-to-Trade Construction & Portfolio Optimization + Web Data Contracts/Prototype — requires supported alpha.
- **Phase30:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase31:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase32:** Outcomes, Learning, Drift Monitoring & Governance + Performance/Learning UI.
- **Phase33:** Production Web Application, Operations & Deployment.
- **Phase34:** LIVE Readiness, Deployment Hardening, Reconciliation & Failure Certification — LIVE still disabled.
- **Phase35:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; research ideas are hypotheses rather than assumed edge; uncertain mutation state requires reconciliation; frontend/UI controls never create or bypass authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; and LIVE authority exists only after Phase35 acceptance.
