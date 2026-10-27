# V27 — Offline SPY fixed-exit quote-path sensitivity

## The actual objective

Get from the completed SPY 411-entry / 1,570-exit source archives to a practical strategy laboratory without restarting large ThetaData collections. The user requested running a strategy with several parameters and eventually running multiple strategies in one account. V25 (PR #392, merged) established synthetic mechanics of a bounded sweep and single shared-capital account. V26 (PR #393) added original quote matching with immutable hash/source checks and a preregistered research ledger. V27 is a narrow, honest next step: **five real historical source-observation fixed holding-period comparisons, each with three cost assumptions**, all on the same preselected entry cohort. It is not the final historical execution simulator.

## Frozen, source-preserving experiment

- Historical original weekly SPY entry schedule: 411 decision dates, 2018–2025; V26 source provenance used unchanged.
- Selection is **all** same-strike/expiry CALL+PUT pairs with entry-time 30–45 calendar DTE, positive two-sided prices and displayed sizes, <=30-second quote age, <=15% spread per leg and <=1-second pair clock skew. There is **no** PIT SPY spot or American IV bound yet, so this is NOT the options-native SPY ATM straddle selector.
- Fixed strategies/scenarios: examine the identical eligible contracts after 1, 2, 3, 4 or 5 subsequent XNYS sessions. **No future price or availability affects entry or the predetermined exit-review date.** Only the exact originally paired contracts count as matched; no ATM reselection, no expiry switching.
- Out-of-range DTE expirations from original provider responses stay on disk. Local DTE is computed for individual entry and later review; the DTE of held contracts naturally declines between them. Extra returned expiries do not invalidate valid originally in-range candidates.
- Example illustrative cost assumptions: per-contract per-side fees $0.00/$0.65/$1.30; four commissions are charged in hypothetical two-leg entry/exit pricing. Entry is **observed 10:00 ASK**, exit **observed 10:00 BID**. Neither is a historically proven eligible/filled 10:01 order. No capital portfolio, equity marks, option assignment, slippage, or market impact is represented.
- Each of five scenario reports retains `eligible_entry_pair_count`, `source_observed_same_contract_pair`, `unobserved_due_to_missing_review_source`, `unobserved_due_to_contract_absence_or_quality`, historical observation coverage, year breakdown, fee-stressed conditional mean/median and positive fraction. **Each scenario preserves exactly the same original entry-pair denominator; the missing side is not assigned a fabricated P&L.**
- The data may be read offline without providers/brokers. Before reading future prices, V27 verifies the V26 frozen pilot/trial registrations and appends its own one-time research trial to the existing D:-bound hash-chained strategy ledger. Does not touch the previously consumed 2026 master holdout.

## Workstation command after PRs #393 and #394 are merged and CI passes

```powershell
$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main' }
if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
git pull --ff-only origin main
if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
$py = '.\.venv\Scripts\python.exe'
& $py -m pytest -q tests/test_options_native_original_pair_diagnostic_v26.py tests/test_options_native_fixed_hold_quote_sweep_v27.py tests/test_strategy_sweep_fastlane_v1.py
if ($LASTEXITCODE -ne 0) { throw 'Targeted tests failed' }
& $py -m scripts.run_options_native_fixed_hold_quote_sweep_v27 --output data/research/spy_fixed_hold_quote_sweep_v27.json
if ($LASTEXITCODE -ne 0) { throw 'Quote sensitivity run failed; save console output' }
```

If the report filename already exists, choose a new name; no overwrite. The script prints all five fixed-hold scenarios, zero provider calls, explicit denominators and fee-conditioned indicative quote economics. On its first run it appends registration metadata, then reuses it. This is historical source *research* rather than trade/account profitability.

## What still blocks a genuinely useful strategy simulator

1. Attach the 10:00 decision point-in-time SPY underlying/21-close economic return inputs and the American rate/dividend/IV/OI data; freeze one ATM option pair using **entry-available** evidence, not every possible contract or future prices.
2. Separate historical source *observation* from executable 10:01 option *order events*; preserve unknown availability and unfilled positions. For a selected pair, query any missing exact-contract follow-up prices while the active subscription allows; the stored `strike_range=2` daily near-spot chain can omit an originally purchased contract that has moved out of that range.
3. Implement a chronological marked account with multi-leg actual fill assumptions, early exit/expiration/assignment, costs, duration, risk budget, and missing terminal equity as NULL. Compare weekly/monthly/yearly outcomes, full drawdown and sensitivity to costs.
4. Reuse V25 sweeps over admitted historical event tapes, keep complete experiment ledger and independent chronological/forward evaluation; combine future shortlisted strategies under shared capital, including cross-asset allocations.

The success criterion for the next user operation is **coverage of exact originally selected contracts at all predetermined exit checkpoints and an honest cost-sensitive indicator**, not a positive retrospective mean.
