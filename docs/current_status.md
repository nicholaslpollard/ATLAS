# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after the Phase30 development-only target run returned zero survivors/winners/finalists; independent negative closeout is implemented and awaiting its target run.**

Read `docs/roadmap.md` first. It remains the normative mission/anti-drift/remaining-phase authority. Then read `docs/phase30_event_driven_public_information_alpha.md`, `docs/phase30_scientific_contract.md`, `docs/phase30_end_to_end_anti_workaround_audit.md`, and this file. `docs/future_news_sentiment_and_option_fair_value.md` records downstream news-sentiment, Alpaca/Benzinga, and option fair-value requirements and does not alter Phase30.

## Repository / authority state

- Accepted project foundation: **through Phase29**.
- Phase26 PR #30 merge `2074808605cf85b5462e5999ed1836d68b0434c3`: `ACCEPTED_NEGATIVE`.
- Phase27 PR #31 merge `dc015f51232dc66ba94b6175c276a0227d5a3761`: `ACCEPTED_NEGATIVE`.
- Phase28 PR #32 merge `285f112d51463dd1e06ea4e874a882ad98f71dc5`: `ACCEPTED_NEGATIVE`.
- Phase29 PR #33 merge `87c9450e1b21606b83489f16ff326235ae92eb2b`: `ACCEPTED_NEGATIVE`.
- Active phase: **Phase30 — Event-Driven Public-Information Alpha**.
- Active branch: `phase-30-event-driven-public-information-alpha`.
- Phase30 target development evidence is negative; formal phase-end closeout is not accepted until `scripts/run_phase30_closeout.py` passes on the target machine.
- Phase31 remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Mission / anti-drift lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference -> Parquet/DuckDB -> features -> broad discovery -> regimes -> ML probability evidence -> deterministic strategy/alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

Never weaken a validator, threshold, chronology rule, multiplicity rule, protected boundary, identity rule, or authority rule to obtain PASS. Legitimate negative research is accepted. Provider-native ticker text/case and PIT identity are preserved. ML/AI do not independently create trade authority. PAPER does not imply LIVE.

## Accepted alpha evidence before Phase30

Phase11 authority remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Modern alpha research:

- Phase26 deterministic/composite self-feature: 21,483 development observations; zero survivors/finalists/support; zero protected returns — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional ranking: 18,111 development rows; zero survivors/winners/finalists/support; zero protected reads — `ACCEPTED_NEGATIVE`.
- Phase28 lead-lag/residual network: 14,466 development rows; zero survivors/winners/finalists/support; zero protected reads — `ACCEPTED_NEGATIVE`.
- Phase29 relative-value/stat-arb: 14,523 development rows; zero survivors/winners/finalists/support; zero protected reads; independent/anti-workaround PASS — `ACCEPTED_NEGATIVE`.

These failed families may not be retuned after observing their results.

## Phase30 frozen scientific contract

Policy fingerprint:

`341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8`

Only `id`, `published_utc`, and exact provider-native `tickers` have Phase30 news alpha authority. Article text/content, provider sentiment, and provider insights remain provenance only because historical revision/model-vintage semantics were not proven before the freeze.

Key frozen rules:

- news warmup `2021-07-16`; research start `2021-08-16`; development end `2026-05-06`;
- outer purge `2026-05-07`, `2026-05-08`, `2026-05-11`;
- protected window `2026-05-12` through `2026-08-11`;
- assign an article to the first XNYS session whose official close is >=30 minutes after publication;
- 20-session zero-filled news baseline;
- `news_surprise = log1p(current_unique_article_count) - mean(log1p(previous_20_session_counts_with_zeros))`;
- reaction field `d1_return_1`;
- outcome horizon exact `t+3` directional return;
- minimum five same-session/direction candidate rows;
- fixed top 20% news-surprise tail inside exact session/direction;
- tie-break `news_surprise DESC, instrument_id ASC`;
- reaction-sign split occurs **after** tail selection;
- primary cost 10 bps; stress cost 25 bps;
- chronological 75% selection / 3-session purge / internal validation remainder;
- selection minimum 750 raw rows / 250 signal sessions / >=5 of 6 positive folds;
- internal minimum 250 / 80 / >=2 of 3;
- protected minimum 75 / 24 / >=2 of 3;
- global Holm-Bonferroni across exactly four hypotheses at alpha .05;
- at most one winner/finalist per direction;
- runner-up substitution forbidden;
- protected performance finalist-only.

Exactly four frozen hypotheses:

1. `news_shock_aligned_continuation_long` — LONG + positive `d1_return_1`;
2. `news_shock_aligned_continuation_short` — SHORT + negative `d1_return_1`;
3. `news_shock_counterreaction_reversal_long` — LONG + negative `d1_return_1`;
4. `news_shock_counterreaction_reversal_short` — SHORT + positive `d1_return_1`.

No post-result text/sentiment variant, lookback change, event cutoff change, threshold search, fifth hypothesis, or runner-up substitution is allowed.

## Phase30 completed target evidence

### Historical-news feasibility — PASS

Fingerprint `04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312`.

Four frozen boundary probes returned 1,219 articles / 1,219 ticker-linked articles / four provider pages. Target outcomes and protected returns remained zero.

### Full Massive historical-news acquisition — PASS

- 775,164 articles;
- 62 immutable/resumable monthly shards;
- 804 successful provider pages;
- full acquisition reconciled the four feasibility snapshots on alpha-authorized metadata;
- target outcomes 0; protected returns 0; external mutation 0.

### Predictor-only metadata news shocks — PASS

