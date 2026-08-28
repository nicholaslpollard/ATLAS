# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-28 after Phase31 predictor-only Form-4 event construction passed with zero market-outcome reads. Development-only performance evaluation is the active internal step; protected predictor rows and protected returns remain unopened.**

Read `docs/roadmap.md` first, then this file, `docs/phase31_sec_insider_transaction_alpha.md`, `docs/phase31_form4_feasibility_incident.md`, `docs/phase31_form4_source_quality_repair.md`, `docs/phase31_full_historical_acquisition.md`, `docs/phase31_predictor_evidence.md`, and `docs/phase31_scientific_contract.md`.

## Authority state

- Accepted foundation: **through Phase30**.
- Phase26–30: all `ACCEPTED_NEGATIVE`; no modern alpha family has earned support.
- Phase30 PR #34 merge: `bf673ad82886e7172db0d54a33dd9612fa9ea29e`.
- Active branch: `phase-31-sec-insider-transaction-alpha`.
- Active gate: **Phase31 — SEC Form-4 Insider-Transaction Alpha**.
- Current Phase31 state: **SOURCE QUALITY PASS / SCIENTIFIC POLICY FROZEN / FULL-HISTORY ACQUISITION PASS / PREDICTOR-ONLY PASS / DEVELOPMENT-ONLY PERFORMANCE NEXT**.
- Phase32 remains blocked until >=1 alpha architecture earns accepted historical analytical `SUPPORTED` authority.
- LIVE remains disabled. Automatic broker failover remains disabled.

Never weaken a chronology, identity, statistical, multiplicity, protected, or authority gate to obtain PASS. Zero finalists/trades is valid. Provider-native ticker strings/case and PIT identity remain authoritative.

## Protected holdout

Master protected outcome window:

`2026-05-12` through `2026-08-11`

Phases26–30 read zero protected returns. Phase31 feasibility, diagnostics, source-quality work, policy freeze, acquisition, and predictor construction have read **zero protected returns**. Predictor construction also read zero development market outcomes.

The protected predictor artifact is metadata only and is frozen by SHA. The development-performance stage may verify that SHA but may not parse protected predictor rows or read protected stock/SPY returns. Protected returns remain finalist-only after an independent blindness/lineage audit. Any nonempty protected Phase31 return read consumes the master holdout for later alpha selection.

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

## Source-quality target repair — preserved PASS

Historical target result label:

`SOURCE_QUALITY_REPAIR_PASS`

Policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Implementation head:

`03dcd371e79554cc9e52a1bb4ed3b642a067ca4b`

Historical replay runner retained for provenance:

`scripts/run_phase31_form4_source_quality_repair.py`

Target-machine result:

- raw rows **45,921**
- chronology seed rows **1**
- contaminated accessions **1**
- quarantined accession rows **6**
- authoritative rows **45,915**
- quarantine SHA `586df9eb91fb8a9a949a0dc44e0765f7c4b7db54c2b383037012d0fb17aaf1eb`
- target/protected outcomes 0.

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

Eligibility is source-quality-clean pure original Form-4 `P` or `S`, non-derivative, correct acquired/disposed direction, positive shares/price, timely `O`, no affirmative 10b5-1 flag, no equity swap, Section-16 role, exactly one provider-native ticker, unique PIT identity, and a safe corporate-action-clean decision-to-exit path. `transaction_value` is diagnostic only.

Public availability: `NEXT_XNYS_SESSION_STRICTLY_AFTER_FILING_DATE`.

Entry: `DECISION_SESSION_OPEN`.

Exit: `CLOSE_20_XNYS_SESSIONS_AFTER_DECISION`.

Event unit: one exact ticker × decision session × direction. Same ticker/session purchase and sale evidence is excluded as contradictory.

Cluster: current + previous 19 XNYS sessions with >=2 distinct owner CIKs and >=2 distinct qualifying accessions.

Primary evaluation:

`direction * (stock open-to-t+20 close return - SPY open-to-t+20 close return) - cost`

Unhedged directional after-cost mean must also be positive. Costs: 0/5/10/25/50 bps; primary 10; stress 25.

Selection/internal rules remain frozen: chronological first 75% of eligible development sessions, 20-XNYS-session purge, remaining internal validation; 6/3 folds; 20-session block bootstrap; global four-hypothesis Holm at 0.05; previous-session accepted market/ticker regimes for robustness; one winner/finalist maximum per direction; no runner-up substitution.

## Full historical Form-4 acquisition — PASS

Accepted target-machine run: 2026-08-28.

Accepted implementation head:

`069cca8a76446cc33b5fcf4931612e56a315f5b8`

Accepted acquisition runner retained for provenance:

`scripts/run_phase31_form4_acquisition.py`

Evidence:

