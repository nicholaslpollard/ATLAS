# Phase 30 — Event-Driven Public-Information Alpha

**Status:** DEVELOPMENT RESULT NEGATIVE; independent negative closeout pending target PASS. Protected returns remain unread.

**Source foundation:** Phase29 merge `87c9450e1b21606b83489f16ff326235ae92eb2b` (`ACCEPTED_NEGATIVE`).

## Plain-English purpose

Phase30 deliberately changed the information mechanism after four price-derived modern-alpha families failed. It tested whether timestamped public company news-arrival intensity, combined with the already point-in-time-safe Phase26 same-session reaction field, added repeatable directional value after realistic costs.

The experiment is now frozen and has been run on development outcomes. It produced zero selection survivors, zero winners, and zero finalists. The correct remaining work is independent negative reconstruction and full phase-end closeout without opening protected returns.

## Frozen scientific contract

Policy fingerprint:

`341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8`

Only the following news fields have Phase30 alpha authority:

- `id`;
- `published_utc`;
- exact provider-native `tickers`.

Historical title/description/content, provider sentiment, and provider insights remain provenance only. Their historical revision/model-vintage semantics were not proven before the freeze, so they may not be introduced after observing Phase30 performance.

Frozen chronology and signal rules:

- news warmup start `2021-07-16`;
- research start `2021-08-16`;
- development end `2026-05-06`;
- outer purge `2026-05-07`, `2026-05-08`, `2026-05-11`;
- protected window `2026-05-12` through `2026-08-11`;
- article maps to first XNYS session whose official regular close is at least 30 minutes after publication;
- news shock uses current unique-article count versus the prior 20 XNYS sessions with zero-news sessions included;
- reaction field is accepted Phase26 `d1_return_1`;
- outcome is exact `t+3` directional return from the accepted Phase26 development observation artifact;
- at least five exact session/direction rows are required before ranking;
- signal is fixed top 20% by `news_surprise` within exact session/direction;
- deterministic tie-break `news_surprise DESC, instrument_id ASC`;
- positive/negative reaction split occurs only after the direction tail is determined;
- primary cost 10 bps; stress cost 25 bps;
- chronological 75% selection, exact three-session purge, then internal validation;
- selection minimum 750 raw rows / 250 signal sessions / >=5 of 6 positive folds;
- internal minimum 250 / 80 / >=2 of 3;
- protected minimum 75 / 24 / >=2 of 3;
- global Holm-Bonferroni across exactly four hypotheses at alpha .05;
- maximum one winner/finalist per direction;
- runner-up substitution forbidden;
- protected returns finalist-only.

Exactly four hypotheses were frozen before performance inspection:

1. `news_shock_aligned_continuation_long` — LONG + `d1_return_1 > 0`;
2. `news_shock_aligned_continuation_short` — SHORT + `d1_return_1 < 0`;
3. `news_shock_counterreaction_reversal_long` — LONG + `d1_return_1 < 0`;
4. `news_shock_counterreaction_reversal_short` — SHORT + `d1_return_1 > 0`.

No fifth hypothesis, alternate text/sentiment signal, alternate lookback, alternate event cutoff, cost change, threshold search, or runner-up substitution is allowed after observing the result.

## Evidence completed

### Historical-news feasibility — PASS

The accepted Massive REST path `/v2/reference/news` was proven on four frozen boundary windows with exact publication timestamps, ticker linkage, deterministic pagination/evidence hashing, and zero market-outcome/protected reads.

Feasibility fingerprint:

`04d31c5687c8da2892d017692b26ad930eff6af19f54a55294509e50d97bd312`

### Full historical acquisition — PASS

- 775,164 articles;
- 62 immutable/resumable monthly shards;
- 804 successful provider pages;
- all four feasibility snapshots reconciled against the full acquisition on the authorized metadata fields;
- target outcomes 0; protected returns 0; external mutation 0.

### Predictor-only construction — PASS

Target head `58c846ba04b8e769c7dbb356c42c945e23de3d76`:

- 775,164 articles scanned;
- 1,917,356 ticker links scanned;
- 1,012,022 development predictor rows / 16,749 tickers;
- 23,183 protected predictor rows / 4,828 tickers;
- target outcome rows 0;
- protected return rows 0;
- external activity 0.

The protected predictor artifact contains only metadata-derived news shocks; it does not contain protected market outcomes.

### Development-only study — PASS / NEGATIVE

Target head `34ebbca0d2a94cd4637987b0591707f30980d133`:

- joined development population: 3,057 rows / 1,736 tickers / 953 sessions;
- selection `2021-08-16..2025-02-28`;
- purge `2025-03-03`, `2025-03-04`, `2025-03-05`;
- internal `2025-03-06..2026-05-06`;
- protected candidate rows read 0;
- protected return rows read 0;
- holdout consumed false.

Frozen selection results:

- aligned continuation LONG: 171 rows / 112 sessions, primary mean after 10 bps `-0.05516706`;
- aligned continuation SHORT: 8 / 6, primary mean `-0.01477761`;
- counterreaction reversal LONG: 30 / 28, primary mean `0.07203060`, 95% LCB `0.00857746`, raw bootstrap p `0.04347826`, but Holm reject false and mandatory sample/year/regime gates failed;
- counterreaction reversal SHORT: 1 / 1, primary mean `-0.01977370`.

Selection survivors `[]`; selection winners `[]`; internal-validation candidates none; frozen finalists `[]`.

The reversal-LONG diagnostic is not support. Its 30 rows / 28 sessions are far below the preregistered 750 / 250 selection minimum and it failed multiplicity/robustness gates. It may not be retuned or promoted after the fact.

## Independent negative closeout

The closeout path now consists of:

- `packages/backtesting/phase30_validation.py`;
- `packages/backtesting/phase30_closeout.py`;
- `scripts/run_phase30_closeout.py`;
- `scripts/validate_phase30_closeout.py`;
- `tests/unit/test_phase30_validation.py`;
- `tests/unit/test_phase30_closeout.py`;
- `docs/phase30_end_to_end_anti_workaround_audit.md`.

The independent validator does not import `phase30_development.py`. It reconstructs the exact source join directly from the accepted Phase26 development observation artifact plus immutable Phase30 development predictor artifact and independently applies the frozen tail-before-reaction logic.

For the negative conclusion, the decisive independent proof is the mandatory sample gate: every independently reconstructed candidate is below at least one frozen selection minimum (`750` rows / `250` sessions). The validator also reconciles raw-row count, signal-session count, and primary 10-bps mean return against the target development report.

If this independent target reconstruction and full closeout pass, Phase30 disposition is `ACCEPTED_NEGATIVE`. Protected returns remain unopened and the inherited holdout remains unconsumed. Phase31 remains blocked because supported alpha is still zero.

## Future news work is separate

`docs/future_news_sentiment_and_option_fair_value.md` records future sentiment and Alpaca/Benzinga research requirements. They do not alter or rescue Phase30. Historical text from any provider requires proven point-in-time revision semantics before leakage-sensitive alpha authority; prospective real-time capture is the preferred future vintage-safe path.

## Authority

During closeout:

- local development evidence reads: allowed;
- protected predictor metadata existence: allowed;
- protected candidate outcome reads: **FORBIDDEN**;
- protected return reads: **FORBIDDEN**;
- provider writes: 0;
- broker reads/writes: 0;
- order writes: 0;
- PAPER submits: 0;
- LIVE writes: 0;
- automation writes: 0;
- automatic broker failover: disabled;
- frontend trading authority: none.

A negative Phase30 closeout grants no alpha, PAPER, or LIVE authority and does not satisfy Phase31's supported-alpha entry condition.
