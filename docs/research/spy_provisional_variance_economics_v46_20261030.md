# V46 — SPY 09:59 American-IV variance feasibility (explicitly exploratory)

## Observed workstation V45 evidence — 2026-10-30

The V45 report uploaded by the user, `spy_v45_two_clock_20261030_111449.json`, has fingerprint
`450da4ee779aad96b6656e1d7a03435bf3521875c72ebca6f69b845a7205bd5e`.
All 356 missing original 09:59 option quote source uses were fetched and archived
in about 53 seconds without a failure.

Of 361 original weekly selected dates, **323** have two-clock source quality passes,
**16** original cases failed the <=1-second 09:59 call/put skew requirement, and
**22** have no source-quality eligible pair. The 323 comprise **162** frozen
original selected pairs and **161** *separately versioned alternate* pairs.
Preserve the 50 original abstentions, so this is not 323 actual entries.

Two of the 323 have suspicious matching call and put bid/ask snapshots:
2018-04-02 (at 10:01) and 2021-06-21 (at 09:59). V46 excludes them
rather than inferring that the source identity was correct.

As a preliminary economic observation, the 323 passed 10:01 bid/ask
snapshots had median two-leg entry debit of approximately **$1,637**
and median immediate two-sided crossing loss of **$8 per one-contract
straddle**, prior to commissions and extra slippage. These values are
not results of a trading strategy or verified executable fills.

## What this stage does

V46 uses the exact, previously archived 09:59 call/put quote snapshots from V45,
the 20-previous-return **retrospective raw-price volatility** proxy from V37,
and the **existing V41 101-step American Leisen-Reimer IV engine** to compare
forecast annual variance with model pair-IV variance under **three explicitly
assumed** rate/dividend scenarios:

- Low-rate/zero-yield: rate 1%, yield 0%
- Mid-rate/moderate-yield: rate 4%, yield 1.5%
- High-rate/high-yield: rate 8%, yield 3%

Assume 16:00 ET on the recorded expiry date as model maturity. That timestamp
is **not verified OCC exercise/expiry timing**. None of the three rate/yield pairs
is evidence that those values were known on a historical decision date.
The retrospective raw-price return volatility is **not** the historically
qualified 20-return economic forecast. V41's continuous yield approximation
is **not** an accepted discrete ex-dividend exercise model.

Classify dates separately as hypothetical long across all three scenarios,
hypothetical abstain across all, scenario-dependent/IV-unsolvable,
source rejected, anomalous, or missing retrospective prior-return proxy.
Keep original and alternate strategy identities separate. No parameters
are fit on outcomes and no future exit data is read or used for entry selection.

**This is intentionally an exploratory filter, NOT a completed pilot entry
signal, historical order, actual broker fill, or profitability backtest.**
It cannot be used to promote a strategy. An attractive scenario does not
authorize treating that date as a true historical trade.

## Workstation command (after PR merge and green CI)

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    if ((git branch --show-current).Trim() -ne 'main') { throw 'ATLAS must be on main' }
    if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked local changes present' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git update failed' }

    $v45 = 'data/research/spy_v45_two_clock_20261030_111449.json'
    $v37 = 'data/research/spy_v37_pretrade_20261029_162223.json'
    foreach ($path in @($v45, $v37)) {
        if (-not (Test-Path $path)) { throw "Required source report absent: $path" }
    }
    $out = "data/research/spy_v46_provisional_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & '.\.venv\Scripts\python.exe' -m scripts.run_spy_v46_provisional_signal --v45 $v45 --v37 $v37 --output $out
    if ($LASTEXITCODE -ne 0) { throw 'V46 exploratory calculation failed' }
    Write-Host "V46 exploratory sensitivity report: $out"
}
```

Run the three scenario variants, inspect counts across each year, and do
not optimize the historical strategy to these retrospective classifications.

## The actual next simulator milestone

Replace this assumption sensitivity with independently accepted historical
publication evidence for the prior 20 economic returns, underlying spot,
SOFR (decision-time), dividend expectations/discrete ex-date exercise model,
OCC 100-share deliverables and the exact predecision quotes. Drive the actual
frozen V41 variance decision, then stream **only true eligible entries and
their causally scheduled exit source requirements** through V39/V38. Build
chronological $100k account cash/event replay with one-call-plus-one-put
filled/partial/unresolved states, commissions/slippage, 5% debit cap,
one open pair, 5-session maximum and dynamic exit. Report all weeks/months/years
including abstentions and missing exits. No protected 2026 outcomes; no strategy
promotion without an independent evaluation window and qualified evidence.
