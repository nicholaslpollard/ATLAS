# ATLAS

**Autonomous Trading, Learning, and Analysis System**

ATLAS is being built as an options-first research and trading system: discover opportunities in option pricing and volatility, independently evaluate stock signals, compare trade expressions, simulate realistic accounts, and eventually operate through an observable PAPER workflow. The objective is positive returns after costs with controlled risk. No strategy currently has validated profitable trading authority.

**Reviewed 2026-10-22 through merged PR #356 (`018d9557`).** The 815-underlying source-demand census, Free-tier ThetaData EOD connectivity/audit, B34 six-snapshot source review, and ZSL 20-prior-session premarket-volume diagnostic are complete on the workstation. The ZSL diagnostic found all 20 sessions, 5,150 prior premarket source rows, and raw volume ratios 0.669238 at 09:20 and 0.662866 at 09:30/09:35. These ratios remain NOT strategy-admissible: the 2026-10-22 complete archived-ledger check returned zero April ZSL action candidates, but independent issuer-action completeness, identity continuity and PIT comparability remain unqualified. Historical intraday option quotes, OI, Greeks, paid-tier access and fills also remain unqualified. The frozen options-native SPY 10:00 CALL/PUT anchor qualifier is implemented but has not been executed against paid data.

## Start here

- [Project guide and roadmap](docs/roadmap.md): the single authority for goals, current state, architecture, dependencies, active work, and continuation.
- [Strategy evidence register](docs/strategy_evidence_register.md): compact results, limitations, dispositions, and completed experiment identities.
- [Options-native pilot plan](scripts/plan_options_native_pilot_v1.py): provider-free specification and bounded CALL/PUT discovery demand; no performance run or download.
- [Pilot input packet](scripts/inspect_options_native_pilot_inputs_v1.py): completed 21-close SPY raw-input check; its uploaded packet is verified and needs no repeat.
- [Cached pilot stock-input review](scripts/review_options_native_stock_inputs_v1.py): completed 22/22 exact minute observations in the retained operator report; not a task to repeat.
- [Multi-underlying source-plan inventory](scripts/review_options_multi_underlying_source_inventory_v1.py): completed on 2026-10-17; the signed 09:35 CALL-only source plan enumerates 815 underlyings, 9,455 deduplicated requests and 9,654 case memberships (2021-09-28..2025-12-24). No quotes, downloads, option listing or simulated trades were qualified.
- [ThetaData Python-library preflight](scripts/preflight_thetadata_python_library_v1.py): zero-data provider-environment, pinned SDK method-signature and frozen-plan check; the separate [provider environment setup](scripts/setup_thetadata_python_env_v1.py) can be completed before subscription without market-data requests.
- [B34 causal premarket context review](scripts/review_b34_premarket_decision_context_v1.py): completed 2026-10-20 with six source-only snapshots for ZSL 2026-04-30 and AA 2026-03-09; zero provider/outcome calls, no option fills or performance.
- [B34 prior-20-session premarket-volume readiness](scripts/review_b34_premarket_prior20_volume_v1.py): completed on the workstation 2026-10-22, reviewing ZSL 2026-04-30 against 20 preceding NYSE sessions (5,150 historical premarket minute rows, 20/20 observed at each clock). The ratios are **source diagnostics only**, not split/PIT-qualified signals; do not repeat this accepted data scan.
- [Options-native 10:00 SPY CALL+PUT quote-source gate](scripts/qualify_options_native_spy_thetadata_quotes_v1.py): **provider-free inspection completed 2026-10-22** (design fingerprint `73369c3d84d35ac90fea4abb2abec0a72dd858065add7d0613c3c79c7d44167e`, 0 provider reads). Exactly 24 frozen year-stratified 2018–2025 entry anchors plus one repeat; the default command makes zero requests. A separate future paid-tier run requires all three explicit authorization flags and caps quote method calls at 25. Distinguishes transport/no-data/schema, validates both option rights, 10:00 causal timestamps and same-strike 30–45 DTE pair shape; requires all three paid flags even from Python, checks repeated price/size/exchange/condition values, and retains immutable SDK-normalized source receipts (not raw network responses); no OI/IV/Greeks/fills/outcomes or strategy authority.\n- [B34 original ZSL corporate-action candidates](scripts/review_b34_premarket_zsl_action_candidates_v1.py): **completed 2026-10-22**. The workstation hash-checked the previously accepted 378,362-record original action ledger; **zero April ZSL effective-date or undated candidates** were selected. This does NOT establish complete action coverage or split-adjusted volume. Independent [ProShares](https://www.proshares.com/press-releases/proshares-announces-etf-share-splits-021126) and [SEC 8-K](https://www.sec.gov/Archives/edgar/data/1415311/000119312526046988/d39409d8k.htm) sources identify a 1-for-10 ZSL reverse split **effective 2026-02-26**, outside the April lookback. Those retrospective research leads do not certify the absence of other actions; do not repeat the ledger scan.
- [Offline workstation review](scripts/review_offline_workstation_v1.py): one bounded, provider-free inventory of storage bindings and retained metadata; usage is in the project guide.
- [Retained stock results review](scripts/review_retained_stock_results_v1.py): reconcile accepted route/fold returns, costs, concentration, and five-session paths without a new replay; `--selected-only` uses the exact original summary and six matching aggregates when the full route cache is unavailable.
- [Retained option account review](scripts/review_retained_option_account_v1.py): audit the original V2 ledger, retained cash/fees and unresolved contracts, then save a bounded evidence demand without rerunning its simulation.
- [Retained exact-exit source audit](scripts/audit_retained_option_exit_sources_v1.py): explain the ten unresolved exit labels using their original hash-bound quote histories and cache receipts; no strategy or account replay.

Read both before continuing. Update the guide in place when material state changes and the register when an experiment changes. This README is an entry page. Historical specifications and closeouts support the guide; they are not instructions to rerun completed campaigns.

## Current position

The Alpaca SIP stock corpus and historical news are available on the workstation. Stock research and recurrent-account components exist. Cached MarketData history supports EOD option diagnostics, but its entry clock did not reproduce the intended 09:35 option decision. Causal stock spots are ready for 9,654 cases, deduplicated to 9,455 option candidate surfaces. ThetaData source/enrichment plans, bounded qualification and cache support are implemented. The isolated direct Python-library transport and zero-data preflight are prepared. The operator's 2026-10-20 Windows setup confirmed Python 3.14.0, ThetaData SDK 1.0.12, python-dotenv 1.2.4 and compatible SDK method signatures. A subsequent zero-provider-read preflight confirmed a recognized API-key source and both frozen source/enrichment plans valid and linked. The first **real Free-tier ThetaData EOD calls** then succeeded: SPY 2026-10-16 stock EOD (one row, 16 columns), and 2026-11-20 SPY CALL EOD for the same observation day (four rows, 20 columns), with 2 market-data method calls total. The [retained EOD audit](scripts/audit_thetadata_free_eod_receipt_v1.py) verifies the original local JSON fingerprint, all rows, contracts and EOD timestamps without contacting ThetaData. **EOD schema connectivity is proven, but 09:35 option quotes, historical OI, Greeks, paid-tier entitlements and source qualification are not.** Java/Theta Terminal is not needed for the Python-library route.

The retained V2 account review completed on 2026-10-14. The 2026-10-15 exact-exit audit found all ten original quote sources: nine exits failed the legacy positive-volume rule and one failed the fixed 16:00 rule on an early close; four positions exceeded reported bid size. These findings establish neither fills nor resolved account equity. Opt-in synthetic partial-exit accounting now tests residual contracts, cost basis and fee reserves. The retained $0.65-per-contract costs remain generic assumptions; broker-specific costs and historical settlement remain open in the roadmap.

ThetaData Options Standard ($80/month) is planned for Friday, 2026-10-23, but is not active yet. The direct Python SDK remains pinned to 1.0.12; newer public releases do not authorize silent upgrades. Continue offline planning, account-lifecycle work and cached-result reporting meanwhile; verify historical coverage and exact entitlements at checkout. PR #347 blocks ambiguous legacy dividend-dollar versus yield inputs to historical binomial Greeks before SDK initialization; quote/OI remain separately available only under their existing access gates. The [roadmap](docs/roadmap.md#ordered-roadmap) defines deliverables and dependencies.

The first options-native pilot is a separately versioned SPY long-straddle hypothesis with prior-only volatility inputs and option-aware daily exits. Its specification, 411 weekly CALL/PUT discovery requests, synthetic feature/contract selection, daily exit requests and two-leg cash/exposure mechanics are implemented. The uploaded raw-input packet reconciles all 21 closes; synthetic economic-return arithmetic now requires explicit split, cash-entitlement and timing inputs. The cached 22-clock check and 411-week physical coverage review are complete (407 price-complete weeks). State Street's original issuer workbook reconciles all 33 target-period cash dividends, including the 2018-06-15 archive omission. A separate all-event publication-demand packet is complete, but original as-of announcement/revision receipts are absent. The completed offline multi-underlying inventory confirms 815 distinct symbols across the 9,455 planned 09:35 CALL requests. The frozen 10:00 SPY CALL+PUT pilot remains separate; no source plan is a list of available historical option contracts. Historical economic-return/source clocks, per-underlying action completeness, real option quotes, broker costs and multi-leg execution remain unqualified. The next market-data step requires separately accepted provider/source access; do not rerun the inventory. The original 9,455 stock-to-CALL surfaces and closed experiments retain their own identities.

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
