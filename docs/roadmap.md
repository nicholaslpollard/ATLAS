# ATLAS Master Roadmap and Research/Product Source of Truth

**Current as of 2026-09-17 (UTC). This roadmap, the root `README.md`, and
`docs/strategy_evidence_register.md` are the three living project documents.**

This document replaces the pre-Review roadmap after ATLAS Review Chat 3. It keeps
all valid evidence and safeguards while correcting the process drift that made
unsuccessful alpha research a global blocker for the product.

## 1. Document authority and continuation

Every continuation chat must read the root `README.md`, this roadmap, and
`docs/strategy_evidence_register.md` in full before recommending or changing
anything. Update README and roadmap whenever mission, current state, authority,
roadmap order, active work, material evidence, or implemented capability changes.
Any package that opens, changes, interprets, closes, calibrates, or promotes strategy
evidence must also update the Strategy Evidence Register in the same package. A
future chat must be able to reconstruct current product state, research direction,
and strategy evidence from these three files without depending on a prior chat. Do
not create another competing current-status, handoff, plan, roadmap, evidence
register, or living README.

All older README and roadmap files were moved verbatim to
`docs/archive/2026-09-02-pre-product-rebaseline/`. The old `docs/current_status.md`,
`docs/phase_flow.md`, and `docs/phase_plain_english_contract.md` remain only as
frozen compatibility snapshots for accepted historical validators; exact originals
are in the same archive. All other documentation is immutable specification,
research, incident, or acceptance evidence. It may be cited but must not silently
become a competing current plan.

If the three living documents conflict, progression fails closed until they are
reconciled. Code and tests remain the authority for actual behavior; Git history and
accepted artifacts remain the authority for what happened. A code or research
package with stale applicable living documents is incomplete even if its tests pass.

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
- **Canonical Parquet/DuckDB V2 lake:** primary broad historical/research source and
  large-universe discovery substrate; external providers are the current/live interface,
  not a replacement for the validated analytical lake.
- **Alpaca market data:** primary live/current stock and option market-data provider;
  REST narrows/discovers and WebSockets are allocated selectively to finalists,
  pending orders and open positions under explicit feed-quality/freshness evidence.
- **Massive:** historical provenance/reproducibility remains immutable; any retained
  free access is diagnostic/research-only and is not a required runtime dependency or
  trading-authority source.
- **Official SEC EDGAR/XBRL:** read-only regulatory provenance only within an
  explicitly authorized source contract.
- **Webull:** primary PAPER/sandbox and intended primary LIVE broker only after
  separate acceptance; secondary live/current market-data fallback when its API
  entitlement and feed quality satisfy the requested evidence.
- **Alpaca execution:** explicit/manual secondary execution broker. Market-data
  primacy does not create execution authority. No automatic broker failover.
- **ML:** predictive evidence and ranking, never standalone trading authority.
- **AI:** independent review/challenge, never unilateral trading authority.
- **Browser GUI:** operator surface over the same engine, never a second trading
  engine. It may format and aggregate authoritative records but must not maintain a
  separate trading truth or independently recompute trading decisions.

The decommissioned V1 daily lake used Alpaca SIP through `2021-08-13` and
Massive from `2021-08-16`; this is retained historical provenance only. The current
isolated V2 candidate base uses Alpaca SIP throughout its frozen source interval and
forbids V1 rows or derived-state ancestry. V2 minute semantics and the initial opening/premarket strategy pack are accepted by B34; missing history may not be invented, and performance remains separately gated.

### Live/current market-data transport policy — 2026-09-16

ATLAS now separates its durable analytical lake from its live market interface. The
canonical Parquet/DuckDB V2 lake remains the broad historical/research source used for
large-universe discovery and replay. **Alpaca is the primary live/current market-data
provider; Webull is the secondary live/current fallback where its API entitlement and
feed quality are sufficient.** Execution remains a separate concern: Webull is the
planned primary PAPER/LIVE execution broker and Alpaca remains the explicitly selected
manual execution fallback. Automatic broker failover remains prohibited.

Massive is no longer a required forward runtime dependency. Any retained Massive free
access is diagnostic/research-only and carries no trading authority; historical Massive
source provenance and reproducibility paths remain immutable evidence and are not
rewritten. Tradier and unofficial Yahoo/yfinance feeds are not part of the supported
operating-provider chain.

Live transport is intentionally selective rather than market-wide. Broad discovery
runs locally first; REST/API snapshots refresh the narrowed candidate set and obtain
option-chain/contract evidence; WebSocket subscriptions are then allocated where
seconds matter economically: final candidate validation before entry, pending orders,
open positions, and exits. REST remains the normal overflow and recovery path when a
candidate does not receive a streaming slot or a stream is degraded. One provider
connection may multiplex many symbol/contract subscriptions; subscription capacity,
not one-connection-per-candidate, is the managed resource.

Streaming priority is: **open positions and pending orders first; entry-ready finalists
second; strong near-finalists third; lower-ranked candidates by REST; broad discovery
from the local lake.** A central market-data coordinator must own the stream/REST budget,
share one underlying subscription across related option candidates, apply hysteresis or
minimum residency so nearly tied candidates do not thrash subscriptions, and dynamically
promote/demote candidates as ranking changes. A WebSocket failure degrades first to a
fresh same-provider REST snapshot, then to the accepted secondary provider when
available, and finally to `DATA_UNAVAILABLE`/abstention rather than invented market
state.

Every live observation must retain provider, feed, transport, market timestamp,
receive timestamp, freshness/age, and quality/provenance. Current Alpaca Basic limits
verified on 2026-09-16 are **30 equity WebSocket symbols** on the real-time IEX stock
feed and **200 option quote subscriptions** on the indicative option feed, with REST
rate capacity treated as a separate budget. These are operational entitlements, not
scientific constants: the coordinator must configure/discover current provider limits
rather than hard-code them permanently. The then-current paid Alpaca plan raises stock
streaming to unlimited symbols and option quote streaming to 1,000 with consolidated
U.S. equities/OPRA-quality access; ATLAS does not require that paid plan until the
system's economics justify supporting its own data subscription.

For options, the intended sequence is `underlying shortlist -> REST option-chain
snapshot/Greeks/liquidity -> small contract finalist set -> underlying + finalist
WebSockets -> entry -> held-contract/underlying streams through exit`. If finalists
exceed streaming capacity, the coordinator streams the highest-priority subset and
keeps the remainder current through rate-aware REST polling. Provider transport choice
must not alter strategy authority, economics, portfolio-risk gates, or execution truth.

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
20. Every repository-changing implementation package updates README and roadmap before acceptance/merge; any package changing or interpreting strategy evidence also updates the Strategy Evidence Register in the same package.

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
mutation, exact-head full regression and cross-platform CI, and updates to all applicable
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

**B35 status (2026-09-13): canonical DEVELOPMENT replay CLOSED / ACCEPTED; condition/selector, retained-artifact robustness, and exact targeted minute perturbations COMPLETE / NO PROMOTION. Successor PRE-OUTCOME freeze, rule/feature implementation, PR #83 source/runner contract, and the workstation hash-only source verification are complete; PR #84 is the separately gated DEVELOPMENT outcome-runner acceptance package, with the workstation equivalence benchmark next after merge.** The v2 contract remains frozen. Repository acceptance did not itself open outcomes; the later immutable DEVELOPMENT authorization opened only the exact frozen replay described below. The original `atlas-b35-a36-conditional-evidence-v1-pre-outcome` fingerprint `7bfd1cfdd65e946d45caa99dd2a35a90d8b424cb82cad5941ad26cac51816c4c` is preserved as superseded pre-outcome lineage and opened no B35 outcomes. Before any outcome access, review found that B34 validly permits a bar stamped 11:30 ET, which is usable only at 11:31, while v1 stopped its decision-time bucket at 11:30. Review also found that an overnight split should make the raw prior-close/current-open gap unavailable without erasing an otherwise valid same-session ORB/premarket/HVD condition snapshot. These are preregistration corrections, not outcome-driven retuning. B34 itself is unchanged.

The active contract is `atlas-b35-a36-conditional-evidence-v2-pre-outcome-clock-split-corrected`, fingerprint `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`, bound to unchanged B34 pack fingerprint `6f7239fcda11ac6c890d2635980d431ec49e346707d9cc549f111bd50daaa4bf`. B35 decision time is valid through 11:31 ET and the final bucket is `1031_TO_1131`; later decisions fail closed. A split-crossed raw gap is `UNAVAILABLE` for non-gap profiles, while B34 gap continuation remains blocked across the split. Twenty close-to-close realized-volatility returns require 21 completed split-safe closes. All other frozen walk-forward, exit, cost, selector, multiplicity, robustness, blind, and A34 risk-envelope rules remain as preregistered.

**Finite replay implementation boundary.** The governed replay is one canonical trial over `2016-01-04..2026-04-30`; the CLI exposes no alternate start/end, output-root, or trial-ledger override. The implementation binds that exact DEVELOPMENT minute-unit set to the immutable native acquisition plan and exact `year/month/batch/unit` checkpoint/canonical paths. May-2026-or-later minute partitions remain structurally rejected before open. Paths are confined to isolated V2 roots without symlink escape; canonical SHA-256 is checked lazily immediately before use; raw/unadjusted physical rows, duplicate keys, exchange-session labels, and strict Boolean adjustment schema fail closed. The source plan is itself content-fingerprint validated so a modified in-memory plan cannot retain a stale trusted fingerprint. Split/corporate-action evidence is separately path/hash bound.

Actual outcome replay additionally requires the immutable self-hash DEVELOPMENT authorization. Replay publication is serialized to prevent concurrent writers, writes an immutable self-hash read-start marker before the first authorized outcome read so a failed run cannot erase the fact that outcome access began, and materializes only compact fired-opportunity/context/outcome JSONL by deterministic symbol batch. Completed outputs have self-hash receipts; unreceipted orphan derived outputs are discarded and deterministically recomputed, while receipts missing their exact output fail closed. Restart reuses only validated exact receipts. The final run fingerprint binds validated receipt identities. No permanent broad minute-feature lake is authorized or created.

Frozen mechanics are implemented exactly: an information-safe signal enters at the first observed eligible regular-minute open within five minutes measured from the decision time; stops are strategy-specific; target is 2R; exact target opens resolve at the target before later intrabar ambiguity; stop gaps use the worse open; target gaps receive no improvement; same-bar unresolved stop/target collisions are adverse-stop-first; 15:55..15:59 provides the fixed time exit. The 0/10/25/50/100-bps all-in grid remains adverse by side. Short gross/net returns and MFE/MAE are normalized to entry notional. Entered-but-unresolved opportunities preserve signal/entry/stop/target/excursion evidence while remaining excluded from completed-return claims. The optimized setup scan only reduces repeated evaluation calls; final fired results are confirmed by the unchanged B34 evaluators.

