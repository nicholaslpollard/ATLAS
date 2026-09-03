# ATLAS Master Roadmap and Research/Product Source of Truth

**Current as of 2026-09-03 (UTC). This roadmap and the root `README.md` are the
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

Accepted daily historical boundary remains Alpaca SIP through `2021-08-13` and
Massive from `2021-08-16`. Provider boundaries must remain explicit. Multi-provider
data is not automatically invalid. Pre-2021 intraday history must not be fabricated.

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

- Master protected window: `2026-05-12..2026-08-11` — **unconsumed**.
- Retained branch protected return reads: **0**.
- No strategy currently has `HISTORICALLY_VALIDATED`, `PAPER_VALIDATED`,
  `LIVE_ELIGIBLE`, or LIVE-authorized status.
- Operational PAPER may be built and used with labeled baselines under its own
  explicit controls, but actual A35 PAPER testing is blocked until A34.5 operator
  live observability is accepted.
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
  `26a2892a4c4bb5597d2e688e78be8cb7da4fc656872a30fe887cf60669476cb8`.
- trusted-lake adapter:
  `reference-lake-adapter-v1-massive-development-split-free-identity-exact`.

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
- Preserve the existing master protected window; use a newly declared future
  confirmation policy for the practitioner program.
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
7. Protected performance is finalist-only; a read consumes the governed holdout for
   later selection.
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

**Implementation status (2026-09-03): reference foundation and first trusted-lake
adapter complete; empirical run not started.** The separate catalog contains six families and nine
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
`/api/v1/strategies/reference`. The runner hard-rejects the retained master
protected dates before feature work and has zero provider/broker/PAPER/LIVE writes.
The read-only adapter contract
`reference-lake-adapter-v1-massive-development-split-free-identity-exact` scans
accepted canonical partitions without provider calls or writes. Its V1 scope is the
Massive-only DEVELOPMENT interval `2021-08-16..2026-05-11`: exact XNYS partition
and regular-open semantics, retained reference metadata no later than the run end,
authoritative-or-unique identity, no current active/delisted filter, and complete
split-report/hash reconciliation. Because accepted canonical bars are unadjusted,
V1 excludes every split-touched identity and every stream with an internal session
gap; retained factor-1 streams are exactly equivalent to split-adjusted prices.
Pre-seam Alpaca and split-affected instruments require a later validated V2 rather
than guessed factors. The canonical provider timestamp remains the regular-open
stamp, while contract
`reference-signal-availability-v1-xnys-regular-close-next-open` adds the true XNYS
close availability time for daily signals. The runner records that close clock and
still enters no earlier than the next regular-session open. The current checkout has
no market lake, so no empirical run or ATLAS performance result has been produced.
PR #47 accepted the adapter and merged it as
`646db6e6e44ccd2355c7c2263221f35cd01d5da8`; post-merge Windows and Ubuntu full
tests passed. Protected return rows read: **0**; performance opened:
**false**; provider/broker/PAPER/LIVE writes: **0**.

### A34 — Signal-to-Trade Construction, Portfolio Replay, and Replay Dashboard

This replaces the former global alpha-blocked **Phase33 — Signal-to-Trade
Construction** dependency. Construct complete candidate trades, compare strategies,
admit a risk-controlled account portfolio, replay cash/orders/positions/exits as one
process, and show decisions, counterfactuals, costs, exposure, and outcomes in the
browser. Baselines remain operational-only unless separately validated.

**First vertical-slice status (2026-09-03): implemented; empirical account replay
not started.** Frozen portfolio-policy fingerprint:
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
the regime writer. Ticker and sector regime context remain `UNAVAILABLE` until an
accepted PIT ticker-state join and PIT instrument-to-sector map exist. Remaining
A34 context work is therefore ticker, sector, and correlation control only after
their evidence contracts exist; none should delay the first honest fixed-policy
replay on the trusted lake.

PR #51 merged the exact PIT market-regime context as
`e2dd741b4cdd3f5b729c4ec1cb510451887c748c`; its post-merge `main` test workflow
passed. This preserves zero protected reads and zero provider/broker/PAPER/LIVE
writes.

### A34.5 — Operator Live Observability and Paper Dashboard Gate

**New hard prerequisite established 2026-09-03 before Operational PAPER.** Extend
the authoritative stacked Phase19 browser/control plane from historical/research
inspection into the near-live operator surface that will be used during A35. The
front end must be connected before PAPER broker testing begins so the operator can
see the product acting rather than infer behavior later from logs.

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

### A35 — Operational PAPER and Operator Web Beta

**May begin only after A34.5 is accepted.** Run the same engine prospectively with
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

Build the walk-forward condition profiles and frozen selector challenger; compare it
to simple family baselines. Add strategy management, calibration, degradation,
regime, slippage, portfolio contribution, and trials-ledger views. Learning may
recommend but never self-promote.

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

## 20. Phase/package cadence and progress reporting

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

1. The operator may reclaim space now with the explicit database-only V1
   decommission mode. It produces an exact allowlisted SHA-256-bound manifest,
   requires its derived confirmation token, rejects symlinks/path drift, preserves
   live/model/unrelated-research state, retains a completion or partial-failure
   receipt, and then stops. It does not acquire bars, identities, or corporate
   actions; the combined delete-and-rebuild path remains code-locked.
2. Implement deterministic native `1Day` then native `1Min` acquisition units with
   raw response evidence, request-policy fingerprints, checksums, retries, pagination,
   checkpoints, and restart-safe idempotency. No V1 persisted row may fill a V2 gap.
3. Build V2 PIT identity/lifecycle and corporate-action layers covering splits,
   reverse splits, dividends, symbol/name changes, mergers, delistings, and spin-offs;
   ticker text alone must never establish identity.
4. Canonicalize and validate each base independently, remeasure actual disk use, then
   allow derived bars/features only if the phase-specific peak plus reserve passes.
   Promotion is an explicit config/path switch after full acceptance, never a merge
   into V1 paths.
5. After the V2 foundation is accepted, run the nine frozen practitioner policies on
   DEVELOPMENT data and continue A34.5/A35 Product work. Database work does not grant
   historical, PAPER, or LIVE authority; protected reads remain zero and LIVE stays
   disabled. The retained A34 contract continues to treat ticker and sector regime
   context as unavailable rather than guessing labels.
6. Keep focused tests, the full repository suite, retained scientific validators,
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
