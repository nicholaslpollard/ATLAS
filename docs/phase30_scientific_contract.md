# Phase 30 — Frozen Scientific Contract: Metadata-Only Public-News Shock Confirmation

**Status:** FROZEN BEFORE ANY PHASE30 MARKET-OUTCOME READ.

**Scientific policy fingerprint:** computed by `packages/backtesting/phase30_policy.py`.

**Source feasibility:** Phase30 historical-news feasibility fingerprint
`04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312` passed on the authorized target machine with all four historical boundary windows readable, 1,219 total/ticker-linked articles, and zero target/protected outcome reads.

## Why this contract exists

Phase30 changes the information source rather than retuning the price-derived failures from Phases 26–29. The feasibility gate proved that Massive historical news can be read with exact publication timestamps and ticker linkage across the required research/protected boundaries.

It did **not** prove historical revision/vintage semantics for article title/description text or provider-generated sentiment/insights. A current historical API response may contain the provider's present representation of an old article. Without a revision history or model-vintage guarantee, retrospective NLP could accidentally use information that was not exactly available at publication time.

Therefore Phase30 deliberately freezes a **metadata-only** public-information mechanism:

- authorized news alpha fields: `id`, `published_utc`, `tickers`;
- article title, description, publisher metadata, keywords, URLs, images, authors, and all provider `insights` remain raw provenance only;
- no provider content or provider model output may affect ranking, candidate selection, or support.

This is stricter than merely having historical news data and closes a potential vintage-leakage path before any outcome inspection.

## Economic mechanism

The test asks whether **unusually intense public-information arrival**, combined with the market's already-observed same-session reaction, adds confirmation value to ATLAS's existing production-path directional candidate.

The mechanism is motivated by established evidence that stock-price behavior differs when large moves coincide with identifiable public news, and by evidence of underreaction/overreaction around public information. Wesley Chan (Journal of Financial Economics, 2003, DOI `10.1016/S0304-405X(03)00146-6`) reports post-news drift and a distinction between news-associated and no-news price moves. Paul Tetlock and coauthors document delayed incorporation of firm-specific news information (Journal of Finance, 2008, DOI `10.1111/j.1540-6261.2008.01362.x`). Tetlock (Review of Financial Studies, 2011, DOI `10.1093/rfs/hhq141`) separately documents reversal when investors react to stale information.

Phase30 is **not** a replication of any of those papers. They motivate a finite preregistered question: when a production candidate experiences an unusual burst of ticker-linked public news, does an aligned market reaction continue, or does an opposing reaction reverse back toward the pre-existing production thesis?

## Frozen lineage and chronology

- source Phase29 merge: `87c9450e1b21606b83489f16ff326235ae92eb2b`;
- research start: `2021-08-16`;
- development end: `2026-05-06`;
- outer purge dates: `2026-05-07`, `2026-05-08`, `2026-05-11`;
- protected start: `2026-05-12`;
- protected end: `2026-08-11`;
- outcome horizon: exact `t+3` directional return;
- news warmup begins `2021-07-16`, which is sufficient to populate the frozen 20-session trailing news baseline before the first research session;
- Phase26 production-path-native observations remain the focal candidate lineage;
- protected predictors may be constructed, but protected returns remain unread unless and until frozen finalists exist and the independent blindness audit passes.

## Frozen article-to-session timing

A news item is assigned to the **first XNYS session whose official regular-session close is at least 30 minutes after publication**.

This dynamic exchange-calendar rule is used instead of a hard-coded 4:00 PM cutoff, so shortened sessions are handled correctly.

Consequences:

- premarket and earlier same-session news can belong to the current session;
- news too close to the official close is deferred to the next session;
- after-hours/weekend/holiday news is deferred to the next eligible session;
- the 30-minute buffer is fixed before outcome inspection.

## Frozen news-shock feature

For each exact provider-native ticker and effective XNYS session:

1. count unique article IDs assigned to that ticker/session;
2. zero-fill the ticker's previous 20 XNYS sessions;
3. compute:

`news_surprise = log1p(current_unique_article_count) - mean(log1p(previous_20_session_counts_with_zeros))`

Requirements:

- current article count must be at least 1;
- the full previous 20 exchange sessions must be available;
- ticker matching is exact; no uppercasing, alias remapping, current-universe projection, or survivorship repair is allowed;
- duplicate article IDs are not double counted;
- all counts use only publication timestamps available by the frozen decision time.

The finalized Phase26 field `d1_return_1` is the only current-session market-reaction field used by this hypothesis family. It is observation-time information, not a future outcome.

## Exactly four frozen hypotheses

The global scientific family contains **exactly four** hypotheses.

1. `news_shock_aligned_continuation_long`
   - focal Phase26 direction = `LONG`;
   - finalized `d1_return_1 > 0`;
   - larger `news_surprise` is stronger;
   - thesis: unusual public-news arrival plus an aligned positive session reaction continues in the pre-existing LONG direction.