**Retained-artifact robustness result (2026-09-11): COMPLETE / NO PROMOTION.** Robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` covers the same 2,079 complete XNYS walk-forward test sessions. Every declared 50-bps profile has negative mean session return; all five Deflated-Sharpe probabilities are `0.0`; 13 selected fold/cell hypotheses yield 0 BH-FDR q=.05 rejections. The frozen selector remains positive at 0/10/25 bps but turns negative at 50/100 bps and its bootstrap probability of positive mean 50-bps session return is 24.21%. PBO/CSCV = 0.01% is interpreted only as low rank-overfit tendency among the five declared profiles, not evidence of positive alpha. Exact entry/setup perturbations remained pending because compact outputs cannot reconstruct counterfactual minute paths; PR #79 implements those five families together in one hash-receipted, restartable DEVELOPMENT-only pass with per-group canonical baseline-equivalence gates and no selector refit.

PIT market regime remains `UNAVAILABLE` wherever this minute replay does not have an exact accepted prior-session regime join; it is never guessed. Short signal outcomes may later be RESEARCH-profiled, but A34 portfolio admission remains long-only until borrow/locate/recall economics are accepted. This package does not complete the later conditional-profile/selector analysis.

**Source-only workstation gate ACCEPTED (2026-09-08).** On merged `main` commit `4cf27ae9d23ac3b5d1821200e4d303db787f361a`, the canonical `2016-01-04..2026-04-30` source-only run selected exactly `59,768` minute units. Source fingerprint = `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`; split-evidence fingerprint = `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`; active B35 fingerprint = `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`. The run created no DEVELOPMENT outcome authorization and opened no B35 outcomes. Consumed-master rows permitted/read `0/0`; future-blind rows permitted/read `0/0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`. DEVELOPMENT scoring still ends `2026-04-30`; the consumed `2026-05-12..2026-08-11` master interval remains permanently unavailable for B35 fitting/scoring/qualification; the future blind beginning on/after `2026-09-08` remains unopened.

**Canonical DEVELOPMENT replay ACCEPTED (2026-09-11).** The one authorized replay completed `482/482` deterministic groups and `59,768/59,768` frozen source units with exactly `482` validated receipt ids. It produced `20,171,286` fired opportunity/context/outcome records and run fingerprint `8955a282453cb89a24d3bcdf819d80451bebfa3ec9752dc24c113efc668cffe6`. Bound identities remained unchanged: B35 fingerprint `145cc8983439b6062fd5e60303539d1611cdf7db0119ed68a7da1e68ffd8eda6`, source fingerprint `af371478a68d2dca486ffbaa1a339d24e1166257a67ba5f6ededfdda202a04cd`, split fingerprint `3bcccaddf3937368c675fb27a441f9bbac8cbf34816c26e37a4a3e84d03554f6`, and authorization `562d7104d56151e6203a1bf85457f9d1a90bbf19e60cd4d9359a3f96bc0a7be5`. Consumed-master rows read `0`; future-blind rows read `0`; provider calls `0`; broker reads/writes `0/0`; PAPER/LIVE authority `false/false`; strategy/selector promotion `false/false`; no permanent minute feature lake was created. Aggregate fired/comparable counts were: gap continuation `2,875,318 / 1,811,231`; opening-range breakout `16,982,463 / 12,626,529`; premarket relative-volume consolidation `313,447 / 309,304`; highest-volume-day style `58 / 58`. These are replay coverage counts, not profitability conclusions.

The canonical continuation reused 82 validated groups and computed the remaining **400 groups / 49,600 units in 11:40:46 at 4,246.7 units/hour**. This was about **6.43x** the original ~660.6-unit/hour serial restart and **44.3% faster** than the accepted 2,942.2-unit/hour isolated 10 x 1 equivalence benchmark, saving about **63.4 hours** versus serial processing of the remaining work.

**B35 condition/selector analyzer status (2026-09-11): COMPLETE / PROFILE-ONLY.** PR #76 merged as `cceccdc23569f6d48395a52322a83f59ba555b23`; the workstation analysis completed with fingerprint `8369790cc019e84091d9ff431e0ba82678e8b23ec09f65f010cdfaca35d3254f`. It normalized all 20,171,286 accepted compact opportunities and constructed 33 complete-XNYS 504/63/63/1 walk-forward folds. The frozen selector evaluated 17,030,985 test opportunities, selected 3,747 (3,188 comparable), and abstained on 99.978%. Selected mean return across the exact cost grid was +0.2984% / +0.1984% / +0.0485% / -0.2015% / -0.7014% at 0/10/25/50/100 bps. Strategy-level interpretation and current dispositions live in `docs/strategy_evidence_register.md`; no strategy or selector was promoted.

**B35 retained-artifact robustness and exact targeted minute perturbations are COMPLETE / NO PROMOTION.** PR #78 merged as `83d09c424a02883f7d3529a39c62294dcbaf6bc2`; robustness fingerprint `c4489478e82a535ef890fd017e47c9594ad9d590d439c5f55089426bd8565107` remains binding. PR #79 merged as `b6133d2efe8bc331a80d71bb2c0bfa47707655db`; the repaired workstation run subsequently completed 482/482 groups and 59,768/59,768 units with all 27 frozen profiles, exact canonical baseline equivalence, targeted fingerprint `078bdc84a18bd6e5ff401ca0a21d4feed61f7b21770a86610a42ee0fdd16374d`, and run fingerprint `dd3f6b94f9c669218512ed1eb014b33c0fd35e8ffe38484cc8967dc7a6e29f69`. Master/future/provider/broker reads remained zero and no authority changed. No neighboring parameter variant became economically viable: gap remained deeply negative, ORB timing/range perturbations were essentially flat and negative, premarket-relvol's best gross mean remained below 10 bps, and HVD remained sparse/negative.

Next Track-B sequence: (1) COMPLETE — freeze 21 economic families, four bounded B35 same-family challengers, shared PIT context and confluence rules; (2) COMPLETE — PR #82 merged exact rules/features without performance; (3) COMPLETE — PR #83 merged the portable source/runner contract and 28 routes; (4) COMPLETE — workstation preflight verified 493/493 groups and 59,768 minute units under runner fingerprint `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c` and source-verification fingerprint `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`, with zero outcomes/protected/future/provider/broker access; (5) PR #84 implements the separate outcome-opening evaluator/output runner on `SuccessorParallelCoordinator`, preserving standalone artifacts before conditioning/confluence and hard-rejecting consumed-master/future-blind access; (6) after exact-head PR #84 acceptance/merge, run only the frozen 4x1/6x1/8x1 workstation exact-equivalence benchmark and require identical science plus acceptable thermal/OS headroom; (7) only after benchmark acceptance authorize the second-gated full standalone DEVELOPMENT diagnostic; (8) analyze standalone evidence before condition/confluence; (9) any survivor still requires untouched/prospective authority evidence; and (10) never reuse the consumed master or silently open the future blind. Full mechanics and methodology anchors remain in `docs/b35_a36_preoutcome_conditional_evidence.md`.

### 19A status — Successor practitioner laboratory

**PRE-OUTCOME freeze implemented 2026-09-13.** `packages/strategies/successor_practitioner_lab.py` is the machine-readable scientific contract and `docs/successor_practitioner_lab_preoutcome.md` is its immutable human-readable specification. It freezes 10 retained + 11 new economic families, the four bounded B35 mechanism-level challengers, shared PIT context, 504/63/63/1 walk-forward design, 60/30/20 condition-support minimums, frequency-aware cost interpretation, abstention, multiplicity and confluence semantics. The consumed master and future blind remain structurally forbidden and this package has no promotion/PAPER/LIVE authority.

Runtime implementation is parallel-by-default and restart-safe. `packages/core/successor_execution_profile.py` supplies a bounded hardware-aware worker/DuckDB budget with separate successor environment overrides; `packages/backtesting/successor_parallel.py` supplies atomic group outputs, self-hash receipts, validated restart reuse, machine-readable progress, and scientific fingerprints that exclude execution profile/telemetry. The B35 targeted replay's 8x1 sustained workstation result is retained as a reference for similar workloads, but each materially different long successor workload must benchmark exact-equivalent execution shapes and choose the fastest stable non-throttling profile.

The freeze itself opened no successor outcomes. PR #83 subsequently merged the portable source/runner contract, and the workstation hash-only preflight completed 493/493 groups and 59,768 minute units with zero outcomes, protected/future reads, provider calls, or broker access. The accepted runner-contract fingerprint is `d2fb4b36ce9aafa1d807c915c15e15f8b52aa2fb11f5b7db742e0d7ecfe6d81c`; the accepted source-verification fingerprint is `a5662843dcce50a15bbdc1158c020ef58437592652654e4f6a00f73cf07c86c3`.

PR #84 implements the separate DEVELOPMENT outcome-opening package, while repository CI itself opens no performance. The runner validates the exact accepted preflight; reconstructs a hash-bound SPY session-close benchmark from the already accepted native minute acquisition source because `research_daily` intentionally contains common stocks only; computes shared daily features once per instrument; preserves exact retained-reference signal masks; applies one common executable-universe disposition across all 18 daily routes; and evaluates all 10 minute routes on the accepted B35 native-plan grouping. The accepted source starts on `2016-01-04`; no earlier warm-up history is invented. Atomic standalone artifacts and receipts are hash-bound, and drift/corruption fails closed before reuse.

Any DEVELOPMENT outcome access requires `--authorize-development-outcomes`; the full 493-group standalone run additionally requires `--authorize-full-standalone`. Before that broad gate may be used, the workstation must run the frozen 4x1/6x1/8x1 benchmark subset and prove exact scientific equivalence while preserving thermal/OS headroom. Runtime profile stays outside scientific identity. No consumed-master/future-blind/provider/broker/PAPER/LIVE/promotion authority is created.

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

**Status: SUCCESSOR PRE-OUTCOME FREEZE + RULE/FEATURE IMPLEMENTATION COMPLETE; PR #83 SOURCE/RUNNER CONTRACT + HASH-ONLY SOURCE VERIFICATION IS CURRENT; NO SUCCESSOR OUTCOMES OPENED.**
The completed four-strategy B35 DEVELOPMENT result is immutable historical evidence
and must not be rewritten for rescue tuning. ATLAS already has **six accepted daily practitioner families** in the
A33/B33 reference catalog plus **four frozen B34 intraday/opening families**. The next
library package therefore targets **21 total families by adding eleven new mechanisms**,
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

### 19A.2 Eleven genuinely new families

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

- `pract_adx_dmi_continuation_v1` — objective DMI directional state plus ADX trend-strength state under one frozen rule; ADX alone never chooses direction.
- `pract_relative_strength_momentum_v1` — PIT ticker out/underperformance versus SPY over a small frozen horizon set; sector-relative strength remains unavailable until an accepted PIT sector map exists.
- `pract_session_failed_break_reclaim_v1` — objective breach then bounded reclaim of previous-day high/low and premarket high/low with normalized breach depth, explicit confirmation, sweep-extreme invalidation and one coherent exit hierarchy; no hidden-liquidity claim.

For every new family freeze before performance: exact timeframe/bar authority;
indicator definition; lookback/minimum history; pivot algorithm; normalized geometry
and tolerances; entry clock; duplicate-signal rule; stop/target/time exit; costs;
long/short authority; sample/coverage minimums; condition dimensions; robustness
perturbations; and trial/fingerprint identity. Chart patterns use one deterministic
shared pivot/geometry engine. Manual visual labeling is forbidden.

### 19A.3 Shared PIT context and confluence are separate from strategy definitions

The successor run records a bounded shared context vector for incremental testing: broad-market alignment/volatility state; ticker relative strength/weakness versus SPY; one higher-timeframe trend representation; ATR-normalized trend maturity/extension; opening/premarket/same-time volume participation; overnight gap; price band; signal time; realized volatility; and liquidity/execution quality. Sector-relative strength waits for an accepted PIT sector map. Context is measured first and is not automatically a hard filter.

Opening Range receives two high-priority successor policies inside the same economic family: `orb_stocks_in_play_5m_v1`, testing abnormal same-time opening participation plus a 5-minute range break, and a versioned 15-minute close + bounded retest/hold confirmation challenger. Their agreement is not independent confluence. The failed-break/reclaim family is distinct from pivot breakout because one tests rejection/reversal after a structural breach while the other tests continuation through structure.

Portfolio loss limits, simultaneous-position capital competition, strategy exposure, concentration/correlation admission and account-level risk belong to the later account/PAPER simulation layer. Anchored VWAP, sector-relative strength, Level-2/order-book, options-flow/GEX and intraday fundamental conditioning wait for their own objective PIT/source contracts. Fixed arbitrary stop percentages/R:R, psychology rules, discretionary watchlists, Fibonacci/ICT/FVG/order-block terminology and generic indicator stacks are not added from practitioner anecdotes.

### 19A.4 Confluence is evidence, not vote counting

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

### 19A.5 Post-result diagnosis and bounded refinement

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

### 19A.6 Efficient shared implementation

Use one point-in-time primitive/context layer for OHLCV, SMA/EMA, RSI, MACD,
Bollinger statistics, ATR/ATRP, VWAP, relative volume/OBV, rolling highs/lows,
deterministic pivots, regime/liquidity and session context. Feed immutable views to
independent strategy evaluators. Reuse process-local infrastructure and parallelize
independent work under the validated ATLAS efficiency protocol. Avoid redundant full
feature lakes and repeated expensive scans when exact-equivalent shared computation
is possible. Golden-output/receipt equivalence remains mandatory whenever execution
mechanics change.

### 19A.7 Ordered successor work after B35

1. **COMPLETE:** B35 replay/selector/robustness/targeted perturbations are closed with no promotion.
2. **COMPLETE:** freeze the 21-family successor contract, four same-family challengers, shared PIT context and confluence semantics.
3. **COMPLETE:** implement shared daily PIT features plus all new/challenger rules with explicit information clocks.
4. **COMPLETE:** PR #83 freezes the portable source/runner contract, 28 routes, profile-independent grouping, outcome semantics and restart-safe source hashing.
5. **COMPLETE:** workstation hash-only preflight verifies 493/493 groups and 59,768 minute units with zero outcome/protected/future/provider/broker access.
6. **PR #84 ACCEPTANCE PACKAGE:** separately authorized DEVELOPMENT evaluator/output runner with exact preflight binding, shared daily feature reuse, exact retained masks, common daily universe, accepted B35 minute grouping, accepted-native-minute SPY benchmark, atomic standalone artifacts, self-hash receipts, validated restart reuse, input/artifact binding, and no conditioning/confluence before standalone completion.
7. **NEXT WORKSTATION GATE AFTER PR #84 MERGE:** run the frozen 4x1/6x1/8x1 benchmark subset with `--authorize-development-outcomes --mode benchmark`; require exact scientific equivalence and choose the fastest stable non-throttling shape.
8. **ONLY AFTER BENCHMARK ACCEPTANCE:** authorize the second-gated complete standalone DEVELOPMENT run; preserve standalone family/challenger outputs before condition/confluence analysis.
9. Any favorable DEVELOPMENT-inspired successor requires untouched/prospective evidence under a new authority contract before promotion. Consumed master stays unavailable and future blind stays unopened.

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
PLAIN-ENGLISH END → UPDATE ALL APPLICABLE LIVING DOCS IN THE SAME PACKAGE → MERGE →
POST-MERGE VERIFY`

