# V32 — SPY source-verified quote observation tape after exact-contract acquisition

## Latest workstation evidence

- V29 source selection: 411 frozen weekly SPY entry dates; 2,406 of 2,407 original stock-minute clocks physically present; 361 *provisional* one-pair ATM identities; 50 original-entry abstentions.
- Those 361 choices create **1,805** predetermined review uses (one through five XNYS sessions). Original exit source states include **550 matched pairs**, **1,176 both-right-absent** source responses, 8 missing review sources and 71 failing quote-quality/skew reviews. 2,352 distinct missing exact dated option-right requests prepared by V29.
- V30 paid source run: tests 12 passed; correct V29 immutable fingerprint preview; 80 original exact-right responses archived, 4 started-but-not-terminal ambiguous identities, 2,268 never attempted. No returned provider fault or invalid archive among first 80; unattempted identities can be resumed with existing V30 `--run`, preserving all original receipts. No automatic retry of the four uncertain IDs.
- V32 consumes **only** source material already archived at execution time and can run before/after V30 completions. It never calls ThetaData, stock/option publishers or brokers, never runs 10:01 trades, and does not reread 97 monthly SPY stock files. It is a precise link between acquired data and the future option account simulator.

## V32 source-only integration

The immutable original V29 report is verified by the now passing V31 two-level fingerprint validator. The V26 original reader verifies entry V12/V14 source eligibility and broad exit V24 archives. V30 receipt reader verifies each individual exact original provider SHA/gzip, status and query/plan binding. Only state `RAW_ARCHIVED_EXACT_CONTRACT_DIAGNOSTIC` supplies a price, and only if the full raw response contains the uniquely requested exact contract. A V30 response with **extra unrelated expiries/strikes** is preserved as the original lossless source, but V32 selects only the requested right/expiry/strike and continues to enforce V26 timestamp, spread, positive size and pair synchronization gates.

The frozen V29 identity is never reselected by later market price, completeness or liquidity. For every selected pair, exactly five predetermined 10:00 option review observations are classified as:

- `ORIGINAL_PAIR_QUOTE_MATCH`: both original rights already qualified under the V26 acceptance gate.
- `EXACT_SOURCE_RECOVERED_PAIR_QUOTE_MATCH`: a qualifying original CALL+PUT pair becomes observable only after verified V30 exact-right recovery.
- `MISSING_ORIGINAL_REVIEW_SOURCE`: no source was retained for that review day.
- `BOTH_OPTION_RIGHTS_NOT_AVAILABLE`, `ONE_OPTION_RIGHT_NOT_AVAILABLE`: incomplete retained original+exact rights, including uncertain paid dispatches and no-data outcomes.
- `PRESENT_QUOTES_UNQUALIFIED`: both rights observed but bid/ask, timestamp, displayed size, spread or leg sync fail the original fixed quote gate.

Every one of the five horizons preserves the **361** selected-pair denominator (no post-outcome deletion). For each originally selected pair/horizon an append-only *derived report* records original entry source identity, original review source identity, exact source IDs when archived, request terminal states, observed two-leg 10:00 ASK at entry and 10:00 BID at later review **only when both exact rights qualify**. An absent match retains `null` exit quote. The published tape is source-verifiable and intended as input for an eventually admitted execution model, **not** a historical filled trade tape or portfolio backtest.

Run the reader only when V30 has stopped or finished a campaign invocation (e.g. after its first 80 archived rights), not simultaneously with V30 writing source receipts. Later, run the reader again after additional V30 receipts have been durably written. Since it is derived, every invocation writes a new exclusive-create filename; previous reports and original source archives stay untouched. The report includes full source references, plan/source fingerprints, status/denominator reconciliation and a new research trial ledger registration.

## Workstation command (after green CI and V32 merge)

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    if ((git branch --show-current).Trim() -ne 'main') { throw 'ATLAS must be on main' }
    if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
    $py = '.\.venv\Scripts\python.exe'
    & $py -m pytest -q tests/test_options_native_spy_recovered_quote_tape_v32.py
    if ($LASTEXITCODE -ne 0) { throw 'V32 focused regression failed' }
    & $py -m scripts.run_options_native_spy_recovered_quote_tape_v32 `
        --plan data/research/spy_one_pair_exact_exit_demand_v29.json `
        --output data/research/spy_original_plus_exact_quote_tape_v32_first.json
    if ($LASTEXITCODE -ne 0) { throw 'V32 source tape report failed' }
}
```

If the file already exists, choose a fresh output path; never overwrite. Zero historical provider calls.

## Next beyond source observations

Build source-admitted and causally eligible prior-20 economic SPY return variance, PIT option IV/OI and dated rates/dividend inputs; lock the actual volatility signal at 10:00. Then implement a **separate** 10:01 executable-latency, spread and fee model with actual account equity, reserved capital, expiry/assignment and unresolved mark support. Never treat 10:00 observed bid/ask as an executable trade price; the 2026 protected holdout has already been viewed and cannot become fresh forward evaluation. Use V32 as *research evidence* for selected-contract continuity, not as trade profitability evidence.
