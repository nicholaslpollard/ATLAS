# V25 — Rapid offline strategy sweep fast lane (synthetic mechanics only)

## Purpose and priority

The user's immediate goal is a historically qualified, profitable strategy laboratory **before the active ThetaData Standard acquisition window expires**. Market-source requests and scenario evaluation must be separate phases:

1. **Acquire once** into immutable lossless option/stock quote archives, with original identity and SHA, explicit missing dates and query-completeness evidence. Preserve current V24 SPY exit campaign and 411 original entry sources.
2. **Build the exact-source historical adapter** that links an original observed strategy decision, eligible option contracts, underlying prices, PIT rates/dividends/OI, executable bid/ask, contract terms, time-qualified future exits and terminal settlement to the account engine.
3. **Run many scenarios offline** on the same pinned historical input. No repeat ThetaData GET for a policy or risk variation. Separately record every variant and outcome.
4. **Jointly simulate** all surviving strategies with one chronological cash/equity ledger, shared buying power, risk limits, contract/account mechanics and mutual competition for capital.
5. Freeze selections using DEVELOPMENT; evaluate only on untouched forward data and then prospective PAPER. The consumed master 2026 holdout is never fresh again.

V25 supplies **only the reusable step-3 fixture/mechanics orchestration path**, not step 2 or 4 for a mixed stock/options account. Building and testing this path early avoids making the paid-data collection a serial blocker for all simulation infrastructure work.

## Implemented in this PR

- `packages/simulation/strategy_sweep_fastlane_v1.py` reuses the existing `ReplayPolicy` and chronological `replay_synthetic_account` engine (not a second cash ledger). For each policy combination, runs every named strategy independently.
- For **two or more same-mode strategies with distinct case identities**, also replays their combined cases through one actual shared-capital synthetic account. This captures same-time slot/cash competition. It **does not** add separately funded returns or silently net mixed assets.
- Allows up to **12 fixture strategies, 20,000 source-fixture cases, 64 scenario configurations** with Cartesian grids over position allocation, maximum concurrent positions, per-position units, and explicit stock/option execution costs. Repeated runs use exactly the same input cases; no future outcome informs earlier decisions.
- `scripts/run_strategy_sweep_fastlane_v1.py` accepts a strict `SYNTHETIC_FIXTURE_ONLY` JSON. It emits scenario-level P&L, finishing cash, NULL equity for unresolved holdings, time/year disposition counts, and a content-addressed report fingerprint. Optionally writes a new report without overwriting a previous one.
- No SDK, network, provider, broker, protected holdout, orders, paper, live, strategy promotion or historical authority. Unknown/unsupported strategy parameters are rejected. The pilot's historical quote sources cannot be relabeled as fixtures to claim profitability.

## Demonstration command (synthetic data — no ThetaData)

From the ATLAS repository root after updating to the merged code:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/test_strategy_sweep_fastlane_v1.py
.\.venv\Scripts\python.exe -m scripts.run_strategy_sweep_fastlane_v1 --manifest examples/strategy_sweep_synthetic_v1.json --output data/research/strategy_sweep_synthetic_v1_report.json
```

The example does **not** measure a real trading strategy. Do not use its results to choose trading parameters or estimate profit.

## Required work for a genuinely useful historical strategy laboratory

**P0 — while ThetaData is active:** Complete V24 source acquisition with a known bounded storage budget; investigate the two invalid original archives and eight source faults independently; persist high-reuse exact observation paths needed to evaluate the frozen strategies. No broad 815-underlying expansion until the small primary pilot's economic relevance is established.

**P1 — in parallel, before subscription expiry:** Implement a **separately typed, verifiable historical event tape**, distinct from `SYNTHETIC_FIXTURE_ONLY`. Preserve original source SHA/receipt, decision clock, entry/exit eligibility, unknown marks, OCC deliverable and multiplier, bid/ask/size, latency, corporate actions, funding/cost basis and shared account allocation. Review existing `multiyear_historical_eod_option_account_replay_v1` and pair-account engines rather than setting the fixture-origin flag on historical data. Historical parameter grids must select entry rules only from **as-of information**; each trial/sweep counts toward a versioned experiment ledger.

**P2:** Implement `run_historical_strategy_sweep` on that admitted event tape with one frozen observation set, up to a bounded number of declared strategy variants/cost stresses. Report individual scenarios and side-by-side weekly, monthly and annual trade/account metrics, costs, drawdowns, unresolved open positions, denominator and concentration. Label diagnostic evidence separately from fully qualified causal account performance.

**P3:** Generalize the chronological multi-asset account engine to combine STOCK, CALL, PUT and paired straddles under **one** capital/risk/equity ledger with asymmetric fills/partial legs, option expiration and settlement. Promote no strategy solely because its optimum was selected in the same historical data. Require fresh forward/paper confirmation and risk limits.

## Explicit warning about apparent optimization

V25's sweep is a **mechanics accelerator**, not an optimizer. A profitable historical scenario selected after seeing all the historical outcomes is in-sample research, **not independent evidence of profitability**. Report all tried configurations, including losers, and preregister a limited independent chronological validation for finalists. Avoid asking ThetaData for data repeatedly just because an account parameter changed.