Operator checkpoints are reserved for destructive actions, external authority,
broker/provider mutation, qualifying PAPER/LIVE activation, protected evidence, or
material ambiguity. Internal implementation does not need a conversational gate.

Every repository-changing package must update README and roadmap before merge; any package that changes or interprets strategy evidence must also update the Strategy Evidence Register.
Documentation is part of the implementation package, not a later clerical task.
Each update must leave an auditable handoff including the package goal, what code/
product capability changed, test and CI result when known, empirical/scientific
result if any, exact authority gained or not gained, protected-read/write state,
known limitations, and the next highest-value package. If any applicable living document is
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

1. Finish exact-head Windows/Ubuntu acceptance and merge PR #84. Repository acceptance opens no successor performance and grants no PAPER/LIVE/promotion authority.
2. On accepted `main`, run only `.\.venv\Scripts\python.exe scripts\run_successor_development.py --authorize-development-outcomes --mode benchmark` on the workstation. This bounded benchmark evaluates the frozen subset under 4x1/6x1/8x1 shapes and must prove exact scientific equivalence before runtime selection.
3. Record the fastest shape that also preserves thermal and OS headroom; raw speed does not override throttling.
4. Only after benchmark acceptance may the second-gated full standalone DEVELOPMENT command be authorized. Preserve all standalone results before condition/confluence analysis.
5. Consumed master and future blind remain prohibited; provider/broker access remains zero; PAPER/LIVE/promotion remains false.
6. Track A may continue independently under its separate authority gates.

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


## 23. Living Strategy Evidence Register

`docs/strategy_evidence_register.md` is the living scientific ledger for
strategy/version evidence. It preserves observed baseline results, supported and
unsupported condition evidence, walk-forward behavior, robustness status, current
research disposition, successor hypotheses, unresolved limitations, and authority.
It does not replace immutable receipts/artifacts or code behavior; it prevents future
research chats from reconstructing strategy truth from conversational memory.

B35 canonical replay, strategy x condition/selector analysis, retained-artifact robustness, exact targeted perturbations and final research disposition are complete. Do not rerun the canonical minute replay or reopen neighboring B35 parameter rescue. The register's current dispositions remain: Gap Continuation = condition-gate/calibrate candidate; Opening Range Breakout = condition-gate/calibrate plus execution audit; Premarket Rel-Vol = cost/execution-sensitive R&D candidate; Highest-Volume-Day style = redefine/insufficient evidence. None is promoted.

The successor 21-family/context/confluence package, exact rules/features, PR #83 portable source/runner contract, hash-only workstation source binding, and the bounded SPY source-only audit are complete. PR #84 remains the Track-B DEVELOPMENT outcome runner implementation. The accepted SPY audit resolved all 2,596 DEVELOPMENT sessions with 2,595 minute-primary closes and one exact same-session raw-native-daily repair on 2019-08-12. The next permitted evidence action is the separately authorized complete 546-work-group standalone run (64 daily buckets + 482 minute groups); 493 is retained only as the earlier source-verification grouping. The frozen 4x1/6x1/8x1 benchmark remains available as an optional performance/equivalence diagnostic, not a scientific prerequisite. The long-term router should
activate/deactivate strategy specialties using trailing point-in-time evidence and
abstain when no specialty clears support, cost, robustness, risk, and authority
gates. Continuous market coverage is desirable; forced continuous trading is not.

## 20. Successor DEVELOPMENT benchmark preparation repair

The first authorized successor 4x1/6x1/8x1 workstation benchmark attempt on 2026-09-13 stopped during deterministic input preparation, before any benchmark execution profile ran or any successor performance was reported. The accepted minute source has no exact scheduled final regular SPY minute for 2019-08-12, while the daily successor feature contract only requires a same-session SPY close available for a next-session-open decision.

The repaired benchmark aggregation contract therefore uses the last observed regular SPY bar from the **same session** at or before the scheduled final minute only when it is no more than **5 minutes stale**. Every fallback session, selected timestamp, and staleness value is recorded. Cross-session fill, previous-day substitution, provider calls, protected/master reads, and future-blind reads remain forbidden. Missing SPY coverage beyond the 5-minute bound still fails closed. The aggregation contract/fingerprint is part of the successor run identity, so the failed preparation cannot be silently reused under the repaired contract.

That minute-only repair path is superseded by the accepted source-only audit described below. The full 493-group standalone DEVELOPMENT run still requires its explicit second CLI authorization, but no longer depends on completing the optional 4x1/6x1/8x1 performance benchmark first. This change affects execution governance only; it grants no PAPER, LIVE, broker, provider, or promotion authority.


### 20.1 Second preparation finding and source-only repair gate

The repaired <=5-minute same-session minute rule was exercised on the workstation and failed before any benchmark profile ran: `2019-08-12` has a last accepted SPY regular minute at `19:31:00Z` / 15:31 ET, **28 minutes** before the scheduled final minute. Increasing the tolerance to 30 minutes is rejected because that would redefine a stale intraday observation as a daily close.

The successor benchmark source is re-gated through `run_successor_spy_source_audit.py`. The accepted B35 minute source remains primary. When a DEVELOPMENT session is missing/invalid or more than five minutes stale, the audit may use the exact same-session SPY close from the already-lineaged raw canonical V2 daily source **only for years <= 2025**. It may not open a 2026 native-daily partition; any unresolved 2026 minute session fails the audit. The workstation audit is now **ACCEPTED**: contract fingerprint `912bf7b0ed12a0e4fd7c0382244138573564472e618586677e78c154f7e3cc33`, scientific fingerprint `c575d5df1b7f0d0a7734efc3833329f57f73c953b7b67ccb4ea54d33abb4555c`, benchmark SHA-256 `29d7ea9d6a322b4b55af872f7d2e5097777738b209727a487cfd0dcf1306790d`, native-acceptance fingerprint `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`, and **2,596/2,596 sessions resolved**. Of those, **2,595** are minute-primary and exactly one (`2019-08-12`) is repaired from `NATIVE_RAW_DAILY`; its last accepted minute was `19:31:00Z`, 28.0 minutes stale. Authority stayed source-only with consumed-master/future/provider/broker reads `0`, PAPER/LIVE/promotion false, and strategy outcomes unopened. PR #87 subsequently removed optional pandas Parquet-engine dependencies from this audit and the downstream runner without changing scientific identity. The full standalone DEVELOPMENT run is now the next evidence gate; the 4x1/6x1/8x1 benchmark is optional.

### 20.2 First full standalone attempt — flat prior geometry repair

