# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after the Phase31 Form-4 chronology diagnostic completed and root cause was classified as a Massive early-access/beta source-association/data-quality defect. A generalized fail-closed source-quality repair is frozen; local frozen-evidence replay is the next target action. No Phase31 market outcomes have been read.**

Read `docs/roadmap.md` first. It remains the normative mission/anti-drift/remaining-phase authority. Then read `docs/phase31_sec_insider_transaction_alpha.md`, `docs/phase31_form4_feasibility_incident.md`, and `docs/phase31_form4_source_quality_repair.md`. Phase30 closeout documents remain provenance. `docs/future_news_sentiment_and_option_fair_value.md` remains a downstream Phase32+ design requirement and does not alter the active alpha gate.

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
- Phase31 status: **ACTIVE — SOURCE-QUALITY REPAIR FROZEN / TARGET REPLAY PENDING**.
- Original Phase31 feasibility result remains **`FEASIBILITY_FAIL`** historical evidence.
- Phase32 signal-to-trade remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains **DISABLED**. Automatic broker failover remains **DISABLED**.

## Mission / anti-drift lock

ATLAS exists to make evidence-driven stock/options trading decisions with the objective of growing account equity and producing profit over time after realistic costs while controlling drawdown, tail risk, concentration, execution risk, and risk of ruin.

`market/reference/regulatory -> Parquet/DuckDB -> features -> discovery/regimes -> ML probability evidence -> deterministic alpha evaluation -> promotion -> deep research/news -> stock/options selection -> geometry -> portfolio risk/sizing -> deterministic case -> independent AI audit -> alerts -> shadow/paper/live execution -> learning -> browser control plane -> deployment`

Never weaken a validator, scientific threshold, chronology rule, multiplicity rule, protected boundary, identity rule, or authority rule to obtain PASS. Legitimate negative research is accepted. Provider-native ticker text/case and PIT identity are preserved. ML/AI do not independently create trade authority. PAPER does not imply LIVE.

## Provider/subscription facts relevant to Phase31

### Massive

Current Massive subscription: **Stocks Starter**.

Phase31 lead source:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

The endpoint is currently early-access/beta. The first target proved authenticated historical retrieval and persisted provider evidence, so the incident was not an entitlement failure.

Massive's documented semantics relevant to the repair:

- `filing_date` = date submitted to the SEC;
- `transaction_date` = date of the transaction;
- `transaction_timeliness=O` = on time; `L` = late;
- Form 4 follows reportable insider transactions.

ATLAS's Phase31 adapter copies these provider rows directly; it does not swap or synthesize those dates.

Do **not** assume Financials & Ratios Expansion, a Massive Options plan, paid Massive/Benzinga partner data, or unavailable stock trade/quote entitlements.

## Accepted alpha evidence through Phase30

Phase11 authority:

- SUPPORTED: **0**
- MIXED: `momentum_long_v1`, `pullback_long_v1`, `trend_following_long_v1`
- UNSUPPORTED: `breakdown_short_v1`, `breakout_long_v1`, `momentum_short_v1`, `pullback_short_v1`, `trend_following_short_v1`

Modern research:

- Phase26 deterministic/composite self-feature: 21,483 development observations; zero support — `ACCEPTED_NEGATIVE`.
- Phase27 cross-sectional learned ranking: 18,111 development rows; zero support — `ACCEPTED_NEGATIVE`.
- Phase28 cross-stock lead-lag/residual network: 14,466 development rows; zero support — `ACCEPTED_NEGATIVE`.
- Phase29 PCA/distance relative value: 14,523 development rows; zero support — `ACCEPTED_NEGATIVE`.
- Phase30 public-news metadata shock: 3,057 joined development rows; zero survivors/winners/finalists/support; independent negative reconstruction PASS — `ACCEPTED_NEGATIVE`.

Failed families may not be retuned after observing results.

## Protected-holdout state

Master protected outcome window:

`2026-05-12` through `2026-08-11`

Phases26–30 read **zero protected returns**. Phase31 feasibility, diagnostic, and the frozen source-quality repair have read **zero market outcomes**. The holdout remains outcome-unopened.

## Active Phase31 — SEC Form-4 Insider-Transaction Alpha

### Purpose

Phase31 asks whether legally reported insider ownership decisions contain robust future-return information after those filings become public. This is a materially different information mechanism from the price/self-feature, cross-sectional, cross-stock, relative-value, and news-arrival mechanisms rejected in Phases26–30.

No Phase31 alpha hypothesis library is frozen yet. No Phase31 market performance has been inspected.

### Conservative PIT rule

Until authoritative exact historical SEC acceptance timestamps are proven before performance, a filing may first influence ATLAS on the **first XNYS trading session strictly after its `filing_date`**.

Frozen constant:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

This rule has not changed.

### Original feasibility target — FAILED / permanently preserved

- target head: `b59a64938eb84c0c1e7df3aaea390cc437326f94`
- feasibility fingerprint: `edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`
- endpoint: `/stocks/filings/vX/form-4`
- result: **`FEASIBILITY_FAIL`**
- sole failed check: **`transaction_dates_do_not_postdate_filings`**
- target outcome rows read: 0
- protected candidate rows read: 0
- protected return rows read: 0
- no alpha/trading authority granted.

The original check computes:

`lag_calendar_days = filing_date - transaction_date`

The original failure is not rewritten into PASS.

### Frozen-evidence diagnostic — COMPLETE

