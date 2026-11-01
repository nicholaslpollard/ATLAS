# V86 – Original 1-second option quote exit-limit recovery and cancel/reprice (2026-10-31)

## Why V86 is necessary after V85

V85 replay succeeded: 606 original option event journals SHA verified, 48 one-position $25,000 shared-cash research scenarios, 0 provider calls or broker orders. The combined balanced (−35/+100), 1-second quote-reference account showed +$2,242.30 after an adverse 2% exit-BID haircut, with 77 hypothetical entries and one blocked overlapping opportunity; the 3-second alternative fell to +$758.54, with 68 entries. These are historical development quote references, **not fill-verified trading profits**.

V84 measured 31 of 78 independent balanced/1-second exit actions where observed BID was below the initial sell-limit trigger. These 31 trades contributed +$1,898.28 of the **independent closed-only haircut scenario**. This is NOT a causal entry filter: the marketability classification only exists after the selected entry. Excluding these trades after observing exits fabricates selection bias.

V85's strict no-reprice counterfactual maintained an *indefinite* unresolved position when the first historical trigger limit was unmarketable. That is intentionally safe against invented liquidation and autoexercise cash, but not a realistic literal 0DTE multimonth capacity model. The position's contract expires the session day; its terminal cash/assignment liability remains unknown unless explicitly modeled. No strategy should be promoted on either that indefinite no-reprice outcome or the immediately repriced BID quote-shadow result.

## Predeclared V86 offline original quote recovery experiment

Use the same complete original immutable V83/V84 set, 101 signed 0DTE SPY option tape requirements, and all 606 V84 signed compressed journals. Verify every original receipt, exact request, archive source SHA and option quote observation before any result is published. **No new provider calls. No broker orders. No promotion.**

For every originally modeled V84 exit action:

- If the observed action BID was at least the trigger sell limit, retain the action quote as a **marketability observation, not a fill**.
- Otherwise register the original fixed limit as resting for exactly **0, 3, 10 or 30 seconds** after original action. Scan the actual archived 1-second quotes in strict timestamp order. A later bid is a marketability observation only with V55-compatible noncrossed bid/ask, <=15% spread, positive displayed BID size at least original quantity, and original fixed sell limit <= observed bid. For conservatism, hypothetical credit uses exactly the original limit, not hindsight price improvement above it. No order-queue assumptions.
- If never observed marketable inside the registered window, assume a **hypothetical** cancel-and-replace intent at its end. Enforce the separately registered original 1s/3s action lag and at most 3 seconds additional arrival slack, use only the first following qualified quote BID (same original contract and source SHA), never the best later price. A 2% adverse BID haircut is a simultaneous stress case, not newly observed historical market data.
- If no qualified bid/size before the hard exchange-aware research cutoff, retain **UNRESOLVED_POSITION** with unknown expiry/exercise cash, NOT zero P&L or instant cash liberation. Do not create portfolio totals that omit a live unsettled entry after looking at its future.
- All four variants remain research-only, not observed orders. Recheck results never prove historical fixed limit or replace order fills; quote timestamps alone do not show our queue priority or market impact.
- Preserve signed journals for **606 original V84 alternatives × 4 fixed-limit rests = 2,424 individual counterfactual exit-order scenarios**. Full source tapes stay in existing V38 immutable cache; only audit references, decisions, observed BID actions and outcomes are written.
- For each duration, original strategy, frozen V84 exit policy and V84 action lag, construct conditional V85 **shared-capital cash** research ledgers only when all selected option exits were source-resolved, otherwise explicitly withhold complete portfolio P&L. Four family scopes × 3 exits × 2 original action latencies × 4 limit rests = **96 research account scenarios**. Store full signed event ledgers, as well as compact side-by-side comparisons, each with source SHA lineage.
- No same-sample parameter winner is automatically considered a profitable trading system. Inspect which exit actions would require repricing, how many fixed limits subsequently become marketable, delay sensitivity, and censoring before deciding whether to acquire a genuine out-of-sample test.

V86 does **not** infer actual options exchange order execution, slippage distribution, autoexercise/assignment payouts, physical share deliveries, broker account buying power or any held-out model success.

## Safe workstation command after local tests

```powershell
python -m scripts.run_spy_v86_original_exit_order_recheck `
  --v83-dir data/research/spy_v83_source_first_2025h2_20261031_173217 `
  --v84-dir data/research/spy_v84_offline_2025h2_20261031_212028 `
  --output-dir data/research/spy_v86_exit_recheck_2025h2_FIRST_RUN
```

Output is immutable. The runner does not need the V85 local output folder: it recomputes all candidate account possibilities from the same original V84 SHA-verified trial event chain. ZIP only the V86 output folder, not the V38 original provider tapes.
