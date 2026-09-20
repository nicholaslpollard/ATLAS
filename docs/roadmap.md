# ATLAS Master Roadmap and Research/Product Source of Truth

**Current as of 2026-09-20 (UTC). This roadmap, the root `README.md`, and
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
trade construction → portfolio/risk → deterministic case/authority → optional independent
AI verification → operator-observable control plane → operational PAPER → outcomes →
performance/learning → production operations`

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
deterministic case/authority → optional independent AI verification → SHADOW/PAPER
execution → outcome ledger → walk-forward learning → API/browser control plane →
production operations`

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
- **AI:** late optional independent verification only. It is not part of signal generation, deterministic trade gating, option construction, sizing, portfolio admission, or exit-plan construction; the complete quantitative system must function and be measurable with AI disabled.
- **Browser GUI:** operator surface over the same engine, never a second trading
  engine. It may format and aggregate authoritative records but must not maintain a
  separate trading truth or independently recompute trading decisions.

### Historical News V1 acquisition — 2026-09-20

Historical News V1 is the first acquisition stage under the bounded news/options
foundation. It freezes a complete prior-day corpus window
`2015-01-01..2026-09-19` into 141 monthly partitions.

Each month produces:

- immutable deterministic gzip JSONL containing the provider article records;
- normalized ZSTD Parquet retaining article ID/source/author/headline/summary/content,
  URL, created/updated timestamps, symbols/images JSON and source-record hash;
- a hash-bound COMPLETE receipt used for restart/resume and corruption detection.

The PIT text rule is conservative: the historical endpoint does not expose the full
sequence of article revisions, so the retrieved text is not considered available at
the original `created_at` timestamp when a later `updated_at` exists.
`pit_available_at = updated_at` is frozen for V1.

The acquisition uses multiple monthly I/O workers behind one global Alpaca request
rate limiter. Before promoting each partition, the storage guard accounts for the
replacement-aware final byte footprint and refuses a write that would exceed the
4 GiB news quota, 40 GiB total research budget or 50 GiB free-space floor.

Historical News V1 remains source-only. Predictor development begins only after the
source corpus completes and its exact receipt set is frozen. The next data package
after news is historical option contract reference, followed by broad option daily
history; candidate minute/quote/trade cache acquisition remains selective.

### News/options historical-data foundation — 2026-09-20

Before integrating catalyst/news and option economics into replay, ATLAS must prove
that the workstation has storage headroom and that the configured provider
entitlements can reproduce the needed historical intervals.

The initial local-data policy reserves at most 40 GiB for this new research layer and
fails closed before projected acquisition would cross a 50 GiB system-free-space
floor. A 65 GiB free-space threshold is a warning boundary. Category quotas are
4 GiB news, 4 GiB option reference, 8 GiB broad option daily aggregates, 20 GiB
selective candidate option cache and 4 GiB derived IV/Greeks.

Storage architecture:

`data/news/raw` -> immutable provider articles;
`data/news/normalized` -> normalized point-in-time records;
`data/news/features` -> versioned sentiment/event/novelty/materiality features;
`data/options/reference` -> active/expired contract identity;
`data/options/daily` -> economical broad option OHLCV;
`data/options/candidate_cache/*` -> permanent chain/minute/quote/trade slices only
for replay-generated candidates;
`data/options/derived/*` -> versioned reconstructed IV/Greeks.

Provider coverage assumptions are deliberately separated from entitlement proof.
Current documented coverage as of 2026-09-20 is: Alpaca news from 2015; Alpaca
historical options from February 2024; Massive day/minute/trade option data from
June 2014; Massive top-of-book option quotes from March 7, 2022. The pre-2022 quote
gap is explicit: no historical bid/ask is invented. A later replay contract must
either use an accepted conservative execution model for that era or exclude cases
whose required execution evidence is unavailable.

The preflight package creates no market-data history. With provider probing enabled
it performs only a one-record Alpaca historical-news request, a one-record Massive
2016 SPY option-reference request and one-object S3 visibility checks for 2016/2025
option daily/minute prefixes. This determines actual workstation entitlement before
any acquisition package is permitted.

Ordered continuation after an accepted preflight:

1. broad Historical News V1 acquisition/normalization;
2. historical option contract-reference acquisition;
3. broad option daily history only if storage and entitlement gates pass;
4. candidate-driven minute/quote/trade acquisition with per-category quota checks;
5. deterministic historical IV/Greek reconstruction;
6. integrate news/catalyst features and stock-vs-option construction into replay.

### Target full-system simulator decision schema — frozen 2026-09-20

The recurrent stock-equivalent research simulator is an intermediate scientific
instrument, not the final ATLAS simulator. The full simulator must progressively
integrate the following deterministic layers while retaining point-in-time lineage
and an explicit no-AI baseline.

**Underlying forecast:** direction/probability, expected move distribution, horizon,
MFE/MAE and path/touch distributions, realized/implied volatility state, market/
sector/ticker regime, momentum/relative-strength/trend/gap context, execution quality,
tail scenarios, uncertainty and exact strategy/version provenance.

**Catalyst/context:** news sentiment, novelty, materiality, relevance and duplication;
event type/timing; earnings/guidance proximity; SEC/regulatory/corporate actions;
accepted fundamental/reference predictors; macro/calendar risk; sector/industry/peer
context; approved short-interest/ownership/event predictors; data freshness and
contradiction state.

**Trade gate:** TAKE/ABSTAIN, calibrated confidence/probability of profit, expected
gross/net edge after all modeled costs, downside/tail value, evidence support and
stability, walk-forward/regime applicability, independent confluence/conflict,
tradability/freshness, portfolio capacity, authority state, ranked priority and
explicit abstention/rejection reason.

**Stock/options construction:** compare stock economics to option economics rather
than assuming stock return maps mechanically to option return. For options retain
call/put or structure, DTE/expiration, strike/moneyness, executable premium/spread,
delta/gamma/theta/vega/rho where material, IV/term structure/skew, open interest,
volume/quote age/liquidity, synchronized underlying/option timestamps, event exposure,
scenario P&L distribution, breakeven, maximum premium at risk, expected value after
option-specific costs and the reason the option or stock instrument won.

**Risk/portfolio:** risk-normalized position size, premium/notional limits, buying
power/cash reservation, gross/net exposure, ticker/family/sector/industry/factor
concentration, correlation/clusters, beta, aggregate option Greeks/volatility exposure,
liquidity/exit capacity, current drawdown/loss limits, gap/volatility stress loss,
risk-of-ruin controls, competing-opportunity priority and capital opportunity cost.

**Position management:** bind entry method and slippage tolerance, stop/target/time
exit, versioned volatility-scaled or static geometry, any supported trailing/
breakeven/partial-exit rules, option IV/theta/event invalidation, thesis invalidation,
mark/freshness requirements, degraded-data behavior and trigger precedence before
entry. Historical replay must use only data actually available at the relevant time
and must model ambiguous bar ordering conservatively.

**Outcome/learning:** retain every taken and abstained opportunity, realized stock or
option P&L after modeled costs, MFE/MAE/touch/timing/path data, realized execution
costs, option IV/Greek evolution where available, decision/exit reason, attribution
by strategy/regime/catalyst/contract/portfolio constraint, marked/book equity impact,
calibration error and complete fingerprints/provenance.

The integration sequence is intentionally incremental: establish competent underlying
forecast/trade gating and risk mechanics; add option-economics replay early enough
that stock-return optimization does not become the wrong objective; add catalyst/news
and reference evidence under accepted PIT source contracts; integrate portfolio-level
option/risk accounting; then run the deterministic full-stack simulator and prospective
SHADOW/PAPER.

**AI remains outside this sequence until the deterministic stack is accepted.**
When introduced, the AI receives an immutable completed deterministic case and may
approve, caution, reject or flag inconsistency. It may not rewrite trade parameters
or feed its judgment backward into the baseline decision. Any proposed alternative
must be re-evaluated deterministically as a new record. ATLAS must maintain an
AI-disabled control path so incremental AI value can be measured directly before
AI is granted any operational role.

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

The post-close valuation layer described below closes the remaining current
marked-equity gap before browser integration. The Strategy Evidence Register remains
unchanged because this package changes product/account-simulation architecture only.

## Track A post-close lifecycle marked-account state — 2026-09-17

Track A now freezes `atlas-simulation-lifecycle-marked-account-state-v1` under
contract
`4cc4fb35c5a95cb48603f581a48127fe188c844c44e445394ad3d662e07a5346`.

This package resolves the lifecycle valuation gap between deterministic closeout and
operator observability. Market-mark evidence is already bound to immutable individual
position fingerprints, but the earlier account-level marked state is bound to the
pre-close open-position snapshot. After any close, using that old account snapshot as
"current" would incorrectly include closed positions.

Frozen semantics:

1. consume the exact accepted closeout account state and exactly one fresh,
   valuation-eligible mark for every currently open position at one common valuation
   timestamp;
2. reject missing, duplicate, stale, closed-position, or otherwise extra marks;
3. mark only surviving positions; never revalue closed trades;
4. carry cumulative entry fees, exit fees, account-realized P&L, lifetime trade net
   P&L, cash, reservations, and closeout book equity forward without recomputation;
5. compute current aggregate unrealized P&L only from surviving positions and define
   marked equity as `account_book_equity + aggregate_unrealized_pnl`;
6. independently reconcile marked equity to cash + remaining reserved capital +
   current marked open-position value;
7. allow an all-closed account to publish a complete zero-mark valuation equal to its
   closeout book equity; and
8. retain option delta-equivalent exposure as an entry reference only, with no current
   Greek inference.

This remains read-only simulation valuation and grants no account mutation, new
realized-P&L, exit/closeout, provider/broker read/write, order, PAPER/LIVE, promotion,
or confluence authority.

The read-only lifecycle observability layer described below now consumes this
post-close truth. The Strategy Evidence Register remains unchanged because this package
changes product/account-simulation architecture only.

## Track A engine-owned simulation lifecycle observability — 2026-09-17

Track A now projects the accepted lifecycle state into the existing loopback
control-plane/browser without creating a second trading truth.

Frozen boundaries:

1. `SimulationLifecycleDashboardService` accepts an injected
   `CloseoutAccountV1` + `LifecycleMarkedAccountStateV1` pair only;
2. it revalidates state, ledger, marked-state, source-binding, accounting carry-forward,
   and current position/mark lineage before projection;
3. no source injection yields explicit `NOT_CONNECTED`; invalid source yields
   `INVALID`; there is no fallback to Phase15, broker state, or provider refresh;
4. `GET /api/v1/ops/simulation-lifecycle` is loopback/read-only and reports zero
   provider, broker, order, PAPER, and LIVE mutation authority;
