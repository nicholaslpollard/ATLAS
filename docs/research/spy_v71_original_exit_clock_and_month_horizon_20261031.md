# V71 — original source continuity around invalid exits, and native SPY horizon catalog

## Evidence accepted from the workstation
On Oct 31, 2026, the user executed the combined V70/V69 acceptance:
- All **29 targeted tests passed**.
- V70 June 23–30 original quote-reference account: **6/6 days resolved**, $25,000 → $25,530.20, four closed trades, two Tue/Thu weekday exclusions, original fees and daily signed receipts validated, **no new provider requests** and no broker orders.
- V69 June 2–30 original source-first cohort: 21 weekdays, 13 selected M/W/F option contracts, **3 new exact ThetaData historical quote-tape acquisitions**, 10 existing original option tape SHA-verified cache hits, all **13/13 original sources archived**, no blocked/missing source.
- Replayed day results: **8 closed quote-reference trades**, **3 valid price-drift NO_ENTRY**, **8 weekday-filter NO_SIGNAL**, **2 genuinely unresolved positions** (June 4 and June 13). The eight individually closed trades total **+$349.30**, but *this is not June's cumulative cash result*: an unqualified open June 4 position prevents chronological settlement past that date. V70's smaller June 23–30 cash ledger is a separate complete and valid hypothetical interval, not an unrestricted monthly track record.
- Original full-June V69 report SHA: `0b8379ee99238bfde3c4230e74f7d8c9412c3fece899f3f0e1e3b3c75a18d7dd`. The uploaded preflight/replay/source/chunk/root source archive fingerprints and 21 nested per-session replay fingerprints were independently verified.
- June 2 590 CALL: -$219.90 closed at 09:50:33 via -50% stop. June 4 598 CALL: original entry $1.23 ×4, **unresolved exit**. June 6 599 CALL: -$182.60 via -50% stop. June 13 598 PUT: original entry $1.72 ×2, **unresolved exit**.

## Source anomaly finding
Both open positions have a recorded `EXIT_SOURCE_REJECTION` with `QUOTE_SPREAD_ABOVE_15_PERCENT` at **exactly 2025-06-04/13 10:00:01 Eastern**, each following an accepted original 10:00:00 quote. This common moment is not proof of a provider bug. It is a possible clock boundary or market-data quality pattern worthy of one bounded, original-only audit before changing simulator execution rules. ATLAS must not substitute a later price for a failed current quote, invent an exit or carry unknown cash.

V71 reads the original SHA-verified exact quotes for **only those two dates** using the V38 read-only cache reader. It confirms full V69 original signed parent and all subreports, the same selected exact provider request, source SHA, original entry and recorded rejected row index/time. It examines the original **five seconds before through sixty seconds after** the rejection. For each observed quote it saves raw bid, ask and sizes, qualification reason, and whether a **diagnostic-only** later qualified bid lies above the original 100% take-profit or below the original -50% stop threshold. This is *not* a valid fill assumption or a revised trade. No provider calls and no repeated ambiguous same-query dispatch are issued. A missing or changed original option archive is a **source acquisition required** blocker.

## Native stock-month inventory
In the same run, V71 discovers physical V2 Alpaca SIP native `1m` checkpoint month directories, uses the repository's complete-native metadata reader scoped to each month, and records whether there is exactly one SPY native unit with canonical and raw originals present. The catalog is a **preflight candidate inventory**, not an independent full SHA certification: **V69 itself must verify both full original source hashes on each chosen month before it can request any options data**. Missing original stocks or invalid checkpoint metadata remain visible blockers. No arbitrary universe/candidate cap or new monthly data provider call is introduced by the inventory.

The resulting report allows a subsequent **multi-month V69 source-first historical run** to select observed, actually available underlying SPY months and automatically acquire missing exact 0DTE options tapes for those months, instead of restarting repeated June simulations or guessing months.

## One guarded workstation command (original-source read only)
Run from the V71 reviewed GitHub revision after CI acceptance, or from `main` after merge:

```powershell
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
$py = '.\.venv\Scripts\python.exe'
$testTmp = Join-Path $env:USERPROFILE ('at' + [guid]::NewGuid().ToString('N').Substring(0, 4))
& $py -m pytest -q --basetemp $testTmp tests/test_spy_v71_original_exit_clock_and_month_catalog.py tests/test_spy_v69_source_first_multimonth_census.py tests/test_spy_v70_causal_portfolio_ledger.py
if ($LASTEXITCODE -ne 0) { throw 'V71 regression test gate failed; source evidence untouched' }
$stamp = Get-Date -Format yyyyMMdd_HHmmss
& $py -m scripts.run_spy_v71_original_exit_clock_and_month_catalog `
  --v69-folder 'data/research/spy_v69_full_june_20261031_134145' `
  --expected-v69-fingerprint '0b8379ee99238bfde3c4230e74f7d8c9412c3fece899f3f0e1e3b3c75a18d7dd' `
  --output-dir "data/research/spy_v71_exit_clock_and_native_months_$stamp"
if ($LASTEXITCODE -ne 0) { Write-Warning 'Preserve original files; inspect V71 blocker without repeating provider calls' }
```

The output directory contains signed `exit_2025-06-04.json`, `exit_2025-06-13.json`, `month_catalog.json`, `summary.json`. It requires **zero provider or broker calls** and never edits original V69 or V70 files.

## Next simulations
Select two or more earlier native SPY months supported by the catalog and run existing V69 source-first windows over them, with the same 1s/1% rule, full SHA verification and automatic exact ThetaData option tape acquisition. Preserve every candidate, rejection, action quote, exit and unresolved source. Build V70 chronological cash for complete source-qualified intervals and **stop** at the first unresolved account exposure. Only after sufficient prior-fold samples exist can strategies be fit and evaluated on independent later folds by weekly/monthly/yearly profitability, with realistic execution costs, partial fills, slippage and provider latency assumptions.

The user requirement still stands: all genuinely needed sources—including Greek inputs, open interest, historical rates/dividends, news and stock bars—must be acquired by their connected adapters or recorded as explicit blockers, never silently treated as no-trade outcomes. The all-provider integration is tracked under Issue #437.
