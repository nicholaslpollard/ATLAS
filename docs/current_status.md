# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27 after Phase30 historical-news feasibility PASS and scientific-policy freeze.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Then read this file, `docs/phase30_event_driven_public_information_alpha.md` for the immutable feasibility boundary, and `docs/phase30_scientific_contract.md` for the now-frozen Phase30 scientific contract.

## Repository state

- **Accepted project foundation through Phase29.**
- Phase26 PR #30 merge: `2074808605cf85b5462e5999ed1836d68b0434c3` — `ACCEPTED_NEGATIVE`.
- Phase27 PR #31 merge: `dc015f51232dc66ba94b6175c276a0227d5a3761` — `ACCEPTED_NEGATIVE`.
- Phase28 PR #32 merge: `285f112d51463dd1e06ea4e874a882ad98f71dc5` — `ACCEPTED_NEGATIVE`.
- Phase29 PR #33 merge: `87c9450e1b21606b83489f16ff326235ae92eb2b` — `ACCEPTED_NEGATIVE`.
- Phase29 post-merge workflow `33124971664`: Ubuntu PASS / Windows PASS.
- **Active phase:** Phase30 — Event-Driven Public-Information Alpha.
- Active branch: `phase-30-event-driven-public-information-alpha`.
- Phase30 feasibility/scientific-freeze implementation commits include `21d53bdb76e37649a93d61057bfb113fd5448a81`, `b632e9d2bb1c550e74b63baf212882bdf2c2736e`, and CI integration `9dc03efb7018b8d68b9e26427d579b767bbbe133`.
- Signal-to-trade construction is Phase31 and remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.

## Mission / authority lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

Parquet is durable analytical history; DuckDB is analytics; PostgreSQL is future operational state; Massive is primary market/reference; Webull is primary PAPER/sandbox and intended primary LIVE only after separate acceptance; Alpaca is manual secondary only. ML and AI do not create trade authority. Browser/UI never bypasses backend authority.

LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Root-cause / no-workaround lock

A failed check must be traced to the owning layer and corrected there. ATLAS cannot earn acceptance by weakening a validator, ignoring a discrepancy, adding a bypass/parallel authority path, changing a research threshold after results, or stacking repair wrappers merely to obtain PASS.

Legitimate negative research is accepted rather than repaired into a positive result.

## Accepted strategy authority

Phase11 support remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Phases26–29 did not replace this map.

## Modern alpha research evidence

### Phase26 — focal self-feature/composite alpha

Policy fingerprint `24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`.

- development observations: **21,483**;
- protected predictors: **1,096**;
- survivors/finalists/supported: **0 / 0 / 0**;
- protected returns: **0**;
- disposition: `ACCEPTED_NEGATIVE`.

### Phase27 — cross-sectional learned ranking alpha

Policy fingerprint `63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0`.

- development rows: **18,111**;
- protected predictors: **920**;
- survivors/winners/finalists/supported: **0 / 0 / 0 / 0**;
- protected candidate/return reads: **0 / 0**;
- disposition: `ACCEPTED_NEGATIVE`.

### Phase28 — cross-stock lead-lag/residual-network alpha

Policy fingerprint `0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5`.

- development network rows: **14,466**;
- protected network predictors: **741**;
- survivors/winners/finalists/supported: **0 / 0 / 0 / 0**;
- protected candidate/return reads: **0 / 0**;
- disposition: `ACCEPTED_NEGATIVE`.

### Phase29 — relative-value statistical-arbitrage confirmation

Policy fingerprint `5d40218c1c554117388d99362ce1343fde8a598aaa6d09b95e83fad7e625b30d`.

- development relative-value rows: **14,523**;
- protected relative-value predictors: **745**;
- selection survivors/winners/internal finalists/supported: **0 / 0 / 0 / 0**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**;
- independent validation: **PASS**;
- end-to-end anti-workaround audit: **PASS**;
- disposition: **`ACCEPTED_NEGATIVE`**.

The four failed modern families may not be retuned after observing their results.

## Phase30 — current exact state

### Feasibility/provenance gate — PASSED

Target-machine command `scripts/run_phase30_news_feasibility.py` passed under feasibility fingerprint:

`04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312`

