# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after the Phase31 source-quality target replay passed and the finite Form-4 scientific contract was frozen before any market-outcome read. Full historical Form-4 acquisition is next.**

Read `docs/roadmap.md` first, then this file, `docs/phase31_sec_insider_transaction_alpha.md`, `docs/phase31_form4_feasibility_incident.md`, `docs/phase31_form4_source_quality_repair.md`, and `docs/phase31_scientific_contract.md`.

## Authority state

- Accepted foundation: **through Phase30**.
- Phase26–30: all `ACCEPTED_NEGATIVE`; no modern alpha family has earned support.
- Phase30 PR #34 merge: `bf673ad82886e7172db0d54a33dd9612fa9ea29e`.
- Active branch: `phase-31-sec-insider-transaction-alpha`.
- Active gate: **Phase31 — SEC Form-4 Insider-Transaction Alpha**.
- Current Phase31 state: **SOURCE QUALITY PASS / SCIENTIFIC POLICY FROZEN / FULL-HISTORY ACQUISITION NEXT**.
- Phase32 remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains disabled. Automatic broker failover remains disabled.

Never weaken a chronology, identity, statistical, multiplicity, protected, or authority gate to obtain PASS. Zero finalists/trades is valid. Provider-native ticker strings/case and PIT identity remain authoritative.

## Protected holdout

Master protected outcome window:

`2026-05-12` through `2026-08-11`

Phases26–30 read zero protected returns. Phase31 feasibility, diagnostic, source-quality repair, and scientific-policy work have read **zero Phase31 market outcomes** and zero protected returns. The holdout remains outcome-unopened.

## Provider facts

Current Massive plan: **Stocks Starter**.

Phase31 source:

`MassiveRESTClient -> GET /stocks/filings/vX/form-4`

The endpoint is early-access/beta. Massive documents `filing_date` as SEC submission date and `transaction_date` as transaction date. ATLAS preserves those fields and provider-native ticker values directly.

## Original feasibility — permanently preserved

Target head:

`b59a64938eb84c0c1e7df3aaea390cc437326f94`

Feasibility fingerprint:

`edb2af8b5c0f0d9273aa8120cf878f11ccc1b8fbdce31dbbf6b5fe39df366bdc`

Result: **`FEASIBILITY_FAIL`**.

Sole failed check: `transaction_dates_do_not_postdate_filings`.

This failure is not rewritten.

## Chronology diagnostic — complete

Implementation head:

`80b9dc6d3541f850e3d004b1e880ae1c2d8aa7b7`

Target evidence:

- 36,854 dated transaction rows
- 33,510 transaction-before-filing
- 3,343 same-day
- 1 transaction-after-filing
- violating accession `0000950170-23-043337`, WISH
- filing `2023-08-17`, returned transaction `2023-09-15`, gap 29 days
- violation SHA256 `3fac83bf60206e4056d6d9b1fd285b79f7a6b366b7fb154aefd4daaea4abc044`
- provider/outcome/broker/order/PAPER/LIVE reads-writes all zero.

Root cause: **Massive beta source-association/data-quality defect**, not an ATLAS parser bug. The chronology invariant remains unchanged.

## Source-quality repair — TARGET PASS

Policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Implementation head:

`03dcd371e79554cc9e52a1bb4ed3b642a067ca4b`

Historical replay runner retained for provenance:

`scripts/run_phase31_form4_source_quality_repair.py`

Workflow `33143971229`: Ubuntu SUCCESS / Windows SUCCESS.

Target-machine result:

