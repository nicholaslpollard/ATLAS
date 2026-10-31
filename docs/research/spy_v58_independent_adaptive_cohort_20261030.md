# V58 — independent-cash adaptive exit comparison across frozen V56 cohort

**Status:** offline, source-verified, developmental post-outcome hypothesis. No provider or broker requests. The V57 hyperparameters were selected after reviewing the 2025-06-09 losing trade; this cohort is **not a new out-of-sample holdout** and cannot certify profitability.

## Research problem

V55/V56 original strategy is a completed-minute-close (not the published first-tick) SPY 0DTE M/W/F opening-range breakout, $500 max long premium, commission $0.65 per contract per side, 1s/3s action lag and capped adverse ask movement. The baseline uses fixed +100%/-50%/15:30 bid exits; accepted June 9 report showed four 600C at $1.18 ask, then a 15:30 bid of $0.72 and net **-$189.20**. V57 standalone verified 552 past quote observations and modeled risk-budget stop at $0.88 bid with **-$125.20**, independently confirmed by the user's workstation at 21:50 EDT October 30, 2026; no real broker fills. A one-day improvement in a losing trade does not establish a strategy edge.

V58 evaluates the **unchanged** V57 risk/trail rule on each V56 session, while tracking an **independently compounded adaptive hypothetical cash account** starting from $25,000. For each date, V58 reuses the already accepted V56 entry at the same option ask/quantity and computes a new V57 0.5%-equity risk-dollar threshold from the adaptive account's current available cash, not the baseline account's then-different cash balance. An original full SHA-chained journal and report fingerprint must match each day before the independent replay can run.

## Stop and trail definition

Risk budget: 0.5% of independent pretrade equity, with entry/exit $0.65 per-contract fees reflected in the reference bid floor. Stop is a **trigger on the actual quote**; true broker losses may exceed the target due to gaps, spread, market impact or routing latency. Once observed bid rises 20% over entry ask, enable a monotonic no-loosening trailing bid threshold 10–20% below observed bid high-water; distance uses previous rolling 60 absolute bid changes. 15:00 ET force cutoff. Every observation records bid/ask, size, spread, quote intervals, high-water, mean absolute movement, current risk and trailing floors, estimated upside envelope (untrained, auditing only), hypothetical immediate net exit, and hold/exit reason.

## Faithful comparison limits

- If adaptive exit occurs before or at the original baseline's exit, compare their separately modeled **net** trade outcomes, with a matched-pair daily difference and weekly/monthly/annual matched-pair summaries.
- The original V55/V56 event journal **may stop at its own baseline exit**. A V57 hypothetical trade that would continue afterward is reported **CENSORED_AT_PARENT_BASELINE_EXIT**, not assigned a future close or return. Subsequent independent-account portfolio returns are blocked because they cannot be proven from available quotes.
- Invalid original source SHA, journal link, unexpected source identity, account drift, day order or partial provider quote coverage cannot be silently treated as winning or losing trades.
- No trade in the original signal is recorded as a no-entry. If it was a **cash-dependent** no-entry, the independent model blocks because the other portfolio might have had different entry eligibility.
- A V56 session with an unresolved baseline account cannot support the subsequent baseline equity path. V58 blocks instead of silently carrying a made-up balance.
- Output is write-new immutable: per-day complete adaptive observations, atomic checkpoint per session, final verified cohort summary with independent adaptive cash, drawdown, censor rates, matched return differences, model/source/journal SHA provenance and explicit historical-performance disclaimers.
- All quote prices are **reference bids/asks**. No fill probability model, quote-to-real-market slippage calibration, liquidity available at the routing latency, margin constraints, or independently validated first-publication timing; hence no demonstrated executable alpha.

## Run following V56 completion

Identify the completed V56 output folder containing `summary.json`. Full run is **offline**.

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q tests/test_spy_v57_causal_exit_shadow.py tests/test_spy_v58_independent_adaptive_cohort.py

& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v58_adaptive_cohort_comparison `
  --cohort-dir 'data/research/spy_v56_june_cohort_<actual-run-timestamp>' `
  --output-dir "data/research/spy_v58_paired_shadows_$(Get-Date -Format yyyyMMdd_HHmmss)"
```

Return the V56 `summary.json` (or `checkpoint.json` on partial source failure) and V58 `summary.json` for cash, matched win/loss, weekly/monthly/annual risk-window analysis. Do not overinterpret the post-hoc June 9 policy choice.

## Next step: actual conditional maximum-favorable-excursion modeling

Register **training-only**, strictly pre-decision features (time of day, prior-volatility window, available SPY market context, option quote spread/size, premium, option DTE/right and only prior causal flow/Greeks). Estimate conditional MFE and adverse excursion **using only earlier folds**, then choose risk/reward thresholds using net after-fee expected utility and observed price/size feasibility. Preregister prospective chronological folds. Any later period reused to tune parameters is no longer untouched. Require explicitly defined minimum evaluation counts and full quote coverage; preserve every rejection reason and candidate quote timestamp.
