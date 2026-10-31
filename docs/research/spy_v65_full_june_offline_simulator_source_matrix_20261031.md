# V65 — full June 2025 offline SPY simulator source/readiness matrix

## Why now

V64 verified (21/21 local tests, zero paid calls) that on **June 13, 2025**, SPY's as-of stock midpoint moved from **$598.020 at 10:00:00** to **$598.755 at 10:00:01** (+$0.735 / +0.1229%). SPY 598 PUT BID declined **$1.70→$1.05 (−$0.65 / −38.2%)**, while ASK declined **$1.81→$1.60 (−$0.21 / −11.6%)**, expanding the midpoint spread from 6.27% to 41.51%. The rising underlying is directionally consistent with a put declining, so an erroneous bid has **not** been established. Same-second Option 1s quotes have different timestamp semantics than real NBBO, and first-publication remains unproven. Original June 13 remains unresolved and must not be retroactively filled from subsequent quotes.

V63's 09:59:59 put surface hit ThetaData worker error after about 179 seconds; the 180s worker response timeout is consistent with but does not prove an exact timeout cause. V38 exact `FAILED_RETRYABLE` does not prove no provider dispatch. V63 now implements read-only exact-query preflight that prevents automatic same-query retries after `FAILED_RETRYABLE` / `IN_FLIGHT`. The original V64 SQLite receipt was `FAILED_RETRYABLE`. Avoid spending further provider requests on that same query without a documented resolution.

## Change of priority: complete opportunity universe first

V56 multi-session closed-bar SPY 0DTE simulator ran only five June 9–13 weekday dates before one unresolved position halted independent cash lineage. The remaining dates of the requested June 9–20 window have not been independently scanned and inventoried in that cumulative account. We want to know where follow-up market source fetching would actually matter **before** invoking paid ThetaData methods.

V65 is a separate offline-only stage using V55's unchanged closed-minute M/W/F ORB trading policy. For every calendar weekday June 9–20 inclusive:

- Resolves exactly one SPY original June 2025 native Alpaca SIP minute checkpoint and verifies both original canonical and raw-bundle SHA-256 **once per month**, using existing V56/V51 validators, not ad hoc data transformations.
- Runs causal `closed_bar_signal` only on Monday/Wednesday/Friday original minute bars; Tuesday/Thursday remain predeclared no-signal days. Holidays with no market data do **not** become simulated positions. Records each day's signal status, timestamp, first selected contract, reason codes, original per-session source warnings.
- Constructs the exact **V56/V38** 1-second option tape query for each signal without sending it: current day's selected symbol/expiry/strike/right, decision clock, until 15:30. Reuses the canonical source requirement normalizer and a stable fingerprint, so the user can see precisely which queries are archived, never registered, explicitly no-data, or uncertain.
- Reads the V38 exact SQLite source-receipt table only using URI `mode=ro`. Marks **every** scope non-retryable in this audit, especially `FAILED_RETRYABLE` or `IN_FLIGHT`. A source marked `ARCHIVED` must pass the original V38 compressed and canonical source SHA and exact requirement equality. No SDK worker construction, Alpaca requests or broker calls.
- For any already archived source, runs V55's exact original quote-reference replay **in isolation with a fixed $25,000 starting account**. For no source, reports NO_ENTRY (not a fabricated losing or flat trade); Tuesday/Thursday are NO_SIGNAL. All replay events, reason codes, source fingerprints, evidence and censor flags are persisted in the immutable SHA-fingerprinted per-cohort JSON report.
- These independent per-day replays deliberately **do not chain cash between dates**, and must not be summed as a cumulative realized equity curve. An unresolved day remains unresolved. No historical execution, no fills, no validated profitability claims.

## Expected decision after report

1. Count June 9–20 days with an independently observed signal and qualified archived options tapes. Identify the exact days where source is missing versus blocked by price/latency/quality (not all days require paid queries).
2. Determine whether the **original frozen V55 completed-minute ORB strategy** is worth further development based on how many available sessions are actually resolved, rather than trying to rescue June 13 alone.
3. Route still-missing source needs through the existing safe planner; do not repeat an ambiguous exact query and do not fetch all universe historical options without a data-usage reason. Then run first real multi-session after-cost simulator on independent periods, retaining orders/trade/no-trade reasons and weekly/monthly/annual profitability gates.
4. Test user-supplied research strategies in parallel using the same source-readiness and after-cost performance discipline. Results for the already reviewed June cohort must be labeled development/in-sample.

## Operator

```powershell
$stamp = Get-Date -Format yyyyMMdd_HHmmss
& .\.venv\Scripts\python.exe -m scripts.run_spy_v65_full_june_offline_simulator_readiness `
    --start 2025-06-09 --end 2025-06-20 `
    --output "data/research/spy_v65_full_june_2025_offline_$stamp.json"
```

One scan, one full original monthly hash verification, no provider calls or trade orders. `V65` does not change a frozen V56 source or optimize an in-sample strategy rule.