The first authorized full successor standalone attempt opened only the frozen DEVELOPMENT interval at 8 workers x 1 DuckDB thread under run-contract fingerprint `22a2ace77c4c578c30964ba2a645b822738ef667617f0ef6bffb3192f75582ae`. Its startup correctly reported **546 outcome work groups = 64 daily buckets + 482 minute groups** and 59,768 minute source units. The previously repeated 493 figure is the source-verification grouping and is not the standalone progress denominator.

The attempt stopped before a complete standalone result when `pract_session_failed_break_reclaim_v1` received a prior regular session whose observed high equaled its low. The strategy evaluator correctly rejects such geometry, but the shared minute engine incorrectly treated the presence of a prior session as sufficient readiness and propagated the exception. The repair keeps the strict evaluator unchanged and instead makes finite, positive, non-flat prior regular geometry an engine readiness condition. Flat/invalid prior geometry means this route is unavailable for that session; it is not filled, widened, or replaced with an older session. The standalone engine contract is versioned so the failed run identity and any partial artifacts cannot be silently reused under the repaired semantics.

Operationally, the coordinator already maintained an atomic `progress.json` heartbeat but did not expose it to the operator console. It now prints parent-process progress with completed/total, reused/new, active/queued, elapsed time, new-group throughput and ETA on startup, completion/failure, and at least every 30 seconds or five new group completions. These telemetry changes remain excluded from scientific identity. Consumed-master/future/provider/broker access remains forbidden and PAPER/LIVE/promotion authority remains false.


## 24. Strategy Development Cycle, actionability, and stock/options trade expression — 2026-09-15 direction

### 24.1 Broad-first, bounded-deep strategy development

ATLAS should broaden the implemented strategy library before spending unlimited research cycles on any one family. Every genuinely implemented strategy receives a clean baseline under the current PIT/walk-forward methodology; older observed results remain binding evidence rather than being relabeled as unseen. Repository inventory must distinguish implemented strategies from partial implementations and zero-byte/name-only placeholders before claiming coverage.

After each baseline, use the following controlled loop:

`BASELINE -> DIAGNOSE -> TARGETED EXTERNAL RESEARCH -> <=3 MATERIAL REVISIONS -> RETEST -> SPECIALIZE OR PARK -> MOVE ON`

Diagnosis asks why the mechanism underperformed or where it created opportunity: direction, market/volatility state, ticker trend and relative strength, extension, liquidity, price band, gap, participation, time of day, setup geometry, entry/confirmation delay, exit/holding logic, MFE/MAE, stop/target path, costs, unresolved/no-entry rate, concentration, fold/year stability, and underlying move magnitude/speed. Research then looks specifically for explanations and evidence-backed fixes in credible academic/replication work, original strategy/indicator sources, exchange/broker/quant research, books, respected practitioner material, and community experience. Do not ask generically for the historically best setting and then select it from the same outcomes.

A useful revision may seek either **greater edge per qualified opportunity** or **more quality opportunities while preserving acceptable edge, costs, drawdown and stability**. Opportunity count alone is not success, and a large per-trade edge with negligible usable frequency may contribute little at account level. Preserve every v1; a parked family is not deleted and may be revisited with new evidence or new source capability. No more than three materially distinct candidate revisions per family per research cycle by default; no dense parameter grids or tiny threshold stepping. The evidence that motivates v2 is diagnostic/training evidence only. Qualification of v2 requires untouched/fresh walk-forward or prospective evidence under a new version/fingerprint.

### 24.2 Universal economic actionability gate

A strategy firing is not permission to trade. Before instrument selection, every candidate must clear an economic actionability gate using a point-in-time forecast of expected reward versus costs, uncertainty, downside, liquidity, capital use and portfolio risk. ATLAS should estimate an **underlying move/time distribution**, not merely direction: expected/median move, uncertainty/tails, expected holding window/time-to-target, probability of positive return, probabilities of crossing material move thresholds (at least 1%, 2%, 3%, 5% where meaningful), ATR-normalized move probabilities, MFE/MAE, and path/speed characteristics. Thresholds and models used for admission must be frozen before qualifying evaluation.

This gate prevents technically correct but economically immaterial signals from consuming capital. It also supplies the bridge between strategy evidence and instrument construction: ATLAS first decides whether the underlying opportunity is worth expressing, then decides how to express it.

### 24.3 Operator-selectable trade-expression modes

The browser/control plane should ultimately expose four explicit modes:

- `OPTIONS_ONLY`: consider only economically acceptable option constructions; if none clears the gate, abstain even when the underlying signal is attractive.
- `STOCKS_ONLY`: ignore option constructions and admit only economically acceptable stock trades.
- `OPTIONS_PREFERRED`: evaluate both; prefer an acceptable option when its expected risk-adjusted economics meet the frozen preference rule, otherwise stock may remain eligible.
- `STOCKS_PREFERRED`: evaluate both; normally use stock, but permit an option when its expected risk-adjusted economics are materially superior under the frozen preference rule.

These settings control permitted/preferred expression, never strategy authority and never a requirement to trade. Stock remains a valid trade, not merely an error fallback; options remain a major intended expression because ATLAS originated partly from an options-alert/trading objective.

### 24.4 Option-worthiness and contract construction

Before real historical option-chain qualification exists, strategy research must add an **option-worthiness scorecard** from the underlying path: frequency/probability of 1/2/3/5% moves, 1-ATR/2-ATR moves, MFE/MAE, speed/time-to-move, adverse excursion before the move, realized volatility during the intended hold, and distribution/tail behavior. Equal mean stock return can imply very different option value when one strategy produces larger/faster convex moves.

For a current candidate that passes underlying actionability, option construction evaluates only point-in-time available contracts and must account for: strike, expiration/DTE and moneyness; premium and executable bid/ask; delta/gamma/theta/vega; implied volatility and plausible IV changes; volatility skew/smile and term structure when available; interest rates and dividends; American-style early-exercise considerations; volume/open interest and liquidity; known events such as earnings; expected option P&L and return distribution; probability of profit; material-loss probabilities; break-even; and expected value per dollar of capital/risk. Reprice candidate contracts across the underlying move/time distribution and plausible IV scenarios rather than at one deterministic target only.

Black-Scholes-Merton and other option-pricing models are references for theoretical value, Greeks and scenario analysis. A market price below one model estimate is only **model-relative undervaluation evidence**, not proof of mispricing. Compare it with the observed IV surface, neighboring strikes/expirations and executable liquidity. Historical option P&L cannot be claimed until a separately accepted PIT historical option-chain/quote/IV source contract exists. If option economics fail while the underlying stock economics remain acceptable, stock remains a candidate in modes that allow it.

### 24.5 Efficiency architecture

Do not scan and fully price every contract in the market continuously. Use the funnel:

`broad stock universe -> cheap strategy/regime scan -> qualified candidate -> underlying move/time forecast -> economic actionability -> option chain only when needed -> cheap liquidity/moneyness/DTE filters -> vectorized scenario pricing on a small contract set -> stock/option/abstain -> portfolio/risk`

Cache reusable rate/dividend/IV-surface/context inputs where PIT-safe, batch/vectorize Greek/scenario calculations, and keep option analytics outside scientific strategy firing. The expected performance bottleneck is option-data breadth/history/entitlement rather than the per-candidate pricing math; no source or correctness gate may be weakened for speed.

### 24.6 Current successor evidence and immediate research order

The complete successor standalone DEVELOPMENT run is now accepted: **546/546 groups**, **54,618,427 records**, scientific contract `d962d72579996c26485a292469e6483132b413c484b90471aba74b209993cafb`, standalone run fingerprint `c22bcb45b1a13dde11854f7ad166ae0abe1810fc0d6ab7371dbdd1165c1006e6`, artifact-set fingerprint `4e5d66b8db1b37ac70dcff9e92fc4602bb729f90f18852db59f7e827de5a55d6`, with 424 fresh groups completed in 9:00:08 at 47.10 groups/hour after 122 validated reuses. Master/future/provider/broker reads remained zero and PAPER/LIVE/promotion remained false.

The frozen successor conditioning v1 analysis is also complete across **33 folds** and **45,516,323 test-eligible opportunities**. It selected **36,259** opportunities (**36,254 comparable**), abstained on about **99.92%**, and the aggregate selected result remained negative at **-0.313660% primary / -0.466303% stress**. About **75.8%** of selections were from the most-specific selector level, so broad fallback is not the primary failure explanation. The selector had 11 positive and 22 negative folds, showing material temporal instability. **Confluence remains closed**; it must not be opened as a rescue layer for an unqualified selector.

Route-level post-result diagnostics identify research candidates, not validated winners. `pract_bollinger_mean_reversion_v1` LONG is the strongest current specialty candidate with **5,516 comparable selections**, **+0.4536% primary / +0.3032% stress**, active in 21 folds with 15 positive / 6 negative and largest-fold share about 21.9%. Smaller positive diagnostics are Donchian SHORT (379), ADX/DMI LONG (204), flag/pennant SHORT (191), RSI-recovery LONG (189), and triangle LONG (57); triangle LONG is especially concentrated with about 80.7% in one fold. Only 261 minute selections occurred, all from the 15-minute ORB retest challenger, and both directions were negative; every other minute route selected zero under the frozen conservative hurdle.

Next Track-B work is therefore: formally close conditioning v1 without promotion; add move-magnitude/speed/option-worthiness diagnostics from retained immutable artifacts where possible; inventory implemented/partial/placeholder strategy families; perform bounded failure-mode research for justified candidates while broadening baseline coverage; freeze any v2 rules before new performance; and require untouched/prospective evidence for qualification. The consumed master remains permanently unavailable and the future blind remains unopened.

### 24.7 Successor option-worthiness retained-artifact diagnostic — PRE-RUN

The next Track-B package after conditioning v1 is implemented as a descriptive retained-artifact analysis, not a selector rescue. It binds the exact accepted 546-group / 54,618,427-record standalone and conditioning-v1 identities, hash-validates the 546 normalized conditioning parts plus eligibility assignments, and then aggregates only those accepted Parquet artifacts. No raw market data, option history, provider, broker, consumed-master, or future-blind source is opened.

The package reports three populations separately: all comparable DEVELOPMENT opportunities, walk-forward test comparable opportunities, and conditioning-v1 selected comparable opportunities. Per route/direction it records return and MFE/MAE distributions, 1/2/3/5% favorable-excursion and adverse-breach frequencies, available daily horizon behavior, intraday holding-time behavior, and selected-fold persistence/concentration. Daily retained MFE/MAE is explicitly labeled `THROUGH_20_SESSIONS`; intraday excursion is `ENTRY_TO_ACTUAL_EXIT`. The daily primary return remains the separate five-session outcome, so 20-session MFE threshold frequencies are never described as five-session hit rates. The terminal/JSON handoff lists every selected route with descriptive move diagnostics in policy-id order; it deliberately creates no post-result ranking score. Exact time-to-threshold, ATR-normalized move-hit rates, full path ordering, hold-period realized volatility, and historical option P&L remain explicitly unavailable from retained artifacts.

