# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-29 (America/New_York). Phase32 remains closed and merged `ACCEPTED_NEGATIVE`; protected stock/SPY returns remain unread and the holdout remains unconsumed. Historical supported alpha remains 0 and Phase33 remains blocked. The materially different SEC XBRL fundamental-quality/accrual mechanism has now passed its source-only feasibility gate on target-machine evidence and has advanced to a frozen source-only PIT filing/acceptance-time/restatement/identity audit.**

Read `docs/roadmap.md`, this file, `docs/alpha_gate_sec_xbrl_fundamental_quality.md`, `docs/alpha_gate_sec_xbrl_pit_audit.md`, `docs/phase32_closeout.md`, retained Phase32 source/scientific records, `docs/phase_flow.md`, and accepted code/CI evidence before continuing.

## Authority state

- Accepted foundation: through **Phase32**, merged into `main`.
- Phase26–32: all scientifically valid `ACCEPTED_NEGATIVE`.
- Accepted historical modern alpha support: **0**.
- Current Massive subscription: **Stocks Starter**; no broader entitlement is assumed.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Retained Phase32 research/closeout branch: `phase-32-sec-8k-material-event-alpha`.
- Phase32 PR: **#37**.
- Phase32 merge: `69f8aa81289934b71f2652482c747391917c15a3`.
- Phase32 final disposition: **`ACCEPTED_NEGATIVE`**.
- Accepted XBRL feasibility branch/head: `alpha-gate-sec-xbrl-fundamental-quality-feasibility` at `5a8c15f95417390d0d64ff240977adfb38a20c45`.
- Current research branch: `alpha-gate-sec-xbrl-fundamental-quality-pit-audit`.
- Current research authority: **source-only SEC XBRL PIT chronology/restatement/identity audit; no alpha hypotheses frozen and no market outcomes authorized**.
- Phase33 signal-to-trade entry condition: **not satisfied / blocked**.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory. The failed Phase32 50-row protected source gate may not be weakened, and the Phase32 family may not be retuned after results.

## Phase32 final evidence

Frozen scientific policy fingerprint:

`4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`

Exactly five hypotheses remained frozen throughout Phase32: `equity_issuance_short`, `share_repurchase_long`, `financial_integrity_adverse_short`, `listing_distress_short`, and `solvency_distress_short`.

Retained core feasibility contract:

`phase32-feasibility-v2-sec-submissions-8k-metadata-no-market-outcomes`

Authoritative source roles remained:

- Massive `/stocks/filings/vX/index` for historical original-8-K discovery/ticker metadata;
- official SEC `data.sec.gov/submissions` for authoritative SEC submissions metadata, acceptance time, accession/CIK/form/date/item reconciliation.

Accepted source/predictor fingerprints:

- core V2: `978353878cfa10c98450a6e0abab2a6d2ff00e039f7c6b87616014bd5690a9f4`;
- semantic V2: `eb30f5094bfbe0bd360231a6d220b3ae19e23d28fc0db9f70074dddfcdcf8566`;
- independent source/predictor acceptance: `531d91c04a0698fb005c9a0813040a82ab0a6ce29164b3dc8ddb67f4943bebde`.

Accepted full-history acquisition retained 36,309 filing entities, 19,792 eligible predictors, 18,819 development predictors, 973 protected-predictor-only rows, and zero market outcomes during acquisition.

Development-only performance evaluation was ACCEPTED PASS. All five frozen candidates survived selection plus Holm-5. The one-per-direction winners were `share_repurchase_long` and `solvency_distress_short`; internal validation rejected the LONG winner and left exactly one development finalist, `solvency_distress_short`.

The independent finalist blindness / lineage audit independently reproduced the accepted development path and exact finalist before using source-only protected predictor metadata.

Accepted finalist-audit fingerprint:

`c047dd1800877ed1d268b2d8e4c4fc1bfe158fcf715caedc275405f1bf01853e`

Accepted protected-plan fingerprint:

`2f44f2d87578a0b0a0cee6a6f5c855340056222ce52d68835b931ce5f114a344`

Accepted protected-plan rows SHA-256:

`b9591ac49dab3f6f7ff01ab4331ef114c68a436e8475456e099058bce847f703`

Frozen protected finalist population:

- event rows: **46**;
- signal sessions: **33**;
- unique instruments: **40**.

Frozen source-only minimums were **50 / 20 / 20**. Only the event-row gate failed (`46 < 50`). Audit status was `AUDIT_PASS_PROTECTED_SAMPLE_GATE_IMPOSSIBLE`.

**Protected stock/SPY returns remain unread.** Protected return rows read = **0**. Protected holdout consumed = **false**. No protected-performance evaluator is authorized for the Phase32 family.

The target-machine negative-closeout runner passed on exact head `6fbf9726088629b574480ce10dc49c60a36c153b`. Dedicated Phase32 and full ATLAS regressions then passed on Ubuntu and Windows, after which PR #37 merged at `69f8aa81289934b71f2652482c747391917c15a3`.

## Scientific interpretation of Phase32

Phase32 produced genuine development evidence, but not admissible historical support. A candidate that cannot satisfy the preregistered protected sample-size gate cannot become `SUPPORTED` by looking at protected returns. The correct result is therefore `ACCEPTED_NEGATIVE`, not a threshold change or runner-up substitution.

