# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-27 after Phase29 full closeout and roadmap rebaseline.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase source of truth. Read `docs/phase_plain_english_contract.md` before beginning/closing a numbered phase. Phase29's frozen historical specification is `docs/phase29_relative_value_statistical_arbitrage.md`; the next active specification is created when Phase30 begins.

## Repository state

- **Accepted project foundation through Phase29.**
- Phase25 merge: `ba0a1588d816c3f2c7d4c2f0754b5fb4a29c8950`.
- Phase26 PR #30 merge: `2074808605cf85b5462e5999ed1836d68b0434c3` — `ACCEPTED_NEGATIVE`.
- Phase27 PR #31 merge: `dc015f51232dc66ba94b6175c276a0227d5a3761` — `ACCEPTED_NEGATIVE`.
- Phase28 PR #32 merge: `285f112d51463dd1e06ea4e874a882ad98f71dc5` — `ACCEPTED_NEGATIVE`.
- Phase28 post-merge workflow `33114372397`: Ubuntu PASS / Windows PASS.
- Phase29 accepted closeout head: `e078fe56cad4900be54bf39d7d88679d2f6dc4df` — `ACCEPTED_NEGATIVE`.
- Phase29 exact-head workflow `33123195681`: Ubuntu PASS / Windows PASS, including the Phase29 closeout/anti-workaround validator and full pytest.
- Phase29 merge is the current repository-closeout action; no further Phase29 performance read is required.
- **Next gate after merge: Phase30 — Event-Driven Public-Information Alpha.**
- Signal-to-trade construction is now Phase31 and remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.

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

## Alpha research evidence

### Phase26

Policy fingerprint `24e4f0e24d3e81dfc3dc572f0562337b2c156cd3ea22d6a7448b6ad6586016d2`.

- development observations **21,483**;
- protected predictors **1,096**;
- survivors/finalists/supported **0 / 0 / 0**;
- protected returns **0**;
- independent + anti-workaround PASS;
- disposition `ACCEPTED_NEGATIVE`.

### Phase27

Policy fingerprint `63030d55fbdb60ce61ea0c84081ae95d62d68fc717f494aa41a23d31c410aab0`.

- development rows **18,111**;
- protected predictors **920**;
- survivors/winners/finalists/supported **0 / 0 / 0 / 0**;
- protected candidate/return reads **0 / 0**;
- holdout consumed **False**;
- independent + anti-workaround PASS;
- disposition `ACCEPTED_NEGATIVE`.

### Phase28

Policy fingerprint `0f15966f61a0baf52513cd46dc4fa8492c98e7dc8cf9ed3d551c2ebc955adea5`.

- development network rows **14,466**;
- protected network predictors **741**;
- survivors/winners/finalists/supported **0 / 0 / 0 / 0**;
- protected candidate/return reads **0 / 0**;
- holdout consumed **False**;
- independent + end-to-end anti-workaround PASS;
- disposition `ACCEPTED_NEGATIVE`.

### Phase29

Policy fingerprint `5d40218c1c554117388d99362ce1343fde8a598aaa6d09b95e83fad7e625b30d`.

Frozen hypotheses were PCA-residual reversion and nearest-distance-pair reversion, independently LONG/SHORT. The target and full closeout were executed on the exact accepted implementation without post-result research changes.

- development relative-value rows **14,523**;
- protected relative-value predictors **745**;
- selection survivors **0**;
- selection winners **0**;
- internal-validation finalists **0**;
- supported candidates **0**;
- protected candidate rows read **0**;
- protected return rows read **0**;
- protected holdout consumed **False**;
- independent validation **PASS**;
- end-to-end anti-workaround audit **PASS**;
- provider/broker/order/PAPER/LIVE activity **0**;
- local cumulative + full closeout **PASS**;
- disposition **`ACCEPTED_NEGATIVE`**.

The result is valid negative evidence. Formation length, PCA components, pair rule, tail, costs, chronology, and statistical gates are not to be retuned after this result.

## Protected-holdout state

Master protected predictor window: `2026-05-12` through `2026-08-11`.

Phases26, 27, 28, and 29 read **zero protected returns**. Phase29 had zero finalists, so no protected read plan was created. The holdout remains genuinely outcome-unopened.

A future alpha phase may use it only through its own independently validated finalist-only protected path. The first nonempty protected outcome read permanently consumes it for later alpha selection.

## Research failure map

Rejected under frozen standards:

1. Phase26 — deterministic/composite focal self-feature rules;
2. Phase27 — same-stock cross-sectional learned expected-return/ranking models;
3. Phase28 — cross-stock residual/lead-lag predictive signals;
4. Phase29 — trailing PCA/pair relative-value mean-reversion confirmation.

These results must not be converted into another threshold/model search over the same information families.

## Next Phase30 direction — Event-Driven Public-Information Alpha

Phase30 changes the information source rather than retuning price-derived signals. Its first internal step is non-performance-bearing historical-news feasibility/provenance:

- verify Massive historical ticker-news entitlement/coverage over the intended research windows;
- prove exact `published_utc` chronology, pagination, ticker association, deterministic replay, and PIT-safe acquisition;
- persist immutable raw article evidence and provenance;
- exclude provider-derived historical fields whose model/vintage semantics cannot be proven PIT-safe, or derive deterministic local features from contemporaneously observable text/metadata;
- inspect **no target outcomes** during that feasibility work;
- only after feasibility passes, freeze the finite hypothesis library, feature transforms, chronology, costs, multiplicity/dependence treatment, robustness gates, winner/finalist rules, and protected-read boundary.

Phase30 is still one project gate. Its feasibility, acquisition, development selection, internal validation, blindness audit, protected confirmation, independent validation, and closeout are internal work packages—not separate phases.

Phase30 historical provider reads may be authorized only as bounded data acquisition/provenance. Broker writes, order writes, PAPER submits, LIVE writes, automatic broker failover, and frontend trading authority remain disabled.

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

Preserve provider-native ticker case and PIT identity; quarantine ambiguity; do not synthesize unavailable history; finalized facts outrank provisional state; ML/AI do not create trade authority; research ideas are hypotheses; uncertain mutation state requires reconciliation; UI never creates/bypasses authority; no automatic broker failover; PAPER does not imply LIVE; negative research is accepted rather than manipulated; LIVE authority exists only after a separately accepted activation phase.
