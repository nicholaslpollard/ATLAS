# ATLAS Project Guide and Roadmap

**Reviewed 2026-10-14 (America/New_York). Code baseline: main at `8e9a35d89fe00f2ea4f14d63e47b075b8a219376` (PR #322). Workstation observations below retain their original dates.**

This is the single living project guide. It combines mission, architecture, current status, dependencies, work order, operating rules, and continuation. The [evidence register](strategy_evidence_register.md) records experiment results; the root README provides navigation. Code/tests establish behavior; original artifacts and Git history establish what ran. The documentation consolidation did not rerun the historical corpus. A subsequent operator metadata inventory on 2026-10-12 established the storage observations below.

## Goals and definition of progress

Build an operator-usable quantitative system that reconstructs trustworthy stock/news/options information point in time; evaluates independent strategy families and conditions; forecasts underlying move magnitude, timing, downside, and uncertainty; compares stock/option economics after costs; sizes, manages, and reconciles realistic accounts; replays history and operates prospective PAPER; records decisions and outcomes; and improves through versioned research with explicit promotion and rollback. Controlled LIVE operation is a later goal.

The financial objective is positive expected value and account growth after costs, with controlled drawdown, tail loss, concentration, capacity, and execution risk. Profit is never guaranteed. A completed download or functioning dashboard is engineering progress, not a profitable strategy.

Product engineering and strategy research proceed together. A negative research result does not block useful product work. A working product does not validate its baseline strategies. Avoid restarting the architecture when a research branch fails.

## Current status

| Area | Repository / previously recorded workstation state | Remaining limitation |
| --- | --- | --- |
| Stock source | Alpaca SIP V2: 67,480 complete units, 5,302 daily / 62,178 minute; 3,897,688,734 canonical rows and 1,757,288 quarantined rows; acquisition/acceptance/research metadata found locally on 2026-10-12 | Inventory reads headers only; retain existing acceptance receipts for source identity and cutoff before a dependent raw-data replay |
| Daily/minute semantics | V2 research preparation and B34 intraday/session audits accepted | Preserve missing bars, exact source identity, and corporate-action boundaries |
| News | 141 monthly partitions, 2,211,606 records; source-integrity V2 accepted | No validated news-derived alpha; sentiment and attribution need PIT-safe evaluation |
| Strategy laboratory | 21 economic families / 28 routes; 54,618,427 standalone DEVELOPMENT records; conditioning v1 completed | Aggregate conditioning/account evidence does not establish robust profitable strategies |
| Dynamic exits | Prior-fold discrete Dynamic Exit V1 and continuous distribution-based V2 tested | V1 negative later results; V2 saturated near 3%/5%; neither is an accepted final exit policy |
| Recurrent account | Reservations, entries, marks, closes, re-entry, clocks, durable checkpoints, transactions, observability, offline retry mechanics and read-only mark coverage preview implemented | Accepted retry/source integration, historical settlement and missing-mark source resolution remain open |
| MarketData options | Candidate raw chains, exact-series caches, receipts, source reconciliation, and EOD account diagnostics exist | EOD timing differs from the intended intraday strategy; unresolved positions prevent a valid full account return |
| Stock exit clock | 9,667/9,974 pre-2026 cases expressible after 09:35; 304 already finished; three trigger gaps | Minute bars cannot establish within-minute tick ordering |
| Decision spot | 9,654/9,667 causal 09:35 spots; 13 missing-minute cases; 9,455 unique surfaces | Old 18,921 open-selected single-contract requests are superseded; do not acquire them |
| ThetaData | v3 client, source/enrichment plans, quote/OI qualification, candidate cache, and zero-data Terminal preflight implemented | No accepted provider run or full acquisition recorded |
| Operator UI | Phase19 local control plane, replay drilldowns, A34.5 read-only paper observability, recurrent lifecycle projections | Integrated operator product and A35 PAPER broker mutation unfinished |
| Trading authority | Research/baseline engineering; historical supported modern alpha remains zero | No strategy promotion, qualifying PAPER, LIVE, or automatic broker failover |

File presence proves implementation, not workstation completion. Consult the evidence register for scientific results and actual manifests for physical cache state.

## System map and active components

The common engine follows `PIT source -> features/context -> independent strategies -> evidence/forecast -> stock/options construction -> risk/account admission -> execution/lifecycle -> outcomes/performance -> operator interface`.

| Component | Role and source of truth |
| --- | --- |
| Parquet / DuckDB | Durable analytical lake and replay engine; accepted Alpaca SIP V2 is the current stock research base |
| Alpaca market data | Primary current stock/options data; REST discovery and selective streams for finalists/positions |
| MarketData.app | Retained candidate-first historical EOD cache; diagnostic history, not a 09:35 quote proxy |
| ThetaData | Intended historical intraday option candidate; Standard subscription pending; source qualification before full acquisition |
| Massive / Czar28 | Retained provenance, anomaly diagnosis, optional challengers; not required simulator critical-path downloads |
| SEC / regulatory sources | Existing research lineage; closed negative/source-limited branches are not active rerun queues |
| Webull / Alpaca execution | Webull primary PAPER/sandbox and intended LIVE broker after acceptance; Alpaca explicit/manual secondary; no automatic failover |
| ML / AI | ML supplies evidence/ranking only; AI optional late independent verification; quantitative pipeline works with AI disabled |
| API / browser | Displays authoritative engine records; never computes a separate trading truth |
| PostgreSQL / Docker / frontend scaffolds | Future operational/deployment work; presence is not accepted production readiness |

Core code: `packages/data`, `packages/backtesting`, `packages/strategies`, `packages/simulation`, `packages/providers/thetadata`, `packages/control_plane`, `scripts`, and `apps/web`. Contracts, source receipts, and append-only trials remain authoritative.

### Workstation storage

ATLAS source, environment, accepted stock corpus, checkpoints, and core runtime remain on C:. Secondary root `D:/ATLAS_DATA` is selected by `ATLAS_EXTERNAL_DATA_ROOT`; verified Windows junctions retain stable project paths. The operator's 2026-10-12 inventory reported all six bindings READY: options, news, provider qualification, research evidence, fundamentals, and archives. Free capacity at that observation was C: 140.51 GiB / D: 228.72 GiB. Capacity changes with use.

Raw responses are immutable. Preserve hashes, receipts, and original failures; reuse verified caches. Missing D: bindings must not spill acquisition onto C:. The [secondary-storage specification](external_secondary_storage_v1_20260924.md) defines bindings and quotas.

## Simulation and research boundaries

- Measure signal expectancy, instrument expression, execution assumptions, and account competition separately. Paired trade diagnostics are not portfolios.
- Select option contracts from surfaces available at the actual decision clock. EOD values cannot become intraday prices, fills, or same-day features.
- Preserve identity/deliverables, source clocks, calendars/early closes, financing, spread/liquidity, and unresolved positions explicitly.
- Unknown marks mean unknown equity/total return. Cash or realized P&L cannot replace equity. Never drop unresolved losses to complete a report.
- Fit forecasts, thresholds, selectors, and revisions on prior windows only; maintain DEVELOPMENT/qualification boundaries, purging, embargo, and trials.
- Keep standalone strategy/version lineage and counterfactual/rejected decisions. Favorable post-result slices are hypotheses, not validated rules.
- Do not weaken costs, support thresholds, source checks, or protected-data restrictions to turn a failure into PASS. Confluence is separate and remains unopened as a profitability rescue search.
- Master `2026-05-12..2026-08-11` was consumed exactly once on 2026-09-07, with 93,380 protected return rows. It cannot qualify a revised strategy. Each package names its permitted interval; source scans must not open protected outcomes indirectly. New prospective evidence is still needed.
- Historical fills, strategy validation, operational PAPER, qualifying PAPER, and LIVE are distinct acceptance states.

Deterministic decisions retain underlying distribution/horizon, PIT catalyst context, costs/uncertainty, instrument construction, risk/sizing, position plan, rejection reason, outcome, and source/code/policy lineage. AI does not generate signals, select contracts, size, or construct exits.

## Ordered roadmap

ThetaData Options Standard remains planned. Activation is expected approximately three to four weeks from 2026-10-12; this estimate is not a scheduled purchase. Progress below does not depend on immediate activation.

| Order | Work package | Completion criterion | Dependency |
| --- | --- | --- | --- |
| 1 | Workstation/cache inventory — metadata pass complete 2026-10-12 | All expected metadata groups found and six D: bindings READY; several option files exceeded the 8 MiB read limit, so their contents remain uninspected | Inventory is not new source acceptance; no purchase |
| 2 | Unified offline results — selected stock and retained option ledger reviews verified | Stock report reconciles 36,254 selections, 43 directions and 33 folds; full stock baseline stays blocked by one changed file. Option audit reconciles 84 entries / 74 closes / ten unresolved positions and retained cash/fees | Completed retained-result review; source acceptance, settlement and broker-specific cost qualification remain separate |
| 3 | Historical account lifecycle — retries and mark coverage preview implemented | Frozen retry/calendar mechanics, resumable cursors and partial coverage reporting are fixture-tested; strict valuation still requires all fresh exact-position marks. Accepted source integration and settlement remain open | Existing engine/cache; unresolved evidence demand identifies physical dependencies |
| 4 | Option input and execution-cost readiness | Identify PIT dividend/rate/event/volume gaps; qualify broker/account/order-channel fee schedules, applicable dates, pass-throughs and rounding; validate with fixtures | No subscription for design/fixtures; account classification and applicable broker schedule required for broker-accurate costs |
| 5 | ThetaData local/source acceptance | Terminal preflight, bounded quote/OI qualification, original receipts, timestamp/schema/entitlement/repeatability checks | Active subscription and Terminal; no full campaign before success |
| 6 | Candidate acquisition/construction | Acquire/reuse frozen 9,455 surfaces; qualify enrichment; PIT filters, dividend-aware Greeks, then common economic contract selection | Accepted source/storage; separately qualify unproven Greeks surface |
| 7 | Exact option replay | Selected-contract exit demand only; execution/lifecycle at stock decision/exit clocks; STOCK vs OPTION comparison with coverage/costs | Selected entries, exact quotes, accepted inputs/lifecycle and qualified broker-specific costs |
| 8 | Further strategy experiments | Separately frozen hypotheses, prior-only training, untuned qualifying/prospective evidence; failed versions/trials retained | Evidence reviewed; experimental specifications still to be decided |
| 9 | Operator PAPER and production | Integrated engine/UI, accepted Webull PAPER path, reconciliation/observability, operational state/recovery, authenticated deployment | Explicit authority packages; A35/A37 |
| 10 | Qualifying PAPER and controlled LIVE | New prospective evidence, risk/execution acceptance, explicit promotion/rollback | A38, then Phase39; currently blocked |

Orders 2-4 can overlap after required files are verified. Missing option access must not block stock/product work. Avoid new full strategy tournaments or repeated completed source campaigns merely to keep the machine busy.

### Offline workstation review

`scripts/review_offline_workstation_v1.py --save-report` implements a bounded metadata inventory for order 1. It inspects storage bindings and free capacity, locates the known stock/news/successor reports and option/ThetaData plans, and reads only small allowlisted JSON headers. It saves one new inventory JSON under `data/research/offline_workstation_review_v1`; the original inputs remain read-only.

The command makes zero provider/broker calls, scans no bars or raw quote bodies, and runs no simulations. Missing or misbound paths, oversized/unreadable metadata, multiple candidates, and truncation remain explicit. It never picks the newest plan or describes file presence/reported headers as accepted source lineage. Use the inventory to choose the next existing artifacts to inspect, not to rerun completed acquisition or validation. No new strategy specification, threshold change, or authority is created.

The saved operator inventory was `data/research/offline_workstation_review_v1/20261012T224545593297Z.json`. It found the stock acceptance/research, news, successor, Dynamic Exit V1 and ThetaData-plan metadata. The reported option decision-clock/quote-lineage gaps were existing files too large for the bounded header reader; this result did not establish missing market files or renew their acceptance.

### Retained stock results review

`scripts/review_retained_stock_results_v1.py --save-report` advances order 2 using two frozen analysis summaries and five small aggregate Parquet files: option-worthiness strategy inventory, route returns, selected folds, and selected-daily path/first-touch summaries. It recomputes the original accepted analysis identities, verifies the contents actually read, and reconciles route/direction, fold, path, threshold and inventory populations. It never follows file paths supplied by a report or selects a newer run. Missing, altered, oversized or inconsistent artifacts block reporting; no rebuild or fallback is automatic.

The JSON under `data/research/retained_stock_review_v1` retains all recorded route directions, including losing and unselected routes. It reports gross/primary/stress means, observed cost drag, selection coverage, fold signs and concentration, five-session excursions/giveback, and unordered same-session first touches. Daily baseline MFE/MAE remains explicitly 20-session evidence. The existing dependencies suffice; temporary aggregate snapshots are discarded after reading. The original evidence remains read-only.

The operator's diagnostic ZIP on 2026-10-12 showed that six small aggregates match their original hashes, but `optionworthiness_v1/caedb97b7031c70e/route_summary.parquet` does not: expected `a9f72b5f4b8ad82af556ca1e62c729d1286f1cd78cf08cecfe82e769c312f412`, observed `4d68e887a7d43d69b043809cf1edd41ed21281ff111926c06dcf16f42b732c9c`. Its selected means have tiny floating-point differences from the original embedded summary; the entire file has not been proven equivalent. The original hash and failed full-review disposition remain intact. No automatic rewrite or hash replacement is permitted by the reviewer.

`--selected-only --save-report` produces a separately labeled selected-results review without opening that route file. It pins the complete original stock/path summary bytes, verifies six healthy aggregates, and reconciles embedded selected metrics against folds, stability, threshold curves and five-session paths. All 43 observed directions remain visible, including 14 with no comparable selections. Full DEVELOPMENT/test route means and selected-return medians remain unavailable in this mode. The uploaded artifacts completed this scoped review; another operator run is unnecessary to establish the uploaded result.

The reader accepts the original SQL decimal threshold representation without changing the exact 1/2/3/5% grid. Its test-record count is the 45,907,526 retained assignment rows bound by the input summary, rather than the narrower 45,516,323 test-eligible count in the conditioning closeout.

This is a descriptive review of existing DEVELOPMENT results. It does not rerun or reaccept the 54-million-record source set, change strategy or exit settings, estimate option profit, or compute compounded account returns. Week/month/year account windows and regime-specific acceptance require separate case/account evidence. No new strategy experiment specification is established by this reviewer. The full baseline cache needs an original hash-matching copy or a separately scoped reconstruction; it must not trigger a broad automatic rerun merely to unblock reporting.

### Offline account lifecycle

The synthetic account engine now reports `replay_horizon_utc`: the explicit as-of cutoff, or the latest decision/entry/exit clock in the chosen-mode fixture cohort. A future failed exit cannot alter an earlier snapshot. An exit failure needs a reached attempt clock; an untimed flag is not an observed attempt. Other instrument modes do not advance this account's clock.

With only an expiration date, the engine marks an open option as unresolved expiry/assignment after that date has ended in New York. It does not infer an intraday trading/exercise deadline or settle the contract. Failed exits and unresolved expiry retain positions, committed cash and exit-fee reserves; missing marks keep equity unknown.

`packages/simulation/offline_option_exit_retry_v1.py` adds an explicit opt-in retry plan to that same synthetic account engine. Each plan specifies its request clock, hard deadline, interval, attempt limit and quote-age limit before quotes are inspected. The schedule uses frozen XNYS regular-session windows, including holidays, early closes and daylight-saving shifts, and ends before expiration day. This is a conservative planning window, not acceptance of an option's trading/exercise hours. Bounds are 64 attempts per plan, a 31-day window and 100,000 aggregate account attempts. Existing fixed-exit paths retain their behavior; no strategy defaults are changed.

The new path accepts only in-memory synthetic observations for the exact contract. A usable modeled exit needs a positive uncrossed bid/ask, qualified source/clock flags, observation and availability by the attempt, permitted quote age/session, and displayed bid size covering the whole position. Missing, stale, future, late-available, one-sided, zero-bid, crossed, wrong-contract, undersized and unqualified observations retain explicit failure reasons. It does not change contracts or shrink positions to manufacture an exit. Known slippage and fees flow through the existing ledger once; failed attempts leave cash and fee reserves unchanged, and exhausted plans remain open with unknown equity.

Retry cursors preserve the frozen plan and completed attempt prefix. Restoration requires the caller's retained plan/cursor fingerprints; completed attempts are not reread and a ready close quote ends the retry loop. These are quote-retry checkpoints, not standalone durable account checkpoints. Fixtures reconcile resumed versus uninterrupted cursors, future-quote isolation, CALL/PUT cash, slot release and legacy paths. The package makes no provider requests and does not rerun or reaccept historical results. Accepted source/recurrent-account integration, settlement evidence and missing-mark valuation remain downstream; new historical research authority is not created.

The recurrent coordinator's `mark_coverage_preview` exposes known position values and explicit missing/stale/clock-mismatch reasons without changing its account, ledger, revision or published valuation. Incomplete coverage leaves total equity and aggregate unrealized P&L unknown; cash, reserves and entry book values remain separately labeled. Provenance/identity errors, duplicate marks and extra positions still fail closed. Complete coverage delegates to the existing strict valuation builder. A fresh zero option bid can be a known valuation mark; it does not force an exit or settlement. This preview is an engine-owned read-only dictionary, not an accepted partial valuation state or a new risk/account mutation input.

### Retained option account review — completed workstation gate

`scripts/review_retained_option_account_v1.py --save-report` reads only the original V2 scenario `multiyear_continuous_dynamic_exit_v2_option_scenario_03406fdf1def8233.json` and strict account `multiyear_continuous_dynamic_exit_v2_option_replay_b525b49fabd0aead.json`. Each read is bounded at 64 MiB. The legacy filenames retain 16-character identities: the reader checks those original run prefixes, the complete reports' existing self-signatures, mutual scenario linkage, frozen policy/costs and recorded populations. It captures complete fingerprints and raw-file hashes in the new review. This is retained-result integrity and accounting reconciliation, not new source acceptance. It never chooses a newer run or follows paths stored in a report.

The operator completed the review on 2026-10-14 (America/New_York), reconciling 84 admitted / 74 completed / ten unresolved positions, $24,997.70 cash and -$33,365.40 modeled realized P&L. All ten unresolved positions opened in 2021 and carry `STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP`; this is the retained source classification, not proof of permanent market illiquidity. Their 226 contracts retain $41,636.90 committed entry cash including fees and $146.90 reserved exit fees, leaving $24,850.80 cash after that reserve. Equity, total return and terminal valuation clock remain unknown. The saved review is `data/research/retained_option_account_review_v1/20261015T035701371767Z_98c60bf4.json`; its fingerprint and the complete original report identities are in the evidence register. No simulation, raw quote/bar scan, provider request, settlement, retry policy or capital release was performed. Another review run is unnecessary for this result.

Evidence demand includes exact deliverable/corporate-action lineage, original exit-clock observation or explicit absence, an explicit terminal account clock, exercise/expiration outcome, historical settlement cash/share movements and marks for any resulting positions. Exercise can change cash and share holdings, and adjustments can change deliverables; see [OCC equity options](https://www.theocc.com/clearance-and-settlement/clearing/equity-options-product-specifications) and [OIC contract adjustments](https://www.optionseducation.org/referencelibrary/faq/splits-mergers-spinoffs-bankruptcies). Settlement timing must use the historical effective rules, including the [2024 T+1 transition memo](https://infomemo.theocc.com/infomemos?number=54436). The reader does not infer those outcomes from expiration dates, intrinsic value, missing bids or a nominal 100-share model. The negative V2 branch remains closed; this demand cannot silently revise its outcomes or promote a new strategy.

### Broker fees and execution costs — unqualified

The frozen V2 `ReplayPolicy` uses $0.65 per option contract on entry and $0.65 on exit, zero additional option slippage, and ask-entry/bid-exit pricing. These are generic model assumptions. Reconciled arithmetic does not verify the selected broker's charges; the $146.90 exit-fee reserve is 226 contracts times $0.65, not a broker bill. The flat constants do not separately model date-dependent regulatory/clearing/exchange fees, order-size exceptions, daily rounding or account classification. They are not established as conservative overall execution costs.

Official schedules checked on 2026-10-14 (America/New_York): [Webull US OpenAPI](https://developer.webull.com/apis/docs/trade-api/faq/) says API trading fees match its app, while [Webull equity-option pricing](https://www.webull.com/trading-investing/options) distinguishes ordinary commission-free orders from oversized/index exceptions and pass-through charges. [Alpaca's fee schedule, revised 2026-10-12](https://files.alpaca.markets/disclosures/library/BrokFeeSched.pdf), distinguishes ordinary equity options from professional/index/partner arrangements and applies separate pass-throughs with daily aggregation/rounding. Current schedules do not establish historical 2021-2025 charges.

Before broker-comparable simulation, bind the broker, US account/classification, order channel/product, fee effective dates, component rates, exceptions and aggregation/rounding rules. Test those rules and reconcile actual broker fee records when available. Keep bid/ask spread, additional slippage, financing/borrow, and recurring data/platform costs separately identified. Preserve the original V2 policy/artifacts; use any qualified fee profile only in a separately bound future run. Fee qualification can advance without ThetaData and creates no new strategy experiment or profitability claim.

### ThetaData handoff

The implemented v3 client makes HTTP calls through a local Theta Terminal, normally `127.0.0.1:25503`. Zero-data preflight checks Java 21+, loopback reachability, authentication-source presence, and plan signatures/linkage. It does not prove entitlement. The [preflight command](../scripts/preflight_thetadata_terminal_v1.py) needs actual `--source-plan` and `--enrichment-plan` paths.

The [combined qualifier](../scripts/qualify_thetadata_candidate_source_pipeline_v1.py) makes at most 32 read-only requests: 15 quote anchors plus a repeated 2021 surface; then 15 OI anchors plus a repeat only after quote success. Keep no-data, transport, and entitlement outcomes distinct. Full acquisition follows acceptance.

Frozen demand is CALL-only at 09:35, all strikes/expirations, max DTE 75. Pre-Greeks filters: 14-45 DTE, OI >=100, spread-to-mid <=15%. OI must be available by decision time and represents prior-session state under pending qualification. The enrichment plan targets expiration-specific first-order Leisen-Reimer historical binomial Greeks: 101 steps, version 1, minute boundary, SOFR, explicit PIT annual dividends. This is architecture, not accepted provider Greeks evidence. Missing dividends cannot default to zero. Volume/event context and final economics/selection are downstream.

## Working and verification

Use the existing environment. Reproduce `requirements.lock`, then install editable without resolving a new dependency set:

```powershell
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m pip check
python scripts/validate_dependency_lock.py
python scripts/validate_secret_hygiene.py
```

Run focused changed-package tests, required validators, and cross-platform CI. Partial environments/fixtures are not full acceptance. Documentation-only changes require reference/compatibility checks, not a historical rerun. Local simulation results require operator data; GitHub tests cannot replace workstation evidence.

Use coherent packages: clear scope, focused validation, reviewable diff, guide update, merge, verification. Explain change, result, limitation, and next action plainly. Continue until a real local run, unavailable file, external dependency, or authority gate needs the operator.

### Efficiency standard

- Project needed columns, symbols, sessions, and contracts; reuse feature passes and completed results before scanning the large stock lake.
- Deduplicate demand globally, persist responses before dependent work, and resume validated checkpoints.
- Benchmark workers/threads/I/O on actual hardware; prove deterministic output hash/receipt equivalence before accepting optimization.
- Retain resource headroom and provider limits. Completion order must not become scientific ordering; resource adaptation cannot weaken quality.
- Long jobs emit start/scope/profile, completed/total, reused/new, elapsed time, throughput, heartbeat at least every 60 seconds, ETA or explicit unavailable, and terminal status. Write observability atomically outside scientific fingerprints.

B35 continuation achieved 4,246.7 units/hour versus 660.6 serial; a single-scan rewrite fell to 820.8. Measure bottlenecks rather than assuming fewer files or more workers is faster.

## Documentation ownership

1. Keep current goals, capabilities, limitations, dependencies, and next work here. Replace old paragraphs instead of appending daily logs.
2. Record scientific results/dispositions in the evidence register; link closeouts/contracts for detail. Acquisition telemetry belongs in receipts, not this ledger.
3. Update README for navigation, material entry instructions, or compatibility only.
4. Preserve specs/closeouts needed by code, validation, or unique evidence. Future chats need not read every historical file.
5. `current_status.md` and `phase_flow.md` are frozen validator records, not current handoffs; old statements are scoped to their historical experiments.
6. Remove unused empty docs, obsolete packaging notes, duplicate archives, and superseded operational prose. Git history retains original versions.
7. Add a document only for a durable spec or unique evidence without an existing owner. No competing status/roadmap files.

Before continuing, read this guide and the register, inspect Git head/worktree, then inspect source/tests and original records needed by the active package. Reconcile disagreements before claiming readiness.

## Historical validator compatibility

This appendix preserves binding historical facts and exact identities required by accepted validators. It is not a current work queue. Original documents remain at [the baseline commit](https://github.com/nicholaslpollard/ATLAS/tree/641757803b00bbebf75eb5c20c366b2668ee9707).

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