Historical supported alpha remains **0**. Phase33 Signal-to-Trade Construction cannot start because its positive entry condition is not met.

## SEC XBRL mechanism — accepted feasibility

The new mechanism changes the economic/information source rather than retuning Phase32. It examines standardized point-in-time quarterly fundamentals from SEC 10-Q/10-K XBRL facts, with the intended mechanism family of profitability, cash-vs-accrual quality, and fundamental change.

Feasibility contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Feasibility fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Authoritative Company Facts route:

`data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

The deterministic source-only census used 200 SHA-256-ranked unique issuer CIKs from the accepted Phase32 predictor source inventory. Only the issuer CIK inventory was reused; Phase32 labels, directions, taxonomy, performance, finalist, and protected evidence were not used.

The target-machine run on exact head `5a8c15f95417390d0d64ff240977adfb38a20c45` returned **`FEASIBILITY_PASS`**:

- source inventory unique CIKs: **4,400**;
- sample size: **200**;
- successful Company Facts documents: **200**;
- failed documents: **0**;
- accrual-history-ready issuers: **170** versus frozen minimum 100;
- profitability-history-ready issuers: **92** versus frozen minimum 80;
- group readiness counts: assets 174, cost of revenue 97, gross profit 78, net income 180, operating cash flow 180, revenue 136;
- target outcome rows read: **0**;
- protected return rows read: **0**;
- protected holdout consumed: **false**;
- provider reads/writes = **200 / 0**;
- broker/order/PAPER/LIVE/automation activity = **0**.

Accepted feasibility evidence fingerprint:

`33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9`

This result establishes source coverage only. It does not establish alpha.

## Current pre-Phase33 gate — XBRL PIT source / chronology / identity audit

Current audit contract:

`alpha-gate-xbrl-pit-audit-v1-source-only-accession-versioned-no-market-outcomes`

Frozen audit fingerprint:

`50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c`

The audit independently reconstructs exact original `10-Q`/`10-K` accession identity, official SEC acceptance time, first XNYS session strictly after acceptance, accession-versioned fact/restatement history, and issuer-to-instrument identity through Massive `/v3/reference/tickers` filtered by exact CIK + point-in-time date.

Frozen sample and gates:

- exactly **40** deterministic feasibility-ready issuers;
- up to **5** evenly spaced original accessions per issuer;
- Company Facts success >= **36**;
- selected original filings >= **180**;
- SEC metadata reconciled >= **170**;
- acceptance-time decision sessions >= **170**;
- unambiguous PIT instrument mappings >= **120**;
- issuers with >=3 unambiguous mappings >= **30**;
- same-accession semantic-context conflicts <= **0**.

Fact version rule:

`EXACT_ACCESSION_VERSIONED_NEVER_OVERWRITE_ACROSS_ACCESSIONS`

Identity remains governed by:

`instrument-identity-v4-no-issuer-level-medium-collapse`

**Alpha hypotheses are not frozen. Market prices/returns, target outcomes, and protected returns are forbidden.** Provider writes, broker/order/PAPER/LIVE/automation authority remain zero.

An `AUDIT_PASS` can authorize only the next scientific freeze package. It cannot itself authorize a performance study or satisfy Phase33.

See `docs/alpha_gate_sec_xbrl_pit_audit.md`.

## Protected boundary

Master protected outcome window remains `2026-05-12..2026-08-11`.

Phase32 development outcomes were legitimately opened under its frozen contract. Phase32 protected returns were never opened. The unconsumed holdout may be used only under a later scientifically valid, materially different preregistered mechanism after that mechanism's source, chronology, hypothesis, and protected-evidence contracts are frozen. It is not available for post-hoc Phase32 optimization.

The current XBRL source-only PIT audit reads **zero** market outcomes and therefore does not consume the holdout.

## Retained Phase31 provenance

Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE` under scientific fingerprint `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`.

Historical Phase31 full-acquisition runner retained for provenance: `scripts/run_phase31_form4_acquisition.py`.

The original Phase31 target result remains `FEASIBILITY_FAIL`; it is preserved rather than rewritten. The diagnosed root cause was a **Massive beta source-association/data-quality defect**, not a chronology-rule defect and not a performance result.

The accepted source-quality repair retained 45,915 authoritative rows under repair fingerprint:

`2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`

Retained source-quality policy:

`RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`

Phase31 produced zero survivors/winners/finalists/support and zero protected reads. Its original failed feasibility evidence, repair lineage, no-threshold-weakening rule, and final `ACCEPTED_NEGATIVE` disposition remain historical evidence while the project advances.

## Immediate repository action

Complete and validate the frozen XBRL PIT source/chronology/identity audit package on `alpha-gate-sec-xbrl-fundamental-quality-pit-audit`, including focused tests, static contract validation, synchronized docs, and Ubuntu/Windows CI. Only then run `scripts/run_alpha_gate_xbrl_pit_audit.py` on the target machine because repository CI cannot establish live SEC/Massive historical source coverage against the local accepted feasibility report and caches.

Do not read market outcomes or freeze an alpha hypothesis during this audit. Do not enter Phase33 unless a later XBRL scientific/performance gate earns accepted historical `SUPPORTED` authority.
