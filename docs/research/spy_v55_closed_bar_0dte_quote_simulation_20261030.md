# V55 — First integrated SPY 0DTE historical quote-reference simulation

Date: 2026-10-30. **DEVELOPMENT / NOT VERIFIED BROKER EXECUTION / NOT PUBLISHED ORB REPRODUCTION.**

## Purpose

Run one complete original-source-to-chronological-cash account experiment instead of another disconnected options canary. Select **one original SPY 0DTE long CALL or PUT** only from verified native 1-minute stock bars, automatically acquire the **exact selected option** 1-second original quote tape into the existing V38 compressed read-through cache, model the entry and dynamic stop/target/15:30 exit, and preserve every decision/quote review in independent fingerprinted JSON and verifiable hash-chained JSONL. No broker requests or real fills.

This experiment is **newly versioned**, NOT the independently researched author's first-tick ORB configuration in V51, nor the original SPY long-straddle. Source-backed quote cash is useful development economics; it is not independently qualified PIT earnings or proof of execution/profitability.

## Predeclared development policy

- For this version use only Mon/Wed/Fri, with SPY opening high/low from complete 09:30–09:34 one-minute bars.
- Identify the **first completed one-minute candle CLOSE** strictly above that opening high or below that opening low, after 09:35. A minute's high/low alone never qualifies an entry, and a missing intervening bar blocks the first signal.
- As an unproved availability assumption, the completed bar is acted on **one second after candle end**. The original historical first-publication time is NOT independently verified; this remains a development sensitivity rather than a validated historical trade.
- Select same-day expiration, nearest-dollar ATM strike based only on the observed closing price of the signal bar; select CALL for an upward close, PUT for a downward close. Never use later option returns to choose the right, strike or decision.
- Require the exact selected original option 1s quote tape from decision clock until 15:30, with exact query identity, original SHA, bid/ask, displayed sizes, timestamp and <=15% bid/ask spread. One-contract/session source responses keep the existing 24 MiB/250k raw bounds; on size/schema error, do not fabricate zero or try a different contract based on its future results.
- Reference order: first observed eligible quote at or after the signal decision, within 30 seconds. Action quote is the first independently observed quote no earlier than +1s (or separately selected +3s), within a one-second observation window.
- Adverse option ASK rise between order and action is bounded at 1% baseline, with separately labeled 0.5% and 2% sensitivity. Prices are quoted reference, **not guaranteed broker fills**.
- Maximum **$500 premium** per entry using whole contracts; entry/exit modeled at option ASK/BID respectively, $0.65 per option contract on each side. Starting reference cash $25,000, one position and one opportunity on this session.
- Walk **every observed quote chronologically**, log all reviews, close on +100% option price (bid vs original entry ask), -50% stop, or the final qualifying 15:30 quote. A gap >60 seconds, invalid quote, missing needed exit size or absent fresh <=30s closing quote leaves **terminal equity null** and the actual trade unproved.
- Exact original source and full run are fingerprinted. A sibling immutable JSONL event ledger includes manifest, all decision/entry/exit events and closeout, chained by SHA256, independently verified after writing. It is not a broker fill ledger.
- Frozen 2026 master holdout is excluded (native reader stops 2026-04-30). Develop on prior 2018–2025; prospective future evidence is necessary for strategy validation. No tuning after seeing this day's results and calling the same day a fresh holdout.

## Run

Only after PR merge, on the local ATLAS workstation:

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v55_closed_bar_quote_replay `
  --date 2025-06-09 `
  --lag-seconds 1 `
  --max-adverse-pct 1 `
  --output "data/research/spy_v55_closed_bar_quote_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

The runner immediately announces each potentially blocking step before it starts: exact native source discovery, full original canonical+raw-bundle SHA verification with true 10% byte progress, one-date Parquet read, signal selection, one exact cache-first source request with **unknown** provider completion until it returns, quote-clock verification, exit replay, and incremental hash-chain output. A single ThetaData GET has no invented progress while in-flight. The selected original source persists on D: under `data/options/hybrid/on_demand_source_cache_v38/` and is reusable for later runs of identical exact requirement.

If there is no first completed-close breakout, the result is NO_SIGNAL and no paid request occurs. A provider/schema error or unresolved position is reported and persisted, and the launcher returns nonzero. If the exact quote schema lacks safe timestamp/bid/ask/size evidence, the result is a source blocker, not manufactured historical P&L. A first close-based candidate might not match the original first tick selection, deliberately.

## Next phase

After the first original-source day is analyzed, fix actual schema/clock mistakes supported by the returned JSON, then add **multiple development sessions and week/month/year capital windows** to the same engine without re-downloading archived sources. Expand separately to the original first-tick ORB with independent tick and first-publication proof, and to separately registered short-premium strategies. Do not select the best-looking exit threshold after observing the development session and report it as independently verified profitability.