Diagnostic implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

Target-machine diagnostic result:

- status: `DIAGNOSTIC_COMPLETE`
- pass: True
- dated transaction rows: **36,854**
- transaction before filing: **33,510**
- same day: **3,343**
- transaction after filing: **1**
- violating rows/accessions/issuers/owners: **1 / 1 / 1 / 1**
- violating window: `mid_history`
- accession: `0000950170-23-043337`
- ticker: `WISH`
- filing date: `2023-08-17`
- returned transaction date: `2023-09-15`
- impossible gap: **29 calendar days**
- code: `M`
- security type: derivative
- security title: `Restricted Stock Unit`
- acquired/disposed: `A`
- direct/indirect: `D`
- 10b5-1: false
- transaction timeliness: `O`
- officer title: Chief Product Officer
- shares: 496
- violation artifact SHA256: `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`
- provider calls: 0
- target/protected outcome reads: 0
- broker/order/PAPER/LIVE activity: 0.

### Root-cause classification

The chronology rule was correct.

Massive documents `transaction_date` as the actual transaction date, `filing_date` as SEC submission date, and `transaction_timeliness=O` as on time. A September 15 transaction cannot be an on-time transaction row belonging to an August 17 Form-4 filing under those documented semantics.

Because the ATLAS adapter preserves the raw Massive fields directly, this is **not an ATLAS date parser/mapping bug**. The endpoint is early-access/beta, and the impossible row is classified as a **Massive beta source-association/data-quality defect**.

ATLAS does not infer a corrected accession or silently rewrite the row.

### Frozen source-quality repair

Repair policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Source-quality policy fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Generic rule:

1. keep all raw provider rows immutable;
2. detect any transaction row where `transaction_date > filing_date`;
3. quarantine the **entire accession_number** containing a violating row;
4. never clamp/swap dates or infer a replacement filing;
5. authoritative corpus must contain zero chronology-invalid transaction rows;
6. missing accession on a violating row fails closed;
7. provider-native ticker case remains unchanged;
8. the classifier cannot use ticker, transaction code, security type, role, or performance to decide quarantine.

This is **not** an "allow one exception" tolerance. It is a stronger source-authority boundary for a beta feed.

The repair implementation is:

`scripts/run_phase31_form4_source_quality_repair.py`

It is provider-free and must replay only the exact failed feasibility + diagnostic evidence. It writes separate derived authoritative and quarantine artifacts and never overwrites the raw provider files.

A repair PASS authorizes only the **scientific-policy freeze** that must occur before any Phase31 return read. It does not accept Phase31, grant alpha support, consume protected outcomes, unlock Phase32, or enable PAPER/LIVE.

See `docs/phase31_form4_source_quality_repair.md`.

## Exact next target action

After pulling the repair head, run:

`\.\.venv\Scripts\python.exe scripts\run_phase31_form4_source_quality_repair.py`

Expected high-level landmarks:

- `Phase 31 Form-4 source-quality repair: PASS`
- original raw rows preserved
- chronology violation seed population reproduced
- >=1 contaminated accession quarantined
- authoritative chronology violations = 0
- target/protected outcome rows = 0
- provider/broker/order/PAPER/LIVE activity = 0
- `Scientific-policy freeze authorized: True`
- `Alpha support granted: False`
- `Phase32 entry satisfied: False`
- `Pass: True`

If it fails, diagnose the repair implementation/evidence lineage. Do not weaken the chronology or quarantine rules.

## Phase31 current authority

Allowed:

- replay/diagnosis of persisted Form-4 evidence;
- source-quality quarantine/reconciliation from frozen evidence;
- immutable/derived evidence writes;
- metadata/semantics/field-completeness analysis;
- tests/validators/documentation.

Forbidden:

- development/target future-return reads until scientific contract freeze;
- protected candidate/return reads;
- performance-driven exclusions or hypothesis choices;
- broker reads/writes;
- order writes;
- PAPER submissions;
- LIVE writes;
- automatic broker failover;
- frontend trading authority.

## Remaining roadmap

`docs/roadmap.md` was reviewed after the chronology incident and remains structurally correct.

- **Phase31:** SEC Form-4 Insider-Transaction Alpha — active source-quality repair, then scientific freeze/evaluation.
- **Phase32:** Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype — blocked until supported alpha exists.
- **Phase33:** End-to-End Historical Replay & Stress Certification + Replay Dashboard.
- **Phase34:** Prospective SHADOW/PAPER Certification + Operator Web Beta.
- **Phase35:** Outcomes/Learning/Drift/Governance + Performance UI.
- **Phase36:** Production Web App/Operations/Deployment.
- **Phase37:** LIVE Readiness/Deployment Hardening/Reconciliation/Failure Certification — LIVE still disabled.
- **Phase38:** Controlled LIVE Activation & Evidence-Based Scaling.

## Downstream requirements already preserved

`docs/future_news_sentiment_and_option_fair_value.md` remains binding once signal-to-trade becomes reachable:

- news sentiment is supportive evidence by default and material contradiction can force thesis re-evaluation;
- prospectively versioned first-receipt news is preferred for PIT-safe sentiment authority;
- Phase32 option selection must include an explicit configurable fair-value engine;
- BSM is a reference, not sole valuation authority;
- valuation must incorporate IV surface/skew/term structure, independent volatility evidence, rates/dividends, executable prices/liquidity, Greeks, and American-style exercise where relevant.
