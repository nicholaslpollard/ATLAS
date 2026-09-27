# Integrated stock + news + options laboratory — six-year switch (2026-09-27)

**Target:** January 2021 through the last fully completed 2026 market session, with six visible per-year coverage reports. Do not confuse an accepted 2022 source census with a general six-year backtest. The 2022 work is reusable historical proof-of-process, not the chosen simulator horizon.

## Two separate operations, one frozen dataset per experiment

1. **PREPARE:** Fix the stock-signal cohort, decision calendar, desired option right/expiry/strike rule **before seeing option future liquidity or outcome**. Resolve each required local source against original receipts, including the accepted 2022 6,398 exact-CALL corpus and limited 2025 pilot. Produce deduplicated missing requests. The historical provider has a rolling five-year entitlement: as of 2026-09-27, the approximate earliest eligible day is 2021-09-27, so 2021-01-01 through 2021-09-26 is explicitly a provider gap, never silently omitted. Different licensed existing data may close it. 2026 is YTD, not a future full year. Freeze the resulting source manifest, raw-body SHA, coverage/missing statuses, times and contract identities. Only this operation can use external APIs and only under separate operator authorization.
2. **SIMULATE/TUNE:** Use the exact frozen local source manifest, offline, across all years with a common decision/entry/exit clock. Run stock, CALL/PUT and abstain expression scenarios from the **same** signal set and portfolio capital schedule; use actual observed quote side and source time or explicitly report unfilled/missing. Vary exit, DTE, delta, allocation, regime and news rules without rerequesting or changing source evidence. No outcomes from previously consumed master-protected intervals may be called a fresh holdout.

Do not fetch one quote per simulated trade or rerun the entire five-year acquisition with every parameter change. Acquire quote **series** once by exact OCC/from/to identity; reuse prior overlapping verified series when actual date/symbol coverage permits. Historical option-chain cost is per 1,000 contracts returned and historical quote series per 1,000 quote observations returned, not per iteration. Source gaps receive explicit entries; never pick a future-liquid alternate based on subsequent observations.

## Current, conservative credit guard

The user reported **fewer than 2,000 MarketData credits remaining today**. No code in this PR spends any: the scope planner and Greeks module have no network client. The planning contract defaults to zero requests and caps a future *separately authorized* preparation at at most 250 requests/250 observed credits, with an asserted 500-credit remaining reserve. A production worker must additionally verify actual provider credit headers and in-flight worst-case exposure, and must not allow concurrent unrelated paid processes to share the account budget. The plan itself never authorizes a request. Errors/unresolved intent preserve original bytes and do not retry automatically. A combined cap for both chains and quotes and storage preflight is required before any new paid year-acquisition entrypoint.

## Mathematical model boundary

MarketData historical chain and quote series return null historical IV/Greeks. \`packages/simulation/historical_option_greeks_v1.py\` now derives a **European-equivalent** Black–Scholes–Merton implied volatility from a genuine historical two-sided quote midpoint, matching as-traded underlying price and expiry. It outputs delta, gamma, daily theta, vega per one absolute vol fraction, and rho per one absolute rate fraction. It demands explicit historically appropriate risk-free and dividend inputs with source IDs, verified standard deliverable and raw price basis. If the quote is missing, crossed, expired, not invertible or adjusted without verified deliverable, the result is missing/fail-closed; Greeks are **never** fabricated from stock returns.

This is a research feature, not an American equity option early-exercise model or a substitution for an observed executable bid/ask. Follow with American/binomial or numerical early-exercise treatment for dividends/puts, contract adjustment/corporate action terms and realistic commissions/fees before claiming accurately simulated option P&L. Match observation times and underlying source prices. Option EOD entry cannot be inserted at original 09:35; qualify independent intraday option quote snapshots for that strategy, or re-time both stock and option entries to available later EOD observations.

## Immediate implementation steps from here

The existing 2022 source-only stock/news/option casebook PR #266 is a useful narrow provenance join, *not* a blocker to selecting a six-year scope. Build general source adapters for 2021, 2023, 2024, 2025 and 2026 with explicit missing/entitlement statuses and a unified record schema. Reuse verified existing receipts first. Join normalized PIT-safe news by original information time, never final article text backdated to initial publication. Match dated native stock marks and option ask/bid/expiry economics. Build the account-level common-clock comparator, then a repeatable tuning CLI/dashboard.

**Zero-credit scope preview:**

\`\`\`powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main. Stop.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed. Stop.' }; & .\.venv\Scripts\python.exe scripts\plan_multiyear_stock_news_option_lab_v1.py; if ($LASTEXITCODE -ne 0) { throw 'Six-year offline planner stopped; do not run paid acquisition.' } }
\`\`\`

MarketData license is subscription-bound: the ability to use cached downloads offline during a valid subscription does not confer permanent retention after cancellation without a different written agreement.
