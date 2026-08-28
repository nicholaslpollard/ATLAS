# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after Phase30 merged `ACCEPTED_NEGATIVE`, the post-merge suite passed on Ubuntu/Windows, and Phase31 was rebaselined to SEC Form-4 insider-transaction alpha.**

Read `docs/roadmap.md` first. It is the normative mission/anti-drift/remaining-phase authority. Then read the active `docs/phase31_sec_insider_transaction_alpha.md`. Phase30's frozen scientific and closeout documents remain provenance. `docs/future_news_sentiment_and_option_fair_value.md` remains a downstream Phase32+ design requirement and does not alter the active alpha gate.

## Repository / authority state

- Accepted foundation: **through Phase30**.
- Phase26 PR #30: `ACCEPTED_NEGATIVE`.
- Phase27 PR #31: `ACCEPTED_NEGATIVE`.
- Phase28 PR #32: `ACCEPTED_NEGATIVE`.
- Phase29 PR #33 merge `87c9450e1b21606b83489f16ff326235ae92eb2b`: `ACCEPTED_NEGATIVE`.
- Phase30 PR #34 merge `bf673ad82886e7172db0d54a33dd9612fa9ea29e`: `ACCEPTED_NEGATIVE`.
- Phase30 post-merge workflow `33141442154`: Ubuntu SUCCESS / Windows SUCCESS.
- Active branch: `phase-31-sec-insider-transaction-alpha`.
- Active gate: **Phase31 — SEC Form-4 Insider-Transaction Alpha**.
- Phase32 signal-to-trade remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Mission / anti-drift lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference/regulatory -> Parquet/DuckDB -> features -> discovery/regimes -> ML probability evidence -> deterministic alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

Never weaken a validator, threshold, chronology rule, multiplicity rule, protected boundary, identity rule, or authority rule to obtain PASS. Legitimate negative research is accepted. Provider-native ticker text/case and PIT identity are preserved. ML/AI do not independently create trade authority. PAPER does not imply LIVE.

## Provider/subscription facts relevant to the active gate

### Massive

The current Massive subscription is **Stocks Starter**.

Current official plan documentation describes Stocks Starter as including all US stock tickers, five years of historical market data, 15-minute-delayed market data, reference data, corporate actions, technical indicators, minute/second aggregates, flat files, WebSockets, and snapshot access.

For the active Phase31 source specifically, Massive currently documents `GET /stocks/filings/vX/form-4` as:

- included in **all Stocks plans**, including Stocks Starter;
- updated daily;
- early-access/beta, so schema/plan movement is possible and must trigger revalidation;
- structured around SEC filing/accession/insider transaction data.

Do **not** assume the current subscription includes:

- Financials & Ratios Expansion;
- Massive Options Starter/Developer/Advanced;
- paid Massive/Benzinga partner datasets;
- stock trades/quotes unavailable to Stocks Starter;
- any other asset-class subscription not separately proven.

### Alpaca news

A bounded authenticated probe using the configured paper credentials proved historical Benzinga news access:

- HTTP 200;
- full article content available;
- observed `X-Ratelimit-Limit: 200` requests/minute.

This proves historical REST news access only; it does not prove Alpaca real-time news WebSocket entitlement or latency. Future live-news provider choice remains prospective and configurable between Massive Standard, Alpaca/Benzinga, and optional separately entitled Massive/Benzinga real-time partner data.

## Accepted alpha evidence through Phase30

Phase11 authority remains:

- SUPPORTED: **0**;
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`;
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`.

Modern research:

- Phase26 self-feature deterministic/composite: 21,483 development observations; zero support — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional learned ranking: 18,111 development rows; zero support — `ACCEPTED_NEGATIVE`.
- Phase28 cross-stock lead-lag/residual network: 14,466 development rows; zero support — `ACCEPTED_NEGATIVE`.
- Phase29 PCA/distance relative value: 14,523 development rows; zero support — `ACCEPTED_NEGATIVE`.
- Phase30 public-news metadata shock: 3,057 joined development rows; zero survivors/winners/finalists/support; independent negative reconstruction PASS — `ACCEPTED_NEGATIVE`.

Failed families may not be retuned after observing their results.

## Phase30 final evidence

Frozen policy fingerprint:

`341f3a5a97281f7878ab0c55f8ab5a33c9910abc47b69a0b5fef8e94771ce4f8`

Key target evidence:

