# Accepted stock/news to PIT options quote bridge (2026-09-27)

## What is implemented

The historical stock/news/option lab is **not yet an accurate five-year account-level options simulator**. This stage closes the disconnection between accepted stock/native-open/news cases and existing exact option quote acquisition. It is an offline D:-bound evidence compiler, not another chain-audit campaign and not a simulated trade.

Source inputs: original signed 14,902 accepted stock/news cases, independently verified native raw next-day stock OPEN, original 2022/2025 source crosswalk, 7,646 physical-source demand and accepted original global cache overlap. The source/2022 plan identities are fixed by the accepted research receipts. The compiler:

- Retains all original case IDs and decision times. No unseen 2026 historical stock signals or 2026 protected outcome reads.
- Reuses the original 2022 structural CALL selected symbol **only if it is in the immutable 6,398-symbol original quote-plan index**; no 2022 raw quote body is reread at selection. Actual quote use later independently verifies the original exact receipt/body.
- Selects nearest-to-original-raw-open CALL and/or PUT from verified **previous-session** chain raw bodies, tie-breaking to the out-of-the-money strike. No same-day EOD quote, future volume, OI, favorable outcome or later Greeks is used for contract selection. Original 2025 pilot CALL pointers are checked against the original complete chain SHA/body.
- Reuses any newly acquired exact original local source and the 71 previously verified complete global overlaps, including the accepted original query strike window. An original attempted-but-uncertain query does not fall through to another provider request. Original exact-query 404 remains an exact-query gap, not absence of any option.
- Reports unavailable older-2021 source, expired/out-of-policy, no chosen right, missing chain and 17 protected future entry deferrals as explicit gaps, not synthetic fills.
- Writes one immutable full-case/right coverage selection and deduplicated exact OCC/from/to quote demand, both under the D:-bound options manifests directory. Default is both rights, but the operator can plan only CALL or only PUT. This is demand, not a paid request.
- Reuses the existing full-series quote cache executor and its SHA-bound local bodies for future capped paid calls. The initial source bridge makes **zero** API calls. C: continues to own core stock data/compute; D: owns downloaded option/news evidence and derivatives.

## One free operator command

From ATLAS root, after merge:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed.' }; & .\.venv\Scripts\python.exe scripts\prepare_multiyear_option_quote_sources_v1.py --rights both; if ($LASTEXITCODE -ne 0) { throw 'PIT quote-source bridge stopped; paste complete output.' } }
~~~

The command prints its source selection path, quote-plan path, original 14,902-case denominator, missing statuses, selected CALL/PUT identities, exact quote series to acquire, and D: free space. **No provider token or payment approval required.** The generated exact quote-plan JSON may be used as --plan input to the existing run_multiyear_demand_quote_cache_v1.py, initially without paid flags for an offline reuse/availability census. Do not run overlapping provider jobs; historical quote acquisition requires independent authorization and a current observed credit budget. There were only 487 credits in the last observed live source run.

## What remains before a true option-trade backtest

1. Fill missing exact series from the frozen plan with bounded provider calls and persistence; use original 2022 full 6,398 CALL histories unchanged. A 1,114-credit chain campaign acquired 1,116 complete chains and 63 exact no-data, but did **not** download full selected OCC series.
2. Normalize original two-sided historical EOD option observations alongside same-session stock and conservative PIT news into a common-clock source adapter; never turn a later EOD row into original 09:35 fill. The current 2026 accepted replay is not available and the older 2021 rolling-window region is missing; show six-year coverage separately and never call it a complete 2021–2026 result.
3. Implement account-level fill assumptions using ask to enter, bid to exit, no crossed/no quote fills, contract multiplier and actual adjustments, spread/slippage/commissions, capital/margin constraints, timing, stops, expiry handling, costs and drawdowns; record no-fill/unresolved exit. Local IV/Greeks need matched raw stock, exact timestamp, historical rates/dividends and independently checked standard deliverable. EOD scenario results are not historical 09:35 execution.
4. Evaluate strategy hypotheses and tuning across chronological DEVELOPMENT/walk-forward regimes, then protect the original holdout. Do not force or target a return percentage.