- scope `2021-07-16..2026-08-11`
- month shards **62**
- fresh provider shards **20**
- reused SHA-bound raw shards **42**
- successful provider pages **105**
- raw rows **2,993,648**
- authoritative rows **2,992,608**
- quarantined rows **1,040**
- contaminated accessions **187**
- chronology violation seed rows **233**
- missing `transaction_code` seed rows **15**
- target outcome rows read **0**
- protected candidate rows read **0**
- protected return rows read **0**
- provider/broker/order/PAPER/LIVE/automation writes **0**.

Historical admissibility generically quarantines an entire accession if any transaction row has impossible chronology or lacks required transaction classification. Raw evidence remains unchanged; no field is imputed. The original target source-quality fingerprint remains unchanged.

Probe replay:

- research boundary raw/authoritative `13,645 / 13,645`, exact
- mid-history `12,066 / 12,060`, 6 quarantined, exact
- development boundary `13,884 / 13,884`, exact
- protected boundary `6,326 / 6,326`, exact.

Complete record: `docs/phase31_full_historical_acquisition.md`.

## Predictor-only Form-4 event construction — PASS

Accepted target-machine run: 2026-08-28.

Accepted predictor implementation head:

`dbde716b79ae882bcfec412e1a13e1bb3c274f6a`

Runner:

`scripts/run_phase31_form4_predictors.py`

Evidence:

- authoritative rows scanned **2,992,608**
- qualified accessions before session/identity **103,773**
- resolved noncontradictory events **5,870**
- development predictor rows **5,400**
- protected predictor rows **343**
- candidate membership:
  - `open_market_purchase_long` **2,482**
  - `clustered_open_market_purchase_long` **1,009**
  - `open_market_sale_short` **3,261**
  - `clustered_open_market_sale_short` **1,724**
- authoritative lineage SHA `a9a385828b436fde7bf2297d1f8b987c4899eaff7500d79fd0b6c4abf6de7918`
- PIT identity interval SHA `beabae4416f8444a5a062d3c3d49cdab46dec7919a545850ac0808ed94cfe3de`
- development predictor SHA `a82ff3114febc0c6f7c13d5f045549b714edbf0fd66157ef93853be9ae90c49f`
- protected predictor SHA `d3bcd2696463ec1e384919007a36570475f8cb0bf1e393f109f0accd24224e27`
- target outcome rows read **0**
- protected return rows read **0**
- provider/broker/order/PAPER/LIVE/automation writes **0**.

Complete frozen record: `docs/phase31_predictor_evidence.md`.

This PASS freezes event/candidate membership before performance. Broad and clustered hypotheses deliberately overlap. Predictor exclusions are deterministic source/timing/identity rules and cannot be altered after returns merely to rescue a result.

## Exact next target — development-only performance evaluation

Runner:

`scripts/run_phase31_development.py`

This is the first Phase31 step authorized to read **development** market outcomes. It must:

- bind the exact frozen development and protected predictor SHAs before outcomes;
- parse only the 5,400 development predictor rows; the protected predictor file is hash-bound only;
- join stock `OPEN` at the exact decision session to stock `CLOSE` at the exact frozen t+20 exit;
- join SPY over the same exact open-to-t+20-close timestamps;
- use accepted Phase26 corporate-action evidence read-only to censor focal-stock split crossings rather than fabricating an adjusted path;
- reconstruct accepted market and ticker regime state from the **previous XNYS session** only;
- derive the chronological 75% selection region from the frozen XNYS calendar, then apply the exact 20-session purge, then internal validation;
- evaluate exactly the four frozen hypotheses, including sample, profitability, stress, unhedged, fold, year/regime, concentration, bootstrap-LCB, and global Holm requirements;
- select at most one winner per direction by highest selection LCB then candidate ID;
- perform internal validation only on those frozen winners, with **no runner-up substitution**;
- freeze zero, one, or two finalists;
- read **zero protected candidate rows and zero protected returns**;
- perform zero provider/broker/order/PAPER/LIVE/automation activity.

If there are zero finalists, the next action is an independent negative closeout and the master holdout remains unconsumed. If there are finalists, the next action is an independent blindness/lineage audit and immutable finalist-only protected-return plan; protected returns are still not opened by the development runner itself.

A development runner `Pass: True` proves study integrity. It does not by itself mean Phase31 found alpha; the finalist list and frozen gates determine the scientific result.

## Remaining roadmap

- Phase31 — active Form-4 alpha gate
- Phase32 — Signal-to-Trade Construction & Portfolio Optimization + Web Contracts/Prototype, blocked on supported alpha
- Phase33 — End-to-End Historical Replay & Stress Certification + Replay Dashboard
- Phase34 — Prospective SHADOW/PAPER Certification + Operator Web Beta
- Phase35 — Outcomes/Learning/Drift/Governance + Performance UI
- Phase36 — Production Web App/Operations/Deployment
- Phase37 — LIVE readiness certification; LIVE still disabled
- Phase38 — Controlled LIVE activation and evidence-based scaling.
