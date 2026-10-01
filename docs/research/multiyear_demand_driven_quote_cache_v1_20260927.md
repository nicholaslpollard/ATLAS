# Multi-year exact historical options demand cache V1 — 2026-09-27

The strategy laboratory must not get trapped in one year or spend an API credit every time stop-loss/DTE/entry rules are tuned. This component is the source-only missing-series cache across **2021–2026**, separate from the simulator. It accepts **already selected** OCC contract identities with original timestamp and accepted stock-source SHA, freezes original case denominator and deduplicates physical exact-symbol/from/to history requests. No later observed liquidity can change the original selected contract. The manifest explicitly retains 2021 candidates before the rolling Starter five-year floor and future-date candidates as ineligible—not silently omitted. 2026 unexpired histories end at the most recently completed regular market session, not an invented future expiry mark.

Before a new GET, the executor checks the original accepted 2022 6,398 CALL plan **once** and reuses an intact covering original history without copying raw bytes. For other exact queries it verifies local raw/intent/receipt SHA and classification. A complete source or exact 404/no_data is not reacquired. Every new paid request is preceded by an immutable on-disk attempt. The provider response's raw bytes, observed headers and classification are saved under the D:-bound \`data/options/candidate_cache/quotes/multiyear_demand_v1\`. Missing/partial/tampered evidence or an uncertain attempt stops; no automatic retry or source overwrite.

**Budget:** preview requires **zero token and zero provider requests**. Paid execution requires all three affirmative flags, a token in environment, independent positive caps of at most 250 new requests and 250 observed credits per invocation, an asserted remaining allowance preserving at least **500 credits**, and a first single GET to establish provider header evidence before any bounded parallel wave. Each subsequent wave is reserved against both request/credit caps and remaining balance; worker count is capped at eight and reduced to workstation CPU headroom. Every attempt is classified and original responses are preserved. A paid-session lock exists under D: for this new worker; an unresolved/uncertain run leaves that lock and per-request attempt intact for manual review. Other older provider workflows do not honor this lock, so the operator must not run paid source jobs concurrently. The user reported fewer than 2,000 credits left on September 27; today's default is still zero, and **do not interpret the user-reported figure as an actual current provider balance.**

The underlying option historical endpoint is EOD, and these receipts make **NO 09:35 fill, Greeks, historical deliverable, executable quote, option P&L, PAPER or LIVE claim**. The next stage reads verified quote+stock+news evidence into the common-clock case schema and computes local IV/Greeks only when historical risk-free, dividend and deliverable inputs exist. Quotes expiring beyond the current date will require a later incremental tail strategy, not blind re-download of a full completed year; this initial immutable exact-query cache deduplicates identical requests and supports accepted 2022 coverage. An accepted stock decision source adapter is still needed to freeze **genuine** 2021, 2023, 2024, 2025 and 2026 selection files; arbitrary row source SHA text is not sufficient validation or promotion authority.