Target head `58c846ba04b8e769c7dbb356c42c945e23de3d76`:

- articles scanned: **775,164**;
- ticker links scanned: **1,917,356**;
- development predictor rows/tickers: **1,012,022 / 16,749**;
- protected predictor rows/tickers: **23,183 / 4,828**;
- source-lineage SHA256 `557d34878c394bc626235ef4dd76604ba8eb6fab67ec0aeea43b26399ff88d00`;
- development SHA256 `2ef164e06768f5ba90f78cfcce6c5d2406de306496be766a110cf752843073dd`;
- protected SHA256 `84166de8961665b376a61ca0e9164d6eef224b0d34bdc741bdfa2b6a7e5e91df`;
- target outcomes 0; protected returns 0; external activity 0.

### Development-only selection + internal validation — PASS / NEGATIVE

Target run on exact head `34ebbca0d2a94cd4637987b0591707f30980d133`:

- exact joined development population: **3,057 rows / 1,736 tickers / 953 sessions**;
- selection interval `2021-08-16..2025-02-28`;
- purge `2025-03-03`, `2025-03-04`, `2025-03-05`;
- internal interval `2025-03-06..2026-05-06`;
- development target rows read: **3,057**;
- protected candidate rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **False**.

Frozen selection results:

- `news_shock_aligned_continuation_long`: **171 rows / 112 sessions**, mean10 `-0.05516706`, LCB `-0.08436764`, Holm reject false.
- `news_shock_aligned_continuation_short`: **8 / 6**, mean10 `-0.01477761`, Holm reject false.
- `news_shock_counterreaction_reversal_long`: **30 / 28**, mean10 `0.07203060`, LCB `0.00857746`, raw bootstrap p `0.04347826`, but Holm reject false and mandatory sample/year/regime gates fail.
- `news_shock_counterreaction_reversal_short`: **1 / 1**, mean10 `-0.01977370`, Holm reject false.

Selection survivors: `[]`.
Selection winners: `[]`.
Internal-validation candidates: none.
Frozen finalists: `[]`.

The positive reversal-long diagnostic is **not** authority and may not be chased or retuned: 30 rows / 28 sessions is far below the frozen 750 / 250 selection minimum and it also failed multiplicity/robustness gates.

## Phase30 current boundary — independent negative closeout

Implemented after the target development result:

- `packages/backtesting/phase30_validation.py`
- `packages/backtesting/phase30_closeout.py`
- `scripts/run_phase30_closeout.py`
- `scripts/validate_phase30_closeout.py`
- `tests/unit/test_phase30_validation.py`
- `tests/unit/test_phase30_closeout.py`
- `docs/phase30_end_to_end_anti_workaround_audit.md`

The independent validator does **not** import `phase30_development.py`. It reconstructs the exact Phase26 + Phase30 development source join and independently applies the frozen direction/session eligibility, top-20% tail, deterministic tie-break, and reaction split. It reconciles raw rows, signal sessions, and primary 10-bps mean return.

The negative proof is intentionally minimal and decisive: every independently reconstructed hypothesis fails at least one mandatory frozen sample gate (`750` rows / `250` sessions), so no candidate can legally survive regardless of bootstrap inference. The closeout path reads no protected outcomes and creates no protected-confirmation/read-plan artifact.

Formal Phase30 disposition becomes `ACCEPTED_NEGATIVE` only after the target closeout run passes. That disposition keeps Phase31 blocked.

## Protected-holdout state

Master protected outcome window: `2026-05-12` through `2026-08-11`.

Phases26–29 and all Phase30 work completed so far have read **zero protected returns**. The predictor-only protected news artifact exists but contains no market outcomes. With zero Phase30 finalists, the correct path is to close Phase30 without ever opening protected returns. The inherited outcome holdout remains unopened and unconsumed.

## Future news sentiment / Alpaca / option fair-value requirements

`docs/future_news_sentiment_and_option_fair_value.md` is downstream-only and does not modify Phase30.

- News sentiment defaults to **Supporting Evidence** with asymmetric treatment of credible contradictory/thesis-invalidating news.
- Alpaca's historical Benzinga news API is recorded as a candidate independent source: documentation states history back to 2015 and exposes historical REST plus real-time WebSocket news. Current docs do not clearly publish a separate Basic-vs-paid news entitlement matrix, so actual ATLAS credential access must be proven with a read-only authenticated probe before dependency.
- Historical REST `created_at` / `updated_at` do not by themselves prove exact historical text vintage. Prospectively archiving the real-time news stream is the strongest future PIT-safe sentiment dataset path.
- Phase31 option selection must include the explicit Option Fair-Value Engine. BSM is a reference rather than sole authority; IV surface/skew/term structure, independent volatility/fair-value estimates, rates/dividends, executable pricing/liquidity, Greeks, and American-style pricing are incorporated where applicable.
- Planned fair-value modes: `Off`, `Rank Boost` (default), `Require Positive Valuation Edge`.

## Remaining roadmap

- Phase30: Event-Driven Public-Information Alpha — development result negative; independent closeout pending target PASS.
- Phase31: Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — **blocked until supported alpha exists**.
- Phase32: End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- Phase33: Prospective SHADOW/PAPER Certification + Operator Web Beta.
- Phase34: Outcomes/Learning/Drift/Governance + Performance UI.
- Phase35: Production Web App/Operations/Deployment.
- Phase36: LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- Phase37: Controlled LIVE Activation & Evidence-Based Scaling.

After a negative Phase30 closeout, the roadmap must be rebaselined to a genuinely different alpha-information mechanism before Phase31; Phase30 itself may not be retuned from its observed result.