Repository acceptance of this package does not itself open the additional diagnostic aggregates. After merge, the next workstation action is the separately authorized retained-artifact command. Confluence remains closed. Results may motivate bounded versioned strategy research but cannot validate a strategy or option trade on the same DEVELOPMENT evidence.

### Successor path-timing gate — frozen 2026-09-15

The first retained-artifact option-worthiness pass is complete (`analysis_fingerprint=6f82ac0e55be43b8cf95fc362c7f292cb592b41c15ff897b24665470e95410f3`). Its main design finding is that the retained daily MFE/MAE window runs through 20 sessions and is too permissive to answer whether a move is fast enough for the five-session strategy horizon or an options expression. Large eventual favorable excursions are common even among routes with negative five-session expectancy.

Before any strategy revision, run the frozen selected-daily path diagnostic on the 35,995 already-selected comparable daily opportunities. Required outputs are five-session favorable/adverse excursion, first-touch session for 1%/2%/3%/5%, favorable-versus-adverse first-touch classification, five-session exit capture versus MFE, and peak give-back. Daily same-session collisions remain unordered. This gate is diagnostic only and may motivate bounded v2 hypotheses; it cannot retroactively validate a route. Keep confluence closed. The 259 selected intraday ORB opportunities require a separate minute-resolution path package after the daily result.
## Successor selected-path closeout and exact-minute continuation — 2026-09-15

**Execution repair:** the first exact-minute invocation failed safely at the selector-artifact read because `eligibility_assignments.parquet` is intentionally compact and does not carry retained gross/path fields. The repaired reader now uses the accepted option-worthiness join discipline to bind each selected assignment back to its SHA-validated normalized opportunity before any native minute source is opened. A regression test reproduces the compact-selector schema. The failed attempt opened no minute evidence and changed no authority.

The retained 20-session excursion diagnostic is closed as useful but insufficient for trade-expression timing. The separately frozen selected-daily five-session diagnostic completed under analysis fingerprint `e89d1d61b7fe6875353816a11727f7ad4a0797917eac0ef4b2d437812a053e20` across exactly 35,995 selected comparable daily DEVELOPMENT opportunities. It confirms that magnitude alone is not enough: many routes eventually reach 2-3% inside five sessions while favorable-before-adverse path quality is often only ~30-50%. Positive post-result specialist evidence remains concentrated in Bollinger mean-reversion LONG (broadest sample), Flag/Pennant SHORT (cleaner 2-3% path but small sample), Donchian SHORT, ADX/DMI LONG and RSI-recovery LONG. These findings are diagnostic and create no promotion.

Immediate Track B sequence:

1. complete the preregistered **259-case exact-minute ORB path diagnostic** using only accepted serialized native-unit bindings and selected symbol/session paths;
2. preserve daily and minute path results as descriptive evidence; do not retrofit selector thresholds or open confluence to rescue them;
3. diagnose each promising family by failure mode (adverse-first path, regime mismatch, entry timing, exit/give-back, cost sensitivity, support/concentration);
4. perform targeted external research against that observed failure mechanism;
5. freeze at most a small bounded set of materially different successor versions, preserving v1 permanently;
6. require untouched/new/prospective evidence before any validation/promotion claim.

The options-oriented construction path remains: `strategy edge -> underlying move magnitude/speed/path distribution -> universal actionability gate -> operator trade-expression mode -> stock and/or option evaluation -> contract economics -> portfolio/risk/sizing -> trade or abstain`. Option evaluation must include delta, gamma, theta, vega/IV, skew/term structure, DTE, strike/moneyness, rates/dividends/early exercise where relevant, spread/liquidity/open interest, event risk, break-even/max loss and scenario expected P&L. A model-relative Black-Scholes value is evidence, not executable historical P&L. In modes permitting stock fallback, an underlying candidate may remain eligible when no option contract is economically acceptable.

Track A should continue account simulator/control-plane work in parallel using clearly labeled baselines. Historical alpha qualification is still zero; consumed master remains permanently closed, future blind unopened, confluence closed, and PAPER/LIVE/promotion authority false.

## Exact-minute ORB diagnosis and bounded literature-fidelity revision — 2026-09-15

The 259-case selected `orb_15m_close_retest_v2` minute-path diagnostic completed under fingerprint `a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8` after exact SHA verification of 218 native units and 55,581 path bars. LONG was -0.71% gross / -1.20% primary / -1.70% stress; SHORT was -0.01% / -0.51% / -1.01%. Favorable-first frequency was below 50% at every 1/2/3/5% threshold in both directions and generally worsened with threshold size. The opening-range retest failure is therefore localized to directional/path ordering rather than insufficient move magnitude.

The bounded next research action is `orb_stocks_in_play_5m_literature_v2`, preserved separately from `orb_stocks_in_play_5m_v1`. Its pre-outcome contract is frozen at `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb` and follows the literature mechanism rather than a parameter sweep: five-minute range, PIT 14-session share-volume/ATR/opening-relative-volume inputs, RV >= 1.0, daily top-20 RV rank, opening-candle direction, directional stop entry, 0.10 x ATR14 stop, and EOD exit. Gap-through entries fill at the worse first post-09:35 bar open; same-minute entry/stop ordering will remain unresolved/noncomparable rather than be assigned favorably.

Next implementation order:
1. Build a DEVELOPMENT-only cross-sectional runner that computes all v2 eligibility/ranking facts at 09:35 ET from prior-only evidence and accepted native minute sources.
2. Reconstruct exact direction-specific stop entries and exits with the frozen ambiguity rule and ATLAS 0/10/25/50/100-bps costs (50/100 primary/stress).
3. Report signal quality plus minute path/option-worthiness diagnostics; do not claim historical option P&L without PIT option-chain evidence.
4. Treat any DEVELOPMENT result as research diagnosis only. Do not reuse the consumed master, open the future blind, promote the strategy, or open confluence to rescue it.
5. After this one bounded ORB revision, move on rather than continue iterative ORB parameter tuning; Track A simulator/control-plane work remains independent and should continue.

## 25. Literature-fidelity ORB v2 DEVELOPMENT execution gate — 2026-09-15

### 25.1 Why this revision exists

The exact-minute closeout of `orb_15m_close_retest_v2` (`a58c06b19b499082190110c227ddd4617826bb33e733d07bd17d849d73b099d8`) localized the retained ORB failure to direction/path ordering rather than a lack of intraday movement. The bounded next hypothesis is therefore the separately versioned `orb_stocks_in_play_5m_literature_v2`, not another 15-minute retest parameter search. Base strategy fingerprint: `1be9081b60656affd09c683a28545894c66871e7a808e2b7e8f58bada67cf4cb`.

### 25.2 Frozen DEVELOPMENT runner

The pre-outcome DEVELOPMENT analysis contract is `87ee4ff703f8040d88c22147444aa992d196ab49be91dc749e3035e3c15e739b` over 2016-01-04 through 2026-04-30 only. Before any v2 outcome access, source review corrected the runner to preserve accepted V2 semantics: reconstruct raw daily OHLC only for Wilder ATR14; use provider-native split-adjusted daily share volume as supplied for the prior-14-session one-million-share gate; never derive volume from the price adjustment factor. Opening relative-volume history must contain the exact previous 14 XNYS sessions with a complete five-bar 09:30-09:34 ET opening snapshot.

The runner is deliberately funnelled for efficiency:

1. verify accepted successor preflight and exact native minute bindings;
2. materialize PIT prior-14 daily volume and ATR once;
3. across all 482 accepted minute groups, read only the first five regular-session minutes and publish restart-safe SHA-bound group artifacts;
4. filter price > $5, prior provider-native daily volume >= 1,000,000 shares, prior ATR14 > $0.50, opening relative volume >= 1.0;
5. rank the eligible cross-section deterministically by relative volume and retain the top 20; a doji occupies its rank slot but abstains;
6. only then open full-session minute paths for directional candidates;
7. apply direction-specific stop entry, adverse gap-through fills, 0.10xATR14 stop, EOD exit, same-minute entry/stop noncomparability, the 0/10/25/50/100-bps grid, and 1/2/3/5% path-timing diagnostics.

### 25.3 Evidence and authority boundary

Historical outcomes are still **UNOPENED** at this gate. Once the package passes exact-head acceptance, the next action is one explicit DEVELOPMENT-only workstation run. Its result is descriptive/research evidence and cannot validate itself, open confluence, or create promotion/PAPER/LIVE/option authority. The consumed master remains unavailable and the future blind remains unopened. If the v2 distribution is economically interesting, it becomes a candidate for untouched/prospective evidence and later option-worthiness/contract analysis; if it is not, freeze the result, preserve the version, and move on under the Strategy Development Cycle.


## 26. ORB v2 closeout and product-side actionability/trade expression — 2026-09-16

### 26.1 ORB literature v2 DEVELOPMENT disposition

`orb_stocks_in_play_5m_literature_v2` is closed as a completed DEVELOPMENT diagnostic under analysis fingerprint `cc6c34b18479aa76558e3c73cbc17ae75d85dd2c7b45d3806a8ac00d17b3a035`. The accepted population is 40,345 directional candidates / 33,773 entries / 23,412 comparable outcomes. Aggregate comparable return is +0.12% gross, -0.38% at 50 bps and -0.88% at 100 bps. LONG is +0.13% gross / -0.37% primary; SHORT is +0.11% / -0.39%. Both directions are already negative at 25 bps. Mean MFE/MAE is 1.27%/0.41% and the median comparable hold is 12 minutes in both directions.

The result is cost-sensitive rather than economically actionable under the frozen ATLAS conservative assumptions. Preserve the version and do not sweep parameters on this evidence. The 10,361 same-minute entry/stop collisions (~30.68% of entries) diagnose a tight immediate stop relative to minute noise, but any stop redesign is a separately versioned future hypothesis. No promotion, confluence, PAPER, LIVE or option-trading authority is created. Consumed master and future blind remain closed.

Underlying path timing remains useful for future option-worthiness research: LONG/SHORT favorable-hit rates are about 34%/35% at 1%, 18%/20% at 2%, 11%/12% at 3% and 4.7%/5.5% at 5%. These do not establish option profitability because no accepted PIT historical option-chain/quote/IV replay exists.

### 26.2 Track A economic actionability foundation

Implement the product decision sequence as:

`strategy/forecast evidence -> underlying move/time distribution -> universal economic actionability -> trade-expression mode -> stock/option/abstain -> portfolio/risk -> execution planning`

The first pure decision layer is frozen under contract fingerprint `a9341b7c0e6399165403cfa3d2f33e9f3b2749194ce39d41044a260dbd5fef4c`. It has no broker or execution authority and introduces no hidden economic thresholds. The caller must explicitly supply minimum expected net value, minimum return on capital, minimum probability of profit, maximum expected-loss/gain ratio, maximum execution-cost/gain ratio, minimum liquidity, and the material-superiority ratio used by preferred modes.