- 775,164 Massive historical news articles;
- 1,917,356 ticker links;
- 1,012,022 development predictor rows / 16,749 tickers;
- 23,183 protected predictor rows / 4,828 tickers;
- development join 3,057 rows / 1,736 tickers / 953 sessions;
- zero selection survivors;
- zero winners;
- zero finalists;
- zero supported candidates;
- independent validation `PASS_NEGATIVE_SAMPLE_GATE_PROOF`;
- protected candidate rows read 0;
- protected return rows read 0;
- holdout consumed False.

The positive-looking reversal-LONG diagnostic had only 30 rows / 28 sessions and failed the preregistered minimum sample, Holm, and robustness requirements. It is not support and may not be chased.

## Protected-holdout state

Master protected outcome window:

`2026-05-12` through `2026-08-11`

Phases26–30 read **zero protected returns**. Phase30 produced a protected predictor artifact with no protected market outcomes. The holdout remains genuinely unopened and may be reused only under a materially different, pre-frozen future alpha architecture.

## Active Phase31 — SEC Form-4 Insider-Transaction Alpha

### Plain-English purpose

Instead of asking price patterns or news-arrival counts to predict themselves, Phase31 asks whether legally reported ownership decisions by corporate insiders contain future-return information after the trades become public through SEC Form 4 filings.

This is a genuinely different information mechanism. It uses insiders' disclosed capital-allocation behavior and ownership changes rather than another transformation of price, cross-stock relationships, relative value, or news frequency.

### Current stage: feasibility/provenance only

No Phase31 performance has been inspected and no Phase31 hypothesis library is yet frozen.

The initial feasibility step must prove:

- the actual Stocks Starter credential can read Form 4;
- historical coverage exists around the required ATLAS research/protected boundaries;
- pagination is deterministic;
- accession number, filing date, issuer CIK, owner CIK, ticker linkage, record type, transaction code, shares/price/value, insider role, security type, ownership, 10b5-1 flag, and timeliness coverage can be measured;
- purchase (`P`) and sale (`S`) transaction populations are large enough to design a finite study;
- immutable raw evidence can be replayed;
- zero market outcomes are read.

### Conservative PIT rule

Massive Form 4 currently exposes `filing_date` as a date, not an exact acceptance timestamp. Therefore, until exact SEC acceptance timestamps are independently proven **before performance**, a Form 4 filing may first influence an ATLAS signal on the **next XNYS trading session strictly after its filing date**.

This may sacrifice some reaction speed, but it prevents hidden same-day timing leakage. Exact SEC timing can only replace this rule if a separate non-performance feasibility step proves authoritative, reproducible acceptance timestamps before any Phase31 outcome read.

### Why Form 4 is the lead regulatory mechanism

Research literature has repeatedly found corporate-insider purchases to be more informative than insider sales and to contain predictive information beyond simple contrarian behavior. This motivates testing only; it does not grant ATLAS support.

Form 4 is preferable to short interest as the first regulatory gate because short-interest `settlement_date` is not the same as the date FINRA released the data to the public. Phase31 will not create a lookahead bug by treating settlement date as publication date.

### Phase31 authority boundary

Allowed now:

- bounded read-only Massive Form-4 queries;
- immutable local/provider evidence writes;
- metadata/field-completeness analysis;
- tests/validators/documentation.

Forbidden now:

- development/target future-return reads;
- protected candidate/return reads;
- broker reads or writes;
- order writes;
- PAPER submissions;
- LIVE writes;
- automatic broker failover;
- frontend trading authority;
- performance-driven threshold/hypothesis selection.

## Downstream design requirements already preserved

`docs/future_news_sentiment_and_option_fair_value.md` remains binding once signal-to-trade becomes reachable:

- news sentiment defaults to **Supporting Evidence** and can force thesis re-evaluation when materially contradictory;
- prospectively versioned first-receipt news is preferred for PIT-safe sentiment authority;
- live-news provider is configurable and selected by measured latency/reliability/coverage rather than brand preference;
- Phase32 option selection must include an explicit Option Fair-Value Engine;
- BSM is a reference, not sole valuation authority;
- valuation must account for IV surface/skew/term structure, independent vol estimates, rates/dividends, executable prices/liquidity, Greeks, and American-style exercise where relevant.

## Remaining roadmap

- **Phase31:** SEC Form-4 Insider-Transaction Alpha — active feasibility/provenance stage.
- **Phase32:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked until supported alpha exists.
- **Phase33:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase34:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase35:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase36:** Production Web App/Operations/Deployment.
- **Phase37:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase38:** Controlled LIVE Activation & Evidence-Based Scaling.
