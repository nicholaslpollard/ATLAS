# V56 — Source-backed chronological SPY 0DTE multi-session development simulation

Created 2026-10-30, following operator-accepted V55 actual workstation receipt.
**Development quote reference only. No historical broker fills, independently proved original feed publication, valid historical alpha or protected-holdout authority.**

## Why V56 exists

The V55 workstation run on **2025-06-09** completed: 821 source SPY bars; completed-candle decision **10:33:01 ET**, SPY close **600.145**, selected **SPY 2025-06-09 600 CALL**; 17,820 exact historical 1s quote rows; bought **4** theoretical contracts at ask **1.18**, with **474.60** total debit/fees, and sold at **15:30:00 ET** observed bid **0.72**, **285.40** credit after exit fees. **Net P&L -189.20; $25,000 → $24,810.80**. Neither +100% target nor -50% stop tripped. Historical bid max **1.61** at **12:52:47** and min **0.63** at **15:25:20**. All 17,825 SHA-chained JSONL journal records independently verified, final tip `ca029a2dcd829a521538827091ea2f7f82b50cadc28cf94f1094bcbb92a10f2a`; report fingerprint `54098dba3b3386d2365f0b078d5d78c537cc61828586efd1fe06d0a1ee0c201f`.

The V55 output is **one losing development example**, not a reason to optimize the +100/-50 exit thresholds. The expensive stage was **full-history native checkpoint metadata discovery** (2026-10-30 21:16:00→21:22:45 EDT ≈ 405 seconds), not the source SHA check (7,582,618 bytes validated in <1 second) or provider GET (approximately 6 seconds). V56 narrows the search to the checkpoint's `year=YYYY/month=MM` subtree while still SHA-verifying both monthly canonical and raw original bundles. Monthly source verification occurs once for that month regardless of how many dates are evaluated; the original bytes and metadata identity are not bypassed.

## Unchanged policy, now over real consecutive sessions

- **Uses V55's exact unchanged versioned strategy and contract selector**: Mon/Wed/Fri, opening 09:30–09:34 high/low, first completed *minute CLOSE* outside the range, observe one second after minute end (publication *assumed*, not PIT proved), nearest-dollar spot ATM, same-day expiration, CALL on up/PUT on down.
- One dynamically selected contract per qualifying day. Exact one-day `1s` bid/ask/size quote tape from post-close decision to 15:30 ET fetched **cache first**, then provider GET on miss; original option quote compressed/archive and query/source SHA retained permanently in V38. No artificially frozen contract, strike, or day roster; a date filter defines the requested cohort, not a lifetime source cap.
- Starting account **$25,000**, maximum option premium **$500 per trade** whole contract sizing, **$0.65** commission per contract/side, buy at ASK, hypothetical sell at BID. Lag 1 second baseline or separately versioned 3-second sensitivity; adverse ask rise capped 1% baseline or predeclared 0.5%/2% diagnostic.
- Position exits on observed +100% option bid vs entry ask, -50% stop, or 15:30. No lookahead into future quote prices in entry selection. Missing/invalid quote path before target/stop/time exit means terminal equity unknown; **block later chronological account cash**, retain source error and receipt. No zero liquidation assumption or fake source.
- Excluded Tuesday/Thursday and source-less sessions are logged as no-signal or reason-coded abstentions without a provider call. A source failure remains an explicit cohort blocker and is never recast as a strategy loss.
- Every session independently saves its original source references, full decision and exit event JSON, and hash-chained immutable JSONL (verify/readback), then atomically updates a cumulative checkpoint. Once completed, `summary.json` includes the realized cash curve, max realized drawdown, source cache/new requests and errors, closed trades and fees, plus standalone **weekly/monthly/annual** gross/net/cost/disposition results.
- Preserve 2026 consumed master holdout barrier. The operating contract and research evidence ledger still require prior-only model training and prospective validation. These development windows do not validate alpha or real fills.

## First cohort / workstation handoff

Use PR-merged `main`, with the same activated ThetaData Standard and connected D: option source binding as in the successful V55 workstation run. Do not run concurrently with another ThetaData bulk process. Initially run **2025-06-09 through 2025-06-20** (ten regular weekdays including two Tuesday/Thursday exclusions and any session holiday). The exact source workload is discovered only when a signal selects a contract; existing 2025-06-09 source should hit V38 cache.

```powershell
$stamp=Get-Date -Format yyyyMMdd_HHmmss
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v56_multi_session_quote_replay `
    --start 2025-06-09 --end 2025-06-20 `
    --lag-seconds 1 --max-adverse-pct 1 `
    --output-dir "data/research/spy_v56_june_cohort_$stamp"
```

Progress contract: timestamped START before every potentially blocking stage, source SHA 10% by bytes, checkpoint metadata 10% by files, quote replay clocks 10%, journals 10% by records, and session-level 10% by elapsed observed throughput. One SDK GET reports a precise START with completion fraction UNKNOWN and end/error later; there is no fake in-flight percentage or heartbeat spam. Every successful original source is cached regardless of later account returns. The cohort output dir is immutable/no overwrite, and every completed day survives failures in `checkpoint.json`.

## Acceptance questions

- Does per-month scoped metadata discovery remove the six-minute full-history scan without skipping original source SHA?
- Are original 1s contract quotes available for several distinct dynamically selected option strikes, expirations and rights?
- How many trades are entered, rejected, censored, and closed? Is source coverage selection-dependent?
- What are **separate** realized net/gross/fees, drawdown, win/loss and weekly/monthly/annual distribution at the original unchanged V55 thresholds?
- If source failures occur, preserve their exact stage/error type and original SHA; fix structural issues rather than silently narrowing to favorable periods.
- Once a sizable development cohort works, add unbiased full-universe candidate scheduling and fixed walk-forward past-only parameter evaluation **before** interpreting performance as repeatability.

**No one-day or two-week return, including positive results, establishes profitability.**
