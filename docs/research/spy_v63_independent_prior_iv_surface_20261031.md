# V63 — independent prior-option surface capture, 2025-06-13

V62 workstation succeeded with **29/29 tests**, **one historical Alpaca SIP stock-quote page / 1,467 original SPY observations**. At the June 13 2025 10:00:01 ET target, the latest past-only stock bid/ask was **$598.63 × $598.88**, age **0.006825872 s** (the selected NBBO has a relatively wide $0.25 spread, so its market conditions must still be vetted). The source bytes were saved unchanged with SHA-256. The underlying stock quote is an **independent pricing input**, not an option fill or independently established option IV.

June 13 previously failed because the actual SPY 598 PUT **sell bid** was $1.05 ×2 versus ask $1.60 ×5 (41.5% relative spread) at 10:00:01. The prior bid of $1.70 one second earlier is not a substitute execution price; it does not independently establish the $1.05 as a bad bid.

## V63 source acquisition design

A single **prior** SPY option surface, via the existing approved V38 provider read-through cache, for **2025-06-13 at 09:59:59 ET**, two seconds before the suspect sell bid. Exact request: `option_at_time_quote_surface(symbol=SPY,date_et=2025-06-13,time_of_day_et=09:59:59.000,right=put,max_dte=1,strike_range=3)`. Scope deliberately keeps original put 598 excluded from all independent IV calibration. 0DTE put quotes at other strikes can be inspected if physically present, complete, time-qualified and bid/ask sound. Source call uses read-through cache: verified existing SHA archive reused, otherwise one historical ThetaData options source GET, immutable raw canonical bytes compressed on the external options drive. No broker orders.

Prior to any paid call, the script verifies V62 summary fingerprint, all original Alpaca response pages' raw SHA and row counts, and chooses **another** SPY source quote no later than 09:59:59, at most 2 seconds old, from that same verified historical window. The 10:00:00.993174128 stock quote is *future information* for the 09:59:59 calibration and must not leak into prior-IV estimation.

The original ThetaData return can include unsuitable expirations, strike scopes, stale clocks or quotes with wide spreads. V63 categorizes those **without** assuming the SDK `max_dte` filter actually enforces 1 DTE (previous ATLAS work encountered uncertain SDK DTE forwarding). It reports original expiry strings, row field names and counts, excludes the original 598 put and any after-09:59:59 observation, and never uses one suspicious midpoint to validate itself.

The V63 report is SHA-fingerprinted, immutable and separately versioned. It reports **NOT_YET_CALIBRATED** independent volatility, **NOT_YET_QUALIFIED** historical risk-free rate/dividend as-of, and no fair-price/exit/P&L assumption. Original V56 V57 V58 V59 V60 V61 V62 evidence untouched.

After observing the V63 report:
1. Confirm actual alternate 0DTE puts at multiple strikes were available and time-qualified **strictly before** the sell decision, and reverify each original source archive identity.
2. Establish valid expiry timestamp and historical risk-free rate/dividend observations, then calculate **prior-only** independent implied vol *range* from multiple liquid alternative contracts against matching contemporaneous SPY stock bid/ask, subject to uncertainty and noisy crossed bid/ask/size filters.
3. Feed separate prior IV band, a distinct current SPY NBBO, and original 598 put quote into V60 buy/sell side-aware BSM. Report side-specific over/under fair range while retaining valid execution-time quote, size and stop constraints. If independently sourced IV or stock condition publication is uncertain, ABSTAIN.
4. After post-mortem June 13, evaluate same rule on later independent cohorts, preserving rejection reasons and cash lineage; no historical broker fills or claimed alpha.

## Operator command

After V63 focused tests pass:

```powershell
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
& .\.venv\Scripts\python.exe -m scripts.run_spy_v63_prior_option_surface_source `
  --v62-summary 'data/research/spy_v62_spot_quote_20261031_100317/summary.json' `
  --output "data/research/spy_v63_prior_iv_surface_$stamp.json"
```

The script intentionally does **not** automatically switch to `right=call` or a wider `max_dte` query if no suitable prior quotes are returned; a second distinct scope would need its own query ID and archived source evidence.
