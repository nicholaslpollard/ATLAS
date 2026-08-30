# ATLAS Current Status and Handoff

**Last synchronized: 2026-08-29 (America/New_York). Phase32 is merged and closed `ACCEPTED_NEGATIVE` on target-machine source-only evidence. The independent finalist blindness/lineage audit reproduced `solvency_distress_short`, but its frozen protected population contained only 46 event rows versus the preregistered minimum of 50. Protected stock/SPY returns remain unread and the holdout remains unconsumed. Historical supported alpha remains 0 and Phase33 remains blocked. A materially different SEC XBRL fundamental-quality/accrual alpha gate is now open for source-only feasibility only.**

Read `docs/roadmap.md`, this file, `docs/alpha_gate_sec_xbrl_fundamental_quality.md`, `docs/phase32_closeout.md`, retained Phase32 source/scientific records, `docs/phase_flow.md`, and accepted code/CI evidence before continuing.

## Authority state

- Accepted foundation: through **Phase32**, merged into `main`.
- Phase26–32: all scientifically valid `ACCEPTED_NEGATIVE`.
- Accepted historical modern alpha support: **0**.
- Phase31 merge: `ab9fe4f31ea55c013ff7d0fbb52425f9e790f2f4`.
- Phase32 PR: **#37**.
- Phase32 merge: `69f8aa81289934b71f2652482c747391917c15a3`.
- Phase32 final disposition: **`ACCEPTED_NEGATIVE`**.
- Current research branch: `alpha-gate-sec-xbrl-fundamental-quality-feasibility`.
- Current research authority: **source-only SEC XBRL feasibility; no alpha hypotheses frozen and no market outcomes authorized**.
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

## Scientific interpretation

Phase32 produced genuine development evidence, but not admissible historical support. A candidate that cannot satisfy the preregistered protected sample-size gate cannot become `SUPPORTED` by looking at protected returns. The correct result is therefore `ACCEPTED_NEGATIVE`, not a threshold change or runner-up substitution.

Historical supported alpha remains **0**. Phase33 Signal-to-Trade Construction cannot start because its positive entry condition is not met.

## Current pre-Phase33 research gate — SEC XBRL fundamental quality / accrual feasibility

A new mechanism is open because it changes the economic/information source rather than retuning Phase32. It examines standardized point-in-time quarterly fundamentals from SEC 10-Q/10-K XBRL facts, with the intended mechanism family of profitability, cash-vs-accrual quality, and fundamental change.

Current contract:

`alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes`

Current fingerprint:

`6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152`

Current branch:

`alpha-gate-sec-xbrl-fundamental-quality-feasibility`

Authoritative source route:

`data.sec.gov/api/xbrl/companyfacts/CIK##########.json`

The XBRL client reuses the accepted SEC EDGAR fair-access/network seam and restricts it to exact Company Facts CIK JSON documents. There is no parallel SEC HTTP authority.

The deterministic source-only census uses 200 SHA-256-ranked unique issuer CIKs from the accepted Phase32 predictor source inventory. Only the issuer CIK inventory is reused; Phase32 labels, directions, taxonomy, performance, finalist, and protected evidence are not used.

Frozen source-only feasibility gates:

- exactly 200 sampled issuers;
- >=160 successful Company Facts documents;
- >=100 issuers with >=8-period assets + net-income + operating-cash-flow history;
- >=80 issuers with >=8-period assets + revenue + gross-profit-or-cost history.

**Alpha hypotheses are not frozen. Market prices/returns, target outcomes, and protected returns are forbidden.** Provider writes, broker/order/PAPER/LIVE/automation authority remain zero.

A feasibility PASS would authorize only the next independent PIT accession/acceptance-time, original-filing/restatement, and issuer-to-instrument identity audit. It would not authorize a performance study and would not satisfy Phase33.

## Protected boundary

Master protected outcome window remains `2026-05-12..2026-08-11`.

Phase32 development outcomes were legitimately opened under its frozen contract. Phase32 protected returns were never opened. The unconsumed holdout may be used only under a later scientifically valid, materially different preregistered mechanism after that mechanism's source, chronology, hypothesis, and protected-evidence contracts are frozen. It is not available for post-hoc Phase32 optimization.

The current XBRL feasibility gate reads **zero** market outcomes and therefore does not consume the holdout.

## Retained Phase31 provenance

Phase31 Form-4 alpha closed `ACCEPTED_NEGATIVE` under scientific fingerprint `e6364e797efe58ffb10fb6950eaf0f38d1553d7f0014dd0fde0413e0b95c5c67`. Its accepted source-quality repair retained 45,915 authoritative rows under repair fingerprint `2358fbd00b85795d49faab27602e99418314e41bd4ff0558fab18282b7bcaf83`. The original `FEASIBILITY_FAIL` remains preserved. Phase31 produced zero survivors/winners/finalists/support and zero protected reads.

## Immediate repository action

Complete and validate the XBRL source-only feasibility package on `alpha-gate-sec-xbrl-fundamental-quality-feasibility`, including focused tests, static contract validation, synchronized docs, and Ubuntu/Windows CI. Only then run `scripts/run_alpha_gate_xbrl_feasibility.py` on the target machine, because repository CI cannot establish the local accepted Phase32 issuer inventory or live SEC source coverage.

Do not read market outcomes or freeze an alpha hypothesis during this feasibility work. Do not enter Phase33 unless a later materially different alpha gate earns accepted historical `SUPPORTED` authority.
