# ATLAS V81 / V82 / V83 — broker-neutral options order-state and three distinct causal entries

**Status:** independent research / simulator development, *zero broker order authority*. Preceding V79/V80 exit-event audit and price-protection gate were merged via PR #449. The prior V74/V76 historical quote-reference results remain immutable and are not broker fills, bankable cash or validated alpha. Webull remains primary paper/intended broker; Alpaca may be manually selected only after flat/reconciled accounts, with **no automatic failover**. The accepted Phase15 broker execution adapters still support **EQUITY in PAPER only**, not direct live options.

## V81: no more 'a quote appeared, therefore an order filled'

Code `packages/simulation/spy_v81_broker_neutral_option_order_lifecycle.py` models an explicit *fixture-only* order lifecycle:

- Original source-linked option SELL_TO_CLOSE DAY LIMIT intent with immutable client order ID, contract, quantity, limit, expiry, fee assumptions and broker label
- `QUOTE_OBSERVED` context never changes an order or creates a fill
- `SUBMIT_REQUESTED` means **submission unconfirmed**, not acknowledgment; `BROKER_ACK` must identify the exact broker order ID
- `PARTIAL_FILL` must increment cumulative filled contracts and supply an accepted price **at or above the sell limit**; `FINAL_FILL` must reconcile the exact total quantity
- `CANCEL_REQUESTED` is unsafe pending until `CANCEL_ACK`; partial filled contracts remain visible when remainder is cancelled
- `BROKER_TIMEOUT` produces `UNKNOWN_NEEDS_RECONCILIATION`; `BROKER_RECONCILIATION` requires an exact order ID and independently supplied filled quantity. It refuses to infer prices for unreported partials
- Terminal states cannot silently change; a DAY clock passing does not prove broker cancellation or SPY option exercise, automatic cash payout or liquidation
- Every event must be uniquely ID'd, signed, ordered by observed/availability time, and bound to the same broker/client/order identity. No unknown status is retried or transferred to another broker
- **All events currently have origin `SYNTHETIC_ORDER_FIXTURE_ONLY`**. The engine's `synthetic_fill_proceeds_after_fees` is not account cash and `historical_broker_cash_credited=None` even with four synthetic filled contracts. This is strict contract/regression groundwork for eventual actual broker receipt adapters, **not** an assertion of historical options execution.

V81 does not yet attach to V80 quote-classification output or change any historical V74 returns. It proves state semantics before that coupling is safe.

## V82: entry strategy diversification with explicit causal source gates

`packages/simulation/spy_v82_causal_entry_family_registry.py` registers **three genuinely different, fixed entry signal families** rather than sweeping exit thresholds against the same M/W/F ORB entry:

| Strategy | Earliest decision | Original available features | Signal |
|---|---|---|---|
| `orb_continuation_0940` | 09:40:01 ET | SPY minute bars 09:30–09:39, completed bar clocks | CALL on closing upside continuation beyond 5m range; PUT on downside continuation |
| `failed_breakout_fade_0940` | 09:40:01 ET | Same ten prior complete minutes | PUT when an upper break of the first 5m range was rejected back into range without simultaneous lower break; inverse CALL |
| `gap_fade_0935` | 09:35:01 ET | Previous regular closing bar and first 09:30–09:34 minutes | PUT when opening is >=+0.60% above previous close and fades during first 5m; CALL on <=-0.60% down gap and first-5m rebound |

Exact 09:35/09:40 decision bars must be completed **before** the one-second-after-close decision. Prior close and prior stock SHA must be independently supplied. A missing minute, unqualified source, quote timestamp beyond decision, overlapping opposing breakouts or absent source provenance cannot silently create a signal or trade.

The decision is **OPTIONS_CANDIDATE_SOURCE_SELECTION_REQUIRED**, not an option trade. Source demands for qualified candidates follow existing V65/V38 `option_history_exact_quote_tape` normalized shape, and `v39_demand` translates to existing V39 cache-first automatic source coordinator. It cannot invent a listed 0DTE contract, option bid/ask depth, strike universe coverage, underlying spot fill, return, or permission to pay cash. Stock fallback is signaled as `UNPRICED_AND_UNAUTHORIZED`, not faked as a successful stock execution.

## V83: original-source monthly three-family experiment

`scripts/run_spy_v83_three_family_native_source_screen.py` wraps the existing V51 full original monthly stock canonical/raw SHA verification and B34 native one-minute SPY dataset validation. All XNYS market days in the requested range are screened, not only M/W/F. Previous XNYS session end-of-regular-market minute is loaded and verified for the gap family's prior-close input, including previous month when necessary. Missing genuine original bars remain signed, abstained cases.

- By default the runner **only** screens stock source and signs all per-day candidate/no-signal/blocked decisions plus exact option source plans. All broker and provider calls zero.
- Optional `--acquire-options` passes each generated options demand through V39's existing immutable cache-first ThetaData coordinator. Newly selected 0DTE strikes are an explicitly unverified *ATM stock-close proxy*, not a proven contemporaneously listed/liquid option contract; any provider explicit no-data persists and must block a trade. One family’s contract shift yields its own source query ID. V39 performs automatic new calls and saves/indexes receipts without a fixed total-call quota; previous ambiguous dispatch cannot be blindly retried.
- No entry execution, option trade, exit modeling, shared cash ledger, option order or profitability claim is produced in V83. This creates the **actual diversified candidate/source denominator** for those next runs.
- V83's source version string and immutable registry SHA are fixed for this development experiment. H1/H2 2025 have already had some outcomes inspected by earlier V74/V76, so do not claim those dates are untouched held-out testing.

### Example offline stock-only native source screen (zero paid calls)

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v83_three_family_native_source_screen `
  --start 2025-07-01 --end 2025-12-31 `
  --output-dir "data/research/spy_v83_three_family_screen_$(Get-Date -Format yyyyMMdd_HHmmss)"
```

After accepted offline signal/audit evidence, explicitly add `--acquire-options` on a **new immutable output folder** for cache-first paid source acquisition, retaining original source receipts. No partial output folder may be silently overwritten.

## Following acceptance gates

1. Connect V80 exit action quotes to V81 research order lifecycle **without** treating quote BID as a broker ack/fill; implement fresh repricing with broker confirmation and explicit uncertainty/partial fills.
2. For each V82 family, select contracts from prior-clock eligible option listing/liquidity evidence, then request exact entry and exit sources dynamically; quote-based returns must be marked hypothetical until real order evidence exists.
3. Run one family at a time on historical source snapshots with 1s/3s action lag, fee/spread/negative-drift stress and complete skipped candidate logs. Reconcile causal timing, 0DTE expiration risk and physical exercise.
4. Introduce stock fallback only with a separate real stock source/entry/exit contract; then combine strategies under a **single shared** capital/risk and position-account ledger, not a sum of separately reset $25k balances.
5. Prior-only fold selection and genuinely uninspected follow-up weeks/months/years are mandatory before promoting any profitability or LIVE broker option execution.
