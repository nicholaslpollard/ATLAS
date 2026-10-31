# V66 — three precisely missing June SPY 0DTE option quote tapes

## Source-backed motivation

V65 on the operator workstation verified 9/9 tests, all ten weekdays 2025-06-09 through 2025-06-20, both original June 2025 native SPY minute source SHA checks, zero provider calls, zero broker orders. Six dates triggered the frozen M/W/F completed-bar ORB signal:

| Date | Exact contract | Closed-bar decision (ET) | V65 original option status |
|---|---|---|---|
| 2025-06-09 | SPY 600 CALL expires June 9 | 10:33:01 | ARCHIVED; modeled net **−$189.20** |
| 2025-06-11 | SPY 602 PUT expires June 11 | 09:47:01 | ARCHIVED; NO_ENTRY due action ASK drift |
| 2025-06-13 | SPY 598 PUT expires June 13 | 09:59:01 | ARCHIVED; UNRESOLVED_POSITION after quote spread |
| 2025-06-16 | SPY 602 CALL expires June 16 | 09:42:01 | NOT_REGISTERED |
| 2025-06-18 | SPY 599 CALL expires June 18 | 09:48:01 | NOT_REGISTERED |
| 2025-06-20 | SPY 599 CALL expires June 20 | 09:38:01 | NOT_REGISTERED |

The remaining four dates were intentionally not considered by the original Monday/Wednesday/Friday strategy. The three missing dates are **source censored, not genuine NO_ENTRY trading-rule rejections**. One observed closed, fee-modeled trade is a loss, not evidence of strategy profitability.

**V65 evidence fingerprint:** `26f6cd1ce497f08094f9001b56f60a600d0d547ab786e528912546eb7039486c`.

## Safe read-through acquisition, no universe crawl

V66 accepts the exact original user V65 JSON; verifies fingerprint, contract/version, date window and all three original per-day exact requirements. Each request is original V56/V38 `option_history_exact_quote_tape`, 1s, 0DTE, until 15:30 ET; no re-selection or new search universe.

- **June 16** exact query ID: `669d16e1df78897005e93cf81de93ba929bea7a7eb8e0f95c0bdab8ae8e0dbea`, 602 CALL, **09:42:01–15:30**.
- **June 18** exact query ID: `23b8b0b6bf2e178568b9e5d52b8b7a5f9fe0df8b87b06ec3ca348191b8621bd4`, 599 CALL, **09:48:01–15:30**.
- **June 20** exact query ID: `20113f0f56ec7c7476f73d467f6b567e31a4d8e5c479e4f379bf657548c98b5c`, 599 CALL, **09:38:01–15:30**.

For each **one at a time**, V66 reads the V38 exact query receipt through SQLite read-only. `ARCHIVED` is reused only if V38 confirms original compressed and canonical data SHA; `NO_DATA_EXPLICIT` is a recorded absence; `FAILED_RETRYABLE` or `IN_FLIGHT` immediately blocks same-query retry. For `NOT_REGISTERED`, the script writes an **immutable, fsynced dispatch-intent JSON before** invoking the existing V38 read-through method once. V38's source-cache API authenticates and fetches the exact historical option tape and archives canonical bytes on the external options drive. V66 then re-reads the original archive and SHA before accepting it. An exception or unqualified return marks **only that exact query** blocked, records the exception **type** and uncertain provider outcome, and continues acquiring every other independent requirement in the current cohort. It does not retry the ambiguous query automatically, and any unresolved input remains explicitly pending. A later run will reuse verified cached sources without paying/retrieving twice and will refuse ambiguous failures.

V66 does **not** override ThetaData SDK 180-second worker response timeout, does not retry, does not perform V55 broker or P&L simulation, does not fill June 13 from future, and does not claim profitability. Full V65 original log remains immutable. The per-date V66 sources feed a separate V65 rerun for a later isolated replay.

## Operator

First tests, then source-only:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q `
 tests/test_spy_v66_three_missing_exact_tape_acquisition.py `
 tests/test_spy_v65_full_june_offline_simulator_readiness.py

$stamp=Get-Date -Format yyyyMMdd_HHmmss
& .\.venv\Scripts\python.exe -m scripts.run_spy_v66_three_missing_exact_tape_acquisition `
 --v65-report 'data/research/spy_v65_full_june_offline_20261031_121350.json' `
 --output-dir "data/research/spy_v66_three_exact_tapes_$stamp"
```

Every request remains a bounded historical read-only options GET, never a broker order. The three exact requests may take minutes each depending on provider conditions. A timed-out response is not proof of no provider dispatch, and the same exact query must not be automatically resubmitted.

## Next stage

Re-run V65 against the newly archived sources, recording all session events, entry/rejection decisions, slippage/latency/size and censored dates. If the standalone June 16/18/20 source replays all resolve, separately construct a chronologically consistent account from a frozen trading policy; June 13's original unresolved position may still prevent authoritative cumulative equity. Then independently test additional dates, weeks, months, years and multiple alternative strategies, retaining honest after-cost outcomes.

## System-wide acquisition authority (operator clarification, 2026-10-31)

**The three exact tapes in V66 are an immediate cohort requirement, not a permanent ATLAS limit.** Every strategy iteration and runtime feature may discover new option chains, stocks, bid/ask windows, Greeks, historical OI, independent historical volatility inputs, market news or other source needs, across ANY symbol/date/contract for which a valid provider is connected. These must become persistent source demands automatically, not user approval requests.

Required production workflow: **identify exact required source → check persistent indexed cache → automatically retrieve all missing sources from the appropriate provider → save original source bytes plus digest/provenance in durable storage and index → verify and expose only causally eligible observations to the simulator → continue/resume the strategy.** New strategy revisions create new source requirements. No hard-coded total requests, contract candidate count, eligible symbols, dates, lookback period or provider-call budget may suppress those new demands. Reuse previously verified archives to avoid duplicate provider work.

This also applies when requests arise mid-simulation, when more exit data is required, when parameter sweeps select another strike/expiration, and when an earlier cohort is revisited. A missing required input is a **pending acquisition need**, not a permanent NO_ENTRY or a zero-return trade. Successful acquisitions must remain searchable for every later strategy.

Operational edge cases are not policy limits: provider entitlements or API semantics, physically available storage, source quality and rate limits are factual constraints. Chunk/paginate a large demand into supportable source requests, then resume rather than dropping it. A query with an **ambiguous prior dispatch** must be reconciled or fulfilled through a separate valid source before sending an indistinguishable duplicate; this does not block *other independent* requests or prevent the engine from accepting new strategy demands.

**Implementation scope:** V38 already supports open-ended options cache-first read-through, but the cross-provider strategy-runner auto-acquisition orchestration and resumable blocked-requirement queue remain integration work. V66 is the exact three-request cohort test, not proof that every future source type is already automatically wired.