The architecture is: stock/news/native-open → PIT contract selection → verified D: quote cache → common-clock observed source → offline account simulator. Missing data should be requested **once per immutable exact series** by the preparation/acquisition layer and saved to D:, not one GET per candidate stop-loss or backtest iteration. All paid requests are explicit and receipt-bounded; no broker/PAPER/LIVE authority.

## Accepted operator execution — 2026-09-27 America/New_York

The first real after-merge workstation run completed without a provider call. It wrote source selection `multiyear_pit_selected_option_quotes_v1_3fa478312734f9c2.json` and frozen quote demand `multiyear_demand_quote_v1_dbe759955e48946b.json` under `data/options/manifests` (physically D: via the configured ATLAS binding). All **14,902 original cases / 29,804 right slots** were retained. **7,788 selected memberships** are: original accepted CALL pointer 2,654; verified original chain 2,712; verified new chain 2,422. Remaining right-slot categories: exact source query no-data 468; missing chain 13,126; no frozen expiry/native OPEN 40; no physical source identity 72; old-2021 rolling gap 8,276; protected-2026 entry 34. The quote plan has **6,622 unique exact OCC/from/to requests**, all with `SOURCE_DEMAND_READY` plan disposition; this describes request eligibility, **not cached quote coverage**. D: reported 225.212 GiB free. No option fill or P&L was created.

### Next zero-credit workstation step

Run in ATLAS PowerShell after merging this documentation update:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed.' }; & .\\.venv\\Scripts\\python.exe scripts\\run_multiyear_demand_quote_cache_v1.py --plan .\\data\\options\\manifests\\multiyear_demand_quote_v1_dbe759955e48946b.json; if ($LASTEXITCODE -ne 0) { throw 'Offline quote-cache census stopped; paste complete output.' } }
~~~

No `--max-new-requests`, credit budget, token, or paid authorization flag is specified. The returned census distinguishes original 2022 covering-history reuse, verified new cache, exact no-data quote results and genuinely pending full quote histories. Reconcile that output before any new paid authorization; the existing executor has a static 500-credit floor and per-run 250-request/250-credit caps that need a separately reviewed budget-contract change if larger user-authorized batches are desired. The original 63 chain-query 404s must not be conflated with 468 per-right source no-data slots or later quote history no-data. Do not re-run chain acquisition merely because a separate price history is absent.

## Accepted quote cache reuse and source-to-replay handoff — 2026-09-27 local

The offline quote executor returned signed report fingerprint `09b634c4392f4ac326e9e58c6722ad0774d2cb565304ad11beea7438080b229c`: 6,622 unique requests, 2,229 verified covering original 2022 sources, zero completed multiyear-v1 cache series, zero exact quote 404s, and 4,393 pending in the *currently checked cache namespaces*. No provider credits were spent. Treat the latter as currently unindexed or pending, not proven absent across all old D: archives. This is not a repeat of the original 6,398-complete 2022 corpus audit.

`scripts/prepare_multiyear_option_quote_reuse_handoff_v1.py` compiles a new immutable, SHA-signed, D:-bound **full case/right** map. It consumes the frozen source-selection file and quote plan, invokes the existing zero-paid receipt census to verify every reused source, and joins the 29,804 original slots to a verified quote body SHA/pointer or an explicit gap. It emits per-year status counts without re-reading the entire 2022 corpus or inventing a fill. The map is the next integration input to the existing same-clock and local-Greeks research modules. No present option mark or source receipt establishes a 09:35 trade.

Single command from repository root, after CI and merge:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed.' }; & .\\.venv\\Scripts\\python.exe scripts\\prepare_multiyear_option_quote_reuse_handoff_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Offline quote reuse handoff stopped; paste complete output.' } }
~~~

