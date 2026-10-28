# V34 — Fast historical SPY quote-cash scenarios, not executed strategy returns

## Motivation and workstation checkpoint (October 28, 2026)

The workstation's V33 paid acquisition completed **2,344 / 2,352** exact SPY option-right original archives, **zero unattempted**, and **eight earlier uncertain STARTED identities not retried**. V32 (fingerprint \`a0bfbd1ae8db9d3b502ee21780db17a23d37d5284655611167078c5a870c365e\`) observed **361** preselected original entry pairs out of **411** frozen weekly clocks, with **50** original abstentions. Recovered valid selected-pair exit quotes:

| Post-entry review session | Original | New exact | Total matched / 361 | Unresolved |
| --- | ---: | ---: | ---: | ---: |
| 1 | 184 | 123 | 307 | 54 |
| 2 | 130 | 192 | 322 | 39 |
| 3 | 100 | 207 | 307 | 54 |
| 4 | 83 | 199 | 282 | 79 |
| 5 | 53 | 243 | 296 | 65 |

**1,514 / 1,805** selected entry+review observations are qualified as paired 10:00 historical quotes; **291 / 1,805** remain missing or unqualified. The five review populations overlap (same 361 entries); 1,514 is not a count of independent trades. This coverage is enough to begin a carefully labeled diagnostic without another broad source campaign.

## Implemented rapid diagnostic

\`packages/simulation/options_native_spy_quote_account_diagnostic_v34.py\` accepts the **saved** V32 JSON report, verifies its original V32 SHA-256 content fingerprint and all 361×5 frozen denominators, and analyzes 20 predeclared quote scenarios: 1–5 exit sessions, $0.65/$1.30 commission per contract per side, and $0/$0.05 adverse slippage per share per leg. It includes:

- Matched-only **conditional quote-to-quote percentage returns**, with unmatched cases explicitly counted and never imputed.
- A separate chronological **hypothetical quote-cash ledger** beginning at $100,000, allocating at most 10% of available cash per candidate, two open pair slots, and ten two-leg pairs per entry. Exit events occur before same-date entries; future observations never determine an earlier entry.
- A missing exit remains open and consumes cash/position capacity. No synthetic liquidation or later backfill is inserted. **Ending equity and return are NULL** if any unmarked positions remain; closed-position realized amounts are explicitly partial.
- Realized hypothetical P&L by exit ISO week, month, and year, never mislabeled as periodic investment returns. Drawdown is NULL without independent interim marks.
- Immutable separately written output and a registered, explicitly retrospective experiment before reading V32 outcome data.

The input is **real historical market data**, but the trade policy is explicitly **ALL preselected pairs hypothetically entered**. The options-native SPY volatility signal has not been calculated. Exact 10:00 observed asks and bids are *not demonstrated 10:01 executable fills*. This report is not an actual portfolio backtest, out-of-sample validation, paper result, broker order, or live authority. It must not be fed into synthetic \`ReplaySignal\` or ranked as validated alpha.

## Next local execution

Only after this PR merges and CI passes. The V32 report must be present at the workstation; the already printed fingerprint is fixed. This command makes **zero provider/broker calls** and writes an exclusive new report:

\`\`\`powershell
Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
git pull --ff-only origin main
$py = '.\.venv\Scripts\python.exe'
$inputTape = 'data/research/spy_quote_tape_post_v33_20261028_155608.json'
$output = "data/research/spy_v34_quote_cash_diagnostic_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
& $py -m scripts.run_options_native_spy_quote_account_diagnostic_v34 \`
  --tape $inputTape \`
  --expect-fingerprint 'a0bfbd1ae8db9d3b502ee21780db17a23d37d5284655611167078c5a870c365e' \`
  --output $output
if ($LASTEXITCODE -ne 0) { throw 'V34 source-based diagnostic stopped' }
Write-Host "V34 report: $output"
\`\`\`

## After V34 — simulator critical path

**P0:** Use V34's coverage/capital/fee sensitivity to decide whether the actual SPY pilot's economics warrant a full build; avoid spending the active ThetaData subscription repairing eight uncertain rights without a demonstrated coverage blocker.

**P1:** Implement frozen causal prior-20 SPY economic return variance, historical contemporaneous IV/Greeks with independently available rates, dividends and prior-state OI, then apply the actual preregistered SPY volatility entry signal. Entry eligibility must not read future review prices.

**P2:** Implement historical execution-time source qualification at 10:01, two-leg receipt/fill and cancellation events, terminal expiration/assignment, missing-price and equity marks, account risk and the V25 scenario grid on admitted events. Reuse existing two-leg coordinator and account mechanics, do not relabel quote simulations as historical fills.

**P3:** Compare frozen strategies across chronological development, later unconsumed qualification and prospective paper; then simulate combined capital/risk. Never reuse the already consumed 2026 master holdout as fresh proof. Do not assume profitable weekly/monthly/annual windows: disclose all, including losing and unresolved periods.
