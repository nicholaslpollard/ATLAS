# ATLAS Master Roadmap and Research/Product Source of Truth

**Current as of 2026-09-08 (UTC). This roadmap and the root `README.md` are the
only living project documents.**

This document replaces the pre-Review roadmap after ATLAS Review Chat 3. It keeps
all valid evidence and safeguards while correcting the process drift that made
unsuccessful alpha research a global blocker for the product.

## 1. Document authority and continuation

Every continuation chat must read the root `README.md` and this roadmap in full
before recommending or changing anything. Update both in the same commit whenever
mission, current state, authority, roadmap order, active work, material evidence, or
implemented capability changes. Every repository-changing implementation package
must document its goal, capability change, result/test evidence, exact authority or
safety impact, unresolved limitations, and next work in both living documents before
it is accepted or merged. A future chat must be able to reconstruct the current
product and research state from these two files without depending on a prior chat.
Do not create another current-status, handoff, plan, roadmap, or living README.

All older README and roadmap files were moved verbatim to
`docs/archive/2026-09-02-pre-product-rebaseline/`. The old `docs/current_status.md`,
`docs/phase_flow.md`, and `docs/phase_plain_english_contract.md` remain only as
frozen compatibility snapshots for accepted historical validators; exact originals
are in the same archive. All other documentation is immutable specification,
research, incident, or acceptance evidence. It may be cited but must not silently
become a competing current plan.

If these two living documents conflict, progression fails closed until both are
reconciled. Code and tests remain the authority for actual behavior; Git history and
accepted artifacts remain the authority for what happened. A code package with
stale living documents is incomplete even if its tests pass.

## 2. Mission

ATLAS is the **Autonomous Trading, Learning, and Analysis System**, the greenfield
successor to Chart Monitor.

Its product mission is to become an operator-usable quantitative trading system
that can:

1. ingest and reconstruct trustworthy information point in time;
2. discover opportunities and identify current market, sector, ticker, volatility,
   liquidity, and event conditions;
3. evaluate multiple independently specified strategy families;
4. estimate probability, expected net return, downside, cost, and confidence;
5. select and construct appropriate stock or options trades;
6. size and admit them under portfolio risk constraints;
7. run historical replay and prospective PAPER without hindsight;
8. manage positions and exits;
9. record every decision, non-decision, execution, and outcome;
10. show the operator current state, evidence, performance, and controls; and
11. improve through versioned research without silently changing production.

The financial objective is positive expected value and account growth after
realistic costs while controlling drawdown, tail loss, concentration, execution
risk, and risk of ruin. Profit is never guaranteed. Trade frequency is not success.

## 3. Two parallel tracks

### Track A — ATLAS Product

Complete the operating system:

`market data → features → regimes → discovery → strategies → candidate promotion →
trade construction → portfolio/risk → AI review → operator-observable control plane
→ operational PAPER → outcomes → performance/learning → production operations`

Reference strategies may exercise every component. They must be visibly labeled
as baselines and may not gain qualifying-PAPER or LIVE authority merely because the
product works.

Operational PAPER is not allowed to begin as a black-box backend exercise. Before
A35 broker mutation starts, the operator must already have an accepted browser view
of the authoritative runtime state so candidate reasoning, positions, P&L, orders,
fills, exits, and system health can be watched as they change.

### Track B — ATLAS Strategy & Research Lab

Build and challenge the strategy library:

- practitioner indicator/setup strategies first;
- regime and condition evaluation;
- literature-anchored academic mechanisms next;
- event, SEC, options, news/NLP, cross-sectional, ML, and novel-source research
  when its expected information gain justifies the effort;
- continuous strategy degradation, improvement, and challenger research.

Track B failure does not block ordinary Track A product completion. Track A may not
misrepresent a baseline as supported alpha. Both tracks join only at the stronger
qualification gates for LIVE.

## 4. Locked architecture and roles

`market/reference/regulatory → Parquet analytical lake → DuckDB analytics →
versioned features → broad discovery → market/sector/ticker regimes → deterministic
strategy evaluation → optional ML probability evidence → authority gate →
opportunity ranking → stock/options construction → portfolio risk/sizing →
deterministic case → independent AI audit → SHADOW/PAPER execution → outcome ledger
→ walk-forward learning → API/browser control plane → production operations`

- **Parquet:** durable analytical/history lake.
- **DuckDB:** analytical and replay query engine.
- **PostgreSQL:** future operational state after its schema, migrations, recovery,
  concurrency, and ownership boundaries are accepted. Current files are scaffolds.
- **Massive:** primary broad-market/reference provider where entitlement and PIT
  semantics are proven. Current known plan: Stocks Starter.
- **Official SEC EDGAR/XBRL:** read-only regulatory provenance only within an
  explicitly authorized source contract.
- **Webull:** primary PAPER/sandbox and intended primary LIVE broker only after
  separate acceptance.
- **Alpaca:** explicit/manual secondary broker. No automatic broker failover.
- **ML:** predictive evidence and ranking, never standalone trading authority.
- **AI:** independent review/challenge, never unilateral trading authority.
- **Browser GUI:** operator surface over the same engine, never a second trading
  engine. It may format and aggregate authoritative records but must not maintain a
  separate trading truth or independently recompute trading decisions.

The decommissioned V1 daily lake used Alpaca SIP through `2021-08-13` and
Massive from `2021-08-16`; this is retained historical provenance only. The current
isolated V2 candidate base uses Alpaca SIP throughout its frozen source interval and
forbids V1 rows or derived-state ancestry. V2 minute semantics and the initial opening/premarket strategy pack are accepted by B34; missing history may not be invented, and performance remains separately gated.

## 5. Accepted foundation through Phase32

Phases1–25 accepted project/config/session foundations, provider ingestion,
canonical Parquet/DuckDB data, PIT identity/history, live market state,
deterministic features, universe/discovery/regime/ML/strategy routing,
promoted-only deeper research, news/options/instrument/geometry/portfolio-risk
planning, independent AI audit, broker-neutral SHADOW/PAPER primitives,
Webull-primary/Alpaca-manual-secondary operations, API/browser primitives,
restart-safe orchestration, centralized PAPER authority, and exact historical
production-path reconstruction.

Modern alpha phases remain:

- Phase26 deterministic/composite self-feature alpha — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional expected-return learning/ranking — `ACCEPTED_NEGATIVE`.
- Phase28 cross-stock lead-lag/residual network alpha — `ACCEPTED_NEGATIVE`.
- Phase29 relative-value statistical arbitrage — `ACCEPTED_NEGATIVE`.
- Phase30 public-news-arrival alpha — `ACCEPTED_NEGATIVE`.
- Phase31 SEC Form 4 insider transactions — `ACCEPTED_NEGATIVE`; merge
  `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 SEC 8-K material corporate events — `ACCEPTED_NEGATIVE`; PR #37 merge
  `69f8aa81289934b71f2652482c747391917c15a3`.

Phase32 policy fingerprint:
`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.
Exactly five hypotheses were frozen before performance. Its frozen finalist was
`solvency_distress_short`. Protected source-only evidence was **46 event rows / 33
signal sessions / 40 unique instruments** versus **50 / 20 / 20**. Protected
stock/SPY returns remain unread; holdout consumed is false.

Phase32's old immediate-successor rule required a **materially different
point-in-time fundamental-information mechanism**. The later XBRL branch satisfied
that historical change-of-mechanism requirement. Nothing here reopens Phase32.
Later work may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result.

Historical supported alpha remains **zero**. Historical supported modern alpha
remains **0**. This prevents any claim of historical validation or LIVE authority;
it no longer prevents Product work using explicit baselines.

## 6. Completed Pre-Phase33 SEC XBRL mechanism — `ACCEPTED_NEGATIVE`

Mechanism:
`PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY`.

- Phase32 source merge: `69f8aa81289934b71f2652482c747391917c15a3`;
- feasibility contract:
  `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`;
- feasibility state: `FEASIBILITY_PASS`;
- feasibility fingerprint:
  `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`;
- accepted feasibility evidence fingerprint:
  `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`;
- frozen PIT audit fingerprint:
  `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`;
- feasibility: 200 Company Facts documents, 170 accrual-history-ready issuers,
  92 profitability-history-ready issuers;
- original PIT failure preserved; common-stock active-only identity repair passed
  without changing source population or numeric gates;
- scientific fingerprint:
  `2602ca0e89c5af6c8272e5a6324474b66da9cc6c153974e5a32c35339a0f1490`;
- development: 0 selection passers, 0 winners, 0 internal finalists;
- protected return rows read: 0; holdout consumed: false;
- closeout fingerprint:
  `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91`;
- PR #38 merge: `083c0a5742b161cf4b7c04d5bf0246f3057f6c19`.

XBRL protected return rows read = **0**.

## 7. Completed Pre-Phase33 SEC Schedule 13D/13G beneficial ownership — `ACCEPTED_NEGATIVE`

Source-only feasibility mechanism:
`PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`.

Frozen feasibility fingerprint:
`f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`.

Those identifiers are retained historical source-gate lineage and accepted-
validator compatibility anchors; they are not the later scientific mechanism or
new Phase33 authority.

Mechanism:
`PIT_SEC_SCHEDULE_13D_13G_INITIAL_BENEFICIAL_OWNERSHIP_INTENT_AND_CONCENTRATION`.

- repaired source: 43/43 quarterly indexes, 200/200 complete submissions, 195
  unique subject CIKs, 200 decision sessions, 142 unambiguous PIT common-stock
  mappings;
- scientific fingerprint:
  `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c`;
- 3,652 predictors and 2,412 usable development outcomes;
- 0 selection passers, 0 winners, 0 internal finalists;
- protected return rows read: 0; holdout consumed: false;
- closeout fingerprint:
  `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`;
- PR #39 merge: `208529c5562920cc0b2bcf2bae546e2b9af0a25b`.

## 8. Other completed pre-Phase33 research

### FINRA consolidated short interest v1

Disposition: `ACCEPTED_NEGATIVE_PROTECTED_SOURCE_INSUFFICIENT`.

- mechanism:
  `PIT_FINRA_CONSOLIDATED_SHORT_INTEREST_POSITIONING_AND_CROWDING`;
- scientific fingerprint:
  `0b32d59677e86544777807525cd4aba13dd36fd0fcfd7744458556205561d13f`;
- 19,343 predictors = 14,841 DEVELOPMENT + 4,502 PROTECTED;
- the only frozen source-count failure was
  `rapid_short_cover_crowded_long`: 257 protected rows versus 300 required;
  sessions 26 versus 16 and instruments 211 versus 200 passed;
- development/target outcome rows read: 0; protected returns read: 0;
- closeout fingerprint:
  `bdd494a01ed23d891c460e353831cba6f9cf010c5bf38cf1c9c527b4abe8b565`.

This was a source-capacity result, not a return result. The four-hypothesis family,
sampling, buckets, chronology, multiplicity, costs, and protected rules remain
closed to post-result alteration.

### SEC diluted-EPS earnings innovation v1

Disposition: `ACCEPTED_NEGATIVE_PIT_SOURCE_INTEGRITY_FAILURE`.

- mechanism:
  `PIT_SEC_XBRL_DILUTED_EPS_SEASONAL_EARNINGS_INNOVATION_POST_PERIODIC_FILING_DRIFT`;