- `SOURCE_QUALITY_REPAIR_PASS`
- raw rows **45,921**
- violation seed rows **1**
- contaminated accessions **1**
- quarantined accession rows **6**
- authoritative rows **45,915**
- quarantine SHA `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target outcomes 0
- protected candidates 0
- protected returns 0
- broker/order/PAPER/LIVE activity 0
- scientific-policy freeze authorized True
- Phase32 entry satisfied False.

Accepted authoritative probe SHAs:

- research `0378adc4364b0b49812f95f700ff47eb52d55b2cf2c17bbecad77a48d6f8a4d5`
- mid-history `d8acaf8834ce166901388b437d5df1adf097d798fefb2e86449d92683acd7afd`
- development boundary `76c250af73a5694751eeb5974dbc55410c3ec63335d57632ab39d4a80d4edd8c`
- protected boundary `a3b1b23c00ffbc7372f779d48171fa0a7aac04a5b3bf028c7b2e9bf74d0bb6e0`.

## Frozen Phase31 scientific policy

Policy fingerprint:

`e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`

Exactly four hypotheses:

1. `open_market_purchase_long`
2. `clustered_open_market_purchase_long`
3. `open_market_sale_short`
4. `clustered_open_market_sale_short`.

No fifth hypothesis, alternate horizon, trade-value tail, role-specific rescue, text/footnote model, or runner-up substitution is authorized.

### Eligibility

Only source-quality-clean, pure original Form-4 `P` or `S` accessions may contribute. Eligible accessions require non-derivative securities, correct acquired/disposed direction, positive shares/price, timely `O` reporting, no affirmative 10b5-1 flag, no equity swap, Section-16 role, exactly one provider-native ticker, unique PIT identity, and a safe corporate-action-clean decision-to-exit interval.

Mixed grant/exercise/withholding/gift accessions are excluded. Multi-ticker filings are preserved raw but excluded from alpha authority. `transaction_value` is diagnostic only. A null 10b5-1 flag is unknown/not affirmatively flagged, not proof of no plan.

### Timing and event construction

Public availability:

`NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`

Entry: `DECISION_SESSION_OPEN`.

Exit: `CLOSE_20_XNYS_SESSIONS_AFTER_DECISION`.

One exact ticker × decision session × direction = one statistical event. Same ticker/session purchase and sale evidence is excluded as contradictory.

Cluster = current + previous 19 XNYS sessions with >=2 distinct owner CIKs and >=2 distinct qualifying accessions.

### Primary evaluation

Primary:

`direction * (stock open-to-t+20 close return - SPY open-to-t+20 close return) - cost`

Unhedged directional after-cost mean must also be positive.

Costs: 0/5/10/25/50 bps; primary 10; stress 25.

### Chronology

- source warmup `2021-07-16`
- research signals `2021-08-16..2026-04-13`
- development t+20 endpoint `2026-05-11`
- outer embargo `2026-04-14..2026-05-11`
- protected signal start `2026-05-12`
- last complete protected signal `2026-07-14`
- protected t+20 endpoint `2026-08-11`
- development split: chronological 75% selection, 20-session purge, remaining internal validation.

### Statistics

- folds 6 / 3 / 3
- bootstrap block 20 sessions, 2,000 reps, seed 310231
- confidence 95% / 90% / 80%
- selection minima 750 rows / 250 sessions / 250 tickers / >=5-of-6 positive folds
- internal minima 250 / 80 / 80 / >=2-of-3
- protected minima 75 / 24 / 24 / >=2-of-3
- global Holm-Bonferroni across exactly 4, alpha .05
- year robustness >=60%
- previous-session market/ticker-state robustness >=50%
- max session concentration 10%
- max ticker concentration 5%
- max one winner/finalist per direction
- winner = highest selection LCB then candidate ID
- no runner-up substitution
- protected returns finalist-only.

Complete contract: `docs/phase31_scientific_contract.md`.

## Exact next target

`scripts/run_phase31_form4_acquisition.py`

The full historical acquisition must:

- cover `2021-07-16..2026-08-11`
- use exactly 62 monthly immutable raw shards
- create separate authoritative/quarantine shards
- be resumable without rewriting raw evidence
- reproduce all four accepted probe windows exactly
- read zero market outcomes/protected returns
- perform no provider writes, broker activity, orders, PAPER, LIVE, or automation.

A beta-provider history mismatch against any frozen probe SHA is a source-drift failure, not permission to update the accepted evidence.

Acquisition PASS authorizes predictor-only event construction. It does not accept Phase31 or unlock Phase32.

## Remaining roadmap

- Phase31 — active Form-4 alpha gate
- Phase32 — Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype, blocked on supported alpha
- Phase33 — End-to-End Historical Replay & Stress Certification + Replay Dashboard
- Phase34 — Prospective SHADOW/PAPER Certification + Operator Web Beta
- Phase35 — Outcomes/Learning/Drift/Governance + Performance UI
- Phase36 — Production Web App/Operations/Deployment
- Phase37 — LIVE readiness certification; LIVE still disabled
- Phase38 — Controlled LIVE activation and evidence-based scaling.
