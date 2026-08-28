# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after the first real Phase31 Form-4 feasibility target returned `FEASIBILITY_FAIL` on a chronology invariant. Root-cause diagnosis is active; no Phase31 market outcomes have been read.**

Read `docs/roadmap.md` first. It remains the normative mission/anti-drift/remaining-phase authority. Then read `docs/phase31_sec_insider_transaction_alpha.md` and the open `docs/phase31_form4_feasibility_incident.md`. Phase30 closeout documents remain provenance. `docs/future_news_sentiment_and_option_fair_value.md` remains a downstream Phase32+ design requirement and does not alter the active alpha gate.

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
- Phase31 status: **ACTIVE REPAIR / FEASIBILITY NOT ACCEPTED**.
- Phase32 signal-to-trade remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Mission / anti-drift lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference/regulatory -> Parquet/DuckDB -> features -> discovery/regimes -> ML probability evidence -> deterministic alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

Never weaken a validator, threshold, chronology rule, multiplicity rule, protected boundary, identity rule, or authority rule to obtain PASS. Legitimate negative research is accepted. Provider-native ticker text/case and PIT identity are preserved. ML/AI do not independently create trade authority. PAPER does not imply LIVE.

## Provider/subscription facts relevant to Phase31

### Massive

The current Massive subscription is **Stocks Starter**.

For Phase31, the lead source is the Massive early-access/beta Form-4 endpoint:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

The first real target run successfully reached authenticated Form-4 retrieval and persisted provider evidence. Therefore the current incident is **not classified as an entitlement failure**. It is a returned-data chronology/semantics problem until proven otherwise.

Do **not** assume the current subscription includes Financials & Ratios Expansion, a Massive Options plan, paid Massive/Benzinga partner datasets, unavailable stock trades/quotes, or any other asset-class subscription not separately proven.

### Alpaca news

Earlier accepted provider work proved bounded authenticated historical Benzinga news access through the configured Alpaca paper credentials. That does not change the active Form-4 gate and does not prove real-time news WebSocket latency/entitlement.

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

Key evidence:

- 775,164 Massive historical news articles;
- 1,917,356 ticker links;
- 1,012,022 development predictor rows / 16,749 tickers;
- 23,183 protected predictor rows / 4,828 tickers;
- development join 3,057 rows / 1,736 tickers / 953 sessions;
- zero selection survivors, winners, finalists, or supported candidates;
- independent validation `PASS_NEGATIVE_SAMPLE_GATE_PROOF`;
- protected candidate rows read 0;
- protected return rows read 0;
- holdout consumed False.

The positive-looking reversal-LONG diagnostic had only 30 rows / 28 sessions and failed preregistered sample, Holm, and robustness requirements. It is not support and may not be chased.

## Protected-holdout state

Master protected outcome window:

`2026-05-12` through `2026-08-11`

Phases26–30 read **zero protected returns**. The holdout remains genuinely outcome-unopened. Phase31 feasibility has also read zero market outcomes; the current Form-4 incident does not consume the holdout.

## Active Phase31 — SEC Form-4 Insider-Transaction Alpha

### Plain-English purpose

Phase31 asks whether legally reported ownership decisions by corporate insiders contain robust future-return information after they become public, using a materially different regulatory/ownership-flow information mechanism from the price, cross-stock, relative-value, and metadata-news mechanisms rejected in Phases26–30.

No Phase31 alpha hypothesis library is frozen yet. No Phase31 market performance has been inspected.

### Conservative PIT rule

Until an authoritative exact historical SEC acceptance timestamp is proven before performance, a Form-4 filing may first influence an ATLAS signal on the **first XNYS trading session strictly after its `filing_date`**.

Frozen constant:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

This rule has not changed after the failed target.

### First real feasibility target — FAILED / NOT ACCEPTED

Target-machine run:

- branch: `phase-31-sec-insider-transaction-alpha`;
- exact head: `b59a64938eb84c0c1e7df3aaea390cc437326f94`;
- feasibility fingerprint: `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`;
- declared plan: Stocks Starter;
- endpoint: `/stocks/filings/vX/form-4`;
- result: **`FEASIBILITY_FAIL`**;
- failed check: **`transaction_dates_do_not_postdate_filings`**;
- target outcome rows read: 0;
- protected candidate rows read: 0;
- protected return rows read: 0;
- no alpha hypothesis/support/trading authority granted.

The failing invariant computes:

`lag_calendar_days = filing_date - transaction_date`

At least one persisted provider transaction row produced a negative lag, meaning the returned `transaction_date` was later than the returned `filing_date`.

The provider adapter maps those fields directly. The gate is still intact. Do not swap fields, clamp dates, ignore offending rows, or relax the check merely to obtain PASS.

### Current root-cause action

The failed target wrote immutable JSONL evidence for all four probe windows before the check failed. The next internal action is therefore **provider-free**:

`scripts/diagnose_phase31_form4_lag.py`

It must:

- read only those frozen local provider evidence files;
- verify each evidence SHA against the failed feasibility report;
- verify that the original target failed exactly the chronology check;
- classify violating rows by transaction code, security type, acquired/disposed, direct/indirect ownership, Rule 10b5-1, timeliness, role, date gap, accession, and ticker;
- print deterministic violating-row samples;
- read zero target/protected market outcomes;
- make zero provider calls;
- preserve broker/order/PAPER/LIVE authority at zero.

After those diagnostics, classify the root cause as parser/mapping bug, authoritatively legitimate Form-4 semantic case, provider-beta data defect, or unresolved ambiguity. Only then may a repair be designed. No performance result may influence the choice.

See `docs/phase31_form4_feasibility_incident.md` for the exact incident record.

### Phase31 authority boundary

Allowed now:

- local replay/diagnosis of already-persisted Form-4 provider evidence;
- bounded read-only provider calls only when a later explicitly frozen feasibility repair requires them;
- immutable provider evidence writes;
- metadata/field-completeness/semantics analysis;
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
- performance-driven exclusion, threshold, or hypothesis selection.

## Downstream design requirements already preserved

`docs/future_news_sentiment_and_option_fair_value.md` remains binding once signal-to-trade becomes reachable:

- news sentiment defaults to **Supporting Evidence** and can force thesis re-evaluation when materially contradictory;
- prospectively versioned first-receipt news is preferred for PIT-safe sentiment authority;
- live-news provider is configurable and selected by measured latency/reliability/coverage;
- Phase32 option selection must include an explicit Option Fair-Value Engine;
- BSM is a reference, not sole valuation authority;
- valuation must account for IV surface/skew/term structure, independent vol estimates, rates/dividends, executable prices/liquidity, Greeks, and American-style exercise where relevant.

## Remaining roadmap

`docs/roadmap.md` was reviewed after this incident and remains structurally correct; the chronology failure changes no phase numbering or authority condition.

- **Phase31:** SEC Form-4 Insider-Transaction Alpha — active feasibility repair/root-cause stage.
- **Phase32:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked until supported alpha exists.
- **Phase33:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase34:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase35:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase36:** Production Web App/Operations/Deployment.
- **Phase37:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase38:** Controlled LIVE Activation & Evidence-Based Scaling.
