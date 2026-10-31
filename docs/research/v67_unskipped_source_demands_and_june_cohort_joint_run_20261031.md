# V67 — no silent missing option-source demand; combined acquisition and replay

## User requirement (October 31, 2026)
Every strategy/system must expose the exact data required to reach its decision or manage its position. New contract selections, parameters, time windows, historical option quote tapes, option Greeks, quote/OI surfaces, spot prices, prior IV, rates/dividends, corporate actions, and future provider/source families must never be silently treated as absent or assigned a zero-return trade simply because the cache does not yet have them.

### Existing wired route
V39's simulator-facing streaming source coordinator already accepts arbitrarily many **ThetaData** option demands for all six V38 supported methods: exact quotes, exact intraday tapes, at-time quote surfaces, hourly surfaces, historical open interest, and first-order Greeks. Strategy changes must produce new exact requirements; they cannot reuse an unrelated strike, expiration, right, timestamp, or Greek model setting. Each requirement is written to durable strategy/candidate/purpose/query lineage in V38's source SQLite index. On an unregistered exact query, the existing provider bridge is called automatically. Verified immutable originals are reused. Explicit no-data and exceptions are **unresolved** rather than a hypothetical fill or flat P&L.

V67 hardens that shared route: **if** the original query has state `FAILED_RETRYABLE` or `IN_FLIGHT`, its dispatch may have been received even if the SDK failed or the lease is stale. V39 now logs `SOURCE_RECONCILIATION_REQUIRED`, refuses that identical ambiguous request and proceeds with other independently specified requirements when `continue_on_error=True`. A newly missing source still generates a normal paid read-through request; a newly changed contract or Greek query is not suppressed by a prior different failure. A failed newly dispatched request is logged as `SOURCE_DISPATCH_OUTCOME_UNKNOWN` and cannot be auto retried through V39 on the next run. The original V38 receipt remains intact for reconciliation. Never print raw provider error strings or access tokens in progress.

This is a **specific supported-path improvement, not a blanket claim that every future provider is automatically integrated.** The cross-provider strategy-runner demand queue and provider adapters for stock tick/quote, point-in-time market news, external corporate actions, and other distinct data services require explicit integration. Unsupported data classes must be reported as **unresolved integration requirements**, not discarded or silently approximated. An on-demand query that would exceed safe *single-response* byte/row bounds should be chunked into independently verifiable source requirements; there must not be an arbitrary aggregate request cap or ignored later chunks.

## V67 one-command SPY June 9–20 workstation acceptance
`scripts/run_spy_v67_acquire_then_offline_reaudit.py` executes the already accepted V65 source fingerprint and exact three V66 missing requests, then reruns the immutable V55/V65 ten-day **standalone, not chained-cash** 0DTE completed-minute breakout source audit. It records a signed combined summary and retains V66 per-exact-query intent/source receipts and the full new V65 event report. If one independent provider request fails ambiguously, V66 attempts the **other distinct** needs; the offline V65 audit still runs against whatever original sources were successfully verified. A source is not counted as a losing or flat trade while missing.

### Single guarded PowerShell test/acquisition/replay command
On the development revision or after merge into `main`, with only one ThetaData source session active:
```powershell
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
$py = '.\.venv\Scripts\python.exe'
& $py -m compileall -q packages/simulation/strategy_options_source_runtime_v39.py scripts/run_spy_v66_three_missing_exact_tape_acquisition.py scripts/run_spy_v67_acquire_then_offline_reaudit.py
if ($LASTEXITCODE -ne 0) { throw 'ATLAS compilation failed; no paid source requests' }
& $py -m pytest -q tests/test_options_on_demand_source_cache_v38.py tests/test_strategy_options_source_runtime_v39.py tests/test_spy_v65_full_june_offline_simulator_readiness.py tests/test_spy_v66_three_missing_exact_tape_acquisition.py tests/test_spy_v67_acquire_then_offline_reaudit.py
if ($LASTEXITCODE -ne 0) { throw 'ATLAS regression tests failed; no paid source requests' }
$stamp = Get-Date -Format yyyyMMdd_HHmmss
& $py -m scripts.run_spy_v67_acquire_then_offline_reaudit `
  --v65-report 'data/research/spy_v65_full_june_offline_20261031_121350.json' `
  --output-dir "data/research/spy_v67_joint_$stamp"
if ($LASTEXITCODE -ne 0) { Write-Warning "V67 may have preserved partial valid original sources; inspect the generated summary.json, do not re-run ambiguous exact requests blindly" }
```

V67 does not override ThetaData SDK worker's 180-second response timeout and performs no broker orders. The original June 13 unresolved position remains unresolved if no causally qualified exit exists; V67 does **not** manufacture cumulative account earnings or establish alpha. Missing data that remain must feed subsequent distinct source requirements and independent periods.

## Follow-on integration
1. Merge V65, V66 and V67 only after passing CI and targeted Windows acceptance (or keep V67 as a stacked PR until its base is accepted).
2. Execute V67 once to acquire June 16/18/20 option tapes and compute new standalone results from the SHA-verified originals.
3. Link the generic source-demand discovery path into the actual multi-session simulator before each required feature and every exit observation. Build adapters for additional real provider families; report unsupported ones as pending instead of skipping.
4. Evaluate the corrected SPY strategy and other strategies across new independent historical windows. Train adaptive trade exits only from earlier folds; do not optimize from the already-observed June 9 outcome. Preserve weekly/monthly/annual after-cost economics and censored periods separately. Never promote quote-reference P&L to actual broker fills.

**Important**: A V39 source-use record is not proof the information existed at the historical strategy decision time. The original feed publication, quote clock, historical OI reporting time, underlying bid/ask, rates/dividend evidence, liquidity/size, and execution-price/slippage gates remain independent.

## Acceptance and CI authority

Synthetic Linux/Windows CI validates source routing, guarded ambiguity, complete exact-demand coverage, and launcher behavior without real provider access. The actual ThetaData workstation run is still required to qualify the new original June 16/18/20 quotes and any resulting simulated trade. A green CI test is not equivalent to completed historical market data acquisition.
