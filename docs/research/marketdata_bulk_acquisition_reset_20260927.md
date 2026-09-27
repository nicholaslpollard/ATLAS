# MarketData historical options: coordinated bulk-acquisition reset — 2026-09-27

## Why the acquisition plan changes

Operator identified a material mismatch: D: secondary SSD is not growing despite repeated successful chain campaigns. The latest completed source campaign (shards 0–5) yielded 229 exact historical chain sources, 11 strictly proven source gaps, and 200 new GETs/189 observed credits; shards 6–15 are currently in a separately authorized workstation acquisition. Small option-chain snapshots are naturally compact; increasing the number of calls is **not** a metric for usable simulator data or disk utilization.

The initial 2025 quote pilot captured 11 exact CALL contract EOD history series and 320 quote-day rows. The **large-cohort quote-series adapter is not implemented**; `marketdata_candidate_2025_selected_quote_source_v1.py` is deliberately frozen to its eleven original 2025 symbols. Further standalone chain shards are source acquisition only, not a substitute for contract history or intraday fill data.

## Provider economics and key licensing constraint

MarketData's publicly documented historical option-chain pricing is 1 credit per 1,000 returned symbols; historical exact-contract quote-series pricing is 1 credit per 1,000 returned quote rows. From/to query parameters retrieve the full available EOD history for a symbol in one call; do not query each trading day separately. Actual header-reported charge is authoritative. MarketData Starter provides 10,000 daily credits, with a 09:30 ET reset per the accepted prior provider qualification; do not assume a credit cap from the number of requests alone.

As of the published MarketData Terms of Service (2025-08-18, rechecked 2026-09-27), licensed downloaded data must be deleted on subscription termination. The D: SSD does not grant permanent post-cancellation retention. Until MarketData provides explicit written rights for the intended perpetual internal historical use, **do not promise that ATLAS can cancel Starter and keep/reuse downloaded raw chain/quote data**. Preserve license scope and never redistribute raw provider data; retain derived evidence only as permitted. Source: https://www.marketdata.app/terms/ ; https://www.marketdata.app/docs/api/options/chain/ ; https://www.marketdata.app/docs/api/options/quotes/ .

## One-campaign engineering objective, not blindly full exchange universe

The next engineering implementation should replace repeated operator handoffs with one resumable, daily-credit-aware *candidate-first* 2022–2025 program:

1. Establish the accepted available DEVELOPMENT daily LONG opportunity universe for each year and the protected holdout boundary; do not invent a 2021 accepted native-stock adapter or select on outcomes.
2. Preserve all already completed 2022 and 2025 provider receipts, no-data proofs, chain sources, source SHA and global physical-query keys. Never re-request an exact physical group because its plan ID differs.
3. Freeze a PIT contract-coverage rule before reading same-day EOD: original previous-session chain snapshot, raw-as-traded entry OPEN, bounded strike/expiry alternatives appropriate to intended option simulator. Include source gaps/abstentions and corporate-action/deliverable uncertainty explicitly.
4. **Use available previous-session chain receipts to build selected exact CALL symbol/horizon requests.** Group repeated contract symbols across opportunities and merge their overlapping or adjacent requested date intervals before any quote API GET. Use one `from/to` call per unique contract interval where valid, rather than one call per session. Preserve all opportunity-to-contract memberships.
5. Extend the original 2025 quote cache semantics to general cohorts: immutable original raw body and intent/receipt SHA, 404/no_data exact-only classification, 4 MiB/row bounds or separately explicit expanded limits, D: physical quota, no blind retry after uncertain attempt, per-response actual credits, at most bounded hardware-aware request concurrency below provider limit after collision locks.
6. In the same workstation campaign, advance new chain source requests and quote histories by actual missing work with explicit aggregate request, observed-credit, storage and date-window ceilings; persist a global progress ledger, resume rather than start again, and stop safely before/provider reset or on ambiguous errors. Distinguish API/credit/day ceilings from disk bytes and completed quote days. The user authorizes each broad acquisition scope explicitly; do not launch an unbounded unattended 71-shard loop.
7. Generate a real **physical storage and demand ledger** from local receipt body_bytes and research-storage category sizes, and estimate remaining requests/credits by output type. Do not infer data growth solely from count of HTTP GETs. If the requested EOD corpus remains small, that is expected; SSD headroom supports other sources but should not trigger irrelevant downloads.

A history of EOD option quotes is **not** historical executable bid/ask at the strategy's 09:35 decision. For a faithful same-minute options replay, separately source timestamped intraday quotes or build an explicitly later-entry EOD scenario. Do not mix same-day 16:00 prices/volume into morning selection, label zero-volume last as a same-day trade, infer historical deliverable, or promote any option return/PAPER/LIVE strategy from the mere presence of a chain or quote history.

For a separate bulk provider, Massive lists options minute-aggregate flat files (four historic 2022–25 annual archives total on the order of tens of GB), while full historical OPRA top-of-book tick quote archives are tens of **terabytes per year** and would not fit D:. Availability to ATLAS depends on the operator's actual purchased entitlement, not documentation alone. Sources: https://massive.com/docs/flat-files/options/minute-aggregates ; https://massive.com/docs/flat-files/options/quotes ; https://massive.com/docs/flat-files/quickstart .

## Immediate operator transition

The 2022 shards 6–15 campaign already started under the previous explicit authorization; do not start a second process concurrently, interrupt a completed-source/receipt write, or blanket repeat paid calls. Capture its final output. **Before authorizing another chain-only campaign, implement and test the generalized selected-contract quote acquisition and unified cost/storage ledger**. The next workstation handoff should progress both new chain coverage and historical quote-history coverage within one budget. Record actual D: bytes and the remaining subscription rights before any cancellation decision.


### 2026-09-27 — Operator subscription and simulation scope clarified

The operator explicitly confirmed this historical options dataset is for **private ATLAS simulator/research use**, and the paid MarketData subscription will remain active for as long as needed to run those strategies. The intended workflow is reusable local D: historical chain plus selected-contract EOD quote source, not immediate subscription cancellation. The existing terms-of-service requirement for eventual termination still applies; this is not a perpetual offline-license assumption. Prioritize complete source coverage needed by scenario design, deduplication of paid requests, actual receipt bytes and credit-ledger observability. Chain-only snapshots must not masquerade as priced options simulations. Do not start an overlapping provider job while the previously authorized 2022 shard 6–15 campaign is active.