5. the browser panel displays marked/book equity, realized/unrealized P&L, fees, open
   marked positions, deterministic closed trades, and fingerprint provenance;
6. it reuses the existing `atlas:observability-refreshed` event and adds no new
   polling timer or mutation route; and
7. the synthetic preview uses the same payload shape but is labeled synthetic and
   carries no trading authority.

The single-cycle coordinator described below now supplies the atomic engine-owned
source. Post-close re-entry remains a separate next lifecycle boundary.

## Track A atomic single-cycle simulation lifecycle coordinator — 2026-09-17

Track A now freezes `atlas-simulation-lifecycle-coordinator-v1` under contract
`696254240971db5a9a7ae2a0307c2c847b376d360d5cfe1f8b5f30ec80a93a9b`.

The coordinator occupies the previously empty simulation-engine seam and owns one
accepted lifecycle cycle from an immutable `OpenPositionAccountStateV1` through
marking and deterministic closeout.

Frozen semantics:

1. initialize one exact accepted open-position snapshot into the accepted closeout
   account deterministically;
2. own the current immutable closeout account and optional current lifecycle marked
   state behind one `RLock`;
3. advance logical revision by actual new closeout ledger events and new unique
   valuation publications, making sequential and batch replay converge;
4. invalidate the prior marked state after every real account mutation;
5. preserve a current valuation across identical idempotent duplicate exit reuse;
6. accept only complete/fresh mark sets under the existing lifecycle valuation
   contract and treat identical republishing as idempotent;
7. expose one atomic current book+mark pair to the lifecycle dashboard adapter, or no
   pair when valuation is absent/stale;
8. perform no filesystem reconstruction, provider/broker reads or writes, or order
   creation; and
9. remain explicitly single-cycle: no new reservation, new entry, or re-entry after
   the immutable source snapshot.

`create_phase19_status_server` can now receive the coordinator directly and constructs
the read-only lifecycle dashboard source from the coordinator's atomic pair. Supplying
both a coordinator and an explicit dashboard service is rejected as ambiguous.

The lifecycle-native reservation layer described below now begins that re-entry path
without conflating reserved capital with a filled position.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation/control-plane architecture only.

## Track A lifecycle-native post-close re-entry reservations — 2026-09-17

Track A now freezes `atlas-simulation-lifecycle-reservation-account-v1` under
contract
`b4b825cca77a59f2d65064c9644d513714968f4ae7b8cea03f0738411d3459bb`.

This package replaces the unsafe idea of restarting the old reservation-only account
after closeout. The legacy reservation state assumes cash + reservations equals the
entire account equity; once open positions and realized P&L exist, that identity is no
longer sufficient. The lifecycle-native reservation state therefore carries the
accepted closeout book forward.

Frozen semantics:

1. initialize from one exact accepted closeout state + closeout ledger fingerprint;
2. carry current open positions, closed trades, entry/exit fee history, account
   realized P&L, lifetime trade net P&L, cash, book equity, and active reservations
   forward unchanged;
3. reserve new stock or long-option capital only from current unreserved cash;
4. keep account book equity unchanged by reservation and reconcile it to
   cash + stock reserved capital + option reserved capital + open entry-book value;
5. keep new stock reserved gross notional separate from existing open-stock exposure;
6. keep new option reserved delta/max-loss/premium risk separate from immutable
   open-option entry references;
7. ledger abstention, missing-option-terms, and insufficient-current-cash decisions
   without capital mutation;
8. make duplicate decisions idempotent, conflicting option terms fail closed, and
   deterministic batch replay reconstruct exact state/ledger fingerprints; and
9. prohibit entry fills, new-position creation, closeout, mark-to-market,
   provider/broker/order access, PAPER/LIVE, promotion, and confluence authority.

The lifecycle-native fill/funding evidence layer described below is required before
the reservation-to-position mutation because the earlier accepted evidence contracts
are explicitly bound to the legacy reservation-only account contract.

## Track A lifecycle-native re-entry fill/funding evidence — 2026-09-18

Track A now freezes two post-close descriptive evidence contracts:

- `atlas-simulation-lifecycle-entry-fill-evidence-v1` —
  `a2bcaddbfba19370af070217cd2c4b911b121797abb76348747e575e17aa3b3c`;
- `atlas-simulation-lifecycle-funding-terms-v1` —
  `26266be782240511baadeb73d11aef393aaa6a52f12883b30cd3aab025f54870`.

A separate lifecycle version is required because the earlier entry-fill and funding
contracts explicitly bind the legacy reservation-only account-state v2 contract. The
post-close authoritative account now carries realized P&L, fee history, open positions,
closed trades, and current reservations under the lifecycle reservation contract.
Changing only a fingerprint field on the old evidence would violate the frozen input
contract.

Frozen semantics:

1. bind fill evidence to one exact current lifecycle reservation-state fingerprint,
   one exact active reservation, decision/candidate lineage, and explicit source
   id/SHA-256;
2. stock fills materialize the complete reserved economic notional and derive quantity
   from the explicit fill price, while leaving stock funding unresolved;
3. long-option fills reuse exact accepted reservation terms/contract count/multiplier,
   cap premium debit and entry fees at the reserved buckets, and record unspent reserve;
4. lifecycle stock funding is fully cash-funded and may use only the existing
   reservation plus current unreserved lifecycle cash;
5. lifecycle option funding reuses the exact reserved debit, requires zero supplemental
   cash, and preserves unspent reservation;
6. fill and funding fingerprints must bind the same current lifecycle reservation state
   and exact active reservation;
7. prior open/closed history, realized P&L, and fee history are inputs only and are not
   recomputed or mutated; and
8. no reservation release, new position, provider/broker/order, PAPER/LIVE, promotion,
   or confluence authority is granted.

The atomic reservation-to-position layer described below now consumes this evidence.

## Track A lifecycle-native reservation-to-position state — 2026-09-18

Track A now freezes `atlas-simulation-lifecycle-position-account-v1` under contract
`7c5f2a82a8583b9f7b2e90f994f7d6ca4c682888448b97ad287e79e6dad82f29`.

Frozen semantics:

1. initialize from one exact accepted lifecycle reservation state + reservation ledger
   fingerprint and carry all prior open/closed history, fees, realized P&L and book
   equity forward;
2. require lifecycle entry-fill and funding evidence to bind that immutable source
   reservation-state fingerprint;
3. require the exact matched reservation to remain active at mutation time, remove it
   once, and create one exact new open position/cost basis;
4. expense the new entry fee once while leaving prior realized P&L and exit-fee history
   unchanged;
5. reconcile book equity both as
   `initial_equity - cumulative_entry_fees + cumulative_account_realized_pnl` and as
   current cash + remaining reservations + open entry-book value;
6. enforce current-cash competition during deterministic multi-entry application even
   when each fill/funding object was independently fundable against the common source
   snapshot;
7. order competing entries by fill timestamp then fill fingerprint;
8. make identical duplicate entry application idempotent, reject conflicting second
   fills, and provide fingerprint-chained deterministic replay; and
9. grant no new-reservation, exit/closeout, mark-to-market, provider/broker/order,
   PAPER/LIVE, promotion, or confluence authority.

The accepted post-reentry valuation, exit-evidence, and deterministic closeout layers
described below now complete the bounded one-generation lifecycle bridge.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation account architecture only.

## Track A lifecycle post-reentry marked-account state — 2026-09-18

Track A freezes `atlas-simulation-lifecycle-position-marked-account-v1` under
contract
`ba944922450d570ac15b6b28794cfe0cb2c7894cba0e62d09e0957df35c92863`.

Frozen semantics:

1. consume one exact accepted lifecycle position-account state;
2. reuse position-bound market-mark evidence for inherited and newly re-entered open
   positions;
3. require exactly one fresh, valuation-eligible mark for every current open position
   at one common valuation timestamp;
4. reject missing, duplicate, stale, closed-position, or other extra marks;
5. carry cash, reservations, entry/exit fees, realized P&L, lifetime trade net P&L,
   closed history, and book equity forward unchanged;
6. compute unrealized P&L only from current open positions;
7. define marked equity as `account_book_equity + aggregate_unrealized_pnl` and
   independently reconcile it to cash + reservations + marked open-position value; and
8. grant no account mutation, new realized-P&L, exit/closeout, provider/broker/order,
   PAPER/LIVE, promotion, or confluence authority.

## Track A lifecycle-native post-reentry exit-fill evidence — 2026-09-18

Track A freezes `atlas-simulation-lifecycle-exit-fill-evidence-v1` under contract
`f3a952f971d693dbc0ca098d9eb5ff912d54443b9dcf2580409bb5558285df74`.

Frozen semantics:

1. bind one exact lifecycle position-account state fingerprint and exact current active
   position fingerprint;
2. inherit exact position quantity/unit, multiplier, instrument/option identity, and
   entry-fill/funding/reservation lineage;
3. require an explicit source id/SHA-256, timezone-aware exit timestamp, nonnegative
   exit price, and explicit nonnegative exit fees;
4. require exit time to be at or after both lifecycle position state and position open;
5. compute gross proceeds as `quantity * exit_price * multiplier` and net proceeds as
   gross less exit fees;
6. permit zero-price complete-loss exits while preventing fees from exceeding gross
   proceeds;
7. remain full-close only; and
8. grant no position/account mutation, realized P&L, provider/broker/order, PAPER/LIVE,
   promotion, or confluence authority.

## Track A lifecycle-native post-reentry deterministic closeout — 2026-09-18

Track A freezes `atlas-simulation-lifecycle-closeout-account-v1` under contract
`9588c3ac326a78103803371071655f0133608beaf0fb10ee7932b3cf0cbace1b`.

Frozen semantics:

1. initialize from one exact lifecycle position-account state + ledger fingerprint;
2. require each exit to bind that immutable source state and one exact current open
   position with complete entry/funding/reservation lineage;
3. remove only the matched position, preserve reservations and unrelated positions, and
   return exact net exit proceeds to cash;
4. preserve pre-reentry `ClosedTradeV1` history exactly and append separate
   `LifecycleClosedTradeV1` records with lifecycle-native source provenance;
5. add new exit fees and realized P&L once while never re-expensing entry fees;
6. preserve account realized-P&L delta as
   `net_exit_proceeds - entry_book_value` and lifetime trade net P&L as that delta
   minus the already-expensed entry fee;
7. reconcile book equity both from fee/realized history and from cash + reservations +
   remaining open entry-book value;
8. make identical exit-fill reuse idempotent, reject conflicting second closes, order
   batches by exit timestamp/fingerprint, and require exact deterministic replay; and
9. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

## Track A stable recurrent lifecycle account foundation — 2026-09-18

Track A now consolidates the accepted one-generation bridge into
`atlas-simulation-recurrent-lifecycle-account-v1` under contract
`9a22ebdb75a85c7d602851f48ae19a4262b0ab5a28441fc80f26b22a96781299`.

This is the stable multi-cycle account contract rather than another numbered
reservation/position/closeout copy.

Frozen foundation semantics:

1. bootstrap from one exact accepted lifecycle-closeout state + ledger;
2. preserve current cash, active reservations, open positions, fee history, realized
   P&L, lifetime trade net P&L, and account book equity exactly;
3. canonicalize both original `ClosedTradeV1` and lifecycle
   `LifecycleClosedTradeV1` history into one recurrent closed-trade collection while
   retaining each record's original source-contract fingerprint, source-state
   fingerprint, and source-record fingerprint;
4. keep historical economics and fee/P&L values independently verifiable after
   canonicalization;
5. freeze one append-only recurrent ledger schema broad enough for reservation, entry,
   and closeout transitions against this same account contract;
6. start the recurrent ledger at the exact bootstrap recurrent-state fingerprint;
7. keep market valuation as a read-only projection rather than a ledger mutation; and
8. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The recurrent reservation transition layer described below now begins mutating this
same stable account and append-only ledger.

The Strategy Evidence Register remains unchanged because this package consolidates
product/simulation account architecture without changing strategy evidence.

## Track A recurrent lifecycle reservation transitions — 2026-09-18

Track A freezes `atlas-simulation-recurrent-reservation-transitions-v1` under
contract
`8e7cb6b4cf3d64bcafc8f0af9443bde8022df92c5b200aec67f4611fbedae796`.

Frozen semantics:

1. consume and return the same `RecurrentLifecycleAccountV1` contract;
2. append reservation/abstention/rejection events to the existing recurrent ledger
   rather than creating a new reservation-account generation;
3. evaluate stock and option reservation admission against current unreserved recurrent
   cash while preserving current open positions and canonical closed history;
4. preserve stock reserved capital/gross notional separately from long-option reserved
   capital, max-loss, premium-at-risk, and signed/absolute delta-equivalent exposure;
5. require exact accepted long-option reservation terms for OPTION decisions;
6. retain exact decision, reservation, option-terms/economics, candidate, contract,
   instrument, ticker, direction, state-chain, and monetary/exposure delta lineage in
   the recurrent event;
7. ledger abstentions and insufficient-capital/missing-terms rejections without money
   mutation so account time still advances deterministically;
8. make duplicate decisions idempotent, reject conflicting duplicate option terms, and
   order batches by decision timestamp then decision fingerprint; and
9. grant no entry-fill, open-position, exit/closeout, provider/broker/order,
   PAPER/LIVE, promotion, or confluence authority.

The recurrent entry/funding evidence layer described below now binds complete
broker-neutral entry evidence to the same current recurrent snapshot.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation account transitions only.

## Track A recurrent lifecycle entry-fill/funding evidence — 2026-09-18

Track A freezes two descriptive operation contracts:

- `atlas-simulation-recurrent-entry-fill-evidence-v1` —
  `6802682c78dac10921afd49a023bab774dded6d5c8415e53f17ac92f852bf15a`;
- `atlas-simulation-recurrent-funding-terms-v1` —
  `4340cbe3d39b1026663db416094093814dab691ef611e7fca8a8a93e5023b6fc`.

Frozen semantics:

1. bind fill and funding evidence to one exact current recurrent-state fingerprint and
   one exact still-active reservation fingerprint;
2. preserve exact decision/candidate lineage and explicit fill-source id/SHA-256;
3. stock fills materialize the reserved economic notional and derive complete quantity
   from explicit fill price without inferring stock funding;
4. long-option fills reuse exact accepted reservation terms, contract count/multiplier,
   and premium/fee buckets while recording unspent reserve;
5. bullish stock funding uses only reserved capital plus current recurrent unreserved
   cash, with no borrowing, margin, or short-sale proceeds inference;
6. long-option funding reuses the exact reserved debit with zero supplemental cash;
7. historical closed-trade/fee/realized-P&L state is input-only and is not recomputed;
   and
8. no reservation release, position creation, provider/broker/order, PAPER/LIVE,
   promotion, or confluence authority is granted.

The recurrent reservation→position transition described below now consumes this
evidence against the same recurrent account/ledger contract.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation account evidence only.


## Track A recurrent lifecycle reservation-to-position transitions — 2026-09-18

Track A freezes `atlas-simulation-recurrent-position-transition-v1` under contract
`998b3c505aaabd429b5009cb1c9cfebe864810f2d6e871d60450f4ccc2d7e084`.

Frozen semantics:

1. consume and return the same `RecurrentLifecycleAccountV1` contract rather than
   creating another position-account generation;
2. require recurrent fill and funding evidence to bind one exact accepted recurrent
   source snapshot and one exact still-active reservation;
3. consume only the matched reservation, create one exact
   `SimulatedOpenPositionV1`, and append one fingerprint-chained `OPEN_POSITION`
   event to the existing recurrent ledger;
4. expense the new entry fee exactly once while preserving canonical closed history,
   prior exit fees, account-realized P&L, and lifetime trade net P&L;
5. transfer stock or option reservation exposure into the corresponding open-position
   entry-book/exposure fields without conflating stock gross notional and option
   delta-equivalent reference exposure;
6. require single-entry evidence to bind the exact current state; permit deterministic
   batches only when every fill/funding pair binds one common source snapshot;
7. order batch entries by fill timestamp then fill fingerprint and recheck current cash
   and reservation availability at each mutation so multiple fills cannot spend the
   same supplemental cash twice;
8. make exact duplicate fill/funding reuse idempotent, reject conflicting second fills,
   and require exact state/ledger replay; and
9. grant no exit/closeout, mark-to-market, provider/broker/order, PAPER/LIVE,
   promotion, or confluence authority.

The recurrent marked-account projection described below now supplies current valuation
without changing the stable recurrent state or ledger.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation account transitions only.

## Track A recurrent lifecycle marked-account projection — 2026-09-18

Track A freezes `atlas-simulation-recurrent-marked-account-v1` under contract
`6f473d2480167efa77e7826c994661d12141621122e99b644cb58cc39bbf5532`.

Frozen semantics:

1. consume one exact accepted recurrent lifecycle account state;
2. require exactly one fresh, valuation-eligible position-bound mark for every current
   open position at one common valuation timestamp;
3. reject missing, duplicate, stale, closed-position, or other extra marks;
4. value inherited and newly recurrent-opened positions through their immutable
   position fingerprints;
5. compute aggregate unrealized P&L from current open positions only;
6. define marked equity as `account_book_equity + aggregate_unrealized_pnl` and
   independently reconcile it to cash + reservations + marked open-position value;
7. carry cash, reservations, fee/realized-P&L history, book equity, canonical closed
   history, and the recurrent ledger forward unchanged; and
8. grant no account mutation, new realized-P&L, exit/closeout,
   provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The recurrent exit-evidence layer described below now supplies the full-close
descriptive boundary.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation valuation architecture only.

## Track A recurrent lifecycle exit-fill evidence — 2026-09-18

Track A freezes `atlas-simulation-recurrent-exit-fill-evidence-v1` under contract
`61135bbede1416c852d7c84fa2914876c056508be9fdad1a87b834cb71f659ad`.

Frozen semantics:

1. bind one exact current recurrent-state fingerprint and exact active position;
2. preserve the separate immutable entry-source account-state fingerprint carried by
   the position;
3. inherit exact decision/candidate/reservation/entry-fill/funding and option lineage;
4. require explicit source id/SHA-256, timezone-aware exit time, nonnegative price, and
   explicit nonnegative fees;
5. require a complete full-position close with exact quantity and multiplier;
6. compute gross proceeds as quantity × exit price × multiplier and net proceeds as
   gross less exit fees;
7. permit zero-price complete losses while rejecting fees above gross proceeds; and
8. grant no account/position mutation, realized P&L, recurrent-ledger mutation,
   provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The recurrent `CLOSE_POSITION` transition described below now consumes this evidence
on the same stable recurrent account and append-only ledger.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation exit evidence only.

## Track A recurrent lifecycle close-position transitions — 2026-09-18

Track A freezes `atlas-simulation-recurrent-close-position-transition-v1` under
contract
`9f2f32d8905c19bfb377184abd1fa3f9842eb979829ce5ca03c3a44068e17e39`.

Frozen semantics:

1. consume and return the same recurrent lifecycle account/ledger contract;
2. require exact recurrent exit evidence and one currently open matched position;
3. remove only the matched position while leaving active reservations and unrelated
   open positions unchanged;
4. return exact net exit proceeds to cash and append one fingerprint-chained
   `CLOSE_POSITION` ledger event;
5. append a canonical `RecurrentClosedTradeV1` with native
   `RECURRENT_ACCOUNT_V1` origin, exact recurrent source-state provenance, exact exit
   evidence fingerprint, and complete decision/candidate/reservation/entry/funding
   lineage;
6. compute account realized P&L as net proceeds minus entry-book value while lifetime
   trade net P&L additionally includes the already-expensed entry fee exactly once;
7. leave cumulative entry fees unchanged, add exit fees once, and maintain both book
   equity reconciliation formulas;
8. require exact-current-state evidence for a single close and support deterministic
   common-source-snapshot batches ordered by exit time then fingerprint;
9. make identical duplicate exit-fill application idempotent and reject conflicting
   second closes; and
10. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The stable recurrent simulation loop is now complete on one account contract:
reserve → entry evidence/funding → open → mark → exit evidence → close → reserve again.

The recurrent coordinator described below now owns that loop atomically.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation account transitions only.

## Track A recurrent lifecycle coordinator — 2026-09-18

Track A freezes `atlas-simulation-recurrent-lifecycle-coordinator-v1` under contract
`0cadfd2c89c09c26731b8895ca70893dde3855c3eded4773c4455bce94b8e882`.

Frozen semantics:

1. own one accepted recurrent lifecycle account behind one `RLock`;
2. delegate reservation, entry, valuation, and close work only to accepted recurrent
   transition/projection contracts;
3. initialize logical revision from the existing recurrent ledger-event count;
4. advance revision for every newly appended ledger event, including zero-money
   abstention/rejection events;
5. advance revision for each unique complete mark publication without mutating the
   account ledger;
6. invalidate current valuation after any real account-state mutation;
7. preserve a current valuation across exact idempotent mutation reuse and preserve
   revision across identical mark republication;