- feasibility produced 5,905 unique direct-quarter observations;
- PIT audit retained 5,896 observations from 5,902 candidates but found 3 ambiguous
  earliest period contexts and 6 accession/form/filing-date contradictions;
- a clean V2 replay matched all 300 Company Facts hashes and reproduced the SEC
  Submissions contradictions, proving an upstream source-semantics limitation rather
  than local corruption;
- diagnostic fingerprint:
  `399e7d0bece8088e63c4835566d276b51375a5031d81f4db4781675351a87961`;
- closeout fingerprint:
  `29e72b427aa63c6ae2e0c25917fad0c9c948f2a2cd97c0d51f390ecd343baacc`;
- development/protected outcome rows read: 0; holdout consumed: false.

### SEC Form 13F institutional positioning v1

Disposition: `ACCEPTED_NEGATIVE_SOURCE_INTEGRITY_FAILURE`.

- mechanism:
  `PIT_SEC_FORM13F_INSTITUTIONAL_POSITIONING_CHANGE_AND_CONSENSUS_ACCUMULATION`;
- 2016Q1 valid-nine-character-CUSIP fraction was 0.993405 versus frozen 0.995;
- 10,431 malformed holdings across 374 accessions;
- original EDGAR V2 reconciled 374/374 exact CUSIP multisets and reproduced all
  10,431 malformed values in original as-filed XML;
- the V1 archive locator 404 is preserved separately as
  `IMPLEMENTATION_DEFECT_FIXED`; it did not cause the source defect;
- closeout fingerprint:
  `0375d5567e0547c151f9fb140309aa568d17528246e611a68fa5984a1c481acd`;
- accepted reconciliation SHA-256:
  `e5b0cad238eb13f998c34ca51f659474484ba0ab97e64091a1a73cb604083d47`;
- development/protected outcome rows read: 0; holdout consumed: false.

These families cannot be rescued by lowering observed gates, selecting preferred
contexts, padding or dropping identifiers, changing source reconciliation,
substituting runners-up, or opening outcomes to select a repair. This family may
not be resumed by retuning the observed version.

### Unmerged ATLAS Review research lineage

- LIT-01 Heston-Sadka calendar-seasonality work is source-inconclusive.
- LIT-02 terminal/source repair work remains deferred and incomplete.
- These branches remain preserved for audit, are not merged product authority, and
  grant no historical support, PAPER authority, or LIVE authority.

## 9. Current protected and trading authority

- Master protected window: `2026-05-12..2026-08-11` — **consumed exactly once
  on 2026-09-07** by the frozen practitioner-library V2 walk-forward. Completed
  accounting records **93,380 master-protected return rows read**. The same frozen
  version continued without parameter change through the accepted V2 source cutoff
  `2026-09-03`; later rows are tracked separately as post-protected continuation.
- V2 daily split-reconciliation validator repair (2026-09-07): the former
  inverse-price-factor volume equality is audit-only provider-native evidence.
  OHLC split-factor consistency, provenance, canonical value validity, and
  finite/nonnegative volume remain hard acceptance gates. Focused post-build
  regressions exercise both the allowed volume divergence and the still-fatal
  price-factor mismatch. At repair acceptance it changed no source, strategy,
  portfolio, PAPER/LIVE authority, or protected-window state. The later frozen
  replay subsequently consumed the master holdout exactly once.
- Frozen A33/B33 V2 master-protected return reads: **93,380**. DEVELOPMENT account
  replay: **-17.912608%** return / **-20.803073%** max drawdown. Frozen walk-forward
  account replay through `2026-09-03`: **-8.372772%** return / **-8.372772%** max
  drawdown. Authority promotion: **none**.
- A33/B33 compatibility validation distinguishes immutable pre-outcome foundation
  evidence from the living current-state handoff. It accepts only the original
  zero-read documentation state before consumption or the exact one-time-consumed
  state with protected-row accounting afterward; frozen fingerprints and authority
  boundaries remain unchanged.
- No strategy currently has `HISTORICALLY_VALIDATED`, `PAPER_VALIDATED`,
  `LIVE_ELIGIBLE`, or LIVE-authorized status.
- PR #60 implements the A34.5 operator live-observability prerequisite. Once this
  exact-head package is merged, A35 may begin only under its own separate PAPER/
  broker-authority package; A35 has not begun.
- Qualifying PAPER may begin only for historically validated frozen versions.
- LIVE remains disabled until every later gate passes and the operator explicitly
  enables it.
- Automatic broker failover remains forbidden.

## 10. Strategy taxonomy: signals are not strategies

ATLAS will model five distinct objects:

1. **Indicator/feature:** a deterministic PIT value such as RSI, EMA, relative
   volume, ATR, or a premarket range.
2. **Setup/signal:** a time-local condition such as a crossover, recovery, squeeze,
   pullback, or range break.
3. **Strategy policy:** a versioned universe, setup, direction, entry timing, stop,
   target/exit, maximum hold, sizing, liquidity, cost, and invalidation contract.
4. **Router/selector:** determines whether an authorized policy is compatible and
   estimates its conditional economics relative to other opportunities.
5. **Authority:** determines whether the policy may run in research, operational
   PAPER, qualifying PAPER, or LIVE.

An RSI value is not a strategy. “Buy the breakout” is not reproducible until the
range, bar, order timing, false-break definition, stop, exit, and cost are fixed.

Popular descriptions must be corrected before implementation:

- a crossover is a transition from the prior bar, not merely `fast > slow`;
- RSI below 30 means strong recent downside momentum, not intrinsic
  “undervaluation”; the initial rule uses a recovery trigger and trend context;
- Bollinger compression predicts neither direction nor guaranteed expansion; a
  separate range/band break supplies direction;
- ADX measures trend strength, not direction;
- an EMA “bounce” needs a numeric ATR tolerance and confirmation event;
- ribbons use one canonical period set before any alternatives;
- same-bar indicator calculation and fill are prohibited.

## 11. Evidence and authority model

### Evidence source

- `PRACTITIONER_BASELINE`: transparent practitioner/chart/community rule; low prior
  authority and unverified until ATLAS tests it.
- `LITERATURE_ANCHORED`: supported by credible academic/replication or transparent
  institutional evidence; higher prior research weight, never guaranteed.
- `INTERNAL_CHALLENGER`: an ATLAS-created variant or selector; lowest external prior
  unless independently supported.

Evidence source affects research priority and prior confidence. It never grants
execution permission.

### Strategy authority

`RESEARCH → CANDIDATE → HISTORICALLY_VALIDATED → PAPER_VALIDATED → LIVE_ELIGIBLE`

- **RESEARCH:** specified/implemented; no trading authority.
- **CANDIDATE:** source rationale and faithful ATLAS implementation accepted;
  historical evaluation in progress.
- **HISTORICALLY_VALIDATED:** passed frozen PIT, after-cost, walk-forward,
  robustness, concentration, and statistical gates; eligible for qualifying PAPER.
- **PAPER_VALIDATED:** profitable prospective expectancy is credible across a
  meaningful sample with acceptable drawdown, stability, execution, and risk.
- **LIVE_ELIGIBLE:** historical, PAPER, system, risk, governance, and operational
  gates passed. Actual LIVE still requires explicit operator activation.

Authority controls permission. Conditional ranking controls preference only among
permitted strategies. No score, AI opinion, or GUI action can bypass authority.

## 12. Practitioner strategy catalog

The catalog stores aliases under materially different families so five momentum
parameterizations do not masquerade as five independent discoveries.

| Family | Common practitioner setups | Canonical research object | Data readiness | Order |
|---|---|---|---|---|
| Moving-average trend | Golden/death cross, fast/slow EMA, price/MA cross, 5-8-13, ribbon/Guppy | transition in slow/fast trend structure | Daily ready; some features needed | Pack 1 |
| Trend continuation | higher highs/lows, ADX trend, multi-timeframe alignment | persistent directional structure | Daily partial | Pack 2 |
| Pullback continuation | 9/21 EMA bounce, 20 EMA pullback, first pullback, breakout retest | temporary retracement inside prior trend | Daily partial | Pack 1 |
| Momentum | MACD signal/zero cross, RSI midline, stochastic pop, ROC | acceleration/continuation | Daily partial | Pack 1/2 |
| Price breakout | Donchian, support/resistance break, consolidation break | close beyond prior PIT range | Daily ready | Pack 1 |
| Volatility expansion | Bollinger squeeze, TTM squeeze, VCP, ATR expansion, NR7 | compression followed by directional break | Daily partial | Pack 1/2 |
| Mean reversion | RSI recovery, RSI(2), Bollinger/EMA/z-score/VWAP reversion | short-horizon reversal after stretch | Daily partial | Pack 1/2 |
| Exhaustion reversal | divergence, volume climax, failed break | failed continuation/exhaustion | Needs pattern definitions | Pack 3 |
| Volume confirmation | relative volume, OBV, accumulation/distribution, climax | participation confirms or rejects price move | Daily partial | Pack 1/2 |
| Relative strength | market/sector/industry relative strength, RS breakout | focal asset out/underperformance | Daily data ready; features needed | Pack 2 |
| Gap | gap-and-go, continuation, fill, reversal | opening discontinuity plus response | Minute/session work needed | Intraday pack |
| Opening range | 5/15/30-minute ORB, prior-day break | regular-session price discovery break | Minute/session work needed | Intraday pack |
| Premarket | premarket high, flag, high relative volume, consolidation break | extended-hours attention and range break | Extended-hours audit needed | Intraday pack |
| Support/resistance | bounce, rejection, break/reclaim/retest | reaction at PIT structural level | Definitions needed | Pack 3 |
| Composite | trend+momentum, breakout+volume, Triple Screen | prespecified evidence intersection | Components first | Pack 3 |
| Regime-conditioned | trend in trend, reversion in range, breakout after compression | strategy/context interaction | Outcomes/selector needed | Selector pack |

The catalog is deliberately broad; implementation is deliberately finite. New
aliases enter an existing family unless they change the mechanism, timing, or
trade policy materially.