This command does not include provider authorization or any paid GET. The requested data stays under the configured D: physical binding. Next work must index original 2025 historical series with exact from/to coverage checks and valid original receipts before considering 4,393 as truly missing, and must normalize source observations for later EOD account replay rather than acquiring another chain-only batch.

## Accepted offline quote-reuse handoff and new observed-source timeline — 2026-09-27 local

The operator handoff is accepted: `multiyear_option_quote_reuse_handoff_v1_46e4c27c3d203581.json`, fingerprint `46e4c27c3d203581ae92c2f0ff653c9c3e65b1fa07f093a195dca2ecd8aff8cd`. It preserves the full 29,804 case/right slots. Its 2,673 selected memberships with reusable historical quotes share only **2,229 physical original 2022 receipts**; 5,115 other selected memberships map to **4,393 unique pending** full quote histories in the currently indexed caches. Three 2023 selected memberships are covered by older original-2022 exact histories. The original 2021 source floor and protected 2026 rows remain explicit; nothing has been promoted to a 2021–2026 strategy result.

The new `multiyear_observed_option_quote_timeline_v1` adapter verifies original raw/intent/receipt hashes of only referenced histories, decodes each unique source once, joins all source-gap slots and reports actual first and subsequent valid observed **later-session** two-sided option quote source records. Same-session EOD may never impersonate original 09:35. The source `updated` timestamp is not verified historical publication time or synchronized 16:00 ET option/stock observation. A complete full quote history can still have zero or only one usable later observation. Unknown actual contract multiplier/deliverable, no matched raw stock EOD, spread/cost and no-fill rules remain gates to account-level simulation. Any broken SHA, receipt, timestamp or physical-query identity fails closed. Missing data never causes an automatic GET.

Operator step, after PR merge, from ATLAS root:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed.' }; & .\\.venv\\Scripts\\python.exe scripts\\prepare_multiyear_observed_option_quote_timeline_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Observed option quote timeline stopped; paste complete output.' } }
~~~

The result is an immutable D:-bound `data/options/derived/multiyear_observed_option_quote_timeline_v1_<fingerprint>.json`, year/status counts and **zero provider GETs**. The next component must reconcile independent same-session stock EOD marks and prove option quote clock compatibility before any scenario reference, and keep all nonpaired original cases in its denominator.

### Offline timeline first-run failure and narrow-window fix

The first workstation timeline execution failed closed before output with `ObservedOptionTimelineError: quote timing, spread or source classification changed`. The original 2022 accepted cache has full-length physical histories that may **cover** a narrower selected request; three 2023 case/right memberships reuse a covering original 2022 physical quote history. V1 accidentally rejected legitimate older rows when testing the full original body against the narrower selected range. The revised adapter first verifies the complete original physical source receipt/body and validates every decoded observation (including out-of-request older source rows), then slices the normalized, already validated rows to the immutable from/to demand interval. Neither a later EOD mark at the original intraday decision nor a crossed source quote becomes an executable fill. Original receipts, full-case selection, quote demand and 29,804-slot handoff are unchanged; no paid fallback. Regression tests include an older invalid row, same-year narrower request, and original 2022 source covering a 2023 request. Repeat the existing zero-GET timeline command only after the fix is merged.

## Consolidated next offline step after observed quote window correction

PR #287 corrected the earlier failure where the selected demand window was narrower than its intact covering original 2022 quote history. The original full raw source and receipts are checked, including earlier original records, then only the selected demand window is exposed to the scenario source. No original evidence was changed.

Run this **one command** from the ATLAS root on `main`, after the combined preflight PR merges:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_option_stock_eod_preflight_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Integrated offline source preflight stopped; paste complete output. Do not run a paid command.' } }
~~~