8. expose an atomic current account+marked-state pair only when exact source-state
   fingerprints match; and
9. perform no provider/broker/order/filesystem/network I/O and grant no PAPER/LIVE,
   promotion, or confluence authority.

The recurrent lifecycle observability layer described below now projects the atomic
runtime pair through the existing loopback/browser surface.

The Strategy Evidence Register remains unchanged because this package changes
product/simulation runtime architecture only.

## Track A recurrent lifecycle observability — 2026-09-18

Track A now projects recurrent runtime truth through the existing
`GET /api/v1/ops/simulation-lifecycle` endpoint.

Frozen semantics:

1. accept only an injected atomic recurrent account + recurrent marked-state pair;
2. revalidate recurrent account state/ledger fingerprints, marked-state fingerprint,
   exact source binding, carried accounting, and complete current mark coverage;
3. return `NOT_CONNECTED` when no current marked pair exists and `INVALID` for failed
   provenance validation rather than reconstructing state elsewhere;
4. expose recurrent account/ledger fingerprints and canonical closed-trade provenance
   while preserving the browser's existing account/position/P&L payload;
5. retain browser compatibility with older closeout provenance fields during migration;
6. allow Phase 19 injection of one explicit dashboard service, one legacy coordinator,
   or one recurrent coordinator and fail closed on ambiguous multiple sources;
7. perform no provider/broker initialization or refresh as part of lifecycle GET; and
8. reuse the existing observability refresh event with GET-only, zero browser/order
   mutation authority.

The durable recurrent checkpoint/restore layer described below now closes the
restart boundary while keeping recurrent ownership as the only current simulation
truth.

The Strategy Evidence Register remains unchanged because this package changes
product/control-plane architecture only.

## Track A durable recurrent lifecycle checkpoint/restore — 2026-09-18

Track A freezes `atlas-simulation-recurrent-lifecycle-checkpoint-v1` under contract
`53d34c03bf23157bb447cdf4ddb8902cd56ac008403efb8dd8145e596c45c2fa`.

Frozen semantics:

1. persist one exact recurrent coordinator snapshot, including logical revision,
   recurrent account state/ledger fingerprints, optional marked-state fingerprint, and
   the complete validated snapshot payload;
2. self-hash every checkpoint and preserve every superseded current checkpoint in
   content-addressed history before replacing the current projection;
3. use same-directory atomic temp/replace writes with `fsync=True`;
4. require monotonic revision, identical snapshot at equal revision, immutable
   recurrent ledger prefix, and unchanged recurrent bootstrap lineage;
5. allow exact duplicate persistence as idempotent reuse without growing history;
6. support expected-previous-checkpoint SHA binding so stale writers fail closed;
7. reconstruct the exact dataclass graph on restore and re-run all recurrent
   coordinator/account/ledger/marked-state invariants and fingerprints;
8. preserve mark-only coordinator revisions across restart even when revision exceeds
   recurrent ledger-event count;
9. restore Phase 19 from
   `data/live/simulation/recurrent_lifecycle/current.json` only; missing state remains
   `NOT_CONNECTED`, while invalid/corrupt authoritative state aborts startup instead
   of falling back to research or legacy artifacts; and
10. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The durable recurrent runtime transaction layer described below now closes this
mutation↔checkpoint boundary.

The Strategy Evidence Register remains unchanged because this package changes
product/runtime durability only.

## Track A durable recurrent runtime transaction boundary — 2026-09-18

Track A freezes `atlas-simulation-recurrent-durable-runtime-v1` under contract
`2959ba43c8279fd28cedeeca6df24f6f56edb6714a72cfc47999ea7e2bb3f891`.

Frozen semantics:

1. wrap one accepted recurrent coordinator plus one verified recurrent checkpoint
   behind a single runtime lock;
2. capture the exact pre-operation snapshot before reservation, entry, close-position,
   or mark-publication work;
3. require every changed post-operation snapshot to commit using the exact expected
   previous checkpoint SHA;
4. skip persistence entirely for exact idempotent operations whose coordinator snapshot
   does not change;
5. after a checkpoint exception, read durable state back and classify it against the
   exact pre/post snapshots;
6. if durable state is the pre-state, restore the in-memory coordinator to that
   snapshot and fail the operation as rolled back;
7. if durable state is the post-state, accept the commit even when an exception was
   surfaced after the atomic replace;
8. if durable state is unreadable or matches neither pre nor post state, enter
   `UNCERTAIN` and block current-state/dashboard/mutation access until explicit
   verified checkpoint reload;
9. restore Phase 19 production startup into the durable wrapper, not a naked recurrent
   coordinator; and
10. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The controlled recurrent genesis package described below now creates the first
authoritative durable account without a hidden balance or external account source.

The Strategy Evidence Register remains unchanged because this package changes
product/runtime durability and orchestration boundaries only.

## Track A one-time recurrent genesis bootstrap — 2026-09-18

Track A freezes `atlas-simulation-recurrent-genesis-bootstrap-v1` under contract
`2784da99747760b50ff5cab35ae6f761d9ec8a77378ce767e603960571130b2a`.

Frozen semantics:

1. require explicit positive starting simulation equity and a timezone-aware bootstrap
   timestamp; ATLAS embeds no default starting balance;
2. perform zero provider, broker, research-artifact, or legacy-current-state reads;
3. build the first recurrent account only by walking the accepted empty account chain:
   simulation v2 → open-position → closeout → lifecycle reservation → lifecycle
   position → lifecycle closeout → recurrent account;
4. require every intermediate transition ledger and every reservation/open/closed
   collection to be empty;
5. require recurrent cash and book equity to equal the explicit starting equity and all
   fee/P&L/exposure fields to be zero;
6. retain all intermediate state fingerprints plus the recurrent state/ledger
   fingerprints in the bootstrap result;
7. refuse to overwrite an existing recurrent current checkpoint;
8. refuse bootstrap when preserved recurrent checkpoint history exists without current
   state;
9. create the first authoritative checkpoint only through the durable recurrent runtime
   bootstrap path; and
10. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

The durable recurrent cycle orchestrator described below now freezes the stage ordering
and restart-safe receipt semantics.

The Strategy Evidence Register remains unchanged because this package changes
product/runtime bootstrap only.

## Track A durable recurrent simulation-cycle orchestration — 2026-09-18

Track A freezes `atlas-simulation-recurrent-cycle-receipt-v1`.

Frozen semantics:

1. consume accepted evidence only; provider and broker evidence acquisition remains
   outside the orchestrator;
2. execute exactly `CLOSE → RESERVE → ENTRY → MARK → COMPLETE`;
3. bind one cycle id/fingerprint to its source durable checkpoint SHA-256 and recurrent
   runtime snapshot fingerprint;
4. persist one atomic, fsync-backed, self-hash-verified cycle receipt and one ordered
   stage record for every stage, including explicitly empty stages;
5. fingerprint exact CLOSE exit fills, RESERVE decisions plus exact option reservation
   terms (or explicit absence), ENTRY fill+funding pairs, and MARK evidence plus the
   valuation timestamp;
6. make exact stage reuse idempotent and reject reuse with conflicting evidence;
7. reconcile an interrupted post-runtime/pre-receipt stage by proving the exact action
   fingerprints already exist in recurrent ledger/marked state before recording the
   missing receipt, preventing double application;
8. fail closed on stage-order violations, unexplained runtime checkpoint advancement,
   receipt tampering, broken checkpoint/snapshot chains, or durable runtime uncertainty;
9. complete a cycle only after all four stage records exist and current durable runtime
   state still equals the MARK-stage result; and
10. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

A bounded post-genesis smoke CLI, `scripts/run_recurrent_empty_cycle.py`, may run only
when the recurrent account has no active reservations or open positions. It executes an
empty four-stage cycle and publishes an empty marked state to prove checkpoint/receipt
restart behavior with zero provider/broker reads.

Immediate Track A continuation is the production cycle runner and evidence-admission
surface: deterministic cycle ids/schedule, explicit current-evidence acquisition
outside the orchestrator, operator-visible cycle health/receipts, and workstation
restart/resume proof before any qualifying PAPER program.

The Strategy Evidence Register remains unchanged because this package changes
product/runtime orchestration only.










## Track A deterministic recurrent cycle runner admission — 2026-09-18

Track A freezes `atlas-simulation-recurrent-cycle-runner-v1` under contract
`2de1540cddf58f0c724efbbd25378800143de586c7d0f159fefa2e4af0ac5e0d`.

Frozen semantics:

1. derive the cycle id deterministically from an explicit safe schedule id plus an
   explicit timezone-aware scheduled slot normalized to UTC;
2. grant no scheduler-trigger authority merely because deterministic slot identity
   exists;
3. restore only the authoritative durable recurrent checkpoint;
4. before each CLOSE, RESERVE, ENTRY, or MARK mutation, persist one atomic/fsync,
   self-hash-verified stage-admission record;
5. bind each admission to cycle/stage identity, the exact expected pre-stage checkpoint
   and runtime snapshot, evidence-source id/SHA-256, evidence fingerprint/count, and
   stage context;
6. admit evidence stage by stage so later entry/mark evidence is built against state
   produced by prior accepted stages rather than stale pre-cycle state;
7. make exact admission reuse idempotent and reject conflicting admission reuse before
   mutation;
8. delegate mutation idempotency and post-runtime/pre-receipt crash reconciliation to
   the accepted recurrent-cycle orchestrator;
9. keep provider/broker acquisition and current-evidence construction outside the
   runner; and
10. grant no provider/broker/order, PAPER/LIVE, promotion, or confluence authority.

Immediate Track A continuation is the current-evidence acquisition adapter and
read-only cycle-health projection, followed by workstation restart/resume and
market-hours validation before any qualifying PAPER program.

The Strategy Evidence Register remains unchanged because this package changes
product/runtime admission and orchestration only.

## Track A current live evidence adapter and cycle health — 2026-09-18

Track A freezes `atlas-simulation-current-live-evidence-v1` under contract
`6502f8b9a4644705ec819bf7ecfcc3ee8b65742f4016454e497b0da8aca5deb0`
and adds a GET-only recurrent-cycle health projection.

Frozen semantics:

1. read only the persisted `data/live/market_state/current.json` artifact; perform zero
   provider or broker network calls as part of evidence capture;
2. hash the exact raw source bytes and validate the accepted `LiveStateSnapshot`
   schema before exposing current evidence;
3. reject a future-dated snapshot, duplicate exact-case symbols, or minute/quote
   feed-mode, expected-delay, or symbol lineage that disagrees with the enclosing
   snapshot;
4. preserve explicit feed mode, delay, connection/session state, freshness counts,
   source SHA-256 and normalized evidence fingerprint;
