# ATLAS V76 — Five preregistered option-exit alternatives on the SAME original entries

**Status: proposed source-cache-only research experiment, NOT broker execution.** V75 verified that the original V74 SPY 0DTE opening-range breakout entry/exit combination is losing across 2025 January–June, with an observed 1-second quote-reference P&L of -$2,497.60, gross modeled profit factor 0.4695, 30 wins versus 25 losses and 17 previously censored exits now producing -$1,256.00. Future changes must not erase the original 38 matched V55 exits, any source no-data censoring or V74 original comparison. See [V75 six-month evidence](spy_v75_sixmonth_original_exit_economics_review_20261031.md).

V76 **pre-registers** a bounded experiment to examine whether losses reflect stop distances, profit-protection timing, or maximum hold rather than immediately spending extra ThetaData calls. It reuses the same original V55 entry signal, 1-second/+1% original entry condition, selected SPY contract, full original ThetaData quote tape, quantity and price/fee semantics. New decisions only see observations at or before their timestamp. The only changing dimensions are exit policy and the predeclared 1s/3s **exit action lag**, never a future quote or altered trade selection.

| V76 policy ID | Downside stop | Target | Trailing arm | Trail from high bid | Maximum hold |
|---|---:|---:|---:|---:|---:|
| `v74_control` | -50% option ask | +100% | +20% | 15% | 180 min |
| `defensive_25_75` | -25% | +75% | +10% | 10% | 120 min |
| `balanced_35_100` | -35% | +100% | +20% | 15% | 120 min |
| `fast_25_40` | -25% | +40% | +10% | 10% | 60 min |
| `runner_35_150` | -35% | +150% | +30% | 20% | 180 min |

*'Stop' and 'target' percentages are measured relative to original purchased ask option premium, not ETF spot or account equity; trailing arm and floor use only already observed valid option BID, no retrospective high/low. Model continues with the same 30-second invalid quote blackout, 60-second fresh quote gap limit, full size check and exit-intent clock. It never assumes a broker option market order or guaranteed liquidation. Stops can realize prices worse than the intended stop because of quote jumps and latency.*

## Storage, integrity and scope

Code: `packages/simulation/spy_v74_dynamic_sell_to_close_shadow.py` gains finite optional pre-registered thresholds while preserving the original V74 default observable output and signed fields. `scripts/run_spy_v76_registered_exit_benchmark.py` compares all **five policies × two exit latency settings** on each source-qualified date in one signed original V69/V73 month. Each of the 10 dated policy variants is retained as **full signed JSON gzip** with lossless bytes and per-journal SHA-256; no missing trade, rejected quote or reason code is silently dropped. Root monthly summary includes session roster, original source fingerprints and each scenario's complete daily journal references, signal status, modeled P&L, win/loss breakdown, source censor and nominal profit factor. No calls to ThetaData or any broker; source reader is read-only, SHA-verified and must fail closed if the exact archive is absent.

This is an explicitly **retrospective in-sample development sweep** over January–June 2025, not independent evidence that an alternative is profitable. These five variants were registered after inspecting V74 January–June outcomes. Do not rank a six-month-only winner as production-ready; independently test any strategy promotion against later previously unseen qualified sessions with a predeclared candidate selection procedure and realistic broker-order/cash constraints. March 31 continues to be original-source `NO_DATA_EXPLICIT` and must censor cash; other missing original dates cannot be ignored for account returns.

## After CI and workstation acceptance

A new V76 experiment should run against six already-acquired original months without paid GETs and preserve ten alternatives separately. Run one original month:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v76_registered_exit_benchmark `
  --parent-v69-folder 'data/research/spy_v73_202501_sourcefirst_20261031_145354' `
  --expected-v69-fingerprint '0cf0d09e1b9756c46a492e704a314e7d5b28e140aa19a1569568a1c9a6509d4f' `
  --output-dir "data/research/spy_v76_202501_$(Get-Date -Format yyyyMMdd_HHmmss)"
```

**Acceptance goals:** baseline V76 control 1s/3s must reproduce V74 same-day statuses/P&L; original contract and entry remain identical; all valid/invalid quote decisions retained and no policy can claim a broker fill; all ten policy/lag combinations produce signed journals with 10%-completed progress. The comparison must focus on worst-case loss distribution, trade expectancy, number of qualified exits, 1s/3s sensitivity and weeks/months losing. Subsequent candidates should include different entry families, not merely exit tuning on one entry signal.


## V77 multi-month acquisition + immediate variant comparison

`scripts/run_spy_v77_multi_month_source_and_exit_campaign.py` is the single-run wrapper for any explicitly selected inclusive range of months. It executes each XNYS-calendar-aware V73 monthly original stock SHA + V39 exact option cache-first acquisition, saves immutable original source receipts, then runs the **same preregistered 5×2 V76 exit comparison** on each newly source-qualified month. A blocked month is written as an independent signed receipt and does not suppress later months; ambiguous original provider requests are never blindly retried. Actual provider dispatch/cache/no-data counts are extracted from signed original source receipts, not inferred from a planned candidate count. Complete per-date/per-policy event journals remain gzipped on the workstation and the campaign prints stage-start and true 10%-completion progress. Outputs never submit orders, exercise options or claim Webull-versus-Alpaca fill differences.

For future previously uninspected periods, the five-policy roster is frozen by the commit/registry SHA before sourcing. Later results cannot be used to rewrite the policy roster and then re-label the same period as untouched. The monthly policy quote P&L sums are **not an integrated portfolio account**, and a missing/uncertain exact source leaves account proof censored. Early XNYS closes are time-qualified public calendar inputs: V76 proactively moves its *experimental* sell-to-close clock to 60 minutes before the official close and last permitted action to 55 minutes before; normal 16:00 sessions preserve V74's 15:00 / 15:05 clocks. November 28 and December 24, 2025 are exchange early-close sessions, not assumed ordinary 16:00 option expiries.

One-command **example** (run only after tests pass and merge or pinned reviewed commit):

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v77_multi_month_source_and_exit_campaign `
  --start-month 2025-07 --end-month 2025-12 `
  --output-dir "data/research/spy_v77_2025_h2_$(Get-Date -Format yyyyMMdd_HHmmss)"
```

This is the next **larger original-source simulator research campaign** rather than repeating Jan–Jun diagnostics and is appropriate only after accepting the registered risk/strategy scope. Since all five alternatives retain the *same* original M/W/F opening-range-breakout entry, this is a **multi-exit** race, not a comparison across distinct entry strategies or a broker-certified full portfolio simulator. Distinct entry families, stock fallback, multi-strategy cash/risk allocation and actual option broker adapter acceptance remain later integration work.