This replaces re-running separate quote timeline and small overlap audits. It prints and writes **four independently signed D:-bound artifacts**: corrected full-case option quote observation timeline; exact-contract original 2025 pilot historical-quote reuse/partial-window census; de-duplicated accepted native raw 1Day CLOSE requests for actual later-session option source dates; and a **targeted original C: native CLOSE source**. The final stage verifies accepted V2 plan, exact daily-unit checkpoint and canonical Parquet SHA and reads only requested ticker/year units with bounded hardware-aware workers. Missing exact stock-date rows remain source gaps. It does NOT rescan the entire 3.9-billion-row stock corpus or reuse adjusted research-view OPEN for option structural selection. The first-/next-observed quote marks remain provider EOD references, **not** 09:35, historical executable fills, a matched stock/option 16:00 clock, confirmed contract multiplier, or portfolio P&L. All 14,902 original cases, 29,804 right slots and protected 2026 boundary remain visible.

The separate paid quote executor now accepts larger safe batches and an explicit operator `--min-remaining-credits` (default 500), with two potential credit reservations per in-flight GET. This consolidated command does not authorize or call it in paid mode. Any new paid acquisition must exclude correctly verified original full-coverage reuse and account for partial legacy overlap before spending.


### 2026-09-28 — Same-run full-cohort stock/option dated source casebook (source-only)

The consolidated zero-GET workstation preflight now adds a fifth stage after targeted original C:-native raw daily CLOSE verification: an immutable D:-bound signed full-cohort source casebook. This is added to the same existing script, not a separate workstation command. It joins every original 14,902 signal / 29,804 case-right slots by immutable identities across the accepted quote reuse handoff, receipt-verified option timeline, frozen native-close demand and SHA-verified original native CLOSE source. Each selected slot retains its original OCC, quote-body SHA, observed later option bid/ask and provider update timestamp, and actual native raw stock CLOSE on exactly the corresponding ET session if present. Nonselected and missing-source slots remain in the denominator. It reports per-year counts for absent later two-sided option source, native exact daily gaps and dated stock+option source pairs; 2026 remains zero in this accepted 2021–2025 source population. Results are immutable under the configured D: options derived binding; source files and prior signed artifact fingerprints are not rewritten.

Dated source evidence **does not** prove matched stock/option observation timestamps: a provider update is not historical publication time, the original native daily bar does not carry a certified option-synchronous close timestamp, and original 09:35 entry cannot use later EOD. No deliverable/multiplier is inferred; no historical fill, Greek, option P&L, account return, PAPER/LIVE or new protected-holdout authority is granted. The source casebook is the bounded, receipt-linked join for subsequent independent clock/deliverable/cost validation and account replay, not a simulated trade. No new provider calls or broad original stock corpus scan are introduced. The fourth-stage native close reader remains 1–4 workers and stops on SHA/plan drift or an invalid required native source; exact missing daily bars remain explicit gaps.

One operator action after merge, from ATLAS PowerShell root:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_option_stock_eod_preflight_v1.py --native-workers 4; if ($LASTEXITCODE -ne 0) { throw 'Combined option-stock source preflight stopped; paste complete output. No blind paid retry.' } }
~~~

Next: inspect actual one-pass source counts and gaps before authorizing paid exact series; account-level simulation requires independent clock, original deliverable, commissions/fees, expiry and fill semantics, plus the accepted signed source population. Do not re-run earlier successful census/selection/acquisition stages merely for another status check.


### 2026-09-28 — Offline multiyear account mechanics and actual source-admission census

A separate, zero-provider account-mechanics kernel now supports four alternatives (STOCK, CALL, PUT, ABSTAIN) on **the same original synthetic signal cohort**. It orders events chronologically, releases exits before same-timestamp entries, enforces cash-only long positions, allocation fractions, maximum concurrent positions and units, adverse stock slippage, option ask-to-enter/bid-to-exit plus separate per-contract entry/exit fees, and reserves exit fees before new admissions. Every omitted leg, insufficient cash, unqualified clock/source, unknown option deliverable and expiry/assignment uncertainty is an explicit nontrade rather than a fabricated exit. Complete modeled exits return an auditable cash ledger and per-year status counts; no intraday mark/drawdown, historical fill or portfolio-return authority is claimed. Historical data **cannot** be smuggled into this fixture engine by merely setting a proof flag: the kernel admits `SYNTHETIC_FIXTURE_ONLY` source origin, while actual evidence requires its own later verified admission adapter.