**Operator path, once green and merged:** \`scripts/run_multiyear_demand_quote_cache_v1.py --selected <accepted-source-selection.json>\` writes the exact plan on D: and previews source reuse/missing status with zero GETs. There is no need to spend today's remaining allowance before the multi-year source-selection adapter can define missing queries for real strategy cases. Paid flags are deliberately not suggested as a ready command until the actual plan and current account balance are inspected. Never treat the full-year 2022 reference's median hypothetical first-ask/next-bid change as a six-year option-strategy return.

The MarketData license requires deletion of downloaded subscription data when subscription ends; offline research access while subscribed does not grant indefinite post-cancellation retention.


### September 29 reset-day source acquisition — rolling entitlement guard

The accepted six-year quote plan was frozen when Starter's rolling floor was 2021-09-27; after daily reset on September 29, the exact older FROM may no longer be entitled. The paid cache now rechecks **only new, as-yet-unacquired exact requests** against the current Eastern-calendar five-year floor. Intact verified local histories are always reused before this test. It preserves each immutable query fingerprint and all original case memberships: out-of-window exact histories are reported as `rolling_floor_stale_pending` and remain pending, **never charged, silently clipped, falsely called no-data or promoted to a historical fill**. An independently signed clipped-prefix source overlay may later recover the newly accessible portion of 2021 without modifying the original plan. The script prints the current paid floor and stale count. Eligible 2022–2025 exact series continue through the bounded, receipt-first worker, keeping no automatic retry/unknown attempts and actual observed headers.

The historical MarketData Starter quote endpoint charges **one credit per 1,000 returned EOD quote observations**, and the accepted executor caps each response at 500 rows; the first authorized paid GET establishes current remaining credits for subsequent waves. The published Starter plan permits 10,000 credits/day, but this published limit is **not proof of the operator's current personal remaining balance**. For a user-approved fully reset account, an explicit total-credit and request cap must still be supplied; reserve all in-flight worst-case exposure against the lower of that asserted amount and latest observed provider header. Do not run another paid ATLAS source job concurrently; no benchmark, trade replay, current-chain fetch or Greek calculation belongs in the paid exact-series acquisition. Native stock stays on C:; receipts and quote series persist under D:-bound options storage. Exact 2021 out-of-window coverage remains an explicit missing-source category. 


### 2026-09-30 — Full exact-cache acquisition closeout, 2021 tail recovery and source refresh

The accepted exact quote acquisition completed every still-entitled original request: 3,906 new exact histories were persisted and SHA/receipt verified for 3,897 observed credits, alongside 2,229 reused original 2022 histories. The only remaining original-query gap was 487 requests whose immutable 2021-09-27 start had fallen behind the 2021-09-30 rolling Starter floor. Those requests remain immutable and are never retried with silently changed dates.

A new recovery layer derives a **separate signed clipped-tail request** only for a still-pending original exact request whose original FROM is older than the current five-year floor while its TO remains accessible. The recovery request starts at the current entitlement floor and carries the original request identity as provenance. Its raw body/receipt uses its own exact query identity in the existing D:-bound cache. Missing earlier days remain explicit; a clipped suffix can never claim original-window completeness, 09:35 availability, a historical fill or P&L. Recovery plans are deterministic for an Eastern calendar day, deduplicate identical clipped physical queries, and reuse the standard paid lock, durable pre-request intent, no-auto-retry, credit/header and storage guards.

The full-case source handoff can consume a zero-GET signed recovery overlay. A recovered case/right retains the original quote-demand ID for cohort membership but records the **actual physical recovery request ID, source FROM/TO and body SHA** separately. The observed timeline decodes each physical recovery body once, validates every returned session, and may use only two-sided observations actually present in the clipped source. The source casebook and execution-proof demand likewise bind the physical source identity; no clipped body may be mislabeled as the unavailable original full-window body.

`scripts/refresh_multiyear_sources_after_quote_cache_v1.py` performs the downstream rebuild with **zero provider GETs**: verify original/recovery local caches -> immutable recovery overlay -> fresh 29,804-right handoff -> observed option timelines -> exact native daily-CLOSE demand -> bounded local native-unit verification -> fresh source casebook -> replay-readiness census -> execution-proof demand. New quote coverage can therefore flow to the simulator without redownloading histories. Historical account P&L remains NULL until independent stock/option common-clock, as-traded deliverable/multiplier, entry/exit liquidity/cost and expiry/exercise proof gates are satisfied.


### 2026-09-30 — Additive reset-day source sweep supersedes the initial reset-day advance

The first invocation of `scripts/run_multiyear_reset_day_source_advance_v1.py` stopped before any provider GET because that new script resolved `MARKETDATA_TOKEN` before `load_settings()` had loaded the repository-root `.env`. Its targeted tests had passed (**34 passed**) but the paid path made **zero provider requests and consumed zero credits**. The credential-ordering defect is fixed and guarded repository-wide; however, the initial full-plan rebuild design is also superseded before first paid use.

The accepted reset-day path is now the **additive source sweep** in `scripts/run_multiyear_reset_day_source_sweep_v1.py`. It preserves every previously selected PIT OCC identity and every existing exact quote query/window from the accepted base selection/plan. Additional year-balanced PIT chain acquisition may make previously unselected CALL/PUT slots selectable; only those newly selectable slots are added to quote demand. Existing contract identities may not be replaced merely because more chain evidence becomes available. Newly selected 2021 slots already outside the current Starter window remain explicit source gaps with no invented full-window request.

One cumulative daily credit ceiling spans: (1) verified clipped-tail recovery for still-accessible portions of the 487 stale original 2021 exact requests; (2) year-balanced missing PIT chain snapshots; and (3) exact quote histories for newly selectable contracts. The sweep withholds a configurable portion of the daily budget from the chain stage only so newly discovered contracts can still obtain quote histories; `min_remaining_credits=0` may still allow the full operator-authorized daily budget to be used across the complete sweep. Provider headers remain the harder runtime balance after the first GET. All completed receipts are reused and no uncertain paid attempt is automatically retried.

After paid source work, the same command rebuilds the clipped-source overlay, full 29,804-right handoff, observed option timelines, targeted native raw daily CLOSE evidence, source casebook, account-readiness census and execution-proof demand with **zero further provider GETs**. Native stock stays on C:, options/news/evidence remain on the D:-bound secondary storage. Historical option P&L remains NULL; provider EOD quote timestamps are not 09:35/publication proof, native daily CLOSE is not a synchronized option clock, and deliverable/multiplier, executable liquidity/cost and expiry/exercise/assignment proof remain required.

For future ATLAS review sessions, do **not** resume from the older reset-day advance command. Review current `main`, this section, the repository-root `.env` credential contract, the latest operator output, and use the additive sweep as the sole reset-day multiyear paid orchestration path unless a later merged living-document revision explicitly replaces it.


### 2026-09-30 — Additive reset-day paid acquisition completed; offline native-2026 boundary repair

The first authoritative additive reset-day sweep completed its **paid acquisition stages** and then stopped only in the zero-provider native-stock verification stage. Operator output recorded:

- cumulative observed MarketData credits: **9,999**;
- last provider remaining header: **1**;
- verified clipped 2021 recovery overlay: **487 complete / 0 gaps / 0 pending**;
- additive exact quote cache after the run: **7,314 complete**, **2,235 reused accepted 2022 histories**, **0 exact source gaps**, **7,799 still pending**;
- the paid exact-quote stage ended cleanly at provider remaining 1 and persisted every completed body/attempt/receipt before the later offline stop.

**Do not rerun the paid sweep to recover from the subsequent error.** Those credits and source receipts are already retained on D:.

The later stop was:

`NativeEodCloseError: protected/adjusted native request cannot be read`.

Root cause: newly available 2025 option contracts can have first/next retained option-source observations in early **2026**. The accepted native-stock contract intentionally forbids opening 2026 stock outcomes. The original native-close resolver treated the presence of such a request as a fatal malformed demand instead of recording the protected boundary as an explicit source disposition.

The repaired contract now keeps an exact 2026 native CLOSE request in lineage but labels it `PROTECTED_2026_NATIVE_CLOSE_WITHHELD_NOT_READ`. No 2026 native stock unit, Parquet row, return, open or close is read. Pre-2026 native requests continue through SHA/checkpoint-verified local source reads. The source casebook exposes `OPTION_SOURCE_DATES_PRESENT_PROTECTED_2026_NATIVE_CLOSE_WITHHELD`, and replay readiness exposes `PROTECTED_2026_NATIVE_CLOSE_WITHHELD`; neither is an executable trade or an inferred price gap. `protected_2026_outcomes_read` remains zero.

The deterministic recovery command is now `scripts/continue_multiyear_source_refresh_offline_v1.py --acquisition-day-et 2026-09-30`. It performs **zero provider GETs**. It reconstructs the current PIT selection from local chain receipts, discovers exactly one additive quote plan bound to the accepted base-plan fingerprint + current selection fingerprint + September 30 acquisition day, discovers exactly one matching signed recovery overlay, verifies local quote receipts, then resumes handoff -> option timeline -> native CLOSE source -> casebook -> readiness -> execution-proof demand. If artifact lineage is ambiguous, it fails closed instead of choosing by modification time or performance.

Future ATLAS handoffs must preserve this distinction: the September 30 paid work is complete evidence acquisition, while the native-2026 repair is an offline source-classification fix. Remaining 7,799 exact quote histories are future acquisition work after another provider reset; they are not a reason to repeat already completed September 30 requests.

### 2026-10-01 — Cross-day clipped-tail cache reuse before the next paid reset

The September 30 offline continuation closed successfully with zero provider GETs:
17,348 physical exact histories are now in the additive plan, with 2,235 accepted
2022 histories reused, 7,314 exact cache histories complete, zero exact quote gaps
and 7,799 pending. The prior clipped-tail overlay remains 487/487 complete.

A reset-day review identified a duplicate-spend risk: advancing the rolling entitlement
floor by one day would create a new narrower clipped request even when yesterday's
verified clipped body already covered that entire suffix. The recovery planner now
discovers signed prior recovery overlays and reuses the broadest verified covering
physical query for the same immutable original request. Reuse requires exact option
symbol and end-date equality, prior start <= current floor, signed overlay provenance
and the prior body SHA-256. The ordinary cache census re-verifies the physical
receipt/body before reuse; SHA drift fails closed. A missing/corrupt prior body is not
silently reacquired under the stale query identity.

This is a cache/transport efficiency repair only. It does not make the unavailable
original prefix complete, does not turn provider `updated` into publication proof,
does not synchronize native stock CLOSE with option quotes, and creates no historical
fill, deliverable, P&L, strategy, PAPER or LIVE authority.

After merge, the next paid reset should prioritize the 7,799 already-selected exact
histories while retaining only a bounded chain budget. Completed September 30 quote,
chain and recovery receipts must be reused; no paid request is repeated merely because
the Eastern rolling floor advanced.

### 2026-10-01 — Carry the signed additive head across reset days

Cross-day clipped-tail reuse is necessary but not sufficient. The reset-day
orchestrator must also carry forward the latest accepted additive quote plan itself.
The additive planner preserves exact prior windows only relative to the plan it is
given as its base. Reusing the original September 27 root every day would cause all
later selections to be frozen again under the new rolling floor, changing some 2021
request identities and defeating exact-cache reuse.

The reset-day path now discovers one unique signed parent→child additive lineage from
the frozen root. Every hop requires exact parent-plan fingerprint, exact base-selection
fingerprint, signed referenced expanded selection, unchanged prior selected contract
fields, exact request membership/count reconciliation and non-backward planning-day
chronology. Forks, cycles, missing selection artifacts or broken links fail closed.

The latest lineage head is used for the initial exact-cache census and clipped-tail
recovery. A local current-selection rebuild is validated against that head before any
provider work. After the bounded chain stage, only selections absent from the head are
newly planned under the current floor. Existing request identities/windows are copied
forward unchanged. The offline continuation uses the same lineage chain.

For the current October 1 handoff the expected pre-acquisition head is September 30
`90f940b2bf167a9451a3d569286ee2fc065c776a2e8df12edf9bef7e02bcbc03`
(17,348 physical exact queries; 7,314 new-cache complete; 2,235 reused accepted
2022; 0 exact gaps; 7,799 pending). Do not spend October 1 credits from a build that
reconstructs those non-root selections from the September 27 base.
