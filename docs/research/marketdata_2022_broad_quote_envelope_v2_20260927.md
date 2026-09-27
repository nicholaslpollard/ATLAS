# 2022 historical CALL research envelope V2 — 2026-09-27

## Operator decision and accepted source closeout

The objective is a **local-first private ATLAS options simulator corpus**: bulk-acquire a deliberately bounded research universe while the paid MarketData subscription remains active, then satisfy repeat research runs from D: and use the provider only for genuinely missing symbols/date ranges or new sessions. Do not download the entire listed exchange or infer data value from drive utilization alone.

2022 original three-per-month source is already complete. The 2022 additive chain program has now completed **shards 0–15**: 640 physical exact historical chain queries, **601 complete original chain bodies, 39 narrowly proved zero-credit exact 404/no_data source gaps, zero pending**. Shards 6–15 are accepted under campaign fingerprint \`d358e3b4816cf7a588adc5f3f19e863f369e6d7d51f43eacd3fac59f0df77dbe\`: 400 new GETs, 372 credits, final 9,275 reported remaining; source loader called exactly once. Earlier 0–5 were 229 complete, eleven exact gaps. These are saved *sources*, not option return or P&L results. Do not repeat a completed shard.

### Why a distinct V2 plan is necessary

The existing V1 selected-history planner only chose nearest CALL plus up to two alternatives per opportunity. That was too narrow for future research scenarios. The V1 source-only cache and exact physical query identities are preserved.

V2 freezes **all CALLs returned by each accepted previous-session monthly chain that lie within ±8% of that opportunity's original raw-as-traded 1D entry OPEN**. Price-window selection uses no historical same-day option EOD volume, last, bid/ask, future return or outcome. It is not an arbitrary top-three filter. A repeated exact OCC symbol gets one full \`2022-01-01\` through expiry-inclusive EOD quote request; all source/opportunity memberships and original chain SHA lineage remain in the frozen private plan. The V2 code uses the existing V1 exact-series physical query cache, preserving and reusing any previously captured matching V1 quote receipts even if the wider plan has a new fingerprint. The original frozen 2025 11-CALL quote pilot is not modified.

The selection scope is *available previously captured source rows*, not all theoretical listed 2022 options. The original chain request itself was bounded to roughly ±8% by point-in-time raw underlying OPEN, with overlapping original physical requests kept as originally frozen. A 404 is a gap for that exact historical query only, not proof the option never existed.

### Expiration and universe boundary — do not silently claim completeness

This first V2 phase deliberately remains **one originally accepted 28–60-DTE monthly expiration per source opportunity**, because those are the original immutable chain receipts. The extra expirations required for future scenario coverage, the prior original three-per-month 2022 cohort (36 physical keys), remaining additive shards 16–70, supported 2023/2024/2025 cohorts, adjusted deliverables and 2021 stock-native admissibility are *not* automatically covered by this V2 plan.

Broader expiration coverage must first be separately PIT-planned against real historical exchange-calendar listings/contract structural reference, raw OPEN, explicit strike bounds and original physical-query deduplication. It must then be acquired with new immutable chain receipts before any quote series may be selected from those additional contracts. This prevents inventing an option expiry or look-ahead-based option selection.

### Acquisition, cost, and storage

Runner: \`scripts/run_marketdata_2022_broad_quotes_v2.py\`.

The V2 plan is distinct and immutable at \`data/options/manifests/marketdata_2022_broad_quote_plans_v2/through_shard_015.json\`; raw bodies/receipts reuse the existing exact \`data/options/candidate_cache/quotes/marketdata_2022_additive_v1\` physical key layout. The existing tested source acquisition layer provides original durable exclusive intent before any paid GET, up to four concurrent workers, no blind retries, 4 MiB/500 EOD-row per-series bounds, original body/receipt SHA checks, zero-credit exact 404 proof, category \`options_candidate_cache\` physical D: quota and free-space floor, per-response credit headers and a 200-credit floor. Each bounded batch respects the configured observed-credit target; any uncertain/quarantined original response stops later dispatch with original evidence preserved. One full from/to quote-series GET is made per deduplicated exact OCC symbol, not one per market day.

The local console prints original source census, exact selected memberships and distinct series, actual raw response bytes, D: free/category usage before and after, provider credits and remaining. It does not infer storage consumed from 400 chain GETs. The first authorized campaign is at most **2,000 new quote requests / 2,100 observed-credit stopping target**, so a wide source plan may truthfully end \`PARTIAL_BUDGET_OR_CREDIT_FLOOR\`; continue later from intact exact receipts rather than rerunning previously billed requests. A credit target is observed after responses, not a guaranteed invoice ceiling.

These historical EOD observations cannot prove executable bid/ask at the stock signal's original 09:35 ET decision or intraday SL/TP. Future options simulation must use properly sourced intraday prices or explicitly preregistered later-entry EOD scenarios. Do not issue return, strategy/promotion, PAPER/LIVE or broker authority based on source acquisition.

MarketData raw data remains subject to license terms; the operator explicitly intends to maintain Starter while data is needed by the private simulator, not cancel immediately.

## One operator command after merge

\`\`\`powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\\.venv\\Scripts\\python.exe scripts\\run_marketdata_2022_broad_quotes_v2.py --shards-through 15 --max-new-requests 2000 --max-observed-credits 2100 --workers 4 --authorize-provider-reads --confirm-paid-starter --confirm-private-internal-use; if ($LASTEXITCODE -ne 0) { throw 'Original quote campaign stopped. Preserve plan/intents/receipts; no blind retries.' } }
\`\`\`

Use only one authenticated workstation acquisition process, and do not publish provider response data to GitHub. The plan/receipt evidence from this run determines the next range and whether additional expiry/source coverage is necessary before further prices.


## Network-bound acquisition throughput tuning — 2026-09-27

The operator's initial V2 bulk historical quote campaign was launched with explicit \`--workers 4\`. Its measured CPU, RAM and USB SSD utilization were very low. This is expected because each original exact-OCC full-history GET spends most of its time waiting for external HTTP/network response; local compute and bytes are modest. The previously frozen source and quote plans, exact physical query key, D: paths and all original receipts remain unchanged. Do not terminate/relaunch the already running four-worker process merely to change its concurrency.

The next invocation accepts \`--workers 1..24\`, with **16 default** for this 2022 V2 CLI (versus four previously). The existing executor remains strictly bounded by the selected worker count and dispatches a new batch only after the whole prior batch is collected and verified. It does **not** automatically retry 429, timeout, ambiguous HTTP, quarantine or original intent. A bad original attempt preserves evidence and stops subsequent batches. Existing exact quote receipts are reused and only genuinely pending source-supported OCC histories can produce new GETs. Per-batch original paid intents, original body+receipt SHA, 4 MiB per response, D: category/free-floor reservation (\`workers * (4 MiB + 8192)\`), actual credit-header aggregation, observed-credit target and provider-remaining floor still apply. With 24 potential in-flight requests, an observed-credit target is a post-response stopping target, never a strict pre-response guaranteed billing ceiling.

MarketData's current official documentation states 50 simultaneous requests per account (not per local process) and suggests 20–40 maximum for a custom HTTP client. ATLAS caps this job at 24 to leave headroom for non-overlapping account activity, not to claim that 24 is optimal without actual response measurements. No other paid acquisition process should run concurrently. See https://www.marketdata.app/docs/api/rate-limiting/ and https://www.marketdata.app/docs/api/troubleshooting/too-many-concurrent-requests/ . Real-time per-batch output now includes configured worker count, batch size, batch duration, cumulative elapsed and actual newly attempted GETs/s. These performance-only values are **not** inserted into immutable source plan/receipt fingerprints. This tuning does not make CPU, RAM, or SSD usage a target.

If the current process finishes with zero pending, **do not repeat its already completed requests solely to use 16 workers**. If it reports \`PARTIAL_BUDGET_OR_CREDIT_FLOOR\`, resume the identical frozen V2 plan after a clean main update and explicit new request/credit budget; the original exact requests will be reused. If it fails ambiguously, inspect its original durable attempt/receipt first; do not blind retry. Future benchmark the observed GET/s and physical bytes, then set worker count based on evidence. No 09:35 executable fill/P&L, protected-holdout promotion or PAPER/LIVE authority.