5. forbid minute-bar-to-bid/ask fabrication: valid delayed `AM.*` evidence may have
   zero quote coverage and must remain unsuitable for executable mark construction;
6. restore the authoritative recurrent checkpoint read-only for cycle health;
7. validate recent durable cycle receipts and runner admission records and report
   current stage, next action, runtime revision, reservations and open-position counts;
8. report corrupt receipts/admissions as degraded health and missing checkpoint/current
   evidence explicitly rather than reconstructing hidden state;
9. expose the projection at `GET /api/v1/ops/recurrent-cycle-health`; and
10. grant no browser mutation, provider/broker/order, scheduler-trigger, PAPER/LIVE,
    promotion, or confluence authority.

Immediate Track A continuation is stage-specific production evidence construction.
RESERVE decisions must come from the accepted forecast/economics/selection path, while
CLOSE/ENTRY/MARK evidence must use real execution-quality current sources. The current
Massive Starter delayed minute feed is not reinterpreted as executable quote evidence;
broker/finalist quote integration and workstation market-hours validation remain
required before qualifying PAPER.

The Strategy Evidence Register remains unchanged because this package changes
product/runtime evidence admission and read-only operations visibility only.

## Track A realtime current-stock mark adapter — 2026-09-18

Track A freezes `atlas-simulation-current-stock-mark-adapter-v1` under contract
`2ff8bfc7afff4b072b37e364a46aa565d40d4d91a29a799de0aece13bb2ac4c0`.

Frozen semantics:

1. consume only accepted `atlas-simulation-current-live-evidence-v1` plus exact open
   stock-position records;
2. perform zero provider/broker calls inside the adapter;
3. require a subscribed real-time snapshot with zero expected delay and no open
   transport gap;
4. require exact-case symbol coverage and a fresh quote for every supplied stock
   position;
5. reject any option position in v1 rather than substituting underlying stock prices;
6. reject minute-only state and never fabricate bid/ask from OHLC;
7. require quote market time to postdate position open and preserve
   market <= receive <= valuation chronology;
8. reuse the accepted market-mark contract and reject any mark outside its frozen
   60-second freshness policy;
9. return deterministic complete mark batches bound to source evidence/raw SHA and
   valuation time; and
10. grant no provider/broker/order/PAPER/LIVE, promotion, or confluence authority.

Immediate continuation is RESERVE decision production and execution-quality ENTRY/CLOSE
evidence construction, including explicit fee/fill semantics and the accepted
broker/finalist quote source. Real-machine market-hours acceptance remains required
before non-empty production MARK cycles.

## Track A current Webull L1 quote bundle and stock marks — 2026-09-18

Track A freezes two current-deployment contracts:

- `atlas-execution-current-webull-stock-quote-bundle-v1`:
  `5c2df876e2d9814434d6823f04c2cd0e6bfcdbe9b071cf291213abb634f2d26d`;
- `atlas-simulation-current-webull-stock-mark-adapter-v1`:
  `586b58a791e14cc21a3bb02f8d556a35785deae335a4153cee5bd37d30f33148`.

Frozen semantics:

1. require an explicit, sorted, unique exact-case stock symbol set;
2. invalidate the prior current bundle when a new capture begins, then capture exactly
   one Webull sandbox L1 read per requested symbol and persist no partial bundle when any
   requested symbol fails;
3. require positive uncrossed bid/ask, provider timestamp, zero-delay realtime
   semantics, regular-session classification, and the accepted execution age cap;
4. retain quote/source timestamps, sizes, read count, exact requested coverage and a
   self-fingerprint in one fsync-backed atomic local artifact;
5. perform no account read, provider write, broker write, order creation, PAPER or LIVE
   mutation during capture;
6. construct marks later from the local bundle with zero additional network calls;
7. require exact recurrent stock-position identity and complete exact-case quote
   coverage;
8. reject option positions rather than substituting underlying stock quotes;
9. preserve the stricter 30-second execution quote freshness cap while reusing the
   accepted generic market-mark contract; and
10. grant no provider/broker/order/PAPER/LIVE, promotion, or confluence authority merely
    because quote evidence or marks exist.

Immediate continuation is RESERVE decision production and execution-quality ENTRY/CLOSE
evidence construction with explicit fee/fill semantics. Target-machine market-hours
Webull sandbox capture remains an acceptance gate before non-empty recurrent MARK
cycles.

The Strategy Evidence Register remains unchanged because this package adds product
current-evidence plumbing and simulation marks without changing research evidence.

## Track A durable recurrent RESERVE evidence — 2026-09-18

Track A freezes `atlas-simulation-recurrent-reserve-evidence-bundle-v1` under contract
`e410ab31187b4b35cd5c036ba02073f63de41dd35269f33af4b9ff10357de875`.

Frozen semantics:

1. bind every bundle to one deterministic recurrent cycle id/fingerprint and schedule;
2. consume only accepted `SimulationDecisionRecord` objects plus optional accepted
   `LongOptionReservationTerms`;
3. preserve explicit abstentions as RESERVE-stage evidence instead of dropping them;
4. forbid option terms on stock/abstain decisions and require exact terms for every
   selected option;
5. validate exact decision, chosen-candidate, forecast, underlying and direction lineage
   for option terms;
6. deterministically order decisions by decision timestamp then record fingerprint and
   reject duplicates or decisions later than bundle construction time;
7. persist the complete typed evidence atomically with fsync at
   `data/live/simulation/recurrent_reserve/current.json`;
8. reconstruct every stored decision through the accepted deterministic decision
   builder and require the rebuilt complete record to equal the stored payload before
   admission;
9. expose the bundle fingerprint/source id directly to the recurrent runner's RESERVE
   admission boundary; and
10. perform zero provider/broker calls and grant no order/PAPER/LIVE, promotion, or
    confluence authority.

Immediate continuation is durable ENTRY/CLOSE evidence production with exact
execution-quality quote/fill/fee lineage, then target-workstation restart/resume and
market-hours cycle acceptance.

The Strategy Evidence Register remains unchanged because this package adds product
simulation evidence persistence and admission without changing research evidence.

## Track A current Webull stock ENTRY evidence — 2026-09-18

Track A freezes `atlas-simulation-current-webull-stock-entry-evidence-bundle-v1` under
contract `2a5635ce3cffff6eadeda16a2857a6b71acfb6daa267f786caa9e2aa803d070d`.

Frozen semantics:

1. consume one accepted post-RESERVE recurrent account, one exact durable RESERVE
   evidence bundle, one accepted Webull stock L1 quote bundle and one explicit
   fingerprinted fee source;
2. perform zero provider/broker calls inside ENTRY evidence construction;
3. preserve abstentions and explicit insufficient-capital RESERVE rejections as no-entry
   outcomes;
4. require every active recurrent reservation to be represented by current RESERVE
   decision evidence and fail closed on orphan reservations;
5. support active stock reservations only in v1; active option reservations fail closed;
6. require exact-case regular-session quote coverage received after the post-RESERVE
   recurrent state and within the accepted 30-second execution age cap;
7. use the Webull ask as the stock simulated complete entry price while preserving the
   already-reserved gross notional as the quantity source;
8. require explicit nonnegative entry fees with exact active-stock decision coverage—no
   implicit zero-fee default;
9. build accepted recurrent fill and funding records, then dry-run the whole recurrent
   entry batch so competing supplemental cash needs are validated before admission; and
10. persist deterministic fill/funding pairs atomically with fsync and grant no
    provider/broker/fill/order/PAPER/LIVE, promotion or confluence authority.

That original continuation direction is superseded by the 2026-09-19 lineage audit
below. Recurrent exit planning now consumes the accepted product-side
`UnderlyingMoveTimeForecast -> SimulationDecisionRecord` lineage directly; Phase 13
`TradeGeometry` is not a recurrent exit dependency.

The Strategy Evidence Register remains unchanged because this package advances product
simulation execution evidence rather than research findings.

## Track A decision-bound recurrent stock exit-plan book — 2026-09-19

A lineage audit retired PR #150 unmerged despite 20/20 green exact-head CI. That branch
attempted to reintroduce Phase 13 reference geometry as a required recurrent exit source,
which conflicted with the accepted separately versioned product sequence:
`UnderlyingMoveTimeForecast -> SimulationDecisionRecord -> RESERVE -> ENTRY`.
`Phase13CaseFile` remains unchanged/legacy-compatible and is not current recurrent
exit truth.

The replacement freezes
`atlas-simulation-recurrent-decision-stock-exit-plan-v1` under contract
`445d820b0d4268f10d66b842e3ed341ccadd94363418edf2f4ff30f755e44754`.

Frozen semantics:

1. consume exact accepted `SimulationDecisionRecord` plus exact recurrent bullish stock
   open-position lineage; open option positions fail closed in v1;
2. require an explicit non-authoritative stock-exit policy id/fingerprint for every
   newly opened position;
3. require both explicit stop and target fractions to match threshold fractions already
   present in the original accepted `UnderlyingMoveTimeForecast`; no hidden threshold
   default or Phase 13 geometry substitution is allowed;
4. permit different stop and target threshold fractions while retaining the exact
   corresponding threshold-probability/path-order evidence;
5. derive stop/target only from the actual simulated entry fill:
   `stop = entry × (1-stop_fraction)`,
   `target = entry × (1+target_fraction)`;
6. preserve the full immutable decision record, forecast fingerprint, selected candidate
   fingerprint, explicit policy, actual fill and original forecast horizon in each plan;
7. preserve forecast horizon as evidence only—time-exit triggering remains disabled
   until a separate clock-policy contract is accepted;
8. persist one durable **open-position plan book**: existing open-position plans are
   immutable/carried forward, new positions require current RESERVE decision evidence,
   and plans for positions absent from current authoritative state are pruned;
9. require exact coverage of every current open bullish stock position and persist the
   deterministic self-fingerprinted book atomically with fsync at
   `data/live/simulation/recurrent_decision_stock_exit_plan/current.json`;
10. centralize persisted `SimulationDecisionRecord` typed reconstruction in the
    decision-record layer and make RESERVE reuse that canonical deterministic decoder;
11. perform zero provider/broker reads or writes and grant no trigger, CLOSE-fill,
    order, PAPER/LIVE, promotion or confluence authority.

Immediate continuation is current Webull L1 stock CLOSE evidence against this plan book:
exact current-position/plan/quote coverage, executable bid for bullish exits, explicit
STOP/TARGET/NO_TRIGGER disposition, explicit fees only for triggered positions, durable
evidence/readback, and pure close-batch dry-run before recurrent runner admission.
Time-based exit remains separately gated.