Mode semantics:

1. `OPTIONS_ONLY`: evaluate options only; if no option clears both the universal gate and complete option-context requirements, abstain.
2. `STOCKS_ONLY`: evaluate stock only; options are ignored.
3. `OPTIONS_PREFERRED`: evaluate both; use an acceptable option unless an acceptable stock is materially superior under the explicit preference score/policy. If no option passes, stock may be used only if it independently passes.
4. `STOCKS_PREFERRED`: symmetric stock preference with an option override only when the option independently passes and is materially superior.

All option candidates require complete contract/Greeks/IV/liquidity/event context in addition to the universal gate. A Black-Scholes or other model-relative undervaluation flag is nonblocking evidence only; it cannot rescue missing option evidence or failed economics.

### 26.3 Immediate product sequence

After repository acceptance of this foundation, continue Track A without waiting for another strategy to validate:

1. define the versioned underlying move/time forecast schema that carries threshold probabilities, expected/median move, uncertainty, time-to-move, MFE/MAE and path evidence into actionability;
2. connect the actionability/trade-expression decision to the deterministic case-file/account-simulator path without granting broker authority;
3. implement stock economics first with explicit slippage/cost/capital/risk inputs;
4. implement option scenario-economics interfaces next, but keep historical option-P&L unavailable until a PIT option source is separately contracted and accepted;
5. expose the four trade-expression modes and abstention reasons through the browser/control plane;
6. keep qualifying PAPER/LIVE gates unchanged. Product simulation may use clearly labeled baseline strategies while supported modern alpha remains zero.

Track B proceeds independently with broad-first strategy inventory and bounded failure-specific research. The completed ORB v2 is parked rather than repeatedly tuned.

## 27. Underlying move/time forecast foundation — 2026-09-16

### 27.1 Contract boundary

The broker-neutral product forecast contract is `93525886fb2f0e8af3821caba8c87854ab1d732d5619dc02838df0ef98d931e1` (`atlas-underlying-move-time-forecast-v1`). It converts supported strategy/model/empirical evidence into a common underlying-price-path distribution **before** stock or option construction.

An available forecast carries:

- identity, direction, forecast creation time and PIT evidence cutoff;
- horizon in minutes or sessions;
- method/source labels, SHA-256 source lineage and sample size;
- reference price;
- mean, median, p10, p25, p75 and p90 signed underlying return;
- probability of a positive underlying return;
- direction-normalized mean MFE and MAE;
- optional uncertainty score;
- for directional forecasts, unique direction-relative move thresholds with favorable/adverse touch probabilities, favorable-first/adverse-first/same-interval ordering probabilities and median favorable time.

The schema sorts thresholds deterministically and rejects probability curves that become larger at a more difficult move threshold. It also rejects unordered quantiles, non-finite values, future evidence, timing beyond the horizon and internally inconsistent path-order probabilities. A neutral available forecast carries a return distribution but no directional threshold table. An unavailable forecast carries identity/method/source/reasons only and cannot smuggle partial numeric evidence downstream.

### 27.2 Authority and compatibility

The forecast is underlying-only and cannot claim historical option P&L or grant instrument-selection, broker, PAPER, LIVE or promotion authority. It does not modify `Phase13CaseFile`, whose v1 primary instrument remains equity, and does not modify the Phase 15 order builder. This preserves the accepted execution path while Track A builds a separately versioned simulator/control-plane path.

### 27.3 Next implementation sequence

1. add a deterministic adapter that turns an available move/time forecast plus explicit stock economics into a stock `EconomicCandidate` for the universal actionability gate;
2. define an option-scenario input/output interface using the same underlying distribution, with executable quote/spread, Greeks, IV scenario, theta, liquidity and event completeness required before an option `EconomicCandidate` can exist;
3. create a versioned simulator decision case joining forecast + actionability policy + trade-expression decision + broker-neutral portfolio sizing, with abstention as a normal outcome;
4. expose those read-only decision objects and reason codes through the browser/control-plane surface;
5. leave live/paper order creation on the existing authority-gated path until a later explicitly accepted integration package.

The immediate goal is a usable account simulator driven by deterministic, inspectable evidence even while no strategy is historically promoted.

## Track A stock-economics adapter foundation — 2026-09-16

The product-side decision path now includes a frozen stock-economics adapter after the accepted underlying move/time forecast contract and before universal actionability/trade-expression selection.

Frozen adapter contract: `68f4b7ca0e4f86f07bf20afa1c7e6e5aa9708c081db44cc3c18f8123e711f924` (`atlas-stock-economics-adapter-v1`).

Decision sequence:

`strategy/forecast evidence -> underlying move/time forecast -> explicit stock economics -> universal economic gate -> trade-expression mode -> stock/option/abstain -> portfolio/risk -> simulator/execution boundary`

Stock economics v1 rules:

1. Only an available directional underlying forecast can create a stock candidate; unavailable and neutral forecasts abstain at this layer.
2. Position notional and reserved capital are explicit independent inputs. The adapter never infers leverage, margin, buying power or short collateral.
3. Entry/exit slippage bps, round-trip commissions/fees, horizon borrow cost and horizon financing cost are explicit nonnegative inputs. All are included in `execution_cost_dollars` as all-in expression cost for conservative actionability comparison.
4. Direction-adjusted mean underlying return drives expected gross P&L. All-in cost is subtracted to obtain expected net value, and net value divided by reserved capital gives expected return on capital.
5. Forecast mean MFE/MAE times position notional provide the candidate's expected gain/loss path-scale evidence. They are not option P&L claims.
6. Net probability of profit is supplied explicitly by the stock scenario layer; it is never inferred from MFE or threshold-touch rates and cannot exceed the forecast's gross directional sign probability.
7. Candidate preference score is expected return on capital. Negative expected value/ROC is preserved and therefore fails the downstream economic gate rather than being clamped positive.
8. Bearish stock candidates require explicit shortability. A failed shortability check keeps the candidate for audit but marks it non-executable.
9. This package remains broker-neutral decision support. Provider reads/writes, broker reads/writes, order creation, PAPER, LIVE, strategy promotion and confluence authority remain false/unavailable.

Immediate Track A continuation after acceptance:

1. compose the move/time forecast, stock-economics adapter and trade-expression gate into one deterministic product decision record with complete reason-code lineage;
2. feed that record into the account simulator without touching the legacy Phase 13 equity-only case contract or Phase 15 execution-authority contract;
3. add stock portfolio/capital reservation effects to simulation using explicit account-state inputs;
4. implement a separately versioned option-scenario economics adapter using strike/DTE/Greeks/IV/liquidity/event context and the same underlying forecast, with historical option-P&L claims still forbidden until an accepted PIT option-history source exists;
5. surface trade-expression mode, economics and abstention/rejection reasons through the browser/control plane.

The Strategy Evidence Register is intentionally unchanged by this package because no new strategy research result or disposition is created.

## Track A deterministic simulation decision record — 2026-09-16

The product-side path now has a versioned composition boundary before account simulation. Frozen contract: `62dceacde38687828e610c096d8c0a39479d5bc65b26b56aed2bf4164d8c8af8` (`atlas-simulation-decision-record-v1`).

The deterministic record binds:

1. the complete `atlas-underlying-move-time-forecast-v1` object and forecast instance fingerprint;
2. the original `StockEconomicsInputs` and resulting `atlas-stock-economics-adapter-v1` output;
3. the exact caller-supplied universal `ActionabilityPolicy` plus its deterministic fingerprint;
4. the selected `OPTIONS_ONLY`, `STOCKS_ONLY`, `OPTIONS_PREFERRED` or `STOCKS_PREFERRED` mode;
5. normalized option economic-candidate inputs and individual candidate fingerprints when supplied;
6. stock/option gate eligibility and reason-code lineage, including explicit `NOT_EVALUATED_BY_MODE` states rather than silently deleting ignored evidence;
7. the final trade-expression decision and selection/abstention reason codes;
8. an explicit timezone-aware decision timestamp and deterministic final record fingerprint.

The record requires accepted upstream contract identities and rejects a decision timestamp before forecast creation. Option input ordering is canonicalized, duplicate option identifiers are rejected, and changes to evidence, policy, mode, timestamp or instrument candidates are fingerprint material.

Authority boundary remains unchanged: provider reads/writes = 0, broker reads/writes = 0, order creation = false, PAPER = false, LIVE = false, promotion = false and confluence authority = false. The legacy Phase 13/15 execution contracts remain untouched.

Immediate Track A continuation after acceptance:

1. implement a new simulation account-state contract under `packages/simulation` with explicit cash, equity, reserved capital, gross exposure and simulated positions;
2. apply stock decisions to that state through deterministic capital reservation/release and opportunity competition without broker access or order authority;
3. produce a replayable account ledger keyed to simulation-decision-record fingerprints;
4. implement the separately versioned option scenario-economics adapter using the same underlying forecast plus strike/DTE/Greeks/IV/liquidity/event evidence;
5. add option capital/risk semantics to the same simulator only after the option-economics contract is accepted;
6. expose decision fingerprints, expression modes, economics and abstention/rejection reasons through the browser/control plane.

The Strategy Evidence Register is intentionally unchanged by this package because it introduces product/simulation architecture rather than new strategy research evidence or a strategy disposition change.

## Track A deterministic simulation account state — 2026-09-16

The next product-side boundary is now frozen under contract
`2460956a47dfa3f73c157b5e2f60aa710b10dabb0c1a7115309056d06c1a588b`
(`atlas-simulation-account-state-v1`). It consumes accepted simulation decision
records but remains a broker-neutral reservation ledger rather than a fill or P&L
engine.

V1 accounting semantics:

1. initialize explicit equity and unreserved cash with zero reservation/exposure;
2. a selected STOCK decision reserves exactly its accepted candidate capital and
   records the stock-economics position notional as gross exposure;
3. account equity remains unchanged because the package has no fill, mark-to-market
   or realized-P&L authority; `cash + reserved_capital == equity` and active
   reservation sums must reconcile exactly within deterministic numeric tolerance;
4. stock reservations are keyed to simulation-decision-record fingerprints and
   retain candidate/instrument/ticker/direction and reservation timestamp lineage;
5. ABSTAIN, insufficient-capital rejection and unsupported OPTION selection are
   explicitly ledgered without changing account amounts;
6. duplicate decision application and duplicate release are idempotent;
7. opportunity competition is deterministic by `decision_created_utc`, then
   decision-record fingerprint; v1 does not invent a second selector or rank with
   future outcomes;
8. every event binds before/after state fingerprints; the ledger is replayable and
   exact state-lineage mismatch fails closed.

This contract does not infer stock margin/leverage, short collateral, option margin,
buying-power multipliers, fill prices, realized/unrealized P&L, mark-to-market,
position quantity, correlation/concentration limits, or broker semantics. Existing
Phase 13 portfolio/risk planning remains separate; account-state v1 records the
capital/exposure consequences of already-selected broker-neutral decision evidence
and does not silently replace accepted risk contracts.