The new `multiyear_account_readiness_v1` accepts the operator's original immutable signed `176aa0427a9ec34f...` 29,804-right casebook without decoding the historical raw corpus again. It checks the original case/right denominator, all C/P memberships, D: source fingerprint and unchanged source-only/unsynchronized authority; labels exactly why each historical right cannot yet enter a true replay. The current 2,648 **date-matched but unsynchronized** source pairs remain in the population, with zero qualified historical trades and NULL historical P&L; the 11 native-close gaps, 4,393 previously pending exact histories and 2026 protected/absent population are not silently promoted. Report is immutable and stored on the configured D:-bound options derived path, while the stock database and simulation code stay C:-resident. Neither operation issues a MarketData GET, touches the accepted receipts, or asserts that an option provider update equals the native stock close clock.

One future offline operator step after merge (from ATLAS repository root) audits the actual source-admission census and executes a **clearly labeled fabricated-price** smoke scenario for all four account modes:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only origin main; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\run_multiyear_offline_account_replay_v1.py --synthetic-smoke; if ($LASTEXITCODE -ne 0) { throw 'Offline account source-admission/synthetic-engine run stopped; paste complete output.' } }
~~~

Next real-source integration: independently qualify option/publication and native underlying clock, verified historical deliverable/multiplier, source-proven entry/exit side plus cost/expiry policy; then add a receipt-bound historical adapter to the account kernel. Do not report the synthetic smoke P&L as historical performance or use same-date (unsynchronized) data as exact-minute execution. Paid exact-history acquisition remains a separate user-authorized, credit-capped preparation stage, not a hidden replay fallback.


### 2026-09-28 — Causal event replay and frozen real-execution proof demand

The initial two-case synthetic smoke passed but exposed a necessary historical-backtest design correction: a known future exit price must **never** be required to admit an earlier entry. The offline account engine now makes entry eligibility independent of later outcome/exit evidence. It accepts an explicit as-of UTC cutoff; future decisions and future entries stay in the original denominator, not silently dropped. Qualified entries debit and reserve cash immediately. If an exit is absent, after the cutoff, unqualified, or later than an option's expiry, the position remains OPEN with explicit missing-source/expiry status, its liquidity and exit-fee reserve remain locked, and **ending equity, unrealized P&L and flat-account cash-change return are NULL**. Realized P&L only sums completed modeled exits. The engine does not fabricate a zero-bid exit, intrinsic settlement, assignment or option expiration credit; stock/option clock and deliverable admission remain necessary. Tests cover incomplete exits, cutoff, unknown equity, expiry and no change in entry cash when future evidence disappears.

In the **same existing zero-provider account CLI**, `multiyear_historical_execution_requirements_v1.py` now reads the accepted signed full-case source casebook and previously signed replay-readiness result, freezes one immutable D:-bound source-work manifest for the **2,648 dated-but-unsynchronized pairs** and their first/next later option/stock observations, deduplicates exact quote observation and original native CLOSE request identities, and reports six-year blockers without dropping the remaining original 29,804 right slots. Every work item identifies original quote-body SHA, immutable request identity, observed bid/ask, provider update, exact-date native raw close, source unit SHA, and the independent clock, publication/availability, contract multiplier/deliverable, execution liquidity/cost and expiry proof still required. Provider update remains **not** publication proof; daily stock CLOSE remains **not** same-clock proof. No input may self-certify a historical fill or account return; all admission fields remain false/NULL. No new provider GET and no broad original stock corpus scan. This is **not** permission to pay for 5,296 source observations again—the historical source prices are already present; the manifest freezes what independent evidence is missing for safe account replay.

Next step: bind actual timestamped underlying trade/quote observations and independent option availability plus point-in-time corporate-action deliverables to these exact source identities, then implement genuine historical entry and exit adapters. Do not relabel synthetic cash-flow changes or EOD dates as actual 09:35 trades or reconstruct 2026 protected performance. The accepted origin-specific historical adapter must prove its inputs, not simply pass the synthetic fixture-origin flag.


