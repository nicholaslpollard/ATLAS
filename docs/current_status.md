# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after Phase30 predictor-only target PASS; development-only selection implementation is frozen before its first performance read.**

Read `docs/roadmap.md` first. It remains the normative mission/anti-drift/remaining-phase source of truth. Then read `docs/phase30_event_driven_public_information_alpha.md`, `docs/phase30_scientific_contract.md`, and this file. `docs/future_news_sentiment_and_option_fair_value.md` records explicit Phase31+ requirements and does not alter Phase30.

## Repository / authority state

- Accepted project foundation: **through Phase29**.
- Phase26 PR #30 merge `2074808605cf85b5462e5999ed1836d68b0434c3`: `ACCEPTED_NEGATIVE`.
- Phase27 PR #31 merge `dc015f51232dc66ba94b6175c276a0227d5a3761`: `ACCEPTED_NEGATIVE`.
- Phase28 PR #32 merge `285f112d51463dd1e06ea4e874a882ad98f71dc5`: `ACCEPTED_NEGATIVE`.
- Phase29 PR #33 merge `87c9450e1b21606b83489f16ff326235ae92eb2b`: `ACCEPTED_NEGATIVE`.
- Phase29 post-merge workflow `33124971664`: Ubuntu PASS / Windows PASS.
- Active phase: **Phase30 — Event-Driven Public-Information Alpha**.
- Active branch: `phase-30-event-driven-public-information-alpha`.
- Phase31 remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Mission / anti-drift lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

A failed check must be traced to the owning layer. Never weaken a validator, threshold, chronology rule, multiplicity rule, protected boundary, or authority rule to obtain PASS. Legitimate negative research is accepted. Provider-native ticker text/case and PIT identity are preserved; ambiguity fails closed. ML/AI do not independently create trade authority. PAPER does not imply LIVE.

## Accepted strategy / modern alpha evidence

Phase11 authority remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Modern alpha research:

- Phase26 self-feature/composite: 21,483 development observations, 1,096 protected predictors, zero survivors/finalists/support, zero protected returns — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional ranking: 18,111 development rows, 920 protected predictors, zero survivors/winners/finalists/support, zero protected reads — `ACCEPTED_NEGATIVE`.
- Phase28 lead-lag/residual network: 14,466 development rows, 741 protected predictors, zero survivors/winners/finalists/support, zero protected reads — `ACCEPTED_NEGATIVE`.
- Phase29 relative value/stat-arb: 14,523 development rows, 745 protected predictors, zero survivors/winners/finalists/support, zero protected reads, holdout unconsumed, independent/anti-workaround PASS — `ACCEPTED_NEGATIVE`.

These failed research families may not be retuned after observing their results.

## Phase30 frozen scientific contract

Policy fingerprint:

`341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8`

Only these news fields have Phase30 alpha authority:

- `id`;
- `published_utc`;
- exact provider-native `tickers`.

Article text/content, provider sentiment, and provider `insights` are raw provenance only because historical revision/model-vintage semantics were not proven. They cannot be introduced into Phase30 after the freeze.

Frozen dates / signal rules:

- news warmup start: `2021-07-16`;
- research start: `2021-08-16`;
- development end: `2026-05-06`;
- outer purge: `2026-05-07`, `2026-05-08`, `2026-05-11`;
- protected: `2026-05-12` through `2026-08-11`;
- first XNYS session whose official close is >=30 minutes after publication;
- 20 previous XNYS sessions, including zero-news sessions;
- `news_surprise = log1p(current_unique_article_count) - mean(log1p(previous_20_session_counts_with_zeros))`;
- current reaction field: accepted PIT-safe Phase26 `d1_return_1`;
- exact focal-stock outcome: `t+3` directional return;
- minimum 5 eligible rows in the exact session/direction;
- fixed top 20% news-surprise tail within exact session/direction;
- implementation tie-break: `news_surprise DESC, instrument_id ASC`, never outcomes;
- reaction-sign partition occurs **after** the fixed direction tail is determined;
- costs 0/5/10/25/50 bps; primary 10 bps; stress 25 bps;
- first 75% of frozen development sessions = selection, then exact 3-session purge, then internal validation;
- folds 6 selection / 3 internal / 3 protected;
- block bootstrap 6 sessions / 2,000 reps / seed `300230`;
- confidence 95% selection / 90% internal / 80% protected;
- selection minimum 750 rows / 250 signal sessions / >=5 of 6 positive folds;
- internal minimum 250 / 80 / >=2 of 3;
- protected minimum 75 / 24 / >=2 of 3;
- positive-year fraction >=60% with >=20 signal sessions;
- positive-regime fraction >=50% with >=20 signal sessions;
- maximum single-session row concentration 10%;
- maximum single-ticker row concentration 10%;
- global Holm-Bonferroni family exactly 4 at alpha .05;
- at most one winner/finalist per direction;
- runner-up substitution forbidden;
- win rate/median diagnostics only;
- deflated-performance diagnostic required;
- protected performance finalist-only.

Exactly four hypotheses:

1. `news_shock_aligned_continuation_long` — LONG + `d1_return_1 > 0`;
2. `news_shock_aligned_continuation_short` — SHORT + `d1_return_1 < 0`;
3. `news_shock_counterreaction_reversal_long` — LONG + `d1_return_1 < 0`;
4. `news_shock_counterreaction_reversal_short` — SHORT + `d1_return_1 > 0`.

