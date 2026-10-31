# V57 — Causal dynamic exit management, separated from V55/V56 baseline

Status: **independent developmental shadow candidate** after the completed 2025-06-09 V55 test. The policy was proposed after reviewing this original losing day, so replaying the same date **is in-sample illustration only**, not an out-of-sample performance gain or any proof of predictive skill.

## Why fixed +100% TP / -50% SL needs a challenger

V55's accepted original SPY June 9, 2025 600C long entry was four theoretical contracts bought at 10:33:02 ET for $474.60 including fees ($1.18 ask), closed at 15:30 bid $0.72 for $285.40 after fees; net -$189.20. Its full one-second quote tape reached **bid $1.61 at 12:52:47** but a fixed +100% bid target would require $2.36; fixed -50% would require $0.59. Neither triggered, so the strategy held until 15:30. A post-hoc price peak is **not** information a trader possessed earlier. Do not label a retrospectively chosen exit as profitable predictive alpha.

## Preregistered development challenger: dynamic risk + past-only volatility trailing

**Pre-trade limit**: portfolio reference start $25,000, existing maximum $500 option premium, $0.65 commission per contract on both sides. The *desired* risk-loss budget is 0.50% of opening account ($125) after modeled commissions; for four contracts originally purchased at $1.18 this implies a **reference BID stop $0.8805**. It is not a guaranteed $125 loss cap: a bid jump, insufficient displayed size, no brokerage fill and an overnight gap can produce worse fills/losses up to the entire long premium.

**While position is open, each observation updates causally**:
- Option bid, ask, displayed size and relative spread (<=15%); no post-entry futures.
- Current unrealized exit profit net of both fees, account-relative risk budget, time of day and seconds since last original quote.
- Prior-only highest and lowest observed bid to date, high-water drawdown and rolling 60 quote mean absolute bid movement. A >60s gap or invalid quote is **censored**, not silently skipped.
- A *heuristic* possible next-five-minute upside envelope based only on past quote changes; it is **not** a trained/proven forecast, is audit-only and is not used for optimization or entry/exit.
- Activate profit protection when observed bid is at least 20% above entry ask. Maintain a trailing exit floor 10%-20% beneath the **highest BID observed so far**, widened only by trailing quote noise at the current clock. The stop is monotonic as high water improves, with risk-budget hard floor remaining active.
- Exit at first observed BID <= risk floor, below activated trailing floor, or 15:00 ET, subject to sufficient displayed BID size; preserve true trigger quote rather than replacing it with the intended stop level. Realized stop losses can exceed the budget if price jumps across the threshold.
- Record *every* observed decision, threshold, risk state, bid/ask spread, expected net exit cash and the reason for holding/exiting.

**Anti-hindsight / anti-promotion**: This is a separate registered experiment. The V55 and V56 fixed-exit results stay unchanged. Policy selection after seeing June 9 outcome means **do not choose this exit policy because it happens to improve June 9**. Future candidate policies should be selected using earlier training folds and evaluated on chronologically later untouched periods; models of *maximum favorable excursion (MFE)* or the conditional future high must use strictly prior training/known decision-time features only. Report walk-forward net expectancy, average R, profit factor, risk-adjusted drawdown, win/loss size, cost sensitivity, quote/fill quality, adverse jumps and coverage by weekly/monthly/annual window. The original 2026 master holdout is already consumed; don't label it virgin.

## Offline initial side-by-side acceptance

Run after merge; it only reads the already archived V55 2025-06-09 JSON + verified SHA-linked JSONL and produces a new complete immutable adaptive-decision JSON report. It performs **zero provider requests** and **zero broker orders**, and never alters original source or baseline journal.

```powershell
& '.\.venv\Scripts\python.exe' -m scripts.run_spy_v57_adaptive_exit_shadow `
  --input 'data/research/spy_v55_closed_bar_quote_20261030_211559.json' `
  --output "data/research/spy_v57_adaptive_shadow_$(Get-Date -Format yyyyMMdd_HHmmss).json"
```

**What this comparison can show:** Whether fixed thresholds vs a predeclared responsive trailing/risk policy produce different *modeled quote-reference* dispositions when both use exactly the same previously observed historical tape and commissions. It cannot answer whether either policy is superior across multiple trade dates, because we have only a single exploratory trade at this stage.

**Next integration after V56 cohort:** Evaluate the frozen challenger and baseline across identical underlying option tapes and independent portfolios, including holding beyond the earlier baseline exit when the complete original cached quote tape is available. When only the truncated V55 event stream is available, a challenger whose position outlasts the baseline receives `CENSORED_AT_PARENT_BASELINE_EXIT`, **not** fabricated later profit. Candidate MFE forecasts may be added only with an auditable prior-only training cohort, model fingerprint and true pre-decision feature provenance.

## Reference context

Cboe documents the extremely high intraday sensitivity of 0DTE options near expiration: https://www.cboe.com/tradable-products/0dte . The SEC warns that a triggered stop normally becomes a market order and price is not guaranteed, and trailing stops are not a substitute for controlled executions: https://www.investor.gov/introduction-investing/general-resources/news-alerts/alerts-bulletins/investor-bulletins-15 . Those references support risk controls and caution, **not** the numeric parameters or a profitability claim.
