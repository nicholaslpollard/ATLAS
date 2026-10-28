# V36 — Continue the SPY quote-based account across 2018–2025 (explicit expiry-zero stress)

## Operator result / reason

The workstation successfully ran V34 on the immutable post-V33 V32 tape (report SHA `a0bfbd1ae8db9d3b502ee21780db17a23d37d5284655611167078c5a870c365e`) and saved `data/research/spy_v34_20261028_174204.json`, report SHA `4c76044d792d977aa03a1fd73a7f5e57e7befb09304be93d138a88eb3304dd24`.

V34 source-based conditional mean ask-to-bid option-pair returns, using the $0.65/contract/side fee and no extra slippage, were negative at every frozen exit: **−2.3580%, −2.2177%, −2.1766%, −2.1991%, −1.4973%** over matched selected cohort denominators **307/322/307/282/296** out of 361 original choices. Adverse slippage of $0.05/share/leg worsens the means to −3.8374%, −3.6942%, −3.6437%, −3.7161%, and −2.9902%. Conditioning on observed pairs does not establish general strategy performance.

The V34 chronological account engine retained two open positions indefinitely after missing review quotes, occupying both maximum slots for the rest of the experiment. Depending on horizon, **only 7–44 of 361** weekly opportunities were hypothetically opened, and the resulting ending equity was NULL. A source quality data repair of every missing review was not appropriate during the active options subscription.

## V36 isolated stress replay

V36 keeps the same **original immutable historical 10:00 quote tape** and frozen first-pair entry identities. It adds explicit contractual **expiration** events for positions that have *no qualified bid at the chosen review date*:

1. At each weekly entry, allocate cash and a position slot without reading future quote outcomes. Never select a different option or future-favorable exit.
2. At the frozen 1–5 session review, a verified original call+put bid can close a position **hypothetically** at the observed quote minus scenario fees/slippage.
3. If the review quote is missing or unqualified, retain full cost and the position slot through the original contract's expiry. **No sale is invented at the review date.**
4. After expiration, simulate **ZERO final proceeds** and charge the entire original debit as a loss in a separately labeled pessimistic cash-stress branch. This zero credit is a deliberate assumption, NOT observed settlement, a guarantee of worthless expiry, OCC exercise history, or an accepted mark. No future real quotes or protected outcomes are opened.

A position expiring on the same calendar date as a new weekly entry is only released *after* that entry's 10:01 clock, not prematurely.

Scenario grid: **5** hold horizons × **2** fees ($0.65/$1.30 per contract per side) × **2** adverse slippage assumptions ($0.00/$0.05 per share per leg) × **2** capacity policies = **40** retrospective source-linked cash stress cases.

Capacity baselines:

- Historical V34 comparison: 2 open straddles, 10% of available cash per new position, cap of 10 straddle contract-pairs per entry.
- Frozen SPY pilot **capacity geometry only**: maximum 1 open straddle, 1 straddle contract-pair per new entry, and 5% of available cash for the total debit. This **does not** implement its 20-return volatility predictor, historical IV/open-interest/rates/dividends, or 10:01 execution admission.

Each result tracks all **361** original selected pair opportunities regardless of capital or later missing exits, trade skips, unobserved zero-credit expirations, modeled cash return, and weekly/monthly/annual model P&L. No unrealized marks/drawdown, real fills, actual underlying exercise proceeds or historical trading profitability are asserted. Research variant outcomes are retrospective; not an out-of-sample test.

## Operator execution (after PR CI success and merge)

Use the **existing V32 JSON** on the workstation, not the smaller V34 summary; no provider calls or storage-heavy acquisition.

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }
    $py = '.\.venv\Scripts\python.exe'
    $out = "data/research/spy_v36_expiry_stress_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & $py -m scripts.run_options_native_spy_expiry_zero_stress_v36 `
        --tape data/research/spy_quote_tape_post_v33_20261028_155608.json `
        --expect-fingerprint a0bfbd1ae8db9d3b502ee21780db17a23d37d5284655611167078c5a870c365e `
        --output $out
    if ($LASTEXITCODE -ne 0) { throw 'V36 offline stress replay failed' }
    Write-Host "V36 report: $out"
}
```

## Critical path to actual historical strategy simulation

**Next code milestone:** separately reconstruct the 20 **previously completed** SPY economic log returns and time-qualified spot, independently available prior-session open interest, complete unadjusted deliverable proof, PIT rate/dividend and American-consistent IV for **each** frozen selection, then apply the actual signed volatility-vs-implied-variance entry signal. Separately qualify execution-event quotes at the frozen **10:01 ET** order clock, paired fills and a source-accepted exit/expiration/mark lifecycle. Only then is a true account-level historical strategy replay meaningful. The V36 zero-credit terminal scenarios are a diagnostic throughput tool, **not** evidence the actual straddle strategy wins or loses after real execution.

Preserve V29/V30/V32 source receipts and the previously opened 2026 master holdout. Do not resume broad SPY recovery solely to resolve 8 uncertain exact right IDs or the 291 absent/unqualified review observations.