No fifth hypothesis, alternate text/sentiment signal, alternate lookback, alternate event cutoff, threshold search, or runner-up substitution is permitted after performance is observed.

## Phase30 completed internal evidence

### Historical news feasibility — PASS

Fingerprint:
`04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312`

Boundary probes: 1,219 articles / 1,219 ticker-linked / 4 successful provider pages. Target outcome rows 0; protected returns 0; external mutation zero.

### Full historical news acquisition — PASS

Target run on head `65208611b1f441a667bd95e8ed7a740ab42c6e79`:

- 775,164 articles;
- 775,164 ticker-linked articles;
- 62 immutable/resumable monthly shards;
- 804 successful provider pages;
- first complete run resumed 0 shards;
- target outcome rows 0;
- protected returns 0;
- provider/broker/order/PAPER/LIVE mutations zero.

The four frozen feasibility boundary snapshots were reconciled against the full acquisition on alpha-authorized metadata.

### Predictor-only metadata news shocks — PASS

Target run on exact head `58c846ba04b8e769c7dbb356c42c945e23de3d76`:

- articles scanned: **775,164**;
- ticker links scanned: **1,917,356**;
- development predictor rows/tickers: **1,012,022 / 16,749**;
- protected predictor rows/tickers: **23,183 / 4,828**;
- source shards: **62**;
- source-lineage SHA256: `557d34878c394bc626235ef4dd76604ba8eb6fab67ec0aeea43b26399ff88d00`;
- development SHA256: `2ef164e06768f5ba90f78cfcce6c5d2406de306496be766a110cf752843073dd`;
- protected SHA256: `84166de8961665b376a61ca0e9164d6eef224b0d34bdc741bdfa2b6a7e5e91df`;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- provider reads/writes / broker reads/writes / orders / PAPER / LIVE: **0 / 0 / 0 / 0 / 0 / 0 / 0**;
- result: **PASS**.

This stage used the accepted XNYS calendar authority, including shortened closes, exact ticker case, and only the three authorized metadata fields. It created no alpha/support/trading authority.

## Phase30 next scientific boundary — development-only study

`packages/backtesting/phase30_development.py` is the first Phase30 stage authorized to inspect target performance. It is deliberately limited to the already accepted **Phase26 development observation artifact** and the Phase30 **development news-shock artifact**.

It must:

1. verify both source reports and SHA256 lineage;
2. verify Phase26 and Phase30 protected-return-read counters are still zero;
3. exact-join only on `ticker` (case-preserving) + session date;
4. reuse Phase26's already accepted exact `t+3` development outcome rather than recompute prices/returns;
5. determine the top 20% tail inside each exact session/direction before applying the frozen positive/negative reaction split;
6. use deterministic `news_surprise DESC, instrument_id ASC` tie handling;
7. execute the frozen selection statistics and global four-hypothesis Holm family;
8. choose at most one selection winner per LONG/SHORT direction;
9. run internal validation only for selection winners; runner-up substitution remains forbidden;
10. freeze zero, one, or two finalists;
11. read **zero protected candidate rows and zero protected returns**.

The development run is scientifically consequential because it is the first Phase30 performance inspection. Its code/policy/validator must therefore be cross-platform green before target execution.

If there are zero finalists, Phase30 proceeds to independent reconstruction/negative closeout without opening protected returns. If there are finalists, the next step is an independent blindness audit plus immutable finalist-only protected-read plan; protected returns are still not read until those gates pass.

## Protected-holdout state

Master protected window: `2026-05-12` through `2026-08-11`.

Phases26–29 and all completed Phase30 feasibility/acquisition/predictor work have read **zero protected returns**. The holdout remains genuinely outcome-unopened and unconsumed.

Any nonempty future Phase30 protected-return read is allowed only after development selection, internal validation, frozen finalists, an independent blindness audit, and an immutable finalist-only read plan. That read consumes this inherited holdout for subsequent alpha selection.

## Future news sentiment / options fair-value requirements

`docs/future_news_sentiment_and_option_fair_value.md` is an explicit Phase31+ design lock and does not modify Phase30.

- News sentiment defaults to **Supporting Evidence**. Credible contradictory news must trigger asymmetric confidence/profitability reduction or thesis re-evaluation; severe thesis-invalidating event classes use a dedicated event-risk gate and can force PASS/no-trade. Material post-entry news triggers a position/risk re-evaluation without rewriting the original signal.
- Phase31 option selection must include an explicit **Option Fair-Value Engine**. Black-Scholes-Merton is a reference, not sole authority; IV surface/skew/term structure, independently estimated volatility/fair value, realized/forecast/event volatility, rates/dividends, executable pricing/liquidity, Greeks, and American-style pricing where early exercise matters are incorporated as applicable.
- Planned modes: `Off`, `Rank Boost` (default), `Require Positive Valuation Edge`.

## Remaining roadmap

- Phase30: Event-Driven Public-Information Alpha.
- Phase31: Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — requires supported alpha.
- Phase32: End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- Phase33: Prospective SHADOW/PAPER Certification + Operator Web Beta.
- Phase34: Outcomes/Learning/Drift/Governance + Performance UI.
- Phase35: Production Web App/Operations/Deployment.
- Phase36: LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- Phase37: Controlled LIVE Activation & Evidence-Based Scaling.

The roadmap is conditional. A negative Phase30 result is valid science but does not satisfy Phase31's positive entry condition.
