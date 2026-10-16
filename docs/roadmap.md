# ATLAS Project Guide and Roadmap

**Reviewed 2026-10-16 (America/New_York). Confirmed main baseline before this package: `c6ada0620f28832c11c56f4b8fdb8ee1a17af120` (PR #331). The SPY 411-week exact-minute input coverage scan has now completed on the workstation. Workstation observations retain their original dates.**

This is the single living project guide. It combines mission, architecture, current status, dependencies, work order, operating rules, and continuation. The [evidence register](strategy_evidence_register.md) records experiment results; the root README provides navigation. Code/tests establish behavior; original artifacts and Git history establish what ran. The documentation consolidation did not rerun the historical corpus. A subsequent operator metadata inventory on 2026-10-12 established the storage observations below.

## Goals and definition of progress

Build an operator-usable quantitative system that reconstructs trustworthy stock/news/options information point in time; evaluates independent strategy families and conditions; forecasts underlying move magnitude, timing, downside, and uncertainty; compares stock/option economics after costs; sizes, manages, and reconciles realistic accounts; replays history and operates prospective PAPER; records decisions and outcomes; and improves through versioned research with explicit promotion and rollback. Controlled LIVE operation is a later goal.

Options-native discovery is a primary research branch: volatility pricing, implied versus forecast movement, skew, term structure and events can originate a hypothesis without a stock BUY signal. Stock research remains independent and can support directional options or a stock alternative. Both branches use the same economic, risk and evidence standards. The first implementation targets one bounded long-volatility hypothesis; additional structures, including short options, need their own specifications and lifecycle support.

The financial objective is positive expected value and account growth after costs, with controlled drawdown, tail loss, concentration, capacity, and execution risk. Profit is never guaranteed. A completed download or functioning dashboard is engineering progress, not a profitable strategy.

Product engineering and strategy research proceed together. A negative research result does not block useful product work. A working product does not validate its baseline strategies. Avoid restarting the architecture when a research branch fails.

## Current status

| Area | Repository / previously recorded workstation state | Remaining limitation |
| --- | --- | --- |
| Stock source | Alpaca SIP V2: 67,480 complete units, 5,302 daily / 62,178 minute; 3,897,688,734 canonical rows and 1,757,288 quarantined rows; acquisition/acceptance/research metadata found locally on 2026-10-12 | Inventory reads headers only; retain existing acceptance receipts for source identity and cutoff before a dependent raw-data replay |
| Daily/minute semantics | V2 research preparation and B34 intraday/session audits accepted | Preserve missing bars, exact source identity, and corporate-action boundaries |
| News | 141 monthly partitions, 2,211,606 records; source-integrity V2 accepted | No validated news-derived alpha; sentiment and attribution need PIT-safe evaluation |
| Strategy laboratory | 21 economic families / 28 routes; 54,618,427 standalone DEVELOPMENT records; conditioning v1 completed | Aggregate conditioning/account evidence does not establish robust profitable strategies |
| Options-native research | SPY pilot, CALL/PUT plan, synthetic variance/geometry/exits/two-leg account and economic-return arithmetic implemented; 21-close/22-clock, original action-page and 20-return conditional variance reports inspected | No historical performance run; full 411-case stock-minute coverage preview prepared, while PIT economic returns, publication/revision clocks, option quotes/costs and prospective qualification remain open |
| Dynamic exits | Prior-fold discrete Dynamic Exit V1 and continuous distribution-based V2 tested | V1 negative later results; V2 saturated near 3%/5%; neither is an accepted final exit policy |
| Account lifecycle | Recurrent reservations, entries, marks, closes, re-entry, clocks, checkpoints, transactions and observability; synthetic retry/partial-exit mechanics and read-only mark coverage preview implemented | Accepted source integration, historical settlement and missing-mark source resolution remain open; recurrent V1 closes still require whole positions |
| MarketData options | Candidate raw chains, exact-series caches, receipts, source reconciliation, and EOD account diagnostics exist | EOD timing differs from the intended intraday strategy; unresolved positions prevent a valid full account return |
| Stock exit clock | 9,667/9,974 pre-2026 cases expressible after 09:35; 304 already finished; three trigger gaps | Minute bars cannot establish within-minute tick ordering |
| Decision spot | 9,654/9,667 causal 09:35 spots; 13 missing-minute cases; 9,455 unique surfaces | Old 18,921 open-selected single-contract requests are superseded; do not acquire them |
| ThetaData | v3 client, source/enrichment plans, quote/OI qualification, candidate cache, and zero-data Terminal preflight implemented | No accepted provider run or full acquisition recorded |
| Operator UI | Phase19 local control plane, replay drilldowns, A34.5 read-only paper observability, recurrent lifecycle projections | Integrated operator product and A35 PAPER broker mutation unfinished |
| Trading authority | Research/baseline engineering; historical supported modern alpha remains zero | No strategy promotion, qualifying PAPER, LIVE, or automatic broker failover |

File presence proves implementation, not workstation completion. Consult the evidence register for scientific results and actual manifests for physical cache state.

## System map and active components

The common engine follows `PIT source -> independent stock and options-native research -> evidence/forecast -> economic construction or NO TRADE -> risk/account admission -> execution/lifecycle -> outcomes/performance -> operator interface`.

Use two levels with one versioned strategy specification: fast feature/diagnostic screening, then exact event-driven account replay for survivors. Fast approximations remain labeled and cannot manufacture fills or portfolio returns. Source validation and trade eligibility are separate: later source knowledge cannot remove an earlier bad trade. Multi-leg construction and paired execution are new capabilities; the accepted directional single-leg economics contract remains intact.

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
| 1 | Options-native pilot specification and data design — implemented | One SPY long-straddle variant, prior-only variance feature, dynamic management rule and 411 weekly CALL/PUT discovery surfaces, independently registered from stock signals | Code specification is not performance evidence; no operator run needed to repeat fixture checks |
| 2 | Pilot input and cost qualification — original action proof, January conditional variance and 411-week physical minute coverage completed | Preserve pinned 407/411 physically complete weekly windows; index archival SPY actions across all years before pursuing separately proven historical PIT disclosures | Next bounded one-ledger archival action index below; source snapshots and recorded dates do not establish historical availability |
| 3 | Pilot pair construction and execution mechanics — synthetic path implemented | Exact common-strike/expiry selection, daily exit requests, explicit legging, reservations, residual marks and sale-settlement cash reconcile | Fixtures establish mechanics; accepted execution, deliverables, exercise and settlement adapters remain downstream; frozen single-leg engines unchanged |
| 4 | ThetaData source acceptance when active | Preserve existing 09:35 qualifier; separately qualify native 10:00 CALL/PUT shape and earlier years with bounded receipts/repeatability | Subscription and Terminal; no acquisition or subscription activation authorized by the new planner |
| 5 | Bounded candidate acquisition and enrichment | Reuse/acquire the separate native discovery plan and frozen 9,455 stock-to-CALL surfaces; exact OI/IV/entry/management demand follows causal selection | Accepted source/storage, PIT dividends/rates and model units; no broad market-wide tick campaign |
| 6 | Fast DEVELOPMENT research | Register the matching trial before outcomes, evaluate one frozen variant, report all decisions/coverage and reject unsupported hypotheses cheaply | Accepted native inputs/adapters and experiment budget; 2018-2025 is DEVELOPMENT, not fresh qualification |
| 7 | Exact standalone account and window evaluation | Replay surviving specifications with fills, capital competition and complete valuation; rolling 5/21/252-session and calendar week/month/year reports | Qualified costs, source clocks, multi-leg lifecycle and marks; losing windows remain visible |
| 8 | Independent comparison and portfolio assembly | Hand-audit fixture cash/order differences against a separately configured engine such as LEAN; combine justified survivors and test common capital/risk | Same inputs, explicit model differences, complete trial accounting and new independent/prospective evidence |
| 9 | Operator PAPER and production | Integrated engine/UI, accepted Webull PAPER path, reconciliation/observability, operational state/recovery, authenticated deployment | Explicit authority packages; A35/A37 |
| 10 | Qualifying PAPER and controlled LIVE | New prospective evidence, risk/execution acceptance, explicit promotion/rollback | A38, then Phase39; currently blocked |

Orders 2-3 can advance offline before the subscription. Completed cache inventory, selected-stock review and ten-position exit audit remain recorded below; no repeat run is needed. Existing full-stock reporting remains blocked by one changed aggregate. Missing option access must not block useful stock/product work, and closed negative experiments remain closed.

### Options-native pilot and data contract

The source of truth is [the pilot contract](../packages/strategies/options_native_pilot_v1_contract.py); [the planner](../scripts/plan_options_native_pilot_v1.py) builds deterministic demand with no provider/broker calls, source scans or outcomes. The specification fingerprint is `e3ad55ad153ca61432bfde65aa0b5c54004766866a2919a567b6b5ade551efca`. This is a newly specified research hypothesis, with no profitable result or trading authority.

| Item | Frozen pilot choice |
| --- | --- |
| Universe and clock | SPY, first XNYS session of each ISO week; observations through 10:00 ET, qualified delivery/computation through 10:01, then order eligibility |
| Expression | Buy one CALL and one PUT at the same strike/expiration; earliest 30-45 DTE expiry, nearest common strike to causal spot, lower-strike tie; selected-pair failure abstains without fallback |
| Feature | Twenty prior completed economic log returns; constant calendar-time variance rate projected to the same explicit model maturity as the pair's American-model IV |
| Entry hypothesis | Forecast total variance strictly greater than the mean of CALL/PUT implied total variances; this comparison is neither a straddle-price model nor an expected-dollar-profit forecast |
| Management | Recheck the original pair daily at 10:00; request exit when the forecast gap closes, after five subsequent sessions, or at <=14 calendar DTE; execution starts at 10:01 and can fail |
| Capital | Research cash $100,000, one open pair, one pair per entry; debit plus fee reserves <=5% of available cash; no assumed cash interest |
| Scope/budget | 2018-2025 DEVELOPMENT, including 2020; one strategy variant, qualified primary and predeclared spread/latency stress, NO TRADE control |

The forecast assumes a constant variance rate, including weekends; it is a deliberately simple fixed baseline. IV and forecast share one maturity and 365-day units, while the position may exit much earlier. Actual premium repricing, theta, changing delta/vega, spreads and costs must therefore be evaluated from qualified quotes, not inferred from the variance gap. Model-based attribution stays separate from observed economics. Dynamic management here means a changing observable thesis, not tuned stock-percentage stop/target points.

The plan contains 418 weekly clocks, with seven late-2025 entries excluded by a fixed 45-calendar-day buffer: 411 independent CALL/PUT snapshots. Initial qualification design uses 24 quote anchors plus a repeat, within a 64-request total design cap including bounded OI/model checks; all execution permissions remain false. Requests use a small provider strike band and max DTE 45; provider 0-29 DTE overfetch is ineligible. OI and model enrichment follow geometric pair selection. Entry, daily management and exit histories remain exact-contract downstream demand, not already acquired coverage. Both-rights/earlier-year qualification is separate from the existing 9,455 09:35 CALL plan.

The synthetic feature function rejects future/late/stale inputs, incomplete prior windows, unqualified corporate-action/rate/dividend inputs and incompatible IV models. Its PASS proves arithmetic for invented fixtures only. The data contract distinguishes observation, publication/availability, decision readiness and offline calculation times. Unknown publication timing needs a separately qualified bounded clock/latency model with its assumptions retained; it cannot silently become observed availability. The stock calendar does not qualify option trading or exercise hours.

Historical runs remain blocked until source/adapters, broker costs and multi-leg execution/lifecycle qualify. Two snapshots do not prove an atomic pair fill, and partial legs retain actual exposure. `specification_trial_draft` uses the existing hash-chained `StrategyTrialLedger`; no workstation ledger was appended here. Before any later historical outcome read, append the matching draft and bind the run/input identities. Material rule/universe/clock changes consume a new registered variant; additional variants require a separately declared budget. Keep all negative results, abstentions and coverage gaps. Assess every eligible rolling window and calendar period, including low-count/unresolved windows; positive results in every window are not an acceptance requirement. Regime restrictions require independent later verification. The consumed 2026 holdout cannot qualify this pilot; prospective qualification needs its own interval and authority.

The planner can be previewed without saving; `--output` optionally saves a deterministic review copy and refuses conflicting files. Another workstation command is unnecessary for this specification. The frozen pilot fingerprint and one-variant budget remain unchanged by the following engineering work.

### Options-native pair mechanics and next workstation input

[Pair construction and management](../packages/strategies/options_native_pair_v1.py) accept invented typed fixtures only. Selection fixes the earliest 30-45 DTE expiry and nearest common strike before inspecting selected-leg liquidity or availability; failure abstains without another pair. The selected pair requires qualified original identities/deliverables, spot, quote/OI states and clocks, spread and displayed size. Zero reported volume alone does not reject a quote. Daily fixture reviews request an exit when the variance gap is nonpositive, five subsequent XNYS sessions have elapsed, or DTE is at most 14. Missing/unqualified variance cannot establish a thesis exit but never disables time guards. These are requests at 10:01, not fills or capital releases.

The separate [synthetic pair coordinator](../packages/simulation/options_native_pair_account_v1.py) reuses the existing cent cash convention without changing recurrent V1 or single-leg contracts. It reserves both original entry limits and explicit entry/exit fees, enforces one open pair and the frozen 5% cap, and processes each invented fill at its availability clock. A lone filled leg or residual exit remains exposure. Only a qualified final zero-fill cancellation releases an unfilled leg's reservation; a timeout does not. Sale receipts realize only that leg's basis/P&L and create unsettled proceeds. An explicit, exact sale-settlement receipt transfers those proceeds to spendable cash; no historical settlement date or intrinsic exercise is assumed. Missing current marks, pending execution or unresolved expiry leave equity unknown. All fees are explicit fixture assumptions, not a broker schedule. This is a bounded in-memory fixture coordinator, not a historical or durable production account adapter.

The operator completed [the pilot raw-input packet](../scripts/inspect_options_native_pilot_inputs_v1.py) on 2026-10-16: all 21 requested SPY closes were present for 2019-12-04 through 2020-01-03, before the fixed `2020-01-06T15:00:00Z` anchor. The uploaded `92c4d71997ec3225.json` independently reconciles its complete signature, session/calendar window and two unit bindings. Report fingerprint: `92c4d71997ec3225d5040f00375fc4ad66d654be6ce4a6cb81136a87d75374dc`; raw-file SHA-256: `e02946c3390626bf8f1b1aee13081febfbc00ae100c8f1a8bf272e868a444459`; native acceptance: `6e3e78f181183f0ee92517fd6fabf2f0bd5b33c1a6eea14a87f0894ce2bd6664`. This verifies the uploaded packet and recorded source bindings; the underlying workstation files were not opened in this chat. No repeat daily scan is needed. Economic-return adjustments and historical availability remain unqualified.

The next [cached stock-input review](../scripts/review_options_native_stock_inputs_v1.py) pins those original bytes and follows only known V2 paths. It selects exactly the SPY December 2019 and January 2020 minute units from the frozen plan, verifies their accepted inventory membership and complete checkpoint/canonical hashes, and applies a SQL predicate for 22 observations: 21 final regular-session minute bars plus the 09:59-10:00 ET bar on the anchor date. It handles the December 24 early close and never selects the 10:00-starting bar. Missing exact bars stay missing; daily data or earlier minutes are not substitutes. Daily/minute differences are retained diagnostics, not proof of an error or permission to replace a source; [Alpaca's bar methodology](https://docs.alpaca.markets/us/docs/market-data-faq) applies different eligible-trade rules to minute and daily aggregation.

The same command hashes the accepted source snapshot and its original native-action/raw-bundle files, streams the bounded native ledger, and retains SPY effective-date candidates and undated action records with their original payloads. Individual raw pages are not reparsed; page hashes are labeled as manifest-recorded. Empty selection is not qualified no-action coverage, revisions are not silently deduplicated, and declaration/ex/record/payment dates never become availability clocks. [Alpaca's corporate-action endpoint](https://docs.alpaca.markets/us/reference/corporateactions-1) filters by process date and gives no creation-time guarantee. A later source capture cannot prove what was known at a 2020 decision. A separately justified and labeled bounded availability/revision model remains permitted by the pilot contract; none is accepted by this command.

Resource bounds: two sequential minute units at 256 MiB each, 4 MiB per JSON, 128 MiB inventory, 64/256 MiB compressed/expanded plan, 128/512 MiB compressed/expanded action files, 1 MiB lines and bounded row/output counts. DuckDB uses two threads and 512 MiB; a heartbeat reports active checks every 20 seconds. There are zero daily-unit rereads, provider/broker requests, option histories, outcome calculations or simulations. Output remains diagnostic, with unknown historical availability and no pilot acceptance.

The completed 2026-10-16 workstation command was `scripts/review_options_native_stock_inputs_v1.py --save-report`; do **not** repeat that successful stock-input scan. The next command is the original-action proof described below.

The report saves under `data/research/options_native_stock_input_review_v1`, honors the research-evidence storage binding, and refuses conflicting output. The operator completed this follow-up on 2026-10-16. The uploaded `9caee69b5d0fc180.json` records 22/22 exact minute observations (21 prior regular closes plus the 2020-01-06 09:59–10:00 ET SPY spot at 321.60), no missing clock and one SPY dividend candidate with ex-date 2019-12-20 and rate 1.569992 per share. Its fingerprint is `9caee69b5d0fc18075451f7b4b8c46ec3c8db817d4b0b0d3ed311bf9712748e7`. These are verified retained report facts, not as-of historical publication proof, accepted dividend treatment or an executable option input. No repeat stock scan is needed. Missing/changed/oversized artifacts block without rebuild or fallback.

### Options-native original corporate-action page proof — completed local gate

[The bounded source-proof module](../packages/data/options_native_spy_action_source_proof_v1.py) and [operator command](../scripts/prove_options_native_spy_actions_v1.py) use the pinned 2026-10-16 cached-stock review, original action manifest/source snapshot, full native-action ledger and original concatenated gzip-page bundle. Each decompressed original source page must match its manifest-recorded SHA-256/length; every extracted original record must match the corresponding native ledger record in exact page/type/index order. The old December–January SPY selection must reproduce the verified prior report byte-for-byte at the semantic-record level. The separate expanded action window is 2019-10-01 through 2020-03-31 so dividend, split, identity and undated candidates remain visible for the 2020 pilot. Revised candidate records are retained separately rather than cherry-picked or deduplicated. Blank selection is not qualified no-action coverage.

The source proof does not reinterpret process/ex/record/payment dates as announcement or publication clocks, does not correct bar prices, and does not create economic-return, volatility, option-model, historical trade or PAPER/LIVE authority. Historical action availability, source revisions, corporate-action coverage and a justified as-of economic adjustment are still required. The pilot strategy/version and prior close review are immutable. No option/market/stock-outcome/provider reads are performed.

Only two source objects are streamed: the accepted native-action ledger and original compressed-page bundle. Both compressed files are hash-verified within 128 MiB each; concatenated gzip members have 32 MiB per-page and 512 MiB aggregate expansion limits, with an exact ledger equality/count check and a 20-second heartbeat. Original page hashes are **verified** here, unlike the earlier cached-stock summary which only recorded them. Existing mismatched reports are not overwritten.

The 2026-10-16 operator source proof completed: original pages 379/379; reconciled action records 378,362. Uploaded report `b0cbad9dca14d6ce.json` has fingerprint `b0cbad9dca14d6ce0221cd684473fbc3190e17248c42b0b0909c0854a9f8d929` and raw SHA-256 `3880427d8300d814cebd7ede1c6a2b6dc72c51d8a50fc686a75932081566b237`. The bounded SPY candidates were cash dividends ex-2019-12-20 at 1.569992/share and ex-2020-03-20 at 1.405559/share; only the first lies inside the frozen pilot prior window. The original stock and action proof scans are complete, and historical publication/coverage remain unqualified.

### Conditional SPY prior variance diagnostic

The [offline diagnostic](../packages/data/options_native_spy_prior_variance_sensitivity_v1.py) and [script](../scripts/inspect_options_native_spy_prior_variance_v1.py) read only the two pinned JSON reports, without stock/option/source-bar scans or provider requests. They compare 20 prior log-price returns against a one-dividend hypothetical return series using the frozen calendar-time squared-return variance convention. The March 2020 distribution is excluded. Preliminary independently calculated annualized values were about 7.34% for raw closing-minute price returns versus 7.54% for a conditional ex-dividend adjustment. These are diagnostics, **not** historically qualified economic returns, a strategy forecast, or alpha evidence. Unknown publication/revision clocks and complete adjustment coverage remain blocking; `economic_log_returns` and `forecast_total_variance` are null. The original strategy specification and option plan do not change.

The operator completed the prior-variance sensitivity on 2026-10-16. The verified uploaded `0962d8ff207f29ea.json` has file SHA-256 `574d57fb0d19e60486e1b3defbf50ac09f677d19fd37b4ef716e6a73607b0ccc` and report fingerprint `0962d8ff207f29ea492408e711d714726d8dcaada55c6e50942b6c646007e378`. It reconciles 21 closes, 20 dated return intervals, 2,592,000 elapsed calendar seconds and two conditional annual volatilities: 0.07336247724542309 (raw) versus 0.07540933714681941 (one-dividend scenario). These numbers are **unqualified feature arithmetic**, not observations of contemporaneous disclosure or predictive performance. March 2020 remains future to the January 2020 anchor.

### Multi-year SPY exact-minute coverage — next bounded workstation gate

[The development coverage module](../packages/data/options_native_spy_development_clock_coverage_v1.py) and [runner](../scripts/review_options_native_spy_development_clocks_v1.py) replace repeated one-week raw-stock lookups with one globally deduplicated query plan over all **411** frozen 2018–2025 options-native weekly decision clocks. Each case requires its 21 exact prior regular close-minute starts plus the exact 09:59–10:00 ET decision spot, including XNYS early closes and DST changes. One accepted 1-minute SPY unit per needed historical year/month is selected from the entire immutable, hash-verified native acquisition plan and accepted inventory; only required timestamps, columns, symbol and units are scanned. No data from 2026 or the consumed protected interval is eligible. No daily unit, option chain, news, broker, provider, market outcome or corporate-action source is opened.

The 2020-01-06 group must exactly match the earlier 22-clock raw SPY source report, including canonical unit IDs and price values, or the entire run blocks. Missing monthly units or exact bars remain explicit gaps, not a substituted price or automatic provider demand. Source file/hash/provenance drift blocks rather than being treated as absent market data. The reader runs two DuckDB threads with a 512 MiB query limit, bounds source Parquet units to 256 MiB each, reads at most 125 monthly units and reports progress at least every 20 seconds. A content-fingerprinted report retains case-by-case physical coverage and source identities; incomplete/source-unknown cases never qualify historical economic returns or forecasts.

The operator completed `scripts/review_options_native_spy_development_clocks_v1.py --save-report` on 2026-10-16. Do not rerun the 97-month scan. Return the complete terminal output and JSON report under `data/research/options_native_spy_development_clock_coverage_v1` (research-evidence D: binding). This is a larger physical coverage pass through historical cached minute units, not another run of the January pilot. It is **zero paid API calls** and gives a multi-year data-coverage baseline before ThetaData qualification. Historical action/quote publication and economic source coverage remain separate gates. The frozen strategy, 411 quote-surface plan and trial budget are unchanged.

The uploaded `bf18bb1a4c7e38f0.json` was independently inspected and its canonical fingerprint rechecked. Raw SHA-256: `962852e3fc3739494b9758a8916ebe9ba0dfb8cdcadc71a651fa254e99455191`; report fingerprint: `bf18bb1a4c7e38f0dad91e1afaf3dd93d3dbdea9692f9e1345cf3b25efb56c2f`. All 97 accepted monthly source units were checked in one 15-second workstation run. Exactly 2,406/2,407 unique SPY minute clocks are present. The **one** missing observation is the normal 15:59–16:00 ET closing bar for SPY on **2019-08-12**, starting `2019-08-12T19:59:00+00:00`. Its source unit is `d1fee36b2b31db90fc3f268bba82742b970d8406260c7af60c8179d84d7b037e`; the originally accepted canonical file SHA-256 is `88e65db9f050db7885e225c0f559f94fdee6fca8f3101898a0219650c89cbd18`. Because prior 21-session lookbacks overlap, the gap affects the **2019-08-19**, **2019-08-26**, **2019-09-03**, and **2019-09-09** decisions, each with 21/22 minute observations. All other **407/411** weekly cases are physically complete. These are NOT 407 historically accepted signals: the 2026 archive lacks contemporaneous bar-publication and economic-action qualifications. No missing-bar substitute or paid acquisition is authorized. The 2026 master holdout was not accessed.

### Full-period SPY archival action inventory — completed 2026-10-16

[The bounded archive index](../packages/data/options_native_spy_archival_action_timeline_v1.py) and [script](../scripts/index_options_native_spy_archival_actions_v1.py) extend the 2020 action-source proof across the entire frozen 2018–2025 weekly pilot. They pin the complete 411-week price-coverage report by raw SHA-256 and content fingerprint, and similarly pin the previously verified 379-page original corporate-action source proof. The command verifies the source manifest and hash of the accepted `native_actions.jsonl.gz`, streams precisely the 378,362 existing normalized records ONCE, and selects SPY archival event candidates from 2017-11-01 through 2025-12-23. The originally verified 379 raw pages are **not reopened**. Candidate effective/execution/ex-dates, undated records and all action types remain separately visible. They are indexed only against the **20 return-ending sessions** of each frozen 21-close input window; the first prior close is only the baseline. The four 2019 gap weeks remain physically incomplete.

This work identifies when available archive records *purport* to have economic effects. It does **not** convert archival event dates, vendor process times or the 2026 snapshot into contemporary 2018–2025 publication/revision clocks. Absence of a retained dated SPY record is **not** qualified evidence of zero cash or no splits; undated or identity actions cannot be assumed harmless. No historical total returns, forecast IV comparisons, simulations, trades or promotion are authorized. Later historical availability/coverage evidence must be obtained and qualified independently; the frozen options-native hypothesis and single strategy budget remain unchanged.

Once exact-head Linux/Windows CI is green and the PR is merged, run the following from the existing Windows `main` checkout. Return full terminal output **and** the small report named by the `saved report` line:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed.' }
    & .\.venv\Scripts\python.exe scripts\index_options_native_spy_archival_actions_v1.py --save-report
    if ($LASTEXITCODE -ne 0) { throw 'SPY archival corporate-action index blocked; paste output.' }
}
```

The JSON is stored under `data/research/options_native_spy_archival_action_timeline_v1` on the established research-evidence D: binding. Provider, broker, raw SPY price, option, outcome and 2026 protected data reads remain **zero**.

The operator successfully completed this archival pass and uploaded `6aaf6b09006443d0.json` on **2026-10-16**. Independently verified raw SHA-256 is `0010728cd99394834434555042ead745e4d12420050dcaa81396e277baa7546d`; canonical report fingerprint is `6aaf6b09006443d01dceb38b67c4e25ad496db165964411cddafebdc13d2a7a6`. The source lists 32 cash-dividend records, no other types, zero undated SPY selections, 144 weekly decisions with at least one archived ex-date in the fixed prior return window and **267 archive-empty windows**. None is an accepted no-action window. The original 378,362-row ledger and 379 original pages have already been fully inspected; **do not run this command again** unless explicitly investigating identity drift.

### Source completeness failure: independently documented omitted 2018 SPY dividend

A retrospective cross-source check on 2026-10-16 found that this immutable Alpaca corporate-action archive omits the SPY cash dividend with U.S. ex-date **2018-06-15**, USD **1.245568** per share. Its existence and approximately USD 1.24557 distribution are corroborated by [State Street's related SPY/CDI distribution-history table](https://www.ssga.com/au/en_gb/institutional/etfs/state-street-spdr-sp-500-etf-spy) and the US ex-date/amount by [U.S. SPY dividend history](https://dividendhistory.org/payout/SPY/) and [an independent SPY dividend table](https://www.slickcharts.com/symbol/SPY/dividend). The Australian CDI table has **different distribution-calendar semantics**, so it is NOT evidence of the US SPY ex-date or historical announcement clock by itself. Sources are contemporary retrospective pages, not timestamped immutable 2018 announcements.

The **2018-06-18, 2018-06-25, 2018-07-02, 2018-07-09 and 2018-07-16** weekly prior windows contain this ex-date but show *zero* archived dividend candidates. All five have physically complete raw SPY 21-close/decision-spot windows. Thus historical action completeness fails independently of the separate four incomplete-price weeks in August/September 2019. The omission proves the accepted archive is **incomplete**, not which acquisition stage omitted the record, and does not establish that other missing events exist or don't exist. Existing action-source receipts are preserved and must not be rewritten to fabricate the missing event.

[The offline negative-control module](../packages/data/options_native_spy_dividend_negative_control_v1.py) and [script](../scripts/review_options_native_spy_dividend_negative_control_v1.py) pin the completed 411-week minute-coverage JSON and the newly uploaded archival-action JSON by both file SHA and canonical fingerprint. Without reopening any raw records, they derive exactly which fixed prior 20 return-ending clocks overlap the externally witnessed ex-date. The result explicitly records 32 archived cash dividends, 267 archive-empty weeks and five directly disproven 'no action' interpretations. No dividends are backfilled, no historical publication clock is fabricated, and no forecast or trade is authorized. Candidate source coverage, announcement/revision times, split/no-split coverage, adjusted economic returns and option inputs remain **unqualified**. The historical hypothesis, trial budget, source archive and 2026 holdout stay frozen.

Once **exact-head Linux and Windows CI are green and PR merged**, run only the new bounded source discrepancy certificate:

```powershell
& {
    $ErrorActionPreference = 'Stop'
    if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed.' }
    & .\.venv\Scripts\python.exe scripts\review_options_native_spy_dividend_negative_control_v1.py --save-report
    if ($LASTEXITCODE -ne 0) { throw 'SPY archive negative control blocked; paste output.' }
}
```

This reads only the two completed small pinned JSON reports. The JSON report goes to `data/research/options_native_spy_dividend_negative_control_v1` on D:; user returns only this command output and saved JSON. No provider/broker/source-bar/option/outcome calls or simulation.

**Follow-up priority:** obtain a complete, traceable sponsor/authoritative historical distribution series, reconcile ex-dates and event cash values across all frozen windows, and separately establish historical announcement/revision availability. The present witness proves incompleteness but is not, by itself, a substitute accepted event series. Avoid dozens of small pilots or repeated native archive scans.





When this package is merged, run `python scripts/inspect_options_native_spy_prior_variance_v1.py --save-report` once after updating the Windows `main` checkout. It stores a conflict-safe report under `data/research/options_native_spy_prior_variance_sensitivity_v1` through the research-evidence storage binding. Return its terminal output and saved JSON. No repeat raw source audit is needed.

[Economic-return fixture arithmetic](../packages/strategies/options_native_economic_returns_v1.py) prepares the next adapter without inventing source facts. For one share at the prior close, it computes `ln((split_new_per_old * current_raw_close + ex_date_cash_per_original_share) / prior_raw_close)` using a 34-digit decimal context and 24-decimal-place log returns compatible with the existing variance-input contract. Cash is an analytical ex-date entitlement per original share, not a payment-date account credit. Explicit split/no-split and cash/no-cash values, complete action coverage and publication/revision qualification are required. Unknowns, noncash/identity actions or ambiguous share basis abstain; one bad interval invalidates the fixed twenty-return window. It emits typed fixture returns for the existing variance screen, grants no historical adapter authority and changes neither the frozen strategy nor its budget. [S&P's total-return methodology](https://www.spglobal.com/spdji/en/methodology/article/index-mathematics-methodology/) describes the distinction between price movement and dividend reinvestment; this fixture convention is separately labeled from account cash settlement and option pricing.

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

`SyntheticOptionExitFillV1` adds a separate opt-in path through `ReplayLeg.exit_fill_fixtures`: at most 64 explicit invented option executions per leg and 100,000 per chosen-mode account. Each fixture binds a unique fill ID, exact contract, quantity, execution/availability clocks, final execution price and source/clock assumptions. It replaces the fixed exit or retry plan; it does not derive fills from quotes, displayed size or reported volume. Availability controls when cash can fund later entries, without backdating earlier decisions. Final execution prices include execution slippage; entry slippage and per-contract policy exit fees still apply. This extension creates no new broker fee schedule.

Each accepted slice realizes its own P&L, removes only its proportional entry cost and exit-fee reserve, and keeps the residual position/slot open until fully closed. Duplicate fills, overselling and fills after complete closure fail; unqualified reached fixtures record zero cash movement. Missing marks and unresolved expiration keep residual equity unknown. A fixture closing 11 of 35 contracts leaves 24 open; this tests mechanics and does not execute any audited historical quote. Complete legacy STOCK/CALL/PUT/ABSTAIN fixture fingerprints remain unchanged. The frozen recurrent V1 entry/exit contracts and closed historical V2 are unchanged; this extension is not a recurrent partial-close mutation or a durable account checkpoint.

The recurrent coordinator's `mark_coverage_preview` exposes known position values and explicit missing/stale/clock-mismatch reasons without changing its account, ledger, revision or published valuation. Incomplete coverage leaves total equity and aggregate unrealized P&L unknown; cash, reserves and entry book values remain separately labeled. Provenance/identity errors, duplicate marks and extra positions still fail closed. Complete coverage delegates to the existing strict valuation builder. A fresh zero option bid can be a known valuation mark; it does not force an exit or settlement. This preview is an engine-owned read-only dictionary, not an accepted partial valuation state or a new risk/account mutation input.

### Retained option account review — completed workstation gate

`scripts/review_retained_option_account_v1.py --save-report` reads only the original V2 scenario `multiyear_continuous_dynamic_exit_v2_option_scenario_03406fdf1def8233.json` and strict account `multiyear_continuous_dynamic_exit_v2_option_replay_b525b49fabd0aead.json`. Each read is bounded at 64 MiB. The legacy filenames retain 16-character identities: the reader checks those original run prefixes, the complete reports' existing self-signatures, mutual scenario linkage, frozen policy/costs and recorded populations. It captures complete fingerprints and raw-file hashes in the new review. This is retained-result integrity and accounting reconciliation, not new source acceptance. It never chooses a newer run or follows paths stored in a report.

The operator completed the review on 2026-10-14 (America/New_York), reconciling 84 admitted / 74 completed / ten unresolved positions, $24,997.70 cash and -$33,365.40 modeled realized P&L. All ten unresolved positions opened in 2021 and carry `STRATEGY_EXIT_SESSION_OPTION_LIQUIDITY_GAP`; this is the retained source classification, not proof of permanent market illiquidity. Their 226 contracts retain $41,636.90 committed entry cash including fees and $146.90 reserved exit fees, leaving $24,850.80 cash after that reserve. Equity, total return and terminal valuation clock remain unknown. The saved review is `data/research/retained_option_account_review_v1/20261015T035701371767Z_98c60bf4.json`; its fingerprint and the complete original report identities are in the evidence register. No simulation, raw quote/bar scan, provider request, settlement, retry policy or capital release was performed. Another review run is unnecessary for this result.

Evidence demand includes exact deliverable/corporate-action lineage, original exit-clock observation or explicit absence, an explicit terminal account clock, exercise/expiration outcome, historical settlement cash/share movements and marks for any resulting positions. Exercise can change cash and share holdings, and adjustments can change deliverables; see [OCC equity options](https://www.theocc.com/clearance-and-settlement/clearing/equity-options-product-specifications) and [OIC contract adjustments](https://www.optionseducation.org/referencelibrary/faq/splits-mergers-spinoffs-bankruptcies). Settlement timing must use the historical effective rules, including the [2024 T+1 transition memo](https://infomemo.theocc.com/infomemos?number=54436). The reader does not infer those outcomes from expiration dates, intrinsic value, missing bids or a nominal 100-share model. The negative V2 branch remains closed; this demand cannot silently revise its outcomes or promote a new strategy.

### Retained exact-exit source audit — completed workstation gate

The uploaded 2026-10-15 review copy matches its complete fingerprint and original file bytes. Its ten exact source identities allow `scripts/audit_retained_option_exit_sources_v1.py --save-report` to read only that pinned review (256 KiB bound), the original V2 scenario (64 MiB), and at most ten named demand-cache quote histories (4 MiB each) with their original signed receipts/attempts (64 KiB each). Full report/body hashes, request/query identities, original case membership and source projections are verified. Missing triplets remain explicit; altered, linked, oversized or inconsistent inputs block. No broad manifest search, stock scan, new quote request or later-quote substitution occurs.

The operator completed the audit on 2026-10-15 (America/New_York). Its output reports all ten original exact sources verified, no missing sources or classification disagreements, and all ten snapshots at their recorded exit clocks. Nine exits failed only the legacy positive-reported-volume requirement. CME failed only the fixed 16:00 ET requirement: its `2021-11-26T18:00:00+00:00` snapshot matches the recorded early close. Four positions exceeded reported bid size: OTTR 35 contracts / size 11, FOX 74 / 6, REYN 24 / 5, CME 13 / 10. These observations separate quote availability, clock rejection and displayed capacity; a zero volume field alone does not establish absence of a quoted bid.

The saved report is `data/research/retained_option_exit_source_audit_v1/20261016T021014995089Z_f361ff14.json`, with reported fingerprint `81ef6487f0f0cd99431d33136a14c97294c6c704b270b88a21e75c459b0427f7`. This update records operator output; the saved JSON has not been independently inspected in this chat. No repeat run is needed. Snapshots do not prove publication availability, option trading/exercise hours or fills; reported size does not guarantee an execution quantity. Original exits, fees, cash, settlement and unknown equity remain intact, and V2 remains closed. The next historical dependencies are qualified execution/source clocks, deliverable/adjustment lineage, exercise/settlement movements and surviving-position marks. Synthetic accounting can progress without inventing those facts.

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