Provider reads/writes = 0, broker reads/writes = 0, order creation = false, fill
simulation = false, realized-P&L/mark-to-market authority = false, PAPER = false,
LIVE = false, promotion = false and confluence authority = false. Option selection
fails closed at the account layer until separately accepted option economics and
capital/risk semantics exist.

Immediate Track A continuation after acceptance:

1. define a separately versioned long-option capital/risk reservation contract tied
   to accepted option-economics evidence, explicit debit/max-loss cash at risk, and
   option-specific exposure fields; never substitute stock notional/margin rules;
2. extend the deterministic account-state/ledger replay so accepted OPTION decisions
   can reserve and release capital under that contract while preserving exact
   decision and economics fingerprints;
3. add later execution/fill and mark-to-market/outcome state as separate authority
   packages rather than relabeling reservations as positions/fills;
4. expose decision fingerprints, reservation/ledger state, trade-expression mode,
   economics and rejection/abstention reasons through the existing browser/control
   plane;
5. preserve all qualifying PAPER/LIVE gates and existing broker authority boundaries.

The Strategy Evidence Register is intentionally unchanged by this package because it
introduces product/account-simulation architecture rather than strategy research
evidence or a strategy disposition change.


## Track A option scenario economics — 2026-09-16

The option construction boundary is now frozen under contract
`798b05ab3867058865301c35a52491ee9a8cde82c6f1b019b8d27bae34e88178` (`atlas-option-scenario-economics-adapter-v1`). It consumes the accepted
underlying move/time forecast and validated `OptionCandidateEvidence`, and it emits a
normal `OPTION` `EconomicCandidate` for the already accepted universal actionability
and four-mode trade-expression gate.

V1 scientific/product semantics:

1. support only long single-leg calls for bullish forecasts and puts for bearish
   forecasts; unavailable/neutral forecasts or direction mismatch produce no option
   candidate;
2. bind every scenario model to the exact underlying-forecast fingerprint and require
   an explicit model id plus SHA-256 fingerprint; independently fingerprint the full
   `OptionCandidateEvidence` snapshot and include that lineage in both the economics
   result and option candidate identity;
3. require explicit expected/favorable/adverse terminal premiums and model
   probability of profit; do not infer a historical option-return distribution from
   stock returns or sparse Greeks;
4. require ordered scenario premiums (`adverse <= expected <= favorable`) and a
   holding period no longer than option DTE;
5. use current quote midpoint as valuation reference and ask debit as entry
   execution economics; derived entry half-spread plus explicit exit slippage,
   commissions and fees form all-in expression cost;
6. compute signed net value and return on explicit economic capital without clamping
   negative economics; for long options the denominator cannot be below the
   executable ask debit (`ask * multiplier * contracts`), preventing artificial ROC
   inflation, while the capital input remains **not** simulator reservation authority;
7. preserve separate completeness state for contract, Greeks, IV surface/context,
   liquidity, events and rates/dividends so the universal option gate can reject
   incomplete evidence transparently;
8. make upstream option-screen failure, event-risk rejection, executability and
   risk-budget rejection auditable rather than dropping the candidate silently;
9. permit an optional reference-model premium only as model-relative valuation
   evidence; `model_reference_premium > ask` maps to
   `MODEL_RELATIVE_UNDERVALUE_EVIDENCE_ONLY`, never to historical support;
10. claim no historical option P&L and require a separately accepted PIT option
    source before any historical option-return qualification.

Deterministic economics use:

- entry spread cost = `(ask - mid) * contract_multiplier * contracts`;
- expected gross P&L = `(expected_terminal_premium - mid) * multiplier * contracts`;
- all-in cost = entry spread + exit slippage + round-trip commissions + fees;
- expected net value = expected gross P&L - all-in cost;
- expected return on capital = expected net value / explicit economic capital;
- favorable gain evidence = `max((favorable_terminal_premium - mid) * multiplier * contracts, 0)`;
- adverse loss evidence = `max((mid - adverse_terminal_premium) * multiplier * contracts, 0)`.

Provider reads/writes = 0, broker reads/writes = 0, order writes = 0, historical
option-P&L claim = false, simulator option-reservation authority = false, PAPER =
false, LIVE = false, promotion = false and confluence authority = false. The accepted
simulation decision-record contract needs no mutation because it already accepts
normalized option `EconomicCandidate` inputs; the new adapter supplies those inputs
with explicit provenance.

Immediate Track A continuation:

1. freeze long-option account capital/risk semantics before any option reservation is
   allowed; debit/max-loss cash-at-risk, fees and exposure measures must be explicit;
2. extend the account-state ledger with option-specific reservation/release while
   keeping stock gross notional and option exposure conceptually separate;
3. only after reservation semantics are accepted, compose adapter-produced option
   candidates through decision record -> account state in focused replay tests;
4. defer fills, mark-to-market, realized P&L and broker mutation to separately
   authorized packages;
5. expose option scenario/economic/completeness/rejection lineage in the browser
   control plane without creating a second trading truth.

The Strategy Evidence Register is intentionally unchanged because this package adds
product option-construction architecture, not new strategy evidence or a disposition
change.

## Track A long-option capital/risk reservation terms — 2026-09-16

The option account-admission boundary is frozen under contract
`26835cbab3e551f0f7514e8537d823cb23d5db1f440362d20b1ba7493ff6aa64`
(`atlas-long-option-capital-risk-reservation-v1`). It consumes the accepted
simulation decision record, accepted option scenario-economics result, and the exact
option evidence snapshot, and emits immutable long-option reservation terms without
mutating account state.

Frozen v1 semantics:

1. require an OPTION-selected simulation decision and exact selected-candidate
   fingerprint lineage through both the decision record and option economics;
2. require the accepted option-economics contract and exact underlying-forecast
   fingerprint;
3. require the economics result's `source_option_evidence_fingerprint` to equal the
   full supplied `OptionCandidateEvidence` fingerprint, so quote-identical but
   otherwise changed delta/IV/liquidity/eligibility/open-interest evidence fails
   closed;
4. support only upstream-eligible long single-leg calls for bullish forecasts and
   puts for bearish forecasts, with complete correctly signed delta and complete
   accepted option scenario economics;
5. reserve premium at risk from the accepted executable ask debit and require
   `reserved_capital = ask_debit + explicit_nonnegative_cash_fee_reserve`;
6. set long-option max-loss cash equal to reserved capital and require the selected
   option's economic capital denominator to cover that full amount;
7. record signed and absolute delta-equivalent underlying notional from
   `delta * underlying_reference_price * multiplier * contracts` as option-specific
   exposure evidence only;
8. never mutate or reinterpret the stock account-state gross exposure field; and
9. grant no account-mutation, fill, realized-P&L, mark-to-market, broker/order,
   PAPER, LIVE, promotion, or confluence authority.

Immediate Track A continuation after acceptance:

1. extend the deterministic simulation account state with option-specific active
   reservations keyed to the decision/reservation fingerprints;
2. debit/release exact reserved cash deterministically while maintaining explicit
   stock reserved capital, option reserved capital, stock gross notional, and option
   signed/absolute delta-equivalent exposure as separate auditable quantities;
3. add option admission rejection for insufficient unreserved cash without inventing
   margin, collateral, or leverage semantics;
4. extend ledger events and replay verification so reservation/release is
   deterministic, idempotent, chronology-safe, and hash-lineage checked; and
5. keep equity invariant until a later separately accepted fill/mark-to-market/P&L
   package exists.

The Strategy Evidence Register remains unchanged because this package changes
product/account-simulation architecture only.

## Track A open-position entry-book account state — 2026-09-16

Track A now adds `atlas-simulation-open-position-account-state-v1` under contract
`c15c03400d61bf9e025f836118bf431178caadbdfc7c9a62826ec03796a0ee37`. It consumes one immutable accepted reservation-account snapshot plus
exact simulated entry-fill and funding/collateral evidence, then converts reservations
into deterministic **entry-book-value open positions**. The source reservation batch is
never rewritten: every fill and funding record remains bound to the exact account-state
fingerprint against which it was created, while the position layer tracks which source
reservations remain unconverted.

Each transition releases exactly one matching reservation and updates cash as
`current cash + released reservation - accepted required cash`. Cash is rechecked at
the moment of transition, so multiple fills that were individually affordable against
the same original unreserved-cash pool cannot spend those dollars twice. Same-fill
reapplication is idempotent; a different fill for an already-open decision fails
closed. Batch application is deterministic by `(filled_utc, fill_fingerprint)`, and
state/event/ledger fingerprints support exact replay verification and tamper detection.

Entry fees are expenses immediately: `entry book equity = initial equity - cumulative
entry fees`, while `cash + remaining reservations + open entry book value` must equal
that entry-book equity. Stock gross exposure transfers exactly from the reservation to
the cash-funded bullish stock position. Long-option premium paid becomes option entry
book value/premium at risk; the reservation's signed/absolute delta-equivalent exposure
is retained only as an **entry reference**, not a current Greek or mark. Stock shorts
remain unsupported because no accepted collateral/proceeds model exists.

The open-position package deliberately stops before market valuation. The source-bound
market-mark evidence layer described below now supplies exact valuation provenance, but
mark-to-market, unrealized/realized P&L, exits/closeout, broker mutation and PAPER/LIVE
authority remain separate gates. The Strategy Evidence Register remains unchanged
because these packages change product/account-simulation architecture only.


## Track A source-bound market-mark evidence — 2026-09-16

Track A now freezes `atlas-simulation-market-mark-evidence-v1` under contract
`1219f600e447f90718213ce0f974314f6480e90e13f46487770785e45c87c154`. The package binds one immutable mark record to one exact accepted
open-position fingerprint and requires explicit source id/SHA-256, provider, feed,
transport, feed-quality, market timestamp, receive timestamp, and valuation timestamp.
It is evidence-only: the accounting layer still performs no provider or broker read.

For the currently supported long stock and long-option positions, v1 selects the
**executable bid** as the conservative valuation candidate. Midpoint and last may be
retained descriptively but are never treated as liquidation truth. Stock requires a
positive bid; a long option may legitimately carry a zero bid, preserving a possible
zero liquidation value rather than inventing one. Crossed quotes fail closed.

Freshness is frozen at a maximum **60 seconds** from market timestamp to valuation
time. `market_timestamp <= received_timestamp <= valuation_timestamp` is mandatory.
A stale observation is retained for audit but is explicitly
`valuation_eligible = false`; it cannot create or carry forward P&L. The 60-second
limit is a versioned simulation policy rather than a permanent provider constant.

The market-mark package itself remains evidence-only and grants no account mutation,
realized P&L, exit/closeout, provider/broker, order, PAPER, LIVE, promotion or
confluence authority. The deterministic marked-account layer described below now
consumes those fresh marks for simulation valuation and unrealized P&L. The Strategy
Evidence Register remains unchanged because these packages change
product/account-simulation architecture only.


