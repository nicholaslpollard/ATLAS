# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-29 (America/New_York). Phase32 is closed `ACCEPTED_NEGATIVE` on target-machine source-only evidence. The independent finalist blindness/lineage audit reproduced the development finalist `solvency_distress_short`, but its frozen protected population contained only 46 event rows versus the preregistered minimum of 50. Protected stock/SPY returns remain unread and the holdout remains unconsumed. Historical supported alpha remains 0 and Phase33 remains blocked.**

Read `docs/roadmap.md`, this file, `docs/phase32_sec_8k_material_event_alpha.md`, `docs/phase32_scientific_contract.md`, `docs/phase32_predictor_independent_acceptance.md`, `docs/phase32_development_evaluation.md`, `docs/phase32_finalist_blindness_audit.md`, `docs/phase32_closeout.md`, retained Phase32 incident docs, and `docs/phase31_closeout.md` before continuing.

## Authority state

- Accepted foundation: through **Phase32**, pending Phase32 branch merge into `main`.
- Phase26–32: all scientifically valid `ACCEPTED_NEGATIVE`.
- Accepted historical modern alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Current closeout branch: `phase-32-sec-8k-material-event-alpha`.
- Phase32 final disposition: **`ACCEPTED_NEGATIVE`**.
- Phase33 signal-to-trade entry condition: **not satisfied / blocked**.
- LIVE and automatic broker failover remain disabled.

Root cause before workaround remains mandatory. The failed 50-row protected source gate may not be weakened, and the Phase32 family may not be retuned after results.

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

The independent finalist blindness / lineage audit was then run with `scripts/run_phase32_finalist_audit.py`. It independently reproduced the accepted development path and exact finalist before using source-only protected predictor metadata.

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

**Protected stock/SPY returns remain unread.** Protected return rows read = **0**. Protected holdout consumed = **false**. No protected-performance evaluator is authorized for this Phase32 family.

## Scientific interpretation

Phase32 produced genuine development evidence, but not admissible historical support. A candidate that cannot satisfy the preregistered protected sample-size gate cannot become `SUPPORTED` by looking at protected returns. The correct result is therefore `ACCEPTED_NEGATIVE`, not a threshold change or runner-up substitution.

Historical supported alpha remains **0**. Phase33 Signal-to-Trade Construction cannot start because its positive entry condition is not met.

The next alpha research work, if continued, must use a **materially different alpha mechanism**. It may not repackage or retune the failed Phase32 8-K family, lower 50/20/20, substitute `share_repurchase_long`, change the five-session horizon after results, or consume the untouched holdout to search for a rescue.

## Protected boundary

Master protected outcome window remains `2026-05-12..2026-08-11`.

Development outcomes were legitimately opened under the frozen Phase32 contract. Protected returns were never opened. The unconsumed holdout remains available only under a future scientifically valid, materially different preregistered mechanism; it is not available for post-hoc Phase32 optimization.

## Retained Phase31 provenance

Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE` under scientific fingerprint `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`. Its accepted source-quality repair retained 45,915 authoritative rows under repair fingerprint `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`. The original `FEASIBILITY_FAIL` remains preserved. Phase31 produced zero survivors/winners/finalists/support and zero protected reads.

Retained historical Phase31 feasibility provenance: feasibility fingerprint `505716315cff51656083265644075856794ffc49f5b1f36652578ac5622f005d`; Massive `form4_transactions` source route; Massive plan `Stocks Starter`; repair policy `RAW_PRESERVED_FAIL_CLOSED_ACCESSION_CHRONOLOGY_QUARANTINE`; diagnosed root cause `Massive beta source-association/data-quality defect`; historical acquisition runner `scripts/run_phase31_form4_acquisition.py`; source-quality repair runner `scripts/run_phase31_form4_source_quality_repair.py`.

## Immediate repository action

Run `scripts/run_phase32_closeout.py` on the target machine after pulling the closeout implementation. That runner validates the exact accepted audit/plan artifacts, verifies the 46 / 33 / 40 source-only proof, verifies protected reads remain zero, and emits `phase32_closeout_report.json`.

After that one target-machine closeout proof and green Ubuntu/Windows regression on the exact branch head, merge Phase32 as `ACCEPTED_NEGATIVE`. Do not enter Phase33 unless a later materially different alpha phase earns accepted historical `SUPPORTED` authority.