Observed coverage facts only:

- `research_start`: 642 articles / 642 ticker-linked;
- `development_end`: 251 / 251;
- `protected_start`: 249 / 249;
- `protected_end`: 77 / 77;
- total articles: **1,219**;
- total ticker-linked: **1,219**;
- successful provider pages: **4**;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- provider writes / broker reads / broker writes / orders / PAPER / LIVE: **0 / 0 / 0 / 0 / 0 / 0**.

This proves the historical Massive news source is readable at the frozen boundaries with exact publication timestamps/ticker linkage. It does **not** grant performance authority.

### Scientific hypothesis contract — FROZEN

Policy fingerprint:

`341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8`

Phase30 deliberately authorizes only news-event metadata for alpha:

- `id`;
- `published_utc`;
- exact provider-native `tickers`.

Article text/content and provider-generated `insights` remain provenance only because the feasibility work did not establish historical revision/model-vintage semantics. Retrospective NLP/provider sentiment is therefore not allowed in this phase.

Frozen event timing and signal construction:

- first XNYS session whose official close is at least **30 minutes** after publication;
- 20 prior XNYS sessions, zero-filled, as the news baseline;
- `news_surprise = log1p(current_unique_article_count) - mean(log1p(previous_20_session_counts_with_zeros))`;
- current market-reaction field = already-PIT-safe Phase26 `d1_return_1`;
- same-session/direction minimum rows = 5;
- fixed top 20% news-surprise tail;
- exact `t+3` directional outcome;
- 10 bps primary / 25 bps stress costs;
- chronological 75% selection + 3-session purge + internal remainder;
- 6 selection / 3 internal / 3 protected folds;
- moving/block bootstrap 6 sessions / 2,000 reps / seed `300230`;
- global Holm-Bonferroni across exactly **4** hypotheses;
- year/regime/session/ticker concentration robustness;
- at most one finalist per direction;
- runner-up substitution forbidden.

Exactly four frozen hypotheses:

1. `news_shock_aligned_continuation_long`;
2. `news_shock_aligned_continuation_short`;
3. `news_shock_counterreaction_reversal_long`;
4. `news_shock_counterreaction_reversal_short`.

No fifth hypothesis, text variant, provider-sentiment variant, alternate lookback, alternate timing cutoff, or post-result threshold search is authorized.

### Next internal Phase30 action

Run the full historical **non-performance** news acquisition from `2021-07-16` through `2026-08-11`, sharded monthly with immutable local evidence and resumable metadata. This reads provider news only and must continue to report zero target/protected outcome rows.

After acquisition passes, build development and protected **predictor-only** news-shock frames under the frozen policy. Development outcomes may then be joined only through the explicitly implemented development selection path. Protected returns remain finalist-only.

## Protected-holdout state

Master protected predictor window: `2026-05-12` through `2026-08-11`.

Phases26, 27, 28, 29, and Phase30 feasibility/scientific freeze have read **zero protected returns**. The holdout remains genuinely outcome-unopened.

A nonempty future Phase30 protected-return read is allowed only after development selection, internal validation, frozen finalists, independent blindness audit, and immutable finalist-only read plan. Any such read consumes the holdout for later alpha selection.

## Research failure map

Rejected under frozen standards:

1. Phase26 — deterministic/composite focal self-feature rules;
2. Phase27 — same-stock cross-sectional learned expected-return/ranking models;
3. Phase28 — cross-stock residual/lead-lag predictive signals;
4. Phase29 — trailing PCA/pair relative-value mean-reversion confirmation.

Phase30 changes the information mechanism to timestamped public-news arrival rather than searching another parameterization of those failures.

## Rebaselined downstream roadmap

- **Phase30:** Event-Driven Public-Information Alpha.
- **Phase31:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — requires supported alpha.
- **Phase32:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase33:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase34:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase35:** Production Web App/Operations/Deployment.
- **Phase36:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase37:** Controlled LIVE Activation & Evidence-Based Scaling.

## Persistent non-negotiables

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; research ideas are hypotheses; uncertain mutation state requires reconciliation; UI never creates/bypasses authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; protected performance is finalist-only; LIVE authority exists only after a separately accepted activation phase.