## Track A deterministic marked account and unrealized P&L — 2026-09-16

Track A now adds `atlas-simulation-marked-account-state-v1` under contract
`f09a1ead48e86ae82442785f281c0e57d242db3773537a3ba64a44bb2519c082`. It consumes the exact accepted open-position account snapshot plus
one exact fresh, valuation-eligible market-mark record for **every** active position at
one common valuation timestamp. Missing, stale, duplicate, mismatched, or extra marks
fail closed; ATLAS does not publish an authoritative account-level marked-equity value
for an incomplete valuation snapshot.

For each active position, marked value is `quantity * selected bid mark * multiplier`.
Unrealized P&L is marked value minus immutable entry book value, and unrealized return
uses entry book value as its denominator. Account unrealized P&L is the sum of the
position values, while marked equity is `entry_book_equity + aggregate_unrealized_P&L`
and independently reconciles to `cash + remaining reservations + marked open-position
value`. Entry fees were already expensed when the position opened and are therefore
never subtracted a second time in unrealized P&L.

A long option with a valid fresh zero bid may mark to zero and therefore to a full loss
of its entry book value. Option delta-equivalent exposure remains the immutable
**entry reference** only; this package does not infer a current Greek from price marks.
All marked positions share the requested valuation timestamp, and a mark whose market
timestamp predates the position open is rejected. Empty accounts produce a complete
zero-position valuation deterministically.

This is deterministic simulation valuation only. It does not mutate the open-position
state and grants no realized-P&L, exit/closeout, provider/broker, order, PAPER, LIVE,
promotion or confluence authority. The next bounded Track A work is broker-neutral
simulated exit-fill evidence followed by deterministic closeout/realized-P&L accounting
with lifetime trade-P&L and account-equity semantics kept explicit so entry fees cannot
be double counted. The Strategy Evidence Register remains unchanged because this is
product/account-simulation architecture only.


## Track A broker-neutral simulated exit-fill evidence — 2026-09-17

Track A now freezes `atlas-simulated-exit-fill-evidence-v1` under contract
`d823bdf481f6ae6266be0a7e87d36702e1687d5a84f97da105e64cfc7e8f77c0`.
It consumes the exact accepted open-position account state and one exact active
open-position fingerprint plus explicit source id/SHA-256, timezone-aware exit
timestamp, executable simulation exit price, and explicit exit fees.

The v1 exit boundary is full-close only. Exact quantity, quantity unit, multiplier,
instrument identity, and entry lineage are inherited from the active position; no
partial-exit or silent quantity mutation is permitted. Gross proceeds equal
`quantity * exit_price * multiplier`; net proceeds equal gross proceeds less exit
fees. A zero exit price is valid so complete-loss outcomes remain representable, while
exit fees may not exceed gross proceeds.

The exit-fill record remains descriptive evidence only. It grants no position/account
mutation, realized-P&L, closeout, provider/broker read/write, broker-fill, order,
PAPER/LIVE, promotion, or confluence authority.

The deterministic closeout layer described below now consumes this evidence. The
Strategy Evidence Register remains unchanged because this package changes
product/account-simulation architecture only.

## Track A deterministic closeout and realized-P&L accounting — 2026-09-17

Track A now freezes `atlas-simulation-closeout-account-state-v1` under contract
`d8363e6a0dba68ad8894691a308eff6231770e59ccea909a38fd95af317aa599`.
It consumes the exact accepted open-position account state plus exact accepted
`atlas-simulated-exit-fill-evidence-v1` lineage and performs the first deterministic
simulation closeout mutation.

Frozen semantics:

1. only the exact matched active position is removed; unrelated positions and all
   remaining reservations are unchanged;
2. exact net exit proceeds are returned to simulation cash;
3. account-state realized-P&L delta is
   `net_exit_proceeds - entry_book_value`, excluding the entry fee because that fee
   was already expensed at open;
4. lifetime trade net P&L is
   `gross_exit_proceeds - entry_book_value - entry_fees - exit_fees`, so each fee is
   counted exactly once over the complete trade lifecycle;
5. account book equity is
   `initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and
   must independently equal cash + remaining reservations + remaining open book value;
6. closed-trade records retain exact position/decision/fill lineage, entry/exit
   economics, fees, holding duration, account-realized delta, and lifetime trade net
   P&L;
7. identical duplicate exit-fill application is idempotent, conflicting second closes
   fail closed, transitions are chronological/fingerprint chained, and deterministic
   batch replay must reproduce both state and ledger fingerprints.

This is simulation lifecycle accounting only. It grants no provider/broker read/write,
order, PAPER, LIVE, promotion, or confluence authority.

Immediate Track A continuation after acceptance is to integrate the authoritative
decision, open-position, market-mark, marked-account, exit-fill, closed-trade, and
account-P&L records into the existing browser/operator observability and control-plane
surface without creating a second trading truth; then close any remaining lifecycle
or orchestration gaps before later broker/PAPER authority work.

The Strategy Evidence Register remains unchanged because this package changes
product/account-simulation architecture only.


## Track A funding/collateral terms — 2026-09-16

Track A now freezes the funding boundary under contract `f76d77ebbf138924a22813773ad27276b0fa71691ddff1d21040171c7b6d3821`
(`atlas-simulation-funding-collateral-terms-v1`). It consumes only the exact accepted
simulation account-state v2 snapshot and exact broker-neutral entry-fill evidence. The
terms object is descriptive evidence only: it does not mutate the account, release a
reservation, create a position, borrow funds, create an order, mark to market, realize
P&L, read/write a broker/provider, or grant PAPER/LIVE/promotion/confluence authority.

V1 permits a **fully cash-funded bullish stock long only**. Required cash is exact
filled gross notional plus explicit entry fees. The existing stock reservation is
credited toward that requirement and any remaining amount must be proven available in
the account's currently unreserved cash pool. Insufficient supplemental cash fails
closed. Borrowing, margin, leverage, collateral and short-sale proceeds remain exactly
zero and are never inferred from the accepted economic-capital/gross-notional gap.
Bearish stock/short position conversion therefore remains unsupported until a separate
versioned short-collateral/proceeds model is accepted.

Long options reuse the already-resolved debit from accepted fill evidence. Required
cash equals the exact filled premium debit plus accepted entry fees, supplemental cash
is zero, and any unspent option reservation remains explicit for the later atomic
position transition. Option delta-equivalent exposure remains separate from stock
gross notional and is not reinterpreted as funding or collateral.

The next bounded Track A package may now atomically convert an accepted reservation +
accepted fill + exact funding terms into deterministic open-position/cost-basis state,
with idempotent duplicate application and replay/tamper checks. Mark-to-market,
unrealized/realized P&L, exits/closeout, broker mutation and PAPER/LIVE authority remain
later gates. The Strategy Evidence Register is intentionally unchanged because this
package changes product simulation architecture only.


## Track A stock-option simulation account-state v2 — 2026-09-16

The reservation-only mixed-instrument account boundary is frozen under contract
`1e9da000571d02eb8fe4d317d770fdef25fb35a527ad177d1a87a6794c9592e5`
(`atlas-simulation-account-state-v2-stock-option-reservations`). It extends the
accepted account-state foundation without altering the historical v1 contract.

Frozen v2 semantics:

1. preserve the accepted v1 stock reservation arithmetic while strengthening chosen
   stock candidate lineage with an exact economic-candidate fingerprint check;
2. require exact accepted long-option reservation terms before any OPTION decision
   can reserve account capital;
3. use one unreserved-cash pool while tracking stock reserved capital, option reserved
   capital, stock gross notional, option signed/absolute delta-equivalent notional,
   option max-loss cash, and option premium-at-risk separately;
4. require `cash + stock_reserved_capital + option_reserved_capital == equity` and
   keep equity invariant throughout reservation-only state transitions;
5. fail closed on missing option terms, insufficient unreserved cash, contract or
   candidate lineage mismatch, backward chronology, or malformed state/ledger data;
6. make repeated decision applications and repeated releases idempotent, with
   deterministic competition ordering by decision timestamp then record fingerprint;
7. release exactly the previously reserved stock or option cash/exposure amounts
   without inventing fills, marks, or P&L;
8. provide deterministic state, event, and ledger fingerprints plus replay checks for
   chronology, before/after state lineage, and reservation/release integrity;
9. never fold option delta-equivalent exposure into stock gross notional; and
10. infer no margin, collateral, or leverage and grant no provider/broker, order,
    fill, mark-to-market, realized-P&L, PAPER, LIVE, promotion, or confluence authority.

## Track A broker-neutral simulated entry-fill evidence — 2026-09-16

The next execution boundary is frozen under contract
`e271ba5c66fe9bc41b7f81945a1ef8152a2eeae091b27f6efd4859bacd2d8668`
(`atlas-simulated-entry-fill-evidence-v1`). It consumes exact active reservation,
account-state, decision-record and selected-candidate lineage plus explicit
caller-supplied complete-fill evidence. Source id, source fingerprint, fill timestamp,
price and explicit fees are fingerprint material. Partial fills remain outside this
version.

Frozen fill semantics:

1. STOCK preserves the accepted reservation economic gross notional and derives
   complete fractional simulation quantity as notional / explicit fill price;
2. STOCK does not resolve or infer cash funding, margin, collateral, leverage or
   short-sale proceeds when accepted economic capital differs from gross notional;
3. OPTION requires exact accepted long-option reservation terms, contract count and
   multiplier;
4. OPTION premium debit cannot exceed the reserved ask-premium debit, explicit entry
   fees cannot exceed the separate fee reserve, total cash debit cannot exceed total
   reserved capital, and unspent reserve is recorded explicitly;
5. every fill binds exact account-state, reservation, decision, candidate and external
   fill-source lineage and receives a deterministic fingerprint; and
6. the package grants no reservation-release, account-mutation, open-position,
   mark-to-market, realized-P&L, provider/broker, order, PAPER, LIVE, promotion or
   confluence authority.

Immediate Track A continuation after acceptance:

1. freeze broker-neutral simulated complete exit-fill evidence tied to one exact active
   open-position fingerprint, explicit source id/SHA-256, exit timestamp, executable
   exit price, exact quantity/multiplier and explicit exit fees;
2. keep the exit evidence descriptive only—no broker/order/PAPER/LIVE authority and no
   position mutation merely because an exit fill record exists;
3. consume exact open-position + exit-fill lineage in a deterministic closeout state
   that removes only the matched position and returns exact net exit proceeds to cash;
4. distinguish account-state realized P&L from lifetime trade net P&L so previously
   expensed entry fees are not double counted, and add replay/idempotency/tamper checks;
5. only after lifecycle accounting is accepted, integrate the authoritative records into
   browser observability and later broker/PAPER authority gates.

The Strategy Evidence Register remains unchanged because this package changes
product/account-simulation architecture only.