Practitioner source anchors are definitions and idea provenance, not proof of
profitability: [Fidelity's technical-analysis overview](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/what-is-technical-analysis),
[Golden Cross](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/trading-using-the-golden-cross),
[Guppy/ribbon](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/guppy-multiple-moving-average-an-ma-ribbon-designed-to-tip-the-markets-hand),
[moving-average support/pullback](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/moving-average-trading-strategies/finding-support-and-resistance-in-moving-averages),
[MACD zero-line setup](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/macd-zero-line-crosses-with-swing-points),
[Bollinger squeeze](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/bollinger-band-squeeze),
[RSI(2)](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/rsi-2),
and [gap strategies](https://chartschool.stockcharts.com/table-of-contents/trading-strategies-and-models/trading-strategies/gap-trading-strategies).

## 13. First reference library: frozen starting specifications

These are the starting contracts to implement before ATLAS performance is viewed.
They are practitioner baselines, not claims of edge. Phase A33/B33 may correct an
implementation ambiguity before outcome access, but any material change must be
versioned and recorded in the trials ledger.

Common daily universe: PIT-active U.S. common stocks; no ETFs unless a strategy
explicitly says so; adjusted analytical bars with raw/execution-price lineage;
close at least $5; prior 20-session median dollar volume at least $5 million;
sufficient warm-up; no ambiguous identity; signal at finalized daily close; earliest
entry next regular-session executable price. Research reports both long-only and
benchmark-relative results where appropriate, but a benchmark is not a fabricated
hedge order.

Common risk/cost diagnostics: equal-risk sizing at a fixed small portfolio risk
budget; no lookahead sizing; `0/5/10/25/50` bps round-trip signal grid, 10 bps
primary and 25 bps stress; executable replay later uses spread/slippage/order/ADV
economics. Stop/target collision inside a bar uses the conservative adverse-first
assumption unless lower-timeframe authoritative data resolves order.

| ID | Setup and entry | Exit/risk | Native question |
|---|---|---|---|
| `ma_trend_cross_50_200_long_v1` | SMA50 crosses from at/below to above SMA200; buy next session | initial stop 2 ATR below entry; exit on reverse cross, 3 ATR trailing stop, or 126 sessions | Does slow trend transition produce positive after-cost long expectancy? |
| `ema_pullback_20_50_long_v1` | EMA20 > EMA50; a 1–5-session pullback bar intersects the EMA20 ±0.5 ATR zone without closing below EMA50; the first close above EMA20 enters next session, including a one-bar touch-and-recovery | stop below pullback low or 1.5 ATR, whichever is farther but within risk cap; exit at 2.5R, close below EMA50, or 15 sessions | Does a confirmed retracement inside an uptrend resume? |
| `macd_shift_12_26_9_long_v1` / `macd_shift_12_26_9_short_v1` | MACD crosses above signal while both are below zero for LONG; distinct SHORT version crosses below signal while both are above zero; next-session entry | 1.5 ATR stop; 3R target; opposite MACD cross or 20 sessions | Does momentum turn before/through broader continuation? |
| `rsi_recovery_14_trend_long_v1` | close above EMA200; RSI14 was below 30 and crosses back above 30; enter next session | 2 ATR stop; exit at EMA20, RSI >= 60, or 10 sessions | Does oversold recovery inside a long trend mean-revert after costs? |
| `donchian_breakout_20_volume_long_v1` / `donchian_breakout_20_volume_short_v1` | close crosses the prior 20-session high for LONG or low for SHORT; relative volume20 >= 1.5; EMA50 slope agrees; next-session entry | initial stop is the closer adverse price of the channel boundary or 2 ATR; 3 ATR trail; 20-session maximum | Does range escape with participation continue? |
| `bollinger_squeeze_breakout_20_long_v1` / `bollinger_squeeze_breakout_20_short_v1` | prior session BB width20 is at/below its trailing 126-session 10th percentile, then current close crosses the corresponding outer band with relative volume >= 1.25; next-session entry | stop at BB midline or 1.5 ATR; 2 ATR trail; 3R target; 20-session maximum | Does directional escape from compression continue? |

The code resolves the EMA pullback as a bounded 1–5-session pullback and first
EMA20 recovery. Its initial stop is the farther adverse price of the pullback
extreme or 1.5 ATR; the opportunity is risk-rejected when that stop exceeds the
frozen 10% maximum stop distance rather than silently tightening the stop. The
Donchian stop is the closer adverse price of the channel boundary or 2 ATR. The
Bollinger trigger requires prior-session compression and uses a 2 ATR trail. The
same controls apply symmetrically to short policies, including later borrow/locate
and asymmetric executable costs. Long and short are distinct versions, not
automatic mirrors.

The six materially different families comprise nine direction-specific policy
versions. Before ATLAS performance access, the frozen A33/B33 fingerprints are:

- reference strategy policy:
  `26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3`;
- strategy authority:
  `a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5`;
- daily reference features:
  `ee7e09b680b64b65280dea88c01d402bd9576a04cc70bc7748d8e3048ff57159`.
  The pre-outcome revision uses same-session unadjusted close for the PIT price
  floor while split-adjusted prices remain the indicator/return stream.
- retained legacy trusted-lake adapter:
  `reference-lake-adapter-v1-massive-development-split-free-identity-exact`.
- isolated V2 trusted-lake adapter:
  `reference-v2-lake-adapter-v2-alpaca-sip-hash-bound-explicit-evaluation-scopes`.

Every version remains `PRACTITIONER_BASELINE`, `RESEARCH`, and
`RESEARCH_REPLAY`-only. Master protected return rows read: **0**; holdout consumed:
**false**; provider writes: **0**; broker writes: **0**; PAPER submits: **0**; LIVE
writes: **0**.

### Later intraday reference pack

Intraday work starts only after timestamp, extended-hours flag, split adjustment,
auction, halt, missing-bar, and provider-coverage semantics pass a source-only gate.

- **Gap-and-go / 15-minute opening-range breakout:** frozen gap threshold, opening
  range, relative-volume clock, next-bar entry, range stop, R-based exits, and
  end-of-day flat rule.
- **Premarket relative-volume consolidation breakout:** source idea includes the
  Reddit “Highest Volume Day Strategy.” ATLAS will replace subjective phrases with
  a fixed premarket window, prior-volume lookback, minimum price/liquidity, gap,
  consolidation-width/duration, one-consolidation algorithm, next-bar premarket-high
  break, explicit stop, partial/target logic, and end-of-day exit before opening
  performance. Reported social-media gains and win rates are unverified claims.

No “highest day ever” comparison may depend on how many years happen to exist in a
ticker's file. Use a fixed prior lookback and disclose the resulting population.

## 14. Historical testing system

### 14.1 One reusable engine

Do not build a bespoke backtester per indicator. A versioned engine must accept a
strategy policy and produce:

- PIT universe and exact feature snapshot;
- every eligible setup and every reason for rejection;
- route/authority decision;
- next-executable-event entry and conservative fill;
- stop, target, trailing, time exit, corporate action, halt, delisting, and missing
  data handling;
- gross and net returns under primary and stress economics;
- maximum favorable/adverse excursion and target-before-stop outcome;
- account-level cash, exposure, overlap, portfolio admissions, conflicts, and
  capacity;
- exact data, feature, strategy, selector, cost, risk, and code versions.

### 14.2 Record all opportunities, not just chosen trades

The outcome ledger must retain fired, routed-out, risk-rejected, not-selected,
shadow/counterfactual, planned, submitted, filled, partially filled, canceled,
exited, and unreconciled opportunities. Otherwise ATLAS cannot distinguish a weak
strategy from a strong strategy that the portfolio selector consistently ignored.

Counterfactual outcomes are research evidence only. A blocked strategy is never
sent to a broker merely to gather data.

### 14.3 Chronology and partitions

- Use expanding or rolling walk-forward folds in time order.
- Fit thresholds, calibration, conditional models, and selectors only on prior
  windows.
- Purge and embargo around overlapping outcome horizons.
- Keep final qualifying historical evidence separate from development.
- The retained master protected window was hash-bound and consumed exactly once
  by the frozen practitioner V2 walk-forward on 2026-09-07. It may never be reused
  to qualify a revision. The unchanged frozen version continued afterward through
  the V2 source cutoff as post-protected historical continuation. A new future
  prospective PAPER period remains necessary and cannot be backfilled from history.
- Never choose a parameter, regime rule, cost, or exit after observing the period
  meant to qualify it.

### 14.4 What gets measured

At signal, trade, session, and account levels report:

- count of trades and independent opportunities;
- coverage and abstention;
- win/loss distribution, expectancy, payoff ratio, profit factor;
- total return, drawdown, volatility, downside/tail loss, Sharpe/Sortino where
  meaningful;
- gross-to-net cost decay and cost stress;
- MFE/MAE and target-before-stop calibration;
- turnover, holding time, liquidity/capacity, spread/slippage, borrow/locate;
- performance by year/fold and predeclared market, sector, ticker, volatility,
  liquidity, direction, and time-of-day conditions;
- concentration by session, ticker, sector, strategy, and unusually successful
  trade;
- stability against small *predeclared* neighboring parameter checks;
- benchmark and simple-family comparator.

Raw trade win rate is not a universal gate; positive expectancy may have a low win
rate with asymmetric payoffs. Likewise, a high win rate may hide rare ruinous loss.

### 14.5 Multiple testing and overfitting

Maintain an append-only trials ledger including failures. Test at the strategy-family
level, treat nearby parameters as related trials, use dependence-aware bootstrap or
appropriate panel/session methods, and apply a frozen family-wise or false-discovery
procedure. White's Reality Check, Hansen's Superior Predictive Ability test,
deflated performance measures, and probability-of-backtest-overfitting diagnostics
are available tools, selected prospectively rather than only when convenient.

This follows the central warning from [White's Reality Check](https://doi.org/10.1111/1468-0262.00152),
[Hansen's SPA test](https://doi.org/10.1198/073500105000000063), and the
[Probability of Backtest Overfitting](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253):
the best-looking rule from a large search is not evaluated honestly as if it were
the only rule tried. Empirical results for technical rules are mixed after these
corrections—one U.S. futures study found significance in only 2 of 17 markets,
while a large Chinese-equity study reported surviving rules after costs—so ATLAS
must test rather than assume ([Park & Irwin](https://doi.org/10.1002/fut.20435),
[Jiang et al.](https://doi.org/10.1111/irfi.12161)).

## 15. Learning what works where

The correct goal is conditional evidence, not a giant sparse table of every
indicator crossed with every regime.

### 15.1 Condition profile

For each frozen strategy version, accumulate outcomes by a limited predeclared set:

- direction and native timeframe;
- market, sector, and ticker regime;
- volatility and liquidity bucket;
- gap/extended-hours state for intraday strategies;
- strategy age and recent prospective window.

Report raw counts, effective independent sample size, net expectancy, calibrated
target-before-stop probability, downside, uncertainty interval, and degradation.
Never show a strong conditional estimate without its support and uncertainty.

### 15.2 Partial pooling before hard routing

Use regularization or hierarchical partial pooling so small cells shrink toward the
family/global estimate instead of producing extreme probabilities. A condition may
become `PREFERRED`, `ALLOWED`, or `BLOCKED` only with a prospectively frozen minimum
effective sample and evidence threshold. Until then it is `UNKNOWN`, not favorable.

### 15.3 Walk-forward selector

The selector is fitted only on prior outcomes and produces, per current opportunity:

- calibrated `P(target before stop)` and/or win probability;
- expected gross and net return;
- expected downside/tail loss;
- cost and fill confidence;
- estimate uncertainty and data support;
- correlation/concentration effect on the current portfolio;
- evidence source and authority.

A useful ranking quantity is expected net utility:

`expected payoff after cost − downside penalty − concentration/correlation penalty`

but its exact function, coefficients, abstention threshold, and calibration method
must be frozen before qualifying evaluation. Prefer stable forecast combinations or
simple regularized models to a large tournament when performance is close; forecast
combination can reduce instability, while conditional predictive-ability testing
supports comparing forecasts in changing environments
([Rapach, Strauss & Zhou](https://academic.oup.com/rfs/article/23/2/821/1604687),
[Giacomini & White](https://doi.org/10.1111/j.1468-0262.2006.00718.x)).

The selector may abstain. It may recommend a strategy family for a *new versioned
research experiment*. It may not tune that family on the live opportunity, alter a
production rule, or grant itself authority.

### 15.4 Challenger promotion

Every learned condition rule or selector revision is a frozen challenger:

1. train on prior windows;
2. compare out of sample to the incumbent and simple no-selector baseline;
3. evaluate costs, turnover, calibration, drawdown, and regime stability;
4. run operational PAPER if needed;
5. run a new qualifying prospective window when seeking authority; and
6. promote explicitly with version and rollback plan.

## 16. PAPER is the practical bridge to LIVE

### Operator-observability prerequisite

No Operational PAPER or Qualifying PAPER session may begin until the A34.5 browser
observability gate is accepted. The operator must be able to watch the same
engine-owned state used by execution/reconciliation change without manual page
refresh: account/equity, open positions, live unrealized/realized P&L, strategy and
setup rationale, sizing/risk, order/fill lifecycle, exits, history, and system/data/
broker health. Unknown/stale state must be explicit. This requirement improves
operational control and debuggability; it does not validate a strategy.

### Operational PAPER

Purpose: prove the complete product can ingest, decide, construct, size, route,
execute, manage, reconcile, record, and display without real money. Baselines are
allowed. Its results cannot silently count toward LIVE qualification.

Operational PAPER starts only after A34.5 proves the browser is connected to the
authoritative runtime event/state path. During PAPER, every material lifecycle event
must be visible and retrospectively traceable from candidate through final exit.

### Qualifying PAPER

Purpose: forward-test a historically validated frozen strategy and full portfolio
process on genuinely new information. Before it starts, freeze sample and minimum
duration logic, cost/slippage comparison, profitability/expectancy, drawdown,
tail-loss, concentration, stability, execution/reconciliation, and system-health
gates.

Qualification evaluates completed trades and independent opportunities, net
expectancy, return, profit factor, drawdown, risk-adjusted measures when meaningful,
tail loss, concentration, regime dependence, modeled-versus-observed slippage,
stability through time, and dependence on exceptional winners. `PAPER P&L > 0`
alone does not pass.

Paper fills differ from live queue position, spread capture, partial fills, latency,
and impact. PAPER validation is therefore necessary, not sufficient.

### LIVE

LIVE is deliberately difficult. It requires a `LIVE_ELIGIBLE` strategy/portfolio,
accepted system readiness, explicit operator activation, small initial risk, hard
loss/exposure limits, health/reconciliation, emergency disable/flatten capability,
and manual fallback. No automatic broker failover.

## 17. Data integrity and V2 policy

When data is materially questionable:

1. perform a serious root-cause/reconciliation investigation covering local
   corruption, transformations, provider semantics, and authoritative limitations;
2. if V1 cannot remain economically trustworthy, preserve its results, hashes, and
   provenance; persisted V1 historical files may be decommissioned only under an
   explicit operator decision and exact fail-closed deletion manifest;
3. build a clean separately named V2 from the best authoritative sources and
   documented canonical rules;
4. do not substitute V2 beneath an observed experiment or pretend it is the same
   experiment;
5. rerun only as a new prospectively declared experiment; and
6. preserve audit lineage and never use persisted V1 rows as V2 ancestry; retaining
   both physical lakes is preferred but is not mandatory when precise V1
   decommissioning has been explicitly authorized.

The Alpaca SIP V2 generation enforces this policy physically beneath
`data/v2_build/alpaca_sip_v2`. Its frozen source request contract is native `1Day`
followed by native `1Min`, SIP feed, raw adjustment, `asof=-` (no provider ticker
remapping), 10,000 total bars per page, and opaque pagination until null. API windows
are bounded at New York local midnight; because Alpaca documents `end` as inclusive,
each window ends one microsecond before the next local midnight. Fresh active and
inactive assets and complete-quality corporate actions seed acquisition literals, but
they do not establish identity continuity. Exact provider rejections and response/row
anomalies are evidence-bearing quarantines, never occasions to guess a replacement.
Unit Parquet is an isolated candidate base until the identity, completeness, quality,
provenance, and promotion gates pass.

The post-build contract performs that next daily gate without V1 ancestry.
It reconstructs and hash-verifies the frozen plan and every native unit, fully scans
native daily facts, binds assets and complete corporate-action evidence, and builds
a conservative first V2 identity map. Only one provider asset ID tied to one literal
symbol and an explicitly common-stock asset name is initially eligible. Current
active/inactive status is retained but never used as a historical filter; name
changes, mergers, reorganizations, spin-offs/rights, stock distributions,
termination/redemption events, ticker reuse, ambiguous security type, response
anomalies, and internal XNYS gaps are preserved and excluded rather than silently
repaired until a separate segment and cash-flow policy exists. A separate SIP
`adjustment=split`, `asof=-` daily capture is resumable and reconciled to raw keys
and factors. The analytical view preserves raw execution state separately and adds
same-session unadjusted close for the PIT price floor, preventing a later split from
rewriting historical `$5` eligibility. The independently captured source can extend
through its frozen current cutoff, but DEVELOPMENT strategy-input Parquet ends
physically at `2026-05-11` and materializes zero protected-window return rows. This
is a research-data promotion only, not a global production path switch. A separate
`walk_forward_daily.json` view may be materialized only after DEVELOPMENT succeeds
and an immutable source/policy authorization plus permanent consumption receipt have
been written. Its signal clock begins on `2026-05-12`, its end is exactly the accepted
V2 cutoff, and any failure after protected materialization begins remains consumed.
Attributable provider rejections or malformed adjusted rows exclude their literal
symbol globally while preserving the evidence and allowing the clean remainder to
proceed. An unattributed anomaly or unit-level validation failure remains a hard
stop; one bad literal does not silently poison or unnecessarily discard the entire
generation.

The frozen daily indicator engine may consume only the exact hash-bound V2 research
manifest through the isolated V2 adapter. It cannot discover legacy paths. No V2 PIT
regime generation is accepted yet, so market, sector, and ticker contexts remain
explicitly `UNAVAILABLE`; importing retained V1 regime state would violate the clean
generation boundary. Native minute bundles are hash-verified during base acceptance, and full extended-hours/intraday semantics are now accepted by B34. Adjusted-minute derivation remains deliberately absent: canonical minute bars are raw and cross-split price/volume lookbacks fail closed. News is a separate source/PIT research package and does not block
daily database acceptance or the Product track.

Existing valid caches are evidence. A clean authoritative replay that reproduces a
contradiction means purge/refetch is not a repair. Source integrity is a supporting
gate, not the product, and a source branch should stop when its expected information
gain falls below stronger trusted-data experiments.

## 18. Persistent safeguards

1. PIT population, identity, chronology, publication/acceptance timing, and session
   rules are mandatory.
2. Preserve provider-native ticker case and exact identity; ticker text alone does
   not prove continuity.
3. Corporate actions, delistings, missing bars, stale data, halts, auctions, and
   universe membership must be explicit.
4. Signals formed at a close cannot enter before the next executable event.
5. Same-bar stop/target ambiguity is conservative unless authoritative finer data
   resolves it.
6. Transaction costs, spread, slippage, borrow, fees, market impact, and capacity
   cannot be chosen to make a result pass.
7. Retained alpha branches keep their finalist-only protected-performance rules.
   The explicitly authorized frozen practitioner library has a separate one-time
   historical walk-forward contract. Its consumption is permanent, including failed
   attempts, and the same period cannot qualify a later retuned version.
8. Negative/zero-trade results are valid and never rescued by post-result retuning.
9. Scientific families and variants are frozen before governed performance.
10. ML and AI are evidence/audit, not authority.
11. Research code never writes to providers or brokers.
12. Unknown data, mutation, broker, order, fill, exposure, or operator-display state
    fails closed.
13. LONG geometry requires `stop < entry < target`; SHORT requires the reverse.
14. PAPER never implies LIVE; credentials/endpoints/UI controls do not create
    authority.
15. No automatic cross-broker failover.
16. No silent self-modification; every change is versioned, replayed, qualified,
    promoted, observable, and reversible.
17. Root cause before workaround; accepted evidence and failed evidence are
    preserved.
18. Prefer the largest safe coherent package over conversational micro-gates.
19. Operational PAPER may not run ahead of accepted operator live observability.
20. Every repository-changing implementation package updates both living documents
    in the same commit before acceptance/merge.

## 19. Roadmap from the rebaseline

Track A and Track B gates may proceed in parallel when they do not contaminate each
other's evidence. Product gates A33–A37 do not require supported alpha. A38/A39 LIVE
progression requires qualifying strategy and system evidence.

### A33/B33 — Practitioner Strategy Laboratory and Product Rebaseline

Build stable strategy/source/authority/version contracts, a non-placeholder catalog,
the first six daily policies, missing daily indicators, reusable PIT backtest/trade
simulation, trials ledger, complete opportunity/outcome ledger, condition slices,
and API read models. Connect baselines to the accepted discovery/regime/risk path.

Acceptance proves code correctness, exact signal transitions, next-event timing,
cost application, portfolio overlap, failure paths, reproducibility, cross-platform
tests, retained scientific facts, and zero accidental PAPER/LIVE authority. It also
produces the first honest historical reports; each strategy may pass, fail, or remain
underpowered independently.

**Implementation status (2026-09-07): reference foundation, retained legacy adapter,
isolated V2 post-build/adapter path, and explicit frozen walk-forward controls are
implemented; empirical V2 strategy performance has not been opened.**
The operator's native acquisition completed with **67,480 / 67,480 units**,
including **5,302 daily** and **62,178 minute** units, **3,897,688,734 canonical
rows**, and **1,757,288 quarantined rows**. This is complete native capture but not
post-build identity/daily acceptance; quarantines remain evidence for attribution.
The original post-build package
was accepted in PR #58 and merged as
`8e5abf21fe1ca138cd90125005b8c305a598dd44`; its post-merge `main` workflow passed
on Windows and Ubuntu. Operator execution remains pending.
The separate catalog contains six families and nine
direction-specific policies. The accepted Phase11 eight-rule registry and accepted
33-feature core remain unchanged. PR #45 merged the accepted phase-start seed and
opportunity-event contracts as
`bc105be4958cce808dbbeb306f0ec58f23b13a6d`; those six blocked seed
specifications remain preserved for compatibility. The completed nine-policy
catalog resolves the blockers in a separate versioned layer. A separate daily
feature overlay implements exact transition features; a provider-free runner
performs independent-strategy replay from caller-supplied bars; versioned
opportunity/run schemas retain rejected, selected, and overlap-suppressed
counterfactual records; an atomic append-only hash-chain ledger records strategy
trials; and the control plane exposes the catalog read-only at
`/api/v1/strategies/reference`. The runner hard-rejects all post-DEVELOPMENT rows by
default. Its separate walk-forward mode requires an immutable source/policy-bound
authorization, accepts pre-May-12 rows only as feature warm-up, emits signals only
from May 12 through the exact validated cutoff, and records the protected-row count
in strategy, account, trial-ledger, post-build, and consumption evidence. It has zero
provider/broker/PAPER/LIVE writes in either mode.
The restart repair now preserves each prior receipt state in content-addressed
history, verifies the complete chain before continuation, retains known row counts
across retries, and reuses completed results only after operator artifact verification.
A source-only rerun cannot erase prior holdout consumption. Missing/corrupt receipt
history and invalid completed results fail closed; incomplete GUI states show the
attempt and known/pending row accounting without an unopened-outcomes claim.
The materialization-cutoff failure path also preserves the protected-row count in
both the receipt and post-build summary when the reported cutoff disagrees with the
authorized cutoff. Three additional pytest cases cover that failure and successful
retries after cutoff and replay failures. The complete implementation revision
`0879bbed7f22c53108f58db0b790f58c61a04987` passed all **ten PR #61 workflow
groups**, including the locked Windows and Ubuntu full suites at **1,581 tests
plus 4 subtests per platform** and all three retained A33/A34 validators. Local
checks also passed 10 isolated standard-library receipt tests, 13 isolated
coordinator checks, Python compilation, JavaScript syntax, dependency-lock
validation, and secret hygiene. Local isolation was necessary because application
dependencies were absent; the full application evidence comes from locked CI.
The final closeout changes only these two living documents. Full CI on the final
PR revision and post-merge `main` verification remain mandatory release gates.
The next operation is the authorized workstation chain: source acceptance,
DEVELOPMENT, then the frozen one-time walk-forward. No workstation outcomes were
opened during implementation; all nine policies remain RESEARCH and PAPER/LIVE
authority remains absent.
Compile-all and the complete local suite for the accepted V2 post-build package pass
at **1,546 tests**; all ten PR #58 exact-head workflow groups and the post-merge
`main` workflow passed.
The read-only adapter contract
`reference-lake-adapter-v1-massive-development-split-free-identity-exact` scans
accepted canonical partitions without provider calls or writes. Its V1 scope is the
Massive-only DEVELOPMENT interval `2021-08-16..2026-05-11`: exact XNYS partition
and regular-open semantics, retained reference metadata no later than the run end,
authoritative-or-unique identity, no current active/delisted filter, and complete
split-report/hash reconciliation. Because accepted canonical bars are unadjusted,
V1 excludes every split-touched identity and every stream with an internal session
gap; retained factor-1 streams are exactly equivalent to split-adjusted prices.
Pre-seam Alpaca and split-affected instruments require the separately validated V2
rather than guessed factors. The V2 DEVELOPMENT adapter binds only the exact
isolated research-daily manifest and all partition hashes; it refuses arbitrary
paths and legacy fallback. A separate walk-forward adapter accepts only its exact
manifest, verifies the authorization self-hash, current frozen policy fingerprints,
and permanent consumption receipt, requires the exact authorized warm-up start plus
the complete protected interval and source-cutoff end, and is never selected
implicitly. Provider-native
split-adjusted analytical bars retain a separate unadjusted close for the PIT price
floor. The first stream measures price return and
does not yet credit or debit cash distributions; its replay is diagnostic only until
dividend and spin-off cash-flow economics are implemented or conservatively bounded.
The canonical provider timestamp remains the regular-open
stamp, while contract
`reference-signal-availability-v1-xnys-regular-close-next-open` adds the true XNYS
close availability time for daily signals. The runner records that close clock and
still enters no earlier than the next regular-session open. The operator V2 run has now produced the first empirical frozen reference results.
PR #47 accepted the retained legacy adapter and merged it as
`646db6e6e44ccd2355c7c2263221f35cd01d5da8`; post-merge Windows and Ubuntu full
tests passed. DEVELOPMENT produced **161,347 opportunities** and account return
**-17.912608%** with **-20.803073%** max drawdown. The frozen walk-forward produced
**14,081 opportunities**, read **93,380** rows from the retained master holdout,
and returned **-8.372772%** with **-8.372772%** max drawdown through `2026-09-03`.
Provider/broker/PAPER/LIVE writes remained **0**. The daily feature fingerprint
changed before outcome access solely to bind the unadjusted PIT price-floor
correction; strategy policy and authority fingerprints remain unchanged and no
strategy was promoted.

### A34 — Signal-to-Trade Construction, Portfolio Replay, and Replay Dashboard

This replaces the former global alpha-blocked **Phase33 — Signal-to-Trade
Construction** dependency. Construct complete candidate trades, compare strategies,
admit a risk-controlled account portfolio, replay cash/orders/positions/exits as one
process, and show decisions, counterfactuals, costs, exposure, and outcomes in the
browser. Baselines remain operational-only unless separately validated.

**First vertical-slice status (2026-09-07): implemented and empirically replayed;
result is negative at the account level and grants no authority promotion.** Frozen
portfolio-policy fingerprint:
`c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`.
The RESEARCH account replay consumes only the exact input-bound independent run and
uses a fixed event clock: opening exits → opening candidate admission → intraday
daily-bar exits → closing mark. It begins at `$100,000`, risks `0.25%` of current
equity per position including primary modeled costs, caps single-position notional
at `10%`, gross exposure at `100%`, open positions at `10`, and active family
positions at `3`. The non-learned selector balances current family load and then
uses stable identifiers; it never ranks same-session candidates with realized
outcomes. One position per instrument is allowed. This first vertical slice was
accepted in PR #48 and merged as
`147b95810936a0b10b24eb08e51cd4d83c16c85b`; its post-merge Windows and Ubuntu
full suite passed.

V1 is deliberately long-only. It retains short-strategy evidence but rejects short
account admission until short borrow, locate, and recall economics exist. It also labels
correlation and sector controls unavailable rather than fabricating them. Unresolved
exits are rejected so every admitted V1 position has an entry, exit, cost, cash
transition, and reconciled outcome. The full DEVELOPMENT command preregisters this
policy before performance and writes hash-bound decisions, simulated orders,
position outcomes, equity, and summary artifacts. The read-only endpoint
`/api/v1/research/reference-replay` and the current stacked Phase19 operator
dashboard show the honest `NOT_RUN`, `INVALID`, or `AVAILABLE` state, the nine
strategies and RESEARCH authority, per-strategy account statistics, aggregate
account return/drawdown/costs, recent completed positions, portfolio admission
decisions, simulated order events, and a closing-equity/exposure curve. The read
model verifies the recorded SHA-256 and row schema of all four replay artifacts
before displaying an available result; any drift fails the complete view closed.
The implemented walk-forward extension adds `INCOMPLETE`, prefers a completed separately
labeled walk-forward over DEVELOPMENT, verifies its final consumption receipt and
protected-row count, and never hides a failed/incomplete protected run by falling
back to DEVELOPMENT.
Run it with
`python scripts/run_phase19_control_plane.py` and open `http://127.0.0.1:8765`.
The panel uses local read-only endpoints and performs no provider or broker call.
The operator-path correction was accepted in PR #49 and merged as
`cc0ecc6995ad977ca6eeb5fc00983ba2926317a0`; its post-merge Windows and Ubuntu
full suite passed. The hash-verified operator drilldown was accepted in PR #50 and
merged as `f0a45cbff2662e26f4f1f55e8a16c0c356c9266c`; its post-merge Windows and
Ubuntu full suite passed. This is not qualifying historical or PAPER evidence;
authority promotion and provider/broker/PAPER/LIVE writes remain zero.

The A34 PIT context slice now uses contract
`reference-regime-context-v1-exact-asof-hash-bound-same-close-market-only`. It
accepts only the split-origin manifest whose as-of date is exactly the replay end,
hash-verifies its snapshot and effective-market history, rejects any future,
duplicate, blank, or missing-session row, and joins the same-session finalized market regime
that is available at close for a next-open decision. It never invokes
the regime writer. The ticker and sector regime context remains `UNAVAILABLE` until an
accepted PIT ticker-state join and PIT instrument-to-sector map exist. Remaining
A34 context work is therefore ticker, sector, and correlation control only after
their evidence contracts exist; none should delay the first honest fixed-policy
replay on the trusted lake.

PR #51 merged the exact PIT market-regime context as
`e2dd741b4cdd3f5b729c4ec1cb510451887c748c`; its post-merge `main` test workflow
passed. This preserves zero protected reads and zero provider/broker/PAPER/LIVE
writes.

### A34.5 — Operator Live Observability and Paper Dashboard Gate

PR #60 on `a34-5-frontend-operator-dashboard` now implements the A34.5
operator-observability gate and closes it when this exact-head package is accepted
and merged. `PaperDashboardService` reads accepted local Phase15 execution evidence
plus Phase5 persisted marks; path/hash/schema drift fails `INVALID`, stale or
uncertain provider state is visibly `DEGRADED`, and passive refresh initializes no
provider or broker object. Fresh LONG positions mark at bid and SHORT positions at
ask. Upstream-unbound strategy provenance and gross-only realized P&L remain
explicitly unavailable rather than fabricated.

The existing loopback-only Phase19 server exposes GET-only
`/api/v1/ops/paper-dashboard`. The browser uses bounded 5/15/30-second polling over
the same engine-owned evidence and organizes the operator console into Overview,
Market, Research, Portfolio, Execution, Brokers & Data, Operations, and Controls.
The separate synthetic preview never loads `.env`, never initializes a real provider
or broker, disables mutation controls, and rejects POST. **A34.5 grants no PAPER
strategy authority and no broker-write authority.** Its completion only removes the
observability prerequisite so A35 may begin under a separate explicit authority
package.

The dashboard acceptance surface must include, at minimum:

1. **Account:** equity, cash/buying power, gross/net exposure where applicable,
   realized P&L, unrealized P&L, and useful session/day totals.
2. **Open positions:** ticker/instrument, strategy/version, side, quantity, entry and
   current price, stop/target/invalidation, risk amount, unrealized dollar and
   percent P&L, and age/hold state.
3. **Decision feed and reasoning:** setup/signal that fired, relevant regime/
   condition context, concise deterministic selection or rejection reasons,
   strategy authority, sizing/risk rationale, and AI review/audit state when used.
4. **Order/fill lifecycle:** planned, submitted, accepted, partial, filled,
   canceled, rejected, and reconciliation state with timestamps and broker/order
   identifiers where safe to expose locally.
5. **Exits/sales:** exit trigger/reason, exit price, realized dollar/percent P&L,
   modeled/observed costs, hold duration, and final reconciliation state.
6. **History/statistics:** searchable recent decisions and closed trades, plus
   strategy-level and account-level performance/behavior statistics sufficient to
   understand what has been working, losing, abstained, or blocked.
7. **Health/control:** market-data freshness, provider and broker health, last
   successful update, orchestration state, current execution/authority mode, stale
   or unknown state warnings, and visible kill/emergency-control status.

The browser must update without operator-initiated page refresh through an accepted
event-driven or short-polling mechanism. The implementation may choose SSE,
WebSocket, or bounded polling based on the existing control-plane architecture; the
contract is freshness, traceability, and single-source-of-truth behavior rather than
a specific transport.

The GUI must consume the same engine-owned decision, order, fill, position, account,
health, and reconciliation records used by execution. It may create read models and
aggregations but may not create a second trading state or independently decide what
ATLAS bought/sold. Unknown, stale, hash-invalid, or inconsistent state must be
visibly degraded and fail closed. Historical replay views remain supported and
should reuse the same lifecycle concepts where practical so replay and PAPER are
operator-comparable.

A34.5 acceptance requires focused schema/read-model/UI tests, no accidental broker
mutation, exact-head full regression and cross-platform CI, and updates to both
living documents in the same accepted package. **A34.5 grants no PAPER strategy
authority and no broker-write authority by itself.** It only satisfies the
operator-observability prerequisite for A35.

### B34 — Intraday Source Readiness and Opening/Premarket Pack

Audit trusted minute and extended-hours coverage without performance. If ready,
freeze and implement gap/opening-range and premarket relative-volume consolidation
strategies, including a quantified Highest Volume Day variant. If not ready, record
the limitation and proceed with daily strategies rather than entering an open-ended
data repair branch.

The native V2 acceptance stage may verify minute bundle/canonical hashes, but that
does not by itself accept intraday semantics. B34 must scan actual timestamp/session-
segment behavior, duplicates, OHLCV, auction/halt/missing-bar implications,
extended-hours coverage, split adjustment, and the exact premarket information clock.
Do not materialize billions of indicator rows before this finite readiness report
shows which intraday pack can be represented faithfully.


**B34 status (2026-09-08): CLOSED / ACCEPTED.** The enhanced workstation audit returned `ACCEPTED` under `atlas-b34-intraday-source-readiness-v2-ohlcv-pack-frozen` with evidence SHA-256 `415c46c714b80f5cff4950320443088b8b89ed761c9f51d071fccf3e60baefd0`, while preserving semantic/source-readiness evidence SHA-256 `aad355e57c089a7aaea84a3f941091dec69d89ce87235972f13472a308550237`. All five deterministic OHLCV samples passed, including accepted zero-row source absence; sampled coverage represented 325 premarket, 933 regular, and 125 after-hours bars. The selector opened zero monthly partitions overlapping the consumed `2026-05-12..2026-08-11` master holdout and made zero provider calls, broker reads, or broker writes. Missing minutes remain absence rather than zero-filled or inferred halts; the 09:30 provider aggregate is not rewritten as a separate auction record; canonical minute bars remain raw/unadjusted; cross-split price/volume lookbacks fail closed; and a bar stamped `T` is usable only at `T+1m`, with premarket state available at 09:30 ET after stamp 09:29 and the 15-minute opening range available at 09:45 ET after stamp 09:44.

The frozen pre-outcome pack fingerprint is `6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf` and contains four RESEARCH-only references: `b34_gap_continuation_v1`, `b34_opening_range_breakout_15m_v1`, `b34_premarket_relvol_consolidation_v1`, and `b34_highest_volume_day_style_v1`. No governed performance was accessed; outcome access remains false. B34 grants no promotion, PAPER order authority, broker mutation, LIVE authority, or broad/full minute materialization. The next research step must freeze its evaluation design and a new blind/future validation boundary before opening development outcomes; the consumed master holdout may never be reused to qualify these strategies.

### A35 — Operational PAPER and Operator Web Beta

**Next Track-A package after PR #60 merges. A34.5 observability is satisfied, but
A35 PAPER/broker authority has not begun and must be granted separately.** Run the
same engine prospectively with
PAPER money: ingest, generate, select, construct, risk-check, submit under
centralized authority, manage, reconcile, record, and display. The accepted A34.5
browser must show the lifecycle as it happens rather than being added afterward.
Prove restart/idempotency, duplicate prevention, stale-data handling,
partial/cancel/reject behavior, kill controls, and clear operational-versus-qualifying
labels. LIVE unavailable.

Operational PAPER completion must demonstrate that the operator can reconstruct any
trade from the dashboard and underlying authoritative records: what fired, why it
was selected or rejected, how it was sized, what was sent to the broker, how it
filled, current/realized P&L, why it exited, and whether reconciliation completed.

### B35/A36 — Conditional Evidence, Selector, Outcomes, and Performance UI

Build the walk-forward condition profiles and frozen selector challenger; compare it to simple family baselines. Add strategy management, calibration, degradation, regime, slippage, portfolio contribution, and trials-ledger views. Learning may recommend but never self-promote.

**B35 DEVELOPMENT replay status (2026-09-11): CLOSED / ACCEPTED; strategy x condition / selector analysis NEXT.** The v2 contract remains frozen. Repository acceptance did not itself open outcomes; the later immutable DEVELOPMENT authorization opened only the exact frozen replay described below. The original `atlas-b35-a36-conditional-evidence-v1-pre-outcome` fingerprint `7bfd1cfdd65e946d45caa99dd2a35a90d8b424cb82cad5941ad26cac51816c4c` is preserved as superseded pre-outcome lineage and opened no B35 outcomes. Before any outcome access, review found that B34 validly permits a bar stamped 11:30 ET, which is usable only at 11:31, while v1 stopped its decision-time bucket at 11:30. Review also found that an overnight split should make the raw prior-close/current-open gap unavailable without erasing an otherwise valid same-session ORB/premarket/HVD condition snapshot. These are preregistration corrections, not outcome-driven retuning. B34 itself is unchanged.

The active contract is `atlas-b35-a36-conditional-evidence-v2-pre-outcome-clock-split-corrected`, fingerprint `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`, bound to unchanged B34 pack fingerprint `6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf`. B35 decision time is valid through 11:31 ET and the final bucket is `1031_TO_1131`; later decisions fail closed. A split-crossed raw gap is `UNAVAILABLE` for non-gap profiles, while B34 gap continuation remains blocked across the split. Twenty close-to-close realized-volatility returns require 21 completed split-safe closes. All other frozen walk-forward, exit, cost, selector, multiplicity, robustness, blind, and A34 risk-envelope rules remain as preregistered.

**Finite replay implementation boundary.** The governed replay is one canonical trial over `2016-01-04..2026-04-30`; the CLI exposes no alternate start/end, output-root, or trial-ledger override. The implementation binds that exact DEVELOPMENT minute-unit set to the immutable native acquisition plan and exact `year/month/batch/unit` checkpoint/canonical paths. May-2026-or-later minute partitions remain structurally rejected before open. Paths are confined to isolated V2 roots without symlink escape; canonical SHA-256 is checked lazily immediately before use; raw/unadjusted physical rows, duplicate keys, exchange-session labels, and strict Boolean adjustment schema fail closed. The source plan is itself content-fingerprint validated so a modified in-memory plan cannot retain a stale trusted fingerprint. Split/corporate-action evidence is separately path/hash bound.

Actual outcome replay additionally requires the immutable self-hash DEVELOPMENT authorization. Replay publication is serialized to prevent concurrent writers, writes an immutable self-hash read-start marker before the first authorized outcome read so a failed run cannot erase the fact that outcome access began, and materializes only compact fired-opportunity/context/outcome JSONL by deterministic symbol batch. Completed outputs have self-hash receipts; unreceipted orphan derived outputs are discarded and deterministically recomputed, while receipts missing their exact output fail closed. Restart reuses only validated exact receipts. The final run fingerprint binds validated receipt identities. No permanent broad minute-feature lake is authorized or created.

Frozen mechanics are implemented exactly: an information-safe signal enters at the first observed eligible regular-minute open within five minutes measured from the decision time; stops are strategy-specific; target is 2R; exact target opens resolve at the target before later intrabar ambiguity; stop gaps use the worse open; target gaps receive no improvement; same-bar unresolved stop/target collisions are adverse-stop-first; 15:55..15:59 provides the fixed time exit. The 0/10/25/50/100-bps all-in grid remains adverse by side. Short gross/net returns and MFE/MAE are normalized to entry notional. Entered-but-unresolved opportunities preserve signal/entry/stop/target/excursion evidence while remaining excluded from completed-return claims. The optimized setup scan only reduces repeated evaluation calls; final fired results are confirmed by the unchanged B34 evaluators.

PIT market regime remains `UNAVAILABLE` wherever this minute replay does not have an exact accepted prior-session regime join; it is never guessed. Short signal outcomes may later be RESEARCH-profiled, but A34 portfolio admission remains long-only until borrow/locate/recall economics are accepted. This package does not complete the later conditional-profile/selector analysis.

**Source-only workstation gate ACCEPTED (2026-09-08).** On merged `main` commit `4cf27ae9d23ac3b5d1821200e4d303db787f361a`, the canonical `2016-01-04..2026-04-30` source-only run selected exactly `59,768` minute units. Source fingerprint = `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`; split-evidence fingerprint = `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`; active B35 fingerprint = `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`. The run created no DEVELOPMENT outcome authorization and opened no B35 outcomes. Consumed-master rows permitted/read `0/0`; future-blind rows permitted/read `0/0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`. DEVELOPMENT scoring still ends `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval remains permanently unavailable for B35 fitting/scoring/qualification; the future blind beginning on/after `2026-09-08` remains unopened.

**Canonical DEVELOPMENT replay ACCEPTED (2026-09-11).** The one authorized replay completed `482/482` deterministic groups and `59,768/59,768` frozen source units with exactly `482` validated receipt ids. It produced `20,171,286` fired opportunity/context/outcome records and run fingerprint `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`. Bound identities remained unchanged: B35 fingerprint `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`, source fingerprint `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`, split fingerprint `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`, and authorization `562d7104d56151e6203a1bf85457f9d1a90bbf19e60cd4d9359a3f96bc0a7be5`. Consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`; no permanent minute feature lake was created. Aggregate fired/comparable counts were: gap continuation `2,875,318 / 1,811,231`; opening-range breakout `16,982,463 / 12,626,529`; premarket relative-volume consolidation `313,447 / 309,304`; highest-volume-day style `58 / 58`. These are replay coverage counts, not profitability conclusions.

The canonical continuation reused 82 validated groups and computed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**. This was about **6.43x** the original ~660.6-unit/hour serial restart and **44.3% faster** than the accepted 2,942.2-unit/hour isolated 10 x 1 equivalence benchmark, saving about **63.4 hours** versus serial processing of the remaining work.

**B35 condition/selector analyzer status (2026-09-11): IMPLEMENTED / ACCEPTANCE PENDING in PR #76.** The analyzer consumes only the completed compact DEVELOPMENT group artifacts and first revalidates the final replay summary, exact receipt set and every group-output SHA. It normalizes the 20,171,286 compact records once into an atomic, hash-receipted Parquet view, computes standalone strategy and frozen condition/interaction evidence across the full `0/10/25/50/100` bps cost grid, and constructs walk-forward folds from the complete XNYS calendar rather than opportunity-bearing dates. Training-cell eligibility remains exactly `60` opportunities / `30` sessions / `20` instruments; selector scoring remains the deterministic 5th percentile of `1,000` XNYS-session-cluster bootstrap mean net-R outcomes at `50` bps. The fallback hierarchy backs off only for insufficient support; a supported cell with nonpositive or undefined score abstains and cannot be rescued by a broader positive cell. Same-fold standalone baselines are recorded beside the out-of-sample selector profile. Derived analysis artifacts are atomic, restartable and self-hash/SHA receipted. This package opens no new outcomes and grants no strategy/selector promotion, PAPER/LIVE, provider, broker, consumed-master or future-blind authority. BH-FDR/Deflated-Sharpe/PBO-CSCV and tail/portfolio robustness remain required before any promotion decision.

Next Track-B sequence: (1) accept/merge PR #76 only after exact-head Windows+Ubuntu regression is green; (2) run `.\.venv\Scripts\python.exe scripts\run_b35_evidence_analysis.py` once against the already-completed compact B35 artifacts—**do not rerun the minute replay**; (3) review standalone strategy, frozen condition-cell and out-of-sample selector results, including HVD's known sparse 58-opportunity coverage; (4) complete the preregistered multiplicity/robustness and portfolio-level diagnostics before any promotion claim; (5) perform the bounded diagnostic/calibration review while preserving every v1 result; (6) freeze the eight-new-family successor contract and confluence schema before opening their outcomes; (7) later evaluate the genuinely new future blind only after required accrual and without refitting on it; and (8) never reuse the consumed master interval. Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.

### B36 — Literature-Anchored Reference Library

After the product loop works, research and rank established mechanisms—cross-
sectional momentum, time-series momentum/trend, short-term reversal, volatility
management, quality/profitability, value/quality composites, PEAD/revisions, and
other credible families—by replication breadth, costs, persistence, ATLAS data
compatibility, PIT risk, retail suitability, and diversification. Add only a small
diverse batch with frozen formulations.

### A37 — Production Web Application and Operations

Consolidate the Python engine and browser control plane; promote PostgreSQL
operational state only after schema/migration/recovery/ownership acceptance; add
scheduling, observability, backup/recovery, deployment, authentication/authorization,
and parity tests. The complete application may remain PAPER-only indefinitely.

### A38 — Qualifying PAPER and LIVE Readiness

For historically validated frozen strategies only, complete a prospectively defined
qualifying PAPER program while hardening provider/broker outage, fills, reconciliation,
buying-power drift, database/network/restart, emergency disable/flatten, and manual
fallback. No LIVE authority until the complete gate passes. The accepted live
operator dashboard remains required throughout qualifying PAPER.

### Phase39 — Controlled LIVE Activation

Enable LIVE only after explicit operator authorization for `LIVE_ELIGIBLE` versions,
with deliberately small exposure, hard risk/loss limits, reconciliation/health,
kill capability, and evidence-based scaling. This phase may never be reached; a
complete PAPER-only ATLAS remains a valid product.

### Continuing Track B — Research Lab

After the reference library, continue academic mechanisms, event/SEC research,
options, alternative ML, news/NLP, regime science, cross-sectional models, and new
data sources by research value per unit effort. Each experiment is finite,
preregistered, versioned, and stoppable. No research delay globally blocks the
finished product.

## 19A. Practitioner strategy-library expansion, confluence, and calibration

**Status: PLANNED SUCCESSOR WORK; B35 DEVELOPMENT REPLAY CLOSED / ACCEPTED; B35 CONDITION/SELECTOR ANALYZER ACCEPTANCE ACTIVE.**
The completed four-strategy B35 DEVELOPMENT result is immutable historical evidence
and must not be rewritten for rescue tuning. ATLAS already has **six accepted daily practitioner families** in the
A33/B33 reference catalog plus **four frozen B34 intraday/opening families**. The next
library package therefore targets **18 total families by adding eight new mechanisms**,
not by cloning the existing Golden Cross, EMA, MACD, RSI, Donchian or Bollinger-squeeze
work under new ids.

### 19A.1 Retained ten-family base

A33/B33 retained families and exact existing policy ids:

- Golden Cross / 50-200 SMA trend transition — `ma_trend_cross_50_200_long_v1`.
- 20/50 EMA pullback continuation — `ema_pullback_20_50_long_v1`.
- 12/26/9 MACD momentum shift — `macd_shift_12_26_9_long_v1` and
  `macd_shift_12_26_9_short_v1`.
- RSI(14) trend-filtered recovery — `rsi_recovery_14_trend_long_v1`.
- 20-session Donchian high-volume breakout —
  `donchian_breakout_20_volume_long_v1` and
  `donchian_breakout_20_volume_short_v1`.
- 20-session Bollinger squeeze breakout —
  `bollinger_squeeze_breakout_20_long_v1` and
  `bollinger_squeeze_breakout_20_short_v1`.

B34/B35 retained families:

- `b34_gap_continuation_v1`;
- `b34_opening_range_breakout_15m_v1`;
- `b34_premarket_relvol_consolidation_v1`;
- `b34_highest_volume_day_style_v1`.

These accepted/frozen versions remain immutable historical hypotheses. Successor
research may create explicitly versioned v2 candidates after diagnostic review, but
must never silently rewrite v1.

### 19A.2 Eight genuinely new families

Freeze under a new successor fingerprint before opening any new performance:

- `pract_bollinger_mean_reversion_v1` — Bollinger excursion plus deterministic
  rejection/re-entry; band touch alone does not fire.
- `pract_atr_volatility_expansion_v1` — normalized low-ATR/range consolidation
  followed by directional range/price expansion; ATR supplies volatility/risk, not
  direction.
- `pract_vwap_reclaim_reject_v1` — closed-bar intraday VWAP reclaim-and-hold long
  profile and mirrored reject short research profile.
- `pract_pivot_sr_breakout_v1` — confirmed breakout of deterministic structural
  pivot support/resistance; volume/OBV participation retained as separate evidence.
- `pract_head_shoulders_v1` — objective five-pivot H&S/inverse H&S with frozen
  shoulder similarity, head prominence, spacing, prior-trend and neckline rules;
  neckline break required.
- `pract_double_top_bottom_v1` — two separated level tests, material intervening
  reversal and neckline/support/resistance break required.
- `pract_flag_pennant_v1` — objective impulse leg, bounded continuation consolidation
  with frozen retracement/contraction geometry, then same-direction breakout.
- `pract_triangle_breakout_v1` — deterministic repeated-pivot converging boundaries,
  ascending/descending/symmetrical classification and information-safe breakout.

For every new family freeze before performance: exact timeframe/bar authority;
indicator definition; lookback/minimum history; pivot algorithm; normalized geometry
and tolerances; entry clock; duplicate-signal rule; stop/target/time exit; costs;
long/short authority; sample/coverage minimums; condition dimensions; robustness
perturbations; and trial/fingerprint identity. Chart patterns use one deterministic
shared pivot/geometry engine. Manual visual labeling is forbidden.

### 19A.3 Confluence is evidence, not vote counting

A strategy's fired/not-fired state remains immutable and independently testable.
Confluence consumes those signals plus point-in-time context without rewriting the
underlying strategy. Preserve primary strategy/direction, raw same-direction signal
count, distinct evidence-family count, exact contributors, opposing evidence,
estimated costs, signal age and relevant PIT context.

Evidence families are at least **trend**, **momentum**, **volume/participation**,
**price structure**, **volatility**, **chart pattern**, and **context/regime**.
Correlated indicators within one family are capped/regularized or otherwise prevented
from multiplying confidence. Five trend indicators are not equivalent to independent
agreement across trend, volume, structure, volatility and regime.

Do not initially create redundant composite strategies such as a separate EMA+MACD
rule solely because both already exist. Keep EMA pullback and MACD shift standalone,
then measure whether same-direction agreement adds value in the confluence layer.

Evaluate three preregistered systems: **standalone**, **hard-confirmation variant**,
and **confluence ranking**. Start with transparent stratified outcome tables, not
hand-designed point scores. If evidence supports it, a later conventional model may
estimate calibrated probability and/or net expectancy from training-only walk-forward
features with leakage guards, regularization and explicit baselines. The operator UI
may show a 0-100 strength only when it maps to a documented calibrated probability,
percentile or frozen score.

Confluence earns authority only if untouched evidence shows improvement over
standalone strategies in probability/expectancy, downside and/or capital efficiency.
If extra confirmation only reduces sample size or arrives too late, retain the simpler
strategy.

### 19A.4 Post-result diagnosis and bounded refinement

Every v1 receives a structured post-result review whether positive or negative.
Slice by regime, liquidity, price band, time, volatility, setup intensity, entry
delay, MFE/MAE, stop/target behavior, cost drag, unresolved/no-entry rate,
concentration, losing streak and confluence/conflict state. This is failure/opportunity
attribution, not retrospective threshold shopping.

Default calibration budget: **no more than three materially distinct v2 candidates
per family per research cycle**. Each successor must state the observed failure mode,
practitioner/statistical rationale, exact rule change, total trial count and untouched
evaluation source before performance is opened. Dense grids and tiny threshold
stepping are prohibited. Preserve v1. Data that motivated v2 may diagnose/train but
cannot independently validate v2; promotion requires fresh walk-forward or other
untouched evidence under a new trial/fingerprint. Consumed master evidence is never
reused and blind windows are never reassigned after results are known.

### 19A.5 Efficient shared implementation

Use one point-in-time primitive/context layer for OHLCV, SMA/EMA, RSI, MACD,
Bollinger statistics, ATR/ATRP, VWAP, relative volume/OBV, rolling highs/lows,
deterministic pivots, regime/liquidity and session context. Feed immutable views to
independent strategy evaluators. Reuse process-local infrastructure and parallelize
independent work under the validated ATLAS efficiency protocol. Avoid redundant full
feature lakes and repeated expensive scans when exact-equivalent shared computation
is possible. Golden-output/receipt equivalence remains mandatory whenever execution
mechanics change.

### 19A.6 Ordered successor work after B35

1. **COMPLETE (2026-09-11):** close and validate the B35 canonical replay; all
   482 groups / 59,768 units completed with zero protected/future/provider/broker
   leakage, immutable run fingerprint, and final 4,246.7-unit/hour production rate.
2. **NEXT:** produce the preregistered B35 strategy x condition evidence and selector result.
3. Freeze the exact **eight-new-family** successor contract and confluence feature
   schema; bind the six daily plus four B34 families as retained baseline lineage.
4. Implement shared PIT indicators/pivots and the eight independent new evaluators;
   run source-only, semantic and exact-equivalence tests.
5. Run expanded DEVELOPMENT evidence with standalone strategies first.
6. Evaluate hard confirmation and confluence as separate hypotheses, including
   redundancy, conflict, costs and sample-size effects.
7. Perform one bounded diagnostic/calibration cycle; preregister up to three justified
   v2 candidates per family and evaluate them only on untouched evidence.
8. Promote nothing automatically. Survivors become candidates for the next
   prospective/PAPER evidence gate; failures stay in the ledger and guide the next
   research family.

This Track-B expansion does not block Track A product completion. PAPER plumbing may
advance independently under its own authority while strategy research continues.

## 20. Phase/package cadence and progress reporting

### Validated efficiency protocol for long-running ATLAS work

B35 establishes a reusable engineering gate for runtime-sensitive deterministic and research workloads. Future packages should adapt this pattern to their own correctness contract rather than copying B35 mechanics blindly:

- capture real target-hardware baseline throughput and restart state before optimization;
- make canonical work atomic, restartable, and receipt/checkpoint validated before performance experimentation;
- keep scientific/correctness semantics and runtime mechanics explicitly separated;
- benchmark plausible bottlenecks independently, including process concurrency, library threading, storage scans, Python/object conversion, and safe process-local resource reuse;
- run optimization candidates against isolated completed golden work and require the strongest practical equivalence proof, with exact output hashes plus scientific receipt-field parity preferred for deterministic artifacts;
- change one execution layer per experiment, reject regressions, and retain enough evidence to prevent repeating failed approaches;
- empirically choose the fastest scientifically equivalent worker/thread/resource shape on the actual host while preserving OS/operator headroom;
- permit reusable operational infrastructure but never trade away source/hash verification, fail-closed validators, protected-data controls, required schema/model validation, or authority boundaries for speed;
- keep all benchmark/progress artifacts non-authoritative and prevent parallel completion order from becoming scientific ordering;
- once accepted, resume the canonical workload from every valid checkpoint rather than rebuilding successful work; and
- after completion, record actual sustained runtime/throughput and compare it with the probe so future workload sizing uses observed evidence.

The B35 reference case improved the measured serial restart from about **660.6 units/hour** to an isolated exact-equivalent **2,942.2 units/hour** at 10 x 1, roughly **4.45x faster**, while preserving 10/10 sampled output hashes and all frozen scientific and authority semantics. The accepted canonical continuation then reused 82 valid groups and completed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**—about **6.43x the original serial rate**, **44.3% faster than the accepted isolated benchmark**, and about **63.4 hours saved** versus serial processing of the remaining work. The equivalent full 59,768-unit workload at that sustained rate is about **14.1 hours** versus roughly **90.5 hours** serial. A seemingly attractive single-Parquet-scan rewrite was retained as a negative optimization result because it fell to **820.8 units/hour** despite exact equivalence. This combination—measure, isolate, prove equivalence, benchmark, reject regressions, preserve restart state, resume, then record actual production performance—is the default ATLAS efficiency pattern when long-running work becomes a material project bottleneck.

**Runtime observability and execution-efficiency standard.** Long-running workstation commands must never be silent. They must emit a flushed start timestamp/PID/scope/execution profile; completed/total groups or units, percentage, elapsed time, restart-reused work and throughput; a timestamped heartbeat at least every 60 seconds; ETA after a sufficient stable sample or an explicit unavailable state; and terminal COMPLETE/FAILED/INTERRUPTED timestamp plus total elapsed time. The same operational state must be written atomically to a machine-readable status artifact for second-terminal and browser-GUI inspection. These fields are **NON_AUTHORITATIVE** and are forbidden from scientific fingerprints, group/receipt identities, strategy decisions, source authority, or qualification evidence. Receipt/output validation and the final frozen summary remain authoritative. Performance work may increase concurrency, vectorization, filtering, caching, or I/O efficiency only when an equivalence gate proves that the frozen scientific output is unchanged. Runtime targets never justify reducing data coverage, validation strength, or research quality.

One coherent package uses:

`PLAIN-ENGLISH START → DEFINE/FREEZE AUTHORITY AND SCIENCE → IMPLEMENT LARGEST SAFE
PACKAGE → FOCUSED TESTS → ROOT-CAUSE REPAIR → EXACT-HEAD FULL ACCEPTANCE →
PLAIN-ENGLISH END → UPDATE BOTH LIVING DOCS IN THE SAME COMMIT → MERGE →
POST-MERGE VERIFY`

Operator checkpoints are reserved for destructive actions, external authority,
broker/provider mutation, qualifying PAPER/LIVE activation, protected evidence, or
material ambiguity. Internal implementation does not need a conversational gate.

Every repository-changing package must update both living documents before merge.
Documentation is part of the implementation package, not a later clerical task.
Each update must leave an auditable handoff including the package goal, what code/
product capability changed, test and CI result when known, empirical/scientific
result if any, exact authority gained or not gained, protected-read/write state,
known limitations, and the next highest-value package. If either living document is
stale, the package is not complete.

Every closeout reports:

- functioning product progress: strategy implemented, replay completed, candidate
  generated, portfolio/trade constructed, PAPER event processed, position managed,
  outcome recorded, statistics/calibration updated, dashboard/control working;
- scientific controls: PIT, costs, lookahead, trials/multiplicity, dependence,
  folds, concentration, protected reads, fingerprints, reproducibility;
- exact authority gained or not gained;
- negative results and unresolved risks;
- next highest-value coherent package.

## 21. Immediate next action

1. **COMPLETE — V1 historical database decommission.** The confirmed workstation
   run deleted exactly **8 targets / 38,034 files / 147,206,406,678 bytes (137.10
   GiB)** and retained
   `data/checkpoints/alpaca_v2_migration/v1_decommission_receipt.json`. Source code,
   Git history, `data/live`, `data/models`, and unrelated research state were outside
   the deletion scope. ATLAS currently has no accepted historical market database.
   The subsequent read-only inventory exposed residual V1 database layers that were
   not in the first eight-target plan (`raw/day_aggs_v1`, legacy Alpaca payloads,
   training/discovery/universe/regime/quality/reference outputs, and old manifests).
   They are now in a separate exact hash-bound residual plan; its receipt is
   plan-hash-specific so the original 137.10 GiB deletion receipt cannot be overwritten.
2. **COMPLETE NATIVE CAPTURE / ACCEPTANCE PENDING — fresh native V2 acquisition.**
   The single
   `--build-v2` coordinator performs confirmed residual cleanup, freezes the last
   completed XNYS session, captures fresh active/inactive Alpaca assets and
   complete-quality corporate actions, freezes an exact-literal universe and plan,
   then executes deterministic yearly `1Day`/100-symbol units before monthly
   `1Min`/100-symbol units. Every provider page is durably checkpointed with exact
   compressed response evidence, request semantics, checksums, normalized Parquet,
   anomaly evidence, opaque next token, and restart state. Completed unit source and
   canonical hashes are verified before a resume skip. Invalid provider literals are
   globally quarantined without mapping or substitution. Unit compaction uses the
   canonical market schema and exchange schedule; duplicates block that unit rather
   than being silently collapsed. A 30 GiB reserve plus transient-work guard pauses
   safely. No V1 persisted row is a V2 input. Synthetic daily/minute end-to-end,
   page-token resume, corruption fail-closed, rejection quarantine, and cleanup-scope
   package was accepted in PR #57. The operator run finished all **67,480 / 67,480
   units**: **5,302 daily**, **62,178 minute**, **3,897,688,734 canonical rows**, and
   **1,757,288 quarantined rows**. Its terminal status is `COMPLETE`, but this remains
   isolated candidate capture: identity, quality, quarantine attribution, analytical
   acceptance, and production promotion have not passed merely because acquisition
   ended.
3. **NEXT OPERATOR RUN — V2 daily post-build foundation.** After pulling the accepted
   corrected package, run `scripts/run_alpaca_v2_postbuild.py`. It
   hash-verifies source/plan/every unit, validates all daily rows, constructs
   conservative identity/lifecycle evidence, acquires resumable provider-native
   split-adjusted daily bars, reconciles them to raw, and writes the isolated
   research-daily manifest. Stable content fingerprints make a clean rerun
   idempotent. `--validate-only` makes no provider request; `--max-hours` checkpoints
   adjusted-daily acquisition. Do not run this concurrently with native acquisition.
4. **RECOMMENDED EXPLICIT CONTINUATION — DEVELOPMENT plus frozen walk-forward.** Run
   `scripts/run_alpaca_v2_postbuild.py --through-walk-forward-replay
   --authorize-master-holdout-consumption` as one command. It first completes the
   frozen nine-policy and A34 account DEVELOPMENT replay through `2026-05-11`. Only
   after that succeeds does it persist irreversible consumption evidence, create the
   separate walk-forward view, and evaluate signals from `2026-05-12` through the
   exact accepted source cutoff. The holdout remains consumed after any later failure.
   Every superseded consumption state is preserved beneath
   `manifests/master_holdout_consumption_history/` before the current receipt changes.
   Retry attempts keep known protected-row counts; a completed replay is verified and
   reused, while missing or damaged receipt/history/result evidence stops safely.
   Historical replay is never relabeled as prospective PAPER; no strategy promotion,
   broker write, PAPER submit, or LIVE authority is granted. Omitting both flags opens
   no performance; `--through-reference-replay` remains the DEVELOPMENT-only option.
5. Review the actual post-build exclusion, identity, coverage, split-factor, disk,
   and replay reports. Record pass/fail honestly before any strategy revision. Daily
   indicators are computed by the frozen engine on demand; do not first build a
   redundant full feature lake. Continue A34.5 Product work in parallel regardless
   of strategy profit.
6. **COMPLETE — B34 intraday readiness and frozen opening/premarket pack.** Final workstation evidence is `ACCEPTED`; repository acceptance retains the enhanced evidence hash, earlier semantic evidence hash, and frozen strategy-pack fingerprint without opening outcomes or trading authority.
7. **CURRENT Track-B gate — complete the resumed canonical B35 DEVELOPMENT replay using the accepted execution path.** PR #72 is merged as `4a2ec3fcfb33c375a7b883ae8b3473e82fa29f6f`. The fastest tested scientifically equivalent workstation configuration is **10 workers x 1 DuckDB thread** with process-local DuckDB/calendar reuse and `itertuples()` canonical-bar conversion while retaining full per-minute `CanonicalBar.model_validate()`. The final isolated real-data probe passed **10/10 exact JSONL SHA-256 comparisons** at **2,942.2 units/hour**, versus about **660.6 units/hour** on the measured serial restart, approximately **4.45x faster**. The canonical run has resumed from **82 validated groups / 10,168 units** under the unchanged authorization `562d7104d56151e6203a1bf85457f9d1a90bbf19e60cd4d9359a3f96bc0a7be5`, trial `b35.dev.20160104_20260430.eb3b7ff9f417.registration`, frozen `2016-01-04..2026-04-30` source, zero consumed-master/future-blind reads, and zero provider/broker/PAPER/LIVE or promotion authority. Final canonical runtime/throughput will be recorded on completion; after successful B35 completion, proceed to strategy x condition evidence and the preregistered selector, then freeze and implement the eight-new-family successor package that expands the retained ten-family base to 18 total families, plus the separate confluence/strength layer defined in Section 19A. The active B35 result must not be retroactively mixed with those new hypotheses.

8. Keep focused tests, the full repository suite, retained scientific validators,
   cross-platform exact-head CI, and same-commit updates to both living documents
   mandatory for every package.

The destination is concrete: open the GUI, see versioned strategies operating,
watch candidates become or fail to become trades, see positions and P&L change,
understand why ATLAS bought or sold, replay the same lifecycle historically, PAPER
trade through the real product path, inspect every decision and outcome, learn which
families retain credible conditional expectancy, and improve the library while LIVE
capital remains strongly protected.

## 22. Retained exact historical validator statements

These literals preserve accepted phase-validator recognition. They describe the
closed historical state and do not restore the superseded product dependency:

- Exactly five hypotheses were frozen before performance under policy fingerprint `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.
- Frozen finalist: `solvency_distress_short`; source evidence: 46 event rows / 33 signal sessions / 40 unique instruments versus 50 / 20 / 20.
- Protected stock/SPY returns remain unread.
- Historical supported alpha remains **zero**.
- Accepted foundation through Phase32; Completed Pre-Phase33 SEC XBRL; Phase33 — Signal-to-Trade Construction; Phase39 — Controlled LIVE Activation.
- The historical successor was required to use a materially different point-in-time fundamental-information mechanism.
- The historical XBRL successor may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result.
- V2 split-price quantization repair: the real completed V2 source showed that the
  former absolute `1e-5` OHLC-factor equality was also too strict for provider-rounded
  split-adjusted prices. The retained quantization diagnostic covered 2,825,114 paired
  eligible rows: maximum adjusted-price residual was `$0.05841364` and maximum
  relative factor error was `0.000994532`. Reconciliation now fails closed unless each
  open/high/low value is within `$0.10` adjusted-price residual **and** `0.001` relative
  factor error of the close-derived split factor. A new regression accepts bounded
  provider rounding while the existing corruption regression still rejects a material
  price-factor mismatch. No source bytes, strategy/portfolio policy, holdout receipt,
  protected-return state, PAPER authority, or LIVE authority are changed.
