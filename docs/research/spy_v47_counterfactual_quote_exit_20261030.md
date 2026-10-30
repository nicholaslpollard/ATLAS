# V47 — first full-cohort conditional SPY option exit-price economics

## Historical evidence (October 30, 2026)

Workstation V46 `data/research/spy_v46_provisional_20261030_115607.json`
fingerprint `966a6155d57423cd680a26a84bc5bf85e6d02b1f0f06015037612659ef0cc2f7`
reconciles 361 original selected weekly SPY dates across 2018–2025:
106 robust **hypothetical** long positions across all three rate/yield scenarios
(48 frozen-original, 58 separately versioned strike/expiry alternate),
206 robust abstentions, 7 scenario-dependent, 2 missing prior-return proxy,
2 anomalous identical call/put price observations and 38 source-quality rejected.
These classifications are *not historically qualified trading signals*.

V45 exact two-clock source fingerprint
`450da4ee779aad96b6656e1d7a03435bf3521875c72ebca6f69b845a7205bd5e`
is required for exact SPY CALL/PUT symbols, expirations and strikes and the
observed 10:01 paired option ask references.

## What V47 will actually do

1. Verify both immutable report fingerprints and the 361 date identities;
   select only V46's existing 106 unanimous hypothetical LONGs, not a new
   optimizer. Preserve **original vs. alternate** option cohorts.
2. Use the ATLAS XNYS exchange calendar to enumerate the next **five regular
   trading sessions** after each hypothetical 10:01 entry.
3. Request the **same** CALL and PUT exact option-contract 10:01 historical quotes
   on each exit session, one to five, via the V39/V38 read-through source cache.
   This is 106 x 5 x 2 = **1,060 exact source uses**. Provider calls are only
   needed for cache misses. Original source receipts are losslessly archived
   for future reuse. No artificial provider-call quota is imposed.
4. Require both source receipts with exact unique right/strike/expiry,
   non-crossed positive two-sided quotes, positive bid/ask sizes, <=15%
   relative spread, <=30 seconds age and <=1 second CALL/PUT time skew.
   Missing/invalid evidence is **censored**, not a zero exit or retroactive
   suppression of the hypothetical entry.
5. Compare the earlier paired entry **ASK** with later paired exit **BID**
   for each hold. The base reference charges $0.65 per option contract per
   side; a distinct stressed scenario applies one extra observed full
   spread to both legs on both entry and exit. Prices are not claimed to
   be executable broker fills.
6. Generate per-hold observed, censored and net-quote-return metrics with
   denominators. Also separately create five one-position-at-a-time
   hypothetical $100,000 cash ledgers **separately for original, alternate, and an explicitly new combined research variant** with the frozen 5% entry-debit
   constraint, for each price stress. A missing scheduled exit **keeps its
   position unresolved and blocks later hypothetical entries**;
   ending account equity is withheld when an open position cannot be marked.
7. Timestamped progress prints after each 10% of source requirements, with
   provider attempts, cached/fetched counts, observed throughput and rough ETA.

## Scientific boundaries

**This is a conditional, exploratory exit-price stress diagnostic, not the
frozen SPY pilot's historical dynamic-exit replay.** Its 106 entries derive
from V46's non-PIT raw-price prior volatility and hypothetical rate/dividend
scenarios, not historically qualified 20 economic returns, PIT SOFR/dividends
and 101-step American IV. The five fixed exit clocks replace the pilot's
dynamic daily variance recheck for research **only**; no trading strategy
revision, trial promotion or hindsight parameter choice is implied.
The model includes no actual simultaneous multi-leg order fills and never
calls quotes fills. Exact source availability at historical observation
time and original OCC deliverables remain unqualified.

Observed quote reference profitability is not actual trading profitability.
The account ledgers are **counterfactual** diagnostics; no broker, paper or
live execution orders are placed. Do not tune entry thresholds, pick the
best exit holding period, or make an OOS claim from this same development
interval. Missing exits remain visible.

## Local run after green CI and PR merge

```powershell
& {
    $ErrorActionPreference = 'Stop'
    Set-Location 'C:\Users\cyberdyne\Desktop\ATLAS'
    if ((git branch --show-current).Trim() -ne 'main') { throw 'ATLAS must be on main' }
    if (@(git status --porcelain --untracked-files=no).Count -gt 0) { throw 'Tracked changes present' }
    git pull --ff-only origin main
    if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }

    $v46 = 'data/research/spy_v46_provisional_20261030_115607.json'
    $v45 = 'data/research/spy_v45_two_clock_20261030_111449.json'
    foreach ($p in @($v46,$v45)) {
        if (-not (Test-Path $p)) { throw "Missing input report: $p" }
    }

    $output = "data/research/spy_v47_exits_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
    & '.\.venv\Scripts\python.exe' -m scripts.run_spy_v47_counterfactual_quote_exit `
        --v46 $v46 --v45 $v45 --output $output
    if ($LASTEXITCODE -ne 0) { throw "V47 exited with an error; inspect saved source receipts and console output" }
    Write-Host "V47 outcome report: $output"
}
```

## After V47

Use observed source coverage, *not* retrospective profits, to prioritize
integrating historical source publication and proper PIT 20 economic return
variance, SOFR/dividends/OCC 100-share deliverables and native discrete
exercise into V41's 101-step IV. Then replace fixed-hold economics with the
specified *causal* daily dynamic exit recheck, qualified multi-leg fill
model, real sequential $100k account, fees/slippage, censored outcomes, and
weekly/monthly/annual P&L with independent future validation.
