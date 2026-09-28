# Accepted stock/news to PIT options quote bridge (2026-09-27)

## What is implemented

The historical stock/news/option lab is **not yet an accurate five-year account-level options simulator**. This stage closes the disconnection between accepted stock/native-open/news cases and existing exact option quote acquisition. It is an offline D:-bound evidence compiler, not another chain-audit campaign and not a simulated trade.

Source inputs: original signed 14,902 accepted stock/news cases, independently verified native raw next-day stock OPEN, original 2022/2025 source crosswalk, 7,646 physical-source demand and accepted original global cache overlap. The source/2022 plan identities are fixed by the accepted research receipts. The compiler:

- Retains all original case IDs and decision times. No unseen 2026 historical stock signals or 2026 protected outcome reads.
- Reuses the original 2022 structural CALL selected symbol **only if it is in the immutable 6,398-symbol original quote-plan index**; no 2022 raw quote body is reread at selection. Actual quote use later independently verifies the original exact receipt/body.
- Selects nearest-to-original-raw-open CALL and/or PUT from verified **previous-session** chain raw bodies, tie-breaking to the out-of-the-money strike. No same-day EOD quote, future volume, OI, favorable outcome or later Greeks is used for contract selection. Original 2025 pilot CALL pointers are checked against the original complete chain SHA/body.
- Reuses any newly acquired exact original local source and the 71 previously verified complete global overlaps, including the accepted original query strike window. An original attempted-but-uncertain query does not fall through to another provider request. Original exact-query 404 remains an exact-query gap, not absence of any option.
- Reports unavailable older-2021 source, expired/out-of-policy, no chosen right, missing chain and 17 protected future entry deferrals as explicit gaps, not synthetic fills.
- Writes one immutable full-case/right coverage selection and deduplicated exact OCC/from/to quote demand, both under the D:-bound options manifests directory. Default is both rights, but the operator can plan only CALL or only PUT. This is demand, not a paid request.
- Reuses the existing full-series quote cache executor and its SHA-bound local bodies for future capped paid calls. The initial source bridge makes **zero** API calls. C: continues to own core stock data/compute; D: owns downloaded option/news evidence and derivatives.

## One free operator command

From ATLAS root, after merge:

~~~powershell
& { $ErrorActionPreference = 'Stop'; if ((git branch --show-current).Trim() -ne 'main') { throw 'Not on main.' }; git pull --ff-only; if ($LASTEXITCODE -ne 0) { throw 'Git pull failed.' }; & .\.venv\Scripts\python.exe scripts\prepare_multiyear_option_quote_sources_v1.py --rights both; if ($LASTEXITCODE -ne 0) { throw 'PIT quote-source bridge stopped; paste complete output.' } }
~~~

The command prints its source selection path, quote-plan path, original 14,902-case denominator, missing statuses, selected CALL/PUT identities, exact quote series to acquire, and D: free space. **No provider token or payment approval required.** The generated exact quote-plan JSON may be used as --plan input to the existing run_multiyear_demand_quote_cache_v1.py, initially without paid flags for an offline reuse/availability census. Do not run overlapping provider jobs; historical quote acquisition requires independent authorization and a current observed credit budget. There were only 487 credits in the last observed live source run.

## What remains before a true option-trade backtest

1. Fill missing exact series from the frozen plan with bounded provider calls and persistence; use original 2022 full 6,398 CALL histories unchanged. A 1,114-credit chain campaign acquired 1,116 complete chains and 63 exact no-data, but did **not** download full selected OCC series.
2. Normalize original two-sided historical EOD option observations alongside same-session stock and conservative PIT news into a common-clock source adapter; never turn a later EOD row into original 09:35 fill. The current 2026 accepted replay is not available and the older 2021 rolling-window region is missing; show six-year coverage separately and never call it a complete 2021–2026 result.
3. Implement account-level fill assumptions using ask to enter, bid to exit, no crossed/no quote fills, contract multiplier and actual adjustments, spread/slippage/commissions, capital/margin constraints, timing, stops, expiry handling, costs and drawdowns; record no-fill/unresolved exit. Local IV/Greeks need matched raw stock, exact timestamp, historical rates/dividends and independently checked standard deliverable. EOD scenario results are not historical 09:35 execution.
4. Evaluate strategy hypotheses and tuning across chronological DEVELOPMENT/walk-forward regimes, then protect the original holdout. Do not force or target a return percentage.

The architecture is: stock/news/native-open → PIT contract selection → verified D: quote cache → common-clock observed source → offline account simulator. Missing data should be requested **once per immutable exact series** by the preparation/acquisition layer and saved to D:, not one GET per candidate stop-loss or backtest iteration. All paid requests are explicit and receipt-bounded; no broker/PAPER/LIVE authority.
