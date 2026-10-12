# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is being built to discover stock opportunities, compare stock and option trade expressions, simulate realistic accounts, and eventually operate through an observable PAPER workflow. The objective is positive returns after costs with controlled risk. No strategy currently has validated profitable trading authority.

**Reviewed 2026-10-12 against main at `641757803b00bbebf75eb5c20c366b2668ee9707`.** This documentation review is not a fresh workstation audit or a new simulation result.

## Start here

- [Project guide and roadmap](docs/roadmap.md): the single authority for goals, current state, architecture, dependencies, active work, and continuation.
- [Strategy evidence register](docs/strategy_evidence_register.md): compact results, limitations, dispositions, and completed experiment identities.

Read both before continuing. Update the guide in place when material state changes and the register when an experiment changes. This README is an entry page. Historical specifications and closeouts support the guide; they are not instructions to rerun completed campaigns.

## Current position

The Alpaca SIP stock corpus and historical news are available on the workstation. Stock research and recurrent-account components exist. Cached MarketData history supports EOD option diagnostics, but its entry clock did not reproduce the intended 09:35 option decision. Causal stock spots are ready for 9,654 cases, deduplicated to 9,455 option candidate surfaces. ThetaData source/enrichment plans, bounded qualification, cache support, and local Terminal preflight are implemented; provider acceptance and full acquisition are pending.

ThetaData Options Standard remains planned, with activation expected approximately three to four weeks after this review. Continue offline stock analysis, cached-result reporting, account-lifecycle work, and source-input preparation meanwhile. The [roadmap](docs/roadmap.md#ordered-roadmap) defines deliverables and dependencies.

## Local operator interface

From the existing Windows ATLAS environment:

```powershell
.\.venv\Scripts\python.exe scripts\run_phase19_control_plane.py
```

Open `http://127.0.0.1:8765`. The browser displays engine-owned evidence. PAPER/LIVE activation remains a separate gate. [Working and verification](docs/roadmap.md#working-and-verification) covers environment checks.

## Historical validator compatibility

This appendix records historical facts required by retained validators. It does not restore old roadmaps or grant current authority.

### Accepted reference and account contracts

The original A33/B33 catalog contains six families and nine direction-specific RESEARCH policies. Frozen identities:

| Contract | Fingerprint / version |
| --- | --- |
| Policy | `26a6aae124b1a5d2b14b8a11a72671b06ac34d3cf94eb7ac47f16d2cfb94a8b3` |
| Authority | `a23ec27367ae540b869abc428d118241e84436719a8a543cbdbc3f3b678c69c5` |
| Features | `ee7e09b680b64b65280dea88c01d402bd9576a04cc70bc7748d8e3048ff57159` |
| Legacy lake adapter | `reference-lake-adapter-v1-massive-development-split-free-identity-exact` |
| RESEARCH account replay | `c6528b5619a0058131347715dae771474a7b37babda282856f5f53a430f792fa`; short borrow unavailable |
| Signal clock | `reference-signal-availability-v1-xnys-regular-close-next-open` |
| Regime context | `reference-regime-context-v1-exact-asof-hash-bound-same-close-market-only`; same-session finalized market regime; ticker and sector remain unavailable in this adapter |

The master holdout was consumed exactly once with 93,380 protected return rows; a revised policy cannot reuse it. These legacy contracts are not the current Alpaca SIP V2 source contract.

### Accepted foundation through Phase32

Phase31 SEC Form 4 insider research closed `ACCEPTED_NEGATIVE`, with zero survivors, finalists, supported alpha, and protected reads.

Phases26–31 are scientifically valid `ACCEPTED_NEGATIVE`; Phase32 is `ACCEPTED_NEGATIVE` as well. Phase32 is `ACCEPTED_NEGATIVE`: frozen `solvency_distress_short` had 46 event rows / 33 signal sessions / 40 unique instruments versus 50 / 20 / 20 required. Exactly five hypotheses were frozen before performance. Protected stock/SPY returns remain unread for that experiment; protected return rows read = 0 and holdout consumed = false.

Phase32 scientific policy: `4e9d22e9ec3bae8058484a6a0e78e786c2c2822bc5a8607b294a21fb17a0bff7`.

Historical supported modern alpha remains **0**. Historical supported alpha remains **zero**. LIVE and automatic broker failover remain disabled.

“Phase33 signal-to-trade remains blocked” is a superseded historical product-dependency statement: baseline product construction is permitted, while LIVE authority stays blocked. Historical numbering: Phase33 — Signal-to-Trade Construction; Phase39 — Controlled LIVE Activation.

### Completed Pre-Phase33 SEC XBRL

The materially different point-in-time fundamental-information mechanism `PIT_SEC_XBRL_QUARTERLY_FUNDAMENTAL_PROFITABILITY_AND_ACCRUAL_QUALITY` may not reuse Phase32 candidate labels, directions, event taxonomy, development performance, finalist choice, or protected result.

XBRL source gate `FEASIBILITY_PASS`: 200 documents, 170 accrual-ready / 92 profitability-ready issuers; zero development passers. XBRL protected return rows read = **0** for this experiment. Final `ACCEPTED_NEGATIVE`.

| Historical identity | Fingerprint |
| --- | --- |
| Source merge | `69f8aa81289934b71f2652482c747391917c15a3` |
| Feasibility contract | `alpha-gate-xbrl-feasibility-v1-quarterly-fundamental-source-only-no-market-outcomes` |
| Feasibility | `6574a9c942d085fb897b7737961d26dd3da0c3a85b69992081a21f044960d152` |
| Accepted feasibility evidence | `33953ffe4543e2e9a98160821b67efd966d1974bc1685850fb2633ee138365a9` |
| PIT audit | `50e68495d71f15b24e27800b66e32ab12b914162be60906058086ffc14b1519c` |
| Closeout | `291770f7ee110dc85453f58e6410bee4a4431ac44c17f3e59b272fb88315ac91` |

## 7. Completed Pre-Phase33 SEC Schedule 13D/13G beneficial ownership — `ACCEPTED_NEGATIVE`

Historical source-only feasibility mechanism: `PIT_SEC_SCHEDULE_13D_13G_BENEFICIAL_OWNERSHIP_DISCLOSURE`; feasibility fingerprint `f1b6a5b22be1e5bbb3c5317118d0af88baaac40836a6b7051e6bc4789b3bb3bb`. Later scientific fingerprint `4bf51f02fb74a219609e2affef3319b24b7c98eb06fa9d88e405ae4f7448434c` is distinct. Final closeout: 3,652 predictors / 2,412 usable development outcomes / zero passers / protected returns unread; evidence `c67f21ace68b9ead20afb1db123e67e574b3ac3d26bf2fd897c6fcca215746b8`. Phase33 LIVE authority remains blocked.