2. `news_shock_aligned_continuation_short`
   - focal Phase26 direction = `SHORT`;
   - finalized `d1_return_1 < 0`;
   - larger `news_surprise` is stronger;
   - thesis: unusual public-news arrival plus an aligned negative session reaction continues in the pre-existing SHORT direction.

3. `news_shock_counterreaction_reversal_long`
   - focal Phase26 direction = `LONG`;
   - finalized `d1_return_1 < 0`;
   - larger `news_surprise` is stronger;
   - thesis: an unusual news burst produced an opposing negative reaction that subsequently reverses toward the pre-existing LONG thesis.

4. `news_shock_counterreaction_reversal_short`
   - focal Phase26 direction = `SHORT`;
   - finalized `d1_return_1 > 0`;
   - larger `news_surprise` is stronger;
   - thesis: an unusual news burst produced an opposing positive reaction that subsequently reverses toward the pre-existing SHORT thesis.

A zero current-session return satisfies neither sign and is excluded.

No fifth hypothesis, alternate text signal, provider-sentiment version, alternate lookback, alternate event-time cutoff, or runner-up substitution may be introduced after performance is observed.

## Frozen signal selection

- same-session/direction minimum eligible rows: 5;
- rank candidate score within the exact same session/direction;
- select the fixed top 20% tail by `news_surprise`;
- deterministic tie handling must be documented in implementation and may not use outcomes;
- no threshold search is authorized.

## Frozen costs and outcome

- outcome: exact focal-stock `t+3` directional return in the Phase26 candidate direction;
- primary cost: 10 bps;
- stress cost: 25 bps;
- diagnostic cost grid: 0 / 5 / 10 / 25 / 50 bps;
- costs are applied exactly as in the prior accepted alpha gates;
- median return and win rate are diagnostics, not hard gates.

## Frozen development / internal / protected design

- chronological development split: first 75% selection / remaining internal validation;
- exact 3-session purge between selection and internal validation;
- selection folds: 6;
- internal-validation folds: 3;
- protected folds: 3;
- no protected outcome may be read to tune any setting.

Minimum evidence:

- selection: 750 raw rows, 250 signal sessions, at least 5/6 positive folds;
- internal validation: 250 raw rows, 80 signal sessions, at least 2/3 positive folds;
- protected confirmation: 75 raw rows, 24 signal sessions, at least 2/3 positive folds.

## Frozen inference and robustness

- moving/block bootstrap block length: 6 sessions;
- bootstrap replicates: 2,000;
- seed: `300230`;
- selection confidence: 95%;
- internal confidence: 90%;
- protected confidence: 80%;
- global multiple-testing correction: Holm-Bonferroni across exactly 4 hypotheses at family alpha 0.05;
- positive-year fraction >= 60% where year evidence has at least 20 signal sessions;
- positive-regime fraction >= 50% where regime evidence has at least 20 signal sessions;
- maximum single-session row fraction: 10%;
- maximum single-ticker row fraction: 10%;
- deflated-performance diagnostic required;
- at most one winner/finalist per direction;
- runner-up substitution: forbidden.

A candidate cannot be promoted merely because its point estimate is positive. It must satisfy the complete frozen selection/internal/protected evidence chain.

## Protected holdout

The inherited `2026-05-12` through `2026-08-11` holdout remains outcome-unopened at this scientific freeze.

Before any protected return read:

1. development selection must complete;
2. internal validation must complete;
3. finalists must be frozen;
4. an independent blindness audit must confirm no protected performance has been inspected;
5. an immutable finalist-only protected read plan must be persisted.

If there are zero finalists, protected returns remain unread and the holdout remains unconsumed.

Any nonempty Phase30 protected-return read consumes the inherited holdout for subsequent alpha selection.

## Full historical news acquisition

After this scientific freeze, the next non-performance step is a resumable immutable acquisition of Massive news from:

- `2021-07-16T00:00:00Z`
- through `2026-08-11T23:59:59.999999Z`.

Acquisition is sharded by calendar month and reuses the accepted `MassiveRESTClient -> /v2/reference/news` path. Raw provider objects are retained for provenance, but only the three authorized metadata fields may affect alpha.

The acquisition itself reads **zero** market outcomes.

## Authority

Allowed now:

- read-only Massive historical news acquisition;
- immutable local raw-news/provenance writes;
- deterministic predictor-only news-shock construction from frozen metadata and already-PIT-safe Phase26 observation-time fields.

Still forbidden now:

- protected return reads before finalist/blindness gates;
- post-result hypothesis/threshold changes;
- provider writes;
- broker reads/writes;
- order writes;
- PAPER submits;
- LIVE writes;
- automation writes;
- automatic broker failover.

A positive Phase30 closeout grants historical analytical `SUPPORTED` authority only and unlocks the next signal-to-trade phase. It does not grant PAPER or LIVE authority.