The Strategy Evidence Register remains unchanged because this package repairs and
advances product simulation architecture without changing strategy evidence.

## Track A current Webull decision-bound stock CLOSE evidence — 2026-09-19

Track A freezes **atlas-simulation-current-webull-decision-stock-close-evidence-bundle-v1** under
contract **3834abe2212b794a04ce70b5595d992de38cea77ac82185e6daaf6134bd6db96**.

Frozen semantics:

1. consume only the exact current recurrent account, accepted decision-bound
   open-position exit-plan book and current Webull sandbox stock L1 evidence;
2. require exact open-position ↔ plan coverage and fail closed on option or bearish
   stock positions in v1;
3. require exact-case current ticker quote coverage for every open position, with
   zero-delay realtime, regular-session, post-state chronology and the accepted
   30-second execution age cap;
4. require quote-bundle capture time no later than CLOSE evidence construction;
5. classify bullish stock exits from executable bid only: STOP at/below stop, TARGET
   at/above target, otherwise explicit NO_TRIGGER;
6. preserve NO_TRIGGER as durable evidence with no exit fill and no fee source;
7. require exact explicit nonnegative fee coverage and one fingerprinted fee source
   only for STOP/TARGET positions;
8. create accepted recurrent full-close fill evidence at the exact bid and bind fill
   source lineage to the plan-book, quote-bundle, exact plan/quote/disposition and fee;
9. dry-run all triggered fills through the accepted pure recurrent close-batch
   transition before evidence acceptance;
10. retain the complete plan book and quote bundle inside the CLOSE artifact so typed
    readback re-proves nested source lineage instead of trusting fingerprints alone;
11. treat zero-open-position CLOSE as provider-inert: no quote bundle, fee source or
    exit-fee evidence is permitted;
12. persist the deterministic self-fingerprinted bundle atomically with fsync at
    data/live/simulation/recurrent_decision_stock_close/current.json;
13. reuse a canonical typed exit-plan-book decoder for standalone and nested readback;
    and
14. grant no provider/broker write, broker-fill, order, PAPER/LIVE, promotion or
    confluence authority. Time-exit evaluation remains disabled in v1.

Immediate continuation is to integrate exit-plan-book refresh into the recurrent
production sequence immediately after ENTRY, then freeze a separate horizon/clock
policy before time can trigger CLOSE. After those deterministic seams are accepted,
run the target-workstation market-hours Webull sandbox and restart/resume acceptance
proof.

The Strategy Evidence Register remains unchanged because this package advances product
simulation execution/lifecycle plumbing without changing strategy research evidence.

## Track A restart-safe post-ENTRY exit-plan refresh — 2026-09-19

Track A freezes **atlas-simulation-recurrent-exit-plan-refresh-v1** under contract
**7cf394ab6ba2fd3dc7e506a7718acb9f90ff647a55ed7b68c0a6a5f4eade2abc**.

Frozen semantics:

1. remain a sidecar orchestration receipt rather than changing the accepted recurrent
   CLOSE → RESERVE → ENTRY → MARK mutation-stage order;
2. run only while the cycle is OPEN with exactly CLOSE, RESERVE and ENTRY recorded;
   MARK already present or ENTRY missing fails closed;
3. require the durable runtime checkpoint SHA, snapshot fingerprint and revision to
   equal the post-ENTRY cycle receipt;
4. persist the immutable ENTRY stage-record fingerprint and independently persisted
   ENTRY stage-admission SHA so refresh lineage remains provable after MARK/COMPLETE
   rewrites the cycle receipt file;
5. when a current RESERVE bundle is supplied, require its cycle identity and bundle
   fingerprint to equal the actual admitted RESERVE evidence source;
6. bind explicit exit-policy inputs to decision-record fingerprints in deterministic
   order and preserve exact policy fingerprints in the refresh receipt;
7. refresh the accepted durable open-position plan book: carry valid existing plans,
   require current RESERVE decision evidence plus explicit policy for new positions,
   and prune positions no longer open;
8. use the ENTRY stage recorded timestamp as deterministic plan-book/refresh effective
   time so retries do not create time-dependent fingerprints;
9. atomic/fsync-write the plan book first and then a self-fingerprinted per-cycle
   refresh receipt adjacent to the recurrent checkpoint;
10. reuse exact recorded refreshes idempotently and reject conflicting reuse;
11. recover the interrupted book-written/receipt-missing window only when the current
    book already binds the exact current recurrent state, deterministic ENTRY timestamp,
    and supplied policies match;
12. leave the generic v1 cycle runner and zero-evidence smoke semantics unchanged; the
    production-cycle facade below now enforces ENTRY → refresh → MARK;
13. perform zero provider/broker reads or writes and grant no order, PAPER/LIVE,
    promotion or confluence authority.

Time-based exits remain separately gated. The accepted move/time schema names MINUTES
and SESSIONS horizons but does not yet freeze whether MINUTES means wall-clock versus
regular-session elapsed time or the exact exchange-session counting rule for SESSIONS.
A clock trigger must not be inferred until those semantics are separately contracted.

The plan-aware production-cycle facade below now consumes this refresh boundary without
modifying the generic runner. Immediate continuation is therefore the explicit
horizon/clock contract, followed by target-workstation market-hours/restart-resume
acceptance.

The Strategy Evidence Register remains unchanged because this package advances durable
product orchestration rather than strategy evidence.

## Track A plan-aware recurrent production-cycle facade — 2026-09-19

Track A freezes **atlas-simulation-recurrent-production-cycle-v1** under contract
**c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca**.

Frozen semantics:

1. compose, rather than replace, the accepted deterministic recurrent runner;
2. preserve the generic mutation order CLOSE → RESERVE → ENTRY → MARK;
3. freeze the exact accepted dependency fingerprints for runner, RESERVE, Webull
   stock ENTRY, post-ENTRY refresh, decision-bound exit-plan book, Webull CLOSE, and
   Webull stock MARK;
4. on first CLOSE application, require the evidence bundle to bind the exact current
   recurrent state; exact durable retries use the existing stage admission;
5. require accepted RESERVE evidence for the same cycle;
6. on first ENTRY application, require the bundle to bind current recurrent state and
   the exact already-admitted RESERVE bundle; exact durable retries again use stage
   admission rather than post-mutation state;
7. before first MARK admission, run or idempotently recover/reuse the accepted
   post-ENTRY exit-plan refresh;
8. re-prove refresh lineage from the durable refresh receipt, immutable ENTRY stage
   fingerprint, ENTRY admission SHA, ENTRY result checkpoint/snapshot/revision, exact
   current account state, exact RESERVE bundle, policy bindings and durable plan book;
9. require exact current Webull stock-mark coverage for every open stock position and
   matching valuation time; zero-position MARK remains provider-inert;
10. make recorded MARK retry idempotent by verifying the existing MARK admission and
    returning the recorded receipt without reopening runtime mutation, including after
    cycle completion;
11. support direct restore from the durable recurrent checkpoint after process restart;
12. delegate COMPLETE to the accepted generic runner and leave the zero-evidence smoke
    runner backward-compatible; and
13. perform no provider/broker acquisition and grant no scheduler-trigger, broker-write,
    order, PAPER/LIVE, promotion or confluence authority.

The separately versioned forecast-horizon clock contract below now freezes the missing
MINUTES/SESSIONS deadline semantics without granting expiry-disposition or CLOSE
authority. Immediate continuation is a durable open-position horizon-clock book so session-policy
selection cannot drift between cycles, then a separately versioned time-expiry
disposition, explicit STOP/TARGET/TIME precedence, and target-workstation market-hours
Webull sandbox/restart-resume acceptance.

The Strategy Evidence Register remains unchanged because this package integrates
accepted product/runtime components without changing strategy evidence.

## Track A descriptive forecast-horizon exchange clock — 2026-09-19

Track A freezes **atlas-simulation-forecast-horizon-clock-v1** under contract
**5efb0fb3b6bd37ba718ced50d1ebcbd589843cc895aba33426aa6235c643a56a**.

Frozen semantics:

1. consume the exact accepted decision-bound recurrent exit plan and exact retained
   move/time forecast lineage;
2. freeze **XNYS** as the v1 exchange calendar because current recurrent evidence does
   not carry an authoritative per-position exchange identity;
3. define MINUTES as elapsed official regular-session minutes from actual simulated
   position open; premarket, after-hours, closed periods, overnight, weekends and
   exchange holidays contribute zero;
4. respect official early closes and carry remaining MINUTES into later official
   sessions;
5. retain the ordered session trace traversed by a MINUTES deadline;
6. require an explicit fingerprinted SESSIONS counting policy because the original
   forecast did not specify whether entry session counts;
7. support exactly `ENTRY_SESSION_INCLUDED` and
   `FULL_SESSIONS_AFTER_ENTRY`;
8. reject a session-counting policy for MINUTES and require one for SESSIONS;
9. retain exact exit-plan, forecast, decision, position and policy fingerprints plus
   entry session, horizon unit/value, deadline UTC, deadline session and counted
   sessions;
10. require the actual typed accepted exit-plan object and re-verify plan/forecast
    lineage before calculating the deadline;
11. emit **no evaluation timestamp and no expired boolean**—the clock is immutable
    descriptive deadline evidence only; and
12. grant no time-expiry disposition, price-trigger, CLOSE-fill, account-mutation,
    provider/broker, order, PAPER/LIVE, promotion or confluence authority.

Tests use real decision → RESERVE → Webull ENTRY → open-position → exit-plan lineage,
plus weekend carry, official early-close handling, both explicit SESSIONS modes,
arbitrary-exchange rejection and lookalike-plan rejection.

The durable open-position horizon-clock book below now retains the exact clock and
selected policy for every open simulated position across cycles. Immediate continuation
is therefore a separately versioned `TIME_EXPIRED / NOT_EXPIRED` disposition over the
immutable clock plus explicit evaluation UTC. A later CLOSE integration must then
freeze STOP/TARGET/TIME precedence before time expiry can produce a simulated exit fill.

The Strategy Evidence Register remains unchanged because this package resolves product
simulation clock semantics without changing strategy evidence.

## Track A durable open-position forecast-horizon clock book — 2026-09-19

Track A freezes **atlas-simulation-forecast-horizon-clock-book-v1** under contract
**b6badd42b77c47f5994db08f5c419991831c232041857f968bde80efd3514017**.

Frozen semantics:

1. consume and retain the complete typed accepted decision-bound exit-plan book;
2. require exactly one descriptive horizon clock for every current open exit plan;
3. require an explicit ForecastHorizonClockPolicyV1 for every newly unclocked
   position, including the explicit XNYS/no-session-counting policy for MINUTES;