### September 29 reset-day source acquisition — rolling entitlement guard

The accepted six-year quote plan was frozen when Starter's rolling floor was 2021-09-27; after daily reset on September 29, the exact older FROM may no longer be entitled. The paid cache now rechecks **only new, as-yet-unacquired exact requests** against the current Eastern-calendar five-year floor. Intact verified local histories are always reused before this test. It preserves each immutable query fingerprint and all original case memberships: out-of-window exact histories are reported as `rolling_floor_stale_pending` and remain pending, **never charged, silently clipped, falsely called no-data or promoted to a historical fill**. An independently signed clipped-prefix source overlay may later recover the newly accessible portion of 2021 without modifying the original plan. The script prints the current paid floor and stale count. Eligible 2022–2025 exact series continue through the bounded, receipt-first worker, keeping no automatic retry/unknown attempts and actual observed headers.

The historical MarketData Starter quote endpoint charges **one credit per 1,000 returned EOD quote observations**, and the accepted executor caps each response at 500 rows; the first authorized paid GET establishes current remaining credits for subsequent waves. The published Starter plan permits 10,000 credits/day, but this published limit is **not proof of the operator's current personal remaining balance**. For a user-approved fully reset account, an explicit total-credit and request cap must still be supplied; reserve all in-flight worst-case exposure against the lower of that asserted amount and latest observed provider header. Do not run another paid ATLAS source job concurrently; no benchmark, trade replay, current-chain fetch or Greek calculation belongs in the paid exact-series acquisition. Native stock stays on C:; receipts and quote series persist under D:-bound options storage. Exact 2021 out-of-window coverage remains an explicit missing-source category. 


### 2026-09-30 — Full exact-cache acquisition closeout, 2021 tail recovery and source refresh

The accepted exact quote acquisition completed every still-entitled original request: 3,906 new exact histories were persisted and SHA/receipt verified for 3,897 observed credits, alongside 2,229 reused original 2022 histories. The only remaining original-query gap was 487 requests whose immutable 2021-09-27 start had fallen behind the 2021-09-30 rolling Starter floor. Those requests remain immutable and are never retried with silently changed dates.

A new recovery layer derives a **separate signed clipped-tail request** only for a still-pending original exact request whose original FROM is older than the current five-year floor while its TO remains accessible. The recovery request starts at the current entitlement floor and carries the original request identity as provenance. Its raw body/receipt uses its own exact query identity in the existing D:-bound cache. Missing earlier days remain explicit; a clipped suffix can never claim original-window completeness, 09:35 availability, a historical fill or P&L. Recovery plans are deterministic for an Eastern calendar day, deduplicate identical clipped physical queries, and reuse the standard paid lock, durable pre-request intent, no-auto-retry, credit/header and storage guards.

The full-case source handoff can consume a zero-GET signed recovery overlay. A recovered case/right retains the original quote-demand ID for cohort membership but records the **actual physical recovery request ID, source FROM/TO and body SHA** separately. The observed timeline decodes each physical recovery body once, validates every returned session, and may use only two-sided observations actually present in the clipped source. The source casebook and execution-proof demand likewise bind the physical source identity; no clipped body may be mislabeled as the unavailable original full-window body.

`scripts/refresh_multiyear_sources_after_quote_cache_v1.py` performs the downstream rebuild with **zero provider GETs**: verify original/recovery local caches -> immutable recovery overlay -> fresh 29,804-right handoff -> observed option timelines -> exact native daily-CLOSE demand -> bounded local native-unit verification -> fresh source casebook -> replay-readiness census -> execution-proof demand. New quote coverage can therefore flow to the simulator without redownloading histories. Historical account P&L remains NULL until independent stock/option common-clock, as-traded deliverable/multiplier, entry/exit liquidity/cost and expiry/exercise proof gates are satisfied.
