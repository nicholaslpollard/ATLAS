# ATLAS V104 — V103 independent completed-evidence audit and 2026 exact-source recovery

Date: 2026-11-01. V104 is an independent source-recovery research successor to V103 (draft PR #456), which is based on V102 (draft #455) and V101 (draft #454). No V104 provider calls or brokerage orders have been executed in this GitHub development session; the V104 workstation runner remains to be executed and tested.

## The actual V103 user workstation result

Original pinned V103 \`da6a1e2db6da074cdd054bdef421519dc36cf15e\` completed June 2025 through April 2026: **11 months**, **230 XNYS exchange sessions**, excluding 3 shortened sessions from the original V55 strategy's 15:30 time exit. Original complete ZIP \`spy_v103_multimonth_original_orb_20261101_182528_full_source_linked_evidence.zip\`; original summary ZIP same stem, \`_summary_evidence.zip\`.

Independent reviewer verified:
- Full original ZIP SHA-256: \`79e9421b1e25f92aad55b979518d9b022826c6f334cc773c873df1f20afb4aa5\`.
- Summary ZIP SHA-256: \`66302e1201e677d291d57589dd0a70cb485effdc69993aedc57c1de595369d60\`.
- Signed V103 root fingerprint: \`15ffac1de97473c2ef3d924b6a84a22b8fa5342edeab79e182238ca69faa861b\`.
- Original signed chronological capital-account fingerprint: \`52edbbb578ea8cd1599d0d42d017f72e9c36091f2d582eec353b1f0b3f403820\`.
- **3,992 independent checks, 0 discrepancies**, across 24 ZIP members: ZIP CRC, matching summary members, all 11 signed V65 monthly parent journals (original raw bytes re-decompressed and SHA checked, every compressed member SHA), all 11 V103 signed monthly cash accounts, 227 signed V65 session reports and their nested V55 minute-signal and quote-replay SHA records, 230 signed V103 chronological account session events, source query fingerprints and raw debit/credit quote cash arithmetic. The source original historical ThetaData cache bytes themselves remain on workstation and were **not** independently rehashed in the uploaded ZIP beyond V65's original source receipts and parent SHA pointers. V65 had verified complete original canonical/raw Alpaca native monthly source SHA at the workstation.

### Exact classification — do NOT treat source-missing as zero-profit

| Original V103 event | Sessions |
|---|---:|
| Closed quote reference | 57 |
| Original V55 entry rejected with archived quotes | 18 |
| Entered but exit unresolved | 16 |
| Missing exact option quote source | 45 |
| Published strategy policy excludes Tue/Thu | 91 |
| Early market close excluded | 3 |
| **TOTAL original XNYS sessions** | **230** |

Original options quote receipt census: **91 ARCHIVED** exact source queries and **45 NOT_REGISTERED**, all **45 unique**, all in January–April 2026. Original closed outcomes: **20 wins / 37 losses**, win rate 35.09%, 36 stop-loss, 18 take-profit, 3 time-exit modeled closes; gross positive closed-trade quote P&L **$7,858.40** / absolute closed losses **$7,886.10**, sum **−$27.70** and profit factor **0.9965**. This sum is **a conditional diagnostic of only 57 independent V55 hypothetical closes**, not the return on an 11-month $25,000 capital account. An original one-slot account is source/expiry censored on **2025-06-04** after a prior **−$219.90** closed quote-reference trade on 2025-06-02. The terminal 11-month portfolio equity is legitimately **unknown**. V55 is a completed-minute-close 0DTE ORB with presumed +1s candle finalization, not the externally published first-breakout-tick ORB; original source BID/ASK quote observations are not actual broker fills.

### Original conditional completed-quote outcomes by month

| Month | Closed reference trades | P&L of closes only (USD) | Original missing source |
|---|---:|---:|---:|
| 2025-06 | 8 | +349.30 | 0 |
| 2025-07 | 5 | +833.70 | 0 |
| 2025-08 | 7 | +184.60 | 0 |
| 2025-09 | 7 | +348.00 | 0 |
| 2025-10 | 13 | −328.10 | 0 |
| 2025-11 | 8 | −357.50 | 0 |
| 2025-12 | 8 | −847.10 | 0 |
| 2026-01 | 0 | no qualified closed trades | 12 |
| 2026-02 | 1 | −210.60 | 10 |
| 2026-03 | 0 | no qualified closed trades | 11 |
| 2026-04 | 0 | no qualified closed trades | 12 |

**Unresolved exits require independent remediation, not setting P&L=0 or assuming an immediate successful liquidation**. From original V55 events: 9 quote spreads >15%, 4 empty-size/crossed quote, 1 missing/invalid BID/ASK size, 2 exit bid-size insufficient. Those represent exact quote-quality, liquidity and uncertain exercise/expiry risks, not an automatically recoverable data bug. Do not reclassify these as ordinary stopped trades based on another later quote unless independently predeclared execution logic and as-of availability permit it.

## What V104 adds, without changing strategy

1. \`scripts/run_spy_v104_original_orb_source_recovery.py\` verifies the precise original V103 full ZIP byte SHA and signed root, 11 original V65 monthly raw/gzip hashes, 11 signed monthly V103 cash-parent links, all 227 V65 signed underlying minute signal and quote decisions, original exact 1s SPY contract identity and query hash, and builds an immutable **45-query original source plan**. Every first-source candidate must have been \`NOT_REGISTERED\` in original V103, not \`FAILED_RETRYABLE\` or \`IN_FLIGHT\`. Frozen source window ends 2026-04-30; no holdout access.
2. A separate immutable **16-unresolved-position diagnosis** records original source SHA, debit, exit-censor reason and original quote rejection rows, **without filling missing expiry cash**.
3. The \`--acquire\` option invokes existing \`resolve_strategy_source_demands\` (V39) through its SHA-protected V38 exact source receipt/cache. Before each separate original query, V39 rechecks the live local registry. Newly selected exact sources may make ThetaData historical GET calls, while cached source data are reused and uncertain previous dispatches are blocked without the same-query retry. Every dispatch or error is appended and fsynced in a durable event log; independent requests can proceed when one request fails. The 45-query frozen population is not a lifetime API quota on other ATLAS strategies.
4. \`scripts/run_spy_v104_compare_refreshed_orb.py\` independently checks the V103 rerun, 227 original SPY minute signals, strike/rights, original request identities, original archive/fill observations and 2025 quote-replay SHA. Every original 2025 replay must match; only sources that were **NOT_REGISTERED in original 2026** may change source states/outcomes. Refreshed V103 still censors any unresolved option/expiry cash; original ORB entry/exit parameters remain unchanged.
5. \`scripts/run_spy_v104_exact_source_acquire_and_replay_20261101.ps1\` bundles compile and regression tests, original ZIP audit, up to the 45 original missing query identities via V39, full original V103 11-month source-only re-simulation, SHA comparison and three evidence ZIP outputs (source recovery; refreshed summary; refreshed full).

**Do not claim 2026 profits, 11-month full cash P&L, or recovered trades merely because the source acquisition finished.** Original 2025 settlement uncertainty remains structurally blocking until a genuinely qualified causal exit/settlement treatment is separately tested. No broker requests are made; paid historical ThetaData acquisition happens **only when the user runs the V104 PowerShell command**. Retain original V103 and prior V99/V101 evidence. Full 2026 May–August holdout remains unopened.

## Acceptance gates

- Original ZIP checksum and exact root; 227 original signed source sessions; exactly 45 original absent unique 2026 exact 1s quote tape demands; exactly 16 archived-but-unresolved options.
- Regression suite and source cache adapter tests must pass *before* dispatch.
- First previously registered ambiguous requests must never be resent; errors retained in event log.
- Refreshed original V55 source-only full multimonth replay and every frozen original signal identity SHA must match; no changes to past 2025 quote exits or historical account P&L.
- A newly archived source may still be quoted-price unqualified or terminal cash unresolved. No invented fills.
- No broker orders, no master holdout access; preserve each source artifact and original compressed V65 event journal.
