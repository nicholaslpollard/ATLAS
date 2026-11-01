# V85 – Execution-aware shared-capital option shadow ledger (2026-10-31)

## Measured V84 evidence before V85

V84 finished on 2025-H2 original sources: 101 0DTE exact original option candidate tapes, 606 journaled independent 3-exit-policy × 2-action-delay trials, 441 closed BID/ASK quote-reference exits, 165 rejected entry quotes (all >1% adverse ASK move), 150 of 441 original exit limits not immediately marketable at the observed action BID, zero unclosed V84 *reprice-to-observed-BID* cases. All four source/candidate/window summaries and 606 independently compressed event-journal SHA digests passed review against ZIP `spy_v84_offline_2025h2_20261031_212028.zip`. No broker transactions occurred.

The sample is **development / not held-out**. Results below are hypothetical closed-only dollars after V84 fees and 2% adverse exit-BID haircut; NO_ENTRY cases are never scored as trades:

| Original frozen entry family | Exit policy | 1s (closed / total, USD stress) | 3s (closed / total, USD stress) |
| --- | --- | --- | --- |
| Failed-breakout fade | Balanced −35/+100 | 43/51, +$1,459.52 | 39/51, +$941.30 |
| Failed-breakout fade | Runner −35/+150 | 43/51, +$1,492.84 | 39/51, +$925.62 |
| Opening-range continuation | Balanced −35/+100 | 33/45, +$840.64 | 29/45, −$51.00 |
| Opening-range continuation | Runner −35/+150 | 33/45, −$28.62 | 29/45, −$508.66 |
| Gap fade | Balanced −35/+100 | 2/5, −$63.90 | 1/5, −$141.40 |

The original-trigger-limit marketability subset is observed **after** the exit decision and therefore cannot be used as an entry-time strategy filter. Original marketable limit is not proof of a historical fill; unmarketable limit is not a confirmed filled exit.

## V85 frozen next-stage design

V85 reads **only** original V83 and V84 signed documents and all 606 compressed source-linked V84 journals; it checks every SHA digest and cross-link. Missing, mutated, unregistered, duplicated or out-of-scope receipts STOP before creating results. It never reconstructs option data from a ZIP or calls ThetaData or brokers.

For each of the four scopes (three entry families independently, and combined); each of the three V84 exit policies; both 1-second and 3-second V84 action-delay trials; and two exit-order reference treatments, produce **48 shared-cash simulations**. Use one $25,000 initial experimental cash account, at most **one open position at a time**, no margin/borrowing, and the frozen V84 $500/candidate one-to-four-contract premium limit. Candidate choice is causal: order original 09:35 and 09:40 signals by their decision clocks; same-clock priority is gap fade, then failed breakout fade, then opening-range continuation (otherwise immutable exact source ID). Keep cash and stress-cash separate. A rejected V84 entry is a logged abstention. A qualified entry receives a hypothetical ASK-reference debit only if both cash ledgers can afford it and another position is not still open. An occupied position makes the later candidate a **blocked opportunity**, not a retroactively selected winner.

Two explicitly contrasting, non-executable market-behavior assumptions:

1. `repriced_bid_quote_shadow`: the model *hypothetically* receives an exit credit at V84 action BID; evaluate simultaneously a V84 2% lower exit-BID scenario. Any original exit-trigger-limit that was unmarketable requires a new, lower limit or market order—neither actual order nor filled execution is proven. This is a **conditional price-reference** account, not realized broker P&L.
2. `original_fixed_limit_censored`: if the observed action BID is below the original exit-trigger limit, **DO NOT** credit cash. The original option remains unresolved; its later cancel/replace, exercise, expiry, and assignment cash is unknown. Reserve capital and maintain the open-position capacity block across following opportunities. The final account equity is **null** whenever an unknown terminal position remains. A marketable original limit is also only a quote reference, never a verified fill.

Record every one of the original V83 384 considered decisions by SHA linkage (including all 283 NO_SIGNAL cases), all 101 signed V84 possible entries, which opportunities were accepted or rejected and why, capacity conflicts, action/exit clocks, cash debit/credit, action marketability, open-position censoring, per-month/week/year scenario cash-flow returns, and flat-to-flat drawdown (not a claim of intraposition drawdown). Every experimental run includes a full signed event journal, linked SHA source, and a compact comparison report. **Never add results of 48 alternative parameter scenarios** or infer stability from overlapping same-sample variants. All fees come from V84; quote fills are not newly invented or promoted.

The payoff question for V85 is whether the *development* evidence for failed-breakout fade remains remotely attractive once chronology, one shared position slot, latency and censoring are counted. Even if attractive, the next required steps are truly held-out historical testing, live forward paper verification of marketability and actual order handling, full 0DTE exercise/expiry accounting, and realistic execution costs. No strategy is promoted merely from this run.

### Workstation invocation

Use fresh immutable output path:

```powershell
python -m scripts.run_spy_v85_shared_capital_quote_portfolios `
  --v83-dir data/research/spy_v83_source_first_2025h2_20261031_173217 `
  --v84-dir data/research/spy_v84_offline_2025h2_20261031_212028 `
  --output-dir data/research/spy_v85_shared_cash_2025h2_FIRST_RUN
```

All original options archives remain in V38. The V85 output ZIP contains only signed analyses and event journals—not original provider data.
