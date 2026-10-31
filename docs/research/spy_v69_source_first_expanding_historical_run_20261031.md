# V69: source-first expanding SPY 0DTE research cohort

## Why V69 exists
V67 completed exactly three new original provider source archives and verified all six selected option tapes in the June 9–20, 2025 SPY cohort. V68's full six-policy original source sensitivity shows that simply widening the adverse option ask tolerance to 2% admits losing trades and additional unqualified exit paths. The 1s/1% default repeats exactly, and the original June 13 position remains unresolved. This **is not** a basis to choose a winning policy from June. Expand historical cohorts, retain the existing signal/execution policy, and collect new original data with no skipped source requirement.

V56 previously generated new option contracts dynamically and cached original quote data, but it called legacy V38 directly (where prior provider failed/expired state may be retried automatically) and stopped a chronological account at the first unresolved exit, avoiding later independent date analysis. V65 independently surveys ten days but does not itself acquire the missing original source. V69 stitches the **existing frozen V65 strategy/signal/replay** into V39's safer streaming cache-first options-source runtime.

## Stages per consecutive historical window
1. Enumerate the weekday sessions in the requested range (no arbitrary overall date or candidate count cap). Divide into windows of at most 30 trading weekdays because V65's underlying original archive checks are window-scoped. A window length is not a source-request lifetime cap.
2. Run the original zero-paid-request V65 audit, verifying original native SPY minute source SHA, minute geometry, every completed-bar signal, selected expiry/strike/right and exact option tape requirement, and writing the complete, signed per-day **preflight**.
3. Yield **every selected exact option tape** to V39 even when previously cached: the runtime links each source to the strategy/candidate and returns SHA-verified cached originals or automatically performs a new ThetaData read-through archive. V39 keeps independently new requests flowing on error, protects uncertain same-query retries, and persists immutable exact-source receipts. It issues all new necessary supported requests; no frozen universe and no per-run source count cap.
4. Persist the V39 source census before further audit. Re-run V65 offline over the identical original SPY minutes. Require both pre/post signals, contract selection, native original source SHA and quote requirement to match. Censor any still-unresolved source requirement separately from a strategy's true price-drift/size rejection.
5. Emit independently signed source and quote-reference replay reports for each window plus an overall summary. Keep an unqualified open position **unresolved** rather than closing at zero or carrying arbitrary future cash forward. **No live broker orders or validated alpha claims**.
6. For an underlying SPY month absent from the local original checkpoint registry, emit `UNDERLYING_OR_ORIGINAL_PREFLIGHT_BLOCKED`, continue other independent windows, and require original stock data via the relevant historical source adapter; do not invent bars or skip its affected options. A future integration must wire automatic underlying stock acquisition and the broader Greek/OI/news/rates/dividend requirements into a universal typed source queue (GitHub Issue #437). This V69 component does not falsely claim the whole cross-provider system is already integrated.

This scope is a **genuine new strategy-driven source-acquisition workflow**, not merely an offline chart. It does not itself produce a trustworthy cumulative account when unresolved exits persist, and it does not implement prior-fold training or out-of-sample validation.

## Initial workstation procedure
Start with **June 23–30, 2025**, a continuation inside the same June monthly native SPY source archive already SHA-verified by V65/V67. This avoids guessing whether a different month's underlying checkpoints have been installed, and causes V69 to request genuinely new exact contract tapes automatically for fresh signals. If the June archive does not contain accepted minute bars for one of those days, record the source blocker rather than claiming no trading signal. A later multi-month run can extend to other verified native stock months. This test may make **new paid ThetaData requests** for eligible selected contracts, so ensure the Options Standard provider is active.

```powershell
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
$py = '.\.venv\Scripts\python.exe'
$testTmp = Join-Path $env:USERPROFILE ('at' + [guid]::NewGuid().ToString('N').Substring(0,4))
& $py -m pytest -q --basetemp $testTmp tests/test_spy_v69_source_first_multimonth_census.py tests/test_strategy_options_source_runtime_v39.py tests/test_spy_v65_full_june_offline_simulator_readiness.py
if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed; no provider requests' }
$stamp = Get-Date -Format yyyyMMdd_HHmmss
& $py -m scripts.run_spy_v69_source_first_multimonth_census `
  --start 2025-06-23 --end 2025-06-30 `
  --output-dir "data/research/spy_v69_june_extension_$stamp"
if ($LASTEXITCODE -ne 0) { Write-Warning 'Inspect saved V69 per-window blockers and source receipts before other requests' }
```

Choose the month based on verified local original SPY source inventory, not guessed coverage. Do not issue the same exact ambiguous query again; completed sources are re-used. All partial original receipts must be retained for the next run. If no underlying original month exists, building the historical SPY stock data adapter becomes the next critical step before claiming automatic end-to-end acquisition.

## Acceptance tests
- Changed candidate right/strike/date dynamically yields new exact source and retains strategy/candidate lineage.
- Prior FAILED_RETRYABLE/IN_FLIGHT does not silently re-dispatch; new independent sources continue.
- Pre/post source replay does not change underlying bar SHA, generated contract, signal timestamp, source query ID or immutable record identities.
- A missing selected source counts as a **source blocker**, not as a genuine no-entry execution decision or a negative trade result.
- Missing SPY native month remains a visible underlying-source integration blocker with zero option provider calls; other windows remain processable.
- No overwriting prior output, no broker orders, no false cumulative profit; per-window progress and request count visible.

The first run should review new source states, filled vs no-entry vs unresolved outcomes, and the value of expanding the research horizon after source readiness, without mining the initial June 2025 sample for an optimal policy.
