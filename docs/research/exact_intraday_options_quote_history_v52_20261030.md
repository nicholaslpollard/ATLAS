# V52 — Efficient exact-contract, same-session intraday option quote history

Date: 2026-10-30. This is a provider/source adapter, **not a trading strategy**, historical execution claim, simulator result or loss/profit promotion.

## Evidence for new capability

The official ThetaData documentation states that Options Standard supports historical tick-level options data and the existing `option_history_quote` SDK method can return every NBBO update for an exact option contract. It accepts an exact `date`, `expiration`, `strike`, `right`, `start_time`, `end_time`, and `interval` such as `1s` or `tick`. These source facts are distinct from any claim that its historical availability timestamps prove executable orders. Provider docs:

- https://www.thetadata.net/docs/operations_python/option_history_quote.html
- https://docs.thetadata.us/Articles/Getting-Started/Subscriptions.html
- https://www.thetadata.net/docs/operations_excel/option_at_time_quote.html

The provider warns that sub-minute **at-time** requests can be slow; requesting exactly one 0DTE selected right's contiguous same-day quote history once can avoid repeated at-time provider GETs to measure hypothetical +1/+3s action price and dozens of potential stop/target observations. Store the raw response with original SHA in the existing V38 compressed cache, then derive all multiple-strategy observations offline. **A source is not a fill.** An observed tick can still be unusable for a hypothetical order because of mismatched times, missing size, crossed market or spread.

## Scope implemented

- New `packages/providers/thetadata/client.py::option_history_exact_quote_tape` wrapper around **existing, pinned SDK 1.0.12** `option_history_quote`. Adds no dependency, no new worker/SDK method and no new authentication. Requires an exact underlying, a single explicit session, canonical original expiration, positive numerical strike, a single CALL or PUT, time range 09:30:00–16:00:00 with start<=end, and only `1s`, `tick`, or diagnostic `1m` granularity. An exact quote tape cannot request `expiration=*`, `strike=*`, `right=both`, or a multi-day universe. Date after expiration fails.
- The V38/V39 dynamic source path now permits that **single additional exact read-only source method** with original strict normalized query identity. Re-running the identical method/argument tuple reuses the compressed and fingerprint-verified archived original; new strike, expiration, single-session time slice or tick resolution gets a new source identity and may request a new source if missing. No blanket lifetime quote-call cap.
- Existing source bounds remain unchanged: **24 MiB raw response**, **250,000 rows per source**, and the storage floor. A quote tape exceeding those bounds is rejected and needs narrower contiguous time slices rather than silently truncated, forgotten, or credited as a complete observation. `1s` is an initial bounded observation choice, `tick` a more faithful but potentially larger record. Neither interval proves unobserved limit order fills or stop-trigger sequencing.
- Tests run fully offline using mock provider responses, verifying source SHA/cache hits/no duplicate request, different source IDs for changed time/interval, reject wildcard/expired/overnight/same-date-invalid source requirements, and no broker/simulation promotion. No paid API calls or credential access in GitHub CI.

## First bounded paid-source canary — operator handoff

`scripts/run_spy_v52_exact_intraday_quote_canary.py` is the first end-to-end one-contract, two-minute historical **source** request. The default known test scope is SPY, **2025-06-09** expiry and session, **604 CALL**, 09:35–09:37 ET at **1s** interval. This was chosen as an **arbitrary availability/SDK/schema canary**, NOT as a retrospectively selected first-breakout contract or a trade. It might return genuine no-data, insufficient entitlement, unsupported SDK time/interval semantics, or a source that cannot yet be independently qualified. The requester must not infer a profit or entry from an observed quote.

From the workstation on an up-to-date `main` after V52 is merged:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v52_exact_intraday_quote_canary `
  --output "data/research/spy_v52_0dte_canary_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

The command makes **at most one historical provider GET on cache miss**, with an exact same-contract compressed archive on D: via V38. Repeat identical requests hit cache with zero provider calls. Preview stores only the request, source SHA, row count, field names, a few timestamp examples and **three small bid/ask row previews**. It never dumps the whole source or displays provider credential text. It flags an expiration/strike/right/symbol discrepancy if the raw dataframe includes such columns, and records if per-row identity is not available. A request identity and successful provider status are not themselves first-publication, bid/ask tradeability or executable-fill proof. Send the **canary JSON and console output** back to ATLAS for the historical schema qualification and next original-breakout source acquisition. A nonzero exit means stop/diagnostic, not retry repeatedly.

## Strategy integration once merged

V51 #418 separately implements the source-only SPY 09:30–09:35 opening range and a one-long-option 0DTE quote-reference engine. After separately verified first breakout tick, generate a V52 **single-day exact contract quote tape** from just before first actionable tick to 15:30 ET, through `resolve_strategy_source_demands` in V39. If the one-day tape exceeds existing V38 capacity, divide into bounded non-overlapping segments that preserve all original timestamps, provider query and source SHA. A later adapter must read the archived full original quote sequence and decide **as of each action/evaluation clock** which values had actually become available; historical publication timing remains to be independently verified, and missing intrasecond data must remain unresolved. This can support:
- one-second vs three-second action-latency quote changes for the *same* contract;
- chronological stop-loss/target/3:30 time-exit decision references without refetching the same original contract for every policy variant;
- comparison of preserved MWF published ORB vs separately registered all-weekdays exploratory variants, without any hindsight strike re-selection;
- future exact multi-leg source tapes after proper SPXW/ETF instrument terms, collateral and settlement accounting are implemented.

This branch is deliberately independent of currently pending V50 #417 and V51 #418; there is no rerun of V47/V48 negative outcomes. **Actual readiness to run source-backed 0DTE history still requires the operator's workstation, active eligible ThetaData provider environment, underlying breakout time/tick evidence, and exact original quote receipts.**