4. require SESSIONS to retain the explicit accepted counting policy selected when the
   position is first clocked;
5. carry existing open-position clocks forward unchanged only when their exact
   exit-plan/forecast/decision/position/horizon lineage still matches;
6. reject policy resubmission for already-clocked positions, preventing SESSIONS policy
   drift between cycles;
7. prune clocks for plans no longer present in the authoritative open-position plan
   book;
8. order clocks deterministically by position fingerprint and use the source
   exit-plan-book timestamp as deterministic book time;
9. retain the full source exit-plan book inside the artifact so typed readback can
   re-prove nested lineage instead of trusting an external fingerprint alone;
10. persist one deterministic self-fingerprinted clock book atomically with fsync at
    `data/live/simulation/forecast_horizon_clock_book/current.json`; and
11. emit no evaluation timestamp or expired boolean and grant no time-exit disposition,
    price-trigger, CLOSE-fill, account-mutation, provider/broker, order, PAPER/LIVE,
    promotion or confluence authority.

The separately versioned `TIME_EXPIRED / NOT_EXPIRED` disposition below now consumes
the immutable clock book plus explicit evaluation UTC. Immediate continuation is
therefore the CLOSE precedence boundary that must freeze deterministic STOP/TARGET/TIME
ordering before time expiry may create an exit fill.

The Strategy Evidence Register remains unchanged because this package advances durable
product timing evidence rather than strategy research evidence.

## Track A explicit forecast-horizon time disposition — 2026-09-19

Track A freezes **atlas-simulation-forecast-horizon-time-disposition-v1** under contract
**eda75ce9e816942b46e9c215c429da0b568cd2d2012bba2b09c43fe0672a049b**.

Frozen semantics:

1. consume and retain the complete typed durable forecast-horizon clock book;
2. require one explicit timezone-aware evaluation UTC for the entire current clock set;
3. reject evaluation before any source position-open UTC;
4. emit `NOT_EXPIRED` only when evaluation UTC is strictly before deadline UTC;
5. emit `TIME_EXPIRED` when evaluation UTC is equal to or later than deadline UTC;
6. freeze deadline equality as expired rather than leaving boundary behavior implicit;
7. retain exact clock, position, instrument/ticker, position-open, deadline and
   evaluation lineage for every disposition;
8. require deterministic exact coverage of every current clock and re-derive each
   disposition during typed validation/readback;
9. persist the complete nested clock book and disposition set atomically with fsync at
   `data/live/simulation/forecast_horizon_time_disposition/current.json`;
10. permit an empty current clock book to produce an empty disposition set while still
    binding the explicit evaluation UTC; and
11. grant no price-trigger, STOP/TARGET/TIME precedence, CLOSE-fill, account-mutation,
    provider/broker, order, PAPER/LIVE, promotion or confluence authority.

The price-first time-aware CLOSE package below now consumes current price-trigger
evidence plus this time-disposition evidence and freezes exact STOP/TARGET/TIME
precedence. Immediate continuation is production-cycle facade integration followed by
target-workstation market-hours/restart-resume acceptance.

The Strategy Evidence Register remains unchanged because this package advances product
timing disposition evidence rather than strategy research evidence.

## Track A price-first time-aware Webull stock CLOSE — 2026-09-19

Track A freezes **atlas-simulation-current-webull-time-aware-stock-close-v1** under
contract **7b3a9f25959002ea070eca4611a16ce57f73771430d7075f855cd924ca7cac45**.

Frozen semantics:

1. retain and consume the complete accepted current Webull price-CLOSE bundle and
   complete explicit horizon time-disposition bundle;
2. require both sources to retain the exact same decision-bound exit-plan book;
3. require time evaluation UTC to equal the price-CLOSE build timestamp;
4. freeze price-first precedence: STOP remains STOP and TARGET remains TARGET even when
   time is expired;
5. permit TIME only for price NO_TRIGGER plus TIME_EXPIRED;
6. preserve price NO_TRIGGER plus NOT_EXPIRED as final NO_TRIGGER;
7. reuse accepted STOP/TARGET fills unchanged and prohibit separate time-fee evidence
   for those positions;
8. for TIME only, require the retained Webull quote receipt timestamp at or after the
   immutable horizon deadline, use the exact retained executable bid, and require exact
   explicit time-exit fees from one fingerprinted source;
9. require exact time-fee coverage only for final TIME positions and reject unused fee
   sources when there are no TIME exits;
10. dry-run all final STOP/TARGET/TIME fills together through the accepted pure recurrent
    close-batch transition before final evidence acceptance;
11. retain full nested price/time source evidence and deterministic final rows,
    self-fingerprint the complete artifact, and atomically fsync-persist it at
    `data/live/simulation/recurrent_time_aware_stock_close/current.json`;
12. expose/reuse one canonical typed decoder for the accepted price-CLOSE source; and
13. perform no provider/broker calls and grant no broker-fill, order, PAPER/LIVE,
    promotion or confluence authority.

Immediate continuation is a production-cycle facade update that admits this final
price/time CLOSE evidence as the recurrent CLOSE source while keeping the generic
CLOSE → RESERVE → ENTRY → MARK stage order unchanged. After that, proceed to the
target-workstation market-hours Webull sandbox and restart/resume acceptance proof.

The Strategy Evidence Register remains unchanged because this package advances product
simulation lifecycle evidence rather than strategy research evidence.

## Track A time-aware recurrent production-cycle extension — 2026-09-19

Track A freezes **atlas-simulation-recurrent-time-aware-production-cycle-v1** under
contract **c16ce1d4b9923d857673a92e6a4378a76699d6413ccf3ee8dbed9b138a894e84**.

Frozen semantics:

1. extend, but do not modify, accepted recurrent production-cycle v1
   (**c03e6e299076618a537e8ab2d7ebd575b33f22924f25fc1f0ba655f10e7412ca**);
2. inherit BEGIN, RESERVE, ENTRY, post-ENTRY plan refresh, MARK, COMPLETE and
   restart/restore behavior unchanged;
3. preserve generic recurrent mutation order CLOSE → RESERVE → ENTRY → MARK;
4. override only CLOSE to require the accepted time-aware final stock-CLOSE bundle
   (**7b3a9f25959002ea070eca4611a16ce57f73771430d7075f855cd924ca7cac45**);
5. require exact cycle identity and current recurrent-state binding on first CLOSE;
6. after account mutation, delegate exact CLOSE retry to the existing immutable
   stage-admission receipt so restart/retry cannot double-apply a close;
7. inherit restore through the base cycle's class-aware constructor so restored
   instances remain time-aware production-cycle instances;
8. leave STOP/TARGET/TIME precedence, clock evidence, time disposition and fill
   construction owned by their already accepted evidence packages;
9. leave base production v1 behavior frozen: it continues to reject the time-aware
   CLOSE contract rather than silently acquiring new semantics;
10. perform zero provider/broker reads or writes and grant no order, PAPER/LIVE,
    promotion or confluence authority.

Immediate continuation after acceptance is target-workstation operational proof rather
than another speculative backend layer: exercise real market-hours Webull sandbox L1
through the accepted production facade, interrupt/restart the process at lifecycle
boundaries, prove deterministic resume/no-double-application, and verify the browser/
control-plane reads the same authoritative recurrent state. PAPER authority remains
separately gated on that evidence.

The Strategy Evidence Register remains unchanged because this package composes already
accepted product evidence and changes no strategy research result.

## Track A isolated target-workstation recurrent acceptance — 2026-09-19

Track A freezes **atlas-recurrent-workstation-acceptance-v1** under contract
**5d450f115c03cfef389845ba594402f34a62ed7491f263dc7e33f8b5bb38af50**.

Frozen semantics:

1. run only against a dedicated isolated live root; the configured normal live root is
   forbidden;
2. use the accepted Webull sandbox L1 capture path for exactly three explicit provider
   reads and perform zero provider writes, broker reads/writes or order actions;
3. require operator-supplied initial simulation equity plus explicit entry and exit
   fees; no pretend starting balance or silent fee default;
4. label the acceptance decision as product fixture / NOT_STRATEGY_EVIDENCE;
5. freeze a one-regular-session-minute MINUTES horizon and fixed ±20% threshold before
   any exit observation; price-band breach fails acceptance instead of retuning;
6. create a real process boundary after durable ENTRY, then restore for MARK;
7. require production MARK to create/verify the accepted post-ENTRY exit-plan refresh,
   complete cycle one, persist the explicit clock book and expose dashboard status
   `AVAILABLE` from the same authoritative account/marked-state pair;
8. wait for the immutable deadline and capture a new current Webull quote;
9. require price NO_TRIGGER and accepted `TIME_EXPIRED` before final TIME resolution;
10. admit TIME through the accepted time-aware production facade at exact current bid
    with explicit exit fee evidence;
11. create another real process boundary, restore the same CLOSE cycle and resubmit the
    exact final bundle; require closed-trade count to remain exactly one;
12. require cycle-health lineage with zero invalid receipts/admissions and expected
    `OPEN_CYCLE` status after the intentionally paused second cycle CLOSE;
13. write a self-fingerprinted final acceptance receipt containing quote, decision,
    plan, clock, time-disposition, close, checkpoint, dashboard and health lineage;
14. grant no PAPER/LIVE, order, promotion or confluence authority.

The accepted operator command is:

`python scripts/run_recurrent_workstation_acceptance.py --ticker SPY --initial-equity 100000 --entry-fee 0 --exit-fee 0`

Run it during XNYS regular market hours with Webull sandbox credentials present. The
harness normally waits about one minute between MARK and the final quote capture.

A successful receipt closes the current simulation-runtime acceptance gate. Any later
PAPER enablement remains a separate explicit authority decision. The Strategy Evidence
Register remains unchanged.

## Track A / Track B bridge: recurrent successor historical outcome replay — 2026-09-19

ATLAS now stages **atlas-recurrent-successor-outcome-replay-v1-walk-forward-selector-long-only** as the first historical campaign bridge from accepted successor research artifacts into the current recurrent account lifecycle.

This package deliberately reuses evidence rather than recomputing strategy rules. It consumes only the accepted successor conditioning output and its hash-bound normalized DEVELOPMENT artifacts. Admission remains the already-frozen 504-session training / 1-session embargo / 63-session test walk-forward selector. For each selected test opportunity, the product-side move/return forecast is reconstructed only from that fold's prior training cell; the held-out opportunity's realized return is not used in its forecast, selection, sizing, or reservation.

Frozen v1 campaign mechanics:

1. DEVELOPMENT signal scope remains within `2016-01-04..2026-04-30`; consumed master and future-blind rows remain forbidden.
2. `research_eligible AND comparable` conditioning rows are the only candidate stream.
3. portfolio constraints preserve the accepted reference mechanics: 10% of current book equity per position, at most 10 active/reserved positions, at most 3 per economic family, and one active/reserved position per ticker;
4. v1 simulates **LONG stock only** because the accepted recurrent funding model is cash-only bullish stock. Selected SHORT opportunities are counted and reported but cannot be silently converted into longs or funded without the separately versioned short borrow/collateral model;
5. each admitted opportunity creates a genuine `SimulationDecisionRecord` from its fold's training-only distribution, then passes through the current recurrent RESERVE -> ENTRY -> CLOSE accounting transitions;
6. the accepted successor outcome is represented on a normalized $100 entry-price basis so percentage economics and the accepted cost convention are reproduced exactly without pretending to reconstruct historical share quantities;
7. daily rows use the frozen five-session / 10-bps primary outcome; intraday rows use their accepted entry/exit timestamps and 50-bps primary cost convention;
8. entry and exit costs are split exactly across the two recurrent fills, and every completed trade must reproduce the accepted primary net return or the campaign fails closed;
9. portfolio output includes decisions/rejections, closed trades, realized book-equity curve, strategy/family P&L attribution, finite-cash competition, peak active/reserved slots, and realized/book-equity drawdown;
10. this first mode is explicitly **OUTCOME_REPLAY_DIAGNOSTIC**. It does not yet reread historical bars to retest decision-bound STOP/TARGET/TIME exits and therefore is not the final strategy-tuning simulator;
11. source files/receipts are hash-verified before use; provider calls, broker reads/writes, order actions, PAPER, LIVE, promotion and confluence authority remain zero/false.

The operator entry point is:

`python scripts/run_recurrent_successor_outcome_replay.py --authorize-development-replay --initial-equity 100000 [--start YYYY-MM-DD] [--end YYYY-MM-DD] [--policy-id POLICY]`

A successful first workstation run will establish the current recurrent account as a historical portfolio replay surface. The next historical-simulation package is the stricter bar-level campaign that rereads accepted historical bars and lets decision-bound STOP/TARGET/TIME mechanics determine exits directly rather than replaying retained outcomes. The separate PR #161 current-Webull workstation acceptance still requires XNYS regular market hours and remains an operational-runtime gate, not a prerequisite for this historical replay.

## Track A / Track B bridge: first workstation recurrent portfolio result — 2026-09-19

The first real workstation campaign for
`atlas-recurrent-successor-outcome-replay-v1-walk-forward-selector-long-only`
completed over `2025-01-01..2025-12-31`.

Run fingerprint:
`2096fe4bc3babdd80c667a0548ab24a861a586bd08f880237744f11b23378166`.

Observed result:

- 4,685 selected comparable opportunities;
- 3,650 supported LONG / 1,035 reported-only SHORT;
- 439 admitted and 439 completed positions;
- $100,000.00 -> $101,647.15;
- +1.6472% total return;
- -20.9896% maximum realized/book-equity drawdown;
- peak 10 active/reserved slots;
- rejections: 2,429 max-per-family, 458 max-open-position, 262 insufficient-capital, 62 duplicate-active-ticker.

The portfolio gate therefore admitted only about 12.0% of supported LONG selections.
Family concentration/competition is the dominant observed bottleneck, not raw signal
scarcity. This is the first direct evidence that successor selection behavior changes
materially once strategies share finite capital and simultaneous-position constraints.

Do **not** tune the frozen v1 account constraints from this single post-result run.
The next historical-simulation package is a new bar-level campaign contract that:

1. preserves the same DEVELOPMENT-only / no-consumed-master authority;
2. retains exact walk-forward training/test chronology;
3. uses the current recurrent account as the sole cash/position/ledger truth;
4. obtains historical entry, mark and exit evidence from accepted PIT bars rather than
   replaying the retained terminal outcome;
5. applies separately frozen decision-bound STOP/TARGET/TIME policies;
6. resolves ambiguous same-bar/session stop/target collisions conservatively and
   explicitly rather than inferring intrabar order;
7. records mark-to-market equity in addition to realized/book-equity;
8. keeps strategy/family, symbol, regime, fold and decision-version attribution;
9. supports restart/resume and visible progress on workstation-scale runs; and
10. remains DEVELOPMENT_DIAGNOSTIC with no promotion/PAPER/LIVE authority.

Short-side portfolio simulation remains a later explicit funding/collateral package and
must not be faked inside the bar-level campaign.

## Static-exit regime closeout and Dynamic Exit V1 — 2026-09-20

The retrospective 2018–2024 annual regime map completed under run fingerprint
`60989a10985973bff48d3d2a82a633282b62e664f22f5c3fac4c35bfee380ede`.

Neither frozen static exit geometry generalized:

- 2% STOP / 5% TARGET was positive in 1/7 annual regimes, median annual return
  -11.00%, worst annual return -24.87%, worst marked-equity drawdown -25.32%;
- 3% STOP / 5% TARGET was positive in 1/7 annual regimes, median annual return
  -11.18%, worst annual return -27.74%, worst marked-equity drawdown -28.38%.

2019 was the only positive year for both geometries. Together with the failed
chronologically forward 2026 confirmation, this ends the static universal-exit
candidate path. No fixed exit policy is promoted.

Dynamic Exit V1 is the next bounded research gate. The initial action menu is frozen
to six geometries with target at least 1.5x stop: 1/2, 1/3, 1/5, 2/3, 2/5, and 3/5
percent, plus ABSTAIN. The five-session time exit remains fixed so V1 isolates the
effect of stop/target selection.

For every current opportunity, the selector may use only the preceding eight completed
walk-forward folds. It searches an interpretable context hierarchy built from policy,
market-volatility state, higher-timeframe trend, realized-volatility bucket, and
market-direction alignment. A context cell requires >=60 cases, >=30 sessions, and
>=20 instruments. Exit actions are ranked by a one-sided 95% lower-confidence bound
of equal-weight prior session mean net returns after the frozen 10-bps execution cost.
No positive robust action means ABSTAIN.

The first Dynamic Exit V1 package is intentionally a selector diagnostic, not an
account return. It records action assignments and their subsequently revealed trade
outcomes while proving the current trade's future path and current-fold outcomes do
not influence the choice. If coherent, the next package will bind those frozen
assignments into the recurrent account simulator with capital competition, risk caps,
mark-to-market drawdown, and compounding.

## 2026 forward confirmation failure and static-exit regime map — 2026-09-19

The frozen 2%/5% and 3%/5% candidates were evaluated unchanged over
`2026-01-01..2026-04-30` using run fingerprint
`bd8e1fd32d2c34e8699e6e243e851c936c475e0d5b16fc4f6047d5f02e40f210`.

Observed results:

- 2% STOP / 5% TARGET: -6.38% return, -9.88% marked-equity drawdown,
  282 completed positions;
- 3% STOP / 5% TARGET: -6.97% return, -10.42% marked-equity drawdown,
  236 completed positions.

The first chronologically later confirmation therefore rejected both static exit
geometries as general rules. No static candidate is promoted and no 2026-informed
parameter change is permitted.

The next diagnostic is a retrospective annual regime map across 2018–2024 with both
candidate geometries unchanged. The runner loads the accepted daily-case source once,
subsets by signal year, and parallelizes regime-policy jobs. Each year starts from the
same initial equity so cross-year return/drawdown behavior is directly comparable.

The regime map is not validation and cannot overturn the failed forward result. It is
the evidence package for Dynamic Exit V1. Dynamic Exit V1 should choose decision-bound
STOP/TARGET/TIME geometry from point-in-time information only, initially using a small
frozen action set and features such as volatility regime, ATR/realized volatility,
strategy family, prior favorable/adverse path probabilities, forecast uncertainty and
market regime. Continuous ATR-scaled geometry and in-trade adaptation remain later
versions after discrete dynamic selection is proven.

## 2025 daily exit sweep result and 2026 forward-confirmation gate — 2026-09-19

The preregistered 16-policy daily LONG sweep completed for 2025 under run fingerprint
`2726c3a644ac22ed3238adf5b03e978152eaa50a5d0e91fc937716309f0db9f4`.

The 3,520 usable daily LONG cases produced only two positive endpoint policies:

- 2% STOP / 5% TARGET: +1.45% return, -9.20% maximum marked-equity drawdown,
  649 completed positions;
- 3% STOP / 5% TARGET: +0.46% return, -13.11% maximum marked-equity drawdown,
  575 completed positions.

The remaining 14 policies were negative. The 1%-target family was particularly poor,
and no tested 2% or 3% target combination finished positive.

The result supports a bounded exit-policy hypothesis but not promotion. Because 2025
selected the candidate set, the next primary gate is the chronologically later
DEVELOPMENT interval `2026-01-01..2026-04-30`. Exactly two candidates are frozen
before that result is observed: 2%/5% and 3%/5%.

The forward-confirmation runner requires the exact completed 2025 sweep fingerprint
before opening the 2026 test. It retains the same recurrent account, compounding,
sizing, family/ticker caps, historical daily source, 10-bps cost assumption,
conservative collision/gap semantics and five-session TIME horizon.

After 2026 confirmation, those same candidates may be checked across earlier
DEVELOPMENT regimes for robustness. Earlier periods are explicitly backward
cross-regime checks, not temporally forward validation. Prospective SHADOW/PAPER
qualification remains a later gate.

## Recurrent daily exit-policy tuning campaign — preregistered 2026-09-19

The next simulation package is frozen as
`atlas-recurrent-successor-daily-exit-policy-sweep-v1`.

It holds selector, sizing, family caps, ticker exclusivity, cost assumptions and LONG
funding semantics fixed while comparing the 16 combinations formed by 1/2/3/5% STOP
x 1/2/3/5% TARGET. TIME remains the fifth entry-session close. Same-session collision
is worst-case STOP; adverse stop gaps fill at the worse open; favorable target gaps
receive no improvement beyond target.

Historical execution rereads only accepted hash-bound DEVELOPMENT daily bars for
selected instruments. Daily close marks feed the current recurrent marked-account
projection, so each policy reports both realized/book equity and daily marked-equity
drawdown. Current-fold outcomes cannot affect their own forecasts: return evidence is
training-only and threshold/timing evidence comes only from strictly prior selected
folds with minimum support 30.

The 2025 sweep is hypothesis generation only. No automatic winner or promotion is
permitted. Bounded candidates that improve return/drawdown/capital recycling must next
survive other DEVELOPMENT regimes with the same frozen policy before any prospective
SHADOW/PAPER qualification. Portfolio-cap tuning and short funding remain separate
versioned research/product packages.

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

